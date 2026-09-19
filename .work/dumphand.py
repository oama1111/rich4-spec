import sys; sys.path.insert(0,'.work')
from r4 import *
ACT=[ (a, rd32(0x475324+4*a)) for a in range(1,44) ]
BOUNDS={}
addrs=sorted(set(v for _,v in ACT))
for k,v in enumerate(addrs):
    BOUNDS[v]= addrs[k+1] if k+1<len(addrs) else 0x421ea0
G={0x499114:'num_players',0x49910c:'current_player',0x4990e8:'price_index',
   0x499120:'hand[]',0x499198:'deck_cnt[]',0x48be58:'aiP0',0x48be5c:'aiP1',0x48be60:'aiP2',0x48be64:'aiP3',
   0x48b8b4:'g48b8b4',0x48b8c4:'g48b8c4',0x48b8b8:'g48b8b8',0x48b8bc:'g48b8bc',0x48b8c0:'g48b8c0',
   0x4751f0:'deed_tbl',0x498e80:'map2land',0x498e84:'res_land',0x498e88:'com_land',0x499110:'deed_idx',
   0x498b1c:'g498b1c',0x47fdea:'card_tbl-2',0x4990ec:'g4990ec',0x499100:'g499100',0x499104:'g499104',
   0x499108:'g499108',0x499118:'g499118',0x49911c:'g49911c'}
PF={0x15:'type',0x16:'b16',0x17:'personality',0x19:'b19',0x1c:'cash',0x20:'bank',0x24:'loan',0x28:'f28',0x2c:'f2c',
    0x30:'points',0x34:'f34',0x38:'f38',0x3c:'f3c',0x40:'f40',0x41:'ally',0x42:'f42',0x44:'f44',0x48:'f48',
    0x4c:'hostility[0]',0x50:'hostility[1]',0x54:'hostility[2]',0x58:'hostility[3]',
    0x5c:'monthly_paid',0x60:'monthly_received',0x64:'f64'}
def ann(op):
    o=op
    for k,v in G.items():
        o=o.replace('0x%x'%k, v)
    import re
    def rep(m):
        off=int('496b'+m.group(1),16)-0x496b68
        if off in (0x15,0x16,0x17,0x19,0x1c,0x20,0x24,0x28,0x2c,0x30,0x34,0x38,0x3c,0x40,0x41,0x42,0x44,0x48,0x4c,0x50,0x54,0x58,0x5c,0x60,0x64):
            return 'player+0x%x(%s)'%(off,PF[off])
        return 'player+0x%x'%off
    o=re.sub(r'0x496b([0-9a-f]{2})', rep, o)
    return o
which=sys.argv[1]
want=[int(x,16) for x in sys.argv[2:]] if len(sys.argv)>2 else None
for a,h in ACT:
    if want and h not in want: continue
    end=BOUNDS[h]
    print('#### action %d  handler %08x  len=%d'%(a,h,end-h))
    for i in dis(h,end=end):
        t=''
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            tt=int(i.op_str,16); e=FBY.get(tt)
            if e and e.get('name'): t=' ; '+e['name']
        print('%08x  %-9s %s%s'%(i.address,i.mnemonic,ann(i.op_str),t))
