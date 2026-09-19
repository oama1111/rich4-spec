import sys,re,glob; sys.path.insert(0,'.work')
from r4 import *
FILE=sys.argv[1]
txt=open(FILE).read()
pat=re.compile(r'@0x([0-9a-fA-F]{6,8})\s*`([^`]+)`')
bad=[];n=0
for m in pat.finditer(txt):
    va=int(m.group(1),16); want=m.group(2).strip()
    ins=[i for i in dis(va,end=va+16,n=1)]
    if not ins: bad.append((va,want,'<no insn>')); continue
    i=ins[0]
    got='%s %s'%(i.mnemonic,i.op_str)
    n+=1
    # normalize whitespace/comma spacing
    norm=lambda s: re.sub(r'\s+',' ',s.replace(', ',',')).strip().lower()
    if norm(got)!=norm(want):
        bad.append((va,want,got))
print('%s: checked %d, mismatches %d'%(FILE,n,len(bad)))
for va,w,g in bad: print('  MISMATCH @0x%08x\n     doc: %s\n     exe: %s'%(va,w,g))
