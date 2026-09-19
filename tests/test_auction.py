#!/usr/bin/env python3
"""
通道 2 差分测试 · **拍卖全流程** `run_auction` / `sub_0043bde5`（VA `0x0043bde5`，725 条 / 2735 B）

复刻侧对应：
  · `packages/core/src/rules/auction.ts`（`auctionBasePrice`/`auctionSeatStatus`/
    `auctionAiLimits`/`auctionAiRaise`/`auctionFinished`/`auctionOutcome`/`settleAuction`）
  · `packages/core/src/state/reduce.ts`（`openAuction`/`startAuction`/`settleAuctionExplicit`）

本函数是**阻塞式**的：调用它就跑完一整场（建座位表 → 算心理价位 → 开窗等竞价 → 结算）。
驱动分两层：

  ① **整支驱动** `0x43bde5` → `ret`（`emu.call`）：窗口/绘图/消息泵按「打桩清单」
     换成桩后，「标的判定 → 起拍价 → 座位表 → 心理价位（真跑 `0x439f0d` + 真随机流）
     → 落槌结算（真跑 `0x41d2c6` 付款）→ 返回值」整条确定性主链**全是真机器码**。
     另用两个**中途停址**观察中间态：`P1=0x43c2f5`（建表循环刚结束，状态码还是原值）
     与 `P2=0x43c680`（显示循环结束：非 0 状态座位已被删、心理价位已算完）。
  ② **分段驱动** 竞价循环里那两段**纯规则**（它们是拍卖窗口过程 `0x43a2dd` 的内联块，
     没有独立入口、`jmp` 目标也不在函数图里）：AI 出价档位 `loc_0043b0ef`..`0x43b219`
     （= 复刻 `auctionAiRaise`）与终局判定 `loc_0043b295`..`0x43b2f6`
     （= 复刻 `auctionFinished`）。用 `eval_block` / `UC_HOOK_CODE` 探针驱动。

## 范围边界（诚实声明）

**驱动了**：起拍价两支（地產 `+0x1c` / 設施 `+0x22`）、`(2000,4000)`/`(4000,6000)`
开区间判据、标的指针与「設施标志」写点、图标号 `[0x48c494]`、座位表
（`who_plays==0` 无座位 / 状态 8「出不起底价」/ 状态 1..6 六个阻碍计数 / 卖家 7 /
**非 0 状态座位在显示循环里被整格删掉**）、心理价位的调用闸门与随机数消费
（真跑 `0x439f0d`）、落槌结算（归属、`flast` 到期日、`pay_money` 付款方向与金额、
返回值）、AI 加价档位全部分支、终局判定三分支。

**未驱动（表现层 / 消息层）**：100ms 定时器驱动的竞价状态机与动画（`0x43a2dd` 的
`0x113`/`0x401`/`0x402`/`0x405`/`0x407`/`0xf`/`0x201..0x203` 各分支）、消息泵
`0x4018e7`、真人按钮命中测试、`0x43b5ff`/`0x43b945`/`0x43b9d6`/`0x43baa7` 四处
**按帧**的 `rand`（`magic-house.md` §5.2.1 已登记为「时间相关，无头不可能对齐」）、
MKF 贴图与音效。⇒ 「竞价循环怎么把价格从底价推到成交价」这一步本测试**没有**端到端
跑；价格推进的规则由 ② 覆盖，`[0x48c488]` 的逐拍更新（`0x43a4ae`，在 `0x407` 分支里）
**未驱动**（本测试把「落槌时的现价」当输入注入）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x004018e7` | 拍卖窗口的模态消息泵（`PostMessage(0x401,…)` + `PeekMessage` 循环，返回 0x402 的 wParam）| 记下 `(proc, param)` → 把注入的「现价」写回 `[0x48c488]` → 返回**注入的**得标座位号 | 它的语义 = 「跑消息循环」，正是本测试不驱动的表现层；桩把「窗户里发生了什么」变成可注入的输入 |
| `0x00456f2d` | CRT `rand()` | 从暂存序列取值并**自增计数槽** | 本测试钉的是「谁掷、掷几次、顺序」；PRNG 算法本身上下 `tests/test_prng.py` 已差分 |
| `0x00450441` | 按编号取资源字符串（表 `0x4762f4`）| 记下编号、返回暂存区字符串 | 纯表现层资源加载（Unicorn 里没有 MKF 资源）|
| `0x00451a5a` | 建拍卖窗口 | 返回一个暂存区地址 | 同上；返回值只被当**基址做算术**后转交给其它桩 |
| `0x0044f9d8`/`0x004563f5`/`0x00456418`/`0x0044fabc`/`0x00457110`/`0x0045663e`/`0x00457d96`/`0x0044ec30`/`0x00454176`/`0x004549cf`/`0x00454bcc`/`0x00454240`/`0x0041d476`/`0x004528b9`/`0x0040a4e1`/`0x00456e11` | 绘图 / 文本 / 镜头 / 睡眠 / 重绘 / 释放 | `xor eax,eax; ret`（`0x4549cf` 返回 0 以跳过后面的 `0x454bcc`）| 全是画与音与主循环节奏；**没有一个**参与规则判定 |
| `[0x48a0e0]` 的两个虚调用槽 `+0x64`/`+0x80` | DirectDraw 风格对象 | 假对象 + 假 vtable，项指向 `ret 0x14` / `ret 8` 的小桩 | 调用方不 `add esp`（被调方负责清栈）⇒ 桩必须带 `ret N`，否则栈立刻错位 |
| `0x00439f0d` | 「心理价位」 | **真跑** | 本测试要的正是**调用闸门 + 随机数消费**（公式已由 `test_auction_limit.py` 14/14 独立钉住）|
| `0x0041d2c6` | `pay_money` | **真跑**（`[0x46cad8]=2` 关面板刷新；金额恒 < 现金 ⇒ 不进破产分支）| 付款方向/金额正是要判的规则（该函数另由 `test_money_move.py` 29/29 钉住）|
| `0x004521cb` | 到期日加法（16 位回卷）| **真跑** | 纯函数，无副作用、无调用 |
| `0x00456f60` | CRT `memset` | **真跑** | 座位表清零（`0x43c0de`）是被断言的一部分 |
| `0x00457dbc` | `__round_toward_zero` | **真跑** | 起拍价取整方向正是要判的规则 |

跑法：cd rich4-spec && .venv/bin/python tests/test_auction.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import (  # noqa: E402
    RET_SENTINEL,
    SCRATCH_BASE,
    STACK_TOP,
    STUB_BASE,
    Emu,
    GP_REGISTERS,
)
from unicorn import UC_HOOK_CODE, UcError  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ESP  # noqa: E402

# ── 被测函数与内联块 ──
AUCTION = 0x43BDE5              # run_auction（整支）
P1_BUILD_END = 0x43C2F5         # 建表循环刚结束（状态码还是原值）
P2_DISPLAY_END = 0x43C680       # 显示循环结束（非 0 状态座位已删、心理价位已算）
AI_RAISE_ENTRY = 0x43B0EF       # 竞价循环：AI 出价档位（含压价段）
AI_RAISE_END = 0x43B22B         # ★ 含 0x43b219..0x43b22a 的「单座位强制最小加价」
FINISH_ENTRY = 0x43B295         # 竞价循环：终局判定
FIN_BAIL = 0x43B2CD             # 流標出口
FIN_SETTLE = 0x43B2F6           # 成交候选（再查 [0x48c4a8] != -1）
FIN_NEXT = 0x43B3C2             # 换下一家
FIN_PAY = 0x43B303              # 成交动画段入口（= 确认为成交）

# ── 被真跑的函数（**绝不能**打桩）──
AI_LIMIT = 0x439F0D
PAY_MONEY = 0x41D2C6
DATE_ADD = 0x4521CB
MEMSET = 0x456F60
ROUND_ZERO = 0x457DBC

# ── 打桩的 UI / 消息层 ──
MODAL_PUMP = 0x4018E7
PRNG = 0x456F2D
LOAD_STRING = 0x450441
CREATE_WINDOW = 0x451A5A
UI_NOOPS = (
    0x44F9D8, 0x4563F5, 0x456418, 0x44FABC, 0x457110, 0x45663E, 0x457D96,
    0x44EC30, 0x454176, 0x4549CF, 0x454BCC, 0x454240, 0x41D476, 0x4528B9,
    0x40A4E1, 0x456E11,
)

# ── 全局量与表 ──
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_CHAR, P_WHO, P_CASH, P_BANK = 0x13, 0x15, 0x1C, 0x20
P_PAID, P_RECEIVED = 0x5C, 0x60
P_BLOCK = (0x32, 0x33, 0x34, 0x35, 0x36, 0x37)   # 四个阻碍计数 + 冬眠 + 夢遊

NUM_PLAYERS = 0x499114
PRICE_INDEX = 0x4990E8
LAND_TABLE_PTR, LAND_COUNT = 0x498E84, 0x498E98
FAC_TABLE_PTR, FAC_COUNT = 0x498E88, 0x498E8C
G4991B6, G4991B8 = 0x4991B6, 0x4991B8
DEED_TERM = 0x499110
CURRENT_DATE = 0x497160
CURRENT_PLAYER = 0x49910C
POOL = 0x499080
GAME_MODE = 0x46CAD8          # > 1 ⇒ pay_money 不刷面板

SEAT_TABLE = 0x48C434         # 座位表：4 槽 × 0x14
SEAT_STRIDE = 0x14
S_PLAYER, S_STATUS, S_LIMIT = 0x00, 0x02, 0x04   # ★ 心理价位在 **+4**（0x48c438）
S_STR0, S_STR1, S_STR2 = 0x08, 0x0C, 0x10        # 三张字符串（名字/…）
SEAT_CUR = 0x48C4A4           # 当前座位槽
SEAT_TOP = 0x48C4A8           # 当前最高出价者槽 / -1
SEAT_NSINGLE = 0x48C4B1       # byte：可出价座位数（窗口过程写，本测试直接铺）

BASE_PRICE = 0x48C488         # ★ 起拍价 **且** 竞价期间的「现价」
FACILITY_FLAG = 0x48C490
LAND_OBJ, FAC_OBJ = 0x48C48C, 0x48C498
ICON_INDEX = 0x48C494

LAND_STRIDE = 0x34
L_NAME, L_TYPE, L_OWNER, L_LEVEL, L_PRICE, L_FLAST = 0x04, 0x18, 0x19, 0x1A, 0x1C, 0x30
FAC_STRIDE = 0x38
F_NAME, F_TYPE, F_OWNER, F_LEVEL, F_PRICE, F_FLAST = 0x04, 0x18, 0x19, 0x1A, 0x22, 0x34

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0
DEED_TABLE = 0x4751F0
RAISE_STEPS = 0x475BA2        # [1..5] = 100 / 500 / 1000 / 5000 / 10000

# ── 数据区布局 ──
# ★ 座位表要的两张表**不能**放 64KB 的暂存区：编号 → 记录是 `(编号-2000)×0x34`，
#   编号 3999 就要 67,852 字节（暂存区只有 64KB ⇒ 实测 `UC_ERR_READ_UNMAPPED
#   @0x43be37`）。故另开一块 256KB 映射给两张表。
TABLE_BASE = 0x700000
TABLE_SIZE = 0x40000
LANDS = TABLE_BASE
FACS = TABLE_BASE + 0x20000

# ── 暂存区槽 ──
RAND_SEQ = SCRATCH_BASE + 0x0200
RAND_IDX = SCRATCH_BASE + 0x0300
STR_IDS = SCRATCH_BASE + 0x0340
STR_IDX = SCRATCH_BASE + 0x03C0
M_PROC = SCRATCH_BASE + 0x0400
M_PARAM = SCRATCH_BASE + 0x0404
M_RET = SCRATCH_BASE + 0x0408
M_PRICE = SCRATCH_BASE + 0x040C
STRPTR = SCRATCH_BASE + 0x0420
FOBJ = SCRATCH_BASE + 0x0500
FVT = SCRATCH_BASE + 0x0600

# ── 桩代码 ──
# ★ 三个「有返回值」的桩必须**整支替换在函数自己的地址上**（`patch(VA, 桩体)`），
#   不能写成「在 VA 处 `mov eax,别处; ret`」—— 那是**返回**一个地址而不是**进入**
#   那段代码（实测：模态泵那样写 ⇒ 把 0x4C0080 当座位号 ⇒ `UC_ERR_READ_UNMAPPED
#   @0x43c72d`）。
S_VT64 = STUB_BASE + 0xF0       # 5 个参数 ⇒ ret 0x14
S_VT80 = STUB_BASE + 0xF8       # 2 个参数 ⇒ ret 8

SENTINEL = 0x5A5A5A5A
RESULTS = []


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >= (1 << 31) else x


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<12} 期望 {want!s}")
    return ok


class World:
    """一个 exe 镜像 + 一局可注入的拍卖现场。"""

    def __init__(self):
        self.emu = Emu()
        self.emu.mu.mem_map(TABLE_BASE, TABLE_SIZE)   # 两张表的数据区（见文件头）
        self._install_stubs()
        self.clear()

    # ────────────────────────── 桩 ──────────────────────────
    def _install_stubs(self):
        e = self.emu
        # rand()：从序列取值 + 计数（整支替换 0x456f2d 本体）
        e.patch(PRNG, (
            b"\xA1" + struct.pack("<I", RAND_IDX)            # mov eax,[RAND_IDX]
            + b"\x8B\x0C\x85" + struct.pack("<I", RAND_SEQ)  # mov ecx,[RAND_SEQ+eax*4]
            + b"\x8D\x50\x01"                                # lea edx,[eax+1]
            + b"\x89\x15" + struct.pack("<I", RAND_IDX)      # mov [RAND_IDX],edx
            + b"\x89\xC8"                                    # mov eax,ecx
            + b"\xC3"
        ))
        # 取字符串：记编号，返回暂存指针（整支替换 0x450441 本体）
        e.patch(LOAD_STRING, (
            b"\x8B\x54\x24\x08"                              # mov edx,[esp+8]  (= 编号)
            + b"\xA1" + struct.pack("<I", STR_IDX)           # mov eax,[STR_IDX]
            + b"\x89\x14\x85" + struct.pack("<I", STR_IDS)   # mov [STR_IDS+eax*4],edx
            + b"\x40"                                        # inc eax
            + b"\xA3" + struct.pack("<I", STR_IDX)           # mov [STR_IDX],eax
            + b"\xB8" + struct.pack("<I", STRPTR)            # mov eax,STRPTR
            + b"\xC3"
        ))
        # 模态消息泵：记 (proc, param) → 把注入的「现价」写回 [0x48c488] → 返回注入的座位号
        e.patch(MODAL_PUMP, (
            b"\x8B\x44\x24\x04"                              # mov eax,[esp+4]
            + b"\xA3" + struct.pack("<I", M_PROC)
            + b"\x8B\x44\x24\x08"                            # mov eax,[esp+8]
            + b"\xA3" + struct.pack("<I", M_PARAM)
            + b"\xA1" + struct.pack("<I", M_PRICE)           # mov eax,[M_PRICE]
            + b"\xA3" + struct.pack("<I", BASE_PRICE)        # mov [0x48c488],eax
            + b"\xA1" + struct.pack("<I", M_RET)
            + b"\xC3"
        ))
        e.patch(CREATE_WINDOW, b"\xB8" + struct.pack("<I", SCRATCH_BASE + 0x8000) + b"\xC3")
        for va in UI_NOOPS:
            e.patch(va, b"\x31\xC0\xC3")                     # xor eax,eax; ret
        e.patch(S_VT64, b"\xC2\x14\x00")
        e.patch(S_VT80, b"\xC2\x08\x00")

    # ────────────────────────── 现场 ──────────────────────────
    def clear(self):
        self.num_players = 4
        self.price_index = 1
        self.g4991b6 = 0
        self.g4991b8 = 0
        self.deed_term = 0
        self.current_date = 0x0100
        self.pool0 = 0
        self.players = [dict(who=0, char=0, cash=0, bank=0, blocks=(0,) * 6)
                        for _ in range(4)]
        self.lands = {}          # 下标(= 编号-2000) → dict(owner, level, price, name, type, flast)
        self.facs = {}
        self.num_lands = 0
        self.num_facs = 0
        self.rand_seq = [0] * 64
        self.base_sentinel = SENTINEL
        self.flag_sentinel = SENTINEL
        self.seats = None        # None ⇒ 铺 0xAB 哨兵（证明 memset 清了整张 0x50）
        self.seat_cur = SENTINEL
        self.seat_top = SENTINEL
        self.seat_nsingle = 2
        self.call_args = (0, 0, 0)
        self.expected_base = 0
        self.trace = False
        self.trace_hits = set()

    def player(self, p, who=0, char=0, cash=0, bank=0, blocks=(0,) * 6):
        self.players[p] = dict(who=who, char=char, cash=cash, bank=bank, blocks=blocks)
        return self

    def land(self, idx, owner=0, level=0, price=0, name=b"", type_=0, flast=SENTINEL):
        self.lands[idx] = dict(owner=owner, level=level, price=price, name=name,
                               type=type_, flast=flast)
        self.num_lands = max(self.num_lands, idx)
        return self

    def fac(self, idx, owner=0, level=0, price=0, name=b"", type_=0, flast=SENTINEL):
        self.facs[idx] = dict(owner=owner, level=level, price=price, name=name,
                              type=type_, flast=flast)
        self.num_facs = max(self.num_facs, idx)
        return self

    def _setup(self, emu):
        emu.write32(NUM_PLAYERS, self.num_players)
        emu.write32(PRICE_INDEX, self.price_index)
        emu.write32(G4991B6, self.g4991b6)
        emu.write32(G4991B8, self.g4991b8 & 0xFFFFFFFF)
        emu.write32(DEED_TERM, self.deed_term)
        emu.write32(CURRENT_DATE, self.current_date)
        emu.write32(CURRENT_PLAYER, 0)
        emu.write32(POOL, self.pool0)
        emu.write32(GAME_MODE, 2)                  # 关掉 pay_money 的面板刷新
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(LAND_COUNT, self.num_lands)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(FAC_COUNT, self.num_facs)
        emu.write32(BASE_PRICE, self.base_sentinel)
        emu.write32(FACILITY_FLAG, self.flag_sentinel)
        emu.write32(SEAT_CUR, self.seat_cur)
        emu.write32(SEAT_TOP, self.seat_top)
        emu.write8(SEAT_NSINGLE, self.seat_nsingle)
        # ★ 给 eval_block 用的手搓实参槽（函数序言后 arg0 落在 [esp+0xac] = STACK_TOP+4）
        for i, a in enumerate(self.call_args):
            emu.write(STACK_TOP + 4 + i * 4, struct.pack("<I", a & 0xFFFFFFFF))
        # 假对象 / 假 vtable（两个虚调用槽）
        emu.write32(0x48A0E0, FOBJ)
        emu.write32(FOBJ, FVT)
        emu.write32(FVT + 0x64, S_VT64)
        emu.write32(FVT + 0x80, S_VT80)
        # 玩家记录
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write(pb, b"\x00" * PLAYER_STRIDE)
            d = self.players[p]
            emu.write8(pb + P_CHAR, d["char"])
            emu.write8(pb + P_WHO, d["who"])
            emu.write32(pb + P_CASH, i32(d["cash"]))
            emu.write32(pb + P_BANK, i32(d["bank"]))
            for off, v in zip(P_BLOCK, d["blocks"]):
                emu.write8(pb + off, v)
        # 两张表（数据区跨调用保留 ⇒ 先按用到的最大下标清干净再铺）
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * (max(self.lands, default=0) + 1)))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * (max(self.facs, default=0) + 1)))
        for idx, l in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write(b + L_NAME, l["name"] + b"\x00")
            emu.write8(b + L_TYPE, l["type"])
            emu.write8(b + L_OWNER, l["owner"])
            emu.write8(b + L_LEVEL, l["level"])
            emu.write16(b + L_PRICE, l["price"] & 0xFFFF)
            emu.write32(b + L_FLAST, l["flast"] & 0xFFFFFFFF)
        for idx, f in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write(b + F_NAME, f["name"] + b"\x00")
            emu.write8(b + F_TYPE, f["type"])
            emu.write8(b + F_OWNER, f["owner"])
            emu.write8(b + F_LEVEL, f["level"])
            emu.write16(b + F_PRICE, f["price"] & 0xFFFF)
            emu.write32(b + F_FLAST, f["flast"] & 0xFFFFFFFF)
        # 座位表
        if self.seats is None:
            emu.write(SEAT_TABLE, b"\xAB" * 0x50)   # 哨兵：证明 0x456f60 的清零
        else:
            emu.write(SEAT_TABLE, b"\x00" * 0x50)
            for i, s in enumerate(self.seats):
                b = SEAT_TABLE + i * SEAT_STRIDE
                emu.write16(b + S_PLAYER, s.get("player", 0))
                emu.write16(b + S_STATUS, s.get("status", 0))
                emu.write32(b + S_LIMIT, i32(s.get("limit", 0)))
        # 暂存区数据
        emu.scratch_write(RAND_IDX, struct.pack("<I", 0))
        emu.scratch_write(STR_IDX, struct.pack("<I", 0))
        emu.scratch_write(STR_IDS, b"\x00" * 64)
        emu.scratch_write(STRPTR, b"AUCTION\x00")
        for i, v in enumerate(self.rand_seq):
            emu.scratch_write(RAND_SEQ + i * 4, struct.pack("<I", v & 0xFFFFFFFF))

    # ────────────────────────── 驱动 ──────────────────────────
    def run(self, seller, entity, flag=1, winner=None, modal_price=None):
        """整支驱动 0x43bde5 到 ret（含结算与返回值）。"""
        e = self.emu
        self.call_args = (seller, entity, flag)
        e.scratch_write(M_RET, struct.pack("<I", 0xFFFFFFFF if winner is None else winner))
        e.scratch_write(M_PRICE, struct.pack("<I", (self.expected_base if modal_price is None
                                                   else modal_price) & 0xFFFFFFFF))
        hook = None
        if self.trace:
            self.trace_hits = set()

            def rec(mu, addr, size, user):
                self.trace_hits.add(addr)

            hook = e.mu.hook_add(UC_HOOK_CODE, rec)
        try:
            r = e.call(AUCTION, [seller, entity, flag], setup=self._setup)
        finally:
            if hook is not None:
                e.mu.hook_del(hook)
        out = self._observe(entity)
        out["ret"] = r["eax"]
        out["hits"] = set(self.trace_hits)
        return out

    def _observe(self, entity):
        e = self.emu
        in_land = LAND_MARK < entity < FAC_MARK
        in_fac = FAC_MARK < entity < 0x1770
        return {
            "base": e.readu32(BASE_PRICE),
            "flag": e.readu32(FACILITY_FLAG),
            "land_obj": e.readu32(LAND_OBJ),
            "fac_obj": e.readu32(FAC_OBJ),
            "icon": e.readu32(ICON_INDEX),
            "seats": [self._seat(i, e) for i in range(4)],
            "limits": [e.readu32(SEAT_TABLE + i * SEAT_STRIDE + S_LIMIT) for i in range(4)],
            "rand_calls": e.readu32(RAND_IDX),
            "str_ids": [e.readu32(STR_IDS + i * 4) for i in range(e.readu32(STR_IDX))],
            "m_proc": e.readu32(M_PROC),
            "m_param": e.readu32(M_PARAM),
            "cash": [e.read32(PLAYER_BASE + p * PLAYER_STRIDE + P_CASH) for p in range(4)],
            "bank": [e.read32(PLAYER_BASE + p * PLAYER_STRIDE + P_BANK) for p in range(4)],
            "paid": [e.read32(PLAYER_BASE + p * PLAYER_STRIDE + P_PAID) for p in range(4)],
            "received": [e.read32(PLAYER_BASE + p * PLAYER_STRIDE + P_RECEIVED)
                         for p in range(4)],
            "pool": e.read32(POOL),
            "land_owner": e.read8(LANDS + (entity - LAND_MARK) * LAND_STRIDE + L_OWNER)
            if in_land else None,
            "land_flast": e.readu32(LANDS + (entity - LAND_MARK) * LAND_STRIDE + L_FLAST)
            if in_land else None,
            "fac_owner": e.read8(FACS + (entity - FAC_MARK) * FAC_STRIDE + F_OWNER)
            if in_fac else None,
            "fac_flast": e.readu32(FACS + (entity - FAC_MARK) * FAC_STRIDE + F_FLAST)
            if in_fac else None,
        }

    @staticmethod
    def _seat(i, e):
        b = SEAT_TABLE + i * SEAT_STRIDE
        return {
            "player": e.read16(b + S_PLAYER),
            "status": e.read16(b + S_STATUS),
            "limit": e.read32(b + S_LIMIT),
            "str0": e.readu32(b + S_STR0),
            "raw": e.read(b, SEAT_STRIDE),
        }

    def midway(self, stop, seller=0, entity=LAND_MARK + 1, flag=1):
        """从函数入口跑到中途停址（观察建表 / 显示循环的中间态）。"""
        self.call_args = (seller, entity, flag)
        r = self.emu.eval_block(AUCTION, stop, {}, setup=self._setup)
        out = self._observe(entity)
        out["seat_count"] = self.emu.readu32(STACK_TOP - 0x1C)   # [esp+0x8c]
        out["edi"] = i32(r["regs"]["edi"])
        return out

    def probe(self, start, stops, regs=None):
        """从 start 跑，命中 stops 里任一地址就停；返回 (命中的地址, 异常)。"""
        e = self.emu
        e.reset()
        self._setup(e)
        sp = STACK_TOP
        e.mu.mem_write(sp, struct.pack("<I", RET_SENTINEL))
        e.mu.reg_write(UC_X86_REG_ESP, sp)
        e.mu.reg_write(UC_X86_REG_EBP, sp)
        for name, val in (regs or {}).items():
            e.mu.reg_write(GP_REGISTERS[name], val & 0xFFFFFFFF)
        hit = []

        def hook(mu, addr, size, user):
            if addr in stops:
                hit.append(addr)
                mu.emu_stop()

        h = e.mu.hook_add(UC_HOOK_CODE, hook)
        err = None
        try:
            e.mu.emu_start(start, 0xFFFFFFFF, count=20000)
        except UcError as exc:            # noqa: PERF203
            err = exc
        finally:
            e.mu.hook_del(h)
        return (hit[0] if hit else None), err

    def ai_raise(self, price, limit, cash, top, top_cash, nsingles=2):
        """驱动 AI 出价档位块，返回 ebx（0=PASS、1..5=加价档、6=放棄）。"""
        self.seats = [
            {"player": 1, "status": 0, "limit": limit},
            {"player": 2, "status": 0, "limit": 0},
        ]
        self.players[0]["cash"] = cash
        self.players[1]["cash"] = top_cash
        self.seat_cur = 0
        self.seat_top = top
        self.seat_nsingle = nsingles
        self.base_sentinel = price
        r = self.emu.eval_block(AI_RAISE_ENTRY, AI_RAISE_END, {}, setup=self._setup)
        return i32(r["regs"]["ebx"]), r["regs"]

    # ────────────────────────── 模型 ──────────────────────────
    @staticmethod
    def date_add(date, tv):
        """0x4521cb：32 位加法；仅当 arg1 的 bits 8-15 ≠ 0 **且** 和的 bits 8-15 > 0xc00 时 +0xf400。"""
        r = (date + tv) & 0xFFFFFFFF
        if (tv >> 8) & 0xFF and (r & 0xFF00) > 0xC00:
            r = (r + 0xF400) & 0xFFFFFFFF
        return r

    def model_base(self, price, level, pi):
        """起拍价 = trunc(地价 × (1 + 0.5×等级)) × 物价指数（32 位回绕）。"""
        return i32(((price * (2 + level)) // 2) * pi)

    def model_limit(self, entity, player1, base, pi, cash, r1, r2):
        """fcn_00439f0d 的公式（f32 中间量 + 向零截断 + 夹现金）。"""
        if entity < FAC_MARK:
            t = self.lands[entity - LAND_MARK]
            total = self.num_lands
            unowned = sum(1 for i in self.lands.values() if i["owner"] == 0)
            same = sum(1 for i in self.lands.values()
                       if i["owner"] == player1 and i["name"] == t["name"])
            price_field = t["price"]
            scale = ((t["level"] >> 1) + 1 + same)
        else:
            t = self.facs[entity - FAC_MARK]
            total = self.num_facs
            unowned = sum(1 for i in self.facs.values() if i["owner"] == 0)
            price_field = t["price"]
            scale = ((t["level"] >> 1) + 1)
        factor = f32((r1 / 32767.0) * 0.3 + 0.5)
        scarcity = f32(6.0 - 4.0 * (unowned / total))
        v1 = i32(int(i32(scale * base * pi) * scarcity * factor))
        lv = f32(i32(price_field * pi))
        v2 = int((r2 * f32(1.0 / 65536.0) + 3.0) * lv)
        return min(v1, v2, cash)


def main():
    print("差分测试 · 拍卖全流程 run_auction 0x43bde5（2735 B）")
    print("对照：rules/auction.ts + state/reduce.ts（openAuction/startAuction）\n")
    w = World()
    ALL_OFF = [dict(who=0, char=0, cash=0, bank=0, blocks=(0,) * 6) for _ in range(4)]

    # ══════════════════ [A] 标的编号区间与两支分派 ══════════════════
    print("[A] 标的编号：2000 < 编号 < 4000 走地產、4000 < 编号 < 6000 走設施（两端都开）")
    for pid in (2000, 2001, 3999, 4000, 4001, 5999, 6000):
        w.clear()
        w.num_players = 4                      # 全员 who_plays = 0 ⇒ 0 个座位
        w.price_index = 2
        if pid < FAC_MARK:
            w.land(pid - LAND_MARK, owner=1, level=1, price=1001)
            want = w.model_base(1001, 1, 2)
            want_obj, want_flag = (LANDS + (pid - LAND_MARK) * LAND_STRIDE, 0)
        else:
            w.fac(pid - FAC_MARK, owner=1, level=1, price=999)
            want = w.model_base(999, 1, 2)
            want_obj, want_flag = (FACS + (pid - FAC_MARK) * FAC_STRIDE, 1)
        r = w.run(seller=2, entity=pid, flag=1, winner=None)
        taken = 2000 < pid < 4000 or 4000 < pid < 6000
        if not taken:
            case(f"编号 {pid} 落在区间外 ⇒ 不设标的、不动起拍价", r["base"], SENTINEL)
            case(f"  {pid}：設施标志保持哨兵", r["flag"], SENTINEL)
            case(f"  {pid}：座位 0 个 ⇒ 返回 0", r["ret"], 0)
        else:
            case(f"编号 {pid} ⇒ 起拍价 = trunc({1001 if pid < FAC_MARK else 999}×1.5)×2 = {want}",
                 r["base"], want)
            case(f"  {pid}：設施标志 = {want_flag}", r["flag"], want_flag)
            case(f"  {pid}：标的指针 = 表基址 + {want_obj - (LANDS if pid < FAC_MARK else FACS)}",
                 r["land_obj"] if pid < FAC_MARK else r["fac_obj"], want_obj)

    # ══════════════════ [B] 起拍价公式（向零截断）══════════════════
    print("\n[B] 起拍价 `trunc(地价×(1+0.5×等级)) × 物价指数`（★ 向零截断，不是就近取偶）")
    for price, level, pi, want, desc in [
        (1000, 0, 1, 1000, "等级 0"),
        (1001, 1, 1, 1501, "★ 1001×1.5 = 1501.5 ⇒ 向下 1501（就近取偶会给 1502）"),
        (1001, 3, 1, 2502, "★ 1001×2.5 = 2502.5 ⇒ 2502"),
        (3, 1, 1, 4, "3×1.5 = 4.5 ⇒ 4"),
        (3000, 2, 2, 12000, "等级 2 × 物价 2"),
        (65535, 1, 1, 98302, "★ 地价是 u16：65535×1.5 = 98302.5 ⇒ 98302"),
        (100, 4, 3, 900, "等級 4、物价 3"),
    ]:
        w.clear()
        w.num_players = 1
        w.price_index = pi
        w.land(1, owner=0, level=level, price=price)
        case(f"地產 {desc}（价 {price}/级 {level}/物价 {pi}）",
             w.run(seller=2, entity=LAND_MARK + 1, flag=1, winner=None)["base"], want)

    w.clear()
    w.num_players = 1
    w.price_index = 1
    w.fac(1, owner=0, level=1, price=999)      # 設施单价读 +0x22
    case("★ 設施支单价读 +0x22：999×1.5 ⇒ 1498（不是就近 1499）",
         w.run(seller=2, entity=FAC_MARK + 1, flag=1, winner=None)["base"], 1498)

    # ══════════════════ [C] 窗口图标号 [0x48c494] ══════════════════
    print("\n[C] 窗口图标号 `[0x48c494]`（表现层索引，但由本函数确定性地算出）")
    w.clear()
    w.num_players = 1
    w.player(0, who=1, char=5)
    w.land(1, owner=0, level=0, price=100)
    case("地產 · 等级 0 · 无主 ⇒ 图标 0x5a",
         w.run(seller=0, entity=LAND_MARK + 1, winner=None)["icon"], 0x5A)
    w.clear()
    w.num_players = 1
    w.player(0, who=1, char=7)
    w.land(1, owner=1, level=0, price=100)
    case("地產 · 等级 0 · 有主 ⇒ 0x5b + 地主角色号(player[owner-1].+0x13)",
         w.run(seller=-1, entity=LAND_MARK + 1, winner=None)["icon"], 0x5B + 7)
    w.clear()
    w.num_players = 1
    w.player(0, who=1)
    w.land(1, owner=1, level=2, price=100, type_=3)
    case("地產 · 等级≠0 · 类型≠0 ⇒ 0x32",
         w.run(seller=-1, entity=LAND_MARK + 1, winner=None)["icon"], 0x32)
    w.clear()
    w.num_players = 1
    w.player(0, who=1)
    w.g4991b8 = 3
    w.land(1, owner=1, level=2, price=100, type_=0)
    case("地產 · 等级≠0 · 类型 0 · [0x4991b6]==0 ⇒ 5×[0x4991b8]+等级+0x1d",
         w.run(seller=-1, entity=LAND_MARK + 1, winner=None)["icon"], 15 + 2 + 0x1D)
    w.clear()
    w.num_players = 1
    w.player(0, who=1)
    w.fac(1, owner=0, level=0, price=100)
    case("設施 · 等级 0 · 无主 ⇒ 0x67",
         w.run(seller=-1, entity=FAC_MARK + 1, winner=None)["icon"], 0x67)
    w.clear()
    w.num_players = 1
    w.player(0, who=1, char=7)
    w.fac(1, owner=1, level=0, price=100)
    case("設施 · 等级 0 · 有主 ⇒ 0x68 + 角色号",
         w.run(seller=-1, entity=FAC_MARK + 1, winner=None)["icon"], 0x68 + 7)

    # ══════════════════ [D] 座位表（中途停址观察）══════════════════
    print("\n[D] 座位表 0x48c434（4 槽 × 0x14）：资格、状态码、卖家 7、非 0 状态被删")

    def seat_scene(players, seller, entity=LAND_MARK + 1, base=1000):
        w.clear()
        w.num_players = len(players)
        w.price_index = 1
        for i, kw in enumerate(players):
            w.player(i, **kw)
        w.land(entity - LAND_MARK, owner=0, level=0, price=base)
        w.expected_base = base
        return w

    w = seat_scene([dict(who=1, char=3, cash=999999),
                    dict(who=0, char=0, cash=999999),
                    dict(who=2, char=4, cash=999999),
                    dict(who=1, char=5, cash=999999)], seller=3)
    w.rand_seq = [1000, 2000, 3000, 4000]
    b = w.midway(P1_BUILD_END, seller=3)
    case("★ 建表（P1）：出局者（who_plays==0）不占座位，其余 3 人依次坐下",
         [s["player"] for s in b["seats"]], [1, 3, 4, 0])
    case("  ★ 座位号 = 玩家下标 + 1（1 基）", b["seats"][1]["player"], 3)
    case("★ 卖家（arg0 = 3 ⇒ 玩家下标 3）状态 7", b["seats"][2]["status"], 7)
    case("★ 建表后的座位计数（局部 [esp+0x8c]）= 3", b["seat_count"], 3)
    case("★ 第一个取的串是窗口资源 0x1a，之后每个合格座位取 3 个：3×角色号+0x1b/0x1c/0x1d",
         b["str_ids"], [0x1A,
                        3 * 3 + 0x1B, 3 * 3 + 0x1C, 3 * 3 + 0x1D,
                        3 * 4 + 0x1B, 3 * 4 + 0x1C, 3 * 4 + 0x1D,
                        3 * 5 + 0x1B, 3 * 5 + 0x1C, 3 * 5 + 0x1D])
    case("  字符串指针写进座位 +8/+0xc/+0x10",
         [b["seats"][0]["str0"], b["seats"][1]["str0"]], [STRPTR, STRPTR])
    d = w.midway(P2_DISPLAY_END, seller=3)
    case("★★ 显示循环（P2）后：**卖家那一格被整格删掉**（player/status 清 0）",
         [s["player"] for s in d["seats"]], [1, 3, 0, 0])
    case("★ 空槽被 memset 清零（证明 0x456f60 清了整张 0x50）",
         d["seats"][3]["raw"], b"\x00" * SEAT_STRIDE)
    case("★ 传给窗口过程的可出价座位数（edi）= 状态 0 的座位数", d["edi"], 2)
    case("★ 心理价位写在座位 **+4**（0x48c438）：真人座位留 0、电脑座位非 0",
         [d["limits"][0] == 0, d["limits"][1] != 0], [True, True])
    r = w.run(seller=3, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★ 整支跑：窗口过程第 1 实参 = 0x43a2dd", r["m_proc"], 0x43A2DD)
    case("★ 整支跑：窗口过程第 2 实参 = 可出价座位数 = 2", r["m_param"], 2)

    # 现金 == 底价 ⇒ 状态 8（出不起）⇒ 显示循环里被删
    w = seat_scene([dict(who=1, cash=1000), dict(who=2, cash=1001),
                    dict(who=2, cash=999)], seller=-1)
    w.rand_seq = [111, 222]
    b = w.midway(P1_BUILD_END, seller=-1)
    case("★ 现金 == 底价 ⇒ 建表时状态 8（判据是 `现金 > 底价`，严格）",
         [s["status"] for s in b["seats"]], [8, 0, 8, 0])
    d = w.midway(P2_DISPLAY_END, seller=-1)
    case("★ 显示循环后状态 8 的座位被删（含现金 999 那位）",
         [s["player"] for s in d["seats"]], [0, 2, 0, 0])
    case("★ 状态 8 的座位拿不到心理价位（+4 = 0）",
         [d["limits"][0], d["limits"][2]], [0, 0])
    r = w.run(seller=-1, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★ 状态 8 的座位不掷随机数（只有 1 个可投电脑 ⇒ 恰好 2 次）", r["rand_calls"], 2)

    print("  — 状态 1..6（+0x32..+0x37）与覆盖次序（建表态 P1）")
    for blocks, want, desc in [
        ((1, 0, 0, 0, 0, 0), 1, "+0x32 ⇒ 1（坐牢）"),
        ((0, 1, 0, 0, 0, 0), 2, "+0x33 ⇒ 2（住院）"),
        ((0, 0, 1, 0, 0, 0), 3, "+0x34 ⇒ 3（消失）"),
        ((0, 0, 0, 1, 0, 0), 4, "+0x35 ⇒ 4（住店）"),
        ((0, 0, 0, 0, 1, 0), 5, "+0x36 ⇒ 5（冬眠）"),
        ((0, 0, 0, 0, 0, 1), 6, "+0x37 ⇒ 6（夢遊）"),
        ((1, 0, 0, 0, 1, 0), 5, "★ +0x32 与 +0x36 同时非 0 ⇒ 后者覆盖（5）"),
        ((1, 1, 1, 1, 1, 1), 6, "★ 六个全非 0 ⇒ 最后一个（6）"),
    ]:
        w = seat_scene([dict(who=2, cash=999999, blocks=blocks)], seller=-1)
        b = w.midway(P1_BUILD_END, seller=-1)
        case(f"  {desc}", b["seats"][0]["status"], want)
    w = seat_scene([dict(who=2, cash=999999, blocks=(1, 0, 0, 0, 0, 1))], seller=0)
    b = w.midway(P1_BUILD_END, seller=0)
    case("★ 卖家那一条**最后**写 ⇒ 即使 +0x37 非 0 也是 7", b["seats"][0]["status"], 7)

    # ══════════════════ [E] 心理价位的闸门与随机数消费 ══════════════════
    print("\n[E] 心理价位：谁掷、掷几次、存哪（真跑 0x439f0d + 注入随机序列）")
    w.clear()
    w.num_players = 3
    w.price_index = 1
    w.land(1, owner=0, level=1, price=2000, name=b"A")
    w.land(2, owner=1, level=1, price=2000, name=b"A")
    w.player(0, who=2, cash=999999)     # 电脑
    w.player(1, who=1, cash=999999)     # 真人 ⇒ 不掷
    w.player(2, who=2, cash=999999)     # 电脑
    w.expected_base = w.model_base(2000, 1, 1)
    w.rand_seq = [1000, 20000, 30000, 40000]
    r = w.run(seller=-1, entity=LAND_MARK + 1, flag=1, winner=None)
    exp0 = w.model_limit(LAND_MARK + 1, 1, w.expected_base, 1, 999999, 1000, 20000)
    exp2 = w.model_limit(LAND_MARK + 1, 3, w.expected_base, 1, 999999, 30000, 40000)
    case("★ 每个可出价的电脑座位恰好 2 次 rand（入口 + 地价支）⇒ 3 人里 2 个电脑 = 4 次",
         r["rand_calls"], 4)
    case("★ 座位 0（电脑）心理价位 = 模型值", r["limits"][0], exp0)
    case("★ 真人座位（who_plays==1，`test …,6` 为 0）不掷、价位留 0", r["limits"][1], 0)
    case("★ 座位 2（电脑）用第 3/4 个随机数", r["limits"][2], exp2)
    case("  两个电脑的价位不同 ⇒ 随机序列确实逐个座位推进", exp0 != exp2, True)

    w.clear()
    w.num_players = 3
    w.price_index = 1
    w.land(1, owner=0, level=0, price=1000, name=b"A")
    w.player(0, who=2, cash=999999, blocks=(1, 0, 0, 0, 0, 0))   # 坐牢 ⇒ 状态 1
    w.player(1, who=2, cash=999999)
    w.player(2, who=1, cash=999999)
    w.expected_base = 1000
    w.rand_seq = [5000, 6000]
    r = w.run(seller=-1, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★ 状态非 0（坐牢 1）的座位**不掷**且价位留 0", r["limits"][0], 0)
    case("  只有座位 1 掷 ⇒ 2 次", r["rand_calls"], 2)
    case("  座位 1 的价位 = 模型值",
         r["limits"][1], w.model_limit(LAND_MARK + 1, 2, 1000, 1, 999999, 5000, 6000))

    w.clear()
    w.num_players = 2
    w.price_index = 1
    w.land(1, owner=0, level=0, price=1000, name=b"A")
    w.player(0, who=2, cash=999999)
    w.player(1, who=2, cash=999999)
    w.expected_base = 1000
    w.rand_seq = [1, 2]
    r = w.run(seller=0, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★ 卖家（状态 7 ⇒ 也被删）不掷 ⇒ 只剩 1 个电脑 = 2 次", r["rand_calls"], 2)
    case("  卖家座位已被删 ⇒ +4 = 0", r["limits"][0], 0)
    case("  另一座位价位 = 模型值（用第 1/2 个随机数）",
         r["limits"][1], w.model_limit(LAND_MARK + 1, 2, 1000, 1, 999999, 1, 2))

    w.clear()
    w.num_players = 1
    w.price_index = 1
    w.land(1, owner=0, level=0, price=1000, name=b"A")
    w.player(0, who=1, cash=999999)
    w.expected_base = 1000
    w.rand_seq = [7, 8]
    r = w.run(seller=-1, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★ 全员真人 ⇒ 一次 rand 都不掷", r["rand_calls"], 0)
    case("  真人座位价位 0", r["limits"][0], 0)

    # ★ who_plays 的第 2/3 位：原版判据是 `test byte [+0x15], 6`
    w.clear()
    w.num_players = 2
    w.price_index = 1
    w.land(1, owner=0, level=0, price=1000, name=b"A")
    w.player(0, who=3, cash=999999)     # 原版：3 & 6 = 2 ≠ 0 ⇒ 算**电脑**
    w.player(1, who=1, cash=999999)
    w.expected_base = 1000
    w.rand_seq = [100, 200]
    r = w.run(seller=-1, entity=LAND_MARK + 1, flag=1, winner=None)
    case("★★ who_plays = 3（bit0|bit1）⇒ 原版按「电脑」处理：掷 2 次并算价位",
         (r["rand_calls"], r["limits"][0] != 0), (2, True))
    case("  对照 who_plays = 1（真人）⇒ 不掷",
         w.model_limit(LAND_MARK + 1, 1, 1000, 1, 999999, 100, 200) == r["limits"][0], True)

    w.clear()
    w.num_players = 1
    w.price_index = 1
    w.fac(1, owner=0, level=1, price=4000, name=b"F")
    w.fac(2, owner=1, level=1, price=4000, name=b"F")
    w.player(0, who=2, cash=999999)
    w.expected_base = w.model_base(4000, 1, 1)
    w.rand_seq = [9000, 10000]
    r = w.run(seller=-1, entity=FAC_MARK + 1, flag=1, winner=None)
    case("★ 設施支同样掷 2 次且**没有同名数**那一项",
         r["limits"][0], w.model_limit(FAC_MARK + 1, 1, w.expected_base, 1, 999999, 9000, 10000))

    # ══════════════════ [F] 落槌与结算 ══════════════════
    print("\n[F] 落槌：返回值、归属、到期日、付款方向（真跑 pay_money 0x41d2c6）")

    def scene(owner, winner, deed=0, modal_price=None, entity=LAND_MARK + 1,
              seller=2, price=1000, p0=100000, p1=100000, p2=100000):
        """3 人局、卖家 = 玩家下标 2（座位 2 会被删）⇒ 可投座位 = 槽 0/1。"""
        w.clear()
        w.num_players = 3
        w.price_index = 1
        w.player(0, who=1, char=1, cash=p0)
        w.player(1, who=1, char=2, cash=p1)
        w.player(2, who=1, char=3, cash=p2)
        w.deed_term = deed
        w.expected_base = w.model_base(price, 0, 1)
        if entity < FAC_MARK:
            w.land(entity - LAND_MARK, owner=owner, level=0, price=price, name=b"A",
                   flast=SENTINEL)
        else:
            w.fac(entity - FAC_MARK, owner=owner, level=0, price=price, name=b"F",
                  flast=SENTINEL)
        w.rand_seq = [1000, 2000]
        return w, w.run(seller=seller, entity=entity, flag=1, winner=winner,
                        modal_price=modal_price)

    w, r = scene(owner=1, winner=None)
    case("★ 窗口返回 -1（流標）⇒ 本函数返回 0", r["ret"], 0)
    case("  流標不动归属", r["land_owner"], 1)
    case("  流標不动现金", r["cash"][:3], [100000, 100000, 100000])
    case("  流標不进公库", r["pool"], 0)
    case("  流標不写到期日", r["land_flast"], SENTINEL)

    w, r = scene(owner=1, winner=0)          # 槽 0 = 玩家下标 0 = owner(1 基 1)
    case("★ 得标（窗口返回槽号 0）⇒ 返回 1", r["ret"], 1)
    case("★★ 得标者 == 原地主（1 基相等）⇒ **归属不写**，值仍是 1", r["land_owner"], 1)
    case("★★ 得标者 == 原地主 ⇒ **照样付款**：得标者现金减少",
         r["cash"][0], 100000 - w.expected_base)
    case("★★ 收款方 = arg0（发起拍卖的那位，**不是地主、也不是公库**）：存款增加",
         r["bank"][2], w.expected_base)
    case("  ★ 收款进**存款 +0x20**（pay_money flags=0），不进现金", r["cash"][2], 100000)
    case("  收款方月度收入 +0x60 += 成交价", r["received"][2], w.expected_base)
    case("  付款方月度支出 +0x5c += 成交价", r["paid"][0], w.expected_base)
    case("  公库不动（收款方是玩家）", r["pool"], 0)

    w, r = scene(owner=2, winner=0)          # 地主 = 玩家下标 1；得标 = 玩家下标 0
    case("★ 得标者 ≠ 原地主 ⇒ 归属改写为得标者（1 基 = 槽号 + 1）", r["land_owner"], 1)
    case("  地主（玩家 1）现金不动", r["cash"][1], 100000)
    case("  得标者付现金给 arg0 = 玩家 2（进其存款）",
         [r["cash"][:2], r["bank"][2]], [[99000, 100000], 1000])

    w, r = scene(owner=0, winner=0, seller=-1)     # 无主地 + 无卖家 ⇒ 公库
    case("★ arg0 == -1（破产清算/新聞 7 那条路）⇒ 归属给得标者", r["land_owner"], 1)
    case("★ 成交款进公库 0x499080", r["pool"], 1000)
    case("  得标者付出现金，其余人不变", r["cash"][:3], [99000, 100000, 100000])
    case("  ★ 无主地 + [0x499110]==0（無限期）⇒ **不写**到期日", r["land_flast"], SENTINEL)

    w, r = scene(owner=0, winner=0, seller=-1, deed=5)    # 一个月
    tv = w.emu.readu32(DEED_TABLE + 5 * 4)
    case("★ 无主地 + 地契年限 ≠ 0 ⇒ 写到期日（真跑 0x4521cb）",
         r["land_flast"], World.date_add(0x0100, tv))

    w, r = scene(owner=0, winner=0, seller=-1, deed=3)    # 六个月
    tv = w.emu.readu32(DEED_TABLE + 3 * 4)
    case("  六个月档：0x100+0x600 = 0x700（不触发月回卷）",
         r["land_flast"], World.date_add(0x0100, tv))
    case("  六个月档真值 = 0x700", r["land_flast"], 0x0700)
    w, r = scene(owner=0, winner=0, seller=-1, deed=2)    # 一年 = 0x10000
    tv = w.emu.readu32(DEED_TABLE + 2 * 4)
    case("★ 一年档 0x10000：加法是**32 位**（不掩 16 位），且高字节为 0 ⇒ 不触发回卷",
         r["land_flast"], 0x0100 + 0x10000)
    w.clear()
    w.num_players = 3
    w.price_index = 1
    w.land(1, owner=0, level=0, price=1000, flast=SENTINEL)
    for p in range(3):
        w.player(p, who=1, char=p + 1, cash=100000)
    w.expected_base = 1000
    w.deed_term = 3
    r = w.run(seller=2, entity=LAND_MARK + 1, flag=1, winner=0)
    case("  无主地 + 年限 3 ⇒ 写到期日（与得标者是谁无关）", r["land_flast"] != SENTINEL, True)

    w, r = scene(owner=1, winner=0, seller=2, deed=5)
    case("★ 有主地即使年限 ≠ 0 也**不写**到期日（旧主保留）", r["land_flast"], SENTINEL)

    w, r = scene(owner=0, winner=0, seller=2, modal_price=7777)
    case("★ 付款金额 = 落槌瞬间的 [0x48c488]（现价），**不是**底价 1000",
         r["cash"][0], 100000 - 7777)
    case("  同上，收款方存款收到 7777", r["bank"][2], 7777)

    w, r = scene(owner=3, winner=1, seller=-1, entity=FAC_MARK + 1, modal_price=1500)
    case("★ 設施支：归属改写为得标者（1 基 2）", r["fac_owner"], 2)
    case("★ 設施无卖家（arg0=-1）⇒ 成交款进公库", r["pool"], 1500)
    w, r = scene(owner=0, winner=1, seller=0, entity=FAC_MARK + 1, deed=4)
    tv = w.emu.readu32(DEED_TABLE + 4 * 4)
    case("★ 設施的到期日写在 +0x34（地块是 +0x30）", r["fac_flast"],
         World.date_add(0x0100, tv))
    case("  設施得标者 = 玩家 1（现金少 1000），付给 arg0 = 玩家 0（存款 +1000）",
         [r["cash"][:2], r["bank"][0]], [[100000, 99000], 1000])

    w, r = scene(owner=0, winner=1, seller=-1, modal_price=1000)
    case("★ 窗口选中真人座位 ⇒ 照样归属 + 付款",
         (r["ret"], r["land_owner"], r["cash"][:3]), (1, 2, [100000, 99000, 100000]))

    # ══════════════════ [G] 竞价循环：AI 加价档位 ══════════════════
    print("\n[G] AI 加价档位 `loc_0043b0ef`（= 复刻 auctionAiRaise）：五档 + 压价段 + 放弃")
    for price, limit, cash, want, desc in [
        (1000, 20000, 999999, 5, "现价+10000 ≤ 心理价 ⇒ +10000"),
        (1000, 11000, 999999, 5, "★ 边界：1000+10000 == 11000 ⇒ +10000"),
        (1000, 10999, 999999, 4, "★ 边界：只差 1 ⇒ 退到 +5000"),
        (1000, 6000, 999999, 4, "1000+5000 == 6000 ⇒ +5000"),
        (1000, 5999, 999999, 3, "⇒ +1000"),
        (1000, 1999, 999999, 2, "1000+1000 > 1999 ⇒ +500"),
        (1000, 1499, 999999, 1, "⇒ +100"),
        (1000, 1100, 999999, 1, "★ 边界：1000+100 == 1100 ⇒ +100"),
        (1000, 1099, 999999, 0, "现价+100 > 心理价 ⇒ 不加（PASS）"),
        (1000, 999, 999999, 0, "心理价 < 现价 ⇒ PASS"),
        (1000, 20000, 1000, 5, "★ 边界：现金 == 现价 ⇒ **还能投**（判据是 `现价 > 现金`）"),
        (1000, 20000, 999, 6, "★★ 现金 < 现价 ⇒ **6（放棄）**，复刻在这里给 0（PASS）"),
        (1000, 20000, 1001, 5, "★ 边界：现金 1001 > 1000 ⇒ 正常挑档"),
    ]:
        w.clear()
        got, _ = w.ai_raise(price=price, limit=limit, cash=cash, top=-1, top_cash=0)
        case(f"{desc}（现价 {price}/心理价 {limit}/现金 {cash}）", got, want)

    print("  — 压价段（`add edi,0x1f4` = 最高出价者现金 + 500 那道线）")
    for price, step_limit, cash, top, top_cash, want, desc in [
        (1000, 20000, 999999, 1, 1000, 2, "线 1500：room = 500 ⇒ 压到 +500"),
        (1000, 20000, 999999, 1, 11000, 5, "★ 线 11500 > 现价+10000 ⇒ 不进，保留 +10000"),
        (1000, 20000, 999999, 1, 4000, 4, "★ room = 4500-1000 = 3500 ∈ (1000,5000] ⇒ +5000"),
        (1000, 20000, 999999, 1, 1500, 3, "★ room = 1000 ⇒ **+1000**（复刻写成 +5000）"),
        (1000, 20000, 999999, 1, 1600, 4, "★ room = 1100 ⇒ +5000（room>1000 都进这一档）"),
        (1000, 20000, 999999, 1, 1000, 2, "★ room = 500 ⇒ **+500**（复刻写成 +1000）"),
        (1000, 20000, 999999, 1, 1100, 3, "★ room = 600 ⇒ +1000"),
        (1000, 20000, 999999, 1, 600, 1, "★ room = 100 ⇒ **+100**（复刻写成 +500）"),
        (1000, 20000, 999999, 1, 700, 2, "★ room = 200 ⇒ +500"),
        (1000, 20000, 999999, 1, 500, 1, "room = 0 ⇒ +100"),
        (1000, 20000, 999999, 1, 7000, 5, "★ room = 6500 > 5000 ⇒ **保留原档**（+10000）"),
    ]:
        w.clear()
        got, _ = w.ai_raise(price=price, limit=step_limit, cash=cash,
                            top=top, top_cash=top_cash)
        case(f"{desc}（最高出价者现金 {top_cash}）", got, want)

    w.clear()
    got, _ = w.ai_raise(price=1000, limit=20000, cash=999999, top=-1, top_cash=0)
    case("★ top == -1（还没人出价）⇒ 不压档", got, 5)
    w.clear()
    got, _ = w.ai_raise(price=1000, limit=20000, cash=999999, top=1, top_cash=999999)
    case("  top 存在但线很高 ⇒ 不压档", got, 5)

    print("  — ★★ 座位数 == 1 的强制最小加价（`[0x48c4b1]`，复刻**没有**这一条）")
    for n, want in [(1, 1), (2, 5)]:
        w.clear()
        got, _ = w.ai_raise(price=1000, limit=20000, cash=999999, top=-1,
                            top_cash=0, nsingles=n)
        case(f"  可出价座位数 = {n} ⇒ 档位 {want}", got, want)
    w.clear()
    got, _ = w.ai_raise(price=1000, limit=1099, cash=999999, top=-1, top_cash=0, nsingles=1)
    case("  可出价座位数 = 1 但本来就不加价（PASS）⇒ 仍是 0", got, 0)
    w.clear()
    got, _ = w.ai_raise(price=1000, limit=20000, cash=999, top=-1, top_cash=0, nsingles=1)
    case("★★ 可出价座位数 = 1 时**连「出不起」的 6 也被压成 1**（原版就如此）", got, 1)
    w.clear()
    got, _ = w.ai_raise(price=1000, limit=20000, cash=999, top=-1, top_cash=0, nsingles=2)
    case("  对照：座位数 = 2 时出不起仍是 6", got, 6)
    w.clear()
    got, _ = w.ai_raise(price=1000, limit=20000, cash=999999, top=-1, top_cash=0, nsingles=0)
    case("  对照：[0x48c4b1] == 0（无座位）⇒ 不压", got, 5)

    # ══════════════════ [H] 终局判定 ══════════════════
    print("\n[H] 终局判定 `loc_0043b295`（= 复刻 auctionFinished）：流標 / 成交 / 换下一家")
    HIT_NAMES = {FIN_BAIL: "流標", FIN_SETTLE: "成交候选", FIN_NEXT: "换下一家",
                 FIN_PAY: "成交"}

    def fin(seats, top):
        w.clear()
        w.num_players = 4
        w.seats = [{"player": p, "status": st} for p, st in seats]
        w.seat_top = top
        a, err = w.probe(FINISH_ENTRY, {FIN_BAIL, FIN_SETTLE, FIN_NEXT})
        if a == FIN_SETTLE:
            b, _ = w.probe(FIN_SETTLE, {FIN_NEXT, FIN_PAY})
            a = b
        return a, err

    for seats, top, want, desc in [
        ([(0, 0)] * 4, -1, FIN_BAIL, "★ 0 个非空座位 ⇒ 流標（esi==0）"),
        ([(1, 1), (2, 1), (0, 0), (0, 0)], -1, FIN_BAIL, "★ 全员已过/被阻 ⇒ 流標（esi==edi）"),
        ([(1, 1), (2, 1), (3, 1), (0, 0)], 0, FIN_BAIL, "★ 三个非空全非 0 ⇒ 流標"),
        ([(1, 0), (2, 1), (3, 1), (0, 0)], 1, FIN_PAY,
         "★ esi-edi == 1（只剩一个可出价）+ 有人出过价 ⇒ 成交"),
        ([(1, 0), (2, 1), (3, 0), (0, 0)], 1, FIN_NEXT, "★ esi-edi == 2 ⇒ 换下一家"),
        ([(1, 1), (0, 0), (0, 0), (0, 0)], 0, FIN_BAIL,
         "★ esi == 1 且那格是非 0 状态 ⇒ esi==edi 先命中 ⇒ 流標（esi==1 单判是冗余的）"),
        ([(1, 1), (2, 1), (0, 0), (0, 0)], 0, FIN_BAIL, "两个非空、两个都非 0 ⇒ esi==edi ⇒ 流標"),
        ([(1, 0), (0, 0), (0, 0), (0, 0)], 1, FIN_PAY,
         "★ esi == 1 且它是可出价状态、且已有人出过价 ⇒ 成交"),
        ([(1, 0), (0, 0), (0, 0), (0, 0)], -1, FIN_NEXT,
         "★ esi == 1 且它是可出价状态、但没人出过价 ⇒ 换下一家（不是流標）"),
    ]:
        got, err = fin(seats, top)
        case(f"{desc}", (HIT_NAMES.get(got, got), err is None), (HIT_NAMES[want], True))

    w.clear()
    w.num_players = 4
    w.seats = [{"player": 1, "status": 0}, {"player": 2, "status": 1}]
    w.seat_top = -1
    got, _ = w.probe(FINISH_ENTRY, {FIN_BAIL, FIN_SETTLE, FIN_NEXT})
    case("★ 有人可出价（esi=2/edi=1）⇒ 先落到成交检查点", got, FIN_SETTLE)
    got2, _ = w.probe(FIN_SETTLE, {FIN_NEXT, FIN_PAY})
    case("  ★ 但 top == -1（没人出过价）⇒ 退回换下一家", got2, FIN_NEXT)
    w.seat_top = 0
    got3, _ = w.probe(FIN_SETTLE, {FIN_NEXT, FIN_PAY})
    case("  同上但有人出过价（top=0）⇒ 成交", got3, FIN_PAY)

    # ══════════════════ [I] 覆盖旁证 ══════════════════
    print("\n[I] 分支旁证（UC_HOOK_CODE）：关键写点/调用点确实执行")
    def trace_scene(owner, seller, winner, modal_price):
        w.clear()
        w.num_players = 3
        w.price_index = 1
        w.land(1, owner=owner, level=0, price=1000, flast=SENTINEL)
        for p in range(3):
            w.player(p, who=1, char=p + 1, cash=100000)
        w.expected_base = 1000
        w.deed_term = 0
        w.trace = True
        r = w.run(seller=seller, entity=LAND_MARK + 1, flag=1, winner=winner,
                  modal_price=modal_price)
        w.trace = False
        return w, r

    w, r = trace_scene(owner=2, seller=-1, winner=0, modal_price=1500)
    case("★ 走到归属写入 0x43c813", 0x43C813 in r["hits"], True)
    case("★ 走到付款调用点 0x43c855（真跑 0x41d2c6）", 0x43C855 in r["hits"], True)
    case("★ 走到窗口过程调用点 0x43c6e1", 0x43C6E1 in r["hits"], True)
    case("★ 走到起拍价取整 0x43be74（__round_toward_zero）", 0x43BE74 in r["hits"], True)
    case("★ 得标者 ≠ 地主（1 基 3）⇒ 0x43c80c 写 dl 生效，归属 = 1", r["land_owner"], 1)
    case("★ 得标者付 1500 现金给公库（arg0=-1）", (r["cash"][0], r["pool"]), (98500, 1500))
    case("  月度支出记在得标者 +0x5c = 1500", r["paid"][0], 1500)

    w, r = trace_scene(owner=1, seller=-1, winner=0, modal_price=1500)
    case("★★ 得标者 == 地主 ⇒ **跳过**归属写入（0x43c813 不执行）",
         0x43C813 in r["hits"], False)
    case("  但付款照走：0x43c855 仍执行", 0x43C855 in r["hits"], True)
    case("  得标者照样付给公库", (r["cash"][0], r["pool"]), (98500, 1500))

    n_ok = sum(1 for x in RESULTS if x)
    print(f"\n{'=' * 68}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
