#!/usr/bin/env python3
"""
通道 2 差分测试 · **樂透開獎演出（開獎屏）三支**

| 组 | VA | 大小 | 一句话语义 |
|---|---|---|---|
| [A] | `0x00431712` | 256 B（`functions.json`）| **开屏判据 + 建屏包装**：扫 36 个号码槽，一张都没卖出（`eax` 扫到 0x24）⇒ 直接返回；否则装载 4 张 Panel、注册窗口过程、跑模态、再逐个释放 |
| [B] | `0x0043036C` | 268 B（`functions.json`）／可达 281 B | 開獎屏状态机**状态 2 处理器**：置状态 3、清帧计数、铺开奖画面、起摇球机动画 |
| [C] | `0x004308F3` | 432 B | 状态机**状态 8 处理器**：铺收尾画面、把两颗中奖号球按 `[0x48c37d]`/`[0x48c37e]` 贴回来、置状态 9 说收场白 |

### 这些函数是什么（先说清结构，再谈规则）

`0x431712` 的**唯一 `E8` 站点是 `0x41d094`**（字节级 `gen/rel32-calls.json`）—— 日期推进里的
「低字节 == 0x0f ⇒ 先 `0x42ba97`（企業分紅）再 `0x431712`」那一支；复刻侧对应
`places/company.ts:326` 的 `DIVIDEND_DAY` 与 `places/lottery.ts:233` 的 `LOTTERY_DRAW_DAY`。

`0x43036C`/`0x4308F3` **没有任何 `call` 调用者** —— 它们是開獎屏跳表 `0x4300d0` 的成员，
分发在窗口过程 `0x43010c` 的 `WM_TIMER(0x113)` 支：

```asm
; @source 0x0043021b
0043021b  mov al, byte [0x48c37b]      ; 状态字节
00430220  dec al                       ; ★ 下标 = 状态 − 1
00430222  cmp al, 9 / ja 默认           ; 就地等待
0043022f  jmp dword ptr [eax*4 + 0x4300d0]
; 跳表（实测 dump，10 项）：
;   [0]=0x430236 [1]=0x43036C [2]=0x43024C [3]=0x430485 [4]=0x43024C
;   [5]=0x4306FF [6]=0x4308E0 [7]=0x4308F3 [8]=0x430AA3 [9]=0x430AB5
```

⇒ `0x43036C` = **状态 2**，`0x4308F3` = **状态 8**。两条都以 `jmp 0x43024c`
（公共尾 / 状态复位检查）收尾，所以**没有自己的 `ret`**，本测试停在 `0x43024c`。

### [A] `0x00431712`（80 条指令）

```asm
00431716  xor eax,eax
00431718  jmp 0x431720
0043171A  inc eax                      ; ← 循环继续点
0043171B  cmp eax, 0x24 / jge 0x431729 ; ★ 上界恰 36
00431720  cmp byte [eax + 0x4990b8], 0 / je 0x43171A   ; ★ 扫 36 个号码槽
00431729  cmp eax, 0x24 / je 0x43180D                  ; ★ 一张没卖 ⇒ 直接返回（eax = 0x24）
00431732  push 0x47567b / call 0x454176                ; 装音效描述符
00431743  push 0;push 0;push 0x0f;push [0x48a05c];call 0x450441 ; → [0x48c360]
0043175D  push 0;push 0;push 0x0d;push [0x48a05c];call 0x450441 ; → [0x48c368]
00431777  push 0;push 0;push 0x10;push [0x48a05c];call 0x450441 ; → [0x48c358]
00431791  push 0;push 0;push 0x11;push [0x48a05c];call 0x450441 ; → [0x48c354]
004317A7  push 8 / call 0x4549cf
004317B3  push 0;push 0x43010c / call 0x4018e7         ; ★ 注册的就是開獎屏窗口过程
004317C0  call 0x454bcc
004317C5  mov edi,[0x48c360] / … 四次 call 0x456e11     ; 逐个释放 4 张 Panel
00431800  push 0x47567b / call 0x454240                 ; 释放音效
0043180D  pop ebp/edi/esi/ebx / ret
```

★ **`0x450441` 的第 2 个实参才是资源号**（实测：把桩的返回值绑到 `[esp+4]`/`[esp+8]`
分别得到「全句柄相同」/「15,13,16,17」）。复刻的
`CEREMONY_PANEL/DRUM/WINNER/DIGIT`（`places/lottery-ceremony.ts:36-42`）与此逐项一致。

### [B] `0x0043036C`（状态 2）

```asm
0043036C  mov byte [0x48c37b], 3            ; ★ 规则：状态无条件推到 3
00430373  xor al,al / mov byte [0x48c37c], al ; ★ 20 帧计数清零
0043037A  push 8 / push 0x4b / push 0xb7 / push [0x48c358] / call 0x450ced
                                            ; ★ 起摇球机动画 Panel#16 @(183,75) flags=8
004303B2  call 0x45643d  src=[0x48c360]+0x0c  矩形(16,340,16,340,608,130)  ← 清铭牌带
004303D8  call 0x45643d  src=[0x48c360]+0x0c  矩形(472,116,472,116,45,90)
00430402  call 0x456418  src=[0x48c360]+0x18  @(418,66)                   ← 摊手(子图 2)
00430420  call 0x456495  src=[0x48c360]+0x30  (7,340,0,274,134,130)       ← 举板(子图 3)
00430471  push 0 / push 0x47567b / call 0x4542ce      ; 播音效
00430480  jmp 0x43024c
```

### [C] `0x004308F3`（状态 8）

```asm
00430909  call 0x45643d  src=[0x48c360]+0x0c  矩形(16,340,16,340,608,130)  ← 清铭牌带
00430939  call 0x45643d  src=[0x48c360]+0x0c  矩形(489,116,489,116,151,364)← 擦掉右主持人
00430999  call 0x456418  src=[0x48c360]+0x18  @(472,66)                   ← 指人(子图 1)
004309B8  call 0x45643d  src=[0x48c360]+0x30  矩形(52,89,45,23,50,40)     ← 左脸还原(子图 3)
00430991  call 0x456495  src=[0x48c360]+0x30  (7,340,0,274,134,130)
004309DC  src = [0x48c360] + 0x0c + 12×[0x48c37d]，@(286,405)             ← ★ 十位号球
00430A13  src = [0x48c360] + 0x0c + 12×[0x48c37e]，@(358,405)             ← ★ 个位号球
00430A6C  call 0x44ec30(dest=[0x48c360]+0x114, 300, 47, -10, 0, 0x101010) ← 气泡(子图 22)
00430A91  mov byte [0x48c37b], 9            ; ★ 规则：状态 → 9
00430A98  mov ecx,[0x475628] / jmp 0x430243 ; ⇒ push + call 0x44ecb6（说 #0035）
```

`[0x48c37d]`/`[0x48c37e]` 由状态 3 的摇号尾段写：`sprintf(buf,"%02d",号)` 之后
`al = buf[0] − 0x0b` / `al = buf[1] − 0x0b` ⇒ = **37 + 十位** / **37 + 个位**，
落在 `[0x48c360]` 的子图表上正是 `ENTRY.ball + 数字`（`lottery-ceremony.ts:206-213`
的 `ballBlits`）。本文件把这两个字节**直接注入**（摇号本身见 `test_lottery_draw_roll.py`）。

## 打桩清单

| VA | 桩 | 为什么 |
|---|---|---|
| `0x450441` | 记 arg2（资源号）并**返回 arg2** | `mkf_read_resource`：真身要 `[0x4762f4]` 表 + User32 thunk；返回资源号即可钉住「哪个资源进哪个槽、按什么顺序」 |
| `0x454176` / `0x454240` | 记 arg1 | 音效描述符装载/释放；真身同样走 `0x450441` + DirectSound |
| `0x4549cf` | 记 arg1 | 动画/节拍设置（真身读 `[0x46cb06]`/`[0x49715a]`、操作 `0x47e7xx` 脚本状态） |
| `0x4018e7` | 记两个实参 | **模态运行器**：真身会跑完整条窗口消息循环（本测试只驱动「开不开屏」这一层） |
| `0x454bcc` | 空桩 | 模态后的收尾（真身读 `0x47e7d7` 帧脚本表） |
| `0x456e11` | 记 arg1 | 释放 Panel，真身走 `0x488f68` 堆管理 |
| `0x456f2d` (`rand`) | 返回 `[RAND_VAL]` 并计数 | ★ 证明**演出层一个随机数都不消耗**（C-DET-1） |
| `0x450ced` | 记 (句柄,x,y,flags) | 起多帧动画；真身要 DirectDraw 表面 |
| `0x45643d` | 记 (src, dx,dy,sx,sy,w,h) | 带源矩形的抠图 blit（cdecl，调用方 `add esp,0x20`） |
| `0x456418` | 记 (src, x, y) | 抠图 blit |
| `0x456495` | 记 (src, dx,dy,sx,sy,w,h) | 不透明 blit |
| `0x4542ce` | 记 (desc, 0) | 播音效 |
| `0x44ec30` | 记 (dest, x, y, …) | 开对话气泡 |
| `0x44ecb6` | 记 arg1 | 说一句台词 |
| `0x42f417` | 空桩 | 帧收尾（FPS / 翻页） |
| `0x4622f8`（导入 thunk） | 指到 `ret 0xC` 桩 | `InvalidateRect(hwnd,NULL,FALSE)`；★ 调用点后面**没有** `add esp` ⇒ **stdcall** |
| `[0x48a0e0]` vtable `+0x64` / `+0x80` | 指到 `ret 0x14` / `ret 8` 桩 | DirectDraw 表面方法；两处调用点后都没有清栈 ⇒ **callee-cleanup**（实测） |

所有记录桩都放在**独立桩区 `STUB_BASE`**（`emulate.py:56`），原函数入口只写一条
5 字节 `jmp rel32` —— 因为记录桩比原函数长（`0x45643d` 的桩 109 B，
会盖到 0x1d 之后的 `0x456495`），直接就地打桩会**互相覆盖**（第一版就栽在这）。

## 与复刻的逐条裁决（只读 TS，未改一行）

| # | 规则 | 原版 @source | 复刻 file:line | 裁决 |
|---|---|---|---|---|
| 1 | **开屏判据 = 「36 槽里有任何一票」** | `0x431720`/`0x43172c` | `places/lottery.ts:296-305`（`sold.length === 0 ⇒ number: null`）+ `places/lottery-ceremony.ts:246`（`number === null ⇒ []`） | **MATCH** |
| 2 | 4 张 Panel ↔ 资源号 | `0x431743/5d/77/91` | `lottery-ceremony.ts:36-42` | **MATCH** |
| 3 | 每步子图号 = 12 字节表项（`ENTRY.*`） | `[0x48c360]+0xNN` | `lottery-ceremony.ts:53-78` | **MATCH**（本文件 [B5] 逐项核） |
| 4 | 开奖日 = 每月 15 号；**先进企業分红再开奖** | `0x41d08a` / `0x41d08f` / `0x41d094` | `lottery.ts:233` + `company.ts:326` | **MATCH**（顺序见 [A5]） |
| 5 | 状态 2 处理器：状态 → 3；摇球动画 (183,75,flags=8) | `0x43036c` / `0x43037a` | `lottery-ceremony.ts:272-289` | **MATCH** |
| 6 | 状态 2 的 4 处铺图/擦除矩形 | `0x4303b2..0x430448` | `lottery-ceremony.ts:277/280/282/284` | **MATCH** |
| 7 | 状态 8 处理器：状态 → 9 + 说 `#0035`（`drawHopeNext`） | `0x430a91` / `0x430a98` | `lottery-ceremony.ts:385`（`state: 9` 那一步） | **MATCH** |
| 8 | 状态 8 的「擦右主持人 / 还原左脸 / 贴回指人姿势」 | `0x430939` / `0x4309b8` / `0x430999` | `lottery-ceremony.ts:373-377` | **MATCH** |
| 9 | 状态 8 **还**擦铭牌带、补 (7,340) 的腿、**重贴两颗球** | `0x430909` / `0x430991` / `0x4309dc`+`0x430a13` | `lottery-ceremony.ts:373-378`（**没有**这三项） | **无法判定（表现层）**：复刻每步是增量叠加，上一格留下的球与补丁本就在屏上 ⇒ 净观感应等价；core 自己也在 `lottery-ceremony.ts:24-25` 声明状态 6/8 的擦除矩形「未实机核对」 |
| 10 | 每次开语句都调 **气泡开屏 `0x44ec30`**（子图 22，实参 300/47/−10/0/0x101010/0） | `0x430a6c` | `lottery-ceremony.ts:84-87/216-230`（`BUBBLE_AT = [300, -10]`，只在建屏那一步贴一次） | **无法判定**：`0x44ec30` 的 a3(47) / a4(−10) 语义未解（只读了它的序言），复刻取的是 300/−10 |
| 11 | **音效/语音**：装 0x47567b → 状态 2 播 → 释放 | `0x431737`/`0x430473`/`0x431805` | 无对应字段（client 侧 `lottery-draw-screen.ts:85-86` 自认「语音没接」） | **DISCREPANCY（音频，非规则）**：开奖演出**没有声音** |

## 诚实边界（没驱动的部分，明说）

1. **`0x4018e7` 里面的模态消息循环没跑**。[A] 只驱动「开不开屏 + 装/放哪些资源」这一层；
   状态 1..10 的推进（气泡等时、50 ms 定时器、重绘）属窗口过程 `0x43010c`。
   本轮的另外三支 `0x430236`（→2）/`0x430AA3`（→10）/`0x430AB5`（派彩）已有差分；
   **`0x430485`（状态 4 = 得主屏）与 `0x4306FF`（状态 6）仍未驱动**。
2. **[B]/[C] 的像素结果没验**：所有绘制调用都打在桩上，只断言「从哪个子图、什么矩形、
   什么坐标」。真机截图比对未做。
3. **[C] 里 `[0x48c37d]`/`[0x48c37e]` 是注入的** —— `0x430b7a` 的 `sprintf("%02d")` 与
   `−0x0b` 属状态 3 的摇号尾段，不在本文件范围。
4. **[A] 的返回值只在「没卖票」那一支有意义**（`eax = 0x24`）；卖过票那一支 `eax`
   被各桩返回值覆盖，**不断言**。
5. 音效 / 背景音乐（`0x47567b` 描述符、`0x4542ce`）只断言**调用与实参**，不复刻波形。
6. **[B]/[C] 里"画面帧界"那三个 vtable/thunk 调用只断言"发生过"**（它们在调用序列里，
   但不记实参）—— 它们只操作 DirectDraw，没有规则含义。

跑法：cd rich4-spec && .venv/bin/python tests/test_lottery_ceremony.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

# ── 被驱动的 VA ──────────────────────────────────────────────────────────
CEREMONY_OPEN = 0x431712        # [A] 256 B
SCAN_ENTRY = 0x431716           # [A] 只驱动那个 36 槽扫描循环
SCAN_STOP = 0x431729
STATE2 = 0x43036C               # [B] 状态 2 处理器
STATE8 = 0x4308F3               # [C] 状态 8 处理器
TAIL = 0x43024C                 # 两条处理器的 jmp 目标（公共尾）

# ── 全局量（全部实测自反汇编）────────────────────────────────────────────
SLOTS = 0x4990B8                # 36 个号码槽（值 = 持有者下标 + 1，0 = 未售）
SLOT_N = 0x24
UI_STATE = 0x48C37B             # 状态字节
UI_COUNT = 0x48C37C             # 帧计数（状态 3 用 0x14、状态 5 用 0x1e）
DIG_TENS = 0x48C37D             # 十位球子图号 = 37 + 十位
DIG_ONES = 0x48C37E             # 个位球子图号 = 37 + 个位
PANEL_MAIN = 0x48C360           # ← 资源 0x0f（Panel#15）
PANEL_DIGIT = 0x48C368          # ← 资源 0x0d（Panel#13）
PANEL_DRUM = 0x48C358           # ← 资源 0x10（Panel#16）
PANEL_WINNER = 0x48C354         # ← 资源 0x11（Panel#17）
GFX_CTX = 0x48A05C              # `0x450441` 的第 1 实参（上下文）
DDRAW = 0x48A0E0                # DirectDraw 对象（`[[..]]->vtable`）
SURFACE = 0x48A08C              # 目标表面（只作实参传）
SOUND_DESC = 0x47567B           # 音效描述符（奇地址 ⇒ 字节指针）
LINE_HOPE = 0x475628            # [0x475628] = "#0035期待下個月…"（drawHopeNext）
WNDPROC = 0x43010C              # 開獎屏窗口过程
TABLE = 0x4300D0                # 状态跳表（10 项）

# 复刻侧常量（**只作文本对照，不 import TS**）
# @source rich4-remake/packages/core/src/places/lottery-ceremony.ts:53-78
ENTRY = {
    "stage": 0, "pointing": 1, "presenting": 2, "board": 3, "oops": 4,
    "laugh": 5, "jumpBoard": 6, "bubble": 22, "burstSorry": 23,
    "burstWin": 24, "faceWry": 21, "ball": 37,
}

# ── 暂存区（桩的记录区）──────────────────────────────────────────────────
# ★ 每条「字段」一条数组、间隔 0x40（≥ 4×最大调用次数）—— 第一版把同一矩形的
#   六个字段只隔 4 字节，第二次调用就把第一次的值覆盖了（症状：读出来是
#   [call1.dx, call2.dx, call2.dy, …]）。
S = SCRATCH_BASE
GC = S + 0x000                  # 全局调用序号
LOG = S + 0x040                 # 全局调用序列（64 项）
CT = S + 0x140                  # 每个桩自己的计数器（id → CT + id*4）
RAND_VAL = S + 0x1F0
RAND_N = S + 0x1F4
# [A]
AR441 = S + 0x200
AR49CF = S + 0x240
AR401A = S + 0x280
AR401B = S + 0x2C0
ARFREE = S + 0x300
AR176 = S + 0x340
AR240 = S + 0x380
# [B]/[C]
AR_CED_H, AR_CED_X, AR_CED_Y, AR_CED_F = S + 0x400, S + 0x440, S + 0x480, S + 0x4C0
AR_43D_SRC, AR_43D_DX, AR_43D_DY = S + 0x500, S + 0x540, S + 0x580
AR_43D_SX, AR_43D_SY, AR_43D_W, AR_43D_H = S + 0x5C0, S + 0x600, S + 0x640, S + 0x680
AR_418_SRC, AR_418_X, AR_418_Y = S + 0x6C0, S + 0x700, S + 0x740
AR_495_SRC, AR_495_DX, AR_495_DY = S + 0x780, S + 0x7C0, S + 0x800
AR_495_SX, AR_495_SY, AR_495_W, AR_495_H = S + 0x840, S + 0x880, S + 0x8C0, S + 0x900
AR_2CE_A, AR_2CE_B = S + 0x940, S + 0x980
AR_EC30_D, AR_EC30_X, AR_EC30_Y = S + 0x9C0, S + 0xA00, S + 0xA40
AR_EC30_A4, AR_EC30_A5, AR_EC30_A6 = S + 0xA80, S + 0xAC0, S + 0xB00
AR_ECB6 = S + 0xB40
SCRATCH_CLEAR = 0xC00
OBJ = S + 0x2000                 # 假 DirectDraw 对象
VT = S + 0x2100                  # 它的 vtable

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append({"ok": ok, "desc": desc})
    print(f"  {'OK ' if ok else 'NG '} {desc:<60} 实际 {got!s:<24} 期望 {want!s}")
    return ok


def p32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def _seq(id_):
    """把「本桩第几次被调」放 eax/edx，并把 id 追加进全局调用序列 LOG。"""
    c = b"\xA1" + p32(GC)                         # mov eax,[GC]
    c += b"\xFF\x05" + p32(GC)                    # inc dword [GC]
    c += b"\xC7\x04\x85" + p32(LOG) + p32(id_)    # mov [eax*4+LOG], id
    c += b"\xA1" + p32(CT + id_ * 4)              # mov eax,[CT+id*4]
    c += b"\xFF\x05" + p32(CT + id_ * 4)          # inc dword [CT+id*4]
    c += b"\x89\xC2"                              # mov edx,eax
    return c


def stub(id_, recs=(), ret=None, ret_off=None, tail=b"\xC3"):
    """记录桩。

    recs:    [(esp 偏移, 目标数组)]；数组按「本桩第几次调用」下标写入。
    ret:     固定返回值。
    ret_off: 把该 esp 偏移处的**实参**当返回值（`0x450441` 用）。
    tail:    收尾（默认 `ret`；stdcall 桩用 `ret N`）。
    """
    c = _seq(id_)
    for off, arr in recs:
        c += b"\x8B\x44\x24" + bytes([off])       # mov eax,[esp+off]
        c += b"\x89\x04\x95" + p32(arr)           # mov [edx*4+arr],eax
    if ret is not None:
        c += b"\xB8" + p32(ret)
    elif ret_off is not None:
        c += b"\x8B\x44\x24" + bytes([ret_off])
    return c + tail


class Arena:
    """把记录桩放进独立桩区，原函数入口只写一条 `jmp rel32`。

    ★ 为什么必须这样：记录桩比原函数长（`0x45643d` 的桩 109 B），
      而 `0x456495` 就在它后面 0x58 字节 —— 就地打桩会互相覆盖。
    """

    def __init__(self, emu, base=STUB_BASE):
        self.e = emu
        self.next = base + 0x10

    def place(self, code):
        addr = self.next
        self.e.patch(addr, code)
        self.next = (addr + len(code) + 15) & ~15
        assert self.next < STUB_BASE + 0x1000, "桩区放不下"
        return addr

    def func(self, va, code):
        addr = self.place(code)
        rel = addr - (va + 5)
        self.e.patch(va, b"\xE9" + struct.pack("<i", rel))
        return addr


def _clear_scratch(e):
    e.write(S, bytes(SCRATCH_CLEAR))               # 清 GC/LOG/CT/各记录数组
    e.write32(RAND_VAL, 0)
    e.write32(RAND_N, 0)


def _log(e):
    n = e.readu32(GC)
    return [e.readu32(LOG + 4 * i) for i in range(n)]


def _arr(e, base, n):
    return [e.readu32(base + 4 * i) for i in range(n)]


def _cnt(e, id_):
    return e.readu32(CT + id_ * 4)


def _f(e, base, i):
    """读「字段数组 base 的第 i 次调用」。"""
    return e.readu32(base + 4 * i)


def _rect(e, srcs, dxy, i):
    """按调用序号 i 读一条 8 实参 blit 的 (src 偏移由调用方算, dx,dy,sx,sy,w,h)。"""
    return [_f(e, dxy[0], i), _f(e, dxy[1], i), _f(e, dxy[2], i),
            _f(e, dxy[3], i), _f(e, dxy[4], i), _f(e, dxy[5], i)]


def _rand_stub():
    return b"\xA1" + p32(RAND_VAL) + b"\xFF\x05" + p32(RAND_N) + b"\xC3"


def _call_target(e, site):
    """解一条 `E8 rel32` 的目标（调用点字节级复核用）。"""
    b = e.read(site, 5)
    assert b[0] == 0xE8, f"{site:#x} 不是 E8 调用"
    return site + 5 + struct.unpack("<i", b[1:])[0]


_REL32 = None


def _call_sites(callee_key):
    """从字节级全量调用表 `gen/rel32-calls.json` 取「谁调用它」。"""
    global _REL32
    if _REL32 is None:
        import json
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "..", "gen", "rel32-calls.json"), encoding="utf-8") as fh:
            _REL32 = json.load(fh)
    return _REL32.get(callee_key, [])


# ============================================================
#  [A] 0x00431712 —— 开屏判据 + 建屏包装
# ============================================================
class OpenRun:
    """`0x431712` 整支驱动（7 个外部调用全打桩）。"""

    SENT = (0x11111111, 0x22222222, 0x33333333, 0x44444444)

    def __init__(self):
        e = Emu()
        e.patch(0x456F2D, _rand_stub())
        a = Arena(e)
        a.func(0x450441, stub(1, [(8, AR441)], ret_off=8))
        a.func(0x4549CF, stub(2, [(4, AR49CF)]))
        a.func(0x4018E7, stub(3, [(4, AR401A), (8, AR401B)]))
        a.func(0x454BCC, stub(4))
        a.func(0x456E11, stub(5, [(4, ARFREE)]))
        a.func(0x454176, stub(6, [(4, AR176)]))
        a.func(0x454240, stub(7, [(4, AR240)]))
        self.emu = e

    def run(self, slots, guard=0):
        sent = self.SENT
        e = self.emu

        def setup(em):
            _clear_scratch(em)
            for i in range(SLOT_N + 1):
                em.write8(SLOTS + i, 0)
            for i, v in enumerate(slots):
                em.write8(SLOTS + i, v)
            em.write8(SLOTS + SLOT_N, guard)       # 紧邻表尾的哨兵
            em.write32(PANEL_MAIN, sent[0])
            em.write32(PANEL_DIGIT, sent[1])
            em.write32(PANEL_DRUM, sent[2])
            em.write32(PANEL_WINNER, sent[3])
            em.write32(GFX_CTX, 0x0AAAA000)
        return e.call(CEREMONY_OPEN, [], setup=setup)

    def handles(self):
        return (self.emu.readu32(PANEL_MAIN), self.emu.readu32(PANEL_DIGIT),
                self.emu.readu32(PANEL_DRUM), self.emu.readu32(PANEL_WINNER))

    def slots(self):
        return list(self.emu.read(SLOTS, SLOT_N))

    def log(self):
        return _log(self.emu)

    def rands(self):
        return self.emu.readu32(RAND_N)

    def reqs(self):
        return _arr(self.emu, AR441, _cnt(self.emu, 1))


def run_scan(slots, guard=0):
    """只驱动 36 槽扫描循环 `0x431716`–`0x431729`，返回 eax（首个非 0 槽号 / 0x24）。"""
    e = Emu()

    def setup(em):
        for i in range(SLOT_N + 1):
            em.write8(SLOTS + i, 0)
        for i, v in enumerate(slots):
            em.write8(SLOTS + i, v)
        em.write8(SLOTS + SLOT_N, guard)
    out = e.eval_block(SCAN_ENTRY, SCAN_STOP, regs={"eax": 0}, setup=setup)
    return out["regs"]["eax"]


def part_a():
    print("[A] `0x431712`（256 B）—— 开屏判据 + 建屏包装\n")

    print("  ── 跳表定位 ──")
    e0 = Emu()
    tbl = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(10)]
    case("状态跳表 [1] = 0x43036C（= 状态 2，本文件 [B]）", tbl[1], STATE2)
    case("状态跳表 [7] = 0x4308F3（= 状态 8，本文件 [C]）", tbl[7], STATE8)
    case("状态跳表 [9] = 0x430AB5（状态 10 派彩，已另有差分）", tbl[9], 0x430AB5)

    print("\n  ── [A1] 36 槽扫描循环（eax = 首个非 0 槽号；全 0 则 0x24）──")
    case("36 格全 0 ⇒ eax = 0x24", run_scan([0] * SLOT_N), 0x24)
    case("只有槽 0 有票 ⇒ eax = 0", run_scan([1] + [0] * 35), 0)
    case("只有槽 35 有票 ⇒ eax = 35（**上界恰 36**）", run_scan([0] * 35 + [3]), 35)
    case("槽 5 与槽 20 都有票 ⇒ eax = 5（取**首个**非 0）",
         run_scan([0] * 5 + [1] + [0] * 14 + [2] + [0] * 15), 5)
    case("槽 1 与槽 35 都有票 ⇒ eax = 1", run_scan([0, 1] + [0] * 33 + [4]), 1)
    case("★ 紧邻表尾的字节有值也**不算票**（上界是 36 不是 37）",
         run_scan([0] * SLOT_N, guard=1), 0x24)
    case("槽值 0xFF 也算「有票」（判据是 `!= 0`）", run_scan([0xFF] + [0] * 35), 0)

    print("\n  ── [A2] 一张票都没卖：整支直接返回 ──")
    f = OpenRun()
    out = f.run([0] * SLOT_N)
    case("★ 返回值 eax = 0x24（= 36）", out["eax"], 0x24)
    case("★ 4 个 Panel 句柄**一个都没写**（保持注入的哨兵）", f.handles(), OpenRun.SENT)
    case("★ 一次外部调用都没有（调用序列为空）", f.log(), [])
    case("★ `rand` 一次都不消耗", f.rands(), 0)
    case("36 个号码槽原样不动", f.slots(), [0] * SLOT_N)

    print("\n  ── [A3] 卖了票：装 4 张 Panel + 注册窗口过程 + 逐个释放 ──")
    f = OpenRun()
    f.run([0, 0, 7] + [0] * 33)
    case("★ 资源 0x0f → [0x48c360]（Panel#15 主屏）", f.emu.readu32(PANEL_MAIN), 0x0F)
    case("★ 资源 0x0d → [0x48c368]（Panel#13 小数字牌）", f.emu.readu32(PANEL_DIGIT), 0x0D)
    case("★ 资源 0x10 → [0x48c358]（Panel#16 摇球机）", f.emu.readu32(PANEL_DRUM), 0x10)
    case("★ 资源 0x11 → [0x48c354]（Panel#17 得主面板）", f.emu.readu32(PANEL_WINNER), 0x11)
    case("★ 四次资源请求的顺序 = 0x0f,0x0d,0x10,0x11", f.reqs(), [0x0F, 0x0D, 0x10, 0x11])
    case("`0x4549cf` 的实参 = 8", _arr(f.emu, AR49CF, 1), [8])
    case("`0x4018e7` 注册的是開獎屏窗口过程 `0x43010c`", f.emu.readu32(AR401A), WNDPROC)
    case("`0x4018e7` 的第二实参 = 0", f.emu.readu32(AR401B), 0)
    case("释放（`0x456e11`）四次，实参 = 刚才那 4 个句柄",
         _arr(f.emu, ARFREE, 4), [0x0F, 0x0D, 0x10, 0x11])
    case("装载音效描述符 `0x454176(0x47567b)`", f.emu.readu32(AR176), SOUND_DESC)
    case("释放音效描述符 `0x454240(0x47567b)`", f.emu.readu32(AR240), SOUND_DESC)
    case("★ 完整调用序列（6 音效装 → 4×1 资源 → 2 节拍 → 3 模态 → 4 收尾 → 4×5 释放 → 7 音效放）",
         f.log(), [6, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 5, 7])
    case("★ 演出层一个 `rand` 都不消耗", f.rands(), 0)
    case("号码槽不被开屏改写", f.slots(), [0, 0, 7] + [0] * 33)

    print("\n  ── [A4] 判据只问「有没有票」，不问「哪一格 / 有几张」──")
    for k in (0, 17, 35):
        sl = [0] * SLOT_N
        sl[k] = 1
        f = OpenRun()
        f.run(sl)
        case(f"只有槽 {k} 有票 ⇒ 照样装那 4 张 Panel", f.reqs(), [0x0F, 0x0D, 0x10, 0x11])
    f = OpenRun()
    f.run([4] * SLOT_N)
    case("★ 36 格全满 ⇒ 也只装一次 4 张（不是每票一次）", _cnt(f.emu, 1), 4)
    case("★ 36 格全满 ⇒ 释放也恰好 4 次", _cnt(f.emu, 5), 4)

    print("\n  ── [A5] 调用点 `0x41d080`：日 == 0x0f ⇒ 先分红 `0x42ba97` 再开奖 `0x431712` ──")
    case("`0x41d080` = `mov eax,[0x497160]`（打包日期）", e0.read(0x41D080, 5).hex(), "a160714900")
    case("`0x41d085` = `and eax,0xff`（低字节 = 日）", e0.read(0x41D085, 2).hex(), "25ff")
    case("`0x41d08a` = `cmp eax,0x0f` ⇒ 开奖日是每月 15 号（复刻 `LOTTERY_DRAW_DAY` / `DIVIDEND_DAY`）",
         e0.read(0x41D08A, 3).hex(), "83f80f")
    case("★ 第一个调用 = 企業分紅 `0x42ba97`（复刻 `company.ts` 的 `DIVIDEND_DAY`）",
         _call_target(e0, 0x41D08F), 0x42BA97)
    case("★ 第二个调用 = 本函数 `0x431712`（顺序：分红在前、开奖在后）",
         _call_target(e0, 0x41D094), CEREMONY_OPEN)
    case("★ `gen/rel32-calls.json` 里 `0x431712` 的唯一调用点就是 `0x41d094`",
         _call_sites("0x00431712"), ["0x0041d094"])


# ============================================================
#  [B]/[C] 两个状态处理器的公共驱动
# ============================================================
class HandlerRun:
    """状态 2 / 状态 8 处理器：手搭 `esi`（窗口句柄）+ 全部 UI 调用打桩。"""

    def __init__(self, entry, stop=TAIL):
        self.entry = entry
        self.stop = stop
        e = Emu()
        e.patch(0x456F2D, _rand_stub())
        a = Arena(e)
        a.func(0x450CED, stub(10, [(4, AR_CED_H), (8, AR_CED_X),
                                   (12, AR_CED_Y), (16, AR_CED_F)]))
        a.func(0x45643D, stub(11, [(8, AR_43D_SRC), (12, AR_43D_DX),
                                   (16, AR_43D_DY), (20, AR_43D_SX),
                                   (24, AR_43D_SY), (28, AR_43D_W),
                                   (32, AR_43D_H)]))
        a.func(0x456418, stub(12, [(8, AR_418_SRC), (12, AR_418_X),
                                   (16, AR_418_Y)]))
        a.func(0x456495, stub(13, [(8, AR_495_SRC), (12, AR_495_DX),
                                   (16, AR_495_DY), (20, AR_495_SX),
                                   (24, AR_495_SY), (28, AR_495_W),
                                   (32, AR_495_H)]))
        a.func(0x4542CE, stub(14, [(4, AR_2CE_A), (8, AR_2CE_B)]))
        a.func(0x44EC30, stub(15, [(4, AR_EC30_D), (8, AR_EC30_X),
                                   (12, AR_EC30_Y), (16, AR_EC30_A4),
                                   (20, AR_EC30_A5), (24, AR_EC30_A6)]))
        a.func(0x44ECB6, stub(16, [(4, AR_ECB6)]))
        a.func(0x42F417, stub(17))
        # ★ 假 DirectDraw 对象：`[[0x48a0e0]]->+0x64` 是 5 实参、`+0x80` 是 2 实参，
        #   两处调用点后面都**没有** `add esp` ⇒ callee-cleanup（实测）
        self.v64 = a.place(stub(20, tail=b"\xC2\x14\x00"))
        self.v80 = a.place(stub(21, tail=b"\xC2\x08\x00"))
        self.thunk = a.place(stub(22, tail=b"\xC2\x0C\x00"))
        e.patch(0x4622F8, p32(self.thunk))
        self.emu = e

    def run(self, state=2, count=0, tens=0x25, ones=0x2A,
            main=0x10000000, drum=0x0D000000, winner=0x0E000000):
        e = self.emu
        v64, v80 = self.v64, self.v80

        def setup(em):
            _clear_scratch(em)
            em.write8(UI_STATE, state)
            em.write8(UI_COUNT, count)
            em.write8(DIG_TENS, tens)
            em.write8(DIG_ONES, ones)
            em.write32(PANEL_MAIN, main)
            em.write32(PANEL_DRUM, drum)
            em.write32(PANEL_WINNER, winner)
            em.write32(PANEL_DIGIT, 0x0F000000)
            em.write32(SURFACE, 0x0ABCD000)
            em.write32(DDRAW, OBJ)
            em.write32(OBJ, VT)
            em.write32(VT + 0x64, v64)
            em.write32(VT + 0x80, v80)
        return e.eval_block(self.entry, self.stop, regs={"esi": 0x00010001}, setup=setup)

    def state(self):
        return self.emu.read8(UI_STATE)

    def count(self):
        return self.emu.read8(UI_COUNT)

    def tens(self):
        return self.emu.read8(DIG_TENS)

    def ones(self):
        return self.emu.read8(DIG_ONES)

    def log(self):
        return _log(self.emu)

    def rands(self):
        return self.emu.readu32(RAND_N)

    def main_panel(self):
        return self.emu.readu32(PANEL_MAIN)

    def offsets_43d(self):
        mp = self.main_panel()
        return [s - mp for s in _arr(self.emu, AR_43D_SRC, _cnt(self.emu, 11))]

    def offsets_418(self):
        mp = self.main_panel()
        return [s - mp for s in _arr(self.emu, AR_418_SRC, _cnt(self.emu, 12))]

    def rect_43d(self, i):
        return _rect(self.emu, AR_43D_SRC,
                     (AR_43D_DX, AR_43D_DY, AR_43D_SX, AR_43D_SY, AR_43D_W, AR_43D_H), i)

    def rect_495(self, i=0):
        return _rect(self.emu, AR_495_SRC,
                     (AR_495_DX, AR_495_DY, AR_495_SX, AR_495_SY, AR_495_W, AR_495_H), i)


def part_b():
    print("\n[B] `0x43036C`（状态 2 处理器；`functions.json` 268 B／可达 281 B）\n")

    print("  ── [B1] 两条规则写：状态 → 3、帧计数清零（无条件覆盖入口值）──")
    for st in (0, 1, 2, 5, 0xFF):
        f = HandlerRun(STATE2)
        f.run(state=st, count=0x14)
        case(f"入口状态 {st} ⇒ `[0x48c37b]` = 3", f.state(), 3)
    f = HandlerRun(STATE2)
    f.run(state=2, count=0x14)
    case("★ 帧计数 `[0x48c37c]` 被清成 0（入口 0x14）", f.count(), 0)

    print("\n  ── [B2] 起摇球机动画：`0x450ced(句柄, 183, 75, 8)` ──")
    f = HandlerRun(STATE2)
    f.run(drum=0x0D000000)
    case("`0x450ced` 被调**一次**", _cnt(f.emu, 10), 1)
    case("★ 句柄 = `[0x48c358]`（= [A] 里资源 0x10 落地的那个槽）",
         _f(f.emu, AR_CED_H, 0), 0x0D000000)
    case("x = 183（0xb7）", _f(f.emu, AR_CED_X, 0), 183)
    case("y = 75（0x4b）", _f(f.emu, AR_CED_Y, 0), 75)
    case("flags = 8", _f(f.emu, AR_CED_F, 0), 8)

    print("\n  ── [B3] 铺图：子图号 × 12 字节步长 + 矩形 ──")
    f = HandlerRun(STATE2)
    f.run()
    case("`0x45643d` 被调 2 次", _cnt(f.emu, 11), 2)
    case("★ 两次的源子图都是主屏 +0x0c（= 子图 0 = 舞台底图）", f.offsets_43d(), [0x0C, 0x0C])
    case("★ 抠图①矩形 (dest 16,340 ← src 16,340，尺寸 608×130)（清铭牌带）",
         f.rect_43d(0), [16, 340, 16, 340, 608, 130])
    case("★ 抠图②矩形 (dest 472,116 ← src 472,116，尺寸 45×90)（清累积奖金格）",
         f.rect_43d(1), [472, 116, 472, 116, 45, 90])

    case("`0x456418` 被调**一次**", _cnt(f.emu, 12), 1)
    case("★ 该 blit 源 = 主屏 +0x24（= **子图 2**：摊手）", f.offsets_418(), [0x24])
    case("该 blit 落点 = (418, 66)", [_f(f.emu, AR_418_X, 0), _f(f.emu, AR_418_Y, 0)], [418, 66])
    case("★ 0x24 = 0x0c + 12×2 ⇒ 复刻 `ENTRY.presenting` = 2",
         (f.offsets_418()[0] - 0x0C) // 12, ENTRY["presenting"])

    case("`0x456495` 被调**一次**", _cnt(f.emu, 13), 1)
    case("★ 该 blit 源 = 主屏 +0x30（= **子图 3**：举板）",
         f.emu.readu32(AR_495_SRC) - f.main_panel(), 0x30)
    case("★ 该 blit 矩形 (dest 7,340 ← src 0,274，尺寸 134×130)（补腿部）",
         f.rect_495(), [7, 340, 0, 274, 134, 130])
    case("★ 0x30 = 0x0c + 12×3 ⇒ 复刻 `ENTRY.board` = 3",
         (f.emu.readu32(AR_495_SRC) - f.main_panel() - 0x0C) // 12, ENTRY["board"])

    print("\n  ── [B4] 收尾音效与随机流 ──")
    case("`0x4542ce` 的实参 = (0x47567b, 0)",
         [_f(f.emu, AR_2CE_A, 0), _f(f.emu, AR_2CE_B, 0)], [SOUND_DESC, 0])
    case("★ 状态 2 处理器**一个 rand 都不消耗**（演出层不许动游戏随机流）", f.rands(), 0)
    case("★ 完整调用序列（10 动画 → 20 帧开始 → 11,11 抠图 → 12 → 13 → 21 帧结束 → 17 → 22 InvalidateRect → 14 音效）",
         f.log(), [10, 20, 11, 11, 12, 13, 21, 17, 22, 14])
    case("★ 处理器只写 `[0x48c37b]`/`[0x48c37c]` 两个全局字节 + 上面那些调用（没有第三条规则写）",
         (f.state(), f.count()), (3, 0))

    print("\n  ── [B5] 子图号公式（复刻把这张表写成了常量）──")
    for name, off in (("stage", 0x0C), ("pointing", 0x18), ("presenting", 0x24),
                      ("board", 0x30), ("laugh", 0x48), ("jumpBoard", 0x54),
                      ("bubble", 0x114), ("burstSorry", 0x120), ("burstWin", 0x12C)):
        case(f"复刻 `ENTRY.{name}` = {ENTRY[name]} ⇒ 偏移 0x{off:03x} == 0x0c + 12×{ENTRY[name]}",
             off, 0x0C + 12 * ENTRY[name])


def part_c():
    print("\n[C] `0x4308F3`（状态 8 处理器，432 B）\n")

    print("  ── [C1] 规则写：状态 → 9（无条件覆盖入口值）──")
    for st in (0, 6, 7, 8, 0xFF):
        f = HandlerRun(STATE8)
        f.run(state=st, tens=0x25, ones=0x2A)
        case(f"入口状态 {st} ⇒ `[0x48c37b]` = 9", f.state(), 9)

    print("\n  ── [C2] ★ 两颗中奖号球：子图号 = 0x0c + 12 × `[0x48c37d]`/`[0x48c37e]` ──")
    f = HandlerRun(STATE8)
    f.run(tens=0x25, ones=0x2A)                # 0x25 = 37（球 0）／0x2A = 42（球 5）
    case("`0x456418` 被调 3 次（指人姿势 + 十位球 + 个位球）", _cnt(f.emu, 12), 3)
    case("`0x45643d` 被调 3 次、`0x456418` 3 次、`0x456495` 1 次",
         (_cnt(f.emu, 11), _cnt(f.emu, 12), _cnt(f.emu, 13)), (3, 3, 1))
    offs = f.offsets_418()
    case("★ blit①源 = 主屏 +0x18（子图 1 = 指人姿势）", offs[0], 0x18)
    case("★ blit②源 = 主屏 + 0x0c + 12×0x25（十位球子图 37 ⇒ 球 0）", offs[1], 0x0C + 12 * 0x25)
    case("★ blit③源 = 主屏 + 0x0c + 12×0x2A（个位球子图 42 ⇒ 球 5）", offs[2], 0x0C + 12 * 0x2A)
    case("blit①落点 (472, 66)（右主持人位置）",
         [_f(f.emu, AR_418_X, 0), _f(f.emu, AR_418_Y, 0)], [472, 66])
    case("★ 十位球落点 (286, 405)",
         [_f(f.emu, AR_418_X, 1), _f(f.emu, AR_418_Y, 1)], [286, 405])
    case("★ 个位球落点 (358, 405)",
         [_f(f.emu, AR_418_X, 2), _f(f.emu, AR_418_Y, 2)], [358, 405])
    case("★★ 十位球子图号就是复刻的 `ENTRY.ball + 数字`（37 ⇒ 球 0）",
         (offs[1] - 0x0C) // 12, ENTRY["ball"] + 0)
    case("★ 个位球同理（42 ⇒ 球 5）", (offs[2] - 0x0C) // 12, ENTRY["ball"] + 5)

    print("\n  ── [C3] ★ 步长真的是 12 字节、下标真的是**无符号字节** ──")
    f = HandlerRun(STATE8)
    f.run(tens=0x25, ones=0x26)               # 球 0 / 球 1 ⇒ 差恰 12
    s = _arr(f.emu, AR_418_SRC, 3)
    case("下标 0x25 与 0x26 ⇒ 两个源指针恰好差 12 字节", s[2] - s[1], 12)
    f = HandlerRun(STATE8)
    f.run(tens=0x00, ones=0x01)
    case("★ 下标 0 ⇒ 源 = 主屏 + 0x0c（不是 +0x10 之类）", f.offsets_418()[1], 0x0C)
    f = HandlerRun(STATE8)
    f.run(tens=0xFF, ones=0x00)
    case("★★ 下标 0xFF 按**无符号**算 ⇒ 源 = 主屏 + 0x0c + 12×255 = +0xc08"
         "（若按有符号 −1 会得到 +0）", f.offsets_418()[1], 0x0C + 12 * 0xFF)

    print("\n  ── [C4] 收尾画面的擦除/复位（表现层，但矩形是确定的）──")
    f = HandlerRun(STATE8)
    f.run()
    case("★ `0x45643d` 三次的源子图 = [主屏+0x0c, 主屏+0x0c, 主屏+0x30]（舞台/舞台/举板）",
         f.offsets_43d(), [0x0C, 0x0C, 0x30])
    case("★ 抠图①清铭牌带 (16,340 ← 16,340，608×130)", f.rect_43d(0), [16, 340, 16, 340, 608, 130])
    case("★ 抠图②擦掉右主持人 (489,116 ← 489,116，151×364)", f.rect_43d(1), [489, 116, 489, 116, 151, 364])
    case("★ 抠图③还原左脸 (52,89 ← 45,23，50×40)", f.rect_43d(2), [52, 89, 45, 23, 50, 40])
    case("★ `0x456495` 源 = 主屏 +0x30（举板图），矩形 (7,340 ← 0,274，134×130)",
         (f.emu.readu32(AR_495_SRC) - f.main_panel(), f.rect_495()),
         (0x30, [7, 340, 0, 274, 134, 130]))

    print("\n  ── [C5] 气泡 + 收场白 + 随机流 ──")
    mp = f.main_panel()
    case("★ 气泡 `0x44ec30` 的目标 = 主屏 + 0x114（= 0x0c + 12×22 ⇒ `ENTRY.bubble` = 22）",
         ((_f(f.emu, AR_EC30_D, 0) - mp), (_f(f.emu, AR_EC30_D, 0) - mp - 0x0C) // 12),
         (0x114, ENTRY["bubble"]))
    case("★ 气泡的 7 个实参 = (dest, 300, 47, −10, 0, 0x101010, 0)——原样记下，语义属表现层",
         [_f(f.emu, AR_EC30_X, 0), _f(f.emu, AR_EC30_Y, 0), _f(f.emu, AR_EC30_A4, 0),
          _f(f.emu, AR_EC30_A5, 0), _f(f.emu, AR_EC30_A6, 0)],
         [300, 47, -10 & 0xFFFFFFFF, 0, 0x101010])
    case("★ 台词实参 = `[0x475628]` **解引用后**的值（不是指针本身）",
         f.emu.readu32(AR_ECB6), f.emu.readu32(LINE_HOPE))
    case("★ 那句话是 `#0035` 开头的收场白（复刻 `LOTTERY.drawHopeNext`）",
         f.emu.read(f.emu.readu32(LINE_HOPE), 5), b"#0035")
    case("台词只说了**一次**", _cnt(f.emu, 16), 1)
    case("★ 状态 8 处理器**一个 rand 都不消耗**", f.rands(), 0)
    case("★ `[0x48c37d]`/`[0x48c37e]` 被**只读不改**（注入 0x25/0x2A）",
         (f.tens(), f.ones()), (0x25, 0x2A))
    case("★ 完整调用序列（20 帧开始 → 11,11 抠图 → 13 补腿 → 12 指人 → 11 左脸 → "
         "12,12 两颗球 → 21 帧结束 → 22 InvalidateRect → 17 → 15 气泡 → 16 台词）",
         f.log(), [20, 11, 11, 13, 12, 11, 12, 12, 21, 22, 17, 15, 16])


def main():
    print("通道 2 差分测试 · 樂透開獎演出三支 "
          "(0x431712 / 0x43036C / 0x4308F3)\n")
    part_a()
    part_b()
    part_c()
    n_ok = sum(1 for r in RESULTS if r["ok"])
    n = len(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{n} 通过")
    if n_ok != n:
        print("失败项：")
        for r in RESULTS:
            if not r["ok"]:
                print("  NG", r["desc"])
    return 0 if n_ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
