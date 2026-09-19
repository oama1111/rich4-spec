#!/usr/bin/env python3
"""
通道 2 差分测试 #17 · `0x0040e14d(handle)` —— **把一个物件收回**（`release_object`）

规格来源：`gen/db.txt`（本函数 98 条 / 341 字节）+ `docs/systems/gods.md`、
`docs/systems/tools.md`、`docs/systems/save-scalars.md` §2.14（`objects_info` 46×24）。

```asm
0040e14d  edx = [esp+0xc]                  ; arg = handle（物件下标 + 1）
0040e153  test edx,edx / je end            ; handle == 0 → 原样返回
0040e15b  edx -= 1                         ; i = handle - 1
0040e15e  eax = edx*24                     ; objects_info[i]（步长 24）
0040e166  cl = [eax + 0x496d08]            ; +0x00 = 类别
0040e16c  switch (cl)
            0x10 路障    → [0x497321]++            ; 回道具库存（byte +1）
            0x11 地雷    → [0x497322]++
            0x12 定時炸彈 → [0x497323]++；且 [obj+0x05](携带者) != 0 →
                            player[携带者-1].+0x40 = 0        ; 清 f64
            其它(神明)   → 若 [obj+0x05] != 0：
                            player[+0x3f] = 0                 ; god_info
                            player[+0x44] -= word[类别*2 + 0x4749e2]   ; 衰運
                            player[+0x46] -= word[类别*2 + 0x474a06]   ; 財運
                            player[+0x48] -= word[类别*2 + 0x474a2a]   ; 福運
0040e224  if [obj+0x05] == 0: node[[obj+0x02]].+0x26 = 0      ; ★ 有携带者时**不清**节点占用
0040e248  原节点 = [obj+0x02]
0040e25d  [obj+0x02] = [obj+0x04] = [obj+0x05] = 0            ; nodeId / state / attached 全清
0040e275  if i < 0xC:                                        ; ★ 只有前 12 个物件带「搭档」
             ebx = i ^ 1  （奇偶配对）→ call 0x40aa6c(原节点) 挑落点 → call 0x40e033 放搭档
```

★ 本用例验到的六条：
1. `handle == 0` 原样返回；
2. 三种道具（16/17/18）**各自**让库存 `+1`（`0x497321`/`22`/`23`），互不串；
3. 定時炸彈清**携带者**的 `+0x40`（`f64`）；路障/地雷**不清**（它们没有携带者语义）；
4. 神明（默认支）清 `+0x3f`（`god_info`）并按**三张表**把 `+0x44/+0x46/+0x48` **减回去**；
5. ★ `attached != 0` 时**不清节点占用**（`cmp [obj+0x05],0` 在清占用之前）；
6. 物件自身三格（nodeId/state/attached）无论如何都清零。

★ `i < 0xC` 时「搭档登场」：`0x40aa6c(原节点)` 扫**全地图**挑候选格，判据是
（`0x40aac3`..`0x40aad8`）：

```
test dword [node+0x24], 0x80ffff00 / jne 跳过    ; ★ 占用位/物件字节必须全 0
cmp  dword [node+0x18], 0 / jne 收               ; ┐ +0x18 与 +0x1c
cmp  dword [node+0x1c], 0 / je  跳过             ; ┘ **至少一个非 0** 才算候选
```

然后 `rand15() % 候选数` 挑一个（`0x40aadf`，★ **会用掉一个随机数**）；
若 `原节点 != 0`，还要 `abs(dx)` 与 `abs(dy)` 都 < 300（用 CRT 的 `0x458276`），
不满足就**重掷**。⚠️ **候选数为 0 时原版直接 `idiv 0` 崩**（本测试撞到过）。

复刻把落点留给调用方（`known-deviations` Q-OBJ-2），本测试只验「它确实被调用了 +
搭档格拿到了新节点」。

跑法：cd rich4-spec && .venv/bin/python tests/test_object_remove.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

REMOVE_OBJECT = 0x40E14D
# `rand15` 的取状态块入口（0x456f23: `call [0x488f4c] / add eax,0xc`）—— 在无头
# 环境里 `[0x488f4c]` 是 CRT 线程局部访问器，必须打桩成固定返回一个 scratch 地址。
# 见 `tests/test_prng.py` 的 T-A/T-B 两个测试台陷阱。
RAND_ACCESSOR = 0x456F23
RAND_STATE = SCRATCH_BASE + 0x8000   # ★ 远离节点表（0x600000 起的 16×0x28）——放过一次撞车

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
OBJ_BASE, OBJ_STRIDE, OBJ_COUNT = 0x496D08, 24, 46
OBJ_TYPE, OBJ_NODE, OBJ_STATE, OBJ_ATTACHED = 0x00, 0x02, 0x04, 0x05
TOOL_STOCK = 0x497320                 # 8 个 byte
GOD_INFO, F64 = 0x3F, 0x40            # player 内偏移
MISFORTUNE, FORTUNE, LUCK = 0x44, 0x46, 0x48
NODE_TABLE_PTR, NODE_COUNT = 0x498E80, 0x498E9C
NODE_SCRATCH, NODE_STRIDE = 0x600000, 0x28
NODE_OBJ = 0x26                       # node[+0x26] = 该格上的物件字节
MOD_TABLES = (0x4749E2, 0x474A06, 0x474A2A)

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<56} 实际 {got_s!s:<16} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # ★ `i < 0xC` 的「搭档登场」路径会 `call rand15`（`0x40aadf`）——
        #   所以必须先把 rand 的取状态块打桩，否则会在 `0x456f37` 读未映射内存。
        self.emu.patch(RAND_ACCESSOR,
                       bytes([0xB8]) + struct.pack("<I", RAND_STATE) + b"\xC3")
        self.emu.write32(RAND_STATE, 1)

    def remove(self, handle, objs=None, players=None, stock=(0, 0, 0, 0, 0, 0, 0, 0),
               node_obj=0xAA, nodes=16, node_extra=None):
        """objs: {i: (type, nodeId, state, attached)}；players: {i: (godInfo, f64, mis, fort, luck)}"""
        objs = objs or {}
        players = players or {}
        initial = {i: tuple(objs.get(i, (0, 0, 0, 0))) for i in range(OBJ_COUNT)}

        def setup(emu):
            # 节点表：指向 scratch，并给出节点数
            emu.write32(NODE_TABLE_PTR, NODE_SCRATCH)
            emu.write32(NODE_COUNT, nodes)
            for n in range(1, nodes + 1):
                emu.write8(NODE_SCRATCH + n * NODE_STRIDE + NODE_OBJ, node_obj)
            # 候选格判据：`[node+0x24] & 0x80ffff00 == 0` 且（`+0x18` 或 `+0x1c` 非 0）
            for n, (a18, a1c) in (node_extra or {}).items():
                emu.write32(NODE_SCRATCH + n * NODE_STRIDE + 0x18, a18)
                emu.write32(NODE_SCRATCH + n * NODE_STRIDE + 0x1C, a1c)
            # objects_info
            for i in range(OBJ_COUNT):
                base = OBJ_BASE + i * OBJ_STRIDE
                t, nd, st, at = initial[i]
                emu.write8(base + OBJ_TYPE, t)
                emu.write16(base + OBJ_NODE, nd)
                emu.write8(base + OBJ_STATE, st)
                emu.write8(base + OBJ_ATTACHED, at)
            # 玩家
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                gi, f64, mis, fort, luck = players.get(i, (0, 0, 0, 0, 0))
                emu.write8(base + GOD_INFO, gi)
                emu.write8(base + F64, f64)
                emu.write16(base + MISFORTUNE, mis & 0xFFFF)
                emu.write16(base + FORTUNE, fort & 0xFFFF)
                emu.write16(base + LUCK, luck & 0xFFFF)
            # 道具库存
            for i, v in enumerate(stock):
                emu.write8(TOOL_STOCK + i, v)
            # rand 状态每次调用前重置（它在 SCRATCH 区，不被快照恢复）
            emu.write32(RAND_STATE, 1)

        self.emu.call(REMOVE_OBJECT, [handle], setup=setup)
        e = self.emu
        after = [(e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_TYPE),
                  e.read16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE),
                  e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_STATE),
                  e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_ATTACHED))
                 for i in range(OBJ_COUNT)]
        return {
            "stock": [e.read8(TOOL_STOCK + i) for i in range(8)],
            "changed": [i for i in range(OBJ_COUNT) if after[i] != initial[i]],
            "partner_node": after[3][1],
            "objs": [(e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_TYPE),
                      e.read16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE),
                      e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_STATE),
                      e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_ATTACHED))
                     for i in (0, 1, 2, 12, 20, 21)],
            "node_obj": e.read8(NODE_SCRATCH + 5 * NODE_STRIDE + NODE_OBJ),
            "node_obj7": e.read8(NODE_SCRATCH + 7 * NODE_STRIDE + NODE_OBJ),
            "players": [(e.read8(PLAYER_BASE + i * PLAYER_STRIDE + GOD_INFO),
                         e.read8(PLAYER_BASE + i * PLAYER_STRIDE + F64),
                         e.read16(PLAYER_BASE + i * PLAYER_STRIDE + MISFORTUNE),
                         e.read16(PLAYER_BASE + i * PLAYER_STRIDE + FORTUNE),
                         e.read16(PLAYER_BASE + i * PLAYER_STRIDE + LUCK))
                        for i in range(4)],
        }


def main():
    print("差分测试 #17：收回物件 0x0040e14d(handle)\n")
    f = F()

    print("[1] handle == 0：原样返回")
    r = f.remove(0, objs={20: (16, 5, 1, 0)}, stock=(1, 2, 3, 4, 5, 6, 7, 8))
    case("库存不动", r["stock"], [1, 2, 3, 4, 5, 6, 7, 8])
    case("物件记录不动", r["objs"][4], (16, 5, 1, 0))
    case("节点占用不动", r["node_obj"], 0xAA)

    print("\n[2] 路障(16)：库存 +1 在 0x497321，节点占用清零，物件三格清零")
    r = f.remove(21, objs={20: (16, 5, 1, 0)}, stock=(1, 2, 3, 4, 5, 6, 7, 8))
    case("stock[1] 2→3（其余不动）", r["stock"], [1, 3, 3, 4, 5, 6, 7, 8])
    case("objects[20] 三格清零", r["objs"][4], (16, 0, 0, 0))
    case("node[5].+0x26 0xAA→0", r["node_obj"], 0)
    case("别的节点不动", r["node_obj7"], 0xAA)

    print("\n[3] 地雷(17)：落在 0x497322")
    r = f.remove(21, objs={20: (17, 5, 1, 0)}, stock=(1, 2, 3, 4, 5, 6, 7, 8))
    case("stock[2] 3→4", r["stock"], [1, 2, 4, 4, 5, 6, 7, 8])

    print("\n[4] 定時炸彈(18)：落在 0x497323，且清携带者的 +0x40 (f64)")
    r = f.remove(21, objs={20: (18, 5, 1, 3)},
                 players={2: (0, 7, 0, 0, 0)}, stock=(1, 2, 3, 4, 5, 6, 7, 8))
    case("stock[3] 4→5", r["stock"], [1, 2, 3, 5, 5, 6, 7, 8])
    case("player[2].+0x40 7→0", r["players"][2][1], 0)
    case("★ attached != 0 ⇒ **不清**节点占用", r["node_obj"], 0xAA)

    print("\n[5] 神明（默认支）：清 god_info 并按三张表减回去")
    # 类别 1：表值 = 衰運 −100 / 財運 +100 / 福運 0
    r = f.remove(13, objs={12: (1, 5, 1, 2)},
                 players={1: (1, 0, 0, 100, 0)})
    case("player[1].+0x3f (god_info) 1→0", r["players"][1][0], 0)
    case("★ +0x44 减 (−100) ⇒ 0→100", r["players"][1][2], 100)
    case("★ +0x46 减 (+100) ⇒ 100→0", r["players"][1][3], 0)
    case("★ +0x48 减 0 ⇒ 0 不变", r["players"][1][4], 0)
    case("attached != 0 ⇒ 不清节点占用", r["node_obj"], 0xAA)

    # 类别 2：衰運 −200 / 財運 +150 / 福運 0
    r = f.remove(13, objs={12: (2, 5, 1, 1)}, players={0: (2, 0, 50, 20, 0)})
    case("类别 2：+0x44 50−(−200) = 250", r["players"][0][2], 250)
    case("类别 2：+0x46 20−(+150) ⇒ −130（u16）", r["players"][0][3], (-130) & 0xFFFF)

    # 类别 3：衰運 −100 / 財運 0 / 福運 +100
    r = f.remove(13, objs={12: (3, 5, 1, 1)}, players={0: (3, 0, 10, 10, 10)})
    case("类别 3：+0x44 10−(−100) = 110", r["players"][0][2], 110)
    case("类别 3：+0x46 不变", r["players"][0][3], 10)
    case("类别 3：+0x48 10−(+100) ⇒ −90（u16）", r["players"][0][4], (-90) & 0xFFFF)

    print("\n[6] 神明但**没有携带者**（attached == 0）：不清 god_info、不扣修正")
    r = f.remove(13, objs={12: (1, 5, 1, 0)}, players={1: (1, 0, 7, 7, 7)})
    case("player[1] 五项全不动",
         r["players"][1], (1, 0, 7, 7, 7))
    case("★ 但节点占用**清掉**（attached==0 才清）", r["node_obj"], 0)

    print("\n[7] ★ 只有前 12 个物件带「搭档」：i<0xC 会额外动一个物件")
    r = f.remove(21, objs={20: (16, 5, 1, 0)})
    case("i=20（≥0xC）只动自己被清的那一格", r["changed"], [20])
    # ★ i<0xC 时走「搭档登场」：`0x40aa6c` 扫全地图挑候选格（要求 node[+0x24] 的
    #   占用位为 0，且 `+0x18`/`+0x1c` 至少一个非 0），再 `rand() % 候选数`；
    #   若原节点 != 0，还要 abs(dx)/abs(dy) < 300 才算（会重掷）。
    #   本用例把原节点设成 0（物件 nodeId = 0）以跳过 abs 那两步 CRT 调用。
    r = f.remove(3, objs={2: (16, 0, 1, 0)}, node_obj=0, node_extra={1: (1, 0)})
    case("★ i=2（<0xC）⇒ 除了 2，搭档那一格也被写", sorted(r["changed"]) != [2], True)
    case("   被清的那格仍是 2", 2 in r["changed"], True)
    case("   搭档格（3）拿到了新节点（nodeId != 0）", r["objs"][None] if False else
         r["partner_node"] != 0, True)

    print("\n[8] 类别 0（不是道具也不是神明）：只清记录与节点")
    r = f.remove(13, objs={12: (0, 5, 3, 0)}, players={0: (0, 0, 5, 5, 5)},
                 stock=(1, 1, 1, 1, 1, 1, 1, 1))
    case("库存不动", r["stock"], [1] * 8)
    case("玩家不动", r["players"][0], (0, 0, 5, 5, 5))
    case("objects[12] 清零", r["objs"][3], (0, 0, 0, 0))
    case("节点清占用", r["node_obj"], 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
