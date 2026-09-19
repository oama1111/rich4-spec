#!/usr/bin/env python3
"""
rich4-spec · 机械层：字符串表与数据段布局

为什么字符串表重要
------------------
原版把**全部 UI 文本、台词、事件名、卡片说明**以 Big5 字符串内嵌在
**代码段与 DGROUP** 里（实测代码段 3,488 条、DGROUP 2,839 条含中文）。
它们既是最直观的语义线索（"这条字符串被谁引用"往往直接说明该函数干什么），
也是复刻时**必须逐字对齐**的资源。

本工具与 `rich4dis.py` 的分工：
  · `rich4dis.py`  —— 代码：函数边界、调用图、xref、跳表
  · 本工具        —— 数据：字符串表、数据段布局、被引用关系

用法
----
    python3 tools/rich4strings.py build              # 生成 gen/strings.json + gen/layout.json
    python3 tools/layout.py ...                      # （布局查询见下）
    python3 tools/rich4strings.py find 均富         # 按文本搜索
    python3 tools/rich4strings.py refs 0x4630f4      # 谁引用了该字符串
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rich4dis import Image, Disassembler, CODE_VA, CODE_END, is_code_ptr, EXE_DEFAULT  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "gen")

# 含 CJK 或足够长的可打印串才算"有意义的字符串"
CJK = re.compile(r"[\u3400-\u9fff\uff00-\uffef]")


def extract_strings(img: Image, min_cjk_len: int = 2, min_ascii_len: int = 4):
    """扫描代码段与 DGROUP，抽出 C 字符串。

    ⚠️ 必须逐段扫描并**保留节内偏移**，因为同一串可能跨节边界不存在，
       而字符串表里的指针是 VA，`字符串VA → 文本` 的映射是后续 xref 的基础。
    """
    out = []
    for name, va0, off0, size in (
        ("AUTO", 0x401000, 1024, 394240),
        ("DGROUP", 0x463000, 398848, 158720),
    ):
        seg = img.data[off0:off0 + size]
        i = 0
        while i < len(seg):
            b = seg[i]
            if b != 0 and (32 <= b < 127 or b >= 0x80):
                j = i
                while j < len(seg) and seg[j] != 0 and (32 <= seg[j] < 127 or seg[j] >= 0x80):
                    j += 1
                # 必须以 NUL 结尾（否则是数据中间恰好像文本的片段）
                if j < len(seg) and seg[j] == 0:
                    raw = seg[i:j]
                    text = None
                    for enc in ("big5", "cp950"):
                        try:
                            text = raw.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    if text is not None:
                        has_cjk = bool(CJK.search(text))
                        ok = (len(text) >= min_cjk_len) if has_cjk else (len(text) >= min_ascii_len)
                        # 纯 ASCII 且像代码/地址的片段排除
                        if ok and not re.fullmatch(r"[0-9a-fx\s,\.\-]+", text):
                            out.append({"va": va0 + i, "sec": name, "text": text,
                                        "bytes": len(raw),
                                        # ★ `trusted` 是**必须看**的字段，别忽略它：
                                        #   DGROUP 是**数据段**，里面的 NUL 结尾串就是游戏真字符串 ⇒ True
                                        #   AUTO 是**代码段**，那里的"串"只是「一段以 NUL 结尾、
                                        #   恰好能被 Big5 解码的字节」——**绝大多数是乱码假阳性**
                                        #   （实测 4,031 条里 3,209 条含 CJK，但全是如 `1骼︺qI` 的噪声）。
                                        #   把 AUTO 的 text 当文本真值会直接污染规格。
                                        "trusted": name == "DGROUP"})
                    i = j + 1
                    continue
                i = j if j > i else i + 1
            else:
                i += 1
    return out


def build_layout(img: Image, dis: Disassembler, strings):
    """数据段布局：把 DGROUP 切成「字符串区 / 指针表区 / 数值区 / 未初始化区」。

    判据（每一条都可复核）：
      · 落在字符串表某个串的字节范围内          → string
      · 4 字节值能被解析成**同一节内**的 VA     → pointer（跳表/名字表）
      · 其余且非零                              → data
      · `.bss` 区（文件内无字节）                → bss
    """
    str_spans = [(s["va"], s["va"] + s["bytes"] + 1) for s in strings if s["sec"] == "DGROUP"]
    str_spans.sort()

    def in_str(va):
        # 线性扫描足够快（约 2.8k 段）
        for lo, hi in str_spans:
            if lo <= va < hi:
                return True
            if lo > va:
                break
        return False

    regions = []
    for name, va0, off0, size in (
        ("DGROUP", 0x463000, 398848, 158720),
        (".bss", 0x48A000, None, 64512),
    ):
        cursor = va0
        end = va0 + size
        if off0 is None:
            regions.append({"sec": name, "va": va0, "size": size, "kind": "bss"})
            continue
        while cursor < end:
            if in_str(cursor):
                regions.append({"sec": name, "va": cursor, "size": 0, "kind": "string"})
                # 合并连续字符串字节
                k = cursor
                while k < end and in_str(k):
                    k += 1
                regions[-1]["size"] = k - cursor
                cursor = k
                continue
            v = img.u32(cursor)
            if v is not None and (0x401000 <= v < 0x4B0000):
                # 连续的指针构成表
                k = cursor
                n = 0
                while k + 4 <= end:
                    x = img.u32(k)
                    if x is None or not (0x401000 <= x < 0x4B0000):
                        break
                    n += 1
                    k += 4
                if n >= 2:
                    vals = [img.u32(cursor + i * 4) for i in range(n)]
                    code_ptrs = sum(1 for x in vals if is_code_ptr(x))
                    regions.append({
                        "sec": name, "va": cursor, "size": n * 4,
                        "kind": "table:code" if code_ptrs * 2 > n else "table:data",
                        "entries": n,
                    })
                    cursor = k
                    continue
            # 普通数据：走到下一个字符串或下一个指针表
            k = cursor + 4
            while k < end and not in_str(k):
                x = img.u32(k)
                if x is not None and 0x401000 <= x < 0x4B0000:
                    break
                k += 4
            regions.append({"sec": name, "va": cursor, "size": k - cursor, "kind": "data"})
            cursor = k
    return regions


def build_string_xrefs(dis: Disassembler, strings) -> dict:
    """字符串 → 引用它的指令（`push <str>` / `lea reg, [str]` 等）。

    这是最有语义价值的一张表：**某字符串被哪个函数引用**，
    基本就说明了那个函数的用途（例如台词表被 `player_say` 的调用者引用）。
    """
    str_by_va = {s["va"]: s for s in strings}
    # 指令里出现的立即数/绝对地址 → 是否命中字符串
    hits: dict[int, list] = {}
    for entry, fn in dis.funcs.items():
        for i in fn.insns:   # Insn 已带 mem_addr（绝对寻址的全局/字符串地址）
            for cand in (i.mem_addr, i.imm_data):
                if cand is not None and cand in str_by_va:
                    hits.setdefault(cand, []).append({"func": entry, "insn_va": i.va,
                                                      "mnemonic": i.mnemonic, "op": i.op_str})
    return hits


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "build"
    img = Image(EXE_DEFAULT)

    if cmd == "find":
        if len(argv) < 3:
            return print("用法: find <文本片段>") or 2
        pat = argv[2]
        # 复用已生成的 strings.json（若有），否则现扫
        p = os.path.join(GEN, "strings.json")
        if os.path.exists(p):
            strings = json.load(open(p))
        else:
            strings = extract_strings(img)
        n = 0
        for s in strings:
            if pat in s["text"]:
                print("0x%08x  %-6s  %s" % (s["va"], s["sec"], s["text"]))
                n += 1
                if n > 200:
                    print("…（截断）")
                    break
        print(f"\n共 {n} 条命中" + ("" if n <= 200 else "（已截断）"))
        return 0

    if cmd == "refs":
        va = int(argv[2], 16)
        p = os.path.join(GEN, "string-xrefs.json")
        if not os.path.exists(p):
            return print("先跑 build") or 2
        x = json.load(open(p))
        for r in x.get(str(va), []):
            print("  函数 0x%08x  %08x  %s %s" % (r["func"], r["insn_va"], r["mnemonic"], r["op"]))
        return 0

    # build
    print("抽取字符串 …", file=sys.stderr)
    strings = extract_strings(img)
    cjk = sum(1 for s in strings if CJK.search(s["text"]))
    print(f"  共 {len(strings)} 条（含中文 {cjk} 条）", file=sys.stderr)

    print("递归遍历建图（用于 xref）…", file=sys.stderr)
    dis = Disassembler(img)
    dis.traverse(verbose=False, include_orphans=True)

    print("计算字符串引用关系 …", file=sys.stderr)
    refs = build_string_xrefs(dis, strings)

    print("切分数据段布局 …", file=sys.stderr)
    regions = build_layout(img, dis, strings)

    os.makedirs(GEN, exist_ok=True)
    with open(os.path.join(GEN, "strings.json"), "w") as f:
        json.dump(strings, f, ensure_ascii=False, indent=1)
    with open(os.path.join(GEN, "string-xrefs.json"), "w") as f:
        json.dump(refs, f, ensure_ascii=False, indent=1)
    with open(os.path.join(GEN, "layout.json"), "w") as f:
        json.dump(regions, f, ensure_ascii=False, indent=1)

    from collections import Counter
    kinds = Counter(r["kind"] for r in regions)
    print(f"已写入 gen/strings.json（{len(strings)} 条，其中 {len(refs)} 条被引用）")
    print(f"已写入 gen/string-xrefs.json")
    print(f"已写入 gen/layout.json（{len(regions)} 个区间）")
    print("  区间类型分布:", dict(kinds.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
