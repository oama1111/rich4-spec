#!/usr/bin/env python3
"""
通道 2 差分测试 · **搶奪卡的 AI 目标选择** `0x0041f901`（442 B）

复刻侧对应 `packages/core/src/ai/card-policy.ts` 的搶奪卡 handler（`@source 0x0041f901`）。
与 `0x41ed3e`（改建卡）同族：**没有 `call` 调用者**（AI 出牌跳表成员），
建图工具不收，要用 `rich4-remake/tools/disasm.py va` 按需反汇编。

## 语义（442 B 全程读完）

```
0x41f901():                                   ; 无参数
    best = 0                                  ; [esp+0xc]，返回值
    me    = [0x49910c]
    hated = 0x40d2d3(me)                      ; ebp，最恨的人（0 基；无则 −1）
    [0x48be60] = 0x40a45c(-1)                 ; ★ 填「可見表」0x48b8c4，返回项数

    ; ── 第 1 趟：把每个可见格上「站着谁」编成掩码
    for (edi = 0; edi < [0x48be60]; edi++) {
        v = word [0x48b8c4 + edi*2]           ; 可见表项（形如 0x80xx 的玩家标记）
        if (!(v & 0x8000))      continue      ; ★ 必须带 bit15
        if (!(v & 0x000f))      continue      ; ★ 低 4 位必须非 0
        for (esi = 1, p = 0; esi < 0x10; esi <<= 1, p++) {
            if (!(v & esi))               continue   ; 位 p ⇒ 玩家 p 在这格
            if (p == me)                  continue   ; ★ 自己不算
            if (player[p].alive(+0x15) == 0) continue ; ★ 出局的不算
            hasPlayer[p] = 1
            slotWord[p]  = esi | 0x8000       ; ★ 待写进 0x48be58 的值
        }
    }

    ; ── 第 2 趟（首选）：最恨的人在画面里 ⇒ 从他手里挑**类型 ≥ 1 最贵**的卡
    if (hated != -1 && hasPlayer[hated]) {
        bn = 0; bv = 0
        for (i = 0; i < 0x441262(hated); i++) {      ; 手牌张数（真跑）
            c = byte [0x499120 + hated*15 + i]       ; 手牌（卡号）
            if (byte [0x47fdf1 + c*8] < 1)  continue ; ★ 卡表 +2 是「类型」，要 ≥ 1
            v = byte [0x47fdef + c*8]                ; ★ 卡表 +0 是「价格」
            if (v <= bv)                    continue ; ★ 严格 >
            bn = c; bv = v
        }
        if (bn != 0) {
            [0x48be58] = slotWord[hated]             ; = bit(hated) | 0x8000
            [0x48be5c] = bn                          ; 选中的卡号
            → 1
        }
    }

    ; ── 第 2 趟（兜底）：画面里**任何人**手里**类型 == 2 最贵**的卡
    for (p = 0; p < [0x499114]; p++) {
        if (!hasPlayer[p])            continue
        for (i = 0; i < 0x441262(p); i++) {
            c = byte [0x499120 + p*15 + i]
            if (byte [0x47fdf1 + c*8] != 2) continue ; ★ 兜底只要**类型 == 2**
            v = byte [0x47fdef + c*8]
            if (v <= bv)                    continue ; ★ 严格 >
            [0x48be58] = slotWord[p]
            [0x48be5c] = c
            best = 1; bv = v
        }
    }
    → best
```

★ **结论**：这是「**先抢最恨的人手里最贵的「类型 ≥ 1」的卡；抢不到就抢画面里任何人手里最贵的「类型 == 2」的卡**」。
两条分支写在同两个全局：`0x48be58` = 目标（**玩家位 + `0x8000`**）、`0x48be5c` = 卡号。

## 打桩清单（两处，都已在别处独立验证过）

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 填「可見表」`0x48b8c4` | `mov eax,[COUNT_SLOT]; ret`（表本身由 `setup()` 直接铺） | 它自己的语义已单独定案（`map-format.md`；复刻换了视野口径 = **D-005**），**不是本测试的对象** |
| `0x00456f2d` | CRT `rand()` | 从数据槽读 | 本函数**不摇随机数** —— 留着是为了让"没摇"这件事可断言 |

`0x40d2d3`（最恨的人）与 `0x441262`（手牌张数）**真跑**。

## ⚠️ 已知偏离

`0x47fdef`（卡价格，步长 8，字节 0）与 `0x47fdf1`（卡类型，字节 2）这两张表
**由本测试自己铺**（用可分辨的值），不是从 exe 读的 —— 因为要测的是 `0x41f901`
的**取数逻辑与比较规则**，不是卡表内容（卡表内容由
`rich4-remake/packages/data/src/binary-truth.test.ts` 的通道 1 独立校验）。
若不铺，`0x47fdf1` 的真值会让用例无法分辨「类型过滤」和「价格」两条判据。

跑法：cd rich4-spec && .venv/bin/python tests/test_rob_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

ROB_AI = 0x41F901
MOST_HATED = 0x40D2D3
VISIBLE_FILL = 0x40A45C
CARD_COUNT = 0x441262
PRNG = 0x456F2D

CUR = 0x49910C
NUM_PLAYERS = 0x499114
CARD_PARAM = 0x48BE58         # 目标（玩家位 | 0x8000）
CARD_ARG = 0x48BE5C           # 卡号
VIS_LIST = 0x48B8C4           # 可見表（word 数组）
VIS_COUNT = 0x48BE60          # 可见项数（由被调函数返回、调用方存）

CARD_TABLE = 0x47FDEF         # 卡表：+0 价格、+2 类型，步长 8
CARD_STRIDE = 8
CARD_TYPE_OFF = 2
HAND_BASE, HAND_STRIDE, HAND_SLOTS = 0x499120, 15, 15

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_ALIVE, P_PERSONALITY = 0x15, 0x17
P_HOSTILITY, HOST_STRIDE = 0x4C, 4

COUNT_SLOT = SCRATCH_BASE + 0x900
RAND_SLOT = SCRATCH_BASE + 0x800

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        # 可見表填充器 → 只把「项数」交回去；表由 setup() 直接铺在 0x48b8c4
        self.emu.patch(VISIBLE_FILL,
                       b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.num_players = 4
        self.hostility = [0, 0, 0, 0]
        self.alive = [1, 1, 1, 1]
        self.visible = []          # [word, ...] 直接铺进 0x48b8c4
        self.hands = {}            # player → [cardId, ...]
        self.cards = {}            # cardId → (price, type)
        self.rand = 0

    # ── 便捷构造 ───────────────────────────────────────────────────
    def players_on(self, *idx, extra=0):
        """一个可见格，位上站着 idx 里的玩家（0 基）；extra 可加别的位"""
        v = 0x8000
        for p in idx:
            v |= 1 << p
        self.visible.append((v | extra) & 0xFFFF)
        return self

    def raw_visible(self, v):
        self.visible.append(v & 0xFFFF)
        return self

    def hand(self, p, *card_ids):
        self.hands[p] = list(card_ids)
        return self

    def card(self, cid, price, typ):
        self.cards[cid] = (price, typ)
        return self

    # ── 注入 / 回读 ─────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, self.num_players)
        emu.write32(COUNT_SLOT, len(self.visible) & 0xFFFFFFFF)
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        emu.write32(CARD_PARAM, SENTINEL)
        emu.write32(CARD_ARG, SENTINEL)
        emu.write32(VIS_COUNT, 0)
        emu.write(0x48B8C4, b"\x00" * 64)
        for i, v in enumerate(self.visible):
            emu.write16(0x48B8C4 + i * 2, v)
        # 玩家
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_ALIVE, self.alive[p])
            emu.write8(pb + P_PERSONALITY, 0)
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        for j, h in enumerate(self.hostility):
            emu.write32(pb + P_HOSTILITY + j * HOST_STRIDE, h & 0xFFFFFFFF)
        # 手牌
        emu.write(HAND_BASE, b"\x00" * (HAND_STRIDE * 4))
        for p, cards in self.hands.items():
            for i, cid in enumerate(cards):
                emu.write8(HAND_BASE + p * HAND_STRIDE + i, cid)
        # 卡表（价格 +0 / 类型 +2）
        for cid in range(1, 16):
            b = CARD_TABLE + cid * CARD_STRIDE
            price, typ = self.cards.get(cid, (0, 0))
            emu.write8(b, price & 0xFF)
            emu.write8(b + CARD_TYPE_OFF, typ & 0xFF)

    def run(self):
        r = self.emu.call(ROB_AI, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(CARD_PARAM)
        self.arg = self.emu.readu32(CARD_ARG)
        return self


def main():
    print("差分测试 · 搶奪卡 AI 目标选择 0x41f901（442 B）\n")
    w = World()

    # ── A. 可見表的两个闸 ─────────────────────────────────────────
    print("[A] 可見表项必须带 bit15 且低 4 位非 0（= 形如 0x80xx 的玩家标记）")
    w.clear()
    w.raw_visible(0x8000)        # bit15 有、低 4 位 = 0
    w.hand(2, 7).card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("低 4 位 = 0 ⇒ 整项跳过 ⇒ 无目标", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    w.clear()
    w.raw_visible(0x0004)        # 低 4 位有、bit15 没有
    w.hand(2, 7).card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("bit15 = 0 ⇒ 整项跳过 ⇒ 无目标", r.ret, 0)

    # ── B. 首选支：最恨的人在画面里 ────────────────────────────────
    print("\n[B] 首选：最恨的人在画面里 ⇒ 从他手里挑「类型 ≥ 1 最贵」的卡")
    w.clear()
    w.players_on(2)
    w.hand(2, 3, 7, 10)
    w.card(3, 25, 1).card(7, 200, 1).card(10, 180, 2)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 返回 1", r.ret, 1)
    case("★★ 0x48be58 = bit(2) | 0x8000 = 0x8004（目标 = 最恨的人）", r.target, 0x8004)
    case("★★ 0x48be5c = 7（价格 200 最大；卡 10 是类型 2 被排除）", r.arg, 7)

    w.clear()
    w.players_on(2)
    w.hand(2, 10, 7)
    w.card(7, 200, 1).card(10, 180, 2)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 手牌顺序反过来 ⇒ 仍选 7（按**价格**不按槽序）", r.arg, 7)

    w.clear()
    w.players_on(2)
    w.hand(2, 3, 7)
    w.card(3, 200, 1).card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 同价时严格 > ⇒ 取**先出现**的（槽序靠前的 3）", r.arg, 3)

    w.clear()
    w.players_on(2)
    w.hand(2, 7)
    w.card(7, 200, 0)             # ★ 类型 0
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 唯一一张是类型 0 ⇒ 首选支不取（要求 类型 ≥ 1）", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    w.clear()
    w.players_on(2)
    w.hand(2, 1, 2)
    w.card(1, 0, 1).card(2, 0, 1)   # 价格都是 0 ⇒ 严格 > 永不成立
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 价格全 0 ⇒ 严格 > 不成立 ⇒ 无目标", r.ret, 0)

    # ── C. 最恨的人「不在画面里」⇒ 走兜底 ─────────────────────────
    print("\n[C] 最恨的人不在画面里 ⇒ 走兜底支（类型 == 2 最贵）")
    w.clear()
    w.players_on(3)               # 画面里只有 3 号
    w.hand(2, 7).card(7, 200, 1)  # 最恨的 2 号手里有贵的类型 1
    w.hand(3, 10, 5)
    w.card(10, 180, 2).card(5, 60, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 2 号不在画面 ⇒ 不能抢他手里的 7 号", r.arg, 10)
    case("★★ 兜底取的 0x48be58 = bit(3) | 0x8000 = 0x8008", r.target, 0x8008)
    case("  返回 1", r.ret, 1)

    w.clear()
    w.players_on(3)
    w.hand(3, 5)
    w.card(5, 60, 1)              # 只有类型 1
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 兜底只要类型 == 2 ⇒ 类型 1 不取", r.ret, 0)

    w.clear()
    w.players_on(3)
    w.hand(3, 5)
    w.card(5, 60, 3)              # 类型 3 也不算
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 类型 3 也不取（兜底是**等于 2**，不是 ≥ 2）", r.ret, 0)

    w.clear()
    w.players_on(1, 3)
    w.hand(1, 4).hand(3, 10)
    w.card(4, 100, 2).card(10, 180, 2)
    w.hostility = [0, 0, 0, 0]     # 谁都不恨 ⇒ hated = −1 ⇒ 直接兜底
    r = w.run()
    case("★★ 兜底跨所有可见玩家取最贵（180 在 3 号手里）", r.arg, 10)
    case("  目标 = 0x8008", r.target, 0x8008)

    w.clear()
    w.players_on(1, 3)
    w.hand(1, 4).hand(3, 10)
    w.card(4, 180, 2).card(10, 100, 2)
    w.hostility = [0, 0, 0, 0]
    r = w.run()
    case("  反过来也对（180 在 1 号手里 ⇒ 0x8002）", r.target, 0x8002)

    # ── D. 自己 / 出局者不算 ───────────────────────────────────────
    print("\n[D] 自己不算、出局的不算")
    w.clear()
    w.players_on(0)                # 只有我自己
    w.hand(0, 7).card(7, 200, 1)
    w.hostility = [0, 0, 0, 0]
    r = w.run()
    case("★ 可见格上只有自己 ⇒ 不产生目标", r.ret, 0)

    w.clear()
    w.players_on(1, 2)
    w.alive[2] = 0                 # 2 号出局
    w.hand(2, 7).hand(1, 4)
    w.card(7, 200, 1).card(4, 100, 2)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 最恨的人已出局 ⇒ 他不算「在画面里」", r.target, 0x8002)
    case("  兜底取 1 号手里的 4", r.arg, 4)

    w.clear()
    w.players_on(0, 2)
    w.hand(2, 7).card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 同一格上「我 + 对手」⇒ 只认对手那一位（0x8004）", r.target, 0x8004)

    # ── E. 掩码位与玩家的对应 ─────────────────────────────────────
    print("\n[E] 位的含义：位 p ⇒ 玩家 p（0 基），写进 0x48be58 时带 0x8000")
    for p in (1, 2, 3):
        w.clear()
        w.players_on(p)
        w.hand(p, 7)
        w.card(7, 200, 1)
        w.hostility = [500 if i == p else 0 for i in range(4)]   # 恨 p ⇒ 走首选项支
        r = w.run()
        want = 0x8000 | (1 << p)
        case(f"只有玩家 {p} 在画面（位 {p}）⇒ 0x48be58 = 0x{want:04x}", r.target, want)
        case("  卡号 = 7", r.arg, 7)

    w.clear()
    w.players_on(1, 2, 3)
    w.hand(1, 4).hand(2, 7).hand(3, 9)
    w.card(4, 10, 2).card(7, 200, 2).card(9, 100, 2)
    w.hostility = [0, 0, 0, 0]
    r = w.run()
    case("★ 一格三人且都可见 ⇒ 兜底比价格（200 在 2 号 ⇒ 0x8004）", r.target, 0x8004)
    case("  卡号 = 7", r.arg, 7)

    # ── F. 多项可见表的遍历 ────────────────────────────────────────
    print("\n[F] 可见表有多项：逐项累积 hasPlayer（不是只取第一项）")
    w.clear()
    w.players_on(3)                # 第 1 项：3 号
    w.players_on(2)                # 第 2 项：2 号
    w.hand(2, 7).hand(3, 4)
    w.card(7, 200, 1).card(4, 180, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 首选项在第 2 项里也要被看到（⇒ 抢 2 号的 7）", r.arg, 7)
    case("  目标 = 0x8004", r.target, 0x8004)

    w.clear()
    w.players_on(3)
    w.players_on(2)
    w.hand(3, 4).hand(2, 7)
    w.card(4, 180, 2).card(7, 200, 2)
    w.hostility = [0, 0, 0, 0]
    r = w.run()
    case("  兜底也跨多项（200 在 2 号 ⇒ 0x8004）", r.target, 0x8004)

    # ── G. 空可见表 ────────────────────────────────────────────────
    print("\n[G] 边界")
    w.clear()
    r = w.run()
    case("可见表为空 ⇒ 0", r.ret, 0)
    case("  两个输出全局都没被碰", (r.target, r.arg), (SENTINEL, SENTINEL))

    w.clear()
    w.players_on(2)
    w.hostility = [0, 0, 500, 0]   # 人在画面里但手里没牌
    r = w.run()
    case("人在画面里但手牌全空 ⇒ 0", r.ret, 0)

    # ★★ 空槽（洞）：原版**看不到洞后面的牌**
    #    `0x441262(p)` 数的是**非零槽的个数**（`cmp byte [..+0x499120],0 / je 跳过计数`），
    #    而 `0x41f901` 的循环是 `for (i = 0; i < count; i++) c = hand[i]` ——
    #    于是 `hand = [空, 7]` ⇒ count = 1 ⇒ **只查槽 0**，槽 1 的 7 号牌被漏掉。
    #    复刻侧 `qiangduo` 遍历的是 `players[hated].cards`（**紧凑数组、没有洞的概念**）
    #    ⇒ 这一格两边行为**不同**。已登记 known-deviations **D-LEGACY-4**。
    w.clear()
    w.players_on(2)
    w.hand(2, 0, 7)                # 槽 0 空、槽 1 是 7 号牌
    w.card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 洞在槽 0 ⇒ count=1 ⇒ 只查槽 0 ⇒ **抢不到 7**（原版就这样）", r.ret, 0)
    case("  所以 0x48be5c 保持哨兵", r.arg, SENTINEL)

    w.clear()
    w.players_on(2)
    w.hand(2, 7, 0)                # 反过来：槽 0 有牌
    w.card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 牌在槽 0 ⇒ count=1 也够 ⇒ 正常抢到 7", r.arg, 7)

    w.clear()
    w.players_on(2)
    w.hand(2, 4, 0, 7)             # 洞在槽 1 ⇒ count=2 ⇒ 只查槽 0/1
    w.card(4, 100, 1).card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 洞在槽 1 ⇒ count=2 ⇒ 只看到槽 0 的 4 号（更贵的 7 号被漏）", r.arg, 4)

    # ── H. 返回值只有 0 / 1 ────────────────────────────────────────
    print("\n[H] 返回值恒为 0 / 1")
    seen = set()
    w.clear(); r = w.run(); seen.add(r.ret)
    w.clear(); w.players_on(2); w.hand(2, 7); w.card(7, 200, 1)
    w.hostility = [0, 0, 500, 0]; seen.add(w.run().ret)
    case("  两种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
