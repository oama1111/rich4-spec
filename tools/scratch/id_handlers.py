import json, sys
sys.path.insert(0, 'tools')
import rich4dis as R

img = R.Image(); dis = R.Disassembler(img); dis.traverse(verbose=False)
strings = json.load(open("gen/strings.json", encoding="utf-8"))
if not isinstance(strings, list):
    strings = strings.get("strings", [])
by_va = {}
for s in strings:
    a = s.get("va")
    if a is None: continue
    a = int(a, 16) if isinstance(a, str) else a
    by_va[a] = s.get("text") or ""

for va in (0x42608f, 0x4267a4, 0x426c2e, 0x42704e, 0x434492):
    fn = dis.funcs[va]
    imm = set()
    calls = set()
    for i in fn.insns:
        if i.imm_data:
            imm.add(i.imm_data)
        if i.is_call and i.op_str.startswith("0x"):
            try:
                calls.add(int(i.op_str, 16))
            except ValueError:
                pass
    texts = []
    for a in imm:
        if a in by_va:
            texts.append(by_va[a].replace("\n", "\\n")[:40])
    # 也看它调用的函数里引用的串（一层）
    for c in list(calls)[:40]:
        cf = dis.funcs.get(c)
        if not cf: continue
        for i in cf.insns:
            if i.imm_data and i.imm_data in by_va:
                texts.append("[callee] " + by_va[i.imm_data].replace("\n", "\\n")[:40])
    uniq = []
    for t in texts:
        if t not in uniq:
            uniq.append(t)
    print(f"########## 0x{va:06x}  {len(fn.insns)} 条 ##########")
    print(f"  reads(全局): {[hex(x) for x in list(fn.reads)[:8]]}")
    print(f"  字符串线索: {uniq[:8]}")
    print()
