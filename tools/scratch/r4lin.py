#!/usr/bin/env python3
"""Linear disassembler: python3 .work/d.py <va> <len> [n]"""
import sys, struct
from capstone import *
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),(0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
def va2off(va):
    for base,raw,size in SEC:
        if size and base<=va<base+size:
            return va-base+raw
    return None
md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=False
def dis(va,ln):
    off=va2off(va)
    if off is None: print('not in file',hex(va)); return
    code=D[off:off+ln]
    for i in md.disasm(code,va):
        print('%08x  %-8s %s'%(i.address,i.mnemonic,i.op_str))
va=int(sys.argv[1],16); ln=int(sys.argv[2],0)
if len(sys.argv)>3:
    # count mode: n instructions
    off=va2off(va); code=D[off:off+ln]
    n=0
    for i in md.disasm(code,va):
        print('%08x  %-8s %s'%(i.address,i.mnemonic,i.op_str)); n+=1
        if n>=int(sys.argv[3]): break
else:
    dis(va,ln)
