#!/usr/bin/env python3
"""
通道 2 差分测试 #39 · **均富卡 `0x4420d8` / 均貧卡 `0x4421b4`**

两张卡都是 `card_functions[]` 的成员（卡 1 / 卡 2），PRD 里记为「✅ 完整规格」，
本轮第一次**整支驱动**验证 —— 顺带订正 `cards.md` 里一处**自相矛盾的措辞**（见下）。

```asm
; @source 0x4420d8 均富卡（76 条指令）
004420db  push 1 / push [0x49910c] / call 0x441343   ; ① **先弃掉自己手上这张卡**
004420f7  dl = player.character(0x13) → eax = 360*character
0044210e  say(cur, 3, [0x48123a + 360c])             ; ② 台词 '#0426有錢大家花！'
00442126  edi = [0x499114]                           ; 玩家人数
00442133  for (i < edi) if (byte [p+0x15] != 0) { sum += cash(p+0x1c); count++ }
0044214d  idiv ecx                                   ; ③ avg = sum / count（有符号，向零截断）
00442167  for (i < edi) if (byte [p+0x15] != 0) {
            if (avg < cash) {                       ; ★ 只对**现金被拉低**的人
                delta = (cash - avg) / 100           ; ★★ 正数（0x442171 sub edx,esi）
                update_hostility(i, cur, delta)      ;    0x40df69(i, cur, delta)
            }
            cash = avg                               ; ④ 全场拉平
          }
004421ab  return 1

; @source 0x4421b4 均貧卡（376 字节）
004421bf  if (byte [p+0x15] == 1) enc = 0x446ae8(0xe0c0410)   ; 人类：鼠标选人
          else                    enc = 0x41e6f2(0)            ; AI：算一个
004421e2  if (enc == 0) return 0                              ; ① 取消 ⇒ **卡不消耗**
004421f1  remove_card(cur, 2)                                 ; ② 弃卡
0044221b  say(cur, 3, [0x48123e + 360c])                      ;    '#0427朋友有通財之義！'
0044222d  tgt = ctz(enc)                                      ; ③ 掩码 → 下标（0x40d293）
00442250  avg = trunc((cash[cur] + cash[tgt]) / 2)            ; ④ 两人的均值
00442263  if (avg < cash[tgt]) update_hostility(tgt, cur, (cash[tgt]-avg)/100)   ; ★ 正数
0044228f  cash[cur] = cash[tgt] = avg
0044229e  if (byte [cur+0x15] != 1) 0x40e669(0, cur.x, cur.y, tgt.x, tgt.y, 0x64) ; 仅 AI 播动画
004422e5  refresh(cur) ; say(tgt, 1, [0x48132e + 360*char(tgt)]) ; refresh_map()
00443069  return enc                                          ; ★ 返回**掩码**，不是下标
```

## ★ 订正：`cards.md` 均富卡那段的「delta 为负」是错的

`cards.md` §卡 1 的**汇编摘录是对的**（`0x442171 sub edx, esi` ⇒ `cash − avg > 0`），
但**正文三处**写成「为负值 → 敌意减少」：`§精确效果 4.`、`§公式汇总`、
`§边界情况`（「目标现金 < avg ⇒ delta 为负」）。本测试用**非对称现金**
（1000 / 500 / 300）钉死机器行为：

```
平均 600 ⇒ 只有**现金 1000 的那位**被记录敌意，delta = (1000−600)/100 = **+4**（正）
         现金 500 / 300 的两位**没有任何** update_hostility 调用
```
⇒ 语义是「**被拉低的人对施卡者增加敌意**」，与均貧卡同一口径（那一节 PRD 写对了）。
复刻侧 `cards/average-cash.ts` 一直是正数（本来就一致）。

## 打桩（全部 `pushad/popad` 包裹，保证不破坏调用方的 ebx/esi/edi）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x441343` | `remove_card(player, cardId)` | 记两个实参 + 序列 + `ret` |
| `0x44ef41` | `player_say(player, 槽, 文本)` | 记**每一次**（列表）+ `ret` |
| `0x40df69` | `update_hostility(a, b, delta)` | 记**每一次**（列表）+ `ret` |
| `0x41d433` | 刷新玩家条 | 计数 + `ret` |
| `0x41d546` | `refresh_map()` | 计数 + `ret` |
| `0x40e669` | 双方现金同步动画 | 记六实参（列表）+ `ret` |
| `0x446ae8` | 人类选人框 | 返回**可控掩码** + `ret` |
| `0x41e6f2` | AI 选人 | 返回**可控掩码** + `ret` |

`0x40d293`（`ctz`，14 条指令纯函数）**不打桩**，跑真的。

**诚实边界**：选人框/AI 的**合法性筛选**（`0xe0c0410` 的位域、不能选自己）在
`0x446ae8`/`0x41e6f2` **内部**，本测试打桩跳过；那一层见 `cards.md` §1.6.2 与
复刻侧 `cards/target.ts` 的既有测试。本测试只管**卡片效果函数本身**。

跑法：cd rich4-spec && .venv/bin/python tests/test_average_cards.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

AVG_CASH, AVG_POOR = 0x4420D8, 0x4421B4

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_X, P_Y, P_CHAR, P_CASH, P_WHO = 0x08, 0x0A, 0x13, 0x1C, 0x15
CUR, NUM_PLAYERS = 0x49910C, 0x499114

REMOVE_CARD, SAY, HOSTILITY = 0x441343, 0x44EF41, 0x40DF69
REFRESH, REFRESH_MAP, ANIM = 0x41D433, 0x41D546, 0x40E669
SELECT_UI, SELECT_AI = 0x446AE8, 0x41E6F2
CTZ = 0x40D293

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE80          # 调用序列（数组）+ 计数器
#   ⚠️ 计数器**不能**挨着数组放：`mov [ebx*4+SEQ], eax` 在 ebx=1 时会写到 SEQ+4 ——
#   若计数器正好在 SEQ+4，第二笔就会把自己的序号当计数写进去（本轮踩过）。
M_RMC1, M_RMC2 = S + 0x910, S + 0x914
SAY_N, M_SAY = S + 0x920, S + 0x940        # 每次 say：3 个字（a1, a2, a3!=0）
HOS_N, M_HOS = S + 0xA00, S + 0xA40        # 每次敌意：3 个字（a, b, delta）
ANIM_N, M_ANIM = S + 0xB00, S + 0xB40      # 每次动画：6 个字
C_REFRESH, C_REFRESH_MAP = S + 0xC00, S + 0xC04
M_SEL_ARG, M_SEL_ARG_AI = S + 0xC10, S + 0xC14
MASK_UI, MASK_AI = S + 0xC20, S + 0xC24
ZERO = S + 0xC30

# pushad 之后实参的栈偏移：arg1 = [esp + 4 + 32]
A1, A2 = 0x24, 0x28
ALL_SLOTS = [SEQ, SEQ_N, M_RMC1, M_RMC2, SAY_N, HOS_N, ANIM_N,
             C_REFRESH, C_REFRESH_MAP, M_SEL_ARG, M_SEL_ARG_AI, ZERO]
ALL_SLOTS += [M_SAY + i for i in range(0, 24)]
ALL_SLOTS += [M_HOS + i for i in range(0, 24)]
ALL_SLOTS += [M_ANIM + i for i in range(0, 48)]
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def _log(code):
    """往调用序列里记一笔（clobber 任意寄存器 —— 外层有 pushad 兜着）"""
    return (b"\xB8" + struct.pack("<I", code)              # mov eax, code
            + b"\x8B\x1D" + struct.pack("<I", SEQ_N)       # mov ebx, [SEQ_N]
            + b"\x89\x04\x9D" + struct.pack("<I", SEQ)     # mov [ebx*4+SEQ], eax
            + b"\xFF\x05" + struct.pack("<I", SEQ_N))      # inc [SEQ_N]


def _rec(off, slot):
    """`mov eax,[esp+off]` / `mov [slot],eax`（off 用 pushad 之后的偏移）"""
    return b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)


def _list_stub(count_n, count, entry_size, base):
    """往「列表」追加 `count` 个字：ebx = n*entry_size + base，逐个存 arg1..argN"""
    code = (b"\x8B\x1D" + struct.pack("<I", count_n)       # mov ebx,[n]
            + b"\x6B\xDB" + bytes([entry_size])            # imul ebx, ebx, size
            + b"\x81\xC3" + struct.pack("<I", base))       # add ebx, base
    for k in range(count):
        code += _rec(A1 + 4 * k, ZERO)                     # mov eax,[esp+..]
        code += b"\x89\x43" + bytes([k * 4])               # mov [ebx+k*4], eax
    code += b"\xFF\x05" + struct.pack("<I", count_n)
    return code


def _stub(body):
    """pushad / body / popad / ret"""
    return b"\x60" + body + b"\x61\xC3"


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(REMOVE_CARD, _stub(_log(1) + _rec(A1, M_RMC1) + _rec(A2, M_RMC2)))
        self.emu.patch(SAY, _stub(_log(2) + _list_stub(SAY_N, 3, 12, M_SAY)))
        self.emu.patch(HOSTILITY, _stub(_log(4) + _list_stub(HOS_N, 3, 12, M_HOS)))
        self.emu.patch(ANIM, _stub(_log(5) + _list_stub(ANIM_N, 6, 24, M_ANIM)))
        self.emu.patch(REFRESH,
                       _stub(_log(3) + b"\xFF\x05" + struct.pack("<I", C_REFRESH)))
        self.emu.patch(REFRESH_MAP,
                       _stub(_log(6) + b"\xFF\x05" + struct.pack("<I", C_REFRESH_MAP)))
        # 选择器：记实参 →（popad 之后）把数据桩里的掩码返回
        for va, argslot, mask in ((SELECT_UI, M_SEL_ARG, MASK_UI),
                                  (SELECT_AI, M_SEL_ARG_AI, MASK_AI)):
            self.emu.patch(va, b"\x60" + _log(7) + _rec(A1, argslot)
                           + b"\x61" + b"\xA1" + struct.pack("<I", mask) + b"\xC3")

    def _setup(self, emu, *, cur, num, players, mask_ui=0, mask_ai=0):
        for s in ALL_SLOTS:
            emu.write32(s, 0)
        emu.write32(MASK_UI, mask_ui)
        emu.write32(MASK_AI, mask_ai)
        emu.write32(CUR, cur)
        emu.write32(NUM_PLAYERS, num)
        for i in range(4):
            pb = PLAYER_BASE + i * STRIDE
            spec = players[i] if i < len(players) else {}
            emu.write32(pb + P_CASH, spec.get("cash", 0))
            emu.write8(pb + P_WHO, spec.get("who", 0))
            emu.write8(pb + P_CHAR, spec.get("char", 0))
            emu.write16(pb + P_X, spec.get("x", 100 + i))
            emu.write16(pb + P_Y, spec.get("y", 200 + i))

    def _read(self, emu):
        n_seq = emu.readu32(SEQ_N)
        n_say = emu.readu32(SAY_N)
        n_hos = emu.readu32(HOS_N)
        n_anim = emu.readu32(ANIM_N)
        return {
            "cash": [emu.read32(PLAYER_BASE + i * STRIDE + P_CASH) for i in range(4)],
            "seq": [emu.readu32(SEQ + 4 * i) for i in range(min(n_seq, 24))],
            "rmc": (emu.readu32(M_RMC1), emu.readu32(M_RMC2)),
            "says": [(emu.readu32(M_SAY + 12 * i), emu.readu32(M_SAY + 12 * i + 4),
                      emu.readu32(M_SAY + 12 * i + 8) != 0) for i in range(n_say)],
            # delta 是**有符号**的（溢出场景会变负），故第三个字段用 read32
            "hos": [(emu.read32(M_HOS + 12 * i), emu.read32(M_HOS + 12 * i + 4),
                     emu.read32(M_HOS + 12 * i + 8)) for i in range(n_hos)],
            "anims": [[emu.readu32(M_ANIM + 24 * i + 4 * k) for k in range(6)]
                      for i in range(n_anim)],
            "sel_arg": (emu.readu32(M_SEL_ARG), emu.readu32(M_SEL_ARG_AI)),
            "refresh": emu.readu32(C_REFRESH),
            "refresh_map": emu.readu32(C_REFRESH_MAP),
        }

    def call(self, va, *, cur=0, num=4, players, mask_ui=0, mask_ai=0):
        r = self.emu.call(va, [], setup=lambda e: self._setup(
            e, cur=cur, num=num, players=players, mask_ui=mask_ui, mask_ai=mask_ai))
        out = self._read(self.emu)
        out["ret"] = r["eax"]
        return out


def main():
    print("差分测试 #39：均富卡 `0x4420d8` / 均貧卡 `0x4421b4`\n")
    f = F()
    case("★ `ctz` 探针（那个不打桩的辅助函数）", f.emu.call(CTZ, [0b1010])["eax"], 1)

    print("[A] 均富卡：全场拉平 + 敌意只加给**被拉低**的人（正数）")
    s = f.call(AVG_CASH, cur=0, players=[{"cash": 1000, "who": 1, "char": 0},
                                         {"cash": 500, "who": 2},
                                         {"cash": 300, "who": 2},
                                         {"cash": 9999, "who": 0}])
    case("★★ 参战三人均值 (1000+500+300)/3 = 600，全部写成 600；出局者（who=0）不动",
         s["cash"], [600, 600, 600, 9999])
    case("★★ 敌意只记在**现金 1000** 那位头上，delta = (1000−600)/100 = **+4**（正数）",
         s["hos"], [(0, 0, 4)])
    case("★ 现金 500 / 300 的两位**没有**敌意调用（PRD 那张「< avg ⇒ 负 delta」的表是错的）",
         len(s["hos"]), 1)
    case("★ 返回 1（永不失败）", s["ret"], 1)
    case("★ 调用顺序：弃卡 → 台词 → 敌意 → 刷新（弃卡在**最前**、刷新在**最后**）",
         s["seq"], [1, 2, 4, 3])
    case("★ 弃的是**卡 1**（`remove_card(cur,1)`）", s["rmc"], (0, 1))
    case("   台词只有一句：`player_say(cur, 3, 非空文本)`（表 `0x48123a+360c` 的 k=0）",
         s["says"], [(0, 3, True)])
    case("   刷新玩家条一次", s["refresh"], 1)

    print("\n[B] 均富卡：取整与边界")
    s = f.call(AVG_CASH, cur=0, players=[{"cash": 100, "who": 1}, {"cash": 101, "who": 1}])
    case("★ (100+101)/2 = 100（向零截断）⇒ 两人都变 100", s["cash"][:2], [100, 100])
    case("★ 被拉低的那位（101→100）**照样调用**敌意函数，delta = 1/100 = 0",
         s["hos"], [(1, 0, 0)])
    s = f.call(AVG_CASH, cur=2, players=[{"cash": -7, "who": 1}, {"cash": 0, "who": 1},
                                         {"cash": 230, "who": 1}, {"cash": 0, "who": 0}])
    case("★★ 负数也向零截断：(−7+0+230)/3 = 74（trunc(74.33) 不是四舍五入）",
         s["cash"][:3], [74, 74, 74])
    case("★★ 唯一**被拉低**的是 2 号（230→74）：delta = 156/100 = 1；"
         "0 号（−7→74）与 1 号（0→74）都是被抬高 ⇒ 无调用",
         s["hos"], [(2, 2, 1)])
    case("   弃卡与台词都用 2 号", (s["rmc"][0], s["says"][0][0]), (2, 2))
    s = f.call(AVG_CASH, cur=0, num=2, players=[{"cash": 10, "who": 1}, {"cash": 20, "who": 1},
                                                {"cash": 10000, "who": 5},
                                                {"cash": 0, "who": 5}])
    case("★★ 只算前 `[0x499114]=2` 名玩家 —— 2/3 号即便 `who_plays != 0` 也不参与",
         (s["cash"][:2], s["cash"][2]), ([15, 15], 10000))
    s = f.call(AVG_CASH, cur=0, players=[{"cash": 0x7FFFFFFF, "who": 1},
                                         {"cash": 0x7FFFFFFF, "who": 1},
                                         {"cash": 1, "who": 1}, {"cash": 0, "who": 0}])
    case("★★ 求和**按 32 位回绕**：0x7FFFFFFF×2+1 = −1 ⇒ `idiv 3` = 0 ⇒ 三家都变 0",
         s["cash"], [0, 0, 0, 0])
    case("   敌意：前两家 delta = 2147483647/100 = 21474836（正）、第三家 1/100 = 0",
         s["hos"], [(0, 0, 21474836), (1, 0, 21474836), (2, 0, 0)])
    try:
        f.call(AVG_CASH, cur=0, players=[{"cash": 0, "who": 0}] * 4)
        crash = False
    except RuntimeError:
        crash = True
    case("★ 无人在局 ⇒ 原版 `idiv ecx`（ecx=0）**除零异常**（PRD 已记为无防护）", crash, True)

    print("\n[C] 均貧卡：两人拉平 + 目标台词 + 返回掩码")
    s = f.call(AVG_POOR, cur=0, players=[{"cash": 100, "who": 1, "char": 3},
                                         {"cash": 500, "who": 2, "char": 1}],
               mask_ui=0b010)
    case("★★ 两人均值 (100+500)/2 = 300 ⇒ 双方都变 300", s["cash"][:2], [300, 300])
    case("★★ 敌意只记在**目标**头上（500→300）：delta = 200/100 = **+2**", s["hos"], [(1, 0, 2)])
    case("★ 弃的是**卡 2**", s["rmc"], (0, 2))
    case("★★ 两句台词：施卡者 `(0, 3, 表[0x48123e])`、目标 `(1, 1, 表[0x48132e+360*char])`",
         s["says"], [(0, 3, True), (1, 1, True)])
    case("★★ 返回值是**掩码**（2）不是下标（1）", s["ret"], 2)
    case("   人类施卡不播「现金同步」动画", len(s["anims"]), 0)
    case("   刷新玩家条一次 + `refresh_map()` 一次", (s["refresh"], s["refresh_map"]), (1, 1))

    print("\n[D] 均貧卡：AI 施卡 / 多位置掩码 / 取消 / 取整")
    s = f.call(AVG_POOR, cur=0, players=[{"cash": 1000, "who": 2},
                                         {"cash": 0, "who": 2},
                                         {"cash": 400, "who": 2}], mask_ai=0b100)
    case("★ AI 施卡（`who_plays != 1`）走 `0x41e6f2(0)`", s["sel_arg"][1], 0)
    case("★ 掩码 `0b100` ⇒ 目标是 2 号：均值 (1000+400)/2 = 700",
         (s["cash"][0], s["cash"][2]), (700, 700))
    case("★ 目标 400→700（被**抬高**）⇒ 没有敌意调用", s["hos"], [])
    case("★★ AI 施卡**要播**动画：`0x40e669(0, cur.x, cur.y, tgt.x, tgt.y, 0x64)`",
         s["anims"], [[0, 100, 200, 102, 202, 0x64]])
    case("   与目标无关的那位（1 号）不受影响", s["cash"][1], 0)
    s = f.call(AVG_POOR, cur=0, players=[{"cash": 100, "who": 1}], mask_ui=0b1010)
    case("★ 掩码含多位 ⇒ `ctz` 只取**最低**位：0b1010 的 ctz 是 1（不是 3）"
         "⇒ 拉平的是 0 号与 **1 号**（(100+0)/2 = 50），3 号一分不动",
         (s["cash"][0], s["cash"][1], s["cash"][3], s["ret"]), (50, 50, 0, 0b1010))
    s = f.call(AVG_POOR, cur=0, players=[{"cash": 100, "who": 1}], mask_ui=0)
    case("★★ 取消（掩码 0）⇒ 返回 0、**卡不消耗**、没有台词/刷新/动画",
         (s["ret"], s["rmc"], s["cash"][0], s["says"], s["refresh"], s["refresh_map"],
          len(s["anims"])), (0, (0, 0), 100, [], 0, 0, 0))
    s = f.call(AVG_POOR, cur=0, players=[{"cash": 101, "who": 1}, {"cash": 100, "who": 1}],
               mask_ui=0b010)
    case("★ 奇数和对半：(101+100)/2 = 100（向零截断）⇒ 双方 100", s["cash"][:2], [100, 100])
    case("   目标 100→100 未被拉低 ⇒ 无敌意", s["hos"], [])
    s = f.call(AVG_POOR, cur=0, players=[{"cash": -7, "who": 1}, {"cash": 0, "who": 1}],
               mask_ui=0b010)
    case("★ 负数对半：(−7+0)/2 = −3（`sar` 前先 `sub eax,edx` 修正 ⇒ 向零截断）",
         (s["cash"][0], s["cash"][1]), (-3, -3))
    case("   目标 0 → −3 是**被拉低**：delta = (0−(−3))/100 = 0，仍调用", s["hos"], [(1, 0, 0)])

    s = f.call(AVG_POOR, cur=0, players=[{"cash": 0x7FFFFFFF, "who": 1},
                                         {"cash": 0x7FFFFFFF, "who": 1}], mask_ui=0b010)
    case("★★ 两人求和也回绕：0x7FFFFFFF+0x7FFFFFFF = −2 ⇒ `sar` 修正后 /2 = **−1**",
         (s["cash"][0], s["cash"][1]), (-1, -1))
    case("★★ 但 `cmp` 是**有符号**比较：−1 < 0x7FFFFFFF ⇒ 仍判「被拉低」；"
         "差值 0x80000000 回绕 ⇒ delta = **−21474836**（本场景下负号）",
         (s["hos"], s["ret"]), ([(1, 0, -21474836)], 2))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
