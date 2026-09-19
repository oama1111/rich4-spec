#!/usr/bin/env python3
"""
通道 2 差分测试 #36 · **三个「得點券」格** `0x41b184`（50）/ `0x41b21e`（30）/ `0x41b2a3`（10）

它们是**大落点分派器 `0x41abde` 的片段**（跳表成员，不各自成函数），所以本测试用了一个
新手法：**把共用尾声 `0x41b3d0` 打成 `ret`**，就能单独驱动这些入口标签 ——
它们末尾都是 `jmp 0x41b3d0`（`xor eax,eax; mov al,[esp+0xf4]; add esp,0xf8; pop×4; ret`），
替成 `ret` 后直接回到 `emu.call` 的返回地址（栈不平衡无所谓，每次 `call` 都会重置 ESP）。

## 反汇编骨架（A 级）

```asm
; ── 50 點 0x41b184 ──
0041b194  eax = MKF(0x48a0e4, 0x219, 0, 0)      ; 开资源
0041b1ad  0x45144f(...)                          ; 贴到固定小矩形
0041b1b6  0x456e11(eax)                          ; 关资源
0041b1c8  show(0x463a81「得點券５０點」, 0x3e8)   ; ★ 1000 毫秒
0041b1d7  add word [player + 0x496b98], 0x32     ; ★ 16 位加
0041b1e1  ebx = 角色×12×9 = 角色×0x6c            ; 角色台词表步长 0x6c = 27 事件×4
0041b1f8  call rand ; and eax,1                  ; ★ 只有这一档掷
0041b200  ecx = [0x48084a + 角色×0x6c + idx×4]   ; ★ 事件 0 / 1
0041b211  player_say(当前玩家, 0, 台词)
; ── 30 點 0x41b21e ──
0041b271  add word [player + 0x496b98], 0x1e
0041b28d  esi = [0x480852 + 角色×0x6c]           ; ★ 0x480852−0x48084a = 8 ⇒ **事件 2，固定**
0041b29e  player_say(当前玩家, 0, 台词)           ;   ★ 但**不掷随机数**
; ── 10 點 0x41b2a3 ──
0041b2f5  add word [player + 0x496b98], 0xa
0041b2fd  jmp 0x41b3d0                            ; ★ **什么都不说**
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41b3d0` | 共用尾声 | **`ret`**（见上）|
| `0x450441` | 开资源 | `xor eax,eax / ret` |
| `0x45144f` | 贴图 | `ret` |
| `0x456e11` | 关资源 | `ret` |
| `0x440cac` | 显示文字 | 记实参 + `ret` |
| `0x44ef41` | `player_say` | **记三个实参** + `ret` |
| `0x456f2d` | PRNG | 数据桩：记次数 + 返回可控值 |

跑法：cd rich4-spec && .venv/bin/python tests/test_points_squares.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

EPILOGUE = 0x41B3D0
SQUARES = {0x41B184: (0x32, "50"), 0x41B21E: (0x1E, "30"), 0x41B2A3: (0x0A, "10")}

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_POINTS, P_CHAR = 0x30, 0x13
CUR = 0x49910C

LOAD, BLIT, FREE = 0x450441, 0x45144F, 0x456E11
SHOW, SAY, PRNG = 0x440CAC, 0x44EF41, 0x456F2D

M_SHOW, M_SHOW_ARG = SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x804
M_SAY1, M_SAY2, M_SAY3 = (SCRATCH_BASE + 0x808, SCRATCH_BASE + 0x80C,
                          SCRATCH_BASE + 0x810)
RAND_VAL, RAND_N = SCRATCH_BASE + 0x814, SCRATCH_BASE + 0x818
PHRASE_TABLE = SCRATCH_BASE + 0x2000
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<20} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(EPILOGUE, b"\xC3")            # ★ 共用尾声 → ret
        self.emu.patch(LOAD, b"\x31\xC0\xC3")        # xor eax,eax / ret
        self.emu.patch(BLIT, b"\xC3")
        self.emu.patch(FREE, b"\xC3")
        # show(buf, ms) —— 记第二个实参（ms）
        code = b""
        for off, slot in ((4, M_SHOW), (8, M_SHOW_ARG)):
            code += b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)
        self.emu.patch(SHOW, code + b"\xC3")
        # player_say(player, slot, text) —— 记三个实参
        code = b""
        for off, slot in ((4, M_SAY1), (8, M_SAY2), (0xC, M_SAY3)):
            code += b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)
        self.emu.patch(SAY, code + b"\xC3")
        # PRNG：eax = [RAND_VAL] ; inc dword [RAND_N] ; ret
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_VAL)
                       + b"\xFF\x05" + struct.pack("<I", RAND_N) + b"\xC3")

    def run(self, va, *, points=0, char=0, rand=0):
        def setup(emu):
            emu.write32(CUR, 0)
            emu.write32(RAND_VAL, rand & 0xFFFFFFFF)
            emu.write32(RAND_N, 0)
            for s in (M_SHOW, M_SHOW_ARG, M_SAY1, M_SAY2, M_SAY3):
                emu.write32(s, 0)
            # 角色台词表：每个角色 0x6c 字节，前 3 个事件各一个"台词指针"
            for c in range(12):
                for ev in range(3):
                    emu.write32(0x48084A + c * 0x6C + ev * 4, PHRASE_TABLE + c * 16 + ev)
            pb = PLAYER_BASE
            emu.write16(pb + P_POINTS, points & 0xFFFF)
            emu.write8(pb + P_CHAR, char)

        self.emu.call(va, [], setup=setup)
        e = self.emu
        return {
            "points": e.read16(PLAYER_BASE + P_POINTS),
            "show": e.readu32(M_SHOW),
            "ms": e.readu32(M_SHOW_ARG),
            "say": (e.readu32(M_SAY1), e.readu32(M_SAY2), e.readu32(M_SAY3)),
            "say_called": e.readu32(M_SAY1) != 0 or e.readu32(M_SAY3) != 0,
            "rands": e.readu32(RAND_N),
        }


def main():
    print("差分测试 #36：三个「得點券」格 —— 0x41b184 / 0x41b21e / 0x41b2a3\n")
    f = F()

    print("[A] 点数：16 位加（`add word [+0x30], imm`）")
    for va, (delta, name) in sorted(SQUARES.items()):
        s = f.run(va, points=100)
        case(f"得{name}點：100 + {delta} = {100 + delta}", s["points"], 100 + delta)
    for va, (delta, name) in sorted(SQUARES.items()):
        s = f.run(va, points=0xFFF0)
        case(f"★ 得{name}點：65520 + {delta} ⇒ **回绕** {(0xFFF0 + delta) & 0xFFFF}",
             s["points"], (0xFFF0 + delta) & 0xFFFF)

    print("\n[B] 文字框与时长（0x440cac(buf, 0x3e8)）")
    for va, (delta, name) in sorted(SQUARES.items()):
        s = f.run(va)
        case(f"得{name}點：显示一次、时长 1000ms", (s["show"] != 0, s["ms"]), (True, 0x3E8))

    print("\n[C] ★ 随机数：**只有 50 點那一档掷一次**，且用 `& 1` 选事件 0/1")
    s = f.run(0x41B184, rand=0)
    case("50 點：掷了 1 次", s["rands"], 1)
    case("   rand 偶 ⇒ 事件 0 的台词", s["say"][2], PHRASE_TABLE + 0 * 16 + 0)
    s = f.run(0x41B184, rand=1)
    case("   rand 奇 ⇒ 事件 1 的台词", s["say"][2], PHRASE_TABLE + 0 * 16 + 1)
    s = f.run(0x41B184, rand=7, char=5)
    case("   角色 5：台词表按角色×0x6c 取", s["say"][2], PHRASE_TABLE + 5 * 16 + 1)
    for va, (delta, name) in ((0x41B21E, (0x1E, "30")), (0x41B2A3, (0x0A, "10"))):
        s = f.run(va, rand=1)
        case(f"★ 得{name}點：**一次都不掷**", s["rands"], 0)

    print("\n[D] 台词：`player_say(玩家, slot, 台词)`")
    s = f.run(0x41B184, char=3, rand=1)
    case("50 點 ⇒ player_say(0, 0, 事件1)", s["say"], (0, 0, PHRASE_TABLE + 3 * 16 + 1))
    s = f.run(0x41B21E, char=3, rand=1)
    case("★ 30 點 ⇒ player_say(0, 0, **事件 2**)（0x480852 − 0x48084a = 8 ⇒ 固定事件 2）",
         s["say"], (0, 0, PHRASE_TABLE + 3 * 16 + 2))
    s = f.run(0x41B2A3)
    case("★★ 10 點 ⇒ **一句都不说**（直接跳尾声）", s["say_called"], False)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
