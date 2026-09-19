#!/usr/bin/env python3
"""随机数调用点普查 —— 哪些 `rand()` 是**规则**、哪些只是**表现**。

为什么要这个：`docs/gaps/README.md` §7.3 的 1.6 / 4 两条（"走位前瞻的 rand 没进全局流"、
"AI 的 6 类 aiRoll 替身"）一直是**印象式**的待办 —— 因为没有一份
「原版到底在哪些地方掷了骰子」的清单。本工具把它机械列出来，并用既有的
`audit_channel2_targets.py` 的分类器（callee 闭包 + writes 影响面）判每条属于哪一类。

★ **这是粗筛，不是判决**。掷出来的值到底喂给规则还是喂给台词/动画，
  要看**这条指令后面怎么用**（数据流），本工具不做数据流分析。所以分成三桶：

  · **纯绘制**：所属函数是表现层（追 2 层 callee 到 blit/drawText）**且**不写规则状态
    ⇒ 与规则确定性无关
  · **碰台词**：所属函数（自己或 2 层之内）调了台词函数
    （`player_say 0x44ef41` / `0x44f230` / `0x44f2c2`）⇒ **很可能**是"选说哪句"的随机，
    但也可能同一函数里还有规则随机 —— 需要人读
  · **待读**：其余 ⇒ 这是**阅读队列**，不是"全都是规则随机"

判据（机械部分）：
  · `call 0x456f2d`（唯一 PRNG 入口，175 处）
  · 按**所属函数**归组

用法：
    python3 tools/audit_rng_sites.py            # 汇总
    python3 tools/audit_rng_sites.py --list     # 连每条一起列
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit_channel2_targets as A  # noqa: E402

PRNG_VA = "0x456f2d"

# 台词/播报类函数：出现在 callee 闭包里 ⇒ 该函数的随机很可能是"选说哪句"
SPEECH_VAS = {0x44EF41, 0x44F230, 0x44F2C2, 0x44F354, 0x44F42D, 0x44F567,
              0x44F4ED, 0x44F627}
LINE_RE = re.compile(r"^  ([0-9a-f]{8})  .*call\s+0x456f2d")


def call_sites():
    """[(site_va, func_va, func_name)]"""
    out = []
    cur = None
    with open(os.path.join(A.ROOT, "gen", "db.txt"), encoding="utf-8") as fh:
        for line in fh:
            m = A.NAME_RE.match(line)
            if m:
                cur = (int(m.group(1), 16), m.group(2))
                continue
            m2 = LINE_RE.match(line)
            if m2 and cur:
                out.append((int(m2.group(1), 16), cur[0], cur[1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="逐条列出")
    args = ap.parse_args()

    entries = A.load_entries()
    names = A.load_names()
    by_va = {e["va"]: e for e in entries}
    wndprocs = A.load_wndproc_flags()
    sites = call_sites()

    def closure_vas(entry, depth=2):
        """自己 + 往下 2 层的所有函数 VA。"""
        seen, frontier = set(), [entry]
        for _ in range(max(1, depth)):
            nxt = []
            for e in frontier:
                for c in (e.get("callees") or []):
                    cva = int(c, 16)
                    if cva in seen:
                        continue
                    seen.add(cva)
                    ce = by_va.get(f"0x{cva:08x}")
                    if ce is not None:
                        nxt.append(ce)
            frontier = nxt
        return seen

    ui_b, speech_b, todo_b = {}, {}, {}
    for site, fva, fname in sites:
        e = by_va.get(f"0x{fva:08x}")
        score = A.impact(e)[0] if e is not None else 0
        is_ui = e is not None and (A.is_presentation(e, names, by_va)
                                   or fva in wndprocs) and score == 0
        speaks = e is not None and bool(closure_vas(e) & SPEECH_VAS)
        bucket = ui_b if is_ui else (speech_b if speaks else todo_b)
        bucket.setdefault((fva, fname), []).append(site)
    rule, present = todo_b, ui_b

    print(f"`rand()` 调用点共 **{len(sites)}** 处，分布在 "
          f"**{len(rule) + len(present)}** 个函数里：\n")
    print(f"【待读（其余）】**{sum(len(v) for v in rule.values())}** 处 / "
          f"{len(rule)} 个函数 —— 这是**阅读队列**，不能当成「全是规则随机」")
    for (fva, fname), vas in sorted(rule.items(), key=lambda kv: -len(kv[1])):
        print(f"  0x{fva:08x} {fname:<24} {len(vas):>3} 处")
        if args.list:
            print("        " + ", ".join(f"0x{v:x}" for v in vas))

    print(f"\n【纯绘制】**{sum(len(v) for v in present.values())}** 处 / "
          f"{len(present)} 个函数 —— 与规则确定性无关（不必对齐）")
    for (fva, fname), vas in sorted(present.items(), key=lambda kv: -len(kv[1])):
        print(f"  0x{fva:08x} {fname:<24} {len(vas):>3} 处")

    print(f"\n【碰台词】**{sum(len(v) for v in speech_b.values())}** 处 / "
          f"{len(speech_b)} 个函数 —— 很可能是「选说哪句」，但要人确认")
    for (fva, fname), vas in sorted(speech_b.items(), key=lambda kv: -len(kv[1])):
        print(f"  0x{fva:08x} {fname:<24} {len(vas):>3} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
