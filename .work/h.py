#!/usr/bin/env python3
"""Helpers: correct VA->file offset, hex dump, big5 strings."""
import sys, struct
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,1024,394240),('.idata',0x462000,395264,3584),
     ('DGROUP',0x463000,398848,158720),('.bss',0x48a000,0,64512),
     ('.reloc',0x49a000,557568,41984),('.rsrc',0x4a5000,599552,2560)]
def va2off(va):
    for n,b,r,s in SEC:
        if s and b<=va<b+s: return va-b+r
    return None
def sec_of(va):
    for n,b,r,s in SEC:
        if s and b<=va<b+s: return n
    return None
def rd(va,n):
    o=va2off(va)
    if o is None: return None
    return D[o:o+n]
def cstr(va,maxn=256):
    o=va2off(va)
    if o is None: return None
    e=D.find(b'\0',o,o+maxn)
    return D[o:e]
def s(va,maxn=256):
    b=cstr(va,maxn)
    if b is None: return '<unmapped>'
    for enc in ('big5','gbk'):
        try: return b.decode(enc)
        except Exception: pass
    return repr(b)
def hexdump(va,n):
    o=va2off(va)
    if o is None: print('unmapped',hex(va)); return
    for i in range(0,n,16):
        raw=D[o+i:o+i+16]
        try: t=raw.decode('big5')
        except Exception: t=''
        print('%08x  %-47s  %s'%(va+i,' '.join('%02x'%x for x in raw), t.replace('\n','\\n')))
def dw(va):
    b=rd(va,4)
    return struct.unpack('<I',b)[0] if b and len(b)==4 else None
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='str':
        for a in sys.argv[2:]: print(a, hex(int(a,16)), sec_of(int(a,16)), repr(cstr(int(a,16))))
        print('--- decoded ---')
        for a in sys.argv[2:]: print(a, s(int(a,16)))
    elif cmd=='hex':
        hexdump(int(sys.argv[2],16), int(sys.argv[3],0))
    elif cmd=='dw':
        for a in sys.argv[2:]:
            a=int(a,16); print(hex(a), hex(dw(a)), '->', sec_of(dw(a)) if dw(a) and dw(a)>0x400000 else '')
    elif cmd=='sec':
        for a in sys.argv[2:]:
            a=int(a,16); print(hex(a), sec_of(a), hex(va2off(a)) if va2off(a) is not None else None)
