#!/usr/bin/env python3
"""
通道 2 差分测试 · **烏龜卡（卡片 30）的 AI 目标选择** `0x00420970`（1322 B）

复刻侧对应 `packages/core/src/ai/card-policy.ts` 的 `wugui`（`@source 0x00420970`，行 846-946）。
本函数是 **AI 出牌跳表成员**（`ai.md:759` 的 action 30），**没有 `call` 调用者** ⇒
建图工具不收，用 `rich4-remake/tools/disasm.py va 0x00420970` 按需反汇编。

## 语义（1322 B 全程读完，逐地址核对）

```
0x420970():                                          ; 无参数，帧 0x18 字节
    best = 0                                         ; [esp+8]，就是返回值
    [esp+4] = 0                                      ; ★ 死变量：全函数只有两处写它，都是写 0
                                                     ;   ⇒ 两处 `cmp [esp+4],0 / jne` 恒不跳（见下）

    ; ═══ 第 1 段 · 「对自己」：前瞻 3 格 ═══
    if (0x40b221(cur, 3) != 0) goto visible_scan      ; ★ 有岔路 ⇒ 整段自身判定作废
    total = 0 ; count = 0                             ; edi / [esp+0x10]
    for (i = 0; i < 3; i++) {
        n   = word [0x48b8b4 + i*2]                   ; ★ 前瞻缓冲 = **节点 id**
        ref = word [node_table[n]*0x28 + 0x20]        ; 节点 +0x20
        if (ref <= 0x7d0 || ref >= 0xfa0) goto not_land
        ; ── 地块：2000 < ref < 4000（**开区间**）
        l = land_table + (ref-0x7d0)*0x34
        if (l.owner == 0) { total += word[l+0x1c]; count++ }       ; ★ 无主：不看 type/level
        else if (l.owner == cur+1) {
            if (l.type == 0 && l.level < 5) { total += word[l+0x1e]; count++ }
        } else {                                                   ; ★ 对手的地
            if (0x419744(l.owner, &l.name) > 1000*pi) goto visible_scan   ; ★ 该街过路费
        }
        continue
      not_land:
        if (ref <= 0xfa0 || ref >= 0x1770) goto not_fac
        ; ── 設施：4000 < ref < 6000
        f = fac_table + (ref-0xfa0)*0x38
        if (f.owner == 0) { total += word[f+0x22]; count++ }
        else if (f.owner == cur+1) {
            if (f.type != 0 && f.type != 3 && f.level < 5) { total += word[f+0x24]; count++ }
        } else {                                                   ; ★ 对手的設施
            if (f.type != 0 && f.type != 4 && f.level != 0) goto visible_scan
        }
        continue
      not_fac:
        if (ref <= 0x1770 || ref >= 0x1f40) continue               ; ── 企业：6000 < ref < 8000
        c = comm_table + (ref-0x1770)*0x34
        if (c.chairman(+0x18) != 0 && c.chairman != cur+1) goto visible_scan
        ; ★ 企业**不累加、不计数**（只做「作罢」判据）
    }
    ; 循环正常走完（没被 goto 打断）才看四条收尾闸
    if (!(total*1.5 < cash)) goto visible_scan         ; ★ `jae` ⇒ 相等也作废（x87 fcompp + sahf）
    if (count < 2) goto visible_scan
    if (!(cash + moneyInBank > 10000)) goto visible_scan          ; ★ `jle` ⇒ 恰好 10000 作废
    if (word [player+0x46] < 0) goto visible_scan                  ; ★ 財運，**有符号 16 位**
    [0x48be58] = (1 << cur) | 0x8000 ; best = 1
    return best

  visible_scan:
    if (best != 0) return best
    [0x48be60] = 0x40a45c(-1)                         ; ★ 可见**实体**表（0x80xx 玩家标记），不是节点表
    ; ── 第 1 趟：把画面里的玩家按 **表项序 → 位序** 编成一张下标表（放在 [esp+0..3]）
    nvis = 0
    for (i = 0; i < [0x48be60]; i++) {
        v = word [0x48b8c4 + i*2]
        if (!(v & 0x8000)) continue                   ; 必须带 bit15
        if (!(v & 0x000f)) continue                   ; ★ 低 4 位必须非 0
        for (bit = 1, p = 0; bit < 0x10; bit <<= 1, p++) {   ; ★ **只扫 bit0..bit3**
            if (!(v & bit)) continue
            if (p == cur) continue                    ; 自己不算
            if (player[p].alive(+0x15) == 0) continue  ; 出局不算
            list[nvis++] = p
        }
    }
    if (nvis == 0) return best

    ; ── 第 2 趟：对每个可见对手 p，看他前方 3 格
    for (j = 0; j < nvis && best == 0; j++) {
        p = list[j]
        if (0x40b221(p, 3) != 0) continue             ; 他有岔路 ⇒ 跳过
        total = 0 ; count = 0 ; valid = 1
        for (i = 0; i < 3; i++) {
            ref = word [node_table[word[0x48b8b4+i*2]]*0x28 + 0x20]
            if (2000 < ref < 4000) {
                l = land_table + (ref-2000)*0x34
                if (l.owner == cur+1) { total += 0x419744(cur+1, &l.name); count++ }
                if (l.owner == 0 || l.owner == p+1) { valid = 0; break }
            } else if (4000 < ref < 6000) {
                f = fac_table + (ref-4000)*0x38
                if (f.owner == cur+1 && f.type != 0 && f.type != 4 && f.level != 0) {
                    total += word [f + 0x24 + f.level*2]; count++ }     ; ★ **按等级**查表
                if (f.owner == 0 || f.owner == p+1) { valid = 0; break }
            } else if (6000 < ref < 8000) {
                c = comm_table + (ref-6000)*0x34
                if (c.chairman == cur+1) { total += word[c+0x22]; count++ }
                if (c.chairman == 0 || c.chairman == p+1) { valid = 0; break }
            }
        }
        if (valid && total >= 10000*pi && count >= 2) {
            [0x48be58] = (1 << p) | 0x8000 ; best = 1
        }
    }
    return best
```

### ★★ 本函数最值得单独钉的三件事

1. **自身判定的过路费闸是「原始街价和 > 1000」，不是「> 1000×物價」。**
   原版调 `0x419744(owner, &name)`，而 `0x419744` 的返回值**已经乘过物價指数**
   （`0x4197d8 mov ecx,[0x4990e8] / 0x4197e0 imul eax,ecx`），再与 `1000*pi` 比较
   ⇒ **pi 在两边同时出现，约掉了**（pi > 0 时等价于 `街价和 > 1000`）。
   对手判定同理：`Σ(街价和 × pi) >= 10000 × pi` ⟺ `Σ街价和 >= 10000`。
   ⚠️ 复刻侧 `ai/card-policy.ts:172` 的 `streetTollOf()` **不乘物價指数**，
   却在 `:874` / `:914` 拿它去比 `1000*pi` / `10000*pi` ⇒ **pi ≠ 1 时两边行为不同**
   （见 [L] 组与最终报告）。本测试用 pi=2 的用例把原版语义钉死。
2. **`self` 判定里「对手的設施」作废条件是 `type ∉ {0,4} && level != 0`，
   而「我的設施」累加条件是 `type ∉ {0,3} && level < 5`** —— 两组类型白名单**不一样**
   （自：0=公園 / 3=加油站；敌：0=公園 / 4=研究所），且等级判据一边是 `< 5`、一边是 `!= 0`。
   复刻侧逐条一致（`:881` vs `:885`、`:924`）。
3. **对手判定里「我的設施」的过路费按等级查表 `word[fac + 0x24 + level*2]`，
   而自身判定里「我的設施」累加的是**定址** `word[fac + 0x24]`（= `rateByLevel[0]` = 房价）。**
   同一字段、两种寻址 —— 复刻侧也对（`:882` 用 `housePrice`，`:925` 用 `rateByLevel[level]`）。

### 关于 `owner`(1 基) 与玩家下标(0 基)

* 地產/設施/企业的 `+0x19`/`+0x18` 是 **owner = 玩家下标 + 1**（0 = 无主）。
* 可见表那一趟吐出来的是 **0 基玩家下标**，写进 `0x48be58` 时补 `0x8000`。
* 自身命中写的是 `(1 << cur) | 0x8000`（**cur 是 0 基当前玩家**，不是 owner）。
  ⇒ 三处基址各不相同，本测试各有专门断言（[A]/[G]/[J] 组）。

### 关于「防禦/被动卡」的排查（任务点 4 的最后一问）

逐条核实（**结论：本函数是纯「目标选择」，没有任何攻防/状态写入**）：

| 疑点 | 实测 | 证据 |
|---|---|---|
| `whoPlays` 位 / 状态字 | **不读** | 全函数对玩家记录的读只有 `+0x15`(存活)、`+0x1c`(现金)、`+0x20`(存款)、`+0x46`(財運) 四处 |
| `player + 0x15` | **读**，但只当「出局者不算可见对手」用 | `0x420c7f cmp byte [esi+0x496b7d],0` |
| 写 `+0x36`(烏龜天数) / `+0x39` | **不写**（那是卡效果 `0x4458df` 的事） | 函数内无 `mov [reg+0x36/0x39]`，且不调 `0x4458df` |
| 敌意 `0x40df69` | **不调** | 函数内唯一的 call 是 `0x40b221`/`0x40a45c`/`0x419744` |
| 胜负/终局判据 | **无** | 同 `0x41d89e` 零调用 |

⇒ 本函数**只读全局、只写 `0x48be58` 与 `0x48be60`**，是干净的纯判定函数（可整支 `call()`）。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040b221` | 前瞻 3 格（返回「是否遇到岔路」，并填 `0x48b8b4` 节点 id 数组） | 从 `LOOKUP` 表按 **实参玩家号** 读 (fork, n0,n1,n2)，写 `0x48b8b4`，返回 fork；顺带记录调用次数与实参 | 前瞻**本身**已有差分测试 `test_lookahead.py`（58/58）；本测试的对象是**它返回之后的那 1322 字节**。★ 唯一**必须**打桩的是它：真身前瞻会 `rand()%k` 选岔路并依赖真实邻接表，无法把「有岔路 / 无岔路」变成可控输入 |
| `0x0040a45c` | 填「可见**实体**表」`0x48b8c4`（0x80xx 玩家标记） | `mov eax,[COUNT_SLOT]; ret`（表由 `setup()` 直接铺） | 它自己的语义已单独定案（`map-format.md` §4.2）；复刻换了视野口径 = **D-005**，不是本测试对象 |
| `0x00456f2d` | CRT `rand()` | 数据槽 + 调用计数 | 本函数**不摇随机数** —— 留着是为了让「一次都没摇」可断言 |

**真跑（不打桩）**：`0x419744`（`calculate_land_toll`，本测试的过路费真值来源）、
`0x458370`（`strcmp`，被 `0x419744` 调用）、`0x496b68` 起的玩家记录、
`0x498e98`(num_lands) / `0x498e7c`~`0x498e88`(四张表指针) 全部按原版语义读。

⚠️ **`0x40b221` 的桩必须记录实参**：原版两段都用 `n = 3`；
若复刻某处传了别的格数，本测试的 `look_n == 3` 断言会红。

## 复刻侧逐条对照（`packages/core/src/ai/card-policy.ts` 的 `wugui`，行 846-946）

| 规则 | 原版证据 | 复刻 | 判定 |
|---|---|---|---|
| 前瞻有岔路 ⇒ 整段自身判定作废 | `0x42098e jne 0x420a82` | `:859-861` | MATCH |
| 格值区间与「记录 0 不参与」 | `0x4209cf/0x4209df/…` | `:867`+`resolveNodeType` | MATCH（真实地图 `num_lands ≤ 73` ⇒ ref ≤ 2073，上界不可达）|
| 无主地累加 `+0x1c` | `0x420a25 mov ax,[esi+0x1c]` | `:871 l.landPrice` | MATCH |
| 我的住宅 `type==0 && level<5` 累加 `+0x1e` | `0x420a0b/0x420a11/0x420a1f` | `:870-871` | MATCH |
| **对手地：`0x419744(...) > 1000×pi` ⇒ 作废** | `0x420a54` + `0x420a7a` | `:874` | **DISCREPANCY** ★★ |
| 无主設施累加 `+0x22` | `0x420b4c` | `:882 f.landPrice` | MATCH |
| 我的設施 `type∉{0,3} && level<5` 累加 `+0x24`（**定址**） | `0x420b2a..0x420b44` | `:881-882 f.housePrice` | MATCH |
| 对手設施 `type∉{0,4} && level!=0` ⇒ 作废 | `0x420b74..0x420b8c` | `:885` | MATCH |
| 企业：董事長 ∉{0,我} ⇒ 作废（**不累加**） | `0x420bbd..0x420bda` | `:889-895` | MATCH |
| `count≥2` / `total×1.5 < 現金` / `現金+存款 > 10000` / `財運 ≥ 0` | `0x420c0a/…/0x420c3a` | `:897` | MATCH（严格性与边界逐条一致）|
| 自身目标 `(1<<cur)|0x8000` | `0x420c40..0x420c50` | `SELF` | MATCH（数值编码是原版内部 ABI）|
| 可见表：bit15 + 低 4 位、只扫 bit0..bit3 | `0x420ac4..0x420c6c` | `visibleRivals :141-151` | 视野口径 = 已登记 **D-005**（本测试打桩）|
| **`byte[+0x15] != 0`（不掩码）** | `0x420c7f` | `isAlive` = `(whoPlays & 3) != 0` | **DISCREPANCY**（谓词宽度，可达性存疑）|
| 对手地：我的 ⇒ `total += 0x419744(me1,&name)` | `0x420d33..0x420d42` | `:914` | **DISCREPANCY** ★★（同一处物價指数）|
| 对手地：`owner∈{0,p+1}` ⇒ 作废 | `0x420d46/0x420d5b` | `:917` | MATCH |
| 对手設施：我的 `type∉{0,4} && level!=0` ⇒ `rateByLevel[level]` | `0x420d94..0x420dc2` | `:924-925` | MATCH |
| 对手企业：我是董事長 ⇒ `+0x22` | `0x420e21..0x420e2b` | `:935-936` | MATCH |
| 对手收尾 `total ≥ 10000×pi && count ≥ 2` | `0x420e6f/0x420e73` | `:945` | **DISCREPANCY** ★★（同一处物價指数）|

★★ **物價指数那一条的机理**：`0x419744` 的返回值**已经乘过 `[0x4990e8]`**，
原版拿它去比 `1000×pi` ⇒ **`pi` 两边约掉，实际判据是「街价和 > 1000」**
（对手段同理 ⇒ `Σ街价和 ≥ 10000`）。复刻的 `streetTollOf`（`:172-179`）**不乘**
`priceIndex`，却仍比 `1000*pi` / `10000*pi` ⇒ **`pi ≠ 1` 时两边结论不同**。
[L] 组与 [C2] 组的 `pi=2/pi=3` 用例就是为此设的（物價指数初始 1、对局中会升到 2、3…）。

跑法：cd rich4-spec && .venv/bin/python tests/test_turtle_card_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

TURTLE_AI = 0x420970
LOOKAHEAD = 0x40B221
VISIBLE_FILL = 0x40A45C
TOLL = 0x419744
PRNG = 0x456F2D

# ── 全局量 ────────────────────────────────────────────────────────────
CUR = 0x49910C
PRICE_INDEX = 0x4990E8
NUM_LANDS = 0x498E98
NODE_PTR = 0x498E80
COMM_PTR = 0x498E7C
LAND_PTR = 0x498E84
FAC_PTR = 0x498E88

VIS_LIST = 0x48B8C4           # 可见**实体**表（word 数组）
VIS_COUNT = 0x48BE60          # 可见项数
LOOK_BUF = 0x48B8B4           # 前瞻输出缓冲（节点 id，word 数组）
CARD_PARAM0 = 0x48BE58        # 输出：目标（玩家位 | 0x8000）
CARD_PARAM1 = 0x48BE5C        # 输出：第二参数（本函数不该碰）
CARD_PARAM2 = 0x48BE64        # 输出：第三槽（本函数不该碰，= 0x48be58 + 2*4）

# ── 玩家记录 ──────────────────────────────────────────────────────────
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_ALIVE, P_CASH, P_BANK, P_FORTUNE = 0x15, 0x1C, 0x20, 0x46

# ── 四张表 ────────────────────────────────────────────────────────────
NODE_STRIDE, N_REF = 0x28, 0x20
LAND_STRIDE = 0x34
L_NAME, L_TYPE, L_OWNER, L_LEVEL = 0x04, 0x18, 0x19, 0x1A
L_LANDPRICE, L_HOUSEPRICE, L_RENT = 0x1C, 0x1E, 0x20
FAC_STRIDE = 0x38
F_TYPE, F_OWNER, F_LEVEL, F_LANDPRICE, F_RATE = 0x18, 0x19, 0x1A, 0x22, 0x24
COMM_STRIDE = 0x34
C_CHAIRMAN, C_LANDPRICE = 0x18, 0x22

# ── 暂存区布局（★ 各表必须互相错开，见 gaps §7.138(3)）─────────────────
NODES = SCRATCH_BASE + 0x1000
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x5000
COMMS = SCRATCH_BASE + 0x7000
LOOKUP = SCRATCH_BASE + 0x9000     # 8 玩家 × 8 字节：fork, pad, n0, n1, n2, pad
COUNT_SLOT = SCRATCH_BASE + 0xA000
RAND_SLOT = SCRATCH_BASE + 0xA100
NSLOT = SCRATCH_BASE + 0xA200
CALL_SLOT = SCRATCH_BASE + 0xA300
RANDCNT_SLOT = SCRATCH_BASE + 0xA400

# ★ 大下标（1999）用的高位表基址：借**栈映射区**（0x500000..0x540000）的低端，
#   实际栈顶在 0x53ff00 附近，两者相距 0x25000 以上，不会相撞。
HI_BASE = 0x500000
HI_IDX = 1999

SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def _lookahead_stub() -> bytes:
    """0x40b221 的桩：按实参玩家号查 LOOKUP 表，写前瞻缓冲，返回「有岔路」标志。

    LOOKUP + p*8 : +0 = fork 字节、+2/+4/+6 = 3 个节点 id（word）
    """
    a = lambda va: struct.pack("<I", va)          # noqa: E731
    b = b""
    b += b"\x8B\x44\x24\x04"                       # mov eax,[esp+4]      ; player
    b += b"\x8B\x4C\x24\x08"                       # mov ecx,[esp+8]      ; n
    b += b"\x89\x0D" + a(NSLOT)                    # mov [NSLOT],ecx
    b += b"\xFF\x05" + a(CALL_SLOT)                # inc dword [CALL_SLOT]
    b += b"\x0F\xB6\x14\xC5" + a(LOOKUP)           # movzx edx,byte[eax*8+LOOKUP]
    b += b"\x66\x8B\x0C\xC5" + a(LOOKUP + 2)       # mov cx,word[eax*8+LOOKUP+2]
    b += b"\x66\x89\x0D" + a(LOOK_BUF)             # mov [0x48b8b4],cx
    b += b"\x66\x8B\x0C\xC5" + a(LOOKUP + 4)
    b += b"\x66\x89\x0D" + a(LOOK_BUF + 2)
    b += b"\x66\x8B\x0C\xC5" + a(LOOKUP + 6)
    b += b"\x66\x89\x0D" + a(LOOK_BUF + 4)
    b += b"\x0F\xB6\xC2"                           # movzx eax,dl
    b += b"\xC3"                                   # ret
    return b


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(LOOKAHEAD, _lookahead_stub())
        self.emu.patch(VISIBLE_FILL,
                       b"\xA1" + struct.pack("<I", COUNT_SLOT) + b"\xC3")
        self.emu.patch(PRNG,
                       b"\xFF\x05" + struct.pack("<I", RANDCNT_SLOT)
                       + b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        self.clear()

    # ── 构造 ─────────────────────────────────────────────────────────
    def clear(self):
        self.cur = 0
        self.pi = 1
        self.alive = [1, 1, 1, 1]
        self.cash = [0, 0, 0, 0]
        self.bank = [0, 0, 0, 0]
        self.fortune = [0, 0, 0, 0]
        self.visible = []
        self.nodes = {}          # 节点 id → ref 格值
        self.look = {}           # 玩家 → (fork, [n0,n1,n2])
        self.lands = {}
        self.facs = {}
        self.comms = {}
        self.hi = None           # None | 'land' | 'fac' | 'comm'
        self.hi_rec = None
        self.alive4 = False      # 把「玩家 4」的存活字节（落在物件表 0x496d1d）置 1
        self.rand = 12345

    def node(self, nid, ref):
        self.nodes[nid] = ref
        return self

    def ahead(self, p, node_ids, forked=0):
        ns = list(node_ids) + [0] * (3 - len(node_ids))
        self.look[p] = (forked, ns[:3])
        return self

    def see(self, *players, extra=0):
        v = 0x8000
        for p in players:
            v |= 1 << p
        self.visible.append((v | extra) & 0xFFFF)
        return self

    def raw_visible(self, v):
        self.visible.append(v & 0xFFFF)
        return self

    def land(self, idx, owner=0, typ=0, level=0, land_price=0, house_price=0,
             name="", rent=None):
        self.lands[idx] = dict(owner=owner, typ=typ, level=level,
                               land_price=land_price, house_price=house_price,
                               name=name, rent=list(rent or [0] * 6))
        return self

    def fac(self, idx, owner=0, typ=0, level=0, land_price=0, rate=None):
        self.facs[idx] = dict(owner=owner, typ=typ, level=level,
                              land_price=land_price, rate=list(rate or [0] * 6))
        return self

    def comm(self, idx, chairman=0, land_price=0):
        self.comms[idx] = dict(chairman=chairman, land_price=land_price)
        return self

    def hi_rec_set(self, kind, **kw):
        """大下标记录（ref 3999 / 5999 / 7999 ⇒ 记录号 1999），放 HI_BASE"""
        self.hi = kind
        self.hi_rec = kw
        return self

    # ── 常用场景 ─────────────────────────────────────────────────────
    def basic_self(self, cur=0):
        """「自身判定会通过」的最小世界：两块无主地 + 一个空节点。"""
        self.cur = cur
        me1 = cur + 1
        self.node(0, 2001).node(1, 2002).node(2, 0)
        self.ahead(cur, [0, 1, 2], forked=0)
        self.land(1, owner=0, land_price=100)
        self.land(2, owner=0, land_price=100)
        self.cash[cur] = 1000
        self.bank[cur] = 10000          # cash+bank = 11000 > 10000
        self.fortune[cur] = 0
        return me1

    def opp_base(self, p=1, cur=0, rent=5000, land_idx=3):
        """「对手 p 前方 3 格都踩着我(1 基)的同一条街」的必胜路径（自身判定跳过）。"""
        self.cur = cur
        self.see(p)
        self.ahead(cur, [0, 1, 2], forked=1)          # ★ 自身有岔路 ⇒ 整段跳过
        self.node(0, 2000 + land_idx).node(1, 2000 + land_idx).node(2, 0)
        self.land(land_idx, owner=cur + 1, typ=0, level=1, name="MM",
                  rent=[0, rent, 0, 0, 0, 0])
        self.ahead(p, [0, 1, 2], forked=0)
        return cur + 1

    # ── 注入 / 回读 ──────────────────────────────────────────────────
    def _setup(self, emu):
        emu.write32(CUR, self.cur)
        emu.write32(PRICE_INDEX, self.pi)
        emu.write32(NODE_PTR, NODES)
        emu.write32(LAND_PTR, HI_BASE if self.hi == "land" else LANDS)
        emu.write32(FAC_PTR, HI_BASE if self.hi == "fac" else FACS)
        emu.write32(COMM_PTR, HI_BASE if self.hi == "comm" else COMMS)
        emu.write32(NUM_LANDS, max(self.lands) if self.lands else 0)
        # ★ 暂存区跨 call 保留 ⇒ 必须整块清零
        emu.write(NODES, b"\x00" * (LANDS - NODES))
        emu.write(LANDS, b"\x00" * (FACS - LANDS))
        emu.write(FACS, b"\x00" * (COMMS - FACS))
        emu.write(COMMS, b"\x00" * (LOOKUP - COMMS))
        emu.write(LOOKUP, b"\x00" * 0x800)
        emu.write(VIS_LIST, b"\x00" * 128)
        # 高位表（大下标用例）
        if self.hi == "land":
            self._emit_land(emu, HI_BASE, HI_IDX, self.hi_rec, full=False)
        elif self.hi == "fac":
            self._emit_fac(emu, HI_BASE, HI_IDX, self.hi_rec, full=False)
        elif self.hi == "comm":
            self._emit_comm(emu, HI_BASE, HI_IDX, self.hi_rec, full=False)
        for nid, ref in self.nodes.items():
            emu.write16(NODES + nid * NODE_STRIDE + N_REF, ref)
        for idx, d in self.lands.items():
            self._emit_land(emu, LANDS, idx, d)
        for idx, d in self.facs.items():
            self._emit_fac(emu, FACS, idx, d)
        for idx, d in self.comms.items():
            self._emit_comm(emu, COMMS, idx, d)
        for p in range(8):
            fork, ns = self.look.get(p, (0, [0, 0, 0]))
            b = LOOKUP + p * 8
            emu.write8(b, fork)
            for k in range(3):
                emu.write16(b + 2 + k * 2, ns[k] & 0xFFFF)
        for i, v in enumerate(self.visible):
            emu.write16(VIS_LIST + i * 2, v)
        emu.write32(COUNT_SLOT, len(self.visible))
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(NSLOT, 0)
        emu.write32(CALL_SLOT, 0)
        emu.write32(RANDCNT_SLOT, 0)
        emu.write32(CARD_PARAM0, SENTINEL)
        emu.write32(CARD_PARAM1, SENTINEL)
        emu.write32(CARD_PARAM2, SENTINEL)
        emu.write32(VIS_COUNT, 0)
        for p in range(4):
            pb = PLAYER_BASE + p * PLAYER_STRIDE
            emu.write8(pb + P_ALIVE, self.alive[p])
            emu.write32(pb + P_CASH, self.cash[p])
            emu.write32(pb + P_BANK, self.bank[p])
            emu.write16(pb + P_FORTUNE, self.fortune[p] & 0xFFFF)
        # ★ 「玩家 4」的记录落在物件表 0x496d08 里（4*0x68 = 0x1a0）
        emu.write8(PLAYER_BASE + 4 * PLAYER_STRIDE + P_ALIVE, 1 if self.alive4 else 0)

    def _emit_land(self, emu, base, idx, d, full=True):
        if d is None:
            return
        b = base + idx * LAND_STRIDE
        emu.write(b, b"\x00" * LAND_STRIDE)
        emu.write8(b + L_TYPE, d.get("typ", 0) & 0xFF)
        emu.write8(b + L_OWNER, d.get("owner", 0) & 0xFF)
        emu.write8(b + L_LEVEL, d.get("level", 0) & 0xFF)
        emu.write16(b + L_LANDPRICE, d.get("land_price", 0) & 0xFFFF)
        emu.write16(b + L_HOUSEPRICE, d.get("house_price", 0) & 0xFFFF)
        nm = d.get("name", "")
        if nm:
            emu.write(b + L_NAME, nm.encode("ascii") + b"\x00")
        rent = d.get("rent") or [0] * 6
        for k in range(6):
            emu.write16(b + L_RENT + k * 2, rent[k] & 0xFFFF)

    def _emit_fac(self, emu, base, idx, d, full=True):
        if d is None:
            return
        b = base + idx * FAC_STRIDE
        emu.write(b, b"\x00" * FAC_STRIDE)
        emu.write8(b + F_TYPE, d.get("typ", 0) & 0xFF)
        emu.write8(b + F_OWNER, d.get("owner", 0) & 0xFF)
        emu.write8(b + F_LEVEL, d.get("level", 0) & 0xFF)
        emu.write16(b + F_LANDPRICE, d.get("land_price", 0) & 0xFFFF)
        rate = d.get("rate") or [0] * 6
        for k in range(6):
            emu.write16(b + F_RATE + k * 2, rate[k] & 0xFFFF)

    def _emit_comm(self, emu, base, idx, d, full=True):
        if d is None:
            return
        b = base + idx * COMM_STRIDE
        emu.write(b, b"\x00" * COMM_STRIDE)
        emu.write8(b + C_CHAIRMAN, d.get("chairman", 0) & 0xFF)
        emu.write16(b + C_LANDPRICE, d.get("land_price", 0) & 0xFFFF)

    def run(self):
        r = self.emu.call(TURTLE_AI, [], setup=self._setup)
        self.ret = r["eax"]
        self.target = self.emu.readu32(CARD_PARAM0)
        self.arg1 = self.emu.readu32(CARD_PARAM1)
        self.arg2 = self.emu.readu32(CARD_PARAM2)
        self.vis_count = self.emu.readu32(VIS_COUNT)
        self.look_calls = self.emu.readu32(CALL_SLOT)
        self.look_n = self.emu.readu32(NSLOT)
        self.rand_calls = self.emu.readu32(RANDCNT_SLOT)
        return self


def main():
    print("差分测试 · 烏龜卡 AI 目标选择 0x420970（1322 B）\n")
    w = World()

    # ══ [A] 自身段：岔路闸 + 基本命中 + 目标编码 ══════════════════════
    print("[A] 自身段：前瞻有岔路 ⇒ 整段作废；目标 = (1<<cur)|0x8000")
    w.clear()
    w.basic_self(cur=0)
    w.look[0] = (1, [0, 1, 2])                 # ★ 有岔路
    r = w.run()
    case("★ 自身有岔路 ⇒ 不选自自己", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)
    case("  ★ 有岔路但没可见玩家 ⇒ 可见表照填（0x48be60 = 0）", r.vis_count, 0)

    w.clear()
    w.basic_self(cur=0)
    r = w.run()
    case("★ 自身无岔路 + 四道收尾闸全过 ⇒ 返回 1", r.ret, 1)
    case("★ 目标 = (1<<0)|0x8000 = 0x8001", r.target, 0x8001)
    case("  ★ 只调了一次前瞻（自身），可见表根本没扫", r.look_calls, 1)
    case("  前瞻实参 n = 3", r.look_n, 3)

    w.clear()
    w.basic_self(cur=2)                        # me1 = 3
    r = w.run()
    case("★ cur = 2（0 基）⇒ 目标 = (1<<2)|0x8000 = 0x8004", r.target, 0x8004)
    case("  返回 1", r.ret, 1)

    w.clear()
    w.basic_self(cur=3)
    r = w.run()
    case("★ cur = 3 ⇒ 目标 = 0x8008", r.target, 0x8008)

    # ══ [B] 三个格值区间的**开区间**边界 ═════════════════════════════
    print("\n[B] 格值区间：2000 < ref < 4000（地）/ 4000 < ref < 6000（設施）/ 6000 < ref < 8000（企业）")
    w.clear()
    w.basic_self()
    w.node(1, 2000).node(2, 2002)              # ★ 恰好下界 ⇒ 不是地
    w.land(0, owner=0, land_price=100000)      # 若 2000 被当成记录 0，总价会爆掉
    r = w.run()
    case("★ ref = 2000（下界）不收 ⇒ 只算两块地 ⇒ 命中", r.ret, 1)
    case("  目标 0x8001", r.target, 0x8001)

    w.clear()
    w.basic_self()
    w.node(1, 4000).node(2, 2002)              # ★ 恰好 4000 ⇒ 既不是地也不是設施
    w.fac(0, owner=2, typ=1, level=1)          # 若被当設施 0 号 ⇒ 对手設施 ⇒ 作废
    w.comm(0, chairman=2)                      # 若被当企业 0 号 ⇒ 对手董事長 ⇒ 作废
    r = w.run()
    case("★ ref = 4000 ⇒ 不收 ⇒ 命中（没被当設施/企业 0 号）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 4001).node(2, 2002)
    w.fac(1, owner=2, typ=1, level=1)
    r = w.run()
    case("★ ref = 4001 ⇒ 設施 1 号（对手的）⇒ 作废", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(1, 4002).node(2, 2002)
    w.fac(2, owner=0, land_price=50)
    r = w.run()
    case("★ ref = 4002 ⇒ 設施 2 号（无主）⇒ 累加价 + 计数", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 6000).node(2, 2002)
    w.comm(0, chairman=2)
    r = w.run()
    case("★ ref = 6000（下界）不收 ⇒ 命中（没被当企业 0 号）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 6001).node(2, 2002)
    w.comm(1, chairman=2)
    r = w.run()
    case("★ ref = 6001 ⇒ 企业 1 号、董事長是别人 ⇒ 作废", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(1, 6001).node(2, 2002)
    w.comm(1, chairman=0)
    r = w.run()
    case("  同一企业、董事長 = 0 ⇒ 不作废", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 6001).node(2, 2002)
    w.comm(1, chairman=1)                      # = cur+1
    r = w.run()
    case("  同一企业、董事長 = 自己(1 基) ⇒ 不作废", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 8000).node(2, 2002)              # ★ 恰好 8000 ⇒ 超出企业上界
    w.comm(0, chairman=2)
    r = w.run()
    case("★ ref = 8000 ⇒ 一律不收 ⇒ 命中", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(1, 0).node(2, 2002)                 # ref = 0（空节点）
    r = w.run()
    case("  ref = 0 ⇒ 不落任何区间 ⇒ 跳过", r.ret, 1)

    # ── 上界侧（记录号 1999，必须借栈映射区放大表）───────────────────
    print("\n[B2] 区间**上界**侧：ref 3999 / 5999 / 7999 仍属该区间")
    w.clear()
    w.cur = 0
    w.node(0, 3999).node(1, 3999).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.hi_rec_set("land", owner=0, land_price=50)
    w.cash[0] = 1000
    w.bank[0] = 10000
    r = w.run()
    case("★ ref = 3999 ⇒ 地块 1999 号（无主）⇒ 计数 2 ⇒ 命中", r.ret, 1)

    w.clear()
    w.cur = 0
    w.node(0, 4000).node(1, 4000).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.hi_rec_set("land", owner=0, land_price=50)
    w.cash[0] = 1000
    w.bank[0] = 10000
    r = w.run()
    case("★ ref = 4000 ⇒ 不是地 ⇒ 计数 0 ⇒ 不命中", r.ret, 0)

    w.clear()
    w.cur = 0
    w.node(0, 5999).node(1, 5999).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.hi_rec_set("fac", owner=0, land_price=70)
    w.cash[0] = 1000
    w.bank[0] = 10000
    r = w.run()
    case("★ ref = 5999 ⇒ 設施 1999 号（无主）⇒ 计数 2 ⇒ 命中", r.ret, 1)

    w.clear()
    w.cur = 0
    w.node(0, 6000).node(1, 6000).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.hi_rec_set("fac", owner=0, land_price=70)
    w.cash[0] = 1000
    w.bank[0] = 10000
    r = w.run()
    case("★ ref = 6000 ⇒ 不是設施 ⇒ 计数 0 ⇒ 不命中", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(1, 7999).node(2, 2002)
    w.hi_rec_set("comm", chairman=2, land_price=10)
    r = w.run()
    case("★ ref = 7999 ⇒ 企业 1999 号、董事長是别人 ⇒ 作废", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(1, 7999).node(2, 2002)
    w.hi_rec_set("comm", chairman=0, land_price=10)
    r = w.run()
    case("  企业 1999 号、董事長 = 0 ⇒ 不作废 ⇒ 命中", r.ret, 1)

    # ══ [C] 自身段 · 地块累加判据 ════════════════════════════════════
    print("\n[C] 自身段 · 地块：无主 ⇒ `+0x1c`；我的**住宅且 level<5** ⇒ `+0x1e`；对手 ⇒ 只看过路费")
    w.clear()
    w.basic_self()
    w.node(0, 2001).node(1, 2001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.land(1, owner=0, typ=1, level=5, land_price=100)     # ★ 连锁店 + 满级，无主
    r = w.run()
    case("★ 无主地块**不看 type/level**（连锁店 5 级照样累加）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(0, 2001).node(1, 2001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.land(1, owner=1, typ=0, level=4, land_price=99999, house_price=100)
    r = w.run()
    case("★ 我的住宅 ⇒ 取 `+0x1e`（房价 100），不是 `+0x1c`（99999 会超现金）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(0, 2001).node(1, 2001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.land(1, owner=1, typ=0, level=5, land_price=100)
    r = w.run()
    case("★ 我的住宅但 level = 5 ⇒ 不累加（`jae` 门槛，恰好 5 不收）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(0, 2001).node(1, 2001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.land(1, owner=1, typ=1, level=3, land_price=100, house_price=100)
    r = w.run()
    case("★ 我的**连锁店**（type != 0）⇒ 不累加", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1000, 0, 0, 0, 0])
    r = w.run()
    case("★ 对手地块：街价和 = 1000，`1000 > 1000` 不成立 ⇒ 不作废 ⇒ 命中", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1001, 0, 0, 0, 0])
    r = w.run()
    case("★ 对手地块：街价和 = 1001 ⇒ `> 1000` ⇒ 作废", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(3, owner=2, typ=1, level=1, name="AA", rent=[0, 99999, 0, 0, 0, 0])
    r = w.run()
    case("★ 对手**连锁店**（type != 0）不计入过路费（0x419744 只算住宅）⇒ 不作废", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(3, owner=0, typ=0, level=1, name="AA", rent=[0, 99999, 0, 0, 0, 0])
    r = w.run()
    case("  无主地块不查过路费（owner = 0 直接走累加支）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(3, owner=1, typ=0, level=1, name="AA", rent=[0, 99999, 0, 0, 0, 0])
    r = w.run()
    case("  我自己的地不查过路费", r.ret, 1)

    # ══ [C2] 过路费真值 · 记录 0 不可见 与 物價指数 ═══════════════════
    print("\n[C2] ★★ 对手地块的过路费：0x419744（真跑）从**记录 1** 起扫；且它**已乘物價指数**")
    w.clear()
    w.basic_self()
    w.node(2, 2003)
    w.land(0, owner=2, typ=0, level=1, name="AA", rent=[0, 5000, 0, 0, 0, 0])
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1000, 0, 0, 0, 0])
    r = w.run()
    case("★★ 记录 0 号同名同主（租金 5000）**不计入** ⇒ 街价和 = 1000 ⇒ 不作废", r.ret, 1)

    w.clear()
    w.basic_self()
    w.pi = 2
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1000, 0, 0, 0, 0])
    r = w.run()
    case("★ pi = 2、街价和 1000 ⇒ 过路费 2000，`> 2000` 不成立 ⇒ 不作废", r.ret, 1)

    w.clear()
    w.basic_self()
    w.pi = 2
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1001, 0, 0, 0, 0])
    r = w.run()
    case("★★ pi = 2、街价和 1001 ⇒ 过路费 2002 > 2000 ⇒ 作废（★ 复刻侧这里比的是 1001 > 2000）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.pi = 2
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 1500, 0, 0, 0, 0])
    r = w.run()
    case("★★ pi = 2、街价和 1500 ⇒ 过路费 3000 > 2000 ⇒ **作废**（复刻侧 1500 > 2000 为假 ⇒ 不会作废）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.pi = 3
    w.node(2, 2003)
    w.land(3, owner=2, typ=0, level=1, name="AA", rent=[0, 2000, 0, 0, 0, 0])
    r = w.run()
    case("★★ pi = 3、街价和 2000 ⇒ 过路费 6000 > 3000 ⇒ 作废", r.ret, 0)

    # ══ [D] 自身段 · 設施累加判据 ════════════════════════════════════
    print("\n[D] 自身段 · 設施：无主 ⇒ `+0x22`；我的 type∉{0,3} 且 level<5 ⇒ `+0x24`（★ 定址，不按等级）")
    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=0, typ=1, level=3, land_price=100)
    r = w.run()
    case("★ 无主設施**不看 type/level** ⇒ 累加 `+0x22`", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=1, level=4, land_price=99999,
          rate=[100, 111, 222, 333, 444, 555])
    r = w.run()
    case("★ 我的設施 ⇒ 取 `+0x24`（= 房价 100），不是 `+0x22`（99999 会超现金）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=1, level=4, land_price=0,
          rate=[100000, 0, 0, 0, 0, 0])
    r = w.run()
    case("★★ 我的 4 级設施：自身段取**定址** `+0x24`（= rate[0] = 100000 ⇒ 作废），"
         "不是 rate[4] = 0", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=0, level=3, land_price=100, rate=[100] * 6)
    r = w.run()
    case("★ 我的公園（type = 0）⇒ 不累加", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=3, level=3, land_price=100, rate=[100] * 6)
    r = w.run()
    case("★ 我的加油站（type = 3）⇒ 不累加", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=4, level=3, land_price=100, rate=[100] * 6)
    r = w.run()
    case("  我的研究所（type = 4）⇒ **累加**（自身段白名单只有 {0,3}）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=1, level=5, land_price=100, rate=[100] * 6)
    r = w.run()
    case("★ 我的 5 级設施 ⇒ 不累加（`level < 5`，恰好 5 不收）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.ahead(0, [0, 1, 2], forked=0)
    w.fac(1, owner=1, typ=1, level=0, land_price=100, rate=[100] * 6)
    r = w.run()
    case("★ 我的 **0 级**設施 ⇒ 仍累加（自身段等级判据是 `< 5`，不是 `!= 0`）", r.ret, 1)

    for typ, lv, want, desc in [
        (1, 1, 0, "对手 type=1（旅館）level=1 ⇒ 作废"),
        (2, 1, 0, "对手 type=2（商場）level=1 ⇒ 作废"),
        (0, 1, 1, "对手 type=0（公園）⇒ 不作废"),
        (4, 1, 1, "对手 type=4（研究所）⇒ 不作废"),
        (1, 0, 1, "对手 type=1 但 level=0 ⇒ 不作废（`level != 0`）"),
    ]:
        w.clear()
        w.basic_self()
        w.node(0, 4001).node(1, 2001).node(2, 2002)
        w.ahead(0, [0, 1, 2], forked=0)
        w.fac(1, owner=2, typ=typ, level=lv, land_price=100, rate=[100] * 6)
        r = w.run()
        case("★ 自身段 · " + desc, r.ret, want)

    # ══ [E] 自身段 · 企业（只作废、不累加）════════════════════════════
    print("\n[E] 自身段 · 企业：董事長 ∉ {0, 我} ⇒ 作废；**不累加、不计数**")
    w.clear()
    w.basic_self()
    w.node(1, 6001)
    w.node(2, 2002)
    w.comm(1, chairman=1, land_price=100000)
    r = w.run()
    case("★★ 企业**不累加**：董事長是我、地价 100000，若累加会爆掉现金", r.ret, 1)
    case("  目标仍是 0x8001", r.target, 0x8001)

    w.clear()
    w.basic_self()
    w.node(1, 6001)
    w.comm(1, chairman=2)
    r = w.run()
    case("★ 企业董事長 = 第二位玩家（对手）⇒ 作废", r.ret, 0)

    # ══ [F] 自身段 · 四道收尾闸的边界 ═══════════════════════════════
    print("\n[F] 自身段收尾：count ≥ 2 / total×1.5 < 现金 / 现金+存款 > 10000 / 財運 ≥ 0")
    w.clear()
    w.basic_self()
    w.node(1, 0)
    r = w.run()
    case("★ count = 1 ⇒ 不选", r.ret, 0)

    w.clear()
    w.basic_self()
    w.cash[0] = 300                      # total = 200 ⇒ 200×1.5 = 300
    r = w.run()
    case("★ 恰好 total×1.5 == 现金 ⇒ `jae` ⇒ 不选（严格 `<`）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.cash[0] = 301
    r = w.run()
    case("  total×1.5 = 300 < 301 ⇒ 选", r.ret, 1)

    w.clear()
    w.basic_self()
    w.bank[0] = 9000                     # cash 1000 ⇒ 恰好 10000
    r = w.run()
    case("★ 现金+存款 == 10000 ⇒ `jle` ⇒ 不选（严格 `>`）", r.ret, 0)

    w.clear()
    w.basic_self()
    w.bank[0] = 9001
    r = w.run()
    case("  10001 > 10000 ⇒ 选", r.ret, 1)

    w.clear()
    w.basic_self()
    w.fortune[0] = 0
    r = w.run()
    case("  財運 = 0 ⇒ 选（`jl`，0 不算负）", r.ret, 1)

    w.clear()
    w.basic_self()
    w.fortune[0] = -1
    r = w.run()
    case("★ 財運 = −1（word 0xffff，**有符号**）⇒ 不选", r.ret, 0)

    w.clear()
    w.basic_self()
    w.fortune[0] = -32768
    r = w.run()
    case("  財運 = −32768 ⇒ 不选", r.ret, 0)

    w.clear()
    w.basic_self()
    w.fortune[0] = 32767
    r = w.run()
    case("  財運 = 32767 ⇒ 选", r.ret, 1)

    # ══ [G] 对手段 · 可见实体表的闸与遍历 ═══════════════════════════
    print("\n[G] 对手段 · 可见实体表：必须带 bit15、低 4 位非 0；只扫 bit0..bit3")
    w.clear()
    w.see(1)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    r = w.run()
    case("★ 人在画面里但前方 3 格全空 ⇒ 无目标", r.ret, 0)
    case("  ★ 0x48be60 = 可见项数（1）", r.vis_count, 1)

    w.clear()
    w.raw_visible(0x0004)                # 低 4 位有、bit15 没有
    w.ahead(0, [0, 1, 2], forked=1)
    r = w.run()
    case("★ 缺 bit15 ⇒ 整项跳过", r.ret, 0)

    w.clear()
    w.raw_visible(0x8000)                # bit15 有、低 4 位全 0
    w.ahead(0, [0, 1, 2], forked=1)
    r = w.run()
    case("★ 低 4 位 = 0 ⇒ 整项跳过（0x8000）", r.ret, 0)

    w.clear()
    w.raw_visible(0x8010)                # bit4 有、低 4 位 = 0
    w.ahead(0, [0, 1, 2], forked=1)
    r = w.run()
    case("★ 0x8010（只有 bit4）⇒ 低 4 位为 0 ⇒ 整项跳过", r.ret, 0)

    w.clear()
    w.cur = 0
    w.raw_visible(0x8001)                # 只有当前玩家
    w.ahead(0, [0, 1, 2], forked=1)
    w.node(0, 2003).node(1, 2003).node(2, 0)
    w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
    r = w.run()
    case("★ 画面上只有「我自己」⇒ 不算对手", r.ret, 0)

    w.clear()
    w.cur = 0
    w.raw_visible(0x8002)
    w.alive[1] = 0                       # 出局
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    r = w.run()
    case("★ 出局者不算「在画面里」", r.ret, 0)

    w.clear()
    w.cur = 0
    w.raw_visible(0x8002).raw_visible(0x8004)
    w.alive[1] = 0
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.ahead(2, [0, 1, 2], forked=0)
    r = w.run()
    case("  ★ 存活标志按 `0x496b68 + p*0x68 + 0x15` 取（1 号出局、2 号在）", r.ret, 0)
    case("  0x48be60 = 2", r.vis_count, 2)

    # ★★ 「在场」判据的**宽度**：原版是 `byte[+0x15] != 0`，不是 `(byte & 3) != 0`
    print("\n[G2] ★★ 在场判据宽度：原版读 `whoPlays(+0x15)` 整字节比 0（不掩码）")
    for av, want in [(1, 1), (2, 1), (3, 1), (0, 0), (0x10, 1), (0x04, 1), (0x80, 1)]:
        w.clear()
        w.cur = 0
        w.see(1)
        w.alive[1] = av
        w.ahead(0, [0, 1, 2], forked=1)
        w.ahead(1, [3, 3, 2], forked=0)
        w.node(3, 2004)
        w.land(4, owner=1, typ=0, level=1, name="NN", rent=[0, 5000, 0, 0, 0, 0])
        r = w.run()
        case(f"★ whoPlays(+0x15) = 0x{av:02x} ⇒ "
             f"{'算对手' if want else '不算'}（`!= 0` 而非 `& 3`）", r.ret, want)

    # ★ 4 位的扫描上界：p=4 不在玩家表内，其 +0x15 落在物件表 0x496d1d
    w.clear()
    w.cur = 0
    w.raw_visible(0x8014)                # bit2 + bit4
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(2, [0, 1, 2], forked=1)      # p=2 有岔路 ⇒ 跳过
    w.ahead(4, [0, 1, 2], forked=0)      # 若 bit4 被扫到，p=4 会命中
    w.node(0, 2003).node(1, 2003).node(2, 0)
    w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
    w.alive4 = True                      # 把「玩家 4」的存活字节也点亮
    r = w.run()
    case("★★ 位扫描只到 bit3 ⇒ bit4 对应的「玩家 4」永不入选", r.ret, 0)
    case("  ★ 而且 p=2 那次确实被前瞻岔路挡掉了（前瞻调 2 次）", r.look_calls, 2)

    # ══ [H] 对手段 · 前瞻岔路闸 ══════════════════════════════════════
    print("\n[H] 对手段 · 前瞻有岔路 ⇒ 跳过该对手")
    w.clear()
    w.opp_base(p=1)
    r = w.run()
    case("★ 对手与我同街两块地、街价和 5000×2 ≥ 10000 ⇒ 命中", r.ret, 1)
    case("★ 目标 = (1<<1)|0x8000 = 0x8002", r.target, 0x8002)
    case("  ★ 前瞻调了 2 次（自身 1 次 + 对手 1 次）", r.look_calls, 2)
    case("  ★ 一次随机数都没摇", r.rand_calls, 0)

    w.clear()
    w.opp_base(p=1)
    w.ahead(1, [0, 1, 2], forked=1)      # 对手有岔路
    r = w.run()
    case("★ 对手有岔路 ⇒ 跳过", r.ret, 0)

    w.clear()
    w.opp_base(p=1, rent=4999)
    r = w.run()
    case("★ 街价和 4999×2 = 9998 < 10000 ⇒ 不选", r.ret, 0)

    w.clear()
    w.opp_base(p=1, rent=5000)
    w.node(1, 0)                          # 只剩 1 格
    w.ahead(1, [0, 1, 2], forked=0)
    r = w.run()
    case("★ 只有 1 格我的地 ⇒ count = 1 < 2 ⇒ 不选", r.ret, 0)

    # ══ [I] 对手段 · 地块的「作废」判据 ═════════════════════════════
    print("\n[I] 对手段 · 地块：`owner ∉ {0, p+1}` 才继续；我的地才累加")
    w.clear()
    w.opp_base(p=1)
    w.node(2, 2001)
    w.land(1, owner=0, typ=0, level=0, name="UU")
    r = w.run()
    case("★ 路径上有**无主**地 ⇒ 整条作废（哪怕前两格已累加满）", r.ret, 0)
    case("  没写 0x48be58", r.target, SENTINEL)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 2002)
    w.land(2, owner=2, typ=0, level=0, name="PP")     # owner = p+1
    r = w.run()
    case("★ 路径上有**他自己**的地 ⇒ 作废", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 2002)
    w.land(2, owner=3, typ=0, level=0, name="XX")     # 第三个玩家
    r = w.run()
    case("★ 路径上有**第三位玩家**的地 ⇒ 既不累加也不作废", r.ret, 1)
    case("  目标 0x8002", r.target, 0x8002)

    # ══ [J] 对手段 · 設施 ═══════════════════════════════════════════
    print("\n[J] 对手段 · 設施：我的 type∉{0,4} 且 level≠0 ⇒ `rateByLevel[level]`")
    w.clear()
    w.cur = 0
    w.see(1)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.fac(1, owner=1, typ=1, level=2, rate=[0, 100, 5000, 0, 0, 0])
    r = w.run()
    case("★★ 我的 2 级旅館：取 `rateByLevel[2]` = 5000（rate[0] = 0 ⇒ 定址读会得 0）", r.ret, 1)
    case("  目标 0x8002", r.target, 0x8002)

    for typ, lv, desc, want in [
        (0, 2, "我的公園（type = 0）⇒ 不累加", 0),
        (4, 2, "我的研究所（type = 4）⇒ 不累加（对手段白名单是 {0,4}）", 0),
        (1, 0, "我的 0 级設施 ⇒ 不累加（`level != 0`）", 0),
        (1, 1, "我的 1 级設施 ⇒ 累加 rate[1] = 100 ⇒ 2×100 < 10000", 0),
        (3, 2, "我的加油站（type = 3）⇒ **累加**（对手段不看 type 3）", 1),
    ]:
        w.clear()
        w.cur = 0
        w.see(1)
        w.ahead(0, [0, 1, 2], forked=1)
        w.ahead(1, [0, 1, 2], forked=0)
        w.node(0, 4001).node(1, 4001).node(2, 0)
        w.fac(1, owner=1, typ=typ, level=lv, rate=[0, 100, 5000, 0, 0, 0])
        r = w.run()
        case("★ 对手段 · " + desc, r.ret, want)

    w.clear()
    w.cur = 0
    w.see(1)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.node(0, 4001).node(1, 4001).node(2, 0)
    w.fac(1, owner=1, typ=1, level=5, rate=[0, 0, 0, 0, 0, 5000])
    r = w.run()
    case("★ 我的 5 级設施（對手段無 `<5` 闸）⇒ rate[5] = 5000 ⇒ 命中", r.ret, 1)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 4001)
    w.fac(1, owner=0, typ=1, level=2, rate=[0, 100, 5000, 0, 0, 0])
    r = w.run()
    case("★ 路径上有**无主**設施 ⇒ 作废", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 4001)
    w.fac(1, owner=2, typ=1, level=2, rate=[0, 100, 5000, 0, 0, 0])
    r = w.run()
    case("★ 路径上有**他自己**的設施 ⇒ 作废", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 4001)
    w.fac(1, owner=3, typ=1, level=2, rate=[0, 100, 5000, 0, 0, 0])
    r = w.run()
    case("★ 路径上有**第三位玩家**的設施 ⇒ 不作废、不累加", r.ret, 1)

    # ══ [K] 对手段 · 企业 ═══════════════════════════════════════════
    print("\n[K] 对手段 · 企业：董事長是我 ⇒ `+0x22`；董事長 ∈ {0, p+1} ⇒ 作废")
    w.clear()
    w.cur = 0
    w.see(1)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.node(0, 6001).node(1, 6001).node(2, 0)
    w.comm(1, chairman=1, land_price=5000)
    r = w.run()
    case("★ 我是董事長 ⇒ 累加 `+0x22` = 5000，两格 ⇒ 10000 ⇒ 命中", r.ret, 1)
    case("  目标 0x8002", r.target, 0x8002)

    w.clear()
    w.cur = 0
    w.see(1)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.node(0, 6001).node(1, 6001).node(2, 0)
    w.comm(1, chairman=1, land_price=100)
    r = w.run()
    case("  地价只有 100 ⇒ 2×100 < 10000 ⇒ 不选", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 6001)
    w.comm(1, chairman=0, land_price=5000)
    r = w.run()
    case("★ 路径上有**无主**企业 ⇒ 作废", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 6001)
    w.comm(1, chairman=2, land_price=5000)
    r = w.run()
    case("★ 路径上有**他自己**当董事長的企业 ⇒ 作废", r.ret, 0)

    w.clear()
    w.opp_base(p=1)
    w.node(2, 6001)
    w.comm(1, chairman=3, land_price=5000)
    r = w.run()
    case("★ 第三位玩家当董事長 ⇒ 不作废、不累加 ⇒ 仍靠两块地命中", r.ret, 1)

    # ══ [L] 对手段 · 收尾闸与物價指数 ═══════════════════════════════
    print("\n[L] 对手段 · `total ≥ 10000×pi` 与 `count ≥ 2`；★ pi 与过路费里的 pi 互相抵消")
    w.clear()
    w.opp_base(p=1, rent=5000)
    w.pi = 2
    r = w.run()
    case("★★ pi = 2：两块 5000 的街（街价和 10000）⇒ 过路费 20000 ≥ 20000 ⇒ 命中", r.ret, 1)
    case("  ★ 复刻侧不乘 pi（total = 10000）却比 20000 ⇒ 此处会判不中", r.target, 0x8002)

    w.clear()
    w.opp_base(p=1, rent=4999)
    w.pi = 2
    r = w.run()
    case("★ pi = 2：街价和 9998 ⇒ 过路费 19996 < 20000 ⇒ 不选", r.ret, 0)

    w.clear()
    w.opp_base(p=1, rent=20000)
    w.pi = 3
    r = w.run()
    case("★ pi = 3：街价和 40000 ⇒ 过路费 120000 ≥ 30000 ⇒ 命中", r.ret, 1)

    # ══ [M] 对手段 · 可见表遍历顺序 / 位序 / 目标编码 ════════════════
    print("\n[M] 对手段 · 表项序 → 位序；第一个满足条件的对手获胜")
    for p in (1, 2, 3):
        w.clear()
        w.cur = 0
        w.see(p)
        w.ahead(0, [0, 1, 2], forked=1)
        w.ahead(p, [0, 1, 2], forked=0)
        w.node(0, 2003).node(1, 2003).node(2, 0)
        w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
        r = w.run()
        want = 0x8000 | (1 << p)
        case(f"只有玩家 {p} 在画面（位 {p}）⇒ 0x48be58 = 0x{want:04x}", r.target, want)
        case("  卡牌参数第 2 槽保持哨兵", r.arg1, SENTINEL)

    w.clear()
    w.cur = 0
    w.see(1, 2)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.ahead(2, [0, 1, 2], forked=0)
    w.node(0, 2003).node(1, 2003).node(2, 0)
    w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
    r = w.run()
    case("★ 同格两人（位 1、位 2）⇒ 位序靠前的 1 号先入选 = 0x8002", r.target, 0x8002)
    case("  只调了 2 次前瞻（命中即停）", r.look_calls, 2)

    w.clear()
    w.cur = 0
    w.raw_visible(0x8008).raw_visible(0x8002)      # 表项序：3 号在前
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.ahead(3, [0, 1, 2], forked=1)                # 3 号跳过
    w.node(0, 2003).node(1, 2003).node(2, 0)
    w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
    r = w.run()
    case("★ 3 号（表项 1）被跳过 ⇒ 轮到位 1 的 1 号 = 0x8002", r.target, 0x8002)
    case("  两项可见表累计（0x48be60 = 2）", r.vis_count, 2)

    w.clear()
    w.cur = 0
    w.raw_visible(0x8002).raw_visible(0x8008)
    w.ahead(0, [0, 1, 2], forked=1)
    w.ahead(1, [0, 1, 2], forked=1)
    w.ahead(3, [0, 1, 2], forked=0)
    w.node(0, 2003).node(1, 2003).node(2, 0)
    w.land(3, owner=1, typ=0, level=1, name="MM", rent=[0, 5000, 0, 0, 0, 0])
    r = w.run()
    case("★ 反过来（1 号先但被跳过）⇒ 3 号 = 0x8008", r.target, 0x8008)

    # ══ [N] 自身优先 / 输出槽 / 返回值集合 ═══════════════════════════
    print("\n[N] 自身优先于对手；只写 0x48be58；返回值恒 0/1")
    w.clear()
    w.basic_self(cur=0)
    w.see(1)
    w.ahead(1, [0, 1, 2], forked=0)
    w.node(3, 2004)
    w.land(4, owner=1, typ=0, level=1, name="NN", rent=[0, 5000, 0, 0, 0, 0])
    r = w.run()
    case("★★ 自身条件满足 ⇒ 直接返回，**根本不扫可见表**", r.ret, 1)
    case("  目标 = 自己 0x8001", r.target, 0x8001)
    case("  ★ 可见表没被填（0x48be60 仍是 0）", r.vis_count, 0)
    case("  只调了一次前瞻", r.look_calls, 1)

    w.clear()
    w.basic_self(cur=0)
    w.see(1)
    w.ahead(1, [3, 3, 2], forked=0)        # 对手前方 3 格踩着我(1 基)的 4 号街（2 号节点为空）
    w.node(3, 2004)
    w.land(4, owner=1, typ=0, level=1, name="NN", rent=[0, 5000, 0, 0, 0, 0])
    w.cash[0] = 1                          # 自身收尾闸挂掉 ⇒ 转对手段
    r = w.run()
    case("★ 自身被收尾闸挡掉 ⇒ 转对手段（前瞻调 2 次）", r.look_calls, 2)
    case("  对手 1 号入选 = 0x8002", r.target, 0x8002)

    seen = set()
    w.clear(); seen.add(w.run().ret)
    w.clear(); w.basic_self(); seen.add(w.run().ret)
    w.clear(); w.opp_base(p=1); seen.add(w.run().ret)
    case("  三种极端下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    w.clear()
    w.opp_base(p=1)
    r = w.run()
    case("★ 0x48be5c 全程保持哨兵", r.arg1, SENTINEL)
    case("★ 0x48be64（= 0x48be58 + 2*4）全程保持哨兵", r.arg2, SENTINEL)
    case("★ 全程不摇随机数", r.rand_calls, 0)
    case("★ 前瞻实参恒为 3", r.look_n, 3)

    w.clear()
    w.opp_base(p=1)
    w.look[0] = (1, [7, 7, 7])            # 自身那次的缓冲内容无关紧要
    r = w.run()
    case("  前瞻缓冲被覆盖也不影响（每次调用都重填）", r.target, 0x8002)

    # ── 收尾 ─────────────────────────────────────────────────────────
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
