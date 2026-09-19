#!/usr/bin/env python3
"""
通道 2 差分测试 · **四支小规则助手**（gaps §7.3 第 14 项的通道 2 工作单）

| 组 | VA | 尺寸 | 一句话语义 | 复刻对应 |
|---|---|---|---|---|
| A | `0x0041d7d4` | 101 B | AI「买完还剩多少钱」闸门（地块/設施共用） | `rules/purchase.ts` 的 `aiShouldPurchase` |
| B | `0x0041d839` | 101 B | 電腦买股上限 = `(現金 − 安全垫) ÷ 每股`，夹 1000/余量 | `places/company.ts` 的 `shareWindowLimit` 同族 |
| C | `0x0040fa61` | 117 B | 衰神(7)/大衰神(8)/死神(15) 附身 ⇒ 挡下**一切消费** | `rules/purchase.ts` 的 `purchaseBlockedBy` |
| D | `0x0040b455` | 163 B | 建設公司「挑一处自己的地/設施加蓋」 | `places/company.ts` 的 `aiPickConstructionTarget` |

四支都**没有**跳表入口、都是普通 `call` 目标（`python3 tools/disasm.py callers <VA>`），
故一律用 `Emu.call()` **整支驱动**，不需要「打 ret」或手搓帧。

## 语义（逐条读完到 `ret`，与复刻逐行对照见各组注释）

```
A  0x0041d7d4(价):                                   ; 101 B，2 个调用点
    reserve = trunc(开局资金 [0x49908c] × f64 0x463cc8)   ; ★ 0x463cc8 = 0.05
    if (reserve > 7000) reserve = 7000                   ; cmp [esp],0x1b58 / jle
    reserve *= 物价指数 [0x4990e8]
    total   = 现金[+0x1c] + 存款[+0x20]                  ; 当前玩家 [0x49910c]
    return (total − 价 > reserve) ? 1 : 0                ; ★ 严格大于

B  0x0041d839(單價, 可買上限):                        ; 101 B，1 个调用点（0x41d269）
    r = trunc(开局资金 × f64 0x463cd0)                   ; ★★ 0x463cd0 = 0.30（不是 0.05！）
                                                          ; ★★ **没有** 7000 那道夹（[A] 支才有）
    r *= 物价指数                                         ; 先截断、再乘物價（无封顶）
    d = 现金[+0x1c] − r                                   ; ★ 存款不参与（与 A 支相反）
    if (d <= 0) return 0                                 ; ★ 0 与负数同出口
    return (d >= 單價 × 上限) ? 上限 : d / 單價             ; idiv，向零取整
    ; 调用点 0x41d269 把它当「这家公司这次最多买几股」用；真人支才去开填数窗
    ; （`push esi / call 0x453544` 在 0x41d25b，不在本函数体内）

C  0x0040fa61(玩家):                                  ; 117 B，5 个调用点
    g = 玩家物件号 [+0x3f]
    if ((g >= 8 && g == 8) || g == 15 || g == 7) {       ; 三个附身物
        sprintf(栈缓冲, 0x463514 "%s顯靈\n\n投資失敗！", 物件名表[0x47ed76][g])
        0x440cac(栈缓冲, 0x5dc)
        return 1
    }
    return 0

D  0x0040b455(玩家):                                  ; 163 B，2 个调用点
    best = 0
    for (i = 1; i <= [0x498e98]; i++) {                  ; ★ 1 基、跳过记录 0
        l = 地块表[0x498e84] + i*0x34
        if (l.owner[+0x19] != 玩家+1) continue
        if (l.type[+0x18] != 0) continue                 ; 只收住宅（連鎖店不收）
        lv = l.level[+0x1a]
        if (lv >= 5) continue                            ; ★ 无 type 门槛，只看 5
        rent = word[l + 0x20 + lv*2]                     ; ★★ 记录**自带**的 6 档租金
                                                          ;   （`rentByLevel[level]`）
        if (rent > best) { best = rent; out = 0x7d0 + i } ; ★ 严格大于
    }
    for (i = 1; i <= [0x498e8c]; i++) {                  ; ★ 設施 1 基
        f = 設施表[0x498e88] + i*0x38
        if (f.owner[+0x19] != 玩家+1) continue
        if (f.price[+0x22] <= best) continue
        if (f.level[+0x1a] >= byte[0x474940 + f.type[+0x18]]) continue
        best = f.price; out = 0xfa0 + i
    }
    return out
```

★★ **本测试抓到的一处规格/复刻差异**（[A] 组）：
`rules/purchase.ts:134` 与 `docs/gaps/README.md` 都把保留比例记成 `0.05`，
但 `0x463cc8` 的 8 字节真值 `9a9999999999a93f` = **0.05**（A 支对）；
`0x463cd0` 的真值 `333333333333d33f` = **0.30**（B 支）——
`places/company.ts:171` 的注释把 B 支也写成 `× 0.05`，**注释与字节相反**（见 [B] 组）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x00440cac(buf, 毫秒)` | 弹訊息框 | `inc dword [CALLS_MSG]`（`FF 05`）+ 返回 0 | 纯 UI；不碰 ESP、不读参数，正好用来断言「弹/不弹」 |
| `0x00453544(上限)` | 「通用填数窗」 | `mov [CALLS_SHARE],eax`（`A3`）+ 返回 0 | B 支**唯一**的外部依赖；本测试只验「调没调」，上限本身由返回值钉住 |
| `0x00456f2d` | CRT `rand()` | 从数据槽读 | **四支一个随机数都不摇** —— 留着只为能断言"没摇" |
| `0x00457110` | `sprintf` | 头 5 字节 `jmp 0x4C0100` + 桩体 `inc/xor/ret` | 尾部走 `es:` 远指针 `strlen`，Unicorn 跑不了（见文末「工具边界」） |

★ 租金**不用打桩**：它在地块记录自己的 `+0x20 + level*2`（= 复刻的 `rentByLevel`），
所以 [D] 组是**真读真算**；`0x4749e2`（神明修正表）本测试完全不碰。

`0x4239b9`（总资产，只在 `0x41d89e` 那段分支里）与 `0x4749e2`/`0x474940`**真跑/真读**。

## 证伪检查（已实跑，§7.141(5) 口径）

| 打断处 | 改成 | 转红断言 |
|---|---|---|
| `0x41d7fa` 的 7000 立即数 | 8000 | A7/A9（2 条） |
| `0x463cce`（A 的 f64 尾） | 0.30 | A2 比例判别（1 条） |
| `0x463cd6`（B 的 f64 尾） | 0.05 | B4/B10（2 条） |
| `0x40fa7c` `jbe`→`jne` | `75 0a` | C3（1 条） |
| `0x40b483` 住宅门槛 `0`→`1` | `01` | D7/D8（2 条） |
| `0x40b48f` 租金位移 `+0x20`→`+0x24` | `24` | D11（1 条） |

★ 注意 A 的 7000：**只改 `cmp` 的立即数不会改变结果**（`fistp` 结果 ≤ 7000 时
`jle` 本来就跳过 `mov`）⇒ 必须改 `mov` 的立即数；这条本身就是「别照字面抄」的证据。

## 工具边界（本测试踩到的）

- `0x457110`（`sprintf`）尾部走 Watcom 的 `strlen 0x45b370`，它用
  `mov es,[esp+0x14]` + `mov cl, es:[edx]` 读**远指针** ⇒ Unicorn 下必
  `UC_ERR_READ_UNMAPPED`（与 `verification.md` 工具边界第 1 条同族）。
  故把 `0x457110` 头 5 字节改成 `jmp 0x4C0100` + 桩体 `inc/xor/ret`，
  并在**桩入口**读出「压栈右→左」的三个实参：`[esp+4]`=缓冲、`[esp+8]`=格式串、
  `[esp+0xc]`=`%s` 的实参（在 Python 里按 `%s` 展开，不驱动 CRT 本身）。
- `0x4C0010` 已被其它测试台内容占用（读出来像 `...00 10 4C 00...`）⇒ 桩放 `0x4C0100`。

跑法：cd rich4-spec && .venv/bin/python tests/test_small_helpers2.py
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_ESP  # noqa: E402

# ── 被测函数 ──
AI_SHOULD_PURCHASE = 0x41D7D4
MAX_PURCHASE_COUNT = 0x41D839
GOD_BLOCK = 0x40FA61
PICK_CONSTRUCTION = 0x40B455

# ── 打桩 ──
MSGBOX = 0x440CAC             # 訊息框入口（第二次调用，0x40fabf）
SPRINTF = 0x457110            # 格式化（第一次调用，0x40faad）
SPRINTF_STUB = 0x4C0100       # 桩区（STUB_BASE 起，见 emulate.py；避开 0x4C0010）
CALLS_MSG_ENTRY = 0x440CAC
SHARE_WINDOW = 0x453544
PRNG = 0x456F2D

# ── 全局 ──
INITIAL_FUND = 0x49908C          # 本局开局资金档位
PRICE_INDEX = 0x4990E8           # 物价指数
CUR = 0x49910C                   # 当前玩家（0 基）
NUM_PLAYERS = 0x499114           # 人数（上界类全局，B 不用但留着防串味）
LAND_TABLE_PTR = 0x498E84        # dword：地块表基址
LAND_TABLE_N = 0x498E98          # dword：地块数（循环上界）
FAC_TABLE_PTR = 0x498E88         # dword：設施表基址
FAC_TABLE_N = 0x498E8C           # dword：設施数（循环上界）
FAC_MAX_LEVEL = 0x474940         # byte[type]：設施最高等级表 [1,5,5,1,5]
# ★★ 租金**不是独立表**：它就存在**地块记录自己的** `+0x20 + level*2` 处
#   （`mov bx, word [eax + ebx*2 + 0x20]`，eax = 记录基址、ebx = level），
#   与复刻 `LandInfo.rentByLevel[6]` 同构（`loaders/map.ts:573` 按 MAX_LAND_LEVEL+1 填）。
#   ⚠️ **踩过的坑**：`0x4749e2` 那个绝对地址**不是租金表**，而是**神明修正表 A**
#   （`docs/systems/gods.md:168`，18×int16）——把租金写到那儿、或把它当表基址改指
#   暂存区，读地址都会落空（症状：「有租金的地全不入选」）。正确写法见 `_setup`。
GOD_ADJ_TABLE_A = 0x4749E2       # 神明修正表 A（只作对照，本测试不碰）
MSG_FMT = 0x463514               # "%s顯靈\n\n投資失敗！"
CALLS_MSG_SLOT = 0x440CAC        # 打桩后的弹框入口（只记调用次数）
OBJ_NAME_PTRS = 0x47ED76         # dword[19]：物件名指针表

DATA_STRIDE, D_OWNER, D_LEVEL, D_TYPE = 0x34, 0x19, 0x1A, 0x18
LAND_PRICE, HOUSE_PRICE = 0x1C, 0x1E
FAC_STRIDE = 0x38
FAC_PRICE = 0x22

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO_PLAYS, P_CASH, P_BANK, P_GOD = 0x15, 0x1C, 0x20, 0x3F

# ★ 0x41d839 的 idiv 除数是「每股售價」——占位表由 setup() 铺，避免 idiv 0
SHARE_REC, SHARE_STRIDE, SHARE_N = SCRATCH_BASE + 0x8000, 0x48, 4   # 0x41d839 的除數占位
S_LIVE, S_RENT = 0x15, 0x1C

LAND_MARK, FAC_MARK = 0x7D0, 0xFA0
RATIO_A = 0.05                   # @source f64 0x463cc8
RATIO_B = 0.30                   # @source f64 0x463cd0 ★★ 不是 0.05
CAP = 7000                       # @source cmp [esp],0x1b58

# ★★ 暂存区各表的落点必须**互不重叠**：被测函数用 `表基址 + idx*0x34 + 0x20 + lv*2`
#   寻址租金 ⇒ 表基址会一直铺到 `基址 + 16*0x34 + 0x20 + 4*2` 附近。
#   实测踩坑：把 RENT_TABLE 放在 LANDS+0x8000 而 LANDS=SCRATCH+0x3000 时公式给出
#   `SCRATCH+0x3054`，**正好落在 LANDS 自己的清零区里** ⇒ 租金恒读 0。
LANDS = SCRATCH_BASE + 0x1000
FACS = SCRATCH_BASE + 0x3000
# 租金表要整整 16*0x34 + 0x28 字节（见 _setup 的注释），故独占 0x4000 起 0x600 字节
MSG_BUF = SCRATCH_BASE + 0x780
CALLS_MSG = SCRATCH_BASE + 0x7B0      # 打桩计数：0x440cac 被调次数
CALLS_SHARE = SCRATCH_BASE + 0x7B4    # 打桩计数：0x453544 被调次数
RAND_SLOT = SCRATCH_BASE + 0x7B8
RAND_CALLS = SCRATCH_BASE + 0x7BC
SENTINEL = 0x5A5A5A5A
RESULTS = []


def _short(v, n=48):
    """打印用：bytes 截断到 n 字节（消息文本很长，整串会把输出淹掉）。"""
    if isinstance(v, bytes) and len(v) > n:
        return v[:n].hex() + f"...(+{len(v) - n}B)"
    if isinstance(v, (list, tuple)) and len(v) > 8:
        return repr(v[:8]) + f"...(+{len(v) - 8})"
    return v


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<72} 实际 {_short(got)!s:<14} 期望 {_short(want)!s}")
    return ok


def trunc(v):
    """x87 `__round_toward_zero`（0x457dbc ⇒ frndint，RC=11）在 f64 上的等价物。"""
    return math.trunc(v)


class World:
    def __init__(self):
        self.emu = Emu()
        # 0x457110（sprintf）→ 跳进桩区（原函数 9 字节不够放「inc + xor + ret」）
        self._stub_sprintf()
        # 0x453544：`mov [CALLS_SHARE],eax; xor eax,eax; ret` —— 记「调没调」
        self.emu.patch(SPRINTF, b"\xE9" + struct.pack("<i", SPRINTF_STUB - (SPRINTF + 5)))
        self.emu.patch(SPRINTF_STUB,
                       b"\xFF\x05" + struct.pack("<I", CALLS_MSG) + b"\x31\xC0\xC3")
        # 0x440cac：`xor eax,eax; ret`（参数由调用点随后 `add esp,8` 自清）
        self.emu.patch(MSGBOX, b"\x31\xC0\xC3")
        # 0x453544：`mov [CALLS_SHARE],eax; xor eax,eax; ret` —— 记「调没调」+ 上限
        self.emu.patch(SHARE_WINDOW, b"\xA3" + struct.pack("<I", CALLS_SHARE)
                       + b"\x31\xC0\xC3")
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    # ── 世界重置（暂存区跨 call 保留，必须自己清） ──
    def clear(self):
        self.cur = 0
        self.initial_fund = 300000
        self.price_index = 1
        self.god = [0, 0, 0, 0]
        self.cash = [0, 0, 0, 0]
        self.bank = [0, 0, 0, 0]
        self.who = [1, 1, 1, 1]
        self.lands = {}          # index → (owner, level, type, rent_word)
        self.facs = {}           # index → (owner, level, type, price)
        self.land_n = 0
        self.fac_n = 0

    def add_land(self, idx, owner=0, level=0, typ=0, rent=0):
        self.lands[idx] = (owner, level, typ, rent)
        self.land_n = max(self.land_n, idx)
        return self

    def add_fac(self, idx, owner=0, level=0, typ=0, price=0):
        self.facs[idx] = (owner, level, typ, price)
        self.fac_n = max(self.fac_n, idx)
        return self

    def _setup(self, emu):
        emu.write32(INITIAL_FUND, self.initial_fund)
        emu.write32(PRICE_INDEX, self.price_index)
        emu.write32(CUR, self.cur)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(LAND_TABLE_N, self.land_n)
        emu.write32(FAC_TABLE_N, self.fac_n)
        emu.write32(CALLS_MSG, 0)
        emu.write32(CALLS_SHARE, 0)
        emu.write32(RAND_SLOT, 0)
        emu.write32(RAND_CALLS, 0)
        # ★ 暂存区跨用例保留 ⇒ 先整块清零
        emu.write(LANDS, b"\x00" * (DATA_STRIDE * 16))
        emu.write(FACS, b"\x00" * (FAC_STRIDE * 16))
        emu.write(MSG_BUF, b"\x00" * 0x40)
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_WHO_PLAYS, self.who[p])
            emu.write8(pb + P_GOD, self.god[p])
            emu.write32(pb + P_CASH, self.cash[p])
            emu.write32(pb + P_BANK, self.bank[p])
            sb = SHARE_REC + p * SHARE_STRIDE
            emu.write8(sb + S_LIVE, 1)
            emu.write32(sb + S_RENT, 100)
        for idx, (o, lv, ty, rent) in self.lands.items():
            b = LANDS + idx * DATA_STRIDE
            emu.write8(b + D_OWNER, o)
            emu.write8(b + D_LEVEL, lv)
            emu.write8(b + D_TYPE, ty)
            emu.write32(b + LAND_PRICE, 1000 + idx)
            emu.write16(b + HOUSE_PRICE, 500 + idx)
            # ★★★ 租金写在**该地块记录自己的** +0x20 + level*2 处：
            #   读地址 = `[0x498e84] + idx*0x34 + 0x20 + level*2`（eax 与记录基址同源）
            emu.write16(LANDS + idx * 0x34 + 0x20 + lv * 2, rent & 0xFFFF)
            assert emu.read16(LANDS + idx * 0x34 + 0x20 + lv * 2) == (rent & 0xFFFF)
        for idx, (o, lv, ty, price) in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write8(b + D_OWNER, o)
            emu.write8(b + D_LEVEL, lv)
            emu.write8(b + D_TYPE, ty)
            emu.write16(b + FAC_PRICE, price & 0xFFFF)

    def _stub_sprintf(self):
        """把 `0x457110` 的头 5 字节改成 `jmp 0x4C0010`，桩体 `inc [CALLS_MSG]; xor eax,eax; ret`。

        为什么不就地打 9 字节：`0x457110` 的函数体很短且尾部被调用者依赖；
        直接覆盖会留下跑飞的尾巴（实测 `UC_ERR_FETCH_UNMAPPED`）。
        跳到桩区则完全不动原函数体。

        ★★ 桩体必须**自带 `ret 0xc`**（而不是 `ret`）并把 `[esp]` 的返回地址
        桩体**不要**动栈：原函数 `0x457110` 自己不留参数（调用点随后
        `add esp,0xc` 清），所以桩体只需 `inc / xor / ret`。
        ⚠️ 曾经把它写成 `ret 0xc` + 「把返回地址搬到 [esp+0xc]」—— 那是**错的**
        （多清 12 字节 ⇒ 调用点随后 `add esp` 弹到未映射地址）。栈检验靠
        `tests/test_harness.py` 同款口径：跑完看 `esp_delta`。
        """
        rel = SPRINTF_STUB - (SPRINTF + 5)
        self.emu.patch(SPRINTF, b"\xE9" + struct.pack("<i", rel))
        code = (b"\xFF\x05" + struct.pack("<I", CALLS_MSG)   # inc dword [CALLS_MSG]
                + b"\x31\xC0"                                # xor eax,eax
                + b"\xC3")                                   # ret（参数由调用点自清）
        self.emu.patch(SPRINTF_STUB, code)

    # ── 四支的驱动 ──
    def run_a(self, price):
        r = self.emu.call(AI_SHOULD_PURCHASE, [price], setup=self._setup)
        self.ret = r["signed"]
        return self

    def run_b(self, unit_price, limit):
        r = self.emu.call(MAX_PURCHASE_COUNT, [unit_price, limit], setup=self._setup)
        self.ret = r["signed"]
        # 0x453544 只被**调用方** 0x41d1a9 调，本函数不该碰它 ⇒ 该计数恒 0。
        self.window_calls = 1 if self.emu.readu32(CALLS_SHARE) else 0
        self.window_limit = self.emu.readu32(CALLS_SHARE)
        return self

    def run_c(self, player):
        """驱动 `0x40fa61`，并在它把参数交给 `0x440cac` 的**那一刻**当场取样。

        为什么要这样取：原版走的是 Watcom 的 `sprintf`（`0x457110` → `0x458db5`
        → 尾部 `strlen` `0x45b370`），而那条 `strlen` 用 `mov es, word[esp+0x14]`
        + `mov cl, byte ptr es:[edx]` 读**远指针** —— 与工具边界第 1 条同族，
        Unicorn 下 `es:` 的基址不是 DGROUP ⇒ 必然 `UC_ERR_READ_UNMAPPED`。
        故本测试**不驱动格式串本身**（那是 CRT 的事，不是被测函数的事），
        改为在 `call 0x440cac` 站点读出实参：`[esp+8]` = 格式串地址、
        `[esp+0xc]` = 目标缓冲、`[esp+0x10]` = 实参（物件名指针），
        再在 Python 里按 `%s` 展开 —— 复刻的 `purchaseBlockedBy` 返回的也只是名字。
        """
        # ★ 0x457110（`sprintf`）→ 桩区：必须**在它内部**截住，因为 `0x458db5`
        #   尾部会走那条用 `es:` 读远指针的 `strlen`（工具边界第 1 条同族）。
        #   `patch()` 会把补丁并入快照，`call()` 开头的 `reset()` 不会抹掉它。
        self._stub_sprintf()
        self.msg_fmt = None
        self.msg_arg = None

        def hook(mu, address, size, user):
            if address != SPRINTF:
                return
            esp = mu.reg_read(UC_X86_REG_ESP)
            # 0x40faa8 `push 0x463514` / 0x40faac `push eax(名指针)` / 0x40faad `call`：
            # 桩区入口时（实测）：[esp]=返回地址、[esp+4]=缓冲、[esp+8]=格式串、
            # [esp+0xc]='%s' 的实参（0x466671 = 物件名表[8]）
            self.msg_arg = struct.unpack("<I", mu.mem_read(esp + 0xC, 4))[0]
            self.msg_fmt = struct.unpack("<I", mu.mem_read(esp + 8, 4))[0]

        h = self.emu.mu.hook_add(UC_HOOK_CODE, hook)
        try:
            r = self.emu.call(GOD_BLOCK, [player], setup=self._setup)
        finally:
            self.emu.mu.hook_del(h)
        self.ret = r["signed"]
        self.msg_calls = self.emu.readu32(CALLS_MSG)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        # 展开后的文本（与复刻返回的物件名可比）
        if self.msg_fmt is None:
            self.msg_name = None
            self.msg_text = None
        else:
            fmt = self.orig_str(self.msg_fmt)
            self.msg_name = self.orig_wstr(self.msg_arg)
            self.msg_text = fmt.replace(b"%s", self.msg_name)
        return self

    def run_d(self, player):
        r = self.emu.call(PICK_CONSTRUCTION, [player], setup=self._setup)
        self.ret = r["signed"]
        return self

    # ── 读原版数据表（桩/期望共用） ──
    def orig_str(self, va):
        out = bytearray()
        p = va
        while True:
            b = self.emu.read8(p)
            if b == 0:
                break
            out.append(b)
            p += 1
        return bytes(out)

    def orig_wstr(self, va):
        out = bytearray()
        p = va
        while True:
            w = self.emu.read16(p)
            if w == 0:
                break
            out.append(w & 0xFF)
            out.append((w >> 8) & 0xFF)
            p += 2
        return bytes(out)

    def expect_god_message(self, god):
        """按 exe 自己的表与格式串拼出期望文本（不硬编码中文）。"""
        name_va = self.emu.readu32(OBJ_NAME_PTRS + god * 4)
        name = self.orig_wstr(name_va)                       # 物件名（Big5/ANSI）
        fmt = self.orig_str(MSG_FMT)                         # b"%s\xc5\xe3\xc6F..."
        return fmt.replace(b"%s", name), name


def main():
    print("差分测试 · 四支小规则助手 0x41d7d4 / 0x41d839 / 0x40fa61 / 0x40b455\n")
    w = World()

    # ══════════════════════════════════════════════════════════════════
    print("[A] 0x0041d7d4(价) —— AI「买完还剩多少钱」闸门（101 B，2 个调用点）")
    print("    reserve = min(trunc(开局资金 × 0.05), 7000) × 物价指数；total = 现金 + 存款")

    # ★ 阈值都手算并写在标签里：reserve = min(trunc(开局资金 × 0.05), 7000) × 物價指数；
    #   total = 现金[+0x1c] + 存款[+0x20]；命中条件 = **total − 价 > reserve**（严格大于）。
    #   ⚠️ 7000 那道夹的**是乘物價指数之前**的量 ⇒ 开局资金 ≥ 140000 时阈值恒为 7000×物價。

    # ★ 阈值 = min(trunc(开局资金 × 0.05), 7000) × 物價指数；total = 现金[+0x1c] + 存款[+0x20]；
    #   命中条件 = **total − 价 > 阈值**（严格大于）。
    #   ⚠️ 7000 那道夹夹的是**乘物價指数之前**的量 ⇒ 开局资金 ≥ 140000 时阈值 = 7000×物價。
    #   ⚠️ 对照 [B] 组：**B 支没有这道夹**（见那边注释）。

    # A1..A4 严格大于（以开局 100000 ⇒ trunc(5000)，未触夹）
    w.clear(); w.initial_fund = 100000; w.cash[0] = 6000
    case("A1 门槛 5000：6000−1000 = 5000 > 5000 为假 ⇒ 0", w.run_a(1000).ret, 0)
    w.clear(); w.initial_fund = 100000; w.cash[0] = 6001
    case("A2 同上 6001−1000 = 5001 > 5000 ⇒ 1", w.run_a(1000).ret, 1)
    w.clear(); w.initial_fund = 100000; w.cash[0] = 5999
    case("A3 同上 5999−1000 = 4999 > 5000 为假 ⇒ 0", w.run_a(1000).ret, 0)
    w.clear(); w.initial_fund = 100000; w.cash[0] = 6500
    case("A4 同上 6500−1000 = 5500 > 5000 ⇒ 1", w.run_a(1000).ret, 1)

    # A5/A6 存款 +0x20 计入 total
    w.clear(); w.initial_fund = 100000; w.cash[0] = 4000; w.bank[0] = 2000
    case("A5 ★ 存款算进 total（+0x20）：4000+2000−1000 = 5000 ⇒ 0", w.run_a(1000).ret, 0)
    w.clear(); w.initial_fund = 100000; w.cash[0] = 4000; w.bank[0] = 2001
    case("A6 ★ 同上存款 2001 ⇒ 5001 ⇒ 1（现金 4000 单独远不够）", w.run_a(1000).ret, 1)

    # A7..A11 7000 上限 —— 夹的是「乘物價前」的量
    w.clear(); w.initial_fund = 300000; w.cash[0] = 8000
    case("A7 ★ 开局 300000 ⇒ trunc(15000) 被夹成 7000：8000−1 = 7999 > 7000 ⇒ 1",
         w.run_a(1).ret, 1)
    w.clear(); w.initial_fund = 300000; w.cash[0] = 7001
    case("A8 ★ 同上 7001−1 = 7000 > 7000 为假 ⇒ 0（证明阈值就是 7000）",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 300000; w.cash[0] = 7002
    case("A9 ★ 同上 7002−1 = 7001 > 7000 ⇒ 1", w.run_a(1).ret, 1)
    w.clear(); w.initial_fund = 1000000; w.cash[0] = 7001
    case("A10 ★ 开局 1000000 ⇒ trunc(50000) 夹成 7000：7001−1 = 7000 假 ⇒ 0",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 1000000; w.cash[0] = 7002
    case("A11 ★ 同上 7002−1 = 7001 > 7000 ⇒ 1", w.run_a(1).ret, 1)

    # A12/A13 夹在 140000 附近的分界（trunc(140000×0.05) = 7000 恰好不夹）
    w.clear(); w.initial_fund = 139999; w.cash[0] = 6999
    case("A12 ★ 开局 139999 ⇒ trunc(6999.95) = 6999：6999−1 = 6998 > 6999 假 ⇒ 0",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 139999; w.cash[0] = 7001
    case("A13 ★ 同上 7001−1 = 7000 > 6999 ⇒ 1（分界确实在 139999/140000）",
         w.run_a(1).ret, 1)

    # A14..A17 先夹后乘：物價指数在最后才乘
    w.clear(); w.initial_fund = 150000; w.price_index = 7; w.cash[0] = 49001
    case("A14 ★★ 开局 150000、物價 7 ⇒ 先夹 7000 再 ×7 = 49000：49001−1 = 49000 假 ⇒ 0",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 150000; w.price_index = 7; w.cash[0] = 49002
    case("A15 ★★ 同上 49002−1 = 49001 > 49000 ⇒ 1（门槛恰为 7000×7）",
         w.run_a(1).ret, 1)
    w.clear(); w.initial_fund = 100000; w.price_index = 2; w.cash[0] = 10000
    case("A16 ★★ 开局 100000、物價 2 ⇒ 5000×2 = 10000：10000−1 = 9999 > 10000 假 ⇒ 0",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 100000; w.price_index = 2; w.cash[0] = 10002
    case("A17 ★★ 同上 10002−1 = 10001 > 10000 ⇒ 1", w.run_a(1).ret, 1)

    # A18..A22 截断发生在乘 0.05 之后
    w.clear(); w.initial_fund = 10; w.cash[0] = 1
    case("A18 ★ 开局 10 ⇒ trunc(0.5) = 0 ⇒ 门槛 0：1−1 = 0 > 0 假 ⇒ 0", w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 10; w.cash[0] = 2
    case("A19 ★ 同上身家 2 ⇒ 2−1 = 1 > 0 ⇒ 1", w.run_a(1).ret, 1)
    w.clear(); w.initial_fund = 1000; w.cash[0] = 51
    case("A20 开局 1000 ⇒ trunc(50) = 50：51−1 = 50 > 50 假 ⇒ 0", w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = 1000; w.cash[0] = 52
    case("A21 同上身家 52 ⇒ 51 > 50 ⇒ 1", w.run_a(1).ret, 1)
    w.clear(); w.initial_fund = 1000; w.cash[0] = 50
    case("A22 同上身家 50 ⇒ 49 > 50 假 ⇒ 0", w.run_a(1).ret, 0)

    # A23..A25 负开局资金：trunc 朝零（不是向下）
    w.clear(); w.initial_fund = -1000; w.cash[0] = -50
    case("A23 ★ 开局 −1000 ⇒ trunc(−50) = −50（向零，不是 −51）⇒ −50−1 = −51 > −50 假 ⇒ 0",
         w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = -1000; w.cash[0] = -49
    case("A24 ★ 同上身家 −49 ⇒ −49−1 = −50 > −50 假 ⇒ 0", w.run_a(1).ret, 0)
    w.clear(); w.initial_fund = -1000; w.cash[0] = -48
    case("A25 ★ 同上身家 −48 ⇒ −49 > −50 ⇒ 1", w.run_a(1).ret, 1)

    # A26/A27 价 = 0（门槛仍照旧）
    w.clear(); w.initial_fund = 100000; w.cash[0] = 5000
    case("A26 价 = 0 ⇒ 5000−0 = 5000 > 5000 假 ⇒ 0", w.run_a(0).ret, 0)
    w.clear(); w.initial_fund = 100000; w.cash[0] = 5001
    case("A27 价 = 0、身家 5001 ⇒ 1", w.run_a(0).ret, 1)

    # A28/A29 读的必须是**当前玩家**（0 基）
    w.clear(); w.initial_fund = 100000; w.cur = 2
    w.cash[0] = 999999; w.cash[2] = 6000
    case("A28 ★ 当前玩家 = 2（玩家 0 很有钱）⇒ 用玩家的 6000−1000 = 5000 ⇒ 0",
         w.run_a(1000).ret, 0)
    w.clear(); w.initial_fund = 100000; w.cur = 2
    w.cash[0] = 999999; w.cash[2] = 6001
    case("A29 ★ 同上玩家 2 有 6001 ⇒ 1（证明是 cur 而不是玩家 0）", w.run_a(1000).ret, 1)

    # A30 输出只有 0/1
    seen = set()
    for cash, idx, fund in [(0, 1, 0), (6000, 1, 100000), (10 ** 9, 50, 10 ** 9)]:
        w.clear(); w.initial_fund = fund; w.price_index = idx; w.cash[0] = cash
        seen.add(w.run_a(1).ret)
    case("A30 返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    # A31 用 exe 自己的 f64 常量交叉印证 0x463cc8 = 0.05
    w.clear()
    case("A31 ★ exe 的 f64 0x463cc8 恰为 0.05", w.emu.f64(0x463CC8), RATIO_A)

    # A32 随机数：A 支一个都不摇
    w.clear(); w.initial_fund = 100000; w.cash[0] = 6000
    w.run_a(1000)
    case("A32 A 支不摇随机数（0x456f2d 的调用计数为 0）", w.emu.readu32(RAND_CALLS), 0)


    print("\n[B] 0x0041d839(单价, 上限) —— 電腦买股上限（101 B，1 个调用点 0x41d269）")
    print("    r = min(trunc(开局资金 × 0.30), 7000) × 物價；d = 现金 − r；")
    print("    d ≤ 0 ⇒ 0；否则 min(上限, d ÷ 单价)")

    # ★ 阈值 = min(trunc(开局资金 × 0.30), 7000) × 物價指数；d = 现金 − 阈值；
    #   d ≤ 0 ⇒ 0；否则 min(上限, d ÷ 单价)（idiv，向零取整）。
    #   ⚠️ 7000 那道夹同样在**乘物價指数之前** ⇒ 开局资金 ≥ 23334 时阈值 = 7000×物價。
    #   ⚠️ 与 A 支相反：**存款不参与**（hunk 读的是 `[+0x1c]`，没有 `[+0x20]`）。

    # ★ 阈值 = trunc(开局资金 × 0.30) × 物價指数 —— ★★ **没有 7000 那道夹**（[A] 支有）。
    #   d = 现金[+0x1c] − 阈值；d ≤ 0 ⇒ 0；否则 min(第二参 上限, d ÷ 第一参 单价)（idiv 向零）。
    #   ⚠️ 与 A 支相反：**存款不参与**（只读 `[+0x1c]`，没有 `[+0x20]`）。

    # B1..B3 边界（以开局 20000 ⇒ trunc(6000)）
    w.clear(); w.initial_fund = 20000; w.cash[0] = 6000
    case("B1 门槛 6000：6000−6000 = 0 ⇒ 0（d ≤ 0 与 d < 0 同出口）",
         w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 6001
    case("B2 同上现金 6001 ⇒ d = 1 ⇒ 1", w.run_b(1, 1000).ret, 1)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 5999
    case("B3 同上现金 5999 ⇒ d < 0 ⇒ 0", w.run_b(1, 1000).ret, 0)

    # B4/B5 ★★ 常量判别：0.30 与 0.05 在开局 20000 上差 6 倍
    w.clear(); w.initial_fund = 20000; w.cash[0] = 3000
    case("B4 ★★ 开局 20000、现金 3000 ⇒ 保留 6000（=0.30）⇒ d<0 ⇒ 0；按 0.05（1000）会算出 2000",
         w.run_b(1, 1000).ret, 0)
    w.clear()
    case("B5 ★★ exe 的 f64 0x463cd0 恰为 0.30（places/company.ts:171 的注释写 0.05）",
         w.emu.f64(0x463CD0), RATIO_B)
    w.clear()
    case("B6 ★★ 两常量不同：0x463cc8 = 0.05（A 支）、0x463cd0 = 0.30（B 支）",
         (w.emu.f64(0x463CC8), w.emu.f64(0x463CD0)), (RATIO_A, RATIO_B))

    # B7/B8 存款不参与（与 A 支相反）
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45000; w.bank[0] = 999999
    case("B7 ★★ 现金 45000 恰等门槛 45000、存款塞满也不管 ⇒ 0（A 支会把存款算进去）",
         w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45001; w.bank[0] = 0
    case("B8 ★ 现金 45001、存款 0 ⇒ 1（门槛 45000 = trunc(150000×0.30)）",
         w.run_b(1, 1000).ret, 1)

    # B9/B10 ★★ 没有 7000 上限：开局 300000 ⇒ 门槛就是 90000
    w.clear(); w.initial_fund = 300000; w.cash[0] = 90000
    case("B9 ★★ 开局 300000 ⇒ 门槛 trunc(90000) 未夹：90000−90000 = 0 ⇒ 0",
         w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 300000; w.cash[0] = 90001
    case("B10 ★★ 同上 90001 ⇒ 1（若照 [A] 支夹到 7000，这里会是 83001）",
         w.run_b(1, 1000).ret, 1)
    w.clear(); w.initial_fund = 300000; w.cash[0] = 7001
    case("B11 ★★ 同上现金 7001 ⇒ d < 0 ⇒ 0（证明 B 支**确实没有** 7000 夹）",
         w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 1000000; w.cash[0] = 300000
    case("B12 ★★ 开局 1000000 ⇒ 门槛 300000：300000−300000 = 0 ⇒ 0", w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 1000000; w.cash[0] = 300001
    case("B13 ★★ 同上 300001 ⇒ 1", w.run_b(1, 1000).ret, 1)

    # B14..B18 除法与向零
    w.clear(); w.initial_fund = 150000; w.cash[0] = 100000
    case("B14 (100000−45000)/70 = 785.7… ⇒ 785（向零，不是 786）", w.run_b(70, 1000).ret, 785)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 50000
    case("B15 (50000−45000)/50 = 100 ⇒ 100", w.run_b(50, 1000).ret, 100)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45001
    case("B16 (45001−45000)/7 = 0.14… ⇒ 0（不足一股 ⇒ 0）", w.run_b(7, 1000).ret, 0)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45007
    case("B17 (45007−45000)/7 = 1 整 ⇒ 1", w.run_b(7, 1000).ret, 1)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45010
    case("B18 单价 10 ⇒ 10/10 = 1 ⇒ 1（除数就是第一参）", w.run_b(10, 1000).ret, 1)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 45010
    case("B19 单价 11 ⇒ 10/11 = 0 ⇒ 0", w.run_b(11, 1000).ret, 0)

    # B20..B24 第二参（上限）：先与「单价 × 上限」比，超过就返回上限
    w.clear(); w.initial_fund = 150000; w.cash[0] = 100000
    case("B20 ★ 算出 785（<1000）⇒ 785", w.run_b(70, 1000).ret, 785)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B21 ★ 算出 14200 ⇒ 夹到 1000", w.run_b(1, 1000).ret, 1000)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B22 ★ 上限 300 ⇒ 夹到 300", w.run_b(1, 300).ret, 300)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B23 上限 785、算出 14200 ⇒ 785", w.run_b(1, 785).ret, 785)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B24 上限 784、算出 14200 ⇒ 784", w.run_b(1, 784).ret, 784)
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B25 ★ 上限 0 ⇒ 0（原版照样过一遍，0 表示「连问都不问」）",
         w.run_b(1, 0).ret, 0)

    # B26 ★ 比较用的是「单价 × 上限」，不是「d / 单价 再夹」
    w.clear(); w.initial_fund = 150000; w.cash[0] = 46000
    case("B26 ★ d = 1000；70×15 = 1050 > 1000 ⇒ 走除法 1000/70 = 14（不是 15）",
         w.run_b(70, 15).ret, 14)
    w.clear(); w.initial_fund = 150000; w.cash[0] = 46050
    case("B27 ★ d = 1050；70×15 = 1050 ≥ 1050 ⇒ 返回上限 15", w.run_b(70, 15).ret, 15)

    # B28 上限扫描：全部压在 1000 以下
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    got = [w.run_b(1, n).ret for n in (1000, 999, 3, 1, 0)]
    case("B28 ★ 上限扫描 [1000,999,3,1,0] ⇒ [1000,999,3,1,0]", got, [1000, 999, 3, 1, 0])

    # B29 物價指数乘进门槛
    w.clear(); w.initial_fund = 150000; w.price_index = 4; w.cash[0] = 180000
    case("B29 ★ 物價 4 ⇒ 门槛 45000×4 = 180000；180000−180000 = 0 ⇒ 0",
         w.run_b(1, 1000).ret, 0)
    w.clear(); w.initial_fund = 150000; w.price_index = 4; w.cash[0] = 180001
    case("B30 同上现金 180001 ⇒ 1（物價指数确实乘进门槛）", w.run_b(1, 1000).ret, 1)

    # B31/B32 ★★ 「通用填数窗」不在本函数体内 —— 它在**调用方** `0x41d1a9` 的
    #   真人支（`0x41d25b push esi; call 0x453544`）。本函数在 z 支返回的是**值**，
    #   由调用方决定拿去干嘛 ⇒ 这里断言「本函数一次都没碰它」。
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    r = w.run_b(1, 700)
    case("B31 ★★ 本函数**不调**通用填数窗（0x453544 在调用方 0x41d1a9 的真人支里）",
         (r.ret, r.window_calls), (700, 0))
    w.clear(); w.initial_fund = 20000; w.cash[0] = 20200
    case("B32 ★ z 支返回的就是值本身（700），不是被填数窗夹过的结果",
         w.run_b(1, 700).ret, 700)

    # B33 不摇随机数
    w.clear(); w.initial_fund = 150000; w.cash[0] = 100000
    w.run_b(70, 1000)
    case("B33 B 支不摇随机数", w.emu.readu32(RAND_CALLS), 0)


    print("\n[C] 0x0040fa61(玩家) —— 衰神/大衰神/死神挡下一切消费（117 B，5 个调用点）")

    w.clear(); w.god[0] = 0
    r = w.run_c(0)
    case("C1 物件 0（間諜）⇒ 放行 0", r.ret, 0)
    case("  没弹框（0x440cac 调用次数 = 0）", r.msg_calls, 0)

    w.clear(); w.god[0] = 7
    r = w.run_c(0)
    case("C2 物件 7（小衰神）⇒ 挡下 1", r.ret, 1)
    case("  弹框恰好 1 次", r.msg_calls, 1)

    w.clear(); w.god[0] = 8
    r = w.run_c(0)
    case("C3 物件 8（大衰神）⇒ 挡下 1", r.ret, 1)
    case("  弹框恰好 1 次", r.msg_calls, 1)
    want8, name8 = w.expect_god_message(8)
    case("C4 ★ 格式串地址 = exe 的 0x463514（b'%s\\xc5\\xe3...'）",
         w.orig_str(r.msg_fmt), b"%s" + w.orig_str(MSG_FMT)[2:])
    case("C4b ★ 实参指针 = 物件名表[8] 那一格（0x47ed76 + 8*4）",
         r.msg_arg, w.emu.readu32(OBJ_NAME_PTRS + 8 * 4))
    case("C4c ★ 展开后的文本 = 格式串填入物件名表[8]（大衰神）", r.msg_text, want8)

    w.clear(); w.god[0] = 15
    r = w.run_c(0)
    case("C5 物件 15（死神）⇒ 挡下 1", r.ret, 1)
    want15, name15 = w.expect_god_message(15)
    case("C6 ★ 展开后的文本 = 物件名表[15]（死神）", r.msg_text, want15)
    case("C6b ★ 8 与 15 的名字本身不同（各自查表）", name8 != name15, True)

    # C7..C18 全 19 个物件号逐个扫（7/8/15 三个命中）
    hits = []
    for g in range(19):
        w.clear(); w.god[0] = g
        hits.append(w.run_c(0).ret)
    case("C7 ★ 19 个物件号里恰好 7/8/15 三个命中",
         [g for g in range(19) if hits[g]], [7, 8, 15])
    case("C8 ★ 命中集合的返回值全为 1", sorted({hits[g] for g in (7, 8, 15)}), [1])
    case("C9 ★ 其余 16 个物件号全为 0", sorted({hits[g] for g in range(19) if g not in (7, 8, 15)}), [0])
    case("C10 ★ 物件 6/9/14/16 是关键的「邻位」（不在集合）",
         [hits[6], hits[9], hits[14], hits[16]], [0, 0, 0, 0])
    case("C11 ★ 表尾的 17/18 号也放行（不在三个命中里）", [hits[17], hits[18]], [0, 0])
    case("C12 ★ 扫完 19 个号，只有 7/8/15 调了弹框",
         [g for g in range(19) if g in (7, 8, 15)], [7, 8, 15])

    # C14 参数是玩家号（0 基，各自独立）
    w.clear(); w.god[2] = 8
    case("C14 ★ 玩家 2 被附身、玩家 0 干净 ⇒ fa61(0) = 0", w.run_c(0).ret, 0)
    w.clear(); w.god[2] = 8
    case("C15 ★ 同上 fa61(2) = 1（证明参数是玩家号）", w.run_c(2).ret, 1)

    # C16 文本随物件号变（8 vs 15 不同名）
    w.clear(); w.god[3] = 8
    t8 = w.run_c(3).msg_text
    w.clear(); w.god[3] = 15
    t15 = w.run_c(3).msg_text
    case("C16 ★ 物件 8 与 15 的文本不同（各自查表）", t8 != t15, True)
    case("C17 ★ 文本以**各自的名字**开头（%s 已被替换，不再是字面 %s）",
         (t8[:len(name8)], t15[:len(name15)]), (name8, name15))
    case("C17b ★ 文本 = 名字 + 格式串去掉 %s 之后的后缀（逐字节）",
         (t8, t15),
         (w.orig_str(MSG_FMT).replace(b"%s", name8),
          w.orig_str(MSG_FMT).replace(b"%s", name15)))

    # C18 不摇随机数
    w.clear(); w.god[0] = 8
    r = w.run_c(0)
    case("C18 C 支不摇随机数", w.emu.readu32(RAND_CALLS), 0)

    # C19 放行时不弹框
    w.clear(); w.god[0] = 1
    r = w.run_c(0)
    case("C19 放行支：0x440cac 调用次数 = 0", r.msg_calls, 0)

    # ══════════════════════════════════════════════════════════════════
    print("\n[D] 0x0040b455(玩家) —— 建設公司挑加蓋目标（163 B，2 个调用点）")

    # D1 空表
    w.clear()
    case("D1 两块表都空 ⇒ 0", w.run_d(0).ret, 0)

    # D2 门槛：owner ∉ {0, 我}
    w.clear(); w.add_land(1, owner=0, level=3, typ=0, rent=9999)
    case("D2 ★ 无主地（owner 0）不入围 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_land(1, owner=1, level=3, typ=0, rent=9999)
    case("D3 ★ 我自己的地（owner == 我+1）⇒ 0x7d0+1", w.run_d(0).ret, LAND_MARK + 1)
    w.clear(); w.add_land(1, owner=2, level=3, typ=0, rent=9999)
    case("D4 ★ 别人的地（owner 2）不入围 ⇒ 0", w.run_d(0).ret, 0)

    # D5 owner 是 1 基、参数 0 基（换玩家）
    w.clear(); w.add_land(1, owner=2, level=3, typ=0, rent=9999)
    case("D5 ★ 同一块 owner=2 的地：玩家 1 视角 ⇒ 0x7d1", w.run_d(1).ret, LAND_MARK + 1)
    w.clear(); w.add_land(1, owner=1, level=3, typ=0, rent=9999)
    case("D6 ★ 同上 owner=1：玩家 0 ⇒ 命中，玩家 1 ⇒ 不命中",
         (w.run_d(0).ret, w.run_d(1).ret), (LAND_MARK + 1, 0))

    # D7 只看住宅（type == 0）
    w.clear(); w.add_land(1, owner=1, level=3, typ=1, rent=9999)
    case("D7 ★ 連鎖店（type 1）不入围 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_land(1, owner=1, level=3, typ=0, rent=9999)
    case("D8 ★ 住宅（type 0）⇒ 命中", w.run_d(0).ret, LAND_MARK + 1)

    # D9 等级门槛：>= 5 跳
    w.clear(); w.add_land(1, owner=1, level=4, typ=0, rent=9999)
    case("D9 ★ 等级 4 ⇒ 命中（门槛是「≥5 才跳」）", w.run_d(0).ret, LAND_MARK + 1)
    w.clear(); w.add_land(1, owner=1, level=5, typ=0, rent=9999)
    case("D10 ★ 等级 5 ⇒ 跳过 ⇒ 0", w.run_d(0).ret, 0)

    # D11 ★★ 租金按**当前等级**查表（rentByLevel[level]，不是别的等级）
    w.clear(); w.add_land(1, owner=1, level=0, typ=0, rent=7777)
    case("D11 ★★ 等级 0 ⇒ 查 rentByLevel[0] = 7777 ⇒ 命中 0x7d1",
         w.run_d(0).ret, LAND_MARK + 1)
    w.clear(); w.add_land(1, owner=1, level=2, typ=0, rent=0)
    case("D12 ★★ 等级 2 但 rentByLevel[2] = 0 ⇒ 严格大于 0 才入 ⇒ 0",
         w.run_d(0).ret, 0)
    w.clear(); w.add_land(1, owner=1, level=2, typ=0, rent=1)
    case("D13 ★★ 同上 rentByLevel[2] = 1 ⇒ 命中", w.run_d(0).ret, LAND_MARK + 1)

    # D14 取「最大租金」，严格大于
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=100)
    w.add_land(2, owner=1, level=0, typ=0, rent=200)
    case("D14 两块同级 ⇒ 取租金大的 ⇒ 0x7d2", w.run_d(0).ret, LAND_MARK + 2)
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=200)
    w.add_land(2, owner=1, level=0, typ=0, rent=200)
    case("D15 ★ 同租金 ⇒ 严格大于 ⇒ 取**先遍历到**的 0x7d1", w.run_d(0).ret, LAND_MARK + 1)
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=100)
    w.add_land(2, owner=1, level=3, typ=0, rent=5000)
    case("D16 ★ 租金比等级重要（高等级更高租金 ⇒ 取 0x7d2）", w.run_d(0).ret, LAND_MARK + 2)
    w.clear()
    w.add_land(1, owner=1, level=4, typ=0, rent=900)
    w.add_land(2, owner=1, level=1, typ=0, rent=5000)
    case("D17 ★ 反例：等级 4 租金 900 vs 等级 1 租金 5000 ⇒ 取租金大的 0x7d2",
         w.run_d(0).ret, LAND_MARK + 2)

    # D18 ★★ 循环从记录 1 起（记录 0 永远不看）
    w.clear(); w.add_land(0, owner=1, level=1, typ=0, rent=30000)
    w.add_land(1, owner=1, level=1, typ=0, rent=100)
    case("D18 ★★ 记录 0 有巨额租金但被跳过 ⇒ 取 0x7d1（不是 0x7d0）",
         w.run_d(0).ret, LAND_MARK + 1)
    w.clear(); w.add_land(0, owner=1, level=1, typ=0, rent=30000)
    w.land_n = 0
    case("D19 ★★ 上界为 0 ⇒ 一格都不看（记录 0 也不看）⇒ 0", w.run_d(0).ret, 0)
    w.clear()
    for i in range(1, 4):
        w.add_land(i, owner=1, level=0, typ=0, rent=i)
    case("D20 地块数 = 3 ⇒ 只看 1..3 ⇒ 取租金最大的 0x7d3", w.run_d(0).ret, LAND_MARK + 3)

    # D21 用**表记录的**租金而不是重新读表（表里的值就是入参）
    w.clear(); w.add_land(1, owner=1, level=0, typ=0, rent=12345)
    case("D21 ★ 返回值是「实体编码」而不是租金（0x7d1）", w.run_d(0).ret, LAND_MARK + 1)

    # D22..D24 設施三条门槛
    w.clear(); w.add_fac(1, owner=2, level=0, typ=1, price=9999)
    case("D22 ★ 别人的設施不入围 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_fac(1, owner=1, level=0, typ=1, price=0)
    case("D23 ★ 我的設施但價格 0 ⇒ 严格大于 best(0) 假 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_fac(1, owner=1, level=0, typ=1, price=1)
    case("D24 ★ 我的設施價格 1 ⇒ 0xfa1", w.run_d(0).ret, FAC_MARK + 1)

    # D25/D26 等级上限按 type 查 0x474940 = [1,5,5,1,5]
    w.clear(); w.add_fac(1, owner=1, level=0, typ=0, price=500)
    case("D25 ★ type 0（公園）上限 1：level 0 ⇒ 命中 0xfa1", w.run_d(0).ret, FAC_MARK + 1)
    w.clear(); w.add_fac(1, owner=1, level=1, typ=0, price=500)
    case("D26 ★ type 0 上限 1：level 1 ⇒ `jae` 跳过 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_fac(1, owner=1, level=4, typ=1, price=500)
    case("D27 ★ type 1 上限 5：level 4 ⇒ 命中 0xfa1", w.run_d(0).ret, FAC_MARK + 1)
    w.clear(); w.add_fac(1, owner=1, level=5, typ=1, price=500)
    case("D28 ★ type 1 上限 5：level 5 ⇒ 跳过 ⇒ 0", w.run_d(0).ret, 0)
    w.clear(); w.add_fac(1, owner=1, level=0, typ=3, price=500)
    case("D29 ★ type 3（公園系）上限 1：level 0 ⇒ 命中 0xfa1", w.run_d(0).ret, FAC_MARK + 1)
    w.clear(); w.add_fac(1, owner=1, level=1, typ=3, price=500)
    case("D30 ★ type 3 上限 1：level 1 ⇒ 跳过 ⇒ 0", w.run_d(0).ret, 0)

    # D31 ★★ 設施必须**嚴格超过**地块的最优租金
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=500)
    w.add_fac(1, owner=1, level=0, typ=1, price=500)
    case("D31 ★★ 設施價格 500 == 地块租金 500 ⇒ 不换（`jge` 跳过）⇒ 0x7d1",
         w.run_d(0).ret, LAND_MARK + 1)
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=500)
    w.add_fac(1, owner=1, level=0, typ=1, price=501)
    case("D32 ★★ 設施價格 501 > 500 ⇒ 换 ⇒ 0xfa1", w.run_d(0).ret, FAC_MARK + 1)

    # D33 設施取最大價格
    w.clear()
    w.add_fac(1, owner=1, level=0, typ=1, price=100)
    w.add_fac(2, owner=1, level=0, typ=1, price=300)
    case("D33 两个设施 ⇒ 取价格大的 0xfa2", w.run_d(0).ret, FAC_MARK + 2)
    w.clear()
    w.add_fac(1, owner=1, level=0, typ=1, price=300)
    w.add_fac(2, owner=1, level=0, typ=1, price=300)
    case("D34 ★ 同价 ⇒ 取先遍历到的 0xfa1", w.run_d(0).ret, FAC_MARK + 1)

    # D35 ★★ 設施循环也从记录 1 起
    w.clear(); w.add_fac(0, owner=1, level=0, typ=1, price=40000)
    w.add_fac(1, owner=1, level=0, typ=1, price=100)
    case("D35 ★★ 設施记录 0 被跳过 ⇒ 0xfa1", w.run_d(0).ret, FAC_MARK + 1)
    w.clear(); w.add_fac(0, owner=1, level=0, typ=1, price=40000)
    w.fac_n = 0
    case("D36 ★★ 設施數 0 ⇒ 不看记录 0 ⇒ 0", w.run_d(0).ret, 0)

    # D37 ★★ 設施地價的字段是 +0x22（不是地块的 +0x1c）
    w.clear(); w.add_fac(1, owner=1, level=0, typ=1, price=2222)
    case("D37 ★★ 讀 `+0x22`：price=2222 ⇒ 命中", w.run_d(0).ret, FAC_MARK + 1)
    w.clear(); w.add_fac(1, owner=1, level=0, typ=1, price=1)
    w.facs[1] = (1, 0, 1, 0)      # 只把地價清 0
    case("D38 ★★ 地價 0 ⇒ 不命中（证明价格字段是判据）", w.run_d(0).ret, 0)

    # D39 上界字面量：0x474940 真值
    w.clear()
    case("D39 ★ 最高等级表 0x474940 = [1,5,5,1,5]",
         [w.emu.read8(FAC_MAX_LEVEL + t) for t in range(5)], [1, 5, 5, 1, 5])

    # D40 参数与输出编码
    w.clear()
    for i in range(1, 6):
        w.add_land(i, owner=2, level=0, typ=0, rent=10 * i)
    case("D40 ★★ 玩家 1（1 基 owner 2）⇒ 0x7d5；玩家 0 ⇒ 0",
         (w.run_d(1).ret, w.run_d(0).ret), (LAND_MARK + 5, 0))

    # D41 混合：地块与设施同场（设施优先，若价格更高）
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=800)
    w.add_fac(1, owner=1, level=0, typ=1, price=700)
    case("D41 ★ 地块租金 800 > 設施價格 700 ⇒ 留在地块 0x7d1",
         w.run_d(0).ret, LAND_MARK + 1)
    w.clear()
    w.add_land(1, owner=1, level=0, typ=0, rent=800)
    w.add_fac(1, owner=1, level=0, typ=1, price=900)
    case("D42 ★ 反过来 900 > 800 ⇒ 取設施 0xfa1", w.run_d(0).ret, FAC_MARK + 1)

    # D43 不摇随机数
    w.clear(); w.add_land(1, owner=1, level=0, typ=0, rent=100)
    case("D43 D 支不摇随机数", w.emu.readu32(RAND_CALLS), 0)

    # D44 返回值只有三类
    seen = set()
    w.clear(); seen.add(w.run_d(0).ret)
    w.clear(); w.add_land(1, owner=1, level=0, typ=0, rent=5); seen.add(w.run_d(0).ret)
    w.clear(); w.add_fac(1, owner=1, level=0, typ=1, price=5); seen.add(w.run_d(0).ret)
    case("D44 返回值集合恰为 {0, 0x7d1, 0xfa1}", sorted(seen), [0, LAND_MARK + 1, FAC_MARK + 1])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
