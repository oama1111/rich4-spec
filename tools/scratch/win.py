import sys, os; sys.path.insert(0,'tools')
import rich4dis as R
im = R.Image(R.EXE_DEFAULT)
d = R.Disassembler(im)
entry = int(sys.argv[1],0); lo = int(sys.argv[2],0); hi = int(sys.argv[3],0)
for ins in d.decode_at(entry).insns:
    if lo <= ins.va <= hi:
        print(f'{ins.va:08x}  {ins.mnemonic:<7} {ins.op_str}')
