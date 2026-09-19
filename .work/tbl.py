import struct,sys
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
def va2off(va):
    if 0x401000<=va<0x401000+0x60400: return va-0x401000+0x400
    if 0x462000<=va<0x462e00: return va-0x462000+0x60800
    if 0x463000<=va<0x489c00: return va-0x463000+0x61600
    return None
def cstr(va):
    o=va2off(va)
    if o is None: return None
    e=D.index(b'\0',o)
    return D[o:e]
base=0x47fdea
for idx in range(0,46):
    va=base+idx*8
    o=va2off(va)
    nameptr,price=struct.unpack_from('<II',D,o)
    f7=D[o+7]
    nm=cstr(nameptr) if 0x462000<=nameptr<0x48a000 else b'?'
    try: nm=nm.decode('cp950')
    except: nm=repr(nm)
    print(f'idx={idx:2d} ent={va:#010x} nameptr={nameptr:#010x} price={price:#010x}({price}) f7={f7:#04x} name={nm!r}')
