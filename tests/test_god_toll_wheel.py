#!/usr/bin/env python3
"""
通道 2 差分测试 · **神明對過路費的四個跳表片段 + 轉盤的確定性核心**

本文件驱动两块原版机器码（真值只有 `Rich4/rich4.exe`）：

```
[A] 神明對過路費   0x41d741 / 0x41d758 / 0x41d76f / 0x41d788
                   （6 路跳表 0x41d6f1；god 3/4 与「不改变」共用 0x41d79e）
                   分派器入口 0x41d709
[B] 轉盤（旅館/購物中心/保險/航空公司）  0x43f7c6 的確定性核心
                   表 0x475d0c（4 種 × 12 字节，0xff = 空格）
```

## [A] 四个分支**不是函数入口**

它们是分派器 `0x41d709` 的帧内标签，共享尾声 `0x41d79e`：

```asm
; @source 0x0041d709
0041d709  push ebx / push esi / sub esp,0x80
0041d711  edx  = [esp+0x90]              ; arg2 = 填 %s 的文本指针
0041d718  esi  = [esp+0x94]              ; arg3 = 原始租金
0041d71f  ebx  = esi                     ; ★ 调整后金额的初值 = 原值
0041d721  eax  = [esp+0x8c] * 0x68       ; arg1 = 玩家索引
0041d729  al   = byte [eax + 0x496ba7]   ; god_info (+0x3f)
0041d72f  dec al / cmp al,5 / ja 0x41d79e
0041d73a  jmp  dword [eax*4 + 0x41d6f1]
;   表 0x41d6f1（实测 dump）= [0x41d741, 0x41d758, 0x41d79e, 0x41d79e, 0x41d76f, 0x41d788]
0041d741  push edx / push 0x463c67 / lea eax,[esp+8] / push eax / call 0x457110
0041d751  add esp,0xc / sar ebx,1 / jmp 0x41d79e            ; god1 小財神  ÷2
0041d758  ...  push 0x463c80 ... / xor ebx,esi / jmp 0x41d79e ; god2 大財神  免付
0041d76f  ...  push 0x463c95 ... / sar ebx,1 / add ebx,esi / jmp 0x41d79e ; god5 小窮神
0041d788  ...  push 0x463cae ... / lea ebx,[esi+esi]        ; god6 大窮神  ×2（落到 0x41d79e）
0041d79e  cmp ebx,esi / je 0x41d7c9                          ; 金额没变 ⇒ 不弹第二句
0041d7a2  push 0x5dc / lea eax,[esp+4] / push eax / call 0x440cac
0041d7b4  test ebx,ebx / jne 0x41d7c9
0041d7b8  push esi / mov esi,[esp+0x90] / push esi / call 0x44f567
0041d7c9  mov eax,ebx                                        ; ★ 唯一金额出口
0041d7cb  add esp,0x80 / pop esi / pop ebx / ret
```

★★ **必须用 `eval_block(片段入口, 0x41d79e)` + 手搓帧**（gaps §7.3 第 14 项做法⑤ /
§7.81(1)）：四个分支里的 `sprintf` 目标是

```
push edx        ; esp = E-4
push fmt        ; esp = E-8
lea eax,[esp+8] ; eax = E        ← ★ 就是片段入口时的 [esp]
push eax
call sprintf    ; sprintf(dst = E, fmt, edx)
```

即 **`sprintf` 写片段入口的 `[esp]`**（分派器帧里的 0x80 字节局部区）。
用「把尾声打成 `ret` 再 `emu.call`」那一套，返回地址会被格式串覆盖、最后 `ret` 跳飞；
`eval_block` 在 EIP 命中停址时**不执行**该条指令，覆盖 `[esp]` 无害。
停址 `0x41d79e` 是**指令边界**（`jmp` 的落点，也是 god 3/4 的目标）。

## [B] 轉盤 0x43f7c6 是 UI 状态机，本测试只驱动其**确定性核心**

```asm
; @source 0x0043f7cd  起点
0043f7cd  edx=1 / [esp+0x34]=edx / ebx=edx / ebp=0
0043f7da  call 0x456f2d                      ; rand() ★ 全函数**只掷这一次**
0043f7df  mov edx,eax / mov esi,0xc
0043f7e6  sar edx,0x1f / idiv esi            ; edx = rand() % 12（有符号余数）
0043f7eb  mov [0x48c50c],edx                 ; ★ 随机起点

; @source 0x0043f127  每帧步进：指针 +1，满 12 归 0
0043f12e  mov edx,[0x48c50c] / inc edx / mov [0x48c50c],edx
0043f13b  cmp edx,0xc / jne 0x43f148 / xor ebx,ebx / mov [0x48c50c],ebx

; @source 0x0043f9ab（状态 3 = 减速 + 判空格）
0043f9ab  eax = ebp - [esp+0x2c] ; esi = [esp+0x34] ; 不等 ⇒ 本帧不动作
0043f9bb  call 0x43f127(1)                   ; 走一格
0043f9c3  [esp+0x2c] = ebp
0043f9c7  dec [esp+0x30] ; 归零 ⇒ [esp+0x30]=3, [esp+0x34]++    ; 间隔 1→2→3→4→5
0043f9df  cmp [esp+0x34],5 / jl 0x43fa23     ; 间隔 <5 不看格子
0043f9e6  eax = arg1*12 + [0x48c50c]         ; arg1 = 轉盤编号（[esp+0x4c]）
0043f9fa  cmp byte [eax + 0x475d0c],0xff
0043fa01  je  0x43fa23                       ; 空格 ⇒ 继续转
0043fa03  ebx = 5                            ; 数字格 ⇒ 进入收尾
...
0043fabd  eax = arg1*12 + [0x48c50c]
0043fad1  al  = byte [eax + 0x475d0c]        ; ★ 返回值 = 表项（零扩展）
```

★ **为什么「起点之后第一个非空格」是机械化结论**（[B6] 逐帧驱动验证的正是这条）：
状态 3 的间隔从 1 起、每 3 次动作 +1，到间隔 5 之前共动作 `3×4 = 12` 次
——**恰好一整圈**，指针回到 `rand()%12`；那第 12 次动作同时触发第一次看格子。
之后每隔 5 帧走一格再看。⇒ 结果 = 从随机起点**顺时针**的第一个 `!= 0xff` 格。

★ **本测试未驱动的部分（明确边界）**：`0x43f7c6` 的真人点击状态机
（状态 1→2 的鼠标分支 `0x43fa4a`、`0x46230c` 取消息、状态 5 的 `0x28` 帧停顿、
以及整套 DirectDraw blit/音效调用），以及状态机的**画面**。本测试只钉住
「起点、顺时针步进、空格判据、表项返回」这四件纯规则事实。

## 打桩清单

| VA | 原用途 | 桩 | 影响 |
|---|---|---|---|
| `0x00457110` | `sprintf(dst,fmt,…)` | 记 `dst/fmt/第3实参` + 计数，返回 0 | 只用于**读实参**；被测的是压栈次序与目标地址 |
| `0x00440cac` | 金额→显示串（尾部第一句） | 计数器 + `ret` | [A4] 判「弹不弹第二句」的控制流 |
| `0x0044f567` | `ebx==0` 时的那段收尾 | 计数器 + `ret` | 同上 |
| `0x00456f2d` | CRT `rand()` | 从数据槽 `[S_RAND]` 读（[B2] 的定点支） | 让 12 个起点可控 |
| `0x00456f23` | 取 PRNG 状态指针 | `mov eax,RNG_STATE; ret` | [B2] 用**真** `0x456f2d` 验「只掷 1 次」 |
| `0x0043f127` | 轉盤步进 + 音效 + blit | 只保留前 4 条「+1 mod 12」语义（**保留 `ebx`**） | [B6] 整段状态机驱动；音效/blit 属表现层 |
| `0x004542e9` | 音效 | `ret` | [B4]/[B6] 命中数字格后的那一支 |

跑法：cd rich4-spec && .venv/bin/python tests/test_god_toll_wheel.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<64} 实际 {got!s:<26} 期望 {want!s}")
    return ok


def s32(v):
    """把 32 位无符号读回值按有符号解释（原版金额走 `eax`/`ebx` 有符号读法）。"""
    return v - 0x100000000 if v >= 0x80000000 else v


# ══════════════════════════════════════════════════════════════════════════
#  [A] 神明對過路費
# ══════════════════════════════════════════════════════════════════════════
JT_GOD_TOLL = 0x41D6F1
DISPATCH = 0x41D709
B_G1, B_G2, B_G5, B_G6 = 0x41D741, 0x41D758, 0x41D76F, 0x41D788
TAIL = 0x41D79E                       # ★ 共享尾声 = god 3/4 与「不改变」的目标
TAIL_RET_ADDR = 0x41D7C9              # `mov eax,ebx`
TAIL_RET = 0x41D7D3                   # `ret`（停在这里可读 eax）
FMT_OF = {B_G1: 0x463C67, B_G2: 0x463C80, B_G5: 0x463C95, B_G6: 0x463CAE}
SPRINTF = 0x457110
MOUNT_440CAC, MOUNT_44F567 = 0x440CAC, 0x44F567

FRAME_A = 0x53F000                    # 手搓栈帧基址（= 片段入口的 esp，也在大栈内）
SCR = SCRATCH_BASE
S_DST, S_FMT, S_ARG, S_CNT = SCR + 0x1000, SCR + 0x1004, SCR + 0x1008, SCR + 0x100C
S_C440, S_C44F = SCR + 0x1100, SCR + 0x1104
TEXT_PTR = SCR + 0x2000               # 填 %s 的「文本」——本函数不解引用它
TEXT_PTR2 = 0x4630F4
P_BASE, P_STRIDE, P_GOD = 0x496B68, 0x68, 0x3F


class GodToll:
    """四个跳表片段的**直接入口**驱动（不经分派器序言）。"""

    # ── 桩 ────────────────────────────────────────────────────────────
    def _stub_sprintf(self, e):
        # cdecl：入口 [esp]=返回地址 ⇒ dst=[esp+4]、fmt=[esp+8]、第3实参=[esp+0xc]
        e.patch(SPRINTF,
                b"\x8B\x4C\x24\x04" + b"\x89\x0D" + struct.pack("<I", S_DST)
                + b"\x8B\x4C\x24\x08" + b"\x89\x0D" + struct.pack("<I", S_FMT)
                + b"\x8B\x4C\x24\x0C" + b"\x89\x0D" + struct.pack("<I", S_ARG)
                + b"\xFF\x05" + struct.pack("<I", S_CNT)
                + b"\x31\xC0\xC3")

    def _stub_mounts(self, e):
        e.patch(MOUNT_440CAC, b"\xFF\x05" + struct.pack("<I", S_C440) + b"\xC3")
        e.patch(MOUNT_44F567, b"\xFF\x05" + struct.pack("<I", S_C44F) + b"\xC3")

    def _zero(self, e):
        for s in (S_DST, S_FMT, S_ARG, S_CNT, S_C440, S_C44F):
            e.write32(s, 0)

    # ── 驱动片段 ──────────────────────────────────────────────────────
    def branch(self, branch, toll, text=TEXT_PTR):
        """从**分支入口**进，停在共享尾声 0x41d79e（指令边界）。返回 ebx。"""
        emu = Emu()

        def setup(e):
            self._stub_sprintf(e)
            self._zero(e)
        out = emu.eval_block(branch, TAIL,
                             regs={"esp": FRAME_A, "edx": text,
                                   "ebx": toll & 0xFFFFFFFF, "esi": toll & 0xFFFFFFFF},
                             setup=setup)
        self.emu = emu
        return {"ebx": out["regs"]["ebx"], "esi": out["regs"]["esi"],
                "dst": emu.readu32(S_DST), "fmt": emu.readu32(S_FMT),
                "arg": emu.readu32(S_ARG), "n": emu.readu32(S_CNT)}

    def tail(self, ebx, esi, stop=TAIL_RET_ADDR):
        """从共享尾声入口 0x41d79e 进（god 3/4「不改变」的实际目标）。"""
        emu = Emu()

        def setup(e):
            self._stub_mounts(e)
            self._zero(e)
        out = emu.eval_block(TAIL, stop,
                             regs={"esp": FRAME_A, "ebx": ebx & 0xFFFFFFFF, "esi": esi & 0xFFFFFFFF},
                             setup=setup)
        return {"ebx": out["regs"]["ebx"], "eax": out["regs"]["eax"],
                "c440": emu.readu32(S_C440), "c44f": emu.readu32(S_C44F),
                "n": emu.readu32(S_CNT)}

    def dispatch(self, god, stop, player=0, toll=1000, extra_gods=None):
        """从**分派器真入口** 0x41d709 进，停在 `stop`（= 期望落到的那个片段入口）。"""
        emu = Emu()

        def setup(e):
            self._stub_sprintf(e)
            self._zero(e)
            e.write8(P_BASE + player * P_STRIDE + P_GOD, god)
            for p, gd in (extra_gods or {}).items():
                e.write8(P_BASE + p * P_STRIDE + P_GOD, gd)
            e.write32(FRAME_A + 0x04, player)      # arg1 付款方（序言 0x88 之前）
            e.write32(FRAME_A + 0x08, TEXT_PTR)    # arg2 文本指针
            e.write32(FRAME_A + 0x0C, toll)        # arg3 原始租金
        out = emu.eval_block(DISPATCH, stop, regs={"esp": FRAME_A}, setup=setup)
        self.emu = emu
        return {"ebx": out["regs"]["ebx"], "esi": out["regs"]["esi"],
                "n": emu.readu32(S_CNT)}


# ── [A3] 每档全部边界（机器真值，事先手工推好，再逐条与 exe 对） ──────────
#   （下面每条的期望值都是照汇编手推的，本测试的作用就是判定手推对不对。）
AMOUNT_CASES = {
    #                toll,   期望 ebx（有符号）
    B_G1: [(0, 0), (1, 0), (2, 1), (3, 1),                    # 奇数**向下**取整
           (999, 499), (1000, 500), (1001, 500),
           (-1, -1), (-2, -1), (-3, -2),                       # 负数仍是算术右移
           (0x7FFFFFFF, 0x3FFFFFFF), (0x40000000, 0x20000000),
           (-2147483648, -1073741824)],
    B_G2: [(0, 0), (1, 0), (999, 0), (-5, 0),
           (0x7FFFFFFF, 0), (-2147483648, 0)],                 # `xor ebx,esi` 恒 0
    B_G5: [(0, 0), (1, 1), (2, 3), (3, 4),                    # (toll>>1) + toll
           (999, 1498), (1000, 1500), (1001, 1501),            # ★ 非 ×1.5
           (-1, -2), (-2, -3), (-3, -5),
           (0x40000000, 1610612736),
           (0x7FFFFFFF, -1073741826),                          # ★ 32 位回绕
           (-2147483648, 1073741824)],                         # ★ 32 位回绕
    B_G6: [(0, 0), (1, 2), (999, 1998), (1000, 2000),
           (-1, -2), (-2, -4), (1000000000, 2000000000),
           (0x40000000, -2147483648),                          # ★ 32 位回绕
           (0x7FFFFFFF, -2), (-2147483648, 0)],                # ★ 32 位回绕
}

# ── [A5] 复刻 `god-toll.ts` 的语义（1:1 手抄 TS，用于逐输入对照） ──────────
def remake_adjust_toll_by_god(toll, god):
    """`rich4-remake/packages/core/src/rules/god-toll.ts:57-86` 的直译。"""
    if god < 1 or god > 6:
        return {"toll": toll, "changed": False}
    nxt = toll
    if god == 1:
        nxt = toll >> 1                     # TS `toll >> 1`（int32 算术右移）
    elif god == 2:
        nxt = 0
    elif god in (3, 4):
        pass
    elif god == 5:
        nxt = (toll >> 1) + toll            # ★ JS 加法 = double，不回绕
    elif god == 6:
        nxt = toll + toll                   # ★ 同上
    return {"toll": nxt, "changed": nxt != toll}


# ══════════════════════════════════════════════════════════════════════════
#  [B] 轉盤確定性核心
# ══════════════════════════════════════════════════════════════════════════
WHEEL_TAB = 0x475D0C
WHEEL_POS = 0x48C50C                  # 起点/当前格
RAND = 0x456F2D
RAND_ACCESSOR = 0x456F23
RNG_STATE = SCR + 0x900
S_RAND = SCR + 0x800
ADV_WALK = 0x43F127                   # 步进（+音效 +blit）
SOUND_2E9 = 0x4542E9
INIT_A, INIT_B = 0x43F7CD, 0x43F7F1   # 起点段
ADV_A, ADV_B = 0x43F12E, 0x43F148     # 「+1 mod 12」
CHK_A, CHK_B = 0x43F9E6, 0x43FA23     # 减速 + 空格判据
RET_A, RET_B = 0x43FABD, 0x43FADC     # 返回表项
STATE_A, STATE_B = 0x43F9AB, 0x43FA23 # 状态 3 整块（[B6]）
FRAME_W = 0x53F000
WHEEL_ROWS = [                        # 实测 dump（1 字节 × 48）
    [1, 0xFF, 0, 0xFF, 1, 0xFF, 2, 0xFF, 3, 0xFF, 2, 0xFF],
    [0xFF, 0xFF, 1, 0xFF, 0xFF, 4, 0xFF, 3, 0xFF, 0xFF, 2, 0xFF],
    [1, 0xFF, 6, 0xFF, 5, 0xFF, 4, 0xFF, 3, 0xFF, 2, 0xFF],
    [5, 0xFF, 3, 0xFF, 30, 0xFF, 20, 0xFF, 15, 0xFF, 10, 0xFF],
]
# 复刻 `facility.ts:292-297` 声明的同一张表（用于 MATCH 判定）
REMAKE_WHEEL_TABLE = [
    [1, 0xff, 0, 0xff, 1, 0xff, 2, 0xff, 3, 0xff, 2, 0xff],
    [0xff, 0xff, 1, 0xff, 0xff, 4, 0xff, 3, 0xff, 0xff, 2, 0xff],
    [1, 0xff, 6, 0xff, 5, 0xff, 4, 0xff, 3, 0xff, 2, 0xff],
    [5, 0xff, 3, 0xff, 30, 0xff, 20, 0xff, 15, 0xff, 10, 0xff],
]


def first_nonblank(wheel, start):
    """手工推：从 start 顺时针找第一个 != 0xff 的格。返回 (格号, 值, 偏移)。"""
    for off in range(12):
        p = (start + off) % 12
        v = WHEEL_ROWS[wheel][p]
        if v != 0xFF:
            return p, v, off
    return None


def remake_spin_wheel(wheel, rand_value):
    """`facility.ts:304-314` 的直译。"""
    table = remake_table(wheel)
    if table is None:
        return 0
    slot = ((rand_value % 12) + 12) % 12
    for _ in range(12):
        v = table[slot]
        if v != 0xFF:
            return v
        slot = (slot + 1) % 12
    return 0


def remake_table(wheel):
    return REMAKE_WHEEL_TABLE[wheel] if 0 <= wheel < 4 else None


class Wheel:
    """`0x43f7c6` 的确定性核心：起点段 / 步进 / 空格判据 / 表项返回 / 整段驱动。"""

    # ── 桩 ────────────────────────────────────────────────────────────
    def _stub_rand_slot(self, e):
        e.patch(RAND, b"\xA1" + struct.pack("<I", S_RAND) + b"\xC3")

    def _stub_rand_real(self, e):
        e.patch(RAND_ACCESSOR, b"\xB8" + struct.pack("<I", RNG_STATE) + b"\xC3")

    def _stub_advance(self, e):
        """`0x43f127` 的步进语义（+1、满 12 归 0）；★ **用 eax 而不是 ebx**，
        因为原函数 `push ebx` 保住了调用方的状态寄存器。"""
        p = struct.pack("<I", WHEEL_POS)
        e.patch(ADV_WALK,
                b"\xA1" + p + b"\x40" + b"\xA3" + p          # mov eax,[POS]; inc eax; mov [POS],eax
                + b"\x83\xF8\x0C" + b"\x75\x07"              # cmp eax,12; jne ret
                + b"\x31\xC0" + b"\xA3" + p + b"\xC3")       # xor eax,eax; mov [POS],eax; ret

    def _stub_sound(self, e):
        e.patch(SOUND_2E9, b"\xC3")

    # ── 驱动 ──────────────────────────────────────────────────────────
    def init(self, rand_value):
        """起点段 0x43f7cd–0x43f7f1（`rand()%12` 落 [0x48c50c]）。"""
        emu = Emu()
        self._stub_rand_slot(emu)

        def setup(e):
            e.write32(S_RAND, rand_value & 0xFFFFFFFF)
            e.write32(WHEEL_POS, 0x0BADF00D)
            e.write32(FRAME_W + 0x34, 0)
        out = emu.eval_block(INIT_A, INIT_B, regs={"esp": FRAME_W}, setup=setup)
        return {"pos": emu.readu32(WHEEL_POS), "ebx": out["regs"]["ebx"],
                "ebp": out["regs"]["ebp"], "ival": emu.readu32(FRAME_W + 0x34)}

    def init_real_rand(self, seed):
        """起点段 + **真** `0x456f2d`：验证只掷 1 次（PRNG 状态恰好前进一步）。"""
        emu = Emu()
        self._stub_rand_real(emu)
        emu.scratch_write(RNG_STATE, struct.pack("<I", 0))
        emu.call(0x456F50, [seed])
        seeded = struct.unpack("<I", emu.scratch_read(RNG_STATE, 4))[0]

        def setup(e):
            e.write32(WHEEL_POS, 0x0BADF00D)
            e.write32(FRAME_W + 0x34, 0)
        emu.eval_block(INIT_A, INIT_B, regs={"esp": FRAME_W}, setup=setup)
        st = struct.unpack("<I", emu.scratch_read(RNG_STATE, 4))[0]
        exp_state = (seed * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
        return {"seeded": seeded, "pos": emu.readu32(WHEEL_POS), "state": st,
                "exp_state": exp_state, "exp_val": (exp_state >> 16) & 0x7FFF}

    def advance(self, pos):
        """步进片段 0x43f12e–0x43f148。"""
        emu = Emu()

        def setup(e):
            e.write32(WHEEL_POS, pos)
        emu.eval_block(ADV_A, ADV_B, regs={"esp": FRAME_W}, setup=setup)
        return emu.readu32(WHEEL_POS)

    def check_cell(self, wheel, pos):
        """空格判据：return True = 数字格（ebx 被置 5），False = 0xff（ebx 仍 3）。"""
        emu = Emu()
        self._stub_sound(emu)

        def setup(e):
            e.write32(WHEEL_POS, pos)
            e.write32(FRAME_W + 0x4C, wheel)     # arg1 = 轉盤编号
        out = emu.eval_block(CHK_A, CHK_B, regs={"esp": FRAME_W, "ebx": 3}, setup=setup)
        return out["regs"]["ebx"] == 5

    def ret_byte(self, wheel, pos):
        """返回片段：eax = byte[0x475d0c + wheel*12 + pos]（零扩展）。"""
        emu = Emu()

        def setup(e):
            e.write32(WHEEL_POS, pos)
            e.write32(FRAME_W + 0x4C, wheel)
        out = emu.eval_block(RET_A, RET_B, regs={"esp": FRAME_W}, setup=setup)
        return out["regs"]["eax"]

    def spin(self, wheel, start):
        """整段状态 3 驱动：减速计数（1→5、每档 3 次）+ 空格判据，直到停在数字格。

        返回 (格号, 动作次数)。**动作次数 = 12 + 顺时针偏移**是机械化的可证伪断言。
        """
        emu = Emu()
        self._stub_advance(emu)
        self._stub_sound(emu)
        last, cnt, ival = 0, 3, 1            # 状态 2 交给状态 3 的三个局部量
        pos = start
        acts = 0
        for frame in range(1, 400):
            def setup(e, last=last, cnt=cnt, ival=ival, pos=pos, wheel=wheel):
                e.write32(WHEEL_POS, pos)
                e.write32(FRAME_W + 0x2C, last)
                e.write32(FRAME_W + 0x30, cnt)
                e.write32(FRAME_W + 0x34, ival)
                e.write32(FRAME_W + 0x4C, wheel)
            out = emu.eval_block(STATE_A, STATE_B,
                                 regs={"esp": FRAME_W, "ebp": frame, "ebx": 3}, setup=setup)
            pos = emu.readu32(WHEEL_POS)
            new_last = emu.readu32(FRAME_W + 0x2C)
            if new_last == frame:
                acts += 1
            last = new_last
            cnt = emu.readu32(FRAME_W + 0x30)
            ival = emu.readu32(FRAME_W + 0x34)
            if out["regs"]["ebx"] == 5:
                return pos, acts
        return None


# ══════════════════════════════════════════════════════════════════════════
def group_a():
    print("[A] 神明對過路費：四個跳表片段 0x41d741/58/6f/88 + 共享尾 0x41d79e")
    g = GodToll()

    print("\n[A1] 跳表 0x41d6f1（6 项）与分派器 0x41d709 的走向")
    emu0 = Emu()
    table = [struct.unpack("<I", emu0.read(JT_GOD_TOLL + 4 * i, 4))[0] for i in range(6)]
    case("表 6 项地址逐项相同",
         [hex(x) for x in table],
         [hex(x) for x in (B_G1, B_G2, TAIL, TAIL, B_G5, B_G6)])
    case("★ god 3/4（福神）指向**与「不改变」同一个地址** 0x41d79e",
         (table[2], table[3]), (TAIL, TAIL))
    for god, stop in ((1, B_G1), (2, B_G2), (3, TAIL), (4, TAIL), (5, B_G5), (6, B_G6)):
        r = g.dispatch(god, stop)
        case(f"god={god} ⇒ 分派到 {hex(stop)}（停址命中即证明走向）",
             (r["ebx"] & 0xFFFFFFFF, r["esi"] & 0xFFFFFFFF), (1000, 1000))
    for god in (0, 7, 8, 0x0F, 0x0E, 0x20, 0xFF):
        r = g.dispatch(god, TAIL_RET_ADDR, toll=777)
        case(f"god={god} 越界 ⇒ 不落跳表、一次 sprintf 都不打、金额原样",
             (r["n"], s32(r["ebx"])), (0, 777))
    r = g.dispatch(1, TAIL, player=2)
    case("god_info 取自 arg1*0x68 + 0x496ba7（player=2 也命中 god 1；停到汇合点看金额）",
         (r["n"], s32(r["ebx"])), (1, 500))
    r = g.dispatch(1, TAIL, player=0, toll=1000, extra_gods={2: 6})
    case("★ player2 身上是 god 6 **不影响** player0 的 god 1 判定",
         (r["n"], s32(r["ebx"])), (1, 500))
    r = g.dispatch(6, TAIL, player=2, toll=1000, extra_gods={0: 1})
    case("★ 反向：player0=god1 不影响 player2 的 god 6（取址带步长 0x68）",
         (r["n"], s32(r["ebx"])), (1, 2000))

    print("\n[A2] 四个片段直接驱动：`sprintf` 的 dst / fmt / 第3实参 / 次数")
    for branch, name in ((B_G1, "god1 小財神"), (B_G2, "god2 大財神"),
                         (B_G5, "god5 小窮神"), (B_G6, "god6 大窮神")):
        r = g.branch(branch, 1000)
        case(f"{name} @{hex(branch)} ⇒ dst = **片段入口的 [esp]** = 0x{FRAME_A:x}",
             r["dst"], FRAME_A)
        case(f"  {name} 的格式串 = 0x{FMT_OF[branch]:x}", r["fmt"], FMT_OF[branch])
        case(f"  {name} 第3实参 = 传入的文本指针", r["arg"], TEXT_PTR)
        case(f"  {name} 恰好 sprintf 一次", r["n"], 1)
    r = g.branch(B_G1, 1000, text=TEXT_PTR2)
    case("★ 第3实参随调用方给的第2实参走（换一个指针 => 记录也跟着换）",
         (r["arg"], r["fmt"], r["n"]), (TEXT_PTR2, FMT_OF[B_G1], 1))
    r = g.tail(1000, 1000)                            # god 3/4 的实际目标
    case("★ god 3/4 走的 0x41d79e 路径**一次 sprintf 都不打**", r["n"], 0)

    print("\n[A3] 金额（`ebx` = 函数返回的 `eax`）：每档全部边界")
    for branch, name in ((B_G1, "god1 小財神 sar ebx,1"),
                         (B_G2, "god2 大財神 xor ebx,esi"),
                         (B_G5, "god5 小窮神 sar;add"),
                         (B_G6, "god6 大窮神 lea [esi+esi]")):
        for toll, want in AMOUNT_CASES[branch]:
            got = s32(g.branch(branch, toll)["ebx"])
            case(f"{name}  toll={toll:<12} ⇒ {want}", got, want)

    print("\n[A4] 共享尾 0x41d79e：不变支 / 返回值 / 两条提示分支")
    for toll in (0, 1, 999, -1, 0x7FFFFFFF):
        r = g.tail(toll, toll)                        # ebx == esi ⇒ je
        case(f"ebx==esi=={toll} ⇒ 不弹提示（0x440cac 0 次）且金额原样",
             (r["c440"], r["c44f"], s32(r["ebx"])), (0, 0, toll))
    r = g.tail(0, 0)
    case("ebx==esi==0 ⇒ 依然一次都不弹（`cmp/je` 先于 `test ebx,ebx`）",
         (r["c440"], r["c44f"]), (0, 0))
    r = g.tail(500, 1000)
    case("ebx(500)!=esi(1000) ⇒ 弹一次金额串、**不**走 ebx==0 的收尾",
         (r["c440"], r["c44f"]), (1, 0))
    r = g.tail(0, 1000)
    case("★ ebx==0 且 esi!=0（大財神免付）⇒ 金额串 + 收尾 `0x44f567` 各一次",
         (r["c440"], r["c44f"]), (1, 1))
    r = g.tail(0, -1000)
    case("★ 判据是 `test ebx,ebx`（只认 0）⇒ esi 为负一样走两条",
         (r["c440"], r["c44f"]), (1, 1))
    for toll in (0, 5, -5, 1000, 0x7FFFFFFF, -2147483648):
        r = g.tail(toll, toll, stop=TAIL_RET)
        case(f"返回值 `eax`（走到 0x41d7d3 的 ret 前）= ebx = {toll}",
             s32(r["eax"]), toll)

    print("\n[A5] 与复刻 `rules/god-toll.ts` 对照（MATCH / DISCREPANCY）")
    parity_inputs = [0, 1, 2, 3, 4, 7, 8, 99, 100, 499, 500, 999, 1000, 1001,
                     12345, 1 << 20, -1, -2, -3, -999, -100000]
    for god in range(0, 9):
        bad = []
        for toll in parity_inputs:
            if god in (1, 2, 5, 6):
                machine = s32(g.branch({1: B_G1, 2: B_G2, 5: B_G5, 6: B_G6}[god], toll)["ebx"])
            else:
                machine = s32(g.tail(toll, toll)["ebx"])
            rm = remake_adjust_toll_by_god(toll, god)
            if machine != rm["toll"] or (rm["changed"] != (machine != toll)):
                bad.append((toll, machine, rm["toll"], rm["changed"]))
        case(f"god={god}：{len(parity_inputs)} 个 int32 域内输入 逐项 MATCH", bad, [])
    for branch, god, toll in ((B_G5, 5, 0x7FFFFFFF), (B_G6, 6, 0x7FFFFFFF),
                              (B_G6, 6, 0x40000000), (B_G5, 5, -2147483648)):
        machine = s32(g.branch(branch, toll)["ebx"])
        rm = remake_adjust_toll_by_god(toll, god)
        case(f"★ DISCREPANCY：god={god} toll={toll} 原版 32 位回绕 = {machine}，"
             f"复刻 JS 加法 = {rm['toll']}",
             (machine, rm["toll"] != machine), (machine, True))


def group_b():
    print("\n[B] 轉盤確定性核心：0x43f7c6 的起点/步进/空格判据/表项返回")
    w = Wheel()

    print("\n[B1] 表 0x475d0c（4 種 × 12 字节），并对照复刻 `facility.ts:292-297`")
    emu = Emu()
    raw = [emu.read8(WHEEL_TAB + i) for i in range(48)]
    for wheel in range(4):
        case(f"轉盤 {wheel} 的 12 字节", raw[wheel * 12:(wheel + 1) * 12], WHEEL_ROWS[wheel])
    case("整表 48 字节", raw, [v for row in WHEEL_ROWS for v in row])
    for wheel in range(4):
        case(f"★ 复刻 WHEEL_TABLE[{wheel}] == exe 表（facility.ts:293-296）",
             REMAKE_WHEEL_TABLE[wheel], WHEEL_ROWS[wheel])

    print("\n[B2] 起点：`[0x48c50c] = rand() % 12`（0x43f7da–0x43f7eb）")
    for v in list(range(12)) + [12, 13, 23, 24, 0x7FFF]:
        r = w.init(v)
        case(f"rand()={v:<6} ⇒ 起点 {v % 12}", r["pos"], v % 12)
    r = w.init(5)
    case("同一段还把 状态寄存器置 1（ebx）、[esp+0x34]=1、ebp=0",
         (r["ebx"], r["ebp"], r["ival"]), (1, 0, 1))
    case("★ 起点段把旧值 0x0badf00d 覆盖掉（确实写了 [0x48c50c]）", r["pos"] != 0x0BADF00D, True)
    for seed in (0x12345678, 0x0BADF00D, 0x00000001, 0xFFFFFFFF):
        r = w.init_real_rand(seed)
        case(f"真 PRNG 种子 0x{seed:08x}：状态恰好前进 **1** 步",
             (r["seeded"], r["state"]), (seed, r["exp_state"]))
        case(f"  起点 = 该次 rand()%12 = {r['exp_val'] % 12}", r["pos"], r["exp_val"] % 12)

    print("\n[B3] 顺时针步进 `[0x48c50c] = ([0x48c50c]+1) % 12`（0x43f12e–0x43f148）")
    for v in range(12):
        case(f"指针 {v} ⇒ {(v + 1) % 12}", w.advance(v), (v + 1) % 12)

    print("\n[B4] 空格判据 `cmp byte[eax+0x475d0c],0xff`（0x43f9e6–0x43fa01）")
    for wheel in range(4):
        for pos in range(12):
            on = WHEEL_ROWS[wheel][pos] != 0xFF
            case(f"轉盤 {wheel} 格 {pos:<2}（值 {WHEEL_ROWS[wheel][pos]:>3}）⇒ "
                 f"{'数字格(ebx=5)' if on else '空格(继续转)'}",
                 w.check_cell(wheel, pos), on)

    print("\n[B5] 返回 `byte[0x475d0c + 轉盤*12 + 格]`（0x43fabd–0x43fad7）")
    for wheel in range(4):
        for pos in range(12):
            case(f"轉盤 {wheel} 格 {pos:<2} ⇒ {WHEEL_ROWS[wheel][pos]}",
                 w.ret_byte(wheel, pos), WHEEL_ROWS[wheel][pos])

    print("\n[B6] 整段状态机驱动（状态 3 的减速计数 + 空格判据）")
    print("     ★ 12 次动作 = 一整圈 ⇒ 第一次看格子时指针已回到起点")
    for wheel in range(4):
        for start in range(12):
            exp_p, exp_v, off = first_nonblank(wheel, start)
            got = w.spin(wheel, start)
            case(f"轉盤 {wheel} 起点 {start:<2} ⇒ 停在格 {exp_p}（值 {exp_v}），"
                 f"动作 {12 + off} 次",
                 got, (exp_p, 12 + off))
            pos_ret = got[0] if got else exp_p
            case(f"  同一起点用返回片段读回 = {exp_v}", w.ret_byte(wheel, pos_ret), exp_v)

    print("\n[B7] 与复刻 `rules/facility.ts` 的 `spinWheel` 对照")
    for wheel in range(4):
        bad = []
        for randv in range(0, 12 * 5):
            exp_p, exp_v, _ = first_nonblank(wheel, randv % 12)
            if w.ret_byte(wheel, exp_p) != remake_spin_wheel(wheel, randv):
                bad.append((randv, exp_v, remake_spin_wheel(wheel, randv)))
        case(f"轉盤 {wheel}：rand 值 0..59 共 60 输入 ⇒ spinWheel 全 MATCH", bad, [])
    case("★ 边界：wheel 越界时复刻兜底返 0（原版无调用者这么传）",
         remake_spin_wheel(-1, 5), 0)
    case("★ 边界：rand 为负时复刻先归一取模（-1 ⇒ 格 11 ⇒ 转一圈 ⇒ 值 1）；"
         "原版有符号 idiv 会去读**上一行末字节**，无调用者能触发",
         remake_spin_wheel(0, -1), 1)


def main():
    print("通道 2 差分测试 · 神明對過路費四個跳表片段 + 轉盤確定性核心\n")
    group_a()
    group_b()
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
