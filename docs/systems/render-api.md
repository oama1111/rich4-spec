# 渲染 / 音频 / 输入 / 文件：对外 API 全图

> @source 全部由 `tools/annotate.py` 从 `../Rich4/rich4.exe` 的导入表与调用点机械提取，
> 可复核：`grep -n '<API名>' gen/db.txt`。

## 一、总览：122 个导入函数，707 个调用点

| DLL | 种类 | 调用点 | 主要用途 |
|---|---|---|---|
| `USER32` | 30 | **490** | 窗口/消息/定时器/鼠标 —— 游戏的主干 |
| `KERNEL32` | 57 | 99 | 文件、TLS、控制台、异常（**多数是 CRT 样板**） |
| `WINMM` | 12 | 75 | MCI 媒体播放、计时、音量 |
| `GDI32` | 15 | 39 | **矢量绘图与文字**（不是位图主体） |
| `DDRAW` | 1 | 2 | DirectDraw 初始化 |
| `DSOUND` | 1 | 2 | DirectSound 初始化 |

**关键判断**：`USER32` 占 490/707 = **69%** 的调用点，而 `DDRAW` 只有 2 处。
这说明原版**不是**一个"DirectDraw 重渲染"的程序，而是
**Win32 消息驱动 + 局部重绘 + 少量 DirectDraw 表面 blit** 的结构。

## 二、★ 渲染架构（三条链路，务必区分）

### 链路 1：位图 blit —— 走 **COM 虚表**，静态不可解析

DirectDraw 接口指针存放在 `.bss`：

| 全局 | 推断身份 | 证据 |
|---|---|---|
| `0x48a0d8` | `LPDIRECTDRAW` | `DirectDrawCreate(NULL, &0x48a0d8, NULL)` @ `0x4015f8` |
| `0x48a0dc` | 表面 A | `mov eax,[0x48a0dc]` 后直接取虚表调用 |
| `0x48a0e0` | 表面 B | 同上 |
| `0x48a0e4` | **`data.mkf` 文件句柄** | 由启动装载序列确证（`VA 0x0040172e`）；**82 处** `read_mkf` 用它，是全工程最大的资源来源 |
| `0x48a05c` | **`panel.mkf` 文件句柄** | `VA 0x00401752`；**71 处** `read_mkf`（界面面板/按钮图素） |
| `0x48a054` | **`speaking.mkf` 文件句柄** | `VA 0x00401740`；**1 处**（`play_speech`） |
| `0x48a058` | **`effect.mkf` 文件句柄** | `VA 0x00401764`；**4 处**（音效集载入） |

实测最热的两个虚表偏移：

| 偏移 | 调用次数 | 前置 push 数 | 说明 |
|---|---|---|---|
| **`0x80`** | **294** | 2 | 见下 |
| **`0x64`** | **290** | 5 | 见下 |
| `0x1c` | 116 | 6 | — |
| `0x6c` | 2 | 1 | `WM_ACTIVATEAPP` 里恢复表面 |

典型形态（`0x40158c`）：

```asm
0040158c  mov  eax, dword ptr [0x48a0e0]   ; 表面指针
00401591  mov  edx, dword ptr [eax]        ; ★ 虚表
00401593  push 0
00401595  push eax                          ; this（也作为参数压栈）
00401596  call dword ptr [edx + 0x80]
```

> ⚠️ **未决（诚实标注）**：`0x64` 与 `0x80` 的**具体方法名未确认**。
> 我尝试过的判定手段与结果：
> - 统计前置 `push` 数 → `0x80` 稳定 2 个、`0x64` 稳定 5 个（已实测）；
> - 查本机 `ddraw.h` 比对 vtable 顺序 → **本机无 DirectX SDK 头文件**，无法比对。
>
> 按 DirectX 7 的 `IDirectDrawSurface7` vtable 顺序粗推，`0x64` 附近像
> `Blt`/`BltFast` 一类（5 参，含 `DDBLTFX`），`0x80` 附近像其他表面方法，
> **但这属于推测，不作为规格结论**。要定论应查 DirectX 7 SDK 头文件
> 或动态跟踪（Frida/调试器）观测实际行为。

### 链路 1之二、★ MKF 记录表：**12 字节表头 + 12 字节/项**（第 74 条新增）

`read_mkf(...)` 返回的不是裸像素，而是一张**记录表**；各屏把它的地址存进自己的全局，
之后一律用 `表基址 + 0xc + 12×图号` 取第「图号」项。

```asm
; 装载（例：资产表屏，资源 9）
004244a1  call 0x450441            ; mkf_read_resource([0x48a05c], 9, 0, 0)
004244a9  mov  dword ptr [0x48c270], eax

; 取第 k 项（例：月结屏头像，k = 3×角色 + 47）
0043883a  mov  edx, dword ptr [0x48c41c]
0043886a  add edx, 0xc              ; ★ 跳过 12 字节表头
0043886d  add edx, ecx              ; ecx = 12×k
00438877  call 0x456418             ; 带透明 blit(dst, 记录地址, x, y)
```

**项内布局**（由 `0x4387f9` 的同一段代码定死）：

| 项内偏移 | 类型 | 含义 | 证据 |
|---|---|---|---|
| `+0` | dword | **像素数据指针**（blit 的第 2 个参数）| `0x43886a` 起 `edx = base+0xc+12k` 直接 `push edx` |
| `+2` | word | **高度** | `0x438848 sub di, word [eax+0xe]`（`eax = base+12k` ⇒ 项内 `+2`）|
| `+6` | word | **y 偏移**（配 `0x14a = 330` 算落点）| `0x43884c add di, word [eax+0x12]`（项内 `+6`）|

各屏把**同一个图号**同时用在「画」与「算落点」上，所以这套偏移是全工程通用的。

**已确认的三张表**（都是这一种构型）：

| 全局 | 来源 | 用途 | 证据 |
|---|---|---|---|
| `0x48c41c` | `mkf_read_resource(panel, 25)` | 月结/頒獎屏的头像与竖栏（图号 `3×角色+47`、`15..18`）| `0x439c26`（写）+ `0x4387f9`（读）|
| `0x48c270` | `mkf_read_resource(panel, 9)` | 資產表屏（图 0/1/2 底图、3/4 页签、5/6 EXIT、**7/8 翻页箭头**、12 下钻钮底、13..24 神明图标）| `0x4244a9`（写）+ `0x423fa5`（读 `+0x60` = 图 7）|
| `0x48c398` | `mkf_read_resource(panel, 0x12 = 18)` | 魔法屋屏的视觉（`+0xc`/`+0x18`/`+0x30`/`+0x6c` = 图 0/1/**3**/8，与 `magic-screen.ts` 的 `MAGIC_CHUNK` 编号一致）| `0x43384a` / `0x433a22`（写，均 `push 0x12`）+ `0x43252b`（读 `+0xc`）|

★ **用法上的推论**（本轮据此订正了两处 remake 注释）：

1. **`+0x18` 是「图 1」，不是「图 2/图 7」** —— 资产表屏那两处「抬手还原」
   （`0x42424e` / `0x4242cd`）拷的是 `+0x18` = 图 1 = **地產清單底图**，
   在箭头自身的坐标上取 30×30 贴回去；真正画「按下态」图 7/8 的是
   `0x423fa5`（`+0x60`）/ `0x424000`（`+0x6c`）。
2. **`0xf0` 是「图 19」** —— `0xf0 = 0xc + 12×19`。月结屏那一笔 80×40 的位移
   取自图 19（实测 `Panel/0025_019.png` = **186×410**），**不是**图 29（60×25）。

`@source` `VA 0x450441`、`VA 0x48c41c`、`VA 0x48c270`、`VA 0x48c398`、`VA 0x48a05c`、
`VA 0x439c26`、`VA 0x4387f9`、`VA 0x438848`、`VA 0x43884c`、`VA 0x43886a`、
`VA 0x4244a9`、`VA 0x423fa5`、`VA 0x424000`、`VA 0x42424e`、`VA 0x4242cd`、
`VA 0x43252b`、`VA 0x432998`、`VA 0x43384a`、`VA 0x433a22`、`VA 0x456418`。

### 链路 2：矢量图与文字 —— 走 **GDI**，且高度集中

GDI 调用只有 39 处，且**几乎全部集中在单个函数 `0x42a2a6`**：

| API | 次数 | 函数数 |
|---|---|---|
| `SelectObject` | 7 | 2 |
| `MoveToEx` / `LineTo` | 各 4 | 1 |
| `CreateSolidBrush` / `Ellipse` | 各 4 | 1 |
| `CreatePen` / `Pie` | 各 2 | 1 |
| `FloodFill` | 1 | 1 |

**含义**：`0x42a2a6` 是**唯一的矢量绘制函数**（画线/圆/饼/填充），
很可能是「小地图」「图表」「指针」这类**非位图**元素的绘制入口。
复刻时它可以直接用现代 2D API 等价实现，风险低。

文字链路独立：

| API | 次数 | 所在函数 | 说明 |
|---|---|---|---|
| `DrawTextA` | 6 | **`0x44fabc` 一个函数** | 全部文本都经此 |
| `SetTextColor` | 3 | `0x44fabc` | 颜色来自**全局**（如 `0x4762e4`），**不是** `#NNNN` |
| `SetBkMode` / `SetTextCharacterExtra` | 各 1 | `0x44fabc` | |
| `TextOutA` | 2 | `0x44f7c7` | 另一条文字路径 |
| `CreateFontA` | 1 | `0x44f9d8` | 字体创建 |
| `DeleteObject` | 2 | `0x44f9b3` 等 | 释放 GDI 对象 |

### 链路 3：界面刷新 —— `WM_PAINT` 驱动

| API | 次数 | 函数数 |
|---|---|---|
| **`InvalidateRect`** | **204** | **124** |
| `BeginPaint` / `EndPaint` | 各 41 | 各 41 |
| `ValidateRect` | 7 | 7 |

**204 处失效标记分散在 124 个函数**，每个界面自行声明重绘区域。
复刻若改成整屏重绘，会在闪烁、遮挡顺序、以及"点哪儿都退屏"这类
交互细节上偏离（详见 `03-annotated-db.md` §3.1）。

## 三、消息与定时器

| API | 次数 | 函数数 | 说明 |
|---|---|---|---|
| `PostMessageA` | 53 | 45 | 自定义消息投递（含消息泵唤醒） |
| `DefWindowProcA` | 42 | 42 | |
| `SetTimer` / `KillTimer` | 22 / 23 | 21 / 20 | **游戏节奏来源**（见 `game-loop.md`） |
| `PeekMessageA` | 8 | 8 | 含内嵌模态泵 `0x4018e7` |
| `TranslateMessage` / `DispatchMessageA` | 各 2 | 各 2 | |
| `MessageBoxA` | 8 | 3 | 含 `DirectDraw Initial Error!` |
| `SetWindowsHookExA` / `UnhookWindowsHookEx` | 1 / 1 | — | 全局钩子，用途待查 |

## 四、音频

| API | 次数 | 说明 |
|---|---|---|
| **`mciSendStringA`** | **37** | 音乐与 AVI 的播放控制（MCI 命令字符串） |
| `timeGetTime` | 24 | 毫秒级计时 |
| `mciGetDeviceIDA` | 3 | |
| `midiOutSetVolume` / `auxSetVolume` | 各 2 | 音量 |
| `midiOutGetVolume` / `midiOutGetDevCapsA` / `auxGetVolume` / `auxGetNumDevs` / `auxGetDevCapsA` | 各 1 | 设备枚举与查询 |
| `timeSetEvent` / `timeKillEvent` | 1 / 1 | 多媒体定时器 |
| `DirectSoundCreate` | 2 | |

**含义**：MIDI/音频**不是自己合成**，而是交给 MCI。
复刻要 1:1，需对齐 MCI 命令字符串的语义（而不是直接换现代音频 API），
否则播放时机、循环、音量控制会偏离。

## 五、输入

| API | 次数 | 说明 |
|---|---|---|
| `GetCursorPos` | 7 | 鼠标位置（**用 Win32，不是 DirectInput**） |
| `SetCursorPos` | 7 | 用于把光标吸到格子中心等 |
| `ShowCursor` | 2 | |
| `SetFocus` | 1 | |
| `SetWindowsHookExA` | 1 | 可能是键盘钩子（见 `rich4_keyboard_hook.asm`） |
| `ReadConsoleInputA` / `GetConsoleMode` | 1 / 1 | **CRT 样板**，与游戏无关 |

**注意**：没有 `DirectInputCreate` —— 输入全部走 Win32 消息 + `GetCursorPos`。
这简化了复刻。

## 六、文件

| API | 次数 | 说明 |
|---|---|---|
| `CreateFileA` / `ReadFile` | 6 / 6 | MKF 与存档读取 |
| `SetFilePointer` | 5 | **32 位偏移** → 原版不支持 >2GB 的 MKF |
| `CloseHandle` | 4 | |
| `WriteFile` | 3 | 存档写入 |
| `GetDriveTypeA` | 1 | `0x45011a`，**光盘检测**（"找不到光碟機！"） |
| `GetFileSize` / `GetFileAttributesA` | 各 1 | |
| `MoveFileA` / `DeleteFileA` | 各 1 | 存档重命名/删除 |

## 七、CRT 样板（**复刻时不需要实现**）

`KERNEL32` 的 99 个调用点里，绝大多数来自 Watcom/msvcrt 运行时：

- TLS：`TlsAlloc` / `TlsGetValue` / `TlsSetValue` / `TlsFree` / `GetCurrentThreadId`
- 临界区：`InitializeCriticalSection` / `EnterCriticalSection` / `LeaveCriticalSection` / `DeleteCriticalSection`
- 控制台：`GetStdHandle` / `SetStdHandle` / `WriteConsoleA` / `ReadConsoleInputA` / `GetConsoleMode` / `SetConsoleMode` / `SetConsoleCtrlHandler`
- 异常：`UnhandledExceptionFilter` / `SetUnhandledExceptionFilter`
- 代码页：`GetACP` / `GetOEMCP` / `GetCPInfo` / `MultiByteToWideChar` / `WideCharToMultiByte`
- 进程：`ExitProcess` / `GetModuleFileNameA` / `GetCommandLineA` / `GetEnvironmentStrings`
- 动态加载：`LoadLibraryA` / `GetProcAddress`（1 处，用途待查）

**这些在复刻里应当直接消失**，不是"要移植的行为"。
把它们列出来是为了避免后人误以为原版有对应的功能。

## 八、复刻优先级建议（据本图）

| 优先级 | 链路 | 理由 |
|---|---|---|
| **P0** | `drawText_colorcode`（`0x44fabc`） | 所有文字的唯一入口，含 `#NNNN` **语音控制码**（⚠️ 不是颜色码，见 `dialogue-voice.md` §三） |
| **P0** | `mkf_read_resource`（`0x450441`） | 所有素材的唯一入口 |
| **P0** | `WM_PAINT` 局部重绘模型 | 影响交互细节，最易被"现代化"改错 |
| **P1** | COM 表面 blit（`0x64` / `0x80`） | 位图主体；**方法名待定** |
| **P1** | MCI 命令字符串 | 音频/视频时机 |
| **P2** | GDI 矢量绘制（`0x42a2a6`） | 集中、可等价替换、风险低 |
| — | CRT 样板 | **不需要实现** |
