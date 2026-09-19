#!/usr/bin/env python3
"""
rich4-spec · **阶段 1 的强口径缺口**：`call` / `jmp` 指向、而 PRD 一次没提的函数。

为什么需要（2026-09-18 新增）
--------------------------
`audit_spec_coverage.py` 的第 4 桶（「有调用者却真遗漏」）用的是
`gen/functions.json` 的 **`callers` 字段** —— 而那个字段是**递归遍历的副产品**，
已知不可靠（实测：`0x43e01e`、`0x403396`、`0x4221c0` 等在代码里明明有 `call 0x…`，
`callers` 却是空数组）。于是第 4 桶长期报 **0**，制造了「阶段 1 已经收口」的**假象**。

本工具换成**文本口径**：直接扫 `gen/db.txt` 里所有 `call 0x…` / `jmp 0x…` 的目标，
再判断「目标所在的宿主函数」有没有在 `docs/**/*.md` 里出现过。
只依赖反汇编文本，不依赖任何推断出来的图结构。

两档口径（**只有第一档是硬信号**）
--------------------------------
| 档 | 判据 | 含义 |
|---|---|---|
| **CALL** | 至少被**一处 `call`** 指向 | ★ 真信号：那是货真价实的子程序入口 |
| JMP | 只被 `jmp` 指向（无任何 `call`）| 待分类：**尾调用**（真函数）与**函数内跳转/遍历器切分产物**混在一起 |

`--strict` 只对 **CALL 档**非零退出；**JT 档**要另加 `--strict-jt`（它的口径更宽，
先把清单吃掉再开）。

其它口径
--------
· 宿主函数表 = `gen/functions.json`（1,560 条），目标地址归到**包含它的那个函数**。
· 「提到」= 宿主区间 `[va, va+size)` 内任一地址出现在 `docs/**/*.md`（
  四种写法都认，与 `audit_spec_coverage.py` 保持一致）。
· **排除 `va >= 0x450000`**（CRT / Open Watcom 运行库区，与玩法无关）。

用法
----
    python3 tools/audit_call_targets.py                 # 总览 + top 20
    python3 tools/audit_call_targets.py --min-size 64
    python3 tools/audit_call_targets.py --strict        # CALL 档非空则非零退出（门禁）
    python3 tools/audit_call_targets.py --strict-jt     # 再把 JT 档也当硬信号（清单吃完后开）
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO_LO, AUTO_HI = 0x401000, 0x462000
LIB_LO = 0x450000
OUT = os.path.join(ROOT, "tools", "scratch", "gap-call-targets.txt")

# 与 audit_spec_coverage.py 保持**逐条一致**的四种写法
VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_|ref_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b(00[0-9a-fA-F]{6})\b"),
    re.compile(r"\b(0{2}4[0-9a-fA-F]{5})\b"),
]

CALL_RE = re.compile(r"\bcall\s+0x([0-9a-fA-F]{5,8})")
JMP_RE = re.compile(r"\bjmp\s+0x([0-9a-fA-F]{5,8})")
HDR_RE = re.compile(r"^# 0x([0-9a-fA-F]+)\s+(\S+)")


def spec_vas() -> set[int]:
    out: set[int] = set()
    for dp, dirs, ns in os.walk(os.path.join(ROOT, "docs")):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for n in ns:
            if not n.endswith(".md"):
                continue
            text = open(os.path.join(dp, n), encoding="utf-8", errors="replace").read()
            for pat in VA_PATTERNS:
                for m in pat.finditer(text):
                    v = int(m.group(1), 16)
                    if AUTO_LO <= v < AUTO_HI:
                        out.add(v)
    return out


def main() -> int:
    argv = sys.argv[1:]
    strict = "--strict" in argv
    # ★ JT 档（跳表成员）单独一个硬开关：它的口径比 CALL 档宽（含遍历器切分出的
    #   片段与"表指向函数内部"的情形），先把清单吃掉再开。
    strict_jt = "--strict-jt" in argv
    min_size = 0
    if "--min-size" in argv:
        min_size = int(argv[argv.index("--min-size") + 1])

    funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
    starts = sorted(((int(f["va"], 16), f.get("size") or 0) for f in funcs))

    calls: dict[int, int] = {}
    jmps: dict[int, int] = {}
    host_of: dict[int, set[str]] = {}
    host = ""
    for line in open(os.path.join(ROOT, "gen", "db.txt"), encoding="utf-8", errors="replace"):
        h = HDR_RE.match(line)
        if h:
            host = h.group(2)
            continue
        for rx, bucket in ((CALL_RE, calls), (JMP_RE, jmps)):
            m = rx.search(line)
            if not m:
                continue
            v = int(m.group(1), 16)
            if AUTO_LO <= v < AUTO_HI:
                bucket[v] = bucket.get(v, 0) + 1
                host_of.setdefault(v, set()).add(host)

    spec = spec_vas()

    def owner(t: int):
        best = None
        for va, size in starts:
            if va > t:
                break
            if t < va + max(size, 1):
                best = (va, size)
        return best

    call_rows: list[tuple[int, int, int, int]] = []
    jmp_rows: list[tuple[int, int, int, int]] = []
    for t in sorted(set(calls) | set(jmps)):
        o = owner(t)
        if o is None:
            continue
        va, size = o
        if va >= LIB_LO or size < min_size:
            continue
        if any(v in spec for v in range(va, va + max(size, 1))):
            continue
        row = (va, size, calls.get(t, 0), jmps.get(t, 0))
        (call_rows if calls.get(t) else jmp_rows).append(row)

    # ★ JT 档：**跳表成员**（`jmp dword [表 + i*4]` 的处理器）。这是第三种入口形态 ——
    #   游戏里所有状态机/分派器的处理器都靠它进入，`call` 口径查不出来。
    #
    #   ★ 判「有没有被规格收」用的是**包含链**口径：一个成员算覆盖，当且仅当
    #   **包含它的任一层函数区间**在 `docs/**` 里出现过。原因：`functions.json` 里
    #   同一个真函数常被切成若干「碎片」，只按最内层判会把「已写过的函数内部被切碎」
    #   误报成缺口（实测：最内层口径 60 个 → 包含链口径 27 个）。
    jt_rows: list[tuple[int, int, int, int]] = []
    jt_inner_only = 0
    jt_path = os.path.join(ROOT, "gen", "jumptables.json")
    if os.path.exists(jt_path):
        members = set()
        for tbl in json.load(open(jt_path, encoding="utf-8")):
            for e in tbl.get("entries", []):
                v = int(e, 16)
                if AUTO_LO <= v < LIB_LO:
                    members.add(v)
        for t in sorted(members):
            ch = [c for c in starts if c[0] <= t < c[0] + max(c[1], 1)]
            if not ch:
                continue
            inner = ch[-1]
            if inner[0] >= LIB_LO or inner[1] < min_size:
                continue
            if any(v in spec for v in range(inner[0], inner[0] + max(inner[1], 1))):
                continue
            if any(
                any(v in spec for v in range(va, va + max(size, 1))) for va, size in ch
            ):
                jt_inner_only += 1          # 最内层碎片没提，但外层函数提过 → 不算缺口
                continue
            jt_rows.append((inner[0], inner[1], 0, 0))
        if jt_inner_only:
            print(
                f"  （另有 {jt_inner_only} 个跳表成员只差在「碎片 vs 外层函数」口径 —— "
                f"它们落在**已写过的函数内部**，不计缺口）"
            )

    def dedup(rows):
        seen: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for r in rows:
            k = (r[0], r[1])
            if k in seen:
                a = seen[k]
                seen[k] = (a[0], a[1], a[2] + r[2], a[3] + r[3])
            else:
                seen[k] = r
        return sorted(seen.values(), key=lambda x: -x[1])

    call_rows, jmp_rows, jt_rows = dedup(call_rows), dedup(jmp_rows), dedup(jt_rows)
    c_bytes = sum(r[1] for r in call_rows)
    j_bytes = sum(r[1] for r in jmp_rows)
    t_bytes = sum(r[1] for r in jt_rows)
    print(f"【CALL 档 ★ 真信号】被 `call` 指向、而 PRD 未提的函数：**{len(call_rows)} 个 / {c_bytes} 字节**")
    for va, size, c, j in call_rows[:20]:
        cs = sorted(host_of.get(va, set()))[:3]
        print(f"  0x{va:06x} {size:5d}B  call×{c}  ← {', '.join(cs) if cs else '(无)'}")
    print(f"【JT 档 ★ 真信号】是**跳表成员**、而 PRD 未提的函数：**{len(jt_rows)} 个 / {t_bytes} 字节**"
          f"（状态机/分派器的处理器；`call` 口径查不出来）")
    for va, size, c, j in jt_rows[:12]:
        print(f"  0x{va:06x} {size:5d}B")
    print(f"【JMP 档 待分类】只被 `jmp` 指向：**{len(jmp_rows)} 个 / {j_bytes} 字节**"
          f"（尾调用与遍历器切分产物混在一起，需逐个看）")
    for va, size, c, j in jmp_rows[:8]:
        cs = sorted(host_of.get(va, set()))[:3]
        print(f"  0x{va:06x} {size:5d}B  jmp×{j}  ← {', '.join(cs) if cs else '(无)'}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# CALL 档（真信号）\n")
        for va, size, c, j in call_rows:
            cs = sorted(host_of.get(va, set()))[:4]
            f.write(f"0x{va:06x} {size:5d}B  call×{c:<3d}  {', '.join(cs)}\n")
        f.write("\n# JT 档（跳表成员，真信号）\n")
        for va, size, c, j in jt_rows:
            f.write(f"0x{va:06x} {size:5d}B  (jump table)\n")
        f.write("\n# JMP 档（待分类）\n")
        for va, size, c, j in jmp_rows:
            cs = sorted(host_of.get(va, set()))[:4]
            f.write(f"0x{va:06x} {size:5d}B  jmp×{j:<3d}  {', '.join(cs)}\n")
    print(f"（完整清单 → {os.path.relpath(OUT, ROOT)}）")

    if strict and call_rows:
        print("✘ CALL 档仍非空 —— 这些是被真正调用的子程序，PRD 必须收")
        return 1
    if strict_jt and jt_rows:
        print("✘ JT 档仍非空 —— 跳表成员是状态机处理器，PRD 必须收")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
