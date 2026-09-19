import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)
txt = R.render_func(dis, 0x40cd87)
for line in txt.split("\n"):
    s = line.strip()
    if s.startswith("0040d1") or s.startswith("0040d2"):
        print(line)
