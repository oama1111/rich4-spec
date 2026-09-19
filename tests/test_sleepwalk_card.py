#!/usr/bin/env python3
"""
通道 2 差分测试 #43 · **夢遊卡（卡 16）** `0x4441dc`（739 字节）

它是「防御卡编排」最复杂的一张：选人 → 扣卡 → 台词 → 动画 → 仇恨 →
**免罪(21) → 嫁禍(19)**（命中即止）→ 施加 → 若「最终目标 == 原始目标」再查 **復仇(18)**。
PRD（`cards.md` §卡 16）有逐段摘录与一张边界表，本轮第一次**整支驱动**验证。

```asm
; @source 0x4441e0（片段）
004441e7  if (player[cur].who_plays == 1) esi = 0x446ae8(0xe0c0710)   ; 人类：选人框
          else                            esi = 0x41e6f2(0)          ; AI
0044420a  if (esi == 0) return 0                                      ; ★ 取消 ⇒ 卡不消耗
00444219  remove_card(cur, 16)
00444243  say(cur, 3, 表[0x481276])                                   ; k=15「睡吧睡吧∼」
0044425b  ebp = ebx = 0x40d293(esi)                                   ; ctz(掩码) = 目标
00444274  if (cur 不是人类) 0x40e669(0, cur.xy, 目标.xy, 100)          ; 只有 AI 播
004442b2  if (目标 >= 4) goto 伪玩家支
004442be  if (player[目标+0x36] != 0) goto 伪玩家支                     ; 已在睡 ⇒ 不施加
004442ea  update_hostility(目标, cur, 150 × price_index)              ; ★ 先记仇恨
004442f5  if (has_card(目标, 21)) { 0x444bb2(目标); goto 收尾 }        ; 免罪：命中即止
00444313  if (has_card(目标, 19)) { 新目标 = 0x44476a(目标,0,0); 若 != -1 ⇒ 目标 = 新目标 }
00444367  al = (目标 != cur) + 4 → byte [目标+0x37] = al（5 / 4）      ; 梦游天数
00444372  byte [目标+0x42] += 5
00444379  byte [目标+0x66] = traffic ; byte [目标+0x67] = ndices      ; 备份
00444399  traffic==1 → 道具 5 回池；traffic==2 → 道具 6 回池；然后 traffic=0, ndices=1
004443e7  0x40b93b(目标)                                             ; 启动梦游流程
004443ef  if (最终目标 == 原始目标 && has_card(原始目标, 18)) {
             0x444691(原始目标)
             byte [**cur** + 0x496b9f] = 5                            ; ★ 施卡者自己梦游 5 天
             （同样备份/回收 cur 的座驾）
          }
0044449b  伪玩家支：if (目标 >= 4 && [目标*16 + 0x498df4] == 0) [..+0x498df5] = 5
004444b3  0x41d546() ; return **掩码**（不是下标）
```

## 打桩（13 个）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x446ae8` / `0x41e6f2` | 人类选人框 / AI 选人 | 返回**可控掩码** |
| `0x441343` | `remove_card(player, card)` | 记实参 + 序列 |
| `0x44ef41` | `player_say` | 记**每一次** |
| `0x40e669` | 双方坐标动画 | 记六个实参 |
| `0x40df69` | `update_hostility` | 记**每一次** |
| `0x4413ad` | `has_card(player, card)` | **数据表桩**：查 scratch 里的 8×32 字节矩阵 |
| `0x444bb2` | 免罪卡生效处理 | 记实参 + 序列 |
| `0x44476a` | 嫁禍卡生效处理 | 记三个实参 + 返回**可控新目标**（−1 = 放弃）|
| `0x444691` | 復仇卡生效处理 | 记实参 + 序列 |
| `0x40b93b` | 启动梦游流程 | 记实参 + 序列 |
| `0x41d546` | `refresh_map()` | 计数 + 序列 |

**诚实边界**：`0x444bb2`（免罪）/ `0x44476a`（嫁禍）/ `0x444691`（復仇）三个**生效处理**
被本测试打桩 —— 本测试钉的是**编排**（顺序、命中即止、目标改写、反弹给谁），
那三个函数各自的效果不在本轮范围。`0x40b93b`（梦游流程，476 条指令）同理打桩。

跑法：cd rich4-spec && .venv/bin/python tests/test_sleepwalk_card.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

SLEEPWALK = 0x4441DC
SEL_UI, SEL_AI = 0x446AE8, 0x41E6F2
REMOVE_CARD, SAY, ANIM, HOSTILITY = 0x441343, 0x44EF41, 0x40E669, 0x40DF69
HAS_CARD, MIANZUI, JIAHUO, FUCHOU = 0x4413AD, 0x444BB2, 0x44476A, 0x444691
DREAMFLOW, REFRESH_MAP = 0x40B93B, 0x41D546

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_X, P_Y, P_TRAFFIC, P_NDICES, P_CHAR, P_WHO = 0x08, 0x0A, 0x11, 0x12, 0x13, 0x15
P_SLEEP, P_SLEEPWALK, P_MISFORTUNE = 0x36, 0x37, 0x42
P_TRAF_BAK, P_NDICE_BAK = 0x66, 0x67
TOOL_AMOUNT = 0x49915C          # +15*player + (道具-1)
NPC_F0C, NPC_F0D = 0x498DF4, 0x498DF5
CUR, PRICE = 0x49910C, 0x4990E8

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE90
M_RMC1, M_RMC2 = S + 0x900, S + 0x904
SAY_N, M_SAY = S + 0x920, S + 0x940
HOS_N, M_HOS = S + 0xA00, S + 0xA40
ANIM_N, M_ANIM = S + 0xB00, S + 0xB40
C_REFRESH = S + 0xC00
C_DREAM = S + 0xC04
M_MIAN, M_JIA, M_FU = S + 0xC10, S + 0xC20, S + 0xC30
CARD_TABLE = S + 0x1000          # 8 玩家 × 32 卡号
MASK_UI, MASK_AI, JIA_RET = S + 0xD00, S + 0xD04, S + 0xD08
ZERO = S + 0xD20
A1, A2, A3 = 0x24, 0x28, 0x2C
ALL_SLOTS = [SEQ, SEQ_N, M_RMC1, M_RMC2, SAY_N, HOS_N, ANIM_N, C_REFRESH, C_DREAM,
             M_MIAN, M_JIA, M_FU, MASK_UI, MASK_AI, JIA_RET, ZERO]
ALL_SLOTS += list(range(M_SAY, M_SAY + 24, 4)) + list(range(M_HOS, M_HOS + 24, 4))
ALL_SLOTS += list(range(M_ANIM, M_ANIM + 48, 4))
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


def _list(n_slot, count, base):
    code = (b"\x8B\x1D" + struct.pack("<I", n_slot)
            + b"\x6B\xDB" + bytes([4 * count])
            + b"\x81\xC3" + struct.pack("<I", base))
    for k in range(count):
        code += _rec(A1 + 4 * k, ZERO) + b"\x89\x43" + bytes([k * 4])
    return code + b"\xFF\x05" + struct.pack("<I", n_slot)


def _stub(body):
    return b"\x60" + body + b"\x61\xC3"


class F:
    def __init__(self):
        self.emu = Emu()
        for va, mask in ((SEL_UI, MASK_UI), (SEL_AI, MASK_AI)):
            # 记实参 + 返回数据桩里的掩码
            self.emu.patch(va, b"\x60" + _log(9) + _rec(A1, M_MIAN + 8)
                           + b"\x61" + b"\xA1" + struct.pack("<I", mask) + b"\xC3")
        self.emu.patch(REMOVE_CARD, _stub(_log(1) + _rec(A1, M_RMC1) + _rec(A2, M_RMC2)))
        self.emu.patch(SAY, _stub(_log(2) + _list(SAY_N, 3, M_SAY)))
        self.emu.patch(HOSTILITY, _stub(_log(5) + _list(HOS_N, 3, M_HOS)))
        self.emu.patch(ANIM, _stub(_log(4) + _list(ANIM_N, 6, M_ANIM)))
        self.emu.patch(MIANZUI, _stub(_log(6) + _rec(A1, M_MIAN)))
        # 嫁禍：记三实参 + 返回 JIA_RET（-1 = 放弃）
        self.emu.patch(JIAHUO, b"\x60" + _log(7) + _rec(A1, M_JIA) + _rec(A2, M_JIA + 4)
                       + _rec(A3, M_JIA + 8) + b"\x61"
                       + b"\xA1" + struct.pack("<I", JIA_RET) + b"\xC3")
        self.emu.patch(FUCHOU, _stub(_log(8) + _rec(A1, M_FU)))
        self.emu.patch(DREAMFLOW, _stub(_log(3) + b"\xFF\x05" + struct.pack("<I", C_DREAM)
                                        + _rec(A1, M_FU + 4)))
        self.emu.patch(REFRESH_MAP, _stub(_log(10) + b"\xFF\x05"
                                          + struct.pack("<I", C_REFRESH)))
        # has_card(player, card)：查 8×32 字节的矩阵
        # ⚠️ 返回值必须在 **popad 之后**写：popad 会把 eax 还原成 pushad 时的值
        self.emu.patch(HAS_CARD, b"\x60"
                       + _rec(A1, ZERO) + _rec(A2, ZERO + 4)
                       + b"\x8B\x1D" + struct.pack("<I", ZERO)          # ebx = player
                       + b"\x6B\xDB\x20"                                # imul ebx, ebx, 32
                       + b"\x81\xC3" + struct.pack("<I", CARD_TABLE)    # add ebx, table
                       + b"\x8B\x0D" + struct.pack("<I", ZERO + 4)      # ecx = card
                       + b"\x0F\xB6\x04\x0B"                            # movzx eax, byte [ebx+ecx]
                       + b"\xA3" + struct.pack("<I", ZERO + 8)           # mov [ZERO+8], eax
                       + b"\x61"                                        # popad
                       + b"\xA1" + struct.pack("<I", ZERO + 8) + b"\xC3")

    def run(self, *, cur=0, price=1, mask_ui=0, mask_ai=0, jia_ret=-1, players=None,
            cards=None, npcs=None):
        players = players if players is not None else [{} for _ in range(4)]
        cards = cards or {}
        npcs = npcs or {}

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            emu.write(CARD_TABLE, b"\x00" * (8 * 32))
            for (p, c), v in cards.items():
                emu.write8(CARD_TABLE + p * 32 + c, v)
            emu.write32(CUR, cur)
            emu.write32(PRICE, price)
            emu.write32(MASK_UI, mask_ui)
            emu.write32(MASK_AI, mask_ai)
            emu.write32(JIA_RET, jia_ret if jia_ret >= 0 else jia_ret + (1 << 32) - (1 << 32))
            if jia_ret < 0:
                emu.write(JIA_RET, struct.pack('<i', jia_ret))
            emu.write(PLAYER_BASE, b"\x00" * (4 * STRIDE))
            emu.write(TOOL_AMOUNT, b"\x00" * 60)
            for i, spec in enumerate(players):
                pb = PLAYER_BASE + i * STRIDE
                emu.write16(pb + P_X, spec.get("x", 100 + i))
                emu.write16(pb + P_Y, spec.get("y", 200 + i))
                emu.write8(pb + P_TRAFFIC, spec.get("traffic", 0))
                emu.write8(pb + P_NDICES, spec.get("ndices", 3))
                emu.write8(pb + P_CHAR, spec.get("char", 0))
                emu.write8(pb + P_WHO, spec.get("who", 1))
                emu.write8(pb + P_SLEEP, spec.get("sleep", 0))
                emu.write8(pb + P_SLEEPWALK, spec.get("sleepwalk", 0))
                emu.write8(pb + P_MISFORTUNE, spec.get("misfortune", 0))
            for i, st in enumerate(npcs):
                emu.write8(NPC_F0C + (i + 4) * 16, 9)   # 默认「已被占」
                emu.write8(NPC_F0D + (i + 4) * 16, 9)
            for i, st in npcs.items():
                emu.write8(NPC_F0C + i * 16, st)

        r = self.emu.call(SLEEPWALK, [], setup=setup)
        e = self.emu
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 20))],
            "rmc": (e.readu32(M_RMC1), e.readu32(M_RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4))
                     for i in range(e.readu32(SAY_N))],
            "hos": [(e.read32(M_HOS + 12 * i), e.read32(M_HOS + 12 * i + 4),
                     e.read32(M_HOS + 12 * i + 8)) for i in range(e.readu32(HOS_N))],
            "anims": [[e.readu32(M_ANIM + 24 * i + 4 * k) for k in range(6)]
                      for i in range(e.readu32(ANIM_N))],
            "tool5": [e.read8(TOOL_AMOUNT + 15 * i + 4) for i in range(4)],
            "tool6": [e.read8(TOOL_AMOUNT + 15 * i + 5) for i in range(4)],
            "traffic": [e.read8(PLAYER_BASE + i * STRIDE + P_TRAFFIC) for i in range(4)],
            "ndices": [e.read8(PLAYER_BASE + i * STRIDE + P_NDICES) for i in range(4)],
            "tbak": [e.read8(PLAYER_BASE + i * STRIDE + P_TRAF_BAK) for i in range(4)],
            "nbak": [e.read8(PLAYER_BASE + i * STRIDE + P_NDICE_BAK) for i in range(4)],
            "sleep": [e.read8(PLAYER_BASE + i * STRIDE + P_SLEEP) for i in range(4)],
            "sw": [e.read8(PLAYER_BASE + i * STRIDE + P_SLEEPWALK) for i in range(4)],
            "mis": [e.read8(PLAYER_BASE + i * STRIDE + P_MISFORTUNE) for i in range(4)],
            "mia": e.readu32(M_MIAN), "jia": (e.readu32(M_JIA), e.readu32(M_JIA + 4)),
            "fu": e.readu32(M_FU), "dream": e.readu32(C_DREAM),
            "refresh": e.readu32(C_REFRESH),
            "npc": [(e.read8(NPC_F0C + i * 16), e.read8(NPC_F0D + i * 16))
                    for i in range(4, 8)],
            "sel_arg": e.readu32(M_MIAN + 8),
        }


def main():
    print("差分测试 #43：夢遊卡 `0x4441dc`（卡 16）\n")
    f = F()

    print("[A] 选人 → 扣卡 → 台词（掩码 0 = 取消，卡不消耗）")
    s = f.run(cur=0, mask_ui=0b010, players=[{}, {}, {}, {}])
    case("★ 人类（who=1）走选人框 `0x446ae8(0xe0c0710)`",
         (s["sel_arg"], s["rmc"]), (0xE0C0710, (0, 16)))
    case("★ 扣的是卡 16", s["rmc"], (0, 16))
    case("★ 说一句 `player_say(cur, 3, …)`", s["says"][0], (0, 3))
    case("★ 返回**掩码**（不是下标）", s["ret"], 0b010)
    case("★ 收尾 `0x41d546()` 一次", s["refresh"], 1)
    s2 = f.run(cur=0, mask_ui=0)
    case("★★ 掩码 0 ⇒ 返回 0、**卡不消耗**、没有台词/刷新",
         (s2["ret"], s2["rmc"], s2["says"], s2["refresh"]), (0, (0, 0), [], 0))
    s3 = f.run(cur=0, mask_ai=0b1000, players=[{"who": 2}] * 4)
    case("★ AI（who!=1）走 `0x41e6f2(0)`", s3["sel_arg"], 0)

    print("\n[B] 目标解出、动画只给 AI、仇恨 = 150×物價")
    s = f.run(cur=0, price=2, mask_ui=0b1000, players=[{}, {}, {}, {}])
    case("★ `ctz(0b1000)` ⇒ 目标是 3 号", [h[0] for h in s["hos"]], [3])
    case("★★ 人类施卡**不播**动画", s["anims"], [])
    s_ai = f.run(cur=0, mask_ai=0b0100, players=[{"who": 2}, {"who": 2}, {"who": 2},
                                                {"who": 2}])
    case("★★ AI 施卡播动画：`0x40e669(0, cur.xy, 目标.xy, 0x64)`",
         s_ai["anims"], [[0, 100, 200, 102, 202, 0x64]])
    case("★★ 敌意 = 150 × 物價指數（物價 2 ⇒ 300）", s["hos"], [(3, 0, 300)])

    print("\n[C] 施加：梦游天数 5 / 倒霉 +5 / 座驾回收 / 启动梦游流程")
    case("★★ 目标 `+0x37`（梦游）= **5**（最终目标 != 施卡者）", s["sw"][3], 5)
    case("★ 目标 `+0x42`（倒霉天數）+= 5", s["mis"][3], 5)
    case("★ 备份原座驾/骰子到 `+0x66` / `+0x67`", (s["tbak"][3], s["nbak"][3]), (0, 3))
    case("★ 启动梦游流程 `0x40b93b(目标)`", s["dream"] >= 1, True)
    s = f.run(cur=0, mask_ui=0b0010, players=[{}, {"traffic": 1, "ndices": 3}, {}, {}])
    case("★ 座驾 = 機車(1) ⇒ 道具 5 回池 + 下车 + 骰子回 1",
         (s["tool5"][1], s["tool6"][1], s["traffic"][1], s["ndices"][1]), (1, 0, 0, 1))
    s = f.run(cur=0, mask_ui=0b0010, players=[{}, {"traffic": 2}, {}, {}])
    case("★ 座驾 = 汽車(2) ⇒ 道具 6 回池", (s["tool5"][1], s["tool6"][1]), (0, 1))
    s = f.run(cur=0, mask_ui=0b0010, players=[{}, {"traffic": 0x1F}, {}, {}])
    case("★★ 座驾 = 0x1f（工程車）⇒ **两个池都不回**，但仍下车、骰子回 1",
         (s["tool5"][1], s["tool6"][1], s["traffic"][1], s["ndices"][1]), (0, 0, 0, 1))

    print("\n[D] 两道「不施加」闸")
    s = f.run(cur=0, mask_ui=0b0010, players=[{}, {"sleep": 3}, {}, {}])
    case("★★ 目标已在睡觉（`+0x36 != 0`）⇒ 不记仇恨、不改梦游天数（卡已消耗）",
         (s["hos"], s["sw"][1], s["rmc"]), ([], 0, (0, 16)))
    s = f.run(cur=0, mask_ui=0b10000, npcs={4: 0}, players=[{}, {}, {}, {}])
    case("★★ 目标 ≥ 4（伪玩家）：`+0x0c`（**冬眠**）为 0 ⇒ 只写 `+0x0d`（**梦游**）= 5、不记仇恨",
         (s["npc"][0], s["hos"]), ((0, 5), []))
    s = f.run(cur=0, mask_ui=0b10000, npcs={4: 1}, players=[{}, {}, {}, {}])
    case("★★ 伪玩家槽 `+0x0c != 0`（已在冬眠）⇒ 完全不写 **且不记仇恨**（另一个「不施加」闸）",
         (s["npc"][0], s["hos"]), ((1, 9), []))

    print("\n[E] 防御卡编排：免罪 → 嫁禍（命中即止）→ 復仇")
    s = f.run(cur=0, mask_ui=0b0010, cards={(1, 21): 1}, players=[{}, {}, {}, {}])
    case("★★ 目标持免罪卡(21) ⇒ 调 `0x444bb2(目标)`、**不再查嫁禍**、不施加效果",
         (s["mia"], s["jia"][0], s["sw"][1]), (1, 0, 0))
    case("★ 仇恨调用在免罪判定**之前** ⇒ 仇恨**已经**记上了（只有效果被抵消）",
         [h[0] for h in s["hos"]], [1])
    s = f.run(cur=0, mask_ui=0b0010, jia_ret=2, cards={(1, 19): 1},
              players=[{}, {}, {}, {}])
    case("★★ 目标持嫁禍卡(19) 且返回新目标 2 ⇒ 效果落在 **2 号**身上",
         (s["jia"][0], s["sw"][1], s["sw"][2]), (1, 0, 5))
    case("   仇恨仍记在**原始目标** 1 号头上（仇恨调用在嫁禍之前）",
         [h[0] for h in s["hos"]], [1])
    s = f.run(cur=0, mask_ui=0b0010, jia_ret=-1, cards={(1, 19): 1},
              players=[{}, {}, {}, {}])
    case("★ 嫁禍返回 −1（放弃）⇒ 仍打原目标 1 号", (s["sw"][1], s["sw"][2]), (5, 0))
    s = f.run(cur=0, mask_ui=0b0010, jia_ret=2, cards={(1, 19): 1, (1, 18): 1},
              players=[{}, {}, {}, {}])
    case("★★ 被嫁禍改写后（最终 != 原始）**不查復仇卡**", s["fu"], 0)
    s = f.run(cur=0, mask_ui=0b0010, cards={(1, 18): 1}, players=[{}, {}, {}, {}])
    case("★★ 最终 == 原始 **且** 原始目标持復仇卡(18) ⇒ 调 `0x444691(1)`",
         s["fu"], 1)
    case("★★ 且**施卡者自己**（0 号）梦游 5 天（目标 1 号也照样中招）",
         (s["sw"][0], s["sw"][1]), (5, 5))
    s = f.run(cur=0, mask_ui=0b0010, cards={(1, 21): 1, (1, 19): 1},
              players=[{}, {}, {}, {}])
    case("★ 免罪与嫁禍同时持有 ⇒ **只走免罪**（顺序固定、命中即止）",
         (s["mia"], s["jia"][0]), (1, 0))
    s = f.run(cur=0, mask_ui=0b0010, cards={(1, 18): 1}, players=[{"traffic": 2},
                                                                   {}, {}, {}])
    case("★ 復仇反弹时**施卡者的座驾也回收**（道具 6 +2 池、下车）",
         (s["tool6"][0], s["traffic"][0]), (1, 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
