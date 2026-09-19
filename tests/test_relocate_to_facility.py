#!/usr/bin/env python3
"""
通道 2 差分测试 #25 · **把玩家挪到設施位置** `0x0040d5a5`（281 字节）

全 exe **唯一调用点** `0x0041a85e`（旅館落点那一支）：住店的玩家被挪到
**旅館設施的坐标**上（不是格子的坐标）—— 与关押那一段同源的"贴图位置 ≠ 所在格"。

## 反汇编（A 级）

```asm
; 签名：0x40d5a5(player, arg_fromNode /*[esp+0x14]*/, facilityIdx /*[esp+0x18]*/)
0040d5a8  cl = player ; eax = 0x100 << cl ; ecx = ~eax          ; 占用位清除掩码
0040d5be  dx = player.nodeId
0040d5d2  and dword [node[nodeId] + 0x24], ecx                  ; ★ 清旧格的占用位
0040d5d6  eax = facilityIdx
0040d5da..0x40d5e4  eax = idx*8 → *8 − idx*8 … = idx * 0x38
0040d5e4  eax = [0x498e88] + idx*0x38                           ; ★ 設施表
0040d5ec  edx = movsx word [eax]        ; 設施 x
0040d5ef  eax = movsx word [eax + 2]    ; 設施 y
0040d5f5  cx = player.nodeId
0040d5fc  cmp ecx, [esp+0x14]  ; nodeId == arg_fromNode ?
0040d600  jne 0x40d650
0040d606  cmp player, [0x49910c]        ; 且他就是当前玩家 ?
0040d60c  jne 0x40d650
; ── 支 A（当前玩家 + 还在原节点上）：只立标记、算朝向，**不动坐标** ──
0040d60e  or  byte [player + 0x15], 0x20      ; ★ WHO_PLAYS_RELOCATED
0040d615  cl = byte [player + 0x10]           ; 朝向后备 ← 当前朝向
0040d61b  byte [player + 0x1b] = cl
0040d623  ecx = player.x ; edx -= ecx          ; dx = 設施x − 玩家x
0040d630  edx = player.y ; eax -= edx          ; dy = 設施y − 玩家y
0040d63b  call 0x454fb4(dx, dy)                ; 朝向 = atan2 表
0040d643  byte [player + 0x10] = al
0040d649  call 0x40dd1f                        ; ★ 真正的"挪过去"（动画/走位）在它里面
0040d64e  jmp 0x40d6aa
; ── 支 B（别人 / 已经不在原节点上）：**原地瞬移** ──
0040d657  word [player + 0x08] = dx            ; ★ x/y ← **設施坐标**
0040d65e  word [player + 0x0a] = ax
0040d66c  dx = players[[0x49910c]].nodeId      ; ★ nodeId ← **当前玩家**的节点
0040d673  word [player + 0x0c] = dx
0040d67a  dx = players[[0x49910c]].lastNodeId
0040d681  word [player + 0x0e] = dx
0040d688  al = players[[0x49910c]].+0x10
0040d68e  byte [player + 0x1b] = al            ; 朝向后备 ← 当前玩家的朝向
0040d697  call 0x40b93b(player)                ; 重画
0040d6a2  call 0x40fc00(player)                ; ★ 跟班物件同步所在格
; ── 公共尾 ──
0040d6af  edx = [esp+0x18]                     ; facilityIdx
0040d6b3  word [player + 0x4a] = dx            ; ★ +0x4a = 本次目标（行走函数 0x40c101 读它）
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x454fb4` | 朝向 = atan2 表 | **记录 (dx, dy) 并返回固定 7** —— 本测试只验"传进去的是什么" |
| `0x40dd1f` | 真正的挪动（动画/走位） | 记调用次数后 `ret` |
| `0x40b93b` | 重画该玩家 | 记实参后 `ret` |
| `0x40fc00` | 跟班物件同步所在格 | 记实参后 `ret`（另有 `test_god_follow.py` 专测它）|

跑法：cd rich4-spec && .venv/bin/python tests/test_relocate_to_facility.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

RELOCATE = 0x40D5A5

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE, P_LAST = 0x08, 0x0A, 0x0C, 0x0E
P_FACING, P_WHO, P_BACKUP, P_TARGET = 0x10, 0x15, 0x1B, 0x4A
CURRENT = 0x49910C
FACILITY_TABLE_PTR = 0x498E88
NODE_TABLE_PTR = 0x498E80

FACILITY_X, FACILITY_Y = 1500, 900
OLD_NODE = 40

STUB_ATAN = 0x454FB4
STUB_MOVE = 0x40DD1F
STUB_REDRAW = 0x40B93B
STUB_ESCORT = 0x40FC00

ATAN_DX, ATAN_DY, ATAN_COUNT = SCRATCH_BASE + 0x400, SCRATCH_BASE + 0x404, SCRATCH_BASE + 0x408
MOVE_COUNT = SCRATCH_BASE + 0x410
REDRAW_ARG = SCRATCH_BASE + 0x418
ESCORT_ARG = SCRATCH_BASE + 0x41C

FIXED_FACING = 7
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # atan2 桩：记录两个实参，返回固定朝向
        aten = (
            b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", ATAN_DX)
            + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", ATAN_DY)
            + b"\xFF\x05" + struct.pack("<I", ATAN_COUNT)
            + b"\xB8" + struct.pack("<I", FIXED_FACING)      # mov eax, 7
            + b"\xC3"
        )
        self.emu.patch(STUB_ATAN, aten)
        self.emu.patch(STUB_MOVE, b"\xFF\x05" + struct.pack("<I", MOVE_COUNT) + b"\xC3")
        self.emu.patch(
            STUB_REDRAW,
            b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", REDRAW_ARG) + b"\xC3",
        )
        self.emu.patch(
            STUB_ESCORT,
            b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", ESCORT_ARG) + b"\xC3",
        )

    def run(self, idx, from_node, facility_idx, *, cur, node=OLD_NODE, facing=3,
            x=100, y=200, cur_node=55, cur_last=54, cur_facing=5):
        def setup(emu):
            emu.write32(CURRENT, cur)
            emu.write32(FACILITY_TABLE_PTR, SCRATCH_BASE + 0x2000)
            emu.write32(NODE_TABLE_PTR, SCRATCH_BASE + 0x1000)
            fbase = SCRATCH_BASE + 0x2000 + facility_idx * 0x38
            emu.write16(fbase + 0x00, FACILITY_X)
            emu.write16(fbase + 0x02, FACILITY_Y)
            nbase = SCRATCH_BASE + 0x1000 + node * 0x28  # 表按 nodeId 直接索引
            emu.write(nbase + 0x24, b"\xff\xff\xff\xff")  # 全 1，好看出哪一位被清
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write16(base + P_X, x)
            emu.write16(base + P_Y, y)
            emu.write16(base + P_NODE, node)
            emu.write16(base + P_LAST, 7)
            emu.write8(base + P_FACING, facing)
            emu.write8(base + P_WHO, 0x42)
            emu.write8(base + P_BACKUP, 0)
            emu.write16(base + P_TARGET, 0)
            # ⚠️ 当前玩家与目标玩家可能是**同一个人** —— 那时不能覆盖他的 nodeId/x/y
            #   （写串了会让支 A 的两个前提凭空失效，本测试第一版就踩了）
            if cur != idx:
                cbase = PLAYER_BASE + cur * PLAYER_STRIDE
                emu.write16(cbase + P_NODE, cur_node)
                emu.write16(cbase + P_LAST, cur_last)
                emu.write8(cbase + P_FACING, cur_facing)
            for slot in (ATAN_DX, ATAN_DY, ATAN_COUNT, MOVE_COUNT, REDRAW_ARG, ESCORT_ARG):
                emu.write32(slot, 0)

        self.emu.call(RELOCATE, [idx, from_node, facility_idx], setup=setup)
        e = self.emu
        base = PLAYER_BASE + idx * PLAYER_STRIDE
        return {
            "x": e.read16(base + P_X),
            "y": e.read16(base + P_Y),
            "node": e.read16(base + P_NODE),
            "last": e.read16(base + P_LAST),
            "facing": e.read8(base + P_FACING),
            "who": e.read8(base + P_WHO),
            "backup": e.read8(base + P_BACKUP),
            "target": e.read16(base + P_TARGET),
            "mask": e.readu32(SCRATCH_BASE + 0x1000 + OLD_NODE * 0x28 + 0x24),
            "atan_dx": e.read32(ATAN_DX),
            "atan_dy": e.read32(ATAN_DY),
            "atan_n": e.read32(ATAN_COUNT),
            "move_n": e.read32(MOVE_COUNT),
            "redraw": e.read32(REDRAW_ARG),
            "escort": e.read32(ESCORT_ARG),
        }


def main():
    print("差分测试 #25：把玩家挪到設施位置 —— 0x40d5a5\n")
    f = F()

    print("[1] 支 A：当前玩家 + nodeId == 原节点 ⇒ 只立标记、算朝向，**不动坐标**")
    s = f.run(1, from_node=OLD_NODE, facility_idx=3, cur=1, x=100, y=200, facing=3)
    case("置 [+0x15] |= 0x20（WHO_PLAYS_RELOCATED）", s["who"], 0x42 | 0x20)
    case("朝向后备 +0x1b ← 原 +0x10", s["backup"], 3)
    case("★ 朝向 = atan2(設施x − 玩家x, 設施y − 玩家y)",
         (s["atan_dx"], s["atan_dy"]), (FACILITY_X - 100, FACILITY_Y - 200))
    case("   +0x10 ← 表函数的返回值（桩给 7）", s["facing"], FIXED_FACING)
    case("★★ x/y **不变**（真正的挪动在 0x40dd1f 里）", (s["x"], s["y"]), (100, 200))
    case("   nodeId / lastNodeId 也不变", (s["node"], s["last"]), (OLD_NODE, 7))
    case("   ★ 调了 0x40dd1f 一次", s["move_n"], 1)
    case("   没走支 B 的 0x40b93b / 0x40fc00", (s["redraw"], s["escort"]), (0, 0))
    case("公共尾：+0x4a ← facilityIdx", s["target"], 3)

    print("\n[2] 支 B：不是当前玩家（或已离开原节点）⇒ **原地瞬移**")
    s = f.run(1, from_node=OLD_NODE, facility_idx=3, cur=0, x=100, y=200, facing=3)
    case("★ x/y ← **設施坐标**（不是格子坐标）", (s["x"], s["y"]), (FACILITY_X, FACILITY_Y))
    case("★ nodeId/lastNodeId ← **当前玩家**的（55/54）", (s["node"], s["last"]), (55, 54))
    case("朝向后备 ← 当前玩家的朝向", s["backup"], 5)
    case("★ 不置 0x20", s["who"] & 0x20, 0)
    case("   朝向 +0x10 不变（没调 atan2）", (s["facing"], s["atan_n"]), (3, 0))
    case("   没调 0x40dd1f", s["move_n"], 0)
    case("★ 调了 0x40b93b(player) 与 0x40fc00(player)", (s["redraw"], s["escort"]), (1, 1))
    case("公共尾：+0x4a ← facilityIdx", s["target"], 3)

    print("\n[3] 支 A 的**两个**前提缺一不可")
    s = f.run(1, from_node=OLD_NODE + 1, facility_idx=3, cur=1)
    # 这一例里当前玩家就是他自己 ⇒ 支 B 的"抄当前玩家"抄到的还是自己的节点
    case("nodeId != 原节点 ⇒ 走支 B（瞬移）", (s["x"], s["node"]), (FACILITY_X, OLD_NODE))
    s = f.run(1, from_node=OLD_NODE, facility_idx=3, cur=0)
    case("不是当前玩家 ⇒ 走支 B（瞬移）", (s["x"], s["node"]), (FACILITY_X, 55))
    s = f.run(0, from_node=OLD_NODE, facility_idx=3, cur=0)
    case("同一位玩家当当前玩家且 nodeId 命中 ⇒ 支 A", (s["x"], s["who"] & 0x20), (100, 0x20))

    print("\n[4] 两支都做的一件事：清**旧格**的占用位")
    s = f.run(1, from_node=OLD_NODE, facility_idx=3, cur=1)
    case("支 A：idx=1 ⇒ node[nodeId].+0x24 清 bit9", s["mask"], 0xFFFFFDFF)
    s = f.run(2, from_node=OLD_NODE, facility_idx=3, cur=1)
    case("支 B（idx=2）⇒ 清 bit10", s["mask"], 0xFFFFFBFF)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
