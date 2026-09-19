#!/usr/bin/env python3
"""列出 0x44808a（store）与 0x448544（restore）里每一次 memcpy 的
(目的偏移, 大小, 源地址)，并汇总覆盖的字节。
"""
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rich4dis as R  # noqa: E402

img = R.Image(); dis = R.Disassembler(img); dis.traverse()

def lit(s):
    s = s.strip()
    m = re.fullmatch(r"0x([0-9a-f]+)", s)
    if m:
        return int(m.group(1), 16)
    return int(s, 10) if re.fullmatch(r"[0-9]+", s) else None

def regions(start):
    fn = dis.funcs[start]
    out = []
    for k, x in enumerate(fn.insns):
        if not (x.is_call and x.target == 0x456DE8):
            continue
        pushes = []
        dst = None
        for j in range(k - 1, max(-1, k - 40), -1):
            p = fn.insns[j]
            if p.mnemonic == "push":
                pushes.append(p.op_str)
                if len(pushes) == 3:
                    break
            elif p.mnemonic == "add" and p.op_str.startswith("eax,"):
                if dst is None:
                    dst = lit(p.op_str.split(",")[1])
        pushes.reverse()
        size = lit(pushes[0]) if pushes else None
        src = lit(pushes[1]) if len(pushes) > 1 else None
        out.append((x.va, dst, size, src))
    return out

for start in (0x44808A, 0x448544):
    print(f"\n===== 0x{start:06x}  memcpy 列表（含 dst 偏移） =====")
    total = 0
    for va, dst, size, src in regions(start):
        ds = "?" if dst is None else f"0x{dst:04x}"
        ss = "?" if size is None else f"0x{size:04x}"
        cs = "?" if src is None else f"0x{src:08x}"
        print(f"  0x{va:08x}  dst+{ds}  size {ss} ({size})  src {cs}")
        total += size or 0
    print(f"  合计 {total} 字节")
