#!/usr/bin/env python3
"""通道 2 差分测试 #45 · **紅卡（卡 24）`0x444f25` / 黑卡（卡 25）`0x44503f` / 同盟卡（卡 29）`0x445710`**

三张卡在 `card_functions[]` 里都已实现、PRD 也有完整规格（`cards.md` §卡 24/25/29），
但**从未被驱动过**（工作单里各占一格，且都是「影响面 10 分」那一档）。

```asm
; ── 卡 24 紅卡 0x444f25（91 条 / 282 字节）──
00444f51  say(cur, 0, 表B[character][23])          ; '#0449跟著我買股票準沒錯！'
00444f6a  who_plays == 1 ? → 人类支 : AI 支
   AI: 00444f75 idx = 0x41e6f2(0)                  ; [0x48be58]（0-based）
       00444f88 stock[idx].trend = 0x20            ; 高 4 位非 0 ⇒ 涨
       00444f91 0x429040(idx+1)                    ; 重算价
       00444fc9 sprintf("對%s使用%s！", 名, "紅卡") / 00444fdb 显示 / ebx = 1
   人类: 00444ff0 0x4021f8(0xc,0xf,0xa) → 00444ffa 0x42b58f(1)（股市屏，内部写 trend+改价）
        → 0044500c 0x4021f8(0x29,1,0) → 00445016 0x41906a(1) → 00445020 取消(0) ⇒ 返回 0 不扣卡
00445022  remove_card(cur, 24); return ebx

; ── 卡 25 黑卡 0x44503f（133 条 / 433 字节）──
00445081  快照 12 支旧价到 [esp+0x80..]（stock[i]+0x14）
0044509e  who_plays == 1 ? 人类(同上，模式参数 2) : AI（trend = 2 ⇒ 跌、0x429040、显示）
0044515e  n == 0 ⇒ 返回 0 不扣卡
00445167  delta = old[n-1] - stock[n-1].price       ; float
00445184  for (p = 0; p < [0x499114]; p++)
0044519d      if (holdings[p][n] == 0) continue
004451a6      v = holdings[p][n] * delta / 200.0f
004451b9      sub esp,8 / fstp qword [esp]         ; ★ 按 **double** 压栈
004451c7      update_hostility(p, cur, v)          ; ★ 被调方只读 4 字节
004451d2  remove_card(cur, 25); return n

; ── 卡 29 同盟卡 0x445710（130 条 / 463 字节）──
0044573d  esi = 掩码；00445741 == 0 ⇒ 返回 0 不扣卡
00445750  remove_card(cur, 29)
00445788  say(cur, 3, 表B[character][28])          ; '#0454好哥兒們！！'
00445791  tgt = ctz(掩码)；人类不播 0x40e669
004457ef  若 cur 有旧盟友 ⇒ 双向清（旧盟友 +0x41/+0x3d、cur +0x41/+0x3d）
00445827  若 tgt 有旧盟友 ⇒ 双向清（同上）
00445866  cur.allied = tgt+1 / cur.+0x3d = 7 / tgt.allied = cur+1 / tgt.+0x3d = 7
0044589c  0x41d433(cur)                            ; 暂设当前玩家并重绘
004458c1  say(tgt, 0, 表B[character][88])          ; '#0476可別想占我便宜！'
004458d3  0x41d546()；return 掩码
```

## 打桩（13 个）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x441343` | `remove_card` | 记实参 + 序列 |
| `0x44ef41` | `player_say` | 记三实参（含**真表**指针）|
| `0x41e6f2` | AI 选股/选人 | 记实参 + 返回**可控值** |
| `0x446ae8` | 人类选人框 | 记参数 + 返回**可控掩码** |
| `0x42b58f` | 股市屏（模式参数 1=涨 / 2=跌）| 记参数 + 返回**可控值** |
| `0x4021f8` | 界面配色/状态 | 记三实参 |
| `0x41906a` | 收尾刷新 | 计数 |
| `0x429040` | 按走势字节重算价 | 记实参 + **把可控新价写进 `stock+0x14`** |
| `0x452946` | 去空格拷贝 | 记两实参 |
| `0x457110` | `sprintf` | 记四实参 |
| `0x440cac` | 显示消息 | 记两实参 |
| `0x40e669` | 落点动画 | 记六实参 |
| `0x41d433` | 暂设当前玩家 + 重绘 | 记实参 |
| `0x41d546` | `refresh_map` | 计数 |

★ `0x40d293`（`ctz`）、`0x40df69`（`update_hostility`）**不打桩、真跑** ——
后者是本轮的重点：黑卡把「持股数 × 价差 ÷ 200」按 **double** 压栈，而被调方只读 4 字节，
于是**真正写进关系值的是那个 double 的低 32 位**。本测试直接读最终关系值对模型。

跑法：cd rich4-spec && .venv/bin/python tests/test_stock_alliance_cards.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

RED, BLACK, ALLIANCE = 0x444F25, 0x44503F, 0x445710
REMOVE_CARD, SAY, AI_PICK, HUMAN_PICK = 0x441343, 0x44EF41, 0x41E6F2, 0x446AE8
STOCK_DIALOG, UI_SET, UI_END = 0x42B58F, 0x4021F8, 0x41906A
STOCK_APPLY, STRIP, SPRINTF, SHOW = 0x429040, 0x452946, 0x457110, 0x440CAC
ANIM, CAMERA, REFRESH = 0x40E669, 0x41D433, 0x41D546
HOSTILITY = 0x40DF69

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_X, P_Y, P_CHAR, P_WHO = 0x08, 0x0A, 0x13, 0x15
P_ALLIED, P_ALLIED_DAYS = 0x41, 0x3D
P_HOSTILITY = 0x4C                     # +0x4c + b*4
STOCK_BASE, STOCK_STRIDE = 0x496980, 36
S_NAME, S_TREND, S_PRICE, S_PREV = 0x00, 0x07, 0x14, 0x10
HOLDINGS = 0x497198                    # + p*96 + n*8（n 为 1-based）
CUR, NUM_PLAYERS = 0x49910C, 0x499114
CARD_TABLE = 0x48123A                  # 卡牌台词表（槽 = 卡号-1）
K23, K28, K88 = 0x481296, 0x4812AA, 0x48139A
STOCKS = 12

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE90
M_RMC1, M_RMC2 = S + 0x900, S + 0x904
SAY_N, M_SAY = S + 0x920, S + 0x940
PICK_RET, PICK_ARG = S + 0x9A0, S + 0x9A4
DLG_RET, DLG_ARG = S + 0x9A8, S + 0x9AC
APPLY_N, M_APPLY, NEW_PRICE = S + 0xA00, S + 0xA40, S + 0xA80
STRIP_N, M_STRIP = S + 0xAA0, S + 0xAC0
SPRINTF_N, M_SPRINTF = S + 0xB00, S + 0xB40
SHOW_N, M_SHOW = S + 0xB80, S + 0xBC0
UI_N, M_UI = S + 0xC00, S + 0xC40
C_END, ANIM_N, M_ANIM = S + 0xC80, S + 0xD00, S + 0xD40
CAM_N, M_CAM, C_REFRESH = S + 0xD80, S + 0xDA0, S + 0xDC0
ZERO = S + 0xE20
HERO_ALIVE = S + 0xE30                  # 玩家数（黑卡循环上界）
A1, A2, A3, A4 = 0x24, 0x28, 0x2C, 0x30
ALL_SLOTS = [SEQ, SEQ_N, M_RMC1, M_RMC2, SAY_N, PICK_RET, PICK_ARG, DLG_RET, DLG_ARG,
             APPLY_N, NEW_PRICE, STRIP_N, SPRINTF_N, SHOW_N, UI_N, C_END, ANIM_N,
             CAM_N, C_REFRESH, ZERO, HERO_ALIVE]
for base, n in ((M_SAY, 3), (M_APPLY, 1), (M_STRIP, 2), (M_SPRINTF, 4), (M_SHOW, 2),
                (M_UI, 3), (M_ANIM, 6), (M_CAM, 1)):
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


class F:
    def __init__(self):
        self.emu = Emu()
        e = self.emu
        e.patch(REMOVE_CARD, _stub(_log(1) + _rec(A1, M_RMC1) + _rec(A2, M_RMC2)))
        e.patch(SAY, _stub(_log(2) + _list(SAY_N, 3, M_SAY)))
        e.patch(AI_PICK, _stub_ret(_log(3) + _rec(A1, PICK_ARG), PICK_RET))
        e.patch(HUMAN_PICK, _stub_ret(_log(4) + _rec(A1, DLG_ARG), DLG_RET))
        e.patch(STOCK_DIALOG, _stub_ret(_log(5) + _rec(A1, DLG_ARG), DLG_RET))
        e.patch(UI_SET, _stub(_log(6) + _list(UI_N, 3, M_UI)))
        e.patch(UI_END, _stub(_log(7) + _rec(A1, C_END)))
        # ``0x429040(idx+1)``：记实参，并把可控新价写进 stock[idx]+0x14
        e.patch(STOCK_APPLY, _stub(
            _log(8) + _list(APPLY_N, 1, M_APPLY)
            + b"\x8B\x44\x24" + bytes([A1])                 # mov eax,[esp+arg1]
            + b"\x48"                                        # dec eax
            + b"\x6B\xD0" + bytes([STOCK_STRIDE])            # imul edx, eax, 36
            + b"\xA1" + struct.pack("<I", NEW_PRICE)         # mov eax,[NEW_PRICE]
            + b"\x89\x82" + struct.pack("<I", STOCK_BASE + S_PRICE)))  # mov [edx+stock+0x14], eax
        e.patch(STRIP, _stub(_log(9) + _list(STRIP_N, 2, M_STRIP)))
        e.patch(SPRINTF, _stub(_log(10) + _list(SPRINTF_N, 4, M_SPRINTF)))
        e.patch(SHOW, _stub(_log(11) + _list(SHOW_N, 2, M_SHOW)))
        e.patch(ANIM, _stub(_log(12) + _list(ANIM_N, 6, M_ANIM)))
        e.patch(CAMERA, _stub(_log(13) + _list(CAM_N, 1, M_CAM)))
        e.patch(REFRESH, _stub(_log(14) + _count(C_REFRESH)))

    def _setup(self, cur=0, who=1, char=0, px=100, py=200, pick=0, dialog=0,
               players=None, stocks=None, holdings=None, num_players=4, new_price=0.0,
               types=None):
        players = players or [{} for _ in range(4)]
        stocks = stocks or {}
        holdings = holdings or {}
        types = types or {}

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            emu.write32(CUR, cur)
            emu.write32(NUM_PLAYERS, num_players)
            emu.write32(PICK_RET, pick)
            emu.write32(DLG_RET, dialog)
            emu.write(NEW_PRICE, struct.pack("<f", new_price))
            emu.write(PLAYER_BASE, b"\x00" * (4 * STRIDE))
            for i, spec in enumerate(players):
                pb = PLAYER_BASE + i * STRIDE
                emu.write16(pb + P_X, spec.get("x", px + i))
                emu.write16(pb + P_Y, spec.get("y", py + i))
                emu.write8(pb + P_CHAR, spec.get("char", char if i == cur else 0))
                emu.write8(pb + P_WHO, spec.get("who", who if i == cur else 2))
                # 关系值初始化为可识别的值，便于看「有没有被写」
                for b in range(4):
                    emu.write32(pb + P_HOSTILITY + 4 * b, spec.get("host", 0))
            emu.write(STOCK_BASE, b"\x00" * (STOCKS * STOCK_STRIDE))
            for i in range(STOCKS):
                sb = STOCK_BASE + i * STOCK_STRIDE
                emu.write32(sb + S_NAME, 0x466B00 + i * 8)
                emu.write8(sb + S_TREND, stocks.get(i, {}).get("trend", 0))
                emu.write(sb + S_PRICE, struct.pack("<f", stocks.get(i, {}).get("price", 100.0)))
                emu.write(sb + S_PREV, struct.pack("<f", stocks.get(i, {}).get("prev", 100.0)))
            emu.write(HOLDINGS, b"\x00" * (4 * 96))
            for (p, n), amount in holdings.items():
                emu.write32(HOLDINGS + p * 96 + n * 8, amount)
        return setup

    def run(self, va, **kw):
        r = self.emu.call(va, [], setup=self._setup(**kw))
        e = self.emu
        cur = kw.get("cur", 0)
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 24))],
            "rmc": (e.readu32(M_RMC1), e.readu32(M_RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4),
                      e.readu32(M_SAY + 12 * i + 8)) for i in range(e.readu32(SAY_N))],
            "pick_arg": e.readu32(PICK_ARG),
            "dlg_param": e.readu32(DLG_ARG),
            "ui": [[e.readu32(M_UI + 12 * i + 4 * k) for k in range(3)]
                   for i in range(e.readu32(UI_N))],
            "end": e.readu32(C_END),
            "apply": [e.readu32(M_APPLY + 4 * i) for i in range(e.readu32(APPLY_N))],
            # ⚠️ `_list` 是「一次调用写 count 个 dword」⇒ 必须按**记录**读
            "strip": [[e.readu32(M_STRIP + 8 * i + 4 * k) for k in range(2)]
                      for i in range(e.readu32(STRIP_N))],
            "sprintf": [[e.readu32(M_SPRINTF + 16 * i + 4 * k) for k in range(4)]
                        for i in range(e.readu32(SPRINTF_N))],
            "show": [[e.readu32(M_SHOW + 8 * i + 4 * k) for k in range(2)]
                     for i in range(e.readu32(SHOW_N))],
            "anims": [[e.readu32(M_ANIM + 24 * i + 4 * k) for k in range(6)]
                      for i in range(e.readu32(ANIM_N))],
            "cam": [e.readu32(M_CAM + 4 * i) for i in range(e.readu32(CAM_N))],
            "refresh": e.readu32(C_REFRESH),
            "trend": [e.read8(STOCK_BASE + i * STOCK_STRIDE + S_TREND) for i in range(STOCKS)],
            "price": [struct.unpack("<f", e.read(STOCK_BASE + i * STOCK_STRIDE + S_PRICE, 4))[0]
                      for i in range(STOCKS)],
            "allied": [e.read8(PLAYER_BASE + i * STRIDE + P_ALLIED) for i in range(4)],
            "days": [e.read8(PLAYER_BASE + i * STRIDE + P_ALLIED_DAYS) for i in range(4)],
            "host": [[e.read32(PLAYER_BASE + i * STRIDE + P_HOSTILITY + 4 * b)
                      for b in range(4)] for i in range(4)],
        }

    def cstr(self, va):
        return self.emu.img.cstr(va)


def main():
    print("差分测试 #45：紅卡 `0x444f25` / 黑卡 `0x44503f` / 同盟卡 `0x445710`\n")
    f = F()

    print("[A] 卡 24 紅卡 · AI 路径（写完走势字节就重算价）")
    s = f.run(RED, cur=0, who=2, pick=3, stocks={3: {"price": 100.0}}, new_price=110.0)
    case("★ 台词 = 表B 槽 23（`#0449跟著我買股票準沒錯！`）",
         (s["says"][0][0], s["says"][0][1], f.cstr(s["says"][0][2])),
         (0, 0, "#0449跟著我買股票\n準沒錯！"))
    case("★ AI 走 `0x41e6f2(0)`（实参 0）", s["pick_arg"], 0)
    case("★★ 走势字节 `stock[idx]+0x07 = 0x20`（高 4 位非 0 ⇒ 涨）", s["trend"][3], 0x20)
    case("   其它股票的走势字节没被动", [s["trend"][i] for i in (0, 2)], [0, 0])
    case("★★ 紧跟一次 `0x429040(idx+1)`（1-based）", s["apply"], [4])
    case("★ 扣卡：`remove_card(cur, 24)`", s["rmc"], (0, 24))
    case("★ 返回 1（不是股票号）", s["ret"], 1)
    case("★★ 提示串实参：`sprintf(缓冲, \"對%s使用%s！\", 名, \"紅卡\")`",
         (hex(s["sprintf"][0][1]), hex(s["sprintf"][0][3]),
          f.cstr(s["sprintf"][0][1]), f.cstr(s["sprintf"][0][3])),
         ("0x4653ae", "0x466b63", "對%s使用%s！", "紅卡"))
    case("★ 去空格拷贝的源 = 该股票名指针（`0x466b00 + idx*8`）",
         s["strip"][0][1], 0x466B00 + 3 * 8)
    case("★ 显示一次 `0x440cac(文本, 0x5dc)`（1500 = 时长）", s["show"][0][1], 0x5DC)
    case("   调用顺序：台词 → AI 选股 → 改价 → sprintf → 显示 → 扣卡",
         s["seq"][:3], [2, 3, 8])

    print("\n[B] 卡 24 紅卡 · 人类路径（改价在**股市屏内部**，卡本体不碰股票表）")
    s = f.run(RED, cur=1, who=1, dialog=5, stocks={4: {"price": 100.0}}, new_price=999.0)
    case("★★ 人类走 `0x42b58f(1)`（模式 1 = 涨）+ 前后两次界面设置",
         (s["dlg_param"], s["ui"]), (1, [[0xC, 0xF, 0xA], [0x29, 1, 0]]))
    case("★ 收尾 `0x41906a(1)` 一次", s["end"], 1)
    case("★★ 卡本体**不改**任何趋势字节（那是对话框内部干的）", max(s["trend"]), 0)
    case("★★ 卡本体**不调** `0x429040`（改价也在对话框里）", s["apply"], [])
    case("★ 扣卡 + 返回对话框给的值（5）", (s["rmc"], s["ret"]), ((1, 24), 5))
    s = f.run(RED, cur=1, who=1, dialog=0)
    case("★★ 对话框返回 0（取消）⇒ 返回 0、**不扣卡**",
         (s["ret"], s["rmc"]), (0, (0, 0)))

    print("\n[C] 卡 25 黑卡 · AI 路径 + 旧价快照")
    s = f.run(BLACK, cur=0, who=2, pick=2, stocks={2: {"price": 100.0}}, new_price=95.0)
    case("★ 台词 = 表B 槽 24（`#0450這支股票\n太貴了！！`）",
         (s["says"][0][0], f.cstr(s["says"][0][2])), (0, "#0450這支股票\n太貴了！！"))
    case("★★ 走势字节 = `2`（高 4 位为 0 ⇒ 跌）", s["trend"][2], 2)
    case("★ `0x429040(idx+1)` 一次、扣卡、返回股票号（1-based）",
         (s["apply"], s["rmc"], s["ret"]), ([3], (0, 25), 3))
    s = f.run(BLACK, cur=1, who=1, dialog=0)
    case("★★ 人类取消 ⇒ 返回 0、不扣卡（**台词已经说过**）",
         (s["ret"], s["rmc"], len(s["says"])), (0, (0, 0), 1))

    print("\n[D] ★★ 黑卡尾部的「double 压栈当 int 读」——真跑 `0x40df69` 看实际写入值")

    def f32(x):
        return struct.unpack("<f", struct.pack("<f", x))[0]

    def model_low(old_price, new_price, shares):
        """原版算式：`fild 持股 / fmul(价差 float32) / fdiv 200.0f / fstp qword` 的**低 32 位**

        ★ 两个价都先按 float32 取（状态里存的就是 float32），差值再 `fstp dword` 舍一次。
        """
        delta = f32(f32(old_price) - f32(new_price))
        v = shares * delta / 200.0
        return struct.unpack("<i", struct.pack("<d", v)[:4])[0]

    s = f.run(BLACK, cur=0, who=2, pick=0, stocks={0: {"price": 100.0}}, new_price=99.7,
              holdings={(1, 1): 100})
    case("★★ 持股 100、价差 0.3 ⇒ v = 0.15 的 double 低 32 位恰为 **0**（本例无副作用）",
         (s["host"][1][0], model_low(100.0, 99.7, 100)), (0, 0))
    s = f.run(BLACK, cur=0, who=2, pick=0, stocks={0: {"price": 100.0}}, new_price=99.7,
              holdings={(1, 1): 10})
    case("★★ 只把持股换成 10 ⇒ 低 32 位变成 **1717986918**（原版真的写进关系值！）",
         (s["host"][1][0], model_low(100.0, 99.7, 10)), (1717986918, 1717986918))
    s = f.run(BLACK, cur=0, who=2, pick=0, stocks={0: {"price": 100.0}}, new_price=99.7,
              holdings={(1, 1): 3})
    case("★★ 持股 3 ⇒ 低 32 位 = **−687194767**（负增量 ⇒ 关系值 0 时被提前返回，看不到）",
         (s["host"][1][0], model_low(100.0, 99.7, 3)), (0, -687194767))
    s = f.run(BLACK, cur=0, who=2, pick=0, stocks={0: {"price": 100.0}}, new_price=90.0,
              holdings={(1, 1): 200})
    case("★ 价差取「整数档」（10.0）时低 32 位恰为 0 —— 看上去『没有副作用』",
         (s["host"][1][0], model_low(100.0, 90.0, 200)), (0, 0))
    s = f.run(BLACK, cur=0, who=2, pick=0, stocks={0: {"price": 100.0}}, new_price=99.7,
              holdings={(1, 1): 0, (2, 1): 10})
    case("★★ 持股为 0 的玩家**整支跳过**（1 号不动、2 号照写）",
         (s["host"][1][0], s["host"][2][0]), (0, 1717986918))
    s = f.run(BLACK, cur=0, who=2, pick=0, num_players=3, stocks={0: {"price": 100.0}},
              new_price=99.7, holdings={(1, 1): 10, (2, 1): 10})
    case("★★ 循环上界是 `[0x499114]`（人数 = 3）⇒ 只处理 1/2 号，3 号不动",
         (s["host"][1][0], s["host"][2][0], s["host"][3][0]), (1717986918, 1717986918, 0))

    print("\n[E] 卡 29 同盟卡 · 拆旧链 + 建新盟")
    s = f.run(ALLIANCE, cur=0, who=1, dialog=(1 << 2))
    case("★★ 人类选框参数 = `0xe0c0410`（属玩家组、弹窗层禁选自己）",
         s["dlg_param"], 0xE0C0410)
    case("   掩码 → 目标下标 = ctz（0b100 ⇒ 2 号）", (s["allied"][2], s["days"][2]), (1, 7))
    case("★ 自己那两格：`+0x41 = 3`（2+1）、`+0x3d = 7`", (s["allied"][0], s["days"][0]), (3, 7))
    case("★ 使用者台词 = 表B 槽 28、被选者台词 = 表B 槽 88",
         [(x[0], f.cstr(x[2])) for x in s["says"]],
         [(0, "#0454好哥兒們！！"), (2, "#0476可別想占我\n便宜！")])
    case("★ `0x41d433(cur)` + 收尾 `0x41d546()` 各一次",
         (s["cam"], s["refresh"]), ([0], 1))
    case("★ 选人 → **扣卡** → 台词（序列 4 → 1 → 2）", s["seq"][:3], [4, 1, 2])
    case("★ 返回**掩码**（不是下标）", s["ret"], 1 << 2)

    print("\n[F] 卡 29 · 双向拆旧链（不留单向悬挂）")
    s = f.run(ALLIANCE, cur=0, who=1, dialog=(1 << 1),
              players=[{"allied": 3}, {"allied": 4}, {}, {}])
    case("★★ 自己原有盟友（3 号）⇒ 双向清：自己的两格 + 3 号的两格",
         (s["allied"][0], s["days"][0], s["allied"][2], s["days"][2]), (2, 7, 0, 0))
    s = f.run(ALLIANCE, cur=0, who=1, dialog=(1 << 1),
              players=[{}, {"allied": 4}, {}, {}])
    case("★★ 目标原有盟友（3 号）⇒ 目标与 3 号都被清，再建新盟",
         (s["allied"][2], s["days"][2], s["allied"][1], s["days"][1]), (0, 0, 1, 7))
    s = f.run(ALLIANCE, cur=0, who=1, dialog=(1 << 1),
              players=[{"allied": 2}, {"allied": 1}, {}, {}])
    case("★★ 双方互为旧盟 ⇒ 两段拆链都跑，最终仍是新盟（0↔1）",
         (s["allied"][0], s["allied"][1], s["days"][0], s["days"][1]), (2, 1, 7, 7))
    s = f.run(ALLIANCE, cur=0, who=1, dialog=0)
    case("★★ 掩码 0 ⇒ 返回 0、**不扣卡**、一句话都不说",
         (s["ret"], s["rmc"], s["says"]), (0, (0, 0), []))

    print("\n[G] 卡 29 · 动画只给 AI（与卡 16/22/23 同一规矩）")
    s = f.run(ALLIANCE, cur=0, who=1, dialog=(1 << 1))
    case("★ 人类施卡不播 `0x40e669`", s["anims"], [])
    s = f.run(ALLIANCE, cur=0, who=2, pick=(1 << 1), dialog=(1 << 1), players=[{"x": 100, "y": 200},
                                                              {"x": 300, "y": 400}, {}, {}])
    case("★★ AI 施卡播 `0x40e669(0, cur.xy, tgt.xy, 0x64)`",
         s["anims"], [[0, 100, 200, 300, 400, 0x64]])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
