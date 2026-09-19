#!/usr/bin/env python3
"""
通道 2 差分测试 #19 · `0x0040cd07(player)` —— **毁掉座驾／回合末的交通工具回收**

规格来源：`gen/db.txt`（本函数 40 条 / 128 字节）+ `docs/systems/tools.md`、
`docs/systems/places.md` §五之二（`0x40cc56` 的挪位原语）。

```asm
0040cd08  edx = arg = player
0040cd0c  eax = player*0x68
0040cd0f  cmp byte [player+0x15], 0 / je 0x40cd70     ; who_plays == 0 → 另一支
0040cd18  cmp dword [player+0x32], 0 / jne 0x40cd70   ; ★ 已被关/住 → 免疫
0040cd21  cl = byte [player+0x11]                     ; traffic_method
0040cd27  test cl, cl / je 0x40cd5b                   ; ★ 已经是徒步 → 直接去置 0x40
0040cd2b  al = cl & 3
           1 → [0x497324]++    ; ★ 道具 5（機車）回**全局**库存
           2 → [0x497325]++    ; ★ 道具 6（汽車）
           0/3 → 不回库存
0040cd49  [player+0x11] = 0                           ; traffic_method = 徒步
0040cd54  [player+0x12] = 1                           ; ★ ndices = 1（一颗骰）
0040cd5e  or byte [player+0x15], 0x40                 ; ★ 无条件置「本回合无车」位
0040cd66  call 0x40b93b(player)                       ; 重绘/摆位（**表现层**，本测试打桩）
; 另一支：
0040cd70  cmp byte [player+0x15], 0 / jne 0x40cd85    ; 活着但被阻碍 → 什么都不做
0040cd7c  call 0x40cc56(player)                       ; who_plays == 0 → **挪位**（乞丐那个原语）
```

★ 本用例验到的五条：
1. 機車(1) → `0x497324` +1、汽車(2) → `0x497325` +1（**回车是回全局库存，不是回自己道具栏**）；
2. `traffic_method` 归 0、`ndices` 归 1；
3. ★ `+0x15 |= 0x40` **无条件**（连 `traffic_method == 0` 这一支也置）；
4. ★ 已被关押/住宿的玩家**免疫**（早退，连 `0x40` 都不置）；
5. `who_plays == 0` 时走 `0x40cc56` 的**挪位**分支。

★★ **`+0x15` 的 `0x40` 位是纯表现位**：全 exe 只有 `0x40cd5e` 写它，
而读它的只有重绘例程 `0x40b93b`（`0x40b976 test cl,0x40`）——
复刻不镜像它（客户端按 `trafficMethod` 画棋子），故**不需要**建模。

跑法：cd rich4-spec && .venv/bin/python tests/test_vehicle_wreck.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

WRECK = 0x40CD07
REPAINT = 0x40B93B            # 表现层，打桩成 ret
RELOCATE = 0x40CC56           # 挪位（会自己调 0x40aa6c 挑格 → 用 rand）
RAND_ACCESSOR = 0x456F23

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE, P_LAST, P_TRAFFIC, P_NDICES, P_WHO, P_BLOCK = (
    0x08, 0x0A, 0x0C, 0x0E, 0x11, 0x12, 0x15, 0x32)
TOOL_STOCK = 0x497320         # 8 个 byte，**下标 = 道具号 − 1**
NODE_TABLE_PTR, NODE_COUNT = 0x498E80, 0x498E9C
NODE_SCRATCH, NODE_STRIDE = 0x600000, 0x28
NODE_X, NODE_Y, NODE_ADJ, NODE_OCC = 0x00, 0x02, 0x18, 0x24
RAND_STATE = SCRATCH_BASE + 0x8000   # ★ 远离节点表（踩过一次撞车）

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<56} 实际 {got_s!s:<16} 期望 {want_s!s}")
    return ok


def node_addr(n):
    return NODE_SCRATCH + n * NODE_STRIDE


class F:
    def __init__(self):
        self.emu = Emu()
        # ① 重绘例程（表现层）打桩成 ret —— 它内部会 read_mkf，无头跑不动
        self.emu.patch(REPAINT, b"\xC3")
        # ② rand 的取状态块入口打桩（挪位那条分支要用）
        self.emu.patch(RAND_ACCESSOR,
                       bytes([0xB8]) + struct.pack("<I", RAND_STATE) + b"\xC3")

    def wreck(self, idx, traffic=1, who=1, block=0, stock=None, node_id=5):
        stock = stock or [0] * 8
        nodes = {1: (10, 10, [2]), 5: (300, 400, [1]), 7: (500, 500, [1])}

        def setup(emu):
            emu.write32(NODE_TABLE_PTR, NODE_SCRATCH)
            emu.write32(NODE_COUNT, len(nodes) + 1)
            for nid, (x, y, adj) in nodes.items():
                a = node_addr(nid)
                emu.write16(a + NODE_X, x)
                emu.write16(a + NODE_Y, y)
                for k, v in enumerate(adj[:4]):
                    emu.write16(a + NODE_ADJ + 2 * k, v)
                emu.write32(a + NODE_OCC, 0)
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write16(base + P_X, 100)
            emu.write16(base + P_Y, 100)
            emu.write16(base + P_NODE, node_id)
            emu.write16(base + P_LAST, 0)
            emu.write8(base + P_TRAFFIC, traffic)
            emu.write8(base + P_NDICES, 6)
            emu.write8(base + P_WHO, who)
            emu.write32(base + P_BLOCK, block & 0xFFFFFFFF)
            for i, v in enumerate(stock):
                emu.write8(TOOL_STOCK + i, v)
            emu.write32(RAND_STATE, 1)

        self.emu.call(WRECK, [idx], setup=setup)
        e = self.emu
        base = PLAYER_BASE + idx * PLAYER_STRIDE
        return {
            "stock": [e.read8(TOOL_STOCK + i) for i in range(8)],
            "traffic": e.read8(base + P_TRAFFIC),
            "ndices": e.read8(base + P_NDICES),
            "who": e.read8(base + P_WHO),
            "block": e.read32(base + P_BLOCK),
            "node": e.read16(base + P_NODE),
        }


def main():
    print("差分测试 #19：毁座驾 / 交通工具回收 0x0040cd07(player)\n")
    f = F()

    print("[1] 機車(1) / 汽車(2) 回**全局**库存")
    r = f.wreck(0, traffic=1, stock=[1, 2, 3, 4, 5, 6, 7, 8])
    case("traffic=1 ⇒ stock[4] 5→6（道具 5 = 機車）", r["stock"][4], 6)
    case("   其余不动", [r["stock"][i] for i in (3, 5, 6)], [4, 6, 7])
    r = f.wreck(0, traffic=2, stock=[1, 2, 3, 4, 5, 6, 7, 8])
    case("traffic=2 ⇒ stock[5] 6→7（道具 6 = 汽車）", r["stock"][5], 7)
    r = f.wreck(0, traffic=3, stock=[1, 2, 3, 4, 5, 6, 7, 8])
    case("traffic=3 ⇒ **不回**库存", r["stock"][4:6], [5, 6])

    print("\n[2] traffic / ndices 归一")
    r = f.wreck(0, traffic=1)
    case("+0x11（traffic_method）= 0", r["traffic"], 0)
    case("+0x12（ndices）= 1", r["ndices"], 1)

    print("\n[3] ★ `+0x15 |= 0x40` 是**无条件**的")
    r = f.wreck(0, traffic=1, who=1)
    case("有车时置位", r["who"] & 0x40, 0x40)
    r = f.wreck(0, traffic=0, who=1)
    case("★ 本来就徒步（traffic=0）也照样置位", r["who"] & 0x40, 0x40)
    case("   而 traffic/ndices 不再被写", (r["traffic"], r["ndices"]), (0, 6))

    print("\n[4] ★ 已被关押/住宿 ⇒ 免疫（早退，连 0x40 都不置）")
    # inHotel = 3 → dword +0x32 = 0x00000003
    r = f.wreck(0, traffic=1, who=1, block=0x00000003, stock=[1, 2, 3, 4, 5, 6, 7, 8])
    case("stock 不动", r["stock"][4], 5)
    case("traffic 不动", r["traffic"], 1)
    case("★ +0x15 不动（0x40 没置）", r["who"] & 0x40, 0)

    print("\n[5] ★ who_plays == 0 ⇒ 走挪位分支 0x40cc56（节点会变）")
    r = f.wreck(0, traffic=1, who=0, node_id=5)
    case("★ 节点被挪走（不再是 5）", r["node"] != 5, True)
    case("   这条路上 traffic 不归零（0x40cd07 的规则段没跑）", r["traffic"], 1)

    print("\n[6] 活着但被阻碍（traffic 非 0、block 非 0）→ 两支都不做")
    r = f.wreck(0, traffic=2, who=1, block=0xFF)
    case("节点不动", r["node"], 5)
    case("stock 不动", r["stock"][5], 0)
    case("+0x15 不动", r["who"] & 0x40, 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
