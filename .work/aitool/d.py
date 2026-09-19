import sys,struct
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
def va2off(va):
    for base,raw,size in [(0x401000,0x400,0x60400),(0x462000,0x60800,0xe00),(0x463000,0x61600,0x26c00),(0x48a000,None,0xfc00),(0x49a000,0x88200,0xa400),(0x4a5000,0x92600,0xa00)]:
        if size and base<=va<base+size:
            return None if raw is None else va-base+raw
    return None
def rd(va,n):
    o=va2off(va)
    if o is None: raise SystemExit('unmapped %#x'%va)
    return D[o:o+n]
md=Cs(CS_ARCH_X86,CS_MODE_32)
if __name__=='__main__':
    c=sys.argv[1]
    if c=='bytes':
        va=int(sys.argv[2],16); n=int(sys.argv[3],0); b=rd(va,n)
        for k in range(0,len(b),16):
            print('%08x  '%(va+k)+' '.join('%02x'%x for x in b[k:k+16]))
    elif c=='dis':
        va=int(sys.argv[2],16); n=int(sys.argv[3],0)
        for i in md.disasm(rd(va,n),va):
            print('%08x  %-10s %s'%(i.address,i.mnemonic,i.op_str))
    elif c=='dword':
        va=int(sys.argv[2],16); n=int(sys.argv[3],0)
        for k in range(n):
            print('%08x  %08x'%(va+4*k,struct.unpack_from('<I',rd(va+4*k,4))[0]))
    elif c=='str':
        for a in sys.argv[2:]:
            va=int(a,16); o=va2off(va)
            e=D.index(b'\0',o)
            raw=D[o:e]
            try: s=raw.decode('cp950')
            except Exception as ex: s=repr(raw)
            print(a,repr(s))
