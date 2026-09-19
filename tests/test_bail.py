#!/usr/bin/env python3
"""
通道 2 差分测试 #31 · **保釋（探監 / 探病）** `0x0043d304`（監獄）/ `0x0043e9a4`（醫院）

落在監獄/醫院格上做的事：**花點券把里面的人放出来**。两段逐条同构，
只差占用表（`0x496b30` / `0x496b60`）、计数字段（`+0x34` / `+0x35`）、
赎金表（`0x475c44` / `0x475ca4`）与替身出狱函数（`0x43d7bf` / `0x43ee6e`）。
真人那一支（`who_plays == 1`）是模态屏，本测试**只驱动电脑分支**。

## 反汇编骨架（A 级，两段共用）

```asm
0043d30e  for (slot = 0; slot < 8; slot++) if (占用表[slot] != 0) break
0043d321  if (slot == 8) return                     ; ★ 里面没人 ⇒ 连 rand 都不掷
0043d32a  if (current.who_plays(+0x15) == 1) { …模态屏… ; return }
; ── 电脑分支 ──
0043d3d8  call rand ; test al,1 ; je 返回            ; ★① 一半概率根本不管
0043d3ee  dl = current[+0x17]                       ; 個性
0043d409  dl == 0 ⇒ 候选 = 占用表槽 0..3 里非空的
0043d432  dl == 1 ⇒ 候选 = 槽 0..3；再 call rand ; idiv 3 ; 余数 == 0 才并上槽 4..7
0043d484  dl == 2 ⇒ 候选 = 槽 4..7
          其它值 ⇒ 空候选（什么都不加）
0043d4a4  if (候选空) return
0043d4ac  call rand ; idiv esi ; 目标 = 候选[余数]
0043d4c1  cost = dword [目标*4 + 0x475c44]          ; ★ 赎金表（監獄/醫院两张数值相同）
0043d4cd  目标 < 4：if (點券(+0x30) <= cost) return  ;   ★ **严格大于**
0043d4f4  目标 >= 4：if (點券 < 0x2bc=700) return   ;   ★ 门槛 700、实收 300
0043d503  名字：目标 < 4 ⇒ player[目标][+0x00]；否则 dword [目标*4 + 0x47ed5a]（小偷/強盜/流氓/間諜）
0043d534  sprintf(buf, "保釋%s"(0x465169), 名字) ; 0x440cac(buf, 0x5dc=1500ms)
0043d55f  ★ 監獄：`66 sub word [current+0x30], si`      —— **16 位**减
0043ec0c  ★ 醫院：`   sub dword [current+0x30], esi`    —— **32 位**减（★★ 新发现，见 §F）
0043d566  目标 < 4 ⇒ byte [目标 + 0x34] = 0x80、占用表[目标] = 0
0043d57f  目标 >= 4 ⇒ call 0x43d7bf(目标)            ; 醫院是 0x43ee6e
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x456f2d` | PRNG | **序列桩**：按顺序吐出预设的 `rand()` 值（并记次数）|
| `0x452946` | 取名字 | 记两个实参 + `ret` |
| `0x457110` | 拼字符串 | 记实参 + `ret` |
| `0x440cac` | 显示文字框 | 记一次 + `ret` |
| `0x43d7bf` / `0x43ee6e` | 替身出狱 | 记实参 + `ret` |

跑法：cd rich4-spec && .venv/bin/python tests/test_bail.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

PRISON = 0x43D304
HOSPITAL = 0x43E9A4
OCC_PRISON = 0x496B30
OCC_HOSPITAL = 0x496B60

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_PERSONALITY, P_POINTS = 0x15, 0x17, 0x30
P_INPRISON, P_INHOSPITAL = 0x34, 0x35
CUR = 0x49910C

COST_PRISON = 0x475C44
COST_HOSPITAL = 0x475CA4
NAME_TABLE = 0x47ED5A
FMT_BAIL = 0x465169

PRNG = 0x456F2D
GET_NAME = 0x452946
SPRINTF = 0x457110
SHOW = 0x440CAC
RELEASE_PRISON = 0x43D7BF
RELEASE_HOSPITAL = 0x43EE6E

RAND_PTR, RAND_N = SCRATCH_BASE + 0x800, SCRATCH_BASE + 0x804
ROLLS = SCRATCH_BASE + 0x900
M_NAME, M_FMT, M_SHOW, M_REL = (SCRATCH_BASE + 0x810, SCRATCH_BASE + 0x814,
                                SCRATCH_BASE + 0x818, SCRATCH_BASE + 0x81C)
M_N1, M_N2, M_F1 = SCRATCH_BASE + 0x820, SCRATCH_BASE + 0x824, SCRATCH_BASE + 0x828
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # PRNG 序列桩：push ecx / mov ecx,[RAND_PTR] / mov eax,[ecx] /
        #              add dword [RAND_PTR],4 / inc dword [RAND_N] / pop ecx / ret
        code = (b"\x51"
                + b"\x8B\x0D" + struct.pack("<I", RAND_PTR)
                + b"\x8B\x01"
                + b"\x83\x05" + struct.pack("<I", RAND_PTR) + b"\x04"
                + b"\xFF\x05" + struct.pack("<I", RAND_N)
                + b"\x59\xC3")
        self.emu.patch(PRNG, code)
        # 记一笔：mov dword [slot], 1 / ret
        for va, slot in ((SHOW, M_SHOW), (RELEASE_PRISON, M_REL), (RELEASE_HOSPITAL, M_REL)):
            self.emu.patch(va, b"\xC7\x05" + struct.pack("<I", slot)
                           + struct.pack("<I", 1) + b"\xC3")
        # 记两个实参的桩
        def two_args(s1, s2):
            out = b""
            for off, slot in ((4, s1), (8, s2)):
                out += b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)
            return out + b"\xC3"
        self.emu.patch(GET_NAME, two_args(M_N1, M_N2))
        # 真人那一支是**模态屏**：把 MKF 资源装载 / 模态循环 / 收框全部打桩，
        # 只验规则侧残留（什么都不该改）。真实画面不在通道 2 的范围里。
        for va in (0x450441, 0x451A5A, 0x43C8FB, 0x4549CF, 0x4018E7, 0x454BCC, 0x456E11):
            self.emu.patch(va, b"\x31\xC0\xC3")   # xor eax,eax / ret
        self.emu.patch(SPRINTF, two_args(M_F1, M_F1 + 4))

    def run(self, va, *, who=2, personality=0, points=0, occ=None, rolls=(),
            humans=()):
        def setup(emu):
            emu.write32(CUR, 0)
            emu.write32(M_NAME, 0)
            emu.write32(M_FMT, 0)
            emu.write32(M_SHOW, 0)
            emu.write32(M_REL, 0)
            for i, v in enumerate(rolls):
                emu.write32(ROLLS + i * 4, v & 0xFFFFFFFF)
            emu.write32(RAND_PTR, ROLLS)
            emu.write32(RAND_N, 0)
            table = OCC_PRISON if va == PRISON else OCC_HOSPITAL
            for s in range(8):
                emu.write8(table + s, (occ or {}).get(s, 0))
            for idx in range(4):
                pb = PLAYER_BASE + idx * PLAYER_STRIDE
                # `+0x00` 是姓名/头像那 4 字节 —— 保釋字幕会把它当名字源传给 0x452946
                emu.write32(pb + 0x00, 0x11110000 + idx)
                emu.write8(pb + P_WHO, 0)
                emu.write8(pb + P_PERSONALITY, 0)
                emu.write16(pb + P_POINTS, 0)
            pb = PLAYER_BASE  # 0 号 = 访客
            emu.write8(pb + P_WHO, who)
            emu.write8(pb + P_PERSONALITY, personality)
            emu.write16(pb + P_POINTS, points & 0xFFFF)
            for idx in humans:
                emu.write8(PLAYER_BASE + idx * PLAYER_STRIDE + P_WHO, 1)

        self.emu.call(va, [], setup=setup)
        e = self.emu
        table = OCC_PRISON if va == PRISON else OCC_HOSPITAL
        return {
            "points": e.read16(PLAYER_BASE + P_POINTS),
            "points32": e.readu32(PLAYER_BASE + P_POINTS),
            "occ": [e.read8(table + s) for s in range(8)],
            "flag": [e.read8(PLAYER_BASE + i * PLAYER_STRIDE + P_INPRISON) for i in range(4)]
                    + [e.read8(PLAYER_BASE + i * PLAYER_STRIDE + P_INHOSPITAL) for i in range(4)],
            "rolls": e.readu32(RAND_N),
            "show": e.readu32(M_SHOW),
            "rel": e.readu32(M_REL),
            "name_args": (e.readu32(M_N1), e.readu32(M_N2)),
            "fmt_args": (e.readu32(M_F1), e.readu32(M_F1 + 4)),
        }


def main():
    print("差分测试 #31：保釋（監獄 0x43d304 / 醫院 0x43e9a4）\n")
    f = F()

    print("[A] 赎金表与名字表（真值直接从 exe 读）")
    e = f.emu
    for name, va in (("監獄 0x475c44", COST_PRISON), ("醫院 0x475ca4", COST_HOSPITAL)):
        vals = [e.readu32(va + i * 4) for i in range(8)]
        case(f"{name} 8 项", vals, [30, 30, 30, 30, 300, 300, 300, 300])
    names = [e.readu32(NAME_TABLE + s * 4) for s in range(4, 8)]
    got = []
    for p in names:
        raw = e.read(p, 12)
        got.append(raw.split(b"\x00")[0].decode("big5", "replace"))
    case("替身名字表 0x47ed5a 的槽 4..7", got, ["小偷", "強盜", "流氓", "間諜"])

    print("\n[B] 里面没人 ⇒ 直接返回（连 rand 都不掷）")
    s = f.run(PRISON, who=2, points=9999, occ={})
    case("占用表全空：不掷 rand", s["rolls"], 0)
    case("   不显示文字框", s["show"], 0)

    print("\n[C] ★ 第一道闸：`rand() & 1 == 0` ⇒ 一半概率根本不管")
    s = f.run(PRISON, who=2, points=9999, occ={0: 1}, rolls=[0])
    case("rand 偶 ⇒ 不保釋", (s["rolls"], s["occ"][0], s["points"]), (1, 1, 9999))
    s = f.run(PRISON, who=2, points=9999, occ={0: 1}, rolls=[1, 0])
    case("rand 奇 ⇒ 继续（并挑中候选）", s["occ"][0], 0)
    case("   rand 次数 = 2", s["rolls"], 2)

    print("\n[D] ★ 個性（`+0x17`）决定候选池")
    s = f.run(PRISON, who=2, personality=0, points=9999, occ={0: 1, 5: 1}, rolls=[1, 0])
    case("個性 0（只救玩家）：槽 0 被保、槽 5 不动", (s["occ"][0], s["occ"][5]), (0, 1))
    case("   只掷 2 次（不掷那次 %3）", s["rolls"], 2)
    s = f.run(PRISON, who=2, personality=2, points=9999, occ={0: 1, 5: 1}, rolls=[1, 0])
    case("個性 2（只放犯人）：选中替身槽 5（调放人函数）、槽 0 不动、扣 300",
         (s["occ"][0], s["rel"], s["points"]), (1, 1, 9699))
    s = f.run(PRISON, who=2, personality=1, points=9999, occ={5: 1}, rolls=[1, 0])
    case("個性 1 + %3 == 0 ⇒ 并上槽 4..7 ⇒ 选中替身 5", (s["rolls"], s["rel"]), (3, 1))
    s = f.run(PRISON, who=2, personality=1, points=9999, occ={5: 1}, rolls=[1, 1])
    case("個性 1 + %3 != 0 ⇒ 池子里只有槽 0..3（空）⇒ 不保", (s["rolls"], s["occ"][5]), (2, 1))
    s = f.run(PRISON, who=2, personality=1, points=9999, occ={0: 1, 5: 1}, rolls=[1, 0, 1])
    case("個性 1 + %3 == 0 ⇒ 池 = [0,5]，第 3 掷 1%2=1 ⇒ 选替身 5",
         (s["occ"][0], s["rel"], s["rolls"]), (1, 1, 3))
    s = f.run(PRISON, who=2, personality=3, points=9999, occ={0: 1}, rolls=[1])
    case("★ 個性 > 2 ⇒ 空候选 ⇒ 不保（只掷了那一次 50% 闸）",
         (s["rolls"], s["occ"][0]), (1, 1))

    print("\n[E] 钱的两条判据")
    s = f.run(PRISON, who=2, personality=0, points=30, occ={0: 1}, rolls=[1, 0])
    case("★ 玩家槽要**严格大于** 30：正好 30 ⇒ 不保", (s["occ"][0], s["points"]), (1, 30))
    s = f.run(PRISON, who=2, personality=0, points=31, occ={0: 1}, rolls=[1, 0])
    case("31 ⇒ 保，扣 30", (s["occ"][0], s["points"]), (0, 1))
    s = f.run(PRISON, who=2, personality=2, points=699, occ={4: 1}, rolls=[1, 0])
    case("★ 替身槽门槛 700：699 ⇒ 不保", (s["occ"][4], s["points"]), (1, 699))
    s = f.run(PRISON, who=2, personality=2, points=700, occ={4: 1}, rolls=[1, 0])
    case("700 ⇒ 保（走放人函数），但只扣 300（门槛 ≠ 收费）", (s["rel"], s["points"]), (1, 400))

    print("\n[F] ★★ 扣款宽度：两段都是 **16 位**（第 94 条订正了第 93 条的误报）")
    s = f.run(PRISON, who=2, personality=0, points=100, occ={0: 1}, rolls=[1, 0])
    case("監獄：100 − 30 = 70", s["points"], 70)
    s = f.run(HOSPITAL, who=2, personality=0, points=100, occ={0: 1}, rolls=[1, 0])
    case("醫院：同样 70（高位为 0 时两种宽度等价）", s["points"], 70)
    # ★★ 指令字节直证：两条**都是** `66 29 b2 …` = `sub word [..+0x30], si`
    #   ⚠️ 第 93 条曾从 `0x43ec0c` 起解、少了 `0x66` 前缀，误报成 `sub dword` 并
    #   登记了不存在的原版瑕疵 Q-BAIL-1。真相：`0x43ec04` 的
    #   `imul edx, [0x49910c], 0x68` 正好 7 字节（末字节 `68` 落在 `0x43ec0a`），
    #   所以 `66` 在 **0x43ec0b** —— 指令起点是 0x43ec0b，不是 0x43ec0c。
    #   机械普查（全 exe 38 处访问全是 16 位）见 `tests/test_points_field.py`。
    case("★ 監獄那条：0x43d55f 起是 `66 29 b2 …`（sub **word**）",
         e.read(0x43D55F, 3).hex(), "6629b2")
    case("★★ 醫院那条：0x43ec0b 起也是 `66 29 b2 …`（**同一形状**）",
         e.read(0x43EC0B, 3).hex(), "6629b2")
    case("   两条的位移都指向同一个 +0x30",
         (e.read(0x43D562, 4).hex(), e.read(0x43EC0E, 4).hex()), ("986b4900", "986b4900"))

    print("\n[G] 保釋成功后的副作用（監獄）")
    s = f.run(PRISON, who=2, personality=0, points=9999, occ={2: 1}, rolls=[1, 0])
    case("★ 被保者的 +0x34 挂 0x80（= 直接置「刑满」位）", s["flag"][2], 0x80)
    case("   占用表清 0", s["occ"][2], 0)
    case("   没动到 +0x35（醫院那一格）", s["flag"][4 + 2], 0)
    case("   显示时长 1500ms 的框被调用", s["show"], 1)
    case("   替身槽不走 0x43d7bf", s["rel"], 0)
    s = f.run(HOSPITAL, who=2, personality=0, points=9999, occ={1: 1}, rolls=[1, 0])
    case("醫院：被保者的 +0x35 挂 0x80", s["flag"][4 + 1], 0x80)
    s = f.run(PRISON, who=2, personality=2, points=700, occ={6: 1}, rolls=[1, 0])
    case("★ 替身槽（>=4）⇒ 调 0x43d7bf 而不是置位", (s["rel"], s["flag"][6]), (1, 0))
    s = f.run(HOSPITAL, who=2, personality=2, points=700, occ={6: 1}, rolls=[1, 0])
    case("   醫院那支调 0x43ee6e（同一个「放人」步）", s["rel"], 1)
    case("★★ 占用表的分工：替身槽由**放人函数**清，本函数一个字都不写",
         s["occ"][6], 1)

    print("\n[H] 名字与文本")
    s = f.run(PRISON, who=2, personality=0, points=9999, occ={1: 1}, rolls=[1, 0])
    case("★ 玩家槽：名字源 = player[下标][+0x00] 那 4 字节",
         s["name_args"][1], 0x11110001)
    case("   拼串格式串 = 0x465169（「保釋%s」）", s["fmt_args"][0] != 0, True)
    s = f.run(PRISON, who=2, personality=2, points=700, occ={7: 1}, rolls=[1, 0])
    case("★ 替身槽：名字源 = dword[0x47ed5a + 槽*4]",
         s["name_args"][1], e.readu32(NAME_TABLE + 7 * 4))

    print("\n[I] 真人（who_plays == 1）走的是模态屏，不在这里判定")
    s = f.run(PRISON, who=1, points=9999, occ={0: 1}, rolls=[1, 0])
    case("不掷 rand、不动占用表、不扣点", (s["rolls"], s["occ"][0], s["points"]), (0, 1, 9999))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
