import struct,sys
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,0x400,0x60400),('.idata',0x462000,0x60800,0xe00),('DGROUP',0x463000,0x61600,0x26c00),('.reloc',0x49a000,0x88200,0xa400),('.rsrc',0x4a5000,0x92600,0xa00)]
def off2va(o):
    for n,b,r,s in SEC:
        if r<=o<r+s: return b+(o-r)
    return None
def va2off(va):
    for n,b,r,s in SEC:
        if b<=va<b+s: return r+(va-b)
    return None
tgts=[int(x,16) for x in sys.argv[1:]]
for t in tgts:
    print('=== %08x'%t)
    res=[]
    for o in range(0,len(D)-4):
        if D[o] in (0xE8,0xE9):
            rel=struct.unpack_from('<i',D,o+1)[0]
            va=off2va(o)
            if va is not None and (va+5+rel)&0xffffffff==t:
                res.append(('%s'%('call' if D[o]==0xE8 else 'jmp'),va))
    # also push imm32 of target (function pointer)
    for o in range(len(D)-4):
        v=struct.unpack_from('<I',D,o)[0]
        if v==t:
            va=off2va(o)
            if va: res.append(('ptr',va))
    for k,va in res: print('  %-4s %08x'%(k,va))
