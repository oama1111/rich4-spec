#!/usr/bin/env python3
"""用原版真码测「持股市值」的累加精度：证交税基数到底是 float32 还是 double 累加。

被测区块：`0x44a0c6`..`0x44a110`（事件表第 13 项 `0x44a029` 里的持股遍历循环）
```asm
0044a0c6  eax = player*0x60 + stock*8
0044a0dc  cmp dword [eax + 0x4971a0], 0      ; 持股为 0 跳过
0044a0e3  je  下一支
0044a0e5  fild dword [eax + 0x4971a0]        ; 持股数（int32，精确）
0044a0f9  fmul dword [stock*0x24 + 0x496994] ; × 现价（**float32**）
0044a100  fadd dword [esp + ebx*4 + 0x94]    ; 加进**float32** 累计槽
0044a107  fstp dword [esp + ebx*4 + 0x94]    ; ★ 每步都把累计值**存回 float32**
```
⇒ 每步都把运行中的合计数**舍入到 24 位尾数**。复刻用 JS 双精度累加，
   因此在这种"金额大 + 多支股票 + 现价带小数"的场景下会与原版差 1。

本脚本：驱原版循环 → 与两种模型对照 → 给出可直接复现的反例。
跑法：cd rich4-spec && .venv/bin/python tools/scratch/probe_stock_sum.py
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from emulate import Emu, STACK_TOP  # noqa: E402

LOOP, LOOP_STOP = 0x44A0C6, 0x44A110
HOLD_BASE, HOLD_PLAYER_STRIDE = 0x4971A0, 0x60
PRICE_BASE, PRICE_STRIDE = 0x496994, 0x24
SUM_LOCAL = 0x94          # [esp + ebx*4 + 0x94]
IDX_LOCAL = 0xA4          # [esp + 0xa4]
N_STOCKS = 12


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def original_sum(emu, player, holdings, prices):
    """驱原版循环，返回它落在 [esp+ebx*4+0x94] 的 **float32** 合计数。"""

    def setup(e):
        for i in range(N_STOCKS):
            e.write32(HOLD_BASE + player * HOLD_PLAYER_STRIDE + i * 8,
                      int(holdings[i]))
            e.write(PRICE_BASE + i * PRICE_STRIDE, struct.pack("<f", prices[i]))
        e.write32(STACK_TOP + IDX_LOCAL, 0)                 # 循环下标
        e.write(Sum_local_addr(player), struct.pack("<f", 0.0))   # 累计槽清零

    emu.eval_block(LOOP, LOOP_STOP, {"ebx": player}, setup=setup)
    raw = emu.read(Sum_local_addr(player), 4)
    return struct.unpack("<f", raw)[0]


def Sum_local_addr(player: int) -> int:
    return STACK_TOP + player * 4 + SUM_LOCAL


def model_f32(holdings, prices):
    """模型：每步 `t = f32(t + h*p)`（乘积在 53 位下算，只有**存回**是 float32）。"""
    t = 0.0
    for h, p in zip(holdings, prices):
        if h == 0:
            continue
        t = f32(t + h * p)
    return t


def model_f64(holdings, prices):
    """复刻现状：全程双精度。"""
    return sum(h * p for h, p in zip(holdings, prices) if h != 0) if False else \
        sum(h * p for h, p in zip(holdings, prices))


CASES = [
    # (说明, 持股 12 支, 现价 12 支)
    ("全 0", [0] * 12, [10.0] * 12),
    ("单支整数价", [1000] + [0] * 11, [12.0] + [0] * 11),
    ("单支小数价", [1000] + [0] * 11, [12.35] + [0] * 11),
    ("多支大额小数价",
     [6043, 1536, 5010, 7490, 8369, 7188, 1236, 1321, 6931, 0, 0, 0],
     [171.1004, 51.0515, 161.094, 261.2626, 245.384, 48.5834,
      168.2934, 148.6658, 252.661, 0, 0, 0]),
    ("四支大额",
     [3767, 3732, 9879, 3857] + [0] * 8,
     [15.6024, 297.313, 168.2229, 60.6896] + [0] * 8),
]


def main():
    emu = Emu()
    print("原版循环 vs 两种累加模型（合计数 = 证交税基数）\n")
    print(f"{'用例':<16}{'原版(float32累加)':>20}{'模型f32':>16}{'复刻f64':>18}"
          f"{'税(原版)':>10}{'税(f64)':>10}  判定")
    bad = 0
    for name, holds, prices in CASES:
        o = original_sum(emu, 0, holds, prices)
        m32 = model_f32(holds, prices)
        m64 = model_f64(holds, prices)
        t_o, t_64 = math.trunc(o * 0.05), math.trunc(m64 * 0.05)
        same_model = (o == m32)
        verdict = "一致" if t_o == t_64 else "★ 税差 1!"
        if t_o != t_64:
            bad += 1
        print(f"{name:<16}{o:>20.4f}{m32:>16.4f}{m64:>18.4f}"
              f"{t_o:>10}{t_64:>10}  {verdict}"
              f"{'' if same_model else '  ⚠模型与原版不符'}")
    print()
    print(f"★ 证交税差 1 的用例：{bad} / {len(CASES)}")
    print("结论：原版是 **float32 逐步累加**（每步 `fstp dword`），"
          "复刻的双精度累加会在这些用例上给出不同的税。")


if __name__ == "__main__":
    sys.exit(main())
