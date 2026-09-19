#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通道 2 差分测试 · **道具 8「遙控骰子」的 AI 判定** `0x00421827`（895 B）

复刻侧：`rich4-remake/packages/core/src/ai/tool-policy.ts` 的 `yaokong`
（`@source 0x00421827`）。本函数**没有 `call` 调用者** —— 它是 AI 出牌跳表
`0x47539c` 的成员（见 `tool-policy.ts` 文件头），函数建图工具不收，
故用 `rich4-remake/tools/disasm.py va 0x00421827` 按需反汇编。

## 语义（逐条从机器码读出）

闸门（任一不过 ⇒ 立刻返回 0，**前瞻一次都不调**）：

| # | 判据 | @source |
|---|---|---|
| 1 | `godInfo(+0x3f) ∈ {7,8,15}` ⇒ 0 | `0x42183f`–`0x421852` |
| 2 | `days_tortoise_walking(+0x39) != 0` ⇒ 0 | `0x42185b` |
| 3 | `cash(+0x1c) + moneyInBank(+0x20) < 10000`（**32 位有符号**）⇒ 0 | `0x421864`–`0x421875` |
| 4 | `fortune(+0x46)`（**word、有符号**）`< 0` ⇒ 0 | `0x421877` |
| 5 | `lookahead(cur, 6)` 报「有岔路」⇒ 0 | `0x421881`–`0x42188e` |

循环 `i = 0..5`（`0x421894` 起、`0x4219df` 的 `cmp ebx,6 / jge` 收）；
出口参数 `[0x48be64]` 写的是 **`i+1`**（`0x4219c8`）⇒ 步数是 **1 基**。

逐格（`0x4219f3`–`0x421a35`）：
* a. `(node+0x24) & 0xf000`（bits 12-15 = 玩家占用）非 0 ⇒ **跳过本格**（`0x421a12`–`0x421a20`）
* b. `(node+0x24) & 0x3f0000 >> 16`（bits 16-21 = 物件下标+1）非 0 ⇒ 查物件表
  `0x496d08 + (idx-1)*0x18` 的 `+0` 类型；**{5,6,7,8,10,11,16,17,18}** ⇒ 跳过本格
  （`0x4218a0`–`0x421907`）
* 其余类型 ⇒ 继续；bits 8-11 / bit31 **不参与**判据

格值 `word[node+0x20]`（`0x421922`）分派：

* `2000 < v < 4000` ⇒ 地块 `idx = v-2000`、步长 `0x34`（`0x421942`–`0x421951`）
  * **无主**（`+0x19 == 0`）：同街（**同名**、且 `owner == cur+1`）的我的地数 `≥ 2`
    **且** `cash > 2.5 × landPrice(+0x1c)` ⇒ **立即定**（`0x421997`–`0x4219ce`）
  * **我的**：`type(+0x18) == 0` ∧ `level(+0x1a) < 5` ∧ 同街 `≥ 2` ∧
    `cash > 2.5 × housePrice(+0x1e)` ∧ `level > bestLevel` ⇒ **只记下、不立即定**
    （`0x421a3a`–`0x421adb`，**不置 found 标志**）
* `4000 < v < 6000` ⇒ 設施 `idx = v-4000`、步长 `0x38`（`0x421ae0`–`0x421b0b`）
  * **无主**：`cash > 2.5 × [+0x22]` ⇒ **立即定**（`0x421b13`–`0x421b39`，
    判据是 `jb`，**与下面两支用的是不同的比较点**）
  * **我的**：`type != 0`（公園）∧ `type != 3`（加油站）∧ `level < 5` ∧
    `cash > 2.5 × [+0x24]` ⇒ **立即定**（`0x421b3f`–`0x421b83`，跳到共用尾 `0x4219af`）
* 其余（`v ≤ 2000`、`v ≥ 6000`＝企業）⇒ 不处理

扫完（`0x421b88`–`0x421b9d`）：`bestLevel != 0` ⇒ 返回 1（参数已在 `[0x48be64]`）；
否则返回 0（`[0x48be64]` **不被写**，保持哨兵）。

★★ **比较是浮点**：`fild cash` / `fild price` / `fmul qword [0x463d48]`（= double **2.5**，
本测试实测 `f64(0x463d48) == 2.5`）/ `fcompp` + `jae`（`0x4219a3`–`0x4219c2`）
⇒ 判据是 **`cash > 2.5 × price`**；`cash == 2.5 × price` 时 `jae` 成立 ⇒ **不合格**。
整数等价写法 = `2 × cash > 5 × price`（**严格大于**，两侧同构）。

★ 本函数**自己一次 `rand()` 都不掷**：全函数只有两处 `call` —— `0x40b221`（前瞻）
与 `0x458370`（strcmp）。本测试对**每一个**用例都断言 `rand` 计数 == 0。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040b221` | 前瞻 6 格：把路径节点写进 `0x48b8b4`，返回「有没有岔路」 | 从数据槽拷 `[count]` 个 word 进 `0x48b8b4`、返回 `[ret]`；**另记录两个实参与调用次数** | 它的语义已由 `tests/test_lookahead.py`（58/58）独立驱动；本测试还要用它断言「闸门短路时前瞻**没被调**」以及「实参 = (当前玩家, 6)」 |
| `0x00456f2d` | CRT `rand()` | 从数据槽读 + 自增计数槽 | 本函数不用随机数 ⇒ 用计数**证明**「一次都没掷」 |
| `0x00458370` | `strcmp`（同街判据） | **不打桩、真跑** | 它是本函数唯一的外部依赖，emulator 能跑（`emulate.py selftest` 已自检） |

`0x49910c`（当前玩家）、`0x498e80/84/88`（节点/地块/設施表**指针**）、
`0x498e98`（地块数）、`0x496d08`（物件表，**绝对地址**）、`0x48be64`（参数出口）
由 `setup()` 直接铺；`0x463d48`（= 2.5）**不动**，读出来复核。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_dice_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测函数 ──
DICE = 0x421827                # 8 遙控骰子（895 B：0x421827..0x421ba5）

# ── 打桩 ──
LOOK_FWD = 0x40B221            # 前瞻（本测试打桩；真身语义见 test_lookahead.py）
PRNG = 0x456F2D                # CRT rand（本函数不掷，只作计数）

# ── 全局 ──
CUR = 0x49910C                 # 当前玩家（0 基）
NODE_TABLE_PTR = 0x498E80
LAND_TABLE_PTR = 0x498E84
FAC_TABLE_PTR = 0x498E88
NUM_LANDS = 0x498E98           # 同街扫描的上界（含）
OBJ_TABLE = 0x496D08           # 地图物件表**绝对地址**：+0 类型，步长 0x18
TOOL_PARAM = 0x48BE64          # AI 道具参数出口（本函数写「步数 1..6」）
LOOK_BUF = 0x48B8B4            # 前瞻输出缓冲（8 word）
DICE_CONST = 0x463D48          # double 2.5

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_CASH, P_BANK, P_TORTOISE, P_GOD, P_FORTUNE = 0x1C, 0x20, 0x39, 0x3F, 0x46

NODE_STRIDE, N_ENTITY, N_FLAGS = 0x28, 0x20, 0x24
LAND_STRIDE, FAC_STRIDE = 0x34, 0x38
L_NAME, L_TYPE, L_OWNER, L_LEVEL, L_LPRICE, L_HPRICE = 0x04, 0x18, 0x19, 0x1A, 0x1C, 0x1E
F_NAME, F_TYPE, F_OWNER, F_LEVEL, F_LPRICE, F_HPRICE = 0x04, 0x18, 0x19, 0x1A, 0x22, 0x24
OBJ_STRIDE, O_TYPE = 0x18, 0x00

LAND_MARK, FAC_MARK, COMM_MARK = 0x7D0, 0xFA0, 0x1770
BAD_OBJ = (5, 6, 7, 8, 10, 11, 16, 17, 18)   # @source 0x4218b6..0x421901

NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000
PATH_SRC = SCRATCH_BASE + 0x8000

LOOK_SRC, LOOK_COUNT, LOOK_RET = (SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x900,
                                  SCRATCH_BASE + 0x904)
LOOK_CALLS, LOOK_ARG1, LOOK_ARG2 = (SCRATCH_BASE + 0x908, SCRATCH_BASE + 0x90C,
                                    SCRATCH_BASE + 0x910)
RAND_SLOT, RAND_CALLS = SCRATCH_BASE + 0x914, SCRATCH_BASE + 0x918

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<12} 期望 {want!s}")
    return ok


def _lookahead_stub() -> bytes:
    """前瞻桩：记录实参 → 把 [count] 个 word 从 [src] 拷到 0x48b8b4 → 返回 [ret]。

    必须保留 ebx/esi/edi/ecx/edx（`rep movsw` 用 esi/edi/ecx）。
    """
    return (
        b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", LOOK_ARG1)   # mov eax,[esp+4]
        + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", LOOK_ARG2)  # mov eax,[esp+8]
        + b"\x53\x56\x57\x51\x52"                                      # push ebx/esi/edi/ecx/edx
        + b"\xA1" + struct.pack("<I", LOOK_COUNT) + b"\x89\xC1"        # mov eax,[count];ecx=eax
        + b"\xA1" + struct.pack("<I", LOOK_SRC) + b"\x89\xC6"          # mov eax,[src];esi=eax
        + b"\xBF" + struct.pack("<I", LOOK_BUF)                        # mov edi,0x48b8b4
        + b"\xF3\x66\xA5"                                              # rep movsw
        + b"\x5A\x59\x5F\x5E\x5B"                                      # pop edx/ecx/edi/esi/ebx
        + b"\xFF\x05" + struct.pack("<I", LOOK_CALLS)                  # inc dword [calls]
        + b"\xA1" + struct.pack("<I", LOOK_RET)                        # mov eax,[ret]
        + b"\xC3"
    )


class World:
    def __init__(self):
        self.emu = Emu()
        assert self.emu.f64(DICE_CONST) == 2.5, "0x463d48 必须是 double 2.5"
        self.const25 = self.emu.f64(DICE_CONST)
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.emu.patch(LOOK_FWD, _lookahead_stub())
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.me = 0
        self.cash = 10000
        self.bank = 0
        self.tortoise = 0
        self.god = 0
        self.fortune = 0
        self.path = []             # 前瞻输出（节点 id），最多 6
        self.forked = 0
        self.num_lands = 8
        self.nodes = {}            # nid → (entity, flags dword)
        self.lands = {}            # idx → (owner, type, level, price, house, name)
        self.facs = {}             # idx → (owner, type, level, price22, house24, name)
        self.objs = {}             # 1 基下标 → 类型
        self.rand = 0
        return self

    # 节点
    def node(self, nid, ent=0, players=0, obj_idx=0, extra=0):
        flags = ((players & 0xF) << 12) | ((obj_idx & 0x3F) << 16) | extra
        self.nodes[nid] = (ent & 0xFFFF, flags & 0xFFFFFFFF)
        return self

    def land_node(self, nid, idx):
        return self.node(nid, LAND_MARK + idx)

    def fac_node(self, nid, idx):
        return self.node(nid, FAC_MARK + idx)

    def comm_node(self, nid, idx):
        return self.node(nid, COMM_MARK + idx)

    def ghost_node(self, nid):
        return self.node(nid, 0)

    def on_node(self, nid, *players):
        """格上有玩家（bits 12-15 的对应位）"""
        ent, flags = self.nodes.get(nid, (0, 0))
        m = flags & 0xF000
        for p in players:
            m |= 1 << (12 + p)
        self.nodes[nid] = (ent, (flags & ~0xF000) | m)
        return self

    def with_obj(self, nid, obj_idx, otype):
        """给节点挂物件（obj_idx 1 基，写进 node+0x24 的 bits 16-21）"""
        ent, flags = self.nodes.get(nid, (0, 0))
        self.nodes[nid] = (ent, (flags & 0xFC0FFFFF) | ((obj_idx & 0x3F) << 16))
        self.objs[obj_idx] = otype
        return self

    # 表项
    def land(self, idx, owner=0, ltype=0, level=0, price=100, house=200, name="A"):
        self.lands[idx] = (owner, ltype, level, price, house, name)
        return self

    def fac(self, idx, owner=0, ftype=1, level=0, price=100, house=200, name="F"):
        self.facs[idx] = (owner, ftype, level, price, house, name)
        return self

    def path_of(self, *nids, forked=0):
        self.path = list(nids)
        self.forked = forked
        return self

    def my_street(self, name="A", n=2, owner=1, base=1):
        """铺 n 块同名的「我的」地（默认玩家 0 ⇒ owner=1）"""
        for k in range(n):
            self.land(base + k, owner=owner, name=name)
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        emu.write32(pb + P_CASH, self.cash)
        emu.write32(pb + P_BANK, self.bank)
        emu.write8(pb + P_TORTOISE, self.tortoise)
        emu.write8(pb + P_GOD, self.god)
        emu.write16(pb + P_FORTUNE, self.fortune & 0xFFFF)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(NUM_LANDS, self.num_lands)
        emu.write32(TOOL_PARAM, SENTINEL)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write32(LOOK_SRC, PATH_SRC)
        emu.write32(LOOK_COUNT, 6)          # 原版固定要 6 格（0x421881 的 push 6）
        emu.write32(LOOK_RET, self.forked)
        emu.write32(LOOK_CALLS, 0)
        emu.write32(LOOK_ARG1, 0)
        emu.write32(LOOK_ARG2, 0)
        # ★ 暂存区跨 call() 保留 ⇒ 每次必须把整张表清零
        emu.write(NODES, b"\x00" * (NODE_STRIDE * 64))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(OBJ_TABLE, b"\x00" * (OBJ_STRIDE * 32))
        emu.write(LOOK_BUF, b"\x00" * 16)
        emu.write(PATH_SRC, b"\x00" * 16)
        path = list(self.path) + [0] * (6 - len(self.path))
        emu.write(PATH_SRC, b"".join(struct.pack("<H", v & 0xFFFF) for v in path[:6]))
        for nid, (ent, flags) in self.nodes.items():
            b = NODES + nid * NODE_STRIDE
            emu.write16(b + N_ENTITY, ent)
            emu.write(b + N_FLAGS, struct.pack("<I", flags))
        for idx, (owner, ty, lv, price, house, name) in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write8(b + L_OWNER, owner)
            emu.write8(b + L_TYPE, ty)
            emu.write8(b + L_LEVEL, lv)
            emu.write16(b + L_LPRICE, price)
            emu.write16(b + L_HPRICE, house)
            emu.write(b + L_NAME, name.encode("ascii") + b"\x00")
        for idx, (owner, ty, lv, price, house, name) in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write8(b + F_OWNER, owner)
            emu.write8(b + F_TYPE, ty)
            emu.write8(b + F_LEVEL, lv)
            emu.write16(b + F_LPRICE, price)
            emu.write16(b + F_HPRICE, house)
            emu.write(b + F_NAME, name.encode("ascii") + b"\x00")
        for idx, ty in self.objs.items():
            emu.write8(OBJ_TABLE + (idx - 1) * OBJ_STRIDE + O_TYPE, ty)

    def run(self):
        r = self.emu.call(DICE, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(TOOL_PARAM)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        self.look_calls = self.emu.readu32(LOOK_CALLS)
        self.look_arg1 = self.emu.readu32(LOOK_ARG1)
        self.look_arg2 = self.emu.readu32(LOOK_ARG2)
        return self


def expect(w, desc, ret, param=None, look=1, rand=0):
    """跑一次并断言「返回 / 参数 / 前瞻调用次数 / rand 调用次数」。"""
    r = w.run()
    case(f"{desc}｜返回", r.ret, ret)
    case(f"{desc}｜前瞻调用次数", r.look_calls, look)
    case(f"{desc}｜rand 调用次数", r.rand_calls, rand)
    if param is not None:
        case(f"{desc}｜参数[0x48be64]", r.param, param)
    return r


def usable(w, cash=10000):
    """铺一个「第 1 格就是可立即定的无主地」的世界（同街 2 块我的地、同名）。"""
    w.my_street("A", 2)
    w.land(3, owner=0, name="A", price=100)
    w.land_node(11, 3)
    w.path_of(11)
    w.cash = cash
    return w


def main():
    print("差分测试 · 道具 8 遙控骰子 AI 判定 `0x00421827`（895 B）\n")
    w = World()
    print(f"0x463d48（×2.5 常量）= {w.const25}")

    # ═══════════ [A] 正对照 · 参数与步数 ═══════════
    print("\n[A] 正对照：无主地「同街 ≥ 2 + 现金 > 地价×2.5」⇒ 立即定，参数 = i+1")
    expect(usable(w.clear()), "A1 第 1 格立即定", 1, param=1)

    w.clear(); usable(w).path_of(0, 0, 0, 0, 0, 11)
    expect(w, "A2 命中在第 6 格", 1, param=6)

    w.clear(); usable(w).path_of(0, 11)
    expect(w, "A3 命中在第 2 格", 1, param=2)

    w.clear(); usable(w)
    r = expect(w, "A4 前瞻实参", 1, param=1)
    case("A4 前瞻第 1 实参 = 当前玩家(0)", r.look_arg1, 0)
    case("A4 前瞻第 2 实参 = 6", r.look_arg2, 6)

    w.clear(); usable(w); w.me = 2; w.lands[1] = (3, 0, 0, 100, 200, "A")
    w.lands[2] = (3, 0, 0, 100, 200, "A")
    r = expect(w, "A5 me=2（1 基 = 3）时前瞻实参", 1, param=1)
    case("A5 前瞻第 1 实参 = 2（玩家下标直接传）", r.look_arg1, 2)

    w.clear()                                   # 全 0 路径 ⇒ 节点 0 ⇒ 无实体
    expect(w, "A6 全 0 路径（节点 0）", 0, param=SENTINEL)

    w.clear(); usable(w).path_of(0, 0, 0, 0, 11)
    expect(w, "A7 命中在第 5 格", 1, param=5)

    # ═══════════ [B] 闸门 1：godInfo ∈ {7,8,15} ═══════════
    print("\n[B] 闸门 1：godInfo(+0x3f) ∈ {7,8,15} ⇒ 返回 0 且**前瞻都不调**")
    for god, ret, look in [(7, 0, 0), (8, 0, 0), (15, 0, 0),
                           (6, 1, 1), (9, 1, 1), (14, 1, 1), (16, 1, 1), (0, 1, 1),
                           (1, 1, 1), (2, 1, 1), (255, 1, 1)]:
        w.clear(); usable(w); w.god = god
        expect(w, f"B godInfo={god}", ret, param=(1 if ret else SENTINEL), look=look)

    # ═══════════ [C] 闸门 2：龜行中 ═══════════
    print("\n[C] 闸门 2：days_tortoise_walking(+0x39) != 0 ⇒ 返回 0 且前瞻不调")
    for t, ret, look in [(0, 1, 1), (1, 0, 0), (2, 0, 0), (3, 0, 0),
                         (0x7F, 0, 0), (0x80, 0, 0), (0xFF, 0, 0)]:
        w.clear(); usable(w); w.tortoise = t
        expect(w, f"C 龜行天数={t}", ret, param=(1 if ret else SENTINEL), look=look)

    # ═══════════ [D] 闸门 3：现金 + 存款 < 10000 ═══════════
    print("\n[D] 闸门 3：cash(+0x1c) + moneyInBank(+0x20) < 10000（32 位有符号）")
    for cash, bank, ret, look in [
        (0, 0, 0, 0), (9999, 0, 0, 0), (5000, 4999, 0, 0), (0, 9999, 0, 0),
        (9999, 1, 1, 1), (10000, 0, 1, 1), (5000, 5000, 1, 1),
        (10001, 0, 1, 1),
        # ★ 闸门过（前瞻被调）但现金买不起地（地价 100 ⇒ 需 >250）⇒ 返回 0
        (0, 10000, 0, 1), (-1, 10001, 0, 1),
        (-1, 10000, 0, 0), (-100, 100, 0, 0),
    ]:
        w.clear(); usable(w, cash=cash); w.bank = bank
        expect(w, f"D 现金={cash} 存款={bank}", ret,
               param=(1 if ret else SENTINEL), look=look)

    # ★ 32 位回绕：0x7fffffff + 1 ⇒ 负数 ⇒ 闸门判「低于一万」
    w.clear(); usable(w, cash=0x7FFFFFFF); w.bank = 1
    expect(w, "★ D 32 位回绕 0x7fffffff+1 ⇒ 负数 ⇒ 不用", 0, param=SENTINEL, look=0)

    # ═══════════ [E] 闸门 4：財運（word 有符号） ═══════════
    print("\n[E] 闸门 4：fortune(+0x46，word 有符号) < 0 ⇒ 返回 0 且前瞻不调")
    for f, ret, look in [(0, 1, 1), (1, 1, 1), (32767, 1, 1), (100, 1, 1),
                         (-1, 0, 0), (-100, 0, 0), (-32768, 0, 0)]:
        w.clear(); usable(w); w.fortune = f
        expect(w, f"E 財運={f}", ret, param=(1 if ret else SENTINEL), look=look)

    # ═══════════ [F] 闸门 5：前瞻有岔路 ═══════════
    print("\n[F] 闸门 5：lookahead 报「有岔路」⇒ 返回 0（参数保持哨兵）")
    w.clear(); usable(w).path_of(11, 12, forked=1)
    expect(w, "F forked=1", 0, param=SENTINEL, look=1)
    w.clear(); usable(w).path_of(11, 12, forked=0)
    expect(w, "F forked=0 正对照", 1, param=1, look=1)

    # ═══════════ [G] 逐格判据 a：玩家占用（bits 12-15） ═══════════
    print("\n[G] 逐格判据 a：(node+0x24) & 0xf000 ⇒ 跳过本格")
    for p in range(4):
        w.clear(); usable(w).on_node(11, p)
        expect(w, f"G 槽 {p} 站在第 1 格 ⇒ 跳过", 0, param=SENTINEL)
    w.clear(); usable(w).on_node(11, 0, 1, 2, 3)
    expect(w, "G 四槽全占 ⇒ 跳过", 0, param=SENTINEL)

    for extra, ret in [(0x0100, 1), (0x0200, 1), (0x0400, 1), (0x0800, 1),
                       (0x0F00, 1), (0x80000000, 1), (0x00C00000, 1)]:
        w.clear(); usable(w); w.node(11, LAND_MARK + 3, extra=extra)
        expect(w, f"G bits 8-11/31 不参与：extra=0x{extra:08x}", ret,
               param=(1 if ret else SENTINEL))

    # ★ bits 16-21 = 物件下标+1，无对应物件表项（类型 0）⇒ 不跳过
    w.clear(); usable(w).with_obj(11, 1, 0)
    expect(w, "G 物件下标非 0 但类型 0 ⇒ 不跳过", 1, param=1)

    # 占用在第 2 格：第 1 格空格、第 2 格占用+好地、第 3 格好地 ⇒ 参数 3
    w.clear(); w.my_street("A", 2); w.land(3, owner=0, name="A", price=100)
    w.land(4, owner=0, name="A", price=100); w.land(5, owner=0, name="A", price=100)
    w.node(11, 0); w.land_node(12, 3); w.on_node(12, 0); w.land_node(13, 4)
    w.path_of(11, 12, 13)
    expect(w, "★ G 第 2 格被占但第 3 格可定 ⇒ 参数 3（确实跳过后继续）", 1, param=3)

    # ═══════════ [H] 逐格判据 b：坏物件类型集 ═══════════
    print("\n[H] 逐格判据 b：物件类型 ∈ {5,6,7,8,10,11,16,17,18} ⇒ 跳过本格")
    for t in BAD_OBJ:
        w.clear(); usable(w).with_obj(11, 1, t)
        expect(w, f"H 坏物件类型 {t} 在第 1 格", 0, param=SENTINEL)
    for t in (0, 1, 2, 3, 4, 9, 12, 13, 14, 15, 19, 20, 26, 255):
        w.clear(); usable(w).with_obj(11, 1, t)
        expect(w, f"H 好物件类型 {t} 不跳过", 1, param=1)

    # 坏物件只影响它自己那一格
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=0, name="A", price=100); w.land(4, owner=0, name="A", price=100)
    w.land_node(11, 3); w.with_obj(11, 1, 5)
    w.land_node(12, 4); w.path_of(11, 12)
    expect(w, "★ H 第 1 格坏物件、第 2 格好地 ⇒ 参数 2", 1, param=2)

    # 物件下标 0（bits 16-21 == 0）⇒ 视为无物件
    w.clear(); usable(w); w.ghost_node(11); w.land_node(11, 3)
    w.nodes[11] = (LAND_MARK + 3, 0)
    expect(w, "H 无物件位（bits 16-21 == 0）", 1, param=1)

    # ═══════════ [I] 无主住宅地 ═══════════
    print("\n[I] 无主住宅地：同街（同名、且 owner==cur+1）≥ 2 且 cash > 2.5×地价")
    w.clear(); w.my_street("A", 1); w.land(3, owner=0, name="A", price=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "I 同街我的地 = 1 ⇒ 不够", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2, base=1); w.land(3, owner=0, name="A", price=100)
    w.land(4, owner=0, name="B", price=100); w.land_node(11, 4); w.path_of(11)
    w.cash = 10000
    expect(w, "I 同名数 = 0（我的地叫 A，目标是 B）", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2); w.land(3, owner=2, name="A", price=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "I 目标地是别人的（owner=2）⇒ 不处理", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 3); w.land(4, owner=0, name="A", price=100)
    w.land_node(11, 4); w.path_of(11); w.cash = 10000
    expect(w, "I 同街我的地 = 3 ⇒ 立即定（>2 也行）", 1, param=1)

    # ★★ 最高价值边界：2×cash == 5×price ⇒ **不合格**
    print("   ★★ 2.5× 边界（cash == 2.5×price 必须**不**合格）")
    for price, cash, ret in [
        (100, 250, 0),        # 2*250 = 500 == 5*100 ⇒ 不合格
        (100, 251, 0 + 1),    # 502 > 500 ⇒ 合格
        (4, 10, 0),           # 2*10 = 20 == 20 ⇒ 不合格
        (4, 11, 1),
        (3, 7, 0),            # 14 < 15 ⇒ 不合格（2.5*3 = 7.5，7 < 7.5）
        (3, 8, 1),            # 16 > 15 ⇒ 合格
        (1, 2, 0),            # 4 == 5? 2*2=4 < 5 ⇒ 不合格
        (1, 3, 1),            # 6 > 5 ⇒ 合格
        (1000, 2500, 0),
        (1000, 2499, 0),
        (1000, 2501, 1),
        (2, 5, 0),            # 10 == 10 ⇒ 不合格
        (2, 6, 1),
    ]:
        w.clear(); w.my_street("A", 2); w.land(3, owner=0, name="A", price=price)
        w.land_node(11, 3); w.path_of(11); w.cash = cash; w.bank = 100000
        expect(w, f"I ★边界 地价={price} 现金={cash}（2c={2*cash} 5p={5*price}）", ret,
               param=(1 if ret else SENTINEL))

    # 地价是 word ⇒ 65535 时 2*cash 需 > 327675
    w.clear(); w.my_street("A", 2); w.land(3, owner=0, name="A", price=65535)
    w.land_node(11, 3); w.path_of(11); w.cash = 163837    # 327674 < 327675
    expect(w, "I 地价=65535、现金=163837 ⇒ 不合格", 0, param=SENTINEL)
    w.clear(); w.my_street("A", 2); w.land(3, owner=0, name="A", price=65535)
    w.land_node(11, 3); w.path_of(11); w.cash = 163838
    expect(w, "I 地价=65535、现金=163838 ⇒ 合格", 1, param=1)

    # 无主地用的是 +0x1c 地价而不是 +0x1e 房价
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=0, name="A", price=100, house=1000000)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "★ I 无主地只看地价(+0x1c)：房价巨大也合格", 1, param=1)
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=0, name="A", price=1000000, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "★ I 无主地地价巨大 ⇒ 不合格（不是看房价）", 0, param=SENTINEL)

    # ═══════════ [J] 我的住宅 ═══════════
    print("\n[J] 我的住宅：type==0 ∧ level<5 ∧ 同街≥2 ∧ cash>2.5×房价(+0x1e) ∧ level>bestLevel ⇒ 只记下")
    # J1 ★ 记下 ≠ 立即定：第 3 格的无主地会「立即定」，故参数 = 3 而非 1
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, price=100, house=100)
    w.land(4, owner=0, name="A", price=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "★ J1 我的住宅(3级)只记下 ⇒ 扫到第 2 格才立即定 ⇒ 参数 2", 1, param=2)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 只有我的住宅可记 ⇒ 仍返回 1（记下的那条被采用）", 1, param=1)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, house=100)
    w.land(4, owner=1, name="A", level=2, house=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "★ J 等级 3 → 2：低者不覆盖 ⇒ 参数 1", 1, param=1)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=2, house=100)
    w.land(4, owner=1, name="A", level=3, house=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "★ J 等级 2 → 3：高者覆盖 ⇒ 参数 2", 1, param=2)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, house=100)
    w.land(4, owner=1, name="A", level=3, house=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "★ J 等级相同（3,3）：严格 > ⇒ 不覆盖 ⇒ 参数 1", 1, param=1)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=4, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 等级 4（<5）⇒ 采用", 1, param=1)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=5, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 等级 5 ⇒ 跳过（level < 5）", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=255, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 等级 255 ⇒ 跳过", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=0, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "★ J 等级 0：level > bestLevel(0) 不成立 ⇒ 不记 ⇒ 返回 0", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", ltype=1, level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 我的地 type=1（非住宅）⇒ 跳过", 0, param=SENTINEL)

    w.clear(); w.land(3, owner=1, name="A", level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 同街我的地 = 1（只有它自己）⇒ 跳过", 0, param=SENTINEL)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="B", level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "J 目标地与我同街吗（名字 B vs A）⇒ 同街数 0 ⇒ 跳过", 0, param=SENTINEL)

    # ★★ 我的住宅的 2.5× 边界用的是 +0x1e 房价
    for house, cash, ret in [(100, 250, 0), (100, 251, 1), (4, 10, 0), (4, 11, 1),
                             (3, 7, 0), (3, 8, 1)]:
        w.clear(); w.my_street("A", 2)
        w.land(3, owner=1, name="A", level=3, price=1, house=house)
        w.land_node(11, 3); w.path_of(11); w.cash = cash; w.bank = 100000
        expect(w, f"J ★边界 房价={house} 现金={cash}", ret,
               param=(1 if ret else SENTINEL))

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, price=1000000, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "★ J 我的住宅只看房价(+0x1e)：地价巨大也合格", 1, param=1)

    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=3, price=100, house=1000000)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "★ J 房价巨大 ⇒ 不合格（不是看地价）", 0, param=SENTINEL)

    # me=2（1 基 = 3）时归属判据
    w.clear(); w.my_street("A", 2, owner=3); w.land(3, owner=3, name="A", level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000; w.me = 2
    expect(w, "★ J me=2：owner==3 才是我的 ⇒ 采用", 1, param=1)
    w.clear(); w.my_street("A", 2, owner=2); w.land(3, owner=2, name="A", level=3, house=100)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000; w.me = 2
    expect(w, "★ J me=2：owner==2（玩家 1 的）⇒ 不是我的 ⇒ 0", 0, param=SENTINEL)

    # ═══════════ [K] 无主設施 ═══════════
    print("\n[K] 无主設施：cash > 2.5 × [+0x22] ⇒ 立即定（**无类型闸**）")
    w.clear(); w.fac(1, owner=0, ftype=1, price=100, house=200)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "K 无主設施可负担 ⇒ 立即定", 1, param=1)

    w.clear(); w.fac(1, owner=0, ftype=0, price=100)     # 公園
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ K 无主「公園」(type 0) 也可定（无类型闸）", 1, param=1)

    w.clear(); w.fac(1, owner=0, ftype=3, price=100)     # 加油站
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ K 无主「加油站」(type 3) 也可定", 1, param=1)

    for price, cash, ret in [(100, 250, 0), (100, 251, 1), (4, 10, 0), (4, 11, 1),
                             (3, 7, 0), (3, 8, 1), (1000, 2500, 0), (1000, 2501, 1)]:
        w.clear(); w.fac(1, owner=0, ftype=1, price=price)
        w.fac_node(11, 1); w.path_of(11); w.cash = cash; w.bank = 100000
        expect(w, f"K ★边界 [+0x22]={price} 现金={cash}", ret,
               param=(1 if ret else SENTINEL))

    w.clear(); w.fac(1, owner=0, ftype=1, price=100, house=1000000)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ K 无主設施只看 +0x22：+0x24 巨大也合格", 1, param=1)
    w.clear(); w.fac(1, owner=0, ftype=1, price=1000000, house=100)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ K +0x22 巨大 ⇒ 不合格（不是看 +0x24）", 0, param=SENTINEL)

    w.clear(); w.fac(1, owner=2, ftype=1, price=100)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "K 設施是别人的（owner=2）⇒ 不处理", 0, param=SENTINEL)

    # 格值边界：≤2000 / ≥6000 都不处理
    w.clear(); w.node(11, LAND_MARK)                      # 2000 ⇒ 不处理
    w.path_of(11); w.cash = 10000; w.my_street("A", 2)
    expect(w, "K 格值 2000（地塊 0 号）⇒ 不处理", 0, param=SENTINEL)
    w.clear(); w.node(11, FAC_MARK)                       # 4000 ⇒ 不处理
    w.path_of(11); w.cash = 10000
    expect(w, "K 格值 4000（設施 0 号）⇒ 不处理", 0, param=SENTINEL)
    w.clear(); w.land(0, owner=0, name="A", price=0)      # 地价 0：2*cash>0 ⇒ 合格
    w.my_street("A", 2); w.node(11, LAND_MARK + 0); w.path_of(11); w.cash = 1
    w.bank = 10000
    expect(w, "K 格值 2000 = 地塊 0 号：原版 `jle 2000` ⇒ 不处理（即使地价 0）",
           0, param=SENTINEL)
    w.clear(); w.comm_node(11, 1)                         # 6001 ⇒ 企業
    w.path_of(11); w.cash = 10000
    expect(w, "K 企業格（6001）⇒ 不处理", 0, param=SENTINEL)
    w.clear(); w.node(11, COMM_MARK)
    w.path_of(11); w.cash = 10000
    expect(w, "K 格值 6000 ⇒ 不处理", 0, param=SENTINEL)
    w.clear(); w.node(11, 0xFFFF)
    w.path_of(11); w.cash = 10000
    expect(w, "K 格值 65535 ⇒ 不处理", 0, param=SENTINEL)

    # ═══════════ [L] 我的設施 ═══════════
    print("\n[L] 我的設施：type != 0 ∧ type != 3 ∧ level < 5 ∧ cash > 2.5 × [+0x24] ⇒ 立即定")
    for ftype, ret in [(0, 0), (3, 0), (1, 1), (2, 1), (4, 1), (5, 1), (255, 1)]:
        w.clear(); w.fac(1, owner=1, ftype=ftype, level=0, price=1, house=100)
        w.fac_node(11, 1); w.path_of(11); w.cash = 10000
        expect(w, f"L 我的設施 type={ftype}", ret, param=(1 if ret else SENTINEL))

    for level, ret in [(0, 1), (1, 1), (4, 1), (5, 0), (255, 0)]:
        w.clear(); w.fac(1, owner=1, ftype=1, level=level, price=1, house=100)
        w.fac_node(11, 1); w.path_of(11); w.cash = 10000
        expect(w, f"L 我的設施 level={level}（门槛 < 5）", ret,
               param=(1 if ret else SENTINEL))

    for house, cash, ret in [(100, 250, 0), (100, 251, 1), (4, 10, 0), (4, 11, 1),
                             (3, 7, 0), (3, 8, 1)]:
        w.clear(); w.fac(1, owner=1, ftype=1, level=0, price=1, house=house)
        w.fac_node(11, 1); w.path_of(11); w.cash = cash; w.bank = 100000
        expect(w, f"L ★边界 [+0x24]={house} 现金={cash}", ret,
               param=(1 if ret else SENTINEL))

    w.clear(); w.fac(1, owner=1, ftype=1, price=1000000, house=100)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ L 我的設施只看 +0x24：+0x22 巨大也合格", 1, param=1)
    w.clear(); w.fac(1, owner=1, ftype=1, price=100, house=1000000)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "★ L +0x24 巨大 ⇒ 不合格（不是看 +0x22）", 0, param=SENTINEL)

    w.clear(); w.fac(1, owner=3, ftype=1, price=1, house=100)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "L 設施是别人的（owner=3）⇒ 不处理", 0, param=SENTINEL)
    w.clear(); w.fac(1, owner=0, ftype=1, price=1, house=100)
    w.fac_node(11, 1); w.path_of(11); w.cash = 10000
    expect(w, "L 无主設施走「无主」支 ⇒ 立即定", 1, param=1)

    # ═══════════ [M] 步数（1 基）与顺序/优先级 ═══════════
    print("\n[M] 步数 1 基 + 扫描顺序 + 立即定优先于记录")
    # 第 6 格才命中
    w.clear(); w.fac(1, owner=1, ftype=1, price=1, house=100)
    w.fac_node(16, 1); w.path_of(0, 0, 0, 0, 0, 16); w.cash = 10000
    expect(w, "M 第 6 格我的設施 ⇒ 参数 6", 1, param=6)

    # 第 3 格命中
    w.clear(); w.fac(1, owner=1, ftype=2, price=1, house=100)
    w.fac_node(13, 1); w.path_of(0, 0, 13); w.cash = 10000
    expect(w, "M 第 3 格我的設施 ⇒ 参数 3", 1, param=3)

    # 立即定优先：第 1 格是无主地（立即定），第 2 格是我的高等级住宅（记下）
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=0, name="A", price=100)
    w.land(4, owner=1, name="A", level=4, house=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "M 无主地(立即) 在前 ⇒ 参数 1", 1, param=1)

    # 反序：第 1 格我的住宅(记下)，第 2 格无主地(立即) ⇒ 参数 2
    w.clear(); w.my_street("A", 2)
    w.land(3, owner=1, name="A", level=4, house=100)
    w.land(4, owner=0, name="A", price=100)
    w.land_node(11, 3); w.land_node(12, 4); w.path_of(11, 12); w.cash = 10000
    expect(w, "M 记录在前、立即定在后 ⇒ 参数 2", 1, param=2)

    # 记录会被后续「更高等级」替换，且替换发生在第 5 格
    w.clear(); w.my_street("A", 2)
    for k, lv in enumerate([1, 0, 4, 0, 2]):
        w.land(3 + k, owner=1, name="A", level=lv, house=100)
        w.land_node(11 + k, 3 + k)
    w.path_of(11, 12, 13, 14, 15); w.cash = 10000
    expect(w, "M 等级序列 1,0,4,0,2 ⇒ 最高在第 3 格 ⇒ 参数 3", 1, param=3)

    # 全是「不成立」的格 ⇒ 返回 0、参数保持哨兵
    w.clear(); w.my_street("A", 1)
    w.land(3, owner=2, name="A", price=1)
    w.land_node(11, 3); w.path_of(11); w.cash = 10000
    expect(w, "M 全部不合格 ⇒ 0 且参数保持哨兵", 0, param=SENTINEL)

    # 同一格既有占用又有好地 ⇒ 占用优先（跳过）
    w.clear(); usable(w).on_node(11, 3)
    expect(w, "M 占用与好地同格 ⇒ 跳过", 0, param=SENTINEL)

    # ═══════════ 结果 ═══════════
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
