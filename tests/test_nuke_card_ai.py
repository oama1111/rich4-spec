#!/usr/bin/env python3
"""
通道 2 差分测试 · **道具 13 核子飛彈的 AI 判定**（`0x00421E62`，862 B）

复刻侧对应 `packages/core/src/ai/tool-policy.ts`（`HANDLERS` / `AI_NEVER_USES`）。
该函数是 AI 出道具跳表 `0x475324` 的成员（entry 43），**没有 `call` 调用者**
（`gen/functions.json` 的 `callers` 是 `[]`），故用
`rich4-remake/tools/disasm.py va <地址>` 按需反汇编。

真实尺寸：`0x421e62..0x4221bf`（`0x4221bf ret`）⇒ **862 B**，与 `functions.json` 一致。

═══════════════════════════════════════════════════════════════════════
Q-TOOL-3 裁决（本文件的核心结论）
═══════════════════════════════════════════════════════════════════════
问题（`docs/known-deviations.md` 的 Q-TOOL-3）：核子飛彈 AI 判定里
`a0b1(x, y, -1)` 的半径 −1 若 = 全图，则「我在爆风内」恒真 ⇒ 原版 AI **永不发核彈**；
remake 因此把 13 放进 `AI_NEVER_USES`。

机器码裁决：**半径 −1 属实，但「中止判据恒真」不成立 —— 原版 AI 会发核彈。**
决定性的三条：

1. **半径实参确实是 −1**：`0x00421f92 push -1`（设施支 `0x00421f9b` 也共用同一次）。
   差分实测：**每一次**爆风调用的第三参都是 `0xffffffff`（本文件 [D]/[J] 组逐次钉住）。
   —— 这一点 Q-TOOL-3 没说错。

2. **`0x40a0b1(x, y, r)` 不是 `0x40a45c(r)`**（两者常被混为一谈）。`0x40a45c` 是纯收集器；
   `0x40a0b1` 是「**以 (x,y) 为中心重建实体图** + 再收集」：
   * 它一进来就 `memset` 整张 440×440 的 word 实体图：
     `0x0040a108 push 0x5e880 / push 0 / mov ebx,[0x474938] / call 0x456f60`
     （`0x5e880 = 0x1b8 × 0x1b8 × 2`）；
   * 然后**只把格距在 ±0xe = ±14 格内的有主地块/設施写进去**：
     `0x0040a22d sar ebx,5 / 0x0040a232 sub ebx,[esp+0x14] / 0x0040a236 add ebx,0xe /
      0x0040a251 cmp ebx,0x1c / 0x0040a254 jg → 跳过`（y 同）；
   * 玩家标记**只写当前玩家一个**：`0x0040a1bb mov cl,[0x49910c] / 0x0040a1ca add ch,0x80`
     （即 `0x8000 | 1<<cur`），且被关押时不写（`0x0040a117 cmp dword [player+0x32],0 /
     0x0040a11f jne 0x40a206`）。
   ⇒ 半径 r 只决定**扫这张图的多大范围**（`0x0040a3e9 cmp edx,-1 / 0x0040a3f4 mov ebp,0x1b8`
   = 全图；否则 `2r × 2r`）——**图里本来就只有候选周围那 ±14 格**。
   `-1` 是「把刚建好的那一窗全要了」，不是「全地图的地产」。

3. 于是中止判据 `0x0040a1bc..0x0040a1dc` 的 `test bh,0x80`
   （`0x00421fd4 mov bx,word[0x48b8c4+ebp*2] / 0x00421fe2 test bh,0x80 /
    0x00421fe7 mov [esp+0x414],1`）的实际语义是
   **「我的棋子落在候选 ±14 格（448px）内」**，不是恒真。
   候选是随机挑的「别人的有等级地产」，完全可能离我 448px 以外 ⇒ 中止判据可假；
   接着的两条判据（我的实体数 ÷ 对方、我的等级和 ÷ 对方，都 `< 1/(存活数+2)`）
   在「爆风里没有我的产业」时就是 `0 < 阈` ⇒ **发**（`0x0042213a` 写 `[0x48be64] = id`、
   `0x00422146 mov [esp+0x410],1`）。

**差分实证**：本文件 [Q] 组用「按 `0x40a0b1` 的建图口径算出来的爆风表」直接对打：
同一个候选 —— 我在 ±14 格内 ⇒ 弃（ret=0）；我在 448px 外、窗里只有对方产业 ⇒
**ret=1 且 `[0x48be64]` = 候选格值**。即中止判据可假、原版会发核彈。

**remake 裁决 = DISCREPANCY**：
* `packages/core/src/ai/tool-policy.ts:528-532` 的注释把 `a0b1(x,y,-1)` 读成
  「半径 −1 = 全图 ⇒ 我在爆风内恒真」，**这是把 AI 侧的 `0x40a0b1` 与效果侧的
  `damage_area` `0x40ac7b`（它才把半径直接转交 `0x40a45c(r)`，`0x0040ac95`）混为一谈**；
* `tool-policy.ts:534 AI_NEVER_USES = [10, 13]` 因此少了 13 号（`HANDLERS` 也没有
  `hedan`，见 `tool-policy.ts:511-523`）。
* 后果：原版电脑会放核子飛彈（清掉候选窗内对方的产业），remake 电脑永远不放 ⇒
  玩家可观察的 AI 行为差异。修法：补 `hedan` handler（候选 = 别人的有等级住宅/設施，
  ⩽10 次 `rand()%n`；中止 = 我的棋子落在候选 ±448px 内；否则两个比值都
  `< 1/(存活数+2)` 就发），并把 13 从 `AI_NEVER_USES` 撤掉。
* 效果侧的 `rules/tool-effects.ts:251 NUKE_RADIUS = -1`（`damage_area` 的全图支）
  **没错**，错的只是「拿效果侧半径解释 AI 侧扫描」。

（**没有**改任何 TS 代码；本条只出差分证据。）

═══════════════════════════════════════════════════════════════════════
源语义（逐条照 `0x00421e62` 的机器码读出来）
═══════════════════════════════════════════════════════════════════════
```
0x421e62():                                     ; @source 0x00421e62..0x004221bf（862 B）
    found = 0                                   ; [esp+0x410]
    cand = []; count = 0                        ; [esp+0x41c]
    for (i = 1; i <= [0x498e98]; i++):          ; ★ 地块 0 号永不入选（`lea eax,[base+0x34]`）
        L = &land[i]                            ; 步长 0x34
        if (L.owner == 0) continue              ; +0x19
        if (L.owner == [0x49910c] + 1) continue ; 我的地
        if (L.level == 0) continue              ; +0x1a
        cand[count++] = 0x7d0 + i
    for (i = 1; i <= [0x498e8c]; i++):          ; ★ 設施 0 号同样永不入选
        F = &fac[i]                             ; 步长 0x38
        ... 三道闸同上 ...
        cand[count++] = 0xfa0 + i
    if (count == 0) return 0                    ; ★ 0 候选 ⇒ 一次 rand 都不摇
    for (try = 0; try < 10 && !found; try++):   ; ★ 最多 10 次
        id = cand[rand() % count]               ; 0x0042216f；每次恰摇 1 次（n==1 也摇）
        (x, y) = int16 记录 +0/+2               ; 0x00421f82/0x00421f86（符号扩展）
        n = blast(0x40a0b1)(x, y, -1)           ; ★ 半径恒为 -1
        my = ot = myLv = otLv = 0; abort = 0
        for (k = 0; k < n; k++):
            w = word[0x48b8c4 + k*2]
            if (w & 0x8000) { abort = 1; break }        ; 玩家标记 ⇒ 放弃本候选
            if (0x4216ab(cur, w) == 1) { myLv += level(w); my++ }   ; 我的地/設施
            else                       { otLv += level(w); ot++ }
        if (!abort && my/ot < 1/(alive+2) && myLv/otLv < 1/(alive+2)):
            [0x48be64] = id; found = 1           ; ★ 输出 = 候选格值
    return found

alive = [0x499114] 以内 whoPlays(+0x15) != 0 的人数   ; 0x0040d2b4，再 +2
```
★ 原版两条编译产物怪癖（断言里都钉住）：
1. `my/ot` 或 `myLv/otLv` 为 `0/0` 时 x87 得 **QNaN**，`fcomp` 置 CF=1 ⇒ `jae` 不跳
   ⇒ **NaN 当「小于」用**：爆风表为空（或对方等级和恰为 0）时**会发**。
2. `0x4216ab` 的「不是我的」出口返回**调用方的 edx**（`0x00421714 mov eax,edx`）。
   在本函数的循环里，`edx` 在每次调用**之后**被 `0x0042201f mov edx,eax` 覆写成
   `(前一 id − 0xfa0) × 8`（首轮 = 爆风桩的 edx = 0），永远不等于 1
   ⇒ `cmp [esp+0x42c],1` 在本上下文里就是「是不是我的」。本测试的爆风桩出口显式
   `xor edx,edx`（与 `test_missile_target_ai.py` 同约定）。

═══════════════════════════════════════════════════════════════════════
打桩清单
═══════════════════════════════════════════════════════════════════════
| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a0b1` | 以 (x,y) 为中心重建 440×440 实体图（±14 格窗口、只画当前玩家标记）后再收进 `0x48b8c4`，返回项数 | **逐次**记录 `(x,y,r)` 三个实参，并从**预设的逐次列表**拷 word 进 `0x48b8c4`，返回项数；出口 `xor edx,edx` | ★ 半径实参**正是** Q-TOOL-3 的关键证据，必须记录；它的建图语义（±14 格）本文件用 [Q] 组的窗口模型显式复现，并在文档里给 `@source` |
| `0x00456f2d` | CRT `rand()` | 从**逐次序列**槽读值，并自增一个调用计数槽 | 本测试只钉「摇没摇、摇几次、`% n` 取到谁」，不钉 PRNG 位级（`test_prng.py` 另有 6/6） |
**真跑（绝不打桩）**：`0x4216ab`（「这格是不是我的」，同一支已被
`test_missile_target_ai.py` 的 [A9] 逐字节钉住）、`0x40d2b4`（存活人数）。

★ `0x40d2b4` 的循环上界是 `[0x499114]`（人数）：`setup()` 必须写它 + 各玩家
`whoPlays(+0x15)`，否则存活数恒 0 ⇒ 阈值 1/2 ⇒ 判据静默走另一条路
（见 `docs/verification.md` 工具限制第 5 条）。

★ 爆风表项若 bit15 未置且不是合法地块/設施格值（如 `0x7fff`），原版会拿
`(id−0xfa0)×0x38` 去读設施表**越界**（仿真里表现为 `UC_ERR_READ_UNMAPPED`）
⇒ 本文件的非中止项一律用合法格值；`0x8000` 及以上的项在越界之前就 `break`。

跑法：cd rich4-spec && .venv/bin/python tests/test_nuke_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
NUKE = 0x421E62               # 道具 13 核子飛彈 的 AI 判定（862 B）

# ── 真跑的被调方 ──
IS_MINE = 0x4216AB            # 「这格是不是我的」（0x7d0<w<0xfa0 地块 / 0xfa0<w<0x1770 設施）
ALIVE_COUNT = 0x40D2B4        # whoPlays != 0 的人数

# ── 打桩 ──
BLAST_SCAN = 0x40A0B1         # 以 (x,y) 为心重建实体图再收集
PRNG = 0x456F2D               # CRT rand

# ── 全局 ──
CUR = 0x49910C                # 当前玩家（0 基）
NUM_PLAYERS = 0x499114        # ★ 人数（0x40d2b4 的循环上界）
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NUM_LANDS = 0x498E98
NUM_FACS = 0x498E8C
VIS_LIST = 0x48B8C4           # 爆风表（word 数组）
OUT_PARAM = 0x48BE64          # AI 输出参数（= 候选格值）

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO = 0x15                  # byte：whoPlays（0 = 不在场）

LAND_STRIDE, L_OWNER, L_LEVEL = 0x34, 0x19, 0x1A
FAC_STRIDE, F_OWNER, F_LEVEL = 0x38, 0x19, 0x1A
LAND_X, LAND_Y = 0x00, 0x02   # word（int16）
FAC_X, FAC_Y = 0x00, 0x02

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0

# ── 暂存区布局（★ 与所有表错开；桩的源区也不能压在表上） ──
S = SCRATCH_BASE
LANDS = S + 0x3000
FACS = S + 0x6000
BSRC = [S + 0x8400 + i * 0x80 for i in range(16)]      # 逐次爆风表数据源
BLAST_PTR_SEQ = S + 0x140      # 16 × dword：逐次源指针
BLAST_CNT_SEQ = S + 0x1C0      # 16 × dword：逐次项数
BX_SEQ, BY_SEQ, BR_SEQ = S + 0x300, S + 0x340, S + 0x380   # 逐次记录的实参
RAND_SEQ = S + 0x200           # 16 × dword：rand 返回值序列
BCALLS, BLASTCNT = S + 0x1A0, S + 0x1A4
RAND_IDX = S + 0x120

SENTINEL = 0x5A5A5A5A
NULL = 0xFFFFFFFF             # −1（半径实参）
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<68} 实际 {got!s:<14} 期望 {want!s}")
    return ok


# ─────────────────────────────────────────────────────────────────────
# 桩
# ─────────────────────────────────────────────────────────────────────
def _rand_stub() -> bytes:
    """eax = RAND_SEQ[min(idx,15)]；idx++。"""
    return (b"\xA1" + struct.pack("<I", RAND_IDX)                    # mov eax,[RAND_IDX]
            + b"\x8B\x0C\x85" + struct.pack("<I", RAND_SEQ)          # mov ecx,[eax*4+SEQ]
            + b"\xFF\x05" + struct.pack("<I", RAND_IDX)              # inc dword [RAND_IDX]
            + b"\x89\xC8"                                            # mov eax,ecx
            + b"\xC3")


def _blast_stub() -> bytes:
    """记录 (x, y, r) 三个实参；按调用序取一张预设表拷进 0x48b8c4；返回项数。

    必须 pushad/popad 包住（被测函数把 myCount/mySum/otCount/otSum 放在
    ebp/edi/esi 里），且返回值 / edx 只能在 `popad` **之后**写。
    """
    code = b"\x60"                                                   # pushad
    # ★ 先把 esi 换成调用序下标 —— 调用方的 esi 是候选的 **y 坐标**（0x00421f94
    #   `mov esi,[esp+0x42c]`），拿它当索引会写飞。
    code += b"\x8B\x35" + struct.pack("<I", BCALLS)                  # mov esi,[BCALLS]
    code += b"\x83\xFE\x0F"                                          # cmp esi,15
    code += b"\x76\x05"                                              # jbe +5
    code += b"\xBE\x0F\x00\x00\x00"                                  # mov esi,15
    i = 0
    for slot in (BX_SEQ, BY_SEQ, BR_SEQ):
        # mov ecx,[esp+0x24+4i] / mov [esi*4+slot],ecx
        code += b"\x8B\x4C\x24" + struct.pack("<B", 0x24 + 4 * i)
        code += b"\x89\x0C\xB5" + struct.pack("<I", slot)
        i += 1
    code += b"\x8B\x0C\xB5" + struct.pack("<I", BLAST_CNT_SEQ)       # mov ecx,[esi*4+CNT]
    code += b"\x89\x0D" + struct.pack("<I", BLASTCNT)                # mov [BLASTCNT],ecx
    code += b"\x8B\x34\xB5" + struct.pack("<I", BLAST_PTR_SEQ)       # mov esi,[esi*4+PTR]
    code += b"\xBF" + struct.pack("<I", VIS_LIST)                    # mov edi,VIS_LIST
    code += b"\xF3\x66\xA5"                                          # rep movsw
    code += b"\xFF\x05" + struct.pack("<I", BCALLS)                  # inc dword [BCALLS]
    code += b"\x61"                                                  # popad
    code += b"\xA1" + struct.pack("<I", BLASTCNT)                    # mov eax,[BLASTCNT]
    code += b"\x31\xD2"                                              # xor edx,edx（见文档）
    code += b"\xC3"
    return code


# ─────────────────────────────────────────────────────────────────────
# 世界
# ─────────────────────────────────────────────────────────────────────
class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, _rand_stub())
        self.emu.patch(BLAST_SCAN, _blast_stub())
        self.clear()

    def clear(self):
        self.me = 0                      # [0x49910c]
        self.num = 4                     # [0x499114]
        self.who = [1, 1, 1, 1]          # whoPlays（存活判据）
        self.num_land = 0
        self.num_fac = 0
        self.lands = {}                  # idx → (x, y, owner, level)
        self.facs = {}
        self.blasts = [[]]               # 逐次爆风表
        self.seq = [0]                   # 逐次 rand 返回值
        return self

    def run(self):
        r = self.emu.call(NUKE, [], setup=self._setup)
        self.ret = r["eax"]
        self.out = self.emu.readu32(OUT_PARAM)
        self.rand_calls = self.emu.readu32(RAND_IDX)
        self.blast_calls = self.emu.readu32(BCALLS)
        n = max(1, min(16, self.blast_calls))
        self.bx = [self.emu.readu32(BX_SEQ + 4 * k) for k in range(n)]
        self.by = [self.emu.readu32(BY_SEQ + 4 * k) for k in range(n)]
        self.br = [self.emu.readu32(BR_SEQ + 4 * k) for k in range(n)]
        self.bx0 = self.bx[0]
        self.by0 = self.by[0]
        self.br0 = self.br[0]
        return self

    def _setup(self, e):
        e.write32(CUR, self.me)
        e.write32(NUM_PLAYERS, self.num)
        e.write32(LAND_TABLE_PTR, LANDS)
        e.write32(FAC_TABLE_PTR, FACS)
        e.write32(NUM_LANDS, self.num_land)
        e.write32(NUM_FACS, self.num_fac)
        e.write32(OUT_PARAM, SENTINEL)
        e.write32(BCALLS, 0)
        e.write32(BLASTCNT, 0)
        e.write32(RAND_IDX, 0)
        for slot in (BX_SEQ, BY_SEQ, BR_SEQ):
            e.write32(slot, SENTINEL)
        # ★ 跨 call() 保留 ⇒ 先清表（verification.md 工具限制第 3 条）
        e.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        e.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        e.write(VIS_LIST, b"\x00" * 128)
        bl = list(self.blasts) + [self.blasts[-1]] * 16
        for k in range(16):
            vals = bl[k]
            e.write(BSRC[k], b"".join(struct.pack("<H", v & 0xFFFF) for v in vals))
            e.write32(BLAST_PTR_SEQ + 4 * k, BSRC[k])
            e.write32(BLAST_CNT_SEQ + 4 * k, len(vals))
        sq = list(self.seq) + [self.seq[-1]] * 16
        e.write(RAND_SEQ, b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in sq[:16]))
        for p in range(4):
            e.write8(PLAYER_BASE + p * PLAYER_STRIDE + P_WHO, self.who[p] & 0xFF)
        for idx, (x, y, o, lv) in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            e.write16(b + LAND_X, x & 0xFFFF)
            e.write16(b + LAND_Y, y & 0xFFFF)
            e.write8(b + L_OWNER, o)
            e.write8(b + L_LEVEL, lv)
        for idx, (x, y, o, lv) in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            e.write16(b + FAC_X, x & 0xFFFF)
            e.write16(b + FAC_Y, y & 0xFFFF)
            e.write8(b + F_OWNER, o)
            e.write8(b + F_LEVEL, lv)


# ── Q-TOOL-3：0x40a0b1 建图口径的模型（只为造输入；判据本体由机器码钉） ──
TILE_SHIFT = 5                # 32px/格
WINDOW_HALF = 0x0E            # @source 0x0040a236 `add ebx,0xe` / 0x0040a251 `cmp ebx,0x1c`


def window_blast(cx, cy, props, me_xy, me_blocked, me):
    """按 `0x40a0b1` 的建图口径算出它这次会返回的爆风表。

    `props` 的键是**实体格值**（`0x7d0+i` / `0xfa0+i`），值是坐标；
    与 `0x40a0b1` 的建图循环（它写的正是格值）同一口径。

    0x0040a0b1 每次调用都先 `memset` 整张实体图（0x0040a108），再只把
    「格距 ±0xe 内」的有主地块/設施写进去（0x0040a225..0x0040a265），
    玩家标记**只写当前玩家**（0x0040a1bb `mov cl,[0x49910c]`，
    `0x0040a1ca add ch,0x80`）且被关押时不写（0x0040a117/0x0040a11f）。
    """
    out = []
    cx_t, cy_t = cx >> TILE_SHIFT, cy >> TILE_SHIFT
    for pid, (px, py) in props.items():
        if abs((px >> TILE_SHIFT) - cx_t) <= WINDOW_HALF and \
           abs((py >> TILE_SHIFT) - cy_t) <= WINDOW_HALF:
            out.append(pid)
    if not me_blocked and me_xy is not None:
        mx, my = me_xy
        if abs((mx >> TILE_SHIFT) - cx_t) <= WINDOW_HALF and \
           abs((my >> TILE_SHIFT) - cy_t) <= WINDOW_HALF:
            out.append(0x8000 | (1 << me))
    return out


def main():
    print("差分测试 · 核子飛彈 AI 判定 `0x421e62`（862 B）\n")
    w = World()

    # ═════════════════════════════════════════════════════════════════
    # [A] 候选收集：两趟循环 + 三道闸 + 返回值/消费时机
    # ═════════════════════════════════════════════════════════════════
    print("[A] 候选收集：地块 1..num_lands + 設施 1..num_facs，owner≠0 / owner≠me+1 / level≠0")

    w.clear(); w.lands = {}; w.facs = {}
    r = w.run()
    case("A1 无地无設施 ⇒ 0 候选", (r.ret, r.blast_calls, r.rand_calls), (0, 0, 0))
    case("A2 0 候选时 [0x48be64] 未被写（哨兵）", r.out, SENTINEL)
    case("A3 0 候选时爆风扫描一次都没被调（三个实参仍哨兵）",
         (r.bx0, r.by0, r.br0), (SENTINEL, SENTINEL, SENTINEL))

    w.clear(); w.num_land = 1; w.lands = {1: (100, 200, 2, 1)}; w.blasts = [[]]
    r = w.run()
    case("A4 唯一候选 = 1 号地（别人、level 1）⇒ 返回 1", r.ret, 1)
    case("A5 唯一候选也照摇 1 次 rand（`rand()%1`）", r.rand_calls, 1)
    case("A6 输出 [0x48be64] = 0x7d1", r.out, 0x7D1)
    case("A7 爆风扫描恰好被调 1 次", r.blast_calls, 1)

    w.clear(); w.num_land = 1; w.lands = {0: (0, 0, 2, 1)}
    r = w.run()
    case("A8 ★ 地块 0 号（0x7d0）永不入选 ⇒ 0 候选、不摇 rand、不扫爆风",
         (r.ret, r.rand_calls, r.blast_calls), (0, 0, 0))

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 1, 3)}
    r = w.run()
    case("A9 我自己的地（owner == [0x49910c]+1）⇒ 排除", (r.ret, r.rand_calls), (0, 0))

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 0, 3)}
    r = w.run()
    case("A10 无主地（owner == 0）⇒ 排除", (r.ret, r.rand_calls), (0, 0))

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 0)}
    r = w.run()
    case("A11 别人的地但 level == 0 ⇒ 排除", (r.ret, r.rand_calls), (0, 0))

    w.clear(); w.num_land = 1; w.lands = {2: (0, 0, 2, 1)}
    r = w.run()
    case("A12 ★ 循环上界：[0x498e98]=1 ⇒ 2 号地看不见 ⇒ 0 候选", (r.ret, r.rand_calls), (0, 0))
    w.num_land = 2
    r = w.run()
    case("A13 上界放到 2 ⇒ 看见 2 号地 ⇒ 候选 0x7d2", r.out, 0x7D2)

    w.clear(); w.me = 2; w.num_land = 2
    w.lands = {1: (0, 0, 3, 1), 2: (0, 0, 1, 1)}
    w.blasts = [[]]
    r = w.run()
    case("A14 ★ owner 判据是 cur+1：me=2 时 owner=3 是我的 ⇒ 只剩 0x7d2（owner 1）",
         r.out, 0x7D2)
    case("A15 同上：候选数 1 ⇒ 摇 1 次", r.rand_calls, 1)

    w.clear(); w.num_fac = 1; w.facs = {1: (0x1234, 0x2345, 3, 2)}; w.blasts = [[]]
    r = w.run()
    case("A16 設施 1 号（别人、level 2）⇒ 候选 0xfa1", (r.ret, r.out), (1, 0xFA1))
    w.clear(); w.num_fac = 1; w.facs = {0: (0, 0, 3, 2)}; w.blasts = [[]]
    r = w.run()
    case("A17 ★ 設施 0 号（0xfa0）永不入选", (r.ret, r.rand_calls, r.blast_calls), (0, 0, 0))
    w.clear(); w.num_fac = 1; w.facs = {1: (0, 0, 1, 2)}; w.blasts = [[]]
    r = w.run()
    case("A18 我的設施 ⇒ 排除", (r.ret, r.rand_calls), (0, 0))
    w.clear(); w.num_fac = 1; w.facs = {1: (0, 0, 3, 0)}; w.blasts = [[]]
    r = w.run()
    case("A19 設施 level == 0 ⇒ 排除", (r.ret, r.rand_calls), (0, 0))

    # ═════════════════════════════════════════════════════════════════
    # [B] 爆风扫描的实参：中心 = 候选记录 +0/+2，半径 = −1（Q-TOOL-3 关键证据）
    # ═════════════════════════════════════════════════════════════════
    print("\n[B] 爆风实参：中心 = 候选记录的 +0/+2（int16），★ 半径恒为 −1")

    w.clear(); w.num_land = 1; w.lands = {1: (100, 200, 2, 1)}; w.blasts = [[]]
    r = w.run()
    case("B1 ★★ 半径实参 = 0xffffffff（−1）", r.br0, NULL)
    case("B2 中心 = 地块记录的 (0x64, 0xc8)", (r.bx0, r.by0), (100, 200))

    w.clear(); w.num_fac = 1; w.facs = {1: (0x1234, 0x2345, 3, 2)}; w.blasts = [[]]
    r = w.run()
    case("B3 設施支的中心 = 設施记录的 (0x1234, 0x2345)", (r.bx0, r.by0), (0x1234, 0x2345))
    case("B4 ★ 設施支的半径同样是 −1", r.br0, NULL)

    w.clear(); w.num_land = 1; w.lands = {1: (0xFFFF, 0x8000, 2, 1)}; w.blasts = [[]]
    r = w.run()
    case("B5 ★ 坐标按 int16 符号扩展（0xffff → 0xffffffff，0x8000 → 0xffff8000）",
         (r.bx0, r.by0), (0xFFFFFFFF, 0xFFFF8000))
    case("B6 符号扩展不影响半径", r.br0, NULL)

    w.clear(); w.num_land = 2
    w.lands = {1: (0x100, 0x0, 2, 1), 2: (0x300, 0x0, 2, 1)}
    w.blasts = [[]]; w.seq = [1]
    r = w.run()
    case("B7 rand=1、2 候选 ⇒ 选 0x7d2 ⇒ 中心跟着变成 (0x300, 0)", (r.out, r.bx0), (0x7D2, 0x300))
    case("B8 该次半径仍为 −1", r.br0, NULL)

    w.clear(); w.num_land = 1; w.lands = {1: (0x11, 0x22, 2, 1)}
    w.blasts = [[0x8001]] * 3; w.seq = [0]
    r = w.run()
    case("B9 ★ 10 次上限内每一次爆风调用的半径都是 −1", r.br[:3], [NULL, NULL, NULL])
    case("B10 每一次的中心都是同一个候选 (0x11, 0x22)", (r.bx[:3], r.by[:3]),
         ([0x11] * 3, [0x22] * 3))

    # ═════════════════════════════════════════════════════════════════
    # [C] rand 规则：每次恰 1 次；`% 候选数`；0 候选不摇；10 次上限
    # ═════════════════════════════════════════════════════════════════
    print("\n[C] rand：每次恰摇 1 次、`rand() % 候选数`、0 候选不摇、最多 10 次")

    w.clear(); w.num_land = 3
    w.lands = {i: (i * 0x100, 0, 2, 1) for i in range(1, 4)}
    w.blasts = [[]]
    for rv, want in [(0, 0x7D1), (1, 0x7D2), (2, 0x7D3), (3, 0x7D1), (5, 0x7D3),
                     (4, 0x7D2), (12345, 0x7D1)]:
        w.seq = [rv]
        r = w.run()
        case(f"C1 rand={rv} % 3 ⇒ 候选 {want:#x}", r.out, want)
        case("C2   —— 恰好消费 1 次 rand", r.rand_calls, 1)

    w.clear(); w.num_land = 1; w.num_fac = 1
    w.lands = {1: (0x100, 0, 2, 1)}
    w.facs = {1: (0x900, 0, 2, 1)}
    w.blasts = [[]]
    w.seq = [0]
    r = w.run()
    case("C3 候选次序 = 先地块后設施：rand=0 ⇒ 0x7d1", r.out, 0x7D1)
    w.seq = [1]
    r = w.run()
    case("C4 rand=1 ⇒ 0xfa1（設施排在后面）", r.out, 0xFA1)
    case("C5 每次仍只摇 1 次", r.rand_calls, 1)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x8001]]
    w.seq = [0]
    r = w.run()
    case("C6 ★ 一直不成功 ⇒ 恰试 10 次、摇 10 次、扫爆风 10 次",
         (r.ret, r.rand_calls, r.blast_calls), (0, 10, 10))
    case("C7 10 次都没发 ⇒ 输出保持哨兵", r.out, SENTINEL)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x8001]] * 9 + [[]]
    w.seq = [0]
    r = w.run()
    case("C8 ★ 第 10 次才成功 ⇒ 返回 1（上限是「10 次」不是「9 次后放弃」）", r.ret, 1)
    case("C9   恰摇 10 次、扫 10 次", (r.rand_calls, r.blast_calls), (10, 10))
    case("C10  输出 = 0x7d1", r.out, 0x7D1)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x8001]] * 11
    w.seq = [0]
    r = w.run()
    case("C11 ★ 11 次可失败机会也只跑 10 次（第 11 次不存在）", r.rand_calls, 10)

    # ═════════════════════════════════════════════════════════════════
    # [D] 中止判据：爆风表里出现任何 0x80xx 玩家标记
    # ═════════════════════════════════════════════════════════════════
    print("\n[D] 中止判据：`test bh,0x80` —— 表里出现任何玩家标记就放弃本候选")

    for mk in (0x8000, 0x8001, 0x8002, 0x8004, 0x8008, 0x800F, 0xFFFF):
        w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
        w.blasts = [[mk]]; w.seq = [0]
        r = w.run()
        case(f"D1 爆风含 {mk:#06x} ⇒ 返回 0（不再看两个比值）", r.ret, 0)
        case("D2   输出未写（哨兵）", r.out, SENTINEL)

    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 2, 1)}
    w.blasts = [[0x7D1, 0x7D2, 0x8002]]; w.seq = [0]
    r = w.run()
    case("D3 ★ 标记在**最后一项** ⇒ 仍然中止（逐项扫，边扫边累加不算数）", r.ret, 0)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x7D1]]; w.seq = [0]
    r = w.run()
    case("D4 只有合法地块格值（bit15 未置）⇒ 不中止 ⇒ 发", r.ret, 1)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x8001], [0x7D1]]
    w.seq = [0]
    r = w.run()
    case("D5 ★★ 中止标志每候选重置：第 1 次弃、第 2 次（无标记）发 ⇒ 返回 1",
         (r.ret, r.out), (1, 0x7D1))
    case("D6   两次爆风调用都发生了", (r.rand_calls, r.blast_calls), (2, 2))

    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 2, 1)}
    w.blasts = [[0x8001], [0x7D2]]
    w.seq = [0, 1]
    r = w.run()
    case("D7 ★★ 第 1 候选被中止、换第 2 候选后发 ⇒ 输出 = 第 2 个候选 0x7d2",
         (r.ret, r.out), (1, 0x7D2))
    case("D8   摇 2 次、扫 2 次（中止不是全局放弃）", (r.rand_calls, r.blast_calls), (2, 2))

    # ═════════════════════════════════════════════════════════════════
    # [E] 发弹判据：my/ot 与 myLv/otLv 都要 < 1/(存活数+2)
    # ═════════════════════════════════════════════════════════════════
    print("\n[E] 发弹判据：两个比值都 `< 1/(存活数+2)`（严格小于；NaN 当「小于」）")

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x7D1]]; w.seq = [0]
    r = w.run()
    case("E1 mine=0 / other=1（比 0）⇒ 发", r.ret, 1)

    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 1, 1)}
    w.blasts = [[0x7D1, 0x7D2]]; w.seq = [0]
    r = w.run()
    case("E2 mine=1 / other=1 ⇒ 1 ≥ 1/6 ⇒ 不发", (r.ret, r.out), (0, SENTINEL))

    # 存活数 4 ⇒ 阈 1/6；mine=1、other=7、全 lv1 ⇒ 1/7 < 1/6
    w.clear(); w.num = 4
    w.num_land = 8
    w.lands = {i: (0, 0, 2, 1) for i in range(1, 8)}
    w.lands[8] = (0, 0, 1, 1)
    w.blasts = [[0x7D1 + k for k in range(8)]]; w.seq = [0]
    r = w.run()
    case("E3 1/7 < 1/6（存活 4）⇒ 发", (r.ret, r.out), (1, 0x7D1))

    # mine=1、other=5 ⇒ 1/5 = 0.2：存活 2 ⇒ 阈 1/4 ⇒ 发；存活 4 ⇒ 阈 1/6 ⇒ 不发
    for alive, want in [(2, 1), (4, 0)]:
        w.clear(); w.num = alive; w.who = [1] * alive + [0] * (4 - alive)
        w.num_land = 6
        w.lands = {i: (0, 0, 2, 1) for i in range(1, 6)}
        w.lands[6] = (0, 0, 1, 1)
        w.blasts = [[0x7D1 + k for k in range(6)]]; w.seq = [0]
        r = w.run()
        case(f"E4 mine/other=1/5（0.2）、存活 {alive}（阈 1/{alive + 2}）⇒ "
             f"{'发' if want else '不发'}", r.ret, want)

    # 相等：1/4 对阈 1/4 ⇒ `jae` 跳过 ⇒ 不发
    w.clear(); w.num = 2; w.who = [1, 1, 0, 0]
    w.num_land = 5
    w.lands = {i: (0, 0, 2, 1) for i in range(1, 5)}
    w.lands[5] = (0, 0, 1, 1)
    w.blasts = [[0x7D1 + k for k in range(5)]]; w.seq = [0]
    r = w.run()
    case("E5 ★ 恰好相等（1/4 vs 阈 1/4）⇒ 严格小于才发 ⇒ 不发", r.ret, 0)

    # 等级和比值单独卡住：mine=1 lv10 vs other=7 lv1
    w.clear(); w.num = 4
    w.num_land = 8
    w.lands = {i: (0, 0, 2, 1) for i in range(1, 8)}
    w.lands[8] = (0, 0, 1, 10)
    w.blasts = [[0x7D1 + k for k in range(8)]]; w.seq = [0]
    r = w.run()
    case("E6 ★ 数量比 1/7 过关、等级和比 10/7 = 1.43 不过 ⇒ 不发（第二条判据真的在）",
         r.ret, 0)

    # other=0：只有我的产业（桩允许）⇒ +inf ⇒ 不发
    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 1, 1)}
    w.blasts = [[0x7D2]]; w.seq = [0]
    r = w.run()
    case("E7 ★ 爆风里只有我的（other=0）⇒ 我的/0 = +inf ⇒ 不发", r.ret, 0)

    # 对方等级和 = 0 ⇒ 第二条比值 0/0 = NaN ⇒ 当「小于」⇒ 发（原版怪癖）
    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 2, 0)}
    w.blasts = [[0x7D2]]; w.seq = [0]
    r = w.run()
    case("E8 ★★ 对方等级和 0 ⇒ myLv/otLv = 0/0 = NaN，`jae` 不跳 ⇒ 当「小于」⇒ 发",
         r.ret, 1)

    # 空表 ⇒ 两个比值都是 NaN ⇒ 发（原版怪癖；真实路径上候选自己必在窗内，故不可达）
    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[]]; w.seq = [0]
    r = w.run()
    case("E9 ★★ 空爆风表（桩造）⇒ 0/0 = NaN ⇒ 发（原版 NaN 怪癖；真实路径上不可达）",
         (r.ret, r.out), (1, 0x7D1))

    # level 按各自步长读：設施 +0x1a、步长 0x38；mine=1 lv5 vs other=5 lv1 ⇒ 5/5=1 ≥ 阈
    w.clear(); w.num = 4; w.num_fac = 6
    w.facs = {i: (0, 0, 2, 1) for i in range(1, 6)}
    w.facs[6] = (0, 0, 1, 5)
    w.blasts = [[0xFA1 + k for k in range(6)]]; w.seq = [0]
    r = w.run()
    case("E10 ★ 設施等级按 0x38 步长读：myLv/otLv = 5/5 = 1 ⇒ 不发", r.ret, 0)

    # 存活数上界 = [0x499114]：num=2 时 2/3 号的 whoPlays 看不见 ⇒ 阈 1/4（而非 1/6）
    w.clear(); w.num = 2; w.who = [1, 1, 1, 1]
    w.num_land = 6
    w.lands = {i: (0, 0, 2, 1) for i in range(1, 6)}
    w.lands[6] = (0, 0, 1, 1)
    w.blasts = [[0x7D1 + k for k in range(6)]]; w.seq = [0]
    r = w.run()
    case("E11 ★★ 人数=2 ⇒ 阈 1/4；1/5 < 1/4 ⇒ 发（若上界读成 4 则阈 1/6 ⇒ 不发）",
         r.ret, 1)

    # 存活判据是**整字节** != 0（不是 &3）：who=0x10 仍算存活
    for who1, want in [(0x00, 1), (0x10, 0)]:
        w.clear(); w.num = 4; w.who = [1, who1, 0, 0]
        w.num_land = 9
        w.lands = {i: (0, 0, 2, 1) for i in range(1, 8)}
        w.lands[8] = (0, 0, 1, 1)
        w.lands[9] = (0, 0, 1, 1)
        w.blasts = [[0x7D1 + k for k in range(9)]]; w.seq = [0]
        r = w.run()
        case(f"E12 whoPlays[1]={who1:#04x}、mine/other=2/7 ⇒ 存活 {1 if who1 == 0 else 2} "
             f"⇒ {'发' if want else '不发'}（★★ 判据是整字节 != 0，不是 &3）",
             r.ret, want)

    # ═════════════════════════════════════════════════════════════════
    # [F] 返回值与输出参数
    # ═════════════════════════════════════════════════════════════════
    print("\n[F] 返回值 = found；[0x48be64] = 命中候选的格值")

    w.clear(); w.num_land = 2; w.num_fac = 1
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 2, 1)}
    w.facs = {1: (0, 0, 2, 1)}
    w.blasts = [[]]
    for rv, want in [(0, 0x7D1), (1, 0x7D2), (2, 0xFA1), (3, 0x7D1)]:
        w.seq = [rv]
        r = w.run()
        case(f"F1 rand={rv} % 3 ⇒ 输出 {want:#x}", r.out, want)
        case("F2   返回 1", r.ret, 1)

    w.clear(); w.num_land = 1; w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x8001]]; w.seq = [0]
    r = w.run()
    case("F3 不发时返回 0、输出哨兵", (r.ret, r.out), (0, SENTINEL))

    w.clear(); w.num_land = 2
    w.lands = {1: (0, 0, 2, 1), 2: (0, 0, 2, 1)}
    w.blasts = [[0x8001], [0x7D2]]; w.seq = [0, 1]
    r = w.run()
    case("F4 ★ 输出是**命中那一次**的候选（不是第一次尝试的）", r.out, 0x7D2)
    case("F5 返回 1", r.ret, 1)

    # ═════════════════════════════════════════════════════════════════
    # [G] 「我的」判据 = 0x4216ab（owner == cur+1；非我 → 调用方 edx ≠ 1）
    # ═════════════════════════════════════════════════════════════════
    print("\n[G] 「我的」= `0x4216ab(cur, w) == 1`（owner == cur+1）")

    w.clear(); w.me = 2; w.num_land = 2
    w.lands = {1: (0, 0, 3, 1), 2: (0, 0, 1, 1)}
    w.blasts = [[0x7D1]]; w.seq = [0]
    r = w.run()
    case("G1 me=2：owner=3 是「我的」⇒ mine=1/other=0 ⇒ +inf ⇒ 不发", r.ret, 0)

    w.clear(); w.me = 2; w.num_land = 1
    w.lands = {1: (0, 0, 1, 1)}
    w.blasts = [[0x7D1]]; w.seq = [0]
    r = w.run()
    case("G2 me=2：owner=1 不是我的 ⇒ other=1、mine=0 ⇒ 发", r.ret, 1)

    w.clear(); w.num_land = 1
    w.lands = {1: (0, 0, 2, 1)}
    w.blasts = [[0x7D1, 0x7D2]]
    w.num_land = 2
    w.lands[2] = (0, 0, 0, 0)          # 无主（0x4216ab 判「不是我的」）
    w.seq = [0]
    r = w.run()
    case("G3 无主地进爆风表 ⇒ 归 other 侧（不是「我的」，也不是中止）", r.ret, 1)

    # ═════════════════════════════════════════════════════════════════
    # [Q] Q-TOOL-3 实证：按 0x40a0b1 的建图口径造表，看中止判据可不可假
    # ═════════════════════════════════════════════════════════════════
    print("\n[Q] Q-TOOL-3：中止 = 「我的棋子在候选 ±14 格内」⇒ 可假 ⇒ 原版会发核彈")

    near, far = 64, 4480             # 2 格 / 140 格（32px/格）
    # 候选 140 格外，窗里只有对方产业（我的棋子进不了表）
    w.clear(); w.num_land = 1
    w.lands = {1: (far, far, 2, 1)}
    w.blasts = [window_blast(far, far, {0x7D1: (far, far)}, (0, 0), False, 0)]
    w.seq = [0]
    r = w.run()
    case("Q1 ★★ 候选在 140 格外（我的棋子进不了 0x40a0b1 的 ±14 格窗）⇒ 返回 1",
         r.ret, 1)
    case("Q2   [0x48be64] = 该候选 0x7d1", r.out, 0x7D1)
    case("Q3   ★ 这次爆风扫描的半径实参仍是 −1", r.br0, NULL)
    case("Q4   这次爆风表里确实没有玩家标记", window_blast(far, far, {0x7D1: (far, far)},
                                                          (0, 0), False, 0), [0x7D1])

    # 同一局，候选换成离我 2 格 ⇒ 我的标记 0x8001 进表 ⇒ 中止
    w.clear(); w.num_land = 1
    w.lands = {1: (near, 0, 2, 1)}
    w.blasts = [window_blast(near, 0, {0x7D1: (near, 0)}, (0, 0), False, 0)]
    w.seq = [0]
    r = w.run()
    case("Q5 ★★ 候选只离我 2 格 ⇒ 我的标记进表 ⇒ 中止 ⇒ 返回 0", r.ret, 0)
    case("Q6   该表 = [0x7d1, 0x8001]", window_blast(near, 0, {0x7D1: (near, 0)},
                                                    (0, 0), False, 0), [0x7D1, 0x8001])
    case("Q7   输出未写", r.out, SENTINEL)

    # 我在牢里/住店时 0x40a0b1 不画我的标记（0x40a117/0x40a11f）⇒ 不中止
    w.clear(); w.num_land = 1
    w.lands = {1: (near, 0, 2, 1)}
    w.blasts = [window_blast(near, 0, {0x7D1: (near, 0)}, (0, 0), True, 0)]
    w.seq = [0]
    r = w.run()
    case("Q8 ★ 同样 2 格，但我被关押（+0x32 != 0）⇒ 不画我的标记 ⇒ 不中止 ⇒ 返回 1",
         r.ret, 1)

    # 候选很远，但我在它旁边有一块地 ⇒ mine=1 / other=1 ⇒ 数量比不过关
    w.clear(); w.num_land = 2
    w.lands = {1: (far, far, 2, 1), 2: (far - 96, far, 1, 1)}
    props = {0x7D1: (far, far), 0x7D2: (far - 96, far)}
    w.blasts = [window_blast(far, far, props, (0, 0), False, 0)]
    w.seq = [0]
    r = w.run()
    case("Q9 ★ 候选很远但窗内有我的一块地 ⇒ mine=1/other=1 ⇒ 不是中止而是比值挡下",
         (r.ret, r.out), (0, SENTINEL))
    case("Q10  该表 = [0x7d1, 0x7d2]（我的 0x7d2 进了窗）",
         window_blast(far, far, props, (0, 0), False, 0), [0x7D1, 0x7D2])

    # 组合：两个候选，近的被中止、远的发 ⇒ 一回合内确实会发出核彈
    w.clear(); w.num_land = 2
    w.lands = {1: (near, 0, 2, 1), 2: (far, far, 2, 1)}
    props = {0x7D1: (near, 0), 0x7D2: (far, far)}
    w.blasts = [window_blast(near, 0, props, (0, 0), False, 0),
                window_blast(far, far, props, (0, 0), False, 0)]
    w.seq = [0, 1]
    r = w.run()
    case("Q11 ★★ 近候选被中止 → 换远候选 ⇒ 返回 1、输出 0x7d2（原版真的会发核彈）",
         (r.ret, r.out), (1, 0x7D2))
    case("Q12  两次爆风的半径都是 −1", r.br[:2], [NULL, NULL])
    case("Q13  两次的中心分别 = 两个候选的坐标",
         (r.bx[:2], r.by[:2]), ([near, far], [0, far]))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
