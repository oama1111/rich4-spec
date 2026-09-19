import sys,subprocess,re,struct
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,0x400,0x60400),('.idata',0x462000,0x60800,0xe00),('DGROUP',0x463000,0x61600,0x26c00),('.reloc',0x49a000,0x88200,0xa400),('.rsrc',0x4a5000,0x92600,0xa00)]
def va2off(va):
    for n,b,r,s in SEC:
        if b<=va<b+s: return r+(va-b)
    return None
def rd(va,n=64):
    o=va2off(va)
    if o is None: return None
    return D[o:o+n]
def s(va):
    b=rd(va)
    if b is None: return '?'
    b=b.split(b'\0')[0]
    try: return b.decode('big5')
    except Exception: return b.decode('big5',errors='replace')
for a in sys.argv[1:]:
    print(hex(int(a,16)), repr(s(int(a,16))))
