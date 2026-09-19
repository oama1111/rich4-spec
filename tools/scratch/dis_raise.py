import sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image()
dis = R.Disassembler(img)
dis.traverse(verbose=False)
# 找包含 0x4454e3 的函数起点
starts = sorted(dis.funcs)
owner = max(f for f in starts if f <= 0x4454e3)
print("涨价卡函数起点:", hex(owner))
print(R.render_func(dis, owner)[:5000])
