#!/usr/bin/env python3
"""
通道 2 差分测试 #56 · **樂透開獎「摇号」那一段**（`0x430b0d`–`0x430b7a`，在状态 4 里）

開獎屏状态 4（`0x430485`）里有一段**纯规则**代码：扫 36 个号码槽、统计每人的票数、
决定「必中」还是「可能空开」、再摇一个号码出来。它不是函数入口，故用
`eval_block` + 手搭寄存器驱动：

```asm
; @source 0x00430b07（LoopHead：eax 从 0xffffffff 起，第一条就 inc ⇒ 0）
00430b07  inc eax
00430b08  cmp eax, 0x24 / jge 0x430b2a   ; 扫 36 格
00430b0d  cl = byte [eax + 0x4990b8]     ; ★ 槽值 = 持有者下标 + 1，0 = 未售出
00430b13  test cl,cl / je LoopHead
00430b19  dl = cl
00430b1b  inc byte [esp + edx + 0x7f]    ; ★ 每人票数（esp+0x80..0x83）
00430b1f  dl = al + 1
00430b23  mov byte [esp + ebx + 0x40], dl ; ★ 已售号码表（1 基），ebx = 已售张数
00430b27  inc ebx
00430b2a  cmp byte [esp+0x80], 0xa / ja 0x430b52   ; ★ 四条：任一玩家 > **10** 张
00430b34  cmp byte [esp+0x81], 0xa / ja 0x430b52
00430b3e  cmp byte [esp+0x82], 0xa / ja 0x430b52
00430b48  cmp byte [esp+0x83], 0xa / jbe 0x430b66
; ── 分支 A（有人 >10 张 ⇒ **必有人中奖**）──
00430b52  rand() / idiv ebx                ; ebx = 已售张数 n
00430b60  bl = byte [esp + edx + 0x40]     ; = 已售号码表[rand() % n]（1 基）
; ── 分支 B（人人 ≤10 张 ⇒ **可能空开**）──
00430b66  rand() / mov ebx,0x24 / idiv ebx
00430b77  ebx = edx + 1                    ; ★ = rand() % 36 + 1 ∈ 1..36
00430b7a  （出口）
```

★ 三条要点（全部实测）：

| # | 事实 | 对应复刻 |
|---|---|---|
| 1 | ★ 门槛是**严格大于 10**（`ja 0xa`），「恰好 10 张」走**可能空开**那支 | `drawLottery` 的 `n > LOTTERY_RIG_THRESHOLD(10)` |
| 2 | ★ 分支 A 抽的是**已售号码表**（不是 36 全表）⇒ `rand() % n` 后取 1 基号码 | `sold[rng.next() % sold.length]` |
| 3 | ★ 分支 B 是 `rand() % 36 + 1`（**可能抽到空槽**） | `rng.next() % LOTTERY_NUMBERS`（0 基） |

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x456f2d` | `mov eax,[槽] / ret` | `rand()`。返回值取自**数据槽**（`SCRATCH_BASE+0x800`），因为代码段的补丁在同实例里重写不生效（见 `test_turn_around.py` 的注释） |

跑法：cd rich4-spec && .venv/bin/python tests/test_lottery_draw_roll.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

LOOP_HEAD = 0x430B07        # ★ 必须从**循环头**进：它第一条就是 `inc eax`，故 eax
                            #   初值给 0xffffffff 才会从槽 0 开始扫。直接进 0x430b0d
                            #   会漏掉槽 0（第一版就栽在这：`0x430b0d` 不是循环头）。
STOP = 0x430B7A
PRNG = 0x456F2D
RAND_SLOT = SCRATCH_BASE + 0x800
SLOTS = 0x4990B8            # 36 个号码槽（值 = 持有者下标 + 1）
SLOT_N = 0x24
TABLE_DUMP = 0x4300D0       # 開獎屏状态机跳表（10 项）
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<22} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    @staticmethod
    def rand_stub(slot):
        return b"\xA1" + struct.pack("<I", slot) + b"\xC3"

    def _setup_slots(self, e, slots, rand):
        e.patch(PRNG, self.rand_stub(RAND_SLOT))
        e.write32(RAND_SLOT, rand & 0xFFFFFFFF)
        for i in range(SLOT_N):
            e.write8(SLOTS + i, slots[i] if i < len(slots) else 0)

    def roll(self, slots, rand):
        """返回开奖号码（1..36）。"""
        emu = Emu()

        def setup(e):
            self._setup_slots(e, slots, rand)
        out = emu.eval_block(LOOP_HEAD, STOP, regs={"eax": 0xFFFFFFFF, "ebx": 0},
                             setup=setup, timeout_insns=200000)
        self.emu = emu
        return out["regs"]["ebx"]

    def count_at_branch(self, slots, rand=0):
        """在**分支判定点 `0x430b2a`** 停住，返回已售张数 `ebx`。

        ★ 为什么必须停在这里：出口 `0x430b7a` 的 `ebx` 已经是**摇号结果**
        （分支 B 是 `ebx = rand()%36+1`），空表也会得到一个号码 ——
        「有没有卖出票」这个判据只存在于判定点。
        """
        emu = Emu()

        def setup(e):
            self._setup_slots(e, slots, rand)
        out = emu.eval_block(LOOP_HEAD, 0x430B2A, regs={"eax": 0xFFFFFFFF, "ebx": 0},
                             setup=setup, timeout_insns=200000)
        return out["regs"]["ebx"]


def slots_from(spec):
    """`{玩家下标+1: [号码(1..36), ...]}` → 36 槽。"""
    t = [0] * SLOT_N
    for owner, nums in spec.items():
        for n in nums:
            t[n - 1] = owner
    return t


def main():
    print("差分测试 #56：樂透開獎摇号段 0x430b0d–0x430b7a\n")

    print("[A] 状态机跳表 `0x4300d0` 的索引 3 就是状态 4（本段所在的状态）")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE_DUMP + 4 * i, 4))[0] for i in range(10)]
    case("[3] = 0x430485", got[3], 0x430485)

    print("\n[B] ★★ 门槛：**任一玩家 > 10 张**才「必中」，恰好 10 张不算")
    #   玩家 1 持 1..10（10 张）、玩家 2 持 11..20 ⇒ 人人 ≤10 ⇒ 走**分支 B**
    t10 = slots_from({1: list(range(1, 11)), 2: list(range(11, 21))})
    for r in (0, 4, 30, 35, 36, 200, 3599):
        case(f"10 张 + rand={r} ⇒ 分支 B：{r}%36+1 = {r % 36 + 1}",
             F().roll(t10, r), r % 36 + 1)
    #   ★ 关键性质：分支 B 可以抽到**未售出**的号码（这里 21..36 全是空的）
    case("★ 10 张 + rand=30 ⇒ 号码 31（**空槽** ⇒ 无人中奖、奖金结转）",
         F().roll(t10, 30), 31)

    print("\n[C] ★ 11 张 ⇒ 分支 A：只在**已售号码**里抽（`rand() % n`）")
    t11 = slots_from({1: list(range(1, 12))})        # 号码 1..11 全归玩家 1
    for r in (0, 1, 10, 11, 1000):
        case(f"11 张 + rand={r} ⇒ 已售表[{r}%11] = 号码 {r % 11 + 1}",
             F().roll(t11, r), r % 11 + 1)

    #   ★ 已售号码**不连续**且有人 >10 张 ⇒ 走分支 A，可验「表里存的是**号码**而非下标」
    nums3 = [2, 9, 14, 27, 31, 33, 35, 36, 1, 3, 4, 7]      # 12 张（玩家 3）
    nums1 = [5, 6, 8, 20, 10, 11, 12, 13]                    # 8 张（玩家 1）
    sparse = slots_from({3: nums3, 1: nums1})
    sold_sorted = sorted(nums3 + nums1)
    n = len(sold_sorted)
    for r in (0, 3, 7, 11, 13, 19, 20):
        want = sold_sorted[r % n]
        case(f"★ 稀疏表 n={n}，rand={r} ⇒ 已售表[{r % n}] = 号码 {want}",
             F().roll(sparse, r), want)
    case("★ 号码不是 1..n 连续 ⇒ 证明表里存的是**号码**",
         (F().roll(sparse, 0), F().roll(sparse, 1)), (sold_sorted[0], sold_sorted[1]))

    print("\n[D] 全 36 张售出（n = 36 ⇒ 两支相同）")
    full = slots_from({1: list(range(1, 37))})
    for r in (0, 5, 35, 36, 71):
        case(f"满场 rand={r} ⇒ {r % 36 + 1}", F().roll(full, r), r % 36 + 1)

    print("\n[E] ★ 单张票**仍走分支 B**（「>10 张」是分支 A 的唯一条件，与总票数无关）")
    #   ⇒ 单张票也可能抽到**别**的号码（这里只有号码 36 有票，但 rand=0 ⇒ 开 1）
    one = slots_from({4: [36]})          # 只有号码 36 有票
    for r in (0, 7, 35, 99):
        case(f"只有号码 36 有票 + rand={r} ⇒ 分支 B 给 {r % 36 + 1}（未必是 36）",
             F().roll(one, r), r % 36 + 1)
    case("★ 其中 rand=35 恰好抽到已售的 36 ⇒ 才会有人中奖", F().roll(one, 35), 36)
    one2 = slots_from({4: [1]})          # 只有号码 1 有票
    case("只有号码 1 有票 + rand=99 ⇒ 分支 B 给 28（空槽 ⇒ 无人中奖）",
         F().roll(one2, 99), 28)
    case("同上 rand=0 ⇒ 才抽到 1", F().roll(one2, 0), 1)

    print("\n[F] ★ 空表：扫完 36 格 `ebx` 仍是 **0**（上层 `0x431712` 据此**不开屏**）")
    #   ⚠️ 不能在出口 0x430b7a 读 ebx：那里**已经被摇号结果覆盖**了
    #      （分支 B 是 `ebx = rand()%36+1`，所以空表也会得到一个号码）。
    #      「有没有卖出票」的判据在**分支判定点**：`0x430b2a` 处 ebx 是多少。
    case("★ 36 格全 0 ⇒ 判定点 ebx = 0（⇒ 上层不开屏）", F().count_at_branch([0] * SLOT_N), 0)
    case("★ 单张票 ⇒ 判定点 ebx = 1", F().count_at_branch(one), 1)
    case("★ 20 张票 ⇒ 判定点 ebx = 20", F().count_at_branch(sparse), 20)
    case("★ 满场 ⇒ 判定点 ebx = 36（且四人的票数都 ≤10 才走分支 B）",
         F().count_at_branch(full), 36)
    case("★ 空表仍然会摇出一个号码（这一段不做「有没有票」的判定，只摇号）",
         F().roll([0] * SLOT_N, 3), 4)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
