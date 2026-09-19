#!/usr/bin/env python3
"""对 `0x44b896`（神明加持档位）的每个调用点，从紧邻的两次 `push` 反推
(arg0, arg1) → 用法（reward / penalty / misfortune），供与事件表对照。"""
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rich4dis as R  # noqa: E402

img = R.Image(); dis = R.Disassembler(img); dis.traverse()
KIND = {(0, 0): "reward(+0x46 獎金口吻)", (0, 1): "penalty(+0x46 罰金口吻)", (1, 1): "misfortune(+0x48 福運)"}
for f in sorted(dis.funcs.values(), key=lambda x: x.va):
    for i, x in enumerate(f.insns):
        if not (x.is_call and x.target == 0x44B896):
            continue
        # 往回找两次 push（跳过中间的算术/取址指令）
        args = []
        j = i - 1
        while j >= 0 and len(args) < 2:
            p = f.insns[j]
            if p.mnemonic == "push":
                m = re.fullmatch(r"0x([0-9a-f]+)|(\d+)", p.op_str.strip())
                args.append(int(m.group(1), 16) if m and m.group(1) else (int(m.group(2)) if m else None))
            elif p.mnemonic in ("call", "ret"):
                break
            j -= 1
        args.reverse()  # [arg0, arg1]
        key = tuple(a or 0 for a in args)
        print(f"函数 0x{f.va:06x}  调用 0x{x.va:08x}  push={args} → {KIND.get(key, '?')}")
