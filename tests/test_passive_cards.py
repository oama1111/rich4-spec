#!/usr/bin/env python3
"""
通道 2 差分测试 · **被动防御卡族**（免費 20 / 免罪 21 / 嫁禍 19 / 復仇 18）

主目标：`0x00444A60`（338 B，函数表；`ret` 在 `0x444bb1`）=
**免費卡(20) 的使用判定与消耗**。

本文件把「被动防御卡」的**四张处理函数**连同**它们的调用方（陷害卡 17）**
一起在 Unicorn 里整支驱动原版机器码，钉的是**命中/消耗/顺序/天数/敌意/返回编码**，
不是复述复刻实现。复刻侧对应：
  · `rich4-remake/packages/core/src/cards/passive.ts`
  · `rich4-remake/packages/core/src/cards/tax.ts`（查稅卡）
  · `rich4-remake/packages/core/src/rules/toll-flow.ts`（过路费）
  · `rich4-remake/packages/core/src/cards/frame.ts` / `sleepwalk.ts`（陷害/夢遊）

机器码范围（逐条反汇编核对，`rich4-remake/tools/disasm.py`）：

```
0x444A60  int use_free_card(int target, int payer, int amount)      ; 免費卡(20)，338 B
0x444BB2  int absolve(int target)                                    ; 免罪卡(21)，共享尾 0x444753
0x444691  int revenge(int target)                                    ; 復仇卡(18)
0x44476A  int blame_shift(int target, int mode, int amount)          ; 嫁禍卡(19)，758 B
0x4444BF  int frame_card(void)                                       ; 陷害卡(17) 的调用方（命中顺序/復仇）
```

## 控制流（全文反汇编后的伪代码）

### `0x444a60(target, payer, amount)` —— 免費卡

```
    anim_fly(target)                          ; 0x444a8a call 0x41d476
    if player[target].whoPlays == 1:          ; 0x444a92 cmp [ebx+0x496b7d],1
        ; ── 真人：确认框 ──
        sprintf(buf, "%s\\n\\n是否使用免費卡？", player[target].name)   ; 0x457110 / str 0x465388
        if confirm(buf) != 1:                 ; 0x444af4 call 0x440ba8 / 0x444afe cmp eax,1
            return 0                          ; 0x444ba0 尾部（**卡不消耗**）
    else:
        ; ── 电脑：门槛 ──          0x444a9b call rand (0x456f2d)
        thr = priceIndex * (3000 + rand() % 3000)      ; idiv 3000 / add edx,3000 / imul
        if !(amount > player[target].cash || amount > thr):
            return 0                          ; 0x444ad1 -> 0x444ba0
    ; ── 使用（真/电脑共用）──
    popup(buf, 20)                            ; 0x444b25 call 0x441f73
    remove_card(target, 20)                   ; ★ 0x444b2d push 0x14 / 0x444b30 call 0x441343
    say(target, 0, k19)                       ; 0x444b5e call 0x44ef41
    if payer != -1: say(payer, 1, k19)        ; 0x444b6d cmp ecx,-1 / 0x444b98 call 0x44ef41
    refresh_map()                             ; 0x444ba0 call 0x41d546
    return 1                                  ; 0x444ba5 mov eax,esi
```

★ 两个反直觉处（都已在断言里钉住）：
1. **本函数不查 `has_card`** —— 是调用方（过路费/查稅卡）先查。没卡也照样返回 1 并尝试扣。
2. **门槛是 `>`，不是 `>=`**：`amount == thr` 判为**不用**（`cmp esi,thr / jge 不用`）。

★ **本函数不调用 `0x40df69`（敌意写入）** —— 已逐条核对 callees，
查稅卡的敌意在调用方 `0x4452fc`、陷害卡的敌意在 `0x4445c1`，
都在调用本函数**之前**。故不变量 `0x40df69` 在本文件里由 `0x4444bf` 那一组断言钉住。

### `0x444bb2(target)` —— 免罪卡

```
    anim_fly(target); sprintf(buf,"%s\\n\\n免罪卡生效！", name); popup(buf,21)
    remove_card(target, 21)                   ; ★ 0x444c11 call 0x441343
    say(target, 0, k20)
    jmp 0x444753 -> call 0x44ef41(target,0,k) ; 共享尾 = 0x444691 的说话段
    return 1
```
无条件消耗、无条件返回 1。

### `0x444691(target)` —— 復仇卡

```
    anim_fly; sprintf(buf,"%s\\n\\n復仇卡生效！", name); popup(buf,18)
    remove_card(target, 18)                   ; ★ 0x4446f0 call 0x441343
    say(target, 0, k); say([0x49910c], 2, k)  ; 施卡者（当前玩家）说话
    return 1
```

### `0x44476a(target, mode, amount)` —— 嫁禍卡（返回新目标；`-1` = 放弃）

```
    ret = -1; anim_fly(target)
    if player[target].whoPlays == 1:                     ; 真人
        cand = [p : player[p].whoPlays != 0 && p != target]
        if |cand| == 1:
            if confirm() == 1: ret = cand[0]
            else: return -1                              ; ★ 0x444863 —— 放弃直接返回，**不扣卡**
        else: ret = select_dialog(|cand|)                ; 0x440e1a
    else:                                                ; 电脑
        pick = mostHated(target)                         ; 0x40d2d3
        if pick == -1: pick = select_one_active(target)  ; 0x40d31c
        if   mode == 0: ret = pick
        elif mode == 1:                                  ; 过路费
            thr = priceIndex * (4000 + rand() % 4000)     ; idiv 4000 / add 4000
            if amount > player[target].cash or amount > thr: ret = pick
        elif mode == 2:                                  ; 查稅卡
            if priceIndex*4000 < 0.2 * player[target].cash: ret = pick
        ; mode >= 3 或 < 0 -> 保持 -1
    if ret == -1: return -1                              ; ★ 0x4449e7 je 0x444a53 —— **不扣卡**
    popup(19)
    remove_card(target, 19)                              ; ★ 0x4449ef call 0x441343
    say(target, 0); say(ret, 2)
    return ret
```

★★ **「放弃转嫁不消耗嫁禍卡」**：README §四之二 第 11 条的括注
「放弃转嫁时嫁祸照样被消耗（原版在 `cmp eax,-1` 之前就扣）」**与机器码不符**。
`0x4449e7 cmp ebx,-1 / 0x4449ea je 0x444a53` 就在扣卡指令 `0x4449ef` **之前**，
两个「放弃」出口（真人 `0x444863`、电脑 `0x444973`）都落在 `0x4449e7` 上。
本文件用 `UC_HOOK_CODE` 直接证明 `0x4449ec`（扣卡）**没有执行**。

### `0x4444bf()` —— 陷害卡(17) 的调用方（命中顺序 / 敌意 / 復仇）

```
    mask = human_dialog(0xe0c0710) or ai_default(0)      ; 参数在 [0x48be58]（0x41e6f2）
    if mask == 0: return 0                               ; ★ 选不到目标 -> 卡 17 不消耗
    remove_card(current, 17)                             ; ★ 0x4444fc —— 目标选定后立刻扣
    say(current, 3)
    idx = orig = ctz(mask)                               ; 0x40d293
    if idx >= 4: confine(idx, 5); refresh(); return mask ; 0x44467a 伪玩家支
    hostility_add(idx, current, 150 * priceIndex)        ; ★ 0x4445c1 call 0x40df69（**在防御卡之前**）
    if has_card(idx, 21): absolve(idx); return mask      ; ★ 免罪命中即止，不查 19、不入狱
    if has_card(idx, 19):
        n = blame_shift(idx, 0, 0)
        if n != -1: idx = n
    confine(idx, 4 if idx == current else 5)             ; 0x444619 push 5 / 0x444614 push 4
    say(idx, 1)
    if idx != orig: return mask                          ; ★ 0x444652 cmp ebx,edi / jne —— 被改写则**不查復仇**
    if has_card(orig, 18):
        revenge(orig)                                    ; 消耗 18
        confine(current, 5)                              ; ★★ 0x44466f push 5 —— 復仇**硬编码 5 天**
    return mask                                          ; 返回**掩码**，不是下标
```

夢遊卡(16) 的復仇支（`0x4443ef`–`0x444424`，本文件用 `eval_block` 驱动）：

```
    if final == original && has_card(original, 18):
        revenge(original)                        ; 消耗 18
        player[[0x49910c]].sleepDays(+0x37) = 5  ; ★ 0x44441d mov byte [eax+0x496b9f],5
```

查稅卡(26) 的防御链（`0x44530d` 起，本文件用 `eval_block` 驱动）：

```
    if has_card(target, 20):                 ; 0x44530d
        if use_free_card(target, current, tax) == 1:   ; 0x44532d call 0x444a60
            goto 0x445426 (成功；**跳过**嫁禍)          ; 0x445338 je 0x445426
    ; 落空 -> 0x44533e
    if has_card(target, 19) && tax > 2000:   ; 0x44533e / 0x44534e
        n = blame_shift(target, 2, 0); if n != -1: target = n
```

## 打桩清单（只打**已独立定案**的辅助；函数本身与四个处理函数全部真跑）

| VA | 原用途 | 桩 | 理由 |
|---|---|---|---|
| `0x00456de8` | CRT `memmove`（`remove_card` 内部调用） | 等价 `rep movsb`（保存 esi/edi）+ `ret` | 真身首条 `push es` 在 Unicorn 上报 `UC_ERR_WRITE_UNMAPPED`（§7.126(3) 已记录，三轮打桩绕不过）。本桩只替代 CRT 搬运，**调用点仍是原版 `0x441343`** |
| `0x00456f2d` | CRT `rand()` | `mov eax,[槽]; ret` | 由 `setup()` 注入，便于钉门槛 |
| `0x0041d476` | 落点/镜头动画 | `xor eax,eax; ret` | 纯表现层 |
| `0x00441f73` | 卡牌弹窗 | `xor eax,eax; ret` | 纯表现层（喂给它的 sprintf 缓冲同理） |
| `0x00457110` | CRT `sprintf` | `xor eax,eax; ret` | 输出只进上面的弹窗桩；玩家名字指针可能非法 |
| `0x0044ef41` | 说话/刷屏 | 记录 `(player, mode)` 到暂存区 | 纯表现层；本测试用它**观察**调用了谁 |
| `0x0041d546` | `refresh_map`（重绘标志 + 停顿） | `xor eax,eax; ret` | 纯表现层 |
| `0x00440ba8` | 确认框 | `mov eax,[槽]; ret` | UI；本测试要控制「是/否」 |
| `0x00440e1a` | 多候选选择框 | `mov eax,[槽]; ret` | UI |
| `0x00440cac` | 停顿/翻页 | `xor eax,eax; ret` | 纯表现层 |
| `0x00452946` | 取名字串 | `xor eax,eax; ret` | 纯表现层 |
| `0x0040e669` | 镜头动画 | `xor eax,eax; ret` | 纯表现层 |
| `0x0043d593` | `send_to_*`（关押+传送） | 记录 `(index, days)` 到暂存区 | 其自身语义已由 `test_confinement_teleport.py` 48/48 驱动；本测试要的正是**传进去的 (下标, 天数)** |
| `0x0040d2d3` | 最恨的人 | `mov eax,[槽]; ret` | 候选筛选；本测试要控制候选 |
| `0x0040d31c` | `select_one_active_player` | `mov eax,[槽]; ret` | 同上 |
| `0x00446ae8` | 真人目标选择框 | `xor eax,eax; ret` | 本测试一律走电脑支 `0x41e6f2` |

**真跑（未打桩）**：`0x444a60`、`0x444bb2`、`0x444691`、`0x44476a`、`0x4444bf`
以及 `0x4413ad`（has_card）、`0x441343`（remove_card）、`0x40d293`（ctz）、
`0x41e6f2`（读 `[0x48be58]`）、`0x40df69`（敌意写入）。

## 复刻对照（结论见文件末尾 `REMAKE_VERDICT`）

| 规则 | 机器码 | 复刻 | 裁决 |
|---|---|---|---|
| 防御顺序 21 → 19，命中即止 | `0x4445c9`→`0x4445e7` | `passive.ts:74-80` / `:108-122` | MATCH |
| 命中即消耗 21 / 19 | `0x444c11` / `0x4449ef` | `passive.ts:109-120` | MATCH |
| **放弃转嫁不消耗 19** | `0x4449e7`/`0x4449ea`/`0x4449ef` | `passive.ts:115-119`（先扣再选） | **DISCREPANCY** |
| 復仇 5 天硬编码 | `0x44466f` / `0x44441d` | `passive.ts:132`、`frame.ts:236` | MATCH |
| 免费卡 AI 门槛 `3000+rand%3000` | `0x444a9b`–`0x444ad3` | `toll-flow.ts:85-88`；`tax.ts:90` | 过路费 MATCH / **查稅 DISCREPANCY** |
| 嫁禍 mode 1 门槛 `4000+rand%4000` | `0x4448fc`–`0x444932` | `toll-flow.ts:129-130` | MATCH |
| 嫁禍 mode 2 门槛 `0.2·cash > 4000·pi` | `0x444934`–`0x44496f` | `tax.ts:115`（无此门槛） | **DISCREPANCY** |
| 选不到目标不扣施害卡 | `0x4444ed` | `frame.ts:143-154` 之后才扣 | MATCH |
| 敌意在防御卡之前 | `0x4445c1` | `frame.ts:147-149` | MATCH |

跑法：`cd rich4-spec && .venv/bin/python tests/test_passive_cards.py`
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402

# ── 被测函数 / 真跑的辅助 ────────────────────────────────────────────────
FREE = 0x444A60          # 免費卡(20) 处理
AMNESTY = 0x444BB2       # 免罪卡(21) 处理
REVENGE = 0x444691       # 復仇卡(18) 处理
SCAPEGOAT = 0x44476A     # 嫁禍卡(19) 处理
FRAME = 0x4444BF         # 陷害卡(17) 的调用方
HAS_CARD = 0x4413AD
REMOVE_CARD = 0x441343
CTZ = 0x40D293           # 位掩码 -> 下标（真跑）
AI_DEFAULT = 0x41E6F2    # 读 [0x48be58]（真跑）
HOSTILITY = 0x40DF69     # 敌意写入（真跑）
PRNG = 0x456F2D
MEMMOVE = 0x456DE8

# ── 全局 / 玩家结构 ────────────────────────────────────────────────────
PLAYER_BASE = 0x496B68
PS = 0x68
P_NAME = 0x00
P_CHAR = 0x13
P_WHOPLAYS = 0x15
P_CASH = 0x1C
P_BANK = 0x20
P_SLEEPDAYS = 0x37
P_ALLIED = 0x41
P_HOSTILITY = 0x4C
HAND = 0x499120
CUR = 0x49910C
PRICE_INDEX = 0x4990E8
NUM_PLAYERS = 0x499114
CARD_PARAM0 = 0x48BE58    # 陷害卡的 AI 目标（位掩码）

# ── 关键分支地址（UC_HOOK_CODE 用；全部逐条反汇编核对）────────────────
A_FREE_HUMAN = 0x444AD8
A_FREE_AI_RAND = 0x444A9B
A_FREE_USE = 0x444ACA
A_FREE_DECLINE = 0x444AD1
A_FREE_REMOVE20 = 0x444B2D
A_FREE_TAIL = 0x444BA0
A_AMNESTY_REMOVE21 = 0x444C11
A_REVENGE_REMOVE18 = 0x4446F0
A_BLAME_ACCEPT = 0x444971
A_BLAME_SKIP = 0x444973
A_BLAME_DECLINE_RET = 0x444A53
A_BLAME_REMOVE19 = 0x4449EF
A_FRAME_REMOVE17 = 0x4444FC
A_FRAME_HOSTILITY = 0x4445C1
A_FRAME_HAS21 = 0x4445CC
A_FRAME_ABSOLVE = 0x4445DA
A_FRAME_HAS19 = 0x4445EA
A_FRAME_BLAME = 0x4445FC
A_FRAME_CONFINE = 0x44461C
A_FRAME_CMP_REVENGE = 0x444652
A_FRAME_REVENGE = 0x444667
A_FRAME_REVENGE_CONFINE = 0x44467D
A_FRAME_PSEUDO = 0x44467A
A_TAX_CHAIN = 0x44530D
A_TAX_JNE_SCAPEGOAT = 0x44533E
A_TAX_SKIP_TO_END = 0x445426
STACK_TOP = 0x53FF00

# ── 暂存区（不在 reset 快照里 ⇒ 每次 setup 显式写）─────────────────────
S = SCRATCH_BASE
RAND_SLOT = S + 0x800
MOSTH_SLOT = S + 0x8C0
SEL_SLOT = S + 0x8C4
CONFIRM_SLOT = S + 0x8C8
MULTI_SLOT = S + 0x8CC
CONF_LOG = S + 0xC00
CONF_COUNT = S + 0xC80
SPEECH_COUNT = S + 0xD00
SPEECH_P = S + 0xD04
SPEECH_MODE = S + 0xD08

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<12} 期望 {want!s}")
    return ok


# ── 桩的机器码 ─────────────────────────────────────────────────────────
def ret0():
    return b"\x31\xC0\xC3"


def ld32(slot):
    return b"\xA1" + struct.pack("<I", slot) + b"\xC3"


def stub_memmove():
    """等价前向 `memmove`，且保存 esi/edi（`remove_card` 依赖它们跨调用存活）。"""
    return (b"\x56\x57"                                  # push esi / push edi
            b"\x8B\x7C\x24\x0C"                          # mov edi,[esp+0xC]  dest
            b"\x8B\x74\x24\x10"                          # mov esi,[esp+0x10] src
            b"\x8B\x4C\x24\x14"                          # mov ecx,[esp+0x14] n
            b"\xF3\xA4"                                  # rep movsb
            b"\x8B\xC7"                                  # mov eax,edi
            b"\x5F\x5E\xC3")                             # pop edi / pop esi / ret


def stub_confine():
    """记录 (index, days) 到 CONF_LOG，计数到 CONF_COUNT，返回 0。"""
    c = b"\x8B\x0D" + struct.pack("<I", CONF_COUNT)      # mov ecx,[CONF_COUNT]
    c += b"\x8B\x44\x24\x04"                             # mov eax,[esp+4]
    c += b"\x89\x04\xCD" + struct.pack("<I", CONF_LOG)   # mov [ecx*8+CONF_LOG],eax
    c += b"\x8B\x44\x24\x08"                             # mov eax,[esp+8]
    c += b"\x89\x04\xCD" + struct.pack("<I", CONF_LOG + 4)
    c += b"\x41"                                         # inc ecx
    c += b"\x89\x0D" + struct.pack("<I", CONF_COUNT)     # mov [CONF_COUNT],ecx
    c += b"\x31\xC0\xC3"
    return c


def stub_speech():
    """记录最近一次 (player, mode)，并计数。"""
    c = b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", SPEECH_P)
    c += b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", SPEECH_MODE)
    c += b"\xA1" + struct.pack("<I", SPEECH_COUNT) + b"\x40"
    c += b"\xA3" + struct.pack("<I", SPEECH_COUNT)
    c += b"\xC3"
    return c


def wu32(emu, addr, v):
    """写 32 位无符号（`Emu.write32` 走 `<i`，-1 之类的哨兵会炸）。"""
    emu.write(addr, struct.pack("<I", v & 0xFFFFFFFF))


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(MEMMOVE, stub_memmove())
        self.emu.patch(PRNG, ld32(RAND_SLOT))
        for va in (0x41D476, 0x441F73, 0x457110, 0x41D546, 0x440CAC,
                   0x40E669, 0x452946, 0x446AE8):
            self.emu.patch(va, ret0())
        self.emu.patch(0x44EF41, stub_speech())
        self.emu.patch(0x43D593, stub_confine())
        self.emu.patch(0x440BA8, ld32(CONFIRM_SLOT))
        self.emu.patch(0x440E1A, ld32(MULTI_SLOT))
        self.emu.patch(0x40D2D3, ld32(MOSTH_SLOT))
        self.emu.patch(0x40D31C, ld32(SEL_SLOT))
        self.clear()

    # ── 每用例状态 ────────────────────────────────────────────────────
    def clear(self):
        self.hands = {}
        self.who = [0, 0, 0, 0]
        self.cash = [100_000, 100_000, 100_000, 100_000]
        self.pi = 1
        self.rand = 0
        self.confirm = 1
        self.mosth = -1
        self.sel = -1
        self.multi = 0
        self.mask = 0
        self.tax = 0
        self.tax_target = 1
        self.tax_current = 0

    def _setup_base(self, emu):
        emu.write32(PRICE_INDEX, self.pi)
        emu.write32(NUM_PLAYERS, 4)
        emu.write32(CUR, self.tax_current)
        wu32(emu, RAND_SLOT, self.rand)
        wu32(emu, CONFIRM_SLOT, self.confirm)
        wu32(emu, MULTI_SLOT, self.multi)
        wu32(emu, MOSTH_SLOT, self.mosth)
        wu32(emu, SEL_SLOT, self.sel)
        emu.write32(CONF_COUNT, 0)
        emu.write32(SPEECH_COUNT, 0)
        wu32(emu, SPEECH_P, 0xFFFFFFFF)
        wu32(emu, SPEECH_MODE, 0xFFFFFFFF)
        wu32(emu, CARD_PARAM0, self.mask)
        emu.write(HAND, b"\x00" * 60)
        for p, cs in self.hands.items():
            for i, c in enumerate(cs):
                emu.write8(HAND + p * 15 + i, c)
        for p in range(4):
            pb = PLAYER_BASE + p * PS
            emu.write8(pb + P_WHOPLAYS, self.who[p])
            emu.write8(pb + P_CHAR, p)
            emu.write32(pb + P_NAME, 0x4630F4)
            emu.write32(pb + P_CASH, self.cash[p])
            emu.write32(pb + P_BANK, 0)
            emu.write8(pb + P_ALLIED, 0)
            emu.write8(pb + P_SLEEPDAYS, 0)
            for j in range(4):
                emu.write32(pb + P_HOSTILITY + 4 * j, 0)

    def call(self, va, args, extra=None):
        def s(emu):
            self._setup_base(emu)
            if extra is not None:
                extra(emu)
        return self.emu.call(va, args, setup=s)

    def call_traced(self, va, args, extra=None):
        seen = []

        def hook(mu, address, size, user):
            seen.append(address)

        h = self.emu.mu.hook_add(UC_HOOK_CODE, hook)
        try:
            r = self.call(va, args, extra)
        finally:
            self.emu.mu.hook_del(h)
        return r, set(seen)

    def block(self, start, stop, regs, extra=None):
        def s(emu):
            self._setup_base(emu)
            emu.write32(STACK_TOP + 0x94, self.tax & 0xFFFFFFFF)
            if extra is not None:
                extra(emu)
        return self.emu.eval_block(start, stop, regs, setup=s)

    # ── 回读 ──────────────────────────────────────────────────────────
    def hand(self, p):
        return [self.emu.read8(HAND + p * 15 + i) for i in range(15)]

    def hand_nz(self, p):
        return [c for c in self.hand(p) if c != 0]

    def confines(self):
        n = self.emu.read32(CONF_COUNT)
        return [(self.emu.read32(CONF_LOG + 8 * i),
                 self.emu.read32(CONF_LOG + 8 * i + 4)) for i in range(n)]

    def speech_count(self):
        return self.emu.read32(SPEECH_COUNT)

    def speech_last(self):
        return self.emu.read32(SPEECH_P), self.emu.read32(SPEECH_MODE)

    def hostility(self, a, b):
        return self.emu.read32(PLAYER_BASE + a * PS + P_HOSTILITY + 4 * b)


def main():
    print("差分测试 · 被动防御卡族（免費 20 / 免罪 21 / 嫁禍 19 / 復仇 18）")
    print("主目标 0x444a60（免費卡），含 0x444bb2 / 0x44476a / 0x444691 / 0x4444bf\n")
    w = World()

    # ══════════════════════════════════════════════════════════════════
    print("[A] 0x444a60 免費卡 · 电脑门槛 = pi × (3000 + rand()%3000)，判定用 `>`")
    def free_ai(amount, cash=100_000, rand=0, pi=1, cards=(20,), target=0):
        w.clear()
        w.hands = {target: list(cards)}
        w.cash[target] = cash
        w.pi = pi
        w.rand = rand
        return w.call(FREE, [target, 1, amount])

    r = free_ai(2999)
    case("A1 amount=2999 < 3000 ⇒ 不用，返回 0", r["eax"], 0)
    case("A2 同上：卡 20 仍在手牌", w.hand_nz(0), [20])

    r = free_ai(3000)
    case("A3 ★ 边界：amount == 门槛(3000) ⇒ 不用（jge 跳过）", r["eax"], 0)
    case("A4 同上：卡 20 仍在手牌", w.hand_nz(0), [20])

    r = free_ai(3001)
    case("A5 amount=3001 > 3000 ⇒ 用，返回 1", r["eax"], 1)
    case("A6 用后卡 20 被消耗", w.hand_nz(0), [])

    r = free_ai(5999, rand=2999)
    case("A7 rand=2999 ⇒ 门槛 5999；amount == 5999 ⇒ 不用", r["eax"], 0)
    r = free_ai(6000, rand=2999)
    case("A8 amount=6000 ⇒ 用", r["eax"], 1)

    r = free_ai(6000, rand=0, pi=2)
    case("A9 ★ 门槛随物价指数放大：pi=2、rand=0 ⇒ 6000；amount == 6000 ⇒ 不用", r["eax"], 0)
    r = free_ai(6001, rand=0, pi=2)
    case("A10 amount=6001 ⇒ 用", r["eax"], 1)

    r = free_ai(1001, cash=1000, rand=2999, pi=1000)
    case("A11 ★ 另一条腿：amount > 现金 ⇒ 即使远低于门槛也用", r["eax"], 1)
    r = free_ai(1000, cash=1000, rand=2999, pi=1000)
    case("A12 ★ amount == 现金 ⇒ 不 `jg`；门槛又远高 ⇒ 不用", r["eax"], 0)

    w.clear()
    w.hands = {0: [7, 20, 3]}
    w.cash[0] = 100_000
    r = w.call(FREE, [0, 1, 999_999])
    case("A13 消耗的是**卡 20**且左移紧凑（[7,20,3] ⇒ [7,3]）", w.hand(0)[:4], [7, 3, 0, 0])
    case("A14 返回值就是 1", r["eax"], 1)

    w.clear()
    w.hands = {0: [7, 3]}
    r = w.call(FREE, [0, 1, 999_999])
    case("A15 ★★ 本函数**不查 has_card**：手里没有 20 也返回 1", r["eax"], 1)
    case("A16 手牌因此不变（remove_card 找不到）", w.hand(0)[:3], [7, 3, 0])

    # ══════════════════════════════════════════════════════════════════
    print("\n[B] 0x444a60 · 真人支（whoPlays == 1）= 确认框，且**不套**电脑门槛")
    def free_human(amount, confirm, cards=(20,)):
        w.clear()
        w.hands = {0: list(cards)}
        w.who = [1, 0, 0, 0]
        w.confirm = confirm
        return w.call(FREE, [0, 1, amount])

    r = free_human(999_999, 0)
    case("B1 真人答『否』⇒ 返回 0", r["eax"], 0)
    case("B2 ★ 答『否』卡 20 **不消耗**", w.hand_nz(0), [20])
    case("B3 ★ 答『否』一句台词都不说", w.speech_count(), 0)

    r = free_human(999_999, 1)
    case("B4 真人答『是』⇒ 返回 1", r["eax"], 1)
    case("B5 答『是』卡 20 被消耗", w.hand_nz(0), [])
    case("B6 答『是』说两句（本人 + 施卡者）", w.speech_count(), 2)

    r = free_human(1, 1)
    case("B7 ★★ 真人支不吃电脑门槛：amount=1 也能用", r["eax"], 1)

    r = free_human(999_999, 2)
    case("B8 ★★ 真人支的返回 = 确认框的**原样**返回值（esi），不是归一的 0/1", r["eax"], 2)
    case("B9 ★★ 且只有『恰为 1』才算用：返回 2 时卡留着", w.hand_nz(0), [20])
    case("B10 返回 2 时不说台词", w.speech_count(), 0)

    # ══════════════════════════════════════════════════════════════════
    print("\n[C] 0x444a60 · 消耗点 / 说话对象 / 返回编码（UC_HOOK_CODE 直证分支）")
    w.clear()
    w.hands = {0: [20]}
    r, seen = w.call_traced(FREE, [0, 1, 999_999])
    case("C1 使用时执行到扣卡点 0x444b2d", A_FREE_REMOVE20 in seen, True)
    case("C2 ★ 使用时不走『不用』出口 0x444ad1", A_FREE_DECLINE in seen, False)
    case("C3 电脑门槛在电脑支里（0x444a9b 随机）", A_FREE_AI_RAND in seen, True)
    case("C4 电脑支不进真人对话框 0x444ad8", A_FREE_HUMAN in seen, False)

    w.clear()
    w.hands = {0: [20]}
    r, seen = w.call_traced(FREE, [0, 1, 100])
    case("C5 不用时执行到 0x444ad1", A_FREE_DECLINE in seen, True)
    case("C6 ★ 不用时**没有**执行扣卡点 0x444b2d", A_FREE_REMOVE20 in seen, False)
    case("C7 不用时也要 refresh（0x444ba0）", A_FREE_TAIL in seen, True)

    w.clear()
    w.hands = {0: [20]}
    w.call(FREE, [0, 1, 999_999])
    case("C8 ★ payer=1 时最后一句台词是 payer、mode=1", w.speech_last(), (1, 1))
    case("C9 两句台词（本人 + payer）", w.speech_count(), 2)

    w.clear()
    w.hands = {0: [20]}
    r = w.call(FREE, [0, -1, 999_999])
    case("C10 ★ payer == -1 ⇒ 只对本人说一句", w.speech_count(), 1)
    case("C11 那一句是 (本人, mode 0)", w.speech_last(), (0, 0))
    case("C12 payer=-1 仍然返回 1", r["eax"], 1)

    # ══════════════════════════════════════════════════════════════════
    print("\n[D] 0x444bb2 免罪卡(21) · 无条件消耗 + 返回 1")
    w.clear()
    w.hands = {1: [21]}
    r, seen = w.call_traced(AMNESTY, [1])
    case("D1 返回 1", r["eax"], 1)
    case("D2 卡 21 被消耗", w.hand_nz(1), [])
    case("D3 执行到扣卡点 0x444c11", A_AMNESTY_REMOVE21 in seen, True)
    case("D4 说一句 (目标, mode 0)", (w.speech_count(), w.speech_last()), (1, (1, 0)))

    w.clear()
    w.hands = {1: [7, 21, 3]}
    w.call(AMNESTY, [1])
    case("D5 只动 21：`[7,21,3] ⇒ [7,3]`", w.hand(1)[:3], [7, 3, 0])

    w.clear()
    w.hands = {1: [7, 3]}
    r = w.call(AMNESTY, [1])
    case("D6 ★ 没卡也返回 1（消耗无条件，has_card 在调用方）", r["eax"], 1)
    case("D7 手牌不变", w.hand_nz(1), [7, 3])

    w.clear()
    w.hands = {1: [21, 19]}
    w.call(AMNESTY, [1])
    case("D8 ★★ 免罪只消耗 21，19 原样留下（命中即止）", w.hand_nz(1), [19])

    # ══════════════════════════════════════════════════════════════════
    print("\n[E] 0x444691 復仇卡(18) · 无条件消耗 18 + 施卡者说话(mode 2)")
    w.clear()
    w.hands = {1: [18]}
    w.tax_current = 2
    r, seen = w.call_traced(REVENGE, [1])
    case("E1 返回 1", r["eax"], 1)
    case("E2 卡 18 被消耗", w.hand_nz(1), [])
    case("E3 执行到扣卡点 0x4446f0", A_REVENGE_REMOVE18 in seen, True)
    case("E4 两句台词", w.speech_count(), 2)
    case("E5 ★ 最后一句对**施卡者**（[0x49910c]=2）、mode=2", w.speech_last(), (2, 2))

    w.clear()
    w.hands = {1: [5, 18, 6]}
    w.call(REVENGE, [1])
    case("E6 只动 18：`[5,18,6] ⇒ [5,6]`", w.hand(1)[:3], [5, 6, 0])

    w.clear()
    w.hands = {1: [5]}
    r = w.call(REVENGE, [1])
    case("E7 没卡也返回 1", r["eax"], 1)
    case("E8 手牌不变", w.hand_nz(1), [5])

    # ══════════════════════════════════════════════════════════════════
    print("\n[F] 0x44476a 嫁禍卡(19) · 电脑支三档门槛 + ★ 放弃不扣卡")
    def blame(target, mode, amount, cash=100_000, rand=0, pi=1, mosth=2, sel=-1,
              cards=(19,), trace=False):
        w.clear()
        w.hands = {target: list(cards)}
        w.cash[target] = cash
        w.pi = pi
        w.rand = rand
        w.mosth = mosth
        w.sel = sel
        if trace:
            return w.call_traced(SCAPEGOAT, [target, mode, amount])
        return w.call(SCAPEGOAT, [target, mode, amount])

    r, seen = blame(0, 0, 0, mosth=2, trace=True)
    case("F1 mode 0：最恨的人=2 ⇒ 返回 2", r["signed"], 2)
    case("F2 卡 19 被消耗", w.hand_nz(0), [])
    case("F3 执行到扣卡点 0x4449ef", A_BLAME_REMOVE19 in seen, True)
    case("F4 两句台词，最后一句 (新目标 2, mode 2)", w.speech_last(), (2, 2))

    r, seen = blame(0, 0, 0, mosth=-1, sel=-1, trace=True)
    case("F5 ★★ 电脑支无人可嫁（两个挑选器都 -1）⇒ 返回 -1", r["signed"], -1)
    case("F6 ★★ 放弃时卡 19 **不被消耗**", w.hand_nz(0), [19])
    case("F7 ★★ 放弃时不执行扣卡点 0x4449ec/0x4449ef", A_BLAME_REMOVE19 in seen, False)
    case("F8 ★ 放弃走 0x444a53 返回", A_BLAME_DECLINE_RET in seen, True)
    case("F9 放弃时 0x4449e7 的 cmp 有执行", 0x4449E7 in seen, True)

    r = blame(0, 0, 0, mosth=-1, sel=3)
    case("F10 mode 0：最恨无人时退回 select_one_active=3 ⇒ 返回 3", r["signed"], 3)

    r = blame(0, 1, 4000, rand=0, pi=1)
    case("F11 mode 1 门槛 = pi×(4000+rand%4000)=4000；amount == 4000 ⇒ 不用", r["signed"], -1)
    case("F12 同上：19 留着", w.hand_nz(0), [19])
    r = blame(0, 1, 4001, rand=0, pi=1)
    case("F13 amount=4001 ⇒ 嫁禍，返回候选", r["signed"], 2)
    r = blame(0, 1, 7999, rand=3999, pi=1)
    case("F14 rand=3999 ⇒ 门槛 7999；amount == 7999 ⇒ 不用", r["signed"], -1)
    r = blame(0, 1, 8000, rand=3999, pi=1)
    case("F15 amount=8000 ⇒ 嫁禍", r["signed"], 2)
    r = blame(0, 1, 1001, cash=1000, rand=3999, pi=1000)
    case("F16 mode 1 另一条腿：amount > 现金 ⇒ 用", r["signed"], 2)
    r = blame(0, 1, 1000, cash=1000, rand=3999, pi=1000)
    case("F17 amount == 现金且远低门槛 ⇒ 不用", r["signed"], -1)

    r = blame(0, 2, 0, cash=100_000, pi=1)
    case("F18 mode 2：0.2×cash=20000 > 4000×pi=4000 ⇒ 嫁禍", r["signed"], 2)
    r = blame(0, 2, 0, cash=1000, pi=1)
    case("F19 mode 2：0.2×cash=200 < 4000 ⇒ 不用，返回 -1", r["signed"], -1)
    case("F20 同上：19 留着", w.hand_nz(0), [19])
    r = blame(0, 2, 0, cash=100_000, pi=100)
    case("F21 mode 2：物价指数放大 ⇒ 20000 < 400000 ⇒ 不用", r["signed"], -1)
    r = blame(0, 2, 0, cash=20000, pi=1)
    case("F22 ★ mode 2 边界：0.2×cash == 4000 ⇒ 不用（不是 >）", r["signed"], -1)
    r = blame(0, 2, 0, cash=20001, pi=1)
    case("F23 ★ mode 2 边界：4000.2 > 4000 ⇒ 嫁禍", r["signed"], 2)

    r = blame(0, 3, 999_999, cash=1000, pi=1)
    case("F24 mode 3（未知档）⇒ 恒放弃，返回 -1", r["signed"], -1)
    case("F25 同上：19 留着", w.hand_nz(0), [19])
    r = blame(0, -1, 999_999, cash=1000, pi=1)
    case("F26 mode -1 ⇒ 恒放弃", r["signed"], -1)

    r = blame(0, 0, 0, mosth=2, cards=(19, 18))
    case("F27 嫁禍成功也**不碰**目标的復仇卡 18", w.hand_nz(0), [18])

    # ══════════════════════════════════════════════════════════════════
    print("\n[G] 0x44476a 真人支（whoPlays == 1）= 唯一候选要确认；答否不扣卡")
    def blame_human(confirm):
        w.clear()
        w.hands = {0: [19]}
        w.who = [1, 1, 0, 0]          # 候选恰 1 个：玩家 1
        w.confirm = confirm
        return w.call(SCAPEGOAT, [0, 0, 0])

    r = blame_human(1)
    case("G1 唯一候选 + 答『是』⇒ 返回候选 1", r["signed"], 1)
    case("G2 卡 19 被消耗", w.hand_nz(0), [])

    w.clear()
    w.hands = {0: [19]}
    w.who = [1, 1, 0, 0]
    w.confirm = 0
    r, seen = w.call_traced(SCAPEGOAT, [0, 0, 0])
    case("G3 ★★ 真人答『否』⇒ 返回 -1", r["signed"], -1)
    case("G4 ★★ 真人放弃时卡 19 **不消耗**", w.hand_nz(0), [19])
    case("G5 ★★ 真人放弃时扣卡点 0x4449ef 不执行", A_BLAME_REMOVE19 in seen, False)

    # ══════════════════════════════════════════════════════════════════
    print("\n[H] 0x4444bf 陷害卡(17) 调用方 · 命中顺序 / 敌意 / 復仇 5 天 / 消耗")
    def frame(mask, hands, who=(0, 0, 0, 0), pi=1, mosth=-1, sel=-1):
        w.clear()
        w.hands = dict(hands)
        w.who = list(who)
        w.pi = pi
        w.mask = mask
        w.mosth = mosth
        w.sel = sel
        return w.call(FRAME, [])

    # --- H1-H4: 免罪优先，命中即止 ---
    w.clear()
    w.hands = {0: [17], 1: [21, 19]}
    w.mask = 2
    r, seen = w.call_traced(FRAME, [])
    case("H1 ★ 目标选择后立刻扣施害卡 17（执行 0x4444fc）", A_FRAME_REMOVE17 in seen, True)
    case("H2 ★★ 免罪(21) 命中：扣 21，19 **不扣**", w.hand_nz(1), [19])
    case("H3 ★★ 免罪命中即止：不查 19（0x4445ea 未执行）", A_FRAME_HAS19 in seen, False)
    case("H4 ★★ 免罪命中：不入狱（confine 0 次）", w.confines(), [])
    case("H5 返回值 = 目标**掩码** 2（不是下标）", r["eax"], 2)
    case("H6 免罪命中仍记敌意 150×pi（pi=1）", w.hostility(1, 0), 150)

    w.clear()
    w.hands = {0: [17], 1: [21]}
    w.mask = 2
    w.pi = 3
    w.call(FRAME, [])
    case("H7 敌意随物价指数：pi=3 ⇒ 450", w.hostility(1, 0), 450)
    case("H8 ★ 敌意方向 = 目标对**施卡者**（[目标][current]）", w.hostility(1, 0), 450)
    case("H9 反向槽仍是 0（不是对称写入）", w.hostility(0, 1), 0)

    # --- H10-H11: 无防御卡 -> 入狱 5 天 ---
    w.clear()
    w.hands = {0: [17], 1: []}
    w.mask = 2
    w.call(FRAME, [])
    case("H10 无防御卡：目标 != 施卡者 ⇒ 入狱 5 天", w.confines(), [(1, 5)])
    case("H11 受害者的卡 17 已扣（施害卡消耗）", w.hand_nz(0), [])

    w.clear()
    w.hands = {0: [17]}
    w.mask = 1
    w.call(FRAME, [])
    case("H12 ★ 目标 == 施卡者 ⇒ **4 天**（不是 5）", w.confines(), [(0, 4)])

    w.clear()
    w.hands = {0: [17]}
    w.mask = 0x10                 # 下标 4 = 伪玩家
    r, seen = w.call_traced(FRAME, [])
    case("H13 伪玩家支（下标 ≥ 4）⇒ 入狱 5 天", w.confines(), [(4, 5)])
    case("H14 ★ 伪玩家支走 0x44467a", A_FRAME_PSEUDO in seen, True)
    case("H15 ★ 伪玩家支**不**记敌意、不查防御卡", A_FRAME_HOSTILITY in seen, False)
    case("H16 伪玩家支照样扣施害卡 17", w.hand_nz(0), [])
    case("H17 返回值仍是掩码 0x10", r["eax"], 0x10)

    w.clear()
    w.hands = {0: [17]}
    w.mask = 0
    r = w.call(FRAME, [])
    case("H18 ★★ 选不到目标（mask=0）⇒ 返回 0 且**卡 17 不消耗**", (r["eax"], w.hand_nz(0)), (0, [17]))

    # --- H19-H25: 嫁禍改写 / 復仇 ---
    w.clear()
    w.hands = {0: [17], 1: [19]}
    w.mask = 2
    w.mosth = 2
    r, seen = w.call_traced(FRAME, [])
    case("H19 嫁禍成功：19 被消耗", w.hand_nz(1), [])
    case("H20 关押改写给**候选 2**、5 天", w.confines(), [(2, 5)])
    case("H21 ★★ 被改写（ebx != edi）⇒ 不查復仇（0x444667 未执行）", A_FRAME_REVENGE in seen, False)
    case("H22 但仍执行了 `cmp ebx,edi`（0x444652）", A_FRAME_CMP_REVENGE in seen, True)

    w.clear()
    w.hands = {0: [17], 1: [19, 18]}
    w.mask = 2
    w.mosth = -1
    w.sel = -1
    r, seen = w.call_traced(FRAME, [])
    case("H23 ★★★ 放弃转嫁：19 **不扣**（0x4449ef 未执行）", A_BLAME_REMOVE19 in seen, False)
    case("H24 ★★★ 放弃转嫁仍查復仇：18 被消耗", 18 not in w.hand_nz(1), True)
    case("H25 ★★ 先后两次关押：(原目标,5) 然后 (施卡者,5)", w.confines(), [(1, 5), (0, 5)])
    case("H26 ★★ 復仇的执行点 0x444667 有跑到", A_FRAME_REVENGE in seen, True)
    case("H27 ★★ 復仇的关押走 0x44467d（push 5）", A_FRAME_REVENGE_CONFINE in seen, True)
    case("H28 ★★ 放弃转嫁时 19 留、18 扣（两者命运不同）", w.hand_nz(1), [19])

    w.clear()
    w.hands = {0: [17], 1: [18]}
    w.mask = 2
    w.call(FRAME, [])
    case("H29 只有復仇卡：先是 (目标,5) 再 (施卡者,5)", w.confines(), [(1, 5), (0, 5)])
    case("H30 18 被消耗", w.hand_nz(1), [])

    w.clear()
    w.hands = {0: [17], 1: [19, 18]}
    w.mask = 2
    w.mosth = 0                    # 转嫁给**施卡者自己**
    r = w.call(FRAME, [])
    case("H31 转嫁给施卡者自己 ⇒ 关押按『自己』= 4 天", w.confines(), [(0, 4)])
    case("H32 ★ 被改写后 18 仍留着（不查復仇）", w.hand_nz(1), [18])
    case("H33 19 已消耗", 19 not in w.hand_nz(1), True)

    w.clear()
    w.hands = {0: [17], 1: []}
    w.mask = 4
    r = w.call(FRAME, [])
    case("H34 返回编码：mask=4 ⇒ 返回 4（**掩码**，不是下标 2）", r["eax"], 4)
    case("H35 关押的是从掩码解出的下标 2", w.confines(), [(2, 5)])

    # ══════════════════════════════════════════════════════════════════
    print("\n[I] 0x4443ef–0x444424 夢遊卡的復仇支 · 硬编码 5 天（eval_block 驱动）")
    w.clear()
    w.hands = {1: [18]}
    w.tax_current = 0
    r = w.block(0x4443EF, 0x444424, {"ebx": 1, "ebp": 1})
    case("I1 ★★ 施卡者(0)的梦游天数 +0x37 被写成 5", w.emu.read8(PLAYER_BASE + P_SLEEPDAYS), 5)
    case("I2 目标的 18 被消耗", w.hand_nz(1), [])
    case("I3 两句台词（目标 + 施卡者）", w.speech_count(), 2)

    # ══════════════════════════════════════════════════════════════════
    print("\n[J] 查稅卡的防御链 0x44530d · ★ 免費(20) 先于 嫁禍(19)，用了就跳过")
    def tax_chain(tax, target, cards, pi=1, stop=A_TAX_SKIP_TO_END, mosth=2):
        w.clear()
        w.hands = {target: list(cards)}
        w.pi = pi
        w.tax = tax
        w.mosth = mosth
        return w.block(A_TAX_CHAIN, stop, {"ebx": target, "ebp": 0, "esi": tax})

    r = tax_chain(999_999, 1, [20, 19])
    case("J1 ★★ 免費卡用掉 ⇒ 跳到 0x445426（不再查嫁禍）", r["regs"]["eax"], 1)
    case("J2 20 被消耗、19 留着", w.hand_nz(1), [19])
    r = tax_chain(100, 1, [20, 19], stop=A_TAX_JNE_SCAPEGOAT)
    case("J3 ★★ 免費卡判定为『不用』⇒ 落到 0x44533e（继续查嫁禍）", r["regs"]["eax"], 0)
    case("J4 ★★ 落空时 20 **不消耗**", w.hand_nz(1), [20, 19])
    r = tax_chain(999_999, 1, [19], stop=A_TAX_JNE_SCAPEGOAT)
    case("J5 目标没有 20 ⇒ 直接落到 0x44533e", r["regs"]["eax"], 0)
    case("J6 19 尚未被动（这一段还没查它）", w.hand_nz(1), [19])

    # ══════════════════════════════════════════════════════════════════
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
