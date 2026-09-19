#!/usr/bin/env python3
"""
通道 2 差分测试 #24 · **换人 / 回合开始** `0x00418ebd`（429 字节，全 exe 唯一调用点 `0x40d86f`）

这支函数是「上一位走完 → 推进游标 → 给**新**当前玩家走一天」的全部逻辑，
第 84/85 条正是靠它才把「递减的是哪一位」与「刑满后白丢一回合」两件事定下来。
本测试把它的**顺序与游标**钉死。

## 反汇编骨架（A 级）

```asm
; 入口（唯一调用点 0x40d86f，来自走路/结算驱动 0x40d808 的"回合记录 0x80"分支）
00418ec2  dword [0x48be18] = 0            ; ★ 清"需要重绘地图"标志
00418ec8  ecx = [0x49910c]                ; 当前 actor
00418ece  cmp ecx, 8 / jne 0x418efb
00418ed3      [0x49910c] = byte [0x498e70]; if (![0x498e72]) [0x498e72] = 3
00418ef1      call 0x415e70(1) / jmp 0x419055     ; ★ 另一条"轮次收尾"路径
00418efb  cmp ecx, 4 / jge 0x418f93               ; 惡人（0x20 相位）不走阻碍那一支
00418f07  test byte [player+0x15], 0x30 / je 0x418f93
          ; ── 被阻碍（含"刚释放、走回棋盘"）：整回合跳过 ──
00418f16      call 0x41906a(1)
00418f25      test byte [player+0x15], 0x10 / je 0x418f80
00418f2e         bl = [player+0x1b] & 0xf
00418f37         cmp bl, 0xf / je 0x418f42      ; 哨兵 ⇒ 不恢复朝向
00418f3c         [player+0x10] = bl
00418f59         call 0x40f381(player, node)   ; 神明显灵落点
00418f78         call 0x448a7e(player, node)   ; 中途落脚判定（对監獄/醫院格是空操作）
00418f87      and byte [player+0x15], 0xf      ; ★ 清 0x10/0x20
00418f8e      jmp 0x419058                     ; ★ **不推进游标**、不 tick
; ── 0x418f93 推进游标 ──
00418f95  esi = cur + 1 ; [0x49910c] = esi
00418fa2  if (esi == [0x499114]) { [0x49910c] = 4; goto 0x418fd4 }
00418fb6  if (esi == 8) { [0x49910c] = 0; ebx = 1; goto 0x418fee }   ; ★ ebx=1 ⇒ 绕回
00418fca  if (4 <= esi < 8) { [0x49910c] = 4; goto 0x418fd4 }
00418fd4  eax = [0x49910c] << 4 ; if (byte [eax+0x498df2] != 0) goto 0x418f95  ; 该 actor 不在场 → 再推
00418fe5  if ([0x49910c] >= 4) goto 0x419008
00418fee  if (player.whoPlays == 0 && player.xpos == 0) goto 0x418f95         ; 出局且不在盘上 → 再推
00419008  if ([0x46caff] != 0) { [0x46caff] = 0; call 0x41906a(1); and [0x496b7d], 0xfb }
0041902a  if (ebx) call 0x41cf67          ; ★★ 只有"绕回 0 号"那一次才推日期/物价/行情/開獎/月結
00419033  eax = [0x49910c]
00419039  call 0x41c84f                   ; ★★ 递减**新**当前玩家的阻碍计数
00419041  if (ebx) { if ([0x49715c]) call 0x402fd1(0) }
00419058  dword [0x498ea0 + [0x49910c]*0x34] |= 0x80   ; 回合记录：这一位已派过
00419069  ret
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41c84f` | 被查对象：日切 tick | **记录实参 + 调用序号**后 `ret` |
| `0x41cf67` | 推日期/物价/行情/開獎/月結 | **记录调用序号**后 `ret` |
| `0x40f381` | 神明显灵落点 | 记录 `(player, node)` 后 `ret` |
| `0x448a7e` | 中途落脚判定 | 记录 `(player, node)` 后 `ret` |
| `0x41906a` / `0x402fd1` / `0x415e70` | 刷新 / 收尾 / 轮次 | `ret` |

跑法：cd rich4-spec && .venv/bin/python tests/test_turn_cursor.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

ADVANCE = 0x418EBD

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE = 0x08, 0x0A, 0x0C
P_FACING, P_WHO, P_BACKUP = 0x10, 0x15, 0x1B
CURRENT = 0x49910C
PLAYER_COUNT = 0x499114
ACTOR_ACTIVE = 0x498DF2  # actor `idx` 的在场字节 = `[idx<<4 | 0x498df2]`
TURN_REC_BASE, TURN_REC_STRIDE = 0x498EA0, 0x34
REDRAW_FLAG = 0x48BE18
GATE_46CAFF = 0x46CAFF
GATE_49715C = 0x49715C

TICK = 0x41C84F
DAY_ADVANCE = 0x41CF67
GOD_LANDING = 0x40F381
MID_LANDING = 0x448A7E
REFRESH = 0x41906A
FINALE = 0x402FD1
ROUND_END = 0x415E70

# 暂存区：顺序日志 + 各桩的实参
ORDER = SCRATCH_BASE + 0x300
TICK_ARG, TICK_ORDER, TICK_COUNT = SCRATCH_BASE + 0x310, SCRATCH_BASE + 0x314, SCRATCH_BASE + 0x318
DAY_ORDER, DAY_COUNT = SCRATCH_BASE + 0x320, SCRATCH_BASE + 0x324
F381_P, F381_NODE, F381_ORDER = SCRATCH_BASE + 0x330, SCRATCH_BASE + 0x334, SCRATCH_BASE + 0x338
M448_P, M448_NODE, M448_ORDER = SCRATCH_BASE + 0x340, SCRATCH_BASE + 0x344, SCRATCH_BASE + 0x348

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def _bump_order():
    """`mov ecx,[ORDER] / inc ecx / mov [ORDER],ecx`（结果留在 ecx）"""
    return b"\x8B\x0D" + struct.pack("<I", ORDER) + b"\x41" + b"\x89\x0D" + struct.pack("<I", ORDER)


def stub_1arg(arg_slot, order_slot, count_slot):
    """记 (arg1, order) 并计数，然后 ret。"""
    return (
        _bump_order()
        + b"\x8B\x44\x24\x04"                                  # mov eax,[esp+4]
        + b"\xA3" + struct.pack("<I", arg_slot)                # mov [arg],eax
        + b"\x89\x0D" + struct.pack("<I", order_slot)          # mov [order],ecx
        + b"\xFF\x05" + struct.pack("<I", count_slot)          # inc dword [count]
        + b"\xC3"
    )


def stub_0arg(order_slot, count_slot):
    return (
        _bump_order()
        + b"\x89\x0D" + struct.pack("<I", order_slot)
        + b"\xFF\x05" + struct.pack("<I", count_slot)
        + b"\xC3"
    )


def stub_2arg(a_slot, b_slot, order_slot):
    """`(player, node)` 两参桩。"""
    return (
        _bump_order()
        + b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", a_slot)
        + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", b_slot)
        + b"\x89\x0D" + struct.pack("<I", order_slot)
        + b"\xC3"
    )


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(TICK, stub_1arg(TICK_ARG, TICK_ORDER, TICK_COUNT))
        self.emu.patch(DAY_ADVANCE, stub_0arg(DAY_ORDER, DAY_COUNT))
        self.emu.patch(GOD_LANDING, stub_2arg(F381_P, F381_NODE, F381_ORDER))
        self.emu.patch(MID_LANDING, stub_2arg(M448_P, M448_NODE, M448_ORDER))
        for va in (REFRESH, FINALE, ROUND_END):
            self.emu.patch(va, b"\xC3")

    def run(self, entry, *, who=None, facing=3, backup=0, xpos=100, node=5,
            count=4, actors_on=(True, True, True, True), pending_46caff=0,
            gate_49715c=0, redraw=0xFFFF):
        w = who if who is not None else [1, 1, 1, 1]

        def setup(emu):
            emu.write32(CURRENT, entry)
            emu.write32(PLAYER_COUNT, count)
            emu.write8(REDRAW_FLAG, redraw & 0xFF)
            emu.write8(REDRAW_FLAG + 1, (redraw >> 8) & 0xFF)
            emu.write8(GATE_46CAFF, pending_46caff)
            emu.write8(GATE_49715C, gate_49715c)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write16(base + P_X, xpos)
                emu.write16(base + P_Y, 200)
                emu.write16(base + P_NODE, node)
                emu.write8(base + P_FACING, facing)
                emu.write8(base + P_WHO, w[i])
                emu.write8(base + P_BACKUP, backup)
            # 惡人槽 4..7 的**状态字节**（`0x498df2 + idx*0x10` = 槽记录 `+0x0a`）
            # ★ 极性：**非 0 ⇒ 跳过这一位**（`0x418fdc cmp byte [eax+0x498df2],0 / jne 0x418f95`）
            #   ——「关着/不在盘上」的 NPC 就是靠这个字节被跳过的。
            for k, on in enumerate(actors_on):
                emu.write8((4 + k) * 16 + ACTOR_ACTIVE, 0 if on else 1)
            for i in range(8):
                emu.write8(TURN_REC_BASE + i * TURN_REC_STRIDE, 0)
                emu.write8(TURN_REC_BASE + i * TURN_REC_STRIDE + 2, 0)
                emu.write8(TURN_REC_BASE + i * TURN_REC_STRIDE + 3, 0)
            # 顺序日志清零（每次 run 都是新的 reset，但显式写一遍更稳）
            emu.write32(ORDER, 0)
            for slot in (TICK_ARG, TICK_ORDER, TICK_COUNT, DAY_ORDER, DAY_COUNT,
                         F381_P, F381_NODE, F381_ORDER, M448_P, M448_NODE, M448_ORDER):
                emu.write32(slot, 0)

        self.emu.call(ADVANCE, [entry], setup=setup)
        return Snap(self.emu)


class Snap:
    def __init__(self, e):
        self.e = e
        self.current = e.read32(CURRENT)
        self.redraw = e.read32(REDRAW_FLAG) & 0xFFFF
        self.tick_arg = e.read32(TICK_ARG)
        self.tick_order = e.read32(TICK_ORDER)
        self.tick_count = e.read32(TICK_COUNT)
        self.day_order = e.read32(DAY_ORDER)
        self.day_count = e.read32(DAY_COUNT)
        self.f381 = (e.read32(F381_P), e.read32(F381_NODE), e.read32(F381_ORDER))
        self.m448 = (e.read32(M448_P), e.read32(M448_NODE), e.read32(M448_ORDER))
        self.turnrec = [
            (e.read8(TURN_REC_BASE + i * TURN_REC_STRIDE),
             e.read8(TURN_REC_BASE + i * TURN_REC_STRIDE + 2),
             e.read8(TURN_REC_BASE + i * TURN_REC_STRIDE + 3))
            for i in range(8)
        ]
        self.flags = [e.read8(PLAYER_BASE + i * PLAYER_STRIDE + P_WHO) for i in range(4)]
        self.facing = [e.read8(PLAYER_BASE + i * PLAYER_STRIDE + P_FACING) for i in range(4)]


def main():
    print("差分测试 #24：换人 / 回合开始 —— 0x418ebd\n")
    f = F()

    print("[1] 游标推进：0→1→2→3→4(惡人)→…→7→绕回 0")
    s = f.run(0)
    case("入口 0 → 当前玩家 1", s.current, 1)
    case("   清了重绘标志 [0x48be18]", s.redraw, 0)
    case("   回合记录 [1] |= 0x80", s.turnrec[1][0], 0x80)
    s = f.run(1)
    case("入口 1 → 2", s.current, 2)
    s = f.run(2)
    case("入口 2 → 3", s.current, 3)
    s = f.run(3)
    case("★ 入口 3（玩家人数 4）→ 4：跳到惡人段，**不是**绕回 0", s.current, 4)
    case("   这一支不推日期", s.day_count, 0)
    s = f.run(4)
    case("入口 4 → 5", s.current, 5)
    s = f.run(7)
    case("★ 入口 7 → 绕回 0（esi==8 那一支）", s.current, 0)
    case("★ 只有绕回那一支才推日期", s.day_count, 1)

    print("\n[2] ★★ 递减/推日期的**顺序与对象**（第 84/85 条的根据）")
    s = f.run(0)
    case("tick 的实参 = **新**当前玩家 1（不是入口的 0）", s.tick_arg, 1)
    case("非绕回 ⇒ 一次 tick、零次推日期", (s.tick_count, s.day_count), (1, 0))
    s = f.run(7)
    case("绕回：推日期 1 次、tick 1 次", (s.day_count, s.tick_count), (1, 1))
    case("★ 顺序：推日期(tick#1) **先于** tick(#2)", (s.day_order, s.tick_order), (1, 2))
    s = f.run(4)
    case("惡人段的 actor 也要 tick（实参 = 5）", s.tick_arg, 5)

    print("\n[3] 跳过不在场 / 已出局的 actor")
    s = f.run(3, actors_on=(False, False, False, False))
    case("★ 四个惡人都不在场（状态字节非 0）⇒ 从 3 一路绕回 0 并推日期",
         (s.current, s.day_count), (0, 1))
    case("   绕回那一次照样 tick 一次（对象 = 0）", (s.tick_count, s.tick_arg), (1, 0))
    case("★ 但玩家段的「在场」判据与惡人**不同**（见下一组）", s.current, 0)
    s = f.run(0, who=[1, 0, 1, 1], xpos=100)
    case("★ whoPlays==0 且 xpos!=0 ⇒ 跳过（`0x418ffc`/`0x419006` 那两句）", s.current, 2)
    s = f.run(0, who=[1, 0, 1, 1], xpos=0)
    case("★ whoPlays==0 且 xpos==0 ⇒ **不**跳过（照 machine code 的原样）", s.current, 1)

    print("\n[4] ★ 被阻碍那一支：**不推进游标**、整回合跳过")
    s = f.run(0, who=[0x11, 1, 1, 1], backup=0)
    case("带 0x10 的人：当前玩家**不变**（仍是 0）", s.current, 0)
    case("   清掉 0x10/0x20（`and 0xf`）", s.flags[0], 0x01)
    case("★ 这一支**不 tick**、不推日期", (s.tick_count, s.day_count), (0, 0))
    case("★ 走回棋盘的收尾：先 0x40f381 再 0x448a7e",
         (s.f381[0], s.f381[2], s.m448[0], s.m448[2]), (0, 1, 0, 2))
    case("   两支都带上了该玩家的所在格", (s.f381[1], s.m448[1]), (5, 5))
    s = f.run(0, who=[0x21, 1, 1, 1])
    case("只带 0x20（位置被挪过）：同样整回合跳过、不调那两支",
         (s.current, s.f381[2], s.m448[2]), (0, 0, 0))
    s = f.run(0, who=[0x11, 1, 1, 1], backup=0x03)
    case("★ 朝向后备 != 0xf ⇒ 写回 +0x10", s.facing[0], 3)
    s = f.run(0, who=[0x11, 1, 1, 1], facing=5, backup=0x0F)
    case("★ 后备 == 0xf（关押写的哨兵）⇒ **不**恢复朝向", s.facing[0], 5)

    print("\n[5] 两个小闸")
    s = f.run(0, pending_46caff=1)
    case("[0x46caff] 非 0 ⇒ 被清掉（并刷新一次）", f.emu.read8(GATE_46CAFF), 0)
    s = f.run(7, gate_49715c=1)
    case("绕回且 [0x49715c] 非 0 ⇒ 调 0x402fd1（已打桩，不崩）", s.current, 0)
    s = f.run(0, redraw=0x1234)
    case("重绘标志被整个 dword 清 0", (f.emu.read32(REDRAW_FLAG), s.redraw), (0, 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
