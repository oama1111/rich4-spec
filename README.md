# rich4-spec —— 《大富翁4》1:1 复刻规格体系

原版《大富翁4 超时空之旅》(v3.11, 2001, 大宇资讯) 的**逆向规格**。
目标：让开发人员能照此实现 1:1 复刻，**而不是每次遇到问题才去汇编里找答案**。

> 实现代码在 `../rich4-remake/`，本目录只放规格与工具。

## 为什么是"体系"而不是"一份大 PRD"

"读完 15 万行汇编写一份完整 PRD"这条路是**无界**的：永远还剩边界情况，
且人工转录已被证实会引入错误（既有审计记录 **8 处**实质错误）。

本目录改为三层结构，每层做它**擅长的**事：

| 层 | 产出 | 性质 |
|---|---|---|
| **机械层** | 全函数清单、调用图、全局字段 xref、跳表、数据段布局 | **不含推断，可机械校验**，因此不会错 |
| **语义层** | 各玩法系统的高颗粒度规格，每条带 `VA` 引用与汇编摘录 | 承载约 80% 的稳定契约 |
| **验收层** | 二进制真值测试、单函数差分、状态指纹差分 | 回答"这条到底对不对" |

剩下的未知不靠文档消灭，而靠**查索引**或**跑差分**廉价回答。

## 目录

```
tools/rich4dis.py         递归遍历反汇编器（代码：函数/调用图/xref/跳表）
tools/rich4strings.py     字符串表与数据段布局（数据：7,146 条串 + 区间切分）
tools/annotate.py         ★ 函数注解库：把 IAT 解析成 API 名 → gen/db.txt（全库反汇编）
tools/lint_specs.py       规格质检（校验 VA 引用真实性与证据密度）
tools/difftrace.py        ★ 状态轨迹比对（通道 3 工具，原版预言机待建）
tools/coverage.py         ★ 覆盖度追踪：按玩法系统度量覆盖与证据密度
tools/emulate.py          ★ Unicorn 仿真台：直接执行原版函数（差分测试用）
tools/scratch/            子代理分析时的临时脚本，非主线，仅供参考
tests/test_toll.py        ★ 过路费差分测试（13/13 通过，含 owner 1 基回归）
tests/test_prng.py        ★ PRNG 差分测试（6/6 通过）
tests/test_wealth.py      ★ 总资产差分测试（18/18 通过）
tests/test_tables.py      ★ 数据表结构真值 + 卡片/台词不变量（22/22 通过）
gen/functions.json        1,388 个函数：调用者/被调用者/读写的全局地址
gen/xrefs.json            2,259 个全局地址的读/写者函数
gen/jumptables.json       69 个跳表
gen/strings.json          7,146 条字符串（含中文 6,388）
gen/string-xrefs.json     340 条被引用字符串 → 引用它的函数（★ 语义定位利器）
gen/layout.json           2,349 个数据段区间（字符串/指针表/数值/bss）
gen/db.txt                ★ 全库反汇编 114,312 行，调用点已解析为名字（707 处 API）
gen/annotations.json      1,459 个函数的一行摘要
gen/imports.json          122 个导入函数：IAT 槽 → DLL!函数名
docs/00-methodology.md    证据等级、三条铁律、诚实边界、文档模板
docs/01-mechanical-layer.md  PE 结构、遍历结果、三个必知的坑
docs/02-strings-and-layout.md 字符串表与数据段布局
docs/03-annotated-db.md   ★ 注解库与架构结论（渲染是 WM_PAINT 驱动等）
docs/systems/economy.md   金钱与资产核算（总资产公式，含股价表步长 0x24 的坑）
docs/systems/*.md         各玩法系统规格，含**表现层四模块**：
                          地产/卡片/道具/新闻/命运/股市/银行/监狱/医院/神明/
                          魔法屋/小游戏/AI/回合/渲染/存档
                          + ★ UI 界面 / 动效 / 台词与语音 / 效果音
docs/coverage.md          ★ 覆盖度追踪表（自动生成）
docs/verification.md      验收层：什么做不到，三条通道怎么做
docs/systems/*.md         各玩法系统规格
```

## 快速开始

```bash
python3 tools/rich4dis.py info                          # 段信息 + 函数指针表
python3 tools/rich4dis.py func 0x419744 --orphans        # 反汇编过路费函数
python3 tools/rich4dis.py boundaries --orphans           # 覆盖率与边界冲突体检
python3 tools/rich4dis.py gaprefs                        # 未覆盖区有没有指令指向
python3 tools/rich4dis.py tail --orphans                 # 剩余部分归因（填充/不可达/数据）
python3 tools/rich4dis.py build --orphans                # 重建 gen/functions|xrefs|jumptables.json
python3 tools/rich4strings.py build                      # 重建 gen/strings|string-xrefs|layout.json
python3 tools/rich4strings.py find 均富                   # 按文本搜字符串
python3 tools/rich4strings.py refs 0x465f53              # 谁引用了这条串
python3 tools/annotate.py build                          # 重建 gen/db.txt + annotations.json
python3 tools/annotate.py show 0x419744                  # 单函数带注解反汇编
python3 tools/lint_specs.py                              # 规格文档质检
python3 tools/coverage.py --write                        # 刷新覆盖度追踪表

python3 tools/difftrace.py selftest                      # 轨迹比对工具自检
bash run-all-checks.sh                                   # ★ 一键自检（机械层+质检+差分+轨迹）

# 验收层：用 Unicorn 执行原版机器码做差分（需 .venv）
python3 -m venv .venv && .venv/bin/pip install unicorn capstone
.venv/bin/python tests/test_toll.py                      # 过路费差分测试 → 13/13
.venv/bin/python tests/test_prng.py                      # PRNG 差分测试 → 6/6
.venv/bin/python tests/test_wealth.py                    # 总资产差分测试 → 18/18
.venv/bin/python tests/test_tables.py                    # 数据表结构真值 → 15/15
```

依赖：`python3 -m pip install capstone`

## 现状（据实）

| 项 | 数值 |
|---|---|
| 已建图函数 | **1,388** |
| 代码段覆盖 | **365,331 / 394,240 = 92.7%** |
| 函数边界冲突 | **0** |
| 已解析跳表 | **69** |
| 规格文档 | **19 份 / 11,500+ 行 / 3,049 个唯一 VA 引用** |
| 差分测试 | **4 个 / 59 个用例全通过** |
| 剩余未覆盖的归因 | 不可达代码 81.7%、内嵌数据 16.9%、对齐填充 1.5% |

## 铁律

1. **唯一真值是 `../Rich4/rich4.exe`**。`rich4-re` 是有价值的线索，
   但已证实含错，**不是真值**。
2. 凡逻辑结论必须给 `@source VA`，关键处附汇编原文摘录。
3. 数值表必须以 exe 为基准做常驻测试，禁止人工转录后无校验。
4. 未知就写「未决」，**不要用推测填充**。

详见 `docs/00-methodology.md`。

## 版权

原作版权归**大宇资讯 / 软星科技**所有。本目录为互操作性逆向分析成果，
采用 GPL-3.0-or-later（与 `../rich4-remake/` 一致）。
