#!/usr/bin/env python3
"""
通道 2 差分测试 #58 · **道具「给出 / 收走」这一对**（`0x445a4d` / `0x445aa2`）

原版把玩家道具与**全局库存**分成两张表，给/收是**对称**的一对：

```asm
; @source 0x00445a4d  receive_tool(player, toolId)   ← 收进一个
00445a4e  edx = [esp+0xc]                  ; arg2 = 道具编号
00445a52  ecx = [esp+8]                    ; arg1 = 玩家下标
00445a58  eax = (ecx*4 + ecx) * 4 - ecx*5  ; ★ = 玩家*15（每玩家 15 个槽）
00445a64  cmp byte [edx + eax + 0x49915b], 9
00445a6c  jae 0x445aa0                     ; ★ 已有 9 个 ⇒ 收不下，**什么都不做**
00445a71  cmp edx, 8 / jg 0x445a87         ; ★ 编号 > 8 的**不查库存**
00445a73  bh = byte [edx + 0x49731f]       ; 该编号的库存
00445a7b  je 0x445aa0                      ; ★ 库存为 0 ⇒ 也什么都不做
00445a81  byte [edx + 0x49731f] = bh - 1   ; 库存 −1
00445a99  inc byte [edx + eax + 0x49915b]  ; ★ 持有量 +1
00445aa0  ret

; @source 0x00445aa2  after_player_use_tool(player, toolId)   ← 收走一个（与上面完全对称）
00445aaa  eax = 玩家*15
00445aba  dl = byte [eax + 0x49915b]
00445ac2  je 0x445ad9                      ; ★ 没有 ⇒ 什么都不做
00445ac8  byte [eax + 0x49915b] = dl - 1   ; 持有量 −1
00445ace  cmp ecx, 8 / jg 0x445ad9
00445ad3  inc byte [ecx + 0x49731f]        ; ★ **把库存还回去**（编号 ≤ 8）
00445ad9  ret
```

★ 三条要点（全部实测）：

| # | 事实 | 对应复刻 |
|---|---|---|
| 1 | 持有上限 **9**（`cmp …,9 / jae`）—— 第 10 个收不下 | `giveTool` 的 `MAX_TOOL_COUNT` |
| 2 | ★ 编号 **> 8** 的道具**不查库存、也不还库存**（9..13 实际无限量） | `toolId <= STOCKED_TOOL_MAX_ID(8)` |
| 3 | ★★ 收走时**把库存还回去** ⇒ 搶奪卡「从 A 转到 B」的净额不变 | `takeTool` 的 `nextStock[toolId] += 1` |

## 打桩

无（两支都是纯读写，不调外部函数）。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_give_take.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

GIVE = 0x445A4D            # _rich4_receive_tool(player, toolId)
TAKE = 0x445AA2            # _rich4_after_player_use_tool(player, toolId)
TOOLS_BASE = 0x49915B      # 玩家道具（每玩家 15 槽）
TOOL_STRIDE = 15
STOCK_BASE = 0x49731F      # 全局库存（按编号，byte）
STOCKED_MAX = 8            # 编号 ≤ 8 才查/还库存
MAX_TOOL_COUNT = 9         # 持有上限
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<22} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def run(self, fn, player, tool, *, have=None, stock=None):
        """`have[player][tool]` 与 `stock[tool]` 由调用方给；返回 (持有量, 库存)。"""
        emu = Emu()
        have_d = {} if have is None else dict(have)
        stock_d = {} if stock is None else dict(stock)

        def setup(e):
            for (p, t), v in have_d.items():
                e.write8(TOOLS_BASE + p * TOOL_STRIDE + t, v)
            for t, v in stock_d.items():
                e.write8(STOCK_BASE + t, v)
        emu.call(fn, [player, tool], setup=setup, timeout_insns=200000)
        self.emu = emu
        return self

    def have(self, player, tool):
        return self.emu.read8(TOOLS_BASE + player * TOOL_STRIDE + tool)

    def stock(self, tool):
        return self.emu.read8(STOCK_BASE + tool)


def main():
    print("差分测试 #58：道具「给出 / 收走」一对 0x445a4d / 0x445aa2\n")

    print("[A] 给出：正常一进一出")
    f = F().run(GIVE, 0, 3, have={(0, 3): 0}, stock={3: 5})
    case("持有 0→1", f.have(0, 3), 1)
    case("库存 5→4", f.stock(3), 4)

    print("\n[B] ★ 持有上限 9：第 10 个收不下")
    f = F().run(GIVE, 0, 3, have={(0, 3): 8}, stock={3: 5})
    case("持有 8→9", f.have(0, 3), 9)
    case("库存 5→4（这次仍成功）", f.stock(3), 4)
    f = F().run(GIVE, 0, 3, have={(0, 3): 9}, stock={3: 5})
    case("★ 持有 9 ⇒ **持有与库存都不动**", (f.have(0, 3), f.stock(3)), (9, 5))

    print("\n[C] ★ 编号 ≤ 8：库存为 0 时收不下（且**不扣持有**）")
    f = F().run(GIVE, 0, 8, have={(0, 8): 0}, stock={8: 0})
    case("库存 0 ⇒ 持有仍 0、库存仍 0", (f.have(0, 8), f.stock(8)), (0, 0))
    f = F().run(GIVE, 0, 1, have={(0, 1): 0}, stock={1: 1})
    case("库存 1 ⇒ 成功（持有 1、库存 0）", (f.have(0, 1), f.stock(1)), (1, 0))

    print("\n[D] ★★ 编号 > 8（9..13）**不查库存**：库存 0 也能收")
    for tool in (9, 10, 11, 12, 13):
        f = F().run(GIVE, 0, tool, have={(0, tool): 0}, stock={tool: 0})
        case(f"编号 {tool} + 库存 0 ⇒ 持有变 1、库存**不动**",
             (f.have(0, tool), f.stock(tool)), (1, 0))

    print("\n[E] 收走：把库存**还回去**（编号 ≤ 8）")
    f = F().run(TAKE, 0, 3, have={(0, 3): 1}, stock={3: 4})
    case("持有 1→0", f.have(0, 3), 0)
    case("★ 库存 4→5（还回去）", f.stock(3), 5)
    f = F().run(TAKE, 0, 8, have={(0, 8): 3}, stock={8: 0})
    case("编号 8、持有 3 ⇒ 持有 2、库存 0→1", (f.have(0, 8), f.stock(8)), (2, 1))

    print("\n[F] 收走：持有为 0 ⇒ 什么都不做（库存也不动）")
    f = F().run(TAKE, 0, 3, have={(0, 3): 0}, stock={3: 4})
    case("持有 0 ⇒ (0, 4) 原样", (f.have(0, 3), f.stock(3)), (0, 4))

    print("\n[G] ★★ 编号 > 8 收走时**不还库存**")
    for tool in (9, 10, 13):
        f = F().run(TAKE, 0, tool, have={(0, tool): 2}, stock={tool: 0})
        case(f"编号 {tool} 收走 ⇒ 持有 2→1、库存**不动**",
             (f.have(0, tool), f.stock(tool)), (1, 0))

    print("\n[H] ★ 玩家下标步长 = 15（两人互不干扰）")
    f = F().run(GIVE, 1, 3, have={(0, 3): 7, (1, 3): 0}, stock={3: 5})
    case("玩家 1 收 ⇒ 玩家 0 的 7 不动", f.have(0, 3), 7)
    case("玩家 1 的变 1", f.have(1, 3), 1)
    f = F().run(TAKE, 1, 3, have={(0, 3): 7, (1, 3): 1}, stock={3: 5})
    case("玩家 1 交还 ⇒ 玩家 0 的 7 仍不动", f.have(0, 3), 7)

    print("\n[I] ★ 一进一出净额不变（搶奪卡的语义）")
    #   A 持 1、B 持 0；把 A 的收走（库存+1）再给 B（库存−1）⇒ 库存回到原值
    f = F().run(TAKE, 0, 5, have={(0, 5): 1, (1, 5): 0}, stock={5: 2})
    case("第一步：A 交还 ⇒ 库存 2→3", (f.have(0, 5), f.stock(5)), (0, 3))
    f2 = F().run(GIVE, 1, 5, have={(0, 5): 0, (1, 5): 0}, stock={5: 3})
    case("第二步：B 收下 ⇒ 库存 3→2（**净额回到 2**）",
         (f2.have(1, 5), f2.stock(5)), (1, 2))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
