## AI 买地 / 盖房 / 落点决策

真值：`Rich4/rich4.exe`（ImageBase 0x400000，PE32）。全部 VA 由本次自行反汇编（capstone 5.0.7）取得，
指令文本为真实反汇编输出。凡未经指令直接证明者标「推断」，无法确证者标「未决」。

---

### 1. 行动路由 0x00417d65（动作号 → 决策类别 对照表）

**先修正前提：0x417d65 不是「AI 路由」，而是「顶部 11 格指令条 / 热键」的动作分派器。**

证据：

* 入口读第一实参作为动作号：
  `00417d65  push ebx` → `00417d66  push 0` → `00417d68  call 0x402460` → `00417d6d  add esp, 4`
  → `00417d70  call 0x419703` → `00417d75  mov dword ptr [0x48bde4], 0xffffffff`
  → `00417d7f  push 1` → `00417d81  call 0x415d31` → `00417d86  add esp, 4`
  → `00417d89  mov ecx, dword ptr [esp + 8]`（此时 esp=入口-4，[esp+8]=第一实参）
  → `00417d8d  cmp ecx, 0xa` → `00417d90  ja 0x417dff`
  → `00417d96  mov eax, ecx` → `00417d98  jmp dword ptr [eax*4 + 0x417d39]`
* 跳表 0x417d39 共 11 项（本次直接读 dword，与任务给定锚点逐项一致）：
  `[0]=0x417d9f [1]=0x417dad [2]=0x417db6 [3]=0x417dbd [4]=0x417dcb [5]=0x417dd2
   [6]=0x417dd9 [7]=0x417de0 [8]=0x417de7 [9]=0x417dee [10]=0x417df5`
* 全文件扫描 `call/jmp rel32` 指向 0x417d65 者**只有两处**：`0x00401321`、`0x00418870`（无第三处、无数据表指针）。
  - `0x00418870`：位于 WndProc `0x00417e26` 的 WM_LBUTTONUP 分支。
    `004186f3  mov bl, byte ptr [0x48be28]` → `00418855  cmp bl, 0xc` → `00418858  jne 0x418863`
    → `00418863  cmp bl, 0x64` → `00418866  jb 0x418878` → `00418868  xor eax, eax`
    → `0041886a  mov al, bl` → `0041886c  sub eax, 0x64` → `0041886f  push eax` → `00418870  call 0x417d65`
    即 **动作号 = 控件号 - 0x64**。控件号 ≥0x64 的唯一产生点在同一函数的鼠标按下分支：
    `00418670  cmp esi, 0x1b8`（x<440）→ `00418678  cmp edx, 0x28`（y<40）
    → `0041868c  mov ebx, 0x28` → `00418698  idiv ebx` → `0041869a  add eax, 0x64`
    → `0041869d  mov byte ptr [0x48be28], al`。
    即屏幕左上 440×40 的一条 11 格、每格 40px 的指令条。
  - `0x00401321`：热键/命令分派链（`0x0046cb07` 为按键码），逐项比较 .bss 中的热键表后 push 动作号：
    `00401314  mov dx, word ptr [0x497180]` → `0040131f  push 0xa` → `00401321  call 0x417d65`
    `0040132d  mov dx, word ptr [0x497182]` → `00401338  push 9`
    `0040133e  mov dx, word ptr [0x497184]` → `00401349  push 8`
    `0040134f  mov dx, word ptr [0x497186]` → `0040135a  push 7`
    `00401360  mov dx, word ptr [0x497188]` → `0040136b  push 6`
    `00401371  mov dx, word ptr [0x49718a]` → `0040137c  push 5`
    `00401390  mov dx, word ptr [0x497190]` → `00401405  push 2`
    `0040140e  mov dx, word ptr [0x497192]` → `00401419  push 1`
    `00401422  mov dx, word ptr [0x497194]` → `0040142d  push 4`
    `00401436  mov dx, word ptr [0x497196]` → `00401441  push 3`
    `0040144a  mov dx, word ptr [0x497198]` → `00401455  push 0`
    这些表项位于 `.bss`（0x48a000–0x49a000 原始大小 0，运行时初始化），故其值**未决**；但动作号常量本身在代码里。

**AI 完全不经过此路由**：AI 回合驱动 `0x00418c55` 直接调用同一批底层函数
（`00418e13  call 0x4284be`、`00418e21  call 0x441baa`、`00418e28  call 0x447d97`）。
因此「AI 动作号从哪来」这一问的答案是：**AI 没有动作号**；动作号只属于人类/托管玩家的指令条与热键。

| case | 处理函数 VA | 决策类别 | 证据（真实指令/字符串） |
|---|---|---|---|
| 0 | 0x0044eb39 | 系统：说明（help）窗口，**非 AI** | `00417d9f push 0x3c` `00417da1 push 0x14` `00417da3 call 0x44eb39`；`0044eb3c push 0x466096`（"help.mkf"）`0044eb49 mov dword ptr [0x48c5f4], eax` |
| 1 | 0x00411b53 | 系统：游戏设定/选项窗口，**非 AI** | `00411bb6 mov ecx, dword ptr [ebx*4 + 0x474a54]` 循环 `00411bd0 cmp ebx, 0xa`；0x474a54 起 10 个标签＝游戏速度/动画过程/音 乐/音 效/自动存档/乐 曲/视 窗/日、月历/缩小地图/组合画面 |
| 2 | 0x0041e345 | 系统：託管AI 设定面板，**非 AI 决策本身** | 字符串 0x463cd8「託管AI」、0x463cdf「個  性」、0x463ce6「資金運用比例」、0x463cf3「使用卡片」、0x463cfc「使用道具」、0x463d05/0x463d0c/0x463d13「乖寶寶/普通人/大老奸」；`0041e5a6 test byte ptr [eax + 0x496b7d], 1` 只列出 bit0 置位的玩家 |
| 3 | 0x00403d74 | 系统：读取存档（LOAD），**非 AI** | `00403e11 push 0x4630d8`（"SAVE%d.DAT"）`00403e23 push 0x4630e3`（"rb"）；路由 case3 `00417dbd push 1` `00417dbf call 0x403d74` |
| 4 | 0x00404165 | 系统：存档（SAVE），**非 AI**（推断） | 与 0x403d74 结构孪生：`00404170 push 0x208`、`0040418d push 2`、`004041b9 movsx edx, word ptr [eax + 0x18]`；本函数无 DGROUP 字符串引用（文案来自资源），故标签为推断 |
| 5 | 0x0040a9bd | 系统：缩小地图窗口，**非 AI**（推断） | `0040a9bf push 0x40a801` `0040a9c4 call 0x4018e7`（模态对话）；对话过程序把每位玩家坐标缩放后画头像：`0040a8fb shl eax, 7` → `0040a8fe sar eax, 0x10`、矩形 `0040a938..0040a94f`＝0x14,0x3c,0x1a4,0x1cc、头像 `0040a909 mov eax, dword ptr [eax + 0x498eb0]` `0040a90f add eax, 0x48` |
| 6 | 0x00424492 | 系统：清单/资料窗口，**非 AI** | `004244ca push 0x423cf3` `004244cf call 0x4018e7`；对话过程序用 `00423d91 cmp dword ptr [0x4753fc], 1`（清单类型）、`00423d9c mov ecx, dword ptr [0x475400]`（选中项）、`004240fd mov edx, dword ptr [ebx*4 + 0x47540c]`；0x47540c 起＝資產清單/地產清單/股票清單/現  金/存  款/貸  款/總資產/股  票/… |
| 7 | 0x00447d97 | **行动：使用道具**（AI 自动分支 / 人类对话框） | `00447da5 mov dl, byte ptr [eax + 0x496b7d]` `00447dab cmp dl, 1` `00447dae jne 0x447f82`（≠1→自动分支）；`00447f87 test byte ptr [eax + 0x496b7e], 2`（使用道具许可位）；道具槽 `00447fd0 cmp byte ptr [ebx + eax + 0x49915c], 0`；名表 0x47feda；`00448054 push 0x4653e5`（"使用%s"） |
| 8 | 0x00441baa | **行动：使用卡片**（AI 自动分支 / 人类对话框） | `00441bbb mov dl, byte ptr [eax + 0x496b7d]` `00441bc1 cmp dl, 1` `00441bc4 jne 0x441d00`；`00441d09 test byte ptr [eax + 0x496b7e], 1`（使用卡片许可位）；卡片槽 `00441d7d mov al, byte ptr [edx + eax + 0x499120]`；名表 0x47fdea；AI 判据 `00441db2 call 0x41e69e` |
| 9 | 0x004284be | **行动：股票交易**（AI 自动分支 / 人类对话框） | `004284d1 cmp byte ptr [eax + 0x496b7d], 1` `004284d8 jne 0x42886e`；人类分支字符串 0x463f1a「股票名稱」/0x463f23「持有張數」/0x463f2c「總 市 價」/0x463f35「類型：」/0x463f3c「市價：」/0x463f43「賣價：」 |
| 10 | 0x0042b58f | 系统：股票表/持有股数表，**非 AI** | `00417df5 push 0` `00417df7 call 0x42b58f`；字符串 0x4640a6「持有股數表」、0x4640b1「股 價 表」、0x4640ba「股票名稱」、0x4640c3「成交價」、0x4640ca「漲跌」、0x4640cf「交易量」、0x4640d6「持有股數」、0x4640df「平均成本」、0x4640e8「本日休市」 |

结论：11 个 case 中只有 **7 / 8 / 9** 属于「回合内行动决策」，且 AI 走的是同函数的自动分支；
**0..6、10 全部是系统/资讯菜单窗口，与 AI 无关**。

---

### 2. 调用者与动作号的产生

1. 动作号来源（人类/托管路径）见 §1：`0x418870`（指令条，动作号 = 控件号−0x64）与 `0x401321`（热键表）。
2. AI 路径没有动作号，走独立的回合驱动：
   * 主循环调用点：`00401db3  call 0x418c55`，前置条件
     `00401d8d imul eax, dword ptr [0x49910c], 0x34`
     `00401d94 cmp byte ptr [eax + 0x498ea2], 0` / `00401d9d mov ch, byte ptr [eax + 0x498ea0]`
     `00401da3 test ch, 0x80` / `00401daa and dl, 0x7f`。
   * 回合驱动 `0x418c55`：先调 AI 状态机 `00418d6e push 0` `00418d70 call 0x40c912`（返回 0..5）
     → `00418d78 cmp eax, 5` → `00418d81 jmp dword ptr [eax*4 + 0x418c3d]`，
     跳表 0x418c3d（本次直接读 dword）＝`0x418d88, 0x418d99, 0x418dc6, 0x418e7a, 0x418e7a, 0x418dc6`
     （state 0 = 落点/行动；state 1 = `00418db0 call dword ptr cs:[0x46231c]` 移动鼠标；state 2/5 = 决策块；state 3/4 = 直接返回）。
   * **决策块（state 2/5）** `0x418dc6`：
     `00418de5 push esi` `00418de6 call 0x42bf03`
     `00418df3 push eax` `00418df4 call 0x42c79f`
     `00418dfc push 0` `00418dfe call 0x436b0a`
     `00418e13 call 0x4284be`（股票/行动）
     `00418e18 call 0x456f2d` `00418e1d test al, 1` `00418e1f je 0x418e28`
     `00418e21 call 0x441baa`（用卡） / `00418e28 call 0x447d97`（用道具）
   * state 0 处理 `0x418e7f`：`00418e7f push 1` `00418e81 call 0x40c912`，返回非 0 时
     `00418e94 mov ax, word ptr [eax + 0x496b74]` → `00418ea1 call 0x41982d`（**落点处理**）。
     `0x41982d` 全文件唯一调用点即 `0x00418ea1`（call rel32 扫描）。
3. 卡片的「个性门控」决策分派器（AI 独立使用卡片的入口）：
   `0x41e69e`，唯一调用点 `00441db2`（在 0x441baa 的 AI 分支内）。见 §6 第 2 行。

---

### 3. 买地判据

落点处理函数 `0x0041982d`（`0041982d push ebx` 起）：

```
00419837  mov edx, dword ptr [esp + 0x10c]      ; 落点/事件序号
0041983e  mov eax, edx
00419840  shl eax, 2
00419843  add eax, edx
00419845  shl eax, 3                             ; eax = 序号 * 0x28
00419848  mov edx, dword ptr [0x498e80]          ; 事件/落点数组，stride 0x28
0041984e  add eax, edx
00419850  mov dx, word ptr [eax + 0x20]          ; +0x20 = 地点 id
0041985b  mov ebx, dword ptr [eax + 0x24]        ; +0x24 = 事件类型（低字节）
00419864  mov byte ptr [esp + 0xf4], 0x80        ; 默认返回码 0x80
0041986c  imul eax, dword ptr [0x49910c], 0x68
00419873  cmp byte ptr [eax + 0x496b9f], 0       ; 玩家 +0x37
0041987a  je 0x419884
0041987c  test ebx, ebx
0041987e  jne 0x41b3d0                           ; 非 0 事件类型 → 直接返回
...
```
**分派按「事件类型」而非地点 id**：
```
00419884  cmp ebx, 2
00419887  jb 0x4198a9
00419889  cmp ebx, 0x10
0041988c  ja 0x4198a9
0041988e  push 0
00419890  xor eax, eax
00419892  mov al, byte ptr [ebx + 0x475299]     ; 每事件类型一字节（任务锚点已给出）
00419898  shl eax, 3
0041989b  add eax, 0x48234a
004198a0  push eax
004198a1  call 0x4542ce
004198a9  cmp ebx, 0x10
004198ac  ja 0x41b3d0
004198b2  jmp dword ptr [ebx*4 + 0x4197e9]
```
跳表 `0x004197e9`（本次直接读 dword）：条目 0..15 ＝
`0x4198b9, 0x41b3d0, 0x41b11e, 0x41b128, 0x41b132, 0x41b13c,
0x41b146, 0x41b15e, 0x41b16c, 0x41b17a, 0x41b184, 0x41b21e, 0x41b2a3, 0x41b302, 0x41b396, 0x41b3b9`。
结合上文 `0041987c test ebx, ebx` / `0041987e jne 0x41b3d0`，可知 **事件类型 0 → 0x4198b9 = 地点结算（买地/盖房/过路费）**，
类型 1 → 0x41b3d0（直接返回），类型 2..0x10 → 其余事件（`0x41b184` 即「得點券５０點」0x463a81）。

**地点 id 分段**（两套不同的地图数组）：

* `0x7d0 ≤ id < 0xfa0`（在 `0x004198b9` 内判定）→ 数组 `0x498e84`，stride `0x34`（＝我方锚点）。
  `004198e4  sub eax, 0x7d0` `004198e9  imul eax, eax, 0x34` `004198ec  mov esi, dword ptr [0x498e84]`
* `0xfa0 ≤ id < 0x1770` → 转入 `0x0041a168`，数组 `0x498e88`，stride `0x38`。
  `0041a18a  sub eax, 0xfa0` `0041a18f  shl eax, 3` `0041a194  shl eax, 1`…（净效果 ×56）
  `0041a199  mov edx, dword ptr [0x498e88]`

#### 3.1 判定分支（0x004198b9，住宅/一般地）

```
004198f4  mov ch, byte ptr [esi + 0x19]     ; owner
004198f7  test ch, ch
004198f9  je 0x41a013                        ; owner==0 → 买地
004198ff  xor edx, edx
00419901  mov dl, ch
00419903  mov eax, dword ptr [0x49910c]
00419908  inc eax
00419909  cmp edx, eax
0041990b  jne 0x419a67                       ; 别人的地 → 过路费
00419911  cmp byte ptr [esi + 0x1a], 5       ; 已有地且是自己的 → 盖房/加盖
00419915  jae 0x41b077
```

#### 3.2 买地（0x0041a013）——**精确条件与立即数**

```
0041a013  imul eax, dword ptr [0x49910c], 0x68
0041a01a  cmp byte ptr [eax + 0x496b9f], 0   ; 玩家+0x37 必须为 0
0041a021  jne 0x41b077
0041a027  cmp byte ptr [eax + 0x496ba7], 0xc ; 玩家+0x3f 不得为 0x0c(12)
0041a02e  je 0x41b077
0041a034  xor ecx, ecx
0041a036  mov cl, byte ptr [esi + 0x1a]      ; level
0041a039  xor edx, edx
0041a03b  mov dx, word ptr [esi + 0x1e]      ; house_price (uint16)
0041a03f  imul edx, ecx                      ; house_price * level
0041a042  xor ecx, ecx
0041a044  mov cx, word ptr [esi + 0x1c]      ; land_price (uint16)
0041a048  add edx, ecx                       ; land_price + house_price*level
0041a04a  mov ebp, dword ptr [0x4990e8]      ; price_index 物價指數
0041a050  imul ebp, edx                      ; cost = price_index * (land_price + house_price*level)
0041a053  cmp ebp, dword ptr [eax + 0x496b84] ; vs 現金(+0x1c)
0041a059  jg 0x41a159                          ; cost > 現金 → 「AI 拒绝」分支
0041a05f  push ebp
0041a060  lea eax, [esi + 4]
0041a063  push eax
0041a064  push 0x4639e1
0041a069  lea eax, [esp + 0xc]
0041a06d  push eax
0041a06e  call 0x457110                        ; sprintf(buf, "%s\n\n費用:%d元\n\n是否買下此地？", name, cost)
0041a076  xor edi, edi
0041a078  imul eax, dword ptr [0x49910c], 0x68
0041a07f  test byte ptr [eax + 0x496b7d], 6    ; (電腦/託管標誌 & 6) != 0
0041a086  je 0x41a098
0041a088  push ebp
0041a089  call 0x41d7d4                        ; ← AI 买地判据(cost)
0041a08e  add esp, 4
0041a091  cmp eax, 1
0041a094  jne 0x41a098
0041a096  mov edi, eax                         ; edi = 1（决定买）
0041a098  imul eax, dword ptr [0x49910c], 0x68
0041a09f  cmp byte ptr [eax + 0x496b7d], 1     ; 恰为 1 → 人类确认框
0041a0a6  jne 0x41a0b8
0041a0a8  mov eax, esp
0041a0aa  push eax
0041a0ab  call 0x440ba8                        ; 模态确认框，返回 1=确定
0041a0b0  add esp, 4
0041a0b3  cmp eax, 1
0041a0b6  je 0x41a0c0
0041a0b8  test edi, edi
0041a0ba  je 0x41b077                          ; AI 说“不买” → 结束
0041a0c0  mov edi, dword ptr [0x49910c]
0041a0c6  push edi
0041a0c7  call 0x40fa61
0041a0cc  add esp, 4
0041a0cf  test eax, eax
0041a0d1  jne 0x41b077
0041a0d7  mov al, byte ptr [0x49910c]
0041a0dc  inc al
0041a0de  mov byte ptr [esi + 0x19], al        ; owner = current_player + 1
...
0041a132  sub dword ptr [eax + 0x496b84], ebp  ; 現金 -= cost
0041a13e  call 0x44f627
```

#### 3.3 AI 买地判据 0x0041d7d4(cost) —— **完整 101 字节**

```
0041d7d4  push esi
0041d7d5  sub esp, 4
0041d7d8  xor ecx, ecx
0041d7da  fild dword ptr [0x49908c]        ; 開局資金設定值
0041d7e0  fmul qword ptr [0x463cc8]        ; × 0.05（双精度常量 = 0.05）
0041d7e6  call 0x457dbc
0041d7eb  fistp dword ptr [esp]
0041d7ee  cmp dword ptr [esp], 0x1b58      ; 7000
0041d7f5  jle 0x41d7fe
0041d7f7  mov dword ptr [esp], 0x1b58      ; 上限 7000
0041d7fe  mov eax, dword ptr [esp]
0041d801  mov esi, dword ptr [0x4990e8]    ; price_index
0041d807  imul eax, esi                    ; reserve = min(floor(資金*0.05),7000) * price_index
0041d80a  mov dword ptr [esp], eax
0041d80d  imul eax, dword ptr [0x49910c], 0x68
0041d814  mov edx, dword ptr [eax + 0x496b84]  ; +0x1c 現金
0041d81a  add edx, dword ptr [eax + 0x496b88]  ; +0x20 存款
0041d820  mov eax, dword ptr [esp + 0xc]       ; 参数 = cost
0041d824  sub edx, eax                         ; 可用 = 現金 + 存款 - cost
0041d826  mov eax, edx
0041d828  cmp eax, dword ptr [esp]
0041d82b  jle 0x41d832
0041d82d  mov ecx, 1                           ; 可用 > reserve → 买
0041d832  mov eax, ecx
0041d834  add esp, 4
0041d837  pop esi
0041d838  ret
```

**买地公式（精确）：**

```
cost    = price_index × ( land_price + house_price × level )
reserve = min( floor( 0x49908c × 0.05 ), 0x1b58 ) × price_index        ; 0x1b58 = 7000
买      ⟺ (現金 + 存款 − cost) > reserve
```

* `0x463cc8` = double `0.05`（本次读文件字节确认）；`0x1b58` = 7000（立即数，位于 `0041d7ee`/`0041d7f7`）。
* `0x49908c` = **开局资金设定值**，不是玩家现值：唯一写点在
  `00407172  mov eax, dword ptr [0x46cb40]` → `00407177  mov eax, dword ptr [eax*4 + 0x46cb94]`
  → `0040717e  mov dword ptr [0x49908c], eax`；表 `0x46cb94` = `{300000, 200000, 100000, 50000, 30000, 10000}`
  （0x46cb94+0x14 = 0x46cbe8 为 `{0,730,365,182,91,30}`，另一组）。整局不变。
* **不是**现金的百分比，**不**乘地价，**不是**固定值；`price_index` 对门槛与成本**同时**生效。
* `0x41a01a`/`0x41a027` 两个玩家级开关（+0x37、+0x3f≠0x0c）先过滤。
* **未考虑** hostility(+0x4c)、owner（买地分支里 owner 恒为 0）、type（type 只在买下之后决定，见下）、level（level=0 时成本中该项为 0）。

**商业地（0xfa0≤id<0x1770）同构**：
```
0041a86b  cmp byte ptr [eax + 0x496b9f], 0     ; +0x37
0041a872  jne 0x41b077
0041a878  cmp byte ptr [eax + 0x496ba7], 0xc   ; +0x3f != 12
0041a87f  je 0x41b077
0041a88c  movzx ebp, word ptr [ebp + 0x22]     ; 商业地买价（+0x22, uint16）
0041a890  imul ebp, dword ptr [0x4990e8]       ; × price_index
0041a897  cmp ebp, dword ptr [eax + 0x496b84]
0041a89d  jg 0x41a159                          ; 现金不足
0041a8c0  test byte ptr [eax + 0x496b7d], 6
0041a8c7  je 0x41a8d9
0041a8c9  push ebp
0041a8ca  call 0x41d7d4                        ; ← 同一 AI 判据
0041a8e0  cmp byte ptr [eax + 0x496b7d], 1
0041a8e7  jne 0x41a8f9
0041a8ec  call 0x440ba8                        ; 人类确认框（同一格式串 0x4639e1）
0041a91f  mov edx, dword ptr [esp + 0xe0]
0041a926  mov byte ptr [edx + 0x19], al        ; owner = cp+1
0041a984  sub dword ptr [eax + 0x496b84], ebp  ; 現金 -= cost
```
因此 **住宅地与商业地共用同一个买地判据 0x41d7d4**。

#### 3.4 买下之后：type 的选择（AI 用随机）
```
0041a21c  imul eax, edx, 0x68
0041a21f  cmp byte ptr [eax + 0x496b7d], 1
0041a226  jne 0x41a23e
0041a228  push 0
0041a22a  call 0x440aac            ; 人类：选类型
0041a232  mov edx, dword ptr [esp + 0xe0]
0041a239  mov byte ptr [edx + 0x18], al
0041a23c  jmp 0x41a25a
0041a23e  call 0x456f2d            ; rand()
0041a243  mov edx, eax
0041a245  mov ecx, 4
0041a24a  sar edx, 0x1f
0041a24d  idiv ecx                 ; rand() % 4
0041a24f  inc edx                  ; +1
0041a250  mov eax, dword ptr [esp + 0xe0]
0041a257  mov byte ptr [eax + 0x18], dl   ; 商業地 type = rand()%4 + 1
```

#### 3.5 「AI 拒绝」分支
* 现金不足：`0041a059 jg 0x41a159`（住宅）/ `0041a89d jg 0x41a159`（商业）/ 盖房 `0041a2e6 jg 0x41a159`、`00419951 jg 0x419a52`
  → `0041a159 push 0x5dc` `0041a15e push 0x46398b`（"您的現金不足！"）`0041a163 jmp 0x419a5d` → `call 0x440cac`（1500ms 提示），再 `jmp 0x41b074`。
* AI 判据返回 0：`0041a0ba je 0x41b077` → `0041b077 mov ecx, dword ptr [esp + 0x10c]`
  `0041b07f mov ebx, dword ptr [0x49910c]` `0041b086 call 0x40f381`（正常结束本次落点），
  最终 `0041b3d0 xor eax, eax` `0041b3d2 mov al, byte ptr [esp + 0xf4]` `0041b3e3 ret`。

---

### 4. 盖房/加盖判据

#### 4.1 住宅地（0x00419911 起，owner == 自己）
```
00419911  cmp byte ptr [esi + 0x1a], 5      ; level 上限 = 5（硬编码）
00419915  jae 0x41b077
0041991b  cmp byte ptr [esi + 0x18], 0      ; 只允许 type == 0（住宅）
0041991f  jne 0x41b077
00419925  imul eax, dword ptr [0x49910c], 0x68
0041992c  cmp byte ptr [eax + 0x496b9f], 0  ; 玩家+0x37 == 0
00419933  jne 0x41b077
00419939  movzx ebp, word ptr [esi + 0x1e]  ; house_price (uint16)
0041993d  imul ebp, dword ptr [0x4990e8]    ; cost = house_price × price_index
00419944  imul eax, dword ptr [0x49910c], 0x68
0041994b  cmp ebp, dword ptr [eax + 0x496b84]  ; vs 現金
00419951  jg 0x419a52                          ; 不足 → 0x46398b「您的現金不足！」
00419957  push ebp
00419958  lea eax, [esi + 4]
0041995b  push eax
0041995c  mov eax, 0x46396d
00419961  push eax
00419962  lea eax, [esp + 0xc]
00419966  push eax
00419967  call 0x457110     ; sprintf(buf, "%s\n\n升級費用:%d元\n\n是否升級？", name, cost)
0041996f  imul eax, dword ptr [0x49910c], 0x68
00419976  test byte ptr [eax + 0x496b7d], 6   ; 電腦/託管 → 直接盖，无对话、无判据、无掷骰
0041997d  jne 0x4199a7
0041997f  imul eax, dword ptr [0x49910c], 0x68
00419986  cmp byte ptr [eax + 0x496b7d], 1    ; 恰为 1 → 人类确认框
0041998d  jne 0x41b077
00419993  mov eax, esp
00419995  push eax
00419996  call 0x440ba8
0041999e  cmp eax, 1
004199a1  jne 0x41b077
004199a7  mov ebx, dword ptr [0x49910c]
004199ad  push ebx
004199ae  call 0x40fa61
004199b6  test eax, eax
004199b8  jne 0x41b077
004199c5  sub dword ptr [eax + 0x496b84], ebp   ; 現金 -= cost
004199d1  inc byte ptr [esi + 0x1a]             ; level++
004199eb  cmp byte ptr [esi + 0x1a], 5
004199ef  jne 0x419a2b                          ; 到 5 级 → 0x4199f1 特殊处理
```

**住宅盖房公式（精确）：** `cost = price_index × house_price(+0x1e)`；条件
`owner==自己 && level<5 && type==0 && 玩家+0x37==0 && cost ≤ 現金`。
**AI 没有独立盖房判据**：`00419976 test byte ptr [eax + 0x496b7d], 6` → `0041997d jne 0x4199a7`
（越过对话框直落 `004199a7` 建屋），成本检查在其之前（`0041994b`）已经做过。即：
**AI 只要付得起就盖，无随机、无門檻、无个性参与。**

#### 4.2 商业地（0x0041a2b3 起，owner == 自己且 level>0）
```
0041a2b3  xor edx, edx
0041a2b5  mov ecx, dword ptr [esp + 0xe0]
0041a2bc  mov dl, byte ptr [ecx + 0x18]      ; type
0041a2bf  mov bl, byte ptr [ecx + 0x1a]      ; level
0041a2c2  cmp bl, byte ptr [edx + 0x474940]  ; 上限表 0x474940[type]
0041a2c8  jae 0x41b077
0041a2d5  movzx ebp, word ptr [ebp + 0x24]   ; 商业加盖价（+0x24, uint16）
0041a2d9  imul ebp, dword ptr [0x4990e8]     ; cost = ×price_index
0041a2e0  cmp ebp, dword ptr [eax + 0x496b84]
0041a2e6  jg 0x41a159                        ; 现金不足
0041a2ee  push 0x46396d                      ; 同一格式串「升級費用」
0041a307  mov ch, byte ptr [eax + 0x496b7d]
0041a30d  test ch, 6
0041a310  jne 0x41a32f                       ; 電腦/託管 → 直接升级
0041a312  cmp ch, 1
0041a315  jne 0x41b077
0041a31e  call 0x440ba8
0041a32f  mov esi, dword ptr [0x49910c]
0041a336  call 0x40fa61
0041a346  imul eax, dword ptr [0x49910c], 0x68
0041a34d  sub dword ptr [eax + 0x496b84], ebp
0041a35a  mov dh, byte ptr [eax + 0x1a]
0041a35d  inc dh
0041a35f  mov byte ptr [eax + 0x1a], dh
0041a362  cmp dh, 5
0041a365  je 0x4199f1
```
上限表 `0x474940`（本次读文件字节）：`[0]=1, [1]=5, [2]=5, [3]=1, [4]=5, [5]=0, [6]=0, [7]=0`。
即商业地按类型 1/2/4 上限 5，类型 3 上限 1。

#### 4.3 0x0044101d 是什么 —— **不是盖房，是「道具开发/研究所」面板**
```
00441024  mov edi, dword ptr [esp + 0x24]
00441028  imul eax, dword ptr [0x49910c], 0x68
0044102f  cmp byte ptr [eax + 0x496b7d], 1     ; 只对人类(==1)开
00441036  jne 0x4411e7
00441040  push 0xb
...
004410c5  mov al, byte ptr [edi + 0x1a]        ; 传入建筑的等级
004410c8  cmp ebx, eax
004410ca  jl 0x441093                          ; 循环 5 格 (0x441097 cmp ebx, 5)
```
字符串 `0x465298`＝「請選擇欲開發道具」；唯一调用点 `0041b109`，前置
`0041b0fc cmp byte ptr [eax + 0x1a], 0` `0041b100 je 0x41b111`
`0041b102 test byte ptr [eax + 0x1c], 0xf` `0041b106 jne 0x41b111`
（[facility+0x18]==4、[facility+0x1a]!=0、([facility+0x1c]&0xf)==0）。**结论：研究所（type 4 建筑）的道具开发 UI，与盖房无关。**

---

### 5. 股票 / 银行 AI

#### 5.1 股票（有确认的 AI 函数）
* `0x004284be`（路由 case 9，人类=股票交易画面）的 **AI 分支 `0x0042886e` 起**（`004284d8 jne 0x42886e`）：
  - `0042886e call 0x456f2d` `00428875 mov ebx, 0xf` `0042887d idiv ebx` `0042887f test edx, edx` `00428881 jne 0x428a37`
    → **rand()%15 == 0（1/15）** 才进入「用卡/用道具」块（卡片槽 `0x499120`、道具槽 `0x49915c`，
    个性门控 `004289b0 sub edx, eax` `004289b2 cmp edx, 2` `004289b5 jne 0x42896e`）。
  - 选中的道具以 `00428a17 imul eax, eax, 0x64` `00428a1a imul eax, dword ptr [0x4990e8]` 计价后
    `00428a2f call 0x4246c5`（参数：current_player, 3, 目标, 价, 0）。
  - `00428a37 call 0x456f2d` … `00428a43 idiv ebx(3)` `00428a48 test edx, edx` `00428a4a jne 0x428ae8`
    → **rand()%3 == 0（1/3）**：遍历持股市价（每股记录 `0x4967e0 + player*0x54 + 股票*12`，
    字段 `+0 類型`、`+2 word 股票id`、`+4 dword 總市價`），用表 0x47fedf / 0x47fdef 重算市价。
  - `00428ae8 call 0x456f2d` … `00428af7 idiv ebx(4)` `00428afb jne 0x42885c`
    → **rand()%4 == 0（1/4）**：遍历其他玩家（`00428b28 cmp byte ptr [eax + 0x496b7d], 0` `je`）与其持股跟进。
* `0x0042bf03(player)`（AI 回合里 `00418de6 call 0x42bf03`）：
  `0042bf14 call 0x456f2d` `0042bf1b mov ecx, 3` `0042bf23 idiv ecx` `0042bf25 test edx, edx` `0042bf27 jne 0x42c794`
  → **rand()%3 == 0**；随后 `0042bf30 cmp byte ptr [ebx + 0x496b82], 0`（玩家+0x1a≠0）、
  `0042bf3d call 0x428d01` / `0042bf42 cmp eax, 1` / `0042bf45 je 0x42c794`、
  `0042bf4b mov edx, dword ptr [ebx + 0x496b94]`（+0x2c）、`0042bf5d call 0x4521aa`、`0042bf65 cmp eax, 0xf` `jl`；
  然后遍历 `i<0xc`（12 档）的持股数组 `0x4971a0`，per-player stride `0x60`：
  `0042bf9e mov eax, dword ptr [esp + 0xe0]` `0042bfa5 shl eax, 3` `0042bfa8 add eax, edx`
  `0042bfaa cmp dword ptr [eax + 0x4971a0], 0`，成本用 `0042bfc7 fmul dword ptr [eax*4 + 0x496994]`。
* `0x0042c79f(player)`（`00418df4 call 0x42c79f`，字符串 `0x4641cc`＝「%s\n\n賣出%s%d張」→ **AI 卖股票**）：
  ```
  0042c7bc  mov ecx, dword ptr [ebx + 0x496b94]     ; +0x2c
  0042c7c9  push esi（[0x497160]）
  0042c7ca  call 0x4521aa
  0042c7d2  cmp eax, 6
  0042c7d5  jg 0x42c7f8                             ; >6 → 走随机路径
  0042c7d7  mov eax, dword ptr [ebx + 0x496b88]     ; +0x20 存款
  0042c7dd  add eax, dword ptr [ebx + 0x496b84]     ; +0x1c 現金
  0042c7e3  cmp eax, dword ptr [ebx + 0x496b8c]     ; +0x24 貸款
  0042c7e9  jge 0x42c7f8
  0042c7eb  mov dword ptr [esp + 0xd0], 1           ; 强制卖股
  0042c802  call 0x456f2d
  0042c809  mov ecx, 3
  0042c811  idiv ecx
  0042c813  test edx, edx
  0042c815  jne 0x42d0e4                            ; rand()%3 != 0 → 放弃
  ```
  即：**若 0x4521aa(...)≤6 且 (存款+現金) < 貸款 ⇒ 强制变现（无随机）；否则 rand()%3==0 才尝试卖出。**
* `0x00428d01`：被 `0x420063, 0x420102, 0x4291e2, 0x42b6b4, 0x42bf3d, 0x42c81b` 调用，返回 1 时抑制买/卖（**未决**：其内部判据未展开）。

#### 5.2 银行
* `0x00436b0a`（`00418dfe call 0x436b0a`，字符串 0x464b75「銀行資金準備\n\n不足%d元\n\n由經營者%s墊付！」、
  0x464b9e「銀行經營權易主！」、0x464baf「%s\n\n強制償還%d元\n\n銀行特別融資！」）：
  ```
  00436b1e  mov ebp, dword ptr [0x498e7c]        ; 建筑/地產数组
  00436b24  cmp ebx, dword ptr [0x498e90]        ; 数量
  00436b2c  imul esi, ebx, 0x34
  00436b31  cmp byte ptr [esi + 0x1a], 7         ; level==7 → 銀行
  00436b37  mov dl, byte ptr [esi + 0x18]        ; type
  00436b3a  test dl, dl
  00436b3e  movzx edi, dl
  00436b41  dec edi                              ; edi = 銀行所有者
  00436b5c  cmp edi, dword ptr [0x49910c]        ; 不是自己才处理
  00436b68  imul ebx, edi, 0x68
  00436b6b  mov ebx, dword ptr [ebx + 0x496b90]  ; +0x28
  ```
  → AI 银行：在银行经营者资金不足时强制偿还/特别融资。
* **存款/提款的主动 AI 决策未找到**（`0x42bf03` 的数组 `0x4971a0` 更像股票持股；银行面板本身的 UI 与 AI 存款判据**未决**）。

---

### 6. 随机数调用点清单

`0x00456f2d` = `_libc_rand`（LCG）。以下为 AI 决策路径上可达的调用点（均为本次 `call 0x456f2d` 扫描 + 上下文反汇编）。

| VA | 随机用法 | 阈值 | 作用 |
|---|---|---|---|
| 0x0041e6ce | `call 0x456f2d` → `0041e6d5 mov ecx, 3` `0041e6dd idiv ecx` | `0041e6df test edx, edx` `0041e6e1 je 0x41e6e6` ⇒ `rand()%3==0`（1/3） | **个性门控**：`edx = 門檻表[卡] − 個性(+0x17)`；`edx>=2` 直接 0；`edx==1` 时需 `rand()%3==0`；`edx<=0` 直接放行（见下方摘录）|
| 0x00418e18 | `call 0x456f2d` → `00418e1d test al, 1` `00418e1f je 0x418e28` | `rand()&1`（1/2） | AI 回合二选一：`00418e21 call 0x441baa`（用卡） vs `00418e28 call 0x447d97`（用道具）|
| 0x0042886e | `call 0x456f2d` `0042887d idiv ebx(0xf)` | `rand()%15==0`（1/15） | 股票 AI 进入「用卡/用道具」块 |
| 0x004288fb | `call 0x456f2d` `00428905 idiv dword ptr [esp + 0x10]` | `rand()%count` | 从（重复牌）清单中随机取一张 |
| 0x004289d3 | `call 0x456f2d` `004289dd idiv ebp` | `rand()%count` | 随机选一件道具（个性门控后）|
| 0x00428a37 | `call 0x456f2d` `00428a43 idiv ebx(3)` | `rand()%3==0`（1/3） | 刷新持股市价 |
| 0x00428ae8 | `call 0x456f2d` `00428af7 idiv ebx(4)` | `rand()%4==0`（1/4） | 观察其他玩家持股并跟进 |
| 0x0042bf14 | `call 0x456f2d` `0042bf23 idiv ecx(3)` | `rand()%3==0`（1/3） | 股票/融资 AI 的总闸门 |
| 0x0042c802 | `call 0x456f2d` `0042c811 idiv ecx(3)` | `rand()%3==0`（1/3） | AI 卖股票（非强制情形）|
| 0x00441d4a | `call 0x456f2d` `00441d54 idiv esi` | `rand()%count`（仅当 count>8） | 用卡：随机起点洗牌（`00441d45 cmp esi, 8` `jle 0x441d5a` 时 `esi=0`）|
| 0x00447ff5 | `call 0x456f2d` `00447fff idiv esi` | `rand()%count`（仅当 count>4） | 用道具：随机起点（`00447ff0 cmp esi, 4` `jle 0x448005` 时 `ebx=0`）|
| 0x0041a23e | `call 0x456f2d` `0041a24d idiv ecx(4)` `0041a24f inc edx` | `rand()%4 + 1` | 商业地买下后 **[land+0x18] = rand()%4+1**（类型）|
| 0x0041b1f8 | `call 0x456f2d` `0041b1fd and eax, 1` | `rand()&1` | 「得點券５０點」事件(0x463a81)里选一句台词 `[char*108 + eax*4 + 0x48084a]`，交 `0041b211 call 0x44ef41`；**非决策** |
| 0x0040ca20 | `call 0x456f2d` `0040ca25 test al, 1` | `rand()&1` | 状态机消息：`0040ca17 cmp byte ptr [eax + 0x496b9c], 0`（玩家+0x34 消失计时）→ 显示 0x4631f5「%s消失中…」|
| 0x0040ca99 | 同上 | `rand()&1` | `0040ca90 cmp byte ptr [eax + 0x496b9d], 0`（+0x35 坐牢）→ 0x46320a「%s坐牢中…」|
| 0x0040cb1b | 同上 | `rand()&1` | `0040cb09 cmp byte ptr [eax + 0x496b9e], 0`（+0x36 住院）→ 0x46321f「%s住院中…」|
| 0x0040de50 | `call 0x456f2d` `0040de5c sar edx,0x1f` `0040de5f idiv ecx(9)` `0040de61 add edx, 2` | `rand()%9 + 2` | `0040de64 mov dword ptr [0x48baf8], edx`（AI 停机/等待天数）|
| 0x00408328 | `call 0x456f2d` `0040832f sar edx,0x1f` `00408332 idiv edi` | `rand()%edi` | 从候选取一块地 → `00408340 mov word ptr [eax + 0x496b76], dx`（AI 选目标地）|
| 0x0040aa53 | `call 0x456f2d` `0040aa5a sar edx,0x1f` `0040aa5d idiv ebx` | `rand()%ebx` | 从候选列表随机取一项返回 |
| 0x004222e1 | `call 0x456f2d` `004222e6 mov dl, al` `004222e8 and dl, 1` `004222eb add dl, 2` | `rand()&1 + 2` | `004222f5 mov byte ptr [eax + 0x496b7a], dl`（玩家+0x12 状态计数器）|

**个性门控 0x0041e69e 全文（D-004 所涉原版行为）：**
```
0041e69e  mov eax, dword ptr [esp + 4]           ; 卡片 id
0041e6a2  xor edx, edx
0041e6a4  mov dl, byte ptr [eax*8 + 0x47fdf1]    ; 門檻表[卡]（基址 0x47fdea + stride 8 的 +7 字节）
0041e6ab  imul eax, dword ptr [0x49910c], 0x68
0041e6b2  mov al, byte ptr [eax + 0x496b7f]      ; 玩家 +0x17 = 個性
0041e6b8  and eax, 0xff
0041e6bd  sub edx, eax                           ; edx = 門檻 − 個性
0041e6bf  mov eax, edx
0041e6c1  cmp edx, 2
0041e6c4  jl 0x41e6c9
0041e6c6  xor eax, edx                           ; edx>=2 → 返回 0（拒绝）
0041e6c8  ret
0041e6c9  cmp edx, 1
0041e6cc  jne 0x41e6e6
0041e6ce  call 0x456f2d                          ; rand()
0041e6d5  mov ecx, 3
0041e6dd  idiv ecx
0041e6df  test edx, edx
0041e6e1  je 0x41e6e6                            ; rand()%3 == 0 → 放行
0041e6e3  xor eax, eax
0041e6e5  ret                                    ; 否则返回 0
0041e6e6  mov eax, dword ptr [esp + 4]
0041e6ea  call dword ptr [eax*4 + 0x475324]      ; 卡片专用 AI 判据表
0041e6f1  ret
0041e6f2  mov eax, dword ptr [esp + 4]           ; 另一函数（0x41e6f2）：
0041e6f6  mov eax, dword ptr [eax*4 + 0x48be58]  ; 取该卡片的 AI 参数（0x48be58 运行时填写，语义未决）
0041e6fd  ret
```
门槛表（`0x47fdf1 + id*8`，名表 `0x47fdea + id*8` 的 dword 指针，本次逐项读取）：
id1 均富卡=2、id2 均貧卡=2、id3 購地卡=1、id4 換地卡=0、id5 換屋卡=0、id6 轉向卡=0、id7 改建卡=0、
id8 拍賣卡=1、id9 天使卡=0、id10 惡魔卡=2、id11 怪獸卡=2、id12 拆除卡=1、id13 搶奪卡=2、id14 停留卡=0、
id15 冬眠卡=2、id16 夢遊卡=1、id17 陷害卡=2、id18 復仇卡=0、id19 嫁禍卡=0、id20 免費卡=0、id21 免罪卡=0、
id22 送神符=0、id23 請神符=0、id24 紅卡=0、id25 黑卡=1、id26 查稅卡=1、id27 漲價卡=0、id28 查封卡=1、
id29 同盟卡=0、id30 烏龜卡=0（id0 = 空槽）。
AI 判据跳表 `0x475324 + id*4`：id1→0x41e6fe、id2→0x41e779、id3→0x41e9e2、id4→0x41eae2、
id5/id6→0x41e6e3(返回0=永不用)、id7→0x41ed3e、id8→0x41ef26、id9→0x41f037、id10→0x41f1b3、
id11→0x41f400、id12→0x41f6a9、id13→0x41f901、id14→0x41facc、id15→0x41fe4e、id16/id17→0x41fe6f、
id18..id21→0x41e6e3、id22→0x41ff77、id23→0x41fff8、id24→0x420055、id25→0x4200ea、id26→0x4202d2、（后续 id 未逐项展开）。

道具名表 `0x47feda + id*8`（dword 名指针，本次读取）：id1 機器娃娃、id2 路障、id3 地雷、id4 定時炸彈、
id5 機車、id6 汽車、id7 飛彈、id8 遙控骰子、id9 機器工人、id10 時光機、id11 傳送機、id12 工程車、id13 核子飛彈。
槽位数组：卡片 `0x499120`（`00441d7d mov al, byte ptr [edx + eax + 0x499120]`，`eax = 15*player`），
道具 `0x49915c`（`00447fd0 cmp byte ptr [ebx + eax + 0x49915c], 0`），各 4 人 × 15 槽，
初始化 `00407186 push 0x499120` / `00407196 push 0x49915c` `0040718b call 0x456f60`（长度 0x3c=60）。

---

### 汇编摘录

路由入口与跳表分派：
```asm
00417d65  push ebx
00417d66  push 0
00417d68  call 0x402460
00417d6d  add esp, 4
00417d70  call 0x419703
00417d75  mov dword ptr [0x48bde4], 0xffffffff
00417d7f  push 1
00417d81  call 0x415d31
00417d86  add esp, 4
00417d89  mov ecx, dword ptr [esp + 8]
00417d8d  cmp ecx, 0xa
00417d90  ja 0x417dff
00417d96  mov eax, ecx
00417d98  jmp dword ptr [eax*4 + 0x417d39]
00417d9f  push 0x3c
00417da1  push 0x14
00417da3  call 0x44eb39
00417dad  push 1
00417daf  call 0x411b53
00417db6  call 0x41e345
00417dbd  push 1
00417dbf  call 0x403d74
00417dcb  call 0x404165
00417dd2  call 0x40a9bd
00417dd9  call 0x424492
00417de0  call 0x447d97
00417de7  call 0x441baa
00417dee  call 0x4284be
00417df5  push 0
00417df7  call 0x42b58f
00417dff  call 0x40defe
00417e04  cmp eax, 1
00417e07  jne 0x417e24
00417e09  cmp dword ptr [esp + 8], 3
00417e0e  jne 0x417e15
00417e10  cmp ebx, -1
00417e13  jne 0x417e24
00417e15  call 0x4196f1
00417e1a  push 1
00417e1c  call 0x402460
00417e24  pop ebx
00417e25  ret
```

指令条命中测试（控件号 = x/0x28 + 0x64）与右键/左键分派：
```asm
00418670  cmp esi, 0x1b8
00418676  jge 0x4186a7
00418678  cmp edx, 0x28
0041867b  jge 0x4186a7
0041868c  mov ebx, 0x28
00418691  mov eax, esi
00418698  idiv ebx
0041869a  add eax, 0x64
0041869d  mov byte ptr [0x48be28], al
...
004186f3  mov bl, byte ptr [0x48be28]
00418863  cmp bl, 0x64
00418866  jb 0x418878
00418868  xor eax, eax
0041886a  mov al, bl
0041886c  sub eax, 0x64
0041886f  push eax
00418870  call 0x417d65
```

AI 回合驱动（决策块 + 落点）：
```asm
00418d70  push 0
00418d70  call 0x40c912          ; AI 状态机 0..5
00418d78  cmp eax, 5
00418d7b  ja 0x418e7a
00418d81  jmp dword ptr [eax*4 + 0x418c3d]
...
00418de5  push esi
00418de6  call 0x42bf03
00418df3  push eax
00418df4  call 0x42c79f
00418dfc  push 0
00418dfe  call 0x436b0a
00418e13  call 0x4284be
00418e18  call 0x456f2d
00418e1d  test al, 1
00418e1f  je 0x418e28
00418e21  call 0x441baa
00418e28  call 0x447d97
00418e2d  mov edx, dword ptr [0x49910c]
...
00418e7f  push 1
00418e81  call 0x40c912
00418e94  mov ax, word ptr [eax + 0x496b74]
00418ea1  call 0x41982d
```

住宅买地 AI 判据调用与「拒绝」：
```asm
0041a07f  test byte ptr [eax + 0x496b7d], 6
0041a086  je 0x41a098
0041a088  push ebp
0041a089  call 0x41d7d4
0041a08e  add esp, 4
0041a091  cmp eax, 1
0041a094  jne 0x41a098
0041a096  mov edi, eax
0041a09f  cmp byte ptr [eax + 0x496b7d], 1
0041a0a6  jne 0x41a0b8
0041a0ab  call 0x440ba8
0041a0b8  test edi, edi
0041a0ba  je 0x41b077
```

住宅盖房（AI 无需判据）：
```asm
00419939  movzx ebp, word ptr [esi + 0x1e]
0041993d  imul ebp, dword ptr [0x4990e8]
0041994b  cmp ebp, dword ptr [eax + 0x496b84]
00419951  jg 0x419a52
00419976  test byte ptr [eax + 0x496b7d], 6
0041997d  jne 0x4199a7
00419986  cmp byte ptr [eax + 0x496b7d], 1
0041998d  jne 0x41b077
00419996  call 0x440ba8
004199c5  sub dword ptr [eax + 0x496b84], ebp
004199d1  inc byte ptr [esi + 0x1a]
```

AI 买地判据 0x41d7d4（见 §3.3 全文），核心四行：
```asm
0041d7da  fild dword ptr [0x49908c]
0041d7e0  fmul qword ptr [0x463cc8]          ; 0.05
0041d7ee  cmp dword ptr [esp], 0x1b58        ; 7000 上限
0041d828  cmp eax, dword ptr [esp]           ; (現金+存款-cost) vs reserve
0041d82b  jle 0x41d832
0041d82d  mov ecx, 1
```

用道具 AI（0x447d97）随机选件：
```asm
00447f87  test byte ptr [eax + 0x496b7e], 2
00447fd0  cmp byte ptr [ebx + eax + 0x49915c], 0
00447ff0  cmp esi, 4
00447ff5  call 0x456f2d
00447fff  idiv esi
00448001  mov ebx, edx
0044802c  test dh, dh
00448039  call 0x420e9a
00448041  cmp eax, 1
0044805e  call 0x457110
```

用卡 AI（0x441baa）随机洗牌 + 个性门控：
```asm
00441d09  test byte ptr [eax + 0x496b7e], 1
00441d1d  call 0x441262
00441d45  cmp esi, 8
00441d4a  call 0x456f2d
00441d54  idiv esi
00441d7d  mov al, byte ptr [edx + eax + 0x499120]
00441db2  call 0x41e69e
00441dba  cmp eax, 1
00441dda  call 0x457110
00441e00  call dword ptr [eax*4 + 0x475d5c]
```

---

### 未决

1. **跳表热键表 0x497176–0x49719e 的取值**：位于 `.bss`（原始大小 0），运行时初始化；未找到写入点，故「哪个热键对应哪个动作号」未决。动作号常量本身在 `0x401314`–`0x401457` 已确证。
2. **玩家标志字节 +0x15（0x496b7d）的位语义**：已确证的只有用法——
   `+0x15 & 6 != 0` → 走自動判据/直接执行（`0x41a07f`、`0x419976`、`0x41a8c0`、`0x41a307`）；
   `+0x15 == 1` → 弹互动确认框 `0x440ba8`；`+0x15 & 1` → 出现在託管AI面板名单（`0x41e5a6`）；
   `+0x15 & 0x30` → 跳过 AI 回合自动块（`0x418dd8`/`0x40c969`）；`+0x15 & 0x40` → 走路分支（`0x40b976`）。
   任务锚点「+0x15 = 1 表示 AI」与上述指令**不一致**：所有落点决策里 `==1` 都是「显示对话等人类确认」。
   `+0x64`（0x496bcc）由 `004072ec mov eax, dword ptr [edi + 0x48a35c]` → `004072f5 and eax, 1`
   → `004072f8 inc eax` → `004072f9 mov byte ptr [esi + 0x496bcc], al` 置为 1 或 2，
   并在 `00418d01 mov dl, byte ptr [eax + 0x496bcc]` → `00418d07 mov byte ptr [eax + 0x496b7d], dl`
   回写到 +0x15。具体位（2 / 4 / 0x30 / 0x40）的语义**未决**（推断：bit0＝託管中、bit1＝電腦、bit2＝人類的託管自動化）。
3. **玩家 +0x37（0x496b9f）与 +0x3f（0x496ba7）的语义**：买地/盖房/研究所三处都要 `+0x37==0` 且 `+0x3f != 0x0c`；写入点 `0x41c9b6/0x41cb36/0x41cb43/0x444193/0x444369`，语义未展开。推断为异常状态（如住院/坐牢/已行动）标志。
4. **个案 4（0x404165）究竟为 存檔 还是 另一个读档变体**：与 0x403d74 结构孪生且无 DGROUP 文案，未能确证。
5. **个案 5（0x40a9bd）**：对话过程序按坐标缩放画各玩家头像，推断为「缩小地图」；未能从字符串确证。
6. **银行 AI 的存款/提款决策**：除 `0x436b0a`（银行经营者垫付/特别融资）与 `0x42c79f`（为还贷强制卖股）外，未找到主动存款/提款判据，**未决**。
7. **`0x428d01`（返回 1 则抑制买/卖）内部判据未展开**；`0x48be58`（每张卡片的 AI 参数表，运行时填写）语义**未决**。
8. **`0x49908c` 的语义为推断**（开局资金设定值 `0x46cb94` 表的选中项）：其唯一写点 `0040717e` 已确证，但游戏内是否在别处按关卡改写未能完全排除（无其它写点被扫描到）。
9. **`0x4521aa(0x497160, ...)` 的返回值语义未决**（用于股票买/卖门槛 0xf 与 6）。
