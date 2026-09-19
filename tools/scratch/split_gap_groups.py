#!/usr/bin/env python3
"""
把 audit_prd_gaps 的「remake 已知、PRD 未提」清单切成 6 个工作包（按屏/模块分组），
每个包写一个 VA 列表文件，供子代理并行起草规格段落。

用法：python3 tools/scratch/split_gap_groups.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "scratch"))

# 组 → 归属的 client 文件（子串匹配）
GROUPS = [
    ("g1-shop-help-options", ["shop-screen", "help-screen", "options-pages", "options.ts", "options.test"]),
    ("g2-lottery-minigame", ["lottery-draw-screen", "lottery-screen", "wheel-screen", "minigame-screen", "magic-screen"]),
    ("g3-board-asset-hud", ["board-screen", "asset-sheet", "big-map-screen", "picking", "render.ts", "hud"]),
    ("g4-bail-monthly-stock", ["bail-screen", "monthly-screen", "bank-dynamic", "stock-screen", "shares-screen"]),
    ("g5-main-setup-god", ["main.ts", "ai-settings", "bgm-wiring", "setup.ts", "god-slot"]),
    ("g6-auction-cards-loop", ["auction-screen", "land-cards", "blocking"]),
]


def main() -> int:
    out = os.popen(f"cd {ROOT} && python3 tools/audit_prd_gaps.py --top 400").read()
    rows = []
    for line in out.split("\n"):
        m = re.match(r"^(0x[0-9a-f]{6})\s+(\d+)B\s+→\s+(\S+)\s+(\S+):(\d+)", line)
        if m:
            rows.append((m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5))))
    assigned = set()
    for name, keys in GROUPS:
        sel = [r for r in rows if any(k in r[3] for k in keys)]
        for r in sel:
            assigned.add(r[0])
        path = os.path.join(ROOT, "tools", "scratch", f"gap-{name}.txt")
        with open(path, "w", encoding="utf-8") as f:
            for r in sel:
                f.write(f"{r[0]} {r[1]:5d}B {r[2]:<18} {r[3]}:{r[4]}\n")
        print(f"{name:<26} {len(sel):3d} 个 / {sum(x[1] for x in sel):6d} 字节  → {path}")
    left = [r for r in rows if r[0] not in assigned]
    if left:
        print("\n未分组：")
        for r in left:
            print(f"  {r[0]} {r[1]:5d}B {r[2]:<18} {r[3]}:{r[4]}")
    print(f"\n合计 {len(rows)} 个，已分组 {len(assigned)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
