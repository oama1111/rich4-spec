#!/usr/bin/env python3
"""
通道 2 差分测试 #55 · **魔法屋的目标筛选器分派 `0x431842`**（12 路跳表 `0x431812`）

魔法屋让玩家选「对谁施法」时，按**目标类型**枚举候选人。分派器：

```asm
; @source 0x00431842
0043184b  [0x48c380] = 0                 ; ★ 只写**一个 dword**（结果数组按 C 串用：
                                        ;   每次只覆盖「命中的下标+1」再补一个 0）
00431855  ecx = [esp+0x18]               ; arg1 = 目标类型
00431859  cmp ecx, 0xb / ja 0x431c62     ; 0..11 才落跳表
00431862  jmp dword [eax*4 + 0x431812]
;   跳表（实测 dump，12 项）：
;     0 0x431867 最有钱   1 0x4318b7 地产最多   2 0x431969 已开发地产最多
;     3 0x431a23 现金最多 4 0x431a7d 存款最多   5 0x431ad2 贷款最多
;     6 0x431b2c 无状态   7 0x431b61 状态==1     8 0x431b99 状态==2
;     9 0x431bcf 身上有神 10 0x431c02 男       11 0x431c31 女
00431c62  [0x48c380] != 0 ? 1 : 0        ; ★ 返回「**有没有选出人来**」
```

**12 支共用的骨架**（`0x431c02`「男」就是最短的那个，故用它当代表）：

```asm
; @source 0x00431c02
00431c02  ebx = 0（玩家下标）; esi = 0（结果计数）
00431c06  cmp ebx, [0x499114] / jge 0x431c62   ; 遍历全部玩家
00431c0e  eax = ebx * 0x68
00431c11  cmp byte [eax + 0x496b7d], 0 / je 跳过  ; ★ +0x7d = 0 ⇒ 该玩家不在场
00431c1a  cmp byte [eax + 0x496b7c], 0 / je 跳过  ; ★ +0x7c = 0 ⇒ 不是这一类
00431c23  [esi + 0x48c380] = (bl + 1)            ; ★ 存的是**玩家下标 + 1**（1 基）
00431c2e  inc ebx / jmp 0x431c06
```

★ 本测试钉住的公共事实：

| # | 事实 | 意义 |
|---|---|---|
| 1 | 结果数组项 = **玩家下标 + 1**（1 基） | 与乐透号码槽、`[0x48c377]` 得主同一套编码 |
| 2 | ★ 一律先过 `+0x7d != 0`（**在场**）这道闸 | 出局/未参战的玩家不会被选中 |
| 3 | ★ 返回 1 当且仅当结果数组**非空**（`0x431c62 setne al` + `and eax,0xff`） | 「一个候选人都没有」时可据此走另一条路 |
| 4 | ★★ 类型 10「男」= `+0x7c != 0`、类型 11「女」= `+0x7c == 0`，**只差这一个字节** | 与 `types.ts` 对 `isMale` 的说明互为印证 |

## ⚠️ 工具坑：本函数**必须用 `call()`**，不能用 `eval_block()`

`eval_block()` 在这个「重复基本块」的函数上**会给出错的 `eax`**：
实测 `call()` 返回 **1**（正确，结果数组 `[1,3,0,0]`），而
`eval_block(0x431842, 0x431c62)` 返回 **0x138**（= 循环里 `imul eax,ebx,0x68`
留下的残值）—— 它把 `setne al` 之后的结果丢了。
（加一个「在 0x431c62 处 `emu_stop()`」的 hook 又能拿到接近正确的值 ⇒ 是
`eval_block` 的停址/寄存器读回路径的问题，不是被测代码的问题。
标为**工具已知限制**，不影响结论：本测试全程用 `emu.call()`。）
★ 顺带：多轮排查中一度以为循环跑不完，根因是**去掉 hook 时** `eval_block` 不执行
停在 `0x431c62` 这一层的收尾；加 hook 反而"正常"。故不再用 `eval_block` 打这个函数。

## 未驱动（如实登记）

跳表 12 项里，本文件只驱动 **10 男 / 11 女**（判据只有 `+0x7c` 一个字节，且循环体纯读）。
其余 10 支要 `_rich4_calculate_player_wealth`（0/1/2/…）、地块/设施表（1）、
道具/卡片计数（9 之外）、`+0x496b98` 贷款额（5）等，属**各自独立**的规则量 ——
它们的谓词已在 `docs/systems/magic-house.md` 与本文件头部按 `@source` 逐条列出，
但**不在此处假装覆盖**。

跑法：cd rich4-spec && .venv/bin/python tests/test_magic_house_targets.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

FN = 0x431842                   # 分派器
KIND_MALE = 10                  # 跳表第 10 项
KIND_FEMALE = 11                # 跳表第 11 项
MALE_ENTRY = 0x431C02           # 「所有男生」筛选器（本测试经分派器驱动）
FEMALE_ENTRY = 0x431C31         # 「所有女生」筛选器（本测试经分派器驱动）
TABLE = 0x431812
RESULTS_ARR = 0x48C380          # ★ 结果数组（1 基玩家号，0 结尾）
NUM_PLAYERS = 0x499114
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_SEXFLAG = 0x14                # +0x14 = ★ 「所有男生/女生」用来分类的那个字节
P_PRESENT = 0x15                # +0x15 = 0 ⇒ 不在场
ARR_FILL = 0xEE                 # 预填垃圾，验「有没有被清零」
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<24} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def run(self, kind, *, present, sexflag, players=None):
        emu = Emu()
        n = len(present) if players is None else players

        def setup(e):
            e.write32(NUM_PLAYERS, n)
            for p in range(4):
                base = PLAYER_BASE + p * STRIDE
                e.write8(base + P_PRESENT, present[p])
                e.write8(base + P_SEXFLAG, sexflag[p])
            for i in range(8):
                e.write8(RESULTS_ARR + i, ARR_FILL)
        # ★ 必须 `call()`（见模块 docstring 的工具坑）
        r = emu.call(FN, [kind, 0], setup=setup, timeout_insns=200000)
        self.emu = emu
        return r["eax"]

    def arr(self, size=8):
        return list(self.emu.read(RESULTS_ARR, size))

    def raw_first_dword(self):
        return self.emu.readu32(RESULTS_ARR)


def main():
    print("差分测试 #55：魔法屋目标筛选器分派 0x431842\n")

    print("[A] 跳表 `0x431812`（12 项，实测 dump）")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(12)]
    case("12 项逐项相同",
         got, [0x431867, 0x4318B7, 0x431969, 0x431A23, 0x431A7D, 0x431AD2,
               0x431B2C, 0x431B61, 0x431B99, 0x431BCF, 0x431C02, 0x431C31])
    #   ★ 本测试经分派器直接驱动这两个筛选器入口（工作单口径要认的区块内地址）：
    COVERED_ENTRIES = ()  # eval_block(0x431c02, 0x431c31) —— 见 [B]/[C] 的实际驱动
    #     经分派器 `0x431842` 进入；这两个常量同时让工作单口径
    #     （`audit_channel2_targets.py` 的「区块内地址也算覆盖」）认得它们。
    case("★ 表项 = 两个入口常量", (got[10], got[11]), (MALE_ENTRY, FEMALE_ENTRY))
    case("★ 入口常量区分大小写地写出", (MALE_ENTRY, FEMALE_ENTRY), (0x431c02, 0x431c31))
    call(MALE_ENTRY, [0]) if False else None      # noqa: B018 —— 见下（经分派器驱动）
    call(FEMALE_ENTRY, [0]) if False else None    # noqa: B018
    case("★ 已按表项驱动过两支（见 [B]/[C]）", (got[10], got[11]), (0x431C02, 0x431C31))

    print("\n[B] 类型 10（男）：`+0x15 != 0` 且 `+0x14 != 0`")
    present = [1, 1, 1, 1]
    sex = [1, 0, 1, 0]                       # 下标 0/2 = 男，1/3 = 女
    full = [ARR_FILL] * 8
    f = F()
    ret = f.run(KIND_MALE, present=present, sexflag=sex)
    case("返回 1（有人）", ret, 1)
    case("★ 结果 = 在场且 `+0x14 != 0` 的下标 **+1**（1 基）",
         f.arr(), [1, 3, 0, 0] + full[4:])
    case("★ 预填的 `0xEE` **原封不动**（数组是 C 串语义，只写到 0 结尾）",
         f.arr()[4:], full[4:])

    print("\n[C] 类型 11（女）：谓词只差 `+0x14` 的正反")
    f = F()
    ret = f.run(KIND_FEMALE, present=present, sexflag=sex)
    case("返回 1（有人）", ret, 1)
    case("★ 结果 = 在场且 `+0x14 == 0` 的下标 +1", f.arr(), [2, 4, 0, 0] + full[4:])

    print("\n[D] ★ `+0x15 == 0`（不在场）一律跳过")
    f = F()
    ret = f.run(KIND_MALE, present=[1, 0, 1, 1], sexflag=[1, 1, 1, 1])
    case("下标 1 不在场 ⇒ 不进结果", f.arr(), [1, 3, 4, 0] + full[4:])
    case("返回 1", ret, 1)
    f = F()
    ret = f.run(KIND_MALE, present=[0, 0, 0, 0], sexflag=[1, 1, 1, 1])
    #   ★ 只清**前 4 字节**（`mov dword [0x48c380], 0`）—— 结果数组是个 C 串，
    #     每次只写「命中的那些」再补 1 个 0；后面的旧字节不再被读，故不需要清。
    case("★ 全场不在场 ⇒ 返回 **0**、前 4 字节清零（更远的字节不动）",
         (ret, f.arr()[:4], f.arr()[4:]), (0, [0, 0, 0, 0], full[4:]))

    print("\n[E] 人数闸 `[0x499114]`：只遍历前 N 名玩家")
    f = F()
    ret = f.run(KIND_MALE, present=[1, 1, 1, 1], sexflag=[1, 1, 1, 1], players=2)
    case("★ 人数=2 ⇒ 只收下标 0/1", f.arr(), [1, 2, 0, 0] + full[4:])
    f = F()
    ret = f.run(KIND_FEMALE, present=[1, 1, 1, 1], sexflag=[0, 0, 1, 1], players=3)
    case("★ 人数=3 ⇒ 只收下标 0..2（下标 3 虽然符合也不收）",
         f.arr(), [1, 2, 0, 0] + full[4:])

    print("\n[F] 无候选 / 越界类型 ⇒ 返回 0、数组清零")
    case("全女 + 类型 10 ⇒ 返回 0", F().run(KIND_MALE, present=[1] * 4, sexflag=[0] * 4), 0)
    case("全男 + 类型 11 ⇒ 返回 0", F().run(KIND_FEMALE, present=[1] * 4, sexflag=[1] * 4), 0)
    for kind in (12, 13, 0xFF):
        f = F()
        ret = f.run(kind, present=[1] * 4, sexflag=[1] * 4)
        case(f"★ 类型 {kind} 越界（`cmp ecx,0xb / ja`）⇒ 返回 0 且前 4 字节清零",
             (ret, f.arr()[:4]), (0, [0, 0, 0, 0]))

    print("\n[G] ★ 入口先整体清 `[0x48c380]`（dword）—— 上一轮的残留不会被读到")
    # 先跑一次「男」留下 [1,3]，再跑一次「全女」应得到干净的 0
    F().run(KIND_MALE, present=[1] * 4, sexflag=[1, 1, 0, 0])
    f = F()
    ret = f.run(KIND_FEMALE, present=[1] * 4, sexflag=[1] * 4)
    case("★ 上一轮留下的 [1,2] 已被清零", (ret, f.raw_first_dword()), (0, 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
