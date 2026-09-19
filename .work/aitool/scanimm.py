import struct,sys
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
CB=0x401000; CR=0x400; CS=0x60400
md=Cs(CS_ARCH_X86,CS_MODE_32)
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
res={}
for i in md.disasm(D[CR:CR+CS],CB):
    for tok in i.op_str.replace('[',' ').replace(']',' ').replace(',',' ').split():
        try: v=int(tok,16)
        except: continue
        if lo<=v<=hi: res.setdefault(v,[]).append((i.address,i.mnemonic,i.op_str))
for v in sorted(res):
    print('%08x'%v)
    for a,m,o in res[v]: print('    %08x  %-8s %s'%(a,m,o))
