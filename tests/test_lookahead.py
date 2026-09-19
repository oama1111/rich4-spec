#!/usr/bin/env python3
"""
通道 2 差分测试 · **前瞻 / 反瞻**（`0x0040b221` 282 B ／ `0x0040b343` 274 B）

这两支是**同一段算法的两个方向**，在 `gen/functions.json` 里一直是 5 分候选
（复刻侧 `ai/tool-policy.ts:126`（反瞻）与 `ai/card-policy.ts:192`（前瞻）
都实现了它，但**没有任何测试驱动过原版**）。

## 语义（逐条从 `0x40b221` 读出，`0x40b343` 只差两条初值）

```
0x40b221(player, n):                     ; 前瞻
    [0x48b8b4 .. +0x10] = 0              ; ★ 输出缓冲**每次先清 16 字节**
    if (n > 8) n = 8                     ; ★ jle 跳过 ⇒ n ≤ 8（含负数）保持原样
    cur  = player + 0x0c                 ; node_id（脚下那格）
    prev = player + 0x0e                 ; lastNodeId（来路）
    forked = 0
    for (i = 0; i < n; i++) {
        node  = &node_table[cur]         ; [0x498e80] 是指针，stride 0x28
        flags = node + 0x24
        mask  = 0x40000000; k = 0
        for (slot = 0; slot < 4; slot++, mask >>= 1) {
            nb = word [node + 0x18 + slot*2]
            if (nb == 0)        continue
            if (nb == prev)     continue     ; ★ 不走回头路
            if (flags & mask)   continue     ; ★ 该槽被封路（位 30−slot）
            cand[k++] = nb
        }
        if      (k == 0) next = prev         ; ★ 死路 ⇒ 原地（写 prev）
        else if (k == 1) next = cand[0]
        else { next = cand[rand() % k]; forked = 1 }
        buf[i] = next
        prev = cur                           ; ★ prev 是**逐格更新**的，不是固定的 lastNodeId
        cur  = buf[i]
    }
    return forked                            ; 0／1
```

`0x40b343(player, n)` 是**反瞻**：与前瞻**只差起点/来路对调** ——
`cur = player+0x0e`（lastNodeId）、`prev = player+0x0c`（nodeId）。
（`0x40b376` / `0x40b381` 两条 `mov dx/ax, word [eax+0x496b7x]` 正好互换，
其余 80 条指令逐条同构 —— 本测试对两者跑**同一组断言**来钉住这一点。）

## 为什么这几条断言值得写

* **输出缓冲先清**：缓冲只有 8 个 word（`0x48b8b4..0x48b8c3`），紧邻
  **`0x48b8c4` 可見表**。若没有「n 封顶 8」，第 9 格就会踩进可见表 ——
  本测试在 `0x48b8c4` 放哨兵字节来**证明封顶真的生效**。
* **`prev` 逐格更新**（`0x40b311..0x40b315`）是最容易写错的一处：写成固定的
  `lastNodeId` 时，**死路**与**第二格开始的不回头**都会与真值不同。
  两个专门用例（见 [D]/[E]）就是为此设计的。
* 前瞻/反瞻**共用同一个全局缓冲**（`map-format.md` §(2) 已记），
  故两者不能同时持有结果 —— 本测试两条都断言缓冲落点相同。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x00456f2d` | CRT `rand()` | 从**数据槽**读返回值（同 `test_walk_step.py`） |

`0x456f60`（`memset`，对应 C 的 `push 0x10 / push 0 / push 0x48b8b4`）**真跑** ——
「缓冲先清」本身就是要钉住的语义之一。

## ⚠️ 与复刻的已知偏离（不在本测试的断言范围内）

原版这里摇的是**全局 CRT `rand() % k`**；复刻侧走 `ai/card-policy.ts:70` 的
`aiRoll(state, salt, n)` 确定性替身（`(rngState ^ imul(salt,0x9e3779b1)) % n`，
**不推进 `rngState`**）。这是**已登记**的 **D-004**（`docs/known-deviations.md:629`
正文 + `docs/gaps/02-cards.md:125` 逐点表）。所以本测试只钉
`cand[rand() % k]` 这条**取模规则**与 `rand` 的**消费时机**，
不声称复刻的选点与原版逐位相同。

跑法：cd rich4-spec && .venv/bin/python tests/test_lookahead.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

FORWARD = 0x40B221        # 前瞻
BACKWARD = 0x40B343       # 反瞻

NODE_TABLE_PTR, NODE_STRIDE = 0x498E80, 0x28
NODE_ADJ, NODE_FLAGS = 0x18, 0x24

LOOK_BUF = 0x48B8B4       # 前瞻/反瞻共用的输出缓冲（8 个 word）
VISIBLE_LIST = 0x48B8C4   # 紧邻的「可見表」——`0x48b8b4 + 0x10`，用来验封顶

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_LAST = 0x0C, 0x0E

PRNG = 0x456F2D
RAND_SLOT = SCRATCH_BASE + 0x800
NODES = SCRATCH_BASE + 0x1000

SENTINEL = 0xBEEF         # 「可見表」哨兵（若封顶失效会被第 9 格覆盖）

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<24} 期望 {want!s}")
    return ok


class World:
    """把玩家/节点表的状态留在 Python 侧，每拍重新注入（`Emu.call` 会 reset）。"""

    def __init__(self):
        self.emu = Emu()
        # PRNG 桩：mov eax, [slot] / ret —— 返回值放**数据**里，避免重复改代码段补丁
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.player = 0
        self.node = 1              # player + 0x0c
        self.last = 0              # player + 0x0e
        self.adj = {}              # nodeId → 4 个邻接槽
        self.flags = {}            # nodeId → node + 0x24
        self.rand = 0
        self.buf_sentinel = True

    def _setup(self, emu):
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        # ★ 必须先**清空**节点表：`Emu.reset()` 还原的是构造时的快照，
        #   而 SCRATCH 区的写入**跨调用保留**（这正是它存在的意义）。
        #   不清就会读到上一个用例留下的邻接 —— 本稿第一次跑就是被
        #   上一用例的 `adj[6]=[7]` 污染，`[H]` 那两行莫名变成 [6,7]。
        for nid in range(0, 16):
            emu.write(NODES + nid * NODE_STRIDE, b"\x00" * NODE_STRIDE)
        if self.buf_sentinel:
            # 缓冲与可见表都铺满哨兵：用来证明「先清 16 字节」+「不越界到 0x48b8c4」
            for off in range(0, 16, 2):
                emu.write16(LOOK_BUF + off, 0xDEAD)
            emu.write16(VISIBLE_LIST, SENTINEL)
        for nid, slots in self.adj.items():
            base = NODES + nid * NODE_STRIDE
            for slot in range(4):
                emu.write16(base + NODE_ADJ + slot * 2, slots[slot] & 0xFFFF)
        for nid, fl in self.flags.items():
            emu.write32(NODES + nid * NODE_STRIDE + NODE_FLAGS, fl & 0xFFFFFFFF)
        pb = PLAYER_BASE + self.player * PLAYER_STRIDE
        emu.write16(pb + P_NODE, self.node)
        emu.write16(pb + P_LAST, self.last)

    def _read(self):
        emu = self.emu
        buf = [emu.read16(LOOK_BUF + i * 2) for i in range(8)]
        return buf, emu.read16(VISIBLE_LIST)

    def run(self, fn, n):
        """→ self（`.buf` / `.ret` / `.sentinel` 供断言）"""
        r = self.emu.call(fn, [self.player, n], setup=self._setup)
        self.buf, self.sentinel = self._read()
        self.ret = r["eax"]
        return self

    def fwd(self, n=8):
        return self.run(FORWARD, n)

    def bwd(self, n=8):
        return self.run(BACKWARD, n)


def main():
    print("差分测试 · 前瞻 0x40b221 ／ 反瞻 0x40b343\n")
    w = World()

    # ── A. 直线：唯一候选就跟着走 ────────────────────────────────────
    print("[A] 直线 1→2→3→4（每格只有一个邻接）")
    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [3, 0, 0, 0], 3: [4, 0, 0, 0], 4: [0, 0, 0, 0]}
    r = w.fwd(3)
    case("前瞻 3 格 ⇒ buf = [2,3,4]", r.buf[:3], [2, 3, 4])
    case("  后面 5 格被清零（先清 16 字节）", r.buf[3:], [0] * 5)
    case("  返回值 0（一路无岔路）", r.ret, 0)
    case("  可见表哨兵未被碰", r.sentinel, SENTINEL)

    # ── B. n 的边界：封顶 8 / 负数 / 0 ──────────────────────────────
    print("\n[B] `cmp [esp+0x30],8 / jle 跳过` ⇒ 只对 n>8 封顶；负数不封顶")
    w.clear()
    w.adj = {i: [i + 1, 0, 0, 0] for i in range(1, 11)}
    w.adj[10] = [1, 0, 0, 0]           # 闭环，保证第 8 步也有候选
    r = w.fwd(12)
    case("★ n=12 ⇒ 只走 8 格（缓冲就 8 个 word）", r.buf, [2, 3, 4, 5, 6, 7, 8, 9])
    case("★★ 第 9 格**没有**越界写进可见表 0x48b8c4", r.sentinel, SENTINEL)

    w.clear()
    w.adj = {i: [i + 1, 0, 0, 0] for i in range(1, 11)}
    r = w.fwd(8)
    case("  n=8（正好不触发封顶）⇒ 同样 8 格", r.buf, [2, 3, 4, 5, 6, 7, 8, 9])

    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [3, 0, 0, 0]}
    r = w.fwd(0)
    case("★ n=0 ⇒ 一格不走，缓冲全 0", r.buf, [0] * 8)
    case("  返回值 0", r.ret, 0)

    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [3, 0, 0, 0]}
    r = w.fwd(-1)
    case("★ n=−1 ⇒ **不封顶**、循环直接不成立 ⇒ 全 0", r.buf, [0] * 8)
    case("  返回值 0", r.ret, 0)

    # ── C. 候选筛选：来路 / 封路位 ──────────────────────────────────
    print("\n[C] 候选 = 非 0 ∧ ≠ 来路 ∧ 该槽未封路")
    w.clear()
    w.adj = {1: [2, 3, 0, 0]}
    w.last = 2
    r = w.fwd(1)
    case("邻接 [2,3]、来路 2 ⇒ 只剩 3", r.buf[:1], [3])
    case("  只有一个候选 ⇒ 不算岔路（返回 0）", r.ret, 0)

    w.clear()
    w.adj = {1: [2, 3, 0, 0]}
    w.flags = {1: 0x40000000}          # 槽 0 = 位 30
    r = w.fwd(1)
    case("★ 槽 0 封路（bit30）⇒ 排除 2 ⇒ 走 3", r.buf[:1], [3])

    w.clear()
    w.adj = {1: [2, 3, 0, 0]}
    w.flags = {1: 0x20000000}          # 槽 1 = 位 29
    r = w.fwd(1)
    case("★ 槽 1 封路（bit29）⇒ 排除 3 ⇒ 走 2", r.buf[:1], [2])

    w.clear()
    w.adj = {1: [2, 3, 4, 5]}
    w.flags = {1: 0x08000000}          # 槽 3 = 位 27
    w.rand = 2
    r = w.fwd(1)
    case("★ 槽 3 封路（bit27）⇒ 候选 [2,3,4]，rand=2 ⇒ 4", r.buf[:1], [4])
    case("  rand 摇过 ⇒ 返回值 1（有岔路）", r.ret, 1)

    w.clear()
    w.adj = {1: [2, 3, 0, 0]}
    w.flags = {1: 0x100}               # 占用位（0x100 << 玩家号）—— **不是**封路位
    r = w.fwd(1)
    case("★★ 占用位 bit8 **不算**封路 ⇒ 仍是 2 个候选（返回 1）", r.ret, 1)
    case("  取 cand[rand=0] = 2", r.buf[:1], [2])

    # ── D. 岔路取模 ────────────────────────────────────────────────
    print("\n[D] 岔路：`cand[rand() % k]`")
    for rand, want in [(0, 2), (1, 3), (2, 4), (3, 5), (5, 3), (7, 5), (9, 3)]:
        w.clear()
        w.adj = {1: [2, 3, 4, 5]}
        w.rand = rand
        r = w.fwd(1)
        case(f"4 个候选、rand={rand} ⇒ {rand}%4={rand % 4} ⇒ {want}", r.buf[:1], [want])
        case("  返回值 1", r.ret, 1)

    w.clear()
    w.adj = {1: [2, 3, 0, 0]}
    w.rand = 12345
    r = w.fwd(1)
    case("2 个候选、rand=12345 ⇒ 12345%2=1 ⇒ 3", r.buf[:1], [3])

    # ── E. ★ `prev` 逐格更新（最容易写错的一处）────────────────────
    print("\n[E] ★ `prev` 每格更新成「上一格」，不是固定的 lastNodeId")
    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [1, 3, 0, 0]}
    w.last = 0
    r = w.fwd(2)
    case("★ 1→2 之后，2 的候选里 1 被当来路排除 ⇒ 只剩 3", r.buf[:2], [2, 3])
    case("★★ 若 prev 固定在 0 ⇒ 2 会有 2 个候选 ⇒ 返回 1；真值是 0", r.ret, 0)

    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [0, 0, 0, 0]}
    w.last = 0
    r = w.fwd(2)
    case("★ 第 2 格死路 ⇒ buf[1] = **更新后的** prev = 1，不是 0", r.buf[:2], [2, 1])
    case("  死路不算岔路（返回 0）", r.ret, 0)

    w.clear()
    w.adj = {1: [0, 0, 0, 0]}
    w.last = 7
    r = w.fwd(1)
    case("起点就死路 ⇒ buf[0] = 初始 prev = 7", r.buf[:1], [7])
    case("  返回值 0", r.ret, 0)

    w.clear()
    w.adj = {1: [0, 0, 0, 0]}
    w.last = 0
    r = w.fwd(1)
    case("起点死路且来路为 0 ⇒ buf[0] = 0", r.buf[:1], [0])

    # ── F. 反瞻 = 前瞻的起点/来路对调 ──────────────────────────────
    print("\n[F] 反瞻 `0x40b343`：cur ← lastNodeId、prev ← nodeId")
    w.clear()
    w.adj = {5: [1, 0, 0, 0], 6: [7, 0, 0, 0]}
    w.node, w.last = 5, 6
    r = w.fwd(1)
    case("前瞻：起点 5、来路 6 ⇒ 走 1", r.buf[:1], [1])
    r = w.bwd(1)
    case("反瞻：起点 6、来路 5 ⇒ 走 7", r.buf[:1], [7])

    w.clear()
    w.adj = {5: [6, 1, 0, 0], 6: [5, 7, 0, 0]}
    w.node, w.last, w.rand = 5, 6, 0
    r = w.fwd(1)
    case("★ 前瞻：5 的邻接 [6,1]、来路 6 ⇒ 排除 6 ⇒ 只剩 1", r.buf[:1], [1])
    case("  唯一候选 ⇒ 返回 0（若没排除来路会摇随机数 ⇒ 返回 1）", r.ret, 0)
    r = w.bwd(1)
    case("★ 反瞻：6 的邻接 [5,7]、来路 5 ⇒ 排除 5 ⇒ 只剩 7", r.buf[:1], [7])
    case("  唯一候选 ⇒ 返回 0", r.ret, 0)

    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [1, 3, 0, 0]}
    w.node, w.last = 2, 1
    r = w.bwd(2)
    # 反瞻：cur ← last = 1、prev ← node = 2
    #   第 1 格：1 的邻接 [2]，而 2 正是来路 ⇒ 被排除 ⇒ 死路 ⇒ buf[0] = prev = 2
    #   第 2 格：cur = 2、prev = 1（★ 已更新）⇒ 邻接 [1,3] 里排除 1 ⇒ 只剩 3
    case("★ 反瞻逐格更新：第 1 格死路写来路 ⇒ [2,3]", r.buf[:2], [2, 3])
    case("★★ prev 若固定在 node=2 ⇒ 第 2 格会有 2 个候选 ⇒ 返回 1；真值是 0",
         r.ret, 0)

    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [0, 0, 0, 0]}
    w.node, w.last = 2, 1
    r = w.bwd(2)
    #   第 1 格：1 的邻接 [2] 被来路排除 ⇒ 死路 ⇒ buf[0] = 2；prev ← 1、cur ← 2
    #   第 2 格：2 无邻接 ⇒ 死路 ⇒ buf[1] = 更新后的 prev = 1
    case("★ 反瞻连续死路 ⇒ [2,1]（第 2 格写的是**更新后**的 prev=1）",
         r.buf[:2], [2, 1])

    # ── G. 两者共用同一个全局缓冲 ──────────────────────────────────
    print("\n[G] 前瞻/反瞻**共用** `0x48b8b4`（不能同时持有两份结果）")
    w.clear()
    w.adj = {5: [1, 0, 0, 0], 6: [7, 0, 0, 0], 1: [0, 0, 0, 0], 7: [0, 0, 0, 0]}
    w.node, w.last = 5, 6
    w.fwd(1)
    case("前瞻跑完 ⇒ 缓冲是前瞻的结果", w.buf[:1], [1])
    w.bwd(1)
    case("★ 反瞻跑完 ⇒ 同一格的缓冲已被覆盖", w.buf[:1], [7])
    case("  缓冲地址确实都是 0x48b8b4（前瞻写 8 格 + 清空 ⇒ 尾部为 0）", w.buf[1:], [0] * 7)

    # ── H. 同构性：把「前瞻从 (node,last) 出发」与「反瞻从 (last,node) 出发」
    #        放进**同一个拓扑**，证明两者确实是同一台机器、只差初值
    print("\n[H] 同一拓扑下两条函数的对照")
    w.clear()
    w.adj = {1: [2, 3, 4, 5], 5: [6, 0, 0, 0]}
    w.node, w.last, w.rand = 5, 1, 3
    # 前瞻：cur ← 5、prev ← 1 ⇒ 邻接 [6] 且 6≠1 ⇒ 唯一候选 6；第 2 格（6 号，空）⇒ 死路写 prev=5
    f = w.fwd(2)
    case("前瞻：起点 node=5、来路 last=1 ⇒ [6,5]", f.buf[:2], [6, 5])
    case("  唯一候选、第 2 格死路 ⇒ 全程无岔路 ⇒ 返回值 0", f.ret, 0)

    w.clear()
    w.adj = {1: [2, 3, 4, 5], 5: [6, 0, 0, 0]}
    w.node, w.last, w.rand = 5, 1, 3
    # 反瞻：cur ← 1、prev ← 5 ⇒ 邻接 [2,3,4,5] 排除 5 ⇒ 三候选 ⇒ rand=3 ⇒ cands[3%3=0]=2
    #       第 2 格（2 号，空）⇒ 死路写 prev=1
    b = w.bwd(2)
    case("★ 反瞻 同一拓扑：起点 last=1、来路 node=5 ⇒ [2,1]", b.buf[:2], [2, 1])
    case("  三分支岔路摇过随机数 ⇒ 返回值 1（前瞻那支是 0）", b.ret, 1)

    w.clear()
    w.adj = {1: [2, 3, 4, 5], 5: [6, 0, 0, 0]}
    w.node, w.last, w.rand = 5, 1, 0
    case("★ 反瞻 rand=0 ⇒ 取 cands[0]=2（与前瞻的 6 不同 ⇒ 起点/来路确实对调了）",
         w.bwd(2).buf[:1], [2])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
