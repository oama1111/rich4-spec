#!/usr/bin/env python3
"""
通道 2 差分测试 #54 · **樂透開獎「派彩 + 关屏」那一支** `0x430ab5`（開獎屏状态机跳表 `0x4300d0` 第 9 项）

開獎屏的窗口过程按 `[0x48c37b]` 走状态 0..10，跳表 `0x4300d0`（实测 dump，10 项）。
第 9 项 `0x430ab5` 是**收尾**：把累積獎金派给得主、清空号码槽、关屏。

```asm
; @source 0x00430ab5
00430ab5  ecx = [0x48c373] / push / KillTimer(esi=hwnd, [0x48c373])
00430ac4  ebx = [0x48c377]              ; ★ 得主 = 玩家下标+1（0 = 無人得獎）
00430aca  test ebx,ebx / je 0x430afb    ; ★★ 無人得獎 ⇒ **整段派彩跳过**（含 memset 与池归零）
00430ace  push 1                        ; flags = 1 ⇒ 进**现金**（不是存款）
00430ad0  edi = [0x499080]              ; ★ 累積獎金池**全额**
00430ad6  push edi
00430ad7  eax = ebx - 1                 ; 得主下标
00430ada  call 0x41d3f4                 ; give_money(player, pool, flags=1)
00430ae0  add esp,0xc
00430ae3  xor ebp,ebp
00430ae5  [0x499080] = 0                ; ★ 池归零
00430ae7  memset(0x4990b8, 0, 0x24)     ; ★ 36 个号码槽全清
00430afb  push 0 / call 0x401966        ; PostMessage(0x402)（关屏）
00430b02  jmp 0x430249                  ; ⇒ add esp,4 / cmp [0x48c37b],3 ⇒ 回窗口过程
```

★ 一句话：**「無人得獎」时奖金与票全部结转**（下一段正是「累積獎金会越滚越大」的原因）。

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x4622fc`（导入 thunk） | 桩区 `xor eax,eax ; ret` | `KillTimer(hwnd, id)` 指向未映射的 User32 |
| `0x401966` | 桩区 `ret` | `Post_0402_Message`：内部走 thunk `0x462310`（PostMessageA）⇒ 关屏是表现层 |

跑法：cd rich4-spec && .venv/bin/python tests/test_lottery_settle.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import STUB_BASE, Emu  # noqa: E402

FN = 0x430AB5
STOP = 0x43024C                 # `add esp,4` 之后的第一条（状态检查）—— 不再往下走屏
TABLE = 0x4300D0
UI_STATE = 0x48C37B             # 状态机状态字节
TIMER_ID = 0x48C373
WINNER = 0x48C377               # ★ 得主 = 玩家下标 + 1，0 = 無人得獎
POOL = 0x499080                 # 累積獎金池
SLOTS = 0x4990B8                # 36 个号码槽
SLOT_N = 0x24
PLAYER_BASE = 0x496B68
P_CASH = 0x1C                   # +0x1c 现金
P_BANK = 0x20                   # +0x20 存款
P_MONTHLY = 0x60                # +0x60 本月收入（`0x496bc8 = 0x496b68 + 0x60`）
STRIDE = 0x68
CUR = 0x49910C
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<26} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def _install(self, e):
        # `KillTimer` 导入 thunk：把它存的地址改成桩区的 `xor eax,eax ; ret`
        e.patch(STUB_BASE, b"\x31\xC0\xC3")
        e.patch(0x4622FC, struct.pack("<I", STUB_BASE))
        # `Post_0402_Message`：内部走未映射的 PostMessageA ⇒ 整支打桩
        e.patch(0x401966, b"\xC3")
        # `0x41d433`：`give_money` 只在**得主 == 当前玩家**时调它（那是「刷新自己的
        #   余额显示」那一支，纯表现）⇒ 打桩；也正因如此下面的用例默认让
        #   当前玩家 != 得主，**不依赖这个桩**。
        e.patch(0x41D433, b"\xC3")

    def run(self, *, winner=0, pool=0, slots=None, cash=0, bank=0,
            monthly=0, player=0, cur=0, state=10):
        emu = Emu()

        def setup(e):
            self._install(e)
            e.write8(UI_STATE, state)
            e.write32(TIMER_ID, 0x1234)
            e.write32(WINNER, winner)
            e.write32(POOL, pool)
            e.write32(CUR, cur)
            e.write32(PLAYER_BASE + player * STRIDE + P_CASH, cash)
            e.write32(PLAYER_BASE + player * STRIDE + P_BANK, bank)
            e.write32(PLAYER_BASE + player * STRIDE + P_MONTHLY, monthly)
            for i in range(SLOT_N):
                e.write8(SLOTS + i, (slots or [0] * SLOT_N)[i])
            e.write32(0x53FFF0 - 8, 0)          # 帧余量
        emu.eval_block(FN, STOP, regs={"esp": 0x53FFF0 - 8},
                       setup=setup, timeout_insns=200000)
        self.emu = emu
        return self

    def cash(self, player=0):
        return self.emu.readu32(PLAYER_BASE + player * STRIDE + P_CASH)

    def bank(self, player=0):
        return self.emu.readu32(PLAYER_BASE + player * STRIDE + P_BANK)

    def monthly(self, player=0):
        return self.emu.readu32(PLAYER_BASE + player * STRIDE + P_MONTHLY)

    def pool(self):
        return self.emu.readu32(POOL)

    def slots(self):
        return list(self.emu.read(SLOTS, SLOT_N))


def main():
    print("差分测试 #54：樂透開獎派彩收尾 0x430ab5\n")

    print("[A] 跳表 `0x4300d0`（10 项状态机处理器，实测 dump）")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(10)]
    case("10 项逐项相同",
         got, [0x430236, 0x43036C, 0x43024C, 0x430485, 0x43024C,
               0x4306FF, 0x4308E0, 0x4308F3, 0x430AA3, 0x430AB5])
    case("★ 第 9 项就是本函数", got[9], FN)

    print("\n[B] 有人中奖：派彩 = 池**全额**、进**现金**、池归零、号码槽全清")
    filled = [1] * SLOT_N
    # 得主下标 2（`[0x48c377] = 3`）身上预置现金 100 / 存款 200 / 本月收入 7
    f = F().run(winner=3, pool=12345, slots=filled, player=2, cur=0,
                cash=100, bank=200, monthly=7)
    case("得主（下标 2）现金 100 + 12345 = 12445", f.cash(2), 12445)
    case("★ flags=1 ⇒ **存款不动**", f.bank(2), 200)
    case("★ 本月收入 +12345", f.monthly(2), 7 + 12345)
    case("池归零", f.pool(), 0)
    case("★ 36 个号码槽全清", f.slots(), [0] * SLOT_N)
    case("★ 非得主分文不动", (f.cash(0), f.cash(1), f.cash(3)), (0, 0, 0))
    case("★ 非得主账户的存款/本月收入也一动不动",
         (f.bank(0), f.bank(1), f.monthly(0), f.monthly(1)), (0, 0, 0, 0))

    print("\n[C] 無人得奖（得主 == 0）：**整段派彩跳过** —— 奖金与票全部结转")
    f = F().run(winner=0, pool=99999, slots=filled, player=2, cur=0, cash=100, bank=200)
    case("池**保持不变**（结转下月）", f.pool(), 99999)
    case("★ 36 个号码槽**全部保留**", f.slots(), filled)
    case("★ 所有账户**都保持注入时的原值**（预置：下标 2 现金 100 / 存款 200）",
         (f.cash(0), f.cash(1), f.cash(2), f.cash(3)), (0, 0, 100, 0))
    case("存款同样一动不动", (f.bank(0), f.bank(2)), (0, 200))

    print("\n[D] 得主下标 = `[0x48c377] − 1`（逐位验）")
    for w in (1, 2, 3, 4):
        f = F().run(winner=w, pool=1000, slots=[0] * SLOT_N)
        hit = [p for p in range(4) if f.cash(p) == 1000]
        case(f"得主域 {w} ⇒ 收款人下标 {w-1}", hit, [w - 1])

    print("\n[E] 池为 0 时仍然「成交」：槽被清、池保持 0")
    f = F().run(winner=1, pool=0, slots=filled)
    case("池 0 ⇒ 现金仍 0", f.cash(0), 0)
    case("★ 号码槽**仍被清空**（`memset` 不在 `pool != 0` 闸门内）",
         f.slots(), [0] * SLOT_N)

    print("\n[F] ★ 得主恰是**当前玩家**时：多走一条刷新分支（已打桩），金额口径不变")
    f = F().run(winner=1, pool=777, slots=[0] * SLOT_N, player=0, cur=0,
                cash=5, bank=6, monthly=1)
    case("现金 5 + 777 = 782", f.cash(0), 782)
    case("存款不动（flags=1）", f.bank(0), 6)
    case("本月收入 1 + 777", f.monthly(0), 778)
    case("池归零", f.pool(), 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
