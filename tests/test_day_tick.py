#!/usr/bin/env python3
"""
通道 2 差分测试 #23 · 回合边界的**阻碍计数递减 / 释放**（`0x0041c84f`）

这是 4 个阻碍计数（住宿/消失/监狱/医院）唯一的递减点，也是「刑满放人」的触发点。
复刻里对应 `rich4-remake/packages/core/src/rules/blocking.ts` 的 `tickBlocking`。

## 为什么这支必须钉住

第 79 条查出「释放是两段式」时留下一个**时机**问题没定：释放函数
（`0x43d7bf`/`0x43ee6e`）**不清 `+0x34`/`+0x35`**，那计数是谁清的？
本轮把全链读完，结论是：

1. `0x41c84f` 的读数分支（A 级，见下）：
   - 计数 `!= 0x80` 且 `!= 0` ⇒ `计数--`；**减到 0 的当次就 `| 0x80`**；
   - 计数 `& 0x80` ⇒ `call 释放函数`，**不再递减**（`0x80` 原地留着）。
2. 释放函数里只有**消失**那一支（`0x40d4e5`）自己把计数清 0；
   监狱/医院两支**一个字都不写** `+0x34`/`+0x35`（`0x43d7bf` 只 `call 0x40d6be` + 清占用表）。
3. ⇒ 监狱/医院的计数是由**走路例程** `0x40c05c` 在 `0x40c3cf` 那句
   `mov dword [player+0x32], 0`（一次清四个）里清的，而那一支要
   `+0x15 & 0x30` 且 `trunc(距离/步长) >= 2`。
   也就是说：**刑满那一回合玩家要走一段路（从綠島／醫院大樓走回棋盘）**，
   走完才把四个计数清零 —— 这一回合**不掷骰**（回合推进函数 `0x418ebd`
   在 `0x418f8e` 直接 `jmp` 掉），是白丢的一回合。

## 打桩清单（都是非目标路径）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41906a` | 弹/关一个 0xf 号资源窗（`0x417e26`） | `ret` |
| `0x42915a` | 回合边界的**股票**前置（12 支遍历） | `ret`（另有 `test_sell_stock.py` 等覆盖股票侧） |
| `0x436a5a` | 回合边界的**银行**前置 | `ret`（另有 `test_bank_settle.py` 覆盖银行侧） |
| `0x40b93b` | 更新该玩家的**显示**（读回合记录 + `0x40b8d8` 摆图） | `ret` |
| `0x450441` / `0x45144f` / `0x456e11` | 载入 MKF 资源 / blit / 释放 | `ret` |

⚠️ **诚实边界**：因此本测试**只覆盖**「计数与释放」那一段（约 60 条指令的骨架
＋四个释放函数），`0x42915a`/`0x436a5a`/`0x40b93b` 的内部行为不在内。
另：`idx >= 4` 的 NPC 分支（`0x41ce39`）**未覆盖**。

跑法：cd rich4-spec && .venv/bin/python tests/test_day_tick.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

TICK = 0x41C84F

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE = 0x08, 0x0A, 0x0C
P_WHO = 0x15
P_HOTEL, P_VANISH, P_PRISON, P_HOSPITAL = 0x32, 0x33, 0x34, 0x35
RELEASE_FLAG = 0x10  # `+0x15` 的「走回棋盘」位（0x40d6be 置）
PRISON_OCC, HOSPITAL_OCC = 0x496B30, 0x496B60
NODE_TABLE_PTR = 0x498E80
PAUSE_GATE = 0x46CAF8  # `[0x46caf8] != 0` ⇒ 整个 tick 直接返回

NODES = SCRATCH_BASE + 0x1000
OLD_NODE = 60
STUB_VAS = (0x41906A, 0x42915A, 0x436A5A, 0x40B93B, 0x450441, 0x45144F, 0x456E11)

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        for va in STUB_VAS:
            self.emu.patch(va, b"\xC3")

    def tick(self, idx=1, *, hotel=0, vanish=0, prison=0, hospital=0, who=1,
             pause=0, occ=None, node=OLD_NODE, flag=0):
        def setup(emu):
            emu.write8(PAUSE_GATE, pause)
            emu.write32(NODE_TABLE_PTR, NODES)
            for nid in (node,):
                base = NODES + nid * 0x28  # ★ 表按 nodeId 直接索引（0 号哨兵）
                emu.write16(base + 0x00, 4000 + nid)
                emu.write16(base + 0x02, 5000 + nid)
                emu.write(base + 0x24, b"\x00\x00\x00\x00")
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write16(base + P_X, 111)
            emu.write16(base + P_Y, 222)
            emu.write16(base + P_NODE, node)
            emu.write8(base + P_WHO, who)
            emu.write8(base + 0x10, 3)
            emu.write8(base + 0x1B, 0)
            emu.write8(base + P_HOTEL, hotel)
            emu.write8(base + P_VANISH, vanish)
            emu.write8(base + P_PRISON, prison)
            emu.write8(base + P_HOSPITAL, hospital)
            for i in range(8):
                emu.write8(PRISON_OCC + i, (occ or {}).get(("prison", i), 1 if i == idx else 0))
                emu.write8(HOSPITAL_OCC + i, (occ or {}).get(("hospital", i), 1 if i == idx else 0))

        self.emu.call(TICK, [idx], setup=setup)
        return Snap(self.emu, idx, node)

    def tick_many(self, counters, idx=1, **kw):
        """四个计数一起给，用来验「一次 tick 处理全部四个」。"""
        return self.tick(idx, hotel=counters[0], vanish=counters[1],
                         prison=counters[2], hospital=counters[3], **kw)


class Snap:
    def __init__(self, e, idx, node):
        self.e = e
        base = PLAYER_BASE + idx * PLAYER_STRIDE
        self.hotel = e.read8(base + P_HOTEL)
        self.vanish = e.read8(base + P_VANISH)
        self.prison = e.read8(base + P_PRISON)
        self.hospital = e.read8(base + P_HOSPITAL)
        self.who = e.read8(base + P_WHO)
        self.facing = e.read8(base + 0x10)
        self.backup = e.read8(base + 0x1B)
        self.node = e.read16(base + P_NODE)
        self.prison_occ = [e.read8(PRISON_OCC + i) for i in range(8)]
        self.hospital_occ = [e.read8(HOSPITAL_OCC + i) for i in range(8)]
        self.node_mask = e.readu32(NODES + node * 0x28 + 0x24)

    @property
    def counters(self):
        return (self.hotel, self.vanish, self.prison, self.hospital)


def main():
    print("差分测试 #23：回合边界阻碍计数递减 / 释放 —— 0x41c84f\n")
    f = F()

    print("[1] 递减：四格各自独立，减到 0 的**当次**就挂 0x80")
    s = f.tick_many((5, 4, 3, 2))
    case("5/4/3/2 → 4/3/2/1", s.counters, (4, 3, 2, 1))
    s = f.tick_many((1, 1, 1, 1))
    case("★ 1/1/1/1 → 0x80 ×4（同一 tick 里四格都处理）", s.counters, (0x80,) * 4)
    s = f.tick_many((0, 0, 0, 0))
    case("0 不动", s.counters, (0, 0, 0, 0))
    s = f.tick(1, hotel=0x7F)
    case("0x7f（高位数占满）→ 0x7e（只减低 7 位那一格）", s.hotel, 0x7E)

    print("\n[2] ★ 消失那一格用 **0x3f** 掩码判零，且 bit6 = 原因被保留")
    s = f.tick(1, vanish=0x41)
    case("0x41 = 天数1 | 原因0x40 → 0xC0（0x40 保留 + 挂 0x80）", s.vanish, 0xC0)
    s = f.tick(1, vanish=0x42)
    case("0x42（天数2）→ 0x41（还在消失中，不挂 0x80）", s.vanish, 0x41)
    s = f.tick(1, vanish=0x05)
    case("0x05 → 0x04", s.vanish, 0x04)

    print("\n[3] ★ 释放：计数挂着 0x80 时**不再递减**，而是调释放函数")
    s = f.tick(1, prison=0x80)
    case("监狱：+0x34 仍是 0x80（释放函数**不清**它）", s.prison, 0x80)
    case("监狱：占用表 [1] 被清", s.prison_occ, [0] * 8)
    case("监狱：置「走回棋盘」位 +0x15 |= 0x10", s.who & RELEASE_FLAG, RELEASE_FLAG)
    case("监狱：node[nodeId] |= 0x100<<1 = 0x200", s.node_mask, 0x200)
    # 两张表都按「[idx] = 1」铺的，所以监狱释放**只**动监狱表
    case("监狱：医院表原样（只清监狱那一张）", s.hospital_occ, [0, 1, 0, 0, 0, 0, 0, 0])

    s = f.tick(1, hospital=0x80)
    case("医院：+0x35 仍是 0x80", s.hospital, 0x80)
    case("医院：占用表 [1] 被清", s.hospital_occ, [0] * 8)
    case("医院：置「走回棋盘」位", s.who & RELEASE_FLAG, RELEASE_FLAG)

    s = f.tick(1, hotel=0x80)
    case("住宿：+0x32 仍是 0x80", s.hotel, 0x80)
    case("住宿：只立标记（没有占用表可清）", s.who & RELEASE_FLAG, RELEASE_FLAG)

    s = f.tick(1, vanish=0x80)
    case("★ 消失：+0x33 被**清成 0**（四格里只有它自己清账）", s.vanish, 0)
    case("★ 消失：`+0x15` **不置** 0x10（它不走「回棋盘」那一支）", s.who & RELEASE_FLAG, 0)
    case("消失：node[nodeId] |= 0x200（这一支照置）", s.node_mask, 0x200)

    print("\n[4] 独立性与前置闸")
    s = f.tick(1, hotel=0x80, prison=3)
    case("住宿在待释放 + 监狱 3 天 → 0x80 / 2（互不干扰）", (s.hotel, s.prison), (0x80, 2))
    s = f.tick(1, prison=0x80, hospital=0x80)
    case("两张表各自清各自的槽", (s.prison_occ, s.hospital_occ), ([0] * 8, [0] * 8))
    s = f.tick_many((3, 3, 3, 3), who=0)
    case("★ whoPlays == 0（出局）× 四格全 3 → 一个都不减", s.counters, (3, 3, 3, 3))
    s = f.tick_many((3, 3, 3, 3), pause=1)
    case("★ [0x46caf8] != 0（全局暂停）→ 一个都不减", s.counters, (3, 3, 3, 3))
    s = f.tick(2, prison=2)
    case("被 tick 的是**参数指定的**玩家（idx=2）：他自己的计数减到 1", s.prison, 1)
    base1 = PLAYER_BASE + 1 * PLAYER_STRIDE
    case("玩家 1 的计数不受影响（仍为 0）",
         f.emu.read8(base1 + P_PRISON), 0)

    print("\n[5] 释放链的**终点**：监狱/医院的计数由走路例程清，不由本函数清")
    s = f.tick(1, prison=0x80)
    case("★ 连调两次 tick：0x80 原地不动（不会自动清零）", f.tick(1, prison=s.prison).prison, 0x80)
    case("   ⇒ 清 0 只能在 `0x40c3cf` 的 `mov dword [player+0x32], 0` 那一句",
         s.prison, 0x80)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 68}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
