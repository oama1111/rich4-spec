#!/usr/bin/env python3
"""Full-traversal xref by instruction: python3 gx.py 0x496ba3 0x496b80 ...
Shows every instruction (in a real traversed function) whose memory operand is the given absolute VA.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False, include_orphans=True)

targets = {int(a,16) for a in sys.argv[1:]}
hits = {t: [] for t in targets}
for va, fn in dis.funcs.items():
    for i in fn.insns:
        if i.mem_addr in targets:
            hits[i.mem_addr].append((fn.va, i.va, i.mnemonic, i.op_str))
for t in sorted(targets):
    print(f'=== 0x{t:08x}  ({len(hits[t])} insns)')
    for fnva, va, mn, ops in sorted(hits[t], key=lambda x: x[1]):
        print(f'   fn 0x{fnva:08x}   {va:08x}  {mn:<8} {ops}')
