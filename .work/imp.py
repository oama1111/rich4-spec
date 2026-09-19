import struct,sys
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
pe=struct.unpack_from('<I',D,0x3c)[0]
assert D[pe:pe+4]==b'PE\0\0'
nsec=struct.unpack_from('<H',D,pe+6)[0]
optsz=struct.unpack_from('<H',D,pe+20)[0]
opt=pe+24
magic=struct.unpack_from('<H',D,opt)[0]
print('magic',hex(magic))
ddir=opt+(96 if magic==0x10b else 112)
imp_rva,imp_sz=struct.unpack_from('<II',D,ddir+8)
print('import dir rva',hex(imp_rva),imp_sz)
secs=[]
so=opt+optsz
for i in range(nsec):
    b=so+i*40
    name=D[b:b+8].rstrip(b'\0').decode('latin1')
    vsize,vaddr,rawsize,rawptr=struct.unpack_from('<IIII',D,b+8)
    secs.append((name,vaddr,vsize,rawptr,rawsize))
    print(name,hex(vaddr),hex(vsize),hex(rawptr),hex(rawsize))
def rva2off(rva):
    for name,va,vs,raw,rs in secs:
        if va<=rva<va+max(vs,rs): return rva-va+raw
    return None
o=rva2off(imp_rva)
i=0
slots={}
while True:
    oft,ts,fc,nrva,ft=struct.unpack_from('<IIIII',D,o+i*20)
    if oft==0 and nrva==0: break
    i+=1
    dllname=D[rva2off(nrva):].split(b'\0')[0].decode('latin1')
    thunk = oft if oft else ft
    to=rva2off(thunk)
    j=0
    while True:
        v=struct.unpack_from('<I',D,to+j*4)[0]
        if v==0: break
        if v&0x80000000:
            nm='ord#%d'%(v&0xffff)
        else:
            o2=rva2off(v)
            nm=D[o2+2:].split(b'\0')[0].decode('latin1')
        va=ft+j*4
        slots[va]='%s!%s'%(dllname,nm)
        j+=1
for va in sorted(slots):
    print(hex(va),slots[va])
