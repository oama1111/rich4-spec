import struct,sys
from capstone import *
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,0x400,0x60400),('.idata',0x462000,0x60800,0xe00),('DGROUP',0x463000,0x61600,0x26c00),('.reloc',0x49a000,0x88200,0xa400),('.rsrc',0x4a5000,0x92600,0xa00)]
def off2va(o):
    for n,b,r,s in SEC:
        if r<=o<r+s: return b+(o-r)
def va2off(va):
    for n,b,r,s in SEC:
        if b<=va<b+s: return r+(va-b)
md=Cs(CS_ARCH_X86,CS_MODE_32)
def insns_from(va,n=20):
    o=va2off(va)
    if o is None: return []
    return list(md.disasm(D[o:o+n],va))
for tgt in sys.argv[1:]:
    t=int(tgt,16)
    print('=== %08x'%t)
    pat=struct.pack('<I',t)
    seen=set()
    i=0
    while True:
        i=D.find(pat,i)
        if i<0: break
        va=off2va(i); i+=1
        if va is None: continue
        for back in range(1,9):
            for ins in insns_from(va-back,12):
                if ins.address!=va-back: continue
                if ins.address+ins.size not in (va+4,va+8): continue
                if hex(t)[2:] not in ins.op_str.replace('0x',''): pass
                if '491' in ins.op_str or hex(t).lstrip('0x') in ins.op_str.replace('0x',''):
                    key=(ins.address,ins.mnemonic,ins.op_str)
                    if key not in seen:
                        seen.add(key); print('  %08x  %-8s %s'%(ins.address,ins.mnemonic,ins.op_str))
                break
