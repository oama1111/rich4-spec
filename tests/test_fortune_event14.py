#!/usr/bin/env python3
"""
通道 2 差分测试 · 命運事件 14「行人闖越馬路罰款 %d 元」`0x0044cd99`（389 B）

跳表成员：`fortune_call_table[14]` @ `0x475ef0`（37 项），由 `fortune_events 0x44db81`
两趟驱动 —— 第 1 趟 `push 0`（画字），第 2 趟 `push 1`（生效）：

```asm
0044dc44  push 0 / call dword [eax*4 + 0x475ef0]    ; @source pass 0（显示）
0044dd5b  push 1 / call dword [eax*4 + 0x475ef0]    ; @source pass 1（生效）
```

`[esp+0x94]`＝唯一实参（`0x44cda3 cmp dword [esp+0x94],0 / jne 0x44ce35`）；
作用对象恒为**当前玩家** `[0x49910c]`，无其它参数。

## 控制流（全 389 B 读完；行首即 VA）

```
0x44cd99(pass):                                     ; 帧：push×4 + sub esp,0x80 ⇒ arg0=[esp+0x94]
    if (pass == 0) {                                ; @source 0x44cda3
        amount = 3000 × [0x4990e8]                  ; 0x44cdb1 移位链 d*4−d=3d →*8=24d +d=25d
                                                    ;   →*8=200d →<<4=3200d −200d = 3000d
        [0x48c5b4] = amount                         ; 0x44cdcd ★ 金额全局（**只有这一趟写**）
        sprintf(buf, "#0199行人闖越馬路罰款%d元" @0x465a94, amount)      ; 0x44cddd
        drawText([0x48c5e0]+0x18, buf, 0x18, 0x14a, 0)                  ; 0x44fabc
        drawPortrait([0x48c5e0]+0x18, disp[player]+0x24, 0x186, 0x158)  ; 0x4562a5
        return                                      ; 0x44ce30 jmp 尾声 —— 一个钱都不动
    }

    ; ── pass 1：★ **不重算金额**，下面读的 [0x48c5b4] 是 pass 0 留下的跨趟全局 ──
    mult = 0x44b896(0, 1)                           ; 0x44ce39 ★ 加持档位（罰金口吻，读 +0x46）
    [0x48c5b0] = mult                               ; 0x44ce41
    update_player_info_window(0, 0, 3)              ; 0x44ce4c 表现层刷新
    if (mult == 1) {                                ; 0x44ce5a ★ 「免付罰金」
        show([0x48c5b8], 1500)                      ; 0x44ce69（串由 0x44b896 写）
        player_say_a(cur, [0x48c5b4])               ; 0x44ce7e
        return                                      ; ★ 不付款、不理赔
    }
    if (mult == 2) {                                ; 0x44ce8b ★ 「罰金加倍」
        show([0x48c5b8], 1500)                      ; 0x44ce9a
        [0x48c5b4] *= 2                             ; 0x44cea2/0x44ceaa（add esi,esi）
    }
    pay_money(cur, -1, [0x48c5b4], 0)               ; 0x44cec2 ＝ 0x41d2c6，现金优先→存款→破产
    if (player[cur].who_plays(+0x15) == 0) return   ; 0x44ced1 ★ 已出局/破产 ⇒ 跳过尾部
    if (byte [0x46caf8] != 0) return                ; 0x44cede ★ 终局码非 0 ⇒ 跳过尾部
    player_say_b(cur, [0x48c5b4])                   ; 0x44cef9 表现层
    insurance(cur, [0x48c5b4], 1)                   ; 0x44cf11 ＝ 0x44ba63 ★ 意外理赔
    return                                          ; 0x44cf19 jmp 尾声（共享 0x44d800）

0x44ba63(player, amount, unused):                   ; ★ 第三个实参原函数不读
    if (player.insurance_days(+0x3e) == 0) return   ; 0x44ba74
    idx = 1
    while (idx <= [0x498e90] && 企業[idx].industry(+0x1a) != 4) idx++   ; 0x44ba88 第一家保險公司
    sprintf(buf, "保險期間…得到理賠金%d元" @0x4658fa, amount)          ; 0x44baaf
    show(buf, 2000)                                 ; 0x44bac1
    pay_money(0x64 + idx, player, amount, 1)        ; 0x44bad8 ＝ 公司出钱、玩家**收现金**
```

★ 三条最容易写错的：
1. 付款金额是 `3000 × 物價指數`，**不含**加持倍率；`0x44b896` 的档位是
   `0 = ×1 / 1 = ×0（免付）/ 2 = ×2（加倍）`，只在 pass 1 使用。
2. `pass 0` 印的数是 **3000×p（未加倍）**，实际可能付 6000 —— 原版就是这样。
3. 理赔金额是 **`[0x48c5b4]`（请求额）**，不是被级联截断后的实付额；而「真缺口 ⇒ 破产」
   那条路会先把 `who_plays` 清 0，于是尾部整段被跳过（`0x44ced1`）——
   所以「截断」与「理赔」在原版里**不会同时发生**。
4. ★★ **pass 1 不重算金额**：`0x44ce35` 直接跳过 `0x44cdb1..0x44cdcd` 那段移位链，
   `[0x48c5b4]` 只在 pass 0 被写。⇒ 两趟之间是一个**跨趟全局契约**
   （调度器 `0x44db81` 恒先 pass 0 后 pass 1，故实机永远成立）。
   本测试台 `emu.call()` 每次 `reset()` 会还原 DGROUP，所以 `_setup` 把
   `[0x48c5b4]` 预置成 pass 0 会写的值（`run_pair()` 就是真跑两趟再搬过去）；
   [B2] 组专门用「预置成别的值 / 0 / 哨兵」来钉这条契约。

## 打桩清单

| VA | 原用途 | 桩 | 为什么合法 |
|---|---|---|---|
| `0x456f2d` | CRT `rand()` | 从数据槽读 + **计数** | 确定性；计数是真值（本链上只有 `0x44b896` 会摇） |
| `0x457110` | CRT `sprintf` | 记录 `(dst, fmt, arg1)`、不格式化 | 真身走 `es:` 段前缀扫串，仿真里踩未映射段（工具边界） |
| `0x440cac` | 字幕（串, 毫秒） | 记录 `(串, 毫秒)` | 表现层 |
| `0x44f567` | `player_say` 金額階梯 A | 记录 `(玩家, 金额)`，返回哨兵 `0x2222` | 表现层；真身还会再摇一次 `rand()&1` |
| `0x44f42d` | `player_say` 金額階梯 B | 记录 `(玩家, 金额)`，返回哨兵 `0x3333` | 同上 |
| `0x41d476` | `update_player_info_window(x,y,mode)` | 记录 `(x,y,mode)` | 表现层（`news.md` §237 的命名） |
| `0x44fabc` | `drawText_colorcode` | 记录 5 个实参 | 表现层（`render-api.md` §135） |
| `0x4562a5` | 贴头像 | 记录 4 个实参 | 表现层（`ui-screens.md` §1016） |
| `0x41d433` | 付款后刷新面板 | **不打桩**，用 `[0x46cad8]=2` 早退（`0x41d438 jg 0x41d474`） | 与 `test_money_move.py` 同一手法 |
| `0x40cd87` | **破产/退场** | **不打桩**：真跑到它内部的 MKF 读取点 `0x450471` 报错为止 | 与 `test_money_move.py` 同一手法；它在此之前已把 `who_plays` 清 0（`0x40ce13`） |

**真跑**（本测试的判据主体）：`0x41d2c6`（付款级联）、`0x44b896`（加持档位）。

跑法：cd rich4-spec && .venv/bin/python tests/test_fortune_event14.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

FORTUNE14 = 0x44CD99
PRNG = 0x456F2D
SPRINTF = 0x457110
SHOW = 0x440CAC
SAY_A = 0x44F567
SAY_B = 0x44F42D
WINDOW = 0x41D476
DRAWTEXT = 0x44FABC
PORTRAIT = 0x4562A5
MKF_FAULT_EIP = 0x450471

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
CASH, BANK, WHO, INS_DAYS = 0x1C, 0x20, 0x15, 0x3E
GOD, FORTUNE, LUCK = 0x3F, 0x46, 0x48
MONTHLY_PAID, MONTHLY_RECEIVED = 0x5C, 0x60
NODE_ID = 0x0C

CUR = 0x49910C
NUM_PLAYERS = 0x499114
PI = 0x4990E8
POOL = 0x499080
GAME_MODE = 0x46CAD8
GAMEOVER = 0x46CAF8
AMOUNT_G = 0x48C5B4
MULT_G = 0x48C5B0
TOAST = 0x48C5B8
SURFACE_G = 0x48C5E0
DISP_TABLE = 0x498EB0

COMPANY_PTR, COMPANY_COUNT = 0x498E7C, 0x498E90
START_POS_PTR = 0x498E80
C_STRIDE, C_FUNDS, C_MIRROR, C_IND = 0x34, 0x28, 0x2C, 0x1A
INDUSTRY_INSURANCE = 4

# ── 桩的代码位置与记录区 ──
STUB_RAND = STUB_BASE + 0x000
STUB_SPRINTF = STUB_BASE + 0x080
STUB_SHOW = STUB_BASE + 0x100
STUB_SAY_A = STUB_BASE + 0x180
STUB_SAY_B = STUB_BASE + 0x200
STUB_WINDOW = STUB_BASE + 0x280
STUB_DRAW = STUB_BASE + 0x300
STUB_PORTRAIT = STUB_BASE + 0x380

RAND_VAL = SCRATCH_BASE + 0x0800
RAND_N = SCRATCH_BASE + 0x0700          # ★ 计数器与数据槽分开（verification.md 工具边界）
FMT_LOG = SCRATCH_BASE + 0x2000         # N / dst / fmt / arg1 各占 0x40
SHOW_LOG = SCRATCH_BASE + 0x2200
SAYA_LOG = SCRATCH_BASE + 0x2400
SAYB_LOG = SCRATCH_BASE + 0x2600
WIN_LOG = SCRATCH_BASE + 0x2800
DRAW_LOG = SCRATCH_BASE + 0x2A00
PORT_LOG = SCRATCH_BASE + 0x2C00

COMPANY_TAB = SCRATCH_BASE + 0x6000
START_TAB = SCRATCH_BASE + 0x7000
DISP_PTRS = SCRATCH_BASE + 0x5000
DISP_REC = SCRATCH_BASE + 0x5400

FMT_EVENT = 0x465A94      # "#0199行人闖越馬路罰款%d元"
FMT_INSURANCE = 0x4658FA  # "保險期間\n\n得到理賠金\n\n%d元"
FMT_BLESS_B2 = 0x4658AE   # B 路：%s作祟\n\n罰金加倍！
FMT_BLESS_B1 = 0x4658C1   # B 路：%s保佑\n\n免付罰金！
FMT_REWARD_D = 0x465888   # A 路（獎金口吻）加倍 —— 本事件**不该**用
FMT_REWARD_V = 0x46589B   # A 路 作廢
FMT_MISFORT_D = 0x4658D4  # C 路（劫难口吻）倒霉加倍 —— 本事件**不该**用
FMT_MISFORT_V = 0x4658E7  # C 路 逃過此劫

SENT = 0x5A5A5A5A
SURFACE = 0x00700000      # 假窗口指针（只作实参，不解引用）
CASH0, BANK0 = 1_000_000, 1_000_000
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    g = got if isinstance(got, (int, float)) else str(got)
    x = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'OK ' if ok else 'NG '} {desc:<62} 实际 {g!s:<24} 期望 {x!s}")
    return ok


def p32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def recorder(data_va: int, retval: int, nargs: int) -> bytes:
    """记录 nargs 个实参到 data_va，返回 retval。

    ★ 只用 eax/ecx（cdecl 易失），**不碰 ebx/esi/edi/ebp**
      （verification.md：桩里拿 ebx 当临时寄存器会悄悄破坏调用方活跃值）。
    """
    code = b"\xA1" + p32(data_va)                       # mov eax,[N]
    for i in range(nargs):
        code += b"\x8B\x4C\x24" + bytes([4 + 4 * i])     # mov ecx,[esp+4+4i]
        code += b"\x89\x0C\x85" + p32(data_va + 0x40 + 0x40 * i)  # [A_i+eax*4] = ecx
    code += b"\x40"                                      # inc eax
    code += b"\xA3" + p32(data_va)                       # mov [N],eax
    code += b"\xB8" + p32(retval)                        # mov eax,retval
    code += b"\xC3"
    return code


def sprintf_stub() -> bytes:
    """`sprintf(dst, fmt, …)`：cdecl ⇒ [esp+4]=dst、[esp+8]=fmt、[esp+0xc]=第一个 %d/%s 实参。"""
    code = b"\xA1" + p32(FMT_LOG)                        # mov eax,[N]
    code += b"\x8B\x4C\x24\x04"                          # mov ecx,[esp+4]  dst
    code += b"\xC6\x01\x00"                              # mov byte [ecx],0
    code += b"\x89\x0C\x85" + p32(FMT_LOG + 0x40)        # [DST+eax*4] = ecx
    code += b"\x8B\x54\x24\x08"                          # mov edx,[esp+8]  fmt
    code += b"\x89\x14\x85" + p32(FMT_LOG + 0x80)        # [FMT+eax*4] = edx
    code += b"\x8B\x4C\x24\x0C"                          # mov ecx,[esp+0xc] arg1
    code += b"\x89\x0C\x85" + p32(FMT_LOG + 0xC0)        # [ARG+eax*4] = ecx
    code += b"\x40" + b"\xA3" + p32(FMT_LOG)             # inc / 回写计数器
    code += b"\x31\xC0\xC3"                              # xor eax,eax / ret
    return code


def rand_stub() -> bytes:
    return (b"\xFF\x05" + p32(RAND_N)                    # inc dword [RAND_N]
            + b"\xA1" + p32(RAND_VAL)                    # mov eax,[RAND_VAL]
            + b"\xC3")


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, rand_stub())
        self.emu.patch(SPRINTF, sprintf_stub())
        self.emu.patch(SHOW, recorder(SHOW_LOG, 0x1111, 2))
        self.emu.patch(SAY_A, recorder(SAYA_LOG, 0x2222, 2))
        self.emu.patch(SAY_B, recorder(SAYB_LOG, 0x3333, 2))
        self.emu.patch(WINDOW, recorder(WIN_LOG, 0x4444, 3))
        self.emu.patch(DRAWTEXT, recorder(DRAW_LOG, 0x5555, 5))
        self.emu.patch(PORTRAIT, recorder(PORT_LOG, 0x6666, 4))
        self.clear()

    # ── 场景 ──────────────────────────────────────────────
    def clear(self):
        self.player = 0
        self.pi = 1
        self.fortune = 0
        self.luck = 0
        self.god = 0
        self.insured = 0
        self.who = 1
        self.gameover = 0
        self.rand = 0
        self.amount_seed = None      # None ⇒ 用 `3000×pi`（＝ pass 0 会留下的全局值）
        self.cash = [CASH0] * 4
        self.bank = [BANK0] * 4
        self.paid = [0] * 4
        self.recv = [0] * 4
        self.companies = []          # [(industry, funds, mirror), …]，下标从 1 起
        self.eax = None
        self.fault = None
        return self

    def company(self, idx, industry, funds=0, mirror=0):
        while len(self.companies) < idx:
            self.companies.append((0, 0, 0))
        self.companies[idx - 1] = (industry, funds, mirror)
        return self

    def _setup(self, emu):
        emu.write32(GAME_MODE, 2)                    # 关掉 0x41d433 面板刷新
        emu.write32(CUR, self.player)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(PI, self.pi)
        emu.write32(POOL, 0)
        emu.write32(GAMEOVER, self.gameover)
        emu.write32(AMOUNT_G,
                    (3000 * self.pi if self.amount_seed is None else self.amount_seed) & 0xFFFFFFFF)
        emu.write32(MULT_G, SENT)
        emu.write8(TOAST, 0)
        emu.write32(SURFACE_G, SURFACE)
        emu.write32(COMPANY_PTR, COMPANY_TAB)
        emu.write32(COMPANY_COUNT, len(self.companies))
        emu.write32(START_POS_PTR, START_TAB)
        for p in range(8):
            emu.write32(DISP_TABLE + p * 0x34, DISP_REC)
        # 记录区 / 计数器 / 假表（暂存区跨调用保留 ⇒ 每个用例自己清）
        for base in (FMT_LOG, SHOW_LOG, SAYA_LOG, SAYB_LOG, WIN_LOG, DRAW_LOG, PORT_LOG):
            emu.scratch_write(base, bytes(0x200))
        emu.write32(RAND_N, 0)
        emu.write32(RAND_VAL, self.rand & 0xFFFFFFFF)
        emu.scratch_write(COMPANY_TAB, bytes(C_STRIDE * (len(self.companies) + 4)))
        for i, (ind, funds, mirror) in enumerate(self.companies, start=1):
            b = COMPANY_TAB + i * C_STRIDE
            emu.write8(b + C_IND, ind)
            emu.write32(b + C_FUNDS, funds)
            emu.write32(b + C_MIRROR, mirror)
        emu.scratch_write(START_TAB, bytes(0x28 * 8))
        for p in range(4):
            base = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write32(base + CASH, self.cash[p])
            emu.write32(base + BANK, self.bank[p])
            emu.write32(base + MONTHLY_PAID, self.paid[p])
            emu.write32(base + MONTHLY_RECEIVED, self.recv[p])
            emu.write8(base + WHO, self.who if p == self.player else 1)
            emu.write8(base + INS_DAYS, self.insured if p == self.player else 0)
            emu.write8(base + GOD, self.god)
            emu.write16(base + FORTUNE, self.fortune & 0xFFFF)
            emu.write16(base + LUCK, self.luck & 0xFFFF)
            emu.write16(base + NODE_ID, 0)

    def run(self, arg=1):
        r = self.emu.call(FORTUNE14, [arg], setup=self._setup)
        self.eax = r["eax"]
        self.fault = None
        return self

    def run_pair(self):
        """按原版的**两趟协议**跑：pass 0 写 `[0x48c5b4]` → pass 1 读它。

        ★★ 关键：pass 1 **不重算**金额（`0x44ce35` 直接跳过 `0x44cdb1` 的移位链），
        它用的是 pass 0 留在全局 `[0x48c5b4]` 里的值。而 `emu.call()` 每次都会
        `reset()` 还原 DGROUP，所以两趟之间必须把这个全局值重新注入
        —— 这正是原版真实存在的**跨趟全局契约**（见 [B2] 组的证伪用例）。
        """
        self.run(0)
        self.amount_seed = self.amount
        self.run(1)
        return self

    def run_expect_mkf_fault(self, arg=1):
        """破产分支跑不到底（MKF 读取）—— 捕获那个**已知的**故障点。"""
        self.fault = None
        try:
            r = self.emu.call(FORTUNE14, [arg], setup=self._setup)
        except RuntimeError as exc:
            if f"0x{MKF_FAULT_EIP:08x}" in str(exc):
                self.fault = MKF_FAULT_EIP
                self.eax = None
                return self
            raise
        self.eax = r["eax"]
        return self

    # ── 回读 ──────────────────────────────────────────────
    def pl(self, p):
        b = PLAYER_BASE + p * PLAYER_STRIDE
        return (self.emu.read32(b + CASH), self.emu.read32(b + BANK),
                self.emu.read32(b + MONTHLY_PAID), self.emu.read32(b + MONTHLY_RECEIVED),
                self.emu.read8(b + WHO))

    def comp(self, idx):
        b = COMPANY_TAB + idx * C_STRIDE
        return (self.emu.read32(b + C_FUNDS), self.emu.read32(b + C_MIRROR))

    @property
    def pool(self):
        return self.emu.read32(POOL)

    @property
    def amount(self):
        return self.emu.read32(AMOUNT_G)

    @property
    def mult(self):
        return self.emu.read32(MULT_G)

    @property
    def rand_n(self):
        return self.emu.read32(RAND_N)

    def _rec(self, base, call, n):
        """第 `call` 次调用的前 n 个实参（桩把 arg_k 存成 `base+0x40+0x40*k` 的数组）。"""
        return tuple(self.emu.read32(base + 0x40 + 0x40 * k + 4 * call) for k in range(n))

    def _n(self, base):
        return self.emu.read32(base)

    def sprintf_calls(self):
        n = min(self._n(FMT_LOG), 16)
        return [(self.emu.read32(FMT_LOG + 0x40 + 4 * i),
                 self.emu.read32(FMT_LOG + 0x80 + 4 * i),
                 self.emu.read32(FMT_LOG + 0xC0 + 4 * i)) for i in range(n)]

    def fmts(self):
        return [c[1] for c in self.sprintf_calls()]


def main():
    print("差分测试 · 命運事件 14「行人闖越馬路罰款」0x44cd99（389 B）\n")
    w = World()

    # ── A. 两趟 pass ─────────────────────────────────────────────
    print("[A] 两趟 pass：0 = 只画字、1 = 生效（@source 0x44cda3 / 0x44dc44 / 0x44dd5b）")
    w.clear()
    w.run(0)
    case("pass 0 不扣钱（现金/存款/公库/月支出/月收入全不动）",
         (w.pl(0), w.pool), ((CASH0, BANK0, 0, 0, 1), 0))
    case("pass 0 仍把金额写进 [0x48c5b4] = 3000×物價", w.amount, 3000)
    case("pass 0 不写加持档位 [0x48c5b0]（保持哨兵）", w.mult, SENT)
    sc = w.sprintf_calls()
    case("pass 0 sprintf 恰一次、fmt = 0x465a94", (len(sc), sc[0][1]), (1, FMT_EVENT))
    case("pass 0 的 %d 实参 = 3000", sc[0][2], 3000)
    case("pass 0 drawText 恰一次", w._n(DRAW_LOG), 1)
    case("pass 0 drawText 画的就是 sprintf 的目标缓冲（同一块局部缓冲）",
         w._rec(DRAW_LOG, 0, 5)[1], sc[0][0])
    case("pass 0 drawText 参数 = (SURFACE+0x18, buf, 0x18, 0x14a, 0)",
         (w._rec(DRAW_LOG, 0, 5)[0], w._rec(DRAW_LOG, 0, 5)[2],
          w._rec(DRAW_LOG, 0, 5)[3], w._rec(DRAW_LOG, 0, 5)[4]),
         (SURFACE + 0x18, 0x18, 0x14A, 0))
    case("pass 0 头像参数 = (SURFACE+0x18, disp[0]+0x24, 0x186, 0x158)",
         w._rec(PORT_LOG, 0, 4), (SURFACE + 0x18, DISP_REC + 0x24, 0x186, 0x158))
    case("pass 0 不调 update_player_info_window", w._n(WIN_LOG), 0)
    case("pass 0 不调 player_say / 字幕 / 加持",
         (w._n(SAYA_LOG), w._n(SAYB_LOG), w._n(SHOW_LOG), w.rand_n), (0, 0, 0, 0))

    w.clear()
    w.run(1)
    case("pass 1 扣现金 3000；公库 +3000；月支出 +3000",
         (w.pl(0), w.pool), ((CASH0 - 3000, BANK0, 3000, 0, 1), 3000))
    case("pass 1 **不**重算金额，直接沿用 pass 0 留下的 [0x48c5b4] = 3000", w.amount, 3000)
    case("pass 1 [0x48c5b0] = 加持档位（fortune=0 ⇒ 0）", w.mult, 0)
    case("pass 1 update_player_info_window(0,0,3)", w._rec(WIN_LOG, 0, 3), (0, 0, 3))
    case("pass 1 不画字、不贴头像（那是 pass 0 的事）",
         (w._n(DRAW_LOG), w._n(PORT_LOG)), (0, 0))
    case("pass 1 走 player_say B（付款后那一支），不走 A",
         (w._n(SAYB_LOG), w._n(SAYA_LOG)), (1, 0))
    case("pass 1 走 say B 的实参 = (当前玩家, 金额)", w._rec(SAYB_LOG, 0, 2), (0, 3000))
    case("pass 1 不显示加持字幕（档位 0 无提示）", w._n(SHOW_LOG), 0)
    case("pass 1 没有保险期 ⇒ 不料理赔", (w.comp(1), w.pl(0)[0]), ((0, 0), CASH0 - 3000))

    # ── B. 金额公式 ──────────────────────────────────────────────
    print("\n[B] 金额 = 3000 × 物價指數（移位链 @0x44cdb1；无其它系数）")
    print("    ★ 两趟协议：pass 0 算并写 [0x48c5b4]，pass 1 直接读它（不重算）")
    for pi in (0, 1, 2, 3, 5, 7, 100):
        w.clear(); w.pi = pi; w.run_pair()
        case(f"pi={pi}（两趟）⇒ [0x48c5b4] = {3000 * pi}、现金 −{3000 * pi}",
             (w.amount, w.pl(0)[0], w.pool), (3000 * pi, CASH0 - 3000 * pi, 3000 * pi))
    w.clear(); w.pi = 2; w.run(0)
    case("pass 0 的 %d 也乘物價（pi=2 ⇒ 6000）", w.sprintf_calls()[0][2], 6000)
    w.clear(); w.pi = 4; w.god = 7; w.run_pair()
    case("★ 金额不乘神明/任何其它系数（god=7、pi=4 ⇒ 恰 12000）",
         (w.amount, w.pl(0)[0]), (12000, CASH0 - 12000))
    w.clear(); w.pi = 1; w.fortune = -1; w.run(0)
    case("★ pass 0 印的是**未加倍**的 3000（fortune<0 时 pass 1 实付 6000）",
         (w.amount, w.sprintf_calls()[0][2]), (3000, 3000))

    print("\n[B2] ★★ pass 1 **不重算**金额：它读的是 pass 0 留在 [0x48c5b4] 的全局值")
    w.clear(); w.pi = 9; w.amount_seed = 4321; w.run(1)
    case("★ 预置 [0x48c5b4] = 4321（pi=9 也不影响）⇒ 就付 4321、公库 4321",
         (w.amount, w.pl(0)[0], w.pool), (4321, CASH0 - 4321, 4321))
    w.clear(); w.pi = 1; w.amount_seed = 0; w.run(1)
    case("★ 预置 0 ⇒ 一分不付（连 pass 0 的 3000 都没有）", (w.pl(0)[0], w.pool), (CASH0, 0))
    w.clear(); w.pi = 1; w.amount_seed = SENT; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run_expect_mkf_fault(1)
    case("★★ 预置成哨兵（＝pass 1 单独跑、没有 pass 0）⇒ 巨款把玩家抽干并破产（MKF 故障）",
         (w.fault, w.pl(0)[0], w.pl(0)[4]), (MKF_FAULT_EIP, 0, 0))

    # ── C. 加持档位：0x44b896(0,1)「罰金口吻」读 +0x46 ───────────
    print("\n[C] 加持档位 = 0x44b896(0,1)（罰金口吻，读 +0x46；真跑）")
    print("    档位 0 ⇒×1；1 ⇒×0（免付）；2 ⇒×2（加倍）")
    print("    分档：>100 → 1；50<x≤100 → rand()&1；0≤x≤50 → 0；x<0 → 2")
    for val, want_mult, want_cash, want_rand in [
        (0, 0, CASH0 - 3000, 0),
        (1, 0, CASH0 - 3000, 0),
        (50, 0, CASH0 - 3000, 0),
        (101, 1, CASH0, 0),
        (32767, 1, CASH0, 0),
        (-1, 2, CASH0 - 6000, 0),
        (-32768, 2, CASH0 - 6000, 0),
    ]:
        w.clear(); w.fortune = val; w.rand = 7; w.run(1)
        case(f"fortune={val} ⇒ 档位 {want_mult}、现金 {want_cash}、摇 {want_rand} 次",
             (w.mult, w.pl(0)[0], w.rand_n), (want_mult, want_cash, want_rand))
    for val, rnd, want_mult, want_cash in [
        (51, 0, 0, CASH0 - 3000), (51, 1, 1, CASH0),
        (75, 0, 0, CASH0 - 3000), (75, 1, 1, CASH0),
        (100, 0, 0, CASH0 - 3000), (100, 1, 1, CASH0),
        (100, 2, 0, CASH0 - 3000), (100, 3, 1, CASH0),
    ]:
        w.clear(); w.fortune = val; w.rand = rnd; w.run(1)
        case(f"fortune={val}、rand={rnd} ⇒ 档位 {want_mult}、现金 {want_cash}",
             (w.mult, w.pl(0)[0], w.rand_n), (want_mult, want_cash, 1))

    w.clear(); w.fortune = 100; w.rand = 1; w.run(1)
    case("★ 免付：一分不付、公库不动、月支出不动",
         (w.pl(0), w.pool), ((CASH0, BANK0, 0, 0, 1), 0))
    case("★ 免付：字幕串由 0x44b896 写（fmt = 0x4658c1「%s保佑 免付罰金」）",
         w.fmts(), [FMT_BLESS_B1])
    case("★ 免付：字幕走 show([0x48c5b8], 1500)",
         w._rec(SHOW_LOG, 0, 2), (0x48C5B8, 1500))
    case("★ 免付：走 say A(cur, amount)，不走 say B",
         (w._n(SAYA_LOG), w._rec(SAYA_LOG, 0, 2), w._n(SAYB_LOG)), (1, (0, 3000), 0))
    case("★ 免付：不理赔（无 0x4658fa；月收入也不动）",
         (FMT_INSURANCE in w.fmts(), w.pl(0)[3]), (False, 0))

    w.clear(); w.fortune = -1; w.run(1)
    case("★ 加倍：字幕 fmt = 0x4658ae「%s作祟 罰金加倍」＝**罰金口吻 B 路**",
         w.fmts(), [FMT_BLESS_B2])
    case("★★ 不是獎金口吻 A 路（0x465888/0x46589b），也不是劫难口吻 C 路（0x4658d4/0x4658e7）",
         [f in (FMT_REWARD_D, FMT_REWARD_V, FMT_MISFORT_D, FMT_MISFORT_V) for f in w.fmts()],
         [False])
    case("★ 加倍：先 show 再 ×2 再付款、再 say B",
         (w._n(SHOW_LOG), w.amount, w.pl(0)[0], w._n(SAYB_LOG)),
         (1, 6000, CASH0 - 6000, 1))

    w.clear(); w.fortune = -1; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 加倍 + 有保险 ⇒ sprintf 次序 = [加持字幕, 理赔字幕]（支付在两者之间）",
         w.fmts(), [FMT_BLESS_B2, FMT_INSURANCE])

    w.clear(); w.fortune = 60; w.rand = 1; w.insured = 5
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 免付时即使有保险也不理赔（fmt 表里没有 0x4658fa）",
         (w.fmts(), w.pl(0)[0], w.comp(1)), ([FMT_BLESS_B1], CASH0, (100000, 200000)))

    # ── D. 金钱级联（真跑 0x41d2c6）──────────────────────────────
    print("\n[D] pay_money(cur, -1, amount, 0)：现金优先 → 存款 → 破产")
    w.clear(); w.cash[0] = 500; w.bank[0] = 4000; w.run(1)
    case("现金 500 付 3000 → 现金 0、存款扣 2500、月支出记**全额** 3000",
         (w.pl(0), w.pool), ((0, 1500, 3000, 0, 1), 3000))
    w.clear(); w.cash[0] = 3000; w.bank[0] = 777; w.run(1)
    case("★ 边界 现金恰好 = 3000 ⇒ 现金 0、存款不动、**不破产**",
         (w.pl(0), w.pool), ((0, 777, 3000, 0, 1), 3000))
    w.clear(); w.cash[0] = 2999; w.bank[0] = 1; w.run(1)
    case("★ 边界 现金 2999 + 存款 1 ⇒ 恰好付清、**不破产**、月支出 = 3000",
         (w.pl(0), w.pool), ((0, 0, 3000, 0, 1), 3000))
    w.clear(); w.cash[0] = 4000; w.bank[0] = 0; w.run(1)
    case("现金充足时存款一个子儿都不动", w.pl(0), (1000, 0, 3000, 0, 1))
    w.clear(); w.cash[0] = 1000; w.bank[0] = 5000; w.run(1)
    case("★ 现金不够但存款够 ⇒ 实付全额、月支出全额（**不破产**）",
         (w.pl(0), w.pool), ((0, 3000, 3000, 0, 1), 3000))
    w.clear(); w.cash[0] = 0; w.bank[0] = 0; w.who = 0; w.run(1)
    case("两口袋全 0、who=0 ⇒ 实付 0、月支出 0、公库 0、who 保持 0（破产处理早退）",
         (w.pl(0), w.pool), ((0, 0, 0, 0, 0), 0))
    w.clear(); w.pi = 1; w.run(1)
    case("★ 公库只进罚款：付款方=玩家、收款方 = −1 ⇒ 没有任何玩家 +0x60",
         (w.pool, w.pl(0)[3], w.pl(1)[3]), (3000, 0, 0))

    print("\n[D2] 破产边界：现金**不会**变负；破产处理真跑到 MKF 读取点（同 test_money_move）")
    w.clear(); w.cash[0] = 500; w.bank[0] = 300; w.run_expect_mkf_fault(1)
    case("★ 总额 800 付 3000 ⇒ 现金流被抽干到 0、存款 0（都不为负）",
         (w.pl(0)[0], w.pl(0)[1]), (0, 0))
    case("★ 破产处理在此前把 who_plays 清 0（@source 0x40ce13）", w.pl(0)[4], 0)
    case("★ 故障点固定 = mkf_read_resource 的 0x450471（越界即说明分支变了）",
         w.fault, MKF_FAULT_EIP)
    case("★ 故障发生在 `+0x5c += 实付` 与入公库**之前** ⇒ 两者此刻仍是 0",
         (w.pl(0)[2], w.pool), (0, 0))
    w.clear(); w.cash[0] = 0; w.bank[0] = 3000; w.run(1)
    case("★ 边界 总额恰好 = 3000 ⇒ **不**破产（`jge`），who 保持 1",
         (w.pl(0), w.pool), ((0, 0, 3000, 0, 1), 3000))

    # ── E. 保险尾部（真跑 0x44ba63）─────────────────────────────
    print("\n[E] 保险尾部 0x44ba63(cur, amount, 1)：+0x3e 非 0 才赔、第一家行業別 4 出钱")
    w.clear(); w.insured = 0
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("无保险期（+0x3e = 0）⇒ 只付罚款、公司不动",
         (w.pl(0), w.comp(1)), ((CASH0 - 3000, BANK0, 3000, 0, 1), (100000, 200000)))
    case("  没有 0x4658fa 理赔字幕", FMT_INSURANCE in w.fmts(), False)

    w.clear(); w.insured = 1
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 有保险 ⇒ 玩家现金回到原值（罚款 3000 被赔回）", w.pl(0)[0], CASH0)
    case("★ 理赔进**现金**（flags=1），存款不动", w.pl(0)[1], BANK0)
    case("★ 月收入 +0x60 独立累计 3000（与 +0x5c 月支出 3000 分开）",
         (w.pl(0)[2], w.pl(0)[3]), (3000, 3000))
    case("★ 保险公司 +0x28/+0x2c 各 −3000（两个字段同进同出）",
         w.comp(1), (97000, 197000))
    case("★ 大理赔款走公司（不是公库）：公库仍只有 3000 罚款", w.pool, 3000)
    case("★ 理赔字幕 fmt = 0x4658fa、show(串, 2000ms)",
         (w.fmts(), w._rec(SHOW_LOG, 0, 2)[1]),
         ([FMT_INSURANCE], 2000))
    case("★ 理赔字幕的串 = 那次 sprintf 的目标缓冲",
         w._rec(SHOW_LOG, 0, 2)[0], w.sprintf_calls()[0][0])

    w.clear(); w.insured = 0x80
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 保险期高位（+0x3e = 0x80「今日到期」）只判 `!= 0` ⇒ 照样赔",
         w.pl(0)[0], CASH0)

    print("\n[E2] 保险公司选取 = 第一家 +0x1a == 4；其它公司/公库不动")
    w.clear(); w.insured = 3
    w.company(1, 1, 5000, 6000)        # 航空：不是保險公司
    w.company(2, INDUSTRY_INSURANCE, 100000, 200000)
    w.company(3, INDUSTRY_INSURANCE, 70000, 80000)
    w.run(1)
    case("★ 扫到**第一家**行業別 4（下标 2）就停：下标 1 不动、下标 3 不赔",
         (w.comp(1), w.comp(2), w.comp(3)),
         ((5000, 6000), (97000, 197000), (70000, 80000)))
    w.clear(); w.insured = 3
    w.company(1, 1, 5000, 6000)
    w.company(2, 7, 40000, 40000)
    w.run(1)
    case("★★ 地图上没有保險公司 ⇒ 原版按 `家数+1` 越界记账（Q-INS-2）",
         (w.comp(1), w.comp(2), w.comp(3)),
         ((5000, 6000), (40000, 40000), (-3000, -3000)))
    case("  越界那一笔**不进**公库、也不给任何玩家",
         (w.pool, w.pl(1)[0], w.pl(2)[0]), (3000, CASH0, CASH0))

    w.clear(); w.fortune = -1; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 加倍后理赔 = **加倍后的金额** 6000（保险拿到的是 [0x48c5b4]）",
         (w.pl(0)[0], w.pl(0)[3], w.comp(1)),
         (CASH0, 6000, (94000, 194000)))

    w.clear(); w.pi = 0; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ 金额 0 时**仍**走理赔尾部（原版不判 amount > 0）",
         (w.pl(0), w.comp(1), w.fmts()),
         ((CASH0, BANK0, 0, 0, 1), (100000, 200000), [FMT_INSURANCE]))

    # ── F. 尾部两道闸门 ─────────────────────────────────────────
    print("\n[F] 尾部两道闸：who_plays(+0x15) == 0 / [0x46caf8] != 0（付款不受它们影响）")
    w.clear(); w.who = 0; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ who_plays = 0 ⇒ **照扣罚款**（本函数没有 purchaseBlockedBy/神灵闸）",
         (w.pl(0)[0], w.pool), (CASH0 - 3000, 3000))
    case("★ who_plays = 0 ⇒ 跳过 say B 与理赔",
         (w._n(SAYB_LOG), w.comp(1), w.pl(0)[3]), (0, (100000, 200000), 0))

    w.clear(); w.who = 0; w.fortune = -1; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ who_plays = 0 但 fortune<0 ⇒ 加持字幕**仍**显示、仍加倍、仍扣款、仍不理赔（闸在最后）",
         (w.fmts(), w.pl(0)[0], w._n(SAYB_LOG), w.comp(1)),
         ([FMT_BLESS_B2], CASH0 - 6000, 0, (100000, 200000)))

    w.clear(); w.gameover = 1; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★ [0x46caf8] != 0 ⇒ 仍扣款，但跳过尾部（say B + 理赔）",
         (w.pl(0)[0], w.pool, w._n(SAYB_LOG), w.comp(1)),
         (CASH0 - 3000, 3000, 0, (100000, 200000)))
    w.clear(); w.gameover = 3; w.run(1)
    case("★ [0x46caf8] = 3 与 1 同效（只判 `!= 0`）", w.pl(0)[0], CASH0 - 3000)

    w.clear(); w.who = 0x10; w.insured = 4
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("★★ 原版闸门是**整字节** != 0 ⇒ who_plays=0x10（低 2 位为 0）照样理赔",
         (w.pl(0)[0], w.comp(1)), (CASH0, (97000, 197000)))

    # ── G. 返回值 ───────────────────────────────────────────────
    print("\n[G] 返回值：本函数**没有**自己的返回语义（调用方 0x44dc44/0x44dd5b 不读 eax）")
    w.clear(); w.fortune = 101; w.run(1)
    case("★ 免付支的 eax = 台词桩 A 的哨兵 0x2222（尾部没有自己的返回值）", w.eax, 0x2222)
    w.clear(); w.run(1)
    case("★ 付款支的 eax = 残留的 `player*0x68`（玩家 0 ⇒ 0）", w.eax, 0)
    w.clear(); w.player = 1; w.run(1)
    case("★ 玩家 1 ⇒ 残留 eax = 0x68（同一条 `imul eax,esi,0x68`）", w.eax, 0x68)
    w.clear(); w.player = 1; w.who = 0; w.run(1)
    case("  who=0 跳过尾部的支也返回残留 0x68", w.eax, 0x68)

    # ── H. 作用对象只有当前玩家 ─────────────────────────────────
    print("\n[H] 只作用于**当前玩家**（[0x49910c]）；其它玩家一个字段都不动")
    w.clear(); w.player = 1; w.insured = 2
    w.company(1, INDUSTRY_INSURANCE, 100000, 200000)
    w.run(1)
    case("玩家 1 付款+理赔（净额回到原值），玩家 0/2/3 不动",
         (w.pl(0), w.pl(1), w.pl(2), w.pl(3)),
         ((CASH0, BANK0, 0, 0, 1), (CASH0, BANK0, 3000, 3000, 1),
          (CASH0, BANK0, 0, 0, 1), (CASH0, BANK0, 0, 0, 1)))
    case("  公库只进 3000（罚款），公司只出 3000", (w.pool, w.comp(1)), (3000, (97000, 197000)))

    w.clear(); w.player = 2; w.run(0)
    case("pass 0 谁的钱都不动",
         (w.pl(0), w.pl(2), w.pool),
         ((CASH0, BANK0, 0, 0, 1), (CASH0, BANK0, 0, 0, 1), 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
