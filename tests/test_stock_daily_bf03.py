#!/usr/bin/env python3
"""
通道 2 差分测试 · 股市两支（**每日可成交量** + **电脑买股这一拍**）

本文件覆盖两个**从未被驱动过**的函数（与既有 `test_stock_daily.py`（`0x4291d6` 行情）、
`test_stock_price.py`（`0x428ec5` 落档）、`test_sell_stock.py`（`0x428e23` 卖 / `0x428d2a` 买）、
`test_stock_transfer.py`（`0x42565c` 公佈欄股票）**不相交**）：

| 段 | VA | 尺寸 | 调用点 | 语义 |
|---|---|---|---|---|
| `[A]` | `0x0042915a` | 124 B | `0x41c868`（日推进）、`0x407dfe`（开局） | 12 支股票**每日重算可成交量** `+0x0a` |
| `[B]` | `0x0042bf03` | **2,204 B** | `0x418de6`（电脑调度步 0） | 电脑回合「买股」：三道闸 → 预算 → 12 支打分 → qsort → 抽签 → 下单 |

> ★ **尺寸订正**：`gen/functions.json` 记 `0x42bf03` = **370 B**（止于 `0x42c075`），
> 那是把**循环体入口**（`0x42c075` 的 `fild [ecx+0x2c]`）误当成了函数入口 ——
> 真函数一直延伸到卖股那一支入口 `0x42c79f` 之前的**共享尾声** `0x42c794`，
> 即 `0x42c79f − 0x42bf03 = 0x89c` = **2,204 B**。与 §7.139 的两处尺寸订正同族。
> 本文件的整支驱动是从**真入口** `0x42bf03` 进的。

## [A] `0x42915a` 语义（逐条来自反汇编）

```asm
0042915f  xor esi,esi                       ; ★ 循环从**记录 0** 起
00429170  ebx = esi*9*4 = esi*36
0042917a  dx  = word [ebx+0x496988]         ; 股票 +0x08「流通股数」
00429181  cmp dx, 0x3e8 / jbe 0x429163      ; ★ **无符号** 16 位比较
00429163     word [ebx+0x49698a] = dx       ;   ≤1000 ⇒ 原样照抄，**不掷 rand**
00429188  call 0x456f2d                     ; rand()
00429197  idiv 2000                         ; edx = rand % 2000（sar edx,0x1f ⇒ 有符号）
00429199  edx += 1000                       ; factor ∈ [1000, 2999]（rand<0 时可为 999）
0042919f  ax = word [ebx+0x496988]          ; **零扩展**回读 0x08
004291ae  fild factor（整数）→ st0
004291b4  fdiv dword [0x463fc0]（= 10000.0f）  ; ★ st0 = factor/10000，**不落内存**
004291ba  fmulp st(1)                        ; ★ × 流通股数，仍用**未舍入的商**
004291bc  0x457dbc（把 x87 舍入档改成向零）→ 0x4291c1 `fistp` → `mov word [+0x0a], ax`
```

⇒ `f10(+0x0a) = 流通股数 ≤ 1000 ? 流通股数 : trunc(流通股数 × (1000 + rand%2000) / 10000)`。
`rand` **只在该支 >1000 时**掷；`+0x08` 本身**不被改**。
★ 那个商**没有过一次 f32**（对比 `0x429260` 的 `fst dword [+0x20]` 才是真的存 f32）
—— 复刻却写了 `Math.fround(r / 10000)`，见 **DISCREPANCY #3**。

## [B] `0x42bf03` 语义（逐条来自反汇编）

```asm
0042bf14  call rand / idiv 3 / test edx,edx / jne 结束   ; ★ 闸0：rand()%3 != 0 ⇒ 走人
0042bf30  cmp byte [player*0x68 + 0x496b82], 0 / je 结束 ; ★ 闸1：+0x1a stockRatio == 0
0042bf3d  call 0x428d01 / cmp eax,1 / je 结束            ; ★ 闸2：休市（==1 才算）
0042bf4b  edx = player+0x2c（還款到期日）
0042bf53  if (edx != 0) { 0x4521aa(今天, 到期日) ; if (< 0xf) 结束 }   ; ★ 闸3 有符号
0042bf94  for i in 0..11: 市值 = trunc(持股[i] × 现价[i] + f32(市值))   ; 逐支过一次 f32
0042c002  target = trunc((市值 + 存款 + 现金) × stockRatio / 100)        ; imul + idiv（有符号）
0042c043  if (市值 >= target) 结束
0042c04d  可投 = target − 市值 ; if (可投 > 存款) 可投 = 存款
0042c58c  for i in 0..11:                                               ; ★ 打分循环（记 0 起）
            停牌(+0x06)≠0 | 0x4295ea(i)==1(漲停) | +0x0a==0 ⇒ 0 分
            无企业(+0x04==0): 存款 ≤ 30000×pi ⇒ 0 分；否则按 avg24/avg6 三档 +2/+4/+2
            有企业:           存款 ≤ 20000×pi ⇒ 0 分；否则按月均盈余 3 档 + 董事長 3 项 + 2 档
            记录 = (i<<16) | 分（低字 = 分）
0042c63d  qsort(记录, 12, 4, 0x42bed0)     ; 比较器比**低字**（16 位有符号）⇒ 分降序
0042c67a  逐名次 i：0 分跳过；rand()%24 <= 12−i 才选中；否则下一名；全落空 ⇒ −1
0042c6e2  股数 = trunc(可投 / 现价) ; ==0 ⇒ 结束 ; 超过 +0x0a ⇒ 取 +0x0a
0042c72d  0x428d2a(player, 股票, 股数, 1)   ; 下单（cdecl 四参）
```

★ `[B]` 的 `rand` 消费：闸0 一次；之后**打分循环一次都不掷**；抽签循环**每个非 0 分名次掷一次**。

## 打桩清单

| VA | 原用途 | 桩 | 理由 |
|---|---|---|---|
| `0x456f2d` | CRT `rand` | 序列桩 + 调用计数 | 本测试要钉的是**取模规则与消费次数** |
| `0x428d01` | 休市判定（真身查 `[0x4990dc]` + 日期表） | 数据槽返回值 | 日期表口径另属 `stock-market.ts` |
| `0x4521aa` | 日期差 | 数据槽返回值 + **记录两个实参** | 只为钉「只在到期日≠0 时调用」与实参序 |
| `0x4295ea` | 漲停判定 | 逐支数据表 | 它自己（含 `0x428ec5` 落档）另属 `test_stock_price.py` |
| `0x428d2a` | 真·买入 | **只记录四个实参 + 计数** | 它自己的语义已由 `test_sell_stock.py` 反向驱动 |
| `0x41d433` / `0x452946` / `0x457110` / `0x440cac` | 下单后的重绘/取名/格式化/弹框 | `ret`（弹框另计次） | 纯表现层 |
| `0x457e6c` | Watcom `qsort` | ★ **等价的选择排序**（调用**真比较器 0x42bed0**） | **工具限制**：该 `qsort` 在本仿真器上必崩（见下） |

> ★ **测试台硬限制（新增一条）**：Watcom 的 `qsort 0x457e6c`（`push es/fs/gs` +
> `enter 0x150,0`）在本 Unicorn 上**任何 n 都在 `0x457e42` 报 `UC_ERR_READ_UNMAPPED`**
> （实测 n=1/2/3/12 全部失败），与 `memmove 0x456de8` 的 `push es` 同族。
> 故用一个**位置无关的选择排序**替换它，并**每次比较都 call 真比较器 `0x42bed0`**
> ——排序契约（按比较器升序）与算法无关，**分数互不相同时任何正确排序给出同一排列**，
> 故下游（抽签 + 下单）仍是原版机器码。**平手次序因此不在本测试的判定范围内**
> （原版 `qsort` 不稳定 ⇒ 已登记 **D-006**，复刻按下标升序）。

## 与复刻的对照（`ai/stock-policy.ts` / `ai/policy.ts` / `places/stock-market.ts`）

| 规则 | 原版 | 复刻 | 裁决 |
|---|---|---|---|
| `[A]` 流通股数 ≤1000 原样 | `jbe 0x3e8` | `stock-market.ts:521` `if (s.shares <= 1000)` | MATCH |
| `[A]` rand 只在该支掷 | `call` 在 `jbe` **之后** | 同 | MATCH |
| `[A]` 除数/取整 | 商**不落内存**、直接 `fmulp`（FPU 精度）+ 向零 | `stock-market.ts:525` `Math.trunc(Math.fround(shares * Math.fround(r/10000)))` — **多两次 f32 舍入** | ★★ **DISCREPANCY #3** |
| `[B]` 闸1/2/3 | `+0x1a==0` / `0x428d01==1` / 差<15 | `stock-policy.ts:323/327/331` | MATCH |
| `[B]` 预算与两道夹 | `stock-policy.ts:335-337` | 同 | MATCH（6 例） |
| `[B]` 无企业 +2 的**第二个判据** | ★ **`momentum(+0x1c) > 2.0`**（`0x42c4bb`，`cmp dword … ,0x40000000`） | `stock-policy.ts:222` **`s.volatility(+0x18) > 2.0`** | ★★ **DISCREPANCY #1** |
| `[B]` **闸0 `rand()%3`**（进场与否） | `0x42bf14 idiv 3 / jne 结束` ⇒ **只有 1/3 的回合看股市** | **没有**（`ai/policy.ts:150-151` 直接 `decideStockTrade`；对比卖股侧 `stock-policy.ts:551` 有 `aiRoll(state, 0x42c802, 3)`） | ★★ **DISCREPANCY #2** |
| `[B]` 其余门槛/+3/+5/抽签/股数 | — | — | MATCH |

### DISCREPANCY #1（A 级，玩家可见）

```asm
0042c4bb  cmp dword ptr [edx + 0x49699c], 0x40000000   ; edx = 股票×36 ⇒ +0x1c = **momentum**
```
`ai/stock-policy.ts:222` 判的是 `s.volatility`（= `stock_info +0x18`，`stock-policy.ts:277`），
而 `+0x1c` 在复刻里叫 **`trend`**（`places/stock.ts:83`，注释就写着 `@source +28`），**根本没进 `StockScoreInput`**。
`+0x18` 的取值域实测（直读 `0x47f072` 的 96 条）是 **0.4…2.0**，**没有一支 > 2.0**
⇒ 复刻这条 `+2` **永远拿不到**；原版在「动能 > 2.0」时会给。
后果：无上市企业的股票在「现价 < 2.5×参考价 且 近 6 日均价高于近 24 日」时，
原版 AI 多 2 分、复刻少 2 分 ⇒ **AI 选股排序在动能 > 2 的交易日整体偏移**
（差分实证见 `[B8]`：`vol=1.0, mom=3.0` ⇒ 原版 +2；`vol=3.0, mom=0` ⇒ 原版 0）。

### DISCREPANCY #2（A 级，玩家可见）

`0x42bf03` 的**头 0x2b 字节**就是一道硬币：`rand()%3 != 0` ⇒ 当场返回（`0x42bf27 jne 0x42c794`）。
复刻的 `decideStockTrade`（`ai/stock-policy.ts:318`）**从 0x42bf30 起**（其文件头注释也自称
「入口 VA 0x0042bf30，三道闸」）—— 漏掉了这道闸。卖股侧则有对应实现
（`stock-policy.ts:551` 的 `aiRoll(state, 0x42c802, 3)`，对应原版 `0x42c802` 的 `idiv 3`）。
后果：**复刻 AI 每回合都在看股市（只要另三闸过），原版只有 1/3 的回合看** ⇒
复刻 AI 买股频率约为原版 3 倍，胜率/资产曲线与原件不可比。

### DISCREPANCY #3（A 级，玩家可见）

原版 `0x4291b4 fdiv dword [0x463fc0]` 之后**没有 `fstp dword`** —— 那个商留在 x87 里，
`0x4291ba fmulp st(1)` 直接乘流通股数，全程 FPU 精度，最后才 `fistp` 截断。
复刻 `places/stock-market.ts:525` 却写成
`u16(Math.trunc(Math.fround(s.shares * Math.fround(r / 10000))))` —— **两次多余的 f32 舍入**。

`[A12]`–`[A14]` 三格**同时**满足「扩展精度模型 == double 模型 == 预言机」，
故与仿真器的 x87 精度无关，是硬差（复刻一律少 1）：

| 流通股数 | `rand%2000` | factor | 预言机（原版） | 复刻 |
|---|---|---|---|---|
| 3000 | 370 | 1370 | **411** | 410 |
| 3000 | 510 | 1510 | **453** | 452 |
| 4000 | 255 | 1255 | **502** | 501 |

（在 `shares ∈ {3000,4000,5000,6000,10000}` × `factor ∈ [1000,3000)` 的域上，
「扩展 == double ≠ 复刻」的格子共 **195** 个。）
后果：`+0x0a` 是**当日可成交量的硬上限**（`[B]` 的股数封顶、柜台「交易量」列都读它）
⇒ 这些格子上复刻 AI 可买股数**少 1**、玩家看到的交易量列也**少 1**。

### 两处工具限制（登记，不据此判复刻错）

1. **Watcom `qsort 0x457e6c` 在本仿真器上必崩**（`push es/fs/gs` + `enter 0x150,0`，
   实测 n=1/2/3/12 全部 `UC_ERR_READ_UNMAPPED @0x457e42`）⇒ 用等价选择排序替换，
   **真比较器 `0x42bed0` 照跑**；平手次序因此不判（原版 qsort 不稳定，已登记 D-006）。
2. ★★ **仿真器的 x87 按 53 位 double 算，不是 80 位扩展精度**。实测补桩：
   `1.0f + 2^-60`（80 位可表示）与 `10.0f × 1.2(double)` 都给出 double 结果（12.0）。
   真机 FPCW=0x027F ⇒ PC=扩展 ⇒ `10.0f × 1.2` = 11.9999999999999995559… < 12。
   ⇒ `[B12]` 的 **恰好 `现价 == A×1.2`** 那一格**无法判定**，本文件只钉 11.9 / 12.1 两侧，
   不写边界断言。此外 `[A]` 与其余比较的取值都远离边界，两种精度给出同一结论（不受影响）。

跑法：cd rich4-spec && .venv/bin/python tests/test_stock_daily_bf03.py
"""
import os
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE, STACK_TOP  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ESP  # noqa: E402

# ── 被测函数 ──────────────────────────────────────────────────────────
VOLUME = 0x42915A            # [A] 每日重算可成交量
BUY = 0x42BF03               # [B] 电脑买股这一拍

# ── 被调 / 打桩 ───────────────────────────────────────────────────────
PRNG = 0x456F2D
CLOSED = 0x428D01
DATE_DIFF = 0x4521AA
LIMITUP = 0x4295EA
QSORT = 0x457E6C
BUY_EXEC = 0x428D2A
REDRAW = 0x41D433
NAME_FMT = 0x452946
SPRINTF = 0x457110
MSGBOX = 0x440CAC

# ── 全局表 / 全局量（stocks.md §1.3）──────────────────────────────────
STOCKS = 0x496980            # 12 × 36（**绝对地址**，不是指针）
S_COMPANY, S_PAUSE, S_NEWS = 0x04, 0x06, 0x07
S_SHARES, S_F10 = 0x08, 0x0A
S_BASE, S_OPEN, S_PRICE, S_VOL, S_MOM, S_RAND = 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20
STOCK_STRIDE = 36

HOLD, HOLD_STRIDE = 0x4971A0, 0x60      # 玩家 × 12 支 × 8（+0 股数、+4 均价）
HISTORY = 0x497328                      # 12 × 144 × f32
RING = 0x499100                         # 环形下标 0..0x8f
COMM_PTR = 0x498E7C                     # 上市企业表基址（1 基，步长 0x34）
PRICE_INDEX = 0x4990E8
TOTAL_MONTHS = 0x499084
TODAY = 0x497160
PLAYER, PLAYER_STRIDE = 0x496B68, 0x68
P_RATIO, P_CASH, P_BANK, P_DUE = 0x1A, 0x1C, 0x20, 0x2C

# ── 暂存区槽（SCRATCH 不参与 reset 快照 ⇒ 每个用例必须显式写全）────────
RAND_SEQ = SCRATCH_BASE + 0x2000
RAND_PTR = SCRATCH_BASE + 0x3000
RAND_N = SCRATCH_BASE + 0x3004
CLOSED_SLOT = SCRATCH_BASE + 0x3008
DIFF_SLOT = SCRATCH_BASE + 0x300C
DATE_A1 = SCRATCH_BASE + 0x3010
DATE_A2 = SCRATCH_BASE + 0x3014
DATE_N = SCRATCH_BASE + 0x3018
LU_TAB = SCRATCH_BASE + 0x3020          # 12 dwords
LU_N = SCRATCH_BASE + 0x3060
BUY_N = SCRATCH_BASE + 0x3064
BUY_ARGS = SCRATCH_BASE + 0x3068        # (player, stock, shares, flag)
TAIL_N = SCRATCH_BASE + 0x3078
COMM = SCRATCH_BASE + 0x4000            # 上市企业表（[0x498e7c] 指向这里）

STOP_SCORING = 0x42C63D      # 打分循环结束、qsort 之前（取回 12 个记录）
RET_SENTINEL = 0x53FFF0      # 与 emulate.py 同值：落在栈映射内
SENTINEL = 0xA5A5
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<20} 期望 {want!s}")
    return ok


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32frombits(b):
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= (1 << 31) else v


def round_ext(fr, bits=64):
    """把精确有理数就近舍入到 `bits` 位有效位（x87 扩展精度，就近偶数）。"""
    if fr == 0:
        return Fraction(0)
    sign = -1 if fr < 0 else 1
    x = abs(fr)
    e = 1
    while Fraction(2) ** e <= x:
        e += 1
    while e > 1 and Fraction(2) ** (e - 1) > x:
        e -= 1
    scale = Fraction(2) ** (e - bits)
    q = x / scale
    n = q.numerator // q.denominator
    r = q - n
    if r > Fraction(1, 2) or (r == Fraction(1, 2) and n % 2 == 1):
        n += 1
    return sign * n * scale


def ext_mul(a_f32, b_double):
    """x87：`fld dword[a] / fmul qword[b]` 的积（扩展精度）。"""
    return round_ext(Fraction(a_f32) * Fraction(b_double), 64)


def remake_volume(shares, rand):
    """复刻 `places/stock-market.ts:525` 的公式（**两次 f32 舍入**）：

    `u16(trunc(fround(shares × fround((rand%2000 + 1000) / 10000))))`
    """
    if shares <= 1000:
        return shares
    r = (rand % 2000) + 1000
    return int(f32(shares * f32(r / 10000.0)))


# ══════════════════════════════════════════════════════════════════════
#  位置无关的小汇编器（只为 qsort 桩 + 记录桩用）
# ══════════════════════════════════════════════════════════════════════
class Asm:
    def __init__(self):
        self.b = bytearray()
        self.lbl = {}
        self.fix = []

    def raw(self, *chunks):
        for c in chunks:
            self.b.extend(c)

    def mark(self, name):
        self.lbl[name] = len(self.b)

    def jmp(self, name):
        self.b.append(0xE9)
        at = len(self.b)
        self.b.extend(b"\x00\x00\x00\x00")
        self.fix.append((at, name))

    def jcc(self, cc, name):
        self.b.extend(bytes([0x0F, 0x80 | cc]))
        at = len(self.b)
        self.b.extend(b"\x00\x00\x00\x00")
        self.fix.append((at, name))

    def build(self):
        out = bytearray(self.b)
        for at, name in self.fix:
            out[at:at + 4] = struct.pack("<i", self.lbl[name] - (at + 4))
        return bytes(out)


def sort_stub():
    """等价 qsort：按**传入的比较器**升序做选择排序（位置无关）。

    每次比较都 `call` 传入的比较器（真 `0x42bed0`），保证钉子落在**真比较器**上。
    比较器 `cmp(a,b)`：`-1` ⇒ a 排在 b 前。「严格 < 才换」⇒ 平手保序。
    """
    a = Asm()
    a.raw(b"\x53\x56\x57\x55")                       # push ebx/esi/edi/ebp
    a.raw(b"\x83\xEC\x10")                           # sub esp,16
    a.raw(b"\x8B\x5C\x24\x24")                       # mov ebx,[esp+0x24]  base
    a.raw(b"\x8B\x74\x24\x28")                       # mov esi,[esp+0x28]  n
    a.raw(b"\x8B\x44\x24\x30")                       # mov eax,[esp+0x30]  cmp
    a.raw(b"\x89\x44\x24\x0C")                       # mov [esp+0xc],eax
    a.raw(b"\xC7\x04\x24\x00\x00\x00\x00")           # mov dword [esp],0
    a.mark("outer")
    a.raw(b"\x8B\x04\x24")                           # mov eax,[esp]
    a.raw(b"\x39\xF0")                               # cmp eax,esi
    a.jcc(0x8D, "done")                              # jge done
    a.raw(b"\x89\x44\x24\x04")                       # mov [esp+4],eax
    a.raw(b"\x40")                                   # inc eax
    a.raw(b"\x89\x44\x24\x08")                       # mov [esp+8],eax
    a.mark("inner")
    a.raw(b"\x8B\x44\x24\x08")                       # mov eax,[esp+8]
    a.raw(b"\x39\xF0")                               # cmp eax,esi
    a.jcc(0x8D, "after_inner")                       # jge after_inner
    a.raw(b"\x8D\x14\x83")                           # lea edx,[ebx+eax*4]
    a.raw(b"\x8B\x44\x24\x04")                       # mov eax,[esp+4]
    a.raw(b"\x8D\x0C\x83")                           # lea ecx,[ebx+eax*4]
    a.raw(b"\x51")                                   # push ecx  (arg2)
    a.raw(b"\x52")                                   # push edx  (arg1)
    a.raw(b"\xFF\x54\x24\x14")                       # call dword [esp+0x14]
    a.raw(b"\x83\xC4\x08")                           # add esp,8
    a.raw(b"\x85\xC0")                               # test eax,eax
    a.jcc(0x8D, "no_better")                         # jge no_better
    a.raw(b"\x8B\x44\x24\x08")                       # mov eax,[esp+8]
    a.raw(b"\x89\x44\x24\x04")                       # mov [esp+4],eax
    a.mark("no_better")
    a.raw(b"\xFF\x44\x24\x08")                       # inc dword [esp+8]
    a.jmp("inner")
    a.mark("after_inner")
    a.raw(b"\x8B\x04\x24")                           # mov eax,[esp]
    a.raw(b"\x8B\x4C\x24\x04")                       # mov ecx,[esp+4]
    a.raw(b"\x39\xC8")                               # cmp eax,ecx
    a.jcc(0x84, "next_i")                            # je next_i
    a.raw(b"\x8B\x14\x83")                           # mov edx,[ebx+eax*4]
    a.raw(b"\x8B\x2C\x8B")                           # mov ebp,[ebx+ecx*4]
    a.raw(b"\x89\x2C\x83")                           # mov [ebx+eax*4],ebp
    a.raw(b"\x89\x14\x8B")                           # mov [ebx+ecx*4],edx
    a.mark("next_i")
    a.raw(b"\xFF\x04\x24")                           # inc dword [esp]
    a.jmp("outer")
    a.mark("done")
    a.raw(b"\x83\xC4\x10")                           # add esp,16
    a.raw(b"\x5D\x5F\x5E\x5B\xC3")                   # pop ebp/edi/esi/ebx/ret
    return a.build()


def rec4_stub(slot):
    """记录四个 cdecl 实参 + 计数（保留 ebx/esi/edi）。"""
    return (b"\x53\x56\x57"
            + b"\xFF\x05" + struct.pack("<I", BUY_N)
            + b"\x8B\x44\x24\x10" + b"\xA3" + struct.pack("<I", slot)
            + b"\x8B\x44\x24\x14" + b"\xA3" + struct.pack("<I", slot + 4)
            + b"\x8B\x44\x24\x18" + b"\xA3" + struct.pack("<I", slot + 8)
            + b"\x8B\x44\x24\x1C" + b"\xA3" + struct.pack("<I", slot + 12)
            + b"\x5F\x5E\x5B\xC3")


def hist6(idx, hi6=20.0, lo=10.0):
    """ring=0 时 avg24 读 120..143、avg6 读 138..143 ⇒ 用 138..143 控制 avg6。"""
    return {(idx, d): (hi6 if d >= 138 else lo) for d in range(120, 144)}


def merge(*dicts):
    out = {}
    for d in dicts:
        out.update(d)
    return out


class F:
    def __init__(self):
        self.emu = Emu()
        # rand：序列桩
        self.emu.patch(PRNG, b"\x51"
                       + b"\x8B\x0D" + struct.pack("<I", RAND_PTR)
                       + b"\x8B\x01"
                       + b"\x83\x05" + struct.pack("<I", RAND_PTR) + b"\x04"
                       + b"\xFF\x05" + struct.pack("<I", RAND_N)
                       + b"\x59\xC3")
        # 休市：数据槽
        self.emu.patch(CLOSED, b"\xA1" + struct.pack("<I", CLOSED_SLOT) + b"\xC3")
        # 日期差：记录两个实参 + 数据槽
        self.emu.patch(DATE_DIFF,
                       b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", DATE_A1)
                       + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", DATE_A2)
                       + b"\xFF\x05" + struct.pack("<I", DATE_N)
                       + b"\xA1" + struct.pack("<I", DIFF_SLOT)
                       + b"\xC3")
        # 漲停：`mov eax,[esp+4] / mov eax,[eax*4+tbl] / inc n / ret`
        self.emu.patch(LIMITUP, b"\x8B\x44\x24\x04" + b"\x8B\x04\x85"
                       + struct.pack("<I", LU_TAB)
                       + b"\xFF\x05" + struct.pack("<I", LU_N) + b"\xC3")
        # 真·买入：只记录
        self.emu.patch(BUY_EXEC, rec4_stub(BUY_ARGS))
        # 表现层：重绘/取名/格式化直接 ret；弹框计数
        for va in (REDRAW, NAME_FMT, SPRINTF):
            self.emu.patch(va, b"\xC3")
        self.emu.patch(MSGBOX, b"\xFF\x05" + struct.pack("<I", TAIL_N) + b"\xC3")
        # ★ qsort：等价选择排序（真比较器 0x42bed0）
        self.emu.patch(QSORT, sort_stub())

    # ── 自带的调用驱动 ────────────────────────────────────────────────
    # ⚠️ 为什么不用 `Emu.call()`：它在每次调用里都 `hook_add` 却**从不移除**，
    #    于是 `self._hook` 会跨用例累积；每个钩子都自增同一个 `insn_count`，
    #    而 `insn_count > MAX_INSN(400000)` 会 `emu_stop()` ⇒ **第 N 次调用时
    #    实际可执行的指令数被压到 400000/N**。实测：本文件到 `[B14]` 附近
    #    （约 90 次调用）时，`0x42bf03` 在 qsort 前后被腰斩 —— 表现为
    #    「记录数组在 qsort 后突然全 0 / 抽签一次 rand 都不摇」，
    #    极易误读成被测函数的 bug。这里自己驱动，**每次只挂一个钩子并摘掉**。
    def _run(self, func_va, args=(), setup=None, stop=None):
        e = self.emu
        e.reset()
        if setup is not None:
            setup(e)
        mu = e.mu
        sp = STACK_TOP
        for a in reversed(args):
            sp -= 4
            mu.mem_write(sp, struct.pack("<I", a & 0xFFFFFFFF))
        sp -= 4
        mu.mem_write(sp, struct.pack("<I", RET_SENTINEL))
        before = sp
        state = {"n": 0, "scoring_esp": None}

        def hook(mu2, address, size, user):
            state["n"] += 1
            if address == STOP_SCORING:
                state["scoring_esp"] = mu2.reg_read(UC_X86_REG_ESP)
                if stop == STOP_SCORING:
                    mu2.emu_stop()
            if state["n"] > 400000:
                mu2.emu_stop()

        h = mu.hook_add(UC_HOOK_CODE, hook)
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_EBP, sp)
        try:
            mu.emu_start(func_va, RET_SENTINEL, count=400000)
        finally:
            mu.hook_del(h)
        eax = mu.reg_read(UC_X86_REG_EAX)
        esp_after = mu.reg_read(UC_X86_REG_ESP)
        return {"eax": eax, "esp_delta": esp_after - before,
                "scoring_esp": state["scoring_esp"], "insns": state["n"]}

    # ── [A] 驱动 ─────────────────────────────────────────────────────
    def volume(self, shares, rolls=()):
        def setup(e):
            e.write32(RAND_PTR, RAND_SEQ)
            e.write32(RAND_N, 0)
            for i, v in enumerate(rolls):
                e.write(RAND_SEQ + i * 4, struct.pack("<I", v & 0xFFFFFFFF))
            for i in range(12):
                b = STOCKS + i * STOCK_STRIDE
                e.write16(b + S_SHARES, shares.get(i, 0) & 0xFFFF)
                e.write16(b + S_F10, SENTINEL)
                e.write(b + S_BASE, struct.pack("<f", 11.0))
                e.write(b + S_PRICE, struct.pack("<f", 22.0))

        r = self._run(VOLUME, [], setup=setup)
        return {
            "f10": [self.emu.read16(STOCKS + i * STOCK_STRIDE + S_F10) for i in range(12)],
            "shares": [self.emu.read16(STOCKS + i * STOCK_STRIDE + S_SHARES) for i in range(12)],
            "base": [struct.unpack("<f", self.emu.read(STOCKS + i * STOCK_STRIDE + S_BASE, 4))[0]
                     for i in range(12)],
            "price": [struct.unpack("<f", self.emu.read(STOCKS + i * STOCK_STRIDE + S_PRICE, 4))[0]
                      for i in range(12)],
            "rolls": self.emu.readu32(RAND_N),
            "esp_delta": r["esp_delta"],
        }

    # ── [B] 驱动 ─────────────────────────────────────────────────────
    def buy(self, *, player=0, ratio=100, cash=0, bank=1000000, due=0, diff=0x20,
            closed=0, rolls=(), stocks=None, companies=None, holdings=None,
            limitup=None, ring=0, total_months=0, pi=1, history=None,
            today=0x07E5060F, stop=None):
        stocks = stocks or {}
        companies = companies or {}
        holdings = holdings or {}
        history = history or {}
        limitup = limitup or {}

        def rec(i):
            d = {"company": 0, "pause": 1, "shares": 0, "f10": 0, "base": 10.0,
                 "open": 10.0, "price": 10.0, "vol": 1.0, "mom": 0.0}
            d.update(stocks.get(i, {}))
            return d

        def setup(e):
            e.write32(PRICE_INDEX, pi)
            e.write32(TOTAL_MONTHS, total_months)
            e.write32(RING, ring)
            e.write32(COMM_PTR, COMM)
            e.write32(TODAY, today)
            e.write32(CLOSED_SLOT, closed)
            e.write32(DIFF_SLOT, diff)
            e.write32(RAND_PTR, RAND_SEQ)
            e.write32(RAND_N, 0)
            e.write32(DATE_N, 0)
            e.write32(LU_N, 0)
            e.write32(BUY_N, 0)
            e.write32(TAIL_N, 0)
            e.write32(DATE_A1, 0)
            e.write32(DATE_A2, 0)
            for k in range(4):
                e.write32(BUY_ARGS + k * 4, 0)
            for i, v in enumerate(rolls):
                e.write(RAND_SEQ + i * 4, struct.pack("<I", v & 0xFFFFFFFF))
            for i in range(12):
                e.write32(LU_TAB + i * 4, limitup.get(i, 0))
            e.write(COMM, bytes(8 * 0x34))           # 企业表先整段清零（SCRATCH 跨调用保持）
            for i in range(12):
                d = rec(i)
                b = STOCKS + i * STOCK_STRIDE
                e.write16(b + S_COMPANY, d["company"] & 0xFFFF)
                e.write8(b + S_PAUSE, d["pause"] & 0xFF)
                e.write8(b + S_NEWS, 0)
                e.write16(b + S_SHARES, d["shares"] & 0xFFFF)
                e.write16(b + S_F10, d["f10"] & 0xFFFF)
                e.write(b + S_BASE, struct.pack("<f", d["base"]))
                e.write(b + S_OPEN, struct.pack("<f", d["open"]))
                e.write(b + S_PRICE, struct.pack("<f", d["price"]))
                e.write(b + S_VOL, struct.pack("<f", d["vol"]))
                e.write(b + S_MOM, struct.pack("<f", d["mom"]))
                e.write(b + S_RAND, struct.pack("<f", 0.0))
            for (idx, day), v in history.items():
                e.write(HISTORY + (idx * 144 + day) * 4, struct.pack("<f", v))
            for idx, c in companies.items():
                cb = COMM + idx * 0x34
                e.write8(cb + 0x18, c.get("chair", 0) & 0xFF)
                e.write8(cb + 0x19, c.get("stock", idx - 1) & 0xFF)
                e.write32(cb + 0x24, c.get("asset", 0))
                e.write32(cb + 0x28, c.get("funds", 0))
                e.write32(cb + 0x2C, c.get("profit", 0))
                e.write32(cb + 0x30, c.get("remaining", 0))
            for (p, s), (amount, cost) in holdings.items():
                e.write32(HOLD + p * HOLD_STRIDE + s * 8, amount)
                e.write32(HOLD + p * HOLD_STRIDE + s * 8 + 4, cost)
            pb = PLAYER + player * PLAYER_STRIDE
            e.write8(pb + P_RATIO, ratio & 0xFF)
            e.write32(pb + P_CASH, cash)
            e.write32(pb + P_BANK, bank)
            e.write32(pb + P_DUE, due)

        r = self._run(BUY, [player], setup=setup, stop=stop)

        out = {
            "reached": r["scoring_esp"] is not None,
            "records": [], "scores": [], "idxs": [],
            "rolls": self.emu.readu32(RAND_N),
            "lu_n": self.emu.readu32(LU_N),
            "date_n": self.emu.readu32(DATE_N),
            "date_a1": s32(self.emu.readu32(DATE_A1)),
            "date_a2": s32(self.emu.readu32(DATE_A2)),
            "buy_n": self.emu.readu32(BUY_N),
            "buy": [self.emu.readu32(BUY_ARGS + k * 4) for k in range(4)],
            "tail_n": self.emu.readu32(TAIL_N),
            "esp_delta": r["esp_delta"],
            "insns": r["insns"],
        }
        if out["reached"]:
            esp = r["scoring_esp"]
            out["records"] = [self.emu.readu32(esp + 0x80 + i * 4) for i in range(12)]
            out["scores"] = [v & 0xFFFF for v in out["records"]]
            out["idxs"] = [(v >> 16) & 0xFFFF for v in out["records"]]
        return out

    def score0(self, **kw):
        """跑一次并只取「下标 0 的分」（停址 = 打分循环结束）。"""
        r = self.buy(stop=STOP_SCORING, **kw)
        return r["scores"][0] if r["reached"] else None


# 常用股票输入
def nocomp(**kw):
    d = {"company": 0, "pause": 0, "f10": 1000, "base": 10.0, "price": 4.0, "mom": 0.0}
    d.update(kw)
    return d


def comp(idx=1, **kw):
    d = {"company": idx, "pause": 0, "f10": 1000, "base": 10.0, "price": 30.0,
         "shares": 1000, "mom": 0.0}
    d.update(kw)
    return d


def main():
    print("差分测试 · 股市两支（[A] 0x42915a / [B] 0x42bf03）\n")
    f = F()

    # ══════════════════════════════════════════════════════════════════
    print("[A] 0x42915a 每日重算可成交量 —— 12 支 × `+0x08 → +0x0a`")
    print("    公式：f10 = shares ≤ 1000 ? shares : trunc(shares × (1000 + rand%2000) / 10000)")

    s = f.volume({})
    case("A1 全部流通股为 0 ⇒ f10 全 0", set(s["f10"]), {0})
    case("A1 ★ 一次 rand 都不掷", s["rolls"], 0)

    s = f.volume({0: 1000}, rolls=[7])
    case("A2 流通股 == 1000（边界）⇒ 原样照抄", s["f10"][0], 1000)
    case("A2 ★ 边界不掷 rand（`jbe` 含等于）", s["rolls"], 0)

    s = f.volume({0: 1001}, rolls=[0])
    case("A3 流通股 1001（边界外）⇒ 走随机支", s["f10"][0], 100)
    case("A3 ★ 恰好掷一次 rand", s["rolls"], 1)
    case("A3 ★ 源字段 +0x08 不被改", s["shares"][0], 1001)

    s = f.volume({0: 1001}, rolls=[1234])
    case("A4 向零取整而非四舍五入：1001×2234/10000 = 223.6 → 223", s["f10"][0], 223)

    s2 = f.volume({0: 1001}, rolls=[2000])
    case("A5 rand=2000 ⇒ 余数 0（`idiv 2000`）⇒ 同 rand=0", (s2["f10"][0], s2["rolls"]), (100, 1))

    s = f.volume({0: 1001}, rolls=[1999])
    case("A6 rand=1999 ⇒ factor 2999；1001×2999/10000 = 300.19 → 300", s["f10"][0], 300)

    s = f.volume({0: 65535}, rolls=[1999])
    case("A7 ★ u16 上限：65535×2999/10000 = 19653.9 → 19653（< 65536，不回绕）",
         s["f10"][0], 19653)
    case("A7 ★ 存储宽度是 word（结果仍落在 u16 内）", s["f10"][0] < 65536, True)

    s = f.volume({0: 2000}, rolls=[0xFFFFFFFF])
    case("A8 ★ `sar edx,0x1f / idiv` 是**有符号**：rand=−1 ⇒ 余数 −1 ⇒ factor 999",
         s["f10"][0], 199)

    s = f.volume({0: 1001, 5: 2000, 11: 9999}, rolls=[0, 2000, 1999])
    case("A9 ★ 循环从记录 0 起：下标 0 被处理", s["f10"][0], 100)
    case("A9 ★ 循环到记录 11：下标 11 被处理", s["f10"][11], 2998)
    case("A9 下标 5（中间记录）也被处理", s["f10"][5], 200)
    case("A9 ★ 只有 >1000 的三支掷 rand ⇒ 恰好 3 次", s["rolls"], 3)
    case("A9 未越 1000 的支照抄（下标 1 ⇒ 0）", s["f10"][1], 0)

    s = f.volume({i: 3000 for i in range(12)}, rolls=[100] * 12)
    case("A10 12 支全 >1000 ⇒ 12 次 rand", s["rolls"], 12)
    case("A10 ★ 每支独立按自己的 rand 算（同一 rand ⇒ 同结果）",
         set(s["f10"]), {int(3000 * 1100 / 10000)})

    s = f.volume({0: 1001}, rolls=[0])
    case("A11 只写 +0x0a，参考价/现价不动", (s["base"][0], s["price"][0]), (11.0, 22.0))
    case("A11 cdecl（无参，调用方清栈：esp_delta = +4）", s["esp_delta"], 4)

    print("\n     [A12] ★★ DISCREPANCY #3：复刻多做的**两次 f32 舍入**（+0x0a 少 1）")
    # 原版：`fdiv dword [10000.0f]` 的商**不落内存**（没有 `fstp dword`），
    #   紧接着 `fmulp` 直接用 FPU 精度的商 ⇒ 复刻的 `Math.fround(r/10000)` 是**多出来的**一次舍入。
    # 下面三格都满足「扩展精度模型 == double 模型 == 预言机」⇒ 与仿真器精度无关，是**硬差**。
    s = f.volume({0: 3000}, rolls=[370])
    case("A12 预言机：3000 × (1000+370%2000) / 10000 = 411", s["f10"][0], 411)
    case("A12 附：复刻公式同一格给 410（少 1）", remake_volume(3000, 370), 410)
    s = f.volume({0: 3000}, rolls=[510])
    case("A13 预言机：3000 × 1510 / 10000 = 453", s["f10"][0], 453)
    case("A13 附：复刻公式同一格给 452", remake_volume(3000, 510), 452)
    s = f.volume({0: 4000}, rolls=[255])
    case("A14 预言机：4000 × 1255 / 10000 = 502", s["f10"][0], 502)
    case("A14 附：复刻公式同一格给 501", remake_volume(4000, 255), 501)
    # 对照：这些格两边一致（复刻在小盘股上仍对）
    case("A14 对照：3000 × 1100 / 10000 = 330，两边一致",
         (f.volume({0: 3000}, rolls=[100])["f10"][0], remake_volume(3000, 100)), (330, 330))

    # ══════════════════════════════════════════════════════════════════
    print("\n[B] 0x42bf03 电脑买股这一拍")

    ready = dict(stocks={0: nocomp(price=4.0, mom=3.0, f10=50000)},
                 history=hist6(0), rolls=[1, 12])

    print("\n  [B0] 入口闸 `rand()%3`（0x42bf14）")
    r = f.buy(**ready)
    case("B0-1 rand()%3 = 1 ⇒ 立刻返回（不进打分）", r["reached"], False)
    case("B0-1 ★ 只掷了入口那一次 rand", r["rolls"], 1)
    case("B0-1 没有下单", r["buy_n"], 0)
    r = f.buy(**{**ready, "rolls": [2, 12]})
    case("B0-2 rand=2 ⇒ 同样返回", (r["reached"], r["rolls"], r["buy_n"]), (False, 1, 0))
    r = f.buy(**{**ready, "rolls": [3, 12]})
    case("B0-3 ★ rand=3 ⇒ 3%3=0 通过（是取模不是位与）",
         (r["reached"], r["buy_n"]), (True, 1))
    r = f.buy(**{**ready, "rolls": [6, 12]})
    case("B0-4 rand=6 ⇒ 同样通过", (r["reached"], r["buy_n"]), (True, 1))
    case("B0-5 cdecl（esp_delta = +4）", r["esp_delta"], 4)

    print("\n  [B1] 闸1 stockRatio(+0x1a)（0x42bf30）")
    r = f.buy(ratio=0, stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0),
              rolls=[0, 12])
    case("B1-1 ratio == 0 ⇒ 返回", (r["reached"], r["rolls"]), (False, 1))
    r = f.buy(ratio=1, stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0),
              rolls=[0, 12])
    case("B1-2 ratio == 1 ⇒ 通过（闸是 ==0）", r["reached"], True)

    print("\n  [B2] 闸2 休市 0x428d01 == 1（0x42bf3d）")
    r = f.buy(closed=1, stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0),
              rolls=[0, 12])
    case("B2-1 返回 1 ⇒ 返回", (r["reached"], r["rolls"]), (False, 1))
    r = f.buy(closed=2, stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0),
              rolls=[0, 12])
    case("B2-2 ★ 返回 2 ⇒ **不**返回（判据是 `cmp eax,1`）", r["reached"], True)

    print("\n  [B3] 闸3 還款到期日（0x42bf4b..0x42bf68）")
    r = f.buy(due=0, stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0),
              rolls=[0, 12])
    case("B3-1 到期日 == 0 ⇒ 不调查询函数", (r["date_n"], r["reached"]), (0, True))
    r = f.buy(due=0x07E50101, diff=14, stocks={0: nocomp(price=4.0, mom=3.0)},
              history=hist6(0), rolls=[0, 12])
    case("B3-2 到期日 ≠ 0 且差 14 < 15 ⇒ 返回", (r["reached"], r["date_n"]), (False, 1))
    case("B3-2 ★ 实参序 = (今天, 到期日)", (r["date_a1"], r["date_a2"]),
         (0x07E5060F, 0x07E50101))
    r = f.buy(due=0x07E50101, diff=15, stocks={0: nocomp(price=4.0, mom=3.0)},
              history=hist6(0), rolls=[0, 12])
    case("B3-3 差 15（边界）⇒ 通过（`jl` 严格小于）", r["reached"], True)
    r = f.buy(due=0x07E50101, diff=-3, stocks={0: nocomp(price=4.0, mom=3.0)},
              history=hist6(0), rolls=[0, 12])
    case("B3-4 差 −3（有符号）⇒ 返回", r["reached"], False)

    print("\n  [B4] 预算公式与两道夹（0x42bf94..0x42c067）")
    r = f.buy(ratio=1, bank=0, cash=0, holdings={(0, 0): (10, 1)},
              stocks={0: nocomp(price=1.0, f10=100)}, rolls=[0, 12])
    case("B4-1 市值 10 ≥ target 0 ⇒ 返回（打分都没进）", r["reached"], False)
    r = f.buy(ratio=100, cash=1000000, bank=40000, holdings={},
              stocks={0: nocomp(price=1.0, f10=65535, mom=3.0)},
              history=hist6(0), rolls=[0, 12])
    case("B4-2 ★ 可投夹到**存款**：40000 / 价 1 ⇒ 40000 股（不夹会是 1040000）",
         r["buy"], [0, 0, 40000, 1])
    r = f.buy(ratio=1, cash=0, bank=40000,
              holdings={(0, 1): (1, 1)},
              stocks={0: nocomp(price=1.0, f10=100000, mom=3.0),
                      1: {"pause": 1, "price": 2.5}},
              history=hist6(0), rolls=[0, 12])
    case("B4-3 ★ 市值 = trunc(1 × 2.5) = 2（若取整成 3 则股数会少 1）",
         r["buy"], [0, 0, 398, 1])
    r = f.buy(ratio=3, cash=0, bank=40000, holdings={(0, 1): (1000, 1)},
              stocks={0: nocomp(price=400.0, base=1000.0, f10=100000, mom=3.0),
                      1: {"pause": 1, "price": 1.0}},
              history=hist6(0), rolls=[0, 12])
    case("B4-4 股数 = 0 ⇒ 不下单", r["buy_n"], 0)
    case("B4-4 ★ 但抽签已摇过一次（rand 总次数 = 入口 1 + 抽签 1）", r["rolls"], 2)

    print("\n  [B5] 打分前置三闸（0x42c5a6 / 0x42c5b0 / 0x42c5bd）")
    r = f.buy(stocks={0: {"pause": 1, "f10": 5, "mom": 3.0}}, rolls=[0, 12],
              stop=STOP_SCORING)
    case("B5-1 停牌 ⇒ 0 分", r["scores"][0], 0)
    case("B5-1 ★ 停牌在漲停判定**之前** ⇒ 一次 0x4295ea 都不调", r["lu_n"], 0)
    r = f.buy(stocks={0: nocomp(f10=5, mom=3.0)}, rolls=[0, 12], stop=STOP_SCORING)
    case("B5-2 可成交量 +0x0a == 0 ⇒ 0 分", r["scores"][0], 0)
    case("B5-2 该支的漲停判定被调过一次", r["lu_n"], 1)
    r = f.buy(stocks={0: nocomp(f10=5, mom=3.0)}, limitup={0: 1}, rolls=[0, 12],
              stop=STOP_SCORING)
    case("B5-3 漲停（0x4295ea 返回 1）⇒ 0 分", r["scores"][0], 0)
    r = f.buy(stocks={0: nocomp(price=4.0, mom=3.0, f10=5), 7: nocomp(price=4.0, mom=3.0, f10=5)},
              history=merge(hist6(0), hist6(7)), rolls=[0, 12], stop=STOP_SCORING)
    case("B5-4 记录 = (下标<<16) | 分（下标 0 ⇒ 0x0006）", r["records"][0], 6)
    case("B5-5 ★ 下标基是 0 基且写进**高字**（下标 7 ⇒ 0x00070006）",
         r["records"][7], (7 << 16) | 6)

    print("\n  [B6] 无企业支：存款门槛 30000×pi（0x42c352..0x42c379）")
    h6 = hist6(0)
    case("B6-1 存款 == 30000 ⇒ 0 分（`jge` 含等于）",
         f.score0(bank=30000, stocks={0: nocomp(price=4.0, mom=3.0, f10=5)}, history=h6,
                  rolls=[0, 12]), 0)
    case("B6-2 存款 == 30001 ⇒ 打分生效（+2+4=6）",
         f.score0(bank=30001, stocks={0: nocomp(price=4.0, mom=3.0, f10=5)}, history=h6,
                  rolls=[0, 12]), 6)
    case("B6-3 ★ 门槛乘物價指數：pi=2、存款 30001 < 60000 ⇒ 0 分",
         f.score0(bank=30001, pi=2, stocks={0: nocomp(price=4.0, mom=3.0, f10=5)},
                  history=h6, rolls=[0, 12]), 0)
    case("B6-4 pi=2、存款 60001 > 60000 ⇒ 打分生效",
         f.score0(bank=60001, pi=2, stocks={0: nocomp(price=4.0, mom=3.0, f10=5)},
                  history=h6, rolls=[0, 12]), 6)

    print("\n  [B7] 无企业支的三个加分（0x42c4a2 / 0x42c4f7 / 0x42c52d）")
    def nc(base=10.0, price=4.0, mom=0.0, h=None):
        return f.score0(stocks={0: nocomp(base=base, price=price, mom=mom, f10=5)},
                        history=h or hist6(0), rolls=[0, 12])
    case("B7-1 现价<2.5×参考 且 动能>2 且 avg6>avg24 ⇒ +2", nc(price=24.0, mom=3.0), 2)
    case("B7-2 ★ 现价 == 2.5×参考（边界）⇒ 不加（`jae` 跳过）", nc(price=25.0, mom=3.0), 0)
    case("B7-3 现价<0.6×参考 且 avg6>avg24 ⇒ +4", nc(price=5.0, mom=0.0), 4)
    case("B7-4 ★ 现价 == 0.6×参考（边界）⇒ 不加", nc(price=6.0, mom=0.0), 0)
    case("B7-5 avg6 < avg24×0.5 ⇒ +2（与现价无关）", nc(price=30.0, mom=0.0, h=hist6(0, hi6=5.0, lo=20.0)), 2)
    case("B7-6 三条可叠加：+2（动能）+4（超跌）= 6", nc(price=5.0, mom=3.0), 6)

    print("\n  [B8] ★★ 无企业 +2 的第二个判据是 **momentum(+0x1c)**，不是 volatility(+0x18)")
    case("B8-1 volatility=1.0（≤2）但 momentum=3.0 ⇒ **+2 成立**",
         f.score0(stocks={0: nocomp(price=24.0, mom=3.0, vol=1.0, f10=5)}, history=hist6(0),
                  rolls=[0, 12]), 2)
    case("B8-2 volatility=3.0（>2）但 momentum=0 ⇒ **+2 不成立**",
         f.score0(stocks={0: nocomp(price=24.0, mom=0.0, vol=3.0, f10=5)}, history=hist6(0),
                  rolls=[0, 12]), 0)
    case("B8-3 ★ 边界：momentum == 2.0 ⇒ 不加（`cmp dword / jle`）",
         f.score0(stocks={0: nocomp(price=24.0, mom=2.0, vol=3.0, f10=5)}, history=hist6(0),
                  rolls=[0, 12]), 0)
    case("B8-4 ★ 位型 0x40000001（2.0 的次一颗）⇒ 加 2",
         f.score0(stocks={0: nocomp(price=24.0, mom=f32frombits(0x40000001), f10=5)},
                  history=hist6(0), rolls=[0, 12]), 2)
    case("B8-5 −0.0 的位型是 0x80000000（`cmp dword` 有符号 ⇒ 负数）⇒ 不加",
         f.score0(stocks={0: nocomp(price=24.0, mom=f32frombits(0x80000000), f10=5)},
                  history=hist6(0), rolls=[0, 12]), 0)

    print("\n  [B9] 有企业支：存款门槛 20000×pi（0x42c5d8..0x42c5f8）")
    def ccase(profit=10000):
        return dict(stocks={0: comp(price=30.0, f10=5)},
                    companies={1: {"asset": 100000, "funds": 0, "profit": profit,
                                   "remaining": 0, "chair": 0}},
                    rolls=[0, 12], total_months=1)
    case("B9-1 存款 == 20000 ⇒ 0 分",
         f.score0(bank=20000, **ccase()), 0)
    case("B9-2 存款 == 20001 ⇒ 打分生效（月均盈余 10000 ⇒ +3）",
         f.score0(bank=20001, **ccase()), 3)
    case("B9-3 ★ 门槛乘物價：pi=3、存款 20001 < 60000 ⇒ 0 分",
         f.score0(bank=20001, pi=3, **ccase()), 0)

    print("\n  [B10] 有企业支：月均盈余三档（0x42c612..0x42c19f）")
    def monthly(profit, tm, pi=1):
        return f.score0(stocks={0: comp(price=30.0, f10=5)},
                        companies={1: {"asset": 100000, "funds": 0, "profit": profit,
                                       "remaining": 0, "chair": 0}},
                        rolls=[0, 12], total_months=tm, pi=pi)
    case("B10-1 月均 0 ⇒ 0 分", monthly(0, 1), 0)
    case("B10-2 月均 −1 ⇒ 0 分（`0 < monthly` 门槛）", monthly(-1, 1), 0)
    case("B10-3 月均 4999 ⇒ +1（上界开）", monthly(4999, 1), 1)
    case("B10-4 ★ 月均 5000 ⇒ +2（`jbe` 跳过 +1）", monthly(5000, 1), 2)
    case("B10-5 月均 9999 ⇒ +2", monthly(9999, 1), 2)
    case("B10-6 ★ 月均 10000 ⇒ +3", monthly(10000, 1), 3)
    case("B10-7 ★ 總月數 = 0 ⇒ 直接用累計盈余（不除）", monthly(6000, 0), 2)
    case("B10-8 ★ 總月數 = 2、盈余 10000 ⇒ 月均 5000（idiv 截断）⇒ +2", monthly(10000, 2), 2)
    case("B10-9 ★ pi=2 把门槛抬一倍：月均 10000 ⇒ +2（pi=1 时是 +3）",
         monthly(10000, 1, pi=2), 2)
    case("B10-10 pi=2、月均 20000 ⇒ +3（正好到 10000×pi）", monthly(20000, 1, pi=2), 3)

    print("\n  [B11] 有企业支：資產額 → A = trunc(+0x24 / 10000)（0x42c07f..0x42c095）")
    def assetcase(asset, price):
        return f.score0(stocks={0: comp(price=price, f10=5)},
                        companies={1: {"asset": asset, "funds": 0, "profit": 0,
                                       "remaining": 0, "chair": 0}},
                        rolls=[0, 12])
    case("B11-1 现价 8、A=10 ⇒ <0.85×10 ⇒ +3；≥0.7×10 ⇒ 不加 5", assetcase(100000, 8.0), 3)
    case("B11-2 现价 6、A=10 ⇒ <0.7×10 ⇒ +3+5 = 8", assetcase(100000, 6.0), 8)
    case("B11-3 现价 9、A=10 ⇒ 两档都不中 ⇒ 0", assetcase(100000, 9.0), 0)
    case("B11-4 ★ A 是**截断**：資產 99999 ⇒ A=9 ⇒ 现价 8 ≥ 0.85×9=7.65 ⇒ 0",
         assetcase(99999, 8.0), 0)
    case("B11-5 同資產 99999、现价 7 < 7.65 ⇒ +3", assetcase(99999, 7.0), 3)

    print("\n  [B12] 有企业支：「便宜到能进场」+1（0x42c1a7..0x42c201）")
    def cheap(price, funds=1, holding=0, shares=1000, asset=100000):
        return f.score0(stocks={0: comp(price=price, f10=5, shares=shares)},
                        companies={1: {"asset": asset, "funds": funds, "profit": 0,
                                       "remaining": 0, "chair": 0}},
                        holdings={(0, 0): (holding, 0)}, rolls=[0, 12])
    case("B12-1 累積盈余>0、持股 0、现价 11 ≤ A×1.2 ⇒ +1", cheap(11.0), 1)
    case("B12-2 累積盈余 == 0 ⇒ 不进该支 ⇒ 0 分", cheap(11.0, funds=0), 0)
    case("B12-3 ★ 持股 == 5000（边界）⇒ 不进 ⇒ 0 分", cheap(11.0, holding=5000), 0)
    case("B12-4 持股 4999 ⇒ +1", cheap(11.0, holding=4999), 1)
    case("B12-5 现价 11.9（明确在 A×1.2 之下）⇒ +1", cheap(11.9), 1)
    case("B12-6 现价 12.1（明确在 A×1.2 之上）⇒ 不加 ⇒ 0", cheap(12.1), 0)
    # ★ 恰好 现价 == A×1.2 == 12 那一格 **无法判定**，本文件不写断言：
    #   真机 x87（FPCW=0x027F ⇒ PC=扩展）算 10.0f × 1.2(double) = 11.9999999999999995559… < 12
    #   ⇒ 原版应**不加**；而本仿真器在这条边界上给 +1（= JS double 的 12.0）。
    #   ⇒ Unicorn 的 x87 乘法没有体现 80 位扩展精度，**该边界不能拿它当预言机**。
    #   已在报告里登记为「仿真器保真限制」（与 verification.md 的工具边界同族）。
    case("B12-7 附：扩展精度模型确实算得 11.999… < 12（真机应判「不加」）",
         Fraction(12) <= ext_mul(f32(10.0), 1.2), False)

    print("\n  [B13] 有企业支：董事長两项（0x42c218..0x42c2d6）")
    def chair(chi, hold_of_chair, shares=1000, remaining=2000, f10=500, holding=0):
        hs = {(0, 0): (holding, 0)}
        if chi >= 1:
            hs[(chi - 1, 0)] = (hold_of_chair, 0)
        return f.score0(stocks={0: comp(price=11.5, f10=f10, shares=shares)},
                        companies={1: {"asset": 100000, "funds": 1, "profit": 0,
                                       "remaining": remaining, "chair": chi}},
                        holdings=hs, rolls=[0, 12])
    case("B13-1 董事長 == 我+1 ⇒ 只跳过董事長那两项（便宜 +1 仍给）⇒ 1", chair(1, 100), 1)
    case("B13-2 无董事長（+0x18 == 0）⇒ 只留 +1（便宜）⇒ 1", chair(0, 0), 1)
    case("B13-3 流通 1000+持股 0+保留 2000 = 3000 > 董事長 100 ⇒ +1；500>100 ⇒ +2；再 +1 便宜 = 4",
         chair(2, 100), 4)
    case("B13-4 董事長持股 400：3000>400 ⇒ +1；500>400 ⇒ +2；+1 = 4", chair(2, 400), 4)
    case("B13-5 董事長持股 600：3000>600 ⇒ +1；500>600 否；+1 = 2", chair(2, 600), 2)
    case("B13-6 董事長持股 4000：两项都不成立 ⇒ 只剩 +1 = 1", chair(2, 4000), 1)
    case("B13-7 ★ 第二项用的是 **+0x0a 可成交量**：f10=300 ⇒ 2；f10=500 ⇒ 4",
         (chair(2, 400, f10=300), chair(2, 400, f10=500)), (2, 4))

    print("\n  [B14] 排名与抽签（0x42c63d..0x42c6c1）")
    two = dict(stocks={0: nocomp(price=4.0, mom=3.0, f10=50000),
                       2: nocomp(price=24.0, mom=3.0, f10=50000)},
               history=merge(hist6(0), hist6(2)))
    r = f.buy(**two, rolls=[0, 12], stop=STOP_SCORING)
    case("B14-1 分互不相同：下标 0 = 6 分、下标 2 = 2 分",
         (r["scores"][0], r["scores"][2]), (6, 2))
    r = f.buy(**two, rolls=[0, 12])
    case("B14-2 ★ 第 0 名：rand()%24 = 12 ≤ 12 ⇒ 选中最高分（下标 0）",
         r["buy"][:3], [0, 0, 50000])
    r = f.buy(**two, rolls=[0, 13, 11])
    case("B14-3 ★ 第 0 名被拒（13 > 12）⇒ 第 1 名门槛 11，rand=11 ≤ 11 ⇒ 选中下标 2",
         r["buy"][:3], [0, 2, 41666])
    r = f.buy(**two, rolls=[0, 13, 12])
    case("B14-4 ★ 第 1 名门槛正好是 11：rand=12 > 11 ⇒ 全落空 ⇒ 不下单",
         (r["buy_n"], r["rolls"]), (0, 3))
    three = dict(stocks={0: nocomp(price=4.0, mom=3.0, f10=50000),
                         2: nocomp(price=24.0, mom=3.0, f10=50000),
                         7: nocomp(price=5.0, mom=0.0, f10=50000)},
                 history=merge(hist6(0), hist6(2), hist6(7)))
    r = f.buy(**three, rolls=[0, 13, 13, 10])
    case("B14-5 ★ 第 2 名门槛 10：前三名 13/13/10 ⇒ 选中下标 2",
         r["buy"][:2], [0, 2])
    r = f.buy(**three, rolls=[0, 13, 10])
    case("B14-6 ★ 换 13/10：第 1 名门槛 11，rand=10 ≤ 11 ⇒ 选中 4 分那支（下标 7）",
         r["buy"][:2], [0, 7])

    print("\n  [B15] 0 分记录在抽签里**不摇**（0x42c684）")
    r = f.buy(stocks={5: nocomp(price=4.0, mom=3.0, f10=50000)}, history=hist6(5),
              rolls=[0, 13])
    case("B15-1 只有下标 5 非 0 分；它被拒后其余 0 分不摇 ⇒ rand 总次 = 2",
         (r["rolls"], r["buy_n"]), (2, 0))
    r = f.buy(stocks={0: nocomp(price=4.0, mom=3.0, f10=50000),
                      2: nocomp(price=24.0, mom=3.0, f10=50000)},
              history=merge(hist6(0), hist6(2)), rolls=[0, 13, 13])
    case("B15-2 两个非 0 分档各摇一次、都被拒 ⇒ 3 次", (r["rolls"], r["buy_n"]), (3, 0))

    print("\n  [B16] 下单：股数 = trunc(可投/现价)，上限 +0x0a；四参 = (玩家, 股票, 股数, 1)")
    r = f.buy(player=2, ratio=100, cash=0, bank=100000,
              stocks={7: nocomp(price=4.0, mom=3.0, f10=30000)},
              history=hist6(7), rolls=[0, 12])
    case("B16-1 玩家 2 / 股票 7 / 100000÷4 = 25000 / +0x0a=30000 ⇒ 25000",
         r["buy"], [2, 7, 25000, 1])
    case("B16-2 第四个实参恒为 1", r["buy"][3], 1)
    case("B16-3 走完表现层（弹框计数 1）", r["tail_n"], 1)
    r = f.buy(stocks={7: nocomp(price=4.0, mom=3.0, f10=999)}, history=hist6(7),
              rolls=[0, 12])
    case("B16-4 ★ 股数被 +0x0a 封顶（999 < 25000）", r["buy"][2], 999)
    r = f.buy(stocks={7: nocomp(price=4.0, mom=3.0, f10=25000)}, history=hist6(7),
              rolls=[0, 12])
    case("B16-5 ★ 恰好相等（f10 == 股数）⇒ 不封顶（取小值仍 25000）", r["buy"][2], 25000)
    r = f.buy(bank=100000, stocks={7: nocomp(price=3.0, mom=3.0, f10=50000)},
              history=hist6(7), rolls=[0, 12])
    case("B16-6 ★ 除法向零取整：100000/3 = 33333.3 → 33333", r["buy"][2], 33333)
    r = f.buy(bank=100000, stocks={11: nocomp(price=4.0, mom=3.0, f10=50000)},
              history=hist6(11), rolls=[0, 12])
    case("B16-7 ★ 下标 11（末支）也能被选中，且股数按它的现价算", r["buy"], [0, 11, 25000, 1])

    print("\n  [B17] 玩家步长 0x68（+0x1a/+0x1c/+0x20/+0x2c 各就各位）")
    r = f.buy(player=2, ratio=0, cash=999999, bank=999999,
              stocks={0: nocomp(price=4.0, mom=3.0)}, history=hist6(0), rolls=[0, 12])
    case("B17-1 玩家 2 的 ratio == 0 ⇒ 返回（读的是 arg1 那位）", r["reached"], False)
    r = f.buy(player=2, ratio=50, cash=0, bank=100000,
              stocks={0: nocomp(price=4.0, mom=3.0, f10=8000)},
              history=hist6(0), rolls=[0, 12])
    case("B17-2 玩家 2 的 ratio/bank 正确落位 ⇒ 下单", r["buy"], [2, 0, 8000, 1])

    print("\n  [B18] 持仓步长 0x60（只有目标玩家的格子参与市值）")
    both = dict(stocks={0: nocomp(price=2.0, mom=3.0, f10=60000),
                        1: {"pause": 1, "price": 1.0}},
                history=hist6(0), ratio=80, cash=0, bank=100000, rolls=[0, 12])
    r = f.buy(player=0, holdings={(1, 1): (100000, 1)}, **both)
    case("B18-1 ★ 玩家 1 的持仓不影响玩家 0：target 80000 ⇒ 40000 股",
         r["buy"], [0, 0, 40000, 1])
    r = f.buy(player=1, holdings={(1, 1): (100000, 1)}, **both)
    case("B18-2 换成玩家 1 ⇒ 市值 100000 参与预算（target 16 万 − 10 万 ⇒ 30000 股）",
         r["buy"], [1, 0, 30000, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
