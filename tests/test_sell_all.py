#!/usr/bin/env python3
"""
通道 2 差分测试 #38 · **变卖全部道具 / 全部手牌** `0x445b3f` / `0x441f21`

这两个函数是**一对**（原版总连着调）：命运事件 32「變賣所有卡片道具」、
破产清算、財神/魔法屋的没收分支都调用它们。返回值是**變賣所得點券**，
调用方 `add word [player+0x30], ax`（16 位加）。

```asm
; @source 0x445b3f _rich4_player_sell_all_tools(player)
00445b49  dl = player[+0x11]                        ; traffic_method（0x496b79）
00445b51  if (dl == 0) goto 卖道具                    ; ★ 走路就整体跳过（连清零也不做）
00445b55  bl = dl & 3
00445b66  bl == 1 → add byte [15p + 0x499160], bl   ; ★ 座驾折回**道具 5 機車**（+1）
00445b81  bl == 2 → inc byte [15p + 0x499161]       ; 道具 6 汽車
00445b89  bl == 3 → inc byte [15p + 0x499167]       ; ★ 道具 **12 工程車**（0x1f & 3 == 3）
00445b92  player[+0x11] = 0 ; player[+0x12] = 1     ; 下车、骰子回 1
00445ba2  call 0x40b93b(player)                     ; 重绘（纯表现）
00445bb0  for (i = 0; i < 13; i++) {                ; 道具 1..13
            cl = byte [15p + i + 0x49915c]          ; 持有量
            if (cl == 0) continue
            if (i < 8) byte [i + 0x497320] += cl    ; ★ 编号 ≤ 8 才回**商店库存**
            ebx += byte [i*8 + 0x47fee7] * cl       ; 道具表 +5 = 售价（**原价**）
            byte [15p + i + 0x49915c] = 0           ; ★★ **清零**
          }
00445c0e  return ebx

; @source 0x441f21 _rich4_player_sell_all_the_card(player)
00441f33  for (ecx = 0; ecx < 15; ecx++) {          ; 15 个手牌槽（槽里存**卡号**）
            dl = byte [15p + ecx + 0x499120]
            if (dl == 0) continue
            inc byte [dl + 0x499197]                ; 卡片回商店库存（按卡号索引）
            ebx += byte [dl*8 + 0x47fdef]           ; 卡表 +5 = 售价
            byte [15p + ecx + 0x499120] = 0
          }
00441ec9  return ebx
```

## ★ 本轮钉住的两件事

1. **PRD 里那条「未决」有答案了**（`fortune.md` §…：「`0x445b3f` / `0x441f21` 是否
   **顺带清空**玩家的道具/卡片」）—— **会清空**：道具那支把 13 个槽逐个写 0
   （`0x445c05`），卡片那支把 15 个槽逐个写 0（`0x441f6b`）。没有「只算价不清空」的分支。
2. **售价就是原价**（道具表 `+5` / 卡表 `+5`），**不看物价指数、不打折**；
   道具编号 ≤ 8 的回 **商店库存**（`0x497320 + i`），9..13 **不回**（本就不限量）；
   卡片**全都回**商店库存（`0x499197 + 卡号`）。

## 数组边界（A 级结构佐证，本测试顺带断言）

```
手牌槽   0x499120 + 15*玩家 + 槽(0..14)      4 玩家 × 15 = 60 B → 到 0x49915b
道具持有 0x49915c + 15*玩家 + (道具-1)        4 玩家 × 15 = 60 B → 到 0x499197
卡片库存 0x499197 + 卡号(1..30)              30 B
商店库存 0x497320 + (道具-1)                 只覆盖道具 1..8
```
⇒ `0x499120 + 60 == 0x49915c`、`0x49915c + 60 == 0x499198 == 0x499197 + 1`
（两处首尾相接，与 `tools.md` §3.1 / `cards.md` 的表边界一致）。

## 打桩

| VA | 原用途 | 桩 |
|---|---|---|
| `0x40b93b` | 玩家重绘（下车后刷新棋子）| 计数 + `ret` |

跑法：cd rich4-spec && .venv/bin/python tests/test_sell_all.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

SELL_TOOLS, SELL_CARDS = 0x445B3F, 0x441F21
REDRAW = 0x40B93B

PLAYER_BASE, STRIDE = 0x496B68, 0x68
TRAFFIC, NDICES = 0x11, 0x12          # player + 0x11 / +0x12
CARDS_BASE, TOOLS_BASE = 0x499120, 0x49915C
CARD_STOCK, TOOL_STOCK = 0x499197, 0x497320
TOOL_PRICE, CARD_PRICE = 0x47FEE7, 0x47FDEF
SLOT_PER_PLAYER = 15
TOOL_COUNT, CARD_SLOTS, CARD_STOCK_MAX = 13, 15, 30

C_REDRAW = SCRATCH_BASE + 0x900
RESULTS = []

# 道具表 +5（售价）：`tools.md` §1.2 的 A 级表
TOOL_PRICES = [15, 30, 25, 25, 80, 150, 100, 30, 30, 40, 95, 150, 250]
# 卡片表 +5（售价）：`cards.md` §1.1.5 的 A 级表（30 张）
CARD_PRICES = [200, 200, 35, 25, 20, 20, 15, 20, 160, 180, 60, 15, 25, 20, 100,
               25, 20, 20, 40, 25, 25, 10, 20, 50, 30, 35, 35, 35, 40, 70]


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got!s:<16} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(REDRAW, b"\xFF\x05" + struct.pack("<I", C_REDRAW) + b"\xC3")

    def run_tools(self, player=0, *, traffic=0, tools=None, stock=None):
        """调 `0x445b3f(player)`；`tools` = {道具号: 数量}、`stock` = {道具号: 数量}"""
        def setup(emu):
            emu.write32(C_REDRAW, 0)
            emu.write(TOOLS_BASE, b"\x00" * (4 * SLOT_PER_PLAYER))
            emu.write(TOOL_STOCK, b"\x00" * 8)
            # 库存表只有 8 格（道具 1..8）；`+8` 之后是别的全局量 —— 放个哨兵，
            # 证明「编号 ≥ 9 不回库存」不是靠数组越界写出来的
            emu.write8(TOOL_STOCK + 8, 0x5A)
            for p in range(4):
                emu.write8(PLAYER_BASE + p * STRIDE + TRAFFIC, traffic if p == player else 0)
                emu.write8(PLAYER_BASE + p * STRIDE + NDICES, 7)
            # 玩家 p 的道具：`0x49915c + 15p + (道具-1)`
            for pid, n in (tools or {}).items():
                emu.write8(TOOLS_BASE + player * SLOT_PER_PLAYER + pid - 1, n)
            for pid, n in (stock or {}).items():
                emu.write8(TOOL_STOCK + pid - 1, n)
            # 邻居（玩家 1）放一件，确认卖玩家 0 不动别人
            emu.write8(TOOLS_BASE + 1 * SLOT_PER_PLAYER + 0, 5)

        r = self.emu.call(SELL_TOOLS, [player], setup=setup)
        e = self.emu
        base = TOOLS_BASE + player * SLOT_PER_PLAYER
        return {
            "ret": r["eax"],
            "slots": [e.read8(base + i) for i in range(TOOL_COUNT)],
            "stock": [e.read8(TOOL_STOCK + i) for i in range(8)],
            "canary": e.read8(TOOL_STOCK + 8),
            "neighbor": e.read8(TOOLS_BASE + 1 * SLOT_PER_PLAYER + 0),
            "traffic": e.read8(PLAYER_BASE + player * STRIDE + TRAFFIC),
            "ndices": e.read8(PLAYER_BASE + player * STRIDE + NDICES),
            "redraw": e.readu32(C_REDRAW),
        }

    def run_cards(self, player=0, *, slots=None, stock=None):
        """调 `0x441f21(player)`；`slots` = {槽(0..14): 卡号}"""
        def setup(emu):
            emu.write(CARDS_BASE, b"\x00" * (4 * SLOT_PER_PLAYER))
            emu.write(CARD_STOCK, b"\x00" * (CARD_STOCK_MAX + 8))
            for slot, card in (slots or {}).items():
                emu.write8(CARDS_BASE + player * SLOT_PER_PLAYER + slot, card)
            for cid, n in (stock or {}).items():
                emu.write8(CARD_STOCK + cid, n)
            emu.write8(CARDS_BASE + 1 * SLOT_PER_PLAYER + 0, 7)   # 邻居的牌

        r = self.emu.call(SELL_CARDS, [player], setup=setup)
        e = self.emu
        base = CARDS_BASE + player * SLOT_PER_PLAYER
        return {
            "ret": r["eax"],
            "slots": [e.read8(base + i) for i in range(CARD_SLOTS)],
            "stock": [e.read8(CARD_STOCK + c) for c in range(1, CARD_STOCK_MAX + 1)],
            "neighbor": e.read8(CARDS_BASE + 1 * SLOT_PER_PLAYER + 0),
        }


def main():
    print("差分测试 #38：变卖全部道具 `0x445b3f` / 全部手牌 `0x441f21`\n")
    f = F()

    print("[0] 通道 1：两张售价表（表项 +5）")
    prices = [f.emu.read8(TOOL_PRICE + t * 8) for t in range(TOOL_COUNT)]
    case("★ 道具售价表 `0x47fee7 + 8t` == tools.md §1.2", prices, TOOL_PRICES)
    cprices = [f.emu.read8(CARD_PRICE + c * 8) for c in range(1, CARD_STOCK_MAX + 1)]
    case("★ 卡片售价表 `0x47fdef + 8c` == cards.md §1.1.5", cprices, CARD_PRICES)
    case("★ 数组首尾相接：手牌槽 60B 之后正好是道具持有表",
         (CARDS_BASE + 4 * SLOT_PER_PLAYER, TOOLS_BASE), (TOOLS_BASE, TOOLS_BASE))
    case("★ 道具持有表 60B 之后正好是卡片库存（0x499197+1）",
         TOOLS_BASE + 4 * SLOT_PER_PLAYER, CARD_STOCK + 1)

    print("\n[A] `0x445b3f` 变形一：走路（traffic = 0）")
    s = f.run_tools(0, traffic=0)
    case("★ 空手 ⇒ 返回 0", s["ret"], 0)
    case("★ 走路 ⇒ **不重绘**（`dl == 0` 整块跳过，连清零都不做）",
         (s["redraw"], s["traffic"], s["ndices"]), (0, 0, 7))
    s = f.run_tools(0, traffic=0, tools={2: 3, 9: 2, 13: 1})
    case("★ 有道具、没座驾 ⇒ 返回 30×3 + 30×2 + 250×1 = 400", s["ret"], 400)
    case("★★ **清空**：13 个槽全变 0（PRD 的「未决」答案）", s["slots"], [0] * 13)
    case("   编号 2 回商店库存 +3", s["stock"][1], 3)
    case("★ 编号 ≥ 9 **不回**库存 ⇒ 库存表后面那格哨兵没被碰", s["canary"], 0x5A)
    case("   别人（玩家 1）的道具没被碰", s["neighbor"], 5)
    case("   不变座驾/骰子（本就没座驾）", (s["traffic"], s["ndices"]), (0, 7))

    print("\n[B] `0x445b3f` 变形二：座驾折回道具（**先折再卖**）")
    for traffic, tid, price in ((1, 5, 80), (2, 6, 150), (3, 12, 150)):
        s = f.run_tools(0, traffic=traffic)
        case(f"★ traffic={traffic} ⇒ 折成道具 {tid} 又立刻卖掉：返回 {price}",
             (s["ret"], s["slots"][tid - 1]), (price, 0))
        stock_ok = s["canary"] == 0x5A if tid > 8 else s["stock"][tid - 1] == 1
        case(f"   道具 {tid} {'回' if tid <= 8 else '不回'}商店库存",
             (stock_ok, s["traffic"], s["ndices"], s["redraw"]), (True, 0, 1, 1))
    s = f.run_tools(0, traffic=0x1F)
    case("★ traffic = 0x1f（工程車）⇒ `& 3 == 3` ⇒ 道具 12（150 點）",
         (s["ret"], s["traffic"], s["ndices"]), (150, 0, 1))
    s = f.run_tools(0, traffic=4)
    case("★ traffic = 4（`& 3 == 0`）⇒ 没有对应道具，只下车",
         (s["ret"], s["traffic"], s["ndices"], s["redraw"]), (0, 0, 1, 1))
    case("   四个槽都干净", s["slots"], [0] * 13)

    print("\n[C] `0x445b3f` 变形三：满仓求和 + 16 位口径")
    s = f.run_tools(0, tools={1: 2, 2: 1, 8: 3, 9: 1, 13: 255})
    want = 15 * 2 + 30 * 1 + 30 * 3 + 30 * 1 + 250 * 255
    case(f"★ 返回 Σ 售价×数量 = {want}", s["ret"], want)
    case("   库存：道具 1 +2、2 +1、8 +3", (s["stock"][0], s["stock"][1], s["stock"][7]),
         (2, 1, 3))
    case("   9 / 13 不回库存（哨兵仍在）", s["canary"], 0x5A)
    case("   30 号槽（不存在）不动", f.emu.read8(TOOLS_BASE + 14), 0)
    s = f.run_tools(3, traffic=1, tools={5: 9, 13: 9})
    case("★ 玩家 3：座驾折成道具 5（9+1=10）再卖 ⇒ 80×10 + 250×9 = 3050",
         s["ret"], 80 * 10 + 250 * 9)
    case("   玩家 3 的道具槽按 15 步长寻址、全清", s["slots"], [0] * 13)
    case("   玩家 3 走的是 `0x49915c + 45`，玩家 1 不受影响", s["neighbor"], 5)

    print("\n[D] `0x441f21` 变卖全部手牌")
    s = f.run_cards(0, slots={0: 1, 3: 5, 14: 30})
    want = CARD_PRICES[0] + CARD_PRICES[4] + CARD_PRICES[29]
    case(f"★ 三张牌 ⇒ 返回 {want}（均富 200 + 換屋 20 + 烏龜 70）", s["ret"], want)
    case("★★ **清空**：15 个槽全变 0（PRD 的「未决」答案）", s["slots"], [0] * CARD_SLOTS)
    case("   卡片回商店库存（按卡号索引）",
         (s["stock"][0], s["stock"][4], s["stock"][29]), (1, 1, 1))
    case("   别人（玩家 1）的牌没被碰", s["neighbor"], 7)
    s = f.run_cards(0, slots={0: 12, 1: 12})
    case("★ 同一张牌占两个槽 ⇒ 算两次（逐槽，不按去重）",
         (s["ret"], s["stock"][11]), (15 * 2, 2))
    s = f.run_cards(2, slots={5: 24})
    case("★ 玩家 2：按 15 步长寻址 ⇒ 返回 50（紅卡）", s["ret"], CARD_PRICES[23])
    case("   空手 ⇒ 0", f.run_cards(0)["ret"], 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
