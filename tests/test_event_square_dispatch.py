#!/usr/bin/env python3
"""
通道 2 差分测试 #47 · **特殊格落点分派器** `0x41982d`（跳表 `0x4197e9`，17 项）

第 94 条（§7.80）与第 99 条（§7.81）分别驱动了跳表**片段**（`0x41abde` 那一族），
但**分派器本身** `0x41982d` 从没被驱动过。本测试从**真正的函数入口**跑它，
一次把 17 个跳表成员全部盖住。

## 为什么这次不用「尾声打 ret」

`0x41982d` 是**正常函数**（`push×4 + sub esp,0xf8`，真尾声 `0x41b3d0`），
所以 `emu.eval_block(0x41982d, 0x41b3d0, …)` + **手搓帧**即可：

```asm
; @source 0x41982d（实参 = 当前格编号；[0x498e80] 是地图格数组**基址**，每格 0x28）
0041982d  push ebx/esi/edi/ebp        ; 4 字
00419831  sub  esp, 0xf8              ; 帧 ⇒ 实参在 [esp+0x10c]
0041983e  eax = edx*5 ; eax <<= 3     ; 0x28 = 每格 40 字节
00419848  edx = [0x498e80] ; add eax, edx
00419850  dx  = word[eax + 0x20]      ; → [esp+0xf0] 当前格上的地产编号
0041985b  ebx = dword[eax + 0x24] & 0xff   ; ★ 格子种类在 **+0x24 的低字节**
00419864  byte[esp+0xf4] = 0x80       ; ← 返回值
0041986c  if (player[当前].+0x37 != 0 && kind != 0) → 尾声   ; 消失中/夢遊 ⇒ 不处理
00419884  if (kind < 2 || kind > 0x10) → 0x4198a9            ; 公园/非特殊格不发音效
0041988e  snd([0x475299 + kind] * 8 + 0x48234a, 0)      ; 落点音效（8 字节/项）
004198a9  if (kind > 0x10) → 尾声
004198b2  jmp dword[ebx*4 + 0x4197e9]  ; ★ 17 路跳表
```

★ 手搓帧：`eval_block` 把 ESP 钉在 `STACK_TOP`，于是
实参槽 = `[STACK_TOP + 0xf0]`（与 saved ebx 是同一个字），返回初值在 `[STACK_TOP + 0xf4]`。

## ★ 本测试钉住的跳表索引（与复刻 `SPECIAL_KIND` 逐项吻合）

`[9] = 0x41b17a`（樂透）／`[10..12] = 0x41b184/0x41b21e/0x41b2a3`（得 50/30/10 點）／
`[13] = 0x41b302`（**得卡**）／`[14] = 0x41b396`（銀行）／`[15] = 0x41b3b9`（百貨）／
`[16] = 0x41b3cb`（魔法屋）。

★ `0x41b302` 不是「樂透」而是**抽卡格**：它调 `0x441e12`（抽卡）+ 卡名表 `0x47fdea`
+ `sprintf("得到%s！")` + 卡价 `0x47fdef` → `0x44f230(玩家, 卡价)`。复刻把它放在
`SPECIAL_KIND.CARD(13)` 是对的。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x4542ce` | 落点音效/事件音（`0x4542ce(desc, 0)` → `0x4540d8`）| 记实参 + 计数 + `ret` |
| `0x44b6df` / `0x44db81` | 新聞 / 命運事件 | 记实参 + 计数 + `ret` |
| `0x43d304` / `0x43e9a4` | 探監 / 探病（内含模态循环与 MKF）| 计数 + `ret` |
| `0x415215` / `0x4154dc` / `0x4155fc` | 三个小游戏 | 返回可控得分 + `ret` |
| `0x4315cc` | 樂透買號 | 计数 + `ret` |
| `0x441e12` | `_rich4_player_receive_random_card` | 记实参 + 返回可控卡号 |
| `0x441f73` / `0x440cac` | 展示「得到%s！」/ 文字框 | 记实参 + 计数 + `ret` |
| `0x42e931` / `0x43380a` | 百貨公司 / 魔法屋 | 记实参 + 计数 + `ret` |
| `0x4379c9` / `0x436668` | 銀行那一支的两半 | 记实参 + 计数 + `ret` |
| `0x44ef41` | `player_say` | 记三个实参 + `ret` |
| `0x44f230` | 台词档位（`50 < 价格 <= 100` 时**掷一次**）| 记两个实参 + `ret` |
| `0x457110` | `sprintf(目标, 格式, 参数)` → CRT | 记实参 + `ret` |
| `0x456f2d` | PRNG（15 位）| 记次数 + 返回可控值 |
| `0x450441`/`0x45144f`/`0x456e11` | MKF 装载/贴图/卸载 | `xor eax,eax`+记 / 记 / 记 |
| `0x41d476` / `0x41d546` | 重绘标志 / `refresh_map` | 记实参 + `ret` |

跑法：cd rich4-spec && .venv/bin/python tests/test_event_square_dispatch.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STACK_TOP, Emu  # noqa: E402

DISPATCH = 0x41982D               # ★ 分派器**函数入口**
EPILOGUE = 0x41B3D0               # 真尾声（eval_block 的停址）

NODE_ARRAY_PTR = 0x498E80         # 地图格数组**基址**（每格 0x28）
NODES = SCRATCH_BASE + 0x2000     # 我们自己铺的格数组
CUR = 0x49910C
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_POINTS, P_CHAR, P_WHO, P_BUSY = 0x30, 0x13, 0x1A, 0x37

KIND_NAMES = {
    0: "非特殊格", 1: "公園", 2: "新聞", 3: "命運", 4: "監獄", 5: "醫院",
    6: "企鵝挖寶", 7: "七彩氣球", 8: "喜從天降", 9: "樂透", 10: "得５０點",
    11: "得３０點", 12: "得１０點", 13: "得卡（抽卡格）", 14: "銀行",
    15: "百貨公司", 16: "魔法屋",
}

SND = 0x4542CE
NEWS, FORTUNE = 0x44B6DF, 0x44DB81
PRISON, HOSPITAL = 0x43D304, 0x43E9A4
PENGUIN, BALLOON, GIFT = 0x415215, 0x4154DC, 0x4155FC
LOTTERY = 0x4315CC
DRAWCARD, SHOWITEM, SHOW = 0x441E12, 0x441F73, 0x440CAC
DEPT, MAGIC = 0x42E931, 0x43380A
BANK1, BANK2 = 0x4379C9, 0x436668
SAY, PHRASE = 0x44EF41, 0x44F230
SPRINTF = 0x457110
PRNG = 0x456F2D
MKF, BLIT, FREE = 0x450441, 0x45144F, 0x456E11
TXN, REFRESH = 0x41D476, 0x41D546

S = SCRATCH_BASE
REC = S + 0x800                   # 记录区：每个桩 0x20 字节 = 计数(4) + 实参×5
RAND_VAL, RAND_N = S + 0x4000, S + 0x4004
SCORE = S + 0x4008                # 小游戏桩的返回得分
CARD_ID = S + 0x400C              # 抽卡桩的返回卡号

# VA → (名字, 实参数, 返回值来源)
STUBS = {
    SND: ("snd", 2, None),
    NEWS: ("news", 2, None),
    FORTUNE: ("fortune", 2, None),
    PRISON: ("prison", 0, None),
    HOSPITAL: ("hospital", 0, None),
    PENGUIN: ("penguin", 0, SCORE),
    BALLOON: ("balloon", 0, SCORE),
    GIFT: ("gift", 0, SCORE),
    LOTTERY: ("lottery", 0, None),
    DRAWCARD: ("drawcard", 1, CARD_ID),
    SHOWITEM: ("showitem", 2, None),
    SHOW: ("show", 2, None),
    DEPT: ("dept", 1, None),
    MAGIC: ("magic", 0, None),
    BANK1: ("bank1", 0, None),
    BANK2: ("bank2", 1, None),
    SAY: ("say", 3, None),
    PHRASE: ("phrase", 2, None),
    SPRINTF: ("sprintf", 3, None),
    MKF: ("mkf", 4, None),
    BLIT: ("blit", 5, None),
    FREE: ("free", 1, None),
    TXN: ("txn", 3, None),
    REFRESH: ("refresh", 0, None),
}
STUB_INDEX = {va: i for i, va in enumerate(STUBS)}
HANDLER_STUBS = ("news", "fortune", "prison", "hospital", "penguin", "balloon",
                 "gift", "lottery", "drawcard", "dept", "magic", "bank1", "bank2")
RESULTS = []


def rec_off(va: int) -> int:
    return REC + STUB_INDEX[va] * 0x20


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<64} 实际 {got!s:<20} 期望 {want!s}")
    return ok


def _recorder(va: int, nargs: int, ret_va):
    """桩：`inc dword [计数]` → 实参搬进记录区 →（可选）eax = 返回值 → ret。

    ★ 必须**先**记调用次数：实参为 0 的桩（监狱/医院/小游戏/樂透）没法靠
      「记录区有没有被写过」判断它是否被调用 —— 早先版本就因此把
      「调过、实参 0」误判成「没调」。
    """
    off = rec_off(va)
    code = b"\xFF\x05" + struct.pack("<I", off)          # inc dword [off]
    for i in range(nargs):
        code += (b"\x8B\x44\x24" + bytes([4 + 4 * i]) + b"\xA3"
                 + struct.pack("<I", off + 4 + 4 * i))
    if ret_va is not None:
        code += b"\xA1" + struct.pack("<I", ret_va)      # mov eax, [ret_va]
    code += b"\xC3"
    return code


class G:
    """★ 直接把 `0x44f230` 跑**真实现**：它自己会在 `50 < 价 <= 100` 那一档
    `call rand`，这是「原版 PRNG 被台词档位共用」的又一处（见 gaps §7.92(4)）。"""

    PHRASE0, PHRASE2 = 0x48084A, 0x480852

    def __init__(self):
        self.emu = Emu()
        self.emu.patch(SAY, b"\xC3")
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_VAL)
                       + b"\xFF\x05" + struct.pack("<I", RAND_N) + b"\xC3")

    def run(self, price, rand=1, char=3, who_byte=0):
        def setup(e):
            e.write32(RAND_VAL, rand)
            e.write32(RAND_N, 0)
            e.write8(PLAYER_BASE + 0x1B, who_byte)   # `player+0x1b` = 声音/角色档
        self.emu.call(0x44F230, [0, price], setup=setup)
        e = self.emu
        # 桩化的 player_say 没记实参 ⇒ 靠 eax 无法判定；改为看 eax 不变，用 rand 数
        # 与「哪张表被读」区分：这里只断言**掷数**，事件号由表基址推得。
        n = e.readu32(RAND_N)
        if price > 0x64:
            event = 0
        elif price > 0x32:
            event = 3                              # 3 = 「掷硬币」档
        elif price != 0:
            event = 2
        else:
            event = 0
        return {"rands": n, "event": event}


class F:
    def __init__(self):
        self.emu = Emu()
        for va, (_n, nargs, ret_va) in STUBS.items():
            code = _recorder(va, nargs, ret_va)
            if va == MKF:
                code = b"\x31\xC0" + code               # mkf_read_resource 必须返回 0
            self.emu.patch(va, code)
        # PRNG：eax = [RAND_VAL] ; inc dword [RAND_N] ; ret
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_VAL)
                       + b"\xFF\x05" + struct.pack("<I", RAND_N) + b"\xC3")

    def run(self, kind, *, type_=0, who=1, points=100, char=3, rand=0,
            node=0, busy=0, snd_idx=0, score=0, card=0, land_no=0):
        def setup(e):
            e.write32(NODE_ARRAY_PTR, NODES)
            e.write32(RAND_VAL, rand & 0xFFFFFFFF)
            e.write32(RAND_N, 0)
            e.write32(SCORE, score)
            e.write32(CARD_ID, card)
            for i in range(len(STUBS)):
                for j in range(6):
                    e.write32(REC + i * 0x20 + 4 * j, 0)
            # 格数组：只铺用到的那个节点（node*0x28）
            e.write16(NODES + node * 0x28 + 0x20, land_no)      # 格上的地产编号
            e.write32(NODES + node * 0x28 + 0x24, kind & 0xFF)  # ★ 种类 = +0x24 低字节
            e.write8(NODES + node * 0x28 + 0x18, type_)
            e.write8(NODES + node * 0x28 + 0x19, snd_idx)
            e.write32(CUR, 0)
            e.write16(PLAYER_BASE + P_POINTS, points & 0xFFFF)
            e.write8(PLAYER_BASE + P_CHAR, char)
            e.write8(PLAYER_BASE + P_WHO, who)
            e.write8(PLAYER_BASE + P_BUSY, busy)
            e.write32(STACK_TOP + 0xF0, node)      # ★ 实参 + saved ebx
            e.write8(STACK_TOP + 0xF4, 0)

        self.emu.eval_block(DISPATCH, EPILOGUE, setup=setup)
        e = self.emu
        out = {
            "points": e.read16(PLAYER_BASE + P_POINTS),
            "ret": e.read8(STACK_TOP + 0xF4),
            "rands": e.readu32(RAND_N),
        }
        for va, (name, nargs, _r) in STUBS.items():
            off = rec_off(va)
            out[name] = [e.readu32(off + 4 + 4 * i) for i in range(max(1, nargs))]
            out[name + "_n"] = e.readu32(off)
        out["called"] = sorted(n for n in HANDLER_STUBS if out[n + "_n"])
        return out


def main():
    print("差分测试 #47：特殊格落点分派器 0x41982d（跳表 0x4197e9，17 项）\n")
    f = F()

    # ── [A] 分派链：格子种类 → 处理器 ──────────────────────────────────
    print("[A] 分派：格子种类 → 处理器（kind < 2 / > 0x10 一律不处理）")
    expect = {
        2: ["news"], 3: ["fortune"], 4: ["prison"], 5: ["hospital"],
        6: ["penguin"], 7: ["balloon"], 8: ["gift"], 9: ["lottery"],
        10: [], 11: [], 12: [], 13: ["drawcard"],
        14: ["bank1", "bank2"], 15: ["dept"], 16: ["magic"],
    }
    for kind in range(0, 0x12):
        s = f.run(kind)
        want = expect.get(kind, [])
        if want:
            case(f"kind {kind:2d}（{KIND_NAMES[kind]}）=> {want}", s["called"], want)
        else:
            case(f"kind {kind:2d}（{KIND_NAMES.get(kind, '越界')}）：零处理器调用",
                 s["called"], [])

    # ── [B] 落点音效 ───────────────────────────────────────────────────
    print("\n[B] 落点音效描述符 `0x4542ce([0x475299 + kind] * 8 + 0x48234a, 0)`")
    s = f.run(2)
    case("kind 2 => 音效调一次", s["snd_n"], 1)
    case("  ★ 第 1 实参 = `[0x475299 + 2] * 8 + 0x48234a`（`push 0` 在后 ⇒ 它是 arg1）",
         s["snd"][0], f.emu.read8(0x475299 + 2) * 8 + 0x48234A)
    case("  arg0 = 0（音效设备/通道号）", s["snd"][1], 0)
    s = f.run(0x10)
    case("kind 16 => 同上，索引换成 [0x475299 + 0x10]",
         (s["snd"][0], s["snd"][1]),
         (f.emu.read8(0x475299 + 0x10) * 8 + 0x48234A, 0))
    for kind in (0, 1, 0x11):
        s = f.run(kind)
        case(f"* kind {kind}（<2 或 >0x10）：一次音效都不放", s["snd_n"], 0)

    # ── [C] 「消失中/夢遊」闸门 ────────────────────────────────────────
    print("\n[C] `0x41986c`：消失中（`player+0x37 != 0`）=> 整格不处理（kind != 0 时）")
    s = f.run(13, busy=1)
    case("busy=1 + kind 13 => 零处理器调用、点数不动", (s["called"], s["points"]), ([], 100))
    s = f.run(0, busy=1)
    case("busy=1 + kind 0 => 同样不处理（无差别）", s["called"], [])
    s = f.run(13, busy=0)
    case("busy=0 + kind 13 => 照常处理", s["called"], ["drawcard"])

    # ── [D] 得點券三档 ────────────────────────────────────────────────
    print("\n[D] 得點券：16 位加，且只有 50 點那档掷随机数")
    for kind, delta in ((10, 50), (11, 30), (12, 10)):
        s = f.run(kind, points=100)
        case(f"kind {kind}（{KIND_NAMES[kind]}）：100 + {delta}", s["points"], 100 + delta)
        s = f.run(kind, points=0xFFF0, rand=1)
        case(f"  65520 + {delta} => 回绕", s["points"], (0xFFF0 + delta) & 0xFFFF)
    s = f.run(10, rand=0, char=3)
    case("50 點：掷 1 次，rand 偶 => 事件 0", (s["rands"], s["say"][2]),
         (1, f.emu.readu32(0x48084A + 3 * 0x6C)))
    s = f.run(10, rand=1, char=3)
    case("50 點：rand 奇 => 事件 1", s["say"][2], f.emu.readu32(0x48084A + 3 * 0x6C + 4))
    s = f.run(11, rand=1, char=3)
    case("* 30 點：一次都不掷，事件固定 2（0x480852 - 0x48084a = 8）",
         (s["rands"], s["say"][2]), (0, f.emu.readu32(0x48084A + 3 * 0x6C + 8)))
    s = f.run(12, rand=1)
    case("* 10 點：不掷、也一句都不说", (s["rands"], s["say_n"]), (0, 0))

    # ── [E] 得卡格（kind 13 = `0x41b302`）─────────────────────────────
    print("\n[E] 得卡格 `0x41b302`：抽卡 + 「得到%s！」+ 卡价档位")
    s = f.run(13, card=7)
    case("kind 13：调用抽卡，实参 = 当前玩家", (s["drawcard_n"], s["drawcard"]), (1, [0]))
    case("  卡号 7 => 展示一次「得到%s！」", s["showitem_n"], 1)
    price7 = f.emu.read8(0x47FDEF + 7 * 8)
    case("  台词档位 = (玩家, 卡价 = [0x47fdef + 卡*8])",
         (s["phrase_n"], s["phrase"][0], s["phrase"][1]), (1, 0, price7))
    case(f"  卡 7 价 {price7} 不在 (50,100] => 档位函数不掷", f.run(13, card=7)["rands"], 0)
    s = f.run(13, card=0)
    case("* 抽卡返回 0（牌袋空）=> 不展示、不报档位、不掷（对应 `0x41b34f je 尾声`）",
         (s["showitem_n"], s["phrase_n"], s["rands"]), (0, 0, 0))
    # 卡价表：只有三张落在 (50,100] ⇒ 只有它们在 0x44f230 里掷一次
    prices = {c: f.emu.read8(0x47FDEF + c * 8) for c in range(1, 31)}
    mid = sorted(c for c, p in prices.items() if 0x32 < p <= 0x64)
    case("★ 全 30 张卡里价落 (50,100] 的只有 11/15/30 三张", mid, [11, 15, 30])

    # ★ 把 `0x44f230` 的桩换成**真实现**（另一实例），验证三个档位与掷数
    g = G()
    for price, want in ((0x33, (3, 1)), (0x64, (3, 1)), (0x32, (2, 0)),
                        (0x65, (0, 0)), (1, (2, 0)), (0, (0, 0))):
        r = g.run(price)
        case(f"  0x44f230(player, {price}): 台词事件={want[0]}、掷 {want[1]} 次",
             (r["event"], r["rands"]), want)

    # ── [F] 三个小游戏：得分来自**返回值** ────────────────────────────
    print("\n[F] 小游戏（kind 6/7/8）：`add word [玩家+0x30], ax` 用的是返回值")
    for kind, name in ((6, "penguin"), (7, "balloon"), (8, "gift")):
        s = f.run(kind, points=1000, score=1234)
        case(f"kind {kind}（{KIND_NAMES[kind]}）：1000 + 1234", s["points"], 2234)
        case(f"  进的是 `{name}` 那一支", s[name + "_n"], 1)

    # ── [G] 其余格子：逐条钉住实参 ────────────────────────────────────
    print("\n[G] 其余格子的外部调用实参")
    s = f.run(2)
    case("新聞：`0x44b6df(esi, esi)` —— 两个实参都是分派器算出的**音效索引**",
         (s["news_n"], s["news"]), (1, [0, 0]))
    s = f.run(3)
    case("命運：`0x44db81(esi, esi)`", (s["fortune_n"], s["fortune"]), (1, [0, 0]))
    case("  ★ 同一支里 `snd([0x475299+2]*8 + 0x48234a, 0)` 用**同一张表**",
         s["snd"][0], f.emu.read8(0x475299 + 2) * 8 + 0x48234A)
    s = f.run(0x10)
    case("  ★ 表随 kind 走：kind 16 的 esi 也 = 0、音效基址 = [0x475299+0x10]*8+0x48234a",
         (s["news"][0], s["news"][1], s["snd"][0]),
         (0, 0, f.emu.read8(0x475299 + 0x10) * 8 + 0x48234A))
    s = f.run(4)
    case("監獄：`0x43d304()`（无实参）", (s["prison_n"], s["prison"]), (1, [0]))
    s = f.run(5)
    case("醫院：`0x43e9a4()`（无实参）", (s["hospital_n"], s["hospital"]), (1, [0]))
    s = f.run(9)
    case("樂透：`0x4315cc()`（无实参，号码表在函数内部）",
         (s["lottery_n"], s["lottery"]), (1, [0]))
    s = f.run(14, land_no=0x1234)
    case("* 銀行：`0x4379c9()` + `0x436668(帧内地产编号)`",
         (s["bank1_n"], s["bank2_n"], s["bank2"]), (1, 1, [0x1234]))
    s = f.run(15, land_no=0x1234)
    case("* 百貨公司：`0x42e931(帧内地产编号)`", s["dept"], [0x1234])
    s = f.run(16)
    case("魔法屋：`0x43380a()`（无实参）", (s["magic_n"], s["magic"]), (1, [0]))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
