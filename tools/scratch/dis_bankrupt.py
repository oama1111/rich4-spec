import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)
starts = sorted(dis.funcs)
for target in (0x40d095, 0x40d0d6):
    owner = max(f for f in starts if f <= target)
    print(f"### {hex(target)} 属于函数 {hex(owner)}")
    print(R.render_func(dis, owner))
    print()
