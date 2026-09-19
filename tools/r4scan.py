#!/usr/bin/env python3
import sys,struct
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
CODE_START=0x401000; CODE_RAW=1024; CODE_SIZE=394240
def va2off(va):
    if CODE_START<=va<CODE_START+CODE_SIZE: return va-CODE_START+CODE_RAW
    return None
def off2va(o):
    if CODE_RAW<=o<CODE_RAW+CODE_SIZE: return o-CODE_RAW+CODE_START
    return None
targets=[int(x,16) for x in sys.argv[1:]]
for t in targets:
    print('== target',hex(t))
    # E8 rel32
    for o in range(CODE_RAW,CODE_RAW+CODE_SIZE-5):
        if D[o]==0xE8:
            rel=struct.unpack_from('<i',D,o+1)[0]
            va=off2va(o)
            if va is not None and (va+5+rel)&0xffffffff==t&0xffffffff:
                print('  call at',hex(va))
        if D[o]==0xE9:
            rel=struct.unpack_from('<i',D,o+1)[0]
            va=off2va(o)
            if va is not None and (va+5+rel)&0xffffffff==t&0xffffffff:
                print('  jmp at',hex(va))
    # push imm32 (0x68)
    for o in range(CODE_RAW,CODE_RAW+CODE_SIZE-5):
        if D[o]==0x68:
            imm=struct.unpack_from('<I',D,o+1)[0]
            if imm==t:
                print('  push imm32 at',hex(off2va(o)))
    # dword data anywhere
    b=struct.pack('<I',t); i=0
    while True:
        j=D.find(b,i)
        if j<0: break
        print('  dword@file',hex(j),'va',hex(j-1024+0x401000) if o and 1024<=j<1024+CODE_SIZE else '(datasec off %#x)'%j)
        i=j+1
