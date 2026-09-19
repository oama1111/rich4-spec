import sys,struct
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
TEXT_OFF=1024; TEXT_BASE=0x401000; TEXT_SIZE=394240
md=Cs(CS_ARCH_X86,CS_MODE_32)
def dec(va):
    o=va-TEXT_BASE+TEXT_OFF
    it=md.disasm(D[o:o+16],va)
    for i in it: return i
    return None
def walk(start, seen_ins, roots, limit=200000):
    todo=[start]
    while todo:
        va=todo.pop()
        if va in seen_ins: continue
        while True:
            if va in seen_ins: break
            if not (TEXT_BASE<=va<TEXT_BASE+TEXT_SIZE): break
            i=dec(va)
            if i is None: break
            seen_ins[va]=i
            m=i.mnemonic
            if m=='call':
                if i.op_str.startswith('0x'):
                    t=int(i.op_str,16)
                    roots.add(t); todo.append(t)
                va=i.address+i.size; continue
            if m=='jmp':
                if i.op_str.startswith('0x'):
                    todo.append(int(i.op_str,16)); break
                else: break
            if m.startswith('j') and i.op_str.startswith('0x'):
                todo.append(int(i.op_str,16))
                va=i.address+i.size; continue
            if m=='ret' or m=='retf': break
            va=i.address+i.size
if __name__=='__main__':
    seen={}; roots=set()
    for a in sys.argv[1:]:
        walk(int(a,0),seen,roots)
    # also follow push imm32 code pointers
    changed=True
    while changed:
        changed=False
        for va,i in list(seen.items()):
            if i.mnemonic=='push' and i.op_str.startswith('0x'):
                t=int(i.op_str,16)
                if TEXT_BASE<=t<TEXT_BASE+TEXT_SIZE and t not in seen:
                    walk(t,seen,roots); changed=True
    import json
    N={}
    try:
        for e in json.load(open('gen/functions.json')): N[int(e['va'],16)]=e.get('name') or ''
    except Exception: pass
    print('reachable instructions:',len(seen))
    print('rand sites:')
    for va in sorted(seen):
        i=seen[va]
        if i.mnemonic=='call' and i.op_str=='0x456f2d':
            print('  ',hex(va))
    print('call targets:')
    print('  ',', '.join(sorted(hex(t) for t in roots)))
