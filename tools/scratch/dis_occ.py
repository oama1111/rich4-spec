import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)

SITES = [
    ("读 0x409bc0 (0xffff00)", 0x409bc0),
    ("读 0x409f7c (0xffff00)", 0x409f7c),
    ("写 0x4083a0 (or)", 0x4083a0),
    ("写/清 0x40c1e9-0x40c202", 0x40c202),
    ("写/清 0x40c576-0x40c5a5", 0x40c5a5),
    ("读 0x40c7fe", 0x40c7fe),
    ("写 0x40cc88 (and)", 0x40cc88),
    ("写 0x40cd00 (or)", 0x40cd00),
    ("写 0x40d444 (and)", 0x40d444),
    ("写 0x40e13c (or)", 0x40e13c),
]
# 建立 va -> 指令 的全景索引
lines = {}
for f in dis.funcs:
    fn = dis.funcs[f]
    for ins in fn.insns:
        lines[ins.va] = ins.mnemonic + " " + ins.op_str

for label, va in SITES:
    print(f"\n########## {label}  ({hex(va)}) ##########")
    start = max(v for v in lines if v <= va)
    keys = sorted(k for k in lines if start - 40 <= k <= va + 24)
    for k in keys:
        mark = "  <<<" if k == va else ""
        print(f"  {k:08x}  {lines[k]}{mark}")
