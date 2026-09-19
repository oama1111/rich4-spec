#!/usr/bin/env python3
"""
通道 2 差分测试 · **过路费免收判据（九种免收）** `0x0041d559`（408 B）

复刻侧对应：
  · `packages/core/src/rules/toll-flow.ts` 的 `tollExemption`（`@source VA 0x0041d559`）
  · 调用点 `packages/core/src/state/reduce.ts:1364`（住宅）/ `:5296`（設施）

调用点（原版两条路共用一个免收闸）：
  · 住宅 `0x00419a8a`（`cmp eax,1 / jne 0x41b077` ⇒ **非 1 就一分不收**）
  · 設施 `0x0041a3cc`（本工作单指定的那个）——
    `0x0041a3c5..0x0041a3cc` 压栈顺序：
    `push 費名(0x47517c[0x47528b[type]]) / push byte[rec+0x1c] / push byte[rec+0x19]-1`
    ⇒ cdecl 首参 = **地主（0 基）**、次参 = **涨价位字节**（設施在 `+0x1c`；
      住宅那条路传的是地块的 `+0x17`）、三参 = **費名串指针**。

## 语义（408 B 全程读完；`0x0041d6f0` 是它唯一的 `ret`）

本函数**只读全局**、**不摇随机数**（全函数只有 5 个 `call`：
`0x452946` 取地主名、`0x457110` sprintf ×2、`0x440cac` 文字框、`0x44ef41` 台词），
返回值只有 **1 = 照收 / 0 = 免收** 两种。

```
0x41d559(landlord, priceStatus, feeName):
    ; 序言 push ebx/esi/ebp + sub esp,0x94
    ;   局部：msg 缓冲 = 帧基 F（0x80 字节）、name 缓冲 = F+0x80
    ;   帧基 F = STACK_TOP - 0xb0（三实参 + 返回地址共 0x10，再减 0xc 与 0x94）
    ;   实参：arg1=[F+0xa4] arg2=[F+0xa8] arg3=[F+0xac]
    result = 1                                        ; 0x41d569 mov ebx,1
    copy_no_space(F+0x80, *(char**)(player[landlord]+0x00))   ; 0x41d585 → 地主姓名字串指针
    p = (byte)priceStatus                              ; 0x41d58d mov ah,byte [esp+0xa8]
    if (p & 0xf0) != 0 and (p & 0x0f) != 0:            ; 0x41d594/0x41d599 两跳
        sprintf(msg, "房屋查封中\\n\\n免收%s！"(0x463bb8), feeName); result = 0
    elif *(u8*)(player[landlord]+0x41) == curPlayer+1: ; 0x41d5bd/0x41d5c3/0x41d5ca
        sprintf(msg, "與%s同盟中\\n\\n免收%s！"(0x463bcd), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x3f) == 0x0f:        ; 0x41d5f0 god_info
        sprintf(msg, "死神顯靈\\n\\n免收%s！"(0x463be2), feeName); result = 0
    elif *(u8*)(player[landlord]+0x32) != 0:           ; 0x41d601 住宿中
        sprintf(msg, "%s住宿中\\n\\n免收%s！"(0x463bf5), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x33) != 0:           ; 0x41d61a 消失中
        sprintf(msg, "%s消失中\\n\\n免收%s！"(0x463c08), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x34) != 0:           ; 0x41d633 坐牢中
        sprintf(msg, "%s坐牢中\\n\\n免收%s！"(0x463c1b), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x35) != 0:           ; 0x41d64c 住院中
        sprintf(msg, "%s住院中\\n\\n免收%s！"(0x463c2e), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x36) != 0:           ; 0x41d668 冬眠中
        sprintf(msg, "%s冬眠中\\n\\n免收%s！"(0x463c41), name, feeName); result = 0
    elif *(u8*)(player[landlord]+0x37) != 0:           ; 0x41d684 夢遊中
        sprintf(msg, "%s夢遊中\\n\\n免收%s！"(0x463c54), name, feeName); result = 0
    ; 0x41d6a0 test ebx,ebx / jne 0x41d6e5 ⇒ 一个都没命中 ⇒ 直接返回 1
    if result == 0:                                    ; 0x41d6a4 尾巴
        show_text_box(msg, 0x5dc=1500ms)               ; 0x440cac
        player_say(curPlayer, 3,                        # 0x44ef41
                   *(u32*)(0x48087e + char(curPlayer)*108))   ; 0x48087e 台词表，27 项/角色
    return result                                      ; 0x41d6e5 mov eax,ebx
```

★ 关键口径（差分逐条钉住，全部**不是**常识）：
  1. **`priceStatus` 只读低字节**（`mov ah, byte [esp+0xa8]`，编码 `8a a4 24 a8 00 00 00`）
     ⇒ `0x00000101` 的低字节是 `0x01` ⇒ **不查封**；`0x000001FF` ⇒ 查封。
  2. 查封判据是**两个半字节都非 0**（`0x10`/`0x01`/`0xf0`/`0x0f` 都**不**免收）。
  3. 同盟判据是「地主 `+0x41` == **全局当前玩家** `[0x49910c]` **+ 1**」，
     与实参里的地主不是同一人也可命中（用的是全局，不是第二个实参）。
  4. 死神只认 `god_info == **0x0f**`（物件下标 14）；`0x0e`（下标 13）**不免收**
     —— 与 `0x40fbb8`「由他人賠償」认 `0x0e/0x0f` 两个不同（**非对称**）。
  5. 六个阻碍字节 `+0x32..+0x37` 判据一律是 **byte != 0**（高位标志位也算非 0）。
  6. 优先级严格按上表**自上而下**（查封 > 同盟 > 死神 > 住宿 > 消失 > 坐牢 > 住院 > 冬眠 > 夢遊）。
  7. 免收时**才**弹文字框（1500ms）并让**当前玩家**说一句台词；
     照收时 `0x440cac`/`0x44ef41`/`0x457110` **一次都不调**。
  8. 台词取的是**当前玩家**的 `character(+0x13)`（不是地主的）：`0x48087e + character*108`。

## 逐条核实过的「陷阱」（本函数里哪些**不**适用）

本函数 408 字节的**全部内存读**只有三处来源，别的陷阱一律无从落地：
`[esp+0xa4/a8/ac]`（三实参）、`[0x496b68 + landlord*0x68 + {0, 0x32..0x37, 0x3f, 0x41}]`、
`[0x49910c]`、`[0x48087e + character*0x6c]`。据此：

| 陷阱 | 本函数 |
|---|---|
| 地块表 `0x498e84` / 設施表 `0x498e88` 的步长与字段 | **不适用**：本函数一个都不碰，记录指针由调用方（`0x419a8a` / `0x41a3cc`）给 |
| 物件表 `0x496d08`（绝对基址、0 基下标） | **不适用**：无引用 |
| 遍历常从 1 起、记录 0 看不见 | **不适用**：本函数**没有任何循环** |
| `cmp dword [0x496b30], 0` 那种 4 字节读（只覆盖槽 0..3） | **不适用**：本函数的阻碍判据一律是 **byte** `+0x32..+0x37`（实测 `0x80` 也命中 ⇒ 高位标志位算非 0）|
| `rand` `0x456f2d` | **不适用**：`call` 目标穷举后无它；另用「rand 桩计数」断言恒 0 |
| 少写上界全局（如 `[0x499114]` 人数）⇒ 静默走另一支 | **不适用**：本函数不调任何需要上界的遍历器（无 `0x40d2d3`/`0x441262` 之类）|
| `priceStatus` 的宽度 | ★ **适用**：只读**低字节**（`mov ah, byte [esp+0xa8]`），已用 6 条 `0x0100/0x0101/0x1101/0x1100/0x01FF/0xFF11` 用例钉住 |

## 打桩清单

| VA | 原用途 | 桩 | 打桩理由（合法性） |
|---|---|---|---|
| `0x00452946` | 取玩家姓名（去空格拷进缓冲） | 记 `(dst, src)` + **原样拷贝** + `ret` | 真身内部调 `0x45825d`（`strlen`，`mov es,ds` + `repne scasb`）—— 实测在本仿真器上 `UC_ERR_READ_UNMAPPED @0x458271`（工具限制）。本测试只断言「传给它的 dst/src 是谁」，**不含**去空格语义（那条已由 `test_bail.py` 独立钉住）|
| `0x00457110` | `sprintf(dst, fmt, …)`（CRT `vsprintf` 包装） | 记 `(dst, fmt, a0, a1)` + 把 fmt 串拷进 dst + `ret` | 真身实测 `UC_ERR_READ_UNMAPPED @0x45b392`（CRT 依赖）。本测试的断言是**哪一条分支的格式串**与**实参是谁**，不是格式化结果本身 |
| `0x00440cac` | 弹文字框（Win32 文本渲染） | 记 `(buf, ms)` + `ret` | 真身走 `0x44f9d8` → `call dword cs:[0x46228c]`（未映射的导入 thunk）。断言只需「调了没、参数是什么」|
| `0x0044ef41` | `player_say(player, 槽, 句表)`（含立绘/Win32） | 记 `(player, slot, phrase)` + `ret` | 真身 `call dword [edx+0x64]`（Win32）。断言只需三个实参 |

`0x49910c`（当前玩家）与玩家记录**真读**；**没有**任何被调用的遍历器，
故不需要 `[0x499114]`（人数）之类的上界全局 —— 这一点已被 `call` 目标清单穷举核实：
本函数 408 字节内只有 `0x452946`/`0x457110`×2/`0x440cac`/`0x44ef41` 五个 `call`。
本函数**不摇随机数**（无 `call 0x456f2d`），测试里专门断言「一次都没摇」。

跑法：cd rich4-spec && .venv/bin/python tests/test_toll_exemption.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SCRATCH_BASE, STACK_TOP  # noqa: E402

FN = 0x41D559
GET_NAME = 0x452946
SPRINTF = 0x457110
SHOW_BOX = 0x440CAC
PLAYER_SAY = 0x44EF41

# ── 全局（原版绝对地址） ──────────────────────────────────────────
CUR = 0x49910C                 # 当前玩家（0 基）
CUR_W = 0x499108               # 首富 / 终局用，本函数不读（回归用哨兵）
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NAME = 0x00                  # char* 姓名串指针
P_CHAR = 0x13                  # character（台词表用）
P_HOTEL = 0x32                 # days_in_hotel
P_DISAPPEAR = 0x33
P_PRISON = 0x34
P_HOSPITAL = 0x35
P_SLEEP = 0x36                 # 冬眠
P_SLEEPWALK = 0x37
P_GOD = 0x3F                   # god_info
P_ALLIED = 0x41                # allied_player（0 = 无，否则 player+1）
PHRASE_TABLE = 0x48087E        # 每位角色 27 个 dword（0x6c = 108 字节）
PHRASE_PER_CHAR = 0x6C

# ── 帧布局（由序言 push ebx/esi/ebp + sub esp,0x94 + 三实参 + 返回地址推出） ──
FRAME = STACK_TOP - 0xB0       # 帧基 F
MSGBUF = FRAME                 # 0x41d5a4/0x41d5dc 的 sprintf 目标
NAMEBUF = FRAME + 0x80         # 0x452946 的目标（0x41d57d 的 [esp+0x84]）

# ── 九种免收的格式串（VA → 原文，已在真值里核过） ────────────────
FMT = {
    "sealed": 0x463BB8,
    "ally": 0x463BCD,
    "reaper": 0x463BE2,
    "hotel": 0x463BF5,
    "disappearing": 0x463C08,
    "prison": 0x463C1B,
    "hospital": 0x463C2E,
    "sleeping": 0x463C41,
    "sleepWalking": 0x463C54,
}
FMT_TEXT = {
    "sealed": "房屋查封中\n\n免收%s！",
    "ally": "與%s同盟中\n\n免收%s！",
    "reaper": "死神顯靈\n\n免收%s！",
    "hotel": "%s住宿中\n\n免收%s！",
    "disappearing": "%s消失中\n\n免收%s！",
    "prison": "%s坐牢中\n\n免收%s！",
    "hospital": "%s住院中\n\n免收%s！",
    "sleeping": "%s冬眠中\n\n免收%s！",
    "sleepWalking": "%s夢遊中\n\n免收%s！",
}
# 顺序 = 原版链式比较的顺序（也是复刻 tollExemption 的顺序）
ORDER = ["sealed", "ally", "reaper", "hotel", "disappearing",
         "prison", "hospital", "sleeping", "sleepWalking"]
# 只有一个 %s 的三种（查封 / 死神），其余两个（姓名 + 費名）
ONE_ARG = {"sealed", "reaper"}

BLOCK_FIELD = {
    "hotel": P_HOTEL,
    "disappearing": P_DISAPPEAR,
    "prison": P_PRISON,
    "hospital": P_HOSPITAL,
    "sleeping": P_SLEEP,
    "sleepWalking": P_SLEEPWALK,
}

# ── 暂存区布局（SCRATCH 不在 reset 快照里；计数器与数据槽必须隔开） ──
FEE_NAME = SCRATCH_BASE + 0x1000
SRC_NAME = SCRATCH_BASE + 0x2000
NAME_TEXT = b"Alice Wong"
FEE_TEXT = "過路費".encode("big5")

NC_N = SCRATCH_BASE + 0x0800        # copy_no_space 调用计数
NC_DST = SCRATCH_BASE + 0x0820
NC_SRC = SCRATCH_BASE + 0x0840
S_N = SCRATCH_BASE + 0x0880         # sprintf 调用计数
S_FMT = SCRATCH_BASE + 0x08A0
S_A0 = SCRATCH_BASE + 0x08C0
S_A1 = SCRATCH_BASE + 0x08E0
S_DST = SCRATCH_BASE + 0x0A00
Q_N = SCRATCH_BASE + 0x0900         # 文字框 + 台词 共用计数（也用来验先后次序）
RAND_N = SCRATCH_BASE + 0x07E0      # rand 被调用次数（用来断言"一次都没摇"）
Q_BUF = SCRATCH_BASE + 0x0920
Q_DUR = SCRATCH_BASE + 0x0940
Q_P0 = SCRATCH_BASE + 0x0960
Q_P1 = SCRATCH_BASE + 0x0980
Q_P2 = SCRATCH_BASE + 0x09A0
SEQ = SCRATCH_BASE + 0x09C0

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<70} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def p32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def S(r, i, k):
    """安全地取第 i 次 sprintf 记录的第 k 个字段（没有那次调用时给 None）。

    故意破坏一处 setup 时，某些调用会消失 —— 这时应该出现**红断言**，
    而不是 IndexError 把整轮打断。
    """
    return r["sms"][i][k] if len(r["sms"]) > i else None


def _copy_stub():
    """copy_no_space 桩：记 (dst, src) 后原样拷贝（不去空格）。"""
    return (b"\x8B\x4C\x24\x04"                       # mov ecx,[esp+4]  dst
            + b"\x8B\x54\x24\x08"                     # mov edx,[esp+8]  src
            + b"\xA1" + p32(NC_N)                     # mov eax,[NC_N]
            + b"\x89\x0C\x85" + p32(NC_DST)           # mov [eax*4+NC_DST],ecx
            + b"\x89\x14\x85" + p32(NC_SRC)           # mov [eax*4+NC_SRC],edx
            + b"\x40"                                 # inc eax
            + b"\xA3" + p32(NC_N)                     # mov [NC_N],eax
            + b"\x8A\x02\x88\x01\x41\x42\x84\xC0\x75\xF6"   # 拷贝循环
            + b"\xC3")


def _sprintf_stub():
    """sprintf 桩：把 fmt 原样拷进 dst，并记 (dst, fmt, a0, a1)。"""
    return (b"\x8B\x4C\x24\x04"                       # mov ecx,[esp+4]  dst
            + b"\x8B\x54\x24\x08"                     # mov edx,[esp+8]  fmt
            + b"\x8A\x02\x88\x01\x41\x42\x84\xC0\x75\xF6"   # 拷贝 fmt → dst
            + b"\xA1" + p32(S_N)                      # mov eax,[S_N]
            + b"\x8B\x54\x24\x04" + b"\x89\x14\x85" + p32(S_DST)
            + b"\x8B\x54\x24\x08" + b"\x89\x14\x85" + p32(S_FMT)
            + b"\x8B\x54\x24\x0C" + b"\x89\x14\x85" + p32(S_A0)
            + b"\x8B\x54\x24\x10" + b"\x89\x14\x85" + p32(S_A1)
            + b"\x40" + b"\xA3" + p32(S_N)
            + b"\xC3")


def _show_stub():
    """文字框桩：记 (buf, ms) 与次序标记 1。"""
    return (b"\x8B\x4C\x24\x04"                       # mov ecx,[esp+4]
            + b"\x8B\x54\x24\x08"                     # mov edx,[esp+8]
            + b"\xA1" + p32(Q_N)
            + b"\xC7\x04\x85" + p32(SEQ) + p32(1)     # mov dword [eax*4+SEQ],1
            + b"\x89\x0C\x85" + p32(Q_BUF)
            + b"\x89\x14\x85" + p32(Q_DUR)
            + b"\x40" + b"\xA3" + p32(Q_N)
            + b"\x31\xC0\xC3")


def _say_stub():
    """台词桩：记 (player, slot, phrase) 与次序标记 2。"""
    return (b"\x8B\x4C\x24\x04"                       # mov ecx,[esp+4]
            + b"\x8B\x54\x24\x08"                     # mov edx,[esp+8]
            + b"\xA1" + p32(Q_N)
            + b"\xC7\x04\x85" + p32(SEQ) + p32(2)     # mov dword [eax*4+SEQ],2
            + b"\x89\x0C\x85" + p32(Q_P0)
            + b"\x89\x14\x85" + p32(Q_P1)
            + b"\x8B\x54\x24\x0C"                     # mov edx,[esp+0xc]
            + b"\x89\x14\x85" + p32(Q_P2)
            + b"\x40" + b"\xA3" + p32(Q_N)
            + b"\x31\xC0\xC3")


def install(e):
    """★ 打桩必须在 `setup()` 里（`call()` 先 `reset()`，`patch()` 会重拍快照）。"""
    e.patch(GET_NAME, _copy_stub())
    e.patch(SPRINTF, _sprintf_stub())
    e.patch(SHOW_BOX, _show_stub())
    e.patch(PLAYER_SAY, _say_stub())


def cstr(e, va, limit=64):
    b = e.read(va, limit)
    return b.split(b"\x00")[0].decode("big5", "replace")


class TollExemption:
    def __init__(self):
        self.emu = None

    def run(self, landlord=2, price=0, *, cur=1, allied=0, god=0, block=None,
            cur_char=0, landlord_char=9, price_hi=0):
        """驱动 0x41d559(landlord, priceStatus, feeName) 一次。

        `price_hi` 用来测「只读低字节」：最终实参 = `price_hi<<8 | price`。
        """
        block = dict(block or {})
        price_arg = ((price_hi & 0xFFFFFF) << 8) | (price & 0xFF)
        emu = Emu()

        def setup(e):
            install(e)
            for slot in (NC_N, S_N, Q_N):
                e.write32(slot, 0)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            e.write32(CUR, cur)
            e.write32(CUR_W, 0x5A5A5A5A)          # 本函数不该读它
            pb = PLAYER_BASE + landlord * PLAYER_STRIDE
            e.write32(pb + P_NAME, SRC_NAME)      # 地主姓名字串指针
            e.write8(pb + P_CHAR, landlord_char)
            e.write8(pb + P_ALLIED, allied)
            e.write8(pb + P_GOD, god)
            for off in (P_HOTEL, P_DISAPPEAR, P_PRISON, P_HOSPITAL, P_SLEEP,
                        P_SLEEPWALK):
                e.write8(pb + off, 0)
            for kind, val in block.items():
                e.write8(pb + BLOCK_FIELD[kind], val)
            # 台词取的是**当前玩家**的 character，故意与地主的不同
            e.write8(PLAYER_BASE + cur * PLAYER_STRIDE + P_CHAR, cur_char)

        r = emu.call(FN, [landlord, price_arg, FEE_NAME], setup=setup)
        self.emu = emu
        s_n = emu.readu32(S_N)
        self.out = {
            "ret": r["eax"],
            "signed": r["signed"],
            "esp_delta": r["esp_delta"],
            "insns": r["insns"],
            "nc_n": emu.readu32(NC_N),
            "nc_dst": emu.readu32(NC_DST) if emu.readu32(NC_N) else None,
            "nc_src": emu.readu32(NC_SRC) if emu.readu32(NC_N) else None,
            "nc_text": cstr(emu, NAMEBUF) if emu.readu32(NC_N) else None,
            "s_n": s_n,
            "sms": [(emu.readu32(S_DST + 4 * i), emu.readu32(S_FMT + 4 * i),
                     emu.readu32(S_A0 + 4 * i), emu.readu32(S_A1 + 4 * i))
                    for i in range(s_n)],
            "q_n": emu.readu32(Q_N),
            "seq": [emu.readu32(SEQ + 4 * i) for i in range(emu.readu32(Q_N))],
            "q_buf": emu.readu32(Q_BUF),
            "q_dur": emu.readu32(Q_DUR),
            "q_player": None,
            "q_slot": None,
            "q_phrase": None,
        }
        # 文字框与台词共用同一个计数器 ⇒ 按次序表定位台词那一笔
        seq = self.out["seq"]
        if 2 in seq:
            k = seq.index(2)
            self.out["q_player"] = emu.readu32(Q_P0 + 4 * k)
            self.out["q_slot"] = emu.readu32(Q_P1 + 4 * k)
            self.out["q_phrase"] = emu.readu32(Q_P2 + 4 * k)
        if 1 in seq:
            k = seq.index(1)
            self.out["q_buf"] = emu.readu32(Q_BUF + 4 * k)
            self.out["q_dur"] = emu.readu32(Q_DUR + 4 * k)
        # 命中的是哪一支（用格式串反推）
        hit = None
        if s_n >= 1:
            for kind, va in FMT.items():
                if self.out["sms"][0][1] == va:
                    hit = kind
        self.hit = hit
        self.out["hit"] = hit
        return self.out


def main():
    print("差分测试 · 过路费免收判据（九种免收）0x41d559（408 B）\n")
    t = TollExemption()
    e = Emu()

    # ── 0. 真值表：九条格式串与顺序（从 exe 的 DGROUP 里读，不靠人工转录） ──
    print("[0] 真值表：九条格式串原文与它在链上的位置")
    for kind in ORDER:
        case(f"0x{FMT[kind]:06X} 原文 = {FMT_TEXT[kind]!r}", cstr(e, FMT[kind]), FMT_TEXT[kind])
        n = cstr(e, FMT[kind]).count("%s")
        case(f"  {kind} 的 %s 个数 = {'1' if kind in ONE_ARG else '2'}", n,
             1 if kind in ONE_ARG else 2)

    # ── A. 九种都不命中 ⇒ 照收（返回 1），且尾巴一次都不跑 ────────────
    print("\n[A] 一个都不命中 ⇒ 返回 1（照收）且**不弹框、不说话、不 sprintf**")
    r = t.run()
    case("全零地主 ⇒ ret", r["ret"], 1)
    case("  sprintf 调用次数", r["s_n"], 0)
    case("  文字框调用次数", r["q_n"], 0)
    case("  0x440cac 与 0x44ef41 一次不调（次序表为空）", r["seq"], [])
    case("  取姓名调了一次", r["nc_n"], 1)
    case("  取姓名的 dst = 帧基+0x80（局部姓名缓冲）", r["nc_dst"], NAMEBUF)
    case("  取姓名的 src = 地主记录 +0x00 的姓名串指针", r["nc_src"], SRC_NAME)
    case("  姓名缓冲内容 = 原串", r["nc_text"], NAME_TEXT.decode())
    case("  cdecl 正常收尾（ret 弹掉返回地址）⇒ esp_delta = 4", r["esp_delta"], 4)
    case("  [0x499108] 哨兵未被读改", t.emu.readu32(CUR_W), 0x5A5A5A5A)

    for idx in (0, 1, 3):
        case(f"地主下标 = {idx}（0x68 步长）全零 ⇒ 仍照收", t.run(landlord=idx)["ret"], 1)
    case("地主下标 7（仍在地段内）⇒ 照收", t.run(landlord=7)["ret"], 1)

    # ── B. 查封：高低两个半字节都非 0，且**只读低字节** ─────────────
    print("\n[B] 查封（`房屋查封中`）：两个半字节都非 0；**只读 priceStatus 的低字节**")
    for price, want, desc in [
        (0x11, 0, "两个半字节都非 0"),
        (0x51, 0, "查封卡写的 0x51"),
        (0xFF, 0, "全 1"),
        (0x1F, 0, "1 与 f"),
        (0xF1, 0, "f 与 1"),
        (0x10, 1, "只有高半字节（涨价位）"),
        (0x01, 1, "只有低半字节"),
        (0xF0, 1, "只有高半字节 = f"),
        (0x0F, 1, "只有低半字节 = f"),
        (0x00, 1, "两半都 0"),
        (0x30, 1, "复刻 toll-flow.test.ts 的对照值"),
    ]:
        r = t.run(price=price)
        case(f"priceStatus = 0x{price:02X}（{desc}）⇒ ret", r["ret"], want)
        case(f"  命中支", r["hit"], "sealed" if want == 0 else None)

    r = t.run(price=0xFF)
    case("查封：sprintf 恰 1 次", r["s_n"], 1)
    case("查封：sprintf 的格式串指针", S(r, 0, 1), FMT["sealed"])
    case("★ 查封只带 1 个实参 = 費名（不是地主姓名）", S(r, 0, 2), FEE_NAME)
    case("查封：弹出的缓冲 = 帧基", r["q_buf"], MSGBUF)

    for price, hi, want, desc in [
        (0x00, 0x01, 1, "0x0100：高字节非 0，**低字节为 0** ⇒ 不查封"),
        (0x01, 0x01, 1, "0x0101：低字节 0x01 ⇒ 不查封"),
        (0x01, 0x11, 1, "0x1101：低字节 0x01 ⇒ 不查封"),
        (0x00, 0x11, 1, "0x1100：低字节 0x00 ⇒ 不查封"),
        (0xFF, 0x01, 0, "0x01FF：低字节 0xFF ⇒ 查封"),
        (0x11, 0xFF, 0, "0xFF11：低字节 0x11 ⇒ 查封"),
    ]:
        r = t.run(price=price, price_hi=hi)
        case(f"arg2 = 0x{hi:04X}{price:02X}（{desc}）⇒ ret", r["ret"], want)

    # ── C. 同盟 ────────────────────────────────────────────────────
    print("\n[C] 同盟（`與%s同盟中`）：地主 +0x41 == **当前玩家** [0x49910c] + 1")
    for cur, allied, want, desc in [
        (1, 2, 0, "cur=1、allied=2 = cur+1"),
        (0, 1, 0, "cur=0、allied=1"),
        (3, 4, 0, "cur=3、allied=4"),
        (1, 1, 1, "allied == cur（差一，必须 +1 才命中）"),
        (1, 3, 1, "allied == cur+2"),
        (1, 0, 1, "allied = 0（无同盟）"),
        (0, 0, 1, "cur=0、allied=0"),
        (2, 1, 1, "allied 指向别人"),
    ]:
        r = t.run(cur=cur, allied=allied)
        case(f"{desc} ⇒ ret", r["ret"], want)
        if want == 0:
            case("  命中支 = ally", r["hit"], "ally")

    r = t.run(cur=2, allied=3)
    case("同盟：sprintf 恰 1 次", r["s_n"], 1)
    case("同盟：格式串指针", S(r, 0, 1), FMT["ally"])
    case("★ 同盟：第 1 个实参 = 地主姓名缓冲", S(r, 0, 2), NAMEBUF)
    case("★ 同盟：第 2 个实参 = 費名", S(r, 0, 3), FEE_NAME)
    # +0x40 单独写 2、+0x41 留 0 ⇒ 不命中（证明读的是 +0x41）
    def run_at(off, val, cur=1):
        emu = Emu()

        def setup(e):
            install(e)
            e.write32(CUR, cur)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            pb = PLAYER_BASE + 2 * PLAYER_STRIDE
            e.write32(pb + P_NAME, SRC_NAME)
            e.write8(pb + off, val)
        return emu.call(FN, [2, 0, FEE_NAME], setup=setup)["eax"]

    case("★ +0x41 写 2（cur=1）⇒ 同盟命中", run_at(0x41, 2), 0)
    case("★ +0x40 写 2（cur=1）⇒ 仍照收（f64 不是同盟字段）", run_at(0x40, 2), 1)
    case("★ +0x42 写 2（cur=1）⇒ 仍照收", run_at(0x42, 2), 1)

    # 地主 2 与地主 3 互不串位（两条记录各自独立）
    def run_two_records(which):
        emu = Emu()

        def setup(e):
            install(e)
            e.write32(CUR, 1)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            for p in (2, 3):
                e.write32(PLAYER_BASE + p * PLAYER_STRIDE + P_NAME, SRC_NAME)
            e.write8(PLAYER_BASE + 2 * PLAYER_STRIDE + P_ALLIED, 2)   # 只有地主 2 有同盟
        return emu.call(FN, [which, 0, FEE_NAME], setup=setup)["eax"]

    case("两条记录：地主 2 有同盟 ⇒ 查地主 2 = 免收", run_two_records(2), 0)
    case("两条记录：地主 3 无同盟 ⇒ 查地主 3 = 照收（不串位）", run_two_records(3), 1)

    # 姓名取的是**地主**的 +0x00（当前玩家的姓名是另一条串）
    def run_name_src():
        emu = Emu()

        def setup(e):
            install(e)
            e.write32(CUR, 1)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            e.write(SRC_NAME + 0x40, b"Bob\x00")
            e.write32(PLAYER_BASE + 2 * PLAYER_STRIDE + P_NAME, SRC_NAME)
            e.write32(PLAYER_BASE + 1 * PLAYER_STRIDE + P_NAME, SRC_NAME + 0x40)
        emu.call(FN, [2, 0, FEE_NAME], setup=setup)
        return emu.readu32(NC_SRC), cstr(emu, NAMEBUF)

    case("★★ 姓名取地主(+0x00)而非当前玩家：src 与拷贝内容",
         run_name_src(), (SRC_NAME, NAME_TEXT.decode()))

    # ── D. 死神 ────────────────────────────────────────────────────
    print("\n[D] 死神（`死神顯靈`）：只认 god_info == **0x0F**（物件下标 14）")
    for god, want, desc in [
        (0x0F, 0, "0x0f（下标 14）"),
        (0x0E, 1, "0x0e（下标 13，第二个死神槽）—— 免收**不认**"),
        (0x10, 1, "0x10（下标 15）"),
        (0x01, 1, "0x01"),
        (0xFF, 1, "0xff"),
    ]:
        r = t.run(god=god)
        case(f"god_info = 0x{god:02X}（{desc}）⇒ ret", r["ret"], want)
        case("  命中支", r["hit"], "reaper" if want == 0 else None)

    r = t.run(landlord=3, god=0x0F)
    case("地主的 god_info 也按 0x68 步长读（地主 3）", r["hit"], "reaper")
    r = t.run(god=0x0F)
    case("死神：sprintf 恰 1 次", r["s_n"], 1)
    case("死神：格式串指针", S(r, 0, 1), FMT["reaper"])
    case("★ 死神只带 1 个实参 = 費名", S(r, 0, 2), FEE_NAME)

    def run_offset(off):
        emu = Emu()

        def setup(e):
            install(e)
            e.write32(CUR, 1)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            pb = PLAYER_BASE + 2 * PLAYER_STRIDE
            e.write32(pb + P_NAME, SRC_NAME)
            e.write8(pb + off, 0x0F)
        return emu.call(FN, [2, 0, FEE_NAME], setup=setup)["eax"]

    case("★ 0x0f 写在 +0x3f ⇒ 免收（字段偏移）", run_offset(0x3F), 0)
    case("★ 0x0f 写在 +0x3e ⇒ 照收（不是那一格）", run_offset(0x3E), 1)
    case("★ 0x0f 写在 +0x40 ⇒ 照收（不是那一格）", run_offset(0x40), 1)

    # ── E. 六个阻碍字节 +0x32..+0x37 ───────────────────────────────
    print("\n[E] 六个阻碍字节：+0x32 住宿 / +0x33 消失 / +0x34 坐牢 / +0x35 住院 / +0x36 冬眠 / +0x37 夢遊")
    for kind in ["hotel", "disappearing", "prison", "hospital", "sleeping",
                 "sleepWalking"]:
        off = BLOCK_FIELD[kind]
        r = t.run(block={kind: 1})
        case(f"+0x{off:02X} = 1 ⇒ 免收（{kind}）", r["ret"], 0)
        case("  命中支与格式串", r["hit"], kind)
        case("  格式串指针", S(r, 0, 1), FMT[kind])
        case("  ★ 两个实参 = 姓名缓冲 + 費名",
             (S(r, 0, 2), S(r, 0, 3)), (NAMEBUF, FEE_NAME))
        r = t.run(block={kind: 0x80})
        case(f"+0x{off:02X} = 0x80（只剩高位标志）⇒ 仍免收（判据是 byte != 0）", r["ret"], 0)

    print("\n[E2] 字段偏移的排他性：只有 +0x32..+0x37 这六个字节算数")
    for off in (0x31, 0x38, 0x39, 0x3A, 0x42):
        emu = Emu()

        def setup(e, off=off):
            install(e)
            e.write32(CUR, 1)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            pb = PLAYER_BASE + 2 * PLAYER_STRIDE
            e.write32(pb + P_NAME, SRC_NAME)
            e.write8(pb + off, 1)

        case(f"★ 把 1 写在 +0x{off:02X} ⇒ 仍照收（不在免收清单里）",
             emu.call(FN, [2, 0, FEE_NAME], setup=setup)["eax"], 1)

    print("\n[E3] 优先级：链式比较自上而下（查封 > 同盟 > 死神 > 住宿 > 消失 > 坐牢 > 住院 > 冬眠 > 夢遊）")
    r = t.run(price=0x11, cur=1, allied=2, god=0x0F, block={"hotel": 1, "prison": 1})
    case("全部九条同时成立 ⇒ 命中 sealed", r["hit"], "sealed")
    case("  且只 sprintf 一次", r["s_n"], 1)
    r = t.run(cur=1, allied=2, god=0x0F, block={"hotel": 1})
    case("同盟 + 死神 + 住宿 ⇒ 命中 ally", r["hit"], "ally")
    r = t.run(cur=1, god=0x0F, block={"hotel": 1, "sleepWalking": 1})
    case("死神 + 住宿 + 夢遊 ⇒ 命中 reaper", r["hit"], "reaper")
    r = t.run(block={"hotel": 1, "disappearing": 1})
    case("住宿 + 消失 ⇒ 命中 hotel", r["hit"], "hotel")
    r = t.run(block={"disappearing": 1, "prison": 1})
    case("消失 + 坐牢 ⇒ 命中 disappearing", r["hit"], "disappearing")
    r = t.run(block={"prison": 1, "hospital": 1})
    case("坐牢 + 住院 ⇒ 命中 prison", r["hit"], "prison")
    r = t.run(block={"hospital": 1, "sleeping": 1})
    case("住院 + 冬眠 ⇒ 命中 hospital", r["hit"], "hospital")
    r = t.run(block={"sleeping": 1, "sleepWalking": 1})
    case("冬眠 + 夢遊 ⇒ 命中 sleeping", r["hit"], "sleeping")
    r = t.run(cur=2, allied=2, block={"hotel": 1})
    case("allied == cur（同盟不成立）+ 住宿 ⇒ 命中 hotel（同盟不拦）", r["hit"], "hotel")
    r = t.run(god=0x0E, block={"hotel": 1})
    case("god = 0x0e（非死神）+ 住宿 ⇒ 命中 hotel", r["hit"], "hotel")

    # ── F. 尾巴：文字框 + 台词 ─────────────────────────────────────
    print("\n[F] 免收时才跑的尾巴：文字框 1500ms + 当前玩家说一句（次序固定）")
    r = t.run(block={"prison": 1}, cur=1, cur_char=0)
    case("文字框调用次数", r["q_n"], 2)          # 1 框 + 1 台词
    case("次序 = [框, 台词]", r["seq"], [1, 2])
    case("文字框的缓冲 = 帧基", r["q_buf"], MSGBUF)
    case("★ 文字框时长 = 0x5dc（1500ms）", r["q_dur"], 0x5DC)
    case("台词的 player = 当前玩家", r["q_player"], 1)
    case("台词的槽位 = 3", r["q_slot"], 3)
    expect0 = e.readu32(PHRASE_TABLE + 0 * PHRASE_PER_CHAR)
    case("★ 台词指针 = 0x48087e + 当前玩家角色*0x6c", r["q_phrase"], expect0)

    for ch in (1, 5, 11):
        r = t.run(block={"prison": 1}, cur=2, cur_char=ch)
        case(f"当前玩家角色 = {ch} ⇒ 台词指针 = 该角色的表项",
             r["q_phrase"], e.readu32(PHRASE_TABLE + ch * PHRASE_PER_CHAR))
    case("  角色 0/1/5/11 的表项互不相同", len({e.readu32(PHRASE_TABLE + c * PHRASE_PER_CHAR)
                                          for c in (0, 1, 5, 11)}), 4)

    # 台词取「当前玩家」的角色，不是地主的角色：地主角色被故意设成 9
    r = t.run(landlord=2, cur=1, cur_char=3, landlord_char=9, block={"prison": 1})
    case("★★ 台词角色取当前玩家（3）而非地主（9）",
         r["q_phrase"], e.readu32(PHRASE_TABLE + 3 * PHRASE_PER_CHAR))
    r = t.run(landlord=2, cur=1, cur_char=9, landlord_char=3, block={"prison": 1})
    case("★★ 反向对照：当前玩家角色 9、地主 3 ⇒ 取 9",
         r["q_phrase"], e.readu32(PHRASE_TABLE + 9 * PHRASE_PER_CHAR))

    # 台词表结构真值：12 角色 × 27 项，全部指向 '#' 开头的字符串
    bad = []
    for c in range(12):
        for k in range(27):
            p = e.readu32(PHRASE_TABLE + c * PHRASE_PER_CHAR + 4 * k)
            if not (0x463000 <= p < 0x48A000) or e.read8(p) != ord("#"):
                bad.append((c, k, p))
    case("台词表 12×27 项全部是 DGROUP 内 '#' 开头的串", bad, [])
    case("台词表首项 = #1063耶穌保佑 所在串", cstr(e, e.readu32(PHRASE_TABLE)), "#1063耶穌保佑")

    print("\n[F2] 照收时尾巴整段不跑（把免收条件全部撤销后复查）")
    r = t.run(god=0x0E, cur=1, allied=1, block={"sleeping": 0, "sleepWalking": 0})
    case("ret", r["ret"], 1)
    case("  文字框 0 次、台词 0 次", r["q_n"], 0)
    case("  sprintf 0 次", r["s_n"], 0)
    case("  取姓名仍然调 1 次（它在判据之前）", r["nc_n"], 1)

    # ── G. 返回值只有 0/1；不读别的全局 ───────────────────────────
    print("\n[G] 返回值恒 ∈ {0,1}；本函数不摇随机数、不依赖人数上界")
    seen = set()
    for kw in ({}, {"price": 0x11}, {"god": 0x0F}, {"allied": 2, "cur": 1},
               {"block": {"hotel": 1}}, {"block": {"sleepWalking": 1}},
               {"price": 0x10}, {"god": 0x0E}, {"cur": 3, "allied": 3},
               {"landlord": 0, "block": {"prison": 1}}, {"landlord": 7}):
        seen.add(t.run(**kw)["ret"])
    case("  横扫 11 种输入：返回值集合恰为 {0,1}", sorted(seen), [0, 1])
    r = t.run(block={"hotel": 1})
    case("  返回值是 32 位 0（不是别的）", r["ret"] == 0 and r["signed"] == 0, True)
    case("  指令数在合理范围（< 400）", r["insns"] < 400, True)
    case("  cdecl：esp_delta == 4（被调方没自己清栈）", r["esp_delta"], 4)

    def run_no_rand():
        """把 rand 打成 '被调用就返回 0xDEADBEEF' 并计数，确认本函数从不调它。"""
        emu = Emu()

        def setup(e):
            install(e)
            e.write32(CUR, 1)
            e.write(FEE_NAME, FEE_TEXT + b"\x00")
            e.write(SRC_NAME, NAME_TEXT + b"\x00")
            pb = PLAYER_BASE + 2 * PLAYER_STRIDE
            e.write32(pb + P_NAME, SRC_NAME)
            e.write8(pb + P_HOTEL, 1)
            # rand 桩：命中就 +1 并返回 0xDEADBEEF
            e.patch(0x456F2D, b"\x83\x05" + p32(RAND_N) + b"\x01"
                              + b"\xB8\xEF\xBE\xAD\xDE\xC3")
            e.write32(RAND_N, 0)
        emu.call(FN, [2, 0, FEE_NAME], setup=setup)
        return emu.readu32(RAND_N)

    case("★ 本函数不摇随机数（rand 桩计数 = 0）", run_no_rand(), 0)

    # ── H. 地址级：帧布局与实参槽 ─────────────────────────────────
    print("\n[H] 帧布局：arg1=[F+0xa4]、arg2=[F+0xa8]、arg3=[F+0xac]；F = STACK_TOP-0xb0")
    case("  MSGBUF = STACK_TOP - 0xb0", MSGBUF, 0x53FE50)
    case("  NAMEBUF = MSGBUF + 0x80", NAMEBUF, 0x53FED0)
    r = t.run()
    case("  取姓名的 dst 恰为 NAMEBUF", r["nc_dst"], NAMEBUF)
    case("  姓名串指针来自 player[landlord]+0x00", r["nc_src"], SRC_NAME)
    r = t.run(price=0x11)
    case("  查封支 sprintf 的 dst 恰为 MSGBUF（= 帧基）", S(r, 0, 0), MSGBUF)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 78}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
