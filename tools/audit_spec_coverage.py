#!/usr/bin/env python3
"""
rich4-spec · **逐函数**覆盖审计（阶段 1 的机械补充）

回答一个此前只能靠人肉判断的问题：
**exe 里到底有哪些函数，PRD 一次都没提过？**

口径（可机械复算）：
  · 函数表 = `gen/functions.json`（1560 条，全部落在 AUTO 代码段 0x401000..0x462000）
  · 「提到」= 该函数**入口 VA** 或区间 `[entry, entry+size)` 内任一地址
    出现在 `docs/**/*.md` 里（文档常引用 `loc_0043c4f5` 这类**内部**地址）
  · 只有落在 AUTO 段内的十六进制数才算 VA（过滤尺寸/常量/偏移的噪声）

为什么按**字节数**加权：一个 4270 字节的函数没人提，比 5 字节的桩严重得多。

★ 输出分桶（**只有 3/4 桶才是审计信号**）：上游是 `rich4dis.py` 的递归遍历产物，
里面混着 CRT/运行库、Windows 窗口过程（由系统回调，天然 0 调用者），
以及遍历器的投机候选。不分类的话，头几十条全是噪声。

| 桶 | 判据 | 含义 |
|---|---|---|
| 1 | `va >= 0x450000` | 运行库/CRT 区（在 .idata 之前），与玩法无关 |
| 2 | 0 调用者 **且** 0 被调用者 | 存疑：很可能是遍历器的**幻影**或纯数据 |
| 3 | 0 调用者、有被调用者 | ★ 大概率是**回调/窗口过程**（含 UI 界面）——需要人看一眼 |
| 4 | 有调用者 | ★ 真·遗漏：被游戏代码调用，而规格没提 |

用法
----
    python3 tools/audit_spec_coverage.py                # 总览 + 各桶 top
    python3 tools/audit_spec_coverage.py --bucket 4     # 只看第 4 桶
    python3 tools/audit_spec_coverage.py --min-size 64
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DOCS = os.path.join(ROOT, "docs")
FUNCS = os.path.join(ROOT, "gen", "functions.json")
# ★ remake 侧：它的**代码注释**里沉着一大批自己逆出来的 VA（PRD 里没有）。
#   把两边都扫一遍，"PRD 缺什么" 立刻分成两类：
#     · remake 已知、PRD 未收  → **直接可搬**（最有价值的一类）
#     · 两边都没有            → 真盲区，要重新逆向
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")
REMAKE_DOCS = os.path.join(REMAKE, "docs")
REMAKE_SRC = os.path.join(REMAKE, "packages")

AUTO_LO, AUTO_HI = 0x401000, 0x462000
LIB_LO = 0x450000          # 运行库/CRT 区起点（见文末「这个界怎么来的」）

# ★ 规格文档里有**四种**写法，只认 `0x` 前缀会系统性低估覆盖度
#   （实测：`0x` 口径 3982 个地址，加上裸 8 位写法后 8745 个）：
#     · `0x0040ce0e` / `0x40ce0e`  —— 散文与表格里最常用
#     · `fcn_00407a2c` / `loc_0043c4f5` / `sub_0040aa0f` —— 反汇编器风格标注
#     · `0040ce0e` —— **文档里粘贴的汇编清单**（最长的一类，4300+ 个）
#     · 裸 `4xxxxx`（6 位）—— 少见，风险大，故**不**收（可能与十进制金额混淆）
VA_PATTERNS = [
    re.compile(r"0x0*([0-9a-fA-F]{4,8})"),
    re.compile(r"(?:fcn_|loc_|sub_|jmp_)(0*[0-9a-fA-F]{5,8})"),
    re.compile(r"\b0{2}(4[0-9a-fA-F]{5})\b"),
]


def collect_vas(paths):
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


def walk_md(root):
    files = []
    for dirpath, _dirs, names in os.walk(root):
        for n in names:
            if n.endswith(".md"):
                files.append(os.path.join(dirpath, n))
    return sorted(files)


def walk_ext(root, exts):
    files = []
    if not os.path.isdir(root):
        return files
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git")]
        for n in names:
            if n.endswith(exts):
                files.append(os.path.join(dirpath, n))
    return sorted(files)


def main() -> int:
    argv = sys.argv[1:]
    min_size = 0
    if "--min-size" in argv:
        min_size = int(argv[argv.index("--min-size") + 1])
    only = None
    if "--bucket" in argv:
        only = int(argv[argv.index("--bucket") + 1])

    funcs = json.load(open(FUNCS, encoding="utf-8"))
    spec_vas = collect_vas(walk_md(SPEC_DOCS))
    rmk_docs = collect_vas(walk_md(REMAKE_DOCS))
    rmk_src = collect_vas(walk_ext(REMAKE_SRC, (".ts",)))
    remake_vas = rmk_docs | rmk_src
    print(f"PRD（rich4-spec/docs）提到的不重复地址：{len(spec_vas)} 个")
    print(f"remake 文档提到：{len(rmk_docs)} 个；remake 代码注释提到：{len(rmk_src)} 个")
    print(f"★ remake 知道、而 PRD 没收的地址：{len(remake_vas - spec_vas)} 个")

    rows = []
    for f in funcs:
        va = int(f["va"], 16)
        size = f.get("size") or 0
        hit = va in spec_vas
        if not hit:
            hit = any(v in spec_vas for v in range(va, va + max(size, 1)))
        rmk_hit = va in remake_vas
        if not rmk_hit:
            rmk_hit = any(v in remake_vas for v in range(va, va + max(size, 1)))
        callers = len(f.get("callers", []))
        callees = len(f.get("callees", []))
        if hit:
            bucket = 0
        elif va >= LIB_LO:
            bucket = 1
        elif callers == 0 and callees == 0:
            bucket = 2
        elif callers == 0:
            bucket = 3
        else:
            bucket = 4
        rows.append({"va": va, "size": size, "bucket": bucket,
                     "root": f.get("root", ""), "insn": f.get("insn_count", 0),
                     "callers": callers, "callees": callees,
                     "ends": f.get("ends", ""), "rmk": rmk_hit})

    total = sum(r["size"] for r in rows)
    covered = sum(r["size"] for r in rows if r["bucket"] == 0)
    print(f"函数 {len(rows)} 个 / {total} 字节；被规格提到 "
          f"{sum(1 for r in rows if r['bucket'] == 0)} 个"
          f"（{covered} 字节 = {covered * 100 / total:.1f}%）")
    names = {1: "运行库/CRT 区（≥0x450000）",
             2: "0 调用者 + 0 被调用者（存疑/幻影）",
             3: "0 调用者、有被调用者（★ 回调/窗口过程？）",
             4: "有调用者（★★ 真·遗漏）"}
    for b in (1, 2, 3, 4):
        n = [r for r in rows if r["bucket"] == b]
        print(f"  [{b}] {names[b]}：{len(n)} 个 / {sum(r['size'] for r in n)} 字节")

    # 表驱动的入口（卡片/新闻/命运）有没有被提到 —— 这个信号最直接
    tabs = [r for r in rows if r["root"].startswith("table:")]
    tab_miss = [r for r in tabs if r["bucket"] != 0]
    print(f"\n表驱动入口（table:*）共 {len(tabs)} 个，其中未提到 {len(tab_miss)} 个")
    if tab_miss:
        for r in sorted(tab_miss, key=lambda r: -r["size"])[:12]:
            print(f"    0x{r['va']:06x}  {r['size']:5d}B  {r['root']}")

    miss = [r for r in rows if r["bucket"] != 0]
    rmk_known = [r for r in miss if r["rmk"]]
    blind = [r for r in miss if not r["rmk"]]
    print(f"\n★ 未覆盖者里，**remake 已经知道**（PRD 可直接搬）：{len(rmk_known)} 个 / "
          f"{sum(r['size'] for r in rmk_known)} 字节")
    print(f"  两边都不知道（真盲区）：{len(blind)} 个 / {sum(r['size'] for r in blind)} 字节")

    buckets = [only] if only else [3, 4]
    for b in buckets:
        sel = [r for r in rows if r["bucket"] == b and r["size"] >= min_size]
        sel.sort(key=lambda r: -r["size"])
        print(f"\n=== 桶 [{b}] {names[b]}：{len(sel)} 条 ===")
        print(f"{'VA':>10} {'size':>6} {'insn':>5} {'callers':>7} {'callees':>7}  "
              f"{'remake已知':<10} root")
        for r in sel[:50]:
            print(f"0x{r['va']:06x} {r['size']:6d} {r['insn']:5d} {r['callers']:7d} "
                  f"{r['callees']:7d}  {'是' if r['rmk'] else '—':<10} {r['root'][:30]}")
    print("\n★ 这个界（0x450000）怎么来的：.idata 在 0x462000，"
          "而 0x450000..0x461fff 这一段里全是 C 运行库例程"
          "（浮点格式化、malloc/free 家族、字符串与文件包装，"
          "特征是多处 `push es`/段寄存器与 `_libc_*` 调用链）；"
          "玩法代码在这条界之下。它只是**分桶用的启发式**，不是硬结论。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
