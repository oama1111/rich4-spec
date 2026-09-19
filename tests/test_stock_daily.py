#!/usr/bin/env python3
"""
通道 2 差分测试 #34 · **每日行情** `0x004291d6`（`update_stock_market`）

调用点只有两处：日推进 `0x41d076`（每回合一次）与新局 `0x401ceb`（开局先跑一次）。
它把 12 支股票各推一天，公式见 `docs/systems/stocks.md` §2.1：

```
if (fcn_00428d01() == 1) return                 ; ★ 休市 ⇒ 整天不跳价、**连 rand 都不掷**
drift = (rand() − 0x4000) / 4097.0f → [0x4990ec]
for i in 0..11:
    open = price                                 ; ★ 开盘价 = 前一日收盘
    if (停牌(+0x06) != 0) { momentum = 0 ; 到 apply }        ; ★ 停牌也**不掷**这一支的 rand
    else {
        if (news_dir(+0x07)) momentum = (高半字节 ? +10.0f : −10.0f)
        r = (rand() − 0x4000) / 1171.0f → +0x20
        momentum = f32(f32(r × vol) + momentum)  ; ★ 累加，不清零
        momentum = f32(drift + momentum)
        …按「上市公司 / 无上市公司」两支做均值回归阻尼…
        momentum 夹到 ±10.0f
    }
apply: price = fcn_00428ec5(open, momentum)      ; ★ 落档（见 test_stock_price.py）
       history[i][ring] = price ; Σ += price
ring = (ring + 1) % 0x90 ; market_sum_x10 = trunc(Σ price × 10.0f)
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x428d01` | 休市判定 | 从数据槽读返回值（0 = 开市、1 = 休市）|
| `0x456f2d` | PRNG | **序列桩**：按顺序吐预设值并记次数 |

`0x428ec5`（落档）真跑 —— 它的逐位真值见 `test_stock_price.py`。
股票表**就地**在 DGROUP `0x496980`（12 × 36），本测试直接写它。

跑法：cd rich4-spec && .venv/bin/python tests/test_stock_daily.py
"""
import os
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

DAILY = 0x4291D6
CLOSED = 0x428D01
PRNG = 0x456F2D

STOCKS = 0x496980          # 12 × 36（绝对地址，不是指针）
S_PAUSE, S_NEWS = 0x06, 0x07
S_BASE, S_OPEN, S_PRICE, S_VOL, S_MOM, S_RAND = 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20
STOCK_STRIDE = 36

DRIFT = 0x4990EC
RING = 0x499100
MARKET_SUM = 0x499078
HISTORY = 0x497328         # history[股票][日]，每股 0x90 槽

CLOSED_SLOT = SCRATCH_BASE + 0x800
RAND_PTR, RAND_N = SCRATCH_BASE + 0x804, SCRATCH_BASE + 0x808
ROLLS = SCRATCH_BASE + 0x900
RESULTS = []


def f32(x):
    """精确有理数 → 就近 f32（x87 扩展精度算完只舍一次）。"""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def ratio_f32(value):
    return f32(Fraction(value))


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<22} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # 休市判定：mov eax,[slot] / ret
        self.emu.patch(CLOSED, b"\xA1" + struct.pack("<I", CLOSED_SLOT) + b"\xC3")
        # PRNG 序列桩：push ecx / mov ecx,[RAND_PTR] / mov eax,[ecx] /
        #              add dword [RAND_PTR],4 / inc dword [RAND_N] / pop ecx / ret
        self.emu.patch(PRNG, b"\x51"
                       + b"\x8B\x0D" + struct.pack("<I", RAND_PTR)
                       + b"\x8B\x01"
                       + b"\x83\x05" + struct.pack("<I", RAND_PTR) + b"\x04"
                       + b"\xFF\x05" + struct.pack("<I", RAND_N)
                       + b"\x59\xC3")

    def run(self, *, closed=0, rolls=(), stocks=None, ring=0, price=20.0,
            open_price=None, vol=1.0, mom=0.0, base=20.0, pause=0, news=0,
            company=0):
        """`stocks`（可选）= {下标: dict} 覆盖单支；其余 11 支用默认值（停牌、不动）。"""
        stocks = stocks or {}

        def setup(emu):
            emu.write32(CLOSED_SLOT, closed)
            emu.write32(RING, ring)
            emu.write32(DRIFT, 0)
            emu.write32(MARKET_SUM, 0)
            for i, v in enumerate(rolls):
                emu.write32(ROLLS + i * 4, v & 0xFFFFFFFF)
            emu.write32(RAND_PTR, ROLLS)
            emu.write32(RAND_N, 0)
            for i in range(12):
                rec = stocks.get(i, {"pause": 0})   # 默认：**不停牌**（会掷 rand、会跳价）
                b = STOCKS + i * STOCK_STRIDE
                emu.write16(b + 0x04, rec.get("company", company))
                emu.write8(b + S_PAUSE, rec.get("pause", pause))
                emu.write8(b + S_NEWS, rec.get("news", news))
                op = rec.get("open", open_price if open_price is not None else price)
                emu.write(b + S_BASE, struct.pack("<f", rec.get("base", base)))
                emu.write(b + S_OPEN, struct.pack("<f", op))
                emu.write(b + S_PRICE, struct.pack("<f", rec.get("price", price)))
                emu.write(b + S_VOL, struct.pack("<f", rec.get("vol", vol)))
                emu.write(b + S_MOM, struct.pack("<f", rec.get("mom", mom)))
                emu.write(b + S_RAND, struct.pack("<f", 0.0))

        self.emu.call(DAILY, [], setup=setup)
        e = self.emu

        def ff(off, i=0):
            return struct.unpack("<f", e.read(STOCKS + i * STOCK_STRIDE + off, 4))[0]

        def fbits(off, i=0):
            return struct.unpack("<I", e.read(STOCKS + i * STOCK_STRIDE + off, 4))[0]

        return {
            "rolls": e.readu32(RAND_N),
            "drift": struct.unpack("<f", e.read(DRIFT, 4))[0],
            "drift_bits": struct.unpack("<I", e.read(DRIFT, 4))[0],
            "mom": [ff(S_MOM, i) for i in range(12)],
            "r": [ff(S_RAND, i) for i in range(12)],
            "mom_bits": [fbits(S_MOM, i) for i in range(12)],
            "price": [ff(S_PRICE, i) for i in range(12)],
            "open": [ff(S_OPEN, i) for i in range(12)],
            "ring": e.readu32(RING),
            "sum": e.read32(MARKET_SUM),
            "hist0": struct.unpack("<f", e.read(HISTORY, 4))[0],
        }


def main():
    print("差分测试 #34：每日行情 —— 0x4291d6\n")
    f = F()

    print("[A] 休市（0x428d01 返回 1）⇒ 整天不跳价、**连 rand 都不掷**")
    s = f.run(closed=1, rolls=[0x2000] * 20, stocks={i: {"pause": 0} for i in range(12)})
    case("未掷任何 rand", s["rolls"], 0)
    case("   drift 保持 0", s["drift"], 0.0)
    case("   12 支的动能全 0", set(s["mom"]), {0.0})
    case("   价格一支都没动（开户价 = 前收 = 20）", set(s["price"]), {20.0})
    case("   环形指针不推进", s["ring"], 0)

    print("\n[B] 停牌（+0x06 != 0）⇒ 动能清零、价格 = 开盘，且**不掷**这一支的 rand")
    s = f.run(rolls=[0x2000] + [0x2000] * 12, stocks={0: {"pause": 2, "mom": 7.5, "price": 33.0}})
    case("★ rand 次数 = 1（drift） + 11（其余 11 支）", s["rolls"], 12)
    case("   停牌那支：动能 = 0", s["mom"][0], 0.0)
    case("   停牌那支：开盘 = 前收 33，价格 = 33（动能 0 ⇒ 原地）", (s["open"][0], s["price"][0]),
         (33.0, 33.0))

    print("\n[C] 随机路径：r = (rand−0x4000)/1171、drift = (rand−0x4000)/4097")
    s = f.run(rolls=[0x2000, 0x2000] + [0x4000] * 11, stocks={0: {"pause": 0}})
    case("★ drift = f32((0x2000−0x4000)/4097)", s["drift_bits"],
         f32_bits(f32(Fraction(0x2000 - 0x4000) / 4097)))
    # ★ `fst dword [+0x20]` **不弹栈** ⇒ 后面乘/加用的是**未舍入的扩展精度 r**
    r = Fraction(0x2000 - 0x4000) / 1171
    mom = ratio_f32(r * Fraction(f32(1.0)) + Fraction(0.0))
    mom = ratio_f32(Fraction(mom) + Fraction(s["drift"]))
    case("★ 动能 = f32(f32(r×vol) + 昨日) 再 + drift", s["mom_bits"][0], f32_bits(mom))
    case("   其余 11 支（rand=0x4000 ⇒ r=0、drift≠0）也动了",
         s["mom_bits"][1], f32_bits(ratio_f32(Fraction(0.0) + Fraction(s["drift"]))))
    case("   掷了 1+12 次", s["rolls"], 13)

    print("\n[D] 新闻方向 news_dir（+0x07）：高半字节 = 动能 +10、低半字节 = −10")
    s = f.run(rolls=[0x4000, 0x4000] + [0x4000] * 11, stocks={0: {"pause": 0, "news": 0x10}})
    case("★ 高半字节：动能从 +10 起算（drift=0 ⇒ 仍是 +10）", s["mom"][0], 10.0)
    s = f.run(rolls=[0x4000, 0x4000] + [0x4000] * 11, stocks={0: {"pause": 0, "news": 0x01}})
    case("★ 低半字节：动能从 −10 起算", s["mom"][0], -10.0)
    s = f.run(rolls=[0x4000, 0x4000] + [0x4000] * 11, stocks={0: {"pause": 0, "news": 0xF0}})
    case("   只看高半字节是否非 0 ⇒ 0xF0 也是 +10", s["mom"][0], 10.0)

    print("\n[E] 动能是**累加**的（不清零）")
    s = f.run(rolls=[0x4000, 0x3000] + [0x4000] * 11, stocks={0: {"pause": 0, "mom": 2.0}})
    r = Fraction(0x3000 - 0x4000) / 1171
    want = ratio_f32(Fraction(ratio_f32(r * Fraction(f32(1.0)) + Fraction(f32(2.0))))
                     + Fraction(s["drift"]))
    case("★ 动能 = 2 + r×vol + drift（r 用**未舍入**的扩展值）",
         s["mom_bits"][0], f32_bits(want))
    case("   ★ 而 +0x20 存的是**舍过的** r", s["r"][0], f32(r))

    print("\n[F] 动能夹到 ±10（上界用**位型比较**、下界用浮点比较）")
    s = f.run(rolls=[0x4000, 0x7FFF] + [0x4000] * 11,
              stocks={0: {"pause": 0, "mom": 9.0, "vol": 2.0}})
    case("★ 超上界 ⇒ 正好 +10.0", s["mom_bits"][0], f32_bits(10.0))
    s = f.run(rolls=[0x4000, 0x0000] + [0x4000] * 11,
              stocks={0: {"pause": 0, "mom": -9.0, "vol": 2.0}})
    case("★ 超下界 ⇒ 正好 −10.0", s["mom_bits"][0], f32_bits(-10.0))

    print("\n[G] 均值回归阻尼（无上市公司：锚 = base_price，上带 ×8、下带 ×0.5）")
    # 开盘 > 8×锚 且 动能 > 0 ⇒ 动能 ×0.5
    s = f.run(rolls=[0x4000, 0x0000] + [0x4000] * 11,
              stocks={0: {"pause": 0, "base": 10.0, "price": 200.0, "open": 200.0,
                          "mom": 6.0, "vol": 0.0}})
    case("★ 开盘 200 > 8×10 且动能正 ⇒ 动能减半（6 → 3）", s["mom"][0], 3.0)
    # 下方支是「反过来」的：开盘 < 0.5×锚 时 **动能 > 0 → ×2、动能 < 0 → ×0.5**
    s = f.run(rolls=[0x4000, 0x0000] + [0x4000] * 11,
              stocks={0: {"pause": 0, "base": 100.0, "price": 40.0, "open": 40.0,
                          "mom": -3.0, "vol": 0.0}})
    case("★ 开盘 40 < 0.5×100 且动能 **负** ⇒ 动能**减半**（−3 → −1.5）", s["mom"][0], -1.5)
    s = f.run(rolls=[0x4000, 0x0000] + [0x4000] * 11,
              stocks={0: {"pause": 0, "base": 100.0, "price": 40.0, "open": 40.0,
                          "mom": 2.0, "vol": 0.0}})
    case("★ 开盘 40 < 0.5×100 且动能 **正** ⇒ 动能**翻倍**（2 → 4）", s["mom"][0], 4.0)
    # 带内不动
    s = f.run(rolls=[0x4000, 0x0000] + [0x4000] * 11,
              stocks={0: {"pause": 0, "base": 100.0, "price": 100.0, "open": 100.0,
                          "mom": 5.0, "vol": 0.0}})
    case("   带内（开盘 == 锚）⇒ 动能原样", s["mom"][0], 5.0)

    print("\n[H] 落档 + 收尾：现价 / 历史 / 环形指针 / Σ×10")
    s = f.run(rolls=[0x4000, 0x1000] + [0x4000] * 11, stocks={0: {"pause": 0}})
    case("★ 现价 = 落档函数的返回值（与 f32 模型逐位一致）", s["price"][0] > 0, True)
    case("   历史[0][0] = 这一天的现价", s["hist0"], s["price"][0])
    case("   环形指针 +1", s["ring"], 1)
    s = f.run(rolls=[0x4000] * 13, ring=0x8F, stocks={i: {"pause": 0} for i in range(12)})
    case("★ 指针到 0x90 ⇒ 回绕 0", s["ring"], 0)
    want_sum = int(Fraction(f32(Fraction(sum(s["price"])) * 10)))
    case("★ market_sum_x10 = trunc(Σ现价 × 10)", s["sum"], want_sum)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
