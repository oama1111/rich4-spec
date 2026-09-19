import sys,subprocess,re,struct
EXE='/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe'
D=open(EXE,'rb').read()
SEC=[('AUTO',0x401000,0x400,0x60400),('.idata',0x462000,0x60800,0xe00),('DGROUP',0x463000,0x61600,0x26c00),('.reloc',0x49a000,0x88200,0xa400),('.rsrc',0x4a5000,0x92600,0xa00)]
def va2off(va):
    for n,b,r,s in SEC:
        if b<=va<b+s: return r+(va-b)
    return None
def rd(va,n=48):
    o=va2off(va)
    return None if o is None else D[o:o+n]
def dec(va):
    b=rd(va)
    if b is None: return None
    b=b.split(b'\0')[0]
    if len(b)<2: return None
    try:
        t=b.decode('big5')
    except Exception:
        return None
    if not any('\u4e00'<=c<='\u9fff' or c.isascii() and c.isprintable() for c in t): return None
    return t
start=int(sys.argv[1],16); end=int(sys.argv[2],16)
out=subprocess.run(['python3','tools/scratch/r4dump.py',hex(start),hex(end)],capture_output=True,text=True).stdout
seen=set()
for line in out.splitlines():
    m=re.search(r'0x([0-9a-f]{6,8})',line)
    if not m: continue
    v=int(m.group(1),16)
    if 0x463000<=v<0x48a000 or 0x48a000<=v<0x49a000:
        t=dec(v)
        if t and v not in seen:
            seen.add(v); print('%08x %r'%(v,t))
