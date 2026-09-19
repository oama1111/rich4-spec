"""探针 2：0x428ec5 —— 用**随机真实输入**（open/pct 都是 f32）比较多套 fmod 模型。"""
import math
import os
import random
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


def model(open_, pct, kind):
    raw = f32((pct + 100.0) / 100.0 * open_)
    tick = tick_of(raw)
    diff = f32(raw - open_) if pct > 0 else f32(open_ - raw)
    if kind == "c":
        rem = math.fmod(diff, tick)
    elif kind == "heuristic":
        q = diff / tick
        n = round(q)
        near = abs(q - n) < 1e-6 * max(1.0, abs(q))
        if near and abs(n) >= 4:
            rem = diff - n * tick
        else:
            rem = diff - math.trunc(q) * tick
    elif kind == "trunc":
        rem = diff - math.trunc(diff / tick) * tick
    res = f32(raw - rem) if pct > 0 else f32(raw + rem)
    if bits(res) < 0x3F800000:
        res = 1.0
    elif res > 9999.0:
        res = 9999.0
    return res


def main():
    random.seed(20260919)
    emu = Emu()
    kinds = ["c", "trunc", "heuristic"]
    bad = {k: [] for k in kinds}
    n = 0
    for _ in range(1200):
        o = f32(random.choice([1, 2, 3, 5, 10, 20, 25, 30, 40, 50, 75, 100, 150,
                               200, 500, 1000, 3000]) + random.random() * 10)
        p = f32(random.uniform(-10, 10))
        got = from_bits(emu.call(PRICE, [bits(o), bits(p)])["eax"])
        n += 1
        for k in kinds:
            if bits(got) != bits(model(o, p, k)):
                bad[k].append((o, p, got, model(o, p, k)))
    for k in kinds:
        print(f"{k:10} 不符 {len(bad[k])}/{n}")
        for o, p, got, want in bad[k][:5]:
            print(f"    open={o!r} pct={p!r} exe={got!r} model={want!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
