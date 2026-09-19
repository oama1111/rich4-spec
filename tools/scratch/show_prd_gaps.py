import json, os, re
ROOT = "/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-spec"
REMAKE = "/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-remake"
AUTO_LO, AUTO_HI = 0x401000, 0x462000
pats = [re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
        re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
        re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b")]
def collect(paths):
    out = set()
    for p in paths:
        t = open(p, encoding="utf-8", errors="replace").read()
        for pat in pats:
            for m in pat.finditer(t):
                v = int(m.group(1), 16)
                if AUTO_LO <= v < AUTO_HI: out.add(v)
    return out
spec = set()
for dp,_d,ns in os.walk(os.path.join(ROOT,"docs")):
    for n in ns:
        if n.endswith(".md"):
            spec |= collect([os.path.join(dp,n)])
funcs = json.load(open(os.path.join(ROOT,"gen","functions.json"), encoding="utf-8"))
src = []
for dp,dirs,ns in os.walk(os.path.join(REMAKE,"packages")):
    dirs[:] = [d for d in dirs if d not in ("node_modules","dist")]
    for n in ns:
        if n.endswith(".ts"): src.append(os.path.join(dp,n))
va_lines = {}
for f in src:
    rel = os.path.relpath(f, REMAKE)
    for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        for pat in pats:
            for m in pat.finditer(line):
                v = int(m.group(1), 16)
                if AUTO_LO <= v < AUTO_HI: va_lines.setdefault(v, []).append((rel, i, line.strip()))
out = []
for fn in funcs:
    va = int(fn["va"],16); size = fn.get("size") or 0
    if va >= 0x450000: continue
    if any(v in spec for v in range(va, va+max(size,1))): continue
    w = va_lines.get(va)
    if not w: continue
    # 跳过「客户端表现层」那一大组，只看规则相关
    if all(x[0].startswith("packages/client") for x in w): continue
    out.append((size, va, w))
out.sort(key=lambda r: -r[0])
print(f"非 client 组：{len(out)} 个\n")
for size, va, w in out:
    print(f"########## 0x{va:06x}  {size}B  ##########")
    for rel, ln, line in w[:2]:
        print(f"  {rel}:{ln}")
        print(f"    {line[:150]}")
    print()
