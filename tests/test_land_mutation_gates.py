#!/usr/bin/env python3
"""
通道 2 差分测试 · **地块/設施改造三支（整支驱动原版机器码）**

| 组 | VA | 字节 | 语义 | 复刻对应 |
|---|---|---|---|---|
| `[A]` | `0x0040ab4a` | 305 | `mutate_land(ref, mode)` —— 拆一级 / 完全清除 / 夷平（地块 2000..4000、設施 4000..6000 一张函数两支） | `cards/monster.ts` 的 `mutateLand`/`mutateFacility`、`rules/land-mutation.ts` 的 `demolishLand` |
| `[B]` | `0x0040b110` | 273 | `upgrade(ref)` —— **就地加蓋一級**（地块写死上限、設施查 `0x474940`；等級 0 时**顺便定种类**） | `rules/tool-effects.ts:230` 的 `buildOneLevel`、`state/reduce.ts:4804` 的 `freeBuildFacilityById` |
| `[C]` | `0x004294d5` | 277 | `update_commercial_owner(player, stock)` —— 把该玩家从企业持股排名表摘下、按持股降序插回，**排名第一即老闆** | `places/commercial.ts:78` 的 `updateCommercialOwner`、`state/reduce.ts:3339` 的 `reownCommercial` |

## 调用点（字节级，`gen/rel32-calls.json` 的 callee→sites 口径）

```
0x0040ab4a  ← 9 处: 0x40dc19(mode?) 0x40f61b(mode 0) 0x41b71f(mode 0) 0x43234c(mode 0)
                    0x443a81(mode 2) 0x44944f(mode 1) 0x44a543(mode 2) 0x44aaaf(mode 1)
                    0x44adfe(mode 0)
0x0040b110  ← 8 处: 0x40f493 0x40f983 0x41aae8 0x41aafc 0x41ad7e 0x432059 0x4436ad 0x447345
                    （機器工人 / 魔法屋「就地加蓋房屋」/ 建設公司 / 新聞）
0x004294d5  ← 3 处: 0x42571e(公佈欄買股) 0x428e14(buy_stock 尾) 0x428eb7(sell_stock 尾)
```
★ `0x432085` / `0x4436b5` / `0x44736d` 都 `test …,0x80` —— 返回值的 **bit7（剛好升到 5 級）真的被消费**。

## [A] `0x0040ab4a(ref, mode)` 全文语义

```
changed = 0
if 0x7d0 < ref < 0xfa0:                        ; 地块：rec = [0x498e84] + (ref-0x7d0)*0x34
    mode 0:  if level == 0 → return 0
             level -= 1
             if type != 0:  level = 0; type = 0        ; ★ 连锁店直接铲平（owner 留着！）
             changed = 1
    mode 1:  owner = 0; level = 0; type = 0; dword[+0x30] = 0     ; ★ 无任何前置判据
             call 0x40a4e1(0);  changed = 1
    mode 2:  if level == 0 → return 0
             level = 0; type = 0                        ; ★ owner 留着
             changed = 1
    mode ≥3: return 0
if 0xfa0 < ref < 0x1770:                       ; 設施：rec = [0x498e88] + (ref-0xfa0)*0x38
    mode 0:  if level == 0 → return 0
             level -= 1
             if level == 0:  type = 0; call 0x40dffa()  ; ★ 拆到 0 级才放人
             changed = 1
    mode 1:  owner = 0; level = 0; type = 0; dword[+0x34] = 0
             call 0x40dffa();  call 0x40a4e1(0);  changed = 1
    mode 2:  if level == 0 → return 0
             level = 0; type = 0; call 0x40dffa()
             changed = 1
    mode ≥3: return edx（= 0）
return changed
```

**★ 精确写点（hexdiff 逐字节验，见 `[A]` 的 diff 断言）**

| 分支 | 被写的字节 | 不写的（易错） |
|---|---|---|
| 地块 mode 0 住宅 | `+0x1a` | `+0x18`/`+0x19`/`+0x30` |
| 地块 mode 0 连锁店 | `+0x18`、`+0x1a` | **`+0x19`（owner 保留）**、`+0x1a` 被写两次（`dec` 那次是死写） |
| 地块 mode 1 | `+0x18`、`+0x19`、`+0x1a`、`+0x30..+0x33`（**dword**） | —— |
| 地块 mode 2 | `+0x18`、`+0x1a` | `+0x19`、`+0x30` |
| 設施 mode 0（未归零） | `+0x1a` | `+0x18`/`+0x19`/`+0x34` |
| 設施 mode 0（拆到 0） | `+0x18`、`+0x1a` | **`+0x19`**、`+0x34` |
| 設施 mode 1 | `+0x18`、`+0x19`、`+0x1a`、**`+0x34..+0x37`** | **`+0x30..+0x33`（住宅才在 +0x30）** |
| 設施 mode 2 | `+0x18`、`+0x1a` | `+0x19`、`+0x34` |

★★ **「无前置判据 ⇒ 恒 changed」**：地块与設施的 mode 1 即使记录**全 0**也返回 **1**，
并照样调 `0x40a4e1`（`§三` 第 16 条的同一族，差分在此钉死）。
★★ **`0x40dffa` 的门控不对称**：**地块支一次都不调**，設施支三种 mode 里
「拆到 0 级 / mode 1 / mode 2（level≠0）」各调一次 —— 一刀切把**全场**被关押者置 `0x80`。

## [B] `0x0040b110(ref)` 全文语义

```
eax = 0
if 0x7d0 < ref < 0xfa0:                        ; 地块
    rec = [0x498e84] + (ref-0x7d0)*0x34
    if type == 0 && level < 5 : eax = 1        ; ★ 上限写死 5
    if type == 1 && level < 1 : eax = 1        ; ★ 连锁店上限写死 1
    if eax != 0:
        level += 1
        if level == 5: eax |= 0x80             ; ★ bit7 = 剛好到 5 級
if 0xfa0 < ref < 0x1770:                       ; 設施
    rec = [0x498e88] + (ref-0xfa0)*0x38
    if level == 0:                             ; 首建：種類在這一刻決定
        if (player[cur].whoPlays & 6) != 0:    ; 「電腦/託管」那一支
            if rec.owner == cur+1: rec.type = rand()%4 + 1     ; $rand 用一次
            else                 : rec.type = 0                 ; 替別人蓋 → 公園
        else:
            rec.type = 0x440aac(0) & 0xff      ; 真人走選單
        eax = 1;  level = 1                    ; ★ 不查上限表
    else:
        if level >= byte[rec.type + 0x474940] → return 0
        eax = 1;  level += 1
        if level == 5: eax = 0x81              ; ★ 这里**赋值** 0x81（不是 or）
return eax
```
★ 返回值的 **bit0 = 成了 / bit7 = 剛好到 5 級**；`type ∉ {0,1}` 的地块**一律不能加蓋**。
★ 全程**不看 owner、不扣钱、不放人**（`+0x19` 一个字节都不写）。

## [C] `0x004294d5(player, stock)` 全文语义

```
n = word[stock_table + stock*0x24 + 0x04]        ; 1 基企業序号（stock_table = 0x496980）
if n == 0: return 0                              ; ★ 该股票没有对应企業 ⇒ 一个字节都不写
com = [0x498e7c] + n*0x34                        ; 企業表 **1 基**、步长 0x34
for k = 0..3:                                    ; ① 摘下：把 player+1 从 4 槽排名表里删掉
    if com[0x1c+k] == player+1:
        memmove(&com[0x1c+k], &com[0x1c+k+1], 3-k);  com[0x1f] = 0;  break
mine = holdings[player*0x60 + stock*8]           ; = 该玩家在这支股票的持股数
if mine != 0:                                    ; ② 按持股降序插回
    insertAt = 0
    for k = 2 down to 0:
        s = com[0x1c+k]
        if s == 0: continue                      ; 空位跳过（继续往前）
        if holdings[(s-1)*0x60 + stock*8] < mine: com[0x1c+k+1] = s   ; ★ 严格 <
        else: insertAt = k+1; break
    com[0x1c+insertAt] = player+1
if com[0x18] != com[0x1c]:                       ; ③ 第一名即老闆
    com[0x18] = com[0x1c]; call 0x40a4e1(0); return 1
return 0
```
★ 笔数写在 `+0x18`，名次表在 `+0x1c..+0x1f`（各 1 字节、值 = 玩家下标+1）；**全程不掷 `rand`**。
★★ **只在「老闆易主」时返回 1** —— 名次表被改写但老闆没变时返回 **0**（且**不刷新**）。
★★ 算法**假设名次表连续无洞**：遇到洞就只会「跳过」，于是可能**覆盖**掉洞上方的项（差分钉住）。

## 打桩清单

| VA | 原用途 | 桩 | 理由 |
|---|---|---|---|
| `0x0040a4e1` | 地图实体数组重算 + 重绘（805 B） | `mov eax,[esp+4] / mov [ARG],eax / inc [CNT] / ret` | 首步就 `memmove([0x48bad0]+0xc, …)`，而该指针在裸镜像里是 **0** ⇒ 真跑必 `UC_ERR_WRITE_UNMAPPED`；且它是**复刻有意未实现**的表现层重算（gaps §7.46）。**实参与调用次数**已断言。 |
| `0x00456f2d` | CRT `rand()` | `mov eax,[VAL] / inc [CNT] / ret` | 被测对象是「**用不用、用几次、怎么取模**」，不是 PRNG 本体（PRNG 已由 `test_prng.py` 单独定案）。 |
| `0x00440aac` | 真人「选建筑种类」模态窗 | `mov eax,[VAL] / ret` | 无头环境没有那一屏（复刻侧记为缺 UI，Q-CO-1 同类）；本测试要钉的是「**真人支走这个调用、且值是它的 `al`**」。 |
| `0x00456de8` | CRT `memmove` | `pushad / mov edi,[esp+0x24] / mov esi,[esp+0x28] / mov ecx,[esp+0x2c] / rep movsb / popad / ret` | 真身的 `push es / movsd` 在本仿真器上跑不了（`docs/verification.md` 工具边界第 1 条）。等价语义逐字节验。 |

**真跑**：`0x0040dffa`（全场标记释放，`test_mutate_release.py` 已单独定案 7/7）——
`[A]` 要的正是「`mutate` 的哪个分支会调它」。

## 复刻裁决（file:line 相对 `rich4-remake/packages/core/src/`）

| # | 规则 | 原版真值（本测试钉死的） | 复刻 | 裁决 |
|---|---|---|---|---|
| A-1 | 地块 mode 0 住宅 | 只 `level−1`；`level==0` 则不动 | `cards/monster.ts:90`、`rules/land-mutation.ts:75` | **MATCH** |
| A-2 | 地块 mode 0 连锁店 | `level=0; type=0`，**owner 保留** | `cards/monster.ts:84`（`{...land}` 保留 owner） | **MATCH** |
| A-3 | 地块 mode 1 | owner/level/type ＋ **dword `+0x30`** 全清；**恒 changed** | `cards/monster.ts:110` | **MATCH** |
| A-4 | 地块 mode 2 | level/type 归 0，owner/flast 保留 | `cards/monster.ts:117` | **MATCH** |
| A-5 | ★★ **放人门控（住宅支）** | `0x40ab4a` 的**地块支三种 mode 一次都不调 `0x40dffa`**：字节级全 exe 只有 8 个调用点（`0x40ac33/4d/6c` 在本函数的**設施**支、`0x40ae0d/0x40ae58` 在**另一个函数** `0x40ac7b`（飛彈/颱風作用域），另 3 处在拆屋卡/新聞 18）；且 `0x40a4e1` 的调用闭包（5 个目标、传递 8 支）**够不到** `0x40dffa` | `cards/monster.ts:87,95,115,123` 让地块三种 mode 都可能 `releasesConfined:true`，`events/news-effects.ts:494,531,585` 据此**真放人**（颱風 / 地震 / 拆屋类）；`rules/blocking.ts:205` 的注释把 `0x40ac7b` 的调用点当成 `mutateLand` 的 | **DISCREPANCY** |
| A-6 | 設施放人门控 | 拆到 0 级 / mode 1 / mode 2（level≠0）各调一次 | `cards/monster.ts:219-247` | **MATCH** |
| A-7 | 設施 flast 在 `+0x34`（住宅 `+0x30`） | dword @`+0x34` | `loaders/map.ts:600` | **MATCH** |
| A-8 | `0x40a4e1`（地图数组重算） | mode 1 两表各调一次、实参 0 | 复刻未实现（`cards/monster.ts:105,213` 自认，gaps §7.46） | **DISCREPANCY（已登记）** |
| B-1 | 地块可蓋判据 | `type==0 && level<5` **或** `type==1 && level<1` | `rules/tool-effects.ts:230-234`（`buildOneLevel`，caller 传 `MAX_LAND_LEVEL=5`）**MATCH**；但魔法屋那条 `state/reduce.ts:2537` 写成 `isChain = land.type !== 0` ⇒ `type≥2` 时它**会蓋**、原版不蓋 | **DISCREPANCY（潜在：`type≥2` 不可达）** |
| B-2 | 設施首建「電腦」判据 | `(whoPlays & 6) != 0` | `state/reduce.ts:4857` 用 `(whoPlays & 0x03) !== 1` ⇒ **`whoPlays=5`（人类+托管）走错支**（原版按电脑给 公園/`rand()%4+1`；复刻走真人支、`chosenType=-1` ⇒ **建不成**） | **DISCREPANCY** |
| B-3 | 設施加蓋上限 | `level < byte[type + 0x474940]` | `rules/facility.ts:395`（表 `[1,5,5,1,5]`） | **MATCH** |
| B-4 | 返回值 **bit7**（剛好到 5 級） | `0x81`；`0x432085`/`0x4436b5`/`0x44736d` 都消费它 ⇒ `0x40b0cd`（MKF 0x20b ＋ 音效）＋ 台词 | `state/reduce.ts:4844-4886` 只回等级，bit7 丢弃 | **DISCREPANCY（表现层）** |
| B-5 | `rand` 消耗 | 电脑且 `owner==cur+1` 恰 **1** 次；其余分支 **0** 次 | `state/reduce.ts:4855` 同 | **MATCH** |
| B-6 | 真人支 | `0x440aac(0)` 模态选单 | 无那一屏（`chosenType=-1 ⇒ null`），自认 Q-CO-1 | **无法判定（UI 缺屏）** |
| C-1 | 该股票无对应企業 | `word[stock+4]==0` ⇒ 返回 0、零写 | `state/reduce.ts:3340` 在调用方早退 | **MATCH（层次不同）** |
| C-2 | 摘下＋按持股降序插回（严格 `<`） | 见上 | `places/commercial.ts:86-113` 逐行同 | **MATCH** |
| C-3 | 返回值 = 「**老闆易主**」而非「有改动」 | 名次变了但老闆没变 ⇒ **0** 且不刷新 | `places/commercial.ts:116-121` 同 | **MATCH** |
| C-4 | 名次表有洞 ⇒ 插入位可能**覆盖**上方项 | `[1,0,3,4]` ＋ 小持股 ⇒ `[1,0,3,2]` | `places/commercial.ts:99-112` 同 | **MATCH** |
| C-5 | 不掷 `rand` | 0 次 | 0 次 | **MATCH** |
| C-6 | `0x40a4e1` 刷新 | 老闆易主才调一次 | 复刻无（表现层） | **DISCREPANCY（已登记）** |

## ★ 可证伪检查（`--falsify`，一次只破一个字节）

| 组 | 破坏的字节 | 变红断言数 |
|---|---|---|
| `[A]` | `0x40ab76` 地块步长 `0x34 → 0x38` | **22 / 354** |
| `[A2]` | `0x40aba0` mode 0 的 `cmp [eax+0x18],0` 位移 `0x18 → 0x19`（类型判据改判 owner） | **4 / 354** |
| `[B]` | `0x40b12f` 地块步长 `0x34 → 0x38` | **13 / 354** |
| `[C]` | `0x42950a` 企業步长 `0x34 → 0x38` | **38 / 354** |

跑法：
```bash
cd rich4-spec && .venv/bin/python tests/test_land_mutation_gates.py
cd rich4-spec && .venv/bin/python tests/test_land_mutation_gates.py --falsify
```
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402

# ── 被测函数 ────────────────────────────────────────────────────────────────
MUTATE = 0x40AB4A          # mutate_land(ref, mode)      305 B
UPGRADE = 0x40B110         # upgrade(ref)                273 B
REOWN = 0x4294D5           # update_commercial_owner(player, stock)  277 B

# ── 真跑 / 打桩 ────────────────────────────────────────────────────────────
RELEASE_ALL = 0x40DFFA     # 真跑
MAP_REFRESH = 0x40A4E1     # 桩
PRNG = 0x456F2D            # 桩
PICK_TYPE = 0x440AAC       # 桩
MEMMOVE = 0x456DE8         # 桩

# ── 全局（.bss 0x48a000..0x499c00 ⇒ 每次 call 前被 reset 成 0） ────────────
LAND_PTR = 0x498E84
FAC_PTR = 0x498E88
COM_PTR = 0x498E7C
MAXLEVEL_TABLE = 0x474940          # DGROUP：[1,5,5,1,5]
STOCK_BASE, STOCK_STRIDE = 0x496980, 0x24
STOCK_COMNO = 0x04                 # word：1 基企業序号
HOLD_BASE, HOLD_STRIDE, HOLD_STOCK = 0x4971A0, 0x60, 8
CUR, NUM_PLAYERS = 0x49910C, 0x499114
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_BUSY = 0x15, 0x32

# ── 记录布局 ───────────────────────────────────────────────────────────────
LAND_STRIDE = 0x34
L_NAME, L_STATUS, L_TYPE, L_OWNER, L_LEVEL = 0x04, 0x17, 0x18, 0x19, 0x1A
L_LANDPRICE, L_HOUSEPRICE, L_FLAST = 0x1C, 0x1E, 0x30
FAC_STRIDE = 0x38
F_NAME, F_TYPE, F_OWNER, F_LEVEL, F_STATUS = 0x04, 0x18, 0x19, 0x1A, 0x1C
F_RESEARCH, F_LANDPRICE, F_RATE, F_FLAST = 0x1D, 0x22, 0x24, 0x34
COM_STRIDE = 0x34
C_STOCK, C_OWNER, C_RANK, C_ASSETS = 0x19, 0x18, 0x1C, 0x24

MODE_DEMOLISH, MODE_CLEAR, MODE_FLATTEN = 0, 1, 2

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0
LAND_LO, LAND_HI = 0x7D0, 0xFA0
FAC_LO, FAC_HI = 0xFA0, 0x1770

# ── 暂存区（跨 call 保持 ⇒ setup 里必须自己清零） ──────────────────────────
LANDS = SCRATCH_BASE + 0x1000
FACS = SCRATCH_BASE + 0x3000
COMS = SCRATCH_BASE + 0x5000
S_RAND, S_RAND_N = SCRATCH_BASE + 0x700, SCRATCH_BASE + 0x704
S_REF, S_REF_N = SCRATCH_BASE + 0x708, SCRATCH_BASE + 0x70C
S_TYPE, S_TYPE_N = SCRATCH_BASE + 0x710, SCRATCH_BASE + 0x714

# 大索引边界用例用的大表（0x7cf 号记录要 69KB，暂存区放不下）
ARENA, ARENA_SIZE = 0x700000, 0x120000
BIG_LANDS = ARENA
BIG_FACS = ARENA + 0x80000

FILL_L, FILL_F, FILL_C = 0xA5, 0x5A, 0xC3
NAME = b"TestLand\x00\x00\x00\x00\x00\x00\x00\x00"

RESULTS = []
FAILED = []
QUIET = False


def say(msg=""):
    if not QUIET:
        print(msg)


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    if not ok:
        FAILED.append(desc)
    if not QUIET:
        g = got if isinstance(got, (int, str, tuple, list)) else str(got)
        w = want if isinstance(want, (int, str, tuple, list)) else str(want)
        print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {g!s:<24} 期望 {w!s}")
    return ok


def hexdiff(before: bytes, after: bytes):
    """逐字节比 → 被写的偏移（形态 `('+0x18', '+0x1a')`）"""
    if len(before) != len(after):
        return ("LEN",)
    return tuple(f"+0x{i:02x}" for i in range(len(before)) if before[i] != after[i])


def put32(emu, va, v):
    """无符号 32 位写（`Emu.write32` 走 `<i`，塞不进 0xdeadbeef 这类值）"""
    emu.write(va, struct.pack("<I", v & 0xFFFFFFFF))


# ── 记录打包（带哨兵填充 ⇒ 任何越界/漏写都会被 hexdiff 抓到） ──────────────
def pack_land(owner=0, level=0, type=0, status=0,
              land_price=0, house_price=0, flast=0):
    b = bytearray([FILL_L] * LAND_STRIDE)
    b[L_NAME:L_NAME + len(NAME)] = NAME
    b[L_STATUS] = status & 0xFF
    b[L_TYPE] = type & 0xFF
    b[L_OWNER] = owner & 0xFF
    b[L_LEVEL] = level & 0xFF
    struct.pack_into("<H", b, L_LANDPRICE, land_price & 0xFFFF)
    struct.pack_into("<H", b, L_HOUSEPRICE, house_price & 0xFFFF)
    struct.pack_into("<I", b, L_FLAST, flast & 0xFFFFFFFF)
    return bytes(b)


def pack_fac(owner=0, level=0, type=0, status=0, research=0,
             land_price=0, rate=0, flast=0):
    b = bytearray([FILL_F] * FAC_STRIDE)
    b[F_NAME:F_NAME + len(NAME)] = NAME
    b[F_TYPE] = type & 0xFF
    b[F_OWNER] = owner & 0xFF
    b[F_LEVEL] = level & 0xFF
    b[F_STATUS] = status & 0xFF
    struct.pack_into("<H", b, F_RESEARCH, research & 0xFFFF)
    struct.pack_into("<H", b, F_LANDPRICE, land_price & 0xFFFF)
    struct.pack_into("<H", b, F_RATE, rate & 0xFFFF)
    struct.pack_into("<I", b, F_FLAST, flast & 0xFFFFFFFF)
    return bytes(b)


def pack_com(stock=0, owner=0, ranking=(0, 0, 0, 0), assets=0):
    b = bytearray([FILL_C] * COM_STRIDE)
    b[F_NAME:F_NAME + len(NAME)] = NAME
    b[C_STOCK] = stock & 0xFF
    b[C_OWNER] = owner & 0xFF
    for i, r in enumerate(ranking):
        b[C_RANK + i] = r & 0xFF
    struct.pack_into("<I", b, C_ASSETS, assets & 0xFFFFFFFF)
    return bytes(b)


class World:
    """三支函数共用的一个 exe 镜像（每次 call 前 reset DGROUP/.bss）。"""

    WATCH = (0x40AB9E, 0x40ABA4, 0x40ABAE, 0x40ABC8, 0x40AC2E, 0x40AC3A,
             0x40AC5E, 0x40B161, 0x40B1A0, 0x40B1C5, 0x40B1E2, 0x40B1F9,
             0x42951E, 0x429579, 0x4295AD, 0x4295CA)

    def __init__(self, sabotage=None):
        self.emu = Emu()
        # ── 打桩 ──
        self.emu.patch(MAP_REFRESH,
                       b"\x8B\x44\x24\x04"
                       b"\xA3" + struct.pack("<I", S_REF)
                       + b"\xFF\x05" + struct.pack("<I", S_REF_N) + b"\xC3")
        self.emu.patch(PRNG,
                       b"\xA1" + struct.pack("<I", S_RAND)
                       + b"\xFF\x05" + struct.pack("<I", S_RAND_N) + b"\xC3")
        self.emu.patch(PICK_TYPE,
                       b"\xA1" + struct.pack("<I", S_TYPE)
                       + b"\xFF\x05" + struct.pack("<I", S_TYPE_N) + b"\xC3")
        self.emu.patch(MEMMOVE,
                       b"\x60"
                       b"\x8B\x7C\x24\x24\x8B\x74\x24\x28\x8B\x4C\x24\x2C"
                       b"\xF3\xA4\x61\xC3")
        self.emu.mu.mem_map(ARENA, ARENA_SIZE)
        self.watch = set(self.WATCH)
        self.hits = {}
        self.emu.mu.hook_add(UC_HOOK_CODE, self._hook)
        # 真实上限表（未打补丁前读 DGROUP 镜像）
        self.real_max = [self.emu.read8(MAXLEVEL_TABLE + i) for i in range(8)]
        if sabotage is not None:
            va, old, new, desc = SABOTAGES[sabotage]
            got = self.emu.read8(va)
            if got != old:
                raise RuntimeError(f"破坏点 0x{va:08x} 原字节是 0x{got:02x}，不是 0x{old:02x}")
            self.emu.patch(va, bytes([new]))
            self.sabotage_desc = desc
        self.reset_state()

    def _hook(self, mu, address, size, user):
        if address in self.watch:
            self.hits[address] = self.hits.get(address, 0) + 1

    # ── 状态声明 ───────────────────────────────────────────────────────────
    def reset_state(self):
        self.cur = 0
        self.nplayers = 4
        self.who = [1, 1, 1, 1]
        self.busy = [0, 0, 0, 0]
        self.rand_val = 0
        self.pick_val = 0
        self.lands = {}
        self.facs = {}
        self.coms = {}
        self.stocks = {}
        self.holds = {}
        self.land_base, self.fac_base = LANDS, FACS
        self.big = False
        self.max_override = {}      # type -> 覆盖 0x474940 的字节
        self.hits = {}
        return self

    def big_tables(self):
        self.land_base, self.fac_base, self.big = BIG_LANDS, BIG_FACS, True
        return self

    def land(self, idx, **f):
        self.lands[idx] = f
        return self

    def fac(self, idx, **f):
        self.facs[idx] = f
        return self

    def com(self, n, **f):
        self.coms[n] = f
        return self

    def stock_company(self, stock, n):
        self.stocks[stock] = n
        return self

    def hold(self, player, stock, amount):
        self.holds[(player, stock)] = amount
        return self

    def maxlevel(self, type, value):
        self.max_override[type] = value
        return self

    # ── 注入 ───────────────────────────────────────────────────────────────
    def _setup(self, emu):
        put32(emu, LAND_PTR, self.land_base)
        put32(emu, FAC_PTR, self.fac_base)
        put32(emu, COM_PTR, COMS)
        put32(emu, CUR, self.cur)
        put32(emu, NUM_PLAYERS, self.nplayers)
        put32(emu, S_RAND, self.rand_val)
        put32(emu, S_RAND_N, 0)
        put32(emu, S_REF, 0x00C0FFEE)
        put32(emu, S_REF_N, 0)
        put32(emu, S_TYPE, self.pick_val)
        put32(emu, S_TYPE_N, 0)
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_WHO, self.who[p])
            emu.write8(pb + P_BUSY, self.busy[p])
        for t, v in self.max_override.items():
            emu.write8(MAXLEVEL_TABLE + t, v)
        # 表（暂存区跨调用保持 ⇒ 先按用到的最远下标清零）
        if self.lands:
            emu.write(self.land_base, b"\x00" * (max(self.lands) + 1) * LAND_STRIDE)
        if self.facs:
            emu.write(self.fac_base, b"\x00" * (max(self.facs) + 1) * FAC_STRIDE)
        if self.coms:
            emu.write(COMS, b"\x00" * (max(self.coms) + 1) * COM_STRIDE)
        for idx, f in self.lands.items():
            emu.write(self.land_base + idx * LAND_STRIDE, pack_land(**f))
        for idx, f in self.facs.items():
            emu.write(self.fac_base + idx * FAC_STRIDE, pack_fac(**f))
        for n, f in self.coms.items():
            emu.write(COMS + n * COM_STRIDE, pack_com(**f))
        for stock, n in self.stocks.items():
            emu.write16(STOCK_BASE + stock * STOCK_STRIDE + STOCK_COMNO, n & 0xFFFF)
        for (p, stock), amt in self.holds.items():
            put32(emu, HOLD_BASE + p * HOLD_STRIDE + stock * HOLD_STOCK, amt)

    # ── 调用 ───────────────────────────────────────────────────────────────
    def run(self, fn, args):
        self.last_error = None
        try:
            r = self.emu.call(fn, args, setup=self._setup)
            self.ret = r["eax"]
        except Exception as e:                      # noqa: BLE001
            self.last_error = str(e)
            self.ret = f"CRASH({e})"
            if not QUIET:
                print(f"    ⚠️ 仿真异常：{e}")
        return self.ret

    def run_mutate(self, ref, mode):
        return self.run(MUTATE, [ref, mode])

    def run_upgrade(self, ref):
        return self.run(UPGRADE, [ref])

    def run_reown(self, player, stock):
        return self.run(REOWN, [player, stock])

    # ── 回读 ───────────────────────────────────────────────────────────────
    def read_land(self, idx):
        return self.emu.read(self.land_base + idx * LAND_STRIDE, LAND_STRIDE)

    def read_fac(self, idx):
        return self.emu.read(self.fac_base + idx * FAC_STRIDE, FAC_STRIDE)

    def read_com(self, n):
        return self.emu.read(COMS + n * COM_STRIDE, COM_STRIDE)

    def diff_land(self, idx):
        return hexdiff(pack_land(**self.lands[idx]), self.read_land(idx))

    def diff_fac(self, idx):
        return hexdiff(pack_fac(**self.facs[idx]), self.read_fac(idx))

    def diff_com(self, n):
        return hexdiff(pack_com(**self.coms[n]), self.read_com(n))

    def land_f(self, idx, off):
        return self.read_land(idx)[off]

    def land_u16(self, idx, off):
        return struct.unpack_from("<H", self.read_land(idx), off)[0]

    def land_u32(self, idx, off):
        return struct.unpack_from("<I", self.read_land(idx), off)[0]

    def fac_f(self, idx, off):
        return self.read_fac(idx)[off]

    def fac_u16(self, idx, off):
        return struct.unpack_from("<H", self.read_fac(idx), off)[0]

    def fac_u32(self, idx, off):
        return struct.unpack_from("<I", self.read_fac(idx), off)[0]

    def com_f(self, n, off):
        return self.read_com(n)[off]

    def com_rank(self, n):
        b = self.read_com(n)
        return tuple(b[C_RANK + i] for i in range(4))

    def com_owner(self, n):
        return self.read_com(n)[C_OWNER]

    def rand_calls(self):
        return self.emu.readu32(S_RAND_N)

    def refresh_calls(self):
        return self.emu.readu32(S_REF_N)

    def refresh_arg(self):
        return self.emu.readu32(S_REF)

    def pick_type_calls(self):
        return self.emu.readu32(S_TYPE_N)

    def busy_now(self):
        return tuple(self.emu.read8(PLAYER_BASE + p * PLAYER_STRIDE + P_BUSY)
                     for p in range(4))

    def who_now(self):
        return tuple(self.emu.read8(PLAYER_BASE + p * PLAYER_STRIDE + P_WHO)
                     for p in range(4))


# ============================================================================
#  [A]  0x0040ab4a —— mutate_land(ref, mode)
# ============================================================================
def group_a(w):
    say("\n" + "=" * 78)
    say("[A] 0x0040ab4a(ref, mode) —— 拆除 / 完全清除 / 夷平（305 B，整支驱动）")
    say("=" * 78)

    # ── A1 · 格值范围与 mode 分派 ─────────────────────────────────────────
    say("\n[A1] 格值范围闸门：只有 (0x7d0,0xfa0) 走地块、(0xfa0,0x1770) 走設施")
    for ref, desc in ((LAND_LO, "ref=2000（下界本身）"), (FAC_LO, "ref=4000（地块/設施分界）"),
                      (FAC_HI, "ref=6000（上界本身）"), (0x7CF, "ref=1999"),
                      (0x1800, "ref=6144（企業段）")):
        w.reset_state()
        w.land(1, owner=3, level=2, type=0)
        w.fac(1, owner=3, level=2, type=1)
        w.com(1, owner=1, ranking=(1, 2, 3, 4))
        w.run_mutate(ref, MODE_CLEAR)
        case(f"{desc} · mode 1 ⇒ 返回 0", w.ret, 0)
        case("  两表一个字节都没动", (w.diff_land(1), w.diff_fac(1)), ((), ()))
        case("  没调 0x40a4e1", w.refresh_calls(), 0)
        case("  没放人（0x40dffa 的门槛没碰到）", w.busy_now(), (0, 0, 0, 0))

    w.reset_state()
    w.land(1, owner=3, level=2, type=0, flast=0x11111111)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("★ ref=2001 ⇒ 动的正是**地块 1 号**记录（下标 = ref−0x7d0）", w.land_f(1, L_LEVEL), 1)
    case("  返回 1", w.ret, 1)

    w.reset_state().big_tables()
    w.land(0x7CF, owner=3, level=2, type=0)
    w.run_mutate(LAND_HI - 1, MODE_DEMOLISH)
    case("★ ref=3999 ⇒ 地块 0x7cf 号（(0xf9f−0x7d0)）", w.land_f(0x7CF, L_LEVEL), 1)
    case("  返回 1", w.ret, 1)

    w.reset_state().big_tables()
    w.fac(0x7CF, owner=3, level=2, type=1)
    w.run_mutate(FAC_HI - 1, MODE_FLATTEN)
    case("★ ref=5999 ⇒ 設施 0x7cf 号（(0x176f−0xfa0)）", w.fac_f(0x7CF, F_LEVEL), 0)
    case("  返回 1", w.ret, 1)

    w.reset_state()
    w.fac(1, owner=3, level=2, type=1)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("★ ref=4001 ⇒ 動的是**設施 1 号**", w.fac_f(1, F_LEVEL), 1)
    case("  返回 1", w.ret, 1)

    say("\n[A2] mode ≥ 3 / 非 0 大数 ⇒ 一律 0，且不写、不刷新、不放人")
    for mode in (3, 4, 0x7FFFFFFF, -1):
        w.reset_state()
        w.land(1, owner=3, level=2, type=0)
        w.fac(1, owner=3, level=2, type=1)
        w.run_mutate(LAND_LO + 1, mode)
        case(f"地块 mode={mode} ⇒ 0，无写", (w.ret, w.diff_land(1)), (0, ()))
        w.run_mutate(FAC_LO + 1, mode)
        case(f"設施 mode={mode} ⇒ 0，无写/无刷新", (w.ret, w.diff_fac(1), w.refresh_calls()),
             (0, (), 0))
        case("  没放人", w.busy_now(), (0, 0, 0, 0))

    # ── A3 · 地块 mode 0 ─────────────────────────────────────────────────
    say("\n[A3] 地块 mode 0（拆一级）：住宅只掉一级；连锁店(type≠0) 直接铲平 —— 但 **owner 保留**")
    w.reset_state()
    w.land(1, owner=3, level=3, type=0, status=0x50, land_price=7, house_price=9)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("住宅 3 级 ⇒ 返回 1", w.ret, 1)
    case("  ★ level 3→2", w.land_f(1, L_LEVEL), 2)
    case("  type 仍是 0（住宅）", w.land_f(1, L_TYPE), 0)
    case("  owner 不动", w.land_f(1, L_OWNER), 3)
    case("  ★ 精确写点 = 只有 +0x1a", w.diff_land(1), ("+0x1a",))
    case("  priceStatus/地价/房价 都没动",
         (w.land_f(1, L_STATUS), w.land_u16(1, L_LANDPRICE), w.land_u16(1, L_HOUSEPRICE)),
         (0x50, 7, 9))
    case("  ★★ 地块支**不调 0x40dffa**（busy 不变）", w.busy_now(), (0, 0, 0, 0))
    case("  也不调 0x40a4e1", w.refresh_calls(), 0)
    case("  旁证：确实走了 0x40ab9e（type 判据）", w.hits.get(0x40AB9E, 0) > 0, True)

    w.reset_state()
    w.land(1, owner=3, level=1, type=0)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("住宅 1 级 ⇒ 0 级、返回 1", (w.ret, w.land_f(1, L_LEVEL)), (1, 0))
    case("  ★ 仍然不放人（住宅支没有 0x40dffa）", w.busy_now(), (0, 0, 0, 0))

    w.reset_state()
    w.land(1, owner=3, level=0, type=0, status=0x50, flast=0x22222222)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("住宅 0 级 ⇒ 返回 0", w.ret, 0)
    case("  ★ 一个字节都没写", w.diff_land(1), ())

    for lv, tp, desc in ((1, 1, "连锁店 1 级"), (5, 1, "连锁店 5 级"), (3, 2, "type=2 3 级")):
        w.reset_state()
        w.land(1, owner=3, level=lv, type=tp, status=0x51, flast=0x33333333)
        w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
        case(f"★ {desc}（type≠0）⇒ level 0 且 type 0，返回 1",
             (w.ret, w.land_f(1, L_LEVEL), w.land_f(1, L_TYPE)), (1, 0, 0))
        case("  ★★ owner **保留**（不是清归属）", w.land_f(1, L_OWNER), 3)
        case("  ★ 精确写点 = {+0x18,+0x1a}（+0x1a 被写两次，净效果一样）",
             w.diff_land(1), ("+0x18", "+0x1a"))
        case("  flast / priceStatus 没动",
             (w.land_u32(1, L_FLAST), w.land_f(1, L_STATUS)), (0x33333333, 0x51))

    # ── A4 · 地块 mode 1 ─────────────────────────────────────────────────
    say("\n[A4] 地块 mode 1（完全清除）：owner+level+type 三项字节 + **dword @+0x30**，无前置判据")
    w.reset_state()
    w.land(1, owner=3, level=4, type=2, status=0x50, land_price=7, house_price=9,
           flast=0x11223344)
    w.run_mutate(LAND_LO + 1, MODE_CLEAR)
    case("返回 1", w.ret, 1)
    case("  owner=0 / level=0 / type=0",
         (w.land_f(1, L_OWNER), w.land_f(1, L_LEVEL), w.land_f(1, L_TYPE)), (0, 0, 0))
    case("  ★ flast（dword @+0x30）= 0", w.land_u32(1, L_FLAST), 0)
    case("  ★ 精确写点 = {+0x18,+0x19,+0x1a,+0x30..+0x33}",
         w.diff_land(1), ("+0x18", "+0x19", "+0x1a", "+0x30", "+0x31", "+0x32", "+0x33"))
    case("  priceStatus / 地价 / 房价 不属清除范围",
         (w.land_f(1, L_STATUS), w.land_u16(1, L_LANDPRICE), w.land_u16(1, L_HOUSEPRICE)),
         (0x50, 7, 9))
    case("  调 0x40a4e1 一次、实参 0", (w.refresh_calls(), w.refresh_arg()), (1, 0))
    case("  ★★ 地块 mode 1 **不放人**", w.busy_now(), (0, 0, 0, 0))

    w.reset_state()
    w.busy = [1, 5, 0, 3]
    w.land(1, level=0, type=0, owner=0, flast=0, status=0, land_price=0, house_price=0)
    w.run_mutate(LAND_LO + 1, MODE_CLEAR)
    case("★★ 全 0 记录：仍**返回 1**（无前置判据 ⇒ 恒 changed）", w.ret, 1)
    case("  没有可写的（值本来就对）", w.diff_land(1), ())
    case("  但仍然调了 0x40a4e1", w.refresh_calls(), 1)
    case("  busy 依旧一个不动（地块支不放人）", w.busy_now(), (1, 5, 0, 3))

    # ── A5 · 地块 mode 2 ─────────────────────────────────────────────────
    say("\n[A5] 地块 mode 2（夷平）：level 归 0 + type 归 0，**owner / flast 保留**")
    w.reset_state()
    w.land(1, owner=3, level=5, type=0, flast=0x44444444)
    w.run_mutate(LAND_LO + 1, MODE_FLATTEN)
    case("住宅 5 级 ⇒ 0 级、type 0、返回 1",
         (w.ret, w.land_f(1, L_LEVEL), w.land_f(1, L_TYPE)), (1, 0, 0))
    case("  ★ owner **保留**", w.land_f(1, L_OWNER), 3)
    case("  ★ flast **保留**（与 mode 1 的区别）", w.land_u32(1, L_FLAST), 0x44444444)
    case("  ★ 精确写点 = {+0x1a}（type 本来就是 0 ⇒ 写 0 看不出来）",
         w.diff_land(1), ("+0x1a",))
    case("  不放人 / 不刷新", (w.busy_now(), w.refresh_calls()), ((0, 0, 0, 0), 0))

    w.reset_state()
    w.land(1, owner=3, level=2, type=1)
    w.run_mutate(LAND_LO + 1, MODE_FLATTEN)
    case("★ 连锁店 2 级 mode 2 ⇒ 0/0（与 mode 0 同结果，但 mode 0 是 dec 后再清）",
         (w.ret, w.land_f(1, L_LEVEL), w.land_f(1, L_TYPE)), (1, 0, 0))
    case("  ★★ owner 保留", w.land_f(1, L_OWNER), 3)

    w.reset_state()
    w.land(1, owner=3, level=0, type=0, flast=0x55555555)
    w.run_mutate(LAND_LO + 1, MODE_FLATTEN)
    case("0 级 ⇒ 返回 0、零写", (w.ret, w.diff_land(1)), (0, ()))

    # ── A6 · 設施 mode 0 ─────────────────────────────────────────────────
    say("\n[A6] 設施 mode 0：没拆到 0 级 ⇒ 只掉一级；**拆到 0 级才** type=0 + 全场放人")
    w.reset_state()
    w.fac(1, owner=2, level=3, type=2, status=0x51, land_price=5, rate=6, research=0x0102)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("3 级 ⇒ 2 级、返回 1", (w.ret, w.fac_f(1, F_LEVEL)), (1, 2))
    case("  type 保留 2", w.fac_f(1, F_TYPE), 2)
    case("  ★ 精确写点 = {+0x1a}", w.diff_fac(1), ("+0x1a",))
    case("  ★ 未归零 ⇒ **不放人**", w.busy_now(), (0, 0, 0, 0))
    case("  不刷新", w.refresh_calls(), 0)
    case("  owner / status / landPrice / rate / research 不动",
         (w.fac_f(1, F_OWNER), w.fac_f(1, F_STATUS), w.fac_u16(1, F_LANDPRICE),
          w.fac_u16(1, F_RATE)), (2, 0x51, 5, 6))

    w.reset_state()
    w.busy = [1, 0, 5, 0]
    w.fac(1, owner=2, level=1, type=2, flast=0x66666666)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("★ 1 级 ⇒ 0 级 + type 0、返回 1",
         (w.ret, w.fac_f(1, F_LEVEL), w.fac_f(1, F_TYPE)), (1, 0, 0))
    case("  ★★ owner **保留**（拆到 0 级也不清归属）", w.fac_f(1, F_OWNER), 2)
    case("  ★ flast **保留**（+0x34 不动）", w.fac_u32(1, F_FLAST), 0x66666666)
    case("  ★ 精确写点 = {+0x18,+0x1a}", w.diff_fac(1), ("+0x18", "+0x1a"))
    case("  ★★ 归零 ⇒ 0x40dffa 一刀切：(1,0,5,0) → (0x80,0,0x80,0)",
         w.busy_now(), (0x80, 0, 0x80, 0))
    case("  但**不**刷新地图数组", w.refresh_calls(), 0)

    w.reset_state()
    w.busy = [1, 2, 3, 4]
    w.who = [1, 1, 0, 1]
    w.fac(1, level=1, type=3)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("★ 出局者（whoPlays=0）跳过 ⇒ 下标 2 保持 3", w.busy_now(), (0x80, 0x80, 3, 0x80))

    w.reset_state()
    w.fac(1, owner=2, level=0, type=1, flast=0x77777777)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("0 级 ⇒ 返回 0、零写、不放人",
         (w.ret, w.diff_fac(1), w.busy_now()), (0, (), (0, 0, 0, 0)))

    # ── A7 · 設施 mode 1 ─────────────────────────────────────────────────
    say("\n[A7] 設施 mode 1：四项全清 —— flast 在 **+0x34**（住宅才是 +0x30）")
    w.reset_state()
    w.busy = [2, 0, 0, 7]
    w.fac(1, owner=2, level=3, type=4, status=0x51, research=0x0102,
          land_price=5, rate=6, flast=0x44556677)
    w.run_mutate(FAC_LO + 1, MODE_CLEAR)
    case("返回 1", w.ret, 1)
    case("  owner=0 / level=0 / type=0",
         (w.fac_f(1, F_OWNER), w.fac_f(1, F_LEVEL), w.fac_f(1, F_TYPE)), (0, 0, 0))
    case("  ★ flast（dword @+0x34）= 0", w.fac_u32(1, F_FLAST), 0)
    case("  ★ 精确写点 = {+0x18,+0x19,+0x1a,+0x34..+0x37}",
         w.diff_fac(1), ("+0x18", "+0x19", "+0x1a", "+0x34", "+0x35", "+0x36", "+0x37"))
    case("  ★★ +0x30..+0x33 **一个字节都没动**（設施的 flast 不在 +0x30）",
         tuple(o for o in w.diff_fac(1) if o in ("+0x30", "+0x31", "+0x32", "+0x33")), ())
    case("  status / research / landPrice / rate 不在清除范围",
         (w.fac_f(1, F_STATUS), w.fac_u16(1, F_RESEARCH), w.fac_u16(1, F_LANDPRICE),
          w.fac_u16(1, F_RATE)), (0x51, 0x0102, 5, 6))
    case("  ★★ 放人：(2,0,0,7) → (0x80,0,0,0x80)", w.busy_now(), (0x80, 0, 0, 0x80))
    case("  ★ 0x40a4e1 一次、实参 0", (w.refresh_calls(), w.refresh_arg()), (1, 0))

    w.reset_state()
    w.busy = [1, 1, 1, 1]
    w.fac(1, owner=0, level=0, type=0, flast=0)
    w.run_mutate(FAC_LO + 1, MODE_CLEAR)
    case("★★ 全 0 設施：仍返回 1（无前置判据）", w.ret, 1)
    case("  仍然放人 + 刷新", (w.busy_now(), w.refresh_calls()),
         ((0x80, 0x80, 0x80, 0x80), 1))

    # ── A8 · 設施 mode 2 ─────────────────────────────────────────────────
    say("\n[A8] 設施 mode 2（夷平）：level/type 归 0 + 放人，**owner / flast 保留**，不刷新")
    w.reset_state()
    w.busy = [0, 4, 0, 0]
    w.fac(1, owner=2, level=2, type=3, flast=0x88888888, status=0x50)
    w.run_mutate(FAC_LO + 1, MODE_FLATTEN)
    case("2 级 ⇒ 0 级 + type 0、返回 1",
         (w.ret, w.fac_f(1, F_LEVEL), w.fac_f(1, F_TYPE)), (1, 0, 0))
    case("  ★★ owner 保留", w.fac_f(1, F_OWNER), 2)
    case("  ★ flast 保留（+0x34）", w.fac_u32(1, F_FLAST), 0x88888888)
    case("  ★ 精确写点 = {+0x18,+0x1a}", w.diff_fac(1), ("+0x18", "+0x1a"))
    case("  放人", w.busy_now(), (0, 0x80, 0, 0))
    case("  不刷新", w.refresh_calls(), 0)
    case("  status 保留", w.fac_f(1, F_STATUS), 0x50)

    w.reset_state()
    w.busy = [3, 3, 3, 3]
    w.fac(1, owner=2, level=0, type=1, flast=0x99999999)
    w.run_mutate(FAC_LO + 1, MODE_FLATTEN)
    case("0 级 ⇒ 返回 0、零写、**不放人**",
         (w.ret, w.diff_fac(1), w.busy_now()), (0, (), (3, 3, 3, 3)))

    # ── A9 · 等价性 / 旁证 ───────────────────────────────────────────────
    say("\n[A9] 分支旁证（防止「断言静默退化成别的分支」）")
    w.reset_state()
    w.land(1, level=2, type=0)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("  走過 0x40aba4（连锁店清空支）了吗？住宅支应为 0", w.hits.get(0x40ABA4, 0), 0)
    w.reset_state()
    w.land(1, level=2, type=1)
    w.run_mutate(LAND_LO + 1, MODE_DEMOLISH)
    case("  连锁店 ⇒ 走了 0x40aba4", w.hits.get(0x40ABA4, 0) > 0, True)
    w.reset_state()
    w.land(1, level=2, type=0)
    w.run_mutate(LAND_LO + 1, MODE_FLATTEN)
    case("  mode 2 ⇒ 走了 0x40abc8", w.hits.get(0x40ABC8, 0) > 0, True)
    w.reset_state()
    w.fac(1, level=1, type=1)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("  設施拆到 0 级 ⇒ 走了 0x40ac2e（jne 不跳）", w.hits.get(0x40AC2E, 0) > 0, True)
    w.reset_state()
    w.busy = [1, 0, 0, 0]
    w.fac(1, level=1, type=1)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("  busy=1 ⇒ 真的被放人", w.busy_now(), (0x80, 0, 0, 0))
    w.reset_state()
    w.fac(1, level=3, type=1)
    w.run_mutate(FAC_LO + 1, MODE_DEMOLISH)
    case("  未归零 ⇒ 没走 0x40ac2e 的清空支（0x40ac30）", w.hits.get(0x40AC2E, 0) > 0, True)
    case("  但 busy 不动", w.busy_now(), (0, 0, 0, 0))


# ============================================================================
#  [B]  0x0040b110 —— upgrade(ref)
# ============================================================================
def group_b(w):
    say("\n" + "=" * 78)
    say("[B] 0x0040b110(ref) —— 就地加蓋一級 / 首建定种类（273 B，整支驱动）")
    say("=" * 78)

    say("\n[B1] 上限表的真值（DGROUP 0x474940）")
    case("0x474940[0..7] == [1,5,5,1,5,0,0,0]（公園/旅館/購物中心/加油站/研究所）",
         tuple(w.real_max), (1, 5, 5, 1, 5, 0, 0, 0))

    say("\n[B2] 地块支：上限**写死**（type 0 ⇒ 5、type 1 ⇒ 1），其余 type 一律不能蓋")
    for tp, lv, want_ret, want_lv, desc in (
            (0, 4, 0x81, 5, "住宅 4 级 ⇒ 5 级（bit7 = 剛好到 5 級）"),
            (0, 3, 1, 4, "住宅 3 级 ⇒ 4 级"),
            (0, 0, 1, 1, "住宅 0 级 ⇒ 1 级"),
            (0, 5, 0, 5, "住宅 5 级 ⇒ 已满，返回 0"),
            (1, 0, 1, 1, "连锁店 0 级 ⇒ 1 级"),
            (1, 1, 0, 1, "连锁店 1 级 ⇒ 上限写死 1，返回 0"),
            (1, 5, 0, 5, "连锁店 5 级 ⇒ 返回 0"),
            (2, 0, 0, 0, "★ type=2 0 级 ⇒ **不能蓋**（只有 0/1 两种地块可蓋）"),
            (2, 4, 0, 4, "★ type=2 4 级 ⇒ 返回 0"),
            (9, 0, 0, 0, "★ type=9 ⇒ 返回 0")):
        w.reset_state()
        w.land(1, owner=3, level=lv, type=tp, status=0x50, land_price=7, house_price=9,
               flast=0x12345678)
        w.run_upgrade(LAND_LO + 1)
        case(desc + f" ⇒ 返回 {want_ret}", w.ret, want_ret)
        case(f"  level == {want_lv}", w.land_f(1, L_LEVEL), want_lv)
        if want_lv != lv:
            case("  ★ 精确写点 = {+0x1a}", w.diff_land(1), ("+0x1a",))
        else:
            case("  零写", w.diff_land(1), ())
        case("  ★★ owner 一个字节都没动（替别人蓋也一样）", w.land_f(1, L_OWNER), 3)
        case("  status / flast / 地价 / 房价 不动",
             (w.land_f(1, L_STATUS), w.land_u32(1, L_FLAST)), (0x50, 0x12345678))
        case("  不掷 rand / 不刷新 / 不放人",
             (w.rand_calls(), w.refresh_calls(), w.busy_now()), (0, 0, (0, 0, 0, 0)))

    w.reset_state()
    w.land(1, owner=3, level=4, type=0)
    w.run_upgrade(LAND_LO + 1)
    case("★ 旁证：走了 0x40b161（加蓋写点）", w.hits.get(0x40B161, 0) > 0, True)

    say("\n[B3] 地块支的格值范围")
    for ref, desc in ((LAND_LO, "ref=2000（下界）"), (FAC_LO, "ref=4000"),
                      (FAC_HI, "ref=6000"), (0x7CF, "ref=1999")):
        w.reset_state()
        w.land(1, level=4, type=0)
        w.fac(1, level=2, type=1)
        w.run_upgrade(ref)
        case(f"{desc} ⇒ 返回 0、两表零写", (w.ret, w.diff_land(1), w.diff_fac(1)), (0, (), ()))

    w.reset_state().big_tables()
    w.land(0x7CF, level=4, type=0)
    w.run_upgrade(LAND_HI - 1)
    case("★ ref=3999 ⇒ 地块 0x7cf 号升到 5 级、返回 0x81",
         (w.ret, w.land_f(0x7CF, L_LEVEL)), (0x81, 5))

    say("\n[B4] 設施支（level ≠ 0）：上限查 **0x474940[type]**，到 5 级返回 0x81")
    for tp, lv, mx, want_ret, want_lv, desc in (
            (1, 2, None, 1, 3, "旅館 2→3"),
            (4, 1, None, 1, 2, "研究所 1→2"),
            (1, 4, None, 0x81, 5, "旅館 4→5（bit7）"),
            (1, 5, None, 0, 5, "旅館 5 级 ⇒ 已满"),
            (0, 1, None, 0, 1, "公園（上限 1）1 级 ⇒ 0"),
            (3, 1, None, 0, 1, "加油站（上限 1）1 级 ⇒ 0"),
            (2, 6, 7, 1, 7, "★ 把 0x474940[2] 改成 7 ⇒ 6→7（**证明查的是表字节**）"),
            (4, 3, 3, 0, 3, "★ 把 0x474940[4] 改成 3 ⇒ 3 级被挡（表字节说了算）")):
        w.reset_state()
        if mx is not None:
            w.maxlevel(tp, mx)
        w.fac(1, owner=2, level=lv, type=tp, status=0x51, land_price=5, rate=6,
              research=0x0102, flast=0xABCDEF01)
        w.run_upgrade(FAC_LO + 1)
        case(desc + f" ⇒ 返回 {want_ret}", w.ret, want_ret)
        case(f"  level == {want_lv}", w.fac_f(1, F_LEVEL), want_lv)
        case("  type 不动", w.fac_f(1, F_TYPE), tp)
        case("  ★ owner 不动", w.fac_f(1, F_OWNER), 2)
        case("  ★ flast（+0x34）不动", w.fac_u32(1, F_FLAST), 0xABCDEF01)
        case("  不掷 rand / 不刷新 / 不放人",
             (w.rand_calls(), w.refresh_calls(), w.busy_now()), (0, 0, (0, 0, 0, 0)))

    w.reset_state()
    w.fac(1, level=2, type=1)
    w.run_upgrade(FAC_LO + 1)
    case("★ 旁证：走了 0x40b1f9（等級≠0 的上限支）", w.hits.get(0x40B1F9, 0) > 0, True)

    w.reset_state().big_tables()
    w.fac(0x7CF, level=4, type=1)
    w.run_upgrade(FAC_HI - 1)
    case("★ ref=5999 ⇒ 設施 0x7cf 号升到 5 级、返回 0x81",
         (w.ret, w.fac_f(0x7CF, F_LEVEL)), (0x81, 5))

    say("\n[B5] 設施支（level == 0）：**首建同时定种类**，且不看上限表")
    # 電腦 + 地主就是自己 ⇒ rand()%4 + 1
    for rv, want_type, desc in ((4, 1, "rand=4 ⇒ 4%4+1 = 1"),
                                (5, 2, "rand=5 ⇒ 5%4+1 = 2"),
                                (6, 3, "rand=6 ⇒ 6%4+1 = 3"),
                                (7, 4, "rand=7 ⇒ 7%4+1 = 4"),
                                (12345, 2, "rand=12345（奇數）⇒ 12345%4+1 = 2")):
        w.reset_state()
        w.cur = 0
        w.who = [2, 1, 1, 1]           # 電腦（whoPlays & 6 != 0）
        w.rand_val = rv
        w.fac(1, owner=1, level=0, status=0x51, flast=0x11112222)
        w.run_upgrade(FAC_LO + 1)
        case(f"★ 電腦 + owner==cur+1：{desc}", w.fac_f(1, F_TYPE), want_type)
        case("  ★ 種類 = rand()%4+1（不是位与）", w.fac_f(1, F_TYPE) in (1, 2, 3, 4), True)
        case("  level 0→1、返回 1", (w.ret, w.fac_f(1, F_LEVEL)), (1, 1))
        case("  ★★ rand 恰好用 1 次", w.rand_calls(), 1)
        case("  没走真人选单", w.pick_type_calls(), 0)
        case("  ★ 精确写点 = {+0x18,+0x1a}", w.diff_fac(1), ("+0x18", "+0x1a"))
        case("  owner/status/flast 不动",
             (w.fac_f(1, F_OWNER), w.fac_f(1, F_STATUS), w.fac_u32(1, F_FLAST)),
             (1, 0x51, 0x11112222))
        case("  不刷新 / 不放人", (w.refresh_calls(), w.busy_now()), (0, (0, 0, 0, 0)))

    w.reset_state()
    w.cur = 0
    w.who = [2, 1, 1, 1]
    w.rand_val = -1
    w.fac(1, owner=1, level=0, type=2)
    w.run_upgrade(FAC_LO + 1)
    case("★★ `sar edx,0x1f / idiv` 是**有符号**取模：rand=−1 ⇒ 商 0 余 −1 ⇒ +1 = 0（无符号会是 4）",
         w.fac_f(1, F_TYPE), 0)
    case("  （可达性：原版 rand 只回 0..0x7fff ⇒ 本行只钉编码形态）", w.rand_calls(), 1)

    for owner, desc in ((2, "owner=2（是別人的地，cur=0）"), (0, "owner=0（无主）")):
        w.reset_state()
        w.cur = 0
        w.who = [2, 1, 1, 1]
        w.rand_val = 7
        w.fac(1, owner=owner, level=0, type=2, flast=0x33334444)
        w.run_upgrade(FAC_LO + 1)
        case(f"★ 電腦 + {desc} ⇒ type = 0（公園）、level 1、返回 1",
             (w.ret, w.fac_f(1, F_TYPE), w.fac_f(1, F_LEVEL)), (1, 0, 1))
        case("  ★★ rand **一次都没用**", w.rand_calls(), 0)
        case("  ★ 精确写点 = {+0x18,+0x1a}（原 type=2 被覆写成 0）",
             w.diff_fac(1), ("+0x18", "+0x1a"))
        case("  owner 不动", w.fac_f(1, F_OWNER), owner)

    # 真人 ⇒ 0x440aac(0)
    w.reset_state()
    w.cur = 0
    w.who = [1, 1, 1, 1]
    w.rand_val = 7
    w.pick_val = 3
    w.fac(1, owner=1, level=0, flast=0x55556666)
    w.run_upgrade(FAC_LO + 1)
    case("★ 真人（whoPlays & 6 == 0）⇒ 種類 = 0x440aac(0) 的 al", w.fac_f(1, F_TYPE), 3)
    case("  level 0→1、返回 1", (w.ret, w.fac_f(1, F_LEVEL)), (1, 1))
    case("  ★ 真人选单恰好 1 次", w.pick_type_calls(), 1)
    case("  ★★ rand 一次没用", w.rand_calls(), 0)
    case("  ★ 精确写点 = {+0x18,+0x1a}", w.diff_fac(1), ("+0x18", "+0x1a"))

    w.reset_state()
    w.cur = 0
    w.who = [1, 1, 1, 1]
    w.maxlevel(3, 0)
    w.pick_val = 3
    w.fac(1, owner=1, level=0)
    w.run_upgrade(FAC_LO + 1)
    case("★ level==0 支**不查** 0x474940（把上限改成 0 也照样蓋、種類照给）",
         (w.ret, w.fac_f(1, F_TYPE), w.fac_f(1, F_LEVEL)), (1, 3, 1))

    w.reset_state()
    w.cur = 0
    w.who = [0, 1, 1, 1]
    w.pick_val = 4
    w.fac(1, owner=1, level=0)
    w.run_upgrade(FAC_LO + 1)
    case("★ whoPlays=0（出局）也走**真人支**（`& 6 == 0`）⇒ 用 0x440aac 的值",
         (w.ret, w.fac_f(1, F_TYPE)), (1, 4))

    w.reset_state()
    w.cur = 0
    w.who = [6, 1, 1, 1]
    w.rand_val = 4
    w.pick_val = 3
    w.fac(1, owner=1, level=0)
    w.run_upgrade(FAC_LO + 1)
    case("★ whoPlays=6（& 6 = 6 ≠ 0）走**電腦支** ⇒ rand 用 1 次、选单 0 次",
         (w.rand_calls(), w.pick_type_calls(), w.fac_f(1, F_TYPE)), (1, 0, 1))

    say("\n[B6] whoPlays 读的是**當前玩家**（同一块地、只换 cur）")
    w.reset_state()
    w.who = [1, 2, 1, 1]
    w.rand_val = 6
    w.pick_val = 3
    w.fac(1, owner=1, level=0)
    w.cur = 0
    w.run_upgrade(FAC_LO + 1)
    case("cur=0（who=1 ⇒ 真人）⇒ 種類 3（选单）", (w.fac_f(1, F_TYPE), w.rand_calls()),
         (3, 0))
    w.reset_state()
    w.who = [1, 2, 1, 1]
    w.rand_val = 6
    w.pick_val = 3
    w.fac(1, owner=1, level=0)
    w.cur = 1
    w.run_upgrade(FAC_LO + 1)
    case("cur=1（who=2 ⇒ 電腦）且 owner(1) != cur+1(2) ⇒ 種類 0、不掷 rand",
         (w.fac_f(1, F_TYPE), w.rand_calls()), (0, 0))
    w.reset_state()
    w.who = [1, 2, 1, 1]
    w.rand_val = 6
    w.fac(1, owner=2, level=0)
    w.cur = 1
    w.run_upgrade(FAC_LO + 1)
    case("cur=1 且 owner(2) == cur+1(2) ⇒ 種類 = 6%4+1 = 3、rand 1 次",
         (w.fac_f(1, F_TYPE), w.rand_calls()), (3, 1))

    say("\n[B7] 返回值形态：成功 bit0、剛好到 5 級 bit7；集合 = {0,1,0x81}")
    seen = set()
    for tp, lv in ((0, 0), (0, 4), (0, 5), (1, 0), (2, 0)):
        w.reset_state()
        w.land(1, level=lv, type=tp)
        w.run_upgrade(LAND_LO + 1)
        seen.add(w.ret)
    for tp, lv in ((1, 2), (1, 4), (0, 1), (3, 1)):
        w.reset_state()
        w.fac(1, level=lv, type=tp)
        w.run_upgrade(FAC_LO + 1)
        seen.add(w.ret)
    w.reset_state()
    w.who = [2, 1, 1, 1]
    w.rand_val = 5
    w.fac(1, owner=1, level=0)
    w.run_upgrade(FAC_LO + 1)
    seen.add(w.ret)
    case("★ 返回值集合恰为 {0,1,0x81}", sorted(seen), [0, 1, 0x81])
    case("★ 旁证：走了 0x40b1c5（rand 调用点）", w.hits.get(0x40B1C5, 0) > 0, True)


# ============================================================================
#  [C]  0x004294d5 —— update_commercial_owner(player, stock)
# ============================================================================
def group_c(w):
    say("\n" + "=" * 78)
    say("[C] 0x4294d5(player, stock) —— 企业持股名次重排 / 老闆易主（277 B，整支驱动）")
    say("=" * 78)

    say("\n[C1] 前置闸门：stock 的 +0x04（1 基企業序号）== 0 ⇒ 直接返回 0，一个字节都不写")
    w.reset_state()
    w.stock_company(0, 0)
    w.com(1, owner=1, ranking=(1, 2, 3, 4), assets=12345)
    w.hold(0, 0, 500)
    w.run_reown(0, 0)
    case("n == 0 ⇒ 返回 0", w.ret, 0)
    case("  ★ 企業记录零写", w.diff_com(1), ())
    case("  ★ 不刷新", w.refresh_calls(), 0)
    case("  ★ 不掷 rand", w.rand_calls(), 0)

    say("\n[C2] 摘下：把 player+1 从 4 槽名次表里删掉（後面的前移、末槽清零）")
    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 3, 4))
    w.run_reown(1, 0)                       # player=1 ⇒ code 2，在槽 1
    case("名次表 [1,2,3,4] 去掉 2 ⇒ [1,3,4,0]", w.com_rank(1), (1, 3, 4, 0))
    case("  ★ 精确写点 = {+0x1d,+0x1e,+0x1f}", w.diff_com(1),
         ("+0x1d", "+0x1e", "+0x1f"))
    case("  mine == 0 ⇒ 不插回，老闆 = 1（未变）⇒ 返回 0", w.ret, 0)
    case("  ★★ 名次变了但老闆没变 ⇒ **不刷新**", w.refresh_calls(), 0)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 3, 4))
    w.run_reown(0, 0)                       # code 1 在槽 0
    case("去掉槽 0 的 1 ⇒ [2,3,4,0]", w.com_rank(1), (2, 3, 4, 0))
    case("  ★★ 老闆 1→2 ⇒ 返回 1、+0x18 = 2", (w.ret, w.com_owner(1)), (1, 2))
    case("  ★ 刷新一次、实参 0", (w.refresh_calls(), w.refresh_arg()), (1, 0))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 3, 4))
    w.run_reown(3, 0)                       # code 4 在槽 3 ⇒ memmove 长度 0
    case("去掉末槽的 4 ⇒ [1,2,3,0]", w.com_rank(1), (1, 2, 3, 0))
    case("  ★ 精确写点 = {+0x1f}（memmove 长度 0，只靠末槽清零）", w.diff_com(1), ("+0x1f",))
    case("  老闆未变 ⇒ 返回 0", w.ret, 0)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(2, 1, 2, 0))
    w.run_reown(1, 0)                       # code 2 出现两次（槽 0 与槽 2）
    case("★ 重复项只摘**第一个**匹配 ⇒ [1,2,0,0]", w.com_rank(1), (1, 2, 0, 0))
    case("  老闆 1→1 ⇒ 返回 0", w.ret, 0)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 3, 4))
    w.run_reown(2, 0)                       # code 3 不在？在槽 2
    case("去掉槽 2 的 3 ⇒ [1,2,4,0]", w.com_rank(1), (1, 2, 4, 0))

    say("\n[C3] 插回：按**持股降序**排（从倒数第二槽往前找插入点，严格 `<` 才算「比我少」）")
    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 100)
    w.hold(1, 0, 500)
    w.run_reown(1, 0)
    case("★ 500 > 100 ⇒ [2,1,0,0]", w.com_rank(1), (2, 1, 0, 0))
    case("  ★★ 老闆易主 ⇒ 返回 1、+0x18 = 2", (w.ret, w.com_owner(1)), (1, 2))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 500)
    w.hold(1, 0, 100)
    w.run_reown(1, 0)
    case("★ 100 < 500 ⇒ 插在他後面 [1,2,0,0]", w.com_rank(1), (1, 2, 0, 0))
    case("  ★★ 名次表被改写了却返回 0（老闆没变）", (w.ret, w.refresh_calls()), (0, 0))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 100)
    w.hold(1, 0, 100)
    w.run_reown(1, 0)
    case("★★ 同持股 ⇒ **严格 <** 不成立 ⇒ 插在他後面 [1,2,0,0]（若写成 <= 会是 [2,1,…]）",
         w.com_rank(1), (1, 2, 0, 0))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 0, 0))
    w.hold(0, 0, 900)
    w.hold(1, 0, 500)
    w.hold(2, 0, 700)
    w.run_reown(2, 0)
    case("★ 700 > 500 但 < 900：插到中间 ⇒ [1,3,2,0]", w.com_rank(1), (1, 3, 2, 0))
    case("  老闆未变 ⇒ 返回 0", w.ret, 0)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 3, 4))
    w.hold(0, 0, 400)
    w.hold(1, 0, 1000)
    w.hold(2, 0, 200)
    w.hold(3, 0, 100)
    w.run_reown(1, 0)
    case("★★ 4 槽满时插到榜首 ⇒ [2,1,3,4]（第 5 名被挤出表外）", w.com_rank(1), (2, 1, 3, 4))
    case("  老闆 1→2 ⇒ 返回 1", (w.ret, w.com_owner(1)), (1, 2))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 0, 0))
    w.hold(0, 0, 100)
    w.hold(1, 0, 50)
    w.hold(2, 0, 900)
    w.run_reown(2, 0)
    case("★ 比所有人都大 ⇒ [3,1,2,0]", w.com_rank(1), (3, 1, 2, 0))
    case("  ★★ 老闆 1→3 ⇒ 返回 1", (w.ret, w.com_owner(1)), (1, 3))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 0, 0))
    w.hold(0, 0, 900)
    w.hold(1, 0, 500)
    w.hold(2, 0, 10)
    w.run_reown(2, 0)
    case("★ 比所有人都小 ⇒ [1,2,3,0]", w.com_rank(1), (1, 2, 3, 0))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 3, 4))
    w.hold(0, 0, 900)
    w.hold(2, 0, 900)
    w.hold(3, 0, 900)
    w.hold(1, 0, 50)
    w.run_reown(1, 0)
    case("★★ 名次表有洞 [1,0,3,4] ⇒ 洞被「跳过」，插入位 3 **覆盖**掉 4 ⇒ [1,0,3,2]",
         w.com_rank(1), (1, 0, 3, 2))

    say("\n[C4] 持股为 0 ⇒ 只摘不插；名次表全空 ⇒ 老闆变 0（企业变无主）")
    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 2, 0, 0))
    w.hold(0, 0, 0)
    w.hold(1, 0, 500)
    w.run_reown(0, 0)
    case("★ 賣光的原老闆被摘掉、不插回 ⇒ [2,0,0,0]", w.com_rank(1), (2, 0, 0, 0))
    case("  ★★ 老闆 1→2 ⇒ 返回 1", (w.ret, w.com_owner(1)), (1, 2))
    case("  mine == 0 ⇒ 名次表里没有 code 1", 1 in w.com_rank(1), False)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 0)
    w.run_reown(0, 0)
    case("★ 唯一股東賣光 ⇒ 名次表全 0", w.com_rank(1), (0, 0, 0, 0))
    case("  ★★ 老闆 1→0（無主）⇒ 返回 1、+0x18 = 0", (w.ret, w.com_owner(1)), (1, 0))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=0, ranking=(0, 0, 0, 0))
    w.hold(3, 0, 0)
    w.run_reown(3, 0)
    case("★ 本来就无主、持股也 0 ⇒ 返回 0、名次表仍全 0",
         (w.ret, w.com_rank(1), w.com_owner(1)), (0, (0, 0, 0, 0), 0))

    say("\n[C5] 精确写点：只动 +0x18 与 +0x1c..+0x1f；其余字段（含 +0x19/+0x24）零写")
    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, stock=0, owner=1, ranking=(1, 0, 0, 0), assets=0x0BADF00D)
    w.hold(0, 0, 100)
    w.hold(1, 0, 900)
    w.run_reown(1, 0)
    case("★ 精确写点 = {+0x18,+0x1c,+0x1d}", w.diff_com(1), ("+0x18", "+0x1c", "+0x1d"))
    case("  +0x19（对应股票行号）不动", w.com_f(1, C_STOCK), 0)
    case("  +0x24（資產額）不动", w.emu.readu32(COMS + 1 * COM_STRIDE + C_ASSETS), 0x0BADF00D)
    case("  名字段（+0x04 起）不动", w.read_com(1)[0x04:0x0D], NAME[:9])
    case("  ★ 全程不掷 rand", w.rand_calls(), 0)

    say("\n[C6] 企業表指针 / 序号：n 是 **1 基**、步长 **0x34**")
    w.reset_state()
    w.stock_company(0, 2)
    w.com(1, owner=5, ranking=(1, 2, 3, 4))
    w.com(2, owner=1, ranking=(1, 0, 0, 0))
    w.hold(1, 0, 700)
    w.run_reown(1, 0)
    case("★ n=2 ⇒ 动的是 2 号企業记录（code 2 插到榜首）", w.com_rank(2), (2, 1, 0, 0))
    case("  ★ 1 号记录零写（证明 *0x34 步长 + 指针基址）", w.diff_com(1), ())

    w.reset_state()
    w.stock_company(5, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(2, 5, 800)
    w.run_reown(2, 5)
    case("★ 读的是 (stock,player) 交叉格：stock=5/player=2 ⇒ code 3 插到榜首",
         w.com_rank(1), (3, 1, 0, 0))
    case("  ★★ 老闆 1→3 ⇒ 返回 1", (w.ret, w.com_owner(1)), (1, 3))

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 900)          # 同一玩家在 stock 0
    w.hold(1, 1, 900)          # 另一支股票
    w.run_reown(1, 0)
    case("★ 持股按 **stock 列**取：stock 0 里 player1 = 0 ⇒ 不插回",
         (w.ret, w.com_rank(1)), (0, (1, 0, 0, 0)))

    say("\n[C7] 旁证（防止插回循环静默退化）")
    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 100)
    w.hold(1, 0, 500)
    w.run_reown(1, 0)
    case("  走了 0x429579（后移支）", w.hits.get(0x429579, 0) > 0, True)
    case("  没走 0x4295ad（break 支）", w.hits.get(0x4295AD, 0), 0)
    case("  走了 0x4295ca（老闆易主 ⇒ 刷新）", w.hits.get(0x4295CA, 0) > 0, True)

    w.reset_state()
    w.stock_company(0, 1)
    w.com(1, owner=1, ranking=(1, 0, 0, 0))
    w.hold(0, 0, 500)
    w.hold(1, 0, 100)
    w.run_reown(1, 0)
    case("  100 < 500 ⇒ 走 0x4295ad（insertAt = k+1 后 break）", w.hits.get(0x4295AD, 0) > 0, True)
    case("  没走 0x4295ca（老闆没变）", w.hits.get(0x4295CA, 0), 0)


# ============================================================================
#  可证伪检查
# ============================================================================
SABOTAGES = {
    "A": (0x40AB76, 0x34, 0x38,
          "0x40ab4a · 地块记录步长 0x34 → 0x38（记录指针错位一格）"),
    "A2": (0x40ABA0, 0x18, 0x19,
           "0x40ab4a · mode 0 的『type == 0?』判据位移 +0x18 → +0x19（改判 owner）"),
    "B": (0x40B12F, 0x34, 0x38,
          "0x40b110 · 地块记录步长 0x34 → 0x38（读到隔壁记录）"),
    "C": (0x42950A, 0x34, 0x38,
          "0x4294d5 · 企業记录步长 0x34 → 0x38（指针算错一格）"),
}


def run_suite(w):
    RESULTS.clear()
    FAILED.clear()
    group_a(w)
    group_b(w)
    group_c(w)
    return sum(RESULTS), len(RESULTS)


def main(argv):
    global QUIET
    if "--falsify" in argv:
        return falsify()
    w = World()
    say("通道 2 差分测试 · 地块/設施改造三支（0x40ab4a / 0x40b110 / 0x4294d5）")
    run_suite(w)
    n, t = sum(RESULTS), len(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n}/{t} 通过")
    if FAILED:
        print("红的断言：")
        for d in FAILED:
            print("  ❌ " + d)
    return 0 if n == t else 1


def falsify():
    global QUIET
    w = World()
    n, t = run_suite(w)
    print(f"基线（未破坏）：{n}/{t} 通过")
    if n != t:
        print("  基线不是全绿 ⇒ 先修测试")
        return 1
    bad = 0
    for key in SABOTAGES:
        va, old, new, desc = SABOTAGES[key]
        QUIET = True
        try:
            ws = World(sabotage=key)
            ns, ts = run_suite(ws)
        finally:
            QUIET = False
        red = ts - ns
        print(f"\n破坏 [{key}] @VA 0x{va:08x}：{desc}")
        print(f"  → 变红 {red}/{ts} 条")
        for d in FAILED[:3]:
            print(f"    · {d}")
        if red == 0:
            print("  ✗ 一条都没红 ⇒ 该组断言不可证伪")
            bad += 1
    print(f"\n可证伪检查：{'全通过' if bad == 0 else f'{bad} 组失败'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
