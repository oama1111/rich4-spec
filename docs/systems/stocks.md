# 股票市场与企业（股市 / 上市企业）

> 真值：`../Rich4/rich4.exe`（v3.11, 2001, 大宇资讯；ImageBase `0x400000`）。
> 本文件所有 `@source` 均为**原版虚拟地址（VA）**。`../rich4-re/` 只作线索，
> 凡与 exe 冲突处一律以 exe 为准，冲突已单独列在第九节。

---

## 〇、本文件的验证方式与证据级别

### 验证方式

| 手段 | 命令 | 用途 |
|---|---|---|
| 全量建图 | `python3 tools/rich4dis.py func <VA> --orphans` | 取含分支块的完整函数体 |
| 结构化读表 | 自写脚本按 VA→文件偏移直读 exe 字节（`AUTO` 0x401000/1024/394240；`DGROUP` 0x463000/398848/158720） | 96 条股票记录、常量池、跳表 |
| 调用者反查 | 扫描 `AUTO` 段全部 `E8 rel32` / `E9 rel32` 求目标 | `gen/functions.json` 的 `callers` 对本系统**大面积缺失**（这些函数是跳表/间接进入），必须自己扫 |
| 字段读写者 | `gen/xrefs.json` + 逐函数 capstone 反汇编正则匹配 | 判定「谁写了这个字段」 |
| 导入名解析 | 解析 `.idata`（0x462000）的 hint/name 与 IThunk（值为 **RVA**） | 确认 `call cs:[0x4623cc]` = `GetTickCount`、`[0x4622a0]` = `FloodFill` |

### 证据级别

| 级别 | 含义 | 本文件中的使用 |
|---|---|---|
| **A** | 直接读自 exe 的指令/字节 | 结构布局、公式、常量、条件顺序、调用点 |
| **B** | 由 A 级证据**推断**的命名/语义 | 字段命名、「保留股份/流通股」这一层解释 |
| **C** | `rich4-re`（2018 csrc / 2026 asm） | **只作线索**，凡采纳均回 exe 复核并在正文注明 |
| **未决** | 无法从静态反汇编确定 | 明确写「未决」，**不用推测填充** |

### 汇编摘录的约定（**读之前必看**）

本文件的 `asm` 块是**关键指令摘录**，不是完整函数体：

- 省略了 x87 比较后的 `fnstsw ax` / `sahf` 样板（每一处 `fcomp` 后都有）；
- 省略了与结论无关的 `push`/`add esp`/寄存器搬运；
- **部分 `jmp` 未列出** ⇒ 相邻两行**不一定**是顺序执行的。控制流一律以**文字说明**
  与「行尾 `;` 注释里的跳转目标」为准；需要逐条核对时用
  `python3 tools/rich4dis.py func <VA> --orphans` 取完整函数体。

### 本文件独立复核过、且**推翻或订正**了既有说法的条目（摘要，详见第九节）

1. `rich4_stocks.h` 把 `player_stock_info` 第二字段标成 `int _` —— **实为 `float` 持仓成本均价**（A，见 §5.1）。
2. 既有文档「卖出不触发企业归属重排」—— **错**，`_rich4_sell_stock` 尾部确有 `call 0x4294d5`（A，见 §6.3）。
3. 「股票表 96 项每项含名称与 4 个浮点字段」—— **口径要修**：96 是**记录数**，**步长 36 字节**；
   记录内含 **4 个有效浮点字段**（`+0x0c/+0x10/+0x14/+0x18`），另有 `+0x1c/+0x20` 两个 float 槽在**运行期**才写入。
   题面提示的 `dump 0x47f072 96 16` **跑不通**（width 只支持 1/2/4），**不可用**（A，见 §1.1）。
4. 既有文档「[0x499084] = 總天數」—— **实为「经过的月数」**（A，见 §6.4）。
5. 「企業資產額會進玩家總資產」—— **不成立**：`_rich4_calculate_player_wealth` 里没有任何企业项（A，见 §5.4/§6.2）。

---

## 一、股票表与「每张地图可交易集合」

### 1.1 `game_stocks` @ `0x47f072` —— **96 条记录 × 36 字节**

**结论（A）**：`0x47f072` 起是一张 **96 条、每条 36 字节**（共 3456 = `0x47f072..0x47fdf1`）的静态表，
= **8 张地图 × 每图 12 支**。记录布局与运行期表 `stocks_on_map`（`0x496980`）**完全同构**：

| 偏移 | 类型 | 字段 | 含义 | 可靠性 |
|---|---|---|---|---|
| `0x00` | `char *` | `name_ptr` | 股票名（Big5，指向 `0x4667xx` 的字符串） | A |
| `0x04` | `uint16` | `company_flag` | 开局为 **1 = 這支股票有上市公司**，`0` = 無；**运行期会被改写成 1 基企业序号**（见 §1.3） | A |
| `0x06` | `uint8` | `pause_days` | **停牌倒数天数**（>`0` = 停牌中） | A |
| `0x07` | `uint8` | `news_dir` | **新闻强制方向/天数**：高半字节 ⇒ 连涨、低半字节 ⇒ 连跌 | A |
| `0x08` | `uint16` | `float_shares` | 「流通股数」；建图时 `企業+0x30 = 10000 − 本字段` | A（算术）/ B（命名） |
| `0x0a` | `uint16` | `avail_shares` | 柜台**可买上限**；行情表「交易量」列显示它 | A |
| `0x0c` | `float` | `base_price` | **初始股价**；同时也是**无上市公司**那几支的均值回归锚点 | A |
| `0x10` | `float` | `open_price` | **开盘价**（每日由前一日收盘价覆写） | A |
| `0x14` | `float` | `price` | **成交价（现价）** | A |
| `0x18` | `float` | `volatility` | **波动系数**（每日随机项的乘数） | A |
| `0x1c` | `float` | `momentum` | **累积动能**（运行期状态，见 §2） | A |
| `0x20` | `float` | `last_random` | 当日抽到的**随机量 r**（运行期状态） | A |

**4 个「有效浮点字段」是 `+0x0c / +0x10 / +0x14 / +0x18`。**
静态表里 `f12 = f16 = f20`（三份写同一个初始价）、`f24 = 0.4..2.0` 的波动系数，
`f28`（`+0x1c`）与 `f32`（`+0x20`）恒为 `0.0`（它们是运行期状态槽，静态表只占位）。

**实测样本（前 3 条 / 后 3 条，脚本直读 exe）**：

```
[ 0] 中國信託   flag=1 +8=10000 f12=f16=f20=100.0   vol=1.0
[ 1] 臺灣人壽   flag=1 +8= 5000 f12=f16=f20= 40.0   vol=0.6
[ 2] 大宇百貨   flag=1 +8=10000 f12=f16=f20= 25.0   vol=1.5
...
[93] 可口可樂   flag=0 +8=10000 f12=f16=f20= 30.0   vol=0.8
[94] 麥當勞     flag=0 +8=10000 f12=f16=f20= 44.0   vol=1.0
[95] 愛迪達     flag=0 +8=10000 f12=f16=f20= 30.0   vol=1.2
```

**⚠️ 「96 项」的口径**：`96 = 8 图 × 12 支`，是**记录数**。
题面/工具提示里的 `dump 0x47f072 96 16` **用不了**：
`tools/disasm.py dump` 的 width 只支持 `1/2/4`，传 `16` 会直接 `KeyError`；
即便按「96 × 2 字节」去理解，也只覆盖 192 字节 = 5.33 条记录。
必须按 **步长 36 字节**读（本文件用自写脚本直读 exe 验证）。

`@source`：表首 `0x47f072`；步长在代码里是 `imul eax, eax, 0x…` 系列的 `*9*4` 展开：

```asm
; 0x402c94（读档时逐条改写 name_ptr）
00402c94  mov   eax, ebx
00402c96  shl   eax, 3
00402c99  add   eax, ebx        ; eax = i*9
00402c9b  shl   eax, 2          ; eax = i*36        ★ 步长 36
00402c9e  lea   edx, [esi + eax]     ; esi = 432*gid
00402ca1  mov   edx, dword ptr [edx + 0x47f072]   ; 静态表第 gid*12+i 条的 name_ptr
00402ca7  mov   dword ptr [eax + 0x496980], edx   ; 写回运行期表第 i 条的 name_ptr
```

**复核既有说法**：`rich4-re/asm/rich4_all_stocks.c` 的 96 条与本次直读 exe **逐字段一致**
（名称、`flag`、`+8`、三份初始价、`volatility`、末尾两个 0）。该表确为「直接从 exe 生成」，
本次复核**未发现任何差异**。但它把这张表当**数据表**用；实际上 exe 里它同时是
**新局的数值来源**（见 §1.2）。

### 1.2 每张地图的 12 支如何确定（`stocksOfMap` 的对应关系）

**判定式（A）**：全局 `gid = [0x4991b6] * 4 + [0x4991b8]`。
`[0x4991b6]` = **关卡（stage）**，`[0x4991b8]` = **地图（map 0..3）**；
`gid` 即 `0..7`，与既有的 `global_map_id = game_stage*4 + game_map` 一致。

```asm
; 0x407410 新局把静态表整块 432 字节拷进运行期表
0040740b  push  0x1b0                     ; 432 = 12 * 36
00407410  movsx eax, word ptr [0x4991b6]  ; stage
00407417  shl   eax, 2
0040741a  movsx edx, word ptr [0x4991b8]  ; map
00407421  add   edx, eax                  ; edx = gid = stage*4 + map
00407423  mov   eax, edx
00407425  shl   eax, 2
00407428  sub   eax, edx                  ; *3
0040742a  shl   eax, 4                    ; *48
0040742d  mov   edx, eax
0040742f  shl   eax, 3                    ; *384
00407432  add   eax, edx                  ; *432
00407434  add   eax, 0x47f072             ; ★ 源 = game_stocks[gid*12]
00407439  push  eax
0040743a  push  0x496980                  ; 目标 = stocks_on_map
0040743f  call  0x456de8                  ; memcpy(dst, src, 0x1b0)
```

同一个 `gid` 也在 `0x406e3a` 用来开地图资源（`gid` 就是 map 资源号）：

```asm
00406e3a  movsx edx, word ptr [0x4991b6]
00406e41  shl   edx, 2
00406e44  movsx ecx, word ptr [0x4991b8]
00406e4b  add   edx, ecx
00406e4d  push  edx                       ; 资源号 = gid
00406e4f  call  0x450441                  ; 开资源
```

`0x401cbf` 是「新局」的跳表入口，它把 stage 硬置为 `1`（⇒ `gid = 4..7`）；
`0x401cc8`（跳表第 0 项）不带这一句（⇒ `gid = 0..3`）。地图号由**上一层的关卡选择流程**给出
（`0x401cac call 0x4029fd` 取选择结果，跳表 `0x401b78` 只用到前 5 项）：

```asm
00401cac  call  0x4029fd                   ; 取选择结果 → ebx
00401cb3  cmp   ebx, 4
00401cb6  ja    0x401d2b                   ; >4 → 进消息循环
00401cb8  jmp   dword ptr [ebx*4 + 0x401b78]
00401cbf  mov   word ptr [0x4991b6], 1     ; ★ 只有这一支设 stage=1
00401cc8  xor   eax, eax
00401cca  mov   al, byte ptr [0x46cafc]    ; ★ 地图号（0..3）
00401cd0  call  0x406de7                   ; 地图资料初始化（含 §1.2 的 memcpy）
00401ce1  call  0x407ad2                   ; 地产/企业表 + 保留股份
00401ceb  call  0x4291d6                   ; ★ 开局先跑一次行情
```

> **注（本规格边界）**：「关卡→(`stage`,`map`)」的菜单映射属开局流程，**未决**；
> 本规格只钉住 `gid = stage*4 + map` → `game_stocks[gid*12 .. gid*12+11]` 这条契约。

存读档路径：`0x402ac5`（读 `SAVE%d.DAT`）先 `fread` 12×36 字节进 `0x496980`，再用静态表的
`name_ptr` 覆写每条的 `0x00` 字段 —— 即**存档存数值、不存指针**。
`0x448544`（读档进内存）同形（`0x448825/0x44882b`）。

### 1.3 运行期表 `stocks_on_map` @ `0x496980`（12 × 36）

布局与 §1.1 表**完全相同**（`+0x04` 是唯一语义有变的字段）。相关全局：

| 地址 | 名称 | 说明 |
|---|---|---|
| `0x496980` | `stocks_on_map` | 12 条 × 36 字节 = 432，`0x496980..0x496b2f` |
| `0x4971a0` | `player_stocks` | 4 人 × 12 支 × 8 字节 = 384，`0x4971a0..0x49731f` |
| `0x497328` | `stock_history` | 12 × **144** × 4 字节（`float`）= 6912，`0x497328..0x498e27` |
| `0x499100` | `history_slot` | 环形下标 `0..0x8f` |
| `0x499078` | `market_sum_x10` | `trunc(Σ 12 支现价 × 10.0f)`，**只被存档写出，无逻辑读取**（未决） |
| `0x49907c` | `init_sum_x10` | 新局 `trunc(Σ 12 支 base_price × 10.0f)`，同上（未决） |
| `0x4990ec` | `market_drift` | 当日**全市场漂移** `(rand−0x4000)/4097.0f` |
| `0x4990e8` | `price_index` | 物价指数（§2.6） |
| `0x4990dc` | `market_close_days` | 全股市暂停交易倒数（§3.2） |
| `0x49908c` | `init_money` | 开局资金档位（`0x46cb94` 表：`300000/200000/100000/50000/30000/10000`） |
| `0x4990e4` | `day_counter` | 每日 +1 |
| `0x499084` | `month_counter` | **每次日期跨月 +1**（§6.4） |
| `0x497160` | `date` | `年<<16 | 月<<8 | 日`（低字节 = 日） |
| `0x498e7c` | `commercial_ptr` | 上市企业表基址（**1 基**，步长 `0x34`） |
| `0x498e90` | `num_commercials` | 企业数（1 基表的有效末下标） |

**`+0x04` 的改写（A）**：`_rich4_init_stock_commercial` @ `0x428caf`（由地图加载 `0x408072` 调用）
把 `flag`（`1`）改写成**该企业在本图企业表里的 1 基序号**。判定依据是
`企业+0x19`（企业记录里存的「对应股票行号」，0 基）：

```asm
00428cb1  xor   esi, esi                    ; esi = 股票行号 0..11
00428cc1  mov   eax, esi
00428cc3  shl   eax, 3
00428cc6  add   eax, esi                    ; *9
00428cc8  cmp   word ptr [eax*4 + 0x496984], 0   ; stock+4 == 0 ?
00428cd1  je    0x428cbb                    ;   无上市公司 → 跳过
00428cd3  mov   edx, 1                      ; edx = 1 基企业序号
00428cde  add   ecx, 0x34                   ; &commercial[edx]
00428ce7  mov   al, byte ptr [ecx + 0x19]   ; 企业+0x19 = 股票行号
00428cea  cmp   eax, esi
00428cec  jne   0x428cfb
00428cf3  mov   word ptr [eax*4 + 0x496984], dx   ; ★ stock+4 = 1 基企业序号
```

> ⚠️ 该循环**找到后不 break**，若同一张图有两家企业都指向同一支股票，**最后一家赢**；
> 若 12 支里没有任何企业指向它，`+0x04` 会**停在 1**（一个非 0 的假企业序号）。
> 8 张图的实际数据里没有这种情形，但复刻时要照抄这段（不 break）。

---

## 二、股价变动公式

### 2.1 每日行情 `fcn_004291d6`（192 条指令，`0x4291d6`）

**调用者（A，自扫直接调用）**：仅两处
- `0x41d076` —— 日期推进函数 `fcn_0041cf67` 内（**每回合一次**，§7.1）
- `0x401ceb` —— 新局跳表入口 `0x401cbf` 内（**开局先跑一次**）

**总流程（A）**：

```asm
004291e2  call  0x428d01        ; 休市判定
004291e7  cmp   eax, 1
004291ea  je    0x4294cd        ; ★ 休市 → 整天不跳价，直接 return
004291f0  call  0x456f2d        ; ★ rand() #1（全市场漂移）
004291f5  sub   eax, 0x4000
004291fe  fild  dword ptr [esp + 8]        ; 单精度源
00429202  fdiv  dword ptr [0x463fc4]       ; / 4097.0f   ← 单精度
00429208  fstp  dword ptr [0x4990ec]       ; ★ market_drift ∈ [-3.9990, +3.9995]
0042920e  xor   esi, esi                   ; i = 0..11
00429210  mov   ebp, 0xc1200000            ; -10.0f
00429215  mov   edi, 0xc1200000            ; -10.0f
```

每支股票的循环头（`0x429470`）：

```asm
0042947a  mov   eax, dword ptr [ebx + 0x496994]   ; 现价
00429480  mov   dword ptr [ebx + 0x496990], eax   ; ★ 开盘价 = 前一日现价
00429486  cmp   byte ptr [ebx + 0x496986], 0      ; 停牌倒数
0042948d  je    0x42921f                           ;   未停牌 → 正常路径
00429493  xor   edx, edx
00429495  mov   dword ptr [ebx + 0x49699c], edx   ; ★ 停牌：动能清零
0042949b  jmp   0x429413                           ;   仍走 apply（价格 = 开盘价，不变）
```

正常路径（`0x42921f`）：

```asm
0042921f  mov   dl, byte ptr [ebx + 0x496987]     ; news_dir
00429225  test  dl, dl
00429227  je    0x429248                           ; ==0 → 随机路径
00429229  test  dl, 0xf0
0042922e  mov   dword ptr [ebx + 0x49699c], 0x41200000   ; 高半字节 → 动能 = +10.0f
0042923d  mov   dword ptr [ebx + 0x49699c], ebp          ; 低半字节 → 动能 = -10.0f
; ── 随机路径 ──
00429248  call  0x456f2d                           ; ★ rand() #2..#13
0042924d  sub   eax, 0x4000
00429256  fild  dword ptr [esp + 8]
0042925a  fdiv  dword ptr [0x463fc8]               ; / 1171.0f   ← 单精度
00429260  fst   dword ptr [ebx + 0x4969a0]         ; +0x20 = r
00429266  fmul  dword ptr [ebx + 0x496998]         ; * volatility        ← 单精度
0042926c  fadd  dword ptr [ebx + 0x49699c]         ; + 昨日动能           ← ★ 动量累加
00429272  fstp  dword ptr [ebx + 0x49699c]
00429278  fld   dword ptr [0x4990ec]
0042927e  fadd  dword ptr [ebx + 0x49699c]
00429284  fstp  dword ptr [ebx + 0x49699c]         ; ★ + 全市场漂移
```

> ★★ **关键**：`+0x1c` **不是**「当日涨跌」，而是**累积动量**。随机路径是
> `momentum = momentum + r*vol + drift`，**没有清零**（只有停牌那一支清零）。
> 因此存在跨日动量：昨天的涨跌会带进今天。

均值回归阻尼（`0x4292b7..0x4293d1`）—— 分「有上市公司 / 无上市公司」两支，
用**开盘价**与锚点比较，只对**远到一定程度之外**的股票做缩放：

| 支 | 锚点 | 上方带 | 下方带 | 触发条件 | 动作 |
|---|---|---|---|---|---|
| 有上市公司 | `企業+0x24 ÷ 10000.0f`（每股净值） | `×3.0f` | `×0.85`（**double**） | 开盘 **>** 3×锚点 或 开盘 **<** 0.85×锚点 | 动能正 → `×0.5f`；动能 ≤0 → `×2.0f`（下方支反过来） |
| 无上市公司 | `stock+0x0c`（初始股价） | `×8.0f` | `×0.5f` | 开盘 **>** 8×锚点 或 开盘 **<** 0.5×锚点 | 同上 |

```asm
004292a9  fild  dword ptr [edx + eax + 0x24]     ; 企業資產額（int）
004292ad  fdiv  dword ptr [0x463fd8]             ; / 10000.0f   ← 单精度
004292b3  fstp  dword ptr [esp + 4]              ; anchor
004292b7  fld   dword ptr [ebx + 0x496990]       ; 开盘
004292bd  fcomp dword ptr [esp + 4]
004292c4  jbe   0x429316                          ; 开盘 <= anchor → 下方支
004292ca  fmul  dword ptr [0x463fe4]             ; anchor * 3.0f
004292e1  jbe   0x4293d2                          ; 开盘 <= 3*anchor → 只做 clamp
004292e9  fcomp dword ptr [ebx + 0x49699c]
004292f2  jae   0x429305                          ; 动能 <= 0
004292fa  fmul  dword ptr [0x463fcc]             ; ★ 动能 *= 0.5f
0042930b  fmul  dword ptr [0x463fd0]             ; ★ 动能 *= 2.0f
0042931a  fmul  qword ptr [0x463fdc]             ; ★★ 唯一一处 qword：anchor *= 0.85（双精度）
```

限幅（`0x4293d2`，注意上下不对称）：

```asm
004293dc  cmp   dword ptr [eax + 0x49699c], 0x41200000  ; ★ 整数比较（原始位型）
004293e6  jle   0x4293f2
004293e8  mov   dword ptr [eax + 0x49699c], 0x41200000  ; 上界 = +10.0f
004293fc  fld   dword ptr [ebx + 0x49699c]
00429402  fcomp dword ptr [0x463fe8]                     ; 下界 = -10.0f（浮点比较）
0042940b  jae   0x429413
0042940d  mov   dword ptr [ebx + 0x49699c], edi           ; = -10.0f
```

应用与落档（`0x429413`）：

```asm
00429413  mov   ebx, esi
0042941a  push  dword ptr [ebx*4 + 0x49699c]   ; arg1 = 动能（当 delta 用）
00429421  push  dword ptr [ebx*4 + 0x496990]   ; arg2 = 开盘价
00429428  call  0x428ec5                        ; ★ 定价函数（§2.2）
00429438  fstp  dword ptr [ebx*4 + 0x496994]   ; 现价 = 返回值
0042944a  mov   eax, dword ptr [0x499100]      ; 环形槽
00429456  mov   dword ptr [edx + eax*4 + 0x497328], ecx   ; history[i][slot] = 现价
```

收尾：

```asm
004294a0  lea   ecx, [eax + 1]
004294a3  mov   dword ptr [0x499100], ecx
004294a9  cmp   ecx, 0x90
004294af  jne   0x4294b9
004294b1  xor   esi, esi
004294b3  mov   dword ptr [0x499100], esi      ; ★ 144 槽环形
004294b9  fld   dword ptr [esp]                ; Σ 现价（单精度累加）
004294bc  fmul  dword ptr [0x463fec]           ; × 10.0f
004294c2  call  0x457dbc                       ; __round_toward_zero
004294c7  fistp dword ptr [0x499078]           ; market_sum_x10
```

### 2.2 定价函数 `0x428ec5`（`apply_price_change`）—— 逐项公式

**签名**：`float apply_price_change(float open /*[esp+0x14]*/, float delta /*[esp+0x18]*/)`，
返回 32 位 float 位型（`mov eax,[esp+0xc]`）。

```
① factor = (delta + 100.0f) / 100.0f          ; 单精度内存操作数
② price  = open * factor                      ; 单精度（fstp dword）
③ 若 delta > 0:  diff = price - open ; price = price - fmod((double)diff, step)
   若 delta ≤ 0:  diff = open - price ; price = price + fmod((double)diff, step)
④ 说明：price ∓ fmod(diff, step) 等价于「把相对开盘价的涨跌量向开盘价取整到 step 的整数倍」
⑤ if (price < 1.0f)   price = 1.0f            ; ★ 整数比较（cmp dword,0x3f800000 / jge）
⑥ if (price > 9999.0f) price = 9999.0f        ; ★ 浮点比较（fcomp [0x463fbc]）
```

`step` 由**②算出的新价**分档（`0x428efb..0x428f75`）：

| 新价区间 | `step`（**双精度 qword**） | 对应显示精度（`fcn_00429691`） |
|---|---|---|
| `price < 5.0f` | `fmod(…, 0.01)` = `0.01` | 0 → `"%.2f"` |
| `5.0 ≤ price < 15.0` | `0.05` | 0 → `"%.2f"` |
| `15.0 ≤ price < 50.0` | `0.1` | 1 → `"%.1f"` |
| `50.0 ≤ price < 150.0` | `0.5` | 1 → `"%.1f"` |
| `price ≥ 150.0` | `1.0` | 2 → `"%.0f"` |

### ★★ 通道 2 已整段差分（2026-09-19 第 95 条，`tests/test_stock_price.py` 65/65）

`0x428ec5(open, delta)` 是纯函数（返回值放 **eax 的 float 位型**），已整支驱动并逐位对账。
上面那份公式**全部成立**，另外补三条**此前没写清**的事实：

| # | 事实 | 证据 |
|---|---|---|
| 1 | ★★ `fmod` 走的是 **x87 `fprem`**（`0x45841c`），**不是 C 库 fmod**：当 `diff` 恰是 `tick` 的整数倍时，`fprem` 常常给 **≈0**，而 C 库 fmod 给 **±tick** ⇒ 结果**差一跳**（`(open=20, pct=+10)`：exe **22.0**、C fmod **21.9**）| §E；复现率：通用输入 1200/1200 一致，整数价×整数涨跌族 **39/2800** 差一跳。**复刻现状用的是 JS `%`（= C fmod）⇒ 已登记 T-STOCK-1** |
| 2 | ★ 分界**不是** `k` 的简单函数（`y=0.1` 时 k=7 落 tick、k=8 落 0、k=9 落 tick…）⇒ 要么照抄 `fprem` 的「每轮 3 位商 + PC=53 舍入」，要么登记偏离，**不做启发式修一半** | `tools/scratch/probe4.py` 的 k→tag 表 |
| 3 | ★★ ①②③ 的**中间精度是 x87 扩展（80 位）**，只在落回 f32 时舍一次 ⇒ 用 double 先算再 `fround` 会**二次舍入**，实测 60 例非整数输入里有 2 例差 1 ulp（`open=33.3, pct=±9.5`）。差分测试里用**精确有理数**再舍一次即可复现 | §F 的分数模型 |

**单/双精度标注（重要）**：

- ①②③ 的**内存操作数**：`open`/`delta`/`factor`/`price` 全是 `dword`（**单精度**）；
  `step` 是 `qword`（**双精度**，`fld qword [0x463fb4/…]`）。
- `fmod` 走 `0x45841c`，其核心是 **`fprem`**（不是 `pow`！）：
  ```asm
  0045841c  test  byte ptr [0x48936c], 1
  00458425  fprem                       ; ★ st0 = st0 mod st1
  00458431  jp    0x45841c              ; C2 → 未完成，重试
  00458433  fstp  st(1)
  ```
  exe 里也有它的 C 入口 `0x458436`（`fld qword [esp+0xc] / fld qword [esp+4] / call 0x45841c`
  = `fmod(x, y)`，两个参数都是 **double**）。
- 减/加那一步把 `price` 用 `fstp qword` 提到**双精度**再运算：
  ```asm
  00428f19  fld   dword ptr [esp + 0xc]
  00428f1d  fstp  qword ptr [esp]     ; ★ float → double 提升
  00428f20  fsubr qword ptr [esp]     ; ★ 双精度减法
  ```
  ⇒ **`fmod` 一定在双精度上做**，用单精度复刻会在低价股上出现 1 分钱级差异。
- x87 中间结果天然是 80 位扩展精度；**落回内存时才是单精度**（`fstp dword`）。
  复刻时建议：`factor/price` 用 `float` 存，`diff/step/fmod/加减` 用 `double`。

**常量池实测（A）**：

```
0x463f88 = 100.0f      0x463f8c = 5.0f     0x463f90 = 15.0f    0x463f94 = 50.0f
0x463f98 = 150.0f      0x463f9c = 0.5   (d) 0x463fa4 = 0.1 (d)  0x463fac = 0.05 (d)
0x463fb4 = 0.01   (d)  0x463fbc = 9999.0f 0x463fc0 = 10000.0f
0x463fc4 = 4097.0f     0x463fc8 = 1171.0f
0x463fcc = 0.5f        0x463fd0 = 2.0f    0x463fd4 = 8.0f     0x463fd8 = 10000.0f
0x463fdc = 0.85   (d)  0x463fe4 = 3.0f    0x463fe8 = -10.0f   0x463fec = 10.0f
0x463ff0 = 15.0f       0x463ff4 = 150.0f
0x463194 = 10.0f       0x463190 = 100.0f
0x463cd0 = 0.3    (d)  0x463b60 = 0.2   (d) 0x4641a4 = 0.85 (d) 0x4641ac = 0.7 (d)
```

### 2.3 随机数调用点（可复现性）

**PRNG 本体（A）** = 标准 MSVC `rand`：

```asm
00456f2d  call  0x456f23                  ; 取种子所在地址
00456f37  imul  edx, dword ptr [eax], 0x41c64e6d
00456f3d  add   edx, 0x3039
00456f43  mov   dword ptr [eax], edx
00456f45  mov   eax, edx
00456f47  shr   eax, 0x10
00456f4a  and   eax, 0x7fff               ; 返回 0..32767
```

`0x456f50` = `srand(seed)`（只写种子）。`srand` 全 exe **仅 3 处调用**（自扫）：

| 调用点 | 上下文 | 种子 |
|---|---|---|
| `0x40170f` | 游戏初始化 | `GetTickCount()` |
| `0x402fa1` | 某帧循环前 | `GetTickCount()` |
| **`0x41d06e`** | **日推进里，紧挨在行情更新之前** | **`GetTickCount()`** |

```asm
0041d066  call  dword ptr cs:[0x4623cc]   ; = GetTickCount（已解析 .idata：RVA 0x629ca）
0041d06d  push  eax
0041d06e  call  0x456f50                  ; ★ srand(GetTickCount())
0041d076  call  0x4291d6                  ; 行情更新
```

> ⚠️ **复刻必读**：每日行情在**每次日推进时用墙钟重新播种**。⇒
> 股价序列**无法只靠存档复现**；任何「原版差分测试」都必须在同一 tick 内注入种子，
> 或把 `rand` 换成本项目的可注入 PRNG 并接受这是**有意偏离**。

**一天里 `rand()` 的消耗次数（A）**：
`1 + #{ i : stock[i].+0x06 == 0 且 stock[i].+0x07 == 0 }`。
停牌支与 `news_dir != 0` 支都**不消耗**随机数 —— 因此**消耗次数随状态变化**，
复刻时不能假设每天固定 13 次。

### 2.4 涨跌幅的**实际范围**

```
raw    = r × volatility + momentum_old + drift
         r          ∈ [-16384/1171, 16383/1171] = [-13.9915, +13.9906]
         volatility ∈ [0.4, 2.0]                （静态表实测）
         drift      ∈ [-16384/4097, 16383/4097] = [-3.9990, +3.9995]
damped = raw × 0.5 或 raw × 2.0（视锚点带内外与符号；见 §2.1 表）
momentum_new = clamp(damped, ...)              ; 上界用整数比较 +10.0f，下界用浮点比较 -10.0f
price  = apply_price_change(open, momentum_new) ; |Δ| ≤ 10% 且向开盘价量化到 step
硬边界 = [1.0f, 9999.0f]（apply 尾部）
```

**结论**：单日涨跌幅**硬上限 ±10%**（限幅在 apply 之前），
下限使价格不低于 `1.0`、上限不高于 `9999.0`。没有「涨跌停」以外的额外波动率限制。

### 2.5 新闻/事件的**即时跳价** `0x429040`（82 条指令）

**签名**：`int fcn_00429040(int stock_1based)`；`0` = 对全部 12 支做一遍。

```asm
00429047  mov   esi, dword ptr [esp + 0x18]   ; 1 基股票号；0 = 全部
0042904b  mov   edi, dword ptr [0x499100]
00429051  dec   edi
00429052  test  edi, edi
00429056  mov   edi, 0x8f                     ; ★ slot-1（负数回绕到 143）
00429070  mov   dl, byte ptr [eax + 0x496987] ; +7
0042907e  test  dl, 0xf0
00429083  mov   dword ptr [eax + 0x49699c], 0x41200000   ; +10.0f
0042908f  mov   dword ptr [eax + 0x49699c], 0xc1200000   ; -10.0f
004290af  call  0x428ec5                       ; 用「現有的開盤價」重算
004290bf  fst   dword ptr [ebx*4 + 0x496994]   ; 现价
004290d3  fstp  dword ptr [ebx + eax*4 + 0x497328]  ; ★ 覆写「昨天」那一格历史
```

⇒ 新闻一次就把现价按 ±10% 跳一次，并**回写历史的前一格**（不新增历史点、不改开盘价）。

`0x429040` 的全部直接调用点（A，自扫）：`0x42b13f`（红/黑卡在股市屏上选股后当场跳价）、
`0x444f91` / `0x4450ff`（红卡 / 黑卡的效果函数）、`0x44b04b`（新闻 24 全面上涨）、
`0x44b096`（新闻 25 全面下跌）、`0x44b409`（新闻 30 / 32 / 33 / 34 共用的尾段）、
`0x44b6ce`（新闻 35）。
**新闻 27（个股停牌）不调用它** —— 它在 `0x44b17b` 直接把现价压回开盘价并回写历史。

### 2.6 物价指数 `0x4990e8`（复核 F-002）——**结论：既有结论正确**

**更新函数 `0x423acf`（34 条指令，唯一运行时写点 `0x423b1b`）**：

```asm
00423ad8  cmp   ebx, dword ptr [0x499114]     ; 遍历玩家
00423ae3  cmp   byte ptr [eax + 0x496b7d], 0  ; who_plays（player+0x15）
00423aed  call  0x4239b9                       ; 总资产
00423af5  add   esi, eax                       ; Σ 资产
00423af7  inc   edi                            ; 在场人数
00423b02  idiv  edi                            ; ① 人均（向零取整）
00423b09  mov   ecx, dword ptr [0x49908c]      ; ② 开局资金
00423b0f  idiv  ecx                            ; ③ 再除一次
00423b13  cmp   eax, dword ptr [0x4990e8]
00423b19  jle   0x423b20
00423b1b  mov   dword ptr [0x4990e8], eax      ; ★ 只升不降
```

**调用点（A，自扫）**：只有 `0x41cfbf`（日推进内），且在日期 +1、`0x41d89e() != 1`
门控**之后**、行情更新 `0x4291d6` **之前**。
另两处写点：`0x4073b4`（开局 = `1`）、`0x44889c`（读档还原）。

**公式**：`price_index = max(旧值, trunc(trunc(Σ在场资产 / 在场人数) / 开局资金))`。
`0x49908c` 取自表 `0x46cb94`（`300000/200000/100000/50000/30000/10000`，由 `[0x46cb40]` 选档）。
⇒ **既有 F-002 的公式、唯一写点、调用时机、「只升不降」全部复核通过，本规格不再另立结论。**
补充两点 A 级细节：① 两次除法都是 `idiv`（**向零取整**，非 floor）；
② 更新**不受休市影响**（`0x423acf` 里没有 `0x428d01` 判定），休市日指数照涨。

★★ **通道 2 已差分**（2026 本轮，`tests/test_price_index.py` 29/29，直接 `call 0x423acf`）：
覆盖「只升不降」闸门、出局者不计入分子/分母、两次 `idiv` 的截断、开局资金六档除数。
另外补上一条**此前没写进规格的真相**：

> **`wealth()` 内部的 float32 量化会穿透到物价指数。**
> `0x423aed` 调的总资产函数在股票段会把运行中的总资产反复压进 float32
> （见 §5.4），于是人均值也是被量化过的：
>
> | 玩家现金 | `f32(现金)` | 原版指数 | 纯精确模型 | 差 |
> |---|---|---|---|---|
> | `99,899,999` | `99,900,000` | **333** | 332 | **+1** |
> | `89,999,999` | `90,000,000` | **300** | 299 | **+1** |
> | `99,999,999` | `100,000,000` | 333 | 333 | 0 |
> | `16,777,217` | `16,777,216` | 55 | 55 | 0 |
>
> 差的那两档不是"只在理论边界"：物价指数是**所有**价格公式的乘子，
> 差 1 档会同时改变估价/地價稅/證交稅/挂牌市价。复刻侧因此**不能**用纯整数
> 累加来算 `wealthOf`（`rules/wealth.ts` 已按 §5.4 逐步 `Math.fround`）。
>
> ⚠️ 除零边界：`在场人数 == 0` 时原版在 `0x423b02 idiv edi` 上**直接除零异常**；
> 复刻加了 `count === 0` 护栏 —— **有意偏离**（正常对局不可达）。

---

## 三、涨跌停、休市、停牌

### 3.1 涨跌停状态 `fcn_004295ea`（54 条指令）

**签名**：`int stock_limit_status(int stock)` → `0..4`。

```asm
004295f3  mov   edx, [eax*4 + 0x496990]      ; open
00429603  mov   eax, [eax*4 + 0x496994]      ; cur
0042960e  fld   [esp + 4]                    ; cur
00429612  fcomp [esp + 8]                    ; vs open
00429619  jbe   0x42964f                     ; cur <= open
; ── cur > open ──
0042961b  push  0x41200000                   ; +10.0f
00429620  push  edx                          ; open
00429621  call  0x428ec5                     ; 涨停价 = apply(open, +10)
0042963e  jae   0x429646                     ; cur >= 涨停价
00429640  xor   eax, eax                     ; → 0（涨）
00429646  mov   eax, 1                       ; → 1（涨停）
; ── cur <= open ──
0042964f  jae   0x429688                     ; 复用上面 flag：cur >= open ⇒ cur == open
00429651  push  0xc1200000                   ; -10.0f
00429657  call  0x428ec5                     ; 跌停价 = apply(open, -10)
00429674  jbe   0x42967f                     ; cur <= 跌停价
00429676  mov   eax, 2                       ; → 2（跌）
0042967f  mov   eax, 3                       ; → 3（跌停）
00429688  mov   eax, 4                       ; → 4（平）
```

| 返回 | 含义 | 判定 |
|---|---|---|
| 0 | 涨 | `open < cur < 涨停价` |
| 1 | **涨停** | `cur >= 涨停价`（**含等号**） |
| 2 | 跌 | `跌停价 < cur < open` |
| 3 | **跌停** | `cur <= 跌停价`（**含等号**） |
| 4 | 平 | `cur == open` |

`涨停价 = apply_price_change(open, +10.0f)`、`跌停价 = apply_price_change(open, -10.0f)`：
**涨停/跌停价本身也经过 §2.2 的 `fmod` 量化与 `[1.0, 9999.0]` 夹取**，
所以门槛值不是单纯的 `open × 1.1`（例：`open = 3.0` → `3.3`，再按 `step = 0.01` 向 3.0 取整）。
**恰好等于涨停/跌停价时算涨停/跌停**（`>=` / `<=`）。

### 3.2 休市日 `fcn_00428d01`

```asm
00428d01  push  ebx
00428d02  xor   ebx, ebx
00428d04  cmp   dword ptr [0x4990dc], 0     ; 全股市暂停交易倒数
00428d0b  jne   0x428d21                     ;   != 0 → 休市
00428d0d  mov   ecx, dword ptr [0x497160]    ; 当日日期
00428d14  call  0x4523d5                     ; 节日/星期判定
00428d1c  cmp   eax, 1
00428d1f  jne   0x428d26
00428d21  mov   ebx, 1                       ; ★ 返回 1 = 休市
```

即：**休市 = `[0x4990dc] != 0` 或 `is_holiday(今日) == 1`**。

`is_holiday` = `fcn_004523d5`（39 条指令）：

```asm
004523dc  push  ebx                          ; arg3 = NULL（不取「当月天数」）
004523dd  lea   eax, [esp + 4]
004523e1  push  eax                          ; arg2 = &wday
004523e2  mov   edx, [esp + 0x18]
004523e7  push  edx                          ; arg1 = 日期
004523e7  call  0x4520a6                     ; 算 wday 与当月天数
004523ef  cmp   dword ptr [esp], 0
004523f3  je    0x452437                     ; ★ wday == 0（星期日）→ 休
004523f9  push  esi
004523fa  call  0x4521f0                     ; 查该图 24 条节日项
00452404  cmp   eax, -1
00452407  je    0x45243c                     ;   无匹配 → 不休
00452409  movsx ecx, word ptr [0x4991b6]     ; stage
00452413  movsx eax, word ptr [0x4991b8]     ; map
0045241a  add   ecx, eax                     ; gid = stage*4 + map
00452426  mov   eax, edx                     ; edx = 由 0x4521f0 返回的项号
00452428  shl   eax, 2
0045242b  sub   eax, edx                     ; *3
0045242d  cmp   byte ptr [ecx + eax*4 + 0x47ff4a], 0   ; 该图节日表[项号].+0
00452435  je    0x45243c                     ;   0 → 不休
00452437  mov   ebx, 1
```

节日起始表在 `0x47ff4a`，**每张图 288 字节 × 8 图**，每项 **12 字节 × 24 项**；
项头字节：`0x80` 位 = 该册项**停用**（`0x4521f0` 里 `test byte […],0x80 / jne 下一条`），
其余非 0 = 该日是假日。`0x4520a6` 里 `wday = (0x451f8c(date) + 4) % 7`（`idiv 7`）。

> **复核既有结论（Q-STOCK-1）**：「`0x4520a6` 算星期 → 星期日休」「`0x4521f0` 查
> `0x47ff4a` 节日表」两条**都成立**，但顺序要写对：**先判星期日（wday==0 直接返回 1），
> 再去查节日表**。既有文字把两步写成并列，容易被误读为「两个条件都要成立」。

**全股市暂停**（新闻 26，`0x44b0a0`）：

```asm
0044b0c6  mov   dword ptr [0x4990dc], 0xa   ; ★ 立即数 10，文案说「１０天」
```

递减在日推进（`0x41cfc9`）用「减到 0 先置 `0x80`、下一次才清 0」的两段式：

```asm
0041cfc9  test  byte ptr [0x4990dc], 0x80
0041cfd4  mov   dword ptr [0x4990dc], eax    ; 已置 0x80 → 清 0
0041cfe5  lea   ebx, [ecx - 1]
0041cfe8  mov   dword ptr [0x4990dc], ebx
0041cff0  jne   0x41cff9
0041cff2  or    byte ptr [0x4990dc], 0x80    ; ★ 到 0 再加一天
```

⇒ **实际关门 11 天**（10 + 1 个释放日）。与既有结论一致。

**休市日的表现层**（复核 Q-STOCK-5，A）：

```asm
; 股市屏入口 0x42b58f
0042b6b4  call  0x428d01
0042b6b9  cmp   eax, 1
0042b6bc  jne   0x42b745                     ; ★ 开市才画股票名/页头/进真窗口过程
0042b6d6  push  2 / 0xf4 / 0x144 / 0x4640e8  ; "本日休市" 黑字 (324,244)
0042b6f8  push  1 / 2 / 0 / 0xf0f0f0 / 0x48
0042b70d  push  2 / 0xf0 / 0x140 / 0x4640e8  ; "本日休市" 白字 (320,240)
0042b731  push  0x42b2ec                     ; ★ 訊息框窗口过程
```

⇒ 休市那一屏**没有表头、没有股票名、没有行情数字、点哪儿都退屏**，
**根本点不到买卖** —— 与既有结论一致。

### 3.3 停牌（个股）

- 字段：`stock+0x06`（`uint8`，倒数天数）。写得两处：
  - 新闻 27（`0x44b0d1`）：随机一支 `+6 = 0xf`（**15 天**，文案说「１０天」），
    并把现价压回开盘价、回写历史。
  - 新闻 28（`0x44b1a3`）：在所有 `+6 != 0` 的股票里随机一支，`+6 = 0`。
- 递减：日推进 `0x41d017`，**简单 `dec`，没有 0x80 两段式** ⇒ 15 天就是 15 天。
- 行情影响：停牌支把 `momentum` 清零、价格冻结在开盘价，但**仍写历史**。
- 买卖影响：柜台买入 `0x42aef4`、卖出 `0x42b02f`，**静默拒绝（无提示）**：

```asm
0042aef2  add   eax, edx
0042aef4  cmp   byte ptr [eax*4 + 0x496986], 0   ; ★ 查的是 +0x06
0042aefc  jne   0x42b0d3                         ; 直接返回，无任何提示
```

**复核 Q-STOCK-3**：偏移确为 **`+0x06`**（不是 `+0x02`）；既有的订正正确。

**行情表「交易量」列的显示**（`0x429a36`）：`+6 != 0` 时该格改画字符串
`0x46400f`「暫停交易」（而非数字）。

---

## 四、买卖规则

### 4.1 两个入口函数的**精确签名**（A，容易搞反，务必照抄）

**买入 `fcn_00428d2a`**（71 条指令）：

```
int buy_stock(int player /*[esp+0x1c]*/, int stock /*[esp+0x20]*/,
              int amount /*[esp+0x24]*/, int flag /*[esp+0x28]*/);

flag == 0  → 「認購」：单价 = 企業+0x24 / 10000（idiv，有符号）
             扣玩家 cash(+0x1c)；企業+0x30 -= amount
flag != 0  → 「市場買進」：单价 = stock+0x14（現價，單精度）
             扣玩家 money_in_bank(+0x20)；stock+0x0a -= amount、stock+0x08 -= amount
两种情况最后都走同一段「加權平均成本」更新，然后 call 0x4294d5(player, stock)
```

```asm
00428d47  cmp   dword ptr [esp + 0x28], 0
00428d4c  je    0x428d7f                          ; flag==0 → 認購
; ── flag != 0：市場買進 ──
00428d52  fild  dword ptr [esp + 8]               ; amount
00428d56  fmul  dword ptr [eax + 0x496994]        ; ★ × 現價（單精度 dword）
00428d5c  call  0x457dbc                          ; __round_toward_zero
00428d61  fistp dword ptr [esp + 4]               ; cost
00428d65  sub   word ptr [eax + 0x49698a], si     ; +0x0a -= amount
00428d6c  sub   word ptr [eax + 0x496988], si     ; +0x08 -= amount
00428d77  sub   dword ptr [ebx + 0x496b88], eax   ; ★ 存款 -= cost
; ── flag == 0：認購 ──
00428d7f  mov   ax, word ptr [eax + 0x496984]     ; 1 基企业序号
00428d8b  imul  eax, eax, 0x34
00428d8e  mov   ecx, dword ptr [0x498e7c]
00428d94  add   ecx, eax
00428d96  mov   edi, 0x2710                       ; 10000
00428d9b  mov   eax, dword ptr [ecx + 0x24]       ; ★ 企業資產額
00428da3  idiv  edi                               ; 每股净值 = 資產額 / 10000
00428da7  imul  edx, eax                          ; cost = amount * 单价
00428dae  sub   dword ptr [ecx + 0x30], esi       ; ★ 企業+0x30（保留股份）-= amount
00428db1  sub   dword ptr [ebx + 0x496b84], edx   ; ★ 現金 -= cost
```

**卖出 `fcn_00428e23`**（47 条指令）：

```
int sell_stock(int player /*[esp+0x14]*/, int stock /*[esp+0x18]*/,
               int amount /*[esp+0x1c]*/, int flag /*[esp+0x20]*/);

amount 从持仓扣；若扣完为 0 → 成本均价同时清 0
单价 = stock+0x14（現價，單精度）；proceeds = trunc(amount × 現價)
flag != 0 → player.money_in_bank += proceeds
flag == 0 → [0x499080] += proceeds        ★ 钱直接凭空消失（见 §4.4）
stock+0x0a += amount、stock+0x08 += amount
最后 call 0x4294d5(player, stock)
```

```asm
00428e45  mov   edx, dword ptr [eax + 0x4971a0]
00428e4b  sub   edx, ecx
00428e4d  mov   dword ptr [eax + 0x4971a0], edx
00428e53  jne   0x428e5b
00428e55  mov   dword ptr [eax + 0x4971a4], edx   ; ★ 清仓时均价同时清零（edx==0）
00428e6a  fild  dword ptr [esp + 4]
00428e6e  fmul  dword ptr [eax*4 + 0x496994]      ; ★ × 現價（單精度）
00428e75  call  0x457dbc
00428e7a  fistp dword ptr [esp]                   ; proceeds
00428e7d  add   word ptr [eax*4 + 0x49698a], cx   ; +0x0a += amount
00428e85  add   word ptr [eax*4 + 0x496988], cx   ; +0x08 += amount
00428e8d  cmp   dword ptr [esp + 0x20], 0
00428e92  je    0x428ea4
00428e9c  add   dword ptr [edx + 0x496b88], eax   ; 存款 += proceeds
00428ea4  mov   eax, dword ptr [esp]
00428ea7  add   dword ptr [0x499080], eax         ; ★ flag==0 → 进「消失池」
00428eb7  call  0x4294d5                          ; ★ 卖出也重排企业归属
```

**调用点与 flag 取值（A，自扫全部直接调用）**：

| 函数 | 调用点 | flag | 场景 |
|---|---|---|---|
| `buy_stock` | `0x42afc6` | `1` | 柜台买进（扣**存款**，受 `+0x0a` 上限约束） |
| `buy_stock` | `0x42c72d` | `1` | AI 买进（`0x42c721 push 1`） |
| `buy_stock` | `0x41d281` | `0` | 走到**上市企业格**时的「認購」（扣**现金**，扣 `企業+0x30`） |
| `sell_stock` | `0x42b0ad` | `1` | 柜台卖出（进**存款**） |
| `sell_stock` | `0x42d033` | `1` | AI 卖出（`0x42d02e push 1`） |
| `sell_stock` | `0x44c9ec` | `1` | 命运事件（`fortune_call_table[8]` 分支） |
| `sell_stock` | `0x44c8fd` | `0` | 命运事件（钱消失） |
| `sell_stock` | `0x40d17b` | `0` | **破产清算**（`0x40cd87` 内；钱消失） |

> ⚠️ **同一个 `flag` 在买/卖里含义不同**：买 `flag==0` = 認購（走企业资产额定价、扣现金），
> 卖 `flag==0` = 收益进「消失池」。**不要合并成一条语义**。

★★ **通道 2 已差分**（2026 本轮，`tests/test_sell_stock.py` 24/24）：
直接 `call 0x00428e23`（`_rich4_sell_stock`，四参：`player, stock, amount, toPlayer`），
外加 `0x00428d2a`（买）反向确认同一对计数器。验到的四条**容易做错的**：

| 行为 | 原版真值 |
|---|---|
| `toPlayer != 0` → 进玩家**存款**；`== 0` → 进 `0x499080`（破产清算/命运事件走这条） | 落点只由第 4 参定 |
| ★ **成本均价只在持股变成「恰好 0」时清**（`holdings != 0` 就跳过） | 持 1000 卖 999 → 成本留着；卖 1000 → 清 0 |
| ★ **超卖不夹**：持股会变**负数**，成本**不清**，进账仍按请求量算 | 持 1000 卖 1500 → 持股 −500、成本 15、进账 1500×价 |
| ★ 成交量两格（`+8`/`+0a`）是 **u16**，`add/sub word` ⇒ **回绕** | 卖：`f10=65530` +300 → **294**；买：`10` −300 → **65246** |
| ★ 进账按**完整 amount**、计数器只吃 **`cx`（低 16 位）** | `amount=65541` → 进账 65541，计数器只 +5 |

### 4.2 手续费 / 税 —— **没有**（A）

**结论**：股市买卖**没有手续费、没有证券交易税、没有任何费率扣除**。
- 买：`cost = trunc(amount × 現價)`，只做一次乘法，随后一次 `sub`；
- 卖：`proceeds = trunc(amount × 現價)`，只做一次乘法，随后一次 `add`；
- 全 exe 字符串表里**没有**「手續費 / 證券交易稅 / 交易稅」这类字面量
  （`grep 稅` 只命中「所得稅５％」「查稅卡」等**与股市无关**的新闻/卡片文本）。

> **未决**：`0x499080`（卖 `flag==0` 的去向，也是 `0x41d2c6` 里 `to == -1` 的去向）
> 全 exe **无任何逻辑读取**，只在开局/读档被清零。
> 从 `0x41d2c6` 的语义看它是「**money sink 累计器**」（钱离开游戏），
> 但**没有证据**表明它被用于任何判定或显示 ⇒ 命名按「消失池」记录，用途**未决**。

### 4.3 成交量限制（上限来自哪里）

| 操作 | 上限 | @source |
|---|---|---|
| 柜台**买** | `n = min((uint16)stock+0x0a, trunc(player.money_in_bank / stock+0x14))` | `0x42af43` / `0x42af66` |
| 柜台**卖** | `n = player_stocks[player][stock].amount` | `0x42b076`（读 `+0x4971a0`） |
| **認購** | `n = min(1000, 企業+0x30, trunc((player.cash − trunc(0x49908c×0.3)×price_index) / 单价))` | `0x41d20a`（封顶 `0x3e8`）、`0x41d216`、`0x41d839` |
| AI 买 | `n = min(想买量, (uint16)stock+0x0a)` | `0x42c70a..0x42c71a` |
| AI 卖 | `n = 持仓量` | `0x42d025` |

```asm
; 柜台买上限  0x42af43
0042af43  mov   cx, word ptr [eax*4 + 0x49698a]   ; ★ +0x0a
0042af66  fild  dword ptr [eax + 0x496b88]        ; 存款
0042af6c  fdiv  dword ptr [edx + 0x496994]        ; / 現價（單精度）
0042af72  call  0x457dbc
0042af77  fistp dword ptr [esp + 0x50]
0042af7f  cmp   ecx, edi
0042af83  mov   eax, ecx                          ; min
0042af87  mov   eax, edi
0042af89  test  eax, eax
0042af8b  je    0x42b0d3                          ; 0 → 不弹输入框
0042af91  push  eax
0042af92  call  0x453544                          ; 数量输入框（上限 = n）
```

⇒ **「成交量限制」= `stock+0x0a` 这一支 u16**；它随买卖增减
（买 `-= amount`、卖 `+= amount`），是**滚动的可买余量**，不是每日重置的成交量。
行情表把它显示在标题为「交易量」（字符串 `0x4640cf`）的那一列 —— 原版的标签与用法
**不一致**（B 级观察），复刻时按**用法**实现、按**原标签**显示。

> **未决**：`+0x08`（`企業+0x30 = 10000 − +0x08` 的那一支）与 `+0x0a` 是两个都随买卖
> 增减的 u16，二者**是否在数值上恒等**未能确证（初值都等于静态表的 `+0x08`，
> 由 `0x42915a` 把 `+0x0a` 写成 `+0x08` 或 `trunc(+0x08 × (1000+rand%2000) / 10000)` —— 见下）。
> 8 张图里 `+0x08 ≤ 1000` 的股票（本作实测为 0 支）才会让两者恒等；
> `+0x08 > 1000` 时 `+0x0a` 初值**小于** `+0x08`，之后两者同步增减，差值恒定。

```asm
; 0x42915a 开局初始化「可买余量」+0x0a
0042917a  mov   dx, word ptr [ebx + 0x496988]     ; +0x08
00429181  cmp   dx, 0x3e8                          ; 1000
00429186  jbe   0x429163                           ; <= 1000 → +0x0a = +0x08
00429188  call  0x456f2d                           ; rand()
00429197  idiv  ecx                                ; % 2000
00429199  add   edx, 0x3e8                         ; r = 1000 + rand()%2000
004291b4  fdiv  dword ptr [0x463fc0]               ; r / 10000.0f（單精度）
004291ba  fmulp st(1)                              ; × (float)+0x08
004291c1  fistp dword ptr [esp]
004291c7  mov   word ptr [ebx + 0x49698a], ax     ; ★ +0x0a = trunc(+0x08 × r / 10000)
```

### 4.4 停牌 / 涨跌停的判定点（柜台）

| 判定 | 地址 | 行为 |
|---|---|---|
| 买入：停牌 | `0x42aef4` `cmp byte [stocks+6], 0 / jne 0x42b0d3` | **静默拒绝** |
| 买入：涨停 | `0x42af0b call 0x4295ea` → `0x42af13 cmp eax,1 / jne 0x42af30` | 提示 `0x464088` = `"漲停無法買進！"`（`0x464087` 是 `"@漲停無法買進！"`，`push 0x464088` 跳过 `@`） |
| 卖出：停牌 | `0x42b02f` `cmp byte [stocks+6], 0 / jne 0x42b0d3` | **静默拒绝** |
| 卖出：跌停 | `0x42b03e call 0x4295ea` → `0x42b046 cmp eax,3 / jne 0x42b05a` | 提示 `0x464097` = `"跌停無法賣出！"` |
| 卖出：无持仓 | `0x42b019` `cmp dword [eax+ebx*8+0x497198], 0 / je 0x42b0d3`（`0x497198` = `0x4971a0−8`，配 1 基行号） | 静默返回 |

**买入前置**还有一道「自己已经持有 `>= 5000`」的判定
（`0x4971a0` 与 `0x1388` 比较）—— 出现在 **AI 打分**里（`0x42c1c8`），
柜台路径没有这道闸。

---

## 五、持仓与成本均价

### 5.1 `player_stock_info` 的**精确布局**（★ 订正 `rich4_stocks.h`）

```c
// 基址 0x4971a0，玩家步长 0x60，股票步长 8
typedef struct {          // 共 8 字节
    int   amount;         // +0x00  持股数（整数）
    float avg_cost;       // +0x04  ★ 持仓成本均价（单精度 float，不是 int！）
} player_stock_info;      // player_stocks[4][12]
```

**证据（A）**：汇编以 `fild`/`fmul dword`/`fdivrp`/`fstp dword` 按**浮点**读写 `+0x04`：

```asm
; 买入 0x428dce
00428dce  fild  dword ptr [edx + 0x4971a0]        ; amount → float
00428dd4  fmul  dword ptr [edx + 0x4971a4]        ; ★ 与 float 均价相乘
00428df4  fild  dword ptr [edx + 0x4971a0]        ; 新 amount
00428dfe  fild  dword ptr [esp + 8]               ; 新的总成本
00428e02  fdivrp st(1)                            ; ★ 浮点除法
00428e04  fstp  dword ptr [edx + 0x4971a4]        ; ★ 以「单精度」落回均价
```

`rich4-re/asm/rich4_stocks.h` 写成 `typedef struct { int amount; int _; }` —— **`_` 是错的**，
按 `int` 读会在第一笔买入后立刻得到垃圾值。凡引用该头文件的实现都必须改。

**元素下标算式（A）**：`offset = player*0x60 + stock*8`
（`0x428dbd`：`eax = player*3; shl 5 → *96`；`0x428dc9`：`edx = stock*8`）。
`player_stocks` 总长 384 = 4 人 × 12 支 × 8（新局 `memset(0x4971a0, 0, 0x180)` @ `0x407492`）。

### 5.2 买入如何更新均价 —— **加权平均，先算旧成本再算新均价**

```
old_amount  = player_stocks[p][s].amount
old_cost    = trunc( (float)old_amount × avg_cost )       ; ★ 单精度乘 + 向零取整
new_amount  = old_amount + bought
total_cost  = old_cost + cost_of_this_purchase            ; cost 见 §4.1（亦为 trunc）
avg_cost    = (float)total_cost / (float)new_amount       ; ★ 单精度除法
```

```asm
00428dce  fild  dword ptr [edx + 0x4971a0]
00428dd4  fmul  dword ptr [edx + 0x4971a4]
00428dda  call  0x457dbc                      ; __round_toward_zero
00428ddf  fistp dword ptr [esp]
00428de2  add   dword ptr [edx + 0x4971a0], esi      ; amount += bought
00428def  add   ebx, eax                              ; total = old_cost + cost
00428df4  fild  dword ptr [edx + 0x4971a0]            ; new amount
00428dfe  fild  dword ptr [esp + 8]                   ; total
00428e02  fdivrp st(1)                                ; ★ total / amount（反向除法）
00428e04  fstp  dword ptr [edx + 0x4971a4]            ; avg_cost = 单精度
```

**精度要点（A）**：
- 两次乘法（`old_amount × avg`、`amount × price`）都是 `fild`（int→x87）+ `fmul dword`（单精度内存操作数），
  再 `call 0x457dbc`（`__round_toward_zero`）后 `fistp dword` → **整数成本，向零取整**。
- 均价除法 `fdivrp` 在 x87 内做，落回 `fstp dword` ⇒ **均价为单精度 float**。
- ⇒ 复刻必须用 `float` 存均价、用「`trunc` 到整数再除」而不是 `double` 累加，
  否则几百笔交易后会与原件分叉。

### 5.3 卖出如何计算盈亏

**结论（A）**：**原版不计算已实现盈亏，也不做任何盈亏统计**。
卖出只做三件事：

1. `amount -= sold`；若结果恰为 `0`，把 **`avg_cost` 一并清 0**（`0x428e53`/`0x428e55`）；
2. `proceeds = trunc(sold × 現價)`（单精度），进存款（`flag=1`）或消失池（`flag=0`）；
3. `+0x0a` / `+0x08` 各 `+= sold`，然后重排企业归属。

**没有**用到成本均价的减法 ⇒ 「盈亏」在原版里**只是 UI 上的一列 `平均成本`**
（字符串 `0x4640df`，行情表画 `stock+0x04` 的 float，`sprintf("%.2f")` @`0x463f64`，`x=0x261`）。
若复刻要显示「已实现盈亏」，那是**本项目自创**，必须标为偏离。

> **未决**：除买卖之外，`player_stocks[·][·].amount/avg_cost` 还有**其它写入者**
> （`gen/xrefs.json` 的 `written_by` 列出 17 个函数地址，其中
> `0x42565c`（股数转移 + 重算均价）、`0x41646c`、`0x42017c`、`0x42c79f`、`0x44a029`、
> `0x44bb4b`、`0x44c7ef` 等）。本规格**只逐行验证了买卖两条主路径**与
> `0x42565c` 的均价重算形态；其余（卡片 / 命运 / 新闻 / 破产清算的强制转移）
> **未逐一取证**，标为**未决**。
> `gen/xrefs.json` 的 `written_by` 对 `0x4971a0` 明显偏保守（把 `0x4297f7`、`0x42ba97`
> 这类**只读**函数也标进来了），**不能当权威清单用**，需按行复核。

### 5.4 玩家总资产 `_rich4_calculate_player_wealth` @ `0x4239b9`

```
total = cash(+0x1c) + money_in_bank(+0x20) − loan(+0x24)
for i in 0..11:
    total = trunc( (float)total + (float)player_stocks[p][i].amount × stock[i].price )   ; 单精度累加
for land in 1..num_lands   (步长 0x34，表 0x498e84):
    if (land.owner == player+1):
        total += land.land_price(0x1c)                      ; u16
        if (land.type(0x18) != 0) total += land.house_price(0x1e)
        elif (land.level(0x1a) != 0) total += land.level × land.house_price
for fac in 1..num_facilities (步长 0x38，表 0x498e88):
    if (fac.owner == player+1):
        total += fac.level(0x1a) × fac.0x24 + fac.0x22      ; u16×u16 + u16
```

```asm
004239ec  fild  dword ptr [ecx + eax*8 + 0x4971a0]   ; 持股
004239f8  fmul  dword ptr [eax*4 + 0x496994]         ; ★ × 現價（單精度）
00423a0a  fstp  dword ptr [esp + 4]                  ; ★ 累加前把整数总资产降成单精度
00423a12  call  0x457dbc
00423a17  fistp dword ptr [esp]
```

★ **「单精度累加」的量化后果（2026 本轮用原版真码测出）**：分界点正是 **2^24**。
持股 1000 股 × `10.35`（float32 值 `10.350000381469727`）：

| 起始总资产 | 原版 | 纯双精度 | 差 |
|---|---|---|---|
| `2^24` = 16777216 | 16787566 | 16787566 | 0 |
| `2^24+1` | 16787566 | 16787567 | −1 |
| `10^8` | 100010352 | 100010350 | +2 |
| `123456789` | 123467144 | 123467139 | +5 |
| `999999999` | **1000010368** | 1000010349 | **+19** |

★★ **循环是 `for edx = 0..11` 一轮不落**（`0x423a1a inc edx` / `cmp edx,0xc` / `jl`），
**空仓不跳过** —— 空仓那一轮的实际作用就是「把总资产再压一次 float32」：

| 起始（持股全 0） | 原版 |
|---|---|
| `999999999` | 1000000000 |
| `2^24+1` | **16777216**（往下舍） |
| `123456789` | 123456792 |
| `1000` | 1000（小额不受影响） |

⇒ 复刻必须写成 `total = trunc(市值 + fround(total))`，且**不能**因"该槽无持股"就跳过迭代。
差分真值：`tests/test_inline_formulas.py` §10（驱 `0x4239e0`..`0x423a20`）。

**★ 结论：企业资产额（`企業+0x24`）不进入玩家总资产**，`保留股份`也不进。
玩家从上市企业拿到的只有：**股票市值**（持股×现价）与**分红**（§6.4）。
本项目**不应**新增「企业资产计入身家」这类机制。

**该函数被 8 处调用**（自扫）：`0x41633a, 0x41d8d6, 0x4233b4, 0x423aed, 0x431887, 0x43668f, 0x437e1b, 0x438f33`
（物价指数、结算画面、AI、银行等）。

### 5.5 持股市值（證交稅基数）的累加也是**单精度** @ `0x44a0c6`..`0x44a110`

事件表第 13 项（`0x44a029`）里的持股遍历循环，是**證交稅**的基数来源：

```asm
0044a0c6  eax = player*0x60 + stock*8   ; 寻址
0044a0dc  cmp dword [eax + 0x4971a0], 0 ; ★ 持股为 0 则 **跳过**（与 §5.4 的循环不同！）
0044a0e3  je  下一支
0044a0e5  fild dword [eax + 0x4971a0]      ; 持股（int32）
0044a0f9  fmul dword [stock*0x24 + 0x496994] ; × 現價（float32）
0044a100  fadd dword [esp + ebx*4 + 0x94]    ; 加进合计数
0044a107  fstp dword [esp + ebx*4 + 0x94]    ; ★ 每步都把合计数**存回 float32**
0044a0c1  cmp esi, 0xc / jge 结束            ; 12 支
```

⇒ **合计数全程活在 float32 里**（乘积本身在 x87 里是 53 位，与 JS 双精度一致；
只有"存回"这一步丢精度）。这**不是**"可能差最低位"——会差到税上：

| | |
|---|---|
| 持股（另 6 支空仓） | `[9572, 3546, 5541, 8967, 9430, 683]` |
| 现价 | `[141.931076, 78.522301, 284.512482, 57.756199, 238.642319, 113.872337]` |
| 原版合计（float32 累加） | **6059560** |
| 双精度合计 | 6059559.70671463 |
| `×0.05` 截断（證交稅，指数 1） | **原版 302978** ／ 双精度 **302977** |

⚠️ 两条循环**形状不同**，别写成一个：
§5.4 的总资产循环**空仓也跑**（于是空仓会额外压一次 float32），
本条（證交稅基数）**空仓跳过**。复刻分别是
`wealth.ts` 的 `trunc(amount*price + fround(total))`（12 轮全跑）与
`percentage.ts` `stockValue` 的 `sum = fround(sum + h*p)`。

差分真值：`tests/test_inline_formulas.py` §10（驱 `0x44a0c6`..`0x44a110`）。

---

## 六、上市企业

### 6.1 企业记录布局（步长 `0x34`，**1 基**，基址 `[0x498e7c]`）

| 偏移 | 类型 | 字段 | 含义 | 可靠性 |
|---|---|---|---|---|
| `0x04` | `char[19]` | `name` | 企业名（Big5） | A |
| `0x18` | `uint8` | `owner` | **经营者**：`0` = 无，否则 `player_index + 1` | A |
| `0x19` | `uint8` | `stock_index` | **本企业对应的股票行号（0 基）** | A |
| `0x1a` | `uint8` | `level` | 等级（决定消费金额；`0x439…` 用） | B |
| `0x1c` | `uint8[4]` | `rank` | **持股排名表**（`player_index+1`，按持股降序，`0` 为空位） | A |
| `0x24` | `uint32` | `assets` | **企业资产额**（**只读，来自地图文件**） | A |
| `0x28` | `int32` | `month_profit` | **本月盈餘**（每月 15 号派发后清零） | A |
| `0x2c` | `int32` | `total_profit` | **累積盈餘** | A |
| `0x30` | `int32` | `reserved` | **保留股份**（可由「認購」减少） | A（算术）/ B（命名） |

**股数守恒（A，由 §4.1 的三条加减推出）**：
`保留股份(0x30) + 流通股(股票+0x08) + Σ玩家持股 = 10000`，
在三种操作下都守恒：市场买进（`+0x08 -= n`，持股 `+= n`）、
市场卖出（`+0x08 += n`，持股 `-= n`）、認購（`+0x30 -= n`，持股 `+= n`）。

建图时 `保留股份` 的初值（`0x407ad2`，A）：

```asm
00407dc6  cmp   ebx, dword ptr [0x498e90]          ; 遍历 1..num_commercials
00407dda  mov   dl, byte ptr [esi + 0x19]          ; 企业对应的股票行号
00407de4  mov   ax, word ptr [eax*4 + 0x496988]    ; 股票 +0x08
00407dec  and   eax, 0xffff
00407df1  mov   edx, 0x2710
00407df6  sub   edx, eax
00407df8  mov   dword ptr [esi + 0x30], edx        ; ★ 保留股份 = 10000 − 股票+0x08
```

⇒ 8 张图实测：`+0x08 = 10000` 的公司（多数）**保留股份 = 0**，**不能認購**；
`+0x08 = 5000/6000/4000/3000` 者分别有 `5000/4000/6000/7000` 股可認購。
`0x41d1a9` 开头那道 `cmp dword [ebx+0x30], 0 / je 返回` 就是这个意思。

### 6.2 企业资产额 `+0x24`：**运行时零写入**（复核 Q-STOCK-2）

逐函数扫「引用了 `0x498e7c` 的函数」里所有 `[reg+0x24]` 的写形态，**全部是别的结构体**
（土地/设施的 flag 位）。`企業+0x24` 只有 **5 处读**：

| 读取点 | 用途 |
|---|---|
| `0x428d9b` | 認購单价 = `資產額 / 10000`（`idiv`） |
| `0x41d1ef` | 認購数量上限（`資產額 / 10000`） |
| `0x4292a9` | 均值回归锚点（`fild` + `fdiv 10000.0f`） |
| `0x42c084` | AI 打分 |
| `0x42c853` | AI 打分 |

⇒ 与既有结论一致：**「买下企业后资产额会变、股价随之被拉动」在原版不成立**；
`+0x24` 是**地图文件里的静态字段**，本引擎**不应**新增动态资产额。

### 6.3 控股判定 / 持股排名 `_rich4_update_commercial_owner` @ `0x4294d5`

**签名（A）**：`int update_commercial_owner(int stock /*[esp+0x1c]*/, int player /*[esp+0x18]*/)`
—— **注意参数顺序：股票在前、玩家在后**。

★★ **全部调用点（自扫，3 处）—— "凡是持股变了就要重排"**：

| VA | 归属 | 实参 | 说明 |
|---|---|---|---|
| `0x428e14` | `_rich4_buy_stock` 尾部 | `(stock, 买家)` | 市場買進**与**認購都汇到这里 ⇒ 两条都重排 |
| `0x428eb7` | `_rich4_sell_stock` 尾部 | `(stock, 卖家)` | 柜台卖出 / AI 卖出 / **命運卖股** / **破产清算** 全走这支 |
| `0x42571e` | ★ **公佈欄买股票**（`0x0042565c`） | `push [槽+0x4967e2]`(股票号) + `push [0x49910c]`(买家) | **先前漏了这条路径**：挂牌股票易主会改变"谁持股最多"，老闆要跟着换 |

⇒ 复刻里凡是改 `holdings` 的地方都**必须**跟一次重排（`reownCommercial`）。
⚠️ 顺序要求：重排要读**改完之后**的持股（破产清算那段尤其要注意先写 `holdings` 再重排）。

```asm
004294e0  mov   edx, dword ptr [esp + 0x1c]        ; = stock
004294ee  mov   dx, word ptr [eax + 0x496984]      ; 1 基企业序号
004294f5  test  dx, dx
004294f8  jne   0x429501
004294fa  xor   edx, edx                            ; 无上市公司 → 返回 0
; ① 先把本玩家从排名表里摘掉
00429523  mov   dl, byte ptr [eax + 0x1c]          ; rank[ecx]
00429526  mov   esi, dword ptr [esp + 0x18]        ; player
0042952a  inc   esi
0042952e  cmp   edx, esi
00429532  mov   edx, 3
00429537  sub   edx, ecx
00429543  call  0x456de8                            ; memcpy(&rank[ecx], &rank[ecx+1], 3−ecx)
0042954b  mov   byte ptr [ebx + 0x1f], 0            ; rank[3] = 0
; ② 持股为 0 → 直接跳到「更新 owner」
00429561  mov   edi, dword ptr [eax + edi*8 + 0x4971a0]   ; 我的持股
0042956a  je    0x4295c0
; ③ 从第 2 名往下插，按持股降序
0042956c  mov   ecx, 2
004295a9  cmp   edx, edi                            ; 对手持股 vs 我的
004295ab  jl    0x429579                            ; 对手更少 → rank[ecx+1] = rank[ecx]（后移）
004295ad  inc   ecx                                 ; 否则停在此位
004295bc  mov   byte ptr [ebx + eax + 0x1c], dl      ; rank[pos] = player+1
; ④ owner = rank[0]，变了才通报
004295c0  mov   al, byte ptr [ebx + 0x18]
004295c3  mov   dh, byte ptr [ebx + 0x1c]
004295c6  cmp   al, dh
004295ca  mov   byte ptr [ebx + 0x18], dh            ; ★ owner = rank[0]
004295cf  call  0x40a4e1                             ; 界面刷新
004295d7  mov   dword ptr [esp], 1
```

**规则（A）**：
1. 排名表 `+0x1c..+0x1f` 恒按持股降序维护，存 `player_index+1`，空位为 `0`；
2. 每次调用先把**本玩家**从表里摘掉（`memcpy` 前移 + `rank[3] = 0`）；
3. 我的持股 `> 0` 时按降序插回；`== 0` 时不插回（等于退出排名）；
4. **`owner = rank[0]`**；只有 `owner` 真的变了才返回 `1` 并刷新界面。

**触发点（A，自扫）**：`0x428e14`（买入尾部，两条分支共用）、`0x428eb7`（卖出尾部，共用）、
`0x42571e`（`0x42565c` 股数转移）。
⇒ **买入与卖出都会重排**。既有 `Q-COM-1` 的「卖出不触发」是**错的**
（该条已在 `Q-STOCK-2` 里被订正，但 `Q-COM-1` 原文仍在），本规格以 exe 为准。

> **未决**：`0x4294d5` 找到匹配后**不 break**（摘除循环），
> 若同一玩家在表里出现两次只会摘掉第一处 ⇒ 表可能被写坏。
> 正常路径下不可能出现重复，故**未确证是否有可达路径**。

### 6.4 分红结算「上市公司分紅」`fcn_0042ba97`（308 条指令）

**触发（A）**：日推进 `fcn_0041cf67` 内，日期推进之后：

```asm
0041d07b  call  0x452444                  ; 先推进日期
0041d080  mov   eax, dword ptr [0x497160]
0041d085  and   eax, 0xff
0041d08a  cmp   eax, 0xf                  ; ★ 每月「15 號」
0041d08d  jne   0x41d099
0041d08f  call  0x42ba97                  ; ★ 上市公司分紅
0041d094  call  0x431712
```

**流程（A）**：对 `i = 0..11` 逐支股票：

```
if (stock[i].+0x04 == 0) 跳过（未上市不参与）
com = 企业表[stock[i].+0x04]
total = Σ over p in 0..num_players−1 where player[p].+0x15 != 0 : player_stocks[p][i].amount
for p: ratio[p] = (amount == 0) ? 0.0f : (float)amount / (float)total      ; 单精度除法
for p: dividend[p] = trunc( (float)com.+0x28 × ratio[p] )                  ; 单精度，向零取整
       屏幕画 dividend[p]
画 com.+0x28（企业总额）
if (total != 0) com.+0x28 = 0                                             ; ★ 本月盈餘清零
```

收尾：把 `dividend[p]` 逐个加进 `player.money_in_bank(+0x20)`，并处理负数连锁破产：

```asm
0042be8a  mov   edi, dword ptr [eax + 0x496b88]   ; 存款
0042be90  add   edi, esi                            ; += 红利
0042be92  mov   dword ptr [eax + 0x496b88], edi
0042be9a  jge   0x42bec2
0042be9c  add   dword ptr [eax + 0x496b84], edi     ; 存款为负 → 从现金抵
0042bea4  mov   dword ptr [eax + 0x496b88], ecx     ; 存款 = 0
0042beaa  cmp   dword ptr [eax + 0x496b84], 0       ; 现金也负?
0042beb3  mov   dword ptr [eax + 0x496b84], ecx     ; 现金 = 0
0042beba  call  0x40cd87                            ; ★ 破产处理
```

```asm
; 单一玩家的红利 = trunc(本月盈餘 × 自己持股 / 全体在场玩家总持股)
0042bc90  fild  dword ptr [eax + 0x28]              ; 企業+0x28（本月盈餘）
0042bc93  fmul  dword ptr [esp + ebx*4 + 0x80]      ; × ratio（單精度）
0042bc9a  call  0x457dbc
0042bc9f  fistp dword ptr [esp + 0xa0]
```

**规则要点（A）**：
- **分红只发给在场玩家**（`player+0x15 != 0`），分母也是同一集合；
- **保留股份不参与分配**；非股东分不到（金额 0）；
- 若**全体玩家持股和为 0** ⇒ 分母 0、`total == 0` ⇒ **企业本月盈餘不清零**（继续累积）；
- 分红进的是**存款**（`+0x20`），不是现金；
- 每月只发一次（15 号），且**本月盈餘派完即清零**，`累積盈餘(+0x2c)` **不动**。

**「平均盈餘」的除数 `[0x499084]`（A，订正既有说法）**：日推进里

```asm
0041cfa1  call  0x452117                  ; 日期 +1 天；返回「是否跨月」
0041cfa9  mov   edi, eax
0041d099  cmp   edi, 1
0041d09c  jne   0x41d0ff
0041d0f9  add   dword ptr [0x499084], edi  ; ★ 跨月才 +1
```

`0x452117` 只在「日 > 当月天数」时把 `ebp = 1` 返回（`0x45216f`），
其余情况返回 0 ⇒ **`[0x499084]` 是「经过的月数」，不是总天数**。
详情卡 `0x429d65` 用它做除数算「平均盈餘 = `企業+0x2c ÷ [0x499084]`」，
语义应为「**平均月盈餘**」。既有 `Q-STOCK-6` 的「總天數」是错的。

### 6.5 企业盈餘（`+0x28/+0x2c`）的所有来源（A）

| 来源 | 地址 | 变化 |
|---|---|---|
| 玩家在企业格消费 | `0x42e931` 尾 | `+0x28 += 金额`、`+0x2c += 金额`（节点号 ∈ `(6000, 8000)`，企业序号 = 节点号 − 6000） |
| 通用转账助手（企业为收款方/付款方） | `0x41d2c6` | `to > 0x64`：`+0x28/+0x2c += 额`；`from > 0x64`：`−= 额` |
| 新闻 30「工廠排放污水 罰款10000元」 | `0x44b374` | 两者 `−10000`，股票 `+7 = 3`（连跌 3 天），立即跳价 |
| 新闻 31「海外投資 獲利20000元」 | `0x44b419` | 两者 `+20000`，股票 `+7 = 0x30`（连涨 3 天） |
| 新闻 32「海外投資 虧損20000元」 | `0x44b4a8` | 两者 `−20000`，`+7 = 4`（连跌 4 天） |
| 新闻 33「違規開發山坡地 罰款10000元」 | `0x44b53f`（跳到 `0x44b3ad`） | 两者 `−10000`，`+7 = 3` |
| 新闻 34「製造噪音公害 罰款5000元」 | `0x44b57d` | 两者 `−5000`，`+7 = 3` |
| 新闻 35「獲利調高一倍」 | `0x44b5f5` | 只挑 `+0x28 > 10000` 的企业，`+0x28 = 2×旧`，`+0x2c += 2×旧`，`+7 = (旧/10000)<<4` |
| 分红派发 | `0x42ba97` | `+0x28 = 0`（`+0x2c` 不动） |

```asm
; 0x42e931 尾部（玩家在企业格消费 → 企业盈餘）
0042ed57  cmp   ebx, 0x1770                 ; 6000
0042ed5d  jle   0x42ed82
0042ed5f  cmp   ebx, 0x1f40                 ; 8000
0042ed65  jge   0x42ed82
0042ed67  lea   edx, [ebx - 0x1770]         ; 企业序号（1 基）
0042ed6d  imul  edx, edx, 0x34
0042ed75  add   dword ptr [edx + eax + 0x28], ebp   ; ★ 本月盈餘 += 消费额
0042ed7e  add   dword ptr [edx + eax + 0x2c], ebp   ; ★ 累積盈餘 += 消费额
```

> **未决**：`0x41d2c6` 的 20 个调用点里，哪些把 `to`/`from` 传成 `> 0x64`（企业）
> 只逐点验证了 `0x44bad8`（`add ebx, 0x64` 后 push → 企业付钱给玩家）。
> 其余站点（消费/过路费/新闻/卡片）**未逐一取证**，标为**未决**。

### 6.6 股价均值回归锚点 = 每股净值（再确认）

上市公司的锚点 = `企業+0x24 / 10000`；而「認購单价」= `企業+0x24 / 10000`（`idiv`，**整数**）。
⇒ 设计上自洽：**10000 股总股本，每股净值 = 资产额/10000**；
認購按净值成交，二级市场价格偏离净值过远时被阻尼拉回。
无上市公司的股票则用**初始价**（`+0x0c`）当锚点。

---

## 七、回合流程中的接线点

### 7.1 一天一次：`fcn_0041cf67`（176 条指令）

**调用者（A，自扫）**：只有 `0x41902e`（在 `0x418ebd` 内）。

**顺序（A）**：

```
0x41cf9c  call 0x452117([0x497160])   ; ① 日期 +1 天；edi = 是否跨月
0x41cfab  inc  [0x4990e4]             ; ② 天数计数器 += 1
0x41cfb1  call 0x41d89e               ; ③ 胜负判定；返回 1 → 整个日推进 return（不再采样）
0x41cfbf  call 0x423acf               ; ④ ★ 物价指数（只升不降，§2.6）
0x41cfc4  call 0x428475               ; ⑤
0x41cfc9..0x41cff2                    ; ⑥ [0x4990dc] 两段式递减（§3.2）
0x41cffb..0x41d064                    ; ⑦ 12 支股票：+6 递减、+7 的两个半字节递减
0x41d066  GetTickCount
0x41d06e  srand(tick)                 ; ⑧ ★ 重新播种
0x41d076  call 0x4291d6               ; ⑨ ★★ 每日行情（§2）
0x41d07b  call 0x452444               ; ⑩ 节日/日期事件
0x41d080  if (date.day == 15) { call 0x42ba97(分红); call 0x431712 }
0x41d099  if (edi == 1) { call 0x439bfa; ...; add [0x499084], 1 }   ; 跨月结算
0x41d0ff  for land in 1..num_lands: 递减 0x17 的 0xf0 半字节；处理地契到期
0x41d14b  for facility in 1..num_facilities: 同形
```

**关键片段（A）**：

```asm
0041cfc9  test  byte ptr [0x4990dc], 0x80      ; 全股市暂停交易倒数
0041cffb  jmp   0x41d003                        ; 12 支股票循环
0041d00d  mov   ch, byte ptr [eax + 0x496986]   ; 停牌倒数
0041d013  test  ch, ch
0041d019  dec   dl / mov [eax + 0x496986], dl   ; ★ 简单递减（无 0x80 两段式）
0041d02b  mov   dh, byte ptr [eax + 0x496987]   ; news_dir
0041d03a  sub   ch, 0x10 / mov [eax+0x496987], ch   ; 高半字节 −0x10
0041d05a  dec   dh / mov [eax + 0x496987], dh       ; 低半字节 −1
0041d066  call  dword ptr cs:[0x4623cc]         ; GetTickCount
0041d06e  call  0x456f50                        ; srand
0041d076  call  0x4291d6                        ; ★ 行情
```

### 7.2 一回合 = 8 个行动位：`0x418ebd`

```asm
00418f93  xor   ebx, ebx
00418f95  mov   esi, dword ptr [0x49910c]       ; 当前行动者
00418f9b  inc   esi
00418f9c  mov   dword ptr [0x49910c], esi
00418fa2  cmp   esi, dword ptr [0x499114]       ; num_players
00418fa8  jne   0x418fb6
00418faa  mov   dword ptr [0x49910c], 4         ; 轮到虚拟玩家 4..7
00418fb6  cmp   esi, 8
00418fb9  jne   0x418fca
00418fbb  xor   ecx, ecx
00418fbd  mov   dword ptr [0x49910c], ecx       ; 回到 0
00418fc3  mov   ebx, 1                          ; ★ ebx = 1 ⇒ 一轮走完
0041902a  test  ebx, ebx
0041902c  je    0x419033
0041902e  call  0x41cf67                        ; ★★ 日推进（→ 行情更新）
00419033  mov   eax, dword ptr [0x49910c]
00419039  call  0x41c84f                        ; 当前玩家回合开始
```

⇒ **接线结论（A）**：行动者顺序 `0,1,2,3 → 4,5,6,7 → 8`；
`esi == 8` 时回到 0 并置 `ebx = 1`，**此时推进一天（含行情）**，
所以**股价每天更新一次，发生在「所有行动位走完一圈、轮回到 0 号玩家之前」**。
`0x4291d6` 另一处调用是新局开局（`0x401ceb`）。

### 7.3 与本系统相关的其它入口

| 入口 | 地址 | 说明 |
|---|---|---|
| 股市屏（含红/黑卡模式） | `0x42b58f` | 三处调用：`0x417df5`（正常进股市）、`0x444ffa`（红卡 `push 1`）、`0x4450be`（黑卡 `push 2`）；模式存 `[0x48c2ed]` |
| 行情/持股两页绘制 | `0x4297f7`（`page` 参数） | 由 `0x42afcb` 调 |
| 上市公司详情卡 | `0x429d65`（408 条） | **窗口过程，全 exe 无直接 `call`**（经 `0x4018e7` 注册后由消息循环派发） |
| AI 选股/买卖打分 | `0x42c078`（464 条） | 买入 `push 1` @ `0x42c721` |
| AI 卖出/重整 | `0x42c79f`（634 条） | 卖出 `push 1` @ `0x42d02e` |
| 命运事件强制卖股 | `0x44c7ef`（`fortune_call_table[8]`） | `flag=0` → 钱进消失池 |
| 破产清算卖股 | `0x40cd87` @ `0x40d17b` | `flag=0` |

---

## 八、未决清单（**未用推测填充**）

1. **`0x499078` / `0x49907c` 的用途**：前者每日 `trunc(Σ现价×10)`、后者新局 `trunc(Σ初始价×10)`，
   两者**只被存档写出（`0x44808a`）、无任何逻辑读取**。是否有 UI 直接寻址这两格而未被 xref 捕获，未确证。
2. **`0x499080`（消失池）**：只在开局/读档清零，被卖出 `flag=0` 与 `0x41d2c6` 的 `to == -1` 累加，
   **无逻辑读取**。它是否就是存档里某个被显示的统计量，未决。
3. **`player_stocks` 的全部写入者**：只逐行验证了买入、卖出、`0x42565c`；
   其余 14 个 `written_by` 地址（卡片 / 新闻 / 命运 / 破产 / AI 重整）**未逐一取证**。
   且 `gen/xrefs.json` 的 `written_by` 混入了只读函数（`0x4297f7`、`0x42ba97` 等），**需逐行复核后才可引用**。
4. **`0x41d2c6`（通用转账）20 个调用点的参数**：只逐点验证了过路费支与 `0x44bad8`（企业付钱）。
   哪些站点传企业号（`> 0x64`、或「先 `add 0x64` 再 push」）未穷尽。
5. **`stock+0x08` 与 `+0x0a` 是否恒等**：初值上 `+0x08 > 1000` 时 `+0x0a` 由 `0x42915a` 随机缩水，
   之后同步增减 ⇒ 差值恒定但一般**不相等**。既有文档把 `+0x0a` 当「交易量」、
   把 `+0x08` 当「股数」，两者的**命名**属 B 级推断。
6. **`企業+0x1a`（level）** 在消费金额计算里的确切角色（等级→倍率表在哪张表）**未取证**。
7. **`0x4294d5` 摘除循环不 break** 是否可达（重复条目）**未确证**。
8. **关卡菜单 → (`stage`, `map`) 的映射**（`0x4029fd` 的返回值语义）属开局流程，未取证。
9. **`0x4291d6` 的 `[0x4990ec]` 在停牌/`news_dir != 0` 的股票上被跳过** ——
   即「全市场漂移」并非对所有股票生效。这是 A 级事实，但**是否为原版有意设计**无法从汇编判定。
10. **`fcn_004291d6` 是否有第三处调用**（经函数指针表）：自扫直接调用只找到 2 处，
   但没有检查所有 `call dword ptr [table]` 形态。

---

## 九、与既有结论**矛盾**之处（逐条）

| # | 既有说法 | 本规格（exe 为准） | 证据 |
|---|---|---|---|
| 1 | `rich4_stocks.h`：`player_stock_info` 第二字段 `int _` | **`float avg_cost`（单精度持仓成本均价）** | `0x428dd4 fmul dword [..+0x4971a4]`、`0x428e04 fstp dword [..+0x4971a4]` |
| 2 | `Q-COM-1`「**卖出不触发**企业归属重排（`_rich4_sell_stock` 里没有这一步）」 | **卖出也触发**：`0x428eb7 call 0x4294d5`（买 `0x428e14`） | 见 §6.3 |
| 3 | `Q-STOCK-6`「`[0x499084]` = 總天數 ⇒ 平均盈餘 = 累積盈餘/總天數」 | **`[0x499084]` = 经过的月数**（`0x41d0f9` 只在 `0x452117` 返回 1 时 +1，而它表示跨月） ⇒ 平均**月**盈餘 | `0x41cfa1` / `0x41d0f9` / `0x45216f` |
| 4 | 题面「股票表 96 项，工具提示 `dump 0x47f072 96 16`」 | 96 是**记录数**，步长 **36 字节**；`96 × 16 位`只覆盖 5.33 条 | §1.1 |
| 5 | `Q-STOCK-1`「先算星期、再查节日表」（并列语气） | 顺序是**先判星期日**（`wday == 0` 即刻返回 1），**再**查节日表 | `0x4523f3 je 0x452437` |
| 6 | `map-format.md` §4.1「`stocks_on_map` 每项 36 字节、**股价在 +8**」 | `+0x08` **不是股价**，是 u16 股数（`保留股份 = 10000 − +0x08`）；股价在 `+0x14`（开盘 `+0x10`） | `0x407de4`（读 `+8` 算保留股份）、`0x428d56`（买价读 `+0x14`） |
| 7 | 「企业资产额如何计入玩家总资产」（题面隐含） | **不计入**。总资产 = 现金+存款−贷款+股票市值+地产+设施 | `0x4239b9` 全函数 |

**已复核通过、维持原结论的条目**：休市日（§3.2）、涨停/跌停（§3.1）、
停牌不能买卖且偏移是 `+0x06`（§3.3）、休市那一屏是訊息框（§3.2）、
物价指数公式与调用时机（§2.6）、企业资产额静态只读（§6.2）、
持股排名与归属（§6.3，除第 2 条订正外）、台股屏两页与标题（§7.3 入口，
标题字符串 `0x4640a6`「持有股數表」/`0x4640b1`「股 價 表」分别画在 surface+0xc / +0x18）。

---

## 附：`.idata` 导入名解析（本规格自用，供复核）

`.idata` VA `0x462000`，RawOff `395264`，Size `3584`。
IThunk 里存的是 **RVA**（不是 VA），hint/name 条目在 `0x4624xx..0x4629xx`。

| 代码里写法 | IAT 槽 | 名称 |
|---|---|---|
| `call cs:[0x4623cc]` | `0x4623cc` | `GetTickCount` |
| `call cs:[0x4622a0]` | `0x4622a0` | `FloodFill` |
| `call cs:[0x462094]` | `0x462094` | `CreateSolidBrush` |
| `call cs:[0x4620b0]` | `0x4620b0` | `Pie` |

⇒ 日推进里的 `GetTickCount` + `srand` 组合与股市屏饼图的 `FloodFill` 均**已确名**，非推测。
