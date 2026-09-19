#!/usr/bin/env python3
"""
通道 2 差分测试 #60 · **魔法屋「极值类」目标筛选器**（跳表 0x431812 的 idx 0/3/4/5）

上一支（`test_magic_house_targets.py`）驱动了最简的 idx 10/11（男/女）。
本文件驱动**同一骨架**的四个「取最大者」：

```asm
; 跳表 0x431812（12 项）：0 最有钱 1 地产最多 2 已开发最多 3 现金最多
;                        4 存款最多 5 點券最多 6 走路 7 機車 8 汽車
;                        9 有神 10 男 11 女
; 四支共用的骨架（以 idx 3「现金最多」0x431a23 为例）：
00431a23  ebx = 0（玩家下标）; esi = 0（结果计数）
00431a27  eax = 0                    ; ★ 这里的初值是 0（不是 edx！）
00431a29  dword [esp] = eax          ;   「当前最大值」的槽
00431a2c  cmp ebx, [0x499114] / jge 汇合点
00431a38  eax = ebx * 0x68
00431a3b  cmp byte [eax + 0x496b7d], 0 / je 下一位  ; ★ +0x7d = 0 ⇒ 不在场
00431a38  cmp dword [eax + 0x496b84], 0 / je 下一位  ; ★ **值为 0 也跳过**
00431a50  ecx = [eax + 0x496b84]                    ; 候选值
00431a56  cmp edx(当前最大), ecx
00431a58  jge 0x431a6d                              ; 不大 ⇒ 看是否相等
00431a5a    [esp] = ecx                              ; 更大 ⇒ 换最大值
00431a5d    esi == 0 ? 跳到收录 : **清空结果数组**（`[0x48c380] = 0`）
00431a6d  jne 下一位                                 ; ★ **严格小于**才跳过 ⇒ 相等也收录
00431a6f  [esi + 0x48c380] = (bl + 1)                ; ★ 1 基
00431a79  inc esi
```

★ 四条实测要点：

| # | 事实 | 意义 |
|---|---|---|
| 1 | ⚠️ **平手语义：原版未定义**（`jle` 走「换最大」，`jne` 才跳过 —— 但「最大值槽初值」来自**第二实参**，而两个调用点都只压 1 个实参 ⇒ 读到未初始化栈） | 复刻定为「**平手全收**」，已登记 `known-deviations` **D-LEGACY-3**（取证见 gaps §7.123/§7.124）；**本测试不钉平手集合** |
| 2 | ★ **值为 0 直接跳过**（`cmp …,0 / je`） | 一分钱没有的人不会因为「大家都没钱」而中选 |
| 3 | ★ 换新最大值时**清空**已收集的结果 | 结果数组只留最后一个最大值的下标 |
| 4 | 结果项 = **玩家下标 + 1**（1 基） | 与其余筛选器同制 |

★ 四个类型的差别只在**读哪个字段**：

| idx | VA | 字段 | 备注 |
|---|---|---|---|
| 0 | `0x431867` | 依次调 `0x4239b9`（`calculate_player_wealth`） | **不需要**预处理 |
| 3 | `0x431a23` | `player + 0x1c`（现金，i32） | |
| 4 | `0x431a7d` | `player + 0x20`（存款，i32） | |
| 5 | `0x431ad2` | `player + 0x30`（**點券**，**u16**；★ 贷款在 `+0x24`，dword） | |

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x4239b9` | `mov eax,[SCRATCH+0x810] / ret` | `calculate_player_wealth` —— idx 0 每轮调它一次；用**数据槽**喂值，从而把 idx 0 也变成「字段比较」的同构用例 |

跑法：cd rich4-spec && .venv/bin/python tests/test_magic_house_extremes.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

DISPATCH = 0x431842
WEALTH = 0x4239B9
WEALTH_SLOT = SCRATCH_BASE + 0x810
WEALTH_N = SCRATCH_BASE + 0x840


def _wealth_stub_bytes():
    """`calculate_player_wealth(p)` 的替身：**依次**返回队列表里的第 n 个值。

    调用顺序 = 玩家下标升序（骨架就是这么扫的），故用队列表即可把 idx 0
    变成与 idx 3/4/5 同构的「字段比较」用例。

    ```asm
    mov  eax, [WEALTH_N]
    mov  eax, [eax*4 + WEALTH_SLOT]
    inc  dword [WEALTH_N]
    ret
    ```
    """
    return (b"\x8B\x05" + struct.pack("<I", WEALTH_N)
            + b"\x8B\x04\x85" + struct.pack("<I", WEALTH_SLOT)
            + b"\xFF\x05" + struct.pack("<I", WEALTH_N)
            + b"\xC3")

TABLE = 0x431812
RESULTS_ARR = 0x48C380
NUM_PLAYERS = 0x499114
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_PRESENT = 0x15
P_CASH = 0x1C
P_BANK = 0x20
P_POINTS = 0x30
STOP = 0x431C62
ARR_FILL = 0xEE
# idx → (字段偏移, 位宽)
EXTREMES = {
    0: ("wealth", None),
    3: ("cash", 32),
    4: ("bank", 32),
    5: ("points", 16),
}
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<26} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def run(self, kind, values, present=None, players=None, wealth_stub=False):
        """`values[p]` = 该玩家的「候选值」；返回 (返回值, 结果数组)。"""
        emu = Emu()
        n = len(values) if players is None else players
        pres = [1] * 4 if present is None else present

        def setup(e):
            e.write32(NUM_PLAYERS, n)
            for p in range(4):
                base = PLAYER_BASE + p * STRIDE
                e.write8(base + P_PRESENT, pres[p])
                v = values[p] if p < len(values) else 0
                if kind == 0:
                    # idx 0 用「依次喂」的办法：桩每次返回同一批值里的下一个，
                    # 但调用顺序 = 玩家下标升序，故直接用 values[p] 铺一个队列表。
                    e.write32(WEALTH_SLOT + p * 4, v & 0xFFFFFFFF)
                elif kind == 3:
                    e.write32(base + P_CASH, v & 0xFFFFFFFF)
                elif kind == 4:
                    e.write32(base + P_BANK, v & 0xFFFFFFFF)
                elif kind == 5:
                    e.write16(base + P_POINTS, v & 0xFFFF)
            # ★ wealth 桩**总是**打上（idx 0 要用；其它 idx 不会调到它，
            #   留着也无害），计数器每个用例清零。
            e.patch(WEALTH, _wealth_stub_bytes())
            e.write32(WEALTH_N, 0)
            for i in range(8):
                e.write8(RESULTS_ARR + i, ARR_FILL)
        r = emu.call(DISPATCH, [kind, 0], setup=setup, timeout_insns=200000)
        self.emu = emu
        return r["eax"], list(emu.read(RESULTS_ARR, 8))


def main():
    print("差分测试 #60：魔法屋极值类筛选器（idx 0/3/4/5）\n")

    print("[A] 跳表 `0x431812` 的四项")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(12)]
    case("[0] 最有钱 = 0x431867", got[0], 0x431867)
    case("[3] 现金最多 = 0x431a23", got[3], 0x431A23)
    case("[4] 存款最多 = 0x431a7d", got[4], 0x431A7D)
    case("[5] 點券最多 = 0x431ad2", got[5], 0x431AD2)

    print("\n[B] idx 3「现金最多」：单选与平手")
    fill = [ARR_FILL] * 8
    ret, arr = F().run(3, [100, 300, 200, 0])
    case("返回值 1（有候选）", ret, 1)
    case("现金 300 的下标 1 ⇒ 结果 [2]", arr, [2, 0, 0, 0] + fill[4:])
    ret, arr = F().run(3, [500, 300, 200, 400])
    case("最大值在下标 0 ⇒ [1]", arr, [1, 0, 0, 0] + fill[4:])
    ret, arr = F().run(3, [300, 300, 100, 0])
    #   ⚠️ 平手**不断言具体集合** —— 原版这一支的「最大值槽初值」来自
    #   `0x431842` 的**第二实参**，而两个调用点都只压 1 个实参 ⇒ 原版读的是
    #   未初始化栈内容 ⇒ 平手到底「全收」还是「只留最后一个」在原版里**不确定**。
    #   复刻定为「全收」，已登记为 `known-deviations` 的 **D-LEGACY-3**（同 D-LEGACY-1/2 一族）。
    #   故这里只钉「确实选中了并列者之一」这件**确定**的事。
    case("★ 平手（0/1 都是 300）⇒ 返回值 1，且结果是并列者之一（**不钉集合**，见 D-LEGACY-3）",
         (ret, arr[0] in (1, 2), arr[2]), (1, True, 0))
    ret, arr = F().run(3, [300, 300, 300, 0])
    case("★ 三人平手 ⇒ 返回值 1，且结果是并列者之一",
         (ret, arr[0] in (1, 2, 3)), (1, True))

    print("\n[C] ★ 值为 0 的玩家不进结果（即使全场都是 0）")
    ret, arr = F().run(3, [0, 0, 0, 0])
    case("全场现金 0 ⇒ 返回 0、数组前 4 字节清 0", (ret, arr[:4]), (0, [0, 0, 0, 0]))
    ret, arr = F().run(3, [0, 0, 5, 0])
    case("只有下标 2 有 5 ⇒ [3]", arr, [3, 0, 0, 0] + fill[4:])

    print("\n[D] ★ 不在场（`+0x7d == 0`）不参评")
    ret, arr = F().run(3, [100, 999, 200, 0], present=[1, 0, 1, 0])
    case("下标 1 不在场（它现金 999）⇒ 赢家是下标 2", arr, [3, 0, 0, 0] + fill[4:])

    print("\n[E] ★ 人数闸 `[0x499114]`")
    ret, arr = F().run(3, [100, 300, 200, 0], players=2)
    case("人数 2 ⇒ 只看到 100/300 ⇒ [2]", arr, [2, 0, 0, 0] + fill[4:])

    print("\n[F] idx 4「存款最多」读 `player + 0x20`")
    ret, arr = F().run(4, [100, 300, 200, 0])
    case("存款 300 在下标 1 ⇒ [2]", arr, [2, 0, 0, 0] + fill[4:])
    ret, arr = F().run(4, [100, 100, 0, 0])
    case("★ 平手 100/100 ⇒ 结果是并列者之一（**不钉集合**，见 D-LEGACY-3）",
         (ret, arr[0] in (1, 2)), (1, True))

    print("\n[G] idx 5「點券最多」读 `player + 0x30`（**u16**；★ 不是贷款 —— 贷款在 `+0x24`，dword）")
    ret, arr = F().run(5, [10, 300, 20, 0])
    case("點券 300 在下标 1 ⇒ [2]", arr, [2, 0, 0, 0] + fill[4:])
    ret, arr = F().run(5, [0xFFFF, 1, 0, 0])
    case("★ u16 上界 0xffff 仍是最大 ⇒ [1]", arr, [1, 0, 0, 0] + fill[4:])

    print("\n[H] ★ idx 0「最有钱」：字段换成人均总资产（`0x4239b9` 已打桩）")
    ret, arr = F().run(0, [100, 300, 200, 0], wealth_stub=True)
    case("总资产 300 在下标 1 ⇒ [2]", arr, [2, 0, 0, 0] + fill[4:])
    ret, arr = F().run(0, [100, 100, 0, 0], wealth_stub=True)
    case("★ 平手 ⇒ 结果是并列者之一（**不钉集合**，见 D-LEGACY-3）",
         (ret, arr[0] in (1, 2)), (1, True))

    print("\n[I] 四个类型的结果结构与 idx 3 完全一致（同构核对）")
    for kind in (0, 3, 4, 5):
        ret, arr = F().run(kind, [100, 300, 200, 0], wealth_stub=(kind == 0))
        case(f"idx {kind} ⇒ [2]", arr, [2, 0, 0, 0] + fill[4:])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
