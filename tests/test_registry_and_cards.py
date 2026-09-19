#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通道 2 差分测试 · **換屋卡助手 `0x0040b4f8`（992 B）＋ 两处 AI 目标判定
`0x0041e8e6`（252 B）/ `0x0041ef26`（273 B）**

真值只有 `Rich4/rich4.exe`。三支都**整支驱动原版机器码**（Unicorn）。
`0x40b4f8` 是**正函数入口**（`push×3 + sub esp,0x38`、`ret` 收尾）⇒ 直接 `call`；
两支 AI 是 `0x475324` 出牌跳表的成员（**无 `call` 调用者**，建图工具不收）
⇒ 用 `rich4-remake/tools/disasm.py va <地址>` 按需反汇编（§7.132(1)）。

===========================================================================
[A] `0x0040b4f8`（992 B）· 换屋卡（5）「交换两处房产的房子」助手
===========================================================================
复刻侧：
  · `cards/turn-and-house.ts:174` `applySwapHouseCard`      —— `@source` 地块尾段 `0x40b6c5`
  · `cards/turn-and-house.ts:208` `applySwapHouseFacilityCard` —— `@source` 設施尾段 `0x40b880`
  · 调用点 `cards/registry.ts:836`（地块）/ `registry.ts:824`（設施）
调用者 `0x00442c94`（`push 选中 / push 脚下 / call 0x40b4f8`）
⇒ **arg1 = 脚下那一格的格值，arg2 = 玩家选中的格值**。

### 语义（992 B 逐条读完；边界 `0x40b8d7 ret`）
```
0x40b4f8(arg1 /*脚下*/, arg2 /*选中*/):            ; cdecl 2 参
    if (0x7d0 < arg1 < 0xfa0) {                    ; ★ 地块支（两端都是**开**区间）
        rec1 = [0x498e84] + (arg1-0x7d0)*0x34      ; 地块步长 0x34
        rec2 = [0x498e84] + (arg2-0x7d0)*0x34      ; ★ arg2 **不做**范围检查
    } else {                                       ; ★ 其余**一律**走設施支（无第二判据）
        rec1 = [0x498e88] + (arg1-0xfa0)*0x38      ; 設施步长 0x38
        rec2 = [0x498e88] + (arg2-0xfa0)*0x38
    }
    ; ── 表现层：算「两图标连线」的帧数，逐帧插值 +0x00/+0x02，最后还原
    frame = trunc( sqrt(dx*dx + dy*dy) * f32[0x4631d8] + 1 )   ; f32[0x4631d8] = 0.0625
    for (k = 0; k < frame; k++) {
        插值写 rec1/rec2 的 +0x00/+0x02
        0x41d476(0, 0, 1)                                    ; 刷新（表现层）
        t1 = timeGetTime()
        if (t1 - t0 < 0x18) 0x45285e(0x18 - (t1-t0))         ; 帧内节流
    }
    rec1/+0x00,+0x02 = 原值; rec2/+0x00,+0x02 = 原值          ; 0x40b6a7 / 0x40b880
    ; ── 规则（唯一实质效果）：交换 level(+0x1a) 与 type(+0x18)；**owner(+0x19) 不动**
    swap(rec1[0x1a], rec2[0x1a]); swap(rec1[0x18], rec2[0x18])
    0x41d476(0, 0, 1); 0x45285e(0x1f4)                        ; 收尾（表现层）
    ret                                                        ; ★ 本函数不设返回值
```
- **4 个 `call`**：`0x4582bc`(sqrt) / `0x457dbc`(trunc) / `0x41d476`(刷新) / `0x45285e`(等待)
  ＋ 一处 `call dword cs:[0x46246c]`（IAT thunk → `WINMM!timeGetTime`）。
- **3 次全局读**：`[0x498e84]`、`[0x498e88]`、`[0x4631d8]`（逐条核过，没有别的表读）。
- 它**不碰** `+0x42`（本月倒楣天數）、不碰地契/tenure、**不碰 owner**、不查防御卡。
- `arg1 == arg2` 只是自交换（助手内**无守卫**）——「不能选自己脚下那格」的闸在**调用者**
  （`registry.ts:816` 的 `fac.id === here.id`；原版 `0x00446427 cmp ecx,ebx / je 拒绝`）。

### ★ 关键结构：`0x7d0/0xfa0` 判定**只作用于 arg1**
两条 `cmp … jle/jge 0x40b6e2` 只看 `[esp+0x48]`（= arg1）；arg2 直接按**同一支**的基址与
步长换算。⇒ arg1 落到設施支而 arg2 仍是「地块式」编号时，会去算設施表里一个**负下标**
（`0x40b6e2 sub eax,0xfa0` 无守卫）。本测试用 `FACS = LANDS + 0x7d0*0x38`
让「設施 −2000 号」**恰好等于**地块 0 号，从而把 `arg1 == 0x7d0` 的分支归属
做成**可观测**的断言（[A5]）。

### 打桩清单（本文件 [A] 段全部桩）
| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0041d476` | 重绘/刷新（内部走 Win32 绘制链） | `mov eax,[slot]; inc eax; mov [slot],eax; ret`（**计数**） | 纯表现层；本测试只用它**数帧数** |
| `0x0045285e` | 帧间等待（内部 `timeGetTime` + 消息等待） | 计数桩 + `mov eax,0x1234; ret` | 纯表现层；`0x1234` 用来钉「本函数没有自己的返回码」 |
| `[0x0046246c]` | IAT thunk → `WINMM!timeGetTime` | 数据槽桩 `mov eax,[TS]; add eax,[INC]; mov [TS],eax; ret` | 静态镜像里该槽 = `0x62c90`（**未映射**，一 call 就崩）⇒ 必须换掉；`INC` 控制「时间是否前进」以驱动节流支 |
| `0x004582bc` | `sqrt`（`fsqrt`；负输入支走 `0x459c51`） | **真跑** | 所有用例的坐标差都保证 `dx²+dy² ≥ 0`（且不溢出 int32） |
| `0x00457dbc` | `trunc`（`frndint` + 控制字 RC=截断） | **真跑** | 帧数公式的取整必须用真身 |

⚠️ 假表铺在 **DGROUP**（`LANDS=0x465000`、`FACS=LANDS+0x1b580`）：`Emu.call()` 每次先
`reset()` 把 DGROUP/.bss 还原成原版快照，所以**用例之间天然隔离**，不必手工清零
（`verification.md` 工具边界第 3 条讲的是 SCRATCH 区，这里刻意避开它）。

### 与复刻的对照结论 —— **MATCH**
| # | 规则 | 原版 @source | 复刻 file:line | 裁决 |
|---|---|---|---|---|
| 1 | 交换 `+0x1a`(level) | `0x40b6c5`／`0x40b89e` | `turn-and-house.ts:185,186`（`:219,220`） | MATCH |
| 2 | 交换 `+0x18`(type) | `0x40b6d1`–`0x40b6da`／`0x40b8aa`–`0x40b8b3` | 同上 `type: b.type` / `type: a.type` | MATCH |
| 3 | **不**动 `+0x19`(owner) | 全函数无 `+0x19` 写点（本测试逐字节证） | 无 owner 写点 | MATCH |
| 4 | 其余字节不动 | 只 4 个字节写点 | `{...l, level, type}` 不改别的 | MATCH |
| 5 | 地块/設施表步长 `0x34`/`0x38`、基址 `[0x498e84]`/`[0x498e88]` | `0x40b51d`/`0x40b6ef` | `loaders/map.ts` 的 `LAND_SIZE`/`FACILITY_SIZE` | MATCH |
| 6 | 判定**只看 arg1**（`0x7d0 < arg1 < 0xfa0`，区间两端开） | `0x40b502`–`0x40b512` | `registry.ts:824,836` 按 `target.kind` 分派（选择器已保证同类） | MATCH |
| 7 | 动画（`+0x00/+0x02` 插值、帧数、24ms 节流、收尾 500ms） | `0x40b537`–`0x40b8c9` | **core 有意不复刻**（`turn-and-house.ts:152` 注） | MATCH（净状态效果为 0，本测试证坐标被还原） |
| 8 | `arg1 == arg2` / 记录不存在 | 无守卫（自交换/写到越界处） | `ok:false` 早退（`:181-183`） | MATCH（**不可达**：调用者 `registry.ts:816` 已拒「选自己脚下」；`landIdA===landIdB` 故 `ok:false` 与「无效果」同结论） |
| 9 | 返回值 | 无自己的返回码（= `0x45285e` 的 eax） | `{ok}` 结构体 | MATCH（调用者两版都不读助手的返回值选分支） |
| 10 | `+0x42`（本月倒楣天數）/ 地契 tenure | **完全不碰** | 不碰 | MATCH（本测试逐字节证 +0x17/+0x1b/+0x1c 哨兵未动） |

**玩家可见后果**：两版都是「两处房产的房子（等级＋种类）互换、归属不变」，无差别。

===========================================================================
[B] `0x0041e8e6`（252 B）·「这块地值不值得从对手手里拿」（購地卡 AI 的判据）
===========================================================================
复刻侧 `ai/card-policy.ts:265` 的 `worthTaking(view, enemy, ent)`
（文档注释 `@source 0x0041e8e6(enemy, code)`；调用点 `:349` 購地卡 `godi`）。
原版调用者 `0x41e9e2`：`hated = 0x40d2d3(cur)` → `0x41e8e6(hated, 格值)`
⇒ **arg1 = enemy（0 基，−1 = 没有），arg2 = 格值**。

### 语义（252 B，边界 `0x41e9e1 ret`）
```
0x41e8e6(enemy, code):
    if (enemy == -1) return 0                       ; 0x41e8f0
    if (0x7d0 < code < 0xfa0) {                     ; 地块支（两端开）
        L = land[code-0x7d0]                        ; 步长 0x34
        if (L.owner == 0 || L.owner == cur+1 || L.level == 0) goto ENEMY
        for (i = 1; i <= [0x498e98] /*num_lands*/; i++)     ; ★ 从 1 起（跳过 0 号记录）
            if (strcmp(L.name /*+0x04*/, land[i].name) != 0) continue
            if (land[i].owner == cur+1) return 1    ; ★ 同街有我的 ⇒ 值
    ENEMY:
        return (L.owner == enemy+1 && L.level >= 2)
    }
    if (0xfa0 < code < 0x1770) {                    ; 設施支（两端开）
        F = fac[code-0xfa0]                         ; 步长 0x38
        return (F.owner != 0 && F.owner != cur+1 && F.level != 0)
    }
    return 0                                        ; 企业/景观/越界一律 0
```
★ 同街判据是**真 `strcmp`(`0x458370`)**，只比名字（`+0x04`），**不比 type**
（复刻侧 `sameStreet` 就是 `a.name === b.name`，`ai/card-policy.ts:167`）。
★ 同街扫描**从下标 1 起**、上界 = `[0x498e98]` —— 复刻的 `lands` 数组 id 也**从 1 起**
（`loaders/map.ts:558` 的 `for (let i = 1; i <= numLands; i++)`），所以「跳过 0 号记录」
这一格**两边口径一致**（[B5] 把原版这一条钉住；同族坑见 §7.138(3) 第 4 条）。
★ 設施支**完全不看 enemy**（除了函数开头那一道 `enemy == -1`）。
★ 本函数原版有**两处调用点**（字节级 `gen/rel32-calls.json`）：卡 3 購地卡 `0x41ea1b`、
卡 4 換地卡 `0x41ecc1`，**两处实参序一致**（`push 格值` / `push hated`）；复刻
`worthTaking` 有 3 个调用点（`:323` / `:349` / `:360`），其中 `:349`+`:360` 是卡 4 的
地块/設施两条（原版同在一个循环体里、共用一次 `call`）。
全函数**只有一次 `call`**、**不摇随机数**、**不写任何全局** ⇒ 纯函数，零桩。

### 打桩清单
| VA | 原用途 | 桩 |
|---|---|---|
| （无） | —— | **零桩**：`0x458370`（strcmp）真跑；不摇 `rand`、无 I/O |

### 与复刻的对照结论 —— **MATCH**（逐条）
| # | 规则 | 原版 @source | 复刻 file:line | 裁决 |
|---|---|---|---|---|
| 1 | `enemy == −1` ⇒ 不值 | `0x41e8f0` | `:266` `if (enemy === -1) return false` | MATCH |
| 2 | 地块域 `2000 < code < 4000`（两端开） | `0x41e8fe`–`0x41e90e` | `ent.kind === 'land'`（`map.ts:488` 同区间） | MATCH |
| 3 | `owner == 0` / `owner == cur+1` / `level == 0` ⇒ 不值 | `0x41e928`–`0x41e93e` | `:270` | MATCH（★ 控制流不同：原版跳到 enemy 判定、复刻直接 `return false`；两者结论都 false） |
| 4 | 同街：`strcmp(+0x04)` 相等**且** `owner == cur+1` ⇒ 值 | `0x41e940`–`0x41e978` | `:271` + `sameStreet`（`:167`） | MATCH |
| 5 | 否则 `owner == enemy+1 && level >= 2` | `0x41e97e`–`0x41e992` | `:272` | MATCH |
| 6 | 同街扫描 `i = 1..[0x498e98]` | `0x41e940`,`0x41e948` | `view.lands`（id 从 1 起，`map.ts:558`） | MATCH |
| 7 | 設施域 `4000 < code < 6000`；`owner∉{0,我} && level≠0` | `0x41e994`–`0x41e9d4` | `:274-276` | MATCH |
| 8 | 企业/景观/越界 ⇒ 0 | `0x41e994`/`0x41e99b`/`0x41e9db` | `:278` `return false` | MATCH |

**玩家可见后果**：AI 判「这块地值不值得从对手手里拿」的门槛与两版完全一致
（1 基 owner / 0 基 hated 的换算也对）；无差别。

===========================================================================
[C] `0x0041ef26`（273 B）· 拍賣卡（8）AI「脚下那块值不值得拍」
===========================================================================
复刻侧 `ai/card-policy.ts:405` 的 `paimai`（`@source 0x0041ef26`）。
**无参数**（全走全局），**无 `call` 调用者**（跳表成员）。

### 语义（273 B，边界 `0x41f036 ret`）
```
0x41ef26():
    best  = 0
    ref   = word[ node_table([0x498e80]) + word[player[cur]+0x0c]*0x28 + 0x20 ]
    hated = 0x40d2d3(cur)                           ; 真跑（0 基；无则 −1）
    if (0x7d0 < ref < 0xfa0) {                      ; 脚下是地块
        L = land[ref-0x7d0]
        if (L.owner != 0 && L.owner != cur+1 && L.level >= 3) → 1
        if (L.owner == hated+1 && L.level >= 2) → 1
        → 0
    }
    if (0xfa0 < ref < 0x1770) {                     ; 脚下是設施
        F = fac[ref-0xfa0]                          ; ★ 骨架与地块支**完全同形**
        if (F.owner != 0 && F.owner != cur+1 && F.level >= 3) → 1
        if (F.owner == hated+1 && F.level >= 2) → 1
        → 0
    }
    → 0                                             ; 企业/景观/空格一律 0
```
★ 一个全局都不写（`0x48be58` 不在其中）；返回值 = `ebx` ∈ {0,1}。

### 打桩清单
| VA | 原用途 | 桩 |
|---|---|---|
| （无） | —— | **零桩**：`0x40d2d3`（最恨的人）**真跑**（其语义已由 `test_rebuild_card_ai.py` 独立钉过） |

### 与复刻的对照结论 —— **MATCH**（逐条）
| # | 规则 | 原版 @source | 复刻 file:line | 裁决 |
|---|---|---|---|---|
| 1 | `ref ← word[node[player+0x0c].+0x20]` | `0x41ef2a`–`0x41ef4c` | `hereOf` → `nodeOf(topo, me.nodeId)`（`:253-260`） | MATCH（`+0x0c` = `nodeId`，`save.ts:573`） |
| 2 | 地块域 `2000 < ref < 4000`（两端开） | `0x41ef63`–`0x41ef71` | `here.kind === 'land'`（`map.ts:488` 同区间） | MATCH |
| 3 | `owner == 0` 或 `owner == cur+1` ⇒ 不用 | `0x41ef83`–`0x41ef97` | `:409` | MATCH |
| 4 | 对手且 `level >= 3` ⇒ 用 | `0x41ef99`–`0x41ef9d` | `:410` | MATCH |
| 5 | 否则 `owner == hated+1 && level >= 2` ⇒ 用 | `0x41efab`–`0x41efcc` | `:411` | MATCH |
| 6 | 設施支与地块支**同形**（无等级非对称） | `0x41efd1`–`0x41f027` | `:408-411`（两支共用同一个 `e`） | MATCH |
| 7 | 企业（≥6000）/景观/空格 ⇒ 不用 | `0x41efd1`/`0x41efd9`/`0x41f032` | `here.kind==='commercial'` ⇒ `e===undefined` ⇒ `null` | MATCH |
| 8 | 不写任何全局（`0x48be58` 未出现） | 全函数无写点（本测试钉住） | 返回 `NONE`（目标由调用侧「脚下」隐式确定） | MATCH |

**玩家可见后果**：AI 只在「脚下是别人的 ≥3 级房产，或最恨之人的 ≥2 级房产」时才肯出拍賣卡；
两版判据一致，无差别。

===========================================================================
★ 测试台的坑（本文件踩到并处理）
===========================================================================
`Emu.call()` 每次都 `mu.hook_add(UC_HOOK_CODE, self._hook)` 且**从不删除** ⇒ 第 k 次调用时
`insn_count` 被**放大 k 倍**，长循环会被 `MAX_INSN` **假停**。实测：dx=5000 的 313 帧动画在
同一实例的第 14 次调用上只跑了 **177** 帧，现象酷似「帧数公式读错了」。
本文件的做法：**每个用例新建一个 `Emu`**（实测 1 ms 量级），于是每次只有一个 hook。

跑法：cd rich4-spec && .venv/bin/python tests/test_registry_and_cards.py
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import STUB_BASE, SCRATCH_BASE, Emu  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402

# ── [A] 0x40b4f8 ────────────────────────────────────────────────────────
SWAP_HOUSES = 0x40B4F8
A_REFRESH = 0x41D476
A_SLEEP = 0x45285E
A_TIMEGET_THUNK = 0x46246C
A_FRAME_FACTOR = 0x4631D8          # f32 = 0.0625

LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NODE_TABLE_PTR = 0x498E80
NUM_LANDS = 0x498E98

LAND_STRIDE = 0x34
FAC_STRIDE = 0x38
NODE_STRIDE = 0x28
NODE_REF = 0x20

OFF_X, OFF_Y = 0x00, 0x02
OFF_NAME = 0x04
OFF_TYPE, OFF_OWNER, OFF_LEVEL = 0x18, 0x19, 0x1A

LAND_MARK = 0x7D0                  # 格值：地块 = 2000 + id
FAC_MARK = 0xFA0                   # 格值：設施 = 4000 + id
COMM_MARK = 0x1770                 # 格值：企业 = 6000 + id

# 假表铺在 DGROUP（reset() 会还原 ⇒ 用例天然隔离）。
# FACS 特意取成「設施 −2000 号 ≡ LANDS + 0」，使 arg1 == 0x7d0 的分支归属可观测。
LANDS_A = 0x465000
FACS_A = LANDS_A + LAND_MARK * FAC_STRIDE          # = 0x480580

A_TIME_STUB = STUB_BASE + 0x300
A_REFRESH_CNT = SCRATCH_BASE + 0x10
A_SLEEP_CNT = SCRATCH_BASE + 0x20
A_TIME_SLOT = SCRATCH_BASE + 0x30
A_TIME_INC = SCRATCH_BASE + 0x40
A_SLEEP_RET = 0x1234               # 等待桩的返回值：用来钉「本函数没有自己的返回码」

# ── [B] 0x41e8e6 / [C] 0x41ef26 ─────────────────────────────────────────
WORTH_TAKING = 0x41E8E6
PAIMAI_AI = 0x41EF26

CUR = 0x49910C
NUM_PLAYERS = 0x499114
CARD_PARAM = 0x48BE58              # 「本张卡的参数字」全局（[B]/[C] 都**不该**写它）
CARD_ARG = 0x48BE5C

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_ALIVE = 0x0C, 0x15
P_HOSTILITY, HOSTILITY_STRIDE = 0x4C, 4

# [B]/[C] 的假表也铺在 DGROUP（无别名要求，故另选基址）
LANDS_BC = 0x464000
FACS_BC = 0x466000
NODES_BC = 0x46C000

SENTINEL = 0x5A5A5A5A
RESULTS = []
SECTIONS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<72} 实际 {got!s:<26} 期望 {want!s}")
    return ok


def f32_at(emu, va):
    return struct.unpack("<f", emu.read(va, 4))[0]


# ══════════════════════════════════════════════════════════════════════════
#  [A] 0x40b4f8
# ══════════════════════════════════════════════════════════════════════════
class SwapWorld:
    """每次 `run()` 新建一个 `Emu`（见文件头「测试台的坑」）。

    地块/設施记录用**完整 0x34 / 0x38 字节模式**注入：+0x17/+0x1b/+0x1c 放哨兵，
    于是「到底改了哪几个字节」成为可证伪的断言。
    """

    def __init__(self):
        self.clear()

    def clear(self):
        self.lands = {}            # idx → (x, y, type, owner, level, name)
        self.facs = {}
        self.arg1 = LAND_MARK + 1
        self.arg2 = LAND_MARK + 2
        self.tick = 0x18           # 每次 timeGetTime 前进的毫秒数（≥0x18 ⇒ 循环内跳过等待）
        self.lands_base = LANDS_A
        self.facs_base = FACS_A
        # 结果
        self.ret = self.refresh = self.sleep = self.insns = self.esp_delta = None
        self.seq = None
        self.emu = None

    def land(self, idx, x=0, y=0, typ=0, owner=0, level=0, name=None):
        self.lands[idx] = (x, y, typ, owner, level, name if name is not None else f"L{idx:04d}")
        return self

    def fac(self, idx, x=0, y=0, typ=0, owner=0, level=0, name=None):
        self.facs[idx] = (x, y, typ, owner, level, name if name is not None else f"F{idx:04d}")
        return self

    # ── 记录编码 / 解码 ────────────────────────────────────────────────
    @staticmethod
    def rec_bytes(stride, x, y, typ, owner, level, name):
        b = bytearray(b"\x00" * stride)
        struct.pack_into("<hh", b, OFF_X, x, y)
        b[OFF_NAME:OFF_NAME + len(name)] = name.encode()
        b[0x17] = 0xCD                      # 哨兵（level 前一个字节）
        b[OFF_TYPE] = typ
        b[OFF_OWNER] = owner
        b[OFF_LEVEL] = level
        b[0x1B] = 0xAB                      # 哨兵（level 后一个字节）
        b[0x1C] = 0xEF                      # 哨兵
        return bytes(b)

    def land_bytes(self, idx):
        x, y, t, o, lv, nm = self.lands[idx]
        return self.rec_bytes(LAND_STRIDE, x, y, t, o, lv, nm)

    def fac_bytes(self, idx):
        x, y, t, o, lv, nm = self.facs[idx]
        return self.rec_bytes(FAC_STRIDE, x, y, t, o, lv, nm)

    def expect_land(self, idx, **over):
        x, y, t, o, lv, nm = self.lands[idx]
        g = dict(x=x, y=y, typ=t, owner=o, level=lv, name=nm)
        g.update(over)
        return self.rec_bytes(LAND_STRIDE, **g)

    def expect_fac(self, idx, **over):
        x, y, t, o, lv, nm = self.facs[idx]
        g = dict(x=x, y=y, typ=t, owner=o, level=lv, name=nm)
        g.update(over)
        return self.rec_bytes(FAC_STRIDE, **g)

    def after_land(self, idx):
        return self.emu.read(self.lands_base + idx * LAND_STRIDE, LAND_STRIDE)

    def after_fac(self, idx):
        return self.emu.read(self.facs_base + idx * FAC_STRIDE, FAC_STRIDE)

    def field(self, addr, off):
        return self.emu.read8(addr + off)

    # ── 跑 ────────────────────────────────────────────────────────────
    def run(self):
        emu = Emu()
        emu.patch(A_REFRESH,
                  b"\xA1" + struct.pack("<I", A_REFRESH_CNT) + b"\x40"
                  + b"\xA3" + struct.pack("<I", A_REFRESH_CNT) + b"\xC3")
        emu.patch(A_SLEEP,
                  b"\xA1" + struct.pack("<I", A_SLEEP_CNT) + b"\x40"
                  + b"\xA3" + struct.pack("<I", A_SLEEP_CNT)
                  + b"\xB8" + struct.pack("<I", A_SLEEP_RET) + b"\xC3")
        emu.patch(A_TIME_STUB,
                  b"\xA1" + struct.pack("<I", A_TIME_SLOT)
                  + b"\x03\x05" + struct.pack("<I", A_TIME_INC)
                  + b"\xA3" + struct.pack("<I", A_TIME_SLOT) + b"\xC3")

        if LAND_MARK < self.arg1 < FAC_MARK:
            rec1 = self.lands_base + (self.arg1 - LAND_MARK) * LAND_STRIDE
            rec2 = self.lands_base + (self.arg2 - LAND_MARK) * LAND_STRIDE
        else:
            rec1 = self.facs_base + (self.arg1 - FAC_MARK) * FAC_STRIDE
            rec2 = self.facs_base + (self.arg2 - FAC_MARK) * FAC_STRIDE
        self.rec1, self.rec2 = rec1, rec2

        seq = []

        def cap(mu, address, size, user):
            seq.append((emu.read16(rec1), emu.read16(rec1 + 2),
                        emu.read16(rec2), emu.read16(rec2 + 2)))

        emu.mu.hook_add(UC_HOOK_CODE, cap, begin=A_SLEEP, end=A_SLEEP)

        def setup(e):
            e.write32(LAND_TABLE_PTR, self.lands_base)
            e.write32(FAC_TABLE_PTR, self.facs_base)
            e.write32(A_TIMEGET_THUNK, A_TIME_STUB)
            e.write32(A_REFRESH_CNT, 0)
            e.write32(A_SLEEP_CNT, 0)
            e.write32(A_TIME_SLOT, 0)
            e.write32(A_TIME_INC, self.tick & 0xFFFFFFFF)
            for idx in self.lands:
                e.write(self.lands_base + idx * LAND_STRIDE, self.land_bytes(idx))
            for idx in self.facs:
                e.write(self.facs_base + idx * FAC_STRIDE, self.fac_bytes(idx))

        r = emu.call(SWAP_HOUSES, [self.arg1, self.arg2], setup=setup)
        self.emu = emu
        self.ret = r["eax"]
        self.insns = r["insns"]
        self.esp_delta = r["esp_delta"]
        self.refresh = emu.readu32(A_REFRESH_CNT)
        self.sleep = emu.readu32(A_SLEEP_CNT)
        self.seq = seq
        return self


def sec_a():
    print("=" * 80)
    print("[A] `0x0040b4f8`（992 B）· 換屋卡助手 —— 整支驱动（sqrt/trunc 真跑）")
    print("=" * 80)
    w = SwapWorld()

    # ── A0. 常量与调用约定 ────────────────────────────────────────────
    print("\n[A0] 常量 / 调用约定 / 返回值语义")
    case("★ f32 @ 0x4631d8 == 0.0625（帧数系数）", f32_at(Emu(), A_FRAME_FACTOR), 0.0625)
    w.clear()
    w.land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("★ 返回值 = 收尾等待桩的 eax ⇒ 本函数**没有自己的返回码**",
         w.ret & 0xFFFFFFFF, A_SLEEP_RET)
    case("  cdecl：callee 不清栈 ⇒ esp_delta == 4（2 个实参留给调用者）", w.esp_delta, 4)

    # ── A1. 地块支：交换 +0x1a 与 +0x18，owner 不动 ───────────────────
    print("\n[A1] 地块支 0x7d0 < arg1 < 0xfa0：交换 level(+0x1a) 与 type(+0x18)")
    w.clear()
    w.land(1, 10, 20, 7, 2, 11).land(2, 30, 40, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("★ 地块 1 号 == 只有 type/level 被换的期望字节串",
         w.after_land(1), w.expect_land(1, typ=9, level=22))
    case("★ 地块 2 号 == 只有 type/level 被换的期望字节串",
         w.after_land(2), w.expect_land(2, typ=7, level=11))
    case("  1 号 owner(+0x19) 仍是 2（房子换、人不换）", w.field(w.rec1, OFF_OWNER), 2)
    case("  2 号 owner 仍是 3", w.field(w.rec2, OFF_OWNER), 3)
    case("  1 号 +0x17 哨兵 0xCD 未动", w.field(w.rec1, 0x17), 0xCD)
    case("  1 号 +0x1b 哨兵 0xAB 未动", w.field(w.rec1, 0x1B), 0xAB)
    case("  1 号 +0x1c 哨兵 0xEF 未动", w.field(w.rec1, 0x1C), 0xEF)
    case("  1 号姓名段 +0x04 未动", w.after_land(1)[OFF_NAME:OFF_NAME + 5], b"L0001")

    # ── A2. 名称/坐标还原；未参与记录一个字节都不动 ──────────────────
    print("\n[A2] 坐标动画后还原；未参与的第 0 号记录逐字节不动")
    w.clear()
    w.land(0, 5, 6, 1, 9, 33, name="ZZZZ").land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("★ 0 号记录（未参与）逐字节等于注入值", w.after_land(0), w.land_bytes(0))
    case("★ 1 号坐标 (+0x00,+0x02) 还原", w.after_land(1)[0:4], w.land_bytes(1)[0:4])
    case("★ 2 号坐标 (+0x00,+0x02) 还原", w.after_land(2)[0:4], w.land_bytes(2)[0:4])

    # ── A3. arg2 无范围检查（地块支里 arg2 = 0x7d0 ⇒ 命中地块 0 号）───
    print("\n[A3] arg2 **不做**范围检查：地块支里 arg2 = 0x7d0 ⇒ 命中地块 0 号")
    w.clear()
    w.land(0, 0, 0, 4, 9, 33).land(1, 0, 0, 7, 2, 11)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK      # arg2 = 2000 ⇒ idx 0
    w.run()
    case("★ 地块 0 号 拿到 arg1 的 (type,level)", w.after_land(0),
         w.expect_land(0, typ=7, level=11))
    case("  地块 1 号 拿到 0 号的 (type,level)", w.after_land(1),
         w.expect_land(1, typ=4, level=33))
    case("  地块 0 号 owner 仍是 9", w.field(w.lands_base, OFF_OWNER), 9)

    # ── A4. 設施支：步长 0x38 ─────────────────────────────────────────
    print("\n[A4] 設施支（arg1 ≥ 0xfa0）：步长 0x38、基址 [0x498e88]；owner 同样不动")
    w.clear()
    w.fac(1, 10, 20, 1, 4, 55).fac(2, 30, 40, 2, 5, 66)
    w.arg1, w.arg2 = FAC_MARK + 1, FAC_MARK + 2
    w.run()
    case("★ 設施 1 号 == 只有 type/level 被换的期望字节串",
         w.after_fac(1), w.expect_fac(1, typ=2, level=66))
    case("★ 設施 2 号 == 只有 type/level 被换的期望字节串",
         w.after_fac(2), w.expect_fac(2, typ=1, level=55))
    case("  1 号 owner 仍是 4", w.field(w.rec1, OFF_OWNER), 4)
    case("  步长是 0x38 不是 0x34（两块互不串位）",
         (w.field(w.rec2, OFF_TYPE), w.field(w.rec2, OFF_OWNER)), (1, 5))
    case("★ 1 号坐标 (+0x00,+0x02) 还原", w.after_fac(1)[0:4], w.fac_bytes(1)[0:4])
    case("★ 2 号坐标 (+0x00,+0x02) 还原", w.after_fac(2)[0:4], w.fac_bytes(2)[0:4])

    # ── A5. 边界：0x7d0 / 0x7d1 / 0xfa0 ──────────────────────────────
    print("\n[A5] ★ 边界判据只作用于 arg1：0x7d0 ⇒ 設施支、0x7d1 ⇒ 地块支、0xfa0 ⇒ 設施支")
    case("  构造前提：FACS − 0x7d0×0x38 == LANDS（别名）",
         (FACS_A - LAND_MARK * FAC_STRIDE, LANDS_A), (LANDS_A, LANDS_A))
    w.clear()
    w.land(0, 0, 0, 4, 1, 33).land(2, 0, 0, 9, 3, 22)      # 0 号 = 「設施 −2000 号」
    w.fac(1, 0, 0, 5, 2, 44)
    w.arg1, w.arg2 = LAND_MARK, FAC_MARK + 1               # arg1 = 2000
    w.run()
    case("★★ arg1 == 0x7d0 ⇒ 走**設施**支（jle）：地块 0 号 那一格 变 (5,44)",
         w.after_land(0), w.expect_land(0, typ=5, level=44))
    case("  同上：地块 0 号 owner 仍是 1", w.field(w.lands_base, OFF_OWNER), 1)
    case("  設施 1 号 拿到 (4,33)", w.after_fac(1), w.expect_fac(1, typ=4, level=33))
    case("★ 地块 2 号**没被碰**（若误判成地块支，会去动 2002 号）",
         w.after_land(2), w.land_bytes(2))

    w.clear()
    w.land(1, 0, 0, 4, 1, 33).land(2, 0, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2          # arg1 = 2001
    w.run()
    case("  地块 1 号 变 (9,22)（arg1 == 0x7d1 确实是地块支）",
         w.after_land(1), w.expect_land(1, typ=9, level=22))

    w.clear()
    w.fac(0, 0, 0, 4, 1, 33).fac(1, 0, 0, 5, 2, 44)
    w.arg1, w.arg2 = FAC_MARK, FAC_MARK + 1                # arg1 = 4000
    w.run()
    case("★ arg1 == 0xfa0 ⇒ 設施表 0 号（jge 跳到設施支）",
         w.after_fac(0), w.expect_fac(0, typ=5, level=44))
    case("  設施 1 号 拿到 (4,33)", w.after_fac(1), w.expect_fac(1, typ=4, level=33))

    w.clear()
    w.land(1999, 0, 0, 4, 1, 33).land(2, 0, 0, 9, 3, 22)
    w.arg1, w.arg2 = 3999, LAND_MARK + 2                   # 上端开区间的内侧
    w.run()
    case("★ arg1 == 3999 ⇒ 地块表 1999 号（地址 = LANDS + 1999×0x34）",
         w.after_land(1999), w.expect_land(1999, typ=9, level=22))

    # ── A5b. arg1 ≥ 0x1770 仍走設施支（无第三条判据）───────────────
    print("\n[A5b] ★ arg1 > 0x1770 仍是設施支（代码里**没有**第三道 cmp）")
    w.clear()
    w.lands_base, w.facs_base = 0x464000, 0x466000
    w.fac(2001, 0, 0, 4, 1, 33).fac(1, 0, 0, 5, 2, 44)
    w.arg1, w.arg2 = 0x1771, FAC_MARK + 1                  # 6001 ⇒ 設施 idx 2001
    w.run()
    case("★ arg1 = 0x1771 ⇒ 設施表 2001 号（企业格值也走設施支）",
         w.after_fac(2001), w.expect_fac(2001, typ=5, level=44))
    w.clear()
    w.lands_base, w.facs_base = 0x464000, 0x466000
    w.fac(35, 0, 0, 4, 1, 33).fac(1, 0, 0, 5, 2, 44)
    w.arg1, w.arg2 = FAC_MARK + 35, FAC_MARK + 1
    w.run()
    case("  arg1 = 0xfa0+35 ⇒ 設施 35 号", w.after_fac(35),
         w.expect_fac(35, typ=5, level=44))

    # ── A6. arg1 == arg2（助手内无守卫）──────────────────────────────
    print("\n[A6] arg1 == arg2：自交换（守卫在调用者 0x446427 / registry.ts:816，不在助手内）")
    w.clear()
    w.land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
    w.arg1 = w.arg2 = LAND_MARK + 1
    w.run()
    case("★ 地块 1 号 逐字节原样", w.after_land(1), w.land_bytes(1))
    case("  地块 2 号 逐字节原样", w.after_land(2), w.land_bytes(2))
    case("  距离 0 ⇒ 帧数 1 ⇒ 刷新 2 次", w.refresh, 2)

    # ── A7. 帧数公式 ─────────────────────────────────────────────────
    print("\n[A7] ★ 帧数 = trunc(sqrt(dx²+dy²) × 0.0625 + 1)（f32[0x4631d8] 真身读入）")
    factor = f32_at(Emu(), A_FRAME_FACTOR)
    for (dx, dy) in ((0, 0), (1, 0), (15, 0), (16, 0), (17, 0), (32, 0), (33, 0),
                     (100, 0), (159, 0), (160, 0), (300, 0), (3, 4), (6, 8)):
        expect_frames = int(math.trunc(math.sqrt(dx * dx + dy * dy) * factor + 1.0))
        w.clear()
        w.tick = 0x18                       # 节流开 ⇒ 循环内不调等待桩
        w.land(1, 0, 0, 7, 2, 11).land(2, dx, dy, 9, 3, 22)
        w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
        w.run()
        case(f"  (dx,dy)=({dx},{dy}) ⇒ 帧数 {expect_frames} ⇒ 刷新 {expect_frames + 1} 次",
             w.refresh, expect_frames + 1)

    # ── A8. 帧内节流支 0x40b689 ──────────────────────────────────────
    print("\n[A8] ★ 帧内节流支（0x40b689 cmp eax,0x18 / jae 0x40b69e）")
    for tick, desc, want_sleep in ((0x18, "时间前进 24ms（恰好达到阈值）", 1),
                                   (0x19, "时间前进 25ms", 1),
                                   (0x17, "时间前进 23ms（差 1ms）", 8),
                                   (0x00, "时间完全不动", 8)):
        w.clear()
        w.tick = tick
        w.land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
        w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
        w.run()
        case(f"  {desc} ⇒ 等待桩调用 {want_sleep} 次（帧数 7）", w.sleep, want_sleep)
    w.clear()
    w.tick = 0x17
    w.land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("  时间不动时 等待次数 == 刷新次数", (w.sleep, w.refresh), (8, 8))

    # ── A9. 逐帧插值序列 ─────────────────────────────────────────────
    print("\n[A9] ★ 逐帧插值 +0x00/+0x02（等待桩入口快照；末条 = 还原后的原值）")
    w.clear()
    w.tick = 0
    w.land(1, 0, 0, 7, 2, 11).land(2, 100, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("★ dx=100、帧数 7 的完整坐标序列 (x1,y1,x2,y2)",
         w.seq,
         [(14, 0, 85, 0), (28, 0, 71, 0), (42, 0, 57, 0), (57, 0, 42, 0),
          (71, 0, 28, 0), (85, 0, 14, 0), (100, 0, 0, 0), (0, 0, 100, 0)])
    case("  序列长度 = 帧数 + 1（多出那条是收尾/还原后）", len(w.seq), 8)

    w.clear()
    w.tick = 0
    w.land(1, 0, 0, 7, 2, 11).land(2, 16, 0, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("  dx=16（帧数 2）的序列", w.seq,
         [(8, 0, 8, 0), (16, 0, 0, 0), (0, 0, 16, 0)])

    w.clear()
    w.tick = 0
    w.land(1, 7, 9, 7, 2, 11).land(2, 7, 9, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("  dist = 0 ⇒ 帧数 1、坐标原地不动", (w.refresh, w.seq),
         (2, [(7, 9, 7, 9), (7, 9, 7, 9)]))

    w.clear()
    w.tick = 0
    w.land(1, 0, 0, 7, 2, 11).land(2, 0, 48, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("  dy=48（帧数 4、只动 y）的序列：x 恒 0、两块 y 相向",
         w.seq,
         [(0, 12, 0, 36), (0, 24, 0, 24), (0, 36, 0, 12), (0, 48, 0, 0), (0, 0, 0, 48)])
    w.clear()
    w.tick = 0
    w.land(1, 0, 0, 7, 2, 11).land(2, 0, 10, 9, 3, 22)
    w.arg1, w.arg2 = LAND_MARK + 1, LAND_MARK + 2
    w.run()
    case("  dy=10 ⇒ 帧数 1（trunc(0.625+1)）⇒ 一步到位后再还原",
         w.seq, [(0, 10, 0, 0), (0, 0, 0, 10)])

    # ── A10. 設施支的动画 ────────────────────────────────────────────
    print("\n[A10] 設施支：坐标同样插值后还原")
    w.clear()
    w.tick = 0
    w.fac(1, 0, 0, 1, 4, 55).fac(2, 40, 30, 2, 5, 66)
    w.arg1, w.arg2 = FAC_MARK + 1, FAC_MARK + 2
    w.run()
    case("  dist=50 ⇒ 帧数 = trunc(3.125+1) = 4 ⇒ 序列长度 5", len(w.seq), 5)
    case("  末条 == 原值（設施坐标还原）", w.seq[-1], (0, 0, 40, 30))
    case("  第一帧朝对方走 (x: 0→10, 40→30)", w.seq[0], (10, 7, 30, 22))

    SECTIONS.append(("[A]", len(RESULTS)))


# ══════════════════════════════════════════════════════════════════════════
#  [B] 0x41e8e6 · [C] 0x41ef26
# ══════════════════════════════════════════════════════════════════════════
class TableWorld:
    """[B]/[C] 共用的世界：铺地块表 / 設施表 / 节点表 + 玩家记录。零桩。"""

    def __init__(self):
        self.clear()

    def clear(self):
        self.cur = 0
        self.num_players = 4
        self.num_lands = 8
        self.hostility = [0, 0, 0, 0]
        self.alive = [1, 1, 1, 1]
        self.lands = {}          # idx → (type, owner, level, name)
        self.facs = {}           # idx → (type, owner, level)
        self.nodes = {}          # idx → ref（[C] 用）
        self.node = 3
        self.ret = None
        self.emu = None
        self.emu_card_param = self.emu_card_arg = None

    def land(self, idx, typ=0, owner=0, level=0, name=None):
        self.lands[idx] = (typ, owner, level, name if name is not None else "SAME")
        return self

    def fac(self, idx, typ=1, owner=0, level=0):
        self.facs[idx] = (typ, owner, level)
        return self

    def node_ref(self, idx, ref):
        self.nodes[idx] = ref
        return self

    def _setup(self, e):
        e.write32(CUR, self.cur)
        e.write32(NUM_PLAYERS, self.num_players)
        e.write32(NUM_LANDS, self.num_lands)
        e.write32(LAND_TABLE_PTR, LANDS_BC)
        e.write32(FAC_TABLE_PTR, FACS_BC)
        e.write32(NODE_TABLE_PTR, NODES_BC)
        e.write32(CARD_PARAM, SENTINEL)
        e.write32(CARD_ARG, SENTINEL)
        for i in range(4):
            pb = PLAYER_BASE + i * PLAYER_STRIDE
            e.write8(pb + P_ALIVE, self.alive[i])
            e.write8(pb + P_NODE, 0)
            for j in range(4):
                e.write32(pb + P_HOSTILITY + j * HOSTILITY_STRIDE, 0)
        pb = PLAYER_BASE + self.cur * PLAYER_STRIDE
        e.write16(pb + P_NODE, self.node)
        for j, h in enumerate(self.hostility):
            e.write32(pb + P_HOSTILITY + j * HOSTILITY_STRIDE, h & 0xFFFFFFFF)
        # ★ 表内容固定 4 字节模式，使「读了哪一条」可证伪
        for idx in range(0, 8):
            e.write32(LANDS_BC + idx * LAND_STRIDE, 0)
            e.write32(FACS_BC + idx * FAC_STRIDE, 0)
        for idx, (typ, owner, level, name) in self.lands.items():
            b = LANDS_BC + idx * LAND_STRIDE
            e.write8(b + OFF_TYPE, typ)
            e.write8(b + OFF_OWNER, owner)
            e.write8(b + OFF_LEVEL, level)
            e.write(b + OFF_NAME, name.encode() + b"\x00")
        for idx, (typ, owner, level) in self.facs.items():
            b = FACS_BC + idx * FAC_STRIDE
            e.write8(b + OFF_TYPE, typ)
            e.write8(b + OFF_OWNER, owner)
            e.write8(b + OFF_LEVEL, level)
        for idx, ref in self.nodes.items():
            e.write16(NODES_BC + idx * NODE_STRIDE + NODE_REF, ref & 0xFFFF)

    def _finish(self, emu, r):
        self.emu = emu
        self.ret = r["eax"]
        self.emu_card_param = emu.readu32(CARD_PARAM)
        self.emu_card_arg = emu.readu32(CARD_ARG)
        return self


class WorthWorld(TableWorld):
    """[B] 0x41e8e6。`call(enemy, code)`。"""

    def call(self, enemy, code):
        emu = Emu()
        r = emu.call(WORTH_TAKING, [enemy & 0xFFFFFFFF, code], setup=self._setup)
        return self._finish(emu, r)


class PaimaiWorld(TableWorld):
    """[C] 0x41ef26。无参数。"""

    def run(self):
        emu = Emu()
        r = emu.call(PAIMAI_AI, [], setup=self._setup)
        return self._finish(emu, r)


def sec_b():
    print("\n" + "=" * 80)
    print("[B] `0x0041e8e6`（252 B）·「这块地值不值得从对手手里拿」—— 零桩，strcmp 真跑")
    print("=" * 80)
    b = WorthWorld()

    # ── B1. enemy == -1 提前返回 ────────────────────────────────────
    print("\n[B1] 第一道闸：enemy == −1 ⇒ 恒 0（哪怕是一块 5 级敌产）")
    b.clear(); b.land(1, owner=3, level=5)
    case("enemy = −1、地块 1 号 3 号玩家 5 级 ⇒ 0", b.call(-1, LAND_MARK + 1).ret, 0)
    b.clear(); b.land(1, owner=3, level=5)
    case("  enemy = 2（0 基）⇒ owner 3 == enemy+1 ⇒ 1",
         b.call(2, LAND_MARK + 1).ret, 1)
    b.clear(); b.fac(1, owner=3, level=1)
    case("  enemy = −1、設施 ⇒ 也是 0", b.call(-1, FAC_MARK + 1).ret, 0)

    # ── B2. 格值区间（两端开）──────────────────────────────────────
    print("\n[B2] 格值区间：地块 0x7d0 < code < 0xfa0、設施 0xfa0 < code < 0x1770（两端开）")
    for code, desc in ((LAND_MARK, "0x7d0（地块 0 号）"), (FAC_MARK, "0xfa0（設施 0 号）"),
                       (COMM_MARK, "0x1770（企业 0 号）"), (0, "0"), (0x2000, "0x2000"),
                       (0xFFFF, "0xffff")):
        b.clear(); b.land(1, owner=3, level=5); b.fac(1, owner=3, level=5)
        b.land(1999, owner=3, level=5)
        case(f"  code = {desc} ⇒ 0", b.call(2, code).ret, 0)
    b.clear(); b.land(1, owner=3, level=2)
    case("  code = 0x7d1（地块 1 号）⇒ 1（下端开）", b.call(2, LAND_MARK + 1).ret, 1)
    b.clear(); b.land(1999, owner=3, level=2)
    case("  code = 0x7d0+1999 = 0xf6f（地块 1999 号）⇒ 1", b.call(2, LAND_MARK + 1999).ret, 1)
    b.clear(); b.fac(1, owner=3, level=1)
    case("  code = 0xfa1（設施 1 号）⇒ 1（下端开）", b.call(2, FAC_MARK + 1).ret, 1)
    b.clear(); b.fac(1999, owner=3, level=1)
    case("  code = 0x176f（設施 1999 号）⇒ 1（上端开）", b.call(2, 0x176F).ret, 1)

    # ── B3. 地块支三道闸 + enemy 判定 ───────────────────────────────
    print("\n[B3] 地块支：owner∈{0,我} 或 level==0 ⇒ 落到 enemy 判定；level ≥ 2 且 owner==enemy+1")
    b.clear(); b.land(1, owner=0, level=5)
    case("owner == 0 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear(); b.land(1, owner=1, level=5)                 # cur=0 ⇒ me+1=1
    case("owner == cur+1（我自己的地）⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear(); b.land(1, owner=3, level=0)
    case("level == 0（空地）⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear(); b.land(1, owner=3, level=1)
    case("owner == enemy+1 但 level == 1 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear(); b.land(1, owner=3, level=2)
    case("★ owner == enemy+1 且 level == 2（边界相等）⇒ 1", b.call(2, LAND_MARK + 1).ret, 1)
    b.clear(); b.land(1, owner=3, level=5)
    case("  level == 5 ⇒ 1", b.call(2, LAND_MARK + 1).ret, 1)
    b.clear(); b.land(1, owner=4, level=5)
    case("  owner == 4（不是最恨的 3 号）且 level 5 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)

    # ── B4. 同街（真 strcmp）支 ─────────────────────────────────────
    print("\n[B4] 同街支：strcmp(名字) 命中且那块是**我的** ⇒ 1（不看 level、不看 enemy）")
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")        # 目标：敌产 1 级
    b.land(2, typ=1, owner=1, level=1, name="AAA")        # 同街、我的、连鎖店(type=1)
    case("★ 同街有我的地 ⇒ 1（type 不同也照样算同街：只比名字）",
         b.call(2, LAND_MARK + 1).ret, 1)
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.land(2, typ=1, owner=1, level=1, name="BBB")
    case("  名字不同 ⇒ 不算同街 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.land(2, typ=0, owner=2, level=1, name="AAA")
    case("  同街但是别人的 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.land(3, typ=0, owner=1, level=1, name="AAA")
    case("  同街的我在 3 号（跨过不同名的 2 号）⇒ 1（扫完整段）",
         b.call(2, LAND_MARK + 1).ret, 1)
    b.clear()
    b.land(1, typ=0, owner=3, level=0, name="AAA")
    b.land(2, typ=0, owner=1, level=1, name="AAA")
    case("★★ 目标是空地(level 0) ⇒ 同街段**整个跳过** ⇒ 0（0x41e93a 直接跳 ENEMY）",
         b.call(2, LAND_MARK + 1).ret, 0)

    # ── B5. ★ 循环从下标 1 起、上界 = [0x498e98] ────────────────────
    print("\n[B5] ★ 同街扫描：i = 1..num_lands（0 号记录永远数不到）")
    b.clear()
    b.land(0, typ=1, owner=1, level=1, name="AAA")        # ★ 同街、我的，但在 0 号
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.num_lands = 1
    case("★ 唯一同街的我方在 **0 号记录** ⇒ 扫不到 ⇒ 0", b.call(2, LAND_MARK + 1).ret, 0)
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.land(2, typ=1, owner=1, level=1, name="AAA")
    b.num_lands = 1
    case("  同街我方在 2 号但 num_lands=1 ⇒ 循环不覆盖 ⇒ 0",
         b.call(2, LAND_MARK + 1).ret, 0)
    b.clear()
    b.land(1, typ=0, owner=3, level=1, name="AAA")
    b.land(2, typ=1, owner=1, level=1, name="AAA")
    b.num_lands = 2
    case("  同一布局、num_lands=2 ⇒ 1（上界确实是 [0x498e98]）",
         b.call(2, LAND_MARK + 1).ret, 1)
    b.clear()
    b.land(1, typ=0, owner=3, level=2, name="AAA")
    b.num_lands = 0
    case("  num_lands=0 ⇒ 同街段整个不跑；仍走 enemy 判定 ⇒ 1（level 2）",
         b.call(2, LAND_MARK + 1).ret, 1)

    # ── B6. 設施支 ──────────────────────────────────────────────────
    print("\n[B6] 設施支：owner ∉ {0, 我} 且 level ≠ 0 ⇒ 1（**完全不看 enemy**）")
    b.clear(); b.fac(1, owner=0, level=5)
    case("owner == 0 ⇒ 0", b.call(2, FAC_MARK + 1).ret, 0)
    b.clear(); b.fac(1, owner=1, level=5)
    case("owner == cur+1 ⇒ 0", b.call(2, FAC_MARK + 1).ret, 0)
    b.clear(); b.fac(1, owner=3, level=0)
    case("level == 0 ⇒ 0", b.call(2, FAC_MARK + 1).ret, 0)
    b.clear(); b.fac(1, owner=3, level=1)
    case("★★ 对手（enemy 本人）的 1 级設施 ⇒ 1（設施支没有等级门槛）",
         b.call(2, FAC_MARK + 1).ret, 1)
    b.clear(); b.fac(1, owner=4, level=1)
    case("★★ **不是**最恨的人的 1 级設施 ⇒ 也 1（enemy 只用于地块支）",
         b.call(2, FAC_MARK + 1).ret, 1)

    # ── B7. 返回值域 / 无副作用 ─────────────────────────────────────
    print("\n[B7] 返回值只有 0/1；不写任何全局")
    seen = set()
    b.clear(); seen.add(b.call(2, LAND_MARK + 1).ret)
    b.clear(); b.land(1, owner=3, level=2); seen.add(b.call(2, LAND_MARK + 1).ret)
    b.clear(); b.fac(1, owner=3, level=1); seen.add(b.call(2, FAC_MARK + 1).ret)
    case("  三种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])
    b.clear(); b.land(1, owner=3, level=2)
    b.call(2, LAND_MARK + 1)
    case("  命中时 0x48be58 仍是哨兵", b.emu_card_param, SENTINEL)
    case("  命中时 0x48be5c 仍是哨兵", b.emu_card_arg, SENTINEL)

    SECTIONS.append(("[B]", len(RESULTS)))


def sec_c():
    print("\n" + "=" * 80)
    print("[C] `0x0041ef26`（273 B）· 拍賣卡 AI —— 零桩，0x40d2d3（最恨的人）真跑")
    print("=" * 80)
    c = PaimaiWorld()

    # ── C1. 脚下格值区间 ────────────────────────────────────────────
    print("\n[C1] 脚下 ref 的两个开区间；企业/景观/空格 ⇒ 0")
    for ref, desc in ((0, "ref=0（脚下没东西）"), (LAND_MARK, "ref=0x7d0（地块 0 号）"),
                      (FAC_MARK, "ref=0xfa0（設施 0 号）"),
                      (COMM_MARK, "ref=0x1770（企业 0 号）"), (0x2000, "ref=0x2000")):
        c.clear(); c.node = 3; c.land(1, owner=3, level=5); c.fac(1, owner=3, level=5)
        c.node_ref(3, ref)
        case(f"  {desc} ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=3, level=3); c.node_ref(3, LAND_MARK + 1)
    case("  ref=0x7d1 + 对手 3 级地 ⇒ 1（下端开）", c.run().ret, 1)
    c.clear(); c.node = 3; c.fac(1, owner=3, level=3); c.node_ref(3, FAC_MARK + 1)
    case("  ref=0xfa1 + 对手 3 级設施 ⇒ 1（下端开）", c.run().ret, 1)
    c.clear(); c.node = 3; c.fac(1999, owner=3, level=3); c.node_ref(3, 0x176F)
    case("  ref=0x176f（= 設施 1999 号）+ 3 级 ⇒ 1（上端开）", c.run().ret, 1)

    # ── C2. 地块支 ──────────────────────────────────────────────────
    print("\n[C2] 地块支：对手（非我非无主）且 level ≥ 3 ⇒ 1")
    c.clear(); c.node = 3; c.land(1, owner=3, level=3); c.node_ref(3, LAND_MARK + 1)
    case("★ 对手 3 级（边界相等）⇒ 1", c.run().ret, 1)
    c.clear(); c.node = 3; c.land(1, owner=3, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 0, 0]
    case("  对手 2 级、无人可恨 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=0, level=5); c.node_ref(3, LAND_MARK + 1)
    case("  owner == 0 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=1, level=5); c.node_ref(3, LAND_MARK + 1)
    case("  owner == cur+1（我自己的）⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=3, level=5); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 0, 0]
    case("  5 级对手（level≥3 支，与 hated 无关）⇒ 1", c.run().ret, 1)

    # ── C3. 地块支 · 最恨的人支 ─────────────────────────────────────
    print("\n[C3] 最恨的人支：owner == hated+1 且 level ≥ 2 ⇒ 1")
    c.clear(); c.node = 3; c.land(1, owner=3, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 500, 0]                 # 最恨 0 基玩家 2 ⇒ owner 3
    case("★ 最恨的人（0 基 2）的 2 级地 ⇒ 1", c.run().ret, 1)
    c.clear(); c.node = 3; c.land(1, owner=3, level=1); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 500, 0]
    case("  最恨的人但只有 1 级 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=2, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 500, 0]                 # 最恨 0 基 2 ⇒ 1 基 owner 3 ≠ 2
    case("  owner=2 而最恨 0 基 2 ⇒ 不匹配 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=2, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 500, 0, 0]                 # 最恨 0 基 1 ⇒ 1 基 owner 2
    case("★ 最恨 0 基 1 ⇒ owner 2 命中（1 基/0 基无错位）", c.run().ret, 1)
    c.clear(); c.node = 3; c.land(1, owner=2, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 0, 500]                 # 最恨是我自己 ⇒ 0x40d2d3 跳过 cur
    case("  敌意表里只有 cur 自己 ⇒ hated = −1（0x40d2d3 跳过 cur）⇒ 0",
         c.run().ret, 0)

    # ── C4. 設施支 ──────────────────────────────────────────────────
    print("\n[C4] 設施支与地块支**完全同形**（也是 ≥3 / 最恨 ≥2）")
    c.clear(); c.node = 3; c.fac(1, owner=3, level=3); c.node_ref(3, FAC_MARK + 1)
    case("  对手 3 级設施 ⇒ 1", c.run().ret, 1)
    c.clear(); c.node = 3; c.fac(1, owner=3, level=2); c.node_ref(3, FAC_MARK + 1)
    c.hostility = [0, 0, 0, 0]
    case("★ 对手 2 级設施、无人可恨 ⇒ 0（**没有**「設施只要 1 级」这种非对称）",
         c.run().ret, 0)
    c.clear(); c.node = 3; c.fac(1, owner=3, level=2); c.node_ref(3, FAC_MARK + 1)
    c.hostility = [0, 0, 500, 0]
    case("★ 最恨的人 2 级設施 ⇒ 1", c.run().ret, 1)
    c.clear(); c.node = 3; c.fac(1, owner=3, level=1); c.node_ref(3, FAC_MARK + 1)
    c.hostility = [0, 0, 500, 0]
    case("  最恨的人 1 级設施 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.fac(1, owner=0, level=5); c.node_ref(3, FAC_MARK + 1)
    case("  owner == 0 ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.fac(1, owner=1, level=5); c.node_ref(3, FAC_MARK + 1)
    case("  owner == cur+1 ⇒ 0", c.run().ret, 0)

    # ── C5. 节点取址 ────────────────────────────────────────────────
    print("\n[C5] 节点取址：node = word[player+0x0c]，步长 0x28，ref = word[node+0x20]")
    c.clear(); c.land(1, owner=3, level=3); c.node = 5; c.node_ref(5, LAND_MARK + 1)
    case("★ 5 号节点的 ref ⇒ 1（地址 = [0x498e80] + 5×0x28 + 0x20）", c.run().ret, 1)
    c.clear(); c.land(1, owner=3, level=3)
    c.node = 4; c.node_ref(0, LAND_MARK + 1)     # 诱饵放在 0 号
    case("★ 站在 4 号、0 号节点有诱饵 ⇒ 只看我脚下的 4 号 ⇒ 0", c.run().ret, 0)
    c.clear(); c.land(1, owner=3, level=3)
    c.node = 0; c.node_ref(0, LAND_MARK + 1)     # 0 号也能用（node 是 word，无 1 基）
    case("  站在 0 号节点、ref 在 0 号 ⇒ 1（节点号没有 1 基偏移）", c.run().ret, 1)
    c.clear(); c.land(1, owner=3, level=3)
    c.node = 5; c.node_ref(5, 0); c.node_ref(6, LAND_MARK + 1)
    case("  站在 5 号（ref=0）而 6 号有 ⇒ 0（确实是按节点号寻址）", c.run().ret, 0)

    # ── C6. cur = [0x49910c] ────────────────────────────────────────
    print("\n[C6] cur = [0x49910c]：换玩家 ⇒ 「我自己的地」判据跟着换")
    c.clear(); c.node = 3; c.land(1, owner=2, level=5); c.node_ref(3, LAND_MARK + 1)
    c.cur = 1
    case("cur=1（0 基）⇒ owner 2 是**我自己的** ⇒ 0", c.run().ret, 0)
    c.clear(); c.node = 3; c.land(1, owner=2, level=5); c.node_ref(3, LAND_MARK + 1)
    c.cur = 0
    case("cur=0 ⇒ 同一个 owner 2 变成对手 ⇒ 1", c.run().ret, 1)

    # ── C7. 返回值 / 无副作用 ───────────────────────────────────────
    print("\n[C7] 返回值只有 0/1；不写 0x48be58")
    seen = set()
    c.clear(); c.node = 3; c.node_ref(3, 0); seen.add(c.run().ret)
    c.clear(); c.node = 3; c.land(1, owner=3, level=3); c.node_ref(3, LAND_MARK + 1)
    seen.add(c.run().ret)
    c.clear(); c.node = 3; c.land(1, owner=3, level=2); c.node_ref(3, LAND_MARK + 1)
    c.hostility = [0, 0, 500, 0]
    seen.add(c.run().ret)
    case("  三种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])
    c.clear(); c.node = 3; c.land(1, owner=3, level=3); c.node_ref(3, LAND_MARK + 1)
    case("★ 命中时 0x48be58 仍是哨兵（本函数不写任何全局）",
         c.run().emu_card_param, SENTINEL)

    SECTIONS.append(("[C]", len(RESULTS)))


def main():
    print("通道 2 差分测试 · 換屋卡助手 `0x40b4f8`（992 B）＋ AI 判据 "
          "`0x41e8e6`（252 B）/ `0x41ef26`（273 B）\n")
    sec_a()
    sec_b()
    sec_c()

    start = 0
    print()
    for name, end in SECTIONS:
        n = end - start
        print(f"  {name} 小计：{sum(RESULTS[start:end])}/{n} 通过")
        start = end
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 80}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
