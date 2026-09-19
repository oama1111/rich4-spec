#!/usr/bin/env python3
"""
通道 2 差分测试 · PRNG (VA 0x00456f2d / 设种子 0x00456f50)

用 Unicorn 执行**原版机器码**，验证 `docs/systems/game-loop.md` 里登记的算法：

    state  = state * 0x41C64E6D + 0x3039        (mod 2^32)
    返回值 = (state >> 16) & 0x7FFF             ← 15 位，[0, 32767]

⚠️ 本测试揭示过两个**测试台本身的陷阱**，都已在 `tools/emulate.py` 里修掉，
   写在这里备查（它们会让"原版行为"看起来完全错误）：

  T-A 补丁会被 reset 抹掉
      打桩代码段后若没重拍快照，第二次 `call()` 的 `reset()` 会把补丁还原。
      → 用 `emu.patch()`，它会把补丁并入快照。

  T-B 状态放在被快照的段里会被清零
      RNG 状态若放在 DGROUP/.bss（都在快照内），每次调用前都被恢复成初始值，
      于是永远从 0 开始 —— 表现是"设了种子却没生效"。
      → 把状态放在 `SCRATCH_BASE`（**故意不纳入快照**的暂存区）。

跑法：cd rich4-spec && .venv/bin/python tests/test_prng.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

PRNG = 0x456F2D
SEED_FN = 0x456F50
ACCESSOR = 0x456F23
A, B, MASK = 0x41C64E6D, 0x3039, 0xFFFFFFFF

SEEDS = [0x12345678, 0x00000001, 0xDEADBEEF, 0xFFFFFFFF, 0x00000000]
N_PER_SEED = 12
RESULTS = []


def expected_sequence(seed: int, n: int):
    """规格里的算法：既给出返回值，也给出状态推进。"""
    s = seed
    out = []
    for _ in range(n):
        s = (s * A + B) & MASK
        out.append(((s >> 16) & 0x7FFF, s))
    return out


def main():
    emu = Emu()
    state_va = SCRATCH_BASE
    # 把「取状态块」打桩成固定返回 state_va；patch() 会并入快照
    emu.patch(ACCESSOR, bytes([0xB8]) + struct.pack("<I", state_va) + b"\xC3")

    print("差分测试：PRNG")
    print("对照规格：docs/systems/game-loop.md §四\n")

    for seed in SEEDS:
        emu.scratch_write(state_va, struct.pack("<I", 0))     # 先清零
        emu.call(SEED_FN, [seed])                             # 设种子
        got_seed = struct.unpack("<I", emu.scratch_read(state_va, 4))[0]
        if got_seed != seed:
            RESULTS.append(False)
            print(f"  ❌ 设种子失败：写入 0x{seed:08x}，读回 0x{got_seed:08x}")
            continue

        exp = expected_sequence(seed, N_PER_SEED)
        bad = []
        for i, (want_val, want_state) in enumerate(exp):
            got = emu.call(PRNG, [])["eax"]
            st = struct.unpack("<I", emu.scratch_read(state_va, 4))[0]
            if got != want_val or st != want_state:
                bad.append((i, got, want_val, st, want_state))

        ok = not bad
        RESULTS.append(ok)
        print(f"  {'✅' if ok else '❌'} 种子 0x{seed:08x}：{N_PER_SEED} 个值 + 状态推进"
              f"{'' if ok else f'，{len(bad)} 处不符'}")
        for i, g, w, gs, ws in bad[:3]:
            print(f"        [{i}] 返回 0x{g:04x}≠0x{w:04x}  状态 0x{gs:08x}≠0x{ws:08x}")

    # 范围检查：返回值必须是 15 位
    emu.scratch_write(state_va, struct.pack("<I", 0xA5A5A5A5))
    vals = [emu.call(PRNG, [])["eax"] for _ in range(200)]
    in_range = all(0 <= v <= 0x7FFF for v in vals)
    RESULTS.append(in_range)
    print(f"  {'✅' if in_range else '❌'} 返回值范围：200 次调用全部落在 [0, 32767]"
          f"（min={min(vals)}, max={max(vals)}）")

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
