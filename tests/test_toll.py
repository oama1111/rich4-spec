#!/usr/bin/env python3
"""
通道 2 差分测试 · calculate_land_toll (VA 0x419744)

用 Unicorn 执行**原版机器码**，与 `docs/systems/land-rent.md` 的规格逐条比对。

每个用例的"期望值"都是从规格的人工读数算出来的 —— 本测试的作用就是
**判定那份规格有没有读错**。这是本项目最重要的验证手段：它把"照汇编手写
可能写错"变成"与真值逐次比对"。

跑法：cd rich4-spec && .venv/bin/python tests/test_toll.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SEGMENTS  # noqa: E402

LAND_BASE = 0x480000
RENTS = [100, 200, 400, 800, 1600, 3200]   # 按等级租金表 @0x20，6 项 uint16

RESULTS = []


class Fixture:
    """构造合成地产数据并调用原版函数。

    ⚠️ 每次改动 DGROUP 后必须调用 `setup()` 重拍快照，否则 `Emu.call()` 的
       `reset()` 会把注入的数据抹掉 —— 初版就踩了这个坑。
    """

    def __init__(self):
        self.emu = Emu()

    def put(self, va, data):
        self.emu.mu.mem_write(va, bytes(data))

    def land(self, idx, typ, owner, level, name, rents=RENTS):
        b = LAND_BASE + idx * 0x34
        self.put(b + 0x18, [typ])          # type：0=住宅，非 0=商業用地
        self.put(b + 0x19, [owner])
        self.put(b + 0x1a, [level])
        self.put(b + 0x20, struct.pack("<6H", *rents))
        self.put(b + 0x04, name + b"\0")

    def setup(self, num_lands, price_index):
        # NOTE: 必须重拍快照，否则 reset() 会抹掉注入的数据
        self.put(0x498E84, struct.pack("<I", LAND_BASE))   # land_info_ptr
        self.put(0x498E98, struct.pack("<I", num_lands))   # num_lands
        self.put(0x4990E8, struct.pack("<i", price_index))  # price_index
        self.emu._snapshot = {va: self.emu.mu.mem_read(va, sz)
                              for va, off, sz, w in SEGMENTS if w}

    def toll(self, player, name_va):
        return self.emu.call(0x419744, [player, name_va])["signed"]


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<44} 实际 {got:<8} 期望 {want}")
    return ok


def main():
    print("差分测试：calculate_land_toll(VA 0x419744)")
    print("对照规格：docs/systems/land-rent.md\n")

    f = Fixture()
    f.land(0, 0, 0, 0, b"X")
    f.land(1, 0, 0, 1, b"AAA")
    f.land(2, 0, 0, 2, b"AAA")
    f.setup(2, 3)
    name_va = LAND_BASE + 0x34 + 0x04        # land[1].name 的地址

    print("[规格] 住宅 + 同名 + 同主 → 累加 租金表[level]，再乘 price_index")
    case("两块同名住宅 level1+level2，price_index=3",
         f.toll(0, name_va), (RENTS[1] + RENTS[2]) * 3)

    print("\n[规格] 分支 A 只算 type==0（住宅）；type!=0 归商業用地，不计入 A")
    f.land(2, 1, 0, 2, b"AAA")
    f.setup(2, 3)
    case("l[2] 改商業用地后走 name 分支", f.toll(0, name_va), RENTS[1] * 3)

    print("\n[规格] 分支 B（name=NULL）只算 type!=0（商業用地），固定 2000/块")
    case("name=NULL，1 块商業用地", f.toll(0, 0), 2000 * 3)

    print("\n[规格] owner 必须等于 player，否则跳过")
    f.put(LAND_BASE + 0x34 * 2 + 0x19, [3])
    f.setup(2, 3)
    case("l[2].owner=3 而查 player=0", f.toll(0, name_va), RENTS[1] * 3)

    print("\n[规格] 返回值 = 累加值 × price_index（32 位有符号 imul）")
    f.setup(2, 1)          # setup 内部会写 price_index 并重拍快照
    case("price_index=1", f.toll(0, name_va), RENTS[1] * 1)

    print("\n[边界] num_lands=0 → 返回 0")
    f.setup(0, 100)
    case("无地产时返回 0", f.toll(0, name_va), 0)

    print("\n[边界] 商業用地分支不比较名字")
    f.land(1, 1, 0, 1, b"ZZZ")
    f.setup(1, 1)
    case("name=NULL 且 type!=0 → 2000", f.toll(0, 0), 2000)

    print("\n[边界] 同主但名字不同 → 不计入")
    f.land(1, 0, 0, 1, b"AAA")
    f.land(2, 0, 0, 2, b"BBB")
    f.setup(2, 1)
    case("名字不同只算一块", f.toll(0, name_va), RENTS[1])

    print("\n[规格] owner 是 1 基：函数内部直接相等比较，不做 ±1 调整")
    # 用同一块地分别以 owner=0/1 与第1参 0/1/2 交叉验证
    for owner_val, arg, want in ((0, 0, RENTS[1]), (0, 1, 0),
                                 (1, 1, RENTS[1]), (1, 0, 0), (1, 2, 0)):
        f.land(1, 0, owner_val, 1, b"AAA")
        f.setup(1, 1)
        case(f"owner={owner_val} 且第1参={arg}", f.toll(arg, name_va), want)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
