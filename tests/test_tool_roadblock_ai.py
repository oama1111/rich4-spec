#!/usr/bin/env python3
"""
通道 2 差分测试 · **道具 2 路障的 AI 判定** `0x0042107f`（838 B，两段式）

复刻侧对应 `rich4-remake/packages/core/src/ai/tool-policy.ts` 的 `luzhang`
（该文件 `@source 0x0042107f`，约在 `tool-policy.ts:212` 的注释与 `:222` 的
`const luzhang: Handler`）。

它是「AI 出牌跳表」`0x420e9a` 的成员之一 —— **没有 `call` 调用者**，
函数图里查不到 ⇒ 用 `rich4-remake/tools/disasm.py va 0x42107f` 按需反汇编。

## 原版语义（逐地址读出来的，本测试就是钉它）

```
0x42107f():
    result = 0                                   ; [esp+8]
    if (0x40b221(cur, 4) != 0) goto phase2       ; ① 前瞻 4；岔路 ⇒ 阶段一整体跳过
    for (i = 0; i < 4; i++) {                    ; ② 只扫前 4 格（常量上界）
        if (result) goto phase2                  ;    已命中 ⇒ 停止
        node = node_table[ path[i] ]
        if (node[+0x24] & 0x3fff00) continue     ; ③ 非空 ⇒ 跳过（nodeClear 闸门）
        v = node[+0x20]                          ;    格值
        if (0x7d0 < v < 0xfa0) {                 ; ④ 住宅地（两端都严格）
            land = land_table[v - 0x7d0]
            if (land[+0x19] != 0) continue       ;    必须有主？不 —— 必须**无主**
            n = sameStreetCount(land)            ; ⑤ 从下标 1 起数到 num_lands（含）
            if (n < 2 && land[+0x1a] == 0) continue
            if (!rich(cur)) continue             ; ⑥ 現金+存款 > 10000、財運 >= 0、龜行 == 0
            if (land[+0x1c] * priceIndex >= cash) continue   ; ⑦ 只用**現金**、严格 <
            → result = 1; [0x48be64] = path[i]
        } else if (0xfa0 < v < 0x1770) {         ; ⑧ 設施（两端都严格）
            fac = fac_table[v - 0xfa0]
            if (fac[+0x19] != 0) continue
            if (!rich(cur)) continue
            if (fac[+0x22] * priceIndex >= cash) continue
            → result = 1; [0x48be64] = path[i]
        } else if ((node[+0x24] & 0xff) == 0xf) { ; ⑨ 百貨公司（specialKind 15）
            if (points(+0x30, word) > 200) {     ;    无符号、严格 >；**不查钱**
                → result = 1; [0x48be64] = path[i]
            }
        }
    }
phase2:
    if (result) return 1                         ; 阶段一已命中 ⇒ 阶段二不跑
    0x40b343(cur, 6)                             ; ⑩ 反瞻 6（返回值被忽略）
    cnt = 0x409ef9()                             ;    画面可见**节点**表项数
    best = 0
    for (i = 0; i < cnt; i++) {                  ; ⑪ **按可见表（画面行序）枚举**
        if (visible[i] ∉ backward[0..5]) continue
        node = node_table[visible[i]]
        if (!(0x7d0 < node[+0x20] < 0xfa0)) continue   ;    只收住宅地、无 nodeClear 闸门
        land = land_table[node[+0x20] - 0x7d0]
        if (land[+0x19] != cur + 1) continue     ;    必须**是我的**（1 基）
        toll = 0x419744(cur + 1, land + 4)
        if (toll <= 6000 * priceIndex) continue  ; ⑫ 严格 >
        if (toll <= best) continue               ; ⑬ 严格 >；并列保留**行序靠前**的
        best = toll; [0x48be64] = visible[i]; result = 1
    }
    return result                                ; eax = 0/1
```

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040b221` | 前瞻 | 把数据槽里的 8 个 word 拷进 `0x48b8b4`，返回 `FWD_FORKED`；另记 `(arg1,arg2)` 与调用次数 | 它自己的语义由 `tests/test_lookahead.py`（58/58）独立驱动；本测试要的是**它的参数与分岔语义** |
| `0x0040b343` | 反瞻 | 同上（写**另一组**源槽） | 同上 |
| `0x00409ef9` | 填「可见**节点**表」 | 把数据槽里的 word 拷进 `0x48b8c4`，返回项数 | 视野口径差异 = **D-005**，不是本测试对象 |
| `0x00419744` | 该地主在这条街的住宅过路费 | 返回**该地块记录 `+0x30` 的 dword**（`flast`，本函数不读） | 它自己的语义另属 `land-rent.md`；本测试要的是**阈值/比较/取最大**，需要每格独立的过路费 |

★ **两处前瞻必须各用一套「源/计数/返回」槽** —— 若共用一个源，阶段一的前瞻
会被阶段二的源顶掉（本文件里 `FWD_*` 与 `BWD_*` 是两套）。两处输出都落在同一个
缓冲 `0x48b8b4`（原版就是这样共用的），但因为**阶段一先读完才轮到阶段二**，
不会互相污染；本测试仍每格都拷满 8 个 word（不足处补 0 = 空节点），
以免「上一次调用的残留」造成不确定。

## 真值来源

被测函数的返回值、出口参数 `0x48be64` 全部是**原版机器码跑出来的**；
每条断言的期望值来自上面那份逐地址语义，**不是**复述某个实现。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_roadblock_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
ROADBLOCK = 0x42107F          # 2 路障（AI 判定，两段式，838 B）

# ── 打桩 ──
LOOK_FWD = 0x40B221
LOOK_BACK = 0x40B343
VISIBLE_NODES = 0x409EF9
STREET_TOLL = 0x419744

# ── 全局 ──
CUR = 0x49910C                 # 当前玩家（0 基）
PRICE_INDEX = 0x4990E8
NODE_TABLE_PTR = 0x498E80
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NUM_LANDS = 0x498E98           # dword：住宅地块个数（计数循环上界）
TOOL_PARAM = 0x48BE64          # AI 道具参数出口（本函数只写）
LOOK_BUF = 0x48B8B4            # 前瞻/反瞻共用输出缓冲（8 word）
VIS_LIST = 0x48B8C4            # 可见节点表（word 数组）

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_CASH = 0x1C                  # dword 0x496b84 現金
P_DEPOSIT = 0x20               # dword 0x496b88 存款
P_POINTS = 0x30                # word  0x496b98 點券
P_TORTOISE = 0x39              # byte  0x496ba1 龜行天数
P_FORTUNE = 0x46               # int16 0x496bae 神明修正 B（財運）

NODE_STRIDE = 0x28
N_ENTITY = 0x20                # word：格值（住宅 0x7d0+i / 設施 0xfa0+i / 企業 0x1770+i）
N_FLAGS = 0x24                 # dword：低字节 = specialKind，bits 8..21 = 占用

LAND_STRIDE = 0x34
L_NAME, L_OWNER, L_LEVEL, L_PRICE, L_TOLL = 0x04, 0x19, 0x1A, 0x1C, 0x30
FAC_STRIDE = 0x38
F_OWNER, F_DECOY, F_PRICE = 0x19, 0x1C, 0x22

LAND_MARK, FAC_MARK, COMM_MARK = 0x7D0, 0xFA0, 0x1770
DEPT_KIND = 0x0F               # 百貨公司 specialKind

# ── 暂存区布局（SCRATCH 不参与 reset 快照 ⇒ setup 必须自己清干净）──
NODE_MAX, LAND_MAX, FAC_MAX = 0x80, 16, 16
NODES = SCRATCH_BASE + 0x1000                       # 0x80 * 0x28 = 0x1400
LANDS = SCRATCH_BASE + 0x4000                       # 16 * 0x34
FACS = SCRATCH_BASE + 0x5000                        # 16 * 0x38
FWD_SRC = SCRATCH_BASE + 0x8000                     # 8 word
BWD_SRC = SCRATCH_BASE + 0x8020                     # 8 word
VIS_SRC = SCRATCH_BASE + 0x8040                     # 8 word

FWD_SRC_SLOT = SCRATCH_BASE + 0x800
FWD_COUNT = SCRATCH_BASE + 0x804
FWD_RET = SCRATCH_BASE + 0x808
FWD_CALLS = SCRATCH_BASE + 0x80C
FWD_ARGP = SCRATCH_BASE + 0x810
FWD_ARGN = SCRATCH_BASE + 0x814
BWD_SRC_SLOT = SCRATCH_BASE + 0x818
BWD_COUNT = SCRATCH_BASE + 0x81C
BWD_RET = SCRATCH_BASE + 0x820
BWD_CALLS = SCRATCH_BASE + 0x824
BWD_ARGP = SCRATCH_BASE + 0x828
BWD_ARGN = SCRATCH_BASE + 0x82C
VIS_SRC_SLOT = SCRATCH_BASE + 0x830
VIS_COUNT = SCRATCH_BASE + 0x834

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<74} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def _look_stub(dst, src_slot, count_slot, ret_slot, calls_slot, argp_slot, argn_slot) -> bytes:
    """前瞻/反瞻桩：记录 (arg1,arg2) 与调用次数，把 [src] 的 [count] 个 word 拷到 dst。

    ★ 必须**保留 esi/edi/ecx**（被测函数把循环状态放在 edi/esi/ebx 里）。
    ★ 8 个 word 恰好写满 `0x48b8b4..0x48b8c4`（不越界到可见表）。
    """
    return (
        b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", argp_slot)   # mov eax,[esp+4]; mov [argp],eax
        + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", argn_slot)  # mov eax,[esp+8]; mov [argn],eax
        + b"\x56\x57\x51"                                              # push esi/edi/ecx
        + b"\xFF\x05" + struct.pack("<I", calls_slot)                  # inc dword [calls]
        + b"\xA1" + struct.pack("<I", count_slot)                      # mov eax,[count]
        + b"\x89\xC1"                                                  # mov ecx,eax
        + b"\xA1" + struct.pack("<I", src_slot)                        # mov eax,[src]
        + b"\x89\xC6"                                                  # mov esi,eax
        + b"\xBF" + struct.pack("<I", dst)                             # mov edi,dst
        + b"\xF3\x66\xA5"                                              # rep movsw
        + b"\x59\x5F\x5E"                                              # pop ecx/edi/esi
        + b"\xA1" + struct.pack("<I", ret_slot)                        # mov eax,[ret]
        + b"\xC3"
    )


def _vis_stub() -> bytes:
    """可见表桩：把 [VIS_SRC_SLOT] 的 [VIS_COUNT] 个 word 拷到 0x48b8c4，返回项数。"""
    return (
        b"\x56\x57\x51"
        + b"\xA1" + struct.pack("<I", VIS_COUNT)
        + b"\x89\xC1"
        + b"\xA1" + struct.pack("<I", VIS_SRC_SLOT)
        + b"\x89\xC6"
        + b"\xBF" + struct.pack("<I", VIS_LIST)
        + b"\xF3\x66\xA5"
        + b"\x59\x5F\x5E"
        + b"\xA1" + struct.pack("<I", VIS_COUNT)
        + b"\xC3"
    )


# 过路费桩：arg2 = (land + 4) ⇒ 返回 [land + 0x30]（步长 0x34 的记录里 +0x30 是本测试的槽）
TOLL_STUB = b"\x8B\x44\x24\x08" + b"\x8B\x40\x2C" + b"\xC3"


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(LOOK_FWD, _look_stub(
            LOOK_BUF, FWD_SRC_SLOT, FWD_COUNT, FWD_RET, FWD_CALLS, FWD_ARGP, FWD_ARGN))
        self.emu.patch(LOOK_BACK, _look_stub(
            LOOK_BUF, BWD_SRC_SLOT, BWD_COUNT, BWD_RET, BWD_CALLS, BWD_ARGP, BWD_ARGN))
        self.emu.patch(VISIBLE_NODES, _vis_stub())
        self.emu.patch(STREET_TOLL, TOLL_STUB)
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.me = 0
        self.price = 1
        self.cash = [20000, 0, 0, 0]
        self.deposit = [0, 0, 0, 0]
        self.points = [0, 0, 0, 0]
        self.fortune = [0, 0, 0, 0]
        self.tortoise = [0, 0, 0, 0]
        self.extra = []            # [(va, bytes)] 额外字节注入（宽度/越界类断言用）
        self.num_lands = 1
        self.nodes = {}            # nid -> (entity, flags)
        self.lands = {}            # idx -> dict
        self.facs = {}             # idx -> dict
        self.land_base = LANDS     # 住宅表基址（边界用例改指到已映射的栈区，见 [D]）
        self.fac_base = FACS
        self.fwd = [0] * 8         # 前瞻输出（节点 id）
        self.fwd_forked = 0
        self.bwd = [0] * 8         # 反瞻输出（节点 id）
        self.vis = []              # 可见节点表（本函数按这个顺序扫）
        return self

    def node(self, nid, entity=0, flags=0):
        self.nodes[nid] = (entity & 0xFFFF, flags & 0xFFFFFFFF)
        return self

    def land(self, idx, owner=0, level=0, price=1, name=b"A", toll=0):
        self.lands[idx] = dict(owner=owner & 0xFF, level=level & 0xFF,
                               price=price & 0xFFFF, name=name, toll=toll & 0xFFFFFFFF)
        return self

    def fac(self, idx, owner=0, price=1, decoy=0):
        self.facs[idx] = dict(owner=owner & 0xFF, price=price & 0xFFFF,
                              decoy=decoy & 0xFFFF)
        return self

    def fwd_path(self, *nids, forked=0):
        ids = list(nids)[:8]
        self.fwd = ids + [0] * (8 - len(ids))
        self.fwd_forked = forked
        return self

    def bwd_path(self, *nids):
        ids = list(nids)[:8]
        self.bwd = ids + [0] * (8 - len(ids))
        return self

    def see(self, *nids):
        self.vis = list(nids)
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(PRICE_INDEX, self.price & 0x7FFFFFFF)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, self.land_base)
        emu.write32(FAC_TABLE_PTR, self.fac_base)
        emu.write32(NUM_LANDS, self.num_lands)
        emu.write32(TOOL_PARAM, SENTINEL)
        emu.write32(FWD_SRC_SLOT, FWD_SRC)
        emu.write32(FWD_COUNT, 8)
        emu.write32(FWD_RET, self.fwd_forked)
        emu.write32(FWD_CALLS, 0)
        emu.write32(FWD_ARGP, 0)
        emu.write32(FWD_ARGN, 0)
        emu.write32(BWD_SRC_SLOT, BWD_SRC)
        emu.write32(BWD_COUNT, 8)
        emu.write32(BWD_RET, 0)
        emu.write32(BWD_CALLS, 0)
        emu.write32(BWD_ARGP, 0)
        emu.write32(BWD_ARGN, 0)
        emu.write32(VIS_SRC_SLOT, VIS_SRC)
        emu.write32(VIS_COUNT, len(self.vis))
        # ★ 暂存区跨调用保留 ⇒ 整张表先清零（verification.md 工具边界第 3 条）
        emu.write(NODES, b"\x00" * (NODE_STRIDE * NODE_MAX))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * LAND_MAX))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * FAC_MAX))
        emu.write(LOOK_BUF, b"\x00" * 16)
        emu.write(VIS_LIST, b"\x00" * 16)
        emu.write(FWD_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.fwd))
        emu.write(BWD_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.bwd))
        emu.write(VIS_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in self.vis))
        for nid, (ent, flags) in self.nodes.items():
            b = NODES + nid * NODE_STRIDE
            emu.write16(b + N_ENTITY, ent)
            emu.write(b + N_FLAGS, struct.pack("<I", flags))
        for idx, l in self.lands.items():
            b = self.land_base + idx * LAND_STRIDE
            name = l["name"] if l["name"].endswith(b"\x00") else l["name"] + b"\x00"
            emu.write(b + L_NAME, name)
            emu.write8(b + L_OWNER, l["owner"])
            emu.write8(b + L_LEVEL, l["level"])
            emu.write16(b + L_PRICE, l["price"])
            emu.write(b + L_TOLL, struct.pack("<I", l["toll"]))
        for idx, f in self.facs.items():
            b = self.fac_base + idx * FAC_STRIDE
            emu.write8(b + F_OWNER, f["owner"])
            emu.write16(b + F_DECOY, f["decoy"])
            emu.write16(b + F_PRICE, f["price"])
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write(pb + P_CASH, struct.pack("<I", self.cash[p] & 0xFFFFFFFF))
            emu.write(pb + P_DEPOSIT, struct.pack("<I", self.deposit[p] & 0xFFFFFFFF))
            emu.write16(pb + P_POINTS, self.points[p] & 0xFFFF)
            emu.write8(pb + P_TORTOISE, self.tortoise[p] & 0xFF)
            emu.write16(pb + P_FORTUNE, self.fortune[p] & 0xFFFF)
        for va, data in self.extra:
            emu.write(va, data)

    def run(self, func=ROADBLOCK):
        r = self.emu.call(func, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(TOOL_PARAM)
        self.fwd_calls = self.emu.readu32(FWD_CALLS)
        self.bwd_calls = self.emu.readu32(BWD_CALLS)
        self.fwd_argp = self.emu.readu32(FWD_ARGP)
        self.fwd_argn = self.emu.readu32(FWD_ARGN)
        self.bwd_argp = self.emu.readu32(BWD_ARGP)
        self.bwd_argn = self.emu.readu32(BWD_ARGN)
        return self


# ── 场景小工具 ──
def p1_land(w, nid=10, idx=1, level=1, price=100, name=b"A", flags=0, owner=0, entity=None):
    """铺一个「阶段一、住宅地」场景：前瞻第 1 格 = nid。

    `entity` 可覆盖格值（边界用例需要 `entity` 与地块下标解耦）。
    """
    w.clear()
    w.node(nid, entity=(LAND_MARK + idx) if entity is None else entity, flags=flags)
    w.land(idx, owner=owner, level=level, price=price, name=name)
    w.fwd_path(nid, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(0, 0, 0, 0, 0, 0, 0, 0)
    return w


def p1_fac(w, nid=10, idx=1, price=100, owner=0, flags=0, decoy=0):
    """铺一个「阶段一、設施」场景。"""
    w.clear()
    w.node(nid, entity=FAC_MARK + idx, flags=flags)
    w.fac(idx, owner=owner, price=price, decoy=decoy)
    w.fwd_path(nid, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(0, 0, 0, 0, 0, 0, 0, 0)
    return w


def p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=201):
    """铺一个「阶段一、百貨公司」场景。"""
    w.clear()
    w.node(nid, entity=entity, flags=flags)
    w.points[0] = points
    w.fwd_path(nid, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(0, 0, 0, 0, 0, 0, 0, 0)
    return w


def main():
    print("差分测试 · 道具 2 路障 AI 判定 `0x0042107f`（838 B，两段式）\n")
    w = World()

    # ═══════════════ [A] 入口 / 前瞻分岔 / 循环上界 ═══════════════
    print("[A] 阶段一入口：`call 0x40b221(cur, 4)`；分岔 ⇒ 阶段一整体跳过")

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.fwd_path(10, 0, 0, 0, 0, 0, 0, 0, forked=1)
    r = w.run()
    case("★★ 前瞻分岔（forked=1）⇒ 阶段一整体跳过（第 1 格本是有效候选）", r.ret, 0)
    case("   出口参数未写（哨兵）", r.param, SENTINEL)
    case("★ 反瞻仍被调用 ⇒ 确实落了阶段二", r.bwd_calls, 1)
    case("   前瞻恰调用 1 次", r.fwd_calls, 1)
    case("★★ 前瞻参数 = (当前玩家 0, 4)", (r.fwd_argp, r.fwd_argn), (0, 4))
    case("★★ 反瞻参数 = (当前玩家 0, 6)", (r.bwd_argp, r.bwd_argn), (0, 6))

    p1_land(w, nid=10, idx=1, level=1, price=100)
    r = w.run()
    case("   分岔=0 且第 1 格有效 ⇒ 阶段一命中", r.ret, 1)
    case("   出口参数 = 节点 10", r.param, 10)
    case("★ 命中后阶段二不跑（反瞻 0 次）", r.bwd_calls, 0)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.fwd_path(0, 0, 0, 0, 10, 0, 0, 0, forked=0)
    r = w.run()
    case("★★ 前瞻只扫常量 4 格：候选在第 5 格 ⇒ 不选", r.ret, 0)
    case("   出口参数未写", r.param, SENTINEL)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.fwd_path(0, 0, 0, 10, 0, 0, 0, 0, forked=0)
    r = w.run()
    case("   候选在第 4 格（下标 3）⇒ 选", r.param, 10)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.node(11, entity=LAND_MARK + 2, flags=0)
    w.land(2, owner=0, level=1, price=100)
    w.fwd_path(10, 11, 0, 0, 0, 0, 0, 0, forked=0)
    r = w.run()
    case("★ 前 4 格里先到者胜（10 在 11 前）⇒ 取 10", r.param, 10)

    p1_land(w, nid=10, idx=1, level=1, price=100, flags=0x100)
    w.node(11, entity=LAND_MARK + 2, flags=0)
    w.land(2, owner=0, level=1, price=100)
    w.fwd_path(10, 11, 0, 0, 0, 0, 0, 0, forked=0)
    r = w.run()
    case("★ 第 1 格被 nodeClear 拦掉 ⇒ 继续看第 2 格（节点 11）", r.param, 11)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.me = 1
    w.cash = [0, 20000, 0, 0]
    r = w.run()
    case("★★ 当前玩家取自 [0x49910c]：me=1 ⇒ 前瞻参数 (1,4)", (r.fwd_argp, r.fwd_argn), (1, 4))
    case("   me=1 时读 1 号玩家的钱 ⇒ 仍命中", r.ret, 1)

    # ═══════════════ [B] sameStreetCount：从下标 1 起 / 跳过 0 号 / 上界含 num_lands ═══
    print("\n[B] sameStreetCount：`mov edi,1` / `add esi,0x34`（跳 0 号）/ `jg num_lands`（含上界）")

    p1_land(w, nid=10, idx=1, level=0, price=100)
    w.num_lands = 1
    r = w.run()
    case("★ level=0 且同街我的地 0 块 ⇒ 不选（计数门槛）", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=0, price=100)
    w.land(2, owner=1, level=0, name=b"A").land(3, owner=1, level=0, name=b"A")
    w.num_lands = 3
    r = w.run()
    case("★ 同街我的地 2 块（2/3 号）⇒ 即使 level=0 也选", r.ret, 1)
    case("   出口参数 = 节点 10", r.param, 10)

    p1_land(w, nid=10, idx=1, level=0, price=100)
    w.land(0, owner=1, level=0, name=b"A").land(2, owner=1, level=0, name=b"A")
    w.num_lands = 2
    r = w.run()
    case("★★ 0 号地不参与计数：只有 0/2 号同街 ⇒ 计 1 块 ⇒ 不选", r.ret, 0)
    w.land(3, owner=1, level=0, name=b"A")
    w.num_lands = 3
    r = w.run()
    case("   同两点改放 2/3 号（且 num_lands=3）⇒ 计 2 块 ⇒ 选（上界含 3）", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=0, price=100)
    w.land(2, owner=1, level=0, name=b"A").land(3, owner=1, level=0, name=b"A")
    w.num_lands = 3
    r = w.run()
    case("★★ 计数上界**含** num_lands：j=1,2,3 ⇒ 2/3 号计入 ⇒ 2 块 ⇒ 选", r.ret, 1)
    w.num_lands = 2
    r = w.run()
    case("   同一局把 num_lands 收到 2（j=3 不再扫）⇒ 计 1 块 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=3, level=0, price=100)
    w.land(1, owner=1, level=0, name=b"A").land(2, owner=1, level=0, name=b"A")
    w.num_lands = 3
    r = w.run()
    case("★★ 计数**从下标 1 起**：1/2 号同街 ⇒ 2 块 ⇒ 选（若从 2 起只会算 1）", r.ret, 1)
    w.num_lands = 1
    r = w.run()
    case("   同一局 num_lands=1（j=1 扫到）⇒ 1 块 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.num_lands = 1
    r = w.run()
    case("★ level≠0 ⇒ 不看同街计数（0 块照样选）", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=0, price=100, name=b"A")
    w.land(2, owner=1, level=0, name=b"B")
    w.num_lands = 2
    r = w.run()
    case("   同 owner 但街道名不同（strcmp≠0）⇒ 不计 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=0, price=100, name=b"A")
    w.land(2, owner=2, level=0, name=b"A")
    w.num_lands = 2
    r = w.run()
    case("   同街道但 owner 不是我（me+1=1）⇒ 不计 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=0, price=100, name=b"A")
    w.me = 1
    w.cash = [0, 20000, 0, 0]
    w.land(2, owner=2, level=0, name=b"A")
    w.num_lands = 2
    r = w.run()
    case("★★ owner 用 cur+1：me=1 时 owner=2 算我的 ⇒ 计 1 块 ⇒ 不选", r.ret, 0)
    w.land(3, owner=2, level=0, name=b"A")
    w.num_lands = 3
    r = w.run()
    case("   再加一块 ⇒ 计 2 块 ⇒ 选", r.ret, 1)

    # ═══════════════ [C] nodeClear 闸门 `dword[node+0x24] & 0x3fff00` ═══════════════
    print("\n[C] nodeClear 闸门：`test dword [node+0x24], 0x3fff00` ⇒ 非 0 跳过")
    for flags, want, note in [
        (0x000100, 0, "bit 8"),
        (0x000800, 0, "bit 11"),
        (0x001000, 0, "bit 12"),
        (0x008000, 0, "bit 15"),
        (0x010000, 0, "bit 16"),
        (0x200000, 0, "bit 21"),
        (0x400000, 1, "bit 22（掩码外）"),
        (0xC00000, 1, "bit 22+23（掩码外）"),
        (0x0000FF, 1, "低 8 位 = specialKind（掩码外）"),
        (0x3FFF00, 0, "整个掩码"),
    ]:
        p1_land(w, nid=10, idx=1, level=1, price=100, flags=flags)
        r = w.run()
        case(f"★ flags=0x{flags:08x}（{note}）⇒ {'选' if want else '跳过'}", r.ret, want)

    # ═══════════════ [D] 格值区间两端都严格 + owner 必须无主 ═══════════════
    print("\n[D] 格值区间：`0x7d0 < v < 0xfa0`（住宅）/ `0xfa0 < v < 0x1770`（設施），两端严格")

    p1_land(w, nid=10, idx=1, level=1, price=100)
    r = w.run()
    case("   v = 0x7d1（住宅下界+1）⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=0x7CF, level=1, price=100)   # entity 0xf9f ⇒ 地块 0x7cf 号
    w.land_base = 0x500000     # 0x7cf 号记录落在已映射的栈区（LANDS 暂存区放不下 2000 项）
    r = w.run()
    case("   v = 0xf9f（住宅上界−1）⇒ 仍是住宅 ⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=0, level=1, price=100)
    w.node(10, entity=LAND_MARK, flags=0)
    r = w.run()
    case("★★ v = 0x7d0（恰在下界）⇒ **不是**住宅（否则会读 0 号地并命中）⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=0, level=1, price=100)
    w.node(10, entity=FAC_MARK, flags=0)
    r = w.run()
    case("★★ v = 0xfa0（恰在住宅上界）⇒ 不是住宅也不是設施 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=0, level=1, price=100)
    w.node(10, entity=COMM_MARK, flags=0)
    r = w.run()
    case("★★ v = 0x1770（恰在設施上界）⇒ 不是設施（否则会读 0 号設施并命中）⇒ 不选", r.ret, 0)

    p1_fac(w, nid=10, idx=0x7CF, price=100)             # entity 0x176f ⇒ 設施 0x7cf 号
    w.fac_base = 0x500000
    r = w.run()
    case("   v = 0x176f（設施上界−1）⇒ 仍是設施 ⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=1, price=100, owner=1)
    r = w.run()
    case("★ 住宅是我的（owner=me+1=1）⇒ 阶段一不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=100, owner=2)
    r = w.run()
    case("★ 住宅是别人的（owner=2）⇒ 阶段一不选", r.ret, 0)

    # ═══════════════ [E] rich 闸门（現金+存款 > 10000）与「价格只比現金」 ═══
    print("\n[E] 钱闸门：`現金(+0x1c)+存款(+0x20) > 0x2710`；但地价比的是**只有現金**")

    p1_land(w, nid=10, idx=1, level=1, price=1)
    w.cash = [10000] + [0] * 3
    r = w.run()
    case("★★ 現金+存款 = 10000 ⇒ 不 > 10000 ⇒ 不选（严格）", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=1)
    w.cash = [10001] + [0] * 3
    r = w.run()
    case("   現金+存款 = 10001 ⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=1, price=1)
    w.cash = [6000] + [0] * 3
    w.deposit = [6000] + [0] * 3
    r = w.run()
    case("★ 錢闸门把現金与存款**相加**（6000+6000=12000）⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=1, price=1)
    w.cash = [0] + [0] * 3
    w.deposit = [20000] + [0] * 3
    r = w.run()
    case("★★ 錢闸门过（存款 20000）但地价比的是**現金=0** ⇒ 1 >= 0 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=10000)
    w.cash = [10000] + [0] * 3
    w.deposit = [1] + [0] * 3
    r = w.run()
    case("★★ 地价×物價 == 現金 ⇒ 不选（`jge` = 严格 <）", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=9999)
    w.cash = [10000] + [0] * 3
    w.deposit = [1] + [0] * 3
    r = w.run()
    case("   地价×物價 == 現金−1 ⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=1, price=5000)
    w.price = 2
    w.cash = [10000] + [0] * 3
    w.deposit = [1] + [0] * 3
    r = w.run()
    case("★ 物價=2：5000×2 == 10000 ⇒ 不选", r.ret, 0)

    p1_land(w, nid=10, idx=1, level=1, price=4999)
    w.price = 2
    w.cash = [10000] + [0] * 3
    w.deposit = [1] + [0] * 3
    r = w.run()
    case("   物價=2：4999×2 = 9998 < 10000 ⇒ 选", r.ret, 1)

    p1_land(w, nid=10, idx=1, level=1, price=0xFFFF)
    w.price = 0x10000
    w.cash = [10001] + [0] * 3
    r = w.run()
    case("★★ 32 位有符号 `imul`：0xffff×0x10000 溢出为负 ⇒ 反而 < 現金 ⇒ 选", r.ret, 1)

    # ═══════════════ [F] 財運 / 龜行 ═══════════════
    print("\n[F] rich 的另两项：`cmp word [p+0x46],0 / jl`（有符号）与 `cmp byte [p+0x39],0 / jne`")

    for fortune, want, note in [
        (0, 1, "0"),
        (1, 1, "+1"),
        (0x7FFF, 1, "0x7fff"),
        (0xFFFF, 0, "0xffff = −1（有符号）"),
        (0x8000, 0, "0x8000 = −32768"),
    ]:
        p1_land(w, nid=10, idx=1, level=1, price=100)
        w.fortune[0] = fortune
        r = w.run()
        case(f"★ 財運(+0x46) = {note} ⇒ {'选' if want else '不选'}", r.ret, want)

    for tortoise, want, note in [
        (0, 1, "0"),
        (1, 0, "1"),
        (2, 0, "2"),
        (3, 0, "3"),
        (0x80, 0, "0x80（高位标记）"),
        (0xFF, 0, "0xff"),
    ]:
        p1_land(w, nid=10, idx=1, level=1, price=100)
        w.tortoise[0] = tortoise
        r = w.run()
        case(f"★ 龜行(+0x39) = {note} ⇒ {'选' if want else '不选'}", r.ret, want)

    p1_land(w, nid=10, idx=1, level=1, price=100)
    w.extra.append((PLAYER_BASE + P_TORTOISE + 1, b"\x01"))   # +0x3a = 1
    r = w.run()
    case("★★ `cmp byte`：龜行字节为 0，紧邻的 +0x3a=1 不算 ⇒ 选（非 word/dword 读）", r.ret, 1)

    # ═══════════════ [G] 設施分支 ═══════════════
    print("\n[G] 設施分支：`fac[+0x19] == 0` 且同样的钱闸，地价取 `fac+0x22`")

    p1_fac(w, nid=10, idx=1, price=100)
    r = w.run()
    case("★ 无主設施、100×1 < 20000 ⇒ 选", r.ret, 1)
    case("   出口参数 = 节点 10", r.param, 10)

    p1_fac(w, nid=10, idx=1, price=20000)
    r = w.run()
    case("★ 設施地价×物價 == 現金 ⇒ 不选（严格）", r.ret, 0)

    p1_fac(w, nid=10, idx=1, price=19999)
    r = w.run()
    case("   設施地价×物價 == 現金−1 ⇒ 选", r.ret, 1)

    p1_fac(w, nid=10, idx=15, price=100)
    r = w.run()
    case("★ 最高一格設施（idx 15，步长 0x38）⇒ 选", r.ret, 1)

    p1_fac(w, nid=10, idx=3, price=100, owner=1)
    r = w.run()
    case("★ 設施是我的 ⇒ 不选", r.ret, 0)

    p1_fac(w, nid=10, idx=3, price=100, owner=2)
    r = w.run()
    case("★ 設施是别人的 ⇒ 不选（阶段一只收无主）", r.ret, 0)

    p1_fac(w, nid=10, idx=1, price=100)
    w.cash = [10000] + [0] * 3
    r = w.run()
    case("★ 設施也走同一个钱闸：現金+存款 = 10000 ⇒ 不选", r.ret, 0)

    p1_fac(w, nid=10, idx=1, price=100)
    w.cash = [0] + [0] * 3
    w.deposit = [20000] + [0] * 3
    r = w.run()
    case("★★ 設施地价比的也是**只有現金**=0 ⇒ 100 >= 0 ⇒ 不选", r.ret, 0)

    p1_fac(w, nid=10, idx=1, price=1, decoy=40000)
    r = w.run()
    case("★★ 設施地价在 **+0x22**：+0x22=1（便宜）/+0x1c=40000 ⇒ 选", r.ret, 1)

    p1_fac(w, nid=10, idx=1, price=40000, decoy=1)
    r = w.run()
    case("★★ 同上反过来（+0x22=40000 / +0x1c=1）⇒ 不选（证明读的是 +0x22）", r.ret, 0)

    p1_fac(w, nid=10, idx=1, price=100)
    w.node(10, entity=FAC_MARK - 1, flags=0)   # 0xf9f：住宅上界
    w.land(0x7CF, owner=0, level=1, price=100)
    w.land_base = 0x500000
    r = w.run()
    case("   v = 0xf9f 仍走住宅支（不是設施）⇒ 选", r.ret, 1)

    # ═══════════════ [H] 百貨公司（specialKind 15）与點券 > 200 ═══════════════
    print("\n[H] 百貨公司格：`(node[+0x24] & 0xff) == 0xf` 且 `word [p+0x30] > 0xc8`（无符号）")

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=201)
    w.cash = [0] * 4
    w.deposit = [0] * 4
    w.fortune[0] = -1
    w.tortoise[0] = 1
    r = w.run()
    case("★★ 百貨公司：點券=201 ⇒ 选，且**完全不查钱/財運/龜行**", r.ret, 1)
    case("   出口参数 = 节点 10", r.param, 10)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=200)
    r = w.run()
    case("★★ 點券 = 200 ⇒ 不选（`jbe` = 严格 >）", r.ret, 0)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=0xFFFF)
    r = w.run()
    case("★★ 點券 = 0xffff（无符号 65535，有符号 −1）⇒ 选（无符号比较）", r.ret, 1)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=0x8000)
    r = w.run()
    case("★★ 點券 = 0x8000（有符号为负）⇒ 选（无符号比较）", r.ret, 1)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=0x0E, points=999)
    r = w.run()
    case("★ flags 低字节 = 0x0e ⇒ 不是百貨公司 ⇒ 不选", r.ret, 0)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=0x1F, points=999)
    r = w.run()
    case("★ flags 低字节 = 0x1f ⇒ 不等于 0xf（不是「含 0xf」）⇒ 不选", r.ret, 0)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=0x10F, points=999)
    r = w.run()
    case("★ flags = 0x10f（低字节对但 bit8 占用）⇒ nodeClear 先拦 ⇒ 不选", r.ret, 0)

    p1_dept(w, nid=10, entity=0, flags=DEPT_KIND, points=201)
    r = w.run()
    case("★ 空格（v=0）+ 低字节 0xf ⇒ 也走百貨公司支 ⇒ 选", r.ret, 1)

    p1_dept(w, nid=10, entity=LAND_MARK, flags=DEPT_KIND, points=201)
    r = w.run()
    case("★★ v = 0x7d0（恰在下界）+ 低字节 0xf ⇒ 不是住宅 ⇒ 落百貨公司支 ⇒ 选", r.ret, 1)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=0)
    w.extra.append((PLAYER_BASE + P_POINTS + 2, struct.pack("<H", 1)))   # +0x32 = 1
    r = w.run()
    case("★★ 點券是 16 位：+0x30=0 而 +0x32=1 ⇒ 不选（若读 dword 会选）", r.ret, 0)

    p1_dept(w, nid=10, entity=COMM_MARK, flags=DEPT_KIND, points=0x100)
    w.extra.append((PLAYER_BASE + P_POINTS + 2, struct.pack("<H", 0xFFFF)))
    r = w.run()
    case("★★ 點券低 16 位 = 0x0100 > 200 ⇒ 选（高 16 位的 0xffff 不参与）", r.ret, 1)

    # ═══════════════ [I] 阶段二：反瞻 6 ∩ 可见表，按可见表（画面行序）枚举 ═══════════════
    print("\n[I] 阶段二：反瞻 6 ∩ 可见表；我的住宅地、过路费 > 6000×物價，取最大（严格 >）")

    def mine(idx, toll):
        return dict(owner=1, level=1, price=100, name=b"A", toll=toll)

    def scene(vis, bwd, lands, price=1, flags=None):
        w.clear()
        w.price = price
        w.fwd_path(0, 0, 0, 0, 0, 0, 0, 0, forked=0)
        w.bwd_path(*bwd)
        w.see(*vis)
        for nid, (idx, kw) in lands.items():
            w.node(nid, entity=LAND_MARK + idx, flags=(flags or {}).get(nid, 0))
            w.land(idx, **kw)
        return w.run()

    r = scene([], [0] * 8, {})
    case("   可见表空 ⇒ 阶段二不选（返回 0、参数未写）", (r.ret, r.param), (0, SENTINEL))
    case("   反瞻仍被调用（阶段二入口无条件调）", r.bwd_calls, 1)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 6001))})
    case("★ 可见∩反瞻 = {10}，我的地、过路费 6001 > 6000×1 ⇒ 选", (r.ret, r.param), (1, 10))

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 6000))})
    case("★★ 过路费 == 6000×1 ⇒ 不选（`jle` = 严格 >）", (r.ret, r.param), (0, SENTINEL))

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 17999))}, price=3)
    case("★ 物價=3 ⇒ 门槛 18000：17999 不选", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 18000))}, price=3)
    case("★★ 物價=3、过路费 == 18000 ⇒ 不选（门槛 = 6000×物價）", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 18001))}, price=3)
    case("   物價=3、过路费 18001 ⇒ 选", r.ret, 1)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 12001))}, price=2)
    case("   物價=2、过路费 12001 ⇒ 选", r.ret, 1)

    r = scene([10], [11, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 9999)), 11: (2, mine(2, 9999))})
    case("★ 可见有 10 但反瞻只有 11 ⇒ 不选（必须**相交**）", r.ret, 0)

    r = scene([10], [0, 0, 0, 0, 0, 10, 0, 0], {10: (1, mine(1, 9999))})
    case("★ 反瞻第 6 格（下标 5）命中 ⇒ 选", (r.ret, r.param), (1, 10))

    r = scene([10], [0, 0, 0, 0, 0, 0, 10, 0], {10: (1, mine(1, 9999))})
    case("★★ 反瞻只扫前 6 格：命中在下标 6 ⇒ 不选", r.ret, 0)

    r = scene([10, 11], [10, 11, 0, 0, 0, 0, 0, 0],
              {10: (1, mine(1, 7000)), 11: (2, mine(2, 8000))})
    case("★★ 两个候选：7000 与 8000 ⇒ 取过路费**最大**的（节点 11）", r.param, 11)

    r = scene([10, 11], [10, 11, 0, 0, 0, 0, 0, 0],
              {10: (1, mine(1, 7000)), 11: (2, mine(2, 7000))})
    case("★★ 并列（都 7000）⇒ 保留**先枚举**的（节点 10，`jle` 严格 >）", r.param, 10)

    r = scene([11, 10], [10, 11, 0, 0, 0, 0, 0, 0],
              {10: (1, mine(1, 7000)), 11: (2, mine(2, 7000))})
    case("★★ 枚举顺序 = **可见表顺序**（不是节点号/反瞻序）：并列时取可见表里靠前的 11", r.param, 11)

    r = scene([10, 11], [10, 11, 0, 0, 0, 0, 0, 0],
              {10: (1, mine(1, 9000)), 11: (2, mine(2, 8000))})
    case("   递减：9000 在前 ⇒ 保持节点 10（后面的 8000 不大于 best）", r.param, 10)

    r = scene([10, 11], [10, 11, 0, 0, 0, 0, 0, 0],
              {10: (1, mine(1, 7000)), 11: (2, mine(2, 5000))})
    case("   次候选低于门槛（5000）⇒ 仍取节点 10", r.param, 10)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, dict(owner=2, level=1, price=100, name=b"A", toll=9999))})
    case("★★ 别人的地（owner=2）⇒ 不选（阶段二只收 cur+1）", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, dict(owner=0, level=1, price=100, name=b"A", toll=9999))})
    case("★ 无主地（owner=0）⇒ 不选", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, dict(owner=3, level=1, price=100, name=b"A", toll=9999))})
    case("★ 第三家的地（owner=3）⇒ 不选", r.ret, 0)

    w.clear()
    w.fwd_path(0, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(10, 0, 0, 0, 0, 0, 0, 0)
    w.see(10)
    w.node(10, entity=FAC_MARK + 1, flags=0)
    w.fac(1, owner=1, price=100)
    r = w.run()
    case("★★ 設施（阶段二只收住宅地）⇒ 不选", r.ret, 0)

    w.clear()
    w.fwd_path(0, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(10, 0, 0, 0, 0, 0, 0, 0)
    w.see(10)
    w.node(10, entity=LAND_MARK, flags=0)
    w.land(0, owner=1, level=1, price=100, name=b"A", toll=9999)
    r = w.run()
    case("★★ 阶段二格值区间同样严格：v = 0x7d0 ⇒ 不选", r.ret, 0)

    w.clear()
    w.fwd_path(0, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(10, 0, 0, 0, 0, 0, 0, 0)
    w.see(10)
    w.node(10, entity=LAND_MARK + 1, flags=0x3FFF00)
    w.land(1, owner=1, level=1, price=100, name=b"A", toll=9999)
    r = w.run()
    case("★★ 阶段二**没有** nodeClear 闸门：flags=0x3fff00 也照样选", (r.ret, r.param), (1, 10))

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 1))}, price=0)
    case("★ 物價=0 ⇒ 门槛 0：过路费 1 > 0 ⇒ 选", (r.ret, r.param), (1, 10))

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 0))}, price=0)
    case("★★ best 初值 0 且门槛 0：过路费 0 既不 > 门槛 也不 > best ⇒ 不选", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, -1))}, price=0)
    case("★ 过路费为负（有符号比较）⇒ 不选", r.ret, 0)

    r = scene([10], [10, 0, 0, 0, 0, 0, 0, 0], {10: (1, mine(1, 6001))}, price=1, flags={10: 0x100})
    case("   阶段二不看占用掩码（对照阶段一）⇒ 仍选", r.ret, 1)

    # 阶段一命中 + 可见表里也有更好的一格 ⇒ 阶段二必须不跑（返回阶段一那格）
    w.clear()
    w.node(10, entity=LAND_MARK + 1, flags=0)
    w.land(1, owner=0, level=1, price=100, name=b"A")
    w.node(20, entity=LAND_MARK + 2, flags=0)
    w.land(2, owner=1, level=1, price=100, name=b"A", toll=99999)
    w.fwd_path(10, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(20, 0, 0, 0, 0, 0, 0, 0)
    w.see(20)
    r = w.run()
    case("★★ 阶段一命中 ⇒ 不落阶段二（哪怕阶段二有更「肥」的一格）", (r.ret, r.param), (1, 10))
    case("   反瞻 0 次（旁证）", r.bwd_calls, 0)

    # me=1 的阶段二（owner 匹配与参数都用当前玩家）
    w.clear()
    w.me = 1
    w.cash = [0, 20000, 0, 0]
    w.price = 1
    w.fwd_path(0, 0, 0, 0, 0, 0, 0, 0, forked=0)
    w.bwd_path(10, 0, 0, 0, 0, 0, 0, 0)
    w.see(10)
    w.node(10, entity=LAND_MARK + 1, flags=0)
    w.land(1, owner=2, level=1, price=100, name=b"A", toll=6001)
    r = w.run()
    case("★★ me=1 时 owner=2 才是我的 ⇒ 选", (r.ret, r.param), (1, 10))
    case("   反瞻参数 = (1, 6)", (r.bwd_argp, r.bwd_argn), (1, 6))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
