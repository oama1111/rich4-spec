#!/usr/bin/env python3
"""列出快照 store/restore 函数里**不经 memcpy** 的标量直写（含目的偏移）。"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rich4dis as R  # noqa: E402

img = R.Image(); dis = R.Disassembler(img); dis.traverse()
BASE = 0x48CB80

for start, label in ((0x44808A, "store"), (0x448544, "restore")):
    fn = dis.funcs[start]
    print(f"\n===== 0x{start:06x} ({label}) —— 目的地址形如 [eax + 0x48xxxx] 的非 memcpy 访问")
    cur_off = None
    for i, x in enumerate(fn.insns):
        # 跟踪 `add eax, 0x48cb80` 之后的 `add eax, N`
        if x.mnemonic == "add" and x.op_str.startswith("eax,"):
            v = x.op_str.split(",")[1].strip()
            if re.fullmatch(r"0x[0-9a-f]+", v):
                iv = int(v, 16)
                if iv == BASE:
                    cur_off = 0
                    continue
                if cur_off is not None and iv < 0x10000:
                    cur_off = iv
                    continue
        if x.mem_addr is not None and BASE <= x.mem_addr < BASE + 0x2718:
            print(f"  [{i:4d}] 0x{x.va:08x}  {x.mnemonic:<8} {x.op_str}   → +0x{x.mem_addr - BASE:04x}")
        if x.is_call and x.target == 0x456DE8:
            cur_off = None
