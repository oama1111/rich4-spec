import sys,re; sys.path.insert(0,'.work')
from r4 import *
exec(open('.work/dumphand.py').read().split("which=sys.argv")[0].replace("import sys; sys.path.insert(0,'.work')",""))
JCC=set('je jne jg jge jl jle ja jae jb jbe js jns jz jnz'.split())
def want(i):
    m=i.mnemonic; o=ann(i.op_str)
    if m in ('call','ret','imul','idiv'): return True
    if m in JCC: return True
    if '[esp' in o or '[esp' in o: return False
    if re.search(r'0x[0-9a-f]+|\b\d+\b',o) or 'ptr [' in o:
        return m not in ('push','pop','add esp','sub esp')
    return False
for a,h in ACT:
    end=BOUNDS[h]
    print('#### action %d  handler %08x  len=%d'%(a,h,end-h))
    for i in dis(h,end=end):
        if want(i): print('%08x  %-9s %s'%(i.address,i.mnemonic,ann(i.op_str)))
