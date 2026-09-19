import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)
txt = R.render_func(dis, 0x40cd87)
keep = False
for line in txt.split("\n"):
    if line.strip().startswith("0040d0"):
        keep = True
    if line.strip().startswith("0040d1"):
        keep = False
    if keep:
        print(line)
