#!/usr/bin/env python3
"""
rich4-spec · 覆盖度追踪

回答一个问题：**目标里的每个玩法系统，现在覆盖到什么程度？**

度量口径（全部可机械复算，不靠主观判断）：
  · 文档行数 / 唯一 VA 引用数 / @source 标注数
  · 未决条目数（未决**不是缺点**，是把不确定性显式化）
  · 是否被差分测试覆盖（扫描 tests/ 里出现的 VA）

用法
----
    python3 tools/coverage.py            # 打印表格
    python3 tools/coverage.py --write    # 同时刷新 docs/coverage.md
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYS = os.path.join(ROOT, "docs", "systems")
TESTS = os.path.join(ROOT, "tests")

VA_RE = re.compile(r"0x0*([0-9a-fA-F]{5,8})")
UNDECIDED = re.compile(r"未决|未确认|未知|待确认|待定")

# 目标里点名的全部玩法系统 → 承载它的规格文件（None 表示尚无）
SYSTEMS: list[tuple[str, str | None, str]] = [
    ("地图格式",    "map-format.md",  "地图资源定位、40 字节头与五张表（node/land/facility/commercial/landscape）"),
    ("地产/过路费", "land-rent.md",   "住宅与商業用地的结构与过路费公式"),
    ("金钱/资产",   "economy.md",     "总资产核算与全部数组基准"),
    ("卡片",        "cards.md",       "30 张卡片效果函数"),
    ("道具",        "tools.md",       "13 个道具"),
    ("新闻",        "news.md",        "36 项新闻事件"),
    ("命运",        "fortune.md",     "37 项命运事件"),
    ("股市/企业",   "stocks.md",      "股价公式、买卖、企业归属与分红"),
    ("银行",        "bank.md",        "存款/贷款/利息/ATM 与 cashRatio"),
    ("银行/监狱/医院/乐透", "places.md", "四地点系统（与 bank.md 在银行节有重叠）"),
    ("监狱",        "places.md",      "服刑天数与出狱"),
    ("医院",        "places.md",      "住院天数与出狱"),
    ("乐透",        "places.md",      "投注、开奖、赔率"),
    ("神明",        "gods.md",        "附身流程与 15 项發威效果"),
    ("魔法屋",      "magic-house.md", "12 项效果与转盘"),
    ("小游戏",      "small-games.md", "三个小游戏的玩法与奖罚"),
    ("AI",          "ai.md",          "决策结构与阈值"),
    ("回合流程",    "game-loop.md",   "消息循环/定时器/主循环骨架"),
    ("渲染/API",    "render-api.md",  "对外 API 全图与三条渲染链路"),
    ("动效",        "animation.md",   "全局动画相位、物件帧公式、定时器节拍"),
    ("台词与语音",  "dialogue-voice.md", "台词表 324 条、#NNNN 语音控制码、Speaking.mkf 1375 WAV"),
    ("效果音",      "sound-effects.md", "19 张音效集表、64 项编号、151 处播放点"),
    ("UI 界面",     "ui.md",          "界面清单（37 个界面/面板函数）+ 刷新模型"),
    ("UI 标签表",   "ui-labels.md",   "12 张字符串指针表的用途/顺序/索引语义（表→界面元素映射）"),
    ("存档",        "save-format.md", "文件构成、权威块序、加载/保存对称性"),
    ("存档标量",    "save-scalars.md", "状态块全局标量的逐个定名（§二 块序表的 30 个地址）"),
    ("数据表",      "data-tables.md", "layout.json 的 104 张 table:data：三张大表（0x48084a 步长108 / 0x480d5a 步长104×16槽 / 0x48123a 步长360×90槽）的步长与槽位、21 张独立串表、7 条既有文档勘误"),
]


def scan(path: str):
    t = open(path, encoding="utf-8").read()
    vas = {int(m, 16) for m in VA_RE.findall(t)}
    vas = {v for v in vas if 0x400000 <= v < 0x4B0000}
    return {
        "lines": t.count("\n"),
        "vas": len(vas),
        "sources": len(re.findall(r"@source", t)),
        "undecided": len(UNDECIDED.findall(t)),
    }


def test_links():
    """测试文件 → 它**显式指向的规格文件**。

    ⚠️ 初版用"文档里出现的 VA 是否等于被测函数地址"来判定，结果
    `test_prng.py` 的 PRNG 地址（`0x456f2d`）被新闻/股市/道具等**每一个**
    文档引用过，于是全部被误判成"已差分测试"。正确的判据是
    **测试文件自己声明它验证哪份规格**，而不是靠地址巧合。
    """
    links: dict[str, list[str]] = {}
    if not os.path.isdir(TESTS):
        return links
    for f in sorted(os.listdir(TESTS)):
        if not f.endswith(".py"):
            continue
        t = open(os.path.join(TESTS, f), encoding="utf-8").read()
        seen = set()
        for m in re.finditer(r"docs/systems/([A-Za-z0-9_\-]+\.md)", t):
            key = (m.group(1), f)
            if key in seen:
                continue          # 同一文件里多次提到同一规格只记一次
            seen.add(key)
            links.setdefault(m.group(1), []).append(f)
    return links


def main(argv):
    write = "--write" in argv
    tvas = test_links()
    rows = []
    total_vas = 0
    for name, fname, note in SYSTEMS:
        if fname is None:
            rows.append((name, "—", 0, 0, 0, "—", note, False))
            continue
        p = os.path.join(SYS, fname)
        if not os.path.exists(p):
            rows.append((name, fname, 0, 0, 0, "—", note, False))
            continue
        st = scan(p)
        total_vas += st["vas"]
        tested = sorted(tvas.get(fname, []))
        rows.append((name, fname, st["lines"], st["vas"], st["undecided"],
                     ",".join(tested) if tested else "—", note, True))

    # 打印
    print("%-12s %-16s %6s %6s %5s %s" % ("系统", "规格文件", "行数", "VA", "未决", "差分测试"))
    print("-" * 96)
    n_done = 0
    for name, fname, lines, vas, und, tested, note, ok in rows:
        print("%-12s %-16s %6s %6s %5s %s" % (
            name, fname, lines or "—", vas or "—", und or "—", tested))
        if ok:
            n_done += 1
    print("-" * 96)
    print("有规格文件的系统：%d / %d ；规格合计 %d 行、%d 个唯一 VA 引用"
          % (n_done, len(rows), sum(r[2] for r in rows), total_vas))
    missing = [r[0] for r in rows if not r[7]]
    if missing:
        print("尚无规格文件：", "、".join(missing))

    if write:
        out = os.path.join(ROOT, "docs", "coverage.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write("# 系统覆盖度追踪\n\n")
            f.write("> 由 `tools/coverage.py --write` 生成，**不要手工编辑**。\n\n")
            f.write("本表回答一个问题：目标里点名的每个玩法系统，现在覆盖到什么程度。\n\n")
            f.write("| 系统 | 规格文件 | 行数 | 唯一 VA 引用 | 未决条目 | 差分测试 | 说明 |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for name, fname, lines, vas, und, tested, note, ok in rows:
                f.write("| %s | %s | %s | %s | %s | %s | %s |\n" % (
                    name, f"`{fname}`" if fname else "—", lines or "—", vas or "—",
                    und or "—", f"`{tested}`" if tested != "—" else "—", note))
            f.write("\n## 怎么读这张表\n\n")
            f.write("· **VA 引用**是证据密度的下限；空表或低值的系统说明覆盖还浅。\n")
            f.write("· **未决条目**不是缺点 —— 它把不确定性**显式化**了。未决为 0\n")
            f.write("  的系统反而值得怀疑：是否把推测写成了结论？\n")
            f.write("· **差分测试**列表示该系统有函数被原版机器码验证过（通道 2），\n")
            f.write("  这是最强的证据形式。见 `verification.md`。\n\n")
            f.write("## 缺口\n\n")
            if missing:
                f.write("尚无规格文件的系统：**%s**。\n" % "、".join(missing))
            else:
                f.write("全部系统都已有规格文件。\n")
        print(f"\n已刷新 {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
