#!/usr/bin/env python3
"""
通道 2 差分测试 · 两个小访问器

| # | VA | 语义 | 复刻侧 |
|---|---|---|---|
| A | `0x00420eee` (12 B) | `getToolParam(idx)` = `dword [0x48be64 + idx*4]` —— 效果侧读 AI 道具参数 | `ai/tool-policy.ts` 的 `[0x48be64]`（复刻把参数编进 action，不建这个数组）|
| B | `0x0042bed0` (51 B) | `cmpSignedWord(a, b)`：`*a > *b → −1`、`*a < *b → 1`、相等 → 0（`movsx` **有符号**）| `ai/stock-policy.ts` 排序用 |

★ B 的两个易错点：
1. 比较的是**有符号 16 位**（`movsx`）—— 0xFFFF 应视为 −1，不是 65535；
2. 返回值方向反直觉：`*a > *b` 返回 **−1**（C 的 `qsort` 升序比较器约定）。

## 打桩清单

两个函数都**不调用任何子程序**、**不摇随机数**，故无桩。
`0x48be64`（道具参数数组）与两个比较用 word 由 `setup()` 直接铺。

跑法：cd rich4-spec && .venv/bin/python tests/test_misc_accessors.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

GET_TOOL_PARAM = 0x420EEE
CMP_WORD = 0x42BED0
TOOL_PARAM = 0x48BE64

WORD_A = SCRATCH_BASE + 0x800
WORD_B = SCRATCH_BASE + 0x804
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.clear()

    def clear(self):
        self.params = [0, 0, 0, 0]
        self.a = 0
        self.b = 0
        return self

    def _setup(self, emu):
        for i, v in enumerate(self.params):
            iv = v & 0xFFFFFFFF
            if iv >= 1 << 31:
                iv -= 1 << 32
            emu.write32(TOOL_PARAM + i * 4, iv)
        for addr, v in ((WORD_A, self.a), (WORD_B, self.b)):
            iv = v & 0xFFFF
            if iv >= 1 << 15:
                iv -= 1 << 16
            emu.write16(addr, iv)

    def get_param(self, idx):
        return self.emu.call(GET_TOOL_PARAM, [idx], setup=self._setup)["eax"]

    def cmp(self):
        r = self.emu.call(CMP_WORD, [WORD_A, WORD_B], setup=self._setup)
        return r["signed"] if r["eax"] >= 1 << 31 else r["eax"]


def main():
    print("差分测试 · `0x420eee`（道具参数访问器）/ `0x42bed0`（有符号 word 比较器）\n")
    w = World()

    # ── A. 0x420eee ──
    print("[A] `0x420eee(idx)` = `dword [0x48be64 + idx*4]`")
    w.clear(); w.params = [11, 22, 33, 44]
    for idx, want in enumerate([11, 22, 33, 44]):
        case(f"idx={idx} ⇒ {want}", w.get_param(idx), want)

    w.clear(); w.params = [0, 0, 0, 0]
    case("全 0 ⇒ 0", w.get_param(0), 0)

    w.clear(); w.params = [0x7FFFFFFF, 0, 0, 0]
    case("0x7FFFFFFF 原样返回（不截断）", w.get_param(0), 0x7FFFFFFF)

    w.clear(); w.params = [0xFFFFFFFF, 0, 0, 0]
    case("★ 0xFFFFFFFF 原样返回（无符号读出）", w.get_param(0), 0xFFFFFFFF)

    w.clear(); w.params = [0, 0x12345678, 0, 0]
    case("★ 步长是 4（idx=1 读第二格）", w.get_param(1), 0x12345678)

    w.clear(); w.params = [0xABCDEF01, 0, 0, 0]
    case("  高位字节不丢（完整 32 位）", w.get_param(0), 0xABCDEF01)

    # ── B. 0x42bed0 ──
    print("\n[B] `0x42bed0(a, b)`：`*a > *b → −1`、`*a < *b → 1`、相等 → 0（有符号）")
    for a, b, want in [(5, 3, -1), (3, 5, 1), (3, 3, 0), (0, 0, 0),
                       (32767, -32768, -1), (-32768, 32767, 1),
                       (-1, 1, 1), (1, -1, -1), (-1, -1, 0),
                       (0, -1, -1), (-1, 0, 1)]:
        w.clear(); w.a = a; w.b = b
        case(f"*a={a} *b={b} ⇒ {want}", w.cmp(), want)

    print("  ★ 有符号语义的反例（若用无符号会得到相反结果）")
    w.clear(); w.a = 0xFFFF; w.b = 1      # −1 vs 1
    case("★ 0xFFFF（= −1）< 1 ⇒ 返回 1（无符号会得 −1）", w.cmp(), 1)
    w.clear(); w.a = 0x8000; w.b = 0      # −32768 vs 0
    case("★ 0x8000（= −32768）< 0 ⇒ 返回 1", w.cmp(), 1)

    print("  ★ 返回值只在 {−1, 0, 1}")
    seen = set()
    for a, b in [(1, 2), (2, 1), (2, 2)]:
        w.clear(); w.a = a; w.b = b
        seen.add(w.cmp())
    case("  三种关系下返回值集合恰为 {−1,0,1}", sorted(seen), [-1, 0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
