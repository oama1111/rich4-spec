#!/usr/bin/env python3
"""
通道 2 差分测试 · **道具的個性闸门 + 跳表分派** `0x00420e9a`（84 B）

复刻侧对应 `rich4-remake/packages/core/src/ai/policy.ts` 的 `decideTool` 里那个
`gatedTool`（`personalityAllows`，`ai/personality.ts`）。

## 语义（逐指令读完）

```asm
0x420e9a(toolId):                       ; cdecl，一个参数
    d = byte [0x47fee1 + toolId*8]      ; 该道具的「凶狠度 f7」（步长 8）
    p = byte [player + 0x17]            ; 当前玩家的個性（0x496b7f）
    d = d - p                           ; 有符号
    if (d >= 2) { eax = d ^ d; ret }    ; ★ = 0：**不查跳表、不摇随机数**
    if (d == 1) {
        rand()                          ; ★ 恰好 1 次
        if (rand() % 3 != 0) { eax = 0; ret }
    }
    eax = toolId
    jmp  dword [toolId*4 + 0x47539c]    ; 尾调用该道具的判定函数，返回值即本函数返回值
```

★ 三条易错点：
1. `d >= 2` 与 `d == 1` 的两条早退里，**跳表函数一次都不被调用**；
2. `d == 1` 时**恰好摇 1 次** `rand()`，余数不为 0 才早退（即 1/3 通过）；
3. 余下的路径（`d <= 1` 通过后）是**尾调用**，本函数返回值 = 被调函数的返回值
   （不是一个常量 1）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x00456f2d` | CRT `rand()` | 数据槽 + **自增计数槽** | 本测试要钉的正是「摇了几次」与 `% 3` 规则（D-004 已登记复刻用确定性替身）|
| `0x0047539c + id*4` | 道具判定**跳表** | 指向桩 `inc [COUNT]; mov eax, IMM; ret` | 逐个道具**判定函数**的语义已由 `test_tool_policy_ai.py` 等各自驱动；本测试要钉的是**闸门与分派**本身 |
| `0x0047fee1` | 道具 `f7` 表（步长 8） | 由 `setup()` 直接铺 | 表内容属通道 1（`packages/data` 的 exe-anchored 测试）|

跑法：cd rich4-spec && .venv/bin/python tests/test_ai_tool_gate.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

TOOL_GATE = 0x420E9A      # 被测函数
PRNG = 0x456F2D

F7_TABLE = 0x47FEE1       # 道具 f7 表（步长 8，取 +0）
DISPATCH = 0x47539C       # 道具判定跳表（id*4）
CUR = 0x49910C
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_PERSONALITY = 0x17

RAND_SLOT = SCRATCH_BASE + 0x900
RAND_CALLS = SCRATCH_BASE + 0x904
STUB_CALLS = SCRATCH_BASE + 0x908
STUB = STUB_BASE          # 判定函数桩的地址
STUB_VALUE = 7
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        # 判定函数桩：计数 + 返回固定值
        self.emu.patch(STUB, b"\xFF\x05" + struct.pack("<I", STUB_CALLS)
                       + b"\xB8" + struct.pack("<I", STUB_VALUE) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.personality = 0
        self.f7 = {}           # toolId → f7
        self.rand = 0
        self.tool = 1
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write32(STUB_CALLS, 0)
        emu.write8(PLAYER_BASE + self.me * PLAYER_STRIDE + P_PERSONALITY, self.personality)
        # ★ 先把整段 f7 表清成 0，再只写要用的那一格（以及一个 +1 的诱饵）
        emu.write(F7_TABLE - 8, b"\x00" * (8 * 16))
        for tid, v in self.f7.items():
            emu.write8(F7_TABLE + tid * 8, v)
            emu.write8(F7_TABLE + tid * 8 + 1, 0xEE)   # 诱饵：步长错读成 +1 就会红
        # 跳表全部指向桩
        for tid in range(0, 16):
            emu.write32(DISPATCH + tid * 4, STUB)

    def run(self, tool_id):
        r = self.emu.call(TOOL_GATE, [tool_id], setup=self._setup)
        self.ret = r["eax"]
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        self.stub_calls = self.emu.readu32(STUB_CALLS)
        return self


def main():
    print("差分测试 · 道具個性闸门 `0x420e9a`（f7 − 個性；≥2 从不 / ==1 三分之一 / ≤0 照做）\n")
    w = World()

    # ── A. gap >= 2：不查跳表、不摇随机数 ──
    print("[A] gap = f7 − 個性 >= 2 ⇒ 返回 0，且**跳表函数一次都不调、rand 一次都不摇**")
    for f7, per, gap in [(5, 3, 2), (4, 0, 4), (10, 8, 2), (255, 0, 255)]:
        w.clear(); w.tool = 1; w.f7 = {1: f7}; w.personality = per
        r = w.run(1)
        case(f"f7={f7} 個性={per}（gap={gap}）⇒ 0", r.ret, 0)
        case("  跳表函数调用次数", r.stub_calls, 0)
        case("  rand 调用次数", r.rand_calls, 0)

    # ── B. gap == 1：恰好摇 1 次，1/3 通过 ──
    print("\n[B] gap == 1 ⇒ 摇 **1** 次 rand()，余数 0 才继续（1/3）")
    for rand, pass_ in [(0, True), (1, False), (2, False), (3, True), (5, False), (6, True), (99, True)]:
        w.clear(); w.tool = 2; w.f7 = {2: 4}; w.personality = 3; w.rand = rand
        r = w.run(2)
        case(f"rand={rand}（%3={rand % 3}）⇒ {'走跳表' if pass_ else '早退 0'}", r.ret, STUB_VALUE if pass_ else 0)
        case("  ★ rand 恰好 1 次", r.rand_calls, 1)
        case("  跳表调用次数", r.stub_calls, 1 if pass_ else 0)

    # ── C. gap <= 0：直接走跳表、不摇随机数 ──
    print("\n[C] gap <= 0 ⇒ 直接尾调用跳表函数（返回值 = 被调函数返回值）")
    for f7, per, gap in [(3, 3, 0), (0, 1, -1), (1, 5, -4), (0, 255, -255)]:
        w.clear(); w.tool = 3; w.f7 = {3: f7}; w.personality = per
        r = w.run(3)
        case(f"f7={f7} 個性={per}（gap={gap}）⇒ {STUB_VALUE}", r.ret, STUB_VALUE)
        case("  跳表调用次数", r.stub_calls, 1)
        case("  rand 调用次数", r.rand_calls, 0)

    # ── D. 返回值 = 被调函数的返回值（不是常量）──
    print("\n[D] 本函数是**尾调用**：返回值原样来自判定函数")
    import struct as _s
    w.clear(); w.tool = 4; w.f7 = {4: 0}; w.personality = 0
    w.emu.patch(STUB, b"\xB8" + _s.pack("<I", 12345) + b"\xC3")
    r = w.run(4)
    case("★ 桩返回 12345 ⇒ 本函数返回 12345", r.ret, 12345)
    w.emu.patch(STUB, b"\xFF\x05" + _s.pack("<I", STUB_CALLS)
                + b"\xB8" + _s.pack("<I", STUB_VALUE) + b"\xC3")

    # ── E. f7 按 toolId 索引、步长 8、只读 +0 ──
    print("\n[E] f7 表按 `toolId*8` 索引、只读 `+0`（诱饵 0xEE 在 `+1`）")
    w.clear(); w.tool = 5
    w.f7 = {5: 5, 6: 0}      # 道具 6 的 f7 = 0
    w.personality = 3        # 对道具 5：gap = 2 → 早退；对道具 6：gap = -3 → 走跳表
    r5 = w.run(5)
    case("★ 道具 5（f7=5, gap=2）⇒ 0", r5.ret, 0)
    r6 = w.run(6)
    case("★ 道具 6（f7=0, gap=-3）⇒ 走跳表", r6.ret, STUB_VALUE)
    w.clear(); w.tool = 7; w.f7 = {7: 3}; w.personality = 3   # gap = 0 ⇒ 走跳表
    r = w.run(7)
    case("★ 只读 +0（若错读 +1 的 0xEE 则 gap=235 ⇒ 早退 0）", r.ret, STUB_VALUE)

    # ── F. 边界：gap 恰为 1 / 2、個性为 255 ──
    print("\n[F] 边界值")
    w.clear(); w.tool = 8; w.f7 = {8: 2}; w.personality = 0   # gap = 2 恰好
    case("★ gap 恰为 2 ⇒ 早退（>= 2 含 2）", w.run(8).ret, 0)
    w.clear(); w.tool = 8; w.f7 = {8: 1}; w.personality = 0; w.rand = 0   # gap = 1
    case("  gap 恰为 1、rand%3==0 ⇒ 走跳表", w.run(8).ret, STUB_VALUE)
    w.clear(); w.tool = 8; w.f7 = {8: 0}; w.personality = 0; w.rand = 1   # gap = 0
    r = w.run(8)
    case("  gap 恰为 0 ⇒ 走跳表且不摇", r.ret, STUB_VALUE)
    case("  rand 0 次", r.rand_calls, 0)
    w.clear(); w.tool = 9; w.f7 = {9: 0}; w.personality = 255  # gap = -255
    r = w.run(9)
    case("  個性 255、f7 0 ⇒ gap = −255 ⇒ 走跳表", r.ret, STUB_VALUE)

    seen = set()
    w.clear(); w.tool = 1; w.f7 = {1: 9}; w.personality = 0; seen.add(w.run(1).ret)
    w.clear(); w.tool = 1; w.f7 = {1: 0}; w.personality = 0; seen.add(w.run(1).ret)
    w.clear(); w.tool = 1; w.f7 = {1: 1}; w.personality = 0; w.rand = 1; seen.add(w.run(1).ret)
    case("  三种情形下返回值集合恰为 {0, 7}", sorted(seen), [0, STUB_VALUE])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
