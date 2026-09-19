#!/usr/bin/env python3
"""
通道 2 差分测试 · **十三件道具的 AI 判定**（跳表入口 `0x420e9a` 的 members）

复刻侧对应 `packages/core/src/ai/tool-policy.ts`。这些判定函数**没有 `call` 调用者**
（AI 出牌跳表的成员），建图工具不收 ⇒ 用
`rich4-remake/tools/disasm.py va <地址>` 按需反汇编。

本文件覆盖（逐个 function VA）：

| 道具 | VA | 语义 |
|---|---|---|
| 5 機車 | `0x421644` | `(traffic & 3) == 0` 且 `rand()%4 == 0` |
| 6 汽車 | `0x421675` | `(traffic & 3) < 2` 且 `rand()%4 == 0` |
| 12 工程車 | `0x421e20` | `(traffic & 3) == 3` → 不用；否则 `rand()%15 <= 個性` |
| 1 機器娃娃 | `0x420efa` | 前瞻 4 格无岔路；路径格上的坏物件/我的地雷/别人路障 |
| 3 地雷 | `0x4213c5` | 反瞻 6 格 ∩ 画面；只收**别人的**地/設施；`rand()%候选数` |
| 4 定時炸彈 | `0x421574` | 同上，但**什么格都收** |

★ 本文件最重要的一条发现（[E]/[F] 两组）：原版在监狱/医院那两格里比的是
**`cmp dword [0x496b30], 0`（4 字节 = 只含槽 0..3 玩家）**，而复刻的
`ai/tool-policy.ts` 用了 `anyoneConfined`（**8 槽**，含 4..7 物件槽）。
这正是 §四之二 第 3 条在「落点 8 槽 / 新闻 4 字节」上修过的**同一个宽度区分**，
只是当时漏了道具 AI 这一处（第三处）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040b221` | 前瞻 | 从数据槽拷 n 个 word 进 `0x48b8b4`，返回「是否岔路」 | 它自己的语义已由 `tests/test_lookahead.py`（58/58）独立驱动 |
| `0x0040b343` | 反瞻 | 同上 | 同上 |
| `0x00409ef9` | 填「可见**节点**表」 | 从数据槽拷入 `0x48b8c4`，返回项数 | 视野口径差异 = **D-005**，不是本测试对象 |
| `0x0040a45c` | 填「可见**实体**表」 | 同上 | 同上 |
| `0x00419744` | 该地主在这条街的住宅过路费 | 从数据槽读 | 它自己的语义另属 `land-rent.md` |
| `0x00456f2d` | CRT `rand()` | 从数据槽读，并**自增一个计数槽**（用来断言"摇没摇"）| 本测试只钉取模规则与消费时机 |

`0x48bae0`/`0x48bae2`（监狱/医院节点 id）与 `0x496b30`/`0x496b60`（占用表）
由 `setup()` 直接铺 —— 本测试要的正是这两个判据的**宽度**。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_policy_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
JICHE = 0x421644          # 5 機車
QICHE = 0x421675          # 6 汽車
GONGCHENG = 0x421E20      # 12 工程車
DOLL = 0x420EFA           # 1 機器娃娃
MINE = 0x4213C5           # 3 地雷
BOMB = 0x421574           # 4 定時炸彈

# ── 打桩 ──
LOOK_FWD = 0x40B221
LOOK_BACK = 0x40B343
VISIBLE_NODES = 0x409EF9
VISIBLE_ENTITIES = 0x40A45C
STREET_TOLL = 0x419744
PRNG = 0x456F2D

# ── 全局 ──
CUR = 0x49910C                 # 当前玩家（0 基）
PRICE_INDEX = 0x4990E8
NODE_TABLE_PTR = 0x498E80
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
OBJ_TABLE = 0x496D08           # 地图物件表**绝对地址**（不是指针）：+0 类型，步长 0x18
PRISON_NODE = 0x48BAE0         # word：监狱所在节点 id
HOSPITAL_NODE = 0x48BAE2       # word：医院所在节点 id
PRISON_OCC = 0x496B30          # byte[8]：占用表（0..3 玩家 / 4..7 物件）
HOSPITAL_OCC = 0x496B60
TOOL_PARAM = 0x48BE64          # AI 道具参数出口
LOOK_BUF = 0x48B8B4            # 前瞻/反瞻共用输出缓冲（8 word）
VIS_LIST = 0x48B8C4            # 可见表（word 数组）

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_TRAFFIC, P_PERSONALITY = 0x11, 0x17

NODE_STRIDE = 0x28
N_ENTITY = 0x20                # word：实体格值（地块 0x7d0+i / 設施 0xfa0+i / 企業…）
N_OBJ = 0x24                   # dword：bits 16-21 = 物件下标 + 1

LAND_STRIDE, L_OWNER = 0x34, 0x19
FAC_STRIDE, F_OWNER = 0x38, 0x19
OBJ_STRIDE, O_TYPE = 0x18, 0x00

LAND_MARK, FAC_MARK, COMM_MARK = 0x7D0, 0xFA0, 0x1770

NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000
PATH_SRC = SCRATCH_BASE + 0x8000  # 前瞻/反瞻输出源区（避开 LANDS 0x3000 / FACS 0x6000）
VIS_SRC = SCRATCH_BASE + 0x8400   # 可见表源区
# ★ 两处桩各用**自己的**源/计数/返回槽 —— 共用会让可见表覆盖路径源
LOOK_SRC, LOOK_COUNT, LOOK_RET = (SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x900,
                                  SCRATCH_BASE + 0x904)
VIS_SRC_SLOT, VIS_COUNT, VIS_RET = (SCRATCH_BASE + 0x908, SCRATCH_BASE + 0x90C,
                                    SCRATCH_BASE + 0x910)
RAND_SLOT = SCRATCH_BASE + 0x914
RAND_CALLS = SCRATCH_BASE + 0x918
TOLL_SLOT = SCRATCH_BASE + 0x91C

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def _copy_stub(dst: int, src_slot: int, count_slot: int, ret_slot: int) -> bytes:
    """把 [src_slot] 起的 [count_slot] 个 word 拷到 dst，返回 [ret_slot]。

    必须**保留 esi/edi/ecx**：被测函数把循环状态放在 edi/esi 里
    （例如 `0x420efa` 用 edi 当路径下标、esi 当命中标志），
    而原版那两支都有自己的 push/pop 序言。
    """
    return (
        b"\x56\x57\x51"                                       # push esi / edi / ecx
        + b"\xA1" + struct.pack("<I", count_slot)             # mov eax,[count]
        + b"\x89\xC1"                                         # mov ecx,eax
        + b"\xA1" + struct.pack("<I", src_slot)               # mov eax,[src]
        + b"\x89\xC6"                                         # mov esi,eax
        + b"\xBF" + struct.pack("<I", dst)                    # mov edi,dst
        + b"\xF3\x66\xA5"                                     # rep movsw
        + b"\x59\x5F\x5E"                                     # pop ecx / edi / esi
        + b"\xA1" + struct.pack("<I", ret_slot)               # mov eax,[ret]
        + b"\xC3"
    )


class World:
    def __init__(self):
        self.emu = Emu()
        # rand()：读数据槽 + 自增调用计数
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.emu.patch(STREET_TOLL, b"\xA1" + struct.pack("<I", TOLL_SLOT) + b"\xC3")
        stub = _copy_stub(LOOK_BUF, LOOK_SRC, LOOK_COUNT, LOOK_RET)
        self.emu.patch(LOOK_FWD, stub)
        self.emu.patch(LOOK_BACK, stub)
        vis = _copy_stub(VIS_LIST, VIS_SRC_SLOT, VIS_COUNT, VIS_COUNT)  # ★ 返回**项数**
        self.emu.patch(VISIBLE_NODES, vis)
        self.emu.patch(VISIBLE_ENTITIES, vis)
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.me = 0
        self.traffic = [0, 0, 0, 0]
        self.personality = [1, 1, 1, 1]
        self.price = 1
        self.path = []             # 前瞻/反瞻输出（节点 id）
        self.forked = 0
        self.visible = []          # 可见**节点**表
        self.nodes = {}            # id → (entity, obj_index_1based)
        self.lands = {}            # idx → owner
        self.facs = {}             # idx → owner
        self.objs = {}             # idx(1 基) → type
        self.prison_node = 0
        self.hospital_node = 0
        self.prison_occ = [0] * 8
        self.hospital_occ = [0] * 8
        self.rand = 0
        self.toll = 0
        return self

    def land_node(self, nid, idx, owner=0):
        self.nodes[nid] = (LAND_MARK + idx, self.nodes.get(nid, (0, 0))[1])
        self.lands[idx] = owner
        return self

    def fac_node(self, nid, idx, owner=0):
        self.nodes[nid] = (FAC_MARK + idx, self.nodes.get(nid, (0, 0))[1])
        self.facs[idx] = owner
        return self

    def ghost_node(self, nid):
        """无实体、无物件的空格"""
        self.nodes.setdefault(nid, (0, 0))
        return self

    def with_obj(self, nid, obj_index, otype):
        """给节点挂一个物件（obj_index 1 基，写进 node+0x24 的 bits 16-21）"""
        ent = self.nodes.get(nid, (0, 0))[0]
        self.nodes[nid] = (ent, obj_index)
        self.objs[obj_index] = otype
        return self

    def path_of(self, *nids, forked=0):
        self.path = list(nids)
        self.forked = forked
        return self

    def see(self, *nids):
        self.visible = list(nids)
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(TOOL_PARAM, SENTINEL)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write32(TOLL_SLOT, self.toll)
        emu.write32(LOOK_SRC, PATH_SRC)
        emu.write32(LOOK_COUNT, len(self.path))
        emu.write32(LOOK_RET, self.forked)
        emu.write32(VIS_SRC_SLOT, VIS_SRC)
        emu.write32(VIS_COUNT, len(self.visible))
        emu.write32(VIS_RET, 0)
        emu.write16(PRISON_NODE, self.prison_node & 0xFFFF)
        emu.write16(HOSPITAL_NODE, self.hospital_node & 0xFFFF)
        # ★ 跨调用保留 ⇒ 先清表
        emu.write(NODES, b"\x00" * (NODE_STRIDE * 64))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(OBJ_TABLE, b"\x00" * (OBJ_STRIDE * 16))
        emu.write(LOOK_BUF, b"\x00" * 16)
        emu.write(VIS_LIST, b"\x00" * 64)
        # 路径 / 可见表：两处各写自己的源区
        emu.write(PATH_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.path))
        emu.write(VIS_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.visible))
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_TRAFFIC, self.traffic[p])
            emu.write8(pb + P_PERSONALITY, self.personality[p])
        for nid, (ent, obj) in self.nodes.items():
            b = NODES + nid * NODE_STRIDE
            emu.write16(b + N_ENTITY, ent & 0xFFFF)
            emu.write32(b + N_OBJ, ((obj & 0x3F) << 16) & 0xFFFFFFFF)
        for idx, owner in self.lands.items():
            emu.write8(LANDS + idx * LAND_STRIDE + L_OWNER, owner)
        for idx, owner in self.facs.items():
            emu.write8(FACS + idx * FAC_STRIDE + F_OWNER, owner)
        for idx, t in self.objs.items():
            emu.write8(OBJ_TABLE + (idx - 1) * OBJ_STRIDE + O_TYPE, t)  # ★ 0 基（先 dec）
        for i, v in enumerate(self.prison_occ):
            emu.write8(PRISON_OCC + i, v)
        for i, v in enumerate(self.hospital_occ):
            emu.write8(HOSPITAL_OCC + i, v)

    def run(self, func):
        r = self.emu.call(func, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(TOOL_PARAM)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        return self


def main():
    print("差分测试 · 道具 AI 判定（機車/汽車/工程車/機器娃娃/地雷/定時炸彈）\n")
    w = World()

    # ═══════════════ [A] 機車 0x421644 ═══════════════
    print("[A] 5 機車 `0x421644`：(traffic & 3) == 0 且 rand()%4 == 0")
    for traffic, rand, want, calls in [
        (0, 0, 1, 1), (0, 1, 0, 1), (0, 3, 0, 1),
        (1, 0, 0, 0), (2, 0, 0, 0), (3, 0, 0, 0),
        (4, 0, 1, 1),          # 只比低 2 位 ⇒ 4 & 3 == 0
        (0xFC, 0, 1, 1),       # 高位不参与
    ]:
        w.clear(); w.traffic[0] = traffic; w.rand = rand
        r = w.run(JICHE)
        case(f"traffic=0x{traffic:02x} rand={rand} ⇒ 返回 {want}", r.ret, want)
        case("  rand 消费次数", r.rand_calls, calls)

    # ═══════════════ [B] 汽車 0x421675 ═══════════════
    print("\n[B] 6 汽車 `0x421675`：(traffic & 3) < 2 且 rand()%4 == 0")
    for traffic, rand, want, calls in [
        (0, 0, 1, 1), (1, 0, 1, 1),
        (2, 0, 0, 0), (3, 0, 0, 0),
        (0, 2, 0, 1), (1, 3, 0, 1),
        (5, 0, 1, 1),          # 5 & 3 == 1 < 2
        (6, 0, 0, 0),          # 6 & 3 == 2
    ]:
        w.clear(); w.traffic[0] = traffic; w.rand = rand
        r = w.run(QICHE)
        case(f"traffic=0x{traffic:02x} rand={rand} ⇒ 返回 {want}", r.ret, want)
        case("  rand 消费次数", r.rand_calls, calls)

    # ═══════════════ [C] 工程車 0x421e20 ═══════════════
    print("\n[C] 12 工程車 `0x421e20`：(traffic & 3) == 3 → 不用；否则 rand()%15 <= 個性")
    for traffic, personality, rand, want, calls in [
        (3, 255, 0, 0, 0),     # 已开着 → 不摇
        (7, 255, 0, 0, 0),     # 7 & 3 == 3
        (0, 0, 0, 1, 1),       # 0 <= 0
        (0, 0, 1, 0, 1),       # 1 > 0
        (0, 1, 1, 1, 1),       # 1 <= 1
        (0, 1, 2, 0, 1),       # 2 > 1
        (0, 14, 14, 1, 1),     # 14 <= 14
        (0, 14, 0, 1, 1),
        (0, 255, 14, 1, 1),    # 個性 255（大老奸）→ 一律肯
        (0, 3, 4, 0, 1),
        (2, 14, 15 % 15, 1, 1),
    ]:
        w.clear(); w.traffic[0] = traffic; w.personality[0] = personality; w.rand = rand
        r = w.run(GONGCHENG)
        case(f"traffic={traffic} 個性={personality} rand={rand} ⇒ {want}", r.ret, want)
        case("  rand 消费次数", r.rand_calls, calls)

    # ═══════════════ [D] 機器娃娃 0x420efa ═══════════════
    print("\n[D] 1 機器娃娃 `0x420efa`：前瞻 4 格无岔路；扫描路径格上的物件")
    w.clear(); w.path_of(11, 12, 13, 14, forked=1)
    r = w.run(DOLL)
    case("★ 有岔路（forked）⇒ 直接不用", r.ret, 0)

    w.clear(); w.path_of(11, 12, 13, 14, forked=0).ghost_node(11)
    r = w.run(DOLL)
    case("路径格全空 ⇒ 不用", r.ret, 0)

    # 坏神/惡犬：5,6,7,8,11
    for t in (5, 6, 7, 8, 11):
        w.clear(); w.land_node(11, 1, 0).with_obj(11, 1, t)
        w.path_of(11, 12, 13, 14, forked=0)
        r = w.run(DOLL)
        case(f"★ 路径上物件类型 {t}（坏神/惡犬）⇒ 用", r.ret, 1)

    for t in (0, 1, 3, 9, 12, 15, 18):
        w.clear(); w.land_node(11, 1, 0).with_obj(11, 1, t)
        w.path_of(11, 12, 13, 14, forked=0)
        r = w.run(DOLL)
        case(f"  物件类型 {t} ⇒ 不用", r.ret, 0)

    # 地雷（17）只在我自己的地上才用
    w.clear(); w.land_node(11, 1, 1).with_obj(11, 1, 17)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("★ 我的地上的地雷(17) ⇒ 用", r.ret, 1)

    w.clear(); w.land_node(11, 1, 2).with_obj(11, 1, 17)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("★ 别人地上的地雷(17) ⇒ 不用（那是别人的雷）", r.ret, 0)

    w.clear(); w.land_node(11, 1, 0).with_obj(11, 1, 17)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("  无主地上的地雷(17) ⇒ 不用", r.ret, 0)

    # 路障（16）：别人的地，且该地主同街过路费 > 3000×物價
    w.clear(); w.land_node(11, 1, 2).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 1; w.toll = 3001
    r = w.run(DOLL)
    case("★★ 別人地上的路障(16)、过路费 3001 > 3000×1 ⇒ 用", r.ret, 1)

    w.clear(); w.land_node(11, 1, 2).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 1; w.toll = 3000
    r = w.run(DOLL)
    case("★★ 过路费 3000（不严格大于 3000×1）⇒ 不用", r.ret, 0)

    w.clear(); w.land_node(11, 1, 2).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 2; w.toll = 6000
    r = w.run(DOLL)
    case("★ 物價=2 ⇒ 门槛 6000，6000 不大于 ⇒ 不用", r.ret, 0)

    w.clear(); w.land_node(11, 1, 2).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 2; w.toll = 6001
    r = w.run(DOLL)
    case("★ 物價=2、过路费 6001 ⇒ 用", r.ret, 1)

    w.clear(); w.land_node(11, 1, 1).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 1; w.toll = 999999
    r = w.run(DOLL)
    case("★ 我自己地上的路障(16) ⇒ 不用", r.ret, 0)

    w.clear(); w.land_node(11, 1, 0).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.price = 1; w.toll = 999999
    r = w.run(DOLL)
    case("★ 无主地上的路障(16) ⇒ 不用（要求 owner != 0）", r.ret, 0)

    w.clear(); w.fac_node(11, 1, 2).with_obj(11, 1, 16)
    w.path_of(11, 12, 13, 14, forked=0)
    w.toll = 0
    r = w.run(DOLL)
    case("★★ 別人**設施**上的路障(16) ⇒ 用（設施过路费按 0x989680 恒过闸）", r.ret, 1)

    # 只看路径前 4 格（缓冲里第 5 格不该被看）—— 用 path 只给 4 格验证顺序
    w.clear()
    w.land_node(12, 1, 0).with_obj(12, 1, 5)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("★ 命中在第 2 格 ⇒ 用", r.ret, 1)

    w.clear()
    w.land_node(11, 1, 0).with_obj(11, 1, 5)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("★ 命中在第 1 格 ⇒ 用", r.ret, 1)

    # 物件下标 0（node+0x24 的 bits 16-21 == 0）⇒ 视为无物件
    w.clear(); w.ghost_node(11)
    w.path_of(11, 12, 13, 14, forked=0)
    r = w.run(DOLL)
    case("  无物件位（bits 16-21 == 0）⇒ 不用", r.ret, 0)

    # ═══════════════ [E] 地雷 0x4213c5 ═══════════════
    print("\n[E] 3 地雷 `0x4213c5`：反瞻 6 格 ∩ 画面；只收别人的地/設施")
    w.clear(); w.see(11, 12, 13).path_of(11, forked=0)
    r = w.run(MINE)
    case("可见格都不在反瞻路径里 ⇒ 不用", r.ret, 0)
    case("  参数未写（哨兵）", r.param, SENTINEL)
    case("  rand 未消费", r.rand_calls, 0)

    w.clear(); w.land_node(11, 2, 2).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("★ 反瞻路径里别人的地(owner=2) ⇒ 用", r.ret, 1)
    case("  参数 = 节点 11", r.param, 11)
    case("  rand 消费 1 次（哪怕只有 1 个候选也摇）", r.rand_calls, 1)

    w.clear(); w.land_node(11, 1, 0).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("无主地 ⇒ 不候选", r.ret, 0)

    w.clear(); w.land_node(11, 1, 1).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("★ 我自己的地 ⇒ 不候选", r.ret, 0)

    w.clear(); w.fac_node(11, 1, 3).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("★ 别人的設施 ⇒ 用", r.ret, 1)

    w.clear(); w.fac_node(11, 1, 1).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("  我自己的設施 ⇒ 不候选", r.ret, 0)

    w.clear(); w.ghost_node(11).see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("★ 空格（无实体）⇒ 不候选", r.ret, 0)

    w.clear(); w.nodes[11] = (COMM_MARK + 1, 0)
    w.see(11).path_of(11, forked=0)
    r = w.run(MINE)
    case("★ 企業格（0x1770+i）⇒ 不候选", r.ret, 0)

    # 多候选：rand % 候选数
    w.clear()
    w.land_node(11, 1, 2).land_node(12, 2, 3).land_node(13, 3, 4)
    w.see(11, 12, 13).path_of(11, 12, 13, forked=0)
    w.rand = 0
    r = w.run(MINE)
    case("★ 3 个候选、rand=0 ⇒ 第 1 个（节点 11）", r.param, 11)
    w.rand = 1
    r2 = w.run(MINE)
    case("  rand=1 ⇒ 第 2 个（节点 12）", r2.param, 12)
    w.rand = 2
    r3 = w.run(MINE)
    case("  rand=2 ⇒ 第 3 个（节点 13）", r3.param, 13)
    w.rand = 5
    r4 = w.run(MINE)
    case("  rand=5 ⇒ 5%3=2 ⇒ 第 3 个", r4.param, 13)

    # 可见表顺序决定候选顺序（不是节点号大小）
    w.clear()
    w.land_node(11, 1, 2).land_node(12, 2, 3)
    w.see(12, 11).path_of(11, 12, forked=0)
    w.rand = 0
    r = w.run(MINE)
    case("★ 候选顺序照**可见表顺序**（先 12）", r.param, 12)

    # 监狱 / 医院：直选
    w.clear()
    w.land_node(11, 1, 2).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.path_of(11, 12, forked=0)
    w.prison_occ[0] = 5
    r = w.run(MINE)
    case("★ 监狱格有人在押 ⇒ 直选监狱格（节点 12），不看 rand", r.param, 12)
    case("  rand 未消费", r.rand_calls, 0)

    w.clear()
    w.land_node(11, 1, 2).see(11, 12).path_of(11, 12, forked=0)
    w.hospital_node = 12
    w.hospital_occ[3] = 5
    r = w.run(MINE)
    case("★ 医院格槽 3 有人住院 ⇒ 直选（4 字节比较覆盖槽 0..3）", r.param, 12)
    case("  rand 未消费", r.rand_calls, 0)

    # ★★★ 关键：**只有物件槽（4..7）被占用**时，原版**不**直选
    w.clear()
    w.land_node(11, 1, 2).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.prison_occ[4] = 9           # 只占物件槽
    r = w.run(MINE)
    case("★★ 仅**物件槽** 4 被占 ⇒ 原版**不**直选监狱格（cmp dword 只见槽 0..3）", r.param, 11)
    case("  于是落到普通候选（节点 11）并摇 1 次", r.rand_calls, 1)

    w.clear()
    w.land_node(11, 1, 2).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.prison_occ[7] = 9
    r = w.run(MINE)
    case("★★ 仅物件槽 7 被占 ⇒ 同样不直选", r.param, 11)

    w.clear()
    w.ghost_node(12).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.prison_occ[4] = 9
    r = w.run(MINE)
    case("★★ 仅物件槽被占 + 监狱格是空格 ⇒ 完全无候选（复刻的 8 槽口径会误直选）", r.ret, 0)
    case("  参数未写", r.param, SENTINEL)

    # 医院同一条
    w.clear()
    w.ghost_node(12).see(11, 12).path_of(11, 12, forked=0)
    w.hospital_node = 12
    w.hospital_occ[5] = 9
    r = w.run(MINE)
    case("★★ 医院格同理：仅物件槽被占 ⇒ 无候选（原版不直选）", r.ret, 0)

    # 监狱/医院节点不在反瞻路径里 ⇒ 不直选
    w.clear()
    w.land_node(11, 1, 2).see(11, 13).path_of(11, forked=0)
    w.prison_node = 13
    w.prison_occ[0] = 5
    r = w.run(MINE)
    case("  监狱格不在路径里 ⇒ 不直选（仍选节点 11）", r.param, 11)

    # ═══════════════ [F] 定時炸彈 0x421574 ═══════════════
    print("\n[F] 4 定時炸彈 `0x421574`：同一骨架，但**什么格都收**")
    w.clear(); w.ghost_node(11).see(11).path_of(11, forked=0)
    r = w.run(BOMB)
    case("★ 空格也收 ⇒ 用（与地雷相反）", r.ret, 1)
    case("  参数 = 节点 11", r.param, 11)
    case("  rand 消费 1 次", r.rand_calls, 1)

    w.clear(); w.land_node(11, 1, 1).see(11).path_of(11, forked=0)
    r = w.run(BOMB)
    case("★ 我自己的地也收 ⇒ 用", r.ret, 1)

    w.clear(); w.see(11).path_of(99, forked=0)
    r = w.run(BOMB)
    case("可见格不在路径里 ⇒ 不用", r.ret, 0)
    case("  rand 未消费", r.rand_calls, 0)

    w.clear()
    w.ghost_node(11).ghost_node(12).ghost_node(13)
    w.see(11, 12, 13).path_of(11, 12, 13, forked=0)
    w.rand = 2
    r = w.run(BOMB)
    case("★ 3 个空格候选、rand=2 ⇒ 节点 13", r.param, 13)

    w.clear()
    w.ghost_node(11).ghost_node(12).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.prison_occ[2] = 5
    r = w.run(BOMB)
    case("★ 监狱格槽 2 有人在押 ⇒ 直选", r.param, 12)
    case("  rand 未消费", r.rand_calls, 0)

    w.clear()
    w.ghost_node(11).ghost_node(12).see(11, 12).path_of(11, 12, forked=0)
    w.prison_node = 12
    w.prison_occ[4] = 9
    r = w.run(BOMB)
    case("★★ 仅物件槽被占 ⇒ **不**直选；监狱格照样作为普通空格候选", r.param, 11)
    case("  但仍进了候选并摇 1 次", r.rand_calls, 1)

    w.clear()
    w.ghost_node(12).see(11, 12).path_of(11, 12, forked=0)
    w.hospital_node = 12
    w.hospital_occ[7] = 9
    w.rand = 0
    r = w.run(BOMB)
    case("★★ 医院格仅物件槽被占 ⇒ 不直选，按可见表顺序取候选 11", r.param, 11)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
