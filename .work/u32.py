import struct,sys
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720)]
def off(va):
    for b,r,s in SEC:
        if b<=va<b+s: return va-b+r
def u32(va): return struct.unpack_from('<I',D,off(va))[0]
def cstr(va,n=60):
    o=off(va); return D[o:o+n].split(b'\x00')[0].decode('big5','replace')
if __name__=='__main__':
    for a in sys.argv[1:]:
        va=int(a,0); v=u32(va)
        try: s=cstr(v)
        except Exception: s=''
        print(hex(va),hex(v),repr(s))
