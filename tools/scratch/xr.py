#!/usr/bin/env python3
"""Query gen/xrefs.json + functions.json.
usage: xr.py 0x496b88 0x496ba3      # who reads/writes these data VAs
       xr.py --fn 0x436668          # funcs that mention VA in reads/writes
       xr.py --callers 0x40cd87
       xr.py --search 0x434492      # find 4-byte LE occurrences of a VA in code/data
"""
import sys, json, os, struct
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXE = os.path.join(os.path.dirname(ROOT), 'Rich4', 'rich4.exe')
D = open(EXE,'rb').read()
SEC = [(0x401000,1024,394240),(0x462000,395264,3584),(0x463000,398848,158720),
       (0x48a000,0,64512),(0x49a000,557568,41984),(0x4a5000,599552,2560)]
def va2off(va):
    for b,r,s in SEC:
        if b <= va < b+s: return None if r is None else va-b+r
    return None
def off2va(o):
    for b,r,s in SEC:
        if r is not None and r <= o < r+s: return b + (o-r)
    return None
XR = json.load(open(os.path.join(ROOT,'gen','xrefs.json')))
FUNCS = json.load(open(os.path.join(ROOT,'gen','functions.json')))
BY_VA = {int(f['va'],16): f for f in FUNCS}
NAME = {int(f['va'],16): (f.get('name') or '') for f in FUNCS}

def xr(va):
    hit = [e for e in XR if int(e['addr'],16) == va]
    if not hit:
        print(f'0x{va:08x}: (no entry)')
        return
    e = hit[0]
    print(f'0x{va:08x}:')
    print('  read_by   :', e.get('read_by'))
    print('  written_by:', e.get('written_by'))

def funcs_mentioning(va):
    out=[]
    for f in FUNCS:
        if va in f.get('reads',[]) or va in f.get('writes',[]):
            out.append((int(f['va'],16), 'R' if va in f.get('reads',[]) else '', 'W' if va in f.get('writes',[]) else ''))
    for v,r,w in sorted(out):
        print(f'  0x{v:08x} {r}{w} {NAME.get(v,"")}')

def callers(va):
    f = BY_VA.get(va)
    print(f'0x{va:08x} callers:', f['callers'] if f else None)

def search(val, limit=60):
    pat = struct.pack('<I', val)
    n=0
    i=0
    while True:
        j = D.find(pat, i)
        if j < 0: break
        v = off2va(j)
        if v is not None:
            print(f'  0x{v:08x}')
            n+=1
            if n>=limit: break
        i = j+1

if __name__ == '__main__':
    args = sys.argv[1:]
    if args[0]=='--fn':
        funcs_mentioning(int(args[1],16))
    elif args[0]=='--callers':
        callers(int(args[1],16))
    elif args[0]=='--search':
        search(int(args[1],16))
    else:
        for a in args: xr(int(a,16))
