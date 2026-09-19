#!/usr/bin/env python3
"""通道 2 **待测工作单**：哪些「规则函数」已实现/已命名，却从未被差分测试驱动过。

为什么要这个工具：第 55~59 条连续四轮都是"手挑一个函数去差分"，效率低且容易漏。
这里把挑选过程机械化：

  候选 = ①复刻代码里引用过的函数入口（`@source`/字面 VA）
         − ②通道 2 测试已经驱动过的（**含区块内地址**：测试引用了入口内部
           任意地址，就算这个入口已被覆盖）
         − ③CRT/表现层（VA ≥ 0x450000，或只调 drawText/blitRect 之类）

★ 关于 **WndProc**：它们**不是**天生不可测 —— WndProc 靠消息号分发，
  用 `call(va, [hwnd, msg, wparam, lparam])` 就能驱动**某一条消息分支**
  （例如 `0x42f7fc` 投注屏的 `0x113`/`WM_TIMER`、`0x401` 等）。
  所以本工具只在「它**不写规则状态**」时才把 WndProc 排除（见 `impact()` 那道闸）。

输出按「字节数升序」——**小的通常好驱动**（少全局依赖），适合先做。
同时打印 `reads/writes` 计数作为"要铺多少全局量"的粗略指标。

用法：
    python3 tools/audit_channel2_targets.py [--all] [--limit N]
        --all    连表现层/CRT 也列出来（默认过滤）
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REMAKE = os.path.join(os.path.dirname(ROOT), "rich4-remake")

CRT_BOUNDARY = 0x450000          # ≥ 此值基本是 C 运行库（见 audit_spec_coverage 的分桶启发式）

# ★ 2026-09-19：`IMPACT_REGIONS` 的区间**收窄过一次**（原来把 `0x497158` 一族
#   RICH4.CFG 设置字节算进「全局资金/回合」）—— 那次修正把 `0x411e8f`
#   （配置读写器）从候选里剔掉了。凡再动这张表，请跑一次工作单 diff 并登记。

# ── 「玩家可观察」打分用的全局区段（半开区间） ──────────────────────────
# 依据：`functions.json` 的 reads/writes 是**全局地址**，所以可以直接看
# 「这个函数写不写玩家结构 / 钱 / 地图 / 股价」。写得越靠玩家，越值得先验。
IMPACT_REGIONS = [
    (6, "玩家结构", 0x496B68, 0x4971A8),      # 4 × 0x68（现金/存款/贷款/位置/状态/累计）
    # ★ 2026-09-19 收窄：原来写 `(0x499078, 0x499120)`，把 **RICH4.CFG 的设置字节**
    #   （`0x497158..0x497165` 那一族：game speed / 動畫過程 / 音樂音效开关）
    #   也当成「全局资金/回合」⇒ `0x411e8f`（**配置读写器**）被算成"高影响面候选"。
    #   现在只圈真正的资金/回合量：公库 0x499080、物價 0x4990e8、
    #   当前玩家 0x49910c、人数 0x499114、牌堆 0x499090、回合 0x499084/0x4990dc。
    (6, "全局资金/回合", 0x499080, 0x499120),
    (5, "地块/设施/企业", 0x48A000, 0x496000),
    (4, "股市", 0x496980, 0x497400),          # 股价表 0x496994 / 持股 0x4971a0 / AI 打分 0x497328
    (3, "公佈欄", 0x4967E0, 0x496800),
    (2, "公告板天龄/其他", 0x497180, 0x4971A0),
    # ★ 2026-09-19 补：**乐透号码相关的两张表**在 `0x4990b8/0x499120` 一带，
    #   原来没圈进来 ⇒ `0x430ab5`（開獎收尾：`give_money(公库,中奖者)` + 清号码）
    #   只显示成「全局资金/回合」1 个写点，`0x44…` 那两支显示成 1 个。
    #   注意：**`0x4990b8` 不是号码表**（号码表是 `0x4990c8`，见 `lottery.ts`）——
    #   它是逐号状态/标记表，两者都算乐透规则量。
    (5, "乐透号码表", 0x4990B8, 0x499198),
]

# ★★ 已复核为「**表现层 / 配置基建**、不需要差分驱动」的函数 —— 手工白名单，
#    每条都注明复核依据（判据：它只动绘制资源/重绘标志/设置字节，且**不写任何规则态**）。
#    加进来的函数会**直接从工作单**里去掉（与「删候选」不同：这里是真的不用测）。
VERIFIED_NOT_RULE = {
    # `0x40b8d8(n, k)`：按 (设施/格, 转向) 释放 `[0x498eb4 + n*0x34 + k*8 + j*4]` 四张
    # 图素（`my_free` + 清 0）—— 与同族 `0x40b93b` 一起由 `0x40c03b` 成对调用。
    # 判据：写点全在 `0x498eb4`（**图素指针表**，非规则字段），且只做 free/清 0。
    0x40B8D8: "图素资源释放（表现）",
    # `0x40c03b`：对槽 0..8 各调一次 `0x40b8d8(槽, 0)` 与 `(槽, 1)` ⇒ 批量清图素。
    0x40C03B: "批量清图素（表现）",
    # `0x411e8f`：**RICH4.CFG 读写器** —— `fopen("RICH4.CFG","rb")` + `fread(0x497158,0x10)`
    # + `fread(0x497168,0x38)`；文件不在时写默认值并 `memcpy(0x497168, 0x47edc2, 0x38)`。
    # ★ 判定依据：**它读/写的全是设置字节**（`0x497158` 一族），一个规则态都不碰；
    #   工作单把它当成候选是 **`IMPACT_REGIONS` 圈太宽**的假阳性（本轮已收窄区间）。
    0x411E8F: "RICH4.CFG 配置读写（非规则）",
    # ★ 2026-09-19：`0x4018e7(arg1, proc)` = **原版唯一的模态对话框消息泵**
    #   （`PeekMessageA`/`TranslateMessage`/`DispatchMessageA` 忙等循环，直到收到
    #   `0x402` 才 `dec [0x46cad8]` 退出）。它是**人类输入的来源**，不是可差分的行为：
    #   行为完全由 Windows 消息队列决定 ⇒ 无头仿真里没有确定性的"下一条消息"。
    #   复刻侧的对应物是**注入式参数**（`cards/target.ts` 的「原版是模态选单
    #   `0x004018e7`；缺省时 registry 拒收（targetRequired）」），故它不该被驱动。
    #   证据：`docs/systems/game-loop.md` §"嵌套消息泵"逐条反汇编；
    #        `docs/systems/ui.md` §"`0x48a010[深度]`"；`docs/systems/bank.md` 第 1333 条。
    0x4018E7: "模态消息泵（人类输入来源，非可差分行为）",
    # ★★ 2026-09-19 第 159 条：`0x40829d(cam_x, cam_y)` = **棋盤重畫**（5,960 B / 1,557 条）。
    #   判据（逐条列在 gaps §7.142(3)）：① 主体是绘制 —— 把相机位置写进
    #   `0x48b2ac/b0`（定点滚动坐标）→ `call 0x407a2c`（投影）→ 遍历
    #   `0x473610`（按视角相位 `0x499088` 索引的**图块表**）逐格 blit →
    #   `call [edx+0x64]`（`0x48a0e0` 的**绘制虚表**）→ 重建渲染列表
    #   `0x48a44c`/`0x48a84c`/`0x48bac8`（`animation.md` §二之二 已逐条记）；
    #   ② 唯一"像规则"的一段是**相机为 (0,0) 时的惰性初始化**（`0x4082d9`）：
    #   `rand` 抽一个空格 → 写 `player[当前].node_id` / `+0x0e` / `+0x10`。
    #   ★ 这段**已经有独立的通道 2 差分**：`tests/test_random_node.py`（38/38）驱动了
    #   它的全部规则来源 `0x40aa0f`；复刻侧建模在
    #   `packages/core/src/rules/new-game.ts` 的 `drawStartNodes`（`@source 0x004082d9`）。
    #   剩下的 `[0x475114] = 5`（`0x475110` 同族的**重画计时**）与相机回中都是表现层。
    #   ⇒ 再驱动整支 5,960 B 只能验"图块表顺序一样"，对复刻没有约束力。
    0x40829D: "棋盤重畫（规则部分已由 test_random_node.py 单独驱动）",
}
# ⚠️ 必须是 **5~8 位**十六进制：测试里普遍写 6 位（`0x428E23`），
#    早期只认 8 位（`0x00428E23`）⇒ 自己写过的测试**没被算成覆盖**，
#    候选数被系统性高估（实测修正后 174 → 见下）。
VA_RE = re.compile(r"0x([0-9a-fA-F]{5,8})")
PRESENTATION_CALLEES = (
    "drawText", "blitRect", "InvalidateRect", "BeginPaint", "EndPaint",
    "DefWindowProcA", "PostMessageA", "SetCursorPos", "create_font",
    "modal_msg_pump", "text_out", "BitBlt", "StretchBlt", "CreateWindowExA",
    "ShowWindow", "UpdateWindow", "GetDC", "ReleaseDC", "sprite",
)

# 名字判据（上面的闭包启发式）够不着、但**已被通道 2 测试实证为纯表现**的函数。
VERIFIED_PRESENTATION = {
    # 0x41d476(x, y, flag) —— 只写重绘标志（`0x475110`、`0x48be18/1c/20`）
    # @source 0x0041d476；证据 tests/test_confinement_teleport.py（48/48）
    0x41D476: "重绘标志",
    # 0x44f2c2(player, days) —— 只挑立绘/台词变体（内部 `call 0x44ef41` 换动作）。
    # ⚠️ 它在 `days ∈ (3,6]` 那一支会消耗**一个随机数**（`0x44f312 call 0x456f2d`），
    #    这是「原版 PRNG 被表现层共用」的又一例（见 gaps §7.48）
    0x44F2C2: "立绘/台词变体",
    # ★ 2026-09-19：`0x48b8c4` **可見表**（"当前屏幕上有什么"）的**三个填充器**。
    #   它们不是规则函数：填出来的表**每帧重建**，只被绘制与"AI 看哪一格"消费；
    #   复刻侧对应物是 D-005 的「以我为中心 ±220px 方形视野」，**故意换了口径**，
    #   所以差分驱动它们对复刻没有约束力（口径分歧已登记在 known-deviations）。
    #   证据：`docs/systems/map-format.md` §"`0x48b8c4` 可見表的三個填充器"
    #   （`0x409ef9` 129 条 → 畫面內節點 id；`0x40a45c` 49 条 → 畫面內實體格值；
    #    `0x40a0b1` 275 条 → 以某點為中心的實體）。
    #   ⚠️ 它们**自己只写可见表**，所以 `score0 == 0` 那道闸能生效 —— 这就是
    #   先补 `NON_RULE_GLOBALS`（把 `0x48b8c4` 剔出规则态）、再补这里的原因；
    #   顺序反了会被 `looks_ui and score0 == 0` 漏掉。
    0x409EF9: "可見表填充（畫面內節點）",
    0x40A45C: "可見表填充（畫面內實體）",
    0x40A0B1: "可見表填充（點+半徑實體）",
    # ★★ 2026-09-19 第 159 条：侧栏两个**页行值计算器** —— **零写点**。
    #   判据：`functions.json` 的 `writes` 为空，只读规则量算出一个**显示用**数字。
    #   它们的对应物是 `packages/core/src/state/panel.ts` 的两行（`@source` 已标），
    #   被读的规则量（持股 `0x4971a0`、股价 `0x496994`、地产/设施表）各自已有测试；
    #   驱动这两个函数只能证明"加法顺序一样"，对复刻没有约束力。
    #   `0x416355`：遍历 `0x498e84`（地產表，步长 0x34）与 `0x498e88`（設施表，步长 0x38），
    #     数出 `+0x19 == 玩家+1` 的项 ⇒ 侧栏「地產」行的 `[esp+0xac]`（总数）。
    #   `0x41646c`：`Σ_i holdings[i] * price[i]`（x87 `fild/fmul/fadd/fistp`）⇒ 侧栏「股票」行。
    0x416355: "侧栏地產行值计算（零写点）",
    0x41646C: "侧栏股票行值计算（零写点）",
}

# 落在 `IMPACT_REGIONS` 的地址区间里、但**不是规则状态**的全局量。
# ★ `0x48be18` 是「需要重绘地图」标志（见 `docs/systems/cards.md`），
#   `0x48be1c`/`0x48be20` 与它同族、`0x475110` 是重绘脏位；
#   它们都落在「地块/设施/企业」那一格里，会把**纯绘制**函数误判成"写规则态"
#   （`0x41d476` 就是这样混进工作单的）。
NON_RULE_GLOBALS = {0x475110, 0x48BE18, 0x48BE1C, 0x48BE20,
                    # ★ 2026-09-19：`IMPACT_REGIONS` 的「地块/设施/企业」那一格
                    #   `0x48A000..0x496000` 里**混着整片渲染缓冲**，把若干纯绘制
                    #   函数喂成了 5 分候选。逐条复核（依据全部写在 docs 里）：
                    #   `0x48b8c4` = **畫面「可見表」**（`0x0040a095` 从网格 `0x474938`
                    #     收集出的"当前屏幕上的对象/实体格值"），见
                    #     `docs/systems/map-format.md` §"`0x48b8c4` 可見表的三個填充器"。
                    #   `0x48bac8` = **渲染列表项数**（每帧清零，**不是**时间计数），
                    #     见 `docs/systems/animation.md` 的"全工程只命中 1 处"一节。
                    #   `0x48b2ac`/`0x48b2b0` = **定点滚动坐标**（5 位小数，`sar 5`
                    #     还原像素），见 `docs/systems/animation.md`「定点坐标」。
                    #   判据：四者都是**每帧重建的绘制中间量**，不参与任何跨帧规则判定。
                    0x48B8C4, 0x48BAC8, 0x48B2AC, 0x48B2B0,
                    # ★ 2026-09-19：**模态消息泵的层级状态**，同样落在这个区间里。
                    #   `0x48a010` = 「每层界面的消息处理器」数组（按 `0x46cad8` 深度索引），
                    #   `0x48a0d4` = 主窗口句柄（被当作伪父窗口用）。
                    #   证据：`docs/systems/game-loop.md` §"嵌套消息泵"（`0x4018e7` 逐条）
                    #   与 `docs/systems/ui.md` §"`0x48a010[深度]`"。
                    #   判据：它们是 **Windows 消息分发的路由表**，不参与任何游戏规则判定。
                    0x48A010, 0x48A0D4}

# ★★ 2026-09-19 第 159 条：落在 `IMPACT_REGIONS` 里、但**整块都是界面状态**的**区段**
#    （`NON_RULE_GLOBALS` 只能逐个列地址，这一块有 100+ 个写点，逐个列不可维护）。
#    判据：这一块 `0x48c400..0x48c600` 是**各屏自己的模态状态 / 布局缓存**
#    （点选目标实例对话框 `0x445e4d`、研究所面板 `0x4402d7`、拍卖屏 `0x43bde5`、
#      命运事件屏 `0x44cd99`… 各占一小段），**与规则态无关**：
#    它们不在存档里、不被任何规则函数读回、每次进屏重算。
#    证据：`packages/client/src/picking.ts` / `research-screen.ts` 的对应物都是
#    **注入式参数**（原版把"玩家点了哪一项"写进这些字节，复刻直接传参）。
#    ⚠️ 收进这里之后，写这一块的功能**只剩"是不是 WndProc/纯绘制"这一道闸**
#    —— 这正是我们要的：`0x445e4d`/`0x4402d7` 都是消息分发器。
NON_RULE_REGIONS = [
    (0x48C400, 0x48C600, "各屏模态状态/布局缓存"),
]


def in_non_rule_region(addr: int) -> bool:
    return any(lo <= addr < hi for lo, hi, _ in NON_RULE_REGIONS)

# 这些一出现就说明**纯仿真跑不了**（要么读 MKF 资源、要么直接文件 I/O）。
# 见 `rich4-remake/docs/gaps/README.md` §7.44 的「三类纯仿真限制」。
FILE_IO_CALLEES = (
    "mkf_read_resource", "ReadFile", "WriteFile", "SetFilePointer",
    "CreateFileA", "fread", "fwrite", "fopen", "load_resource",
)

NAME_RE = re.compile(r"^# 0x([0-9a-fA-F]{8})\s+(\S+)\s+\[")


def load_entries():
    with open(os.path.join(ROOT, "gen", "functions.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_names():
    """`gen/db.txt` 的 `# 0xADDR  名字  [func]` 头 → {va: 名字}。

    ⚠️ 必需：`functions.json` 的 `callees` 存的是**地址**不是名字，
    早期版本直接拿地址去和名字子串比 —— 于是「表现层」过滤**从来没生效过**
    （工作单里混着大量 `mkf_read_resource`/窗口函数就是证据）。
    """
    names = {}
    with open(os.path.join(ROOT, "gen", "db.txt"), encoding="utf-8") as fh:
        for line in fh:
            m = NAME_RE.match(line)
            if m:
                names[int(m.group(1), 16)] = m.group(2)
    return names


def vas_in_tests():
    """通道 2 测试里**真正驱动**过的 VA（含区块内地址）。

    ⚠️ 口径（两处已知的**高估**来源，宁可高估也不漏报）：
      1. 只认「`call(` / `eval_block(` / `= 0x…` 常量」这三种出现方式 ——
         纯注释里提到某个 VA **不算**驱动；
      2. 但 `patch(0x…)`（打桩）出现在同一行时**跳过** —— 被打桩的是**被替换掉**的
         表现层函数，不是被测对象（例如 `test_victory.py` 打了 `0x41906a`）。
         仍有漏网：桩地址若写在独立常量里就区分不出来。
    """
    out = set()
    tdir = os.path.join(ROOT, "tests")
    for fn in sorted(os.listdir(tdir)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        with open(os.path.join(tdir, fn), encoding="utf-8") as fh:
            for line in fh:
                if "patch(" in line:
                    continue
                if not any(k in line for k in ("call(", "eval_block(", "= 0x", "=0x")):
                    continue
                for m in VA_RE.finditer(line):
                    out.add(int(m.group(1), 16))
    return out


def vas_in_remake(subdirs=("packages/core/src",)):
    """复刻源码里引用过的 VA（@source 与普通字面量都算）。"""
    out = {}
    for sub in subdirs:
        base = os.path.join(REMAKE, sub)
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".ts") or fn.endswith(".test.ts"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                for m in VA_RE.finditer(text):
                    out.setdefault(int(m.group(1), 16), set()).add(
                        os.path.relpath(path, REMAKE))
    return out


def impact(entry):
    """按 writes 落在哪些区段打分（分越高越"玩家可观察"）。"""
    score, tags = 0, []
    writes = [int(w, 16) for w in (entry.get("writes") or [])]
    writes = [w for w in writes
              if w not in NON_RULE_GLOBALS and not in_non_rule_region(w)]
    for weight, name, lo, hi in IMPACT_REGIONS:
        if any(lo <= w < hi for w in writes):
            score += weight
            tags.append(name)
    return score, tags


def load_wndproc_flags():
    """哪些函数**是窗口过程**（WndProc）—— 它们天生不可无头驱动。

    判据（扫 `gen/db.txt` 的函数体）：出现 `DefWindowProcA`/`BeginPaint`/`EndPaint`
    **或**对 `0x201/0x202/0x203/0x205/0x113/0xf/0x401/0x405/0x406` 这类
    Windows 消息号做比较。`0x42f7fc`（投注屏）就是这样漏过"callee 里有 drawText"
    那条规则的 —— WndProc 自己只做**分发**，真正的绘制在别的函数里。
    """
    flags = set()
    cur = None
    with open(os.path.join(ROOT, "gen", "db.txt"), encoding="utf-8") as fh:
        for line in fh:
            m = NAME_RE.match(line)
            if m:
                cur = int(m.group(1), 16)
                continue
            if cur is None or not line.startswith("  "):
                continue
            if ("DefWindowProcA" in line or "BeginPaint" in line
                    or "EndPaint" in line):
                flags.add(cur)
                continue
            for msg in ("0x201", "0x202", "0x203", "0x205", "0x113", "0x401",
                        "0x405", "0x406"):
                if f"cmp" in line and msg in line:
                    flags.add(cur)
                    break
    return flags


def callee_names(entry, names):
    return [names.get(int(c, 16), c) for c in (entry.get("callees") or [])]


def is_presentation(entry, names, by_va=None, depth=2):
    """表现层判据：自己的被调函数名里出现绘图/窗口名，**或**往下追 2 层能追到。

    ⚠️ 必须追层：`0x40a4e1` 自己只调 `sub_00456280`（名字看不出来），
    而后者调的是 `blitRect_inner` —— 一层就漏。实测 `0x40a4e1` 读的是
    `player+0x04`（颜色）并走 blit，是纯绘制（见
    `docs/systems/map-format.md` 的小地图一节）。
    """
    if by_va is None:
        by_va = {}
    if int(entry["va"], 16) in VERIFIED_PRESENTATION:
        return True
    seen, frontier = set(), [entry]
    for _ in range(max(1, depth)):
        nxt = []
        for e in frontier:
            for c in (e.get("callees") or []):
                cva = int(c, 16)
                cname = names.get(cva, c)
                if any(p in cname for p in PRESENTATION_CALLEES):
                    return True
                if cva in seen:
                    continue
                seen.add(cva)
                ce = by_va.get(f"0x{cva:08x}")       # ★ 按 **VA** 取，不是按名字
                if ce is not None:
                    nxt.append(ce)
        frontier = nxt
        if not frontier:
            break
    return False


def does_file_io(entry, names):
    return any(any(p in c for p in FILE_IO_CALLEES)
               for c in callee_names(entry, names))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="连表现层/CRT 也列出")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    entries = load_entries()
    names = load_names()
    wndprocs = load_wndproc_flags()
    by_va = {e["va"]: e for e in entries}
    tested = vas_in_tests()
    remake = vas_in_remake()

    # 区块内地址也算覆盖：把测试引用的地址映射到所属入口
    covered = set()
    for e in entries:
        va, size = int(e["va"], 16), e["size"]
        if any(va <= t < va + size for t in tested):
            covered.add(va)

    rows = []
    for e in entries:
        va, size = int(e["va"], 16), e["size"]
        if va not in remake or va in covered:
            continue
        entry = e
        score0, _tags0 = impact(entry)
        # ★ 表现层/WndProc **只在它不写规则状态时**才算"不用测"：
        #   `0x004379c9`（银行结息）会弹一个消息框（⇒ 追 2 层能追到 drawText），
        #   但它写玩家/地块字段 —— 早期版本一刀切按 callee 名过滤，会把它**藏起来**。
        #   故这里加 `score0 == 0` 这道闸：只有"只画不写规则"的才排除。
        looks_ui = is_presentation(entry, names, by_va) or va in wndprocs
        if not args.all and (va >= CRT_BOUNDARY
                             or va in VERIFIED_NOT_RULE          # ★ 已复核：表现/配置基建
                             or (looks_ui and score0 == 0)
                             or does_file_io(entry, names)):
            continue
        score, tags = impact(entry)
        rows.append((score, size, va, entry, sorted(remake[va]), tags))

    # 先按「玩家可观察」打分降序，再按字节升序 —— 高分且小的最适合先做
    rows.sort(key=lambda r: (-r[0], r[1]))
    total = sum(r[1] for r in rows)
    print(f"通道 2 待测候选（复刻引用过、测试没驱动过、非表现层/CRT）："
          f"**{len(rows)} 个 / {total} 字节**\n")
    print(f"{'分':>3} {'字节':>6} {'VA':>12} {'读':>3} {'写':>3} {'调':>3}  影响面 / 复刻侧引用")
    for score, size, va, entry, files, tags in rows[: args.limit]:
        print(f"{score:>3} {size:>6} {entry['va']:>12} "
              f"{len(entry.get('reads') or []):>3} {len(entry.get('writes') or []):>3} "
              f"{len(entry.get('callees') or []):>3}  "
              f"{('/'.join(tags) or '-')[:14]:<14} "
              f"{', '.join(f.split('/')[-1] for f in files[:3])}")
    if len(rows) > args.limit:
        print(f"… 另有 {len(rows) - args.limit} 个（--limit 调整）")

    if args.all:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
