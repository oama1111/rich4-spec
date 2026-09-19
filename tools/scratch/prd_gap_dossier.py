#!/usr/bin/env python3
"""
rich4-spec · 为 audit_prd_gaps.py 报出的「remake 已知、PRD 未提」函数做档案。

对每个 VA 输出：
  - 尺寸 / 指令数 / 结尾类型
  - 被调用者（用 db.txt 的 `→ name` 注解解析）
  - push 的字符串常量（用 gen/strings.json 解析）
  - 触碰的全局 `[0x...]`（前 12 个）
  - 引用它的 remake 文件:行 与附近的注释块（语义线索）

用法：
    python3 tools/scratch/prd_gap_dossier.py > tools/scratch/prd-gap-dossier.txt
    python3 tools/scratch/prd_gap_dossier.py --va 0x42d977
"""
from __future__ import annotations

import json
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


def load_db():
    """返回 (函数名表 {va: name}, 逐函数行表 {va: [lines]})"""
    names: dict[int, str] = {}
    body: dict[int, list[str]] = {}
    cur = None
    hdr = re.compile(r"^# 0x([0-9a-fA-F]+)\s+(\S+)")
    with open(os.path.join(ROOT, "gen", "db.txt"), encoding="utf-8", errors="replace") as f:
        for line in f:
            m = hdr.match(line)
            if m:
                cur = int(m.group(1), 16)
                names[cur] = m.group(2)
                body[cur] = []
                continue
            if cur is not None and line.startswith("  "):
                body[cur].append(line.rstrip("\n"))
    return names, body


def load_strings():
    out = {}
    for s in json.load(open(os.path.join(ROOT, "gen", "strings.json"), encoding="utf-8")):
        if s.get("trusted"):
            out[int(s["va"])] = s["text"]
    return out


def main() -> int:
    argv = sys.argv[1:]
    if "--va" in argv:
        want = {int(argv[argv.index("--va") + 1], 16)}
    else:
        spec = collect(walk(os.path.join(ROOT, "docs"), (".md",)))
        funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
        src = [f for f in walk(os.path.join(REMAKE, "packages"), (".ts",)) if "/dist/" not in f]
        where: dict[int, list[tuple[str, int]]] = {}
        for f in src:
            rel = os.path.relpath(f, REMAKE)
            for lineno, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
                for pat in VA_PATTERNS:
                    for m in pat.finditer(line):
                        v = int(m.group(1), 16)
                        if AUTO_LO <= v < AUTO_HI:
                            where.setdefault(v, []).append((rel, lineno))
        want = set()
        for fn in funcs:
            va = int(fn["va"], 16)
            size = fn.get("size") or 0
            if va >= 0x450000:
                continue
            if any(v in spec for v in range(va, va + max(size, 1))):
                continue
            if where.get(va):
                want.add(va)

    names, body = load_db()
    strs = load_strings()

    for va in sorted(want):
        lines = body.get(va, [])
        print(f"===== 0x{va:06x}  {names.get(va, '?')}  {len(lines)} 条 =====")
        callees: list[str] = []
        pushes: list[str] = []
        globs: list[str] = []
        for ln in lines:
            m = re.search(r"→ (\S+)", ln)
            if m:
                callees.append(m.group(1))
            for mm in re.finditer(r"push\s+0x([0-9a-fA-F]+)", ln):
                v = int(mm.group(1), 16)
                if v in strs:
                    pushes.append(f"0x{v:06x}={strs[v]!r}")
            for mm in re.finditer(r"\[0x([0-9a-fA-F]{5,8})\]", ln):
                g = "0x" + mm.group(1).lower().zfill(8)
                if g not in globs:
                    globs.append(g)
        if callees:
            uniq = []
            for c in callees:
                if c not in uniq:
                    uniq.append(c)
            print("  callees: " + ", ".join(uniq[:24]))
        if pushes:
            print("  strings: " + " | ".join(pushes[:10]))
        if globs:
            print("  globals: " + ", ".join(globs[:14]))
        for ln in lines[:14]:
            print("   " + ln)
        if len(lines) > 14:
            print(f"    ... 余 {len(lines) - 14} 条")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
