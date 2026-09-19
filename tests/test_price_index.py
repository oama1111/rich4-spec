#!/usr/bin/env python3
"""
通道 2 差分测试 #8 · `rich4_update_price_index`（VA 0x00423acf）

物价指数是全游戏价格的乘子（估价、地價稅/證交稅、挂牌市价、AI 判据…），
但这条**更新规则**此前只做过"读汇编 + 单元测试"，没有真值比对。

规格来源：`docs/systems/stocks.md` §2.6、`docs/systems/economy.md` 与
`gen/db.txt` 的 `0x423acf`。算法（34 条指令 / 85 字节，**无参数、全读全局**）：

```
sum = 0 ; count = 0
for p in 0 .. [0x499114]-1:          ; 玩家数
    if byte [player(p) + 0x15] == 0: continue     ; whoPlays==0 ⇒ 出局，跳过
    sum += wealth(p)                 ; ← 调 0x4239b9，**内部会把总资产压成 float32**
    count++
average = trunc(sum / count)          ; 0x423b02 `idiv edi`（有符号向零）
next    = trunc(average / [0x49908c]) ; 0x423b0f `idiv ecx`；除数 = **本局开局资金**
if next >  [0x4990e8]: [0x4990e8] = next   ; 0x423b13 `cmp/jle` —— **不降级**
```

★ 本轮最有价值的发现：`wealth()` 内部的 float32 量化会**穿透到物价指数**。
`cash = 99899999` 时总资产被量化成 `99900000`，于是
`trunc(99900000/300000) = 333`，而"纯精确"模型给 `332` —— **差 1 档物价指数**，
再乘进所有价格公式。这一条把「股票段的 f32 量化」（上一轮修的）与
「物价指数」串了起来，用例里专门锁死。

⚠️ 除零：`count == 0`（全员出局）时原版在 `0x423b02 idiv edi` 上直接**除零异常**，
复刻加了 `count === 0` 的护栏 —— 属**有意偏离**（该分支在正常对局不可达）。

跑法：cd rich4-spec && .venv/bin/python tests/test_price_index.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

UPDATE_PRICE_INDEX = 0x423ACF

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
WHO_PLAYS, CASH, BANK, LOAN = 0x15, 0x1C, 0x20, 0x24
NUM_PLAYERS, INITIAL_FUND, PRICE_INDEX = 0x499114, 0x49908C, 0x4990E8

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<50} 实际 {got!s:<10} 期望 {want!s}")
    return ok


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


class F:
    def __init__(self):
        self.emu = Emu()

    def update(self, cash, alive=None, n=None, initial=300_000, cur=1):
        """跑一次原版 0x423acf，返回**更新后**的物价指数 [0x4990e8]。"""
        alive = tuple(alive) if alive is not None else (True,) * len(cash)
        n = n if n is not None else len(cash)
        cash = list(cash) + [0] * (4 - len(cash))
        alive = alive + (True,) * (4 - len(alive))

        def setup(emu):
            emu.write32(NUM_PLAYERS, n)
            emu.write32(INITIAL_FUND, initial)
            emu.write32(PRICE_INDEX, cur)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + WHO_PLAYS, 1 if (i < n and alive[i]) else 0)
                emu.write32(base + CASH, cash[i])
                emu.write32(base + BANK, 0)
                emu.write32(base + LOAN, 0)

        self.emu.call(UPDATE_PRICE_INDEX, [], setup=setup)
        return self.emu.read32(PRICE_INDEX)


def main():
    print("差分测试 #8：rich4_update_price_index(VA 0x00423acf)\n")
    f = F()

    print("[1] 单人：next = trunc(trunc(资产/1) / 开局资金)，且**只在变大时**写入")
    case("100 万 / 30 万 → 3", f.update([1_000_000], n=1), 3)
    case("59.9999 万 → 1（不更新，保持 cur=1）", f.update([599_999], n=1), 1)
    case("60 万 → 2", f.update([600_000], n=1), 2)
    case("89.9999 万 → 2", f.update([899_999], n=1), 2)
    case("90 万 → 3", f.update([900_000], n=1), 3)
    case("0 → 1（不更新）", f.update([0], n=1), 1)
    case("★ 当前更高时不降级：cur=99 → 99", f.update([1_000_000], n=1, cur=99), 99)
    case("★ 与 cur 相等也不写：cur=3 → 3", f.update([1_000_000], n=1, cur=3), 3)

    print("\n[2] 出局者（whoPlays == 0）不计入分子也不计入分母")
    case("4 人只有 p0 活着、100 万 → 3",
         f.update([1_000_000], alive=(True, False, False, False)), 3)
    case("4 人只有 p2 活着、100 万 → 3",
         f.update([0, 0, 1_000_000, 0], alive=(False, False, True, False)), 3)
    case("4 人 p1/p2 活着各 120/60 万 → 平均 90 万 → 3",
         f.update([0, 1_200_000, 600_000, 0], alive=(False, True, True, False)), 3)
    case("★ 若误把出局者算进分母（1 人 100 万 / 4）→ 会是 1",
         f.update([1_000_000, 0, 0, 0], alive=(True, False, False, False)), 3)

    print("\n[3] 平均值对存活人数取整（`idiv` 向零）")
    case("4 人各 30 万 → 平均 30 万 → 1（=cur，不更新）", f.update([300_000] * 4), 1)
    case("4 人各 45 万 → 平均 45 万 → 1", f.update([450_000] * 4), 1)
    case("4 人各 60 万 → 平均 60 万 → 2", f.update([600_000] * 4), 2)
    case("4 人 [120万,0,0,0] 全活 → 平均 30 万 → 1", f.update([1_200_000, 0, 0, 0]), 1)

    print("\n[4] 开局资金档位 = 除数（`[0x49908c]`）")
    case("100 万 / 3 万档 → 33", f.update([1_000_000], n=1, initial=30_000), 33)
    case("100 万 / 100 万档 → 1", f.update([1_000_000], n=1, initial=1_000_000), 1)
    case("100 万 / 10 万档 → 10", f.update([1_000_000], n=1, initial=100_000), 10)

    print("\n[5] ★ 总资产的 float32 量化会**穿透**到物价指数（本轮发现）")
    # wealth() 的股票段把总资产反复压进 float32（>2^24 丢低位），于是：
    case("★ 99899999：量化成 99900000 → 333（纯精确给 332）",
         f.update([99_899_999], n=1), 333)
    case("   对照：99900000 本身就是 float32 可表示值 → 333",
         f.update([99_900_000], n=1), 333)
    case("   对照：纯精确模型 trunc(99899999/300000)",
         (99_899_999) // 300_000, 332)
    case("   f32(99899999) 确实是 99900000",
         f32(99_899_999), 99_900_000.0)
    case("   量化后与原版的差 = 1 档物价指数",
         f.update([99_899_999], n=1) - (99_899_999) // 300_000, 1)
    case("★ 99999999：量化成 1e8 → 333（精确也是 333，不差）",
         f.update([99_999_999], n=1), 333)
    case("★ 16777217（2^24+1）：量化成 16777216 → 55（精确 55，不差）",
         f.update([16_777_217], n=1), 55)

    print("\n[6] 量化穿透的第二个算例：跨过 300000 的整数倍")
    # 89999999 → f32 = 90000000 → 300 → 而精确 89999999/300000 = 299.99… → 299
    case("★ 89999999 → 量化 90000000 → 300（精确 299）",
         f.update([89_999_999], n=1), 300)
    case("   f32(89999999) = 9e7", f32(89_999_999), 90_000_000.0)
    case("   纯精确模型 → 299", 89_999_999 // 300_000, 299)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
