#!/usr/bin/env python3
"""通道 2 差分测试 #46 · **購地卡（卡 3）`0x442325`** ＋ **拍賣卡（卡 8）`0x443225`**

两张卡都在 `card_functions[]` 里、PRD（`cards.md` §卡 3/§卡 8）也有完整规格，
但**从未被驱动过**。它们的共同看点：**仇恨增量按 8 字节 double 压栈**，
而 `0x40df69` 只读低 32 位 —— 与黑卡（卡 25）同一类栈错位 bug。

```asm
; ── 卡 3 購地卡 0x442325（222 条 / 765 字节）—— 作用对象 = **脚下那格** ──
0044234b  code = 格表[node*40 + 0x20]（u16）
          2000 < code < 4000 → 住宅用地[code-2000]，步长 0x34
          4000 < code < 6000 → 商業用地[code-4000]，步长 0x38（0x498e88）
0044237b  owner == 0 或 owner == cur+1 ⇒ 返回 0（不扣卡）
   住宅:  00442399  price = (level*[+0x1e] + [+0x1c]) * price_index
   商業:  0044250b  price = (level*[+0x24] + [+0x22]) * price_index
004423b5  price > cash ⇒ 显示「您的現金不足！」、返回 0（不扣卡）
004423c4  ① 仇恨（**double 压栈**）：value = (price_index*地价) * (level+2)/5.0
004423fb     0x40df69(owner-1, cur, value)：被调方只读低 32 位
0044242f  ② say(cur, 3, 表B[ch][2])
0044243e  ③ owner = cur+1
0044246c  ④ flast：住宅写 **+0x30**、商業写 **+0x34**（`[0x499110] != 0` 才写）
00442479  ⑤ pay_money(cur, owner-1, price, 0)
00442610  ⑥ remove_card(cur, 3)；返回 1

; ── 卡 8 拍賣卡 0x443225（203 条 / 667 字节）──
0044327f  地块分支：owner != 0 ⇒ 同一套 double 压栈的仇恨（地价取 [+0x1c]，商業取 [+0x22]）
004432ee  say(cur, 3, 表B[ch][7])
0044330a  owner != cur+1 ⇒ say(owner-1, 1, 表B[ch][67])
0044334f  0x43bde5(cur, 地产编号, 1)   ; 开拍卖
00443359  返回 0（没卖出去）⇒ owner = 0、flast(+0x30) = 0、重绘 ⇒ 仍算成功
0044336b  ebx = 1；00443370 jmp 收尾（remove_card(cur,8) / 返回 1）
00443375  商業同一套（编号区间 0xfa0..0x1770）
```

## 打桩

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41d2c6` | `pay_money(from,to,amount,flags)` | 记四实参（自身已被 `test_money_move.py` 验过）|
| `0x40a4e1` | 重绘地产 | 记实参 + 计数 |
| `0x4521cb` | 「日期 + 年限」= 地契到期日 | 记两实参 + 返回**可控值** |
| `0x441343` | `remove_card` | 记实参 |
| `0x44ef41` | `player_say` | 记三实参 |
| `0x440cac` | 显示消息 | 记两实参 |
| `0x43bde5` | 开拍卖（`auction(玩家, 地产号, 1)`）| 记三实参 + 返回**可控值** |

★ `0x40df69`（`update_hostility`）**不打桩、真跑** —— 仇恨那笔「double 低 32 位」
是本轮的核心看点，直接读最终关系值对模型。

跑法：cd rich4-spec && .venv/bin/python tests/test_land_auction_cards.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

BUY_LAND, AUCTION, REBUILD = 0x442325, 0x443225, 0x44309B
PAY_MONEY, REDRAW, DEED_DATE = 0x41D2C6, 0x40A4E1, 0x4521CB
REMOVE_CARD, SAY, SHOW, OPEN_AUCTION, REFRESH, UI_END = (
    0x441343, 0x44EF41, 0x440CAC, 0x43BDE5, 0x41D546, 0x41906A)
HUMAN_TYPE, AI_PICK = 0x440AAC, 0x41E6F2

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_NODE, P_CASH, P_CHAR, P_WHO = 0x0C, 0x1C, 0x13, 0x15
P_HOSTILITY = 0x4C
NODE_TABLE_PTR, HOUSING_PTR, COMMERCIAL_PTR = 0x498E80, 0x498E84, 0x498E88
DEED_INDEX, DATE_NOW, DEED_YEARS = 0x499110, 0x497160, 0x4751F0
CUR, PRICE_INDEX = 0x49910C, 0x4990E8
CARD_TABLE = 0x48123A
NODE_STRIDE, CELL_ENTITY = 40, 0x20
HOUSING_STRIDE, COMM_STRIDE = 0x34, 0x38
L_OWNER, L_LEVEL, L_LAND_PRICE, L_HOUSE_PRICE, L_FLAST, L_TYPE = 0x19, 0x1A, 0x1C, 0x1E, 0x30, 0x18
C_OWNER, C_LEVEL, C_PRICE_A, C_PRICE_B, C_FLAST, C_TYPE = 0x19, 0x1A, 0x22, 0x24, 0x34, 0x18
CODE_HOUSING, CODE_COMMERCIAL = 2001, 4001

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE90
PAY_N, M_PAY = S + 0x900, S + 0x920
REDRAW_N, M_REDRAW = S + 0x980, S + 0x990
DEED_N, M_DEED, DEED_RET = S + 0x9A0, S + 0x9C0, S + 0x9E0
RMC1, RMC2 = S + 0xA00, S + 0xA04
SAY_N, M_SAY = S + 0xA20, S + 0xA40
SHOW_N, M_SHOW = S + 0xAA0, S + 0xAC0
AUC_N, M_AUC, AUC_RET = S + 0xB00, S + 0xB20, S + 0xB40
ZERO = S + 0xB60
C_REFRESH = S + 0xB70
C_END = S + 0xB74
TYPE_RET, AI_RET, M_TYPE_ARG, M_AI_ARG = S + 0xB80, S + 0xB84, S + 0xB88, S + 0xB8C
NODES = S + 0x2000
HOUSING = S + 0x3000
COMMERCIAL = S + 0x4000
A1, A2, A3, A4 = 0x24, 0x28, 0x2C, 0x30
ALL_SLOTS = [SEQ, SEQ_N, PAY_N, REDRAW_N, DEED_N, DEED_RET, RMC1, RMC2, SAY_N,
             SHOW_N, AUC_N, AUC_RET, ZERO, C_REFRESH, C_END, TYPE_RET, AI_RET,
             M_TYPE_ARG, M_AI_ARG]
for base, n in ((M_PAY, 4), (M_REDRAW, 1), (M_DEED, 2), (M_SAY, 3), (M_SHOW, 2),
                (M_AUC, 3)):
    ALL_SLOTS += list(range(base, base + 4 * n, 4))
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def _log(code):
    return (b"\xB8" + struct.pack("<I", code)
            + b"\x8B\x1D" + struct.pack("<I", SEQ_N)
            + b"\x89\x04\x9D" + struct.pack("<I", SEQ)
            + b"\xFF\x05" + struct.pack("<I", SEQ_N))


def _rec(off, slot):
    return b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)


def _count(n_slot):
    return b"\xFF\x05" + struct.pack("<I", n_slot)


def _list(n_slot, count, base):
    code = (b"\x8B\x1D" + struct.pack("<I", n_slot)
            + b"\x6B\xDB" + bytes([4 * count])
            + b"\x81\xC3" + struct.pack("<I", base))
    for k in range(count):
        code += _rec(A1 + 4 * k, ZERO) + b"\x89\x43" + bytes([k * 4])
    return code + _count(n_slot)


def _stub(body):
    return b"\x60" + body + b"\x61\xC3"


def _stub_ret(body, ret_slot):
    """★ 要返回值的桩：返回值必须在 **popad 之后**写"""
    return b"\x60" + body + b"\x61" + b"\xA1" + struct.pack("<I", ret_slot) + b"\xC3"


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def written(low):
    """`0x40df69` 的早期返回：当前关系值为 0 且增量为负 ⇒ 直接返回（不写）"""
    return low if low > 0 else 0


def hostility_model(land_price, level, price_index):
    """原版算式：`fild(地价×物价) ; fild(等级) fadd 2.0f fdiv 5.0f ; fmulp ; fstp qword` 的低 32 位

    ★ 写法照 asm 次序、按 **double 精度**逐步舍入：x87 默认精度控制字 `0x027F`
    （PC = 10b = 53 位 = double），故 `fild A` → `(等级+2)/5` → `fmulp` 每一步
    都舍成 double，与 JS 的 `A * ((level + 2) / 5)` **逐位相同**。
    实测（真跑原版 `0x40df69`）：`A=1001, 等级 2` ⇒ 低 32 位 = **+1717986919**；
    若写成「精确乘积 ÷ 5」会得到 +1717986918（差 1 ulp）。
    """
    value = (land_price * price_index) * ((level + 2) / 5)
    low = struct.unpack("<i", struct.pack("<d", value)[:4])[0]
    return low


class F:
    def __init__(self):
        e = self.emu = Emu()
        e.patch(PAY_MONEY, _stub(_log(1) + _list(PAY_N, 4, M_PAY)))
        e.patch(REDRAW, _stub(_log(2) + _list(REDRAW_N, 1, M_REDRAW)))
        e.patch(DEED_DATE, _stub_ret(_log(3) + _list(DEED_N, 2, M_DEED), DEED_RET))
        e.patch(REMOVE_CARD, _stub(_log(4) + _rec(A1, RMC1) + _rec(A2, RMC2)))
        e.patch(SAY, _stub(_log(5) + _list(SAY_N, 3, M_SAY)))
        e.patch(SHOW, _stub(_log(6) + _list(SHOW_N, 2, M_SHOW)))
        e.patch(OPEN_AUCTION, _stub_ret(_log(7) + _list(AUC_N, 3, M_AUC), AUC_RET))
        e.patch(REFRESH, _stub(_log(8) + _count(C_REFRESH)))
        e.patch(UI_END, _stub(_log(9) + _rec(A1, C_END)))
        e.patch(HUMAN_TYPE, _stub_ret(_log(10) + _rec(A1, M_TYPE_ARG), TYPE_RET))
        e.patch(AI_PICK, _stub_ret(_log(11) + _rec(A1, M_AI_ARG), AI_RET))

    def _setup(self, cur=0, node=1, code=0, cash=100000, who=1, char=0, price_index=1,
               housing=None, commercial=None, players=None, deed_index=0, date=0,
               deed_ret=12345, auc_ret=1, occupancy=None, types=None, deed_years=11,
               type_ret=0, ai_ret=0):
        housing = housing or {}
        commercial = commercial or {}
        players = players or [{} for _ in range(4)]
        occupancy = occupancy or {}

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            emu.write32(CUR, cur)
            emu.write32(PRICE_INDEX, price_index)
            emu.write32(DEED_INDEX, deed_index)
            emu.write32(DATE_NOW, date)
            emu.write32(DEED_RET, deed_ret)
            emu.write32(DEED_YEARS + 4 * deed_index, deed_years)
            emu.write32(AUC_RET, auc_ret)
            emu.write32(TYPE_RET, type_ret)
            emu.write32(AI_RET, ai_ret)
            emu.write(NODES, b"\x00" * 0x400)
            emu.write(HOUSING, b"\x00" * 0x800)
            emu.write(COMMERCIAL, b"\x00" * 0x800)
            emu.write32(NODE_TABLE_PTR, NODES)
            emu.write32(HOUSING_PTR, HOUSING)
            emu.write32(COMMERCIAL_PTR, COMMERCIAL)
            emu.write(PLAYER_BASE, b"\x00" * (4 * STRIDE))
            for i, spec in enumerate(players):
                pb = PLAYER_BASE + i * STRIDE
                emu.write16(pb + P_NODE, spec.get("node", node if i == cur else 0))
                emu.write32(pb + P_CASH, spec.get("cash", cash if i == cur else 0))
                emu.write8(pb + P_CHAR, spec.get("char", char if i == cur else 0))
                emu.write8(pb + P_WHO, spec.get("who", who if i == cur else 2))
                for b in range(4):
                    emu.write32(pb + P_HOSTILITY + 4 * b, spec.get("host", 0))
            # 脚下那一格的「地产编号」（`+0x20`，u16）
            emu.write16(NODES + node * NODE_STRIDE + CELL_ENTITY, code)
            for idx, spec in housing.items():
                b = HOUSING + idx * HOUSING_STRIDE
                emu.write8(b + L_OWNER, spec.get("owner", 0))
                emu.write8(b + L_LEVEL, spec.get("level", 0))
                emu.write8(b + L_TYPE, spec.get("type", 0))
                emu.write16(b + L_LAND_PRICE, spec.get("landPrice", 0))
                emu.write16(b + L_HOUSE_PRICE, spec.get("housePrice", 0))
                emu.write32(b + L_FLAST, spec.get("flast", 0x0AAAAAAA))
            for idx, spec in commercial.items():
                b = COMMERCIAL + idx * COMM_STRIDE
                emu.write8(b + C_OWNER, spec.get("owner", 0))
                emu.write8(b + C_LEVEL, spec.get("level", 0))
                emu.write8(b + C_TYPE, spec.get("type", 0))
                emu.write16(b + C_PRICE_A, spec.get("priceA", 0))
                emu.write16(b + C_PRICE_B, spec.get("priceB", 0))
                emu.write32(b + C_FLAST, spec.get("flast", 0x0BBBBBBB))
        return setup

    def run(self, va, hidx=1, cidx=1, **kw):
        r = self.emu.call(va, [], setup=self._setup(**kw))
        e = self.emu
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 20))],
            "pay": [[e.readu32(M_PAY + 16 * i + 4 * k) for k in range(4)]
                    for i in range(e.readu32(PAY_N))],
            "redraw": [e.readu32(M_REDRAW + 4 * i) for i in range(e.readu32(REDRAW_N))],
            "deed": [[e.readu32(M_DEED + 8 * i + 4 * k) for k in range(2)]
                     for i in range(e.readu32(DEED_N))],
            "rmc": (e.readu32(RMC1), e.readu32(RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4),
                      e.readu32(M_SAY + 12 * i + 8)) for i in range(e.readu32(SAY_N))],
            "show": [[e.readu32(M_SHOW + 8 * i + 4 * k) for k in range(2)]
                     for i in range(e.readu32(SHOW_N))],
            "auc": [[e.readu32(M_AUC + 12 * i + 4 * k) for k in range(3)]
                    for i in range(e.readu32(AUC_N))],
            "refresh": e.readu32(C_REFRESH),
            "ui_end": e.readu32(C_END),
            "type_arg": e.readu32(M_TYPE_ARG),
            "ai_arg": e.readu32(M_AI_ARG),
            "h_type": e.read8(HOUSING + hidx * HOUSING_STRIDE + L_TYPE),
            "h_level": e.read8(HOUSING + hidx * HOUSING_STRIDE + L_LEVEL),
            "c_type": e.read8(COMMERCIAL + cidx * COMM_STRIDE + C_TYPE),
            "c_level": e.read8(COMMERCIAL + cidx * COMM_STRIDE + C_LEVEL),
            "owner": e.read8(HOUSING + hidx * HOUSING_STRIDE + L_OWNER),
            "flast": e.read32(HOUSING + hidx * HOUSING_STRIDE + L_FLAST),
            "c_owner": e.read8(COMMERCIAL + cidx * COMM_STRIDE + C_OWNER),
            "c_flast": e.read32(COMMERCIAL + cidx * COMM_STRIDE + C_FLAST),
            "host": [[e.read32(PLAYER_BASE + i * STRIDE + P_HOSTILITY + 4 * b)
                      for b in range(4)] for i in range(4)],
        }

    def cstr(self, va):
        return self.emu.img.cstr(va)


def main():
    print("差分测试 #46：購地卡 `0x442325`（卡 3）＋ 拍賣卡 `0x443225`（卡 8）\n")
    f = F()

    print("[A] 卡 3 · 住宅支：订价 / 仇恨（double 低 32 位）/ 改主 / 地契 / 付款")
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 2, "level": 3, "landPrice": 1001, "housePrice": 200}},
              deed_index=2, date=777, deed_ret=88888)
    case("★ 价格 = (level×房价 + 地价) × 物价 = 3×200+1001 = 1601（下标 = code-2000）",
         s["pay"], [[0, 1, 1601, 0]])
    case("★★ 付款：`pay_money(cur, owner-1, 价格, 0)`（收款人 1-based → 0-based）",
         (s["pay"][0][0], s["pay"][0][1], s["pay"][0][3]), (0, 1, 0))
    case("★★ `owner` 写成 **cur+1**（1-based，不是 0-based）", s["owner"], 1)
    case("★★ 地契到期日：`0x4521cb(日期, 年限表[deed_index])`，住宅写 **+0x30**",
         (s["deed"], s["flast"]), ([[777, 11]], 88888))
    case("★ 扣卡 `(cur, 3)`、返回 1", (s["rmc"], s["ret"]), ((0, 3), 1))
    case("★ 施卡者台词 = 表B 槽 2（`#0428讓我把它\n據為己有！！`）",
         (s["says"][0][0], s["says"][0][1], f.cstr(s["says"][0][2])),
         (0, 3, "#0428讓我把它\n據為己有！！"))
    case("★★ **原地主**的反应台词（表B 槽 62，槽位参数 1）—— 这一段 PRD 原先漏了",
         (s["says"][1][0], s["says"][1][1], f.cstr(s["says"][1][2])),
         (1, 1, "#0461好大的膽子！！"))
    case("★ 收尾 `refresh_map()` 一次；卡 8 另有 `0x41906a(1)`", s["refresh"], 1)

    case("★ 重绘地产一次", s["redraw"], [0])
    low = hostility_model(1001, 3, 1)
    case("★★ 仇恨 = `(物价×地价) × (等级+2)/5` 的 double **低 32 位**（等级 3 ⇒ 5/5 整除 ⇒ 0）",
         (s["host"][1][0], low), (written(low), 0))
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 2, "level": 2, "landPrice": 1001, "housePrice": 200}},
              deed_index=2, date=777)
    low = hostility_model(1001, 2, 1)
    case("★★★ 等级 2 ⇒ 4/5 不整除 ⇒ 低 32 位 = **+1717986919**（原版真写垃圾值）",
         (s["host"][1][0], low, low > 0), (written(low), 1717986919, True))

    print("\n[B] 卡 3 · 失败路径（都不扣卡）")
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1, housing={1: {"owner": 0}})
    case("★★ 无主地 ⇒ 返回 0、不扣卡、不付款", (s["ret"], s["rmc"], s["pay"]), (0, (0, 0), []))
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1, housing={1: {"owner": 1}})
    case("★★ 已是自己的地（owner == cur+1）⇒ 返回 0、不扣卡",
         (s["ret"], s["rmc"]), (0, (0, 0)))
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1, cash=100,
              housing={1: {"owner": 2, "level": 3, "landPrice": 1001, "housePrice": 200}})
    case("★★ 现金不足 ⇒ 显示「您的現金不足！」+ 返回 0、不扣卡",
         (s["ret"], s["rmc"], [x[1] for x in s["show"]],
          f.cstr(s["show"][0][0]) if s["show"] else None),
         (0, (0, 0), [0x5DC], "您的現金不足！"))
    s = f.run(BUY_LAND, cur=0, node=1, code=1500, hidx=1)
    case("★ 脚下那格不是地产（编号 1500）⇒ 返回 0、不扣卡", (s["ret"], s["rmc"]), (0, (0, 0)))
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 2, "level": 0, "landPrice": 1001, "housePrice": 200}},
              deed_index=0)
    case("★★ `[0x499110] == 0` ⇒ **不调**到期日函数、`flast` 保持旧值",
         (s["deed"], s["flast"]), ([], 0x0AAAAAAA))

    print("\n[C] 卡 3 · 商業支（步长 0x38；价格用 `level×[+0x24] + [+0x22]`；flast 在 **+0x34**）")
    s = f.run(BUY_LAND, cur=1, node=1, code=CODE_COMMERCIAL, cidx=1,
              housing={}, commercial={1: {"owner": 3, "level": 2, "priceA": 700, "priceB": 300}},
              deed_index=1, date=555, deed_ret=66666, players=[{}, {}, {}, {}])
    case("★★ 商業价格 = 2×300 + 700 = 1300（**另一个步长/另一组字段**）",
         s["pay"], [[1, 2, 1300, 0]])
    case("★★ 商業 `flast` 写 **+0x34**（住宅是 +0x30）", s["c_flast"], 66666)
    case("★ 商業 `owner` 同样写 cur+1", s["c_owner"], 2)
    case("   （本用例没铺住宅数组 ⇒ 它仍是全 0，一个字节没动）", s["flast"], 0)
    s = f.run(BUY_LAND, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1,
              commercial={1: {"owner": 0}})
    case("★ 商業无主 ⇒ 返回 0、不扣卡", (s["ret"], s["rmc"]), (0, (0, 0)))

    print("\n[D] 卡 8 · 拍賣卡：仇恨（同一套 double 压栈）+ 台词 + 开拍卖")
    s = f.run(AUCTION, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 2, "level": 3, "landPrice": 1001, "housePrice": 200}},
              auc_ret=1)
    low = hostility_model(1001, 3, 1)
    case("★★★ 地块分支的仇恨与卡 3 **同一个公式**（地价取 `+0x1c`）",
         (s["host"][1][0], low), (written(low), 0))
    case("★★ 开拍卖 `0x43bde5(cur, 地产编号, 1)`",
         s["auc"], [[0, CODE_HOUSING, 1]])
    case("★★ 两句台词：施卡者槽 7、受害者槽 67（1-based 原位主）",
         [(x[0], x[1], f.cstr(x[2])) for x in s["says"]],
         [(0, 3, "#0433漫天喊價\n就地還錢！"), (1, 1, "#0466誰敢買試試看！")])
    case("★ 拍卖成功 ⇒ 扣卡、返回 1、`owner` 不动",
         (s["rmc"], s["ret"], s["owner"]), ((0, 8), 1, 2))

    s = f.run(AUCTION, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 2, "level": 3, "landPrice": 1001, "housePrice": 200}},
              auc_ret=0)
    case("★★ 流拍（`0x43bde5` 返回 0）⇒ `owner = 0`、`flast = 0`、重绘，**仍算成功**",
         (s["owner"], s["flast"], s["redraw"], s["ret"], s["rmc"]),
         (0, 0, [0], 1, (0, 8)))
    s = f.run(AUCTION, cur=0, node=1, code=CODE_HOUSING, hidx=1, housing={1: {"owner": 0}})
    case("★★ 无主地 ⇒ **不记仇恨**、跳过受害者台词，照常开拍卖 + 扣卡",
         (s["host"][1][0], len(s["says"]), s["ret"]), (0, 1, 1))
    s = f.run(AUCTION, cur=0, node=1, code=CODE_HOUSING, hidx=1, housing={1: {"owner": 1}})
    case("★★ 是自己的地 ⇒ 同样跳过受害者台词（`owner == cur+1`）",
         (len(s["says"]), s["says"][0][0]), (1, 0))
    s = f.run(AUCTION, cur=0, node=1, code=1500)
    case("★★ 脚下不是地产/設施 ⇒ 返回 0、不扣卡、不开拍卖",
         (s["ret"], s["rmc"], s["auc"]), (0, (0, 0), []))
    s = f.run(AUCTION, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1,
              commercial={1: {"owner": 2, "level": 1, "priceA": 1001, "priceB": 0}})
    low = hostility_model(1001, 1, 1)
    case("★★ 商業分支：地价取 `+0x22`、编号区间 `0xfa0..0x1770`（低 32 位为负 ⇒ 不写）",
         (s["host"][1][0], s["auc"][0][1]), (written(low), CODE_COMMERCIAL))
    case("   （模型说低 32 位是负数 ⇒ `0x40df83` 的早期返回让它『看不见』）", low < 0, True)

    print("\n[E] ★★★ 「逐步 double 舍入」vs「精确乘积 ÷ 5」—— 用原版把这一步钉死")
    # x87 默认精度控制字 0x027F（PC = 10b = 53 位 = double）⇒ 每一步都舍成 double。
    # 两种写法在某些参数上差 1 ulp，垃圾值随之差 1 —— 原版给的是**逐步舍入**那个。
    for lp, lv, pi, want in ((3, 0, 1, 858993460), (1001, 2, 1, 1717986919)):
        s = f.run(AUCTION, cur=0, node=1, code=CODE_HOUSING, hidx=1, price_index=pi,
                  housing={1: {"owner": 2, "level": lv, "landPrice": lp}}, auc_ret=1)
        step = (lp * pi) * ((lv + 2) / 5)
        onediv = (lp * pi * (lv + 2)) / 5
        case(f"★★★ 地价{lp}/等级{lv}/物价{pi}：原版 = {want}（逐步舍入），一次除法会是"
             f"{struct.unpack('<i', struct.pack('<d', onediv)[:4])[0]}",
             (s["host"][1][0], struct.unpack("<i", struct.pack("<d", step)[:4])[0]), (want, want))

    print("\n[F] 卡 7 · 改建卡：住宅↔商業 翻转 / 商業要选类别 / 等级压制")
    s = f.run(REBUILD, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 1, "level": 3, "type": 0}})
    case("★★ 住宅（type 0）⇒ `type ^= 1` 变商業、**等级压到 1**", (s["h_type"], s["h_level"]), (1, 1))
    case("★ 台词 = 表B 槽 6；扣卡(7)；返回 1；收尾 refresh 一次",
         ((s["says"][0][0], s["says"][0][1], f.cstr(s["says"][0][2])), s["rmc"], s["ret"], s["refresh"]),
         ((0, 3, "#0432不必謝我！！"), (0, 7), 1, 1))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 1, "level": 3, "type": 1}})
    case("★★ 商業 → 住宅：翻回 0 时**不压等级**（翻转结果为 0）",
         (s["h_type"], s["h_level"]), (0, 3))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_HOUSING, hidx=1,
              housing={1: {"owner": 1, "level": 0, "type": 0}})
    case("★★ level == 0（未开发）⇒ 返回 0、不扣卡、不说话",
         (s["ret"], s["rmc"], s["says"]), (0, (0, 0), []))
    s = f.run(REBUILD, cur=0, node=1, code=1500)
    case("★ 脚下不是地产 ⇒ 返回 0、不扣卡", (s["ret"], s["rmc"]), (0, (0, 0)))

    s = f.run(REBUILD, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1, who=1, type_ret=3,
              commercial={1: {"owner": 1, "level": 3, "type": 1}})
    case("★★ 商業支：人类走选類別窗 `0x440aac(1)`", s["type_arg"], 1)
    case("★★ 选中类别 3（加油站）⇒ 写 `+0x18 = 3` 且**等级压到 1**",
         (s["c_type"], s["c_level"]), (3, 1))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1, who=1, type_ret=4,
              commercial={1: {"owner": 1, "level": 3, "type": 1}})
    case("★★ 类别 4（研究所）⇒ 写 4、**等级保持 3**", (s["c_type"], s["c_level"]), (4, 3))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1, who=1, type_ret=-1,
              commercial={1: {"owner": 1, "level": 3, "type": 1}})
    case("★★ 选類別窗返回 −1（取消）⇒ 返回 0、不扣卡、类型不变",
         (s["ret"], s["rmc"], s["c_type"]), (0, (0, 0), 1))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1, who=2, ai_ret=0,
              commercial={1: {"owner": 1, "level": 3, "type": 1}})
    case("★★ 电脑走 `0x41e6f2(0)`（实参 0）；类别 0（公園）⇒ 等级压到 1",
         (s["ai_arg"], s["c_type"], s["c_level"]), (0, 0, 1))
    s = f.run(REBUILD, cur=0, node=1, code=CODE_COMMERCIAL, cidx=1, who=1, type_ret=2,
              commercial={1: {"owner": 1, "level": 0, "type": 1}})
    case("★★ 商業 level == 0 ⇒ 返回 0、不扣卡（连选類別窗都不开）",
         (s["ret"], s["rmc"], s["type_arg"]), (0, (0, 0), 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
