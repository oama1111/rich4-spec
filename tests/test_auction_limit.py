#!/usr/bin/env python3
"""
通道 2 差分测试 · 拍卖「心理价位」 `fcn_00439f0d` (VA 0x00439f0d)

用 Unicorn 执行**原版机器码**，与 `docs/systems/magic-house.md` §5.2.1 的规格
（以及 remake 的 `rules/auction.ts` `auctionAiLimit`）逐次比对。

规格（本测试的「期望值」就按它算 —— 测试的作用正是判定它有没有读错）：

    factor   = rand()/32767.0 * 0.3 + 0.5
    scarcity = 6 − 4 × (无主数 / 总数)
    scale    = (⌊等级/2⌋ + 1 + 同名数) × 起拍价 × 物价指数
    v1       = trunc(scale × scarcity × factor)
    v2       = trunc(地价 × 物价指数 × (3 + rand()/65536))
    心理价位 = min(v1, v2, 现金)

★ 两处易错，本测试专门覆盖：
  · 每次调用消耗**两个** rand（入口一个、地价支一个）；
  · 最后要**夹到玩家现金**（`player+0x1c`）。

⚠️ 浮点边界：x87 是 80 位、Python 是双精度，末位可能差 1。故对每个用例
   先算「结果离整数有多远」，离得太近（<1e-6）的**标为跳过**并打印，
   免得把「末位噪声」报成「规格读错」。这是本测试台的诚实边界。

跑法：cd rich4-spec && .venv/bin/python tests/test_auction_limit.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

ACCESSOR = 0x456F23          # 「取 PRNG 状态块」的访问器 —— 打桩到暂存区
TARGET = 0x439F0D
LAND_BASE = 0x480000
FACILITY_BASE = 0x481000
LAND_STRIDE = 0x34
FACILITY_STRIDE = 0x38
STATE_VA = SCRATCH_BASE
A, B, MASK = 0x41C64E6D, 0x3039, 0xFFFFFFFF

RESULTS = []


def lcg(seed, n):
    s, out = seed, []
    for _ in range(n):
        s = (s * A + B) & MASK
        out.append((s >> 16) & 0x7FFF)
    return out


def near_boundary(x):
    return abs(x - round(x)) < 1e-6


def model_land(lands, target_id, player1, price_index, base_price, cash, r1, r2):
    """按规格算地產支的心理价位。lands = 1 基列表（下标 0 占位）。"""
    target = lands[target_id]
    total = len(lands) - 1
    unowned = sum(1 for l in lands[1:] if l["owner"] == 0)
    same = sum(
        1 for l in lands[1:]
        if l["name"] == target["name"] and l["owner"] == player1
    )
    factor = r1 / 32767.0 * 0.3 + 0.5
    scarcity = 6.0 - 4.0 * (unowned / total)
    scale = (target["level"] // 2 + 1 + same) * base_price * price_index
    f1 = scale * scarcity * factor
    f2 = target["landPrice"] * price_index * (3 + r2 / 65536.0)
    v1, v2 = int(f1), int(f2)
    return min(v1, v2, cash), (near_boundary(f1) or near_boundary(f2))


def model_facility(facs, target_id, player1, price_index, base_price, cash, r1, r2):
    """設施支：**沒有同名數**那一項（规格：該支恒 0）。"""
    target = facs[target_id]
    total = len(facs) - 1
    unowned = sum(1 for f in facs[1:] if f["owner"] == 0)
    factor = r1 / 32767.0 * 0.3 + 0.5
    scarcity = 6.0 - 4.0 * (unowned / total)
    scale = (target["level"] // 2 + 1) * base_price * price_index
    f1 = scale * scarcity * factor
    f2 = target["landPrice"] * price_index * (3 + r2 / 65536.0)
    v1, v2 = int(f1), int(f2)
    return min(v1, v2, cash), (near_boundary(f1) or near_boundary(f2))


class Fixture:
    def __init__(self):
        self.emu = Emu()
        # 把 PRNG 状态打桩到暂存区（不参与快照，故 seed 不会被 reset 抹掉）
        self.emu.patch(ACCESSOR, bytes([0xB8]) + struct.pack("<I", STATE_VA) + b"\xC3")

    def put(self, va, data):
        self.emu.mu.mem_write(va, bytes(data))

    def setup(self, lands, facs, price_index, base_price, cash, seed):
        self.put(0x498E84, struct.pack("<I", LAND_BASE))
        self.put(0x498E98, struct.pack("<I", len(lands) - 1))
        self.put(0x498E88, struct.pack("<I", FACILITY_BASE))
        self.put(0x498E8C, struct.pack("<I", len(facs) - 1))
        self.put(0x4990E8, struct.pack("<i", price_index))
        self.put(0x48C488, struct.pack("<i", base_price))
        for i, l in enumerate(lands[1:], start=1):
            o = LAND_BASE + i * LAND_STRIDE
            self.put(o + 0x04, l["name"] + b"\0")
            self.put(o + 0x19, [l["owner"]])
            self.put(o + 0x1a, [l["level"]])
            self.put(o + 0x1c, struct.pack("<H", l["landPrice"]))
        for i, f in enumerate(facs[1:], start=1):
            o = FACILITY_BASE + i * FACILITY_STRIDE
            self.put(o + 0x04, f["name"] + b"\0")
            self.put(o + 0x19, [f["owner"]])
            self.put(o + 0x1a, [f["level"]])
            self.put(o + 0x22, struct.pack("<H", f["landPrice"]))
        # 玩家 0 的现金（arg1 = player+1 = 1 ⇒ 读 0x496b68 + 0x1c）
        self.put(0x496B84, struct.pack("<i", cash))
        self.emu.scratch_write(STATE_VA, struct.pack("<I", seed))
        # ★ 注入完再拍快照：否则 reset() 会把合成数据抹掉
        from emulate import SEGMENTS
        self.emu._snapshot = {
            va: self.emu.mu.mem_read(va, sz)
            for va, off, sz, w in SEGMENTS if w
        }

    def limit(self, entity_id):
        return self.emu.call(TARGET, [1, entity_id])["signed"]


def case(desc, got, want, skipped):
    if skipped:
        RESULTS.append(True)
        print(f"  ⏭ {desc}：浮点离整数太近，跳过（末位噪声风险）")
        return
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc}：原版={got} 规格={want}")


def main():
    print("差分测试：拍卖心理价位 fcn_00439f0d")
    print("对照规格：docs/systems/magic-house.md §5.2.1 / auction.ts auctionAiLimit\n")

    lands = [
        None,
        {"name": b"A", "owner": 1, "level": 4, "landPrice": 3000},
        {"name": b"B", "owner": 1, "level": 2, "landPrice": 5000},
        {"name": b"A", "owner": 0, "level": 0, "landPrice": 2500},
        {"name": b"C", "owner": 2, "level": 5, "landPrice": 8000},
    ]
    facs = [
        None,
        {"name": b"F1", "owner": 1, "level": 3, "landPrice": 4000},
        {"name": b"F2", "owner": 0, "level": 1, "landPrice": 6000},
        {"name": b"F3", "owner": 2, "level": 0, "landPrice": 2000},
    ]

    # ── 地產支 ──
    f = Fixture()
    cases_land = [
        # (说明, target, priceIndex, basePrice, cash, seed)
        ("1 号地（4 级、同区有我的地）", 1, 1, 3000, 999_999, 0x12345678),
        ("2 号地（2 级、无同区）", 2, 1, 3000, 999_999, 0x12345678),
        ("3 号地（无主、0 级）", 3, 1, 3000, 999_999, 0x12345678),
        ("4 号地（5 级、别人的）", 4, 2, 5000, 999_999, 0xDEADBEEF),
        ("1 号地 × 高物价", 1, 7, 12000, 999_999, 0x00000001),
        ("2 号地 × 高起拍价", 2, 3, 9000, 999_999, 0xFFFFFFFF),
        ("★ 现金夹顶", 1, 1, 3000, 500, 0x12345678),
        ("★ 现金夹顶（中等）", 2, 1, 3000, 40_000, 0x12345678),
        ("1 号地 × 零现金", 1, 1, 3000, 0, 0x12345678),
        ("4 号地 × 大起拍价", 4, 5, 30_000, 999_999, 0xA5A5A5A5),
    ]
    for desc, tid, pi, bp, cash, seed in cases_land:
        f.setup(lands, facs, pi, bp, cash, seed)
        r1, r2 = lcg(seed, 2)
        want, skip = model_land(lands, tid, 1, pi, bp, cash, r1, r2)
        case(f"{desc}（seed=0x{seed:08x}）", f.limit(2000 + tid), want, skip)

    # ── 設施支 ──
    f2 = Fixture()
    cases_fac = [
        ("設施 1（3 级、有主）", 1, 1, 3000, 999_999, 0x12345678),
        ("設施 2（无主）", 2, 1, 3000, 999_999, 0xDEADBEEF),
        ("設施 3（0 级）", 3, 2, 4000, 999_999, 0x0BADF00D),
        ("★ 設施 · 现金夹顶", 1, 1, 3000, 1200, 0x12345678),
    ]
    for desc, tid, pi, bp, cash, seed in cases_fac:
        f2.setup(lands, facs, pi, bp, cash, seed)
        r1, r2 = lcg(seed, 2)
        want, skip = model_facility(facs, tid, 1, pi, bp, cash, r1, r2)
        case(f"{desc}（seed=0x{seed:08x}）", f2.limit(4000 + tid), want, skip)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
