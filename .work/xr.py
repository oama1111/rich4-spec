import struct,sys
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720)]
def va2off(va):
    for base,raw,size in SEC:
        if base<=va<base+size: return va-base+raw
    return None
def scan(target):
    res=[]
    # call rel32 e8
    for va in range(0x401000,0x401000+394240):
        off=va2off(va)
        if off is None: continue
        b=D[off]
        if b==0xE8:
            rel=struct.unpack_from('<i',D,off+1)[0]
            if va+5+rel==target: res.append((hex(va),'call'))
        elif b==0xE9:
            rel=struct.unpack_from('<i',D,off+1)[0]
            if va+5+rel==target: res.append((hex(va),'jmp'))
    # raw dword
    for off in range(1024,1024+394240-4):
        if struct.unpack_from('<I',D,off)[0]==target:
            res.append((hex(off-1024+0x401000),'dword'))
    return res
for t in sys.argv[1:]:
    t=int(t,0)
    r=scan(t)
    print('==',hex(t),len(r))
    for a,k in r: print('   ',a,k)
