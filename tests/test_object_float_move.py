#!/usr/bin/env python3
"""
通道 2 差分测试 #20 · `0x0040fafd(objIdx, fromNode, toNode)` —— **物件起手移动**

规格来源：`gen/db.txt`（本函数 52 条 / 187 字节）+ `docs/systems/tools.md` §6.1
（物件记录 `objects_info` 46×24 的字段表）+ `docs/systems/gods.md`。

```asm
0040fb03  edi = arg1 = objIdx ; if (edi == 0) return
0040fb20  edi -= 1                                     ; 0 基下标
0040fb21  esi = node[from].x（int16）; ebx = node[from].y
0040fb35  edx = node[to].x           ; ecx = node[to].y
0040fb3e  dx = from.x - to.x
0040fb45  fild [esp] / fmul qword [0x46352c]=0.5
0040fb55  fstp [obj*24 + 0x496d18]                     ; ★ +0x10 = dx × 0.5（x 速度）
0040fb63  fild (from.y - to.y) / fmul 0.5
0040fb6c  fstp [obj*24 + 0x496d1c]                     ; ★ +0x14 = dy × 0.5
0040fb76  fild from.x / fadd [+0x496d18]
0040fb80  fstp [obj*24 + 0x496d10]                     ; ★ +0x08 = from.x + 速度x
0040fb8a  fild from.y / fadd [+0x496d1c]
0040fb94  fstp [obj*24 + 0x496d14]                     ; ★ +0x0c = from.y + 速度y
0040fb9b  byte [obj*24 + 0x496d0e] = 0xff              ; ★ +0x06 = 0xFF（计时/存在位）
0040fba3  dl = byte [obj*24 + 0x496d09]                ; +0x01 = 朝向
0040fbaa  byte [obj*24 + 0x496d0f] = dl                ; ★★★ +0x07 ← +0x01
```

★★ **`+0x07` 是本次查清的新字段**：PRD `tools.md` §6.1 的表里它此前写「未定位」，
`gods.md` 也说「可能是方向或动画索引」——实测它就是**朝向的副本**（把 `+0x01`
`sub_00407a8c` 算出的朝向码再存一份给动画用）。

★ 本用例验到的四条：
1. `objIdx == 0` 直接返回（一个字节都不写）；
2. 四个 float（`+0x08/+0x0c/+0x10/+0x14`）按 `距离差 × 0.5` 与 `起点 + 速度` 落位
   —— **含 float32 舍入**（`fstp dword`），本测试按 IEEE-754 单精度逐步复算；
3. `+0x06 = 0xFF`（起手移动的计时初值）；
4. `+0x07` = `+0x01`（朝向副本）。

跑法：cd rich4-spec && .venv/bin/python tests/test_object_float_move.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

START_MOVE = 0x40FAFD

OBJ_BASE, OBJ_STRIDE = 0x496D08, 24
OBJ_FACING, OBJ_FACING2, OBJ_TIMER = 0x01, 0x07, 0x06
OBJ_FX, OBJ_FY, OBJ_VX, OBJ_VY = 0x08, 0x0C, 0x10, 0x14

NODE_TABLE_PTR, NODE_COUNT = 0x498E80, 0x498E9C
NODE_SCRATCH, NODE_STRIDE = 0x600000, 0x28
NODE_X, NODE_Y = 0x00, 0x02

RESULTS = []


def f32(x: float) -> float:
    """IEEE-754 单精度（原版 `fstp dword` 的落点）。"""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<56} 实际 {got_s!s:<18} 期望 {want_s!s}")
    return ok


def node_addr(n):
    return NODE_SCRATCH + n * NODE_STRIDE


class F:
    def __init__(self):
        self.emu = Emu()

    def start(self, obj, from_node, to_node, nodes, facing=3):
        def setup(emu):
            emu.write32(NODE_TABLE_PTR, NODE_SCRATCH)
            emu.write32(NODE_COUNT, len(nodes) + 2)
            for nid, (x, y) in nodes.items():
                a = node_addr(nid)
                emu.write16(a + NODE_X, x & 0xFFFF)
                emu.write16(a + NODE_Y, y & 0xFFFF)
            if obj != 0:
                base = OBJ_BASE + (obj - 1) * OBJ_STRIDE
                emu.write8(base + OBJ_FACING, facing)
                emu.write8(base + OBJ_FACING2, 0)
                emu.write8(base + OBJ_TIMER, 0)
                for off in (OBJ_FX, OBJ_FY, OBJ_VX, OBJ_VY):
                    emu.write32(base + off, 0)

        self.emu.call(START_MOVE, [obj, from_node, to_node], setup=setup)
        e = self.emu
        if obj == 0:
            return None
        base = OBJ_BASE + (obj - 1) * OBJ_STRIDE

        def rf(off):
            return struct.unpack("<f", e.read(base + off, 4))[0]

        return {
            "fx": rf(OBJ_FX),
            "fy": rf(OBJ_FY),
            "vx": rf(OBJ_VX),
            "vy": rf(OBJ_VY),
            "timer": e.read8(base + OBJ_TIMER),
            "facing": e.read8(base + OBJ_FACING),
            "facing2": e.read8(base + OBJ_FACING2),
        }


def main():
    print("差分测试 #20：物件起手移动 0x0040fafd(objIdx, fromNode, toNode)\n")
    f = F()
    nodes = {1: (100, 200), 2: (300, 260), 3: (7, 9), 4: (-40, 16)}

    print("[1] 速度 = (from − to) × 0.5；位置 = from + 速度")
    r = f.start(5, 1, 2, nodes)
    dx, dy = 100 - 300, 200 - 260
    vx, vy = f32(dx * 0.5), f32(dy * 0.5)
    case("+0x10 (vx) = (100−300)×0.5 = −100", r["vx"], vx)
    case("+0x14 (vy) = (200−260)×0.5 = −30", r["vy"], vy)
    case("+0x08 (fx) = 100 + (−100) = 0", r["fx"], f32(100 + vx))
    case("+0x0c (fy) = 200 + (−30) = 170", r["fy"], f32(200 + vy))

    print("\n[2] 反向/负坐标也照同一式子")
    r = f.start(3, 4, 3, nodes)
    dx, dy = -40 - 7, 16 - 9
    vx, vy = f32(dx * 0.5), f32(dy * 0.5)
    case("vx = (−47)×0.5 = −23.5", r["vx"], vx)
    case("vy = 7×0.5 = 3.5", r["vy"], vy)
    case("fx = −40 + (−23.5) = −63.5", r["fx"], f32(-40 + vx))
    case("fy = 16 + 3.5 = 19.5", r["fy"], f32(16 + vy))

    print("\n[3] ★ 计时位与朝向副本")
    r = f.start(5, 1, 2, nodes, facing=3)
    case("+0x06 = 0xFF（起手移动）", r["timer"], 0xFF)
    case("★★ +0x07 = +0x01（朝向副本，此前 PRD 写「未定位」）", r["facing2"], 3)
    r = f.start(5, 1, 2, nodes, facing=7)
    case("   换个朝向再验一次", (r["facing"], r["facing2"]), (7, 7))

    print("\n[4] objIdx == 0 ⇒ 原样返回（一个字节都不写）")
    r = f.start(0, 1, 2, nodes)
    case("返回 None（调用点不读；此处只验没有异常与写入）", r, None)
    base = OBJ_BASE + 0 * OBJ_STRIDE
    case("objects[0] 的 +0x07 仍是 0", f.emu.read8(base + OBJ_FACING2), 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
