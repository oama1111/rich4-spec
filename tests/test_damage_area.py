#!/usr/bin/env python3
"""
通道 2 差分测试 · **效果侧范围伤害 `damage_area`**（`0x0040ac7b`，663 B）
＋ **得５０點 分支的尾块**（`0x0041b211`，13 B，跳表片段）

复刻侧对应：
  · `packages/core/src/rules/tool-effects.ts`（`MISSILE_RADIUS` / `NUKE_RADIUS` /
    `MISSILE_FLAGS` / `blastLand`）
  · `packages/core/src/state/reduce.ts` 的 `fireMissile`（`@source damage_area VA 0040ac7b`）
  · `packages/core/src/rules/special-square.ts`（`POINTS_50` 那支的台词选择）

════════════════════════════════════════════════════════════════════════════
[A] `0x0040ac7b` `damage_area(radius, flags, heavy, attacker)` —— 663 B
════════════════════════════════════════════════════════════════════════════
cdecl 四实参（`emu.call` 的 `args` 序即此序）：

    arg0 `[esp+0x20]` radius   —— **原样**转交 `0x40a45c(r)`（`0x0040ac8e` `push edx`）
    arg1 `[esp+0x24]` flags    —— bit1(2) 打住宅 · bit2(4) 打設施 · bit5(0x20) 打人/物件
    arg2 `[esp+0x28]` heavy    —— 0 = 飛彈（轻击）· 非 0 = 核彈（重击）
    arg3 `[esp+0x2c]` attacker —— 记敌意时用的「谁干的」，`-1` = 不记

骨架（逐字节读出来）：

```asm
0040ac8e  push [esp+0x20] ; call 0x40a45c         ; ★ 半径原样透传；返回 n = 表项数
0040ac97  [esp] = n ; edi = 0
0040ac9c  for (i = 0; i < n; i++):
0040aca5      w = word[0x48b8c4 + i*2]            ; 可见实体表的一项
0040acb6      if (flags & 2)                      ; ── 住宅（半开区间 0x7d0 < w < 0xfa0）
0040acc5          if (0x7d0 < w < 0xfa0):
0040acdd              rec = [0x498e84] + (w-0x7d0)*0x34
0040acee              if (heavy == 0):            ; 飛彈
0040acf2                  if (attacker != -1 && rec.owner(+0x19) != 0)
0040acfd                      hostility(owner-1, attacker, 30*pi)   ; ★ 固定 30×物价
0040ad1c                  if (rec.level(+0x1a) != 0) rec.level--
0040ad2a                  if (rec.type(+0x18) != 0) { level = 0; type = 0 }  ; 連鎖店夷平
0040ad3a              else:                     ; 核彈
0040ad45                  if (attacker != -1 && owner != 0)
0040ad53                      hostility(owner-1, attacker, 30*level*pi)   ; ★ 按等级
0040ad6b                  owner = 0; level = 0; type = 0; dword[rec+0x30] = 0
0040ad7e                  call 0x40a4e1(0)       ; ★ **无条件**刷新（哪怕本来全 0）
0040ad88      if (flags & 4)                      ; ── 設施（半开区间 0xfa0 < w < 0x1770）
0040ad97          if (0xfa0 < w < 0x1770):
0040adb5              rec = [0x498e88] + (w-0xfa0)*0x38
0040adc7              if (heavy == 0):            ; 飛彈
0040adcb                  if (attacker != -1 && owner != 0) hostility(owner-1, attacker, 30*pi)
0040adf5                  if (level != 0) level--
0040ae03                  if (level == 0) { type = 0; call 0x40dffa() }   ; ★ 放人
0040ae14              else:                     ; 核彈
0040ae1f                  if (attacker != -1 && owner != 0) hostility(owner-1, attacker, 30*level*pi)
0040ae45                  owner = 0; level = 0; type = 0; dword[rec+0x34] = 0
0040ae58                  call 0x40dffa()       ; ★ 无条件放人
0040ae5d                  call 0x40a4e1(0)      ; ★ 无条件刷新（★ 在放人**之后**）
0040ae67      if (flags & 0x20)                   ; ── 玩家/物件标记（word 带 bit15）
0040ae72          if (w & 0x8000):
0040ae7d              lo = w & 0x0f  ; 逐位 ⇒ 0x40cd07(位号)        ; 位 0..3 = 玩家 0..3
0040aeac              hi = w & 0xf0  ; 逐位 ⇒ 0x43ec3f(位号, 0)      ; 位 4..7（参数恒 0）
0040aee0              v = (w >> 8) & 0x7f ; 非 0 ⇒ 0x40e14d(v)      ; 位 8..14（1 基物件号）
```

★ 三条与复刻直接相关的字节级事实：
1. `0x0040ac8e` 把 **arg0 原样**压给 `0x40a45c` ⇒ §7.140 的裁决（`NUKE_RADIUS = -1`
   的全图支在**效果侧**是对的）在本测试里被逐值钉死（含 `-1` → `0xffffffff`）。
2. 轻击**只减一级**（level 0 不写），重击**连地契一起烧**（`+0x30`/`+0x34` 清 0）——
   与 `tool-effects.ts` 的 `blastLand` 同形，但**設施那一支形状不同**：
   轻击是「level−1，归零才清 type」，地块是「type≠0 就直接 level=0;type=0」。
3. `0x40dffa`（全场放人）只出现在**設施**两支，且重击支**无条件**调用；
   `0x40a4e1(0)`（地图重算）只出现在**重击**两支的地块/設施记录上。

════════════════════════════════════════════════════════════════════════════
[B] `0x0041b211` 得５０點 分支尾块（13 B，**不是函数入口**）
════════════════════════════════════════════════════════════════════════════
字节（`e8 2b 3d 03 00 | 83 c4 0c | e9 b2 01 00 00`）：

```asm
0041b211  call 0x44ef41      ; player_say(player, 0, phrase)   —— 三实参已在栈上
0041b216  add  esp, 0xc      ; 弹出三实参（cdecl）
0041b219  jmp  0x41b3d0      ; 大落点分派器的共用尾声
```

它就是 `0x41b184`（跳表第 10 项·得５０點）尾部的那三条指令，`rich4dis.py`
按 `call` 目标切出来的碎片。**栈上没有返回地址**（`[esp]` 本身就是帧内局部量），
所以只能用 `eval_block(0x41b211, 0x41b3d0, {"esp": 帧})` 驱动，且必须**手搓帧**：
`[esp]=player`、`[esp+4]=0`、`[esp+8]=phrase`（与 `push ecx / push 0 / push ebx` 同形）。

它的**生产者段** `0x41b1d0..0x41b211` 才是「选台词」的规则本体：

```asm
0041b1d0  eax = [0x49910c] * 0x68
0041b1d7  add word [eax + 0x496b98], 0x32        ; 點券 += 50（16 位，回绕）
0041b1df  ebx = 角色(+0x13) * 0x6c               ; 0x6c = 27 事件 × 4
0041b1f8  call 0x456f2d ; and eax,1              ; ★ 只取 bit0
0041b200  ecx = [0x48084a + ebx + idx*4]         ; 角色台词表事件 0 / 1
0041b207  player_say(当前玩家, 0, ecx)
```

复刻 `rules/special-square.ts` 把这一支建模为 `pointsDelta=50` +
`phraseIndex = rng.next() & 1`（只有 `POINTS_50` 掷一次），本测试把**两句台词
到底取自哪一格**用真表钉死。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 按半径扫「可见实体表」`0x48b8c4`，返回项数（`-1` ⇒ 整张 440×440） | 记下 **半径实参**，把数据槽里 `[VIS_N]` 个 word 拷进 `0x48b8c4`，返回 `VIS_N` | 视野/镜头口径差异 = **D-005**，不是本测试对象；本测试要的正是「**半径怎么传进来的** + 拿到表之后怎么处理」 |
| `0x0040df69` | 记敌意 `hostility(a, b, delta)` | 记 `(a, b, delta)` + 全局序 | 它自己的语义另属 `test_hostility_update.py`（22/22） |
| `0x0040dffa` | 全场放人（`test_mutate_release.py` 7/7） | 记调用序 | 本测试只钉「**哪一支**会调它、几次、什么次序」 |
| `0x0040a4e1` | 地图实体数组重算 + 重绘 | 记 `(序, 实参)` | 首步就 `memmove([0x48bad0]+0xc,…)`，裸镜像里该指针是 0 ⇒ 真跑必崩；且 `test_land_mutation_gates.py`（354/354）已单独定案其调用条件 |
| `0x0040cd07` | 被炸玩家的「毁车 + 挂 `+0x15 |= 0x40`」流程（128 B，内含 `0x40b93b`） | 记 `(序, 玩家号)` | 它是表现/状态混合函数；本测试要钉的是**位掩码怎么解**（哪个位 ⇒ 哪个玩家） |
| `0x0043ec3f` | 物件槽分支（**两个**实参） | 记 `(序, 槽号, 0)` | 同上；本测试钉「位 4..7 ⇒ `(槽, 0)`」 |
| `0x0040e14d` | 物件效果（**1 基**物件号，内部 `dec` 后 ×0x18 查 `0x496d08`） | 记 `(序, 值)` | 同上；本测试钉「位 8..14 ⇒ 1 基物件号」 |
| `0x00456f2d` | CRT `rand()` | 数据桩：返回可控值 + 计数 | 本测试只钉「摇没摇、摇几次、怎么取位」（PRNG 本体见 `test_prng.py` 6/6） |
| `0x0044ef41` | `player_say(player, slot, text)` | 记三个实参 + 可控返回值 | 无头环境没有播音/字幕（表现层） |

**真跑**：`0x40ac7b` 与片段 `0x41b211` 本体（本测试对象），以及
`0x41b1d0..0x41b211` 生产者段（只依赖两个被打了桩的 call）。

## 用例分组

| 组 | 钉住什么 |
|---|---|
| `[A1]` | 入口：半径**原样**透传 `0x40a45c`（6 个值，含 `-1`→`0xffffffff`）、`n=0`、循环恰 `n` 次 |
| `[A2]` | `flags` 门控：`0` / `2` / `4` / `0x6` / `0x20` / `0x26` 六种组合下**哪些支跑** |
| `[A3]` | 住宅·轻击：`level−1`（level 0 不写）、`type≠0 ⇒ level=0;type=0`、敌意 `30×pi` 的两道闸 |
| `[A4]` | 住宅·重击：四项全清 + `0x40a4e1(0)` 无条件、敌意 `30×level×pi`、32 位回绕 |
| `[A5]` | 設施·轻击：`level−1`、**归零才清 type 并 `0x40dffa` 放人**、不刷新、无前置 level 判据 |
| `[A6]` | 設施·重击：四项全清 + 放人 + 刷新（次序 `敌意 → 放人 → 刷新`） |
| `[A7]` | 人·物件标记：bit15 门槛 + 三段位解码（低 4 位/位 4..7/位 8..14） |
| `[A8]` | 综合：一发表里多类实体的**交错事件序** |
| `[A9]` | 人·物件支**不看** `attacker`/`heavy`（字节里没有那种判据） |
| `[B1]` | 片段本体：13 字节逐字节 + call/jmp 目标 + 帧三实参 + eax 透传 + `add esp,0xc` + callee-saved + 不掷 rand |
| `[B2]` | 片段生产者段：`點券 += 50`（16 位回绕）、`rand&1` 选角色台词表事件 0/1、实参 = `(cur, 0, 台词)` |

## 复刻裁决（file:line 相对 `rich4-remake/packages/core/src/`）

| # | 规则（原版真值 = 本测试钉死的） | 复刻 | 裁决 |
|---|---|---|---|
| 1 | `damage_area(radius,flags,heavy,attacker)`，`radius` **原样**转交 `0x40a45c` | `MISSILE_RADIUS=0x64` / `NUKE_RADIUS=-1`（`rules/tool-effects.ts:250`） | **MATCH** |
| 2 | `-1` ⇒ 整张 440×440（全图）；否则 `2r×2r` 方窗 | `fireMissile` 的 `inBlast`：heavy ⇒ 全图（`state/reduce.ts:2662-2667`） | **MATCH**（`-1` 那一支）；其余窗口口径见 #3 |
| 3 | 非 `-1` 的窗口是**视图空间**（镜头 + 等距投影后的 440×440） | 改用**地图节点坐标**的方窗，半径同为 100（`state/reduce.ts:2662-2667`） | **DISCREPANCY（已登记 Q-TOOL-1）**：窗内实体集合可不同；§7.140 已裁决 `-1` 那一支在效果侧是对的 |
| 4 | `flags` bit1/bit2/bit5 = 住宅/設施/人·物件；`0x26` 三类齐打 | `MISSILE_FLAGS = 0x26`（`rules/tool-effects.ts:252`） | **MATCH** |
| 5 | 住宅轻击：`level−1`（0 不写）；`type≠0 ⇒ level=0;type=0`；owner/`+0x30` 保留 | `blastLand`（`rules/tool-effects.ts:294-305`） | **MATCH**（`blastLand` 层） |
| 6 | ★★ 上面的 `type=0` 必须**落到状态** | `fireMissile` 只写 `landLevel`/`landOwner`（`state/reduce.ts:2689-2690`），**`out.type` 被丢弃** | **DISCREPANCY**：飛彈打連鎖店时原版「夷平成普通 0 级住宅」，复刻仍是 `landType≠0` 的「0 级連鎖店」（影响 `buildOneLevel` 的 type==1 专支、連鎖店计数/租金类判据） |
| 7 | 住宅重击：owner/level/type/`+0x30`(地契) 全清 | `blastLand` 返回 `owner/level/type=0`（`:307-308`），但循环只写 level/owner（`:2689-2690`），**`landType`/`landTenure` 不动** | **DISCREPANCY**：核彈后那格仍带連鎖店身份与地契到期日；原版 `+0x30=0` ⇒ 复刻的地可能在后续 `sweepTenure`（`:3597-3603`）里"到期" |
| 8 | 重击住宅**每块**都 `0x40a4e1(0)` | 复刻无 `0x40a4e1`（未实现） | **DISCREPANCY（已登记 A-8；本函数新增 4 处调用点证据）** |
| 9 | 敌意 `30×pi`（轻）/`30×level×pi`（重），`attacker=-1` 或 `owner=0` 不记，delta=0 **也调** | `blastLand` 同式（`:297`/`:307`）；`fireMissile` 多一道 `out.hostility !== 0`（`:2691`） | **MATCH（调用次数偏差、状态等价）**：`0x40df69(…,0)` 不改表 |
| 10 | 設施轻击：`level−1`；**归零才** `type=0` 且 `0x40dffa`(放人) | `mutateFacility(fac, MUTATE_DEMOLISH_ONE)`（`state/reduce.ts:2730` → `cards/monster.ts:224-236`） | **MATCH（level≥1）**；`level==0` 见 #11 |
| 11 | ★★ `level` **已经是 0** 的設施：照样 `type=0` + `0x40dffa` | `mutateFacility` 在 `level===0` 时**提前返回**（`cards/monster.ts:225`） | **DISCREPANCY**：原版在那一格上会「放人」（旅館/醫院的人次日释放），复刻什么都不做（可达性取决于表里能否出现 `owner≠0 ∧ level==0` 的設施 —— 拆一级到 0 级会留下这种记录，`mutateFacility` 自己就会留下它） |
| 12 | 設施重击：owner/level/type/`+0x34` 全清 + `0x40dffa` + `0x40a4e1(0)`；設施轻击**不**刷新 | `state/reduce.ts:2708-2735`（四项 + `releaseFlag`）；`land` 支同样不刷新 | **MATCH**（`0x40a4e1` 除外，见 #8） |
| 13 | 人·物件支：bit15 门槛；位 0..3 ⇒ `0x40cd07(位号)`；位 4..7 ⇒ `0x43ec3f(位号,0)`；位 8..14 ⇒ `0x40e14d(1 基号)` | 复刻不建模这张位掩码表，直接按 `hitNodes.has(p.nodeId)` 遍历玩家（`state/reduce.ts:2755`） | **无法判定**（结构不同：谁进窗口由 `0x40a45c` 填表口径决定 = 打桩的 D-005） |
| 14 | 被炸玩家的敌意 `90×pi` / 住院 `3` 天 | `MISSILE_HOSTILITY_FACTOR=90` / `MISSILE_HOSPITAL_DAYS=3`（`rules/tool-effects.ts:255/257`） | **无法判定**：这两个常量**不在** `0x40ac7b` 体内（本函数只把玩家交给 `0x40cd07`），它们的真值点在本测试窗口之外 |
| 15 | 片段 `0x41b211`：`player_say(玩家, 0, 台词)` 后 `add esp,0xc` 再 `jmp` 尾声 | 复刻 core 不调表现层：`settleSpecialSquare` 交出 `phraseIndex`（`rules/special-square.ts:180`） | **MATCH（职责分层）** |
| 16 | 台词下标 = `rand() & 1`，取自 `角色×0x6c + idx*4 + 0x48084a`；**只有 50 點**掷一次 | `phraseIndex = rng.next() & 1`，仅 `POINTS_50`（`rules/special-square.ts:172-181`） | **MATCH** |
| 17 | `add word [+0x30], 0x32`（16 位回绕） | `addPoints` = `(cur+delta) & 0xffff`（`rules/points.ts:39-40`） | **MATCH** |

## 范围外的顺带发现（`damage_area` 的调用方，本测试不驱动其宿主函数）

`0x40ac7b` 全 exe 共 **4 个调用点**（字节级扫描 `e8` 相对位移）：

| 调用点 | 实参 | 复刻对应 |
|---|---|---|
| `0x44707a` 飛彈道具 | `(0x64, 0x26, 0, 当前玩家)` | `MISSILE_*` ✅ |
| `0x447b8c` 核子飛彈 | `(-1, 0x26, 1, 当前玩家)` | `NUKE_*` ✅（§7.140 已裁决） |
| `0x44ac43` 新聞 20「超級颱風」`fcn_0044ab2c` | `(0x64, 6, 0, -1)` | `news-effects.ts:451` 的 `typhoonBlast` ✅ **MATCH** |
| `0x44922d` 新聞 4「外星人攻打地球」`fcn_0044913d` | `(0x64, 0x26, 1, -1)` **重击** | ✅ **已修（2026-09-20，README §7.143）**：事件表第 4 项改记 `['alienBlast']`（`literal: null` 本来就是对的），`news-effects.ts` 新增该分支（半径 100 重击 + 送医 3 天 + 不记敌意），`reduce.ts` 接上 `toolStock` 与理赔。回归见 `packages/core/src/events/news-effects.test.ts`（+16 例）与 `packages/data/src/event-table.test.ts`（+4 例，直接读 exe 字节） |

`fcn_0044913d` 本体：先在一张「level≠0 的地块 + level≠0 的設施」候选表里 `rand()%n` 挑一处
（`0x44917c..0x4491dd`），`0x40af12` 取坐标 → 移镜头 → 重击半径 100；随后
`0x44926e` 扫玩家 0..人数−1，**`+0x15 & 0x40`**（正是 `0x40cd07` 在人·物件支里挂的「被炸」位）
⇒ `0x43ec3f(玩家, 3)` 送医院 3 天。⇒ 原版的新闻 4 是「随机一处房产为中心的**核弹级**爆炸 +
把被炸到的人送医」，不是「把人送医」。

跑法：
```bash
cd rich4-spec && .venv/bin/python tests/test_damage_area.py
cd rich4-spec && .venv/bin/python tests/test_damage_area.py --falsify
```
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STACK_TOP, Emu  # noqa: E402

# ── 被测 ────────────────────────────────────────────────────────────────────
DAMAGE = 0x40AC7B            # damage_area(radius, flags, heavy, attacker)  663 B
FRAG = 0x41B211              # 得50點 尾块：call player_say / add esp,0xc / jmp 尾声
FRAG_END = 0x41B3D0          # 大落点分派器的共用尾声（片段的 jmp 目标）
PRODUCER = 0x41B1D0          # 片段的生产者段（點券 += 50 + 选台词）

# ── 打桩 ────────────────────────────────────────────────────────────────────
VISIBLE = 0x40A45C           # 扫可见实体表（本测试记录它的半径实参）
HOSTILITY = 0x40DF69         # 记敌意 (a, b, delta)
RELEASE_ALL = 0x40DFFA       # 全场放人
MAP_REFRESH = 0x40A4E1       # 地图重算 + 重绘
WRECK = 0x40CD07             # 玩家被炸（毁车/住院那条链的头）
OBJ_SLOT = 0x43EC3F          # 物件槽分支（两实参）
OBJ_FX = 0x40E14D            # 物件效果（1 基物件号）
PRNG = 0x456F2D              # CRT rand
PLAYER_SAY = 0x44EF41        # player_say(player, slot, text)

# ── 全局 ────────────────────────────────────────────────────────────────────
LAND_PTR = 0x498E84
FAC_PTR = 0x498E88
PRICE_INDEX = 0x4990E8
CUR = 0x49910C
VIS_LIST = 0x48B8C4          # 可见实体表（word 数组）
PHRASE_TABLE = 0x48084A      # 角色台词表基址（角色步长 0x6C，事件 0/1 各 4 B）
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_POINTS, P_CHAR = 0x30, 0x13

# ── 记录布局 ────────────────────────────────────────────────────────────────
LAND_STRIDE = 0x34
L_TYPE, L_OWNER, L_LEVEL, L_FLAST = 0x18, 0x19, 0x1A, 0x30
FAC_STRIDE = 0x38
F_TYPE, F_OWNER, F_LEVEL, F_FLAST = 0x18, 0x19, 0x1A, 0x34

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0
MARK_END = 0x1770

# ── 大表（暂存区只有 64 KB，0x7cf 号记录要 66 KB ⇒ 另映射一段） ─────────────
ARENA, ARENA_SIZE = 0x700000, 0x120000
LANDS = ARENA
FACS = ARENA + 0x60000

# ── 暂存区（**跨 call 保持** ⇒ setup 里必须自己清零） ───────────────────────
S_VIS_SRC = SCRATCH_BASE + 0x3000     # 可见实体表的源（word 数组）
S_VIS_REC = SCRATCH_BASE + 0x4000     # (序, 半径) × 64
S_HOST_REC = SCRATCH_BASE + 0x4400    # (序, a, b, delta) × 32
S_REL_REC = SCRATCH_BASE + 0x4800     # (序) × 16
S_REF_REC = SCRATCH_BASE + 0x4900     # (序, 实参) × 16
S_WRECK_REC = SCRATCH_BASE + 0x4A00   # (序, 玩家号) × 32
S_TEL_REC = SCRATCH_BASE + 0x4B00     # (序, 槽号, 0) × 16
S_OBJ_REC = SCRATCH_BASE + 0x4C00     # (序, 物件号) × 16
S_SAY_REC = SCRATCH_BASE + 0x4D00     # (序, player, slot, text) × 16
S_PHRASE = SCRATCH_BASE + 0x6000      # 角色台词表替身（12×3 个 4 B 指针）
# ★ 计数器与数据数组**隔开**（见 verification.md 的桩坑 ④）
SEQ = SCRATCH_BASE + 0x5000
C_VIS = SCRATCH_BASE + 0x5004
C_HOST = SCRATCH_BASE + 0x5008
C_REL = SCRATCH_BASE + 0x500C
C_REF = SCRATCH_BASE + 0x5010
C_WRECK = SCRATCH_BASE + 0x5014
C_TEL = SCRATCH_BASE + 0x5018
C_OBJ = SCRATCH_BASE + 0x501C
C_SAY = SCRATCH_BASE + 0x5020
VIS_N = SCRATCH_BASE + 0x5024         # 本次要拷几个 word
RAND_VAL = SCRATCH_BASE + 0x5028
RAND_N = SCRATCH_BASE + 0x502C
SAY_RET = SCRATCH_BASE + 0x5030

FRAME = 0x53F000              # 片段手搓帧（栈内、离 STACK_TOP 0x1000）
assert FRAME + 0x40 < STACK_TOP

FILL_L, FILL_F = 0xA5, 0x5A
NAME = b"BlastLand\x00\x00\x00\x00\x00\x00"

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
        FAILED.append(f"{desc}（实际 {got!r} ≠ 期望 {want!r}）")
    if not QUIET:
        g = got if isinstance(got, (int, str, tuple, list)) else str(got)
        w = want if isinstance(want, (int, str, tuple, list)) else str(want)
        print(f"  {'✅' if ok else '❌'} {desc:<74} 实际 {g!s:<28} 期望 {w!s}")
    return ok


def put32(emu, va, v):
    """无符号 32 位写（`Emu.write32` 走 `<i`，塞不进 0xffffffff 这类值）"""
    emu.write(va, struct.pack("<I", v & 0xFFFFFFFF))


def pick(recs, i, j):
    """安全取记录字段：记录不存在 ⇒ None（破坏字节后不让断言抛异常，
    而是让断言**如实变红**）。"""
    return recs[i][j] if i < len(recs) else None


def _p32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def _rec_head(rec_va, cnt_va):
    """记录桩的公共头：`ebx` = **本桩自己的**第几次调用（用来定记录下标），
    `esi` = 全局事件序（用来断言跨桩次序）⇒ `eax` = 本次记录槽。

    ★ 两者必须分开：`SEQ` 是所有桩共享的，拿它当下标会让**别的桩**吃掉下标
    （实测：可见表桩先跑一次 ⇒ 第一个毁车记录落到下标 1、读出来整体错位一格）。
    """
    c = b"\x60"                                            # pushad
    c += b"\x8b\x1d" + _p32(cnt_va)                        # mov ebx,[CNT]
    c += b"\xff\x05" + _p32(cnt_va)                        # inc dword [CNT]
    c += b"\x8b\x35" + _p32(SEQ)                           # mov esi,[SEQ]
    c += b"\xff\x05" + _p32(SEQ)                           # inc dword [SEQ]
    return c


def _stub(nargs, rec_va, cnt_va, ret_va=None):
    """通用记录桩：`(序, arg0 … argN-1)` 写进 `rec_va`，自增 `cnt_va`。

    `pushad/popad` 把自己包严（cdecl 只保证 eax/ecx/edx 易失，而调用方
    把**循环下标**放在 ebx/edi 里）；要返回值的桩必须把结果写在 `popad` **之后**。
    """
    recsz = (1 + nargs) * 4
    c = _rec_head(rec_va, cnt_va)
    c += b"\x69\xc3" + _p32(recsz)                         # imul eax,ebx,recsz
    c += b"\x8d\x80" + _p32(rec_va)                        # lea eax,[eax+rec_va]
    c += b"\x89\x30"                                       # mov [eax],esi   ; 序
    for k in range(nargs):
        c += b"\x8b\x54\x24" + bytes([0x24 + 4 * k])       # mov edx,[esp+0x24+4k]
        c += b"\x89\x50" + bytes([4 + 4 * k])              # mov [eax+4+4k],edx
    c += b"\x61"                                           # popad
    if ret_va is not None:
        c += b"\xa1" + _p32(ret_va)                        # mov eax,[ret]
    c += b"\xc3"
    return c


def _vis_stub():
    """`0x40a45c`：记半径实参 → 拷 `[VIS_N]` 个 word 进 `0x48b8c4` → 返回 `[VIS_N]`。"""
    c = _rec_head(S_VIS_REC, C_VIS)
    c += b"\x6b\xc3\x08"                                   # imul eax,ebx,8
    c += b"\x8d\x80" + _p32(S_VIS_REC)                     # lea eax,[eax+S_VIS_REC]
    c += b"\x89\x30"                                       # mov [eax],esi
    c += b"\x8b\x54\x24\x24"                               # mov edx,[esp+0x24]  ; 半径
    c += b"\x89\x50\x04"                                   # mov [eax+4],edx
    c += b"\x8b\x0d" + _p32(VIS_N)                         # mov ecx,[VIS_N]
    c += b"\xbe" + _p32(S_VIS_SRC)                         # mov esi,SRC
    c += b"\xbf" + _p32(VIS_LIST)                          # mov edi,LIST
    c += b"\xf3\x66\xa5"                                   # rep movsw
    c += b"\x61"                                           # popad
    c += b"\xa1" + _p32(VIS_N)                             # mov eax,[VIS_N]
    c += b"\xc3"
    return c


def pack_land(owner=0, level=0, type=0, flast=0):
    b = bytearray([FILL_L] * LAND_STRIDE)
    b[0x04:0x04 + len(NAME)] = NAME
    b[L_TYPE] = type & 0xFF
    b[L_OWNER] = owner & 0xFF
    b[L_LEVEL] = level & 0xFF
    struct.pack_into("<I", b, L_FLAST, flast & 0xFFFFFFFF)
    return bytes(b)


def pack_fac(owner=0, level=0, type=0, flast=0):
    b = bytearray([FILL_F] * FAC_STRIDE)
    b[0x04:0x04 + len(NAME)] = NAME
    b[F_TYPE] = type & 0xFF
    b[F_OWNER] = owner & 0xFF
    b[F_LEVEL] = level & 0xFF
    struct.pack_into("<I", b, F_FLAST, flast & 0xFFFFFFFF)
    return bytes(b)


def hexdiff(before, after):
    if len(before) != len(after):
        return ("LEN",)
    return tuple(f"+0x{i:02x}" for i in range(len(before)) if before[i] != after[i])


class World:
    def __init__(self, sabotage=None):
        self.emu = Emu()
        self.emu.mu.mem_map(ARENA, ARENA_SIZE)
        # ── 打桩 ──
        self.emu.patch(VISIBLE, _vis_stub())
        self.emu.patch(HOSTILITY, _stub(3, S_HOST_REC, C_HOST))
        self.emu.patch(RELEASE_ALL, _stub(0, S_REL_REC, C_REL))
        self.emu.patch(MAP_REFRESH, _stub(1, S_REF_REC, C_REF))
        self.emu.patch(WRECK, _stub(1, S_WRECK_REC, C_WRECK))
        self.emu.patch(OBJ_SLOT, _stub(2, S_TEL_REC, C_TEL))
        self.emu.patch(OBJ_FX, _stub(1, S_OBJ_REC, C_OBJ))
        self.emu.patch(PLAYER_SAY, _stub(3, S_SAY_REC, C_SAY, ret_va=SAY_RET))
        self.emu.patch(PRNG, b"\xa1" + _p32(RAND_VAL)
                       + b"\xff\x05" + _p32(RAND_N) + b"\xc3")
        self.sabotage_desc = None
        if sabotage is not None:
            va, old, new, desc = SABOTAGES[sabotage]
            got = self.emu.read8(va)
            if got != old:
                raise RuntimeError(f"破坏点 0x{va:08x} 原字节是 0x{got:02x}，不是 0x{old:02x}")
            self.emu.patch(va, bytes([new]))
            self.sabotage_desc = desc
        self.state = {}

    # ── 世界构造 ───────────────────────────────────────────────────────────
    def clear(self):
        self.state = {"words": [], "lands": {}, "facs": {}, "pi": 1, "rand": 0, "say_ret": 0}
        return self

    def tbl(self, *words):
        self.state["words"] = list(words)
        return self

    def land(self, idx, **f):
        self.state["lands"][idx] = f
        return self

    def fac(self, idx, **f):
        self.state["facs"][idx] = f
        return self

    def pi(self, v):
        self.state["pi"] = v
        return self

    def _setup(self, emu):
        st = self.state
        put32(emu, LAND_PTR, LANDS)
        put32(emu, FAC_PTR, FACS)
        put32(emu, PRICE_INDEX, st["pi"])
        put32(emu, CUR, 0)
        put32(emu, VIS_N, len(st["words"]))
        put32(emu, RAND_VAL, st["rand"])
        put32(emu, SAY_RET, st["say_ret"])
        for s in (SEQ, C_VIS, C_HOST, C_REL, C_REF, C_WRECK, C_TEL, C_OBJ, C_SAY, RAND_N):
            put32(emu, s, 0)
        # ★ 暂存区跨调用保持 ⇒ 先把用到的记录区清零，再写本次的项
        for base, n in ((S_VIS_REC, 0x200), (S_HOST_REC, 0x200), (S_REL_REC, 0x100),
                        (S_REF_REC, 0x100), (S_WRECK_REC, 0x200), (S_TEL_REC, 0x200),
                        (S_OBJ_REC, 0x100), (S_SAY_REC, 0x200)):
            emu.write(base, b"\x00" * n)
        emu.write(VIS_LIST, b"\x00" * 0x100)
        # 大表：只清本次用到的记录（其余保持上次内容也无妨 —— 断言只按本次的项）
        for idx in st["lands"]:
            emu.write(LANDS + idx * LAND_STRIDE, pack_land(**st["lands"][idx]))
        for idx in st["facs"]:
            emu.write(FACS + idx * FAC_STRIDE, pack_fac(**st["facs"][idx]))
        # 可见实体表源
        emu.write(S_VIS_SRC, b"".join(struct.pack("<H", w & 0xFFFF) for w in st["words"]))

    # ── 运行 ───────────────────────────────────────────────────────────────
    def run(self, radius=-1, flags=0x26, heavy=0, attacker=-1, **kw):
        for k, v in kw.items():
            self.state[k] = v
        # ★ 「改写前」= setup 将要写进去的那份打包字节（不能读内存：ARENA 不在
        #   快照里、且 setup 还没跑，读到的会是**上一个用例**的残留）
        before = {("L", i): pack_land(**f) for i, f in self.state["lands"].items()}
        before.update({("F", i): pack_fac(**f) for i, f in self.state["facs"].items()})
        rc = self.emu.call(DAMAGE, [radius & 0xFFFFFFFF, flags, heavy, attacker],
                           setup=self._setup)
        e = self.emu
        self.res = {
            "vis": self._recs(S_VIS_REC, 8, e.readu32(C_VIS)),
            "host": self._recs(S_HOST_REC, 16, e.readu32(C_HOST)),
            "rel": self._recs(S_REL_REC, 4, e.readu32(C_REL)),
            "ref": self._recs(S_REF_REC, 8, e.readu32(C_REF)),
            "wreck": self._recs(S_WRECK_REC, 8, e.readu32(C_WRECK)),
            "tel": self._recs(S_TEL_REC, 12, e.readu32(C_TEL)),
            "obj": self._recs(S_OBJ_REC, 8, e.readu32(C_OBJ)),
            "say": self._recs(S_SAY_REC, 16, e.readu32(C_SAY)),
            "radius": e.readu32(S_VIS_REC + 4),
            "rand_n": e.readu32(RAND_N),
            "insns": rc["insns"],
            "diff": {},
        }
        for key, b in before.items():
            kind, i = key
            if kind == "L":
                self.res["diff"][("L", i)] = hexdiff(b, self._read(LANDS, i, LAND_STRIDE))
            else:
                self.res["diff"][("F", i)] = hexdiff(b, self._read(FACS, i, FAC_STRIDE))
        return self.res

    def _read(self, base, idx, stride):
        return self.emu.read(base + idx * stride, stride)

    # ── 回读记录字段 ───────────────────────────────────────────────────────
    def lb(self, idx, off=0):
        return self.emu.read8(LANDS + idx * LAND_STRIDE + off)

    def ld(self, idx, off):
        return self.emu.readu32(LANDS + idx * LAND_STRIDE + off)

    def fb(self, idx, off=0):
        return self.emu.read8(FACS + idx * FAC_STRIDE + off)

    def fd(self, idx, off):
        return self.emu.readu32(FACS + idx * FAC_STRIDE + off)

    def _recs(self, base, size, n):
        return [[self.emu.readu32(base + i * size + 4 * k) for k in range(size // 4)]
                for i in range(n)]

    def counts(self):
        r = self.res
        return (len(r["vis"]), len(r["host"]), len(r["rel"]), len(r["ref"]),
                len(r["wreck"]), len(r["tel"]), len(r["obj"]))

    def events(self, kinds=("host", "rel", "ref", "wreck", "tel", "obj")):
        """按**全局事件序**把各桩的记录合并 → `[(kind, args…), …]`。

        ★ 各桩的「第几次」是各自的计数器（用来定记录下标），跨桩次序看的是
        共享的 `SEQ`；两者分开才不会因为「可见表桩先跑一次」而整体错位一格。
        """
        out = []
        for k in kinds:
            for rec in self.res[k]:
                out.append((rec[0], k, rec[1:]))
        return [(k, a) for _, k, a in sorted(out, key=lambda t: t[0])]

    # ── 片段（[B]） ────────────────────────────────────────────────────────
    def run_frag(self, player, phrase, says_ret=0, regs=None):
        def setup(emu):
            put32(emu, SEQ, 0)
            put32(emu, C_SAY, 0)
            put32(emu, RAND_N, 0)
            put32(emu, SAY_RET, says_ret)
            emu.write(S_SAY_REC, b"\x00" * 0x200)
            put32(emu, FRAME + 0x00, player)
            put32(emu, FRAME + 0x04, 0)
            put32(emu, FRAME + 0x08, phrase)
        r = self.emu.eval_block(FRAG, FRAG_END, regs=dict({"esp": FRAME}, **(regs or {})),
                                setup=setup)
        self.frag = {
            "regs": r["regs"],
            "insns": r["insns"],
            "say": self._recs(S_SAY_REC, 16, self.emu.readu32(C_SAY)),
            "rand_n": self.emu.readu32(RAND_N),
        }
        return self.frag

    def run_producer(self, cur=0, char=0, points=0, rand=0, say_ret=0):
        def setup(emu):
            put32(emu, CUR, cur)
            put32(emu, SEQ, 0)
            put32(emu, C_SAY, 0)
            put32(emu, RAND_N, 0)
            put32(emu, RAND_VAL, rand & 0xFFFFFFFF)
            put32(emu, SAY_RET, say_ret)
            emu.write(S_SAY_REC, b"\x00" * 0x200)
            emu.write(S_PHRASE, b"\x00" * 0x200)
            for c in range(12):
                for ev in range(3):
                    put32(emu, PHRASE_TABLE + c * 0x6C + ev * 4, S_PHRASE + c * 16 + ev)
            for p in range(4):
                emu.write16(PLAYER_BASE + p * PLAYER_STRIDE + P_POINTS, 0)
                emu.write8(PLAYER_BASE + p * PLAYER_STRIDE + P_CHAR, 0)
            emu.write16(PLAYER_BASE + cur * PLAYER_STRIDE + P_POINTS, points & 0xFFFF)
            emu.write8(PLAYER_BASE + cur * PLAYER_STRIDE + P_CHAR, char)
        r = self.emu.eval_block(PRODUCER, FRAG_END, regs={"esp": FRAME}, setup=setup)
        self.prod = {
            "regs": r["regs"],
            "say": self._recs(S_SAY_REC, 16, self.emu.readu32(C_SAY)),
            "rand_n": self.emu.readu32(RAND_N),
            "points": {p: self.emu.read16(PLAYER_BASE + p * PLAYER_STRIDE + P_POINTS)
                       for p in range(4)},
        }
        return self.prod


# ============================================================================
#  [A] damage_area 0x40ac7b
# ============================================================================
def group_a1(w):
    say("[A1] 入口：半径**原样**转交 0x40a45c(r)（0x0040ac8e）+ 循环 n 次")
    for radius, want in [(0x64, 0x64), (-1, 0xFFFFFFFF), (0, 0), (1, 1),
                         (0x1B8, 0x1B8), (0x12345678, 0x12345678)]:
        w.clear().tbl()
        r = w.run(radius=radius)
        case(f"radius={radius & 0xFFFFFFFF:#x} ⇒ 0x40a45c 收到 {want:#x}", r["radius"], want)
        case("  ★ 0x40a45c 恰被调 1 次", len(r["vis"]), 1)

    w.clear().tbl()
    r = w.run()
    case("n=0 ⇒ 除 0x40a45c 外一个被调方都不动", w.counts(), (1, 0, 0, 0, 0, 0, 0))

    w.clear().tbl(0x8001, 0x8002, 0x8004)
    r = w.run(flags=0x20)
    case("n=3 ⇒ 循环正好 3 次（三个玩家标记）", len(r["wreck"]), 3)
    case("  依表序 [0, 1, 2]", [x[1] for x in r["wreck"]], [0, 1, 2])


def group_a2(w):
    say("\n[A2] flags 门控：bit2 住宅 / bit2+1 設施 / bit5 人·物件")
    land = dict(owner=3, level=3, type=0)
    fac = dict(owner=2, level=3, type=5)

    w.clear().tbl(0x7D1, 0xFA1, 0x8001).land(1, **land).fac(1, **fac)
    r = w.run(flags=0)
    case("flags=0 ⇒ 三类全不动", w.counts(), (1, 0, 0, 0, 0, 0, 0))
    case("  地块零改动", r["diff"][("L", 1)], ())
    case("  設施零改动", r["diff"][("F", 1)], ())

    w.clear().tbl(0x7D1, 0xFA1).land(1, **land).fac(1, **fac)
    r = w.run(flags=0x2, attacker=0)
    case("flags=0x2 ⇒ 只有住宅那支跑（設施不动）", r["diff"][("F", 1)], ())
    case("  住宅掉一级", r["diff"][("L", 1)], ("+0x1a",))
    case("  敌意 1 次、没有 0x40a4e1（飛彈不刷新）", w.counts(), (1, 1, 0, 0, 0, 0, 0))

    w.clear().tbl(0x7D1, 0xFA1).land(1, **land).fac(1, **fac)
    r = w.run(flags=0x4)
    case("flags=0x4 ⇒ 只有設施那支跑（住宅不动）", r["diff"][("L", 1)], ())
    case("  設施掉一级", r["diff"][("F", 1)], ("+0x1a",))
    case("  没有敌意（attacker=-1）", len(r["host"]), 0)

    w.clear().tbl(0x7D1).land(1, **land)
    r = w.run(flags=0x20)
    case("flags=0x20 且该词无 bit15 ⇒ 什么也不做", w.counts(), (1, 0, 0, 0, 0, 0, 0))
    case("  住宅零改动", r["diff"][("L", 1)], ())

    w.clear().tbl(0x7D1, 0xFA1, 0x8001).land(1, **land).fac(1, **fac)
    r = w.run(flags=0x6, attacker=0, pi=1)
    case("flags=0x6 ⇒ 住宅 + 設施都跑，人那支不跑", len(r["wreck"]), 0)
    case("  两条敌意（住宅 30、設施 30）", [x[3] for x in r["host"]], [30, 30])


def group_a3(w):
    say("\n[A3] 住宅 · 轻击（飛彈）：level−1，type≠0 ⇒ 直接夷平；敌意恒 30×物价")
    w.clear().tbl(0x7D1).land(1, owner=3, level=3, type=0, flast=0x11223344)
    r = w.run(flags=0x2, attacker=2, pi=1)
    case("hostility(owner-1=2, attacker=2, 30×1=30)", pick(r["host"], 0, slice(1, None)), [2, 2, 30])
    case("★ 只动 +0x1a（3→2）", r["diff"][("L", 1)], ("+0x1a",))
    case("owner/+0x30 保留", (w.lb(1, L_OWNER), w.ld(1, L_FLAST)), (3, 0x11223344))

    w.clear().tbl(0x7D1).land(1, owner=3, level=0, type=0, flast=7)
    r = w.run(flags=0x2, attacker=2)
    case("level=0 ⇒ 一个字节都不写（不写回绕）", r["diff"][("L", 1)], ())
    case("  敌意照样记", len(r["host"]), 1)

    w.clear().tbl(0x7D1).land(1, owner=3, level=3, type=5)
    r = w.run(flags=0x2, attacker=2)
    case("★ 連鎖店(type=5) 轻击 ⇒ level 与 type 一起归 0", r["diff"][("L", 1)],
         ("+0x18", "+0x1a"))
    case("  连击后 owner 仍在", w.lb(1, L_OWNER), 3)

    w.clear().tbl(0x7D1).land(1, owner=3, level=0, type=5)
    r = w.run(flags=0x2, attacker=2)
    case("type=5 且 level 已 0 ⇒ 只清 type", r["diff"][("L", 1)], ("+0x18",))

    w.clear().tbl(0x7D1).land(1, owner=3, level=2, type=0)
    r = w.run(flags=0x2, attacker=-1)
    case("attacker=-1 ⇒ 不记敌意，但照样拆一级", (len(r["host"]), r["diff"][("L", 1)]),
         (0, ("+0x1a",)))

    w.clear().tbl(0x7D1).land(1, owner=0, level=2, type=0)
    r = w.run(flags=0x2, attacker=2)
    case("owner=0 ⇒ 不记敌意，但照样拆一级", (len(r["host"]), r["diff"][("L", 1)]),
         (0, ("+0x1a",)))

    w.clear().tbl(0x7D1).land(1, owner=3, level=1, type=0)
    r = w.run(flags=0x2, attacker=2, pi=3)
    case("物价指数 3 ⇒ 敌意 90（30×pi）", pick(r["host"], 0, 3), 90)

    w.clear().tbl(0x7D1).land(1, owner=3, level=1, type=0)
    r = w.run(flags=0x2, attacker=2, pi=0)
    case("物价指数 0 ⇒ 敌意 0，但调用**照发**", (len(r["host"]), pick(r["host"], 0, 3)), (1, 0))

    w.clear().tbl(0x7D0).land(1, owner=3, level=2, type=0)
    r = w.run(flags=0x2, attacker=2)
    case("★ 下界开区间：w=0x7d0（住宅 0 号）不算命中", (w.counts(), r["diff"][("L", 1)]),
         ((1, 0, 0, 0, 0, 0, 0), ()))

    w.clear().tbl(0x7D1, 0xF9F).land(1, owner=1, level=1, type=0)
    w.land(0x7CF, owner=2, level=1, type=0)
    r = w.run(flags=0x2, attacker=0)
    case("★ 上界开区间：w=0xf9f ⇒ 记录 0x7cf（步长 0x34 算对）",
         ([x[1] for x in r["host"]], r["diff"][("L", 0x7CF)]), ([0, 1], ("+0x1a",)))

    w.clear().tbl(0x7D1, 0x7D2).land(1, owner=1, level=1, type=0)
    w.land(2, owner=2, level=1, type=0)
    r = w.run(flags=0x2, attacker=3)
    case("两次命中按表序 ⇒ [(0,3,30), (1,3,30)]",
         [[x[1], x[2], x[3]] for x in r["host"]], [[0, 3, 30], [1, 3, 30]])

    w.clear().tbl(0xFA1).fac(1, owner=1, level=2, type=0)
    r = w.run(flags=0x2)
    case("flags 只有 bit1 时，設施词（0xfa1）不归住宅支", w.counts(),
         (1, 0, 0, 0, 0, 0, 0))


def group_a4(w):
    say("\n[A4] 住宅 · 重击（核彈）：owner/level/type/+0x30 全清 + 无条件刷新")
    w.clear().tbl(0x7D1).land(1, owner=3, level=4, type=5, flast=0x11223344)
    r = w.run(flags=0x2, heavy=1, attacker=2, pi=1)
    case("hostility(2, 2, 30×4×1=120)", pick(r["host"], 0, slice(1, None)), [2, 2, 120])
    case("★ 四项全清", r["diff"][("L", 1)],
         ("+0x18", "+0x19", "+0x1a", "+0x30", "+0x31", "+0x32", "+0x33"))
    case("★ 0x40a4e1(0) 恰 1 次", (len(r["ref"]), pick(r["ref"], 0, 1)), (1, 0))
    case("★ 不碰放人函数（那是設施支的事）", len(r["rel"]), 0)

    w.clear().tbl(0x7D1).land(1, owner=0, level=3, type=5, flast=9)
    r = w.run(flags=0x2, heavy=1, attacker=2)
    case("owner=0 ⇒ 不记敌意，但四项照样清 + 照样刷新",
         (len(r["host"]), len(r["ref"]), w.lb(1, L_LEVEL)), (0, 1, 0))

    w.clear().tbl(0x7D1).land(1, owner=3, level=3, type=0, flast=9)
    r = w.run(flags=0x2, heavy=1, attacker=-1)
    case("attacker=-1 ⇒ 不记敌意，但清地 + 刷新照旧",
         (len(r["host"]), len(r["ref"]), w.lb(1, L_OWNER)), (0, 1, 0))

    w.clear().tbl(0x7D1).land(1, owner=3, level=0, type=0)
    r = w.run(flags=0x2, heavy=1, attacker=2, pi=5)
    case("★ level=0 ⇒ 敌意 0，但调用**照发**（无条件支）",
         (len(r["host"]), pick(r["host"], 0, 3)), (1, 0))
    case("  全 0 记录仍刷新", len(r["ref"]), 1)

    w.clear().tbl(0x7D1).land(1, owner=1, level=255, type=0)
    r = w.run(flags=0x2, heavy=1, attacker=0, pi=0x1000000)
    case("★ imul 32 位回绕：30×255×0x1000000 = 0x1de2_000000 ⇒ 低 32 位 0xe2000000",
         f"{r['host'][0][3]:#010x}", "0xe2000000")

    w.clear().tbl(0xFA1).fac(1, owner=2, level=2, type=1)
    r = w.run(flags=0x2, heavy=1, attacker=2)
    case("重击但词在設施区间 ⇒ 住宅支不命中，也不刷新", w.counts(),
         (1, 0, 0, 0, 0, 0, 0))

    w.clear().tbl(0x7D1, 0x7D2).land(1, owner=1, level=1, type=0)
    w.land(2, owner=1, level=1, type=0)
    r = w.run(flags=0x2, heavy=1, attacker=0)
    case("两块重击地 ⇒ 刷新 2 次，都实参 0",
         (len(r["ref"]), [x[1] for x in r["ref"]]), (2, [0, 0]))
    case("  两次敌意与两次刷新交错（host < ref < host < ref）",
         [k for k, _ in w.events()], ["host", "ref", "host", "ref"])


def group_a5(w):
    say("\n[A5] 設施 · 轻击：level−1，归零才清 type 并**放人**（地块那支形状不同）")
    w.clear().tbl(0xFA1).fac(1, owner=2, level=3, type=5, flast=0x01020304)
    r = w.run(flags=0x4, attacker=0, pi=1)
    case("hostility(owner-1=1, attacker=0, 30)", pick(r["host"], 0, slice(1, None)), [1, 0, 30])
    case("★ 3→2：只掉一级，type 保留", r["diff"][("F", 1)], ("+0x1a",))
    case("  没归零 ⇒ 不放人、不刷新", (len(r["rel"]), len(r["ref"])), (0, 0))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=1, type=5, flast=0x01020304)
    r = w.run(flags=0x4, attacker=0)
    case("★ 1→0 ⇒ type 也清 0", r["diff"][("F", 1)], ("+0x18", "+0x1a"))
    case("★ 归零 ⇒ 放人 1 次", len(r["rel"]), 1)
    case("  轻击**不**调 0x40a4e1", len(r["ref"]), 0)
    case("  +0x34（設施地契）保留", w.fd(1, F_FLAST), 0x01020304)

    w.clear().tbl(0xFA1).fac(1, owner=2, level=0, type=5)
    r = w.run(flags=0x4, attacker=0)
    case("★ level 已 0 且 type≠0 ⇒ 清 type 且**照放人**（无前置 level 判据）",
         (r["diff"][("F", 1)], len(r["rel"])), (("+0x18",), 1))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=0, type=0)
    r = w.run(flags=0x4, attacker=0)
    case("★ 全 0 設施记录：一个字节不改，但**仍然放人**",
         (r["diff"][("F", 1)], len(r["rel"])), ((), 1))

    w.clear().tbl(0xFA1).fac(1, owner=0, level=2, type=0)
    r = w.run(flags=0x4, attacker=0)
    case("owner=0 ⇒ 不记敌意，但仍拆一级", (len(r["host"]), r["diff"][("F", 1)]),
         (0, ("+0x1a",)))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=2, type=0)
    r = w.run(flags=0x4, attacker=-1)
    case("attacker=-1 ⇒ 不记敌意", (len(r["host"]), r["diff"][("F", 1)]), (0, ("+0x1a",)))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=1, type=0)
    r = w.run(flags=0x4, attacker=0, pi=3)
    case("敌意 30×3=90（輕击不吃等级）", pick(r["host"], 0, 3), 90)

    w.clear().tbl(0xFA0, 0x1770, 0x176F).fac(0x7CF, owner=1, level=1, type=0)
    r = w.run(flags=0x4, attacker=0)
    case("★ 两端都是开区间：0xfa0 与 0x1770 都不命中，0x176f ⇒ 记录 0x7cf",
         (len(r["host"]), r["diff"][("F", 0x7CF)]), (1, ("+0x1a",)))

    w.clear().tbl(0xFA1).fac(1, owner=1, level=1, type=0)
    r = w.run(flags=0x4, attacker=0)
    case("★ 次序：先记敌意、再放人", [e[0] for e in (r["host"] + r["rel"])],
         sorted([x[0] for x in r["host"]] + [y[0] for y in r["rel"]]))


def group_a6(w):
    say("\n[A6] 設施 · 重击：四项全清 + 放人 + 刷新（次序 放人 → 刷新）")
    w.clear().tbl(0xFA1).fac(1, owner=2, level=6, type=3, flast=0x01020304)
    r = w.run(flags=0x4, heavy=1, attacker=1, pi=2)
    case("hostility(1, 1, 30×6×2=360)", pick(r["host"], 0, slice(1, None)), [1, 1, 360])
    case("★ 四项全清", r["diff"][("F", 1)],
         ("+0x18", "+0x19", "+0x1a", "+0x34", "+0x35", "+0x36", "+0x37"))
    case("★ 放人 1 次 + 刷新 1 次（实参 0）",
         (len(r["rel"]), len(r["ref"]), pick(r["ref"], 0, 1)), (1, 1, 0))
    case("★★ 次序：敌意 → 放人 → 刷新",
         (None if None in (pick(r["host"], 0, 0), pick(r["rel"], 0, 0), pick(r["ref"], 0, 0))
          else pick(r["host"], 0, 0) < pick(r["rel"], 0, 0) < pick(r["ref"], 0, 0)), True)

    w.clear().tbl(0xFA1).fac(1, owner=0, level=0, type=0, flast=0)
    r = w.run(flags=0x4, heavy=1, attacker=3)
    case("★ 全 0 设施：不记敌意，仍放人 + 刷新",
         (len(r["host"]), len(r["rel"]), len(r["ref"])), (0, 1, 1))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=3, type=1)
    r = w.run(flags=0x4, heavy=1, attacker=-1)
    case("attacker=-1 ⇒ 不记敌意，仍放人 + 刷新",
         (len(r["host"]), len(r["rel"]), len(r["ref"])), (0, 1, 1))

    w.clear().tbl(0xFA1).fac(1, owner=2, level=0, type=9)
    r = w.run(flags=0x4, heavy=1, attacker=0, pi=7)
    case("level=0 ⇒ 敌意 0，调用照发", (len(r["host"]), pick(r["host"], 0, 3)), (1, 0))

    w.clear().tbl(0xFA1).fac(1, owner=1, level=200, type=0)
    r = w.run(flags=0x4, heavy=1, attacker=0, pi=0x1000000)
    case("★ 設施重击同一 imul：30×200×0x1000000 = 0x1770_000000 ⇒ 低 32 位 0x70000000",
         f"{r['host'][0][3]:#010x}", "0x70000000")


def group_a7(w):
    say("\n[A7] 人·物件标记（flags & 0x20）：bit15 门槛 + 三段位解码")
    w.clear().tbl(0x0001)
    r = w.run(flags=0x20)
    case("无 bit15（w=0x0001）⇒ 一个都不调", w.counts(), (1, 0, 0, 0, 0, 0, 0))

    for wd, want in [(0x8001, [0]), (0x8002, [1]), (0x8004, [2]), (0x8008, [3]),
                     (0x800F, [0, 1, 2, 3]), (0x8009, [0, 3])]:
        w.clear().tbl(wd)
        r = w.run(flags=0x20)
        case(f"w={wd:#06x} ⇒ 毁车(位号) {want}", [x[1] for x in r["wreck"]], want)

    for wd, want in [(0x8010, [[4, 0]]), (0x8020, [[5, 0]]), (0x8040, [[6, 0]]),
                     (0x8080, [[7, 0]]),
                     (0x80F0, [[4, 0], [5, 0], [6, 0], [7, 0]])]:
        w.clear().tbl(wd)
        r = w.run(flags=0x20)
        case(f"w={wd:#06x} ⇒ 物件槽支 {want}", [x[1:] for x in r["tel"]], want)

    for wd, want in [(0x8000, []), (0x8100, [1]), (0x8200, [2]), (0x8400, [4]),
                     (0xFF00, [0x7F]), (0xFE00, [0x7E])]:
        w.clear().tbl(wd)
        r = w.run(flags=0x20)
        case(f"w={wd:#06x} ⇒ 物件效果(1 基) {want}", [x[1] for x in r["obj"]], want)

    w.clear().tbl(0xFFFF)
    r = w.run(flags=0x20)
    case("★ w=0xffff ⇒ 4 毁车 + 4 槽 + 1 物件效果，共 9 次",
         (len(r["wreck"]), len(r["tel"]), len(r["obj"])), (4, 4, 1))
    case("  物件号 = (0xffff>>8)&0x7f = 0x7f", pick(r["obj"], 0, 1), 0x7F)
    case("★★ 三段次序：全部毁车 → 全部槽 → 物件效果",
         [k for k, _ in w.events()],
         ["wreck"] * 4 + ["tel"] * 4 + ["obj"])

    w.clear().tbl(0x80FF)
    r = w.run(flags=0x20)
    case("w=0x80ff（bits 8..14 = 0）⇒ 4+4 次、无物件效果",
         (len(r["wreck"]), len(r["tel"]), len(r["obj"])), (4, 4, 0))

    w.clear().tbl(0x7D1, 0x8001).land(1, owner=1, level=1, type=0)
    r = w.run(flags=0x26, attacker=0)
    case("★ 人支与住宅支共存：敌意(w=0x7d1) 先于 毁车(w=0x8001)",
         (len(r["host"]), len(r["wreck"]),
          None if None in (pick(r["host"], 0, 0), pick(r["wreck"], 0, 0))
          else pick(r["host"], 0, 0) < pick(r["wreck"], 0, 0)),
         (1, 1, True))
    case("  住宅被拆一级", r["diff"][("L", 1)], ("+0x1a",))

    w.clear().tbl(0x8001, 0x8002)
    r = w.run(flags=0x20)
    case("两个标记按表序处理", [x[1] for x in r["wreck"]], [0, 1])

    w.clear().tbl(0x8001)
    r = w.run(flags=0x2)
    case("flags 无 bit5 ⇒ 标记完全不处理", w.counts(), (1, 0, 0, 0, 0, 0, 0))


def group_a8(w):
    say("\n[A8] 综合：一发表里的多类实体 + 重击的完整调用序")
    w.clear().tbl(0x7D1, 0xFA1, 0x8001)
    w.land(1, owner=1, level=1, type=0).fac(1, owner=1, level=1, type=5)
    r = w.run(flags=0x26, attacker=0)
    case("flags=0x26 轻击：住宅敌意 → 設施(敌意→放人) → 毁车",
         [k for k, _ in w.events()], ["host", "host", "rel", "wreck"])
    case("  三项副作用各自发生",
         (r["diff"][("L", 1)], r["diff"][("F", 1)]), (("+0x1a",), ("+0x18", "+0x1a")))

    w.clear().tbl(0x7D1, 0xFA1)
    w.land(1, owner=1, level=1, type=0).fac(1, owner=1, level=1, type=5)
    r = w.run(flags=0x6, heavy=1, attacker=0)
    case("★★ flags=0x6 与 heavy=1：住宅(敌意→刷新) 然后 設施(敌意→放人→刷新)",
         [k for k, _ in w.events()], ["host", "ref", "host", "rel", "ref"])
    case("  刷新实参恒 0", [x[1] for x in r["ref"]], [0, 0])

    w.clear().tbl(0x7D1, 0x0000, 0x7D2).land(1, owner=1, level=1, type=0)
    w.land(2, owner=2, level=1, type=0)
    r = w.run(flags=0x2, attacker=0)
    case("★ 表中间的 0 词只是跳过，不打断循环", [x[1] for x in r["host"]], [0, 1])
    case("  两块地都被拆一级",
         (r["diff"][("L", 1)], r["diff"][("L", 2)]), (("+0x1a",), ("+0x1a",)))


def group_a9(w):
    say("\n[A9] 人·物件支**不含**任何「自己/攻击者/弹种」过滤（字节里没有那种判据）")
    w.clear().tbl(0x800F, 0x80F0, 0xFF00)
    r1 = w.run(flags=0x20, attacker=-1, heavy=0)
    sig1 = w.events()
    w.run(flags=0x20, attacker=3, heavy=0)
    sig2 = w.events()
    w.run(flags=0x20, attacker=3, heavy=1)
    sig3 = w.events()
    case("★ 表 [0x800f, 0x80f0, 0xff00] ⇒ 4 毁车 + 4 槽 + 1 物件效果",
         (len(r1["wreck"]), len(r1["tel"]), len(r1["obj"])), (4, 4, 1))
    case("★★ attacker 从 -1 换到 3 ⇒ 人·物件支一字不变", sig1 == sig2, True)
    case("★★ heavy 从 0 换到 1 ⇒ 人·物件支一字不变（弹种不影响这一段）", sig1 == sig3, True)
    case("  事件序：毁车 0..3（小写位先行）", [k for k, _ in sig1][:4], ["wreck"] * 4)
    case("  接着槽 4..7", [k for k, _ in sig1][4:8], ["tel"] * 4)
    case("  最后 1 基物件号 0x7f", sig1[8:9], [("obj", [0x7F])])

    # ★ 测试台回归（gaps §7.141）：同一实例跑到这里已经上百次 call()，
    #   若 hook 泄漏，insn_count 会被放大 k 倍并在 MAX_INSN 处**静默假停**。
    rr = w.run(radius=-1)
    case("★★ 跑满 100+ 次后单次指令数仍然很小（钩子泄漏回归）", rr["insns"] < 1000, True)


# ============================================================================
#  [B] 0x41b211 片段
# ============================================================================
def group_b1(w):
    say("\n[B1] 0x41b211 片段本体（13 B）：call player_say / add esp,0xc / jmp 尾声")
    raw = w.emu.read(FRAG, 13)
    case("★ 字节：e8 2b3d0300 | 83 c4 0c | e9 b2010000",
         raw.hex(), "e82b3d030083c40ce9b2010000")
    call_rel = struct.unpack_from("<i", raw, 1)[0]
    case("★ call 目标 = 0x41b216 + rel ⇒ 0x44ef41 (player_say)",
         (FRAG + 5 + call_rel), PLAYER_SAY)
    jmp_rel = struct.unpack_from("<i", raw, 9)[0]
    case("★ jmp 目标 = 0x41b21e + rel ⇒ 0x41b3d0 (共用尾声)",
         (FRAG + 13 + jmp_rel), FRAG_END)
    case("★ 片段长度 13 B（0x41b211..0x41b21e）", 0x41B21E - FRAG, 13)

    f = w.run_frag(player=2, phrase=0x11112222)
    case("player_say 恰被调 1 次", len(f["say"]), 1)
    case("★ 帧里的三实参原样传出：(player=2, slot=0, text)",
         f["say"][0][1:], [2, 0, 0x11112222])

    f = w.run_frag(player=0, phrase=0xABCDEF01)
    case("换帧 ⇒ 实参跟着换（不是常量）", f["say"][0][1:], [0, 0, 0xABCDEF01])

    f = w.run_frag(player=3, phrase=0x5A5A5A5A)
    case("player=3 也原样传出", f["say"][0][1:], [3, 0, 0x5A5A5A5A])

    f = w.run_frag(player=1, phrase=0x1000, says_ret=0x0BADF00D)
    case("★ eax 直接透传 player_say 的返回值", f["regs"]["eax"], 0x0BADF00D)
    f = w.run_frag(player=1, phrase=0x1000, says_ret=0x7FFFFFFF)
    case("  换返回值也透传", f["regs"]["eax"], 0x7FFFFFFF)

    f = w.run_frag(player=1, phrase=0x1000)
    case("★ 收尾 `add esp,0xc` 弹掉三实参", f["regs"]["esp"], FRAME + 0xC)

    f = w.run_frag(player=1, phrase=0x1000,
                   regs={"ebx": 0xB1B1B1B1, "esi": 0xE51E51E5, "edi": 0xD1D1D1D1,
                         "ebp": 0xB0B0B0B0})
    case("★ 片段不改 callee-saved（ebx/esi/edi/ebp）",
         (f["regs"]["ebx"], f["regs"]["esi"], f["regs"]["edi"], f["regs"]["ebp"]),
         (0xB1B1B1B1, 0xE51E51E5, 0xD1D1D1D1, 0xB0B0B0B0))

    f = w.run_frag(player=1, phrase=0x1000)
    case("★ 片段本身不掷随机数（rand&1 在调用方）", f["rand_n"], 0)

    # 停址：若片段 jmp 到别处，eval_block 会抛「区块未停在预期停址」
    try:
        w.run_frag(player=0, phrase=1)
        case("★ 片段的目标确实是共用尾声 0x41b3d0（eval_block 停在停址）", True, True)
    except Exception as e:  # noqa: BLE001
        case(f"★ 片段的目标确实是共用尾声 0x41b3d0（异常：{e}）", False, True)


def group_b2(w):
    say("\n[B2] 片段的生产者段 0x41b1d0..0x41b211（點券 += 50 + 选台词）")
    p = w.run_producer(cur=0, char=0, points=100, rand=0)
    case("★ 點券 100 + 50 = 150", p["points"][0], 150)
    case("★ 只动**当前玩家**的點券（别人不变）", [p["points"][i] for i in (1, 2, 3)],
         [0, 0, 0])
    case("★ rand 恰掷 1 次", p["rand_n"], 1)
    case("rand=0（偶）⇒ 事件 0 的台词",
         p["say"][0][1:], [0, 0, S_PHRASE + 0 * 16 + 0])

    p = w.run_producer(cur=0, char=0, rand=1)
    case("rand=1（奇）⇒ 事件 1 的台词", p["say"][0][3], S_PHRASE + 0 * 16 + 1)

    p = w.run_producer(cur=0, char=0, rand=2)
    case("rand=2 ⇒ `and eax,1` ⇒ 事件 0", p["say"][0][3], S_PHRASE + 0 * 16 + 0)
    p = w.run_producer(cur=0, char=0, rand=0xFFFFFFFF)
    case("rand=0xffffffff ⇒ bit0=1 ⇒ 事件 1", p["say"][0][3], S_PHRASE + 0 * 16 + 1)

    p = w.run_producer(cur=2, char=5, points=0xFFF0, rand=1)
    case("★ 角色 5：表位移 = 5×0x6c（不是 5×4）", p["say"][0][3], S_PHRASE + 5 * 16 + 1)
    case("★ 16 位回绕：65520 + 50 ⇒ 34", p["points"][2], (0xFFF0 + 50) & 0xFFFF)
    case("★ 实参 = (当前玩家, 0, 台词)", p["say"][0][1:], [2, 0, S_PHRASE + 5 * 16 + 1])

    p = w.run_producer(cur=3, char=11, rand=0)
    case("角色 11 / cur=3 也按同一算式", p["say"][0][1:], [3, 0, S_PHRASE + 11 * 16 + 0])

    p = w.run_producer(cur=1, char=7, rand=1, say_ret=0x33)
    case("生产者段同样透传 player_say 的返回值", p["regs"]["eax"], 0x33)
    case("  也停在共用尾声（regs 可读）", isinstance(p["regs"]["esp"], int), True)


# ============================================================================
#  可证伪检查
# ============================================================================
SABOTAGES = {
    "A": (0x40ACE5, 0x34, 0x38,
          "0x40ac7b · 地块记录步长 0x34 → 0x38（记录指针错位）"),
    "B": (0x40ADBD, 0x29, 0x01,
          "0x40ac7b · 設施步长算式 `sub eax,edx` → `add`（0x38 → 0x50）"),
    "C": (0x40AD79, 0x30, 0x34,
          "0x40ac7b · 重击地块的 flast 位移 +0x30 → +0x34（清了設施的字段）"),
    "D": (0x40AE76, 0x80, 0x40,
          "0x40ac7b · 人·物件支的门槛 `test [esp+9],0x80` → 0x40（bit15 → bit14）"),
    "E": (0x40AD08, 0x04, 0x05,
          "0x40ac7b · 轻击敌意的 `shl eax,4` → `shl eax,5`（30×pi → 62×pi）"),
    "F": (0x40AD29, 0x1A, 0x19,
          "0x40ac7b · 轻击地块的 level 写点 +0x1a → +0x19（改成写 owner）"),
    "G": (0x40AE0C, 0x18, 0x19,
          "0x40ac7b · 轻击設施归零时的 type 写点 +0x18 → +0x19"),
    "H": (0x41B218, 0x0C, 0x10,
          "0x41b211 · 片段收尾 `add esp,0xc` → `add esp,0x10`"),
    "I": (0x41B203, 0x4A, 0x4E,
          "0x41b1d0 · 台词表位移低字节 0x4a → 0x4e（事件 0/1 → 事件 1/2）"),
}


def run_suite(w):
    RESULTS.clear()
    FAILED.clear()
    group_a1(w)
    group_a2(w)
    group_a3(w)
    group_a4(w)
    group_a5(w)
    group_a6(w)
    group_a7(w)
    group_a8(w)
    group_a9(w)
    group_b1(w)
    group_b2(w)
    return sum(RESULTS), len(RESULTS)


def main(argv):
    global QUIET
    if "--falsify" in argv:
        return falsify()
    say("通道 2 差分测试 · 效果侧范围伤害 damage_area 0x0040ac7b（663 B）"
        " ＋ 得50點尾块 0x0041b211（13 B）")
    w = World()
    run_suite(w)
    n, t = sum(RESULTS), len(RESULTS)
    print(f"\n{'=' * 84}\n结果：{n}/{t} 通过")
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
        print(f"\n破坏 [{key}] @VA 0x{va:08x} 0x{old:02x}→0x{new:02x}：{desc}")
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
