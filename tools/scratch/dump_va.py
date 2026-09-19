import sys, os; sys.path.insert(0,'tools')
import rich4dis as R
im = R.Image(R.EXE_DEFAULT)
d = R.Disassembler(im)
for a in sys.argv[1:]:
    va = int(a, 0)
    print('='*72); print(hex(va))
    for ins in d.decode_at(va).insns[:int(os.environ.get('N','80'))]:
        print(f'{ins.va:08x}  {ins.size}  {ins.mnemonic:<7} {ins.op_str}')
