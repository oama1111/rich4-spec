import sys
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
md=Cs(CS_ARCH_X86,CS_MODE_32)
code=D[1024:1024+394240]
base=0x401000
pats=[p.lower().replace('0x','') for p in sys.argv[1:]]
for i in md.disasm(code,base):
    s=i.op_str.lower()
    for p in pats:
        if p in s.replace('0x',''):
            print('%08x  %-8s %s'%(i.address,i.mnemonic,i.op_str)); break
