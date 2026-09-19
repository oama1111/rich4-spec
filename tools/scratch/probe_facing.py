"""探针：0x454fb4(dx, dy) 的朝向真值表 + 0x407a8c(a, b) 的参数序。

跑法：.venv/bin/python tools/scratch/probe_facing.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

DIRFN = 0x454FB4
NODEFN = 0x407A8C
NODE_TABLE_PTR = 0x498E80
NODE_STRIDE = 0x28
NODES = SCRATCH_BASE + 0x1000


def main():
    emu = Emu()

    print("=" * 72)
    print("A) 0x454fb4(dx, dy) —— 8 个主方向")
    # 屏幕坐标：x 向右、y 向下。取 100 像素步长
    for name, dx, dy in [
        ("(+100,   0)", 100, 0), ("(+100,+100)", 100, 100), ("(  0,+100)", 0, 100),
        ("(-100,+100)", -100, 100), ("(-100,   0)", -100, 0), ("(-100,-100)", -100, -100),
        ("(  0,-100)", 0, -100), ("(+100,-100)", 100, -100),
    ]:
        r = emu.call(DIRFN, [dx, dy])
        print(f"   {name} → {r['eax'] & 0xFF}")

    print("\nB) 0x454fb4 —— 非等距（看是否按角度量化）")
    for name, dx, dy in [
        ("(+200, +10)", 200, 10), ("(+200, +40)", 200, 40), ("(+200, +90)", 200, 90),
        ("(+200,+200)", 200, 200), ("(+90, +200)", 90, 200), ("(+40, +200)", 40, 200),
        ("(+10, +200)", 10, 200), ("( 0, 0)", 0, 0),
    ]:
        r = emu.call(DIRFN, [dx, dy])
        print(f"   {name} → {r['eax'] & 0xFF}")

    print("\nC) 0x454fb4 —— 8 个扇区边界（45° 两侧 ±1°）")
    import math
    for deg in (0, 22.4, 22.6, 67.4, 67.6, 112.4, 112.6, 157.4, 157.6,
                202.4, 202.6, 247.4, 247.6, 292.4, 292.6, 337.4, 337.6):
        rad = math.radians(deg)
        dx = round(1000 * math.cos(rad))
        dy = round(1000 * math.sin(rad))
        r = emu.call(DIRFN, [dx, dy])
        print(f"   {deg:6.1f}° (dx={dx:5d}, dy={dy:5d}) → {r['eax'] & 0xFF}")

    print("\n" + "=" * 72)
    print("D) 0x407a8c(a, b) —— 参数序（节点坐标放在 nodeId 直接索引的表里）")

    def setup(e):
        e.write32(NODE_TABLE_PTR, NODES)
        # node 1 = (100,100)；node 2 = (200,100) 在它**右**边
        e.write16(NODES + 1 * NODE_STRIDE + 0, 100)
        e.write16(NODES + 1 * NODE_STRIDE + 2, 100)
        e.write16(NODES + 2 * NODE_STRIDE + 0, 200)
        e.write16(NODES + 2 * NODE_STRIDE + 2, 100)

    for a, b in [(1, 2), (2, 1)]:
        r = emu.call(NODEFN, [a, b], setup=setup)
        print(f"   0x407a8c({a}, {b}) → {r['eax'] & 0xFF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
