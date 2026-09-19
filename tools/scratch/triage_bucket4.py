import json, os, re, sys
sys.path.insert(0, 'tools')
import rich4dis as R

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
HEX = re.compile(r"0x0*([0-9a-fA-F]{4,8})")
spec = set()
for dp, _d, ns in os.walk(os.path.join(ROOT, "docs")):
    for n in ns:
        if n.endswith(".md"):
            t = open(os.path.join(dp, n), encoding="utf-8", errors="replace").read()
            for m in HEX.finditer(t):
                v = int(m.group(1), 16)
                if 0x401000 <= v < 0x462000:
                    spec.add(v)

byname = {int(f["va"], 16): f for f in funcs}
strings = json.load(open(os.path.join(ROOT, "gen", "strings.json"), encoding="utf-8"))
# strings.json 形状兼容
strs = strings if isinstance(strings, list) else strings.get("strings", [])

img = R.Image(); dis = R.Disassembler(img); dis.traverse(verbose=False)

def covered(va):
    return va in spec

rows = []
for f in funcs:
    va = int(f["va"], 16); size = f.get("size") or 0
    if va >= 0x450000: continue
    if any(v in spec for v in range(va, va + max(size,1))): continue
    if len(f.get("callers", [])) == 0: continue
    rows.append(f)
rows.sort(key=lambda f: -(f.get("size") or 0))
print(f"桶 4 共 {len(rows)} 条\n")
for f in rows:
    va = int(f["va"], 16)
    callers = [int(c, 16) for c in f.get("callers", [])]
    callees = [int(c, 16) for c in f.get("callees", [])]
    print(f"########## 0x{va:06x}  {f.get('size')}B  {f.get('insn_count')}条  ends={f.get('ends')} ##########")
    print(f"  被调用: {[hex(c) for c in callers]}")
    print(f"  调用  : {[hex(c) for c in callees]}")
    # 读到的字符串常量
    reads = [int(x, 16) for x in f.get("reads", [])]
    named = []
    for s in strs:
        a = s.get("va") if isinstance(s, dict) else None
        if a is None: continue
        a = int(a, 16) if isinstance(a, str) else a
        if a in reads and s.get("trusted", True):
            t = (s.get("text") or "").replace("\n", "\\n")[:60]
            named.append(t)
    if named:
        print(f"  字符串: {named[:4]}")
    fn = dis.funcs.get(va)
    if fn:
        for i in fn.insns[:8]:
            print(f"    {i.va:08x}  {i.mnemonic:<8} {i.op_str}")
    print()
