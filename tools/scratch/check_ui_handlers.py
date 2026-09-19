"""机械核对 ui.md §一 的「42 个处理器」清单。

难点：注册调用 `call 0x4018e7` 有几条**跳转汇入**的路径
（例：`push 0 / push 0x42608f / jmp 0x42839c`，而 call 在 0x42839c），
所以「取紧邻前一条 push」会漏。这里改成**沿控制流向后回溯**收集 push 立即数。
"""
import os, re, sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image(); dis = R.Disassembler(img); dis.traverse(verbose=False)
lines = {}
for f in dis.funcs:
    for i in dis.funcs[f].insns:
        lines[i.va] = (i.mnemonic, i.op_str)
order = sorted(lines)

def prev(va):
    i = order.index(va) if va in lines else -1
    return order[i-1] if i > 0 else None

# 建立「谁跳到 x」的反向表（直接跳转）
jmps = {}
for va, (mn, op) in lines.items():
    if mn == "jmp" and op.startswith("0x"):
        try:
            t = int(op, 16)
        except ValueError:
            continue
        jmps.setdefault(t, []).append(va)

sites = sorted(k for k, v in lines.items() if v[0] == "call" and "0x4018e7" in v[1])
print(f"`call 0x4018e7` 共 {len(sites)} 处")

def collect_pushes(site, budget=10):
    """沿直线前驱 + 跳转前驱回溯，收集 push 立即数（代码段内的）。"""
    out, seen, queue = [], set(), [site]
    while queue:
        va = queue.pop(0)
        cur = va
        for _ in range(budget):
            cur = prev(cur)
            if cur is None or cur in seen:
                break
            seen.add(cur)
            mn, op = lines[cur]
            if mn == "push" and op.startswith("0x"):
                try:
                    h = int(op, 16)
                except ValueError:
                    break
                if 0x401000 <= h < 0x462000:
                    out.append(h)
                break
            if mn in ("jmp",):
                if op.startswith("0x"):
                    try:
                        queue.append(int(op, 16))
                    except ValueError:
                        pass
                break
            if mn == "ret" or mn == "call":
                break
            if op.startswith("jmp ") or mn.startswith("j"):
                break
        # 也考虑直接跳到本地址的路径
        queue.extend(jmps.get(va, []))
    return out

handlers = set()
for site in sites:
    for h in collect_pushes(site):
        handlers.add(h)
print(f"解析出的处理器（去重）：{len(handlers)} 个")

ui = open("docs/systems/ui.md", encoding="utf-8").read().lower()
missing = sorted(h for h in handlers if f"{h:06x}" not in ui and f"{h:08x}" not in ui)
print(f"\n★ 注册了、但 ui.md 一次都没提的：{len(missing)} 个")
for h in missing:
    print(f"  0x{h:06x}")
