#!/usr/bin/env python3
"""
通道 2 差分测试 #35 · **銀行格** `0x004379c9`（`bank_square`）

落在銀行格上做的事：先看「銀行拒絕往來」还剩几天，然后**真人开柜台的模态屏**、
**电脑按 `+0x19`（現金↔存款比例）把現金/存款重分一次**。

## 反汇编骨架（A 级）

```asm
004379d3  edx = cur*0x68
004379da  ah = [player + 0x3b]                  ; days_rejected_by_bank
004379e0  if (ah != 0) {                        ; ★ 拒绝往来：只印一行字就走
004379e4      sprintf(buf, "銀行拒絕往來\\n\\n還剩%d天！", (ah & 0x7f) + 1)
00437a0b      show(buf, 0x3e8)                  ; 1000 毫秒
00437a13      goto 收尾
00437a18  cl = [player + 0x15]                  ; who_plays
00437a1e  if (cl == 1) { …模态屏（载 MKF 0x18 / Wait_0402_Message 0x436ef8）… goto 收尾 }
; ── 电脑分支 0x437acd ──
00437acd  ecx = [0x497160] & 0xff               ; 今天（低字节 = 日）
00437ad9  ebx = 現金(+0x1c) + 存款(+0x20)        ; 总资产
00437ae5  ratio = f32(現金 / 总资产)
00437b02  target = f32(f32([player+0x19]) / 100.0f)
00437b23  if (日 <= 7)  target = f32(target × 1.5)      ; double 1.5
00437b3c  if (日 >= 26) target = f32(target × 0.5)      ; double 0.5
00437b55  if (target >= 1.0f) target = 0.9f
00437b6f  else if (target <= 0.0f) target = 0.1f
00437b88  diff = ratio − target
00437ba6  if (diff >= +0.25) goto 重分             ; [0x464c20] = 0.25（double）
00437bb8  if (diff <= −0.25) goto 重分             ; [0x464c28] = −0.25
00437bc1  if (現金 != 0) goto 收尾                  ; ★ 带内且現金非 0 ⇒ 什么都不做
; ── 重分 0x437bca ──
00437bca  新現金 = trunc(总资产 × target)           ; fild/fmul/call 0x457dbc(向零截断)/fistp
00437bfb  [player+0x1c] = 新現金 ; [player+0x20] = 总资产 − 新現金
00437c0a  call 0x41d433(cur)                       ; 重绘
00437c14  call 0x436b0a(1)                         ; 存取款动画
```

⚠️ **总资产 = 0 的数值事故**：原版这时 `0/0 = NaN`，NaN 的比较全为「无序」
⇒ 落进重分那一支，`fistp` 把 NaN 写成 `0x80000000`，現金与存款**双双变成 −2147483648**。
那是数值事故不是规则，复刻**有意不同**（原样返回），登记在 `known-deviations.md` 的 Q-BANK-3。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x457110` | 拼字符串 | 记实参 + `ret` |
| `0x440cac` | 显示文字框 | 记一笔 + `ret` |
| `0x41d433` / `0x436b0a` | 重绘 / 存取款动画 | 记一笔 + `ret` |
| `0x450441` / `0x4018e7` / `0x45285e` / `0x41d476` / `0x456e11` | 模态屏那一串 | `xor eax,eax / ret` |

`0x457dbc`（向零截断）真跑。

跑法：cd rich4-spec && .venv/bin/python tests/test_bank_square.py
"""
import os
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

BANK = 0x4379C9
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_CASH, P_BANK, P_RATE, P_WHO, P_REJECT = 0x1C, 0x20, 0x19, 0x15, 0x3B
CUR, DATE = 0x49910C, 0x497160

SPRINTF, SHOW = 0x457110, 0x440CAC
REDRAW, ANIM = 0x41D433, 0x436B0A
UI = (0x450441, 0x4018E7, 0x45285E, 0x41D476, 0x456E11)

M_SHOW, M_REDRAW, M_ANIM = (SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x804,
                            SCRATCH_BASE + 0x808)
M_FMT, M_ARG = SCRATCH_BASE + 0x80C, SCRATCH_BASE + 0x810
RESULTS = []


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def trunc0(x):
    return int(Fraction(x)) if x == x else 0     # 向零截断（NaN 另有处理）


def target_of(rate, day):
    """照原版一步步算目标現金比例：f32(rate/100) → （日≤7 ×1.5 / 日≥26 ×0.5）→ 两端夹取"""
    t = f32(f32(rate) / 100.0)
    if day <= 7:
        t = f32(t * 1.5)
    if day >= 26:
        t = f32(t * 0.5)
    if t >= 1.0:
        t = f32(0.9)
    elif t <= 0.0:
        t = f32(0.1)
    return t


def expect_cash(total, rate, day):
    return trunc0(Fraction(total) * Fraction(target_of(rate, day)))


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<22} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(SHOW, b"\xC7\x05" + struct.pack("<I", M_SHOW)
                       + struct.pack("<I", 1) + b"\xC3")
        for va, slot in ((REDRAW, M_REDRAW), (ANIM, M_ANIM)):
            self.emu.patch(va, b"\xC7\x05" + struct.pack("<I", slot)
                           + struct.pack("<I", 1) + b"\xC3")
        for va in UI:
            self.emu.patch(va, b"\x31\xC0\xC3")
        # sprintf(dst, fmt, days) —— 记下**后两个**实参（cdecl：最后一个 push 是第一参，
        # 所以 [esp+4] = dst、[esp+8] = fmt、[esp+0xC] = 天数）
        code = b""
        for off, slot in ((8, M_FMT), (0xC, M_ARG)):
            code += b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)
        self.emu.patch(SPRINTF, code + b"\xC3")

    def run(self, *, cash=0, bank=0, rate=60, who=2, reject=0, day=15):
        def setup(emu):
            emu.write32(CUR, 0)
            emu.write32(DATE, day & 0xFFFF)          # 低字节 = 日
            emu.write32(M_SHOW, 0)
            emu.write32(M_REDRAW, 0)
            emu.write32(M_ANIM, 0)
            emu.write32(M_FMT, 0)
            emu.write32(M_ARG, 0)
            pb = PLAYER_BASE
            emu.write32(pb + P_CASH, cash)
            emu.write32(pb + P_BANK, bank)
            emu.write8(pb + P_RATE, rate)
            emu.write8(pb + P_WHO, who)
            emu.write8(pb + P_REJECT, reject)

        self.emu.call(BANK, [], setup=setup)
        e = self.emu
        return {
            "cash": e.read32(PLAYER_BASE + P_CASH),
            "bank": e.read32(PLAYER_BASE + P_BANK),
            "show": e.readu32(M_SHOW),
            "redraw": e.readu32(M_REDRAW),
            "anim": e.readu32(M_ANIM),
            "fmt": e.readu32(M_FMT),
            "arg": e.readu32(M_ARG),
        }


def main():
    print("差分测试 #35：銀行格 —— 0x4379c9\n")
    f = F()
    e = f.emu

    print("[A] 拒絕往來（`+0x3b != 0`）⇒ 只印一行字、錢一分不动")
    s = f.run(cash=5000, bank=5000, reject=3)
    case("現金/存款原样", (s["cash"], s["bank"]), (5000, 5000))
    case("   ★ 显示了一次文本框", s["show"], 1)
    case("   不重绘、不播存取款动画", (s["redraw"], s["anim"]), (0, 0))
    case("   ★ 天数显示 = (值 & 0x7f) + 1", s["arg"], (3 & 0x7F) + 1)
    s = f.run(cash=5000, bank=5000, reject=0x83)
    case("   带 0x80 位时也只算低 7 位（0x83 → 4）", s["arg"], 4)
    case("   格式串 = 0x464bed", s["fmt"], 0x464BED)
    print("       （0x464bed = " + repr(e.read(0x464BED, 22).decode("big5", "replace")
                                       .split("\x00")[0]) + "）")

    print("\n[B] 真人（who_plays == 1）⇒ 开模态屏，本函数**不**重分")
    s = f.run(cash=10000, bank=0, rate=60, who=1)
    case("現金/存款原样", (s["cash"], s["bank"]), (10000, 0))
    case("   不播存取款动画", s["anim"], 0)

    print("\n[C] 电脑：按 `+0x19` 把現金/存款重分一次")
    s = f.run(cash=10000, bank=0, rate=60, day=15)
    case("★ 比例 60%、总资产 10000 ⇒ 現金 6000 / 存款 4000",
         (s["cash"], s["bank"]), (6000, 4000))
    case("   ★ 重绘 + 存取款动画各一次", (s["redraw"], s["anim"]), (1, 1))
    s = f.run(cash=0, bank=10000, rate=60, day=15)
    case("★ 反向：現金 0、存款 10000 ⇒ 現金 6000 / 存款 4000",
         (s["cash"], s["bank"]), (6000, 4000))

    print("\n[D] 日期两条系数：日 ≤ 7 ×1.5、日 ≥ 26 ×0.5")
    # ⚠️ 起始局面要**离开 ±0.25 带**才会重分：用「現金 0 / 存款 10000」（ratio = 0）
    for day, tag in ((3, "月初（日=3）"), (7, "日=7 也"), (8, "日=8 不带"),
                     (26, "月末（日=26）"), (25, "日=25 不带")):
        s = f.run(cash=0, bank=10000, rate=60, day=day)
        want = expect_cash(10000, 60, day)
        case(f"★ {tag} ⇒ 目标 {target_of(60, day):.9f} ⇒ 現金 {want}", s["cash"], want)

    print("\n[E] 目标比例的两端夹取（≥1 → 0.9、≤0 → 0.1）")
    s = f.run(cash=0, bank=10000, rate=100, day=15)
    case("★ rate=100 ⇒ 目标 1.0 → 夹成 **f32(0.9)** ⇒ 現金 8999（不是 9000！）",
         s["cash"], expect_cash(10000, 100, 15))
    s = f.run(cash=0, bank=10000, rate=0, day=15)
    case("★ rate=0 ⇒ 目标 0 → 夹成 f32(0.1) ⇒ 現金 1000", s["cash"], expect_cash(10000, 0, 15))
    s = f.run(cash=0, bank=10000, rate=5, day=15)
    case("   rate=5 ⇒ 0.05（**不**夹到 0.1）⇒ 現金 500", s["cash"], expect_cash(10000, 5, 15))

    print("\n[F] 「±0.25 带内不折腾」——但現金恰好为 0 时例外")
    s = f.run(cash=6000, bank=4000, rate=60, day=15)
    case("★ 正好在目标上（ratio = 0.6）⇒ 一分不动", (s["cash"], s["bank"]), (6000, 4000))
    case("   也不播存取款动画", s["anim"], 0)
    s = f.run(cash=5700, bank=4300, rate=60, day=15)
    case("   带内（ratio = 0.57）⇒ 不动", (s["cash"], s["bank"]), (5700, 4300))
    s = f.run(cash=3400, bank=6600, rate=60, day=15)
    case("★ 差 0.26 > 0.25 ⇒ 重分到 6000", s["cash"], 6000)
    s = f.run(cash=0, bank=10000, rate=0, day=15)
    case("★ 現金 0、目标 0.1、差 0.1（带内）⇒ 仍然重分（現金 1000）", s["cash"], 1000)

    print("\n[G] 截断方向：新現金 = trunc(总资产 × 目标)")
    for total, rate in ((10000, 63), (9999, 63), (12345, 37), (777, 99), (1, 50)):
        s = f.run(cash=0, bank=total, rate=rate, day=15)
        want = expect_cash(total, rate, day=15)
        case(f"★ 总资产 {total} × f32({rate}/100) = "
             f"{float(Fraction(total) * Fraction(target_of(rate, 15))):.4f} ⇒ 截断 {want}",
             s["cash"], want)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
