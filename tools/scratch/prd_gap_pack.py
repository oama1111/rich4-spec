#!/usr/bin/env python3
"""
rich4-spec · 「remake 已知、PRD 未提」函数的**合并档案**（每函数一段）。

段落内容：
  1. VA / 名字 / 尺寸 / 指令数
  2. callees（带名）、push 的字符串、触碰的全局
  3. 汇编全文（长函数截断到 40 条）
  4. remake 侧的引用上下文（注释块）—— 知识在哪里

用法：
    python3 tools/scratch/prd_gap_pack.py > tools/scratch/prd-gap-pack.txt
    python3 tools/scratch/prd_gap_pack.py 0x42d977 0x42728e
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")
AUTO_LO, AUTO_HI = 0x401000, 0x462000
MAX_ASM = 40

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


def load_db():
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


def main() -> int:
    argv = [a for a in sys.argv[1:] if a.startswith("0x")]
    if argv:
        want = sorted(int(a, 16) for a in argv)
    else:
        spec = set()
        for p in walk(os.path.join(ROOT, "docs"), (".md",)):
            spec |= set(range(0, 1))  # placeholder
        spec_text = ""
        for p in walk(os.path.join(ROOT, "docs"), (".md",)):
            spec_text += open(p, encoding="utf-8", errors="replace").read()
        spec_vas = set()
        for pat in VA_PATTERNS:
            for m in pat.finditer(spec_text):
                spec_vas.add(int(m.group(1), 16))
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
        want = []
        for fn in funcs:
            va = int(fn["va"], 16)
            size = fn.get("size") or 0
            if va >= 0x450000:
                continue
            if any(v in spec_vas for v in range(va, va + max(size, 1))):
                continue
            if where.get(va):
                want.append(va)
        want.sort()

    names, body = load_db()
    strs = {}
    for s in json.load(open(os.path.join(ROOT, "gen", "strings.json"), encoding="utf-8")):
        if s.get("trusted"):
            strs[int(s["va"])] = s["text"]

    # remake 引用上下文
    src = [f for f in walk(os.path.join(REMAKE, "packages"), (".ts",)) if "/dist/" not in f]
    ctx: dict[int, list[tuple[str, int, list[str]]]] = {v: [] for v in want}
    for f in src:
        rel = os.path.relpath(f, REMAKE)
        lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            found = set()
            for pat in VA_PATTERNS:
                for m in pat.finditer(line):
                    v = int(m.group(1), 16)
                    if v in ctx:
                        found.add(v)
            for v in found:
                ctx[v].append((rel, i + 1, lines[max(0, i - 8) : i + 2]))

    for va in want:
        lines = body.get(va, [])
        print("=" * 78)
        print(f"### 0x{va:06x}  {names.get(va, '?')}   {len(lines)} 条")
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
            print("callees: " + ", ".join(uniq[:26]))
        if pushes:
            print("strings: " + " | ".join(pushes[:12]))
        if globs:
            print("globals: " + ", ".join(globs[:16]))
        print("--- asm ---")
        for ln in lines[:MAX_ASM]:
            print(ln)
        if len(lines) > MAX_ASM:
            print(f"  ... 余 {len(lines) - MAX_ASM} 条")
        print("--- remake 引用 ---")
        for rel, lineno, c in ctx[va][:3]:
            print(f"[{rel}:{lineno}]")
            for x in c:
                print("  " + x.rstrip())
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
