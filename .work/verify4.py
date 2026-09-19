import sys,re; sys.path.insert(0,'.work')
from r4 import *
FILE=sys.argv[1]
bad=[];n=0
txt=open(FILE).read()
for m in re.finditer(r'@source\s+0x([0-9a-fA-F]{6,8})\s+([^`\n]+)', txt):
    va=int(m.group(1),16)
    if not (0x401000<=va<0x489c00): continue
    want=m.group(2).strip().rstrip('`').split(';')[0].strip()
    ins=list(dis(va,end=va+16,n=1))
    if not ins: bad.append((va,want,'<no insn>')); continue
    i=ins[0]; got='%s %s'%(i.mnemonic,i.op_str)
    norm=lambda s: re.sub(r'\s+',' ',s.replace(', ',',').replace(',',', ')).strip().lower()
    n+=1
    if norm(got)!=norm(want): bad.append((va,want,got))
print('%s: checked %d inline @source, mismatches %d'%(FILE,n,len(bad)))
for va,w,g in bad[:40]: print('  MISMATCH @0x%08x\n     doc: %s\n     exe: %s'%(va,w,g))
