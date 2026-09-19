# AI 决策入口与辅助函数（Rich4 v3.11 / rich4.exe, ImageBase 0x400000）

> 真值：`Rich4/rich4.exe` 文件字节 + 本文所有 `@source` 处的**实际反汇编文本**（由 `tools/scratch/r4dump.py`、`tools/scratch/r4lin.py`、`tools/scratch/r4scan.py` 现场产出）。
> `rich4-spec/docs/systems/ai.md` 只当**导航提示**：其中 `0x419703 = 清屏`、`case 9/10 可能`、`0x4971xx 是"指令码"` 三处与本次实测不符（见下）。
> **注意**：`gen/functions.json` 的 `size` / `callers` 在本区域**多处不准**（例：`0x417d65` 记 97 字节、`0x401010` 未登记为函数、`0x415d31` 的调用者漏了 3 处）。本文一律以现场扫描为准。

---

## AI 决策的整体结构与入口

### 1. 决策时机与调用者（谁在什么时候调用 AI）

**顶层：主循环每帧一次。**
`0x401b9e` 起的 WinMain 级函数在 `0x401bb0` 把窗口过程登记为 `0x4019dd`：

```asm
@source 0x00401bb0   mov      dword ptr [esp + 4], 0x4019dd
@source 0x00401c05   call     dword ptr cs:[0x462318]     ; RegisterClassA
@source 0x00401d38   call     dword ptr cs:[0x46230c]     ; PeekMessageA（消息泵 0x401d2b↔0x401d66）
@source 0x00401d5f   call     dword ptr cs:[0x4622e0]     ; DispatchMessageA
```

消息泵每帧之后进入「决策点」，条件成立才调 `0x418c55`：

```asm
@source 0x00401d8d   imul     eax, dword ptr [0x49910c], 0x34   ; [0x49910c]=当前玩家座位
@source 0x00401d94   cmp      byte ptr [eax + 0x498ea2], 0
@source 0x00401d9b   jne      0x401db8
@source 0x00401d9d   mov      ch, byte ptr [eax + 0x498ea0]
@source 0x00401da3   test     ch, 0x80                          ; 「该玩家有待处理决策」标记
@source 0x00401da6   je       0x401db8
@source 0x00401dad   mov      byte ptr [eax + 0x498ea0], dl      ; dl = ch&0x7f，清掉 bit7
@source 0x00401db3   call     0x418c55                          ; ★ 回合决策驱动
```

**`0x418c55` = 回合决策驱动（phase 分派器）**，只有**一个**调用点（`r4scan.py 0x418c55` → `call at 0x401db3`）：

```asm
@source 0x00418d6e   push     0
@source 0x00418d70   call     0x40c912          ; 取当前玩家所处「相位」→ eax ∈ 0..5
@source 0x00418d75   add      esp, 4
@source 0x00418d78   cmp      eax, 5
@source 0x00418d7b   ja       0x418e7a
@source 0x00418d81   jmp      dword ptr [eax*4 + 0x418c3d]   ; ★ 6 项相位跳表
```

相位跳表实测内容（逐 dword 读出，`0x418c3d`，6 项）：

| 相位 | 入口 | 实测代码 | 归类 |
|---|---|---|---|
| 0 | `0x418d88` | `@source 0x00418d88 call 0x418e7f` / `mov byte ptr [0x46cafb],1` / `ret` | 落点事件结算（`0x418e7f` → `0x41982d`） |
| 1 | `0x418d99` | `@source 0x00418d99 call 0x4196f1` / `SetCursorPos` / `push 1; call 0x402460` / `ret` | 光标/画面复位 |
| **2** | `0x418dc6` | 见下 | **★ AI 决策块** |
| 3 | `0x418e7a` | 直接收尾 | 空 |
| 4 | `0x418e7a` | 直接收尾 | 空 |
| **5** | `0x418dc6` | 同相位 2 | **★ AI 决策块** |

**AI 决策块的完整顺序（`0x418dc6` 起）**：

```asm
@source 0x00418dc6   mov      esi, dword ptr [0x49910c]
@source 0x00418dcc   cmp      esi, 4
@source 0x00418dcf   jge      0x418e75                    ; 座位>=4（非玩家位）→ 跳过
@source 0x00418dd5   imul     eax, esi, 0x68
@source 0x00418dd8   test     byte ptr [eax + 0x496b7d], 0x30   ; player+0x15 电脑/托管标志
@source 0x00418ddf   jne      0x418e75                    ; 非 1（不是电脑）或被 0x30 置位 → 跳过
@source 0x00418de5   push     esi
@source 0x00418de6   call     0x42bf03                    ; ① 银行 AI（含 rand()%3 门槛）
@source 0x00418dee   mov      eax, dword ptr [0x49910c]
@source 0x00418df4   call     0x42c79f                    ; ② 银行 AI（第二段）
@source 0x00418dfc   push     0
@source 0x00418dfe   call     0x436b0a                    ; ③ 第 3 段（参数 0）
@source 0x00418e06   cmp      byte ptr [0x46caf8], 0
@source 0x00418e0d   jne      0x418e7a                    ; 暂停中 → 不做主体决策
@source 0x00418e13   call     0x4284be                    ; ④ 股市 AI（= 路由 case 9）
@source 0x00418e18   call     0x456f2d                    ; ★ rand()
@source 0x00418e1d   test     al, 1
@source 0x00418e1f   je       0x418e28
@source 0x00418e21   call     0x441baa                    ; ⑤a 用卡/用道具（= 路由 case 8）
@source 0x00418e26   jmp      0x418e2d
@source 0x00418e28   call     0x447d97                    ; ⑤b 另一支（= 路由 case 7）
```

⇒ **一个 AI 玩家的一个决策帧 = 银行(2 段) → 第 3 段 → 股市 → rand()&1 二选一（用卡 / 另一支）**，全部**同步顺序执行**，没有「AI 线程」。
⇒ 相位 2 与相位 5 都是这条块，所以同一次行动里 AI 可能被判两次（两次之间 `0x40c912` 的返回值由局面变化决定）。
⇒ `0x40c912`（唯一两个调用点：`0x418d70`、`0x418e81`）按 `player+0x15`、`player+0x32/+0x36/+0x37` 等字段+实参选相位，返回 0..5；本报告不展开其分支。

**行动路由 `0x417d65` 的两个调用点**（`r4scan.py 0x417d65` → `call at 0x401321`、`call at 0x418870`）：

- **调用点 A `0x401321`**：位于 **全局键盘钩子过程 `0x401010`**。
  钩子安装点：

  ```asm
  @source 0x00401784   push     0x401010                       ; lpfn
  @source 0x00401789   push     2                              ; idHook = WH_KEYBOARD
  @source 0x0040178b   call     dword ptr cs:[0x462328]        ; SetWindowsHookExA
  @source 0x00401792   mov      dword ptr [0x48a050], eax      ; hHook
  ```

  钩子过程取键盘 wParam/lParam（入口 `@source 0x00401010`：`push ebx/esi/edi/ebp` + `sub esp,8`，故 3 个参数落在 `[esp+0x1c]/[esp+0x20]/[esp+0x24]`）：

  ```asm
  @source 0x00401017   mov      esi, dword ptr [esp + 0x20]    ; esi = VK 虚拟键码
  @source 0x0040101b   mov      ebx, dword ptr [esp + 0x24]    ; ebx = lParam（bit31=抬起）
  @source 0x0040102f   call     dword ptr cs:[0x4622ec]        ; GetCursorPos
  @source 0x00401038   mov      ax, word ptr [0x497168]        ; ★ 键位表[0]
  @source 0x0040103e   cmp      esi, eax
  ```

  **动作号来源 = 数据表**：`0x497168` 起 **28 个 WORD**（stride 2，共 `0x38` 字节）。
  初始化两条路径（都实测）：
  - 缺省表拷贝：`@source 0x00411f0a push 0x38` / `@source 0x00411f0c push 0x47edc2` / `@source 0x00411f11 push 0x497168` / `@source 0x00411f16 call 0x456de8`（= memcpy(dst 0x497168, src 0x47edc2, 0x38)）；
  - 读 `RICH4.CFG`：`@source 0x00411f80`（函数）里 `push 1; push 0x38; push 0x497168; call 0x457ada`（fread）。
  实测：`0x47edc2` 的 28 个 WORD 与 `Rich4/RICH4.CFG` 偏移 `0x10` 起的 28 个 WORD **逐字节相同**：
  `26,27,28,25,0d,1b,09,09,59,4e,20,44,57,58,43,45,46,4d,bc,be,41,56,53,4c,48,21,22,1151`（WORD，hex）。

  **表下标 → 路由 action 的实测映射**（`0x497168 + 2*k`）：

  | k | 表项 VA | 缺省键值 | 路由 action | 证据 |
  |---|---|---|---|---|
  | 10 | `0x49717c` | `0x20` (Space) | （不直接进路由）→ `push 0; call 0x402460` / `call 0x419703` / `call 0x41d546` / `call 0x40dd1f` | `@source 0x00401264 mov dx,word ptr [0x49717c]` / `@source 0x00401279 call 0x419703` |
  | 11 | `0x49717e` | `0x44` ('D') | （不直接进路由）→ 改 `player+0x11` 等 | `@source 0x0040128f mov dx,word ptr [0x49717e]` / `@source 0x004012b7 mov al,byte ptr [eax + 0x496b79]` |
  | 12 | `0x497180` | `0x57` ('W') | **10** | `@source 0x0040131f push 0xa` / `@source 0x00401321 call 0x417d65` |
  | 13 | `0x497182` | `0x58` ('X') | **9** | `@source 0x00401338 push 9` / `@source 0x0040133a jmp 0x401321` |
  | 14 | `0x497184` | `0x43` ('C') | **8** | `@source 0x00401349 push 8` |
  | 15 | `0x497186` | `0x45` ('E') | **7** | `@source 0x0040135a push 7` |
  | 16 | `0x497188` | `0x46` ('F') | **6** | `@source 0x0040136b push 6` |
  | 17 | `0x49718a` | `0x4d` ('M') | **5** | `@source 0x0040137c push 5` |
  | 18 | `0x49718c` | `0xbc` | （不直接进路由）→ `0x499088` 递减+`push 1; call 0x415e70` | `@source 0x00401385 mov dx,word ptr [0x49718c]` |
  | 19 | `0x49718e` | `0xbe` | （同上，递增） | `@source 0x004013c5 mov dx,word ptr [0x49718e]` |
  | 20 | `0x497190` | `0x41` ('A') | **2** | `@source 0x00401405 push 2` |
  | 21 | `0x497192` | `0x56` ('V') | **1** | `@source 0x00401419 push 1` |
  | 22 | `0x497194` | `0x53` ('S') | **4** | `@source 0x0040142d push 4` |
  | 23 | `0x497196` | `0x4c` ('L') | **3** | `@source 0x00401441 push 3` |
  | 24 | `0x497198` | `0x48` ('H') | **0** | `@source 0x00401457 push 0` |

  ⇒ 键盘钩子里 **action 0..10 全部可达**（缺省键 `H,V,A,L,S,M,F,E,C,X,W`），每个 case 只做 `push imm` + `jmp/call 0x417d65`，**没有** `test ebx,0x80000000` 抬起过滤（`0x401312`–`0x401457` 全段实测无该 test）。
  ⇒ 因此同一按键的按下与抬起都会触发（原版行为，照抄）。

- **调用点 B `0x418870`**：位于**棋盘屏窗口过程 `0x417e26`**。该函数被登记进「每屏窗口过程表」：

  ```asm
  @source 0x00401981   push     ebx
  @source 0x00401982   mov      edx, dword ptr [0x46cad8]
  @source 0x00401988   inc      edx
  @source 0x00401989   mov      dword ptr [0x46cad8], edx
  @source 0x0040198f   mov      dword ptr [edx*4 + 0x48a010], 0x417e26    ; ★ 注册为屏处理函数
  @source 0x004019aa   call     dword ptr cs:[0x462310]                  ; PostMessageA(hwnd,0x401,…)
  ```

  真 WndProc `0x4019dd` 对未识别消息转发到该表：`@source 0x00401b3c cmp dword ptr [ebx + 0x48a010], 0` / `@source 0x00401b51 call dword ptr [ebx + 0x48a010]`。
  `0x417e26` 自己按 msg 分派（实测）：`0x201`/`0x203`→`0x418151`、`0x202`→`0x4186cb`、`0x205`→`0x418893`、`0x200`→`0x418910`、`0x113`→`0x418b7a`、`0xf`→`0x418bb9`、`0x401`→`0x417eba`、其余→`DefWindowProcA`。
  `0x418870` 落在 **`0x202`（WM\_LBUTTONUP）** 分支内：

  ```asm
  @source 0x004186f3   mov      bl, byte ptr [0x48be28]     ; bl = 被点中的工具条格号（或格号+100）
  @source 0x004186f9   cmp      bl, 1
  @source 0x004186fc   je       0x418707
  @source 0x004186fe   cmp      bl, 2
  @source 0x00418701   jne      0x418855
  @source 0x00418863   cmp      bl, 0x64
  @source 0x00418866   jb       0x418878
  @source 0x0041886a   mov      al, bl
  @source 0x0041886c   sub      eax, 0x64                    ; action = bl - 100
  @source 0x0041886f   push     eax
  @source 0x00418870   call     0x417d65                     ; ★ action 0..10
  ```

  格号由 **WM\_LBUTTONDOWN（`0x201`）** 分支写入，实测是「棋盘屏左上角 440×40 的 11 格横条」（x<0x1b8=440、y<0x28=40，每格 40 像素 = 11 格）：

  ```asm
  @source 0x00418670   cmp      esi, 0x1b8                  ; esi = 鼠标 x
  @source 0x00418678   cmp      edx, 0x28                   ; edx = 鼠标 y
  @source 0x0041868c   mov      ebx, 0x28
  @source 0x00418691   mov      eax, esi
  @source 0x00418698   idiv     ebx                         ; x / 40
  @source 0x0041869a   add      eax, 0x64                   ; + 100
  @source 0x0041869d   mov      byte ptr [0x48be28], al     ; ★ 存格号+100
  ```

  ⇒ 所以**同一张跳表既由 11 格工具条点击驱动、又由键盘热键驱动**；`bl == 0xc` 时走 `@source 0x0041885c mov byte ptr [0x48be2a], al`（al=0），不进路由。
  ⇒ `0x48be28` **不止一处写入**（实测写点：`0x418127`、`0x4181d1`、`0x4184a0`、`0x4184a7`、`0x418515`、`0x41869e`、`0x4186f5`、`0x418709`、`0x418766`、`0x4187d2`、`0x41888a`）。另一路是 `@source 0x0041849f mov byte ptr [0x48be28], al`（前置 `@source 0x0041849e inc eax`，来自 `(y-3)/25+1`）⇒ 侧栏页号 1..N，正是 `bl==1`/`bl==2` 两分支读到的语义。该字节是**多义槽位**（侧栏页号，或 `100+` 工具条格号）。

- **AI 回合推进的辅助链**（不是决策本身，但同属该屏）：
  `0x41d546` → `0x41906a` → `0x417e26(msg=0xf)`：

  ```asm
  @source 0x0041d546   xor      edx, edx
  @source 0x0041d548   mov      dword ptr [0x48be18], edx
  @source 0x0041d54e   push     1
  @source 0x0041d550   call     0x41906a
  @source 0x0041906e   push     0
  @source 0x00419072   push     0xf
  @source 0x00419074   mov      edx, dword ptr [0x48a0d4]
  @source 0x0041907b   call     0x417e26
  ```

  `0x41d546` 有 **30 个**调用点（`r4scan.py 0x41d546`），遍布用卡/用道具/事件函数——即「改完局面就通知棋盘屏重画」。

### 2. 行动路由 `0x00417d65` 与动作号来源

```asm
@source 0x00417d65   push     ebx
@source 0x00417d66   push     0
@source 0x00417d68   call     0x402460                    ; 0x402460(arg)：置界面标志/重绘
@source 0x00417d70   call     0x419703                    ; 见 §3
@source 0x00417d75   mov      dword ptr [0x48bde4], 0xffffffff
@source 0x00417d7f   push     1
@source 0x00417d81   call     0x415d31                    ; 见 §3（arg=1 → 实绘 11 格工具条）
@source 0x00417d89   mov      ecx, dword ptr [esp + 8]    ; 参数 = action
@source 0x00417d8d   cmp      ecx, 0xa
@source 0x00417d90   ja       0x417dff
@source 0x00417d96   mov      eax, ecx
@source 0x00417d98   jmp      dword ptr [eax*4 + 0x417d39]  ; ★ 11 项跳表
@source 0x00417dff   call     0x40defe                    ; 后置检查（返回 0/1）
@source 0x00417e04   cmp      eax, 1
@source 0x00417e07   jne      0x417e24
@source 0x00417e09   cmp      dword ptr [esp + 8], 3      ; action==3 ?
@source 0x00417e0e   jne      0x417e15
@source 0x00417e10   cmp      ebx, -1                     ; case3 的返回值 == -1 ?
@source 0x00417e13   jne      0x417e24
@source 0x00417e15   call     0x4196f1                    ; 置 [0x46cafd]=1 + 刷新
@source 0x00417e1a   push     1
@source 0x00417e1c   call     0x402460
@source 0x00417e24   pop      ebx
@source 0x00417e25   ret
```

跳表 `0x417d39` 逐项实测（6 项示例与全部 11 项）：

| case | 跳表 dword@VA | 处理函数 VA | 决策类别 | 调用证据 |
|---|---|---|---|---|
| 0 | `@0x417d39 = 0x417d9f` | `0x44eb39` | **帮助/说明模态子画面**：`0x4502fe("help.mkf")`，画 8 行（表 `0x4761b4`，stride 20），模态循环回调 `0x44e40b` | `@source 0x00417d9f push 0x3c` / `@source 0x00417da1 push 0x14` / `@source 0x00417da3 call 0x44eb39`；`@source 0x0044eb3c push 0x466096` / `@source 0x0044eb41 call 0x4502fe`（0x466096 = `"help.mkf"`）/ `@source 0x0044ebe7 push 0x44e40b` / `@source 0x0044ebec call 0x4018e7` |
| 1 | `@0x417d3d = 0x417dad` | `0x411b53` | **地图/坐标绘制**（表 `0x474b3a`，6 字节/项，两组 `movsx word`），surface 资源 3 | `@source 0x00417dad push 1` / `@source 0x00417daf call 0x411b53`；`@source 0x00411b9b movsx esi,word ptr [eax*2 + 0x474b3c]`；`@source 0x00411b67 push 3` |
| 2 | `@0x417d41 = 0x417db6` | `0x41e345` | **模态子画面**（surface 资源 `0x4d`，字符串 `0x463cd8`，**推断**） | `@source 0x00417db6 call 0x41e345`；`@source 0x0041e34f push 0x4d`；`@source 0x0041e386 push 0x463cd8` |
| 3 | `@0x417d45 = 0x417dbd` | `0x403d74` | **模态子画面**（surface 资源 `0x208`；arg=1）；也由主循环 `@source 0x00401e31 call 0x403d74` 以 arg=0 调用，返回值 `-1` 时重入初始化 | `@source 0x00417dbd push 1` / `@source 0x00417dbf call 0x403d74` / `@source 0x00417dc7 mov ebx, eax`（后置检查用） |
| 4 | `@0x417d49 = 0x417dcb` | `0x404165` | **模态子画面**（surface 资源 `0x208` + `2`） | `@source 0x00417dcb call 0x404165`；`@source 0x00404170 push 0x208`；`@source 0x0040418d push 2` |
| 5 | `@0x417d4d = 0x417dd2` | `0x40a9bd` | **模态循环**（回调 `0x40a801`），结束后 `0x415e70(1)` | `@source 0x00417dd2 call 0x40a9bd`；`@source 0x0040a9bf push 0x40a801` / `@source 0x0040a9c4 call 0x4018e7` |
| 6 | `@0x417d51 = 0x417dd9` | `0x424492` | **模态循环**（回调 `0x423cf3`，surface 资源 `9`+`0x4a`，循环前后各 `call 0x41906a`） | `@source 0x00417dd9 call 0x424492`；`@source 0x00424498 push 9`；`@source 0x004244ca push 0x423cf3` |
| 7 | `@0x417d55 = 0x417de0` | `0x447d97` | **AI 动作**：先验 `player+0x15 == 1`，再 `0x41d546`（推 msg 0xf），开 surface 资源 `0xb`；含 1 处 `rand()` | `@source 0x00417de0 call 0x447d97`；`@source 0x00447da5 mov dl,byte ptr [eax + 0x496b7d]` / `@source 0x00447dab cmp dl,1` / `@source 0x00447db4 call 0x41d546`；`@source 0x00447dbd push 0xb` |
| **8** | `@0x417d59 = 0x417de7` | `0x441baa` | **★ AI 用卡 / 用道具**（读卡槽数组 `0x499120`；含 `rand()%手牌数` 选起点） | `@source 0x00417de7 call 0x441baa`；`@source 0x00441b71`、`@source 0x00441d80` 引用 `0x499120`；`@source 0x00441d4a call 0x456f2d` |
| **9** | `@0x417d5d = 0x417dee` | `0x4284be` | **★ 股市 AI 决策**（字符串 `0x463f1a = "股票名稱"`，surface 资源 `0x49`/`0x4a`，含 **5** 处 `rand()`） | `@source 0x00417dee call 0x4284be`；`@source 0x0042852f push 0x463f1a`；`@source 0x004284e2 push 0x49`；`@source 0x004284fc push 0x4a` |
| **10** | `@0x417d61 = 0x417df5` | `0x42b58f` | **★ 持股表 AI 决策**（字符串 `0x4640a6 = "持有股數表"`，surface 资源 `0x4b`） | `@source 0x00417df5 push 0` / `@source 0x00417df7 call 0x42b58f`；`@source 0x0042b5cb push 0x4640a6`；`@source 0x0042b597 push 0x4b` |

> case 0/2/3/4/5/6 都通过 `0x4018e7` 建「模态消息循环」（实测：`0x4018e7` 把回调写入 `0x48a010[++[0x46cad8]]`，`PostMessageA(hwnd,0x401,…)`，然后 `PeekMessageA`/`DispatchMessageA` 循环到 `msg==0x402`）：

```asm
@source 0x004018fe   mov      dword ptr [eax*4 + 0x48a010], edx   ; 新屏处理函数 = 实参
@source 0x0040190c   push     0x401
@source 0x00401918   call     dword ptr cs:[0x462310]             ; PostMessageA
@source 0x0040192c   call     dword ptr cs:[0x46230c]             ; PeekMessageA
@source 0x00401937   cmp      dword ptr [esp + 4], 0x402
@source 0x0040194e   call     dword ptr cs:[0x4622e0]             ; DispatchMessageA
@source 0x00401957   dec      dword ptr [0x46cad8]
```

⇒ 归类为「模态子画面」的 case 本质是**决策后的 UI**，不是规则本身。case 7/8/9/10 是被 AI 回合驱动 `0x418c55` 直接复用的**决策函数**（见 §1 的 `0x418e13`/`0x418e21`/`0x418e28`）。

### 3. 辅助函数清单

| 函数 | VA | 签名 | 返回值 | 语义 | 证据 |
|---|---|---|---|---|---|
| `0x419703` | `0x00419703` | `void f(void)` | 无 | 清 `[0x46cafd]`（键盘处理开关=关）后 `0x417191(0)` 刷新棋盘 | `@source 0x00419703 xor ah, ah` / `@source 0x00419705 mov byte ptr [0x46cafd], ah` / `@source 0x0041970b push 0` / `@source 0x0041970d jmp 0x4196fa`；`@source 0x004196fa call 0x417191` / `@source 0x004196ff add esp, 4` / `@source 0x00419702 ret` |
| `0x4196f1` | `0x004196f1` | `void f(void)` | 无 | 置 `[0x46cafd]=1`（键盘处理开关=开）后 `0x417191(1)` 刷新 | `@source 0x004196f1 mov byte ptr [0x46cafd], 1` / `@source 0x004196f8 push 1` / `@source 0x004196fa call 0x417191` |
| `0x417191` | `0x00417191` | `void f(int mode)` | 无 | 棋盘/画面刷新：由 `[0x48bdec]/[0x48bde8]`+`[0x48bdd8]/[0x48bddc]` 组矩形，`0x40235d(&rect)`，DirectDraw blit；`mode!=0` 另走「读当前玩家 `+0x38/+0x39`」分支 | `@source 0x004171aa mov edx, dword ptr [0x48bdd8]` / `@source 0x004171c9 call 0x40235d` / `@source 0x004171eb cmp dword ptr [esp + 0x1c], 0` / `@source 0x00417256 cmp byte ptr [eax + 0x496ba0], 0`（`+0x38`） |
| `0x415d31` | `0x00415d31` | `void f(int draw)` | 无 | 布置/绘制棋盘屏 11 格行动工具条（**440×40**，每格 40）；由 `[0x475110]&1` 做一次性初始化；`draw!=0` 时才做实际 rect/blit | `@source 0x00415d38 test byte ptr [0x475110], 1` / `@source 0x00415d7c cmp ebx, 0xb`（11 项循环）/ `@source 0x00415d94 cmp ebx, ecx`（`ecx=[0x48bde4]` 高亮格）/ `@source 0x00415dfb cmp dword ptr [esp + 0x24], 0` / `@source 0x00415e08 mov dword ptr [esp + 0xc], 0x28` / `@source 0x00415e13 mov dword ptr [esp + 8], 0x1b8` / `@source 0x00415e64 or byte ptr [0x475110], 1` |
| `0x402460` | `0x00402460` | `void f(int on)` | 无 | 设界面标志 `[0x48a178]`+按需 `0x402250`/`0x40235d` | `@source 0x0040246b mov byte ptr [0x48a178], al` / `@source 0x0040247b call 0x402250` |
| `_rich4_find_most_hostile_player` | **`0x0040d2d3`** | `int f(int self)` | 座位下标，无候选时 **-1** | 找「**self 对之敌意最高**」的在世玩家（详见 §4） | 见 §4 |
| `_rich4_calculate_land_toll` | `0x00419744` | `int f(int player_1based, const char* name)` | 金额 | 过路费：扫地块表 `[0x498e84]+0x34` stride `0x34`，`+0x18`=type、`+0x19`=owner、`+0x1a`=level，`name=NULL` 时算该玩家全部连锁店合计 | `@source 0x00419748 mov ebp, dword ptr [esp + 0x14]` / `@source 0x0041974e cmp dword ptr [esp + 0x18], 0` / `@source 0x00419760 add ebx, 0x34` / `@source 0x00419777 mov al, byte ptr [ebx + 0x19]` / `@source 0x00419793 mov al, byte ptr [ebx + 0x1a]` |
| `_rich4_get_player_num_chain_store` | **`0x0041970f`** | `int f(int player_1based)` | 连锁店数量 | 扫地块表，`+0x18 != 0`（连锁店）且 `+0x19 == player` 的块数 | `@source 0x00419711 mov esi, dword ptr [esp + 0xc]` / `@source 0x00419724 cmp edx, dword ptr [0x498e98]` / `@source 0x0041972c cmp byte ptr [eax + 0x18], 0` / `@source 0x00419734 mov bl, byte ptr [eax + 0x19]` / `@source 0x0041973b inc ecx` / `@source 0x0041973f mov eax, ecx` |
| `_rich4_player_has_card` | `0x004413ad` | `int f(int player, int card_id)` | 1/0 | 扫 **15** 卡槽 `0x499120 + player*15 + i`，命中返回 1 | `@source 0x004413bc cmp ecx, 0xf` / `@source 0x004413cf mov al, byte ptr [ecx + eax + 0x499120]` / `@source 0x004413db cmp eax, ebx` / `@source 0x004413df mov eax, 1` / `@source 0x004413e7 xor eax, eax` |
| `_rich4_player_card_num` | **`0x00441262`**（**不是** `0x4410a6`；`0x4410a6` 落在 `0x44101d` 函数体内部、且是 `mov eax,edx` 的末字节，**不是入口**） | `int f(int player)` | 非空卡槽数 | 数 `0x499120 + player*15 + 0..14` 中非 0 的槽 | `@source 0x00441264 mov esi, dword ptr [esp + 0xc]` / `@source 0x0044126f cmp ecx, 0xf` / `@source 0x00441282 cmp byte ptr [ecx + eax + 0x499120], 0` / `@source 0x0044128c inc ebx`；反汇编 `0x4410a2 lea edx,[ebx+0xa]` / `0x4410a5 mov eax,edx` / `0x4410a7 shl eax,2` 证实 `0x4410a6` 是指令中段 |
| `_rich4_calculate_player_wealth` | **`0x004239b9`** | `int f(int player)` | 身家 | `+0x1c`(现金)+`+0x20`(存款)−`+0x24`(贷款)，再加 12 支股票市值（表 `0x4971a0` 与价表 `0x496994`） | `@source 0x004239c7 mov edx, dword ptr [eax + 0x496b84]`(+0x1c) / `@source 0x004239cd add edx, dword ptr [eax + 0x496b88]`(+0x20) / `@source 0x004239d3 mov esi, dword ptr [eax + 0x496b8c]`(+0x24) / `@source 0x004239d9 sub edx, esi` / `@source 0x004239ec fild dword ptr [ecx + eax*8 + 0x4971a0]` / `@source 0x00423a1b cmp edx, 0xc` |
| `0x440cac` | `0x00440cac` | `int f(int a1, int a2, …)`（取 `[esp+0x34]`=第 2 实参作标志/文本指针来源） | `eax = edi` | **角色头顶浮动气泡/提示框（推断）**：以 `[0x48bdb8..0x48bdc4]` 为基准建 `0x1e0×0x28` surface，从 `[0x48bad8]+0x48` 的精灵按 `+0x4c/+0x4e` 偏移 blit，再画文字 `0x44fabc`，最后 `0x4528b9`；第 2 实参 bit31=1 时把矩形上下各扩 `0x64`(100) | `@source 0x00440cb2 mov esi, dword ptr [esp + 0x34]` / `@source 0x00440cef test esi, 0x80000000` / `@source 0x00440cfd add dword ptr [esp], 0x64` / `@source 0x00440d24 mov dword ptr [esp + 0x14], 0x28` / `@source 0x00440d2c mov dword ptr [esp + 0x18], 0x1b8` / `@source 0x00440d62 mov eax, dword ptr [0x48bad8]` / `@source 0x00440dac call 0x44fabc` / `@source 0x00440de8 call 0x4528b9` |

### 4. `_rich4_find_most_hostile_player` 精确算法（含 tie-break）

**函数存在，VA = `0x0040d2d3`**（先前按 `imm32 == 0x496bb4` 扫描只得到 6 个引用点，其中 `0x40d305` 就是本条比较指令；早期把 `0x40d2f0` 当入口看导致误判为「不存在」——`0x40d2f0` 是指令中段）。

完整实测反汇编（**本次自己跑出，与 `docs/systems/ai.md` 的转抄一致**）：

```asm
@source 0x0040d2d3   push     ebx
@source 0x0040d2d4   push     esi
@source 0x0040d2d5   push     edi
@source 0x0040d2d6   mov      esi, dword ptr [esp + 0x10]      ; esi = self（自己的座位下标）
@source 0x0040d2da   xor      eax, eax                         ; i = 0
@source 0x0040d2dc   xor      ecx, ecx                         ; best = 0
@source 0x0040d2de   mov      edi, 0xffffffff                  ; bestIdx = -1
@source 0x0040d2e3   cmp      eax, dword ptr [0x499114]        ; 上界 = 玩家数 [0x499114]
@source 0x0040d2e9   jge      0x40d316
@source 0x0040d2eb   cmp      eax, esi
@source 0x0040d2ed   je       0x40d313                         ; ★ 排除自己
@source 0x0040d2ef   imul     edx, eax, 0x68
@source 0x0040d2f2   cmp      byte ptr [edx + 0x496b7d], 0     ; ★ 排除 player+0x15 == 0（出局/未参与）
@source 0x0040d2f9   je       0x40d313
@source 0x0040d2fb   imul     edx, esi, 0x68                   ; edx = self*0x68
@source 0x0040d2fe   mov      ebx, eax
@source 0x0040d300   shl      ebx, 2                           ; ebx = i*4
@source 0x0040d303   add      edx, ebx
@source 0x0040d305   mov      ebx, dword ptr [edx + 0x496bb4]  ; ★ ebx = player[self].hostility[i]
@source 0x0040d30b   cmp      ecx, ebx                         ; ★★ best vs h
@source 0x0040d30d   jge      0x40d313                         ; ★★ jge → 只在严格大于时更新
@source 0x0040d30f   mov      ecx, ebx                         ; best = h
@source 0x0040d311   mov      edi, eax                         ; bestIdx = i
@source 0x0040d313   inc      eax
@source 0x0040d314   jmp      0x40d2e3
@source 0x0040d316   mov      eax, edi                         ; 返回 bestIdx
@source 0x0040d318   pop      edi
@source 0x0040d319   pop      esi
@source 0x0040d31a   pop      ebx
@source 0x0040d31b   ret
```

| 项 | 实测结论 |
|---|---|
| 循环上界 | `i < [0x499114]`（`@source 0x0040d2e3 cmp eax, dword ptr [0x499114]` + `jge`）——不是固定 4 |
| 被扫的敌意 | **`player[self].hostility[i]`**，即 `0x496b68 + self*0x68 + 0x4c + i*4` = `0x496bb4 + self*0x68 + i*4`（`@source 0x0040d2fb imul edx, esi, 0x68` / `@source 0x0040d305 mov ebx, dword ptr [edx + 0x496bb4]`）⇒ 是**自己对他人的敌意** |
| 是否含自己 | **排除**（`@source 0x0040d2eb cmp eax, esi` / `@source 0x0040d2ed je 0x40d313`） |
| 额外过滤 | **排除 `player[i] + 0x15 == 0`**（出局/未参与，`@source 0x0040d2f2`/`@source 0x0040d2f9`） |
| best 初值 | **0**（`@source 0x0040d2dc xor ecx, ecx`），bestIdx 初值 **-1**（`@source 0x0040d2de`） |
| 比较方向 | `cmp ecx, ebx` 后 **`jge`**（`@source 0x0040d30d`）⇒ 只有 `h > best` 才更新 |
| **tie-break** | **first-wins（下标小者胜）**：相等时 `jge` 跳过更新，因此先命中的小下标一直保持；由 `cmp ecx, ebx` + `jge` 这对指令实现（寄存器 `ecx`=best、`ebx`=h） |
| 全 0 / 无候选 | 返回 **-1**（`best=0` ⇒ `0 >= 0` 恒真 ⇒ `bestIdx` 永不更新） |

调用点（`r4scan.py 0x40d2d3` → **17** 处）：`0x41e78c, 0x41ea11, 0x41eb1e, 0x41ed6d, 0x41ef59, 0x41f1d8, 0x41f424, 0x41f919, 0x41fe9b, 0x42020b, 0x4202e5, 0x420424, 0x420652, 0x4207f4, 0x42172a, 0x4448b1, 0x44f4f7`。
其中 14 处落在 `0x41e6fe..0x421e62` 的**用卡/用道具效果函数**区间内（即 AI 选目标），与 `rich4-re/asm/rich4_ai_use_card.asm` / `rich4_ai_use_tool.asm` 的 hint 一致。
**未决**：`hostility[a][b]` 的「a 对 b / b 对 a」方向仅在 `update_hostility`（`0x40df69` 附近，见下）可确认；本函数读的是 `player[self].+0x4c+i*4`。同一数组的其它引用点实测只有 3 处：`@source 0x0040cf63 mov dword ptr [eax + edx*4 + 0x496bb4], ebp`（清零，清零者在替换玩家时被调）、`@source 0x0040dfa3 mov dword ptr [eax + 0x496bb4], edi`（累加，带 `@source 0x0040dfad xor ecx,ecx` 下限 0 钳位）。

### 5. AI 路径上的随机数调用点

`_libc_rand` = `0x00456f2d`（LCG `state = state*0x41C64E6D + 0x3039`）。全 exe 共 **183** 个 `call 0x456f2d`。**从路由 / 其调用链可达**的如下（其余在无关系统里）：

| VA | 随机用法 | 阈值 | 作用 |
|---|---|---|---|
| `0x0041e6ce` | `rand() % 3`（`idiv ecx(3)` 后取 `edx`，`test edx,edx` / `je`） | `!= 0` → 放弃 | **個性闸门**：`card_table[card].+7`（`0x47fdf1`，stride 8，基址 `0x47fdea`）减 `player+0x17`（`0x496b7f`）= 1 时，只有 1/3 概率通过；差 ≥2 直接 0；差 ≤0 走 `[eax*4 + 0x475324]` 卡效果表。**重制版已按 D-004 换成确定性替身** |
| `0x00418e18` | `rand() & 1`（`test al,1`） | 50/50 | **AI 回合主体二选一**：`0x441baa`（用卡/用道具）或 `0x447d97` |
| `0x00441d4a` | `rand() % 手牌数`（`idiv esi`，`esi`=手牌数） | 仅 `手牌数 > 8` 才掷（`@source 0x00441d45 cmp esi, 8` / `jle`，否则起点 0） | **AI 用卡**：从 8 个候选里取随机起点 |
| `0x00428ae8`（同段还有 `0x0042886e`、`0x004288fb`、`0x004289d3`、`0x00428a37`） | 5 处 `rand()` | 各段自定 | **股市 AI 决策**（路由 case 9 / 回合驱动第 ④ 步） |
| `0x0042bf14` | `rand() % 3`（`idiv ecx(3)`，`test edx,edx` / `jne` 退出） | `== 0` 才继续 | **银行 AI**（`0x42bf03`，回合驱动第 ① 步）：1/3 概率才进入后续判断 |
| `0x00447ff5` | 1 处 `rand()` | 未细读 | 路由 case 7（`0x447d97`）内部 |
| `0x00441e4a`、`0x00441e8e` | 2 处 `rand()` | 未细读 | `0x441baa` 之后紧邻的函数（`0x441e12` = 文档所称 `random_slot_of_hand`）；**不在** case 8 边界内（`0x441baa` 实长 `0x25d`） |

**重制版已替换的**：仅闸门 `0x41e6ce` 的 `rand()%3` → `aiRoll()` 确定性替身（`rich4-remake/docs/known-deviations.md:629` D-004）。其余（`0x418e18` 的 50/50、`0x441d4a`、股市 5 处、银行 `0x42bf14`、case7 的 1 处）**原版都在推进 LCG**，重制版处置状态**未决**。

### 汇编摘录

```asm
; ── 主循环 → 回合决策驱动 ────────────────────────────────────────
@source 0x00401d8d   imul     eax, dword ptr [0x49910c], 0x34
@source 0x00401d94   cmp      byte ptr [eax + 0x498ea2], 0
@source 0x00401d9b   jne      0x401db8
@source 0x00401da3   test     ch, 0x80
@source 0x00401da6   je       0x401db8
@source 0x00401dad   mov      byte ptr [eax + 0x498ea0], dl
@source 0x00401db3   call     0x418c55

; ── 相位跳表 0x418c3d（6 项：0x418d88,0x418d99,0x418dc6,0x418e7a,0x418e7a,0x418dc6）
@source 0x00418d70   call     0x40c912
@source 0x00418d78   cmp      eax, 5
@source 0x00418d7b   ja       0x418e7a
@source 0x00418d81   jmp      dword ptr [eax*4 + 0x418c3d]

; ── AI 决策块（相位 2/5）────────────────────────────────────────
@source 0x00418dc6   mov      esi, dword ptr [0x49910c]
@source 0x00418dd8   test     byte ptr [eax + 0x496b7d], 0x30
@source 0x00418de6   call     0x42bf03            ; 银行 AI
@source 0x00418dfe   call     0x436b0a
@source 0x00418e13   call     0x4284be            ; 股市 AI
@source 0x00418e18   call     0x456f2d            ; rand()
@source 0x00418e1d   test     al, 1
@source 0x00418e21   call     0x441baa            ; 用卡/道具
@source 0x00418e28   call     0x447d97

; ── 路由入口 + 跳表 ────────────────────────────────────────────
@source 0x00417d66   push     0
@source 0x00417d68   call     0x402460
@source 0x00417d70   call     0x419703
@source 0x00417d75   mov      dword ptr [0x48bde4], 0xffffffff
@source 0x00417d81   call     0x415d31
@source 0x00417d89   mov      ecx, dword ptr [esp + 8]
@source 0x00417d8d   cmp      ecx, 0xa
@source 0x00417d90   ja       0x417dff
@source 0x00417d98   jmp      dword ptr [eax*4 + 0x417d39]

; ── 两个调用点 ────────────────────────────────────────────────
@source 0x0040131f   push     0xa                 ; 键盘钩子：'W' → action 10
@source 0x00401321   call     0x417d65
@source 0x00418863   cmp      bl, 0x64            ; 工具条第 k 格 → action k
@source 0x0041886c   sub      eax, 0x64
@source 0x00418870   call     0x417d65

; ── find_most_hostile_player（tie-break = jge，first-wins）──────
@source 0x0040d2d6   mov      esi, dword ptr [esp + 0x10]
@source 0x0040d2dc   xor      ecx, ecx
@source 0x0040d2de   mov      edi, 0xffffffff
@source 0x0040d2e3   cmp      eax, dword ptr [0x499114]
@source 0x0040d2ed   je       0x40d313
@source 0x0040d2f9   je       0x40d313
@source 0x0040d305   mov      ebx, dword ptr [edx + 0x496bb4]
@source 0x0040d30b   cmp      ecx, ebx
@source 0x0040d30d   jge      0x40d313
@source 0x0040d311   mov      edi, eax
@source 0x0040d316   mov      eax, edi

; ── 個性闸门（含 D-004 的 rand()%3）───────────────────────────
@source 0x0041e6a4   mov      dl, byte ptr [eax*8 + 0x47fdf1]
@source 0x0041e6b2   mov      al, byte ptr [eax + 0x496b7f]
@source 0x0041e6bd   sub      edx, eax
@source 0x0041e6c4   jl       0x41e6c9
@source 0x0041e6ce   call     0x456f2d
@source 0x0041e6dd   idiv     ecx                 ; ecx = 3
@source 0x0041e6df   test     edx, edx
@source 0x0041e6ea   call     dword ptr [eax*4 + 0x475324]

; ── 模态循环 0x4018e7 ─────────────────────────────────────────
@source 0x004018fe   mov      dword ptr [eax*4 + 0x48a010], edx
@source 0x00401918   call     dword ptr cs:[0x462310]      ; PostMessageA
@source 0x0040192c   call     dword ptr cs:[0x46230c]      ; PeekMessageA
@source 0x0040194e   call     dword ptr cs:[0x4622e0]      ; DispatchMessageA
```

### 未决

1. **`0x40c912` 的相位判据**：只确认返回 0..5、按 `player+0x15/+0x32/+0x36/+0x37` 等字段分派；各相位对应的**游戏语义**（落地/结算/再决策）未逐条读定。
2. **case 2 / 3 / 4 / 6 的业务类别**：只确认是「`0x4018e7` 模态子画面 + 各自 surface 资源号（`0x4d` / `0x208` / `0x208`+`2` / `9`+`0x4a`）」。字符串 `0x463cd8` 不在 `gen/strings.json` 中（该处为数值数据，非串），**无法据此判定**。
3. **case 1（`0x411b53`）**：表 `0x474b3a` 的 6 字节项语义（两组坐标 + 第三字段）未读定；「地图绘制」为**推断**。
4. **`0x440cac`**：判定为「角色头顶浮动气泡/提示框（含文字）」属**推断**——已确证的是矩形来源、`0x1e0×0x28` surface、精灵偏移 `+0x4c/+0x4e`、`0x44fabc` 画字、`0x4528b9` 收尾、以及 bit31 触发 `+0x64` 外扩。**实测调用点 104 处**（`r4scan.py 0x440cac` → 104 个 `call at`；`gen/functions.json` 只记 9 处、且把 `0x440cac` 划进 `0x440ba8` 的函数体，两者皆与实际不符——`@source 0x00440ca7 jmp 0x43f212` 之后 `@source 0x00440cac push ebx` 已是新函数），**未逐个核对语义**。
5. **`hostility[a][b]` 的方向**：`0x40d2d3` 读 `player[self].+0x4c+i*4`；但 `update_hostility`（`0x40df69` 一族）的实参顺序与「谁对谁」未在调用点逐个核对。
6. **11 格工具条是否在正式版可见**：已确证点击区 `x<440 && y<40`（`@source 0x00418670` / `@source 0x00418678`）与 `x/40+100` 的编码；但「它在成品 UI 里长什么样、是否被其它绘制覆盖」未核对。
7. **`0x401010` 键盘钩子对 key-up 的处理**：实测 `0x401312`–`0x401457` 段**无** `test ebx,0x80000000` 过滤，故按下/抬起都会触发 action；是否另有全局抬起过滤（钩子只认按下）**未确认**。
8. **`0x441e4a` / `0x441e8e` 两处 `rand()`** 属 `0x441baa` 之后的函数（文档称 `0x441e12 random_slot_of_hand`），是否被 AI 用卡路径 `0x441baa` 调用**未确认**。
