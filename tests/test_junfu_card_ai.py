#!/usr/bin/env python3
"""
通道 2 差分测试 · **均富卡（卡 1）的 AI 判据** `0x0041e6fe`（123 B）

复刻侧对应 `rich4-remake/packages/core/src/ai/card-policy.ts` 的 `junfu`。

## 语义（逐指令读完）

```asm
0x41e6fe():                                  ; 无参
    sum = 0 ; count = 0 ; edx = 0
    for (p = 0; p < [0x499114]; p++) {       ; 人数
        if (byte [player_p + 0x15] == 0) continue    ; who_plays == 0（出局）不算
        sum += dword [player_p + 0x1c]       ; cash
        count++
    }
    avg = sum / count                        ; ★ idiv（向零取整；count 为 0 会崩，实机不可达）
    if (avg <= me_cash * 10) return 0        ; ★ 严格 >
    if (3000 * [0x4990e8] <= me_cash) return 0   ; ★ 物价指数 × 3000，严格 >
    return 1
```

★ 三个易错点：
1. 平均里含**我自己**（原版不排除 `cur`），且只排除 `who_plays == 0` 的人；
2. `avg > 我的现金 × 10` —— `10` 是 `shl 2 + add + add`（5×2）凑出来的，**严格**；
3. 第二闸是 `现金 < 3000 × 物价指数`（即 `3000×pi > 现金`），也是**严格**。

## 打桩清单

本函数**不调用任何子程序**（不查可见表、不摇随机数），故无桩。
`0x499114`（人数）/`0x49910c`（当前玩家）/`0x4990e8`（物价指数）与玩家记录
（`0x496b68 + p*0x68`：`+0x15` who_plays、`+0x1c` 现金）全由 `setup()` 直接铺。

跑法：cd rich4-spec && .venv/bin/python tests/test_junfu_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

JUNFU = 0x41E6FE
CUR = 0x49910C
NUM_PLAYERS = 0x499114
PRICE_INDEX = 0x4990E8
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_CASH = 0x15, 0x1C
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.clear()

    def clear(self):
        self.me = 0
        self.price = 1
        self.players = {}      # idx → (who, cash)
        return self

    def set(self, idx, cash, who=2):
        self.players[idx] = (who, cash)
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(NUM_PLAYERS, 4)
        for p in range(4):
            b = PLAYER_BASE + p * PLAYER_STRIDE
            who, cash = self.players.get(p, (0, 0))
            emu.write8(b + P_WHO, who)
            cv = cash & 0xFFFFFFFF
            if cv >= 1 << 31:
                cv -= 1 << 32
            emu.write32(b + P_CASH, cv)

    def run(self):
        r = self.emu.call(JUNFU, [], setup=self._setup)
        self.ret = r["eax"]
        return self


def main():
    print("差分测试 · 均富卡 AI `0x41e6fe`（平均现金 > 我的 10 倍 且 我的现金 < 3000×物價）\n")
    w = World()

    # ── A. 平均的组成：含自己、只排除 who_plays == 0 ──
    print("[A] 平均含**自己**、只排除 `who_plays == 0`（出局者）")
    w.clear(); w.me = 0
    w.set(0, 1000).set(1, 1000).set(2, 1000).set(3, 1000)     # 平均 1000
    case("四家各 1000、平均 1000、我 1000 ⇒ 不满足 1000 > 10000 ⇒ 0", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 10000).set(2, 10000).set(3, 10000)   # 平均 7525
    r = w.run()
    # avg = trunc(30100/4) = 7525 > 100*10 = 1000 ✓；100 < 3000×1 ✓ ⇒ 1
    case("★ 平均 7525 > 我 100×10、且 100 < 3000 ⇒ 1", r.ret, 1)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 10000, who=0).set(2, 10000).set(3, 10000)
    # who_plays == 0 的玩家被排除：平均 = (100+10000+10000)/3 = 6700
    r = w.run()
    case("★ 出局者不进平均（分母 3）⇒ 仍 1", r.ret, 1)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 10000, who=0).set(2, 10000, who=0).set(3, 10000, who=0)
    # 只剩我一人：avg = 100，100 > 1000 为假 ⇒ 0
    case("★ 只剩我一人 ⇒ 平均 = 我的现金 ⇒ 0", w.run().ret, 0)

    # ── B. 第一闸：avg > 我的现金 × 10（严格）──
    print("\n[B] 第一闸 `avg > 我的现金 × 10`（严格 >）")
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 3000).set(2, 3000).set(3, 3000)
    # avg = (100+9000)/4 = 2275；我*10 = 1000；2275 > 1000 ✓；pi=1: 3000 > 100 ✓ ⇒ 1
    w.price = 1
    case("avg=2275 > 1000 且 100 < 3000 ⇒ 1", w.run().ret, 1)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 3000).set(2, 3000).set(3, 3000)
    w.price = 4     # 3000×4 = 12000 > 100 ⇒ 过；第一闸也过 ⇒ 1
    case("  pi=4（第二闸门槛 12000 > 100）⇒ 1", w.run().ret, 1)

    # 构造 avg == 我×10：我=100 → 需 avg=1000 → sum=4000 → 其余共 3900
    w.clear(); w.me = 0
    w.set(0, 100).set(1, 1300).set(2, 1300).set(3, 1300)
    w.price = 1     # avg = (100+3900)/4 = 1000；1000 > 1000 为假 ⇒ 0
    case("★★ avg = 我×10（恰好相等）⇒ 0（严格 >）", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 100).set(1, 1300).set(2, 1300).set(3, 1304)
    w.price = 1     # sum=4004, avg=1001 > 1000 ⇒ 过第一闸；第二闸 3000>100 ⇒ 1
    case("★★ avg = 我×10 + 1 ⇒ 1", w.run().ret, 1)

    # 整数除法是**向零取整**：sum=10, count=4 → avg=2
    w.clear(); w.me = 0
    w.set(0, 1).set(1, 3).set(2, 3).set(3, 3)   # sum=10, avg=2
    w.price = 1     # 2 > 1*10=10? 否 ⇒ 0
    case("★ 截断：avg = 10/4 = 2（不是 2.5）⇒ 2 > 10 为假 ⇒ 0", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 0).set(1, 40).set(2, 0).set(3, 0)   # sum=40, avg=10
    w.price = 1     # 10 > 0*10=0 ✓；第二闸 3000 > 0 ✓ ⇒ 1
    case("★ avg=10 > 0 ⇒ 1（含我 0 现金）", w.run().ret, 1)

    # ── C. 第二闸：3000 × 物价指数 > 我的现金（严格）──
    print("\n[C] 第二闸 `我的现金 < 3000 × 物價指數`（严格 >）")
    w.clear(); w.me = 0
    w.set(0, 3000).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1     # 第一闸：avg=(3000+300000)/4=75750 > 30000 ✓；第二闸 3000 <= 3000 ⇒ 0
    case("★★ 现金恰为 3000×pi ⇒ 0（严格 >）", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 2999).set(1, 100000).set(2, 100000).set(3, 100000)
    w.price = 1     # 第一闸 ✓；第二闸 3000 > 2999 ✓ ⇒ 1
    case("★★ 现金 2999 = 3000×pi − 1 ⇒ 1", w.run().ret, 1)

    w.clear(); w.me = 0
    w.set(0, 6000).set(1, 1000000).set(2, 1000000).set(3, 1000000)
    w.price = 2     # 第一闸：avg=751500 > 60000 ✓；第二闸 6000 <= 6000 ⇒ 0
    case("★★ pi=2、现金恰为 6000 ⇒ 0", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 5999).set(1, 1000000).set(2, 1000000).set(3, 1000000)
    w.price = 2
    case("★★ pi=2、现金 5999 ⇒ 1", w.run().ret, 1)

    # ── D. 第一闸不满足时，第二闸再宽也不出 ──
    print("\n[D] 两闸是**与**：第一闸不满足时，即使现金远小于 3000×pi 也不出")
    w.clear(); w.me = 0
    w.set(0, 10).set(1, 20).set(2, 20).set(3, 20)   # avg = 17.5 → 17；10*10=100 ⇒ 17 > 100 假
    w.price = 1
    case("avg=17 <= 100（第一闸假）⇒ 0（尽管 10 < 3000）", w.run().ret, 0)

    w.clear(); w.me = 0
    w.set(0, 0).set(1, 0).set(2, 0).set(3, 0)
    w.price = 1
    case("  全 0 ⇒ avg=0 > 0 为假 ⇒ 0", w.run().ret, 0)

    # ── E. 当前玩家下标 / 人数 ──
    print("\n[E] 当前玩家是「我」的读法（cur）")
    w.clear(); w.me = 2
    w.set(0, 10000).set(1, 10000).set(2, 100).set(3, 10000)   # avg=7525 > 1000 ✓
    w.price = 1
    case("★ cur=2 时读的是 2 号的现金（100）⇒ 1", w.run().ret, 1)

    w.clear(); w.me = 2
    w.set(0, 100).set(1, 100).set(2, 10000).set(3, 100)       # avg=2575；我*10=100000 ⇒ 假
    case("★ cur=2 现金 10000 ⇒ 第一闸假 ⇒ 0", w.run().ret, 0)

    w.clear(); w.me = 3
    w.set(0, 100).set(1, 4000).set(2, 4000).set(3, 100)       # avg=2050 > 1000 ✓
    w.price = 1
    case("  3 号为自己 ⇒ 1", w.run().ret, 1)

    seen = set()
    w.clear(); w.me = 0; w.set(0, 100).set(1, 10000).set(2, 10000).set(3, 10000); seen.add(w.run().ret)
    w.clear(); w.me = 0; w.set(0, 100).set(1, 100).set(2, 100).set(3, 100); seen.add(w.run().ret)
    case("  两种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
