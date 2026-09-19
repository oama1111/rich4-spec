#!/usr/bin/env python3
"""
通道 2 差分测试 · 两张事件牌堆的**分派器**（可行性判定 / 事件重映射 / 取牌循环）

| VA | 大小 | 一行语义 |
|---|---|---|
| `0x0044BB4B` | **715 B**（`0x44BB4B..0x44BE15`） | 命運：判定事件在当前局面下是否可行；★ 兼做**事件号重映射**（`[arg]` 是 in/out 指针） |
| `0x00448BE2` | **744 B**（`0x448BE2..0x448EC9`） | 新聞：判定事件在当前局面下是否可行（入参**按值**，无重映射） |

复刻侧：
  · `rich4-remake/packages/core/src/events/fortune.ts` 的 `checkFortune()`
  · `rich4-remake/packages/core/src/events/news.ts`   的 `isNewsFeasible()`
  · 调用点 `rich4-remake/packages/core/src/state/reduce.ts:3751` / `:3914`
  · 取牌循环 `rich4-remake/packages/core/src/events/deck.ts:104` `drawEvent()`

## 真实职责的框定（先纠一个常见误解）

这两个 VA **不是**"选一个事件号然后 `call` 事件体"。真正的"取牌 → 判定 → 调事件体"
在**调用者**里，两个调用者各 1 处（`disasm.py callers` 实测）：

```
0x44DB81  命運事件屏（"fortune_events"）：                0x44B6DF  新聞事件屏：
  do {                                                     do {
    id = deck_f[cursor_f]        ; 0x44DBBA                  id = deck_n[cursor_n]     ; 0x44B718
    ok = 0x44BB4B(&id)           ; 0x44DBD1 ★ 判定+重映射     ok = 0x448BE2(id)         ; 0x44B72B
    if (ok) {                                                if (ok) {
      ...画字/头像...                                          ...画字/头像...
      body(id, 0)                ; 0x44DC44 push 0 ★ 第 1 趟   body(id, 0)              ; 0x44B7BB push 0
    }                                                        }
    cursor = (cursor+1) % N      ; 0x44DCB0 / 0x44DCB7         cursor = (cursor+1) % N   ; 0x44B7CD / 0x44B7D4
  } while (!ok);                                             } while (!ok);
  ...模态屏 0x640ms...                                       ...模态屏 0x960ms...
  body(id, 1)                    ; 0x44DD5B push 1 ★ 第 2 趟   body(id, 1)              ; 0x44B873 push 1
```

⇒ 两趟协议（`push 0` 画字 / `push 1` 生效）与「牌堆游标无论可行与否都前进、
不可行就抽下一张」都在**调用者**里。本测试把两段调用者循环**整段驱动**
（[A11]/[A12] 与 [B13]/[B14]：`eval_block` + 把事件体表改成记录桩），
于是「抽了几张、转到哪一号、第几趟」全部成为可断言的事实；
「第 2 趟用同一个（重映射后的）号」也由 [A12]/[B14] 单独驱动坐实。

## 牌堆 / 游标（实测地址，不猜）

| | 牌堆基址 | 张数 | 游标 | 回绕判据 |
|---|---|---|---|---|
| 命運 | `0x496B38` | **37**（`0x25`） | `0x4990B4` | `0x44DCB7 cmp esi,0x25` |
| 新聞 | `0x499090` | **36**（`0x24`） | `0x4990E0` | `0x44B7D4 cmp edx,0x24` |

洗牌 `0x44BAEA`（命運 37）/ `0x448B81`（新聞 36）末尾都把游标清 0、各自
**恰好消耗"张数"次 `rand()`**（本测试实测 37 / 36）。

## 三个反复踩的坑（本测试专门各留一条断言）

1. 表基址是**绝对地址，不是指针**（`0x496D08` 物件表同族）；本测试里的表同理：
   `0x4971A0`（持股 12 槽×8B/人）、`0x496986`（股票 f6，步长 0x24）、
   `0x499120`（手牌 `player*15+slot`）、`0x496B30`/`0x496B60`（监/医占用）
   前五个按绝对地址写、不经过任何指针全局（只有三张「产业表」走 `[0x498E7C/84/88]` 指针）。
2. 循环 `i = 1..N` **跳过记录 0**：地產 `0x498E84` / 設施 `0x498E88` /
   企業 `0x498E7C` 三张表的判定循环都从 1 开始（[A2]/[B2]/[B3]/[B4]/[B8]/[B9] 各留一条）。
3. `cmp dword [0x496B30], 0` 是**4 字节**（= 只有槽 0..3，即**玩家**；不是 8 槽的
   完整占用表）。[B1] 用「只写槽 4（在**下一个 dword**）」反证。

★ **`0xff` / "未实现"哨兵：两张表里都没有。** 实测 `0x475EF0`（37 项）与
`0x475E24`（36 项）**每一项都是非 0 代码指针**，且把 id 扫到 0..255 时返回值恒 ∈ {0,1}、
`0xff` 走的是一般的 `default` 支（没有"未实现 ⇒ 跳过"的分支）。见 [A6]/[B14]。

## 打桩清单

| VA | 原用途 | 桩 | 为什么合法 |
|---|---|---|---|
| `0x456F2D` | CRT `rand()` | 从数据槽读 + **计数** | 确定性；★ 计数本身是本测试的判据（判定器**一次都不该摇**，洗牌**恰好摇 N 次**） |
| `0x475EF0[0..36]` | 命運事件体表（数据） | 指向记录桩 | [A8]/[A9] 只关心"转到哪一号、第几趟"，事件体另有测试（`test_fortune_event14.py` 等） |
| `0x475E24[0..35]` | 新聞事件体表（数据） | 同上 | 同上 |
| `0x44F9D8`/`0x450441`/`0x456280`/`0x456E11`/`0x44FABC` | 建窗/贴图/画字/销毁窗/画色码字 | `ret` | 表现层；调用者自己 `add esp,N` 清栈（cdecl），桩不动任何寄存器 |

**真跑**（判据主体）：`0x44BB4B`、`0x448BE2` 本体；`0x441262`（手牌非零槽计数，
命運 5 要它）、`0x40D73F`（在局且无阻碍计数，新聞 29 要它）都**不打桩** ——
它们是判定的一部分，不是表现层。

跑法：`cd rich4-spec && .venv/bin/python tests/test_event_dispatch.py`

## 可证伪钩子（第 7 步：故意打断一个字节）

    EVENT_DISPATCH_MUTATE=A  # 0x44BB5C 的立即数 0x0c → 0x0d（命運首层分派树错位）
    EVENT_DISPATCH_MUTATE=B  # 0x448C9B 的 0x30 → 0x60（新聞 0/1 改读医院表）

两者都只改**原版机器码一个字节**（运行时 patch，不改任何文件）。实测：

| 注入 | 打断的字节 | 转红 |
|---|---|---|
| （无） | — | **259/259 通过** |
| `A` | `0x44BB5C: 83 FB 0C → 83 FB 0D`（命運首层分派树错位：id 12 落进 10/11 支） | **7 条**：id 12/13 的 traffic 映射 4 条 + 「重映射要传到事件体」3 条 |
| `B` | `0x448C9B: 30 → 60`（新聞 0/1 的 `cmp dword [0x496B30]` 改读医院表 `0x496B60`） | **4 条**：监狱表那 4 条 |
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, STACK_TOP, Emu  # noqa: E402

try:
    from unicorn import UC_HOOK_CODE
except ImportError:                      # pragma: no cover
    sys.exit("需要 unicorn：python3 -m venv .venv && .venv/bin/pip install unicorn")

# ── 被测函数 ──────────────────────────────────────────────────────────
FORTUNE_GATE = 0x44BB4B
FORTUNE_GATE_END = 0x44BE16          # 715 B
NEWS_GATE = 0x448BE2
NEWS_GATE_END = 0x448ECA             # 744 B

# ── 洗牌（牌堆/游标的来源） ────────────────────────────────────────────
FORTUNE_SHUFFLE = 0x44BAEA
NEWS_SHUFFLE = 0x448B81

# ── 调用者循环（两趟协议 + 游标前进/回绕） ─────────────────────────────
FORTUNE_LOOP = 0x44DBBA              # do { id = deck[cursor]; ok = gate(&id); ...
FORTUNE_LOOP_STOP = 0x44DCCC         # ★ 只在 ok != 0 时到达 ⇒ 跑整段「不可行就抽下一张」
FORTUNE_PASS1 = 0x44DD51             # push 1; call table[ebp]
FORTUNE_PASS1_STOP = 0x44DD78
NEWS_LOOP = 0x44B718                 # do { id = deck[cursor]; ok = gate(id); ...
NEWS_LOOP_STOP = 0x44B7E9            # ★ 只在 ok != 0 时到达
NEWS_PASS1 = 0x44B86F                # mov eax,[esp+0x10]; push 1; call table[eax]
NEWS_PASS1_STOP = 0x44B87C

# ── 事件体指针表（数据） ──────────────────────────────────────────────
FORTUNE_TABLE = 0x475EF0
FORTUNE_TABLE_N = 37
NEWS_TABLE = 0x475E24
NEWS_TABLE_N = 36

# ── 牌堆 / 游标 ───────────────────────────────────────────────────────
FORTUNE_DECK = 0x496B38
FORTUNE_CURSOR = 0x4990B4
NEWS_DECK = 0x499090
NEWS_CURSOR = 0x4990E0

# ── 里循环会用到的全局 ────────────────────────────────────────────────
PRNG = 0x456F2D
CUR = 0x49910C
NUM_PLAYERS = 0x499114
GAME_STAGE = 0x4991B6                # ★ 命運 33..36 的唯一判据（word）
GAME_MAP = 0x4991B8                  # ★ 调用者里 `id >= 33` 支的表位移（word）
SURFACE_F = 0x48C5E0                 # 命運屏 surface（只作实参）
SURFACE_N = 0x48C5AC                 # 新聞屏 surface
DRAWOBJ_A = 0x48A0E4                 # 新聞屏画字用的对象
DRAWOBJ_B = 0x48A0E0                 # 命运屏 modal 用的对象（只在本块之外用）

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_VEHICLE, P_WHO, P_BLOCK = 0x11, 0x15, 0x32   # +0x32 是 dword（四个阻碍计数）
PRISON_TABLE = 0x496B30              # ★ 判定里按 **dword** 读（= 槽 0..3）
HOSPITAL_TABLE = 0x496B60

LAND_PTR, LAND_COUNT = 0x498E84, 0x498E98
FAC_PTR, FAC_COUNT = 0x498E88, 0x498E8C
COM_PTR, COM_COUNT = 0x498E7C, 0x498E90
L_STRIDE, L_OWNER, L_LEVEL = 0x34, 0x19, 0x1A
F_STRIDE, F_OWNER, F_LEVEL = 0x38, 0x19, 0x1A
C_STRIDE, C_OWNER, C_PRICE = 0x34, 0x18, 0x28

STOCK_HOLD = 0x4971A0                # 绝对基址：p*0x60 + i*8（+0 = 持股数）
STOCK_F6 = 0x496986                  # 绝对基址：i*0x24（+0 = stock_info.f6）
HAND_TABLE = 0x499120                # 绝对基址：p*15 + slot

# ── 暂存区布局 ────────────────────────────────────────────────────────
ID_SLOT = SCRATCH_BASE + 0x0100      # 命運判定器的 in/out 事件号
RAND_COUNT = SCRATCH_BASE + 0x0200
RAND_VALUE = SCRATCH_BASE + 0x0204
LOG_COUNT = SCRATCH_BASE + 0x0300
LOG_EAX = SCRATCH_BASE + 0x0400
LOG_EBX = SCRATCH_BASE + 0x0C00
LOG_EBP = SCRATCH_BASE + 0x1400
LOG_RET = SCRATCH_BASE + 0x1C00
LOG_PASS = SCRATCH_BASE + 0x2400
MARK = SCRATCH_BASE + 0x2C00
SURFACE_OBJ = SCRATCH_BASE + 0x3000
LAND_TAB = SCRATCH_BASE + 0x4000
FAC_TAB = SCRATCH_BASE + 0x5000
COM_TAB = SCRATCH_BASE + 0x6000

STUB_BODY = STUB_BASE + 0x400
STUB_MARK = STUB_BASE + 0x500

SURFACE = 0x00700000                 # 假 surface（只作实参）
SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    g = got if isinstance(got, (int, float)) else str(got)
    x = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'OK ' if ok else 'NG '} {desc:<64} 实际 {g!s:<22} 期望 {x!s}")
    return ok


def p32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def rand_stub():
    """`rand()` 桩：计数器 +1，返回数据槽里的定值。"""
    return (b"\xFF\x05" + p32(RAND_COUNT)     # inc dword [RAND_COUNT]
            + b"\xA1" + p32(RAND_VALUE)       # mov eax,[RAND_VALUE]
            + b"\xC3")


def log_stub():
    """事件体桩：把 (eax, ebx, ebp, 返回地址, [esp+4]=趟号) 追加进记录区。

    ★ 只用 eax/ecx/edx —— 调用者在这些调用点依赖 ebx/esi/edi/ebp 活着
      （verification.md 工具边界：桩里拿 ebx 当临时寄存器会静默破坏调用方）。
    """
    c = b""
    c += b"\x8B\x0D" + p32(LOG_COUNT)          # mov ecx,[LOG_COUNT]
    c += b"\x89\x04\x8D" + p32(LOG_EAX)        # mov [LOG_EAX+ecx*4],eax
    c += b"\x89\x1C\x8D" + p32(LOG_EBX)        # mov [LOG_EBX+ecx*4],ebx
    c += b"\x89\x2C\x8D" + p32(LOG_EBP)        # mov [LOG_EBP+ecx*4],ebp
    c += b"\x8B\x14\x24"                       # mov edx,[esp]     （返回地址）
    c += b"\x89\x14\x8D" + p32(LOG_RET)        # mov [LOG_RET+ecx*4],edx
    c += b"\x8B\x54\x24\x04"                   # mov edx,[esp+4]   （趟号 0/1）
    c += b"\x89\x14\x8D" + p32(LOG_PASS)       # mov [LOG_PASS+ecx*4],edx
    c += b"\x41"                               # inc ecx
    c += b"\x89\x0D" + p32(LOG_COUNT)          # mov [LOG_COUNT],ecx
    c += b"\x31\xC0"                           # xor eax,eax
    c += b"\xC3"
    return c


def mark_stub():
    return b"\xFF\x05" + p32(MARK) + b"\x31\xC0\xC3"    # inc [MARK]; xor eax,eax; ret


class World:
    """一次 exe 镜像 + 可复位的局面注入。"""

    def __init__(self):
        self.emu = Emu()
        # ★ 测试台缺陷（本测试要调用上千次，必须自己收口）：
        #   `Emu.call()/eval_block()` 每次都 `hook_add(UC_HOOK_CODE, self._hook)`
        #   却**从不 hook_del** ⇒ 钩子线性累积，而 `_hook` 每命中一条指令就
        #   `insn_count += 1` 并在 > MAX_INSN 时 `emu_stop()`。
        #   实测：本文件跑到 [A9] 时已累积约 200 个钩子 ⇒ `insn_count` 涨 200 倍
        #   ⇒ 洗牌（6533 条指令）在第 8 张牌处被**静默截断**（表现为"只摇了 8 次"）。
        #   这里把 `hook_add` 换成记账版，每次驱动后统一摘掉。
        self._hooks = []
        self._track_hooks()
        self.emu.patch(PRNG, rand_stub())
        self.emu.patch(STUB_BODY, log_stub())
        self.emu.patch(STUB_MARK, mark_stub())
        for va in (0x44F9D8, 0x450441, 0x456280, 0x456E11, 0x44FABC):
            self.emu.patch(va, b"\xC3")
        self.clear()

    def _track_hooks(self):
        real_add = self.emu.mu.hook_add
        real_del = self.emu.mu.hook_del

        def tracked(htype, cb, *a, **k):
            h = real_add(htype, cb, *a, **k)
            self._hooks.append(h)
            return h

        self.emu.mu.hook_add = tracked
        self._real_hook_del = real_del

    def _purge_hooks(self):
        while self._hooks:
            h = self._hooks.pop()
            try:
                self._real_hook_del(h)
            except Exception:                     # noqa: BLE001
                pass

    def _call(self, va, args, setup=None):
        """`Emu.call` + 驱动后摘钩（见 `_track_hooks` 的说明）。"""
        try:
            return self.emu.call(va, args, setup=setup)
        finally:
            self._purge_hooks()

    def _block(self, start, stop, regs=None, setup=None, timeout=200000):
        """`Emu.eval_block` + **自己**的停址钩子。

        ★ 实测：这里只靠 `emu_start(begin, until)` **不够** —— 调用者循环里
          `until` 会被跳过（翻译块链接会在链内继续跑），执行随即冲进
          `mov eax,[0x48A0E0] / mov ebx,[eax]` 踩未映射地址。
          用 `UC_HOOK_CODE` 在停址上 `emu_stop()` 可靠；但**停址必须在指令边界**
          （本测试一开始写的 0x44DCC8 其实是 `je rel32` 的第 3 个字节，真边界是
          0x44DCCC —— 症状是崩在 0x44DCD1）。
        """
        mu = self.emu.mu

        def stopper(m, addr, size, user):
            if addr == stop:
                m.emu_stop()

        mu.hook_add(UC_HOOK_CODE, stopper)
        try:
            return self.emu.eval_block(start, stop, regs, setup=setup,
                                       timeout_insns=timeout)
        finally:
            self._purge_hooks()

    # ── 局面 ──────────────────────────────────────────────────────────
    def clear(self):
        self.event_id = 0
        self.cur = 0
        self.num = 4
        self.stage = 0
        self.game_map = 0
        self.lands = {}          # idx -> (owner, level)   记录 1..N；0 = 表头
        self.facs = {}           # idx -> (owner, level)
        self.comms = {}          # idx -> (owner, price@+0x28)
        self.stocks = {}         # (p, i) -> dword @ +0
        self.stocks_hi = {}      # (p, i) -> dword @ +4（**不该被读**）
        self.hands = set()       # (p, slot)
        self.players = {p: (1, 0, 0) for p in range(4)}   # p -> (who, vehicle, block32)
        self.prison = 0
        self.hospital = 0
        self.f6 = [0] * 12
        self.deck = None         # 命運牌堆（37 字节）；None ⇒ 不写
        self.news_deck = None
        self.cursor = 0
        return self

    def hand(self, p, slot):
        self.hands.add((p, slot))
        return self

    def land(self, idx, owner, level):
        self.lands[idx] = (owner, level)
        return self

    def fac(self, idx, owner, level):
        self.facs[idx] = (owner, level)
        return self

    def comm(self, idx, owner, price):
        self.comms[idx] = (owner, price)
        return self

    def stock(self, p, i, amount):
        self.stocks[(p, i)] = amount
        return self

    def sole(self, p, who=1, vehicle=0, block=0):
        """只让玩家 p 在局（其余 4 人 who_plays 全 0），便于钉「逐玩家扫描」的闸门。"""
        for q in range(4):
            self.players[q] = (0, 0, 0)
        self.players[p] = (who, vehicle, block)
        return self

    def player(self, p, who=None, vehicle=None, block=None):
        w, v, b = self.players.get(p, (0, 0, 0))
        self.players[p] = (w if who is None else who,
                           v if vehicle is None else vehicle,
                           b if block is None else block)
        return self

    def rand(self, value):
        self.emu.write(RAND_VALUE, p32(value))
        return self

    # ── 注入 ──────────────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.cur)
        emu.write32(NUM_PLAYERS, self.num)
        emu.write16(GAME_STAGE, self.stage & 0xFFFF)
        emu.write16(GAME_MAP, self.game_map & 0xFFFF)
        emu.write32(SURFACE_F, SURFACE)
        emu.write32(SURFACE_N, SURFACE)
        emu.write32(DRAWOBJ_A, SURFACE)
        emu.write32(DRAWOBJ_B, SURFACE)
        emu.write32(SURFACE_OBJ + 8, 0)
        emu.write32(ID_SLOT, self.event_id)

        # 地產 / 設施 / 企業：三张表都是**绝对基址**全局
        for base, stride, n, items, off_o, off_l in (
            (LAND_TAB, L_STRIDE, 0x400, self.lands, L_OWNER, L_LEVEL),
            (FAC_TAB, F_STRIDE, 0x400, self.facs, F_OWNER, F_LEVEL),
            (COM_TAB, C_STRIDE, 0x400, self.comms, C_OWNER, None),
        ):
            emu.write(base, bytes(n))          # ★ 暂存区跨 call 保留 ⇒ 每次清整张表
            for idx, val in items.items():
                rec = base + idx * stride
                emu.write8(rec + off_o, val[0] & 0xFF)
                if off_l is not None:
                    emu.write8(rec + off_l, val[1] & 0xFF)
                else:
                    emu.write(rec + C_PRICE, p32(val[1]))
        emu.write32(LAND_PTR, LAND_TAB)
        emu.write32(LAND_COUNT, max(self.lands) if self.lands else 0)
        emu.write32(FAC_PTR, FAC_TAB)
        emu.write32(FAC_COUNT, max(self.facs) if self.facs else 0)
        emu.write32(COM_PTR, COM_TAB)
        emu.write32(COM_COUNT, max(self.comms) if self.comms else 0)

        # 持股 / 手牌 / 股票 f6 / 占用表 / 玩家表：全是绝对地址
        emu.write(STOCK_HOLD, bytes(4 * 0x60))
        for (p, i), amt in self.stocks.items():
            emu.write(STOCK_HOLD + p * 0x60 + i * 8, p32(amt))
        for (p, i), amt in self.stocks_hi.items():
            emu.write(STOCK_HOLD + p * 0x60 + i * 8 + 4, p32(amt))
        emu.write(HAND_TABLE, bytes(60))
        for p, slot in self.hands:
            emu.write8(HAND_TABLE + p * 15 + slot, 7)
        for i, v in enumerate(self.f6):
            emu.write8(STOCK_F6 + i * 0x24, v & 0xFF)
        emu.write(PRISON_TABLE, p32(self.prison))
        emu.write(HOSPITAL_TABLE, p32(self.hospital))
        for p in range(8):
            base = PLAYER_BASE + p * PLAYER_STRIDE
            who, veh, blk = self.players.get(p, (0, 0, 0))
            emu.write8(base + P_WHO, who & 0xFF)
            emu.write8(base + P_VEHICLE, veh & 0xFF)
            emu.write(base + P_BLOCK, p32(blk))

    # ── 被判定器直接驱动 ──────────────────────────────────────────────
    def gate_fortune(self, eid):
        self.event_id = eid
        r = self._call(FORTUNE_GATE, [ID_SLOT], setup=self._setup)
        return r["eax"], self.emu.read32(ID_SLOT), r["esp_delta"]

    def gate_fortune_ret(self, eid):
        return self._gate_fortune_short(eid)[0]

    def _gate_fortune_short(self, eid):
        self.event_id = eid
        r = self._call(FORTUNE_GATE, [ID_SLOT], setup=self._setup)
        return r["eax"], self.emu.read32(ID_SLOT)

    def gate_news(self, eid):
        self.event_id = eid
        r = self._call(NEWS_GATE, [eid], setup=self._setup)
        return r["eax"], r["esp_delta"]

    def gate_news_ret(self, eid):
        return self.gate_news(eid)[0]

    # ── 取牌循环（整段驱动调用者） ────────────────────────────────────
    def _loop_setup(self, emu):
        self._setup(emu)
        emu.scratch_write(LOG_COUNT, bytes(4))
        emu.write32(MARK, 0)
        for i in range(FORTUNE_TABLE_N):
            emu.write32(FORTUNE_TABLE + i * 4, STUB_BODY)
        for i in range(NEWS_TABLE_N):
            emu.write32(NEWS_TABLE + i * 4, STUB_BODY)
        # 表尾之后一格：给"`id >= 33` 支的表位移"留的独立桩
        emu.write32(FORTUNE_TABLE + FORTUNE_TABLE_N * 4, STUB_MARK)
        if self.deck is not None:
            emu.write(FORTUNE_DECK, bytes(self.deck))
        if self.news_deck is not None:
            emu.write(NEWS_DECK, bytes(self.news_deck))

    def run_fortune_loop(self, start, deck, timeout=200000):
        self.cursor = start
        self.deck = list(deck) + [0] * (37 - len(deck))

        def setup(emu):
            self._loop_setup(emu)
            emu.write32(FORTUNE_CURSOR, start)

        self._block(FORTUNE_LOOP, FORTUNE_LOOP_STOP,
                    {"ebx": SURFACE_OBJ}, setup=setup, timeout=timeout)
        return self.emu.read32(FORTUNE_CURSOR)

    def run_news_loop(self, start, deck, timeout=200000):
        self.news_deck = list(deck) + [0] * (36 - len(deck))

        def setup(emu):
            self._loop_setup(emu)
            emu.write32(NEWS_CURSOR, start)

        self._block(NEWS_LOOP, NEWS_LOOP_STOP,
                    {"esi": SURFACE_OBJ, "ebx": 0}, setup=setup, timeout=timeout)
        return self.emu.read32(NEWS_CURSOR)

    def run_fortune_pass1(self, eid, game_map=None):
        def setup(emu):
            self._loop_setup(emu)
            if game_map is not None:
                emu.write16(GAME_MAP, game_map & 0xFFFF)

        self._block(FORTUNE_PASS1, FORTUNE_PASS1_STOP,
                    {"ebp": eid}, setup=setup)
        return self.logs()

    def run_news_pass1(self, eid):
        def setup(emu):
            self._loop_setup(emu)
            emu.write32(STACK_TOP + 0x10, eid)

        self._block(NEWS_PASS1, NEWS_PASS1_STOP, {}, setup=setup)
        return self.logs()

    # ── 记录区 ────────────────────────────────────────────────────────
    def logs(self):
        n = self.emu.read32(LOG_COUNT)
        out = []
        for k in range(n):
            out.append({
                "eax": self.emu.read32(LOG_EAX + k * 4),
                "ebx": self.emu.read32(LOG_EBX + k * 4),
                "ebp": self.emu.read32(LOG_EBP + k * 4),
                "ret": self.emu.read32(LOG_RET + k * 4),
                "pass": self.emu.read32(LOG_PASS + k * 4),
            })
        return out


def section(title):
    print(f"\n── {title} " + "─" * max(0, 70 - len(title)))


# ======================================================================
#  [A] 命運事件判定器 / 重映射器 0x0044BB4B
# ======================================================================
def section_a(w, mutate):
    print("\n" + "=" * 74)
    print("[A] 命運 0x0044BB4B —— 715 B：可行性判定 + 事件号重映射（in/out 指针）")
    print("=" * 74)

    section("[A0] 函数边界 / 调用约定 / 返回编码")
    code = w.emu.read(FORTUNE_GATE, 4)
    case("入口前 4 字节是 push ebx/esi/edi/ebp（0x53 56 57 55）", code.hex(), "53565755")
    case("0x44BE15 是 ret（0xC3）", w.emu.read8(0x44BE15), 0xC3)
    case("0x44BE16 已是下一个函数（0x53 56）", w.emu.read(0x44BE16, 2).hex(), "5356")
    case("尺寸 = 0x44BE16 − 0x44BB4B = 715 B", FORTUNE_GATE_END - FORTUNE_GATE, 715)

    w.clear().land(1, 1, 2)
    ret, new_id, delta = w.gate_fortune(0)
    case("cdecl 单实参：esp_delta == 4", delta, 4)
    case("入参是**指针**：[arg] 被原样读回（id 0 不重映射）", new_id, 0)
    w.clear()
    ret, new_id, _ = w.gate_fortune(12)
    case("★ 入参是 in/out 指针：id 12 且 traffic=0 ⇒ 自映射、[arg] 仍是 12", new_id, 12)
    w.clear().player(0, vehicle=1)
    ret, new_id, _ = w.gate_fortune(12)
    case("★ …traffic=1 ⇒ [arg] 12 → 13（真改写）", (ret, new_id), (1, 13))

    section("[A1] 返回编码：全 id 域只可能是 0 / 1")
    seen = set()
    w.clear().land(1, 1, 3).player(0, vehicle=1)
    for eid in range(0, 41):
        seen.add(w.gate_fortune_ret(eid))
    w.clear().land(1, 1, 0).stock(0, 0, 5).player(0, vehicle=2)
    for eid in range(0, 41):
        seen.add(w.gate_fortune_ret(eid))
    case("id 0..40 两种局面下返回值集合 ⊆ {0,1}", sorted(seen), [0, 1])
    case("★ id 0xff（255）不是「未实现」哨兵 ⇒ 返回 1 且不改号",
         w.gate_fortune(0xFF)[:2], (1, 0xFF))

    section("[A2] 事件 0 / 1 —— 自有地產（owner 1 基、level 0x1a）")
    w.clear().land(1, 1, 3)
    case("自有 3 级地 ⇒ id 0 可行", w.gate_fortune(0)[:2], (1, 0))
    w.clear().land(1, 1, 0)
    case("★ 自有**空地** ⇒ id 0 不可行", w.gate_fortune(0)[:2], (0, 0))
    case("★ 同一局面 id 1（空地）可行", w.gate_fortune(1)[:2], (1, 1))
    w.clear().land(1, 2, 3)
    case("★ owner=2 而当前玩家 0 ⇒ id 0 不可行（owner 是 1 基）", w.gate_fortune(0)[:2], (0, 0))
    w.clear().land(1, 1, 3)
    case("  同一局面 id 1 不可行（有房 ⇒ 不是空地）", w.gate_fortune(1)[:2], (0, 1))
    w.clear().land(1, 0, 3)
    case("★ owner=0（无主）永远不算「我的地」 ⇒ id 0 不可行", w.gate_fortune(0)[:2], (0, 0))
    w.clear()
    case("  一张地都没有 ⇒ id 0 不可行", w.gate_fortune(0)[:2], (0, 0))
    case("  一张地都没有 ⇒ id 1 不可行", w.gate_fortune(1)[:2], (0, 1))
    w.clear().land(1, 2, 3)
    w.cur = 1
    case("  cur=1 时 owner 2 == cur+1 ⇒ id 0 可行", w.gate_fortune(0)[:2], (1, 0))
    w.cur = 2
    case("  cur=2 时同一块地不再算我的 ⇒ id 0 不可行", w.gate_fortune(0)[:2], (0, 0))
    # ★ 循环 i = 1..N 跳过记录 0
    w.clear().land(0, 1, 5).land(1, 0, 0)
    case("★★ 记录 0 里的 5 级地**不算**（循环 i=1..N）", w.gate_fortune(0)[:2], (0, 0))
    w.clear().land(0, 1, 0).land(1, 0, 0)
    case("★★ 记录 0 里的空地也不算 ⇒ id 1 不可行", w.gate_fortune(1)[:2], (0, 1))
    w.clear().land(1, 0, 0).land(2, 1, 4)
    case("  可行记录在第 2 条 ⇒ 仍能找到（不是只看第一条）", w.gate_fortune(0)[:2], (1, 0))

    section("[A3] 事件 2/3/4/6/7 与 17..32 —— 一律可行（default）")
    w.clear()
    for eid in (2, 3, 4, 6, 7):
        case(f"空局面 id {eid} ⇒ 1（无约束）", w.gate_fortune(eid)[:2], (1, eid))
    for eid in list(range(17, 33)) + [37, 40, 255]:
        case(f"空局面 id {eid} ⇒ 1（无约束、不改号）", w.gate_fortune(eid)[:2], (1, eid))

    section("[A4] 事件 5 —— **其他**玩家手牌总数 ≠ 0（`0x441262` 真跑）")
    w.clear()
    case("全场空手 ⇒ 不可行", w.gate_fortune(5)[:2], (0, 5))
    w.hand(0, 0)
    case("★ 只有**自己**手里有牌 ⇒ 仍不可行（跳过 self）", w.gate_fortune(5)[:2], (0, 5))
    w.clear().land(1, 1, 1)
    w.hand(1, 0)
    case("别的玩家有 1 张 ⇒ 可行", w.gate_fortune(5)[:2], (1, 5))
    w.clear().hand(3, 14)
    case("★ 槽 14（最后一格）也算（0x441262 扫 0..14）", w.gate_fortune(5)[:2], (1, 5))
    w.clear().hand(1, 0).hand(3, 7)
    w.num = 2
    case("★★ num=2 时玩家 3 不在局 ⇒ 只数玩家 0..1", w.gate_fortune(5)[:2], (1, 5))
    w.clear().hand(3, 7)
    w.num = 2
    case("★★ 只有玩家 3（超界）有牌 ⇒ 不可行（上界是 [0x499114]）", w.gate_fortune(5)[:2], (0, 5))
    w.clear().hand(0, 0).hand(2, 3)
    w.cur = 2
    case("  cur=2 ⇒ 玩家 0 变成「别人」⇒ 可行", w.gate_fortune(5)[:2], (1, 5))

    section("[A5] 事件 8 / 9 —— **当前玩家自己**的 12 支持股（`0x4971A0 + p*0x60 + i*8`）")
    w.clear()
    case("没有持股 ⇒ id 8 不可行", w.gate_fortune(8)[:2], (0, 8))
    case("没有持股 ⇒ id 9 不可行", w.gate_fortune(9)[:2], (0, 9))
    w.clear().stock(0, 0, 3)
    case("持第 0 支 ⇒ id 8 可行", w.gate_fortune(8)[:2], (1, 8))
    case("持第 0 支 ⇒ id 9 可行", w.gate_fortune(9)[:2], (1, 9))
    w.clear().stock(0, 11, -5)
    case("★ 第 11 支（最后一格）也算（循环 0..11）", w.gate_fortune(8)[:2], (1, 8))
    w.clear().stock(3, 0, 9)
    case("★ 只有**别的**玩家持股 ⇒ 当前玩家 id 8 不可行", w.gate_fortune(8)[:2], (0, 8))
    w.cur = 3
    case("  cur=3 后同一格 ⇒ 可行", w.gate_fortune(8)[:2], (1, 8))
    w.clear()
    w.stocks_hi[(0, 0)] = 0x7FFFFFFF
    case("★★ 只读每槽的 **+0**（持股数）：+4 有值 ⇒ 仍不可行", w.gate_fortune(8)[:2], (0, 8))
    w.clear()
    w.stocks[(0, 12)] = 5          # 第 13 个 dword（越过 12 槽）
    case("★★ 第 12 槽（下标 12）**不读**（上界 = 12 支）", w.gate_fortune(8)[:2], (0, 8))
    w.emu.write32(STOCK_HOLD + 0 * 0x60 + 12 * 8, 5)
    case("  （同上，直接写绝对地址复核）", w.gate_fortune(8)[:2], (0, 8))

    section("[A6] 事件 10/11（車）与 12/13（步行/車）—— traffic = player+0x11")
    expect = {
        # id: {vehicle: (feasible, resulting id)}
        10: {0: (0, 10), 1: (1, 10), 2: (1, 11), 3: (0, 10), 255: (0, 10)},
        11: {0: (0, 11), 1: (1, 10), 2: (1, 11), 3: (0, 11), 255: (0, 11)},
        12: {0: (1, 12), 1: (1, 13), 2: (0, 12), 3: (0, 12), 255: (0, 12)},
        13: {0: (1, 12), 1: (1, 13), 2: (0, 13), 3: (0, 13), 255: (0, 13)},
        14: {0: (1, 14), 1: (1, 15), 2: (1, 16), 3: (0, 14), 255: (0, 14)},
        15: {0: (1, 14), 1: (1, 15), 2: (1, 16), 3: (0, 15), 255: (0, 15)},
        16: {0: (1, 14), 1: (1, 15), 2: (1, 16), 3: (0, 16), 255: (0, 16)},
    }
    for eid, table in expect.items():
        for veh, want in table.items():
            w.clear().player(0, vehicle=veh)
            got = w.gate_fortune(eid)[:2]
            case(f"id {eid}, traffic={veh} ⇒ {want}", got, want)
    w.clear().player(2, vehicle=1)
    w.cur = 2
    case("★ traffic 读的是**当前玩家**（cur=2, veh=1, id 10 ⇒ 保持 10）",
         w.gate_fortune(10)[:2], (1, 10))
    w.clear().player(2, vehicle=2)
    w.cur = 2
    case("★ cur=2, veh=2, id 10 ⇒ 11", w.gate_fortune(10)[:2], (1, 11))

    section("[A7] 事件 33..36 —— `word [0x4991B6] == 0` 才可行")
    for eid in (33, 34, 35, 36):
        w.clear()
        w.stage = 0
        case(f"stage=0 ⇒ id {eid} 可行", w.gate_fortune(eid)[:2], (1, eid))
        w.stage = 1
        case(f"★ stage=1 ⇒ id {eid} 不可行", w.gate_fortune(eid)[:2], (0, eid))
        w.stage = 255
        case(f"★ stage=255（非 0）⇒ id {eid} 不可行", w.gate_fortune(eid)[:2], (0, eid))
    w.clear()
    w.stage = 1
    case("★ 边界：id 32 不受 stage 约束 ⇒ 仍 1", w.gate_fortune(32)[:2], (1, 32))
    case("★ 边界：id 37 不受 stage 约束 ⇒ 仍 1", w.gate_fortune(37)[:2], (1, 37))

    section("[A8] ★ rand 消耗：判定器本身**一次都不摇**")
    w.emu.write32(RAND_COUNT, 0)
    for eid in range(0, 41):
        w.gate_fortune_ret(eid)
    w.clear().land(1, 1, 1).hand(1, 0).stock(0, 0, 1).player(0, vehicle=1)
    for eid in range(0, 41):
        w.gate_fortune_ret(eid)
    case("id 0..40 × 两种局面 ⇒ rand 调用数 == 0", w.emu.read32(RAND_COUNT), 0)

    section("[A9] 牌堆：洗牌 `0x44BAEA` ⇒ 37 张、游标 `0x4990B4` 清 0、摇 37 次")
    w.clear().rand(12345)
    w.emu.write32(RAND_COUNT, 0)
    w._call(FORTUNE_SHUFFLE, [], setup=lambda e: e.write32(RAND_VALUE, 12345))
    deck = list(w.emu.read(FORTUNE_DECK, 37))
    case("洗出的 37 字节是 0..36 的一个排列", sorted(deck), list(range(37)))
    case("洗牌末尾把游标 [0x4990B4] 清 0", w.emu.read32(FORTUNE_CURSOR), 0)
    case("★ 洗牌恰好消耗 37 次 rand()", w.emu.read32(RAND_COUNT), 37)
    w.emu.write32(RAND_COUNT, 0)
    w._call(FORTUNE_SHUFFLE, [], setup=lambda e: e.write32(RAND_VALUE, 7))
    w._call(FORTUNE_SHUFFLE, [], setup=lambda e: e.write32(RAND_VALUE, 7))
    case("  两次洗牌 = 74 次 rand()（每张牌一次）", w.emu.read32(RAND_COUNT), 74)

    section("[A10] 表事实：0x475EF0 共 37 项，**没有**空项 / 0xff 哨兵")
    entries = [w.emu.read32(FORTUNE_TABLE + i * 4) for i in range(37)]
    case("37 项全部非 0（= 都有事件体，不存在「未实现」指针）",
         all(v != 0 for v in entries), True)
    case("  末项（id 36）在代码段内（0x401000..0x4A0000）",
        0x401000 < entries[36] < 0x4A0000, True)

    section("[A11] ★★ 取牌循环整段驱动：不可行就抽下一张、游标恒前进")
    # deck = [0, 1, ...]；局面里只有一块 level=0 的自有地 ⇒ 0 不可行、1 可行
    w.clear().land(1, 1, 0)
    end = w.run_fortune_loop(0, [0, 1] + [0] * 35)
    logs = w.logs()
    case("  恰好调用事件体 1 次（跳过了 1 张不可行牌）", len(logs), 1)
    case("  被调的是 id 1（第 2 张）", logs[0]["ebp"] if logs else None, 1)
    case("★ 第 1 趟 = push 0（画字趟）", logs[0]["pass"] if logs else None, 0)
    case("  返回地址落在 0x44DC44 的调用点之后（0x44DC4B）",
         logs[0]["ret"] if logs else None, 0x44DC4B)
    case("★ 游标不管可行与否都前进：0 → 2", end, 2)

    w.clear().land(1, 1, 0)
    end = w.run_fortune_loop(36, [0] * 36 + [1])
    logs = w.logs()
    case("★★ 起始游标 36 + 37 张全扫一遍 ⇒ 回绕到第 37 张（id 1）", logs[0]["ebp"] if logs else None, 1)
    case("★★ 回绕后游标 = (36+1) % 37 = 0（钉死张数 = 37）", end, 0)

    # ★ 重映射必须一路传到事件体：deck 第 1 张 = 12，traffic=1 ⇒ 体应收到 13
    w.clear().player(0, vehicle=1)
    end = w.run_fortune_loop(0, [12, 1] + [0] * 35)
    logs = w.logs()
    case("★★ 判定器的重映射**传到了事件体**：牌面 12 + traffic 1 ⇒ 体收到 13",
         logs[0]["ebp"] if logs else None, 13)
    case("★ 且传参寄存器 eax 也是重映射后的号（不是牌面 12）",
         logs[0]["eax"] if logs else None, 13)
    case("  游标推进 1（第 1 张就可行，没跳牌）", end, 1)

    section("[A12] ★★ 两趟协议：第 2 趟在 `0x44DD51` 用**同一个（重映射后的）号**")
    logs = w.run_fortune_pass1(13)
    case("  第 2 趟 = push 1（生效趟）", logs[0]["pass"] if logs else None, 1)
    case("★ eax = id*4（表索引），ebp = id ⇒ 用的还是 13", logs[0]["ebp"] if logs else None, 13)
    case("  返回地址 = 0x44DD63（0x44DD5D 调用点之后）",
         logs[0]["ret"] if logs else None, 0x44DD63)
    case("  两趟是同一个表项：0x475EF0 + 13*4",
         (13 * 4, w.emu.read32(FORTUNE_TABLE + 13 * 4) != 0), (52, True))
    # id >= 33 支：表基址按 word[0x4991B8]*0x10 位移
    w.clear()
    logs = w.run_fortune_pass1(33, game_map=0)
    m0 = w.emu.read32(MARK)
    w.clear()
    logs1 = w.run_fortune_pass1(33, game_map=1)
    m1 = w.emu.read32(MARK)
    case("★ game_map=0 ⇒ id 33 走 0x475EF0+33*4（记录桩命中 1 次）",
         (len(logs), m0), (1, 0))
    case("★★ game_map=1 ⇒ 表项位移 4 项：走 0x475EF0+37*4（专用桩命中）",
         (len(logs1), m1), (0, 1))

    section("[A13] ★ rand：判定/取牌/两趟协议再走一遍，仍然一次都不摇")
    w.emu.write32(RAND_COUNT, 0)
    w.clear().land(1, 1, 1).hand(1, 0).stock(0, 0, 1).player(0, vehicle=1)
    for eid in (0, 5, 8, 10, 12, 14, 33, 36):
        w.gate_fortune_ret(eid)
    w.run_fortune_loop(0, [0, 1] + [0] * 35)
    w.run_fortune_pass1(1)
    case("判定 + 取牌 + 两趟 ⇒ rand 调用数 == 0", w.emu.read32(RAND_COUNT), 0)


# ======================================================================
#  [B] 新聞事件判定器 0x00448BE2
# ======================================================================
def section_b(w, mutate):
    print("\n" + "=" * 74)
    print("[B] 新聞 0x00448BE2 —— 744 B：可行性判定（入参按值，无重映射）")
    print("=" * 74)

    section("[B0] 函数边界 / 调用约定 / 返回编码")
    case("入口前 4 字节是 push ebx/esi/edi/ebp", w.emu.read(NEWS_GATE, 4).hex(), "53565755")
    case("0x448EC9 是 ret（0xC3）", w.emu.read8(0x448EC9), 0xC3)
    case("0x448ECA 已是下一个函数（0x53 56）", w.emu.read(0x448ECA, 2).hex(), "5356")
    case("尺寸 = 0x448ECA − 0x448BE2 = 744 B", NEWS_GATE_END - NEWS_GATE, 744)
    w.clear()
    ret, delta = w.gate_news(0)
    case("cdecl 单实参：esp_delta == 4", delta, 4)
    case("★ 入参是**值**不是指针：传 0 不 deref（能正常返回）", ret, 0)
    seen = set()
    w.clear().prison = 1
    for eid in range(0, 38):
        seen.add(w.gate_news_ret(eid))
    w.clear().land(1, 1, 1).player(0, vehicle=2)
    for eid in range(0, 38):
        seen.add(w.gate_news_ret(eid))
    case("id 0..37 两种局面下返回值集合 ⊆ {0,1}", sorted(seen), [0, 1])

    section("[B1] 事件 0/1（监狱）与 2/3（医院）—— ★ 读的是 **dword**（槽 0..3 玩家）")
    w.clear()
    case("监狱表全 0 ⇒ id 0 不可行", w.gate_news_ret(0), 0)
    w.prison = 1
    case("监狱槽 0 非 0 ⇒ id 0 可行", w.gate_news_ret(0), 1)
    case("★ 同一局面 id 1 也可行（0/1 同判据）", w.gate_news_ret(1), 1)
    w.clear()
    w.prison = 0x01000000
    case("监狱槽 3 非 0（dword 高位）⇒ id 0 可行", w.gate_news_ret(0), 1)
    w.clear()
    w.emu.write8(PRISON_TABLE + 4, 1)          # ★ 槽 4 在**下一个 dword**（0x496B34）
    case("★★ 只有**槽 4**（地图物件位）非 0 ⇒ id 0 **不可行**（dword 只覆盖槽 0..3）",
         w.gate_news_ret(0), 0)
    w.clear()
    w.prison = 0x01000000                      # 只有槽 3
    case("  只把槽 3 置 1 ⇒ 可行（确认读的确实是 0..3）", w.gate_news_ret(0), 1)
    w.clear()
    case("医院表全 0 ⇒ id 2 不可行", w.gate_news_ret(2), 0)
    w.hospital = 1
    case("医院槽 0 非 0 ⇒ id 2 可行", w.gate_news_ret(2), 1)
    case("★ 同一局面 id 3 也可行（2/3 同判据）", w.gate_news_ret(3), 1)
    w.clear()
    w.emu.write8(HOSPITAL_TABLE + 4, 1)
    case("★★ 只有医院槽 4 非 0 ⇒ id 2 不可行（dword）", w.gate_news_ret(2), 0)
    w.clear()
    w.prison = 1
    case("★ 监狱非 0 不影响医院判据 id 2", w.gate_news_ret(2), 0)

    section("[B2] 事件 4/5/15 —— 有任何**已建房**的地產**或**設施（level 0x1a ≠ 0）")
    w.clear()
    for eid in (4, 5, 15):
        case(f"空局面 id {eid} 不可行", w.gate_news_ret(eid), 0)
    w.clear().land(1, 0, 3)
    for eid in (4, 5, 15):
        case(f"一块 3 级地產 ⇒ id {eid} 可行", w.gate_news_ret(eid), 1)
    w.clear().fac(1, 0, 2)
    case("★★ 只有**設施**已建房（无地產）⇒ id 4 可行（第二张表要真扫）",
         w.gate_news_ret(4), 1)
    case("★★ 同上 ⇒ id 15 也可行", w.gate_news_ret(15), 1)
    w.clear().land(0, 0, 5).land(1, 0, 0)
    case("★★ 地產记录 0 已建房**不算**（循环 i=1..N）", w.gate_news_ret(4), 0)
    w.clear().fac(0, 0, 5).fac(1, 0, 0)
    case("★★ 設施记录 0 已建房**不算**", w.gate_news_ret(4), 0)

    section("[B3] 事件 7 —— 有任何**无主**地產 / 設施（owner 0x19 == 0）")
    w.clear().land(1, 1, 0)
    case("全部有主 ⇒ id 7 不可行", w.gate_news_ret(7), 0)
    w.land(2, 0, 0)
    case("一条无主地產 ⇒ id 7 可行", w.gate_news_ret(7), 1)
    w.clear().fac(1, 0, 0)
    case("★ 只有无主設施 ⇒ id 7 可行", w.gate_news_ret(7), 1)
    w.clear().land(0, 0, 0).land(1, 1, 0)
    case("★★ 记录 0 的无主不算", w.gate_news_ret(7), 0)
    w.clear()
    case("  一张表都没有 ⇒ id 7 不可行", w.gate_news_ret(7), 0)

    section("[B4] 事件 8/9/12 —— 有任何**有主**地產 / 設施")
    w.clear().land(1, 0, 0)
    for eid in (8, 9, 12):
        case(f"全部无主 ⇒ id {eid} 不可行", w.gate_news_ret(eid), 0)
    w.land(1, 2, 0)
    for eid in (8, 9, 12):
        case(f"一条有主地產 ⇒ id {eid} 可行", w.gate_news_ret(eid), 1)
    w.clear().fac(1, 3, 0)
    case("★ 只有有主設施 ⇒ id 8 可行", w.gate_news_ret(8), 1)
    w.clear().land(0, 1, 0).land(1, 0, 0)
    case("★★ 记录 0 的有主不算", w.gate_news_ret(8), 0)

    section("[B5] 事件 10/13 —— 在局玩家（`byte[+0x15] != 0`）的 12 支持股")
    w.clear()
    for eid in (10, 13):
        case(f"无人持股 ⇒ id {eid} 不可行", w.gate_news_ret(eid), 0)
    w.clear().stock(0, 0, 1)
    case("玩家 0 持第 0 支 ⇒ id 10 可行", w.gate_news_ret(10), 1)
    case("玩家 0 持第 0 支 ⇒ id 13 可行", w.gate_news_ret(13), 1)
    w.clear().stock(0, 11, 4)
    case("★ 第 11 支也算（循环 0..11）", w.gate_news_ret(10), 1)
    w.clear().stock(3, 5, 2)
    w.player(3, who=0)
    case("★★ 持股者 who_plays == 0（不在局）⇒ 不算", w.gate_news_ret(10), 0)
    w.player(3, who=1)
    case("  同一格 who_plays != 0 ⇒ 算", w.gate_news_ret(10), 1)
    w.clear().stock(2, 3, 1).sole(2)
    w.num = 2
    case("★ 上界 = [0x499114]：num=2 时玩家 2 不在扫描范围", w.gate_news_ret(10), 0)
    w.num = 4
    case("  num=4 时同一局面 ⇒ 算", w.gate_news_ret(10), 1)
    w.clear()
    w.stocks_hi[(1, 2)] = 0x12345678
    case("★★ 只读每槽 **+0**：+4 有值 ⇒ 不可行", w.gate_news_ret(10), 0)
    w.clear()
    w.emu.write32(STOCK_HOLD + 1 * 0x60 + 12 * 8, 9)
    case("★★ 第 12 槽（越界）**不读**", w.gate_news_ret(10), 0)
    w.clear().stock(1, 0, 1)
    w.player(1, who=0x10)
    case("★★★ `who_plays = 0x10`（高位、低 2 位为 0）⇒ 原版**算**（整字节 != 0）",
         w.gate_news_ret(10), 1)

    section("[B6] 事件 16/17 —— 在局玩家的 `traffic_method`（+0x11）")
    w.clear().sole(0, who=0, vehicle=0)
    case("没有在局玩家 ⇒ id 16 不可行", w.gate_news_ret(16), 0)
    case("没有在局玩家 ⇒ id 17 不可行", w.gate_news_ret(17), 0)
    w.clear().sole(0, who=1, vehicle=0)
    case("在局 + vehicle=0 ⇒ id 16 可行", w.gate_news_ret(16), 1)
    case("在局 + vehicle=0 ⇒ id 17 不可行", w.gate_news_ret(17), 0)
    w.clear().sole(0, who=1, vehicle=2)
    case("在局 + vehicle=2 ⇒ id 16 不可行", w.gate_news_ret(16), 0)
    case("在局 + vehicle=2 ⇒ id 17 可行", w.gate_news_ret(17), 1)
    w.clear().sole(0, who=0, vehicle=0)
    case("★ 不在局（who=0）即使 vehicle=0 也不算", w.gate_news_ret(16), 0)
    w.clear().sole(0, who=0x20, vehicle=0)
    case("★★★ `who_plays = 0x20` ⇒ 原版**算**（整字节 != 0，非 isAlive）",
         w.gate_news_ret(16), 1)
    w.clear().player(3, who=1, vehicle=1)
    w.num = 2
    case("★ 上界 = [0x499114]：num=2 时玩家 3 不算", w.gate_news_ret(17), 0)

    section("[B7] 事件 28 —— 12 支股票的 `f6`（`0x496986 + i*0x24`）")
    w.clear()
    case("全 0 ⇒ 不可行", w.gate_news_ret(28), 0)
    w.clear().f6[0] = 1
    case("第 0 支 f6 非 0 ⇒ 可行", w.gate_news_ret(28), 1)
    w.clear().f6[11] = 0xFF
    case("★ 第 11 支（最后一格）也算", w.gate_news_ret(28), 1)
    w.clear()
    w.emu.write8(STOCK_F6 + 12 * 0x24, 1)
    case("★★ 第 12 格（越界）**不读**（上界 12）", w.gate_news_ret(28), 0)

    section("[B8] 事件 29 —— 企業 owner ≠ 0 且 `0x40D73F(owner−1) == 1`（真跑）")
    w.clear()
    case("没有企業 ⇒ 不可行", w.gate_news_ret(29), 0)
    w.comm(1, 1, 0)
    case("企業 1 有主（玩家 0 在局且无阻碍）⇒ 可行", w.gate_news_ret(29), 1)
    w.clear().comm(1, 1, 0).player(0, who=0)
    case("★ owner−1 的玩家不在局 ⇒ 不可行（0x40D73F 真跑）", w.gate_news_ret(29), 0)
    w.clear().comm(1, 1, 0).player(0, who=1, block=1)
    case("★ owner−1 有阻碍计数（+0x32 != 0）⇒ 不可行", w.gate_news_ret(29), 0)
    w.clear().comm(1, 0, 0).player(0, who=1)
    case("★ 企業无主（owner 0）⇒ 跳过 ⇒ 不可行", w.gate_news_ret(29), 0)
    w.clear().comm(0, 1, 0).comm(1, 0, 0)
    case("★★ 企業记录 0 有主**不算**（循环 i=1..N）", w.gate_news_ret(29), 0)
    w.clear().comm(2, 2, 0).player(1, who=1)
    case("  owner=2 ⇒ 查玩家 1 ⇒ 可行（1 基 owner）", w.gate_news_ret(29), 1)

    section("[B9] 事件 35 —— 企業 `dword[+0x28] > 0x2710`（严格大于、有符号）")
    w.clear()
    case("没有企業 ⇒ 不可行", w.gate_news_ret(35), 0)
    w.comm(1, 0, 10000)
    case("★ 恰好 10000 ⇒ **不**大于 ⇒ 不可行", w.gate_news_ret(35), 0)
    w.comm(1, 0, 10001)
    case("  10001 ⇒ 可行", w.gate_news_ret(35), 1)
    w.clear().comm(1, 0, -1)
    case("★ +0x28 是**有符号**比较：−1 ⇒ 不可行", w.gate_news_ret(35), 0)
    w.clear().comm(0, 0, 99999).comm(1, 0, 10000)
    case("★★ 企業记录 0 的天价**不算**", w.gate_news_ret(35), 0)
    w.clear().comm(3, 0, 20000)
    case("  第 3 条企業命中（不是只看第一条）", w.gate_news_ret(35), 1)

    section("[B10] default 支：6 / 11 / 14 / 18..27 / 30..34 / 36+ 一律可行")
    w.clear()
    for eid in (6, 11, 14, *range(18, 28), *range(30, 35), 36, 40, 255):
        case(f"空局面 id {eid} ⇒ 1", w.gate_news_ret(eid), 1)

    section("[B11] rand：新聞判定器一次都不摇")
    w.emu.write32(RAND_COUNT, 0)
    for eid in range(0, 38):
        w.gate_news_ret(eid)
    w.clear().comm(1, 1, 99999).f6[0] = 1
    w.stock(0, 0, 3).land(1, 1, 1).fac(1, 1, 1).player(0, vehicle=0)
    for eid in range(0, 38):
        w.gate_news_ret(eid)
    case("id 0..37 × 两种局面 ⇒ rand 调用数 == 0", w.emu.read32(RAND_COUNT), 0)

    section("[B12] 牌堆：洗牌 `0x448B81` ⇒ 36 张、游标 `0x4990E0` 清 0、摇 36 次")
    w.emu.write32(RAND_COUNT, 0)
    w._call(NEWS_SHUFFLE, [], setup=lambda e: e.write32(RAND_VALUE, 12345))
    deck = list(w.emu.read(NEWS_DECK, 36))
    case("洗出的 36 字节是 0..35 的一个排列", sorted(deck), list(range(36)))
    case("洗牌末尾把游标 [0x4990E0] 清 0", w.emu.read32(NEWS_CURSOR), 0)
    case("★ 洗牌恰好消耗 36 次 rand()", w.emu.read32(RAND_COUNT), 36)
    entries = [w.emu.read32(NEWS_TABLE + i * 4) for i in range(36)]
    case("0x475E24 的 36 项全部非 0（没有「未实现」空指针）",
         all(v != 0 for v in entries), True)
    case("  新闻张数判据的立即数是 0x24（`0x44B7D4 cmp edx,0x24`）",
         w.emu.read(0x44B7D4, 3).hex(), "83fa24")
    case("  命運张数判据的立即数是 0x25（`0x44DCB7 cmp esi,0x25`）",
         w.emu.read(0x44DCB7, 3).hex(), "83fe25")

    section("[B13] ★★ 取牌循环整段驱动（0x44B718 → 0x44B7E9）")
    w.clear()
    end = w.run_news_loop(0, [0, 6] + [0] * 34)
    logs = w.logs()
    case("  恰好调用事件体 1 次（跳过 1 张不可行）", len(logs), 1)
    case("  被调的是 id 6（默认可行的那张）", logs[0]["ebx"] if logs else None, 6)
    case("★ 第 1 趟 = push 0", logs[0]["pass"] if logs else None, 0)
    case("  返回地址 = 0x44B7C4（0x44B7BD 调用点之后）",
         logs[0]["ret"] if logs else None, 0x44B7C4)
    case("★ 游标恒前进：0 → 2", end, 2)
    w.clear()
    end = w.run_news_loop(33, [0] * 35 + [6])
    logs = w.logs()
    case("★★ 起始游标 33、前 3 张不可行 ⇒ 命中第 36 格 id 6", logs[0]["ebx"] if logs else None, 6)
    case("★★ 回绕：(35+1) % 36 = 0（钉死张数 = 36）", end, 0)

    section("[B14] ★★ 两趟协议：第 2 趟在 `0x44B86F` 用同一个号（push 1）")
    logs = w.run_news_pass1(6)
    case("  第 2 趟 = push 1", logs[0]["pass"] if logs else None, 1)
    case("  eax = id（表索引）⇒ 6", logs[0]["eax"] if logs else None, 6)
    case("  返回地址 = 0x44B87C", logs[0]["ret"] if logs else None, 0x44B87C)
    case("  两趟同一表项 0x475E24+6*4 非 0",
         w.emu.read32(NEWS_TABLE + 6 * 4) != 0, True)

    section("[B15] ★ 整副牌都不可行 ⇒ 原版**死循环**（remake 改成返回 −1，见 deck.ts:120）")
    w.clear()
    spun = False
    end = None
    try:
        end = w.run_news_loop(0, [0] * 36, timeout=20000)
    except RuntimeError:
        spun = True
    case("新聞：全不可行 ⇒ eval_block 停在 20000 条指令（仍在转）", spun, True)
    w.clear()
    spun = False
    try:
        end = w.run_fortune_loop(0, [0] * 37, timeout=20000)
    except RuntimeError:
        spun = True
    case("命運：全不可行 ⇒ 同样死循环", spun, True)


def main():
    mutate = os.environ.get("EVENT_DISPATCH_MUTATE", "").strip().upper()
    w = World()
    if mutate == "A":
        w.emu.patch(0x44BB5C, b"\x83\xFB\x0D")     # cmp ebx,0xc → 0xd
        print("★ 可证伪注入 A：0x44BB5C 立即数 0x0c → 0x0d")
    elif mutate == "B":
        w.emu.patch(0x448C9B, b"\x60")             # [0x496b30] → [0x496b60]
        print("★ 可证伪注入 B：0x448C9B 位移 0x30 → 0x60（监狱表改读医院表）")

    section_a(w, mutate)
    section_b(w, mutate)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    if mutate:
        print(f"（可证伪注入 {mutate} 生效：{len(RESULTS) - n_ok} 条转红）")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
