#!/usr/bin/env python3
"""
通道 2 差分测试 #14 · `0x0040dffa()` —— **把被关押的人全部标记为「下一天释放」**

无参数、遍历全体玩家：
```asm
0040dffa  xor edx, edx
0040dffc  cmp edx, [0x499114]        ; 玩家数
0040e002  jge 0x40dfd9               ; ★ 出口共用隔壁函数的 `ret`（编译器尾合并）
0040e004  eax = edx*0x68
0040e007  cmp byte [eax + 0x496b7d], 0   ; 出局者跳过
0040e00e  je  下一人
0040e010  cmp byte [eax + 0x496b9a], 0   ; +0x32 == 0 跳过（本来就没被关）
0040e017  je  下一人
0040e019  mov byte [eax + 0x496b9a], 0x80 ; ★ 置「释放挂起」
```

**调用点（本轮自扫，全部在 `mutate` 里）**：
| 调用点 | 场景 |
|---|---|
| `0x0040ac33` | 設施 mode 0：**拆到 0 级**（种类同时归零） |
| `0x0040ac4d` | 設施 mode 1：清归属（后面还跟一个 `0x40a4e1`） |
| `0x0040ac6c` | 設施 mode 2：夷平（`level != 0` 时） |
| `0x0040ae0d` | 住宅 mode 0：拆到 0 级 |
| `0x0040ae51`→`0x0040ae58` | 住宅 mode 1：清归属（后跟 `0x40a4e1`） |
| `0x0040ae58` | 住宅 mode 2：夷平（后跟 `0x40a4e1`） |

⇒ **语义**：任何一种「把旅馆/医院拆掉」的操作，都会把**全场所有**被关押的在场玩家
标记成「下一天释放」—— 注意它**不看地点**（没有参数、也不查设施），是个**一刀切**。
`0x80` 与其它阻塞计数器共用「释放挂起」位（`test d,0x80 / jne → 释放`，
见 `rich4-remake/packages/core/src/rules/blocking.ts` 的 `RELEASE_PENDING`）。

★ 复刻侧此前把这条当成**表现层**（`cards/monster.ts` 的注释写着
「`0x40dffa` 是表现层的设施重建/刷新，core 无可落副作用」）—— **是错的**：
它写的是玩家字段 `+0x32`（复刻映射成 `blocking.inHotel`），是规则状态。
本用例就是这条的差分证据。

跑法：cd rich4-spec && .venv/bin/python tests/test_mutate_release.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

RELEASE_ALL = 0x40DFFA
RELEASE_PENDING = 0x80

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
WHO_PLAYS, BUSY = 0x15, 0x32          # +0x32 = 复刻的 blocking.inHotel / PRD 的「忙碌计数器」
NUM_PLAYERS = 0x499114

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<52} 实际 {got_s!s:<20} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    def release(self, busy=(0, 0, 0, 0), who=(1, 1, 1, 1), n=4):
        def setup(emu):
            emu.write32(NUM_PLAYERS, n)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + WHO_PLAYS, who[i])
                emu.write8(base + BUSY, busy[i])

        self.emu.call(RELEASE_ALL, [], setup=setup)
        return tuple(self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + BUSY)
                     for i in range(4))

    def who(self):
        return tuple(self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS)
                     for i in range(4))


def main():
    print("差分测试 #14：0x0040dffa() 全场标记释放\n")
    f = F()

    print("[1] 在场且非 0 的置 0x80；本来就 0 的不动")
    r = f.release(busy=(3, 0, 5, 0))
    case("(3,0,5,0) → (0x80,0,0x80,0)", r, (128, 0, 128, 0))

    print("\n[2] ★ 出局者跳过（不动物）")
    r = f.release(busy=(1, 2, 3, 4), who=(1, 1, 0, 1))
    case("出局的下标 2 保持 3，其余全 0x80", r, (128, 128, 3, 128))

    print("\n[3] 只看 [0x499114] 范围内的玩家")
    r = f.release(busy=(9, 9, 9, 9), n=1)
    case("玩家数 1 ⇒ 只有下标 0 被改", r, (128, 9, 9, 9))
    r = f.release(busy=(9, 9, 9, 9), n=0)
    case("玩家数 0 ⇒ 谁都不动", r, (9, 9, 9, 9))

    print("\n[4] 已是 0x80 的再置一次仍 0x80（幂等）；不碰别的字段")
    r = f.release(busy=(0x80, 0x81, 0, 0))
    case("(0x80,0x81) → (0x80,0x80)", r[:2], (0x80, 0x80))
    case("whoPlays 一个都没被改", f.who(), (1, 1, 1, 1))

    print("\n[5] ★ 一刀切：**不区分地点**（无参数、不查设施表）")
    # 三条命令式的事实核对：同一调用里，所有非 0 者一起被置
    r = f.release(busy=(1, 1, 1, 1))
    case("四人全被关 → 四人全部置 0x80（不同「哪个旅馆」）", r, (128, 128, 128, 128))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
