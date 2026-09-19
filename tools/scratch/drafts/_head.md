# 各屏内部绘制函数（表现层 · 阶段 1 收口）

> **这份文件回答什么**：`ui.md` 讲的是输入架构、窗口消息路由、模态界面与导航；
> 本文件补齐**每一屏内部**那些绘制 / 版式 / 命中函数——它们在原版里是
> `0x40xxxx`–`0x44xxxx` 段里成百上千个小函数，此前 PRD **一次都没提**，
> 知识只存在于复刻代码的注释里。
>
> **为什么现在补**：阶段 1 的收口工作单 `tools/audit_prd_gaps.py` 曾报出
> **106 个函数 / 13,861 字节**属于「remake 已经引用过、PRD 未收」。本文件收掉其中
> **103 个**（全部在 `client/`），另外 3 个分别落进 `game-loop.md`（`0x40d4e5`）
> 与 `cards.md`（`0x446457` / `0x4464c3`）。收完后该工作单应为 **0**。

## 证据等级（本文件统一口径）

| 级 | 含义 |
|---|---|
| **A** | **exe 逐字**：结论能指回 `gen/db.txt` 里该地址的指令，或能指回一张表 / 全局的地址 |
| **B** | 由 A 级事实**直接推出**（括注推的是哪条 A 级事实）|
| **C** | 只有 remake 侧注释转述、**本轮未回 exe 复核**——当真值用之前必须复核 |

> ⚠️ 真值只有 `Rich4/rich4.exe`。`rich4-remake` 的注释是**线索**，不是真值；
> 本轮已抓到 **多处**「remake 注释与 exe 冲突」，全部记在各自小节的未决里，
> **没有替 remake 圆场**。

## 方法（可复算）

1. 工作单：`python3 tools/audit_prd_gaps.py`（按「提到它的 remake 文件」归组）。
2. 逐函数档案：`python3 tools/scratch/prd_gap_pack.py` —— 每个 VA 一段：
   汇编前 40 条 + callees（带名）+ `push` 的字符串 + 触碰的全局 + remake 引用上下文。
3. 分组：`python3 tools/scratch/split_gap_groups.py` → `tools/scratch/gap-g*.txt`。
4. 复核：本节所有地址都能用 `grep -n '<VA>' gen/db.txt` 在 `db.txt` 里找到。

## 一、总览（103 个函数 / 13,568 字节）

| 节 | 主题 | 函数 | 字节 | 主要 remake 文件 |
|---|---|---|---|---|
| §二 | 商店屏 / 遊戲說明屏 / 標題頁选项副屏 | 20 | 3,141 | `shop-screen.ts` `help-screen.ts` `options.ts` `options-pages.ts` |
| §三 | 樂透 / 抽獎 / 輪盤 / 小遊戲 / 魔法屋 | 15 | 2,196 | `lottery-draw-screen.ts` `lottery-screen.ts` `wheel-screen.ts` `minigame-screen.ts` `magic-screen.ts` |
| §四 | 公佈欄屏（棋盘位）/ 個人資產表 / 大地圖 / HUD | 21 | 3,032 | `board-screen.ts` `asset-sheet.ts` `big-map-screen.ts` `hud.ts` `picking.ts` `render.ts` |
| §五 | 保釋 / 月結頒獎 / 銀行 / 股市 / 股份 | 17 | 1,895 | `bail-screen.ts` `monthly-screen.ts` `stock-screen.ts` `shares-screen.ts` |
| §六 | 主流程 / 開局設定 / 神明槽 / 設定屏 / AI 設定 | 29 | 3,013 | `main.ts` `setup.ts` `god-slot.ts` `ai-settings.ts` |
| §七 | 拍賣結算演出 + 3 个非 UI 残项（转出到 `game-loop.md` / `cards.md`）| 4 | 584 | `auction-screen.ts` `blocking.ts` `land-cards.ts` |

**命名提醒（子代理在核对时发现）**：`client/board-screen.ts` 对应的那一屏在原版里是
**公佈欄**（`_rich4_sale_entry`，`VA 0x004284be`），不是「棋盘绘制屏」。
本文件 §四 按原版叫它**公佈欄屏**，避免与「地图/棋盘渲染」混为一谈。

`@source` 本文件的地址口径：全部取自 `gen/db.txt`（由 `tools/rich4dis.py` 从
`Rich4/rich4.exe` 反汇编）与 `gen/jumptables.json`、`gen/strings.json`。

