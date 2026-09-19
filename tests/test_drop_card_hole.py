#!/usr/bin/env python3
"""
通道 2 差分测试 · **小衰神「丢一张卡」`0x00441e77`（87 B）／大衰神「丢一半卡」`0x00441ece`（77 B）**

复刻侧对应 `packages/core/src/rules/god-power.ts` 的
`_rich4_player_drop_random_card` / `_rich4_player_drop_half_the_card`。

★ 本测试是 **`D-LEGACY-4`（`docs/known-deviations.md`）** 的第二份证据。
该偏离第一份证据是 `test_rob_card_ai.py`（搶奪卡 AI `0x41f901`）；
本轮把 `0x441262` 的**全部 12 个字节级调用点**逐个读完，确认「**用非零槽个数当下标上界**」
这个模式一共命中 **4 个函数**，其中两个就是本文件这两支 —— 而它们是**玩家看得见的规则**。

## 语义（逐条从字节读出）

```
0x441262(player):                      ; 手牌「非零槽个数」，**不是**最后一个有牌的槽下标
    n = 0
    for (i = 0; i < 15; i++) if (hand[player][i] != 0) n++
    return n

0x441e77(player):                      ; 小衰神：丢**一张**
    n = 0x441262(player)
    if (n == 0) → return 0             ; 空手 ⇒ 什么都不做
    k = rand() % n                     ; ★ 模数是「非零槽个数」
    c = hand[player][k]                ; ★ 下标 k ∈ [0, n-1]
    0x441343(player, c)                ; 从手里移除
    return c                           ; ★ 返回值就是被丢掉的那张（0 = 没丢到东西）

0x441ece(player):                      ; 大衰神：丢**一半**
    n = 0x441262(player)
    if (n <= 1) → return 0             ; 0 或 1 张 ⇒ 不丢
    for (i = 0; i < n / 2; i++)        ; ★ 上界 = n/2（整除），下标直接取 i
        0x441343(player, hand[player][i])
    return 1
```

## ★★ 为什么这两支值得单独钉：**手牌有洞时行为会变**

`0x441262` 数的是**非零槽的个数**，而两支都拿它（或其一半）当**下标上界**：

| 手牌（15 槽里的前几格） | `0x441262` | 小衰神能丢到谁 | 大衰神丢谁 |
|---|---|---|---|
| `[7]` | 1 | 只能丢 7 | n ≤ 1 ⇒ 不丢 |
| `[5, 9]` | 2 | `rand%2` ⇒ 5 或 9 | n/2=1 ⇒ 丢槽 0 = 5 |
| `[空, 9]` | **1** | `rand%1=0` ⇒ 取槽 0 = **空** ⇒ **一张都没丢** | n ≤ 1 ⇒ 不丢 |
| `[5, 空, 9]` | **2** | `rand%2` ⇒ 槽 0(5) 或槽 1(**空**) ⇒ ★ **9 永远丢不到** | n/2=1 ⇒ 丢槽 0 = 5 |
| `[空, 空, 3, 8]` | **2** | `rand%2` ⇒ 槽 0/1 **都是空** ⇒ 一张都丢不到 | n/2=1 ⇒ 丢槽 0 = **空**（空转） |

而**洞是真实存在的**：`giveCard`（`0x4412e4`）写入**第一个空槽**（`test_card_give.py` 已实证），
用牌会在中间留下洞。
复刻侧手牌是**紧凑数组**（没有洞的概念）⇒ 上表右两列的"能丢到谁"与复刻**不同**。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以 |
|---|---|---|---|
| `0x00441343` | 从手里移除一张（内部走 `memmove 0x456de8`） | `mov eax,[esp+8] / mov [SLOT],eax / ret` —— 只**记录**被丢的卡号 | ★ 真身 `memmove` 的 `push es` 在 Unicorn 上会崩（`verification.md` 工具边界第 1 条）；且"移除"不是本测试的对象 —— **要钉的是"选中哪一张"** |
| `0x00456f2d` | CRT `rand()` | 从数据槽读 | 本测试要固定 `rand` 才能分辨取模与下标 |

`0x441262`（非零槽个数）**真跑** —— 它正是本偏离的根源，绝不能打桩。

跑法：cd rich4-spec && .venv/bin/python tests/test_drop_card_hole.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

DROP_ONE = 0x441E77
DROP_HALF = 0x441ECE
CARD_COUNT = 0x441262
REMOVE = 0x441343
PRNG = 0x456F2D

HAND_BASE, HAND_STRIDE, HAND_SLOTS = 0x499120, 15, 15
RAND_SLOT = SCRATCH_BASE + 0x800
LAST_REMOVED = SCRATCH_BASE + 0x820
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        # rand → 数据槽
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        # 0x441343(player, card) → 把 card 记下来就返回（真身 memmove 会崩）
        self.emu.patch(REMOVE,
                       b"\x8B\x44\x24\x08"                       # mov eax,[esp+8]
                       + b"\xA3" + struct.pack("<I", LAST_REMOVED)  # mov [LAST],eax
                       + b"\xC3")                                # ret
        self.clear()

    def clear(self):
        self.hand = []          # 只铺前几格；其余为 0
        self.rand = 0

    def slots(self, *vals):
        self.hand = list(vals)
        return self

    def _setup(self, emu):
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        emu.write32(LAST_REMOVED, 0x5A5A5A5A)
        emu.write(HAND_BASE, b"\x00" * (HAND_STRIDE * 4))
        for i, v in enumerate(self.hand):
            emu.write8(HAND_BASE + i, v & 0xFF)

    def run(self, fn, player=0):
        r = self.emu.call(fn, [player], setup=self._setup)
        self.ret = r["eax"]
        self.removed = self.emu.readu32(LAST_REMOVED)
        return self


def main():
    print("差分测试 · 小衰神丢一张 0x441e77 / 大衰神丢一半 0x441ece（D-LEGACY-4 第二份证据）\n")
    w = World()

    # ── A. 0x441262 本身：数的是「非零槽个数」 ─────────────────────
    print("[A] 先钉住根源：0x441262(player) = **非零槽的个数**（不是「最后一个有牌的槽下标」）")
    for hand, want in [((), 0), ((7,), 1), ((5, 9), 2), ((0, 9), 1),
                       ((5, 0, 9), 2), ((0, 0, 3, 8), 2), ((1, 2, 3, 4, 5), 5)]:
        w.clear()
        w.slots(*hand)
        r = w.emu.call(CARD_COUNT, [0], setup=w._setup)
        case(f"手牌 {list(hand)!s:<22} ⇒ 计数 {want}", r["eax"], want)

    # ── B. 小衰神：紧凑手牌（复刻口径也一致）────────────────────────
    print("\n[B] 小衰神（紧凑手牌）：`rand() % n` 取下标 ⇒ 均匀取前 n 张")
    w.clear()
    w.slots(7)
    r = w.run(DROP_ONE)
    case("单张 [7] ⇒ n=1 ⇒ rand%1=0 ⇒ 丢 7", r.ret, 7)
    case("  确实调了一次移除（记到 7）", r.removed, 7)

    for rand, want in [(0, 5), (1, 9), (2, 5), (3, 9), (5, 9), (12345, 9)]:
        w.clear()
        w.slots(5, 9)
        w.rand = rand
        r = w.run(DROP_ONE)
        case(f"[5,9] rand={rand} ⇒ {rand}%2={rand % 2} ⇒ 丢 {want}", r.ret, want)

    w.clear()
    w.slots(5, 9, 3)
    w.rand = 12345
    r = w.run(DROP_ONE)
    case("3 张 [5,9,3] rand=12345 ⇒ 12345%3=0 ⇒ 丢 5", r.ret, 5)

    w.clear()
    w.slots()
    r = w.run(DROP_ONE)
    case("★ 空手 ⇒ n=0 ⇒ 返回 0", r.ret, 0)
    case("  且**没有**调移除（哨兵还在）", r.removed, 0x5A5A5A5A)

    # ── C. ★★ 小衰神 + 洞：洞后面的牌永远丢不到 ────────────────────
    print("\n[C] ★★ 小衰神 + 手牌有洞（D-LEGACY-4 的核心）")
    w.clear()
    w.slots(0)
    r = w.run(DROP_ONE)
    case("★ [空] ⇒ n=0 ⇒ 返回 0", r.ret, 0)

    w.clear()
    w.slots(0, 9)
    w.rand = 0
    r = w.run(DROP_ONE)
    case("★★ [空,9] ⇒ n=1 ⇒ rand%1=0 ⇒ 取槽 0 = **空** ⇒ **一张都没丢**", r.ret, 0)
    case("  且仍然调了一次移除（移除的是卡号 0）", r.removed, 0)

    w.clear()
    w.slots(0, 9)
    w.rand = 99                     # ★ 无论 rand 多大都改不了结论
    r = w.run(DROP_ONE)
    case("★★ 同上、rand=99 ⇒ 99%1=0 ⇒ 仍是取槽 0 ⇒ 仍是**丢不到 9**", r.ret, 0)

    w.clear()
    w.slots(5, 0, 9)
    w.rand = 0
    r = w.run(DROP_ONE)
    case("★★ [5,空,9] rand=0 ⇒ 0%2=0 ⇒ 丢槽 0 = 5", r.ret, 5)
    w.rand = 1
    r = w.run(DROP_ONE)
    case("★★ [5,空,9] rand=1 ⇒ 1%2=1 ⇒ 丢槽 1 = **空**", r.ret, 0)
    w.rand = 7
    r = w.run(DROP_ONE)
    case("★★ [5,空,9] rand=7 ⇒ 7%2=1 ⇒ 又是槽 1 ⇒ ★ **9 永远丢不到**", r.ret, 0)

    w.clear()
    w.slots(0, 0, 3, 8)
    w.rand = 1
    r = w.run(DROP_ONE)
    case("★★ [空,空,3,8] ⇒ n=2 ⇒ rand%2=1 ⇒ 取槽 1 = **空** ⇒ 一张都丢不到",
         r.ret, 0)

    w.clear()
    w.slots(0, 0, 0, 0, 2)
    r = w.run(DROP_ONE)
    case("★★ [空×4, 2] ⇒ n=1 ⇒ 只取槽 0 = 空 ⇒ 丢不到 2", r.ret, 0)

    # ── D. 大衰神：紧凑手牌 ────────────────────────────────────────
    print("\n[D] 大衰神（紧凑手牌）：`for (i = 0; i < n/2; i++) 丢 hand[i]`")
    for hand, want_ret, want_last in [
        ((), 0, 0x5A5A5A5A),        # n=0 ⇒ 不丢
        ((7,), 0, 0x5A5A5A5A),      # n=1 ⇒ 不丢（**注意是 ≤1 才不丢**）
        ((5, 9), 1, 5),             # n=2 ⇒ n/2=1 ⇒ 丢槽 0
        ((5, 9, 3), 1, 5),          # n=3 ⇒ n/2=1 ⇒ 丢槽 0
        ((5, 9, 3, 8), 1, 9),       # n=4 ⇒ n/2=2 ⇒ 丢槽 0,1（最后一个被丢的是 9）
        ((5, 9, 3, 8, 2), 1, 9),    # n=5 ⇒ n/2=2 ⇒ 丢槽 0,1
    ]:
        w.clear()
        w.slots(*hand)
        r = w.run(DROP_HALF)
        case(f"手牌 {list(hand)!s:<22} ⇒ 返回 {want_ret}", r.ret, want_ret)
        case("  **最后**被移除的那张", r.removed, want_last)

    # ── E. ★★ 大衰神 + 洞 ─────────────────────────────────────────
    print("\n[E] ★★ 大衰神 + 手牌有洞")
    w.clear()
    w.slots(0, 0, 3, 8)
    r = w.run(DROP_HALF)
    case("★★ [空,空,3,8] ⇒ n=2 ⇒ n/2=1 ⇒ 只丢槽 0 = **空**（空转，3/8 都留着）",
         r.ret, 1)
    case("  被移除的是卡号 0", r.removed, 0)

    w.clear()
    w.slots(0, 9, 3, 0)
    r = w.run(DROP_HALF)
    case("★★ [空,9,3,空] ⇒ n=2 ⇒ n/2=1 ⇒ 只丢槽 0 = 空（真正在手里的 9/3 一张不丢）",
         r.ret, 1)
    case("  被移除的是卡号 0", r.removed, 0)

    w.clear()
    w.slots(5, 0, 0, 0)
    r = w.run(DROP_HALF)
    case("★ [5,空,空,空] ⇒ n=1 ⇒ **≤1 不丢**（返回 0）", r.ret, 0)

    w.clear()
    w.slots(5, 0, 9, 0)
    r = w.run(DROP_HALF)
    case("★★ [5,空,9,空] ⇒ n=2 ⇒ n/2=1 ⇒ 只丢槽 0 = 5（9 逃过一劫）", r.removed, 5)

    # ── F. 两张的对照：紧凑 vs 有洞 ────────────────────────────────
    print("\n[F] ★★ 直接对照：同样是「手里两张牌」，紧凑与有洞结果不同")
    w.clear()
    w.slots(5, 9)
    w.rand = 1
    r = w.run(DROP_ONE)
    compact = r.ret
    w.clear()
    w.slots(5, 0, 9)
    w.rand = 1
    r = w.run(DROP_ONE)
    holed = r.ret
    case("★★ 紧凑 [5,9] rand=1 ⇒ 丢 9", compact, 9)
    case("★★ 有洞 [5,空,9] rand=1 ⇒ 丢 **空**（9 丢不到）", holed, 0)
    case("  ⇒ 两者不同（这就是 D-LEGACY-4 的可见后果）", compact != holed, True)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
