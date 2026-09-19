"""探针：0x428ec5（定价/落档）—— exe vs PRD 模型 vs 复刻模型。"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from emulate import Emu  # noqa: E402

PRICE = 0x428EC5


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def from_bits(b):
    return struct.unpack("<f", struct.pack("<I", b & 0xFFFFFFFF))[0]


def tick_of(raw):
    if raw < 5.0:
        return 0.01
    if raw < 15.0:
        return 0.05
    if raw < 50.0:
        return 0.1
    if raw < 150.0:
        return 0.5
    return 1.0


def model(open_, pct, fround_rem):
    raw = f32((pct + 100.0) / 100.0 * open_)
    tick = tick_of(raw)
    diff = f32(raw - open_) if pct > 0 else f32(open_ - raw)
    rem = math.fmod(diff, tick)
    if fround_rem:
        rem = f32(rem)
    res = f32(raw - rem) if pct > 0 else f32(raw + rem)
    if bits(res) < 0x3F800000:
        res = 1.0
    elif res > 9999.0:
        res = 9999.0
    return res


def main():
    emu = Emu()
    opens = [1, 3, 7, 12, 20, 40, 80, 120, 200, 500, 1200, 5000, 9999]
    pcts = [-10, -7, -3.5, -1, -0.5, 0, 0.5, 1, 3.5, 7, 10]
    bad_orig = []
    bad_rem = []
    n = 0
    for o in opens:
        for p in pcts:
            got = from_bits(emu.call(PRICE, [bits(f32(o)), bits(f32(p))])["eax"])
            mo = model(o, p, False)
            mr = model(o, p, True)
            n += 1
            if bits(got) != bits(mo):
                bad_orig.append((o, p, got, mo))
            if bits(got) != bits(mr):
                bad_rem.append((o, p, got, mr))
    print(f"用例 {n}：PRD 模型不符 {len(bad_orig)}；复刻模型不符 {len(bad_rem)}")
    for tag, bad in (("PRD", bad_orig), ("复刻", bad_rem)):
        for o, p, got, want in bad[:8]:
            print(f"  [{tag}] open={o} pct={p}: exe={got!r} model={want!r} "
                  f"bits {bits(got):08x} vs {bits(want):08x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
