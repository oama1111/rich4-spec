import sys
sys.path.insert(0, 'tools')
from emulate import Emu, SCRATCH_BASE  # noqa: E402

DISPATCH = 0x431842
LAND = SCRATCH_BASE + 0x1000


def run(kind, lands=(), facilities=(), present=None, players=4, tag=''):
    e = Emu()

    def setup(x):
        x.write32(0x499114, players)
        pres = [1] * 4 if present is None else present
        for p in range(4):
            x.write8(0x496B68 + p * 0x68 + 0x15, pres[p])
        x.write32(0x498E84, LAND)
        x.write32(0x498E98, len(lands))
        x.write32(0x498E88, SCRATCH_BASE + 0x8000)
        x.write32(0x498E8C, len(facilities))
        for i, (own, lv) in enumerate(lands):
            a = LAND + i * 0x34
            x.write8(a + 0x19, own)
            x.write8(a + 0x1a, lv)
        for i, (own, lv) in enumerate(facilities):
            a = SCRATCH_BASE + 0x8000 + i * 0x38
            x.write8(a + 0x19, own)
            x.write8(a + 0x1a, lv)
        for i in range(8):
            x.write8(0x48C380 + i, 0xEE)
    r = e.call(DISPATCH, [kind, 0], setup=setup, timeout_insns=200000)
    arr = list(e.read(0x48C380, 8))
    print("%-34s kind=%d -> eax=%d arr=%s" % (tag, kind, r['eax'], arr[:4]))
    return r['eax'], arr


print("== 单块地：owner=1，等级分别 0/1/5 ==")
for lv in (0, 1, 5):
    run(1, lands=[(1, lv)], tag='idx1 lv=%d' % lv)
    run(2, lands=[(1, lv)], tag='idx2 lv=%d' % lv)

print("== 单块地：owner=2 ==")
run(1, lands=[(0, 0), (2, 0)], tag='idx1 P2 lv=0')
run(2, lands=[(0, 0), (2, 3)], tag='idx2 P2 lv=3')

print("== 平手 10 次（idx 1，两人各 1 块）==")
res = {}
for _ in range(10):
    _, arr = run(1, lands=[(1, 0), (2, 0)], tag='tie')
    key = tuple(arr[:3])
    res[key] = res.get(key, 0) + 1
print("   分布:", res)
