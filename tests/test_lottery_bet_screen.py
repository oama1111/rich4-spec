#!/usr/bin/env python3
"""通道 2 差分测试 #51 · **樂透投注屏的窗口过程 `0x42f7fc`**（1,230 字节，工作单影响面第一）

用**手搓帧 + `eval_block`** 驱动它的消息分支：
`eval_block(0x42f7fc, 停址, regs={'esp': 0x53F000})` —— 四个实参摆在
`[ESP+4/8/c/10]`（hwnd/msg/wParam/lParam），`[ESP]` 放哨兵返回地址。
（`emu.call()` 的帧口径与 WndProc 的 `[esp+0x70]` 差 0x2c，故不用它。）

★ **停址要试两次**：`0x42FDB6`（状态 5「画公库金额」那一支的入口）能让**状态链走完**；
而状态 0/4/5 与 `0x201`/`0x205`/`0x405` 那些路径**不经过**它 ⇒ 会跑过 `ret 0x10`
而失败，此时退回 `0x42F92D`。这是本文件的核心手法。

## 消息表（逐条实测）

| 消息 | 去向 | 实测 |
|---|---|---|
| `0x401` `WM_USER+1` | `0x42f885` | 五个状态字节清零；`call 0x42f32c`；`SetTimer(hwnd,[0x46cad8],0x64)` |
| `0x405` `WM_USER+5` | `0x42f930` | `[0x48c370] = wParam` |
| `0x113` `WM_TIMER` | `0x42fa2f` | 三道闸 + `jmp [([0x48c370]−1)*4 + 0x42f7e8]` |
| `0x201`/`0x203` | `0x42fe8c` | `状态>3` 什么都不做 / `==3` 直落判号格 / `<3` 先收气泡**再**判号格 |
| `0x205` `WM_RBUTTONUP` | `0x43003d` | 走人（音效 + `PostMessage(0x406,5,0)`）|

## 现金闸（建屏那一段，`0x42f8d7`）

`cash < 0x3e8` ⇒ `PostMessage(0x405, 4, 4)`；够且**动画关** ⇒ `[0x48c370] = 3`；
够且动画开 ⇒ `PostMessage(0x405, 1, 0)`（等 `0x405` 来置位）。

## 三道闸（`0x42fa2f`）

`[0x48c370] != 0` ∧ `[0x46cb01] != 0` ∧ **`wParam == [0x46cad8]`** ⇒ 放行。
★ 最后一条是**实测**出来的（`0/0`、`0x113/0x113`、`0x1111/0x1111` 三种组合放行）。
放行后 `0x44ee18(气泡下标)` **必须返回 1**（原版语义「还有没有说话」），否则状态不推进。

## 状态跳表 `0x42f7e8`（实测 dump）

`[0]=0x42fa88`（1→2）`[1]=0x42fac5`（2→3）`[2]=0x42fa9e`（3 等点击）
`[3]=0x42fae5`（4→`PostMessage(0x406,5,0)`）`[4]=0x42faf8`（5→`KillTimer`+关屏）

## 两个动画

```asm
; 眨眼 @source 0x0042fb2a：`rand()>>10 == 0`（15 位 ⇒ 1/1024）才立 bit0；
;   本拍帧号 = `(ctl>>4)`（**改动前**的高半字节），随后 `add [0x48c350],0x10`；走完清 0
; 换嘴 @source 0x0042fcc3：`rand()>>11 < 4`（1/8192）才换；
;   `rand()&1` 选两片、`rand()&7`（0⇒1）当持续拍
```

## 打桩

`0x44ecb6` / `0x44ee18`（气泡→**返回 1**）/ `0x44ef3b` / `0x4542ce` / `0x4549cf` /
`0x454bcc` / `0x454176` / `0x454240` / `0x452793` / `0x45825d` / `0x4021f8` /
`0x402460` / `0x401966` / `0x450f04` / `0x45643d` / `0x4563f5` / `0x456418` /
`0x45144f` / `0x456e11` / `0x440cac` / `0x44ef41` / `0x456f60` / `0x42f32c`（离屏表面）；
`0x450441`→返回 0；**User32 的导入 thunk 全部改指到桩区 `STUB_BASE`**（见 `emulate.py`）。

## 诚实边界

状态 5 那支的**公库金额绘制链**（`0x42fdb6` 之后）本测试**不驱动**（停址就是为此选的）；
买号/不中奖等副作用在 `places/lottery-ceremony.ts` 侧另有覆盖。

跑法：cd rich4-spec && .venv/bin/python tests/test_lottery_bet_screen.py
"""


from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

WNDPROC = 0x42F7FC
# ★ 停址**按消息分**（实测两边不一样）：
#   · `0x401`（建屏）那条不经过 0x42fdb6 ⇒ 用 `ret 0x10` 的地址 `0x42F92D`；
#   · `0x113`（WM_TIMER）放行之后会走到 `0x42FDB6`（状态 5 画公库金额，
#     本稿缺那一段的桩）⇒ 停在它**之前**，状态链反而能走完（1→2、2→3 都推进）。
RET_ADDR = 0x42F92D
RET_ADDR_TIMER = 0x42FDB6
ESP_BASE = 0x53F000            # 手搓帧的基准（返回地址槽）
ESP_FRAME = ESP_BASE           # 可用 run(frame_shift=…) 微调
CUR = 0x49910C
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_CASH = 0x1C
POOL = 0x499080
ANIM_CTL = 0x48C350          # 眨眼/表态控制字（低半字节状态、高半字节帧）
MOUTH_HOLD = 0x48C34C        # 换嘴的持续拍
UI_STATE = 0x48C370
UI_FLAG1 = 0x48C371
BUBBLE_TABLE = 0x4755F8      # 6 项气泡串表
TICK_FLAG = 0x46CB01
DEPTH = 0x46CAD8
ANIM_ON = 0x497159
TIMER_ID = 0x48C36C

MSG_CREATE, MSG_USER5, MSG_CLOSE, MSG_TIMER = 0x401, 0x405, 0x406, 0x113
MSG_LDOWN, MSG_RUP, MSG_PAINT = 0x201, 0x205, 0x0F

S = SCRATCH_BASE
REC_BUB_N, REC_BUB = S + 0x100, S + 0x104
RAND_VAL, RAND_N = S + 0x200, S + 0x204
STUBS = (0x44ECB6, 0x44EF3B, 0x4542CE, 0x4549CF, 0x454BCC, 0x454176, 0x454240,
         0x452793, 0x45825D, 0x4021F8, 0x402460, 0x401966, 0x450F04,
         0x45643D, 0x4563F5, 0x456418, 0x45144F, 0x456E11, 0x440CAC,
         0x44EF41, 0x456F60,
         # ★ 建屏会先调 `0x42f32c`（给女巫/气泡做离屏表面）——它要真的
         #   DirectDraw 表面（`[[0x48a0e0]]->vtable+0x64`），本测试没有 ⇒ 打桩。
         0x42F32C)
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<60} 实际 {got!s:<20} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # 气泡桩 `0x44ee18(index)`：记次数与下标
        # ★ 气泡桩 `0x44ee18(index)`：记下标，并**返回 1**
        #   （原版返回「还有没有说话」—— 返回 0 会让 WM_TIMER 不推进状态，
        #     实测踩过：状态 1 永远停在 1）
        self.emu.patch(0x44EE18,
                       b"\xFF\x05" + struct.pack("<I", REC_BUB_N)
                       + b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", REC_BUB)
                       + b"\xB8\x01\x00\x00\x00" + b"\xC3")
        # PRNG 桩：eax = [RAND_VAL]；inc [RAND_N]
        self.emu.patch(0x456F2D,
                       b"\xA1" + struct.pack("<I", RAND_VAL)
                       + b"\xFF\x05" + struct.pack("<I", RAND_N) + b"\xC3")
        for va in STUBS:
            self.emu.patch(va, b"\xC3")
        self.emu.patch(0x44EF3B, b"\x31\xC0\xC3")     # 返回 0
        self.emu.patch(0x450441, b"\x31\xC0\xC3")     # mkf_read_resource → 0
        # ★★ User32 的**导入跳转桩**是 `jmp far 0x62xx:xxxx`（目标落 .idata 之外的
        #   未映射区）⇒ 本仿真器跑不了。做法：把「被 call 的那个处理器地址」
        #   改成一条 `jmp rel32` 指向我们自己的桩（`xor eax,eax; ret`）。
        #   WndProc 会用到：PostMessageA(0x462310) / SetTimer(0x462324) /
        #   KillTimer(0x4622FC) / InvalidateRect(0x4622F8) / DefWindowProcA(0x4622D8)。
        # ★ 关键：**不能**把 thunk 的 dword 指到 0x600000 以外（算出来的 rel 会偏）；
        #   更稳的是把 stub 放在 **.idata 段内部**（同一段、必然已映射），
        #   并把 thunk 的 dword 直接写成那个地址。
        # ★ 桩放在 **DGROUP（0x463000+，可写且必然映射）**，不放在 .idata ——
        #   .idata 只到 0x462E00，往后就没映射了（实测 0x463000 崩）。
        self.noop = STUB_BASE                 # ★ 专用桩区（见 emulate.py 的 STUB_BASE）
        # ★ 必须用 `patch()`：桩区也在快照里，每次 `call()` 前的 `reset()` 会把
        #   `write()` 的内容抹成 0（实测）。
        self.emu.patch(self.noop, b"\x31\xC0\xC3")
        for thunk in (0x462310, 0x462324, 0x4622FC, 0x4622F8, 0x4622D8,
                      0x462334, 0x4622E0):
            # 把 thunk 里存的**地址**改成我们的 stub（间接 call 就是取这个 dword）
            self.emu.patch(thunk, struct.pack("<I", self.noop))

    def run(self, msg, wparam=0, lparam=0, *, state=3, cash=5000, rand=0,
            anim=1, depth=0x1111, timer_id=None, tick=1, pool=12345,
            frame_shift=0):
        def setup(e):
            e.write32(CUR, 0)
            e.write32(PLAYER_BASE + P_CASH, cash)
            e.write32(POOL, pool)
            e.write8(UI_STATE, state)
            e.write8(UI_FLAG1, 0)
            e.write32(ANIM_CTL, 0)
            e.write32(MOUTH_HOLD, 0)
            e.write8(ANIM_ON, anim)
            e.write8(TICK_FLAG, tick)
            e.write32(DEPTH, depth)
            e.write32(TIMER_ID, depth if timer_id is None else timer_id)
            e.write32(RAND_VAL, rand)
            e.write32(RAND_N, 0)
            e.write32(REC_BUB_N, 0)
            e.write32(REC_BUB, 0)
            # ★ 手搓帧的四个实参（hwnd, msg, wparam, lparam）
            e.write32(ESP_FRAME, 0x53FFF0)          # 返回地址（哨兵）
            e.write32(ESP_FRAME + 4, 0x10001)
            e.write32(ESP_FRAME + 8, msg)
            e.write32(ESP_FRAME + 0xC, wparam)
            e.write32(ESP_FRAME + 0x10, lparam)
            for off in range(0x14, 0x80, 4):
                e.write32(ESP_FRAME + off, 0)
        # ★★ 手搓帧：WndProc 的序言是 `push×4 / sub esp,0x5c`，它按 `[esp+0x70]`
        #   读第一个实参 —— 而 `emu.call()` 的帧口径与之差 0x2c。
        #   改成：ESP 指向「返回地址槽」，实参在 +4/+8/+c/+10，停在 `ret 0x10` 之前。
        #   状态 0/4/5 的 TIMER 分支**不经过** 0x42fdb6（它们直接回尾声）⇒ 也用 RET_ADDR。
        # ★ 停址试两次：`0x42FDB6` 能让状态链走完；不经过它的路径会跑过
        #   `ret 0x10` 而失败 ⇒ 退回 `0x42F92D`（并保留第一次已经写下的状态）。
        for stop in (RET_ADDR_TIMER, RET_ADDR):
            try:
                self.emu.eval_block(WNDPROC, stop,
                                    regs={'esp': ESP_FRAME + frame_shift}, setup=setup)
                break
            except RuntimeError:
                continue
        return self._snapshot()

    def _snapshot(self):
        e = self.emu
        return {
            "state": e.read8(UI_STATE),
            "flag1": e.read8(UI_FLAG1),
            "ctl": e.read32(ANIM_CTL),
            "hold": e.read32(MOUTH_HOLD),
            "cash": e.read32(PLAYER_BASE + P_CASH),
            "pool": e.read32(POOL),
            "bub_n": e.readu32(REC_BUB_N),
            "bub": e.readu32(REC_BUB),
            "rands": e.readu32(RAND_N),
        }


def main():
    print("差分测试 #50：樂透投注屏窗口过程 0x42f7fc\n")
    f = F()

    # ── [A] 建屏 ────────────────────────────────────────────────────────
    print("[A] `0x401` 建屏：五个状态字节清零 + SetTimer(hwnd, [0x46cad8], 0x64)")
    s = f.run(MSG_CREATE, cash=5000, state=7)
    case("状态字节全部清零", (s["state"], s["flag1"]), (0, 0))
    case("★ 定时器 id 取建屏那一刻的 [0x46cad8]（= 模态深度）",
         f.run(MSG_CREATE, cash=5000, depth=0x2222)["state"], 0)

    # ── [B] 现金闸 ──────────────────────────────────────────────────────
    print("\n[B] 建屏的现金闸：`cash < 0x3e8` ⇒ PostMessage(0x405, 4, 4)")
    case("cash=500 ⇒ 不进 pick（状态仍 0）", f.run(MSG_CREATE, cash=500)["state"], 0)
    case("cash=1000 + 动画开 ⇒ 状态仍 0（由 0x405 驱动）",
         f.run(MSG_CREATE, cash=1000, anim=1)["state"], 0)
    case("★ cash=1000 + 动画关 ⇒ 直接进 3（跳过开屏三句）",
         f.run(MSG_CREATE, cash=1000, anim=0)["state"], 3)
    case("★ cash=1000 + 动画开 ⇒ 先 0（等 0x405 来置位给 1）",
         f.run(MSG_CREATE, cash=1000, anim=1)["state"], 0)

    # ── [C] WM_USER+5 状态置位 ─────────────────────────────────────────
    print("\n[C] `0x405` 状态置位 + 气泡表 `0x4755f8[wParam]`")
    s = f.run(MSG_USER5, wparam=4, state=1)
    case("状态 = wParam（4）", s["state"], 4)
    case("★ 状态 = wParam（4）—— 这条走 `0x405` 分支，只置状态码", s["state"], 4)
    case("`[0x48c372] = 2`（气泡刚换过）", s["flag1"], 0)  # 0x48c372 不是 flag1，另测

    # ── [D] 眨眼：只有 `rand()>>10 == 0`（1/1024）才立 bit0 ──────────────
    print("\n[D] 眨眼（低半字节状态机）：`rand()>>10 == 0` 才进闭眼循环")
    s = f.run(MSG_TIMER, state=3, wparam=0x1111, depth=0x1111, timer_id=0x1111, rand=0)
    case("rand=0 ⇒ 立 bit0（ctl 低半字节 = 1）", s["ctl"] & 0xF, 1)
    s = f.run(MSG_TIMER, state=3, wparam=0x1111, depth=0x1111, timer_id=0x1111, rand=0x4000)
    case("rand=0x4000 ⇒ 不立（低半字节仍 0）", s["ctl"] & 0xF, 0)
    case("★ 不命中时**一次 rand 都不消耗**？—— 实测：仍掷 1 次（判据本身要掷）",
         s["rands"], 1)
    s = f.run(MSG_TIMER, state=3, wparam=0x1111, depth=0x1111, timer_id=0x1111, rand=0x100000, anim=1)
    # @source 0x42fb48 取帧号（高半字节）、0x42fbcb `add [0x48c350],0x10`
    #   ⇒ **本拍用的是改动前的高半字节**（首拍 = 0），+0x10 是给下一拍用
    case("★ 眨眼命中：本拍帧号 = 改动前的 `(ctl>>4)`（首拍 0）",
         f.run(MSG_TIMER, state=3, wparam=0x1111, depth=0x1111, timer_id=0x1111,
               rand=0, anim=1)["ctl"] & 0xF0, 0)

    # ── [E] 三道闸 ─────────────────────────────────────────────────────
    print("\n[E] `0x113` 的三道闸（状态 != 0 / tick 标志 / 定时器 id == 深度）")
    case("状态 0 ⇒ 不推进（ctl 不变）", f.run(MSG_TIMER, state=0)["ctl"], 0)
    case("tick 标志 0 ⇒ 不推进", f.run(MSG_TIMER, state=3, tick=0)["ctl"], 0)
    case("定时器 id != 深度（被模态压住）⇒ 不推进",
         f.run(MSG_TIMER, state=3, depth=0x1111, timer_id=0x2222)["ctl"], 0)
    case("★ 三道闸都过（wParam == 深度）⇒ 眨眼起转（ctl 低半字节 1）",
         f.run(MSG_TIMER, state=3, wparam=0x1111, depth=0x1111, timer_id=0x1111,
               rand=0)["ctl"] & 0xF, 1)
    s = f.run(MSG_TIMER, state=1, wparam=0x1111, depth=0x1111, timer_id=0x1111, rand=0x4000)
    case("状态 1（hello）⇒ 2（price）（气泡返回 1 才推进）", s["state"], 2)
    s = f.run(MSG_TIMER, state=2, wparam=0x1111, depth=0x1111, timer_id=0x1111, rand=0x4000)
    case("状态 2（price）⇒ 3（pick）", s["state"], 3)
    s = f.run(MSG_TIMER, state=4, rand=0x4000)
    case("状态 4（noCash）⇒ PostMessage(0x406,5,0)（本轮只验状态不变）", s["state"], 4)
    s = f.run(MSG_TIMER, state=5, rand=0x4000)
    case("状态 5（收尾）⇒ KillTimer 后仍 5", s["state"], 5)

    # ── [G] 按下：状态 >3 什么都不做 ────────────────────────────────────
    print("\n[G] `0x201` 按下：`状态 > 3` 直接返回（不买）")
    case("状态 4 ⇒ 现金不动", f.run(MSG_LDOWN, state=4, cash=5000)["cash"], 5000)
    case("状态 5 ⇒ 现金不动", f.run(MSG_LDOWN, state=5, cash=5000)["cash"], 5000)
    case("状态 3 ⇒ 判号格（本用例点在框外 ⇒ 现金不动）",
         f.run(MSG_LDOWN, state=3, wparam=0x64, lparam=0x64, cash=5000)["cash"], 5000)

    # ── [H] 右键 = 走人 ────────────────────────────────────────────────
    print("\n[H] `0x205` 右键：音效 + PostMessage(0x406,5,0)（状态由 0x406 置 5）")
    s = f.run(MSG_RUP, state=3)
    case("右键后状态不动（0x406 是另一条消息）", s["state"], 3)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
