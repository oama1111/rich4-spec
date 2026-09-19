#!/usr/bin/env python3
"""
通道 2 差分测试 #30 · **回合开始判定** `0x0040c912`（约 780 字节）

它是「轮到某人了 ⇒ 他这回合能不能动」的唯一判据（`rules/turn-start.ts` 的实现就是照它写的，
但此前只有**手抄汇编清单**做依据，没被机器码驱动过）。返回码经 `0x418c55` 的 6 路跳表
（`0x418c3d`）分派：1 → 真人、2/5 → AI、3/4 → 跳过、0 → 什么都不做。

## 反汇编骨架（A 级）

```asm
0040c912(arg0 = quiet) -> ebx
  ebx = 0 ; edx = [0x49910c]                      ; 当前 actor
  if (edx >= 4) goto 0x40cbdd                     ; ── 替身 / NPC 分支 ──
  eax = edx*0x68 ; ch = [player + 0x15]
  if (ch == 0) goto done                          ; ★ 不在场（who_plays == 0）⇒ 0
  if (arg0 != 0) goto 0x40cbc2                    ; ── quiet 路径（只判定、不说话）──
  ; ── 正式路径 ──
  if (dword [player+0x32] != 0 || byte [player+0x36] != 0) {          ; 被阻碍（四项一起读）
      if ([player+0x15] & 0x30) { call 0x40dd1f ; goto done }         ; ★ auto_move（0x40dd1f）
      …else 显示状态文字：0x44808a / 0x452946 / 0x457110 / 0x44ef41 / 0x440cac…
      goto done                                                       ; 两种都是 0
  }
  if (byte [player+0x37] != 0) { call 0x40dd1f ; ebx = -1 ; goto done }   ; ★ 夢遊
  bl = ch ; goto done                             ; ★ 正常 ⇒ 返回 who_plays
; ── 0x40cbc2 quiet ──
  if (ch & 0x30) goto done                        ; ⇒ 0
  if (dword [player+0x32] != 0) goto done         ; ⇒ 0
  if (byte [player+0x36] != 0) goto done          ; ⇒ 0
  bl = ch ; goto done                             ; ★ 注意：quiet 路径**不看 +0x37（夢遊）**
; ── 0x40cbdd 替身（actor 4..7）──
  eax = (edx-4)*0x10
  if ([slot+0x0a] != 0) goto done                 ; ★ 不在棋盘（place != 0）⇒ 0
  if (arg0 != 0) goto done                        ; ⇒ 0
  if ([slot+0x0c] != 0) goto done                 ; ★★ 冬眠（hibernating）⇒ 0
  if ([slot+0x0e] != 0) goto done                 ; ★ 停留（halted）⇒ 0
  ebx = 2 ; goto done                             ; ★ 替身可行动 ⇒ 返回 **2**（= AI）
done: eax = ebx ; ret
```

状态文字那一段的**随机消耗**（表现层，进全局流）：坐牢(`+0x34`)/住院(`+0x35`)/冬眠(`+0x36`)
各自 `call 0x456f2d` 一次、`test al,1` 决定要不要摆头像（`0x44ef41(player, kind, 台词)`：
坐牢/住院 kind = 2、冬眠 kind = 1，台词来自角色表 `0x480896/0x48089a/0x48089e`）；
住宿(`+0x32`)/消失(`+0x33`) 两支**不掷**。冬眠那一支还要求 `dword[+0x32] == 0`。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x40dd1f` | 自动走子（被阻碍/夢遊时） | 记一笔 + `ret` |
| `0x44808a` | 状态文字前置 | `ret` |
| `0x452946` | 取名字 | `ret` |
| `0x457110` | 拼字符串 | `ret` |
| `0x44ef41` | 摆头像/台词 | **记下三个实参** + `ret` |
| `0x440cac` | 收起文字框 | 记一笔 + `ret` |
| `0x456f2d` | PRNG | 数据桩：记调用次数 + 返回可控值 |

跑法：cd rich4-spec && .venv/bin/python tests/test_turn_start.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

TURN_START = 0x40C912

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_C32, P_SLEEP, P_SLEEPWALK = 0x15, 0x32, 0x36, 0x37
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10
A_PLACE, A_HIBER, A_SLEEPWALK, A_HALTED, A_SINGLE = 0x0A, 0x0C, 0x0D, 0x0E, 0x0F
CUR = 0x49910C

AUTO_MOVE = 0x40DD1F
TEXT_PRE = 0x44808A
GET_NAME = 0x452946
SPRINTF = 0x457110
PORTRAIT = 0x44EF41
TEXT_DONE = 0x440CAC
PRNG = 0x456F2D

M_AUTO, M_TEXT, M_PORTRAIT = (SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x804,
                              SCRATCH_BASE + 0x808)
M_ARG1, M_ARG2, M_ARG3 = (SCRATCH_BASE + 0x80C, SCRATCH_BASE + 0x810,
                          SCRATCH_BASE + 0x814)
RAND_VAL, RAND_N = SCRATCH_BASE + 0x818, SCRATCH_BASE + 0x81C
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        for va in (TEXT_PRE, GET_NAME, TEXT_DONE):
            self.emu.patch(va, b"\xC3")
        # 拼字符串：把**目标缓冲的头一个字节**写成 1 —— 原版随后用
        # `cmp byte [esp], 0` 判「这段文字非空才收起文字框」（0x40cb84）。
        # ⚠️ 必须经寄存器写「指针指向的那一格」：`mov byte [esp+4],1` 只改到**参数槽**。
        self.emu.patch(SPRINTF, b"\x8B\x44\x24\x04\xC6\x00\x01\xC3")
        # 记一笔：mov dword [slot], 1 / ret
        for va, slot in ((AUTO_MOVE, M_AUTO), (TEXT_DONE, M_TEXT)):
            self.emu.patch(va, b"\xC7\x05" + struct.pack("<I", slot)
                           + struct.pack("<I", 1) + b"\xC3")
        # 摆头像：把三个实参抄进 scratch 再返回
        code = b""
        for off, slot in ((4, M_ARG1), (8, M_ARG2), (0xC, M_ARG3)):
            code += b"\x8B\x44\x24" + bytes([off])          # mov eax, [esp+off]
            code += b"\xA3" + struct.pack("<I", slot)        # mov [slot], eax
        self.emu.patch(PORTRAIT, code + b"\xC3")
        # PRNG：eax = [RAND_VAL] ; inc dword [RAND_N] ; ret
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_VAL)
                       + b"\xFF\x05" + struct.pack("<I", RAND_N) + b"\xC3")

    def run(self, idx=0, *, who=1, c32=0, c33=0, c34=0, c35=0, c36=0, c37=0,
            actor=None, quiet=0, rand=0):
        def setup(emu):
            emu.write32(CUR, idx)
            emu.write32(RAND_VAL, rand & 0xFFFFFFFF)
            emu.write32(RAND_N, 0)
            emu.write32(M_AUTO, 0)
            emu.write32(M_TEXT, 0)
            for s in (M_ARG1, M_ARG2, M_ARG3):
                emu.write32(s, 0)
            pb = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write8(pb + P_WHO, who)
            emu.write8(pb + P_C32, c32)
            emu.write8(pb + P_C32 + 1, c33)
            emu.write8(pb + P_C32 + 2, c34)
            emu.write8(pb + P_C32 + 3, c35)
            emu.write8(pb + P_SLEEP, c36)
            emu.write8(pb + P_SLEEPWALK, c37)
            if actor is not None:
                place, hibe, sleep, halt, single = actor
                ab = ACTOR_BASE + (idx - 4) * ACTOR_STRIDE
                emu.write8(ab + A_PLACE, place)
                emu.write8(ab + A_HIBER, hibe)
                emu.write8(ab + A_SLEEPWALK, sleep)
                emu.write8(ab + A_HALTED, halt)
                emu.write8(ab + A_SINGLE, single)

        r = self.emu.call(TURN_START, [quiet], setup=setup)
        e = self.emu
        return {
            "ret": r["signed"], "auto": e.readu32(M_AUTO), "text": e.readu32(M_TEXT),
            "args": (e.readu32(M_ARG1), e.readu32(M_ARG2), e.readu32(M_ARG3)),
            "rands": e.readu32(RAND_N),
        }


def main():
    print("差分测试 #30：回合开始判定 —— 0x40c912\n")
    f = F()

    print("[A] 玩家分支的返回码（0 / who_plays / -1）")
    case("who_plays == 0（不在场）⇒ 0", f.run(who=0)["ret"], 0)
    case("真人(1) ⇒ 1", f.run(who=1)["ret"], 1)
    case("电脑(2) ⇒ 2", f.run(who=2)["ret"], 2)
    case("托管人类(5) ⇒ 5", f.run(who=5)["ret"], 5)
    case("★ 只是带 0x10 但没有阻碍计数 ⇒ 照常返回 who（0x30 那支在阻碍块**里面**）",
         f.run(who=0x11)["ret"], 0x11)
    case("   带 0x20 同理", f.run(who=0x21)["ret"], 0x21)

    print("\n[B] 阻碍判定：`dword[+0x32] != 0`（四项一起读）或 `byte[+0x36] != 0`")
    for name, kw, want in [
        ("住宿 +0x32", dict(c32=3), 0), ("消失 +0x33", dict(c33=5), 0),
        ("坐牢 +0x34", dict(c34=2), 0), ("住院 +0x35", dict(c35=1), 0),
        ("★ 只置高位字节（+0x34）也命中 —— 判据是 **dword 读**", dict(c34=0x80), 0),
        ("冬眠 +0x36", dict(c36=4), 0),
        ("带 0x10 + 阻碍 ⇒ 0", dict(who=0x11, c34=1), 0),
        ("带 0x20 + 阻碍 ⇒ 0", dict(who=0x21, c32=1), 0),
    ]:
        case(name, f.run(**kw)["ret"], want)

    print("\n[C] 夢遊（+0x37）：不被阻碍时自动走子并返回 -1")
    s = f.run(c37=3)
    case("返回值 -1", s["ret"], -1)
    case("   ★ 调了一次 0x40dd1f（auto_move）", s["auto"], 1)
    case("   不显示状态文字", (s["text"], s["args"][0]), (0, 0))
    s = f.run(c37=3, c34=1)
    case("★ 夢遊 + 坐牢 ⇒ 阻碍优先：返回 0（不返回 -1）", s["ret"], 0)
    s = f.run(c37=3, c34=1)          # 无 0x30
    case("   无 0x30 时**不**自动走子（走的是状态文字那一支）", s["auto"], 0)
    case("   文字收尾 0x440cac 被调用", s["text"], 1)
    s = f.run(who=0x11, c34=1, c37=3)
    case("★ 夢遊 + 阻碍 + 0x10 ⇒ 走 auto_move 那一支、返回 0", (s["auto"], s["ret"]), (1, 0))
    case("   该支不显示状态文字", (s["text"], s["rands"]), (0, 0))

    print("\n[D] quiet 路径（arg0 != 0）：顺序是 0x30 → +0x32 → +0x36，**不看 +0x37**")
    case("无阻碍 ⇒ who", f.run(who=2, quiet=1)["ret"], 2)
    case("0x30 ⇒ 0", f.run(who=0x11, quiet=1)["ret"], 0)
    case("+0x32 非 0 ⇒ 0", f.run(c32=1, quiet=1)["ret"], 0)
    case("+0x36 非 0 ⇒ 0", f.run(c36=1, quiet=1)["ret"], 0)
    case("★★ 只有 +0x37（夢遊）⇒ **照常返回 who**（quiet 路径不查它）",
         f.run(who=1, c37=9, quiet=1)["ret"], 1)
    case("★ 夢遊 + 坐牢 + quiet ⇒ 0（阻碍照样查）", f.run(c34=1, c37=9, quiet=1)["ret"], 0)
    s = f.run(who=0x21, c32=1, quiet=1)
    case("★ quiet + 0x30 + 阻碍 ⇒ 0，且**不**自动走子、不显示文字",
         (s["ret"], s["auto"], s["text"]), (0, 0, 0))

    print("\n[E] 状态文字那一支：三种状态各自掷一次 rand、摆头像的 kind 不同")
    s = f.run(c34=2, rand=0)
    case("坐牢 + rand 偶 ⇒ 返回 0", s["ret"], 0)
    case("   掷了 1 次", s["rands"], 1)
    case("   rand 偶 ⇒ **不**摆头像", s["args"][0], 0)
    case("   文字收尾照样调", s["text"], 1)
    s = f.run(c34=2, rand=1)
    case("★ 坐牢 + rand 奇 ⇒ 摆头像：实参 = (玩家号 0, kind 2, 台词指针 != 0)",
         (s["args"][0], s["args"][1], s["args"][2] != 0), (0, 2, True))
    s = f.run(c35=1, rand=1)
    case("住院 + rand 奇 ⇒ 同样是 (0, 2, 台词)", (s["args"][0], s["args"][1]), (0, 2))
    s = f.run(c36=1, rand=1)
    case("★ 冬眠 + rand 奇 ⇒ kind = **1**（与坐牢/住院不同）", (s["args"][0], s["args"][1]), (0, 1))
    s = f.run(c32=3, rand=1)
    case("住宿那一支**不掷** rand", s["rands"], 0)
    s = f.run(c33=6, rand=1)
    case("消失那一支**也不掷**", s["rands"], 0)
    s = f.run(c34=1, c35=1, rand=0)
    case("★ 坐牢 + 住院都命中 ⇒ 2 次（这就是**上限**）", s["rands"], 2)
    s = f.run(c34=1, c36=1, rand=0)
    case("★★ 坐牢 + 冬眠 ⇒ 只掷 1 次：冬眠那支要求 `dword[+0x32..+0x35] == 0`",
         s["rands"], 1)
    s = f.run(c32=1, c33=6, c34=1, c35=1, c36=1, rand=0)
    case("   住宿/消失/坐牢/住院全非 0 ⇒ 还是 2 次（住宿、消失不掷）", s["rands"], 2)
    s = f.run(c32=3, c36=1, rand=1)
    case("★ 住宿非 0 时**跳过**冬眠那一整块（`0x40cb12 jne`）",
         (s["rands"], s["args"][1]), (0, 0))

    print("\n[F] 替身 / NPC 分支（actor 4..7）：可行动 ⇒ **2**")
    ok = (0, 0, 0, 0, 0)
    case("place=0、无计数 ⇒ 2", f.run(idx=4, actor=ok)["ret"], 2)
    case("   7 号替身同理", f.run(idx=7, actor=ok)["ret"], 2)
    case("★ place != 0（在監獄/醫院）⇒ 0", f.run(idx=4, actor=(1, 0, 0, 0, 0))["ret"], 0)
    case("★★ 冬眠（slot+0x0c）非 0 ⇒ 0", f.run(idx=4, actor=(0, 1, 0, 0, 0))["ret"], 0)
    case("★ 停留（slot+0x0e）非 0 ⇒ 0", f.run(idx=4, actor=(0, 0, 0, 1, 0))["ret"], 0)
    case("夢遊（slot+0x0d）非 0 **不**拦（原版不查它）",
         f.run(idx=4, actor=(0, 0, 5, 0, 0))["ret"], 2)
    case("龜行（slot+0x0f）非 0 也不拦", f.run(idx=4, actor=(0, 0, 0, 0, 1))["ret"], 2)
    case("quiet ⇒ 0", f.run(idx=4, actor=ok, quiet=1)["ret"], 0)
    case("玩家与替身互不干扰：idx=4 时玩家表的阻碍位无关",
         f.run(idx=4, actor=ok, c34=3)["ret"], 2)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
