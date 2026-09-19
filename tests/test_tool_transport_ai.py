#!/usr/bin/env python3
"""
通道 2 差分测试 · **道具 11 傳送機 的 AI 判定**（VA `0x00421CB6`，362 字节）

被测函数**没有 `call` 调用者**（它是 AI 出牌跳表 `0x475324` 的成员，建图工具不收），
故用 `rich4-remake/tools/disasm.py va 0x421cb6` 按需反汇编。复刻侧对应
`packages/core/src/ai/tool-policy.ts` 的 `chuansong`（`@source 0x00421cb6`）。

## 语义（全文 130 条指令读完）

```
0x421cb6():
    ret = 0 ; [esp] = 0
    n = 0x409ef9()                     ; 画面内**节点 id** 表 → 0x48b8c4，返回项数
    best = 0 ; [esp+4] = n
    for (i = 0; i < n; i++) {
        v = word [0x48b8c4 + i*2]      ; ★ 节点 id（不是格值）
        ent = word [ node_table[v] + 0x20 ]      ; node_table = [0x498e80]，步长 0x28
        if (0x7d0 < ent < 0xfa0) {               ; ── 地块
            L = [0x498e84] + (ent-0x7d0)*0x34
            if (L+0x19 != 0) continue            ; owner 必须 0
            if (L+0x18 != 0) continue            ; 必须住宅（type == 0）
            if (L+0x1a <  3) continue            ; 等级 ≥ 3
            lv = byte [L+0x1a]
            if (best >= lv) continue             ; ★ 严格 >（并列取行序靠前）
            if (word[L+0x1e] * [0x4990e8] >= cash) continue   ; ★ 房价×物价 **严格 <** 現金
            best = lv ; [0x48be64] = v
        } else if (0xfa0 < ent < 0x1770) {       ; ── 設施（企業 ≥0x1770 不收）
            F = [0x498e88] + (ent-0xfa0)*0x38
            if (F+0x19 != 0) continue
            if (F+0x18 == 0) continue            ; 公園（type 0）除外
            if (F+0x1a <  3) continue
            if (word[F+0x24] * [0x4990e8] >= cash) continue
            lv = byte [F+0x1a]
            if (best >= lv) continue
            best = lv ; [0x48be64] = v
        }
        continue: i++
    }
    if (best == 0) return 0
    if (cash + 存款 <= 10000) return 0        ; ★ 钱闸在**找到候选之后**
    if (signed word [cur+0x46] < 0) return 0  ; ★ 財運闸（有符号 16 位）
    return 1
```

一句话：**画面里无主、等级 ≥ 3 的住宅/設施（非公園）中，房价×物价 < 現金的最贵者**；
找到后还要 **現金+存款 > 10000** 且 **財運 ≥ 0**；输出参数 `[0x48be64]` = **节点 id**。

本函数**不调用 `rand()`**（全程 0 次）—— 这一点用计数器桩显式钉住。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x00409ef9` | 填「可見**节点**表」`0x48b8c4`，返回项数 | 从数据槽拷 `[VIS_COPY]` 个 word 进去，返回 `[VIS_RET]` | 视野/镜头口径差异 = **D-005**，不是本测试对象；它自己的语义已另属 `0x409ef9`（本测试的反汇编已确认它写的就是节点 id：先把 `node_table[i]` 的 id 写进 440×440 格表，再收集非 0 项）。两个 count 分开，是为了**直接探测循环上界用的是返回值** |
| `0x00456f2d` | CRT `rand()` | 数据槽 + **自增计数槽** | 本函数**不该摇**，计数器让「没摇」成为可证伪断言 |

被测函数**只调用了 `0x409ef9` 一个外部函数**（其余全是对属性/表的直接读），
故桩清单只有以上两条；`node_table`/`land_table`/`facility_table` 指针、
`[0x49910c]`（当前玩家）、`[0x4990e8]`（物價指數）与玩家结构全由 `setup()` 直接铺。

★ 本函数**不读**「人数上界类」全局（`0x40d2d3`/`0x441262` 那类遍历器一概不调），
所以 `verification.md` 工具边界第 5 条那个坑不适用；但每组仍配了「确实走了目标分支」
的旁证断言（两组同构输入交换后结论必须相反）。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_transport_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
TARGET = 0x421CB6          # 11 傳送機 的 AI 判定

# ── 打桩 ──
VISIBLE_NODES = 0x409EF9   # 填「可見节点表」
PRNG = 0x456F2D            # CRT rand()

# ── 全局 ──
CUR = 0x49910C             # 当前玩家（0 基）
NUMP = 0x499114            # 玩家数（本函数不读，铺上以防口径漂移）
PRICE_INDEX = 0x4990E8     # 物價指數
NODE_TABLE_PTR = 0x498E80
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
TOOL_PARAM = 0x48BE64      # AI 道具参数出口（本函数唯一的写出侧）
VIS_LIST = 0x48B8C4        # 可見节点表（word 数组）

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_CASH, P_BANK, P_FORTUNE = 0x1C, 0x20, 0x46

NODE_STRIDE, N_ENTITY = 0x28, 0x20
LAND_STRIDE, L_OWNER, L_TYPE, L_LEVEL, L_PRICE = 0x34, 0x19, 0x18, 0x1A, 0x1E
FAC_STRIDE, F_OWNER, F_TYPE, F_LEVEL, F_PRICE = 0x38, 0x19, 0x18, 0x1A, 0x24

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0

NODE_SLOTS, LAND_SLOTS, FAC_SLOTS = 64, 16, 16

# ── 暂存区布局（★ 跨 call() 保留 ⇒ setup 必须先清表）──
NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x2000
FACS = SCRATCH_BASE + 0x3000
VIS_SRC = SCRATCH_BASE + 0x4000
VIS_SRC_SLOT = SCRATCH_BASE + 0x800
VIS_COPY = SCRATCH_BASE + 0x804
VIS_RET = SCRATCH_BASE + 0x808
RAND_SLOT = SCRATCH_BASE + 0x80C
RAND_CALLS = SCRATCH_BASE + 0x810

SENTINEL = 0x5A5A5A5A
RESULTS = []
RAND_TOTAL = [0]


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<72} 实际 {got!s:<12} 期望 {want!s}")
    return ok


def _copy_stub(dst: int, src_slot: int, copy_slot: int, ret_slot: int) -> bytes:
    """把 [src_slot] 起的 [copy_slot] 个 word 拷到 dst，返回 [ret_slot]。

    两个 count 分开：`copy` 决定表里铺几项，`ret` 决定原版看到的「项数」。
    正常用例两者相等；专门的探针用例让 copy > ret，用来钉住
    「循环上界 = 返回值 `[esp+4]`」而不是「表里铺了多少项」。
    必须保留 esi/edi/ecx（与 test_tool_policy_ai.py 同一约定）。
    """
    return (
        b"\x56\x57\x51"                                     # push esi / edi / ecx
        + b"\xA1" + struct.pack("<I", copy_slot)            # mov eax,[copy]
        + b"\x89\xC1"                                       # mov ecx,eax
        + b"\xA1" + struct.pack("<I", src_slot)             # mov eax,[src]
        + b"\x89\xC6"                                       # mov esi,eax
        + b"\xBF" + struct.pack("<I", dst)                  # mov edi,dst
        + b"\xF3\x66\xA5"                                   # rep movsw
        + b"\x59\x5F\x5E"                                   # pop ecx / edi / esi
        + b"\xA1" + struct.pack("<I", ret_slot)             # mov eax,[ret]
        + b"\xC3"
    )


class World:
    def __init__(self):
        self.emu = Emu()
        # rand()：读数据槽 + 自增调用计数（本函数不该摇）
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.emu.patch(VISIBLE_NODES,
                       _copy_stub(VIS_LIST, VIS_SRC_SLOT, VIS_COPY, VIS_RET))
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.cur = 0
        self.nplayers = 4
        self.price = 1
        self.cash = [1_000_000] * 4
        self.bank = [0] * 4
        self.fortune = [0] * 4
        self.visible = []          # 可見节点表内容（节点 id）
        self.vis_tail = []         # 铺进表里但**不计入项数**的尾巴（循环上界探针）
        self.nodes = {}            # nid → 格值（node+0x20）
        self.lands = {}            # idx → 记录 dict
        self.facs = {}             # idx → 记录 dict
        self.rand = 0
        return self

    def node(self, nid, entity=0):
        self.nodes[nid] = entity
        return self

    def land(self, nid, idx, owner=0, ltype=0, level=3, price=0, e8=None, e16=None):
        """铺一条地块记录：node[nid].entity = 0x7d0+idx，记录在 LANDS + idx*0x34。

        e8/e16 = 在任意偏移上补写的字节/word（偏移探针用；具名字段后写、优先级高）。
        """
        self.nodes[nid] = LAND_MARK + idx
        self.lands[idx] = dict(owner=owner, type=ltype, level=level, price=price,
                               e8=e8 or {}, e16=e16 or {})
        return self

    def fac(self, nid, idx, owner=0, ftype=1, level=3, price=0, e8=None, e16=None):
        """铺一条設施记录：node[nid].entity = 0xfa0+idx，记录在 FACS + idx*0x38。"""
        self.nodes[nid] = FAC_MARK + idx
        self.facs[idx] = dict(owner=owner, type=ftype, level=level, price=price,
                              e8=e8 or {}, e16=e16 or {})
        return self

    def see(self, *nids, tail=()):
        self.visible = list(nids)
        self.vis_tail = list(tail)
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.cur)
        emu.write32(NUMP, self.nplayers)
        emu.write32(PRICE_INDEX, self.price)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(TOOL_PARAM, SENTINEL)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write32(VIS_SRC_SLOT, VIS_SRC)
        emu.write32(VIS_COPY, len(self.visible) + len(self.vis_tail))
        emu.write32(VIS_RET, len(self.visible))
        # ★ 暂存区跨调用保留 ⇒ 先清表
        emu.write(NODES, b"\x00" * (NODE_STRIDE * NODE_SLOTS))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * LAND_SLOTS))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * FAC_SLOTS))
        emu.write(VIS_LIST, b"\x00" * 128)
        words = self.visible + self.vis_tail
        emu.write(VIS_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in words))
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write32(pb + P_CASH, self.cash[p])
            emu.write32(pb + P_BANK, self.bank[p])
            emu.write16(pb + P_FORTUNE, self.fortune[p] & 0xFFFF)
        for nid, ent in self.nodes.items():
            emu.write16(NODES + nid * NODE_STRIDE + N_ENTITY, ent & 0xFFFF)
        for table, base, stride, owner, typ, level, price in (
            (self.lands, LANDS, LAND_STRIDE, L_OWNER, L_TYPE, L_LEVEL, L_PRICE),
            (self.facs, FACS, FAC_STRIDE, F_OWNER, F_TYPE, F_LEVEL, F_PRICE),
        ):
            for idx, rec in table.items():
                b = base + idx * stride
                for off, val in rec["e16"].items():
                    emu.write16(b + off, val)
                for off, val in rec["e8"].items():
                    emu.write8(b + off, val)
                emu.write8(b + owner, rec["owner"])
                emu.write8(b + typ, rec["type"])
                emu.write8(b + level, rec["level"])
                emu.write16(b + price, rec["price"])

    def run(self):
        r = self.emu.call(TARGET, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(TOOL_PARAM)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        RAND_TOTAL[0] += self.rand_calls
        return self


def main():
    print("差分测试 · 道具 11 傳送機 AI 判定 `0x00421CB6`（通道 2）\n")
    w = World()
    GOOD = 1_000_000                 # 默认：过得了钱闸的現金

    # ═══════════════ [A] 循环边界 / 区间开闭 / 循环上界 ═══════════════
    print("[A] 可見表循环、0x7d0/0xfa0/0x1770 三个区间的开闭")
    w.clear(); w.see()
    r = w.run()
    case("A1 可見表为空（项数 0）⇒ 返回 0", r.ret, 0)
    case("A1b 参数未写（哨兵）", r.param, SENTINEL)
    case("A1c rand 未消费", r.rand_calls, 0)

    w.clear(); w.node(7, 0).see(7)
    r = w.run()
    case("A2 节点格值为 0（空格）⇒ 返回 0", r.ret, 0)
    case("A2b 参数未写", r.param, SENTINEL)

    # ★ 地块 0 号（ent 恰为 0x7d0）：记录本身**完全合格**，仍不可选 ⇒ 下界是开区间
    w.clear(); w.land(7, 0, owner=0, ltype=0, level=5, price=0).see(7)
    r = w.run()
    case("★A3 格值恰为 0x7d0（地块 0 号，记录合格）⇒ 不选（严格 >）", r.ret, 0)
    case("A3b 参数未写", r.param, SENTINEL)

    w.clear(); w.node(7, LAND_MARK - 1).see(7)
    r = w.run()
    case("A4 格值 0x7cf（< 0x7d0）⇒ 不选", r.ret, 0)

    # ★ 設施 0 号（ent 恰为 0xfa0）：地块支的上界开 + 設施支的下界开 ⇒ 两头落空
    w.clear(); w.fac(7, 0, owner=0, ftype=1, level=5, price=0).see(7)
    r = w.run()
    case("★A5 格值恰为 0xfa0（設施 0 号，记录合格）⇒ 不选（两区间都开）", r.ret, 0)
    case("A5b 参数未写", r.param, SENTINEL)

    w.clear(); w.fac(7, 8, owner=0, ftype=1, level=5, price=0)
    w.nodes[7] = 0x1770                      # 企業上界：记录照样铺了（idx 8 合格）
    w.see(7)
    r = w.run()
    case("★A6 格值恰为 0x1770（企業）⇒ 不选（設施支上界开）", r.ret, 0)
    case("A6b 参数未写", r.param, SENTINEL)

    w.clear(); w.node(7, 0x1771).see(7)
    r = w.run()
    case("A7 格值 0x1771（> 0x1770）⇒ 不选", r.ret, 0)

    # ★★ 循环上界 = 返回值 `[esp+4]`（不是表里铺了几项）
    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=3, price=0)
    w.land(8, 2, owner=0, ltype=0, level=5, price=0)
    w.see(7, tail=(8,))                      # 铺 2 项，回报 1 项
    r = w.run()
    case("★★A8 表里铺 2 项但返回项数 1 ⇒ 只看第 1 项（节点 7）", r.param, 7)
    case("A8b 于是最优等级取第 1 项的 3 ⇒ 返回 1", r.ret, 1)

    # ═══════════════ [B] 地块支（0x7d0 < ent < 0xfa0）═══════════════
    print("\n[B] 地块支：owner==0 ∧ type==0（住宅）∧ level≥3 ∧ 房价×物价 < 現金")
    w.clear(); w.land(7, 1, owner=1, level=3, price=0).see(7)
    r = w.run()
    case("B1 owner=1 ⇒ 不选", r.ret, 0)
    case("B1b 参数未写", r.param, SENTINEL)

    w.clear(); w.land(7, 1, owner=2, level=3, price=0).see(7)
    r = w.run()
    case("B2 owner=2 ⇒ 不选", r.ret, 0)

    w.clear(); w.land(7, 1, owner=0, ltype=1, level=3, price=0).see(7)
    r = w.run()
    case("B3 owner=0 但 type=1（商業用地）⇒ 不选", r.ret, 0)

    w.clear(); w.land(7, 1, owner=0, ltype=0, level=2, price=0).see(7)
    r = w.run()
    case("B4 level=2 ⇒ 不选（门槛 3）", r.ret, 0)

    w.clear(); w.land(7, 1, owner=0, ltype=0, level=3, price=100).see(7)
    r = w.run()
    case("★B5 owner=0/住宅/level=3/价100 ⇒ 选中（返回 1）", r.ret, 1)
    case("B5b 参数 = 节点 id 7（不是格值 2001）", r.param, 7)

    w.clear(); w.land(7, 1, owner=0, ltype=0, level=5, price=100).see(7)
    r = w.run()
    case("B6 level=5 ⇒ 选中", r.ret, 1)

    # ⚠️ 房价字段是 **16 位**（u16，见 B11/B17），故边界用例的現金取 50000
    w.clear(); w.cash[0] = 50_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=49_999).see(7)
    r = w.run()
    case("★B7 房价×物价 = 現金−1（49999 < 50000）⇒ 选中", r.ret, 1)

    w.clear(); w.cash[0] = 50_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=50_000).see(7)
    r = w.run()
    case("★B8 房价×物价 == 現金 ⇒ 不选（严格 <）", r.ret, 0)
    case("B8b 参数未写", r.param, SENTINEL)

    w.clear(); w.cash[0] = 50_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=50_001).see(7)
    r = w.run()
    case("B9 房价×物价 > 現金 ⇒ 不选", r.ret, 0)

    # 物價指數参与乘法（[0x4990e8]）
    w.clear(); w.cash[0] = 100_000; w.price = 2
    w.land(7, 1, owner=0, ltype=0, level=3, price=50_000).see(7)
    r = w.run()
    case("★B10 物價=2、房价 50000 ⇒ 100000 == 現金 ⇒ 不选", r.ret, 0)

    w.clear(); w.cash[0] = 100_000; w.price = 2
    w.land(7, 1, owner=0, ltype=0, level=3, price=49_999).see(7)
    r = w.run()
    case("★B10b 物價=2、房价 49999 ⇒ 99998 < 現金 ⇒ 选中", r.ret, 1)

    # 房价字段是 **16 位无符号**（`and eax,0xffff`）—— 用现金恰好等于 65535 分辨
    w.clear(); w.cash[0] = 65_535
    w.land(7, 1, owner=0, ltype=0, level=3, price=65_535).see(7)
    r = w.run()
    case("★B11 房价 0xffff 当 65535（非 −1）⇒ 65535 ≥ 現金 65535 ⇒ 不选", r.ret, 0)

    # 等级严格 >：并列取行序靠前、更高等级后来居上
    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=3, price=0)
    w.land(8, 2, owner=0, ltype=0, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★B12 两块同级地（3,3）⇒ 取行序靠前的节点 7", r.param, 7)

    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=3, price=0)
    w.land(8, 2, owner=0, ltype=0, level=4, price=0)
    w.see(7, 8)
    r = w.run()
    case("★B13 等级 3 后跟 4 ⇒ 后来居上取节点 8（严格 >）", r.param, 8)

    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=4, price=0)
    w.land(8, 2, owner=0, ltype=0, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★B13b 等级 4 后跟 3 ⇒ 保住节点 7", r.param, 7)

    # 等级更高但买不起 ⇒ 不阻断后面便宜的低等级候选
    w.clear(); w.price = 100
    w.land(7, 1, owner=0, ltype=0, level=5, price=65_535)   # 65535×100 = 6553500 ≥ 1e6
    w.land(8, 2, owner=0, ltype=0, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★B14 高等级但买不起 ⇒ 跳过，落到节点 8（best 仍是 3）", r.param, 8)
    case("B14b 高等级被跳过、低等级接住 ⇒ 返回 1", r.ret, 1)

    # 偏移探针：等级读的是 +0x1a
    w.clear(); w.land(7, 1, owner=0, ltype=0, level=2, e8={0x1B: 3}).see(7)
    r = w.run()
    case("★B15 等级写在 +0x1b（错位）⇒ 不选（证明读的是 +0x1a）", r.ret, 0)
    w.clear(); w.land(7, 1, owner=0, ltype=0, level=3, e8={0x1B: 2}).see(7)
    r = w.run()
    case("★B15b 等级写在 +0x1a=3、+0x1b 放垃圾 ⇒ 照选（同上，反向）", r.ret, 1)

    # 偏移探针：房价读的是 +0x1e（不是 +0x1c）
    w.clear(); w.land(7, 1, owner=0, ltype=0, level=3, price=1, e16={0x1C: 60_000}).see(7)
    r = w.run()
    case("★B16 大值放 +0x1c、房价 +0x1e=1 ⇒ 选中（证明读 +0x1e）", r.ret, 1)
    w.clear(); w.cash[0] = 50_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=60_000, e16={0x1C: 1}).see(7)
    r = w.run()
    case("★B16b 大值放 +0x1e、小值放 +0x1c ⇒ 不选（反向）", r.ret, 0)

    # ★ 宽度探针：房价只读**低 16 位**（`mov ax, word [+0x1e]`，高半的字不参与）
    w.clear(); w.cash[0] = 20_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=16_960, e16={0x20: 0xFFFF}).see(7)
    r = w.run()
    case("★B17 +0x1e 是 16960、紧邻的 +0x20 放 0xffff ⇒ 仍选中（只读 word）", r.ret, 1)

    # ═══════════════ [C] 設施支（0xfa0 < ent < 0x1770）═══════════════
    print("\n[C] 設施支：owner==0 ∧ type!=0（非公園）∧ level≥3 ∧ 房价×物价 < 現金")
    w.clear(); w.fac(7, 1, owner=1, ftype=1, level=3, price=0).see(7)
    r = w.run()
    case("C1 owner=1 ⇒ 不选", r.ret, 0)
    case("C1b 参数未写", r.param, SENTINEL)

    w.clear(); w.fac(7, 1, owner=0, ftype=0, level=5, price=0).see(7)
    r = w.run()
    case("★C2 owner=0 但 type=0（公園）⇒ 不选", r.ret, 0)

    w.clear(); w.fac(7, 1, owner=0, ftype=1, level=2, price=0).see(7)
    r = w.run()
    case("C3 level=2 ⇒ 不选（门槛 3）", r.ret, 0)

    w.clear(); w.fac(7, 1, owner=0, ftype=1, level=3, price=100).see(7)
    r = w.run()
    case("★C4 owner=0/非公園/level=3/价100 ⇒ 选中", r.ret, 1)
    case("C4b 参数 = 节点 id 7（不是格值 4001）", r.param, 7)

    for t in (2, 3, 4):
        w.clear(); w.fac(7, 1, owner=0, ftype=t, level=3, price=0).see(7)
        r = w.run()
        case(f"C5 type={t}（非公園）⇒ 选中", r.ret, 1)

    w.clear(); w.cash[0] = 50_000
    w.fac(7, 1, owner=0, ftype=1, level=3, price=50_000).see(7)
    r = w.run()
    case("★C6 房价×物价 == 現金 ⇒ 不选（严格 <）", r.ret, 0)
    w.clear(); w.cash[0] = 50_000
    w.fac(7, 1, owner=0, ftype=1, level=3, price=49_999).see(7)
    r = w.run()
    case("★C6b 房价×物价 == 現金−1 ⇒ 选中", r.ret, 1)

    w.clear(); w.cash[0] = 65_535
    w.fac(7, 1, owner=0, ftype=1, level=3, price=65_535).see(7)
    r = w.run()
    case("★C7 設施房价 0xffff 当 65535（非 −1）⇒ 不选", r.ret, 0)

    w.clear()
    w.fac(7, 1, owner=0, ftype=1, level=3, price=1, e16={0x1E: 60_000})
    w.see(7)
    r = w.run()
    case("★C8 設施房价读 +0x24：+0x1e 放大值、+0x24=1 ⇒ 选中", r.ret, 1)
    w.clear(); w.cash[0] = 50_000
    w.fac(7, 1, owner=0, ftype=1, level=3, price=60_000, e16={0x1E: 1})
    w.see(7)
    r = w.run()
    case("★C8b +0x24 放大值、+0x1e 放小值 ⇒ 不选（反向）", r.ret, 0)

    # ★ 宽度探针：設施房价同样只读低 16 位（`mov si, word [+0x24]`）
    w.clear(); w.cash[0] = 20_000
    w.fac(7, 1, owner=0, ftype=1, level=3, price=16_960, e16={0x26: 0xFFFF})
    w.see(7)
    r = w.run()
    case("★C8c +0x24 是 16960、紧邻的 +0x26 放 0xffff ⇒ 仍选中（只读 word）", r.ret, 1)

    w.clear()
    w.fac(7, 1, owner=0, ftype=1, level=2, e8={0x1B: 3})
    w.see(7)
    r = w.run()
    case("★C9 設施等级写在 +0x1b（错位）⇒ 不选（读的是 +0x1a）", r.ret, 0)
    w.clear()
    w.fac(7, 1, owner=0, ftype=1, level=3, e8={0x1B: 2})
    w.see(7)
    r = w.run()
    case("★C9b 等級 +0x1a=3、+0x1b 放垃圾 ⇒ 照选", r.ret, 1)

    # ═══════════════ [D] 两支混合：按等级严格比较，不行则看行序 ═══════════════
    print("\n[D] 两支混合：同一循环里地块/設施互相比等级（严格 >，并列看行序）")
    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=3, price=0)
    w.fac(8, 1, owner=0, ftype=1, level=4, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D1 地块3 → 設施4 ⇒ 取設施（节点 8）", r.param, 8)

    w.clear()
    w.fac(7, 1, owner=0, ftype=1, level=3, price=0)
    w.land(8, 2, owner=0, ltype=0, level=4, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D2 設施3 → 地块4 ⇒ 取地块（节点 8）", r.param, 8)

    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=5, price=0)
    w.fac(8, 1, owner=0, ftype=1, level=5, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D3 地块5 → 設施5 并列 ⇒ 取先到的地块（节点 7）", r.param, 7)

    w.clear()
    w.fac(7, 1, owner=0, ftype=1, level=5, price=0)
    w.land(8, 2, owner=0, ltype=0, level=5, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D4 設施5 → 地块5 并列 ⇒ 取先到的設施（节点 7）", r.param, 7)

    w.clear(); w.price = 100
    w.fac(7, 1, owner=0, ftype=1, level=5, price=65_535)    # 65535×100 ≥ 1e6
    w.land(8, 2, owner=0, ltype=0, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D5 設施5 买不起 ⇒ 落到地块3（节点 8）；高等级不阻断", r.param, 8)
    case("D5b 返回 1", r.ret, 1)

    w.clear(); w.price = 100
    w.land(7, 1, owner=0, ltype=0, level=5, price=65_535)
    w.fac(8, 1, owner=0, ftype=1, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D6 地块5 买不起 ⇒ 落到設施3（节点 8）", r.param, 8)

    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=3, price=0)
    w.fac(8, 1, owner=0, ftype=1, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★D7 地块3 → 設施3 并列 ⇒ 取先到的地块（节点 7）", r.param, 7)

    # ═══════════════ [E] 输出参数 [0x48be64] ═══════════════
    print("\n[E] 输出参数 [0x48be64]：写的是**节点 id**，且写完才过钱闸")
    w.clear(); w.land(50, 1, owner=0, ltype=0, level=3, price=0).see(50)
    r = w.run()
    case("★E1 节点 id 50 / 格值 2001 ⇒ 参数 = 50", r.param, 50)

    w.clear(); w.node(9, 0).see(9)
    r = w.run()
    case("E2 无候选 ⇒ 参数保持哨兵", r.param, SENTINEL)

    # ★ 关键：钱闸不过时**参数照样已写**（写参数在循环里，钱闸在循环后）
    w.clear(); w.cash[0] = 10_000
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("★★E3 钱闸不过 ⇒ 返回 0", r.ret, 0)
    case("★★E3b 但参数**已经写下**（节点 7）—— 顺序证据", r.param, 7)

    w.clear(); w.fortune[0] = -1
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("★★E4 財運闸不过 ⇒ 返回 0", r.ret, 0)
    case("★★E4b 参数照样已写（节点 7）", r.param, 7)

    w.clear()
    w.land(7, 1, owner=0, ltype=0, level=4, price=0)
    w.land(8, 2, owner=0, ltype=0, level=3, price=0)
    w.see(7, 8)
    r = w.run()
    case("★E5 后到的低等级候选**不覆盖**参数（仍是 7）", r.param, 7)

    # ═══════════════ [F] 收尾两道闸：現金+存款 > 10000、財運 ≥ 0 ═══════════════
    print("\n[F] 收尾两道闸：現金+存款 **严格 > 10000**、財運 **≥ 0**（有符号 16 位）")

    def f_land(**kw):
        w.clear()
        for k, v in kw.items():
            if k == "cash":
                w.cash[0] = v
            elif k == "bank":
                w.bank[0] = v
            elif k == "fortune":
                w.fortune[0] = v
            elif k == "cur":
                w.cur = v
            else:
                raise KeyError(k)
        w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
        return w.run()

    r = f_land(cash=10_000)
    case("F1 現金+存款 == 10000 ⇒ 返回 0", r.ret, 0)
    case("F1b 参数仍写下", r.param, 7)
    r = f_land(cash=10_001)
    case("★F2 現金+存款 == 10001 ⇒ 返回 1（门槛严格 >）", r.ret, 1)
    r = f_land(cash=0)
    case("F3 現金 0 ⇒ 返回 0", r.ret, 0)
    r = f_land(cash=20_000, bank=-10_000)
    case("★F4 現金 20000 + 存款 −10000 == 10000 ⇒ 返回 0（看的是**和**）", r.ret, 0)
    r = f_land(cash=20_000, bank=-9_999)
    case("★F4b 和 == 10001 ⇒ 返回 1", r.ret, 1)
    r = f_land(cash=5_000, bank=5_001)
    case("★F5 現金 5000 + 存款 5001 ⇒ 返回 1（单看現金会误判）", r.ret, 1)
    r = f_land(cash=10_001, fortune=0)
    case("F6 財運 == 0 ⇒ 返回 1（不是「必须 > 0」）", r.ret, 1)
    r = f_land(cash=10_001, fortune=-1)
    case("★F7 財運 −1 ⇒ 返回 0", r.ret, 0)
    r = f_land(cash=10_001, fortune=1)
    case("F8 財運 1 ⇒ 返回 1", r.ret, 1)
    r = f_land(cash=10_001, fortune=32_767)
    case("F9 財運 0x7fff ⇒ 返回 1", r.ret, 1)
    r = f_land(cash=10_001, fortune=-32_768)
    case("★F10 財運 0x8000（有符号 −32768）⇒ 返回 0（jl 是有符号比较）", r.ret, 0)

    w.clear(); w.see()
    r = w.run()
    case("F11 无候选 + 現金充足 + 財運 0 ⇒ 仍返回 0（钱闸造不出候选）", r.ret, 0)
    case("F11b 参数未写", r.param, SENTINEL)

    # 收尾读的是**当前玩家**
    w.clear()
    w.cur = 2
    w.cash = [10_001, 10_001, 10_001, 10_001]
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("★F12 cur=2、四家現金都 10001 ⇒ 返回 1（读的是当前玩家）", r.ret, 1)
    w.cash[2] = 10_000
    r = w.run()
    case("★F12b cur=2 的現金降到 10000 ⇒ 返回 0", r.ret, 0)
    w.cash = [1_000_000, 1_000_000, 10_000, 1_000_000]
    r = w.run()
    case("★F12c 只有 cur=2 是 10000 ⇒ 仍 0（不串到 0 号玩家）", r.ret, 0)
    w.cash[2] = 10_001
    r = w.run()
    case("★F12d cur=2 回到 10001 ⇒ 1", r.ret, 1)

    w.clear()
    w.cur = 3
    w.cash = [0, 0, 0, 20_000]
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("★★F13 cur=3：候选的現金闸也读 3 号玩家（其他人 0）⇒ 选中", r.ret, 1)
    w.cash[3] = 10_000
    r = w.run()
    case("★F13b 3 号玩家 10000 ⇒ 0（同一个 ebx 基址两处共用）", r.ret, 0)

    # ═══════════════ [G] 物價指數来源 & 32 位乘法边界 ═══════════════
    print("\n[G] 物價指數 [0x4990e8] 参与乘法；`imul` 是 32 位截断")
    w.clear(); w.cash[0] = 100_000; w.price = 1
    w.land(7, 1, owner=0, ltype=0, level=3, price=99_999).see(7)
    r = w.run()
    case("G1 物價=1、价 99999 < 100000 ⇒ 选中", r.ret, 1)
    w.clear(); w.cash[0] = 100_000; w.price = 2
    w.land(7, 1, owner=0, ltype=0, level=3, price=50_000).see(7)
    r = w.run()
    case("G2 物價=2、价 50000 ⇒ 100000 ≥ 100000 ⇒ 不选", r.ret, 0)
    w.clear(); w.cash[0] = 100_000; w.price = 0
    w.land(7, 1, owner=0, ltype=0, level=3, price=65_535).see(7)
    r = w.run()
    case("G3 物價=0 ⇒ 乘积 0 < 現金 ⇒ 选中", r.ret, 1)

    # ★ 32 位截断：0xffff × 0x10000 = 0xFFFF0000 = 有符号 −65536 ⇒ 「买得起」
    w.clear(); w.cash[0] = 1_000_000; w.price = 65_536
    w.land(7, 1, owner=0, ltype=0, level=3, price=65_535).see(7)
    r = w.run()
    case("★G4 0xffff×0x10000 截断成负数 ⇒ 原版认为买得起（返回 1）", r.ret, 1)
    w.clear(); w.cash[0] = 1_000_000; w.price = 65_537
    w.land(7, 1, owner=0, ltype=0, level=3, price=65_535).see(7)
    r = w.run()
    case("★G4b 0xffff×0x10001 截断成 0xFFFF0001（仍为负）⇒ 返回 1", r.ret, 1)

    # ═══════════════ [H] rand() 消费次数（全程 0）═══════════════
    print("\n[H] 本函数**不调用 rand()**：任何分支都不消费随机数")
    w.clear(); w.see()
    r = w.run()
    case("H1 空表", r.rand_calls, 0)
    w.clear(); w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("H2 命中地块（返回 1）", r.rand_calls, 0)
    w.clear(); w.fac(7, 1, owner=0, ftype=1, level=3, price=0).see(7)
    r = w.run()
    case("H3 命中設施（返回 1）", r.rand_calls, 0)
    w.clear(); w.cash[0] = 5
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("H4 钱闸挡掉（返回 0）", r.rand_calls, 0)
    w.clear(); w.fortune[0] = -5
    w.land(7, 1, owner=0, ltype=0, level=3, price=0).see(7)
    r = w.run()
    case("H5 財運闸挡掉（返回 0）", r.rand_calls, 0)
    case("★H6 **全程累计** rand 消费次数", RAND_TOTAL[0], 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
