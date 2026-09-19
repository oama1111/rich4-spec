#!/usr/bin/env python3
"""
rich4-spec · **PRD 缺口工作单**：remake 已经知道、而 PRD 一次没提的函数。

`audit_spec_coverage.py` 给出总量（当前 240 个 / 37KB）。本脚本回答"先写哪一个"：
按**提到它的 remake 文件**归组 —— 那个文件就是"知识在哪里"，
也就指明了该搬进哪份规格（`rules/toll.ts` → `land-rent.md`，
`rules/bankruptcy.ts` → `bank.md`，`loaders/map.ts` → `map-format.md` …）。

用法
----
    python3 tools/audit_prd_gaps.py                  # 按目标规格分组的总览
    python3 tools/audit_prd_gaps.py --group bank     # 看某一组（按文件名子串）
    python3 tools/audit_prd_gaps.py --top 30         # 只按尺寸排前 N
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")
AUTO_LO, AUTO_HI = 0x401000, 0x462000

VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b"),
]

# remake 模块 → 该搬进的规格文件（按模块路径前缀匹配，先匹配先生效）
TARGETS = [
    ("rules/toll", "land-rent.md"), ("rules/rent", "land-rent.md"),
    ("rules/bankruptcy", "bank.md"), ("rules/payment", "bank.md"),
    ("places/bank", "bank.md"), ("rules/interest", "bank.md"),
    ("rules/cards", "cards.md"), ("cards/", "cards.md"),
    ("rules/tools", "tools.md"), ("places/shop", "tools.md"),
    ("events/news", "news.md"), ("events/fortune", "fortune.md"),
    ("places/stock", "stocks.md"), ("ai/stock", "stocks.md"),
    ("rules/stock", "stocks.md"), ("places/commercial", "stocks.md"),
    ("rules/god", "gods.md"), ("objects.ts", "gods.md"),
    ("places/magic", "magic-house.md"),
    ("places/lottery", "places.md"), ("rules/confinement", "places.md"),
    ("small-game", "small-games.md"),
    ("rules/map", "map-format.md"), ("loaders/map", "map-format.md"),
    ("loaders/save", "save-format.md"), ("rules/time-machine", "save-format.md"),
    ("loaders/save-writer", "save-format.md"),
    ("ai/", "ai.md"), ("rules/auction", "magic-house.md"),
    ("client/", "ui.md"), ("render", "render-api.md"),
    ("rules/animation", "animation.md"), ("sound", "sound-effects.md"),
    ("dialogue", "dialogue-voice.md"), ("voice", "dialogue-voice.md"),
    ("rules/blocking", "game-loop.md"), ("state/reduce", "game-loop.md"),
    ("rules/special-actors", "ai.md"), ("rules/npc", "ai.md"),
    ("rules/facility", "land-rent.md"), ("rules/purchase", "land-rent.md"),
    ("rules/economy", "economy.md"),
]


def collect(paths):
    out = set()
    for p in paths:
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for pat in VA_PATTERNS:
            for m in pat.finditer(text):
                v = int(m.group(1), 16)
                if AUTO_LO <= v < AUTO_HI:
                    out.add(v)
    return out


def walk(root, exts):
    files = []
    for dp, dirs, ns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git")]
        for n in ns:
            if n.endswith(exts):
                files.append(os.path.join(dp, n))
    return sorted(files)


def target_of(rel):
    for key, doc in TARGETS:
        if key in rel:
            return doc
    return "(未归类)"


def main() -> int:
    argv = sys.argv[1:]
    group = None
    if "--group" in argv:
        group = argv[argv.index("--group") + 1]
    top = None
    if "--top" in argv:
        top = int(argv[argv.index("--top") + 1])

    spec = collect(walk(os.path.join(ROOT, "docs"), (".md",)))
    funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
    src_files = walk(os.path.join(REMAKE, "packages"), (".ts",))
    src_files = [f for f in src_files if "/dist/" not in f]

    # VA → 提到它的 remake 文件（含行号）
    va_where: dict[int, list[tuple[str, int]]] = {}
    for f in src_files:
        rel = os.path.relpath(f, REMAKE)
        for lineno, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
            for pat in VA_PATTERNS:
                for m in pat.finditer(line):
                    v = int(m.group(1), 16)
                    if AUTO_LO <= v < AUTO_HI:
                        va_where.setdefault(v, []).append((rel, lineno))

    rows = []
    for fn in funcs:
        va = int(fn["va"], 16)
        size = fn.get("size") or 0
        if va >= 0x450000:
            continue
        if any(v in spec for v in range(va, va + max(size, 1))):
            continue
        where = va_where.get(va) or []
        if not where:
            continue          # 两边都不知道 → 不属本工作单
        rows.append({"va": va, "size": size, "where": where,
                     "target": target_of(where[0][0]),
                     "callers": len(fn.get("callers", [])),
                     "insn": fn.get("insn_count", 0)})

    rows.sort(key=lambda r: -r["size"])
    print(f"remake 已知、PRD 未提的函数：{len(rows)} 个 / {sum(r['size'] for r in rows)} 字节\n")

    if top:
        print(f"=== 按尺寸前 {top} ===")
        for r in rows[:top]:
            rel, ln = r["where"][0]
            print(f"0x{r['va']:06x} {r['size']:5d}B  → {r['target']:<18} {rel}:{ln}")
        return 0

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["target"], []).append(r)
    print(f"{'目标规格':<20} {'函数':>5} {'字节':>7}  最大的几个")
    for doc, items in sorted(groups.items(), key=lambda kv: -sum(x["size"] for x in kv[1])):
        if group and group not in doc:
            continue
        big = ", ".join(f"0x{x['va']:06x}({x['size']}B)" for x in items[:3])
        print(f"{doc:<20} {len(items):5d} {sum(x['size'] for x in items):7d}  {big}")
    if group:
        print(f"\n=== 组「{group}」明细 ===")
        for r in sorted(groups.get(next((d for d in groups if group in d), ""), []),
                        key=lambda r: -r["size"]):
            rel, ln = r["where"][0]
            print(f"0x{r['va']:06x} {r['size']:5d}B  {rel}:{ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
