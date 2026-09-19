#!/usr/bin/env python3
"""
通道 2 差分测试 #11 · `_rich4_sell_stock`（VA 0x00428e23，162 字节 / 47 条）

这是**股票卖出的唯一落地点**，四个调用方覆盖了三条不同的业务：
```asm
00428e30  eax = player*0x60 + stockIdx*8
00428e45  holdings -= amount                     ; [eax + 0x4971a0]
00428e53  if (holdings != 0) goto 算钱
00428e55  [eax + 0x4971a4] = 0                   ; ★ **恰好归零才**清成本均价
00428e6a  fild amount ; fmul dword [idx*0x24 + 0x496994]（现价 float32）
00428e75  call 0x457dbc（向零截断）; fistp [esp]
00428e7d  add word [idx*0x24 + 0x49698a], cx     ; ★ 成交量两份都 += amount
00428e85  add word [idx*0x24 + 0x496988], cx     ;   （只加 **cx** = 低 16 位）
00428e8d  if (arg4 == 0)
00428ea7      [0x499080] += 钱                  ;   进公库
00428e9c  else [player*0x68 + 0x496b88] += 钱    ;   进**玩家存款**
00428eb7  call 0x4294d5(stockIdx, player)        ;   更新控股/持股排名（本用例不验它）
```

| 调用方 | 场景 |
|---|---|
| `0x0042b0ad` | 股市场卖出 |
| `0x0042d033` | AI 卖股 |
| `0x0040d17b` | ★ **破产清算**（`arg4 = 0` ⇒ 钱进公库，不归玩家） |
| `0x0044c8fd` / `0x0044c9ec` | 機會/命運事件（事件 8/9） |

§7 另用 `0x00428d2a`（**买**）反向确认了同一对 u16 计数器是 `sub word` ⇒ 也会回绕
（买 300、原值 10 → 65246）。`0x428d2a` 的**其它**部分（認購定价、加权平均成本）
不在本文件范围，是另一条待测函数。

★ 本用例验到的**四条容易做错的**：
1. **恰好清零才清成本**（`holdings != 0` 就跳过 ⇒ 超卖成负数时成本**留着**）；
2. **超卖不夹**：`holdings` 会变成负数，函数不校验 —— 夹的任务在调用方；
3. 成交量两份计数器都加 `amount`，但走的是 **`cx`（低 16 位）**，会 **u16 回绕**；
4. 钱按**完整 amount** 算 ⇒ `amount = 65541` 时「成交量 +5、钱按 65541 算」。

跑法：cd rich4-spec && .venv/bin/python tests/test_sell_stock.py
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

SELL_STOCK = 0x428E23

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
BANK = 0x20
HOLD_BASE, HOLD_PLAYER_STRIDE = 0x4971A0, 0x60     # +0 持股、+4 成本均价
PRICE_BASE, STOCK_STRIDE = 0x496994, 0x24          # +0 现价（f32）
VOL_BASE, VOL_ALT = 0x496988, 0x49698A             # 两份 u16 成交量
POOL = 0x499080

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<52} 实际 {got_s!s:<16} 期望 {want_s!s}")
    return ok


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


class F:
    def __init__(self):
        self.emu = Emu()

    def sell(self, player, stock, amount, to_player, hold=1000, cost=15,
             price=20.0, vol=11, bank=5000, pool=0):
        def setup(emu):
            base = HOLD_BASE + player * HOLD_PLAYER_STRIDE + stock * 8
            emu.write32(base, hold)
            emu.write32(base + 4, cost)
            emu.write(PRICE_BASE + stock * STOCK_STRIDE, struct.pack("<f", price))
            emu.write16(VOL_BASE + stock * STOCK_STRIDE, vol & 0xFFFF)
            emu.write16(VOL_ALT + stock * STOCK_STRIDE, 0)
            emu.write32(PLAYER_BASE + player * PLAYER_STRIDE + BANK, bank)
            emu.write32(POOL, pool)

        self.emu.call(SELL_STOCK, [player, stock, amount, to_player], setup=setup)
        return {
            "hold": self.emu.read32(HOLD_BASE + player * HOLD_PLAYER_STRIDE + stock * 8),
            "cost": self.emu.read32(HOLD_BASE + player * HOLD_PLAYER_STRIDE + stock * 8 + 4),
            "bank": self.emu.read32(PLAYER_BASE + player * PLAYER_STRIDE + BANK),
            "pool": self.emu.read32(POOL),
            "vol": (self.emu.read16(VOL_BASE + stock * STOCK_STRIDE),
                    self.emu.read16(VOL_ALT + stock * STOCK_STRIDE)),
        }


def main():
    print("差分测试 #11：_rich4_sell_stock(VA 0x00428e23)\n")
    f = F()

    print("[1] 卖出落点：`arg4 != 0` 进玩家**存款**，`arg4 == 0` 进**公库**")
    r = f.sell(0, 0, 300, 1)
    case("卖 300/1000 股价 20 → 存款 +6000", r["bank"], 11000)
    case("  持股 1000 → 700", r["hold"], 700)
    case("  公库不动", r["pool"], 0)
    r = f.sell(0, 0, 300, 0)
    case("arg4=0（破产清算那支）→ 公库 +6000，存款不动", (r["pool"], r["bank"]), (6000, 5000))

    print("\n[2] ★ 成本均价只在**恰好归零**时清")
    r = f.sell(0, 0, 1000, 1, hold=1000, cost=15)
    case("全部卖出 → 持股 0、成本也清 0", (r["hold"], r["cost"]), (0, 0))
    r = f.sell(0, 0, 1500, 1, hold=1000, cost=15)
    case("★ 超卖 1500 → 持股 **-500**（不夹）、成本**留着**", (r["hold"], r["cost"]), (-500, 15))
    r = f.sell(0, 0, 999, 1, hold=1000, cost=15)
    case("卖 999 → 剩 1、成本不动", (r["hold"], r["cost"]), (1, 15))
    # 第二次把它清掉（测试自己扮演记忆：把上一次结果当输入）
    r = f.sell(0, 0, 1, 1, hold=r["hold"], cost=r["cost"])
    case("  再卖 1 → 归零并清成本", (r["hold"], r["cost"]), (0, 0))

    print("\n[3] 成交量两份计数器都 += amount（各股独立）")
    r = f.sell(0, 0, 300, 1, vol=11)
    case("vol0 11 → 311、vol1 0 → 300", r["vol"], (311, 300))
    r = f.sell(0, 3, 300, 1, vol=11)
    case("换一支股票（下标 3）同样成立", r["vol"], (311, 300))
    r = f.sell(0, 0, 300, 1, vol=65530)
    case("★ u16 回绕：65530 + 300 → 294", r["vol"][0], 294)

    print("\n[4] ★★ 钱按完整 amount 算，但计数器只加低 16 位（`add ..., cx`）")
    r = f.sell(0, 0, 65541, 1, hold=100000, price=1.0)
    case("amount=65541 → 存款 +65541（完整值）", r["bank"] - 5000, 65541)
    case("  但 vol0 只 +5（`cx` = 0x0005）", r["vol"][0], 16)
    case("  vol1 同样只 +5", r["vol"][1], 5)
    case("  持股 -65541", r["hold"], 34459)

    print("\n[5] 价格是 **float32** + 向零截断")
    case("1000 股 × 0.1 → 100", f.sell(0, 0, 1000, 1, price=0.1)["bank"] - 5000, 100)
    case("3 股 × 12.35（f32）→ trunc(37.05) = 37",
         f.sell(0, 0, 3, 1, price=12.35)["bank"] - 5000,
         math.trunc(3 * f32(12.35)))
    case("7 股 × 2.5 → trunc(17.5) = 17（不是 18）",
         f.sell(0, 0, 7, 1, price=2.5)["bank"] - 5000, 17)
    case("100 股 × 1234.56（f32）→ 精确模型一致",
         f.sell(0, 0, 100, 1, price=1234.56)["bank"] - 5000,
         math.trunc(100 * f32(1234.56)))

    print("\n[6] 玩家/股票下标互不串味")
    r = f.sell(2, 5, 300, 1, hold=1000, cost=15, price=20.0)
    case("玩家 2 / 股票 5 → 只动那一格", (r["hold"], r["bank"]), (700, 11000))
    case("  别的玩家格子没被碰",
         f.emu.read32(HOLD_BASE + 0 * HOLD_PLAYER_STRIDE + 0 * 8), 0)
    case("  别的股票格子没被碰",
         f.emu.read16(VOL_BASE + 0 * STOCK_STRIDE), 0)

    print("\n[7] 反向确认：**买**的那一支（`0x428d2a`）同样按 u16 回绕")
    # 只验「计数器」这一格；`0x428d2a` 的認購定价/加权成本是另一条待测函数。
    def buy(stock=0, amount=300, shares=10, f10=10, price=1.0):
        def setup(emu):
            base = HOLD_BASE + 0 * HOLD_PLAYER_STRIDE + stock * 8
            emu.write32(base, 0)
            emu.write32(base + 4, 0)
            emu.write(PRICE_BASE + stock * STOCK_STRIDE, struct.pack("<f", price))
            emu.write16(VOL_BASE + stock * STOCK_STRIDE, shares & 0xFFFF)
            emu.write16(VOL_ALT + stock * STOCK_STRIDE, f10 & 0xFFFF)
            emu.write32(PLAYER_BASE + BANK, 10 ** 9)
            emu.write32(PLAYER_BASE + 0x1C, 10 ** 9)
        f.emu.call(0x428D2A, [0, stock, amount, 1], setup=setup)
        return (f.emu.read16(VOL_BASE + stock * STOCK_STRIDE),
                f.emu.read16(VOL_ALT + stock * STOCK_STRIDE))

    case("买 300 股、计数器原值 10 → 10-300 回绕成 65246（两份都是）",
         buy(), (65246, 65246))
    case("买 3 股、计数器 10 → 7（正常减法）", buy(amount=3), (7, 7))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
