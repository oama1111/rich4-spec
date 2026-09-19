#!/usr/bin/env python3
"""
rich4-spec · 规格文档质检（lint）

为什么需要
----------
本项目最大的风险**不是**漏掉某个机制，而是**文档里写下了错的结论**。
既有审计已记录 8 处实质错误，全部来自人工转录。

因此规格文档必须可机械复核。本脚本检查四件事：

  1. **引用有效性**：文中每个 `0x40xxxx` 形式的 VA 是否真的落在代码段/数据段内，
     以及（若给了函数入口）是否真的在 `gen/functions.json` 的已建图函数集中。
     —— 抓「凭记忆编造地址」。
  2. **证据密度**：每节是否有 `@source`；有没有一节完全没有任何 VA。
  3. **未决标注**：是否明确列出「未决」，而不是用推测填空。
  4. **危险模式**：文中若出现已知的错误命名（如把 `0x44ef41` 当 update_hostility），
     或出现未经考证的绝对化措辞（"必然"/"一定是"）而无 VA 支撑，予以提示。

用法
----
    python3 tools/lint_specs.py                 # 检查 docs/ 下全部 md
    python3 tools/lint_specs.py docs/systems/cards.md
    python3 tools/lint_specs.py --strict        # 有 WARN 即非零退出
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "gen")

def _load_sections():
    """段边界**从 PE 自动计算**，不硬编码。

    ⚠️ 曾经硬编码，结果 `DGROUP` 的上界写成 0x48a000（实际是 0x463000+0x26C00−1
    = 0x489bff，差 1024 字节）—— 一个用来"抓编造地址"的工具自己带着错边界。
    凡段表，一律从 PE 读，避免这类漂移。
    """
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from rich4dis import Image, EXE_DEFAULT
        img = Image(EXE_DEFAULT)
        return [(sec["name"], sec["va"], sec["raw_size"]) for sec in img.sections]
    except Exception:
        # 退化到实测值（与 PE 一致）；仅当 rich4.exe 不可读时使用
        return [
            ("AUTO",   0x401000, 394240),
            (".idata", 0x462000, 3584),
            ("DGROUP", 0x463000, 158720),
            (".bss",   0x48A000, 64512),
            (".reloc", 0x49A000, 41984),
            (".rsrc",  0x4A5000, 2560),
        ]


SECTIONS = _load_sections()

VA_RE = re.compile(r"0x0*([0-9a-fA-F]{5,8})\b")

# 这些是**元数据常量**，不是节内地址，不应报错：
#   0x400000 = ImageBase（PE 头里就有，出现是正常的）
META_CONSTS = {0x400000}
SOURCE_RE = re.compile(r"@source")
UNDECIDED_RE = re.compile(r"未决|未确认|未知|待确认|未定论")

# 已知的错误命名 / 易混对（来自既有审计），出现在文档里要提醒
KNOWN_TRAPS = [
    (r"0x0*44ef41[^\n]{0,40}update_hostility",
     "0x44ef41 是 player_say，不是 update_hostility（审计已澄清）"),
    (r"update_hostility[^\n]{0,40}0x0*44ef41",
     "0x44ef41 是 player_say，不是 update_hostility（审计已澄清）"),
    (r"hostility\[6\]",
     "hostility 实为 4 项，+0x5c/+0x60 是 monthly_paid/received（审计错误 #4）"),
    (r"mscrt\.ld[^\n]{0,30}(信任|可用|采用)",
     "mscrt.ld 把 rand 重定向到 msvcrt，随机序列与原版不同（陷阱 T-001）"),
]


def section_of(va: int):
    for name, lo, size in SECTIONS:
        if lo <= va < lo + size:
            return name
    return None


def load_functions():
    p = os.path.join(GEN, "functions.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return {int(d["va"], 16) for d in json.load(f)}


def lint_file(path: str, func_starts):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    warns, errors, infos = [], [], []

    # 1. 引用有效性
    vas = []
    for m in VA_RE.finditer(text):
        v = int(m.group(1), 16)
        if 0x400000 <= v < 0x4B0000:
            vas.append(v)
    vas = sorted(set(vas))
    # 段**边界端点**是合法记法（如 `DGROUP 0x463000..0x489fff` 的末字节），
    # 不应报错。把每个段的起止各扩一个字节纳入白名单。
    boundary = set()
    for _name, lo, size in SECTIONS:
        boundary.add(lo)
        boundary.add(lo + size - 1)
        boundary.add(lo + size)
    outside = [v for v in vas
               if section_of(v) is None and v not in META_CONSTS and v not in boundary]
    for v in outside:
        errors.append(f"地址 0x{v:08x} 不在任何已知节内 —— 疑似编造或笔误")

    # 2. 证据密度（按二级标题切节）
    #    根文档（00-methodology / 01-mechanical-layer / README / verification）
    #    是方法论与索引，不是规格条目，不强制每节带 @source。
    base = os.path.basename(path)
    is_spec_entry = base not in (
        "00-methodology.md", "01-mechanical-layer.md", "README.md",
        "verification.md", "02-strings-and-layout.md", "03-annotated-db.md",
    )
    parts = re.split(r"\n(?=##+ )", text)
    no_src, no_va = [], []
    for part in parts:
        head = part.splitlines()[0][:60] if part.strip() else "(空)"
        if not SOURCE_RE.search(part) and len(part) > 400:
            no_src.append(head)
        if len(part) > 400 and not VA_RE.search(part):
            no_va.append(head)
    for h in no_src:
        # 规格条目缺 @source 是警告；索引类文档降为提示
        (warns if is_spec_entry else infos).append(f"该节无 @source 标注：{h}")
    for h in no_va:
        if is_spec_entry:
            warns.append(f"该节完全不含 VA：{h}")

    # 3. 未决标注
    if len(text) > 1500 and not UNDECIDED_RE.search(text) and is_spec_entry:
        warns.append("全文没有「未决/未知/待确认」字样 —— 是否把推测当成了结论？")

    # 4. 已知陷阱
    for pat, msg in KNOWN_TRAPS:
        if re.search(pat, text, re.IGNORECASE):
            warns.append(f"命中已知陷阱：{msg}")

    # 5. 函数入口是否真实（仅当文档声明了「函数」且有该 VA）
    if func_starts is not None:
        claimed = re.findall(r"VA\s*`?(0x0*[0-9a-fA-F]{5,8})`?\s*[（(]?\s*函数", text)
        for c in claimed:
            v = int(c, 16)
            if 0x401000 <= v < 0x463000 and v not in func_starts:
                infos.append(f"0x{v:08x} 被写作函数入口，但不在已建图函数集中（可能是分支块或误写）")

    return {"vas": len(vas), "errors": errors, "warns": warns, "infos": infos}


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    targets = args or [os.path.join(ROOT, "docs")]
    func_starts = load_functions()
    if func_starts is None:
        print("⚠️ 未找到 gen/functions.json，跳过函数入口校验（先跑 build）", file=sys.stderr)

    files = []
    for t in targets:
        if os.path.isdir(t):
            for dirpath, _, names in os.walk(t):
                files += [os.path.join(dirpath, n) for n in names if n.endswith(".md")]
        else:
            files.append(t)

    # ★ 防线：抓「同名副本」文件（`xxx 2.md` / `xxx copy.md` 之类）。
    #   并行子代理用 write 落盘时偶发误创建（本项目已发生 2 次：
    #   `tools 2.md`、`gods 2.md`）。这类副本不会被质检覆盖，
    #   且会与正本产生内容分叉，必须在体检阶段就暴露出来。
    import re as _re
    dupe_pat = _re.compile(r"^(.*?)( \d+| copy| - Copy)(\.md)$", _re.IGNORECASE)
    dupes = [f for f in files if dupe_pat.match(os.path.basename(f))]
    if dupes:
        print("⚠️  检测到疑似重复副本文件（请人工确认并删除其中较旧者）：")
        for f in dupes:
            base = dupe_pat.match(os.path.basename(f)).group(1) + ".md"
            sibling = os.path.join(os.path.dirname(f), base)
            extra = ""
            if os.path.exists(sibling):
                extra = "  正本存在：%s（%d 行 vs %d 行）" % (
                    os.path.relpath(sibling, ROOT),
                    sum(1 for _ in open(sibling, encoding="utf-8")),
                    sum(1 for _ in open(f, encoding="utf-8")))
            print("   %s%s" % (os.path.relpath(f, ROOT), extra))
        print("   （这些文件已被排除在质检之外）\n")
        files = [f for f in files if f not in dupes]

    total_e = total_w = 0
    for path in sorted(files):
        r = lint_file(path, func_starts)
        rel = os.path.relpath(path, ROOT)
        status = "ERR" if r["errors"] else ("WARN" if r["warns"] else "ok")
        print(f"[{status:4}] {rel}  （VA 引用 {r['vas']} 个）")
        for e in r["errors"]:
            print(f"         ❌ {e}")
        for w in r["warns"]:
            print(f"         ⚠️  {w}")
        for i in r["infos"]:
            print(f"         ℹ️  {i}")
        total_e += len(r["errors"])
        total_w += len(r["warns"])

    print(f"\n合计：{len(files)} 个文件，{total_e} 个错误，{total_w} 个警告")
    if total_e:
        return 1
    if strict and total_w:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
