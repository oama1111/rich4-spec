#!/usr/bin/env python3
"""
测试台自检 #1 · `tools/emulate.py` 的两条**曾经踩过**的语义

这两条都不是 exe 的行为，而是**测试台**的行为 —— 但它们各自让一轮排查跑偏，
所以单独钉住：

## 1. 同一个 VA 打第二次补丁必须生效（TB 缓存）

```python
e.patch(0x456f2d, mov eax,5 / ret) ; e.call(0x456f2d)  -> 5
e.patch(0x456f2d, mov eax,7 / ret) ; e.call(0x456f2d)  -> 7   # ★ 曾经返回 5
```

原因有两层，都修在 `Emu.patch` 里了：
① 代码段 AUTO **不在可写段表里** ⇒ 原先只有可写段会重拍 `reset()` 快照，
   第二次补丁被 `reset()` 还原成第一次的内容；
② 即使快照对了，Unicorn 的**翻译块缓存**仍会执行旧补丁 —— 必须按**命中段**
   的范围 `ctl_remove_cache(sva, sva+size)`（宽范围 0x400000..0x500000 实测无效）。

## 2. 暂存区不被 reset、DGROUP 被 reset

`SCRATCH_BASE` 起 64KB **故意不进快照**（跨多次 `call()` 保持数据），
而 DGROUP 每次 `call()` 前都会被还原 —— 所以「每次调用前要注入的数据」
必须在 `setup(emu)` 里写（写在调用外会被抹掉，这是文件头注释里记过的老坑）。

跑法：cd rich4-spec && .venv/bin/python tests/test_harness.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

PRNG = 0x456F2D
SCRATCH_SLOT = SCRATCH_BASE + 0x700
DGROUP_SLOT = 0x499300  # DGROUP 里的一个空闲字（本自检不依赖它原来的值）

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got!s:<12} 期望 {want!s}")
    return ok


def stub(v):
    return b"\xB8" + struct.pack("<I", v & 0xFFFFFFFF) + b"\xC3"


def main():
    print("测试台自检：patch 的二次生效 / 暂存区语义\n")
    e = Emu()

    print("[1] 同一个 VA 连续打补丁，每次都生效")
    e.patch(PRNG, stub(5))
    case("第一次：返回 5", e.call(PRNG, [])["eax"], 5)
    e.patch(PRNG, stub(7))
    case("★ 第二次：返回 7（曾因 TB 缓存返回 5）", e.call(PRNG, [])["eax"], 7)
    e.patch(PRNG, stub(0))
    case("第三次：返回 0", e.call(PRNG, [])["eax"], 0)
    e.patch(PRNG, stub(0xFFFFFFFF))
    case("负数（有符号 -1）", e.call(PRNG, [])["signed"], -1)

    print("\n[2] 暂存区跨调用保持，DGROUP 被 reset 还原")
    e.scratch_write(SCRATCH_SLOT, struct.pack("<I", 0x1234))
    e.call(PRNG, [])  # 任何一次 call 都会 reset
    case("暂存区里的 0x1234 还在", e.read32(SCRATCH_SLOT), 0x1234)

    def setup(emu):
        emu.write32(DGROUP_SLOT, 0xABCD)

    e.call(PRNG, [], setup=setup)
    case("setup 里注入的 DGROUP 值当次可见", e.read32(DGROUP_SLOT), 0xABCD)
    e.call(PRNG, [])
    case("下一次 call 之后被 reset 还原", e.read32(DGROUP_SLOT), 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
