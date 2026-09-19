# 地图数据格式（`MAP.MKF` 地图结构数据）

> 真值：`../Rich4/rich4.exe`（大富翁4 v3.11，602,112 字节）。本文件每条结论都带
> `@source 0xADDR` 与汇编原文。
>
> **本文件为什么存在**：在此之前，"地图数据格式"这一节被**外包**给了复刻工程的
> `rich4-remake/docs/map-format.md`（见 `land-rent.md` §五 的旧写法）。而 `rich4-re/`
> 的汇编转写已知有 8+ 处实质错误，不能充当权威。本文件从 `rich4.exe` 机器码重建
> 格式，并**逐条校验**那份复刻文档（见 §七 勘误清单）。
>
> **证据分级**（全文通用）：
> `A` = 机器码直接读出（有 `@source` + 汇编），`B` = 机器码 + 数据双重印证但命名待定，
> `C` = 只有数据统计（佐证），`未决` = 不知道，**不用推测填充**。
>
> 全文入口函数：`0x00407ad2`（装载）、`0x00407c3f`（头解析）、`0x0040af12`（类型分派）。

---

## 零、范围

覆盖：地图资源的**定位方式**（`global_map_id` → `MAP.MKF` 资源号）、地图结构数据的
**40 字节头**、**五张表**（`node` / `land` / `facility` / `commercial` / `landscape`）
的步长与字段、`map_data_size` 的算法、加载/存档流程里各全局指针怎么被设置。

不覆盖：GND 地形图块的像素格式（另有专文机会）、SMP/SPR 精灵库的像素编码
（本文只用到它的**元数据区**，且已发现既有解包文件在此不可信，见 §六）。

`gen/db.txt` 是带注解的全量反汇编。**注意两处注解不可当真**：

- `0x456f80` 被注解为 `mkf_decompress_entry`，但从调用点看它是 **`malloc`**
  （`0x407d12` 申请 `map_data_size` 后，`0x407d2f` 立刻 `memset(...,0,size)`）。
- `0x4502fe` / `0x450404` 无注解名；本文按调用约定称之为 **`mkf_open` / `mkf_close`**
  （命名是本文自拟，**行为**有汇编为证：`0x4502fe` 失败返回 `-1`，见 `0x407be0`）。

@source `0x00407d12`、`0x00407d2f`、`0x004502fe`

---

## 一、地图资源定位

### 1.1 `global_map_id` 公式

@source `0x00407aec`（`MAP.MKF` 里 GND 图块集的资源号）

```asm
00407aec  push     0
00407aee  push     0
00407af0  movsx    edx, word ptr [0x4991b6]     ; ← 高半部
00407af7  shl      edx, 2                        ;   ×4
00407afa  movsx    eax, word ptr [0x4991b8]     ; ← 低半部
00407b01  add      eax, edx                      ;   global_map_id = hi*4 + lo
00407b03  add      eax, eax                      ;   ×2  → GND 资源号
00407b07  call     0x450441   → mkf_read_resource
00407b0f  mov      dword ptr [0x474945], eax
```

**结论（A）**：`global_map_id = [0x4991b6] * 4 + [0x4991b8]`，取值 **0..7**。
同一公式在 exe 里至少出现 8 次，是地图系统的统一入口：

| 出现点 | 用途 |
|---|---|
| `0x00407af0` | `MAP.MKF[gm*2]` = GND 图块集 |
| `0x00407b18` | `MAP.MKF[gm+0x10]` → `0x48badc` |
| `0x00407b41` | `MAP.MKF[gm+0x10]` → `0x48bad0`（**同一资源读了两遍**） |
| `0x00407be9` | `MAPDAT.MKF[gm]`（优先路径，见 §1.2） |
| `0x00407c1a` | `MAP.MKF[gm*2+1]`（回退路径） |
| `0x00407e11` | `MAP.MKF[0x27 + gm*5 + i]` |
| `0x00402c70` | 存档里逐玩家地图缓冲的基址计算 |
| `0x00429ebb`、`0x00416baf`、`0x00433f8d` | UI / 报表 |

**`0x4991b6` / `0x4991b8` 的命名是线索（B）**：exe 里 `[0x4991b6] ∈ {0,1}`
（`0x401c95` 置 0、`0x401cbf` 置 1），`[0x4991b8]` 由选图界面/存档给出
（`0x40692d` `dec eax` 后写入、`0x4073ae` 从 `0x46cb54` 写入、`0x406eef` 置 0）。
`stage` / `game_map` 这两个名字沿用既有文档，**本文只坐实公式本身**。
旁证（B）：`0x407e9d` 用 `[0x4991b8] * 17 + 0x68` 挑关卡附属资源，说明
`0x4991b8` 是"内层"索引。

@source `0x00401c95`、`0x00401cbf`、`0x0040692d`、`0x004073a8`、`0x00406eef`、`0x00407e9d`

### 1.2 ⚠️ 地图结构数据有**两个**来源（复刻文档漏了主路径）

@source `0x00407bc4`

```asm
00407bc4  cmp      dword ptr [0x47493c], 0      ; 已经装过？（存档分支会先装）
00407bcb  jne      0x407e0b
00407bd1  push     0x4631c8   "MAPDAT.MKF"
00407bd6  call     0x4502fe   → mkf_open
00407bdb  mov      esi, eax
00407be0  cmp      eax, -1
00407be3  je       0x407c16                     ; 打不开 → 回退
00407be9  movsx    eax, word ptr [0x4991b6]
00407bf0  shl      eax, 2
00407bf3  movsx    edx, word ptr [0x4991b8]
00407bfa  add      eax, edx
00407bfc  push     eax                          ; 资源号 = global_map_id（**不乘 2**）
00407bfe  call     0x450441   → mkf_read_resource
00407c06  mov      dword ptr [0x47493c], eax
...
00407c16  movsx    eax, word ptr [0x4991b6]     ; ← 回退路径
00407c1a  shl      eax, 2
00407c1d  movsx    edx, word ptr [0x4991b8]
00407c24  add      eax, edx
00407c2d  add      eax, eax                      ; gm*2
00407c2f  inc      eax                           ; gm*2+1
00407c32  call     0x450441   → mkf_read_resource
00407c3a  mov      dword ptr [0x47493c], eax
```

**结论（A）**：
1. 先试图打开 **`MAPDAT.MKF`**，读**资源号 `global_map_id`**；
2. 只有当 `mkf_open` 返回 `-1` 时才回退到 **`MAP.MKF` 资源号 `gm*2+1`**。

**发行版事实（B）**：`../Rich4/` 目录里**没有 `MAPDAT.MKF`**（`ls Rich4/*.MKF`：
Data / Effect / help / jump / map / Panel / Speaking，共 7 个），所以本发行版
**总是走回退分支**，`MAP.MKF[gm*2+1]` 就是全部 8 张地图的结构数据。
复刻文档只写了回退分支，把"机制"写成了"唯一路径"——结论在本版本下成立，
机制描述不完整。**实现复刻时应两条都实现**（`MAPDAT.MKF` 可能是地图编辑器
的输出文件；该文件名的字符串只在 `0x4631c8` 出现一次，无其它线索 → 用途未决）。

### 1.3 `MAP.MKF` 资源号总表（全部来自 `0x00407ad2` 的函数体）

| 资源号 | 内容 | 写入的全局 | @source |
|---|---|---|---|
| `gm*2` | GND 图块集（含 512B 调色板） | `0x474945` | `0x00407b0f` |
| `gm`（在 **MAPDAT.MKF**） | 地图结构数据（优先） | `0x47493c` | `0x00407c06` |
| `gm*2+1` | 地图结构数据（回退） | `0x47493c` | `0x00407c3a` |
| `gm+0x10` | 小地图/缩略图精灵库（SMP，2 帧） | `0x48badc` | `0x00407b38` |
| `gm+0x10` | **同一资源再读一遍** | `0x48bad0` | `0x00407b61` |
| `0x18` | 装饰物精灵库（SMP，**58 帧**，见 §七-19） | `0x474949` | `0x00407bab` |
| `0x19` | 建筑/设施精灵库（SPR） | `0x48aea8` | `0x00407f77` |
| `0x1a` | 第二精灵库（SMP/SPR） | `0x47494d` | `0x00407bbf` |
| `0x27 + gm*5 + i`，i=0..4 | 地图附属资源（**5 项**） | `0x48ae4c[i]` | `0x00407e3b` |
| `0x4f + gm` | 地图附属资源 | `0x48ae60` | `0x00407e6c` |
| `0x57 + i`，i=0..16（`stage==0`） | 关卡资源（**17 项**） | `0x48ae64[i]` | `0x00407e8e` |
| `0x68 + game_map*17 + i`（否则） | 关卡资源（17 项） | `0x48ae64[i]` | `0x00407ec1` |
| `0x205` | 大图图库 | `0x48bad8` | `0x0040808f` |
| `0x207` | 大图图库 | `0x48bad4` | `0x004080ab` |
| `0x18c + i`，i=0..0x13 | 20 项图库 | `0x496930[i]` | `0x004080cc` |

另有**两条按表内字段间接取资源**的路径（资源号 = `0x26 + 表内字段值`；
缓存数组 `0x48ae4c` 用**字段原值**当槽号，只有槽 0..4 被上表的
`0x27+gm*5+i` 预填，其余槽按需填）：

```asm
00407ed3  cmp      ebx, dword ptr [0x498e90]   ; 1..num_commercials（1 基）
00407ede  mov      edx, dword ptr [0x498e7c]   ; 上市企业表
00407ee4  mov      ax, word ptr [edx + eax + 0x20]   ; ★ commercial + 0x20（u16）
00407ef0  mov      esi, eax
00407ef2  shl      esi, 2
00407ef5  mov      ebp, dword ptr [esi + 0x48ae4c]
00407efd  jne      0x407f14
00407f01  add      eax, 0x26                            ; ★ 资源号 = 值 + 0x26
00407f06  call     0x450441   → mkf_read_resource
00407f0e  mov      dword ptr [esi + 0x48ae4c], eax
```

```asm
00407f1c  cmp      ebx, dword ptr [0x499074]   ; 1..num_landscapes
00407f2b  shl      edx, 3
00407f2e  sub      edx, eax                     ; edx = idx*0x1c（景观表步长）
00407f30  mov      eax, dword ptr [0x498e78]
00407f35  mov      ax, word ptr [edx + eax + 0x1a]      ; ★ landscape + 0x1a（u16）
00407f52  add      eax, 0x26                            ; ★ 资源号 = 值 + 0x26
```

@source `0x00407ed3`、`0x00407f1c`

**要点（A）**：这两条路径把 `0x48ae4c` 当成一张**大缓存表**（槽号 = 表内字段值），
只把前 5 槽（`0x27+gm*5+i`）预填。实测字段值域（8 张图，见 §六-2）：

- `commercial+0x20`（u16）∈ `{0} ∪ 134..194 ∪ 228..232` → 资源号 184..270；
- `landscape+0x1a`（u16）∈ `{0} ∪ 144..259` → 资源号最高 **297**，
  **正好等于 `MAP.MKF` 的最后一个资源号（共 298 项，0..297）**。

即"景观/企业建筑图"就是 `MAP.MKF` 尾部那一段 SPR——这既是本文的新结论（A+B），
也解释了为什么 `0x1a` 的值域从 144 起。字段为 0 表示"没有专属图"
（`0x00407eee` / `0x00407f3f` 的 `je` 跳过）。

---

## 二、地图数据头（40 字节 = 10 × `uint32`）

@source `0x00407c3f`（冷启动路径；**同一段解析在存档路径 `0x00402eae` 再出现一次**，
两份逐字节一致，互为独立印证）

```asm
00407c3f  mov      eax, dword ptr [0x47493c]   ; 地图缓冲基址
00407c44  mov      edx, dword ptr [eax]        ; +0x00
00407c46  mov      dword ptr [0x498e9c], edx
00407c4c  mov      edx, dword ptr [eax + 4]    ; +0x04  偏移
00407c4f  lea      ebx, [eax + edx]            ;        基址 + 偏移
00407c52  mov      dword ptr [0x498e80], ebx
00407c58  mov      edx, dword ptr [eax + 8]    ; +0x08
00407c5b  mov      dword ptr [0x498e98], edx
00407c61  mov      edx, dword ptr [eax + 0xc]
00407c64  lea      ebx, [eax + edx]
00407c67  mov      dword ptr [0x498e84], ebx
00407c6d  mov      edx, dword ptr [eax + 0x10]
00407c70  mov      dword ptr [0x498e8c], edx
00407c76  mov      edx, dword ptr [eax + 0x14]
00407c79  lea      ebx, [eax + edx]
00407c7c  mov      dword ptr [0x498e88], ebx
00407c82  mov      edx, dword ptr [eax + 0x18]
00407c85  mov      dword ptr [0x498e90], edx
00407c8b  mov      edx, dword ptr [eax + 0x1c]
00407c8e  lea      ebx, [eax + edx]
00407c91  mov      dword ptr [0x498e7c], ebx
00407c97  mov      edx, dword ptr [eax + 0x20]
00407c9a  mov      dword ptr [0x499074], edx
00407ca0  mov      edx, dword ptr [eax + 0x24]
00407ca3  lea      ebx, [eax + edx]
00407ca6  mov      dword ptr [0x498e78], ebx
```

| 偏移 | 类型 | 字段 | → 全局（项数 / 指针） | 等级 |
|---|---|---|---|---|
| `0x00` | u32 | `num_map_nodes` | `0x498e9c` | A |
| `0x04` | u32 | `node_table_offset` | `0x498e80`（**已加基址**） | A |
| `0x08` | u32 | `num_lands` | `0x498e98` | A |
| `0x0c` | u32 | `land_table_offset` | `0x498e84` | A |
| `0x10` | u32 | `num_facilities` | `0x498e8c` | A |
| `0x14` | u32 | `facility_table_offset` | `0x498e88` | A |
| `0x18` | u32 | `num_commercials` | `0x498e90` | A |
| `0x1c` | u32 | `commercial_table_offset` | `0x498e7c` | A |
| `0x20` | u32 | `num_landscapes` | `0x499074` | A |
| `0x24` | u32 | `landscape_table_offset` | `0x498e78` | A |

**语义（A）**：`*_table_offset` 是**相对地图缓冲基址的字节偏移**（`lea ebx,[eax+edx]`），
不是文件偏移；头之后第一张表紧贴头部（实测 8 张图 `node_table_offset == 0x28`）。

**项数语义（A+实测）**：`num_*` 是**有效项数**；每张表在文件里实际有 **`num_* + 1`** 项
（第 0 项是哨兵），见 §三。

### 2.1 `map_data_size` 的算法

@source `0x00407cac`（**完整解出，与复刻文档给的公式一致**）

```asm
00407cac  mov      edx, dword ptr [0x499074]   ; edx = num_landscapes
00407cb2  shl      edx, 2                       ; edx = n*4
00407cb5  mov      ebx, edx                     ; ebx = n*4
00407cb7  shl      edx, 3                       ; edx = n*32
00407cba  sub      edx, ebx                     ; edx = n*32 - n*4 = n*0x1c
00407cbc  mov      ebx, dword ptr [0x498e78]   ; ebx = landscape 表基址（= buf + lso）
00407cc2  add      edx, ebx                     ; edx = buf + lso + n*0x1c
00407cc4  add      edx, 0x1c                    ;     + 0x1c  ← 哨兵项也算进去
00407cc7  sub      edx, eax                     ;     - buf
00407cc9  mov      dword ptr [0x498e94], edx    ;     → map_data_size
```

即

```
map_data_size = (landscape_table_offset + (num_landscapes + 1) * 0x1c) - 资源基址
```

**结论（A）**：**复刻文档 §2.1 的公式正确**。第 4 行 `add edx,0x1c` 正是"第 0 项哨兵"
的字节数——这同时也是 §三 的直接证据。

**用途（A）**：这个值是"整块地图数据"的长度，用来
① 给**每个玩家**分配一份地图缓冲；② 存档时整块写回。见 §五。

---

### ★ 小地图标记 `0x0040a4e1(landIndex)` —— 纯绘制（2026 本轮查清）

```asm
0040a4ed  ecx = [0x48badc] + 0xc + idx*0xc     ; ★ 精灵记录
0040a503  edx = [0x48bad0] + 0xc + idx*0xc     ; ★ 落点记录
0040a50f  call 0x456280                        ; → blitRect_inner（**画**）
; 然后遍历**整张**地块表（0x498e84，计数 0x498e98）：
0040a5c5  ebp = (owner-1)*0x68
0040a5cd  push [ebp + 0x496b6c]                ; ★ 玩家 +0x04 = 颜色
0040a601  call 0x456384                        ; 又一层 blit 包装
```

⇒ 两条结论（都从**调用链**读出，不再是"弱证据"）：
1. **U7 解决**：`0x48badc` 与 `0x48bad0` 不是冗余 —— 前者当**精灵**（`blitRect_inner`
   读它的 `+0/+2/+8`），后者当**落点/目标**记录；同一份 MKF 资源读两遍是为了
   让"图"与"位"各持一份可写拷贝。
2. **`0x40a4e1` 是表现层**：它只读 `player+0x04`（颜色）并走两层 blit，
   **不写任何规则状态** ⇒ 复刻不实现它**不是**缺口（`cards/monster.ts` 注释里
   原先那句"表现层刷新"是对的）。差分/差分工具据此把它排除。

## 三、索引基点：**1 基**（每表带一个哨兵项 0）★

这是复刻最容易错的一处。三条**互相独立**的证据都指向"1 基 + 哨兵项 0"。

### 证据 1（A）：所有遍历都是 `for (i = 1; i <= count; i++)`

@source `0x00408023`（节点表，步长 `0x28`）

```asm
00408023  mov      ebx, 1
00408028  mov      edi, dword ptr [0x498e9c]   ; num_map_nodes
0040802e  cmp      ebx, edi
00408030  jg       0x408072                    ; i > count 结束 → 1..count
00408032  mov      eax, ebx
00408034  shl      eax, 2
00408037  add      eax, ebx                     ; eax = i*5
00408039  mov      edx, dword ptr [0x498e80]   ; node 表基址
0040803f  cmp      word ptr [edx + eax*8 + 0x20], 0x1f41   ; i*0x28 + 0x20
```

同样形态至少还有 6 处：

@source `0x00407dc6`（上市企业表，步长 `0x34`）、`0x00407ed3`（同）、
`0x00407f1c`（景观表，步长 `0x1c`）、`0x004090f0`（住宅表，步长 `0x34`）、
`0x00409302`（设施表，步长 `0x38`）、`0x0040aa1d`（节点表）、`0x00409bb4`（节点表）

```asm
004090e2  mov      ebx, 1
004090e7  mov      ebp, dword ptr [0x498e84]   ; 住宅表基址
004090ed  add      ebp, 0x34                    ; ★ 先加一整项 → 项 1 在 +0x34
004090f0  cmp      ebx, dword ptr [0x498e98]   ; num_lands
004090f6  jg       0x4092f4
004090fc  movsx    eax, word ptr [ebp]          ; 项 i 的 +0x00
0040910c  movsx    edx, word ptr [ebp + 2]      ; 项 i 的 +0x02
```

### 证据 2（A）：类型编码 `基数 + i` 时也要减去基数

@source `0x0040af12`（"对象 id → 屏幕坐标"的分派器，105 条；`id` 的编码见右列）

```asm
0040af1b  cmp      eax, 0x7d0                   ; 2000
0040af20  jge      0x40af38
0040af22  mov      edx, eax
0040af24  shl      edx, 2
0040af27  add      edx, eax
0040af29  mov      ecx, dword ptr [0x498e80]   ; ① id < 2000 → 直接作 node 索引
0040af2f  movsx    ebx, word ptr [ecx + edx*8]        ; i*0x28 + 0
0040af33  movsx    ecx, word ptr [ecx + edx*8 + 2]
0040af38  cmp      eax, 0x7d0
0040af3d  jle      0x40af62
0040af3f  cmp      eax, 0xfa0                   ; 4000
0040af44  jge      0x40af62
0040af46  sub      eax, 0x7d0                   ; ★ id - 2000
0040af4b  imul     eax, eax, 0x34               ; ★ 住宅表步长 0x34
0040af4e  mov      ecx, dword ptr [0x498e84]
0040af62  cmp      eax, 0xfa0
0040af69  cmp      eax, 0x1770                 ; 6000
0040af70  sub      eax, 0xfa0                   ; ★ id - 4000
0040af75  shl      eax, 3
0040af78  mov      edx, eax
0040af7a  shl      eax, 3
0040af7d  sub      eax, edx                     ;   ×56 = 0x38（设施步长）
0040af7f  mov      ecx, dword ptr [0x498e88]
0040af8e  cmp      eax, 0x1f40                 ; 8000
0040af95  sub      eax, 0x1770                 ; ★ id - 6000
0040af9a  imul     eax, eax, 0x34               ;   ×0x34（企业步长）
0040af9d  mov      ecx, dword ptr [0x498e7c]
0040afa5  cmp      eax, 0x1f40
0040afac  cmp      eax, 0x2710                 ; 10000
0040afb3  sub      eax, 0x1f40                 ; ★ id - 8000
0040afb8  shl      eax, 2
0040afbb  mov      edx, eax
0040afbd  shl      eax, 3
0040afc0  sub      eax, edx                     ;   ×28 = 0x1c（景观步长）
0040afc2  mov      ecx, dword ptr [0x498e78]
```

这段同时给出**四张表的步长**与**类型基数**：`2000+i` 住宅、`4000+i` 设施、
`6000+i` 上市企业、`8000+i` 景观，全部用 `id - 基数` 得索引——
说明 `id = 基数 + i` 就是 `i*stride`，即 **i 从 1 起**（`id == 基数` 落在哨兵项 0）。

同一结论的另一条独立证据：装载时把住宅/交通灯的实体 id 设成
`edx = ebx + 0x7d0`，而 `ebx` 就是上面那个从 1 开始的循环变量。

@source `0x00409246`

```asm
00409246  mov      edx, ebx
00409248  add      edx, 0x7d0                   ; ★ 住宅 i 的对象 id = 2000 + i（i 1 基）
0040925a  mov      word ptr [esi*4 + 0x48a850], dx
```

### 证据 3（实测，C→A）：表间距恒等于 `(count+1) * 步长`

8 张图的**每一张表**都满足 `(下一张表偏移 − 本表偏移) / 步长 == count + 1`，
且**文件末尾**恒为 `landscape_off + (num_landscapes+1)*0x1c`：

```
gm=0  资源1  node 103 → 实测 104 项 | land 50 → 51 | facility 4 → 5 | commercial 3 → 4 | landscape 21 → 22
       文件长度 7956 == 0x1cac + 22*0x1c                          ✔
gm=7  资源15 node 101 → 102        | land  0 →  1 | facility 20 → 21| commercial 7 → 8 | landscape 79 → 80
       文件长度 8004 == 0x1684 + 80*0x1c                          ✔
（8/8 全部 OK；脚本 tools/scratch/map_verify.py）
```

`num_lands == 0`（gm=7）时表里仍有 **1** 项（哨兵），这是最干净的一个反例：
**绝不能按 `count` 项去解析**。这一条同时能由 `0x00407cac` 的 `add edx,0x1c`
（哨兵项被算进 `map_data_size`）与 `0x00407aec` 的
`sub eax, 0x7d0`（`id == 基数` 时不落在任何有效项）在机器码层面独立支持。

@source `0x00407cac`、`0x0040afb3`、`0x004090ed`、`0x004092ff`、`0x00407dce`
（脚本：`tools/scratch/map_verify.py`）

### 哨兵项 0 的内容（实测）

| 表 | 项 0 的内容 |
|---|---|
| `node` | 全 0（x=0,y=0,名字空,adjacent 全 0,type=0,flags=0） |
| `land` / `facility` / `commercial` / `landscape` | 全 0 |

所以"按 `+ 基数` 的对象 id"在数据里**不会**指向哨兵项；而按 1 基直接用 `count` 项
解析的实现会**整表错位一项**。

---

## 四、五张表

### 4.1 `node`（步长 `0x28` = 40）

@source `0x00407a93`（坐标，另一处 `0x00408312` 相邻节点，`0x0040aa25` 随机取格）

```asm
00407a91  mov      eax, edx
00407a93  shl      eax, 2
00407a96  add      eax, edx
00407a98  shl      eax, 3                       ; eax = idx*5*8 = idx*0x28
00407a9b  mov      ebx, dword ptr [0x498e80]
00407aa1  lea      edx, [ebx + eax]             ; 节点指针
00407ab4  movsx    ebx, word ptr [eax]          ; 节点 A 的 +0x00 = x（int16）
00407ab7  movsx    ecx, word ptr [edx]          ; 节点 B 的 +0x00
00407abc  movsx    ecx, word ptr [eax + 2]      ; 节点 A 的 +0x02 = y（int16）
00407ac0  movsx    eax, word ptr [edx + 2]      ; 节点 B 的 +0x02
```

```asm
0040830c  inc      ebx
0040830d  cmp      ebx, 4
00408310  jge      0x408328
00408312  lea      esi, [ebx + ebx]             ; i*2
00408315  add      esi, ebp                    ; ebp = 节点指针
00408317  mov      dx, word ptr [esi + 0x18]    ; ★ adjacent[i]，u16，i=0..3
0040831b  test     dx, dx
0040831e  je       0x40830c                    ; 0 = 无
```

| 偏移 | 大小 | 类型 | 字段 | 证据 | 等级 |
|---|---|---|---|---|---|
| `0x00` | 2 | int16 | `x`（世界坐标，绘制时 `>>5`） | `0x00407ab4`、`0x004090fc` 同构 | A |
| `0x02` | 2 | int16 | `y` | `0x00407abc` | A |
| `0x04` | ≤20 | char[] | `name`：**Big5，NUL 结尾** | `0x0041a060` + 格式串 `0x4639e1` | A |
| `0x18` | 8 | uint16 ×4 | `adjacent[0..3]`：**节点编号，1 基，0 = 无** | `0x00408317` | A |
| `0x20` | 2 | uint16 | `type`：见 §4.6 的编码 | `0x0040803f`、`0x0040af1b` | A |
| `0x22` | 2 | uint16 | `decor`：装饰精灵 1 基下标，0 = 不画 | `0x00408580`、`0x0040862e` | A |
| `0x24` | 4 | uint32 | `flags`：位域，语义部分未决 | `0x00409bc0`、`0x0040aa37` | B |

**名字起点（A）**——先看格式化串，再看传入的指针：

@source `0x0041a05f`

```asm
0041a05f  push     ebp                          ; 费用
0041a060  lea      eax, [esi + 4]               ; ★ 名字 = 项基址 + 4
0041a063  push     eax
0041a064  push     0x4639e1                     ; "%s\n\n費用:%d元\n\n是否買下此地？"
0041a06e  call     0x457110   → sprintf_wrap
```

**名字上限（B，非 A）**：`+0x18` 是 `adjacent`，所以名字**结构上**最多
`0x04..0x17` = **20 字节**。实测 987 个节点的名字节长分布为
`0:66, 4:284, 6:278, 8:351, 10:8`（**最大 10 字节**，即 5 个 Big5 字），
66 个节点名字为空——**20 只是上限，没有数据触及它**。安全读法：
从 `+0x04` 起读到第一个 NUL（exe 就是这么用的）。

**`adjacent` 的"可走"判定（A）**：

@source `0x0040aa37`（"随机取一个空格"里用的判定）

```asm
0040aa37  test     dword ptr [eax + 0x24], 0x80ffff00   ; flags
0040aa3e  jne      0x40aa50
0040aa40  cmp      dword ptr [eax + 0x18], 0           ; ★ 把 4 个 u16 当两个 dword 测
0040aa44  jne      0x40aa4c
0040aa46  cmp      dword ptr [eax + 0x1c], 0
0040aa4a  je       0x40aa50
0040aa4c  mov      byte ptr [esp + ebx], dl
```

即"有效可走" = `flags & 0x80ffff00 == 0` **且** `adjacent` 8 字节非全 0。
实测"adjacent 四项全 0"的节点 **20 / 987**，`adjacent` 最大值 144（== 最大 `num_map_nodes`），
印证"1 基、0 表示无"。

#### `flags`（`+0x24`）到底被怎么用（B）

exe 里共 **4 个**掩码点，**不是同一个掩码**：

| @source | 指令 | 备注 |
|---|---|---|
| `0x00409bc0` | `test dword ptr [ebx+0x24], 0xffff00` | 小地图绘制，**不看 bit 31** |
| `0x00409f7c` | `test dword ptr [esi+0x24], 0xffff00` | 同上 |
| `0x0040aa37` | `test dword ptr [eax+0x24], 0x80ffff00` | 随机取空格（置物判定） |
| `0x0040aac3` | `test dword ptr [eax+0x24], 0x80ffff00` | 同上，另一入口 |

实测地图数据里 `flags` 的**高位**只出现三种：
`bit 27` × 3 个节点、`bit 28` × 7 个、`bit 31` × 47 个，**bits 8..26 恒为 0**。
所以 `0x80ffff00` 两处在**静态数据**下退化成"bit 31 是否置位"，
而 `0x00ffff00` 两处恒为假（永不跳过）。**这四种点位的语义差异未决**。

低字节实测分布（987 节点，`A`级：这是数据）：
`0:628, 1:10, 2:17, 3:22, 4:8, 5:8, 6:9, 7:10, 8:8, 9:16, 10:26, 11:39, 12:130,
13:13, 14:11, 15:17, 16:15`。取值 1..16 全部出现、且 1/2/4/8/16 都是单比特
→ 低字节**可能是位域（bits 0..4）而不是枚举**（B）；**数值↔名称的对应关系本文未能用
exe 坐实 → 未决**。

exe 里确实存在一个"格子/物件类型名"表，但**无法证明它按下标 `flags&0xff` 索引**，
故只作为线索列出：

@source `0x0047606c`（24 个字符串指针，`A`级：数据）

```
0 道具 | 1 說明 | 2 公司企業 | 3 住宅用地 | 4 商業用地 | 5 七彩氣球 | 6 公園
7 卡片 | 8 企鵝挖寶 | 9 百貨公司 | 10 命運 | 11 得十點 | 12 得三十點 | 13 得五十點
14 喜從天降 | 15 新聞 | 16 監獄 | 17 銀行 | 18 樂透 | 19 醫院 | 20 魔法屋
21 乞丐 | 22 土地公 | 23 大衰神
```

**另有一条容易混淆的位域**：`0x48b8c4` 是一张"当前屏幕上的对象 id"表
（`0x0040a095` 处从网格 `0x474938` 收集），`0x0040ac7b` 对它做**位扫描**
（`bit0..3` → `0x0040cd07`、`bit4..7` → `0x0043ec3f`、`bit8..14` → `0x0040e14d`，
见 `0x0040ae85`、`0x0040aeb4`、`0x0040aee0`）。**那是对象 id 的位域，不是节点的
`flags`**——不要混用。

#### `decor`（`+0x22`）：`MAP.MKF[0x18]` 精灵库的 1 基下标（A）

@source `0x00407ba0`（装载）、`0x0040855f`（绘制）

```asm
00407ba0  push     0x18
00407ba3  call     0x450441   → mkf_read_resource
00407bab  mov      dword ptr [0x474949], eax   ; 装饰物精灵库
```

```asm
0040855f  mov      ebx, 1
00408564  mov      eax, dword ptr [0x498e80]   ; node 表
00408569  add      eax, 0x28                   ; 从项 1 起（1 基）
00408570  cmp      ebx, dword ptr [0x498e9c]
0040857c  mov      eax, dword ptr [esp + 0x48]
00408580  cmp      word ptr [eax + 0x22], 0     ; ★ 0 = 不画
00408585  je       0x408657
...
0040862e  mov      ax, word ptr [edx + 0x22]    ; ★ decor
00408632  dec      eax                          ;   1 基 → 0 基
00408635  shl      esi, 2
00408638  sub      esi, eax                     ;   esi = (decor-1)*3
（后续 `shl esi,2` → ×12）
0040863d  mov      eax, dword ptr [0x474949]
00408642  add      eax, 0xc                     ; ★ 精灵库 + 0xc = graph_st 数组
```

**精灵库的帧数（A，不依赖解包文件）**：`MAP.MKF[0x18]` 资源头里
`dword2 = 708`，而 `708 = 12 + 58*12` → **58 帧**（`12` 是库头；见 §六-1 的推导）。
实测 `decor` 取值分布（`A`级：数据）：

- gm 0,1,2,6：只用 **奇数 1..33**；gm 3 缺 7；gm 5、gm 7 缺 1；
- **gm 4 特殊**：用偶数 4..34 + 35..58，全图 135 个节点里 134 个非 0；
  **未被引用的值是 37、38、46 三个**（不是两个）。

> `graph_st` 记录本体（`+0` u16 宽、`+2` u16 高、`+8` 像素指针）有汇编为证
> （`0x00456292` `movzx eax, word ptr [edx+2]`、`0x00456297` `[edx]`、
> `0x004500e0` 把 `+8` 改写成绝对指针）。但**磁盘上第 1..n 条记录的具体数值本文
> 未决**——因为既有解包文件在这里是坏的，见 §六-1。

### 4.2 `land`（步长 `0x34` = 52）—— **就是**运行时的 `housing_land`

@source `0x00407c61`（装载时直接指向地图缓冲内部）、`0x004090e7`（遍历）

```asm
00407c61  mov      edx, dword ptr [eax + 0xc]   ; land_table_offset
00407c67  mov      dword ptr [0x498e84], ebx    ; ★ 指针落在地图缓冲里
```

**结论（A）**：`0x498e84`（既有文档称 `housing_land` / `land_info_ptr`）**没有独立数组**，
它指向地图缓冲内的 `land` 表。所以 `docs/systems/land-rent.md` §一 的字段表就是
**本表的字段表**，两者不是两种结构。

| 偏移 | 类型 | 字段 | 证据 | 地图文件里 |
|---|---|---|---|---|
| `0x00` | int16 | `x` | `0x004090fc` | 非 0 |
| `0x02` | int16 | `y` | `0x0040910c` | 非 0 |
| `0x04` | char[] | `name`（Big5，NUL 结尾） | `0x0041a060` | 实测 ≤ 8 字节 |
| `0x17` | uint8 | **非 0 时过路费翻倍** | `0x00419b09` / `0x00419b0f` | **恒 0**（389/389） |
| `0x18` | uint8 | `type`（0 = 住宅，非 0 = 商業） | `0x0040b138`、`0x0040b149` | 恒 0 |
| `0x19` | uint8 | `owner`（1 基，0 = 无主） | `0x0040b474`、`0x0041c504` | 恒 0 |
| `0x1a` | uint8 | `level`（0..5，索引租金表） | `0x0041a35a`、`0x0040b13e`、`0x00419793` | 恒 0 |
| `0x1b` | uint8 | **未决**（唯一读点见下） | `0x004091af` | **1..5，多数非 0** |
| `0x1c` | uint16 | `land_price`（地价） | `0x00443288`、`0x0041ea5a` | 非 0 |
| `0x1e` | uint16 | `house_price`（房价） | `0x0041ea53` | 非 0 |
| `0x20` | uint16×6 | 按等级租金表 | `0x00419796` | 非 0 |
| `0x2c` | uint32 | 未决（运行时被清零） | `0x00447553`（写） | 恒 0 |
| `0x30` | uint32 | `flast`（地契到期） | 见 `land-rent.md` | 恒 0 |

@source `0x00419793`

```asm
00419793  mov      al, byte ptr [ebx + 0x1a]          ; level
00419796  mov      ax, word ptr [ebx + eax*2 + 0x20]  ; ★ 租金表[level]
0041979b  and      eax, 0xffff
004197a0  add      edi, eax
```

@source `0x00419b09`

```asm
00419b09  cmp      byte ptr [esi + 0x17], 0    ; ★ +0x17 是独立字节字段
00419b0d  je       0x419b11
00419b0f  add      ebp, ebp                    ; ★ 非 0 → 费用翻倍
```

**`+0x1b` 的唯一读点（A 级指令，语义未决）**：

@source `0x004091af`

```asm
004091a8  mov      dword ptr [eax*4 + 0x48a44c], edx
004091af  mov      al, byte ptr [ebp + 0x1b]           ; ★ land + 0x1b
004091b2  add      al, byte ptr [0x499088]             ;  + 当前玩家（0x499088 用作 0xd24 步长索引）
004091b8  mov      dl, 8
004091ba  sub      dl, al
004091bc  and      dl, 7                               ;  (8 - v) & 7
004091bf  mov      eax, dword ptr [0x48bac8]
004091ce  mov      byte ptr [esi + 0x48a853], dl        ;  → 屏幕实体记录的一个 3 位字段
```

即：`land+0x1b` 参与一个 3 位（0..7）的外观/相位值，与"当前玩家"混算。
**它是什么，未决**（不猜）。

**名字长度（B）**：`+0x17` 被当独立字节读（上），所以名字**结构上**最多
`0x04..0x16` = **19 字节**；而地图文件里 `+0x0c..+0x16` 恒 0，实测名字 ≤ 8 字节。
**19 不是"写死的字段长度"**，只是结构上限。

### 4.3 `facility`（步长 `0x38` = 56）—— **就是**运行时的 `business_land`

@source `0x00407c76`（装载）、`0x004092f9`（遍历）

```asm
00407c76  mov      edx, dword ptr [eax + 0x14]   ; facility_table_offset
00407c7c  mov      dword ptr [0x498e88], ebx
```

| 偏移 | 类型 | 字段 | 证据 | 地图文件里 |
|---|---|---|---|---|
| `0x00` | int16 | `x` | `0x004092ff`/`0x0040930e` | 非 0 |
| `0x02` | int16 | `y` | `0x0040931e` | 非 0 |
| `0x04` | char[] | `name`（Big5） | 同 land 的 `lea [esi+4]` 形态；实测 ≤ 10 字节 | 非 0 |
| `0x18` | uint8 | 未决（与 4 比较） | `0x0041cda6`、`0x004456cf` | 恒 0 |
| `0x19` | uint8 | `owner`（1 基） | `0x0040a531`、`0x0040f785` | 恒 0 |
| `0x1a` | uint8 | 未决（被清零） | `0x0040f59c`、`0x004319e9` | 恒 0 |
| `0x1b` | uint8 | **未决** | 与 land 同形的 `+0x1b` 系列 | 1..5，多数非 0 |
| `0x1c` | **uint8** | 计数（高 4 位是倒计时） | `0x0041d160`、`0x0044553e`（写 0x50） | 恒 0 |
| `0x1e` | uint8 | 未决 | `0x0041cdb0`、`0x004456d5` | 恒 0 |
| `0x22` | uint16 | 未决（排序键） | `0x0041ed0c`、`0x00428c30` | 非 0 |
| `0x24` | uint16 | 未决（与 `0x4990e8` 相乘） | `0x0041fc52`、`0x00428c25` | 非 0 |
| `0x26`–`0x2f` | — | **未决**（文件里恒非 0，本文未定位到读点） | — | 非 0 |
| `0x30`–`0x37` | — | 恒 0（运行期） | — | 恒 0 |

@source `0x0041d158`

```asm
0041d158  cmp      ebx, dword ptr [0x498e8c]   ; num_facilities（1 基）
0041d160  mov      dh, byte ptr [eax + 0x1c]    ; ★ 一个**字节**
0041d163  test     dh, 0xf0
0041d166  je       0x41d179
0041d168  mov      cl, dh
0041d16a  sub      cl, 0x10                    ; ★ 高 4 位当计数器递减
```

**注意（A）**：`facility+0x1c` 是 **1 字节**，与 `land+0x1c`（uint16 地价）**不同义**。
两份表的 `0x34/0x38` 步长相近，但**字段布局不同**，不能互相套用。

### 4.4 `commercial`（步长 `0x34` = 52，上市企业）

@source `0x00407c8b`（装载）、`0x00407dce`（装载时的股价初始化）

```asm
00407c8b  mov      edx, dword ptr [eax + 0x1c]   ; commercial_table_offset
00407c91  mov      dword ptr [0x498e7c], ebx
```

| 偏移 | 类型 | 字段 | 证据 | 地图文件里 |
|---|---|---|---|---|
| `0x00` | int16 | `x` | `0x0040af9a` → `0x0040af54`（与住宅共用取坐标尾） | 非 0 |
| `0x02` | int16 | `y` | 同上 | 非 0 |
| `0x04` | char[] | `name`（Big5） | 实测 ≤ 8 字节 | 非 0 |
| `0x18` | uint8 | 未决（被清零） | `0x0040a723`、`0x0041c712` | 恒 0 |
| `0x19` | **uint8** | 股票索引（0 基，见下） | `0x00407dda` | 取值 0..11 |
| `0x1a` | uint8 | 未决（被当索引） | `0x00429ed7` | 取值 1..6+ |
| `0x1b` | uint8 | 未决 | 数据非 0 | 取值 2..6 |
| `0x20` | uint16 | **建筑图资源索引**：资源号 = 值 + `0x26` | `0x00407ee4` | 非 0（36/44 多见） |
| `0x24` | uint32 | **dword**（读作 dword） | `0x00428d9b` | 非 0 |
| `0x2c` | uint32 | 未决 | `0x0042c620`、`0x0042cfee` | 恒 0 |
| `0x30` | uint32 | **载入时算出的派生值**（不在地图文件里） | `0x00407df8` | 恒 0 |

@source `0x00407dc6`（载入时逐企业算 `0x30`）

```asm
00407dc6  cmp      ebx, dword ptr [0x498e90]        ; num_commercials（1 基）
00407dce  imul     esi, ebx, 0x34
00407dd1  mov      eax, dword ptr [0x498e7c]
00407dd6  add      esi, eax
00407dd8  xor      edx, edx
00407dda  mov      dl, byte ptr [esi + 0x19]         ; ★ 股票索引（字节）
00407ddd  mov      eax, edx
00407ddf  shl      eax, 3
00407de2  add      eax, edx
00407de4  mov      ax, word ptr [eax*4 + 0x496988]   ; ★ 每项 9*4 = 36 字节，取 +0 的 u16
00407dec  and      eax, 0xffff
00407df1  mov      edx, 0x2710                        ; 10000
00407df6  sub      edx, eax
00407df8  mov      dword ptr [esi + 0x30], edx        ; ★ +0x30 = 10000 - 股价
```

**股票索引是 0 基**：`+0x19` 直接乘 36，**没有 ±1 修正**（与 `land.owner` 的 1 基
形成对照）；实测取值 `0..8`，含 0，进一步支持 0 基（B）。

### 4.5 `landscape`（步长 `0x1c` = 28，特殊景观）

@source `0x00407ca0`（装载）、`0x0043ecea`（取坐标）

```asm
00407ca0  mov      edx, dword ptr [eax + 0x24]   ; landscape_table_offset
00407ca6  mov      dword ptr [0x498e78], ebx
```

```asm
0043ecea  mov      eax, dword ptr [0x498e78]
0043ecef  mov      si, word ptr [eax + 0x1c]     ; ★ 项 1 的 +0x00（= x）
0043ecf3  mov      word ptr [ebx + 0x496b70], si
0043ecfa  mov      ax, word ptr [eax + 0x1e]     ; ★ 项 1 的 +0x02（= y）
0043d643  mov      si, word ptr [eax + 0x38]     ;   项 2 的 +0x00
0043d64e  mov      ax, word ptr [eax + 0x3a]     ;   项 2 的 +0x02
```

| 偏移 | 类型 | 字段 | 证据 | 地图文件里 |
|---|---|---|---|---|
| `0x00` | int16 | `x` | `0x0043ecef` | 非 0 |
| `0x02` | int16 | `y` | `0x0043ecfa` | 非 0 |
| `0x04` | char[] | `name`（Big5） | 实测 ≤ 8 字节 | 非 0 |
| `0x18` | uint8 | 未决 | 数据非 0 | 151/457 非 0（1..） |
| `0x1a` | uint16 | **图像资源索引**：资源号 = 值 + `0x26` | `0x00407f35` | 456/457 非 0 |
| `0x1b` | uint8 | 未决 | 数据非 0 | 4/457 == 1 |
| `0x1c`–`0x1d` | — | **无**（`0x1c` 就是本表步长，即下一项的 `+0x00`） | — | — |

**"类型基数 8000 + 2 == 0x1f42" 的独立印证**：

@source `0x0040803f`

```asm
00408032  mov      eax, ebx
00408034  shl      eax, 2
00408037  add      eax, ebx
00408039  mov      edx, dword ptr [0x498e80]
0040803f  cmp      word ptr [edx + eax*8 + 0x20], 0x1f41   ; 8001
00408046  jne      0x40804f
00408048  mov      word ptr [0x48bae2], bx                ; 记下节点号
0040805f  cmp      word ptr [edx + eax*8 + 0x20], 0x1f42   ; 8002
00408068  mov      word ptr [0x48bae0], bx
```

即"节点 `+0x20` == 8001/8002"→ 景观表第 1/2 项。这既确认 `+0x20` 是类型字段，
也确认景观基数 `0x1f40`。

### 4.6 五张表的"文件烘焙 / 运行期写入"二分（实测，C→B）

用 8 张图全部 987 节点 / 389 住宅 / 59 设施 / 44 企业 / 457 景观统计每字节是否非 0
（字段偏移与步长取自 `0x004090ed`、`0x004092ff`、`0x00407dce`、`0x00407f2a`）：

@source `0x004090ed`、`0x004092ff`、`0x00407dce`、`0x00407f2e`

| 表 | 文件里**恒 0**（运行期字段） | 文件里**有值**（地图烘焙） |
|---|---|---|
| `node` | — | 全部（`0x00`–`0x27`） |
| `land` | `0x17`、`0x18`、`0x19`、`0x1a`、`0x2c..0x2f`、`0x30..0x33` | `0x00`/`0x02`、`0x04..0x0b`、`0x1b`、`0x1c..0x1d`、`0x1e..0x1f`、`0x20..0x2b` |
| `facility` | `0x18`、`0x19`、`0x1a`、`0x1c`、`0x1e`、`0x20`、`0x21`、`0x30..0x37` | `0x00`/`0x02`、`0x04..0x0d`、`0x1b`、`0x22..0x2f` |
| `commercial` | `0x18`、`0x0e..0x17`、`0x1c..0x1f`、`0x21`、`0x27..0x33` | `0x00`/`0x02`、`0x04..0x0d`、`0x19`、`0x1a`、`0x1b`、`0x20..0x26` |
| `landscape` | `0x0e..0x17`（名字补零区）、`0x19` | `0x00`/`0x02`、`0x04..0x0d`、`0x18`、`0x1a`、`0x1b` |

**含义**：复刻如果从地图文件读 `land.owner` / `land.level` / `land.type`，
读到的**一定是 0**——它们是运行期字段。真正需要从地图烘焙的是
坐标、名字、`+0x1b`（未决）、价格、租金表、以及各"资源索引"字段。

---

### 4.7 ★ 走位与两个**共享缓冲区**（`b8b4` 路径表 / `b8c4` 可见表）`[A]`

> ★ 2026-09-16 补：本節此前**整段缺失**。是逐函數覆蓋審計
> （`tools/audit_spec_coverage.py`）翻出來的 —— remake 的
> `ai/tool-policy.ts` 早已把這兩個緩衝區寫清楚，PRD 卻沒有對應章節。
> 下面每一條都在 exe 裡重新核過。

地圖上有**兩張 16 位元的全域表**，被走位與 AI 判定共用：

| 全域 | 用途 | 誰寫 |
|---|---|---|
| `0x0048b8b4` | **路徑節點表**（`0x10` = 8 個 `word`） | `0x40b221`（前瞻）／`0x40b343`（反瞻） |
| `0x0048b8c4` | **可見表**（節點 id 或「實體格值」） | `0x409ef9`（畫面內節點）／`0x40a45c`（畫面內實體）／`0x40a0b1`（以某點為中心的實體） |

#### (1) `0x40b221(player, n)` 前瞻 —— `@source` 全函式 83 條，本節逐條讀過

```asm
0040b22e  push 0x10 / push 0 / push 0x48b8b4
0040b236  call 0x456f60                  ; ★ 每次呼叫先把 16 位元緩衝清 0
0040b23e  cmp  [esp+0x30], 8 / jle 跳過
0040b245  mov  [esp+0x30], 8             ; ★ 步數**封頂 8**（緩衝就 8 格）
0040b24d  imul eax, [esp+0x2c], 0x68     ; 參數 = 玩家
0040b254  mov  dx, word [eax + 0x496b74] ; 起點 = player + 0x0c = **node_id（腳下那格）**
0040b25f  mov  ax, word [eax + 0x496b76] ; 禁走 = player + 0x0e = **lastNodeId（上一格）**
迴圈 i = 0..n−1：
  edi = node_table + cur*0x28
  ebp = dword [edi + 0x24]               ; 節點 flags
  ecx = 0x40000000                       ; 鄰接槽 0 的**封路位**
  for slot = 0..3:
     nb = word [edi + 0x18 + slot*2]     ; 鄰接節點號
     if (nb == 0) continue               ; 空槽
     if (nb == prev) continue            ; ★ 不走回頭路
     if (ebp & ecx) continue             ; ★ 該槽被封路（位 30−slot）
     cand[ebx++] = nb
     ecx >>= 1
  if (ebx == 0)      buf[i] = prev       ; ★ 死路 → 原地（記 prev）
  elif (ebx == 1)    buf[i] = cand[0]    ; 唯一候選 → 直接走
  else:                                    ; 多候選 →
     buf[i] = cand[ rand() % ebx ]       ; ★ **消耗全域隨機數**
     [esp+8] = 1                          ; ★ 返回值 = 「遇到過岔路」
  prev = cur; cur = buf[i]
return [esp+8]
```

`0x40b343(player, n)` 是**同一個演算法、方向相反**：實測差異只有兩條初值對調 ——
`0x40b221` 是 `起點 = node_id(0x0c)`、`禁走 = lastNodeId(0x0e)`，
`0x40b343` 是 `起點 = lastNodeId(0x0e)`、`禁走 = node_id(0x0c)`
（`0x40b376` / `0x40b381` 兩條 `mov dx/ax, word [eax+0x496b7x]` 正好互換）。

⇒ 語意：**前瞻 = 「我往前走會經過哪 8 格」；反瞻 = 「我是從哪 8 格走過來的」**。
兩者都把結果寫進同一個全域緩衝 `0x48b8b4`，故**不能同時持有兩份**。

#### (2) `0x48b8c4` 可見表的三個填充器

| 函式 | 簽名 | 選出什麼 | 證據 |
|---|---|---|---|
| `0x409ef9()` | 無參 | 畫面內的**節點 id** | 129 條；`writes` 含 `0x48b8c4`；被 `0x4213c5`/`0x421574`/`0x421cb6` 呼叫 `[A]` |
| `0x40a45c(v)` | `v = -1` 表示全掃 | 畫面內的**實體格值**（地塊 `2000+i`／設施 `4000+i`／企業 `6000+i`）與玩家標記 `0x80xx` | 49 條；`writes` 含 `0x48b8c4`；被 `0x40ac7b`/`0x41f400`/`0x421ba6`/`0x444d1a` 呼叫 `[A]`（「選什麼」為 `[B]`，取自 remake 註釋，未逐條複核） |
| `0x40a0b1(x, y, r)` | 地圖點 + 半徑 | 以該點為中心的實體表；玩家標記只留**當前玩家** | 275 條；`writes` 含 `0x48b8c4`；**無呼叫者**（`gen/functions.json` 記 0）⇒ 由函式指標／跳表進入 `[A]`（簽名與「只留當前玩家」為 `[B]`） |

#### (3) 誰在讀這兩張表

`0x420970`／`0x420efa`／`0x42107f` 呼叫**前瞻**（`0x40b221`），
`0x4213c5`／`0x421574` 呼叫**反瞻**（`0x40b343`）並同時呼叫**可見表**（`0x409ef9`）。

**「這一族是 AI 用道具」不是推測**：這五個呼叫者的全域讀寫裡都有
`0x48be58`／`0x48be60`／**`0x48be64`**，而 `0x48be64` 正是**道具參數**全域
（路障/地雷/定時炸彈/傳送機 = 節點 id —— 見 `cards.md`/`tools.md` 一線）。
⇒ 原版 AI 決定「路障放前面還是後面、地雷放哪一格」用的就是這兩張表，
**不是**複刻裡那套「以我為中心 ±220px 方形視野」（那條口徑見 `T-005`/D-005）。

⚠️ **對複刻的意涵**：這兩張表都是**全域單例**，且前瞻/反瞻會互相覆蓋；
複刻若把它們建模成「按需現算的純函式」是**語意等價**的（呼叫點都先用完再算下一張），
但**前瞻裡的 `rand() % ebx` 必須算進全域隨機流** —— 否則又是一個
「少擲一次」的錯位（同第 45 條拍賣那類）。

## 五、加载流程

### 5.1 冷启动：`0x407ad2`（"从 MKF 读地图"）

@source `0x00407ad2`（函数入口，479 条指令 / 1571 字节）

顺序（全部 A 级）：

1. `0x00407ad6` 调 `0x4080f5` —— **释放上一张地图**（`0x00408107`–`0x00408157`
   依次 `free(0x474945 / 0x48badc / 0x48bad0 / 0x47493c / 0x474949 / 0x47494d)`）。
2. `0x00407adb` `mkf_open("MAP.MKF")` → 句柄存 `ebx`。
3. `0x00407af0`–`0x00407b0f` 读 GND 资源 `gm*2` → `0x474945`。
4. `0x00407b66`–`0x00407b97`
   `memcpy(0x48b6b4, gnd+0x10, 0x200)`（调色板）、
   `0x48bac4 = gnd+0x210`、`0x48bacc = gnd+0x2a90`。
5. `0x00407b9c`–`0x00407bbf` 读 `0x18` / `0x1a` 精灵库。
6. `0x00407bc4`–`0x00407c3a` 装**地图结构数据**（§1.2 的两条路径）→ `0x47493c`。
7. `0x00407c3f`–`0x00407ca6` **解析 40 字节头**，设 10 个全局（§二）。
8. `0x00407cac`–`0x00407cc9` 算 `map_data_size` → `0x498e94`。
9. `0x00407cd1`–`0x00407d38` 给**每个玩家**（`i = 0 .. [0x499114]-1`）
   `malloc(map_data_size)` 并清零，指针存 `[0x48f294 + i*0x2718]`
   （`esi = i*0x2718` 由 `0x00407ce0`–`0x00407cf9` 的乘加序列算出）；
   同时 `memset(0x48cb80 + i*0x2718, 0, 0x2718)`。
10. `0x00407d3a`–`0x00407d68`：`memset(0x496d08, 0, 0x450)`，再把
    `0x47ed3c` 的 **46 个字节**（`0x00407d5d` 的循环上限 `0x2e`）按步长
    `0x18` 写进 `0x496d08` 的每项首字节；随后载入各附属资源、
    初始化企业 `+0x30`（§4.4）、读 `0x4f + gm`、关卡资源等。
11. `0x00407e0d`–`0x00407e46`：附属资源 `0x27+gm*5+i` → `0x48ae4c[i]`。
12. `0x00407ece`–`0x00407f68`：按企业 `+0x20`、景观 `+0x1a` 取建筑图。
13. `0x00407f68`–`0x004080d7`：读 `0x19`、`0x205`、`0x207`、`0x18c+i`。
14. `0x00408110` 起（在 `0x4080f5` 里）与 `0x00408238` 起（释放路径）。

### 5.2 热启动：存档里的地图数据（`0x402ac5` 的 `0x402e87` 分支）

@source `0x00402e75`（读 `SAVE%d.DAT` 里的 `map_data_size` 与整块地图）

```asm
00402e75  push     edi
00402e76  push    1
00402e78  push    4
00402e7a  push    0x498e94                    ; ★ 从存档读 map_data_size
00402e7f  call    0x4576d0   → fread
00402e87  mov      ebx, dword ptr [0x498e94]
00402e8e  call     0x456f80   → malloc
00402e96  mov      dword ptr [0x47493c], eax    ; ★ 地图缓冲 = 存档里那整块
00402e9c  mov      esi, dword ptr [0x498e94]
00402ea6  call     0x4576d0   → fread（长度 map_data_size）
00402eae  mov      eax, dword ptr [0x47493c]
00402eb3  mov      edx, dword ptr [eax]
00402eb5  mov      dword ptr [0x498e9c], edx    ; 与 0x407c3f 段逐字节同构
...
00402f19  xor      ebx, ebx
00402f1b  cmp      ebx, dword ptr [0x499114]
00402f23  push     edi
00402f26  push     0x2718
00402f2b  ...                                 ; 逐玩家 malloc(map_data_size) + fread
00402f86  call     0x407ad2                    ; ★ 再调一次：此时 0x47493c != 0，
                                              ;   0x407bc4 直接跳到 0x407e0b（不读 MKF）
```

**结论（A）**：存档**直接保存整块地图缓冲**（40 字节头 + 五张表），长度 = `0x498e94`。
所以 `land.owner` / `level` / `price_status` 等运行期字段也随存档走。
加载存档后再调 `0x407ad2` 是为了补齐 GND/精灵库等**不存档**的资源，
`0x407bc4` 的短路保证不会覆盖存档里的地图数据。

### 5.3 存档写回

@source `0x00403308`

```asm
00403308  push     0x498e94                    ; 先写 4 字节 map_data_size
0040330d  call     0x457ada   → fwrite
00403316  mov      ebx, dword ptr [0x498e94]
0040331f  mov      esi, dword ptr [0x47493c]
00403326  call     0x457ada   → fwrite（长度 map_data_size）
```

### 5.4 全局指针一览

@source `0x00402eb5`–`0x00402f14`（存档路径的 10 个赋值）与 `0x00407c46`–`0x00407ca6`（冷启动路径的 10 个赋值）

| 全局 | 含义 | 写入点 | 读取者（示例） |
|---|---|---|---|
| `0x47493c` | 地图缓冲基址（40B 头 + 五表） | `0x00402e96`（存档）、`0x00407c06`（MAPDAT）、`0x00407c3a`（回退）、`0x0040824a`（释放置 0） | `0x00407c3f`、`0x0040331f` |
| `0x498e94` | `map_data_size` | `0x00407cc9`（算）、`0x00402e7a`（存档读） | `0x00402e87`、`0x00407d0b`、`0x00403316` |
| `0x498e9c` | `num_map_nodes` | `0x00402eb5`、`0x00407c46` | `0x00408028`、`0x0040aa1d` |
| `0x498e80` | `node` 表指针 | `0x00402ec1`、`0x00407c52` | `0x00407a9b`、`0x0040830c`、`0x0040aaf9` |
| `0x498e98` | `num_lands` | `0x00402eca`、`0x00407c5b` | `0x004090f0`、`0x004197b3` |
| `0x498e84` | `land` 表指针（= `housing_land`） | `0x00402ed6`、`0x00407c67` | `0x004090e7`、`0x004197aa`、`0x0040b130` |
| `0x498e8c` | `num_facilities` | `0x00402edf`、`0x00407c70` | `0x00409302`、`0x0041d158` |
| `0x498e88` | `facility` 表指针（= `business_land`） | `0x00402eeb`、`0x00407c7c` | `0x004092f9`、`0x0040ac03` |
| `0x498e90` | `num_commercials` | `0x00402ef4`、`0x00407c85` | `0x00407dc6`、`0x00428cb3` |
| `0x498e7c` | `commercial` 表指针 | `0x00402f00`、`0x00407c91` | `0x00407dce`、`0x00409544` |
| `0x499074` | `num_landscapes` | `0x00402f09`、`0x00407c9a` | `0x00407f1c`、`0x00409697` |
| `0x498e78` | `landscape` 表指针 | `0x00402f14`、`0x00407ca6` | `0x0043ecea`、`0x0043d63e`、`0x0040968e` |

**注意**：`0x498e78`（景观）/ `0x498e7c`（企业）/ `0x498e80`（节点）/ `0x498e84`（住宅）
/ `0x498e88`（设施）**全部指向地图缓冲内部**，不是独立分配的数组。任何"先把表拷出来"
的实现都会与原版行为分叉（尤其存档格式）。

---

## 六、数据实证（统计验证）

> **机器码是主证，统计只是佐证。** 两者冲突时以机器码为准，并指出冲突。
> 复跑：`python3 tools/scratch/map_verify.py`。

### 6.1 ⚠️ `extracted/map/*.bin` 的忠实性（**新发现，很重要**）

@source `0x00407c1a`、`0x00407c3a`（回退路径的资源号）、`0x004500e0`（SPR/SMP 装载期把 `+8` 改写成绝对指针）

`../extracted/map/*.bin` **不是** `MAP.MKF` 资源的逐字节转储。对照方法与结果：

```
按 exe 的算法读 MAP.MKF：表项 = dword(文件头 dword0 + 资源号*4)，
资源数据 = 文件[表项 + 16 .. + dword0]

资源 1,3,5,7,9,11,13,15（8 张地图结构数据）→ extracted 与原始**逐字节相同** ✔
资源 0,2,...,14（GND）        → 不同：首个差异在 0x12（**调色板**）
资源 39..297（SPR/SMP）       → 单段资源 259 个**全部**不同
```

`../assets-clean/map/0000.gnd` 反而与原始**逐字节相同**。

最强的一个反例是 SPR 资源 39（`dword0 == dword1`，即**未压缩、无需解码**）：
原始文件的 8 条记录**全部**满足 `gsize == w*h`：

```
原始 res39: (35,38,21,30,1330) (34,43,21,35,1462) (34,44,20,36,1496) (35,37,22,30,1295)
            (35,32,22,25,1120) (33,36,21,29,1188) (34,36,22,29,1224) (34,32,21,24,1088)
extracted/map/0039.bin: 第 0 条正确，第 1 条起是垃圾（(0x826c,0x0f00,7,0,...)）
```

**结论**：
1. 地图结构数据（`2*gm+1`）的解包是**忠实**的 → 本文 §三/§六-2 的统计验证有效；
2. SPR/SMP/GND 的解包**不可信** → 任何基于
   `extracted/map/*.bin` 的精灵元数据统计（含复刻文档 §3.4 的取值分布、
   `assets-clean/map/*_NNN.png` 的渲染）都需要重做；
3. **本文因此不引用**解包文件的精灵字段，只用能独立算出的量
   （如 `MAP.MKF[0x18]` 的帧数 = `(dword2 - 12)/12 = 58`，因为多段资源的
   `dword2` 是"元数据区字节数"，已在 39/25/26/27 四个资源上验证 `dword2 == 12 + n*12`）。

### 6.2 校验结果汇总

@source `0x00407c3f`、`0x00407cac`、`0x0040802e`、`0x004090f0`、`0x00409302`、`0x00407dc6`、`0x00407f1c`

| 校验 | 结果 |
|---|---|
| 8 张图 × 5 张表：`(表间距)/步长 == count+1` | **40/40 全部 OK** |
| 8 张图：`landscape_off + (nls+1)*0x1c == 文件长度` | **8/8 全部 OK** |
| 节点总数 | **987** |
| 各图 `(nodes, lands, facils, comms, landsc)` | `(103,50,4,3,21) (144,73,8,4,26) (110,49,5,6,16) (118,55,8,6,16) (135,47,5,3,2) (135,60,3,12,143) (141,55,6,3,154) (101,0,20,7,79)` |
| 节点名字节长 | max **10**；空名 66 |
| `adjacent` 四项全 0 的节点 | 20 / 987；最大值 144 |
| `flags` 高位置位 | bit27 ×3、bit28 ×7、bit31 ×47；bits8..26 恒 0 |
| `flags` 低字节 | 1..16 全部出现（分布见 §4.1） |
| `decor` | 0 的节点 506；非 0 最大 58；gm4 用偶数 4..34 + 35..58（缺 37/38/46） |
| `type` 落区间计数 | 特殊(type=0) 384、住宅 388、设施 118、企业 86、景观 11 |
| `type` → 表内名字**完全匹配** | 住宅 385/388、设施 116/118、企业 28/86、景观 6/11 |
| `land+0x17` / `+0x18` / `+0x19` / `+0x1a` | 全 0（389/389） |
| `commercial+0x19`（股票索引） | 取值 `0..11`（含 0 → 0 基） |
| `landscape+0x1a`（u16） | `{0} ∪ 144..259`，99 种取值 |
| `commercial+0x20`（u16） | `{0} ∪ 134..194 ∪ 228..232`，28 种取值 |
| `facility+0x1c` | 全 0（59/59） |

> 「企业 28/86」匹配率低，是因为企业节点的显示名常是通用名（「銀行」「百貨公司」等），
> 而 `commercial.name` 是公司名——**不是**解析错误（复刻文档的猜测方向一致，但
> 它给的分母 8/16 与实测不同）。

---

## 七、勘误：逐条校验 `rich4-remake/docs/map-format.md`

@source `0x00407ad2`、`0x00407c3f`、`0x0040af12`、`0x0040803f`（清单中每条都已在上文给出 @source）

> 该文档自称来源是 `rich4-re/asm/*.asm` + 8 张图解包统计。按铁律，`rich4-re/`
> **只作线索**，下面每条都以本文件的 exe 证据复核。✔ = 属实，✘ = 错，△ = 不完整/过度具体。

| # | 复刻文档的说法 | 判定 | 说明（正确值 / 证据） |
|---|---|---|---|
| 1 | `global_map_id = game_stage*4 + game_map` | ✔ | `0x00407af0`–`0x00407b01`；`stage`/`game_map` 这两个**名字**是线索 |
| 2 | `gm*2` = GND | ✔ | `0x00407ae9`–`0x00407b0f`（`add eax,eax`） |
| 3 | `gm*2+1` = 地图结构数据 | △ | 只是**回退**路径。主路径是 `MAPDAT.MKF[gm]`（`0x00407bd1`–`0x00407c06`），`mkf_open` 失败才回退（`0x00407c16`）。发行版无 `MAPDAT.MKF`，所以结论在本版本下成立 |
| 4 | `16 + gm` = 地图缩略图 | ✔（资源号）/ **A（用途，2026 本轮升级）** | `0x00407b2b`、`0x00407b54`。**同一资源读了两遍**（`0x48badc` 与 `0x48bad0`）—— 见下方「小地图标记」小节，用途已由**调用链**证实 |
| 5 | `0x18`/`0x1a` = 全局共用图素 | ✔ | `0x00407ba0`/`0x00407bb4`；`0x18` 是 **58 帧** SMP |
| 6 | `0x27 + gm*5 + i`（i=0..4） | ✔ | `0x00407e0d`–`0x00407e3b` |
| 7 | `0x4f + gm` | ✔ | `0x00407e48`–`0x00407e6c` |
| 8 | `0x57+i` / `0x68+game_map*17+i` | ✔ | `0x00407e71`–`0x00407ece` |
| 9 | （未列）`0x19`、`0x205`、`0x207`、`0x18c+i` | ✘ 漏列 | `0x00407f77`、`0x0040808f`、`0x004080ab`、`0x004080cc` |
| 10 | （未列）按表内字段取图：企业 `+0x20`、景观 `+0x1a`，资源号 = 值 + `0x26` | ✘ 漏列 | `0x00407ee4`、`0x00407f35` |
| 11 | 头部 = 40 字节 = 10 个 uint32，字段顺序如表 | ✔ | `0x00407c3f`–`0x00407ca6`（并在 `0x00402eae` 重复一次） |
| 12 | 所有表索引从 1 开始，第 i 项在 `off + i*size` | ✔ | 见 §三（循环 `i=1..count`；表间距 == count+1；`0x1c` 哨兵） |
| 13 | `map_data_size = lso + (nls+1)*0x1c - 基址` | ✔ | `0x00407cac`–`0x00407cc9`；且 8/8 张图文件长度吻合 |
| 14 | `node` 步长 `0x28` | ✔ | `0x00407a93`–`0x00407a98`、`0x00408032`–`0x0040803f` |
| 15 | `node` `+0x00`/`+0x02` = x/y int16 | ✔ | `0x00407ab4`、`0x00407abc` |
| 16 | `node+0x04` = Big5 名字，**20 字节** | △ | 起点 ✔（`0x0041a060`）；20 只是结构上限，实测最大 10 字节 → 应写成「NUL 结尾，结构上限 20」 |
| 17 | `node+0x18..0x1e` = `adjacent[4]`，0 = 无 | ✔ | `0x00408317`；`id = node index`，实测最大 144 ≤ `num_map_nodes` |
| 18 | "可走" = `(dword[+0x18] != 0) \|\| (dword[+0x1c] != 0)` | ✔ | **逐字属实**（`0x0040aa40`–`0x0040aa4a`）；补：还要求 `flags & 0x80ffff00 == 0` |
| 19 | `decor` = `MAP.MKF[0x18]` 的 1 基下标，0 = 不画；库有 **58** 张 | ✔ | `0x00408580`、`0x0040862e`–`0x00408645`；58 = `(708-12)/12` |
| 20 | 未被引用的装饰是 **37 与 46** 两个 | ✘ | 实测 gm=4 缺 **37、38、46** 三个 |
| 21 | 非 gm4 的图 decor 取值为 **1..33 全 17 种奇数** | △ | 实测 gm3 缺 7，gm5/gm7 缺 1 → 应写「各图略有出入」 |
| 22 | `flags & 0x80ffff00` 是"原版的可放置判定" | △ | 只出现在 `0x0040aa37`/`0x0040aac3`；`0x00409bc0`/`0x00409f7c` 用的是 **`0x00ffff00`**（不看 bit31） |
| 23 | `flags` 静态高位用到 bit 27 / 28 / 31 | ✔ | 实测 bit27 ×3、bit28 ×7、bit31 ×47，bits8..26 全 0 |
| 24 | 特殊格名称表：監獄 = 7、醫院 = 3；14/15 为 "—" | ✘ | 实测（987 节点）：監獄(4) = **8**、醫院(5) = **8**，14 = **11**、15 = **17**；其余 11 项与文档一致（1:10 2:17 3:22 6:9 7:10 8:8 9:16 10:26 11:39 12:130 13:13 16:15） |
| 25 | "名称↔数值"的对应关系 | 未决 | **本文件未能**用 exe 证明 `flags&0xff` 索引哪张名称表（线索：`0x0047606c` 的 24 项名表，但顺序与 1..16 不对应） |
| 26 | 四张表步长：`lands 0x34`、`facilities 0x38`、`commercials 0x34`、`landscapes 0x1c` | ✔ | `0x00407dce`、`0x004092ff`、`0x0040af4b`、`0x0040af7a`、`0x00407f2e`、`0x0040afbd` |
| 27 | 名字长度：lands 19B / facilities 20B / commercials 20B / landscapes 24B | △ | 这些是"到下一个已知字段"的推断，**不是格式里的长度字段**。硬约束：`land+0x17`、`facility+0x18`、`commercial+0x18` 都是独立字段 → 名字不跨界。安全读法 = 读到 NUL |
| 28 | "Kimi 版解析器对 lands 用 16B、facs/coms/spcs 用 24B 会越界污染" | ✔ | `../tools/parse_map.py` 确为 `16/24/24/24`（`read_named`）；但更准确的说法是"exe 不存长度，靠 NUL 结束" |
| 29 | `commercial[i].+0x30 = 10000 - stocks[+0x19].price`，股票表 36 字节、价在 `+0` | ✔ | `0x00407dda`–`0x00407df8`（`shl 3; add edx` → ×9，`[eax*4+0x496988]` → 每项 36 字节，取 `word [..]` 即 `+0`） |
| 30 | GND 头 `0x08 2B pixels_per_tile` | ✘ | `+0x08` 是 **uint32**（实测 `0x1440 = 5184 = 72*72`），不是 2 字节；`0x0a/0x0b` 恒 0 |
| 31 | GND：`+0x10` 512B 调色板、`0x210` 起图块、载入时 `memcpy` 到 `0x48b6b4` | ✔ | `0x00407b66`–`0x00407b79`（`push 0x200`）、`0x00407b86`、`0x00407b92` |
| 32 | §6 规模实测表（8 图的 land/facil/com/landscape 计数） | ✔ | 与本文 8/8 实测完全一致（节点列文档用 "—"，本文补：118/135/135/141/101） |
| 33 | §7d：资源 `0x1a` 的读取点 `0x004092c3`/`0x0040950e`/`0x00409c43` | ✔ | 三处都在 `0x47494d` 的读点集合里 |
| 34 | 结论来源写"`rich4-re/asm/*.asm` 的汇编分析" | ✘ 方法论 | 按本项目铁律，`rich4-re/` 不得作结论依据；本文所有结论改为 exe 地址 |

**高价值错误**：#9 / #10（漏掉两条资源路径）、#20（未引用装饰的数量）、
#24（两个特殊格计数 + 14/15 被误标为 "—"）、#30（GND `+0x08` 位宽）、
#3（主路径缺失）、#16/#27（把结构上限当成字段长度）。

---

## 八、未决清单（**不猜**）

@source `0x0040aa37`、`0x004091af`、`0x0041d160`、`0x00407ee4`、`0x00407f35`（各条的线索出处）

| # | 未决事项 | 已有线索 |
|---|---|---|
| U1 | `node+0x24`（`flags`）各**位**的语义；低字节是位域还是枚举 | 4 个掩码点见 §4.1；`0x0047606c` 的 24 项名表（无法证明按下标索引） |
| U2 | `land+0x1b` / `facility+0x1b` / `landscape+0x18` / `landscape+0x1b` 的语义 | land 唯一读点 `0x004091af`：`(8 - (v + [0x499088])) & 7` → `0x48a853` |
| U3 | `facility+0x26..0x2f`（文件里恒非 0）的字段划分与语义 | 本文未定位到读点（6 条指令窗口的启发式检索可能漏） |
| U4 | `landscape+0x1a` / `commercial+0x20` 的"资源号 = 值 + `0x26`"落在哪段资源；`0x48ae4c` 只有 5 槽却可能被更大值索引 | `0x00407ee4`、`0x00407f35` |
| U5 | `MAPDAT.MKF` 是谁生成的、内容格式是否与 `MAP.MKF[gm*2+1]` 相同 | 文件名仅在 `0x4631c8` 出现一次；发行版无此文件 |
| U6 | `MAP.MKF[0x19]`、`[0x205]`、`[0x207]`、`[0x18c+i]` 的内容与用途 | 分别存 `0x48aea8`、`0x48bad8`、`0x48bad4`、`0x496930[i]` |
| ~~U7~~ | ~~`0x48bad0` 与 `0x48badc` 为何读同一资源两遍~~ ✅ **已解（2026 本轮）**：**一份当精灵、一份当落点** | 见下方「小地图标记」小节 |
| U8 | SPR/SMP 磁盘上第 1..n 条 `graph_st` 记录的**数值**（`+0`/`+2`/`+8` 的字段序已由汇编坐实，但既有解包文件不可信） | 原始 `MAP.MKF` 可直接复算（见 §6.1 的反例） |
| U9 | `0x4991b6` / `0x4991b8` 是否真名 `game_stage` / `game_map` | 公式 `hi*4+lo` 已坐实；名称沿用线索 |
| U10 | `0x48b8c4` 收集的"对象 id"位域（`bit0..3`/`bit4..7`/`bit8..14`）各代表什么 | `0x0040ae85`、`0x0040aeb4`、`0x0040aee0` |

---

## 九、复核命令

```bash
cd rich4-spec
python3 tools/rich4dis.py func 0x407ad2          # 冷启动装载（§1/§2/§5.1）
python3 tools/rich4dis.py func 0x40af12          # 类型→表 分派（§三/§四）
python3 tools/rich4dis.py func 0x40aa0f          # 随机取空格（flags/adjacent）
sed -n '/^  00402e75/,/^  00402f90/p' gen/db.txt # 存档热启动（§5.2）
sed -n '/^  00407c3f/,/^  00407cc9/p' gen/db.txt # 头部解析 + map_data_size（§2）
python3 tools/scratch/map_verify.py              # 统计验证（§三/§六）
```

对照物（**只作线索，不得作结论依据**）：
`../rich4-remake/docs/map-format.md`（本文 §七 已逐条勘误）、
`../rich4-re/asm/rich4_load_map.asm`、`../tools/parse_map.py`（名称长度 16/24/24/24 的前身）。

@source `0x00407ad2`、`0x0040af12`、`0x0040aa0f`、`0x00402e75`、`0x00407c3f`

## ★ 写出侧覆盖一览（2026-09-17 机械对账，第 40 条）

复刻的 `map-writer.ts` 是否把解析侧读到的每个偏移都写回去了？逐表取差集：

| 表 | 解析到的偏移 | 写出的偏移 | 唯一没写 |
|---|---|---|---|
| 住宅地 | 11 | 11 | `+0x04` `name`（Big5）|
| 設施 | 13 | 12 | `+0x04` `name` |
| 企業 | 13 | 13 | `+0x04` `name` |
| 节点 | 4 | 6 | `+0x04` `name` |
| 景观 | 5 | 4 | `+0x04` `name` |

⇒ **除名字串之外已全覆盖**。名字是 Big5 字节，浏览器端没有 Big5 编码器
（见 `rich4-remake/packages/core/src/loaders/map-writer.ts` 开头），故只能由调用方
以 `carry` 提供原始字节 —— 对「读原版存档再写回」与「拿 `map.mkf` 的解包 `.bin`
当 carry」两条路都无影响，属**技术性缺口**而非漏做。

★ **企業表那四项是运行时字段，别当成静态数据**：
`+0x1c..0x1f` 持股排名、`+0x28` 累積盈餘（有符号，月分红清零）、
`+0x2c` 累計盈餘（有符号，不清零）、`+0x30` 自留股数（= `10000 − 流通股数`；
**静态地图文件里恒为 0**，只有存档/地图块里才是真值）。
写档前必须从 `GameState` 合并，否则写出的公司财务是装载时的旧值
（`rich4-remake` 的 `docs/gaps/README.md` §7.22）。

`@source` 企業字段偏移 `VA 0x47e7xx` 一带的地图记录布局见本文件 §企業表；
运行时赋值点：自留股数初值 `VA 0x00407dd1`（`10000 − 流通股数`）、
持股排名重排 `VA 0x004294d5`（`_rich4_update_commercial_owner`）、
每月 15 日分红后清零 `VA 0x0042ba97`。

