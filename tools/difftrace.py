#!/usr/bin/env python3
"""
rich4-spec · 验收层：状态轨迹比对（通道 3 的可运行部分）

背景与诚实边界
--------------
通道 3 的目标是「原版与重制版跑同一局，逐回合比对状态指纹」。它需要两侧产物：

  · **重制版侧**：已有现成基建（`rich4-remake` 的 `stateFingerprint`
    与 `packages/core/src/state/replay.test.ts`），可导出逐回合指纹。
  · **原版侧**：需要一个**预言机（oracle）**——在 Wine 下用调试器/Frida
    读原版内存并逐回合算出同口径的指纹。这是**一次性工程，本工具不代劳**。

所以本工具做的是**可运行的那一半**：定义 trace 格式、读入两侧 trace、
逐回合比对并给出精确差异定位。原版侧 trace 一旦产出，本工具立即可用。

**它现在能验证什么**：用 `selftest` 自检（造两份 trace 验证比对逻辑本身正确）。
**它现在不能验证什么**：原版的实际状态（那需要上面的预言机）。

trace 格式（JSON Lines，每行一个回合快照）
-----------------------------------------
    {"turn": 12, "fingerprint": "a1b2c3d4", "cash": [150000, 150000, 0, 0]}
    {"turn": 13, "fingerprint": "9f8e7d6c", ...}

只有 `turn` 与 `fingerprint` 是必需字段；其余字段（`cash` 等）可选，
用于在指纹不符时**定位到具体字段**。

用法
----
    python3 tools/difftrace.py selftest                    # 自检比对逻辑
    python3 tools/difftrace.py diff orig.jsonl remake.jsonl
    python3 tools/difftrace.py diff a.jsonl b.jsonl --fields cash,cash2
"""
from __future__ import annotations

import json
import sys


def load_trace(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{lineno} 不是合法 JSON：{e}")
            if "turn" not in rec:
                raise SystemExit(f"{path}:{lineno} 缺少必需字段 turn")
            out.append(rec)
    return out


def diff(a: list[dict], b: list[dict], fields: list[str], max_report: int = 20) -> int:
    """逐回合比对。返回 0 表示完全一致。"""
    if len(a) != len(b):
        print(f"⚠️  长度不同：{len(a)} vs {len(b)} 回合（将比对较短的一侧，"
              f"但这本身已是不一致）")

    n = min(len(a), len(b))
    mismatches = []
    for i in range(n):
        ra, rb = a[i], b[i]
        # 回合号必须对齐
        if ra.get("turn") != rb.get("turn"):
            mismatches.append((i, "turn", ra.get("turn"), rb.get("turn")))
            continue
        fa, fb = ra.get("fingerprint"), rb.get("fingerprint")
        if fa != fb:
            # 指纹不符：尝试用可选字段定位
            detail = []
            for k in fields:
                if k in ra or k in rb:
                    if ra.get(k) != rb.get(k):
                        detail.append(f"{k}: {ra.get(k)!r} ≠ {rb.get(k)!r}")
            mismatches.append((i, f"turn {ra.get('turn')} 指纹 {fa} ≠ {fb}",
                               "; ".join(detail) or "（无可定位字段）", ""))

    if not mismatches:
        status = "✅ 两侧 trace 完全一致" if len(a) == len(b) else "⚠️ 前 %d 回合一致，但长度不同" % n
        print(f"{status}（{n} 个回合）")
        return 0 if len(a) == len(b) else 1

    print(f"❌ 发现 {len(mismatches)} 处不一致（共比对 {n} 个回合）\n")
    print("第一个分歧点最关键 —— 其后所有差异多半是它的连锁结果：\n")
    for i, what, extra, _ in mismatches[:max_report]:
        print(f"  [回合序号 {i}] {what}")
        if extra:
            print(f"              {extra}")
    if len(mismatches) > max_report:
        print(f"  …（其余 {len(mismatches) - max_report} 处省略）")
    return 1


def selftest() -> int:
    """用合成数据验证比对逻辑本身正确（不含原版）。"""
    print("自检：状态轨迹比对逻辑\n")
    base = [{"turn": t, "fingerprint": f"fp{t}", "cash": [100 + t, 200, 0, 0]}
            for t in range(5)]
    fails = 0

    # 1. 完全一致
    import copy
    ok = diff(base, copy.deepcopy(base), ["cash"]) == 0
    print(f"  {'✅' if ok else '❌'} 相同 trace 判定为一致")
    fails += 0 if ok else 1

    # 2. 第 3 回合指纹不同 —— 应报出且能定位到 cash
    mod = copy.deepcopy(base)
    mod[3]["fingerprint"] = "DIFFERENT"
    mod[3]["cash"] = [999, 200, 0, 0]
    rc = diff(mod, base, ["cash"])
    ok = rc == 1
    print(f"  {'✅' if ok else '❌'} 单点指纹差异被检出")
    fails += 0 if ok else 1
    print("     （上面应显示 [回合序号 3] 且给出 cash 的差异值）\n")

    # 3. 长度不同 —— 应提示
    rc = diff(base[:3], base, ["cash"])
    ok = rc == 1
    print(f"  {'✅' if ok else '❌'} 长度不同被检出")
    fails += 0 if ok else 1

    # 4. 回合号错位 —— 应检出
    shifted = copy.deepcopy(base)
    shifted[0]["turn"] = 99
    rc = diff(shifted, base, [])
    ok = rc == 1
    print(f"  {'✅' if ok else '❌'} 回合号错位被检出")
    fails += 0 if ok else 1

    print(f"\n{'=' * 60}")
    if fails == 0:
        print("✅ 自检通过：比对逻辑正确（原版预言机仍需另建，见文件头说明）")
        return 0
    print(f"❌ 自检失败 {fails} 项")
    return 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "selftest"
    if cmd == "selftest":
        return selftest()
    if cmd == "diff":
        if len(argv) < 4:
            return print("用法: diff <原版.jsonl> <重制版.jsonl> [--fields a,b]") or 2
        fields = []
        for a in argv:
            if a.startswith("--fields="):
                fields = a.split("=", 1)[1].split(",")
        return diff(load_trace(argv[2]), load_trace(argv[3]), fields)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
