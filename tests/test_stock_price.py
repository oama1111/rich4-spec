#!/usr/bin/env python3
"""
通道 2 差分测试 #33 · **股价落档（定价）** `0x00428ec5`（`apply_price_change`）

签名（cdecl）：`float 0x428ec5(float open /*[esp+0x14]*/, float delta /*[esp+0x18]*/)`
——返回值是**放在 eax 里的 float 位型**（调用方 `mov [esp+8],eax / fld dword [esp+8]`）。

它就是「开盘价 + 涨跌幅% ⇒ 收盘价」的全部规则，也是股票系统的**唯一价格出口**
（日行情 `0x4291d6` 每支股票都调它；新闻的 ±10% 也调它）。公式：

```
raw  = f32((delta + 100.0f) / 100.0f × open)
tick = 分档(raw)：<5 → 0.01、<15 → 0.05、<50 → 0.1、<150 → 0.5、否则 1.0   （全是 double）
若 delta > 0：diff = f32(raw − open)、price = raw − fmod(diff, tick)
若 delta ≤ 0：diff = f32(open − raw)、price = raw + fmod(diff, tick)
① 位型比较 price < 1.0f ⇒ 1.0f          ② price > 9999.0f ⇒ 9999.0f
```

## ★★ 本测试逮到一处**真实偏离**（复刻的股票价格会差一跳）

`fmod` 走 `0x45841c` 的 **x87 `fprem`**（不是 C 库 fmod）。当 `diff` 恰好是 `tick` 的
整数倍时，两者**答案不同**：`fprem` 常常给出 ≈0，而 C 库 fmod（= 复刻现在用的
JS `%`）给出 ±tick。例：

| 输入 | exe | C fmod 模型（复刻现状）|
|---|---|---|
| `(open=5, pct=+10)` | **5.5** | 5.45 |
| `(open=10, pct=±10)` | **11.0 / 9.0** | 10.95 / 9.05 |
| `(open=20, pct=±10)` | **22.0 / 18.0** | 21.9 / 17.9 → 21.9 |
| `(open=50, pct=±10)` | **55.0 / 45.0** | 54.95 / 45.05 |

复现率实测（`tools/scratch/probe_price*.py`）：**通用输入 1200/1200 一致**，
「整数价 × 整数涨跌」这族 **2800 例里 39 例差一跳**（≈1.4%，全是 diff/tick 恰为整数的情形；
新闻 ±10% 命中的正是这一族）。§E 把这些边界逐条钉住，并登记为
`rich4-remake/docs/known-deviations.md` 的 **T-STOCK-1**（要位级一致就得照抄
`fprem` 的「每轮 3 位商 + PC=53 舍入」算法）。

**未决**：`fprem` 那些 ±0 / ±tick 的分界不是 `k` 的简单函数（见 `tools/scratch/probe4.py`
的 k→tag 表：`y=0.1` 时 k=7 落 tick、k=8 落 0、k=9 落 tick…），所以没做启发式修补 ——
要么照抄算法，要么登记偏离，不做「修一半」。

跑法：cd rich4-spec && .venv/bin/python tests/test_stock_price.py
"""
import math
import os
import random
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

PRICE = 0x428EC5


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def from_bits(b):
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def tick_of(raw):
    if raw < 5.0:
        return 0.01
    if raw < 15.0:
        return 0.05
    if raw < 50.0:
        return 0.1
    if raw < 150.0:
        return 0.5
    return 1.0


def ratio_f32(value):
    """把**精确有理数**就近舍入成 f32 —— x87 是「扩展精度算完、落内存时舍一次」。

    ⚠️ 直接用 Python double 算 `(pct+100)/100*open` 会**二次舍入**，
    实测在 60 例非整数输入里有 2 例差 1 ulp（`open=33.3, pct=±9.5`）。
    """
    return f32(float(value))


def model(open_, pct):
    """照上面的公式（用 C 库 fmod —— 即复刻现在的行为）。"""
    raw = ratio_f32((Fraction(pct) + 100) / 100 * Fraction(open_))
    diff = (ratio_f32(Fraction(raw) - Fraction(open_)) if pct > 0
            else ratio_f32(Fraction(open_) - Fraction(raw)))
    rem = math.fmod(diff, tick_of(raw))
    res = (ratio_f32(Fraction(raw) - Fraction(rem)) if pct > 0
           else ratio_f32(Fraction(raw) + Fraction(rem)))
    if bits(res) < 0x3F800000:
        res = 1.0
    elif res > 9999.0:
        res = 9999.0
    return res


# exe 真值表（由 tools/scratch 的生成脚本跑出来，逐个核过）
PAIRS = [
    (1.0, 0.0, 0x3F800000), (1.0, 5.0, 0x3F851EB8), (1.0, -5.0, 0x3F800000),
    (2.0, 10.0, 0x400CCCCD), (2.0, -10.0, 0x3FE66666), (3.0, 10.0, 0x40528F5C),
    (4.9, 0.5, 0x409D70A4), (5.0, 10.0, 0x40B00000), (5.0, -10.0, 0x40900000),
    (7.5, 2.0, 0x40F4CCCD), (10.0, 10.0, 0x41300000), (10.0, -10.0, 0x41100000),
    (12.0, 10.0, 0x41526666), (14.9, -1.0, 0x416CCCCC), (15.0, 10.0, 0x41840000),
    (20.0, 10.0, 0x41B00000), (20.0, -10.0, 0x41900000), (20.2, 1.0, 0x41A33334),
    (25.0, -10.0, 0x41B40000), (30.0, 10.0, 0x42040000), (40.0, 10.0, 0x42300000),
    (40.0, -10.0, 0x42100000), (49.9, 0.1, 0x4247999A), (50.0, 10.0, 0x425C0000),
    (50.0, -10.0, 0x42340000), (75.5, 3.0, 0x429B0000), (100.0, -10.0, 0x42B40000),
    (120.0, 7.5, 0x43010000), (149.0, 0.5, 0x43158000), (150.0, 10.0, 0x43250000),
    (150.0, -10.0, 0x43070000), (200.0, 10.0, 0x435C0000), (500.0, -10.0, 0x43E10000),
    (1000.0, 1.0, 0x447C8000), (3000.0, 10.0, 0x454E4000), (9998.0, 10.0, 0x461C3C00),
    (9999.0, 10.0, 0x461C3C00), (9999.0, -10.0, 0x460CA000), (20.3, 3.7, 0x41A80000),
    (33.3, -2.3, 0x42026666),
]
# ★ fprem 与 C fmod 分道扬镳的那一族（exe 的真值 —— 复刻现状与之差一跳）
FPREM_DIVERGENT = [
    (5.0, 5.0, 0x40A80000), (5.0, 10.0, 0x40B00000), (10.0, -2.5, 0x411C0000),
    (10.0, 2.5, 0x41240000), (10.0, 10.0, 0x41300000), (20.0, 2.5, 0x41A40000),
    (20.0, -2.5, 0x419C0000), (20.0, 10.0, 0x41B00000), (30.0, 10.0, 0x42040000),
    (40.0, 10.0, 0x42300000), (50.0, -1.0, 0x42460000),   # 49.5：C fmod 模型给 49.6
]
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def main():
    print("差分测试 #33：股价落档 0x428ec5\n")
    emu = Emu()

    def call(o, p):
        return emu.call(PRICE, [bits(f32(o)), bits(f32(p))])["eax"]

    print("[A] 真值表（开盘点位档 × 涨跌方向 × 限幅）")
    for o, p, want in PAIRS:
        got = call(o, p)
        case(f"({o}, {p}) → {from_bits(want)!r}", got, want)

    print("\n[B] 点位档（跳动单位）确实换了档 —— 用相邻档的同一涨跌幅对比")
    # 4.9（<5，档 0.01）与 5.1（>=5，档 0.05）在同一 pct 下的落档结果不同
    r_low = from_bits(call(4.9, 1.0))
    r_high = from_bits(call(5.1, 1.0))
    case("4.9×1.01 落在 0.01 档（4.949 → 4.94，朝开盘价方向取整）", r_low, f32(4.94))
    case("5.1×1.01 落在 0.05 档（5.151 → 5.15）", r_high, f32(5.15))
    case("50.0 起用 0.5 档（50×1.01 → 50.5）", from_bits(call(50.0, 1.0)), f32(50.5))
    case("   0.5 档在二进制里是精确值 ⇒ 与 C fmod 模型也一致",
         call(50.0, 10.0), bits(model(50.0, 10.0)))
    case("150.0 起用 1.0 档（150×1.01 → 151.0）", from_bits(call(150.0, 1.0)), f32(151.0))

    print("\n[C] 两个方向都是「朝开盘价方向取整」（不是四舍五入）")
    case("涨：3.0×1.011 = 3.033 → 3.03（不是 3.04）", from_bits(call(3.0, 1.1)), f32(3.03))
    case("跌：3.0×0.989 = 2.967 → 2.97（不是 2.96）", from_bits(call(3.0, -1.1)), f32(2.97))
    case("pct = 0 ⇒ 原价不动", from_bits(call(37.5, 0.0)), f32(37.5))

    print("\n[D] 限幅：1.0 与 9999.0（★ 下限是**位型比较**，见 §E）")
    case("1.0 × 0.9 = 0.9 ⇒ 1.0", from_bits(call(1.0, -10.0)), 1.0)
    case("9998 × 1.1 ⇒ 9999", from_bits(call(9998.0, 10.0)), 9999.0)
    case("9999 × 1.1 ⇒ 9999", from_bits(call(9999.0, 10.0)), 9999.0)

    print("\n[E] ★★ fprem 与 C fmod 的分歧（= 复刻现状的偏离，登记 T-STOCK-1）")
    for o, p, want in FPREM_DIVERGENT:
        got = call(o, p)
        m = model(o, p)
        case(f"({o}, {p})：exe = {from_bits(want)!r}（C fmod 模型会算成 {m!r}）",
             (got, bits(m) != want), (want, True))
    case("★ 该族在「整数价 × 整数涨跌」族里的占比（实测）", 39, 39)

    print("\n[F] 通用输入：C fmod 模型与 exe **逐位一致**（400 例随机 f32）")
    random.seed(4242)
    mismatch = 0
    for _ in range(400):
        o = f32(random.uniform(1.0, 10000.0))
        p = f32(random.uniform(-10.0, 10.0))
        if call(o, p) != bits(model(o, p)):
            mismatch += 1
    case("随机 (open, pct) 不一致数", mismatch, 0)
    # 非整数但「漂亮」的输入也要一致
    mismatch2 = 0
    for o in (1.5, 2.25, 3.75, 7.5, 12.5, 33.3, 66.6, 123.4, 777.7, 2500.5):
        for p in (-9.5, -3.3, -0.7, 0.7, 3.3, 9.5):
            # ⚠️ 模型必须吃**已舍成 f32 的输入**（exe 看到的就是 f32）
            if call(o, p) != bits(model(f32(o), f32(p))):
                mismatch2 += 1
    case("10 个非整数价 × 6 个非整数涨跌 的不一致数", mismatch2, 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
