#!/usr/bin/env python3
"""Fast function dumper using gen/functions.json boundaries + capstone.
usage: fd.py 0x436668 [0x436a5a ...]      # dump functions
       fd.py --range 0x436034 0x436600     # dump raw range
"""
import sys, json, os
from capstone import *
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(os.path.dirname(ROOT), 'Rich4', 'rich4.exe')
D = open(EXE, 'rb').read()
SEC = [(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),
       (0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
FUNCS = json.load(open(os.path.join(ROOT,'gen','functions.json')))
BY_VA = {int(f['va'],16): f for f in FUNCS}
SORTED = sorted(BY_VA)

def va2off(va):
    for base, raw, size in SEC:
        if base <= va < base+size:
            return None if raw is None else va-base+raw
    return None

def read(va, n):
    off = va2off(va)
    if off is None: return b''
    return D[off:off+n]

def u32(va):
    b = read(va,4)
    return int.from_bytes(b,'little') if len(b)==4 else None

def f64(va):
    b = read(va,8)
    return None if len(b)!=8 else __import__('struct').unpack('<d',b)[0]

md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True

def dump(start, end, label=''):
    print(f'===== {label} 0x{start:08x} .. 0x{end:08x} ({end-start} bytes) =====')
    code = read(start, end-start)
    for i in md.disasm(code, start):
        ann = []
        for op in i.operands:
            if op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                a = op.mem.disp
                ann.append(f'[0x{a:08x}]')
                if a < len(D) and 0x463000 <= a < 0x49a000:
                    s = D[va2off(a):va2off(a)+24] if va2off(a) is not None else b''
                    try:
                        t = s.split(b'\0')[0].decode('gbk')
                        if t and all(32 <= ord(c) < 127 or ord(c) > 0x2000 for c in t):
                            ann.append(f'str="{t}"')
                    except Exception:
                        pass
            elif op.type == X86_OP_IMM and i.mnemonic in ('push','call','jmp'):
                pass
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            t = int(i.op_str,16)
            nm = BY_VA.get(t,{}).get('name') or ''
            ann.append(f'->0x{t:x}{" "+nm if nm else ""}')
        line = f'  {i.address:08x}  {i.mnemonic:<8} {i.op_str}'
        if ann: line += '   ; ' + ' '.join(ann)
        print(line)

if __name__ == '__main__':
    args = sys.argv[1:]
    if args[0] == '--range':
        s = int(args[1],16); e = int(args[2],16)
        dump(s,e)
    else:
        for a in args:
            v = int(a,16)
            nxt = [x for x in SORTED if x > v]
            end = nxt[0] if nxt else v+0x400
            f = BY_VA[v]
            print(f'# func 0x{v:08x} insns={f["insn_count"]} callers={f["callers"]} callees={f["callees"]}')
            print(f'#  reads={f["reads"]}')
            print(f'#  writes={f["writes"]}')
            dump(v, min(end, v+f.get("size",0) or end), 'func')
