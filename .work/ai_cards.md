## AI 用卡决策（《大富翁4》v3.11 / rich4.exe, ImageBase 0x400000）

> 真值：`Rich4/rich4.exe` 字节本身。本文所有 `@source` 后的汇编均为**从 exe 现场线性反汇编得到的原文**，
> 未做助记符/操作数改写；`【推断】`=由字节推出的语义、`【未决】`=静态反汇编无法判定。
> `rich4-re/` 只当导航线索，不作为结论来源。

### 0. 三个必须先纠正的「锚点」

| 常见说法 | 实测 |
|---|---|
| 驱动 `0x441baa` 同时处理卡与道具；手牌 `0x499120` 里卡/道具混放 | **错**。`0x499120` 是**卡**手牌；**道具**是另一份 15 槽数组 `0x49915c`，由另一个驱动 `0x447d97` 处理（§1.4）。两者各有独立的门、决策表、效果表 |
| 道具决策表就是 `0x475324` | 只是同一段数组的**不同基址**：代码里道具门用 `[eax*4 + 0x47539c]`（= `0x475324 + 30*4`），详见 §2.2 |
| `_rich4_get_ai_card_param_value` 在门后面（`0x41e6f6`）就是整函数 | 门是 `0x41e69e`（共 84 字节，止于 `0x41e6f1`）；`0x41e6f2` 才是取值函数（§7） |

---

### 1. 驱动函数 `0x00441baa`

#### 1.1 入口与两条互斥路径

```asm
@source 0x00441bb4  imul  eax, dword ptr [0x49910c], 0x68
@source 0x00441bbb  mov   dl, byte ptr [eax + 0x496b7d]     ; dl = player[+0x15]
@source 0x00441bc1  cmp   dl, 1
@source 0x00441bc4  jne   0x441d00
```
- `player[+0x15] == 1` → 走 `0x441bca`：**人类/可操作玩家的选卡窗口**（建窗 `0x450441`、建控件 `0x451e7e`、`0x451edb` 消息循环、
  `0x4018e7(0x4416f0,…)` 取回调结果放 `ebx`，再 `call dword ptr [eax*4 + 0x475d5c]` 执行）。
- 否则落到 `0x441d00`，即 **AI 路径**：

```asm
@source 0x00441d00  test  dl, 6
@source 0x00441d03  je    0x441e07                       ; 既非 1 也非 2/3 类 → 直接返回
@source 0x00441d09  test  byte ptr [eax + 0x496b7e], 1   ; player[+0x16] bit0 = 「允许用卡」闸
@source 0x00441d10  je    0x441e07
```
`【推断】` `player[+0x15]`：`0`=未参加、`1`=人类、`2/3`=电脑（`& 6` 命中）；`player[+0x16]` 是能力位掩码，bit0=可用卡、bit1=可用道具（道具驱动在 `0x447f87` 检 `test byte ptr [eax + 0x496b7e], 2`）。
`player[+0x17]`=個性，见 §2。

#### 1.2 候选清单的构造（**只收 8 项**）

```asm
@source 0x00441d16  mov   ecx, dword ptr [0x49910c]
@source 0x00441d1d  call  0x441262                      ; count = 手牌非空槽数（15 槽）
@source 0x00441d31  push  8
@source 0x00441d33  push  0
@source 0x00441d35  lea   eax, [esp + 0x98]
@source 0x00441d3d  call  0x456f60                      ; memset(buf@esp+0x90, 0, 8)
@source 0x00441d45  cmp   esi, 8
@source 0x00441d48  jle   0x441d5a
@source 0x00441d4a  call  0x456f2d                      ; rand()
@source 0x00441d54  idiv  esi
@source 0x00441d56  mov   esi, edx                      ; 起点 = rand() % count
@source 0x00441d5a  xor   esi, esi                      ; count<=8 时起点 = 0
```
```asm
@source 0x00441d60  inc   ebx
@source 0x00441d61  cmp   ebx, 8
@source 0x00441d64  jge   0x441d98
@source 0x00441d6e  shl   eax, 2
@source 0x00441d71  add   eax, edx
@source 0x00441d75  shl   eax, 2
@source 0x00441d78  sub   eax, edx                       ; eax = player*15
@source 0x00441d7d  mov   al, byte ptr [edx + eax + 0x499120]
@source 0x00441d84  mov   byte ptr [esp + ebx + 0x90], al
@source 0x00441d8b  cmp   edi, 8
@source 0x00441d8e  jle   0x441d60
@source 0x00441d90  cmp   esi, edi
@source 0x00441d92  jne   0x441d60
@source 0x00441d94  xor   esi, edi                       ; 环形回绕：计到 count 就归零
```
**结论（原文可复核）**
- 源数组：`0x499120 + player*15 + slot`，**15 槽**、`slot∈[0,14]`、`0`=空。
  15 槽这一上界另有两处独立证据：`0x441262` 的 `cmp ecx, 0xf`（`@source 0x0044126f cmp ecx, 0xf`）与 `0x441f21` 的 `@source 0x00441f2e cmp ecx, 0xf`。
- **候选缓冲区固定 8 字节**（`esp+0x90`），循环上界 `cmp ebx, 8`。
- **起点随机**：仅当手牌数 `> 8` 时才 `rand()%count`；否则起点 0。取的是「自起点起、环形推进的 8 项」。
- 手牌是紧凑的（`0x441343` 用 `0x456de8` memmove 收拢、末槽置 0），所以「8 项窗口 + 首个 0 终止」等价于「取 ≤8 张牌」。

#### 1.3 逐项过门 → 命中即执行

```asm
@source 0x00441d98  xor   ebx, ebx
@source 0x00441da2  mov   cl, byte ptr [esp + ebx + 0x90]
@source 0x00441da9  test  cl, cl
@source 0x00441dab  je    0x441e07                       ; 遇到空槽 → 结束（不再往后看）
@source 0x00441db1  push  eax
@source 0x00441db2  call  0x41e69e                       ; ★ 個性闸门（§2）
@source 0x00441dba  cmp   eax, 1
@source 0x00441dbd  jne   0x441d9c                       ; 否决 → 下一项
@source 0x00441dc8  mov   ecx, dword ptr [eax*8 + 0x47fdea]   ; 卡名指针
@source 0x00441dda  call  0x457110                       ; sprintf(名, fmt@0x465305, 卡名)
@source 0x00441def  call  0x441f73                       ; 弹窗（无状态写入）
@source 0x00441df7  xor   eax, eax
@source 0x00441df9  mov   al, byte ptr [esp + ebx + 0x90]
@source 0x00441e00  call  dword ptr [eax*4 + 0x475d5c]    ; ★ 卡片效果函数
```
- **求值顺序**：严格按缓冲区顺序（即上文的环形窗口顺序）；**第一个过门者胜出**，立即执行效果并结束，不做「全部过门再挑一个」。
- **没有「挑哪张牌」的二次选择**；随机性全部来自「起点」与门内的 1/3 掷骰。
- 效果函数返回值语义（供参考）：`0` 表示使用失败/取消（`0x441cd3 push 0 / 0x441cd4 push 0x48233a / 0x441cd9 call 0x4542ce` 提示），
  返回非 0 表示已执行。

#### 1.4 卡 vs 道具：两份独立的 15 槽数组与两台驱动

| | 卡 | 道具 |
|---|---|---|
| 手牌数组 | `0x499120 + player*15 + slot`（15 槽） | `0x49915c + player*15 + slot`（**代码只用 13 槽**，见下） |
| 表 | `0x47fdea`（1..30） | `0x47fee2`（1..13，= 卡表 +30*8） |
| 门 | `0x41e69e` | `0x420e9a` |
| 决策表 | `0x475324`（`+4*id`） | `0x47539c`（`= 0x475324 + 0x78`） |
| 效果表 | `0x475d5c`（`+4*id`） | `0x475dd5`（`call dword ptr [eax*4 + 0x475dd5]`） |
| 参数池 | `0x48be58`（`0x41e6f2`） | `0x48be64`（`0x420eee`） |
| 驱动 | `0x441baa` | `0x447d97` |
| 闸门位 | `player[+0x16] & 1` | `player[+0x16] & 2` |
| 候选窗口 | 8 项（`cmp ebx, 8`） | **4 项**（`@source 0x0044801f cmp ebp, 4`），起点随机仅当候选数 `> 4`（`@source 0x00447ff0 cmp esi, 4`） |
| 额外跳过 | 无 | `@source 0x00447fda cmp eax, 9` / `@source 0x00447fdd je 0x447fab` —— **无条件跳过槽 index 9（道具 10 = 時光機）** |

道具驱动的候选收集（原文）：
```asm
@source 0x00447fcc  mov   eax, dword ptr [esp + 0x48]
@source 0x00447fd0  cmp   byte ptr [ebx + eax + 0x49915c], 0
@source 0x00447fd8  je    0x447fab
@source 0x00447fda  cmp   eax, 9
@source 0x00447fdd  je    0x447fab
@source 0x00447fdf  mov   al, byte ptr [esp + 0x48]
@source 0x00447fe3  inc   al
@source 0x00447fe5  mov   byte ptr [esp + esi + 0x38], al   ; 存 槽号+1 = 道具序号
```
（`ebx = player*15` 由 `@source 0x00447fbe mov ebx, eax` / `0x00447fc0 shl ebx, 2` / `0x00447fc3 add ebx, eax` / `0x00447fc7 shl ebx, 2` / `0x00447fca sub ebx, eax` 构成，即 `p*15`。）

#### 1.5 谁调用驱动、何时调用

```asm
@source 0x00418e13  call  0x4284be          ; 股市 AI
@source 0x00418e18  call  0x456f2d          ; rand()
@source 0x00418e1d  test  al, 1
@source 0x00418e1f  je    0x418e28
@source 0x00418e21  call  0x441baa          ; 50% → 用卡
@source 0x00418e26  jmp   0x418e2d
@source 0x00418e28  call  0x447d97          ; 50% → 用道具
```
`0x441baa` 的直接调用者经全 exe 扫描只有两处：`0x00417de7`（AI 行动路由 `0x417d65` 跳表 `0x417d39` 的 **case 8**）与 `0x00418e21`（上面这个回合步）。
`0x447d97` 的调用者：`0x00417de0`（同跳表 **case 7**）与 `0x00418e28`。

#### 1.6 「谁记下了选中的动作」——**没有全局变量**

- 驱动不写任何「当前使用卡号」全局：`@source 0x00441e00 call dword ptr [eax*4 + 0x475d5c]` 直接把卡号当**表索引**，效果函数从入口参数/静态池 `0x48be58` 取信息。
- 唯一被写入的共享静态是**目标参数池**（§7）与各效果函数自己的落点。
- `0x441f73`（弹窗）经全文检查 `writes` 为空；它只做：按 `action + 0x23a` 建窗、画字、`0x4528b9(0x5dc)` 延时。
  ```asm
  @source 0x00441fad  mov   eax, dword ptr [esp + 0x38]
  @source 0x00441fb1  add   eax, 0x23a
  @source 0x00441fb6  push  eax
  @source 0x00441fbe  call  0x450441
  @source 0x004420a6  push  0x5dc
  @source 0x004420ab  call  0x4528b9
  ```

#### 1.7 题目点名的四个邻近辅助函数

| VA | 语义（证据） |
|---|---|
| `0x441b0a` | **人类玩家手牌格子 UI**。15 项（`@source 0x00441b56 cmp esi, 0xf`），每项 `0x44fabc(窗口, 卡名, x, y, 2)`；x 从 `0x2d` 起步长 `0x50`、到 `0x16d`（5 列），y 从 `0x21` 起步长 `0x38`（3 行）：`@source 0x00441b49 mov ebx, 0x2d` / `@source 0x00441b4e mov edi, 0x21` / `@source 0x00441b95 add ebx, 0x50` / `@source 0x00441b98 cmp ebx, 0x16d` / `@source 0x00441ba5 add edi, 0x38`。卡名取自同表：`@source 0x00441b84 mov edx, dword ptr [eax*8 + 0x47fdea]` |
| `0x441f73` | 用卡**弹窗/动画**，无状态写入（§1.6）。调用者含 `0x441cbc`、`0x441def`、`0x4446de`… |
| `0x441e12` | **按「卡存量」加权随机发一张牌**：把 `0x499198[i]`（i<30，`@source 0x00441e23 cmp eax, 0x1e`）当作重复次数压进栈缓冲（`@source 0x00441e3f mov byte ptr [esp + ebx], al`），再 `@source 0x00441e4a call 0x456f2d` / `@source 0x00441e54 idiv ebx` / `@source 0x00441e56 movzx esi, byte ptr [esp + edx]` / `@source 0x00441e5a inc esi`，最后 `@source 0x00441e64 call 0x4412e4`（add_card）。返回卡号或 0。 |
| `0x441e77` | **随机弃掉手里一张**：`@source 0x00441e80 call 0x441262` 取张数 → `@source 0x00441e8e call 0x456f2d` / `idiv esi` → `@source 0x00441eae mov bl, byte ptr [ebx + eax + 0x499120]` → `@source 0x00441ec1 call 0x441343`（remove_card）。 |
| `0x441ece` | **弃掉一半手牌**：`@source 0x00441ee9 sar eax, 1`（count/2 次），每次 `@source 0x00441efd mov al, byte ptr [ebx + eax + 0x499120]` + `@source 0x00441f0b call 0x441343`；`count<=1` 时返回 0，否则返回 1。`【推断】`因 remove_card 会收拢手牌，实际被弃的是原手牌的偶数位。 |
| `0x441f21` | **清空整手牌并返回总价**：15 槽（`@source 0x00441f2e cmp ecx, 0xf`），每张 `@source 0x00441f54 inc byte ptr [edx + 0x499197]`（把卡退回存量表 `0x499198[卡号-1]`）、`@source 0x00441f5a mov dl, byte ptr [edx*8 + 0x47fdef]`（= 卡表 `+5` 价格）`@source 0x00441f67 add ebx, edx`，最后 `@source 0x00441f6b mov byte ptr [eax + 0x499120], dh` 清槽。 |

---

### 2. 个性闸门 `0x0041e69e`（含原版随机判定）

#### 2.1 卡片门

```asm
@source 0x0041e69e  mov   eax, dword ptr [esp + 4]          ; 卡号
@source 0x0041e6a4  mov   dl, byte ptr [eax*8 + 0x47fdf1]   ; = 卡表[卡号].+7（f7）
@source 0x0041e6ab  imul  eax, dword ptr [0x49910c], 0x68
@source 0x0041e6b2  mov   al, byte ptr [eax + 0x496b7f]     ; player[+0x17] 個性
@source 0x0041e6b8  and   eax, 0xff
@source 0x0041e6bd  sub   edx, eax                          ; d = f7 - 個性
@source 0x0041e6c1  cmp   edx, 2
@source 0x0041e6c4  jl    0x41e6c9
@source 0x0041e6c6  xor   eax, edx                          ; d>=2 → eax=0（恒否决）
@source 0x0041e6c8  ret
@source 0x0041e6c9  cmp   edx, 1
@source 0x0041e6cc  jne   0x41e6e6                          ; d<=0 → 直接派发
@source 0x0041e6ce  call  0x456f2d                          ; d==1 → rand()
@source 0x0041e6d5  mov   ecx, 3
@source 0x0041e6da  sar   edx, 0x1f
@source 0x0041e6dd  idiv  ecx
@source 0x0041e6df  test  edx, edx
@source 0x0041e6e1  je    0x41e6e6                          ; 余数==0 → 派发（1/3）
@source 0x0041e6e3  xor   eax, eax
@source 0x0041e6e5  ret                                             ; 否则否决
@source 0x0041e6e6  mov   eax, dword ptr [esp + 4]
@source 0x0041e6ea  call  dword ptr [eax*4 + 0x475324]      ; 决策跳表
@source 0x0041e6f1  ret
```
**规则**：`d = card_table[card].f7 − player[+0x17]`
- `d >= 2` → **恒返回 0**（绝不主动用），**不消耗随机数**；
- `d == 1` → `rand() % 3 == 0` 才继续（1/3），否则返回 0；
- `d <= 0` → 恒定继续（不掷骰）。

#### 2.2 道具门 `0x00420e9a`（同构，基址不同）

```asm
@source 0x00420ea0  mov   dl, byte ptr [eax*8 + 0x47fee1]   ; 道具表[ord].+7
@source 0x00420eae  mov   al, byte ptr [eax + 0x496b7f]
@source 0x00420eb9  sub   edx, eax
@source 0x00420ebd  cmp   edx, 2
@source 0x00420ec0  jl    0x420ec5
@source 0x00420ec2  xor   eax, edx
@source 0x00420ec4  ret
@source 0x00420eca  call  0x456f2d
@source 0x00420ed1  mov   ecx, 3
@source 0x00420ed9  idiv  ecx
@source 0x00420edb  test  edx, edx
@source 0x00420edd  je    0x420ee2
@source 0x00420edf  xor   eax, eax
@source 0x00420ee1  ret
@source 0x00420ee2  mov   eax, dword ptr [esp + 4]
@source 0x00420ee6  call  dword ptr [eax*4 + 0x47539c]
@source 0x00420eed  ret
```
`0x47539c = 0x475324 + 30*4`，即**同一个 45 项数组**，卡用 `[id]`、道具用 `[30+ord]`。

---

### 3. 行为跳表 `0x00475324` 与卡表 `0x47fdea`（逐项表格）

#### 3.1 表结构（全部实测）

- **卡/道具元数据表**：基址 `0x47fdea`，步长 8，`action` 直接作索引（`action 1` → `0x47fdf2`）。
  字段：`+0` = 名称指针（Big5/cp950 打包串）、`+4` = b4（`0x4071a5` 写入 `0x499198`，`0x441e12` 当重复次数用 → 「存量/权重」）、
  `+5` = **价格**（`0x47fdef + 8*action`，代码按**字节**读：`@source 0x00441f5a mov dl, byte ptr [edx*8 + 0x47fdef]`）、
  `+6` = 未见引用【未决】、`+7` = **f7 個性门槛**（`0x47fdf1 + 8*action`）。
  > 更正：任务书写的「`+4` 处是 price dword」不成立——`+4` 起是 4 个独立字节，价格只是其中第 2 个（`+5`）。
  > 例：均富卡 `+4..+7 = 01 C8 02 02` → b4=1、price=200、+6=2、f7=2。
- **卡片决策跳表** `0x475324`：`[0]=0x180`（哨兵），`[1..30]` 见下表，`[31..44]` 供道具门用，`[44]=0x463d50`（拒绝桩）。
- **卡片效果跳表** `0x475d5c`：`[0]=0`，`[1..30]` 见下表。
- **道具决策跳表** `0x47539c`、**道具效果跳表** `0x475dd5`：见 §3.3。

#### 3.2 逐项表格（action 1..43）

> 「判据摘要」= 返回非 0（决定使用）前测试的条件；`【未决】` 项在 §8 汇总。

| action | 处理函数 VA | 中文名 | f7 | 价格 | 判据摘要 |
|---|---|---|---|---|---|
| 1 | `0x41e6fe` | 均富卡 | 2 | 200 | 全体活跃玩家**平均现金 > 自己现金×10**，且 **price_index×3000 > 自己现金** |
| 2 | `0x41e779` | 均貧卡 | 2 | 200 | 目标须有地权；优先最恨者（其现金 > `price_index×30000` 且 > 自己现金×2），否则按玩家号取第一个（现金 > `price_index×50000` 且 > 自己现金×3）；`aiP0 = 0x8000\|(1<<目标)` |
| 3 | `0x41e9e2` | 購地卡 | 1 | 35 | 脚下地块满足 `0x41e8e6(最恨者, 地块)==1`，且 `price_index×地价 < 自己现金`（住宅价=`[+0x1c]+[+0x1a]×[+0x1e]`，商业=`[+0x22]+[+0x1a]×[+0x24]`） |
| 4 | `0x41eae2` | 換地卡 | 0 | 25 | 先看脚下地块（自有、等级≤1 且同街无同类自有地）；否则遍历全图，在同名街道里挑「地价更高、等级更高」的他人地块且 `0x41e8e6==1`；`aiP0=地块 id` |
| 5 | `0x41e6e3` | 換屋卡 | 0 | 20 | **空桩 `xor eax,eax; ret`**（AI 永不主动用） |
| 6 | `0x41e6e3` | 轉向卡 | 0 | 20 | **空桩** |
| 7 | `0x41ed3e` | 改建卡 | 0 | 15 | 只看**自己脚下**地块。住宅（业主须==自己+1）：`[+0x18]≠0` 时要求存在同名且属自己的另一块 → 用；`[+0x18]==0` 时要求 等级==1，且若 個性≠0 又存在同名**无主**地块则否决（`@source 0x0041ee15 cmp byte ptr [eax + 0x496b7f], 0`）。商业：自有 + `[+0x18]==0` + 等级==1 → `aiP0 = rand()%4+1`（`@source 0x0041eec4 call 0x456f2d`）；他人所有 + `[+0x18]≠0` 且〔等级≥3 或（owner==最恨者+1 且 等级≥2）〕→ `aiP0=0` |
| 8 | `0x41ef26` | 拍賣卡 | 1 | 20 | 脚下地块：他人持有且**等级≥3** → 用；或 **最恨者持有且等级≥2** → 用（不看现金） |
| 9 | `0x41f037` | 天使卡 | 0 | 160 | 自有住宅地块按**街道名**聚类，要求 `[+0x18]==0`、等级<5；某街道合格地块数 **≥3** → `rand()%n` 取一条，`aiP0`=该街首地块 id |
| 10 | `0x41f1b3` | 惡魔卡 | 2 | 180 | 街道级累计：最恨者 `A≥7` 且 `B≥2` 且 自己 `A≤1`；无最恨者时 自己 `A==0` 且 Σ他人`B≥3` 且 Σ他人`A≥9` |
| 11 | `0x41f400` | 怪獸卡 | 2 | 60 | 他人地块中 **等级≥3**（最恨者优先，商业优先于住宅）；无最恨者/其名下无 ≥3 建筑时走全局扫描（住宅门槛升为 **4**） |
| 12 | `0x41f6a9` | 拆除卡 | 1 | 15 | **先 `call 0x41f400` 并复用其 aiP0**；否则：住宅需 `0x41970f(owner)≥4`，商业需 `[+0x18]==3` 且 等级==1，或地图物件类型 ∈{`0x10`,`0x11`} |
| 13 | `0x41f901` | 搶奪卡 | 2 | 25 | 有地权者中：最恨者优先，从其手牌里挑 `f7≥1` 且 **价格最高** 者；否则全局挑 `f7==2` 且价格最高者；`aiP0=0x8000\|(1<<目标)`、`aiP1=卡号` |
| 14 | `0x41facc` | 停留卡 | 0 | 20 | 自己脚下住宅（`价×price_index<现金`、`现金+存款>0x2710`、等级<5…）或商业（`[+0x24]×price_index<现金`、现金>0x2710、`[+0x18]∉{0,3}`）→ `aiP0=0x8000\|(1<<自己)`；否则对「站在自己商业地上」的他人用 |
| 15 | `0x41fe4e` | 冬眠卡 | 2 | 100 | 只有 `rand()%4==0`（25%）才用：`@source 0x0041fe62 test edx, edx` / `@source 0x0041fe64 jne 0x41fe6b` |
| 16 | `0x41fe6f` | 夢遊卡 | 1 | 25 | 有地权、`player[+0x36]==0`、`has_card(p, 18)==0` 的玩家里取最恨者（若在列），否则 `rand()%n` 随机；`aiP0=0x8000\|(1<<p)` |
| 17 | `0x41fe6f` | 陷害卡 | 2 | 20 | 与 16 **共用同一处理函数**，判据完全同上 |
| 18 | `0x41e6e3` | 復仇卡 | 0 | 20 | **空桩**（不可主动使用） |
| 19 | `0x41e6e3` | 嫁禍卡 | 0 | 40 | **空桩** |
| 20 | `0x41e6e3` | 免費卡 | 0 | 25 | **空桩** |
| 21 | `0x41e6e3` | 免罪卡 | 0 | 25 | **空桩** |
| 22 | `0x41ff77` | 送神符 | 0 | 10 | `player[+0x3f]≠0` 时：其指向的地图对象记录 `+0` 类型 ∈{5,6,7,8,`0xa`,`0xf`} → 用；`player[+0x3f]==0` 时：`player[+0x40]≠0` 且该记录的 `+4` 字段 `<0xd` → 用 |
| 23 | `0x41fff8` | 請神符 | 0 | 20 | **已有神明就不用**：`player[+0x3f]∈{1,2,3,4,0xc}` → 直接返回 0（`@source 0x00420010 cmp edx, 1` 系列 `je 0x42002e`，而 `@source 0x0041fff9 xor eax, eax` 使 `eax` 仍为 0）。否则 `eax = 0x444d1a()`，其结果 ∈{1,2,3,4,0xc} → `@source 0x00420047 mov dword ptr [0x48be58], eax` 返回 1 |
| 24 | `0x420055` | 紅卡 | 0 | 50 | `0x428d01()!=1`；在 12 支股票里取 `持仓×价格` **最大**且 `byte[0x496986+i*36]==0`、`0x4295ea(i)!=1` 者；`aiP0=股票下标` |
| 25 | `0x4200ea` | 黑卡 | 1 | 30 | `0x428d01()!=1`；先用 `[0x498e7c+i*0x34+0x18]` 的取值直方图选出值最大的非自己玩家 b（`@source 0x0042013b inc byte ptr [esp + eax - 1]` / `@source 0x00420169 mov edi, ebx`），在 b 的持股里取 `持仓×价格` 最大且 `word[0x496984+i*36]≠0`、`byte[0x496986+i*36]==0`、自己持股==0、`0x4295ea(i)!=3` 者 → `@source 0x004202b9 mov dword ptr [0x48be58], eax`；若一支都没有，改在 `0x40d2d3()`（最恨者）的持股里同样筛选 → `@source 0x004202ad mov dword ptr [0x48be58], ebp`。`aiP0` 始终是**股票下标** |
| 26 | `0x4202d2` | 查稅卡 | 1 | 35 | 有地权者优先最恨者（其现金 **> price_index×30000**），否则任一（现金 **> price_index×50000**）；`aiP0=0x8000\|(1<<目标)` |
| 27 | `0x42040e` | 漲價卡 | 0 | 35 | 自宅所在街道（住宅）：最恨者在该街**没有**地块（`@source 0x00420535 mov dword ptr [esp + 0xc], 1` / `@source 0x0042055b cmp dword ptr [esp + 0xc], 0`）、自有等级和 **≥7**（`@source 0x00420562 cmp dword ptr [esp + 0x24], 7`）、他人等级和 **≤3**（`@source 0x00420569 cmp ebp, 3`）、自有地块占比 **≥0.66**（`@source 0x00420571 fcomp qword ptr [0x463d38]`）；或自有商业地 **等级≥3** 且为同街最高 |
| 28 | `0x42062b` | 查封卡 | 1 | 35 | 沿 `0x40b221(current,6)` 的 6 步路径：住宅街道「同名他人地块等级和 **≥7**」；或商业地属最恨者且 `[+0x18]≠0` 且 **等级≥3** |
| 29 | `0x4207cc` | 同盟卡 | 0 | 40 | 在有地权、非最恨者、未与自己结盟（`player[+0x41]!=自己+1`）的玩家里取 **地产数最多**（住宅+商业地块计数）者；`aiP0=0x8000\|(1<<该玩家)` |
| 30 | `0x420970` | 烏龜卡 | 0 | 70 | 需 `0x40b221(current,3)==0`；路径上无「他人过路费 > price_index×1000」时可对自己用（条件：可购/可升级地总价 **×1.5 < 现金**（double `0x463d40`）、数量≥2、`现金+存款>0x2710`、`word[+0x46]≥0`）；否则改对候选他人（其 3 步路径上自有地产价值 **≥ price_index×10000** 且数量≥2） |
| 31 | `0x420efa` | 機器娃娃 | 0 | 15 | 路径节点上当事人类型 ∈{5,6,7,8} 或 `0xb` → 直接用；类型 `0x11` 需 `owner==自己`；类型 `0x10` 需他人所有且过路费 **> price_index×3000** |
| 32 | `0x42107f` | 路障 | 1 | 30 | 空节点上放置：同街自有地 **≥2** 或该地已有建筑，且 `现金+存款>0x2710`、`word[+0x46]≥0`、`player[+0x39]==0`、`word[地+0x1c]×price_index < 现金`；退化路径取「自有地过路费 > price_index×6000」的最大者 |
| 33 | `0x4213c5` | 地雷 | 1 | 25 | `0x40b343(current,6)` 的 6 步游走格 ∩ `0x409ef9()` 地块表；只收**他人**地产/设施（`@source 0x004214ce cmp byte ptr [eax + 0x19], 0` + `je skip`），特殊节点 `word[0x48bae0]`+`[0x496b30]≠0` 或 `word[0x48bae2]`+`[0x496b60]≠0` 直接选中；`rand()%count` 随机选一，`aiP3=[0x48be64]` 存节点 |
| 34 | `0x421574` | 定時炸彈 | 1 | 25 | 与地雷共用尾部但**不筛归属**：凡「6 步游走 ∩ 地块表」的节点都进候选（`@source 0x00421639 mov word ptr [esp + esi*2], ax`），同样有特殊节点直选（`@source 0x004215ed mov dx, word ptr [0x48bae0]` / `@source 0x0042160f mov ax, word ptr [0x48bae2]`）；`rand()%count` 随机选 |
| 35 | `0x421644` | 機車 | 0 | 80 | `(player[+0x11] & 3)==0`（尚无载具）且 `rand()%4==0`（25%） |
| 36 | `0x421675` | 汽車 | 0 | 150 | `(player[+0x11] & 3)<2`（载具等级<2）且 `rand()%4==0`（25%） |
| 37 | `0x421717` | 飛彈 | 2 | 100 | 目标=`0x40d2d3(self)`，-1 则 `0x40d31c(self)`，仍 -1 → 0；地图 word 需带 `0x8000` 且低 4 位含目标玩家位；再要求以目标为中心半径 `0x64` 的区域内既无 `0x8000` 标记也无**自有**地产 |
| 38 | `0x421827` | 遙控骰子 | 0 | 30 | 前置：`player[+0x3f]∉{7,8,0xf}`、`player[+0x39]==0`、`现金+存款≥0x2710`、`word[+0x46]≥0`、`0x40b221(current,6)==0`；6 个路径节点上选「可买/可升级」：无主地 `现金 > 地价×2.5`（double `0x463d48`），自有地需同街自有≥2、`[+0x18]==0`、等级<5、`现金 > [+0x1e]×2.5` 且取等级最高 |
| 39 | `0x421ba6` | 機器工人 | 0 | 30 | 在可达节点表里找**自有**地产：住宅需 `[+0x18]==0`、等级<5，取 `word[地+等级*2+0x20]` 最大者；商业需 `等级 < byte[类型+0x474940]`，取 `word[设施+等级*2+0x24]` 最大者 |
| 40 | `0x420edf` | 時光機 | 2 | 40 | **`xor eax,eax; ret`**；且道具驱动 `0x447fda`/`0x447fdd` 无条件跳过该槽（双重禁用） |
| 41 | `0x421cb6` | 傳送機 | 1 | 95 | 在可达节点表里找**无主且等级≥3** 的地产（住宅需 `[+0x18]==0`、`价×price_index<现金`；商业需 `[+0x18]≠0`、`[+0x24]×price_index<现金`），取等级最高者；收尾要求 `现金+存款>0x2710` 且 `word[+0x46]≥0` |
| 42 | `0x421e20` | 工程車 | 2 | 150 | `(player[+0x11] & 3) != 3` 且 **`rand()%15 <= player[+0x17]`（個性）**，概率 `(個性+1)/15` |
| 43 | `0x421e62` | 核子飛彈 | 2 | 250 | 候选=全部**他人所有且等级≠0** 的地产；最多抽 **10 次** `rand()%候选数`，对爆风区算「我方等级和/地块数」与「他方等级和/地块数」，**两个比值都 < 1/(存活玩家数+2)** 才用 |

**空桩一览**：action 5、6、18、19、20、21 → `0x41e6e3`（`xor eax,eax; ret`，见 `@source 0x0041e6e3 xor eax, eax` / `@source 0x0041e6e5 ret`）；action 40 → `0x420edf`。

**关键阈值证据（抽样）**
```asm
@source 0x0041e6c1  cmp   edx, 2                     ; 卡门：d>=2 恒否决
@source 0x0041e749  jle   0x41e774                  ; 均富卡：均额<=自己*10 → 否
@source 0x0041e76d  jle   0x41e774                  ; 均富卡：price_index*3000<=现金 → 否
@source 0x0041e841  jge   0x41e873                  ; 均貧卡：price_index*30000>=目标现金 → 否
@source 0x0041e896  imul  eax, dword ptr [0x4990e8], 0xc350   ; 均貧卡回退阈值 = price_index*50000
@source 0x0041fe64  jne   0x41fe6b                  ; 冬眠卡：rand()%4!=0 → 否
@source 0x0041f14e  cmp   word ptr [esp + ecx*8 + 6], 3  ; 天使卡同街计数门槛 3
@source 0x00421e33  cmp   al, 3                     ; 工程車：载具等级==3 → 否
@source 0x00421e54  cmp   edx, esi                  ; 工程車：rand()%15 与 個性 比较
```

#### 3.3 道具决策/效果表（`action 31..43` = ord 1..13）

| ord | action | 决策函数 | 效果函数 | 名称 | f7 | 价 |
|---|---|---|---|---|---|---|
| 1 | 31 | `0x420efa` | `0x446afb` | 機器娃娃 | 0 | 15 |
| 2 | 32 | `0x42107f` | `0x446baa` | 路障 | 1 | 30 |
| 3 | 33 | `0x4213c5` | `0x446c88` | 地雷 | 1 | 25 |
| 4 | 34 | `0x421574` | `0x446d69` | 定時炸彈 | 1 | 25 |
| 5 | 35 | `0x421644` | `0x446e4a` | 機車 | 0 | 80 |
| 6 | 36 | `0x421675` | `0x446f05` | 汽車 | 0 | 150 |
| 7 | 37 | `0x421717` | `0x446fbc` | 飛彈 | 2 | 100 |
| 8 | 38 | `0x421827` | `0x4470f8` | 遙控骰子 | 0 | 30 |
| 9 | 39 | `0x421ba6` | `0x447295` | 機器工人 | 0 | 30 |
| 10 | 40 | `0x420edf`（桩） | `0x447387` | 時光機 | 2 | 40 |
| 11 | 41 | `0x421cb6` | `0x447428` | 傳送機 | 1 | 95 |
| 12 | 42 | `0x421e20` | `0x4479d2` | 工程車 | 2 | 150 |
| 13 | 43 | `0x421e62` | `0x447ace` | 核子飛彈 | 2 | 250 |

`@source 0x00447f51 call dword ptr [eax*4 + 0x475dd5]`（效果派发；`eax` = ord）。
道具**名称**取自 `@source 0x0044804c mov edx, dword ptr [eax*8 + 0x47feda]`（= 道具表 `-8` 基址）。

---

### 4. 关键卡片的判据细节

#### 4.1 均富卡（action 1, handler `0x41e6fe`）

```asm
@source 0x0041e713  cmp   byte ptr [eax + 0x496b7d], 0   ; 只统计 player[+0x15]!=0（在局）
@source 0x0041e71c  add   ecx, dword ptr [eax + 0x496b84] ; 累加 player[+0x1c] 现金
@source 0x0041e72d  idiv  ebx                             ; 平均 = 总额 / 在局人数
@source 0x0041e743  add   eax, edx                        ; 自己现金 ×10（*4,+1,*2）
@source 0x0041e747  cmp   ecx, eax
@source 0x0041e749  jle   0x41e774                        ; 平均 <= 自己×10 → 返回 0
@source 0x0041e767  cmp   eax, dword ptr [ebx + 0x496b84] ; eax = price_index×3000
@source 0x0041e76d  jle   0x41e774                        ; price_index×3000 <= 自己现金 → 返回 0
@source 0x0041e76f  mov   esi, 1
```
判据：**全体在局玩家平均现金 > 自己现金×10** 且 **price_index×3000 > 自己现金**。
`price_index×3000` 的多项式见 `@source 0x0041e74b mov edx, dword ptr [0x4990e8]` 起的 `shl 2 / sub / shl 3 / add / shl 3 / shl 4 / sub`（= `p*(4-1)*8+1)*8 = 200p`，再 `shl 4 = 3200p` 减 200p = **3000p**）。
效果函数 `0x4420d8`：`remove_card(cp,1)` → 台词 → 把每人的现金拉到平均、并按差额 `(现金-均值)/100` 调仇恨（`@source 0x0044217d idiv ecx`，`ecx=0x64`）。

#### 4.2 均貧卡（action 2, handler `0x41e779`）

1. `@source 0x0041e78b push ecx` / `@source 0x0041e78c call 0x40d2d3` → 最恨者 H 存入 `[esp+4]`。
2. 扫全图 word 表，把「有地权」的玩家标进 4 字节标志数组：`@source 0x0041e7c5 test bh, 0x80`（bit15=有主）、`@source 0x0041e7ca test bl, 0xf`（低 4 位=拥有者位掩码）、`@source 0x0041e7fa mov byte ptr [esp + ecx], 1`。
3. 优先分支：H≠-1 且 `[esp+H]!=0`：
```asm
@source 0x0041e839  mov   edx, dword ptr [ecx + 0x496b84]  ; 目标现金
@source 0x0041e83f  cmp   eax, edx
@source 0x0041e841  jge   0x41e873                         ; price_index*30000 >= 目标现金 → 换分支
@source 0x0041e84a  mov   eax, dword ptr [eax + 0x496b84]  ; 自己现金
@source 0x0041e850  add   eax, eax
@source 0x0041e854  jge   0x41e873                         ; 自己×2 >= 目标现金 → 换分支
@source 0x0041e861  or    ah, 0x80                          ; aiP0 = 0x8000|(1<<H)
```
4. 回退分支：按 0..num_players-1 取**第一个**有地权者，要求 `price_index×0xc350(50000) < 其现金` 且 `自己现金×3 < 其现金`（`@source 0x0041e896 imul eax, dword ptr [0x4990e8], 0xc350`、`@source 0x0041e8b5 shl eax, 2` / `@source 0x0041e8b8 sub eax, ecx`）。
5. `aiP0` 与 26（查稅卡）编码相同（`0x8000|1<<玩家`），但 2 多两条「自己比对方穷」的限制。

#### 4.3 購地卡（action 3, handler `0x41e9e2`）+ 辅助 `0x41e8e6`

```asm
@source 0x0041e9f1  mov   bx, word ptr [eax + 0x496b74]      ; 自己当前地图格 +0xc
@source 0x0041ea05  mov   bx, word ptr [ebx + eax*8 + 0x20]  ; map2land[格].+0x20 = 地产 id（步长 0x28）
@source 0x0041ea1b  call  0x41e8e6                          ; (最恨者, 地产 id)
@source 0x0041ea23  cmp   eax, 1
@source 0x0041ea26  jne   0x41eadd                           ; !=1 → 返回 0
@source 0x0041ea75  cmp   edx, dword ptr [eax + 0x496b84]    ; price_index×地价 vs 自己现金
@source 0x0041ea7b  jge   0x41eadd                           ; >= → 返回 0
```
住宅（`0x7d0<id<0xfa0`，记录 `res_land + (id-0x7d0)*0x34`）地价 = `word[+0x1c] + [+0x1a]×word[+0x1e]`；
商业（`0xfa0<id<0x1770`，记录 `com_land + (id-0xfa0)*0x38`）地价 = `word[+0x22] + [+0x1a]×word[+0x24]`。
辅助 `0x41e8e6(player, land_id)`：`@source 0x0041e8f0 cmp dword ptr [esp + 0x14], -1` / `@source 0x0041e8f5 jne 0x41e8fe`（-1 → 0）；
住宅里要求 `@source 0x0041e98c cmp byte ptr [edi + 0x1a], 2` / `@source 0x0041e990 jb 0x41e9db`（等级≥2）且业主 `== player+1`；
另有「同名街道里找到自己持有的另一块」分支（`@source 0x0041e958 call 0x458370`）。`【未决】`：完整语义（同名街道聚合）只能算部分还原。

#### 4.4 拆除卡（action 12）显式复用 怪獸卡（action 11）

```asm
@source 0x0041f6ad  call  0x41f400          ; ★ 直接调用 action 11 的 handler
@source 0x0041f6b2  cmp   eax, 1
@source 0x0041f6b5  je    0x41f8fc          ; 11 决定用 → 12 原样返回 1（连 aiP0 一起复用）
```
若怪獸卡不动手，拆除卡才走自己的三条判据：住宅 `@source 0x0041f744 cmp eax, 4` / `@source 0x0041f747 jl 0x41f8f4`（`0x41970f(owner)>=4`）、
商业 `@source 0x0041f78e cmp byte ptr [eax + 0x18], 3` + `@source 0x0041f798 cmp byte ptr [eax + 0x1a], 1`、
地图物件 `@source 0x0041f7ba test bh, 0x80` + `@source 0x0041f810 cmp byte ptr [edx + 0x496d08], 0x10` / `@source 0x0041f884 cmp byte ptr [edx + 0x496d08], 0x11`。
**复刻注意**：这个 `call 0x41f400` 是文本级的复用，两卡共享一次目标选择，不要各写一套。

#### 4.5 核子飛彈（action 43, handler `0x421e62`）

- 候选 = 他人所有且等级≠0 的地产（`@source 0x00421eb4 cmp byte ptr [eax + 0x1a], 0` / `je skip`；`@source 0x00421e9e mov dl, byte ptr [eax + 0x19]` 业主）。
- 最多抽 10 次：`@source 0x0042216f call 0x456f2d` / `@source 0x00422179 idiv dword ptr [esp + 0x41c]`。
- 阈值：`@source 0x004220ee add eax, 2`（存活玩家数+2）→ `@source 0x00422101 fdivrp st(1)` → 两条 `@source 0x00422125 jae 0x422151` 与 `@source 0x00422138 jae 0x422151`（两个比值都必须 **小于** 阈值才通过）。
- `@source 0x00422141 mov dword ptr [0x48be64], eax`（`aiP3`）。
- `【未决】` `@source 0x00422026 cmp dword ptr [esp + 0x42c], 1` 读的槽首次写入在累加循环**之后**，疑为原版栈残留；需差分验证。

#### 4.6 時光機（action 40）：门与驱动双重禁用

```asm
@source 0x00420edf  xor   eax, eax
@source 0x00420ee1  ret
@source 0x00447fda  cmp   eax, 9          ; 槽索引 9 == 道具 10 == 時光機
@source 0x00447fdd  je    0x447fab        ; 连门都不送
```
人类玩家仍可使用（效果函数 `0x447387` 存在），AI 永不。
另：道具决策表条目 `0x47539c + 4*10 = 0x4753c4` 读出的也正是 `0x420edf`（与 §3.3 表一致）。

---

### 5. `_rich4_find_most_hostile_player` 精确算法

**存在，VA = `0x0040d2d3`**。判据：全文扫描 `call 0x40d2d3` 共 17 处（`0x41e78c, 0x41ea11, 0x41eb1e, 0x41ed6d, 0x41ef59, 0x41f1d8, 0x41f424, 0x41f919, 0x41fe9b, 0x42020b, 0x4202e5, 0x420424, 0x420652, 0x4207f4, 0x42172a, 0x4448b1, 0x44f4f7`）；
读 `0x496bb4` 的函数只有 `0x40d2d3`（读）与 `0x40df69`（update_hostility）/`0x40cd87`（清零），故这是唯一的「找最恨者」实现。

```asm
@source 0x0040d2d3  push     ebx
@source 0x0040d2d4  push     esi
@source 0x0040d2d5  push     edi
@source 0x0040d2d6  mov      esi, dword ptr [esp + 0x10]     ; esi = self
@source 0x0040d2da  xor      eax, eax                        ; i = 0
@source 0x0040d2dc  xor      ecx, ecx                        ; best = 0
@source 0x0040d2de  mov      edi, 0xffffffff                 ; bestIdx = -1
@source 0x0040d2e3  cmp      eax, dword ptr [0x499114]       ; i < num_players
@source 0x0040d2e9  jge      0x40d316
@source 0x0040d2eb  cmp      eax, esi
@source 0x0040d2ed  je       0x40d313                        ; ★ 排除自己
@source 0x0040d2ef  imul     edx, eax, 0x68
@source 0x0040d2f2  cmp      byte ptr [edx + 0x496b7d], 0    ; ★ 排除出局/未参加
@source 0x0040d2f9  je       0x40d313
@source 0x0040d2fb  imul     edx, esi, 0x68
@source 0x0040d2fe  mov      ebx, eax
@source 0x0040d300  shl      ebx, 2
@source 0x0040d303  add      edx, ebx
@source 0x0040d305  mov      ebx, dword ptr [edx + 0x496bb4] ; h = player[self].hostility[i]
@source 0x0040d30b  cmp      ecx, ebx                        ; best vs h
@source 0x0040d30d  jge      0x40d313                        ; ★★ 只在严格大于时更新
@source 0x0040d30f  mov      ecx, ebx
@source 0x0040d311  mov      edi, eax
@source 0x0040d313  inc      eax
@source 0x0040d314  jmp      0x40d2e3
@source 0x0040d316  mov      eax, edi
@source 0x0040d318  pop      edi
@source 0x0040d319  pop      esi
@source 0x0040d31a  pop      ebx
@source 0x0040d31b  ret
```

| 项 | 结论（均有上列原文） |
|---|---|
| 循环上界 | `i < [0x499114]`（**不是固定 4**） |
| 扫的数组 | `player[self].hostility[i]` = `0x496bb4 + self*0x68 + i*4`，即「**自己**对他人的敌意」 |
| 是否排除自己 | **排除**（`cmp eax, esi` / `je`） |
| 其他过滤 | 排除 `player[i][+0x15] == 0` |
| best 初值 | `0`；bestIdx 初值 `-1` |
| **tie-break** | **first-wins（下标小者胜）**：`cmp ecx, ebx` + **`jge`** 表示只有 `h > best` 才更新，相等时保留先命中的小下标 |
| 无候选 | 全 0 时 `0 >= 0` 恒真 → bestIdx 保持 `-1`，返回 **-1** |

相关但**不同**的函数：`0x40d31c`（随机取一个在局他人，`0x40d355 call 0x456f2d` / `idiv esi`），`0x40d2b4`（数 `player[+0x15]!=0` 的玩家数）。

---

### 6. 随机数调用点清单

`0x456f2d` = `_libc_rand`（LCG，返回 0..0x7fff）。下面按「卡路径」列出；`作用` 一栏标注**阈值门**（掷骰决定做/不做）还是**选择**（掷骰选目标）。

#### 6.1 门与驱动

| VA | 随机用法 | 阈值 | 作用 |
|---|---|---|---|
| `0x41e6ce` | `rand()` → `idiv 3` | 仅当 `f7-個性 == 1`；`%3==0` 通过 | **卡片门阈值门**（`@source 0x0041e6dd idiv ecx`，`ecx=3`） |
| `0x420eca` | `rand()` → `idiv 3` | 仅当 `f7-個性 == 1`；`%3==0` 通过 | **道具门阈值门**（`@source 0x00420ed9 idiv ecx`） |
| `0x441d4a` | `rand() % 手牌数` | 仅当手牌数 **> 8**（`@source 0x00441d45 cmp esi, 8`） | **卡片驱动起点选择**（`@source 0x00441d54 idiv esi`） |
| `0x447ff5` | `rand() % 道具候选数` | 仅当候选数 **> 4**（`@source 0x00447ff0 cmp esi, 4`） | **道具驱动起点选择** |
| `0x418e18` | `rand() & 1`（`@source 0x00418e1d test al, 1`） | 50/50 | **回合内二选一**：1=用卡驱动 `0x441baa`，0=用道具驱动 `0x447d97` |

#### 6.2 决策处理函数

| VA | 所属 action | 随机用法 | 阈值 | 作用 |
|---|---|---|---|---|
| `0x41eec4` | 7 改建卡 | `rand()%4` + 1（`@source 0x0041eecb mov ebx, 4` / `@source 0x0041eed3 idiv ebx` / `@source 0x0041eed5 inc edx`） | — | **选择**：`aiP0 = 1..4`（`@source 0x0041eed6 mov dword ptr [0x48be58], edx`） |
| `0x41f172` | 9 天使卡 | `rand()%候选街道数`（`@source 0x0041f17c idiv esi`） | — | **选择**：取一条合格街道，`aiP0` = 其首地块 id |
| `0x41fe51` | 15 冬眠卡 | `rand()%4`（`@source 0x0041fe58 mov ecx, 4`） | `%4==0`（25%） | **阈值门**：`@source 0x0041fe62 test edx, edx` / `@source 0x0041fe64 jne 0x41fe6b` |
| `0x41ff48` | 16/17 夢遊卡/陷害卡 | `rand()%候选数`（`@source 0x0041ff52 idiv esi`） | 仅当最恨者不在候选列 | **选择**：随机挑一个有地权玩家，`aiP0 = 0x8000\|1<<p`（`@source 0x0041ff5e or ah, 0x80`） |
| `0x420eca` | 道具门 | 见 6.1 | — | — |
| `0x42153e` | 33 地雷 / 34 定時炸彈 | `rand()%候选数`（`@source 0x00421548 idiv esi`） | — | **选择**：取目标节点，`@source 0x00421553 mov dword ptr [0x48be64], eax` |
| `0x421657` | 35 機車 | `rand()%4` | `%4==0` | **阈值门**：`@source 0x0042166a jne 0x421671` |
| `0x42168d` | 36 汽車 | `rand()%4` | `%4==0` | **阈值门**：`@source 0x004216a0 jne 0x4216a7` |
| `0x421e43` | 42 工程車 | `rand()%15`（`@source 0x00421e4a mov ecx, 0xf`） | `%15 <= player[+0x17]` | **阈值门**：`@source 0x00421e54 cmp edx, esi` / `@source 0x00421e56 jg 0x421e5d` |
| `0x42216f` | 43 核子飛彈 | `rand()%候选数`，最多 **10** 次（`@source 0x00422160 cmp ecx, 0xa`） | — | **选择**：抽样候选地块（`@source 0x00422179 idiv dword ptr [esp + 0x41c]`） |

#### 6.3 辅助/效果函数（仍在用卡链上）

| VA | 所属 | 随机用法 | 作用 |
|---|---|---|---|
| `0x441e4a` | `0x441e12` 发牌 | `rand()%总权重`（`@source 0x00441e54 idiv ebx`） | **选择**：按 `0x499198[]` 存量加权随机取一张牌 |
| `0x441e8e` | `0x441e77` 弃牌 | `rand()%手牌数`（`@source 0x00441e98 idiv esi`） | **选择**：随机弃一张 |
| `0x4448fc` | action 17 效果 | `rand()%0xfa0` + `0xfa0`（`@source 0x00444903 mov esi, 0xfa0`） | **选择**：结算金额，再乘 price_index |
| `0x444a9b` | action 17 效果 | `rand()%0xbb8` + `0xbb8`（`@source 0x00444aa2 mov esi, 0xbb8`） | 同上 |
| `0x445b12` | action 30 效果 | 加权随机（`@source 0x00445b1c idiv ebx`） | **选择** |
| `0x40b2f2` | `0x40b221`/`0x40b343` 路径游走 | `rand()%候选邻格数`（`@source 0x0040b2fc idiv ebx`） | **选择**：逐跳随机游走，写 `0x48b8b4`（被 28/30/32/33/34/37/38 使用） |

**对复刻最要紧的一条**：门的随机只在 `f7-個性 == 1` 时发生（`rand()%3==0` 的 1/3 通过）；
`>=2` 时**根本不推进 LCG**（恒定否决），`<=0` 时恒定通过。

---

### 7. `_rich4_get_ai_card_param_value`

**VA = `0x0041e6f2`**（整函数 3 条指令，止于 `0x41e6fd`；它紧接在卡片门 `0x41e69e` 之后）：

```asm
@source 0x0041e6f2  mov   eax, dword ptr [esp + 4]
@source 0x0041e6f6  mov   eax, dword ptr [eax*4 + 0x48be58]
@source 0x0041e6fd  ret
```

- **它索引的不是「按卡号的表」，而是一个静态暂存池**：基址 `0x48be58`，步长 4，索引是调用者自己选的**槽号**（不是卡号）。
- 实测调用点（卡效果函数）全部传 `0`（唯一例外是 `@source 0x00443b34 push edi`，而 `edi` 在该函数里 `@source 0x00443b16 xor edi, edi` 恒为 0）：
  `0x4421d6, 0x442693, 0x4428da, 0x442b79, 0x442d8f, 0x442f6f, 0x4431dc, 0x4434ea, 0x443702, 0x443939, 0x443b35, 0x443e5e, 0x443fa2, 0x4441fe, 0x4444e1, 0x444e37, 0x444f75, 0x4450e4, 0x445218, 0x44544f, 0x4455b5, 0x445735, 0x445901`。
- 因此**实际被读的只有 `0x48be58`**；`0x48be5c` 被 `0x44192a` 用 `push 1` 读（= `0x48be5c`，`搶奪卡` 选中的「要抢的卡号」，写入点 `@source 0x0041fa19 mov dword ptr [0x48be5c], edx`）。
- **道具孪生体** `_rich4_get_ai_tool_param_value` = `0x00420eee`，基址 `0x48be64`：
  ```asm
  @source 0x00420eee  mov   eax, dword ptr [esp + 4]
  @source 0x00420ef2  mov   eax, dword ptr [eax*4 + 0x48be64]
  @source 0x00420ef9  ret
  ```
  8 个调用点全部传 `0`：`0x446bef, 0x446cd0, 0x446db1, 0x447009, 0x447252, 0x4472e0, 0x447661, 0x447b1b`。
- **池的边界与初值**：`0x48be58` 落在 PE 段 `.bss` 内（段表：`VA=0x48a000, RawSize=0xfc00, PointerToRawData=0`）。
  写入点覆盖 `0x48be58`（卡主参数）、`0x48be5c`（卡副参数）、`0x48be60`（决策函数内部循环暂存）、`0x48be64`（道具主参数，**与卡的槽 3 重叠**）。
  `【未决】`：`.bss` 段头 `RawSize≠0 且 RawOff=0`，镜像会把文件偏移 0 起 0xfc00 字节复制到 `0x48a000`，故「加载初值是否为 0」未定；
  但所有读取点都在同一轮的写入点之后，**初值不影响 AI 行为**。

---

### 汇编摘录

```asm
; ── AI 路径开关与候选窗口（0x441baa）─────────────────────────────
@source 0x00441bb4  imul  eax, dword ptr [0x49910c], 0x68
@source 0x00441bbb  mov   dl, byte ptr [eax + 0x496b7d]
@source 0x00441bc1  cmp   dl, 1
@source 0x00441bc4  jne   0x441d00
@source 0x00441d00  test  dl, 6
@source 0x00441d03  je    0x441e07
@source 0x00441d09  test  byte ptr [eax + 0x496b7e], 1
@source 0x00441d10  je    0x441e07
@source 0x00441d1d  call  0x441262
@source 0x00441d3d  call  0x456f60
@source 0x00441d45  cmp   esi, 8
@source 0x00441d4a  call  0x456f2d
@source 0x00441d54  idiv  esi
@source 0x00441d56  mov   esi, edx
@source 0x00441d61  cmp   ebx, 8
@source 0x00441d78  sub   eax, edx
@source 0x00441d7d  mov   al, byte ptr [edx + eax + 0x499120]
@source 0x00441d84  mov   byte ptr [esp + ebx + 0x90], al
@source 0x00441da9  test  cl, cl
@source 0x00441dab  je    0x441e07
@source 0x00441db2  call  0x41e69e
@source 0x00441dba  cmp   eax, 1
@source 0x00441dbd  jne   0x441d9c
@source 0x00441dc8  mov   ecx, dword ptr [eax*8 + 0x47fdea]
@source 0x00441dda  call  0x457110
@source 0x00441def  call  0x441f73
@source 0x00441e00  call  dword ptr [eax*4 + 0x475d5c]

; ── 個性闸门（0x41e69e）─────────────────────────────────────────
@source 0x0041e6a4  mov   dl, byte ptr [eax*8 + 0x47fdf1]
@source 0x0041e6ab  imul  eax, dword ptr [0x49910c], 0x68
@source 0x0041e6b2  mov   al, byte ptr [eax + 0x496b7f]
@source 0x0041e6bd  sub   edx, eax
@source 0x0041e6c1  cmp   edx, 2
@source 0x0041e6c4  jl    0x41e6c9
@source 0x0041e6c6  xor   eax, edx
@source 0x0041e6c9  cmp   edx, 1
@source 0x0041e6cc  jne   0x41e6e6
@source 0x0041e6ce  call  0x456f2d
@source 0x0041e6d5  mov   ecx, 3
@source 0x0041e6dd  idiv  ecx
@source 0x0041e6e1  je    0x41e6e6
@source 0x0041e6e3  xor   eax, eax
@source 0x0041e6ea  call  dword ptr [eax*4 + 0x475324]

; ── 卡/道具两表基址（同一数组的两个偏移）────────────────────────
@source 0x0041e6a4  mov   dl, byte ptr [eax*8 + 0x47fdf1]   ; 卡表 f7
@source 0x00420ea0  mov   dl, byte ptr [eax*8 + 0x47fee1]   ; 道具表 f7
@source 0x0041e6ea  call  dword ptr [eax*4 + 0x475324]      ; 卡决策
@source 0x00420ee6  call  dword ptr [eax*4 + 0x47539c]      ; 道具决策
@source 0x00441e00  call  dword ptr [eax*4 + 0x475d5c]      ; 卡效果
@source 0x00447f51  call  dword ptr [eax*4 + 0x475dd5]      ; 道具效果
@source 0x00441e5a  inc   esi
@source 0x00441f5a  mov   dl, byte ptr [edx*8 + 0x47fdef]   ; 价格 = 表项 +5

; ── 卡/道具数组（15 槽 × 玩家）──────────────────────────────────
@source 0x00441d7d  mov   al, byte ptr [edx + eax + 0x499120]  ; 卡手牌
@source 0x00447fd0  cmp   byte ptr [ebx + eax + 0x49915c], 0  ; 道具手牌
@source 0x0044126f  cmp   ecx, 0xf                            ; 15 槽上界

; ── 最恨者（0x40d2d3）tie-break = jge（first-wins）─────────────
@source 0x0040d2d6  mov   esi, dword ptr [esp + 0x10]
@source 0x0040d2dc  xor   ecx, ecx
@source 0x0040d2de  mov   edi, 0xffffffff
@source 0x0040d2ed  je    0x40d313
@source 0x0040d2f9  je    0x40d313
@source 0x0040d305  mov   ebx, dword ptr [edx + 0x496bb4]
@source 0x0040d30b  cmp   ecx, ebx
@source 0x0040d30d  jge   0x40d313
@source 0x0040d311  mov   edi, eax
@source 0x0040d316  mov   eax, edi

; ── 参数池取值（0x41e6f2 / 0x420eee）────────────────────────────
@source 0x0041e6f2  mov   eax, dword ptr [esp + 4]
@source 0x0041e6f6  mov   eax, dword ptr [eax*4 + 0x48be58]
@source 0x0041e6fd  ret
@source 0x00420eee  mov   eax, dword ptr [esp + 4]
@source 0x00420ef2  mov   eax, dword ptr [eax*4 + 0x48be64]
@source 0x00420ef9  ret

; ── 回合内 50/50（0x418e18）─────────────────────────────────────
@source 0x00418e18  call  0x456f2d
@source 0x00418e1d  test  al, 1
@source 0x00418e1f  je    0x418e28
@source 0x00418e21  call  0x441baa
@source 0x00418e28  call  0x447d97

; ── 拆除卡复用怪獸卡（0x41f6ad）─────────────────────────────────
@source 0x0041f6ad  call  0x41f400
@source 0x0041f6b2  cmp   eax, 1
@source 0x0041f6b5  je    0x41f8fc

; ── 冬眠卡 25%（0x41fe51）与 工程車 (個性+1)/15（0x421e43）───────
@source 0x0041fe51  call  0x456f2d
@source 0x0041fe58  mov   ecx, 4
@source 0x0041fe60  idiv  ecx
@source 0x0041fe62  test  edx, edx
@source 0x0041fe64  jne   0x41fe6b
@source 0x00421e3c  movzx esi, byte ptr [edx + 0x496b7f]
@source 0x00421e43  call  0x456f2d
@source 0x00421e4a  mov   ecx, 0xf
@source 0x00421e52  idiv  ecx
@source 0x00421e54  cmp   edx, esi
@source 0x00421e56  jg    0x421e5d
```

---

### 未决

1. **`player[+0x17]`（個性）的取值域与名称**：门公式已定死（`f7 − 個性`），但「0/1/2 分别叫什么」是文档约定，不是 exe 里的字符串。
2. **表格 `+6` 字节（`0x47fdf0 + 8*action`）**：全文找不到引用。
3. **`player[+0x16]` 位掩码其余位**：只证实 bit0=用卡、bit1=用道具；其余位未查。
4. **`player[+0x11]`（载具等级？）、`[+0x36]`、`[+0x39]`、`[+0x3f]`、`[+0x40]`、`[+0x41]`、`[+0x46]`**：多处作为硬门槛使用，但字段语义未定位到赋值点。
5. **住宅/商业记录字段**：`+0x18`、`+0x1a`（当作「等级」用）、`+0x1c/+0x1e`（住宅两个价）、`+0x22/+0x24`（商业两个价）哪个是地价、哪个是建筑价值未定；
   且 `0x498e7c` 那张表把「业主」放在 `+0x18`，与 res/com 的 `+0x19` 不一致。
6. **`0x496d08` 表**（步长 24，`+0`=类型、`+2`=地图格、`+4` 另一字段）：类型码 `{5,6,7,8,0xa,0xb,0x10,0x11,0x12}` 的含义未定（22/31/32/38 都用它）。
7. **核子飛彈 `[esp+0x42c]` 读栈残留**（§4.5）：原版 bug 还是我方读法问题，需 Unicorn 差分。
8. **`0x40b221` / `0x40b343` 的返回值语义**：只知道末尾 `mov eax,[esp+8]` 在 `0x40b309` 被置 1，代表「某步候选≥2 走了随机」；对 30/32/38 的门控含义未定。
9. **`0x428d01`（紅卡/黑卡前置）与 `0x4295ea`（股票判定）**：只知返回码比较，语义未定；因此 24/25 的判据摘要写成「返回码 ≠ 1 / ≠ 3」而不是白话。
10. **均貧卡/查稅卡为何阈值相同却分属两卡**：`aiP0` 编码一致，差异只在「自己是否更穷」的两条附加比较；是否有意为之未决。
