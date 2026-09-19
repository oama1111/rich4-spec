# 道具系统（Tools）

> 真值：`../Rich4/rich4.exe`（602,112 字节，ImageBase 0x400000）。
> 本文件所有 `@source` 均为原版虚拟地址（VA），可逐字节复核。
> 上游 `rich4-re/asm/rich4_tool_*.asm` 在本文件中**只作为线索**，每条结论都回 exe 复核过。

---

## 〇、本文件的验证方式与证据级别

### 验证方式（可复现）

1. **反汇编**：`rich4-spec/tools/rich4dis.py`（全量建图）+ 一个等价于 `rich4-remake/tools/disasm.py va` 的自足脚本，对指定 VA 做按需裁决。
2. **逐指令对照**：把 13 个 `rich4_tool_*.asm` 用「标签切段 → 去注释 → 与 exe 反汇编逐条对齐」的脚本比对，得到**指令条数 + 尾部一致性**结论（§7）。
3. **数据表**：直接按 `VA → 文件偏移` 读原始字节（`VA = 0x401000 + (off - 1024)`，因该 PE 的节表 `VirtualSize` 全为 0）。
4. **字节模式搜索**：对「谁写了某个结构体字段」这类问题，直接在 `AUTO` 节里搜机器码（例如搜 `C6 4? 1E` 找 `mov byte [reg+0x1E], imm8`），避免只依赖上游符号。

### 证据级别

| 级别 | 含义 |
|---|---|
| **A** | 逐指令对照 exe 可直接复核；本文给出 VA + 指令原文 |
| **B** | 由 A 级证据经受控推论得到；文中写明推论链 |
| **C** | **未决**：exe 中已定位到相关代码，但语义/取值范围/可达性无法从静态证据唯一确定 |

> **本文件的诚实边界**：§8 集中列出全部 C 级条目。凡未标注级别者即为 A。
> 特别地，「上游与 exe 矛盾」一节（§7）中有**一条被推翻的已知指控**，请优先阅读。

---

## 一、道具总表

### 1.1 数据表 `tool_table` @ `VA 0x0047fee2`，13 项 × 8 字节

表项布局（由 §3.5 / §3.3 / §5 三处代码交叉确认）：

| 偏移 | 类型 | 字段 | 证据 |
|---|---|---|---|
| `+0` | `char *` | 名称（Big5 字符串指针） | `0x42ec5b` `mov ebp,[ebx*8 + 0x47fee2]` |
| `+4` | `uint8` | 商店/池初始存量（本文记作 `initAmount`） | `0x4071ba` |
| `+5` | `uint8` | 点数售价 | `0x445bf1`、`0x42d290`、`0x42ec78` |
| `+6` | `uint8` | 未定位（见 §8-⑥） | 在 `gen/xrefs.json` 中无读取者 |
| `+7` | `uint8` | 分类码（商店上架 / AI 筛选用） | `0x4284be`、`0x42e931`、`0x42f265` |

> 说明：`+5`/`+7` 的多数读取点用「寄存器基址 + 索引」寻址（如 `[ebx*8 + 0x47fee7]`），
> 因此 `xrefs.json` 只会把**以字面地址为基址**的那几处归到该地址。
> 上表同时列出字面读取点与我直接反汇编确认的寄存器基址读取点。

**表边界的外部佐证（A）**：卡片数据表位于 `0x47fdea`，31 项 × 8 字节 = `0x47fdea + 0xF8 = 0x47fee2`，
即**道具表紧接卡片表之后**。实测 `0x47feda` 项的名称指针 `0x466b89` 解出为「烏龜卡」（卡片第 31 项），
而 `0x47fee2` 项解出为「機器娃娃」（道具第 1 项），两表首尾相接、无重叠。

### 1.2 13 项实测值（全部 A 级）

| 编号(=下标+1) | 名称(Big5) | 名称指针 | `initAmount`(+4) | 售价点数(+5) | `f6` | `f7` |
|---|---|---|---|---|---|---|
| 1 | 機器娃娃 | `0x00466b90` | 10 | 15 | 0 | 0 |
| 2 | 路障 | `0x0046669d` | 10 | 30 | 0 | 1 |
| 3 | 地雷 | `0x004666a2` | 10 | 25 | 0 | 1 |
| 4 | 定時炸彈 | `0x004666a7` | 10 | 25 | 0 | 1 |
| 5 | 機車 | `0x00466b99` | 10 | 80 | 0 | 0 |
| 6 | 汽車 | `0x00466b9e` | 10 | 150 | 1 | 0 |
| 7 | 飛彈 | `0x00466ba3` | 10 | 100 | 1 | 2 |
| 8 | 遙控骰子 | `0x00466ba8` | 10 | 30 | 1 | 0 |
| 9 | 機器工人 | `0x00466bb1` | 0 | 30 | 2 | 1 |
| 10 | 時光機 | `0x00466bba` | 0 | 40 | 2 | 2 |
| 11 | 傳送機 | `0x00466bc1` | 0 | 95 | 2 | 1 |
| 12 | 工程車 | `0x00466bc8` | 0 | 150 | 2 | 2 |
| 13 | 核子飛彈 | `0x00466bcf` | 0 | 250 | 2 | 2 |

```asm
; 原始字节（VA 0x0047fee2 起）
0047fee2  90 6b 46 00 0a 0f 00 00    ; [ 1] 機器娃娃 ptr=00466b90 init=0a price=0f f6=00 f7=00
0047feea  9d 66 46 00 0a 1e 00 01    ; [ 2] 路障     ptr=0046669d init=0a price=1e f6=00 f7=01
0047fef2  a2 66 46 00 0a 19 00 01    ; [ 3] 地雷
0047fefa  a7 66 46 00 0a 19 00 01    ; [ 4] 定時炸彈
0047ff02  99 6b 46 00 0a 50 00 00    ; [ 5] 機車     price=0x50=80
0047ff0a  9e 6b 46 00 0a 96 01 00    ; [ 6] 汽車     price=0x96=150
0047ff12  a3 6b 46 00 0a 64 01 02    ; [ 7] 飛彈     price=0x64=100
0047ff1a  a8 6b 46 00 0a 1e 01 00    ; [ 8] 遙控骰子 price=0x1e=30
0047ff22  b1 6b 46 00 00 1e 02 01    ; [ 9] 機器工人 init=0
0047ff2a  ba 6b 46 00 00 28 02 02    ; [10] 時光機   init=0 price=0x28=40
0047ff32  c1 6b 46 00 00 5f 02 01    ; [11] 傳送機   init=0 price=0x5f=95
0047ff3a  c8 6b 46 00 00 96 02 02    ; [12] 工程車   init=0 price=0x96=150
0047ff42  cf 6b 46 00 00 fa 02 02    ; [13] 核子飛彈 init=0 price=0xfa=250
```

> ⚠️ **对「initAmount 全为 0 解释了道具 9..13 需研发」这一背景说法的修正（A）**：
> `initAmount` 的唯一读取点是 `0x4071ba`，其循环条件是 **`i < 8`**：
> ```asm
> 004071ba  mov  al, byte ptr [ebx*8 + 0x47fee6]   ; tool_table[i].initAmount
> 004071c1  mov  byte ptr [ebx + 0x497320], al     ; remain_tool_amount[i] = al
> 004071c7  inc  ebx
> 004071c8  cmp  ebx, 8
> 004071cb  jl   0x4071ba
> ```
> 也就是说 **道具 9..13 的 `+4` 字段根本不会被读取**（它是死数据）。
> 「9..13 不能买」的真正原因不是这个字段为 0，而是 §3.5 的商店循环上限写死为 8。

### 1.3 名称/台词字符串表 `tool_strings` @ `VA 0x00480d5a`（A）

13 个道具的「使用台词」按 `+4*idx` 排布：

| 偏移 | 指针 | 台词（Big5，`#nnnn` 为语音号） | 使用者 |
|---|---|---|---|
| `+0x00` | `0x00468381` | `#0236替我除掉\n障礙物！` | 機器娃娃 |
| `+0x04` | `0x00468398` | `#0237此路是我開，\n此樹是我栽∼` | 路障 |
| `+0x08` | `0x004683b7` | `#0238小心！\n步步危機∼` | 地雷 |
| `+0x0c` | `0x004683ce` | `#0239送你們一個\n小禮物∼` | 定時炸彈 |
| `+0x10` | `0x004683e7` | `#0234衝啊！\n野牛號！` | 機車 |
| `+0x14` | `0x004683fc` | `#0235嗨！寶貝∼\n一起去兜風吧！` | 汽車 |
| `+0x18` | `0x0046841b` | `#0240炸得你\n雞飛狗跳∼∼` | 飛彈 |
| `+0x1c` | `0x00468434` | `#0241要幾點有幾點！\n開∼` | 遙控骰子 |
| `+0x20` | `0x0046844d` | `#0246兄弟們！\n上工了∼` | 機器工人 |
| `+0x24` | `0x00468464` | `#0242如果再回到\n從前∼` | 時光機 |
| `+0x28` | `0x0046847b` | `#0243瞬間移動！！` | 傳送機 |
| `+0x2c` | `0x0046848d` | `#0244拆除大隊來了！` | 工程車 |
| `+0x30` | `0x004684a1` | `#0245各∼位∼觀∼眾\n．．．．。` | 核子飛彈 |
| `+0x34` | `0` | （空） | — |
| `+0x38` | `0x004684c0` | `#0247誰敢擋我\n去路？！` | **踩到路障时**（`0x41bd56`） |
| `+0x3c` | `0x004684d7` | `#0248誰這麼缺德？！` | **踩到地雷时**（`0x41beff`） |
| `+0x40` | `0x004684eb` | `#0249我不要∼∼∼` | **被装上定时炸弹时**（`0x41c063`） |

> 台词表按玩家角色分块：索引写法为 `[role_id * 0x68 + 0x480d5a + off]`，
> 其中 `role_id = players_state[cur].+0x13 (0x496b7b)`（角色编号），
> 见 `0x446b16`–`0x446b24`。本表给出的是 `role_id = 0` 的第 0 块。

### 1.4 效果入口函数表 @ `VA 0x00475dd9`，13 项 × 4 字节（A）

```asm
; 实测
    [ 1] 0x00446afb    [ 2] 0x00446baa    [ 3] 0x00446c88
    [ 4] 0x00446d69    [ 5] 0x00446e4a    [ 6] 0x00446f05
    [ 7] 0x00446fbc    [ 8] 0x004470f8    [ 9] 0x00447295
    [10] 0x00447387    [11] 0x00447428    [12] 0x004479d2
    [13] 0x00447ace
```
调度点（**1 基**索引，故代码里写成 `表基址 − 4`）：
```asm
; @source 0x447f51 与 0x44807e（均在 _rich4_ui_use_tool_entry 内，
;          机器码 ff 14 85 d5 5d 47 00 实测两处）
call dword ptr [eax*4 + 0x475dd5]     ; = _rich4_tool_functions[eax-1]，eax = 道具编号
```
`0x475dd5 + 1*4 = 0x475dd9` ✓ 与实测表首一致。

---

## 二、汇总表（编号 / 名称 / 入口 VA / 一句话效果 / 放置类 / 需研究所研发）

| 编号 | 名称 | 入口 VA | 一句话效果 | 放置类 | 需研究所 |
|---|---|---|---|---|---|
| 1 | 機器娃娃 | `0x00446afb` | 把自己复制成「实体 8」并让它走**固定 9 步**（台词宣称为「除掉障礙物」） | 否 | 否（商店 + 开局赠送） |
| 2 | 路障 | `0x00446baa` | 在选定格放置路障（对象类型 `0x10`），踩到者被拦下 | **是** | 否 |
| 3 | 地雷 | `0x00446c88` | 在选定格放置地雷（对象类型 `0x11`），踩到者车辆报废 + 住院 3 天 | **是** | 否 |
| 4 | 定時炸彈 | `0x00446d69` | 在选定格放置定时炸弹（对象类型 `0x12`），被踩到后**转移**给踩到者并倒计时 38 | **是** | 否 |
| 5 | 機車 | `0x00446e4a` | 交通方式 = 1，骰子数 = **2**；若原为汽車则退回背包 | 否 | 否 |
| 6 | 汽車 | `0x00446f05` | 交通方式 = 2，骰子数 = **3**；若原为機車则退回背包 | 否 | 否 |
| 7 | 飛彈 | `0x00446fbc` | 选定一格：摧毁其地产/设施（范围内），并让被标记的玩家住院 3 天 | 否 | 否 |
| 8 | 遙控骰子 | `0x004470f8` | 指定下一次骰子点数（写 `0x475dd8`，使骰子数强制为 1） | 否 | 否 |
| 9 | 機器工人 | `0x00447295` | 选定一块地/一座设施，**等级 +1**（上限 5，到顶播放 `mkf 0x20b`） | 否 | **是**（项目 1） |
| 10 | 時光機 | `0x00447387` | 把游戏状态回滚到「本回合开始时的快照」（含玩家/特殊实体/物件/卡/道具） | 否 | **是**（项目 2） |
| 11 | 傳送機 | `0x00447428` | 交换两块地/两座设施的归属与等级（附带 +0x30/+0x34 的迁移），或传送实体 | 否 | **是**（项目 3） |
| 12 | 工程車 | `0x004479d2` | 交通方式 = `0x1f`，骰子数 = 1；把已有的機車/汽車退回背包 | 否 | **是**（项目 4） |
| 13 | 核子飛彈 | `0x00447ace` | 同飛彈但范围 = 全地图，且摧毁为「清空归属+等级+类型」 | 否 | **是**（项目 5） |

---

## 三、数据结构与公共例程

### 3.1 玩家持有量 `player_tool_amount` @ `VA 0x0049915c`（A）

- 步长 **15**，4 名玩家（0..3）共 60 字节：
  `push 0x3c; push 0; push 0x49915c; call memset` @ `0x40718f`。
- 寻址：`amount(player, tool) = byte [0x49915c + 15*player + (tool-1)]`
  ```asm
  ; @source 0x445aa2 (_rich4_after_player_use_tool)
  00445aa2  mov  ecx, dword ptr [esp + 8]      ; arg2 = tool（1 基）
  00445aa6  mov  edx, dword ptr [esp + 4]      ; arg1 = player
  00445aaa  mov  eax, edx
  00445aac  shl  eax, 2
  00445aaf  add  eax, edx
  00445ab1  mov  edx, eax
  00445ab3  shl  eax, 2
  00445ab6  sub  eax, edx                      ; eax = 15*player
  00445ab8  add  eax, ecx
  00445aba  mov  dl, byte ptr [eax + 0x49915b] ; ★ = [0x49915c + 15p + tool-1]
  ```

### 3.2 商店库存/可放置池 `remain_tool_amount` @ `VA 0x00497320`，**8 字节**（A）

- 只覆盖道具 1..8。**这是「9..13 不可购买」的结构性原因**。
- 初始化（新游戏）：`remain_tool_amount[i] = tool_table[i].initAmount`，`i = 0..7` → 全为 10。
- 存档时按 8 字节整块读写（§6.4）。

### 3.3 公共例程

| 函数 | VA | 语义（A） |
|---|---|---|
| `rich4_receive_tool(player, tool)` | `0x00445a4d` | 见下方原文 |
| `rich4_after_player_use_tool(player, tool)` | `0x00445aa2` | 见下方原文 |
| `rich4_receive_random_tool(player)` | `0x00445ada` | 从 `remain_tool_amount[0..7]` 按权重抽一个道具并发放 |
| `rich4_player_sell_all_tools(player)` | `0x00445b3f` | 全部道具折成点数（**全价**），交通工具退回背包 —— 见 §3.4（通道 2 已实证）|
| `rich4_player_sell_all_the_card(player)` | `0x00441f21` | 全部手牌折成点数（**全价**）并清空 15 个槽 —— 见 §3.4 |
| `rich4_player_buy_tool(player, tool)` | `0x0042d272` | `receive_tool` + `points -= price`，返回 `10*price` |
| `fcn_0042d1b2(player, count, tool)` | `0x0042d1b2` | 卖出 `count` 个：`points += floor(price*count*0.9)`，`remain += count`（tool ≤ 8） |
| `rich4_place_object(type, node, a, b)` | `0x0040e033` | 见 §6.1 |
| `rich4_remove_object(objidx_plus_1)` | `0x0040e14d` | 见 §6.2 |
| `rich4_select_instance_with_mouse(mask)` | `0x00446ae8` | 人类玩家用鼠标选目标，返回编码选择值（0 = 取消） |
| `rich4_get_ai_tool_param_value(0)` | `0x00420eee` | AI 的目标参数 |
| `rich4_player_say(player, 0, str)` | `0x0044ef41` | 台词 |

`receive_tool` 原文（容量上限 **9**）：
```asm
; @source 0x445a4d
00445a64  cmp  byte ptr [edx + eax + 0x49915b], 9   ; amount >= 9 ?
00445a6c  jae  0x445aa0                              ; 满了 → 直接返回
00445a6e  cmp  edx, 8
00445a71  jg   0x445a87                              ; tool > 8 → 跳过库存检查
00445a73  mov  bh, byte ptr [edx + 0x49731f]         ; remain_tool_amount[tool-1]
00445a79  test bh, bh
00445a7b  je   0x445aa0                              ; 库存 0 → 直接返回
00445a7d  mov  cl, bh
00445a7f  dec  cl
00445a81  mov  byte ptr [edx + 0x49731f], cl         ; 库存 −1
00445a87  ...  inc  byte ptr [edx + eax + 0x49915b]  ; amount +1
```

`after_player_use_tool` 原文（**回池** 条件：`tool <= 8`）：
```asm
; @source 0x445aa2
00445ac0  test dl, dl
00445ac2  je   0x445ad9               ; 自己没有该道具 → 什么都不做
00445ac8  mov  byte ptr [eax + 0x49915b], dh   ; amount −1
00445ace  cmp  ecx, 8
00445ad1  jg   0x445ad9               ; tool > 8 → 不回池
00445ad3  inc  byte ptr [ecx + 0x49731f]       ; remain_tool_amount[tool-1] +1
```

> ⚠️ **重要差异（A）**：13 个道具里，只有 **7 飛彈、8 遙控骰子、9 機器工人、10 時光機、
> 11 傳送機、13 核子飛彈** 走 `after_player_use_tool`（会回池）；
> **1 機器娃娃**也走它。而 **2 路障 / 3 地雷 / 4 定時炸彈 / 5 機車 / 6 汽車 / 12 工程車**
> 是**直接 `dec` 玩家持有量、不回池**（见各节原文）。
> 后果：放置类道具一旦放下就从经济里「消失」，只有当 `remove_object` 把对象销毁时
> 才 `inc remain_tool_amount[...]`（§6.2），使商店库存随游戏进行**单向增加**。

### 3.35 ★★ 变卖全部道具 / 全部手牌 `0x445b3f` / `0x441f21`（A，2026 本轮通道 2 实证）

> 差分测试：`tests/test_sell_all.py`（**35/35**，含两张售价表的通道 1 复核）。
> 调用点：命运事件 32（`fortune.md`）、破产清算（返回值**丢弃**）、
> 財神/死神/魔法屋的没收与變賣分支（`gods.md`、`magic-house.md`）。

```asm
; ── _rich4_player_sell_all_tools(player) @source 0x445b3f（213 字节）──
00445b49  dl = byte [player + 0x496b79]          ; traffic_method
00445b51  if (dl == 0) goto 卖道具                 ; ★ 走路 ⇒ 整块跳过（连清标志/重绘都不做）
00445b55  bl = dl & 3
00445b79  bl == 1 → add byte [15p + 0x499160], bl ; ★ 折回**道具 5 機車**（+1）
00445b81  bl == 2 → inc byte [15p + 0x499161]     ; 道具 6 汽車
00445b89  bl == 3 → inc byte [15p + 0x499167]     ; ★ 道具 **12 工程車**（`0x1f & 3 == 3`）
00445b92  byte [player + 0x496b79] = 0            ; 下车
00445b9a  byte [player + 0x496b7a] = 1            ; 骰子回 1
00445ba2  call 0x40b93b(player)                   ; 重绘（纯表现）
00445bb0  for (i = 0; i < 13; i++) {              ; ★ 道具 1..13
            cl = byte [15p + i + 0x49915c]        ; 持有量（`0x49915b` 是空槽 0）
            if (cl == 0) continue
            if (i < 8) byte [i + 0x497320] += cl  ; ★ 只有编号 ≤8 回**商店库存**
            ebx += byte [i*8 + 0x47fee7] * cl     ; 道具表 +5 = **售价（原价）**
            byte [15p + i + 0x49915c] = 0         ; ★★ **清零**
          }
00445c0e  return ebx                              ; 變賣所得點券（调用方 `add word [+0x30], ax`）

; ── _rich4_player_sell_all_the_card(player) @source 0x441f21（82 字节）──
00441f33  for (ecx = 0; ecx < 15; ecx++) {        ; ★ 15 个手牌槽（槽里存的是**卡号**）
            dl = byte [15p + ecx + 0x499120]
            if (dl == 0) continue
            inc byte [dl + 0x499197]              ; ★ 卡片**全部**回商店库存（按卡号索引）
            ebx += byte [dl*8 + 0x47fdef]         ; 卡表 +5 = 售价
            byte [15p + ecx + 0x499120] = 0       ; ★★ **清零**
          }
00441ec9  return ebx
```

四条容易做错的：

1. **卖价是原价**（表项 `+5`），**不看物价指数、不打折** —— 与商店买入 /
   卖卡九折（`fcn_0042d1b2` 的 `floor(price*count*0.9)`）都不同。
2. **座驾「先折回道具栏、再一起卖掉」**（`0x445b79` 那三句在循环**之前**）
   ⇒ 开汽車去變賣，所得里包含那台車的 150 點，道具栏**不会**留下一台車。
3. **只有 ≤8 号道具回商店库存**（9..13 本就不限量）——**卡片则全部回**。
4. **两支都清空**（13 / 15 个槽逐个写 0）；返回值是**變賣所得**，
   破产清算那一支调用方**故意丢弃**它。

**数组边界（结构佐证）**：`0x499120 + 4×15 = 0x49915c`（手牌槽紧接道具持有表）、
`0x49915c + 4×15 = 0x499198 = 0x499197 + 1`（道具持有表紧接卡片库存），
库存表 `0x497320` 只覆盖道具 1..8。

### 3.4 「是人类玩家」判定

```asm
; @source 0x446b3d（每个道具函数的固定前缀）
imul eax, dword ptr [0x49910c], 0x68
cmp  byte ptr [eax + 0x496b7d], 1    ; players_state[cur].flags 的 bit0 = 1(人类) / 0(AI)
jne  <AI 分支>
```
`players_state` 基址 `0x496b68`，步长 `0x68`（4 名玩家）。
本文引用到的字段：

| 偏移 | 绝对地址 | 类型 | 含义（A/B） |
|---|---|---|---|
| `+0x08` | `0x496b70` | `uint16` | 屏幕 x（B） |
| `+0x0a` | `0x496b72` | `uint16` | 屏幕 y（B） |
| `+0x0c` | `0x496b74` | `uint16` | 当前格编号 |
| `+0x0e` | `0x496b76` | `uint16` | 未定位 |
| `+0x10` | `0x496b78` | `uint8` | 朝向/帧（B） |
| `+0x11` | `0x496b79` | `uint8` | **交通方式**：0=步行 1=機車 2=汽車 `0x1f`=工程車 |
| `+0x12` | `0x496b7a` | `uint8` | **骰子数** `ndices` |
| `+0x13` | `0x496b7b` | `uint8` | 角色编号（用于选台词块） |
| `+0x15` | `0x496b7d` | `uint8` | **状态旗标**：bit0=人类 bit6(`0x40`)=「本次被炸中」 |
| `+0x17` | `0x496b7f` | `uint8` | 与 `tool_table.f7` 相减做 AI 筛选（`0x42f265`） |
| `+0x30` | `0x496b98` | `uint16` | **点数**（购买/出售的计价货币） |
| `+0x32` | `0x496b9a` | `uint32` | 非 0 时 `fcn_0040cd07` 直接放弃（C：含义未定位） |
| `+0x40` | `0x496ba8` | `uint8` | **附身物件索引+1**（定時炸彈 / 神明） |
| `+0x4c` | `0x496bb4` | `int32[4]` | 对其他玩家的好感/敌意值 |

### 3.5 商店（道具店）

商店建筑节点范围 `0x1770 ≤ node < 0x1f40`，入口 `0x0042e931`。
货架构建循环（**上限写死 8**，这就是道具 9..13 不可购买的直接原因）：
```asm
; @source 0x42ec0b（循环头部/尾部）与 0x42ec23（循环体）
0042ec0b  mov  eax, dword ptr [esp + 0x130]
0042ec12  inc  eax
0042ec13  mov  dword ptr [esp + 0x130], eax
0042ec1a  cmp  eax, 8                            ; ★ 只遍历 0..7
0042ec1d  jge  0x42ecbb
0042ec23  mov  eax, dword ptr [esp + 0x130]
0042ec2a  cmp  byte ptr [eax + 0x497320], 0      ; remain_tool_amount[i] == 0 → 不上架
0042ec31  je   0x42ec0b
0042ec33  mov  al, byte ptr [esp + 0x130]
0042ec3a  inc  al
0042ec3c  mov  byte ptr [esi + 0x48c2f8], al     ; 上架列表 = 道具编号(i+1)
0042ec5b  mov  ebp, dword ptr [ebx*8 + 0x47fee2] ; 名称
0042ec78  mov  al, byte ptr [ebx*8 + 0x47fee7]   ; 售价
```
人类点击购买（`0x42e466`）：
```asm
0042e47a  cmp  byte ptr [eax + ebp + 0x49915b], 9   ; 自己已有 >= 9 → 拒绝
0042e482  jae  0x42e616
0042e488  push ebp                                    ; tool
0042e48f  push esi                                    ; current_player
0042e490  call 0x42d272                               ; buy_tool
```
`buy_tool` 原文（**点数扣减**）：
```asm
; @source 0x42d272
0042d272  push ebx
0042d273  mov  edx, dword ptr [esp + 0xc]      ; tool
0042d277  push edx
0042d278  mov  ecx, dword ptr [esp + 0xc]      ; player
0042d27c  push ecx
0042d27d  call 0x445a4d                        ; receive_tool
0042d282  add  esp, 8
0042d285  imul edx, dword ptr [esp + 8], 0x68  ; → player 结构
0042d28a  mov  eax, dword ptr [esp + 0xc]
0042d28e  xor  bh, bh
0042d290  mov  bl, byte ptr [eax*8 + 0x47fedf] ; ★ price（= 表项 +5）
0042d297  jmp  0x42d25c                        ; 与 buy_card 共享的尾码
; @source 0x42d25c（共享尾码）
0042d25c  sub  word ptr [edx + 0x496b98], bx   ; ★ points -= price
0042d263  xor  edx, edx
0042d265  mov  dl, bl
0042d267  mov  eax, edx
0042d269  shl  eax, 2
0042d26c  add  eax, edx
0042d26e  add  eax, eax                        ; 返回 10 * price
```
> **边界（A）**：人类购买路径**只检查「自己已有 < 9」**（`0x42e47a`），
> **不检查点数是否够**；`sub word` 是无符号回绕写。静态证据只能确认「会回绕」，
> 是否可达（例如货架是否已过滤掉买不起的道具）**未决**（§8-⑪）。

### 3.6 使用道具的 UI 入口 `_rich4_ui_use_tool_entry` @ `0x00447d97`

被 `0x447d97` 的两个调用点（`rich4.asm:11644`、`rich4_ui_clicking_top_panel.asm:88`）触发；
调度 `[eax*4 + 0x475dd5]`（§1.4）。

---

## 四、逐个道具

> 每个函数的固定前缀（约 11 条指令）为：
> `say(tool_strings[tool-1])` → 取目标（人类用鼠标、AI 用参数）→ `if (target == 0) return 0`。
> 下文只摘差异部分。返回值语义（B）：**0 = 取消/未消耗**，非 0 = 已消耗。

### 4.1 機器娃娃（编号 1，`0x00446afb`，37 条指令）

> ★ **本轮修正**：早期写「让它**按骰子走一步**」。实为**固定 9 步** ——
> `@source 0x0040deb9` 起：`mov esi, 9` → `mov [0x48baf8], esi`（步数全局）
> 与 `mov [0x4749d4], esi`。**没有掷骰**，故**不消耗随机数**。

**效果**：把当前玩家「复制」为**实体 8**，然后让实体 8 走一次普通骰子移动。

```asm
; @source 0x446afb
00446afb  push ebx
00446afc  push 1                                       ; tool = 1
00446afe  mov  edx, dword ptr [0x49910c]               ; current_player
00446b04  push edx
00446b05  call 0x445aa2                                ; ★ 先消耗，再做事
00446b0a  add  esp, 8
...
00446b24  mov  ebx, dword ptr [eax + 0x480d5a]         ; '#0236替我除掉\n障礙物！'
00446b2a  push ebx / push 0 / push ecx
00446b2e  call 0x44ef41                                ; player_say
...
00446b3d  mov  dx, word ptr [eax + 0x496b70]           ; 玩家 屏幕x
00446b44  mov  word ptr [0x498e68], dx                 ; → special_players_state[4] +0x40
00446b4b  mov  dx, word ptr [eax + 0x496b72]           ; 屏幕y
00446b52  mov  word ptr [0x498e6a], dx                 ; → +0x42
00446b59  mov  dx, word ptr [eax + 0x496b74]           ; 当前格
00446b60  mov  word ptr [0x498e6c], dx                 ; → +0x44
00446b67  mov  dx, word ptr [eax + 0x496b76]
00446b6e  mov  word ptr [0x498e6e], dx                 ; → +0x46
00446b75  mov  dl, byte ptr [0x49910c]
00446b7b  mov  byte ptr [0x498e70], dl                 ; → +0x48 = 原玩家下标
00446b81  mov  al, byte ptr [eax + 0x496b78]
00446b87  mov  byte ptr [0x498e71], al                 ; → +0x49
00446b8c  xor  ah, ah
00446b8e  mov  byte ptr [0x498e72], ah                 ; → +0x4a = 0
00446b94  mov  dword ptr [0x49910c], 8                 ; ★ current_player := 8
00446b9e  call 0x40dd1f                                ; 让实体 8 做一次骰子移动
00446ba3  mov  eax, 1
00446ba5  pop  ebx
00446ba6  ret
```

- **作用目标**：无（不选目标，人类/AI 走同一路径）。
- **合法性判定**：无。函数内不检查任何条件；消耗在函数开头无条件发生。
- **实体编号映射（A）**：`special_players_state` 基址 `0x498e28`，步长 `0x10`；
  「特殊玩家下标 i（4..8）」对应数组元素 `i-4`。
  实体 8 → `0x498e28 + 4*0x10 = 0x498e68` ✓ 与上文写入地址一致。数组共 **5 项**
  （存档写 `5 × 0x10`，§6.4）。
- **边界**：
  - `target` 不存在 → 不适用（不选目标）。
  - 在自己身上用 → 无「自己」概念。
  - **C（未决）**：台词声称「除掉障礙物」，但 §6.3 的触发分派里，
    `current_player >= 8` 时路障分支（`0x41bcf0`）与地雷分支（`0x41be65`）都会
    绕到只在 `current_player == 4` 才生效的支路，最终**什么都不做**。
    我在 exe 中**没有找到**实体 8 清除路障/地雷的代码路径。详见 §8-①。

### 4.2 路障（编号 2，`0x00446baa`，68 条指令）

**效果**：在选定格放置对象类型 `0x10` 的路障（最多同时存在 **10** 个，§6.1）。

```asm
; @source 0x446baa
00446baa  push ebx
00446bc2  mov  ecx, dword ptr [eax + 0x480d5e]        ; '#0237此路是我開，\n此樹是我栽∼'
00446bc8  push ecx
00446bc9  push 0
00446bcb  push edx
00446bcc  call 0x44ef41                              ; player_say
00446bd1  add  esp, 0xc
00446bd4  imul eax, dword ptr [0x49910c], 0x68
00446bdb  cmp  byte ptr [eax + 0x496b7d], 1
00446be2  jne  0x446bed
00446be4  push 1                                     ; ★ 人类：mask = 1
00446be6  call 0x446ae8                              ; select_instance_with_mouse
00446beb  jmp  0x446bf4
00446bed  push 0
00446bef  call 0x420eee                              ; AI 参数
00446bf4  add  esp, 4
00446bf7  mov  ebx, eax
00446bf9  test ebx, ebx
00446bfb  je   0x446c84                              ; ★ 取消 → 不消耗、返回 0
00446c01  push 0
00446c03  push 0
00446c05  push ebx                                   ; node
00446c06  push 0x10                                  ; ★ object type = 0x10
00446c08  call 0x40e033                              ; rich4_place_object → 返回 slot+1
00446c0d  mov  ecx, eax
00446c0f  add  esp, 0x10
00446c12  push 0x64
...
00446c4e  call 0x40e669                              ; animate_object（放置动画，末参数 0x64）
00446c53  add  esp, 0x18
00446c56  push 0
00446c58  push 0x48236a
00446c5d  call 0x4542ce                              ; 音效
00446c65  call 0x41d546                              ; refresh_screen
...
00446c7e  dec  byte ptr [eax + 0x49915d]             ; ★ 直接扣，不经 after_player_use_tool
00446c84  mov  eax, ebx
00446c86  pop  ebx
00446c87  ret
```
- **合法目标**：任意格（无范围检查；`place_object` 里才有槽位溢出处理，§6.1）。
- **边界**：
  - 取消（返回 0）→ **不消耗**。
  - 放置数达 10 → `place_object` 的槽扫描失败，返回 `ebx+1`（= 范围末值）而**不写入任何槽**，
    但本函数**仍然扣 1 个持有量并播动画**。属于原版行为（A：`0x40e084 jge 0x40e13f`）。
  - 库存：**不回池**（直接 `dec`）。
- **触发时**（踩到）：§6.3。

### 4.3 地雷（编号 3，`0x00446c88`，68 条指令）

与路障同构，差异逐条列全：

| 项 | 路障 | 地雷 |
|---|---|---|
| 台词偏移 | `+4`（`#0237`） | `+8`（`#0238小心！\n步步危機∼`） |
| 鼠标 mask | `1` | `0x10001` |
| 对象类型 | `0x10` | **`0x11`** |
| 音效指针 | `0x48236a` | `0x482372` |
| 扣减下标 | `+1`（`0x49915d`） | **`+2`**（`0x49915e`） |
| 入口 | `0x446baa` | `0x446c88` |

- **踩到的效果**（`0x41be5f`）：`place_object` 槽被销毁 → 车辆报废（`fcn_0040cd07`）
  → 播电影资源 `mkf 0x20d` → 台词 `#0248誰這麼缺德？！` → **住院 3 天**。
- **C**：见 §8-①（实体 8 是否免疫，已在 exe 中确认为「不做任何事」但不清楚设计意图）。

### 4.4 定時炸彈（编号 4，`0x00446d69`，68 条指令）

| 项 | 值 |
|---|---|
| 台词偏移 | `+0x0c`（`#0239送你們一個\n小禮物∼`） |
| 鼠标 mask | `0x20001` |
| 对象类型 | **`0x12`** |
| 音效指针 | `0x48235a` |
| 扣减下标 | `+3`（`0x49915f`） |
| 入口 | `0x446d69` |

- 放置时 `arg3 = arg4 = 0`（`push 0; push 0; push node; push 0x12`），
  即 `objects_info.+4 = 0`、`.+5 = 0`。**归属与倒计时是在被踩到时才写入的**（§6.3）。

### 4.5 機車（编号 5，`0x00446e4a`，56 条指令）

```asm
; @source 0x446e4a
00446e4a  push ebx
00446e4b  push esi
00446e4c  push edi
00446e4d  imul eax, dword ptr [0x49910c], 0x68
00446e54  mov  dl, byte ptr [eax + 0x496b79]     ; traffic_method
00446e5a  cmp  dl, 1
00446e5d  jne  0x446e66
00446e5f  xor  edx, edx
00446e61  jmp  0x446eff                          ; ★ 已在機車上 → 直接返回 0，不消耗
00446e66  cmp  dl, 2
00446e69  jne  0x446e85
00446e7f  inc  byte ptr [eax + 0x499161]         ; ★ 原为汽車 → 汽车退回背包（下标 5）
00446e85  imul eax, dword ptr [0x49910c], 0x68
00446e8c  mov  byte ptr [eax + 0x496b79], 1      ; traffic = 1
00446e93  mov  byte ptr [eax + 0x496b7a], 2      ; ★ ndices = 2
00446ea1  call 0x40b93b                          ; update_player_sprite
00446ea9  push 1
00446eab  push 0
00446ead  push 0
00446eaf  call 0x41d476
00446ece  mov  edi, dword ptr [eax + 0x480d6a]   ; '#0234衝啊！\n野牛號！'
00446ed8  call 0x44ef41
00446ee0  mov  edx, dword ptr [0x49910c]
00446ef4  mov  edx, 1
00446ef9  dec  byte ptr [eax + 0x499160]         ; ★ 直接扣（下标 4），不回池
00446eff  mov  eax, edx
00446f01  pop  edi / pop  esi / pop  ebx / ret
```
- **作用目标**：自己（无目标选择）。
- **合法性判定**：`traffic == 1` → 返回 0 且不消耗；否则一律成功。
- **边界**：`traffic == 2`（汽車）→ 汽车退回背包；`traffic == 0x1f`（工程車）→
  **不会退回**工程車（本函数只判 `== 2`）。工程車从此从玩家持有量里消失（§4.12）。
- 骰子数 = 2 → 每回合掷 2 颗（2..12 步，A：`0x419572` 的 `ndices` 循环）。

### 4.6 汽車（编号 6，`0x00446f05`，52 条指令）

与機車镜像：

| 项 | 機車 | 汽車 |
|---|---|---|
| 台词 | `+0x10` | `+0x14`（`#0235嗨！寶貝∼\n一起去兜風吧！`） |
| 重复使用判定 | `traffic == 1` | `traffic == 2` |
| 退回对象 | 下标 `+5`（汽車） | 下标 `+4`（機車） |
| `traffic` 设为 | `1` | `2` |
| `ndices` 设为 | **2** | **3** |
| 扣减下标 | `+4` | `+5` |

### 4.7 飛彈（编号 7，`0x00446fbc`，104 条指令）

```asm
; @source 0x446fbc（节选）
00446fbc  push ebx / push edi / push ebp
00446fc6  mov  ecx, dword ptr [eax + 0x480d72]   ; '#0240炸得你\n雞飛狗跳∼∼'
...
00446fec  cmp  byte ptr [eax + 0x496b7d], 1
00446ff3  jne  0x447007
00446ffb  push 0x300c0                           ; ★ 人类 mask
00447000  call 0x446ae8
00447005  jmp  0x44700e
00447007  push 0
00447009  call 0x420eee                          ; AI 参数
0044700e  add  esp, 4
00447011  mov  ebx, eax                          ; 选中的格
00447013  test ebx, ebx
00447015  je   0x4470ef                          ; 取消 → 不消耗
0044701b  push 7
0044701d  mov  edi, dword ptr [0x49910c]
00447023  push edi
00447024  call 0x445aa2                          ; ★ after_player_use_tool(cur, 7) → 回池
00447029  add  esp, 8
0044702c  lea  eax, [esp + 4]
00447030  push eax
00447031  lea  eax, [esp + 4]
00447035  push eax
00447036  push ebx
00447037  call 0x40af12                          ; node → (x, y) 屏幕坐标
00447043  push 0x210                             ; ★ mkf 资源号
0044704f  call 0x450441                          ; read_mkf
00447056  add  esp, 0x10
00447065  call 0x41d476                          ; 在 (y,x) 播动画
0044706d  mov  ecx, dword ptr [0x49910c]
00447073  push ecx
00447074  push 0
00447076  push 0x26
00447078  push 0x64                              ; ★ arg1 = 0x64
0044707a  call 0x40ac7b                          ; ★ 范围破坏
00447082  push 0x51 / push 0x90001 / push 0x28 / push 0 / push <res>
0044708e  call 0x45144f
00447096  call 0x456e11                         ; free
0044709f  xor  ebx, ebx
004470a1  cmp  ebx, dword ptr [0x499114]        ; for p in 0..num_players-1
004470a7  jge  0x4470ea
004470ac  test byte ptr [eax + 0x496b7d], 0x40  ; ★ 只处理被标记的玩家
004470b3  je   0x4470e7
004470b5  mov  edx, dword ptr [0x4990e8]        ; price_index
004470bb  mov  eax, edx
004470bd  shl  eax, 2
004470c0  sub  eax, edx        ; 3p
004470c2  add  eax, eax        ; 6p
004470c4  mov  edx, eax
004470c6  shl  eax, 4          ; 96p
004470c9  sub  eax, edx        ; ★ 90 * price_index
004470cb  push eax
004470cc  push current_player
004470d3  push ebx
004470d4  call 0x40df69        ; update_hostility(p, cur, 90*price_index)
004470dc  push 3
004470de  push ebx
004470df  call 0x43ec3f        ; add_player_days_in_hospital(p, 3)
004470e7  inc  ebx
004470e8  jmp  0x4470a1
004470ea  call 0x41d546        ; refresh_screen
```
- **作用目标**：选中的道具/建筑/地格（`mask = 0x300c0`）。
- **边界**：
  - 取消 → 不消耗。
  - **`0x40` 旗标从哪来**：由 `fcn_0040ac7b` 内部对「位于破坏范围内的玩家实体」
    调用 `fcn_0040cd07` 打出（§4.13 / §6.5）。住院函数 `0x43ecad` 会
    `and byte [flags], 0xf` 清掉 bit4..7，所以旗标在住院后即清除（闭环，A）。
  - 目标格不属于任何玩家时，`fcn_0040ac7b` 只做地形破坏，不给任何人挂 `0x40`
    → 后续循环无人住院。
- **C**：`0x40ac7b(0x64, 0x26, 0, cur)` 的**破坏几何范围**无法唯一确定，见 §6.5、§8-②。

### 4.8 遙控骰子（编号 8，`0x004470f8`，126 条指令）

```asm
; @source 0x4470f8（节选）
004470f8  push ebx / push esi / push edi / push ebp
004470fc  sub  esp, 0x10
004470ff  imul eax, dword ptr [0x49910c], 0x68
00447106  cmp  byte ptr [eax + 0x496b7d], 1
0044710d  jne  0x447250                       ; AI 分支
; —— 人类分支 ——
00447113  push 0 / push 0 / push 0x48
00447119  mov  ecx, dword ptr [0x48a05c] / push ecx
00447120  call 0x450441                       ; read_mkf(panel_mkf, 0x48) → 骰子选择图
00447128  mov  dword ptr [0x48c55c], eax
...
0044714e  call 0x44ef41                       ; '#0241要幾點有幾點！\n開∼'
...
004471a2  call 0x4018e7                       ; ★ Wait_0402_Message(0x446774, 0)
004471a7  add  esp, 8
004471aa  mov  ebx, eax                       ; ebx = 选中的骰面 1..6
00447250  push 0 / call 0x420eee              ; AI 分支：参数即点数
0044725c  ...
0044725c  test ebx, ebx
0044725f  je   0x44727b                       ; 0 → 不消耗
00447261  call 0x40dd1f                       ; ★ 走一次普通移动流程
00447266  push 8
00447268  mov  eax, dword ptr [0x49910c] / push eax
0044726d  call 0x445aa2                       ; after_player_use_tool(cur, 8) → 回池
00447272  add  esp, 8
00447275  mov  byte ptr [0x475dd8], bl        ; ★ 强制骰子点数 = 全局 0x475dd8
0044727b  mov  eax, ebx
```
**点数如何生效**（A）：`fcn_00447285` 取出并清零该全局量，
`fcn_00419572` 收到非 0 时把 `ndices` 强行改为 1：
```asm
; @source 0x447285（独立小函数 fcn_00447285）
00447285  xor  eax, eax
00447287  mov  al, byte ptr [0x475dd8]
0044728c  xor  dl, dl
0044728e  mov  byte ptr [0x475dd8], dl
00447294  ret
; @source 0x40d9a4 区域（rich4_player_utils，掷骰点）
0040d9a4  call 0x447285
0040d9a9  push eax
0040d9aa  call 0x419572
0040d9af  add  esp, 4
0040d9b2  mov  dword ptr [0x48baf8], eax
; @source 0x419572
0041957d  movzx esi, byte ptr [esi + 0x496b7a]      ; ndices
00419587  mov  ecx, dword ptr [esp + 0x30]          ; 传入的点数
0041958b  test ecx, ecx
0041958d  jne  0x4195ae
0041958f  xor  ebx, ebx                             ; 点数==0：普通掷骰
00419591  cmp  ebx, esi
00419593  jge  0x4195b7
00419595  call 0x456f2d                             ; rand()
004195a4  idiv ecx (6)
004195a6  inc  edx                                  ; rand()%6+1
004195ae  mov  esi, 1                               ; ★ 强制点数：骰子数改为 1
004195b3  mov  dword ptr [esp + 0x10], ecx          ; 唯一一颗骰子 = 传入值
```
- **作用目标**：自己。
- **边界**：
  - UI 取消 → 返回 0 → 不消耗。
  - UI 的取值来自 `[0x48c598]`；在骰面选择窗口的鼠标移动处理器里它被写成 `face_index + 1`
    （`0x4468ff lea eax,[esi+1]` / `0x446902 mov [0x48c598],eax`），
    面孔循环上界为 6（`0x446847 cmp esi,6`）→ 因此实际取值 **1..6**；
    但 `fcn_00447285` / `fcn_00419572` / 工具函数里**都没有范围检查**
    （C：越界值是否可达，§8-③）。
  - `0x475dd8` 是**全局单值**（不是每人一份）；若同一回合内被多次写入，后者覆盖前者。

### 4.9 機器工人（编号 9，`0x00447295`，80 条指令）

```asm
; @source 0x447295（节选）
00447295  push ebx / push esi / push edi / push ebp
00447299  sub  esp, 8
004472a2  ... mov ecx, dword ptr [eax + 0x480d7a]   ; '#0246兄弟們！\n上工了∼'
004472c9  cmp  byte ptr [eax + 0x496b7d], 1
004472d0  jne  0x4472de
004472d2  push 0x2090006                             ; ★ 人类 mask
004472d7  call 0x446ae8
...
004472e5  test ebx, ebx / je 0x44737d                ; 取消
004472f5  push 9
004472f7  mov  edi, dword ptr [0x49910c] / push edi
004472fe  call 0x445aa2                              ; after_player_use_tool(cur, 9) → 回池
00447304  lea/push ... / call 0x40af12               ; node → (x,y)
0044730d  push 0x229 / call 0x450441                 ; read_mkf(mkf, 0x229)
00447318  call 0x41d476
0044731b  push ebx
0044731c  call 0x40b110                              ; ★ 升级：返回 1 成功 / 0x81 到顶
00447321  add  esp, 4
00447324  mov  dword ptr [esp], eax
00447327  push 0x5b / push 0x2c0001 / push 0x28 / push 0 / push esi
00447333  call 0x45144f
0044733b  test byte ptr [esp], 0x80
0044733f  je   0x447378
00447341  call 0x40b0cd                              ; ★ 到顶：播 mkf 0x20b
00447346  call 0x41d546
```
`fcn_0040b110(node)` 行为（A，`0x40b110`）：
- `0x7d0 < node < 0xfa0`（住宅/商業用地）：`type == 0 && level < 5` → `level++`；
  `type == 1 && level < 1` → `level++`；`level` 达到 5 时返回 `eax | 0x80`。
- `0xfa0 ≤ node < 0x1770`（设施）：`level == 0` → 随机给类型 1..4 后 `level = 1`；
  否则若 `level < 表[0x474940 + type]` → `level++`（表实测：type1→5, type2→5, type3→1, type4→5）。
- 返回值 `0x81` = 「升到上限」。
- **边界**：对 `type == 1` 的地（商業用地）本函数只允许 0→1（原文 `cmp cl,[ebx+0x1a]; jbe`），
  与住宅的「< 5」不同；这是 exe 行为，**不建议在复刻里"修正"**。

### 4.10 時光機（编号 10，`0x00447387`，53 条指令）

```asm
; @source 0x447387
00447387  push ebx / push esi
...
0044738a  ... mov ecx, dword ptr [eax + 0x480d7e]   ; '#0242如果再回到\n從前∼'
004473ae  call 0x44ef41
004473b2  call 0x448544                              ; ★ restore_last_state → eax
004473b7  mov  ebx, eax
004473b9  test eax, eax
004473bb  je   0x447423                              ; 无快照 → 不消耗，返回 0
004473bd  mov  ah, byte ptr [0x46cb06]               ; BGM/计时状态（高位/低位）
004473c3  test ah, ah / je 0x4473fe
004473c7  mov  dl, ah / inc dl / mov [0x46cb06], dl
004473d3  and  al, 0xf / ... / sar eax, 4
004473e5  jle  0x4473fe
004473e7  xor  dh, dh / mov [0x46cb06], dh
004473ef  call 0x454acb / push 0 / call 0x454d91     ; 重置音乐
004473fe  push 0xa
00447400  mov  esi, dword ptr [0x49910c] / push esi
00447407  call 0x445aa2                              ; after_player_use_tool(cur, 10) → 回池
0044740f  push 0 / call 0x40a4e1
00447419  push 1 / call 0x41906a
00447423  mov  eax, ebx
```
- **快照机制（A）**：`_rich4_store_current_state` @ `0x44808a` 把整份可回滚状态
  按 **每玩家 10008 字节（0x2718）** 存到 `0x48cb80 + player*0x2718`：
  ```asm
  ; @source 0x44808a
  00448092  cmp  edx, 4                ; 只对 0..3
  00448095  jge  0x448541
  004480a0  test byte ptr [eax + 0x496b7d], 1   ; ★ 只对「人类」玩家存快照
  004480a7  je   0x448541
  004480ce  mov  dword ptr [eax + 0x48cb80], 1  ; 有效标记
  004480e4  push 0x1a0 / push 0x496b68          ; +0x008 : 玩家状态 416 B
  0044813a  push 0x450 / push 0x496d08          ; +0x1f8 : objects_info 1104 B
  00448178  push 0x3c  / push 0x499120          ; +0x648 : 卡   60 B
  004481b3  push 0x3c  / push 0x49915c          ; +0x684 : 道具 60 B
  ```
  索引算法实测为 `10008 * player`（`0x48cb80 + n`）。
- **入口调用点（A）**：`0x40dd53`（每次掷骰移动前）→ 也就是
  **快照 = 本次移动开始前**；`0x40fc00` 区域（传送等）也会存。
- **边界**：
  - 没有有效快照 → 返回 0 → **道具不消耗**（但函数已播过台词）。
  - **AI 玩家没有快照**（存快照被 `flags & 1` 拦掉）→ AI 用時光機恒定失败。

### 4.11 傳送機（编号 11，`0x00447428`，409 条指令）

```asm
; @source 0x447428（节选）
00447428  push ebx / push esi / push edi / push ebp
0044742c  sub  esp, 0x28
0044742f  xor  esi, esi                       ; esi = 「是否已生效」标志
00447448  mov  ecx, dword ptr [eax + 0x480d82] ; '#0243瞬間移動！！'
00447451  call 0x44ef41
00447460  cmp  byte ptr [eax + 0x496b7d], 1
00447467  jne  0x447478
00447469  push 0x1200036                      ; ★ 人类 mask
0044746e  call 0x446ae8
00447478  mov  cl, byte ptr [0x49910c]
0044747e  mov  eax, 1
00447483  shl  eax, cl
00447485  or   ah, 0x80                       ; AI：自选（自己的位 | 0x8000）
00447488  mov  dword ptr [esp + 0x1c], eax    ; v
0044748c  mov  dh, byte ptr [esp + 0x1d]      ; 高位字节
00447490  test dh, 0x80 / je 0x4474d1
00447495  test dh, 0x3f / je 0x4474d1
0044749a  mov  ebx, dword ptr [esp + 0x1c]
0044749e  and  ebx, 0x3f00
004474a4  sar  ebx, 8                          ; idx = bits 8..13
004474a7  lea  edx, [ebx - 1]
004474aa  mov  eax, edx
004474ac  shl  eax, 2
004474af  sub  eax, edx
004474b1  shl  eax, 3                            ; (idx-1) * 24
004474b4  mov  bh, byte ptr [eax + 0x496d0d]     ; objects_info[idx-1].+5 = owner
004474ba  test bh, bh / je 0x4474d1
004474be  xor  ecx, ecx / mov cl, bh / dec ecx
004474c3  mov  eax, 1 / shl eax, cl / or ah, 0x80
004474cd  mov  dword ptr [esp + 0x1c], eax     ; 换成 owner
; —— 三种目标类型 ——
004474dd  cmp  ebp, 0x7d0 / jle 0x44757c
004474e9  cmp  ebp, 0xfa0 / jge 0x44757c
004474f5  push 0x2090802                       ; ★ 地产分支：再选一块地
004474fa  call 0x446ae8
0044750c  lea  eax, [ebp - 0x7d0]
00447512  imul eax, eax, 0x34                  ; 源 = land_info_ptr + (v-0x7d0)*0x34
00447526  add  edx, ebx                        ; 目标同型
00447528  mov  bl, byte ptr [eax + 0x19]       ; owner
0044752b  mov  byte ptr [edx + 0x19], bl       ; 目标.owner = 源.owner
0044752e  mov  byte ptr [eax + 0x19], 0        ; 源清零
00447532  mov  bl, byte ptr [eax + 0x1a]       ; level
00447535  mov  byte ptr [edx + 0x1a], bl
00447538  mov  byte ptr [eax + 0x1a], 0
0044753c  mov  bl, byte ptr [eax + 0x18]       ; type
0044753f  mov  byte ptr [edx + 0x18], bl
00447542  mov  byte ptr [eax + 0x18], 0
00447546  mov  ecx, dword ptr [eax + 0x30]     ; ★ +0x30
00447549  mov  dword ptr [edx + 0x30], ecx
0044754c  mov  dword ptr [eax + 0x30], 0
00447553  mov  dword ptr [eax + 0x2c], 0       ; ★ +0x2c 也被清（既有文档未记录）
0044755a  push 0
0044755c  call 0x40a4e1                        ; 重绘该格
00447564  push 1 / push 0 / push 0 / call 0x41d476
00447572  mov  esi, 1                          ; 标记已生效
00447577  jmp  0x4479b7                        ; → after_player_use_tool(cur, 11)
; —— 设施分支 0xfa0..0x1770 ——
00447598  push 0x2090804
004475c2  mov  esi, dword ptr [0x498e88]        ; facility_info_ptr
004475d8  mov  bl, byte ptr [esi + eax + 0x19]  ; owner
...
004475ff  mov  ecx, dword ptr [esi + eax + 0x34]
00447603  mov  dword ptr [edx + esi + 0x34], ecx
00447607  mov  dword ptr [esi + eax + 0x34], 0
0044760f  mov  dword ptr [esi + eax + 0x30], 0  ; ★ 详见 §7.1
; —— 实体传送分支 0x44761c / 对象搬移分支 0x4478cb ——
004479b3  test esi, esi / je 0x4479c8
004479b7  push 0xb
004479b9  push current_player
004479c0  call 0x445aa2                        ; ★ 只有 esi != 0 才消耗
004479c8  mov  eax, esi
```
- **作用目标**：地（`0x7d0..0xfa0`）/ 设施（`0xfa0..0x1770`）/ 实体（bit15 + bits8..13）；
  第三次选择用 mask `0x2090001`。
- **合法性**：`v == 0` → 直接跳到 `0x4479c8` 返回 0（不消耗）；
  三个子分支都失败时 `esi` 仍为 0 → **不消耗**。
- **边界**：
  - **第二次选择没有类型校验**（`0x44750c` 之后直接 `imul edx, 0x34`）。
    若玩家点到非地产，`edx` 会变成任意下标 → 越界读写。UI mask 是否已限制住**未决**（§8-④）。
  - 源头的 `+0x30`（地契/到期日）被**迁移**到目标，源置 0；地产分支还额外清 `+0x2c`。
  - **设施分支多清了 `+0x30`，地产分支多清了 `+0x2c`** ——两个结构体的尾部布局不同（A）。

### 4.12 工程車（编号 12，`0x004479d2`，72 条指令）

```asm
; @source 0x4479d2
004479d2  push ebx / push edi / push ebp
004479d5  imul eax, dword ptr [0x49910c], 0x68
004479dc  mov  dl, byte ptr [eax + 0x496b79]
004479df  and  dl, 3
004479e2  cmp  dl, 3
004479e5  jne  0x4479f1
004479e7  xor  edx, edx
004479e9  jmp  0x447ac8               ; ★ 已是工程車(0x1f & 3 == 3) → 返回 0，不消耗
004479f1  cmp  byte ptr [eax + 0x496b79], 1
004479f8  jne  0x447a14
004479fa  ... inc  byte ptr [eax + 0x499160]   ; 機車退回背包
00447a14  mov  ecx, dword ptr [0x49910c]
00447a1a  imul eax, ecx, 0x68
00447a1d  cmp  byte ptr [eax + 0x496b79], 2
00447a24  jne  0x447a3a
00447a34  inc  byte ptr [eax + 0x499161]          ; 汽車退回背包
00447a3a  mov  ebx, dword ptr [0x49910c]
00447a40  imul eax, ebx, 0x68
00447a43  mov  dl, byte ptr [eax + 0x496b79]
00447a49  mov  byte ptr [eax + 0x496bcc], dl      ; ★ 备份原 traffic   → +0x64
00447a4f  mov  dl, byte ptr [eax + 0x496b7a]
00447a55  mov  byte ptr [eax + 0x496bcd], dl      ; ★ 备份原 ndices   → +0x65
00447a5b  mov  byte ptr [eax + 0x496b79], 0x1f    ; traffic = 0x1f
00447a62  mov  byte ptr [eax + 0x496b7a], 1       ; ndices = 1
00447a6a  call 0x40b93b                           ; update_player_sprite
00447a97  mov  ebp, dword ptr [eax + 0x480d86]    ; '#0244拆除大隊來了！'
00447aa1  call 0x44ef41
00447abd  mov  edx, 1
00447ac2  dec  byte ptr [eax + 0x499167]          ; ★ 直接扣（下标 11），不回池
00447ac8  mov  eax, edx
```
- **`traffic = 0x1f` 的语义**：`and 3 == 3` 是全局唯一的识别方式（`0x4479e2`）。
  它**走了什么特殊通道**（能否穿过路障、能否拆建筑等）**未决**（§8-⑤）——
  本次没有在移动/触发代码里找到 `== 0x1f` 或 `& 3 == 3` 的特判。
  已确认的只有：`fcn_0040cd07`（车辆报废）对 `& 3 == 3` **不做任何退回**（§4.13）。
- **边界（C）**：备份值 `+0x64/+0x65` 的**回滚点**未完全追查；
  我只确认了写入点（`0x447a49`/`0x447a55`），未在本次复核范围内找到唯一的消费点。

### 4.13 核子飛彈（编号 13，`0x00447ace`，97 条指令）

与飛彈的逐项差异（全部 A）：

| 项 | 飛彈 | 核子飛彈 |
|---|---|---|
| 台词偏移 | `+0x18` | `+0x30`（`#0245各∼位∼觀∼眾\n．．．．。`） |
| 人类 mask | `0x300c0` | `0x400c0` |
| 消耗调用 | `after_player_use_tool(cur, 7)` | `after_player_use_tool(cur, 13)` |
| 电影资源 | `mkf 0x210` | `mkf 0x212` |
| 播放参数 | `mkf 0x210`→`fcn_0045144f(res,0,0x28,0x90001,0x51)` | `fcn_0045144f(res,0,0x28,0x80090001,0x53)` |
| 破坏调用 | `fcn_0040ac7b(0x64, 0x26, 0, cur)` | **`fcn_0040ac7b(-1, 0x26, 1, -1)`** |
| 玩家循环 | 相同（`flags & 0x40` → `hostility += 90*price_index` + 住院 3 天） | 相同 |

```asm
; @source 0x447b88（核子飛彈的破坏调用）
00447b85  push ecx          ; current_player
00447b86  push 1            ; ★ mode = 1（清空归属）
00447b88  push 0x26         ; flags
00447b8a  push -1           ; ★ arg1 = -1 → 全地图
00447b8c  call 0x40ac7b
```

---

## 五、研究研发顺序与「道具编号 = 项目 + 8」的完整验证

### 5.1 每回合的研究推进循环 @ `VA 0x0041cdb0`（在 `fcn_0041c84f` 内）

```asm
; @source 0x41cd8c
0041cd8c  mov  esi, 1
0041cd91  mov  ebx, dword ptr [0x498e88]      ; facility_info_ptr
0041cd97  add  ebx, 0x38                      ; 设施步长 0x38
0041cd9a  cmp  esi, dword ptr [0x498e8c]      ; num_facilities
0041cda0  jg   0x41cf5d
0041cda6  cmp  byte ptr [ebx + 0x18], 4       ; ★ type == 4（研究所）
0041cdaa  jne  0x41ce33
0041cdb0  mov  cl, byte ptr [ebx + 0x1e]      ; ★ 倒计时
0041cdb3  test cl, cl
0041cdb5  je   0x41ce33
0041cdbb  xor  edx, edx
0041cdbd  mov  dl, byte ptr [ebx + 0x19]      ; owner+1
0041cdc0  mov  eax, dword ptr [0x49910c]
0041cdc5  inc  eax
0041cdc6  cmp  edx, eax
0041cdc8  jne  0x41ce33                       ; 只处理「本人拥有」的研究所
0041cdca  mov  al, byte ptr [ebx + 0x1d]      ; ★ 项目
0041cdcd  cmp  al, byte ptr [ebx + 0x1a]      ; ★ 与等级比较
0041cdd0  ja   0x41ce2f                       ; 项目 > 等级 → 中止
0041cdd2  mov  al, cl
0041cdd4  dec  al
0041cdd6  mov  byte ptr [ebx + 0x1e], al      ; ★ 倒计时 −1（每回合一次）
0041cdd9  jne  0x41ce33
0041cddb  push 1 / call 0x41906a
0041cde5  xor  eax, eax
0041cde7  mov  al, byte ptr [ebx + 0x1d]
0041cdea  mov  ebp, dword ptr [eax*8 + 0x47ff1a]  ; ★ tool_table[7+项目].name
0041cdf1  push ebp / push 0x463b68                ; '%s開發完成！'
0041cdfc  call 0x457110                           ; sprintf
0041ce04  push 0x5dc / push <buf> / call 0x440cac ; 显示
0041ce16  xor  eax, eax
0041ce18  mov  al, byte ptr [ebx + 0x1d]
0041ce1b  add  eax, 8                             ; ★★ 道具编号 = 项目 + 8
0041ce1e  push eax
0041ce1f  mov  eax, dword ptr [0x49910c] / push eax
0041ce25  call 0x445a4d                           ; receive_tool(current_player, 项目+8)
0041ce2d  jmp  0x41ce33
0041ce2f  mov  byte ptr [ebx + 0x1e], 0          ; 项目越权 → 清倒计时
```

**设施结构（研究所）实测字段**：

| 偏移 | 绝对地址（第 1 座） | 类型 | 含义 | 证据 |
|---|---|---|---|---|
| `+0x18` | `0x498ea0` | `uint8` | 类型；**4 = 研究所** | `0x41cda6`、`0x41b0f6` |
| `+0x19` | `0x498ea1` | `uint8` | 拥有者 + 1 | `0x41cdbd` |
| `+0x1a` | `0x498ea2` | `uint8` | **等级**（= 已解锁项目数） | `0x41cdcd` |
| `+0x1c` | `0x498ea4` | `uint8` | 低 4 位非 0 时禁止进入研究所 | `0x41b102` |
| `+0x1d` | `0x498ea5` | `uint8` | **研发项目**（1 起） | `0x41cde7` |
| `+0x1e` | `0x498ea6` | `uint8` | **剩余回合数** | `0x41cdb0` |
| `+0x30`/`+0x34` | | `uint32` | 地契/到期日（傳送機要迁移的两个字段） | `0x447603/0x44760f` |

（`facility_info_ptr = 0x498e88`，`num_facilities = 0x498e8c`，步长 `0x38`，**下标从 1 开始**。）

### 5.2 研发项目的**选定**（`VA 0x0044101d`，研究所入口）

```asm
; @source 0x4411e5
004411e5  jmp  0x4411ed
004411e7  xor  ebx, ebx                          ; —— AI 分支 ——
004411e9  mov  bl, byte ptr [edi + 0x1a]         ; bl = 等级
004411ec  dec  ebx                               ; ebx = 等级 - 1
004411ed  cmp  ebx, -1
004411f0  je   0x43f212                          ; 等级 0 → 不能研发
004411f6  inc  bl
004411f8  mov  byte ptr [edi + 0x1d], bl         ; ★ 项目 = 等级
004411fb  mov  byte ptr [edi + 0x1e], 5          ; ★ 倒计时 = 5 回合
004411ff  jmp  0x43f212
```
人类分支（`0x44102f` 起，`flags == 1`）走 5 行菜单：
```asm
; @source 0x4410c3
004410c3  xor  eax, eax
004410c5  mov  al, byte ptr [edi + 0x1a]         ; 等级
004410c8  cmp  ebx, eax
004410ca  jl   0x441093                          ; 行号 >= 等级 → 不画高亮（不可选）
...
004411b0  mov  al, byte ptr [edi + 0x1a]
004411b3  push eax                               ; 参数 = 等级
004411b4  push 0x4402d7
004411b9  call 0x4018e7                          ; Wait_0402_Message(菜单处理器, 等级)
004411be  add  esp, 8
004411c1  mov  ebx, eax                          ; ebx = 选中的行号 0..4（-1 = 取消）
```
菜单处理器 `fcn_004402d7` @ `0x004402d7`：
```asm
; @source 0x44033b（初始化消息 0x401）
0044033b  mov  dword ptr [0x48c534], edx         ; ★ 上限 = 传入的等级
00440341  mov  dword ptr [0x48c530], 0xffffffff  ; 当前高亮 = 无
; @source 0x4403d6（鼠标移动 0x200）
004403d6  lea  edx, [ebx - 0x23]                 ; 行高 0x4c，第一行 y=0x23
004403d9  mov  ebx, 0x4c
004403e3  idiv ebx
004403e5  mov  esi, eax                          ; 行号 0..4
00440468  mov  ebp, dword ptr [eax*8 + 0x47ff22] ; ★ 行号 i → tool_table[8+i].name
; @source 0x4405d0（左键按下）
004405d0  mov  edi, dword ptr [0x48c530]
004405d6  cmp  edi, -1 / je  <退出>
004405df  cmp  edi, dword ptr [0x48c534]
004405e5  jge  <退出>                            ; ★ 行号 >= 等级 → 拒绝
; @source 0x44062b（左键抬起）→ 0x401966 把选中值交回
```
- 回传值 = 行号 `0..4`（`0x48c530`）；调用方 `inc bl` → **项目 = 行号 + 1**，
  倒计时 = **5**（`0x4411fb`）。

### 5.3 结论：研发顺序与编号映射（全部 A）

| 项目 `+0x1d` | 名称（`tool_table[7+项目].name`） | 发放的道具 `项目+8` | 名称 |
|---|---|---|---|
| 1 | 機器工人 | 9 | 機器工人 ✓ |
| 2 | 時光機 | 10 | 時光機 ✓ |
| 3 | 傳送機 | 11 | 傳送機 ✓ |
| 4 | 工程車 | 12 | 工程車 ✓ |
| 5 | 核子飛彈 | 13 | 核子飛彈 ✓ |

- 研究所**等级 L** 允许研发项目 `1..L`（菜单 `cmp 行号, 等级`；AI 取 `项目 = 等级`）。
- 每项需 **5 回合**（`0x4411fb` / `0x4411f6`），倒计时在 `fcn_0041c84f` 里每回合 −1。
- **顺序完全由 `tool_table` 的排列决定**：名称查表用的是 `0x47ff1a + 项目*8`
  = `tool_table[7 + 项目]`，即 `tool_table` 第 8..12 项（0 基）依次为
  機器工人 / 時光機 / 傳送機 / 工程車 / 核子飛彈 —— 与 §1.2 的表一致。
- **额外发现（A）**：新游戏时**每个玩家**都会白得一个 **機器工人（道具 9）**：
  ```asm
  ; @source 0x407281（新游戏初始化，对每个 player < num_players）
  00407281  push 1 / push ebx / call 0x445a4d   ; 道具 1 機器娃娃
  0040728c  push 2 / push ebx / call 0x445a4d   ; 道具 2 路障
  00407297  push 3 / push ebx / call 0x445a4d   ; 道具 3 地雷
  004072a2  push 4 / push ebx / call 0x445a4d   ; 道具 4 定時炸彈
  004072ad  push 8 / push ebx / call 0x445a4d   ; 道具 8 遙控骰子
  004072b8  push 9 / push ebx / call 0x445a4d   ; ★ 道具 9 機器工人
  ```
  因此「道具 9..13 只能靠研究所」对 **10..13** 成立，对 **9** 不成立。

---

## 六、放置类道具的持久化（存档格式的关键）

### 6.1 全局对象表 `_rich4_objects_info` @ `VA 0x00496d08`（A）

- **46 项 × 24 字节 = 1104 字节（0x450）**。项数 46 由三处独立证据交叉确认：
  1. 存档/读档：`push 0x2e; push 0x18; push 0x496d08`（读 `0x402bca`、写 `0x40309d`）→ 46 × 24；
  2. 更新循环上界 `cmp ebx, 0x2e`（`0x408f78` 循环）；
  3. 槽位分配上界 `0x2e`（`0x40e076`，§6.1.1）。
- 结构（`type` 与 `+2/+4/+5` 由 `place_object` 写、`remove_object` 读，A；
  `+1` 由 `fcn_00407a8c` 写，A；其余由 `rich4.asm` 的绘制循环使用，B）：

| 偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| `+0x00` | `uint8` | **对象类型** | `0x496d08`，`0x40e14d` 分派 |
| `+0x01` | `uint8` | `sub_00407a8c` 算出的**朝向**（方向码，低字节，用途 C） | `0x40e11d` |
| `+0x02` | `uint16` | **所在格编号**（0 = 未放置） | `0x40e0a5` |
| `+0x04` | `uint8` | 放置参数 3（0x40dd1f 参数 / 神明倒计时） | `0x40e0b0` |
| `+0x05` | `uint8` | **拥有者玩家下标 + 1**（0 = 无） | `0x40e0ba` |
| `+0x06` | `uint8` | 存在/动画计时（`0x408f78` 起更新） | `0x496d0e` |
| `+0x07` | `uint8` | **朝向的副本**（`0x40fafd` 把 `+0x01` 抄一份，给动画用） | `@source 0x0040fba3` `mov dl, byte [obj*24 + 0x496d09]` → `0x0040fbaa` `mov byte [obj*24 + 0x496d0f], dl`；通道 2 证据 `tests/test_object_float_move.py`（13/13）。★ 2026-09-18 订正：本行原写「未定位」|
| `+0x08` | `float` | 屏幕 x | `0x496d10` |
| `+0x0c` | `float` | 屏幕 y | `0x496d14` |
| `+0x10` | `float` | x 速度 | `0x496d18` |
| `+0x14` | `float` | y 速度 | `0x496d1c` |

### 6.1.0 ★ 物件**起手移动** `0x0040fafd(objIdx, fromNode, toNode)`（A，2026-09-18 补）

```asm
0040fb03  edi = arg1 = objIdx ; if (edi == 0) return      ; 0 = 空槽，直接走
0040fb20  edi -= 1                                        ; 0 基下标
0040fb21  esi = node[from].x ; ebx = node[from].y         ; int16（+0x00/+0x02）
0040fb35  edx = node[to].x   ; ecx = node[to].y
0040fb3e  dx = from.x − to.x   → fild / fmul qword [0x46352c]=**0.5**
0040fb55  fstp [obj*24 + 0x496d18]                        ; ★ +0x10 = Δx × 0.5（x 速度）
0040fb6c  fstp [obj*24 + 0x496d1c]                        ; ★ +0x14 = Δy × 0.5（y 速度）
0040fb80  fstp [obj*24 + 0x496d10]                        ; ★ +0x08 = from.x + 速度x
0040fb94  fstp [obj*24 + 0x496d14]                        ; ★ +0x0c = from.y + 速度y
0040fb9b  byte [obj*24 + 0x496d0e] = 0xff                  ; ★ +0x06 = 0xFF（起手计时）
0040fbaa  byte [obj*24 + 0x496d0f] = byte [obj*24 + 0x496d09]   ; ★ +0x07 ← +0x01
```

★ 三条值得记的：

1. **速度 = Δ × 0.5**（常量是 **qword double 0.5**，在 `0x46352c`）—— 即「两拍走完一格」，
   起手时位置已经被推进了**半格**（`+0x08 = from.x + 速度x`）；
2. 落点是 **float32**（`fstp dword`）——复刻算这几位要注意单精度舍入
   （测试里按 IEEE-754 单精度逐步复算）；
3. `+0x07` 是**朝向副本**（见上表订正）。

### 6.1.1 槽位分配（`rich4_place_object` @ `0x0040e033`）（A）

```asm
0040e033  push ebx / push esi / push edi
0040e036  mov  edi, dword ptr [esp + 0x10]     ; arg1 = 对象类型
0040e03a  mov  esi, dword ptr [esp + 0x14]     ; arg2 = 格编号
0040e03e  lea  eax, [edi - 0xf]
0040e041  cmp  eax, 3
0040e044  ja   0x40e07d
0040e046  jmp  dword ptr [eax*4 + 0x40e023]    ; 类型 0x0f..0x12 的槽段
0040e04d  mov  ebx, 0xe  / mov ecx, 0x10       ; 0x0f → 槽 [0x0e,0x10) = 2 个
0040e059  mov  ebx, 0x10 / mov ecx, 0x1a       ; 0x10 → 槽 [0x10,0x1a) = 10 个 ← 路障
0040e065  mov  ebx, 0x1a / mov ecx, 0x24       ; 0x11 → 槽 [0x1a,0x24) = 10 个 ← 地雷
0040e071  mov  ebx, 0x24 / mov ecx, 0x2e       ; 0x12 → 槽 [0x24,0x2e) = 10 个 ← 定時炸彈
0040e07d  lea  ebx, [edi - 1] / mov ecx, edi   ; 其它类型 → 唯一槽 [类型-1, 类型)
0040e082  cmp  ebx, ecx
0040e084  jge  0x40e13f                        ; ★ 槽用尽 → 不写入，返回 ebx+1
0040e08a  mov  eax, ebx
0040e08c  shl  eax, 2
0040e08f  sub  eax, ebx
0040e091  shl  eax, 3                          ; ★ 步长 = 24
0040e097  cmp  word ptr [eax + 0x496d0a], 0
0040e09f  jne  0x40e146                        ; 已占用 → 下一槽
0040e0a5  mov  word ptr [eax + 0x496d0a], si   ; node
0040e0ac  mov  cl, byte ptr [esp + 0x18]
0040e0b0  mov  byte ptr [eax + 0x496d0c], cl   ; +4
0040e0b6  mov  cl, byte ptr [esp + 0x1c]
0040e0ba  mov  byte ptr [eax + 0x496d0d], cl   ; +5 = owner
0040e0c0  mov  ecx, dword ptr [esp + 0x1c]
0040e0c4  test ecx, ecx / je 0x40e0dc
0040e0c8  cmp  edi, 0xf / jne 0x40e0dc
0040e0cd  push edx / push 0 / lea eax,[ecx-1] / push eax
0040e0d4  call 0x40ead7                        ; 类型 0x0f 且 owner != 0 → attach_god
0040e0dc  test esi, esi / je 0x40e13f          ; 格号 0 → 不做反向登记
0040e0e0  xor  edx, edx                        ; 依次取 node[esi].+0x18[0..3] 的第一个非 0
0040e0ea  mov  eax, esi
0040e0ec  shl  eax, 2 / lea ecx,[esi+eax] / shl ecx,3   ; esi*40（节点步长 0x28）
0040e0f5  mov  eax, dword ptr [0x498e80]       ; map_node_ptr
0040e0fa  add  eax, ecx
0040e0fc  mov  ecx, edx
0040e0fe  mov  ax, word ptr [eax + ecx*2 + 0x18]
0040e103  and  eax, 0xffff
0040e108  je   0x40e0e4                        ; 为 0 → 下一个
0040e10a  push esi / push eax / call 0x407a8c  ; ★ 两节点间的**朝向**（不是距离）
0040e111  mov  edx, eax / add esp, 8
0040e116  mov  eax, ebx                         ; eax = 槽号
0040e118  shl  eax, 2
0040e11b  sub  eax, ebx
0040e11d  mov  byte ptr [eax*8 + 0x496d09], dl  ; objects_info[slot].+1 = 方向码
0040e124  ...
0040e136  lea  edx, [ebx + 1]
0040e139  shl  edx, 0x10
0040e13c  or   dword ptr [eax + 0x24], edx     ; ★ 节点 +0x26 字节 = 槽号+1（见 §6.3）
0040e13f  lea  eax, [ebx + 1]                  ; 返回值 = 槽号 + 1
```
**同时存在上限（A）**：路障 / 地雷 / 定時炸彈**各 10 个**；
类型 `0x0f`（神明）2 个；其它类型（如 `0x0d` 道具格）各 1 个。
46 = 14（类型 1..0x0e 各 1）+ 2 + 10 + 10 + 10 ✓ 完全吻合。

### 6.1.2 ★★ 槽号 → 类别是**固定表** `0x47ed3c`（46 字节，A，2026 本轮通道 2 补）

装载地图时 `memset(0x496d08, 0, 0x450)` 之后，紧接着一段循环把**一张 46 字节的常量表**
逐字节写进 `objects_info[i].+0`（`i = 0..45`，0 基）：

```asm
; @source 0x407d3a（memset）+ 0x407d4e..0x407d68（填类别）
00407d3a  push 0x450 / push 0 / push 0x496d08 / call 0x456f60     ; memset
00407d4e  xor  ebx, ebx
00407d50  mov  eax, ebx
00407d52  shl  eax, 2
00407d55  sub  eax, ebx                          ; eax = 3*i
00407d57  mov  dl, byte ptr [ebx + 0x47ed3c]     ; ★ 类别表[0 基下标]
00407d5d  mov  byte ptr [eax*8 + 0x496d08], dl   ; objects_info[i].+0 = 类别
00407d64  inc  ebx
00407d65  cmp  ebx, 0x2e                         ; 46 项
00407d68  jl   0x407d50
```

表内容（实测 46 字节，`@source 0x47ed3c`）：

```
槽  1..14 → 类别  1..14      （每类恰好 1 槽）
槽 15..16 → 类别 15           （2 个；类别 15 的处理函数 `0x41c164` = 不处理）
槽 17..26 → 类别 16 路障       （10 个）
槽 27..36 → 类别 17 地雷       （10 个）
槽 37..46 → 类别 18 定時炸彈    （10 个）
```

★★ **这张表是「寶箱处理函数写死 `remove_object(0xe)`」的正当性来源**：
类别 14 只可能在槽 14，故 `0x41bb31 push 0xe` 不是笔误；同族的类别 11 也一样
（`0x41b837 push 0xb`）、类别 13 也一样（`0x41b936`/`0x41b9b6 push 0xd`）。
反过来，路障/地雷/定時炸彈**有 10 个槽**，处理函数必须用分派器帧里的真实槽号
（`[esp+0xa4]`，§6.3）。

> ⚠️ 复刻侧的口径：物件类别**由槽位决定、且此后永不改变**（`place_object` 也从不写 `+0`）。
> 若把类别存成自由字段，就会出现「槽 20 里放着一个寶箱」这种原版不可能有的局面，
> 于是「寶箱永远落在槽 14」这条不变量失效。

### 6.2 销毁 `rich4_remove_object(objidx_plus_1)` @ `0x0040e14d`（A）

```asm
0040e14d  push ebx / push esi
0040e14f  mov  edx, dword ptr [esp + 0xc]
0040e153  test edx, edx / je 0x40e29f          ; 0 → 直接返回
0040e15b  dec  edx
0040e15c  mov  eax, edx *3 *8                  ; 步长 24
0040e166  mov  cl, byte ptr [eax + 0x496d08]   ; type
0040e16c  cmp  cl, 0x11 / jb 0x40e17a
0040e171  jbe  0x40e18a                        ; type == 0x11 → 地雷
0040e173  cmp  cl, 0x12 / je 0x40e195          ; type == 0x12 → 定時炸彈
0040e178  jmp  0x40e1ba                        ; 其它（含神明）
0040e17a  cmp  cl, 0x10 / jne 0x40e1ba         ; type == 0x10 → 路障
0040e17f  inc  byte ptr [0x497321]             ; ★ remain_tool_amount[1] += 1（路障回库存）
0040e18a  inc  byte ptr [0x497322]             ; ★ remain_tool_amount[2] += 1（地雷）
0040e195  inc  byte ptr [0x497323]             ; ★ remain_tool_amount[3] += 1（定時炸彈）
0040e195  mov  bh, byte ptr [eax + 0x496d0d]   ; owner
0040e19e  test bh, bh / je 0x40e21a
0040e1a5  dec  eax / imul eax, 0x68
0040e1ab  mov  byte ptr [eax + 0x496ba8], 0    ; ★ players_state[owner-1].+0x40 = 0
0040e1ba  ... 其它类型：owner 的 +0x3f=0，并按 3 张表扣 +0x44/+0x46/+0x48
0040e21a  ...
0040e21a  cmp  byte ptr [eax + 0x496d0d], 0
0040e222  jne  0x40e248
0040e224  mov  cx, word ptr [eax + 0x496d0a]   ; node
0040e230  mov  byte ptr [ecx + eax*8 + 0x26], 0 ; ★ 清节点反向索引
0040e248  ...  mov  word ptr [+2], 0
0040e25a  mov  byte ptr [+4], 0
0040e263  mov  byte ptr [+5], 0                ; 清空槽
0040e230  cmp  edx, 0xc / jge 0x40e29f
0040e232  test dl, 1 / je 0x40e284
0040e284  ...  push 0 / push 0 / push ecx / call 0x40aa6c   ; find_random_unoccupied_distant_node
0040e29f  pop esi / pop ebx / ret              ; ★ 函数出口（早期误读成"补放"调用点）
```
> ★ **本节曾写过一条错误结论，已修正**。早期版本写的是：
> 「销毁类型 `0x10/0x11/0x12` 会**自动在地图远处随机补放一个同类对象**（槽号 ≥ 0x0c 时跳过），
> 所以路障/地雷/定時炸彈是**自维持**的」。**这是误读控制流造成的。**
>
> 逐指令看 `0x0040e275`–`0x0040e2a1`：
> ```asm
> 0040e275  cmp   edx, 0xc
> 0040e278  jge   0x40e29f          ; ★ 0x40e29f 是**函数出口**，不是"补放"分支
> 0040e27a  test  dl, 1
> 0040e27d  je    0x40e284
> 0040e27f  lea   ebx, [edx - 1]    ; 奇数 → 槽号-1
> 0040e282  jmp   0x40e287
> 0040e284  lea   ebx, [edx + 1]    ; 偶数 → 槽号+1   ← 配对槽（神明"搭档"）
> 0040e287  push  0
> 0040e289  push  0
> 0040e28b  push  ecx
> 0040e28c  call  0x40aa6c          ; find_random_unoccupied_distant_node
> 0040e294  push  eax
> 0040e295  inc   ebx
> 0040e296  push  ebx
> 0040e297  call  0x40e033          ; 在**配对槽**里放一个对象
> 0040e29c  add   esp, 0x10
> 0040e29f  pop   esi               ; ★ 函数出口
> 0040e2a0  pop   ebx
> 0040e2a1  ret
> ```
> **正确结论**：
> 1. 补放**只在 `槽号 < 0x0c` 时发生**，而且放的是 `槽号±1` 的**配对槽** ——
>    这是**神明与它的"搭档"实体**的配对逻辑（见 §6.4 槽位分区：`< 0x0c` 是神明槽）。
> 2. **路障(2)/地雷(3)/定時炸彈(4) 的槽号 ≥ 0x0c，走的是 `jge 0x40e29f` 直接返回，
>    不会有任何"自动补放"**。它们就是被消耗掉，不复生。
> 3. 因此**不存在**"自维持"模型。复刻时**不要**实现自动补放。

### 6.3 触发判定所在函数与分派表

**触发点：`_rich4_player_move_one_step_done` @ `VA 0x0041b42d`**（每回合移动结算）。

```asm
; @source 0x41b47f（读当前格的编码字；esi = 当前格编号）
0041b47f  mov  eax, esi
0041b481  shl  eax, 2
0041b484  add  eax, esi
0041b486  shl  eax, 3                            ; esi * 40（节点步长 0x28）
0041b489  mov  ecx, dword ptr [0x498e80]         ; map_node_ptr
0041b48f  add  eax, ecx
0041b491  mov  ecx, dword ptr [eax + 0x24]
0041b494  and  ecx, 0xff
0041b49a  mov  dword ptr [esp + 0xa0], ecx       ; A = 低字节（格子种类，0x0e = ?）
0041b4a1  mov  ecx, dword ptr [eax + 0x24]
0041b4a4  and  ecx, 0xf00
0041b4aa  shr  ecx, 8
0041b4ad  mov  dword ptr [esp + 0x98], ecx       ; B = 第 2 字节（玩家位掩码）
0041b4b4  mov  eax, dword ptr [eax + 0x24]
0041b4b7  and  eax, 0xff0000
0041b4bc  shr  eax, 0x10
0041b4bf  mov  dword ptr [esp + 0xa4], eax       ; ★ C = 第 3 字节 = 对象槽号+1
0041b4c6  test eax, eax
0041b4c8  je   0x41b4e0
0041b4ca  lea  ebx, [eax - 1]
0041b4cd  mov  eax, ebx
0041b4cf  shl  eax, 2
0041b4d2  sub  eax, ebx
0041b4d4  mov  al, byte ptr [eax*8 + 0x496d08]   ; ★ 对象类型 = objects_info[槽].+0
0041b4db  and  eax, 0xff
0041b4e0  mov  dword ptr [esp + 0x9c], eax       ; 对象类型（0 = 无对象）
; —— 按类型分派 ——
0041b7ef  mov  eax, dword ptr [esp + 0x9c]
0041b7f3  dec  eax
0041b7f6  cmp  eax, 0x11
0041b7f9  ja   0x41c164
0041b7ff  jmp  dword ptr [eax*4 + 0x41b3e5]     ; ★ 对象类型分派表
```
**分派表 `0x41b3e5`，18 项（类型 1..0x12）实测**：

| 类型 | 处理函数 | 说明 |
|---|---|---|
| 1..10 | `0x41b807` | 神明/其它：`attach_god` |
| 11 (`0x0b`) | `0x41b837` | 特殊（`remove_object(0xb)`） |
| 12 (`0x0c`) | `0x41b807` | 同 1..10 |
| 13 (`0x0d`) | `0x41b8f9` | **道具格**：随机得一个道具（1..8），台词 `得到%s！` |
| 14 (`0x0e`) | `0x41bb0c` | 得 500 点券（`add word [player+0x30], 0x1f4`） |
| 15 (`0x0f`) | `0x41c164` | 不处理 |
| **16 (`0x10`)** | **`0x41bceb`** | **路障** |
| **17 (`0x11`)** | **`0x41be5f`** | **地雷** |
| **18 (`0x12`)** | **`0x41bfd2`** | **定時炸彈** |

★ **两处入口形态的订正**（2026 本轮通道 2 补，`tests/test_object_landing_fragments.py` 44/44）：

1. 分派器**函数体是 `0x41b42d`**（`push ebx/esi/edi/ebp` + `sub esp,0xa8`，
   尾声 `0x41c844` = `add esp,0xa8; pop×4; ret`）。`0x41abde` 是**上一层**
   （`0x4198b9`）里的标签；`0x41b3d0` 是 `0x4198b9` 的尾声（`add esp,0xf8`），
   与本分派器无关 —— 第 94 条曾把它当成「共享尾声」。
2. **actor 8（機器娃娃）在进跳表之前就被截住**：
   ```asm
   ; @source 0x41b4e7
   0041b4e7  mov  eax, dword ptr [0x49910c]
   0041b4ec  cmp  eax, 8 / jne 0x41b536          ; 不是娃娃 → 正常走类型跳表
   0041b4f1  cmp  dword ptr [esp + 0xa4], 0 / je 0x41c844   ; 这格没物件 → 收场
   0041b519  call 0x40fafd                       ; 打飞动画（物件下标, 娃娃的格, 上一格）
   0041b529  call 0x40e14d                       ; remove_object(槽号)
   0041b531  jmp  0x41c844                       ; ★ **不再进类型跳表**
   ```
   ⇒ 各处理函数里那些 `cmp …, 8 / jge 另一支` 对 actor 8 是**死代码**
   （防卫生成），真正生效的是 `rules/special-actors.ts` 的 `runDoll`。

#### 6.3.0 ★★ actor 轴：同一个物件，四个玩家 / 小偷 / 另外三个惡人 各走哪一支

四条分支的**共同形状**是「先按 actor 分流，再各自看 `[0x48baf8]`（剩几格）」。
`[0x48baf8] != 0` 表示**这一格不是停下来的那一格**（真值见 `ui-screens.md`：
走子驱动 `0x40d8f3` 是「先处理上一格的落点、再 `dec [0x48baf8]`」，
所以**只有最后一步**的处理函数看到 0）。

| 类别 | actor 0..3（玩家） | actor 4（小偷） | actor 5..7（強盜/流氓/間諜） | actor 8 |
|---|---|---|---|---|
| 14 寶箱 | `remove(0xe)` + `+0x30 += 500` + 事务 + 文字框 + `player_say(自己,0,…)` | `remove(0xe)` + **主人** `+0x30 += 500`，台词由**主人**说，收尾调 `refresh_map()` | 什么也不发生 | 跳表外（见上） |
| 16 路障 | `remove(槽号)` + `[0x48baf8]=0` + `say(自己,1,#0247)` | `remove(槽号)` + `receive_tool(主人,2)`（+文字框） | `remove(槽号)` + `[0x48baf8]=0`（**不说台词、不回收**） | 同上 |
| 17 地雷 | 停稳才炸：`remove(槽号)` + 毁座驾 + 动画 + `say(自己,1,#0248)` + **住院 3 天** | `remove(槽号)` + `receive_tool(主人,3)`（不毁车、不住院） | **停稳时**：`remove(槽号)` + 动画 + **住院 3 天**（不毁车、不说） | 同上 |
| 18 炸彈 | `+0x40 = 槽号` + 记录 `+5=自己+1`、`+4=0x26` + 清当前格 + 事务 + `say(自己,2,#0249)` | `remove(槽号)` + `receive_tool(主人,4)` | 什么也不发生 | 同上 |
| 13 道具格 | `remove(0xd)` + 抽道具 + 事务/文字框 | `remove(0xd)` + 把抽到的道具给主人 | 什么也不发生 | 同上 |

三条容易做错：
1. **`receive_tool(主人, k)` 不是「白给」** —— `0x445a4d` 先从**商店库存**
   `remain_tool_amount[k-1]`（`0x49731f + k - 1`）扣 1，库存为 0 就直接返回
   （`0x445a73`；`k > 8` 才跳过库存检查）。所以小偷「拆下来的陷阱」是
   **从商店池里划一件给主人**，不是凭空造一件。
2. **玩家分支把陷阱还的是「商店池」**（`remove_object` 里 `inc [0x497321..]`，§6.2），
   **不进任何人的道具栏** —— 与 actor 4 那一支不同。
3. **`refresh_map()`（`0x41d546`）在本分派器里只有寶箱替身支调用一次**
   （`0x41bb02`）；路障/地雷/炸彈三支都不调。

#### 6.3.0b 寶箱 `0x41bb0c`（★ 唯一写死槽号 + 唯一调 `refresh_map()` 的一支）

```asm
; @source 0x41bb0c —— player 分支（actor 0..3）
0041bb0c  cmp  dword ptr [0x49910c], 4 / jge 0x41bb9d
0041bb19  cmp  dword ptr [0x48baf8], 0 / jne 0x41bb9d   ; ★ 停稳才算
0041bb31  push 0xe / call 0x40e14d                      ; ★ **写死槽 14**（见 §6.1.2）
0041bb3b  push 1 / push 0 / push 0 / call 0x41d476      ; 落点事务
0041bb49  push 0x5dc / push 0x463ad3 / call 0x440cac    ; 文字框「得到５００點券！」
0041bb5b  imul eax, dword ptr [0x49910c], 0x68
0041bb62  add  word ptr [eax + 0x496b98], 0x1f4         ; ★ 16 位加（+0x30）
0041bb7f  mov  edi, [0x48084a + 角色×0x6c]              ; '#1050別忌妒我！'
0041bb8a  push ebp(cur) / push 0 / push edi / call 0x44ef41     ; player_say(cur, 0, …)

; @source 0x41bb9d —— 替身分支（只认 actor 4）
0041bb9d  mov  ebx, dword ptr [0x49910c]
0041bba3  cmp  ebx, 4 / jne 0x41c164                    ; ★ 5..7、8 都不理
0041bbb1  cmp  byte ptr [eax + 0x498df5], 0 / jne 0x41c164   ; 槽 +0x0d（冻结）⇒ 跳过
0041bbcd  push 0xe / call 0x40e14d
0041bbed  movzx edi, byte ptr [eax + 0x498df0]          ; edi = 槽 +8 = **占用者（主人）**
0041bcb6  add  word ptr [edi*0x68 + 0x496b98], 0x1f4   ; ★ 加到**主人**头上
0041bcdd  push edi / push 0 / push 台词 / call 0x44ef41 ; ★ 台词由**主人**说
0041bce6  jmp  0x41bb02                                 ; → call 0x41d546 = refresh_map()
```

⇒ 「寶箱 = 500 點券」对玩家与替身都成立，**加的对象不同**（自己 / 主人），
而且替身那一支会**整屏刷新**（原版只有它调 `0x41d546`）。

#### 6.3.1 路障 `0x41bceb`

```asm
0041bceb  mov  eax, dword ptr [0x49910c]
0041bcf0  cmp  eax, 8
0041bcf3  jge  0x41bd65                        ; 实体 >= 8 → 另一支路
0041bcf5  cmp  eax, 4
0041bcf8  je   0x41bd65                        ; 实体 == 4 → 另一支路
0041bcfa  ...  mov eax, dword ptr [0x4749d4] / shl 3 / add 0x48234a / push / call 0x4542e9
0041bd10  mov  edx, dword ptr [esp + 0xa4]
0041bd17  push edx / call 0x40e14d              ; ★ remove_object(slot+1) → remain[1] += 1
0041bd20  push 1 / push 0 / push 0 / call 0x41d476
0041bd2e  xor  ecx, ecx / mov dword ptr [0x48baf8], ecx   ; 清「事件进行中」
0041bd36  mov  ebx, dword ptr [0x49910c]
0041bd3c  cmp  ebx, 4 / jge 0x41c164
0041bd45  ...  mov ebp, dword ptr [eax + 0x480d92]        ; '#0247誰敢擋我\n去路？！'
0041bd5c  push ebp / push 1 / push ebx
0041bd60  jmp  0x41bb90                                   ; player_say → 分派出口
0041bd65  mov  ecx, dword ptr [0x49910c]
0041bd6b  cmp  ecx, 4
0041bd6e  jne  0x41c164                                   ; ★ 实体 8 在这里被排除
0041bd74  ...（仅实体 4：remove_object + sprintf(0x47edb6='路障') + receive_tool(p,2)）
```
- **正常玩家**：路障被销毁（回库存 1）、播格动画、清 `0x48baf8`、说 `#0247`，
  然后跳到**分派出口**——本格不再继续结算。
- **无住院、无金钱损失**。
- ★★ **actor 5..7 也走这条玩家分支**（`cmp eax,8 / jge` 与 `cmp eax,4 / je` 只排掉
  8 与 4）：照样 `remove_object(槽号)` + `[0x48baf8] = 0`，只是 `cmp ebx,4 / jge`
  让**台词被跳过**、也**不回收给主人**。
- ★ **actor 4（小偷）那一支**（`0x41bd65`）除了 `remove_object` 还写一句
  `sprintf(buf, "小偷偷得%s\n\n給%s！"/*0x463ac0*/, 0x47edb6='路障')` 并 `show(buf, 0x5dc)`，
  再 `receive_tool(占用者, 2)`；**不调 `refresh_map()`**（整个分派器里只有寶箱那支调）。

#### 6.3.2 地雷 `0x41be5f`

```asm
0041be5f  mov  ebp, dword ptr [0x49910c]
0041be65  cmp  ebp, 8
0041be68  jge  0x41bf16
0041be6e  cmp  ebp, 4
0041be71  je   0x41bf16
0041be77  cmp  dword ptr [0x48baf8], 0
0041be7e  jne  0x41bf16                        ; ★ 事件进行中 → 不触发
0041be84  mov  edx, dword ptr [esp + 0xa4]
0041be8c  call 0x40e14d                        ; remove_object → remain[2] += 1
0041be94  mov  ecx, dword ptr [0x49910c]
0041be9a  cmp  ecx, 4 / jge 0x41bea8
0041be9f  push ecx / call 0x40cd07             ; ★ 车辆报废（并置 flags |= 0x40）
0041bea8  push 0 / push 0 / push 0x20d / push mkf_data / call 0x450441   ; 爆炸动画
0041bece  call 0x45144f
0041bedf  mov  ebp, dword ptr [0x49910c]
0041bee5  cmp  ebp, 4 / jge 0x41b8de
0041bef1  ...  mov ecx, dword ptr [eax + 0x480d96]   ; '#0248誰這麼缺德？！'
0041bf09  call 0x44ef41
0041bf11  jmp  0x41b8de
; —— 0x41b8de（住院出口）——
0041b8de  xor  edi, edi
0041b8e0  mov  dword ptr [0x48baf8], edi
0041b8e6  push 3
0041b8e8  mov  ebp, dword ptr [0x49910c]
0041b8ee  push ebp
0041b8ef  call 0x43ec3f                        ; ★ add_player_days_in_hospital(cur, 3)
```
- **踩到 = 车辆报废（若为機車/汽車）+ 住院 3 天**（A）。
  `fcn_0040cd07` 只对 `traffic & 3 ∈ {1,2}` 回池；`0x1f`（工程車）**不回池**（§4.12）。
- **实体 4 / ≥8 / 「移动中」都走 `0x41bf16`**，而那一支的门槛是 `current_player == 4`
  （`0x41bf25 cmp ecx,4 / jne 0x41c164`）⇒ 实际只有 **actor 4（小偷）** 继续，
  他走的是「`remove_object` + `receive_tool(主人,3)`」那一支（**不毁车、不住院**）。
- ★★ **actor 5..7 落在上面这条「玩家分支」里**（`cmp ebp,4 / je` 只排掉 4，
  `cmp ebp,8 / jge` 只排掉 8）⇒ 強盜/流氓/間諜**踩中地雷会住院 3 天**
  （`cmp ecx,4 / jge` 跳过毁车、`cmp ebp,4 / jge` 跳过台词）。
  ⚠️ 但整支的前提是 `[0x48baf8] == 0` ⇒ **只有停在这一格才炸**；路过不炸。

#### 6.3.3 定時炸彈 `0x41bfd2`（**关键：它会转移**）

```asm
0041bfd2  mov  eax, dword ptr [0x49910c]
0041bfd7  cmp  eax, 4
0041bfda  jge  0x41c072
0041bfe0  imul eax, eax, 0x68
0041bfe3  mov  dl, byte ptr [eax + 0x496ba8]   ; 自己是否已挂着一个物件
0041bfe9  test dl, dl
0041bfeb  jne  0x41c072
0041bff1  cmp  dword ptr [0x48baf8], 0
0041bff8  jne  0x41c072
0041bffa  mov  bl, byte ptr [esp + 0xa4]       ; 槽号+1
0041c001  mov  byte ptr [eax + 0x496ba8], bl   ; ★ players_state[cur].+0x40 = 槽号+1
0041c007  mov  cl, byte ptr [0x49910c]
0041c00d  inc  cl
0041c00f  mov  ebx, dword ptr [esp + 0xa4]
0041c016  dec  ebx
0041c017  mov  eax, ebx
0041c019  shl  eax, 2
0041c01c  sub  eax, ebx
0041c01e  mov  byte ptr [eax*8 + 0x496d0d], cl   ; ★ objects_info[slot].+5 = cur+1
0041c025  mov  byte ptr [eax*8 + 0x496d0c], 0x26 ; ★ objects_info[slot].+4 = 38
0041c034  mov  ecx, dword ptr [0x498e80]
0041c03a  mov  byte ptr [ecx + eax*8 + 0x26], dl ; 节点反向索引清 0
0041c063  mov  ebx, dword ptr [eax + 0x480d9a]   ; '#0249我不要∼∼∼'
0041c069  push ebx / push 2 / push ecx
0041c06d  jmp  0x41bb90
```
**倒计时**（每走一步减 1，源自 `_rich4_player_move_one_step_done` 前段）：
```asm
; @source 0x41b697
0041b697  imul eax, dword ptr [0x49910c], 0x68
0041b69e  mov  ch, byte ptr [eax + 0x496ba8]   ; 自己挂着的物件
0041b6a4  test ch, ch
0041b6a6  je   0x41b7ef
0041b6ac  mov  al, ch
0041b6ae  and  eax, 0xff
0041b6b3  lea  ebx, [eax - 1]
0041b6b6  mov  eax, ebx
0041b6b8  shl  eax, 2
0041b6bb  sub  eax, ebx
0041b6bd  mov  dl, byte ptr [eax*8 + 0x496d0c] ; +4 = 倒计时
0041b6c4  dec  dl
0041b6c6  mov  byte ptr [eax*8 + 0x496d0c], dl
0041b6cd  jne  0x41b78b                        ; 未到 0 → 只做「转移给同格人类玩家」检查
0041b6d3  ...（爆炸：音效 0x482362 + remove_object + 节点 +0x20 结算 + fcn_0040cd07）
; @source 0x41b78b（转移）
0041b78b  test edi, edi / je 0x41b7ef          ; edi = 同格玩家位掩码
0041b795  call 0x40d293                        ; 取最低位玩家下标
0041b7a2  cmp  byte ptr [eax + 0x496b7d], 0
0041b7a9  je   0x41b7ef                        ; ★ +0x15 == 0 → 不转移（见下方 6.3.4）
0041b7ab  mov  ch, byte ptr [eax + 0x496ba8]
0041b7b1  test ch, ch / jne 0x41b7ef           ; 对方已有物件 → 不转
0041b7b7  mov  bh, byte ptr [edi + 0x496ba8]
0041b7bd  mov  byte ptr [eax + 0x496ba8], bh   ; ★ 炸弹转到对方身上
0041b7e5  mov  byte ptr [eax*8 + 0x496d0d], cl ; 更新 objects_info.+5 = 新 owner+1
0041b7f1  mov  byte ptr [edi + 0x496ba8], ch   ; 自己清空
```
### 6.3.4 ★ `player+0x15` 与 `player+0x64` **不是同一个字段**（本轮查清，纠正过一次误判）

炸弹转移那句 `cmp byte ptr [eax+0x496b7d], 0 / je` 的判据，
早期注释写「只转给**人类**玩家」。本轮曾一度把 `+0x15` 当成 `who_plays`
并"改正"为「转给仍在局中的玩家（**电脑也算**）」——**那次改正是错的**。
逐指令查清如下：

| 字段 | 语义 | 证据 |
|---|---|---|
| **`player+0x64`**（`0x496bcc`） | **`who_plays`**：`1` = 人类，`2` = 电脑，`0` = 未参与 | `@source 0x00407247` `test byte ptr [eax+0x496bcc], 1 / je` → 为 1 时 `inc dword ptr [0x499104]`（人类玩家数） |
| **`player+0x15`**（`0x496b7d`） | **本回合活跃/状态字节**：回合开始时**由 `+0x64` 赋值**，回合结束时**对其它玩家一律清 0**；高位是附加状态 | 赋值：`@source 0x00418d01` `mov dl,[eax+0x496bcc]` → `@source 0x00418d07` `mov byte ptr [eax+0x496b7d], dl`。清零：`@source 0x0041d95d`–`0x0041d962` 遍历全部玩家，`cmp ebx,esi`（esi = 当前玩家）**跳过当前玩家**，其余 `xor ch,ch` / `mov [eax+0x496b7d],ch` |

**A 级实证（两个真实存档）**——只有**当前行动者**的 `+0x15` 非 0：

| 存档 | 玩家 | `+0x64`(who_plays) | `+0x15` |
|---|---|---|---|
| `Save0.dat` | 0 / **1** / 2 / 3 | 0 / **1** / 0 / 0 | 0 / **1** / 0 / 0 |
| `SAVE1.DAT` | **0** / 1 / 2 / 3 | **1** / 2 / 2 / 2 | **1** / 0 / 0 / 0 |

（`Save0` 玩家 1 现金 313,273，其余为 0；`SAVE1` 玩家 0 现金 150,000 —— 与"谁是当前/唯一真人"吻合。）

**因此 `+0x15` 的高位是状态位**（由各处 `or`/`and` 维护）：

| 位 | 含义 | 证据 |
|---|---|---|
| `0x01` | **是人类玩家**（低位= who_plays 的低半字节） | `@source 0x0041d97b` `test byte ptr [eax+0x496b7d], 1` |
| `0x10` / `0x20` | 不可行动状态（与 `0x30` 一起被 `test`） | `@source 0x0040d6d1` `or byte ptr [ebx+0x496b7d], 0x10`；`@source 0x0040d60e` `or ..., 0x20`；`@source 0x00418dd8` `test ..., 0x30` |
| `0x40` | **本回合没有座驾**（纯**表现位**：重绘例程据此画步行/坐车） | 唯一写点 `@source 0x0040cd5e` `or byte ptr [eax+0x496b7d], 0x40` —— 它在 **`0x40cd07`（毁座驾/回合末回收交通工具）** 里，且是**无条件**的（连 `traffic_method == 0` 那一支也置）；唯一读点 `@source 0x0040b976` `test cl, 0x40`（在重绘例程 `0x40b93b` 内）。★ 2026-09-18 订正：本行原写「破产/出局」——`0x40cd07` 与破产无关（破产在 `0x40ce2e` 一带）。通道 2 证据：`tests/test_vehicle_wreck.py`（17/17）|
| 高位整体 | 用 `and 0xf` 清除（回合重置） | `@source 0x00418f87`、`0x0043d601`、`0x0043ecad` 均为 `and byte ptr [.. +0x496b7d], 0xf` |

**修正后的正确表述**：炸弹转移的候选是「同节点玩家掩码里**最低下标**的那一个」，
仅当它的 `+0x15 != 0` 时才转移。由于 `+0x15` 对**非当前玩家**在回合结束时已被清 0，
这条判据**在实践中就是"只转给（当前回合的）人类玩家"** —— 原注释方向正确，
而"电脑也会接手"是**错的**。

> ⚠️ **教训**：`+0x15` 与 `+0x64` 都是"玩家状态"，很容易想当然地当成同一个字段。
> 判据：**凡是要判 `who_plays`，用 `+0x64`；凡是要判"本回合是否活跃 / 是否人类 / 是否出局"，用 `+0x15` 的对应位。**
> 复刻侧若把存档里的 `+0x15` 当 `whoPlays`，**读原版存档会把全部电脑玩家判成出局**。

（注：`0x41b78b` 之后的逐条地址我按上游标签与 exe 语义对齐，未逐条重取；
`0x41b697`–`0x41b6cd` 与 `0x41bfd2`–`0x41c06d` 两段已逐条复核 —— 见 §7 的对照方法。）
- **语义（A）**：定时炸弹落地时是「无主」的；**第一个踩到它的玩家把它捡起来挂在自己身上**
  （`+0x40 = 槽号+1`，`objects_info.+4 = 0x26 = 38`，`.+5 = 玩家+1`）。
  此后该玩家**每走一步**倒计时 −1；若中途与另一个人**类**玩家同格且对方身上没有物件，
  炸弹会**转嫁**过去（台词「我不要∼∼∼」）。倒计时归零时爆炸。
- **总结论：存档必须保存 `objects_info` 全表（46×24）才能还原地雷/路障/定时炸弹**，
  另外 `players_state[].+0x40`（挂着的物件索引）也必须存
  ——它在 `all_players_state` 块（4×0x68）里，已包含在内。
  §6.4 的存档块列表就是最终答案。
- ★★ **`+0x40` 是「物件槽号」不是「类别」**（通道 2 钉住：`0x41bffa mov bl,[esp+0xa4]`
  → `0x41c001 mov [player+0x496ba8], bl`，而 `[esp+0xa4]` 就是分派器拆出来的槽号）。
  `0x40e14d` 正是用 `objects_info.+5`（携带者+1）反查玩家、再清他的 `+0x40`。
- ★ **actor 5..7 踩到炸彈什么也不发生**：`0x41bfd7 cmp eax,4 / jge 0x41c072`，
  而 `0x41c072` 里 `cmp ebx,4 / jne 0x41c164` 只放 actor 4 过去。
- ★ **actor 4 那一支**（`0x41c072`，要求槽 `+0x0d == 0`）：`remove_object(槽号)` + 事务
  + `sprintf(… 0x47edbe='定時炸彈')` + 音效 + `show(buf,0x5dc)` + `receive_tool(占用者, 4)`；
  **不往任何人身上挂**（`+0x40` 不动），也不调 `refresh_map()`。

### 6.4 存档中的道具相关块（`_rich4_load_game_from_file` @ `0x00402ac5` / `_rich4_save_game_to_file` @ `0x00402fd1`）（A）

| 顺序 | 全局 | VA | 尺寸 | 内容 |
|---|---|---|---|---|
| 1 | `rich4_all_players_state` | `0x496b68` | 4 × 0x68 = 416 | 含 `tool` 无关状态，但含 `+0x40` 挂载物件索引、交通方式等 |
| 2 | `_num_human_players` | `0x499104` | 1 × 4 | |
| 3 | `rich4_all_special_players_state` | `0x498e28` | **5 × 0x10 = 80** | 5 个特殊实体（含機器娃娃用的实体 8） |
| 4 | **`rich4_objects_info`** | `0x496d08` | **0x2e × 0x18 = 1104** | ★ **地雷/路障/定時炸彈/道具格/神明的全部持久状态** |
| 5 | `rich4_player_cards` | `0x499120` | 0x3c × 1 = 60 | |
| 6 | **`rich4_player_tool_amount`** | `0x49915c` | **0x3c × 1 = 60** | ★ 4 人 × 15 种持有量 |
| 7 | `rich4_remain_card_amount` | `0x499198` | 0x1e × 1 = 30 | |
| 8 | **`rich4_remain_tool_amount`** | `0x497320` | **8 × 1 = 8** | ★ 商店/池库存（仅道具 1..8） |
| 9 | `ref_00499100` | `0x499100` | 1 × 4 | |
| 10 | `ref_00497328` | `0x497328` | 0x6c0 × 4 | |
| 11 | `rich4_player_stocks` | `0x4971a0` | 0x30 × 8 | |
| 12 | `_stocks_on_map` | `0x496980` | 0xc × 0x24 | |

```asm
; @source 读档 0x402bca / 0x402bee / 0x402c12；存档 0x40309d / 0x4030c1 / 0x4030e5
; —— 读（_rich4_load_game_from_file）——
00402bca  push edi / push 0x2e / push 0x18 / push 0x496d08 / call 0x4576d0  ; fread(objects_info, 24, 46)
00402bee  push edi / push 0x3c / push 1    / push 0x49915c / call 0x4576d0  ; fread(tool_amount, 1, 60)
00402c12  push edi / push 8    / push 1    / push 0x497320 / call 0x4576d0  ; fread(remain_tool_amount, 1, 8)
; —— 写（_rich4_save_game_to_file）——
0040309d  push ebx / push 0x2e / push 0x18 / push 0x496d08 / call 0x457ada  ; fwrite(objects_info, 24, 46)
004030c1  push ebx / push 0x3c / push 1    / push 0x49915c / call 0x457ada
004030e5  push ebx / push 8    / push 1    / push 0x497320 / call 0x457ada
```
> 实体 8（機器娃娃）的状态也在存档里（`special_players_state` 5×0x10），
> 但**没有** `player_tool_amount` 之外的道具状态。

### 6.5 `fcn_0040ac7b(sel, flags, mode, src)` @ `0x0040ac7b` —— 飛彈的破坏内核（A/B）

已确认的事实（逐条可复核）：

1. `fcn_0040a45c(sel)` @ `0x40a45c` 先把 440×440 的**格→实例**字表（指针 `[0x474938]`，
   行距 `0x1b8`）清空并重建（`call 0x409de7` 里 `push 0x5e880` = 387200 = 440*440*2），
   然后把窗口内的非 0 项收集到 `0x48b8c4`，返回个数。
   - `sel == -1` → `edi = 0x1b8`（440），`esi = 0` → **整张表**；
   - 否则 `edi = 2*sel`，`esi = 441*(0xdc - sel)`；循环 `row < edi`、`col < edi`、每行 `esi += 0x1b8`。
2. 对列表里每个格值（`[esp+8]`）：
   - `flags & 2` 且 `0x7d0 < v < 0xfa0`（地产）：
     - `mode == 0`：向 `owner-1` 记 `30 * price_index` 敌意；`level--`；
       `type != 0`（商業用地）时 `level = type = 0`（拆平）。
     - `mode != 0`：向 `owner-1` 记 `level*2*15*price_index` 敌意；
       `owner = level = type = 0`，`[land+0x30] = 0`（**完全清除**）。
   - `flags & 4` 且 `0xfa0 ≤ v < 0x1770`（设施）：同上，多清 `[facility+0x34]`。
   - `flags & 0x20` 且 `v & 0x8000`（**这是玩家/实体实例**）：
     ```asm
     0040ae8a  test byte ptr [esp + 8], 0xf / je 0x40aeac
     0040ae9a  test byte ptr [esp + 8], 1 / je 0x40ae90
     0040aea1  push ebx / call 0x40cd07         ; ★ 玩家 0..3：车辆报废 + flags |= 0x40
     0040aeb4  test byte ptr [esp + 4], 0xf0 / je 0x40aee0
     0040aecc  test byte ptr [esp + 8], 0x10 / je 0x40aec2
     0040aed3  push 0 / push ebx / call 0x43ec3f ; ★ 实体 4..7：hospital(p, 0) → 清 flags
     0040aee0  test byte ptr [esp + 5], 0x7f / je 0x40af04
     0040aeeb  sar  eax, 8 / and eax, 0x7f
     0040aefb  push eax / call 0x40e14d          ; ★ 销毁该实例对应的对象槽
     ```
     → 这才是**飛彈/核子飛彈让玩家住院的因果链**：破坏内核给玩家打 `flags |= 0x40`，
     随后 §4.7/§4.13 的循环只对带 `0x40` 的玩家结算敌意与住院。
     住院函数 `0x43ecad` 会 `and byte [flags], 0xf` 清掉该位，闭环成立。
3. `flags = 0x26 = 0b0010_0110` → 位 1(地产)、位 2(设施)、位 5(玩家/实体实例)
   三路全开；位 0/3/4 未使用。

> **C（未决）**：`sel = 0x64 = 100` 时窗口是「以格 (220,220) 为中心、边长 200 的正方形」
> （由 `441*(220-sel)` 的恒等式 A 级确认），但 `0x64` 是**常量**、
> 与玩家选中的格无关。因此我**无法**从静态证据确定「飛彈只炸选中格」这一常识是否成立。
> 见 §8-②。

---

## 七、上游与 exe 的矛盾

### 7.1 ⚠️ 被**推翻**的指控：`rich4_tool_chuansongji.asm` 「少了 `0044760f`」

**任务背景给出的指控**：上游第 140..173 行少了 exe 中
`0044760f mov dword [源+0x30], 0`（清源头的上次过路费）。

**核实结果：指控不成立（A）。**

1. 逐指令对照：`0x447428`–`0x4479d2` 区间（下一个函数 `fcn_00447c00` 之前）
   反汇编得 **409 条指令**；把上游 `rich4_tool_chuansongji.asm` 的函数体去注释后
   也是 **409 条**，且**逐条一一对应**（我用脚本打印了 0..408 的完整对齐表，全部一致）。
2. 该指令确实存在，在**文件第 174 行**：
   ```
   168	mov bl, byte [esi + eax + 0x18]
   169	mov byte [edx + esi + 0x18], bl
   170	mov byte [esi + eax + 0x18], 0
   171	mov ecx, dword [esi + eax + 0x34]
   172	mov dword [edx + esi + 0x34], ecx
   173	mov dword [esi + eax + 0x34], 0
   174	mov dword [esi + eax + 0x30], 0     ; ★ 就是 0x0044760f
   175	jmp near loc_0044755a
   ```
   exe 原文：
   ```asm
   004475ff  mov  ecx, dword ptr [esi + eax + 0x34]
   00447603  mov  dword ptr [edx + esi + 0x34], ecx
   00447607  mov  dword ptr [esi + eax + 0x34], 0
   0044760f  mov  dword ptr [esi + eax + 0x30], 0   ; ★ 存在
   00447617  jmp  0x44755a
   ```
3. 结论：该指令**已在第 174 行**；指控里的行号范围「140..173」恰好把它排除在外，
   属于**行号口径错误或旧版本残留**。上游此函数**当前版本与 exe 完全一致**，
   不需要补任何指令。

### 7.2 真实差异（3 处，均为「共享尾码内联」，**无语义差别**）

我逐函数核对了 13 个 `rich4_tool_*.asm` 与 exe 的指令条数：

| 文件 | exe 条数 | 上游条数 | 结论 |
|---|---|---|---|
| `rich4_tool_jiqiwawa` | 37 | 37 | 一致 |
| `rich4_tool_luzhang` | 68 | 68 | 一致 |
| `rich4_tool_dilei` | 68 | 68 | 一致 |
| `rich4_tool_dingshizhadan` | 68 | 68 | 一致 |
| `rich4_tool_jiche` | 56 | 56 | 一致 |
| `rich4_tool_qiche` | **52** | **60** | 见下 (7.2-a) |
| `rich4_tool_feidan` | 104 | 104 | 一致 |
| `rich4_tool_yaokongtouzi` | 121 + 5 | 121 | 一致（后 5 条属另一函数 `fcn_00447285`） |
| `rich4_tool_jiqigongren` | 80 | 80 | 一致 |
| `rich4_tool_shiguangji` | 53 | 53 | 一致 |
| `rich4_tool_chuansongji` | 409 | 409 | **完全一致**（见 §7.1） |
| `rich4_tool_gongchengche` | 72 | 72 | 一致 |
| `rich4_tool_hezifeidan` | **97** | **104** | 见下 (7.2-b) |

**(7.2-a) qiche**：exe 的「已在汽車上」提前返回走**共享尾码**
```asm
00446f1a  xor  edx, edx
00446f1c  jmp  0x446eff          ; ★ 跳到共享的 mov eax,edx / pop edi / pop esi / pop ebx / ret
```
上游第 22–26 行把这段尾码**内联展开**（`mov eax,edx; pop edi; pop esi; pop ebx; ret`），
差 4 条；第二次提前返回同样内联，再差 4 条 → 52 vs 60。**执行语义相同。**

**(7.2-b) hezifeidan**：exe 的玩家循环退出直接跳进**飛彈的尾码**
```asm
00447bb3  cmp  ebx, dword ptr [0x499114]
00447bb9  jge  0x4470ea          ; ★ 目标落在 feidan（0x446fbc–0x4470f8）内部
```
`0x4470ea` = `call 0x41d546 (refresh_screen)`，`0x4470ef` = `mov eax,ebx; add esp,8; pop ebp; pop edi; pop ebx; ret`。
上游第 132–141 行把这段尾码内联（7 条）→ 97 vs 104。**执行语义相同。**
但上游沿用了从 feidan 抄来的**标签名**（`loc_004470ea` / `loc_004470ef`），
`jge near loc_004470ea` 既然解析到本地内联副本，汇编结果仍是 `jge 0x4470ea`，
**不是错误**，但可读性差且容易引发误判（本次的头号指控正是这类误判的近亲）。

### 7.3 与既有规格 `docs/systems/land-rent.md` 的一处不一致（需回改）

`land-rent.md` 第 37 行断言：「结构体在 `0x20` 之后到 `0x30` 之间**没有别的字段**」。

傳送機的地产迁移代码显示 **存在 `+0x2c`（4 字节）字段并且会被清零**：
```asm
00447546  mov  ecx, dword ptr [eax + 0x30]   ; 源 +0x30 → 目标 +0x30
00447549  mov  dword ptr [edx + 0x30], ecx
0044754c  mov  dword ptr [eax + 0x30], 0
00447553  mov  dword ptr [eax + 0x2c], 0     ; ★ +0x2c 被单独清零
```
若 `+0x2c` 不是独立字段，这条 `mov dword [eax+0x2c], 0` 没有意义。
因此 **`0x2c..0x2f` 是地产结构里的第 7 个（最后一个）字段**，`land-rent.md` 的表述应修正为：
「`0x20..0x2b` 是 6 项租金表，`0x2c` 另有一 4 字节字段（语义未定位），`0x30` 为 `flast`」。
（对设施结构，对应位置是 `+0x30`/`+0x34` 两个 4 字节字段，傳送機同样迁移并清零。）

### 7.4 上游 `tool_table` / `tool.h` 与 exe **完全一致**（A）

`rich4-re/asm/rich4_tool_table.c` 的 13 项（名称、`max_amount`、`price`、`f6`、`f7`）
与 §1.2 逐字节吻合，无需修正。
`asm/tool.h` 的 `rich4_tool` 结构（`name_ptr / max_amount / price / f6 / f7`）
与 `0x47fee2` 的实际布局一致。
`asm/rich4_tool_utils.c` 的 4 个函数（`receive_tool` / `after_player_use_tool` /
`receive_random_tool` / `player_sell_all_tools`）与 `0x445a4d` / `0x445aa2` /
`0x445ada` / `0x445b3f` 的反汇编语义一致（我逐条核对过判定阈值 9、`tool > 8`、
`remain += count`、交通工具回退 1/2/3 → 下标 4/5/11）。

### 7.5 需要提醒的其他上游/二手说法

- `rich4-re/asm/rich4_tool_table.c` 把 `+4` 命名为 `max_amount`（**最大持有量**），
  但 exe 里它是**商店/池的初始库存**，与「每人最多 9 个」（`0x445a64`）是两回事。
  命名建议改为 `initial_stock`。
- 上游 `rich4_tool_utils.c` 的 `rich4_remain_tool_amount[8]` 声明正确（`0x497320`，8 字节）。

---

## 八、未决清单（C 级，明确写「未决」，不用推测填充）

① **機器娃娃是否真的清除路障/地雷** — 未决。
   已确认：它把当前玩家复制成实体 8 并让实体 8 走一步（`0x446b94`–`0x446b9e`），
   台词为「替我除掉障礙物！」。
   已确认：路障分派 `0x41bcf0` 对 `current_player >= 8` 走 `0x41bd65`，
   而 `0x41bd65` 又 `cmp ecx,4; jne 0x41c164`；地雷分派 `0x41be65` 同理。
   即实体 8 走到路障/地雷上**什么都不发生**。
   在 exe 中**未找到**任何以 `current_player == 8` 为前提清除 `objects_info` 类型
   `0x10/0x11` 的代码。设计意图（是原版 bug 还是另有路径，例如
   `0x41c84f` 回合末的清理）**未决**。

② **飛彈的破坏几何范围** — 未决。
   `fcn_0040ac7b(0x64, 0x26, 0, cur)` 的 `0x64` 是**常量**，与选中的格无关。
   已确认 `fcn_0040a45c(0x64)` 收集的窗口是以格 `(220,220)` 为中心、
   边长 `2*0x64=200` 的正方形（由 `(220-sel)*440 + (220-sel) = 441*(220-sel)` 推得，A 级算术）。
   无法从静态证据判断这是「刻意的全屏级范围」还是「漏传了目标坐标」。
   核子飛彈的 `-1` = 整张 440×440 表，则是明确的。

③ **遙控骰子点数范围** — 未决。
   人类 UI 的取值来自 `[0x48c598]`，在鼠标移动处理器里是「骰面下标 + 1」（6 面 → 1..6）；
   `after` 路径与 `fcn_00419572` **都不做范围检查**。
   「是否存在能产生 0 或 > 6 的可达 UI 输入」未决定（`ebx == 0` 明确被当作取消）。

④ **傳送機第二次选择缺少类型校验** — 未决。
   `0x44750c` 之后直接 `imul edx, edx, 0x34`（地产）或 `× 0x38`（设施），
   不检查第二次返回值的范围。UI mask（`0x2090802` / `0x2090804`）的**位定义未破解**，
   因此「玩家能否点到非地产从而越界」未决。

⑤ **`traffic = 0x1f`（工程車）的游戏效果** — 未决。
   已确认：设置点（`0x447a5a`）、唯一识别式（`and 3 == 3`，`0x4479df`）、
   旧交通方式的备份位置（`+0x64`/`+0x65`）、`fcn_0040cd07` 对它不做退回。
   **未找到**「能否无视路障 / 能否拆除建筑」的实现代码。

⑥ **`tool_table.f6` 的语义** — 未决。
   13 项里 `f6` 为 `0,0,0,0,0,1,1,1,2,2,2,2,2`（= 0/1/2 三档）。
   xref 显示 `0x47fee2+6`（即第 1 项的 `f6`）与 `+8*i+6` 全表**没有任何读取者**。
   推测是「购买渠道/类别」，但无证据，故不写入规格。

⑦ **`objects_info.+1`（`0x496d09`）的语义** — 未决。
   写入点是 `0x40e11d`（`fcn_00407a8c(node+0x18 的第一个非 0 项, 本格)` 的低字节），
   读取点在 `rich4_animate_object.asm:41`（对应 `0x40e669` 附近）与 `rich4.asm:1892`。
   名称可暂定 `dist`，但**它的用途**（影响动画还是影响触发）未确认。

⑧ **玩家旗标 `+0x15 (0x496b7d)` 的完整位定义** — 部分未决。
   已确认：bit0 = 人类（`0x446b3e` 等）；bit6 = `0x40` = 「本回合被击中」
   （写：`0x40cd5e`、`0x44927b`；读：`0x4470ac`、`0x447bc2`；
   清：`0x43ecad` 的 `and ...,0xf`）。
   其余位（`0x02`、`0x04`、`0x10`、`0x20`、`0x80`）未逐一确认。

⑨ **玩家 `+0x32 (0x496b9a)`** — 未决。
   `fcn_0040cd07` 在它非 0 时**放弃车辆报废与 `0x40` 打标**（`0x40cd18`）。
   它是一个 dword，语义未定位（可能是「无敌/已住院/被神明附身」之一）。

⑩ **`0x40a45c` 里 `esi` 每行累加 `0x1b8`（440）而基址用 `441*(220-sel)`** —
   存在 1 的步长不一致（441 vs 440）。这是 exe 的实际行为，
   是否导致窗口错位一列、以及是否可达，未决。

⑪ **商店购买时点数不足的行为** — 未决。
   `_rich4_player_buy_tool`（`0x42d25c`）用 `sub word [player+0x30], price` 扣点数，
   **没有余额检查**；人类路径（`0x42e47a`）只检查「自己已有 < 9」。
   静态证据能确认「会无符号回绕」，但我**未**确认货架是否已在别处过滤掉买不起的道具
   （`0x42ebfe`–`0x42ecbb` 的上架循环只看 `remain_tool_amount`），
   也未确认能否通过 UI 触达该路径。**未决**。

⑫ **`tool_table` 的 `+6`（`f6`）** 已在 §8-⑥ 说明（无读取者）。

⑬ **`0x4755f0` 的 6 项「AI 采购优先级表」** — 实测内容为 `07 01 06 00 03 02`
   （→ 遙控骰子 / 路障 / 飛彈 / 機器娃娃 / 定時炸彈 / 地雷），
   用于 `0x42f255` 的自动采购循环；但「为何是这个顺序、与 `f7` 分类码如何配合」
   只有代码事实、没有文档依据，**语义未决**（不写入 §1 的字段语义）。

---

### 9.aa G 类审计：**函数写了没人调**（F 类的镜像）

```bash
cd rich4-remake
python3 tools/scratch/audit-uncalled.py      # core 全部导出函数，按「零引用」分级
```

F 类查「状态写了没人读」，G 类查「函数写了没人调」。两者命中的都是
**看起来实现了、其实没接线**的东西 —— 在 1:1 复刻里，这往往等于
**原版有、复刻写了壳却没接上**。

**口径（第一版写错过，务必照这个来）**：一个导出项若在**它自己的模块里**
被调用，那只是封装松；只有在**整个仓库里除声明行之外一次都不出现**，
才值得追。脚本分三级输出：

| 级别 | 判据 | 含义 |
|---|---|---|
| A | 生产代码零引用、**只有测试在调** | 多为「为测试而导出」的助手；少数是被取代的旧实现 |
| B | **全仓库零引用**（连测试都没有） | 真死代码，逐个查「原版里对应什么」 |
| — | 只在本模块内被调用 | 噪声，不输出 |

⚠️ 统计时要**排除 `src/testing/`**，否则 `factories.ts` 这类测试工厂会把
一堆真答案（例如 `slotsFrom`）标成死代码。

**已抓到**（`rich4-remake/docs/gaps/README.md` §7.26）：

- ★★ **破产清算的「下線拍卖」整段缺失** —— `0x40d1c6..0x40d20f`：
  释放地产 **> 3** 处时随机挑 **3** 处当场开拍（卖方席位 = −1，成交款进公库）。
  详见 `bank.md` §4.4（该节也是本轮新补的，此前无人读过 `0x40d002` 之后）。
- ★ **魔法屋「拍賣」结果空转** —— `applyMagicRequest` 的 `case 'auction'`
  就是一句 `return state`；规格 `magic-house.md` §5 早已写全，是**实现没跟上规格**。
- 顺带把一批「被后一版取代的第一代实现」清掉/标注（`releaseAssets`、
  `playerOccupancyBit`、`markLand`、`isSealed`/`isRaised`、`hasTool`/`heldTools`、
  `isNodeAvailableForObject`、`isNpcActor`、`stockScores`；`attachObject`/`applySummonCard`
  保留但写明「现役是 `attachGod`，不要接这条」）。

**配套教训**（§7.5 第 8 条）：**死代码会带着测试一起活着**。
`releaseAssets` / `markLand` / `isSealed` 各自都有绿测试，而它们断言的是
**没人调用的函数** —— 真正在跑的那条路（`applyBankruptcy` / `applyDistrictMark` /
`isSealedStrict`）当时反而**没被断言过**（破产清算清 `landTenure`/`facilityTenure`
这两条一直没测试）。所以删死代码时**必须把断言搬到现役路径上**。

`@source` 本轮新读的地址：`VA 0x40d089`（释放地块：owner→0、`+0x30` 四字节清零）、
`VA 0x40d0cc`（释放設施：`+0x34`）、`VA 0x40d10d`（企業归属无条件清零）、
`VA 0x40d143`（清算持股）、`VA 0x40d1c6`（下線拍卖闸门）、`VA 0x40d1e3`（开拍调用）、
`VA 0x43bde5`（拍卖主体，arg1=卖方/arg2=实体号/arg3=横幅）。

### 9.ab 数据表覆盖门禁（**规则以表为单位时用这一条**）

```bash
cd rich4-spec
python3 tools/audit_data_tables.py      # 已接进 run-all-checks.sh 第 3.25 步
```

**为什么单列**：`coverage-by-function.md` 那套按**函数**计覆盖度，
而**数据表装的是规则本身**（费率/价格/概率/年限/台词指针）——
一张表没有任何函数可挂，按函数审计会整个漏掉它。
本脚本把 `gen/layout.json` 的 **104 张 `table:data`** 逐张对照 `docs/**/*.md`，
漏一张就非零退出（可直接当门禁）。当前 **104/104**。

★ **同族工具的口径**（都在 `tools/`）：

| 工具 | 问的问题 | 单位 |
|---|---|---|
| `coverage.py` | 27 个玩法系统各写到什么程度 | 系统 |
| `audit_spec_coverage.py` | exe 里哪些函数 PRD 没提 | 函数 |
| `audit_unimplemented.py` | PRD 提过、remake 没提 | 函数 |
| `audit_data_tables.py` | 哪些数据表没进 PRD | **数据表** |

⚠️ **一条踩过的坑**：`layout.json` 的 `table:code`（64 张）**不能**当覆盖单位 ——
里面混着「真值表的子切片」（`0x475de1` = 道具表 +3、`0x475e70` = 新闻表 +19）、
CRT 表、以及把字符串/数据当成指针的**拼凑项**（`0x475ee0`、`0x466706`）。
判分派表要按**真值基址 + 目标函数**判。详见 `coverage-by-function.md` §5.4。

## 附：复核用命令（在 `rich4-spec/` 下执行）

```bash
# 道具数据表（13 项 × 8 字节，含 Big5 名称）
python3 - <<'PY'
import struct
d=open('../Rich4/rich4.exe','rb').read()
for i in range(13):
    va=0x47fee2+i*8; o=1024+(va-0x401000)
    p=struct.unpack_from('<I',d,o)[0]
    oo=1024+(p-0x401000); e=d.index(b'\0',oo)
    print(i+1, d[oo:e].decode('big5'), struct.unpack_from('<BBBB',d,o+4))
PY

# 效果入口函数表
python3 tools/rich4dis.py info                     # 段信息 + 已知函数指针表

# 单点裁决（等价于 rich4-remake/tools/disasm.py va）
python3 ../rich4-remake/tools/disasm.py va 0x41cdb0 40     # 研究推进循环
python3 ../rich4-remake/tools/disasm.py va 0x41b3e5 5      # 对象类型分派表
python3 ../rich4-remake/tools/disasm.py va 0x4411e5 10     # 项目 = 等级；倒计时 = 5
python3 ../rich4-remake/tools/disasm.py va 0x4475b0 30     # 傳送機设施分支（0x44760f 存在）
python3 ../rich4-remake/tools/disasm.py va 0x40ac7b 60     # 飛彈破坏内核
```

### 9.x 卡片「扣卡时机」的两个专用探针（`tools/scratch/`）

卡片系统有一条**决定复刻实现形态**的机械规则：卡在「目标选定之后、效果之前」
被 `remove_card`（`0x441343`）移除。下面两个脚本把它变成可复跑的核验，
而不是"读一遍汇编得到的印象"：

```bash
.venv/bin/python tools/scratch/consume_probe.py             # 30 张卡：remove_card 与全部分支的相对次序
.venv/bin/python tools/scratch/consume_probe.py 9 16 24     # 只看指定卡号
.venv/bin/python tools/scratch/consume_invariant_check.py   # 不变量：remove_card 之后必返回非 0
```

- `consume_probe.py` 输出每张卡函数里 `call 0x441343` 的**序号**，以及它**之前/之后**
  的所有条件分支与选择器调用（`0x446ae8` / `0x41e6f2` / `0x40d293` / `0x44192a` …）。
  据此把 30 张卡分成五组（甲组「紧跟选框」/ 乙组「成功判定之后」/ 丙组「函数开头」/
  丁组「可送物件判定之后」/ 戊组「选到股之后」），见 `cards.md` §1.6.2。
- `consume_invariant_check.py` 从每个 `remove_card` 之后做前向 DFS，
  核验「**扣卡之后的每一条出口都返回非 0**」（v3.11 实测 **30/30 成立**）。
  两个实现细节必须保留，否则会得到**假反例**：
  ① DFS 要跑在**全部已建图函数**拼成的全局指令表上（30 张卡共用若干条收尾，
  只看本函数体会把「跳进共享尾声」误判成出口）；② 「最近一次写 `eax`」必须
  **沿执行序**携带（共享尾声在更低的 VA，按 VA 大小取会取错），
  且 `ax`/`al`/`ah` **也算写 `eax`**（原版大量用 `xor eax,eax / mov ax,<非零>`）。

`@source` `VA 0x441343`、`VA 0x446ae8`、`VA 0x41e6f2`、`VA 0x40d293`、`VA 0x44192a`。

### 9.y 存档结构的两个探针（`tools/scratch/`）

```bash
.venv/bin/python tools/scratch/snapshot_regions.py     # 10,008 字节快照的 17 处 memcpy 逐区表
.venv/bin/python tools/scratch/player_field_scan.py    # 某个玩家字段（绝对地址形式）的全部读写点
```

- `snapshot_regions.py` 把 `_rich4_store_current_state`（`0x44808a`）与
  `_rich4_restore_last_state`（`0x448544`）里的每次 `memcpy` 摘成
  「目的偏移 / 大小 / 源地址」，两个方向应**完全对称**。
  它是「快照 = 回合开始时的历史状态，无法由当前状态推导」这条结论的来源，
  见 `save-format.md` §五 第 6 条。
- `player_field_scan.py` 回答「这个字节是真状态还是派生量」：
  在全部已建图函数里找 `x.mem_addr` 命中目标地址的指令。
  判据用法：**写者为空的字段只可能来自初始化时的整记录 memcpy**
  （`player+0x04` 就是这样被定性的，见 `save-scalars.md` §2.17）。
  ⚠️ 它只看**绝对地址形式**（`[reg + 0x496bXX]`）；寄存器相对形式
  （`[base + 0x64]`）看不到，须另扫。

---

*本文件所有 A 级结论均已在 `rich4.exe` 上逐字节复核；C 级（未决）条目见 §8，请勿以推测填充。*

### 9.z F 类审计：某结构的每个字段「谁在读」

```bash
cd rich4-remake
python3 tools/scratch/audit-state-fields.py            # GameState/MapObject/FacilityInfo/LandInfo/BlockingDays
python3 tools/scratch/audit-more-fields.py             # SpecialActor/Listing/CommercialOwnership/EventDeck/Stock*
python3 tools/scratch/audit-state-block.py             # 42 块表 vs writeStateBlock 实际写出的偏移
```

库房清单 §四 的 **F 类（状态写了但没人读）** 是最隐蔽的一类缺陷 ——
读实现或跑测试都发现不了，只有**机械对照**才能筛出来。三套脚本各管一段：

- `audit-*-fields.py`：对某接口的每个字段统计「**非写侧**（声明/新建/装载/写档/工厂/协议）
  的引用文件」，一个都没有的就是嫌疑。**已抓到**：`Player.ypos`（→ §7.20 位置三元组）、
  `GameState.viewRotation`（→ §7.24 视角档位没进状态）、
  `SpecialActor.hibernating/sleepwalkDays`（→ §7.25 四个计时字节只走两个）。
- `audit-state-block.py`：把 42 块表与写出器里的**字面偏移**取差集，
  并打印每块落在区间内的写入点。**已抓到**：8 个「状态里有字段却没写」的块 + `0x2747` 写了没声明（→ §7.23）。
- 同一套思路也用在**地图块**上（`map-format.md` 的「写出侧覆盖一览」，→ §7.22）。

`@source` 本节的判据地址（三套脚本都只读这些字节，不推断）：
`VA 0x496b70`（`Player` 位置三元组之一）、`VA 0x499088`（地图视角档位）、
`VA 0x4990e8`/`VA 0x499110`/`VA 0x49911c`/`VA 0x499108`/`VA 0x49908c`（状态块标量）、
`VA 0x498e34` / `VA 0x498e36`（替身四个计时字节的前两格与后两格）。

⚠️ 两个坑：① 路径可能是相对的，`Path(p).relative_to(ROOT)` 前要归一化；
② 助手调用里的字面偏移（`writePlayerBlock(out, state, 0x0010)`）要单独抓，
否则会把玩家块误报成"整块走 carry"。
