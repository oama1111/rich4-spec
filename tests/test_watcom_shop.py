#!/usr/bin/env python3
"""
通道 2 差分测试 · **掷骰 `fcn_00419572`（0x00419572，383 B）**
              ＋ **随机道具 `rich4_receive_random_tool`（0x00445ada，101 B）**

两支都"复刻引用过、却从没有差分测试驱动过"。本测试用 Unicorn 执行
`Rich4/rich4.exe` 里的**那一份机器码**当预言机。

真理只有 `Rich4/rich4.exe`；本文件里凡是与规格文档不一致的地方，以 exe 为准。

--------------------------------------------------------------------------------
[A] 0x00419572 —— 掷骰（全程序唯一的掷骰路径，玩家与 AI 共用）
--------------------------------------------------------------------------------

```asm
; @source 0x00419572（逐条读出，节 AUTO）
00419572  push ebx / push esi / push edi / push ebp / sub esp,0x1c
00419579  imul esi, dword [0x49910c], 0x68      ; esi = 当前玩家 * 0x68
00419580  movzx esi, byte [esi + 0x496b7a]      ; esi = ndices（玩家 +0x12）
00419587  mov ecx, dword [esp + 0x30]           ; ecx = 传入的强制点数
0041958b  test ecx, ecx / jne 0x4195ae          ; ── 强制支 ──
0041958f  xor ebx, ebx                          ; ── 随机支：for (i = 0; i < ndices; i++)
00419591  cmp ebx, esi / jge 0x4195b7
00419595  call 0x456f2d                         ;   rand()
0041959a  mov edx,eax / mov ecx,6 / sar edx,0x1f / idiv ecx
004195a6  inc edx                               ;   rand()%6 + 1
004195a7  mov [esp + ebx*4 + 0x10], edx         ;   dice[i] = 点数（★ 栈局部，0x10 基）
004195ae  mov esi, 1                            ; ── 强制支：★ 骰子数被压成 1
004195b3  mov [esp + 0x10], ecx                 ;   dice[0] = 强制值（★ 无范围检查）
004195b7  ... 绘制：索引 = (8 − [0x499088] + 玩家[+0x10]) & 7（视角 + 朝向，见 [A5]）
0041964d  for (i = 0; i < esi; i++)
00419667    frame = 6*i + dice[i] − 1           ; ★ 第 3 个实参（骰面帧号）
0041966d..  arg4 = TBL_X[idx] + 0x88 + 0x55 / arg5 = TBL_Y[idx] + 0x30 + 0x91
004196cf  for (i = 0; i < esi; i++) edi += dice[i]   ; ★ 返回 Σdice[i]
004196da  call 0x45285e(0x1f4)                  ; 定格 500 ms
004196e7  mov eax, edi / 收尾 / ret
```

★ 三条要点（全部由本测试实测钉住）：

| # | 事实 | 复刻 |
|---|---|---|
| 1 | **遥控骰子支完全不消耗 `rand()`**，且把骰子数**压成 1** | `rng/watcom.ts:114` `rollDice` |
| 2 | 随机支**恰好消耗 `ndices` 次** `rand()`，按下标 0,1,2 **顺序**取值 | 同 |
| 3 | `ndices == 0` ⇒ **一颗不掷、返回 0**（两处循环都不执行） | 同（空数组求和 = 0） |

★★ 本测试**整支驱动**（正函数入口 `push×4 + sub esp,0x1c`，`emu.call` 一进一出），
不是"尾段打 ret" —— 所以返回值的求和循环、渲染循环的次数、栈平衡
（`esp_delta == +4`）都在范围内。

--------------------------------------------------------------------------------
[B] 0x00445ada —— 随机抽一件道具（禮物 13 / 商店董事长进门有礼 共用）
--------------------------------------------------------------------------------

```asm
; @source 0x00445ada（逐条读出）
00445ada  push ebx / push esi / sub esp,0x80
00445ae2  xor esi,esi / xor eax,eax / xor ebx,ebx    ; esi=0(返回值) eax=道具下标 ebx=袋长
00445af0  cmp byte [eax + 0x497320], 0 / je 下一件  ; ★ 库存表：下标 0..7 ⇒ 道具 1..8
00445afd  mov cl, byte [eax + 0x497320]              ; 库存几件就塞几个（★ 按库存加权）
00445b07  mov byte [esp + ebx], al / inc ebx         ; 袋[ebx++] = 下标（★ 存的是 0 基下标）
00445b0e  test ebx,ebx / je 0x445b34                 ; ★ 空袋 ⇒ 返回 0 且**一次 rand 都不掷**
00445b12  call 0x456f2d / sar edx,0x1f / idiv ebx
00445b1e  movzx esi, byte [esp + edx]                ; 袋[rand() % 袋长]
00445b22  inc esi                                    ; ★ 1 基（道具编号）
00445b24  mov edx, [esp + 0x90]                      ; = 第一个实参 player
00445b2c  call 0x445a4d(player, 道具)                ; ★ 真发货（receive_tool）
00445b34  mov eax, esi / 收尾 / ret
```

★ 四个可以出错的地方，本测试逐个钉住：

1. **权重**：袋里是"库存件数"个重复下标 ⇒ 库存多的更容易抽到；
2. **空袋**：**不消耗 `rand()`**、返回 0（三个调用点全都把它当"没踩过"：
   `0x41b921`/`0x41ba64`/`0x42e995` 之后都 `test eax,eax`）；
3. **只抽 1..8 号**（`cmp eax,8 / jge`）—— 9..13 号不在袋里，永远抽不到；
4. **返回值与发货是两件事**：玩家已经拿满 9 件时 `0x445a4d` 拒绝，
   但本函数**照样返回道具编号**（调用方以为收到了）。

--------------------------------------------------------------------------------
打桩清单
--------------------------------------------------------------------------------

| VA / 位置 | 原用途 | 桩 |
|---|---|---|
| `0x00456f23` | CRT `rand()` 的状态取址（`call [0x488f4c]; add eax,0xc; ret`） | `mov eax,RAND_STATE; ret` ⇒ **`0x456f2d` 真跑**，于是"取值"与"消费了几次"都可断言 |
| `0x00450cda` | 19 B：写两个绘制全局 | `ret`（cdecl，调用方 `add esp,8`） |
| `0x0045144f` | 288 B：读 MKF 并贴图 | `ret`（调用方 `add esp,0x14`） |
| `0x004542ce` | 27 B：播声音 | `ret`（调用方 `add esp,8`） |
| `0x0045663e` | 306 B：画**一颗**骰子 | **记录桩**：把第 3/4/5 个实参记进暂存区再 `ret`（见下） |
| `0x0045285e` | 91 B：延时 500 ms（`Wait`） | `ret`（调用方 `add esp,4`） |
| `[0x48a0e0]` vtable `+0x64` | DirectDrawSurface `Lock` | 假对象/假 vtable + `ret 0x14` |
| `[0x48a0e0]` vtable `+0x80` | `Unlock` | `ret 8` |
| `[0x48a0dc]` vtable `+0x1c` | `BltFast` | `ret 0x18` |
| `0x00445a4d` | `receive_tool(player, tool)` | [B6]/[B7] **真跑**；[B1]/[B4]/[B8] 改成记录桩（分辨"到底调没调、实参是什么"） |

★ 三个 COM 桩的 `ret N` 不是猜的：按反汇编的压栈数（5/2/6 个 dword）取
`N = 压栈数×4 − 8` 会让尾声的 `add esp,0x1c + pop×4 + ret` 恰好落回返回地址 ——
实测 `esp_delta == +4` 且求和结果正确；把 `ret N` 改小 4（见可证伪性检查）
会让求和读到错位的栈槽（`0x159` 而不是 `0x3`）。

--------------------------------------------------------------------------------
VERDICT（与复刻逐条对照；★ 未改任何 TS 文件）
--------------------------------------------------------------------------------

**MATCH**

| 规则 | 原版证据 | 复刻 | 备注 |
|---|---|---|---|
| 随机支 = `rand()%6+1`、恰好消耗 `ndices` 次、按下标 0,1,2 顺序 | `0x419595`–`0x4195a7` | `rng/watcom.ts:108` `rollDice` | 5 个 seed × 1/2/3 颗逐值相同 |
| 强制支（遥控骰子）：**不掷 rand**、骰子数压成 1、原值照收（无范围检查） | `0x41958b` / `0x4195ae` / `0x4195b3` | 同 | `forced ∈ {1,5,6,7,0xFF,0x7FFFFFFF}` 全实测 |
| `ndices == 0` ⇒ 返回 0、不掷 rand | `0x419591` / `0x4196cf` | 同（空数组求和 0） | |
| 袋 = 道具 1..8，按库存件数重复；空袋返回 0 且**不掷 rand**；`rand % 袋长`；返回值 1 基 | `0x445af0`–`0x445b22` | `rules/object-landing.ts:385` `drawGiftTool` | 逐格核对 + `rand0` 精确控制 |
| 玩家落点：抽不到 ⇒ **不消耗随机数**、当没踩过 | `0x41b91f` `test eax,eax` | `object-landing.ts:664` + `reduce.ts:2120`（`randConsumed` 才前进 `rngState`） | MATCH |
| 只抽 1..8（9..13 不在袋里） | `0x445aeb` `cmp eax,8` | `object-landing.ts:391` `toolId <= 8` | MATCH |

**DISCREPANCY-1（库/随机流错位）** `packages/core/src/rules/npc-walk.ts:497`

```ts
if (objectType === OBJECT_TYPE_GIFT) return drawGiftTool(toolStock, rng.next());
```
`rng.next()` 是**实参**（JS 先求值再调用）⇒ 无论袋是否为空都推进随机流。
原版 `0x445b0e test ebx,ebx / je 0x445b34` ⇒ **空袋一次 rand 都不掷**（`0x456f2d` 的唯一
调用点在 `0x445b12`，在空袋判据之后）。本测试 [B4] 直接钉住 exe 的这一步：
全 0 库存时 `rand` 状态**原封不动**。
调用方 `reduce.ts:857`/`reduce.ts:1793` 都把 `rng.getState()` 写回 `state.rngState`，
⇒ 这一步真的会落进全局随机流。
**玩家可见后果**：8 种道具库存全为 0 时，小偷踩禮物会**多消耗一个随机数** ⇒
此后所有随机事件（掷骰 / AI 出牌 / 抽卡 / 命運新聞）整体错开一步 ——
与 `gaps/README.md` §四之二第 6/8/10 条属**同一类**偏差。

**DISCREPANCY-2（同一根因，商店支）** `packages/core/src/state/reduce.ts:4706`

```ts
if ((rng.next() & 1) !== 0) {
  const toolId = drawGiftTool(next.toolStock, rng.next());   // ← 无条件多掷一次
```
原版 `0x42e98d call 0x445ada` 也只有袋非空才掷（`0x42e9b9` 是卡片支）。
`enterShop` 结尾 `rngState: rng.getState()` ⇒ 同样会落进全局流。
**玩家可见后果**：同上；且 `reduce.ts:4707` 的 `if (toolId !== 0)` 守卫让复刻
**少**显示一次 `0x464378`「%s送您%s」文字框 —— 原版 `0x42e995` 之后到 `0x42ea02`
**没有任何** `test eax,eax`，toolId=0 也照走 `sprintf` + `0x440cac` 文字框
（名字取道具名表 `0x47feda` 的 0 号项；那一项 6 字节非文字数据，
**具体显示成什么字无法判定**，只能判定"会弹框"）。

**KNOWN LEGACY HAZARD（不驱动）** `0x445ae2 sub esp,0x80` 只留 128 字节袋子，
而袋子长度 = Σ库存件数（每件 1 字节）；库存合计 > 128 时原版会写穿栈局部。
实际可达性取决于库存上限，**无法判定**，故本测试不去驱动那段 UB。

跑法：cd rich4-spec && .venv/bin/python tests/test_watcom_shop.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STACK_TOP, STUB_BASE, Emu  # noqa: E402

# ── 被测函数 ──
DICE = 0x419572                    # fcn_00419572(player_idc, forced) → Σ点数
GIFT = 0x445ADA                    # rich4_receive_random_tool(player) → 道具号(1 基)/0
PRNG = 0x456F2D                    # CRT rand()（本测试让它真跑）
PRNG_ACCESSOR = 0x456F23           # rand 的状态取址

# ── LCG（docs/systems/game-loop.md §四；算法本身已由 tests/test_prng.py 钉过） ──
A_MUL, A_INC, MASK32 = 0x41C64E6D, 0x3039, 0xFFFFFFFF
A_INV = pow(A_MUL, -1, 1 << 32)    # 模 2^32 的乘法逆（用于"精确指定第一次 rand 的返回值"）

# ── 全局量（全部来自反汇编，不是猜的） ──
CUR_PLAYER = 0x49910C              # @source 0x419579
VIEW_ROTATION = 0x499088           # @source 0x4195cb `mov eax,8 / sub eax,[0x499088]`
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_DIRECTION, P_NDICES = 0x10, 0x12  # +0x10 → 0x496b78；+0x12 → 0x496b7a（@source 0x419580）
DICE_X_TBL, DICE_Y_TBL = 0x475224, 0x475228   # @source 0x4195d6 / 0x4195e3（步长 8）
STOCK_BASE = 0x497320              # 库存[下标 0] = 道具 1（@source 0x445af0 的 0x497320
                                   #   与 0x445a73 的 `[tool + 0x49731f]` 互证：下标 i ⇒ 道具 i+1）
TOOLS_BASE, TOOL_STRIDE = 0x49915B, 15   # @source 0x445a58..0x445a64（每玩家 15 槽）
MAX_TOOL_HOLD = 9                  # @source 0x445a64 `cmp byte [...],9 / jae`

SURFACE_A, SURFACE_B = 0x48A0E0, 0x48A0DC     # @source 0x419637 / 0x4196b0（COM 接口指针）

# ── 暂存区布局（SCRATCH 不参与 reset 快照，跨调用保持） ──
RAND_STATE = SCRATCH_BASE + 0x100
REC_COUNT = SCRATCH_BASE + 0x200
REC_COUNT_PTR = SCRATCH_BASE + 0x280
REC_FRAME = SCRATCH_BASE + 0x300
REC_X = SCRATCH_BASE + 0x340
REC_Y = SCRATCH_BASE + 0x380
G_COUNT = SCRATCH_BASE + 0x400
G_COUNT_PTR = SCRATCH_BASE + 0x480
G_TOOL = SCRATCH_BASE + 0x500
G_PLAYER = SCRATCH_BASE + 0x540
VTABLE = SCRATCH_BASE + 0x800
OBJECT = SCRATCH_BASE + 0x900

DRAW_DICE = 0x45663E               # 画一颗骰子（被整支替换成记录桩）
STUB_LOCK = STUB_BASE + 0x00
STUB_UNLOCK = STUB_BASE + 0x10
STUB_BLT = STUB_BASE + 0x20

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def u32(b):
    return struct.unpack("<I", b)[0]


def lcg(state):
    return (state * A_MUL + A_INC) & MASK32


def rand_seq(seed, n):
    """规格算法推出的前 n 个 rand() 返回值（与 test_prng.py 同一算法）。"""
    out, s = [], seed
    for _ in range(n):
        s = lcg(s)
        out.append((s >> 16) & 0x7FFF)
    return out


def seed_for_first_rand(r):
    """返回一个状态，使**下一次** rand() 恰好返回 r（0 ≤ r ≤ 0x7fff）。

    做法：让"掷后状态"精确等于 `r << 16`（低 16 位为 0 ⇒ 高 15 位就是 r），
    再用乘数在模 2^32 下的逆把它反推回"掷前状态"。LCG 的乘数是奇数 ⇒ 可逆。
    """
    assert 0 <= r <= 0x7FFF
    return ((r << 16) - A_INC) * A_INV & MASK32


def make_recorder(count_ptr, slots, first_arg_off):
    """生成一个记录桩：按顺序把第 `first_arg_off` 起的若干实参记进 `slots`。

    slots 是 (暂存基址, ...) —— 依次对应 [esp+first_arg_off], +4, +8 …
    桩体：mov eax,[count_ptr] / mov ecx,[eax] / 逐个 mov edx,[esp+off] 后
          mov [ecx*4+slot],edx / inc ecx / mov [eax],ecx / ret
    """
    code = b"\xA1" + struct.pack("<I", count_ptr) + b"\x8B\x08"
    for i, slot in enumerate(slots):
        off = first_arg_off + 4 * i
        code += b"\x8B\x54\x24" + bytes([off])                     # mov edx,[esp+off]
        code += b"\x89\x14\x8D" + struct.pack("<I", slot)          # mov [ecx*4+slot],edx
    code += b"\x41" + b"\x89\x08" + b"\xC3"
    return code


# ============================================================================
#  [A] 0x00419572 掷骰
# ============================================================================
class DiceWorld:
    """整支驱动 `0x419572`：真的 `rand()`，其余绘制/声音/DirectDraw 全打桩。"""

    #: 正函数入口 `push×4 + sub esp,0x1c`，1 个实参 ⇒ 栈帧是确定的
    LOCAL_DICE = STACK_TOP - 4 * 2 - 0x2C + 0x10     # dice[0]（@source 0x4195a7 的 [esp+0x10]）

    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG_ACCESSOR, b"\xB8" + struct.pack("<I", RAND_STATE) + b"\xC3")
        for va in (0x450CDA, 0x45144F, 0x4542CE, 0x45285E):
            self.emu.patch(va, b"\xC3")
        self.emu.patch(DRAW_DICE,
                       make_recorder(REC_COUNT_PTR, (REC_FRAME, REC_X, REC_Y), 0x0C))
        self.emu.patch(STUB_LOCK, b"\xC2\x14\x00")     # ret 0x14
        self.emu.patch(STUB_UNLOCK, b"\xC2\x08\x00")   # ret 8
        self.emu.patch(STUB_BLT, b"\xC2\x18\x00")      # ret 0x18
        vt = bytearray(0x100)
        struct.pack_into("<I", vt, 0x1C, STUB_BLT)
        struct.pack_into("<I", vt, 0x64, STUB_LOCK)
        struct.pack_into("<I", vt, 0x80, STUB_UNLOCK)
        self.emu.scratch_write(VTABLE, bytes(vt))
        self.emu.scratch_write(OBJECT, struct.pack("<I", VTABLE))
        self.emu.scratch_write(REC_COUNT_PTR, struct.pack("<I", REC_COUNT))

    def table_x(self, idx):
        return self.emu.readu32(DICE_X_TBL + idx * 8)

    def table_y(self, idx):
        return self.emu.readu32(DICE_Y_TBL + idx * 8)

    def run(self, ndices, forced=0, player=0, direction=0, view=0,
            seed=None, rand0=None, decoys=None):
        """`decoys = {玩家下标: (ndices, direction)}` —— 用来证明"读的是当前玩家那一份"。"""
        if seed is None:
            seed = seed_for_first_rand(rand0 if rand0 is not None else 0)

        def setup(e):
            e.write8(PLAYER_BASE + player * PLAYER_STRIDE + P_NDICES, ndices & 0xFF)
            e.write8(PLAYER_BASE + player * PLAYER_STRIDE + P_DIRECTION, direction & 0xFF)
            for p, (nd, dr) in (decoys or {}).items():
                e.write8(PLAYER_BASE + p * PLAYER_STRIDE + P_NDICES, nd & 0xFF)
                e.write8(PLAYER_BASE + p * PLAYER_STRIDE + P_DIRECTION, dr & 0xFF)
            e.write32(CUR_PLAYER, player)
            e.write32(VIEW_ROTATION, view)
            e.write32(SURFACE_A, OBJECT)
            e.write32(SURFACE_B, OBJECT)
            e.scratch_write(RAND_STATE, struct.pack("<I", seed))
            e.scratch_write(REC_COUNT, struct.pack("<I", 0))

        r = self.emu.call(DICE, [forced], setup=setup, timeout_insns=200000)
        state = u32(self.emu.scratch_read(RAND_STATE, 4))
        n = u32(self.emu.scratch_read(REC_COUNT, 4))
        return {
            "eax": r["eax"], "signed": r["signed"], "esp_delta": r["esp_delta"],
            "insns": r["insns"], "seed": seed, "state": state, "draws": n,
            "frames": [u32(self.emu.scratch_read(REC_FRAME + 4 * i, 4)) for i in range(n)],
            "x": [u32(self.emu.scratch_read(REC_X + 4 * i, 4)) for i in range(n)],
            "y": [u32(self.emu.scratch_read(REC_Y + 4 * i, 4)) for i in range(n)],
            "slots": [u32(self.emu.read(self.LOCAL_DICE + 4 * i, 4))
                      for i in range(max(n, 3))],
        }


# ============================================================================
#  [B] 0x00445ada 随机道具
# ============================================================================
class GiftWorld:
    """整支驱动 `0x445ada`：真的 `rand()`，真的（或记录的）`0x445a4d`。"""

    def __init__(self, stub_give=True):
        self.emu = Emu()
        self.emu.patch(PRNG_ACCESSOR, b"\xB8" + struct.pack("<I", RAND_STATE) + b"\xC3")
        self.stub_give = stub_give
        if stub_give:
            # 0x445a4d(player, tool)：cdecl ⇒ [esp+4]=player、[esp+8]=道具号
            self.emu.patch(0x445A4D,
                           make_recorder(G_COUNT_PTR, (G_PLAYER, G_TOOL), 0x04))
            self.emu.scratch_write(G_COUNT_PTR, struct.pack("<I", G_COUNT))

    def run(self, stock, player=0, have=None, seed=None, rand0=None):
        if seed is None:
            seed = seed_for_first_rand(rand0 if rand0 is not None else 0)

        def setup(e):
            # 库存表可多写几格（>8）——用来证明 0x445ada **只看 0..7**
            for i in range(min(len(stock), 12)):
                e.write8(STOCK_BASE + i, stock[i])
            for t, v in (have or {}).items():
                e.write8(TOOLS_BASE + player * TOOL_STRIDE + t, v)
            e.scratch_write(RAND_STATE, struct.pack("<I", seed))
            if self.stub_give:
                e.scratch_write(G_COUNT, struct.pack("<I", 0))

        r = self.emu.call(GIFT, [player], setup=setup, timeout_insns=200000)
        n = u32(self.emu.scratch_read(G_COUNT, 4)) if self.stub_give else None
        return {
            "eax": r["eax"], "signed": r["signed"], "esp_delta": r["esp_delta"],
            "insns": r["insns"], "seed": seed,
            "state": u32(self.emu.scratch_read(RAND_STATE, 4)),
            "stock": [self.emu.read8(STOCK_BASE + i) for i in range(10)],
            "have": {t: self.emu.read8(TOOLS_BASE + player * TOOL_STRIDE + t)
                     for t in range(0, 10)},
            "given": n,
            "given_tool": u32(self.emu.scratch_read(G_TOOL, 4)) if n else None,
            "given_player": u32(self.emu.scratch_read(G_PLAYER, 4)) if n else None,
        }


def bag_of(stock):
    """复刻侧的袋（也是本测试的期望值）：道具 1..8，按库存件数重复。"""
    bag = []
    for i in range(8):
        bag.extend([i + 1] * (stock[i] if i < len(stock) else 0))
    return bag


# ============================================================================
def main():
    print("差分测试：掷骰 fcn_00419572 ＋ 随机道具 0x445ada")
    print("预言机：Rich4/rich4.exe 的机器码（Unicorn）\n")

    dice = DiceWorld()
    gift_rec = GiftWorld(stub_give=True)

    print("\nA0 测试台自检：桩过的 `0x456f23` 让 `0x456f2d` **真跑**（返回值 == LCG 规格）")
    st0 = 0x12345678

    def _setup_prng(e):
        e.scratch_write(RAND_STATE, struct.pack("<I", st0))

    r0 = dice.emu.call(PRNG, [], setup=_setup_prng)
    case("rand(0x12345678) == ((s*0x41c64e6d+0x3039)>>16)&0x7fff",
         r0["eax"], rand_seq(st0, 1)[0])
    case("  且 0x456f2d 已把状态写回同一地址", u32(dice.emu.scratch_read(RAND_STATE, 4)),
         lcg(st0))

    # ────────────────────────────────────────────────────────────────────
    print("[A] 0x00419572 掷骰 —— 随机支：取值、次数、帧号、栈槽、和")
    # ────────────────────────────────────────────────────────────────────
    print("\nA1 单颗（ndices=1）：die == rand()%6+1，状态恰好前进 1 步")
    for r0 in (0, 5, 6, 0x7FFE, 0x7FFF):
        w = dice.run(1, rand0=r0)
        want = [r0 % 6 + 1]
        case(f"rand={r0} ⇒ dice={want}（原版栈槽 [S+0x10] 逐位相同）",
             w["slots"][0], want[0])
        case(f"rand={r0} ⇒ 返回值 = Σdice = {want[0]}", w["eax"], want[0])
        case(f"rand={r0} ⇒ 状态前进 1 步", w["state"], lcg(w["seed"]))
        case(f"rand={r0} ⇒ 画 1 颗、帧号 = 6*0+v-1 = {want[0] - 1}",
             (w["draws"], w["frames"]), (1, [want[0] - 1]))

    print("\nA2 三颗（ndices=3）：下标顺序 0,1,2；三次 rand 的取值一一对应")
    for r0 in (0, 3, 0x1234, 0x7FFF):
        w = dice.run(3, rand0=r0)
        seq = rand_seq(w["seed"], 3)
        want = [r % 6 + 1 for r in seq]
        case(f"rand0={r0} ⇒ dice={want}（逐槽）", w["slots"][:3], want)
        case(f"rand0={r0} ⇒ 返回值 = {sum(want)}", w["eax"], sum(want))
        case(f"rand0={r0} ⇒ 状态前进**恰好 3 步**",
             w["state"], lcg(lcg(lcg(w["seed"]))))
        case(f"rand0={r0} ⇒ 画 3 颗、帧号 = 6i+vi-1",
             (w["draws"], w["frames"]), (3, [6 * i + want[i] - 1 for i in range(3)]))
        case(f"rand0={r0} ⇒ seq[0] == 指定的 rand0", seq[0], r0)

    print("\nA3 两颗（ndices=2）：消耗次数 == ndices（不是固定 2 也不是 3）")
    w2 = dice.run(2, rand0=0x1111)
    seq2 = rand_seq(w2["seed"], 2)
    case("ndices=2 ⇒ dice 与 2 次 rand 一致", w2["slots"][:2], [r % 6 + 1 for r in seq2])
    case("ndices=2 ⇒ 返回值 = Σ", w2["eax"], sum(r % 6 + 1 for r in seq2))
    case("ndices=2 ⇒ 状态前进 2 步", w2["state"], lcg(lcg(w2["seed"])))
    case("ndices=2 ⇒ 画 2 颗", w2["draws"], 2)

    print("\nA4 ★ 强制支（遥控骰子）：不掷 rand、压成 1 颗、原值照收")
    for forced in (1, 5, 6, 7, 0xFF, 0x7FFFFFFF):
        w = dice.run(3, forced=forced, rand0=0x2222)   # 故意给 3 颗骰 + 一颗好 seed
        case(f"forced={forced} ⇒ 只 1 颗、值 = {forced}", (w["draws"], w["slots"][0]),
             (1, forced))
        case(f"forced={forced} ⇒ 返回值 = {forced}", w["eax"], forced)
        case(f"forced={forced} ⇒ ★ rand 状态**一步都不动**", w["state"], w["seed"])
        case(f"forced={forced} ⇒ 帧号 = 6*0+v-1", w["frames"], [forced - 1])

    print("\nA5 ★ ndices=0：两颗循环都不执行 ⇒ 返回 0、不掷 rand")
    w = dice.run(0, rand0=0x3333)
    case("ndices=0 ⇒ 返回 0", w["eax"], 0)
    case("ndices=0 ⇒ rand 状态不动", w["state"], w["seed"])
    case("ndices=0 ⇒ 一颗都不画", w["draws"], 0)

    print("\nA6 ndices 的取址 = 当前玩家*0x68 + 0x496b7a（换玩家结论随之变）")
    # 玩家 0 的 +0x12 故意写成 1（诱饵）：若取址串位就会只画 1 颗 / 只走 1 步
    w = dice.run(3, player=2, rand0=0x4321, decoys={0: (1, 0)})
    case("player=2 的 +0x12=3 ⇒ 画 3 颗（诱饵 玩家0=1 不参与）", w["draws"], 3)
    case("player=2 ⇒ 状态前进 3 步", w["state"], lcg(lcg(lcg(w["seed"]))))
    case("player=2 ⇒ 返回 = 自己 3 颗之和",
         w["eax"], sum(r % 6 + 1 for r in rand_seq(w["seed"], 3)))
    w0 = dice.run(1, player=0, rand0=0x4321, decoys={2: (3, 0)})
    case("同一 seed 下改读 player=0（ndices=1，诱饵 玩家2=3）⇒ 只画 1 颗", w0["draws"], 1)
    case("  且返回 = player=2 那次（ndices=3）的第 1 颗 —— 同一颗 seed、同一颗骰",
         w0["eax"], dice.run(3, player=2, rand0=0x4321)["slots"][0])

    print("\nA7 ★ 朝向/视角索引 = (8 − [0x499088] + 玩家[+0x10]) & 7（逐一对照 exe 真表）")
    for direction, view in ((0, 0), (7, 0), (0, 8), (0, 9), (3, 1), (2, 10), (6, 1)):
        w = dice.run(1, direction=direction, view=view, rand0=1)
        idx = (8 - view + direction) & 7
        case(f"dir={direction} view={view} ⇒ 索引 {idx} 的 X = 表值+0x88+0x55",
             w["x"][0], (dice.table_x(idx) + 0x88 + 0x55) & 0xFFFFFFFF)
        case(f"dir={direction} view={view} ⇒ 索引 {idx} 的 Y = 表值+0x30+0x91",
             w["y"][0], (dice.table_y(idx) + 0x30 + 0x91) & 0xFFFFFFFF)
    case("dir=0 view=0 与 dir=7 view=7 命中同一格（(8−7+7)&7 == 0）",
         (dice.run(1, direction=0, view=0, rand0=1)["x"][0]),
         (dice.run(1, direction=7, view=7, rand0=1)["x"][0]))

    print("\nA8 栈平衡：整支驱动后 esp_delta 恒为 +4（1 个实参，cdecl）")
    case("ndices=1 ⇒ esp_delta=+4", dice.run(1, rand0=9)["esp_delta"], 4)
    case("ndices=3 ⇒ esp_delta=+4", dice.run(3, rand0=9)["esp_delta"], 4)
    case("forced=5 ⇒ esp_delta=+4", dice.run(3, forced=5, rand0=9)["esp_delta"], 4)
    case("ndices=0 ⇒ esp_delta=+4", dice.run(0, rand0=9)["esp_delta"], 4)

    print("\nA9 复刻对照：rollDice() 的逐条镜像（纯 Python 重放，不改 TS）")
    for ndices, forced, r0 in ((1, 0, 0x0BAD), (2, 0, 0x0BAD), (3, 0, 0x0BAD),
                               (3, 4, 0x0BAD), (1, 6, 0x0BAD)):
        w = dice.run(ndices, forced=forced, rand0=r0)
        s = w["seed"]
        if forced != 0:
            rec = [forced]                       # ndices 被压成 1
        else:
            rec = []
            for _ in range(ndices):
                s = lcg(s)
                rec.append(((s >> 16) & 0x7FFF) % 6 + 1)
        case(f"rollDice(ndices={ndices}, forced={forced}) == exe（点数/和/掷后状态）",
             (w["slots"][:len(rec)], w["eax"], w["state"]), (rec, sum(rec), s))

    # ────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 76)
    print("[B] 0x00445ada 随机道具 —— 加权袋、空袋不掷 rand、1..8 边界、发货")
    print("=" * 76)

    print("\nB1 袋 = 道具 1..8 按库存件数重复（精确控制 rand ⇒ 逐格核对）")
    stock = [1, 0, 2, 0, 0, 0, 0, 0]
    bag = bag_of(stock)
    case("袋内容（期望值）", bag, [1, 3, 3])
    for r0 in (0, 1, 2):
        w = gift_rec.run(stock, rand0=r0)
        case(f"rand={r0} ⇒ 袋[{r0}%3] = {bag[r0 % 3]}", w["eax"], bag[r0 % 3])
        case(f"rand={r0} ⇒ 状态恰好前进 1 步", w["state"], lcg(w["seed"]))
        case(f"rand={r0} ⇒ 转交 0x445a4d(player=0, {bag[r0 % 3]})",
             (w["given"], w["given_player"], w["given_tool"]),
             (1, 0, bag[r0 % 3]))

    print("\nB2 ★ 加权：某一号库存 3 件、其余全 0 ⇒ 抽 20 个 rand 值全都命中它")
    only3 = [0, 0, 3, 0, 0, 0, 0, 0]
    hits = {gift_rec.run(only3, rand0=r)["eax"] for r in range(20)}
    case("库存 [0,0,3,...] ⇒ 结果集 = {3}", hits, {3})
    only1 = [7, 0, 0, 0, 0, 0, 0, 0]
    hits = {gift_rec.run(only1, rand0=r)["eax"] for r in range(20)}
    case("库存 [7,0,...] ⇒ 结果集 = {1}", hits, {1})

    print("\nB3 ★ 袋长与取模边界（含 rand ≥ 袋长 与 rand = 0）")
    stock = [0, 0, 0, 0, 0, 1, 0, 0]          # 袋 = [6]
    w = gift_rec.run(stock, rand0=0x7FFF)
    case("袋长 1 ⇒ 32767%1 = 0 ⇒ 恒为 6", w["eax"], 6)
    w = gift_rec.run(stock, rand0=0)
    case("袋长 1、rand=0 ⇒ 6", w["eax"], 6)
    stock = [1, 1, 0, 0, 0, 0, 0, 1]          # 袋 = [1,2,8]
    bag = bag_of(stock)
    case("袋 = [1,2,8]", bag, [1, 2, 8])
    for r0 in (0, 1, 2, 3, 5, 0x7FFF):
        w = gift_rec.run(stock, rand0=r0)
        case(f"rand={r0} ⇒ 袋[{r0}%3] = {bag[r0 % 3]}", w["eax"], bag[r0 % 3])

    print("\nB4 ★★ 空袋：返回 0、**一次 rand 都不掷**、0x445a4d **一次都不调**")
    w = gift_rec.run([0] * 8, rand0=0x5555)
    case("全 0 库存 ⇒ 返回 0", w["eax"], 0)
    case("全 0 库存 ⇒ ★ rand 状态原封不动（消费 0 次）", w["state"], w["seed"])
    case("全 0 库存 ⇒ 0x445a4d 调用次数 = 0", w["given"], 0)
    w = gift_rec.run([], rand0=0x5555)
    case("库存表整体为 0 ⇒ 同样返回 0、不掷 rand", (w["eax"], w["state"]), (0, w["seed"]))

    print("\nB5 ★ 只扫下标 0..7（= 道具 1..8）；库存表第 9 项（= 道具 9）永远抽不到")
    w = gift_rec.run([0, 0, 0, 0, 0, 0, 0, 0, 9], rand0=0x6666)
    case("只有道具 9 有货（下标 8，本函数不看这一格）⇒ 返回 0", w["eax"], 0)
    case("同上 ⇒ 一次 rand 都不掷", w["state"], w["seed"])
    case("同上 ⇒ 库存第 9 格的 9 一件都没被取走", w["stock"][8], 9)
    w = gift_rec.run([1, 0, 0, 0, 0, 0, 0, 0, 9], rand0=0x6666)
    case("道具 1 有货 + 道具 9 有货 ⇒ 结果只能是 1（袋里看不到 9）", w["eax"], 1)

    print("\nB6 ★ 实发货（真跑 0x445a4d）：持仓 +1、库存 −1（同一个字节）")
    real = GiftWorld(stub_give=False)
    w = real.run([0, 0, 2, 0, 0, 0, 0, 0], player=1, rand0=1)
    case("rand=1 ⇒ 抽到道具 3", w["eax"], 3)
    case("玩家 1 的道具 3 持仓 0→1", w["have"][3], 1)
    case("库存（0x497320+2 ⇒ 道具 3）2→1", w["stock"][2], 1)
    case("★ 库存的第 1、2 格未动", (w["stock"][0], w["stock"][1]), (0, 0))
    w = real.run([0, 0, 2, 0, 0, 0, 0, 0], player=2, rand0=1)
    case("换玩家 2：抽到同一个道具 3", w["eax"], 3)
    case("★ 只动玩家 2 的槽（步长 15）：玩家 2 持仓 1、玩家 0 仍 0",
         (w["have"][3], real.emu.read8(TOOLS_BASE + 3)), (1, 0))

    print("\nB7 ★★ 持满 9 件：0x445a4d 拒绝，但本函数**照样返回道具编号**")
    w = real.run([0, 0, 2, 0, 0, 0, 0, 0], player=0, have={3: MAX_TOOL_HOLD}, rand0=1)
    case("持仓已是 9 ⇒ 返回值仍是 3（调用方以为收到了）", w["eax"], 3)
    case("持仓仍是 9", w["have"][3], 9)
    case("★ 库存**不扣**（仍 2）", w["stock"][2], 2)

    print("\nB8 返回值语义：1 基；与 0x445a4d 的实参一致（不是 0 基下标）")
    for stock_case in ([1, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 1],
                       [0, 1, 1, 0, 0, 0, 0, 0]):
        bag = bag_of(stock_case)
        w = gift_rec.run(stock_case, rand0=0)
        case(f"库存 {stock_case} ⇒ 返回袋[0]+0（1 基）", w["eax"], bag[0])
        case(f"  同例：转交实参 == 返回值", w["given_tool"], w["eax"])

    print("\nB9 复刻对照：drawGiftTool() 的逐条镜像（纯 Python 重放，不改 TS）")
    for stock_case in ([1, 0, 2, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0],
                       [2, 2, 2, 2, 2, 2, 2, 2], [0] * 8):
        for r0 in (0, 1, 7, 0x7FFF):
            w = gift_rec.run(stock_case, rand0=r0)
            bag = bag_of(stock_case)          # 复刻侧：toolId 1..8，toolStock[toolId]
            want = 0 if not bag else bag[r0 % len(bag)]
            case(f"drawGiftTool({stock_case}, {r0}) == {want}", w["eax"], want)
            case("  随机流是否推进：exe 只在袋非空时前进（复刻须照此）",
                 w["state"] == w["seed"], (want == 0))

    print("\nB10 栈平衡：整支驱动后 esp_delta 恒为 +4（1 个实参，cdecl）")
    case("有货 ⇒ esp_delta=+4", gift_rec.run([1, 0, 0, 0, 0, 0, 0, 0], rand0=0)["esp_delta"], 4)
    case("空袋 ⇒ esp_delta=+4", gift_rec.run([0] * 8, rand0=0)["esp_delta"], 4)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
