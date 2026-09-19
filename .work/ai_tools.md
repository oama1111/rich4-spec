# AI 用道具决策

真值：`Rich4/rich4.exe`（PE32，ImageBase 0x400000，v3.11）。
本文所有地址均为 VA；所有汇编均为本人用 capstone 从 exe 线性反汇编得到的**原文**，不是转述。

> **三处对常见"锚点"的更正（均在本文内给出证据）**
> 1. **道具跳表不在 0x475324**。`0x475324` 是**卡片门**的"基址-1"常数；卡片决策表条目在 `0x475328 + 4*(card-1)`（card 1 → `0x41e6fe`）。**道具**决策表条目在 `0x4753a0 + 4*(ord-1)`，代码里的引用常数是 `0x47539c`（基址-1）。两个表都是 1 基索引。
> 2. **`_rich4_get_ai_tool_param_value` 的 VA 是 `0x420eee`，不是 `0x420e9a`**。`0x420e9a` 是道具"门+派发"函数（与卡片门 `0x41e69e` 同构）。
> 3. **`0x441baa` 只处理卡片**（非"卡+道具"）。道具驱动是 `0x447d97`。两者由 `0x418e18` 的一次 `rand()&1` 二选一。

---

## AI 用道具决策

### 1. 入口与派发

**回合阶段开关**（`0x418d6e`）`push 0; call 0x40c912; cmp eax,5; ja ...; jmp dword [eax*4 + 0x418c3d]`；
表 `0x418c3d` = `0x418d88, 0x418d99, 0x418dc6, 0x418e7a, 0x418e7a, 0x418dc6`（case 2/5 = 用道具阶段）。

**用道具阶段（0x418dc6 起）**：先要求 `current_player < 4` 且 `byte[player*0x68+0x496b7d] & 0x30 == 0`，再依次 `0x42bf03`、`0x42c79f`、`0x436b0a`，然后：

```asm
00418e13  call       0x4284be
00418e18  call       0x456f2d            ; libc_rand
00418e1d  test       al, 1
00418e1f  je         0x418e28
00418e21  call       0x441baa            ; 卡片驱动
00418e26  jmp        0x418e2d
00418e28  call       0x447d97            ; 道具驱动
00418e2d  mov        edx, dword ptr [0x49910c]
```

**结论：不是"优先卡、再退道具"，而是一枚 50/50 硬币**——`rand() & 1` 非零走卡片驱动，为零走道具驱动；每回合**只执行其中一个**。
（另有两条独立分支 `0x417de0 call 0x447d97` 与 `0x417de7 call 0x441baa`，位于另一张开关表里，两者是**并列的 case**，不是先后关系：`0x417de5 jmp 0x417dff`、`0x417dec jmp 0x417dff`。）

**两个驱动共有的"人/机"分岔**（同一形态）：

```asm
00447d9e  imul       eax, dword ptr [0x49910c], 0x68
00447da5  mov        dl, byte ptr [eax + 0x496b7d]   ; player+0x15 电脑标志
00447dab  cmp        dl, 1
00447dae  jne        0x447f82                          ; ≠1 → 走 AI 分支
```
`+0x15 == 1` → 走 UI 选择对话框（`0x447db4` 起，人类用道具；`0x441bca` 起为卡片版）；否则要求 `dl & 6 != 0` 才进入 AI 分支。卡片驱动同构：`0x441bc1 cmp dl,1 / 0x441bc4 jne 0x441d00`。

**卡片 AI 分支 `0x441d16`（对照用）**：`0x441262(current_player)` 取卡片张数 → 把最多 8 个非空槽从 `0x499120 + 15*player + i` 抄进局部数组（起点 = `rand()%count`，仅当 count>8），逐槽调用**卡片门** `0x41e69e`，返回 1 则 `call dword ptr [eax*4 + 0x475d5c]` 执行效果（卡片效果表自 `0x475d60` 起，card 1 → `0x4420d8`）。

**道具 AI 分支 `0x447f82`（本文主角）**：
```asm
00447f82  test       dl, 6
00447f85  je         0x447f7a
00447f87  test       byte ptr [eax + 0x496b7e], 2   ; player+0x16 bit1
00447f8e  je         0x447f7a
00447f90  push       0xd
00447f92  push       0
00447f94  lea        eax, [esp + 0x40]
00447f98  push       eax
00447f99  call       0x456f60                        ; memset(候选表,0,13)
...
00447fb9  mov        eax, dword ptr [0x49910c]       ; 当前玩家
00447fc0  shl        ebx, 2
00447fc3  add        ebx, eax                        ; 5p
00447fc7  shl        ebx, 2                          ; 20p
00447fca  sub        ebx, eax                        ; 15p
00447fd0  cmp        byte ptr [ebx + eax + 0x49915c], 0   ; 道具槽数组
00447fd8  je         0x447fab
00447fda  cmp        eax, 9
00447fdd  je         0x447fab                        ; 跳过槽 i==9
00447fdf  mov        al, byte ptr [esp + 0x48]
00447fe3  inc        al
00447fe5  mov        byte ptr [esp + esi + 0x38], al  ; 候选值 = i+1
00447fe9  inc        esi
```
- 道具槽数组 = `0x49915c + 15*player + i`，`i = 0..12`（13 个道具），**槽值 = 0 表示没有**，候选值 = `i+1`（即"道具序号 ord"，1..13）。
- **槽 `i == 9` 被无条件跳过**（对应 ord 10 = 時光機，且其 handler 本身就是 `ret 0`）。所以 AI 实际只考虑 12 种道具。
- 卡片槽在 `0x499120 + 15*player + i`，道具槽在 `0x49915c + 15*player + i`（两个各 60 字节的数组，见 `0x407186/0x407196` 的 `memset`，以及存档函数 `0x402be0/0x402bf2`）。**注意：共享简报里"hand[]=0x499120 (player*15+slot)"只说对了卡片那一半。**

```asm
00447fec  test       esi, esi
00447fee  je         0x447f7a            ; 一件道具都没有 → 结束
00447ff0  cmp        esi, 4
00447ff3  jle        0x448005
00447ff5  call       0x456f2d            ; rand()
00447fff  idiv       esi
00448001  mov        ebx, edx            ; 起点 = rand()%候选数（仅当候选数>4）
00448005  xor        ebx, ebx            ; 否则起点 0
...
0044800d  jmp        0x448028
0044800f  inc        ebx                 ; 下一个候选（环形）
00448010  cmp        ebx, esi
00448012  jne        0x448016
00448014  xor        ebx, esi            ; 回绕
00448016  mov        ebp, dword ptr [esp + 0x48]
0044801a  inc        ebp
0044801f  cmp        ebp, 4
00448022  jge        0x447f7a            ; 最多试 4 件
00448028  mov        dh, byte ptr [esp + ebx + 0x38]
00448034  xor        eax, eax
00448036  mov        al, dh
00448038  push       eax
00448039  call       0x420e9a            ; 道具门+派发
0044803e  add        esp, 4
00448041  cmp        eax, 1
00448044  jne        0x44800f            ; 否决 → 下一件
```
- **顺序**：候选按槽序号 0..12 收集，起点随机（候选数>4 时），然后**最多尝试 4 件**（环形推进）。即"随机起点 + 最多 4 次试错"。
- 命中后（`0x448046`）用格式串 `0x4653e5`（`"使用%s"`，cp950 解码）拼名字，`call 0x440cac` 显示，再 `call dword ptr [eax*4 + 0x475dd5]` 执行**效果函数**。

**门 + 派发 `0x420e9a`（原文，整段）**：
```asm
00420e9a  mov        eax, dword ptr [esp + 4]     ; 参数 = 道具序号 ord (1..13)
00420e9e  xor        edx, edx
00420ea0  mov        dl, byte ptr [eax*8 + 0x47fee1]   ; f7 = 0x47fee2(=道具1条目)+7
00420ea7  imul       eax, dword ptr [0x49910c], 0x68
00420eae  mov        al, byte ptr [eax + 0x496b7f]     ; player+0x17 個性
00420eb4  and        eax, 0xff
00420eb9  sub        edx, eax                          ; edx = f7 - 個性
00420ebb  mov        eax, edx
00420ebd  cmp        edx, 2
00420ec0  jl         0x420ec5
00420ec2  xor        eax, edx                          ; f7-個性 >= 2 → eax=0
00420ec4  ret
00420ec5  cmp        edx, 1
00420ec8  jne        0x420ee2                          ; f7-個性 <= 0 → 直接派发
00420eca  call       0x456f2d                          ; rand()
00420ecf  mov        edx, eax
00420ed1  mov        ecx, 3
00420ed6  sar        edx, 0x1f
00420ed9  idiv       ecx                               ; edx = rand() % 3
00420edb  test       edx, edx
00420edd  je         0x420ee2                          ; %3==0 → 派发（1/3）
00420edf  xor        eax, eax                          ; 否则否决
00420ee1  ret
00420ee2  mov        eax, dword ptr [esp + 4]
00420ee6  call       dword ptr [eax*4 + 0x47539c]      ; 跳表：0x4753a0+4*(ord-1)
00420eed  ret
```
**个性门槛（原版语义，非 remake 的确定性替代）**：`d = f7 - player[+0x17]`
- `d >= 2` → **永不使用**（返回 0）
- `d == 1` → **`rand()%3 == 0` 才使用**（1/3 概率）
- `d <= 0` → **总是使用**

即 `f7` 是"个性下限要求"：`個性 >= f7` 必用；`個性 == f7-1` 三分之一样；`個性 <= f7-2` 永不用。
卡片门 `0x41e69e` 是同一段代码的卡片版（f7 基址 `0x47fdf1`，跳表 `0x475324`，card 1 → `0x41e6fe`）。

**派发结果写在哪**：各 handler 只做决策，把"目标参数"写进静态池 `0x48be64`（道具）/ `0x48be58`（卡片），返回 1/0；**效果由 `[ord*4+0x475dd5]` 表（首条目 `0x475dd9`，注意该表字节未按 4 对齐）里的函数执行**，效果函数再用 `0x420eee` / `0x41e6f2` 读回该参数。

道具**效果函数**表（ord 1..13，`0x475dd9` 起，逐 dword 读出）：
`0x446afb`(機器娃娃) `0x446baa`(路障) `0x446c88`(地雷) `0x446d69`(定時炸彈) `0x446e4a`(機車) `0x446f05`(汽車) `0x446fbc`(飛彈) `0x4470f8`(遙控骰子) `0x447295`(機器工人) `0x447387`(時光機) `0x447428`(傳送機) `0x4479d2`(工程車) `0x447ace`(核子飛彈)。13 个目标地址均落在函数序言上。

### 2. 道具表 0x47fdea（action 31..43）逐项表格

条目地址 = `0x47fdea + action*8`（action 1..30 = 卡，31..43 = 道具，条目 0 为空哨兵）。
`nameVA = [条目+0]`（cp950 解码自 exe），`b4..b7 = byte[条目+4..+7]`。

| action | 处理函数 VA | 中文名 | f7 | 价格 | 判据摘要 |
|---|---|---|---|---|---|
| 31 | 0x420efa | 機器娃娃 | 0x00 | b4=0x0a b5=0x0f | 路径节点上的当事人类型 ∈{5,6,7,8} 直接用（`0x420f66..0x420f83`）；类型 0xb 也直接用；类型 0x11 需 `owner==current_player+1`（`0x421020`）；类型 0x10 需 owner 为他人且过路费 `> 3000*price_index`（`0x42106b`） |
| 32 | 0x42107f | 路障 | 0x01 | b4=0x0a b5=0x1e | 空节点上放：同地名自有地 >= 2 或该地已有建筑（`0x4210bd`），且 `cash+bank>0x2710`、`p+0x46>=0`、`p+0x39==0`、`word[land+0x1c]*price_index < cash`；退化路：路径上自有地过路费 `> 6000*price_index` 且**取最大** |
| 33 | 0x4213c5 | 地雷 | 0x01 | b4=0x0a b5=0x19 | 在"可达节点表 ∩ 预测路径"里收集**他人**的地/设施 → `rand()%count` 随机选一块；若节点是 `word[0x48bae0]` 且 `[0x496b30]!=0`（或 `word[0x48bae2]` 且 `[0x496b60]!=0`）则立即选它 |
| 34 | 0x421574 | 定時炸彈 | 0x01 | b4=0x0a b5=0x19 | 与地雷同一张表，但**不筛归属**：凡"可达 ∩ 路径"节点都进候选，`rand()%count` 随机选 |
| 35 | 0x421644 | 機車 | 0x00 | b4=0x0a b5=0x50 | `(player+0x11 & 3) == 0`（还没载具）且 `rand()%4 == 0`（25%） |
| 36 | 0x421675 | 汽車 | 0x00 | b4=0x0a b5=0x96 | `(player+0x11 & 3) < 2`（载具等级<2）且 `rand()%4 == 0`（25%） |
| 37 | 0x421717 | 飛彈 | 0x02 | b4=0x0a b5=0x64 | 目标 = `0x40d2d3(self)`（最仇视者），-1 则 `0x40d31c(self)`，仍 -1 → 否；再要求"路径"节点带 0x8000 且低 4 位含该玩家位，且 `0x40a0b1(p+8,p+0xa,0x64)` 的区域里既无 0x8000 节点也**无自有地** |
| 38 | 0x421827 | 遙控骰子 | 0x00 | b4=0x0a b5=0x1e | `p+0x3f ∉ {7,8,0xf}`、`p+0x39==0`、`cash+bank >= 0x2710`、`word[p+0x46]>=0`；在 6 个路径节点上选"可买/可升级"：无主地 `cash > word[land+0x1c]*2.5`；自有地需同地名 >= 2、`land+0x18==0`、等级<5、`cash > word[land+0x1e]*2.5` 且取等级最高 |
| 39 | 0x421ba6 | 機器工人 | 0x01 | b4=0x00 b5=0x1e | 在"可达节点表"里找**自有**地/设施：地需 `land+0x18==0`、等级<5，取 `word[land+等级*2+0x20]` 最大者；设施需 `等级 < byte[类型+0x474940]`，取 `word[fac+等级*2+0x24]` 最大者 |
| 40 | 0x420edf | 時光機 | 0x02 | b4=0x00 b5=0x28 | **`xor eax,eax; ret`——永远否决**；且驱动在 `0x447fda` 无条件跳过槽 i==9 |
| 41 | 0x421cb6 | 傳送機 | 0x01 | b4=0x00 b5=0x5f | 在"可达节点表"里找**无主**且等级 `>= 3` 的地/设施，取等级最高且 `地价*price_index < cash`；最后要求 `cash+bank > 0x2710` 且 `word[p+0x46]>=0` |
| 42 | 0x421e20 | 工程車 | 0x02 | b4=0x00 b5=0x96 | `(player+0x11 & 3) != 3` 且 `rand()%15 <= player[+0x17]（個性）` |
| 43 | 0x421e62 | 核子飛彈 | 0x02 | b4=0x00 b5=0xfa | 候选 = 全部**他人所有且等级 != 0** 的地/设施；最多抽 10 次 `rand()%count`，对爆风区算"我方等级和/他方等级和"，两者都 `< 1/(存活玩家数+2)` 才用 |

**关于"价格"列（重要更正）**：`+4` 处的 dword **不是**一个直接价格（例如 均富卡 = `0x0202c801`，无法当钱用）。逐字节证据表明它被拆成 4 个字段，且代码分别按字节读取：
- `byte+4`：`0x4071a5 mov al, byte ptr [ebx*8 + 0x47fdf6]` → 存入 `0x499198`（卡，30 项）；`0x4071ba mov al, byte ptr [ebx*8 + 0x47fee6]` → 存入 `0x497320`（道具，仅前 8 项）。`0x499198` 在 `0x441e33 mov cl, byte ptr [eax + 0x499198]` 被当作**重复次数/权重**使用 → 推断为"权重/存量"。
- `byte+5`：`0x40ee39 mov al, byte ptr [ebx + 0x47fdef]` 与 `0x40eefd/0x40ef06` 之后 `push eax; push current_player; call 0x44f230`（该函数内以 `0x64`=100、`0x32`=50 分档）→ 推断为**价格档位**（表中"价格"列即此字节）。

### 3. 逐道具判据细节

#### 3.1 機器娃娃 (action 31, ord 1, handler 0x420efa, f7=0x00)
- 前置：`0x40b221(current_player, 4)` 返回 0 才继续（非 0 → 否决，`0x420f11 test eax,eax / 0x420f13 jne 0x421078`）。`0x40b221` 是"从玩家当前格出发的随机游走"：它 memset `0x48b8b4` 16 字节（8 word），逐跳在候选邻格中用 `0x40b2f2 call 0x456f2d; idiv ebx` 随机选一格写入 `0x48b8b4[step]`（`0x40b302 mov word ptr [esi + 0x48b8b4], ax`）。
- 遍历 `edi=0..3` 的 `word[edi*2 + 0x48b8b4]` 节点；取 `[node+0x24] & 0x3f0000 >> 0x10` 为 owner，为 0 跳过。
- `word[node+0x20]`（地产 id）：`0x7d0 < id < 0xfa0` → `0x419744(land+0x19, land+4)` 算过路费；`0xfa0 <= id < 0x1770` → 设施，`edx = 0x989680`（10,000,000）。
- 依 `byte[0x496d08 + 24*(owner-1)]`（当事人类型）判定：`{5,6,7,8}` 直接使用（`0x420f69/0x420f6e/0x420f73/0x420f78 je 0x420f83`）；`0xb` 也直接使用（`0x420f7a cmp eax, 0xb / 0x420f7d jne 0x421010`）；`0x11` 需 `owner == current_player+1`（`0x421014 cmp eax,0x11` + `0x421020 cmp ebx, ebp`）；`0x10` 需 owner 非 0 且非自己、且 `toll > 3000*price_index`（`0x421030 cmp eax,0x10` + `0x421047 cmp ebx, eax` + `0x42106b`）：
```asm
0042104f  mov        ebx, dword ptr [0x4990e8]     ; price_index
0042105a  sub        eax, ebx
0042105c  shl        eax, 3
0042105f  add        eax, ebx                        ; 25*pi
00421061  shl        eax, 3                          ; 200*pi
00421066  shl        eax, 4
00421069  sub        eax, ebx                        ; 3000*pi
0042106b  cmp        edx, eax
0042106d  jle        0x420f88                        ; toll <= 3000*pi → 跳过
```

#### 3.2 路障 (action 32, handler 0x42107f, f7=0x01)
- 前置同 `0x40b221(current,4)`。
- 4 个路径节点，要求节点标志位段为空：`0x421148 test dword ptr [eax + 0x24], 0x3fff00 / 0x42114f jne 0x421118`。
- 无主住宅地：`0x421183 mov edi,1` 起用 `0x458370`(strcmp) 比对 `land+4` 地名，数出**同地名且属自己**的地块数 `ebx`；`0x4210bd cmp ebx,2; jge 0x4210c8` 或 `0x4210c2 cmp byte ptr [eax + 0x1a], 0; je 0x421118`（或该地已有等级）。
- 资金门槛：`0x4210db cmp edx, 0x2710`（cash+bank>10000）、`0x4210e3 cmp word ptr [eax + 0x496bae], 0`（>=0）、`0x4210ed cmp byte ptr [eax + 0x496ba1], 0`（==0）、`0x4210f6 cmp esi, dword ptr [eax + 0x496b84]`（`word[land+0x1c]*price_index < cash`）。
- 商业地分支：`0x421230 mov dx, word ptr [edx + 0x22]` → `0x42123a imul edx, dword ptr [0x4990e8]` → `0x421241 cmp edx, dword ptr [eax + 0x496b84]`。
- 兜底分支（`0x421299`，前面没选到）：`0x40b343(current,6)` + `0x409ef9()` 取长度，取"可达 ∩ 路径"且属自己的住宅，过路费最大者，阈值 `6000*price_index`：`0x42138f cmp ebx, eax`（eax = 6000*pi，由 `0x421379..0x42138d`：`4pi-pi=3pi` → `*8+pi=25pi` → `*16=400pi` → `*16-400pi=6000pi`）。

#### 3.3 地雷 (action 33, handler 0x4213c5, f7=0x01)
- `0x40b343(current_player, 6)`（写 `0x48b8b4`）、`0x409ef9()`（写 `0x48b8c4`，返回可见地块数）→ `0x4213ed mov dword ptr [esp + 0x204], eax`。
- 6 个可达节点里凡**也在**路径表（`0x48b8b4`，4 项）中的：先查两个特殊节点 `0x42144d cmp eax, edx`(=`word[0x48bae0]`) 且 `0x421451 cmp dword ptr [0x496b30], 0`、`0x421470 cmp eax, edx`(=`word[0x48bae2]`) 且 `0x421474 cmp dword ptr [0x496b60], 0` → 命中即直接选该节点。
- 否则只收**他人**地块：`0x4214ce cmp byte ptr [eax + 0x19], 0 / je skip` 且 `0x4214df cmp ecx, eax`（owner == current+1 → skip）；设施同理（`0x421512`、`0x421523`）。
- 随机选一：`0x42153e call 0x456f2d; idiv esi; mov ax, word ptr [esp + edx*2]` → `0x421553 mov dword ptr [0x48be64], eax`，返回 1；`esi==0` → 返回 0（`0x42153a test esi,esi / je 0x421563`）。

#### 3.4 定時炸彈 (action 34, handler 0x421574, f7=0x01)
- 与地雷同一副骨架，但**没有归属筛选**：`0x421631 mov ax, word ptr [ebx*2 + 0x48b8c4]; 0x421639 mov word ptr [esp + esi*2], ax; 0x42163d inc esi` —— 凡"可达 ∩ 路径"节点都进候选。
- 选中后 `0x42163f jmp 0x4215a7`，收尾跳到与地雷**共用的** `0x42153a` 尾部（`call 0x456f2d; idiv esi` 随机选）。

#### 3.5 機車 (action 35, handler 0x421644, f7=0x00) / 3.6 汽車 (action 36, handler 0x421675, f7=0x00)
```asm
00421644  push       ebx
00421645  xor        ebx, ebx
00421647  imul       edx, dword ptr [0x49910c], 0x68
0042164e  test       byte ptr [edx + 0x496b79], 3     ; player+0x11 & 3 = 载具等级
00421655  jne        0x421671
00421657  call       0x456f2d
0042165e  mov        ecx, 4
00421666  idiv       ecx
00421668  test       edx, edx
0042166a  jne        0x421671                         ; rand()%4 != 0 → 否
0042166c  mov        ebx, 1
00421671  mov        eax, ebx
```
汽車把两处判据换成 `0x421685 and dl, 3 / 0x421688 cmp dl, 2 / 0x42168b jae 0x4216a7`（要求 `< 2`），随机同 `0x42168d call 0x456f2d; idiv 4; test edx,edx; jne`。
即：0=无载具、1=機車、2=汽車；機車要求 `==0`，汽車要求 `<2`，各 25% 概率。

#### 3.7 飛彈 (action 37, handler 0x421717, f7=0x02)
- `0x42172a call 0x40d2d3`（最仇视我的玩家，返回 -1 时 `0x421740 call 0x40d31c`），仍为 -1 → 返回 0（`0x42174f xor eax,eax`）。
- `0x421758 push -1; call 0x40a45c` → 长度；在 `word[esi*2 + 0x48b8c4]` 里找 `0x421782 test ch, 0x80`（0x8000 位）且 `0x421787 test cl, 0xf`（低 4 位非 0），并把最低置位的位号 `edx` 与目标玩家序号 `ebx` 比对：`0x4217a1 cmp edx, ebx / 0x4217a3 jne`，命中则 `0x4217a5 mov dword ptr [0x48be64], ecx`。
- 二次校验：`0x4217b7 push 0x64; ... call 0x40a0b1`（以 `word[p+0x08]`、`word[p+0x0a]` 为中心、半径 0x64 取区域）；区内若出现 0x8000 节点（`0x4217f4 test ch,0x80 / jne 0x42181c`）或**自有**地块（`0x421801 call 0x4216ab / 0x421809 cmp eax,1 / je 0x42181c`）则否决；全清才 `0x421815 mov dword ptr [esp], 1`。
- 辅助 `0x4216ab(player, node)`：`0x4216ce mov cl, byte ptr [eax + 0x19]`（住宅）/`0x421703`（设施）后 `0x4216d6 cmp ecx, eax`（owner == player+1）→ 返回 1。

#### 3.8 遙控骰子 (action 38, handler 0x421827, f7=0x00)
- 前置否决：`0x42183f mov al, byte ptr [edx + 0x496ba7]`（p+0x3f）∈{7,8,0xf} → 0（`0x421848/0x42184d/0x421852`）；`0x42185b cmp byte ptr [edx + 0x496ba1], 0 / jne 0`（p+0x39 非 0 → 0）；`0x421870 cmp eax, 0x2710 / jl 0`（cash+bank < 10000 → 0）；`0x421877 cmp word ptr [edx + 0x496bae], 0 / jl 0`。
- `0x40b221(current,6)`；6 个路径节点，节点须 `[node+0x24] & 0xf000 >> 0xc == 0`（`0x421a1e test edx, edx / jne skip`）；owner 非 0 时排除当事人类型 `{5,6,7,8,0xa,0xb,0x10,0x11,0x12}`（`0x4218a0..0x4218f8`）。
- 无主住宅：同地名自有地 > 1（`0x421997 cmp edi, 1 / jle skip`）且 `cash > word[land+0x1c] * 2.5`（常量双精度 `0x463d48 = 2.5`）：
```asm
004219a3  fild       dword ptr [eax + 0x496b84]     ; cash
004219ab  mov        ax, word ptr [ebp + 0x1c]      ; 地价
004219b7  fmul       qword ptr [0x463d48]          ; *2.5
004219bd  fcompp
004219c2  jae        0x4219d6                       ; 地价*2.5 >= cash → 跳过
```
- 自有住宅：`0x421a48 cmp byte ptr [ebp + 0x18], 0 / jne skip`、`0x421a4e cmp byte ptr [ebp + 0x1a], 5 / jae skip`、同地名 > 1、`cash > word[land+0x1e]*2.5`（`0x421a9b..0x421aba`）、且等级 `0x421ac5 cmp eax, dword ptr [esp] / jle skip` 取最大（`0x421ace mov dword ptr [esp], eax`）。
- 设施：无主需 `cash > word[fac+0x22]*2.5`（`0x421b13..0x421b39 jb 0x4219c4`）；自有需 `fac+0x18 != 0` 且 `!= 3`、`level < 5`、`cash > word[fac+0x24]*2.5` 且取等级最大（`0x421b3f..0x421b83`）。
- 末尾 `0x421b88 cmp dword ptr [esp + 4], 0 / jne`；`0x421b8f cmp dword ptr [esp], 0 / je 0x421b9d`；`0x421b95 mov dword ptr [esp + 4], 1`（有最佳等级则放行）。**本 handler 无 rand。**

#### 3.9 機器工人 (action 39, handler 0x421ba6, f7=0x01)
- `0x421bb4 call 0x40a45c`（`push -1`）→ 长度 `ebp`；遍历 `word[esi*2 + 0x48b8c4]`。
- 住宅（属自己）：`0x421bfa mov bl, byte ptr [eax + 0x19]` / `0x421c04 cmp ebx, edi`（edi = current+1）、`0x421c0c cmp byte ptr [eax + 0x18], 0 / jne`、`0x421c2e cmp byte ptr [eax + 0x1a], 5 / jae`；取值 `0x421c1b mov bx, word ptr [eax + ebx*2 + 0x20]`（ebx=等级），`0x421c26 cmp ecx, ebx / jge` 取最大，命中写 `0x421c94 mov dword ptr [0x48be64], edx`。
- 设施（属自己）：`0x421c70 movzx edi, byte ptr [eax + 0x18]`（类型）、`0x421c74 mov bl, byte ptr [eax + 0x1a]`（等级）、`0x421c77 cmp bl, byte ptr [edi + 0x474940] / jae`；取值 `0x421c84 mov ax, word ptr [eax + ebx*2 + 0x24]`。
- 收尾：`0x421ca0 test ecx, ecx / je 0x421cab` → `[esp]=1` 当且仅当最佳值非 0。**无 rand。**

#### 3.10 時光機 (action 40, ord 10, handler 0x420edf, f7=0x02)
```asm
00420edf  xor        eax, eax
00420ee1  ret
```
恒返回 0。此外**驱动层根本不把它送进门**：`0x447fda cmp eax, 9 / 0x447fdd je 0x447fab`（槽 i==9 = ord 10）。（0x4753a0 表中 ord 10 的条目也正是 `0x420edf`。）人类玩家可以用它（效果函数 `0x447387` 存在），AI 不会。

#### 3.11 傳送機 (action 41, handler 0x421cb6, f7=0x01)
- `0x421cc1 call 0x409ef9` → 长度；遍历 `word[edx*2 + 0x48b8c4]`。
- 无主住宅：`0x421d1e cmp byte ptr [eax + 0x19], 0 / jne skip`、`0x421d28 cmp byte ptr [eax + 0x18], 0 / jne skip`、`0x421d32 cmp byte ptr [eax + 0x1a], 3 / jb skip`（等级>=3）、等级 > 当前最佳 `0x421d40 cmp ecx, esi / jge skip`、`0x421d51 imul eax, dword ptr [0x4990e8]; 0x421d58 cmp eax, dword ptr [ebx + 0x496b84]; jge skip`（`word[land+0x1e]*pi < cash`）。
- 无主设施：`0x421da0 cmp byte ptr [eax + 0x18], 0 / je skip`、`0x421da6 cmp byte ptr [eax + 0x1a], 3 / jb skip`、`0x421db9 imul esi, dword ptr [0x4990e8]; 0x421dc0 cmp esi, dword ptr [ebx + 0x496b84]; jge skip`（`word[fac+0x24]*pi < cash`）。
- 收尾：`0x421dee test ecx, ecx / je`；`0x421dfe cmp eax, 0x2710 / jle`（cash+bank>10000）；`0x421e05 cmp word ptr [ebx + 0x496bae], 0 / jl`。（本 handler 无 rand。）

#### 3.12 工程車 (action 42, handler 0x421e20, f7=0x02)
```asm
00421e24  imul       edx, dword ptr [0x49910c], 0x68
00421e2b  mov        al, byte ptr [edx + 0x496b79]     ; player+0x11
00421e31  and        al, 3
00421e33  cmp        al, 3
00421e35  jne        0x421e3c
00421e37  xor        eax, eax                          ; 载具等级==3 → 否
00421e3c  movzx      esi, byte ptr [edx + 0x496b7f]    ; player+0x17 個性
00421e43  call       0x456f2d
00421e4a  mov        ecx, 0xf
00421e52  idiv       ecx
00421e54  cmp        edx, esi
00421e56  jg         0x421e5d
00421e58  mov        ebx, 1                            ; rand()%15 <= 個性 → 用
```
**唯一一个既看 `個性` 又自带 rand 的 handler**：概率 = `(個性+1)/15`。

#### 3.13 核子飛彈 (action 43, handler 0x421e62, f7=0x02)
- 建候选：住宅 `i=1..[0x498e98]`：`0x421e9e mov dl, byte ptr [eax + 0x19]`（owner 非 0）、`0x421eb0 cmp ecx, edx / je skip`（非自己）、`0x421eb4 cmp byte ptr [eax + 0x1a], 0 / je skip`（等级非 0）→ `0x421ece mov word ptr [esp + edx*2], bx`（bx = `i + 0x7d0`）；设施同理用 `+0xfa0`（`0x421f26`、`0x421f3a`），上界 `[0x498e8c]`。
- 无候选 → 0（`0x421f51 cmp dword ptr [esp + 0x41c], 0 / je 0x4221ae`）。
- 最多抽 10 次（`0x422160 cmp ecx, 0xa / jge 0x4221ae`），每次：
```asm
0042216f  call       0x456f2d
00422179  idiv       dword ptr [esp + 0x41c]     ; % 候选数
00422180  mov        ax, word ptr [esp + edx*2]  ; 随机候选地块
00422189  mov        dword ptr [esp + 0x418], eax
```
- 对选中地块取爆风区（`0x421f9d call 0x40a0b1`；住宅用 `word[land+0]`/`word[land+2]`，设施用 `word[fac+0]`/`word[fac+2]` 作坐标），遍历区内 `0x48b8c4` 节点：带 0x8000 位 → 置 `[esp+0x414]=1`（`0x421fe2 test bh, 0x80 / 0x421fe7`）并跳出；否则按 `0x422026 cmp dword ptr [esp + 0x42c], 1` 把等级分别累入 `edi`/计数 `0x424` 与 `esi`/计数 `0x428`。
- 阈值 = `1/(存活玩家数+2)`：`0x4220e9 call 0x40d2b4`（数 `byte[p+0x15] != 0` 的玩家）、`0x4220ee add eax, 2`、`0x422101 fdivrp st(1)`；两条判据 `0x42211b fcomp dword ptr [esp + 0x400]; 0x422125 jae 0x422151` 与 `0x42212e fcomp dword ptr [esp + 0x400]; 0x422138 jae 0x422151`（两个比值都必须 `< 阈值`），通过才 `0x422141 mov dword ptr [0x48be64], eax`。
- **未决/推断**：`0x422026 cmp dword ptr [esp + 0x42c], 1` 所读的槽位在本函数中**首次写于 0x422098（累加循环之后）**，而 `0x4216ab` 的返回值落在 `[esp + 0x434]`（`0x422003` 写入）却**未被读取**。推断原意是按"该节点是否属于自己"分两桶，但编译后的代码读到的是栈残留；首次抽样时该值来自调用者栈帧。存疑，需差分验证。

### 4. `_rich4_get_ai_tool_param_value` 0x00420eee

**地址更正**：该函数实际在 **0x00420eee**（asm 线索里 `_rich4_get_ai_tool_param_value:` 标签就落在 `0x420eed ret` 之后）；`0x420e9a` 是道具门+派发器 `fcn_00420e9a`。

原文（整函数 3 条指令，`0x420eee..0x420ef9`）：
```asm
00420eee  mov        eax, dword ptr [esp + 4]
00420ef2  mov        eax, dword ptr [eax*4 + 0x48be64]
00420ef9  ret
```
- 表基址 **`0x48be64`**（`.bss`，运行时数组），步长 **4 字节**，索引 = **道具序号 ord（1..13）**，返回该 dword。
- 它读的正是各 handler 写进 `0x48be64` 的**目标参数**（节点号 / 玩家序号等）；写入点：`0x42110b`、`0x42128e`（路障）、`0x4213a6`、`0x421553`（地雷/定時炸彈）、`0x4217a5`（飛彈）、`0x4219c9`、`0x421ad6`（遙控骰子）、`0x421c94`（機器工人）、`0x421d66`、`0x421de3`（傳送機）、`0x422141`（核子飛彈）。卡片孪生体是 `0x41e6f2`（`mov eax, dword ptr [eax*4 + 0x48be58]`）。
- **调用者**（`call 0x420eee`，共 8 处）：`0x446bef`、`0x446cd0`、`0x446db1`、`0x447009`、`0x447252`、`0x4472e0`、`0x447661`、`0x447b1b` —— 全部落在**人类用道具 UI / 效果执行**区（`0x446b..0x447b`），即"人类选完目标 → 用 AI 池读回参数"这一共用约定。**AI 决策路径本身不调用它**（AI 侧直接用 `[ord*4+0x475dd5]` 派发，效果函数再读 `0x48be64`）。
- 注意：`0x420e9a`（门）的调用者**只有 1 处**：`0x448039`。

### 5. 随机数调用点清单

`0x456f2d` = `libc_rand`：`0x456f37 imul edx, dword ptr [eax], 0x41c64e6d` / `0x456f3d add edx, 0x3039` / `0x456f47 shr eax, 0x10` / `0x456f4a and eax, 0x7fff`（返回 0..0x7fff）。

| VA | 随机用法 | 阈值 | 作用 |
|---|---|---|---|
| 0x420eca | `call 0x456f2d` → `idiv 3` | 仅当 `f7-個性 == 1`；`%3==0` 通过 | 道具门（阈值门） |
| 0x447ff5 | `call 0x456f2d` → `idiv esi`（esi=候选数） | 仅当候选数 `> 4`（`0x447ff0 cmp esi,4`） | 选起始槽（选择） |
| 0x42153e | `call 0x456f2d` → `idiv esi` | `esi` = 地雷/定時炸彈候选数 | 选目标地块（选择）；地雷 `0x4213c5` 与定時炸彈 `0x421574` 共用 |
| 0x421657 | `call 0x456f2d` → `idiv 4` | `%4==0`（25%） | 機車 是否使用（阈值门） |
| 0x42168d | `call 0x456f2d` → `idiv 4` | `%4==0`（25%） | 汽車 是否使用（阈值门） |
| 0x421e43 | `call 0x456f2d` → `idiv 0xf` | `%15 <= player[+0x17]` | 工程車 是否使用（阈值门） |
| 0x42216f | `call 0x456f2d` → `idiv [esp+0x41c]` | 最多 10 次（`0x422160 cmp ecx,0xa`） | 核子飛彈 候选抽样（选择） |
| 0x448bb1 | `call 0x456f2d` | — | **不在 AI 路径**（`0x44808a` 起的 UI/一般用道具函数） |
| 0x441d4a | `call 0x456f2d` → `idiv esi` | 仅当卡片数 `> 8` | （对照）卡片驱动的起始槽 |
| 0x40b2f2 | `call 0x456f2d` → `idiv ebx` | 每跳候选邻格数 | `0x40b221` 生成 `0x48b8b4` 随机游走路径 |
| 0x441e4a / 0x441e8e | `call 0x456f2d` | — | （对照）卡片辅助函数随机取卡 |

**关键区别（remake 需还原的原版行为）**：门的随机**只在 `f7-個性 == 1` 时**才发生，且是 `rand()%3==0` 的 1/3 通过；`f7-個性 >= 2` 时根本不掷骰（恒定否决），`<= 0` 时恒定通过。

### 汇编摘录

```asm
; ---- 派发：卡 vs 道具（0x418e13） ----
00418e13  call       0x4284be
00418e18  call       0x456f2d
00418e1d  test       al, 1
00418e1f  je         0x418e28
00418e21  call       0x441baa
00418e26  jmp        0x418e2d
00418e28  call       0x447d97

; ---- 道具门 0x420e9a（完整） ----
00420e9a  mov        eax, dword ptr [esp + 4]
00420e9e  xor        edx, edx
00420ea0  mov        dl, byte ptr [eax*8 + 0x47fee1]
00420ea7  imul       eax, dword ptr [0x49910c], 0x68
00420eae  mov        al, byte ptr [eax + 0x496b7f]
00420eb4  and        eax, 0xff
00420eb9  sub        edx, eax
00420ebb  mov        eax, edx
00420ebd  cmp        edx, 2
00420ec0  jl         0x420ec5
00420ec2  xor        eax, edx
00420ec4  ret
00420ec5  cmp        edx, 1
00420ec8  jne        0x420ee2
00420eca  call       0x456f2d
00420ecf  mov        edx, eax
00420ed1  mov        ecx, 3
00420ed6  sar        edx, 0x1f
00420ed9  idiv       ecx
00420edb  test       edx, edx
00420edd  je         0x420ee2
00420edf  xor        eax, eax
00420ee1  ret
00420ee2  mov        eax, dword ptr [esp + 4]
00420ee6  call       dword ptr [eax*4 + 0x47539c]
00420eed  ret

; ---- 参数读取 0x420eee ----
00420eee  mov        eax, dword ptr [esp + 4]
00420ef2  mov        eax, dword ptr [eax*4 + 0x48be64]
00420ef9  ret

; ---- 道具驱动 AI 分支（0x447f82 - 0x448085） ----
00447f82  test       dl, 6
00447f85  je         0x447f7a
00447f87  test       byte ptr [eax + 0x496b7e], 2
00447f8e  je         0x447f7a
00447f90  push       0xd
00447f92  push       0
00447f94  lea        eax, [esp + 0x40]
00447f98  push       eax
00447f99  call       0x456f60
00447fa1  xor        ecx, ecx
00447fa3  mov        dword ptr [esp + 0x48], ecx
00447fa7  xor        esi, esi
00447fa9  jmp        0x447fb9
00447fab  mov        edx, dword ptr [esp + 0x48]
00447faf  inc        edx
00447fb0  mov        dword ptr [esp + 0x48], edx
00447fb4  cmp        edx, 0xd
00447fb7  jge        0x447fec
00447fb9  mov        eax, dword ptr [0x49910c]
00447fbe  mov        ebx, eax
00447fc0  shl        ebx, 2
00447fc3  add        ebx, eax
00447fc5  mov        eax, ebx
00447fc7  shl        ebx, 2
00447fca  sub        ebx, eax
00447fcc  mov        eax, dword ptr [esp + 0x48]
00447fd0  cmp        byte ptr [ebx + eax + 0x49915c], 0
00447fd8  je         0x447fab
00447fda  cmp        eax, 9
00447fdd  je         0x447fab
00447fdf  mov        al, byte ptr [esp + 0x48]
00447fe3  inc        al
00447fe5  mov        byte ptr [esp + esi + 0x38], al
00447fe9  inc        esi
00447fea  jmp        0x447fab
00447fec  test       esi, esi
00447fee  je         0x447f7a
00447ff0  cmp        esi, 4
00447ff3  jle        0x448005
00447ff5  call       0x456f2d
00447ffa  mov        edx, eax
00447ffc  sar        edx, 0x1f
00447fff  idiv       esi
00448001  mov        ebx, edx
00448003  jmp        0x448007
00448005  xor        ebx, ebx
00448007  xor        edi, edi
00448009  mov        dword ptr [esp + 0x48], edi
0044800d  jmp        0x448028
0044800f  inc        ebx
00448010  cmp        ebx, esi
00448012  jne        0x448016
00448014  xor        ebx, esi
00448016  mov        ebp, dword ptr [esp + 0x48]
0044801a  inc        ebp
0044801b  mov        dword ptr [esp + 0x48], ebp
0044801f  cmp        ebp, 4
00448022  jge        0x447f7a
00448028  mov        dh, byte ptr [esp + ebx + 0x38]
0044802c  test       dh, dh
0044802e  je         0x447f7a
00448034  xor        eax, eax
00448036  mov        al, dh
00448038  push       eax
00448039  call       0x420e9a
0044803e  add        esp, 4
00448041  cmp        eax, 1
00448044  jne        0x44800f
00448046  xor        eax, eax
00448048  mov        al, byte ptr [esp + ebx + 0x38]
0044804c  mov        edx, dword ptr [eax*8 + 0x47feda]
00448053  push       edx
00448054  push       0x4653e5
00448059  lea        eax, [esp + 8]
0044805d  push       eax
0044805e  call       0x457110
00448063  add        esp, 0xc
00448066  push       0x5dc
0044806b  lea        eax, [esp + 4]
0044806f  push       eax
00448070  call       0x440cac
00448075  add        esp, 8
00448078  xor        eax, eax
0044807a  mov        al, byte ptr [esp + ebx + 0x38]
0044807e  call       dword ptr [eax*4 + 0x475dd5]

; ---- 道具决策跳表（0x4753a0 起的 13 个 dword，文件字节） ----
; 004753a0  fa 0e 42 00  7f 10 42 00  c5 13 42 00  74 15 42 00
; 004753b0  44 16 42 00  75 16 42 00  17 17 42 00  27 18 42 00
; 004753c0  a6 1b 42 00  df 0e 42 00  b6 1c 42 00  20 1e 42 00
; 004753d0  62 1e 42 00
; → 0x420efa 0x42107f 0x4213c5 0x421574 0x421644 0x421675 0x421717
;   0x421827 0x421ba6 0x420edf 0x421cb6 0x421e20 0x421e62   (ord 1..13)

; ---- 機車/汽車（0x421644） ----
00421647  imul       edx, dword ptr [0x49910c], 0x68
0042164e  test       byte ptr [edx + 0x496b79], 3
00421655  jne        0x421671
00421657  call       0x456f2d
0042165e  mov        ecx, 4
00421666  idiv       ecx
00421668  test       edx, edx
0042166a  jne        0x421671
0042166c  mov        ebx, 1

; ---- 工程車（0x421e20） ----
00421e3c  movzx      esi, byte ptr [edx + 0x496b7f]
00421e43  call       0x456f2d
00421e4a  mov        ecx, 0xf
00421e52  idiv       ecx
00421e54  cmp        edx, esi
00421e56  jg         0x421e5d
00421e58  mov        ebx, 1

; ---- 地雷/定時炸彈共用尾部：随机选地块（0x42153a） ----
0042153a  test       esi, esi
0042153c  je         0x421563
0042153e  call       0x456f2d
00421548  idiv       esi
0042154a  mov        ax, word ptr [esp + edx*2]
0042154e  and        eax, 0xffff
00421553  mov        dword ptr [0x48be64], eax
00421558  mov        dword ptr [esp + 0x200], 1

; ---- rand 本体（0x456f2d） ----
00456f2d  call       0x456f23
00456f32  test       eax, eax
00456f37  imul       edx, dword ptr [eax], 0x41c64e6d
00456f3d  add        edx, 0x3039
00456f43  mov        dword ptr [eax], edx
00456f45  mov        eax, edx
00456f47  shr        eax, 0x10
00456f4a  and        eax, 0x7fff
00456f4f  ret
```

### 未决

1. **`+4` 处 4 字节字段的官方语义**：已证实 `byte+4` 被写入 `0x499198`/`0x497320` 并当"重复次数"用（`0x441e33`），`byte+5` 被送进 `0x44f230`（内含 `0x64`/`0x32` 分档）。但"价格"的确切货币换算（是否 ×1000、是否再乘 `price_index`）**未定**；`byte+6` 的用途**未决**。表中"价格"列只保证是 `byte+5` 的原值。
2. **`0x48b8b4` / `0x48b8c4` 的完整语义**：已证实 `0x40b221`/`0x40b343` 用 `rand()` 逐跳写入 `0x48b8b4`（最多 8 word，路径/落点候选），`0x409ef9` 从 `[0x474938]` 的 `0x1b8×0x1b8` 屏幕格表把非空项写进 `0x48b8c4`；`0x40a45c` 亦写 `0x48b8c4`。`0x40b221(cur,4)` 与 `0x40b343(cur,6)` 的 N（4 步 / 6 步）与"前进/后退"方向差异**未定**。
3. **核子飛彈的 `[esp+0x42c]` 读栈残留**（见 3.13）：是原版 bug 还是我的读法有误，需用 `tools/emulate.py` 差分确认。
4. **`0x40b221(cur,4)` 返回非 0** 的确切含义（`0x40b221` 末尾 `mov eax, [esp+8]`，该槽在 `0x40b309` 被置 1）只知"发生过 rand 选点"；对 機器娃娃/路障/遙控骰子 的门控语义未定。
5. **`node+0x24` 位域**：本文用到 `& 0x3f0000 >> 0x10`（owner）、`& 0xf000 >> 0xc`、`& 0xff`、`test 0x3fff00`；位段命名未定。`0x496d08 + 24*(owner-1)` 的类型码 `{5,6,7,8,0xa,0xb,0x10,0x11,0x12}`（比较点 `0x4218b6..0x421901`）含义未定。
6. `word[0x48bae0]` / `word[0x48bae2]` 两个特殊节点（地雷/定時炸彈在 `[0x496b30]`/`[0x496b60]` 非 0 时直接选它）到底是什么（推断为监狱/医院一类），**未决**。
7. `0x40a0b1(a,b,0x64)` 与 `0x40a45c(-1)` 的"区域/长度"语义未定（前者以 `sar 5` 转格坐标并用 `memset(0x474938,0,0x5e880)` 重建格表）。
