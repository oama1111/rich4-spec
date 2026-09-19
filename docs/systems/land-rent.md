# 地产与过路费

> 真值：`../Rich4/rich4.exe`。本文件所有 `@source` 均为原版虚拟地址。

## 一、数据结构

### 住宅用地 `housing_land`（步长 **0x34 = 52 字节**）

> ★ **神明对过路费的加减不在本文件**：付款方身上的神明会在租金算完之后
> 再调一次 `0x0041d709`（6 路跳表 `0x0041d6f1`：小財神 ÷2、大財神归零、
> 小窮神 ×1.5、大窮神 ×2、**福神无影响**），三个调用点都在本文件的租金分支内
> （`0x419d70`／`0x41a58a`／`0x41aec5`，第一参一律取付款方 `[0x49910c]`）。
> 完整规格见 `gods.md` §6b。

@source `VA 0x00419744` 的循环步长与字段访问；指针与计数见该函数的全局引用。

基址在全局指针 `0x498e84`（`land_info_ptr`），项数在 `0x498e98`（`num_lands`）。
**数组从下标 1 开始使用**（见下方循环从 `esi = 1` 起）。

| 偏移 | 类型 | 字段 | 可靠性 |
|---|---|---|---|
| `0x04` | char[] | `name`（土地名，Big5 字符串） | A |
| `0x17` | uint8 | `price_status` | B（命名待确认） |
| `0x18` | uint8 | `type`：**0 = 住宅，非 0 = 商業用地** | A |
| `0x19` | uint8 | `owner`（**0 = 无主；否则为玩家下标 + 1**，即 **1 基**） | A |
| `0x1a` | uint8 | `level`（等级，直接用作租金表下标） | A |
| `0x1c` | uint16 | `land_price`（地价） | A |
| `0x1e` | uint16 | `house_price`（房价） | A |
| **`0x20`** | uint16×6 | **按等级租金表** | A |
| `0x30` | uint32 | `flast`（地契到期日，见既有文档） | B |

@source `VA 0x00419a67`、`0x00420d25`；实测见文末表。

### ⚠️ `owner` 是 **1 基**（0 = 无主，N = 玩家下标 N−1）

这一点极易写错，且写错会让"过路费能否收到"完全颠倒，故单列取证。

**证据 1 —— 同一函数内两条分支必须同编码**（`calculate_land_toll` 的调用方
`VA 0x00419a67`）：

```asm
00419abc  lea  eax, [esi + 4]              ; 土地名
00419abf  push eax
00419ac0  xor  eax, eax
00419ac2  mov  al, byte ptr [esi + 0x19]   ; ★ 直接用 owner 字节当玩家号
00419ac5  push eax
00419ac6  call 0x419744                    ;   分支一：住宅分支
    …
00419af0  push 0
00419af2  mov  ecx, dword ptr [esp + 0xe8] ; ★ 另一条分支传的是玩家字段
00419af9  push ecx
00419afa  call 0x419744                    ;   分支二
```

两条分支对**同一个形参**必须传同一编码，因此该玩家字段与 `owner` 同为 1 基。

**证据 2 —— "是不是自己的"用 `owner == 当前 + 1`**（多个调用点，如 `0x00420d28`）：

```asm
00420d25  mov  al, byte ptr [esi + 0x19]   ; owner（1 基）
00420d28  mov  edx, dword ptr [0x49910c]   ; 当前玩家（★ 0 基）
00420d2e  inc  edx                         ; 0 基 → 1 基
00420d2f  cmp  eax, edx                    ; ★ owner == 当前玩家0基 + 1
```

### ⚠️ 两种编码必须分清（本文件早期版本在此写错过）

| 量 | 编码 | 证据 |
|---|---|---|
| `land.owner`（`+0x19`） | **1 基**（0=无主） | 卡 3 寫入時 `mov al,[0x49910c]; inc al; mov [ebx+0x19],al` |
| `0x49910c`（当前玩家） | **0 基** | `VA 0x004082f4`：`imul eax, dword ptr [0x49910c], 0x68` —— **直接**用玩家数组的 `0x68` 步长索引 |

本文件早期版本曾写「`0x49910c` 是 1 基的当前玩家」，**这是错的** ——
`owner == [0x49910c] + 1` 恰恰说明 `0x49910c` 是 **0 基**。
（该错误由卡片系统规格的独立复核发现，我按其给出的 `0x4082f4` 复核后确认。）

**实践含义**：`calculate_land_toll` 的第 1 参要求 **1 基**（与 `owner` 同编码），
而**大多数调用点是直接把 `owner` 字节传进去**（见 §二），
不能把 `0x49910c` 直接传给它 —— 需 `+1`。

**证据 3 —— 实测**（`tools/emulate.py` 执行原版机器码）：

| `land.owner` | 第 1 参 = 0 | 第 1 参 = 1 | 第 1 参 = 2 |
|---|---|---|---|
| `0` | **200**（匹配） | 0 | 0 |
| `1` | 0 | **200**（匹配） | 0 |

即函数内部是**直接相等比较**，不做任何 ±1 调整。

**推论**：**玩家不能对自己的地产收过路费**。同主分支传的是
`owner` 本身（= 该玩家 + 1），与当前玩家相等，于是算出"自己的过路费"，
调用方据此判定为无过路费。这是原版设计，不是 bug。

### ⚠️ `0x20` 的按等级租金表

@source `VA 0x00419796`（`mov ax, word ptr [ebx + eax*2 + 0x20]`）。

这是**过路费公式的核心**，且上游 `rich4-re/csrc/land.h` **漏掉了这个字段**
（该错误已记入既有审计）。本规格以 exe 为准：

```asm
00419793  mov   al, byte ptr [ebx + 0x1a]      ; level
00419796  mov   ax, word ptr [ebx + eax*2 + 0x20]  ; ★ 租金表[level]
0041979b  and   eax, 0xffff
004197a0  add   edi, eax
```

结论：**表项为 6 项 uint16（`level` 取值 0..5），紧邻 `house_price` 之后**，
占用 `0x20..0x2b`。

> ⚠️ **修正（本文件早期版本的错误）**：早期版本在这里写「`0x20` 之后到 `0x30`
> 之间没有别的字段」。**这是错的。** `+0x2c` 是一个真实存在的 4 字节字段：
>
> ```asm
> 00447553  mov  dword ptr [eax + 0x2c], 0   ; ★ 傳送機清空地块时清零 +0x2c
> ```
> @source `VA 0x00447553`（傳送機 `0x00447428` 的搬移逻辑内）。
> 即字段布局是：`0x20`–`0x2b` 租金表（6×uint16）、**`0x2c`–`0x2f` 一个 dword**、
> `0x30`–`0x33` `flast`。**`0x2c` 的语义未决**（傳送機在移走地块时把它清零，
> 说明它随归属/等级变化；疑与「上次过路费」或某种计数有关）。

## 二、`calculate_land_toll`（`VA 0x00419744`，57 条指令）

### 签名

@source 参数布局见 `VA 0x00419748`（`mov ebp,[esp+0x14]`）与 `0x0041974e`（取 `[esp+0x18]`）。

```
int calculate_land_toll(int player_1based, const char *land_name)
    [esp+0x14] = player_1based ; 经 ebp 传递；**1 基**，与 land.owner 同编码
    [esp+0x18] = land_name     ; 可为 NULL
```

⚠️ **参数编码**：第 1 参必须与 `land.owner` **同编码（1 基）**。
传 0 基下标会导致**永远匹配不上、过路费恒为 0**（实测见 §一）。

被调用 **13 处**（`0x41790a, 0x420a31, 0x420ce4, 0x420f92, 0x4212fe, 0x4225a3,
0x4226df, 0x422a15, 0x422d51, 0x424aea, 0x424c64, 0x424f61` 等）。
调用 `0x458370`（**`strcmp`**，已复核）。

算法分**两个互斥分支**，由第二个参数是否为 `NULL` 决定：

### 分支 A：`land_name != NULL` —— 按**同名地产**累加等级租金

@source `VA 0x0041974e`（判空）- `0x004197a3`（回边）。

```asm
0041974e  cmp   dword ptr [esp + 0x18], 0
00419753  je    0x4197a5                 ; 为 NULL → 跳分支 B
00419755  mov   esi, 1                   ; ★ 下标从 1 起
0041975a  mov   ebx, [0x498e84]          ; land_info_ptr
00419760  add   ebx, 0x34                ; 每次先加到第 esi 项
00419763  cmp   esi, [0x498e98]          ; num_lands
00419769  jg    0x4197d8                 ; 越界 → 收尾
0041976f  cmp   byte ptr [ebx + 0x18], 0
00419773  jne   0x4197a2                 ; ★ type != 0（商業用地）→ 跳过
00419775  xor   eax, eax
00419777  mov   al, byte ptr [ebx + 0x19]  ; owner
0041977a  cmp   eax, ebp
0041977c  jne   0x4197a2                 ; ★ 非本玩家 → 跳过
0041977e  push  [esp + 0x18]             ; land_name
00419783  lea   eax, [ebx + 4]           ; &land.name
00419786  push  eax
00419787  call  0x458370                 ; strcmp
0041978c  add   esp, 8
0041978f  test  eax, eax
00419791  jne   0x4197a2                 ; ★ 名字不同 → 跳过
00419793  mov   al, byte ptr [ebx + 0x1a]
00419796  mov   ax, word ptr [ebx + eax*2 + 0x20]  ; 租金表[level]
0041979b  and   eax, 0xffff
004197a0  add   edi, eax
004197a2  inc   esi
004197a3  jmp   0x419760
```

**四个判定必须全部成立才累加**，顺序固定（顺序会影响 `strcmp` 的调用次数，
从而影响**性能与副作用**，但不影响结果值）：

1. `type == 0`（住宅）
2. `owner == player`
3. `strcmp(land.name, land_name) == 0`
4. 累加 `租金表[level]`（`uint16`，零扩展）

> **语义解读**：传入土地名而非下标，意味着它会累加**所有同名**且属于该玩家的
> 地产。同名多块地产（地图数据结构允许）会被**一并计入**。

### 分支 B：`land_name == NULL` —— 固定值 2000 / 塊

@source `VA 0x004197a5` - `0x004197d6`。

```asm
004197a5  mov   esi, 1
004197aa  mov   ebx, [0x498e84]
004197b0  add   ebx, 0x34
004197b3  mov   ecx, [0x498e98]         ; num_lands（提到循环外，优化）
004197b9  cmp   esi, ecx
004197bb  jg    0x4197d8
004197c1  cmp   byte ptr [ebx + 0x18], 0
004197c1  je    0x4197d2                ; ★ type == 0（住宅）→ 跳过
004197c3  mov   al, byte ptr [ebx + 0x19]
004197c8  cmp   eax, ebp
004197ca  jne   0x4197d2                ; 非本玩家 → 跳过
004197cc  add   edi, 0x7d0               ; ★ 0x7d0 = 2000
004197d2  inc   esi
004197d3  add   ebx, 0x34
004197d6  jmp   0x4197b9
```

**注意判定与分支 A 相反**：这里要求 `type != 0`，即**商業用地**，
且**不比较名字**。每块累加固定 **2000**。

> 两分支构成互补：分支 A 管**住宅**（按等级租金、需同名），
> 分支 B 管**商業用地**（固定 2000、不查名）。

### 收尾：乘物价指数

```asm
004197d8  mov   ecx, [0x4990e8]   ; price_index
004197de  mov   eax, edi
004197e0  imul  eax, ecx          ; ★ 有符号乘法
004197e3  pop   ebp / edi / esi / ebx
004197e7  ret
```

**返回值为 32 位有符号乘积**（`imul`）。`price_index` 位于 `0x4990e8`。

### 完整公式

```
toll = price_index * Σ ( 每块符合条件的地产的基准值 )

住宅（type == 0）   基准值 = 租金表[level]         条件：owner == player 且 strcmp(name) == 0
商業用地（type != 0）基准值 = 2000                  条件：owner == player
```

当 `land_name != NULL` 时只算住宅；当为 `NULL` 时只算商業用地。
**两个分支不会同时生效**，因此不存在相加。

## 三、边界情况

| 情况 | 行为 | @source |
|---|---|---|
| `num_lands == 0` | 循环体不执行，`edi = 0`，返回 0 | `0x419769` / `0x4197bb` |
| 同名地产有 N 块 | **N 块全部累加**（不取其一） | 循环无 break |
| 同名的他人地产 | 跳过 | `0x41977c` |
| **自己的地产** | 若第 1 参传的是自己的 `owner` 值，会算出非 0 值；调用方据此判定为「无过路费」 | `0x00419a67` 的分支结构 |
| `level > 5` | **越界读** `0x20 + level*2`（原始代码**不校验**） | `0x419796` 无上界检查 |
| `price_index` 为大值 | `imul` 可能溢出，按 32 位补码回绕 | `0x4197e0` |

> ⚠️ `level > 5` 越界读是**原版行为**。复刻时若要 1:1，需保留该读取的
> 内存语义或至少保证不崩；**不要**擅自加 clamp。此处标为**未决**：
> 原版在该情况下读到的是 `flast` 区域的值，需实机确认是否有可达路径。

## 四、待确认（明确写「未知」）

1. `price_status`（`0x17`）的**语义与写入者**未知——本函数不使用它。
   待用 `gen/xrefs.json` 反查 `0x463000+` 对应地址的写入者。
2. `0x7d0 = 2000` 是否为**所有**商業用地的统一值，或与地块种类相关：
   本函数中它是立即数，**与地块数据无关**，故为统一值。
3. 调用方在 13 处传入的 `land_name` 来源未逐一追查；分支 B（`NULL`）
   的实际触发场景未确认。

---

## 五、⚠️ 重要澄清：两种「地块表」其实是**同一块内存**

> **本节已改写**：原文把「地图文件内的 `land_table`」与「运行时 `housing_land`」
> 当成两种结构，并把地图格式**外包**给了复刻工程的文档
> （`../../rich4-remake/docs/map-format.md`）。经 exe 复核，那是**同一个数组**：
> 装载时 `0x498e84` 直接指向地图缓冲内部的 `land` 表。
> 地图格式的权威规格现在是 **`docs/systems/map-format.md`**。

@source `VA 0x00407c61`（装载时把 `0x498e84` 指进地图缓冲）

```asm
00407c61  mov   edx, dword ptr [eax + 0xc]   ; land_table_offset
00407c67  mov   dword ptr [0x498e84], ebx    ; ebx = 地图缓冲基址 + 该偏移
```

同一段汇编的 `VA 0x00407c76` / `VA 0x00407c7c` 用
`facility_table_offset`（头 `+0x14`）给 `0x498e88` 赋值，所以
`cards.md` 的 `business_land` 就是地图文件里的 `facility` 表。

| 名称 | = 地图文件里的哪张表 | 步长 | 名字在哪 | 权威规格 |
|---|---|---|---|---|
| 运行时 `housing_land`（`0x498e84`） | `land` | **0x34 (52)** | 内嵌于 `+0x04` | ✅ 本文 §一 + `map-format.md` §4.2 |
| 运行时 `business_land`（`0x498e88`） | `facility` | **0x38 (56)** | 内嵌于 `+0x04` | ✅ `map-format.md` §4.3 |
| 地图节点表 `node`（`0x498e80`） | `node` | **0x28 (40)** | 内嵌于 `+0x04`（Big5，NUL 结尾，结构上限 20 字节） | ✅ `map-format.md` §4.1 |
| 上市企业表（`0x498e7c`） | `commercial` | **0x34 (52)** | 内嵌于 `+0x04` | ✅ `map-format.md` §4.4 |
| 特殊景观表（`0x498e78`） | `landscape` | **0x1c (28)** | 内嵌于 `+0x04` | ✅ `map-format.md` §4.5 |

**索引基点**：五张表都是 **1 基**，每表在文件里多带一个全 0 的哨兵项 0
（`num_lands == 0` 的 gm=7 也在文件里占 1 项）。详见 `map-format.md` §三。

**字段是「文件烘焙」还是「运行期」**：`land.owner(+0x19)` / `land.level(+0x1a)` /
`land.type(+0x18)` / `land+0x17` 在**地图文件里恒为 0**（389/389 项，8 张图实测），
属于运行期字段；`+0x1c` 地价、`+0x1e` 房价、`+0x20..0x2b` 租金表是地图烘焙的。
逐字段实测值域见 `map-format.md` §4.6。

@source `VA 0x00407c3f`、`VA 0x00407cac`（头部与 `map_data_size`）、`VA 0x004090ed`（land 步长）

### 商業用地 `business_land`（步长 `0x38`）—— 字段布局见 `map-format.md` §4.3

@source `VA 0x00407c76`（`facility` 表步长与基址的独立复核，见 `map-format.md` §4.3）

`cards.md` 的「購地卡」一节从 `VA 0x004424d4` 反汇编出商業用地的记录步长：

```asm
004424d9  shl   eax, 3
004424dc  mov   edx, eax
004424de  shl   eax, 3
004424e1  sub   eax, edx        ; eax = idx * 56 = 0x38
004424e3  mov   ebx, [0x498e88]  ; 商業用地数组基址
```

并给出订价公式 `price = (level * w[+0x24] + w[+0x22]) * price_index`
与 `flast @ +0x34`（**注意与住宅的 `+0x30` 不同**）。

> **注意（已复核）**：`business_land` = 地图文件的 `facility` 表，其字段布局
> **与住宅不同义**——例如 `facility+0x1c` 是**字节**（一个高 4 位倒计数，
> `VA 0x004456cf` / `VA 0x0041d160`），而 `land+0x1c` 是 uint16 地价。
> 完整字段表与未决项见 `docs/systems/map-format.md` §4.3 与 §八。
