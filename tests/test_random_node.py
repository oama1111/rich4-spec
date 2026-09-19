#!/usr/bin/env python3
"""
通道 2 差分测试 · **随机挑一格「可放东西的空节点」** `0x0040aa0f`（93 B）

这是 `_rich4_find_random_unoccupied_node`（无参照点那一支）。开局摆人
（`0x004082d9 call 0x40aa0f`）与物件登场都用它。

复刻侧对应 `rich4-remake/packages/core/src/rules/object-landing.ts` 的
`objectNodeCandidates` + `runtimeOccupiedNodes` + `pickObjectNode`（`rules/new-game.ts`
的 `drawStartNodes` 把它们串起来）。

## 语义（逐指令读完）

```asm
0x40aa0f():
    buf[256]                                   ; 栈上候选表（1 字节一项）
    n = 0
    for (i = 1; i <= [0x498e9c]; i++) {        ; ★ 节点数，**循环含上界**、从 1 起（0 号不看）
        node = [0x498e80] + i*0x28
        if ([node + 0x24] & 0x80ffff00) continue    ; ★ bit31 + bits8..23
        if ([node + 0x18] == 0 && [node + 0x1c] == 0) continue  ; ★ 四个邻接全 0 ⇒ 孤立格
        buf[n++] = i
    }
    rand()                                     ; ★ 恰好 1 次
    return buf[rand() % n]                     ; 返回 **1 基节点 id**
```

★ 三道闸的边界都容易写错（本文件各配正反例）：
1. 掩码 `0x80ffff00` —— **低 8 位不参与**（`specialKind` 就在低字节，不会被这一闸挡掉），
   **bit24..30 也不参与**；
2. 邻接是 `+0x18` 与 `+0x1c` 两个 **dword**（= 4 个 word 槽位）—— 只看前两个槽会漏掉后两个；
3. 循环**含** `num_nodes`（`jg` 才退出），且**从 1 起**（0 号节点永远不在候选里）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x00456f2d` | CRT `rand()` | 数据槽 + **自增计数槽** | 本测试要钉的正是 `rand() % n` 与「恰好摇 1 次」（D-004 已登记复刻用确定性替身）|

`0x498e80`（节点表指针）/`0x498e9c`（节点数）由 `setup()` 直接铺 —— 它们是被测函数的**输入**。

跑法：cd rich4-spec && .venv/bin/python tests/test_random_node.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

FIND_NODE = 0x40AA0F
PRNG = 0x456F2D

NODE_TABLE_PTR = 0x498E80
NUM_NODES = 0x498E9C
NODE_STRIDE = 0x28
N_ADJ = 0x18          # 4 个 word（本测试按两个 dword 的语义填）
N_FLAGS = 0x24

NODES = SCRATCH_BASE + 0x1000
RAND_SLOT = SCRATCH_BASE + 0x900
RAND_CALLS = SCRATCH_BASE + 0x904
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.clear()

    def clear(self):
        self.num_nodes = 0
        self.nodes = {}        # id → (adj4: list[4], flags)
        self.rand = 0
        return self

    def node(self, nid, adj=(0, 0, 0, 0), flags=0):
        self.nodes[nid] = (list(adj), flags)
        self.num_nodes = max(self.num_nodes, nid)
        return self

    def _setup(self, emu):
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(NUM_NODES, self.num_nodes)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write(NODES, b"\x00" * (NODE_STRIDE * 16))
        for nid, (adj, flags) in self.nodes.items():
            b = NODES + nid * NODE_STRIDE
            for k, v in enumerate(adj):
                emu.write16(b + N_ADJ + k * 2, v & 0xFFFF)
            fv = flags & 0xFFFFFFFF            # write32 用有符号 <i 打包
            if fv >= 1 << 31:
                fv -= 1 << 32
            emu.write32(b + N_FLAGS, fv)

    def run(self):
        r = self.emu.call(FIND_NODE, [], setup=self._setup)
        self.ret = r["eax"]
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        return self


def main():
    print("差分测试 · 随机空节点 `0x40aa0f`（掩码 0x80ffff00 + 邻接非 0 + rand()%n）\n")
    w = World()

    # ── A. 基本筛选 ──
    print("[A] 基本：只有「掩码干净 且 有邻接」的节点进候选")
    w.clear(); w.node(1, adj=(2, 0, 0, 0))
    case("唯一候选（邻接槽 0 非 0）⇒ 返回 1", w.run().ret, 1)
    w.clear(); w.node(2, adj=(1, 0, 0, 0))
    case("候选是节点 2 ⇒ 返回 2（证明返回 1 基 id）", w.run().ret, 2)
    # ★ 空候选表在原版会 `idiv 0` 崩（本测试不构造）；要验「某格被排除」就配一个干净陪跑格
    w.clear(); w.node(1, adj=(0, 0, 0, 0)).node(2, adj=(1, 0, 0, 0))
    w.rand = 0
    case("★ 孤立格（四邻接全 0）被排除 ⇒ 只剩节点 2", w.run().ret, 2)

    # ── B. 掩码 0x80ffff00 的逐位边界 ──
    print("\n[B] 掩码 `0x80ffff00`：命中即排除；低 8 位与 bit24..30 **不**排除")
    # 每例都配一个干净陪跑格 2：命中掩码 ⇒ 只剩 2；不命中 ⇒ 候选 [1,2]、rand=0 取 1
    for bit, name in [(8, "bits8（玩家 0 站这格）"), (11, "bits11"), (12, "bits12（这格有物件）"),
                      (23, "bits23"), (31, "bit31（静态禁放）")]:
        w.clear(); w.node(1, adj=(2, 0, 0, 0), flags=1 << bit).node(2, adj=(1, 0, 0, 0))
        w.rand = 0
        case(f"★ flags bit{bit}（{name}）⇒ 排除（只剩 2）", w.run().ret, 2)
    for bit in (0, 3, 7, 24, 30):
        w.clear(); w.node(1, adj=(2, 0, 0, 0), flags=1 << bit).node(2, adj=(1, 0, 0, 0))
        w.rand = 0
        case(f"  flags bit{bit} 不参与掩码 ⇒ 仍是首个候选（返回 1）", w.run().ret, 1)
    w.clear(); w.node(1, adj=(2, 0, 0, 0), flags=0xFF).node(2, adj=(1, 0, 0, 0))
    w.rand = 0
    case("  低 8 位全 1（specialKind 区）⇒ 仍候选（返回 1）", w.run().ret, 1)
    w.clear(); w.node(1, adj=(2, 0, 0, 0), flags=0x80FFFF00).node(2, adj=(1, 0, 0, 0))
    w.rand = 0
    case("★ 掩码全命中 ⇒ 排除（只剩 2）", w.run().ret, 2)

    # ── C. 邻接的四个槽（两个 dword）──
    print("\n[C] 邻接 = `+0x18` 与 `+0x1c` 两个 dword（4 个 word 槽）——每个槽单独都要能命中")
    for k in range(4):
        adj = [0, 0, 0, 0]
        adj[k] = 9
        w.clear(); w.node(1, adj=tuple(adj))
        case(f"★ 只有邻接槽 {k} 非 0 ⇒ 仍候选（返回 1）", w.run().ret, 1)

    # ── D. 多候选 + rand()%n ──
    print("\n[D] 多候选：`rand() % n` 取候选表第几个；rand **恰好 1 次**")
    w.clear(); w.node(1, adj=(2, 0, 0, 0)); w.node(2, adj=(1, 0, 0, 0)); w.node(3, adj=(2, 0, 0, 0))
    for rand, want in [(0, 1), (1, 2), (2, 3), (5, 3), (7, 2)]:
        w.rand = rand
        r = w.run()
        case(f"rand={rand}（%3={rand % 3}）⇒ 节点 {want}", r.ret, want)
        case("  rand 调用次数", r.rand_calls, 1)

    w.clear(); w.node(1, adj=(2, 0, 0, 0)); w.node(3, adj=(2, 0, 0, 0))
    w.rand = 1
    r = w.run()
    case("★ 候选表是**节点号升序**（跳过的 2 不在表里）⇒ rand=1 取节点 3", r.ret, 3)

    # ── E. 循环上界 / 记录 0 ──
    print("\n[E] 循环 `i = 1..num_nodes`（含上界）；0 号节点永不看")
    w.clear()
    w.node(0, adj=(2, 0, 0, 0))     # 记录 0：合法，但循环从 1 起
    w.node(1, adj=(2, 0, 0, 0))
    w.num_nodes = 1
    r = w.run()
    case("★★ 0 号节点不进候选（循环从 1 起）", r.ret, 1)
    w.clear()
    w.node(1, adj=(2, 0, 0, 0)); w.node(2, adj=(1, 0, 0, 0))
    w.num_nodes = 1                 # 节点 2 在 num_nodes 之外
    w.rand = 1                      # 若节点 2 被算进候选，rand=1 ⇒ 返回 2
    r = w.run()
    case("★ 超过 num_nodes 的节点不进候选", r.ret, 1)
    w.clear()
    w.node(5, adj=(1, 0, 0, 0))
    w.num_nodes = 5                 # 节点 5 恰在 num_nodes 上 ⇒ **含**
    case("★ 节点 id == num_nodes ⇒ 仍在候选内（含上界）", w.run().ret, 5)

    # ── F. 只有一个候选时也摇（与 pickNextNode 同类）──
    print("\n[F] 只有 1 个候选时**照样摇 1 次** rand")
    w.clear(); w.node(4, adj=(3, 0, 0, 0))
    for rand in (0, 1, 7, 99):
        w.rand = rand
        r = w.run()
        case(f"  rand={rand} ⇒ 返回 4", r.ret, 4)
    w.rand = 0
    r = w.run()
    case("★ 单候选时 rand 恰好 1 次（不是 0 次）", r.rand_calls, 1)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
