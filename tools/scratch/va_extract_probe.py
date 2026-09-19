import os, re
ROOT = "/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-spec"
AUTO_LO, AUTO_HI = 0x401000, 0x462000
pats = [
    ("0x 前缀",   re.compile(r"0x0*([0-9a-fA-F]{4,8})")),
    ("fcn_/loc_/sub_", re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})")),
    ("裸 00xxxxxx", re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b")),
    ("VA 后",     re.compile(r"VA\s+0*([0-9a-fA-F]{6,8})")),
]
tot = {}
for name, pat in pats:
    s = set()
    for dp, _d, ns in os.walk(os.path.join(ROOT, "docs")):
        for n in ns:
            if n.endswith(".md"):
                t = open(os.path.join(dp, n), encoding="utf-8", errors="replace").read()
                for m in pat.finditer(t):
                    v = int(m.group(1), 16)
                    if AUTO_LO <= v < AUTO_HI:
                        s.add(v)
    tot[name] = s
    print(f"{name:16s} {len(s)} 个唯一地址")
union = set().union(*tot.values())
print(f"\n并集 {len(union)} 个")
# 只有 fcn_/loc_/sub_ 捕到的（说明 0x 前缀口径漏了这些）
only_named = tot["fcn_/loc_/sub_"] - tot["0x 前缀"]
print(f"仅靠 fcn_/loc_/sub_ 命中、0x 口径漏掉的：{len(only_named)}")
print("样例:", [hex(v) for v in list(only_named)[:10]])
only_bare = tot["裸 00xxxxxx"] - tot["0x 前缀"] - tot["fcn_/loc_/sub_"]
print(f"仅靠裸 00xxxxxx 命中：{len(only_bare)}  样例: {[hex(v) for v in list(only_bare)[:10]]}")
