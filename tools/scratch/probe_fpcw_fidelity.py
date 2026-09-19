#!/usr/bin/env python3
"""最小复现：Unicorn 的 x87 状态**不随内存快照还原**，会让浮点结果静默错。

背景（2026 本轮，见 `docs/verification.md` 通道 2 与 `rich4-make` 的 §7.38）：
    验「所得税 = trunc(现金 × 0.05)」（区块 `0x449cee`→`0x449d06`）时出现
    「同一实例里**第二次**求值结果不同」：

        第一次  trunc(2147483644 × 0.05) = 107374182   ← 正确
        第二次  同一实例再跑            = 107374184   ← 错（被舍入到 24 位尾数）

    每个值都换新实例则全部正确；`FPCW` 读回恒为 0（状态不在寄存器可见面）。
    根因：Unicorn 的初始控制字与真实 Windows 进程不同（PC=单精度 24 位），
    且该缓存的精度/舍入状态不在 `reset()` 的内存快照覆盖范围内。

修法：`Emu.reset_fpu()`（`reset()` 内自动调用）每次求值前写回真实进程默认
`0x027F`（RC=就近舍入、PC=双精度 53 位）。

本脚本把三种情形并排跑出来，便于**将来升级 Unicorn 时复检**是否已修复
（若哪天 A 组也全对，说明上游修了，可简化 harness —— 但不要先删 reset_fpu）。

跑法：cd rich4-spec && .venv/bin/python tools/scratch/probe_fpcw_fidelity.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import unicorn.x86_const as C  # noqa: E402
from emulate import Emu, FPCW_DEFAULT  # noqa: E402

TAX, TAX_STOP = 0x449CEE, 0x449D06
CASH = 0x496B84
VALUES = (2147483640, 2147483644, 2147483647)
EXPECT = 107374182


def tax(emu, cash):
    """跑原版所得税区块，读回它落到 [esp+0x94] 的整数。"""
    r = emu.eval_block(TAX, TAX_STOP, {"edx": 0},
                       setup=lambda e: e.write32(CASH, cash))
    return emu.read32(r["regs"]["esp"] + 0x94)


def main():
    print(__doc__.split("跑法：")[0].rstrip())
    print()

    print("A) 同一实例连续跑（**未修复**的 harness 才会出错）")
    e = Emu()
    for v in VALUES:
        got = tax(e, v)
        print(f"   cash={v:>11} → {got:>11}   {'ok' if got == EXPECT else '★ 偏差!'}")
    print("   ↑ 修复后（reset_fpu 生效）应全为 ok；若出现偏差，说明 reset_fpu 失效\n")

    print("B) 每个值换新实例（对照组：一直是对的）")
    for v in VALUES:
        got = tax(Emu(), v)
        print(f"   cash={v:>11} → {got:>11}   {'ok' if got == EXPECT else '★ 偏差!'}")

    print("\nC) 手工把控制字写回真实默认 0x027F 后，同一实例连续跑")
    e2 = Emu()
    for v in VALUES:
        e2.mu.reg_write(C.UC_X86_REG_FPCW, FPCW_DEFAULT)
        got = tax(e2, v)
        print(f"   cash={v:>11} → {got:>11}   {'ok' if got == EXPECT else '★ 偏差!'}")

    print(f"\n真实进程默认控制字 FPCW_DEFAULT = {FPCW_DEFAULT:#06x}")
    print("（RC=00 就近舍入、PC=10 双精度 53 位；`0x457dbc` 内部临时改成扩展+截断）")


if __name__ == "__main__":
    sys.exit(main())
