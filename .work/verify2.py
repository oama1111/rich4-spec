import sys,re; sys.path.insert(0,'.work')
from r4 import *
FILE=sys.argv[1]
bad=[];n=0
for ln,line in enumerate(open(FILE),1):
    m=re.match(r'\s*([0-9a-fA-F]{6,8})\s+([a-z][a-z0-9]*)\s*(.*)$',line)
    if not m: continue
    va=int(m.group(1),16)
    if not (0x401000<=va<0x489c00): continue
    want=(m.group(2)+' '+m.group(3)).strip()
    want=want.split(';')[0].strip()
    ins=list(dis(va,end=va+16,n=1))
    if not ins: bad.append((ln,va,want,'<no insn>')); continue
    i=ins[0]; got='%s %s'%(i.mnemonic,i.op_str)
    norm=lambda s: re.sub(r'\s+',' ',s.replace(', ',',').replace(',',', ')).strip().lower()
    n+=1
    if norm(got)!=norm(want): bad.append((ln,va,want,got))
print('%s: checked %d raw lines, mismatches %d'%(FILE,n,len(bad)))
for ln,va,w,g in bad[:40]: print('  L%d MISMATCH @0x%08x\n     doc: %s\n     exe: %s'%(ln,va,w,g))
