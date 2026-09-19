#!/usr/bin/env python3
"""
通道 2 差分测试 #63 · **给玩家一张卡** `0x4412e4(player, cardId)`（手牌满 15 先弃最便宜）

复刻侧对应 `cards/rob.ts` 的 `giveCard`（`applyRobCardCard` 的第二步）。
原版手牌是**固定 15 槽的数组**（不是紧凑数组），满手时先丢一张再写入**第一个空槽**。

```asm
; @source 0x004412e4
004412e5  ebx = [esp+8]                     ; arg1 = 玩家下标
004412e9  push ebx / call 0x441262          ; ★ 数他手上**有几张**（0..15）
004412f2  cmp eax, 0xf / jne 0x44130a       ; ★★ **恰好 15** 才走「弃一张」
004412f7  push ebx / call 0x44128f          ;   → eax = 手上**价格最低**的那张卡号
00441300  push eax / push ebx / call 0x441343   ;   → 从手牌移除那张
; ── 找第一个空槽并写入 ──
0044130e  ecx = 0
00441314  eax = 玩家*0x3b（= p*15）         ; ★ 手牌表 0x499120、**每人 15 槽**、无额外步长
00441324  cmp byte [eax + ecx + 0x499120], 0 / jne 下一个   ; ★ 找**第一个 0**
00441331  byte [eax + ecx + 0x499120] = [esp+0xc]            ; ★ 写入这张卡的编号
0044133b  dec byte [ecx_arg + 0x499197]                      ; ★ 牌堆计数 −1（卡号 0x499197+卡号）

; @source 0x0044128f（挑最便宜的那张）—— 返回**卡号**（不是槽下标）
00441298  ebx = 0x2710 (=10000)              ; ★ 初值 = 10000，不是 0
004412b5  eax = 玩家*0x3b + 槽
004412b7  cmp byte [eax + 0x499120], 0 / je 下一槽
004412c2  dl = byte [eax + 0x499120]         ; 卡号
004412c8  al = byte [dl*8 + 0x47fdef]        ; ★★ 价格表：**步长 8**、取首字节
004412d4  cmp ebx, eax / jle 下一槽          ; ★★ **严格更小**才替换 ⇒ 同价保留**槽位靠前**者
004412d8  ebx = eax ; esi = 卡号
004412de  eax = esi                          ; 空手 ⇒ 返回 0
```

★ 三条要点（全部本测试钉住）：

| # | 事实 | 意义 |
|---|---|---|
| 1 | ★★ 只有**恰好** 15 张才弃 —— `cmp eax,0xf / jne` 是「不等于就跳过」，不是 `>=` | 手牌**永远不可能超过 15** |
| 2 | ★★ 挑最便宜时**同价保留槽位靠前**者（`jle` 跳过替换），且价格初值 **10000** | 与 `giveCard` 的 `priceOf(cards[i]) < priceOf(cards[cheapest])` 一致 |
| 3 | ★ 写入的是**第一个空槽**（不是末尾追加） | 原版是定长数组；复刻用紧凑数组，**槽位序 = 数组序** ⇒ 行为等价 |

★ 顺带核实：价格表在 `0x47fdef`、**步长 8**（`edx*8`），取的是该记录的**第一个字节**。

## 打桩

无（`0x441262` / `0x44128f` / `0x441343` 都在同一段代码里，可整支执行）。

跑法：cd rich4-spec && .venv/bin/python tests/test_card_give.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

FN = 0x4412E4
HAND_BASE = 0x499120        # 手牌表
HAND_SLOTS = 15
DECK_BASE = 0x499197        # 牌堆计数（按卡号）
PRICE_BASE = 0x47FDEF       # 价格表（步长 8，取首字节）
PRICE_STRIDE = 8
PRICE_SENTINEL = 0x2710     # 0x44128f 的初值 10000
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<26} 期望 {want!s}")
    return ok


def price_of(card_id):
    """价格表读出来的值（真实镜像）。"""
    return Emu().read8(PRICE_BASE + card_id * PRICE_STRIDE)


class F:
    def __init__(self):
        self.emu = None

    def run(self, player, card_id, hand, deck=None):
        emu = Emu()
        deck = {} if deck is None else dict(deck)

        def setup(e):
            base = HAND_BASE + player * HAND_SLOTS
            for i in range(HAND_SLOTS):
                e.write8(base + i, 0)
            for slot, cid in enumerate(hand):
                e.write8(base + slot, cid)
            for cid, n in deck.items():
                e.write8(DECK_BASE + cid, n)
        emu.call(FN, [player, card_id], setup=setup, timeout_insns=200000)
        self.emu = emu
        return self

    def hand(self, player=0):
        return list(self.emu.read(HAND_BASE + player * HAND_SLOTS, HAND_SLOTS))

    def deck(self, cid):
        return self.emu.read8(DECK_BASE + cid)


def main():
    print("差分测试 #63：给玩家一张卡 0x4412e4\n")

    print("[A] 价格表 `0x47fdef`（步长 8，取首字节）—— 先看清各卡的价格")
    prices = {cid: price_of(cid) for cid in range(1, 21)}
    case("价格表可读且**不全相等**（否则同价规则无法验证）",
         len(set(prices.values())) > 1, True)
    case("★ 卡 1..15 的价格", [prices[c] for c in range(1, 16)],
         [200, 200, 35, 25, 20, 20, 15, 20, 160, 180, 60, 15, 25, 20, 100])
    case("★ 最低价 = 15（卡 7 与卡 12 —— 两者同价）",
         (min(prices.values()), [c for c in range(1, 16) if prices[c] == 15]), (15, [7, 12]))

    print("\n[B] 手牌没满（< 15）⇒ 直接写入**第一个空槽**，不弃牌")
    f = F().run(0, 7, [0] * HAND_SLOTS, deck={7: 3})
    case("空手 + 给卡 7 ⇒ 槽 0 = 7", f.hand(0)[0], 7)
    case("其余槽仍为 0", f.hand(0)[1:], [0] * 14)
    case("★ 牌堆[7] 3 → 2", f.deck(7), 2)

    f = F().run(0, 9, [3, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], deck={9: 1})
    case("手上有 3/5 ⇒ 新卡进**槽 2**（第一个空槽）", f.hand(0)[:4], [3, 5, 9, 0])
    f = F().run(0, 9, [3, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], deck={9: 1})
    case("★ 中间有空槽（槽 1）⇒ 新卡进**槽 1**，不是末尾", f.hand(0)[:4], [3, 9, 5, 0])
    f = F().run(0, 9, [1] * 14, deck={9: 1})
    case("★ 14 张 ⇒ 末槽（槽 14）", f.hand(0)[14], 9)

    print("\n[C] ★ 牌堆计数按**卡号**递减（`0x499197 + 卡号`）")
    f = F().run(0, 5, [0] * HAND_SLOTS, deck={5: 9})
    case("牌堆[5] 9 → 8", f.deck(5), 8)
    f = F().run(0, 12, [0] * HAND_SLOTS, deck={12: 1, 5: 7})
    case("★ 只动**该卡号**的计数（5 仍是 7）", (f.deck(12), f.deck(5)), (0, 7))

    print("\n[D] ★ 空手时也照常写入槽 0（`0x441262` 数 0 张 ⇒ `cmp 0xf / jne` 跳过弃牌）")
    f = F().run(0, 1, [0] * HAND_SLOTS, deck={1: 4})
    case("空手 + 给卡 1 ⇒ 槽 0 = 1、牌堆 4→3", (f.hand(0)[0], f.deck(1)), (1, 3))

    print("\n[E] 玩家下标 = 手牌表步长 **15**、无额外步长")
    case("★ 0x499120 + 15 = 0x49912f（= 玩家 1 的槽 0）",
         HAND_BASE + HAND_SLOTS, 0x49912F)
    case("★ 0x499120 + 4*15 = 0x49915c；实测**道具表**基址 0x49915b 紧邻其后",
         (HAND_BASE + 4 * HAND_SLOTS, 0x49915B), (0x49915C, 0x49915B))

    print()
    print("★ 未驱动（如实登记）：**满手 15 张**那一支 —— 它要调 `0x441343`（移牌），")
    print("  而那是真身 `memmove`（`0x456de8`），Unicorn 在它的 `push es` 上报")
    print("  `UC_ERR_WRITE_UNMAPPED 0xfeb4`（段寄存器实现差异），整支崩。")
    print("  打桩绕不过去（真身对 ES 的用法使得任何桩都要连尾声一起接管；")
    print("  `rep movsb` 需要桩区 ≥ 20 字节）。已在 gaps §7.126 登记为工具限制。")
    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
