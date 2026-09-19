#!/usr/bin/env python3
"""
通道 2 差分测试 · 第二批（AI 出牌跳表成员 ＋ 一处视野格网重建器）

  [A] `0x0041E9E2`（256 B）**購地卡（卡 3）AI** `goudi`
  [B] `0x0042062B`（417 B）**查封卡（卡 28）AI** `chafeng`
      ★ 工作单把尺寸记成 62 B —— **真值是 417 B**（0x42062B..0x4207CB，
        下一支同盟卡 0x4207CC 才开始）。建图工具把它切在 `0x420669`
        中间。参见 gaps §7.139 对 `0x4202d2`/`0x41facc` 的同型订正。
  [C] `0x00409DE7`（274 B）**440×440 视野格网重建器**
      ⚠️ **它不是任何一张卡的 AI**。工作单说「在 `card-policy.ts` 里 grep
      `0x00409de7` 找对应 handler」—— 该文件里只有**两处注释引用**
      （`card-policy.ts:13` 与 `:79`，讲 440×440 屏幕格与 `VIEW_HALF`），
      **没有** `@source 0x00409de7` 的复刻函数。核对 AI 出牌跳表
      `0x475324`（30 项）后确认：全部 30 个 handler 都落在
      `0x41E6FE..0x420970` 区间，`0x409DE7` 不在其中。
      它是 `0x40a45c(-1)`（视野收集器）**第一步**要调的重建器
      （`0x474938` 格网 ← `0x48a44c` 渲染列表逐项 OR 上去）。
      本测试按**它实际是什么**驱动它，并按实际可比对象给裁决。

三支都是 **AI 出牌跳表成员 / 无 `call` 调用者**，函数图里查不到 ⇒ 用
`rich4-remake/tools/disasm.py va <地址>` 按需反汇编。

============================================================================
[A] 0x41E9E2 購地卡 AI —— 全程反汇编（256 B，0x41E9E2..0x41EAE1）
============================================================================
```
goudi():                                       ; 无参数
    cur  = [0x49910c]                          ; 当前玩家
    node = word [player[cur] + 0x0c]           ; 脚下那格
    code = word [node_table[node] + 0x20]      ; 格值（2000+i / 4000+i / …）
    hated = 0x40d2d3(cur)                      ; 最恨的人（0 基，无则 −1）
    if (0x41e8e6(hated, code) != 1) return 0   ; 「值得拿」——两参数 cdecl
    if (2000 < code < 4000) {                  ; 地產
        l = land_table + (code-2000)*0x34
        cost = (word[l+0x1c] + byte[l+0x1a]*word[l+0x1e]) * [0x4990e8]
    } else if (4000 < code < 6000) {           ; 設施
        f = fac_table + (code-4000)*0x38
        cost = (word[f+0x22] + byte[f+0x1a]*word[f+0x24]) * [0x4990e8]
    } else return 0
    if (cost >= dword[player[cur]+0x1c]) return 0   ; ★ 严格 <（jge 出口）
    return 1                                        ; ★ 全程**不写** 0x48be58
```
★ **`goudi` 返回 1 却不写 `[0x48be58]`**（与 §7.139(6) 记的停留卡 `0x41facc`
  的 `level≥2` 自用支**同型**）—— 目标靠上一拍的**残留值**。购地卡的效果
  函数 `0x442325` 自己读 `[0x49910c]→nodeId→node+0x20`（实测：全文无
  `0x48be58`），所以「返回 1 且不写目标」在玩家可见层面 == 「打脚下」。

`0x41e8e6(enemy, code)`（worthTaking，真跑）：
```
    if (enemy == -1) return 0
    地產：owner ∉ {0, cur+1} ∧ level != 0
          ∧ ( 同区（strcmp(land+4, other+4)==0，扫 land 记录 1..[0x498e98]）里有我的
              ∨ (owner == enemy+1 ∧ level >= 2) )
    設施：owner ∉ {0, cur+1} ∧ level != 0     ; ★ 不看 +0x18（種類/公園）
    其它（企業 6000+/景观 8000+/玩家标记）：return 0
```

============================================================================
[B] 0x42062B 查封卡 AI —— 全程反汇编（417 B，0x42062B..0x4207CB）
============================================================================
```
chafeng():
    push ebx/esi/edi/ebp; sub esp,0x14
    [esp+8] = 0                                  ; found
    esi     = 0                                  ; ★ 上一条街的名字指针
    0x40b221(cur, 6)                             ; 前瞻 6 格 → 0x48b8b4（8 word）
    [esp+4] = 0x40d2d3(cur)                      ; hated
    [esp+0xc] = 0                                ; i
    loop:
        if (i >= 6) break                        ; 0x4206f1
        if (found) break                         ; 0x4206fa
        node = word [0x48b8b4 + i*2]             ; ★ 缓冲项 = 节点号，0 基
        code = word [node_table[node] + 0x20]    ; [esp+0x10]
        if (code <= 2000 || code >= 4000) goto FAC
        ; ── 地產 ──
        ebp = land_table + (code-2000)*0x34
        if (esi != 0 && strcmp(esi, ebp+4) == 0) goto next   ; 同一条街只看一次
        esi = 1; edi = 0; [esp] = 0              ; ★ [esp] 全程只被写 0（死变量）
        for (j = 1; j <= [0x498e98]; j++) {      ; ★ 记录 0 不读
            if (strcmp(land[j]+4, ebp+4) != 0) continue
            if (land[j].owner == cur+1) goto SKIP_CHECK      ; ★ 我的地 ⇒ 整条街作废
            if (land[j].owner == 0) continue
            edi += land[j].level                 ; 只累**别人的**等级
        }
        if ([esp] != 0) goto SKIP_CHECK          ; ★ 死分支：永不成立
        if (edi < 7) goto SKIP_CHECK             ; ★ 门槛是 **≥ 7**（jl 出口）
        [0x48be58] = code; found = 1
      SKIP_CHECK:
        esi = ebp+4                              ; 记住这条街的名字
        goto next
        ; ── 設施 ──
      FAC:
        if (code <= 4000 || code >= 6000) goto next
        if (hated == -1) goto next
        f = fac_table + (code-4000)*0x38
        if (f.owner != hated+1) goto next
        if (f[+0x18] == 0) goto next             ; ★ 公園（type 0）不算
        if (f.level < 3) goto next               ; ★ 门槛 3
        [0x48be58] = code; found = 1
      next:
        i++
    return found                                 ; 共享尾声 0x41ed36
```
★ 三条不显然的事实，都写了专门断言：
  1. `[esp]` 是**死变量**（只有 `mov [esp],0`，无任何置 1 的写点）⇒
     `cmp [esp],0 / jne` 永不成立；「这条街有我的地」是靠在循环里
     `je 0x420685` **直接跳出判据**实现的。差分反证：[B4] 组。
  2. 输出的目标是**格值** `2000+i` / `4000+i`，**不是**下标。
  3. 内层扫街从**记录 1** 起（记录 0 是哨兵），而 goudi 侧 `0x41e8e6`
     的扫街也从记录 1 起 —— 两处同制。

============================================================================
[C] 0x409DE7 视野格网重建器 —— 全程反汇编（274 B，0x409DE7..0x409EF8）
============================================================================
```
0x409de7():                                    ; 无参数
    memset([0x474938], 0, 0x5e880)             ; 440*440*2 字节 ⇒ 440×440 的 **word** 格网
    if ([0x48bac8] == 0) return                ; ★ 渲染列表空 ⇒ **提前返回**
                                               ;   （0x474930/0x474934 **不清**）
    for (i = 0; i < [0x48bac8]; i++) {
        rec  = dword [0x48a44c + i*4] >> 16    ; ★ 坐标 dword 的**高 16 位 = 记录下标**
        base = 0x48a84c + rec*12               ; 12 字节/项
        if (word [base+4] == 0) continue       ; 格值 0 ⇒ 跳过
        if (dword[base+0] == 0) continue       ; 精灵表指针 0 ⇒ 不画
        x = movsx word [base+8]
        y = movsx word [base+10] − 0x28        ; ★ **y 减 40**（屏幕→格网）
        if ((byte[base+5] & 0x80) && (byte[base+5] & 0x3f)) {   ; 物件标记 0x8000|((idx+1)<<8)
            obj = ((word[base+4] >> 8) & 0x3f) - 1               ; ★ 0 基，先减 1
            if (byte [obj_table + obj*24 + 5] != 0) continue     ; ★ **有主（own+1≠0）就不画**
        }                                                        ;  玩家标记 0x8000|(1<<p)
                                                                 ;  bits13..8==0 ⇒ 不过这道闸
        if (x < 0 || x >= 0x1b8) continue
        if (y < 0 || y >= 0x1b8) continue
        word [grid + (y*440 + x)*2] |= word [base+4]            ; ★ 按 **word** 做 OR
    }
    [0x474930] = 0; [0x474934] = 0             ; 只有非空路径才清这两格
    ret                                        ; ★ 返回值是残留的 EAX（不定义）
```
★ 由此可**机械证伪** `card-policy.ts:13` 的两条注释：
  「`0x8000 | (1<<玩家)`（低 4 位是玩家位）」与
  「`0x8000 | (物件下标+1) << 8`（物件）」—— 都对上了机器码（[C5] 组）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么 |
|---|---|---|---|
| `0x00456F2D` | CRT `rand()` | `inc dword [CNT]; mov eax,[VAL]; ret`（值/计数都在**数据槽**） | 本测试要钉「摇了几次」。前瞻岔路用 `rand()%k` 选格，`0x40b221` 的取模规则已由 `test_lookahead.py` 单独定案 |
| `0x00474000` 格网 | `0x474938` 是指针 | `setup()` 把它指到自映射的 `0x700000`（0x5e880 B） | 格网真实落点 0x474938..0x4D31B8 **跨出本测试台映射的段**；函数每次都重新 `mov edx,[0x474938]`，改指针是**忠实**的注入 |
| `0x0048A44C` 渲染列表 | 由 `0x408f10` 每帧重建 | `setup()` 直接铺 `count/坐标/记录` | 列表构建器 `0x40829d` 是表现层（MKF/精灵/blit），不在本测试范围；本测试要的正是**它下游的格网怎么被算出来** |
| `0x00496D08` | 物件表 | `setup()` 直接铺 `+5` 字节 | 物件表**是绝对基址**（不是指针） |

**真跑的**（一步不打桩）：`0x40d2d3`（最恨的人，循环上界 `[0x499114]`）、
`0x41e8e6`（值得拿，内含真 `strcmp 0x458370`，扫街上界 `[0x498e98]`）、
`0x40b221`（前瞻 6 格，含真 `memset 0x456f60`）、`0x456f60`（memset）、
`0x458370`（strcmp）。⇒ `setup()` 里**必须**同时写 `[0x499114]`（人数）
与 `[0x498e98]`（地產数）—— 漏一个会让分支**静默退化**
（`verification.md` 工具边界第 5 条）。

## 可证伪检查（每支破坏一处，跑完还原）

| 破坏点 | 结果 |
|---|---|
| [A] `0x41EA7B` 的 `jge`(7D 短跳) → `jg`(7F)：严格 `<` 变 `≤` | **41/46，红 5 条**（全是「恰好相等 / pi 档边界 ⇒ 0」那 5 条） |
| [B] `0x420671` 的门槛立即数 `7` → `6` | **44/46，红 2 条**（`3+3=6 ⇒ 0` 与配套的「没写 0x48be58」） |
| [C] `0x409E5A` 的 `sub edx,0x28` → `0x29`（y 偏移差 1） | **20/45，红 25 条**（所有落格/边界断言） |
| 附加：[A] 漏写 `[0x499114]`（人数） | 35/46（`0x40d2d3` 恒 −1 ⇒ 21 条降级） |
| 附加：[B] 漏写 `[0x498e98]`（地產数） | 32/46（扫街循环空转 ⇒ 和恒 0） |
| 还原后复跑 | **137/137 ✅** |

## 与复刻的裁决（逐条证据见文件末尾注释与交付报告）

* [A] `goudi` ↔ `card-policy.ts:320`（＋`worthTaking` `:265`）：**MATCH**（1 处
  「原版返回 1 却不写 `[0x48be58]`」的残留目标 —— 与 §7.139(6) 停留卡同型，
  因 `0x442325` 不读该格而**无玩家可见后果**）。
* [B] `chafeng` ↔ `card-policy.ts:821`：**MATCH**（`[esp]` 死变量 / 输出格值
  / 记录 1 基 / `+0x18 != 0` 四条全部对上）。
* [C] `0x409de7` **没有复刻对应实现**（`visibleEntities` 换了视野口径 = **D-005**）；
  复刻注释里关于格网的两条断言（`0x8000` 两种编码）**机器码证实为真**。

跑法：cd rich4-spec && .venv/bin/python tests/test_card_ai_batch2.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

# ── 被测入口（AI 出牌跳表成员 / 无 call 调用者）──
GOUDI = 0x41E9E2
CHAFENG = 0x42062B
GRID_BUILD = 0x409DE7

# ── 真跑的辅助 ──
MOST_HATED = 0x40D2D3
WORTH = 0x41E8E6
LOOKAHEAD = 0x40B221
STRCMP = 0x458370
MEMSET = 0x456F60

# ── 打桩 ──
PRNG = 0x456F2D

# ── 全局量 ──
CUR = 0x49910C
NUM_PLAYERS = 0x499114          # ★ mostHated 的循环上界
PRICE_INDEX = 0x4990E8
NODE_TABLE_PTR = 0x498E80
NODE_STRIDE = 0x28
N_ADJ, N_CODE, N_FLAGS = 0x18, 0x20, 0x24
LAND_TABLE_PTR = 0x498E84
LAND_STRIDE = 0x34
LAND_COUNT = 0x498E98           # ★ 扫街的循环上界
L_NAME, L_TYPE, L_OWNER, L_LEVEL = 0x04, 0x18, 0x19, 0x1A
L_PRICE, L_HOUSE = 0x1C, 0x1E
FAC_TABLE_PTR = 0x498E88
FAC_STRIDE = 0x38
F_NAME, F_TYPE, F_OWNER, F_LEVEL = 0x04, 0x18, 0x19, 0x1A
F_PRICE, F_HOUSE = 0x22, 0x24
LOOK_BUF = 0x48B8B4
CARD_PARAM0 = 0x48BE58          # 目标
CARD_PARAM1 = 0x48BE5C          # 第二参数
CARD_PARAM2 = 0x48BE64          # 第三参数
GRID_PTR = 0x474938
CAM0, CAM1 = 0x474930, 0x474934
RENDER_COUNT = 0x48BAC8
COORD_ARR = 0x48A44C
REC_ARR = 0x48A84C
REC_STRIDE = 12
OBJ_TABLE = 0x496D08            # ★ 绝对基址（不是指针）
OBJ_STRIDE = 24
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_LAST, P_ALIVE = 0x0C, 0x0E, 0x15
P_CASH, P_HOSTILITY, HOST_STRIDE = 0x1C, 0x4C, 4

GRID = 0x700000                 # 自映射的 440×440 word 格网
GRID_SIZE = 0x5E880             # 440*440*2
GRID_MAP = 0x60000

# 暂存区（**跨 call 保留** ⇒ 每拍必须清）
NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x4000
OBJS = SCRATCH_BASE + 0x5000
RAND_VAL = SCRATCH_BASE + 0x800
RAND_CNT = SCRATCH_BASE + 0x900

SENTINEL = 0x5A5A5A5A
GRID_FILL = 0xAB
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def prng_stub():
    """inc dword [CNT] / mov eax, [VAL] / ret —— 值放**数据**里，省得反复重打代码段补丁。"""
    return (b"\xFF\x05" + struct.pack("<I", RAND_CNT)
            + b"\xA1" + struct.pack("<I", RAND_VAL) + b"\xC3")


def name_bytes(s):
    b = s.encode("ascii") + b"\x00"
    return b + b"\x00" * (0x18 - len(b))


class World:
    """所有可变状态留在 Python 侧，每拍重注入（`Emu.call` 会先 `reset()`）。"""

    def __init__(self):
        self.new_emu()
        self.clear()

    def new_emu(self):
        """换一个干净的 `Emu`。

        ★★ 工具限制（本稿实测，值得登记）：`emulate.Emu.call()` **每次调用都
        `mu.hook_add(UC_HOOK_CODE, self._hook)` 而从不 `hook_del`** ⇒ 钩子逐次
        累积，`insn_count` 被**重复计数**（实测：同一支 `strcmp` 在 200 次调用
        之后 `insns` 从 13 变成 2613 = 13×201）。`_hook` 在
        `insn_count > MAX_INSN(400000)` 时 `emu_stop()` ⇒ 调用次数一多，
        **单次调用的真实指令预算被除掉了**。
        对短函数（本文件 [A]/[B]）无影响；对 [C] 的 `memset(…, 0x5e880)`
        （真值 ≈169,501 条指令）就有影响 —— 3 个钩子就够把它截断成
        「只清了 14,668 字节」，看起来像**被测函数自己写错了**。
        ⇒ 每 2 次调用换一个干净实例（1 个钩子时 169,501；2 个钩子时
        2×169,501 = 339,002 < 400,000，仍有余量）。
        """
        self.emu = Emu()
        self.emu.patch(PRNG, prng_stub())
        self.emu.mu.mem_map(GRID, GRID_MAP)     # 440×440 word 格网
        self._emu_calls = 0

    # ── 状态 ──────────────────────────────────────────────────────
    def clear(self):
        self.me = 0
        self.cash = 50000
        self.pi = 1
        self.hostility = [0, 0, 0, 0]
        self.alive = [1, 1, 1, 1]
        self.node_code = {}          # nodeId → node[+0x20]（格值）
        self.adj = {}                # nodeId → 4 个邻接槽
        self.flags = {}              # nodeId → node[+0x24]
        self.my_node = 1
        self.my_last = 0
        self.lands = {}              # idx → dict
        self.facs = {}               # idx → dict
        self.num_lands = 0
        self.rand = 0
        self.obj = {}                # 物件下标 → +5 字节
        self.render = []             # [{'rec':…, 'id':…, 'x':…, 'y':…, 'spr':…}]
        self.render_count = None     # None ⇒ 用 len(self.render)
        self.cam = [SENTINEL, SENTINEL]
        self.grid_prefill = None     # 预填字节（证明 memset 真的跑了）
        self.extra = []              # [(va, 'b'|'w'|'d', value)] 在标准注入之后再写

    def land(self, idx, owner, level, price=0, house=0, name="X", ltype=0):
        self.lands[idx] = dict(owner=owner, level=level, price=price,
                               house=house, name=name, ltype=ltype)
        return self

    def fac(self, idx, owner, level, price=0, house=0, name="F", ftype=1):
        self.facs[idx] = dict(owner=owner, level=level, price=price,
                              house=house, name=name, ftype=ftype)
        return self

    def line(self, n, start=1):
        """1→2→3… 直线拓扑（无岔路 ⇒ 前瞻不摇 rand）。"""
        for k in range(n):
            self.adj[start + k] = [start + k + 1, 0, 0, 0]
        return self

    # ── 注入 ──────────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(PRICE_INDEX, self.pi)
        emu.write32(NODE_TABLE_PTR, NODES)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(LAND_COUNT, self.num_lands)
        emu.write32(RAND_VAL, self.rand & 0xFFFFFFFF)
        emu.write32(RAND_CNT, 0)
        emu.write32(CARD_PARAM0, SENTINEL)
        emu.write32(CARD_PARAM1, SENTINEL)
        emu.write32(CARD_PARAM2, SENTINEL)
        emu.write32(GRID_PTR, GRID)
        emu.write32(CAM0, self.cam[0] & 0xFFFFFFFF)
        emu.write32(CAM1, self.cam[1] & 0xFFFFFFFF)
        # ★ 暂存区跨 call 保留 ⇒ 先整块清
        emu.write(NODES, b"\x00" * (NODE_STRIDE * 24))
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 24))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 24))
        emu.write(OBJS, b"\x00" * (OBJ_STRIDE * 16))
        emu.write(LOOK_BUF, b"\x00" * 16)
        # 节点
        for nid, slots in self.adj.items():
            base = NODES + nid * NODE_STRIDE
            for s in range(4):
                emu.write16(base + N_ADJ + s * 2, slots[s] & 0xFFFF)
        for nid, code in self.node_code.items():
            emu.write16(NODES + nid * NODE_STRIDE + N_CODE, code & 0xFFFF)
        for nid, fl in self.flags.items():
            emu.write32(NODES + nid * NODE_STRIDE + N_FLAGS, fl & 0xFFFFFFFF)
        # 玩家
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_ALIVE, self.alive[p])
            emu.write32(pb + P_CASH, self.cash if p == self.me else 0)
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        for j, h in enumerate(self.hostility):
            emu.write32(pb + P_HOSTILITY + j * HOST_STRIDE, h & 0xFFFFFFFF)
        emu.write16(pb + P_NODE, self.my_node & 0xFFFF)
        emu.write16(pb + P_LAST, self.my_last & 0xFFFF)
        # 地块
        for idx, l in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write(b + L_NAME, name_bytes(l["name"]))
            emu.write8(b + L_TYPE, l["ltype"])
            emu.write8(b + L_OWNER, l["owner"])
            emu.write8(b + L_LEVEL, l["level"])
            emu.write16(b + L_PRICE, l["price"] & 0xFFFF)
            emu.write16(b + L_HOUSE, l["house"] & 0xFFFF)
        # 設施
        for idx, f in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write(b + F_NAME, name_bytes(f["name"]))
            emu.write8(b + F_TYPE, f["ftype"])
            emu.write8(b + F_OWNER, f["owner"])
            emu.write8(b + F_LEVEL, f["level"])
            emu.write16(b + F_PRICE, f["price"] & 0xFFFF)
            emu.write16(b + F_HOUSE, f["house"] & 0xFFFF)
        # 物件表（绝对基址，0 基）
        for idx, v in self.obj.items():
            emu.write8(OBJ_TABLE + idx * OBJ_STRIDE + 5, v)
        # 渲染列表
        cnt = len(self.render) if self.render_count is None else self.render_count
        emu.write32(RENDER_COUNT, cnt)
        emu.write(COORD_ARR, b"\x00" * 64)
        emu.write(REC_ARR, b"\x00" * (REC_STRIDE * 16))
        for i, e in enumerate(self.render):
            rec = e["rec"]
            emu.write32(COORD_ARR + i * 4,
                        ((rec & 0xFFFF) << 16) | ((e["y"] & 0xFFF) << 4))
            b = REC_ARR + rec * REC_STRIDE
            emu.write32(b, e["spr"] & 0xFFFFFFFF)
            emu.write16(b + 4, e["id"] & 0xFFFF)
            emu.write16(b + 8, e["x"] & 0xFFFF)
            emu.write16(b + 10, e["y"] & 0xFFFF)
        if self.grid_prefill is not None:
            emu.write(GRID, bytes([self.grid_prefill]) * GRID_SIZE)
        for va, kind, val in self.extra:
            if kind == "b":
                emu.write8(va, val)
            elif kind == "w":
                emu.write16(va, val)
            else:
                emu.write32(va, val)

    def _before_call(self):
        if self._emu_calls >= 2:
            self.new_emu()
        self._emu_calls += 1

    def run(self, fn):
        self._before_call()
        r = self.emu.call(fn, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(CARD_PARAM0)
        self.arg1 = self.emu.readu32(CARD_PARAM1)
        self.arg2 = self.emu.readu32(CARD_PARAM2)
        self.rands = self.emu.readu32(RAND_CNT)
        return self

    # ── 格网 ──────────────────────────────────────────────────────
    def grid(self):
        return self.emu.read(GRID, GRID_SIZE)

    def cell(self, x, y):
        off = (y * 440 + x) * 2
        return struct.unpack_from("<H", self.grid(), off)[0]

    def nonzero(self):
        b = self.grid()
        return sum(1 for i in range(0, GRID_SIZE, 2)
                   if b[i] | (b[i + 1] << 8))


# ── [A] 購地卡 AI 0x41E9E2 ────────────────────────────────────────
def section_a(w):
    # A1 最恨的人 = −1 ⇒ worthTaking 一律 0
    print("\n[A] 購地卡 AI 0x41e9e2（256 B）")

    print("[A1] hated == −1 ⇒ `0x41e8e6` 立刻 return 0（再好的地也不出）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=2, level=5, price=1, house=1, name="X")
    w.num_lands = 1
    w.hostility = [0, 0, 0, 0]
    r = w.run(GOUDI)
    case("hated = −1 ⇒ 返回 0", r.ret, 0)
    case("  0x48be58 保持哨兵", r.target, SENTINEL)
    case("  0x48be5c 保持哨兵", r.arg1, SENTINEL)
    case("  0x48be64 保持哨兵", r.arg2, SENTINEL)

    print("\n[A2] 脚下有主但 owner ≠ 最恨的人、同區没我的地 ⇒ 不值")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=3, level=5, price=1, house=1, name="X")
    w.num_lands = 1
    w.hostility = [0, 5, 0, 0]          # 最恨 0 基玩家 1 ⇒ 1 基 owner 2
    r = w.run(GOUDI)
    case("owner=3 ≠ hated+1=2 ⇒ 返回 0", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    print("\n[A3] owner == 最恨的人、level ≥ 2 ⇒ 值；接着看钱（**严格 <**）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=2, level=2, price=1000, house=200, name="X")   # 1000+200*2 = 1400
    w.num_lands = 1
    w.hostility = [0, 5, 0, 0]
    w.pi = 1
    w.cash = 1401
    r = w.run(GOUDI)
    case("(1000+200×2)×1 = 1400 < 1401 ⇒ 返回 1", r.ret, 1)
    case("★★ 返回 1 但**不写** 0x48be58（残留目标）", r.target, SENTINEL)
    case("  0x48be5c 保持哨兵", r.arg1, SENTINEL)

    w.cash = 1400
    r = w.run(GOUDI)
    case("★★ 恰好相等 1400 ⇒ 0（`jge` 出口 = 严格 <）", r.ret, 0)
    w.cash = 1399
    r = w.run(GOUDI)
    case("  1399 < 1400 ⇒ 返回 0", r.ret, 0)

    print("\n[A4] 等級必须 ≥ 2（最恨的人那一条）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=2, level=1, price=10, house=10, name="X")
    w.num_lands = 1
    w.hostility = [0, 5, 0, 0]
    w.cash = 1 << 20
    r = w.run(GOUDI)
    case("owner=hated+1 但 level=1 ⇒ 返回 0", r.ret, 0)
    w.land(1, owner=2, level=2, price=10, house=10, name="X")
    r = w.run(GOUDI)
    case("  同局改成 level=2 ⇒ 返回 1", r.ret, 1)

    print("\n[A5] ★ 物價指數真的乘进去（三个档位，边界都是 ≥ 出口）")
    for pi, cash_bad, cash_ok in ((1, 1400, 1401), (2, 2800, 2801), (3, 4200, 4201)):
        w.clear()
        w.my_node = 1
        w.node_code = {1: 2001}
        w.land(1, owner=2, level=2, price=1000, house=200, name="X")
        w.num_lands = 1
        w.hostility = [0, 5, 0, 0]
        w.pi = pi
        w.cash = cash_bad
        r = w.run(GOUDI)
        case(f"pi={pi}：現金 {cash_bad} ⇒ 0", r.ret, 0)
        w.cash = cash_ok
        r = w.run(GOUDI)
        case(f"pi={pi}：現金 {cash_ok} ⇒ 1", r.ret, 1)

    print("\n[A6] ★ 同區里有我的地 ⇒ 值（且订价用**脚下那块**，不是我的那块）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=3, level=1, price=100, house=50, name="S")      # 脚下：非最恨、1 级
    w.land(2, owner=1, level=5, price=9, house=9, name="S")         # 我的，同區
    w.num_lands = 2
    w.hostility = [0, 5, 0, 0]           # 最恨 1 ⇒ 1 基 owner 2（脚下是 3）
    w.pi = 1
    w.cash = 151
    r = w.run(GOUDI)
    case("同區有我的地 ⇒ 值，且 (100+50×1)=150 < 151 ⇒ 1", r.ret, 1)
    w.cash = 150
    r = w.run(GOUDI)
    case("  恰好 150 ⇒ 0（订价取脚下那块：若是我的 5 级地就不止这个数）", r.ret, 0)
    w.cash = 1 << 20
    r = w.run(GOUDI)
    case("  钱够 ⇒ 1（同一局面）", r.ret, 1)

    print("\n[A7] ★ 扫街从记录 **1** 起（记录 0 是哨兵，**永不**被读）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(0, owner=1, level=5, price=9, house=9, name="S")    # 记录 0：我的、同名
    w.land(1, owner=3, level=1, price=10, house=10, name="S")  # 脚下（记录 1）
    w.land(2, owner=1, level=5, price=9, house=9, name="S")    # 记录 2：我的、同名
    w.hostility = [0, 5, 0, 0]
    w.cash = 1 << 20
    w.num_lands = 1
    r = w.run(GOUDI)
    case("★★ 上界 = 1 ⇒ 只扫记录 1 ⇒ 找不到我的地 ⇒ 返回 0", r.ret, 0)
    w.num_lands = 2
    r = w.run(GOUDI)
    case("  上界 = 2 ⇒ 扫到记录 2 的我的地 ⇒ 返回 1（上界就是 0x498e98）", r.ret, 1)
    w.lands.pop(2)
    w.num_lands = 3
    r = w.run(GOUDI)
    case("★★ 只把「我的地」放在记录 0、上界放到 3 ⇒ 仍返回 0（记录 0 永不读）", r.ret, 0)

    print("\n[A8] 設施支：owner ∉ {0, 我}、level ≠ 0；★ **不看種類**（公園也算）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 4001}
    w.fac(1, owner=2, level=1, price=1000, house=500, name="F", ftype=0)  # 公園
    w.hostility = [0, 5, 0, 0]
    w.pi = 1
    w.cash = 1501
    r = w.run(GOUDI)
    case("設施 (1000+500×1)×1 = 1500 < 1501 ⇒ 1", r.ret, 1)
    case("  ★ 種類 = 公園（+0x18=0）不挡（goudi 侧不查種類）", r.target, SENTINEL)
    w.cash = 1500
    r = w.run(GOUDI)
    case("  恰好 1500 ⇒ 0（严格 <，走 +0x24 房价字段）", r.ret, 0)
    w.fac(1, owner=2, level=0, price=1000, house=500, name="F")
    w.cash = 1 << 20
    r = w.run(GOUDI)
    case("  設施 level = 0 ⇒ 不值 ⇒ 返回 0", r.ret, 0)
    w.fac(1, owner=0, level=3, price=1000, house=500, name="F")
    r = w.run(GOUDI)
    case("  設施無主 ⇒ 不值 ⇒ 返回 0", r.ret, 0)
    w.fac(1, owner=1, level=3, price=1000, house=500, name="F")
    r = w.run(GOUDI)
    case("  設施是我的 ⇒ 不值 ⇒ 返回 0", r.ret, 0)
    w.fac(1, owner=3, level=3, price=1000, house=500, name="F")
    r = w.run(GOUDI)
    case("★★ 設施支**不看 enemy**：别家（非最恨）的設施也算「值得拿」⇒ 1", r.ret, 1)
    case("  返回 1 仍不写 0x48be58", r.target, SENTINEL)
    w.hostility = [0, 0, 0, 0]                    # hated == −1
    r = w.run(GOUDI)
    case("★★ 但 hated == −1 的提前返回对两支都生效 ⇒ 返回 0", r.ret, 0)

    print("\n[A9] ★ 格值区间是**开区间**：2000 / 4000 / 6000+i / 8000+i / 0 全不出")
    for code, desc in ((2000, "格值 2000（地產 0 号哨兵）"),
                       (4000, "格值 4000（設施 0 号哨兵）"),
                       (6001, "企業 6000+i"),
                       (8001, "景观 8000+i"),
                       (0, "空格值 0")):
        w.clear()
        w.my_node = 1
        w.node_code = {1: code}
        w.land(1, owner=2, level=5, price=1, house=1, name="X")
        w.fac(1, owner=2, level=5, price=1, house=1, name="F")
        w.num_lands = 1
        w.hostility = [0, 5, 0, 0]
        w.cash = 1 << 20
        r = w.run(GOUDI)
        case(f"{desc} ⇒ 返回 0", r.ret, 0)
        case(f"  {desc} 不写 0x48be58", r.target, SENTINEL)

    print("\n[A10] 本函数**一次 rand 都不摇**（只有 mostHated + strcmp）")
    w.clear()
    w.my_node = 1
    w.node_code = {1: 2001}
    w.land(1, owner=2, level=2, price=10, house=10, name="X")
    w.num_lands = 1
    w.hostility = [0, 5, 0, 0]
    w.cash = 1 << 20
    r = w.run(GOUDI)
    case("rand 调用次数 = 0", r.rands, 0)
    case("  返回 1", r.ret, 1)


# ── [B] 查封卡 AI 0x42062B ────────────────────────────────────────
def section_b(w):
    print("\n[B] 查封卡 AI 0x42062b（★ 真值 417 B，工作单记 62 B）")

    def base(levels, names=None, owners=None, num_lands=None, host=None):
        """直线 1→2→…→k+1 的六格；第 j 格（1 基）挂地块记录 j。"""
        w.clear()
        n = len(levels)
        w.line(8)
        w.my_node, w.my_last = 1, 0
        w.node_code = {}
        for j in range(1, n + 1):
            w.node_code[j + 1] = 2000 + j        # 前瞻第 j 格 → 地產 j
        for j in range(1, n + 1):
            w.land(j,
                   owner=(owners[j - 1] if owners else 2),
                   level=levels[j - 1],
                   name=(names[j - 1] if names else "X"))
        w.num_lands = num_lands if num_lands is not None else n
        w.hostility = host if host else [0, 5, 0, 0]
        return w

    print("[B1] 某條街对手等级和 ≥ 7 ⇒ 封：目标 = **格值** 2000+i，取**第一个**合格格")
    r = base([4, 3]).run(CHAFENG)
    case("4+3 = 7 ⇒ 返回 1", r.ret, 1)
    case("★ 目标 = 2001（**格值** 2000+记录号，不是下标/地址）", r.target, 2001)
    case("  0x48be5c 保持哨兵", r.arg1, SENTINEL)
    case("  0x48be64 保持哨兵", r.arg2, SENTINEL)

    r = base([3, 3]).run(CHAFENG)
    case("3+3 = 6 < 7 ⇒ 返回 0", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    r = base([7]).run(CHAFENG)
    case("单块 7 级 ⇒ 返回 1（门槛含等号）", r.ret, 1)
    case("  目标 = 2001", r.target, 2001)

    print("\n[B2] 無主地不累加等级")
    r = base([7], owners=[0]).run(CHAFENG)
    case("同一条街只有無主地 ⇒ 和 = 0 ⇒ 返回 0", r.ret, 0)
    r = base([3, 4], owners=[0, 2]).run(CHAFENG)
    case("無主 3 级 + 对手 4 级 ⇒ 和 = 4 < 7 ⇒ 返回 0", r.ret, 0)
    r = base([3, 1, 3], owners=[0, 2, 2]).run(CHAFENG)
    case("無主 3 + 对手 1 + 对手 3 ⇒ 和 = 4 < 7 ⇒ 返回 0", r.ret, 0)

    print("\n[B3] ★ 只累**同一条街**（strcmp 名字）的等级")
    r = base([4, 5], names=["X", "Y"]).run(CHAFENG)
    case("两条不同的街各 4/5 级 ⇒ 每条街都不够 ⇒ 返回 0", r.ret, 0)
    r = base([4, 3, 4], names=["X", "Y", "X"]).run(CHAFENG)
    case("街 X 有 4+4 = 8 ⇒ 返回 1，目标是**最先遇到**的那格", r.ret, 1)
    case("  目标 = 2001（第 1 格，不是第 3 格）", r.target, 2001)

    print("\n[B4] ★★ 这条街有我的地 ⇒ **整条街作废**（`[esp]` 是死变量，靠 je 跳出判据）")
    r = base([4, 4, 1], owners=[2, 2, 1]).run(CHAFENG)
    case("★★ 对手 4+4 = 8 ≥ 7，但有我的 1 级地 ⇒ 返回 0", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    r = base([1, 4, 4], owners=[1, 2, 2]).run(CHAFENG)
    case("★★ 我的地排在最前 ⇒ 立刻整条街作废 ⇒ 返回 0", r.ret, 0)
    r = base([4, 4, 1], owners=[2, 2, 0]).run(CHAFENG)
    case("  把「我的地」换成無主 ⇒ 和仍是 8 ⇒ 返回 1（对照，证明不是门槛变了）", r.ret, 1)

    print("\n[B5] ★ 扫街从记录 **1** 起（记录 0 是哨兵）")
    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {2: 2005}
    w.land(0, owner=2, level=6, price=0, house=0, name="X")   # 记录 0：同名、对手、6 级
    w.land(5, owner=2, level=1, price=0, house=0, name="X")
    w.num_lands = 5
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("★★ 记录 0 的 6 级**不参与**（上界 1..5）⇒ 和 = 1 ⇒ 返回 0", r.ret, 0)
    r.land(0, owner=2, level=1, price=0, house=0, name="X")
    w.num_lands = 6
    w.land(6, owner=2, level=6, price=0, house=0, name="X")
    r = w.run(CHAFENG)
    case("  把 6 级挪到记录 6（合法范围）⇒ 和 = 7 ⇒ 返回 1", r.ret, 1)
    case("  目标 = 2005", r.target, 2005)

    print("\n[B6] ★ 前瞻缓冲的索引基与 6 格上界")
    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {2: 2005}                       # 只在前瞻第 1 格（buf 下标 0）
    w.land(5, owner=2, level=7, price=0, house=0, name="X")
    w.num_lands = 5
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("★★ 第 1 格就合格 ⇒ 返回 1（`i` 从 0 起，不是从 1）", r.ret, 1)
    case("  目标 = 2005", r.target, 2005)

    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {7: 2005}                       # 前瞻第 6 格（buf 下标 5）
    w.land(5, owner=2, level=7, price=0, house=0, name="X")
    w.num_lands = 5
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("★ 第 6 格（buf 下标 5）仍被读 ⇒ 返回 1（上界 6 含）", r.ret, 1)

    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {0: 2005}                       # ★ 陷阱：只有节点 0 合格
    w.land(5, owner=2, level=7, price=0, house=0, name="X")
    w.num_lands = 5
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("★★ 上界就是 6：buf[6]（前瞻不清的哨兵 0 ⇒ 节点 0）**不被读** ⇒ 返回 0", r.ret, 0)

    print("\n[B7] 設施支：hated ≠ −1 ∧ owner == hated+1 ∧ +0x18 ≠ 0 ∧ level ≥ 3")
    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {2: 4002}
    w.fac(2, owner=2, level=3, price=0, house=0, name="F", ftype=1)
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("最恨的人的 3 级非公園設施 ⇒ 返回 1", r.ret, 1)
    case("★ 目标 = 4002（設施格值）", r.target, 4002)

    w.fac(2, owner=2, level=2, price=0, house=0, name="F", ftype=1)
    r = w.run(CHAFENG)
    case("  level = 2 < 3 ⇒ 返回 0", r.ret, 0)
    w.fac(2, owner=2, level=5, price=0, house=0, name="F", ftype=0)
    r = w.run(CHAFENG)
    case("★★ +0x18 == 0（公園）⇒ 返回 0", r.ret, 0)
    w.fac(2, owner=2, level=5, price=0, house=0, name="F", ftype=0)
    w.fac(2, owner=3, level=5, price=0, house=0, name="F", ftype=1)
    r = w.run(CHAFENG)
    case("  owner = 3 ≠ hated+1 = 2 ⇒ 返回 0", r.ret, 0)
    w.fac(2, owner=0, level=5, price=0, house=0, name="F", ftype=1)
    r = w.run(CHAFENG)
    case("  無主設施 ⇒ 返回 0", r.ret, 0)
    w.fac(2, owner=2, level=5, price=0, house=0, name="F", ftype=1)
    w.hostility = [0, 0, 3, 0]                    # 最恨换人 ⇒ hated+1 = 3
    r = w.run(CHAFENG)
    case("★★ 换了最恨的人（hated+1 = 3）⇒ owner=2 的設施不选 ⇒ 返回 0", r.ret, 0)
    w.fac(2, owner=3, level=5, price=0, house=0, name="F", ftype=1)
    r = w.run(CHAFENG)
    case("  owner 跟上新的最恨的人 ⇒ 返回 1", r.ret, 1)
    w.hostility = [0, 0, 0, 0]                    # hated == −1
    r = w.run(CHAFENG)
    case("★★ hated == −1 ⇒ 設施支整个不跑 ⇒ 返回 0", r.ret, 0)
    w.hostility = [0, 5, 0, 0]
    w.fac(2, owner=2, level=3, price=0, house=0, name="F", ftype=1)
    w.node_code = {2: 6002}                       # 企業格值：不在兩段開區間內
    r = w.run(CHAFENG)
    case("  格值 6002（企業）⇒ 两段都不进 ⇒ 返回 0", r.ret, 0)
    w.node_code = {2: 4000}
    r = w.run(CHAFENG)
    case("  格值 4000（設施 0 号哨兵）⇒ 返回 0（开区间）", r.ret, 0)
    w.node_code = {2: 2001}
    w.land(1, owner=2, level=9, price=0, house=0, name="X")
    w.num_lands = 1
    r = w.run(CHAFENG)
    case("  格值 2001 走**地產**支（9 级 ⇒ 1），目标 = 2001", r.target, 2001)

    print("\n[B8] ★ rand 消费：直线前瞻摇 0 次；一个岔路摇 1 次")
    r = base([7]).run(CHAFENG)
    case("直线拓扑 ⇒ rand 次数 = 0", r.rands, 0)
    w.clear()
    w.adj = {1: [2, 0, 0, 0], 2: [3, 4, 0, 0]}
    w.line(8, start=3)
    w.my_node, w.my_last = 1, 0
    w.node_code = {3: 2005}
    w.land(5, owner=2, level=7, price=0, house=0, name="X")
    w.num_lands = 5
    w.hostility = [0, 5, 0, 0]
    w.rand = 0
    r = w.run(CHAFENG)
    case("岔路 k=2、rand=0 ⇒ 走 cand[0]=3 ⇒ 1 rand 次", r.rands, 1)
    case("  目标 = 2005（节点 3 上的地）", r.target, 2005)
    w.rand = 1
    r = w.run(CHAFENG)
    case("岔路 rand=1 ⇒ 走 cand[1]=4（节点 4 没地）⇒ 返回 0", r.ret, 0)
    case("  同样是 1 rand 次", r.rands, 1)

    print("\n[B9] 前瞻 6 格内一无所获 ⇒ 返回 0（不碰任何出口）")
    w.clear()
    w.line(8)
    w.my_node, w.my_last = 1, 0
    w.node_code = {}
    w.num_lands = 0
    w.hostility = [0, 5, 0, 0]
    r = w.run(CHAFENG)
    case("六格全空 ⇒ 返回 0", r.ret, 0)
    case("  0x48be58 保持哨兵", r.target, SENTINEL)
    case("  0x48be5c 保持哨兵", r.arg1, SENTINEL)
    case("  0x48be64 保持哨兵", r.arg2, SENTINEL)


# ── [C] 视野格网重建器 0x409DE7 ────────────────────────────────────
def section_c(w):
    print("\n[C] 视野格网重建器 0x409de7（274 B）—— ⚠️ 不是任何一张卡的 AI")

    def one(ident, x, y, spr=0x11223344, rec=0):
        w.clear()
        w.render = [dict(rec=rec, id=ident, x=x, y=y, spr=spr)]
        return w

    print("[C1] 基本：格网先清、再按 (x, y−0x28) 落一格")
    w.clear()
    w.grid_prefill = GRID_FILL
    w.render = [dict(rec=0, id=2001, x=10, y=50, spr=0x1111)]
    w.run(GRID_BUILD)
    case("★ memset 先清 440×440×2 字节 ⇒ 只剩 1 个非零格", w.nonzero(), 1)
    case("  grid[y=50−40=10][x=10] |= 2001", w.cell(10, 10), 2001)
    case("  邻近格未被写", w.cell(11, 10), 0)
    case("  行 0 未被写", w.cell(10, 0), 0)

    print("[C2] ★ y 的 **−0x28** 偏移（±1 就是两个不同的行）")
    one(0x0102, 5, 40).run(GRID_BUILD)
    case("记录 y = 40 ⇒ 格网行 0", w.cell(5, 0), 0x0102)
    one(0x0103, 5, 41).run(GRID_BUILD)
    case("记录 y = 41 ⇒ 格网行 1（不是行 0）", w.cell(5, 1), 0x0103)
    one(0x0104, 5, 39).run(GRID_BUILD)
    case("★ 记录 y = 39 ⇒ 格网行 −1 ⇒ 整格跳过，格网全 0", w.nonzero(), 0)
    one(0x0105, 5, 39).run(GRID_BUILD)
    case("  （同一用例：行 0 也没被写）", w.cell(5, 0), 0)

    print("[C3] 边界的**闭/开**：x、y ∈ [0, 0x1b8)")
    one(0x0201, 439, 40).run(GRID_BUILD)
    case("x = 439（0x1b7）⇒ 写进 [439,0]", w.cell(439, 0), 0x0201)
    one(0x0202, 440, 40).run(GRID_BUILD)
    case("x = 440（0x1b8）⇒ 越界 ⇒ 整格跳过", w.nonzero(), 0)
    one(0x0203, -1, 40).run(GRID_BUILD)
    case("x = −1（movsx 有符号）⇒ 越界 ⇒ 整格跳过", w.nonzero(), 0)
    one(0x0204, 0, 40 + 439).run(GRID_BUILD)
    case("y = 479 ⇒ 格网行 439 ⇒ 写进 [0,439]", w.cell(0, 439), 0x0204)
    one(0x0205, 0, 40 + 440).run(GRID_BUILD)
    case("y = 480 ⇒ 格网行 440 ⇒ 越界 ⇒ 整格跳过", w.nonzero(), 0)

    print("[C4] 两个「看不见」的闸：格值 0 / 精灵表指针 0")
    one(0, 10, 50).run(GRID_BUILD)
    case("格值 word[+4] == 0 ⇒ 跳过", w.nonzero(), 0)
    one(0x0301, 10, 50, spr=0).run(GRID_BUILD)
    case("精灵表指针 dword[+0] == 0 ⇒ 跳过（看不见的项不入格网）", w.nonzero(), 0)
    one(0x0302, 10, 50, spr=1).run(GRID_BUILD)
    case("  指针非 0 就画", w.cell(10, 10), 0x0302)

    print("[C5] ★ 格值按 **word** 做 OR（不是覆盖、不是加）")
    w.clear()
    w.render = [dict(rec=0, id=0x0001, x=3, y=43, spr=1),
                dict(rec=1, id=0x0002, x=3, y=43, spr=1)]
    w.run(GRID_BUILD)
    case("★ 0x0001 | 0x0002 = 0x0003（不是 2 / 3 相加 / 覆盖）", w.cell(3, 3), 0x0003)
    case("  只有 1 个非零格", w.nonzero(), 1)
    w.clear()
    w.render = [dict(rec=0, id=0x8002, x=3, y=43, spr=1),
                dict(rec=1, id=0x8001, x=3, y=43, spr=1)]
    w.run(GRID_BUILD)
    case("★ 0x8002 | 0x8001 = 0x8003（高位不丢）", w.cell(3, 3), 0x8003)
    w.clear()
    w.render = [dict(rec=0, id=0x2001, x=7, y=47, spr=1)]
    w.extra = [(REC_ARR + 6, "w", 0xFFFF)]      # 记录 +6 的 word 是垃圾
    w.run(GRID_BUILD)
    case("★ 只取 `word[+4]`：记录 +6 的 0xffff **不进格网**", w.cell(7, 7), 0x2001)

    print("[C6] ★ 记录下标来自坐标 dword 的**高 16 位**（0 基）")
    w.clear()
    w.render = [dict(rec=3, id=3001, x=2, y=42, spr=1)]
    w.extra = [(REC_ARR + 0 * REC_STRIDE + 4, "w", 9999),   # 记录 0 放个诱饵
               (REC_ARR + 0 * REC_STRIDE, "d", 1)]
    w.run(GRID_BUILD)
    case("★★ 读的是记录 3（高半 = 3），不是记录 0 ⇒ 3001", w.cell(2, 2), 3001)
    case("  诱饵 9999 没进格网", w.nonzero(), 1)

    print("[C7] 行宽 = 440 word（0x1b8）")
    w.clear()
    w.render = [dict(rec=0, id=0x0A01, x=0, y=40, spr=1),
                dict(rec=1, id=0x0A02, x=1, y=40, spr=1),
                dict(rec=2, id=0x0A03, x=0, y=41, spr=1)]
    w.run(GRID_BUILD)
    case("(x=0,y=0) → 0x0a01", w.cell(0, 0), 0x0A01)
    case("(x=1,y=0) → 0x0a02", w.cell(1, 0), 0x0A02)
    case("(x=0,y=1) → 0x0a03（★ 行距 440 不是 439/441）", w.cell(0, 1), 0x0A03)
    case("  三个非零格", w.nonzero(), 3)

    print("[C8] ★ 物件标记 `0x8000|((下标+1)<<8)` 要看物件表的 `+5`（业主+1）")
    w.clear()
    w.obj = {0: 1}                                # 物件 0 有主
    w.render = [dict(rec=0, id=0x8100, x=4, y=44, spr=1)]
    w.run(GRID_BUILD)
    case("★★ 物件 0 的 +5 ≠ 0（有主）⇒ **不画**", w.nonzero(), 0)
    w.obj = {0: 0}
    r = w.run(GRID_BUILD)
    case("  同一格值、物件 0 的 +5 == 0 ⇒ 画上去 0x8100", w.cell(4, 4), 0x8100)
    w.clear()
    w.obj = {5: 2}                                 # 物件 5 有主
    w.render = [dict(rec=0, id=0x8600, x=4, y=44, spr=1)]
    w.run(GRID_BUILD)
    case("★ 下标解出 5（(0x8600>>8)&0x3f − 1）⇒ 查物件表 5 ⇒ 有主 ⇒ 不画", w.nonzero(), 0)
    w.obj = {5: 0, 0: 7}
    w.run(GRID_BUILD)
    case("  物件 5 无主、物件 0 有主 ⇒ 仍画（查对了槽）", w.cell(4, 4), 0x8600)

    print("[C9] ★ 玩家标记 `0x8000|(1<<p)`（bits13..8 == 0）不过物件表那道闸")
    for pid, ident in ((0, 0x8001), (1, 0x8002), (2, 0x8004), (3, 0x8008)):
        w.clear()
        w.obj = {0: 9, 1: 9}                       # 物件表全「有主」，不能被误查
        w.render = [dict(rec=0, id=ident, x=6, y=46, spr=1)]
        w.run(GRID_BUILD)
        case(f"★ 玩家标记 {ident:#06x}（玩家 {pid}）⇒ 画进格网", w.cell(6, 6), ident)

    print("[C10] ★ 渲染列表为空 ⇒ 提前返回：格网清了，但 0x474930/0x474934 **不清**")
    w.clear()
    w.grid_prefill = GRID_FILL
    w.cam = [SENTINEL, SENTINEL]
    w.render = []
    w.render_count = 0
    w.run(GRID_BUILD)
    case("★ [0x48bac8] == 0 ⇒ 格网仍被 memset 清空", w.nonzero(), 0)
    case("★★ 0x474930 保持哨兵（提前返回，没走到收尾）", w.emu.readu32(CAM0), SENTINEL)
    case("★★ 0x474934 保持哨兵", w.emu.readu32(CAM1), SENTINEL)

    print("[C11] 列表非空 ⇒ 收尾一定把 0x474930/0x474934 清零（哪怕一格都没画）")
    w.clear()
    w.cam = [SENTINEL, SENTINEL]
    w.render = [dict(rec=0, id=0x0000, x=1, y=41, spr=1)]   # 格值 0 ⇒ 一格不画
    w.run(GRID_BUILD)
    case("全部被跳过 ⇒ 格网全 0", w.nonzero(), 0)
    case("★ 0x474930 被清 0", w.emu.readu32(CAM0), 0)
    case("★ 0x474934 被清 0", w.emu.readu32(CAM1), 0)

    print("[C12] 多项：各自落自己的格、互不干扰")
    w.clear()
    w.render = [dict(rec=0, id=0x2001, x=1, y=41, spr=1),
                dict(rec=1, id=0x2002, x=2, y=42, spr=1),
                dict(rec=2, id=0x4003, x=3, y=43, spr=1),
                dict(rec=3, id=0x6004, x=4, y=44, spr=1)]
    w.run(GRID_BUILD)
    case("4 项 ⇒ 4 个非零格", w.nonzero(), 4)
    case("  [1,1] = 0x2001", w.cell(1, 1), 0x2001)
    case("  [2,2] = 0x2002", w.cell(2, 2), 0x2002)
    case("  [3,3] = 0x4003", w.cell(3, 3), 0x4003)
    case("  [4,4] = 0x6004", w.cell(4, 4), 0x6004)


def main():
    print("通道 2 差分测试 · 第二批 [A] 0x41e9e2 購地卡 AI / "
          "[B] 0x42062b 查封卡 AI / [C] 0x409de7 视野格网重建器\n")
    w = World()
    section_a(w)
    section_b(w)
    section_c(w)

    total = len(RESULTS)
    passed = sum(RESULTS)
    print(f"\n{'=' * 78}\n合计 {passed}/{total} 通过"
          + ("" if passed == total else f"  ❌ {total - passed} 条失败"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
