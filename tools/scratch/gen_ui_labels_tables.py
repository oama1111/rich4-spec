#!/usr/bin/env python3
"""ui-labels.md 的条目表生成器（子代理临时脚本，非主线）。

用法：
    python3 tools/scratch/gen_ui_labels_tables.py

把 docs/systems/ui-labels.md 里的 {{TABLE:0xVA:N}} 占位符替换成
「序号 | 字符串 | 字符串 VA」表格，条目直接从 rich4.exe 的 DGROUP 读出。

⚠️ 铁律：每个条目必须落在 DGROUP 且 strings.json 标 trusted==true；
   任何一条不满足就断言失败并中止（说明指针算错了，不是「文本奇怪」）。
   指向「较长串中段」的指针（如 0x475988[0] -> 0x464c30）不在 strings.json 里，
   此时退回直接按 NUL 结尾解码，并同样断言落段为 DGROUP。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rich4dis as R  # noqa: E402

DOC = os.path.join(ROOT, "docs", "systems", "ui-labels.md")
MARK = re.compile(r"\{\{TABLE:(0x[0-9a-fA-F]+):(\d+)\}\}")


def cstr(img: R.Image, va: int) -> str:
    out = b""
    while True:
        b = img.read(va + len(out), 1)
        if not b or b == b"\0":
            break
        out += b
    return out.decode("big5", errors="replace")


def main() -> int:
    img = R.Image(R.EXE_DEFAULT)
    S = {int(x["va"]): x for x in json.load(open(os.path.join(ROOT, "gen", "strings.json")))}
    dgroup_lo, dgroup_hi = 0x463000, 0x48A000

    def render(va: int, n: int) -> str:
        rows = ["| # | 字符串 | 字符串 VA |", "|---|---|---|"]
        for i in range(n):
            slot = va + i * 4
            p = img.u32(slot)
            assert dgroup_lo <= p < dgroup_hi, (
                f"0x{slot:08x}[{i}] -> 0x{p:08x} 不在 DGROUP，指针算错了")
            e = S.get(p)
            if e is not None:
                assert e.get("trusted") is True, (
                    f"0x{slot:08x}[{i}] -> 0x{p:08x} 非 DGROUP 真串，指针算错了")
                text = e["text"]
            else:
                text = cstr(img, p)   # 指向较长串中段，strings.json 未收录
                assert text, f"0x{slot:08x}[{i}] -> 0x{p:08x} 解出空串"
            text = text.replace("\n", "\\n").replace("|", "\\|")
            rows.append(f"| {i} | `{text}` | `0x{p:06x}` |")
        return "\n".join(rows)

    src = open(DOC, encoding="utf-8").read()
    hits = MARK.findall(src)
    if not hits:
        print("docs/systems/ui-labels.md 里已没有 {{TABLE:...}} 占位符"
              "（本脚本是一次性生成器，文档已含生成结果）。")
        return 0
    for m in MARK.finditer(src):
        va, n = int(m.group(1), 16), int(m.group(2))
        print(f"  生成 0x{va:06x} × {n} 项")
    out = MARK.sub(lambda m: render(int(m.group(1), 16), int(m.group(2))), src)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"已写入 {os.path.relpath(DOC, ROOT)}（{out.count(chr(10))} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
