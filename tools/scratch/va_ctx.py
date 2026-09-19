#!/usr/bin/env python3
"""
给出某个 VA 在 remake 里被引用的**上下文**（含附近注释块）——「知识在哪里」。

用法：
    python3 tools/scratch/va_ctx.py 0x42d977 [0x42728e ...]
    python3 tools/scratch/va_ctx.py --all      # 读 audit_prd_gaps 的全表
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")
AUTO_LO, AUTO_HI = 0x401000, 0x462000

VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b"),
]


def walk(root, exts):
    out = []
    for dp, dirs, ns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git")]
        for n in ns:
            if n.endswith(exts):
                out.append(os.path.join(dp, n))
    return sorted(out)


def main() -> int:
    argv = sys.argv[1:]
    want = []
    for a in argv:
        if a.startswith("0x"):
            want.append(int(a, 16))
    src = [f for f in walk(os.path.join(REMAKE, "packages"), (".ts",)) if "/dist/" not in f]
    hits: dict[int, list[tuple[str, int, list[str]]]] = {v: [] for v in want}
    for f in src:
        rel = os.path.relpath(f, REMAKE)
        lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            found = set()
            for pat in VA_PATTERNS:
                for m in pat.finditer(line):
                    v = int(m.group(1), 16)
                    if v in hits:
                        found.add(v)
            for v in found:
                lo = max(0, i - 7)
                hits[v].append((rel, i + 1, lines[lo : i + 3]))

    for v in want:
        print("=" * 70)
        print(f"### 0x{v:06x}   （{len(hits[v])} 处引用）")
        for rel, lineno, ctx in hits[v][:4]:
            print(f"--- {rel}:{lineno}")
            for c in ctx:
                print("    " + c.rstrip())
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
