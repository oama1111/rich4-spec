import sys, os; sys.path.insert(0,'tools')
import rich4dis as R
im = R.Image(R.EXE_DEFAULT)
d = R.Disassembler(im)
va = int(sys.argv[1],0); n = int(os.environ.get('N','60'))
off = R.CODE_OFF + (va - R.CODE_VA)
code = im.data[off: off + int(os.environ.get('LEN','600'))]
for ins in d.md.disasm(code, va):
    print(f'{ins.address:08x}  {ins.size}  {ins.mnemonic:<7} {ins.op_str}')
    n -= 1
    if n <= 0: break
