#!/usr/bin/env python3
"""
rich4-spec · **「PRD 写了、remake 没提」审计**（`audit_spec_coverage.py` 的镜像）

`audit_spec_coverage.py` 问的是「exe 里哪些函数 PRD 没提」；
本脚本问的是**反方向**：**PRD 郑重写过的函数，remake 一次都没提到** ——
那正是「规格有了、实现没跟上」的嫌疑，也就是目标里「据 PRD 逐个补全」那半边。

口径：
  · 函数表 = `gen/functions.json`（1560 条）
  · 「PRD 提到」= 该函数**入口**出现在 `rich4-spec/docs/**/*.md`
  · 「remake 提到」= 同一地址出现在 `rich4-remake/packages/**/*.ts`
    或 `rich4-remake/docs/**/*.md`
  · 输出按**提到它的规格文件**分组 —— 那份文件就是「哪个系统声称实现了它」

⚠️ 命中**不等于缺陷**：大量命中是
   · 表现层（PRD 记录渲染链路，remake 用别的画法，根本没引用那个 VA）；
   · 数据/CRT；
   · 「复刻按等价方式实现、只是没引用那个地址」。
  故本表只用来**排优先级**；每条都要人看一眼再判。

用法
----
    python3 tools/audit_unimplemented.py               # 按规格文件分组的总览
    python3 tools/audit_unimplemented.py --group cards # 看某一组
    python3 tools/audit_unimplemented.py --min-size 200
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")
AUTO_LO, AUTO_HI = 0x401000, 0x462000
LIB_LO = 0x450000

VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b"),
]


def vas_with_files(paths):
    """返回 {va: {文件 basename}}"""
    out: dict[int, set[str]] = {}
    for p in paths:
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        name = os.path.basename(p)
        for pat in VA_PATTERNS:
            for m in pat.finditer(text):
                v = int(m.group(1), 16)
                if AUTO_LO <= v < AUTO_HI:
                    out.setdefault(v, set()).add(name)
    return out


def walk(root, exts):
    files = []
    for dp, dirs, ns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git")]
        for n in ns:
            if n.endswith(exts):
                files.append(os.path.join(dp, n))
    return sorted(files)


def main() -> int:
    argv = sys.argv[1:]
    group = argv[argv.index("--group") + 1] if "--group" in argv else None
    min_size = int(argv[argv.index("--min-size") + 1]) if "--min-size" in argv else 0

    spec = vas_with_files(walk(os.path.join(ROOT, "docs"), (".md",)))
    remake: set[int] = set()
    for p in walk(os.path.join(REMAKE, "packages"), (".ts",)):
        remake |= set(vas_with_files([p]))
    for p in walk(os.path.join(REMAKE, "docs"), (".md",)):
        remake |= set(vas_with_files([p]))

    funcs = json.load(open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8"))
    rows = []
    for f in funcs:
        va = int(f["va"], 16)
        if va >= LIB_LO:
            continue                      # 运行库区：PRD 记它也没意义
        if va not in spec:
            continue                      # PRD 没提 → 归 audit_spec_coverage 管
        if va in remake:
            continue                      # remake 提过 → 不是本表的事
        rows.append({
            "va": va, "size": f.get("size") or 0, "insn": f.get("insn_count", 0),
            "callers": len(f.get("callers", [])), "callees": len(f.get("callees", [])),
            "root": f.get("root", ""), "files": sorted(spec[va]),
        })
    rows = [r for r in rows if r["size"] >= min_size]
    rows.sort(key=lambda r: -r["size"])

    # ★ 分桶 —— 与 `audit_spec_coverage.py` 同一个教训：函数表里混着
    #   遍历器的投机候选（0 调用者），不分桶的话命中全是噪声。
    #   只有 A 桶（**有调用者**）是真信号。
    def bucket(r):
        if r["callers"] > 0:
            return "A"
        if r["callees"] > 0:
            return "B"
        return "C"

    for r in rows:
        r["bucket"] = bucket(r)
    total = sum(r["size"] for r in rows)
    print(f"★ PRD 提到、remake 一次未提的函数：{len(rows)} 个 / {total} 字节")
    for b, name in (("A", "有调用者 —— ★★ 真信号"), ("B", "0 调用者、有被调用者 —— 回调/分支块"),
                    ("C", "0/0 —— 存疑/数据区")):
        sel = [r for r in rows if r["bucket"] == b]
        print(f"   [{b}] {name}：{len(sel)} 个 / {sum(r['size'] for r in sel)} 字节")
    rows = [r for r in rows if r["bucket"] == "A"]
    print()

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["files"][0], []).append(r)
    print(f"{'规格文件':<24} {'函数':>5} {'字节':>7}  最大的几个")
    for doc, items in sorted(groups.items(), key=lambda kv: -sum(x["size"] for x in kv[1])):
        if group and group not in doc:
            continue
        big = ", ".join(f"0x{x['va']:06x}({x['size']}B)" for x in items[:3])
        print(f"{doc:<24} {len(items):5d} {sum(x['size'] for x in items):7d}  {big}")

    if group:
        print(f"\n=== 组「{group}」明细 ===")
        for doc, items in groups.items():
            if group not in doc:
                continue
            for r in sorted(items, key=lambda r: -r["size"]):
                print(f"0x{r['va']:06x} {r['size']:6d}B  {r['insn']:4d}条  "
                      f"callers={r['callers']:2d} callees={r['callees']:2d}  {r['root'][:26]}")
    print("\n（分组总览已按 A 桶过滤；要看全部桶用 --min-size 0 --group <名> 并读上面的分桶计数）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
