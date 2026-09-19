# 卡片系统（卡片效果函数逐条规格）

> 真值：`../Rich4/rich4.exe`（v3.11，602,112 字节，ImageBase `0x400000`）。
> 本文件所有 `@source` 均为原版虚拟地址（VA），可用
> `python3 ../rich4-remake/tools/disasm.py va 0x...` 逐字节复核。
>
> **进度**：**卡 1–30 全部完成**（30/30，每张都有独立的「精确效果 / 边界情况 /
> 防御卡查询 / 未决 / @source」）。汇总表见 **§十二**；逐卡进度台账见 §十。
> 30 张卡的效果函数、以及 18 处 `has_card` 调用点、全部台词表项都已逐条反汇编核对。
>
> **质检**：`python3 tools/lint_specs.py docs/systems/cards.md` → **0 错误**
> （1270 个 VA 引用全部落在已知节内）。剩余的 WARN 全部是
> 「某个子小节内部没有自己的 `@source` 字样」这类**格式**提醒 ——
> 每张卡的 `@source` 汇总块都完整存在于该卡小节末尾。

## 〇、本文件的验证方式与证据级别

### 0.1 证据级别定义（沿用 `../00-methodology.md`）

| 级别 | 含义 | 本文件中的用法 |
|---|---|---|
| **A** | `rich4.exe` 字节本身 | 全部公式、常量、分支顺序、调用关系 |
| **B** | 由 A 机械推导（反汇编 + 表解引用），但**语义命名**是我给的 | 函数名（如 `remove_card`）——命名是推断，地址是事实 |
| **C** | 既有文档（`rich4-re/`）的说法 | 仅用于「与本文冲突」的对照，**不作为结论来源** |
| **未决** | 无法从静态反汇编判定 | 明确标注，不用推测填充 |

### 0.2 本文件的取证流程（每条结论都可复现）

1. **函数边界**：用 `tools/rich4dis.py`（递归遍历）取函数体；
   卡片效果函数的边界与 `card_functions[]` 表项**逐字节吻合**（见 §1.2），
   因此不存在「线性反汇编失步」的风险。
2. **每条结论配汇编原文摘录**，摘录中的地址即真值地址。
3. **凡出现「查表 + push + call」的形状，一律先解引用表项**
   （确认表里存的是台词指针、价格、还是函数指针）再下结论。
   典型反例：`0x44ef41` 形如仇恨更新函数，实为 `player_say`（查表取台词指针再 push）。
4. **调用关系复核**：`gen/functions.json` 的 `callers` 字段**不完整**
   （实测 `0x40df69` 只列 3 个调用者，实际至少 34 个），
   故本文件的调用关系一律由我自己重建的调用图 + `disasm.py callers` 复核。
5. **质检**：本文用 `python3 tools/lint_specs.py docs/systems/cards.md` 校验
   （VA 落在节内、每节带 `@source`、含「未决」标注）。

### 0.3 本文件**不**回答的问题

- 卡片的**动画/音效表现**（属表现层，汇编只给参数不给观感）。
- 卡片**在商店的售卖流程**（属经济系统，本文只在必要处引用价格字段）。
- 台词字符串的**内容翻译**（本文只给 VA 与索引公式）。

---

## 一、卡片系统的机械结构

### 1.1 卡片数据表 `card_data[]` @ VA `0x47fdf2`（30 项 × 8 字节）

表项 **`[i]` 对应卡号 `i+1`**（即 1-based，见 §1.1.2 的下标证据）。

| 偏移 | 类型 | 字段 | 可靠性 | 依据 |
|---|---|---|---|---|
| `+0` | `char*` | `name` → Big5 打包串（`0x466ac2` 起） | A | `0x441c9e` |
| `+4` | `uint8` | `b4`：**初始副数**，装入运行时数组 `0x499198[30]` | A（用途为 B） | `0x4071a5` |
| `+5` | `uint8` | `b5`：**价格**（单位＝點券，见 §1.5） | A | `0x42d152`/`0x42d0ef` |
| `+6` | `uint8` | `b6`：**全文件搜不到任何引用** | A（不存在引用） | 见 §1.1.4 |
| `+7` | `uint8` | `b7`：AI 使用门槛系数 | A（语义为 B） | `0x41e6a4` |

实测原始字节（`disasm.py` 的 `dump` 不支持 8 字节步长，故直接读文件）：

```text
[ 0] c2 6a 46 00 01 c8 02 02   → 卡1  均富卡  b4=1   b5=200 b6=2 b7=2
[ 1] c9 6a 46 00 02 c8 02 02   → 卡2  均貧卡  b4=2   b5=200 b6=2 b7=2
...
[29] 89 6b 46 00 03 46 00 00   → 卡30 烏龜卡  b4=3   b5=70  b6=0 b7=0
```
完整 30 项见 §1.1.5。

`@source` `VA 0x47fdf2`（表本体）、`VA 0x441c9e`（名字字段）、`VA 0x42d165`（价格字段）、
`VA 0x41e6a4`（`b7` 字段）。

#### 1.1.1 名字字段与两处「卡名」的区别（应要求澄清）

卡名在 exe 里存在**两份**：

| 表 | 位置 | 是否被引用 | 结论 |
|---|---|---|---|
| **表 A（本文采用）** | `card_data[i].+0` → 打包串 `0x466ac2` 起 | ✅ 被 `card_data[]` 引用 | 卡片系统真正使用的卡名 |
| **表 B** | 打包串 `0x465f1a`/`0x465f4c` 起；指针表 `0x4760fc`、`0x47610c`、`0x47611c` | ❌ **全文件找不到引用** | 用途**未决**；本文不使用 |

表 B 的三张指针表（实测内容）：

```text
0x47611c[ 0..19] = 均貧卡 均富卡 改建卡 怪獸卡 拍賣卡 拆除卡 查封卡 查稅卡 紅卡 烏龜卡
                   送神符 停留卡 陷害卡 復仇卡 惡魔卡 換地卡 換屋卡 黑卡 嫁禍卡 搶奪卡
0x47610c[ 0.. 3] = 冬眠卡 同盟卡 免費卡 免罪卡
0x4760fc[ 0.. 3] = 惡犬 惡魔 間諜 天使卡        ← 注意前 3 项不是卡片
```
对 `0x4760fc / 0x47610c / 0x47611c` 三个地址做**全文件 4 字节小端扫描**：命中 0 处；
对 `0x466ac2` 扫描：命中 1 处＝`0x47fdf2`（表 A 的名字字段）。
故表 B 是**孤立数据**（可能是旧版本残留，也可能是被未覆盖代码引用的数据）。
**未决**：表 B 的用途。本文所有卡名一律取自表 A。

`@source` `VA 0x466ac2`（表 A 名字串）、`VA 0x4760fc` / `VA 0x47610c` /
`VA 0x47611c`（表 B 指针表）、`VA 0x465f4c`（表 B 字符串）。

#### 1.1.2 `+4` 字段（b4）与 `+5` 字段（b5）的下标证据

存在两个不同的「基址预偏置」，读表时必须区分：

```asm
; ① 0-based：b4 → 运行时数组（0x4071a3）
004071a3  xor   ebx, ebx
004071a5  mov   al, byte ptr [ebx*8 + 0x47fdf6]   ; = card_data[ebx].+4
004071ac  mov   byte ptr [ebx + 0x499198], al     ; → 0x499198[ebx]
004071b2  inc   ebx
004071b3  cmp   ebx, 0x1e                         ; 30 张
004071b6  jl    0x4071a5
```

```asm
; ② 1-based：名字/价格用「表基址-8」预偏置（0x441c9e、0x42d152）
00441c9e  mov   edx, dword ptr [eax*8 + 0x47fdea]  ; = card_data[eax-1].+0（名字）
0042d152  ...
0042d15f  mov   edx, dword ptr [esp + 0x18]        ; edx = 卡号
0042d165  mov   al,  byte ptr [edx*8 + 0x47fdef]   ; = card_data[卡号-1].+5（价格）
```
`0x47fdea = 0x47fdf2 - 8`，`0x47fdef = 0x47fdf2 - 3`。
**结论**：卡号 1..30 ↔ 表项 0..29；`b4`/`b5`/`b7` 均按此换算。
（1-based 与 0-based 两种写法在 exe 里**并存**，这是 Watcom 对减 1 的常见优化。）

`@source` `VA 0x4071a5`、`VA 0x441c9e`、`VA 0x42d165`。

#### 1.1.3 `+5`（价格）的两处独立证据

```asm
; 证据①：买卡扣點券（0x42d237）
0042d23c  push  edx
0042d23d  mov   ecx, dword ptr [esp + 0xc]
0042d241  push  ecx
0042d242  call  0x4412e4                        ; add_card(player, card)
0042d24f  mov   eax, dword ptr [esp + 0xc]      ; 卡号
0042d255  mov   bl,  byte ptr [eax*8 + 0x47fdef]; bl = 价格
0042d25c  sub   word ptr [edx + 0x496b98], bx   ; player.points(0x30) -= 价格
```
```asm
; 证据②：手牌满时丢弃「价格最低」的那张（0x44128f）
00441298  mov   ebx, 0x2710                     ; 初值 10000
004412c8  mov   al,  byte ptr [edx*8 + 0x47fdef]; 候选卡的 b5
004412d4  cmp   ebx, eax
004412d6  jle   0x4412a1
004412d8  mov   ebx, eax                        ; 记录更小者
004412da  mov   esi, edx                        ; 记住卡号
```
另有一处**排序比较器** `0x42d0ef` 也以 `+5` 为键：
```asm
0042d10d  mov   cl, byte ptr [ecx*8 + 0x47fdf7]  ; = card_data[cl-1].+5
0042d114  cmp   cl, byte ptr [ebx*8 + 0x47fdf7]
0042d11d  mov   eax, 0xffffffff                  ; 前者贵 → 排前面（降序）
```
**结论**：`+5` 是「价格」，单位是玩家结构 `+0x30` 的點券（见 §1.5）。

`@source` `VA 0x42d255`（买卡扣款）、`VA 0x4412c8`（丢弃最便宜）、
`VA 0x42d10d`（排序键）、`VA 0x496b98`（`player.points`）。

#### 1.1.4 `+6`（b6）：不存在引用（诚实边界）

对 `0x47fdf8`（表基址 +6，0-based）与 `0x47fdf0`（= `0x47fdea` +6，1-based）
分别做全文件 4 字节小端扫描，**命中 0 处**；在已建图函数的全部指令操作数中
搜索 `0x47fdf8` / `0x47fdf0` 也为 0 命中。
因此 **`b6` 的语义未决**——不能从它非零就反推任何效果。
（表中 b6 非零的卡片共 12 张，例如卡 1 `b6=2`、卡 3 `b6=1`。）

#### 1.1.5 `card_data[30]` 全表（卡名／b4／b5／b6／b7）

| 卡号 | 卡名 | b4 | b5 | b6 | b7 |
|---|---|---|---|---|---|
| 1 | 均富卡 | 1 | 200 | 2 | 2 |
| 2 | 均貧卡 | 2 | 200 | 2 | 2 |
| 3 | 購地卡 | 4 | 35 | 0 | 1 |
| 4 | 換地卡 | 4 | 25 | 0 | 0 |
| 5 | 換屋卡 | 4 | 20 | 0 | 0 |
| 6 | 轉向卡 | 3 | 20 | 0 | 0 |
| 7 | 改建卡 | 8 | 15 | 0 | 0 |
| 8 | 拍賣卡 | 3 | 20 | 0 | 1 |
| 9 | 天使卡 | 2 | 160 | 2 | 0 |
| 10 | 惡魔卡 | 1 | 180 | 2 | 2 |
| 11 | 怪獸卡 | 2 | 60 | 0 | 2 |
| 12 | 拆除卡 | 5 | 15 | 0 | 1 |
| 13 | 搶奪卡 | 4 | 25 | 0 | 2 |
| 14 | 停留卡 | 4 | 20 | 0 | 0 |
| 15 | 冬眠卡 | 2 | 100 | 2 | 2 |
| 16 | 夢遊卡 | 4 | 25 | 0 | 1 |
| 17 | 陷害卡 | 4 | 20 | 0 | 2 |
| 18 | 復仇卡 | 4 | 20 | 0 | 0 |
| 19 | 嫁禍卡 | 4 | 40 | 0 | 0 |
| 20 | 免費卡 | 4 | 25 | 0 | 0 |
| 21 | 免罪卡 | 4 | 25 | 0 | 0 |
| 22 | 送神符 | 3 | 10 | 0 | 0 |
| 23 | 請神符 | 3 | 20 | 0 | 0 |
| 24 | 紅卡 | 3 | 50 | 0 | 0 |
| 25 | 黑卡 | 3 | 30 | 0 | 1 |
| 26 | 查稅卡 | 4 | 35 | 0 | 1 |
| 27 | 漲價卡 | 3 | 35 | 0 | 0 |
| 28 | 查封卡 | 3 | 35 | 0 | 1 |
| 29 | 同盟卡 | 2 | 40 | 0 | 0 |
| 30 | 烏龜卡 | 3 | 70 | 0 | 0 |

`@source` `VA 0x47fdf2`（30×8 数据）、`VA 0x4071a5`（b4 装入）、
`VA 0x47fdf7`（b5）、`VA 0x47fdf1`（b7）。

### 1.2 卡片效果函数表 `card_functions[]` @ VA `0x475d5c`（31 项 × 4 字节）

```asm
; 唯一的两处间接调用（同一个函数的两条分支）
00441cc6  call  dword ptr [eax*4 + 0x475d5c]
00441e00  call  dword ptr [eax*4 + 0x475d5c]
```
`eax` 即卡号（1..30），故 **`card_functions[1..30]` 对应卡 1..30**，`[0]` 为 NULL 占位。

| 卡号 | 函数 VA | 卡号 | 函数 VA |
|---|---|---|---|
| 1 | `0x004420d8` | 16 | `0x004441dc` |
| 2 | `0x004421b4` | 17 | `0x004444bf` |
| 3 | `0x00442325` | 18 | `0x004420d5` ⚠️空桩 |
| 4 | `0x00442622` | 19 | `0x004420d5` ⚠️空桩 |
| 5 | `0x00442b02` | 20 | `0x004420d5` ⚠️空桩 |
| 6 | `0x00442f4d` | 21 | `0x004420d5` ⚠️空桩 |
| 7 | `0x0044309b` | 22 | `0x00444c45` |
| 8 | `0x00443225` | 23 | `0x00444e1a` |
| 9 | `0x004434c0` | 24 | `0x00444f25` |
| 10 | `0x004436e0` | 25 | `0x0044503f` |
| 11 | `0x00443917` | 26 | `0x004451f0` |
| 12 | `0x00443b0f` | 27 | `0x0044542d` |
| 13 | `0x00443e3d` | 28 | `0x00445593` |
| 14 | `0x00443f80` | 29 | `0x00445710` |
| 15 | `0x004440ea` | 30 | `0x004458df` |

空桩本体（**2 字节 + 对齐**）：
```asm
004420d5  xor   eax, eax        ; 31 c0
004420d7  ret                   ; c3
```

**边界自洽性校验**：`rich4dis.py` 给出的函数边界与表项**完全吻合**，
例如 `card_functions[1]=0x4420d8`，函数体 220 字节，`0x4420d8+220 = 0x4421b4`
＝ `card_functions[2]`。逐项核对 30 项全部吻合，
故本文的函数体不含相邻函数的指令。

`@source` `VA 0x475d5c`（函数表）、`VA 0x441cc6` / `VA 0x441e00`（唯一调用点）。

### 1.3 AI 决策函数表 @ VA `0x475324`（1 项/卡，索引 1..30）

```asm
; 只有 AI（who_plays & 6 != 0）才走这条路（0x441d00 起）
0041e6e6  mov   eax, dword ptr [esp + 4]         ; 卡号
0041e6ea  call  dword ptr [eax*4 + 0x475324]
```
该表 `[1..30]` 与卡号一一对应；其中 **`[18]/[19]/[20]/[21]` 全部指向
`0x41e6e3`（`xor eax,eax; ret`）**，即 AI 也不能「主动使用」復仇/嫁禍/免費/免罪卡，
与 §1.4 的结论互相印证（两条独立证据链）。

AI 是否使用某卡由 `0x41e69e` 判定：
```asm
0041e6a4  mov   dl, byte ptr [eax*8 + 0x47fdf1]  ; dl = card_data[卡号-1].+7（b7）
0041e6ab  imul  eax, dword ptr [0x49910c], 0x68
0041e6b2  mov   al,  byte ptr [eax + 0x496b7f]   ; al = player[0x17]（字段名未决）
0041e6bd  sub   edx, eax
0041e6c1  cmp   edx, 2
0041e6c4  jl    0x41e6c9
0041e6c6  xor   eax, edx                          ; edx>=2 → 返回 0（绝不用）
0041e6c8  ret
0041e6c9  cmp   edx, 1
0041e6cc  jne   0x41e6e6
0041e6ce  call  0x456f2d                          ; PRNG，edx==1 时 1/3 概率放弃
```
**结论**：`b7 - player[0x17] >= 2` → AI 永不用该卡；`== 1` → 1/3 概率放弃；
`<= 0` → 一定使用。`player[0x17]`（`VA 0x496b7f`）的语义**未决**。

`@source` `VA 0x475324`、`VA 0x41e69e`、`VA 0x441d00`。

### 1.4 手牌数组与卡槽操作

#### 手牌数组 `VA 0x499120`，布局 `player*15 + slot`，`slot ∈ [0,14]`，`0` = 空槽

```asm
; 初始化：4 名玩家 × 15 槽 = 60 字节清零（0x407183）
00407183  push  0x3c
00407185  push  edi
00407186  push  0x499120
0040718b  call  0x456f60        ; memset
00407193  push  0x3c
00407195  push  edi
00407196  push  0x49915c        ; ★ 另一份同样 4×15 的数组，用途未决
0040719b  call  0x456f60
```

#### 全部卡槽操作函数（本文用到的）

| VA | 签名（推断） | 行为 | 关键证据 |
|---|---|---|---|
| `0x441262` | `count_cards(player)` | 数 15 槽中的非 0 项 | `cmp ecx,0xf` |
| `0x441343` | `remove_card(player, card)` | 找**第一个**匹配槽，`memmove` 收拢，末槽置 0；`inc byte [card+0x499197]` | `0x44138f call 0x456de8` |
| `0x4412e4` | `add_card(player, card)` | 手牌满 15 张时先 `0x44128f` 选「最便宜」的一张移除，再放入第一个空槽 | `0x4412ea`、`0x441324` |
| `0x44128f` | `cheapest_card(player)` | 返回手中 `b5` 最小者的卡号（初值 10000） | `0x441298` |
| `0x4413ad` | `has_card(player, card)` | 命中返回 1，否则 0（**只扫 15 个手牌槽**） | `0x4413df` |
| `0x441e77` | `remove_random_card(player)` | `idx = PRNG % count`，移除并返回该卡号 | `0x441e8e` |
| `0x441ece` | `remove_half_cards(player)` | 移除前 `floor(count/2)` 张 | `0x441ee7` |
| `0x441b0a` | 绘制手牌 UI | 用 `card_data[..].+0` 取卡名 | `0x441b84` |
| `0x441baa` | **主动使用卡片的主流程** | 见 §1.6 | `0x441cc6` |
| `0x441f73` | 使用卡片弹窗/动画 | 无状态影响 | `0x441f7a` |

`0x441343` 里 `inc byte [card + 0x499197]` 的对象就是 §1.1 的运行时数组
`0x499198`（`0x499197 + 卡号` = `0x499198 + 卡号-1`）。
**未决**：该计数器的语义。观测到「加入手牌时 `0x4412e4` 会 `dec`、
移出手牌时 `0x441343` 会 `inc`」，且 `b4` 为其初值；
AI 在 `0x42f079` 把它当作「考虑该卡的次数」来循环。
**最保守的读法**：它是「每张卡在本局中的可获取份数」，初值 = `b4`。
但「使用后仍 `inc`」这一点与该读法不符，故标为**未决**。

`@source` `VA 0x441262`、`VA 0x441343`、`VA 0x4412e4`、`VA 0x44128f`、
`VA 0x4413ad`、`VA 0x441e77`、`VA 0x441ece`、`VA 0x441b0a`、`VA 0x441baa`、
`VA 0x407183`（手牌清零）、`VA 0x42f082`（AI 读该计数）。

#### 「不可主动使用」的四张卡（两条独立证据）

1. `card_functions[18..21] = 0x004420d5`（`xor eax,eax; ret`）。
2. AI 表 `0x475324[18..21] = 0x0041e6e3`（同样 2 字节空桩）。

```asm
@source VA 0x475d5c + 4*18..21  → 0x004420d5
004420d5  xor   eax, eax
004420d7  ret
@source VA 0x475324 + 4*18..21  → 0x0041e6e3
0041e6e3  xor   eax, eax
0041e6e5  ret
```
**结论**：復仇/嫁禍/免費/免罪 **不可主动使用**（选卡界面里选了也只会得到
「使用失败」返回值 0）。真实机制是「有害卡命中目标时，施害卡先查目标是否持有防御卡」
——每张卡的查询**内联在自己的效果函数里**，查询的卡号各不相同，详见各节。

### 1.5 关键全局变量

| VA | 名称（推断） | 依据 |
|---|---|---|
| `0x49910c` | 当前行动玩家下标（0-based） | `0x41d44c` 赋值；各卡函数用 `imul eax,[0x49910c],0x68` 取玩家结构 |
| `0x499114` | **玩家人数** | `0x407157 mov eax,[0x46cb3c]; 0x40715c add eax,2; 0x40715f mov [0x499114],eax` |
| `0x499110` | 「地契年限」表索引 | `0x442455 mov ecx,[edx*4+0x4751f0]` |
| `0x4751f0` | 年限增量表（`0,0x20000,0x10000,0x600,0x300,0x100`…） | 同上 |
| `0x4990e8` | **物价指数**（`price_index`），初值 **1** | `0x4073b4 mov dword [0x4990e8],1` |
| `0x498e84` | 住宅用地数组基址（步长 `0x34`） | 与 `land-rent.md` 一致 |
| `0x498e88` | **商業用地数组基址（步长 `0x38`）** | `0x4424dc`–`0x4424e9` |
| `0x498e80` | 地图格→地产编号表（步长 `0x28`，字段 `+0x20` 为 uint16） | `0x442345`–`0x442350` |
| `0x496b68` | 玩家结构基址，步长 **`0x68`** | 全篇 |
| `0x496bb4` | `player.hostility[4]`（每个玩家 4 个 dword） | `0x40df83` 的 `+ecx*4` |
| `0x48be58` | AI 卡函数的决策中转数组（dword） | `0x41e6f6`、`0x41fabb` |
| `0x48be18` | 「需要重绘地图」标志 | `0x41d548`、`0x41d4e6` |

`@source` `VA 0x49910c`（`0x41d44c` 赋值）、`VA 0x499114`（`0x40715f` 赋值）、
`VA 0x4990e8`（`0x4073b4` 赋初值 1）、`VA 0x498e84` / `VA 0x498e88` / `VA 0x498e80`、
`VA 0x496b68`、`VA 0x496bb4`、`VA 0x48be58`、`VA 0x48be18`、`VA 0x4751f0`。

### 1.6 主动使用卡片的调用契约（**返回值语义**）

```asm
00441cc4  mov   eax, ebx
00441cc6  call  dword ptr [eax*4 + 0x475d5c]     ; ← 卡片效果函数
00441ccd  mov   esi, eax
00441ccf  test  eax, eax
00441cd1  jne   0x441ce1                         ; 非 0 = 成功 → 收尾退出
00441cd3  push  eax
00441cd4  push  0x48233a
00441cd9  call  0x4542ce                         ; 失败提示
00441ce1  test  esi, esi
00441ce3  je    0x441c22                         ; 为 0 → 回到「重新选卡」
```
**结论（A 级，本文所有卡片都遵守）**：
- 返回值 **`0`** ＝ 使用失败/取消：**卡片不消耗**（效果函数必须自己保证，
  即「移除手牌」必须放在失败判定**之后**），玩家回到选卡界面可重选。
- 返回值 **非 0** ＝ 成功。
- 因此本文在每张卡里都注明「`remove_card` 发生在什么位置」，这是复刻时必须保留的细节。
- ⚠️ 失败提示的实际文案**未决**：`0x4542ce(0x48233a, 0)` 会解引用
  `0x48233a` 处的 8 字节描述符（实测为 `{3, 0}`），随后
  `0x4540d8` 因首参为 0 而**直接返回**。该路径更像 UI 对象接口而非静态文案。

`@source` `VA 0x441cc6`、`VA 0x441ccd`、`VA 0x4542ce`、`VA 0x4540d8`。

#### 1.6.1 不变量：**`remove_card` 之后必返回非 0**（30/30 机械核验）

既然「返回值 0 ＝ 卡未消耗」，那反过来就有个可判定问题：
**有没有哪张卡在 `remove_card` 之后还会返回 0？** 答案是没有 ——
这条不变量是复刻时选 `fail`（`ok:false`）还是「成功但无变化」的**唯一依据**。

核验方式（可复现）：

```bash
.venv/bin/python tools/scratch/consume_invariant_check.py
```

它对 30 张卡片函数逐个：
① 找出函数体内所有 `call 0x441343`（`remove_card`）；
② 从其后一条指令起，在**全部已建图函数**拼成的全局指令表上做前向 DFS
（30 张卡共用 `0x443069` / `0x441f1b` / `0x44557e` / `0x444685` / `0x442afa`
等收尾，只看本函数体会把「跳进共享尾声」误判成出口）；
③ 沿**执行序**携带「最近一次写 `eax` 的指令」（`ax`/`al`/`ah` 也算写 ——
原版大量用 `xor eax,eax / mov ax,<非零>`），到出口（`ret` 或跳出已建图代码的 `jmp`）时判定。

在 v3.11 上的结果：**30 张卡、每条出口的 `eax` 都来自选中目标寄存器**
（`mov eax, esi` / `edi` / `ebx` / `ebp` / `dword [esp]`）或字面量 `1`：

| 出口形态 | 卡 |
|---|---|
| `mov eax, esi`/`edi`/`ebx`/`ebp`（选中的目标／掩码） | 3、4、5、6、7、8、9、10、11、13、14、16、17、23、26、27、28、29、30 |
| `mov eax, 1` | 1、15、18 |
| `mov eax, dword ptr [esp]`（栈上的目标值） | 12 |
| `mov eax, ebx`（`ebx` 是掩码／选中股号，恒非 0） | 2、22、24、25 |

**推论（复刻用）**：
- `ok === false` ⟺ 原版返回 0 ⟺ **卡还在手上、状态一点不动**；
- 「目标已选定但什么都没发生」（满级設施、已冬眠的替身、停牌股…）
  在原版是**非 0 = 成功 + 卡已扣**，复刻必须写成「成功但无变化」，
  **不能**写成「失败不扣卡」；
- ⚠️ 反例在 v3.11 中**不存在**；若将来发现某张卡违反此不变量，
  说明上面的 DFS 有漏（先怀疑跳表/间接跳转未覆盖），而不是直接照抄结论。

`@source` `VA 0x441343`、`VA 0x443069`、`VA 0x441f1b`、`VA 0x44557e`、
`VA 0x444685`、`VA 0x442afa`。

#### 1.6.2 每张卡 `remove_card` 的相对位置（甲/乙/丙/丁/戊 五组）

`rich4-spec/tools/scratch/consume_probe.py` 一次列出「`call 0x441343` 与全部分支」
的相对次序，据此分五组：

| 组 | 卡 | `remove_card` 位于 | 目标选不到时 |
|---|---|---|---|
| **甲** | 2、6、9、10、11、12、14、16、17、23、26、27、28、29、30 | 选框/AI 取参**之后立刻** | 不扣卡 |
| **乙** | 3、4、5、7、8、13 | 「买/换/拆/抢**成功**」判定之后 | 不扣卡 |
| **丙** | 1、15 | 函数**开头**（无目标选择） | 无失败路径 |
| **丁** | 22 | 「有没有东西可送」判定之后 | 不扣卡 |
| **戊** | 24、25 | 「股市屏/AI 有没有选到股」判定之后 | 不扣卡 |

各组 `remove_card` 的 VA 见 §1.6.1 的核验输出（`consume_probe.py` 亦逐张打印）。
甲组是唯一需要特别注意的一组：它们**进入了选目标流程**，所以
「选到了但效果落空」也照扣卡。

`@source` `VA 0x4421f1`、`VA 0x442610`、`VA 0x442aeb`、`VA 0x442f36`、
`VA 0x442f8a`、`VA 0x443213`、`VA 0x44349f`、`VA 0x443505`、`VA 0x44371d`、
`VA 0x443954`、`VA 0x443b53`、`VA 0x443f40`、`VA 0x443fca`、`VA 0x4440f6`、
`VA 0x444219`、`VA 0x4444fc`、`VA 0x444ce4`、`VA 0x444e52`、`VA 0x44502a`、
`VA 0x4451db`、`VA 0x445233`、`VA 0x44546a`、`VA 0x4455cc`、`VA 0x445750`、
`VA 0x445929`。

### 1.7 公共被调函数语义（本文反复引用）

| VA | 名称（推断） | 证据 |
|---|---|---|
| `0x40df69` | `update_hostility(a, b, delta)` | `add edi, ecx; mov [eax+0x496bb4], edi`，`eax = a*0x68`，`ecx = b` |
| `0x41d2c6` | `pay_money(from, to, amount, ?)` | 写 `0x496b84`(cash)、`0x496b88`；`0x442479` 调用点 |
| `0x41d433` | `set_current_and_refresh(player)` | 写 `0x49910c`，调用重绘后**还原** |
| `0x41d546` | `refresh_map()` | 写 `0x48be18 = 0` 后 `call 0x41906a(1)` |
| `0x40a4e1` | `redraw_lands(0)` | 读 `0x498e84`/`0x498e88`，写 `0x496b6c` |
| `0x44ef41` | **`player_say(player, slot, text)`** | `0x44ef74` 用 `player*0x68` 取玩家；`0x44ef48` 取 `text`。⚠️ 它的形状与仇恨函数相似，但两者不可互指 |
| `0x4521cb` | `add_deed_date(a, b)` 带 `0xc00` 进位回绕 | `0x4521e2 cmp edx,0xc00` |
| `0x446ae8` | `modal_card_dialog(x)` → `0x4018e7(0x445e4d, x)` | `0x446ae8` 全文 6 条指令 |
| `0x41e6f2` | `ai_scratch(card)` → `0x48be58[card]` | `0x41e6f6` |

`update_hostility` 的完整语义（本文多次引用，故在此定死）：
```asm
0040df6b  mov   edx, dword ptr [esp + 0xc]   ; a
0040df6f  mov   ebx, dword ptr [esp + 0x10]  ; b
0040df73  cmp   edx, ebx
0040df75  je    0x40dfd7                     ; a == b → 直接返回
0040df77  cmp   dword ptr [esp + 0x14], 0    ; delta
0040df7c  jge   0x40df8d
0040df7e  imul  eax, edx, 0x68
0040df81  mov   ecx, ebx
0040df83  cmp   dword ptr [eax + ecx*4 + 0x496bb4], 0
0040df8b  je    0x40dfd7                     ; delta<0 且当前仇恨为 0 → 不改变
0040df9b  mov   edi, dword ptr [eax + 0x496bb4]
0040dfa1  add   edi, ecx
0040dfa3  mov   dword ptr [eax + 0x496bb4], edi
0040dfa9  test  edi, edi
0040dfab  jge   0x40dfb5
0040dfaf  xor   ecx, ecx
0040dfaf  mov   dword ptr [eax + 0x496bb4], ecx ; 下界钳到 0，无上界钳位
0040dfbc  imul  eax, edx, 0x68
0040dfc1  mov   cl,  byte ptr [eax + 0x496ba9] ; player.allied_player(0x41)
0040dfc7  lea   eax, [ebx + 1]
0040dfca  cmp   ecx, eax
0040dfcc  jne   0x40dfd7
0040dfce  push  edx
0040dfcf  call  0x40cc1a                     ; delta>0 且 b 是盟友 → 解除同盟
```
**注意**：`hostility[a][b]` 是 4 项（`b*4`），且**只有下界钳位，没有上界钳位**。

`@source` `VA 0x40df69`（`update_hostility`）、`VA 0x41d2c6`、`VA 0x41d433`、
`VA 0x41d546`、`VA 0x40a4e1`、`VA 0x44ef41`、`VA 0x4521cb`、`VA 0x446ae8`、
`VA 0x41e6f2`、`VA 0x42d237`、`VA 0x42d145`。

---

## 二、逐卡规格

> 约定：下文「玩家结构 `+0xNN`」= `VA 0x496b68 + 0xNN`。
> 「角色台词表」= `VA 0x48123a`，**步长 `0x168`(360) 字节＝90 个 dword**，
> 第 `k` 条台词地址 = `0x48123a + 360*character + 4*k`（实测：
> `k=0` → `0x46927a` `"#0426有錢大家花！"`，卡 1 使用）。

---

### 卡 1 · 均富卡

| 项 | 值 |
|---|---|
| 卡号 | 1 |
| 卡名 VA | `0x00466ac2`（`"均富卡"`，Big5；读法：由 `card_data[0].+0` 指向，§1.1.2） |
| 函数 VA | `0x004420d8`（76 条指令，220 字节） |
| 可否主动使用 | ✅ 可（`card_functions[1]` 非空桩） |
| 查防御卡 | ❌ 不查（无差别全体效果） |
| 目标选择 | 无（自动作用于全体在局玩家） |

#### 精确效果

1. **立即弃掉自己手里的这张卡**（在任何效果之前）：
   ```asm
   004420db  push  1
   004420dd  mov   edx, dword ptr [0x49910c]
   004420e3  push  edx
   004420e4  call  0x441343                 ; remove_card(当前玩家, 1)
   ```
2. **说台词**：`player_say(当前玩家, 3, 角色台词表[character*90 + 0])`
   （`k=0`，内容 `"#0426有錢大家花！"`）：
   ```asm
   004420f7  mov   dl, byte ptr [eax + 0x496b7b]  ; player.character(0x13)
   ; eax = 360 * character
   0044210e  mov   ebx, dword ptr [eax + 0x48123a]
   00442114  push  ebx
   00442115  push  3
   00442117  push  ecx
   00442118  call  0x44ef41
   ```
3. **求全体在局玩家的现金均值**（`who_plays != 0` 者参与；**含自己**）：
   ```asm
   00442126  mov   edi, dword ptr [0x499114]        ; 玩家人数
   00442130  imul  eax, ebx, 0x68
   00442133  cmp   byte ptr [eax + 0x496b7d], 0     ; player.who_plays(0x15)
   0044213a  je    0x442143                          ; == 0 → 跳过
   0044213c  add   esi, dword ptr [eax + 0x496b84]  ; Σ player.cash(0x1c)
   00442142  inc   ecx                               ; 计数
   00442146  mov   eax, esi
   00442148  mov   edx, esi
   0044214a  sar   edx, 0x1f
   0044214d  idiv  ecx                               ; ★ 有符号除法
   0044214f  mov   esi, eax                          ; avg = Σ / 人数
   ```
   **取整语义**：`idiv` 向零截断（不是向下取整）。`esi` 保存 32 位有符号商。
4. **逐个把在局玩家的现金直接写成 `avg`**；对**高于均值**的玩家额外调整仇恨：
   ```asm
   00442167  mov   edx, dword ptr [eax + 0x496b84]  ; 该玩家 cash
   0044216d  cmp   esi, edx
   0044216f  jge   0x442190                          ; avg >= cash → 只赋值，不动仇恨
   00442171  sub   edx, esi                          ; cash - avg（**正数**）
   00442173  mov   ecx, 0x64                         ; 100（十进制）
   00442178  mov   eax, edx
   0044217a  sar   edx, 0x1f
   0044217d  idiv  ecx
   0044217f  push  eax                               ; delta（正）
   00442186  push  ecx(=[0x49910c])                  ; 施卡者
   00442187  push  ebx                               ; 目标玩家
   00442188  call  0x40df69                          ; update_hostility
   00442190  imul  eax, ebx, 0x68
   00442193  mov   dword ptr [eax + 0x496b84], esi   ; cash = avg
   ```
   即 `delta = (cash - avg) / 100`（**十进制 100**，`idiv` 向零截断），为**正值**
   → `hostility[该玩家][施卡者]` **增加**（「被拉低的人恨施卡者」）。
   ★★ **2026 本轮订正**：本节正文原先三处写成「为负值 → 敌意减少」/「目标现金 < avg ⇒ delta 为负」，
   与本段汇编**自相矛盾**；通道 2 `rich4-spec/tests/test_average_cards.py`（38/38）用
   非对称现金（1000 / 500 / 300）实测：只有**现金 1000** 的那位被调用，
   `delta = (1000−600)/100 = +4`，而 500 / 300 两位**一次都没调**。
   与卡 2（均貧）的「目标被拉低 ⇒ 正 delta」是同一口径。
5. **刷新画面**并返回 1：
   ```asm
   0044219c  mov   ebx, dword ptr [0x49910c]
   004421a2  push  ebx
   004421a3  call  0x41d433
   004421ab  mov   eax, 1
   ```

`@source` `VA 0x4420db`（弃卡）、`VA 0x44210e`（台词表）、`VA 0x44214d`（均值 `idiv`）、
`VA 0x442188`（仇恨）、`VA 0x442193`（写回现金）、`VA 0x4421a3`（刷新）。

**公式汇总**
```
参与集合 P = { p | player[p].who_plays != 0,  0 <= p < num_players }
sum = Σ_{p∈P} player[p].cash                  （★ 32 位累加，溢出回绕）
avg = sum / |P|                               （idiv，向零截断）
∀p∈P:
    if player[p].cash > avg:                  ★ 2026 订正：是「高于均值」而不是「低于」
        update_hostility(p, 当前玩家, (player[p].cash - avg) / 100)   ; ★ 正数
    player[p].cash = avg
返回值 = 1（永不失败）
```
★ 通道 2 实证（`rich4-spec/tests/test_average_cards.py`，38/38）：
`update_hostility` 的第一个实参是**被拉低的人**、第三个是**正**增量；
`sum` 用 32 位寄存器累加（`0x7FFFFFFF×2+1 ⇒ −1 ⇒ avg = 0`），
差值 `sub edx, esi` 同样回绕（极端场景下 delta 会变成负数 −21474836）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| `|P| == 0` | `idiv ecx` **除零异常**（原版不检查；通道 2 已实测会崩） | `0x44214d` 无守卫 |
| 自己也在 `P` 中 | 自己的现金也被改成 `avg` | `0x442193` 无「排除自己」判定 |
| 玩家下标 ≥ `[0x499114]` | **不参与**（两道循环都以人数为界），即使 `who_plays != 0` | `0x44212c`、`0x442153` |
| 玩家现金恰好 == avg | 不调 `update_hostility`（`jge`） | `0x44216f` |
| 玩家现金 > avg | `delta = (cash−avg)/100`（**正**，向下游 `update_hostility` 传正值） | `0x442171`–`0x442188` |
| delta 算出来是 0（差额 < 100） | ★ **照样调用** `update_hostility(…, 0)`，不是「跳过」 | `0x44217f`（无 `test eax`） |
| 已破产/退场玩家 | 由 `who_plays != 0` 决定参与与否；**不判断现金正负** | `0x442133` |
| 现金之和或差值溢出 32 位 | 按补码回绕（`add esi` / `sub edx` 都无检查） | `0x44213c`、`0x442171` |
| 效果执行到一半 | 卡片**已被移除**，无法回滚（本卡无失败路径） | `0x4420e4` 在最早处 |

#### 防御卡查询

**无**。本卡不调用 `0x4413ad`（`has_card`），函数体内不存在任何 `call 0x4413ad`。

#### 未决

- `who_plays` 的取值枚举未定：本卡用 `!= 0` 表示「在局」，
  而 §1.3 的 AI 判定用 `& 6`、卡 2 用 `== 1` 表示人类。
  三者一致的解释是「`1` = 人类，`2`/`4` = 电脑系」，
  但**我没有找到写入 `who_plays` 的完整证据链**，故只陈述各处用到的判据。

`@source`：`VA 0x004420d8`（函数入口）、`VA 0x441343`、`VA 0x48123a`、
`VA 0x499114`、`VA 0x496b84`、`VA 0x40df69`、`VA 0x41d433`、`VA 0x44214d`。

---

### 卡 2 · 均貧卡

| 项 | 值 |
|---|---|
| 卡号 | 2 |
| 卡名 VA | `0x00466ac9`（`"均貧卡"`） |
| 函数 VA | `0x004421b4`（118 条指令，376 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **人类由模态对话框选；AI 由 `0x48be58[0]` 提供** |

#### 精确效果

1. **选目标**：
   ```asm
   004421b8  imul  eax, dword ptr [0x49910c], 0x68
   004421bf  cmp   byte ptr [eax + 0x496b7d], 1     ; who_plays == 1（人类）
   004421c6  jne   0x4421d4
   004421c8  push  0xe0c0410                        ; ★ 打包参数
   004421cd  call  0x446ae8                          ; 模态选人对话框 → eax = 目标
   004421d2  jmp   0x4421db
   004421d4  push  0
   004421d6  call  0x41e6f2                          ; = 0x48be58[0]（AI 自己的决策）
   004421db  add   esp, 4
   004421de  mov   ebx, eax
   004421e0  test  ebx, ebx
   004421e2  je    0x443069                          ; 目标 == 0 → 返回 0（失败）
   ```
   `0xe0c0410` 是传给对话框的打包参数（**其位域含义未决**）。
   `0x4421e0` 的 `test ebx,ebx / je` 意味着 **返回值 0 被当作「取消」**。
2. **弃卡**（在目标确定之后）：
   ```asm
   004421e8  push  2
   004421ea  mov   ecx, dword ptr [0x49910c]
   004421f0  push  ecx
   004421f1  call  0x441343                 ; remove_card(当前玩家, 2)
   ```
3. **说台词**：`player_say(当前玩家, 3, 台词表[character*90 + 1])`，
   `k=1` → `0x46928c` `"#0427朋友有\n通財之義！"`：
   ```asm
   0044221b  mov   edi, dword ptr [eax + 0x48123e]   ; ★ +4 = k=1
   00442221  push  edi
   00442222  push  3
   00442224  push  esi
   00442225  call  0x44ef41
   ```
4. **把「目标掩码」转成玩家下标**：
   ```asm
   0044222d  push  ebx
   0044222e  call  0x40d293
   00442233  mov   edi, eax
   00442235  add   esp, 4
   00442238  mov   ebp, eax
   ```
   `0x40d293` 实测语义（14 条指令，本文已解明）：
   ```asm
   0040d293  mov   edx, dword ptr [esp + 4]
   0040d297  test  dl, 0xff
   0040d29a  jne   0x40d2a2
   0040d29c  mov   eax, 0xffffffff      ; 低字节全 0 → 返回 -1
   0040d2a1  ret
   0040d2a2  xor   eax, eax
   0040d2a4  jmp   0x40d2ae
   0040d2a6  sar   edx, 1
   0040d2a8  inc   eax
   0040d2a9  cmp   eax, 8
   0040d2ac  jge   0x40d2b3
   0040d2ae  test  dl, 1
   0040d2b1  je    0x40d2a6
   0040d2b3  ret
   ```
   即 **`ctz(x)`（末尾 0 位数，上限 8；`x & 0xff == 0` 时返回 −1）**。
   **推论（A 级）**：选人对话框/AI 返回的是**玩家位掩码**（`1<<n`），
   本卡把它转成玩家下标 `n`。这解释了为什么「返回 0」＝取消：
   掩码 0 没有任何位被选中。
   AI 侧的写入点也印证了掩码约定：
   ```asm
   0041e856  mov   cl, byte ptr [esp + 4]   ; 选中的玩家下标
   0041e85a  mov   eax, 1
   0041e85f  shl   eax, cl                  ; eax = 1 << idx
   0041e861  or    ah, 0x80                 ; 再置位 15
   0041e864  mov   dword ptr [0x48be58], eax
   ```
   （`0x41e85f` 的 `1<<idx` 与 `0x40d293` 的 `ctz` 互为逆运算。）
5. **把自己的现金与目标的现金都改成两者之和的一半**：
   ```asm
   00442244  mov   edx, dword ptr [edx + 0x496b84]  ; 自己 cash
   0044224a  mov   esi, dword ptr [ecx + 0x496b84]  ; 目标 cash
   00442250  add   edx, esi
   00442252  mov   eax, edx
   00442254  sar   edx, 0x1f
   00442257  sub   eax, edx
   00442259  sar   eax, 1                            ; (a+b)/2，向零截断
   0044225b  mov   esi, eax
   0044228f  mov   dword ptr [eax + 0x496b84], esi   ; 自己 = 均值
   00442298  mov   dword ptr [ecx + 0x496b84], esi   ; 目标 = 均值
   ```
   **取整**：`(x + (x>>31)) >> 1` 即 `trunc(x/2)`，与 `idiv 2` 等价。
6. **仇恨调整**：仅当 `avg < 目标原现金` 时：
   `update_hostility(目标, 施卡者, (目标原现金 - avg)/100)`（**正数**）
   ```asm
   0044225d  mov   eax, dword ptr [ecx + 0x496b84]
   00442263  cmp   esi, eax
   00442265  jge   0x442288
   00442267  sub   edx, esi
   0044226b  mov   ecx, 0x64                          ; 100（十进制）
   00442275  idiv  ecx
   00442280  call  0x40df69
   ```
7. **双方现金同步动画**（仅当施卡者不是人类时）：
   ```asm
   0044229e  cmp   byte ptr [eax + 0x496b7d], 1
   004422a5  je    0x4422de                           ; 人类 → 跳过
   004422a7  push  0x64                               ; 100
   ...        （推入双方坐标）
   004422d6  call  0x40e669                           ; 动画
   ```
8. **刷新 + 受害者台词 + 统一收尾**：
   ```asm
   004422e4  push  esi
   004422e5  call  0x41d433                           ; 刷新
   00442309  mov   edi, dword ptr [eax + 0x48132e]    ; 台词表[target_char*90 + 61]
   0044230f  push  edi
   00442310  push  1                                  ; ★ 受害者槽位 = 1
   00442312  push  ebp
   00442313  call  0x44ef41
   0044231b  call  0x41d546                           ; 统一收尾
   00442320  jmp   0x443069
   00443069  mov   eax, ebx                           ; ★ 返回值 = **掩码**（未决 #3）
   0044306b  pop ebp / pop edi / pop esi / pop ebx
   0044306f  ret
   ```
   `0x48132e = 0x48123a + 0xF4`，`0xF4/4 = 61` → `"#0460喔！我的血汗錢！！"`。

`@source` `VA 0x4421bf`（人类判定）、`VA 0x4421cd`（选人框）、`VA 0x4421f1`（弃卡）、
`VA 0x44225b`（均值）、`VA 0x442280`（仇恨）、`VA 0x44228f` / `VA 0x442298`（写回）、
`VA 0x4422d6`（动画）、`VA 0x443069`（返回值）。

**公式汇总**
```
mask   = 人类 ? dialog(0xe0c0410) : ai_scratch[0]     ; 玩家位掩码（1<<n）
if mask == 0: return 0                                ; 卡不消耗
target = ctz(mask)                                    ; 0x40d293
remove_card(当前玩家, 2)
avg = trunc((cash[当前] + cash[target]) / 2)
if cash[target] > avg: update_hostility(target, 当前, (cash[target]-avg)/100)  ; 正数
cash[当前] = cash[target] = avg
返回值 = mask（非 0 → 成功）
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 选人对话框/AI 返回 0（未选任何玩家） | 视为取消 → 返回 0，**卡片不消耗** | `0x4421e2` |
| 目标是玩家 0（掩码 `1`） | **正常可选中**：`ctz(1)=0` → 下标 0 | `0x40d293`、`0x41e85f` |
| 掩码含多位 | `ctz` 只取**最低**的那一位，其余位被忽略 | `0x40d2a6` |
| 掩码低字节为 0 | `0x40d293` 返回 −1 → `edi=ebp=−1`（越界写玩家结构） | `0x40d29c` 无防护 |
| 目标现金 ≤ 均值 | 跳过仇恨调整，仍执行均值化 | `0x442265` |
| 现金之和为奇数 | `trunc(x/2)` 向零截断（现金非负时即向下取整） | `0x442257` |
| 现金之和溢出 32 位 | `add edx,esi` 无溢出检查，按补码回绕 | `0x442250` |
| 施卡者是人类 | 不播现金同步动画 | `0x4422a5` |
| 目标是自己 | **无判定**；日志上 `0x40df69` 会因 `a == b` 直接返回，现金仍被「均值化」，结果不变 | `0x40df73` |

> **与既有结论的矛盾**：`rich4-re` 的卡片实现把「均貧卡」描述为「与现金最少的玩家平分」，
> 但原版**目标完全由玩家/AI 指定**，函数体内没有任何「找最少者」的搜索
> （无遍历 `[0x499114]` 的循环）。本卡是「任选一人」而非「自动选最穷者」。

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。

#### 未决

1. `0xe0c0410` 的位域含义未决（同一打包常量在其它卡里还会出现；
   AI 侧写入 `0x48be58` 时会 `or ah,0x80`，暗示最高位是一个「来源标记」）。
2. 相对 `0x40e669`（动画）的参数含义未决。
3. 返回值是**掩码**而不是下标（`0x443069 mov eax,ebx`），调度器只判断非 0，
   因此该差别在本文可见范围内不影响行为；但复刻时不可把它当纯下标使用。

`@source`：`VA 0x004421b4`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x441343`、
`VA 0x48123e`、`VA 0x48132e`、`VA 0x40d293`、`VA 0x40df69`、`VA 0x40e669`、
`VA 0x41d433`、`VA 0x41d546`、`VA 0x41e779`（AI 侧掩码写入）、`VA 0x41e864`。

---

### 卡 3 · 購地卡

| 项 | 值 |
|---|---|
| 卡号 | 3 |
| 卡名 VA | `0x00466ad0`（`"購地卡"`） |
| 函数 VA | `0x00442325`（222 条指令，765 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 作用对象 | **自己当前所在格子的地产**（不是自选目标） |

#### 精确效果

**作用对象**由「当前玩家站位」决定，不弹选人框：
```asm
0044232e  imul  edx, dword ptr [0x49910c], 0x68
00442335  xor   ecx, ecx
00442337  mov   cx,  word ptr [edx + 0x496b74]   ; player.node_id(0x0c)，uint16
0044233e  mov   eax, ecx
00442340  shl   eax, 2
00442343  add   eax, ecx                          ; eax = node * 5
00442345  mov   ecx, dword ptr [0x498e80]
0044234b  mov   ax,  word ptr [ecx + eax*8 + 0x20] ; 格表[node*40 + 0x20]，uint16
00442350  and   eax, 0xffff
```
该 uint16 是**地产编号**，分两段：

| 值域 | 含义 | 结构基址 | 步长 | 下标 |
|---|---|---|---|---|
| `2001..3999`（`0x7d1..0xf9f`） | 住宅用地 | `[0x498e84]` | **`0x34`(52)** | `值 - 2000` |
| `4001..5999`（`0xfa1..0x176f`） | 商業用地 | `[0x498e88]` | **`0x38`(56)** | `值 - 4000` |
| 其它 | 无效 → 失败 | — | — | — |

```asm
00442355  cmp   eax, 0x7d0        ; 2000（十进制）
0044235a  jle   0x4424be
00442360  cmp   eax, 0xfa0        ; 4000（十进制）
00442365  jge   0x4424be
0044236b  sub   eax, 0x7d0
00442370  imul  eax, eax, 0x34
00442373  mov   ebx, dword ptr [0x498e84]
00442379  add   ebx, eax
```

`@source` `VA 0x44232e`–`VA 0x442350`（用 `player.node_id` 查格表取地产编号；
两段值域的分界 `0x7d0`=2000、`0xfa0`=4000）、`VA 0x498e80`（格表基址，步长 `0x28`）。

##### 分支 A：住宅用地（步长 `0x34`）

```asm
0044237b  mov   cl, byte ptr [ebx + 0x19]     ; owner（0 = 无主）
0044237e  test  cl, cl
00442380  je    0x442603                      ; 无主 → 失败
00442388  mov   al, cl
0044238a  mov   ecx, dword ptr [0x49910c]
00442390  inc   ecx
00442391  cmp   eax, ecx
00442393  je    0x442603                      ; ★ owner == 自己+1 → 失败（已是自己的）
00442399  movzx edi, byte ptr [ebx + 0x1a]    ; level
0044239d  xor   ecx, ecx
0044239f  mov   cx,  word ptr [ebx + 0x1e]    ; house_price
004423a3  imul  edi, ecx
004423a6  xor   ecx, ecx
004423a8  mov   cx,  word ptr [ebx + 0x1c]    ; land_price
004423ac  add   edi, ecx                      ; dr = level*house_price + land_price
004423ae  imul  edi, dword ptr [0x4990e8]     ; dr *= price_index
004423b5  cmp   edi, dword ptr [edx + 0x496b84]
004423bb  jg    0x4425f1                      ; dr > cash → 失败
004423c1  lea   esi, [eax - 1]                ; esi = owner - 1（1-based → 0-based）
```
**订价公式（住宅）**：
`price = (level * house_price + land_price) * price_index`（全部 32 位有符号乘法，
`imul` 无溢出检查）。`level`/`house_price`/`land_price` 见 `land-rent.md`
（`+0x1a`/`+0x1e`/`+0x1c`，字段偏移与本文一致，构成**独立交叉验证**）。

**转移与改主**：
```asm
00442437  mov   al, byte ptr [0x49910c]
0044243c  inc   al
0044243e  mov   byte ptr [ebx + 0x19], al     ; ★ owner = 当前玩家+1（写入 1-based）
00442441  push  0
00442443  call  0x40a4e1                      ; 重绘地产
0044246f  push  0
00442471  push  edi                           ; 金额
00442472  push  esi                           ; 收款人 = 原 owner-1
00442473  mov   eax, dword ptr [0x49910c]
00442478  push  eax                           ; 付款人 = 当前玩家
00442479  call  0x41d2c6                      ; pay_money(from, to, amount, 0)
004424a7  call  0x44ef41                      ; ★ **原地主**的反应台词（表 B 槽 62、槽位参数 1）
004424af  call  0x41d546                      ; 收尾重绘
```
**地契到期日**：
```asm
0044244b  mov   edx, dword ptr [0x499110]
00442453  je    0x44246f                      ; 索引为 0 → 不设置
00442455  mov   ecx, dword ptr [edx*4 + 0x4751f0]
0044245d  mov   ebp, dword ptr [0x497160]
00442463  push  ebp
00442464  call  0x4521cb
0044246c  mov   dword ptr [ebx + 0x30], eax   ; 住宅：flast @ +0x30
```

`@source` `VA 0x44232e`–`VA 0x442350`（取当前格与地产编号）、
`VA 0x44237b`–`VA 0x4423c1`（住宅判定与订价）、`VA 0x4423fb`（仇恨）、
`VA 0x44243e`（写 `owner`）、`VA 0x442479`（`pay_money`）、`VA 0x44246c`（`flast`）。

##### 分支 B：商業用地（步长 **`0x38`(56)**，本文新发现）

```asm
004424d4  sub   eax, 0xfa0
004424d9  shl   eax, 3
004424dc  mov   edx, eax
004424de  shl   eax, 3
004424e1  sub   eax, edx                      ; eax = idx * 56
004424e3  mov   ebx, dword ptr [0x498e88]     ; ★ 商業用地数组基址
004424e9  add   ebx, eax
004424eb  cmp   byte ptr [ebx + 0x19], 0      ; owner
004424ef  je    0x442603                      ; 无主 → 失败
004424f7  mov   al,  byte ptr [ebx + 0x19]
004424fa  mov   edx, dword ptr [0x49910c]
00442500  inc   edx
00442501  cmp   eax, edx
00442503  je    0x442603                      ; 已是自己的 → 失败
0044250b  mov   dl,  byte ptr [ebx + 0x1a]    ; level
00442510  mov   cx,  word ptr [ebx + 0x24]    ; 第二价
00442514  imul  edx, ecx
00442519  mov   cx,  word ptr [ebx + 0x22]    ; 第一价
0044251d  lea   edi, [ecx + edx]              ; dr = level*w[+0x24] + w[+0x22]
00442520  imul  edi, dword ptr [0x4990e8]
0044252e  cmp   edi, dword ptr [edx + 0x496b84]
00442534  jg    0x4425f1                      ; 现金不足 → 失败
0044255e  ...
004425b7  mov   byte ptr [ebx + 0x19], al     ; owner = 当前玩家+1
004425e1  call  0x4521cb
004425e9  mov   dword ptr [ebx + 0x34], eax   ; ★ 商業：flast @ +0x34（不是 +0x30）
```
**订价公式（商業，本文新结论）**：
`price = (level * w[+0x24] + w[+0x22]) * price_index`
⚠️ 商業用地的字段偏移（`+0x22`/`+0x24`/`+0x30`/`+0x34`）**目前只在本文有据**；
`land-rent.md` 未覆盖商業用地的结构。

`@source` `VA 0x4424d4`–`VA 0x442534`（商業分支的基址、判定与订价）、
`VA 0x4425e9`（`flast` 写在 `+0x34`）、`VA 0x498e88`（步长 `0x38`）。

**失败路径**：
```asm
004425f1  push  0x5dc                ; 1500
004425f6  push  0x46530c            ; "您的現金不足！"
004425fb  call  0x440cac            ; 提示
00442600  add   esp, 8
00442603  test  esi, esi
00442605  je    0x442618            ; esi==0 → 不弃卡，返回 0
00442607  push  3
00442609  mov   ecx, dword ptr [0x49910c]
0044260f  push  ecx
00442610  call  0x441343            ; remove_card(当前玩家, 3)
00442618  mov   eax, esi            ; 返回值 = esi（0 或 1）
```

**公式汇总**
```
node  = player[当前].node_id
code  = 格表[node*40 + 0x20]
住宅 (2000 < code < 4000):
    L = 住宅用地[code-2000]
    if L.owner == 0 or L.owner == 当前+1: return 0
    price = (L.level * L.house_price + L.land_price) * price_index
    if price > cash[当前]: 显示"您的現金不足以……"; return 0
    pay_money(当前, L.owner-1, price, 0)
    L.owner = 当前 + 1
    L.flast = add_deed_date(当前日期, 年限表[0x499110])
商業 (4000 < code < 6000):
    C = 商業用地[code-4000]
    if C.owner == 0 or C.owner == 当前+1: return 0
    price = (C.level * C[+0x24] + C[+0x22]) * price_index
    if price > cash[当前]: 同上失败
    pay_money(当前, C.owner-1, price, 0)
    C.owner = 当前 + 1
    C.flast = add_deed_date(当前日期, 年限表[0x499110])   ; 写在 +0x34
成功后 remove_card(当前, 3)；返回值 1
（★ 住宅/商業支在 `pay_money` 之后**共用**：say(原 owner-1, 1, 表B[ch][62]) → refresh_map()）
```

`@source` `VA 0x44232e`（取格子）、`VA 0x4423ae` / `VA 0x442520`（订价乘物价指数）、
`VA 0x44243e` / `VA 0x4425b7`（写 `owner`）、`VA 0x442479`（付款）、
`VA 0x4425f1`（失败提示）、`VA 0x442610`（弃卡）、`VA 0x442618`（返回值）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 格子无地产（值不在两段内） | 失败，返回 0，卡不消耗 | `0x44235a`/`0x442365` |
| 地产无主 | 失败（`owner == 0`） | `0x442380` |
| 地产已是自己的 | 失败（`owner == 当前+1`） | `0x442393` |
| 现金 < 价格 | 提示 `0x46530c`，失败 | `0x4425f1` |
| `price_index` 大 | `imul` 无溢出检查，按补码回绕 | `0x4423ae` |
| `price_index == 0` | 价格恒为 0 → 永远买得起 | `0x4073b4`（初值 1） |
| `0x499110 == 0` | **不写 `flast`**（保持旧值） | `0x442453` |
| 商業用地 `+0x34` | 住宅写 `+0x30`、商業写 `+0x34`，两者不同 | `0x44246c` vs `0x4425e9` |
| 同一张卡连续成功 | 不可能——成功后立即 `remove_card` | `0x442610` |
| **原地主反应台词** | `say(owner-1, 1, 表B[ch][62])`（槽位参数 1；两支共用） | `0x4424a7` |
| **收尾重绘** | `refresh_map()`（两支共用，`0x4425ec jmp 0x44246f`） | `0x4424af` |

> ⚠️ **与 `land-rent.md` 的矛盾（需要修正上游）**：该文档把 `owner` 描述为
> 「0 = 无主；否则为玩家下标」。本卡给出的是
> **`owner = 玩家下标 + 1`（1-based）**：
> ```asm
> 00442437  mov   al, byte ptr [0x49910c]
> 0044243c  inc   al
> 0044243e  mov   byte ptr [ebx + 0x19], al
> ```
> 并且「是不是自己的」判定也是 `owner == 当前+1`（`0x44238a`–`0x442393`）。
> **待办**：核对 `calculate_land_toll`（`VA 0x419744`）的调用方传的是 `player`
> 还是 `player+1`；两者必须一致，否则 `land-rent.md` 的租金归属判定有误。
> 本文标记为**待修正的上游疑点**，尚未在本文内下最终结论。

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。

#### 未决

1. `0x498e80` 格表的完整结构（步长 `0x28`(40)、字段 `+0x20`）未逐字段确认；
   本文只用到 `+0x20`。
2. 商業用地的 `+0x22`/`+0x24` 字段名（哪个是地价、哪个是房价）**未决** ——
   本文只按「`level * [+0x24] + [+0x22]`」如实记录，不猜名字。
3. 商業用地 `+0x30` 是什么（住宅的 `+0x30` 是 `flast`，商業的 `flast` 在 `+0x34`）**未决**。
4. `0x41d2c6` 的第 4 个参数（此卡传 0）含义未决。
5. 传给 `update_hostility` 的第 3 参数在本卡**按 8 字节 double 压栈**
   （见下），与 `0x40df69` 按 32 位整数读取不一致，**这是原版的不一致**，
   见「附注 A」。

`@source`（未决项对应）：`VA 0x498e80`（格表）、`VA 0x442510` / `VA 0x442519`
（商業用地两个价字段）、`VA 0x4425e9`（商業 `flast`）、`VA 0x44246c`（住宅 `flast`）、
`VA 0x442479`（`pay_money` 第 4 参）、`VA 0x4423f0`（double 压栈）。

#### 附注 A · 本卡与 `update_hostility` 的调用约定不一致（实测）

```asm
004423c9  imul  ecx, eax                 ; ecx = price_index * land_price
004423cc  mov   dword ptr [esp], ecx
004423cf  fild  dword ptr [esp]
004423d4  mov   al, byte ptr [ebx + 0x1a] ; level
004423d7  mov   dword ptr [esp + 4], eax
004423db  fild  word ptr [esp + 4]
004423df  fadd  dword ptr [0x46531c]      ; +2.0f
004423e5  fdiv  dword ptr [0x465320]      ; /5.0f
004423eb  fmulp st(1)                     ; = price_index*land_price * (level+2)/5
004423ed  sub   esp, 8
004423f0  fstp  qword ptr [esp]           ; ★ 8 字节 double 压栈
004423f3  mov   edx, dword ptr [0x49910c]
004423f9  push  edx
004423fa  push  esi
004423fb  call  0x40df69                  ; e8 69 bb fc ff，目标确认为 0x40df69
00442400  add   esp, 0x10                 ; 16 = 8 + 4 + 4
```
- 常量实测：`0x46531c` = **2.0f**，`0x465320` = **5.0f**。
  故意向值是 `(price_index*land_price) * (level + 2) / 5`。
- 但 `0x40df69` 用 `mov ecx, dword ptr [esp+0x14]` 读第 3 参，
  该位置是**这个 double 的低 32 位（尾数低位）**，不是浮点值。
  卡 1 与卡 8 则按 32 位整数传递同一个参数。
- 因此本卡的仇恨增量在实机上是「double 的低 32 位」这一无意义量。
  **这是原版行为**，复刻 1:1 时必须保留；**未决**：原作者意图。

★★ **2026-09-19（第 109 条）通道 2 已整支驱动并订正本节**（`rich4-spec/tests/test_land_auction_cards.py`，33/33）：

| 事实 | 实测 |
|---|---|
| 运算次序 | x87 默认精度控制字 `0x027F`（PC = **53 位 = double**）⇒ `fild 地价×物价` → `(等级+2)/5` → `fmulp` **每一步都舍成 double** |
| 三种写法的差别 | 地价 3/等级 0：逐步舍入 ⇒ **858993460**、精确乘积÷5 ⇒ 858993459（差 1 ulp）——**原版给前者** |
| 地价 1001/等级 2 | 低 32 位 = **+1717986919**（原版真的把垃圾值写进关系值）|
| 等级 3（`5/5` 整除）| 低 32 位 = 0（"看起来没副作用"）|
| 负的低 32 位 | 被 `0x40df83`「当前值 0 且增量为负 ⇒ 直接返回」挡掉（看不到）|

> ⚠️ **复刻侧原先把本卡当"空操作"**（理由："840 组真实参数下低 32 位恒为 0"）——
> 那个扫描只用了 1000/1500/…/8000 这些整齐地价，**机制上是错的**：
> 地价不是"整齐数"时（如 1001）低 32 位就是巨大的正数。
> 已改为照做（`cards/buy-land.ts` 的 `buyLandCardHostility()`，与拍賣卡/黑卡共用
> `rules/hostility.ts` 的 `misalignedDoubleInt()`）。

★ **本节还漏了两条指令**（本轮补上）：住宅支在 `pay_money` 之后还有
**原地主反应台词** `say(owner-1, 1, 表B[ch][62])`（`character=0` 时
`"#0461好大的膽子！！"`）与收尾 `refresh_map()`（`0x4424a7` / `0x4424af`）。
商業支经 `0x4425ec jmp 0x44246f` **共用**这两条。

`@source`：`VA 0x00442325`、`VA 0x40df69`、`VA 0x4423f0`（`dd 1c 24`）、
`VA 0x46531c`、`VA 0x465320`、`VA 0x46530c`、`VA 0x498e80`、`VA 0x498e84`、
`VA 0x498e88`、`VA 0x41d2c6`、`VA 0x4521cb`、`VA 0x4751f0`。

---

## 二·续、逐卡规格（卡 4–8）

### 卡 4 · 換地卡

| 项 | 值 |
|---|---|
| 卡号 | 4 |
| 卡名 VA | `0x00466ad7`（`"換地卡"`） |
| 函数 VA | `0x00442622`（398 条指令，1248 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | 站在住宅/商業用地上 → 选另一块**同类**地产（人类弹地图选框，AI 取 `0x48be58[0]`） |

#### 精确效果

整体结构与卡 5（換屋卡）几乎逐指令同构，只是「交换什么」不同：

| 卡 | 交换对象 |
|---|---|
| 卡 4 換地卡 | **交换两块地的 `owner`（`+0x19`）** |
| 卡 5 換屋卡 | **交换两块地的 `level`（`+0x1a`）与 `type`（`+0x18`）**，见 §卡 5 |

1. **取脚下格子**（与卡 3 同法）：
   ```asm
   00442634  mov   cx,  word ptr [edx + 0x496b74]   ; player.node_id
   00442642  mov   esi, dword ptr [0x498e80]
   00442648  mov   si,  word ptr [esi + eax*8 + 0x20]  ; 地产编号
   00442653  cmp   esi, 0x7d0        ; 2000
   00442659  jle   0x44288c                           ; → 商業分支
   0044265f  cmp   esi, 0xfa0        ; 4000
   00442665  jge   0x44288c
   ```
2. **选目标地产**（同一类别）：
   ```asm
   0044267c  cmp   byte ptr [edx + 0x496b7d], 1   ; who_plays == 1（人类）
   00442683  jne   0x442691
   00442685  push  0xe0c0202                       ; 住宅用
   0044268a  call  0x446ae8
   00442691  push  0
   00442693  call  0x41e6f2                        ; AI：0x48be58[0]
   0044269b  mov   ebx, eax
   0044269d  test  ebx, ebx
   0044269f  je    0x442ade                        ; 0 → 失败
   ```
   **对话框返回的是「地产编号」而不是玩家掩码**（与卡 2/6 不同）：
   ```asm
   004426d9  sub   ebx, 0x7d0        ; ★ 直接把返回值当地产编号用
   004426df  imul  ebx, ebx, 0x34
   004426e2  mov   esi, dword ptr [0x498e84]
   004426e8  add   esi, ebx          ; esi = 目标地产
   ```
   商業分支用 `0xe0c0204`、步长 `0x38`（`0x4428cc`、`0x442920`–`0x442936`）。
3. **把两块地的编号从大地图数组里抹掉**（各一次）：
   ```asm
   004426a5  push  0xffff
   004426aa  push  esi               ; 当前地产编号
   004426ab  push  0x2f440
   004426b0  mov   esi, dword ptr [0x474938]
   004426b6  push  esi
   004426b7  call  0x456c0a
   004426bf  push  0xffff
   004426c4  push  ebx               ; 目标地产编号
   004426c5  push  0x2f440
   004426d1  call  0x456c0a
   ```
   `0x456c0a` 本体是 **word 数组替换**（不是字符串操作）：
   ```asm
   00456c11  mov   esi, [ebp + 8]    ; src
   00456c14  mov   ecx, [ebp + 0xc]  ; count
   00456c17  mov   ebx, [ebp + 0x10] ; old
   00456c1a  mov   edx, [ebp + 0x14] ; new
   00456c20  lodsw ax, word ptr [esi]
   00456c22  cmp   ax, bx
   00456c25  jne   0x456c1d
   00456c27  mov   word ptr [esi - 2], dx
   ```
   **未决**：把这两块地产编号改成 `0xffff` 的用途（`0x2f440` = 193,600 项，
   与 440×440 的格子数吻合）。两次调用之后**没有**再写回去。
4. **交换 `owner`**：
   ```asm
   004426ec  mov   bl,  byte ptr [edi + 0x19]   ; bl = 当前地 owner
   004426f1  mov   al,  byte ptr [esi + 0x19]   ; al = 目标地 owner
   004426f4  mov   dword ptr [esp], eax
   004427bb  mov   byte ptr [esi + 0x19], bl    ; 目标地 = 当前地的 owner
   004427be  mov   al,  byte ptr [esp]
   004427c1  mov   byte ptr [edi + 0x19], al    ; 当前地 = 目标地的 owner
   ```
   ⚠️ **交换前不检查任一方是否有主**，也不检查是否为自己。
   `0x4427bb` 是**无条件执行**的：`0x4426f7`–`0x4427b3` 那一大段 `cmp`/`jb`
   **只用来决定播哪句台词**（两条对称分支都汇合到 `0x442774` 念 k=3），
   两分支在 `0x442c4c` 汇合后继续执行动画与交换。
5. **刷新与动画**：
   ```asm
   004427c4  push  0
   004427c6  call  0x40a4e1            ; 重绘地产
   004427ce  call  0x451985            ; 重绘地图块
   004427d3  push  1 / push 0 / push 0
   004427d9  call  0x41d476
   004427e1  push  0x1f4               ; 500（十进制）
   004427e6  call  0x45285e            ; 延时 500ms（内含消息泵，cs:[0x46246c] = WINMM!timeGetTime）
   ```
   随后按「哪一方是我的」择一玩家念 **k=63**（`0x481336` = `"#0462誰敢動我的地！"`），
   `player_say(那一方, 2, 台词)`（`0x44287a`）。
6. **弃卡与返回值**：
   ```asm
   00442ade  test  ebx, ebx      ; ebx = 对话框/AI 返回的地产编号
   00442ae0  je    0x442af8      ; 0 → 直接返回 0（卡不消耗）
   00442ae2  push  4
   00442ae4  mov   esi, dword ptr [0x49910c]
   00442aea  push  esi
   00442aeb  call  0x441343      ; remove_card(当前玩家, 4)
   00442af3  call  0x41d546
   00442af8  mov   eax, ebx      ; 返回值 = 地产编号（非 0 → 成功）
   ```

**公式汇总**
```
code = 格表[player.node_id * 0x28 + 0x20]
若 2000 < code < 4000  → 类别 = 住宅，步长 0x34，选框参数 0xe0c0202
若 4000 < code < 6000  → 类别 = 商業，步长 0x38，选框参数 0xe0c0204
否则 return 0
sel = 人类 ? dialog(参数) : ai_scratch[0]
若 sel == 0 → return 0
landA = 用地数组[code - 基值]       ; 脚下那块
landB = 用地数组[sel  - 基值]
把 [0x474938][0 .. 0x2f440) 中等于 code 与等于 sel 的 word 全部改为 0xffff
swap(landA.owner, landB.owner)
台词：择一玩家念 k=63
remove_card(当前玩家, 4)
return sel
```

`@source` `VA 0x442634`（取格）、`VA 0x44267c`（选目标）、`VA 0x4426d9`（编号换算）、
`VA 0x4426b7` / `VA 0x4426d1`（`0x456c0a`）、`VA 0x4427bb`（交换 owner）、
`VA 0x44287a`（台词）、`VA 0x442aeb`（弃卡）、`VA 0x442af8`（返回值）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 脚下无地产 | return 0，卡不消耗 | `0x442659`/`0x442665` |
| 选框返回 0 | return 0，卡不消耗 | `0x442ae0` |
| 脚下或目标地产**无主** | **照常交换**（会把 0 换给另一方） | `0x4427bb` 无 owner 判定 |
| 目标地产属于自己 | **照常交换**（自己和自己换 ≡ 无操作） | 同上 |
| 选框返回值超出该类别编号范围 | `sub ebx,0x7d0 / imul 0x34` **无边界检查**，越界读写 | `0x4426d9` 无守卫 |
| 人类玩家 | 不播 `0x40e669` 动画 | `0x44278d` |

> **与既有结论的差异**：本卡**不是**「与对手自动配对换地」，
> 而是「玩家自己在地图上点选一块同类别地产，与该地交换所有权」。

#### 防御卡查询

**无**。

#### 未决

1. `0x445e4d`（选框回调，经 `0x446ae8 → 0x4018e7` 调用）内部是否对可选项做了
   「必须是他人地产」之类的过滤 —— **无法从静态反汇编确定**
   （该函数不在已建图函数集中，仅通过函数指针被调用）。
   这直接决定「能否把无主地换过来」。
2. `0x474938` 所指数组的语义与 `0x2f440` 的项数含义（见上）。
3. `0xe0c0202` / `0xe0c0204` 的位域含义。

`@source` `VA 0x00442622`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x456c0a`、
`VA 0x474938`、`VA 0x40a4e1`、`VA 0x451985`、`VA 0x41d476`、`VA 0x45285e`、
`VA 0x481336`、`VA 0x441343`、`VA 0x41d546`。

---

### 卡 5 · 換屋卡

| 项 | 值 |
|---|---|
| 卡号 | 5 |
| 卡名 VA | `0x00466ade`（`"換屋卡"`） |
| 函数 VA | `0x00442b02`（346 条指令，1099 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | 同卡 4（同类地产，`0xe0c0202` / `0xe0c0204`） |

#### 精确效果

流程与卡 4 **逐段同构**（取格子 → 选目标 → 两次 `0x456c0a` → 动画 → 台词 → 弃卡），
唯一实质差别是「交换」这一步改成调用 `0x40b4f8`：

```asm
00442c89  call  0x451985
00442c8e  push  ebx              ; 先压「选中地产编号」
00442c8f  mov   ebx, dword ptr [esp + 0xc]   ; = 脚下的地产编号
00442c93  push  ebx
00442c94  call  0x40b4f8         ; swap_houses(脚下编号, 选中编号)
00442c99  add   esp, 8
```
（商業分支在 `0x442ea9`–`0x442eaf` 同法调用。）

**`0x40b4f8` 的实际动作**（本卡效果的核心，已逐指令确认）：
```asm
; 住宅分支（arg1 ∈ (2000,4000)）
0040b518  sub   eax, 0x7d0
0040b51d  imul  eax, eax, 0x34
0040b520  mov   esi, dword ptr [0x498e84]
0040b526  lea   ebx, [esi + eax]        ; ebx = 脚下那块
0040b529  mov   eax, dword ptr [esp + 0x4c]
0040b52d  sub   eax, 0x7d0
0040b535  add   esi, eax                ; esi = 选中那块
; —— 计算两块地图标的屏幕坐标差并按帧插值（见下）
; —— 动画结束后：
0040b6c5  mov   al, byte ptr [ebx + 0x1a]   ; 脚下.level
0040b6c8  mov   ah, byte ptr [esi + 0x1a]   ; 选中.level
0040b6cb  mov   byte ptr [ebx + 0x1a], ah   ; ★ 交换 level
0040b6ce  mov   byte ptr [esi + 0x1a], al
0040b6d1  mov   al, byte ptr [ebx + 0x18]   ; 脚下.type
0040b6d4  mov   ah, byte ptr [esi + 0x18]   ; 选中.type
0040b6d7  mov   byte ptr [ebx + 0x18], ah   ; ★ 交换 type
0040b6da  mov   byte ptr [esi + 0x18], al
```
**另有商業分支**（`0x40b6e2` 起：`sub eax,0xfa0`、步长 `0x38`、基址 `0x498e88`），
交换的仍是 `+0x1a` 与 `+0x18`（`0x40b89e`–`0x40b8b3`）。

**动画部分**（卡 4 与卡 5 的表现差异所在，参数已在汇编中确认）：
```asm
0040b537  movsx eax, word ptr [ebx]        ; 地产 +0x00 = 图标 x（int16）
0040b53e  movsx eax, word ptr [ebx + 2]    ; 地产 +0x02 = 图标 y（int16）
0040b573  fild  dword ptr [esp + 0x34]     ; st0 = dx²+dy²
0040b577  call  0x4582bc                   ; sqrt
0040b57f  fmul  dword ptr [0x4631d8]       ; 距离 × 系数
0040b585  fld1
0040b587  faddp st(1)                      ; +1
0040b589  call  0x457dbc                   ; 取整
0040b58e  fistp dword ptr [esp + 0x30]     ; = 帧数
0040b5e7  call  dword ptr cs:[0x46246c]    ; WINMM!timeGetTime（节流到 24ms/帧）
0040b862  cmp   eax, 0x18
0040b86e  push  edx / call 0x45285e        ; 补足帧间隔
```
即：两块地产图标沿直线**相向移动并交换位置**（`+0x00`/`+0x02` 也被插值改写，
最后在 `0x40b880`–`0x40b89a` 恢复），全程约「`sqrt(dx²+dy²) × [0x4631d8] + 1`」帧。
⚠️ 这段属**表现层**：汇编只给参数，**观感需实机确认**（见 `00-methodology.md` §三）。

**台词与弃卡**：
```asm
00442c3a  mov   edx, dword ptr [eax + 0x48124a]  ; k = 4 → "#0430給你面子\n才跟你換的喔！"
00442c44  call  0x44ef41                          ; player_say(施卡者, 3, 台词)
00442d1e  mov   esi, dword ptr [eax + 0x48133a]  ; k = 64 → "#0463太不給面子了！"
00442d28  call  0x44ef41                          ; player_say(另一方, 2, 台词)
00442f2d  push  5
00442f35  push  ebp
00442f36  call  0x441343                          ; remove_card(当前玩家, 5)
00442f43  mov   eax, ebx
```

`@source` `VA 0x442c94`（调用 `0x40b4f8`）、`VA 0x40b6c5`–`VA 0x40b6da`（交换 level/type）、
`VA 0x40b577` / `VA 0x4631d8`（动画帧数）、`VA 0x442c44` / `VA 0x442d28`（台词）、
`VA 0x442f36`（弃卡）、`VA 0x442f43`（返回值）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 脚下无地产 / 选框返回 0 | return 0，卡不消耗 | `0x442b3d`、`0x442b85` |
| 目标无主 或 是自己的 | **照常交换 level/type**（只影响台词选择） | `0x442bdf`–`0x442c49` |
| `level == 0`（空地） | **照常交换**（会把 0 级换给另一块） | `0x40b6c5` 无 level 判定 |
| 选框返回越界编号 | `sub 0x7d0 / imul 0x34` 无守卫 | `0x442bc2` |
| 两地产距离为 0 | 帧数 = `0×系数+1` = 1 | `0x40b573`–`0x40b58e` |

#### 防御卡查询

**无**。

#### 未决

1. `0x4631d8`（帧数系数，单精度）究竟控制「速度」还是「时长」：观感需实机确认。
2. 交换 `+0x18`（type）在两块**住宅**之间是恒等操作（两者都为 0），
   只在两块**商業**之间才有实际效果；其字段语义见 §十一。
3. `0x445e4d` 选框内部过滤规则（同卡 4）。

`@source` `VA 0x00442b02`、`VA 0x40b4f8`、`VA 0x442c94`、`VA 0x40b6c5`–`VA 0x40b6da`、
`VA 0x40b89e`–`VA 0x40b8b3`、`VA 0x4582bc`、`VA 0x4631d8`、`VA 0x45285e`、
`VA 0x48124a`、`VA 0x48133a`、`VA 0x441343`。

---

### 卡 6 · 轉向卡

| 项 | 值 |
|---|---|
| 卡号 | 6 |
| 卡名 VA | `0x00466ae5`（`"轉向卡"`） |
| 函数 VA | `0x00442f4d`（100 条指令，327 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **选一名玩家**（返回掩码，选框参数 `0xe0c0010`） |

#### 精确效果

```asm
00442f51  imul  eax, dword ptr [0x49910c], 0x68
00442f58  cmp   byte ptr [eax + 0x496b7d], 1     ; who_plays == 1
00442f5f  jne   0x442f6d
00442f61  push  0xe0c0010                        ; 选人框
00442f66  call  0x446ae8
00442f6d  push  0 / call 0x41e6f2                ; AI：0x48be58[0]
00442f79  test  ebx, ebx
00442f7b  je    0x443069                          ; 掩码 0 → return 0（卡不消耗）
00442f81  push  6
00442f8a  call  0x441343                          ; remove_card(当前玩家, 6)
00442f99  movzx esi, byte ptr [eax + 0x496b7b]    ; character
00442fb1  mov   edi, dword ptr [eax + 0x48124e]   ; k = 5 → "#0431向後轉！\n齊步走！！"
00442fc1  call  0x44ef41                          ; player_say(施卡者, 3, 台词)
00442fc9  push  ebx
00442fca  call  0x40d293                          ; target = ctz(掩码)
00442fd4  mov   esi, eax
00442fe4  je    0x443024                          ; 人类 → 跳过动画
00442fe6  ... 0x40e669(0, 施卡者坐标, 目标坐标, 100)
00443024  push  esi
00443025  call  0x40c78c                          ; ★ 真正生效：让目标转向
0044302d  cmp   esi, 4
00443030  jge   0x443069                          ; 目标下标 >= 4（神明/怪物）→ 直接返回
```

**`0x40c78c(player)` 的动作**：
```asm
0040c7af  imul  eax, edx, 0x68                    ; edx = 目标玩家
0040c7b2  mov   dl,  byte ptr [eax + 0x496b78]    ; player[0x10]（disasm.py 记作 direction）
0040c7b8  add   dl, 4
0040c7bb  and   dl, 7
0040c7be  mov   byte ptr [eax + 0x496b78], dl     ; ★ = (原值 + 4) & 7，即掉头
0040c7c6  mov   dx,  word ptr [eax + 0x496b74]    ; player[0x0c] = 当前节点
0040c7f4  mov   ax,  word ptr [ecx + eax*2 + 0x18]  ; 节点结构 +0x18+2i = 第 i 个邻接节点
0040c7fe  test  dword ptr [ecx + 0x24], esi         ; +0x24 的方向可用位（0x40000000 >> i）
0040c81e  cmp   edi, dword ptr [esp + 8]            ; 排除 player[0x0e] 当前值
0040c824  mov   word ptr [esp + ebx*2], ax          ; 收进候选数组
0040c834  call  0x456f2d                            ; PRNG
0040c83e  idiv  ebx                                 ; % 候选数
0040c844  mov   word ptr [esi + 0x496b76], ax       ; ★ player[0x0e] = 随机候选
0040c850  mov   word ptr [esi + 0x496b76], bx       ; 无候选 → 0
```
**结论**：`player[0x10]` 加 4 模 8（掉头），并把 `player[0x0e]` 重设为
「当前节点的某个随机邻接节点（排除原值，且排除标记为不可通行的方向）」。

★★ **2026-09-18（第 89 条）把上面那条未决结掉了 —— `+0x0e` 就是「来路」`last_node`**：

```asm
; 行走选岔 `0x40c14c..0x40c1b7`（与 0x40c78c 的候选循环**同构**）
0040c15e  mov  di, word ptr [edi + 0x496b76]   ; ★ 读它当"要排除的那一格"
0040c16b  cmp  edx, edi / je 跳过
0040c175  word [esp + esi*2] = dx ; esi++      ; 收候选
0040c17c  test esi,esi / jne 0x40c196
0040c187      mov di, word [edi + 0x496b76]     ; ★ 一个候选都没有时**退回它自己**
0040c196  call 0x456f2d / idiv esi / 写回 [+0x0e]
```

即：**岔路选择会排除 `+0x0e`**，所以掉头时把它摇成另一个邻居 = 让玩家"换个方向走回去"
⇒ 字段名 = `last_node_id`（`disasm.py` 原来的记法是对的，先前那句"更像下一个目标节点"作废）。
通道 2 证据：`tests/test_turn_around.py`（23/23）。

**后续台词**（只影响说话者）：
```asm
00443038  cmp   esi, edi                          ; 目标 == 当前玩家？
0044303a  jne   0x443070
00443057  mov   ecx, dword ptr [eax + 0x4812c6]   ; k = 35 → "#0456回去巡視一下！"
00443061  call  0x44ef41                          ; player_say(当前玩家, 0, 台词)
0044308c  mov   ebp, dword ptr [eax + 0x48133e]   ; k = 65 → "#0464好馬不吃\n回頭草！！"
00443096  jmp   0x442313                          ; ★ 复用卡 2 的收尾
```
`0x442313` 是卡 2 函数体内的共享收尾（`add esp,0xc; call 0x41d546; jmp 0x443069`），
`0x443069` 为 `mov eax, ebx` → **返回值为掩码**（非 0 → 成功）。

`@source` `VA 0x442f61`（选人框）、`VA 0x442f8a`（弃卡）、`VA 0x40c7be`（掉头）、
`VA 0x40c844`（重设 `player[0x0e]`）、`VA 0x443038` / `VA 0x443070`（台词）、
`VA 0x442313`（共享收尾）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 掩码为 0 | return 0，卡不消耗 | `0x442f7b` |
| 目标是自己 | 仍执行掉头，并改播 k=35 | `0x443038` |
| 目标是 `>= 4` 的伪玩家 | **卡已被移除**；`0x40c78c` 走另一套表（`0x498e2c`/`0x498e2e`/`0x498e31`），随后返回掩码（成功） | `0x40c85e` |
| 目标节点无可用邻居 | `player[0x0e] = 0` | `0x40c850` |
| 掩码含多位 | 只取 `ctz` 最低位对应的玩家 | `0x40d293` |

#### 防御卡查询

**无**。

#### 未决

1. ~~`player[0x0e]`（`VA 0x496b76`）的字段名与语义~~ **✅ 已结（第 89 条）**：
   它是**来路 `last_node`** —— 行走选岔 `0x40c15e`/`0x40c187` 排除它，掉头 `0x40c844` 重设它。
2. 节点结构 `[0x498e80] + node*0x28 + 0x24` 的方向位掩码位序
   （汇编用 `0x40000000 >> i` 逐位测试，i = 0..3）——
   **位序本身已定**（掩码 = `1 << (30 − slot)`，本引擎 `linkBlockedMask` 同式，
   `tests/test_turn_around.py` 用"封槽 0/1/3"实测过）；
   仍**未决**的是「槽号 → 哪个罗盘方向」这层对应（本引擎靠节点的
   `adjacentSlots` 建表，不依赖它）。
3. `player[0x10]` 的取值域（`& 7` → 0..7）。

`@source` `VA 0x00442f4d`、`VA 0x40c78c`、`VA 0x40d293`、`VA 0x446ae8`、
`VA 0x40e669`、`VA 0x48124e`、`VA 0x4812c6`、`VA 0x48133e`、`VA 0x442313`（共享收尾）。

---

### 卡 7 · 改建卡

| 项 | 值 |
|---|---|
| 卡号 | 7 |
| 卡名 VA | `0x00466aec`（`"改建卡"`） |
| 函数 VA | `0x0044309b`（116 条指令，400 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **无**：作用于自己**脚下那一格**的地产 |

#### 精确效果

```asm
004430a9  mov   bx,  word ptr [edx + 0x496b74]   ; player.node_id
004430bd  mov   ax,  word ptr [ebx + eax*8 + 0x20]
004430c7  cmp   eax, 0x7d0
004430cc  jle   0x443147                          ; → 商業分支
004430d2  cmp   eax, 0xfa0
004430d7  jge   0x443147
```

**分支 A：住宅用地（`0x498e84`，步长 `0x34`）**
```asm
004430e9  cmp   byte ptr [ebx + 0x1a], 0          ; level
004430ed  je    0x443202                          ; ★ level == 0（未开发）→ 失败
00443110  mov   ecx, dword ptr [eax + 0x481252]   ; k = 6 → "#0432不必謝我！！"
00443120  call  0x44ef41                          ; player_say(当前玩家, 3, 台词)
00443128  mov   ah, byte ptr [ebx + 0x18]         ; type
0044312b  xor   ah, 1                             ; ★ 翻转 bit0
0044312e  mov   byte ptr [ebx + 0x18], ah
00443131  je    0x44313d                          ; 翻转结果为 0 → 不做等级修正
00443133  cmp   byte ptr [ebx + 0x1a], 1
00443137  jbe   0x44313d
00443139  mov   byte ptr [ebx + 0x1a], 1          ; ★ 等级压到 1
0044313d  mov   esi, 1
```
即**住宅 ↔ 商業 互相改建**（`type` 语义见 `land-rent.md`：0 = 住宅、非 0 = 商業），
且**变成非 0 时把等级截到 1**。

**分支 B：商業用地（`0x498e88`，步长 `0x38`）**
```asm
00443174  cmp   byte ptr [ebx + 0x1a], 0
00443178  je    0x443202                          ; level == 0 → 失败
004431a0  mov   edi, dword ptr [eax + 0x481252]   ; 同一句台词（k=6）
004431aa  call  0x44ef41
004431b9  cmp   byte ptr [eax + 0x496b7d], 1      ; 人类？
004431c0  jne   0x4431da
004431c2  push  1
004431c4  call  0x440aac                          ; ★ 弹「請選擇設施類別」，返回类别或 -1
004431ce  cmp   eax, -1
004431d1  jne   0x4431e4
004431d3  xor   esi, esi                          ; -1 = 取消 → 失败
004431d5  jmp   0x4412de
004431da  push  0 / call 0x41e6f2                 ; AI：0x48be58[0]
004431e4  mov   byte ptr [ebx + 0x18], al         ; ★ +0x18 = 选择的设施类别
004431e7  mov   esi, 1
004431f1  je    0x4431f8                          ; 类别 == 0
004431f3  cmp   dh, 3
004431f6  jne   0x443202                          ; 非 0 且非 3 → 不改等级
004431f8  cmp   byte ptr [ebx + 0x1a], 1
004431fc  jbe   0x443202
004431fe  mov   byte ptr [ebx + 0x1a], 1          ; ★ 类别 0 或 3 时把等级压到 1
```
选框本体 `0x440aac`（77 条指令）打开模态框（回调 `0x43fae4`），
标题串 `0x465289` = `"請選擇設施類別"`：
```asm
00440b58  push  0x465289
00440b5f  call  0x44fabc              ; 绘制标题
00440b7d  push  0x43fae4
00440b82  call  0x4018e7              ; 模态消息循环
00440b9f  mov   eax, ebx              ; 返回值 = 用户选择
```

**收尾**：
```asm
00443202  test  esi, esi
00443204  je    0x4412de              ; 失败 → 返回 0，卡不消耗
0044320a  push  7
00443212  push  edi
00443213  call  0x441343              ; remove_card(当前玩家, 7)
0044321b  call  0x41d546
00443220  jmp   0x4412de             ; 返回 esi
```
`0x4412de` 是**卡 1 之前的公共 epilogue**（`mov eax,esi; pop edi; pop esi; pop ebx; ret`），
本篇多处共用（编译器尾合并）。

`@source` `VA 0x4430e9`（住宅 level 判定）、`VA 0x443128`–`VA 0x443139`（翻转 type 与压等级）、
`VA 0x443174`（商業 level 判定）、`VA 0x4431c4`（设施选框）、`VA 0x4431e4`–`VA 0x4431fe`、
`VA 0x440aac` / `VA 0x465289`（选框本体与标题串）、`VA 0x443213`（弃卡）。

★★ **2026-09-19（第 110 条）通道 2 已整支驱动**（`rich4-spec/tests/test_land_auction_cards.py`，44/44，
与该文件的卡 3/8 同一支）：上面两条分支逐条被机器复现 ——

- **住宅支**：`level == 0` ⇒ 返回 0 不扣卡；否则 `type ^= 1`，**翻转结果为非 0 时等级压到 1**
  （实测 `3 → 1`、`type 1 → 0` 时等级**保持** 3）；台词 = 表 B 槽 6
  `"#0432不必謝我！！"`；扣卡 `(cur,7)`、返回 1、收尾 `refresh_map()` 一次；
- **商業支**：人类走选類別窗 `0x440aac(1)`、电脑走 `0x41e6f2(0)`（实参实测 0）；
  **类别 0 / 3 时等级压到 1**（实测 3 → 1）、类别 4 时**保持** 3；
  选類別窗返回 −1（取消）⇒ 返回 0 且**不扣卡**；`level == 0` 时**连窗都不开**。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 脚下无地产 | return 0，卡不消耗 | `0x443202` |
| 地产 `level == 0`（未开发） | **失败**（两分支都判 level≠0） | `0x4430ed`、`0x443178` |
| 住宅改建后 level > 1 | level 截为 1 | `0x443139` |
| 商業选框取消（返回 −1） | return 0，卡不消耗 | `0x4431d3` |
| 商業选框返回 0 或 3 且 level > 1 | level 截为 1 | `0x4431fe` |
| 商業选框返回 1 或 2 | **不改 level** | `0x4431f6` |
| AI 玩家 | 直接取 `0x48be58[0]` 当设施类别，**不校验范围** | `0x4431da` |

> **与 `land-rent.md` 的交叉验证**：该文档的 `type`（`+0x18`）
> 「0 = 住宅，非 0 = 商業」在本卡得到**行为级确认** ——
> 改建卡正是靠 `xor 1` 在这两个状态间翻转，并配合 `calculate_land_toll`
> 的「住宅按等级租金 / 商業固定 2000」两条互斥分支。

#### 防御卡查询

**无**。

#### 未决

1. 商業用地 `+0x18` 的取值域：选框返回 0..3，但**「设施类别」到数值的映射未知**
   （`0x43fae4` 回调不在已建图函数集中）。
2. 「等级压到 1」的业务理由未知（推测与改建后建筑重置有关，**不作结论**）。
3. AI 经 `0x48be58[0]` 给出的类别值是否一定落在 0..3，无法静态确认。

`@source` `VA 0x0044309b`、`VA 0x440aac`、`VA 0x465289`、`VA 0x481252`、
`VA 0x443128`–`VA 0x443139`、`VA 0x4431e4`–`VA 0x4431fe`、`VA 0x4412de`（共享 epilogue）。

---

### 卡 8 · 拍賣卡

| 项 | 值 |
|---|---|
| 卡号 | 8 |
| 卡名 VA | `0x00466af3`（`"拍賣卡"`） |
| 函数 VA | `0x00443225`（203 条指令，667 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **无**：作用于自己**脚下那一格**的地产 |

#### 精确效果

1. 取脚下格子，分住宅（`0x34`）/ 商業（`0x38`）两支：
   ```asm
   00443237  mov   dx,  word ptr [eax + 0x496b74]
   0044324b  mov   di,  word ptr [edi + eax*8 + 0x20]
   00443256  cmp   edi, 0x7d0
   0044325c  jle   0x443375
   00443262  cmp   edi, 0xfa0
   00443268  jge   0x443375
   ```
2. **仇恨调整**（住宅支，`ebx = land.owner`；`owner != 0` 才做）：
   ```asm
   0044327f  mov   bl,  byte ptr [esi + 0x19]     ; owner
   00443282  test  ebx, ebx
   00443284  je    0x4432ce
   00443288  mov   ax,  word ptr [esi + 0x1c]     ; 住宅 land_price
   0044328c  mov   ebp, dword ptr [0x4990e8]      ; price_index
   00443292  imul  eax, ebp
   004432a4  fild  word ptr [esp + 4]             ; level
   004432a8  fadd  dword ptr [0x465324]           ; + 2.0f
   004432ae  fdiv  dword ptr [0x465328]           ; / 5.0f
   004432b4  fmulp st(1)
   004432b6  sub   esp, 8
   004432b9  fstp  qword ptr [esp]                ; ★ 又是 8 字节 double 压栈
   004432c1  push  [0x49910c]
   004432c5  push  eax                            ; owner - 1
   004432c6  call  0x40df69                       ; update_hostility
   ```
   与卡 3「附注 A」是**同一类调用约定不一致**（8 字节 double 对 32 位整数读）。
   商業支用 `[esi+0x22]` 作地价（`0x4433b0`），常量同为 `0x465324`/`0x465328`。
3. **台词**：
   ```asm
   004432ee  mov   ecx, dword ptr [eax + 0x481256]   ; k = 7 → "#0433漫天喊價\n就地還錢！"
   004432fe  call  0x44ef41                          ; player_say(施卡者, 3, 台词)
   00443306  test  ebx, ebx
   00443308  je    0x443345                          ; 无主 → 跳过受害者台词
   0044330a  mov   eax, dword ptr [0x49910c]
   0044330f  inc   eax
   00443310  cmp   ebx, eax
   00443312  je    0x443345                          ; 是自己的地 → 跳过
   00443333  mov   ecx, dword ptr [eax + 0x481346]   ; k = 67 → "#0466誰敢買試試看！"
   0044333d  call  0x44ef41                          ; player_say(owner-1, 1, 台词)
   ```
4. **拍卖**：
   ```asm
   00443345  push  1
   00443347  push  edi                  ; 地产编号
   00443348  mov   ebx, dword ptr [0x49910c]
   0044334e  push  ebx                  ; 当前玩家
   0044334f  call  0x43bde5             ; auction(当前玩家, 地产编号, 1)
   00443357  test  eax, eax
   00443359  jne   0x44336b             ; 成交（返回 1）→ 本卡不再改动
   0044335b  mov   byte ptr [esi + 0x19], 0   ; ★ 未成交 → owner = 0
   0044335f  mov   dword ptr [esi + 0x30], eax ; ★ flast = 0（住宅写 +0x30）
   00443363  call  0x40a4e1                    ; 重绘
   0044336b  mov   ebx, 1
   ```
   拍卖函数 `0x43bde5` 的返回初值在入口被清 0：
   ```asm
   0043bdef  xor   edx, edx
   0043bdf1  mov   dword ptr [esp + 0x88], edx    ; 返回值默认 0
   0043c804  mov   dword ptr [edx + 0x34], eax    ; 写入 flast（+0x34）
   0043c813  mov   byte ptr [eax + 0x19], dl      ; 写入成交者的 owner
   0043c855  call  0x41d2c6                       ; pay_money(得标者-1, …, 金额, 0)
   0043c85d  mov   dword ptr [esp + 0x88], 1      ; ★ 成交 → 返回 1
   ```
   即**成交时由拍卖函数自己完成过户与收付款**；返回 0 时由本卡把地「释放为无主」。
5. **收尾**：
   ```asm
   00443492  test  ebx, ebx
   00443494  je    0x4434b9
   00443496  push  8
   0044349f  call  0x441343             ; remove_card(当前玩家, 8)
   004434a9  mov   dword ptr [0x48be18], 0
   004434b1  call  0x41906a             ; 刷新
   004434b9  mov   eax, ebx
   ```

`@source` `VA 0x44324b`（取格）、`VA 0x443292` / `VA 0x4432c6`（仇恨，double 压栈）、
`VA 0x4432fe` / `VA 0x44333d`（台词）、`VA 0x44334f`（拍卖）、`VA 0x44335b`（释放地产）、
`VA 0x44349f`（弃卡）、`VA 0x43bde5` / `VA 0x43c85d`（拍卖成交）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 脚下无地产 | return 0（`ebx` 保持 0），卡不消耗 | `0x44322c`、`0x443492` |
| 地产**无主**（owner == 0） | 跳过仇恨调整与受害者台词，**仍照常进入拍卖** | `0x443284`、`0x443308` |
| 地产是自己的 | 跳过受害者台词，仍照常拍卖 | `0x443312` |
| 拍卖成交（返回 1） | 拍卖函数内部已改 `owner`/`flast` 并收付款 | `0x43c813`、`0x43c85d` |
| 拍卖未成交（返回 0） | `owner = 0`、`flast = 0`，地产回到无主 | `0x44335b` |
| 住宅 | `flast` 写 `+0x30` | `0x44335f` |
| 商業 | `flast` 写 `+0x34`（`0x44348a`），地价取 `+0x22`（`0x4433b0`） | 见上 |
| 仇恨增量 | 同卡 3，double 低 32 位被当整数读 | `0x4432c6` |

#### 防御卡查询

**无**。

#### 未决

1. `0x43bde5`（725 条指令的拍卖 UI）内部规则**未逐条拆解**：
   谁可出价、AI 出价策略、最低价、成交价构成。本文只确认两条契约：
   「返回 1 = 成交且内部已过户」「返回 0 = 由本卡释放为无主」，
   以及 `[0x48c498]` 保存被拍卖地产、`0x48c488` 保存成交价。
2. 拍卖返回值除 0/1 外是否还有第三态，未穷举其全部 `ret` 路径。

`@source` `VA 0x00443225`、`VA 0x43bde5`、`VA 0x43bdef`、`VA 0x43c813`、
`VA 0x43c855`、`VA 0x43c85d`、`VA 0x40df69`、`VA 0x465324`、`VA 0x465328`、
`VA 0x481256`、`VA 0x481346`、`VA 0x441343`、`VA 0x41906a`。

---

## 二·续、逐卡规格（卡 9–11）

### 卡 9 · 天使卡

| 项 | 值 |
|---|---|
| 卡号 | 9 |
| 卡名 VA | `0x00466b01`（`"天使卡"`） |
| 函数 VA | `0x004434c0`（154 条指令，544 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **选一块地产**（返回地产编号，选框参数 `0xe0c0006`） |

#### 精确效果

```asm
004434cc  imul  eax, dword ptr [0x49910c], 0x68
004434d3  cmp   byte ptr [eax + 0x496b7d], 1     ; who_plays == 1
004434dc  push  0xe0c0006
004434e1  call  0x446ae8                          ; 人类：选地产
004434e8  push  0 / call 0x41e6f2                 ; AI：0x48be58[0]
004434f2  mov   ebp, eax
004434f4  test  ebp, ebp
004434f6  je    0x4436d9                          ; 0 → return 0，卡不消耗
004434fc  push  9
00443505  call  0x441343                          ; remove_card(当前玩家, 9)
0044352f  mov   edi, dword ptr [eax + 0x48125a]   ; k = 8 → "#0434喔！\n哈利路亞！"
00443539  call  0x44ef41                          ; player_say(当前玩家, 3, 台词)
00443541  cmp   ebp, 0x7d0                        ; 2000
00443547  jle   0x443621                          ; → 商業分支
0044354d  cmp   ebp, 0xfa0                        ; 4000
00443553  jge   0x443621
```

**分支 A：住宅用地 → 提升「所有同名地产」的等级**
```asm
00443562  mov   ebx, dword ptr [0x498e84]
00443568  lea   edi, [ebx + eax]                  ; edi = 选中的那块
0044356b  mov   esi, 1
00443570  add   ebx, 0x34                         ; 逐块推进（步长 0x34）
00443573  cmp   esi, dword ptr [0x498e98]         ; num_lands
00443579  jg    0x4435e4
00443583  lea   eax, [edi + 4] / push eax
00443587  call  0x458370                          ; ★ strcmp：比较土地名
0044358f  test  eax, eax
00443591  jne   0x4435e1                          ; 名字不同 → 跳过
00443593  cmp   byte ptr [ebx + 0x1a], 5          ; level
00443597  jae   0x4435e1                          ; ★ level >= 5 → 跳过
00443599  push  0xffff / push (esi + 0x7d0) / push 0x2f440 / push [0x474938]
004435b1  call  0x456c0a                          ; 地图数组里把该地产编号改成 0xffff
004435b9  cmp   byte ptr [ebx + 0x18], 0          ; type
004435bd  je    0x4435cb
004435bf  cmp   byte ptr [ebx + 0x1a], 0
004435c3  jne   0x4435ce                          ; 非 0 级 → 不动
004435c5  mov   byte ptr [ebx + 0x1a], 1          ; 0 级 → 1 级
004435cb  inc   byte ptr [ebx + 0x1a]             ; ★ 住宅：level += 1
004435ce  cmp   byte ptr [ebx + 0x18], 0
004435d2  jne   0x4435e1
004435d4  cmp   byte ptr [ebx + 0x1a], 5
004435d8  jne   0x4435e1
004435da  mov   dword ptr [esp], 1                ; 标记「升到 5 级」
```
> **注意 `+0x18` 的两个方向不对称**：`type == 0`（住宅）时 `level += 1`；
> `type != 0`（已改建为商業）时**只有 `level == 0` 才置 1**，否则完全不动。
> 两条分支的跳转目标不同（`0x4435bd` 跳 `0x4435cb`、`0x4435c3` 跳 `0x4435ce`），
> 这是原版行为而不是笔误。

```asm
004435e4  push  0x64 / ... 0x40e669               ; 动画（住宅分支**不判断人机**）
00443617  call  0x451985                          ; 重绘地图块
0044361c  jmp   0x4436c0
004436c0  push  1 / push 0 / push 0
004436c6  call  0x41d476
004436ce  cmp   dword ptr [esp], 0
004436d2  je    0x4436d9
004436d4  call  0x40b0cd                          ; ★ 有地产升到 5 级 → 播放特效
004436d9  mov   eax, ebp
004436db  jmp   0x442afa                          ; 复用卡 4 的 epilogue
```

**分支 B：商業用地 → 只提升「选中那一块」**
```asm
00443639  lea   eax, [ebp - 0xfa0]
00443649  mov   ebx, dword ptr [0x498e88]         ; 步长 0x38
00443651  push  0xffff / push ebp / push 0x2f440 / push [0x474938]
00443663  call  0x456c0a
0044366b  cmp   byte ptr [eax + 0x496b7d], 1      ; 人类 → 跳过动画
00443679  je    0x4436a7
0044367b  ... 0x40e669
004436a7  call  0x451985
004436ac  push  ebp
004436ad  call  0x40b110                          ; ★ 升级该商業地产
004436b5  test  al, 0x80                           ; bit7 = 升到 5 级
004436b7  je    0x4436c0
004436b9  mov   dword ptr [esp], 1
```

**`0x40b110(code)` = 「升一级」（可复用的公共升级函数）**：
```asm
0040b138  cmp   byte ptr [ebx + 0x18], 0          ; 住宅支
0040b13e  cmp   byte ptr [ebx + 0x1a], 5
0040b142  jae   0x40b149
0040b144  mov   eax, 1                            ; type==0 且 level<5 → 可升
0040b161  mov   cl, byte ptr [ebx + 0x1a]
0040b164  inc   cl
0040b166  mov   byte ptr [ebx + 0x1a], cl
0040b169  cmp   cl, 5
0040b16e  or    al, 0x80                          ; 到达 5 级 → 返回值 bit7
0040b1a0  cmp   byte ptr [ebx + 0x1a], 0          ; 商業支：level == 0 时先选设施类别
0040b1e2  push  0 / call 0x440aac                 ; 人类：选设施类别（AI 走 0x456f2d 随机）
0040b1ec  mov   byte ptr [ebx + 0x18], al
0040b1f4  inc   byte ptr [ebx + 0x1a]
0040b201  cmp   cl, byte ptr [edx + 0x474940]     ; ★ 每类设施的最高等级表
0040b218  jne   0x40b21f
0040b21a  mov   eax, 0x81
```
`0x474940[+0x18]` 是**按设施类别的等级上限表**（本文新发现，与 §卡 7 的
「設施類別」配合使用）。

**`0x40b0cd()` = 播放特效**（升到 5 级时）：
```asm
0040b0d2  push  0x20b
0040b0de  call  0x450441              ; 载入资源
0040b0ea  push  -1 / push 0 / call 0x40829d
0040b0f4  push  0x5a / push 1 / push 0x28 / push 0 / push ebx
0040b0fd  call  0x45144f              ; 绘制/播放
```

**公式汇总**
```
code = 人类 ? dialog(0xe0c0006) : ai_scratch[0]
if code == 0: return 0
remove_card(当前玩家, 9)
player_say(当前玩家, 3, k=8)
if 2000 < code < 4000:                     # 住宅
    for i in 1..num_lands-1:               # ★ 遍历所有同名地产
        if strcmp(住宅用地[i].name, 住宅用地[code-2000].name) != 0: continue
        if 住宅用地[i].level >= 5: continue
        map_array: code_i -> 0xffff
        if 住宅用地[i].type == 0: 住宅用地[i].level += 1
        else:                     if level == 0: level = 1
        if type == 0 and level == 5: reached5 = 1
else if 4000 < code < 6000:                # 商業
    map_array: code -> 0xffff
    r = upgrade_land(code)                 # 0x40b110
    if r & 0x80: reached5 = 1
if reached5: play_effect()                 # 0x40b0cd
return code
```

`@source` `VA 0x4434dc`（选框）、`VA 0x443505`（弃卡）、`VA 0x44352f` / `VA 0x443539`（台词）、
`VA 0x443587`（`strcmp` 同名匹配）、`VA 0x443597`（5 级上限）、`VA 0x4435cb`（`level += 1`）、
`VA 0x4435e4`（动画）、`VA 0x4436ad`（`0x40b110`）、`VA 0x4436d4`（`0x40b0cd`）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 选框返回 0 | return 0，卡不消耗 | `0x4434f6` |
| `code` 不在两段值域内 | 两分支都不进，**卡已消耗**，但直接返回 `code`（成功） | `0x443547` / `0x443553` / `0x4436d9` |
| 同名地产有多块 | **全部升级**（住宅支）；商業支只升选中的一块 | `0x443587` |
| `level` 已达 5 | 跳过该块（住宅支） | `0x443597` |
| `type != 0` 且 `level >= 1` | **完全不改等级**（住宅支内的不对称行为） | `0x4435c3` |
| 人类玩家（住宅支） | **照样播动画**（无 `who_plays` 判断） | `0x4435e4` |
| 人类玩家（商業支） | 跳过动画 | `0x443679` |
| 住宅 `0x40b110` | **本卡不调用**（住宅支自己写循环） | 分支 A 无 `call 0x40b110` |
| 商業 `0x40b110` 内 `level == 0` | 人类弹「請選擇設施類別」，AI 用 PRNG 随机（`%4 + 1`） | `0x40b1e2` / `0x40b1d6` |

#### 防御卡查询

**无**（函数体内无 `call 0x4413ad`）。

#### 未决

1. `0x474940[+0x18]` 表的**完整内容与类别名称**（只确认它是「按设施类别的等级上限」）。
2. 住宅支「`type != 0` 时只补 0→1 而不 +1」的设计意图（如实记录，不解释）。
3. `0x40b0cd` 播放的具体资源（`push 0x20b` 是资源 id）与观感 —— 属表现层。

`@source` `VA 0x004434c0`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x441343`、
`VA 0x48125a`、`VA 0x458370`、`VA 0x498e98`、`VA 0x456c0a`、`VA 0x474938`、
`VA 0x40b110`、`VA 0x474940`、`VA 0x40b0cd`、`VA 0x442afa`（共享 epilogue）。

---

### 卡 10 · 惡魔卡

| 项 | 值 |
|---|---|
| 卡号 | 10 |
| 卡名 VA | `0x00466b08`（`"惡魔卡"`） |
| 函数 VA | `0x004436e0`（175 条指令，588 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **选一块地产**（返回地产编号，选框参数 `0xe0c0006`） |

#### 精确效果

1. 选框与弃卡同卡 9，台词槽位是 **0**（不是 3）：
   ```asm
   004436eb  cmp   byte ptr [eax + 0x496b7d], 1
   004436f4  push  0xe0c0006
   004436f9  call  0x446ae8
   0044370a  mov   ebp, eax
   0044370c  test  ebp, ebp
   0044370e  je    0x44558c                      ; 0 → 复用卡 27 的 epilogue 返回 0
   00443714  push  0xa
   0044371d  call  0x441343                      ; remove_card(当前玩家, 10)
   00443747  mov   esi, dword ptr [eax + 0x48125e]  ; k = 9 → "#0435嗚！\n邪惡的使者∼"
   0044374e  push  0
   00443751  call  0x44ef41                      ; ★ player_say(当前玩家, 0, 台词)
   ```
2. **住宅支**：遍历**所有同名地产**并「铲平」：
   ```asm
   0044377a  mov   ebx, dword ptr [0x498e84]
   00443780  lea   edi, [ebx + eax]              ; edi = 选中那块
   0044379b  call  0x458370                      ; strcmp（同名）
   004437a7  cmp   byte ptr [ebx + 0x19], 0      ; owner
   004437ab  je    0x4437d8                      ; 无主 → 跳过仇恨
   004437af  mov   dl, byte ptr [ebx + 0x1a]     ; level
   004437b2  add   edx, edx                      ; 2*level
   004437b9  sub   eax, edx                      ; eax = 15*(2*level) = 30*level
   004437bb  imul  eax, dword ptr [0x4990e8]     ; × price_index
   004437c2  push  eax                           ; delta（32 位整数，★ 不是 double）
   004437c8  push  [0x49910c]
   004437cf  push  eax(owner-1)
   004437d0  call  0x40df69                      ; update_hostility(owner-1, 施卡者, +30*level*price_index)
   004437d8  ... 0x456c0a([0x474938], 0x2f440, code_i, 0xffff)
   004437f8  mov   byte ptr [ebx + 0x1a], 0      ; ★ level = 0
   004437fc  mov   byte ptr [ebx + 0x18], 0      ; ★ type = 0
   ```
   **先算仇恨、再清零**（`0x4437d0` 在 `0x4437f8` 之前），delta 用的是原等级。
3. **商業支**：对**选中那一块**的商業记录（`0x498e88`，步长 `0x38`）：
   ```asm
   00443860  lea   eax, [ebp - 0xfa0]
   00443870  mov   ebx, dword ptr [0x498e88]
   004438c4  mov   byte ptr [ebx + 0x1a], 0
   004438c8  mov   byte ptr [ebx + 0x18], 0
   004438cc  call  0x40dffa                      ; ★ 商業被铲平时的连带效果
   ```
4. **收尾**：
   ```asm
   0044390d  call  0x451985
   00443912  jmp   0x44557e
   0044557e  push  1 / push 0 / push 0
   00445584  call  0x41d476
   0044558c  mov   eax, ebp                      ; 返回值 = 地产编号
   ```
   （`0x44557e` / `0x44558c` 位于卡 27 函数体内，是**跨函数共享的尾部**。）

**`0x40dffa()`（商業地产被铲平时的连带效果）**：
```asm
0040dffa  xor   edx, edx
0040dffc  cmp   edx, dword ptr [0x499114]              ; 玩家人数
0040e002  jge   0x40dfd9
0040e004  imul  eax, edx, 0x68
0040e007  cmp   byte ptr [eax + 0x496b7d], 0          ; who_plays
0040e00e  je    0x40e020
0040e010  cmp   byte ptr [eax + 0x496b9a], 0          ; player[0x32]
0040e017  je    0x40e020
0040e019  mov   byte ptr [eax + 0x496b9a], 0x80       ; ★ 置 0x80
```
即：对每个在局玩家，若其 `player[0x32]` 非 0，则置为 `0x80`。
★★ **通道 2 已差分**（2026 本轮，`tests/test_mutate_release.py` 7/7，直接 `call 0x40dffa`）：
它就是**拆除类改造尾部的「全场放人」**（无参数、遍历全体玩家）——
**在场**且 `+0x32 != 0` 的人一律置 `0x80`（释放挂起），出局者跳过、本来为 0 的跳过、
已置过再置一次仍 `0x80`（幂等）。六处调用点全在 `mutate_land`/`mutate_facility` 里：
`0x40ac33`/`0x40ac4d`/`0x40ac6c`（設施 mode 0 归零 / mode 1 / mode 2）、
`0x40ae0d`/`0x40ae58`（住宅同三种）。⇒ 语义是**一刀切**：拆掉任意一处旅馆/医院，
**全场**被关押者一起放出来（不看地点、也没有参数）。
复刻侧的落地见 `docs/gaps/README.md` §7.46（此前被误判为"表现层"）。

⚠️ `player+0x32`（`VA 0x496b9a`）的语义**未决**（`disasm.py` 记作 `days_in_hotel`，
但本函数只在「原本非 0」时才写入，与「住宿天数」的直觉不符；
`0x41c8b5` 处也有 `or byte [..+0x496b9a], 0x80`，说明 `0x80` 至少是一个位标志）。

**公式汇总**
```
code = 人类 ? dialog(0xe0c0006) : ai_scratch[0]
if code == 0: return 0
remove_card(当前玩家, 10)
player_say(当前玩家, 0, k=9)
if 2000 < code < 4000:
    for i in 1..num_lands-1:
        if strcmp(name_i, name_selected) != 0: continue
        if 住宅[i].owner != 0:
            update_hostility(owner-1, 当前, 30 * level_i * price_index)   # 正数
        map_array: code_i -> 0xffff
        住宅[i].level = 0 ; 住宅[i].type = 0
elif 4000 < code < 6000:
    if 商業[code-4000].owner != 0: update_hostility(... 同上 ...)
    map_array: code -> 0xffff
    商業.level = 0 ; 商業.type = 0
    after_commercial_destroyed()          # 0x40dffa
return code
```

`@source` `VA 0x4436f4`（选框）、`VA 0x44371d`（弃卡）、`VA 0x443747` / `VA 0x443751`（台词）、
`VA 0x4437b2`–`VA 0x4437d0`（仇恨公式）、`VA 0x4437f8`（清零）、`VA 0x4438cc`（`0x40dffa`）、
`VA 0x443912`（共享尾部）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 选框返回 0 | return 0，卡不消耗 | `0x44370e` |
| `code` 不在两段值域内 | 直接到收尾，返回 `code`（成功），卡已消耗 | `0x443848` / `0x44385a` |
| 地产无主 | 跳过仇恨调整，仍铲平 | `0x4437ab` |
| 同名地产有多块（住宅支） | **全部铲平**，并分别对各自 owner 计仇恨 | `0x44379b` |
| `level == 0` | delta = 0，`update_hostility` 累加 0（无实际变化） | `0x4437bb` |
| 仇恨 delta 为整数 | 与卡 3/卡 8 的 double 不一致 —— **同一函数在不同卡里参数类型不同** | `0x4437c2` vs `0x4423f0` |

#### 防御卡查询

**无**。

#### 未决

1. `player+0x32`（`VA 0x496b9a`）的语义（见上）。
2. 为什么住宅支遍历同名、而商業支只处理一块（原版如实如此，未解释）。

`@source` `VA 0x004436e0`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x441343`、`VA 0x48125e`、
`VA 0x458370`、`VA 0x4437b2`–`VA 0x4437d0`（仇恨公式）、`VA 0x4437f8`（清零）、
`VA 0x40dffa`、`VA 0x44557e` / `VA 0x44558c`（跨函数共享尾部）。

---

### 卡 11 · 怪獸卡

| 项 | 值 |
|---|---|
| 卡号 | 11 |
| 卡名 VA | `0x00466b0f`（`"怪獸卡"`） |
| 函数 VA | `0x00443917`（163 条指令，504 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查 |
| 目标选择 | **选一块地产**（返回地产编号，选框参数 `0xe0c0506`） |

#### 精确效果

```asm
00443922  cmp   byte ptr [eax + 0x496b7d], 1     ; who_plays == 1
0044392b  push  0xe0c0506
00443930  call  0x446ae8                          ; 人类：选地产
00443937  push  0 / call 0x41e6f2                 ; AI：0x48be58[0]
00443941  mov   esi, eax
00443943  test  esi, esi
00443945  je    0x443b08                          ; 0 → return 0
0044394b  push  0xb
00443954  call  0x441343                          ; remove_card(当前玩家, 11)
0044397f  mov   edi, dword ptr [ebx + 0x481262]   ; k = 10 → "#0436全部夷為\n平地！！"
0044398f  call  0x44ef41                          ; player_say(当前玩家, 0, 台词)
00443997  cmp   esi, 0xfa0
0044399d  jge   0x4439e8                          ; >= 4000 → 商業支
; 住宅支：esi < 4000，直接 esi-0x7d0（★ 无下界检查）
004439b0  mov   cl, byte ptr [ebx + 0x19]         ; owner
004439b3  test  cl, cl
004439b5  je    0x443a32                          ; 无主 → 跳过仇恨
004439bb  mov   dl, byte ptr [ebx + 0x1a]         ; level
004439c0  add   edx, edx
004439c9  imul  eax, dword ptr [0x4990e8]         ; 30*level*price_index（32 位整数）
004439dd  call  0x40df69                          ; update_hostility(owner-1, 施卡者, delta)
```
与卡 10 完全相同的 `30 × level × price_index` 公式（`0x4439bd`–`0x4439c9`）。

```asm
00443a32  movzx edi, byte ptr [ebx + 0x19]        ; owner（留给后面的台词判断）
00443a36  movsx ebp, word ptr [ebx]               ; 图标 x
00443a39  movsx ebx, word ptr [ebx + 2]           ; 图标 y
00443a4d  ... 0x40e669(0, 施卡者坐标, 目标坐标, 100)   ; 非人类才播
00443a76  call  0x41d476
00443a7e  push  2
00443a80  push  esi
00443a81  call  0x40ab4a                          ; ★ modify_land(地产编号, 2)
```
**`0x40ab4a(code, mode)` 是通用的地产修改器**（本文新发现）：
```asm
0040ab7e  cmp   ebx, 1
0040ab83  jbe   0x40abae                          ; mode == 1 → 完全拆除
0040ab85  cmp   ebx, 2
0040ab88  je    0x40abc8                          ; mode == 2 → 只拆建筑
0040ab8c  test  ebx, ebx
0040ab8e  jne   0x40abdb                          ; mode == 0 → 降一级
; —— mode 0（住宅）——
0040ab9b  mov   byte ptr [eax + 0x1a], dl         ; level -= 1
0040ab9e  cmp   byte ptr [eax + 0x18], 0
0040aba4  mov   byte ptr [eax + 0x1a], 0          ; 降到 0 时 type 也归零
0040aba8  mov   byte ptr [eax + 0x18], 0
; —— mode 1（住宅）——
0040abae  mov   byte ptr [eax + 0x19], 0          ; owner = 0
0040abb2  mov   byte ptr [eax + 0x1a], 0
0040abb6  mov   byte ptr [eax + 0x18], 0
0040abba  mov   dword ptr [eax + 0x30], edx       ; flast = 0
0040abbd  call  0x40a4e1                          ; 重绘
; —— mode 2（住宅）——
0040abc8  cmp   byte ptr [eax + 0x1a], 0
0040abcc  je    0x40abdb
0040abce  mov   byte ptr [eax + 0x1a], 0          ; ★ 只把 level / type 归零
0040abd2  mov   byte ptr [eax + 0x18], 0
```
商業支（`0x40abe1` 起，`0xfa0` / 步长 `0x38`）逻辑对称，且 mode 0/1/2 都会调用 `0x40dffa`。
返回值：`eax = 1` 表示确实改动了，`0` 表示无事发生。

**结论**：怪獸卡 = 对选中地产调用 `mode = 2`，即
**把该地的 `level` 与 `type` 归零（拆掉建筑），但保留 `owner` 与 `flast`**。
与卡 10 的差别：卡 10 清**所有同名地产**，卡 11 只清**选中的那一块**。

```asm
00443a89  ... 0x450441(0x48a0e4, 0x22d, 0, 0) → 0x45144f(...) → 释放
00443ac0  push  0x1f4
00443ac5  call  0x45285e                          ; 延时 500ms
00443acd  test  edi, edi
00443acf  je    0x443b03
00443af1  mov   ebp, dword ptr [ebx + 0x481352]   ; k = 70 → "#0467拆得還真乾淨∼"
00443afb  call  0x44ef41                          ; player_say(owner-1, 1, 台词)
00443b03  call  0x41d546                          ; 刷新
00443b08  mov   eax, esi                          ; 返回值 = 地产编号
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 选框返回 0 | return 0，卡不消耗 | `0x443945` |
| `code < 2000` | 走住宅支，`esi − 0x7d0` 为负 → **负下标越界读写**（原版无守卫） | `0x44399f` |
| `code >= 6000` | 商業支内**无上界检查**，同样可能越界 | `0x4439e8` 无上界 |
| 地产无主 | 跳过仇恨调整，仍拆建筑 | `0x4439b5` |
| `level == 0` | `0x40ab4a` 的 mode 2 直接返回 0（无改动），**卡仍消耗** | `0x40abcc` |
| 仇恨 delta | 32 位整数（**不是**卡 3/卡 8 那种 double） | `0x4439d0` |

#### 防御卡查询

**无**。

#### 未决

1. `0x40ab4a` 的 mode 取值全集：本卡用 2，卡 12（拆除卡）是否用 1 —— 待交叉核对
   （见 §卡 12）。
2. `0x450441(0x48a0e4, 0x22d, ...)` 的资源 id `0x22d` 对应哪份美术资源（表现层）。

`@source` `VA 0x00443917`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x441343`、
`VA 0x481262`、`VA 0x481352`、`VA 0x40df69`、`VA 0x40ab4a`、`VA 0x40e669`、
`VA 0x41d476`、`VA 0x41d546`、`VA 0x45285e`。

---

## 二·续、逐卡规格（卡 16–17）

### 卡 16 · 夢遊卡

| 项 | 值 |
|---|---|
| 卡号 | 16 |
| 卡名 VA | `0x00466b2b`（`"夢遊卡"`） |
| 函数 VA | `0x004441dc`（216 条指令，739 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ✅ **免罪卡(21) → 嫁禍卡(19)**；若目标==施卡者，再查 **復仇卡(18)** |
| 目标选择 | **选一名玩家**（返回掩码，选框参数 `0xe0c0710`） |

#### 精确效果

```asm
004441e0  imul  eax, dword ptr [0x49910c], 0x68
004441e7  cmp   byte ptr [eax + 0x496b7d], 1     ; who_plays == 1
004441f0  push  0xe0c0710
004441f5  call  0x446ae8                          ; 人类：选人
004441fc  push  0 / call 0x41e6f2                 ; AI：0x48be58[0]
00444206  mov   esi, eax
00444208  test  esi, esi
0044420a  je    0x4444b8                          ; 0 → return 0
00444210  push  0x10
00444219  call  0x441343                          ; remove_card(当前玩家, 16)
00444243  mov   edi, dword ptr [eax + 0x481276]   ; k = 15 → "#0441睡吧睡吧∼"
0044424d  call  0x44ef41                          ; player_say(当前玩家, 3, 台词)
00444255  push  esi
00444256  call  0x40d293                          ; target = ctz(掩码)
00444260  mov   ebp, eax
00444262  mov   ebx, eax
00444274  ... 0x40e669(0, 施卡者坐标, 目标坐标, 100)   ; 人类则跳过
004442b2  cmp   ebx, 4
004442b5  jge   0x44449b                          ; 目标 >= 4（伪玩家）→ 特殊分支
004442be  cmp   byte ptr [eax + 0x496b9e], 0      ; player[0x36]（days_sleeping）
004442c5  jne   0x44449b                          ; ★ 已在睡觉 → 不重复施加
004442cb  mov   edx, dword ptr [0x4990e8]          ; price_index
004442df  sub   eax, edx                           ; ★ 150 × price_index
004442ea  call  0x40df69                           ; update_hostility(target, 施卡者, 150×price_index)
```
**仇恨增量**：`edx = price_index; eax = edx; eax <<= 2; eax += edx; eax += eax;
edx = eax = 10p; eax <<= 4 = 160p; eax -= edx` ⇒ **`150 × price_index`**（32 位整数）。

**防御卡查询（本卡的核心）**：
```asm
004442f2  push  0x15                      ; 21 = 免罪卡
004442f4  push  ebx                       ; 目标
004442f5  call  0x4413ad                  ; has_card
004442fd  cmp   eax, 1
00444300  jne   0x444310
00444302  push  ebx
00444303  call  0x444bb2                  ; ★ 免罪卡生效 → 完全抵消
0044430b  jmp   0x4444b3                  ; 直接收尾（不再查嫁禍卡）
00444310  push  0x13                      ; 19 = 嫁禍卡
00444312  push  ebx
00444313  call  0x4413ad
0044431e  jne   0x444334
00444320  push  0
00444322  push  0
00444324  push  ebx
00444325  call  0x44476a                  ; ★ 嫁禍卡生效（mode 0）→ 新目标
00444330  je    0x444334                  ; -1 = 放弃 → 仍打原目标
00444332  mov   ebx, eax                  ; ★ 换成新目标
```

**施加效果**：
```asm
00444334  imul  edi, ebx, 0x68
00444356  call  0x44ef41                  ; player_say(目标, 1, 表 0x48089e[character*0x6C])
0044435e  cmp   ebx, dword ptr [0x49910c]
00444364  setne al
00444367  add   al, 4
00444369  mov   byte ptr [edi + 0x496b9f], al   ; ★ player[0x37] = 5 或 4（梦游天数）
00444372  add   byte ptr [eax + 0x496baa], 5    ; player[0x42] += 5
00444379  mov   dl, byte ptr [eax + 0x496b79]   ; player[0x11]（traffic_method）
0044437f  mov   byte ptr [eax + 0x496bce], dl   ; → player[0x66]（备份）
00444385  mov   dl, byte ptr [eax + 0x496b7a]   ; player[0x12]（ndices）
0044438b  mov   byte ptr [eax + 0x496bcf], dl   ; → player[0x67]（备份）
00444399  je    0x4443e6
0044439b  cmp   dh, 1
004443ae  inc   byte ptr [eax + 0x499160]       ; 15×player + 0x499160
004443ce  inc   byte ptr [eax + 0x499161]       ; 15×player + 0x499161
004443d9  mov   byte ptr [eax + 0x496b79], 0    ; traffic_method = 0
004443df  mov   byte ptr [eax + 0x496b7a], 1    ; ndices = 1
004443e7  call  0x40b93b                        ; ★ 启动梦游流程（476 条指令）
```
`player[0x37]` 是**梦游天数**：`5`（转移到别人身上）或 `4`（落在自己身上）。
`player[0x42]` 每次 `+= 5`。

**「最终目标 == 施卡者」时的第三个防御卡查询**：
```asm
004443ef  cmp   ebx, ebp                  ; ebx = 最终目标，ebp = 原始目标
004443f1  jne   0x4444b3
004443f7  push  0x12                      ; 18 = 復仇卡
004443f9  push  ebp
004443fa  call  0x4413ad
00444405  jne   0x4444b3
0044440b  push  ebp
0044440c  call  0x444691                  ; ★ 復仇卡生效
0044441d  mov   byte ptr [eax + 0x496b9f], 5   ; 施卡者自己梦游 5 天
```

**伪玩家（下标 ≥ 4）分支**：
```asm
0044449b  cmp   ebx, 4
0044449e  jl    0x4444b3
004444a0  shl   ebx, 4
004444a3  cmp   byte ptr [ebx + 0x498df4], 0
004444aa  jne   0x4444b3
004444ac  mov   byte ptr [ebx + 0x498df5], 5   ; 伪玩家表：设 5
```
**收尾**：`0x4444b3 call 0x41d546` → `mov eax, esi`（返回掩码）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 掩码 0 | return 0，卡不消耗 | `0x44420a` |
| 目标已在睡眠（`player[0x36] != 0`） | **跳过效果**（不施加、不计仇恨），但**卡已消耗** | `0x4442c5` |
| 目标下标 ≥ 4 | 走伪玩家表（`0x498df4`/`0x498df5`）设 5 | `0x4444ac` |
| 目标持有免罪卡 | 完全抵消；`jmp 0x4444b3` → **不再查嫁禍卡**（顺序固定、命中即止） | `0x44430b` |
| 目标持有嫁禍卡 | 改成打新目标；若放弃（−1）仍打原目标 | `0x444330` |
| **最终目标 == 原始目标** 且 **原始目标**持有復仇卡 | 施卡者自己（`[0x49910c]`）梦游 5 天 | `0x4443ef`、`0x44440c`、`0x444414` |
| 人类玩家 | 不播 `0x40e669` 动画 | `0x444272` |

#### 防御卡查询

**有**：`21 免罪卡 → 19 嫁禍卡`（顺序固定），另在「**最终目标 == 原始目标**」时查 `18 復仇卡`。
调用点：`0x4442f5`、`0x444313`、`0x4443fa`。

> ★ **本轮修正（原写"最终目标 == 施卡者"，是错的）**。逐指令追 `ebp`/`ebx` 的赋值链：
> ```asm
> 00444255  push  esi
> 00444256  call  0x40d293        ; esi = 目标选择掩码 → eax = 最低置位的目标下标
> 0044425b  mov   edx, eax
> 00444260  mov   ebp, eax        ; ★ ebp = 原始目标（玩牌时选定的那个）
> 00444262  mov   ebx, eax        ; ebx 初值同 = 原始目标
> ...
> 00444332  mov   ebx, eax        ; ★ 嫁禍卡改写后 ebx = 最终目标
> 004443ef  cmp   ebx, ebp        ; 比较的是「最终目标」与「原始目标」
> 004443f1  jne   0x4444b3        ; 被改写过 → 不查復仇卡
> 004443f9  push  ebp             ; 查的是**原始目标**是否持有復仇卡
> 004443fa  call  0x4413ad        ; playerHasCard(原始目标, 18)
> ```
> 而「谁梦游 5 天」由 `0x444414` 决定：`mov ecx,[0x49910c]`（= **当前玩家 = 施卡者**）
> → `imul eax,ecx,0x68` → `mov byte ptr [eax+0x496b9f],5`。
> 即**条件**是「最终目标 == 原始目标」，**效果**是「施卡者梦游 5 天」——
> 效果那句原本就写对了，**条件那句写错了**。
> 语义上也讲得通：目标**没有**用嫁禍卡改打别人（仍是原目标），且他持有復仇卡 ⇒ 反弹到施卡者身上。

★★ **2026-09-19（第 105 条）通道 2 已整支驱动**（`rich4-spec/tests/test_sleepwalk_card.py`，31/31）
—— 本卡是「防御卡编排」最复杂的一条链，本轮把整支（739 字节）在 Unicorn 里跑完，
13 个外部调用（选框 / 扣卡 / 台词 / 动画 / 敌意 / `has_card` / 免罪 / 嫁禍 / 復仇 / 梦游流程 / 刷新）
全部打桩记录，上面「精确效果」与「边界情况」的每一条都被机器复现：

- **编排顺序**：`选人 → 掩码 0 ⇒ return 0（不扣卡）→ remove_card(cur,16) → say(cur,3,k=15)
  → ctz → （仅 AI）0x40e669(0, cur.xy, tgt.xy, 0x64) → 敌意 → 免罪(21) → 嫁禍(19) → 施加
  → （最终==原始）復仇(18) → 伪玩家支 → 0x41d546() → return 掩码`。
- **动画只给 AI**：`who_plays == 1`（人类）这一支**不调** `0x40e669`；AI 那一支实测六个实参为
  `(0, cur.x, cur.y, tgt.x, tgt.y, 0x64)`（本卡读 `+0x08`/`+0x0a` 两个 word 作坐标）。
- **敌意在免罪/嫁禍判定之前**：持免罪卡的场合 `update_hostility` **照样被调用一次**
  ⇒ 效果被抵消、**仇恨已经记上**（此前 PRD 只说「完全抵消」，容易被读成「连仇恨也不记」——不是）。
- **命中即止**：免罪与嫁禍同时持有时**只走免罪**（`jmp 0x4444b3`），嫁禍处理函数一次都不调。
- **嫁禍改写后不查復仇**：`jia_ret=2` 且目标同时持 18 ⇒ `0x444691` **零次**；
  返回 −1（放弃）⇒ 仍打原目标，此时才进復仇查询。
- **復仇的两处细节**：① 反弹给**施卡者**（`[0x49910c]`）的天数**恒为 5**（不走「对自己 4 天」的式子）；
  ② 反弹时**施卡者的座驾也照同一套回收**（`traffic==2` ⇒ 道具 6 回池、`traffic=0`、`ndices=1`），
  且**原目标照样中招**（两边都是 5 天）—— 即復仇不是「抵消」，是「加罚施卡者」。
- **座驾回收的边界**：`traffic == 0x1f`（工程車）落在两个 `cmp` 之外 ⇒ **两个池都不回**，
  但仍会 `traffic = 0`、`ndices = 1`。
- **两道「不施加」闸**：① 玩家支 `+0x36 != 0`（已冬眠）⇒ 不记仇恨、不改天数（卡已消耗）；
  ② 伪玩家支 `[tgt*16+0x498df4] != 0`（即 `+0x0c` 冬眠中）⇒ 同样整段跳过。

> ★★ **本轮顺带解出替身记录字段族**（结掉冬眠卡那条「与 `player+0x36/+0x37/+0x38` 的对应关系未确认」）：
> 冬眠卡写 `+0x0c`（`0x498df4`）= 5、清 `+0x0d`；梦游卡**先查 `+0x0c`**，为 0 才写 `+0x0d`（`0x498df5`）= 5。
> 故 **`+0x0c` = 冬眠天数、`+0x0d` = 梦游天数**，语义上互为「不可叠加」——
> 已在冬眠的替身不会再被梦游覆盖，反之亦然（先到者说了算）。
> 复刻侧的 `SpecialActor.hibernating` / `sleepwalkDays` 与 `loaders/save.ts` 的 `+12` / `+13` 映射**正是这一对**，
> 本轮的实测把它们从「按存档布局推测」升级为「由两张卡的原版行为互证」。

复刻侧 `packages/core/src/cards/sleepwalk.ts` 与之逐条一致（本轮无代码改动）：
`days = (tgt != cur) + 4`、`+0x42 += 5`、`+0x66/+0x67` 备份、`TRAFFIC_TO_TOOL` 回收、
`applyDefensiveCards` 命中即消耗（与卡 16/17 共用）、復仇 `REVENGE_DAYS = 5` 且对施卡者
再走一次 `enterSleepwalk`（座驾回收含在内）、`applySleepwalkCardToActor` 的
`hibernating !== 0` 闸门。

#### 未决

1. `0x40b93b`（476 条指令的「启动梦游」流程）**未逐条拆解**：
   本文只确认它会被调用，以及调用前写入的字段。
2. ~~`15×player + 0x499160` / `+0x499161` 两个计数器的语义未决~~
   → **✅ 已结案（2026-09-19，通道 2 `tests/test_sleepwalk_card.py`）**：
   它们是**道具持有表的第 5、6 项**——基址 `0x49915b`、步长 15（`0x49915c` 起是 1-based 的道具 1），
   故 `0x499160` = 道具 **5 機車**、`0x499161` = 道具 **6 汽車**；本卡在 `traffic==1`/`==2` 时
   各自 `inc` 一次，实测与「座驾退还成道具」完全对应（`traffic==0x1f` 两个都不 `inc`）。
3. `0x48089e` 起、步长 `0x6C`(108) 的角色表**语义未决**
   （与台词表 `0x48123a`、步长 `0x168` 不是同一张表）。
4. ~~`player[0x42]`（`VA 0x496baa`）的语义未决。~~
   → **✅ 已结案**：它是**「本月倒楣天數」**（月结屏的读点 `0x4387bd` 直接给出中文字面
   `"本月倒楣天數："`，全 exe 共 6 处 8 位累加：`0x40d431` 消失 / `0x41a83f` 住宿 /
   `0x43d755` 監獄 / `0x43ee04` 醫院 / 冬眠卡 `0x4441a1` / 本卡 `0x444372`；月结清零 `0x439ede`）。
   详见 `rich4-spec/docs/systems/monthly.md` 与复刻侧 `rules/monthly.ts` 的
   `misfortuneDaysAfter`（**8 位回绕**，6 处全是 `add byte ptr`）。

`@source` `VA 0x004441dc`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x40d293`、`VA 0x441343`、
`VA 0x481276`、`VA 0x4442f5`、`VA 0x444313`、`VA 0x4443fa`、`VA 0x444bb2`、`VA 0x44476a`、
`VA 0x444691`、`VA 0x40df69`、`VA 0x40b93b`、`VA 0x499160`、`VA 0x498df4`、`VA 0x48089e`。

---

### 卡 17 · 陷害卡

| 项 | 值 |
|---|---|
| 卡号 | 17 |
| 卡名 VA | `0x00466b32`（`"陷害卡"`） |
| 函数 VA | `0x004444bf`（156 条指令，466 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ✅ **免罪卡(21) → 嫁禍卡(19)**；若 **最终目标 == 原始目标**，再查 **復仇卡(18)**（被查的是原始目标） |
| 目标选择 | **选一名玩家**（掩码，选框参数 `0xe0c0710`，与卡 16 相同） |

#### 精确效果

结构与卡 16 高度同构，差别在「施加什么效果」（入狱而非梦游）：

```asm
004444c3  imul  eax, dword ptr [0x49910c], 0x68
004444ca  cmp   byte ptr [eax + 0x496b7d], 1
004444d3  push  0xe0c0710
004444d8  call  0x446ae8                          ; 人类选人（AI：0x48be58[0]）
004444ed  je    0x44468a                          ; 掩码 0 → return 0
004444f3  push  0x11
004444fc  call  0x441343                          ; remove_card(当前玩家, 17)
00444524  mov   edi, dword ptr [eax + 0x48127a]   ; k = 16 → "#0442去吃牢飯吧！！"
00444534  call  0x44ef41                          ; player_say(当前玩家, 3, 台词)
0044453c  push  esi / call 0x40d293               ; target = ctz(掩码)
0044455b  ... 0x40e669(0, 施卡者坐标, 目标坐标, 100)   ; 非人类才播
00444599  cmp   ebx, 4
0044459c  jge   0x44467a                          ; 目标 >= 4 → 伪玩家
004445a2  mov   edx, dword ptr [0x4990e8]          ; ★ 与卡 16 相同的 150×price_index
004445c1  call  0x40df69
```

**防御卡查询与卡 16 完全相同**：
```asm
004445c9  push  0x15 / push ebx / call 0x4413ad    ; 21 免罪卡
004445da  call  0x444bb2                           ; 命中 → 0x444685 收尾（完全抵消）
004445e7  push  0x13 / push ebx / call 0x4413ad    ; 19 嫁禍卡
004445fc  call  0x44476a                           ; 命中 → 新目标
00444609  mov   ebx, eax
```

**施加效果：入狱**
```asm
0044460b  mov   eax, dword ptr [0x49910c]
00444610  cmp   ebx, eax
00444612  jne   0x444619
00444614  push  4                                  ; ★ 打到自己 → 4 天
00444616  push  eax
00444617  jmp   0x44461c
00444619  push  5                                  ; 打别人 → 5 天
0044461b  push  ebx
0044461c  call  0x43d593                           ; prison(玩家, 天数)
00444640  mov   edx, dword ptr [eax + 0x48136a]   ; k = 76 → "#0471哼！出獄後\n又是一條好漢！"
0044464a  call  0x44ef41                           ; player_say(目标, 1, 台词)
00444652  cmp   ebx, edi                           ; 最终目标 == 原目标？
00444654  jne   0x444685
00444656  push  0x12 / push edi / call 0x4413ad   ; 18 復仇卡
00444667  call  0x444691                           ; 復仇卡生效
0044466f  push  5 / push [0x49910c]
0044467d  call  0x43d593                           ; ★ 施卡者自己入狱 5 天
00444685  call  0x41d546
0044468a  mov   eax, esi                           ; 返回掩码
0044467a  push  5 / push ebx / call 0x43d593       ; 伪玩家分支
```

**`0x43d593(player, days)` 的三条实证**：
```asm
0043d597  mov   cl, byte ptr [esp + 0x14]          ; arg1 = 玩家下标
0043d5a0  shl   edi, cl                            ; edi = 0x100 << player（方向掩码）
0043d5a8  cmp   edx, 4
0043d5ab  jge   0x43d760                           ; >= 4 → 伪玩家路径
0043d65d  mov   byte ptr [ebx + 0x496b9c], al      ; ★ player[0x34] = arg2 = 天数
```
即 `player+0x34`（`VA 0x496b9c`）就是**入狱天数**。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 掩码 0 | return 0，卡不消耗 | `0x4444ed` |
| 目标持有免罪卡 | 完全抵消，`jmp 0x444685`（不再查嫁禍卡） | `0x4445e2` |
| 目标持有嫁禍卡 | 改打新目标（mode 0） | `0x4445fc` |
| **最终目标 == 原始目标** | 先按 **4 天**入狱；若**原始目标**还有復仇卡，再用 `0x43d593(current, 5)` 追加 **5 天** | `0x444652`、`0x444678` |
| 目标下标 ≥ 4 | 走 `0x44467a` → `0x43d593(伪玩家, 5)` | `0x44467a` |
| 人类玩家 | 不播 `0x40e669` 动画 | `0x444559` |

#### 防御卡查询

**有**：`21 免罪卡 → 19 嫁禍卡`，另有 `18 復仇卡`（**最终目标 == 原始目标**时，查原始目标）。
调用点：`0x4445cc`、`0x4445ea`、`0x444659`。

#### 未决

1. `0x43d593`（162 条指令）的完整流程（监狱位置、方向屏蔽、镜头移动）**未逐条拆解**；
   本文只确认它写 `player[0x34]` = 天数、并在 ≥ 4 时走另一套节点表。
2. 伪玩家（下标 ≥ 4）入狱的**含义**（`0x43d760` 分支）未确认。

`@source` `VA 0x004444bf`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x40d293`、`VA 0x441343`、
`VA 0x48127a`、`VA 0x48136a`、`VA 0x4445cc`、`VA 0x4445ea`、`VA 0x444659`、
`VA 0x444bb2`、`VA 0x44476a`、`VA 0x444691`、`VA 0x43d593`、`VA 0x496b9c`、`VA 0x40df69`。

---

## 二·续、防御卡机制总览（卡 18–21）

> **本节是全文最重要的结构性结论之一。**
> 復仇(18)/嫁禍(19)/免費(20)/免罪(21) **都不能主动使用**
> （`card_functions[18..21] = 0x004420d5`，AI 表 `0x475324[18..21] = 0x0041e6e3`，
> 两处都是 `xor eax,eax; ret`），它们的真实机制是
> **「有害卡命中目标时，由施害卡先查目标是否持有防御卡」**。

### 4 个共用的「防御卡生效处理」函数

| 卡 | 处理函数 VA | 作用 | 返回值 |
|---|---|---|---|
| 21 免罪卡 | `0x00444bb2(target)` | 展示 `"%s\n\n免罪卡生效！"`（`0x46539d`）+ 卡牌弹窗，`remove_card(target, 21)`，念 k=20 | `1` |
| 19 嫁禍卡 | `0x0044476a(target, mode, ?)` | 展示 `"%s\n\n嫁禍卡生效！"`（`0x46533d`）+ 卡牌弹窗，选一个新目标，`remove_card`（在弹窗流程内） | **新目标下标**，拒绝则 `-1` |
| 18 復仇卡 | `0x00444691(player)` | 展示 `"%s\n\n復仇卡生效！"`（`0x46532c`）+ 卡牌弹窗，`remove_card(player, 18)`，念 k=17 + 对施害者念 k=77 | `1` |
| 20 免費卡 | `0x00444a60(target, payer, amount)` | 展示 `"是否使用免費卡？"`（`0x465388`）+ 卡牌弹窗，`remove_card(target, 20)`，念 k=19 | `1` = 用卡，`0` = 不用 |

三者共同的收尾在 `0x444753`（`call 0x44ef41` → `mov eax,1` → 返回），
`0x444691` 的**函数体与它连成一片**（`0x444691` 结尾是 fallthrough，
所以 `0x444bb2` 直接 `jmp 0x444753` 复用）。

### 共享的「免罪 → 嫁禍」二级判定 `0x441210(player)`

这是全工程唯一的**通用**防御卡查询封装：
```asm
00441212  mov   esi, dword ptr [esp + 0xc]   ; player
00441216  push  0x15                          ; 21 = 免罪卡
00441218  push  esi
00441219  call  0x4413ad                      ; has_card
00441221  cmp   eax, 1
00441224  jne   0x441237
00441226  push  esi
00441227  call  0x444bb2                      ; 免罪卡生效
0044122f  mov   eax, 0xffffffff               ; ★ 返回 -1 = 「被免罪卡挡下」
00441236  ret
00441237  mov   ebx, esi
00441239  push  0x13                          ; 19 = 嫁禍卡
0044123b  push  esi
0044123c  call  0x4413ad
00441247  jne   0x44125d
00441249  push  0
0044124b  push  0
0044124d  push  esi
0044124e  call  0x44476a                      ; 嫁禍卡生效 → 新目标
00441256  cmp   eax, -1
00441259  je    0x44125d
0044125b  mov   ebx, eax
0044125d  mov   eax, ebx                      ; 返回新目标（无卡则原样返回）
```
**调用者（`0x441210`）**：`0x44b352`、`0x44c6c5`、`0x44c7d7`、`0x44cd41`、`0x44d8a9`
（全部落在 `0x44bxxx`–`0x44dxxx` 的**新闻/命运事件**区），说明免罪/嫁禍
**也能挡事件**，不只是挡卡。⚠️ 事件侧的具体触发条件**未决**（超出本文范围）。

### 防御卡查询矩阵（实测，全部来自 `call 0x4413ad` 的紧邻上文）

| 发起方 | 查询顺序 | 命中后 | @source |
|---|---|---|---|
| 卡 16 夢遊卡 | 21 免罪 → 19 嫁禍 | 免罪：中止；嫁禍：改打新目标 | `0x4442f5`、`0x444313` |
| 卡 16（目标==自己时） | 18 復仇 | 自己也一起中招 | `0x4443fa` |
| 卡 17 陷害卡 | 21 免罪 → 19 嫁禍 | 同上 | `0x4445cc`、`0x4445ea` |
| 卡 17（目标==自己时） | 18 復仇 | 施害者一起入狱 | `0x444659` |
| 卡 26 查稅卡 | 20 免費 → 19 嫁禍（仅当税额 > 2000） | 免費：免缴；嫁禍：改由新目标缴 | `0x445310`、`0x445341` |
| 过路费（`0x419b32`） | 20 免費 → 19 嫁禍 | 同上 | `0x419e3d`、`0x419ea3` |
| 事件 `0x41a3be` / `0x41abde` | 20 免費 → 19 嫁禍 | 同上 | `0x41a611`、`0x41a673`、`0x41af0f`、`0x41af65` |
| 事件族 `0x44b25b`/`0x44c5d8`/`0x44c6ed`/`0x44cc53`/`0x44d783` | 走 `0x441210`（21 → 19） | — | 见上 |
| AI 版夢遊/陷害（`0x41fe6f`） | 18 復仇 | — | `0x41ff17` |

> **与背景事实的一致性**：「梦游卡(16) 查 免罪卡(21) → 嫁祸卡(19)」✅ 完全吻合；
> 「查税卡(26) 查 免费卡(20)」✅ 吻合，且**我在同处还发现第二个查询：嫁祸卡(19)**（当税额 > 2000）。

**穷举交叉验证（本节最关键的一条）**：对全工程所有已建图函数扫描
`call 0x4413ad`（`has_card`）的调用点，**共 18 处**，全部列在上面这张表里。
因此可以下一个**封口结论**：

> **只有卡 16、卡 17、卡 26 这三张卡会查询防御卡。**
> 卡 3/4/5/6/7/8/9/10/11/12/13/14/15/22/23/24/25/27/28/29/30
> **一律不查**（函数体内不存在 `call 0x4413ad`）。
> 另有 2 处是通用封装 `0x441210` 内部的查询、5 处属于过路费/事件系统。

`@source` `VA 0x4413ad`（`has_card` 本体）、18 个调用点见表内 @source 列；
穷举方法见 §0.2 第 4 条。

### 卡 18 · 復仇卡

| 项 | 值 |
|---|---|
| 卡号 | 18 |
| 卡名 VA | `0x00466b39`（`"復仇卡"`） |
| 函数 VA | **`0x004420d5`（2 字节空桩 `xor eax,eax; ret`）** |
| 可否主动使用 | ❌ **不可**（`card_functions[18]` 与 AI 表 `0x475324[18]` 都是空桩） |
| 查防御卡 | 它**本身**就是防御卡：被 `has_card(玩家, 18)` 查询 |
| 触发条件 | 有害卡最终仍落在**施卡者自己**身上时（梦游/陷害的「目标==自己」分支） |

#### 精确效果

**不可主动使用**（返回 0 → 调度器判为失败，卡不消耗）。

触发时的实际处理函数 `0x444691(player)`（`player` = 受害的施卡者）：
```asm
004446c0  mov   ecx, dword ptr [ebx + 0x496b68]   ; player 姓名指针
004446c7  push  0x46532c                          ; "%s\n\n復仇卡生效！"
004446d1  call  0x457110                          ; sprintf
004446dc  push  0x12                              ; 18 = 復仇卡
004446de  call  0x441f73                          ; 卡牌弹窗
004446e6  push  0x12
004446f0  call  0x441343                          ; ★ 消耗该玩家的復仇卡
00444715  mov   edi, dword ptr [eax + 0x48127e]   ; k = 17 → "#0443拖你一起\n下水！！"
0044471f  call  0x44ef41                          ; player_say(受害施卡者, 0, 台词)
00444749  mov   ecx, dword ptr [eax + 0x48136e]   ; k = 77 → "#0472唉！\n損人不利己∼"
00444752  push  edx([0x49910c])                   ; 施害者
00444753  call  0x44ef41                          ; player_say(施害者, 2, 台词)
0044475b  mov   eax, 1
```
⚠️ **`0x444691` 只负责「展示 + 消耗卡 + 台词」，它自己并不施加惩罚**；
惩罚由**调用方**紧接其后施加：
- 卡 16（`0x4440c`）：`0x444691(ebp)` 后把 `player[当前+0x37] = 5`（梦游 5 天）
- 卡 17（`0x444667`）：`0x444691(edi)` 后 `0x43d593(当前玩家, 5)`（入狱 5 天）

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 主动使用 | `0x4420d5` 直接返回 0 → 提示失败，卡不消耗 | `0x4420d5` |
| AI 主动使用 | AI 表同样指向 `0x41e6e3` 空桩 | `0x475324 + 4*18` |
| 受害施卡者没有復仇卡 | 整段跳过，惩罚照旧施加 | `0x444402`–`0x444405` |
| 有復仇卡 | 卡被移除，施害者被追加同样的惩罚 | `0x4446f0` |

#### 防御卡查询

**它自身不被查询，而是被查询的一方**：`push 0x12; push <玩家>; call 0x4413ad`
见 `0x4443fa`（卡 16）、`0x444659`（卡 17）、`0x41ff17`（AI 版）。

#### 未决

1. 「復仇」是否覆盖除梦游/陷害之外的其它自伤场景 —— 目前只找到两处（卡 16、卡 17）。
2. `0x41ff17`（AI 版）里查询復仇卡之后的处理是否与卡 16/17 相同 —— **未逐条拆解**。

`@source` `VA 0x004420d5`、`VA 0x444691`、`VA 0x444753`（共享收尾）、
`VA 0x4443fa`、`VA 0x444659`、`VA 0x41ff17`、`VA 0x48127e`、`VA 0x48136e`、`VA 0x46532c`。

---

### 卡 19 · 嫁禍卡

| 项 | 值 |
|---|---|
| 卡号 | 19 |
| 卡名 VA | `0x00466b40`（`"嫁禍卡"`） |
| 函数 VA | **`0x004420d5`（2 字节空桩）** |
| 可否主动使用 | ❌ **不可** |
| 查防御卡 | 被 `has_card(玩家, 19)` 查询（共 7 处调用点） |
| 触发条件 | 成为梦游(16)/陷害(17)/查税(26)/过路费/事件的受害者时 |

#### 精确效果

处理函数 `0x0044476a(target, mode, ?)`（231 条指令）：
```asm
00444774  mov   edi, dword ptr [esp + 0xb4]     ; arg1 = 原受害者
0044477b  mov   ebx, 0xffffffff                 ; 默认返回 -1（放弃嫁禍）
004447a1  cmp   byte ptr [esi + 0x496b7d], 1    ; 人类？
004447a8  jne   0x4448b0                        ; → AI 路径
; —— 人类路径：列出除自己外的所有在局玩家 ——
004447c8  cmp   ebx, edi
004447ca  je    0x4447d4                        ; 排除自己
004447cc  mov   byte ptr [esp + esi + 0x9c], bl ; 候选表
004447da  cmp   esi, 1
004447dd  jne   0x44486d                        ; 只有 1 个候选 → 自动选中
004447ea  push  0x46533d                        ; "%s\n\n嫁禍卡生效！"
00444834  push  0x46534e                        ; "是否嫁禍給%s？"
00444849  call  0x440ba8                        ; 是/否 对话框
00444851  cmp   eax, esi
00444853  jne   0x444863                        ; 选「否」→ -1
00444855  xor   ebx, ebx
00444857  mov   bl, byte ptr [esp + 0x9c]
0044485e  jmp   0x4449e7                        ; → 返回选中的玩家
; —— 多候选 ——
00444893  push  0x46535d                        ; "請選擇嫁禍對象..."
004448a1  call  0x440e1a                        ; 玩家选择框
; —— AI 路径 ——
004448b1  call  0x40d2d3                        ; 依 hostility 选目标（策略 A）
004448c0  call  0x40d31c                        ; 依 hostility 选目标（策略 B）
004448ca  mov   edx, dword ptr [esp + 0xb8]     ; arg2 = mode（0/1/2）
```
`arg2`（mode）在 AI 路径里分三支（`0x4448ef`、`0x4448fc`、`0x444934`），
分别对应不同的「选谁背锅」策略。实测到的调用取值：

| 调用方 | mode | @source |
|---|---|---|
| 卡 16 夢遊卡 | 0 | `0x444325`（`push 0; push 0; push ebx`） |
| 卡 17 陷害卡 | 0 | `0x4445fc` |
| 卡 26 查稅卡 | **2** | `0x445360`（`push 0; push 2; push ebx`） |
| `0x441210` 通用封装 | 0 | `0x44124e` |
| 过路费 `0x419b32` | 未逐条确认 | `0x419eb8` |
| 事件 `0x41a3be` / `0x41abde` | 未逐条确认 | `0x41a683` / `0x41af75` |

返回值：**新的受害者下标**（`-1` = 放弃，原效果落在自己身上）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 主动使用 | `0x4420d5` → 返回 0，卡不消耗 | `0x4420d5` |
| 只有 1 个候选对象 | **自动选中**，仍弹「是否嫁禍給%s？」确认 | `0x4447dd` |
| 玩家选「否」 | 返回 `-1`，原效果不转移 | `0x444863` |
| 候选数为 0（单人对局） | `esi == 0`，走 `0x44486d` 分支（仍展示卡牌弹窗），返回 `-1` | `0x44486d` |
| 人类 vs AI | 人类用 UI 选；AI 用 `0x40d2d3`/`0x40d31c` 依 hostility 选 | `0x4447a8` |
| 卡 26 的 `> 2000` 门限 | 税额 ≤ 2000 时**根本不查**嫁禍卡 | `0x44534e`–`0x445359` |

#### 防御卡查询

它是被查询方：`push 0x13; push <玩家>; call 0x4413ad`，共 7 处调用点：
`0x444313`、`0x4445ea`、`0x445341`、`0x44123c`、`0x41a673`、`0x41af65`、`0x419ea3`。

#### 未决

1. `mode`（arg2）三支策略的**具体判定规则**（`0x4448ef`–`0x444973`）未逐条拆解。
2. 第 3 个参数在已见的 5 个调用点里都是 0，**是否被使用未决**。
3. 过路费/事件两条路径的 mode 值未确认。

`@source` `VA 0x004420d5`、`VA 0x44476a`、`VA 0x444325`、`VA 0x4445fc`、`VA 0x445360`、
`VA 0x44124e`、`VA 0x46533d`、`VA 0x46534e`、`VA 0x46535d`、`VA 0x40d2d3`、`VA 0x40d31c`。

---

### 卡 20 · 免費卡

| 项 | 值 |
|---|---|
| 卡号 | 20 |
| 卡名 VA | `0x00466b47`（`"免費卡"`） |
| 函数 VA | **`0x004420d5`（2 字节空桩）** |
| 可否主动使用 | ❌ **不可** |
| 查防御卡 | 被 `has_card(玩家, 20)` 查询（查税卡、过路费、事件） |
| 触发条件 | 需要付出一笔钱时（税金 / 过路费 / 事件罚款） |

#### 精确效果

处理函数 `0x00444a60(target, payer, amount)`（108 条指令）：
```asm
00444a6a  mov   edi, dword ptr [esp + 0x94]     ; arg1 = 要付钱的人
00444a92  cmp   byte ptr [ebx + 0x496b7d], 1    ; 人类？
00444a99  je    0x444ad8
; —— AI 判断 ——
00444a9b  call  0x456f2d                        ; PRNG
00444aa2  mov   esi, 0xbb8                       ; 3000（十进制）
00444aaa  idiv  esi
00444aac  add   edx, esi                        ; edx = rand%3000 + 3000
00444aae  mov   esi, dword ptr [0x4990e8]       ; price_index
00444ab4  imul  esi, edx                        ; 阈值 = (3000..5999) × price_index
00444abe  cmp   eax, dword ptr [ebx + 0x496b84]; arg3 > 现金？
00444ac4  jg    0x444aca                        ; 是 → 用卡
00444ac6  cmp   esi, eax
00444ac8  jge   0x444ad1                        ; 阈值 >= 金额 → 不用
00444aca  mov   esi, 1                          ; 用卡
; —— 人类判断 ——
00444adf  push  0x465388                        ; "%s\n\n是否使用免費卡？"
00444af4  call  0x440ba8                        ; 是/否 对话框
; —— 用卡 ——
00444b23  push  0x14                            ; 20 = 免費卡
00444b25  call  0x441f73                        ; 卡牌弹窗
00444b30  call  0x441343                        ; ★ 消耗免費卡
00444b54  mov   edx, dword ptr [eax + 0x481286] ; k = 19 → "#0446有錢也不給你！"
00444b5e  call  0x44ef41                        ; player_say(持卡人, 0, 台词)
00444b66  mov   ecx, dword ptr [esp + 0x98]     ; arg2 = 收钱方
00444b6d  cmp   ecx, -1
00444b70  je    0x444ba0                        ; -1 → 不念第二句
00444b8e  mov   edi, dword ptr [eax + 0x481376] ; k = 79 → "#0474算了！\n老子有的是錢。"
00444b98  call  0x44ef41                        ; player_say(收钱方, 1, 台词)
00444ba5  mov   eax, esi                        ; 返回 1 = 用了卡
```
**AI 的用卡阈值**：`金额 > 现金` 或 `金额 > (PRNG%3000 + 3000) × price_index` 时用卡。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 主动使用 | `0x4420d5` → 返回 0，卡不消耗 | `0x4420d5` |
| AI 金额刚好等于阈值 | `jge` → **不用卡** | `0x444ac8` |
| 人类选「否」 | 返回 0，卡保留 | `0x444afe`–`0x444b01` |
| `arg2 == -1`（无收钱方） | 跳过「算了！老子有的是錢」这句 | `0x444b70` |
| 金额为 0 | AI 侧 `0 > 阈值` 不成立 → 不用卡 | `0x444ac6` |

#### 防御卡查询

被查询方：`push 0x14; push <玩家>; call 0x4413ad`
—— `0x445310`（查税卡）、`0x419e3d`（过路费）、`0x41a611`、`0x41af0f`（事件）。

#### 未决

1. AI 阈值常量 `0xbb8`（3000）的**设计依据**未决。
2. 过路费/事件调用点的 `arg2`（收钱方）如何传递未逐条确认。

`@source` `VA 0x004420d5`、`VA 0x444a60`、`VA 0x445310`、`VA 0x419e3d`、`VA 0x41a611`、
`VA 0x41af0f`、`VA 0x481286`、`VA 0x481376`、`VA 0x465388`、`VA 0x4990e8`。

---

### 卡 21 · 免罪卡

| 项 | 值 |
|---|---|
| 卡号 | 21 |
| 卡名 VA | `0x00466b4e`（`"免罪卡"`） |
| 函数 VA | **`0x004420d5`（2 字节空桩）** |
| 可否主动使用 | ❌ **不可** |
| 查防御卡 | 被 `has_card(玩家, 21)` 查询（**最高优先级**） |
| 触发条件 | 成为梦游(16)/陷害(17)/事件的受害者时 |

#### 精确效果

处理函数 `0x00444bb2(target)`（53 条指令）：
```asm
00444bbd  imul  ebx, dword ptr [esp + 0x94], 0x68   ; target 的玩家结构
00444bd9  call  0x41d476                             ; 把镜头移到该玩家
00444be1  mov   ecx, dword ptr [ebx + 0x496b68]      ; 姓名指针
00444be8  push  0x46539d                             ; "%s\n\n免罪卡生效！"
00444bf2  call  0x457110                             ; sprintf
00444bfd  push  0x15                                 ; 21 = 免罪卡
00444bff  call  0x441f73                             ; 卡牌弹窗
00444c07  push  0x15
00444c11  call  0x441343                             ; ★ 消耗免罪卡
00444c36  mov   edi, dword ptr [eax + 0x48128a]      ; k = 20 → "#0447快滾！\n我不需要你！"
00444c40  jmp   0x444753                             ; 共享收尾 → player_say + 返回 1
```
返回值 **1**。调用方看到「免罪成立」后的典型处理是：
- 卡 16：`0x444302` → `0x444bb2(ebx)` 后直接 `jmp 0x4444b3`（刷新并结束，**完全抵消**）
- 卡 17：`0x4445d9` → 同理，**完全抵消**
- `0x441210`：返回 `-1` 给调用方，由调用方决定「免罪 = 无事发生」

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 主动使用 | `0x4420d5` → 返回 0，卡不消耗 | `0x4420d5` |
| 同时持有免罪卡与嫁禍卡 | **免罪卡优先**，命中的第一张卡被消耗后**不再查嫁禍卡** | `0x441226`–`0x441236` |
| 无免罪卡 | 落到嫁禍卡查询 | `0x441237` |
| 两者都没有 | 原效果照常施加 | `0x44125d` |

#### 防御卡查询

被查询方：`push 0x15; push <玩家>; call 0x4413ad`
—— `0x4442f5`（卡 16）、`0x4445cc`（卡 17）、`0x441219`（通用封装 `0x441210`）。

#### 未决

1. 免罪卡的**优先级是否在所有场合都是第一**：本文确认了 3 处（卡 16、卡 17、`0x441210`），
   但过路费路径（`0x419b32`）**只查免費卡与嫁禍卡、不查免罪卡** —— 见 §十一 的疑问清单。
2. `0x420e9a` 等玩家的「天數」字段在被免罪后是否完全不变（本文未逐字段比对）。

`@source` `VA 0x004420d5`、`VA 0x444bb2`、`VA 0x444753`、`VA 0x441226`–`VA 0x441236`、
`VA 0x4442f5`、`VA 0x4445cc`、`VA 0x441219`、`VA 0x48128a`、`VA 0x46539d`。

---

---

## 二·续、逐卡规格（卡 12–15）

> 本节由子代理按 §0 的证据标准产出，主代理已逐条复核以下要点：
> ① `call 0x4413ad` 的**穷举扫描确认这 4 张卡都不查防御卡**；
> ② 台词索引 k=11/71（卡 12）、12/72（卡 13）、13/43/73（卡 14）、14（卡 15）与 `0x48123a` 表实测一致；
> ③ 卡 15 的 `ebx` 循环上界为 8（`cmp ebx,8`）、写入 `player+0x36 = 5`、`player+0x42 += 5`，与 `0x444136`–`0x4441a1` 一致；
> ④ 卡 14 写 `player+0x38 = 1`（`0x4440d2` 附近的 `mov byte ptr [ebx + 0x496ba0], 1`）。

### 卡 12 · 拆除卡

| 项 | 值 |
|---|---|
| 卡号 | 12 |
| 卡名 VA | `0x00466b0f`（`"拆除卡"`） |
| 函数 VA | `0x00443b0f`（244 条指令，814 字节；区间 `0x443b0f`–`0x443e3c`，共享尾部 `0x442afa`） |
| 可否主动使用 | ✅ 可（有完整效果逻辑，非空桩；返回 0 表示失败） |
| 查防御卡 | ❌ 不查（函数内 19 条 `call` 指令 / 14 个不同目标全为直接调用，无 `call 0x4413ad`，也无任何间接 `call dword ptr [...]`） |
| 目标选择 | 自选地图目标（**不是**玩家掩码）：人类 `0x446ae8(0x0e0c0626)`、AI `0x41e6f2(0)`（读 `[0x48be58]`）；返回 0 = 未选 → 函数返回 0 |

#### 精确效果

**1. 选目标；选不到则整卡失败**

```
00443b18  imul eax, dword ptr [0x49910c], 0x68    ; 当前行动玩家下标 × 0x68
00443b1f  cmp  byte ptr [eax + 0x496b7d], 1        ; player+0x15 = who_plays
00443b26  jne  0x443b34
00443b28  push 0xe0c0626
00443b2d  call 0x446ae8                            ; 人类：目标选择对话框
00443b32  jmp  0x443b3a
00443b34  push edi                                 ; edi = 0
00443b35  call 0x41e6f2                            ; AI：读 0x48be58[0]
00443b3a  add  esp, 4
00443b3d  mov  dword ptr [esp], eax                ; 目标值存入栈上局部变量
00443b40  cmp  dword ptr [esp], 0
00443b44  je   0x443e35                            ; 目标 == 0 → 直接返回 0
```

`0x41e6f2(0)` 的实现是 `mov eax,[esp+4]; mov eax,[eax*4+0x48be58]; ret`（`0x41e6f2`），即读全局数组 `0x48be58` 的第 0 项。

**2. 扣掉自己的拆除卡**（发生在失败判定之后，所以失败时卡不消耗）

```
00443b4a  push 0xc                                 ; 卡号 12
00443b4c  mov  ebx, dword ptr [0x49910c]
00443b52  push ebx
00443b53  call 0x441343                            ; remove_card(current, 12)
```

**3. 当前行动角色说 k=11 台词**

```
00443b61  imul eax, ebp, 0x68
00443b64  mov  al, byte ptr [eax + 0x496b7b]       ; player+0x13 = character
...                                                ; ebx = character × 0x168
00443b80  mov  eax, dword ptr [ebx + 0x481266]     ; 0x48123a + 4×11
00443b86  push eax
00443b87  push 0
00443b89  push ebp
00443b8a  call 0x44ef41                            ; player_say(current, 0, "#0437真礙眼！！！")
```

台词表 `0x48123a + 4×11` 解引用后的字符串为 `"#0437真礙眼！！！"`（指针 `0x0046937b`）。

**4. 按目标值分三路**

```
00443b92  mov  ecx, dword ptr [esp]                ; ecx = 目标值
00443b95  cmp  ecx, 0x7d0        ; 2000
00443b9b  jle  0x443c54
00443ba1  cmp  ecx, 0xfa0        ; 4000
00443ba7  jge  0x443c54
00443bad  lea  ebx, [ecx - 0x7d0]
00443bb3  imul ebx, ebx, 0x34                       ; 记录 = (t-2000) × 52 + [0x498e84]
00443bb6  mov  eax, dword ptr [0x498e84]
00443bbb  add  ebx, eax
```

**4A. 2000 < 目标 < 4000：破坏一张「房屋」记录（步长 52 = 0x34，基址 `[0x498e84]`）**

```
00443bc4  cmp  byte ptr [eax + 0x496b7d], 1
00443bcb  je   0x443bf9                            ; who_plays == 1 时跳过飞行动画
00443bcd  push 0x64
00443bcf  movsx edx, word ptr [ebx + 2]            ; 记录 +2 = y
00443bd3  push edx
00443bd4  movsx edx, word ptr [ebx]                ; 记录 +0 = x
00443bd7  push edx
...                                                ; push 当前玩家 y / x
00443bf1  call 0x40e669                            ; 0x40e669(0, cur_x, cur_y, rec_x, rec_y, 100)
00443bf9  push 0
00443bfb  movsx eax, word ptr [ebx + 2]
00443bff  push eax
00443c00  movsx eax, word ptr [ebx]
00443c03  push eax
00443c04  call 0x41d476                            ; 0x41d476(rec_x, rec_y, 0) = 视野移到该格
00443c0c  movzx esi, byte ptr [ebx + 0x19]         ; 记录 +0x19 = 地主（1-based）
00443c10  dec  byte ptr [ebx + 0x1a]               ; 记录 +0x1a -= 1（等级）
00443c13  cmp  byte ptr [ebx + 0x18], 0
00443c17  je   0x443c21
00443c19  mov  byte ptr [ebx + 0x1a], 0            ; 若 +0x18 ≠ 0 则同时清 +0x1a/+0x18
00443c1d  mov  byte ptr [ebx + 0x18], 0
00443c21  cmp  byte ptr [ebx + 0x19], 0
00443c25  je   0x443db6
00443c39  push eax                                 ; delta = 30 × [0x4990e8]
00443c3f  push eax                                 ; 当前玩家下标
00443c46  push eax                                 ; 地主 - 1
00443c47  call 0x40df69                            ; update_hostility(地主-1, 当前, 30×[0x4990e8])
00443c4f  jmp  0x443db6
```
`30 × [0x4990e8]` 的算法是 `eax=[0x4990e8]; add eax,eax; edx=eax; shl eax,4; sub eax,edx`（`0x443c2b`–`0x443c37`）。

**4B. 4000 < 目标 < 6000：破坏一张「建筑」记录（步长 56，基址 `[0x498e88]`）**

```
00443c54  mov  ebp, dword ptr [esp]
00443c63  cmp  ebp, 0x1770       ; 6000
00443c69  jge  0x443d22
00443c6f  lea  ebx, [ebp - 0xfa0]
00443c75  shl  ebx, 3
00443c78  mov  eax, ebx
00443c7a  shl  ebx, 3
00443c7d  sub  ebx, eax                            ; ebx = (t-4000) × 56
00443c7f  mov  eax, ebx
00443c81  mov  ebx, dword ptr [0x498e88]
00443c87  add  ebx, eax
...                                                ; 同上：条件飞行动画 + 0x41d476(rec_x, rec_y, 0)
00443cd8  movzx esi, byte ptr [ebx + 0x19]         ; 地主
00443cdc  mov  al, byte ptr [ebx + 0x1a]
00443cdf  dec  al
00443ce1  mov  byte ptr [ebx + 0x1a], al           ; +0x1a -= 1
00443ce4  jne  0x443cee
00443ce6  mov  byte ptr [ebx + 0x18], al           ; 减到 0：清 +0x18
00443ce9  call 0x40dffa                            ; 见下方说明
00443cee  cmp  byte ptr [ebx + 0x19], 0
00443cf2  je   0x443db6
00443d15  call 0x40df69                            ; update_hostility(地主-1, 当前, 30×[0x4990e8])
00443d1d  jmp  0x443db6
```

`0x40dffa` 的实现：对 `for (edx = 0; edx < [0x499114]; edx++)`，若 `byte[player+0x15] != 0` 且 `byte[player+0x32] != 0`，则把 `byte[player+0x32]` 置 `0x80`（`0x40dffc`–`0x40e021`）。

**4C. 目标 & 0x8000：移动/清除一格**地图物件**（步长 24 = 0x18 的记录表 `0x496d08`）**

```
00443d22  test byte ptr [esp + 1], 0x80            ; 目标值 bit15
00443d27  je   0x443dae
00443d2d  mov  esi, dword ptr [esp]
00443d30  and  esi, 0x7f00
00443d36  sar  esi, 8                              ; 物件序号 = (t & 0x7f00) >> 8（1-based）
00443d39  imul ebx, dword ptr [0x49910c], 0x68
00443d40  cmp  byte ptr [ebx + 0x496b7d], 1
00443d47  je   0x443d97                            ; who_plays == 1 时跳过飞行动画
00443d49  push 0x64
...                                                ; 从 0x496d08 记录算出该物件所在格的 x/y
00443d69  mov  eax, dword ptr [0x498e80]           ; 地块表（步长 40）
00443d8f  call 0x40e669
00443d97  push esi
00443d98  call 0x40e14d                            ; 对该物件执行清除
00443da0  push 1
00443da2  push 0
00443da4  push 0
00443da6  call 0x41d476                            ; 0x41d476(0, 0, 1)
00443dae  test edi, edi
00443db0  je   0x443e35                            ; edi 恒为 0 → 直接返回目标值
```

`0x40e14d(esi)` 中 `dec edx` 后按 `(esi-1) × 24 + 0x496d08` 取记录，读记录类型字节 `[rec+0]`：

- 类型 `0x10` / `0x11` / `0x12`（十进制 16/17/18）：分别 `inc byte [0x497321]` / `inc byte [0x497322]` / `inc byte [0x497323]`（`0x40e17f`、`0x40e18a`、`0x40e195`）；类型 `0x12` 另外把 `[rec+5]`（1-based 玩家）的 `player+0x40` 清 0（`0x40e1b2`）。
- 其它类型且 `[rec+5] != 0`：把该玩家的 `player+0x3f` 清 0，并从 `0x4749e2` / `0x474a06` / `0x474a2a` 三张 16 位表（以类型值为下标）减去 `player+0x44` / `+0x46` / `+0x48`（`0x40e1db`、`0x40e1f5`、`0x40e204`、`0x40e213`）。
- 表尾统一：`[rec+5] == 0` 时把地块表（`[0x498e80]`，步长 40）中 `[rec+2]` 号地块的 `+0x26` 清 0（`0x40e243`）；随后清空该物件记录的 `+2`（`+0x496d0a`）、`+4`（`+0x496d0c`）、`+5`（`+0x496d0d`）（`0x40e25d`–`0x40e26e`），即把记录归还空表。

注意 `edi` 只在 4B 分支被写（`0x443d07 mov edi,[0x49910c]`），而该分支在 `0x443d1d` 已 `jmp 0x443db6`；走到 `0x443dae` 时 `edi` 仍为 `0x443b16` 的 `xor edi,edi`，所以 `test edi,edi / je 0x443e35` 恒跳转，4C 分支不做任何后续提示。

**5. 4A/4B 共同的收尾：提示框 + 被害者台词**

```
00443db6  push 0
00443db8  push 0
00443dba  push 0x211
00443dbf  mov  edx, dword ptr [0x48a0e4]
00443dc5  push edx
00443dc6  call 0x450441                            ; 按资源 0x211 建提示框
00443dd0  push 0x61
00443dd2  push 0x260001
00443dd7  push 0x28
00443dd9  push 0
00443ddb  push eax
00443ddc  call 0x45144f                            ; 设置框内容
00443de4  push ebx
00443de5  call 0x456e11                            ; 销毁框
00443ded  push 0x1f4
00443df2  call 0x45285e                            ; 延时 500 毫秒
00443dfa  test esi, esi
00443dfc  je   0x443e30
00443dfe  dec  esi                                 ; esi = 地主 - 1 = 玩家下标
00443dff  imul eax, esi, 0x68
00443e02  mov  al, byte ptr [eax + 0x496b7b]       ; character
00443e1e  mov  ecx, dword ptr [ebx + 0x481356]     ; 0x48123a + 4×71
00443e24  push ecx
00443e25  push 1
00443e27  push esi
00443e28  call 0x44ef41                            ; player_say(地主-1, 1, "#0468你皮在癢啊？")
00443e30  call 0x41d546
00443e35  mov  eax, dword ptr [esp]
00443e38  jmp  0x442afa                            ; 返回目标值（非 0 = 成功）
```

**公式汇总**
```
card12_demolish():
    cur = players[0x49910c]
    t = (cur.who_plays == 1) ? dialog(0x0e0c0626) : AI_choice[0]   # 0x48be58[0]
    if (t == 0) return 0                      # 卡不消耗
    remove_card(cur, 12)
    say(cur, 0, line[chr(cur)][11])           # "#0437真礙眼！！！"
    if (2000 < t < 4000):                     # 房屋表 [0x498e84]，步长 52
        r = [0x498e84] + (t-2000)*52
        if (cur.who_plays != 1) fly_anim(cur.x, cur.y, r.x, r.y)
        view(r.x, r.y)
        owner = r[+0x19]                      # 1-based
        r[+0x1a] -= 1
        if (r[+0x18] != 0): r[+0x1a] = 0; r[+0x18] = 0
        if (owner != 0): hostility_add(owner-1, cur, 30 * [0x4990e8])
        msgbox(0x211); wait(500ms)
        if (owner != 0): say(owner-1, 1, line[chr(owner-1)][71])   # "#0468你皮在癢啊？"
    else if (4000 < t < 6000):                # 建筑表 [0x498e88]，步长 56
        r = [0x498e88] + (t-4000)*56
        if (cur.who_plays != 1) fly_anim(cur.x, cur.y, r.x, r.y)
        view(r.x, r.y)
        owner = r[+0x19]
        if (--r[+0x1a] == 0): r[+0x18] = 0; clear_state_0x32()
        if (owner != 0): hostility_add(owner-1, cur, 30 * [0x4990e8])
        msgbox(0x211); wait(500ms)
        if (owner != 0): say(owner-1, 1, line[chr(owner-1)][71])
    else if (t & 0x8000):                     # 地图物件表 0x496d08，步长 24
        idx = (t & 0x7f00) >> 8
        if (cur.who_plays != 1) fly_anim(...)
        clear_object(idx)                     # 0x40e14d
        refresh(0x41d476(0,0,1))
    return t
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 对话框/ AI 返回 0 | 立即返回 0；手牌未动，返回选卡界面 | `0x443b40`、`0x443b44`、`0x443e35` |
| 目标值 == 2000 / == 4000 / == 6000 | 落到 4C 分支（`jle`/`jge` 都跳 0x443c54 / 0x443d22），无 bit15 时什么都不做，直接返回该值 | `0x443b9b`、`0x443ba7`、`0x443c5d`、`0x443c69` |
| 目标值 ≤ 2000 或 ≥ 6000 且 bit15 == 0 | 不做任何事，函数返回该值（非 0，视为成功） | `0x443d22`、`0x443d27`、`0x443dae`、`0x443db0` |
| 4A 目标记录等级 `+0x1a` 为 0 | 无下限保护，`dec` 后变 `0xFF`；仅当 `+0x18 != 0` 时才把 `+0x1a`、`+0x18` 一起清 0 | `0x443c10`、`0x443c13`–`0x443c1d` |
| 4A 目标记录等级 `+0x18 != 0` | 强制把 `+0x1a` 与 `+0x18` 都置 0 | `0x443c19`、`0x443c1d` |
| 4B 减到 0 | 清 `+0x18` 并调用 `0x40dffa`（把 `[0x499114]` 名玩家中 `+0x32 != 0` 者的 `+0x32` 置 `0x80`） | `0x443ce4`、`0x443ce6`、`0x443ce9`、`0x40e019` |
| 记录地主 `+0x19 == 0`（无主） | 照常拆除，但不调用 `update_hostility`，也不播被害者台词 | `0x443c25`、`0x443cf2`、`0x443dfa` |
| 拆自己的地（地主 == 当前玩家） | `update_hostility(me, me, 30×E)` 在 `0x40df75` 的 `cmp edx,ebx / je` 直接返回，敌意不变 | `0x40df75`、`0x40dfd7` |
| 当前玩家是「人类」（`who_plays == 1`） | 跳过 `0x40e669` 飞行动画与 4C 中的取景动画（`cmp ...,1 / je`），其余逻辑相同 | `0x443bc4`–`0x443bcb`、`0x443d40`–`0x443d47` |
| 4C 物件序号为 0（`t & 0x7f00 == 0`） | `0x40e14d` 开头 `test edx,edx / je 0x40e29f` 直接返回，不做清除 | `0x40e153`、`0x40e155` |
| 4C 物件类型非 16/17/18 且 `[rec+5] == 0` | 不清玩家增益，只清地块标志并把记录归还空表 | `0x40e1c4`、`0x40e1cb`、`0x40e243`–`0x40e26e` |
| 4C 物件序号越界（表只有 46 条，`cmp ebx,0x2e` 是初始化循环上界） | `0x40e14d` 在取记录前只做 `dec edx`，没有上界比较（`0x40e15b`–`0x40e166`），直接按 `(序号-1)×24 + 0x496d08` 取 | `0x407d65`、`0x40e15b`、`0x40e166` |

#### 防御卡查询

**无**（函数体自 `0x443b0f` 至 `0x443e38` 共 244 条指令，全部 `call` 均为直接调用，目标是 `0x40df69`、`0x40dffa`、`0x40e14d`、`0x40e669`、`0x41d476`、`0x41d546`、`0x41e6f2`、`0x441343`、`0x446ae8`、`0x44ef41`、`0x450441`、`0x45144f`、`0x45285e`、`0x456e11`，其中没有 `call 0x4413ad`，也没有 `call dword ptr [...]` 形式的间接调用）。对照：同族的卡 16 夢遊卡（`0x004441dc`）确实会查防御卡——`0x4442f2 push 0x15; 0x4442f4 push ebx; 0x4442f5 call 0x4413ad`（21 免罪卡）命中后走 `0x444bb2`，未命中再 `0x444310 push 0x13`（19 嫁禍卡）。卡 12 无此形状。

#### 未决

1. `[0x498e84]`（步长 52）与 `[0x498e88]`（步长 56）两张表的具体身份。二者都由资源加载流程 `0x407c67`/`0x407c7c`（另一处 `0x402ed6`/`0x402eeb`）从 `0x47493c` 指向的数据块按文件内偏移填成指针，exe 内没有表名或语义字符串；本卡只能确认记录字段 `+0x18`（标志）、`+0x19`（1-based 地主）、`+0x1a`（等级）。
2. 记录字段 `+0x18` 的语义（写 0 之外没有任何地方给出取值域）。
3. `0x496d08` 表（步长 24，46 条，类型初值来自静态字节表 `0x47ed3c`，值域 1–18）中类型 1–15 与 16/17/18 的实际含义，以及 `player+0x3f`（`0x496ba7`）、`player+0x40`（`0x496ba8`）、`player+0x44/+0x46/+0x48`（`0x496bac/bae/bb0`）与表 `0x4749e2`/`0x474a06`/`0x474a2a` 的语义。
4. 全局 `0x4990e8` 的语义：`0x4073b4` 在新游戏初始化时置 1，`0x423acf` 会把它抬升为「全体现存玩家某均值 / [0x49908c]」（`0x423b13`、`0x423b1b`），`0x44889c` 从 `player×10008 + 0x48f1ec` 读回。
5. 提示框资源 `0x211`（参数 `[0x48a0e4]`、`0x260001`、`0x61`）显示的文本内容。
6. `0x40dffa` 把 `byte[player+0x32]` 置 `0x80` 的意图（与 `player+0x32` 的语义绑定）。

`@source` `VA 0x443b0f`、`VA 0x442afa`、`VA 0x475d5c+12*4`、`VA 0x47fdf2+11*8`、`VA 0x00466b0f`、`VA 0x441343`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x44ef41`、`VA 0x481266`、`VA 0x481356`、`VA 0x498e84`、`VA 0x498e88`、`VA 0x498e80`、`VA 0x496d08`、`VA 0x40e14d`、`VA 0x40dffa`、`VA 0x40e669`、`VA 0x41d476`、`VA 0x40df69`、`VA 0x450441`、`VA 0x45144f`、`VA 0x456e11`、`VA 0x45285e`、`VA 0x41d546`、`VA 0x407c67`、`VA 0x407d5d`、`VA 0x47ed3c`、`VA 0x4990e8`、`VA 0x423b1b`、`VA 0x44889c`、`VA 0x4073b4`、`VA 0x44624e`、`VA 0x44627d`、`VA 0x4462e7`

---

### 卡 13 · 搶奪卡

| 项 | 值 |
|---|---|
| 卡号 | 13 |
| 卡名 VA | `0x00466b16`（`"搶奪卡"`） |
| 函数 VA | `0x00443e3d`（97 条指令，323 字节；区间 `0x443e3d`–`0x443f7f`，共享尾部 `0x441f1b`） |
| 可否主动使用 | ✅ 可（返回值为被抢到的卡号；返回 0 表示失败） |
| 查防御卡 | ❌ 不查（函数体 9 条 `call` / 9 个不同目标全为直接调用，无 `call 0x4413ad`，也无间接调用；其调用的 `0x44192a` 同样不含 `call 0x4413ad`） |
| 目标选择 | 两段式：① 选一名玩家（掩码；人类 `0x446ae8(0x0e0c0410)`、AI `0x41e6f2(0)`，`0x40d293` 取位号）② 由目标玩家选一张手牌（人类弹窗 `0x44192a(...,1)`、AI `0x41e6f2(1)`） |

#### 精确效果

**1. 选目标玩家**

```
00443e40  imul eax, dword ptr [0x49910c], 0x68
00443e47  cmp  byte ptr [eax + 0x496b7d], 1
00443e4e  jne  0x443e5c
00443e50  push 0xe0c0410
00443e55  call 0x446ae8
00443e5c  push 0
00443e5e  call 0x41e6f2                            ; AI：0x48be58[0]
00443e63  add  esp, 4
00443e66  mov  ebx, eax                            ; ebx = 玩家位掩码
00443e68  test ebx, ebx
00443e6a  je   0x441f1b                            ; 掩码 0 → 返回 0（卡不消耗）
```

**2. 当前行动角色说 k=12 台词**

```
00443e79  xor edx, edx
00443e7b  mov dl, byte ptr [eax + 0x496b7b]        ; character
00443e92  mov esi, dword ptr [eax + 0x48126a]      ; 0x48123a + 4×12
00443e98  push esi
00443e99  push 3
00443e9b  push ecx                                 ; ecx = 当前玩家下标
00443e9c  call 0x44ef41                            ; player_say(current, 3, "#0438把值錢的東西\n交出來！！")
```

**3. 掩码 → 玩家下标；播飞行动画**

```
00443ea4  push ebx
00443ea5  call 0x40d293                            ; ctz(掩码) = 目标玩家下标
00443eaa  mov  edx, eax
00443eaf  mov  esi, eax                            ; esi = 目标下标
00443eb8  cmp  byte ptr [eax + 0x496b7d], 1
00443ebf  je   0x443eff                            ; who_plays == 1 时跳过飞行动画
00443ef7  call 0x40e669                            ; 0x40e669(0, cur_x, cur_y, tgt_x, tgt_y, 100)
```

**4. 调 `0x44192a` 抢牌**

```
00443eff  push 1
00443f01  mov  eax, dword ptr [0x49910c]
00443f06  push eax
00443f07  push esi
00443f08  call 0x44192a                            ; steal_card(target_idx, current_idx, 1)
00443f0d  add  esp, 0xc
00443f10  mov  ebx, eax
00443f12  test eax, eax
00443f14  je   0x441f1b                            ; 没抢到（含人类取消）→ 返回 0，卡不消耗
```

`0x44192a(arg1=目标下标, arg2=施害玩家下标, arg3=1)` 的行为（`0x44192a`–`0x441b09`）：

- **人类**（`cmp byte [player+0x15],1`，`0x441942`）：`0x450441(0x48a05c, 0xb, 0, 0)` 建窗（`0x44195b`）、`0x447c6e(0, win, arg1)`（`0x44196b`）、`0x441b0a(0, win, arg1)` 把目标玩家的 15 个手牌槽列成列表（`0x441977`；`0x441b0a` 内 `mov dl,[player*15+slot+0x499120]`、`mov edx,[eax*8+0x47fdea]` 取卡名，见 `0x441b6f`、`0x441b84`）；随后设矩形 `{0, 0x28, 0x1b8, 0x1e0}`（`0x441988`–`0x44199e`）、`0x451e7e`、`0x4563f5`、最后 `0x4018e7(0x4413ec, (arg3<<16)|arg1)` 跑模态窗口（`0x441a22`–`0x441a34`），结果存 `ebx`（`0x441a3c`），再 `0x456e11` 销毁窗口（`0x441a52`）。
- **AI**（`0x441a5d`）：`0x41e6f2(1)` → 读 `0x48be58[1]`（`0x441a5f`、`0x441a85`），并把「目标玩家名 + 卡名」组成字符串经 `0x440cac` 显示（`0x441aa7`–`0x441ab1`）。
- **搬移**（`0x441ab9` 起）：返回值 `ebx != 0` 时——若 `test bh,0x80` 为 0：`0x441343` 从目标玩家删卡（`0x441ae4`）、`0x4412e4` 把同一张卡加给当前玩家（`0x441af5`，其中 `mov edi,[esp+0xc4]` 在 `push ebx` 之后取到的是 arg2 = 当前玩家）；若 bit15 置位：`and ebx,0x7fff` 后走 `0x445aa2(arg1,target)`/`0x445a4d(arg2,current)`（`0x441ac2`–`0x441adb`）。函数最后返回 `ebx`（`0x441afd` `mov eax,ebx`）。

**5. 敌意 + 扣卡 + 被害者台词**

```
00443f1a  mov  al, byte ptr [eax*8 + 0x47fdef]    ; 卡片表第 (被抢卡) 条记录的第 5 字节
00443f21  and  eax, 0xff
00443f26  push eax                                 ; delta
00443f27  mov  edx, dword ptr [0x49910c]
00443f2d  push edx                                 ; 当前玩家
00443f2e  push esi                                 ; 目标玩家
00443f2f  call 0x40df69                            ; update_hostility(target, current, 表值)
00443f37  push 0xd                                 ; 卡号 13
00443f39  mov  ecx, dword ptr [0x49910c]
00443f3f  push ecx
00443f40  call 0x441343                            ; remove_card(current, 13)
00443f48  imul eax, esi, 0x68
00443f4d  mov  dl, byte ptr [eax + 0x496b7b]       ; 目标角色
00443f64  mov  edi, dword ptr [eax + 0x48135a]     ; 0x48123a + 4×72
00443f6a  push edi
00443f6b  push 1
00443f6d  push esi
00443f6e  call 0x44ef41                            ; player_say(target, 1, "#0469竟敢在太歲\n頭上動土？！")
00443f76  call 0x41d546
00443f7b  jmp  0x441f1b                            ; 返回 ebx = 被抢到的卡号
```

`[eax*8 + 0x47fdef]` 的地址换算：`0x47fdef + card*8 = 0x47fdf2 + (card-1)*8 + 5`，即卡片表 `0x47fdf2` 中第 `card` 条记录的第 5 字节（偏移 +5）。该字节的值例如：拆除卡 12 → 15、搶奪卡 13 → 25、停留卡 14 → 20、冬眠卡 15 → 100、夢遊卡 16 → 25（`0x47fe4f`、`0x47fe57`、`0x47fe5f`、`0x47fe67`、`0x47fe6f`）。

**公式汇总**
```
card13_rob():
    cur = 0x49910c
    mask = (cur.who_plays == 1) ? dialog(0x0e0c0410) : AI_choice[0]    # 0x48be58[0]
    if (mask == 0) return 0                     # 卡不消耗
    say(cur, 3, line[chr(cur)][12])             # "#0438把值錢的東西\n交出來！！"
    tgt = ctz(mask)                             # 0x40d293
    if (cur.who_plays != 1) fly_anim(cur.xy -> tgt.xy)
    card = steal_card(tgt, cur, 1)              # 0x44192a
    if (card == 0) return 0                     # 卡不消耗
    hostility_add(tgt, cur, card_table[card].byte5)
    remove_card(cur, 13)
    say(tgt, 1, line[chr(tgt)][72])             # "#0469竟敢在太歲\n頭上動土？！"
    refresh()
    return card
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 目标掩码为 0（取消 / AI 未选） | 返回 0，手牌未动 | `0x443e68`、`0x443e6a`、`0x441f1b` |
| 目标玩家手牌为空 / 玩家取消选牌 | `0x44192a` 返回 0（人类走 `0x441ab9 test ebx,ebx / je 0x441afd`），卡 13 返回 0，**不扣卡**（扣卡在 `0x443f37`，判定在 `0x443f14`） | `0x443f14`、`0x441ab9`、`0x441afd` |
| `0x44192a` 返回值带 0x8000 位 | 走 `and ebx,0x7fff` + `0x445aa2`/`0x445a4d` 分支（改 `0x49915b[p*15+card]` 计数）而非搬手牌；返回前已把 0x8000 位抹掉，所以后面 `[eax*8+0x47fdef]` 不会越界 | `0x441abd`、`0x441ac2`、`0x441afd` |
| 目标玩家同时是自己（掩码含自己） | 代码不排除自己：会走完整流程（对自己抢牌），`0x40df69` 在 a==b 时直接返回，敌意不变 | `0x40df75`、`0x443e68` |
| 当前玩家是「人类」 | 跳过 `0x40e669` 飞行动画 | `0x443eb8`、`0x443ebf` |
| 被抢卡片的记录第 5 字节 | 作为敌意增量原样传给 `0x40df69`；负数（<0）时 `0x40df7e` 会先判断该玩家对施害者的敌意是否已为 0 | `0x443f1a`、`0x40df77`、`0x40df8b` |
| 抢到后当前玩家手牌已满 15 张 | `0x4412e4` 先调 `0x441262` 数张数，等于 15 时调 `0x44128f` 随机丢掉一张腾位 | `0x4412e4`、`0x4412f2`、`0x4412f7` |

#### 防御卡查询

**无**（函数体 `0x443e3d`–`0x443f7f` 共 97 条指令，直接调用目标为 `0x446ae8`、`0x41e6f2`、`0x44ef41`、`0x40d293`、`0x40e669`、`0x44192a`、`0x40df69`、`0x441343`、`0x41d546`，没有 `call 0x4413ad`，也没有间接调用）。

被调用的 `0x44192a`（143 条指令，`0x44192a`–`0x441b09`）也不查防御卡：其调用目标为 `0x4018e7`、`0x447c6e`、`0x441b0a`、`0x450441`、`0x451e7e`、`0x451edb`、`0x4563f5`、`0x456e11`、`0x452946`、`0x457110`、`0x440cac`、`0x441343`、`0x4412e4`、`0x445aa2`、`0x445a4d`、`0x41e6f2`，无 `0x4413ad`。

#### 未决

1. `0x44192a` 返回值带 0x8000 位这一分支的语义：`0x445aa2(a,b)` 做 `if ([a*15+b+0x49915b] != 0) [a*15+b+0x49915b]--` 且 `if (b <= 8) [b+0x49731f]++`（`0x445aba`、`0x445ace`、`0x445ad3`），`0x445a4d(a,b)` 在 `[a*15+b+0x49915b] < 9` 时做反向操作（`0x445a64`、`0x445a99`）。这两个数组（`0x49915b`、`0x49731f`）的名称与用途未确认——`0x49915b` 的访问形状是 `[玩家][槽]`，但调用方传进来的第二个参数是卡号，两者不一致。
2. 人类对话框返回值的精确编码（是卡号还是手牌槽号）。卡 13 把它当卡号用（`0x441343(target, ebx)`、`[ebx*8+0x47fdef]`），据此可判定为卡号，但 `0x4413ec` 窗口过程本身未逐条确认。
3. `0x44192a` 中 `(arg3<<16)|arg1` 参数（`0x441a22`–`0x441a2e`）的两个字段各自的含义（arg3 在卡 13 场景恒为 1）。
4. 卡片表记录第 5 字节的命名（卡 12–16 的值依次为 15/25/20/100/25），本卡只能确认它被当作「敌意增量」使用。
5. `0x41d546()`（`0x41d546`：`[0x48be18]=0; 0x41906a(1)`）的界面含义。

`@source` `VA 0x443e3d`、`VA 0x441f1b`、`VA 0x475d5c+13*4`、`VA 0x47fdf2+12*8`、`VA 0x00466b16`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x40d293`、`VA 0x44192a`、`VA 0x441b0a`、`VA 0x44ef41`、`VA 0x48126a`、`VA 0x48135a`、`VA 0x40df69`、`VA 0x441343`、`VA 0x4412e4`、`VA 0x47fdef`、`VA 0x445aa2`、`VA 0x445a4d`、`VA 0x41d546`、`VA 0x40e669`

---

### 卡 14 · 停留卡

| 项 | 值 |
|---|---|
| 卡号 | 14 |
| 卡名 VA | `0x00466b1d`（`"停留卡"`） |
| 函数 VA | `0x00443f80`（113 条指令，362 字节；区间 `0x443f80`–`0x4440e9`，自身 `ret` 结尾） |
| 可否主动使用 | ✅ 可（返回目标掩码，非 0 = 成功） |
| 查防御卡 | ❌ 不查（函数体 9 条 `call` / 7 个不同目标全为直接调用，无 `call 0x4413ad`，也无间接调用） |
| 目标选择 | 选一名玩家（掩码）：人类 `0x446ae8(0x0e0c0010)`、AI `0x41e6f2(0)`（读 `[0x48be58]`）；`0x40d293` 把掩码转成玩家下标 |

#### 精确效果

**1. 选目标玩家；选不到则失败**

```
00443f84  imul eax, dword ptr [0x49910c], 0x68
00443f8b  cmp  byte ptr [eax + 0x496b7d], 1
00443f92  jne  0x443fa0
00443f94  push 0xe0c0010
00443f99  call 0x446ae8
00443fa0  push 0
00443fa2  call 0x41e6f2                            ; AI：0x48be58[0]
00443fa7  add  esp, 4
00443faa  mov  edi, eax                            ; edi = 掩码（也是最终返回值）
00443fac  test edi, edi
00443fae  je   0x4440e3                            ; 掩码 0 → 返回 0，卡不消耗
```

**2. 掩码 → 目标下标，并扣掉自己的停留卡**

```
00443fb4  push edi
00443fb5  call 0x40d293                            ; ctz(掩码)
00443fba  mov  ebx, eax
00443fbf  mov  esi, eax                            ; esi = 目标下标
00443fc1  push 0xe                                 ; 卡号 14
00443fc3  mov  ecx, dword ptr [0x49910c]
00443fc9  push ecx
00443fca  call 0x441343                            ; remove_card(current, 14)
```

**3. 目标不是自己时，当前行动角色说 k=13 台词**

```
00443fd2  mov  ebp, dword ptr [0x49910c]
00443fd8  cmp  ebx, ebp                            ; 目标下标 == 当前下标？
00443fda  je   0x44400a
00443fdc  imul eax, ebp, 0x68
00443fe1  mov  bl, byte ptr [eax + 0x496b7b]       ; character
00443ff8  mov  ecx, dword ptr [eax + 0x48126e]     ; 0x48123a + 4×13
00443ffe  push ecx
00443fff  push 3
00444001  push ebp
00444002  call 0x44ef41                            ; player_say(current, 3, "#0439不許動！！")
```

**4. 飞行动画（仅当当前玩家不是人类）**

```
0044400a  imul eax, dword ptr [0x49910c], 0x68
00444011  cmp  byte ptr [eax + 0x496b7d], 1
00444018  je   0x444058
00444050  call 0x40e669                            ; 0x40e669(0, cur_x, cur_y, tgt_x, tgt_y, 100)
00444055  add  esp, 0x18
```

**5. 按目标下标分三路施加「停留」**

```
00444058  cmp  esi, 4
0044405b  jge  0x4440d9                            ; 下标 >= 4 走另一张表
00444061  imul ebx, esi, 0x68
00444064  cmp  esi, dword ptr [0x49910c]
0044406a  jne  0x4440a0
```

**5A. 目标 == 自己（下标 < 4）**

```
0044406c  xor  edx, edx
0044406e  mov  dl, byte ptr [ebx + 0x496b7b]       ; 自己的 character
00444085  mov  ecx, dword ptr [eax + 0x4812e6]     ; 0x48123a + 4×43
0044408b  push ecx
0044408c  push 3
0044408e  push esi
0044408f  call 0x44ef41                            ; player_say(自己, 3, "#0458一動不如一靜！")
00444097  mov  byte ptr [ebx + 0x496ba0], 0x80    ; player+0x38 = 0x80（128）
0044409e  jmp  0x4440e3
```

**5B. 目标是别人且下标 < 4**

```
004440a0  xor  edx, edx
004440a2  mov  dl, byte ptr [ebx + 0x496b7b]       ; 目标的 character
004440b9  mov  edx, dword ptr [eax + 0x48135e]     ; 0x48123a + 4×73
004440bf  push edx
004440c0  push 2
004440c2  push esi
004440c3  call 0x44ef41                            ; player_say(目标, 2, "#0470嗚！\n被關禁閉了！")
004440cb  mov  byte ptr [ebx + 0x496ba0], 1        ; player+0x38 = 1
004440d2  call 0x41d546
004440d7  jmp  0x4440e3
```

**5C. 目标下标 >= 4**

```
004440d9  shl  esi, 4                              ; esi = 下标 × 16
004440dc  mov  byte ptr [esi + 0x498df6], 1        ; [下标×16 + 0x498df6] = 1
004440e3  mov  eax, edi                            ; 返回掩码
004440e5  pop  ebp
004440e6  pop  edi
004440e7  pop  esi
004440e8  pop  ebx
004440e9  ret
```

**公式汇总**
```
card14_stop():
    cur = 0x49910c
    mask = (cur.who_plays == 1) ? dialog(0x0e0c0010) : AI_choice[0]
    if (mask == 0) return 0                     # 卡不消耗
    tgt = ctz(mask)                             # 0x40d293
    remove_card(cur, 14)
    if (tgt != cur) say(cur, 3, line[chr(cur)][13])        # "#0439不許動！！"
    if (cur.who_plays != 1) fly_anim(cur.xy -> tgt.xy)
    if (tgt >= 4):
        [tgt*16 + 0x498df6] = 1
    else if (tgt == cur):
        say(tgt, 3, line[chr(tgt)][43])         # "#0458一動不如一靜！"
        byte[players[tgt] + 0x38] = 0x80        # 128
    else:
        say(tgt, 2, line[chr(tgt)][73])         # "#0470嗚！\n被關禁閉了！"
        byte[players[tgt] + 0x38] = 1
        refresh()                               # 0x41d546
    return mask
```

`player+0x38`（`0x496ba0`）被读取/维护的位置：`0x4012a7 cmp byte [player+0x38],0 / jne 0x401523`（非 0 时该玩家本回合不移动，直接返回）；`0x41c84f` 内 `0x41ca92 test byte [player+0x38],0x80 / mov byte [player+0x38],0`（清 0x80）与 `0x41cb70`–`0x41cb8b`（`dec`，减到 0 时置 `0x80`）。

**公式汇总补充（与玩家状态的交互）**
```
# 0x4012a7：行动开始
if (byte[player + 0x38] != 0) return;    # 本回合不移动
# 0x41c84f 内
if (byte[player + 0x38] & 0x80) byte[player + 0x38] = 0;      # 0x41ca92
if (byte[player + 0x38] != 0) {                                # 0x41cb70
    if (--byte[player + 0x38] == 0) byte[player + 0x38] = 0x80; # 0x41cb86
}
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 掩码为 0 | 返回 0，手牌未动 | `0x443fac`、`0x443fae`、`0x4440e3` |
| 掩码含多位（多选） | 只取 `ctz` 得到的最低位置 1 位那一名玩家，其余忽略 | `0x443fb5`、`0x443fbf` |
| 目标 == 自己 | `player+0x38 = 0x80`，说 k=43「一動不如一靜！」，且**不**播 k=13 台词 | `0x443fd8`、`0x44406c`–`0x444097` |
| 目标是别人且下标 < 4 | `player+0x38 = 1`，说 k=73「嗚！被關禁閉了！」，并 `0x41d546` 刷新 | `0x4440a0`–`0x4440d7` |
| 目标下标 >= 4 | `[下标×16 + 0x498df6] = 1`（**不**写 `player+0x38`，也**不**逐目标说 k=43/k=73） | `0x444058`、`0x44405b`、`0x4440d9`、`0x4440dc` |
| 当前玩家是「人类」 | 跳过 `0x40e669` 飞行动画 | `0x444011`、`0x444018` |
| 目标掩码非 0 但含的下标 >= 8 | 无保护，`shl esi,4` 后按 `0x498df6 + 下标×16` 写 | `0x4440d9` |

#### 防御卡查询

**无**（函数体 `0x443f80`–`0x4440e9` 共 113 条指令，直接调用目标为 `0x446ae8`、`0x41e6f2`、`0x40d293`、`0x441343`、`0x44ef41`、`0x40e669`、`0x41d546`，没有 `call 0x4413ad`，也没有间接调用）。

#### 未决

1. `player+0x38` 取 `0x80`（自己）与取 `1`（别人）的精确回合时序。`0x41ca92`（读到 0x80 就清 0）与 `0x41cb70`（递减，减到 0 补 0x80）位于同一个函数 `0x41c84f` 内且清零在递减之前；`0x4012a7` 的「非 0 则不移动」判定与该函数的相对调用顺序未确认，因此无法断言 0x80 与 1 是否在回合数上等价。
2. `0x498df6` 所在结构的身份。相关索引形状为 `下标 × 16`，同一基址族的字段有 `0x498de8/+0`（x）、`0x498dea/+2`（y，见 `0x41d4bd`/`0x41d4c4`）、`0x498df2`（`0x416f42`、`0x41c17a` 用 `cmp byte [idx*16+0x498df2],0`）、`0x498df4`、`0x498df5`、`0x498df6`。为什么下标 < 4 用 `player+0x38`、下标 >= 4 用这张表，未确认。
3. 玩家下标 >= 4 的合法性（`0x499114` = `[0x46cb3c] + 2`，见 `0x40715f`；`[0x46cb3c]` 在 `0x404f7c`、`0x40568e` 被写入，取值范围未确认），因此 5C 分支是否可达未确认。
4. `player+0x38` 的字段名。本报告只按偏移写作 `player+0x38`；`0x496ba0` 的读取点（`0x4012a7`、`0x40dd64`、`0x417256` 等）与递减/清零点（`0x41ca92`、`0x41cb70`）已确认。
5. `0x40d293` 参数为 0 时返回 −1（`0x40d29c mov eax,0xffffffff`），本卡不会走到（掩码已判非 0）。

`@source` `VA 0x443f80`、`VA 0x475d5c+14*4`、`VA 0x47fdf2+13*8`、`VA 0x00466b1d`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x40d293`、`VA 0x441343`、`VA 0x44ef41`、`VA 0x48126e`、`VA 0x4812e6`、`VA 0x48135e`、`VA 0x496ba0`、`VA 0x4012a7`、`VA 0x41ca92`、`VA 0x41cb70`、`VA 0x41cb86`、`VA 0x498df6`、`VA 0x41d476`、`VA 0x40e669`、`VA 0x41d546`、`VA 0x40715f`

---

### 卡 15 · 冬眠卡

| 项 | 值 |
|---|---|
| 卡号 | 15 |
| 卡名 VA | `0x00466b24`（`"冬眠卡"`） |
| 函数 VA | `0x004440ea`（76 条指令，242 字节；区间 `0x4440ea`–`0x4441db`，共享尾部 `0x4421ab`） |
| 可否主动使用 | ✅ 可（无失败路径，恒返回 1） |
| 查防御卡 | ❌ 不查（函数体 4 个 `call` 全为直接调用，无 `call 0x4413ad`，也无间接调用） |
| 目标选择 | 无（对**除自己以外**的全部符合条件玩家生效，玩家下标循环 0–7） |

#### 精确效果

**1. 先扣卡，然后当前行动角色说 k=14 台词**

```
004440ed  push 0xf                                 ; 卡号 15
004440ef  mov  edx, dword ptr [0x49910c]
004440f5  push edx
004440f6  call 0x441343                            ; remove_card(current, 15)
00444104  imul eax, ecx, 0x68
00444109  mov  dl, byte ptr [eax + 0x496b7b]       ; character
00444120  mov  ebx, dword ptr [eax + 0x481272]     ; 0x48123a + 4×14
00444126  push ebx
00444127  push 3
00444129  push ecx
0044412a  call 0x44ef41                            ; player_say(current, 3, "#0440早睡早起\n身體好！")
```

注意扣卡 `0x4440f6` 在函数最开头，且函数没有任何失败返回 0 的路径（唯一出口 `0x4441d7 jmp 0x4421ab` → `mov eax,1`），所以此处的「先扣卡」不会造成不消耗问题。

**2. 循环 8 个玩家槽**

```
00444132  xor  ebx, ebx                            ; i = 0
00444134  jmp  0x444147
00444136  mov  dh, 5                               ; 循环尾（跳过路径也走这里）
00444138  inc  ebx
00444139  cmp  ebx, 8
0044413c  jge  0x4441c9                            ; i >= 8 结束
00444142  cmp  ebx, 4
00444145  jge  0x4441a9                            ; i >= 4 走另一张表
00444147  mov  edi, dword ptr [0x49910c]
0044414d  cmp  ebx, edi
0044414f  je   0x444136                            ; 跳过当前行动玩家自己
00444151  imul esi, ebx, 0x68
00444154  cmp  byte ptr [esi + 0x496b7d], 0        ; who_plays == 0 → 跳过（空槽）
0044415b  je   0x444136
0044415d  cmp  word ptr [esi + 0x496b70], 0        ; player+0x08（x 坐标）== 0 → 跳过
00444165  je   0x444136
00444167  cmp  dword ptr [esi + 0x496b9a], 0       ; dword[player+0x32] != 0 → 跳过
0044416e  jne  0x444136
```

**3. 对满足条件的目标（下标 < 4）施加冬眠**

```
00444170  mov  edx, dword ptr [0x4990e8]
00444176  mov  eax, edx
00444178  shl  eax, 2                              ; 4E
0044417b  add  eax, edx                            ; 5E
0044417d  add  eax, eax                            ; 10E
0044417f  mov  edx, eax
00444181  shl  eax, 4                              ; 160E
00444184  sub  eax, edx                            ; 150E
00444186  push eax                                 ; delta = 150 × [0x4990e8]
00444187  push edi                                 ; 当前行动玩家
00444188  push ebx                                 ; 目标玩家
00444189  call 0x40df69                            ; update_hostility(目标, 当前, 150×[0x4990e8])
00444191  xor  dl, dl
00444193  mov  byte ptr [esi + 0x496b9f], dl       ; player+0x37 = 0
00444199  mov  dh, 5
0044419b  mov  byte ptr [esi + 0x496b9e], dh       ; player+0x36 = 5
004441a1  add  byte ptr [esi + 0x496baa], dh       ; player+0x42 += 5
004441a7  jmp  0x444136
```

`150 × [0x4990e8]` 的算法是 `E → 10E → 160E − 10E`（`0x444170`–`0x444184`）。

**4. 下标 >= 4 的玩家走另一张表**

```
004441a9  mov  eax, ebx
004441ab  shl  eax, 4                              ; i × 16
004441ae  mov  ch, byte ptr [eax + 0x498df2]
004441b4  test ch, ch
004441b6  jne  0x444138                            ; [i×16+0x498df2] != 0 → 跳过
004441b8  mov  byte ptr [eax + 0x498df5], ch       ; [i×16+0x498df5] = 0
004441be  mov  byte ptr [eax + 0x498df4], dh       ; [i×16+0x498df4] = 5（dh 在 0x444136 处已被置 5）
004441c4  jmp  0x444138
```

**5. 收尾**

```
004441c9  push 1
004441cb  push 0
004441cd  push 0
004441cf  call 0x41d476                            ; 0x41d476(0, 0, 1)
004441d7  jmp  0x4421ab                            ; mov eax,1 → 恒返回 1
```

`0x444136` 的 `mov dh,5` 在每次循环尾都执行（无论是「跳过」还是「已施加」），因此到达 `0x4441a9`（i >= 4）时 `dh` 必为 5；`dh` 在 `0x444199` 也被显式置 5。

**公式汇总**
```
card15_hibernate():
    cur = 0x49910c
    remove_card(cur, 15)
    say(cur, 3, line[chr(cur)][14])              # "#0440早睡早起\n身體好！"
    dh = 5
    for (i = 0; i < 8; i++):
        if (i < 4):
            if (i == cur) continue
            if (players[i].who_plays == 0) continue        # +0x15
            if (players[i].x == 0) continue                # +0x08
            if (dword[players[i] + 0x32] != 0) continue
            hostility_add(i, cur, 150 * [0x4990e8])
            byte[players[i] + 0x37] = 0     # 清除梦游
            byte[players[i] + 0x36] = 5     # 睡眠 5
            byte[players[i] + 0x42] += 5
        else:
            if ([i*16 + 0x498df2] != 0) continue
            [i*16 + 0x498df5] = 0
            [i*16 + 0x498df4] = 5
    refresh(0x41d476(0,0,1))
    return 1
```

`player+0x36`（`0x496b9e`）与 `player+0x37`（`0x496b9f`）的读取点：`0x44ef41`（`player_say`）开头 `cmp byte [player+0x496b9b],0 / jne 返回`、`cmp byte [player+0x496b9f],0 / jne 返回`、`cmp byte [player+0x496b9e],0 / jne 返回`（`0x44ef79`、`0x44ef86`、`0x44ef93`）——即处于消失/梦游/睡眠状态的玩家不会播台词；递减与 0x80 标记在 `0x41c84f` 内（`0x41cb04` 处理 `+0x36`、`0x41cb28` 处理 `+0x37`）。

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 没有其它符合条件的玩家 | 只扣卡 + 说台词 + `0x41d476(0,0,1)`，无任何玩家状态改变；仍返回 1（卡消耗） | `0x4440f6`、`0x4441c9`、`0x4441d7` |
| 当前行动玩家自己 | 循环里 `cmp ebx,[0x49910c] / je` 跳过，自己不会冬眠 | `0x44414d`、`0x44414f` |
| 空玩家槽（`player+0x15 == 0`） | 跳过 | `0x444154`、`0x44415b` |
| `player+0x08`（x 坐标）== 0 | 跳过（视为未落位） | `0x44415d`、`0x444165` |
| `dword[player+0x32] != 0` | 跳过（`+0x32`–`+0x35` 四个字节全为 0 才生效） | `0x444167`、`0x44416e` |
| 目标下标 >= 4 | 不检查 `who_plays`/坐标/`+0x32`，只看 `[i*16+0x498df2]` 是否为 0；为 0 时写 `+0x498df5 = 0`、`+0x498df4 = 5`，**不**做 `update_hostility` | `0x444142`、`0x444145`、`0x4441ae`–`0x4441c4` |
| 目标正被睡眠（`+0x36 != 0`）或梦游（`+0x37 != 0`） | 代码**不**排除这些状态；`+0x37` 被强制清 0、`+0x36` 被覆盖为 5 | `0x444167`、`0x444193`、`0x44419b` |
| 目标下标 >= 4 且 `[i*16+0x498df2] != 0` | 跳过（但 `dh` 仍被置 5，不影响其他玩家） | `0x4441b4`、`0x4441b6` |
| 玩家数 `[0x499114]` 小于 8 | 循环仍跑满 8 个槽，靠 `who_plays == 0`（下标 < 4）或 `[i*16+0x498df2]`（下标 >= 4）过滤 | `0x444139`、`0x444154`、`0x4441ae` |

#### 防御卡查询

**无**（函数体 `0x4440ea`–`0x4441db` 共 76 条指令，直接调用目标只有 `0x441343`、`0x44ef41`、`0x40df69`、`0x41d476` 四个，没有 `call 0x4413ad`，也没有间接调用）。

★★ **2026-09-19（第 104 条）通道 2 已整支驱动**（`rich4-spec/tests/test_hibernate_card.py`，21/21）
—— 上面「公式汇总」的每一条都被机器复现：四道闸（自己 / `who_plays==0` / `x==0` /
`dword[+0x32]!=0`）、`+0x36` **覆盖**为 5（已有 9 也盖）、`+0x37` 清 0、`+0x42 += 5`、
敌意 = `150 × [0x4990e8]`（只在玩家支）、替身槽（4..7）另一张表且**不记敌意**、
收尾 `0x41d476(0,0,1)`、恒返回 1。复刻侧 `packages/core/src/cards/hibernate.ts`
与之逐条一致（本轮无代码改动）。

附带确认：`player_say`（`0x44ef41`）在 `0x44ef79`–`0x44ef9a` 会因目标处于消失/梦游/睡眠状态而直接返回，所以本卡不会出现「让受害者念台词」的问题——本卡也确实没有对受害者调用 `0x44ef41`。

#### 未决

1. ~~`player+0x42`（`0x496baa`）的字段名与用途。~~ → **✅ 已结案**：= **「本月倒楣天數」**，月结屏读点 `0x4387bd` 给出中文字面 `"本月倒楣天數："`；全 exe 6 处 8 位累加（消失 / 住宿 / 監獄 / 醫院 / 冬眠卡 / 夢遊卡）+ 月结清零 `0x439ede`。复刻侧 = `Player.totalWinterSleepDays`（**名是早期的误名**，见 `rules/monthly.ts` 的头注释）。
2. `dword[player+0x32]` 的语义（本卡要求它为 0 才施法）。它被当 dword 读（`0x444167` 等）也被当 byte 写（`0x40e019` 写 `0x80`，`0x40e010` 读），没有单一的字段名证据。
3. ~~下标 >= 4 所用结构的身份与对应关系~~ → **✅ 已结案（2026-09-19，梦游卡通道 2 互证）**：
   替身记录 = `0x498de8 + i*16`，`+0x0a` = 状态（監獄/醫院闸）、**`+0x0c` = 冬眠天数**、
   **`+0x0d` = 梦游天数**、`+0x0e` = 停留（`0x498df6`，卡 14 写 1）。
   **判据**：本卡写 `+0x0c = 5`、清 `+0x0d`；梦游卡**先查 `+0x0c` 为 0** 才写 `+0x0d = 5`
   ⇒ 两者互斥、先到者说了算（详见 §卡 16 的「本轮顺带解出替身记录字段族」）。
   复刻侧映射：`SpecialActor.hibernating` ↔ `+12`、`sleepwalkDays` ↔ `+13`（`loaders/save.ts`）。
4. 下标 >= 4 分支是否可达：`0x499114 = [0x46cb3c] + 2`（`0x40715f`），`[0x46cb3c]` 的定义域未确认。
5. 全局 `0x4990e8` 的语义（同卡 12 未决第 4 条），此处作为 `150 × [0x4990e8]` 的敌意增量。
6. `0x40df69` 对「敌意增量为正且目标当前对施害者敌意为 0」时会不会额外触发什么（`0x40dfb5`–`0x40dfcf` 在 `delta > 0` 且 `player+0x41 == b+1` 时调用 `0x40cc1a`，即仅在两者已是盟友时执行）——本卡只调用 `0x40df69`，未展开 `0x40cc1a` 的语义。

`@source` `VA 0x4440ea`、`VA 0x4421ab`、`VA 0x475d5c+15*4`、`VA 0x47fdf2+14*8`、`VA 0x00466b24`、`VA 0x441343`、`VA 0x44ef41`、`VA 0x481272`、`VA 0x40df69`、`VA 0x41d476`、`VA 0x496b9e`、`VA 0x496b9f`、`VA 0x496baa`、`VA 0x496b9a`、`VA 0x498df2`、`VA 0x498df4`、`VA 0x498df5`、`VA 0x41cb04`、`VA 0x41cb28`、`VA 0x44ef79`、`VA 0x44ef93`、`VA 0x4990e8`、`VA 0x444372`、`VA 0x40715f`

---

## 二·续、逐卡规格（卡 27–30）

> 本节由子代理按 §0 的证据标准产出，主代理已逐条复核以下要点：
> ① `call 0x4413ad` 的穷举扫描确认这 4 张卡**都不查防御卡**；
> ② **抽验通过**：`0x419b09`/`0x419b0f`（`price_status != 0` → 过路费 `add ebp,ebp` 翻倍）、
>    `0x41d594`–`0x41d59c`（查封判定用高低半字节）、`0x41d5e9`（`xor ebx,ebx` 免收返回值）、
>    `0x445659`/`0x4456cb`/`0x4456d5`（写 `0x50`/`0x51`、`+0x1e` 清零）四条指令均与实际字节一致；
> ③ 台词 k=26/27（本卡持有人）、k=88（同盟）、k=89（乌龟）与 `0x48123a` 表实测一致。
>
> ⚠️ **对 `land-rent.md` 的直接补充**：该文档把 `price_status`（住宅 `+0x17`）标为
> 「语义与写入者未知」。本文现在给出**写入者与语义**：
>  - 卡 27 漲價卡 写 `0x50`（住宅 `+0x17` / 商業 `+0x1c`）→ `0x419b09`–`0x419b0f` 令**过路费 ×2**；
>  - 卡 28 查封卡 写 `0x51` → `0x41d559` 判定为「查封中」→ **过路费 0（免收）**，
>    并显示 `"房屋查封中 / 免收%s！"`（串 `0x463bb8`）。
>  即 `price_status` 的**低半字节**是关键：`0` = 正常、`1` = 查封免收；
>  「非 0」在住宅过路费代码里触发翻倍，但 `0x51` 在 `0x41d559` 被优先拦成免收。

### 卡 27 · 漲價卡

| 项 | 值 |
|---|---|
| 卡号 | 27（十进制）＝ `0x1b`（十六进制） |
| 卡名 VA | `0x00466b74`（`"漲價卡"`） |
| 函数 VA | `0x0044542d`（98 条指令，337 字节，`0x0044542d`..`0x0044557e`） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体无 `call 0x4413ad`） |
| 目标选择 | 自选地产（住宅或商业，**掩码参数 `0xe0c0006`**）；返回值为地产编号 |

函数表出处：`card_functions[]` @ `VA 0x00475dc8`（第 27 项）＝ `0x0044542d`；卡名表 `VA 0x0047fec2`（第 27 项 8 字节）＝ `74 6b 46 00 03 23 00 00`，首 dword `0x00466b74`。

#### 精确效果

**1. 选目标：人类走弹窗，电脑读 AI 全局**（`VA 0x00445431`）

```asm
00445431  imul  eax, dword ptr [0x49910c], 0x68   ; eax = &player[cur]（0x49910c 是 0 基下标）
00445438  cmp   byte ptr [eax + 0x496b7d], 1      ; player+0x15 = who_plays
0044543f  jne   0x44544d
00445441  push  0xe0c0006
00445446  call  0x446ae8                          ; 人类：弹窗自选目标
0044544b  jmp   0x445454
0044544d  push  0
0044544f  call  0x41e6f2                          ; 电脑：eax = [0x48be58 + 0]
```

`0x49910c` 是 **0 基**玩家下标：上面直接 `× 0x68` 后读 `player+0x15`，若是 1 基会读到下一个玩家的结构体。同证 `VA 0x00420d28`（`owner == 0x49910c + 1`，而 `land.owner` 是 1 基）。

`0xe0c0006` 的解码链：`0x446ae8`（`VA 0x00446aec`）→ `0x4018e7`（`VA 0x00401905` 起）→ `PostMessageA(hwnd, 0x401, 0, 参数)`（导入项 `[0x462310]`，`gen/imports.json`）；窗口过程 `0x445e4d` 在 `msg == 0x401` 分支（`VA 0x00445e86` → `0x445ec1`）取参数低 16 位：

```asm
00445ee1  xor   eax, eax
00445ee3  mov   ax, cx                  ; cx = 参数低 16 位 = 0x0006
00445ee6  mov   dword ptr [0x48c594], eax
```

低字节 `0x06` 是「可选对象位掩码」，在 `VA 0x00446235` 起逐个位验证：

```asm
0044624e  test  byte ptr [0x48c594], 2   ; bit1 → 住宅
00446257  cmp   ebx, 0x7d0 / 0044625d jle  / 0044625f cmp ebx, 0xfa0 / 00446265 jge
00446267  lea   eax, [ebx - 0x7d0]       ; 2000 < 值 < 4000 → 住宅，idx = 值-2000
0044627d  test  byte ptr [0x48c594], 4   ; bit2 → 商业
00446286  cmp   ebx, 0xfa0 / 0044628c jle / 0044628e cmp ebx, 0x1770 / 00446294 jge
00446296  lea   eax, [ebx - 0xfa0]       ; 4000 < 值 < 6000 → 商业，idx = 值-4000
```

即 `0x0006 = bit1|bit2` → **住宅与商业地产都可选**。高字节为 `0x00`，无确认处理器（`VA 0x0044630a`：`test byte ptr [0x48c595], 0xff` / `je 0x4465b6` → 直接接受）。

**2. 取消判定**（`VA 0x00445457`）

```asm
00445457  mov   ebp, eax
00445459  test  ebp, ebp
0044545b  je    0x44558c            ; 返回 0：使用失败，卡片不消耗
```

**3. 消耗手牌**（`VA 0x00445461`）

```asm
00445461  push  0x1b                ; 卡号 27
00445463  mov   ecx, dword ptr [0x49910c]
0044546a  call  0x441343            ; remove_card(player, card)
```

`0x441343` 只扫手牌 15 槽（`[0x499120 + player*15 + i]`，`VA 0x0044136d` `mov dl, byte ptr [eax + 0x499120]`），找到后把后面的牌前移（`0x456de8`）并清零尾槽；另有副作用 `VA 0x004413a2 inc byte ptr [edi + 0x499197]`（以卡号为下标的计数）。

**4. 台词**（`VA 0x00445492`）

```asm
00445492  mov   esi, dword ptr [eax + 0x4812a2]   ; eax = character*360；0x4812a2 = 台词表基址 0x48123a + 4*26
00445498  push  esi
00445499  push  0
004454a1  push  edi                               ; edi = [0x49910c] = 当前玩家
004454a2  call  0x44ef41                          ; player_say(cur, 0, 台词)
```

指针已解引用：`[0x4812a2]` = `0x004694be` = `"#0452小本經營\n恕不賒欠！！"`（台词表项 k=26，`k = 卡号 − 1`）。

**5. 改地产：住宅分支（`2000 < ebp < 4000`）**（`VA 0x004454b2`）

```asm
004454b2  cmp   ebp, 0xfa0               ; 4000
004454b8  jge   0x445516
004454ba  lea   edi, [ebp - 0x7d0]       ; idx = 值 - 2000
004454c0  imul  edi, edi, 0x34
004454c3  mov   ebx, dword ptr [0x498e84]  ; 住宅数组基址
004454c9  add   edi, ebx                   ; edi = &land[选中]
004454cb  mov   esi, 1
004454d0  add   ebx, 0x34                  ; ebx = &land[esi]（循环头，esi 从 1 起）
004454d3  cmp   esi, dword ptr [0x498e98]  ; num_lands
004454d9  jg    0x4454f6
004454db  lea   eax, [ebx + 4]             ; &land[esi].name
004454de  push  eax
004454df  lea   eax, [edi + 4]             ; &选中.name
004454e2  push  eax
004454e3  call  0x458370                   ; strcmp（已复核的字符串比较实现）
004454e8  add   esp, 8
004454eb  test  eax, eax
004454ed  jne   0x4454f3
004454ef  mov   byte ptr [ebx + 0x17], 0x50   ; ★ price_status = 0x50
004454f3  inc   esi
004454f4  jmp   0x4454d0
```

该循环**只比名字**：不检查 `owner`（`+0x19`）、也不检查 `+0x18`（type）。下标从 **1** 起（`+0x498e98` 为项数），选中的那块本身也在循环内。

**6. 改地产：商业分支（`4000 < ebp < 6000`）**（`VA 0x0044551e`）

```asm
0044551e  cmp   ebp, 0x1770            ; 6000
00445524  jge   0x44557e
00445526  lea   eax, [ebp - 0xfa0]     ; idx = 值 - 4000
0044552c  shl   eax, 3 / 00445531 shl eax, 3 / 00445534 sub eax, ebx   ; ×0x38
00445536  mov   ebx, dword ptr [0x498e88]   ; 商业数组基址
0044553c  add   ebx, eax
0044553e  mov   byte ptr [ebx + 0x1c], 0x50   ; ★ 只改这一块
```

**7. 收尾**（`VA 0x00445504` 人类 / `0x00445576` 电脑）

```asm
00445504  je    0x44557e              ; 人类：跳过落点动画
0044550a  push  0x64                  ; 第 6 参 = 100
0044550c  movsx ebx, word ptr [edi + 2]   ; land.y
00445511  movsx ebx, word ptr [edi]       ; land.x
0044555d  xor   ebx, ebx / 0044555f mov bx, word ptr [eax + 0x496b72]  ; cur.y
00445567  mov   ax, word ptr [eax + 0x496b70]                          ; cur.x
00445576  call  0x40e669              ; 0x40e669(0, cur.x, cur.y, land.x, land.y, 100)
```

共享尾声（不属于任何函数区间，位于卡 27 与卡 28 之间）：

```asm
0044557e  push  1 / 00445580 push 0 / 00445582 push 0
00445584  call  0x41d476              ; 0x41d476(0, 0, 1) 重绘
00445589  add   esp, 0xc
0044558c  mov   eax, ebp              ; ★ 返回值 = 选中的地产编号（非 0）
0044558e  pop ebp / 0044558f pop edi / 00445590 pop esi / 00445591 pop ebx
00445592  ret
```

**8. 该写入的实际效果（跨函数证据）**

住宅 `land + 0x17` 非 0 时，踩到该地产的过路费翻倍：

```asm
00419b09  cmp   byte ptr [esi + 0x17], 0   ; esi = 踩到的地块记录（0x34 步长数组）
00419b0d  je    0x419b11
00419b0f  add   ebp, ebp                   ; ★ 过路费 ×2
```

（`esi` 的记录里 `+0x18` 为 type、`+0x19` 为 owner、`+0x04` 为名字，见 `VA 0x00419ab6` / `0x00419abc` / `0x00419ac2`；`ebp` 是 `0x419744` 的返回值。）

此路径能被走到，前提是 `0x41d559` 返回 1（`VA 0x00419a92` `cmp eax, 1` / `00419a95 jne 0x41b077`）。而 `0x41d559` 里把「查封」定义为 **高、低半字节都非 0**：

```asm
0041d58d  mov   ah, byte ptr [esp + 0xa8]  ; ah = price_status
0041d594  test  ah, 0xf0
0041d597  je    0x41d5b3
0041d599  test  ah, 0xf
0041d59c  je    0x41d5b3                   ; 低半字节为 0 → 不算查封
```

`0x50` 的低半字节是 `0`，所以 `0x50` 不触发免收，只走到 `00419b0f` 的翻倍。

商业 `+0x1c` 另有一处同型 `×2` 分支（`VA 0x0041a446`：`cmp byte ptr [edx + 0x1c], 0` / `je` / `0041a44c add ebx, ebx`），但其入口条件链未追完，语义见卡 28「未决」第 1 条。

**公式汇总**
```
sel = (who_plays == 1) ? select_land(0xe0c0006) : [0x48be58]
if (sel == 0) return 0                      // 失败，卡不消耗
remove_card(cur, 27)                        // 0x441343
say(cur, 0, speech[cur.character][26])      // "#0452小本經營\n恕不賒欠！！"

if (2000 < sel < 4000) {                    // 住宅
    idx = sel - 2000
    for (i = 1; i <= num_lands; i++)
        if (strcmp(land[i].name, land[idx].name) == 0)
            land[i].price_status = 0x50     // 不限 owner、不限 type
} else if (4000 < sel < 6000) {             // 商业
    business[sel - 4000].+0x1c = 0x50       // 只改选中那一块
}                                           // 其它值：不改任何地块

if (who_plays != 1) animate(0, cur.x, cur.y, land.x, land.y, 100)
redraw(0, 0, 1)                             // 0x41d476
return sel                                  // 非 0
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 弹窗取消（`sel == 0`） | 返回 0，**卡片不消耗**，回到选卡界面 | `0x0044545b` → `0x0044558c` |
| `2000 < sel < 4000`（住宅） | 选中块及**所有同名住宅**的 `+0x17` 都写 `0x50`（不限 owner / type） | `0x004454ef` |
| `4000 < sel < 6000`（商业） | 只写选中那一块的 `+0x1c = 0x50` | `0x0044553e` |
| `sel == 2000` 或 `sel == 4000` | `jle` 命中 → 不改任何地块，但仍消耗卡并返回 `sel` | `0x004454b0` / `0x0044551c` |
| `sel <= 2000` 或 `sel >= 6000` | 不改任何地块，但仍消耗卡并返回 `sel` | `0x004454b0` / `0x00445524` |
| `num_lands == 0` | 循环体不执行，仅台词与收尾 | `0x004454d3` |
| 人类玩家 | 不做落点动画 | `0x00445504` |
| 电脑玩家 | 做落点动画后进尾声 | `0x00445576` |
| 目标地与玩家同格 | 无特判（不检查坐标） | 函数体无相关比较 |
| 过路费翻倍与「查封」互斥 | `0x50` 只翻倍；`0x51` 走不到翻倍（在 `0x41d559` 已被拦截） | `0x00419b0f` / `0x0041d594` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。函数体全部 `call` 目标：`0x446ae8`（`VA 0x00445446`）、`0x41e6f2`（`0x0044544f`）、`0x441343`（`0x0044546a`）、`0x44ef41`（`0x004454a2`）、`0x458370`（`0x004454e3`）、`0x40e669`（`0x00445576`）、`0x41d476`（共享尾声 `0x00445584`）。全 exe 中 `0x4413ad` 的调用点只有 18 处，位于 `0x419b32 / 0x41a3be / 0x41abde / 0x41fead / 0x424993 / 0x441210 / 0x4441dc / 0x4444bf / 0x4451f0`，与本卡无关。

#### 未决

1. `0x44ef41` 的**第 2 个实参**（本卡传 0）语义未确认。函数体确实使用参数区（`VA 0x0044f045` 处 `imul eax, dword ptr [esp + 0x2c], 0x34`，随后 `0x0044f050` 又按 12 字节步长取参），但该处 esp 已被 `push 0x82 / push 0xaa` 改变，且路径含分支，无法静态确定该处偏移对应第 1 还是第 2 个实参，故不下结论。
2. `price_status`（住宅 `+0x17` / 商业 `+0x1c`）的**高半字节**（`0x50`/`0x51` 的高位 `5`）含义未确认；只确认「低半字节为 0 → 不触发查封免收」、「非 0 → 过路费 ×2」。
3. 住宅循环会命中 `+0x18 != 0` 的项（未过滤 type）——原版如此；这些项是否可能是商业记录因而被误写 `+0x17`，未确认。

`@source` `VA 0x0044542d`、`VA 0x00446ae8`、`VA 0x00445e4d`、`VA 0x00446235`、`VA 0x0044627d`、`VA 0x0044630a`、`VA 0x00441343`、`VA 0x0044ef41`、`VA 0x00458370`、`VA 0x0040e669`、`VA 0x0041d476`、`VA 0x004812a2`、`VA 0x004694be`、`VA 0x00419b09`、`VA 0x0041d594`

---

### 卡 28 · 查封卡

| 项 | 值 |
|---|---|
| 卡号 | 28（十进制）＝ `0x1c`（十六进制） |
| 卡名 VA | `0x00466b7b`（`"查封卡"`） |
| 函数 VA | `0x00445593`（105 条指令，381 字节，`0x00445593`..`0x00445710`） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体无 `call 0x4413ad`） |
| 目标选择 | 自选地产（住宅或商业，**掩码参数 `0xe0c0006`**）；返回值为地产编号 |

函数表出处：`card_functions[]` @ `VA 0x00475dcc`（第 28 项）＝ `0x00445593`；卡名表 `VA 0x0047feca` 首 dword `0x00466b7b`。

#### 精确效果

**1. 选目标**（`VA 0x00445597`）与卡 27 逐字节同形，参数也是 `0xe0c0006`（住宅＋商业都可选）：

```asm
00445597  imul  eax, dword ptr [0x49910c], 0x68
0044559e  cmp   byte ptr [eax + 0x496b7d], 1
004455a5  jne   0x4455b3
004455a7  push  0xe0c0006 / 004455ac call 0x446ae8
004455b3  push  0 / 004455b5 call 0x41e6f2
```

**2. 取消判定**（`VA 0x004455bd`）

```asm
004455bd  mov   ebp, eax
004455bf  test  ebp, ebp
004455c1  je    0x44558c            ; 返回 0，卡片不消耗
```

**3. 消耗手牌**（`VA 0x004455c3`）

```asm
004455c3  push  0x1c                ; 卡号 28
004455c5  mov   ecx, dword ptr [0x49910c]
004455cc  call  0x441343            ; remove_card(cur, 28)
```

**4. 台词**（`VA 0x004455f4`）

```asm
004455f4  mov   esi, dword ptr [eax + 0x4812a6]   ; 0x4812a6 = 0x48123a + 4*27（k=27）
004455fa  push  esi
004455fb  push  0
004455fd  mov   edi, dword ptr [0x49910c]
00445604  call  0x44ef41                          ; player_say(cur, 0, 台词)
```

指针已解引用：`[0x4812a6]` = `0x004694d9` = `"#0453年度回饋，全面免費！"`。**注意**：这是该卡在台词表中的原文，字面语义与「查封」不符，此处如实照录，不做解释。

**5. 改地产：住宅分支**（`VA 0x0044560c`）

```asm
0044560c  cmp   ebp, 0x7d0 / 00445612 jle 0x44569a
00445618  cmp   ebp, 0xfa0 / 0044561e jge 0x44569a
00445624  lea   edi, [ebp - 0x7d0]
0044562a  imul  edi, edi, 0x34
0044562d  mov   ebx, dword ptr [0x498e84]
00445635  mov   esi, 1
0044563a  add   ebx, 0x34
0044563d  cmp   esi, dword ptr [0x498e98]
00445643  jg    0x445660
0044564d  call  0x458370                   ; strcmp(选中.name, land[esi].name)
00445655  test  eax, eax
00445657  jne   0x44565d
00445659  mov   byte ptr [ebx + 0x17], 0x51   ; ★ price_status = 0x51
0044565d  inc   esi / 0044565e jmp 0x44563a
```

与卡 27 相同的「按名字批量写、从下标 1 起、不过滤 owner/type」结构，只把值换成 `0x51`。

**6. 改地产：商业分支**（`VA 0x004456a6`）——比卡 27 多一步

```asm
004456a6  cmp   ebp, 0x1770 / 004456ac jge 0x44557e
004456b2  lea   eax, [ebp - 0xfa0]        ; idx = 值 - 4000
004456b8  shl   eax, 3 / 004456bd shl eax, 3 / 004456c0 sub eax, ebx   ; ×0x38
004456c4  mov   eax, dword ptr [0x498e88]
004456c9  add   eax, ebx
004456cb  mov   byte ptr [eax + 0x1c], 0x51   ; ★ 查封标记
004456cf  cmp   byte ptr [eax + 0x18], 4      ; ★ 商业子类型 == 4 ？
004456d3  jne   0x4456d9
004456d5  mov   byte ptr [eax + 0x1e], 0      ; ★ 额外把 +0x1e 清零
```

**7. 收尾**（`VA 0x0044566e` 人类 / `0x00445695`、`0x0044570b` 电脑）

人类 `je 0x44557e` 直接进共享尾声；电脑分支把参数拼好后 **`jmp 0x445573`** —— 跳进**卡 27 函数体内部**（`0x00445573` 的 `push eax / push 0 / call 0x40e669`），随后落到共享尾声 `0x44557e`：

```asm
00445690  and   eax, 0xffff
00445695  jmp   0x445573                  ; 住宅电脑分支
00445702  xor   eax, eax
00445704  mov   ax, word ptr [ebx + 0x496b70]   ; cur.x
0044570b  jmp   0x445573                  ; 商业电脑分支
```

尾声与卡 27 相同（`0x44557e..0x445592`：`push 1 / push 0 / push 0 / call 0x41d476` → `mov eax, ebp` → `ret`），返回值是选中地产编号。

**8. 该写入的实际效果（跨函数证据）**

`0x51` 的高、低半字节都非 0，因此命中 `0x41d559` 的「查封」判定：

```asm
0041d58d  mov   ah, byte ptr [esp + 0xa8]   ; ah = price_status = 0x51
0041d594  test  ah, 0xf0 / 0041d597 je 0x41d5b3
0041d599  test  ah, 0xf  / 0041d59c je 0x41d5b3    ; 0x51 & 0xf = 1 → 不跳
0041d59e  push  esi / 0041d59f push 0x463bb8 / 0041d5a9 call 0x457110   ; sprintf
0041d5e9  xor   ebx, ebx                            ; ★ 返回值 = 0
0041d6e5  mov   eax, ebx / 0041d6f0 ret
```

格式串已解引用：`0x00463bb8` = `"房屋查封中\n\n免收%s！"`。

调用方据此**免收过路费**：

```asm
00419a8a  call  0x41d559
00419a92  cmp   eax, 1
00419a95  jne   0x41b077            ; ★ 非 1 → 跳到不做收费的分支
```

商业地 `+0x1c` 的读取点在 `VA 0x0041a446` 与 `0x0041a4a2`（`cmp byte ptr [edx + 0x1c], 0` / `je` / `0041a44c add ebx, ebx`），指令形状是**翻倍**而非免收；其完整入口条件链不在本函数内，故语义见本节「未决」第 1 条。

**公式汇总**
```
sel = (who_plays == 1) ? select_land(0xe0c0006) : [0x48be58]
if (sel == 0) return 0                       // 失败，卡不消耗
remove_card(cur, 28)                         // 0x441343
say(cur, 0, speech[cur.character][27])       // "#0453年度回饋，全面免費！"

if (2000 < sel < 4000) {                     // 住宅
    idx = sel - 2000
    for (i = 1; i <= num_lands; i++)
        if (strcmp(land[i].name, land[idx].name) == 0)
            land[i].price_status = 0x51
} else if (4000 < sel < 6000) {              // 商业
    c = &business[sel - 4000]
    c.+0x1c = 0x51
    if (c.+0x18 == 4) c.+0x1e = 0
}                                            // 其它值：不改任何地块

if (who_plays != 1) animate(0, cur.x, cur.y, land.x, land.y, 100)   // 经 0x445573
redraw(0, 0, 1)                              // 0x41d476
return sel                                   // 非 0
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 弹窗取消（`sel == 0`） | 返回 0，**卡片不消耗** | `0x004455c1` → `0x0044558c` |
| `2000 < sel < 4000`（住宅） | 选中块及**所有同名住宅**的 `+0x17` 都写 `0x51`（不限 owner / type） | `0x00445659` |
| `4000 < sel < 6000`（商业） | 写选中块 `+0x1c = 0x51` | `0x004456cb` |
| 商业块 `+0x18 == 4` | 额外写 `+0x1e = 0` | `0x004456cf` / `0x004456d5` |
| 商业块 `+0x18 != 4` | 不写 `+0x1e` | `0x004456d3` |
| `sel == 2000` 或 `sel == 4000` | 不改地块，仍消耗卡并返回 `sel` | `0x00445612` / `0x004456a0` |
| `sel <= 2000` 或 `sel >= 6000` | 不改地块，仍消耗卡并返回 `sel` | `0x00445612` / `0x004456ac` |
| 人类玩家 | 不做落点动画 | `0x0044566e` |
| 过路费 | 变成 **0（免收）**，并显示 `"房屋查封中\n\n免收%s！"` | `0x0041d599` / `0x00463bb8` / `0x00419a95` |
| 商业地免收的对应判定 | 在 `0x41a3be` 内另有 `[edx+0x1c]` 非 0 → `add ebx, ebx`（翻倍）路径，与住宅不同，本卡规格未展开 | `0x0041a446` / `0x0041a4a2` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。函数体全部 `call` 目标：`0x446ae8`（`VA 0x004455ac`）、`0x41e6f2`（`0x004455b5`）、`0x441343`（`0x004455cc`）、`0x44ef41`（`0x00445604`）、`0x458370`（`0x0044564d`）、`0x40e669`（经 `0x00445695`/`0x0044570b` 跳入 `0x00445573`）、`0x41d476`（共享尾声 `0x00445584`）。

#### 未决

1. **商业地 `+0x1c` 非 0 时 `0x41a446`/`0x41a4a2` 是翻倍还是免收**：该判定与住宅的 `0x41d559` 不是同一段代码，其进入条件链未逐条追完，故只报告指令事实，不下语义结论。
2. 商业 `+0x18 == 4` 时清零 `+0x1e` 的**后果**未确认。已知 `+0x1e` 是一个倒数计数：`VA 0x0041cdb0` 读、`0x0041cdd6` 自减（`mov al, cl / dec al / mov byte ptr [ebx + 0x1e], al`），且只在 `[ebx+0x18] == 4`、`owner == cur+1`、`[ebx+0x1d] <= [ebx+0x1a]` 时自减；清零即令该计数不再前进。
3. 台词表 k=27 的原文 `"#0453年度回饋，全面免費！"` 与「查封」语义不符——只确认指针与取址，未找到解释。
4. `0x44ef41` 第 2 个实参（本卡传 0）语义未确认（同卡 27 未决 1）。

`@source` `VA 0x00445593`、`VA 0x00446ae8`、`VA 0x00441343`、`VA 0x0044ef41`、`VA 0x00458370`、`VA 0x004456cb`、`VA 0x004456d5`、`VA 0x0041d559`、`VA 0x00463bb8`、`VA 0x00419a95`、`VA 0x0041cdb0`、`VA 0x0041cdd6`、`VA 0x0041a446`

---

### 卡 29 · 同盟卡

| 项 | 值 |
|---|---|
| 卡号 | 29（十进制）＝ `0x1d`（十六进制） |
| 卡名 VA | `0x00466b82`（`"同盟卡"`） |
| 函数 VA | `0x00445710`（130 条指令，463 字节，`0x00445710`..`0x004458df`） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体无 `call 0x4413ad`） |
| 目标选择 | 选一名玩家（**掩码参数 `0xe0c0410`**，弹窗层面禁止选自己）；返回值为玩家位掩码 |

函数表出处：`card_functions[]` @ `VA 0x00475dd0`（第 29 项）＝ `0x00445710`；卡名表 `VA 0x0047fed2` 首 dword `0x00466b82`。

#### 精确效果

**1. 选目标**（`VA 0x00445717`）

```asm
00445717  imul  eax, dword ptr [0x49910c], 0x68
0044571e  cmp   byte ptr [eax + 0x496b7d], 1        ; who_plays
00445725  jne   0x445733
00445727  push  0xe0c0410
0044572c  call  0x446ae8                            ; 人类
00445731  jmp   0x44573a
00445733  push  0
00445735  call  0x41e6f2                            ; 电脑：eax = [0x48be58]
```

`0xe0c0410` 低 16 位 = `0x0410`：低字节 `0x10` = bit4，在 `VA 0x004462b3` 只放行**玩家**：

```asm
004462b3  test  byte ptr [0x48c594], 0x10
004462bc  test  bh, 0x80            ; 选中值必须有 bit15（0x8000 | 1<<idx）
004462c1  test  bl, 0xff            ; 低字节非 0
004462c7  call  0x40d293            ; ctz → 玩家下标
004462cf  cmp   eax, 4 / 004462d2 jge 0x4462e2     ; idx>=4 → 有效
004462d9  cmp   byte ptr [eax + 0x496b7d], 0       ; idx<4 要求 who_plays != 0
```

高字节 `0x04` → 确认处理器索引 3（`VA 0x00446319`：`and eax, 0xff00 / shr eax, 8 / dec eax / cmp eax, 7 / ja`，跳表 `VA 0x00445e2d` 第 4 项 = `0x00446434`）。该处理器**禁止选自己**：

```asm
00446434  test  bl, 0xf
00446437  je    0x4465b6             ; 无玩家位 → 拒绝
0044643d  mov   cl, byte ptr [0x49910c]
00446443  mov   eax, 1
00446448  shl   eax, cl              ; 1 << cur
0044644a  test  ebx, eax
0044644c  jne   0x4465b6             ; ★ 选中值包含当前玩家 → 拒绝
00446452  jmp   0x4465ba             ; 接受
```

**2. 取消判定**（`VA 0x0044573d`）

```asm
0044573d  mov   esi, eax            ; esi = 玩家位掩码
0044573f  test  esi, esi
00445741  je    0x4458d8            ; → mov eax, esi（=0）→ 失败，卡不消耗
```

**3. 消耗手牌**（`VA 0x00445747`）

```asm
00445747  push  0x1d                ; 卡号 29
00445749  mov   ecx, dword ptr [0x49910c]
00445750  call  0x441343            ; remove_card(cur, 29)
```

**4. 使用者台词 + 求目标下标 + 落点动画**（`VA 0x00445778`）

```asm
00445778  mov   edi, dword ptr [eax + 0x4812aa]   ; 0x4812aa = 0x48123a + 4*28（k=28）
0044577e  push  edi / 0044577f push 3 / 00445781 mov ebp,[0x49910c] / 00445787 push ebp
00445788  call  0x44ef41                          ; player_say(cur, 3, 台词)
00445790  push  esi / 00445791 call 0x40d293      ; ctz(掩码) → 目标下标
00445796  mov   ebx, eax / 0044579b mov dword ptr [esp], eax   ; 存到本地
0044579e  imul  eax, dword ptr [0x49910c], 0x68
004457a5  cmp   byte ptr [eax + 0x496b7d], 1
004457ac  je    0x4457e8                          ; 人类：跳过落点动画
004457e0  call  0x40e669                          ; 0x40e669(0, cur.x, cur.y, tgt.x, tgt.y, 100)
```

台词指针已解引用：`[0x4812aa]` = `0x004694f4` = `"#0454好哥兒們！！"`。

**5. 解除双方原有同盟**（`VA 0x004457e8`）

```asm
004457ef  mov   bl, byte ptr [eax + 0x496ba9]     ; bl = cur.allied_player（1 基，0 = 无）
004457f5  test  bl, bl
004457f7  je    0x445827
004457fb  mov   dl, bl / 004457fd dec edx / 004457fe imul ebx, edx, 0x68
00445803  mov   byte ptr [ebx + 0x496ba9], cl     ; 旧盟友.allied_player = 0
00445815  mov   byte ptr [ebx + 0x496ba5], cl     ; 旧盟友.+0x3d = 0
0044581b  mov   byte ptr [eax + 0x496ba9], cl     ; cur.allied_player = 0
00445821  mov   byte ptr [eax + 0x496ba5], cl     ; cur.+0x3d = 0
00445827  imul  eax, dword ptr [esp], 0x68        ; &target
0044582b  cmp   byte ptr [eax + 0x496ba9], 0
00445832  je    0x445866
00445842  mov   byte ptr [ebx + 0x496ba9], cl     ; 目标旧盟友.allied_player = 0
00445854  mov   byte ptr [ebx + 0x496ba5], cl     ; 目标旧盟友.+0x3d = 0
0044585a  mov   byte ptr [eax + 0x496ba9], cl     ; target.allied_player = 0
00445860  mov   byte ptr [eax + 0x496ba5], cl     ; target.+0x3d = 0
```

即**双向拆链**：若使用者或目标原本已有盟友，先把双方的 `allied_player` 与 `+0x3d` 都清零（不会留下单向悬挂的链接）。

**6. 建立新同盟**（`VA 0x00445866`）

```asm
00445866  mov   dl, byte ptr [esp] / 00445869 inc dl      ; dl = 目标下标 + 1（1 基）
0044586b  mov   edi, dword ptr [0x49910c]
00445871  imul  eax, edi, 0x68
00445874  mov   byte ptr [eax + 0x496ba9], dl             ; cur.allied_player = 目标+1
0044587a  mov   byte ptr [eax + 0x496ba5], 7              ; cur.+0x3d = 7
00445881  mov   al, byte ptr [0x49910c] / 00445886 inc al ; al = cur + 1
0044588b  imul  ebx, ebp, 0x68                            ; ebp = 目标下标
0044588e  mov   byte ptr [ebx + 0x496ba9], al             ; target.allied_player = cur+1
00445894  mov   byte ptr [ebx + 0x496ba5], 7              ; target.+0x3d = 7
```

**7. 切镜头、目标台词、收尾**（`VA 0x0044589b`）

```asm
0044589b  push  edi / 0044589c call 0x41d433   ; 0x41d433(cur)：暂设 0x49910c=cur 并重绘后还原
004458a1  add   esp, 4
004458a4  mov   bl, byte ptr [ebx + 0x496b7b]   ; ebx = &target → target.character
004458c1  mov   edx, dword ptr [eax + 0x48139a] ; 0x48139a = 0x48123a + 4*88（k=88）
004458c7  push  edx / 004458c8 push 0 / 004458ca push ebp
004458cb  call  0x44ef41                        ; player_say(target, 0, 台词)
004458d3  call  0x41d546                        ; 清 [0x48be18] 并重绘
004458d8  mov   eax, esi                        ; 返回值 = 玩家位掩码（非 0）
004458da  jmp   0x442afa                        ; 卡 4 換地卡 的尾声
```

`0x442afa` 尾声（`VA 0x00442afa`）：`add esp, 4 / pop ebp / pop edi / pop esi / pop ebx / ret`，`eax` 即返回值。

目标台词指针已解引用：`[0x48139a]` = `0x004696e1` = `"#0476可別想占我\n便宜！"`。

**8. 该写入的实际效果（跨函数证据）**

★★ **通道 2 已差分**（2026 本轮，`tests/test_alliance.py` 15/15，直接 `call 0x0040cc1a`）
—— 解除同盟的**四条实测**（`cards.md` 上面那段 4 连清与它同构）：

| 行为 | 实测 |
|---|---|
| 双向清 | 自己与盟友的 `+0x3d`/`+0x41` 四格全清，其它玩家不动 |
| ★ **不看对方是否指回自己** | `p0→p1` 而 `p1→p2` 时，`p1` 的两格照样被清 |
| ★ **不追链** | 只清一层：盟友的「盟友」不动 |
| 自指（`+0x41 == 自己+1`） | 把自己清两遍，无副作用 |

> ⚠️⚠️ **`allied_player == 0` 时原版没有护栏**：`edx = 0-1 = -1` ⇒ 写到
> `0x496ba9 - 0x68 = **0x496B41**` 与 `0x496ba5 - 0x68 = **0x496B3D**`，
> **越界清掉这两格**（实测：从 `0xAA`/`0xBB` 变 0）。这两格的语义
> **PRD 里没有**（`0x496b30` 那一片只确认了「在狱」等少数几个）。
> 复刻 `rules/hostility.ts` 的 `breakAlliance` 加了提前返回 ⇒ **有意偏离**（已登记）；
> 两个调用方目前都保证「有盟友才调」，故该分支不可达。

`allied_player`（`player+0x41`）成立 → **对盟友免收过路费**：

```asm
0041d5b3  imul  eax, dword ptr [esp + 0xa4], 0x68
0041d5bd  mov   cl, byte ptr [eax + 0x496ba9]   ; 地主.allied_player
0041d5c3  mov   edx, dword ptr [0x49910c]
0041d5c9  inc   edx                              ; cur + 1
0041d5ca  cmp   ecx, edx
0041d5cc  jne   0x41d5f0
0041d5cf  ... push 0x463bcd ... call 0x457110
0041d5e9  xor   ebx, ebx                         ; 返回 0 → 免收
```

格式串已解引用：`0x00463bcd` = `"與%s同盟中\n\n免收%s！"`；调用方免收逻辑同卡 28（`VA 0x00419a92` `cmp eax,1` / `00419a95 jne 0x41b077`）。

`+0x3d` 是**同盟剩余天数**，每回合为双方互加好感（降低敌意）：

```asm
0041cbdc  cmp   byte ptr [esi + 0x496ba5], 0    ; esi = &player[ebx]
0041cbe3  je    0x41cc48
0041cbe5  mov   edx, dword ptr [0x4990e8]       ; price_index
0041cbed  shl   eax, 2 / 0041cbf0 add eax, edx / 0041cbf2 shl eax, 2 / 0041cbf5 neg eax
                                                ; delta = -(price_index * 20)
0041cbfa  mov   al, byte ptr [esi + 0x496ba9] / 0041cc00 dec eax
0041cc03  call  0x40df69                        ; update_hostility(ebx, ally, -20*price_index)
0041cc1e  push  ebx / 0041cc21 mov al, [esi+0x496ba9] / 0041cc27 dec eax
0041cc29  call  0x40df69                        ; 反方向同样一次
0041cc31  mov   ch, byte ptr [esi + 0x496ba5]
0041cc37  dec   ch
0041cc39  mov   byte ptr [esi + 0x496ba5], ch   ; ★ 天数 −1
0041cc3f  jne   0x41cc48
0041cc41  mov   byte ptr [esi + 0x496ba5], 0x80 ; ★ 到期哨兵
```

这里的第 3 参 `push eax`（`VA 0x0041cbf7`）是**按 32 位整数**压栈的 `-(price_index*20)`，不是卡 3/卡 8 那种按 8 字节 double 压栈的情形。

到期哨兵 `0x80` 在 `VA 0x0041cace` 被处理：

```asm
0041cace  test  byte ptr [eax + 0x496ba5], 0x80
0041cad5  je    0x41cae0
0041cad7  push  ebx / 0041cad8 call 0x40cc1a
```

**公式汇总**
```
mask = (who_plays == 1) ? select_player(0xe0c0410) : [0x48be58]   // 弹窗禁止选中自己
if (mask == 0) return 0                       // 失败，卡不消耗
remove_card(cur, 29)                          // 0x441343
say(cur, 3, speech[cur.character][28])        // "#0454好哥兒們！！"
t = ctz(mask)                                 // 0x40d293
if (who_plays != 1) animate(0, cur.x, cur.y, t.x, t.y, 100)

if (cur.allied_player != 0) {                 // 拆掉使用者原有同盟（双向）
    a = cur.allied_player - 1
    player[a].allied_player = 0 ; player[a].+0x3d = 0
    cur.allied_player   = 0 ; cur.+0x3d   = 0
}
if (player[t].allied_player != 0) {           // 拆掉目标原有同盟（双向）
    b = player[t].allied_player - 1
    player[b].allied_player = 0 ; player[b].+0x3d = 0
    player[t].allied_player = 0 ; player[t].+0x3d = 0
}

cur.allied_player     = t + 1 ;  cur.+0x3d     = 7    // 同盟 7 回合
player[t].allied_player = cur + 1 ; player[t].+0x3d = 7

switch_current_player_index_to(cur) ; redraw   // 0x41d433
say(t, 0, speech[player[t].character][88])     // "#0476可別想占我\n便宜！"
reset_ai_target(); redraw                      // 0x41d546
return mask                                    // 非 0
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 弹窗取消（`mask == 0`） | 返回 0，**卡片不消耗** | `0x00445741` → `0x004458d8` |
| 选到自己 | 弹窗层拒绝（`test ebx, eax` 命中 → 交回 `0x4465b6`，取消本次确认），因此卡函数里不会出现 `t == cur` | `0x00446448` / `0x0044644c` |
| 使用者原本有盟友 | 先双向清除旧链接与旧 `+0x3d`，再建新链 | `0x004457fb`..`0x00445821` |
| 目标原本有盟友 | 同上，反向清除 | `0x00445834`..`0x00445860` |
| 双方本来就是盟友 | 先各清一次再重建，最终仍是「互为盟友、`+0x3d = 7`」 | `0x00445827` / `0x00445874` |
| `+0x3d` 计数 | 建链时写 **7**（十进制）；每回合由 `0x40df69` 互加好感后自减 1；减到 0 写 `0x80` | `0x0044587a` / `0x0041cc39` / `0x0041cc41` |
| 人类玩家 | 不做落点动画 | `0x004457ac` |
| 目标角色下标 | `target.character = player[t]+0x13`，用于取 k=88 台词 | `0x004458a4` / `0x004458c1` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。函数体全部 `call` 目标：`0x446ae8`（`VA 0x0044572c`）、`0x41e6f2`（`0x00445735`）、`0x441343`（`0x00445750`）、`0x44ef41`（`0x00445788`、`0x004458cb`）、`0x40d293`（`0x00445791`）、`0x40e669`（`0x004457e0`）、`0x41d433`（`0x0044589c`）、`0x41d546`（`0x004458d3`）。

★★ **2026-09-19（第 108 条）通道 2 已整支驱动**（`rich4-spec/tests/test_stock_alliance_cards.py`，40/40）：
「公式汇总」与「边界情况」逐条被机器复现 ——

- 人类选框参数实测 **`0xe0c0410`**；掩码 → 目标 = `ctz`（`0b100 ⇒ 2 号`）；
- 调用序列实测 **选人 → 扣卡 → 台词**，且返回**掩码**（4）；
- 台词两条都对着**真表**核过：使用者 = 表 B 槽 28 `"#0454好哥兒們！！"`、
  被选者 = 表 B 槽 88 `"#0476可別想占我\n便宜！"`；
- ★★ **双向拆旧链**三种组合实测：自己原有 / 目标原有 / **双方互为旧盟** ——
  最终都是「互为盟友、`+0x3d = 7`」，不留单向悬挂；
- 掩码 0 ⇒ 返回 0、**不扣卡**、一句话都不说；
- 落点动画**只给 AI**（`0x40e669(0, cur.xy, tgt.xy, 0x64)`），人类不播；
  `0x41d433(cur)` + 收尾 `0x41d546()` 各一次。

#### 未决

1. `0x41d559` 的第 3 个实参 `[0x47517c]`（在 `0x00419a7c` 被压栈，作为 `sprintf` 的 `%s`）来源与含义未确认。
2. `0x44ef41` 第 2 个实参（本卡第一次传 **3**、第二次传 **0**）语义未确认，两次取值不同但同一函数同一调用点形状，无法从被调方确定差异。
3. 弹窗对 `0xe0c0410` 与 `0xe0c0010` 的差别只确认了「高字节 0x04 → 多一个禁选自己的处理器」；`0x0410` 的低字节为 `0x10`，与 `0xe0c0010` 相同，未发现其它差别。
4. 好感度变化量的单位（为何是 `price_index × 20`）未确认，只确认指令序列与符号（`neg eax`）。

`@source` `VA 0x00445710`、`VA 0x00446ae8`、`VA 0x004462b3`、`VA 0x00446319`、`VA 0x00445e2d`、`VA 0x00446434`、`VA 0x00441343`、`VA 0x0044ef41`、`VA 0x004694f4`、`VA 0x004696e1`、`VA 0x0040d293`、`VA 0x0040e669`、`VA 0x0041d433`、`VA 0x0041d546`、`VA 0x00442afa`、`VA 0x0041d5bd`、`VA 0x00463bcd`、`VA 0x0041cbdc`、`VA 0x0041cc41`、`VA 0x0041cace`

---

### 卡 30 · 烏龜卡

| 项 | 值 |
|---|---|
| 卡号 | 30（十进制）＝ `0x1e`（十六进制） |
| 卡名 VA | `0x00466b89`（`"烏龜卡"`） |
| 函数 VA | `0x004458df`（108 条指令，366 字节，`0x004458df`..`0x00445a4d`） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体无 `call 0x4413ad`） |
| 目标选择 | 选一名玩家（含自己，**掩码参数 `0xe0c0010`**）；返回值为玩家位掩码 |

函数表出处：`card_functions[]` @ `VA 0x00475dd4`（第 30 项，最后一项）＝ `0x004458df`；卡名表 `VA 0x0047feda` 首 dword `0x00466b89`。函数上界由 `0x004458df + 366 = 0x00445a4d` 得出，`0x00445a4d` 正是下一个函数（在 `VA 0x0041ce25` 被调用）。

#### 精确效果

**1. 选目标**（`VA 0x004458e3`）

```asm
004458e3  imul  eax, dword ptr [0x49910c], 0x68
004458ea  cmp   byte ptr [eax + 0x496b7d], 1
004458f1  jne   0x4458ff
004458f3  push  0xe0c0010
004458f8  call  0x446ae8                       ; 人类
004458ff  push  0 / 00445901 call 0x41e6f2     ; 电脑：eax = [0x48be58]
```

`0xe0c0010` 低 16 位 = `0x0010`：低字节 `0x10` = bit4，只放行**玩家**（判定同卡 29，`VA 0x004462b3`）；高字节 `0x00` → **无确认处理器**（`VA 0x0044630a`：`test byte ptr [0x48c595], 0xff` / `je 0x4465b6` → 直接接受）。因此**允许选中自己**，与卡 29 的 `0xe0c0410` 形成对照。

**2. 取消判定**（`VA 0x00445909`）

```asm
00445909  mov   edi, eax
0044590b  test  edi, edi
0044590d  je    0x4440e3            ; → mov eax, edi（=0）→ 失败，卡不消耗
```

**3. 求目标下标 + 消耗手牌**（`VA 0x00445913`）

```asm
00445913  push  edi / 00445914 call 0x40d293   ; ctz(掩码) → 目标下标
00445919  mov   ebx, eax / 0044591e mov esi, eax
00445920  push  0x1e                           ; 卡号 30
00445922  mov   ecx, dword ptr [0x49910c]
00445929  call  0x441343                       ; remove_card(cur, 30)
```

**4. 使用者台词（仅当目标不是自己）+ 落点动画**（`VA 0x00445931`）

```asm
00445931  mov   ebp, dword ptr [0x49910c]
00445937  cmp   ebx, ebp
00445939  je    0x445969                       ; ★ 目标 == 自己 → 不说这句
00445957  mov   ecx, dword ptr [eax + 0x4812ae] ; 0x4812ae = 0x48123a + 4*29（k=29）
0044595d  push  ecx / 0044595e push 3 / 00445960 push ebp
00445961  call  0x44ef41                       ; player_say(cur, 3, 台词)
00445969  imul  eax, dword ptr [0x49910c], 0x68
00445970  cmp   byte ptr [eax + 0x496b7d], 1
00445977  je    0x4459b7                       ; 人类：跳过落点动画
004459af  call  0x40e669                       ; 0x40e669(0, cur.x, cur.y, tgt.x, tgt.y, 100)
```

台词指针已解引用：`[0x4812ae]` = `0x00469506` = `"#0455瞧你那溫吞\n的模樣！"`。

**5. 目标下标 < 4（玩家 1–4）的两种分支**（`VA 0x004459b7`）

```asm
004459b7  cmp   esi, 4
004459ba  jge   0x445a3e                       ; 见第 6 步
004459c0  imul  ebx, esi, 0x68                 ; ebx = &player[目标]
004459c3  cmp   esi, dword ptr [0x49910c]
004459c9  jne   0x445a02                       ; → 目标不是自己

; ---- 目标是自己 ----
004459e4  mov   ecx, dword ptr [eax + 0x481326] ; 0x481326 = 0x48123a + 4*59（k=59）
004459ea  push  ecx / 004459eb push 3 / 004459ed push esi
004459ee  call  0x44ef41                       ; player_say(自己, 3, 台词)
004459f6  mov   byte ptr [ebx + 0x496ba1], 2   ; ★ player+0x39 = 2
004459fd  jmp   0x4440e3

; ---- 目标是别人 ----
00445a1b  mov   edx, dword ptr [eax + 0x48139e] ; 0x48139e = 0x48123a + 4*89（k=89）
00445a21  push  edx / 00445a22 push 2 / 00445a24 push esi
00445a25  call  0x44ef41                       ; player_say(目标, 2, 台词)
00445a2d  mov   byte ptr [ebx + 0x496ba1], 3   ; ★ player+0x39 = 3
00445a34  call  0x41d546
00445a39  jmp   0x4440e3
```

台词指针已解引用：
- `[0x481326]` = `0x00469559` = `"#0459慢慢走\n比較保險！"`（对自己）
- `[0x48139e]` = `0x004696f8` = `"#0477急驚風遇到\n慢郎中∼"`（对别人）

`player+0x39` = `0x496ba1` = `days_tortoise_walking`（`rich4-remake/tools/disasm.py` 的字段名表，`VA 0x004459f6` 独立复核一致）。

**6. 目标下标 >= 4 的分支**（`VA 0x00445a3e`）

```asm
00445a3e  shl   esi, 4
00445a41  mov   byte ptr [esi + 0x498df7], 3   ; ★ 0x498df7 + 目标下标*16 = 3
00445a48  jmp   0x4440e3
```

该地址属于玩家 4–7 的**并行状态数组**：`VA 0x0041c858` 取玩家下标、`VA 0x0041c85f` `cmp ebx, 4` / `0x0041c862 jge 0x41ce39`，随后 `VA 0x0041ce42 sub ebx, 4`，再用 `VA 0x0041ceb7` `test byte ptr [eax + 0x498e37], 0x80` 等按 16 字节步长处理 4 个计时字节。代数上 `0x498e34 + (p−4)*16 + 3 = 0x498df7 + p*16`，与本卡写入式一致。

**7. 收尾**：三条路径都跳到卡 14 停留卡的尾声 `0x4440e3`（`VA 0x004440e3`）：

```asm
004440e3  mov   eax, edi            ; ★ 返回玩家位掩码（非 0）
004440e5  pop   ebp / 004440e6 pop edi / 004440e7 pop esi / 004440e8 pop ebx / 004440e9 ret
```

**8. 该写入的实际效果（跨函数证据）**

`player+0x39` 非 0 → **该玩家本回合移动步数被强制为 1**：

```asm
0040dd6a  ; who_plays & 0x30 等前置判定之后
0040dd7e  cmp   byte ptr [edx + 0x496ba1], 0    ; player+0x39
0040dd85  jne   0x40dd40
0040dd40  mov   dword ptr [0x48baf8], 1         ; ★ 步数 = 1
0040dd4a  mov   byte ptr [eax + 0x498ea2], 1
```

对照组（正常情况）在同一函数里由随机数决定 `VA 0x0040de50`：`call 0x456f2d` → `idiv 9` → `add edx, 2` → `mov dword ptr [0x48baf8], edx`，即 **2..10 步**。玩家 4–7 由并行数组走同一条路：

```asm
0040de1a  cmp   byte ptr [eax + 0x498df6], 0   ; 并行数组 +2
0040de34  cmp   byte ptr [eax + 0x498df7], 0   ; ★ 并行数组 +3（本卡写入的字段）
0040de3b  je    0x40de50
0040de3d  mov   dword ptr [0x48baf8], 1        ; 同样只走 1 步
```

计数字段的过期哨兵 `0x80` 在 `VA 0x0041ca7e` 被清回 0：

```asm
0041ca7e  test  byte ptr [eax + 0x496ba1], 0x80
0041ca85  je    0x41ca8f
0041ca87  xor   dl, dl / 0041ca89 mov byte ptr [eax + 0x496ba1], dl
```

另一处读取 `VA 0x0041726b`：`cmp byte ptr [eax + 0x496ba1], 0` / `je` / `00417274 mov ebx, 4`（否则 `0x41725f mov ebx, 2`），是移动节奏相关参数，用途未确认（见未决）。

**公式汇总**
```
mask = (who_plays == 1) ? select_player(0xe0c0010) : [0x48be58]   // 允许选中自己
if (mask == 0) return 0                        // 失败，卡不消耗
t = ctz(mask)                                  // 0x40d293
remove_card(cur, 30)                           // 0x441343

if (t != cur)
    say(cur, 3, speech[cur.character][29])     // "#0455瞧你那溫吞\n的模樣！"
if (who_plays != 1) animate(0, cur.x, cur.y, t.x, t.y, 100)

if (t < 4) {
    if (t == cur) {
        say(t, 3, speech[player[t].character][59])   // "#0459慢慢走\n比較保險！"
        player[t].+0x39 = 2                          // days_tortoise_walking = 2
    } else {
        say(t, 2, speech[player[t].character][89])   // "#0477急驚風遇到\n慢郎中∼"
        player[t].+0x39 = 3                          // days_tortoise_walking = 3
        reset_ai_target(); redraw                    // 0x41d546
    }
} else {
    *(byte *)(0x498df7 + t*16) = 3                   // 玩家 4..7 的并行计时字段
}
return mask                                    // 非 0
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 弹窗取消（`mask == 0`） | 返回 0，**卡片不消耗** | `0x0044590d` → `0x004440e3` |
| 目标为自己且下标 < 4 | 写 `player+0x39 = 2`（十进制），说 `"#0459慢慢走\n比較保險！"` | `0x004459f6` / `0x004459ee` |
| 目标为别人且下标 < 4 | 写 `player+0x39 = 3`（十进制），说 `"#0477急驚風遇到\n慢郎中∼"`，并 `0x41d546` | `0x00445a2d` / `0x00445a25` / `0x00445a34` |
| 目标下标 >= 4 | 写 `0x498df7 + 目标*16 = 3`，**不论目标是不是自己都是 3**（与下标 < 4 的自己写 2 不一致） | `0x00445a41` |
| 目标为自己时 | 不说使用者的 `"#0455瞧你那溫吞的模樣！"`（`cmp ebx, ebp` / `je`） | `0x00445937` / `0x00445939` |
| 人类玩家 | 不做落点动画 | `0x00445977` |
| 目标已经处于乌龟状态 | 直接覆盖为新值（2 或 3），不做叠加 | `0x004459f6` / `0x00445a2d` / `0x00445a41` |
| 目标下标计算 | `0x40d293` 对 `x & 0xff == 0` 返回 `0xffffffff`；本卡在此前已用 `test edi, edi` / `je` 排除掩码 0 的情况 | `0x0040d297` / `0x0044590d` |
| 移动步数 | `player+0x39 != 0` → 本回合固定走 **1** 步（正常为 2..10） | `0x0040dd7e` / `0x0040dd40` / `0x0040de50` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。函数体全部 `call` 目标：`0x446ae8`（`VA 0x004458f8`）、`0x41e6f2`（`0x00445901`）、`0x40d293`（`0x00445914`）、`0x441343`（`0x00445929`）、`0x44ef41`（`0x00445961`、`0x004459ee`、`0x00445a25`）、`0x40e669`（`0x004459af`）、`0x41d546`（`0x00445a34`）。

#### 未决

1. `+0x39` 写 **2**（对自己）与 **3**（对别人）的差别是否有其他读取者依赖具体数值，未确认。已确认的读取者（`0x40dd7e`、`0x40de34`、`0x41faf7`、`0x4210ed`、`0x421223`、`0x42185b`）都是「非 0 判定」，因此数值 2/3 只在倒数天数上体现；`0x41cb4c` 起每回合自减 1 是唯一逐个数值敏感的处理。
2. 目标下标 >= 4 时**固定写 3**（即使目标是自己），与下标 < 4 的「自己写 2」不一致；这是原版行为，但设计意图未确认。
3. `VA 0x0041726b` 处 `+0x39 != 0 → ebx = 4`（否则 2）的用途未确认；该处上下文含 `GetCursorPos`（`VA 0x004172a6` 附近）与显示代码，只确认指令事实。
4. `0x44ef41` 第 2 个实参（本卡传 3 或 2）语义未确认。
5. 并行数组 `0x498df4 + p*16` 的 4 个计时字节与 `player+0x36..+0x39` 的一一对应关系，只确认了 `+0x498df7 ↔ player+0x39`（乌龟）与 `+0x498df6 ↔ player+0x38`（停留）；`+0`、`+1` 两个字节对应哪两个字段未确认。

`@source` `VA 0x004458df`、`VA 0x0044590d`、`VA 0x00445937`、`VA 0x00445977`、`VA 0x004459b7`、`VA 0x004459c3`、`VA 0x004459f6`、`VA 0x00445a2d`、`VA 0x00445a41`、`VA 0x00445a48`、`VA 0x004440e3`、`VA 0x00446ae8`、`VA 0x004462b3`、`VA 0x0044630a`、`VA 0x00441343`、`VA 0x0044ef41`、`VA 0x00469506`、`VA 0x00469559`、`VA 0x004696f8`、`VA 0x0040d293`、`VA 0x0040dd7e`、`VA 0x0040dd40`、`VA 0x0040de34`、`VA 0x0040de50`、`VA 0x0041c85f`、`VA 0x0041ce42`、`VA 0x0041ceb7`、`VA 0x0041ca7e`、`VA 0x0041726b`

---

## 二·续、逐卡规格（卡 22–26）

> 本节由子代理按 §0 的证据标准产出，主代理已逐条复核以下要点：
> ① `call 0x4413ad` 的穷举扫描：卡 22/23/24/25 **不查防御卡**，卡 26 **查 免費卡(20) → 嫁禍卡(19)**（`0x445310`/`0x445341`），与本文件 §「防御卡机制总览」的矩阵一致；
> ② 台词索引 k=21（送神符）、k=22（請神符）、k=23（紅卡）、k=24（黑卡）、k=25（查稅卡）、k=85（查稅受害者）与 `0x48123a` 表实测一致；
> ③ 抽验通过：`0x4452d7`（`fmul qword [0x4653d8]`，`0x4653d8` 的 f64 实测 = **0.2**）、`0x44534e`（`cmp [esp+0x94], 0x7d0` = 2000 门限）、`0x445360`（`push 0; push 2; push ebx` → `0x44476a` 的 mode 2）、`0x4454ef`/`0x44553e`（写 `0x50`）均与实际字节一致；
> ④ 卡 24/25 的股票记录：基址 `0x496980`、步长 **36(0x24)**、`+0x07` = 趋势字节（紅卡写 `0x20`、黑卡写 `2`）、`+0x14` = 现价（float）、`+0x00` = 股票名指针（已实测 `0x466b63`=「紅卡」… 由 `0x47feaa` 等预解析指针间接引用）。

### 卡 22 · 送神符

| 项 | 值 |
|---|---|
| 卡号 | 22 |
| 卡名 VA | `0x00466b55`（`"送神符"`） |
| 函数 VA | `0x00444c45`（66 条指令，213 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体与全部被调函数内均无 `call 0x4413ad`） |
| 目标选择 | 无（固定作用于当前行动玩家 `[0x49910c]`） |

#### 精确效果

1. 取当前行动玩家结构并清标记：`00444c49 xor ebx, ebx`；`00444c4b imul eax, dword ptr [0x49910c], 0x68`（玩家基址 `0x496b68`，步长 `0x68`）。`ebx` 是「本次是否真的送走了神」的标记（0=什么都没做）。
2. **第二神明槽 `player+0x40`**：`00444c52 mov dl, byte ptr [eax + 0x496ba8]`（`0x496ba8 - 0x496b68 = 0x40`）。若 `dl != 0`：
   - `00444c58 test dl, dl` / `00444c5a je 0x444c71`
   - `00444c5c mov al, dl` / `00444c5e and eax, 0xff` / `00444c63 push eax` / `00444c64 call 0x40e14d` —— 以该字节为 **神明/物品 ID** 调用 `0x40e14d`，把该神从玩家身上拆下并放回地图。
   - `00444c6c mov ebx, 1`。
3. **主神明槽 `player+0x3f`（`god_info`）**：`00444c78 mov dh, byte ptr [eax + 0x496ba7]`（`0x496ba7 - 0x496b68 = 0x3f`）。`00444c7e test dh, dh` / `00444c80 je 0x444cd3`（无神明则直接进入失败判定）。
4. **查神明类别**：`00444c89 lea edx, [eax - 1]`（`eax` 此处 = `god_info`）、`00444c8e shl eax, 2`、`00444c91 sub eax, edx`（`eax = (god-1)*3`）、`00444c93 mov al, byte ptr [eax*8 + 0x496d08]`（`eax*8 = (god-1)*24`）→ 读 `god_table[god-1].type`。神明表基址 `0x496d08`，每项 24 字节，`type` 在 `+0`；该 `type` 由数据表 `0x47ed3c` 初始化（`00407d57 mov dl, byte ptr [ebx + 0x47ed3c]`、`00407d5d mov byte ptr [eax*8 + 0x496d08], dl`）。
5. **类别门槛**：`00444c9f`~`00444cbb` 依次 `cmp eax, 5 / 6 / 7 / 8 / 0xa / 0xf` 并 `je 0x444cbd`，最后一次 `00444cbb jne 0x444cd3`。命中集合 `{5,6,7,8,0xa,0xf}` 时：
   - `00444cbd mov ebx, dword ptr [0x49910c]` / `00444cc3 push ebx` / `00444cc4 call 0x40e32c` —— 带演出动画的送神；`0x40e32c` 在动画结束后执行 `0040e5fe mov eax, dword ptr [esp + 0x2c]` / `0040e602 inc eax` / `0040e603 push eax` / `0040e604 call 0x40e14d`，才真正拆除神明。
   - `00444ccc mov ebx, 1`，`00444cd1 jmp 0x444cdb` 跳到消耗卡的分支。
6. **失败判定**：`00444cd3 test ebx, ebx` / `00444cd5 je 0x443069`。`0x443069` 是共享收尾：`00443069 mov eax, ebx` / `0044306b pop ebp`…`0044306f ret`，此时 `ebx=0` → **返回 0 = 使用失败，卡片不消耗**。
7. 移除手牌：`00444cdb push 0x16`（0x16 = 十进制 22）/ `00444cdd mov esi, dword ptr [0x49910c]` / `00444ce4 call 0x441343`（`0x441343(player, card)` = 在 15 格手牌中删除该卡）。**注意此步在第 6 步失败判定之后**。
8. 取角色台词：`00444cf5 xor edx, edx` / `00444cf7 mov dl, byte ptr [eax + 0x496b7b]`（`+0x13` = `character`）/ `00444d0e mov ebp, dword ptr [eax + 0x48128e]`。`0x48128e = 0x48123a + 360*character + 4*21`，即第 21 条台词；`character=0` 时解引用得 `"#0447快滾！\n我不需要你！"`。
9. 说台词并返回成功：`00444d15 jmp 0x44305e` → `0044305e push 0` / `00443060 push edi`（`edi = [0x49910c]`，见 `00444cec mov edi, dword ptr [0x49910c]`）/ `00443061 call 0x44ef41`（`player_say(cur, 0, 台词)`）→ 落到 `0x443069`，此时 `ebx=1` → 返回 1 = 成功。

**公式汇总**
```
cur   = [0x49910c]
ok    = 0
g2    = player[cur].byte[0x40]                     ; 第二神明槽
if (g2 != 0) { detach_god(g2); ok = 1 }            ; 0x40e14d
g1    = player[cur].byte[0x3f]                     ; god_info
if (g1 != 0) {
    t = god_table[g1-1].type                       ; byte [0x496d08 + (g1-1)*24]
    if (t==5 || t==6 || t==7 || t==8 || t==10 || t==15) {
        detach_god_animated(cur); ok = 1           ; 0x40e32c → 内部 0x40e14d(g1)
    }
}
if (ok == 0) return 0                              ; 失败，卡不消耗
remove_card(cur, 22)                               ; 0x441343
say(cur, 0, speech[player[cur].character][21])     ; 0x48123a + 360*ch + 4*21
return 1
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| `player+0x3f==0` 且 `player+0x40==0`（没有任何神明/物品） | 直接返回 0，卡片不消耗，回到选卡界面重选 | `0x444c80`、`0x444cd5` |
| `player+0x3f!=0` 但类别不属于 `{5,6,7,8,0xa,0xf}`，且 `player+0x40==0` | **什么都不做**，返回 0，卡片不消耗（例：附身大財神 `god_info=2`、天使 `god_info=9`、土地公 `god_info=12` 时送神符无效） | `0x444cbb`、`0x444cd5` |
| `player+0x3f!=0` 类别不属于该集合，但 `player+0x40!=0` | 只送走 `player+0x40` 那一只（`0x40e14d`），卡片照常消耗并说台词 | `0x444c64`、`0x444c6c`、`0x444cd3` |
| 两个槽都有值 | 先 `0x40e14d(player+0x40)`，再 `0x40e32c(cur)`（内部再拆 `god_info`），两只都送走 | `0x444c64`、`0x444cc4`、`0x40e604` |
| 类别命中 `0xa`（ID 10 = 惡魔） | 走 `0x40e32c`，但 `0x40e32c` 内部的「+`say`」分支只覆盖类别 `{5,6,7,8,0xf}`（`0040e618`~`0040e62f`），故惡魔被送走时**不追加该句台词** | `0x40e618`、`0x40e62f` |
| 类别命中 `0xf`（ID 15 = 死神；ID 16 = 路障同类） | `0x40e32c` 追加台词表 `0x4808a6 + 108*character` 的第 0 条（`0040e64a mov ecx, dword ptr [edx + eax*8 + 0x4808a6]`，`character=0` 时为 `"#1073一場惡夢∼"`） | `0x40e631`、`0x40e64a` |
| 神明表 `type` 与 ID 的对应 | `type = 0x47ed3c[ID-1]`；ID 1..14 → type 1..14；ID 15(死神) 与 ID 16(路障) 同为 type 15；ID 17..26 → type 16；27..36 → type 17；37..46 → type 18。因此门槛最终覆盖 ID `{5,6,7,8,10,15,16}` = 小窮神、大窮神、小衰神、大衰神、惡魔、死神（路障仅在理论上同类） | `0x47ed3c`、`0x407d57` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。

函数自身的被调函数只有 `0x40e14d`、`0x40e32c` 两个（`00444c64`、`00444cc4`），二者的被调函数集合分别为 `{}` 与 `{0x40e14d}`，都不含 `0x4413ad`。只有 `0x441343`（移除手牌，`0x4413ad` 的调用者之一在别处）不参与本卡。

★★ **2026-09-19（第 106 条）通道 2 已整支驱动**（`rich4-spec/tests/test_god_charm_cards.py`，48/48，
与卡 23 同一支）：上面「公式汇总」与「边界情况」逐条被机器复现 ——

- **第二槽 `+0x40` 先处理、无类型判定**（`0x40e14d(该字节)` 原样传参，type=0 也照送）；
- **主槽 `+0x3f` 走白名单**：扫 `type = 0..18`，只有 `{5,6,7,8,0xa,0xf}` 命中并调 `0x40e32c(cur)`
  （**不是** `0x40e14d`），其余 13 个 type 一律**返回 0**；
- **`ebx` 是布尔不是计数**：两个槽都送走时返回值仍是 `1`；
- **扣卡与台词严格在送走之后**（序列 `0x40e14d → remove_card(22) → say`）；
- **台词指针来自卡牌台词表**（下表 B 的 `k = 卡号-1 = 21`），实测指向 `"#0447快滾！\n我不需要你！"`。

#### 未决

1. `player+0x40`（第二神明槽）具体存放哪一个神明/物品 ID。已确认 `0x40e14d` 只在 `type == 0x12` 分支清空它（`0040e1cd xor eax, eax` / `0040e1d5 dec eax` / `0040e1db mov byte ptr [eax + 0x496ba7], bl` 附近的 `0040e1b2 mov byte ptr [eax + 0x496ba8], cl`），而 `type 0x12` 对应 ID 37..46；名称表 `0x47ed76` 只覆盖到下标 18（ID 18 = 定時炸彈），ID 37..46 的名称在数据段中不存在，无法给出该槽位的确定名称。
2. `player+0x44`/`player+0x46`/`player+0x48`（神明加成字段，`0x40ead7` 加、`0x40e14d` 减，表 `0x4749e2`/`0x474a06`/`0x474a2a` 按 `type` 索引）的字段语义未确认；仅能确认其数值（例：`type 9`(天使) 为 `-100, +60, +60`，`type 10`(惡魔) 为 `+100, -60, -60`，`type 15`(死神) 为 `+1000, -200, -200`）。
3. 本卡对 ID 16（路障）的实际可达性：路障的 `type` 也是 15，会通过门槛，但未见任何代码把路障写入 `player+0x3f`，故「送神符能否送走路障」未确认。

`@source` `VA 0x444c45`、`VA 0x444cd5`、`VA 0x443069`、`VA 0x40e14d`、`VA 0x40e32c`、`VA 0x47ed3c`、`VA 0x47ed76`、`VA 0x4749e2`

---

### 卡 23 · 請神符

| 项 | 值 |
|---|---|
| 卡号 | 23 |
| 卡名 VA | `0x00466b5c`（`"請神符"`） |
| 函数 VA | `0x00444e1a`（81 条指令，267 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体与全部 15 条神明附身分支内均无 `call 0x4413ad`） |
| 目标选择 | 选**地图上的一个神明/物品**（不是玩家、不是地产）：人类自动取最近的一个（`0x444d1a`），AI 读 `[0x48be58]`（`0x41e6f2(0)`） |

#### 精确效果

1. 分派人类/AI 的选神：
   - `00444e1e imul eax, dword ptr [0x49910c], 0x68` / `00444e25 cmp byte ptr [eax + 0x496b7d], 1`（`+0x15` = `who_plays`。1 = 人类）/ `00444e2c jne 0x444e35`
   - 人类：`00444e2e call 0x444d1a`（无参数，内部自行选神），返回 `eax` = 神明 ID（1-based），没有可选目标时返回 0。
   - AI：`00444e35 push 0` / `00444e37 call 0x41e6f2`（`0041e6f2 mov eax, dword ptr [esp + 4]` / `0041e6f6 mov eax, dword ptr [eax*4 + 0x48be58]`）→ 取 `[0x48be58]` 作为神明 ID。
2. `00444e3f mov esi, eax` / `00444e41 test esi, esi` / `00444e43 je 0x44468a`。`0x44468a` 是共享收尾 `0044468a mov eax, esi` / `0044468c pop ebp`…`ret` → 返回 0 = **失败，卡片不消耗**。
3. 移除手牌：`00444e49 push 0x17`（0x17 = 23）/ `00444e4b mov ecx, dword ptr [0x49910c]` / `00444e52 call 0x441343`。
4. 说台词：`00444e7a mov edi, dword ptr [eax + 0x481292]`（`0x481292 = 0x48123a + 360*character + 4*22`，第 22 条；`character=0` 时解引用得 `"#0448快來幫我吧！"`）/ `00444e80 push edi` / `00444e81 push 0` / `00444e89 push ebp`（`ebp = [0x49910c]`）/ `00444e8a call 0x44ef41`（`player_say(cur, 0, 台词)`）。
5. 记住并临时清空该神在地图上的节点：
   - `00444e92 lea eax, [esi - 1]` / `00444e95 mov ebx, eax` / `00444e97 shl ebx, 2` / `00444e9a sub ebx, eax` → `ebx = (god-1)*3`
   - `00444e9e mov di, word ptr [ebx*8 + 0x496d0a]` —— `god_table[god-1].node_id`（`0x496d0a = 0x496d08 + 2`，即 `+0x2` 的 word）
   - `00444ea8 mov word ptr [ebx*8 + 0x496d0a], dx`（`00444ea6 xor edx, edx`）→ 先把 node_id 清 0。
6. 镜头与出场动画：
   - `00444eb0 push 1` / `00444eb2 push 0` / `00444eb4 push 0` / `00444eb6 call 0x41d476` → `0x41d476(0, 0, 1)`
   - `00444ebe push 0`；`00444ec0 imul eax, dword ptr [0x49910c], 0x68`；`00444ec9 mov dx, word ptr [eax + 0x496b72]`（`player+0xa`，当前玩家 y）；`00444ed1 mov ax, word ptr [eax + 0x496b70]`（`player+0x8`，当前玩家 x）
   - `00444ee8 mov edx, dword ptr [0x498e80]`（地图格表基址）+ `00444ee5 shl eax, 3` 等 → 地址 = `[0x498e80] + node_id*40`（`0x498e80` 是基址指针，格步长 `0x28` = 40）
   - `00444ef0 movsx edx, word ptr [eax + 2]`（目标格 y）、`00444ef5 movsx eax, word ptr [eax]`（目标格 x）
   - `00444ef9 push esi` / `00444efa call 0x40e669` → 实参顺序为 `0x40e669(god, 目标格x, 目标格y, 玩家x, 玩家y, 0)`（`esi` 是最后一个 push，即第 1 个参数）
7. 复原节点：`00444f02 mov word ptr [ebx*8 + 0x496d0a], di`（写回第 5 步保存的 node_id）。
8. 附身：`00444f0a push esi`（神明 ID）/ `00444f0b xor eax, eax` / `00444f0d mov ax, di`（node_id）/ `00444f11 mov ecx, dword ptr [0x49910c]` / `00444f17 push ecx` / `00444f18 call 0x40ead7` → `0x40ead7(cur, node_id, god)`。该函数内部完成：
   - 校验神明可否被请（`0040eaf1 call 0x40ea62`，见下节公式）；
   - 清掉该神在地图上的节点 `0040eb21 xor edx, ebx` / `0040eb23 mov word ptr [eax*8 + 0x496d0a], dx`；
   - `0040eb5e imul ebx, dword ptr [esp + 0x94], 0x68` / `0040eb66 mov byte ptr [ebx + 0x496ba7], al` → `player+0x3f = god`；
   - `0040eb7d mov dx, word ptr [ebx + 0x496b74]`（`player+0x0c` = `node_id`）/ `0040eb84 mov word ptr [eax + 0x496d0a], dx` → 神的 node 跟随玩家；
   - `0040eb94 mov byte ptr [eax + 0x496d0d], dl`（`dl = 玩家下标+1`）→ `god_table[god-1].owner = 玩家下标+1`；
   - `0040eb9a cmp esi, 0xf`（`esi` = type）/ `0040eb9f mov byte ptr [eax + 0x496d0c], 0xd` / `0040eba8 mov byte ptr [eax + 0x496d0c], 7` → `god_table[god-1].+4` 写 13（type==15 时）否则 7；
   - `0040ebc7 mov byte ptr [edx + eax*8 + 0x26], 0` → 若旧 node_id 非 0，清掉原地图格的标记；
   - `0040ebd4 mov dx, word ptr [esi*2 + 0x4749e2]` / `0040ebdc add word ptr [eax + 0x496bac], dx`；`0040ebeb` 用 `0x474a06` 加 `player+0x46`；`0040ebfa` 用 `0x474a2a` 加 `player+0x48`；
   - `0040ec01 lea edx, [esi - 1]` / `0040ec07 ja 0x40ece6` / `0040ec0d jmp dword ptr [edx*4 + 0x40ea9b]` → type ≤ 15 时跳 15 项神明附身效果表（type 1..15 分别对应 `0x40ec14`、`0x40ecf1`、`0x40ed8f`、`0x40ee50`、`0x40ef1b`、`0x40efe4`、`0x40f083`、`0x40f155`、`0x40f205`、`0x40f258`、`0x40ece6`、`0x40f2a0`、`0x40ece6`、`0x40ece6`、`0x40f2eb`；其中 `0x40ece6` 为空桩）。
9. 收尾：`00444f20 jmp 0x444685` → `00444685 call 0x41d546` / `0044468a mov eax, esi`（`esi` = 神明 ID ≠ 0）→ 返回非 0 = **成功**。

人类选神函数 `0x444d1a`（256 字节）要点：
- `00444d23 mov dword ptr [esp + 8], 0x461c4000`（初值 `0x461c4000` = `float 1.0e4`）作为「最小距离」；
- `00444d2b push -1` / `00444d2d call 0x40a45c` → `0x40a45c(-1)` 把 `[0x474938]` 里所有非 0 的 word 收集进数组 `0x48b8c4` 并返回个数（`0040a469 xor esi, esi` / `0040a46b mov edi, 0x1b8`，即遍历 0x1b8 = 440 个格子）；
- 循环每一项：`00444d43 mov ax, word ptr [ebx*2 + 0x48b8c4]` / `00444d4b test ah, 0x80`（高位置 1 表示该格有神明）/ `00444d54 test ah, 0x7f`（神明 ID 非 0）/ `00444d67 sar eax, 8` → `esi` = 神明 ID；
- `00444d70 call 0x40ea62`（能否被请神）+ `00444d8e cmp byte ptr [eax + 0x496d0d], 0`（`god_table[god-1].owner == 0`，即该神当前没有附在别人身上）；
- `00444d99 mov dx, word ptr [eax + 0x496d0a]`（神的 node）/ `00444daa mov eax, dword ptr [0x498e80]` → 目标格坐标；`00444dbf mov di, word ptr [eax + 0x496b70]`、`00444dca mov ax, word ptr [eax + 0x496b72]` → 玩家坐标；
- `00444de6 fild dword ptr [esp + 0xc]` / `00444dea call 0x4582bc`（平方根）/ `00444df7 fcomp dword ptr [esp + 4]` / `00444dfe jbe 0x444e0a`，取距离最小者：`00444e08 mov ebp, esi`；
- `00444e10 mov eax, ebp` 返回；无合格目标时 `ebp` 初值 0（`00444d21 xor ebp, ebp`）→ 返回 0。

**公式汇总**
```
cur = [0x49910c]
god = (player[cur].who_plays == 1) ? nearest_summonable_free_god()   /* 0x444d1a */
                                   : [0x48be58]                      /* 0x41e6f2(0) */
if (god == 0) return 0                                                /* 失败，卡不消耗 */
remove_card(cur, 23)
say(cur, 0, speech[player[cur].character][22])
node = god_table[god-1].node_id        ; word [0x496d0a + (god-1)*24]
god_table[god-1].node_id = 0
camera(0, 0, 1)                        ; 0x41d476
animate(0x40e669, god, cell_x(node), cell_y(node), player[cur].x, player[cur].y, 0)
god_table[god-1].node_id = node
attach_god(cur, node, god)             ; 0x40ead7
camera_end()
return god                             ; 非 0 = 成功

/* 0x40ead7(cur, node, god) */
if (god == 0) return
if (0x40ea62(god) == 0) return          ; type==0xb(11=惡犬) 或 type==0xf(15=死神/路障) 不可请
god_table[god-1].node_id = 0
if (player[cur].god_info != 0) 0x40e32c(cur)      ; 先送走原来的神
player[cur].god_info = god
god_table[god-1].node_id = player[cur].node_id
god_table[god-1].owner   = cur + 1
god_table[god-1].+4      = (type == 0xf) ? 13 : 7
if (node != 0) map_cell/node 的标记 [+0x26] = 0
player[cur].+0x44 += 0x4749e2[type]
player[cur].+0x46 += 0x474a06[type]
player[cur].+0x48 += 0x474a2a[type]
if (type <= 15) jmp god_attach_effect[type-1]      ; 0x40ea9b 15 项跳表
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 人类玩家，地图上没有任何可请的神（无高位置 1 的格子，或全部 `owner != 0`，或全被 `0x40ea62` 否决） | `0x444d1a` 返回 0 → `00444e43 je 0x44468a` → 返回 0，卡片不消耗 | `0x444d21`、`0x444e43`、`0x444e10` |
| AI 路径 `[0x48be58] == 0` | 同上，返回 0 | `0x444e37`、`0x444e43` |
| 神明的 `type` 为 `0xb`(11) 或 `0xf`(15) | `0x40ea62` 返回 0：`0040ea83 cmp eax, 0xc` / 分支 ⇒ 仅 `type != 0xb && type != 0xf` 时 `edx = 1`。人类路径在 `0x444d70` 就把它排除；AI 路径则由 `0x40ead7` 的 `0040eafb je 0x40ece6` 静默放弃（此时卡已消耗、台词已说，`player+0x3f` 不变） | `0x40ea62`、`0x444d70`、`0x40eafb` |
| 该神已附在别的玩家身上（`god_table[god-1].owner != 0`） | 人类路径跳过（`00444d8e cmp byte ptr [eax + 0x496d0d], 0` / `00444d95 jne 0x444e0a`）；AI 路径不检查，会直接把神从原主人身上抢过来（`0x40ead7` 里 `player[cur].god_info` 若非 0 会先 `0x40e32c` 送走自己原有的神） | `0x444d8e`、`0x40eb3e` |
| 玩家原本已有神 | `0x40ead7` 内 `0040eb35 cmp byte ptr [eax + 0x496ba7], 0` / `0040eb3e push edi` / `0040eb3f call 0x40e32c` → 先把旧神送走 | `0x40eb35`、`0x40eb3f` |
| 玩家没有原神，也没有 node 需要清理 | `arg2(node_id) == 0` 时跳过清格标记（`0040ebb6 test ecx, ecx` / `0040ebb8 je 0x40ebcc`） | `0x40ebb6` |
| 附身效果表为空桩的类别 | `type 11(惡犬)`、`type 13(禮物)`、`type 14(寶箱)` 的跳表项都指向 `0x40ece6`（空收尾） | `0x40ea9b`、`0x40ece6` |
| 台词索引 | `0x48123a + 360*character + 4*22`；`character=0` 时 `"#0448快來幫我吧！"`，`character=1` 时 `"#0500天靈靈地靈靈！"`，`character=2` 时 `"#0552有請諸神降臨！"` | `0x444e7a` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。

被调链已逐个核对：`0x444d1a` → `{0x40a45c, 0x40ea62, 0x4582bc}`；`0x40ead7` → `{0x40e32c, 0x40ea62, 0x41d476}`；`0x40e32c` → `{0x40e14d}`；15 条神明附身效果分支（`0x40ec14`…`0x40f2eb`）的被调函数集合为 `{0x40e2a2, 0x41d2c6, 0x41d3f4, 0x41d476, 0x440cac, 0x41e12, 0x41e77, 0x41ece, 0x41f21, 0x44ef41, 0x44f230, 0x44f354, 0x450441, 0x45144f, 0x456e11, 0x457110, 0x45b3f}`，全都不含 `0x4413ad`。故請神符即使请到的是附身效果里会夺取别人资产的恶神，也不查任何防御卡。

★★ **2026-09-19（第 106 条）通道 2 已整支驱动**（`rich4-spec/tests/test_god_charm_cards.py`，48/48）——
整条编排（选神 → 扣卡 → 台词 → 镜头 → 动画 → **node 摘掉/挂回** → 附身）被机器复现：

- **两条选神路径**：`who_plays == 1` 走 `0x444d1a()`（无实参）、否则 `0x41e6f2(0)`（实参实测为 `0`）；
  返回 0 ⇒ **返回 0 且卡不消耗**（失败支）。
- **返回值是神明 ID**（`eax = esi`），不是布尔 1；实测换一个神返回值跟着变。
- **动画期先摘 node**：在 `0x40e669` 被调用的**那一刻**读 `god_table[god-1].node` 实测为 **0**，
  到 `0x40ead7` 被调用的**那一刻**已挂回原值 ⇒ 「暂存 → 清零 → 挂回」三步得到实证
  （复刻侧把这套归给表现层 `client/render.ts` 的「正在飞的那一件要藏起来」，与本结论一致）。
- **`0x40e669` 六实参**：`(god, 目标格 x, 目标格 y, 玩家 x, 玩家 y, 0)` —— 坐标分别读
  `[0x498e80] + node*40` 的 `+0/+2` 与玩家 `+0x08/+0x0a`；**第 6 参确实是 0**。
- **卡本体不查可请性**：AI 路径请到「不可附身」的惡犬(11) 时，**扣卡、台词、附身调用照旧**
  （`player+0x3f` 是否被改写由 `0x40ead7` 决定）—— 与卡 22/23 的「信任调用方」一脉相承。

> ⚠️ **复刻侧的一处口径差异（不可达，仅为防御）**：`cards/registry.ts` 在调 `attachGod` 之前
> 用 `summonableObjects(objects).includes(...)` 再筛一道；原版**AI 路径没有这道**（人类路径的筛选
> 在 `0x444d1a` 里）。两个调用方（`client/object-pick.ts` 的 `nearestSummonableObject`、
> `ai/card-policy.ts` 的 `qingshen`）都已按同一条件筛过，故**任何可达输入下行为相同**。

#### 未决

1. `god_table[g-1] + 0x4`（`0x496d0c`）字段的名称与作用：`0x40ead7` 在 `type == 0xf` 时写 13（`0xd`），否则写 7，未确认这 13/7 是回合数还是其它计数（`0x41c84f`、`0x41b42d` 也读写该字段，本次未展开）。
2. AI 路径下 `[0x48be58]` 由哪个函数写入神明 ID（本次只确认了读取方 `0x41e6f2`），因此「AI 如何挑神」未确认。
3. `0x40e669` 第 6 个实参：本卡传 0，而卡 6（轉向卡）传 `0x64`(100)（`0443022 push 0x64` 处为 `00443024` 之前的 `push 0x64`：`00442fe6`/`00443021`），二者差异代表什么（时长/帧数）未确认。
   → **部分结案（2026-09-19）**：通道 2 已实测「本卡第 6 参 = 0」（`tests/test_god_charm_cards.py`），
   且表现层把它当**收尾停顿时长**接（`client/throw-fx.ts` 的 `CARD_FLIGHT_PAUSE` 表，
   請神符那一行 = 0、其余卡片逐条覆盖，见 `client/throw-fx.test.ts`）。**单位（毫秒/帧）仍未定**。

`@source` `VA 0x444e1a`、`VA 0x444d1a`、`VA 0x40ead7`、`VA 0x40ea62`、`VA 0x40ea9b`、`VA 0x40a45c`、`VA 0x47ed3c`

---

### 卡 24 · 紅卡

| 项 | 值 |
|---|---|
| 卡号 | 24 |
| 卡名 VA | `0x00466b63`（`"紅卡"`） |
| 函数 VA | `0x00444f25`（91 条指令，282 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体与全部被调函数内均无 `call 0x4413ad`） |
| 目标选择 | 选**一支股票**：人类调用股市界面 `0x42b58f(1)`（参数 1 = 上涨），AI 直接读 `[0x48be58]` 为股票下标（0-based）+1 |

#### 精确效果

1. 台词：`00444f2f mov edx, dword ptr [0x49910c]`；`00444f3a mov bl, byte ptr [eax + 0x496b7b]`（`character`）；`00444f51 mov ecx, dword ptr [eax + 0x481296]`（`0x481296 = 0x48123a + 360*character + 4*23`，第 23 条；`character=0` 时 `"#0449跟著我買股票準沒錯！"`）/ `00444f5b call 0x44ef41`（`player_say(cur, 0, 台词)`）。
2. 分派人类/AI：`00444f6a cmp byte ptr [eax + 0x496b7d], 1` / `00444f71 je 0x444fea`（`who_plays==1` = 人类）。
3. **AI 路径**（`0x444f73`~`0x444fe8`）：
   - `00444f73 push 0` / `00444f75 call 0x41e6f2` → `edx = [0x48be58]`（股票下标，0-based）；
   - `00444f7f shl eax, 3` / `00444f82 lea ebx, [edx + eax]` / `00444f85 shl ebx, 2` → `ebx = idx*36`（股票结构步长 0x24 = 36，数组基址 `0x496980`）；
   - `00444f88 mov byte ptr [ebx + 0x496987], 0x20` → 把该股票的「走势字节」（`stock+0x7`）写成 `0x20`。该字节只有高 4 位被使用：`0042907e test dl, 0xf0` / `00429081 je 0x42908f`，高 4 位非 0 → 上涨（`00429083 mov dword ptr [eax + 0x49699c], 0x41200000` = `+10.0f`），否则下跌（`0042908f mov dword ptr [eax + 0x49699c], 0xc1200000` = `-10.0f`）。故 `0x20` = 上涨；
   - `00444f8f inc edx` / `00444f90 push edx` / `00444f91 call 0x429040` → `0x429040(idx+1)` 按走势字节重算价格：`004290a1 push dword ptr [ebx*4 + 0x49699c]`（±10.0f）、`004290a8 push dword ptr [ebx*4 + 0x496990]`、`004290af call 0x428ec5`、`004290bf fst dword ptr [ebx*4 + 0x496994]`（新价写入 `stock+0x14`），并把新价追加到历史数组 `0x497328 + idx*576 + day*4`（`004290d3 fstp dword ptr [ebx + eax*4 + 0x497328]`，`day = [0x499100]-1`，越界时取 143）；
   - 提示文本：`00444f99 mov edi, dword ptr [ebx + 0x496980]`（该股票名称指针）/ `00444fa8 call 0x452946`（`0x452946(dst, src)` = 拷字符串并删掉空格）/ `00444fb0 mov ebp, dword ptr [0x47feaa]`（`0x47feaa` 指向 `"紅卡"`）/ `00444fc9 call 0x457110`（`sprintf(dst, "對%s使用%s！", 名称, "紅卡")`，格式串 `0x4653ae`）/ `00444fdb call 0x440cac`（`0x440cac(0x5dc, 文本)` 显示消息）/ `00445022` 移除卡；
   - `00444fe3 mov ebx, 1`。
4. **人类路径**（`0x444fea`~`0x445020`）：
   - `00444fea push 0xa` / `00444fec push 0xf` / `00444fee push 0xc` / `00444ff0 call 0x4021f8`（界面配色/状态设置）；
   - `00444ff8 push 1` / `00444ffa call 0x42b58f` → 打开股市对话框，参数 1 = 让选中的股票上涨。`0x42b58f` 把该参数原样传给对话框过程：`0042ba4c mov edx, dword ptr [esp + 0x14]`（= 参数 1）/ `0042ba50 push edx` / `0042ba51 push 0x42aaff` / `0042ba56 call 0x4018e7`；对话框过程把参数存入 `0042ab8f mov byte ptr [0x48c2ed], dl`；点确定时 `0x42b0da` 执行 `0042b0fa cmp byte ptr [0x48c2ed], 1` / `0042b101 jne 0x42b11e` → 为 1 时 `0042b114 mov byte ptr [eax*4 + 0x496987], 0x20`（上涨），否则 `0042b12f mov byte ptr [eax*4 + 0x496987], 2`（下跌），随后 `0042b13f call 0x429040` 应用价格变化；
   - `00444fff mov esi, eax` / `00445004 mov ebx, eax` → 对话框返回值（选中的股票号，取消时为 0）；
   - `00445006 push 0` / `00445008 push 1` / `0044500a push 0x29` / `0044500c call 0x4021f8`；`00445014 push 1` / `00445016 call 0x41906a`（收尾刷新）；
   - `0044501e test esi, esi` / `00445020 je 0x445032` → **取消（返回 0）时跳到收尾，`ebx=0` → 返回 0 = 失败，卡片不消耗**。
5. 消耗卡片：`00445022 push 0x18`（0x18 = 24）/ `0044502a call 0x441343` / `00445032 mov eax, ebx` / `00445034 add esp, 0x94` … `ret`。
   - AI 路径 `ebx = 1`；人类路径 `ebx` = 对话框返回的股票号（非 0）。两条路径都返回非 0 = **成功**。

**公式汇总**
```
cur = [0x49910c]
say(cur, 0, speech[player[cur].character][23])
if (player[cur].who_plays == 1) {                 /* 人类 */
    ui(0xc, 0xf, 0xa)                             /* 0x4021f8 */
    n = stock_dialog(mode = 1)                     /* 0x42b58f(1)，非 0 = 选中的股票号 */
    ui(0x29, 1, 0); ui_end(1)                      /* 0x4021f8, 0x41906a */
    if (n == 0) return 0                           /* 取消：卡不消耗 */
    /* 涨跌在对话框内部完成：0x42ab8f 存 mode → 0x42b0fa/0x42b114 写 0x20 → 0x42b13f 调 0x429040 */
    result = n
} else {                                           /* AI */
    idx = [0x48be58]                               /* 0x41e6f2(0)，0-based */
    stock[idx].trend = 0x20                        /* 高 4 位非 0 ⇒ 上涨 */
    stock_apply(idx + 1)                           /* 0x429040：新价 = f(旧价, +10.0f) */
    show("對" + strip_spaces(stock[idx].name) + "使用紅卡！")
    result = 1
}
remove_card(cur, 24); return result
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 人类玩家在股市界面点取消 | `0x42b58f` 返回 0 → `00445020 je 0x445032` → 不移除手牌、返回 0 = 失败 | `0x444fff`、`0x445020` |
| AI 路径 `[0x48be58]` = 0 | 被视为「第 1 支股票」：`ebx = 0*36 = 0`，写 `[0x496987] = 0x20` 并 `0x429040(1)`，无下标校验 | `0x444f82`、`0x444f88`、`0x444f91` |
| 走势字节为 0 的股票 | `0x429040` 跳过（`00429076 test dl, dl` / `00429078 je 0x4290da`），价格不变。本卡与 AI 路径都会先写 `0x20`，故不会命中此分支 | `0x429076` |
| 同一支股票被连续使用 | 每次 `0x429040` 都会重新读 `stock+0x10` 作为输入并写 `stock+0x14`，并把结果同时写进历史数组 `0x497328`（天数下标 `[0x499100]-1`，为负时取 143） | `0x429070`、`0x4290d3` |
| 台词索引 | `0x48123a + 360*character + 4*23`；`character=0` 时 `"#0449跟著我買股票準沒錯！"` | `0x444f51` |
| 「對%s使用%s！」里的第二个 `%s` | 常量 `0x47feaa` → `"紅卡"`（卡 24 的表项名） | `0x444fb0`、`0x47feaa` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。被调函数 `{0x441343, 0x44ef41, 0x41e6f2, 0x429040, 0x452946, 0x457110, 0x440cac, 0x4021f8, 0x42b58f, 0x41906a}` 中只有 `0x429040` 一条支链会间接进入其它代码（`0x428ec5`），也不含 `0x4413ad`。

★★ **2026-09-19（第 108 条）通道 2 已整支驱动**（`rich4-spec/tests/test_stock_alliance_cards.py`，40/40，
与卡 25/29 同一支）：上面「公式汇总」逐条被机器复现 ——

- **AI 路径**：`0x41e6f2(0)` 取下标 → `stock[idx]+0x07 = 0x20` → **紧跟** `0x429040(idx+1)` →
  `sprintf("對%s使用%s！", 去空格名, "紅卡")` → 显示 → **扣卡 `(cur,24)`** → 返回 **1**；
- **人类路径**：`0x4021f8(0xc,0xf,0xa)` → `0x42b58f(1)`（模式 1 = 涨）→ `0x4021f8(0x29,1,0)` →
  `0x41906a(1)`；★★ **卡本体一个字节都不改股票表**（写走势与改价都在股市屏内部）——
  实测「趋势字节全 0」「`0x429040` 零调用」；
- **取消**（对话框返回 0）⇒ 返回 0、**不扣卡**；
- 台词指针实测 `"#0449跟著我買股票\n準沒錯！"`（表 B 槽 23）。

#### 未决

1. 人类路径里 `0x42b58f`（385 条指令、1288 字节）内部除「参数 → `0x48c2ed` → `0x42b0da` 写走势字节 + `0x429040`」这条链之外的部分未逐指令核实，特别是它的返回值如何由选中项决定（只能确认 0 = 取消/未选，非 0 = 成功返回给卡函数）。
2. 人类路径是否也显示 `"對%s使用%s！"` 文本：本卡人类分支里没有对 `0x440cac`/`0x457110` 的调用，推测由 `0x42b58f` 内部绘制，但未确认。
3. `0x47feaa` 处的 `"紅卡"` 是卡表项 `0x47fdf2 + 23*8` 指向的同一个字符串（`0x00466b63`），是否本卡专用的第二份拷贝未确认（`0x47feaa` 存的是指针，解引用得同一地址 `0x00466b63`）。

`@source` `VA 0x444f25`、`VA 0x444f88`、`VA 0x445020`、`VA 0x429040`、`VA 0x42b58f`、`VA 0x42aaff`、`VA 0x42b0da`、`VA 0x47feaa`、`VA 0x4653ae`

---

### 卡 25 · 黑卡

| 项 | 值 |
|---|---|
| 卡号 | 25 |
| 卡名 VA | `0x00466b68`（`"黑卡"`） |
| 函数 VA | `0x0044503f`（133 条指令，433 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ❌ 不查（函数体与全部被调函数内均无 `call 0x4413ad`） |
| 目标选择 | 选**一支股票**：人类调用股市界面 `0x42b58f(2)`（参数 2 = 下跌），AI 直接读 `[0x48be58]` 为股票下标（0-based）+1 |

#### 精确效果

1. 台词：`00445052 mov dl, byte ptr [eax + 0x496b7b]`（`character`）；`00445069 mov ecx, dword ptr [eax + 0x48129a]`（`0x48129a = 0x48123a + 360*character + 4*24`，第 24 条；`character=0` 时 `"#0450這支股票太貴了！！"`）/ `00445079 call 0x44ef41`（`player_say(cur, 0, 台词)`）。
2. **先快照 12 支股票的旧价**（在改价之前）：
   - `00445081 xor ebx, ebx`；循环体 `00445083 mov eax, ebx` / `00445085 shl eax, 3` / `00445088 add eax, ebx`（`eax = i*9`）/ `0044508a mov edx, dword ptr [eax*4 + 0x496994]`（`0x496994 + i*36` = `stock[i]+0x14` 的价格）/ `00445091 mov dword ptr [esp + ebx*4 + 0x80], edx` / `00445098 inc ebx` / `00445099 cmp ebx, 0xc` / `0044509c jl 0x445083`。
   - 结论：股票共 **12 支**，结构步长 `0x24`（36），基址 `0x496980`，价格字段在 `+0x14`。旧价数组在栈上 `[esp+0x80 .. esp+0xac]`。
3. 分派人类/AI：`0044509e imul eax, dword ptr [0x49910c], 0x68` / `004450a5 cmp byte ptr [eax + 0x496b7d], 1` / `004450ac jne 0x4450e2`（非 1 = AI）。
4. **人类路径**（`0x4450ae`~`0x4450e0`）：`004450ae push 0xa` / `004450b0 push 0xf` / `004450b2 push 0xc` / `004450b4 call 0x4021f8`；`004450bc push 2` / `004450be call 0x42b58f`（参数 2 = 下跌）→ `004450c6 mov ebx, eax`；`004450c8 push 0` / `004450ca push 1` / `004450cc push 0x29` / `004450ce call 0x4021f8`；`004450d6 push 1` / `004450d8 call 0x41906a`。对话框内部经 `0042ab8f mov byte ptr [0x48c2ed], dl`（dl = 2）与 `0x42b0da` 的 `0042b101 jne 0x42b11e` 分支写 `0042b12f mov byte ptr [eax*4 + 0x496987], 2`（下跌）并 `0042b13f call 0x429040` 应用价格变化。
5. **AI 路径**（`0x4450e2`~`0x44515a`）：
   - `004450e2 push 0` / `004450e4 call 0x41e6f2` → `eax = [0x48be58]`（0-based 下标）；
   - `004450ec lea ebx, [eax + 1]`（1-based 股票号）；`004450f1 shl eax, 3` / `004450f4 add eax, edx` → `idx*9`；`004450f6 mov byte ptr [eax*4 + 0x496987], 2` → 走势字节 = `2`（高 4 位为 0 ⇒ 下跌）；
   - `004450fe push ebx` / `004450ff call 0x429040` → 重算该股票价格（`+10.0f`/`-10.0f` 由走势字节高 4 位决定，此处为 `-10.0f`）；
   - 提示文本：`00445111 mov edi, dword ptr [eax*4 + 0x496980]`（股票名）/ `00445121 call 0x452946`（去空格拷贝）/ `00445129 mov ebp, dword ptr [0x47feb2]`（`"黑卡"`）/ `00445142 call 0x457110`（`sprintf(dst, "對%s使用%s！", 名称, "黑卡")`）/ `00445154 call 0x440cac`（`0x440cac(0x5dc, 文本)`）。
6. 取消判定：`0044515c test ebx, ebx` / `0044515e je 0x4451e3` → `ebx=0`（人类路径取消）时跳到收尾返回 0 = **失败，卡片不消耗**。
7. **计算价格差**：`00445164 lea edx, [ebx - 1]`（`idx`）；`00445167 mov eax, edx` / `0044516e shl eax, 3` / `0044516d add eax, edx` → `eax = idx*9`；`00445170 fld dword ptr [esp + edx*4 + 0x7c]`（`edx = ebx = idx+1`，故地址 = `esp+0x80+idx*4` = 旧价）/ `00445174 fsub dword ptr [eax*4 + 0x496994]`（减新价）/ `0044517b fstp dword ptr [esp + 0xc4]` → `delta = 旧价 - 新价`（float）。
8. **对每个持股玩家调整关系值**：
   - `00445182 xor esi, esi` / `00445184 cmp esi, dword ptr [0x499114]`（玩家数）/ `0044518a jge 0x4451d2`；
   - `0044518c mov eax, esi` / `0044518e shl eax, 2` / `00445191 sub eax, esi` / `00445193 shl eax, 5` → `eax = 玩家*96`；`00445196 mov edx, ebx` / `00445198 shl edx, 3` → `edx = 股票号*8`；`0044519b add eax, edx`；
   - `0044519d cmp dword ptr [eax + 0x497198], 0` / `004451a4 je 0x4451cf` → 持股为 0 则跳过（持股数组 = `0x497198 + 玩家*96 + 股票号*8`，股票号为 1-based，故实际首元素在 `0x4971a0`）；
   - `004451a6 fild dword ptr [eax + 0x497198]`（持股数）/ `004451ac fmul dword ptr [esp + 0xc4]`（×delta）/ `004451b3 fdiv dword ptr [0x4653bc]`（÷`200.0f`，`0x4653bc` 的 f32 = 200.0）；
   - `004451b9 sub esp, 8` / `004451bc fstp qword ptr [esp]` → **把结果作为 8 字节 double 压栈**；`004451bf mov edi, dword ptr [0x49910c]` / `004451c5 push edi` / `004451c6 push esi` / `004451c7 call 0x40df69` → `0x40df69(i, cur, 值)`。
   - `0x40df69` 的实际签名是 `(int a, int b, int delta)`：`0040df6b mov edx, dword ptr [esp + 0xc]`（a）、`0040df6f mov ebx, dword ptr [esp + 0x10]`（b）、`0040df97 mov ecx, dword ptr [esp + 0x14]`（**delta 只取 4 字节**）、`0040dfa1 add edi, ecx` / `0040dfa3 mov dword ptr [eax + 0x496bb4], edi`（写 `player[a] + 0x4c + b*4`）、`0040dfa9 test edi, edi` / `0040dfad xor ecx, ecx` / `0040dfaf mov dword ptr [eax + 0x496bb4], ecx`（夹到 ≥ 0）。对照普通调用点（`0040ad0b push eax` = 32 位整数、`0040ad19 add esp, 0xc` = 3 个 4 字节参数），可确认第三参是 4 字节整数。
9. 消耗卡片：`004451d2 push 0x19`（0x19 = 25）/ `004451da call 0x441343` / `004451e3 mov eax, ebx` … `ret` → 返回非 0 = **成功**。

**公式汇总**
```
cur = [0x49910c]
say(cur, 0, speech[player[cur].character][24])
for (i = 0; i < 12; i++) old[i] = stock[i].price            /* stock[i]+0x14, 0x496994 + i*36 */

if (player[cur].who_plays == 1) n = stock_dialog(mode = 2)  /* 0x42b58f(2) */
else { idx = [0x48be58]; stock[idx].trend = 2; stock_apply(idx+1); show("對" + name + "使用黑卡！"); n = idx+1 }
if (n == 0) return 0                                        /* 取消，卡不消耗 */

idx   = n - 1
delta = old[idx] - stock[idx].price                         /* float */
for (p = 0; p < [0x499114]; p++) {
    shares = (int)holdings[p][n]                            /* 0x497198 + p*96 + n*8 */
    if (shares == 0) continue
    v = shares * delta / 200.0f                             /* float，以 double 压栈 */
    relation_add(p, cur, v)                                 /* 0x40df69 只取该 double 的低 32 位 */
}
remove_card(cur, 25); return n
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 人类玩家在股市界面点取消（返回 0） | `0044515e je 0x4451e3` → 不移除手牌、返回 0 = 失败（注意此时第 1 步的台词已经说过） | `0x4450c6`、`0x44515e` |
| 没有任何玩家持有该股票 | 第 8 步循环每次都 `je 0x4451cf` 跳过，卡仍照常消耗并返回成功 | `0x4451a4`、`0x4451d2` |
| 持股数组下标 | `0x497198 + p*96 + n*8`，`n` 为 1-based，所以股票号 1 落在 `0x4971a0`（其它函数也按 `0x4971a0` 访问，互为印证） | `0x44519b`、`0x4451a6` |
| 玩家下标上界 | 用 `[0x499114]`（玩家人数）；不排除 `who_plays == 0` 的玩家（与 `0x40d2d3` 的过滤规则不同） | `0x445184` |
| 第三参数类型不匹配 | 调用方压入 8 字节 double（`004451b9 sub esp, 8` / `004451bc fstp qword ptr [esp]`），被调方按 4 字节 int 读（`0040df97 mov ecx, dword ptr [esp + 0x14]`）。因此实际写入关系值的是该 double 的**低 32 位**，而不是 `shares*delta/200` 本身。卡 3 購地卡、卡 8 拍賣卡对同一函数使用同样的 double 压栈方式（`004423ed sub esp, 8` / `004423f0 fstp qword ptr [esp]`、`004432b6` / `004432b9`） | `0x4451b9`、`0x4451bc`、`0x40df97`、`0x4423ed`、`0x4432b6` |
| 关系值下限 | `0x40df69` 先把「当前值为 0 且增量为负」的情况直接返回，再对结果夹到 ≥ 0 | `0x40df83`、`0x40dfad` |
| 台词索引 | `0x48123a + 360*character + 4*24`；`character=0` 时 `"#0450這支股票太貴了！！"` | `0x445069` |

#### 防御卡查询

**无**（函数体无 `call 0x4413ad`）。被调函数 `{0x44ef41, 0x41e6f2, 0x429040, 0x4021f8, 0x42b58f, 0x41906a, 0x452946, 0x457110, 0x440cac, 0x40df69}` 中无一调用 `0x4413ad`（`0x40df69` 只做整数关系值加减与 `0x40cc1a` 的同盟解除判定）。

★★ **2026-09-19（第 108 条）通道 2 已整支驱动**（`rich4-spec/tests/test_stock_alliance_cards.py`，40/40）——
本卡最值得注意的是尾部的敌意循环，本轮**真跑 `0x40df69`** 把它钉死了：

| 事实 | 实测值 |
|---|---|
| 价差 | `float32(旧价) − float32(现价)`，再 `fstp dword` 舍一次（**输入都是 float32**，直接用 double 差会算错）|
| 算式 | `v = 持股 × 价差 ÷ 200.0f`（x87 扩展精度），`fstp qword` 舍成 double |
| 真正落库的 | 那个 double 的**低 32 位**（`0x40df69` 的 `[esp+0x14]` = 调用方 `[esp+0xc]`）|
| 持股 10、价差 0.3 | **1717986918**（原版真的把一个巨大的垃圾值写进关系值！）|
| 持股 3、价差 0.3 | 低 32 位 = **−687194767**（负 ⇒ 关系值为 0 时被 `0x40df83` 提前返回，看不到）|
| 持股 100、价差 0.3 | 低 32 位恰为 **0**（这一档看不出副作用）|
| 价差取整数档（10.0）| 0 |
| 持股 0 | 整支跳过（连 `0x40df69` 都不调）|
| 循环上界 | `[0x499114]`（玩家人数），**不排除** `who_plays == 0` |

> ⚠️ **本轮订正**：本条「未决」与复刻侧 `cards/swap-and-stock.ts` 原先都写着
> 「priceDiff 恒为 0 ⇒ 敌意恒为 0」——**两条都错**：① 价差不是 0（写 `newsFlag`
> 之后紧接着就 `0x429040` 重算了价）；② 低 32 位**大多数情况下非 0**。
> 复刻侧已改为照做（`blackCardHostilityDeltas()`，含 `Math.fround` 的 float32 价差）。
>
> ★★ **连带发现（同一轮）**：复刻在 `reduce.ts` 的 `playCard()` 里把 registry 已经落过的
> 敌意**又落了一遍** ⇒ 全引擎的卡片敌意被加了两倍（梦遊/冬眠/陷害/查稅/黑卡都翻倍）。
> 已修（`playCard` 直接用 `r.players`），回归用例见 `use-card.test.ts`。

#### 未决

1. ~~`0x40df69` 第三参数「调用方压 double、被调方读 int」的确切原因与原始意图~~
   → **已实测（见上表）**：低 32 位生效、且**经常非 0**；原始意图无法从二进制判定
   （WATCOM C 无原型声明的提升，或设计如此），但**行为**已经没有未知量。
2. `0x428ec5`（被 `0x429040` 调用，`108` 条指令）的价格重算公式未展开，因此「新价 = f(旧价, ±10.0f)」的具体函数形式未确认。
3. `0x42b58f(2)` 在人类路径返回什么值才算「选中」：只能确认 0 = 取消（`0044515e`），非 0 的具体含义（股票号 vs 其它）未确认。
4. `stock+0x7` 走势字节除高 4 位之外的低 4 位是否另有含义（AI 写 `2`、`0x20` 两种值，只有 `test dl, 0xf0` 被使用），未确认低 4 位的用途。

`@source` `VA 0x44503f`、`VA 0x44515e`、`VA 0x4451a4`、`VA 0x4451b9`、`VA 0x40df69`、`VA 0x429040`、`VA 0x429076`、`VA 0x42b0da`、`VA 0x4653bc`、`VA 0x47feb2`

---

### 卡 26 · 查稅卡

| 项 | 值 |
|---|---|
| 卡号 | 26 |
| 卡名 VA | `0x00466b6d`（`"查稅卡"`） |
| 函数 VA | `0x004451f0`（169 条指令，584 字节） |
| 可否主动使用 | ✅ 可 |
| 查防御卡 | ✅ 查 **免費卡(20)** → **嫁禍卡(19)**（两次 `call 0x4413ad`，均在移除本卡之后） |
| 目标选择 | 选一名玩家（返回位掩码 `1<<n`，再用 `0x40d293` 转成 0-based 下标）；人类选框参数 **`0xe0c0410`** 经 `0x446ae8` 进入对话框 `0x445e4d`，AI 读 `[0x48be58]`（`0x41e6f2(0)`） |

#### 精确效果

1. 取目标掩码：`004451fa imul eax, dword ptr [0x49910c], 0x68` / `00445201 cmp byte ptr [eax + 0x496b7d], 1`（`who_plays`）/ `00445208 jne 0x445216`
   - 人类：`0044520a push 0xe0c0410` / `0044520f call 0x446ae8`（`00446aec push edx` / `00446aed push 0x445e4d` / `00446af2 call 0x4018e7`）
   - AI：`00445216 push 0` / `00445218 call 0x41e6f2`
   - `0044521d add esp, 4` / `00445220 mov edi, eax`（`edi` = 位掩码）
2. `00445222 test edi, edi` / `00445224 je 0x445426`。`0x445426` 是共享收尾 `00445426 mov eax, edi` / `00445428 jmp 0x441e07`，而 `0x441e07` = `00441e07 add esp, 0x98` / `pop ebp` / `pop edi` / `pop esi` / `pop ebx` / `ret` → 返回 0 = **取消，卡片不消耗**。
3. **先移除本卡**：`0044522a push 0x1a`（0x1a = 26）/ `0044522c mov ecx, dword ptr [0x49910c]` / `00445233 call 0x441343`。此步在防御卡判定**之前**，因此目标即使成功用掉免費卡，本卡也已被消耗。
4. 说台词：`00445244 mov bl, byte ptr [eax + 0x496b7b]`（`character`）/ `0044525b mov esi, dword ptr [eax + 0x48129e]`（`0x48129e = 0x48123a + 360*character + 4*25`，第 25 条；`character=0` 时 `"#0451別想逃漏稅！"`）/ `0044526b call 0x44ef41`（`player_say(cur, 0, 台词)`）。
5. 掩码转下标：`00445273 push edi` / `00445274 call 0x40d293` / `00445279 mov esi, eax` / `0044527e mov ebx, eax` → `ebx = ctz(掩码)` = 目标玩家下标（0-based）；`0x40d293` 对 `掩码 & 0xff == 0` 返回 −1。
6. **计算税额**：`004452ce imul eax, ebx, 0x68`；`004452d1 fild dword ptr [eax + 0x496b84]`（`0x496b84 - 0x496b68 = 0x1c` = `cash`）；`004452d7 fmul qword ptr [0x4653d8]`（`0x4653d8` 的 f64 = `0.2`）；`004452dd call 0x457dbc`（`frndint`，且 `00457dc5 mov byte ptr [esp + 1], 0x1f` 把控制字舍入位设为截断 → **向零取整**）；`004452e2 fistp dword ptr [esp + 0x94]` → `tax = trunc(0.2 * 目标现金)`。
7. **仇恨值**：`004452e9 mov esi, 0x64`（100）/ `004452fa idiv esi`（`eax = [esp+0x94] / 100`，带 `cdq`）/ `004452fc push eax` / `00445303 push ecx`（`ecx = [0x49910c]`）/ `00445304 push ebx` / `00445305 call 0x40df69` → `0x40df69(target, cur, tax/100)`，即把「目标对使用者」的关系值加 `tax/100`（写 `player[target] + 0x4c + cur*4`）。
8. **AI 才播的镜头动画**：`00445280 imul eax, dword ptr [0x49910c], 0x68` / `00445287 cmp byte ptr [eax + 0x496b7d], 1` / `0044528e je 0x4452ce` → 人类跳过；AI 执行 `00445290 push 0x64` / `00445297 mov dx, word ptr [esi + 0x496b72]`（目标 y）/ `0044529f mov si, word ptr [esi + 0x496b70]`（目标 x）/ `004452c4 push 0` / `004452c6 call 0x40e669` → `0x40e669(0, cur_x, cur_y, target_x, target_y, 0x64)`。
9. **防御卡 1：免費卡(20)**
   - `0044530d push 0x14`（0x14 = 20）/ `0044530f push ebx` / `00445310 call 0x4413ad` → `has_card(target, 20)`
   - `00445318 cmp eax, 1` / `0044531b jne 0x44533e`
   - 命中时：`0044531d mov esi, dword ptr [esp + 0x94]`（tax）/ `00445325 push esi` / `0044532b push ebp`（`ebp = [0x49910c]`）/ `0044532c push ebx` / `0044532d call 0x444a60` → `0x444a60(target, cur, tax)`。该函数内部：`00444a92 cmp byte ptr [ebx + 0x496b7d], 1`，人类走 `00444ad8` 的确认框（`00444adf push 0x465388` = `"%s\n\n是否使用免費卡？"`、`00444af4 call 0x440ba8`），AI 走 `00444a9b call 0x456f2d`（随机数）与阈值 `00444aa2 mov esi, 0xbb8`（3000）/ `00444aae mov esi, dword ptr [0x4990e8]`（物价指数）/ `00444ab7 mov eax, dword ptr [esp + 0x9c]`（tax）比较；决定使用后 `00444b2d push 0x14` / `00444b30 call 0x441343`（移除目标的免費卡）、`00444b54 mov edx, dword ptr [eax + 0x481286]`（k=19 = 免費台词）、`00444b5e call 0x44ef41`（目标说话）。
   - `00445332 add esp, 0xc` / `00445335 cmp eax, 1` / `00445338 je 0x445426` → **目标用掉免費卡 ⇒ 直接返回 `edi`（非 0）= 成功，但不再扣钱**。
10. **防御卡 2：嫁禍卡(19)**
    - `0044533e push 0x13`（0x13 = 19）/ `00445340 push ebx` / `00445341 call 0x4413ad` → `has_card(target, 19)`
    - `00445349 cmp eax, 1` / `0044534c jne 0x44536f`
    - `0044534e cmp dword ptr [esp + 0x94], 0x7d0`（2000）/ `00445359 jle 0x44536f` → **税额必须 > 2000 才会触发嫁禍**
    - `0044535b push 0` / `0044535d push 2` / `0044535f push ebx` / `00445360 call 0x44476a` → `0x44476a(target, 2, 0)`。模式 2 = 查稅卡场景（`004448ca mov edx, dword ptr [esp + 0xb8]` / `004448d1 cmp edx, 1` / `004448e5 cmp edx, 2` / `004448e8 je 0x444934`；`0x444934` 用 `fild dword ptr [eax + 0x496b84]`、`fmul qword ptr [0x465380]`（= 0.2）与 `4000 * 物价指数` 比较决定是否嫁禍）。返回 `ebx`（新目标下标，初值 `0044477b mov ebx, 0xffffffff` = −1）。
    - `00445368 cmp eax, -1` / `0044536b je 0x44536f` / `0044536d mov ebx, eax` → 把目标改成替罪羊。
11. `0044536f mov edx, dword ptr [0x49910c]` / `00445375 cmp ebx, edx` / `00445377 je 0x445421` → 若最终目标就是使用者本人，跳过收款直接 `call 0x41d546` 收尾。
12. **收款**（重新按最终目标的现金算额）：
    - `0044537d imul esi, ebx, 0x68` / `00445380 fild dword ptr [esi + 0x496b84]` / `00445386 fmul qword ptr [0x4653d8]`（0.2）/ `0044538c call 0x457dbc` / `00445391 fistp dword ptr [esp + 0x94]` → `tax2 = trunc(0.2 * 最终目标现金)`（未发生嫁禍时 `tax2 == tax`）；
    - `00445398 push 0` / `0044539a mov ecx, dword ptr [esp + 0x98]`（`tax2`）/ `004453a1 push ecx` / `004453a2 push edx`（`[0x49910c]`）/ `004453a3 push ebx` / `004453a4 call 0x41d2c6` → `0x41d2c6(付款方 = 最终目标, 收款方 = 使用者, 金额 = tax2, flags = 0)`。
    - `0x41d2c6` 语义（本卡用到 flags = 0）：`0041d2ca mov esi, dword ptr [esp + 0x14]`（付款方）/ `0041d2ce mov edi, dword ptr [esp + 0x18]`（收款方）/ `0041d2d2 mov ebx, dword ptr [esp + 0x1c]`（金额）/ `0041d2f6 test byte ptr [esp + 0x20], 4` / `0041d2fb je 0x41d33d` → flags bit2 = 0 ⇒ `0041d33d mov edx, dword ptr [eax + 0x496b84]` / `0041d345 mov dword ptr [eax + 0x496b84], edx` **从现金 `player+0x1c` 扣**（不足时继续扣 `player+0x20` 存款并夹 0）；收款侧 `0041d3b2 test byte ptr [esp + 0x20], 1` / `0041d3b7 je 0x41d3c1` / `0041d3c1 add dword ptr [eax + 0x496b88], ebx` ⇒ flags bit0 = 0 时**加到收款方的存款 `player+0x20`**，而非现金；另外 `0041d381 add dword ptr [eax + 0x496bc4], ebx`（付款方累计）与 `0041d3ca add dword ptr [eax + 0x496bc8], ebx`（收款方累计）。
13. **提示文本**：`004453ac mov eax, dword ptr [esi + 0x496b68]`（最终目标的姓名指针 `/ 玩家+0`）/ `004453bb call 0x452946`（去空格拷贝）/ `004453c3 mov edx, dword ptr [esp + 0x94]`（tax2）/ `004453dd call 0x457110`（`sprintf(dst, "抽取%s\n\n%d元稅金！", 姓名, tax2)`，格式串 `0x4653c0`）/ `004453ef call 0x440cac`（`0x440cac(0x5dc, 文本)`）。
14. **受害者台词**：`004453f7 movzx esi, byte ptr [esi + 0x496b7b]`（最终目标的 `character`）/ `0044540f mov ecx, dword ptr [eax + 0x48138e]`（`0x48138e = 0x48123a + 360*character + 4*85`，第 85 条；`character=0` 时 `"#0475算你狠！！"`，`character=1` 时 `"#0527我已經繳過了！"`）/ `00445416 push 2` / `00445418 push ebx` / `00445419 call 0x44ef41`（`player_say(最终目标, 2, 台词)`）。
15. 收尾：`00445421 call 0x41d546`（`0041d546 xor edx, edx` / `0041d548 mov dword ptr [0x48be18], edx` / `0041d550 call 0x41906a`），随后 `00445426 mov eax, edi` / `00445428 jmp 0x441e07` → 返回 `edi`（选中的目标掩码，非 0）= **成功**。

**公式汇总**
```
cur = [0x49910c]
mask = (player[cur].who_plays == 1) ? dialog_target(0xe0c0410)   /* 0x446ae8 → 0x445e4d */
                                    : [0x48be58]                  /* 0x41e6f2(0) */
if (mask == 0) return 0                                           /* 取消，卡不消耗 */
remove_card(cur, 26)                       /* 先消耗，之后的防御卡判定不影响这一点 */
say(cur, 0, speech[player[cur].character][25])
target = ctz(mask)                         /* 0x40d293 */
tax    = (int)(0.2 * player[target].cash)  /* 0.2 为 double，向零取整 */
relation_add(target, cur, tax / 100)       /* 0x40df69：player[target]+0x4c+cur*4 */
if (player[cur].who_plays != 1) camera_anim(0, cur_x, cur_y, target_x, target_y, 100)

if (has_card(target, 20 /*免費卡*/)) {                    /* 0x4413ad */
    if (use_free_card(target, cur, tax) == 1) return mask  /* 0x444a60：税被免除，卡仍已消耗 */
}
if (has_card(target, 19 /*嫁禍卡*/) && tax > 2000) {       /* 0x4413ad + cmp 0x7d0 */
    v = blame_shift(target, 2, 0)                          /* 0x44476a，返回替罪羊下标 */
    if (v != -1) target = v
}
if (target != cur) {
    tax2 = (int)(0.2 * player[target].cash)
    transfer(from = target, to = cur, amount = tax2, flags = 0)   /* 0x41d2c6 */
    show("抽取" + player[target].name + "\n\n" + tax2 + "元稅金！")
    say(target, 2, speech[player[target].character][85])
}
end_ui(); return mask
```

#### 边界情况

| 情况 | 行为 | @source |
|---|---|---|
| 选目标时取消（`mask == 0`） | 返回 0，卡片不消耗 | `0x445224`、`0x445426` |
| `0x40d293(mask)` 返回 −1（掩码低 8 位为 0） | 会把 `ebx = -1` 当作目标：`004452ce imul eax, ebx, 0x68` 读 `0x496b84 - 0x68 * 1` = 玩家 −1 结构（`0x496b1c`），无边界校验 | `0x40d29c`、`0x4452ce` |
| 目标持有免費卡且判定为使用 | 移除目标的免費卡（`00444b30`）、目标说 k=19 台词（`00444b5e`）、本卡**仍已消耗**，函数直接返回 `edi`（`00445338 je 0x445426`），不扣任何钱 | `0x445338`、`0x444b30` |
| 目标持有免費卡但判定为不使用 | `0x444a60` 返回 0 → 继续走嫁禍卡/收款流程 | `0x444a60`、`0x445338` |
| 税额 ≤ 2000（`0x7d0`） | 即使目标持有嫁禍卡也不触发（`00445359 jle 0x44536f`） | `0x44534e` |
| 嫁禍卡流程返回 −1（AI 认为不划算 / 人类取消） | `0044536b je 0x44536f` → 保持原目标继续收款 | `0x445368` |
| 嫁禍替罪羊恰为使用者本人 | `00445377 je 0x445421` → 跳过收款与提示，直接成功返回 | `0x445375` |
| 税额与最终金额的关系 | `tax`（第 6 步）只用于仇恨值 `tax/100`；实际转账金额是第 12 步按最终目标现金重算的 `tax2`。未嫁禍时两者相同 | `0x4452e2`、`0x445391` |
| 收款去向 | flags = 0 ⇒ 使用者的**存款 `player+0x20`** 增加，现金 `player+0x1c` 不变 | `0x41d3b7`、`0x41d3c1` |
| 付款方现金不足 | `0x41d2c6` 会继续从存款扣，并把实际扣除额（可能小于 `tax2`）作为累计值 | `0x41d313`、`0x41d32d` |
| 镜头动画只对 AI 播放 | `00445287 cmp byte ptr [eax + 0x496b7d], 1` / `0044528e je 0x4452ce` | `0x445287` |
| 受害者台词索引 | `0x48123a + 360*character + 4*85`；`character=0` 时 `"#0475算你狠！！"` | `0x44540f` |
| 文本格式 | `0x4653c0` = `"抽取%s\n\n%d元稅金！"` | `0x4653c0` |

#### 防御卡查询

**有，共 2 次，顺序固定：先 `免費卡(20)`，后 `嫁禍卡(19)`，两次都以「被查稅的目标」为手牌持有者。**

1. `免費卡(20)`：
   - `0044530d push 0x14` / `0044530f push ebx` / `00445310 call 0x4413ad`（`has_card(target, 20)`）
   - `00445318 cmp eax, 1` / `0044531b jne 0x44533e`（未持有 → 跳到嫁禍卡检查）
   - 命中：`0044532d call 0x444a60`（`(target, cur, tax)`）。**是否消耗由 `0x444a60` 的返回值决定**：返回 1 时会执行 `00444b2d push 0x14` / `00444b30 call 0x441343` 移除目标手牌中的卡 20（即**消耗防御卡**），随后 `00445338 je 0x445426` 使查稅卡免于扣款并直接成功返回。
2. `嫁禍卡(19)`：
   - `0044533e push 0x13` / `00445340 push ebx` / `00445341 call 0x4413ad`（`has_card(target, 19)`）
   - `00445349 cmp eax, 1` / `0044534c jne 0x44536f`；额外要求 `0044534e cmp dword ptr [esp + 0x94], 0x7d0` / `00445359 jle 0x44536f`（税额 > 2000）
   - 命中：`00445360 call 0x44476a`（`(target, 2, 0)`）。成功使用时该函数内部 `004449ec push 0x13` / `004449ef call 0x441343` **消耗目标手牌中的卡 19**，并返回替罪羊下标；`0044536d mov ebx, eax` 把查稅对象换成替罪羊。

被调函数集合为 `{0x446ae8, 0x41e6f2, 0x441343, 0x44ef41, 0x40d293, 0x40e669, 0x457dbc, 0x40df69, 0x4413ad, 0x444a60, 0x44476a, 0x41d2c6, 0x452946, 0x457110, 0x440cac, 0x41d546}`，其中 `0x4413ad` 的两处调用即为上述两处；`0x444a60`/`0x44476a`/`0x41d2c6` 内部不再调用 `0x4413ad`。

#### 未决

1. 目标选择打包参数 `0xe0c0410` 各位的含义。已确认它被原样传给对话框过程 `0x445e4d`（`00446aec push edx` / `00446aed push 0x445e4d` / `00446af2 call 0x4018e7`，而 `0x4018e7` 把它存入 `004018fe mov dword ptr [eax*4 + 0x48a010], edx`），且同一家族的卡 6 轉向卡用的是 `0xe0c0010`（差异位 `0x400`），但 `0x400` 位控制什么未确认。
2. `0x41d2c6` 第 4 参数（flags）除 bit0（收款方现金/存款）与 bit2（付款方现金/存款）之外的位含义未确认；本卡只在 `00445398 push 0` 传 0。
3. `0x44476a`（嫁禍卡处理，758 字节）只核对了与查稅卡相关的入口（`004448ca` 的模式分支、`00444934` 的模式 2 判定）、返回路径（`00444a53 mov eax, ebx`，初值 `0xffffffff`）与卡 19 的消耗点（`004449ef`）；其人类确认框、候选替罪羊筛选（`0x40d2d3`/`0x40d31c`）的完整细节未展开。
4. `0x444a60`（免費卡处理，338 字节）的 AI 阈值公式：已确认 `00444aa2 mov esi, 0xbb8`（3000）、`00444aae mov esi, dword ptr [0x4990e8]`（物价指数）、`00444ab7` 取 tax、`00444ac6 cmp esi, eax` / `00444ac8 jge 0x444ad1`；但「tax > cash 时无条件使用」这一分支之外，`0x456f2d` 随机数的取值范围未确认。
5. 人类路径下「镜头动画被跳过」（`0044528e je 0x4452ce`）是否由别处补播，未确认。

`@source` `VA 0x4451f0`、`VA 0x445224`、`VA 0x445233`、`VA 0x445310`、`VA 0x445341`、`VA 0x445426`、`VA 0x441e07`、`VA 0x444a60`、`VA 0x44476a`、`VA 0x41d2c6`、`VA 0x445e4d`、`VA 0x4653c0`

## 十、覆盖进度与待办

### 已完成（30 / 30）

> 本节只是进度台账，不含新结论；每张卡的证据见其小节末尾的 `@source` 块。

| 卡 | 状态 |
|---|---|
| 1 均富卡 | ✅ 完整规格 |
| 2 均貧卡 | ✅ 完整规格（已解明 `0x40d293 = ctz`） |
| 3 購地卡 | ✅ 完整规格（商業用地字段名未决） |
| 4 換地卡 | ✅ 完整规格（选框内部过滤规则未决） |
| 5 換屋卡 | ✅ 完整规格（动画系数含义未决） |
| 6 轉向卡 | ✅ 完整规格（`player[0x0e]` 字段名未决） |
| 7 改建卡 | ✅ 完整规格（设施类别映射未决） |
| 8 拍賣卡 | ✅ 完整规格（拍卖 UI 内部规则未逐条拆解） |
| 9 天使卡 | ✅ 完整规格 |
| 10 惡魔卡 | ✅ 完整规格 |
| 11 怪獸卡 | ✅ 完整规格 |
| 12 拆除卡 | ✅ 完整规格（含地图物件表 `0x496d08` 分支） |
| 13 搶奪卡 | ✅ 完整规格 |
| 14 停留卡 | ✅ 完整规格 |
| 15 冬眠卡 | ✅ 完整规格 |
| 16 夢遊卡 | ✅ 完整规格（防御卡矩阵已实测） |
| 17 陷害卡 | ✅ 完整规格（防御卡矩阵已实测） |
| 18 復仇卡 | ✅ 完整规格（不可主动使用，反应式） |
| 19 嫁禍卡 | ✅ 完整规格（不可主动使用，反应式） |
| 20 免費卡 | ✅ 完整规格（不可主动使用，反应式） |
| 21 免罪卡 | ✅ 完整规格（不可主动使用，反应式） |
| 22 送神符 | ✅ 完整规格 |
| 23 請神符 | ✅ 完整规格 |
| 24 紅卡 | ✅ 完整规格 |
| 25 黑卡 | ✅ 完整规格 |
| 26 查稅卡 | ✅ 完整规格（防御卡矩阵已实测） |
| 27 漲價卡 | ✅ 完整规格（`price_status = 0x50` → 过路费 ×2） |
| 28 查封卡 | ✅ 完整规格（`price_status = 0x51` → 过路费免收） |
| 29 同盟卡 | ✅ 完整规格 |
| 30 烏龜卡 | ✅ 完整规格 |

### 待办

**无**（30/30 全部完成）。各卡残留的「未决」项已写在各自小节内，
未用推测填充；汇总见 §十二 表与 §十·「全局待办」。

### 全局待办（与卡片系统相关，尚未在本文定论）

1. **防御卡查询的完整矩阵**：✅ **已完成**，见 §二·续「防御卡机制总览（卡 18–21）」的矩阵表。
2. **`0x499198` 计数字段的语义**（§1.4 末）。
3. **`player[0x17]`（`VA 0x496b7f`）的语义**：AI 卡使用门槛用到它（§1.3）。
4. **`land.owner` 的基址**：✅ **已由委派方裁决**：`owner` 是 **1 基**（0 = 无主，N = 玩家下标 N−1），
   `0x49910c`（当前玩家）是 **0 基**；`calculate_land_toll` 的第 1 参与 `owner` 同编码（1 基），
   函数内是直接相等比较。`land-rent.md` 已据此修正。
5. **表 B（`0x4760fc`/`0x47610c`/`0x47611c`）卡名表的用途**（§1.1.1）。
6. **`b6` 字段的语义**（§1.1.4）。
7. `player_say` 第 2 参数（本文件记作 `slot`，观测值 0/1/2/3）的语义未决；
   它参与 `[(arg2+1)*12 + [0x498eb0][player*0x34] + 0xc]` 的索引计算
   （`@source VA 0x44f045`）。
8. **`player[0x32]`（`VA 0x496b9a`）的语义**（§卡 10 的 `0x40dffa`）。
9. **`0x499160` / `0x499161` 两个计数器**（§卡 16）。
10. **免罪卡是否也应挡过路费**：过路费路径（`0x419b32`）只查免費卡(20) 与嫁禍卡(19)，
    不查免罪卡(21) —— 是「设计如此」还是遗漏，**未决**。

---

## 十一、附：商業用地（步长 `0x38`）字段取证

> 委派方要求：把商業用地结构做成**逐字段、带访问指令**的独立取证。
> 本节给出**已用具体指令证实**的全部字段；未能证实的偏移**明确留空**，
> 不用推测填充。

### 11.1 取证方法与本节的局限（先说不确定性）

- **正向**：从使用商業用地的函数出发，逐条读汇编，确认「基址 + 步长 + 偏移」三件事。
  本文的每条都给出**至少一条真实指令**。
- **反向（只做了一半）**：对全工程 88 个引用 `0x498e88` 的函数做了
  「基址寄存器污点跟踪」，自动收集 `[基址寄存器 + 偏移]` 形式的访问。
  由于该遍历**不处理寄存器重载与多级指针**，它只能作为**交叉验证**，
  不能单独作为结论来源（已知假阳性：`0x41edb3` 的 `lea ebx,[eax+0x34]`
  其实是循环指针自增，不是字段访问）。
- **局限**：`+0x04`–`+0x17` 区间（住宅用地在那里放 `name` 字符串）
  在本文取证范围内**没有任何访问**，因此**未知**。

`@source` 本节的「方法」描述对应 §0.2；被引用的假阳性样本见 `VA 0x41edb3`，
主证据 `VA 0x498e88`（基址）与 `VA 0x4424dc`（步长）。

### 11.2 结构布局（实测）

| 偏移 | 类型 | 字段（推断名） | 可靠性 | 访问指令（证据） |
|---|---|---|---|---|
| `0x00` | int16 | 图标 x | A | `0x40b710` `movsx eax, word ptr [esi]` |
| `0x02` | int16 | 图标 y | A | `0x40b717` `movsx eax, word ptr [esi + 2]` |
| `0x04`–`0x17` | ? | **未知** | — | 取证范围内无访问 |
| `0x18` | uint8 | **type / 设施类别** | A | `0x44250b` 读；`0x4431e4` `mov byte [ebx+0x18], al` 写；`0x40b1ec` 写；`0x4475f2` 复制 |
| `0x19` | uint8 | **owner（1 基）** | A | `0x4424f7` 读；`0x4425b7` `mov byte [ebx+0x19], al` 写；`0x40ab3e` 清零 |
| `0x1a` | uint8 | **level** | A | `0x44250b` 读；`0x40b1f4` `inc byte [ebx+0x1a]`；`0x40ab2b` `dec` |
| `0x1c`–`0x21` | ? | **未知** | — | 取证范围内无**证实**的访问 |
| `0x22` | uint16 | **价 A**（`level × 价B + 价A` 的加项） | A | `0x442519` `mov cx, word ptr [ebx + 0x22]`；`0x4433b0` 卡 8 仇恨公式用它当地价 |
| `0x24` | uint16 | **价 B**（被 `level` 乘） | A | `0x442510` `mov cx, word ptr [ebx + 0x24]`；`0x40b4cf` `mov di, word ptr [eax + 0x24]` |
| `0x26`–`0x2f` | ? | **未知** | — | — |
| `0x30` | uint32 | **未知**（dword） | A（存在）/ B（语义） | `0x44760f` `mov dword ptr [esi+eax+0x30], 0`（**被清零但不在状态复制之列**） |
| `0x34` | uint32 | **flast（地契到期日）** | A | `0x4425e9` `mov dword ptr [ebx + 0x34], eax`；`0x4475ff` 随 owner/level/type 一起复制；`0x40ab46` 清零 |
| `0x38` | — | **步长**（不是字段） | A | `0x4424dc`–`0x4424e1`：`idx*8*8 − idx*8 = idx*56`；`0x40b6e7`、`0x40abf9` 同 |

**订价公式（卡 3 实测）**：
```asm
0044250b  mov   dl, byte ptr [ebx + 0x1a]    ; level
00442510  mov   cx, word ptr [ebx + 0x24]    ; 价 B
00442514  imul  edx, ecx
00442519  mov   cx, word ptr [ebx + 0x22]    ; 价 A
0044251d  lea   edi, [ecx + edx]             ; level*价B + 价A
00442520  imul  edi, dword ptr [0x4990e8]    ; × 物价指数
```

`@source` 本表每条都在「访问指令」列给出具体 VA；`+0x00`/`+0x02` 见 `VA 0x40b710`，
`+0x18` 见 `VA 0x4431e4`，`+0x19` 见 `VA 0x4425b7`，`+0x1a` 见 `VA 0x40b1f4`，
`+0x22` 见 `VA 0x442519`，`+0x24` 见 `VA 0x442510`，`+0x30` 见 `VA 0x44760f`，
`+0x34` 见 `VA 0x4425e9`，步长见 `VA 0x4424dc`。

### 11.3 「状态复制」的旁证（`0x44757c`，302 条指令）

该函数把**一塊商業地产的状态整体搬到另一块**，是判断「哪些字段属于地产状态」的天然标尺：
```asm
004475dc  mov   byte ptr [edx + esi + 0x19], bl   ; owner 被复制
004475e9  mov   byte ptr [edx + esi + 0x1a], bl   ; level 被复制
004475f6  mov   byte ptr [edx + esi + 0x18], bl   ; type  被复制
004475ff  mov   ecx, dword ptr [esi + eax + 0x34]
00447603  mov   dword ptr [edx + esi + 0x34], ecx ; flast 被复制
00447607  mov   dword ptr [esi + eax + 0x34], 0   ; 源清 0
0044760f  mov   dword ptr [esi + eax + 0x30], 0   ; ★ +0x30 只清零、不复制
```
⇒ `+0x30` **不是**「地产状态」的一部分（否则应当一起搬走），
更像「临时计数/动画状态」。

`@source` `VA 0x44757c`（函数入口）、`VA 0x4475dc`–`VA 0x44760f`（复制/清零指令）。

### 11.4 商業用地的等级上限表 `0x474940[+0x18]`

```asm
0040b1f9  xor   edx, edx
0040b1fb  mov   dl, byte ptr [ebx + 0x18]        ; 设施类别
0040b1fe  mov   cl, byte ptr [ebx + 0x1a]        ; level
0040b201  cmp   cl, byte ptr [edx + 0x474940]    ; ★ 上限表[类别]
0040b207  jae   0x40b21f
0040b20e  mov   dl, cl
0040b210  inc   dl
0040b212  mov   byte ptr [ebx + 0x1a], dl        ; level += 1
0040b215  cmp   dl, 5
0040b21a  mov   eax, 0x81                         ; 到 5 级 → bit7
```
同一张表在 `0x40b4de`、`0x41a2c2`、`0x421c77` 也被读取（4 处，皆以
`[类别 + 0x474940]` 形式）；**表内容本身尚未转储**（属地产系统资料，
本文只给出访问点）。

`@source` `VA 0x40b1f9`–`VA 0x40b21a`、`VA 0x40b4de`、`VA 0x41a2c2`、`VA 0x421c77`、`VA 0x474940`。

### 11.5 未决（明确留空，不用推测填充）

1. `+0x04`–`0x17` 的内容（住宅用地那里是 `name`；商業用地是否也有名字？）
   —— **未取得任何访问证据**。
2. `+0x1c`–`0x21`、`+0x26`–`0x2f` 的内容。
3. `+0x30` 的语义。
4. 「价 A / 价 B」的业务命名（哪个是地价、哪个是房价）——
   本文只保证**公式位置**正确（`level × [+0x24] + [+0x22]`）。
5. `0x474940` 表的完整内容与类别名。

`@source` `VA 0x498e88`（基址）、`VA 0x4424dc`（步长）、`VA 0x442519`（`+0x22`）、
`VA 0x442510`（`+0x24`）、`VA 0x4425e9`（`+0x34`）、`VA 0x4475ff` / `VA 0x44760f`（复制定标尺）、
`VA 0x40b710`（`+0x00`/`+0x02`）、`VA 0x4431e4`（`+0x18`）、`VA 0x4425b7`（`+0x19`）、
`VA 0x40b1f4`（`+0x1a`）、`VA 0x474940`（上限表）。

---

## 十二、30 张卡汇总表

> 本表是全篇的索引。每张卡的效果详见对应小节；「查哪张防御卡」一列已用
> **全工程 `call 0x4413ad` 的穷举扫描**独立复核（共 18 处，见 §「防御卡机制总览」）。
> `✅` = 可主动使用；`❌` = `card_functions[N]` 是空桩 `0x4420d5`。

`@source` 本表逐行来自本文件对应卡片小节；函数 VA 来自 `VA 0x475d5c`（`card_functions[]`），
防御卡列来自 `VA 0x4413ad` 的 18 个调用点穷举。

| 卡号 | 卡名 | 函数 VA | 一句话效果 | 可否主动使用 | 查哪张防御卡 |
|---|---|---|---|---|---|
| 1 | 均富卡 | `0x004420d8` | 全体在局玩家现金改为平均值（含自己）；低于均值者降低对施卡者的仇恨 | ✅ | 无 |
| 2 | 均貧卡 | `0x004421b4` | 选一名玩家，双方现金各改为两者之和的一半；较高者增加对施卡者的仇恨 | ✅ | 无 |
| 3 | 購地卡 | `0x00442325` | 按 `(level×house_price+land_price)×price_index` 买下**脚下那格**的他人地产 | ✅ | 无 |
| 4 | 換地卡 | `0x00442622` | 自选一块同类地产，与自己脚下那块**交换 `owner`** | ✅ | 无 |
| 5 | 換屋卡 | `0x00442b02` | 自选一块同类地产，与自己脚下那块**交换 `level` 与 `type`**（含图标换位动画） | ✅ | 无 |
| 6 | 轉向卡 | `0x00442f4d` | 目标 `direction = (direction+4)&7`（掉头），并把 `player[0x0e]` 重设为随机邻接节点 | ✅ | 无 |
| 7 | 改建卡 | `0x0044309b` | 脚下地产住宅↔商業翻转（`type ^= 1`，转商業时 level 截 1）；商業则弹「請選擇設施類別」 | ✅ | 无 |
| 8 | 拍賣卡 | `0x00443225` | 把脚下地产送上拍卖；未成交则 `owner = 0`、`flast = 0` | ✅ | 无 |
| 9 | 天使卡 | `0x004434c0` | 住宅：**所有同名地产** `level += 1`（上限 5）；商業：只升选中那块 | ✅ | 无 |
| 10 | 惡魔卡 | `0x004436e0` | 住宅：**所有同名地产** `level = type = 0`，并按原 level 给 owner 加仇恨 | ✅ | 无 |
| 11 | 怪獸卡 | `0x00443917` | `0x40ab4a(code, 2)`：选中地产 `level = type = 0`（保留 owner 与 flast） | ✅ | 无 |
| 12 | 拆除卡 | `0x00443b0f` | 目标地产**降一级**（降为 0 时清 type）；`bit15` 目标则拆地图物件 | ✅ | 无 |
| 13 | 搶奪卡 | `0x00443e3d` | 选一名玩家，从其手牌抢一张加入自己的手牌 | ✅ | 无 |
| 14 | 停留卡 | `0x00443f80` | 目标 `player[0x38] = 1`（停止；对自己写 `0x80`） | ✅ | 无 |
| 15 | 冬眠卡 | `0x004440ea` | 对**除自己外全部在局玩家**（含伪玩家）施加 5 天睡眠 `player[0x36] = 5` | ✅（恒成功） | 无 |
| 16 | 夢遊卡 | `0x004441dc` | 目标 `player[0x37] = 4/5`（梦游），再调 `0x40b93b` 启动梦游流程 | ✅ | **21 免罪 → 19 嫁禍**；自伤时再查 **18 復仇** |
| 17 | 陷害卡 | `0x004444bf` | 目标入狱 `player[0x34] = 5` 天（打到自己时 4 天） | ✅ | **21 免罪 → 19 嫁禍**；自伤时再查 **18 復仇** |
| 18 | 復仇卡 | `0x004420d5`（空桩） | 反应式：自伤时反向惩罚施害者（`0x444691` 只展示+消耗，惩罚由调用方施加） | ❌ | 本身是**被查方** |
| 19 | 嫁禍卡 | `0x004420d5`（空桩） | 反应式：把落到自己头上的有害效果转给他人（`0x44476a(target, mode, ?)`） | ❌ | 本身是**被查方** |
| 20 | 免費卡 | `0x004420d5`（空桩） | 反应式：免掉一笔税金/过路费（`0x444a60`） | ❌ | 本身是**被查方** |
| 21 | 免罪卡 | `0x004420d5`（空桩） | 反应式：完全抵消一次有害卡/事件（`0x444bb2`），优先级最高 | ❌ | 本身是**被查方** |
| 22 | 送神符 | `0x00444c45` | 送走自己身上的神明（清地图物件表 `0x496d08` 的对应记录） | ✅ | 无 |
| 23 | 請神符 | `0x00444e1a` | 请一尊神明附身到自己身上（`0x40ead7`） | ✅ | 无 |
| 24 | 紅卡 | `0x00444f25` | 指定股票趋势字节置 `0x20`（涨）并重算股价 | ✅ | 无 |
| 25 | 黑卡 | `0x0044503f` | 指定股票趋势字节置 `2`（跌）并重算股价；按各玩家持股量加其对施卡者的仇恨 | ✅ | 无 |
| 26 | 查稅卡 | `0x004451f0` | 抽取目标现金的 **20 %**（`trunc(cash×0.2)`）转给施卡者（入其存款） | ✅ | **20 免費 → 19 嫁禍**（仅当税额 > 2000） |
| 27 | 漲價卡 | `0x0044542d` | 住宅（同名全部）`+0x17 = 0x50` / 商業 `+0x1c = 0x50` → **过路费 ×2** | ✅ | 无 |
| 28 | 查封卡 | `0x00445593` | 同上位置写 `0x51` → **过路费 0（免收）**，显示「房屋查封中」 | ✅ | 无 |
| 29 | 同盟卡 | `0x00445710` | 与目标互为盟友（`player[0x41]`，1 基）+ `player[0x3d] = 7` | ✅ | 无 |
| 30 | 烏龜卡 | `0x004458df` | 目标 `player[0x39] = 2/3`（本回合只走 1 步） | ✅ | 无 |

### 全表统计

| 项 | 数值 |
|---|---|
| 可主动使用 | **26 / 30**（不可者为 18 復仇、19 嫁禍、20 免費、21 免罪） |
| 会查防御卡 | **3 / 30**（16 夢遊、17 陷害、26 查稅） |
| 反应式防御卡 | **4 / 30**（18、19、20、21，全部是 2 字节空桩） |
| 卡名一律取自 | 表 A：`card_data[i].+0` → `0x466ac2` 起的 Big5 打包串（§1.1.1） |

`@source` 全表数据来自本文件各卡小节；防御卡一列另有穷举扫描佐证
（`VA 0x4413ad` 的 18 个调用点，见表内 @source）。

## 十三、★ 目标拾取跳表 `0x00445e2d`（**8 组**，2026-09-18 补齐）

卡片的「能对谁用」不是写在逐卡函数里，而是**目标拾取窗口的红叉规则**。
索引取自**卡片参数的高字节**（它被写进全局 `[0x48c595]`），而「照到的是什么」在
`[0x48c594]`：

```asm
; 卡片的 selectionParam 低 16 位 = 0xHHLL：LL 是"可选类别"掩码，HH 是"确认处理器号"
; HH == 0 → 没有确认处理器，直接接受（0x44630a：test byte [0x48c595],0xff / je 0x4465b6）
004462e7  test byte ptr [0x48c594], 0x20   ; bit5 = 物件
004462f0  test bh, 0x80 …                  ; 物件编码要求 bit15 且 handle 非 0
0044630a  test byte ptr [0x48c595], 0xff
00446311  je   0x4465b6                    ; ★ HH==0：直接走共享出口（此处 ebp==1 ⇒ 接受）
00446317  xor  ebp, ebp
00446319  mov  eax, dword ptr [0x48c594]
0044631e  and  eax, 0xff00
00446323  shr  eax, 8
00446326  dec  eax                         ; ★ 1 基转 0 基
00446327  cmp  eax, 7 / ja 0x4465b6
00446330  jmp  dword ptr [eax*4 + 0x445e2d]
```

⚠️ `0x004465b6` 是**共享出口**，含义由 `ebp` 决定：
`test ebp, ebp / je 0x4465f4` —— `ebp==0` 走 `0x4465f4`（置 `[0x48c580]=5`、
`[0x48c584]=0`，即**红叉**），`ebp==1` 落到 `0x4465ba`（把选中编码写进 `[0x48c584]`，**接受**）。
从跳表进来的那次 `ebp` 已在 `0x446317` 清零，所以**跳表第 3 项就是无条件拒绝**。

`0x00445e2d` 是 8 项跳表（`gen/jumptables.json` 抽出的原文）：

`@source` `VA 0x4462e7`、`VA 0x44630a`、`VA 0x446319`、`VA 0x445e2d`、`VA 0x48c594`、`VA 0x48c595`。

| 组（参数高字节）| 目标 | 判据（汇编摘要）| 30 张卡里谁用 |
|---|---|---|---|
| 1 | `0x00446337` | 地块：`owner == 我+1` 才收（**不查等级**）；設施：`owner == 我+1` 且 `level != 0` | **无**（表里有、30 张卡都没用到）|
| 2 | `0x0044639a` | 取我脚下那格的编码（`node[me.nodeId].+0x20`），**选中同一格 → 拒绝**，且类别必须一致 | `0xe0c0202`：換地卡(4)、換屋卡(5) |
| 3 | `0x004465b6` | 无条件拒绝（`ebp==0` 的共享出口）| **无** |
| 4 | `0x00446434` | **玩家**：必须有玩家位（`test bl,0xf`），且选中位含 `1 << 当前玩家` → 拒绝 | `0xe0c0410`：均貧(2)、搶奪(13)、查稅(26)、同盟(29) |
| 5 | `0x00446457` | **地块/設施**：`owner == 我+1` → 拒绝；`level == 0` → 拒绝 | `0xe0c0506`：**怪獸卡(11)** |
| 6 | `0x004464c3` | 同组 5，**外加物件分支**（见 13.1）| `0xe0c0626`：**拆除卡(12)** |
| 7 | `0x00446569` | 必须有玩家位，且选中位含 `1 << 当前玩家` → 拒绝（写法同组 4 的后半）| `0xe0c0710`：夢遊卡(16)、陷害卡(17) |
| 8 | `0x0044657c` | 地块/設施：`owner != 0` **或** `level != 0` → 拒绝（只收无主空地）| **无** |

★ 组 1 / 3 / 8 在 30 张卡里**没有使用者**（对照 `@rich4/rendered` 的
`selectionParam` 全表：高字节只出现 0 / 2 / 4 / 5 / 6 / 7）——它们是通用拾取窗口留下的
槽位，**未决**：是否有非卡片流程（例如改建/購地 UI）用到组 8 的那条「只收无主空地」，
本轮**未查**，故只登记事实。

### 13.1 组 5 与组 6 的**唯一差别**：物件分支

两组的「地块」与「設施」两支**逐条同形**（`edi` = 地块记录、`esi` = 設施记录，
都查 `+0x19` owner 与 `+0x1a` level）：

```asm
; 组 5（怪獸卡，0x00446457）—— 非地块的值**直接拒绝**
00446489  cmp  ebx, 0xfa0 / jle 0x4465b6      ; ≤ 4000 → 拒绝
00446495  cmp  ebx, 0x1770 / jge 0x4465b6     ; ≥ 6000 → 拒绝
; 组 6（拆除卡，0x004464c3）—— 非地块的值**落到物件分支**
004464f6  cmp  ebx, 0xfa0 / jle 0x446528
004464fe  cmp  ebx, 0x1770 / jge 0x446528
00446528  test bh, 0x80 / je 0x4465b6         ; 必须带 bit15（物件编码 0x8000 | handle<<8）
00446533  and  ecx, 0x7f00 / sar ecx, 8 / dec ecx
00446546  mov  cl, byte ptr [eax*8 + 0x496d08]  ; objects_info[handle-1].+0（类型，步长 24）
0044654d  cmp  ecx, 0x10 / je 收                ; 路障 16
00446556  cmp  ecx, 0x11 / je 收                ; 地雷 17
0044655f  cmp  ecx, 0x12 / jne 0x4465b6         ; 定時炸彈 18
```

⇒ **怪獸卡打不到地图物件，拆除卡能打路障/地雷/定時炸彈这三种**。
`test bh, 0x80` 用位 15 当「这是物件编码」的判据，与
`cards/summon.ts` 的物件编码约定一致。

✅ 复刻侧核对（2026-09-18）：`cards/land-cards.ts` 的 `demolishLikeTargetAllowed`
（owner/level 两条）被 11 与 12 两张卡**共用是对的**（那两支逐字同形）；
物件那一支挂在 `cards/registry.ts` 的 `case 12` 上（**不是 case 11**），
与本节一致。`land-cards.ts` 注释把物件分支的出处记作「跳表组 6 / `VA 0x00446528`」，
按本节口径**成立**（组 6 = 拆除卡那一组 = `0x004464c3`，`0x00446528` 是它内部的分支入口）。

`@source` `VA 0x445e2d`、`VA 0x4462e7`、`VA 0x44630a`、`VA 0x446319`、`VA 0x446337`、
`VA 0x44639a`、`VA 0x446434`、`VA 0x446457`、`VA 0x4464c3`、`VA 0x446528`、
`VA 0x446569`、`VA 0x44657c`、`VA 0x4465b6`、`VA 0x4465f4`、`VA 0x496d08`、
`VA 0x48c594`、`VA 0x48c595`、`VA 0x48c584`、`VA 0x48c580`、`VA 0x443d22`、`VA 0x40e14d`。
