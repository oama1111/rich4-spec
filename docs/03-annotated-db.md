# 机械层 · 函数注解库与全库反汇编

> 由 `tools/annotate.py` 生成。重建：`python3 tools/annotate.py build`

## 一、为什么需要它（非显然但决定性）

原版访问 Win32 API 的方式是 **IAT 间接调用**：

```asm
00401918  call  dword ptr cs:[0x462310]
```

光看这条指令**读不出任何语义** —— `0x462310` 是个数字。而同一个调用在
注解后是这样的：

```asm
00401918  call  dword ptr cs:[0x462310]   → USER32!PostMessageA
```

本工具的职责就是**把 IAT 槽解析回名字**，把函数指针表解析回 `card_functions[1]`
这类标号，并把字符串地址解析成文本。一次生成后，读任何函数
**都不必再手工查 IAT** —— 这是"查索引代替翻汇编"最直接的落地。

### ⚠️ 一个真实踩过的坑：JSON 的键是字符串

`imports.json` 里键写成 `"0x46230c"`（字符串）。若用整数
`slot in imports` 去查会**永远为 False**，于是**全部 707 处 API 调用
一个都解析不出来**，而表面上看不出任何异常（只是"注解为空"）。
`load_imports()` 现在强制把键转成 `int`。

> **推广**：凡"从 JSON 载入地址表再按整数查"的地方，都要先确认没有这个陷阱。
> 排查成本 = 一次安静的错误；发现成本 = 主动去数"应该有注解却没有"的行数。

## 二、产出

| 文件 | 内容 |
|---|---|
| `gen/db.txt` | **全库反汇编，120,521 行 / 4.5 MB**，调用点已解析为名字 |
| `gen/annotations.json` | 1,560 个函数的一行摘要（名称、类别、大小、结尾、被调/调用数） |
| `gen/imports.json` | 122 个导入函数：IAT 槽 → `DLL!函数名` |
| `gen/import-thunks.json` | 122 个导入 thunk 桩地址 → `DLL!函数名` |

### 已解析的规模

| 指标 | 数值 |
|---|---|
| 解析出的 API 调用点 | **707 处** |
| 用到的 API 种类 | **116 种** |
| 命名的函数指针表项 | **100 个** |
| 已定名的本地函数 | 24 个 |

`gen/db.txt` 里 `→` 出现即代表"已解析出名字"，可直接 grep 定位：

```bash
grep -n 'MessageBoxA' gen/db.txt           # 所有弹框点
grep -n '→ card_functions\[' gen/db.txt    # 所有卡片效果分派
python3 tools/annotate.py show 0x419744    # 单函数带注解反汇编
```

## 三、★ 由注解层得出的架构结论

### 3.1 渲染是 **`WM_PAINT` 驱动**，不是连续动画帧

| API | 调用点数 | 出现在多少个函数中 |
|---|---|---|
| `InvalidateRect` | **204** | **124** |
| `BeginPaint` | 41 | 41 |
| `EndPaint` | 41 | 41 |

`InvalidateRect` 高度分散在 **124 个函数**里，且与 `BeginPaint`/`EndPaint`
成对出现 —— 这是典型的**「标记失效 → 等 `WM_PAINT` → 重画局部」**模型。

**复刻含义**：不要按"每帧重绘整屏"设计。原版是**按需局部重绘**，
每个界面自行声明失效区域。复刻若改成整屏重绘，行为上可能看不出差别，
但会在**闪烁、遮挡顺序、以及"点哪儿都退屏"这类交互细节**上偏离。

### 3.2 节奏由定时器驱动（与 `SetTimer` 的 24 处吻合）

`SetTimer` 出现在 **21 个函数**中（`KillTimer` 23 处、`timeGetTime` 12 处），
与 `game-loop.md` 登记的"24 处 `SetTimer` 调用点"互相印证：
**游戏推进靠定时器回调，而不是主循环里的回合函数**。

### 3.3 媒体播放走 MCI 字符串接口

`mciSendStringA` 37 处，分布在 14 个函数中。
这意味着音乐/视频（AVI）是通过 **MCI 命令字符串**控制的，
复刻时若要 1:1，需对齐这些命令字符串的语义，而不是直接换成现代音频 API。

## 四、已定名的本地函数（含签名与证据）

| VA | 名称 | 签名 | 证据 |
|---|---|---|---|
| **`0x0044fabc`** | **`drawText_colorcode`** | `(hdc, text, x, y, …)` | 被调 **86 次**；用 `SelectObject`/`SetBkMode`/`SetTextCharacterExtra`/`DrawTextA`/`SetTextColor`；**解析 `#NNNN` 语音控制码**（`cmp ah,0x23` → 取 4 位十进制 → 调 `0x45441a` 播语音 → `add ebx,5` 跳过前缀）。⚠️ 本项目早期把它写成「颜色码」，**是错的**，见 `docs/systems/dialogue-voice.md` §三 |
| **`0x00450441`** | **`mkf_read_resource`** | `(index, size_out, …)` | 被调 **63 次**；`SetFilePointer` + `ReadFile` 读 16 字节目录项，再调 `0x456f80` 解压 |
| `0x00456f80` | `mkf_decompress_entry` | `(…)` | 由 `mkf_read_resource` 调用 |
| `0x0040df69` | `update_hostility` | `(a, b, int delta)` | 多处 32 位整数传参；⚠️ **不是** `0x44ef41` |
| `0x0044ef41` | `player_say` | `(player, ?, 台词表项)` | 查表取字符串指针后 push |
| `0x00458370` | `strcmp` | `(const char*, const char*)` | 实测：同串返回 0、异串返回 −1 |
| `0x00419744` | `calculate_land_toll` | `(int player_1based, const char* name)` | 见 `docs/systems/land-rent.md` |
| `0x004413ad` | `player_has_card` | `(player, card_id) -> int` | 扫 15 个卡槽（上界 0xf） |
| `0x00456f2d` | `rand15` | `() -> [0,32767]` | `state=A*state+B; (state>>16)&0x7FFF` |
| `0x00456f50` | `srand_r4` | `(uint32 seed)` | 写同一状态块 |
| `0x00456e11` | `my_free` | `(void*)` | 转发 `0x456e1f`，后者遍历 `0x4991bc` 空闲链表 |
| `0x00456f60` | `fillBytes32` | `(dst, value, n)` | 24 位字节交换后转发 `memset` |
| `0x00457110` | `sprintf_wrap` | `(buf, fmt, ...)` | 转发 `0x458db5`，后者调 `vsprintf` 后补 `\0` |
| `0x004563f5` | `blitRect` | `(x, y, w, h, surf)` | 压 `0x280`(640) / `0x1e0`(480) 后调 `0x455b3a` |
| `0x00455b3a` | `blitRect_inner` | `(x, y, w, h, surf, …)` | 按 `[esi]`/`[esi+4]`/`[esi+6]` 读矩形并裁剪 |
| `0x004018e7` | `modal_msg_pump` | `(filter_low, filter_high)` | `PeekMessageA` 忙等 + `WM_QUIT` 退出 |
| `0x004019dd` | `WndProc` | `(hwnd, msg, wParam, lParam)` | `WNDCLASS.lpfnWndProc` 处写入 |
| `0x0040d293` | `ctz` | `(x) -> 位数`，全 0 返回 −1 | 末尾 0 计数，上限 8 |
| `0x00458ae0` | `memset` | `(dst, c, n)` | `or ecx,ecx` 起手 + 4 字节展开 |

### ⚠️ 调用约定易错点（写规格时务必注意）

**`[ebp+8]` 是第一个参数。** 实测 `0x004563f5`：

```asm
004563f8  push dword ptr [ebp + 0x14]    ; 第 5 参
004563fb  push dword ptr [ebp + 0x10]    ; 第 4 参
004563fe  push dword ptr [ebp + 0xc]     ; 第 3 参
00456401  push dword ptr [ebp + 8]       ; ★ 第 1 个参数
00456404  push 0x1e0                     ; 480（硬编码，不是参数）
00456409  push 0x280                     ; 640（硬编码）
```

我曾在早期分析中漏掉 `[ebp+8]`，把实参个数算错。
**凡见 `push [ebp+0x14] / [ebp+0x10] / [ebp+0xc] / [ebp+8]` 的连排，
参数从 `ebp+8` 起数。**

## 五、★ 引擎的两大热点（按被调次数）

| 排名 | 函数 | 被调 | 语义 |
|---|---|---|---|
| 1 | `0x0044fabc` | **86** | **文本绘制**（含 `#` 颜色码解析） |
| 2 | `0x00450441` | **63** | **MKF 资源读取**（`SetFilePointer`+`ReadFile`+解压） |
| 3 | `0x00457110` | 56 | `sprintf` 包装 |
| 4 | `0x004563f5` | 54 | 矩形 blit |
| 5 | `0x00456e11` | 52 | `free` |

两条结论：

1. **所有 UI 文字都走 `drawText_colorcode`**，且支持内嵌 `#` 颜色码
   （既有文档里 `#0428讓我把它據為己有！！` 这种字符串就是它的输入格式）。
   复刻必须实现该颜色码语义，否则大量台词/提示的颜色会不对。
2. **所有素材都走 `mkf_read_resource`**。它用 `SetFilePointer`（32 位偏移）
   + `ReadFile`，说明原版只支持 <2GB 的 MKF，且资源按 16 字节目录项索引。

这两条把"渲染与素材"这条链路的入口钉死了，后续 UI/渲染规格应从这里展开。

## 六、局限

1. **180 个函数仍是 `sub_xxxxxxxx`**（`annotations.json` 里类别为 `func` 的有 1,333 个，
   其中已定名 24 个）。定名需要逐个人工研判用途。
2 . `gen/db.txt` 的字符串注解只覆盖**立即数/绝对寻址**能追到的字符串；
   经指针表间接使用的（约 6,800 条）不会出现，见 `02-strings-and-layout.md` §五。
3. 间接跳转（`call [reg+off]`、COM 虚表）静态无法解析，仍显示为原样指令。
