import struct,sys
from capstone import *
D=open('/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe','rb').read()
CB=0x401000; CR=0x400; CS=0x60400
md=Cs(CS_ARCH_X86,CS_MODE_32)
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
tg={}
off=CR+(lo-CB)
for i in md.disasm(D[off:off+(hi-lo)],lo):
    if i.mnemonic=='call' and i.op_str.startswith('0x'):
        t=int(i.op_str,16); tg.setdefault(t,[]).append(i.address)
for t in sorted(tg):
    print('%08x  <- %s'%(t,' '.join('%08x'%a for a in tg[t])))
