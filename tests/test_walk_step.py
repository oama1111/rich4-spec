#!/usr/bin/env python3
"""
通道 2 差分测试 #29 · **走一格（走路例程）** `0x0040c05c`（1840 字节，全 exe 最大的一支未测函数）

调用点只有 `0x0040d950`（每帧一次）；`ecx = [0x49910c] < 4` 走玩家分支，`>= 4` 走替身分支。

本测试钉住**玩家分支**的整条规则链（表现层调用打桩）：

1. 段起点（`[0x4749dc] == 0`）**选下一格**：候选 = 4 个邻接槽里「非 0 ∧ 该槽未封路
   （`flags & (0x40000000 >> slot)`）∧ ≠ 来路 `+0x0e`」，再 `rand() % k` 摇一个；
   一个候选都没有 ⇒ **原路返回**（写 `+0x0e`）；
2. 换格：`+0x0e ← 旧 +0x0c`、`+0x0c ← 新格`；占用位图 `node[旧].+0x24 &= ~mask`、
   `node[新].+0x24 |= mask`（`mask = 0x100 << 玩家号`）；
3. 朝向 `+0x10 = dir(来路 → 落点)`（★ 参数序：**最后压栈的是第一参**，见 §D）；
4. 帧数 `[0x4749dc] = trunc(dist / 步长)`，步长表 `[0x4749d8] = [8,12,16,8]`，
   下标 = `traffic_method & 3`；`[0x48baf4] = 帧数 >> 1`；
5. ★ **特殊支**：`record[+1] != 0` **或** `+0x15 & 0x30` ⇒ `帧数 = trunc(dist × 0.125)`；
6. 每帧插值：float 累加器 `[玩家号*0x34 + 0x498ea8/ac]` 每帧加 `dx/帧数(未截断的 N)`，
   `+0x08/+0x0a` = `trunc(累加器)`；
7. 帧数用尽那一拍：坐标**吸附到落点**、返回值 1（其余拍返回 0）；
8. ★★ `+0x15 & 0x30` 且 `帧数 < [0x48baf4]`：`0x10` 支把 `+0x32..+0x35` **一次清四个**
   （`mov dword [player+0x32], 0`）并把 `[0x48baf4]` 清零；`0x20` 支只清 `0x20` 位；
9. 「走回棋盘」支（`+0x15 & 0x10`）：**不选路**、起点 = **贴图坐标** `+0x08/+0x0a`、
   终点 = 当前格坐标；
10. 「被挪过」支（`+0x15 & 0x20`）：**不选路**、起点 = **当前格坐标**、
    终点 = `設施[+0x4a]` 的坐标（表 `0x498e88`，stride 0x38，movsx）；
11. 夢遊（`+0x37`）⇒ 回合记录 `+0x04` 在 0..5 之间循环；
12. `0x454fb4(dx, dy)` 的**朝向真值表**（8 向 + 45° 扇区边界 + `(0,0)`）。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x0040fc00` | 落格登记（返回值未用） | `ret` |
| `0x0040b93b` | 轨迹/落点辅助（返回值未用） | `ret` |
| `0x00456f2d` | PRNG | 从**数据槽**读返回值（见 `test_turn_around.py` 的说明） |

`0x4582bc`（sqrt）、`0x457dbc`（向零截断）、`0x407a8c`（两格朝向）、`0x454fb4`（朝向量化）
一律**真跑** —— 本测试要的就是它们和主干的组合行为。

跑法：cd rich4-spec && .venv/bin/python tests/test_walk_step.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

WALK = 0x40C05C
DIRFN = 0x454FB4
NODEFN = 0x407A8C

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE, P_LAST = 0x08, 0x0A, 0x0C, 0x0E
P_FACING, P_TRAFFIC, P_WHO = 0x10, 0x11, 0x15
P_HOTEL, P_SLEEPWALK, P_FACID = 0x32, 0x37, 0x4A

REC_BASE, REC_STRIDE = 0x498EA0, 0x34
REC_TABLE = 0x498EBC
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10

NODE_TABLE_PTR, NODE_STRIDE = 0x498E80, 0x28
NODE_ADJ, NODE_FLAGS = 0x18, 0x24
FAC_TABLE_PTR, FAC_STRIDE = 0x498E88, 0x38

FRAMES, HALF, CUR = 0x4749DC, 0x48BAF4, 0x49910C
STEP_X, STEP_Y = 0x48BAEC, 0x48BAF0     # 每帧位移（float，段起点算一次、逐帧累加）
DEST_X, DEST_Y = 0x48BAE4, 0x48BAE8     # 本段落点（整点）
SPEED_TABLE = 0x4749D8
ACC_BASE, ACC_X, ACC_Y = 0x498EA8, 0x00, 0x04
SPECIAL_K = 0x4631DC  # float 0.125

F_END_EVENT, F_TRAIL = 0x40FC00, 0x40B93B
PRNG = 0x456F2D
RAND_SLOT = SCRATCH_BASE + 0x800

NODES = SCRATCH_BASE + 0x1000
FACS = SCRATCH_BASE + 0x2000
DESC = SCRATCH_BASE + 0x3000

# 节点：1 号在 (100,100)，2 号在它**右**边 100 px，3 号在 2 号**下**边 60 px
COORD = {1: (100, 100), 2: (200, 100), 3: (200, 160), 4: (100, 160), 5: (40, 40)}
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def case_true(desc, ok):
    RESULTS.append(bool(ok))
    print(f"  {'✅' if ok else '❌'} {desc}")
    return ok


class World:
    """把玩家/节点/回合记录的状态留在 Python 侧，每拍重新注入（`Emu.call` 会 reset）。"""

    def __init__(self):
        self.emu = Emu()
        self.emu.patch(F_END_EVENT, b"\xC3")
        self.emu.patch(F_TRAIL, b"\xC3")
        # PRNG 桩：mov eax, [slot] / ret —— 返回值放**数据**里，避免重复改代码段补丁
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    def clear(self):
        self.idx = 0
        self.p = {
            "node": 1, "last": 0, "x": 100, "y": 100, "facing": 2, "traffic": 0,
            "who": 0, "hotel": 0, "sleepwalk": 0, "fac": 0,
        }
        self.adj = {1: [2, 0, 0, 0], 2: [0, 0, 0, 0], 3: [0, 0, 0, 0], 4: [0, 0, 0, 0]}
        self.blocked = {}
        self.occ = {}          # nodeId → 占用位图（只记我们关心的 dword）
        self.frames = 0
        self.half = 0
        self.rand = 0
        self.rec = {"+0": 0, "+1": 0, "+2": 0, "+3": 0, "+4": 0}
        self.acc = None        # (float, float) 或 None = 由坐标初始化
        self.fac_coord = (0, 0)
        self.step = (0.0, 0.0)   # [0x48baec]/[0x48baf0]：段起点算一次，跨拍要保持
        self.dest = (0, 0)       # [0x48bae4]/[0x48bae8]：本段落点

    # ── 注入 / 回读 ─────────────────────────────────────────────────
    def _setup(self, emu):
        p = self.p
        emu.write32(CUR, self.idx)
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(FRAMES, self.frames)
        emu.write32(HALF, self.half)
        emu.write(DEST_X, struct.pack("<i", self.dest[0]))
        emu.write(DEST_Y, struct.pack("<i", self.dest[1]))
        emu.write(STEP_X, struct.pack("<f", self.step[0]))
        emu.write(STEP_Y, struct.pack("<f", self.step[1]))
        for nid, (nx, ny) in COORD.items():
            base = NODES + nid * NODE_STRIDE
            emu.write16(base + 0, nx & 0xFFFF)
            emu.write16(base + 2, ny & 0xFFFF)
            for slot in range(4):
                emu.write16(base + NODE_ADJ + slot * 2,
                            (self.adj.get(nid, [0, 0, 0, 0])[slot]) & 0xFFFF)
            flags = self.occ.get(nid, 0)
            for slot in self.blocked.get(nid, ()):
                flags |= 0x40000000 >> slot
            emu.write32(base + NODE_FLAGS, flags & 0xFFFFFFFF)
        fid = p["fac"]
        fbase = FACS + fid * FAC_STRIDE
        emu.write16(fbase + 0, self.fac_coord[0] & 0xFFFF)
        emu.write16(fbase + 2, self.fac_coord[1] & 0xFFFF)
        pb = PLAYER_BASE + self.idx * PLAYER_STRIDE
        emu.write16(pb + P_X, p["x"] & 0xFFFF)
        emu.write16(pb + P_Y, p["y"] & 0xFFFF)
        emu.write16(pb + P_NODE, p["node"])
        emu.write16(pb + P_LAST, p["last"])
        emu.write8(pb + P_FACING, p["facing"])
        emu.write8(pb + P_TRAFFIC, p["traffic"])
        emu.write8(pb + P_WHO, p["who"])
        emu.write8(pb + P_HOTEL, p["hotel"])
        emu.write8(pb + P_SLEEPWALK, p["sleepwalk"])
        emu.write16(pb + P_FACID, p["fac"])
        rb = REC_BASE + self.idx * REC_STRIDE
        emu.write32(rb + 0, self.rec["+0"] | (self.rec["+1"] << 8)
                    | (self.rec["+2"] << 16) | (self.rec["+3"] << 24))
        emu.write8(rb + 4, self.rec["+4"])
        # 回合记录里的「动画描述符指针表」：真机上由动画例程写，这里给它一张我们自己造的
        # （`[表项 + 4] >> 3` 是这一支动画的总拍数）
        for i in range(8):
            emu.write32(REC_TABLE + i * 4, DESC)
        emu.write32(DESC + 4, 24)          # 24 >> 3 = 3 拍
        if self.acc is not None:
            emu.write(ACC_BASE + self.idx * REC_STRIDE + ACC_X,
                      struct.pack("<f", self.acc[0]))
            emu.write(ACC_BASE + self.idx * REC_STRIDE + ACC_Y,
                      struct.pack("<f", self.acc[1]))

    def _readback(self):
        p = self.p
        emu = self.emu
        pb = PLAYER_BASE + self.idx * PLAYER_STRIDE
        p["x"] = emu.read16(pb + P_X)
        p["y"] = emu.read16(pb + P_Y)
        p["node"] = emu.read16(pb + P_NODE)
        p["last"] = emu.read16(pb + P_LAST)
        p["facing"] = emu.read8(pb + P_FACING)
        p["who"] = emu.read8(pb + P_WHO)
        p["hotel"] = emu.read8(pb + P_HOTEL)
        self.frames = emu.readu32(FRAMES)
        self.half = emu.readu32(HALF)
        self.dest = (struct.unpack("<i", emu.read(DEST_X, 4))[0],
                     struct.unpack("<i", emu.read(DEST_Y, 4))[0])
        self.step = (struct.unpack("<f", emu.read(STEP_X, 4))[0],
                     struct.unpack("<f", emu.read(STEP_Y, 4))[0])
        rb = REC_BASE + self.idx * REC_STRIDE
        d = emu.read(rb, 5)
        self.rec["+0"], self.rec["+1"], self.rec["+2"], self.rec["+3"] = d[0], d[1], d[2], d[3]
        self.rec["+4"] = d[4]
        self.acc = (
            struct.unpack("<f", emu.read(ACC_BASE + self.idx * REC_STRIDE + ACC_X, 4))[0],
            struct.unpack("<f", emu.read(ACC_BASE + self.idx * REC_STRIDE + ACC_Y, 4))[0],
        )
        for nid in COORD:
            self.occ[nid] = emu.readu32(NODES + nid * NODE_STRIDE + NODE_FLAGS)
        return emu

    def tick(self):
        r = self.emu.call(WALK, [], setup=self._setup)
        self._readback()
        return r

    def occ_bit(self, nid):
        return (self.occ.get(nid, 0) >> (8 + self.idx)) & 1


def main():
    print("差分测试 #29：走一格（走路例程）—— 0x40c05c\n")
    w = World()

    # ── A. 朝向量化器真值表 ────────────────────────────────────────
    print("[A] 0x454fb4(dx, dy) 的 8 个主方向（屏幕 y 向下）")
    for name, dx, dy, want in [
        ("右 (+100,0)", 100, 0, 2), ("右下 (+100,+100)", 100, 100, 1),
        ("下 (0,+100)", 0, 100, 0), ("左下 (-100,+100)", -100, 100, 7),
        ("左 (-100,0)", -100, 0, 6), ("左上 (-100,-100)", -100, -100, 5),
        ("上 (0,-100)", 0, -100, 4), ("右上 (+100,-100)", 100, -100, 3),
    ]:
        case(name, w.emu.call(DIRFN, [dx, dy])["eax"] & 0xFF, want)
    case("非等距也按角度：(+200,+10) 仍在「右」扇区", w.emu.call(DIRFN, [200, 10])["eax"] & 0xFF, 2)
    case("  (+200,+90) 已进「右下」扇区", w.emu.call(DIRFN, [200, 90])["eax"] & 0xFF, 1)
    case("  (+90,+200) 仍在「右下」扇区", w.emu.call(DIRFN, [90, 200])["eax"] & 0xFF, 1)
    case("  (+40,+200) 已进「下」扇区", w.emu.call(DIRFN, [40, 200])["eax"] & 0xFF, 0)
    import math
    for deg, want in [(22.4, 2), (22.6, 1), (67.4, 1), (67.6, 0), (112.4, 0),
                      (112.6, 7), (157.4, 7), (157.6, 6), (202.4, 6), (202.6, 5),
                      (247.4, 5), (247.6, 4), (292.4, 4), (292.6, 3),
                      (337.4, 3), (337.6, 2)]:
        rad = math.radians(deg)
        dx = round(1000 * math.cos(rad))
        dy = round(1000 * math.sin(rad))
        case(f"扇区边界 {deg}°（±0.1°）", w.emu.call(DIRFN, [dx, dy])["eax"] & 0xFF, want)
    case("★ (0,0) ⇒ 仍走完「查重映射表」那一拍 ⇒ 2（不是 0）",
         w.emu.call(DIRFN, [0, 0])["eax"] & 0xFF, 2)

    # ── B. 两格朝向 0x407a8c ───────────────────────────────────────
    print("\n[B] 0x407a8c(a, b) = dir(node[a] → node[b])")
    w.clear()

    def nodir(a, b):
        return w.emu.call(NODEFN, [a, b], setup=w._setup)["eax"] & 0xFF

    case("1→2（右）", nodir(1, 2), 2)
    case("2→1（左）", nodir(2, 1), 6)
    case("2→3（下 60px）", nodir(2, 3), 0)
    case("3→2（上）", nodir(3, 2), 4)

    # ── C. 段起点：选下一格 ────────────────────────────────────────
    print("\n[C] 段起点选下一格（候选筛选 + PRNG + 占用位图）")
    w.clear()
    w.tick()
    case("唯一的候选（右邻居）⇒ 换到 2 号格", w.p["node"], 2)
    case("  来路 ← 旧格 1", w.p["last"], 1)
    case("★ 旧格占用位（0x100<<0）被清", w.occ_bit(1), 0)
    case("★ 新格占用位被置", w.occ_bit(2), 1)

    w.clear()
    w.adj[1] = [2, 3, 4, 5]
    w.rand = 5
    w.tick()
    case("4 个候选、rand=5 ⇒ 5%4=1 ⇒ 第 1 个（=3 号格）", w.p["node"], 3)
    w.clear()
    w.adj[1] = [2, 3, 4, 5]
    w.rand = 3
    w.tick()
    case("rand=3 ⇒ 第 3 个（=5 号格）", w.p["node"], 5)

    w.clear()
    w.adj[1] = [2, 3, 0, 0]
    w.blocked[1] = (0,)
    w.rand = 0
    w.tick()
    case("★ 槽 0 被封路（bit30）⇒ 候选只剩 3 号格", w.p["node"], 3)

    w.clear()
    w.adj[1] = [2, 3, 4, 5]
    w.p["last"] = 2
    w.rand = 0
    w.tick()
    case("★ 邻接里等于来路的那个被排除 ⇒ 第 0 个候选 = 3", w.p["node"], 3)

    w.clear()
    w.adj[1] = [0, 0, 0, 0]
    w.p["last"] = 4
    w.tick()
    case("★★ 一个候选都没有 ⇒ **原路返回**（node ← 旧来路 4）", w.p["node"], 4)
    case("   来路也照样更新成旧格 1", w.p["last"], 1)

    w.clear()
    w.adj[1] = [2, 3, 0, 0]
    w.p["last"] = 2
    w.p["who"] = 0x01
    w.rand = 0
    w.tick()
    case("候选只剩 3（2 是来路）⇒ 换到 3", w.p["node"], 3)

    # ── D. 朝向 = dir(来路 → 落点) ─────────────────────────────────
    print("\n[D] 朝向 +0x10 与「谁面向谁」（参数序 = cdecl 最后压栈的是第一参）")
    w.clear()
    w.adj[1] = [2, 0, 0, 0]
    w.tick()
    case("往右走 ⇒ 朝向 = 2（右）—— **面朝去路**，不是倒着走", w.p["facing"], 2)
    w.clear()
    w.adj[1] = [3, 0, 0, 0]
    w.p["node"] = 1
    w.tick()
    case("从 (100,100) 往 (200,160) 走 ⇒ 朝向 = 1（右下）", w.p["facing"], 1)

    # ── E. 帧数 / 步长表 ──────────────────────────────────────────
    print("\n[E] 帧数 = trunc(距离 / 步长[traffic & 3])，步长表 = [8,12,16,8]")
    for traffic, want in [(0, 12), (1, 8), (2, 6), (3, 12)]:
        w.clear()
        w.p["traffic"] = traffic
        w.tick()
        case(f"traffic={traffic}：100 px ÷ {[8, 12, 16, 8][traffic]} ⇒ 首拍后剩 {want - 1}",
             w.frames, want - 1)
    w.clear()
    w.p["who"] = 0x10          # 走回棋盘 ⇒ 特殊支：dist × 0.125
    w.p["node"], w.p["x"], w.p["y"] = 2, 300, 100   # 贴图在 (300,100)，要回到 2 号格 (200,100)
    w.tick()
    case("★ 走回棋盘（+0x15 & 0x10）⇒ 100 × 0.125 = 12.5 ⇒ 12 帧", w.frames, 11)
    w.clear()
    w.rec["+1"] = 1            # 动画序号非 0 ⇒ 也走特殊支
    w.tick()
    case("★ record[+1] != 0 ⇒ 也走特殊支（12 帧）", w.frames, 11)
    w.clear()
    w.p["node"], w.p["x"], w.p["y"] = 5, 40, 40
    w.adj[5] = [1, 0, 0, 0]
    w.p["traffic"] = 2         # 16 px/拍
    w.tick()
    case("极短走法：从 (40,40) 到 (100,100) = 84.85 px / 16 ⇒ trunc = 5", w.frames, 4)

    # ── F. 每帧插值 ───────────────────────────────────────────────
    print("\n[F] 每帧插值：float 累加器 + trunc 回整数")
    w.clear()
    w.tick()                    # 第 1 拍
    case("第 1 拍：100 + 100/12 = 108.33 ⇒ x = 108", w.p["x"], 108)
    case("  y 不动（dy = 0）", w.p["y"], 100)
    case("  返回值 0（这一格还没走完）", w.emu.readu32(FRAMES), 11)
    for _ in range(10):
        w.tick()
    case("★ 每拍步长 = dx / **未截断**的 12.5 = 8.0 ⇒ 第 11 拍 = 188", w.p["x"], 188)
    case("  还剩 1 拍", w.frames, 1)
    r = w.tick()
    case("★ 第 12 拍：吸附到落点 x = 200", w.p["x"], 200)
    case("★★ 返回值 1（= 「这一格走完了」）", r["eax"], 1)
    case("  帧数归零", w.frames, 0)

    w.clear()
    w.p["traffic"] = 1          # 12 px/拍 ⇒ 100/12 = 8.33 ⇒ 8 拍
    for _ in range(7):
        w.tick()
    case("8 拍那一支：第 7 拍 x = 100 + 7×(100/8.3333) = 184", w.p["x"], 184)
    w.tick()
    case("  第 8 拍吸附 200", w.p["x"], 200)

    # ── G. 帧数 < 半程时的清账 ────────────────────────────────────
    print("\n[G] `+0x15 & 0x30` 且 `帧数 < 半程` ⇒ 清账")
    w.clear()
    w.p["who"] = 0x10
    w.p["hotel"] = 3
    w.p["node"], w.p["x"], w.p["y"] = 2, 300, 100   # dist = 100 ⇒ 12 帧，半程 = 6
    w.tick()
    case("  首拍：12 帧", w.frames, 11)
    case("第 1 拍（剩 11 ≥ 半程 6）⇒ 四个计数**还没**清", w.p["hotel"], 3)
    for _ in range(5):
        w.tick()
    case("  走到剩 6（= 半程，jge 跳过）⇒ 仍未清", w.p["hotel"], 3)
    w.tick()
    case("★★ 第 7 拍（剩 5 < 半程）⇒ `mov dword [player+0x32], 0` 一次清四个", w.p["hotel"], 0)
    case("  并把 [0x48baf4] 清零（只清一次）", w.half, 0)

    w.clear()
    w.p["who"] = 0x20           # 只有「被挪过」这一位
    w.p["hotel"] = 3
    w.p["node"], w.p["x"], w.p["y"] = 2, 300, 100
    w.fac_coord = (200, 200)    # dist(当前格 → 設施) = 100 ⇒ 12 帧，半程 = 6
    w.tick()
    case("  首拍：12 帧（走特殊支）", w.frames, 11)
    for _ in range(6):
        w.tick()
    case("★ 只有 0x20 的那一支 ⇒ **不动** +0x32..+0x35", w.p["hotel"], 3)
    case("★★ 而是把 0x20 位清掉（+0x15 ← & 0x0f）", w.p["who"], 0)

    # ── H. 走回棋盘支 ─────────────────────────────────────────────
    print("\n[H] 「走回棋盘」支（+0x15 & 0x10）：不选路，从**贴图坐标**走回**当前格**")
    w.clear()
    w.p["who"] = 0x10
    w.p["node"], w.p["last"] = 3, 2      # 逻辑上在 3 号格 (200,160)
    w.p["x"], w.p["y"] = 300, 100        # 贴图还在醫院/綠島大楼那边
    w.adj[3] = [1, 0, 0, 0]
    w.tick()
    case("★ 节点号不变（不选路）", w.p["node"], 3)
    case("  来路不变", w.p["last"], 2)
    case("  占用位也没动", w.occ_bit(3), 0)
    case("  dist = sqrt(100²+60²) = 116.6 ⇒ 特殊支 14 拍", w.frames, 13)
    case("  第 1 拍：300 − 100/14.577 ⇒ 293", w.p["x"], 293)

    # ── I. 被挪过支 ───────────────────────────────────────────────
    print("\n[I] 「被挪过」支（+0x15 & 0x20）：从**当前格**走向 `設施[+0x4a]`")
    w.clear()
    w.p["who"] = 0x20
    w.p["node"], w.p["last"] = 1, 0
    w.p["x"], w.p["y"] = 300, 300        # 贴图已被挪到旅館
    w.p["fac"] = 7
    w.fac_coord = (100, 500)             # 設施 7 在 (100,500)
    w.adj[1] = [2, 0, 0, 0]
    w.tick()
    case("★ 节点号不变（不选路）", w.p["node"], 1)
    case("  dist = sqrt(0² + 400²) = 400 ⇒ 特殊支 50 拍", w.frames, 49)
    case("★ 第 1 拍：accum 从**贴图坐标** 300 出发、每拍加 (设施−当前格)/50 = +8 ⇒ 308",
         w.p["y"], 308)
    case("  x 不动", w.p["x"], 300)

    # ── J. 夢遊计数 ───────────────────────────────────────────────
    print("\n[J] 夢遊（+0x37）⇒ 回合记录 +0x04 在 0..5 循环")
    w.clear()
    w.p["sleepwalk"] = 1
    for want in (1, 2, 3, 4, 5, 0, 1):
        w.tick()
        case(f"夢遊计数 → {want}", w.rec["+4"], want)
    w.clear()
    w.tick()
    case("不夢遊 ⇒ 计数不动", w.rec["+4"], 0)

    # ── K. 动画拍计数（+0x03）────────────────────────────────────
    print("\n[K] 回合记录 +0x03 是「动画拍计数」，到 `[表项+4] >> 3` 就回绕")
    w.clear()
    w.tick()
    case("+0x03 → 1（总拍数 24>>3 = 3）", w.rec["+3"], 1)
    w.tick()
    w.tick()
    case("+0x03 → 3 ⇒ 回绕 0", w.rec["+3"], 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
