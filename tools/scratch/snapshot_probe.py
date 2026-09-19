#!/usr/bin/env python3
"""把 `_rich4_store_current_state`（0x44808a）与 `restore_last_state`（0x448544）
里的每一次 memcpy 摘出来：目的偏移 / 大小 / 源地址。"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rich4dis as R  # noqa: E402

img = R.Image(); dis = R.Disassembler(img); dis.traverse()
byva = {}
for f in dis.funcs.values():
    for i, x in enumerate(f.insns):
        byva.setdefault(x.va, (f.insns, i))

for start in (0x44808A, 0x448544):
    fn = dis.funcs.get(start)
    print(f"\n===== 0x{start:06x}  {len(fn.insns)} insns  {fn.size} bytes  ends={fn.ends}")
    print("callees:", ", ".join(f"0x{c:x}" for c in sorted(fn.callees)))
    for i, x in enumerate(fn.insns):
        t = f"  -> 0x{x.target:x}" if x.is_call and x.target else ""
        print(f"[{i:4d}] {x.va:08x}  {x.mnemonic:<8} {x.op_str}{t}")
