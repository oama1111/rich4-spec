import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)
print(R.render_func(dis, 0x445593)[:6000])
