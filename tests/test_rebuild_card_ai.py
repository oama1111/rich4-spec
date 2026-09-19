#!/usr/bin/env python3
"""
通道 2 差分测试 · **改建卡的 AI 目标选择** `0x0041ed3e`（488 B）

复刻侧对应 `packages/core/src/ai/card-policy.ts` 的 `gaijian`（`@source 0x0041ed3e`）。
本函数**没有任何 `call` 调用者** —— 它是 AI 出牌跳表的成员，所以
`rich4-spec` 的建图工具不收它（`rich4dis.py func` 会说「不在已建图函数集中」），
要用 `rich4-remake/tools/disasm.py va 0x0041ed3e` 按需反汇编。

## 语义（逐条从字节读出，488 B 全程读完）

```
0x41ed3e():                                    ; 无参数，全走全局
    best = 0                                   ; ← 返回值
    cur  = [0x49910c]                          ; 当前玩家
    ref  = word[ node_table + word[cur*0x68+0x496b74]*0x28 + 0x20 ]
    hated = 0x40d2d3(cur)                      ; esi：最恨的人（下面 facility 支要用）

    ; ── 地块支：0x7d0 < ref < 0xfa0（★ 两端都是**开**区间）
    if (0x7d0 < ref < 0xfa0):
        idx  = ref - 0x7d0
        land = land_table + idx*0x34
        if (land.owner != cur+1)                 → return 0        ; 不是我的地
        if (land.type != 0):                     ; ── 连锁店（非住宅）
            for i in 1..num_lands:               ; ★ 从下标 1 起（0 号地永远数不到）
                if i == idx: continue
                if strcmp(land.name, land[i].name) != 0: continue
                if land[i].owner == cur+1:       → return 1        ; 同街有我的 ⇒ 改
            → return 0                                            ; 同街没我的 ⇒ 不改
        ; ── 住宅（type == 0）
        if (land.level != 1)                     → return 0        ; 住宅必须 1 级
        if (cur.personality == 0)                → return 1        ; 乖寶寶直接改
        for i in 1..num_lands:
            if i == idx: continue
            if strcmp(land.name, land[i].name) != 0: continue
            o = land[i].owner
            if (o == cur+1 || o == 0)            → return 0        ; 同街有我的 或 无主的 ⇒ 不改
        → return 1                                                ; 同街全是别人的 ⇒ 改

    ; ── 設施支：0xfa0 < ref < 0x1770
    if (0xfa0 < ref < 0x1770):
        fac = fac_table + (ref - 0xfa0)*0x38
        if (fac.owner == cur+1 && fac.type == 0 && fac.level == 1):
            [0x48be58] = rand() % 4 + 1          ; ★ 我的公園 1 級 ⇒ 随机改成 1..4 类
            → return 1
        if (fac.owner == 0)                      → return 0
        if (fac.owner == cur+1)                  → return 0        ; 我的但不符合上面
        if (fac.type == 0)                       → return 0        ; 公園不动
        lv = fac.level
        if (lv >= 3)                             → [0x48be58] = 0; return 1
        if (fac.owner != hated+1)                → return 0
        if (lv < 2)                              → return 0
        [0x48be58] = 0                           ; ★ 对手的 ≥3 級，或最恨的人 ≥2 級 ⇒ 夷平（改成公園）
        → return 1
    → return 0
```

★ **`0x48be58` 是「本张卡的参数字」全局**（`0x48be58/0x48be60/0x48be64` 一族，
见 `docs/systems/map-format.md` 关于道具参数全局的那一节）。改建卡是**唯一**写它的卡。

## 与复刻的对照结论（本测试的意义）

逐条比过 `card-policy.ts` 的 `gaijian`，**六个分支与两个边界全部一致**，包括：
`LAND_TYPE_HOUSE == 0`（住宅分支）、`type != 0` 是连锁店且**不看等级**、
住宅要求 `level == 1`、`personality == 0`（`player+0x17`）走「乖寶寶直接改」、
同街扫描**从下标 1 起**、設施支的 `owner == hated+1 && level >= 2` 这个合取。
⇒ 本测试把这些**钉进闸门**，并对复刻唯一的偏离（`rand()%4+1` → `aiRoll` 替身）划清边界。

## ⚠️ 与复刻的已知偏离（不在断言范围内）

原版「我的公園 1 級」那一支摇的是**全局 CRT `rand() % 4 + 1`**；复刻走
`aiRoll(state, 7, 4) + 1`（确定性替身、**不推进 `rngState`**）—— 已登记 **D-004**
（`docs/known-deviations.md`；逐点表见 `docs/gaps/02-cards.md` 第 16 条）。
本测试只钉「取模规则 + 消费时机（**只在那一支摇**）」，不声称选出的类别相同。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x00456f2d` | CRT `rand()` | 从**数据槽**读返回值（同 `test_walk_step.py`） |

`0x40d2d3`（**最恨的人**，本函数 `esi` 的来源）与 `0x458370`（**strcmp**，逐字实现）
一律**真跑** —— 本测试要的正是它们和主干的组合行为。

跑法：cd rich4-spec && .venv/bin/python tests/test_rebuild_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

REBUILD_AI = 0x41ED3E
MOST_HATED = 0x40D2D3
PRNG = 0x456F2D

CUR = 0x49910C
NUM_PLAYERS = 0x499114
NODE_TABLE_PTR = 0x498E80
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NUM_LANDS = 0x498E98
CARD_PARAM = 0x48BE58           # ★ 本卡写出的「参数字」

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_ALIVE, P_PERSONALITY = 0x0C, 0x15, 0x17
P_HOSTILITY, HOST_STRIDE = 0x4C, 4      # dword[me + 0x4c + j*4]

NODE_STRIDE, NODE_REF = 0x28, 0x20
LAND_STRIDE = 0x34
LAND_NAME, LAND_TYPE, LAND_OWNER, LAND_LEVEL = 0x04, 0x18, 0x19, 0x1A
FAC_STRIDE = 0x38
FAC_TYPE, FAC_OWNER, FAC_LEVEL = 0x18, 0x19, 0x1A

RAND_SLOT = SCRATCH_BASE + 0x800
NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000

LAND_MARK = 0x7D0               # 格值基址：地块 = 2000 + i
FAC_MARK = 0xFA0                # 設施 = 4000 + i
FAC_MARK_HI = 0x1770            # 企业 = 6000 + i（本函数不收）

SENTINEL = 0x5A5A5A5A           # 「本函数没碰 0x48be58」的哨兵
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    """状态留在 Python 侧；`Emu.call` 会 reset，故每拍重新注入。"""

    def __init__(self):
        self.emu = Emu()
        # PRNG 桩：mov eax, [slot] / ret —— 返回值放**数据**里
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.num_players = 4
        self.node = 1                  # 我脚下的节点
        self.ref = LAND_MARK + 1       # 该格格值
        self.personality = 1
        self.hostility = [0, 0, 0, 0]  # 我的敌意表
        self.lands = {}                # i → dict(name,type,owner,level)
        self.facs = {}                 # i → dict(type,owner,level)
        self.num_lands = 8
        self.rand = 0
        self.lands_built = False

    # ── 便捷构造：脚下这块地 + 同街若干块 ───────────────────────────
    def my_land(self, kind="house", level=1, name="AAA"):
        self.ref = LAND_MARK + 1
        self.lands[1] = {"name": name, "type": 0 if kind == "house" else 1,
                         "owner": self.me + 1, "level": level}
        self.lands_built = True
        return self

    def same_street(self, *specs, name="AAA"):
        """同街若干块：specs 里每项是 (owner, type, level)"""
        for k, (owner, typ, level) in enumerate(specs):
            self.lands[2 + k] = {"name": name, "type": typ, "owner": owner, "level": level}
        return self

    def facility(self, owner, typ, level):
        self.ref = FAC_MARK + 1
        self.facs[1] = {"owner": owner, "type": typ, "level": level}
        return self

    # ── 注入 / 回读 ─────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, self.num_players)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(NUM_LANDS, self.num_lands)
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        emu.write32(CARD_PARAM, SENTINEL)
        # ★ 暂存区跨调用保留 ⇒ 每次都先清干净（见 verification.md 工具边界第 3 条）
        emu.write(NODES, b"\x00" * (0x28 * 4))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * (self.num_lands + 2)))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * (self.num_lands + 2)))
        # 玩家
        for i in range(4):
            pb = PLAYER_BASE + i * PLAYER_STRIDE
            emu.write8(pb + P_ALIVE, 1)
            emu.write8(pb + P_PERSONALITY, 0)
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        emu.write16(pb + P_NODE, self.node)
        emu.write8(pb + P_PERSONALITY, self.personality)
        for j, h in enumerate(self.hostility):
            emu.write32(pb + P_HOSTILITY + j * HOST_STRIDE, h & 0xFFFFFFFF)
        # 我脚下那格
        emu.write16(NODES + self.node * NODE_STRIDE + NODE_REF, self.ref & 0xFFFF)
        # 地块表
        for i, L in self.lands.items():
            b = LANDS + i * LAND_STRIDE
            emu.write(b + LAND_NAME, L["name"].encode() + b"\x00")
            emu.write8(b + LAND_TYPE, L["type"])
            emu.write8(b + LAND_OWNER, L["owner"])
            emu.write8(b + LAND_LEVEL, L["level"])
        # 設施表
        for i, F in self.facs.items():
            b = FACS + i * FAC_STRIDE
            emu.write8(b + FAC_TYPE, F["type"])
            emu.write8(b + FAC_OWNER, F["owner"])
            emu.write8(b + FAC_LEVEL, F["level"])

    def run(self):
        r = self.emu.call(REBUILD_AI, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.read32(CARD_PARAM)
        return self


def main():
    print("差分测试 · 改建卡 AI 目标选择 0x41ed3e（488 B）\n")
    w = World()

    # ── A. 格值域：两端开区间 ──────────────────────────────────────
    print("[A] 格值域：地块 0x7d0 < ref < 0xfa0、設施 0xfa0 < ref < 0x1770（★ 两端都开）")
    for ref, desc in [(0x0, "ref=0"), (0x7D0, "ref=0x7d0（地块 0 号）"),
                      (0xFA0, "ref=0xfa0（設施 0 号）"), (0x1770, "ref=0x1770（企业 0 号）"),
                      (0x2000, "ref=0x2000 远超")]:
        w.clear()
        w.ref = ref
        r = w.run()
        case(f"{desc} ⇒ 都不是可改建目标", r.ret, 0)
        case("  也没碰 0x48be58", r.param, SENTINEL)

    w.clear()
    w.my_land("house", 1)
    r = w.run()
    case("ref=0x7d1（地块 1 号）+ 我的住宅 1 級 ⇒ 1（下端确实是开的）", r.ret, 1)

    w.clear()
    w.facility(1, 0, 1)
    r = w.run()
    case("ref=0xfa1（設施 1 号）+ 我的公園 1 級 ⇒ 1（0xfa0 确实是开的）", r.ret, 1)

    # ── B. 地块：不是我的 ─────────────────────────────────────────
    print("\n[B] 地块支：不是我的地 ⇒ 0")
    w.clear()
    w.ref = LAND_MARK + 1
    w.lands[1] = {"name": "AAA", "type": 0, "owner": 2, "level": 1}
    r = w.run()
    case("owner=2（对手）⇒ 0", r.ret, 0)
    w.clear()
    w.ref = LAND_MARK + 1
    w.lands[1] = {"name": "AAA", "type": 0, "owner": 0, "level": 1}
    r = w.run()
    case("owner=0（无主）⇒ 0", r.ret, 0)

    # ── C. 住宅（type == 0）────────────────────────────────────────
    print("\n[C] 住宅（type==0）：须 1 級；personality==0 ⇒ 直接改；否则同街全是别人的才改")
    w.clear()
    w.my_land("house", 1)
    w.personality = 0
    r = w.run()
    case("★ 1 級 + personality=0（乖寶寶）⇒ 1", r.ret, 1)
    case("  且**不写** 0x48be58（那是設施支才写的）", r.param, SENTINEL)

    for lv, want in [(0, 0), (2, 0), (5, 0)]:
        w.clear()
        w.my_land("house", lv)
        w.personality = 0
        r = w.run()
        case(f"1 級硬要求：level={lv} ⇒ {want}", r.ret, want)

    w.clear()
    w.my_land("house", 1).same_street((1, 0, 3))     # 同街另一块是我的
    r = w.run()
    case("★ 同街另有我的地 ⇒ 0", r.ret, 0)

    w.clear()
    w.my_land("house", 1).same_street((0, 0, 0))     # 同街另一块无主
    r = w.run()
    case("★ 同街有无主的地 ⇒ 0", r.ret, 0)

    w.clear()
    w.my_land("house", 1).same_street((2, 0, 3), (3, 1, 2))
    r = w.run()
    case("★ 同街其余全是别人的 ⇒ 1", r.ret, 1)

    w.clear()
    w.my_land("house", 1)                            # 同街没有别的
    r = w.run()
    case("同街一块都没有 ⇒ 1（every 的空真）", r.ret, 1)

    w.clear()
    w.my_land("house", 1).same_street((2, 0, 3), name="BBB")
    r = w.run()
    case("★ 同街但有我的地**不叫同名** ⇒ 不算同街 ⇒ 1", r.ret, 1)

    w.clear()
    w.my_land("house", 1).same_street((1, 0, 3), name="BBB")
    r = w.run()
    case("  同名才算同街（名字不同 ⇒ 1）", r.ret, 1)

    # ── D. 连锁店（type != 0）—— 不看等级 ──────────────────────────
    print("\n[D] 连锁店（type!=0）：同街有我的就改，**完全不看等级**")
    w.clear()
    w.my_land("chain", 0).same_street((1, 1, 9))
    w.personality = 0
    r = w.run()
    case("★ type=1、level=0、同街有我的 ⇒ 1（等级不参与）", r.ret, 1)

    w.clear()
    w.my_land("chain", 0)
    w.personality = 0
    r = w.run()
    case("★ 连锁店：同街没我的 ⇒ 0", r.ret, 0)

    w.clear()
    w.my_land("chain", 0).same_street((2, 1, 3))
    r = w.run()
    case("  连锁店：同街全是别人的 ⇒ 0", r.ret, 0)

    w.clear()
    w.my_land("chain", 3).same_street((1, 1, 9))
    w.personality = 0
    r = w.run()
    case("连锁店 + personality=0 也照样看同街（⇒ 1）", r.ret, 1)

    # ── E. 設施：我的公園 1 級 ⇒ rand()%4+1 ────────────────────────
    print("\n[E] 設施支：我的 + type==0（公園）+ level==1 ⇒ [0x48be58] = rand()%4+1")
    for rand, want in [(0, 1), (1, 2), (3, 4), (4, 1), (5, 2), (7, 4), (12345, 2)]:
        w.clear()
        w.facility(1, 0, 1)
        w.rand = rand
        r = w.run()
        case(f"rand={rand} ⇒ {rand}%4={rand % 4} ⇒ 参数 {want}", r.param, want)
        case("  返回值 1", r.ret, 1)

    w.clear()
    w.facility(1, 0, 2)
    r = w.run()
    case("★ 我的公園但 level=2 ⇒ 0，且**不摇随机数**（参数保持哨兵）", r.param, SENTINEL)

    w.clear()
    w.facility(1, 1, 1)
    r = w.run()
    case("★ 我的設施但 type!=0（不是公園）⇒ 0", r.ret, 0)

    w.clear()
    w.facility(1, 0, 0)
    r = w.run()
    case("我的公園 level=0 ⇒ 0（要求恰好 1）", r.ret, 0)

    # ── F. 設施：对手的 ⇒ 夷平（写成公園 = 0）──────────────────────
    print("\n[F] 設施支：对手的 ⇒ level>=3，或「最恨的人 && level>=2」⇒ [0x48be58] = 0（夷平）")
    for lv, want in [(0, 0), (1, 0), (2, 0)]:
        w.clear()
        w.facility(2, 1, lv)
        r = w.run()
        case(f"对手 level={lv}、不是我恨的人 ⇒ {want}", r.ret, want)
        case("  没碰参数", r.param, SENTINEL)

    for lv in (3, 4, 5):
        w.clear()
        w.facility(2, 1, lv)
        r = w.run()
        case(f"★ 对手 level={lv} ⇒ 1，参数写成 0（公園）", r.param, 0)
        case("  返回值 1", r.ret, 1)

    w.clear()
    w.facility(2, 1, 1)
    r = w.run()
    case("对手 level=1 ⇒ 0（不改）", r.ret, 0)

    w.clear()
    w.facility(0, 1, 5)
    r = w.run()
    case("★ 无主的設施（owner=0）⇒ 0，即使等级很高也不碰", r.param, SENTINEL)

    w.clear()
    w.facility(2, 0, 5)
    r = w.run()
    case("★ 对手的**公園**（type==0）⇒ 0，不夷平公園", r.param, SENTINEL)

    # ── G. ★ 最恨的人那一支（0x40d2d3 真跑）───────────────────────
    print("\n[G] ★ 最恨的人：`owner == mostHated+1 && level >= 2` ⇒ 夷平（0x40d2d3 真跑）")
    w.clear()
    w.facility(3, 1, 2)                       # 3 号玩家（1 基 owner = 3）
    w.hostility = [0, 0, 300, 0]              # 最恨 2 号玩家 ⇒ 其 1 基编号 = 3
    r = w.run()
    case("★ level=2 且 owner 正是最恨的人 ⇒ 1", r.ret, 1)
    case("  参数写成 0（夷平）", r.param, 0)

    w.clear()
    w.facility(3, 1, 2)
    w.hostility = [0, 0, 0, 0]                # 谁都不恨 ⇒ hated = -1
    r = w.run()
    case("★★ 同一个 owner=3/level=2，但敌意表全 0 ⇒ **0**", r.ret, 0)
    case("  没碰参数", r.param, SENTINEL)

    w.clear()
    w.facility(3, 1, 2)
    w.hostility = [0, 0, 0, 500]              # 最恨 3 号玩家（1 基 = 4）
    r = w.run()
    case("★★ 最恨的是**别人**（4 号）⇒ owner=3 不命中 ⇒ 0", r.ret, 0)

    # ★ 注意：`hated` 是 **0 基玩家下标**，而 owner 是 **1 基** ⇒ 命中条件是 `owner == hated+1`。
    #   敌意表 [_,_,100,100] ⇒ 严格 > 故取**下标小**的 2 号 ⇒ hated=2 ⇒ owner 必须是 **3**。
    w.clear()
    w.facility(3, 1, 2)
    w.hostility = [0, 0, 100, 100]
    r = w.run()
    case("★★ 并列时取**下标小**的那个（严格 >）⇒ hated=2 ⇒ owner=3 命中 ⇒ 1", r.ret, 1)

    w.clear()
    w.facility(4, 1, 2)
    w.hostility = [0, 0, 100, 100]
    r = w.run()
    case("★★ 同一张敌意表：owner=4（= hated+2）**不**命中 ⇒ 0", r.ret, 0)

    w.clear()
    w.facility(2, 1, 2)
    w.hostility = [0, 0, 0, 100]              # 最恨 3 号，owner=2 ⇒ 不命中
    r = w.run()
    case("  最恨 3 号而 owner=2 ⇒ 0", r.ret, 0)

    w.clear()
    w.facility(4, 1, 5)
    w.hostility = [0, 0, 0, 100]
    r = w.run()
    case("★ level=5 走「>=3」那一支，**与恨谁无关** ⇒ 1", r.ret, 1)

    # ── H. 我的設施 + 最恨的人：不应互相干扰 ───────────────────────
    print("\n[H] 两条設施支互不干扰")
    w.clear()
    w.facility(1, 0, 1)                       # 我的公園 1 級
    w.hostility = [0, 0, 100, 0]
    w.rand = 2
    r = w.run()
    case("★ 我的公園 1 級 ⇒ 走「改成 1..4」那支（参数=3），不是夷平", r.param, 3)

    # ── I. 返回值恒为 0 / 1 ────────────────────────────────────────
    print("\n[I] 返回值恒为 0 或 1（把「会返回 1」的几支也走一遍）")
    seen = set()
    for ref in (0x0, 0x7D1, 0xFA1, 0x1770):          # 全是「不可改建」的格值
        w.clear()
        w.ref = ref
        seen.add(w.run().ret)
    case("  四种不可改建的格值 ⇒ 恰好只有 0", sorted(seen), [0])

    for kind in ("house", "facility"):
        w.clear()
        w.personality = 0
        if kind == "house":
            w.my_land("house", 1)
        else:
            w.facility(1, 0, 1)
        seen.add(w.run().ret)
    case("★ 再走两条「会改」的分支 ⇒ 集合恰为 {0,1}", sorted(seen), [0, 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
