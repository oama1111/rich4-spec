#!/usr/bin/env python3
"""R4 helper: disasm, tables, strings, xrefs."""
import sys, struct, json, os, re
from capstone import *
ROOT='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版'
EXE=ROOT+'/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),(0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
def va2off(va):
    for base,raw,size in SEC:
        if size and base<=va<base+size: return va-base+raw
    return None
def off2va(o):
    for base,raw,size in SEC:
        if size and raw<=o<raw+size: return o-raw+base
    return None
md=Cs(CS_ARCH_X86,CS_MODE_32)
md.detail=True
FUNCS=json.load(open(ROOT+'/rich4-spec/gen/functions.json'))
FBY={int(e['va'],16):e for e in FUNCS}
def func_at(va):
    # exact or containing
    e=FBY.get(va)
    if e: return e
    for k,v in FBY.items():
        if k<=va<k+v['size']: return v
    return None
def dis(va,ln=None,end=None,n=None):
    if end is None and ln is not None: end=va+ln
    off=va2off(va); code=D[off:off+(end-va)]
    out=[]
    for i in md.disasm(code,va):
        out.append(i)
        if n and len(out)>=n: break
    return out
def fmt(i):
    return '%08x  %-10s %s'%(i.address,i.mnemonic,i.op_str)
def show(va,ln=None,end=None,n=None):
    for i in dis(va,ln,end,n):
        s=fmt(i)
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            t=int(i.op_str,16); e=FBY.get(t)
            s+='   ; %s'%((e.get('name') or '') if e else '')
        print(s)
def rd32(va):
    o=va2off(va); return struct.unpack_from('<I',D,o)[0]
def rd8(va):
    o=va2off(va); return D[o]
def rds(va,maxlen=64):
    o=va2off(va)
    if o is None: return None
    e=D.find(b'\x00',o,o+maxlen)
    if e<0: e=o+maxlen
    return D[o:e]
def cjk(b):
    try: return b.decode('cp950')
    except Exception:
        try: return b.decode('big5')
        except Exception: return repr(b)
def callers(va):
    o=va2off(va)
    res=[]
    for i in dis(0x401000, end=0x463000):
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            if int(i.op_str,16)==va: res.append(i.address)
    return res
def randcalls(va,end):
    """list rand calls in range with following 6 insns"""
    ins=dis(va,end=end)
    for k,i in enumerate(ins):
        if i.mnemonic=='call' and i.op_str=='0x456f2d':
            print('--- rand at %08x'%i.address)
            for j in ins[k+1:k+7]: print('   ',fmt(j))
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='show': show(int(sys.argv[2],16), end=int(sys.argv[3],16))
    elif cmd=='fn': 
        e=func_at(int(sys.argv[2],16)); print(json.dumps(e,ensure_ascii=False))
    elif cmd=='callers': print([hex(x) for x in callers(int(sys.argv[2],16))])
    elif cmd=='str': print(cjk(rds(int(sys.argv[2],16),int(sys.argv[3]) if len(sys.argv)>3 else 128)))
    elif cmd=='rand': randcalls(int(sys.argv[2],16),int(sys.argv[3],16))

def sweep(sec_only=True):
    """yield insns across all sections, skipping undecodable bytes"""
    out=[]
    for base,raw,size in SEC:
        if size==0: continue
        code=D[raw:raw+size]
        o=0
        while o < len(code):
            got=None
            for i in md.disasm(code[o:o+16], base+o, count=1):
                got=i; break
            if got is None:
                o+=1; continue
            out.append(got)
            o += got.size
    return out
SW=None
def sw():
    global SW
    if SW is None: SW=sweep()
    return SW
def xref_imm(target, mnemonics=None):
    pat=re.compile(r'0x0*%x(?![0-9a-f])'%target)
    r=[]
    for i in sw():
        if pat.search(i.op_str):
            if mnemonics is None or i.mnemonic in mnemonics: r.append(i)
    return r
def callers2(va):
    r=[]
    for i in sw():
        if i.mnemonic in ('call','jmp') and abs(int(i.op_str,16)-va)==0 if i.op_str.startswith('0x') else False:
            r.append(i.address)
    return r
