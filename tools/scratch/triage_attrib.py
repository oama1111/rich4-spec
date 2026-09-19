"""给桶 4（真·遗漏）的每个函数做「系统归属」推断：看它的调用者被哪份规格提到。"""
import json, os, re, sys
sys.path.insert(0, 'tools')
import rich4dis as R

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
HEX = re.compile(r"0x0*([0-9a-fA-F]{4,8})")

va_files = {}
for dp, _d, ns in os.walk(os.path.join(ROOT, "docs")):
    for n in ns:
        if not n.endswith(".md"): continue
        path = os.path.join(dp, n)
        t = open(path, encoding="utf-8", errors="replace").read()
        for m in HEX.finditer(t):
            v = int(m.group(1), 16)
            if 0x401000 <= v < 0x462000:
                va_files.setdefault(v, set()).add(n)

strs = json.load(open(os.path.join(ROOT, "gen", "strings.json"), encoding="utf-8"))
if not isinstance(strs, list):
    strs = strs.get("strings", [])
str_by_va = {}
for s in strs:
    a = s.get("va")
    if a is None: continue
    a = int(a, 16) if isinstance(a, str) else a
    str_by_va.setdefault(a, s.get("text") or "")

def covered(va, size):
    return any(v in va_files for v in range(va, va + max(size, 1)))

rows = []
for f in funcs:
    va = int(f["va"], 16); size = f.get("size") or 0
    if va >= 0x450000: continue
    if covered(va, size): continue
    if len(f.get("callers", [])) == 0: continue
    rows.append(f)
rows.sort(key=lambda f: -(f.get("size") or 0))

print(f"{'VA':>10} {'size':>5}  推断系统（由调用者/被调用者命中哪份规格）")
for f in rows:
    va = int(f["va"], 16)
    files = set()
    for c in f.get("callers", []) + f.get("callees", []):
        files |= va_files.get(int(c, 16), set())
    reads = [int(x, 16) for x in f.get("reads", [])]
    txt = [str_by_va.get(a, "") for a in reads]
    txt = [t.replace("\n", "\\n")[:26] for t in txt if t]
    # 直接读到的字符串也算线索
    print(f"0x{va:06x} {f.get('size'):5d}  {sorted(files) if files else '—'}   {txt[:3]}")
