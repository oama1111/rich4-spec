import json,sys,collections
F=json.load(open('gen/functions.json'))
by={}
for e in F: by[int(e['va'],16)]=e
def owner(va):
    # find function whose [va, va+size) contains va
    best=None
    for v,e in by.items():
        s=e.get('size') or 0
        if v<=va<v+s:
            if best is None or v>best[0]: best=(v,e)
    return best
callees={}
for v,e in by.items():
    callees[v]=[int(c,16) for c in (e.get('callees') or [])]
# reverse
rev=collections.defaultdict(list)
for v,cs in callees.items():
    for c in cs: rev[c].append(v)
# rand call sites
randcalls=[]
import struct
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,0x400,0x60400),('.idata',0x462000,0x60800,0xe00),('DGROUP',0x463000,0x61600,0x26c00),('.reloc',0x49a000,0x88200,0xa400),('.rsrc',0x4a5000,0x92600,0xa00)]
def off2va(o):
    for n,b,r,s in SEC:
        if r<=o<r+s: return b+(o-r)
for o in range(0,len(D)-4):
    if D[o]==0xE8:
        rel=struct.unpack_from('<i',D,o+1)[0]
        va=off2va(o)
        if va is not None and (va+5+rel)&0xffffffff==0x456f2d:
            randcalls.append(va)
print('total rand call sites',len(randcalls))
roots=[int(x,16) for x in sys.argv[1:]]
seen=set(); q=collections.deque(roots)
while q:
    v=q.popleft()
    if v in seen: continue
    seen.add(v)
    for c in callees.get(v,[]):
        if c not in seen: q.append(c)
print('reachable funcs',len(seen))
inreach=[]
for rc in randcalls:
    ow=owner(rc)
    if ow and ow[0] in seen: inreach.append((rc,ow[0]))
print('rand sites reachable',len(inreach))
for rc,ow in inreach:
    print('%08x in %08x'%(rc,ow))
