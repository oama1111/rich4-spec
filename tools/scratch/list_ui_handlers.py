"""列出全部注册到 0x4018e7 的模态处理器（含跳转汇入路径），并标注 ui.md 是否已列。"""
import re, sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image(); dis = R.Disassembler(img); dis.traverse(verbose=False)
lines = {}
for f in dis.funcs:
    for i in dis.funcs[f].insns:
        lines[i.va] = (i.mnemonic, i.op_str)
order = sorted(lines)
def prev(va):
    if va not in lines: return None
    i = order.index(va)
    return order[i-1] if i > 0 else None
jmps = {}
for va, (mn, op) in lines.items():
    if mn == "jmp" and op.startswith("0x"):
        try: jmps.setdefault(int(op, 16), []).append(va)
        except ValueError: pass
sites = sorted(k for k, v in lines.items() if v[0] == "call" and "0x4018e7" in v[1])

def paths(site, budget=10):
    out, seen, queue = [], set(), [(site, None)]
    while queue:
        va, origin = queue.pop(0)
        cur = va
        for _ in range(budget):
            cur = prev(cur)
            if cur is None or cur in seen: break
            seen.add(cur)
            mn, op = lines[cur]
            if mn == "push" and op.startswith("0x"):
                try: h = int(op, 16)
                except ValueError: break
                if 0x401000 <= h < 0x462000:
                    out.append((h, cur, origin))
                break
            if mn == "jmp":
                if op.startswith("0x"):
                    try: queue.append((int(op, 16), cur))
                    except ValueError: pass
                break
            if mn in ("ret", "call") or mn.startswith("j"): break
        queue.extend((j, site) for j in jmps.get(va, []))
    return out

rows = {}
for site in sites:
    for h, push_va, origin in paths(site):
        rows.setdefault(h, set()).add(origin or site)

ui = open("docs/systems/ui.md", encoding="utf-8").read().lower()
print(f"注册点 {len(sites)} 处，处理器 {len(rows)} 个\n")
print("| 处理器 | 注册路径（push 所在 / 汇入点） | ui.md 已列 |")
print("|---|---|---|")
for h in sorted(rows):
    listed = f"{h:06x}" in ui or f"{h:08x}" in ui
    pts = sorted(rows[h])
    ptxt = ", ".join(f"`0x{p:06x}`" for p in pts[:4])
    print(f"| `0x{h:06x}` | {ptxt} | {'✔' if listed else '**✘**'} |")
