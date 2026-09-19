#!/usr/bin/env python3
"""
通道 2 差分测试 · **均貧卡（卡 2）的 AI 判据** `0x0041e779`（274 B）

复刻侧对应 `rich4-remake/packages/core/src/ai/card-policy.ts` 的 `junpin`。

## 语义（逐指令读完）

```
0x41e779():
    hated = 0x40d2d3(cur)                  ; 最恨的人（0 基，−1 = 无）
    [0x48be60] = 0x40a45c(-1)              ; 可見表项数
    mark[4] = {0}
    for (i = 0; i < [0x48be60]; i++) {     ; 扫可见表里的玩家标记
        v = word [0x48b8c4 + i*2]
        if (!(v & 0x8000)) continue
        if (!(v & 0x000f)) continue
        for (p = 0, bit = 1; bit < 0x10; p++, bit <<= 1) {
            if (!(v & bit))            continue
            if (p == cur)              continue
            if (player_p.who(+0x15)==0) continue
            mark[p] = 1
        }
    }
    ; ── 支 A：最恨的人，门槛 **严格** 30000×pi < cash 且 我×2 < cash
    if (hated != -1 && mark[hated]) {
        if (30000*pi < players[hated].cash && cur.cash*2 < players[hated].cash) {
            [0x48be58] = 0x8000 | (1<<hated); return 1
        }
    }
    ; ── 支 B：兜底，门槛 **严格** 50000×pi < cash 且 我×3 < cash
    for (p = 0; p < [0x499114]; p++) {
        if (!mark[p]) continue
        if (50000*pi < players[p].cash && cur.cash*3 < players[p].cash) {
            [0x48be58] = 0x8000 | (1<<p); esi = 1
        }                                   ; ★ **不 break** ⇒ 下标最大者赢
    }
    return esi
```

★★ 本文件要钉的最重要一条：**支 B 不 break**（`0x41e8d1 mov esi,1` 之后
`0x41e8d6 inc [esp+8] / jmp` 回循环头）⇒ 多人同时合格时**取下标最大者**，
与查稅卡（`0x4202d2`，§7.139(3)）是**同一个形状的坑**。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 填「可見表」`0x48b8c4` | `mov eax,[COUNT_SLOT]; ret`（表由 `setup()` 直接铺）| 视野口径差异 = **D-005**，非本测试对象；本测试要钉的是「表项怎么被解读」（0x8000 / 低 4 位 / 位序）|

`0x40d2d3`（最恨的人）**真跑** ⇒ `setup()` 必须写 `[0x499114]`（人数），
否则它恒返回 −1（`verification.md` 工具边界第 5 条）。

跑法：cd rich4-spec && .venv/bin/python tests/test_junpin_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

JUNPIN = 0x41E779
VISIBLE_FILL = 0x40A45C

CUR = 0x49910C
NUM_PLAYERS = 0x499114
PRICE_INDEX = 0x4990E8
VIS_LIST = 0x48B8C4
VIS_COUNT = 0x48BE60
AI_P0 = 0x48BE58
AI_P1 = 0x48BE5C

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_CASH = 0x15, 0x1C
P_HOSTILITY, HOST_STRIDE = 0x4C, 4

COUNT_SLOT = SCRATCH_BASE + 0x900
SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(VISIBLE_FILL, b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.price = 1
        self.visible = []          # 0x80xx 标记词
        self.players = {}          # idx → (who, cash)
        self.hostility = [0, 0, 0, 0]
        return self

    def set(self, idx, cash, who=2):
        self.players[idx] = (who, cash)
        return self

    def see(self, *markers):
        self.visible = list(markers)
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(COUNT_SLOT, len(self.visible))
        emu.write32(VIS_COUNT, 0)
        emu.write32(AI_P0, SENTINEL)
        emu.write32(AI_P1, SENTINEL)
        emu.write(VIS_LIST, b"\x00" * 64)
        for i, v in enumerate(self.visible):
            emu.write16(VIS_LIST + i * 2, v & 0xFFFF)
        for p in range(4):
            b = PLAYER_BASE + p * PLAYER_STRIDE
            who, cash = self.players.get(p, (0, 0))
            emu.write8(b + P_WHO, who)
            cv = cash & 0xFFFFFFFF
            if cv >= 1 << 31:
                cv -= 1 << 32
            emu.write32(b + P_CASH, cv)
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        for j, h in enumerate(self.hostility):
            emu.write32(pb + P_HOSTILITY + j * HOST_STRIDE, h & 0xFFFFFFFF)

    def run(self):
        r = self.emu.call(JUNPIN, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(AI_P0)
        return self


def main():
    print("差分测试 · 均貧卡 AI `0x41e779`（最恨：30000×pi 且 >我2倍；兜底：50000×pi 且 >我3倍）\n")
    w = World()

    # ── A. 可见表的解读 ──
    print("[A] 可見表：bit15 与低 4 位是两道闸；位 p ⇒ 玩家 p")
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x8002)                                   # 只有玩家 1 上屏
    r = w.run()
    case("★ 0x8002 ⇒ 玩家 1 合格（兜底）", r.target, 0x8002)
    case("  返回 1", r.ret, 1)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x0002)                                   # 缺 bit15
    case("★ 缺 bit15（0x0002）⇒ 不算上屏", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x8000)                                   # 低 4 位为 0
    case("★ 低 4 位为 0（0x8000）⇒ 不算上屏", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x8001)                                   # 只标记我自己
    case("★ 只标记 cur 自己 ⇒ 不用", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000, who=0).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x8002)                                   # 标记玩家 1，但他出局
    case("★ 上屏但 who_plays == 0 ⇒ 不算", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1
    w.see(0x800A)                                   # 位 1 与位 3
    r = w.run()
    case("★ 一格多玩家位（0x800A = p1|p3）⇒ 兜底取**下标最大**者 3", r.target, 0x8008)

    # ── B. 支 A：最恨的人 ──
    print("\n[B] 支 A（最恨的人）：`30000×pi < 他现金` 且 `我×2 < 他现金`（都严格）")
    w.clear(); w.me = 0
    w.set(0, 1000).set(1, 40000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 5, 0, 0]; w.price = 1; w.see(0x8002)
    r = w.run()
    case("★ 最恨者现金 40000 > 30000 且 > 2000 ⇒ 选他", r.target, 0x8002)
    case("  返回 1", r.ret, 1)

    w.clear(); w.me = 0
    w.set(0, 1000).set(1, 30000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 5, 0, 0]; w.price = 1; w.see(0x8002)
    case("★★ 最恨者现金恰为 30000×pi ⇒ 支 A 不中（且 < 50000 兜底也不中）", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 20000).set(1, 40000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 5, 0, 0]; w.price = 1; w.see(0x8002)
    # 30000 < 40000 ✓，但我×2 = 40000，40000 < 40000 为假 ⇒ 支 A 不中；50000 < 40000 假 ⇒ 0
    case("★★ 我×2 恰等于他现金 ⇒ 支 A 不中", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 19999).set(1, 40000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 5, 0, 0]; w.price = 1; w.see(0x8002)
    case("★ 我×2 + 1 < 他现金 ⇒ 选他", w.run().target, 0x8002)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 40000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 0, 0, 0]; w.price = 1; w.see(0x8002)
    case("  没有最恨的人 ⇒ 支 A 跳过（40000 < 50000 ⇒ 0）", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 90000).set(2, 10000).set(3, 10000)
    w.hostility = [0, 5, 0, 0]; w.price = 1
    w.see(0x8004)                                   # 最恨的人没上屏
    r = w.run()
    case("★ 最恨的人未上屏 ⇒ 支 A 跳过；兜底看到的是玩家 2（10000 < 50000）⇒ 0", r.ret, 0)

    # ── C. ★★ 支 B 不 break ⇒ 下标最大者赢 ──
    print("\n[C] ★★ 兜底支**不 break**（`0x41e8d1` 之后回循环）⇒ 下标最大的合格者赢")
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 60000).set(2, 60000).set(3, 60000)
    w.price = 1
    w.see(0x8002, 0x8004, 0x8008)                   # 三人全上屏、全合格
    r = w.run()
    case("★★ 三人全合格 ⇒ 取**下标最大**的玩家 3（旧实现返回玩家 1）", r.target, 0x8008)
    case("  返回 1", r.ret, 1)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 60000).set(2, 10000).set(3, 60000)
    w.price = 1
    w.see(0x8002, 0x8004, 0x8008)
    case("★★ 只有 1 与 3 合格 ⇒ 取 3", w.run().target, 0x8008)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 60000).set(2, 10000).set(3, 10000)
    w.price = 1
    w.see(0x8002, 0x8004, 0x8008)
    case("★ 只有玩家 1 合格 ⇒ 取 1", w.run().target, 0x8002)

    # 最恨的人合格时**不进兜底**（支 A 直接返回）
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 40000).set(2, 90000).set(3, 90000)
    w.hostility = [0, 5, 0, 0]; w.price = 1
    w.see(0x8002, 0x8004, 0x8008)
    r = w.run()
    case("★ 支 A 命中即返回（不走兜底的「取最大」）", r.target, 0x8002)

    # ── D. 兜底门槛的严格性 ──
    print("\n[D] 兜底门槛：`50000×pi < 现金` 且 `我×3 < 现金`（都严格）")
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 50000).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002)
    case("★★ 现金恰为 50000×pi ⇒ 不中", w.run().ret, 0)
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 50001).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002)
    case("★★ 现金 50001 ⇒ 中", w.run().target, 0x8002)
    w.clear(); w.me = 0
    w.set(0, 20000).set(1, 90000).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002)
    # 50000 < 90000 ✓，但我×3 = 60000 < 90000 ✓ ⇒ 中
    case("★ 我×3 = 60000 < 90000 ⇒ 中", w.run().target, 0x8002)
    w.clear(); w.me = 0
    w.set(0, 30000).set(1, 90000).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002)
    # 我×3 = 90000，90000 < 90000 为假 ⇒ 不中
    case("★★ 我×3 恰等于他现金 ⇒ 不中", w.run().ret, 0)

    # 物价指数进两处门槛
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 110000).set(2, 10000).set(3, 10000)
    w.price = 2; w.see(0x8002)
    # 50000×2 = 100000 < 110000 ✓ ⇒ 中
    case("★ pi=2：门槛 100000 < 110000 ⇒ 中", w.run().target, 0x8002)
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 100000).set(2, 10000).set(3, 10000)
    w.price = 2; w.see(0x8002)
    case("★ pi=2：现金恰为 100000 ⇒ 不中", w.run().ret, 0)

    # ── E. 输出槽与返回 ──
    print("\n[E] 命中才写 `0x48be58`；`0x48be5c` 不碰；返回 0/1")
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 10000).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002, 0x8004)
    r = w.run()
    case("无人合格 ⇒ 返回 0", r.ret, 0)
    case("  且 `0x48be58` 保持哨兵（未写）", r.target, SENTINEL)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 60000).set(2, 60000).set(3, 10000)
    w.price = 1; w.see(0x8002, 0x8004)
    r = w.run()
    case("★ 命中时 `0x48be5c` 仍是哨兵（只有搶奪卡用它）",
         w.emu.readu32(AI_P1), SENTINEL)

    seen = set()
    w.clear(); w.me = 0; w.set(0, 100).set(1, 60000).set(2, 10000).set(3, 10000)
    w.price = 1; w.see(0x8002); seen.add(w.run().ret)
    w.clear(); w.me = 0; w.set(0, 100).set(1, 100).set(2, 100).set(3, 100)
    w.price = 1; w.see(0x8002); seen.add(w.run().ret)
    case("  两种情形下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
