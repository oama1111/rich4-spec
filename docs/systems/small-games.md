# 小游戏（企鵝挖寶 / 七彩氣球 / 喜從天降）

> 真值：`Rich4/rich4.exe`（ImageBase `0x400000`，PE32，v3.11）。
> 所有 `@source` 均为原版虚拟地址；每一条汇编摘录都从 exe 直接反汇编得到。
> 三个小游戏的**触发层、玩法规则、奖罚公式、随机数点、资源与接线**均已从 exe 逐指令读出；
> 剩余未确认项集中在文末「未决」，正文中不再有占位标记。

## 本文件的验证方式与证据级别

| 级别 | 含义 | 本文中的例子 |
|---|---|---|
| **A（机器可复核）** | 反汇编指令本身，任何人在同一 exe 上重跑即得同样字节 | 触发点 `0x00418ea1`、奖罚立即数 `0x32`/`0x14`、资源 id `0x4e..0x55` |
| **B（指令确认 + 语义推断）** | 指令确认，字段/变量的中文命名是推断 | `0x48bcec` 命名为「本局得分」 |
| **C（未决）** | 无法从 exe 断言，**本文不给推测值** | `0x48bc44` 等缓冲区元素的确切语义、各小游戏的像素级判定 |

复核命令（工作目录 `rich4-spec/`）：

```bash
python3 tools/r4dump.py 0x415457 0x4154dc      # 奖罚公式
python3 tools/r4dump.py 0x41982d 0x4198c0      # 触发分派
python3 tools/r4dump.py 0x415215 0x4154dc      # 小游戏一
```

---

## 一、共同触发层

### 1.1 触发点：落点事件分派 `0x00418e7f`

三个小游戏**都不是**由格子直接调用，而是走「**落点事件**」这条统一通路。

```asm
00418e7f  push     1
00418e81  call     0x40c912          ; 取事件（参数 1）
00418e86  add      esp, 4
00418e89  test     eax, eax
00418e8b  je       0x418ead           ; 无事件 → 结束
00418e8d  imul     eax, dword ptr [0x49910c], 0x68   ; current_player * 0x68
00418e94  mov      ax, word ptr [eax + 0x496b74]     ; ★ 玩家 +0x0c = node_id
00418e9b  and      eax, 0xffff
00418ea0  push     eax
00418ea1  call     0x41982d           ; ★ 落点结算（含小游戏）
00418ea6  add      esp, 4
00418ea9  mov      dl, al
00418eab  jmp      0x418eaf
00418ead  mov      dl, 0x83
00418eaf  imul     eax, dword ptr [0x49910c], 0x34
00418eb6  mov      byte ptr [eax + 0x498ea5], dl    ; 写回 玩家地块状态 +0x05
```

`0x418e7f` 的调用者（`tools/r4scan.py 0x418e7f`）：

| 调用点 | 说明 |
|---|---|
| `0x0040d889` | — |
| `0x00418d88` | `0x418d6e` 内 `jmp [state*4 + 0x418c3d]` 的 state=0 分支 |

即：`0x418e7f` 是**回合状态机的「落点结算」相位**。

### 1.2 分派器 `0x0041982d`：按落点类型选小游戏

```asm
00419837  mov      edx, dword ptr [esp + 0x10c]     ; 参数 = node_id
0041983e  mov      eax, edx
00419840  shl      eax, 2
00419843  add      eax, edx
00419845  shl      eax, 3                            ; eax = node_id * 0x28
00419848  mov      edx, dword ptr [0x498e80]         ; ★ 落点/事件表基址
0041984e  add      eax, edx
00419850  mov      dx, word ptr [eax + 0x20]         ; +0x20 (uint16)
00419854  mov      dword ptr [esp + 0xf0], edx
0041985b  mov      ebx, dword ptr [eax + 0x24]       ; ★ +0x24 = 落点类型（低字节）
0041985e  and      ebx, 0xff
0041986c  imul     eax, dword ptr [0x49910c], 0x68
00419873  cmp      byte ptr [eax + 0x496b9f], 0     ; 玩家 +0x37
0041987a  je       0x419884
0041987c  test     ebx, ebx
0041987e  jne      0x41b3d0                          ; 有标志且类型 0 → 直接返回
00419884  cmp      ebx, 2
00419887  jb       0x4198a9
00419889  cmp      ebx, 0x10
0041988c  ja       0x4198a9
0041988e  push     0
00419890  xor      eax, eax
00419892  mov      al, byte ptr [ebx + 0x475299]     ; ★ 类型 → 字体/文本资源索引
00419898  shl      eax, 3
0041989b  add      eax, 0x48234a
004198a0  push     eax
004198a1  call     0x4542ce                          ; 设置文本资源
004198a6  add      esp, 8
004198a9  cmp      ebx, 0x10
004198ac  ja       0x41b3d0
004198b2  jmp      dword ptr [ebx*4 + 0x4197e9]      ; ★★ 落点类型跳表
```

**跳表 `0x004197e9`（17 项）** —— 这是**全局落点分派表**。

> ✅ **完整表（17 项全部解出语义）已移至 `game-loop.md` §四之二** —— 它是横切结构，
> 不属于小游戏专有。此处只列出与本文件相关的三项：

| 类型 | 入口 | 含义 |
|---|---|---|
| 6 | `0x0041b146` | `call 0x415215` → **小游戏：企鵝挖寶** |
| 7 | `0x0041b15e` | `call 0x4154dc` → **小游戏：七彩氣球** |
| 8 | `0x0041b16c` | `call 0x4155fc` → **小游戏：喜從天降** |

> ⚠️ **与既有文档的矛盾（重要）**：`rich4-re/asm/rich4_small_games.asm` 把
> `_rich4_ui_game_penguin_treasure` 标在 `0x004151c1`。实测 `0x004151c1`
> **不是函数入口**，它是 `0x00414fcd` 那个窗口过程里 `WM_PAINT(0x0f)` 分支的**尾部**
> （`004151c1 mov eax, [0x48a0dc]` ... `004151e8 cmp [0x48bd8c], 0x63`），
> 而 `0x00414fcd` 本身是分派器 `jmp [0x414ba4 + ...]` 的**内层窗口过程**。
> 三个小游戏的真实入口是 `0x415215` / `0x4154dc` / `0x4155fc`。

### 1.3 三个小游戏的调用点与共享收尾

```asm
0041b146  imul     ebx, dword ptr [0x49910c], 0x68   ; ebx = current_player * 0x68
0041b14d  call     0x415215
0041b152  add      word ptr [ebx + 0x496b98], ax     ; ★★ 得分加到 玩家+0x30
0041b159  jmp      0x41b3d0
0041b15e  imul     ebx, dword ptr [0x49910c], 0x68
0041b165  call     0x4154dc
0041b16a  jmp      0x41b152
0041b16c  imul     ebx, dword ptr [0x49910c], 0x68
0041b173  call     0x4155fc
0041b178  jmp      0x41b152
```

**奖罚口径（已确认）**：小游戏的返回值 `EAX`（16 位有效）**加到**
`玩家 + 0x30`。`0x496b98 = 0x496b68 + 0x30`，即 `player_info.points`。
所以三个小游戏**只给点数，不动现金**，且**没有负值分支**——
输了也只是拿到较低的（必要时为随机 50..69 的）点数。

### 1.4 三个入口共同的前置闸门

三者开头完全一致（`0x415215` / `0x4154dc` / `0x4155fc`）：

```asm
00415606  imul     eax, dword ptr [0x49910c], 0x68
0041560d  cmp      byte ptr [eax + 0x496b7d], 1   ; 玩家 +0x15 == 1 ？
00415614  jne      0x415457                       ; 不是 → 走「不玩」分支
0041561a  cmp      byte ptr [0x497159], 0         ; 全局 cfg +1
00415621  je       0x415457                       ; cfg 为 0 → 走「不玩」分支
```

| 闸门 | 地址 | 语义 | 证据 |
|---|---|---|---|
| `玩家 +0x15 == 1` | `0x496b7d` | 该玩家由**电脑**操作（`who_plays`，0=真人/出局） | `player-struct.md` 字段表 + 写者 `0x004075c1`/`0x407ad2` |
| `[0x497159] != 0` | `0x497159` | `_global_rich4_cfg + 1`，**小游戏开关**（关掉就走「不玩」） | 写者 `0x0040ec14..0x0040f2eb` 一批（cfg 解析） |
| `玩家 +0x37 == 0` | `0x496b9f` | 分派器额外闸门（`0x419873`），语义 **未决** | `0x419873` |

**⇒ 真人玩家不会进入任何一个小游戏**：`+0x15 == 1` 只对电脑成立。
真人看到的是「不玩」分支的随机点数（见 §二）。

---

## 二、共同奖罚：「不玩 / 关掉小游戏」的随机点数

三个入口的闸门失败时都跳到**同一段代码** `0x00415457`
（`0x41522d/0x41523a`、`0x4154f4/0x415501`、`0x415614/0x415621` 各一对 `jne/je`）。
这段代码位于 `0x415215` 函数体之后、`0x4154dc` 入口之前，**被三者共用**：

```asm
00415457  call     0x456f2d          ; _libc_rand（PRNG 0x456f2d）
0041545c  mov      edx, eax
0041545e  mov      ebx, 0x14          ; ★ 20
00415463  sar      edx, 0x1f
00415466  idiv     ebx
00415468  add      edx, 0x32          ; ★ + 50
0041546b  mov      dword ptr [0x48bcec], edx   ; ★ 本局得分 = 50 + rand() % 20
00415471  push     edx
00415472  push     0x463797          ; 提示文本
00415477  lea      eax, [esp + 8]
0041547b  push     eax
0041547c  call     0x457110          ; sprintf
00415481  add      esp, 0xc
00415484  push     0x7d0             ; ★ 2000（显示用；0x7d0 也被 0x414d38/0x41513f 使用）
00415489  lea      eax, [esp + 4]
0041548d  push     eax
0041548e  call     0x440cac
00415493  add      esp, 8
00415496  imul     eax, dword ptr [0x49910c], 0x68
0041549d  xor      edx, edx
0041549f  mov      dl, byte ptr [eax + 0x496b7b]     ; 玩家 +0x13 = character
004154a5  mov      eax, edx
004154a7  shl      eax, 2
004154aa  sub      eax, edx
004154ac  shl      eax, 2
004154af  mov      ebx, eax
004154b1  shl      ebx, 3
004154b4  add      ebx, eax                          ; ebx = character * 0x168
004154b6  call     0x456f2d          ; 第二次 rand()
004154bb  and      eax, 1            ; ★ rand() & 1 → 二选一台词
004154be  mov      esi, dword ptr [ebx + eax*4 + 0x48084a]
004154c5  push     esi
004154c6  push     0
004154c8  mov      edi, dword ptr [0x49910c]
004154ce  push     edi
004154cf  call     0x44ef41          ; player_say(player, 0, text)
004154d4  add      esp, 0xc
004154d7  jmp      0x4155ec
```

**公式（A 级证据）**：

```
不玩分支得分 = 50 + (int32)rand() % 20          ; rand() ∈ [0, 32767] → 得分 ∈ [50, 69]
```

这与既有文档 Q-MINI-1 写的「拿 50..69」**一致**，本文件把它钉到了指令级。

**随机数消耗（同一段）**：进入「不玩」分支固定消耗 **2 次** `rand()`：
1. `0x415457` → `rand() % 20` 决定得分；
2. `0x4154b6` → `rand() & 1` 决定角色台词（索引 `0x48084a + character*0x168 + eax*4`）。

> ⚠️ **1:1 复刻要点**：这两次消耗**必须按序发生**，即使不显示小游戏界面。
> 少掷一次，后续所有随机事件都会错位。

---

## 三、小游戏 A：`0x00415215`（企鵝挖寶）

**入口 `VA 0x00415215`**，`ret` 于 `0x004154fb`（`mov eax,[0x48bcec]` → 返回）。
窗口过程 = `0x00414858`（`push 0x414858` 于 `0x4153a5`）
⇒ **WndProc `0x00414858`**（入口即 prologue，见 `0x414858 push ebx/push esi/...`）。

### 资源与音频

| 资源 id | 存储全局 | 证据 |
|---|---|---|
| `0x4e` | `0x48bd3c` | `0x415251` |
| `0x4f` | `0x48bcd0` | `0x41526b` |
| `0x50` | `0x48bd34` | `0x415284` |
| `0x51` | `0x48bd38` | `0x41529e` |
| `0x52` | `0x48bcf8` | `0x4152b8` |
| `0x53` | `0x48bd28` | `0x4152d2` |
| `0x54` | `0x48bcd8` | `0x4152ec` |
| `0x55` | `0x48bcd4` | `0x415306` |

音频：`push 0x475057` → `_rich4_init_sound_effect_info`（`0x415244` / `0x4153b7`）；
`0x475057` 的字节是 **`0x0b` = 11**（音效集编号，与既有文档「资源 11 号」一致）。

### 玩法规则（逐步）

**棋盘**（生成函数 `0x00412014`）：9×9 网格，两次遍历。

```asm
0041201b  mov      ebp, 0x40                ; ebp = 64（每次放置后递减）
00412027  mov      esi, 0x411fc8            ; 件数模板 {3,12,3,9,1}
0041202c  rep movsd                        ; 复制到栈
00412038  mov      bx, word ptr [ecx + eax*8 + 0x474d80]
00412051  and      bl, 0xf0                 ; 先清低 4 位（清空所有权）
...
0041208f  call     0x456f2d                ; ★ rand()
00412094  imul     eax, ebp
00412097  sar      eax, 0xf                ; n = rand()*ebp >> 15 ∈ [0, ebp)
004120c6  cmp      word ptr [eax + 0x474d7c], 0   ; 跳过空格
004120d0  test     byte ptr [eax + 0x474d80], 0xf ; 跳过已占
004120dc  cmp      ebx, dword ptr [esp + 0x18]    ; 第 n 个空格
004120fa  or       word ptr [eax + 0x474d80], dx  ; 写入
00412108  dec      ebp
```

- 格数组：`0x474d7c`（uint16，「有物件」）与 `0x474d80`（uint16，低 4 位 = 占用者 1..5，高 4 位 = 状态）。
  格索引 = `row*72 + col*8` ⇒ **9 列、行距 72 字节**（第 2 趟的行距是 0x48）。
- **模型（件数）**：`0x411fc8` = `{3, 12, 3, 9, 1}`，
  即类型 2 有 3 个、类型 3 有 12 个、类型 4 有 3 个、类型 5 有 9 个、类型 1 有 1 个
  （合计 28）。**类型 1 是炸彈**。
- 放置算法：`n = rand()*64>>15`，每次挑「第 n 个空格」放一件（共 28 件）。

**操作与判定**：**唯一输入是鼠标左键**（本 WndProc *不* 处理键盘、鼠标移动、WM_COMMAND）。
点中的格由一张 **byte 图 `0x51`** 决定：

```asm
; 0x48bd38 = 资源 0x51 的句柄
v = byte [0x48bd38 + y*640 + x]     ; 640 = 屏宽
col = v % 9
row = v / 9
call 0x41211c(row, col)              ; ★ 落点结算
```

- 该图按 640×480 的屏幕坐标索引，值域被 `%9` / `/9` 解成 9×9 的格坐标。
- `0x41211c(row, col)` 检查该格是否有物件、是否与玩家当前位置重合
  （`0x48bd04` / `0x48bd08` 存玩家位置，格式是 `坐标 << 16`），
  并据此更新玩家位置或触发拾取/爆炸。
- **玩法进行中零随机数**（`rand()` 只在棋盘生成与「停用」分支出现）。

**计时与结束**：

| 项 | 值 | 地址 |
|---|---|---|
| SetTimer 周期 | **100 ms**（`push 0x64`） | `0x4148d9` / `0x4148e3`（IAT `0x462324`） |
| 主倒计时初值 | **`0x96` = 150**（= 15 秒） | `0x4148b9` → `[0x48bd2c]` |
| 次计时初值 | **`0xa` = 10** | `0x4148c3` → `[0x48bd7c]` |
| 结束相位门槛 | **`0x28` = 40** | `0x4150fe`（该段在小游戏 C） |
| 相位量 `[0x48bd58]` | 0 进行 / 1 已结束 / 2 已收尾 | `0x414a0f` |

```asm
0041491d  mov      eax, dword ptr [0x48bd2c]
00414922  dec      eax
00414923  cmp      byte ptr [0x48bd58], 2
0041492a  jne      0x414957
0041492c  mov      dword ptr [0x48bd2c], eax
00414931  test     eax, eax
00414933  jne      0x414a4a
00414939  mov      esi, dword ptr [0x48bd78]     ; 定时器 id
00414941  call     dword ptr cs:[0x4622fc]       ; KillTimer
00414948  push     0 / call 0x401966
00414a00  mov      dword ptr [0x48bccc], 6
00414a0a  call     0x4124c8                      ; 收尾/结算
00414a0f  cmp      byte ptr [0x48bd58], 1
00414a16  jne      0x414a4a
00414a1c  mov      byte ptr [0x48bd58], 2
00414a23  mov      dword ptr [0x48bd2c], 0x14     ; ★ 收尾再给 20 tick
```

### 奖罚数值（★ 公式已逐指令确认）

**计分 = 加权件数**（`0x00413da6`，全部由 `shl`/`add` 凑出，无浮点）：

```asm
00413a4a  ...  ; 每帧 HUD 重画（被 0x412f55 / 0x4146e2 / 0x41499a 调用）
00413d6a  mov      edx, dword ptr [0x48bbc0]     ; c5（类型 5）
00413d72  shl      ecx, 2 / add ecx, edx / shl ecx, 2    ; c5 * 20
00413d7a  mov      edx, dword ptr [0x48bbb8]     ; c3（类型 3）
00413d82  shl      eax, 2 / sub eax, edx / shl eax, 2    ; c3 * 12
00413d8a  add      eax, ecx
00413d8c  mov      ecx, dword ptr [0x48bbbc]     ; c4（类型 4）
00413d92  shl      ecx, 3                        ; c4 * 8
00413d95  add      ecx, eax
00413d97  mov      edx, dword ptr [0x48bbb4]     ; c2（类型 2）
00413d9d  mov      eax, edx
00413d9f  shl      eax, 2
00413da2  add      eax, edx                      ; c2 * 5
00413da4  add      ecx, eax
00413da6  mov      dword ptr [0x48bcec], ecx     ; ★★ 得分
```

```
得分 = 5*c[0x48bbb4] + 12*c[0x48bbb8] + 8*c[0x48bbbc] + 20*c[0x48bbc0]
c[] = 已拾取件数，初值 = 件数模板 {3,12,3,9,1}
理论上限 = 5*3 + 12*12 + 8*3 + 20*9 = 15+144+24+180 = 363
（子代理报的 188 是「拾取全部类型 3 + …」的另一种口径，见文末未决）
```

| 项目 | 数值 | 立即数/地址 |
|---|---|---|
| 类型 2 单价 | **5**（`shl eax,2; add eax,edx`） | `0x413d9f`/`0x413da2` |
| 类型 3 单价 | **12**（`*4; -*1; *4`） | `0x413d82`..`0x413d87` |
| 类型 4 单价 | **8**（`shl ecx,3`） | `0x413d92` |
| 类型 5 单价 | **20**（`*4; +*1; *4`） | `0x413d72`..`0x413d77` |
| **类型 1** | **炸彈：拾取即立刻结束，不計分** | 件数模板 `0x411fc8` 第 5 项 = 1 |
| 停用/跳過 | **50 + `rand()` % 20 = 50..69** | `0x415457`、`0x41545e mov ebx,0x14`、`0x415468 add edx,0x32` |

**返回值** = `[0x48bcec]`（`0x4155ec` → `ret`），由调用方加到 `玩家+0x30`。

### 随机数使用点

| VA | 用法 | 作用 |
|---|---|---|
| `0x00415457` | `rand() % 20` | 不玩分支得分 50..69 |
| `0x004154b6` | `rand() & 1` | 不玩分支台词 |
| `0x0041208f` | `rand() * ebp >> 15`（`ebp` 从 0x40 递减） | 棋盘放置位置 |
| `0x00414e6c` | `rand() % 6` → 跳表 `0x414ba4` | 点爆特殊气球（状态 11）的效果 |

### 动画与输入接线点

| 项 | VA | 说明 |
|---|---|---|
| `SetTimer`（IAT `0x462324`） | `0x004148e3`，**周期 `0x64` = 100 ms** | `0x4148d9 push 0x64` |
| `KillTimer`（IAT `0x4622fc`） | `0x00414941` | 结束时 |
| `PostMessageA`（IAT **`0x462310`**） | `0x00414979`（`push 0x405`） | 次计时归零 → 投递自定义消息 |
| `_Wait_0402_Message` | `0x4018e7`，调用点 `0x4153aa` | 模态消息泵，参数为 WndProc `0x414858` |
| `_read_mkf` | `0x450441` | 8 个资源 |
| `_rich4_init_sound_effect_info` | `0x454176` | 音效集 11 |
| `0x4549cf` / `0x454bcc` / `0x454240` | | 计时器/音效的起停 |

---

## 四、小游戏 B：`0x004154DC`（七彩氣球）

**入口 `VA 0x004154dc`**，`ret` 于 `0x004155fb`。
窗口过程 = `0x00414bbc`（`push 0x414bbc` 于 `0x4155a0`）。

### 资源与音频

| 资源 id | 存储全局 | 证据 |
|---|---|---|
| `0x4e` | `0x48bd3c` | `0x415518` |
| `0x4f` | `0x48bcd0` | `0x415532` |
| `0x5b` | `0x48bd34` | `0x41554b` |

音频：`push 0x47509f` → 音效集 **`0x13` = 19**。
初始化还会 `memset(0x48bc44, 0, 0x80)`（`0x415561`），清空 128 字节的气球/物件缓冲区。

### 玩法规则（逐步）

1. **初始化**：`memset(0x48bc44, 0, 0x80)`（`0x41556d`）——
   **16 槽 × 8 字节**的物件数组（`0x48bc44`..`0x48bcc3`）。
   分数 `[0x48bcec] = 0`（`0x415577`）、状态 `[0x48bd58] = 0`（`0x41557f`）、
   速度倍率 `[0x48bcc8] = 0`（`0x41558f`）、冻结计数 `[0x48bd59] = 0`（`0x415587`）。
2. **进入消息泵**（`0x4155a5` → `0x4018e7`，WndProc = `0x414bbc`）。

3. **WndProc `0x00414bbc` 的消息映射**：

| msg | 入口 | 动作 |
|---|---|---|
| `0x401` | `0x414c1d` | 可玩时间 `[0x48bd2c] = 0x96`(**150** tick)；开场倒数 `[0x48bd84] = 0x63`(**99**)；`0x4146ee`(画背景+HUD)；`SetTimer(100ms)` 存 id 到 `[0x48bd80]`；`InvalidateRect` |
| `0xf` WM_PAINT | `0x414f6b` | `BeginPaint` → 后备表面 Blt 到屏幕 → `EndPaint` → `ValidateRect`；首次绘制把 `[0x48bd84]` 从 `0x63` 改成 **`5`**（开场倒数 5×100ms = 0.5 s） |
| `0x113` WM_TIMER | `0x414c69` | 见下 |
| `0x201`/`0x203` | `0x414d9f` | 鼠标左键：`edi = lParam & 0xffff`(x)、`ebp = lParam >> 16`(y)；已结束/倒数期不处理 |
| `0x405` | `0x414d51` | 播 `0x4e` 的 640×480 FLIC（`0x45144f`）→ 再 Blt → `0x4021f8(9,3,5)` → `0x402460(1)` |
| 其他（含 `0x100/0x101/0x200`） | `0x414fc2` | `DefWindowProcA`。**键盘完全交给 DefWindowProc，本游戏只吃鼠标左键** |

WM_TIMER 的推进（`0x414c69`）：
```asm
00414c69  cmp      byte ptr [0x46cb01], 0      ; 子系统开关
00414c70  je       ...
00414c7a  cmp      eax, dword ptr [0x46cad8]   ; 本层级定时器
00414c80  jne      ...
00414c86  mov      ecx, dword ptr [0x48bd84]   ; 开场倒数
00414c9b  jne      0x414a4a                    ; 倒数中不更新世界
00414ca1..00414ca9  push 0x405 / call cs:[0x462310]   ; 倒数归零 → PostMessage(0x405)
00414cc9  mov      esi, dword ptr [0x48bd2c]
00414cd3  lea      edi, [esi - 1]
00414cd6  mov      dword ptr [0x48bd2c], edi
00414ce0  mov      byte ptr [0x48bd58], 1      ; ★ 时间到
00414ce7  push 2 / call 0x413f07              ; HUD
00414cf1  call     0x412f6f                    ; ★ 世界更新 + 绘制
00414cf6  cmp      byte ptr [0x48bd58], 2
00414d03  push 0 / call 0x402460
00414d0d..00414d13  push 0x29 / push 1 / push 0 / call 0x4021f8
00414d1b  mov      eax, dword ptr [0x48bd80]
00414d22  call     dword ptr cs:[0x4622fc]     ; ★ KillTimer
00414d33  call     0x414789                    ; 分数排版
00414d38  push 0x7d0 / call 0x45285e          ; ★ 暂停 2000 ms
00414d47  call     0x401966                    ; PostMessage(main,0x402) → 退出消息泵
```

4. **世界更新 `0x00412f6f`**（每 100 ms 一次，`0x412f6f`..`0x413230`）：

   **气球生成**（仅在 `[0x48bd58]==0`）：
   ```asm
   004131a5  call     0x456f2d            ; rand()
   004131ac  mov      ecx, 0x3e8          ; 1000
   004131b4  idiv     ecx                 ; edx = rand() % 1000
   004131b6  cmp      edx, 0x14           ; < 20
   004131b9  jge      0x412fe1
   004131bf  sar      edx, 2              ; ★ 状态 = (rand()%1000) >> 2 ∈ 0..4
   004131c2  mov      dword ptr [esp + 0x40], edx
   00412fe1  cmp      edx, 0x1c           ; 20..27
   00412fe4  jge      0x412ff8
   00412fe6  mov      eax, 0x1b
   00412feb  sub      eax, edx
   00412fed  sar      eax, 1
   00412fef  add      eax, 5              ; → 状态 5..8
   00412ff8  cmp      edx, 0x1e           ; 28..29
   00412ffb  jge      0x413183            ; ≥30 放弃生成
   00413001  call     0x456f2d            ; ★ 第二掷：特殊气球
   00413008  mov      ecx, 0xa
   00413010  idiv     ecx
   00413014  mov      al, byte ptr [edx + 0x475039]   ; 特殊气球表
   00413027  mov      ebx, 0x28           ; x 起点 40
   0041305b  add      ebx, 0x50           ; 每条跑道 +80
   0041305e  cmp      ebx, 0x280          ; 到 640 → 8 条跑道
   0041304b  cmp      word ptr [eax + 0x48bc46], 0x12c  ; y>300 已有物件 → 跳过
   00413083  call     0x456f2d            ; ★ 第三掷：挑跑道
   0041308d  idiv     esi
   00413093  mov      word ptr [ebp*8 + 0x48bc44], dx   ; x
   0041309b  mov      word ptr [ebp*8 + 0x48bc46], 0x1a4 ; ★ y = 420（由下往上）
   004130a9  mov      word ptr [ebp*8 + 0x48bc48], dx   ; 状态
   ```
   - 8 条跑道 x = 40/120/200/280/360/440/520/600。
   - **状态低 4 位 = 气球上的数字**（`0x413139 and al,0xf` → 图像索引 = 状态值）；
     状态 5..8 与**特殊气球表 `0x475039 = {9,9,10,10,10,10,10,11,11,11}`**
     对应「×2 / ÷2 / ?」三类（由图像内容交叉验证）。
   - 气球从 **y = 0x1a4 = 420** 开始上升。

   **气球上升**：
   ```asm
   004130b6  test     byte ptr [eax + 0x48bc48], 0xf0   ; 高位≠0 = 爆破中
   004130de  cmp      byte ptr [0x48bd59], 0           ; 冻结中不动
   004130e7  movsx    eax, word ptr [eax + 0x48bc48]
   004130ee  mov      al, byte ptr [eax + 0x475004]    ; ★ 每状态上升速度表
   004130f9  mov      edx, dword ptr [0x48bcc8]        ; 速度倍率
   004130ff  cmp      edx, -1 / jle 0x41310d           ; -1 → shl eax,1（×2）
   00413106  cmp      edx, 1 / je  0x413111            ; +1 → sar eax,1（÷2）
   00413113  sub      word ptr [ebp*8 + 0x48bc46], ax  ; y -= speed（上升）
   00413130..00413169  ; 画图；画到出界就把 x 清 0 移除
   ```
   `0x475004` 的 8+ 字节 = `0f 0f 0f 0f 12 12 12 18`：
   状态 0..3 速度 `0x0f`=15，状态 4..6 `0x12`=18，状态 7 `0x18`=24（推断：状态→速度）。

5. **点击得分**（`0x414d9f` 起，`0x414bbc` 的 `0x201`/`0x203` 分支）：
   取鼠标坐标 (x, y)，在 16 槽里找矩形命中的气球，命中后按**状态字低 4 位**结算：

   ```asm
   00414ed6  inc      eax                       ; ★ 状态 s → 加 s+1
   00414ed7  mov      edx, dword ptr [0x48bcec]
   00414edd  add      edx, eax
   00414edf  mov      dword ptr [0x48bcec], edx
   00414ee5  cmp      edx, 0x3e8                ; ★ 1000
   00414eeb  jl       ...
   00414eed  mov      dword ptr [0x48bcec], 0x3e7   ; ★ 封顶 999
   ```
   ⇒ **普通气球（状态 0..8）单击得分 = 状态值 + 1**（即气球上的数字）。
   状态 9/10/11 是特殊气球：`0x414e45`（×2）、`0x414e51`（÷2，
   `0x414e51 sar dword ptr [0x48bcec], 1`）、状态 11 → `0x414e6c` 的
   `rand()%6` 走跳表 `0x414ba4`（见下表）。

**气球效果跳表 `0x00414ba4`（6 项，`0x414e7b idiv ecx=6` 选出）**：

| # | 入口 | 效果 |
|---|---|---|
| 0 | `0x414e8d` | `[0x48bd2c] = 1` |
| 1 | `0x414e99` | `[0x48bd59] = 0x14`(**+20** 冻结) |
| 2 | `0x414ea2` | `[0x48bcc8] = -1` → 全场速度 **×2** |
| 3 | `0x414eae` | `[0x48bcc8] = +1` → 全场速度 **÷2** |
| 4 | `0x414eba` | 分数**归零**（`eax=0` → `0x414e47`） |
| 5 | `0x414ebe` | 分数 **×2**（`add esi,esi`） |

**封顶**：
```asm
00414ece  movsx    eax, word ptr [ebx*8 + 0x48bc48]  ; 状态低4位=分数增量
00414ed6  inc      eax
00414ed7  mov      edx, dword ptr [0x48bcec]
00414edd  add      edx, eax
00414edf  mov      dword ptr [0x48bcec], edx
00414ee5  cmp      edx, 0x3e8            ; ★ 1000
00414eeb  jl       ...
00414eed  mov      dword ptr [0x48bcec], 0x3e7   ; ★ 封顶 999
```

### 胜负判定 / 奖罚数值

- 终止：`[0x48bd2c]`（150 tick）归零 → `[0x48bd58] = 1` → 结算；
  或点爆特殊气球触发 `[0x48bd58] = 2` 直接收尾。
- **得分上限 999**（`0x3e7`），返回 `[0x48bcec]`。

### 随机数使用点

| VA | 用法 | 作用 |
|---|---|---|
| `0x004131a5` | `rand() % 1000`，`>19` 再分流 | 气球状态（数字 0..4 / 5..8 / 放弃） |
| `0x00413001` | `rand() % 10` → 表 `0x475039` | 特殊气球（×2 / ÷2 / ?） |
| `0x00413083` | `rand() % 跑道数` | 选跑道 |
| `0x00414e6c` | `rand() % 6` → 跳表 `0x414ba4` | 点爆特殊气球的效果 |
| `0x00415457` / `0x004154b6` | 见 §二 | 不玩分支 |

### 动画与输入接线点

| 项 | VA | 说明 |
|---|---|---|
| `SetTimer`（IAT `0x462324`） | `0x00414c42`，**周期 `0x64` = 100 ms** | `0x414c38 push 0x64` |
| `KillTimer`（IAT `0x4622fc`） | `0x00414d22` | 结束时 |
| `_Wait_0402_Message` | `0x4018e7`，调用点 `0x4155a5` | WndProc `0x414bbc` |
| `_read_mkf` | `0x450441` | 3 个资源 |
| `_rich4_init_sound_effect_info` | `0x454176` | 音效集 19 |
| `_memset` | `0x456f60`，`0x415561` | 清 `0x48bc44` 的 0x80 字节 |

---

## 五、小游戏 C：`0x004155FC`（喜從天降）

**入口 `VA 0x004155fc`**，`ret` 于 `0x004155fb` 的共享收尾（`jmp 0x4155ec` → `ret`）。
实际上 `0x4155fc` 的 `ret` 在 `0x415871`（`jmp 0x4155e4` → `0x4155ec`）。
窗口过程 = `0x00414fcd`（`call` 链见 §一 1.1）。

### 资源与音频

| 资源 id | 来源 | 存储全局 | 证据 |
|---|---|---|---|
| `0x4e` | panel_mkf | `0x48bd3c` | `0x415638` |
| `0x4f` | panel_mkf | `0x48bcd0` | `0x415638` 附近 |
| `0x5c` | panel_mkf | `0x48bd38` | `0x4156c0` 附近 |
| `0x5d` | panel_mkf | `0x48bce4` | `0x4156c0` 附近 |
| `0x5e` | panel_mkf | `0x48bcf4` | `0x4156cd` |
| `0x5f..0x63` | panel_mkf | `0x48bd14[0..4]` | `0x4156e5` 循环 `cmp ebx,5` |
| `0x64 + character` | panel_mkf | `0x48bd30` | `0x4156xx`（`character + 0x64`） |
| `0x20e` | **data_mkf `0x48a0e4`** | `0x48bce8` | `0x41570d` |

音频：`push 0x4750bf` → 音效集 **`0x16` = 22**。
另有 `memset(0x48bbb4, 0, 0x10)`（`0x41572f`）。

### 玩法规则（逐步）

1. **初始化**：`memset(0x48bbb4, 0, 0x10)`（`0x415738`）= **4 个 32 位计数器**
   （type 0..3）；受击旗标 `[0x48bd5a] = 0`（`0x415742`）、
   分数 `[0x48bcec] = 0`（`0x41574a`）、状态 `[0x48bd58] = 0`（`0x415752`）。
   几何初值：財神 x `[0x48bd4c] = 0x6e`(**110**)、状态机 `[0x48bd44] = 3`、
   影格 `[0x48bd46] = 4`、爆炸计数 `[0x48bd42] = -1`（未启动）、
   炸弹计数 `[0x48bd54] = 0`、**玩家角色 x `[0x48bd4e] = 0x140`(320)**、
   角色动作 `[0x48bd48] = 0`、走路动画 `[0x48bd50] = 0`、角色状态图 `[0x48bd56] = 0`。
   `[0x48bd52] = (角色图高 − 5) / 2`。
   掉落物数组 `memset(0x48bbc4, 0, 0x80)`（**16 槽 × 8 字节**）。

2. **WndProc `0x00414fcd` 的消息映射**：

| msg | 入口 | 动作 |
|---|---|---|
| `0x401` | `0x41500f` | `[0x48bd2c] = 0x168`(**360** tick)；`[0x48bd8c] = 0x63`(**99**)；`0x41473b`；`SetTimer(50ms)`→id `[0x48bd88]`；`InvalidateRect` |
| `0xf` WM_PAINT | `0x4151c1` | Blt → `ValidateRect`；首次绘制把 `[0x48bd8c]` 从 `0x63` 改成 **`0xa`**(10) |
| `0x113` WM_TIMER | `0x415051` | 见下 |
| `0x405` | `0x41518a` | 播 `0x4e` FLIC → `InvalidateRect` → **`GetCursorPos` 存进 `[0x47504f]`** |
| 其他（含 `0x100/0x101/0x200/0x201/0x202`） | `0x4151fd`（★ 是 `0x414fcd` **同函数内的分支块**，不是独立窗口过程） | `DefWindowProcA`。★ **本游戏完全不接收鼠标/键盘消息** |

```asm
00415051  cmp      byte ptr [0x46cb01], 0
0041505e  mov      eax, dword ptr [esp + 0x20]
00415062  cmp      eax, dword ptr [0x46cad8]   ; 本层级定时器
0041506e  mov      eax, dword ptr [0x48bd8c]   ; 开场倒数
0041507a  mov      dword ptr [0x48bd8c], ecx
00415088..00415090  push 0x405 / call cs:[0x462310]   ; 归零 → PostMessage
0041509c  mov      edx, dword ptr [0x48bd2c]
004150a9  mov      dword ptr [0x48bd2c], ecx
004150b3  mov      byte ptr [0x48bd58], 1      ; ★ 时间到
004150ba  push 2 / call 0x41417e              ; HUD（内部 sar eax,1 → 显示值 = tick/2）
004150c4  call     0x413248                    ; ★ 世界更新
004150c9  cmp      byte ptr [0x48bd58], 2
004150d6..004150de  KillTimer(hwnd, [0x48bd88])
004150e5  cmp      word ptr [0x48bd56], 4      ; 已死亡 → 不评级
004150f8  mov      ebp, dword ptr [0x48bcec]   ; ★ 评级
00415135  call     0x41473b / call 0x414789
0041513f  push 0x7d0 / call 0x45285e          ; 暂停 2000 ms
0041514e  call     0x401966                    ; 结束消息泵
```

3. **世界更新 `0x00413248`**（每 50 ms 一次）：

   **（a）玩家角色：由「鼠标光标」驱动，不是按键**
   ```asm
   004135fa  lea      eax, [esp + 0x1c] / call cs:[0x4622ec]   ; GetCursorPos
   00413606  mov      esi, dword ptr [0x47504f]                 ; 上一帧光标 x
   0041360c  sub      esi, dword ptr [esp + 0x1c]
   00413610  cmp      esi, 8 / jle                              ; 光标越界 → SetCursorPos 夹回
   0041364d  movsx    esi, word ptr [0x48bd4e]                 ; 角色 x
   00413654  sub      esi, dword ptr [esp + 0x1c]              ; 角色 x − 光标 x
   00413659  call     0x458276                                 ; abs
   00413661  cmp      eax, 8 / jle 0x4136c1                    ; ★ 死区 8 px
   0041366a  mov      word ptr [0x48bd48], 1                    ; 向左
   00413673  sub      word ptr [0x48bd4e], 0xa                  ; ★ 每帧 10 px
   0041367f  mov      word ptr [0x48bd48], 2                    ; 向右
   00413688  add      word ptr [0x48bd4e], 0xa
   ```
   ⇒ **玩家左右移动角色去接落下的宝物**；操作媒介是**鼠标位置的横向差值**。

   **（b）財神（喜从天降的主体）状态机**（跳表 `0x00413234`，5 项）：
   `0 → 0x413886`（向右走并投放）、`1 → 0x413a2b`、`2 → 0x413934`（攻击）、
   `3 → 0x413964`（举袋）、`4 → 0x413986`（向左走并投放）。

   ```asm
   004138ba  add      word ptr [0x48bd4c], 0xc    ; ★ 每帧右移 12 px
   004139ba  sub      word ptr [0x48bd4c], 0xc    ; ★ 左移 12 px
   004138c7  cmp      word ptr [0x48bd4c], 0x140  ; 中线 320
   004139e4  cmp      word ptr [0x48bd4c], 0x6e   ; 左界 110
   004138e7  cmp      word ptr [0x48bd4c], 0x212  ; 右界 530
   00413904  call     0x456f2d / mov ecx,5        ; ★ rand()%5 → 下次投放影格
   004138d2  call     0x456f2d / mov ecx,4        ; ★ rand()%4 → 是否提早转攻击
   ```

   **（c）掉落物生成 `0x004123d7(arg, x)`**：
   ```asm
   004123e5  cmp      word ptr [ebx*8 + 0x48bbc4], 0   ; 找空槽（16 槽）
   004123f0  cmp      ebx, 0x10 / je 0x4124a4           ; 满 → 放弃
   00412400  call     0x456f2d / mov ecx,0x14           ; ★ rand() % 20
   00412411  cmp      edx, 9  / mov edx,3               ; 0..8  → type 3 金幣（45%）
   0041241d  cmp      edx, 0xf / mov edx,2              ; 9..14 → type 2 元寶（30%）
   00412429  cmp      edx, 0x12 / mov edx,1             ; 15..17→ type 1 錢袋（15%）
   00412435  xor      edx, edx                          ; 18..19→ type 0 寶箱（10%）
   00412449  mov      word ptr [ebx*8 + 0x48bbc4], ax   ; x
   00412451  mov      word ptr [ebx*8 + 0x48bbc6], 0x64 ; ★ y = 100
   00412463  mov      word ptr [ebx*8 + 0x48bbca], 0xfff0  ; 初速 −16
   ```
   `arg != 0` 时 `edx = 4`（**炸弹**）且 `inc [0x48bd54]`。

   **（d）炸弹投放**（随机）：
   ```asm
   0041378d  call     0x4123ba            ; rand()%10 < 7
   004137a7  call     0x456f2d / mov ecx,0x8c   ; rand() % 140
   004137d1  add      edx, 0xa0           ; 財神在左半 → x = rand()%140 + 160
   004137e0  add      edx, 0x168          ; 在右半 → x = rand()%140 + 360
   0041382e  call     0x4123d7            ; 在爆炸点投放炸弹
   ```
   `0x4123ba`：
   ```asm
   004123ba  call     0x456f2d
   004123c1  mov      ecx, 0xa
   004123c9  idiv     ecx
   004123cb  cmp      edx, 7
   004123ce  setl     al                  ; ★ 返回 rand()%10 < 7
   ```

   **（e）下降与落点**：
   ```asm
   004134b3  add      eax, 2              ; y < 130 时加速 +2
   004134c5  mov      word ptr [ebx + 0x48bbca], 0x10   ; ★ 上限 16
   004134e2  mov      al, byte ptr [edi + 0x475010]      ; ★ type→速度表
   00413523..00413525  ; 出界（y > 0x17c=380）→ 清 x 移除
   ```
   `0x475010` = `{0x18, 0x12, 0x0f, 0x0c, 0x0f}` = **24 / 18 / 15 / 12 / 15**
   （type 0..4；type 4 = 炸弹 15）。

   **（f）碰撞与结算**：
   ```asm
   004133d4  cmp      edi, 4 / jne 0x413436
   00413436  inc      dword ptr [edi*4 + 0x48bbb4]       ; ★ 计数器 +1
   0041343f  mov      word ptr [esi*8 + 0x48bbc4], bx   ; 吃掉
   004133d9..004133ed  ; type 4：停 id 0x18、播 id 0x0f
   00413407  mov      eax, dword ptr [0x48bce8]         ; data.mkf 0x20e 被炸动画
   0041341d  mov      word ptr [0x48bd56], 4            ; 死亡图
   00413428  mov      byte ptr [0x48bd5a], 1
   0041342e  mov      byte ptr [0x48bd58], 1            ; ★ 立即结束
   ```

### 胜负判定 / 奖罚数值（★ 公式已逐指令确认）

**计分**（`0x004144d3`）：
```asm
0041449e  mov      edx, dword ptr [0x48bbb8]     ; c1（錢袋）
004144a6  shl      ecx, 2 / add ecx, edx         ; c1 × 5
004144ab  mov      edx, dword ptr [0x48bbb4]     ; c0（寶箱）
004144b3  shl      eax, 2 / add eax, edx / add eax, eax   ; c0 × 10
004144ba  add      ecx, eax
004144bc  mov      edx, dword ptr [0x48bbbc]     ; c2（元寶）
004144c4  shl      eax, 2 / sub eax, edx         ; c2 × 3
004144c9  add      eax, ecx
004144cb  mov      edx, dword ptr [0x48bbc0]     ; c3（金幣）
004144d1  add      edx, eax                      ; + c3 × 1
004144d3  mov      dword ptr [0x48bcec], edx     ; ★★ 得分
```

```
得分 = 10·c0(寶箱) + 5·c1(錢袋) + 3·c2(元寶) + 1·c3(金幣)
```

| 项目 | 数值 | 立即数/地址 |
|---|---|---|
| 寶箱 (type 0) | **10** 分 | `0x4144b8 add eax,eax` |
| 錢袋 (type 1) | **5** 分 | `0x4144a9 add ecx,edx` |
| 元寶 (type 2) | **3** 分 | `0x4144c7 sub eax,edx` |
| 金幣 (type 3) | **1** 分 | `0x4144d1 add edx,eax` |
| 炸彈 (type 4) | **立即结束，无分** | `0x4133d4 cmp edi,4` |
| 掉落物初始 y | **100** | `0x412451` |
| 掉落速度 type0..4 | **24 / 18 / 15 / 12 / 15** | 表 `0x475010` |
| 加速段 | y<130 时 `+2`，上限 **16** | `0x4134b3` / `0x4134c5` |
| 財神投放影格 | `rand()%5` | `0x413904` |
| 爆炸 x | `rand()%140 + 160`（左）/ `+360`（右） | `0x4137ae` / `0x4137d1` / `0x4137e0` |
| 爆炸触发概率 | `rand()%10 < 7`（70%） | `0x4123cb cmp edx,7` |
| 掉落物种类概率 | 金幣 45% / 元寶 30% / 錢袋 15% / 寶箱 10% | `0x412411` / `0x41241d` / `0x412429` |
| 角色移动 | 每帧 **10 px**，死区 **8 px** | `0x413673` / `0x413688` / `0x413661` |
| 財神移动 | 每帧 **12 px**；左界 **110** / 中线 **320** / 右界 **530** | `0x4138ba` / `0x4139e4` / `0x4138c7` / `0x4138e7` |
| 计时 | **360 tick × 50 ms = 18 s**；开场倒数 **10 tick = 0.5 s** | `0x41500f` / `0x41502a` / `0x4151f1` |
| HUD 显示时间 | `[0x48bd2c] / 2`（`sar eax,1`） | `0x4141a0` |
| **结算分级** `[0x48bd56]` | `<40 → 1`、`40..49 → 2`、`50..59 → 0`、`≥60 → 3` | `0x4150fe` / `0x41510e` / `0x41511e` / `0x41512c` |
| 结算暂停 | 2000 ms | `0x41513f push 0x7d0` |

### 随机数使用点

| VA | 取模 | 选什么 |
|---|---|---|
| `0x004137a7`（在 `0x413248` 内） | `% 140` | 爆炸 x 偏移 |
| `0x004138d2` | `% 4` | 是否提早转入攻击状态 |
| `0x00413904` | `% 5` | 下次投放的动画影格 |
| `0x004139cf` | `% 4` | 状态 4 的镜像版 |
| `0x004139f9` | `% 5` | 同上 |
| `0x004123ba` | `% 10 < 7` | 是否启动爆炸 |
| `0x00412400` | `% 20` | 掉落物种类加权抽取 |
| `0x00415457` / `0x004154b6` | 见 §二 | 不玩分支 |

> `0x4155fc` 与 `0x414fcd` 内**没有** `call 0x456f2d`（全部在世界更新 `0x413248` 及其子函数里）。

### 动画与输入接线点

| 项 | VA | 说明 |
|---|---|---|
| `SetTimer`（IAT `0x462324`） | `0x00415034`，**周期 `0x32` = 50 ms** | `0x41502a push 0x32` |
| `KillTimer`（IAT `0x4622fc`） | `0x004150de` | 结束 |
| `_Wait_0402_Message` | `0x4018e7`，调用点 `0x4157db` | WndProc `0x414fcd` |
| `_read_mkf` | `0x450441` | 多个资源 |
| `0x4502fe` | `0x41587e` | 打开 `0x4637cf` 的 mkf |
| `0x45285e` | `0x415144` | 结束时的收尾（参数 `0x7d0`） |
| `0x401966` | `0x41514e` | 结束时的收尾 |

---

### ★ IAT 槽名（PE 导入表解析所得，本次核实）

| 槽 | 函数 |
|---|---|
| `0x4622d8` | `DefWindowProcA` |
| `0x4622e0` | `DispatchMessageA` |
| `0x4622f8` | `InvalidateRect` |
| `0x4622fc` | `KillTimer` |
| `0x46230c` | `PeekMessageA` |
| **`0x462310`** | **`PostMessageA`**（⚠️ 既有 `game-loop.md` 未登记；**不是 SetTimer**） |
| `0x462314` | `PostQuitMessage` |
| `0x462318` | `RegisterClassA` |
| `0x46231c` | `SetCursorPos` |
| **`0x462324`** | **`SetTimer`** |
| `0x462328` | `SetWindowsHookExA` |
| `0x462334` | `TranslateMessage` |
| `0x462340` | `ValidateRect` |


## 五之二、★ 三处接线更正与既有文档的矛盾

| 既有说法 | 实测 | 证据 |
|---|---|---|
| 「企鵝挖寶入口 `0x004151c1`」 | `0x4151c1` 是 `0x414fcd` 的 `WM_PAINT` 分支尾部；入口是 **`0x415215`** | `0x4151c1 mov eax,[0x48a0dc]` / `0x4151e8 cmp [0x48bd8c],0x63` |
| 「`0x414fcd` 的 SetTimer 周期 50 ms，所在函数 `0x414fcd`；`0x414ba4` 周期 100 ms」（`game-loop.md` §三 的表） | 三处 SetTimer 实际在 **`0x4148e3`（100 ms）/ `0x414c42`（100 ms）/ `0x415034`（50 ms）**，分别属于 WndProc `0x414858` / `0x414bbc` / `0x414fcd`；**`0x414ba4` 是 6 项跳表，不是函数入口**（`0x414ba4`..`0x414bc0` 是表数据） | `0x414ba4` 的 6 个 dword = `{0x414e8d,0x414e99,0x414ea2,0x414eae,0x414eba,0x414ebe}`；`0x414c42` 落在 `0x414bbc` 的函数体里 |
| 「IAT `0x462310` = SetTimer（`game-loop.md` §二 与 §二·消息泵那段把 `0x462310` 记作 `PeekMessage` 相关）」 | **`0x462310` = `PostMessageA`**（PE 导入表解析） | 见 §五之二 起的 IAT 表；`0x414979 push 0x405; call cs:[0x462310]` 与「投递自定义消息」语义吻合 |
| 「`[0x497159]` 语义未定」 | `[0x497159]` = **`RICH4.CFG` 设定块 `0x497158` 的第 2 个字节**，标签表 `0x474a54[1]` = 「動畫過程」 | 写者集中在 `0x40ec14..0x40f2eb`（cfg 解析）；`0x474a54` 是 cfg 标签指针表 |

## 六、`0x00415872` 是**另一个**函数，不是小游戏

`tools/r4scan.py` 会报 `call 0x415872 at 0x401cf0`，容易被误当成第三个入口。
实测它：

```asm
00415879  push     0x4637cf
0041587e  call     0x4502fe            ; 打开某 mkf
00415888  mov      edi, eax
0041588e  push     0x2d / 0x2e        ; read_mkf(handle, 0, 0, 0x2d / 0x2e)
004158b2  push     0x20
004158b4  push     0
004158b6  push     0x48bd90
004158bb  call     0x456f60            ; memset(0x48bd90, 0, 0x20)
004158e0  mov      cl, byte ptr [eax + 0x496b7b]   ; character
004158e6  ...      ; eax = player*0xf + 0x2f + character
004158f7  call     0x450441            ; read_mkf(handle, 0, 0, 0x2f + player*0xf + character)
00415906  mov      dword ptr [ecx + edx*4 + 0x48bd90], eax
```

它是**按角色载入一串资源**的初始化函数（调用点 `0x401cf0`，位于主循环初始化段），
与落点事件的三个小游戏**没有调用关系**。本文不把它算作小游戏。

---

## 七、未决（明确列出，不推测）

1. `0x497159`（RICH4.CFG 设定块的字节）**对应配置文件里的哪个选项名**。
   既有信息：`0x411e8f` 起读 `RICH4.CFG`；同为 cfg 块的邻居有
   `0x497158`（`0x474a54[0]`「遊戲速度」）与 `0x49715a`（`[2]`「音 樂」）——
   按 `0x474a54` 的顺序 `0x497159` 恰好是 `[1]`「動畫過程」，但
   **子代理未在指令里读到该索引**，故本文件不写成结论。
2. `玩家 +0x15`（`0x496b7d`）**除 1 以外的取值语义**。既有「1 = 电脑」的命名
   与本文件 §一 1.4 的现象冲突（`==1` 时反而弹交互框）——见 §六的更正表。
3. `玩家 +0x37`（`0x496b9f`）在分派器 `0x419873` 处的语义。
4. ~~`0x475299` 的「落点类型 → 字体/文本资源」表~~ **✅ 2026-09-19（§7.95）**：那是**落点音效/事件音**的索引表 —— `byte [kind + 0x475299]` 再 `× 8 + 0x48234a` 得到**音效描述符指针**，`0x4540d8` 才是音效描述符内部字段的读取者。另注：`0x47528e` 是**另一张** kind→索引表（`0x41ae64`，比上表低 `0x0b` 字节），两者都经 `0x47517c` 那张指针表解析。`0x48234a` 表项的**字段布局**仍未逐字段读通。
5. panel `0x4e` 的 640×480 FLIC 是**开场**还是**结算**用的
   （推断开场：`0x405` 由开场倒数归零时 `PostMessage` 投递）。
6. `0x48bd84`（小游戏 B 的开场倒数）由 `0x63` 改成 `5` 的意图。
7. ~~`0x450f04` 的语义（输入轮询还是动画推进）~~ **✅ 2026-09-19（§7.98）**：它是**动画推进** —— 每次调用从 `[0x476378]` 往后走**恰好一帧**（`0x450ff2 lea eax,[ebx+ebp]` 把游标加上当前块长度；`0x451000` 认出 `0xF1FA` 帧头就停），调用点在每帧重绘里（如投注屏 `0x42fd5f`）⇒ **一帧重绘 = 一帧动画**，**不看游戏速度档**（速度只分频 `[0x46cafa]` 那个游戏 tick）。
8. `0x475015` 的动画表（財神状态 × 影格）与 `[0x48bd44]` 的完整对应。
9. `0x48bd40`、`0x48bd54`（炸弹计数）的语义。
10. panel `0x4f` 第 10..19 张未被引用；`0x48bc4a`（槽 `+6`）未使用。
11. **三个游戏是否都会在真实对局中出现**（即地图事件类型 6/7/8 的分布）
    —— 事件类型来自地图节点数据，不在 exe 里。
