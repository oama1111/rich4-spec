#!/usr/bin/env python3
"""
rich4-spec · **数据表覆盖门禁**：`layout.json` 的 104 张 `table:data` 是否都被 PRD 提到

为什么单独成一条：数据表装的是**规则本身**（费率、价格、概率、年限、台词指针…），
比函数更接近「玩法细节」。`coverage-by-function.md` 那套按**函数**数的覆盖度
看不见它们 —— 本脚本补这一格，并且**可以直接当门禁**（漏一张就非零退出）。

★ 附带一条方法学结论（第 54 条查清）：**`table:code` 不能当覆盖审计的单位**。
`layout.json` 的 64 张 `table:code` 里有：
  · **子切片**：`0x475de1` = 道具表 `0x475dd5` 的第 3 项起（`0x475dd5 + 3*4`）、
    `0x475e70` = 新闻表 `0x475e24[36]` 的第 19 项起 —— 两张真值表 PRD 都写过，
    而 layout 根本没列出真值基址；
  · **CRT**：`0x4899b0`（55 项，全部指向 0x45Fxxx 库区）；
  · **拼凑**：`0x475ee0` 的头 4 项其实是**字符串**地址（0x465400、+9、+0x12…），
    `0x466706` 的「指针」是 0x420041/0x440043 这种递增模式（数据）。
⇒ 所以「59/64 未提到」是**工具噪声**，不是缺口。要判分派表，
   得按**真值基址 + 目标函数**判，不能按 layout 的切片判。

用法
----
    python3 tools/audit_data_tables.py            # 全过 → 0；漏一张 → 1
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DOCS = os.path.join(ROOT, "docs")
LAYOUT = os.path.join(ROOT, "gen", "layout.json")

VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b"),
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
                out.add(int(m.group(1), 16))
    return out


def walk_md(root):
    files = []
    for dp, _d, ns in os.walk(root):
        for n in ns:
            if n.endswith(".md"):
                files.append(os.path.join(dp, n))
    return sorted(files)


def main() -> int:
    spec = collect(walk_md(SPEC_DOCS))
    layout = json.load(open(LAYOUT, encoding="utf-8"))
    tables = [e for e in layout if e.get("kind") == "table:data"]
    miss = []
    for e in tables:
        va, size = e["va"], e.get("size") or 0
        if not any(v in spec for v in range(va, va + max(size, 1))):
            miss.append((va, size))
    print(f"table:data 共 {len(tables)} 张；PRD 未提到 {len(miss)} 张")
    for va, size in sorted(miss, key=lambda x: -x[1]):
        print(f"  ✘ 0x{va:06x}  {size} 字节")
    if miss:
        print("⇒ 有数据表没进 PRD —— 数据表装的是规则，请补进对应 systems/*.md")
        return 1
    print("✅ 104/104 数据表都在 PRD 里")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
