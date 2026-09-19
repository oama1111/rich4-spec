#!/usr/bin/env python3
"""
通道 2 差分测试 · **查稅卡 `0x004202D2`（316 B）与同盟卡 `0x004207CC`（420 B）的 AI 目标选择**

两张卡都是 AI 出牌跳表 `0x475324` 的成员（卡 26 / 卡 29；入口 `0x41e6e6 call [0x475324+action*4]`），
复刻侧分别对应 `rich4-remake/packages/core/src/ai/card-policy.ts` 的
`chashui`（`card-policy.ts:730`）与 `tongmeng`（`card-policy.ts:819`）。
两个函数**没有任何 `call` 调用者**（只被跳表间址调用），`rich4-spec` 的建图工具不收，
故按需反汇编：`cd rich4-remake && python3 tools/disasm.py va 0x004202d2 110`（及 `0x004207cc 140`）。

★★ **尺寸订正（以字节为准）**：任务说明里的「~159 B / ~191 B」来自 `gen/functions.json`
（= `rich4dis.py func <va> --orphans` 的口径），而该口径把这两个 handler **切碎了**：
  · 它给 `0x4202d2` 记的是「指令 51 / 字节 159 / **结尾 jmp**」，可 159 B 的最后一字节落在
    `0x42036e imul ecx,ebp,0x68` 中间（`0x420371` 才到下一条 `mov edx,[0x4990e8]`）——
    自己的记录就自相矛盾；同一段里还多出一条幻影入口 `0x420369`（越界解码成 `cmp al,0x2c`）。
  · 它给 `0x4207cc` 记的是「指令 60 / 字节 191」，同样在 `0x42088b`（best 循环头）处截断。
逐字节读出的**真实边界**是：
  · `0x4202d2`–`0x42040d`，末尾 `jmp 0x41e8dc`（`mov eax,esi; add esp,0xc; pop×4; ret` 共享尾声）
    ⇒ **316 B**（下一条函数入口 `0x42040e`）
  · `0x4207cc`–`0x42096f`（自带 `add esp,0x1c; pop×4; ret`）⇒ **420 B**（下一条函数入口 `0x420970`）
真值只认机器码，故下面的语义块按 316 / 420 B 写。副证据：碎片化还让 `functions.json` 的
`writes` 只记到 `0x48be60`，**漏掉**两个函数真正的出口 `0x48be58`（本测试 [A1]/[B1] 组把它钉上）。

## 语义 A · 查稅卡 `0x4202d2`（316 B）

```
0x4202d2():                                        ; 无参数（AI 用卡判据）
    esi = 0                                        ; ← 返回值（0 = 不用，1 = 用）
    [esp..esp+3] = 0                               ; mark[4] 玩家标记数组清零
    hated = 0x40d2d3([0x49910c])                   ; 0 基玩家下标，−1 = 没有（真跑）
    [0x48be60] = 0x40a45c(-1)                      ; aiP2 = 可见表项数
    for (i = 0; i < [0x48be60]; i++) {             ; 0x420304
        v = word [0x48b8c4 + i*2]
        if (!(v & 0x8000)) continue                ; 0x42031e  test bh,0x80
        if (!(v & 0x000f)) continue                ; 0x420323  test bl,0xf
        for (p = 0, bit = 1; bit < 0x10; p++, bit <<= 1)       ; 0x42033f / 0x420337 / 0x42033a
            if ((v & bit) && p != cur && player[p].alive != 0) ; 0x420343 / 0x42034a
                mark[p] = 1                        ; 0x420353  mov byte [esp+p], 1
    }
    ; ── 支 A：最恨的人优先，门槛 **严格** cash > 30000×price_index
    if (hated != -1 && mark[hated] && 30000*price < player[hated].cash) {   ; 0x420392 cmp eax,[ecx+0x496b84]
        [0x48be58] = 0x8000 | (1 << hated)         ; 0x4203a5 or ah,0x80
        esi = 1                                    ; 0x4203ad
    }
    ; ── 支 B：兜底，门槛 **严格** cash > 50000×price_index，上界 = 人数
    for (p = 0; p < [0x499114]; p++) {             ; 0x4203cd  ★ 上界 = num_players
        if (!mark[p]) continue                     ; 0x4203d9
        if (50000*price < player[p].cash) {        ; 0x4203e8 cmp edx,[eax+0x496b84]
            [0x48be58] = 0x8000 | (1 << p)         ; 0x4203fe
            esi = 1                                ; ★ 0x420403 之后**没有 break/jmp 出口**
        }                                          ;   ⇒ 命中后继续扫，**最后一个合格的赢**
    }
    return esi
```

两类「非对称 / 易写错」的点：
1. **支 A 的门槛（30000×）与支 B 的（50000×）都是严格 `>`**（`jge` 跳过），
   即 `cash == 门槛` **不**命中。
2. ★★ **支 B 不 break ⇒ 取「下标最大的合格者」**，不是第一个（`[A6]` 组四条专钉这一条）。
3. `mark[]` 的每一位来自**同一个格值的位**：一格值可同时标多个玩家（`0x8000|0b1010` ⇒ p1 与 p3）。
4. ★ **判据宽度**：`30000×pi` 由 `shl/add/sub` 序列算出、`50000×pi` 是 `imul edx,ebp,0xc350`
   —— 两者都是 **32 位有符号**，`pi ≥ 42950` 时 `50000×pi`、`pi ≥ 71583` 时 `30000×pi`
   会**回绕成负数**，于是门槛反过来「无条件通过」（`[A10]` 组四条把回绕点钉住）。

## 语义 B · 同盟卡 `0x4207cc`（420 B）

```
0x4207cc():                                        ; 无参数
    ret = 0                                        ; [esp+0xc]
    [0x48be60] = 0x40a45c(-1)                      ; aiP2 = 可见表项数
    hated = 0x40d2d3([0x49910c])                   ; [esp+0x14]，0 基
    n = 0                                          ; edi：候选个数
    cand[] = 栈上 [esp..]（最多 4 项）
    for (i = 0; i < [0x48be60]; i++) {             ; 0x420804
        v = word [0x48b8c4 + i*2]
        if (!(v & 0x8000)) continue                ; 0x42081e  test dh,0x80
        if (!(v & 0x000f)) continue                ; 0x420823  test dl,0xf
        for (p = 0, bit = 1; bit < 0x10; p++, bit <<= 1) {   ; 0x420839 / 0x420831 / 0x420834
            if (!(v & bit)) continue               ; 0x420839
            if (p == cur) continue                 ; 0x42083d  cmp ecx,[0x49910c]
            if (p == hated) continue               ; 0x420845  cmp ecx,[esp+0x14]
            if (player[p].alive == 0) continue     ; 0x42084e  cmp byte [ebx+0x496b7d],0
            if (player[p].allied == cur+1) continue; 0x42086a  ★ +0x41 是 **1 基** 玩家号
            cand[n++] = p                          ; 0x42086e  mov byte [esp+edi], cl
        }
    }
    if (n == 0) return 0                           ; 0x420879  je 0x420964（0x48be58 不动）
    ; ── best：所有 p != cur 且活着的玩家里，**地產 + 設施记录数**严格最大者（平手取小下标）
    best = 0; best_p = -1                          ; esi / [esp+0x10]
    for (p = 0; p < [0x499114]; p++) {             ; 0x42088b  ★ 上界 = num_players
        if (p == cur) continue                     ; 0x420897
        if (player[p].alive == 0) continue         ; 0x4208a6
        cnt = 0
        for (j = 1; j <= [0x498e98]; j++)          ; 0x4208c3  地產表 [0x498e84] + j*0x34
            if (land[j].owner == p+1) cnt++        ; 0x4208de  ★ owner **1 基**
        for (j = 1; j <= [0x498e8c]; j++)          ; 0x4208fa  設施表 [0x498e88] + j*0x38
            if (fac[j].owner == p+1) cnt++         ; 0x420912
        if (cnt > best) { best = cnt; best_p = p } ; 0x420921 cmp esi,edx / jge 跳过（严格 >）
    }
    ; ── 终判：best_p 必须**同时**出现在候选表里（否则它是不可见 / 最恨 / 已同盟）
    for (k = 0; k < n; k++)                        ; 0x420937
        if (cand[k] == best_p) {                   ; 0x420940
            [0x48be58] = 0x8000 | (1 << best_p); ret = 1; break   ; 0x420952 / 0x420957
        }
    return ret
```

★ **两套下标基**：候选/`best_p` 是 **0 基玩家**，`land.owner`/`fac.owner` 与
`player.allied`（`+0x41`）都是 **1 基**（`owner == p+1`、`allied == cur+1`）——
本测试用 `[F]` 组把这两套基各钉一条。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 把 440×440 物件格 `0x474938` 的非零值抄进 `0x48b8c4`，**返回项数** | `mov eax,[COUNT_SLOT]; ret`（表由 `setup()` 直接铺） | 它自己的语义（视野口径）已定案，复刻换了视野模型 = **D-005**，不是本测试对象；本测试要的是「可见表**如何被解读**」（0x8000 / 低 4 位 / 位序） |
| `0x00456f2d` | CRT `rand()` | **不需要桩** —— 这两个函数体里**一处 `call 0x456f2d` 都没有**（全程无随机） |

`0x40d2d3`（最恨的人）**真跑** —— 本测试要的正是它与主干的组合（`[A3]`/`[B2]` 组）。
★ 因此 `setup()` 必须写 `[0x499114]`（**人数**）：它既是 `0x40d2d3` 的循环上界，
也是两个函数**支 B / best 选取**的上界；漏写会让「最恨的人」恒为 −1（见 verification.md 工具边界第 5 条）。

## 可证伪性自查（已做，记录在案）

本文件 97 条断言（A 48 / B 49）全绿后，**每张卡各故意破坏一个 `setup()` 值**再跑一遍：

| # | 破坏点 | 现象 | 结论 |
|---|---|---|---|
| 1 | 查稅卡：`P_CASH` 从 `+0x1c` 改成 `+0x18`（**错偏移**） | 97 → **74 通过 / 23 失败**，23 条**全在 A 组**（支 A / 支 B 的门槛、目标编码、返回值集合）；B 组 0 失败 | A 的断言真的读到了现金，且只有 A 读现金 |
| 2 | 同盟卡：`NUM_LANDS`(`0x498e98`) 恒写 0（**缺上界全局**） | 97 → **74 通过 / 23 失败**，23 条**全在 B 组**（best 计数、1 基 owner、终判、编码）；A 组 0 失败 | B 的断言真的依赖地块计数上界 |

两次都改回原值后复跑 **97/97**。

## 与复刻逐条对照（`ai/card-policy.ts`，未改任何 TS）

**查稅卡 `chashui`**：门槛（严格 `>`）、最恨者支、`alive`/可见性、上界、目标语义 —— 全部一致。
两处不一致：
  · 支 B 的**「第一个 vs 最后一个」**：本次会话开始时 `card-policy.ts:736` 是
    `if (…) return player(i);`（**取第一个**合格者），而机器码 `0x4203fe` 写完出口后
    **没有 break**（`0x420403 mov esi,1` → `0x420408 inc` → `0x42040c jmp`）
    ⇒ **取下标最大**的合格者 —— 是 **DISCREPANCY**（§7.3 第 14 条那类「选错人」的可见偏差）。
    本文件写完后，`card-policy.ts` 在 **07:59:55 被并发更新**（非本 agent 所为）为
    `let picked = -1; … picked = i; …`（现 `card-policy.ts:740–744`）⇒ 现版本 **MATCH**。
  · ★ **判据宽度（尚未对齐）**：原版 `30000×pi`/`50000×pi` 是 32 位有符号、会回绕
    （`pi ≥ 42950` / `≥ 71583` 起门槛变负 ⇒ 无条件通过），`card-policy.ts:734/742` 用
    JS double 不会回绕 ⇒ 这两个 pi 区间上**口径分叉**。游戏内可达性**无法判定**
    （`pi = trunc(总资产均值 / 开局资金)`，单调不降，上限取决于对局长度与通胀），
    故本测试只钉原版真值（`[A10]`），**不**据此判复刻错。

**同盟卡 `tongmeng`**：候选四道闸（`i != me` / `!= hated` / `alive` / `alliedPlayer != me+1`）、
`地產+設施` 记录数严格最大、平手取小下标、`best` 必须同时在候选表里、`owner === i+1` 的 1 基口径 ——
与机器码**逐条一致**（`card-policy.ts:826–844`）⇒ **MATCH**。
`topo.lands` / `topo.facilities` 由 `loaders/map.ts:541/565` 以 `i = 1..numLands/numFacilities` 建表，
正是原版 `for (j = 1; j <= [0x498e98]/[0x498e8c]; j++)` 的口径（记录 0 两边都不数）。

跑法：`cd rich4-spec && .venv/bin/python tests/test_card_policy_helpers.py`
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
CHARSHUI = 0x4202D2            # 卡 26 查稅卡（316 B）
TONGMENG = 0x4207CC            # 卡 29 同盟卡（420 B）

# ── 打桩 ──
VISIBLE_FILL = 0x40A45C        # 填「可見表」

# ── 全局 ──
CUR = 0x49910C                 # 当前玩家（0 基）
NUM_PLAYERS = 0x499114         # ★ 人数：0x40d2d3 与两个函数的支 B 上界
PRICE_INDEX = 0x4990E8         # 物價指數
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NUM_LANDS = 0x498E98           # 地產记录数（**1 基**遍历 1..N）
NUM_FACS = 0x498E8C            # 設施记录数（**1 基**遍历 1..N）
VIS_LIST = 0x48B8C4            # 可见表（word 数组）
AI_P0 = 0x48BE58               # 目标出口
AI_P1 = 0x48BE5C               # 第二参数（只有搶奪卡用）—— 本两函数不该碰
AI_P2 = 0x48BE60               # 本两函数都写：可见表项数
AI_P3 = 0x48BE64               # 道具参数 —— 本两函数不该碰

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_ALIVE, P_CASH, P_ALLIED = 0x15, 0x1C, 0x41
P_HOSTILITY, HOST_STRIDE = 0x4C, 4

LAND_STRIDE, L_OWNER = 0x34, 0x19
FAC_STRIDE, F_OWNER = 0x38, 0x19

LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000
COUNT_SLOT = SCRATCH_BASE + 0x900

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<74} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    """状态留在 Python 侧；`Emu.call` 每拍先 reset，故每拍都要重新注入。"""

    def __init__(self):
        self.emu = Emu()
        # 可见表桩：返回 setup() 铺进 COUNT_SLOT 的项数
        self.emu.patch(VISIBLE_FILL, b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.fn = CHARSHUI
        self.me = 0
        self.num_players = 4
        self.price = 1
        self.vis = []              # 可见表格值（word）
        self.lands = {}            # 记录号 → owner（1 基 owner；0 号记录正常读不到）
        self.facs = {}
        self.num_lands = None      # None ⇒ 由 lands 的最大下标推出
        self.num_facs = None
        self.cash = [0, 0, 0, 0]
        self.alive = [1, 1, 1, 1]
        self.allied = [0, 0, 0, 0]     # +0x41，1 基玩家号，0 = 未同盟
        self.hostility = [0, 0, 0, 0]
        return self

    def vis_players(self, *ps):
        for p in ps:
            self.vis.append(0x8000 | (1 << p))
        return self

    def land(self, i, owner):
        self.lands[i] = owner
        return self

    def fac(self, i, owner):
        self.facs[i] = owner
        return self

    def rich(self, *ps):
        """给这些玩家一笔「远高于任何门槛」的现金（门槛另由 price 决定）。"""
        for p in ps:
            self.cash[p] = 10 ** 9
        return self

    # ── 注入 ──
    def _setup(self, emu):
        n_land = self.num_lands if self.num_lands is not None else (max(self.lands) if self.lands else 0)
        n_fac = self.num_facs if self.num_facs is not None else (max(self.facs) if self.facs else 0)
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, self.num_players)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(NUM_LANDS, n_land)
        emu.write32(NUM_FACS, n_fac)
        emu.write32(COUNT_SLOT, len(self.vis) & 0xFFFFFFFF)
        # 四个 aiP 槽全部先放哨兵
        for slot in (AI_P0, AI_P1, AI_P2, AI_P3):
            emu.write32(slot, SENTINEL)
        # ★ 暂存区跨调用保留 ⇒ 每次都先整片清零（verification.md 工具边界第 3 条）
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(VIS_LIST, b"\x00" * 64)
        for i, v in enumerate(self.vis):
            emu.write16(VIS_LIST + i * 2, v & 0xFFFF)
        # 玩家表
        for p in range(4):
            b = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(b + P_ALIVE, self.alive[p])
            emu.write32(b + P_CASH, self.cash[p] & 0xFFFFFFFF)
            emu.write8(b + P_ALLIED, self.allied[p] & 0xFF)
        for j, h in enumerate(self.hostility):
            emu.write32(PLAYER_BASE + self.me * PLAYER_STRIDE + P_HOSTILITY + j * HOST_STRIDE,
                        h & 0xFFFFFFFF)
        for i, o in self.lands.items():
            emu.write8(LANDS + i * LAND_STRIDE + L_OWNER, o)
        for i, o in self.facs.items():
            emu.write8(FACS + i * FAC_STRIDE + F_OWNER, o)

    def run(self, fn=None):
        if fn is not None:
            self.fn = fn
        r = self.emu.call(self.fn, [], setup=self._setup)
        self.ret = r["eax"]
        self.p0 = self.emu.read32(AI_P0)
        self.p1 = self.emu.read32(AI_P1)
        self.p2 = self.emu.read32(AI_P2)
        self.p3 = self.emu.read32(AI_P3)
        return self


def main():
    print("差分测试 · 查稅卡 0x4202d2（316 B）+ 同盟卡 0x4207cc（420 B）的 AI 目标选择\n")
    w = World()

    # ============================================================
    #  [A] 查稅卡 0x4202d2
    # ============================================================
    print("=" * 84)
    print("[A] 查稅卡 0x4202d2（卡 26）：可见表 → mark[]，最恨者 > 30000×物價，否则 > 50000×物價")
    print("=" * 84)

    # ── [A1] 输出槽契约 ─────────────────────────────────────────
    print("[A1] 输出槽：只写 0x48be58；0x48be60 = 可见表项数；0x48be5c / 0x48be64 不碰")
    w.clear()
    r = w.run(CHARSHUI)
    case("空可见表 ⇒ 返回 0", r.ret, 0)
    case("  0x48be58 保持哨兵（无目标时不写）", r.p0, SENTINEL)
    case("  0x48be5c 保持哨兵（第二参数只有搶奪卡用）", r.p1, SENTINEL)
    case("  0x48be64 保持哨兵（道具参数，本卡不写）", r.p3, SENTINEL)
    case("  0x48be60 = 可见表项数 0", r.p2, 0)

    w.clear()
    w.vis = [0x8000 | 2, 0x8000 | 4, 0x0001]     # 三条，其中一条无 0x8000 位
    r = w.run(CHARSHUI)
    case("★ 0x48be60 = 可见表项数 3（不是「有效项数」）", r.p2, 3)

    # ── [A2] 可见表编码：0x8000 + 低 4 位 ───────────────────────
    print("\n[A2] 可见表编码：必须 `v & 0x8000` 且 `v & 0x000f` 非 0；低 4 位的每一位 = 一名玩家")
    w.clear()
    w.me = 1
    w.rich(1)
    w.vis = [0x0002]                             # 有玩家位、无 0x8000
    r = w.run(CHARSHUI)
    case("无 0x8000 位（0x0002）⇒ 不进 mark ⇒ 0", r.ret, 0)

    w.clear()
    w.me = 1
    w.rich(1)
    w.vis = [0x8000]                             # 有 0x8000、低 4 位 = 0
    r = w.run(CHARSHUI)
    case("低 4 位 = 0（0x8000）⇒ 0", r.ret, 0)

    w.clear()
    w.rich(1, 2, 3)
    w.vis = [0x8000 | 0x0010]                    # bit4 不在低 4 位内
    r = w.run(CHARSHUI)
    case("★ 只置 bit4（0x8010）⇒ 低 4 位为 0 ⇒ 0（位 4..7 被忽略）", r.ret, 0)

    w.clear()
    w.vis_players(0)                             # 只有我自己
    w.rich(0)
    r = w.run(CHARSHUI)
    case("★ 只标了当前玩家自己 ⇒ 0（mark 里排除 self）", r.ret, 0)

    w.clear()
    w.alive[1] = 0
    w.vis_players(1)
    w.rich(1)
    r = w.run(CHARSHUI)
    case("★ 对手位已置但 player[1].alive=0 ⇒ 0（mark 要求 +0x15 ≠ 0）", r.ret, 0)

    w.clear()
    w.vis = [0x8000 | 0x0100 | 0x0002]           # 高位杂物 + p1 位
    w.rich(1)
    r = w.run(CHARSHUI)
    case("★ 0x8000|0x0100|p1 ⇒ 高位杂物不影响，仍标 p1", r.p0, 0x8002)

    w.clear()
    w.vis = [0x8000 | 0x000A]                    # 一格同时含 p1 与 p3
    w.rich(1, 3)
    r = w.run(CHARSHUI)
    case("★★ 一格多玩家位 0b1010 ⇒ p1、p3 都被标（不是只取最低位）", r.p0, 0x8008)

    # ── [A3] 支 A：最恨的人，严格 > 30000×物價 ─────────────────
    print("\n[A3] 支 A：最恨的人，门槛 **严格** `cash > 30000×price_index`；且他必须在画面上（mark[hated]）")
    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]                   # 最恨 0 基玩家 1
    w.vis_players(1)
    w.cash[1] = 30000 * 1                        # 恰好等于门槛
    r = w.run(CHARSHUI)
    case("★ cash 恰 = 30000×pi ⇒ 支 A **不**命中（严格 >）", r.ret, 0)
    case("  且没写 0x48be58（50000 也不到）", r.p0, SENTINEL)

    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1)
    w.cash[1] = 30000 * 1 + 1
    r = w.run(CHARSHUI)
    case("cash = 30000×pi + 1 ⇒ 支 A 命中", r.ret, 1)
    case("  目标 = 0x8000 | (1 << hated=1) = 0x8002", r.p0, 0x8002)

    w.clear()
    w.me = 2                                     # 换当前玩家：hated 表在 me 那一笔里
    w.hostility = [0, 0, 0, 9]                   # 最恨 0 基玩家 3
    w.vis_players(3)
    w.cash[3] = 10 ** 6
    r = w.run(CHARSHUI)
    case("★ me=2、最恨 0 基玩家 3 ⇒ 目标 0x8008（hated 是 **0 基**，不做 +1）", r.p0, 0x8008)

    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]                   # 最恨 p1
    w.vis_players(2)                             # 但画面里只有 p2
    w.rich(1, 2)                                 # p1 钱多但不可见
    r = w.run(CHARSHUI)
    case("★★ 最恨的人不在画面（mark[hated]=0）⇒ 支 A 不成立 ⇒ 兜底选可见的 p2", r.p0, 0x8004)

    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1, 3)
    w.rich(1, 3)
    r = w.run(CHARSHUI)
    case("★ 最恨 p1 与 p3 都有钱 ⇒ 支 A 只选 p1（不落到兜底的「取最后」）", r.p0, 0x8002)

    # ── [A4] 支 A 的 price_index 缩放 ──────────────────────────
    print("\n[A4] 支 A 的 `30000×price_index` 是**运行时**乘法（不是常量 30000）")
    w.clear()
    w.me = 0
    w.price = 2
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1)
    w.cash[1] = 60000                            # = 30000×2，恰好等于门槛
    r = w.run(CHARSHUI)
    case("pi=2、cash=60000（= 30000×2）⇒ 严格 > 不成立 ⇒ 0", r.ret, 0)

    w.clear()
    w.me = 0
    w.price = 2
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1)
    w.cash[1] = 60001
    r = w.run(CHARSHUI)
    case("pi=2、cash=60001 ⇒ 支 A 命中", r.p0, 0x8002)

    w.clear()
    w.me = 0
    w.price = 3
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1)
    w.cash[1] = 90000                            # 30000×3 恰好等
    r = w.run(CHARSHUI)
    case("pi=3、cash=90000 ⇒ 0（又一次严格 > 的回归）", r.ret, 0)

    # ── [A5] 支 B：门槛严格 > 50000×物價 ───────────────────────
    print("\n[A5] 支 B（hated = −1）：门槛 **严格** `cash > 50000×price_index`")
    w.clear()
    w.vis_players(1)
    w.cash[1] = 50000
    r = w.run(CHARSHUI)
    case("cash 恰 = 50000×pi ⇒ 不命中（严格 >）", r.ret, 0)
    case("  0x48be58 保持哨兵", r.p0, SENTINEL)

    w.clear()
    w.vis_players(1)
    w.cash[1] = 50001
    r = w.run(CHARSHUI)
    case("cash = 50000×pi + 1 ⇒ 命中", r.ret, 1)
    case("  目标 = 0x8002", r.p0, 0x8002)

    w.clear()
    w.price = 3
    w.vis_players(2)
    w.cash[2] = 150000                           # 50000×3
    r = w.run(CHARSHUI)
    case("pi=3、cash=150000（= 50000×3）⇒ 0", r.ret, 0)

    w.clear()
    w.price = 3
    w.vis_players(2)
    w.cash[2] = 150001
    r = w.run(CHARSHUI)
    case("pi=3、cash=150001 ⇒ 命中 0x8004", r.p0, 0x8004)

    w.clear()
    w.price = 0                                  # 门槛 0 ⇒ cash=1 就够
    w.vis_players(1)
    w.cash[1] = 1
    r = w.run(CHARSHUI)
    case("pi=0、cash=1 ⇒ 命中（门槛退化为 0）", r.p0, 0x8002)

    w.clear()
    w.price = 0
    w.vis_players(1)
    w.cash[1] = 0
    r = w.run(CHARSHUI)
    case("pi=0、cash=0 ⇒ 0 > 0 不成立 ⇒ 0", r.ret, 0)

    # ── [A6] ★★ 支 B 不 break：最后一个合格者赢 ────────────────
    print("\n[A6] ★★ 支 B **没有 break**：命中后继续扫 ⇒ 取「下标最大的合格者」（不是第一个）")
    w.clear()
    w.me = 0
    w.vis_players(1, 2)
    w.rich(1, 2)
    r = w.run(CHARSHUI)
    case("★★ p1、p2 都合格 ⇒ 取 **p2**（0x8004），不是 p1", r.p0, 0x8004)

    w.clear()
    w.me = 0
    w.vis_players(1, 2, 3)
    w.rich(1, 2, 3)
    r = w.run(CHARSHUI)
    case("★★ p1/p2/p3 都合格 ⇒ 取 p3（0x8008）", r.p0, 0x8008)

    w.clear()
    w.me = 0
    w.vis_players(1, 2, 3)
    w.cash[1] = 10 ** 6
    w.cash[2] = 10 ** 6
    w.cash[3] = 0                                # 最后一个不合格
    r = w.run(CHARSHUI)
    case("★★ p1/p2 合格、p3 不合格 ⇒ 取 p2 ⇒ 0x8004（既是「取最后」也是「不是取最大下标」）",
         r.p0, 0x8004)

    w.clear()
    w.me = 3                                     # 当前玩家 3 ⇒ mark 里没有他自己
    w.vis_players(0, 1)
    w.rich(0, 1)
    r = w.run(CHARSHUI)
    case("me=3、p0/p1 合格 ⇒ 取 p1（0x8002）", r.p0, 0x8002)

    # ── [A7] 支 B 的人数上界（[0x499114]）──────────────────────
    print("\n[A7] ★ 支 B 的上界是 `[0x499114]`（人数）：越界的位标了也不选")
    w.clear()
    w.me = 0
    w.num_players = 2
    w.vis_players(3)                             # 只标了 p3（越界）
    w.rich(3)
    r = w.run(CHARSHUI)
    case("★ num_players=2、只有 p3 可见且有钱 ⇒ 0（循环扫不到 p3）", r.ret, 0)

    w.clear()
    w.me = 0
    w.num_players = 4
    w.vis_players(3)
    w.rich(3)
    r = w.run(CHARSHUI)
    case("  同一构造、num_players=4 ⇒ 命中 0x8008（对照上一条）", r.p0, 0x8008)

    w.clear()
    w.me = 0
    w.num_players = 1                            # 只剩自己
    w.vis_players(1)
    w.rich(1)
    r = w.run(CHARSHUI)
    case("num_players=1 ⇒ 只有自己 ⇒ 0", r.ret, 0)

    # ── [A8] 目标编码 = 0x8000 | (1<<p)，0 基玩家 ─────────────
    print("\n[A8] 目标编码 `0x8000 | (1 << p)`，p 是 **0 基玩家下标**")
    for p, want in [(0, 0x8001), (1, 0x8002), (2, 0x8004), (3, 0x8008)]:
        w.clear()
        w.me = (p + 1) % 4                       # 保证 p 不是自己
        w.num_players = 4
        w.vis_players(p)
        w.rich(p)
        r = w.run(CHARSHUI)
        case(f"玩家 {p} 命中 ⇒ 0x8000|(1<<{p}) = 0x{want:04x}", r.p0, want)

    w.clear()
    w.me = 0
    w.vis_players(2)
    w.rich(2)
    r = w.run(CHARSHUI)
    case("★ 编码高位 = 0x8000、低 4 位恰一个 bit", (r.p0 >> 4, bin(r.p0 & 0xF).count("1")),
         (0x800, 1))

    # ── [A9] 返回值集合 ────────────────────────────────────────
    print("\n[A9] 返回值恒为 0 或 1（包含支 A / 支 B / 无目标三种）")
    seen = set()
    w.clear(); seen.add(w.run(CHARSHUI).ret)                       # 无目标
    w.clear(); w.vis_players(1); w.rich(1); seen.add(w.run(CHARSHUI).ret)   # 支 B
    w.clear(); w.hostility = [0, 9, 0, 0]; w.vis_players(1); w.rich(1)
    seen.add(w.run(CHARSHUI).ret)                                  # 支 A
    case("三种情形 ⇒ 返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    # ── [A10] 判据宽度：原版是 32 位有符号乘法 ─────────────────
    print("\n[A10] ★ 判据宽度：`30000×pi` / `50000×pi` 在原版是 **32 位有符号** 乘法（会回绕）")
    w.clear()
    w.vis_players(1)
    w.cash[1] = 0
    w.price = 42949                               # 50000×42949 = 2147450000 < 2^31（不回绕）
    r = w.run(CHARSHUI)
    case("pi=42949、cash=0 ⇒ 0（门槛 2147450000 仍为正）", r.ret, 0)

    w.clear()
    w.vis_players(1)
    w.cash[1] = 0
    w.price = 42950                               # 50000×42950 = 2147500000 ⇒ 回绕成负数
    r = w.run(CHARSHUI)
    case("★★ pi=42950、cash=0 ⇒ 命中（`50000×pi` 回绕成 −2147467296）", r.p0, 0x8002)

    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]                    # 最恨 p1
    w.vis_players(1, 2)
    w.cash = [0, 0, 0, 0]
    w.price = 71582                               # 30000×71582 = 2147460000（正）⇒ 支 A 不触发
    r = w.run(CHARSHUI)
    case("★★ pi=71582、全员现金 0 ⇒ 支 A 因 30000×pi 仍为正面跳过 ⇒ 兜底（回绕）取末位 p2",
         r.p0, 0x8004)

    w.clear()
    w.me = 0
    w.hostility = [0, 5, 0, 0]
    w.vis_players(1, 2)
    w.cash = [0, 0, 0, 0]
    w.price = 71583                               # 30000×71583 = 2147490000 ⇒ 回绕成负数
    r = w.run(CHARSHUI)
    case("★★ pi=71583、全员现金 0 ⇒ 支 A 因 `30000×pi` 回绕成负而**无条件**命中 p1（0x8002）",
         r.p0, 0x8002)

    # ============================================================
    #  [B] 同盟卡 0x4207cc
    # ============================================================
    print("\n" + "=" * 84)
    print("[B] 同盟卡 0x4207cc（卡 29）：候选 = 可见 ∩ ¬自己 ∩ ¬最恨 ∩ 活着 ∩ ¬已同盟；取地產最多者")
    print("=" * 84)

    # ── [B1] 输出槽契约 ────────────────────────────────────────
    print("[B1] 输出槽：只写 0x48be58；0x48be60 = 可见表项数；0x48be5c / 0x48be64 不碰")
    w.clear()
    r = w.run(TONGMENG)
    case("空可见表 ⇒ 返回 0（候选为空，提前返回）", r.ret, 0)
    case("  0x48be58 保持哨兵", r.p0, SENTINEL)
    case("  0x48be5c 保持哨兵", r.p1, SENTINEL)
    case("  0x48be64 保持哨兵", r.p3, SENTINEL)
    case("  0x48be60 = 可见表项数 0", r.p2, 0)

    w.clear()
    w.vis = [0x8000 | 2, 0x0001]
    r = w.run(TONGMENG)
    case("★ 0x48be60 = 可见表项数 2（不是候选数）", r.p2, 2)

    # ── [B2] 候选筛除 ──────────────────────────────────────────
    print("\n[B2] 候选筛除：`p==cur`、`p==hated`、`alive==0`、`allied==cur+1` 四道闸")
    w.clear()
    w.vis_players(0)                             # 只有我自己
    w.land(1, 1)
    r = w.run(TONGMENG)
    case("★ 只有自己的位 ⇒ 候选空 ⇒ 0", r.ret, 0)
    case("  候选空时 0x48be58 仍是哨兵（在 best 扫描之前就返回）", r.p0, SENTINEL)

    w.clear()
    w.hostility = [0, 7, 0, 0]                   # 最恨 p1
    w.vis_players(1)                             # p1 是唯一可见对手
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("★ p1 = 最恨的人 ⇒ 不进候选 ⇒ 0", r.ret, 0)

    w.clear()
    w.alive[1] = 0
    w.vis_players(1)
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("★ p1 已死（alive=0）⇒ 不进候选 ⇒ 0", r.ret, 0)

    w.clear()
    w.allied[1] = 1                              # = cur + 1 ⇒ 已和我同盟
    w.vis_players(1)
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("★ p1 的 +0x41 == cur+1（已同盟）⇒ 不进候选 ⇒ 0", r.ret, 0)

    w.clear()
    w.allied[1] = 0                              # 未同盟
    w.vis_players(1)
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("  p1 的 +0x41 == 0（未同盟）⇒ 进候选 ⇒ 命中 0x8002", r.p0, 0x8002)

    w.clear()
    w.allied[1] = 2                              # 与别的玩家同盟，不是和我
    w.vis_players(1)
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("★ p1 的 +0x41 == 2（与**别人**同盟）⇒ 仍进候选 ⇒ 0x8002", r.p0, 0x8002)

    w.clear()
    w.me = 2                                     # me+1 = 3
    w.allied[0] = 3
    w.vis_players(0)
    w.land(1, 1)
    r = w.run(TONGMENG)
    case("★ me=2（me+1=3）：p0 的 +0x41 == 3 ⇒ 跟我同盟 ⇒ 0（比的是 me+1，不是常量 1）", r.ret, 0)

    w.clear()
    w.me = 2
    w.allied[0] = 1                              # 只与玩家 0 自己同盟（= p0+1），不是 me+1
    w.vis_players(0)
    w.land(1, 1)
    r = w.run(TONGMENG)
    case("  me=2：p0 的 +0x41 == 1（≠ me+1=3）⇒ 进候选 ⇒ 0x8001", r.p0, 0x8001)

    w.clear()
    w.vis = [0x0002]                             # 缺 0x8000
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("无 0x8000 位 ⇒ 候选空 ⇒ 0", r.ret, 0)

    w.clear()
    w.vis = [0x8000 | 0x0010]                    # 只有 bit4
    w.land(1, 2)
    r = w.run(TONGMENG)
    case("★ 低 4 位 = 0（只置 bit4）⇒ 候选空 ⇒ 0", r.ret, 0)

    w.clear()
    w.vis = [0x8000 | 0x000A]                    # p1 + p3
    w.land(1, 2)
    w.land(2, 2)                                 # 平手 ⇒ 取小下标 p1
    r = w.run(TONGMENG)
    case("★★ 一格多玩家位 ⇒ p1、p3 都进候选（不是只取最低位）", r.p0, 0x8002)

    # ── [B3] best 选取：地產 + 設施计数，严格最大 ──────────────
    print("\n[B3] best：`地產记录数 + 設施记录数` **严格**最大（平手取小下标）；只用 1 基 owner 计数")
    w.clear()
    w.vis_players(1, 2)
    w.land(1, 2).land(2, 2).land(3, 3)           # p1 两块、p2 一块
    r = w.run(TONGMENG)
    case("地產：p1 两块 vs p2 一块 ⇒ best = p1 ⇒ 0x8002", r.p0, 0x8002)

    w.clear()
    w.vis_players(1, 2)
    w.fac(1, 2).fac(2, 2).land(1, 3)             # p1 两块設施、p2 一块地
    r = w.run(TONGMENG)
    case("★ 設施也计入：p1 两块設施 vs p2 一块地 ⇒ best = p1 → 0x8002", r.p0, 0x8002)

    w.clear()
    w.vis_players(1, 2)
    w.land(1, 2).fac(1, 2).land(2, 3).land(3, 3)  # p1 = 1 地 + 1 設 = 2；p2 = 2 地 = 2
    r = w.run(TONGMENG)
    case("★ 两种记录**合计**：2 vs 2 平手 ⇒ 取小下标 p1（严格 > 才替换）", r.p0, 0x8002)

    w.clear()
    w.vis_players(1, 2)
    w.land(1, 2).land(2, 2).land(3, 3).land(4, 3).land(5, 3)
    r = w.run(TONGMENG)
    case("p1 两块、p2 三块 ⇒ best = p2 ⇒ 0x8004", r.p0, 0x8004)

    w.clear()
    w.me = 0
    w.vis_players(1, 2, 3)
    w.land(1, 1)                                 # = me+1 ⇒ 记给自己（best 扫描时跳过 self）
    w.land(2, 3).land(3, 3)                      # p2 两块
    r = w.run(TONGMENG)
    case("★ owner == me+1 的地只算给「自己」，而 best 扫描跳过 cur ⇒ best = p2", r.p0, 0x8004)

    w.clear()
    w.alive[2] = 0                               # p2 死了但地最多
    w.vis_players(1, 3)
    w.land(1, 3).land(2, 3).land(3, 2)           # p2 两块、p1 一块
    r = w.run(TONGMENG)
    case("★ best 扫描跳过死者：p2 两块但已死 ⇒ best = p1 ⇒ 0x8002", r.p0, 0x8002)

    w.clear()
    w.hostility = [0, 0, 9, 0]                   # 最恨 p2
    w.vis_players(1)
    w.land(1, 3).land(2, 3)                      # p2 两块（= best），p1 一块
    r = w.run(TONGMENG)
    case("★★ 最恨的人也参与 best 比较：p2 两块最多 ⇒ best = p2，但 p2 不在候选 ⇒ 0", r.ret, 0)
    case("  此时 0x48be58 不被写", r.p0, SENTINEL)

    w.clear()
    w.allied[2] = 1                              # p2 已和我同盟
    w.vis_players(1)
    w.land(1, 3).land(2, 3)                      # p2 两块最多
    r = w.run(TONGMENG)
    case("★★ 已同盟的人也参与 best 比较：best = p2，但 p2 不在候选 ⇒ 0", r.ret, 0)

    w.clear()
    w.vis_players(1)
    r = w.run(TONGMENG)                          # 有候选但谁都没地
    case("★ 谁都没有地產/設施 ⇒ best_p = −1 ⇒ 不在候选 ⇒ 0", r.ret, 0)
    case("  且 0x48be58 保持哨兵", r.p0, SENTINEL)

    # ── [B4] best 扫描的人数上界与「记录从 1 起」────────────────
    print("\n[B4] ★ best 扫描上界 = `[0x499114]`；★ 地產/設施表都从**记录 1** 开始数（记录 0 不读）")
    w.clear()
    w.num_players = 2
    w.me = 0
    w.vis_players(1, 3)
    w.land(1, 2).land(2, 4).land(3, 4).land(4, 4)  # p1 一块、p3 三块（越界）
    r = w.run(TONGMENG)
    case("★ num_players=2、p3 地最多 ⇒ 越界不选 ⇒ best = p1 ⇒ 0x8002", r.p0, 0x8002)

    w.clear()
    w.num_players = 4
    w.me = 0
    w.vis_players(1, 3)
    w.land(1, 2).land(2, 4).land(3, 4).land(4, 4)
    r = w.run(TONGMENG)
    case("  同一构造、num_players=4 ⇒ best = p3 ⇒ 0x8008（对照上一条）", r.p0, 0x8008)

    w.clear()
    w.num_lands = 0                              # 地產循环一次都不进
    w.land(0, 2)                                 # 记录 **0** 写归属
    w.vis_players(1)
    r = w.run(TONGMENG)
    case("★★ num_lands=0、记录 0 有归属 ⇒ 计数 0 ⇒ 0（记录 0 永远不被读）", r.ret, 0)

    w.clear()
    w.num_lands = 1
    w.land(1, 2)                                 # 记录 1 才被读
    w.vis_players(1)
    r = w.run(TONGMENG)
    case("★★ 同一归属写在记录 **1**、num_lands=1 ⇒ 计数 1 ⇒ 0x8002", r.p0, 0x8002)

    w.clear()
    w.num_facs = 0
    w.fac(0, 2)
    w.vis_players(1)
    r = w.run(TONGMENG)
    case("★ 設施记录 0 同样不被读（num_facs=0）⇒ 0", r.ret, 0)

    w.clear()
    w.num_facs = 1
    w.fac(1, 2)
    w.vis_players(1)
    r = w.run(TONGMENG)
    case("★ 設施记录 1 被读（num_facs=1）⇒ 0x8002", r.p0, 0x8002)

    # ── [B5] 终判：best 必须出现在候选表里 ─────────────────────
    print("\n[B5] 终判：`best_p` 必须**同时**在候选表里（可见的那一份名单）")
    w.clear()
    w.vis_players(1)
    w.land(1, 2)                                 # p1 一块；候选 = {p1}
    r = w.run(TONGMENG)
    case("best p1 在候选里 ⇒ 返回 1", r.ret, 1)
    case("  目标 = 0x8000|(1<<1) = 0x8002", r.p0, 0x8002)

    w.clear()
    w.vis_players(1)
    w.land(1, 3).land(2, 3)                      # p2 两块（best）但不可见
    r = w.run(TONGMENG)
    case("★ best = p2 但 p2 不在画面 ⇒ 0（不能选看不见的人）", r.ret, 0)
    case("  0x48be58 保持哨兵", r.p0, SENTINEL)

    w.clear()
    w.vis_players(1, 2)
    w.land(1, 3).land(2, 3).land(3, 4)           # p2 三块最多且可见
    r = w.run(TONGMENG)
    case("  可见的 best = p2 ⇒ 0x8004", r.p0, 0x8004)

    w.clear()
    w.vis_players(1, 2, 3)
    w.land(1, 3).land(2, 3).land(3, 4)
    r = w.run(TONGMENG)
    case("★ best 在候选表的**最后一个**位置也照样命中（成员判定与顺序无关）", r.p0, 0x8004)

    w.clear()
    w.price = 999                                # 同盟卡完全不用 price_index
    w.vis_players(1, 2)
    w.land(1, 3).land(2, 3).land(3, 4)
    r = w.run(TONGMENG)
    case("★ price_index=999 与上上条（pi=1）结果一致 ⇒ 同盟卡不读物價指數", r.p0, 0x8004)

    w.clear()
    w.price = 0
    w.vis_players(1, 2)
    w.land(1, 3).land(2, 3).land(3, 4)
    r = w.run(TONGMENG)
    case("★ price_index=0 也一致", r.p0, 0x8004)

    # ── [B6] 目标编码与返回值集合 ──────────────────────────────
    print("\n[B6] 目标编码 `0x8000 | (1 << p)`（0 基玩家）；返回值恒为 0/1")
    for p, want in [(0, 0x8001), (1, 0x8002), (2, 0x8004), (3, 0x8008)]:
        w.clear()
        w.me = (p + 1) % 4
        w.num_players = 4
        w.vis_players(p)
        w.land(1, p + 1)                         # ★ owner 是 **1 基**：p+1
        r = w.run(TONGMENG)
        case(f"玩家 {p}（owner={p + 1}）命中 ⇒ 0x{want:04x}", r.p0, want)

    w.clear()
    w.me = 3
    w.vis_players(0)
    w.land(1, 1)                                 # owner 1 ⇒ 玩家 0
    r = w.run(TONGMENG)
    case("★ owner=1 记给 0 基玩家 0（不是「无主」也不是玩家 1）", r.p0, 0x8001)

    seen = set()
    w.clear(); seen.add(w.run(TONGMENG).ret)
    w.clear(); w.vis_players(1); w.land(1, 2); seen.add(w.run(TONGMENG).ret)
    w.clear(); w.vis_players(1); w.land(1, 3); seen.add(w.run(TONGMENG).ret)
    case("  三种情形 ⇒ 返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 84}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
