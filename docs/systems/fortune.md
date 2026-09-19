# 命运事件（fortune events，37 项）

> 真值：`../../../Rich4/rich4.exe`（v3.11，ImageBase 0x400000）。
> 本文件所有 `@source` 均为**原版虚拟地址（VA）**，全部结论来自对 exe 的实际反汇编。
> 不使用 `rich4-re/csrc/fortune.c`（2018 旧版）作为依据；仅在与它冲突处引用它以便记录差异。

## 本文件的验证方式与证据级别

| 级别 | 含义 | 本文件中的用法 |
|---|---|---|
| **A-反汇编** | 用 `capstone` 从 `rich4.exe` 实际反汇编得到，指令与二进制逐字节对应 | **本文件全部逐事件结论**。按 `fortune_call_table` 的地址序确定每个处理函数的边界（末项上界 `0x44d959`），再逐条反汇编 |
| **A-数据** | 直接读 exe 数据段的字节 | 分派表 `0x475ef0`、图片索引表 `0x475fb4`、字符串字面量、x87 常量 |
| **B** | `rich4-re/asm/rich4_fortune.asm`（2026 人工还原）、`rich4-re/csrc/fortune.c`（2018） | 仅用于登记差异（见 §6） |
| **C** | 其它人工笔记 | 不作依据 |

覆盖率：**37/37 项**。判读约定同 `news.md`：`p` = `price_index`（`0x4990e8`）。

---

## 一、触发接线：命运在回合流程的哪一步被调用

### 1.1 分派表与入口

| 对象 | VA | 说明 |
|---|---|---|
| `fortune_call_table[37]` | `0x475ef0` | 37 项函数指针，地址序排列（已核对相邻项） |
| `fortune_events()` | `0x44db81` | 命运事件总入口 |
| 可行性判定 `fortune_check(int *v)` | `0x44bb4b` | 返回 1/0，**并且可能改写 `*v`**（见 §1.3） |
| 顺序表初始化 | `0x44baea` | 生成 `0..36` 的随机排列写入 `0x496b38`，并把 `0x4990b4` 清零（**算法与消耗次数已通道 2 实证**，见 §1.5）|
| 顺序表 | `0x496b38`（`uint8[37]`，`.bss`，文件中无初值） | `fortune_order[]`（长度 `0x25 = 37`，与 `global_vars.txt` 的 `0x496b38, 0x25` 一致） |
| 游标 | `0x4990b4`（dword） | `fortune_cur_idx`，0..36 循环 |
| 图片索引表 | `0x475fb4`（`uint16[49]`，`0x475fb4..0x476015`） | 事件 → `mkf_data` 图片号 |
| 地图/关卡选择 | `0x4991b8`（`word`） | `≥33` 的事件用它选第二套表块（见 §1.4，**该分支未决**） |
| 阶段开关 | `0x4991b6`（`word`） | 事件 33..36 的可行性开关（见 §2.1） |

#### 1.5 ★★ 洗牌算法（`0x44baea` / 新聞的 `0x448b81`）—— 2026 本轮通道 2 实证（19/19）

两副牌（命運 37 / 新聞 36）**共用同一段代码**，只差长度与落点：

```asm
; @source 0x44baea（命運；新聞 = 0x448b81，0x25→0x24、0x496b38→0x499090、0x4990b4→0x4990e0）
0044baef  push 0x25 / push 0 / lea eax,[esp+8] / push eax / call 0x456f60  ; used[37] = {0}（**局部**）
0044bb00  ebx = 0（已放张数）  esi = 0x25（剩余数）
loop:
0044bb1a  call 0x456f2d                 ; rand()
0044bb1f  mov edx,eax / sar edx,0x1f / idiv esi
                                        ; ★★ 用的是 **edx = 余数** ⇒ k = rand() % 剩余数
0044bb26  eax = 0                       ; at = 0
scan:
0044bb30  if (used[at] == 0) k--         ; 只对**未用过**的槽计数
0044bb37  if (k < 0) goto adopt
0044bb3a  at++（≥0x25 也落进 adopt —— 防御性边界，正常不可达）
adopt:
0044bb09  used[at] = 1
0044bb0d  deck[ebx] = at                 ; = 事件号（0..36）
0044bb13  ebx++ / esi--
0044bb3d  [0x4990b4] = 0                 ; 游标清零
```

⇒ 这是「**选择采样**」而非 Fisher-Yates：每轮取 `k = rand() % 剩余数`，
再从头扫过 `used[]`，落在第 (k+1) 个未使用槽上。

| 事实（通道 2 钉住） | 值 |
|---|---|
| `rand()` 消耗次数 | **恰好 = 牌堆张数**（37 / 36，每轮一次）|
| 全 0 序列 | 排列退化成 `[0,1,2,…]`（每轮 k=0 ⇒ 取第一个未用槽）|
| 恒定 32767 序列 | `k = 32767 % 剩余数`（**余数随剩余数变**，故不是同一个 k）|
| 给定序列下的排列 | 与模型逐项相同（`tests/test_deck_shuffle.py` 里两条固定序列）|
| 游标 | 洗牌末尾清零（`0x44bb3f` / `0x448bd6`）|
| 越界 | 前后哨兵未被动 ⇒ 数组写严格限制在 `[0x496b38, +37)`（`used[]` 是**栈上局部**，与 deck 无关）|

⇒ 复刻侧 `packages/core/src/events/deck.ts` 的 `shuffleDeck()` 同一算法，
并在 `deck.test.ts` 里用**同两条固定序列**（`below(n) := SEQ[i] % n`）钉出**同一个排列** ⇒
「复刻的洗牌 == 原版洗牌」这一步现在是**可判定**的（不再是「都是排列」这种弱性质）。
（用户的随机数口径仍是不要求位级一致；这里能对上是因为**算法本身**照抄了。）

`0x475fb4` 的实际内容（`@source VA 0x00475fb4`，49 项 uint16）：

```
[ 0..19] 0x01dd 0x01de 0x01df 0x01e0 0x01e1 0x01e2 0x01e3 0x01e4
        0x01e5 0x01e6 0x01e7 0x01e8 0x01e9 0x01ea 0x01eb 0x01ec
        0x01ed 0x01ee 0x01ef 0x01f0
[20..36] 0x01f1 0x01f1 0x01f1 0x01f2 0x01f2 0x01f3 0x01f4 0x01f5
        0x01f5 0x01f5 0x01f6 0x01f7 0x01f8 0x01f9 0x01fa 0x01fb
        0x01fc
[37..48] 0x01f9 0x01fd 0x01fe 0x01ff 0x0200 0x01fa 0x01fb 0x0201
        0x0202 0x0203 0x01fe 0x0204
[49..57] 全 0（表中止于此；再往后 0x476016 起是别的数据）
```

* 索引 0..36 是 37 个事件的图片号，37..48 是「第二套块」（`0x4991b8 != 0` 时用）用到的 12 个槽位。
* 表项值与 `csrc/fortune.c` 的 `fortune_data_idx[49]` **逐项一致**（本轮已比对，见 §6）。

### 1.2 调用点

与新闻**共用同一个节点类型跳表**（详见 `news.md` §1.2）：

```asm
0041985b  mov   ebx, dword ptr [eax + 0x24]      ; node+0x24 : 格子类型
004198a9  cmp   ebx, 0x10 / ja 0x41b3d0
004198b2  jmp   dword ptr [ebx*4 + 0x4197e9]     ; 17 项跳表
0041b128  call  0x44db81                         ; ★ type == 3 → 命运事件
```

调用链同上：

```
0x418d88 / 0x40d889 → 0x418e7f（移动结束判定）→ 0x41982d(player.node_id)
   → type==3 → 0x44db81  fortune_events
```

**第二个调用点（魔法屋）**：`@source VA 0x00431dbc`

```asm
00431db7  add   esp, 8
00431dba  xor   ebx, ebx
00431dbc  call  0x44db81          ; ★ 连续调用命运事件
00431dc1  inc   ebx
00431dc2  cmp   ebx, 3
00431dc5  jl    0x431dbc          ; for (i=0;i<3;i++) fortune_events();
```

即魔法屋的某个效果分支会**连续抽 3 次命运事件**。该分支所属的魔法屋效果编号未逐一追到底（见 §5 未决），
但「连续 3 次」这一事实由 `0x431dba..0x431dc5` 的循环直接给出。

### 1.3 `fortune_events()` 的两次调用语义（`@source VA 0x0044db81`）

```asm
0044dbba  mov   esi, dword ptr [0x4990b4]        ; fortune_cur_idx
0044dbc0  xor   eax, eax
0044dbc2  mov   al, byte ptr [esi + 0x496b38]    ; ★ v = fortune_order[fortune_cur_idx]
0044dbc8  mov   dword ptr [esp + 0x10], eax
0044dbcc  lea   eax, [esp + 0x10]
0044dbd0  push  eax
0044dbd1  call  0x44bb4b                         ; ★ fortune_check(&v) —— 可能改写 v
0044dbd6  mov   esi, eax / mov edi, eax           ; 可行性结果
0044dbf5  cmp   esi, 1
0044dbf8  jne   0x44dcaa                         ; 不可行 → 只推进游标
0044dbfe  mov   ebp, dword ptr [esp + 0x10]      ; ★ v（可能已被重映射）
0044dc02  lea   eax, [ebp + ebp]
0044dc06  cmp   ebp, 0x21                        ; v < 33 ?
0044dc09  jge   0x44dc4d
0044dc11  movsx eax, word ptr [eax + 0x475fb4]   ; ★ 图片号 = u16[0x475fb4 + v*2]
0044dc20  call  0x450441                         ; read_mkf(mkf_data, 图片号, ...)
0044dc36  call  0x456280                         ; draw_graph
0044dc44  call  dword ptr [eax*4 + 0x475ef0]     ; ★★ 处理函数(v, 0) —— pass 0
0044dcaa  mov   esi, dword ptr [0x4990b4]
0044dcb0  inc   esi
0044dcb1  mov   dword ptr [0x4990b4], esi
0044dcb7  cmp   esi, 0x25                        ; 37 回绕
0044dcba  jne   0x44dcc4
0044dcbc  xor   edx, edx / mov dword ptr [0x4990b4], edx
0044dcc4  test  edi, edi
0044dcc6  je    0x44dbba                         ; ★ 不可行 → 继续找下一个
0044dd44  push  0x640
0044dd49  call  0x4544f6                         ; sleep 1600 ms
0044dd51  mov   eax, ebp / shl eax, 2
0044dd5b  push  1
0044dd5d  call  dword ptr [eax + 0x475ef0]       ; ★★ 处理函数(v, 1) —— pass 1
0044dd7b  push  0x320
0044dd80  call  0x4528b9                         ; 800 ms
```

要点（与新闻的差异）：

1. **判定函数会改写事件号**。`v = fortune_order[cur]` 先经 `fortune_check(&v)`，
   若被重映射（例如 10 → 11），**显示与执行的都是重映射后的 `v`**，而游标只按顺序表前进。
2. 处理函数同样被调用两次：`arg==0` 在面板显示阶段，`arg==1` 在 1600 ms 之后。
   **全部 37 个处理函数都是「pass 0 只绘制、pass 1 才生效」**
   （`cmp dword ptr [esp+0x94], 0 / jne <生效分支>`），除 fortune[13]/[15]/[16] 直接复用 fortune[12] 的函数体。
3. 与新闻不同：命运**没有**独立的标题字符串表，面板上唯一的文案就是各处理函数内 `sprintf`/`draw_text` 的那句话。
4. 面板为 `read_mkf(mkf_panel, 66, ...)`（与新闻同一张图），图形画在 `panel+0x18`（新闻是 `panel+0x0c`）。

### 1.4 事件号 `≥33` 的第二套表块（`0x4991b8`）—— 未决

```asm
0044dc4d  push 0
0044dc53  movsx esi, word ptr [0x4991b8]
0044dc5a  movsx eax, word ptr [eax + esi*8 + 0x475fb4]    ; 索引 = v + 4*word[0x4991b8]
0044dc8e  shl   esi, 4
0044dc97  call  dword ptr [esi + eax*4 + 0x475ef0]        ; 索引 = v + 4*word[0x4991b8]
```

即 `fortune_pic_group[v + 4*word[0x4991b8]]` 与 `fortune_call_table[v + 4*word[0x4991b8]]`。
`0x475fb4` 实际只到 48（49 项），分派表只有 37 项，所以：

* `word[0x4991b8] == 0` 时该分支与 `v < 33` 分支**完全等价**；
* ★ **越界风险的归因早期写错了**：索引是 `v + 4*word[0x4991b6]`（`@source 0x0044dc5a`：
  `movsx eax, word ptr [eax + esi*8 + 0x475fb4]`，其中 `esi = word[0x4991b8]`；
  但**乘 4 的是 `0x4991b6`**）。`0x4991b8` = **地图编号（0..3）**，
  它与 `v` 一起被编码进「事件号」的低位（`@source 0x00406e3a`/`0x004075f6`：
  索引恒为 `4*[0x4991b6] + [0x4991b8]`），**本身不会越界**：
  `v ≤ 36` 且 `4*b8 ≤ 12` ⇒ 最大 48，而表有 **49 项（0..48）**恰好容下 ——
  这正是「第二套表块 = 4 张地图各一套图」的设计。**越界风险来自 `0x4991b6`，不是 `0x4991b8`。**

`csrc/fortune.c` 把 `0x4991b8` 当作 `game_map` 并用 `fortune_data_idx[game_map*4 + t]`。
**`0x4991b8` = 地图编号（0..3）**（由 `save-scalars.md` 定名：`@source 0x00406e44` 把设置里的地图号写进它，
`@source 0x004075c1` 一带按它选地图）。**不再「未决」。**
**本文件按 `word[0x4991b8] == 0` 的实际路径描述；越界路径不保证可复刻。**

---

## 二、公共机制

### 2.1 `fortune_check(int *v)`（`@source VA 0x0044bb4b`）

调用约定：`v` 是指向事件号的指针（`int*`），返回 1 = 可行、0 = 不可行。默认返回 1。

```asm
0044bb4f  mov  edx, dword ptr [esp + 0x14]     ; &v
0044bb53  mov  edi, 1                          ; 默认可行
0044bb58  xor  ecx, ecx
0044bb5a  mov  ebx, dword ptr [edx]            ; *v
0044bb5c  cmp  ebx, 0xc / jb ... / jbe 0x44bd35
...
0044bce9  mov  dword ptr [edx], 0xb            ; ★ 改写 *v 的例子（case 10, tm==2 → 11）
```

逐分支核对（**与 `csrc/fortune.c` 的分组逐组一致，唯一差异见加粗行**）：

| `*v` | 分支 VA | 返回 | 副作用 |
|---|---|---|---|
| 0 | `0x44bbef` | 当前玩家在 `land[1..num_lands]` 中**至少有一块 `owner==cur+1` 且 `level != 0`** | — |
| 1 | `0x44bc2f` | 当前玩家**至少有一块 `owner==cur+1` 且 `level == 0`** | — |
| 2,3,4 | 默认 | 恒 1 | — |
| 5 | `0x44bc5e` | 其他玩家的卡片总数 `≠ 0`（`Σ 0x441262(i)`） | — |
| 6,7 | 默认 | 恒 1 | — |
| 8,9 | `0x44bc84` | 当前玩家 12 只股票中任一 `amount != 0` | — |
| 10 | `0x44bcb1` | `tm==1` 或 `tm==2` | `tm==2 → *v = 11` |
| 11 | `0x44bcf4` | `tm==1` 或 `tm==2` | `tm==1 → *v = 10` |
| 12 | `0x44bd35` | `tm==0` 或 `tm==1` | `tm==1 → *v = 13` |
| 13 | `0x44bd76` | `tm==0` 或 `tm==1` | `tm==0 → *v = 12` |
| 14 | `0x44bda8` | `tm ≤ 2` | `tm==1 → *v = 15`；`tm==2 → *v = 16` |
| **15** | `0x44bdd1` | `tm ≤ 2` | **`tm==0 → *v = 14`（汇编为 `mov dword [edx],0xe`，即 `0xe = 14`）**；`tm==2 → *v = 16` |
| 16 | `0x44bded` | `tm ≤ 2` | `tm==0 → *v = 14`；`tm==1 → *v = 15` |
| 17..32 | 默认 | 恒 1 | — |
| 33,34,35,36 | `0x44be03` | `word[0x4991b6] == 0` | — |
| ≥37 | 默认 | 恒 1（实际不可达，游标 ≤ 36） | — |

其中 `tm` = `player[current_player].traffic_method`（`+0x11`）。
`test/cmp` 全部是**有符号/无符号混合**：`case 14/15/16` 用 `ja`（无符号 `>2`）判 `tm` 越界，
`case 12/13` 用 `==`。`tm` 为 `uint8`，故 `ja` 对 0xFF 也成立 → 不可行。

### 2.2 重映射「同族变体」的语义（★ 本系统的核心结构）

10..16 号是「同一件事按交通工具分三种版本」，`fortune_check` 负责归一化：

| 家庭 | 步行 `tm==0` | 机车 `tm==1` | 汽车 `tm==2` |
|---|---|---|---|
| 车辆失窃 | 不可行 | 10 機車被偷遺失 | 11 汽車撞電線桿全毀 |
| 摔伤就医 | 12 掉進水溝就醫 | 13 騎機車摔傷住院 | 不可行 |
| 交通罚款 | 14 行人闖越馬路 | 15 騎機車未戴安全帽 | 16 汽車超速 |

**正是这个结构决定了 case 15 的 `*v` 必须是 14**：`case 15`（机车未戴安全帽）在 `tm==0` 时
必须降级为「行人」版本 14，否则会画出机车版画面对行人收罚款。
若把它写成 `*v = 15`（`csrc/fortune.c` 的写法），`tm==0` 的玩家会看到「騎機車未戴安全帽」的图文 —— 与原版不符。

### 2.3 资金与「神明/气运」判定 `0x44b896(gain_domain, fine_domain)`

这是命运系统里**所有随机加减**的唯一裁决函数（`@source VA 0x0044b896`）：

```asm
0044b896  push ebx/esi/edi/ebp
0044b89a  xor  ebx, ebx
0044b89c  xor  ah, ah / mov byte ptr [0x48c5b8], ah      ; 清台词缓冲
0044b8a4  imul eax, dword ptr [0x49910c], 0x68           ; current_player
0044b8ab  cmp  dword ptr [esp + 0x14], 0                 ; arg0
0044b8b0  jne  0x44b9d3                                  ; arg0 != 0 → 用 0x496bb0 (+0x48)
0044b8b6  cmp  dword ptr [esp + 0x18], 0                 ; arg1
0044b8bb  jne  0x44b94b                                  ; arg1 != 0 → 用「罰金」阈值表
; --- (arg0=0, arg1=0) 獎金域：x = word[player+0x496bae]（+0x46）
0044b8c8  cmp  si, 0x64 / jle ...                        ; x > 100 → ebx = 2
0044b8d5  cmp  si, 0x32 / jle ...                        ; x > 50  → ebx = (rand()&1)*2 ∈ {0,2}
0044b8e9  test si, si / jge ...                          ; x < 0   → ebx = 1；0..50 → 0
0044b914  push 0x465888                                  ; "%s保佑\n\n獎金加倍！"   (ebx==2)
0044b941  push 0x46589b                                  ; "%s作祟\n\n獎金作廢！"   (ebx==1)
; --- (arg0=0, arg1=1) 罰金域：同一 x
0044b958  mov  ebx, 1                                    ; x > 100 → 1
0044b96a  and  ebx, 1                                    ; x > 50  → rand()&1 ∈ {0,1}
0044b976  mov  ebx, 2                                    ; x < 0   → 2
0044b99c  push 0x4658ae                                  ; "%s作祟\n\n罰金加倍！"   (ebx==2)
0044b9c9  push 0x4658c1                                  ; "%s保佑\n\n免付罰金！"   (ebx==1)
; --- arg0 != 0 倒霉域：x = word[player+0x496bb0]（+0x48）
0044b9da  cmp  dx, 0x64 / jle ...                        ; x > 100 → ebx = 1
0044b9ed  and  ebx, 1                                    ; x > 50  → rand()&1
0044b9fe  mov  ebx, 2                                    ; x < 0   → 2
0044ba24  push 0x4658d4                                  ; "%s作祟\n\n倒霉加倍！"   (ebx==2)
0044ba4a  push 0x4658e7                                  ; "%s保佑\n\n逃過此劫！"   (ebx==1)
0044ba4f  push 0x48c5b8 / call 0x457110                  ; sprintf(0x48c5b8, 模板, 神明名)
0044ba5c  mov  eax, ebx / ... / ret                       ; ★ 返回 0 / 1 / 2
```

* 神明名来自 `dword[0x47ed76 + god_info*4]`，其中 `god_info = player[+0x3f]`（**物件下标 + 1**）。
* 返回值语义（原版所有调用点一致）：

| 返回 | 含义 | 调用方的处理 |
|---|---|---|
| 0 | 无判定（`x ∈ [0,50]`） | 照常执行 |
| 1 | 「作祟 / 免付 / 逃過」 | **取反**：收益作废、损失免除、倒霉逃过 |
| 2 | 「保佑 / 加倍」 | **倍化**：收益 ×2、损失 ×2 |

* 阈值表（`x` 为 `int16`）：

| `x` | (0,0) 奖金域 | (0,1) 罚金域 | (1,*) 倒霉域 |
|---|---|---|---|
| `x > 100` | 2（加倍） | 1（免付） | 1（逃过） |
| `50 < x ≤ 100` | `(rand()&1)*2` ∈ {0,2} | `rand()&1` ∈ {0,1} | `rand()&1` ∈ {0,1} |
| `0 ≤ x ≤ 50` | 0 | 0 | 0 |
| `x < 0` | 1（作废） | 2（加倍） | 2（加倍） |

* 文案是**固定模板**：收益类事件返回 2 时显示「保佑 獎金加倍」，损失类事件（如 fortune[2] 冒貸、
  fortune[8] 股票違約）返回 2 时**同样**显示「獎金加倍」而实际是把损失加倍。这是**原版文案的既有瑕疵**，
  复刻 1:1 应当保留（否则画面文案会与原版不一致）。

### 2.4 资金原语

与 `news.md` §2.2 完全相同：`pay_money(payer, payee, amount, flags)` = `0x41d2c6`，
`add_money(player, amount, flags)` = `0x41d3f4`。命运里用到的 flags：

| flags | 含义 | 出现处 |
|---|---|---|
| 0 | 付款从**现金**扣 / 收款进**银行存款** | fortune[14]/[15]/[16]/[17]/[18]/[19]/[23]/[24]/[26]/[30] |
| 1 | 付款从**银行存款**扣 / 收款进**现金** | fortune[0]/[1] 的赔款、fortune[4] 的收款 |
| 4 | 付款**先扣银行存款**（不足再吃现金） | fortune[4]（盗领存款） |
| `payee == -1` | 收进「政府/银行」池 `0x499080` | 罚款类 |

### 2.5 `0x44ba63(player, amount, unused)` —— 保险理赔

`@source VA 0x0044ba63`。玩家 `+0x3e`（`0x496ba6`）为保险剩余天数，非 0 才理赔：

```asm
0044ba6c  imul eax, dword ptr [esp + 0x90], 0x68
0044ba74  cmp  byte ptr [eax + 0x496ba6], 0 / je 0x44bae0    ; 无保险 → 直接返回
0044baa5  push 0x4658fa                                       ; "保險期間\n得到理賠金\n%d元"
0044bac1  call 0x440cac                                       ; player_say 文本
0044bac9  push 1 / push esi(amount)
0044bacc  mov  ebp, dword ptr [esp + 0x98]                    ; ★ 注意：= arg0（见下）
0044bad4  add  ebx, 0x64 / push ebx / push ebp
0044bad8  call 0x41d2c6                                       ; pay_money(100+设施号, player, amount, 1)
```

* **参数个数为 3，但第 3 个参数在原函数内未被读取**：`0x44bacc` 处的 `[esp+0x98]` 在两条 push 之后
  等价于入口时的 `[esp+0x90]`，即 **arg0（玩家下标）**。第 3 参数只是调用方习惯性多传。
* 理赔款由「保险设施」（`+0x1a == 4` 的第一家设施，号 `100+ebx`）支付，玩家**收现金**（flags=1）。

---

## 三、逐事件规格

> 「气运判定」列的写法 `(a,b,域)` 指该事件调用了 `0x44b896(a,b)`，`域` 为 `奖金/罚金/倒霉`；
> 「-」表示该事件**不调用** `0x44b896`（不受神明气运影响）。

| # | 事件 | `0x44b896` 调用 |
|---|---|---|
| 0,1 | 强制拆除 / 强制征收 | - |
| 2,3 | 冒贷 / 跳票 | `(0,1)` 罚金域 |
| 4 | 侵入银行电脑 | - |
| 5 | 生日收卡 | - |
| 6,7,10,11,12,13,32,33,34,35,36 | 观光/绑架/失车/就医/卖卡/坐牢 | `(1,1)` 倒霉域 |
| 8,9,14,15,16,17,18,19,23,24,26,30 | 股票损失/罚款/损失类 | `(0,1)` 罚金域 |
| 20,21,22,25,27,28,29,31 | 捡到钱/中奖/理赔 | `(0,0)` 奖金域 |

### fortune[0] — 強制拆除房屋一棟

* **VA**：`0x0044be16`（`0x44be16..0x44bfb1`，411 字节）
* **台词**：`#0185強制拆除房屋一棟`（`@source VA 0x00465915`）
* **有效 pass**：**pass 1**（`@source 0x0044be27`: `jne 0x44becf`）
* **范围**：单个 —— 当前玩家自己的一块**已开发住宅用地**

```asm
0044be2d  xor  ebx, ebx                        ; 候选计数
0044be34  cmp  eax, dword ptr [0x498e98]       ; num_lands
0044be49  mov  cl, byte ptr [edx + 0x19]       ; owner
0044be4c  mov  esi, dword ptr [0x49910c] / inc esi     ; current_player+1
0044be53  cmp  ecx, esi / jne 0x44be62         ; ★ owner == current_player+1
0044be57  cmp  byte ptr [edx + 0x1a], 0 / je 0x44be62  ; ★ level != 0
0044be5d  mov  word ptr [esp + ebx*2], ax      ; 收集 land_index
0044be65  call 0x456f2d / idiv ebx             ; rand() % 候选数
0044be75  and  eax, 0xffff
0044be7a  mov  dword ptr [0x48c5b0], eax       ; ★ 选中的 land_index（裸下标）
; pass 1：
0044becf  imul ebx, dword ptr [0x48c5b0], 0x34
0044bedb  add  ebx, eax                        ; land 指针
0044bee8  call 0x41d476                        ; update_player_info_window(x,y,2)
0044bef2  call 0x409b18                        ; 刷新（参数 1）
0044bf16  call 0x456c0a                        ; 表现层刷新
0044bf1e  push 1
0044bf22  mov  dx, word ptr [ebx + 0x1e]       ; ★ house_price (uint16)
0044bf28  mov  al, byte ptr [ebx + 0x1a]       ; ★ level (uint8)
0044bf2b  imul eax, edx                        ; ★ level * house_price
0044bf2f  push eax / push edi(current_player) / call 0x41d3f4   ; add_money(cur, v, flags=1 → 现金)
0044bf3e  mov  byte ptr [ebx + 0x1a], 0        ; ★ level = 0
0044bf42  mov  byte ptr [ebx + 0x18], 0        ; ★ type  = 0
0044bf46  call 0x451985                        ; 拍卖/刷新
0044bf51  call 0x41d476                        ; update_player_info_window(0,0,1)
0044bf5e  call 0x4528b9                        ; sleep 300
0044bf9f  call 0x44ef41                        ; player_say(cur, 2, 台词[rand()&1])
```

**精确规则**

```
候选 = { land i | land[i].owner(+0x19) == current_player+1 且 land[i].level(+0x1a) != 0 }
选中 = 候选[rand() % |候选|]
赔款 = uint8[sel+0x1a] * uint16[sel+0x1e]        // level * house_price，无 price_index
add_money(current_player, 赔款, flags=1)         // 进现金
sel.level = 0 ; sel.type = 0                     // ★ owner 不变
```

**边界**

* 只有**住宅用地**（`0x498e84`），**不含设施**。
* `owner` **不清除** —— 拆完仍是自己的空地。若 `type` 原本非 0（商業用地），这里直接清 0。
* 候选为空 ⇒ `idiv 0`；`fortune_check` case 0 已保证非空，但若某调用方绕过判定则除零。

### fortune[1] — 強制徵收土地一處

* **VA**：`0x0044bfb1`（`0x44bfb1..0x44c0e8`，311 字节）
* **台词**：`#0186強制徵收土地一處`（`@source VA 0x0046592b`）
* **有效 pass**：**pass 1**（`@source 0x0044bfc2`: `jne 0x44c067`）
* **范围**：单个 —— 当前玩家自己的一块**未开发住宅用地**

```asm
0044bff2  cmp  byte ptr [edx + 0x1a], 0 / jne 0x44bffd   ; ★ level == 0 才入池
0044c012  mov  dword ptr [0x48c5b0], eax                  ; 选中的 land_index
; pass 1：
0044c0ba  mov  ax, word ptr [ebx + 0x1c]                  ; ★ land.land_price (uint16)
0044c0c6  call 0x41d3f4                                   ; add_money(cur, land_price, 1)
0044c0ce  mov  byte ptr [ebx + 0x19], 0                   ; ★ owner = 0
0044c0d2  mov  dword ptr [ebx + 0x30], 0                  ; ★ flast = 0
0044c0db  call 0x40a4e1                                   ; 地块记录清理
0044c0e3  jmp  0x44bf46                                   ; 复用 fortune[0] 的收尾
```

**边界**

* 补偿用的是 **`land_price(+0x1c)`**，与 fortune[0] 的 `level*house_price` 不同。
* 若地已有建築（`level != 0`），本事件不可选（`fortune_check` case 1 只要求「存在 level==0 的地」，
  所以这是「征地」而不是「拆房」）。

### fortune[2] — 人頭被盜用冒貸 %d 元

* **VA**：`0x0044c0e8`（`0x44c0e8..0x44c229`，321 字节）
* **台词**：`#0187人頭被盜用冒貸%d元`（`@source VA 0x00465941`）
* **有效 pass**：**pass 1**（`@source 0x0044c0f8`: `jne 0x44c180`）
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域

```asm
0044c0fe  mov  edx, dword ptr [0x4990e8]       ; price_index → 10000*p（移位序列）
0044c118  mov  dword ptr [0x48c5b4], eax       ; ★ amount = 10000 * p
0044c11e  push 0x465941                        ; "#0187人頭被盜用冒貸%d元"
; pass 1：
0044c180  push 1 / push 0 / call 0x44b896      ; ★ 罚金域判定
0044c18c  mov  dword ptr [0x48c5b0], eax
0044c191  cmp  eax, 1 / jne 0x44c1b8
   r==1 → update_window(0,0,3); player_say(0x48c5b8, 0x5dc); ★ return（不冒贷）
0044c1b8  cmp  eax, 2 / jne 0x44c1eb
   r==2 → player_say(0x48c5b8, 0x5dc); 0x48c5b4 *= 2
0044c1f4  mov  edx, dword ptr [0x48c5b4]
0044c1fa  add  dword ptr [eax + 0x496b8c], edx  ; ★ player.loan += amount
0044c201  call 0x433b7e                         ; （语义未决，见 §5）
0044c218  call 0x44ba63                         ; 保险理赔(cur, amount, 0)
```

**精确规则**：`amount = 10000*p`；气运 `r==1` → **完全不发生**；`r==2` → `amount *= 2`；
随后 `player.loan (+0x24) += amount`，再走 `0x433b7e(cur)` 与保险理赔。

### fortune[3] — 支票跳票，銀行拒絕往來一個月

* **VA**：`0x0044c229`（`0x44c229..0x44c2c2`，153 字节）
* **台词**：`#0188支票跳票\n銀行拒絕往來一個月`（`@source VA 0x00465959`）
* **有效 pass**：**pass 1**（`@source 0x0044c22f`: `jne 0x44c27c`）
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域

```asm
0044c280  call 0x44b896                        ; (0,1)
0044c288  mov  dword ptr [0x48c5b0], eax
0044c28d  cmp  eax, 1 / jne 0x44c2b3
   r==1 → update_window(0,0,3); player_say(0x48c5b8, 0x5dc); return   ★ 免
0044c2b3  imul eax, dword ptr [0x49910c], 0x68
0044c2ba  add  byte ptr [eax + 0x496ba3], 0x1e ; ★ days_rejected_by_bank += 30
```

**边界**：`r==2`（罰金加倍）**不**加倍天数，效果与 `r==0` 相同（都是 +30 天）。
原版没有对天数做 `&0x7f` 掩码，重复触发会累加溢出。
30 天与文案「一個月」一致。

### fortune[4] — 侵入銀行電腦，挪用其他人存款 %d％

* **VA**：`0x0044c2c2`（`0x44c2c2..0x44c3b7`，245 字节）
* **台词**：`#0189侵入銀行電腦\n挪用其他人存款%d％`，`%d` **硬编码 10**（`@source 0x0044c2d4`: `mov ecx,0xa`）
* **有效 pass**：**pass 1**（`@source 0x0044c2d2`: `jne 0x44c342`）
* **范围**：全体**其他对局中玩家**（每人独立结算）

```asm
0044c342  fild dword ptr [0x48c5b0]           ; = 10
0044c348  fdiv dword ptr [0x4659a0]           ; ★ 除以单精度 100.0 → 0.1f
0044c34e  fstp dword ptr [esp + 0x84]
0044c357  cmp  ebx, dword ptr [0x499114]      ; for each player
0044c365  cmp  ebx, edi / je  0x44c3ab        ; ★ 跳过自己
0044c36c  cmp  byte ptr [eax + 0x496b7d], 0 / je 0x44c3ab    ; 跳过非对局
0044c375  cmp  dword ptr [eax + 0x496b88], 0 / je 0x44c3ab   ; ★ 存款为 0 跳过
0044c37e  fild dword ptr [eax + 0x496b88]     ; money_in_bank
0044c384  fmul dword ptr [esp + 0x84]         ; × 0.1（单精度）
0044c38b  call  0x457dbc                      ; 取整
0044c390  fistp dword ptr [esp + 0x80]
0044c397  push 4 / push v / push edi(cur) / push ebx(victim)
0044c3a3  call  0x41d2c6                      ; pay_money(victim, cur, v, flags=4)
```

**精确规则**：`v = round(victim.money_in_bank * 0.1)`（单精度乘法，`0x4659a0` = `100.0f`）；
`pay_money(victim, current_player, v, flags=4)` ⇒ **先从受害者银行扣**，不足再吃现金；
当前玩家**收进银行存款**（flags 未置 bit0）。

**边界**

* 受害者存款为 0 → 跳过（不产生 0 元交易）。
* 受害者存款不足 ⇒ `pay_money` 把实付额截断（**不会让受害者负债**），当前玩家也只收到实付额。
* 只对**其他玩家**生效（`ebx == current_player` 跳过），不涉及银行池。
* 受害者若因扣款破产，`pay_money` 内 `0x40cd87` 处理（破产流程不在本文件范围）。

### fortune[5] — 今天是你生日，向每人收取一張卡片

* **VA**：`0x0044c3b7`（`0x44c3b7..0x44c5d8`，545 字节）
* **台词**：`#0190今天是你生日\n向每人收取一張卡片`（`@source VA 0x004659a4`）
* **有效 pass**：**pass 1**（`@source 0x0044c3ca`: `jne 0x44c41b`）
* **范围**：全体其他对局中玩家（每人被收 1 张卡）
* **气运**：**不调用 `0x44b896`**（无条件执行）

```asm
0044c41f  cmp  ebx, dword ptr [0x499114]      ; for each other player
0044c42b  cmp  ebx, dword ptr [0x49910c] / je 0x44c575       ; 跳过自己
0044c43a  cmp  byte ptr [esi + 0x496b7d], 0 / je 0x44c575    ; 跳过非对局
0044c448  call 0x441262                        ; ★ 对方手牌数
0044c452  je   0x44c575                        ; 没牌 → 跳过
0044c462  mov  dl, byte ptr [eax + 0x496b7d]   ; current_player.who_plays
0044c468  cmp  dl, 1 / jbe 0x44c48b
   who_plays > 1（AI）→ 0x441e77(other) → 0x4412e4(cur, card)  ★ 自动夺牌
0x44c48b: jne 0x44c575                          ; ★ 只有 who_plays == 1（人类）才走交互
0044c4de  push 0x4659c9                         ; "向%s收一張卡片"
0044c51e  call 0x44192a                         ; ★ 交互式夺牌(cur, other, 0)
0044c573  mov  edi, ebp                         ; 交易计数
0044c57b  test edi, edi / je 0x44c5cd
0044c5b5  mov  ebp, dword ptr [ebx + eax*4 + 0x48084a]   ; ★ 台词槽 0x48084a（非 0x480856）
0044c5c5  call 0x44ef41                         ; player_say(cur, 0, 台词)
```

**边界**

* 对方**手牌为 0** 时跳过（`0x441262` 返回 0）。
* 人类玩家（`who_plays == 1`）走**弹窗交互**（显示「向 X 收一張卡片」，等待动画/确认）；
  AI（`who_plays > 1`）直接自动夺牌。复刻时这条分支是**必须保留的**人机差异。
* `who_plays == 0`（出局）时 `cmp dl,1 / jbe` 会进 0x44c48b，但那里 `jne 0x44c575` 会跳过
  —— 出局玩家不会触发交互也不会夺牌。

### fortune[6] — 強迫出國觀光 %d 天

* **VA**：`0x0044c5d8`（`0x44c5d8..0x44c6ed`，277 字节）
* **台词**：`#0191強迫出國觀光%d天`，`%d` = 3（`@source 0x0044c5eb`: `mov eax,3`）
* **有效 pass**：**pass 1**（`@source 0x0044c5e9`: `jne 0x44c658`）
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044c5f0  mov  dword ptr [0x48c5b4], eax      ; days = 3
0044c658  push 1 / push 1 / call 0x44b896     ; ★ 倒霉域
0044c664  mov  dword ptr [0x48c5b0], eax
0044c66f  call 0x41d476                        ; update_window(0,0,3)
0044c67d  cmp  ecx, 1 / jne 0x44c699
   r==1 → player_say(0x48c5b8, 0x5dc); ★ return（逃过）
0044c699  cmp  ecx, 2 / jne 0x44c6be
   r==2 → player_say; 0x48c5b4 *= 2            ; ★ 天数加倍
0044c6c5  call 0x441210                        ; 取可移动槽位
0044c6d0  je   0x44d3d1                        ; -1 → 结束
0044c6d6  push 0
0044c6d8  mov  ebp, dword ptr [0x48c5b4]
0044c6df  push ebp / push eax / call 0x40d375  ; ★ 0x40d375(slot, days, 0)
```

**`0x40d375(slot, days, kind)` 的语义**（`@source VA 0x0040d375`，已反汇编）

* 写 `player.days_disappearing (0x496b9b)`（把 `days` 与 `kind<<6` 合成一个字节）；
* 从当前位置把角色移出（写 `node[当前节点].+0x24` 掩码 `&= ~(1<<player)`）；
* 播放 `mkf 0x22e`（`kind == 0`）或 `mkf 0x215`（`kind != 0`）的消失动画；
* 收取差旅费：`0x44ba63(player, 2000*days*price_index, 0)`
  （`@source 0x0040d400..0x0040d425`：`(days*4 - days)*8 ... *16 ... = 2000*days` 再 `imul price_index`）
  —— 有保险时由保险公司支付。

### fortune[7] — 被外星人綁架 %d 天

* **VA**：`0x0044c6ed`（`0x44c6ed..0x44c7ef`，258 字节）
* **台词**：`#0192被外星人綁架%d天`，`%d` = 3
* **有效 pass**：**pass 1**
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域
* 与 fortune[6] 唯一差别：`0x40d375(slot, days, 1)`（`@source 0x0044c7e8`: `push 1`），
  即改用 `mkf 0x215` 的「绑架」动画。

### fortune[8] — 股票違約交割損失股票 %d％

* **VA**：`0x0044c7ef`（`0x44c7ef..0x44c91f`，304 字节）
* **台词**：`#0193股票違約交割損失股票%d％`，`%d` = 10（`@source 0x0044c802`: `mov ecx,0xa`）
* **有效 pass**：**pass 1**（`@source 0x0044c800`: `jne 0x44c870`）
* **范围**：单个 —— 当前玩家的全部 12 只股票
* **气运**：`(0,1)` 罚金域

```asm
0044c874  call 0x44b896                        ; (0,1)
0044c87c  mov  dword ptr [0x48c5b0], eax
0044c881  cmp  eax, 1 / jne 0x44c8a8
   r==1 → update_window(0,0,3); player_say(0x48c5b8, 0x5dc); ★ return（損失作廢）
0044c8aa  fild dword ptr [0x48c5b4]            ; = 10
0044c8b0  fdiv dword ptr [0x465a24]            ; ★ 单精度 100.0 → 0.1f
0044c8cf  fild dword ptr [edx + eax*8 + 0x4971a0]   ; 持股数
0044c8d8  fmul dword ptr [esp + 0x84]          ; × 0.1（单精度）
0044c8df  call  0x457dbc                       ; 取整
0044c8fd  call  0x428e23                       ; ★ 0x428e23(cur, stock_i, loss, 0)
0044c906  cmp  ebx, 0xc / jl 0x44c8aa          ; i = 0..11
0044c90d  call 0x436b0a                        ; 行情重绘（参数 0）
```

**精确规则**：`loss[i] = round(stock[i].amount * 0.1)`，
`0x428e23(current_player, i, loss[i], 0)`（卖出/扣减，参数 0）。
**`r==2` 不加倍**（与 fortune[2] 不同）：`r==2` 只多说一句台词，损失照常。

**边界**

* **不跳过 amount == 0 的股票**（循环无条件执行 12 次，`loss` 可能为 0）。
* `0x465a24` = `100.0f`（单精度 4 字节），不是双精度 —— 精度路径必须一致。

### fortune[9] — 變賣所有股票求現

* **VA**：`0x0044c91f`（`0x44c91f..0x44ca46`，295 字节）
* **台词**：`#0194變賣所有股票求現`（`@source VA 0x00465a28`）
* **有效 pass**：**pass 1**（`@source 0x0044c928`: `jne 0x44c978`）
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域

```asm
0044c97c  call 0x44b896                        ; (0,1)
0044c989  push 3 / push 0 / push 0 / call 0x41d476
0044c997  cmp  dword ptr [0x48c5b0], 1 / jne 0x44c9b6
   r==1 → say + return                          ★ 免
0044c9c0  ... 逐只股票（amount != 0）
0044c9e1  push 1 / push esi(amount) / push ebx(i) / push ebp(cur)
0044c9ec  call 0x428e23                         ; ★ 全部卖出（参数 1）
0044c9fc  call 0x41d433                         ; 该玩家信息条重绘
0044ca30  call 0x44ef41                         ; player_say(cur, 2, 槽 0x48085e)
0044ca3a  call 0x436b0a                         ; 行情重绘
```

**边界**：`r==2` 与 `r==0` 完全相同（只是台词不同）——**没有**任何倍数。
`amount == 0` 的股票跳过（`0x44c9df: je`）。

### fortune[10] — 機車被偷遺失

* **VA**：`0x0044ca46`（`0x44ca46..0x44cb53`，269 字节）
* **台词**：`#0195機車被偷遺失`（`@source VA 0x00465a3e`）
* **有效 pass**：**pass 1**（`@source 0x0044ca4f`: `jne 0x44ca9f`）
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044caa3  call 0x44b896                        ; (1,1)
0044cab3  cmp  eax, 1 / jne 0x44cad9
   r==1 → update_window(0,0,3); player_say; ★ return（逃過）
0044cad9  mov  ecx, dword ptr [0x49910c]
0044cae4  mov  byte ptr [eax + 0x496b79], dl   ; ★ traffic_method = 0（降级为步行）
0044caea  mov  byte ptr [eax + 0x496b7a], 1    ; ★ ndices = 1（骰子数 1）
0044caf2  call 0x40b93b                         ; 更新载具外观
0044cb00  call 0x41d476                         ; update_player_window(0,0,3)
0044cb41  call 0x44ef41                         ; player_say(cur, 2, 槽 0x480856)
0044cb49  inc  byte ptr [0x497324]              ; ★ 计数器 +1（语义未决）
```

**边界**：`r==2` 与 `r==0` 相同（**不额外惩罚**）；本事件本质就是「失去载具」。
`0x497324` 的用途未决。

### fortune[11] — 汽車撞電線桿全毀

* **VA**：`0x0044cb53`（`0x44cb53..0x44cc53`，256 字节）
* **台词**：`#0196汽車撞電線桿全毀`（`@source VA 0x00465a50`）
* **有效 pass**：**pass 1**
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域
* 与 fortune[10] **完全相同**（`traffic_method = 0`、`ndices = 1`、`0x40b93b`、`0x41d476`、`player_say`），
  唯一差别：计数器写 `inc byte ptr [0x497325]`（`@source 0x0044cc49`）。

### fortune[12] — 掉進水溝就醫 %d 天

* **VA**：`0x0044cc53`（`0x44cc53..0x44cd6c`，281 字节）
* **台词**：`#0197掉進水溝就醫%d天`，`%d` = 3（`@source 0x0044cc67`: `mov eax,3`）
* **有效 pass**：**pass 1**（`@source 0x0044cc65`: `jne 0x44ccd4`）
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044ccd8  call 0x44b896                        ; (1,1)
0044ccf3  cmp  ecx, 1 / jne 0x44cd15
   r==1 → say + return                          ★ 逃過
0044cd15  cmp  ecx, 2 / jne 0x44cd3a
   r==2 → say; 0x48c5b4 *= 2                    ★ 天数加倍
0044cd41  call 0x441210                         ; 取槽位
0044cd4e  je   0x44d800                          ; -1 → 结束
0044cd55  call 0x40cd07                          ; （语义未决）
0044cd65  call 0x43ec3f                          ; ★ add_player_days_in_hospital(slot, days)
```

* `0x43ec3f(player, days)` 写 `player.days_in_hospital (0x496b9d)` 并置 `0x496b60 = 1`
  （已用 fortune[33] 的坐牢对照组与 `0x43d593` 交叉验证）。
* **`r==2` 使住院天数加倍**（3 → 6）。

### fortune[13] — 騎機車摔傷住院 %d 天

* **VA**：`0x0044cd6c`（`0x44cd6c..0x44cd99`，45 字节 —— **只是一个跳板**）
* **台词**：`#0198騎機車摔傷住院%d天`，`%d` = 3
* **有效 pass**：**pass 1**
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044cd76  cmp  dword ptr [esp + 0x94], 0 / jne 0x44ccd4   ; ★ pass 1 → 直接跳进 fortune[12] 的生效段
0044cd84  mov  eax, 3 / mov dword ptr [0x48c5b4], eax
0044cd8f  push 0x465a7c                                    ; "#0198騎機車摔傷住院%d天"
0044cd94  jmp  0x44cc77                                    ; ★ 复用 fortune[12] 的绘制/排版
```

* 即：**同一套逻辑，仅文案不同**。效应与边界同 fortune[12]。

### fortune[14] — 行人闖越馬路罰款 %d 元

* **VA**：`0x0044cd99`（`0x44cd99..0x44cf1e`，389 字节）
* **台词**：`#0199行人闖越馬路罰款%d元`（`@source VA 0x00465a94`）
* **有效 pass**：**pass 1**（`@source 0x0044cdab`: `jne 0x44ce35`）
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域

```asm
0044cdb1  ... 移位序列 → 3000 * p
0044cdcd  mov  dword ptr [0x48c5b4], eax       ; ★ amount = 3000 * price_index
0044ce39  call 0x44b896                        ; (0,1)
0044ce5a  cmp  ecx, 1 / jne 0x44ce8b
   r==1 → say; 0x44f567(cur, amount); ★ return（免付）
0044ce8b  cmp  ecx, 2 / jne 0x44ceb0
   r==2 → say; amount *= 2
0044ceb0  push 0 / push amount / push -1 / push cur / call 0x41d2c6   ; ★ pay_money(cur,-1,amount,0)
0044ced1  cmp  byte ptr [eax + 0x496b7d], 0 / je end
0044cede  cmp  byte ptr [0x46caf8], 0 / jne end
0044cef9  call 0x44f42d                        ; 表现层
0044cf11  call 0x44ba63                        ; ★ 保险理赔(cur, amount, 1)
```

**精确规则**：`amount = 3000*p`；`r==2` → ×2；`pay_money(cur, -1, amount, 0)`（罚给政府，扣现金）；
随后若玩家仍在局且 `byte[0x46caf8]==0`，走 `0x44f42d` 与保险理赔 `0x44ba63(cur, amount, 1)`。

**边界**

* 「免付」分支（`r==1`）只调 **`0x44f567`**，不调保险理赔 —— 即免罚时保险也不理赔。
* `byte[0x46caf8] != 0` 时跳过理赔与特效（但仍已扣款）。

### fortune[15] — 騎機車未戴安全帽，罰款 %d 元

* **VA**：`0x0044cf1e`（`0x44cf1e..0x44d06d`，335 字节）
* **台词**：`#0200騎機車未戴安全帽\n罰款%d元`（`@source VA 0x00465aae`）
* **有效 pass**：**pass 1**
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域
* **金额**：`3000*p`（与 fortune[14] 相同）

```asm
0044cf28  imul eax, dword ptr [0x49910c], 0x68
0044cf2f  cmp  byte ptr [eax + 0x496b79], 0    ; ★ 再次自检 traffic_method
0044cf36  jne  0x44cf4d
0044cf38  mov  ebx, dword ptr [esp + 0x94]     ; 参数原样
0044cf40  call 0x44cc53                        ; ★ tm == 0 → 转入 fortune[12]（就醫）
```

**★ 这就是「case 15 在 tm==0 时必须重映射为 14」的第二道保险**：
即使有人绕过 `fortune_check` 直接调用 `fortune_call_table[15]`，
函数体自己也会在 `traffic_method == 0` 时改走 fortune[12]（掉进水沟就医）。
**但注意**：`fortune_check` 的重映射发生在「选图之前」，而这里的兜底发生在「选图之后」——
只调用函数体、不重映射 `v`，画面仍会是机车版。两者**不能互相替代**。

### fortune[16] — 汽車超速罰款 %d 元

* **VA**：`0x0044d06d`（`0x44d06d..0x44d0d6`，105 字节）
* **台词**：`#0201汽車超速罰款%d元`（`@source VA 0x00465acd`）
* **有效 pass**：**pass 1**
* **范围**：单个 —— 当前玩家
* **气运**：`(0,1)` 罚金域
* 结构同 fortune[15]：`tm == 0` 时转 fortune[12]；金额 `3000*p`；唯一差别是文案。

### fortune[17] — 請所有人吃大餐，花費 %d 元

* **VA**：`0x0044d0d6`（`0x44d0d6..0x44d1a5`，207 字节）
* **台词**：`#0202請所有人吃大餐\n花費%d元`（`@source VA 0x00465ae3`）
* **有效 pass**：**pass 1**（`@source 0x0044d0e8`: `jne 0x44d172`）
* **范围**：**仅当前玩家付费**（文案说「所有人」，但代码里**没有**对其他玩家的循环或分配）

```asm
0044d0ee  ... 移位序列 → 6000 * p
0044d10a  mov  dword ptr [0x48c5b4], eax       ; ★ amount = 6000 * price_index
0044d172  push 1 / push 0 / call 0x44b896      ; (0,1)
0044d197  cmp  ecx, 1 / jne 0x44ce8b
   r==1 → jmp 0x44d009（复用 fortune[14]/[15] 的「免付」段）
0044d057  push 0 / push amount / push -1 / push cur / jmp 0x44cec2   ; pay_money(cur,-1,amount,0)
```

**★ 已复核：本条只对「当前玩家」收 `6000*p`，收款方是政府池（`payee = -1`），
没有任何「发给其他玩家」的代码路径。** 复刻若按文案实现成「请客 = 给别人钱」会与原版不符。

### fortune[18] — 亂丟垃圾罰款 %d 元

* **VA**：`0x0044d1a5`（`0x44d1a5..0x44d1e0`，59 字节）
* **台词**：`#0203亂丟垃圾罰款%d元`（`@source VA 0x00465b00`）
* **有效 pass**：**pass 1**
* **气运**：`(0,1)` 罚金域；金额 `600*p`（`@source 0x0044d1b9` 移位序列）；
  生效段直接 `jmp 0x44d115`（复用 fortune[17] 的绘制）与 `0x44cf82`（复用 fortune[15] 的扣款+理赔）。

### fortune[19] — 你家小狗亂大小便，罰款 %d 元

* **VA**：`0x0044d1e0`（`0x44d1e0..0x44d224`，68 字节）
* **台词**：`#0204你家小狗亂大小便\n罰款%d元`（`@source VA 0x00465b16`）
* **有效 pass**：**pass 1**
* **气运**：`(0,1)` 罚金域；金额 **`1500*p`**（`@source 0x0044d1f8` 移位序列）。

### fortune[20] — 在路邊撿到 %d 元

* **VA**：`0x0044d224`（`0x44d224..0x44d33b`，279 字节）
* **台词**：`#0205在路邊撿到%d元`（`@source VA 0x00465b35`）
* **有效 pass**：**pass 1**（`@source 0x0044d235`: `jne 0x44d2a9`）
* **气运**：`(0,0)` 奖金域
* **金额**：**`1000*p`**

```asm
0044d2ab  push 0 / push 0 / call 0x44b896      ; ★ 奖金域
0044d2c8  cmp  ecx, 1 / jne 0x44d2ea
   r==1 → say; ★ return（作廢，不捡钱）
0044d2ea  cmp  ecx, 2 / jne 0x44d30f
   r==2 → say; amount *= 2
0044d30f  push 1 / push amount / push cur / call 0x41d3f4   ; ★ add_money(cur, amount, flags=1) 进现金
0044d334  call 0x44f354                        ; 表现层
```

### fortune[21] — 在路邊撿到 %d 元

* **VA**：`0x0044d33b`（`0x44d33b..0x44d3db`，160 字节）
* **台词**：`#0206在路邊撿到%d元`（`@source VA 0x00465b49`）
* **有效 pass**：**pass 1**；**气运** `(0,0)`
* **金额**：**`2000*p`**（`@source 0x0044d352` 移位序列）；生效段 `jmp 0x44d2a9`（复用 fortune[20]）。

### fortune[22] — 在路邊撿到 %d 元

* **VA**：`0x0044d3db`（`0x44d3db..0x44d41e`，67 字节）
* **台词**：`#0207在路邊撿到%d元`（`@source VA 0x00465b5d`）
* **有效 pass**：**pass 1**；**气运** `(0,0)`
* **金额**：**`3000*p`**（`@source 0x0044d3f2`）；生效段 `jmp 0x44d379`（复用 fortune[21] 的绘制 + fortune[20] 的发放）。

### fortune[23] — 遺失錢包損失 %d 元

* **VA**：`0x0044d41e`（`0x44d41e..0x44d462`，68 字节）
* **台词**：`#0208遺失錢包損失%d元`（`@source VA 0x00465b71`）
* **有效 pass**：**pass 1**；**气运** `(0,1)` 罚金域
* **金额**：**`1000*p`**（`@source 0x0044d436`）；生效段 `jmp 0x44cf82`（复用 fortune[15] 的扣款+理赔）。

### fortune[24] — 遺失錢包損失 %d 元

* **VA**：`0x0044d462`（`0x44d462..0x44d4a6`，68 字节）
* **台词**：`#0209遺失錢包損失%d元`（`@source VA 0x00465b87`）
* **有效 pass**：**pass 1**；**气运** `(0,1)`
* **金额**：**`2000*p`**（`@source 0x0044d47a`）；生效段 `jmp 0x44d115`。

### fortune[25] — 意外獲得遺產 %d 元

* **VA**：`0x0044d4a6`（`0x44d4a6..0x44d4e7`，65 字节）
* **台词**：`#0210意外獲得遺產%d元`（`@source VA 0x00465b9d`）
* **有效 pass**：**pass 1**；**气运** `(0,0)` 奖金域
* **金额**：**`10000*p`**（`@source 0x0044d4bd`，是全系统最大的一笔收入）；生效段 `jmp 0x44d379`。

### fortune[26] — 被倒會損失 %d 元

* **VA**：`0x0044d4e7`（`0x44d4e7..0x44d52b`，68 字节）
* **台词**：`#0211被倒會損失%d元`（`@source VA 0x00465bb3`）
* **有效 pass**：**pass 1**；**气运** `(0,1)`
* **金额**：**`8000*p`**（`@source 0x0044d4ff`）；生效段 `jmp 0x44d115`。

### fortune[27] — 發票中獎 %d 元

* **VA**：`0x0044d52b`（`0x44d52b..0x44d56e`，67 字节）
* **台词**：`#0212發票中獎%d元`（`@source VA 0x00465bc7`）
* **有效 pass**：**pass 1**；**气运** `(0,0)` 奖金域
* **金额**：**`4000*p`**（`@source 0x0044d542`）；生效段 `jmp 0x44d25e`。

### fortune[28] — 發票中獎 %d 元

* **VA**：`0x0044d56e`（`0x44d56e..0x44d5b1`，67 字节）
* **台词**：`#0213發票中獎%d元`（`@source VA 0x00465bd9`）
* **有效 pass**：**pass 1**；**气运** `(0,0)`
* **金额**：**`6000*p`**（`@source 0x0044d585`）；生效段 `jmp 0x44d379`。

### fortune[29] — 發票中獎 %d 元

* **VA**：`0x0044d5b1`（`0x44d5b1..0x44d5f4`，67 字节）
* **台词**：`#0214發票中獎%d元`（`@source VA 0x00465beb`）
* **有效 pass**：**pass 1**；**气运** `(0,0)`
* **金额**：**`8000*p`**（`@source 0x0044d5c8`）；生效段 `jmp 0x44d379`。

### fortune[30] — 付保險金 %d 元

* **VA**：`0x0044d5f4`（`0x44d5f4..0x44d636`，66 字节）
* **台词**：`#0215付保險金%d元`（`@source VA 0x00465bfd`）
* **有效 pass**：**pass 1**（`@source 0x0044d606`: `jne 0x44d172`）
* **气运**：`(0,1)` 罚金域；**金额 `5000*p`**（`@source 0x0044d60c`）
* 生效段 `jmp 0x44cf82` ⇒ `pay_money(cur, -1, amount, 0)`，即**付给政府池**，而不是保险公司。
  「付保險金」在实现上是「缴纳保费」的支出项。

### fortune[31] — 領取保險金 %d 元

* **VA**：`0x0044d636`（`0x44d636..0x44d677`，65 字节）
* **台词**：`#0216領取保險金%d元`（`@source VA 0x00465c0f`）
* **有效 pass**：**pass 1**（`@source 0x0044d647`: `jne 0x44d2a9`）
* **气运**：`(0,0)` 奖金域；**金额 `5000*p`**（`@source 0x0044d64d`）；生效段 `jmp 0x44d379`
  ⇒ `add_money(cur, amount, 1)` 进现金。

### fortune[32] — 變賣所有卡片道具

* **VA**：`0x0044d677`（`0x44d677..0x44d783`，268 字节）
* **台词**：`#0217變賣所有卡片道具`（`@source VA 0x00465c23`）
* **有效 pass**：**pass 1**（`@source 0x0044d680`: `jne 0x44d6d0`）
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044d6d4  call 0x44b896                        ; (1,1)
0044d6ef  cmp  dword ptr [0x48c5b0], 1 / jne 0x44d70e
   r==1 → say + return                          ★ 逃過
0044d70e  mov  esi, dword ptr [0x49910c]
0044d718  call 0x445b3f                        ; ★ 道具变卖价
0044d720  add  word ptr [ebx + 0x496b98], ax   ; ★ player.points += 道具价
0044d731  call 0x441f21                        ; ★ 卡片变卖价
0044d739  add  word ptr [ebx + 0x496b98], ax   ; ★ player.points += 卡片价
0044d747  call 0x41d433                        ; 信息条重绘
0044d777  call 0x44ef41                        ; player_say(cur, 2, 槽 0x480856)
```

**精确规则**：`points(+0x30, uint16) += 0x445b3f(cur) + 0x441f21(cur)`（先道具后卡片，**16 位累加，可能溢出**）。
**`r==2` 不加倍**。

**未决 → ✅ 已结案（2026 本轮，通道 2 `tests/test_sell_all.py` 35/35）**：
`0x445b3f` / `0x441f21` **会顺带清空** —— 前者把 13 个道具槽逐个写 0
（`@source 0x445c05 mov byte ptr [edx + eax + 0x49915c], cl`，cl=0），
后者把 15 个手牌槽逐个写 0（`@source 0x441f6b mov byte ptr [eax + 0x499120], dh`，dh=0）。
两支都**没有**「只计价不清空」的分支。配套事实：

| 事实 | 值 | @source |
|---|---|---|
| 道具售价 | 道具表 `+5`（**原价**，不打折、不看物价）| `0x445bf1 byte [eax*8 + 0x47fee7]` |
| 卡片售价 | 卡表 `+5` | `0x441f5a byte [edx*8 + 0x47fdef]` |
| 道具回库存 | **仅编号 ≤ 8**（`0x497320 + (编号-1)`）| `0x445bd0 cmp eax,8 / jge`、`0x445bd5 add byte [eax+0x497320], cl` |
| 卡片回库存 | **全部**按卡号回 `0x499197 + 卡号` | `0x441f54 inc byte ptr [edx + 0x499197]` |
| 座驾折算 | `traffic & 3` = 1→道具 5、2→道具 6、3→道具 **12**（故 `0x1f` 工程車 → 12），**先折再卖** | `0x445b79/0x445b81/0x445b89` |
| 下车副作用 | `traffic = 0`、`ndices = 1`（**仅在 traffic ≠ 0 时**做，连重绘 `0x40b93b` 一起跳过）| `0x445b51 je`、`0x445b94`、`0x445b9a` |

### fortune[33] — 酒醉大鬧警局坐牢 %d 天

* **VA**：`0x0044d783`（`0x44d783..0x44d8cf`，332 字节）
* **台词**：`#0218酒醉大鬧警局坐牢%d天`，`%d` = 3（`@source 0x0044d797`: `mov esi,3`）
* **有效 pass**：**pass 1**（`@source 0x0044d795`: `jne 0x44d80b`）
* **范围**：单个 —— 当前玩家
* **气运**：`(1,1)` 倒霉域

```asm
0044d80f  call 0x44b896                        ; (1,1)
0044d82a  mov  ecx, dword ptr [0x48c5b0]
0044d830  cmp  ecx, 1 / jne 0x44d87d
   r==1 → say; player_say(cur, 0, 槽 0x48084a); ★ return（逃過）
0044d87d  cmp  ecx, 2 / jne 0x44d8a2
   r==2 → say; 0x48c5b4 *= 2                    ★ 天数加倍
0044d8a9  call 0x441210                         ; 取槽位
0044d8b4  je   0x44d800                          ; -1 → 结束
0044d8c2  call 0x43d593                          ; ★ add_player_days_in_prison(slot, days)
```

* `0x43d593(player, days)` 写 `player.days_in_prison (0x496b9c)`（已反汇编确认）。

### fortune[34] — 防礙風化坐牢 %d 天

* **VA**：`0x0044d8cf`（`0x44d8cf..0x44d8fd`，46 字节 —— **只是跳板**）
* **台词**：`#0219防礙風化坐牢%d天`（`@source VA 0x00465c53`）
* **天数**：**5**（`@source 0x0044d8e7`: `mov esi,5`）
* 生效段 `jmp 0x44d7a8` ⇒ 完全复用 fortune[33]（含 `(1,1)` 气运判定与加倍）。

### fortune[35] — 走私毒品坐牢 %d 天

* **VA**：`0x0044d8fd`（`0x44d8fd..0x44d92b`，46 字节）
* **台词**：`#0220走私毒品坐牢%d天`（`@source VA 0x00465c69`）
* **天数**：**7**（`@source 0x0044d915`）；生效段 `jmp 0x44d7a8`。

### fortune[36] — 販賣大補帖坐牢 %d 天

* **VA**：`0x0044d92b`（`0x44d92b..0x44d959`，46 字节）
* **台词**：`#0221販賣大補帖坐牢%d天`（`@source VA 0x00465c7f`）
* **天数**：**9**（`@source 0x0044d943`）；生效段 `jmp 0x44d7a8`。

---

## 四、汇总表

| # | VA | 一句话效果 | 范围 | 金额/天数 | 气运域 |
|---|---|---|---|---|---|
| 0 | `0x44be16` | 随机拆自己一块已开发住宅，赔 `level*house_price`，地留给自己 | 单个 | `level*house_price` | - |
| 1 | `0x44bfb1` | 随机征收自己一块空地，赔 `land_price`，`owner=0` | 单个 | `land_price` | - |
| 2 | `0x44c0e8` | `loan += 10000*p`，再理赔 | 单个 | `10000*p` | 罚金 |
| 3 | `0x44c229` | `days_rejected_by_bank += 30` | 单个 | 30 天 | 罚金 |
| 4 | `0x44c2c2` | 盗领其他每人 `round(存款*0.1)` | 全体他人 | 10% | - |
| 5 | `0x44c3b7` | 向其他有牌者各收 1 张卡 | 全体他人 | 1 张/人 | - |
| 6 | `0x44c5d8` | 消失 3 天，差旅费 `2000*days*p` | 单个 | 3 天 | 倒霉 |
| 7 | `0x44c6ed` | 同上，动画不同 | 单个 | 3 天 | 倒霉 |
| 8 | `0x44c7ef` | 每只股票 `-round(amount*0.1)` | 单个 | 10% | 罚金 |
| 9 | `0x44c91f` | 全部股票卖出变现 | 单个 | 全部 | 罚金 |
| 10 | `0x44ca46` | 失去载具（`traffic_method=0`，`ndices=1`） | 单个 | - | 倒霉 |
| 11 | `0x44cb53` | 同 10，另一个计数器 | 单个 | - | 倒霉 |
| 12 | `0x44cc53` | 住院 3 天 | 单个 | 3 天 | 倒霉 |
| 13 | `0x44cd6c` | 同 12，文案不同 | 单个 | 3 天 | 倒霉 |
| 14 | `0x44cd99` | 罚款 `3000*p` | 单个 | `3000*p` | 罚金 |
| 15 | `0x44cf1e` | 罚款 `3000*p`；`tm==0` 时改走 12 | 单个 | `3000*p` | 罚金 |
| 16 | `0x44d06d` | 罚款 `3000*p`；`tm==0` 时改走 12 | 单个 | `3000*p` | 罚金 |
| 17 | `0x44d0d6` | **仅自己**付 `6000*p` 给政府 | 单个 | `6000*p` | 罚金 |
| 18 | `0x44d1a5` | 罚款 `600*p` | 单个 | `600*p` | 罚金 |
| 19 | `0x44d1e0` | 罚款 `1500*p` | 单个 | `1500*p` | 罚金 |
| 20 | `0x44d224` | 得 `1000*p`（进现金） | 单个 | `1000*p` | 奖金 |
| 21 | `0x44d33b` | 得 `2000*p` | 单个 | `2000*p` | 奖金 |
| 22 | `0x44d3db` | 得 `3000*p` | 单个 | `3000*p` | 奖金 |
| 23 | `0x44d41e` | 失 `1000*p` | 单个 | `1000*p` | 罚金 |
| 24 | `0x44d462` | 失 `2000*p` | 单个 | `2000*p` | 罚金 |
| 25 | `0x44d4a6` | 得 `10000*p` | 单个 | `10000*p` | 奖金 |
| 26 | `0x44d4e7` | 失 `8000*p` | 单个 | `8000*p` | 罚金 |
| 27 | `0x44d52b` | 得 `4000*p` | 单个 | `4000*p` | 奖金 |
| 28 | `0x44d56e` | 得 `6000*p` | 单个 | `6000*p` | 奖金 |
| 29 | `0x44d5b1` | 得 `8000*p` | 单个 | `8000*p` | 奖金 |
| 30 | `0x44d5f4` | 失 `5000*p`（付政府） | 单个 | `5000*p` | 罚金 |
| 31 | `0x44d636` | 得 `5000*p` | 单个 | `5000*p` | 奖金 |
| 32 | `0x44d677` | `points += 道具价 + 卡片价` | 单个 | 变卖价 | 倒霉 |
| 33 | `0x44d783` | 坐牢 3 天 | 单个 | 3 天 | 倒霉 |
| 34 | `0x44d8cf` | 坐牢 5 天（复用 33） | 单个 | 5 天 | 倒霉 |
| 35 | `0x44d8fd` | 坐牢 7 天（复用 33） | 单个 | 7 天 | 倒霉 |
| 36 | `0x44d92b` | 坐牢 9 天（复用 33） | 单个 | 9 天 | 倒霉 |

`p` = `price_index`（`0x4990e8`）。全部金额都是 `常数 * p` 或 `round(比例 * 基值) * p`，
**没有一处使用浮点价格指数**。

---

## 五、未决清单

1. **`fortune_check` 的 `case 15` 转录错误已确认**，见 §6 —— 这不是未决，是已结案。
2. ~~**`0x4991b8` 的语义未决**~~ ✅ 已解 = **地图编号（0..3）**（见 `save-scalars.md`）。它是 `word`（16 位），
   `fortune_events` 用它给 `v ≥ 33` 的事件选「第二套表块」，但静态表只到索引 48、
   分派表只有 37 项，`word[0x4991b8] != 0` 会越界。**本文件只描述 `word[0x4991b8] == 0` 的路径。**
3. **`0x4991b6` 的语义未决**：`fortune_check` case 33..36 要求它 `== 0` 才可行。
   `csrc` 称其为 `game_stage`，但未从汇编确认（0x4991b6 有 46 处引用）。
4. **`0x441210(player)` 未决**：返回 `-1` 的确切条件（内部走 `0x4413ad(player,0x15)` 与 `0x444bb2`）。
   它决定了「坐牢/就医/消失」是否真的落到某个角色身上。
5. **`0x428e23(player, stock_i, amount, mode)` 未决**：只确认了参数形状与
   `mode=0`（fortune[8] 扣减）/`mode=1`（fortune[9] 全部卖出）的用法；函数内部（价格、手续费）未展开。
6. **`0x433b7e(player)`（fortune[2] 冒贷后调用）未决**：
   函数头读 `player+0x2c` 与配置日期（`0x497160`），疑似「按日期结算的某种金融操作」，未展开。
7. ~~`0x40cd07(player)`~~ **✅ 已结案（2026-09-18）**：它就是 **`wreck_vehicle`（毁座驾／回合末回收交通工具）**
   —— `traffic_method & 3` 为 1/2 时把**道具 5 機車 / 6 汽車**退回全局库存（`0x497324`/`0x497325`），
   `+0x11 = 0`、`+0x12 = 1`，已关押/住宿者**免疫**，`who_plays == 0` 时走 `0x40cc56` 挪位。
   差分：`tests/test_vehicle_wreck.py`（17/17）。fortune[12] 就医前调它 = 「先毁车再送医」。
   **仍属未决**的是 `0x44f354` / `0x44f42d` / `0x44f567`（表现层飘字）：三者开头都做
   `imul price_index, 0x2328`（=9000）再与金额比较，应为「按金额分档播放不同飘字/动画」，未逐条穷举分档。
8. ~~**`0x445b3f` / `0x441f21`（fortune[32] 的变卖价）未决**：未确认它们是否**顺带清空**
   玩家的卡片与道具。~~ **✅ 已结案（2026 本轮）**：**会清空**（13 道具槽 / 15 手牌槽逐个写 0），
   售价 = 表项 `+5` 原价，道具 ≤8 回商店库存、卡片全回；通道 2 `tests/test_sell_all.py`（35/35）。
9. ~~`0x497324` / `0x497325`（fortune[10]/[11] 的 `inc byte`）~~ **✅ 已结案（2026-09-18）**：
   它们是**全局道具库存** `0x497320` 的第 5/6 格 —— 即**道具 5 機車 / 6 汽車**
   （`@source` 存档侧 `save-writer.ts`：存档下标 = 道具号 − 1）。
   fortune[10]「機車被偷」/fortune[11]「汽車撞毀」那一记 `inc` = **把车退回全局库存**，
   与 `0x40cd07`（毁座驾）同一套口径。差分：`tests/test_vehicle_wreck.py`（17/17）。
   仍未决的只剩 `0x4491b8`。
10. **`0x43bde5`（新闻侧的拍卖）与命运无直接关系**，此处不重复。
11. **魔法屋那条「连抽 3 次命运」的分支所属效果编号未逐一追到底**（只确认了循环本身）。

---

## 六、与既有结论的对照（含 ★ 转录错误复核）

### 6.1 ★ `fortune_check` case 15 的 `*v = 14` vs `*v = 15` —— 复核结论：**`csrc` 转录错误**

**既有说法**：`rich4-re/csrc/fortune.c` 的 `fortune_check()` 中，case 15 分支写成

```c
case 15:
    ch = players[current_player].traffic_method;
    if (ch > 2) return 0;
    if (ch == 0) { *v = 15; }      /* ← 既有说法指这里是错的 */
    else if (ch == 2) { *v = 16; }
    return 1;
```

**汇编真值**（`@source VA 0x0044bdd1` 起，逐条）：

```asm
0044bdd1  mov      ch, byte ptr [eax + 0x496b79]   ; ch = traffic_method
0044bdd7  cmp      ch, 2
0044bdda  ja       0x44be0d                        ; tm > 2 → edi = 0 → 返回 0
0044bddc  test     ch, ch
0044bdde  jne      0x44bde8                        ; tm != 0 → 走 tm==2 判别
0044bde0  mov      dword ptr [edx], 0xe            ; ★★★ *v = 0x0E = 14  （不是 15！）
0044bde6  jmp      0x44be0f                        ; 返回 edi = 1
0044bde8  cmp      ch, 2
0044bdeb  jmp      0x44bdc7                        ; 共用 case 14 的尾巴
0044bdc7  jne      0x44be0f                        ; tm == 1 → *v 保持 15，返回 1
0044bdc9  mov      dword ptr [edx], 0x10           ; tm == 2 → *v = 16
```

* `0x0e = 14`，`0x0f = 15` —— **`0x44bde0` 处的立即数确实是 `0x0e`**。
* **`csrc` 的 `*v = 15` 是转录错误，正确值为 14。**

**旁证（三重独立一致）**

1. **同族一致性**：case 14（`0x44bda8`）在 `tm==1` 时写 `0x0f`、`tm==2` 时写 `0x10`；
   case 16（`0x44bded`）在 `tm==0` 时写 `0x0e`、`tm==1` 时写 `0x0f`。
   若 case 15 的 `tm==0` 写成 15（= 自己），它就会与 case 16 的 `tm==0 → 14` **矛盾**，
   也与 §2.2 的「同族变体归并」结构矛盾。
2. **函数体自保**：`fortune_call_table[15]`（`0x44cf1e`）开头就是

```asm
0044cf2f  cmp  byte ptr [eax + 0x496b79], 0
0044cf36  jne  0x44cf4d
0044cf40  call 0x44cc53            ; traffic_method == 0 → 转 fortune[12]（掉進水溝就醫）
```

   —— 若 `tm==0` 时 `*v` 被改成 15（机车版），这个兜底就成了「自己调自己」，
   而它实际调的是 **12 号**。这与「case 15 在 `tm==0` 时应归并到 14」的设计**方向一致**
   （12 与 14 同属「行人」侧：12 是摔伤就医版、14 是罚款版）。
3. **表结构**：`fortune_pic_group[15] = 0x01ec`、`[14] = 0x01eb`、`[12] = 0x01e9` —— 图片号连续，
   说明 12/13、14/15/16 是两条平行族（就医族、罚款族），归并目标只能是族内的「行人」项。

> 复刻要点：`fortune_check` 的 case 15 必须写 `*v = 14`（`tm == 0` 时）。
> 只改这里、不改其他，就能让「行人被开未戴安全帽罚单」这种错配消失。

### 6.2 `fortune_check` 的其余分支 —— 复核结论：**与 `csrc` 一致**

| 分支 | `csrc` 写法 | 汇编 | 结论 |
|---|---|---|---|
| 0 / 1 | `hlands[i].owner == current_player+1` 且 `level != 0` / `== 0` | `0x44bc12` / `0x44bc51` | ✅ 一致（**只查住宅用地，不查设施**） |
| 5 | `Σ_{i≠cur} player_cards_num(i) != 0` | `0x44bc5e..0x44bc82`（`call 0x441262`） | ✅ |
| 8 / 9 | `player_stocks[cur*12+j].amount != 0` | `0x44bc84..0x44bcac` | ✅ |
| 10 / 11 | `tm ∈ {1,2}`，`tm==2 → 11` / `tm==1 → 10` | `0x44bcb1` / `0x44bcf4` | ✅ |
| 12 / 13 | `tm ∈ {0,1}`，`tm==1 → 13` / `tm==0 → 12` | `0x44bd35` / `0x44bd76` | ✅ |
| 14 / 16 | `tm ≤ 2`，映射到 14/15/16 | `0x44bda8` / `0x44bded` | ✅ |
| 33..36 | `game_stage == 0` | `0x44be03: cmp word [0x4991b6],0 / je 返回1` | ✅ 行为一致（`game_stage` 即 `word[0x4991b6]`；命名未证实，见 §5） |
| default | `return 1` | `0x44be0f: mov eax,edi`（`edi` 全程为 1） | ✅ |

### 6.3 `fortune_data_idx[49]`（`csrc`）vs `0x475fb4` —— 复核结论：**逐项一致**

本轮把 `0x475fb4` 的 49 个 uint16 全部读出并与 `csrc/fortune.c` 的 `fortune_data_idx[49]` 比对，
**49/49 完全相同**（字节级）。

### 6.4 「命运事件如何被触发」的既有说法

| 既有说法 | 复核 | 证据 |
|---|---|---|
| 由 node `+0x24 == 3` 触发 | ✅ 确认 | `0x4198b2` 跳表 `0x4197e9[3] = 0x41b128` → `call 0x44db81` |
| 与新闻共用同一跳表 | ✅ 确认 | 同表相邻两项（2 = 新闻，3 = 命运） |
| 「魔法屋也能触发命运」 | ✅ 确认并量化 | `0x431dba..0x431dc5`：`for (i=0;i<3;i++) fortune_events()` |

### 6.5 本轮新发现（既有文档未提及）

1. **`fortune_check` 会改写事件号**，且改写发生在「选图之前」——
   因此 `fortune_order` 里存的是「族首」（如 14），实际播放的是「族内变体」（如 16）。
2. **`fortune_events` 的面板 sleep 是 1600 ms**（`0x640`），随后 `0x4528b9(800)`；
   新闻是 2400 ms（`0x960`）。两者不是同一个常数。
3. **`0x44ba63` 的第 3 个参数在原函数内未被读取**（`0x44bacc` 读的是 arg0）——
   `csrc/fortune.c` 未记录这一点。
4. **`0x40d375(slot, days, kind)` 是「消失 N 天 + 收取差旅费 `2000*days*p`」的复合操作**，
   不是单纯的「设置天数」；fortune[6]/[7] 的隐藏成本在此。
5. **fortune[17]「請所有人吃大餐」实际只向当前玩家收 `6000*p` 给政府池**，与文案不符。
6. **fortune[8]/[9]/[32] 的 `r==2` 不加倍**（只有 fortune[2]/[6]/[7]/[12..16]/[17]/[20..31]/[33..36] 会加倍）。
   即「神明作祟」对不同事件的效果并不统一。

---

## 附：本文件与 `news.md` 的交叉点

| 共享对象 | `news.md` 中的编号 | `fortune.md` 中的编号 |
|---|---|---|
| 落点跳表 `0x4197e9` | type 2 → `0x44b6df` | type 3 → `0x44db81` |
| 资金原语 | `0x41d2c6` / `0x41d3f4` | 同 |
| `0x44b896`（气运/神明判定） | 未使用 | 几乎所有加减事件 |
| `0x44ba63`（保险理赔） | 未使用 | fortune[2]/[6]/[7]/[14]/[15] 等 |
| `0x4528b9`（等待） | 用作 300 / 500 ms | 用作 300 / 500 / 800 ms |
| `0x4990e8 price_index` | 全部金额公式 | 全部金额公式 |
