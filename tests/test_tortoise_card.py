#!/usr/bin/env python3
"""
通道 2 差分测试 #27 · **烏龜卡**（卡片 30）`0x004458df`（366 字节）

复刻侧是 `rich4-remake/packages/core/src/cards/tortoise.ts`。本测试把三件事钉住：

1. ★ **天数因目标而异**：打**自己** 2 天、打**别人** 3 天（`+0x39 days_tortoise_walking`）；
2. 目标 ≥ 4（特殊棋子）写替身记录的 `+0x0f single_step = 3`；
3. ★ **没选目标 ⇒ 卡不扣**（掩码为 0 时在扣卡之前就跳走）。

## 反汇编（A 级）

```asm
004458e3  imul eax, [0x49910c], 0x68
004458ea  cmp  byte [eax + 0x496b7d], 1     ; 当前玩家是**真人**？
004458f1  jne  0x4458ff
004458f3      push 0xe0c0010 / call 0x446ae8 ;   真人：弹选目标窗（anyPlayer 掩码）
004458fd      jmp  0x445906
004458ff  push 0 / call 0x41e6f2             ;   电脑：取默认目标掩码
00445909  edi = eax
0044590b  test edi,edi / je 0x4440e3         ; ★ 没选到人 ⇒ 直接走公共尾（**不扣卡**）
00445914  call 0x40d293                      ; 掩码 → 目标下标（ctz 最低位）
00445920  push 0x1e / push [0x49910c] / call 0x441343   ; ★ remove_card(当前玩家, 30)
; …表现层：0x40e669 道具/卡片飞行动画、0x44ef41 换立绘…
004459b7  cmp esi,4 / jge 0x445a3e           ; ★ 目标 ≥ 4 = 特殊棋子
004459c3  cmp esi, [0x49910c] / jne 0x445a02 ; 目标 == 当前玩家？
004459f6      mov byte [ebx + 0x496ba1], 2   ;   ★ 自己：+0x39 = 2
00445a02  …  mov byte [ebx + 0x496ba1], 3   ;   ★ 别人：+0x39 = 3
00445a34      call 0x41d546                  ;   音效
00445a3e  shl esi,4 / mov byte [esi + 0x498df7], 3   ; ★ 替身：+0x0f = 3
00445a48  jmp 0x4440e3                        ; 公共尾（本测试打桩成 ret）
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41e6f2` | 电脑取默认目标掩码 | **返回由用例指定的掩码**（数据驱动，见 `test_turn_around.py` 里记的二次补丁坑）|
| `0x446ae8` | 真人选目标窗 | `ret`（返回值走数据槽）|
| `0x441343` | `remove_card(玩家, 卡号)` | 记录两个实参后 `ret` |
| `0x40e669` / `0x44ef41` / `0x41d546` | 卡片动画 / 换立绘 / 音效 | `ret` |
| `0x4440e3` | 公共卡尾（跳进来的） | **不打桩** —— 它是共享尾声（4 个 pop + ret），让它自然跑 |

跑法：cd rich4-spec && .venv/bin/python tests/test_tortoise_card.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

TORTOISE = 0x4458DF

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_WHO, P_TORTOISE = 0x15, 0x39
CURRENT = 0x49910C
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10
A_SINGLE_STEP = 0x0F  # 0x498df7 = 0x498e28 + 0*0x10 + 0x0f

DEFAULT_TARGET = 0x41E6F2   # 电脑：取默认目标掩码
PICK_WINDOW = 0x446AE8      # 真人：选目标窗
REMOVE_CARD = 0x441343
FX_OBJECT = 0x40E669
SET_POSE = 0x44EF41
SOUND = 0x41D546
CARD_TAIL = 0x4440E3

MASK_SLOT = SCRATCH_BASE + 0x700     # 默认目标掩码（数据驱动）
REMOVE_A, REMOVE_B = SCRATCH_BASE + 0x704, SCRATCH_BASE + 0x708
REMOVE_N = SCRATCH_BASE + 0x70C
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def stub_from_slot(slot):
    """`mov eax, [slot] / ret` —— 返回值放数据里（免得每用例重打补丁）"""
    return b"\xA1" + struct.pack("<I", slot) + b"\xC3"


def stub_rec2(a_slot, b_slot, n_slot):
    """记两个实参 + 计数：`mov eax,[esp+4] / mov [a],eax / mov eax,[esp+8] / mov [b],eax / inc [n] / ret`"""
    return (
        b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", a_slot)
        + b"\x8B\x44\x24\x08" + b"\xA3" + struct.pack("<I", b_slot)
        + b"\xFF\x05" + struct.pack("<I", n_slot)
        + b"\xC3"
    )


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(DEFAULT_TARGET, stub_from_slot(MASK_SLOT))
        self.emu.patch(PICK_WINDOW, stub_from_slot(MASK_SLOT))
        self.emu.patch(REMOVE_CARD, stub_rec2(REMOVE_A, REMOVE_B, REMOVE_N))
        for va in (FX_OBJECT, SET_POSE, SOUND):
            self.emu.patch(va, b"\xC3")
        # ⚠️ **不要**把公共尾 0x4440e3 打成 `ret`：它是**共享尾声**
        #    （`mov eax,edi / pop ebp / pop edi / pop esi / pop ebx / ret`），
        #    直接 `ret` 会把栈上保存的 ebp 当返回地址 ⇒ 跳到栈里崩掉（本测试踩过）。
        #    让它自然跑完即可 —— 最后的 `ret` 正好回到 `Emu.call` 压的返回地址。

    def run(self, mask, *, cur=0, who=2, tortoise=(0, 0, 0, 0), actor_offset=0):
        def setup(emu):
            emu.write32(CURRENT, cur)
            emu.write32(MASK_SLOT, mask)
            emu.write32(REMOVE_A, 0)
            emu.write32(REMOVE_B, 0)
            emu.write32(REMOVE_N, 0)
            for i in range(8):
                emu.write8(PLAYER_BASE + i * PLAYER_STRIDE + P_TORTOISE, 0)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + P_WHO, who)
                emu.write8(base + P_TORTOISE, tortoise[i] if i < 4 else 0)
            for k in range(4):
                emu.write8(ACTOR_BASE + k * ACTOR_STRIDE + A_SINGLE_STEP, actor_offset)

        self.emu.call(TORTOISE, [0], setup=setup)
        e = self.emu
        return {
            "tortoise": [e.read8(PLAYER_BASE + i * PLAYER_STRIDE + P_TORTOISE) for i in range(4)],
            "actors": [e.read8(ACTOR_BASE + k * ACTOR_STRIDE + A_SINGLE_STEP) for k in range(4)],
            "remove_a": e.read32(REMOVE_A),
            "remove_b": e.read32(REMOVE_B),
            "remove_n": e.read32(REMOVE_N),
        }


def main():
    print("差分测试 #27：烏龜卡（卡片 30）—— 0x4458df\n")
    f = F()

    print("[1] ★ 天数因目标而异：打自己 2 天、打别人 3 天")
    s = f.run(1 << 0, cur=0)
    case("目标 = 自己（掩码 bit0，当前也是 0）⇒ +0x39 = 2", s["tortoise"][0], 2)
    case("   卡被扣：remove_card(0, 0x1e)", (s["remove_a"], s["remove_b"], s["remove_n"]), (0, 0x1E, 1))
    s = f.run(1 << 2, cur=0)
    case("目标 = 2 号（别人）⇒ +0x39 = 3", s["tortoise"][2], 3)
    case("   卡同样被扣（0x1e）", (s["remove_a"], s["remove_b"]), (0, 0x1E))
    case("   别人不受影响（0 号仍 0）", s["tortoise"][0], 0)

    print("\n[2] ★ 掩码 → 目标下标 = ctz（最低位优先，`0x40d293`）")
    s = f.run((1 << 1) | (1 << 3), cur=0)
    case("掩码 bit1|bit3 ⇒ 取 1 号", s["tortoise"][1], 3)
    s = f.run(1 << 3, cur=0)
    case("掩码只 bit3 ⇒ 取 3 号", s["tortoise"][3], 3)
    s = f.run(1 << 2, cur=2)
    case("当前玩家是 2、目标也是自己(bit2) ⇒ 2 天", s["tortoise"][2], 2)
    s = f.run(1 << 3, cur=3)
    case("当前玩家是 3、目标是自己(bit3) ⇒ 2 天", s["tortoise"][3], 2)

    print("\n[3] 目标 ≥ 4（特殊棋子）⇒ 替身记录 `+0x0f single_step = 3`")
    s = f.run(1 << 5, cur=0)   # 下标 5 = 替身槽 1
    case("掩码 bit5 ⇒ 槽 1 的 +0x0f = 3", s["actors"][1], 3)
    case("   玩家一个都没被写", s["tortoise"], [0, 0, 0, 0])
    case("   卡也扣了", (s["remove_a"], s["remove_b"]), (0, 0x1E))
    s = f.run(1 << 4, cur=0)
    case("掩码 bit4 ⇒ 槽 0 的 +0x0f = 3", s["actors"][0], 3)

    print("\n[4] ★★ 掩码为 0（没选到人）⇒ **卡不扣**、什么都不写")
    s = f.run(0, cur=0)
    case("没有 remove_card 调用", s["remove_n"], 0)
    case("玩家的 +0x39 一个都没动", s["tortoise"], [0, 0, 0, 0])
    case("替身也没动", s["actors"], [0, 0, 0, 0])

    print("\n[5] 覆盖而不是累加（原版是 `mov byte`，不是 `add`）")
    s = f.run(1 << 1, cur=0, tortoise=(0, 9, 0, 0))
    case("原本 9 天 ⇒ 被**覆盖**成 3", s["tortoise"][1], 3)
    s = f.run(1 << 0, cur=0, tortoise=(9, 0, 0, 0))
    case("自己原本 9 天 ⇒ 覆盖成 2", s["tortoise"][0], 2)
    s = f.run(1 << 5, cur=0, actor_offset=7)
    case("替身原本 single_step = 7 ⇒ 覆盖成 3", s["actors"][1], 3)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
