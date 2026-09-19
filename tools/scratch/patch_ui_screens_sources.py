#!/usr/bin/env python3
"""
给 ui-screens.md 的若干小节补 `@source` 行（质检要求：>400 字的二级/三级节必须有 @source）。

只做字符串插入，不重写内容；幂等（已含 @source 的节跳过）。
用法：python3 tools/scratch/patch_ui_screens_sources.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "docs", "systems", "ui-screens.md")

# 标题前缀 → 该节要额外带的 @source 行
INSERTS = [
    ("# 各屏内部绘制函数",
     "\n`@source` 本文件全部结论以 `Rich4/rich4.exe` 反汇编（`gen/db.txt`）为准；"
     "每条结论的地址都可用 `grep -n '<VA>' gen/db.txt` 复核。\n"),
    ("## 三、樂透",
     "\n`@source` 本节的 VA：`0x42f32c`、`0x42faf8`、`0x4306ff`、`0x431117`、`0x431157`、"
     "`0x431222`、`0x41ac3c`、`0x43f883`、`0x43fa19`、`0x412287`、`0x412651`、`0x412851`、"
     "`0x432511`、`0x432951`、`0x4329ef`。\n"),
    ("## 四、棋盤屏",
     "\n`@source` 本节的 VA：`0x42728e`、`0x427469`、`0x42771a`、`0x427816`、`0x4249c2`、"
     "`0x423bd1`、`0x423c0a`、`0x423c48`、`0x423c90`、`0x424049`、`0x4241f2`、`0x42424e`、"
     "`0x4242cd`、`0x40a9a4`、`0x416355`、`0x44ff21`、`0x44ff2a`、`0x44ff42`、`0x44ff4b`、"
     "`0x4020fa`、`0x4079f9`。\n"),
    ("### 保釋屏（`bail-screen.ts`）",
     "\n`@source` `VA 0x43c8fb`、`VA 0x43d88f`、`VA 0x43d304`、`VA 0x43e9a4`。\n"),
    ("### 月結／頒獎屏（`monthly-screen.ts`）",
     "\n`@source` `VA 0x437c25`、`VA 0x4387f9`、`VA 0x4391ee`、`VA 0x437d1a`、`VA 0x439bfa`。\n"),
    ("### 股份屏（`shares-screen.ts`）",
     "\n`@source` `VA 0x42b3ca`、`VA 0x42b3e1`。\n"),
    ("### 7.1 拍賣結算演出的刷新 / 收攤",
     "\n`@source` `VA 0x44ee18`、`VA 0x4762c4`、`VA 0x4762c0`、`VA 0x49715b`、"
     "`VA 0x46246c`、`VA 0x4563f5`、`VA 0x456e11`、`VA 0x454493`、`VA 0x4544b9`、"
     "`VA 0x40235d`、`VA 0x402250`。\n"),
    ("### 8.2 ",
     "\n`@source` 冲突双方：remake 侧见上表「位置」列的文件:行；exe 侧见"
     " `gen/db.txt` 里对应 VA 的指令（本节不含新地址）。\n"),
    ("#### `0x44dd9f` 版面",
     "\n`@source` `VA 0x44dd9f`、`VA 0x44dfb4`、`VA 0x4761b4`、`VA 0x476028`。\n"),
    ("#### 小区块（日期頁四颗微调",
     "\n`@source` `VA 0x410f85`、`VA 0x410fb3`、`VA 0x410fff`、`VA 0x41101a`、`VA 0x411036`、"
     "`VA 0x41076e`、`VA 0x41079c`、`VA 0x4107f3`、`VA 0x410572`、`VA 0x4105b9`、`VA 0x40fc57`。\n"),
]

# 「### 未决」可能出现多次：每处都补一句通用 @source
UNDECIDED = "\n`@source` 本节各条未决所列的 VA 均见同段正文（未决条目本身不引新地址）。\n"


def main() -> int:
    text = open(PATH, encoding="utf-8").read()
    lines = text.split("\n")
    out: list[str] = []
    applied = 0
    for i, line in enumerate(lines):
        out.append(line)
        if not line.startswith("#"):
            continue
        hit = None
        for prefix, block in INSERTS:
            if line.startswith(prefix):
                hit = block
                break
        if hit is None and line.strip() == "### 未决":
            hit = UNDECIDED
        if hit is None:
            continue
        # 幂等：看本节后续 6 行里有没有 @source
        window = "\n".join(lines[i + 1 : i + 7])
        if "@source" in window:
            continue
        out.append(hit.rstrip("\n"))
        applied += 1
    open(PATH, "w", encoding="utf-8").write("\n".join(out))
    print(f"已插入 {applied} 处 @source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
