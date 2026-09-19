#!/usr/bin/env python3
import sys, json
from capstone import *
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),(0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
def va2off(va):
    for base,raw,size in SEC:
        if size and base<=va<base+size: return va-base+raw
NAMES={}
try:
    for e in json.load(open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-spec/gen/functions.json')):
        NAMES[int(e['va'],16)]=e.get('name') or ''
except Exception: pass
md=Cs(CS_ARCH_X86,CS_MODE_32)
start=int(sys.argv[1],0); end=int(sys.argv[2],0)
off=va2off(start)
code=D[off:off+(end-start)]
out=[]
for i in md.disasm(code,start):
    s='%08x  %-8s %s'%(i.address,i.mnemonic,i.op_str)
    if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
        try:
            t=int(i.op_str,16)
            if NAMES.get(t): s+='   ; %s'%NAMES[t]
        except Exception: pass
    out.append(s)
sys.stdout.write('\n'.join(out)+'\n')
