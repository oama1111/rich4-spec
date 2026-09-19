#!/usr/bin/env python3
"""通道 2 差分测试 #44 · **送神符（卡 22）`0x444c45`** ＋ **請神符（卡 23）`0x444e1a`**

两张「神明/物件」卡在 `card_functions[]` 里都已实现、PRD（`cards.md` §卡 22/§卡 23）
也写了完整规格，但**从未被驱动过**。它们又被 `cards/dispel.ts` / `cards/summon.ts`
引用（工作单里各占一格），故本轮一次把两张整支跑掉。

```asm
; ── 卡 22 送神符 0x444c45（66 条指令，213 字节）──
00444c49  ebx = 0                                  ; ok 标记
00444c52  dl = player[cur][0x40]                   ; 第二神明槽
00444c5a  if (dl != 0) { 0x40e14d(dl); ebx = 1 }   ; ★ 无类型判定，有就送
00444c78  dh = player[cur][0x3f]                   ; god_info
00444c80  if (dh == 0) goto 失败判定
00444c93  t = god_table[dh-1].type                 ; byte [0x496d08+(dh-1)*24]
00444cbb  if (t ∉ {5,6,7,8,0xa,0xf}) goto 失败判定
00444cc4  0x40e32c(cur); ebx = 1                   ; ★ 先清地图节点再送（动画版）
00444cd3  if (ebx == 0) return 0                   ; ★ 卡**不消耗**
00444ce4  remove_card(cur, 22)
00444d0e  say(cur, 0, 台词表[character][21])        ; 0x48128e + 360*ch
00444d15  return 1

; ── 卡 23 請神符 0x444e1a（81 条指令，267 字节）──
00444e25  if (player[cur].who_plays == 1) god = 0x444d1a()   ; 人类：自动选最近
00444e37  else                           god = 0x41e6f2(0)   ; AI
00444e43  if (god == 0) return 0                     ; ★ 卡**不消耗**
00444e52  remove_card(cur, 23)
00444e8a  say(cur, 0, 台词表[character][22])         ; 0x481292 + 360*ch
00444e9e  node = god_table[god-1].node               ; word [0x496d0a+(god-1)*24]
00444ea8  god_table[god-1].node = 0                  ; ★ 动画期间先摘掉
00444eb6  0x41d476(0,0,1)                            ; 镜头
00444efa  0x40e669(god, 格x, 格y, player.x, player.y, 0)
00444f02  god_table[god-1].node = node               ; ★ 动画完再挂回去
00444f18  0x40ead7(cur, node, god)                   ; 附身（真正干活的是它）
00444f20  return god                                 ; ★ 返回**神明 ID**，不是 1
```

## 打桩（9 个）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x40e14d` | `remove_object(handle)` | 记实参（其自身已被 `test_object_remove.py` 验过）|
| `0x40e32c` | 带演出的送神 | 记实参 |
| `0x444d1a` | 人类选神（256 字节，见「诚实边界」）| 返回**可控神明 ID** |
| `0x41e6f2` | AI 选神 | 记实参 + 返回**可控 ID** |
| `0x441343` | `remove_card(player, card)` | 记实参 + 序列 |
| `0x44ef41` | `player_say` | 记三实参（含**台词指针**）|
| `0x41d476` | 镜头/重绘标志 | 记三实参 + 序列 |
| `0x40e669` | 飞移动画 | 记六实参 + **当场读神明的 node** |
| `0x40ead7` | `attach_god(cur,node,god)` | 记三实参 + **当场读神明的 node** |
| `0x41d546` | `refresh_map()` | 计数 + 序列 |

★ 台词断言用的是**真表**（`0x48128e` / `0x481292` 在数据段里，不需要打桩）——
于是「台词索引 k=21 / k=22 与 `character` 的换算」是对着原版数据核的，
不是对着我手抄的常量核的。

**本测试顺带钉住的表**：卡牌台词表（表 B）＝ `0x48123a + 360×角色 + 4×(卡号-1)`，
覆盖 12 角色 × 30 张卡 = **360 条**，语音号公式 `#NNNN = 426 + 52×角色 + (卡号-1)`
（`[L]` 段 360 条全扫、无例外）。★ 这张表**复刻侧还没有**（见
`rich4-remake/docs/gaps/README.md` §7.89）。

**诚实边界**：`0x444d1a`（人类选神，最近的合格神）被本测试打桩 ——
本轮钉的是**卡本体的编排**，不是「怎么挑最近的那个」。它自己的算法在
`cards.md` §卡 23 里有摘录（`0x40a45c` 收集 → `0x40ea62` 可请性 →
`owner == 0` → 距离最小），**未驱动**。

跑法：cd rich4-spec && .venv/bin/python tests/test_god_charm_cards.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402
import rich4dis as R  # noqa: E402

DISPEL, SUMMON = 0x444C45, 0x444E1A
REMOVE_OBJ, ADETACH = 0x40E14D, 0x40E32C
GOD_PICK, AI_PICK = 0x444D1A, 0x41E6F2
REMOVE_CARD, SAY, CAM, ANIM, ATTACH, REFRESH = (0x441343, 0x44EF41, 0x41D476,
                                                0x40E669, 0x40EAD7, 0x41D546)

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE, P_CHAR, P_WHO = 0x08, 0x0A, 0x0C, 0x13, 0x15
P_GOD, P_F64 = 0x3F, 0x40
GOD_TABLE, GOD_NODE = 0x496D08, 0x496D0A      # 24 字节一项：+0 type / +2 node
MAP_BASE_PTR = 0x498E80                       # dword → 地图格数组（一部 40 字节）
CUR = 0x49910C
SPEECH21, SPEECH22 = 0x48128E, 0x481292       # 0x48123a + 360*ch + 4*k
CELL_SIZE = 40
DISP_WL = [5, 6, 7, 8, 0xA, 0xF]              # 送得走的 type 白名单
ALL_TYPES = list(range(0, 0x13))              # 0..18 全扫一遍

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE90
M_RMC1, M_RMC2 = S + 0x900, S + 0x904
SAY_N, M_SAY = S + 0x920, S + 0x940
DET_N, M_DET = S + 0xA00, S + 0xA40
ADET_N, M_ADET = S + 0xA80, S + 0xAC0
CAM_N, M_CAM = S + 0xB00, S + 0xB40
ANIM_N, M_ANIM = S + 0xB80, S + 0xBC0
AT_N, M_AT = S + 0xC00, S + 0xC40
C_REFRESH = S + 0xC80
GOD_RET, AI_RET, M_AI_ARG = S + 0xD00, S + 0xD04, S + 0xD10
NODE_AT_ANIM, NODE_AT_ATTACH = S + 0xD18, S + 0xD1C
ZERO = S + 0xD20
MAPCELLS = S + 0x2000
A1, A2, A3 = 0x24, 0x28, 0x2C
ALL_SLOTS = [SEQ, SEQ_N, M_RMC1, M_RMC2, SAY_N, DET_N, ADET_N, CAM_N, ANIM_N,
             AT_N, C_REFRESH, GOD_RET, AI_RET, M_AI_ARG, NODE_AT_ANIM,
             NODE_AT_ATTACH, ZERO]
ALL_SLOTS += list(range(M_SAY, M_SAY + 12, 4)) + list(range(M_DET, M_DET + 8, 4))
ALL_SLOTS += list(range(M_ADET, M_ADET + 8, 4)) + list(range(M_CAM, M_CAM + 12, 4))
ALL_SLOTS += list(range(M_ANIM, M_ANIM + 24, 4)) + list(range(M_AT, M_AT + 12, 4))
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


def _read_god_node(slot, arg_off=A1):
    """把 `god_table[god-1].node` 读进 slot（god 在 pushad 帧里是 `[esp+arg_off]`）

    ⚠️ 「神明 ID 是第几个实参」因函数而异：`0x40e669(god, …)` 是**第 1 个**，
    `0x40ead7(cur, node, god)` 是**第 3 个** —— 第一版两处都按第 1 个读，
    于是附身桩读的是 `god_table[玩家-1]`（另一个槽），读出来恒 0。
    """
    return (b"\x8B\x44\x24" + bytes([arg_off])         # mov eax, [esp+arg_off]
            + b"\x48"                                  # dec eax
            + b"\x6B\xD0\x18"                          # imul edx, eax, 24
            + b"\x0F\xB7\x82" + struct.pack("<I", GOD_NODE)   # movzx eax, word [edx+0x496d0a]
            + b"\xA3" + struct.pack("<I", slot))       # mov [slot], eax


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(REMOVE_OBJ, _stub(_log(11) + _rec(A1, M_DET) + _count(DET_N)))
        self.emu.patch(ADETACH, _stub(_log(12) + _rec(A1, M_ADET) + _count(ADET_N)))
        self.emu.patch(REMOVE_CARD, _stub(_log(1) + _rec(A1, M_RMC1) + _rec(A2, M_RMC2)))
        self.emu.patch(SAY, _stub(_log(2) + _list(SAY_N, 3, M_SAY)))
        self.emu.patch(CAM, _stub(_log(6) + _list(CAM_N, 3, M_CAM)))
        # 动画桩：先记六实参，再当场读一次神明的 node（证明「动画期间已摘掉」）
        self.emu.patch(ANIM, _stub(_log(5) + _list(ANIM_N, 6, M_ANIM)
                                   + _read_god_node(NODE_AT_ANIM)))
        # 附身桩：记三实参 + 当场读同一个 node（证明「动画完已挂回」）
        self.emu.patch(ATTACH, _stub(_log(7) + _list(AT_N, 3, M_AT)
                                     + _read_god_node(NODE_AT_ATTACH, A3)))
        self.emu.patch(REFRESH, _stub(_log(9) + _count(C_REFRESH)))
        self.emu.patch(GOD_PICK, _stub_ret(_log(10), GOD_RET))
        self.emu.patch(AI_PICK, _stub_ret(_log(3) + _rec(A1, M_AI_ARG), AI_RET))

    def _setup(self, cur=0, who=1, char=0, px=100, py=200, pnode=7, god=0, f64=0,
               types=None, nodes=None, cells=None, god_ret=0, ai_ret=0):
        types = types or {}
        nodes = nodes or {}
        cells = cells or {}

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            emu.write(GOD_TABLE, b"\x00" * (48 * 24))
            emu.write(MAPCELLS, b"\x00" * 0x400)
            emu.write32(CUR, cur)
            emu.write32(GOD_RET, god_ret)
            emu.write32(AI_RET, ai_ret)
            emu.write(PLAYER_BASE, b"\x00" * (4 * STRIDE))
            pb = PLAYER_BASE + cur * STRIDE
            emu.write16(pb + P_X, px)
            emu.write16(pb + P_Y, py)
            emu.write16(pb + P_NODE, pnode)
            emu.write8(pb + P_CHAR, char)
            emu.write8(pb + P_WHO, who)
            emu.write8(pb + P_GOD, god)
            emu.write8(pb + P_F64, f64)
            for gid, t in types.items():
                emu.write8(GOD_TABLE + (gid - 1) * 24, t)
            for gid, node in nodes.items():
                emu.write16(GOD_TABLE + (gid - 1) * 24 + 2, node)
            emu.write32(MAP_BASE_PTR, MAPCELLS)
            for node, (cx, cy) in cells.items():
                emu.write16(MAPCELLS + node * CELL_SIZE, cx)
                emu.write16(MAPCELLS + node * CELL_SIZE + 2, cy)
        return setup

    def run22(self, **kw):
        r = self.emu.call(DISPEL, [], setup=self._setup(**kw))
        e = self.emu
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 12))],
            "det": [e.readu32(M_DET + 4 * i) for i in range(e.readu32(DET_N))],
            "adet": [e.readu32(M_ADET + 4 * i) for i in range(e.readu32(ADET_N))],
            "rmc": (e.readu32(M_RMC1), e.readu32(M_RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4),
                      e.readu32(M_SAY + 12 * i + 8)) for i in range(e.readu32(SAY_N))],
        }

    def run23(self, **kw):
        r = self.emu.call(SUMMON, [], setup=self._setup(**kw))
        e = self.emu
        god = kw.get("god_ret") or kw.get("ai_ret") or 0
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 12))],
            "rmc": (e.readu32(M_RMC1), e.readu32(M_RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4),
                      e.readu32(M_SAY + 12 * i + 8)) for i in range(e.readu32(SAY_N))],
            "cam": [[e.readu32(M_CAM + 12 * i + 4 * k) for k in range(3)]
                    for i in range(e.readu32(CAM_N))],
            "anims": [[e.readu32(M_ANIM + 24 * i + 4 * k) for k in range(6)]
                      for i in range(e.readu32(ANIM_N))],
            "at": [[e.readu32(M_AT + 12 * i + 4 * k) for k in range(3)]
                   for i in range(e.readu32(AT_N))],
            "ai_arg": e.readu32(M_AI_ARG),
            "refresh": e.readu32(C_REFRESH),
            "node_at_anim": e.read32(NODE_AT_ANIM),
            "node_at_attach": e.read32(NODE_AT_ATTACH),
            "node_now": e.read16(GOD_TABLE + (god - 1) * 24 + 2) if god else 0,
            "god_field": e.read8(PLAYER_BASE + P_GOD),
        }

    def cstr(self, va):
        return self.emu.img.cstr(va)

    def card_line(self, ch, card):
        """表 B（卡牌台词表）第 `card` 条 —— `0x48123a + 360*ch + 4*(card-1)`"""
        return self.emu.img.u32(0x48123A + 360 * ch + 4 * (card - 1))


def main():
    print("差分测试 #44：送神符 `0x444c45`（卡 22）＋ 請神符 `0x444e1a`（卡 23）\n")
    f = F()

    print("[A] 卡 22 · 失败支：什么都没得送 ⇒ 返回 0 且**一个调用都没有**")
    s = f.run22(god=0, f64=0)
    case("★★ 两个槽都空 ⇒ 返回 0、无 detach/扣卡/台词",
         (s["ret"], s["seq"], s["rmc"], s["says"]), (0, [], (0, 0), []))
    s = f.run22(god=5, f64=0, types={5: 1})
    case("★★ `god_info!=0` 但 type=1（財神）不在白名单 ⇒ 同样**什么都不做**",
         (s["ret"], s["seq"], s["rmc"]), (0, [], (0, 0)))
    s = f.run22(god=3, f64=0, types={3: 0})
    case("   type=0（表里没写）也拦", (s["ret"], s["seq"]), (0, []))

    print("\n[B] 卡 22 · 第二槽 `+0x40`：**无类型判定，有就送**")
    s = f.run22(god=0, f64=4)
    case("★ `+0x40` 有值 ⇒ `0x40e14d(该字节)`、返回 1",
         (s["ret"], s["det"]), (1, [4]))
    case("★★ 扣卡（22）与台词都在**送走之后**（顺序 11 → 1 → 2）",
         s["seq"], [11, 1, 2])
    case("★ 扣的是卡 22、说话的是当前玩家槽 0",
         (s["rmc"], s["says"][0][:2]), ((0, 22), (0, 0)))
    case("★★ 台词指针 = 真表 `0x48128e`（= `0x48123a + 4*21`，k=21）",
         s["says"][0][2], f.emu.img.u32(SPEECH21))
    s = f.run22(god=0, f64=1, types={})
    case("   `+0x40` 的值不经任何 type 表 ⇒ type=0 也照送", s["det"], [1])

    print("\n[C] 卡 22 · 主神明槽 `+0x3f`：type 白名单 {5,6,7,8,10,15}")
    fired, rets = [], []
    for t in ALL_TYPES:
        s = f.run22(god=1, f64=0, types={1: t})
        if s["adet"]:
            fired.append(t)
        if s["ret"] == 1:
            rets.append(t)
    case("★★ 扫 type 0..18：只有白名单命中（走 `0x40e32c`）", fired, DISP_WL)
    case("★★ 返回 1 的集合 == 白名单（其余 13 个 type 全返回 0）", rets, DISP_WL)
    s = f.run22(god=1, f64=0, types={1: 0xF})
    case("★ 命中时：`0x40e32c(cur)`（**不是** `0x40e14d`）+ 扣卡 + 台词",
         (s["adet"], s["det"], s["rmc"][1], len(s["says"])), ([0], [], 22, 1))
    s = f.run22(god=6, f64=0, types={6: 7})
    case("   送的是 `+0x3f` 那个神（arg = 当前玩家，神由表决定）", s["adet"], [0])

    print("\n[D] 卡 22 · 两槽都有 / 边界组合")
    s = f.run22(god=2, f64=9, types={2: 15})
    case("★★ 两槽都有 ⇒ 先 `0x40e14d(9)`、再 `0x40e32c(cur)`（顺序 11 → 12）",
         (s["det"], s["adet"], s["seq"][:2]), ([9], [0], [11, 12]))
    case("★ 两个都送走了，返回值仍是 **1**（ok 是布尔，不是计数）", s["ret"], 1)
    s = f.run22(god=2, f64=9, types={2: 1})
    case("★★ `+0x40` 有值 + 主神 type 不可送 ⇒ 仍算成功（送走 1 个、扣卡）",
         (s["ret"], s["det"], s["adet"], s["rmc"][1]), (1, [9], [], 22))
    s = f.run22(god=2, f64=0, types={2: 1})
    case("   反过来（只有不可送的主神）⇒ 失败、不扣卡",
         (s["ret"], s["rmc"]), (0, (0, 0)))

    print("\n[E] 卡 22 · 台词索引随 character 变（对着真表核）")
    s = f.run22(god=0, f64=4, char=2)
    case("★★ character=2 ⇒ 指针 = `0x48128e + 720`（真表）",
         s["says"][0][2], f.emu.img.u32(SPEECH21 + 720))
    case("   与 character=0 那条不同", s["says"][0][2] != f.emu.img.u32(SPEECH21), True)

    print("\n[F] 卡 23 · 失败支（神明 ID = 0）")
    s = f.run23(who=1, god_ret=0)
    case("★★ 人类选神返回 0 ⇒ **只在 `0x444d1a` 里转一圈**、无扣卡/台词/镜头/动画/附身",
         (s["ret"], s["seq"], s["rmc"], s["says"], s["at"], s["refresh"]),
         (0, [10], (0, 0), [], [], 0))
    s = f.run23(who=2, ai_ret=0)
    case("★★ AI 路径读到 0 同样失败", (s["ret"], s["rmc"], s["refresh"]), (0, (0, 0), 0))

    print("\n[G] 卡 23 · 两条选神路径")
    s = f.run23(who=1, god_ret=5, nodes={5: 12}, cells={12: (300, 400)})
    case("★ 人类（who==1）走 `0x444d1a`（无实参）", s["seq"][0], 10)
    s = f.run23(who=2, ai_ret=7, nodes={7: 3}, cells={3: (11, 22)})
    case("★★ AI（who!=1）走 `0x41e6f2(0)`（实参是 **0**）",
         (s["seq"][0], s["ai_arg"]), (3, 0))
    case("★ AI 路径的返回值就是 `[0x48be58]` 给出的神明 ID", s["ret"], 7)

    print("\n[H] 卡 23 · 成功支的整条编排")
    s = f.run23(who=1, god_ret=5, char=0, px=100, py=200, nodes={5: 12},
                cells={12: (300, 400)})
    case("★★ 返回**神明 ID**（5），不是布尔 1", s["ret"], 5)
    case("★ 扣卡：`remove_card(cur, 23)`", s["rmc"], (0, 23))
    case("★ 台词：`say(cur, 0, 真表[character][22])`",
         (s["says"][0][0], s["says"][0][1], s["says"][0][2]),
         (0, 0, f.emu.img.u32(SPEECH22)))
    case("★ 镜头 `0x41d476(0, 0, 1)`", s["cam"], [[0, 0, 1]])
    case("★★ 动画 `0x40e669(god, 格x, 格y, 玩家x, 玩家y, 0)` —— 参数序与坐标来源",
         s["anims"], [[5, 300, 400, 100, 200, 0]])
    case("★ 第 6 个实参是 **0**（对比卡 6 轉向卡传 0x64）", s["anims"][0][5], 0)
    case("★★ 附身 `0x40ead7(cur, 神明的原 node, god)`", s["at"], [[0, 12, 5]])
    case("★ 收尾 `0x41d546()` 一次", s["refresh"], 1)
    case("★ 调用顺序：扣卡(1) → 台词(2) → 镜头(6) → 动画(5) → 附身(7) → 刷新(9)",
         s["seq"], [10, 1, 2, 6, 5, 7, 9])

    print("\n[I] 卡 23 · 物件 node 的「暂存 → 清零 → 挂回」")
    s = f.run23(who=1, god_ret=5, nodes={5: 12}, cells={12: (300, 400)})
    case("★★ 动画**期间**神的 node == 0（先摘掉，别画在原地）", s["node_at_anim"], 0)
    case("★★ 附身**当场**神的 node 已挂回 12", s["node_at_attach"], 12)
    case("★ 调用结束后表里的 node 仍是 12（不是 0）", s["node_now"], 12)
    s = f.run23(who=1, god_ret=5, nodes={5: 0}, cells={0: (1, 2)})
    case("   原 node 本来就是 0 ⇒ 全程 0（写回 0 无害）",
         (s["node_at_anim"], s["node_at_attach"], s["at"][0][1]), (0, 0, 0))

    print("\n[J] 卡 23 · 卡不查可请性（那是 `0x40ead7` 的事）")
    s = f.run23(who=2, ai_ret=11, nodes={11: 4}, cells={4: (7, 8)})
    case("★★ AI 请到「不可附身」的惡犬(11) 照样走完全程：扣卡 + 台词 + 附身调用",
         (s["ret"], s["rmc"][1], len(s["says"]), s["at"]), (11, 23, 1, [[0, 4, 11]]))
    case("★ `+0x3f` 是否被改写由 `0x40ead7` 决定 —— 本卡一个字段都不动",
         s["god_field"], 0)

    print("\n[K] 卡 23 · 台词索引随 character 变")
    s = f.run23(who=1, god_ret=5, char=1, nodes={5: 12}, cells={12: (1, 2)})
    case("★★ character=1 ⇒ 指针 = `0x481292 + 360`（真表）",
         s["says"][0][2], f.emu.img.u32(SPEECH22 + 360))
    s = f.run23(who=1, god_ret=9, char=0, nodes={9: 6}, cells={6: (1, 2)})
    case("★ 换一个神 ⇒ 返回值跟着变（9），其余不变", s["ret"], 9)

    print("\n[L] 顺带钉住「卡牌台词表」表 B —— 本卡两条台词就是从这张表取的")
    case("★★ 送神符 ch0 的台词就是 `#0447快滾！\\n我不需要你！`",
         f.cstr(f.card_line(0, 22)), "#0447快滾！\n我不需要你！")
    case("★★ 請神符 ch0 的台词就是 `#0448快來幫我吧！`",
         f.cstr(f.card_line(0, 23)), "#0448快來幫我吧！")
    case("★ 换个角色就换一条（ch1 的請神符 = `#0500天靈靈地靈靈！`）",
         f.cstr(f.card_line(1, 23)), "#0500天靈靈地靈靈！")
    bad_ptr, bad_voice, bad_head = [], [], []
    for ch in range(12):
        for card in range(1, 31):
            p = f.card_line(ch, card)
            if p == 0:
                bad_ptr.append((ch, card))
                continue
            t = f.cstr(p)
            if not (len(t) >= 5 and t[0] == "#" and t[1:5].isdigit()):
                bad_head.append((ch, card, t))
                continue
            if int(t[1:5]) != 426 + 52 * ch + (card - 1):
                bad_voice.append((ch, card, t))
    case("★★ 12 角色 × 30 张卡 = 360 条**全非空**", bad_ptr, [])
    case("★★ 360 条都以 `#NNNN` 开头（语音号前缀）", bad_head, [])
    case("★★ 语音号公式 `426 + 52×角色 + (卡号-1)` —— 360 条**无例外**", bad_voice, [])
    case("★ 卡号 ↔ 列号：第 `card` 条落在列 `card-1`（首/末两张对着原文核）",
         [f.cstr(f.card_line(0, 1)), f.cstr(f.card_line(0, 30))],
         ["#0426有錢大家花！", "#0455瞧你那溫吞\n的模樣！"])
    case("   30 张卡各有各的台词（ch0 的 30 个指针互不相同）",
         len({f.card_line(0, c) for c in range(1, 31)}), 30)

    print("\n[M] 反向核：**哪 26 张卡会读自己那一槽**（机械扫 30 个卡片函数体）")
    im = R.Image(R.EXE_DEFAULT)
    words = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gen",
                              "db.txt"), encoding="utf-8").read().split("\n")

    def body(va):
        head = f"# 0x{va:08x} "
        out, on = [], False
        for ln in words:
            if ln.startswith(head):
                on = True
                continue
            if on and ln.startswith("# 0x"):
                break
            if on:
                out.append(ln)
        return out

    speakers, silent, wrong_slot = [], [], []
    for card in range(1, 31):
        fn = im.u32(0x475D5C + card * 4)
        slot = None
        for ln in body(fn):
            if "0x4812" not in ln:
                continue
            m = re.search(r"0x4812([0-9a-f]{2})", ln)
            if m is None:
                continue
            off = 0x481200 + int(m.group(1), 16)
            if 0x48123A <= off <= 0x48123A + 4 * 29:
                slot = (off - 0x48123A) // 4
        if slot is None:
            silent.append(card)
        else:
            speakers.append(card)
            if slot != card - 1:
                wrong_slot.append((card, slot))
    case("★★ 30 张卡里恰好 26 张读卡牌台词表（槽 0..29 全覆盖）", speakers,
         [c for c in range(1, 31) if c not in (18, 19, 20, 21)])
    case("★★ 没读的 4 张正是**四张被动卡**（18 復仇 / 19 嫁禍 / 20 免費 / 21 免罪，空桩）",
         silent, [18, 19, 20, 21])
    case("★★ 每一张读的都是**自己那一槽**（槽号 == 卡号-1，26/26 无例外）",
         wrong_slot, [])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
