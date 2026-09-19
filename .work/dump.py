#!/usr/bin/env python3
"""Linear disasm of a VA range with call/jmp target annotation. usage: dump.py <startVA> <endVA|len> [--len]"""
import sys
from capstone import *
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),(0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
def va2off(va):
    for base,raw,size in SEC:
        if size and base<=va<base+size: return va-base+raw
    return None
def h(s):
    s=s.strip()
    return int(s,16)
start=h(sys.argv[1]); second=h(sys.argv[2])
if len(sys.argv)>3 and sys.argv[3]=='--len': end=start+second
else: end=second
off=va2off(start)
if off is None: print('not mapped',hex(start)); sys.exit(1)
md=Cs(CS_ARCH_X86,CS_MODE_32)
code=D[off:off+(end-start)]
for i in md.disasm(code,start):
    print('%08x  %-8s %s'%(i.address,i.mnemonic,i.op_str))
