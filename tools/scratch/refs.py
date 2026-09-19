import sys, os; sys.path.insert(0,'tools')
import rich4dis as R
im = R.Image(R.EXE_DEFAULT)
d = R.Disassembler(im)
targets = {int(a,0) for a in sys.argv[1:]}
code = im.data[R.CODE_OFF: R.CODE_OFF+R.CODE_SIZE]
for ins in d.md.disasm(code, R.CODE_VA):
    ops = ins.op_str
    for t in targets:
        if hex(t) in ops:
            print(f'{ins.address:08x}  {ins.mnemonic:<7} {ops}')
