#!/usr/bin/env python3
"""
通道 2 差分测试 #57 · **開獎屏状态机：状态 0 / 8 两条最简分支**（`0x430236` / `0x430aa3`）

開獎屏窗口过程按 `[0x48c37b]` 走状态 0..10（跳表 `0x4300d0`）。本文件驱动其中
**只写状态 + 说一句话**的两条：

```asm
; @source 0x00430236（跳表第 0 项 = 状态 0）
00430236  byte [0x48c37b] = 2            ; ★ 直接跳到状态 2
0043023d  ecx = [0x475614]               ; ★ 台词指针（DGROUP 常量）
00430243  push ecx
00430244  call 0x44ecb6                  ; 说这句话（表现层）
; ── 公共尾（0x430244）──
00430249  add esp,4
0043024c  cmp byte [0x48c37b], 3 / jne 0x430f43   ; ★ 状态 3 与 5.. 的处理在别处
00430253  （状态 3 的尾巴）

; @source 0x00430aa3（跳表第 8 项 = 状态 8）
00430aa3  byte [0x48c37b] = 0xa          ; ★ 收官：跳到状态 10
00430aaa  eax = [0x47562c]
00430ab0  jmp 0x430244                   ; ⇒ push + call 同一支「说话」

; ★ 由此推得状态 9（跳表第 8 项 = 0x430aa3 的**前一项** `0x430aa3`）之前那句是
;   `0x430aa3` 自己？不 —— 跳表第 8 项就是 `0x430aa3`，第 9 项是 `0x430ab5`
;   （派彩收尾，见 `test_lottery_settle.py`）。**状态 9 与 10 都由 `0x430aa3`/`0x430ab5`
;   承担**：前者把状态推到 10 并说「行動要快喔！」，后者派彩关屏。
```

★ 本测试钉住的：

| # | 事实 | 意义 |
|---|---|---|
| 1 | 状态 0 ⇒ `[0x48c37b] = 2`（**不是 1**：状态 1 是另一个处理器 `0x43036c`） | 状态机的跳号是原文如此 |
| 2 | 状态 8 ⇒ `[0x48c37b] = 0xa`（直接收官） | 状态 9 不单独出现 |
| 3 | 两条都用**同一个**说话函数 `0x44ecb6`，实参来自 DGROUP 常量 | 台词表：`0x475614`=「現在馬上為您開出這一期…」、`0x47562c`=「行動要快喔！」 |

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x44ecb6` | `ret 4`（吃栈上那个实参） | 说话/立绘，表现层；同时记账「说了几次、实参是哪个」 |

跑法：cd rich4-spec && .venv/bin/python tests/test_lottery_state_simple.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

STATE0 = 0x430236
STATE8 = 0x430AA3
TAIL = 0x430244                 # 两条的公共尾（`call 0x44ecb6` 的那条指令）
SPEECH = 0x44ECB6
TAIL_RET = 0x430249             # `add esp,4` —— 公共尾的第一步
STATE_BYTE = 0x48C37B
LINE0 = 0x475614                # 「#0018現在馬上為您開出這一期…」
LINE8 = 0x47562C                # 「#0036行動要快喔！」
TABLE = 0x4300D0
CALL_SLOT = SCRATCH_BASE + 0x900
FRAME = 0x53F000
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<22} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    @staticmethod
    def speech_stub(slot):
        """`0x44ecb6` 的替身：把栈上实参记到 `slot`，再 `ret 4` 把它弹掉。

        `mov eax,[esp+4]` / `mov [slot],eax` / `ret 4`
        """
        return (b"\x8B\x44\x24\x04"
                + b"\xA3" + struct.pack("<I", slot)
                + b"\xC2\x04\x00")

    def run(self, entry, state=0):
        emu = Emu()

        def setup(e):
            # ★ 必须 `patch()`（并进快照）—— 桩在 `setup()` 里装，见 §7.110 的坑
            e.patch(SPEECH, self.speech_stub(CALL_SLOT))
            e.write8(STATE_BYTE, state)
            e.write32(CALL_SLOT, 0)
            e.write32(FRAME, 0x53FFF0)
        emu.eval_block(entry, TAIL_RET, regs={"esp": FRAME}, setup=setup,
                       timeout_insns=200000)
        self.emu = emu
        return self

    def state(self):
        return self.emu.read8(STATE_BYTE)

    def call_arg(self):
        return self.emu.readu32(CALL_SLOT)

    def ptr(self, va):
        """读 DGROUP 里的**指针常量**（解引用一层）。"""
        return self.emu.readu32(va)


def main():
    print("差分测试 #57：開獎屏状态 0 / 8 两条最简分支 0x430236 / 0x430aa3\n")

    print("[A] 跳表 `0x4300d0` 的两项")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(10)]
    case("[0] = 0x430236（状态 0）", got[0], STATE0)
    case("[8] = 0x430aa3（状态 8）", got[8], STATE8)
    case("[9] = 0x430ab5（状态 10 派彩，已另有差分）", got[9], 0x430AB5)

    print("\n[B] 状态 0 ⇒ 状态直接推到 **2**，并说 `0x475614` 那句话")
    f = F().run(STATE0, state=0)
    case("★ `[0x48c37b]` = 2（不是 1）", f.state(), 2)
    case("★ 说话函数的实参 = 指针 `[0x475614]` **解引用后的值**",
         f.call_arg(), f.ptr(LINE0))
    case("说话函数被调了**一次**（桩记下的实参非 0）", f.call_arg() != 0, True)

    print("\n[C] 状态 8 ⇒ 状态直接推到 **10**（收官），并说 `[0x47562c]` 那句话")
    f = F().run(STATE8, state=8)
    case("★ `[0x48c37b]` = 10", f.state(), 10)
    case("★ 说话函数的实参 = 指针 `[0x47562c]` 解引用后的值",
         f.call_arg(), f.ptr(LINE8))

    print("\n[D] ★ 目标状态与**入口状态**无关（两条都是无条件覆盖）")
    for start in (0, 1, 5, 9, 10, 0xFF):
        f = F().run(STATE8, state=start)
        case(f"状态 8 处理器：入口 {start} ⇒ 一律变 10", f.state(), 10)

    print("\n[E] ★ 台词表本身（DGROUP 常量，逐条读）")
    case("`[0x475614]` 指向 0x46446b", e0.readu32(LINE0), 0x46446B)
    case("`[0x47562c]` 指向 0x464530", e0.readu32(LINE8), 0x464530)
    case("两条台词都是 `#00NN` 前缀的报幕串（第 6 字节已是 Big5 首字节）",
         (e0.read(e0.readu32(LINE0), 5), e0.read(e0.readu32(LINE8), 5)),
         (b"#0018", b"#0036"))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
