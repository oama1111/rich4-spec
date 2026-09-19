#!/usr/bin/env python3
"""
通道 2 差分测试 · **怪獸卡的 AI 目标选择** `0x0041f400`（681 B）

复刻侧对应 `packages/core/src/ai/card-policy.ts` 的 `guaishou`（`@source 0x0041f400`），
也是**拆除卡** `0x41f6a9` 的前半（`chaichu` 先按怪獸卡的判法找）。
与 `0x41ed3e`/`0x41f901` 同族：**没有 `call` 调用者**（AI 出牌跳表成员），
建图工具不收 ⇒ 用 `rich4-remake/tools/disasm.py va 0x0041f400` 按需反汇编。

## 语义（681 B 全程读完）

```
0x41f400():                                        ; 无参数
    best = 0                                       ; [esp+0x40] = 返回值
    memset(栈上数组, 0, 0x40)                       ; 每个 owner 两组记录：地块 / 設施
    hated = 0x40d2d3(cur)                          ; 0 基玩家下标（无则 −1）
    [0x48be60] = 0x40a45c(-1)                      ; 可见表项数

    ; ── 第 1 趟：扫可见表，记「每个 owner 的最佳」
    for (i = 0; i < [0x48be60]; i++) {
        v = word [0x48b8c4 + i*2]                  ; ★ 可见项 = **格值**（不是玩家位掩码！）
        if (0x7d0 < v < 0xfa0) {                   ; 地块
            l = land_table + (v-0x7d0)*0x34
            if (l.owner == 0 || l.owner == cur+1 || l.level < 3) continue  ; ★ 三道闸
            o = l.owner * 8                        ; ★ owner 是 **1 基**
            if ([esp+o-8] < l.level) { [esp+o-8] = l.level; [esp+o-6] = v; [esp+o-4] = word [l+0x1c] }
            else if ([esp+o-8] == l.level && word [l+0x1c] > [esp+o-4]) {
                [esp+o-4] = word [l+0x1c]; [esp+o-6] = v }
        } else if (0xfa0 < v < 0x1770) {           ; 設施（**不看企业 0x1770+**）
            f = fac_table + (v-0xfa0)*0x38
            if (f.owner == 0 || f.owner == cur+1 || f.level < 3) continue
            o = f.owner * 8
            if ([esp+o+0x18] < f.level) { [esp+o+0x18] = f.level; [esp+o+0x1c] = word [f+0x22] }
            else if ([esp+o+0x18] == f.level && word [f+0x22] > [esp+o+0x1c]) {
                [esp+o+0x1c] = word [f+0x22] }
            [esp+o+0x1a] = v                    ; 记录号（两条命中支都写）
        }
    }

    ; ── 选择 A：最恨的人优先，**設施先于地块**，两者只要 level ≥ 3
    if (hated != -1) {
        if ([esp + hated*8 + 0x20] >= 3) { [0x48be58] = word [esp + hated*8 + 0x22]; → best = 1 }
        else if ([esp + hated*8] >= 3)   { [0x48be58] = word [esp + hated*8 + 2];   → best = 1 }
    }

    ; ── 选择 B：兜底 —— 遍历 owner，**地块门槛升到 ≥ 4**、設施仍是 ≥ 3，各自取最高（同级比价）
    if (best == 0) {
        for (p = 0; p < 4; p++) {
            if (p == cur || !player[p].alive) continue
            o = p * 8
            if ([esp+o]     >= 4) → 与 (bestLandLvl, bestLandPrice) 比，取高
            if ([esp+o+0x20] >= 3) → 与 (bestFacLvl,  bestFacPrice)  比，取高
        }
        if (bestFacRef  != 0) { [0x48be58] = bestFacRef;  best = 1 }
        else if (bestLandRef != 0) { [0x48be58] = bestLandRef; best = 1 }
    }
    return best
```

★★ **两处非对称，值得单独钉**（都不是常识，写错也"看起来对"）：

1. **记录门槛统一是 `level ≥ 3`，但兜底选择时地块要求 `level ≥ 4`、設施只要 `≥ 3`。**
   ⇒ 一块**别家的 3 级地**：最恨的人有 ⇒ 会选；不是最恨的人 ⇒ **不选**。
2. **最恨的人优先时 `設施` 先于 `地块`**（而兜底也是設施先）。

★ **关于 `owner`(1 基) 与 `hated`(0 基)**：记录写 `[esp + owner*8 - 8]`（地块等级），
读取用 `[esp + hated*8]`。两者**恰好是同一个槽**，因为 `owner*8 - 8 == hated*8 ⟺ owner == hated+1`
—— 正是「owner 1 基、hated 0 基」的关系。**所以没有 off-by-one**（本稿曾一度怀疑有，
逐地址重推后否定；[I] 组就是为这条留的回归断言）。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x0040a45c` | 填「可見表」`0x48b8c4` | `mov eax,[COUNT_SLOT]; ret`（表由 `setup()` 直接铺）—— 它自己的语义已单独定案，复刻换了视野口径 = **D-005** |
| `0x00456f2d` | CRT `rand()` | 从数据槽读 | 

`0x40d2d3`（最恨的人）**真跑** —— 本测试要的正是它与主干的组合。

跑法：cd rich4-spec && .venv/bin/python tests/test_monster_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

MONSTER_AI = 0x41F400
VISIBLE_FILL = 0x40A45C
PRNG = 0x456F2D

CUR = 0x49910C
NUM_PLAYERS = 0x499114          # ★ 必须设：`0x40d2d3` 的循环上界就是它
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
VIS_LIST = 0x48B8C4
VIS_COUNT = 0x48BE60
CARD_PARAM0 = 0x48BE58          # 目标（本函数只写这一槽）
CARD_PARAM1 = 0x48BE5C          # 第二参数 —— 本函数**不该碰**

LAND_STRIDE = 0x34
L_OWNER, L_LEVEL, L_PRICE = 0x19, 0x1A, 0x1C
FAC_STRIDE = 0x38
F_OWNER, F_LEVEL, F_PRICE = 0x19, 0x1A, 0x22

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_ALIVE = 0x15
P_HOSTILITY, HOST_STRIDE = 0x4C, 4

LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000
COUNT_SLOT = SCRATCH_BASE + 0x900
RAND_SLOT = SCRATCH_BASE + 0x800

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0
SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(VISIBLE_FILL, b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.hostility = [0, 0, 0, 0]
        self.alive = [1, 1, 1, 1]
        self.visible = []          # 格值列表（地塊 2000+i / 設施 4000+i）
        self.lands = {}            # index → (owner, level, price)
        self.facs = {}             # index → (owner, level, price)

    def land(self, idx, owner, level, price):
        self.lands[idx] = (owner, level, price)
        self.visible.append(LAND_MARK + idx)
        return self

    def fac(self, idx, owner, level, price):
        self.facs[idx] = (owner, level, price)
        self.visible.append(FAC_MARK + idx)
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(COUNT_SLOT, len(self.visible) & 0xFFFFFFFF)
        emu.write32(RAND_SLOT, 0)
        emu.write32(CARD_PARAM0, SENTINEL)
        emu.write32(CARD_PARAM1, SENTINEL)
        emu.write32(VIS_COUNT, 0)
        # ★ 暂存区跨调用保留 ⇒ 先清表
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(VIS_LIST, b"\x00" * 64)
        for i, v in enumerate(self.visible):
            emu.write16(VIS_LIST + i * 2, v & 0xFFFF)
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_ALIVE, self.alive[p])
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        for j, h in enumerate(self.hostility):
            emu.write32(pb + P_HOSTILITY + j * HOST_STRIDE, h & 0xFFFFFFFF)
        for idx, (o, lv, pr) in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write8(b + L_OWNER, o)
            emu.write8(b + L_LEVEL, lv)
            emu.write16(b + L_PRICE, pr & 0xFFFF)
        for idx, (o, lv, pr) in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write8(b + F_OWNER, o)
            emu.write8(b + F_LEVEL, lv)
            emu.write16(b + F_PRICE, pr & 0xFFFF)

    def run(self):
        r = self.emu.call(MONSTER_AI, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(CARD_PARAM0)
        self.arg1 = self.emu.readu32(CARD_PARAM1)
        return self


def main():
    print("差分测试 · 怪獸卡 AI 目标选择 0x41f400（681 B）\n")
    w = World()

    # ── A. 记录门槛：owner ∉ {0, 我} 且 level >= 3 ─────────────────
    print("[A] 记录门槛：owner ∉ {0, 我}、level ≥ 3（否则连记录都不产生）")
    for owner, lv, desc, want in [
        (0, 5, "owner = 0（无主）", 0),
        (1, 5, "owner = 1（就是我自己，1 基）", 0),
        (2, 2, "别人的 2 级地", 0),
    ]:
        w.clear()
        w.land(1, owner, lv, 100)
        r = w.run()
        case(f"{desc} ⇒ 无目标", r.ret, want)
        case("  没写 0x48be58", r.target, SENTINEL)

    w.clear()
    w.land(1, 2, 4, 100)
    r = w.run()
    case("别人的 4 级地、无人可恨 ⇒ 兜底选中", r.ret, 1)
    case("  目标 = 2001", r.target, LAND_MARK + 1)

    w.clear()
    w.land(1, 2, 3, 100)
    r = w.run()
    case("★★ 别人的 **3 级地**、无人可恨 ⇒ 兜底要求 ≥ 4 ⇒ **不选**", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    # ── B. ★★ 最恨的人：地块 3 级就够 ─────────────────────────────
    print("\n[B] ★★ 最恨的人优先：**地块 3 级就够**（兜底那条要 4 级）")
    w.clear()
    w.land(1, 3, 3, 100)          # 1 基 owner 3 ⇒ 0 基玩家 2
    w.hostility = [0, 0, 500, 0]  # 最恨 0 基玩家 2
    r = w.run()
    case("★★ 最恨的人的 3 级地 ⇒ 选中（同一块地若换了 owner 就不选）", r.ret, 1)
    case("  目标 = 2001", r.target, LAND_MARK + 1)

    w.clear()
    w.land(1, 2, 3, 100)          # 1 基 owner 2 ⇒ 0 基玩家 1
    w.hostility = [0, 0, 500, 0]  # 最恨 0 基玩家 2 —— 与 owner=2 不对应
    r = w.run()
    case("★ 同一块 3 级地，但 owner 不是最恨的人 ⇒ 不选", r.ret, 0)

    w.clear()
    w.land(1, 2, 3, 100)
    w.hostility = [0, 500, 0, 0]  # 最恨 0 基玩家 1 ⇒ 1 基 owner 2
    r = w.run()
    case("★ 最恨的人对上 owner=2 ⇒ 选中", r.ret, 1)

    w.clear()
    w.land(1, 3, 2, 100)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 最恨的人但只有 2 级 ⇒ 仍不选（记录门槛就挡掉了）", r.ret, 0)

    # ── C. ★★ 最恨的人：設施 先于 地块 ───────────────────────────
    print("\n[C] ★★ 最恨的人优先时：**設施先于地块**（两者都够级也选設施）")
    w.clear()
    w.land(1, 3, 9, 999).fac(1, 3, 3, 10)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★★ 他的 9 级地 + 3 级設施 ⇒ 选**設施**（4001）", r.target, FAC_MARK + 1)
    case("  返回 1", r.ret, 1)

    w.clear()
    w.land(1, 3, 9, 999)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("  只有地（没有設施）⇒ 选地（2001）", r.target, LAND_MARK + 1)

    w.clear()
    w.fac(1, 3, 3, 10)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("  只有設施 ⇒ 选設施（4001）", r.target, FAC_MARK + 1)

    # ── D. 同级比价（同 owner 内）────────────────────────────────
    print("\n[D] 同一 owner：先比等级、同级比价（价格在 `land+0x1c` / `fac+0x22`，word）")
    w.clear()
    w.land(1, 2, 4, 100).land(2, 2, 4, 200)
    r = w.run()
    case("★ 两块同级 ⇒ 选**贵**的（2002）", r.target, LAND_MARK + 2)

    w.clear()
    w.land(1, 2, 4, 200).land(2, 2, 4, 100)
    r = w.run()
    case("  反过来也对（2001）", r.target, LAND_MARK + 1)

    w.clear()
    w.land(1, 2, 5, 10).land(2, 2, 4, 999)
    case_ = w.run()
    case("★ 等级优先于价格（5 级 10 元 赢 4 级 999 元）", case_.target, LAND_MARK + 1)

    w.clear()
    w.land(1, 2, 4, 100).land(2, 3, 4, 200)
    r = w.run()
    case("★ 不同 owner 的同级 ⇒ 兜底里比价（2002 更贵）", r.target, LAND_MARK + 2)

    # ── E. 兜底：跨 owner 取最高，設施优先 ────────────────────────
    print("\n[E] 兜底：跨 owner 取最高级（同级比价），最后**設施优先于地块**")
    w.clear()
    w.land(1, 2, 4, 10).land(2, 3, 5, 10)
    r = w.run()
    case("★ 跨 owner 取最高级 ⇒ 5 级那块（2002）", r.target, LAND_MARK + 2)

    w.clear()
    w.land(1, 2, 6, 10).fac(1, 3, 4, 10)
    r = w.run()
    case("★★ 兜底也**設施优先**：别家 6 级地 vs 4 级設施 ⇒ 选設施（4001）", r.target, FAC_MARK + 1)

    w.clear()
    w.land(1, 2, 4, 10).land(2, 3, 4, 10)
    r = w.run()
    case("★ 两块同级不同 owner ⇒ 价也同 ⇒ 取**先遍历到的 owner**（owner 2）", r.target, LAND_MARK + 1)

    # ── F. 跳过我自己 / 出局者 ─────────────────────────────────────
    print("\n[F] 兜底遍历时跳过我自己与出局者")
    w.clear()
    w.land(1, 1, 9, 999)          # 我自己的（1 基 owner 1）
    r = w.run()
    case("★ 只有我自己的地 ⇒ 不选", r.ret, 0)

    w.clear()
    w.land(1, 2, 9, 100).land(2, 3, 4, 100)
    w.alive[1] = 0                # 0 基玩家 1 = 1 基 owner 2，出局
    r = w.run()
    case("★★ 出局者的 9 级地不参与 ⇒ 选别家的 4 级（2002）", r.target, LAND_MARK + 2)

    w.clear()
    w.land(1, 2, 9, 100)
    w.alive[1] = 0
    r = w.run()
    case("  出局者是他自己 ⇒ 无目标", r.ret, 0)

    # ── G. 設施的等级/价格字段 ────────────────────────────────────
    print("\n[G] 設施：等级 `+0x1a`、价格 `+0x22`（与地块的 `+0x1c` 不同）")
    w.clear()
    w.fac(1, 2, 4, 100).fac(2, 2, 4, 300)
    r = w.run()
    case("★ 两个同级設施 ⇒ 选价高的（4002，价在 +0x22）", r.target, FAC_MARK + 2)

    w.clear()
    w.fac(1, 2, 3, 100)
    r = w.run()
    case("★ 別家的 3 级設施 ⇒ 兜底選中（設施門檻就是 ≥3）", r.target, FAC_MARK + 1)

    # ── H. 只被记录的「记录号」是格值本身 ─────────────────────────
    print("\n[H] 输出的是**格值**（2000+i / 4000+i），不是下标")
    w.clear()
    w.land(5, 2, 4, 10)
    r = w.run()
    case("地塊下标 5 ⇒ 输出 2005", r.target, LAND_MARK + 5)

    w.clear()
    w.fac(7, 2, 4, 10)
    r = w.run()
    case("設施下标 7 ⇒ 输出 4007", r.target, FAC_MARK + 7)

    # ── I. ★ 1 基 owner / 0 基 hated 的一致性回归 ─────────────────
    print("\n[I] ★ owner(1 基) 与 hated(0 基) 的一致性（**没有** off-by-one）")
    w.clear()
    w.land(1, 2, 3, 100).land(2, 3, 3, 100)      # owner 2 与 owner 3 各一块 3 级地
    w.hostility = [0, 0, 500, 0]                  # 最恨 0 基玩家 2 ⇒ 1 基 owner 3
    r = w.run()
    case("★★ 最恨 0 基玩家 2 ⇒ 应选 **owner=3** 那块（2002），不是 owner=2", r.target, LAND_MARK + 2)

    w.clear()
    w.land(1, 2, 3, 100).land(2, 3, 3, 100)
    w.hostility = [0, 500, 0, 0]                  # 最恨 0 基玩家 1 ⇒ 1 基 owner 2
    r = w.run()
    case("★★ 最恨 0 基玩家 1 ⇒ 应选 **owner=2** 那块（2001）", r.target, LAND_MARK + 1)

    # ── J. 返回值与「不该碰的槽」──────────────────────────────────
    print("\n[J] 返回值只 0/1；本函数**只写** `0x48be58`，不碰 `0x48be5c`")
    seen = set()
    w.clear(); seen.add(w.run().ret)
    w.clear(); w.land(1, 2, 4, 10); seen.add(w.run().ret)
    w.clear(); w.land(1, 2, 9, 10); seen.add(w.run().ret)
    case("  三种情形下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    w.clear()
    w.land(1, 2, 4, 10)
    w.fac(1, 2, 9, 10)
    w.hostility = [0, 0, 500, 0]
    r = w.run()
    case("★ 命中时 `0x48be5c` 仍是哨兵（只有搶奪卡用那一槽）", r.arg1, SENTINEL)

    # ── K. 企业格值（0x1770+）不参与 ──────────────────────────────
    print("\n[K] 企业格值（≥ 0x1770）本函数不收")
    w.clear()
    w.visible.append(0x1770 + 1)                  # 企业 1 号
    r = w.run()
    case("★ 可见表里只有企业 ⇒ 无目标", r.ret, 0)

    w.clear()
    w.land(1, 2, 4, 10)
    w.visible.append(0x1770 + 1)
    r = w.run()
    case("  地块 + 企业混在可见表里 ⇒ 仍只看地块（2001）", r.target, LAND_MARK + 1)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
