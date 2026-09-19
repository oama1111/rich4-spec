import sys,struct
sys.path.insert(0,'.work')
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
md=Cs(CS_ARCH_X86,CS_MODE_32)
TEXT_RAW=0x400; TEXT_VA=0x401000; TEXT_SZ=0x60400
code=D[TEXT_RAW:TEXT_RAW+TEXT_SZ]
def insns():
    o=0
    while o<len(code):
        got=None
        for i in md.disasm(code[o:o+15],TEXT_VA+o,count=1):
            got=i;break
        if got is None:
            o+=1;continue
        yield got
        o+=got.size
def calls(target):
    r=[]
    for i in insns():
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            if int(i.op_str,16)==target: r.append((i.address,i.mnemonic))
    return r
def imms(lo,hi):
    r=[]
    for i in insns():
        for tok in i.op_str.replace('[',' ').replace(']',' ').replace(',',' ').replace('+',' ').replace('*',' ').split():
            try: v=int(tok,16)
            except: continue
            if lo<=v<=hi: r.append((i.address,i.mnemonic,i.op_str))
    return r
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='calls':
        for t in sys.argv[2:]:
            t=int(t,16); r=calls(t)
            print('== %08x  %d calls'%(t,len(r)))
            for a,m in r: print('    %08x %s'%(a,m))
    else:
        lo=int(sys.argv[2],16); hi=int(sys.argv[3],16)
        for a,m,o in imms(lo,hi): print('%08x  %-8s %s'%(a,m,o))
