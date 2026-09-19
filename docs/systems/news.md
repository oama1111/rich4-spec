# 新闻事件（news events，36 项）

> 真值：`../../../Rich4/rich4.exe`（v3.11，ImageBase 0x400000）。
> 本文件所有 `@source` 均为**原版虚拟地址（VA）**，全部结论来自对 exe 的实际反汇编。
> 不使用 `rich4-re/csrc/news.c`（2018 旧版）作为依据；仅在与它冲突处引用它以便记录差异。

## 本文件的验证方式与证据级别

| 级别 | 含义 | 本文件中的用法 |
|---|---|---|
| **A-反汇编** | 用 `capstone` 从 `rich4.exe` 实际反汇编得到，指令与二进制逐字节对应 | **本文件全部逐事件结论**。生成脚本见 `tools/scratch/event_dump.py`（按分派表地址序确定每个处理函数的边界，再逐条反汇编） |
| **A-数据** | 直接读 exe 数据段的字节 | 分派表 `0x475e24`、分类表 `0x475eb4`、标题指针表 `0x475ed8`、字符串字面量、x87 双精度常量 |
| **B** | `rich4-re/asm/rich4_news.asm`（2026 人工还原） | **仅用于交叉印证**（见 §6）。凡与 A 冲突一律以 A 为准 |
| **C** | `rich4-re/csrc/news.c`（2018） | 只用于登记差异，不作为依据 |

覆盖率：**36/36 项**。每一项都给出了处理函数 VA、其完整地址范围（到下一条分派表项为止）、关键指令摘录。
凡未追到底的被调函数语义，一律标「未决」，不做推测。

判读约定：

* 「pass 0 / pass 1」= 分派器对该处理函数的**两次调用**（第二参数 0 与 1），见 §1.3。
* 玩家结构基址 `0x496b68`，步长 `0x68`；下文的 `player[N].xxx` 是 `0x496b68 + N*0x68 + off` 的简写。
* 「范围」列含义：全体（对局中所有玩家）/ 单个（当前行动玩家）/ 随机（随机挑一块地或一家公司）。

---

## 一、触发接线：新闻在回合流程的哪一步被调用

### 1.1 分派表与入口

| 对象 | VA | 说明 |
|---|---|---|
| `events_calls_table[36]` | `0x475e24` | 36 项函数指针，**地址序排列**（已核对相邻项） |
| `news_events()` | `0x44b6df` | 新闻事件总入口，返回前无参数、无返回值 |
| 成功判定 `check_news(idx)` | `0x448be2` | 返回 1 = 该事件当前可行，0 = 不可行 |
| 顺序表初始化 | `0x448b81` | 生成 `0..35` 的随机排列写入 `0x499090`，并把 `0x4990e0` 清零 |
| 顺序表 | `0x499090`（`uint8[36]`，在 `.bss`，**文件里没有初值**） | `news_order[]` |
| 游标 | `0x4990e0`（dword） | `news_cur_idx`，0..35 循环 |
| 分类表 | `0x475eb4`（`uint8[36]`） | 事件 → 标题类别（0..5） |
| 标题指针表 | `0x475ed8`（**仅 6 项** dword，`0x475ed8..0x475eef`） | 6 个类别名，紧接着就是 `fortune_call_table`（`0x475ef0`） |
| 图片索引 | `idx + 441`（=0x1B9+i） | `read_mkf(mkf_data, idx+441, ...)` |

`0x475eb4` 的实际内容（`@source VA 0x00475eb4`，36 字节）：

```
[ 0.. 5] = 0   [ 6..13] = 1   [14,15] = 2   [16,17] = 3   [18..21] = 4   [22..35] = 5
```

`0x475ed8[0..5]`（`@source VA 0x00475ed8`）依次为：
`無責任新聞` / `政府公告` / `社會新聞` / `路況報導` / `氣象報導` / `財經新聞`。

### 1.2 调用点：落在 type==2 的格子上

节点表基址 `0x498e80`（`map_node_ptr`），步长 **0x28**。
「踩到格子」总处理后段的跳表分派（函数起始 `0x41982d`）：

```asm
00419837  mov   edx, dword ptr [esp + 0x10c]      ; 参数 = node_id
00419848  mov   edx, dword ptr [0x498e80]         ; map_node_ptr
00419850  mov   dx, word ptr [eax + 0x20]         ; node+0x20 : 该格携带的土地/设施编号
0041985b  mov   ebx, dword ptr [eax + 0x24]       ; node+0x24 : ★ 格子类型
0041985e  and   ebx, 0xff
004198a9  cmp   ebx, 0x10
004198ac  ja    0x41b3d0                         ; type > 16 → 什么都不做
004198b2  jmp   dword ptr [ebx*4 + 0x4197e9]      ; ★ 17 项跳表
```

`@source VA 0x004197e9`（跳表，17 项 dword）与两项关键目标：

| type | 目标 | 行为 |
|---|---|---|
| 0 | `0x4198b9` | 普通土地（唯一走地价/过路费逻辑的分支） |
| **2** | `0x41b11e` | **`call 0x44b6df` → 新闻事件** |
| **3** | `0x41b128` | **`call 0x44db81` → 命运事件** |
| 1 | `0x41b3d0` | 直接返回（返回码保持 `byte[esp+0xf4]` 初值 `0x80`，命中新闻/命运后改为 `0x88`） |

```asm
0041b111  mov   byte ptr [esp + 0xf4], 0x88
0041b119  jmp   0x41b3d0
0041b11e  call  0x44b6df          ; ★ 新闻
0041b123  jmp   0x41b3d0
0041b128  call  0x44db81          ; ★ 命运
```

调用链（`call` 逐层已验证）：

```
玩家行动流程的跳表分支 0x418d88 / 0x40d889
  → 0x418e7f                                   ; 移动结束判定
       push 1 / call 0x40c912                  ; 该函数返回非 0 才继续
       ax = player[current].node_id (+0x0c)     ; mov ax,[eax+0x496b74]
       call 0x41982d(node_id)                  ; ★ 踩格子总处理
          → jmp [type*4 + 0x4197e9]
              type==2 → 0x44b6df  news_events
              type==3 → 0x44db81  fortune_events
```

即在「**当前玩家移动结束 → 结算落点**」这一步。新闻与命运是**同一处跳表的相邻两项**，
接线位置完全相同，差别只在节点类型字节 `node+0x24` 是 2 还是 3。

> 复刻接线点：实现「落点结算」时，把 `node[+0x24]` 的 2/3 分别接到 `news_events()` / `fortune_events()` 即可；
> 注意两函数都**自带整个事件面板的显示与 2.4s（news）/1.6s（fortune）等待**，不能放在纯运算层。

### 1.3 `news_events()` 的两次调用语义（`@source VA 0x0044b6df`）

```asm
0044b718  mov   ebx, dword ptr [0x4990e0]        ; news_cur_idx
0044b71e  mov   bl, byte ptr [ebx + 0x499090]    ; ★ idx = news_order[news_cur_idx]
0044b724  and   ebx, 0xff
0044b72a  push  ebx
0044b72b  call  0x448be2                         ; ★ check_news(idx)
0044b730  mov   edi, eax
0044b735  mov   ebp, eax
0044b74f  cmp   edi, 1
0044b752  jne   0x44b7c7                         ; 不可行 → 只推进游标
0044b75a  lea   edi, [ebx + 0x1b9]              ; mkf_data 图片号 = idx + 441
0044b796  movzx edi, byte ptr [ebx + 0x475eb4]   ; 标题类别
0044b79d  mov   eax, dword ptr [edi*4 + 0x475ed8] ; → 类别名
0044b7af  call  0x44fabc                         ; draw_text
0044b7b7  mov   dword ptr [esp + 0x10], ebx      ; 记住 idx
0044b7bb  push  0
0044b7bd  call  dword ptr [ebx*4 + 0x475e24]     ; ★★ 处理函数(idx, 0)  —— pass 0
0044b7c7  mov   edx, dword ptr [0x4990e0]
0044b7cd  inc   edx
0044b7ce  mov   dword ptr [0x4990e0], edx
0044b7d4  cmp   edx, 0x24
0044b7d7  jne   0x44b7e1
0044b7d9  xor   ebx, ebx
0044b7db  mov   dword ptr [0x4990e0], ebx        ; 36 回绕到 0
0044b7e1  test  ebp, ebp
0044b7e3  je    0x44b718                         ; ★ 不可行 → 继续找下一个
0044b862  push  0x960
0044b867  call  0x4544f6                         ; sleep 2400 ms
0044b86f  mov   eax, dword ptr [esp + 0x10]
0044b873  push  1
0044b875  call  dword ptr [eax*4 + 0x475e24]     ; ★★ 处理函数(idx, 1)  —— pass 1
```

要点：

1. **事件由随机顺序表决定，不由格子决定**。格子只负责「触发一次新闻」。
2. **游标只前进一格**；不可行的事件被跳过（且跳过的同时游标已经推进）。
   因此「本次显示的是第几个事件」= 从 `news_order[news_cur_idx]` 起第一个 `check_news()==1` 的项。
3. 处理函数**被调用两次**：`arg==0` 在面板显示阶段（sleep 之前），`arg==1` 在 sleep 之后。
   每个事件**只在其中一次真正改状态**，另一次只画版面。逐事件标注见 §3，全表如下
   （已用脚本对 36 个处理函数逐个判定「`arg!=0` 的跳转目标是否为函数出口」得到）：

   | 生效 pass | 事件号 |
   |---|---|
   | **pass 0**（sleep 之前） | 0, 1, 2, 3, 16, 17, 22, 23, 24, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35 |
   | **pass 1**（sleep 之后） | 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 29 |

   （命运事件的 37 项**全部**是 pass 1 生效，见 `fortune.md` §1.3。）
4. 若 36 个事件全部不可行，`news_cur_idx` 会循环并**无限重试**（`0x44b7e3` 是回边）。
   由于有恒可行的事件（如 6/11/14/18..27/30..34），实际不会死循环。

---

## 二、公共机制（逐事件会引用）

### 2.1 `check_news(idx)`（`@source VA 0x00448be2`，215 条指令）

`0x448be2` 是二分查找树，`edi` 是返回值（初值 1），`esi` 是各循环的命中标志。

```asm
00448be2  push ebx / push esi / push edi / push ebp
00448be6  mov  ebx, dword ptr [esp + 0x14]     ; idx
00448bea  mov  edi, 1                          ; 默认可行
00448bef  xor  esi, esi
00448bf1  cmp  ebx, 9      / jb ... / jbe 0x448d54
...
00448ec3  mov  eax, edi   / pop ... / ret      ; ★ 单一出口，返回 edi
```

逐分支核对结果（**与 `csrc/news.c` 的 case 分组逐组一致，复核结论：无误**）：

| 事件号 | 分支 VA | 可行条件（全部为「存在性」判定） |
|---|---|---|
| 0, 1 | `0x448c99` | `dword[0x496b30] != 0` —— **至少 1 人在狱**（按 dword 一次读 4 个标志字节） |
| 2, 3 | `0x448cab` | `dword[0x496b60] != 0` —— **至少 1 人住院** |
| 4, 5, 15 | `0x448cb4` | 存在 `land.level(+0x1a) != 0` 或 `facility.level(+0x1a) != 0`（**有已开发建筑**） |
| 6 | 默认 | 恒可行 |
| 7 | `0x448d0a` | 存在 `land.owner(+0x19) == 0` 或 `facility.owner(+0x19) == 0`（**有无主地**） |
| 8, 9, 12 | `0x448d54` | 存在 `land.owner != 0` 或 `facility.owner != 0`（**有已售出地产**） |
| 10, 13 | `0x448da5` | 存在对局中玩家，其 12 只股票中任一只 `dword[0x4971a0 + player*0x60 + i*8] != 0` |
| 11 | 默认 | 恒可行 |
| 14 | 默认 | 恒可行 |
| 16 | `0x448def` | 存在对局中玩家且 `traffic_method(+0x11) == 0`（**有人步行**） |
| 17 | `0x448e19` | 存在对局中玩家且 `traffic_method != 0`（**有人乘车**） |
| 18..27 | 默认 | 恒可行 |
| 28 | `0x448e43` | 存在 `i∈[0,12)` 使 `byte[0x496980 + i*0x24 + 6] != 0`（**有停牌股票**） |
| 29 | `0x448e64` | 存在 `on_map_commercial[+0x18] != 0` 且 `0x40d73f(owner-1) == 1`；`0x40d73f(p)` = `who_plays(p)!=0 && days_in_hotel(p)==0` |
| 30..34 | 默认 | 恒可行 |
| 35 | `0x448e9c` | 存在 `on_map_commercial` 使 `dword[+0x28] > 10000` |
| 其它/越界 | 默认 | 恒可行 |

注意 0/1 与 2/3 用的是 `cmp dword ptr [...]`，**一次覆盖 4 个玩家的标志字节**，
所以「至少一人」而不是「指定某人」。

### 2.2 资金原语（本文件多处引用）

**`pay_money(payer, payee, amount, flags)` — `@source VA 0x0041d2c6`**

```asm
0041d2c6  mov  esi, dword ptr [esp + 0x14]   ; arg0 = payer
0041d2ce  mov  edi, dword ptr [esp + 0x18]   ; arg1 = payee
0041d2d2  mov  ebx, dword ptr [esp + 0x1c]   ; arg2 = amount
0041d2d6  cmp  esi, 0x64 / jle 0x41d2f3      ; payer > 100 → 视为商业实体 (payer-100)*0x34
0041d2f6  test byte ptr [esp + 0x20], 4      ; flags bit2=0x4 → 先从 money_in_bank 扣
0041d303  sub  ecx, ebx  / mov [eax+0x496b88], ecx
0041d30d  jge  0x41d37e
0041d313  mov  edx, ecx / add [eax+0x496b84], edx   ; 银行不够 → 差额从现金补
0041d337  jge  0x41d375 / xor ebx, ebx       ; 仍不够 → 实付额截断到 0（不会负债）
0041d375  push esi / call 0x40cd87           ; 破产检查
0041d381  add  dword ptr [eax + 0x496bc4], ebx   ; player.monthly_paid += 实付额
0041d388  cmp  edi, -1 / jne 0x41d394
0041d38c  add  dword ptr [0x499080], ebx      ; payee == -1 → 进「银行/政府」池
0041d394  cmp  edi, 0x64 / jle 0x41d3af       ; payee > 100 → 商业实体
0041d3b2  test byte ptr [esp + 0x20], 1      ; flags bit0=1 → 收进现金，否则进银行
0041d3b9  add  dword ptr [eax + 0x496b84], ebx
0041d3ca  add  dword ptr [eax + 0x496bc8], ebx   ; player.monthly_received += 实收额
```

* 参数顺序（cdecl，右到左压栈）：`pay_money(payer, payee, amount, flags)`。
  — 待裁决点：`payer <= 100` 时按**玩家下标**处理（含 100 本身），`> 100` 时按**商业实体下标**处理。
* `payee == -1` 表示「政府/银行」。
* `ebx` 在扣款失败时被改写为**实际支付额**，因此 `monthly_paid/monthly_received` 记的是实付/实收。

**`add_money(player, amount, flags)` — `@source VA 0x0041d3f4`**

```asm
0041d400  test byte ptr [esp + 0x10], 1      ; flags bit0=1 → 现金，否则银行存款
0041d407  add  dword ptr [eax + 0x496b84], ecx
0041d418  add  dword ptr [eax + 0x496bc8], ecx   ; monthly_received
```

**`update_player_info_window(x, y, mode)` = `0x41d476`**（本文件多处用于刷新飘字）。
**`0x41d433(player)`**：临时把 `current_player` 切到 `player` 再重绘玩家信息条，随后恢复。

### 2.3 建筑等级修改器 `0x40ab4a(id, mode)`（`@source VA 0x0040ab4a`）

新闻里「拆房 / 受损 / 流失」全部走它，是本系统最关键的共享语义：

```asm
0040ab56  cmp esi, 0x7d0 / jle 0x40abdb      ; id ∈ (0x7d0,0xfa0) → 住宅用地 land[+1]，stride 0x34
0040ab7e  cmp ebx, 1 / jb / jbe / cmp ebx,2
    mode 0 → 等级 -1；若 type(+0x18) != 0（商業用地）→ level=0 且 type=0
    mode 1 → owner(+0x19)=0, level=0, type=0, flast(+0x30)=0, call 0x40a4e1(0)  ★ 完全清除
    mode 2 → 等级直接置 0（若原等级非 0）
0040abdb  cmp esi, 0xfa0 / jle ... / cmp esi,0x1770  ; id ∈ (0xfa0,0x1770) → 设施 facility[+1]，stride 0x38
    mode 0 → 等级 -1；到 0 则 type=0 并 call 0x40dffa
    mode 1 → owner=0, level=0, type=0, +0x34=0, call 0x40dffa + 0x40a4e1(0)
    mode 2 → 等级置 0
```

* 住宅用地 id 编码 = `land_index + 0x7d0`；设施 id 编码 = `facility_index + 0xfa0`。
* 返回值 1 = 确实改动了。
* **mode 0 对商業用地是「一次打到 0」**（不是单纯 -1）——复刻时不要写成只减 1。

### 2.4 金额公式的书写约定

本文件用 `p` 表示 `price_index`（`@source VA 0x004990e8`）。
原版全部用移位凑乘法（编译器把常数乘法展开），下文给出的倍数是**按指令序列逐条算出**的：

```asm
; 例：news[8] 的 10000*p（@source 0x00449994）
mov edx,[0x4990e8] / mov eax,edx / shl eax,2 / add eax,edx / shl eax,3
sub eax,edx / shl eax,4 / add eax,edx / shl eax,4      ; → 10000*p
```

---

## 三、逐事件规格

> 每节的「范围」= 效果落点；「有效 pass」= 只有该次调用会改状态（另一 pass 只绘制后返回）。
> **生效的 pass 不是统一的**，必须逐个按 §1.3 第 3 点的表来（19 项在 pass 0、17 项在 pass 1）。
> 每节给出的 pass 判定依据都是「`arg != 0` 的跳转目标是否为函数出口」这一条可机械复核的事实。

### news[0] — 獄中囚犯無罪開釋

* **VA**：`0x00448eca`（`0x448eca..0x448f45`，123 字节）
* **台词**：`#0149獄中囚犯無罪開釋`（`@source VA 0x00465424`）
* **有效 pass**：**pass 0**（`@source 0x00448ed0`：`test edx,edx / jne 0x448ec7`，第二参数非 0 直接返回）
* **范围**：全体在狱玩家

**效果 / 顺序**

```asm
00448edc  push 0x465424                      ; "#0149獄中囚犯無罪開釋"
00448eca  ... draw_text(panel+0xc, 0x18, 0x136, str, 0)
00448ef2  xor  ebx, ebx                      ; for (ebx = 0; ebx < 4; ebx++)
00448f01  cmp  byte ptr [ebx + 0x496b30], 0  ; ★ 在狱标志
00448f08  je   0x448efb                      ; 不在狱 → 下一个
00448f31  mov  byte ptr [eax + 0x496b9c], 0x80   ; ★ days_in_prison = 0x80
00448f3a  mov  byte ptr [ebx + 0x496b30], dh     ; 清标志（dh 在 0x448f38 被 xor 置 0）
```

1. 画标题。
2. 对 `ebx = 0..3`：若 `byte[0x496b30+ebx] != 0`，额外画该玩家立绘（x 从 0x148 起，每行 +0x2a），
   然后 `player[ebx].days_in_prison (0x496b9c) = 0x80`，`byte[0x496b30+ebx] = 0`。

**边界**

* `days_in_prison` 写的是**常数 `0x80`**（bit7 置位），而不是 0；清的是 `0x496b30` 数组。
  `0x80` 这个值的语义**未决**：它与 `days_disappearing` 的「MSB = 即将重新出现」是同一形状
  （见 `rich4-re/docs/global_vars.txt` 对 `0x496b9b` 的记载），但本文件没有独立证据证明 `0x496b9c`
  的 bit7 也是该含义。可确定的是：复刻时若只按 `0x496b30` 判断「是否在狱」而忽略 `0x496b9c` 的 bit7，
  表现会与原版不同。
* 无人在狱 → `check_news` 已挡掉（case 0/1），函数体仍会画标题。
* 破产/出局玩家同样会被处理（本函数**不查 `who_plays`**，只看 `0x496b30`）。

### news[1] — 獄中囚犯延長刑期 %d 天

* **VA**：`0x00448f45`（`0x448f45..0x449006`，193 字节）
* **台词**：`#0150獄中囚犯延長刑期%d天`，`%d` **硬编码 3**（`@source 0x00448f5b`: `mov ecx,3`）
* **有效 pass**：**pass 0**（`@source 0x00448f55`: `jne 0x448ffd`）
* **范围**：全体在狱玩家

**效果**

```asm
00448f5b  mov  ecx, 3
00448f68  push 0x46543a                      ; "#0150獄中囚犯延長刑期%d天"
00448fa8  cmp  byte ptr [ebx + 0x496b30], 0  ; 在狱？
00448fdb  mov  dl, byte ptr [esp + 0x80]     ; = 3
00448fe2  mov  dh, byte ptr [eax + 0x496b9c] ; days_in_prison
00448fe8  add  dh, dl
00448fea  mov  byte ptr [eax + 0x496b9c], dh
00448ff0  mov  cl, dh / and cl, 0x7f
00448ff5  mov  byte ptr [eax + 0x496b9c], cl ; ★ 结果 &= 0x7f
```

**边界**：`days_in_prison += 3` 后强制 `& 0x7f`。若原值已含 bit7（`0x80`，见 news[0] 的「已释放」语义），
加 3 再 `&0x7f` 会**丢掉释放标记**——即「延长刑期」会把一个刚被释放的囚犯重新关进去。这是**原版行为**。

### news[2] — 住院中病患提前出院

* **VA**：`0x00449006`（`0x449006..0x449081`，123 字节）
* **台词**：`#0151住院中病患提前出院`（`@source VA 0x00465454`）
* **有效 pass**：**pass 0**
* **范围**：全体住院玩家

```asm
0044903d  cmp  byte ptr [ebx + 0x496b60], 0   ; ★ 住院标志
0044906d  mov  byte ptr [eax + 0x496b9d], 0x80    ; days_in_hospital = 0x80
00449076  mov  byte ptr [ebx + 0x496b60], dh      ; 清标志
```

与 news[0] 完全对称，只是换成 `0x496b60` / `0x496b9d`。
**由此可判定：`0x496b30` = 在狱标志数组，`0x496b60` = 住院标志数组**
（另有独立证据：`0x43d593` 写 `0x496b9c`、`0x43ec3f` 写 `0x496b9d` 并置 `0x496b60=1`）。

### news[3] — 住院中病患延長住院 %d 天

* **VA**：`0x00449081`（`0x449081..0x44913d`）
* **台词**：`#0152住院中病患延長住院%d天`，`%d` 硬编码 3（`@source 0x00449097`）
* **有效 pass**：**pass 0**（`jne 0x448ffd` —— **跳到 news[1] 的收尾**，两函数共用尾部）
* **范围**：全体住院玩家
* **效果**：`days_in_hospital (0x496b9d) += 3`，再 `& 0x7f`（同 news[1]）。

### news[4] — 外星人攻打地球

* **VA**：`0x0044913d`（`0x44913d..0x4492a0`，355 字节）
* **台词**：`#0153外星人攻打地球`（`@source VA 0x00465488`）
* **有效 pass**：**pass 1**（`@source 0x00449150`: `jne 0x449175`）
* **范围**：随机 1 块已开发地产（仅作演出）+ **全体**玩家住院 3 天

```asm
; pass 1
00449177  mov  ebx, 1
0044917c  cmp  ebx, [0x498e98]            ; num_lands
0044918d  cmp  byte ptr [edx+eax+0x1a], 0 ; level == 0 → 跳过
00449194  mov  edx, ebx / add edx, 0x7d0  ; ★ 候选 = land_index + 0x7d0
0044919c  mov  word ptr [esp + esi*2], dx ; 收集候选
...
004491cd  mov  edx, ebx / add edx, 0xfa0  ; ★ 设施候选 = facility_index + 0xfa0
004491dd  call 0x456f2d                   ; rand()
004491e7  idiv esi                        ; % 候选数
00449203  call 0x40af12                   ; 取坐标 (&x,&y)
0044921d  call 0x41d476                   ; update_player_info_window(x,y,2)
0044922d  call 0x40ac7b                   ; (-1, 1, 0x26, 0x64) 演出
00449245  call 0x450441                   ; read_mkf(0x213)
0044925b  call 0x45144f                   ; (0x56, 0x180001, 0x28, 0, img)
0044926e  cmp  ebx, [0x499114]            ; for (ebx = 0; ebx < num_players; ebx++)
00449279  test byte ptr [eax + 0x496b7d], 0x40   ; ★ who_plays & 0x40
00449280  je   0x44928d
00449285  call 0x43ec3f                   ; add_player_days_in_hospital(ebx, 3)
```

**边界**

* 候选集为空（无任何已开发建筑）→ `check_news` case 4/5/15 已挡掉；若绕过则为 `idiv 0` 除零。
* `who_plays & 0x40` 这个掩码很关键：**不是 `who_plays != 0`**。`0x40` 位的含义**未决**
  （与 2026 版 `rich4_news.asm` 一致，故不是我的转写错误）。
  复刻时若写成 `who_plays != 0`，效果范围会比原版大（可能把已出局玩家也送进医院，或反之）。
* 该函数**不检查玩家是否已在医院**，重复触发会累加（`0x43ec3f` 内部处理天数）。

### news[5] — 外星怪獸襲擊 %s，摧毀建築一棟

* **VA**：`0x004492a0`（`0x4492a0..0x4494e0`，576 字节）
* **台词**：`#0154外星怪獸襲擊%s\n摧毀建築一棟`（`@source VA 0x0046549c`），`%s` = 该地产名
* **有效 pass**：**pass 1**（`@source 0x004492b2`: `jne 0x44940d`）
* **范围**：随机 1 块**已开发**地产（地或设施），**完全清除**

```asm
; pass 0 —— 候选收集（★ 只收 level != 0 的已开发地块）
004492d0  cmp  byte ptr [ecx + edx + 0x1a], 0
004492d5  je   0x4492e4                    ; 住宅：level == 0 → 跳过
00449308  cmp  byte ptr [ecx + edx + 0x1a], 0
0044930d  je   0x44931c                    ; 设施：level == 0 → 跳过
; pass 1
0044931f  call 0x456f2d                    ; rand()
00449329  idiv ebx                         ; % 候选数
00449331  mov  dword ptr [0x48c59c], eax   ; ★ 选中的 id（带 0x7d0/0xfa0 偏移）
0044935  / 0x493bb  取名字 (0x457d96 = strcpy)
004493bb  mov  al, byte ptr [edx + eax + 0x19]   ; ★ owner -> 0x48c5a0
00449443  call 0x41d476                    ; 刷新窗口
0044944f  call 0x40ab4a                    ; ★ 0x40ab4a(id, 1) = mode 1 完全清除
00449467  call 0x450441                    ; read_mkf(0x21b) + 0x45144f(0x56,0x80001,...)
0044948e  mov  eax, dword ptr [0x48c5a0]   ; owner
00449495  je   0x4494d5                    ; owner == 0 → 无台词
004494cd  call 0x44ef41                    ; player_say(owner-1, 2, 台词[rand()&1])
```

**效果（唯一状态改动）**：`0x40ab4a(sel, 1)` → 该地块 `owner=0, level=0, type=0, flast=0`，
设施还额外 `+0x34=0` 并 `call 0x40dffa`。即「建筑被摧毁且土地回到无主」。
剩余为**纯表现**（动画、刷新窗口、受害者台词）。

**边界**

* 候选里**包含设施**（`+0xfa0` 段），因此文案说「建築」但可能拆掉的是设施。
* owner 台词用 `player_say(owner-1, 2, ...)`：`2` 是「情境槽」编号，台词取 `0x480856 + char*0x24 + (rand()&1)*4`。

### news[6] — %s 公告地價調漲 30%

* **VA**：`0x004494e0`（`0x4494e0..0x449735`，597 字节）
* **台词**：`#0155%s公告地價調漲３０％`（`@source VA 0x004654bd`）
* **有效 pass**：**pass 1**（`@source 0x004494f2`: `jne 0x4495b5`）
* **范围**：随机选中 1 块地/设施 → **所有同名地产**（含他人的）

**pass 0（掷骰 + 出图）**

```asm
004494f8  mov  ebx, [0x498e98] / add ebx, [0x498e8c]   ; num_lands + num_facilities
00449504  call 0x456f2d / idiv ebx / mov [0x48c59c], edx   ; 0..N-1
0044951c  cmp  edx, [0x498e98] / jge 0x44953a
00449529  lea  edi, [edx + 0x7d1]  / mov [0x48c59c], edi   ; ★ 换算成 land id = index+1+0x7d0
```

**pass 1（改价）**

```asm
0044961b  lea  eax, [ebx + 4] / push eax
0044961f  lea  eax, [edi + 4] / push eax
00449623  call 0x458370                    ; ★ strcmp(land[i].name, sel.name) == 0 才处理
0044963b  push 0x2f440 / push id / push 0xffff / push [0x474938] / call 0x456c0a   ; 表现层
00449650  mov  ax, word ptr [ebx + 0x1c]   ; ★ land_price (uint16)
0044965b  fild dword ptr [esp + 0x94]
00449662  fmul qword ptr [0x4654dc]        ; ★ 常量 1.3（IEEE754 双精度）
00449668  call 0x457dbc                    ; 取整
0044967b  mov  word ptr [ebx + 0x1c], ax   ; 写回 land_price
```

设施分支（`0x449682`）用 `+0x22` 作被改字段，乘同一常量 1.3。

**精确规则**

```
对每一块 land：若 strcmp(land.name, sel.name) == 0  →  land.price(+0x1c) = round(land.price * 1.3)
对每一块 facility：若 strcmp(fac.name, sel.name) == 0 → fac.price(+0x22)  = round(fac.price * 1.3)
```

* 常量 `@source VA 0x004654dc` = `1.3`（字节 `cd cc cc cc cc cc f4 3f`）。
* **只改地价，不改房价、不改租金**。同名的他人地产也会一起涨。
* `0x456c0a(0x474938, 0x2f440, id, 0xffff)` 每次命中都调用一次，应为地图/记录刷新（语义未决，见 §5）。

**边界**

* 只要候选池非空就可行；候选池由 `num_lands + num_facilities` 决定，**不做 level/owner 过滤**。
* 两处 `id` 编码不同：pass 0 存的是 `index+1+0x7d0`（land id）或 `index+1+0xfa0`（facility id），
  pass 1 用 `id` 判断区间并反算下标——复刻时不要混用 `index` 与 `id`。

### news[7] — 公開拍賣 %s，公有土地一處

* **VA**：`0x00449735`（`0x449735..0x4498b3`，382 字节）
* **台词**：`#0156公開拍賣%s\n公有土地一處`（`@source VA 0x004654e4`）
* **有效 pass**：**pass 1**（`@source 0x00449746`: `jne 0x449896`）
* **范围**：随机 1 块**无主**地产 → 触发拍卖

```asm
00449766  cmp  byte ptr [ecx + edx + 0x19], 0   ; owner == 0 才进候选
00449798  // 设施同理（0x498e88, +0x19）
004497c9  mov  dword ptr [0x48c59c], eax        ; 选中 id（0x7d0/0xfa0 编码）
0044985d  push 0x4654e4                          ; "#0156公開拍賣%s 公有土地一處"
; pass 1：
00449896  push 1
00449898  mov  ecx, dword ptr [0x48c59c]
0044989e  push ecx
0044989f  push -1
004498a1  call 0x43bde5                          ; ★ 拍卖(land_or_facility_id, -1, 1)
```

* 本函数**不改地状态**，所有权变更在 `0x43bde5`（拍卖流程）内部发生——该流程未在本次任务范围内，
  未逐条展开，标为**未决**（见 §5）。

**边界**：`check_news` case 7 要求「存在 owner==0 的地产」，否则不可行。
若唯一的无主地已被 player_say/拍卖流程占用，仍会走完（无二次校验）。

### news[8] — 公開表揚第一大地主，%s 獲得 %d 元獎勵

* **VA**：`0x004498b3`（`0x4498b3..0x449a8a`，471 字节）
* **台词**：`#0157公開表揚第一大地主\n%s獲得%d元獎勵`（`@source VA 0x00465501`）
* **有效 pass**：**pass 1**（`@source 0x004498c6`: `jne 0x449a24`）
* **范围**：单个 —— 地产数最多的玩家

**★ 复核点：本条确为「地产统计」——确认**

```asm
004498cc  push 0x10 / push 0 / lea eax,[esp+0x9c] / push eax
004498d7  call 0x456f60                    ; memset(counts[0..3], 0, 16)
004498f5  mov  dl, byte ptr [ecx + edx + 0x19]   ; land.owner (+0x19)
004498ff  je   0x449908                    ; owner == 0 → 不计
00449901  inc  dword ptr [esp + edx*4 + 0x90]    ; ★ counts[owner]++
0044992c  mov  dl, byte ptr [ecx + edx + 0x19]   ; facility.owner
00449938  inc  dword ptr [esp + edx*4 + 0x90]    ; ★ counts[owner]++
00449946  mov  edi, [0x499114]              ; num_players
00449953  cmp  byte ptr [ecx + 0x496b7d], 0      ; 跳过非对局玩家
00449961  mov  esi, dword ptr [esp + ecx + 0x94] ; ★ counts[player+1]
00449968  cmp  edx, esi                     ; best < count ?
0044996a  jge  0x449973
0044996c  mov  edx, esi / mov dword ptr [0x48c59c], eax   ; 更新冠军
```

**精确规则**

1. 遍历 `land[1..num_lands]` 与 `facility[1..num_facilities]`，按 `owner(+0x19)`（1 基）累加计数
   （`counts[0]` 收集无主地但不参与评比）。
2. 在**对局中**玩家（`who_plays != 0`）中取计数**最大**者（`best` 初值 0，`>` 才更新 ⇒ 并列取**第一个**）。
3. 奖励金额（pass 0 算出）：

```asm
; @source 0x00449994
mov edx,[0x4990e8] / mov eax,edx / shl eax,2 / add eax,edx / shl eax,3
sub eax,edx / shl eax,4 / add eax,edx / shl eax,4      ; 10000 * p
mov dword ptr [0x48c5a0], eax
```

   即 **`10000 * price_index`**。
4. pass 1：`0x41d3f4(player, amount, 1)`（**进现金**）、`0x41d476` 刷新、`0x41d433(player)`、`0x44f354(player, amount)`。

**边界**

* `owner` 可取 0..4，代码用 `and edx,0xff` 后直接索引 `counts[owner]`；若 `owner > 4`（数据损坏）会越界写栈。
  `counts` 只有 16 字节（4 项），所以 `owner` 实际只能在 0..4。
* `check_news` case 8 保证至少有一块已售出地产，否则不可行 —— 这点很重要，
  它同时避免了「所有 counts 都是 0 时 `0x48c59c` 保留上一次事件的脏值」这个隐患。

### news[9] — 公開補助土地最少者，%s 獲得 %d 元補助

* **VA**：`0x00449a8a`（`0x449a8a..0x449b9c`，274 字节）
* **台词**：`#0158公開補助土地最少者\n%s獲得%d元補助`（`@source VA 0x00465528`）
* **有效 pass**：**pass 1**（`@source 0x00449a9d`: `jne 0x449a24` —— 复用 news[8] 的 pass 1 收尾）
* **范围**：单个 —— 地产数最少的玩家

**★ 复核点：本条同样确为「地产统计」——确认**

```asm
00449ab2  mov  eax, 1 / ... land 循环：inc dword ptr [esp + edx*4 + 0x90]   ; counts[owner]++
00449ae3  ... facility 循环：同样累加
00449b17  mov  edx, 0x2710                  ; ★ best 初值 10000
00449b32  mov  ecx, eax / shl ecx, 2
00449b37  mov  esi, dword ptr [esp + ecx + 0x94]   ; counts[player+1]
00449b3e  cmp  edx, esi / jle 0x449b49      ; best <= count → 不更新
00449b42  mov  edx, esi / mov dword ptr [0x48c59c], eax  ; 更新最少者
```

* 统计方式与 news[8] **完全相同**（`land.owner` + `facility.owner`），
  只是取**最小**（`best` 初值 10000，`<` 才更新 ⇒ 并列取**最后一个**）。
* 奖励金额：`@source 0x00449b6a` 同型移位序列，末位是 `shl eax,3` ⇒ **`5000 * price_index`**。
* pass 1 收尾复用 news[8]（`jmp 0x4499c1`）：`0x41d3f4(player, amount, 1)` 等。

**边界**：`best` 初值 10000 意味着「地产数 ≥ 10000 的玩家永不被选为最少者」；
原版地图不可能达到，但**不是**严格意义的最小值选择（是「≤ 9999 中的最小」）。

### news[10] — 公開表揚股市第一大戶，%s 獲得 %d 元獎勵

* **VA**：`0x00449b9c`（`0x449b9c..0x449c7c`，224 字节）
* **台词**：`#0159公開表揚股市第一大戶\n%s獲得%d元獎勵`（`@source VA 0x0046554f`）
* **有效 pass**：**pass 1**（`@source 0x00449baf`: `jne 0x449a24`）
* **范围**：单个 —— 持股市值（**股数**）最多的玩家

**★ 补充结论：10 号也是「统计」，但统计对象是股票（与 8/9 的地产统计并列）**

```asm
00449bd6  mov  eax, esi / shl eax,2 / sub eax,esi / shl eax,5     ; player*0x60
00449be2  mov  eax, dword ptr [eax + ebx*8 + 0x4971a0]           ; ★ stock amount
00449be9  add  dword ptr [esp + esi*4 + 0x94], eax               ; 累加到该玩家
00449bfd  ... 求最大（edx 初值 0，> 才更新，并列取第一个）
00449c4a  ... 移位序列 → 10000 * p
```

* 累加的是 `dword[0x4971a0 + player*0x60 + i*8]`（**持股数量**，不是市值）。
* 上限：`stock amount` 为 int32，累加 12 只，可能溢出——原版不检查。
* 奖励 = **`10000 * price_index`**，发放同 news[8]。

### news[11] — 所有人繳交所得稅 5%

* **VA**：`0x00449c7c`（`0x449c7c..0x449de6`，362 字节）
* **台词**：`#0160所有人繳交所得稅５％`（`@source VA 0x00465578`）
* **有效 pass**：**pass 1**（`@source 0x00449c94`: `jne 0x449d9f`）
* **范围**：**全体对局中玩家**（逐个扣款）

```asm
; pass 0：按人算税并画版面
00449cde  imul edx, ebx, 0x68
00449ce1  cmp  byte ptr [edx + 0x496b7d], 0   ; 跳过非对局玩家
00449cee  fild dword ptr [edx + 0x496b84]     ; ★ player.cash
00449cf4  fmul qword ptr [0x4655a4]           ; ★ 常量 0.05
00449cfa  call 0x457dbc                       ; 取整
00449cff  fistp dword ptr [esp + 0x94]
00449d12  mov  dword ptr [esi + 0x48c59c], eax   ; ★ 按玩家存税额外 0x48c59c[player]
00449d42  push 0x465592                       ; "%s繳交%d元"
; pass 1：扣款
00449da1  cmp  ebx, [0x499114]
00449dad  cmp  byte ptr [0x46caf8], 0
00449db4  jne  0x44972a                       ; ★ 全局开关非 0 → 一笔都不收
00449ddb  call 0x41d2c6                       ; pay_money(player, -1, tax, 0)
```

**精确规则**

```
tax[i] = round(cash[i] * 0.05)        // 仅 who_plays != 0；四舍五入由 0x457dbc 完成
if (byte[0x46caf8] == 0)  for each i: if (tax[i] != 0) pay_money(i, -1, tax[i], flags=0)
```

* 常量 `@source VA 0x004655a4` = `0.05`（双精度）。
* `flags = 0` ⇒ 从**现金**扣；现金不足时 `pay_money` 自动吃存款，仍不足则**截断实付额**（不会破产负债）。
* `payee = -1` ⇒ 进 `0x499080`（政府/银行池）。

**边界**

* `tax[i] == 0`（现金 0..9）**跳过**，不产生 0 元交易（`0x449d1a: je 0x449d99`）。
* `byte[0x46caf8] != 0` 时 pass 1 **整段跳过**（一个都不收），但 pass 0 的版面照画 —— 会显示「缴交 0 元」的假象。
* 对局中玩家数只有 `num_players` 个，`0x48c59c[player]` 是 4 项 dword 数组（`0x48c59c` 也被别的新闻当单值用！）
  见 §5「全局复用」。
* **破产玩家仍会被扣**（`pay_money` 里有 `0x40cd87` 破产检查兜底）。

### news[12] — 所有人繳交地價稅 5%

* **VA**：`0x00449de6`（`0x449de6..0x44a029`，579 字节）
* **台词**：`#0161所有人繳交地價稅５％`（`@source VA 0x004655ac`）
* **有效 pass**：**pass 1**（`@source 0x00449dfe`: `jne 0x449fdf`）
* **范围**：全体对局中玩家

```asm
; 地产部分（每块属于该玩家的 land）
00449e9d  mov  bx, word ptr [edx + 0x1e]      ; house_price (uint16)
00449ea3  mov  cl, byte ptr [edx + 0x1a]      ; level (uint8)
00449ea6  imul ecx, ebx                       ; ★ level * house_price
00449eab  mov  bx, word ptr [edx + 0x1c]      ; land_price
00449eb1  add  dword ptr [esp + esi*4 + 0x94], ecx   ; 加上 (level*house + land_price)
; 设施部分
00449ef7  mov  cx, word ptr [edx + 0x24]
00449efd  mov  al, byte ptr [edx + 0x1a]
00449f00  imul ecx, eax                       ; level * fac[+0x24]
00449f05  mov  ax, word ptr [edx + 0x22]
00449f09  add  eax, ecx
00449f0b  add  dword ptr [esp + ebx + 0x94], eax
; 汇总
00449f1b  fild dword ptr [esp + ebx + 0x94]
00449f22  fmul qword ptr [0x4655cc]            ; ★ 0.05
00449f28  call 0x457dbc                        ; 取整
00449f34  mov  eax, [esp+0xa4]
00449f3b  mov  ebp, dword ptr [0x4990e8]       ; price_index
00449f41  imul eax, ebp                        ; ★ × price_index
00449f4b  mov  dword ptr [ebx + 0x48c59c], eax
0044a00d  push 0 / push ebx / push -1 / push esi / call 0x41d2c6   ; pay_money(player,-1,tax,0)
```

**精确公式**

```
base[i] = Σ_{land: owner==i+1} ( land.level * land.house_price(+0x1e) + land.land_price(+0x1c) )
        + Σ_{fac : owner==i+1} ( fac.level(+0x1a) * fac[+0x24]        + fac[+0x22] )
tax[i]  = round(base[i] * 0.05) * price_index           // 先四舍五入到整数，再乘物价指数
```

* `base[i]` 是 int32 累加（`add dword`），`round` 由 `0x457dbc`（x87 → int）完成。
* `* price_index` 是 **imul（32 位有符号）**，可能溢出。

**边界**

* 玩家无地 → `base = 0` → `tax = 0` → **跳过扣款**（`0x449f53: je 0x449fd9`）。
* 与 news[11] 相同：`byte[0x46caf8] != 0` 时 pass 1 全部跳过。
* 设施里用的是 `+0x22`（基准值）和 `+0x24`（每级增量），**不是** land 的 `+0x1c/+0x1e` —— 两个结构字段名不同，勿混。

### news[13] — 所有人繳交證交稅 5%

* **VA**：`0x0044a029`（`0x44a029..0x44a220`，503 字节）
* **台词**：`#0162所有人繳交證交稅５％`（`@source VA 0x004655d4`）
* **有效 pass**：**pass 1**（`@source 0x0044a051`: `jne 0x44a1d9`）
* **范围**：全体对局中玩家

```asm
0044a03f  mov  esi, 0x448b71
0044a044  movsd ... ×4                        ; ★ 从代码段搬 16 字节零 到栈上累积数组（初值 0）
0044a0c6  mov  eax, ebx / shl eax,2 / sub eax,ebx / shl eax,5    ; player*0x60
0044a0d0  mov  edx, [esp+0xa4] / shl edx,3 / add eax,edx         ; + i*8
0044a0dc  cmp  dword ptr [eax + 0x4971a0], 0
0044a0e3  je   ...                            ; 持股 0 → 跳过
0044a0e5  fild dword ptr [eax + 0x4971a0]     ; ★ 持股数
0044a0f2  mov  eax, ecx / shl eax,3 / add eax,ecx                ; i*9
0044a0f9  fmul dword ptr [eax*4 + 0x496994]   ; ★ × 股价 float[0x496994 + i*0x24]
0044a100  fadd dword ptr [esp + ebx*4 + 0x94] ; 累加到该玩家
0044a115  fld  dword ptr [esp + esi + 0x94]
0044a11c  fmul qword ptr [0x4655f4]           ; ★ 0.05
0044a122  call 0x457dbc                       ; 取整
0044a13b  imul eax, edx                       ; ★ × price_index
0044a215  call 0x41d2c6                       ; pay_money(player, -1, tax, 0)
```

**精确公式**

```
value[i] = Σ_{k=0..11} ( stock[i][k].amount * float_price[0x496994 + k*0x24] )   // 单精度浮点累加
tax[i]   = round(value[i] * 0.05) * price_index
```

* `0x448b71` 处 16 字节全 0（`@source VA 0x00448b71`，`movsd` ×4 即 4 个 dword 的零）
  —— 这也是「代码段里夹数据」的一个实例，线性反汇编到此处会失步。
* 股价表 `0x496994`，步长 **0x24**（= 股票结构 0x24 的一部分），单精度 float。

**边界**

* `amount == 0` 的股票跳过（`0x44a0e3`），但**负持股**（若有）会照算。
* 除 `price_index` 外全部是浮点：`value` 累加用单精度，`*0.05` 用双精度，最后取整 —— 复刻时必须按此精度顺序，否则小数尾差会改变 `tax`。
* `byte[0x46caf8]` 开关同 news[11]/[12]。

### news[14] — %s 房屋鬧鬼，地價下跌 30%

* **VA**：`0x0044a220`（`0x44a220..0x44a453`，563 字节）
* **台词**：`#0163%s房屋鬧鬼\n地價下跌３０％`（`@source VA 0x004655fc`）
* **有效 pass**：**pass 1**（`@source 0x0044a232`: `jne 0x44a2f5`）
* **范围**：随机 1 块地/设施（★ **不要求已开发**，候选池 = `num_lands + num_facilities` 全量）→ 所有同名地产

```asm
0044a238  mov  ebx, [0x498e98] / add ebx, [0x498e8c]   ; num_lands + num_facilities
0044a244  call 0x456f2d / idiv ebx
0044a24e  mov  dword ptr [0x48c59c], edx      ; 随机选 land/facility（带 0x7d0/0xfa0 编码）
; ★ 这里没有任何 level/owner 过滤
0044a34f  cmp  esi, [0x498e98] / jg 0x449725
0044a35b  lea  eax, [ebx + 4] / push eax
0044a35f  lea  eax, [edi + 4] / push eax
0044a363  call 0x458370                       ; ★ strcmp 同名
0044a38e  xor  eax, eax / mov ax, word ptr [ebx + 0x1c]    ; land_price
0044a39b  fild dword ptr [esp + 0x94]
0044a3a2  fmul qword ptr [0x46561c]           ; ★ 常量 0.7
0044a3a8  call 0x457dbc                       ; 取整
0044a3bb  mov  word ptr [ebx + 0x1c], ax
```

* 设施分支用 `+0x22`，同一常量 `0.7`（`@source VA 0x0046561c`，字节 `66 66 66 66 66 66 e6 3f`）。
* 与 news[6] 完全对称（1.3 ↔ 0.7）。**只改价，不改租金。**

**边界**：与 news[6] 相同（同名全改、含他人地产、不校验 owner）。
另注意：若某地价已是 1，`round(1*0.7) = 1`（四舍五入），不会归零。

### news[15] — %s 一處民宅瓦斯爆炸，房屋失火

* **VA**：`0x0044a453`（`0x44a453..0x44a5d6`，387 字节）
* **台词**：`#0164%s一處民宅瓦斯爆炸\n房屋失火`（`@source VA 0x00465624`）
* **有效 pass**：**pass 1**（`@source 0x0044a465`: `jne 0x44a50f`）
* **范围**：随机 1 块**已开发**住宅用地 → 等级 -1

```asm
; pass 0：只从 land 中挑 level != 0 的（★ 不含设施）
0044a484  cmp  byte ptr [edx + eax + 0x1a], 0
0044a48b  mov  word ptr [esp + esi*2], bx     ; ★ 存的是裸 land_index（无 0x7d0）
; pass 1：
0044a50f  imul eax, dword ptr [0x48c59c], 0x34
0044a520  mov  bl, byte ptr [eax + 0x19]      ; ★ owner
0044a536  push 0
0044a538  mov  eax, [0x48c59c] / add eax, 0x7d0 / push eax
0044a543  call 0x40ab4a                       ; ★ 0x40ab4a(land_id, 0) → 等级 -1
0044a571  call 0x45144f                       ; read_mkf(0x20f) + 动画 0x57/0x50001
0044a587  call 0x4528b9                       ; sleep 300
0044a58f  test ebx, ebx / je 0x44a5cb
0044a5c3  call 0x44ef41                       ; player_say(owner-1, 2, 台词[rand()&1])
```

**边界**

* **候选池只有住宅用地**（`0x498e84`）——不在 `0xfa0` 段取设施。
* 等级 -1 走 `0x40ab4a` mode 0：若该地是 **商業用地**（`type(+0x18) != 0`），
  一次直接归零并清 `type`（见 §2.3），不是「降到下一级」。
* owner 为 0（无主地）→ 无台词，但仍会改等级。

### news[16] — 豪雨特報，行人休息一回合

* **VA**：`0x0044a5d6`（`0x44a5d6..0x44a657`，129 字节）
* **台词**：`#0165豪雨特報\n行人休息一回合`（`@source VA 0x00465645`）
* **有效 pass**：**pass 0**
  （`@source 0x0044a5e4`: `jne 0x44a5d2`；`0x44a5d2` 是 `pop edi / pop esi / pop ebx / ret`
   —— 与 news[15] 的收尾**共用**，即 `arg!=0` 直接返回，效果在 `arg==0` 路径里）
* **范围**：全体**步行**玩家

```asm
0044a60e  imul ebx, esi, 0x68
0044a611  cmp  byte ptr [ebx + 0x496b7d], 0   ; 非对局玩家 → 跳过
0044a61a  cmp  byte ptr [ebx + 0x496b79], 0   ; ★ traffic_method == 0（步行）才命中
0044a621  jne  0x44a654
0044a64a  mov  byte ptr [ebx + 0x496ba0], 1   ; ★ days_stopping = 1
```

* 效果：`player.days_stopping (+0x38) = 1`（**赋值，不是累加**）。
* 已休息中的玩家会被重置为 1（可能缩短原本更长的天数）。

### news[17] — 交通阻塞，汽車停止一回合

* **VA**：`0x0044a657`（`0x44a657..0x44a6e0`，137 字节）
* **台词**：`#0166交通阻塞\n汽車停止一回合`（`@source VA 0x00465662`）
* **有效 pass**：**pass 0**（`@source 0x0044a665`: `jne 0x44a5d2`，同 news[16]）
* **范围**：全体**乘车**玩家
* 与 news[16] 完全对称，条件取反：`cmp byte [ebx+0x496b79],0 / je skip`（即 `traffic_method != 0`），
  效果同样 `days_stopping = 1`。

### news[18] — %s 強烈地震房屋倒塌

* **VA**：`0x0044a6e0`（`0x44a6e0..0x44a91e`，574 字节）
* **台词**：`#0167%s強烈地震房屋倒塌`（`@source VA 0x0046567f`）
* **有效 pass**：**pass 1**（`@source 0x0044a6f2`: `jne 0x44a7b5`）
* **范围**：随机 1 块地/设施 → **所有同名土地**等级 -1

```asm
0044a823  call 0x458370                       ; ★ strcmp 同名
0044a846  call 0x456c0a                       ; 表现层
0044a84e  mov  cl, byte ptr [ebx + 0x1a]      ; level
0044a851  test cl, cl / je 0x44a86a           ; level == 0 → 跳过
0044a855  mov  ch, cl / dec ch
0044a859  mov  byte ptr [ebx + 0x1a], ch      ; ★ level - 1
0044a85c  cmp  byte ptr [ebx + 0x18], 0       ; type
0044a860  je   0x44a86a
0044a862  mov  byte ptr [ebx + 0x1a], 0       ; ★ 商業用地 → 等级清零
0044a866  mov  byte ptr [ebx + 0x18], 0       ;            且 type 清零
; 设施分支（0x44a8db）
0044a8db  mov  ah, byte [ebx + 0x1a] / test / je end
0044a8e2  mov dl, ah / dec dl / mov [ebx + 0x1a], dl
0044a8e9  jne end
0044a8eb  mov byte [ebx + 0x18], dl / call 0x40dffa    ; 设施到 0 → type=0
0044a8f3  call 0x451985                       ; 拍卖/刷新
0044a8fe  call 0x41d476                       ; update_player_info_window(0,0,1)
0044a90b  call 0x4528b9                       ; sleep 500
```

**精确规则**

```
对被选地块的同名 land：level = max(level-1,0)；若 type != 0（商業用地）→ level=0 且 type=0
对被选地块的同名 facility：level = level-1（level>0 时）；若减到 0 → type = 0 并 call 0x40dffa
```

**边界**

* 与 news[15] 的差别：本事件是**同名全体**，news[15] 只改被选中的一块。
* 只有 `land` 分支处理了 `type`，且是「商業用地直接清零」；`facility` 分支只在**减到 0** 时才清 `type`。
  两者语义不同，不要统一。
* 本函数在最终会调用 `update_player_info_window(0,0,1)` 与 sleep 500 ms（表现层）。

### news[19] — %s 山洪爆發土地流失

* **VA**：`0x0044a91e`（`0x44a91e..0x44ab2c`，526 字节）
* **台词**：`#0168%s山洪爆發土地流失`（`@source VA 0x00465697`）
* **有效 pass**：**pass 1**（`@source 0x0044a930`: `jne 0x44aa44`）
* **范围**：随机 1 块地/设施（**不要求已开发**）→ 完全清除

```asm
0044a94d  idiv ebx / mov [0x48c59c], edx       ; 随机 id（0x7d0/0xfa0 编码）
0044a9f8  mov  al, byte ptr [edx + eax + 0x19] ; owner
0044aa01  mov  dword ptr [0x48c5a0], eax
0044aaa7  push 1
0044aaa9  mov  eax, [0x48c59c] / push eax
0044aaaf  call 0x40ab4a                        ; ★ mode 1 = 完全清除（owner=level=type=0）
0044aab7  call 0x451985                        ; 拍卖/刷新
0044aac2  call 0x41d476
0044aacf  call 0x4528b9                        ; sleep 300
0044aad7  mov  edx, [0x48c5a0] / test / je end
0044ab19  call 0x44ef41                        ; player_say(owner-1, 2, ...)
```

**边界**：候选池把 `num_lands + num_facilities` **全量**入池，**不过滤 level**
（`@source 0x0044a936`：`mov eax,[0x498e98]` / `mov ebx,[0x498e8c]` / `add ebx,eax` / `idiv ebx`，
其后 0x44a95b 的区间判断只用来区分「地」还是「设施」，没有等级判定）。
`check_news` case 19 走默认（恒可行），所以「无主空地被山洪冲走」是正常路径。

### news[20] — %s 超級颱風侵襲，多處房屋受損

* **VA**：`0x0044ab2c`（`0x44ab2c..0x44ac99`，365 字节）
* **台词**：`#0169超級颱風侵襲%s\n多處房屋受損`（`@source VA 0x004656af`）
* **有效 pass**：**pass 1**（`@source 0x0044ab3d`: `jne 0x44ac02`）
* **范围**：随机 1 块地/设施 —— **仅演出，无状态改动**

```asm
0044ab59  idiv ebx / mov [0x48c59c], edx
0044ab7b  mov edx, [0x498e84]                  ; 或设施
0044abbc  call 0x457d96                        ; strcpy 名字
0044abd6  call 0x457110                        ; sprintf "#0169..."
0044ac19  call 0x40af12                        ; 取坐标
0044ac33  call 0x41d476                        ; 刷新窗口
0044ac43  call 0x40ac7b                        ; (-1, 0, 6, 0x64) 演出
0044ac5b  call 0x450441                        ; read_mkf(0x216)
0044ac71  call 0x45144f                        ; (0x59, 0x80001, 0x28, 0, img)
0044ac87  call 0x4528b9                        ; sleep 500
; ★ 全函数到此结束，没有任何 land/facility 字段写入
```

**★ 复核结论：news[20] 是「只播动画、不改状态」的事件。**
文案说「多處房屋受損」，但 exe 里**没有**对应的 `0x40ab4a` / 等级写入调用。
复刻 1:1 应当也**不改状态**（否则会与差分测试不符）。
（此结论已用「函数全部 365 字节逐条读完 + 无任何 `mov [mem],` 写地产字段」双重确认。）

### news[21] — %s 龍捲風侵襲，摧毀房屋一棟

* **VA**：`0x0044ac99`（`0x44ac99..0x44ae89`，496 字节）
* **台词**：`#0170龍捲風侵襲%s\n摧毀房屋一棟`（`@source VA 0x004656d0`）
* **有效 pass**：**pass 1**（`@source 0x0044acab`: `jne 0x44adbc`）
* **范围**：随机 1 块地/设施（不要求已开发）→ 等级 -1

```asm
0044ad70  mov  al, byte ptr [edx + eax + 0x19]  ; owner
0044ad79  mov  dword ptr [0x48c5a0], eax
0044adf5  push 0
0044adf7  mov  edi, [0x48c59c] / push edi
0044adfe  call 0x40ab4a                         ; ★ mode 0 = 等级 -1
0044ae3d  call 0x4528b9                         ; sleep 300
0044ae4a  mov  eax, [0x48c5a0] / test / je end
0044ae84  jmp  0x44ab10                         ; 复用 news[19] 的 player_say
```

**边界**：与 news[15] 的差别是候选池**含设施**且**不要求已开发**；
`0x40ab4a` mode 0 对设施是「等级 -1，到 0 清 type」，对商業用地是「直接清零」。

### news[22] — 銀行擠兌停止放款 15 天

* **VA**：`0x0044ae89`（`0x44ae89..0x44aedb`，82 字节）
* **台词**：`#0171銀行擠兌停止放款１５天`（`@source VA 0x004656ef`）
* **有效 pass**：**pass 0**（`@source 0x0044ae90`: `jne 0x44ac97` —— 跳到 news[20] 的 `ret`）
* **范围**：全体对局中玩家

```asm
0044aeb6  mov  bh, 0xf
0044aebe  cmp  edx, [0x499114]
0044aec9  cmp  byte ptr [eax + 0x496b7d], 0     ; who_plays == 0 → 跳过
0044aed2  mov  byte ptr [eax + 0x496ba4], bh    ; ★ bank_freeze_days = 15
```

* 字段 `0x3c`（`0x496ba4`）：既有审计称为 `bank_freeze_days`（银行暂停放款），
  银行界面按 `(v & 0x7f) + 1` 显示天数 —— 与「15 天」文案一致（15 = 0xf ⇒ 显示 16？见 §5 未决）。
* **pass 0 生效**是本事件的特殊点。

### news[23] — 銀行加發 10% 儲金紅利

* **VA**：`0x0044aedb`（`0x44aedb..0x44b00a`，303 字节）
* **台词**：`#0172銀行加發１０％儲金紅利`（`@source VA 0x0046570b`）
* **有效 pass**：**pass 0**（`@source 0x0044aef3`: `jne 0x44972a` —— 跳到 news[11] 的 `ret`）
* **范围**：全体**无贷款**的对局中玩家

```asm
0044af29  cmp  byte ptr [ebx + 0x496b7d], 0   ; 非对局 → 跳过
0044af36  mov  ebp, dword ptr [ebx + 0x496b8c]    ; ★ player.loan
0044af3c  test ebp, ebp / jne 0x44b004            ; ★ 有贷款 → 跳过
0044af44  fild dword ptr [ebx + 0x496b88]         ; ★ money_in_bank
0044af4a  fmul qword ptr [0x465734]               ; ★ 常量 0.1
0044af50  call 0x457dbc                           ; 取整
0044af55  fistp dword ptr [esp + 0x94]
0044af5d  push ebp (0) / push bonus / push esi / call 0x41d3f4   ; add_money(player, bonus, 0) → 进银行
0044afac  push 0x465727                           ; "%s得到%d元"
```

* 常量 `@source VA 0x00465734` = `0.1`。
* 红利 `= round(money_in_bank * 0.1)`，`flags=0` ⇒ 回到 `money_in_bank`。
* 顺序：先算 `loan` 判定，再算红利率 —— 判定用的是**旧**贷款额（本事件不改贷款）。

**边界**：`loan != 0` 一律不发（哪怕存款很多）。存款为 0 时 `bonus = 0`，仍会画一行「得到 0 元」。

### news[24] — 股市低迷不振重挫崩盤

* **VA**：`0x0044b00a`（`0x44b00a..0x44b055`，75 字节）
* **台词**：`#0173股市低迷不振重挫崩盤`（`@source VA 0x0046573c`）
* **有效 pass**：**pass 0**（`@source 0x0044b011`: `jne 0x44b053`）
* **范围**：全局（12 只股票）

```asm
0044b033  mov  bl, 1
0044b035  mov  eax, edx / shl eax,3 / add eax,edx     ; edx*9
0044b03c  mov  byte ptr [eax*4 + 0x496987], bl       ; ★ stock[i].+7 = 1
0044b044  cmp  edx, 0xc / jl  0x44b035                ; i = 0..11
0044b04b  call 0x429040                               ; 参数 0
```

* 股票结构基址 `0x496980`，步长 **0x24**；`+7` 字节是「本回合涨跌档位」。
* 写 1 = 崩盘档；随后 `0x429040(0)` 重算股价。
* **注意**：`0x496987` 正是 `check_news` case 28 判「停牌」用的同一个字节 —— 但停牌时写的是 `0xF`（news[27]），
  所以「1/0x10/3/4/0x30」是涨跌档，`0xF` 才是停牌。

### news[25] — 股市氣勢如虹全面上漲

* **VA**：`0x0044b055`（`0x44b055..0x44b0a0`，75 字节）
* **台词**：`#0174股市氣勢如虹全面上漲`（`@source VA 0x00465756`）
* **有效 pass**：**pass 0**
* 与 news[24] 唯一差别：`mov bl, 0x10`（`@source 0x0044b07e`），即 12 只股票 `+7` 字节写 `0x10`，再 `0x429040(0)`。

### news[26] — 股市暫停交易 10 天

* **VA**：`0x0044b0a0`（`0x44b0a0..0x44b0d1`，49 字节）
* **台词**：`#0175股市暫停交易１０天`（`@source VA 0x00465770`）
* **有效 pass**：**pass 0**（`@source 0x0044b0a6`: `jne 0x44b0d0`）
* **范围**：全局

```asm
0044b0c6  mov  dword ptr [0x4990dc], 0xa     ; ★ stock_rest_days = 10
```

* 唯一副作用是 `0x4990dc = 10`（`global_vars.txt` 记作「number of days the stock market rests」）。

### news[27] — %s 股票暫停交易 10 天

* **VA**：`0x0044b0d1`（`0x44b0d1..0x44b1a3`，210 字节）
* **台词**：`#0176%s股票暫停交易１０天`（`@source VA 0x00465788`）
* **有效 pass**：**pass 0**（`@source 0x0044b0e1`: `jne 0x44b19a`）
* **范围**：随机 1 只股票

```asm
0044b0e7  call 0x456f2d / mov ebx,0xc / idiv ebx     ; rand() % 12
0044b0f8  mov esi, edx                                ; i
0044b104  mov ecx, dword ptr [ebx + 0x496980]         ; ★ 股票名指针
0044b113  call 0x452946                               ; 取名字
0044b154  mov byte ptr [ebx + 0x496986], 0xf          ; ★ stock[i].+6 = 0xF（停牌）
0044b15b  mov edx, dword ptr [0x499100] / dec edx
0044b164  jge 0x44b16b / mov edx, 0x8f                ; 若 -1 → 0x8f
0044b174  mov ecx, dword ptr [eax*4 + 0x496990]
0044b17b  mov dword ptr [eax*4 + 0x496994], ecx       ; 股价 := 昨收（+0x14 → +0x10）
0044b182  fld  dword ptr [eax*4 + 0x496994]
0044b18e  shl  ebx, 6                                  ; stock*0x240
0044b193  fstp dword ptr [ebx + eax*4 + 0x497328]      ; ★ 写价格历史
```

**精确规则**

1. `i = rand() % 12`；取 `stock[i]` 名（`+0x00`）。
2. `stock[i].+6 = 0xF`（停牌标记；`check_news` case 28 即查此字节）。
3. `day = dword[0x499100] - 1`；若 `< 0` 则 `day = 0x8f`（143）。
4. `stock[i].price_at(+0x14) = stock[i].price(+0x10)`（把当前价复制到「昨收」），
   再把该价格写入历史 `0x497328 + i*0x240 + day*4`。

**边界 / 未决**

* `0x497328` 每只股票占 `0x240` 字节 = 144 个 float；`day` 用 `0x8f(143)` 兜底正好落在最后一格，
  说明该表设计为 **144 天**。**`0x499100` = 股价历史表的环形写指针（0..0x8f）** ——
  ★ 早期在这里写「语义未决（日期计数？）」，是**错的**，且与 `stocks.md` 的独立结论冲突。
  实证（本轮由 `save-scalars.md` 定名，已回汇编复核）：
  ```asm
  @source 0x004294a3
  004294a3  mov  dword ptr [0x499100], ecx   ; 写入
  004294a9  cmp  ecx, 0x90                   ; ★ 0..0x8f = 144 槽
  004294b3  mov  dword ptr [0x499100], esi   ; 回绕到 0（esi 已 xor）
  ```
  「日期」是**另一个**全局 `0x4990e4`（`0x41cfab add`，每日 +1）。两者不要混。
* `news[10]` 与 `fortune` 里对 `0x497324`/`0x497325` 的 `inc byte` 表明这几个地址是一个状态块，语义**未决**。

### news[28] — %s 股票恢復上市交易

* **VA**：`0x0044b1a3`（`0x44b1a3..0x44b25b`，184 字节）
* **台词**：`#0177%s股票恢復上市交易`（`@source VA 0x004657a2`）
* **有效 pass**：**pass 0**（`@source 0x0044b1b3`: `jne 0x44b253`）
* **范围**：随机 1 只**已停牌**股票

```asm
0044b1c3  mov eax, edx / shl eax,3 / add eax,edx
0044b1ca  cmp byte ptr [eax*4 + 0x496986], 0    ; ★ 只收 +6 != 0 的股票
0044b1d4  mov dword ptr [esp + ebx*4 + 0x80], edx   ; 收集候选
0044b1de  call 0x456f2d / idiv ebx                  ; rand() % 候选数
0044b24b  xor ch, ch
0044b24d  mov byte ptr [ebx + 0x496986], ch         ; ★ 清停牌标记
```

**边界**：候选为空时 `idiv 0` —— 但 `check_news` case 28 已保证至少一只停牌，故不可达。

### news[29] — %s 違法超貸，經營者 %s 坐牢 5 天

* **VA**：`0x0044b25b`（`0x44b25b..0x44b374`，281 字节）
* **台词**：`#0178%s違法超貸\n經營者%s坐牢５天`（`@source VA 0x004657ba`）
  第一个 `%s` = 公司名，第二个 `%s` = 业主玩家名
* **有效 pass**：**pass 1**
  （`@source 0x0044b26c`: `jne 0x44b323`；`0x44b323` 是**生效分支**，`0x44b316..0x44b321` 是 pass 0
   的收尾——它只把业主下标存进 `0x48c59c` 后 `jmp 0x44b36a` 返回）
* **范围**：随机 1 家**有主**的商业实体 → 其业主坐牢 5 天

```asm
0044b289  cmp  byte ptr [ecx + edx + 0x18], 0   ; ★ 只收 on_map_commercial[+0x18] != 0
0044b29e  call 0x456f2d / idiv ebx                ; rand() % 候选数
0044b2bb  mov  al, byte ptr [ebx + 0x18] / dec eax
0044b2bf  imul eax, eax, 0x68
0044b2c2  mov  ebp, dword ptr [eax + 0x496b68]    ; ★ 业主玩家名（+0x18 = owner+1）
0044b31c  mov  dword ptr [0x48c59c], eax          ; owner index
0044b352  call 0x441210                           ; 返回可坐牢的槽位，-1 = 不可用
0044b35d  je   end
0044b361  push 5 / push eax / call 0x43d593        ; ★ add_player_days_in_prison(x, 5)
```

* `on_map_commercial`（`0x498e7c`，步长 `0x34`）：`+0x18` = **业主玩家下标 + 1**，`+0x19` = 公司/股票下标，`+4` = 名称。
* `0x43d593(player, days)` 写 `player.days_in_prison (0x496b9c)` 并置 `0x496b30`（已用另一路径验证）。

**边界**

* 候选为空则 `idiv 0`；`check_news` case 29 保证非空（且业主是可行动的玩家）。
* `0x441210(owner)` 返回 -1 时**不坐牢**（无任何提示）。

### news[30] — %s 工廠排放污水，罰款 10000 元

* **VA**：`0x0044b374`（`0x44b374..0x44b419`，165 字节）
* **台词**：`#0179%s工廠排放污水\n罰款10000元`（`@source VA 0x004657db`）
* **有效 pass**：**pass 0**
* **范围**：随机 1 家商业实体

```asm
0044b389  call 0x456f2d / idiv [0x498e90] / inc edx   ; rand() % num_on_map_commercials + 1
0044b39d  mov eax, [0x498e7c] / add ebx, eax
0044b3d9  sub  dword ptr [ebx + 0x28], 0x2710         ; ★ -10000
0044b3e0  sub  dword ptr [ebx + 0x2c], 0x2710         ; ★ -10000
0044b3e7  mov  ah, byte ptr [ebx + 0x19]              ; ★ 公司/股票下标
0044b3ea  cmp  ah, 0xc / jae 0x44b411                 ; >= 12 → 跳过股市联动
0044b3fa  mov  byte ptr [eax*4 + 0x496987], 3         ; ★ stock[+7] = 3
0044b402  mov  al, byte [ebx + 0x19] / inc eax / push eax
0044b409  call 0x429040                               ; 0x429040(index+1)
```

* `+0x28` 与 `+0x2c` 两个字段同时 -10000（两字段疑似「资金/净值」双写，语义未决）。
* `stock[+7] = 3` 是「下跌档」，随后 `0x429040(index+1)` 重算。

**边界**：`num_on_map_commercials == 0` 时 `idiv 0`。`check_news` case 30 走默认（恒可行），
所以理论上存在除零路径（原版未防护）——**这是一个真实的健壮性缺口，标为未决（是否可达取决于地图数据）**。

### news[31] — %s 海外投資，獲利 20000 元

* **VA**：`0x0044b419`（`0x44b419..0x44b4a8`，143 字节）
* **台词**：`#0180%s海外投資\n獲利20000元`（`@source VA 0x004657fb`）
* **有效 pass**：**pass 0**
* **范围**：随机 1 家商业实体
* 与 news[30] 对称：`add dword [ebx+0x28], 0x4e20` / `add dword [ebx+0x2c], 0x4e20`（+20000），
  `stock[+7] = 0x30`（上涨档），再 `0x429040(index+1)`。
* `0x4e20 = 20000`，`0x2710 = 10000`。

### news[32] — %s 海外投資，虧損 20000 元

* **VA**：`0x0044b4a8`（`0x44b4a8..0x44b53f`，151 字节）
* **台词**：`#0181%s海外投資\n虧損20000元`（`@source VA 0x00465817`）
* **有效 pass**：**pass 0**
* 与 news[31] 对称，符号取反：`sub ... 0x4e20` ×2，`stock[+7] = 4`，`0x429040(index+1)`。

### news[33] — %s 違規開發山坡地，罰款 10000 元

* **VA**：`0x0044b53f`（`0x44b53f..0x44b57d`，62 字节）
* **台词**：`#0182%s違規開發山坡地\n罰款10000元`（`@source VA 0x00465833`）
* **有效 pass**：**pass 0**
* **范围**：随机 1 家商业实体
* 与 news[30] **完全相同**：`jmp 0x44b3ad` 复用 news[30] 的函数体（`-0x2710` ×2 + `stock[+7]=3` + `0x429040`）。

### news[34] — %s 製造噪音公害，罰款 5000 元

* **VA**：`0x0044b57d`（`0x44b57d..0x44b5f5`，120 字节）
* **台词**：`#0183%s製造噪音公害\n罰款5000元`（`@source VA 0x00465855`）
* **有效 pass**：**pass 0**
* **范围**：随机 1 家商业实体

```asm
0044b5e2  sub  dword ptr [ebx + 0x28], 0x1388     ; -5000
0044b5e9  sub  dword ptr [ebx + 0x2c], 0x1388
0044b5f0  jmp  0x44b3e7                           ; 复用 news[30] 的股市联动
```

* `0x1388 = 5000`。股市联动与 news[30] 相同（`stock[+7]=3`）。

### news[35] — %s 獲利調高一倍

* **VA**：`0x0044b5f5`（`0x44b5f5..0x44b6df`，234 字节）
* **台词**：`#0184%s獲利調高一倍`（`@source VA 0x00465874`）
* **有效 pass**：**pass 0**（`@source 0x0044b605`: `jne 0x44b6d6`）
* **范围**：随机 1 家**获利 > 10000** 的商业实体

```asm
0044b623  cmp  dword ptr [ecx + edx + 0x28], 0x2710
0044b62b  jle  0x44b636                       ; ★ 只收 +0x28 > 10000
0044b62d  mov  word ptr [esp + ebx*2 + 0x80], ax   ; 收集候选
0044b639  call 0x456f2d / idiv ebx                 ; rand() % 候选数
0044b68f  mov  ebx, dword ptr [esi + 0x28]
0044b692  lea  eax, [ebx + ebx]                    ; ★ 2 × 旧值
0044b695  mov  dword ptr [esi + 0x28], eax
0044b698  add  dword ptr [esi + 0x2c], eax         ; ★ +0x2c += 新的 +0x28
0044b69b  cmp  byte ptr [esi + 0x19], 0xc / jae end
0044b6ad  idiv ecx (0x2710)                        ; 新值 / 10000
0044b6af  shl  eax, 4                              ; ×16
0044b6c0  mov  byte ptr [eax*4 + 0x496987], bl     ; ★ stock[+7] = (新值/10000)*16 的低字节
0044b6cd  call 0x429040(index+1)
```

**精确规则**

```
v = com[+0x28]
com[+0x28] = 2*v
com[+0x2c] += 2*v                // 注意：加的是「新值」，不是增量
if (com[+0x19] < 12) stock[com[+0x19]].+7 = ((2*v) / 10000 * 16) & 0xff   // 32 位有符号 idiv
```

**边界**

* `+0x28` 与 `+0x2c` 的语义不同（前者被倍化，后者被累加），复刻时不要一起乘 2。
* `idiv` 是**有符号**除法；`+0x28` 若为负（可能被 news[30]/[32]/[34] 扣成负）→ 候选已被 `> 10000` 过滤掉。
* 档位字节是 `(新值/10000)*16`，新值上不封顶，超过 0xFF 会截断到低 8 位（原版不检查）。

---

## 四、汇总表

| # | VA | 一句话效果 | 范围 | 有效 pass |
|---|---|---|---|---|
| 0 | `0x448eca` | 在狱者全部释放（`days_in_prison=0x80`，清 `0x496b30`） | 全体在狱 | 0 |
| 1 | `0x448f45` | 在狱者刑期 +3 天，`&0x7f` | 全体在狱 | 0 |
| 2 | `0x449006` | 住院者全部提前出院（`days_in_hospital=0x80`，清 `0x496b60`） | 全体住院 | 0 |
| 3 | `0x449081` | 住院者住院 +3 天，`&0x7f` | 全体住院 | 0 |
| 4 | `0x44913d` | 随机 1 块地产演出；`who_plays&0x40` 的玩家住院 3 天 | 全体（掩码） | 1 |
| 5 | `0x4492a0` | 随机 1 块已开发地产**完全清除**（owner/level/type=0） | 随机 1 块 | 1 |
| 6 | `0x4494e0` | **所有同名地产**地价 ×1.3 | 同名全体 | 1 |
| 7 | `0x449735` | 随机 1 块无主地进入拍卖（`0x43bde5`） | 随机 1 块 | 1 |
| 8 | `0x4498b3` | 地产最多的玩家得 `10000*p`（进现金） | 单个（最大） | 1 |
| 9 | `0x449a8a` | 地产最少的玩家得 `5000*p`（进现金） | 单个（最小） | 1 |
| 10 | `0x449b9c` | 持股最多的玩家得 `10000*p` | 单个（最大） | 1 |
| 11 | `0x449c7c` | 全体缴所得税 `round(cash*0.05)` | 全体 | 1 |
| 12 | `0x449de6` | 全体缴地价税 `round(Σ(level*house+price)*0.05)*p` | 全体 | 1 |
| 13 | `0x44a029` | 全体缴证交税 `round(Σ(股数*股价)*0.05)*p` | 全体 | 1 |
| 14 | `0x44a220` | **同名地产**地价 ×0.7 | 同名全体 | 1 |
| 15 | `0x44a453` | 随机 1 块已开发**住宅**等级 -1 | 随机 1 块 | 1 |
| 16 | `0x44a5d6` | 步行者 `days_stopping = 1` | 全体步行 | 0 |
| 17 | `0x44a657` | 乘车者 `days_stopping = 1` | 全体乘车 | 0 |
| 18 | `0x44a6e0` | **同名地产**等级 -1（商業用地清零） | 同名全体 | 1 |
| 19 | `0x44a91e` | 随机 1 块地/设施**完全清除** | 随机 1 块 | 1 |
| 20 | `0x44ab2c` | **仅动画，无状态改动** | — | 1 |
| 21 | `0x44ac99` | 随机 1 块地/设施等级 -1 | 随机 1 块 | 1 |
| 22 | `0x44ae89` | 全体 `bank_freeze_days = 15` | 全体 | 0 |
| 23 | `0x44aedb` | 无贷款者 `money_in_bank` 红利 10% | 全体无贷款 | 0 |
| 24 | `0x44b00a` | 12 只股票涨跌档 = 1，重算 | 全局 | 0 |
| 25 | `0x44b055` | 12 只股票涨跌档 = 0x10，重算 | 全局 | 0 |
| 26 | `0x44b0a0` | `stock_rest_days = 10` | 全局 | 0 |
| 27 | `0x44b0d1` | 随机 1 只股票停牌（`+6=0xF`）并存价格历史 | 随机 1 只 | 0 |
| 28 | `0x44b1a3` | 随机 1 只停牌股票复牌（`+6=0`） | 随机 1 只 | 0 |
| 29 | `0x44b25b` | 随机 1 家有主公司，业主坐牢 5 天 | 单个（业主） | 1 |
| 30 | `0x44b374` | 随机 1 家公司 -10000/-10000，联动股价档 3 | 随机 1 家 | 0 |
| 31 | `0x44b419` | 随机 1 家公司 +20000/+20000，联动股价档 0x30 | 随机 1 家 | 0 |
| 32 | `0x44b4a8` | 随机 1 家公司 -20000/-20000，联动股价档 4 | 随机 1 家 | 0 |
| 33 | `0x44b53f` | 同 news[30]（-10000/档 3） | 随机 1 家 | 0 |
| 34 | `0x44b57d` | 随机 1 家公司 -5000/-5000，联动股价档 3 | 随机 1 家 | 0 |
| 35 | `0x44b5f5` | 随机 1 家获利>10000 的公司 `+0x28` 翻倍 | 随机 1 家 | 0 |

---

## 五、未决清单（明确写「未决」，不用推测填充）

1. **`0x499090`（`news_order[36]`）的实际取值在静态文件里不可读** —— 它位于 `.bss`（`0x48a000` 起，文件中无字节），
   由 `0x448b81` 在运行时用 `rand()` 生成排列。生成算法已完全解出（Fisher–Yates 型「挑第 k 个空位」），
   但**具体排列取决于 PRNG 种子与调用时机**，本文件不给出具体排列。
2. **`who_plays`（`+0x15`）的位域含义未决**。news[4] 用 `& 0x40` 过滤，其余事件用 `!= 0`。
   `0x40` 位的确切语义（「本回合可行动」？「在场上」？）未确认。
3. **`byte[0x46caf8]` 未决**：news[11]/[12]/[13] 的 pass 1 在它非 0 时整段跳过扣款。写入者与语义未追。
4. **`0x441210(player)` 未决**：返回 -1 的条件未完全解出（已看到内部调用 `0x4413ad(player,0x15)` 与 `0x444bb2`）。
5. **`0x43bde5`（拍卖）内部未展开**：news[7] 的所有权变更在该函数内，本文件只记录「以 `(id,-1,1)` 调用」。
6. **`0x456c0a` 未决**：news[6]/[14]/[18] 命中每一块同名地产时都会调用
   `0x456c0a(dword[0x474938], 0x2f440, id, -1)`。从参数形状看像「地图/所有权记录刷新」，但未解引用验证。
7. ~~**`0x497324` / `0x497325` / `0x499100` / `0x497328` 价格历史表的语义未决**~~
   ✅ 已解：`0x499100` = **环形写指针（0..0x8f）**、`0x497328` = **12 股 × 144 槽的历史价表**
   （见 `save-scalars.md` 与 `stocks.md`）；`0x497324`/`0x497325` 见 `stocks.md`。
   （news[27] 写 144 格 float；fortune[10]/[11] 对前两个字节 `inc`）。
8. **`0x48c59c`、`0x48c5a0`、`0x48c5b0`、`0x48c5b4` 是「跨事件复用的全局暂存」**：
   news[11]/[12]/[13] 把 `0x48c59c` 当 **4 项 dword 数组**用，而 news[4]/[5]/[6] 等把它当**单值**用。
   这是原版行为；复刻时若把这些全局拆成各自独立的局部变量，语义等价（因为 pass 0 / pass 1 之间不重叠），
   但**若要逐位对齐内存足迹则必须保留复用**。
9. **news[30]/[31]/[32]/[33]/[34] 在选择公司时没有「候选数为 0」的防护**（`idiv` 除数来自
   `num_on_map_commercials`）。`check_news` 对这些编号返回恒可行，因此**是否存在可达的除零路径取决于地图数据**，
   未实机确认。
10. **公司结构 `on_map_commercial`（`0x498e7c`）的 `+0x28` 与 `+0x2c` 双字段语义未决**：
    新闻里几乎总是成对同增减，只有 news[35] 区别对待（`+0x28` 翻倍、`+0x2c` 累加新值）。

---

## 六、与既有结论的对照（复核记录）

| 既有结论 | 复核结果 | 证据 |
|---|---|---|
| 新闻 8/9 是「地产统计」 | ✅ **确认** | news[8] `0x4498f5`/`0x44992c` 按 `land.owner(+0x19)`、`facility.owner(+0x19)` 累加计数后取最大；news[9] 同一套计数取最小（`best` 初值 `0x2710`）。**补充**：news[10] 也是统计，但统计对象是股票持股数 |
| `check_news` 的 case 分组与汇编「无误」 | ✅ **确认（本轮独立复算）** | §2.1 表；逐分支地址与 `csrc/news.c` 的 case 分组一一对应，未发现差异 |
| 新闻 8/9 号函数 = `0x4498b3` / `0x449a8a` | ✅ 确认（与 `events_calls_table[8]/[9]` 一致） | `@source VA 0x00475e24` + 表项偏移 |
| `csrc/news.c` 的 `news_events` 里 `event_calls_table[ebx](0)` / `(1)` 两次调用 | ✅ 确认 | `0x44b7bd`（pass 0）与 `0x44b875`（pass 1） |
| 「新闻事件由格子类型触发」 | ✅ 确认并**具体化** | node `+0x24 == 2`，跳表 `0x4197e9[2] = 0x41b11e` |

**本轮新发现（既有文档未提及）**

1. **事件顺序是随机排列表**（`0x499090`，由 `0x448b81` 洗牌），游标 `0x4990e0` 前进直到遇到可行事件；
   游标**对不可行事件也会前进**。
2. **处理函数被调用两次**（pass 0 / pass 1），**19 项在 pass 0 生效、17 项在 pass 1 生效**
   （全表见 §1.3 第 3 点）。这直接决定了「画面显示的是改前还是改后状态」。
   与直觉不同：16/17（暂停一回合）与 22..28、30..35 都是**在 sleep 之前**就改状态。
3. **news[20] 无状态改动**（与文案不符），见 §3。
4. `0x40ab4a(id, mode)` 的三档语义：mode 0 对**商業用地**是「一次归零」而非「-1」。
5. `0x44ba63(player, amount, 第3参数)` 的**第 3 个参数在原函数内未被使用**（`0x44bacc` 读的是
   压栈前的 `[esp+0x98]`，即 arg0）—— `csrc` 未记录此细节。
