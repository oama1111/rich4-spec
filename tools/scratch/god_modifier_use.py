#!/usr/bin/env python3
"""列出神明三项修正（player +0x44/0x46/0x48）在每个读点附近的用法。"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rich4dis as R  # noqa: E402

img = R.Image(); dis = R.Disassembler(img); dis.traverse()
TGT = {0x496BAC: "+0x44 misfortune", 0x496BAE: "+0x46 fortune", 0x496BB0: "+0x48 luck"}
for f in sorted(dis.funcs.values(), key=lambda x: x.va):
    hits = [x for x in f.insns if x.mem_addr in TGT]
    if not hits:
        continue
    print(f"\n===== 函数 0x{f.va:06x}（{len(f.insns)} 条）")
    idx = {x.va: i for i, x in enumerate(f.insns)}
    for h in hits:
        i = idx[h.va]
        print(f"  --- {TGT[h.mem_addr]}  @0x{h.va:08x}")
        for j in range(max(0, i - 6), min(len(f.insns), i + 8)):
            x = f.insns[j]
            mark = " <<<" if x.va == h.va else ""
            print(f"      {x.va:08x}  {x.mnemonic:<8} {x.op_str}{mark}")
