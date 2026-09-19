#!/usr/bin/env python3
"""
通道 2 差分测试 · **道具 7 飛彈 的 AI 判定**（`0x00421717`，272 B）
＋ 它调用的 **`select_one_active_player`**（`0x0040d31c`，89 B）

复刻侧对应：
  · `packages/core/src/ai/tool-policy.ts` 的 handler `feidan`
  · `packages/core/src/rules/toll-flow.ts` 的 `aiScapegoat`（同一支原版函数的**姊妹实现**）

两个函数都**没有 `call` 调用者被函数图收全**（`functions.json` 给 `0x421717` 的
`callers` 是 `[]`），故用 `rich4-remake/tools/disasm.py va <地址>` 按需反汇编。

源语义（逐条照 `0x00421717` 的机器码读出来）
------------------------------------------------
```
0x421717():
    [esp] = 0                                   ; 返回值局部量
    ebx = most_hated([0x49910c])                ; 0x40d2d3，**真跑**
    if (ebx == -1):
        ebx = select_one_active_player([0x49910c])   ; 0x40d31c，**真跑**
    if (ebx == -1): return 0                    ; ★ 两次都 −1 ⇒ 不用
    n = fill_visible_entities(-1)               ; 0x40a45c，**打桩**（填充 0x48b8c4）
    ; 第一趟：在可见表里找「目标玩家的 0x80xx 标记」
    for (i = 0; i < n && !found; i++):
        w = word[0x48b8c4 + i*2]
        if !(w & 0x8000): continue               ; bit15 必须置
        if !(w & 0x0f):   continue               ; 低 4 位必须非 0
        b = ctz4(w)                              ; 只在 bit0..3 里找最低置位
        if (b != ebx): continue
        [0x48be64] = w                           ; ★ 输出参数 = **整项词**
        found = 1
    if (!found): return 0                        ; ★ 目标的标记不在可见表 ⇒ 不用
    ; 第二趟：爆风扫描（中心 = **目标**的 +0x08/+0x0a，半径 = 0x64）
    n = blast_scan(x = word[target*0x68 + 0x496b70],
                   y = word[target*0x68 + 0x496b72], 0x64)   ; 0x40a0b1，**打桩**
    for (i = 0; i < n; i++):
        w = word[0x48b8c4 + i*2]
        if (w & 0x8000): return 0                ; ★ **任何**玩家标记（含我自己）⇒ 不用
        if (is_mine([0x49910c], w) == 1): return 0   ; ★ 我的地/設施 ⇒ 不用
    return 1
```
`is_mine` = `0x004216ab`（**真跑**）：`0x7d0 < w < 0xfa0` 取地块
（步长 `0x34`，owner 在 `+0x19`）、`0xfa0 < w < 0x1770` 取設施（步长 `0x38`，
owner 在 `+0x19`），`owner == player + 1` ⇒ 1。
★ 两端都是**严格**比较（`jle`/`jge`）⇒ 地块 0 号（`0x7d0`）与設施 0 号（`0xfa0`）
**永远判不出「我的」**。

★ 一条**原版自己的编译产物怪癖**（本测试 [A9] 组专门钉住）：
`0x4216ab` 的「不是我的」出口走 `0x421714 mov eax,edx / ret`，而**该路径上
没有任何一条指令写过 `edx`**（`edx` 是**调用方**带进来的 —— 逐字节核过
`0x4216ab..0x421716` 共 108 字节，无一处 `xor edx,edx` / `mov edx,…` 落在
「不是我的」分支上）。所以「不是我的」返回的是**调用方的 edx**，不是 0。
导弹调用点的判据是 `cmp eax,1`，因此**只要调用方的 edx 不等于 1，
判据就是「不是我的」**。

原版 `0x40a0b1` 出口的 edx 由它的收集循环决定（`0x40a427 jge 0x40a0a0` 是唯一
出口，循环里只有 `0x40a43f mov dx, word ptr [eax]` 动过 edx 的低 16 位、高 16 位
是瓦片下标）⇒ 实际不可能等于 1（否则飛彈会静默拒发）。**本测试不去猜这个值**，
而是把爆风桩的 **edx 显式置 0**（= 判据「只有 `== 1` 才算我的」），并把这条
「返回值 = 调用方 edx」的怪癖单列成 [A9] 直接驱动真身来钉住。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 填「可見實體表」`0x48b8c4`，返回**项数**；参数 `-1` = 全部可见 | 从数据槽拷 `[count]` 个 word 进 `0x48b8c4`，记下实参，返回 `[count]` | 视野口径差异 = **D-005**（remake 用 `inView`），不是本测试对象；本测试只驱动**导弹怎么读这张表** |
| `0x0040a0b1` | 爆风扫描：以 (x,y) 为心、半径 r 把范围内实体填进**同一张** `0x48b8c4`，返回项数 | ★ **独立**的源槽/计数槽；额外把 `(x, y, r)` 三个实参记进数据槽；出口显式 `xor edx,edx` | 与 `0x40a45c` 共用输出表 ⇒ **必须各自一套源槽**，否则第二趟会覆盖第一趟（§7.138(3)3）；记录实参正是为了钉住「中心 = 目标的 +0x08/+0x0a、半径 = 0x64」 |
| `0x00456f2d` | CRT `rand()` | 从数据槽读，并自增一个**调用计数**槽 | 本测试只钉「摇没摇、摇几次」与 `% n`，不钉 PRNG 位级（`test_prng.py` 另有 6/6） |

**真跑（绝不打桩）**：`0x40d2d3`（最恨的人）、`0x40d31c`（本测试对象 B）、
`0x4216ab`（「这格是不是我的」）—— 它们是本测试的判据本体。

★ `0x40d2d3`/`0x40d31c` 的循环上界都是 **`[0x499114]`（人数）**：
`setup()` 里必须写它，否则上界为 0 ⇒ 恒返回 −1 ⇒ 所有用例静默退化
（见 `docs/verification.md` 工具限制第 5 条）。

跑法：cd rich4-spec && .venv/bin/python tests/test_missile_target_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

# ── 被测函数 ──
MISSILE = 0x421717            # 道具 7 飛彈 的 AI 判定（272 B）
SELECT_ONE = 0x40D31C         # select_one_active_player（89 B）

# ── 真跑的被调方 ──
MOST_HATED = 0x40D2D3         # 最恨的人
IS_MINE = 0x4216AB            # 「这格是不是我的」

# ── 打桩 ──
VISIBLE_ENTITIES = 0x40A45C   # 可见实体表填充器
BLAST_SCAN = 0x40A0B1         # 爆风扫描（与上者共用输出表）
PRNG = 0x456F2D               # CRT rand

# ── 全局 ──
CUR = 0x49910C                # 当前玩家（0 基）
NUM_PLAYERS = 0x499114        # ★ 人数（两个遍历器的上界）
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y = 0x08, 0x0A         # word：屏幕坐标（爆风中心取的就是这两个）
P_WHO = 0x15                  # byte：whoPlays（0 = 不在场）
P_BLOCKING = 0x32             # dword：住店/消失/坐牢/住院 四个字节
P_SLEEP = 0x36                # byte：days_sleeping（**不在**那个 dword 里）
P_SLEEPWALK = 0x37            # byte：夢遊天數（**不在**那个 dword 里）
P_HOSTILITY = 0x4C            # dword[4]：对别人的敌意（`0x496bb4` = base + 0x4c）
VIS_LIST = 0x48B8C4           # 可见实体表 / 爆风表（**共用**）
MISSILE_PARAM = 0x48BE64      # 导弹 AI 的输出参数

LAND_PTR, FAC_PTR = 0x498E84, 0x498E88
LAND_STRIDE, L_OWNER = 0x34, 0x19
FAC_STRIDE, F_OWNER = 0x38, 0x19

# ── 暂存区布局（★ 与所有表错开；桩的源区也不能压在表上） ──
S = SCRATCH_BASE
LANDS = S + 0x3000
FACS = S + 0x6000
VIS_SRC = S + 0x8000          # 可见表数据源（word 数组）
BLAST_SRC = S + 0x8400        # ★ 爆风表**自己的**数据源
VIS_SRC_SLOT, VIS_COUNT, VIS_ARG = S + 0x100, S + 0x104, S + 0x108
BLAST_SRC_SLOT, BLAST_COUNT = S + 0x10C, S + 0x110
BLAST_X, BLAST_Y, BLAST_R = S + 0x114, S + 0x118, S + 0x11C
RAND_SLOT, RAND_CALLS = S + 0x120, S + 0x124

SENTINEL = 0x5A5A5A5A
RESULTS = []

MS = MISSILE_PARAM
WHO = P_WHO


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<72} 实际 {got!s:<12} 期望 {want!s}")
    return ok


def _rec_stub(arg_slots, src_slot, count_slot, zero_edx=False) -> bytes:
    """记下前 len(arg_slots) 个实参，再把 [src] 起的 [count] 个 word 拷进 0x48b8c4。

    必须 **pushad/popad** 包住（被调函数把目标玩家/计数放在 ebx/ebp/edi/esi 里），
    且返回值 / edx 只能在 `popad` **之后**写（否则被还原 —— 见 verification.md 的坑）。
    """
    code = b"\x60"                                              # pushad
    for i, slot in enumerate(arg_slots):
        code += (b"\x8B\x84\x24" + struct.pack("<I", 0x24 + 4 * i)   # mov eax,[esp+0x24+4i]
                 + b"\xA3" + struct.pack("<I", slot))                # mov [slot],eax
    code += b"\x8B\x0D" + struct.pack("<I", count_slot)          # mov ecx,[count]
    code += b"\x8B\x35" + struct.pack("<I", src_slot)            # mov esi,[src]
    code += b"\xBF" + struct.pack("<I", VIS_LIST)                # mov edi,LIST
    code += b"\xF3\x66\xA5"                                      # rep movsw
    code += b"\x61"                                              # popad
    code += b"\xA1" + struct.pack("<I", count_slot)              # mov eax,[count]
    if zero_edx:
        code += b"\x31\xD2"                                      # xor edx,edx
    code += b"\xC3"
    return code


class World:
    def __init__(self):
        self.emu = Emu()
        # rand()：读数据槽 + 自增调用计数
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.emu.patch(VISIBLE_ENTITIES,
                       _rec_stub([VIS_ARG], VIS_SRC_SLOT, VIS_COUNT))
        # ★ 爆风桩：自己的源/计数槽 + 记录 (x,y,r) + 出口 edx=0
        self.emu.patch(BLAST_SCAN,
                       _rec_stub([BLAST_X, BLAST_Y, BLAST_R],
                                 BLAST_SRC_SLOT, BLAST_COUNT, zero_edx=True))
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.me = 0
        self.num = 4
        self.who = [1, 1, 1, 1]
        self.xy = [(0, 0)] * 4
        self.host = [0, 0, 0, 0]
        self.pbytes = {}           # {玩家: {绝对偏移: 字节}}
        self.lands = {}            # 地块下标 → owner
        self.facs = {}             # 設施下标 → owner
        self.visible = []          # 0x40a45c 的输出
        self.blast = []            # 0x40a0b1 的输出
        self.rand = 0
        return self

    def hate(self, t, v):
        self.host[t] = v
        return self

    def at(self, p, x, y):
        self.xy[p] = (x, y)
        return self

    def byte(self, p, off, v=1):
        self.pbytes.setdefault(p, {})[off] = v
        return self

    def see(self, *vals):
        self.visible = list(vals)
        return self

    def boom(self, *vals):
        self.blast = list(vals)
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, self.num)      # ★ 上界类全局，必须写
        emu.write32(MS, SENTINEL)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write32(VIS_ARG, SENTINEL)          # 哨兵：用来断言"有没有被调"
        emu.write32(BLAST_X, SENTINEL)
        emu.write32(BLAST_Y, SENTINEL)
        emu.write32(BLAST_R, SENTINEL)
        emu.write32(VIS_SRC_SLOT, VIS_SRC)
        emu.write32(VIS_COUNT, len(self.visible))
        emu.write32(BLAST_SRC_SLOT, BLAST_SRC)
        emu.write32(BLAST_COUNT, len(self.blast))
        emu.write32(LAND_PTR, LANDS)
        emu.write32(FAC_PTR, FACS)
        # ★ 暂存区的写入跨 call() 保留 ⇒ 先整片清掉（verification.md 工具限制第 3 条）
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(VIS_LIST, b"\x00" * 128)
        emu.write(VIS_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.visible))
        emu.write(BLAST_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.blast))
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + WHO, self.who[p] & 0xFF)
            emu.write16(pb + P_X, self.xy[p][0])
            emu.write16(pb + P_Y, self.xy[p][1])
            for t in range(4):
                emu.write32(pb + P_HOSTILITY + t * 4, self.host[t])
            for off, v in self.pbytes.get(p, {}).items():
                emu.write8(pb + off, v)
        for idx, owner in self.lands.items():
            emu.write8(LANDS + idx * LAND_STRIDE + L_OWNER, owner)
        for idx, owner in self.facs.items():
            emu.write8(FACS + idx * FAC_STRIDE + F_OWNER, owner)

    def run(self):
        """驱动 0x421717"""
        r = self.emu.call(MISSILE, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(MS)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        self.blast_x = self.emu.readu32(BLAST_X)
        self.blast_y = self.emu.readu32(BLAST_Y)
        self.blast_r = self.emu.readu32(BLAST_R)
        self.vis_arg = self.emu.readu32(VIS_ARG)
        return self

    def run_select(self, arg):
        """驱动 0x40d31c(arg)"""
        r = self.emu.call(SELECT_ONE, [arg], setup=self._setup)
        self.ret = r["eax"]
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        return self


def main():
    print("差分测试 · 飛彈 AI 判定 `0x421717`（272 B）＋ select_one_active_player "
          "`0x40d31c`（89 B）\n")
    w = World()

    # ═════════════════════════════════════════════════════════════════
    # [A] 0x00421717 · 道具 7 飛彈 的 AI 判定
    # ═════════════════════════════════════════════════════════════════
    print("[A] 飛彈 `0x421717`：最恨的人 → 随机兜底 → −1 ⇒ 0 → 标记必须在可见表 → 爆风扫描")

    # ── A1 · 最恨的人优先，且这条支**不摇 rand** ──
    print("\n[A1] 最恨的人优先（`0x40d2d3`）")
    w.clear(); w.hate(1, 10); w.see(0x8002); w.rand = 2
    r = w.run()
    case("★ 最恨 1 号 ⇒ 取他的标记 0x8002、返回 1", r.ret, 1)
    case("  输出参数 [0x48be64] = 0x8002", r.param, 0x8002)
    case("★★ 最恨支**不消费 rand**（rand=2 本会摇到 3 号 ⇒ 若走兜底支会返回 0）",
         r.rand_calls, 0)
    case("  可见表填充器收到实参 −1", r.vis_arg, 0xFFFFFFFF)

    w.clear(); w.hate(2, 10); w.see(0x8002, 0x8004)
    r = w.run()
    case("★ 最恨 2 号 ⇒ 取他的标记 0x8004（不是表里第一项）", r.param, 0x8004)
    case("  返回 1", r.ret, 1)

    w.clear(); w.hate(3, 10); w.see(0x8001, 0x8002, 0x8004, 0x8008)
    r = w.run()
    case("★ 最恨 3 号 ⇒ 0x8008（跳过前三个不对位的项）", r.param, 0x8008)

    # ★ 严格 > ：并列取**下标小**者（`0x40d30b cmp ecx,ebx / jge 跳过`）
    w.clear(); w.hate(1, 5); w.hate(2, 5); w.see(0x8002, 0x8004)
    r = w.run()
    case("★★ 敌意并列 (1,2) ⇒ 严格 > ⇒ 取**下标小**的 1 号（参数 0x8002）", r.param, 0x8002)
    case("  不摇 rand", r.rand_calls, 0)

    w.clear(); w.hate(1, 5); w.hate(3, 9); w.see(0x8002, 0x8008)
    r = w.run()
    case("  9 > 5 ⇒ 取 3 号（参数 0x8008）", r.param, 0x8008)

    # ★ 最恨的人**没有** +0x32（关押）闸，但**有** whoPlays != 0 闸
    w.clear(); w.hate(1, 100); w.hate(2, 5); w.who[1] = 0; w.see(0x8004)
    r = w.run()
    case("★ 1 号不在场（+0x15 == 0）⇒ 不参与最恨，退到 2 号（参数 0x8004）", r.param, 0x8004)
    case("  仍走最恨支（不摇 rand）", r.rand_calls, 0)

    w.clear(); w.hate(0, 100); w.see(0x8001, 0x8002)
    r = w.run()
    case("★ 敌意给自己 ⇒ `0x40d2d3` 跳过自己 ⇒ 恒 −1 ⇒ 走随机兜底（摇 1 次）",
         r.rand_calls, 1)
    case("  兜底 rand=0 ⇒ 第 1 个候选（1 号）⇒ 参数 0x8002", r.param, 0x8002)

    # ★★ 不对称：`0x40d2d3` **没有** +0x32（关押）闸，`0x40d31c` 有
    w.clear(); w.hate(1, 10); w.byte(1, 0x32, 1); w.see(0x8002)
    r = w.run()
    case("★★ 最恨的人**在牢里也照样被选**（`0x40d2d3` 无 +0x32 闸，与兜底支不对称）",
         r.param, 0x8002)
    case("  仍走最恨支（不摇 rand）", r.rand_calls, 0)
    w.clear(); w.hate(1, 10); w.byte(1, P_SLEEP, 1); w.see(0x8002)
    r = w.run()
    case("  冬眠中（+0x36）的最恨的人同样照选", r.param, 0x8002)

    # ★ 最恨的遍历上界 = [0x499114]：越界者的敌意再大也看不见
    w.clear(); w.num = 2; w.hate(1, 0); w.hate(2, 100); w.see(0x8002, 0x8004)
    r = w.run()
    case("★★ 人数=2 时 2 号的敌意 100 **看不见** ⇒ 最恨 −1 ⇒ 走兜底",
         r.rand_calls, 1)
    case("  兜底候选只有 1 号 ⇒ 参数 0x8002（若上界写成 4 会取 2 号 ⇒ 0）", r.param, 0x8002)

    # ── A2 · 兜底：select_one_active_player ──
    print("\n[A2] 兜底支（`0x40d31c`）：随机挑一个在场、没被关着的人")
    for rand, want_param in [(0, 0x8002), (1, 0x8004), (5, 0x8004), (12345, 0x8004)]:
        w.clear(); w.num = 3; w.see(0x8002, 0x8004); w.rand = rand
        r = w.run()
        case(f"★ 3 人局、无最恨、rand={rand} ⇒ 参数 {want_param:#x}", r.param, want_param)
        case("  恰好消费 1 次 rand", r.rand_calls, 1)

    w.clear(); w.num = 4; w.see(0x8002, 0x8004, 0x8008); w.rand = 2
    r = w.run()
    case("★ 4 人局兜底候选 [1,2,3]、rand=2 ⇒ 3 号（0x8008）", r.param, 0x8008)

    # ── A3 · 目标 −1 ⇒ 返回 0（且不碰可见表） ──
    print("\n[A3] 两次都 −1 ⇒ 直接返回 0")
    w.clear(); w.num = 1; w.see(0x8001); w.rand = 0
    r = w.run()
    case("★ 单人局（只有自己）⇒ 最恨 −1、兜底 −1 ⇒ 返回 0", r.ret, 0)
    case("  输出参数未写（哨兵）", r.param, SENTINEL)
    case("★ 可见表填充器**也没被调**（提前返回）", r.vis_arg, SENTINEL)
    case("★ 一次 rand 都没摇", r.rand_calls, 0)

    w.clear(); w.num = 3; w.who[1] = 0; w.byte(2, P_BLOCKING, 1); w.see(0x8002, 0x8004)
    w.rand = 0
    r = w.run()
    case("★ 1 号不在场 + 2 号在牢里 ⇒ 兜底候选空 ⇒ 返回 0", r.ret, 0)
    case("★★ 0 候选时 **rand 不被消费**", r.rand_calls, 0)
    case("  可见表未被调用", r.vis_arg, SENTINEL)

    # ── A4 · 目标的 0x80xx 标记必须出现在可见表里 ──
    print("\n[A4] 可见表里必须有**目标**的 0x80xx 标记（bit15 置 ∧ 低 4 位非 0 ∧ bit==目标）")
    for t in (1, 2, 3):
        for b in range(4):
            mark = 0x8000 | (1 << b)
            w.clear(); w.hate(t, 10); w.see(mark)
            r = w.run()
            if b == t:
                case(f"★ 目标={t} 标记={mark:#06x} ⇒ 命中", r.param, mark)
                case("  返回 1", r.ret, 1)
            else:
                case(f"  目标={t} 标记={mark:#06x}（位不对）⇒ 不用", r.ret, 0)
                case("  参数未写", r.param, SENTINEL)

    w.clear(); w.hate(1, 10); w.see()
    r = w.run()
    case("★ 可见表为空 ⇒ 找不到标记 ⇒ 返回 0", r.ret, 0)
    case("  可见表填充器**被调过**（参数 −1）", r.vis_arg, 0xFFFFFFFF)
    case("  参数未写", r.param, SENTINEL)

    for mark, why in [(0x0002, "bit15 未置（只是低 4 位非 0）"),
                      (0x0001, "bit15 未置"),
                      (0x8000, "低 4 位全 0")]:
        w.clear(); w.hate(1, 10); w.see(mark)
        r = w.run()
        case(f"★ 标记 {mark:#06x}（{why}）⇒ 忽略 ⇒ 返回 0", r.ret, 0)
        case("  参数未写", r.param, SENTINEL)

    w.clear(); w.hate(1, 10); w.see(0x7D1)
    r = w.run()
    case("★ 表里是地块值 0x7d1（不是玩家标记）⇒ 不算命中 ⇒ 返回 0", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x7D1, 0x8002)
    r = w.run()
    case("★ 前面有地块值、后面才是标记 ⇒ 命中 0x8002", r.param, 0x8002)

    for mark in (0x8003, 0x8006, 0x800E):
        w.clear(); w.hate(1, 10); w.see(mark)
        r = w.run()
        case(f"★ 多位置位 {mark:#06x}（含 bit1）⇒ 命中且输出**整项词**", r.param, mark)

    w.clear(); w.hate(1, 10); w.see(0x8003, 0x8002)
    r = w.run()
    case("★ 每项独立判：第一项 0x8003 就含 bit1 ⇒ 命中它（不跳过）", r.param, 0x8003)

    # ★ 目标找不到标记时，爆风扫描**不该**被调
    w.clear(); w.hate(1, 10); w.see(0x8004)
    r = w.run()
    case("★ 只有别的玩家的标记 ⇒ 返回 0", r.ret, 0)
    case("★★ 爆风扫描**一次都没被调**（中心/半径仍是哨兵）",
         (r.blast_x, r.blast_y, r.blast_r), (SENTINEL, SENTINEL, SENTINEL))

    # ── A5 · 爆风扫描：中心 = 目标的 +0x08/+0x0a，半径 = 0x64 ──
    print("\n[A5] 爆风扫描的实参：中心 = **目标**的 +0x08/+0x0a，半径 = 0x64")
    w.clear(); w.hate(1, 10); w.see(0x8002)
    w.at(0, 0x1111, 0x2222).at(1, 0x3333, 0x4444).at(2, 0x5555, 0x6666)
    r = w.run()
    case("★ 目标 1 号 ⇒ 中心 (0x3333, 0x4444)（**不是**自己的 0x1111/0x2222）",
         (r.blast_x, r.blast_y), (0x3333, 0x4444))
    case("★ 半径恰为 0x64", r.blast_r, 0x64)

    w.clear(); w.hate(2, 10); w.see(0x8004)
    w.at(0, 0x1111, 0x2222).at(2, 0xABCD, 0x1234)
    r = w.run()
    case("★ 换目标为 2 号 ⇒ 中心跟着变成 (0xABCD, 0x1234)", (r.blast_x, r.blast_y),
         (0xABCD, 0x1234))
    case("  半径仍 0x64", r.blast_r, 0x64)

    w.clear(); w.num = 4; w.see(0x8002, 0x8004, 0x8008); w.rand = 2
    w.at(0, 0x1111, 0x2222).at(3, 0x0007, 0x0009)
    r = w.run()
    case("★ 兜底选中 3 号 ⇒ 中心 = 3 号的 (7, 9)", (r.blast_x, r.blast_y), (7, 9))
    case("  半径 0x64", r.blast_r, 0x64)

    # ── A6 · 爆风扫描：任何玩家标记 ⇒ 0 ──
    print("\n[A6] 爆风表里**任何** 0x80xx 玩家标记 ⇒ 返回 0")
    for mark, why in [(0x8001, "我自己的标记"),
                      (0x8002, "目标的标记"),
                      (0x8008, "别的玩家的标记"),
                      (0x800F, "四个位全置")]:
        w.clear(); w.hate(1, 10); w.see(0x8002); w.boom(mark)
        r = w.run()
        case(f"★ 爆风含 {mark:#06x}（{why}）⇒ 返回 0（哪怕相位 1 已命中）", r.ret, 0)
        case("  输出参数**已写**（相位 1 的 0x8002 保留）", r.param, 0x8002)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.boom(0x7D1, 0x8001)
    r = w.run()
    case("★ 玩家标记在**第二项** ⇒ 仍然返回 0（逐项扫）", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.boom(0x8002)
    r = w.run()
    case("★ 爆风表与可见表是**同一张**（第二趟覆盖第一趟）⇒ 目标的标记也算玩家标记",
         r.ret, 0)
    case("  爆风扫描确实被调（中心非哨兵）", r.blast_r, 0x64)

    # ── A7 · 爆风扫描：我的地 / 我的設施 ⇒ 0 ──
    print("\n[A7] 爆风表里有**我的**（owner == 当前玩家 + 1）地块/設施 ⇒ 返回 0")
    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 1}; w.boom(0x7D1)
    r = w.run()
    case("★ 我的地块 0x7d1（1 号地、owner=1、当前玩家 0）⇒ 返回 0", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 2}; w.boom(0x7D1)
    r = w.run()
    case("★ 别人的地块（owner=2）⇒ 不拦 ⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 0}; w.boom(0x7D1)
    r = w.run()
    case("★ 无主地块（owner=0）⇒ 不拦 ⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.facs = {1: 1}; w.boom(0xFA1)
    r = w.run()
    case("★ 我的設施 0xfa1（owner=1）⇒ 返回 0", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.facs = {1: 3}; w.boom(0xFA1)
    r = w.run()
    case("★ 别人的設施（owner=3）⇒ 返回 1", r.ret, 1)

    # ★ 当前玩家不是 0 号：owner 必须 == cur + 1
    w.clear(); w.me = 2; w.hate(1, 10); w.see(0x8002); w.lands = {1: 3}; w.boom(0x7D1)
    r = w.run()
    case("★ 当前玩家 2 号 ⇒ owner==3 才算我的 ⇒ 返回 0", r.ret, 0)

    w.clear(); w.me = 2; w.hate(1, 10); w.see(0x8002); w.lands = {1: 1}; w.boom(0x7D1)
    r = w.run()
    case("  当前玩家 2 号时 owner==1（1 号的）⇒ 不拦 ⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {5: 1}; w.boom(0x7D5)
    r = w.run()
    case("★ 我的 5 号地（0x7d5）⇒ 返回 0（地块步长 0x34 逐项核对）", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.facs = {5: 1}; w.boom(0xFA5)
    r = w.run()
    case("★ 我的 5 号設施（0xfa5）⇒ 返回 0（設施步长 0x38）", r.ret, 0)

    # ★ 区间端点是**严格**比较（jle/jge）⇒ 0 号地/0 号設施永远判不出"我的"
    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {0: 1}; w.boom(0x7D0)
    r = w.run()
    case("★★ 地块 0 号（0x7d0）即使是 owner=1 也**判不出我的**（`jle`）⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.facs = {0: 1}; w.boom(0xFA0)
    r = w.run()
    case("★★ 設施 0 号（0xfa0）同理（`jle`）⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 1}; w.boom(0x1771)
    r = w.run()
    case("★ 企業格 0x1771（≥0x1770）不在两个区间里 ⇒ 不拦 ⇒ 返回 1", r.ret, 1)

    # ★ 多项：任一项命中就返回 0
    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 2, 2: 2}; w.boom(0x7D1, 0x7D2)
    r = w.run()
    case("★ 两项都是别人的地 ⇒ 返回 1", r.ret, 1)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 2, 2: 1}; w.boom(0x7D1, 0x7D2)
    r = w.run()
    case("★ 我的地在**第二项** ⇒ 仍返回 0", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.lands = {1: 2}; w.boom(0x7D1, 0x8001)
    r = w.run()
    case("★ 玩家标记在第二项 ⇒ 返回 0", r.ret, 0)

    w.clear(); w.hate(1, 10); w.see(0x8002); w.boom()
    r = w.run()
    case("★★ 爆风表为空 + 相位 1 命中 ⇒ 返回 1、参数 = 目标的标记", r.ret, 1)
    case("  输出参数 = 0x8002", r.param, 0x8002)

    # ── A8 · 组合 ──
    print("\n[A8] 组合：兜底 + 我的地")
    w.clear(); w.num = 3; w.see(0x8002, 0x8004); w.rand = 1
    w.lands = {7: 1}; w.boom(0x7D7)
    r = w.run()
    case("★ 兜底摇到 2 号、爆风里有我的 7 号地 ⇒ 返回 0", r.ret, 0)
    case("  但参数已写成 0x8004", r.param, 0x8004)

    w.clear(); w.num = 3; w.see(0x8002, 0x8004); w.rand = 1
    w.lands = {7: 2}; w.boom(0x7D7)
    r = w.run()
    case("★ 同一局但 7 号地是别人的 ⇒ 返回 1", r.ret, 1)

    # ── A9 · `0x4216ab` 的编译产物怪癖（"不是我的"出口返回调用方的 edx） ──
    print("\n[A9] 被调方真值：`0x4216ab(player, value)`（用 call 包装桩精确控制 edx）")
    # 包一层 `(player, value, edx)` 三参的壳，把 edx 显式设好再去 call 真身：
    #   mov edx,[esp+0xc] / mov eax,[esp+4] / mov ecx,[esp+8] / push ecx / push eax
    #   / call 0x4216ab / add esp,8 / ret
    _call_off = 14                       # E8 的位置
    _rel = IS_MINE - (STUB_BASE + _call_off + 5)
    w.emu.patch(STUB_BASE,
                b"\x8B\x54\x24\x0C"
                + b"\x8B\x44\x24\x04"
                + b"\x8B\x4C\x24\x08"
                + b"\x51\x50"
                + b"\xE8" + struct.pack("<i", _rel)
                + b"\x83\xC4\x08\xC3")

    def run_is_mine(player, value, owner, edx, is_fac=False):
        def setup(e):
            e.write32(LAND_PTR, LANDS)
            e.write32(FAC_PTR, FACS)
            e.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
            e.write(FACS, b"\x00" * (FAC_STRIDE * 16))
            e.write8((FACS if is_fac else LANDS)
                     + 1 * (FAC_STRIDE if is_fac else LAND_STRIDE) + L_OWNER, owner)
        return w.emu.call(STUB_BASE, [player, value, edx], setup=setup)["eax"]

    case("★ is_mine(0, 0x7d1) 我的地 ⇒ 1", run_is_mine(0, 0x7D1, 1, 0), 1)
    case("★ is_mine(2, 0x7d1) owner=3 ⇒ 1（1 基：owner == player+1）",
         run_is_mine(2, 0x7D1, 3, 0), 1)
    case("  is_mine(2, 0x7d1) owner=1 ⇒ 0（不是我的）", run_is_mine(2, 0x7D1, 1, 0), 0)
    case("★ is_mine(2, 0xfa1) owner=3 ⇒ 1（設施支）", run_is_mine(2, 0xFA1, 3, 0, True), 1)
    case("★★ 0x7d0 边界 ⇒ 不当地块 ⇒ 0", run_is_mine(0, 0x7D0, 1, 0), 0)
    case("★★ 0xfa0 边界 ⇒ 不当設施 ⇒ 0", run_is_mine(0, 0xFA0, 1, 0, True), 0)
    case("  0x1770 以上（企業）⇒ 0", run_is_mine(0, 0x1771, 1, 0), 0)
    case("  0x7cf 以下 ⇒ 0", run_is_mine(0, 0x7CF, 1, 0), 0)
    case("★★ 「不是我的」出口返回的是**调用方的 edx**（edx=0x2a ⇒ 0x2a）",
         run_is_mine(0, 0x7D1, 2, 0x2A), 0x2A)
    case("★★ 同一个调用 edx=1 ⇒ 返回 1（**与是否我的地无关**）—— 原版怪癖",
         run_is_mine(0, 0x7D1, 2, 1), 1)
    case("  edx=0x2a 且 0x7d0 越界值 ⇒ 也返回 0x2a", run_is_mine(0, 0x7D0, 1, 0x2A), 0x2A)

    # ═════════════════════════════════════════════════════════════════
    # [B] 0x0040d31c · select_one_active_player
    # ═════════════════════════════════════════════════════════════════
    print("\n[B] `0x40d31c(arg)`：遍历 p < [0x499114]，跳过 arg / whoPlays==0 / "
          "dword[+0x32]!=0，返回 players[rand() % count]")

    # ── B1 · 基本挑选与取模 ──
    print("\n[B1] 候选收集与 `rand() % count`")
    for rand, want in [(0, 1), (1, 2), (2, 3), (3, 1), (5, 3), (12345, 1)]:
        w.clear(); w.num = 4; w.rand = rand
        r = w.run_select(0)
        case(f"★ 4 人局、arg=0、rand={rand} ⇒ 返回 {want}", r.ret, want)
        case("  恰好消费 1 次 rand", r.rand_calls, 1)

    for arg, rand, want in [(1, 0, 0), (1, 1, 2), (1, 2, 3),
                            (2, 0, 0), (2, 2, 3),
                            (3, 0, 0), (3, 2, 2)]:
        w.clear(); w.num = 4; w.rand = rand
        r = w.run_select(arg)
        case(f"★ arg={arg}（跳过自己）rand={rand} ⇒ 返回 {want}", r.ret, want)

    # arg 落在人数之外 ⇒ 没有人被它跳过
    w.clear(); w.num = 2; w.rand = 0
    r = w.run_select(7)
    case("★ arg=7 超出人数 ⇒ 候选 [0,1] ⇒ rand=0 返回 0", r.ret, 0)
    w.clear(); w.num = 2; w.rand = 1
    r = w.run_select(7)
    case("  arg=7、rand=1 ⇒ 返回 1", r.ret, 1)

    # ── B2 · whoPlays == 0 跳过 ──
    print("\n[B2] 跳过 `whoPlays(+0x15) == 0`")
    w.clear(); w.num = 4; w.who[2] = 0; w.rand = 0
    r = w.run_select(0)
    case("★ 2 号不在场 ⇒ 候选 [1,3] ⇒ rand=0 返回 1", r.ret, 1)
    w.clear(); w.num = 4; w.who[2] = 0; w.rand = 1
    r = w.run_select(0)
    case("  同上、rand=1 ⇒ 返回 3（不是 2）", r.ret, 3)

    w.clear(); w.num = 4; w.who = [1, 0, 0, 0]; w.rand = 0
    r = w.run_select(0)
    case("★ 只有自己活着 ⇒ 0 候选 ⇒ 返回 −1", r.ret, 0xFFFFFFFF)
    case("★ 0 候选时 **rand 不被消费**", r.rand_calls, 0)

    w.clear(); w.num = 4; w.who = [0, 1, 0, 0]; w.rand = 0
    r = w.run_select(0)
    case("★ arg=0 但 0 号也不在场 ⇒ 候选 [1] ⇒ 返回 1", r.ret, 1)

    # ★ 判据是**整字节**比较（`cmp byte [...],0`），不是 `& 3`
    w.clear(); w.num = 4; w.who = [1, 0x10, 0, 0]; w.rand = 0
    r = w.run_select(0)
    case("★★ whoPlays=0x10（只有高标志位、低 2 位为 0）仍算**在场**（整字节比较）",
         r.ret, 1)
    case("  消费 1 次 rand", r.rand_calls, 1)
    w.clear(); w.num = 4; w.who = [1, 0x40, 0, 0]; w.rand = 0
    r = w.run_select(0)
    case("  同上 whoPlays=0x40 ⇒ 仍入选", r.ret, 1)

    # ── B3 · dword[+0x32] != 0 跳过（四个字节各自都成立） ──
    print("\n[B3] 跳过 `dword[+0x32] != 0`（= 住店/消失/坐牢/住院）")
    for off, name in [(0x32, "days_in_hotel"), (0x33, "disappearing"),
                      (0x34, "in_prison"), (0x35, "days_in_hospital")]:
        w.clear(); w.num = 4; w.byte(1, off, 1); w.rand = 0
        r = w.run_select(0)
        case(f"★ 仅 +0x{off:02x}（{name}）= 1 ⇒ 1 号被排除 ⇒ rand=0 返回 2", r.ret, 2)
        case("  消费 1 次 rand", r.rand_calls, 1)

    w.clear(); w.num = 4; w.byte(1, 0x32, 1); w.rand = 1
    r = w.run_select(0)
    case("  仅 +0x32=1、rand=1 ⇒ 候选 [2,3] ⇒ 返回 3", r.ret, 3)

    # ★★ 边界：+0x36（days_sleeping）**不在**那个 dword 里 ⇒ 不排除
    for rnd, want in [(0, 1), (1, 2)]:
        w.clear(); w.num = 4; w.byte(1, P_SLEEP, 1); w.rand = rnd
        r = w.run_select(0)
        case(f"★★ 仅 +0x36（days_sleeping）= 1、rand={rnd} ⇒ **不排除** ⇒ 候选 [1,2,3] "
             f"⇒ 返回 {want}", r.ret, want)
        case("  消费 1 次 rand", r.rand_calls, 1)
    for rnd, want in [(0, 1), (1, 2)]:
        w.clear(); w.num = 4; w.byte(1, P_SLEEPWALK, 1); w.rand = rnd
        r = w.run_select(0)
        case(f"★★ 仅 +0x37（夢遊）= 1、rand={rnd} ⇒ **不排除** ⇒ 返回 {want}", r.ret, want)

    # 多个人各自不同字节被占
    w.clear(); w.num = 4; w.byte(1, 0x32, 1); w.byte(2, 0x35, 1); w.rand = 0
    r = w.run_select(0)
    case("★ 1 号住店 + 2 号住院 ⇒ 只剩 3 号 ⇒ 返回 3", r.ret, 3)
    case("  1 个候选也**照摇一次** rand", r.rand_calls, 1)
    w.clear(); w.num = 4; w.byte(1, 0x32, 1); w.byte(2, 0x35, 1); w.rand = 999
    r = w.run_select(0)
    case("  同一个候选、rand=999 ⇒ 999%1=0 ⇒ 仍返回 3", r.ret, 3)

    # arg 自己就算被关着也照样被排除（顺序：先比 arg）
    w.clear(); w.num = 4; w.byte(0, 0x32, 1); w.rand = 0
    r = w.run_select(0)
    case("  arg 自己被关着也不影响（先比 arg 再比 +0x32）⇒ 返回 1", r.ret, 1)

    # ── B4 · 0 候选 ⇒ −1 且不摇 ──
    print("\n[B4] 0 候选 ⇒ 返回 −1 且 **不消费 rand**")
    w.clear(); w.num = 1; w.rand = 5
    r = w.run_select(0)
    case("★★ 人数=1（只有自己）⇒ 返回 −1", r.ret, 0xFFFFFFFF)
    case("  rand 一次都没摇（rand=5 也没被取）", r.rand_calls, 0)

    w.clear(); w.who = [1, 0, 0, 0]; w.rand = 5
    r = w.run_select(0)
    case("★★ 其他人都 whoPlays==0 ⇒ 返回 −1", r.ret, 0xFFFFFFFF)
    case("  rand 一次都没摇", r.rand_calls, 0)

    w.clear(); w.rand = 5
    for p in (1, 2, 3):
        w.byte(p, 0x32, 1)
    r = w.run_select(0)
    case("★★ 其他人都被关着（+0x32 dword != 0）⇒ 返回 −1", r.ret, 0xFFFFFFFF)
    case("  rand 一次都没摇", r.rand_calls, 0)

    # ── B5 · 1 候选 ⇒ 摇一次 ──
    print("\n[B5] 1 候选 ⇒ **照摇一次** rand（与第 6 条 `pickNextNode` 同类）")
    for rand in (0, 5, 12345):
        w.clear(); w.num = 2; w.rand = rand
        r = w.run_select(0)
        case(f"★ 人数=2（候选只有 1 号）rand={rand} ⇒ 返回 1", r.ret, 1)
        case("  恰好消费 1 次 rand", r.rand_calls, 1)

    w.clear(); w.num = 4; w.who = [1, 0, 1, 0]; w.rand = 777
    r = w.run_select(0)
    case("★ 只剩 2 号 ⇒ 返回 2", r.ret, 2)
    case("  消费 1 次 rand", r.rand_calls, 1)

    # ── B6 · 上界 = [0x499114] ──
    print("\n[B6] 遍历上界 = `[0x499114]`（人数）")
    w.clear(); w.num = 2; w.rand = 1
    r = w.run_select(0)
    case("★★ 人数=2 时 2/3 号虽在场也**看不见** ⇒ 候选 [1] ⇒ 返回 1（若上界=4 会返回 2）",
         r.ret, 1)
    case("  消费 1 次 rand", r.rand_calls, 1)

    w.clear(); w.num = 3; w.rand = 2
    r = w.run_select(0)
    case("★ 人数=3 ⇒ 候选 [1,2] ⇒ rand=2 ⇒ 2%2=0 ⇒ 返回 1", r.ret, 1)

    w.clear(); w.num = 0; w.rand = 0
    r = w.run_select(0)
    case("★★ 人数=0 ⇒ 0 候选 ⇒ −1（上界必须真的被读）", r.ret, 0xFFFFFFFF)
    case("  rand 未消费", r.rand_calls, 0)

    # ── B7 · 返回的是**玩家下标** ──
    print("\n[B7] 返回值就是玩家下标（0 基），且每个下标都能被选到")
    for arg in (0, 1, 2, 3):
        picked = set()
        for rand in range(12):
            w.clear(); w.num = 4; w.rand = rand
            r = w.run_select(arg)
            picked.add(r.ret)
        case(f"★ arg={arg} ⇒ 12 次取样只落在这三个人里",
             picked, {i for i in range(4) if i != arg})

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
