#!/usr/bin/env python3
"""
通道 2 差分测试 · **物件落点（神明 / 禮物）＋ 公佈欄天龄 ＋ 魔法屋效果派发**（四支）

| 目标 | VA | 真值尺寸 | 复刻归属 |
|---|---|---|---|
| 神明附身（类别 1..10、12 的跳表成员） | `0x0041b807` | **48 B** | `rules/object-landing.ts`（`applyObjectAt` 的 default 支）|
| 禮物（类别 13 的跳表成员） | `0x0041b8f9` | **531 B** | `rules/object-landing.ts`（`case OBJECT_TYPE_GIFT`）|
| 公佈欄槽「天龄 +1」 | `0x00428475` | **73 B** | `places/notice-board.ts`（**只写不读 ⇒ 复刻有意不建模**）|
| 魔法屋效果派发 | `0x00431caa` | **2,150 B** | `places/magic-house.ts` + `state/reduce.ts` |

## ★ 两处工作单尺寸订正（与 §7.141(4) 同族）

- `0x41b8f9` 工作单记 **521 B** = 切在 `0x41bb02`（`call 0x41d546` 那一句）**之前**；
  真身到 `0x41bb0b`（两条出口都是 `jmp`），共 **531 B**。本测试把尾巴一起驱动
  （NPC 支的 `refresh_map()` 就在那 10 字节里）。
- `0x431caa` 工作单记 **44 B** = 切在入口块末尾的 `jmp 0x4320b4`（循环条件）；
  真身是「跳表派发器」：入口块 + 4 项目标循环 + 12 路效果跳表 `0x431c7a`，
  到 `0x432510 ret` 共 **2,150 B**。本测试驱动**整支**（含 12 条效果支）。

## [A] `0x41b807`（类别 1..10/12 ⇒ 神明附身）

分派器 `0x41b42d` 的 18 项跳表 `0x41b3e5` 里，**12 项都指向 `0x41b807`**
（类别 1..10 与 12）—— 即「除了禮物/寶箱/路障/地雷/炸彈/惡犬/死神之外，
踩到的都是神明」（`OBJECT_TYPE_TABLE` 下标 0..13 → 类别 1..14）。

```asm
0041b807  mov  edx, [0x49910c]        ; 当前行动者
0041b80d  cmp  edx, 4 / jge 0x41c164  ; ★ >= 4（替身/惡人）⇒ 不附身
0041b816  cmp  dword [0x48baf8], 0
0041b81d  jne  0x41c164               ; ★ 还在移动中 ⇒ 不附身
0041b823  mov  ebx, [esp+0xa4]        ; ★ 物件槽号（分派器帧内量）
0041b82a  push ebx / push esi / push edx
0041b82d  call 0x40ead7               ; attach_object(player, 节点号=esi, 槽号)
0041b832  jmp  0x41bb95               ; add esp,0xc → jmp 0x41c164（收尾）
```

## [B] `0x41b8f9`（类别 13 ⇒ 禮物）

```asm
; ── 真人支（cur < 4 且 [0x48baf8]==0）──
0041b914  push eax / call 0x445ada    ; ★ 按库存加权抽一个道具（1..8），
                                      ;   并把道具**发到玩家手里**（内部 call 0x445a4d）
0041b91f  test eax,eax / je 0x41c164  ; 抽不到（袋子空）⇒ 什么都不做
0041b92e  call 0x4542ce               ; 音效 0x48237a
0041b936  push 0xd / call 0x40e14d    ; ★ **写死的槽 13**（类别 13 只可能在槽 13）
0041b946  call 0x41d476               ; 落点事务 (0,0,1)
0041b960  sprintf(buf,"得到%s！", dword[工具表 + 号*8 + 0])   ; 0x47feda 工具表
0041b972  call 0x440cac               ; show(text, 0x5dc)
0041b98b  call 0x44f230               ; 台词 (玩家, byte[工具表 + 号*8 + 5] = 工具标价)
0041b990  jmp  0x41c161               ; add esp,8 → 0x41c164

; ── NPC 支（cur == 4，★ 不看 [0x48baf8]）──
0041b995  mov ecx,[0x49910c] / cmp ecx,4 / jne 0x41c164   ; 只认 ==4
0041b9a9  cmp byte[0x498df5], 0 / jne 0x41c164            ; 替身冻结（槽 +0x0d）跳过
0041b9b8  call 0x40e14d(0xd)          ; ★ 先移除，**再**抽
0041b9c6  call 0x41d476(0,0,1)
0041b9f3  call 0x452946 + sprintf(…, 0x463ac0, [0x47edaa], 名字)  ; 第一句
0041ba2a  call 0x4542e9               ; ★ 另一支音效
0041ba3c  call 0x440cac(…, 0x5dc)
0041ba58  call 0x445ada(●**占用者**)   ; 抽给主人，不是替身
0041ba64  test eax,eax / je 0x41be38  ; 抽不到 ⇒ 后半段不做（但前半段已发生！）
0041ba71  call 0x4542ce(0, 0x48237a)
0041baa8  call 0x41d476(word[占据者+8], word[占据者+0xa], 0)   ; ★ 带坐标的事务
0041bac2  sprintf(buf,"得到%s！", 工具名) / show
0041bafa  call 0x44f230(占用者, 工具标价)
0041bb02  call 0x41d546               ; refresh_map
0041bb07  jmp  0x41be38
```

## [C] `0x428475`（公佈欄每槽「天龄 +1」）

```asm
fcn_00428475:
  for (esi = 0; esi < [0x499114]; esi++)      ; ★ 上界 = 人数
    if (byte[player + 0x15] == 0) continue    ; ★ 整字节判据（不是 & 3）
    for (edx = 0; edx < 7; edx++)             ; ★ 恰 7 槽
      if (byte[0x4967e0 + esi*0x54 + edx*12] == 0) continue   ; 空槽跳过
      byte[0x4967e1 + esi*0x54 + edx*12] += 1                 ; ★ 唯一写入
```

★ 唯一调用点是 `0x41cfc4`（日期推进那一支：同段紧跟 `inc [0x4990e4]` 与
`call 0x423acf`）。`0x4967e1` 全 exe 只有「挂零」与「+1」两个写点、**零个读点**
⇒ `places/notice-board.ts:40-61` 有意不建这个字段（等价省略）。本测试驱动真值，
把那 12 条结论钉住。

## [D] `0x431caa`（魔法屋效果派发，`arg0 = 效果转盘落点 0..11`）

```asm
fcn_00431caa:                            ; 唯一调用点 0x004339c6（转盘）
  Prologue(push×4, sub esp,0xb4)
  esi = arg0                             ; 效果编号
  [0x48be18] = 0                         ; ★ 清「需要重绘地图」标志
  [esp+0xb0] = [0x49910c]                ; ★ 存档当前玩家，收尾还原
  for (edi = 0; edi < 4; edi++) {                    ; 0x4320aa
    if (byte[0x48c380 + edi] == 0) break;            ; ★ 空槽 = **结束整个循环**
    [0x49910c] = byte[0x48c380 + edi] - 1;           ; 名单 1 基 → 0 基
    if (esi > 0xb) continue;                         ; 越界效果 ⇒ 跳过此人
    jmp [esi*4 + 0x431c7a];                          ; 12 路效果跳表
  }
  [0x49910c] = [esp+0xb0]; add esp,0xb4; pop×4; ret  ; 0x4324fa
```

| idx | 入口 | 规则（本测试钉住的） |
|---|---|---|
| 0 | `0x431cd6` | `0x441f21(cur)` 变卖所有卡 ⇒ `add **word** [cur+0x30], ax`（16 位回绕）|
| 1 | `0x431d65` | `for (ebx=0..2) call 0x44db81` —— 恰 3 次命运 |
| 2 | `0x431dcc` | 敌意 `0x40df69(cur, 发起者, 90×物價)` + `0x441210(cur)` ⇒ `if (≠ −1) 坐牢(eax, 3)` |
| 3 | `0x431e75` | `byte[cur+0x38] = (byte[cur+0x38] + 1) & 0x7f` |
| 4 | `0x431eef` | `[cur+0x20] += [cur+0x1c]; [cur+0x1c] = 0` |
| 5 | `0x431f67` | `dword[cur+0x32]!=0 ⇒ 跳`；节点值 ∈ (2000, 6000) ⇒ `0x40b110(值)` 免费加盖 |
| 6 | `0x4320dd` | `0x441e12(cur)`（按牌堆加权抽卡）|
| 7 | `0x432160` | `dword[cur+0x32]!=0 ⇒ 跳`；否则 ★ **`call 0x40c78c`（完整掉头）** |
| 8 | `0x4321f0` | `0x445b3f(cur)` 变卖所有道具 ⇒ `add word [cur+0x30], ax` |
| 9 | `0x432259` | 同 5 的门槛/值域 ⇒ `0x40ab4a(值, 0)` 就地拆除 |
| 10 | `0x432384` | 同 2 ⇒ `0x43ec3f(eax, 3)` 住院 |
| 11 | `0x43242b` | 同 5 ⇒ `0x43bde5(cur, 值, 1)` 开拍卖（卖方 = 中签者自己）|

★ **12 条支全部整支驱动**（本文件 `[D]` 段），逐条断言「调了谁、实参是什么、
改了哪个字段」；越界（12 / 255）走 `ja 0x4320aa` ⇒ 只推进循环、零副作用。

## 驱动手法

`[A]`/`[B]` 是**跳表成员（无 prologue、无返回地址）**，用 `eval_block` + 手搓帧：

* `0x41c164`（分派器的收尾汇合点）打成 **`ret`**（1 字节 `C3`）；
  于是每条出口的 `jmp 0x41c161`（先 `add esp,8`）或 `jne 0x41c164` 都落到这个 `ret`，
  ESP 恰好回到 `STACK_TOP`，弹出 `eval_block` 预置的 `RET_SENTINEL` ⇒ 停址 = `RET_SENTINEL`。
* `[A]` 的帧内量：`[STACK_TOP+0xa4]` = 物件槽号、`esi` = 节点号。
* ⚠️ **`sprintf` 的目标就是 `[STACK_TOP]`**（`0x41b95b lea eax,[esp+8]`），
  所以 `0x457110`/`0x440cac` **必须打桩**，否则返回地址被台词文本覆盖。

`[C]`/`[D]` 是**正函数入口**（有 prologue 与 `ret`），直接 `emu.call()`。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x0040ead7` | `attach_object(player, 节点, 槽)` | 记 3 实参 + 计数 + `ret` |
| `0x00445ada` | 按库存抽道具（**并发到手里**） | 从数据槽读返回值 + 记实参 |
| `0x0040e14d` | `remove_object(槽号)` | 记 1 实参 |
| `0x0041d476` | 落点事务（3 实参） | 按调用序记 3 实参 |
| `0x004542ce`/`0x004542e9` | 两支音效 | 计数 |
| `0x00440cac` | 显示文字框 | 按调用序记 2 实参 |
| `0x00457110` | `sprintf`（CRT 深处不可仿真） | 按调用序记 3 实参 |
| `0x0044f230` | 卡片/道具台词（3 档） | 按调用序记 2 实参 |
| `0x00452946` | 去空格拷贝名字 | 记 2 实参 |
| `0x0041d546` | `refresh_map()`（走 DirectDraw vtable） | 计数 |
| `0x0041906a` | 暂停 / 切换输入 | 记 1 实参 |
| `0x00441210` | 免罪(21)/嫁禍(19) 闸门 ⇒ 返回替罪者或 −1 | 从数据槽读返回值 |
| `0x0043d593`/`0x0043ec3f` | 送監獄 / 送醫院 (玩家, 天数) | 记 2 实参 |
| `0x0040df69` | `update_hostility(a, b, delta)` | 按调用序记 3 实参 |
| `0x0044db81` | 抽一张命運 | 计数 |
| `0x00441f21`/`0x00445b3f` | 变卖所有卡 / 所有道具（返回得点） | 记 1 实参 + 从数据槽返回 |
| `0x00441e12` | 按牌堆加权抽一张卡 | 记 1 实参 + 从数据槽返回 |
| `0x004582fc` | 字符串拷贝 | 记 2 实参 |
| `0x0041d433`/`0x0045285e` | 切面板重画 / 延时 | 记 1 实参 |
| `0x0040b110`/`0x0040ab4a` | 加盖 / 拆除 | 记实参 + 从数据槽返回 |
| `0x0040af12` | 取节点名与坐标（★ 写两个输出缓冲） | 记 3 实参 + 往 2/3 参指向的缓冲写哨兵值 |
| `0x00450441`/`0x0045144f`/`0x00456e11` | MKF 装载 / 贴图 / 卸载 | 记实参 + 计数 |
| `0x0040b0cd` | 「剛好升到 5 級」特效 | 计数 |
| `0x0043bde5` | `run_auction(卖方, 値, 1)` | 记 3 实参 |
| `0x0044ef41` | `player_say(玩家, 槽, 串)` | 记 3 实参 |
| `0x00456f2d` | CRT `rand()` | 从数据槽读返回值 + **计数**（钉随机消费）|
| `0x0041c164` | 落点分派器收尾汇合点 | **打成 `ret`**（见上）|

**未打桩（真跑）**：`0x40c78c`（**完整掉头** —— 見 `[D]` 的「7 向後轉」一組：
正因为它顺手把来路 `last_node` 重挑成随机邻居，这条才是与复刻的分歧点，
见 `rich4-remake/packages/core/src/places/magic-house.ts:381-387`）。

跑法：cd rich4-spec && .venv/bin/python tests/test_object_landing_batch.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import RET_SENTINEL, SCRATCH_BASE, STACK_TOP, STUB_BASE, Emu  # noqa: E402

# ── 被测入口 ────────────────────────────────────────────────────────────
GOD = 0x41B807                  # 类别 1..10/12 神明附身（跳表 0x41b3e5 的 12 个成员）
GIFT = 0x41B8F9                 # 类别 13 禮物（跳表 0x41b3e5[12]）
BOARD = 0x428475                # 公佈欄每槽天龄 +1（正函数）
MAGIC = 0x431CAA                # 魔法屋效果派发（正函数，2150 B）

# ── 被调函数（全部打桩） ────────────────────────────────────────────────
ATTACH = 0x40EAD7
DRAWGIFT = 0x445ADA
REMOVE = 0x40E14D
TXN = 0x41D476
SND1, SND2 = 0x4542CE, 0x4542E9
SHOW = 0x440CAC
FMT = 0x457110
SPEAK = 0x44F230
STRIP = 0x452946
REFRESH = 0x41D546
PAUSE = 0x41906A
SELMASK = 0x441210
PRISON, HOSPITAL = 0x43D593, 0x43EC3F
HOSTILITY = 0x40DF69
DRAW_FORTUNE = 0x44DB81
SELL_CARDS, SELL_TOOLS, DRAW_CARD = 0x441F21, 0x445B3F, 0x441E12
STRCPY = 0x4582FC
WALLET, SLEEP = 0x41D433, 0x45285E
BUILD, DEMOLISH, NODENAME = 0x40B110, 0x40AB4A, 0x40AF12
AUCTION = 0x43BDE5
LOAD, BLIT, FREE = 0x450441, 0x45144F, 0x456E11
BUILDFX = 0x40B0CD
PLAYER_SAY = 0x44EF41
PRNG = 0x456F2D
EXIT_JOIN = 0x41C164             # 分派器收尾汇合点（打成 ret）

# ── 全局量 ──────────────────────────────────────────────────────────────
CUR = 0x49910C
BUSY = 0x48BAF8
NUM_PLAYERS = 0x499114
PRICE_INDEX = 0x4990E8
REFRESH_FLAG = 0x48BE18
MAGIC_LIST = 0x48C380            # 魔法屋目标名单（1 基，0 = 结束）
NODE_ARRAY = 0x498E80
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10
A_OWNER, A_SLEEP = 0x08, 0x0D
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHOPLAYS = 0x15
P_XPOS, P_YPOS = 0x08, 0x0A
P_NODE, P_LAST, P_FACING = 0x0C, 0x0E, 0x10
P_CASH, P_BANK, P_POINTS, P_BLOCK, P_STOP = 0x1C, 0x20, 0x30, 0x32, 0x38
BOARD_BASE, BOARD_STRIDE, BOARD_SLOT = 0x4967E0, 0x54, 12
BOARD_SLOTS = 7
TOOL_TABLE = 0x47FEDA            # 工具表：+0 名字指针 / +4 初始量 / +5 标价
NODE_STRIDE = 0x28
N_ADJ, N_TYPE, N_FLAGS = 0x18, 0x20, 0x24

# ── 暂存区布局（跨调用保留 ⇒ 每次 setup 必须清零） ──────────────────────
S = SCRATCH_BASE
VAL_BASE, VAL_SIZE = S + 0x1000, 0x1000
REC_BASE, REC_SIZE = S + 0x3000, 0x4000
CNT_BASE, CNT_SIZE = S + 0x9000, 0x800
NODES = S + 0xA000
NODES_SIZE = 0x1000
STUB_AREA = STUB_BASE + 0x100
SENTINEL = 0x5A5A5A5A
P_FMT_GOT = 0x463AA8             # "得到%s！"
P_FMT_NAME = 0x46482A
P_FMT_OPT = 0x463AC0
P_FMT_CARD = 0x464839
P_SAY_DONE = 0x46482F

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<72} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def _inc(slot):
    return b"\xFF\x05" + struct.pack("<I", slot)


class Stubs:
    """把被调函数替换成「记实参 + 可配返回值」的小桩，桩体放在 `0x4C0000` 段。"""

    def __init__(self, emu):
        self.emu = emu
        self.next = STUB_AREA
        self.index = {}

    def _slot(self, name):
        if name not in self.index:
            i = len(self.index)
            self.index[name] = i
        return self.index[name]

    def val(self, name):
        return VAL_BASE + 8 * self._slot(name)

    def cnt(self, name):
        return CNT_BASE + 8 * self._slot(name)

    def rec(self, name, i, n):
        base = REC_BASE + 0x200 * self._slot(name)
        return [self.emu.readu32(base + 0x20 * i + 4 * k) for k in range(n)]

    def n(self, name):
        return self.emu.readu32(self.cnt(name))

    def _emit(self, code):
        va = self.next
        self.next += (len(code) + 0xF) & ~0xF
        self.emu.patch(va, bytes(code))
        return va

    def install(self, va, nargs, name, ret=True):
        """桩：记录 `nargs` 个实参（按调用序），`ret` ⇒ 从 `VAL(name)` 返回。"""
        rec, cnt = REC_BASE + 0x200 * self._slot(name), self.cnt(name)
        code = b"\x53\x56\x57\x55"                       # push ebx/esi/edi/ebp
        code += b"\x8B\x1D" + struct.pack("<I", cnt)     # mov ebx,[cnt]
        code += b"\xC1\xE3\x05"                          # shl ebx,5
        for k in range(nargs):
            code += b"\x8B\x44\x24" + bytes([0x14 + 4 * k])
            code += b"\x89\x83" + struct.pack("<I", rec + 4 * k)
        code += _inc(cnt)
        code += b"\x5D\x5F\x5E\x5B"                      # pop ebp/edi/esi/ebx
        if ret:
            code += b"\xA1" + struct.pack("<I", self.val(name))
        else:
            code += b"\x31\xC0"
        code += b"\xC3"
        body = self._emit(code)
        rel = (body - (va + 5)) & 0xFFFFFFFF
        self.emu.patch(va, b"\xE9" + struct.pack("<I", rel))

    def install_nodename(self, va):
        """`0x40af12(值, 缓冲A, 缓冲B)`：桩把 A/B 各写一个可断言的哨兵。"""
        name = "nodename"
        rec, cnt = REC_BASE + 0x200 * self._slot(name), self.cnt(name)
        code = b"\x53"                                   # push ebx
        code += b"\x8B\x1D" + struct.pack("<I", cnt)
        code += b"\xC1\xE3\x05"
        code += b"\x8B\x44\x24\x08"                      # mov eax,[esp+8]  = arg1
        code += b"\x89\x83" + struct.pack("<I", rec)
        code += b"\x8B\x4C\x24\x0C"                      # mov ecx,[esp+0xc] = arg2
        code += b"\xC7\x01" + struct.pack("<I", 0x1111)  # mov dword [ecx], 0x1111
        code += b"\x8B\x54\x24\x10"                      # mov edx,[esp+0x10] = arg3
        code += b"\xC7\x02" + struct.pack("<I", 0x2222)  # mov dword [edx], 0x2222
        code += _inc(cnt)
        code += b"\x5B\x31\xC0\xC3"                      # pop ebx / xor eax,eax / ret
        body = self._emit(code)
        rel = (body - (va + 5)) & 0xFFFFFFFF
        self.emu.patch(va, b"\xE9" + struct.pack("<I", rel))


class World:
    def __init__(self):
        self.emu = Emu()
        self.st = Stubs(self.emu)
        self.emu.patch(EXIT_JOIN, b"\xC3")               # ★ 收尾汇合点 → ret
        s = self.st
        s.install(ATTACH, 3, "attach")
        s.install(DRAWGIFT, 1, "drawgift")
        s.install(REMOVE, 1, "remove")
        s.install(TXN, 3, "txn")
        s.install(SND1, 0, "snd1", ret=False)
        s.install(SND2, 0, "snd2", ret=False)
        s.install(SHOW, 2, "show", ret=False)
        s.install(FMT, 3, "fmt", ret=False)
        s.install(SPEAK, 2, "speak", ret=False)
        s.install(STRIP, 2, "strip", ret=False)
        s.install(REFRESH, 0, "refresh", ret=False)
        s.install(PAUSE, 1, "pause", ret=False)
        s.install(SELMASK, 0, "selmask")
        s.install(PRISON, 2, "prison", ret=False)
        s.install(HOSPITAL, 2, "hosp", ret=False)
        s.install(HOSTILITY, 3, "hostility", ret=False)
        s.install(DRAW_FORTUNE, 0, "drawfortune", ret=False)
        s.install(SELL_CARDS, 1, "sellcards")
        s.install(SELL_TOOLS, 1, "selltools")
        s.install(DRAW_CARD, 1, "drawcard")
        s.install(STRCPY, 2, "strcpy", ret=False)
        s.install(WALLET, 1, "wallet", ret=False)
        s.install(SLEEP, 1, "sleep", ret=False)
        s.install(BUILD, 1, "build")
        s.install(DEMOLISH, 2, "demolish", ret=False)
        s.install_nodename(NODENAME)
        s.install(AUCTION, 3, "auction", ret=False)
        s.install(LOAD, 4, "load", ret=False)
        s.install(BLIT, 4, "blit", ret=False)
        s.install(FREE, 1, "free", ret=False)
        s.install(BUILDFX, 0, "buildfx", ret=False)
        s.install(PLAYER_SAY, 3, "say", ret=False)
        s.install(PRNG, 0, "rand")

    # ── 公共 setup ──────────────────────────────────────────────────
    def _clear(self, emu, vals):
        emu.write(REC_BASE, b"\x00" * REC_SIZE)
        emu.write(CNT_BASE, b"\x00" * CNT_SIZE)
        emu.write(VAL_BASE, b"\x00" * VAL_SIZE)
        emu.write(NODES, b"\x00" * NODES_SIZE)
        for name, v in vals.items():
            # 用无符号写：−1 这类哨兵值走 write32 会因 struct "<i" 溢出
            emu.write(self.st.val(name), struct.pack("<I", v & 0xFFFFFFFF))

    # ── [A]/[B] 跳表片段 ────────────────────────────────────────────
    def run_frag(self, entry, *, cur=0, busy=0, node=5, slot=1, actor_owner=0,
                 actor_x=0, actor_y=0, actor_sleep=0, vals=None):
        vals = dict(vals or {})

        def setup(emu):
            self._clear(emu, vals)
            emu.write32(CUR, cur)
            emu.write32(BUSY, busy)
            for off, v in ((0xA4, slot), (0x9C, 0), (0xA0, 0), (0x98, 0)):
                emu.write32(STACK_TOP + off, v)
            emu.write32(NODE_ARRAY, NODES)
            if cur >= 4:
                ab = ACTOR_BASE + (cur - 4) * ACTOR_STRIDE
                emu.write8(ab + A_OWNER, actor_owner)
                emu.write8(ab + A_SLEEP, actor_sleep)
            pb = PLAYER_BASE + actor_owner * PLAYER_STRIDE
            emu.write16(pb + P_XPOS, actor_x)
            emu.write16(pb + P_YPOS, actor_y)

        self.emu.eval_block(entry, RET_SENTINEL, {"esi": node}, setup=setup)

    # ── [C] 公佈欄天龄 ───────────────────────────────────────────────
    def run_board(self, *, who=(2, 2, 2, 2), num=4, kinds=None, ages=None,
                  tail=None):
        """kinds[p] = 7 个槽的「类型」字节；ages[p] = 7 个槽的「天龄」初值。"""
        kinds = kinds or [[1, 1, 1, 1, 1, 1, 1] for _ in range(4)]
        ages = ages or [[10] * BOARD_SLOTS for _ in range(4)]
        tail = tail or {}

        def setup(emu):
            emu.write32(NUM_PLAYERS, num)
            for p in range(4):
                emu.write8(PLAYER_BASE + p * PLAYER_STRIDE + P_WHOPLAYS, who[p])
                for sl in range(BOARD_SLOTS):
                    b = BOARD_BASE + p * BOARD_STRIDE + sl * BOARD_SLOT
                    emu.write8(b + 0, kinds[p][sl])
                    emu.write8(b + 1, ages[p][sl])
                    emu.write(b + 2, b"\xAA" * 10)          # +2..+0b 哨兵
            for va, v in tail.items():
                emu.write8(va, v)

        self.emu.call(BOARD, [], setup=setup)

    def board_age(self, p):
        return [self.emu.read8(BOARD_BASE + p * BOARD_STRIDE + sl * BOARD_SLOT + 1)
                for sl in range(BOARD_SLOTS)]

    # ── [D] 魔法屋效果派发 ───────────────────────────────────────────
    def run_magic(self, option, *, targets=(1,), cur=0, pi=2,
                  cash=(1000, 2000, 3000, 4000), bank=(10, 20, 30, 40),
                  points=(5, 6, 7, 8), stop=(0x7E, 0x7F, 0x80, 0x81),
                  facing=(1, 2, 3, 4), blocking=(0, 0, 0, 0),
                  node=(10, 20, 30, 40), node_type=(2001, 4000, 1999, 0x1770),
                  adj=None, flags=0, vals=None):
        vals = dict(vals or {})

        def setup(emu):
            self._clear(emu, vals)
            for i in range(4):
                emu.write8(MAGIC_LIST + i, targets[i] if i < len(targets) else 0)
            emu.write32(CUR, cur)
            emu.write32(PRICE_INDEX, pi)
            emu.write8(REFRESH_FLAG, 0x5A)                 # ★ 入口应清 0
            for i in range(4):
                pb = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write32(pb + P_CASH, cash[i] & 0xFFFFFFFF)
                emu.write32(pb + P_BANK, bank[i] & 0xFFFFFFFF)
                emu.write16(pb + P_POINTS, points[i] & 0xFFFF)
                emu.write8(pb + P_STOP, stop[i])
                emu.write8(pb + P_FACING, facing[i])
                emu.write16(pb + P_NODE, node[i])
                emu.write16(pb + P_LAST, 0)
                emu.write32(pb + P_BLOCK, blocking[i])
            emu.write32(NODE_ARRAY, NODES)
            for i, t in enumerate(node_type):
                emu.write16(NODES + node[i] * NODE_STRIDE + N_TYPE, t)
            if adj is not None:
                for sl in range(4):
                    emu.write16(NODES + node[0] * NODE_STRIDE + N_ADJ + sl * 2, adj[sl])
                emu.write32(NODES + node[0] * NODE_STRIDE + N_FLAGS, flags)

        self.emu.call(MAGIC, [option], setup=setup)

    def mag(self, addr):
        return self.emu.read8(addr)

    def player(self, i, off, size=32):
        va = PLAYER_BASE + i * PLAYER_STRIDE + off
        return {8: self.emu.read8, 16: self.emu.read16, 32: self.emu.readu32}[size](va)


def main():
    w = World()
    e = w.emu
    st = w.st

    # ════════════════════════════════════════════════════════════════
    print("[A] 0x41b807（类别 1..10/12 ⇒ 神明附身）：门槛 + 三个实参来源")
    print("    `0x40ead7(player, 节点号, 槽号)` —— 玩家取 [0x49910c]、节点取 esi、槽号取 [esp+0xa4]")

    w.run_frag(GOD, cur=0, busy=0, node=33, slot=7)
    case("cur=0 且不在移动中 ⇒ attach 恰 1 次", st.n("attach"), 1)
    case("  实参 = (玩家 0, 节点 33=esi, 槽 7=[esp+0xa4])", st.rec("attach", 0, 3), [0, 33, 7])

    w.run_frag(GOD, cur=3, busy=0, node=44, slot=12)
    case("cur=3 / node=44 / 槽 12 ⇒ 三个实参各自跟着来源走",
         st.rec("attach", 0, 3), [3, 44, 12])

    w.run_frag(GOD, cur=0, busy=1, node=33, slot=7)
    case("★ 移动中（[0x48baf8] != 0）⇒ 一次都不调", st.n("attach"), 0)

    for c in (4, 5, 7):
        w.run_frag(GOD, cur=c, busy=0, node=33, slot=7)
        case(f"★ cur={c}（替身/惡人段）⇒ 一次都不调", st.n("attach"), 0)

    seen = []
    for c in range(4):
        w.run_frag(GOD, cur=c, busy=0, node=1, slot=2)
        seen.append(st.n("attach"))
    case("★ 四名真人（0..3）**全部**接受（只有 >=4 被挡）", seen, [1, 1, 1, 1])

    w.run_frag(GOD, cur=1, busy=0, node=9, slot=9)
    case("  副作用：当前玩家不被改动", e.readu32(CUR), 1)
    case("  副作用：忙标志不被改动", e.readu32(BUSY), 0)

    # ════════════════════════════════════════════════════════════════
    print("\n[B] 0x41b8f9（类别 13 ⇒ 禮物）：真人支 / NPC 支 / 抽不到 / 冻结")
    print("    真人支 = 抽（0x445ada，顺带把道具发到手里）→ 移除**写死的槽 13** → 事务 → 台词")

    w.run_frag(GIFT, cur=0, busy=0, node=9, slot=9, vals={"drawgift": 3})
    case("★ 真人支：移除的是**写死的槽 13**（帧里给 9 也一样）",
         (st.n("remove"), st.rec("remove", 0, 1)), (1, [13]))
    case("  落点事务恰 1 次且 = (0,0,1)",
         (st.n("txn"), st.rec("txn", 0, 3)), (1, [0, 0, 1]))
    case("  show 恰 1 次、文本指针 = [STACK_TOP]（sprintf 的目标）、时长 0x5dc",
         (st.n("show"), st.rec("show", 0, 2)), (1, [STACK_TOP, 0x5DC]))
    case("  sprintf 目标同在 [STACK_TOP]、格式 = 0x463aa8「得到%s！」",
         st.rec("fmt", 0, 3)[:2], [STACK_TOP, P_FMT_GOT])
    case("★ 名字指针 = dword[工具表 + 3*8]（0x47feda 真表）",
         st.rec("fmt", 0, 3)[2], e.readu32(TOOL_TABLE + 8 * 3))
    case("★ 台词 = (当前玩家 0, byte[工具表 + 3*8 + 5])，工具 3 = 地雷 标价 25",
         st.rec("speak", 0, 2), [0, 25])
    case("  音效 0x4542ce×1、★ 0x4542e9 与 refresh_map 都不调（那是 NPC 支的）",
         (st.n("snd1"), st.n("snd2"), st.n("refresh")), (1, 0, 0))
    case("★ 道具**不是**由本片段发的（0x445ada 内部 call 0x445a4d）⇒ receive 0 次",
         st.n("receive"), 0)

    w.run_frag(GIFT, cur=2, busy=0, node=9, slot=13, vals={"drawgift": 5})
    case("★ 工具 5 = 機車 标价 80（不是卡表那一列 29/…）—— 台词取 byte[0x47fedf+40]",
         (st.rec("speak", 0, 2), e.read8(0x47FEDF + 8 * 5)), ([2, 80], 80))

    w.run_frag(GIFT, cur=1, busy=0, node=9, slot=13, vals={"drawgift": 0})
    case("★ 抽不到（返回 0）⇒ 只有抽这一次，后面全不发生",
         (st.n("drawgift"), st.rec("drawgift", 0, 1), st.n("remove"), st.n("txn"),
          st.n("show"), st.n("speak")), (1, [1], 0, 0, 0, 0))

    w.run_frag(GIFT, cur=0, busy=1, node=9, slot=13, vals={"drawgift": 3})
    case("★ 真人 + 移动中 ⇒ 连抽都不抽（0x41b90e→0x41b995→cur!=4→收尾）",
         (st.n("drawgift"), st.n("remove")), (0, 0))

    w.run_frag(GIFT, cur=8, busy=0, node=9, slot=13, vals={"drawgift": 3})
    case("★ cur=8（機器娃娃）⇒ 整支不处理", (st.n("drawgift"), st.n("remove")), (0, 0))

    # ── NPC 支（cur == 4）──
    w.run_frag(GIFT, cur=4, busy=0, node=9, slot=13, actor_owner=2, actor_x=0x1234,
               actor_y=0x5678, vals={"drawgift": 3})
    case("★ NPC 支：照样移除槽 13", (st.n("remove"), st.rec("remove", 0, 1)), (1, [13]))
    case("★★ 事务**两次**：先 (0,0,1)、再 (主人 xpos, 主人 ypos, 0)",
         (st.n("txn"), st.rec("txn", 0, 3), st.rec("txn", 1, 3)),
         (2, [0, 0, 1], [0x1234, 0x5678, 0]))
    case("  show 两次 / 名字去空格 1 次", (st.n("show"), st.n("strip")), (2, 1))
    case("★ 抽道具用的是**主人**（2），不是替身号 4",
         (st.n("drawgift"), st.rec("drawgift", 0, 1)), (1, [2]))
    case("★ 台词 = (主人 2, 标价 25)", st.rec("speak", 0, 2), [2, 25])
    case("★ 后半段的音效是 0x4542e9（与真人支的 0x4542ce 不同）、并调 refresh_map",
         (st.n("snd2"), st.n("refresh")), (1, 1))
    case("  两条 sprintf：先 0x463ac0（带名字），后 0x463aa8「得到%s！」",
         [st.rec("fmt", 0, 3)[1], st.rec("fmt", 1, 3)[1]], [P_FMT_OPT, P_FMT_GOT])

    w.run_frag(GIFT, cur=4, busy=1, node=9, slot=13, actor_owner=2,
               vals={"drawgift": 3})
    case("★★★ 替身支**不看**忙标志（`jge 0x41b995` 后只判 cur==4）⇒ 照样跑完",
         (st.n("remove"), st.n("speak"), st.n("refresh")), (1, 1, 1))

    w.run_frag(GIFT, cur=4, busy=0, node=9, slot=13, actor_owner=2,
               vals={"drawgift": 0})
    case("★★ 抽不到时：**前半段照样发生**（移除/事务/show/名字），后半段不做",
         (st.n("remove"), st.n("txn"), st.n("show"), st.n("fmt"),
          st.n("speak"), st.n("refresh")), (1, 1, 1, 1, 0, 0))

    w.run_frag(GIFT, cur=4, busy=0, node=9, slot=13, actor_owner=2, actor_sleep=1,
               vals={"drawgift": 3})
    case("★ 替身冻结中（槽 +0x0d != 0）⇒ 整支跳过", st.n("remove"), 0)

    w.run_frag(GIFT, cur=5, busy=0, node=9, slot=13, actor_owner=2,
               vals={"drawgift": 3})
    case("★ cur=5（強盜）⇒ 只认 `== 4`，整支跳过", st.n("remove"), 0)

    # ════════════════════════════════════════════════════════════════
    print("\n[C] 0x428475（公佈欄每槽天龄 +1）：上界/判据/步长/只写不读")
    K = [[0, 1, 2, 0, 1, 2, 0], [1, 1, 1, 1, 1, 1, 1],
         [2, 0, 2, 0, 2, 0, 2], [1, 1, 1, 1, 1, 1, 1]]
    w.run_board(kinds=K, who=(2, 2, 2, 2), num=4)
    case("★ 占用的槽 +1、空槽不动（玩家 0 的模式 0/1/2/0/1/2/0 ⇒ 只 1/2/4/5 加）",
         w.board_age(0), [10, 11, 11, 10, 11, 11, 10])
    case("  同为占用（全 1）⇒ 全 +1", w.board_age(1), [11] * BOARD_SLOTS)
    case("  另一个模式逐槽核对", w.board_age(2), [11, 10, 11, 10, 11, 10, 11])

    w.run_board(kinds=K, who=(2, 0, 2, 2), num=4)
    case("★ whoPlays == 0（出局）⇒ 该玩家七个槽一个都不动", w.board_age(1), [10] * BOARD_SLOTS)
    case("  别的玩家照加（只跳过出局者）", w.board_age(2), [11, 10, 11, 10, 11, 10, 11])

    w.run_board(kinds=K, who=(4, 2, 2, 2), num=4)
    case("★★ whoPlays = 4（只剩 bit2，整字节非 0）⇒ **照样记龄**（判据不是 & 3）",
         w.board_age(0), [10, 11, 11, 10, 11, 11, 10])

    w.run_board(kinds=K, who=(2, 2, 2, 2), num=2)
    case("★ 循环上界 = [0x499114]：人数 = 2 ⇒ 玩家 2/3 全不动",
         (w.board_age(2), w.board_age(3)), ([10] * BOARD_SLOTS, [10] * BOARD_SLOTS))

    w.run_board(kinds=K, who=(2, 2, 2, 2), num=0)
    case("  人数 = 0 ⇒ 一个都不动（边界）", w.board_age(0), [10] * BOARD_SLOTS)

    w.run_board(kinds=[[0, 0, 0, 0, 0, 0, 0]] + K[1:], who=(2, 2, 2, 2), num=4)
    case("  全空 ⇒ 玩家的天龄一列不动（第一个槽也要判）",
         w.board_age(0), [10] * BOARD_SLOTS)
    w.run_board(kinds=[[1, 0, 0, 0, 0, 0, 0]] + K[1:], who=(2, 2, 2, 2), num=4)
    case("★ 只占**槽 0** ⇒ 槽 0 加 1（没有 off-by-one 跳过首槽）",
         w.board_age(0), [11, 10, 10, 10, 10, 10, 10])

    # 恰 7 槽：伪造一个「第 8 槽」在玩家 3 之后
    fake = BOARD_BASE + 3 * BOARD_STRIDE + BOARD_SLOTS * BOARD_SLOT
    w.run_board(kinds=K, who=(2, 2, 2, 2), num=4, tail={fake: 1, fake + 1: 77})
    case("★ 恰 7 槽：玩家表之后那一格（伪槽 7）**不被写**（读取 = 77）",
         e.read8(fake + 1), 77)
    case("  步长证据：玩家 1 的槽 0 与玩家 0 的槽 7 同址，两者都按各自玩家口径处理",
         (w.board_age(0)[0], w.board_age(1)[0]), (10, 11))

    w.run_board(kinds=K, who=(2, 2, 2, 2), num=4)
    case("★ 只动 +1 一字节：槽 +2..+0b 的哨兵 0xAA 原样",
         [e.read8(BOARD_BASE + 0 * BOARD_STRIDE + sl * BOARD_SLOT + 2)
          for sl in range(BOARD_SLOTS)], [0xAA] * BOARD_SLOTS)

    # ★ 「读旧值再写」：天龄初值 0xFF ⇒ 加一后**字节回绕成 0**
    #   （若实现是「写成常数」而不是 `inc`，这里会得到 11 而不是 0）
    w.run_board(kinds=K, who=(2, 2, 2, 2), num=4,
                ages=[[0xFF] * BOARD_SLOTS for _ in range(4)])
    case("★ 是**读改写**不是写常数：初值 0xFF ⇒ 加一后回绕成 0",
         w.board_age(0), [0xFF, 0, 0, 0xFF, 0, 0, 0xFF])
    case("  同一趟里全占用的玩家（七格全 1）⇒ 七格一并回绕成 0",
         w.board_age(1), [0] * BOARD_SLOTS)

    # ════════════════════════════════════════════════════════════════
    print("\n[D] 0x431caa（魔法屋效果派发）：骨架 + 12 条效果支")
    print("    骨架：edi<4 循环 / 空槽结束整个循环 / 名单 1 基→0 基 / 收尾还原当前玩家")

    w.run_magic(3, targets=(1, 2, 3, 4), cur=2)
    case("★ 名单 4 人 ⇒ 4 次效果（每人一次）", st.n("pause"), 4)
    case("★ 收尾把 [0x49910c] 还原成进入时的值", e.readu32(CUR), 2)
    case("★ 入口把「需要重绘地图」标志 [0x48be18] 清 0（预置 0x5A）",
         e.read8(REFRESH_FLAG), 0)

    w.run_magic(3, targets=(1, 0, 3, 4), cur=2)
    case("★★ 名单里的 0 是**结束符**：只处理到它之前（1 人）", st.n("pause"), 1)
    w.run_magic(3, targets=(0, 2, 3, 4), cur=2)
    case("★ 首项就是 0 ⇒ 一个人都不处理（0 次）", st.n("pause"), 0)

    w.run_magic(1, targets=(1, 2, 3, 4), cur=2)
    case("★ 1 抽命運三張：4 人 × 3 次 = 12 次 0x44db81（该函数**无实参**）",
         st.n("drawfortune"), 12)
    w.run_magic(0, targets=(1, 2, 3, 4), cur=2, vals={"sellcards": 0x1234})
    case("★★ 每人一次 0x441f21，实参 = 0/1/2/3 = 名单项 − 1",
         [st.rec("sellcards", i, 1)[0] for i in range(4)], [0, 1, 2, 3])

    for opt in (12, 255):
        w.run_magic(opt, targets=(1, 2, 3, 4), cur=2)
        case(f"★ 越界效果 opt={opt}（`cmp esi,0xb / ja`）⇒ 零副作用，但循环照走完",
             (st.n("pause"), st.n("show"), st.n("txn"), e.readu32(CUR)), (0, 0, 0, 2))

    # ── 0 變賣所有卡片 ──
    w.run_magic(0, targets=(2,), cur=0, points=(5, 6, 7, 8), vals={"sellcards": 0x1234})
    case("★ 0 變賣所有卡片：點券按**16 位**加上 0x441f21 的返回值",
         w.player(1, P_POINTS, 16), (6 + 0x1234) & 0xFFFF)
    w.run_magic(0, targets=(1,), cur=0, points=(0xFFF0, 0, 0, 0), vals={"sellcards": 0x20})
    case("★★ 16 位回绕：0xFFF0 + 0x20 = 0x10", w.player(0, P_POINTS, 16), 0x10)
    case("  同支还调 0x41d433(cur) 与 0x45285e(0xc8)",
         (st.n("wallet"), st.rec("sleep", 0, 1)), (1, [0xC8]))

    # ── 1 抽命運三張 ──
    w.run_magic(1, targets=(3,), cur=0)
    case("★ 1 抽命運三張：恰 3 次 0x44db81", st.n("drawfortune"), 3)

    # ── 2 立刻坐牢三天 ──
    w.run_magic(2, targets=(1,), cur=2, pi=3, vals={"selmask": 0})
    case("★ 2 坐牢：敌意 = (中签者 0, 发起者 2, 物價 3 × 90 = 270)",
         st.rec("hostility", 0, 3), [0, 2, 270])
    case("  坐牢 = 0x43d593(0x441210 的返回值, 3)", st.rec("prison", 0, 2), [0, 3])
    case("  0x441210 的实参 = 中签者自己", st.rec("selmask", 0, 1), [0])
    w.run_magic(2, targets=(1,), cur=0, pi=2, vals={"selmask": 0xFFFFFFFF})
    case("★★ 0x441210 返回 −1（免罪卡支）⇒ **不坐牢**，但敌意照样记",
         (st.n("prison"), st.rec("hostility", 0, 3)), (0, [0, 0, 180]))
    w.run_magic(2, targets=(1,), cur=1, pi=2, vals={"selmask": 3})
    case("★★ 0x441210 返回别人（嫁禍卡支）⇒ 坐牢的是**那个人**",
         st.rec("prison", 0, 2), [3, 3])

    # ── 3 原地停留一回合 ──
    w.run_magic(3, targets=(1, 2, 3, 4), cur=2)
    case("★ 3 停留：byte[+0x38] = (旧 + 1) & 0x7f（0x7e/0x7f/0x80/0x81 ⇒ 0x7f/0/1/2）",
         [w.player(i, P_STOP, 8) for i in range(4)], [0x7F, 0x00, 0x01, 0x02])

    # ── 4 存入所有現金 ──
    w.run_magic(4, targets=(1, 2), cur=0, cash=(100, 200, 300, 0), bank=(7, 8, 0, 0))
    case("★ 4 存款：[+0x20] += [+0x1c] 且 [+0x1c] = 0（只动名单里的两人）",
         ([w.player(i, P_BANK, 32) for i in range(4)],
          [w.player(i, P_CASH, 32) for i in range(4)]),
         ([107, 208, 0, 0], [0, 0, 300, 0]))
    case("  收尾 0x45285e(0xc8)", (st.n("wallet"), st.n("sleep")), (2, 2))

    # ── 5 就地加蓋房屋 ──
    for t, want in ((2000, 0), (2001, 1), (5999, 1), (6000, 0)):
        w.run_magic(5, targets=(1,), cur=0, node_type=(t, 0, 0, 0),
                    vals={"build": 0, "selmask": 0})
        case(f"★ 5 加蓋值域：节点值 {t} ⇒ 0x40b110 调用 {want} 次",
             st.n("build"), want)
    w.run_magic(5, targets=(1,), cur=0, blocking=(1, 0, 0, 0))
    case("★★ 5 的门槛 `dword[+0x32] != 0`（住宿/消失/坐牢/住院）⇒ 整支跳过（连暂停都不做）",
         (st.n("build"), st.n("nodename"), st.n("pause")), (0, 0, 0))
    w.run_magic(5, targets=(1,), cur=0, vals={"build": 0x80, "selmask": 0})
    case("★ 5 成功支：0x40b110 的实参 = **节点值**（不是节点号）", st.rec("build", 0, 1), [2001])
    case("  事务的两个坐标 = 0x40af12 写进两个输出缓冲的哨兵（0x1111/0x2222, 0）",
         st.rec("txn", 0, 3), [0x1111, 0x2222, 0])
    case("  0x40af12 的实参 = 节点值", st.rec("nodename", 0, 3)[0], 2001)
    case("  MKF 链 0x450441(…,0x229,…) / 0x45144f(…,0x28,…) / 0x456e11 各一次",
         (st.n("load"), st.n("blit"), st.n("free")), (1, 1, 1))
    case("★ 0x40b110 返回值 bit7 置位 ⇒ 额外调 0x40b0cd；台词 (cur, 0, 0x46482f)",
         (st.n("buildfx"), st.rec("say", 0, 3)), (1, [0, 0, P_SAY_DONE]))
    w.run_magic(5, targets=(1,), cur=0, vals={"build": 0x00, "selmask": 0})
    case("  bit7 清零 ⇒ 不调 0x40b0cd（门槛真的看返回值）", st.n("buildfx"), 0)

    # ── 6 得一張卡片 ──
    w.run_magic(6, targets=(1, 2), cur=0, vals={"drawcard": 7})
    case("★ 6 抽卡：每人一次 0x441e12(中签者)",
         ([st.rec("drawcard", i, 1)[0] for i in range(2)], st.n("drawcard")), ([0, 1], 2))
    case("  第二条 sprintf 的格式 = 0x464839（卡名）", st.rec("fmt", 1, 3)[1], P_FMT_CARD)

    # ── 7 向後轉（★ 与複刻的分歧点）──
    w.run_magic(7, targets=(1,), cur=2, facing=(1, 2, 3, 4), adj=(51, 52, 53, 54),
                vals={"rand": 1})
    case("★ 7 向後轉：朝向 (旧 + 4) & 7", w.player(0, P_FACING, 8), 5)
    case("★★ 原版调 **0x40c78c（完整掉头）** ⇒ 来路 last_node 被重挑成 候选[rand%k]",
         w.player(0, P_LAST, 16), 52)
    case("★ 该支**消耗一个 rand()**", st.n("rand"), 1)
    w.run_magic(7, targets=(1,), cur=2, adj=(51, 52, 53, 54), flags=0x40000000,
                vals={"rand": 2})
    case("  被封路的槽 0 不进候选 ⇒ rand=2 摇到 54（候选 [52,53,54] 的第 3 个）",
         w.player(0, P_LAST, 16), 54)
    w.run_magic(7, targets=(1,), cur=2, adj=(0, 0, 0, 0), vals={"rand": 2})
    case("★ 无候选 ⇒ last_node = 0 **且不摇 rand**", 
         (w.player(0, P_LAST, 16), st.n("rand")), (0, 0))
    w.run_magic(7, targets=(1,), cur=2, facing=(3, 0, 0, 0), blocking=(1, 0, 0, 0),
                adj=(51, 52, 53, 54), vals={"rand": 1})
    case("★ 7 的门槛同上：被阻碍 ⇒ 朝向不动、不摇 rand", 
         (w.player(0, P_FACING, 8), st.n("rand")), (3, 0))
    w.run_magic(7, targets=(1,), cur=2, adj=(51, 52, 53, 54), vals={"rand": 1})
    case("  同支收尾：事务 (0,0,1) + 0x45285e(0x1f4)", 
         (st.rec("txn", 0, 3), st.rec("sleep", 0, 1)), ([0, 0, 1], [0x1F4]))

    # ── 8 變賣所有道具 ──
    w.run_magic(8, targets=(4,), cur=0, points=(0, 0, 0, 0xFFF0),
                vals={"selltools": 0x30})
    case("★ 8 變賣所有道具：同 0 的 16 位加点（0xFFF0 + 0x30 = 0x20）",
         w.player(3, P_POINTS, 16), 0x20)
    case("  实参 = 中签者", st.rec("selltools", 0, 1), [3])

    # ── 9 就地拆除房屋 ──
    w.run_magic(9, targets=(1,), cur=0, vals={})
    case("★ 9 拆除：0x40ab4a(节点值, 0)", st.rec("demolish", 0, 2), [2001, 0])
    w.run_magic(9, targets=(1,), cur=0, node_type=(2000, 0, 0, 0))
    case("  值域下界同 5：2000 ⇒ 不拆", st.n("demolish"), 0)
    w.run_magic(9, targets=(1,), cur=0, blocking=(1, 0, 0, 0))
    case("  门槛同 5：中签者被阻碍 ⇒ 不拆", st.n("demolish"), 0)

    # ── 10 住院檢查三天 ──
    w.run_magic(10, targets=(1,), cur=2, pi=3, vals={"selmask": 0})
    case("★ 10 住院：敌意 (0, 2, 270) 与 0x43ec3f(0, 3)",
         (st.rec("hostility", 0, 3), st.rec("hosp", 0, 2)), ([0, 2, 270], [0, 3]))
    w.run_magic(10, targets=(1,), cur=2, pi=3, vals={"selmask": 0xFFFFFFFF})
    case("★ 免罪卡支（−1）⇒ 不住院，敌意照记",
         (st.n("hosp"), st.rec("hostility", 0, 3)), (0, [0, 2, 270]))

    # ── 11 拍賣當格土地 ──
    w.run_magic(11, targets=(2,), cur=3, vals={})
    case("★ 11 拍賣：0x43bde5(中签者 1, 中签者脚下节点值 4000, 1) —— 卖方 = **中签者**（不是发起者 3）",
         st.rec("auction", 0, 3), [1, 4000, 1])
    w.run_magic(11, targets=(1,), cur=1, node_type=(6000, 0, 0, 0))
    case("  值域上界同 5：6000 ⇒ 不拍", st.n("auction"), 0)
    w.run_magic(11, targets=(1,), cur=1, blocking=(1, 0, 0, 0))
    case("  门槛同 5：被阻碍 ⇒ 不拍", st.n("auction"), 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
