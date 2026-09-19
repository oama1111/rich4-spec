#!/usr/bin/env python3
"""
通道 2 差分测试 · **停留卡（卡 6）的 AI 目标选择** `0x0041facc`（898 B）

复刻侧对应 `packages/core/src/ai/card-policy.ts` 的 `tingliu`（`@source 0x0041facc`），
调用链：AI 出牌循环 `0x441d53..` → `0x41e69e`（個性闸门）→ `0x41e6e6`
`call [0x475324 + action*4]` 的第 14 项 → 本函数；返回 1 后由卡效果
跳表 `0x475d5c[6] = 0x442f4d` 读 `[0x48be58]` 当目标。

与 `0x41f400`（怪獸卡）/ `0x41f901`（搶奪卡）同族：**没有 `call` 调用者**
（AI 出牌跳表成员），建图工具不收 ⇒ 用
`rich4-remake/tools/disasm.py va 0x0041facc` 按需反汇编。
本函数 **0x41facc..0x41fe4d**（唯一 `ret` 在 `0x41fe4d`），全长 **898 字节**。

## 语义（全程读完；只有 3 个 `call`：`0x458370` strcmp / `0x456f60` memset / `0x40a45c` 可見表）

```
0x41facc():                                     ; 无参数（跳表成员）
    esi = 0                                     ; 「已命中」标志，也是返回值
    me  = [0x49910c]
    ref = word [ node[ word[me+0x0c] ] + 0x20 ] ; 我脚下那格的**引用值**
                                                ;   node 表基址 = [0x498e80]，步长 0x28
    if (byte [me+0x39] != 0) goto PHASE2         ; ★ 龜行中 ⇒ 「对自己」整段跳过
                                                ;   （+0x39 = daysTortoiseWalking）

    ; ── A. 对自己·地块：0x7d0 < ref < 0xfa0（**开区间**）
    if (0x7d0 < ref < 0xfa0) {
        L = land[ (ref-0x7d0) ]                 ; land 基址 = [0x498e84]，步长 0x34
        if (L.owner(+0x19) != me+1)              goto PHASE2   ; owner 1 基
        if (L.type (+0x18) != 0)                 goto PHASE2   ; 只认住宅
        if (L.level(+0x1a) >= 5)                 goto PHASE2
        if (word[L+0x1e] * [0x4990e8] >= me.cash(+0x1c)) goto PHASE2  ; ★ 严格 <
        if (me.cash + me.deposit(+0x20) <= 10000)        goto PHASE2  ; ★ 严格 > 10000
        if (word[me+0x46] < 0)                            goto PHASE2  ; 財運 ≥ 0
        for (i = 1; i <= [0x498e98]; i++) {     ; ★★ 1 基、**含**上界、**永远看不到记录 0**
            if (i == ref-0x7d0)                     continue     ; 跳过自己
            if (strcmp(L+4, land[i]+4) != 0)        continue     ; 同街 = 同名（+4 是字符数组）
            if (land[i].owner != me+1)              continue
            → HIT: [0x48be58] = 0x8000 | (1<<me); esi = 1; return 1
        }
        if (L.level >= 2) { esi = 1; return 1 }  ; ★★★ 返回 1 但**不写 [0x48be58]**
    }

  PHASE2:
    ; ── B. 对自己·設施：0xfa0 < ref < 0x1770（**开区间**）
    if (0xfa0 < ref < 0x1770) {
        F = fac[ (ref-0xfa0) ]                  ; fac 基址 = [0x498e88]，步长 0x38
        if (F.owner(+0x19) != me+1)                     goto C
        if (word[F+0x24] * [0x4990e8] >= me.cash)       goto C   ; 严格 <
        if (me.cash <= 10000)                           goto C   ; ★ **不加上存款**
        if (F.type(+0x18) == 0 || F.type == 3)          goto C   ; 公園 / 加油站
        if (F.level(+0x1a) >= 5)                        goto C
        if (word[me+0x46] >= 0) → HIT（同上，写 0x48be58）; else goto C
    }

  C: if (esi) return esi
    ; ── C. 扫「可見表」0x48b8c4，只把**可見玩家**的脚下引用记到栈上
    memset(nodeRef[0..3], 0, 8)
    [0x48be60] = 0x40a45c(-1)                   ; 可见项数
    for (i = 0; i < [0x48be60]; i++) {
        v = word [0x48b8c4 + i*2]
        if (!(v & 0x8000)) continue             ; ★ bit15
        if (!(v & 0x000f)) continue             ; ★ 低 4 位非 0 ⇒ 这是「玩家标记」0x80xx
        for (p = 0, bit = 1; bit < 0x10; bit <<= 1, p++) {   ; ★ 只走位 0..3
            if (!(v & bit))                continue
            if (p == me)                   continue
            if (!player[p].alive(+0x15))   continue
            nodeRef[p] = word [ node[ word[player[p]+0x0c] ] + 0x20 ]
        }
    }
    ; ── D. 选「别人」：下标 0..[0x499114]-1，先到先得
    for (p = 0; p < [0x499114]; p++) {
        if (esi) return esi
        if (p == me)              continue
        if (!player[p].alive)     continue
        r = nodeRef[p]                          ; 没在可見表里 ⇒ 0
        if (0xfa0 < r < 0x1770) {               ; 設施：我的 ∧ type≠0 ∧ level≥2
            F = fac[(r-0xfa0)]
            if (F.owner == me+1 && F.type != 0 && F.level >= 2) → HIT(p)
        } else if (0x1770 < r < 0x1f40) {       ; 企業：+0x18 = 董事長
            M = comm[(r-0x1770)]                ; comm 基址 = [0x498e7c]，步长 0x34
            if (M.owner(+0x18) == me+1) → HIT(p)
        }
        ; ★ 地块（r ≤ 0x1770）在「对别人」里**完全不看**
    }
    return esi
  HIT(p): [0x48be58] = 0x8000 | (1<<p); esi = 1; 下一轮（= 返回）
```

★ **一句话语义**：**先看自己脚下** —— 站在自己「未满级、房价×物價 < 現金」的住宅上，
且（同街另有我的地 **或** 该地 ≥ 2 级）就打自己；設施同理（不看同街、只看現金 > 10000）。
自己这格不成立时，再看**画面里**的别人：谁站在我 ≥ 2 级的非公園設施、或我当董事長的企業上，就打谁。

★★ **本测试钉住的几个反常识点**：

1. **`level ≥ 2` 那半支返回 1 却一个字节都不写 `[0x48be58]`**（`0x41fc1d jmp 0x41fbf8`，
   `eb d9` 已核字节；`0x41fbf3` 的存值被跳过）。⇒ 原版在这里把「目标」留给**上一次**判定
   的残留值（调用方 `0x441db2` 不初始化它，卡效果 `0x442f4d` 直接 `0x41e6f2(0)` 读它）。
   复刻 `card-policy.ts:581` 返回 `SELF`（会被折成 `{kind:'player', index:me}`）⇒ **两边不同**。
2. 三个格值区间全是**开区间**：`0x7d0 < ref < 0xfa0`（地）/ `0xfa0 < ref < 0x1770`（設施）/
   `0x1770 < r < 0x1f40`（企業）⇒ 地 0 号、設施 0 号、企業 0 号**永不可达**。
3. 「对别人」有 **type == 3（加油站）也收**（只要 level ≥ 2），而「对自己」**排除** type 3。
   ⇒ 同一栋加油站：我站着 → 不打；别人站着 → 打。
4. 同街扫描 `i = 1 .. [0x498e98]`：**含上界**、**看不到记录 0**（复刻 lands 是 1 基，故这一格一致）。
5. 「对自己·地块」的现金含存款（`cash+bank > 10000`），「对自己·設施」**只算现金**。

## 与复刻 `ai/card-policy.ts` 的两处差异（本测试证据，未改 TS）

| # | 规则 | 原版（本测试钉住） | 复刻 | 判定 |
|---|---|---|---|---|
| 1 | 该地 ≥ 2 级但同街没有我的地 | `ret 1` 且 **`[0x48be58]` 不写**（`0x41fc1d` → `0x41fbf8`） | `card-policy.ts:581` `return SELF` ⇒ 参数 = `0x8000` 或上 `1<<me` | **DISCREPANCY** |
| 2 | 「对别人」的候选集 | 只收**在可見表里**的玩家（`nodeRefs[p]` 只对可见玩家写） | `card-policy.ts:591` 直接遍历 `state.players`（`nodeOf(p.nodeId)`），**无视野闸** | **DISCREPANCY** |

★ 第 2 条的修法不是换成 `visibleRivals()`（它按屏幕行序排、会改选中次序），
而应是「**在场的成员判据** + 仍按玩家下标 0..N−1 取第一个」（本测试 [I] 组钉住了次序 = 下标）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 填「可見表」`0x48b8c4`，返回项数 | `mov eax,[COUNT_SLOT]; ret`（表由 `setup()` 直接铺） | 它自己的语义已单独定案，复刻换了视野口径 = **D-005**，**不是本测试的对象**；本函数只把它当「哪些玩家在画面里」 |
| `0x00456f2d` | CRT `rand()` | `inc [RAND_COUNT]; mov eax,[RAND_SLOT]; ret` | 本函数**一次也不摇**（全函数 0 处 `call 0x456f2d`）——留着是为了把「没摇」变成**可断言** |

**真跑、不打桩**：

| VA | 原用途 | 为什么能真跑 |
|---|---|---|
| `0x00456f60` | CRT `memset`（清栈上 4 个 word 的 nodeRef） | 不走 ES 段技巧（`verification.md` 工具限制 1 只点名 `memcpy 0x456de8`）⇒ 仿真器可执行 |
| `0x00458370` | `strcmp`（同街判据，比较 `land+4` 的字符数组） | 纯函数、输入输出全在栈上 |
| `0x498e80/84/88/7c` | 四张表的**指针**（node/地產/設施/企業） | 由 `setup()` 指向自建表；表**内容**非本测试对象 |

★ **本函数不调用 `0x40d2d3`（最恨的人）也不调用 `0x441262`（手牌张数）** ——
全函数只有 3 个 `call`（上面那三处打桩/真跑项），与第 154/153 条那两支同族函数不同，
故 `[0x499114]` 在这里的作用是「对别人」循环的上界（不是 `0x40d2d3` 的上界）。

跑法：cd rich4-spec && .venv/bin/python tests/test_stop_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

STOP_AI = 0x41FACC
VISIBLE_FILL = 0x40A45C
PRNG = 0x456F2D

CUR = 0x49910C
NUM_PLAYERS = 0x499114          # ★ 「对别人」循环的上界
PRICE_INDEX = 0x4990E8

NODE_PTR = 0x498E80             # 地图格数组指针（步长 0x28）
LAND_PTR = 0x498E84             # 地產表指针（步长 0x34）
FAC_PTR = 0x498E88              # 設施表指针（步长 0x38）
COMM_PTR = 0x498E7C             # 企業表指针（步长 0x34）
NUM_LANDS = 0x498E98            # 地產记录数（`i = 1..N` 的**上界**）

VIS_LIST = 0x48B8C4             # 可見表（word 数组）
VIS_COUNT = 0x48BE60            # 可见项数（本函数写、被调函数返回）
PARAM0 = 0x48BE58               # 目标（0x8000 | 玩家位）
PARAM1 = 0x48BE5C               # 第二参数 —— 本函数**不该碰**
PARAM_X = 0x48BE64              # 未用槽 —— 本函数**不该碰**

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_ALIVE = 0x0C, 0x15
P_CASH, P_BANK = 0x1C, 0x20
P_TORTOISE, P_FORTUNE = 0x39, 0x46

NODE_STRIDE, N_REF = 0x28, 0x20
LAND_STRIDE, L_NAME, L_TYPE, L_OWNER, L_LEVEL, L_HOUSE = 0x34, 0x04, 0x18, 0x19, 0x1A, 0x1E
FAC_STRIDE, F_NAME, F_TYPE, F_OWNER, F_LEVEL, F_RATE = 0x38, 0x04, 0x18, 0x19, 0x1A, 0x24
COMM_STRIDE, C_OWNER = 0x34, 0x18

# ★ 自建表区：刻意**不复用** SCRATCH_BASE 的默认小暂存区 ——
#   本期要测的是**开区间的上界**（地 0x7cf / 設施 0x7cf / 企業 0x7cf 号记录），
#   需要 ~0x1B000 字节的表，自己 mem_map 一块更大的。
BIG = 0x700000
BIG_SIZE = 0x600000
LANDS = BIG + 0x000000
FACS = BIG + 0x200000
COMMS = BIG + 0x400000
NODES = BIG + 0x500000
LANDS_ZERO = LAND_STRIDE * 0x7D0          # 覆盖 0..0x7cf 号记录
FACS_ZERO = FAC_STRIDE * 0x7D0
COMMS_ZERO = COMM_STRIDE * 0x7D0
NODES_ZERO = NODE_STRIDE * 64

COUNT_SLOT = SCRATCH_BASE + 0x900
RAND_SLOT = SCRATCH_BASE + 0x800
RAND_COUNT = SCRATCH_BASE + 0xA00

LAND_LO, LAND_HI = 0x7D0, 0xFA0           # 地產格值区间（开）
FAC_LO, FAC_HI = 0xFA0, 0x1770            # 設施格值区间（开）
COMM_LO, COMM_HI = 0x1770, 0x1F40         # 企業格值区间（开）

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.mu.mem_map(BIG, BIG_SIZE)
        # 可見表填充器 → 只把「项数」交回去；表由 setup() 直接铺在 0x48b8c4
        self.emu.patch(VISIBLE_FILL,
                       b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        # rand 桩：计次 + 给一个值（本函数**不该**摇）
        self.emu.patch(PRNG,
                       b"\xFF\x05" + struct.pack("<I", RAND_COUNT)
                       + b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    # ── 构造 ────────────────────────────────────────────────────────
    def clear(self):
        self.me = 0
        self.num_players = 4
        self.price = 1
        self.rand = 0
        self.num_lands = None              # None ⇒ 自动 = max(lands)
        self.players = [dict(node=0, alive=1, cash=0, bank=0, tortoise=0, fortune=0)
                        for _ in range(4)]
        self.nodes = {}                    # node_id → 格引用值 (node+0x20)
        self.lands = {}                    # 记录号(1 基) → dict
        self.facs = {}
        self.comms = {}
        self.visible = []                  # word 列表（直接铺 0x48b8c4）

    def pset(self, p, **kw):
        self.players[p].update(kw)
        return self

    def stand(self, p, node_id, ref):
        """玩家 p 站在 node_id 上，该格引用值是 ref"""
        self.players[p]["node"] = node_id
        self.nodes[node_id] = ref
        return self

    def land(self, idx, name="S", owner=0, typ=0, level=1, house=100):
        self.lands[idx] = dict(name=name, owner=owner, typ=typ, level=level, house=house)
        return self

    def fac(self, idx, name="F", owner=0, typ=1, level=0, rate=100):
        self.facs[idx] = dict(name=name, owner=owner, typ=typ, level=level, rate=rate)
        return self

    def comm(self, idx, owner):
        self.comms[idx] = dict(owner=owner)
        return self

    def vis(self, *ps):
        """一个可见格，位上站着 ps 里的玩家（0 基）⇒ 标记 0x8000 | Σ 1<<p"""
        v = 0x8000
        for p in ps:
            v |= 1 << p
        self.visible.append(v & 0xFFFF)
        return self

    def raw_vis(self, v):
        self.visible.append(v & 0xFFFF)
        return self

    def _nlands(self):
        if self.num_lands is not None:
            return self.num_lands
        return max(self.lands) if self.lands else 0

    # ── 注入 / 回读 ─────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, self.num_players)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(NODE_PTR, NODES)
        emu.write32(LAND_PTR, LANDS)
        emu.write32(FAC_PTR, FACS)
        emu.write32(COMM_PTR, COMMS)
        emu.write32(NUM_LANDS, self._nlands())
        emu.write32(COUNT_SLOT, len(self.visible))
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_COUNT, 0)
        emu.write32(PARAM0, SENTINEL)
        emu.write32(PARAM1, SENTINEL)
        emu.write32(PARAM_X, SENTINEL)
        emu.write32(VIS_COUNT, SENTINEL)
        # ★ 暂存/自建区跨调用保留 ⇒ 先整片清零，避免用例互相污染
        emu.write(NODES, b"\x00" * NODES_ZERO)
        emu.write(LANDS, b"\x00" * LANDS_ZERO)
        emu.write(FACS, b"\x00" * FACS_ZERO)
        emu.write(COMMS, b"\x00" * COMMS_ZERO)
        emu.write(VIS_LIST, b"\x00" * 64)
        for i, v in enumerate(self.visible):
            emu.write16(VIS_LIST + i * 2, v & 0xFFFF)
        for nid, ref in self.nodes.items():
            emu.write16(NODES + nid * NODE_STRIDE + N_REF, ref & 0xFFFF)
        for p, pl in enumerate(self.players):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write16(pb + P_NODE, pl["node"] & 0xFFFF)
            emu.write8(pb + P_ALIVE, pl["alive"])
            emu.write32(pb + P_CASH, pl["cash"])
            emu.write32(pb + P_BANK, pl["bank"])
            emu.write8(pb + P_TORTOISE, pl["tortoise"])
            emu.write16(pb + P_FORTUNE, pl["fortune"] & 0xFFFF)
        for idx, l in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write8(b + L_TYPE, l["typ"])
            emu.write8(b + L_OWNER, l["owner"])
            emu.write8(b + L_LEVEL, l["level"])
            emu.write16(b + L_HOUSE, l["house"] & 0xFFFF)
            emu.write(b + L_NAME, l["name"].encode() + b"\x00")
        for idx, f in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write8(b + F_TYPE, f["typ"])
            emu.write8(b + F_OWNER, f["owner"])
            emu.write8(b + F_LEVEL, f["level"])
            emu.write16(b + F_RATE, f["rate"] & 0xFFFF)
            emu.write(b + F_NAME, f["name"].encode() + b"\x00")
        for idx, c in self.comms.items():
            emu.write8(COMMS + idx * COMM_STRIDE + C_OWNER, c["owner"])

    def run(self):
        r = self.emu.call(STOP_AI, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(PARAM0)
        self.arg1 = self.emu.readu32(PARAM1)
        self.argx = self.emu.readu32(PARAM_X)
        self.vis_count = self.emu.readu32(VIS_COUNT)
        self.rand_calls = self.emu.readu32(RAND_COUNT)
        return self


# ── 便捷场景 ────────────────────────────────────────────────────────
def my_land_hit(w, **land_kw):
    """基线：我站在自己 1 号住宅上，同街另有我的 2 号地 ⇒ 必中（写 0x48be58）。"""
    w.clear()
    w.me = 0
    w.stand(0, 1, LAND_LO + 1)
    kw = dict(name="S", owner=1, typ=0, level=1, house=100)
    kw.update(land_kw)
    w.land(1, **kw)
    w.land(2, name="S", owner=1, typ=0, level=1, house=100)
    w.pset(0, cash=20000, bank=0, fortune=0, tortoise=0)
    return w


def my_fac_hit(w, **fac_kw):
    """基线：我站在自己 1 号設施上（type 1、level 0、現金 20000）⇒ 必中。"""
    w.clear()
    w.me = 0
    w.stand(0, 1, FAC_LO + 1)
    kw = dict(name="F", owner=1, typ=1, level=0, rate=100)
    kw.update(fac_kw)
    w.fac(1, **kw)
    w.pset(0, cash=20000, bank=0, fortune=0, tortoise=0)
    return w


def rival_at(w, p, ref, node_id):
    """p 站在 node_id（引用值 ref）且**在可見表里**（标记 0x8000|1<<p）。"""
    w.stand(p, node_id, ref)
    w.vis(p)
    return w


def main():
    print("差分测试 · 停留卡（卡 6）AI 目标选择 0x41facc（898 B）\n")
    w = World()

    # ── A. 龜行闸：整段「对自己」的门 ────────────────────────────────
    print("[A] 龜行闸（player+0x39）：非 0 ⇒ 对自己两支**都**不看，但「对别人」照走")
    my_land_hit(w)
    w.pset(0, tortoise=1)
    r = w.run()
    case("★ 龜行中 + 本来会中的自格 ⇒ 不打自己（ret 0）", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    case("  但进了 PHASE2 ⇒ 0x48be60 被写成 0（可見表空）", r.vis_count, 0)

    my_land_hit(w)
    w.pset(0, tortoise=1)
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★ 龜行中 + 别人站在我 2 级設施上 ⇒ 「对别人」照打", r.ret, 1)
    case("  目标 = 0x8000|bit1 = 0x8002", r.target, 0x8002)

    my_land_hit(w)                                   # tortoise = 0
    r = w.run()
    case("★ 非龜行 ⇒ 自格命中：ret 1", r.ret, 1)
    case("  目标 = 0x8000|bit0 = 0x8001", r.target, 0x8001)
    case("★★ 自格命中在 PHASE2 之前返回 ⇒ 0x48be60 保持哨兵", r.vis_count, SENTINEL)

    w.clear()
    w.me = 0
    w.stand(0, 1, COMM_LO + 1)                       # 脚下是企業 ⇒ 无「对自己」
    w.pset(0, cash=20000, bank=0, fortune=0)
    r = w.run()
    case("★ 脚下是企業格 ⇒ 无自格分支（走 PHASE2，ret 0）", r.ret, 0)
    case("  PHASE2 确实进了（0x48be60 = 0）", r.vis_count, 0)

    # ── B. 「对自己·地块」的格值区间（开区间）────────────────────────
    print("\n[B] 「对自己·地块」区间 0x7d0 < ref < 0xfa0：两端都是开区间")
    # 下界：ref == 0x7d0（= 记录 0 号）永不可达
    my_land_hit(w)
    w.stand(0, 1, LAND_LO)                           # 0x7d0 恰好
    w.land(0, name="S", owner=1, typ=0, level=1, house=100)
    r = w.run()
    case("★★ ref = 0x7d0（地 0 号「记录 0」）⇒ **不算地產**，ret 0", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    # 上界：ref == 0xfa0 也不算地產（同时也不算設施）
    my_land_hit(w)
    w.stand(0, 1, LAND_HI)
    w.land(0x7D0, name="S", owner=1, typ=0, level=1, house=100)
    w.fac(0, owner=1, typ=1, level=0, rate=100)
    r = w.run()
    case("★★ ref = 0xfa0 ⇒ **两头都不算**（地產是 jge 跳出、設施是 jle 跳出）", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    # 上界内侧：ref = 0xf9f（地 0x7cf 号）算地產
    my_land_hit(w)
    w.stand(0, 1, LAND_HI - 1)
    w.land(0x7CF, name="S", owner=1, typ=0, level=1, house=100)
    r = w.run()
    case("★ ref = 0xf9f（地 0x7cf 号）⇒ 算地產，同街命中", r.ret, 1)
    case("  目标 = 0x8001", r.target, 0x8001)
    # 下界内侧：ref = 0x7d1 算地產（基线已覆盖）
    my_land_hit(w)
    r = w.run()
    case("★ ref = 0x7d1（地 1 号）⇒ 算地產（下界内侧）", r.target, 0x8001)

    # ── C. 「对自己·地块」五道门槛 + 边界严格性 ──────────────────────
    print("\n[C] 「对自己·地块」门槛：owner 1 基 / 住宅 / level<5 / 房价×物價<現金 / 存款计入 >10000 / 財運≥0")
    for desc, kw, want in [
        ("owner = 0（无主）", dict(owner=0), 0),
        ("owner = 2（不是 me+1）", dict(owner=2), 0),
        ("type = 1（不是住宅）", dict(typ=1), 0),
        ("type = 255", dict(typ=255), 0),
        ("level = 5", dict(level=5), 0),
    ]:
        my_land_hit(w, **kw)
        r = w.run()
        case(f"{desc} ⇒ 不中（ret 0）", r.ret, want)
        case("  没写 0x48be58", r.target, SENTINEL)

    my_land_hit(w, level=4)
    r = w.run()
    case("★ level = 4（< 5 的上边界内侧）⇒ 中", r.ret, 1)

    my_land_hit(w, house=20001)
    w.pset(0, cash=20001)
    r = w.run()
    case("★★ 房价×物價 == 現金 ⇒ 不中（`jge` ⇒ 严格 <）", r.ret, 0)
    my_land_hit(w, house=20000)
    w.pset(0, cash=20001)
    r = w.run()
    case("★ 房价×物價 = 現金−1 ⇒ 中", r.ret, 1)

    my_land_hit(w, house=100)
    w.price = 10                                     # 100×10 = 1000
    w.pset(0, cash=1000, bank=10000)
    r = w.run()
    case("★ 房价×物價指数确实相乘（100×10 == 現金 1000 ⇒ 不中）", r.ret, 0)
    w.pset(0, cash=1001, bank=10000)
    r = w.run()
    case("  現金 1001（存款另计 10000）⇒ 中", r.ret, 1)

    my_land_hit(w)
    w.pset(0, cash=10000, bank=0)
    r = w.run()
    case("★★ 現金+存款 == 10000 ⇒ 不中（`jle` ⇒ 严格 > 10000）", r.ret, 0)
    w.pset(0, cash=10001, bank=0)
    r = w.run()
    case("  現金+存款 == 10001 ⇒ 中", r.ret, 1)
    w.pset(0, cash=6000, bank=5000)
    r = w.run()
    case("★ 存款**计入**：6000+5000 = 11000 > 10000 ⇒ 中", r.ret, 1)
    w.pset(0, cash=6000, bank=0)
    r = w.run()
    case("  只有現金 6000 ⇒ 不中", r.ret, 0)

    my_land_hit(w)
    w.pset(0, fortune=-1)
    r = w.run()
    case("★ 財運(+0x46, 有符号 16 位) = −1 ⇒ 不中", r.ret, 0)
    w.pset(0, fortune=0)
    r = w.run()
    case("  財運 = 0（≥0 的下边界）⇒ 中", r.ret, 1)

    # ── D. 同街扫描：1 基、含上界、看不到记录 0、跳过自己 ────────────
    print("\n[D] 同街扫描 `for (i=1; i<=[0x498e98]; i++)`：同名 + owner == me+1")
    my_land_hit(w, level=1)
    w.lands.pop(2)                                   # 没有同街伙伴
    r = w.run()
    case("★ 无同街伙伴、level 1 ⇒ 落到 PHASE2（ret 0，0x48be60 被写 0）",
         (r.ret, r.vis_count, r.target), (0, 0, SENTINEL))

    my_land_hit(w, level=1)
    w.lands[2]["owner"] = 0                          # 同街但无主
    r = w.run()
    case("★ 同街但 owner=0 ⇒ 不算（ret 0）", r.ret, 0)
    my_land_hit(w, level=1)
    w.lands[2]["owner"] = 3                          # 同街但别人的
    r = w.run()
    case("★ 同街但是别人的（owner 3）⇒ 不算（ret 0）", r.ret, 0)

    my_land_hit(w, level=1)
    w.lands[2]["name"] = "T"                         # 不同街
    r = w.run()
    case("★ 不同名（不同街）⇒ 不算（ret 0）", r.ret, 0)

    my_land_hit(w, level=1, name="AB")
    w.lands[2]["name"] = "AC"
    r = w.run()
    case("★ 名字逐字节比较（AB vs AC）⇒ 不算", r.ret, 0)
    my_land_hit(w, level=1, name="AB")
    w.lands[2]["name"] = "AB"
    r = w.run()
    case("  AB vs AB ⇒ 算", r.ret, 1)

    # 记录 0 永远看不到
    my_land_hit(w, level=1)
    w.lands.pop(2)
    w.land(0, name="S", owner=1, typ=0, level=1, house=100)
    r = w.run()
    case("★★ 同街同主的伙伴放在**记录 0** ⇒ 扫描从 1 起 ⇒ 看不到（ret 0）", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    # 上界含等号
    my_land_hit(w, level=1)
    w.lands.pop(2)
    w.land(3, name="S", owner=1, typ=0, level=1, house=100)
    w.num_lands = 3
    r = w.run()
    case("★ 伙伴在**记录 N**（== [0x498e98]）⇒ 含上界 ⇒ 命中", r.target, 0x8001)
    w.num_lands = 2                                  # 同一份数据，上界收到 2
    r = w.run()
    case("★★ 同一份数据、上界 N=2 ⇒ 记录 3 看不到（`jg` ⇒ 含上界）", r.ret, 0)

    # 跳过自己
    w.clear()
    w.me = 0
    w.stand(0, 1, LAND_LO + 1)
    w.land(1, name="S", owner=1, typ=0, level=1, house=100)
    w.pset(0, cash=20000, bank=0, fortune=0)
    w.num_lands = 1
    r = w.run()
    case("★★ 只有自己那块地（`i == ref-0x7d0` 被跳过）⇒ 不算「同街另有」⇒ ret 0", r.ret, 0)

    # ── E. ★★ level ≥ 2 的提前返回：返回 1 但**不写参数** ─────────────
    print("\n[E] ★★ `level ≥ 2` 支：返回 1 但 **[0x48be58] 一个字节都不写**")
    my_land_hit(w, level=2)
    w.lands.pop(2)
    r = w.run()
    case("★★ level 2、无同街伙伴 ⇒ ret 1", r.ret, 1)
    case("★★★ 但 0x48be58 **保持哨兵**（0x41fc1d `jmp 0x41fbf8` 跳过存值）",
         r.target, SENTINEL)
    case("★★ 且**没进** PHASE2 ⇒ 0x48be60 保持哨兵", r.vis_count, SENTINEL)

    my_land_hit(w, level=3)
    w.lands.pop(2)
    r = w.run()
    case("★ level 3、无同街伙伴 ⇒ 同样 ret 1 且不写参数", (r.ret, r.target), (1, SENTINEL))

    # 判别：level 1 会落到 PHASE2，level 2 不会
    my_land_hit(w, level=1)
    w.lands.pop(2)
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★ 对照组 level 1：自格不成立 ⇒ 落到 PHASE2 ⇒ 打到别人（0x8002）", r.target, 0x8002)
    my_land_hit(w, level=2)
    w.lands.pop(2)
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★★ level 2：自格那半支**提前返回** ⇒ PHASE2 的别人**打不到**（参数仍哨兵）",
         (r.ret, r.target), (1, SENTINEL))

    # ── F. 「对自己·設施」 ──────────────────────────────────────────
    print("\n[F] 「对自己·設施」0xfa0 < ref < 0x1770：不看同街、現金 > 10000（**不加存款**）")
    my_fac_hit(w)
    r = w.run()
    case("★ 基线：type 1、level 0、rate 100×物價1 < 20000、現金 20000 > 10000 ⇒ 中", r.ret, 1)
    case("  目标 = 0x8001", r.target, 0x8001)

    for desc, kw, want in [
        ("owner = 0", dict(owner=0), 0),
        ("owner = 2", dict(owner=2), 0),
        ("type = 0（公園）", dict(typ=0), 0),
        ("type = 3（加油站）", dict(typ=3), 0),
        ("level = 5", dict(level=5), 0),
    ]:
        my_fac_hit(w, **kw)
        r = w.run()
        case(f"★ 設施 {desc} ⇒ 不中（ret 0）", r.ret, want)
        case("  没写 0x48be58", r.target, SENTINEL)
    my_fac_hit(w, typ=4)
    r = w.run()
    case("★ type = 4 ⇒ 中（只排除 0 与 3）", r.ret, 1)
    my_fac_hit(w, level=4)
    r = w.run()
    case("★ level = 4 ⇒ 中（上界内侧）", r.ret, 1)

    my_fac_hit(w, rate=20001)
    w.pset(0, cash=20001)
    r = w.run()
    case("★★ rate×物價 == 現金 ⇒ 不中（严格 <）", r.ret, 0)
    my_fac_hit(w, rate=20000)
    w.pset(0, cash=20001)
    r = w.run()
    case("  rate×物價 = 現金−1 ⇒ 中", r.ret, 1)
    my_fac_hit(w)
    w.pset(0, cash=10000)
    r = w.run()
    case("★★ 現金 == 10000 ⇒ 不中（`jle`）", r.ret, 0)
    my_fac_hit(w)
    w.pset(0, cash=10001)
    r = w.run()
    case("  現金 == 10001 ⇒ 中", r.ret, 1)
    my_fac_hit(w)
    w.pset(0, cash=6000, bank=100000)
    r = w.run()
    case("★★★ 設施这条**不算存款**：現金 6000 + 存款 100000 ⇒ 仍不中", r.ret, 0)
    my_fac_hit(w)
    w.pset(0, fortune=-1)
    r = w.run()
    case("★ 財運 = −1 ⇒ 不中", r.ret, 0)
    my_fac_hit(w)
    w.pset(0, fortune=0)
    r = w.run()
    case("  財運 = 0 ⇒ 中", r.ret, 1)

    # 設施区间两端
    w.clear()
    w.me = 0
    w.stand(0, 1, FAC_LO)                            # 0xfa0 恰好
    w.fac(0, owner=1, typ=1, level=0, rate=100)
    w.pset(0, cash=20000, fortune=0)
    r = w.run()
    case("★★ ref = 0xfa0（設施 0 号）⇒ 不算設施（`jle`）", r.ret, 0)
    w.clear()
    w.me = 0
    w.stand(0, 1, FAC_HI - 1)                        # 0x176f = 設施 0x7cf 号
    w.fac(0x7CF, owner=1, typ=1, level=0, rate=100)
    w.pset(0, cash=20000, fortune=0)
    r = w.run()
    case("★ ref = 0x176f（設施 0x7cf 号）⇒ 算設施、命中", r.ret, 1)
    w.clear()
    w.me = 0
    w.stand(0, 1, FAC_HI)                            # 0x1770 恰好
    w.fac(0, owner=1, typ=1, level=0, rate=100)
    w.pset(0, cash=20000, fortune=0)
    r = w.run()
    case("★★ ref = 0x1770 ⇒ 不算設施（`jge`），也不算企業（`jbe`）⇒ ret 0", r.ret, 0)

    # ── G. 「对别人」：設施 / 企業，地块不收 ────────────────────────
    print("\n[G] 「对别人」：r 在設施/企業区间才看；**地块完全不看**")
    w.clear()
    w.me = 0
    w.pset(0, cash=0, fortune=0)
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★ 别人站在我 2 级設施上 ⇒ ret 1、目标 0x8002", (r.ret, r.target), (1, 0x8002))
    case("  0x48be5c 保持哨兵", r.arg1, SENTINEL)
    case("  0x48be64 保持哨兵", r.argx, SENTINEL)

    w.facs[1]["level"] = 1
    r = w.run()
    case("★★ 設施 level = 1 ⇒ 不中（这条支要 ≥ 2）", r.ret, 0)
    w.facs[1]["level"] = 2
    w.facs[1]["typ"] = 0
    r = w.run()
    case("★ 設施 type = 0（公園）⇒ 「对别人」也不打", r.ret, 0)
    w.facs[1]["typ"] = 3
    r = w.run()
    case("★★★ 設施 type = 3（加油站）⇒ 「对别人」**照打**（与「对自己」不对称！）",
         (r.ret, r.target), (1, 0x8002))
    w.facs[1]["typ"] = 1
    w.facs[1]["owner"] = 0
    r = w.run()
    case("★ 他人脚下設施无主 ⇒ 不中", r.ret, 0)
    w.facs[1]["owner"] = 3
    r = w.run()
    case("★ 他人脚下設施是**别人**的（owner 3）⇒ 不中", r.ret, 0)
    w.facs[1]["owner"] = 1

    w.clear()
    w.me = 0
    w.pset(0, cash=0)
    rival_at(w, 1, COMM_LO + 1, 20).comm(1, owner=1)
    r = w.run()
    case("★ 别人站在**我当董事長**的企業上 ⇒ ret 1、目标 0x8002", (r.ret, r.target), (1, 0x8002))
    w.comms[1]["owner"] = 0
    r = w.run()
    case("  企業無主 ⇒ 不中", r.ret, 0)
    w.comms[1]["owner"] = 2
    r = w.run()
    case("  企業是别人的 ⇒ 不中", r.ret, 0)

    w.clear()
    w.me = 0
    w.pset(0, cash=0)
    rival_at(w, 1, LAND_LO + 1, 20).land(1, name="S", owner=1, typ=0, level=5, house=100)
    r = w.run()
    case("★★★ 别人站在**我的 5 级地**上 ⇒ 「对别人」**完全不看地块** ⇒ ret 0", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    # 企業区间两端
    w.clear()
    w.me = 0
    rival_at(w, 1, COMM_HI - 1, 20).comm(0x7CF, owner=1)
    r = w.run()
    case("★ 企業 r = 0x1f3f（0x7cf 号）⇒ 命中 0x8002", (r.ret, r.target), (1, 0x8002))
    w.clear()
    w.me = 0
    rival_at(w, 1, COMM_HI, 20).comm(0, owner=1)
    r = w.run()
    case("★★ r = 0x1f40（企業 0x7d0 号）⇒ 越界 ⇒ ret 0", r.ret, 0)
    w.clear()
    w.me = 0
    rival_at(w, 1, FAC_HI - 1, 20).fac(0x7CF, owner=1, typ=1, level=2)
    r = w.run()
    case("★ 設施 r = 0x176f（0x7cf 号）⇒ 命中 0x8002", (r.ret, r.target), (1, 0x8002))

    # 出局 / 自己 / 不可见
    print("\n[H] 「对别人」的闸：出局跳过、自己跳过、**不在可見表里就看不到**")
    w.clear()
    w.me = 0
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    w.pset(1, alive=0)
    r = w.run()
    case("★ 出局者站在我設施上 ⇒ 跳过", r.ret, 0)

    w.clear()
    w.me = 0
    w.stand(0, 1, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    w.vis(0)
    r = w.run()
    case("★ 可見表里只有我自己（0x8001）⇒ 不打自己", r.ret, 0)
    case("  ret 0 而不是 1", r.target, SENTINEL)

    w.clear()
    w.me = 0
    w.stand(1, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)   # 站位有，**没进可見表**
    r = w.run()
    case("★★ 没在可見表里 ⇒ nodeRef = 0 ⇒ 看不到（即便地图格上确实站着）", r.ret, 0)

    w.clear()
    w.me = 0
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    rival_at(w, 2, FAC_LO + 1, 21)
    r = w.run()
    case("★ 两个都合格 ⇒ 取**下标小**的先到先得（0x8002）", r.target, 0x8002)
    w.clear()
    w.me = 0
    rival_at(w, 2, FAC_LO + 1, 21).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("  只有 2 号 ⇒ 0x8004", r.target, 0x8004)

    w.clear()
    w.me = 0
    w.num_players = 2                                # 上界 = 2 ⇒ 只看 0/1
    rival_at(w, 2, FAC_LO + 1, 21).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★★ [0x499114] = 2 ⇒ 2 号不在遍历范围 ⇒ ret 0（缺上界全局会静默退化）", r.ret, 0)
    w.num_players = 3
    r = w.run()
    case("  [0x499114] = 3 ⇒ 又能看到 2 号 ⇒ 0x8004", (r.ret, r.target), (1, 0x8004))

    # ── I. 可見表的编码：bit15 + 低 4 位、位 p ⇒ 玩家 p ──────────────
    print("\n[I] 可見表编码：必须带 bit15 且低 4 位非 0；位 p ⇒ 玩家 p（0 基）")
    w.clear()
    w.me = 0
    w.raw_vis(0x0004)                                # 低 4 位有、bit15 没有
    w.stand(1, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★★ 没有 bit15（0x0004）⇒ 整项跳过 ⇒ 看不到人（ret 0）", r.ret, 0)

    w.clear()
    w.me = 0
    w.raw_vis(0x8000)                                # bit15 有、低 4 位 = 0
    w.stand(1, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★★ 低 4 位 = 0（0x8000，物件标记那一类）⇒ 整项跳过（ret 0）", r.ret, 0)

    for p in (1, 2, 3):
        w.clear()
        w.me = 0
        rival_at(w, p, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
        r = w.run()
        case(f"★ 玩家 {p} 的标记 0x{0x8000 | (1 << p):04x} ⇒ 目标 0x{0x8000 | (1 << p):04x}",
             r.target, 0x8000 | (1 << p))

    w.clear()
    w.me = 0
    w.raw_vis(0x8014)                                # bit15 | bit4 | bit2
    w.stand(2, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    w.stand(1, 21, FAC_LO + 1)
    r = w.run()
    case("★ 位循环只走 0..3：0x8014 只认位 2 ⇒ 0x8004（bit4 不参与）", (r.ret, r.target), (1, 0x8004))

    w.clear()
    w.me = 0
    rival_at(w, 2, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    w.raw_vis(0x8001)                                # 第一项只有我
    r = w.run()
    case("★ 多项可见表逐项累积 ⇒ 第二项里的 2 号照样看得到（0x8004）",
         (r.ret, r.target), (1, 0x8004))
    case("  0x48be60 == 可见项数 2", r.vis_count, 2)

    w.clear()
    w.me = 0
    w.raw_vis(0x800F)                                # 四位玩家全在
    w.stand(1, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    w.stand(2, 21, LAND_LO + 1).land(1, name="S", owner=1, typ=0, level=5, house=1)
    w.stand(3, 22, FAC_HI + 1).fac(0, owner=1, typ=1, level=1)
    r = w.run()
    case("★ 四位全在 ⇒ 先到先得取 1 号（0x8002）", r.target, 0x8002)

    w.clear()
    w.me = 0
    w.raw_vis(0x8004)                                # 行序：2 号在前
    w.raw_vis(0x8002)                                #       1 号在后
    w.stand(1, 20, FAC_LO + 1).fac(1, owner=1, typ=1, level=2)
    w.stand(2, 21, FAC_LO + 1)
    r = w.run()
    case("★★ 选中次序 = **玩家下标**（0..N-1）而不是可見表行序 ⇒ 仍是 1 号 0x8002",
         (r.ret, r.target), (1, 0x8002))

    # ── J. 输出全局 / 返回值 / 随机数消耗 ────────────────────────────
    print("\n[J] 输出：只写 0x48be58（+ PHASE2 时写 0x48be60）；不碰 0x48be5c/0x48be64")
    seen = set()
    w.clear()
    r = w.run()
    seen.add(r.ret)
    case("  空局面 ⇒ ret 0", r.ret, 0)
    case("  0x48be60 被写成 0", r.vis_count, 0)
    my_land_hit(w)
    seen.add(w.run().ret)
    my_land_hit(w, level=2)
    w.lands.pop(2)
    seen.add(w.run().ret)
    w.clear()
    w.me = 0
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    seen.add(w.run().ret)
    case("  四种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    my_land_hit(w)
    r = w.run()
    case("★ 自格命中：0x48be5c 哨兵", r.arg1, SENTINEL)
    case("★ 自格命中：0x48be64 哨兵", r.argx, SENTINEL)

    # 目标里的「我」是 1<<me
    for me in (0, 1, 2, 3):
        w.clear()
        w.me = me
        w.stand(me, 1, LAND_LO + 1)
        w.land(1, name="S", owner=me + 1, typ=0, level=1, house=100)
        w.land(2, name="S", owner=me + 1, typ=0, level=1, house=100)
        w.pset(me, cash=20000, bank=0, fortune=0)
        r = w.run()
        case(f"★ me = {me} ⇒ 自格目标 = 0x8000|(1<<{me}) = 0x{0x8000 | (1 << me):04x}",
             (r.ret, r.target), (1, 0x8000 | (1 << me)))

    # rand 一次也不摇
    my_land_hit(w)
    r = w.run()
    case("★★ 自格命中：rand() 调用 0 次", r.rand_calls, 0)
    w.clear()
    w.me = 0
    r = w.run()
    case("★ 空局面：rand() 调用 0 次", r.rand_calls, 0)
    w.clear()
    w.me = 0
    rival_at(w, 1, FAC_LO + 1, 20).fac(1, owner=1, typ=1, level=2)
    r = w.run()
    case("★ 「对别人」命中：rand() 调用 0 次（本函数无随机）", r.rand_calls, 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
