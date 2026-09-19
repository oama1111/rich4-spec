#!/usr/bin/env python3
"""
通道 2 差分测试 · 保險理賠 `0x0044BA63`（135 B） + 本月首富評選 `0x00437DFE`（54 B）

原版 exe 的那两份机器码在 Unicorn 里**整支驱动**，返回值/内存副作用当预言机。

================================================================
[A] 保險理賠 — VA 0x0044BA63，`0x44ba63..0x44bae9`（含 ret，共 0x87 = 135 B）
================================================================

调用约定（六处调用点**同构**，逐字节核对）：

```
0040d420  push ecx / 0040d425  call 0x44ba63   ; 住店（通用）
0041a82c  push edi / 0041a82d  call 0x44ba63   ; 旅館
0043d748  push ebp / 0043d749  call 0x44ba63   ; 坐牢
0043edf7  push ebp / 0043edf8  call 0x44ba63   ; 住院
0044c217  push eax / 0044c218  call 0x44ba63   ; 命運「冒貸」
0044cf10  push edi / 0044cf11  call 0x44ba63   ; 命運「行人闖越馬路罰款」（事件 14）
```
→ 签名 `(玩家, 損失, 旗标)`（cdecl）。`gen/rel32-calls.json` 的 `"0x0044ba63"`
列表恰为上列 6 个站点（本文件 `[S]` 段机械复核）。

语义（135 B 全程读完，`0x44ba63..0x44bae9`）：

```
0x44ba63(玩家 p, 損失 loss, 旗标 flag) {           ; flag 全函数**从不读**
    if (u8[p*0x68 + 0x3e] == 0) return;             ; 0x44ba74 保險期闸门（byte）
    for (ebx = 1; ebx <= dword[0x498e90]; ebx++)    ; 0x44ba88 企業家数上界
        if (u8[ dword[0x498e7c] + ebx*0x34 + 0x1a ] == 4) break   ; 行業別 4 = 保險
    sprintf(buf, "保險期間\\n\\n得到理賠金\\n\\n%d元", loss);  ; 0x44baaf
    draw_money_box(buf, 2000);                      ; 0x44bac1（表现层）
    transfer_money(ebx + 0x64, p, loss, 1);         ; 0x44bad8
}
```
`0x41d2c6(from, to, amount, flags)`：`from > 0x64` ⇒ 企業表
（`[0x498e7c] + (from-0x64)*0x34`）的 `+0x28`/`+0x2c` **各减 amount**（不判破产、可负）；
`to < 0x64` ⇒ 玩家：`flags & 1` → **现金** `+0x1c += amount`，否则存款 `+0x20`；
两边都 `+0x60 += amount`（本月意外之財）。付款方（玩家时）`+0x5c += 实付额`。

★ 三处不是常识的原版事实（本测试逐条钉死）：
  1. `flag`（第三参）**完全未被读**（`0x44bac9` 硬编码 `push 1`）；六个调用点传 0/1 都不影响。
  2. 玩家记录字段 `+0x3e` 是 **byte ≠ 0** 判据：`0x80`（保險期归零挂的旗）**照样理赔**。
  3. **没有保險公司的地图上原版仍然赔给玩家**（Q-INS-2）：循环落空后 `ebx = 家数+1`，
     `0x41d2e6` 写到企業表**界外**第 `家数+1` 格的 `+0x28`/`+0x2c`，而收款方那一段
     （`0x41d387`）与付款方无关，照样 `玩家现金 += loss`、`+0x60 += loss`。界外写才是 bug，
     "不赔"不是原版行为。

打桩清单（[A]）
---------------
| 桩 | VA | 处置 | 合法性 |
|---|---|---|---|
| `sprintf` | `0x457110` | 打 `ret` + `UC_HOOK_CODE` **记录 (buf, fmt, loss)** 并在 Python 里只复刻 `%d` | 原版 CRT 叶子，内部 `0x45b392` 是 `pop es` ⇒ Unicorn 无段寄存器写能力，必报 `UC_ERR_READ_UNMAPPED`（同 `rich4-spec/docs/verification.md`「工具限制 #1」的 `push es` 族）。它不是被测规则；断言改用**记录的实参 + 复刻文本** |
| `draw_money_box` | `0x440CAC` | 打 `ret` + `UC_HOOK_CODE` 记录 `(text, amount)` | 表现层：`0x440d4e mov eax,[0x48a0e0]` 取 DDraw 对象指针，镜像里该全局 = **0** ⇒ 紧跟的 `mov edx,[eax]` 读 0 号地址必崩。跟金钱/记账无关 |
| 企業表 | `[0x498e7c]` | 指向暂存区 `0x601000`（原版是堆分配） | 只换**存放位置**，不换布局；原版该全局初值 = 0（未开局） |
| 企業家数上界 | `[0x498e90]` | setup 每例必写 | §verification.md 限制 #5「少写上界类全局会静默走另一支」 |

真跑的：`0x44ba63` 本体、企業表扫描（`0x34` 步长 / `+0x1a` 行業別）、
`0x41d2c6` 全套金钱转移（企業付款支 + 玩家收款支 + `+0x60` 累计）、
以及闸门上游的**每日递减内联块** `0x41cc48..0x41cc6c`（`eval_block` 真跑，见 A3b ——
它证明 `0x80 → 0x7f`，而不是被清成 0）。
打桩清单外的断言全是**内存副作用**（现金/存款/`+0x60`/`+0x5c`/企業 `+0x28`/`+0x2c`/界外格）。

================================================================
[B] 本月首富評選 — VA 0x00437DFE，`0x437dfe..0x437e33`（含 ret，共 0x36 = 54 B）
================================================================

```
0x437dfe() {
    n = u8[0x48c420]; best = 0; bestAt = 0;          ; 0x437e01..0x437e05 三个 xor
    for (i = 0; i < n; i++) {                        ; 0x437e09 上界 = u8[0x48c420]
        w = calculate_player_wealth(u8[0x48c418 + i]);   ; 0x437e14 候选表（byte[]）
        if (best < w) { best = w; bestAt = i; }          ; 0x437e23 cmp esi,eax / jge 跳过
    }
    return bestAt;                                   ; 0x437e2e mov eax,edi —— **表下标**
}
```

★ 三条要点：
  1. 返回值是 **候选表下标**，不是玩家 id（`0x437e29 mov edi,ebx`，`ebx` 是循环变量）。
     调用点 `0x43824a` 把它落进 `[0x48c430]`，`0x438536` 一带再 `[eax + 0x48c418]`
     映射回玩家 id —— 與 `[0x48c42f]`（悲情人物，`0x437d1a`）同一套。
  2. 平手取**先出现的**（严格 `>`）。
  3. `best`/`bestAt` 初值都是 **0** ⇒ 候选全为负数、或候选表为空时返回 **0**（= 第 0 个候选）。

调用者（`python3 tools/disasm.py callers 0x437dfe` + `gen/rel32-calls.json`）：
**唯一** `0x0043824a`（紧接 `0x438240 call 0x437d1a` 之后），是月结颁奖屏状态机的一支；
`0x439caa` 按 `u8[p*0x68+0x15] != 0`（在场）**升序**铺 `[0x48c418]/[0x48c420]`。

打桩清单（[B]）：**无代码桩**。`0x4239b9 calculate_player_wealth` 是**纯聚合**（只读全局、
无写点），因此**真跑**（与 `tests/test_wealth.py` 同一套表布局）；只是把本用例不关心的
股票数量表（`0x4971a0 + p*0x60 + s*8`）、股價表（`0x496994 + s*0x24`）、
地產表（`[0x498e84]`,`[0x498e98]`）、商業用地表（`[0x498e88]`,`[0x498e8c]`）
在 setup 里显式清成 0/0 家 —— 这些是**数据**而非代码，且每个方向性用例
（银行/贷款/股票/截断）都会把对应表打开来证明它真被读。

跑法：cd rich4-spec && .venv/bin/python tests/test_insurance_richest.py
故意破坏（可证伪性自查，见文件末 [M] 段）：
    RICH4_MUTATE=A .venv/bin/python tests/test_insurance_richest.py
    RICH4_MUTATE=B .venv/bin/python tests/test_insurance_richest.py
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_ESP  # noqa: E402

# ── [A] 保險理賠 ────────────────────────────────────────────────
INS = 0x44BA63
SPRINTF = 0x457110
UI_BOX = 0x440CAC
TRANSFER = 0x41D2C6
INS_SIZE = 0x44BAE9 - INS + 1          # 135

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_F1C, P_F20, P_F3E, P_F5C, P_F60 = 0x1C, 0x20, 0x3E, 0x5C, 0x60

COMP_PTR = 0x498E7C                    # dword：企業表首址
COMP_N = 0x498E90                      # dword：企業家数（上界，1 基）
COM_STRIDE, COM_KIND, COM_F28, COM_F2C = 0x34, 0x1A, 0x28, 0x2C

FMT_VA = 0x4658FA                      # "保險期間\n\n得到理賠金\n\n%d元"
FMT_BYTES = bytes.fromhex(
    "ab4fc049 b4c1b6a1 0a0a b16fa8ec b27abddf aaf7 0a0a 2564 a4b8"
)
FMT_TEXT = "保險期間\n\n得到理賠金\n\n%d元"
BOX_AMOUNT = 2000                      # 0x44bab7 `push 0x7d0`

COM_TABLE = SCRATCH_BASE + 0x1000      # 企業表落暂存区（原版为堆分配）
COM_SLOTS = 10                         # 够放 count+1 的界外格

# ── [B] 本月首富 ────────────────────────────────────────────────
RICHEST = 0x437DFE
WEALTH = 0x4239B9
RICH_SIZE = 0x437E33 - RICHEST + 1     # 54

CAND_LIST, CAND_N = 0x48C418, 0x48C420
LAND_PTR, LAND_N = 0x498E84, 0x498E98
COM_PTR, COM_N = 0x498E88, 0x498E8C
STOCK_AMT, STOCK_AMT_STRIDE = 0x4971A0, 0x60
STOCK_PRICE, STOCK_PRICE_STRIDE = 0x496994, 0x24

SCRATCH_LAND = SCRATCH_BASE + 0x4000
SCRATCH_COM = SCRATCH_BASE + 0x4800

REL32_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gen", "rel32-calls.json")

# ★ 故意破坏钩子：只在 RICH4_MUTATE 取到对应键时把**被测输入**改坏，
#   期望值一律不变 ⇒ 相关断言必须变红。见文件末 [M]。
MUTATE = os.environ.get("RICH4_MUTATE", "").strip().upper()

RESULTS = []


def m(key, normal, broken):
    return broken if MUTATE == key else normal


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'XX '} {desc:<60} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def bulk(ok):
    RESULTS.append(bool(ok))


def rel32(emu, at):
    """读 `at` 处一条 E8/E9 的绝对目标（32 位环绕）。"""
    return (at + 5 + struct.unpack("<i", emu.read(at + 1, 4))[0]) & 0xFFFFFFFF


def i32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= (1 << 31) else v


_TICK_EMU = None


def emu_tick(player_base, days, player=0):
    """驱动原版**内联**的保險期每日递减块 `0x41cc48..0x41cc6c`（`ebx` = 玩家号）。

    它不是函数入口（`0x41cc48` 只是大函数的中间一小段），故走 `eval_block`。
    `[0x498e90]` 那一类上界全局与它无关；`+0x3e` 是玩家记录里的 byte。
    """
    global _TICK_EMU
    if _TICK_EMU is None:
        _TICK_EMU = Emu()

    def setup(e):
        e.write8(player_base + player * PLAYER_STRIDE + P_F3E, days & 0xFF)

    _TICK_EMU.eval_block(0x41CC48, 0x41CC6C, {"ebx": player}, setup=setup)
    return _TICK_EMU.read8(player_base + player * PLAYER_STRIDE + P_F3E)


# ============================================================
#  [S] 静态自检：把「规格里写下的地址/字段/常量」回 exe 逐字节复核
#      （防止人工转录错一格 —— verification.md「通道 1」的教训）
# ============================================================
def static_checks(emu):
    print("=" * 78)
    print("[S] 静态自检：关键指令字节 / rel32 目标 / 函数尺寸 / 调用点表")
    print("=" * 78)

    case("[A] 入口 push ebx,esi,ebp + sub esp,0x80",
         emu.read(INS, 6), bytes.fromhex("535655 81ec80"))
    case("[A] `imul eax,[esp+0x90],0x68`（参 1 = 玩家，步长 0x68）",
         emu.read(0x44BA6C, 8), bytes.fromhex("6b84249000000068"))
    case("[A] `cmp byte [eax+0x496ba6],0`（闸门 = 玩家 +0x3e，byte 判据）",
         emu.read(0x44BA74, 7), bytes.fromhex("80b8a66b490000"))
    case("[A] `mov edx,[0x498e7c]`（企業表首址全局）",
         emu.read(0x44BA82, 6), bytes.fromhex("8b157c8e4900"))
    case("[A] `cmp ebx,[0x498e90]`（企業家数 = 上界，dword）",
         emu.read(0x44BA88, 6), bytes.fromhex("3b1d908e4900"))
    case("[A] `imul eax,ebx,0x34`（企業步长 0x34）",
         emu.read(0x44BA90, 4), bytes.fromhex("6bc33480"))
    case("[A] `cmp byte [edx+eax+0x1a],4`（行業別 @+0x1a == 4 保險）",
         emu.read(0x44BA93, 5), bytes.fromhex("807c021a04"))
    case("[A] `push 0x7d0`（消息框金额常量 2000）",
         emu.read(0x44BAB7, 5), bytes.fromhex("68d0070000"))
    case("[A] `push 1`（硬编码 flags = 1 = 進現金）",
         emu.read(0x44BAC9, 2), bytes.fromhex("6a01"))
    case("[A] `mov ebp,[esp+0x98]`（= 参数 1，參數 3 全函数无读点）",
         emu.read(0x44BACC, 7), bytes.fromhex("8bac2498000000"))
    case("[A] `add ebx,0x64`（企業编码 = 表下标 + 0x64）",
         emu.read(0x44BAD4, 3), bytes.fromhex("83c364"))
    case("[A] 尾 `add esp,0x80 / pop ebp,esi,ebx / ret`（cdecl，非 ret N）",
         emu.read(0x44BAE0, 10), bytes.fromhex("81c480000000 5d5e5bc3"))
    case("[A] `0x44baaf call 0x457110`（sprintf）", rel32(emu, 0x44BAAF), SPRINTF)
    case("[A] `0x44bac1 call 0x440cac`（表現層消息框）", rel32(emu, 0x44BAC1), UI_BOX)
    case("[A] `0x44bad8 call 0x41d2c6`（金钱转移）", rel32(emu, 0x44BAD8), TRANSFER)
    case(f"[A] 函数尺寸 {INS_SIZE} B（0x44ba63..0x44bae9）", INS_SIZE, 135)

    case("[B] 入口 `push ebx,esi,edi / xor ebx,ebx / xor esi,esi`",
         emu.read(RICHEST, 6), bytes.fromhex("535657 31db31"))
    case("[B] `mov al,[0x48c420]`（候选人数全局，byte 读）",
         emu.read(0x437E09, 5), bytes.fromhex("a020c44800"))
    case("[B] `cmp ebx,eax`（人数上界比较）",
         emu.read(0x437E0E, 2), bytes.fromhex("39c3"))
    case("[B] `mov al,[ebx+0x48c418]`（候选表 = byte[]）",
         emu.read(0x437E14, 6), bytes.fromhex("8a8318c44800"))
    case("[B] `0x437e1b call 0x4239b9`（calculate_player_wealth）",
         rel32(emu, 0x437E1B), WEALTH)
    case("[B] `cmp esi,eax`（严格 >：平手不替换）",
         emu.read(0x437E23, 2), bytes.fromhex("39c6"))
    case("[B] `mov esi,eax`（刷新最高分）",
         emu.read(0x437E27, 2), bytes.fromhex("89c6"))
    case("[B] `mov edi,ebx`（bestAt = **循环下标**，不是玩家 id）",
         emu.read(0x437E29, 2), bytes.fromhex("89df"))
    case("[B] 尾 `mov eax,edi / pop edi,esi,ebx / ret`",
         emu.read(0x437E2E, 6), bytes.fromhex("89f8 5f5e5bc3"))
    case(f"[B] 函数尺寸 {RICH_SIZE} B（0x437dfe..0x437e33）", RICH_SIZE, 54)
    case("[B] 被调者 `0x4239c4 imul eax,ebx,0x68`（同一玩家步长）",
         emu.read(0x4239C4, 3), bytes.fromhex("6bc368"))

    # 调用点表（gen/rel32-calls.json，字节级全量 E8/E9 站点）
    with open(REL32_JSON, encoding="utf-8") as fh:
        calls = json.load(fh)
    case("[A] gen/rel32-calls.json 的 0x44ba63 站点数", len(calls["0x0044ba63"]), 6)
    case("[A] 六个站点（含命運事件 14 尾 0x0044cf11）",
         sorted(calls["0x0044ba63"]),
         ["0x0040d425", "0x0041a82d", "0x0043d749", "0x0043edf8",
          "0x0044c218", "0x0044cf11"])
    case("[B] gen/rel32-calls.json 的 0x437dfe 唯一调用点", calls["0x00437dfe"], ["0x0043824a"])
    case("[B] 同一月结屏里 0x437d1a（悲情人物）的调用点",
         calls["0x00437d1a"], ["0x00438240"])


# ============================================================
#  [A] 保險理賠 0x0044BA63
# ============================================================
class InsWorld:
    def __init__(self):
        self.emu = Emu()
        self.fmt_calls = []          # (buf, fmt_va, fmt_bytes, loss)
        self.ui_calls = []           # (text_ptr, amount)
        self.emu.mu.hook_add(UC_HOOK_CODE, self._on_fmt, begin=SPRINTF, end=SPRINTF)
        self.emu.mu.hook_add(UC_HOOK_CODE, self._on_ui, begin=UI_BOX, end=UI_BOX)
        self.emu.patch(SPRINTF, b"\xc3")     # 见打桩清单：CRT 叶子含 pop es
        self.emu.patch(UI_BOX, b"\xc3")      # 见打桩清单：DDraw 指针为 0

    def _on_fmt(self, mu, addr, size, user):
        esp = mu.reg_read(UC_X86_REG_ESP)
        buf, fmt, val = struct.unpack("<III", bytes(mu.mem_read(esp + 4, 12)))
        fmtb = bytes(mu.mem_read(fmt, 64)).split(b"\x00")[0]
        self.fmt_calls.append((buf, fmt, fmtb, val))
        if fmtb.count(b"%") != 1 or b"%d" not in fmtb:
            raise AssertionError(f"打桩清单只复刻 %d，遇到未预期格式串 {fmtb!r}")
        iv = struct.unpack("<i", struct.pack("<I", val))[0]
        mu.mem_write(buf, fmtb.replace(b"%d", str(iv).encode()) + b"\x00")

    def _on_ui(self, mu, addr, size, user):
        esp = mu.reg_read(UC_X86_REG_ESP)
        self.ui_calls.append(struct.unpack("<II", bytes(mu.mem_read(esp + 4, 8))))

    # ── 一例：写全局（reset 之后、压栈之前） ──
    def run(self, player=0, loss=6000, days=5, kinds=(7, 4, 7), flag=1,
            funds=100000, slot0_kind=None, cash=1000, bank=2000, recv=7, paid=77):
        self.fmt_calls.clear()
        self.ui_calls.clear()

        def setup(e):
            e.write(COMP_PTR, struct.pack("<I", COM_TABLE))
            e.write(COMP_N, struct.pack("<I", len(kinds)))    # ★ 上界全局必写
            e.write(COM_TABLE, b"\x00" * (COM_SLOTS * COM_STRIDE))   # ★ 暂存区每次清零
            for j in range(COM_SLOTS):                        # 每格先铺相同资金当哨兵
                b = COM_TABLE + j * COM_STRIDE
                e.write(b + COM_F28, struct.pack("<i", funds))
                e.write(b + COM_F2C, struct.pack("<i", funds))
            if slot0_kind is not None:
                e.write8(COM_TABLE + COM_KIND, slot0_kind)    # 下标 0 的行业別（应被忽略）
            for i, k in enumerate(kinds, start=1):            # 企業表 1 基
                e.write8(COM_TABLE + i * COM_STRIDE + COM_KIND, k)
            for q in range(4):                                # 四张记录铺同样的基线
                base = PLAYER_BASE + q * PLAYER_STRIDE
                e.write(base + P_F1C, struct.pack("<i", cash))
                e.write(base + P_F20, struct.pack("<i", bank))
                e.write(base + P_F60, struct.pack("<i", recv))
                e.write(base + P_F5C, struct.pack("<i", paid))
                e.write8(base + P_F3E, 0)                     # 只有「本人」有保險期
            p = PLAYER_BASE + player * PLAYER_STRIDE
            e.write8(p + P_F3E, days & 0xFF)

        r = self.emu.call(INS, [player, loss, flag], setup=setup)
        self.ret, self.esp_delta, self.insns = r["signed"], r["esp_delta"], r["insns"]
        base = PLAYER_BASE + player * PLAYER_STRIDE
        self.cash = self.emu.read32(base + P_F1C)
        self.bank = self.emu.read32(base + P_F20)
        self.recv = self.emu.read32(base + P_F60)
        self.paid = self.emu.read32(base + P_F5C)
        self.slot = [(self.emu.read32(COM_TABLE + j * COM_STRIDE + COM_F28),
                      self.emu.read32(COM_TABLE + j * COM_STRIDE + COM_F2C))
                     for j in range(COM_SLOTS)]
        if self.fmt_calls:
            self.text = self.emu.read(self.fmt_calls[0][0], 64).split(b"\x00")[0]
        else:
            self.text = b""
        return self

    def oob(self, count):
        """界外格 = 第 `count+1` 格（原版 `ebx = 家数+1`、`from = ebx + 0x64`）。"""
        return self.slot[count + 1]

    def effects(self):
        return (self.cash, self.bank, self.recv, self.paid,
                tuple(self.slot), len(self.fmt_calls), len(self.ui_calls))

    def player_cash(self, pid):
        return self.emu.read32(PLAYER_BASE + pid * PLAYER_STRIDE + P_F1C)


def section_a():
    print("=" * 78)
    print(f"[A] 保險理賠 0x0044BA63（{INS_SIZE} B）—— 闸门 / 哪家企業付 / 现金 vs 存款 / +0x60 / 界外")
    if MUTATE == "A":
        print("    ★★ RICH4_MUTATE=A：把主用例的保險期 5 天改成 0 天（故意破坏输入）")
    print("=" * 78)
    w = InsWorld()

    # ── A1 主用例：第 2 家（行业別 4）付、玩家進现金、+0x60 累计 ──
    print("A1 主用例 (玩家0, 损失6000, 保險期5天, 企業行业別 [7,4,7])")
    w.run(days=m("A", 5, 0))                       # ★ 破坏点 A
    case("现金 1000 → 7000（收款方進**现金** +0x1c）", w.cash, 7000)
    case("存款 2000 不变（flags=1 ⇒ 不進 +0x20）", w.bank, 2000)
    case("本月意外之財 +0x60 = 7 + 6000（在旧值上累加）", w.recv, 6007)
    case("本月意外損失 +0x5c 不变（付款方是企業，不是玩家）", w.paid, 77)
    case("企業 #1（行业別 7）不付", w.slot[1], (100000, 100000))
    case("企業 #2（行业別 4）付 +0x28", w.slot[2][0], 94000)
    case("企業 #2（行业別 4）付 +0x2c（两个镜像同进同出）", w.slot[2][1], 94000)
    case("企業 #3（行业別 7）不付", w.slot[3], (100000, 100000))
    case("企業 #0（下标 0）永不被扫到", w.slot[0], (100000, 100000))
    case("矩陣外一格（#4）未被写", w.slot[4], (100000, 100000))
    case("消息框被调 1 次", len(w.ui_calls), 1)
    case("消息框第 2 参 = 2000（0x44bab7 push 0x7d0）", w.ui_calls[0][1] if w.ui_calls else None,
         BOX_AMOUNT)
    case("sprintf 被调 1 次", len(w.fmt_calls), 1)
    case("sprintf 的格式串指针 = 0x4658fa", w.fmt_calls[0][1] if w.fmt_calls else None, FMT_VA)
    case("格式串字节（exe 原文）", w.fmt_calls[0][2] if w.fmt_calls else None, FMT_BYTES)
    case("格式串解码（Big5，独立于上面那条）",
         w.fmt_calls[0][2].decode("big5") if w.fmt_calls else None, FMT_TEXT)
    case("sprintf 的可变参 = 损失原样 6000", w.fmt_calls[0][3] if w.fmt_calls else None, 6000)
    case("sprintf 渲染出的文本（%d 已被 Python 桩代入）",
         w.text.decode("big5") if w.text else None, "保險期間\n\n得到理賠金\n\n6000元")
    case("esp_delta = 4（cdecl：一条 ret）", w.esp_delta, 4)
    case("确实走了赔付支（指令数 >> 早退支）", w.insns > 40, True)

    # ── A2 闸门：+0x3e == 0 → 一步不写 ──
    print("A2 闸门 (保險期 0 天)")
    w.run(days=0)
    case("现金不变", w.cash, 1000)
    case("存款不变", w.bank, 2000)
    case("+0x60 不变", w.recv, 7)
    case("+0x5c 不变", w.paid, 77)
    case("企業 #2 +0x28 不变", w.slot[2], (100000, 100000))
    case("消息框不被调", len(w.ui_calls), 0)
    case("sprintf 不被调", len(w.fmt_calls), 0)
    case("指令数 <= 40（= 早退支，不是走完再不改）", w.insns <= 40, True)

    # ── A3 闸门是 byte != 0：1 / 0x7f / 0x80 / 0xff 全赔 ──
    print("A3 闸门边界：byte ≠ 0（含 0x80 —— 保險期归零挂的旗，照样赔）")
    for days in (1, 0x7F, 0x80, 0xFF):
        w.run(days=days, kinds=(4,))
        case(f"保險期 0x{days:02x} → 现金 7000", w.cash, 7000)
        case(f"保險期 0x{days:02x} → +0x60 6007", w.recv, 6007)

    # ── A3b 闸门的上游：原版每日递减 `0x41cc48..0x41cc66`（整字节递减，无 0x80 特判） ──
    #     `0x80` 是「保險期归零」挂的旗；原版**不是**把它当"释放待处理"清 0，
    #     而是继续把它当计数器减到 0x7f —— 于是 +0x3e 在买过保險后**再也不为 0**
    #     （N..1 → 0x80 → 0x7f..1 → 0x80 …），闸门 `!= 0` 实际等于"买过保險就一直赔"。
    print("A3b 原版每日递减（内联块 0x41cc48→0x41cc6c，真跑）：0x80 → 0x7f")
    for before, after in ((5, 4), (1, 0x80), (0x80, 0x7F), (0x7F, 0x7E), (0, 0)):
        case(f"保險期 0x{before:02x} 递减一天 → 0x{after:02x}",
             emu_tick(0x496B68, before), after)
    case("买过保險后连走 4 天永不为 0（1→80→7f→7e→7d）",
         [emu_tick(0x496B68, d) for d in (1, 0x80, 0x7F, 0x7E)], [0x80, 0x7F, 0x7E, 0x7D])

    # ── A4 行业別边界 3 / 4 / 5（1 基，第一家命中即停） ──
    print("A4 行业別边界：只有 == 4 命中")
    for kind, paid_expected, oob_expected in ((3, 100000, 94000), (5, 100000, 94000),
                                              (4, 94000, 100000)):
        w.run(kinds=(kind,))
        case(f"行业別 {kind} ⇒ 企業 #1 资金 {paid_expected}", w.slot[1][0], paid_expected)
        case(f"行业別 {kind} ⇒ 界外第 2 格 {oob_expected}", w.oob(1)[0], oob_expected)

    # ── A5 第一家命中即停 ──
    print("A5 两家都是保險 ⇒ 第一家付")
    w.run(kinds=(4, 4))
    case("企業 #1 付 94000", w.slot[1][0], 94000)
    case("企業 #2 不动", w.slot[2][0], 100000)

    # ── A6 表下标 1 基：下标 0 不参与 ──
    print("A6 企業表 1 基：下标 0 即使行业別 4 也不参与")
    w.run(kinds=(7,), slot0_kind=4)
    case("下标 0 不动", w.slot[0][0], 100000)
    case("落空 → 界外第 2 格被扣 6000", w.oob(1)[0], 94000)
    case("玩家照样进现金 7000", w.cash, 7000)

    # ── A7 Q-INS-2：地图上没有保險公司 ──
    print("A7 Q-INS-2：无保險公司（[7,7,7]）—— 原版仍赔，写界外")
    w.run(kinds=(7, 7, 7))
    case("(1) 界外第 4 格 +0x28 被扣 6000", w.oob(3)[0], 94000)
    case("(2) 界外第 4 格 +0x2c 被扣 6000", w.oob(3)[1], 94000)
    case("(3) 表内三家企业全部不动", (w.slot[1], w.slot[2], w.slot[3]),
         ((100000, 100000), (100000, 100000), (100000, 100000)))
    case("(4) ★ 玩家仍被赔 6000（界外写 ≠ 不赔）", w.cash, 7000)
    case("(5) ★ +0x60 仍累计 6007", w.recv, 6007)
    case("(6) 消息框照画 1 次", len(w.ui_calls), 1)

    # ── A8 第三参（旗标）完全未被读 ──
    print("A8 参数 3（旗标）无读点：0 与 1 效果逐字节相同")
    w.run(kinds=(4,), flag=1)
    a = w.effects()
    w.run(kinds=(4,), flag=0)
    b = w.effects()
    case("现金/存款/+0x60/+0x5c/企業/桩计数 全等", a == b, True)
    case("两者都進现金（0x44bac9 硬编码 push 1）", b[0], 7000)

    # ── A9 金额原样传递、无符号/下限守卫 ──
    print("A9 金额语义：原样、无 loss<=0 守卫、无钳位")
    w.run(loss=1, kinds=(4,))
    case("损失 1 → 现金 1001", w.cash, 1001)
    case("损失 1 → +0x60 = 8", w.recv, 8)
    case("损失 1 → 企業 99999", w.slot[1][0], 99999)
    w.run(loss=0, kinds=(4,))
    case("损失 0 → 现金不变", w.cash, 1000)
    case("损失 0 → +0x60 不变", w.recv, 7)
    case("损失 0 → 企業不变", w.slot[1][0], 100000)
    case("★ 损失 0 仍走完整支（消息框照画）⇒ 原版无 loss<=0 守卫", len(w.ui_calls), 1)
    w.run(loss=-1000, kinds=(4,))
    case("损失 -1000 → 现金 1000-1000 = 0", w.cash, 0)
    case("损失 -1000 → +0x60 = 7-1000 = -993（有符号原样）", w.recv, -993)
    case("损失 -1000 → 企業反而 +1000 = 101000", w.slot[1][0], 101000)
    w.run(loss=6000, kinds=(4,), funds=50)
    case("企業资金 50 - 6000 = -5950（企業不判破产、不钳 0）", w.slot[1][0], -5950)
    case("玩家仍实收 6000", w.cash, 7000)

    # ── A10 玩家下标 ──
    print("A10 参数 1 = 玩家（*0x68 定位）")
    w.run(player=3, loss=100, kinds=(4,))
    case("玩家 3 现金 1000+100", w.player_cash(3), 1100)
    case("玩家 0 现金不变", w.player_cash(0), 1000)
    case("玩家 3 的 +0x60 = 107", w.recv, 107)


# ============================================================
#  [B] 本月首富評選 0x00437DFE
# ============================================================
class RichWorld:
    def __init__(self):
        self.emu = Emu()
        self.calls = []                  # 每次 0x4239b9 的实参（玩家号）
        self.emu.mu.hook_add(UC_HOOK_CODE, self._on_wealth, begin=WEALTH, end=WEALTH)

    def _on_wealth(self, mu, addr, size, user):
        esp = mu.reg_read(UC_X86_REG_ESP)
        self.calls.append(struct.unpack("<i", bytes(mu.mem_read(esp + 4, 4)))[0])

    def run(self, cands, players=None, stocks=()):
        self.calls.clear()
        players = players or {}

        def setup(e):
            # 候选表（生产时由 0x439caa 铺：在场玩家升序）
            # ⚠️ 只清 8 字节：0x48c418+8 == 0x48c420 就是**人数**那一格，多清会把上界抹成 0
            #    （§verification.md 限制 #5 的同一类坑：上界全局没写 ⇒ 循环静默不跑）
            e.write(CAND_LIST, b"\x00" * 8)
            e.write8(CAND_N, len(cands) & 0xFF)
            for i, pid in enumerate(cands):
                e.write8(CAND_LIST + i, pid & 0xFF)
            # 0x4239b9 的辅助表：全部显式关掉（数据，不是代码桩）
            e.write(LAND_PTR, struct.pack("<I", SCRATCH_LAND))
            e.write(COM_PTR, struct.pack("<I", SCRATCH_COM))
            e.write(LAND_N, struct.pack("<I", 0))
            e.write(COM_N, struct.pack("<I", 0))
            e.write(STOCK_AMT, b"\x00" * (4 * STOCK_AMT_STRIDE))
            e.write(STOCK_PRICE, b"\x00" * (12 * STOCK_PRICE_STRIDE))
            for p in range(4):
                e.write(PLAYER_BASE + p * PLAYER_STRIDE, b"\x00" * PLAYER_STRIDE)
            for p, (cash, bank, debt) in players.items():
                base = PLAYER_BASE + p * PLAYER_STRIDE
                e.write(base + P_F1C, struct.pack("<i", cash))
                e.write(base + P_F20, struct.pack("<i", bank))
                e.write(base + 0x24, struct.pack("<i", debt))
            for p, s, amount, price in stocks:
                e.write(STOCK_AMT + p * STOCK_AMT_STRIDE + s * 8, struct.pack("<i", amount))
                e.write(STOCK_PRICE + s * STOCK_PRICE_STRIDE, struct.pack("<f", price))

        r = self.emu.call(RICHEST, [], setup=setup)
        self.ret, self.esp_delta, self.insns = r["signed"], r["esp_delta"], r["insns"]
        return self


def section_b():
    print("=" * 78)
    print(f"[B] 本月首富評選 0x00437DFE（{RICH_SIZE} B）—— 候选表 / 0x4239b9 逐人 / 严格> / 返回表下标")
    if MUTATE == "B":
        print("    ★★ RICH4_MUTATE=B：把「下标≠玩家id」用例的候选表 [3,2] 改成 [2,3]（故意破坏输入）")
    print("=" * 78)
    w = RichWorld()

    # ── B1 ★ 返回值是候选表下标，不是玩家 id ──
    print("B1 ★ 返回值 = 候选表下标（候选表 [3,2]，玩家 2 最有钱）")
    w.run(m("B", [3, 2], [2, 3]), players={2: (900, 0, 0), 3: (100, 0, 0)})   # ★ 破坏点 B
    case("返回 1 = **表下标**（玩家 id 是 2，表里第 2 位）", w.ret, 1)
    case("0x4239b9 被调 2 次（每个候选各一次）", len(w.calls), 2)
    case("实参顺序 = 候选表顺序 [3,2]", w.calls, [3, 2])
    case("esp_delta = 4（cdecl）", w.esp_delta, 4)

    print("B1b 换一张表：候选 [0,3]，玩家 3 最有钱")
    w.run([0, 3], players={0: (100, 0, 0), 3: (900, 0, 0)})
    case("返回 1 = 表下标（玩家 id 3）", w.ret, 1)
    case("实参顺序 [0,3]", w.calls, [0, 3])

    print("B1c 候选 [2,1,0]，玩家 1 最有钱（升序表）")
    w.run([2, 1, 0], players={0: (100, 0, 0), 1: (500, 0, 0), 2: (-50, 0, 0)})
    case("返回 1（表下标）", w.ret, 1)
    case("实参顺序 [2,1,0]（原样遍历，不排序）", w.calls, [2, 1, 0])

    print("B1d 乱序候选 [1,3,0]，玩家 0 最有钱 ⇒ 返回 2")
    w.run([1, 3, 0], players={0: (7000, 0, 0), 1: (10, 0, 0), 3: (20, 0, 0)})
    case("返回 2 = 表下标（玩家 id 0）", w.ret, 2)

    # ── B2 严格 >：平手取先出现的 ──
    print("B2 严格 >（0x437e23 `cmp esi,eax / jge` 跳过替换）")
    w.run([1, 3], players={1: (900, 0, 0), 3: (900, 0, 0)})
    case("两家同分 ⇒ 表下标 0", w.ret, 0)
    case("两次都调了 0x4239b9", len(w.calls), 2)
    w.run([0, 1, 2], players={0: (50, 0, 0), 1: (50, 0, 0), 2: (50, 0, 0)})
    case("三家同分 ⇒ 表下标 0", w.ret, 0)
    w.run([3, 1], players={1: (100, 0, 0), 3: (100, 0, 0)})
    case("同分且玩家号倒序 ⇒ 仍是表下标 0（不是 id 小的赢）", w.ret, 0)

    # ── B3 单调表 ──
    print("B3 单调候选表")
    w.run([0, 1, 2], players={0: (10, 0, 0), 1: (20, 0, 0), 2: (30, 0, 0)})
    case("递增 ⇒ 最后一个下标 2", w.ret, 2)
    w.run([0, 1, 2], players={0: (30, 0, 0), 1: (20, 0, 0), 2: (10, 0, 0)})
    case("递减 ⇒ 第 0 个", w.ret, 0)
    w.run([1, 0, 2], players={0: (500, 0, 0), 1: (20, 0, 0), 2: (30, 0, 0)})
    case("最大值在表中间 ⇒ 1", w.ret, 1)

    # ── B4 空表 / 单人 / 全负 ──
    print("B4 best/bestAt 初值 0 的边界")
    w.run([])
    case("候选人数 0 ⇒ 返回 0，且一次都没调 0x4239b9", (w.ret, len(w.calls)), (0, 0))
    w.run([2], players={2: (123, 0, 0)})
    case("单候选 ⇒ 0", w.ret, 0)
    w.run([0, 1, 2, 3], players={p: (-100, 0, 0) for p in range(4)})
    case("全负资产 ⇒ 返回 0（best 停在初值 0，不选负数）", w.ret, 0)
    case("全负也逐人调 0x4239b9（4 次）", len(w.calls), 4)
    w.run([0, 1], players={0: (-5, 0, 0), 1: (0, 0, 0)})
    case("(-5, 0) ⇒ 0（0 > -5 不成立，best 不动）", w.ret, 0)

    # ── B5 0x4239b9 真跑：现金/存款/贷款/股票/截断 都参与排序 ──
    print("B5 0x4239b9 **真跑**：现金+存款-贷款+股票市值 全参与")
    w.run([0, 1], players={0: (100, 0, 0), 1: (0, 500, 0)})
    case("存款计入（0 现金 +500 存款 > 100 现金）⇒ 1", w.ret, 1)
    w.run([0, 1], players={0: (600, 0, 0), 1: (700, 0, 200)})
    case("贷款计入（700-200=500 < 600）⇒ 0", w.ret, 0)
    w.run([0, 1], players={0: (1000, 0, 0), 1: (100, 0, 0)}, stocks=[(1, 0, 10, 1000.0)])
    case("股票市值计入（100+10×1000 > 1000）⇒ 1", w.ret, 1)
    w.run([0, 1], players={0: (2, 0, 0), 1: (0, 0, 0)}, stocks=[(1, 0, 1, 2.5)])
    case("★ 浮点**向零截断**：trunc(2.5)=2 ⇒ 与 2 平手 ⇒ 0", w.ret, 0)
    w.run([0, 1], players={0: (2, 0, 0), 1: (0, 0, 0)}, stocks=[(1, 0, 1, 3.5)])
    case("对照：3.5 → 3 > 2 ⇒ 1（证明上一条不是恒真）", w.ret, 1)

    # ── B6 候选表是 byte[]，重复项原样遍历 ──
    print("B6 候选表按 byte 逐项读，重复项不去重")
    w.run([3, 3], players={3: (50, 0, 0)})
    case("重复候选 [3,3] ⇒ 调 2 次、返回 0", (len(w.calls), w.ret), (2, 0))
    w.run([2, 0, 1], players={0: (900, 0, 0), 1: (10, 0, 0), 2: (20, 0, 0)})
    case("byte 表 [2,0,1]，玩家 0 最大 ⇒ 返回 1", w.ret, 1)


def main():
    print("通道 2 差分测试：保險理賠 0x0044BA63 + 本月首富評選 0x00437DFE")
    print("真值 = Rich4/rich4.exe（Unicorn 驱动原版机器码）；打桩清单见文件头 docstring")
    static_checks(Emu())
    section_a()
    section_b()
    ok, total = sum(RESULTS), len(RESULTS)
    print("=" * 78)
    print(f"{ok}/{total} 通过" + ("   ★★ 有红项" if ok != total else "   （全绿）"))
    if MUTATE:
        print(f"[M] RICH4_MUTATE={MUTATE}：故意破坏的输入应当让若干断言变红 —— 见上表 XX 行")
    print("=" * 78)
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
