#!/usr/bin/env python3
"""
通道 2 差分测试 #53 · **股市交易里「股票」那一支** `0x42565c`（4 路跳表 `0x4255ca` 第 0 项）

`0x4255da(arg1, arg2)` 是股市交易窗口「确认」的处理：先把挂牌行的**价格**与
当前玩家现金比一遍，再按挂牌行的 `kind`（`1..4`）分派 ——
跳表 `0x4255ca`（实测 dump）= `[0x42565c, 0x42577d, 0x4257d2, 0x425841]`
依次是**股票 / 不动产 / 道具 / 卡片**。本测试驱动 `arg1=卖家, arg2=格子序号`
走到**股票**那一支（`0x42565c`）。

```asm
; @source 0x004255da  （帧：`push ebx/esi/edi/ebp + sub esp,8` ⇒ arg1=[esp+0x1c]、arg2=[esp+0x20]）
004255e9  ebx = arg1*0x54 + arg2*0xC        ; 挂牌行（表基 0x4967e0，行距 0xc）★ 绝对地址
004255f8  ecx = [0x49910c]                  ; 当前玩家 = **买家**
00425601  eax = [玩家+0x496b84]             ; ★ 买家现金
00425607  cmp eax, [ebx+0x4967e4] / jge     ; ★ 现金 < 挂牌价 ⇒ 走「钱不够」提示、不成交
00425640  al = [ebx+0x4967e0] / dec / cmp 3 / ja   ; kind 1..4 → 跳表

; ── 股票支 0x0042565c ──
0042565e  ecx = u16 [ebx+0x4967e2]          ; 股票 id
00425665  eax = [0x49910c]                  ; 买家
0042566d  eax = eax*4 / sub eax,edx / shl 5 ⇒ eax = 买家*0x60
00425675  edi = id*8
0042567a  fild  dword [edi+eax+0x4971a0]   ; 买家**旧**持股数
00425681  fmul  dword [edi+eax+0x4971a4]   ; × 旧均价（**32 位 float**）
00425688  call  0x457dbc                    ; __round_toward_zero
0042568d  fistp dword [esp]                 ; ★ oldTotal（**先取整**）
00425692  edx = u16 [ebx+0x4967e8]          ; 成交股数
00425699  add   dword [edi+eax+0x4971a0], edx   ; ★ 买家持股 += 股数
004256a0  eax = (esi*4 - esi)*32 = esi*0x60 ; esi = arg1 = **卖家**
004256aa  eax += edi
004256ac  edi = [eax+0x4971a0]
004256b2  edi -= edx
004256b4  [eax+0x4971a0] = edi              ; ★ 卖家持股 −= 股数（u32，**不回绕夹紧**）
004256ba  jne  0x4256c2                     ; ★★ 复用 `sub` 的 ZF ⇒「卖家持股 ≠ 0 才跳过」
004256bc  [eax+0x4971a4] = edi              ;    清零时「均价 := 刚算出的 edi」（= 0）
004256c2  … 买家新均价 = (oldTotal + 挂牌价) / 买家新持股数（`fdivrp` + **`fstp dword`**）
```

★ 三条要点（全部由**内存差**直接实测）：

| # | 事实 | 对应复刻 |
|---|---|---|
| 1 | 买家持股 `+= 股数`、卖家 `−= 股数` | `transferListing` 的 `to.amount` / `from.amount` |
| 2 | ★ 卖家清零时**均价被写成 0** —— 因为 `0x4256bc` 存的是刚算出的 `edi`（已是 0），而非常量 | 注释写 `avgCost = 0`，语义等价；本条把「为什么是 0」钉在机器码上 |
| 3 | ★ 买家新均价 = `(trunc(旧持股×旧均价) + 挂牌价) / 买家新持股`，`oldTotal` **先取整**，结果是 **32 位 float** | `recalcAvgCost` 的 `Math.trunc` + `Math.fround` |

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x4294d5` | `xor eax,eax ; ret` | `_rich4_update_commercial_owner(player, stockId)`：地图企业归属重排，属**另一支**（`reduce.ts` 的 `updateCommercialOwner` 另有覆盖）；返回 0 = 没有企业要改归属 |
| `0x424502` / `0x4528b9` / `0x424620` | `ret` | 只有上面那个返回 1 且 `player+0x15==1` 时才走的三条提示/音效（表现层） |

★ 必须走**真入口** `0x4255da`（不是直接跳 `0x42565c`）—— 挂牌行地址
`0x4967e0+arg1*0x54+arg2*0xC` 由它算出来，而 `esi`/`ebp` 是**另外两个**参数
（`esi` 才是卖家那一路的下标）。直接进去 `ebx` 会是 0 ⇒ 读到别的挂牌行（踩过）。
停址取 `0x42575c`（股票支汇入公共尾段），此后是绘制/音效，不驱动。

跑法：cd rich4-spec && .venv/bin/python tests/test_stock_transfer.py
"""
from __future__ import annotations

import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

ENTRY = 0x4255DA
FN = 0x42565C                   # 股票支（跳表第 0 项）
# ★ 停址取 `0x4258b9`（**函数尾声的第一条**：`add esp,8`）：股票支与「现金不够」
#   那条提前退出**都汇到这里**，故两条路径都能停住（取更早的 0x42575c 会漏掉后者）。
STOP = 0x4258B9
TABLE = 0x4255CA
LIST_BASE = 0x4967E0            # ★ 挂牌表就在真实 DGROUP 里（`ebx` 是它的**绝对地址**）
LIST_STRIDE = 0x54
CURRENT_PLAYER = 0x49910C
P_CASH = 0x496B84               # 玩家 +0x1c 现金
P_BANK = 0x496B80
STOCK_TABLE = 0x496980          # _stocks_on_map，步长 0x24
STOCK_WORLD_OFF = 0x04          # +4 = u16 在地图上的企业号（0 = 无）
STOCKS_BASE = 0x4971A0          # _rich4_player_stocks
REC_STRIDE = 0x60               # ★ 玩家步长（`(p*4-p)*32` = p*0x60，实测）
STOCK_STRIDE = 8                # 股票步长
FRAME_BASE = 0x53E000
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<30} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def _install(self, e):
        e.patch(0x4294D5, b"\x31\xC0\xC3")
        for va in (0x424502, 0x4528B9, 0x424620):
            e.patch(va, b"\xC3")

    def run(self, *, buyer=0, seller=1, stock_id=5,
            buyer_amount=0, buyer_avg=0.0,
            seller_amount=0, seller_avg=0.0,
            amount=0, price=0, kind=1, cash=10_000_000, world=0):
        emu = Emu()
        off = seller * LIST_STRIDE

        def setup(e):
            self._install(e)
            e.write32(CURRENT_PLAYER, buyer)
            # ★ 现金在**玩家记录**里（+0x1c），故要按 buyer 下标写
            e.write32(P_CASH + buyer * 0x68, cash)
            e.write32(P_BANK + buyer * 0x68, cash)
            e.write8(LIST_BASE + off + 0x00, kind)
            e.write16(LIST_BASE + off + 0x02, stock_id)
            e.write32(LIST_BASE + off + 0x04, price)
            e.write16(LIST_BASE + off + 0x08, amount)
            e.write16(STOCK_TABLE + stock_id * 0x24 + STOCK_WORLD_OFF, world)
            b = STOCKS_BASE + buyer * REC_STRIDE + stock_id * STOCK_STRIDE
            e.write32(b, buyer_amount)
            e.write32(b + 4, struct.unpack("<I", struct.pack("<f", buyer_avg))[0])
            s = STOCKS_BASE + seller * REC_STRIDE + stock_id * STOCK_STRIDE
            e.write32(s, seller_amount)
            e.write32(s + 4, struct.unpack("<I", struct.pack("<f", seller_avg))[0])
            # `0x4255da` 的实参（帧：push×4 + sub esp,8）
            e.write32(FRAME_BASE + 4, seller)
            e.write32(FRAME_BASE + 8, 0)
        emu.eval_block(ENTRY, STOP, regs={"esp": FRAME_BASE},
                       setup=setup, timeout_insns=200000)
        self.emu = emu
        return self

    def holding(self, player, stock_id):
        a = STOCKS_BASE + player * REC_STRIDE + stock_id * STOCK_STRIDE
        return (self.emu.readu32(a),
                struct.unpack("<f", self.emu.read(a + 4, 4))[0])


def main():
    print("差分测试 #53：股市「股票」交易支 0x42565c\n")

    print("[A] 跳表 `0x4255ca`（4 项 = 股票 / 不动产 / 道具 / 卡片）")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(4)]
    case("4 项入口逐项相同", got, [0x42565C, 0x42577D, 0x4257D2, 0x425841])

    print("\n[B] 数量：买家 `+= 股数`、卖家 `−= 股数`")
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=100, buyer_avg=10.0,
                seller_amount=50, seller_avg=20.0, amount=20, price=100)
    case("买家 100 → 120", f.holding(0, 5)[0], 120)
    case("卖家 50 → 30", f.holding(1, 5)[0], 30)

    f = F().run(buyer=1, seller=0, stock_id=11, buyer_amount=0, buyer_avg=0.0,
                seller_amount=7, seller_avg=4.5, amount=7, price=50)
    case("★ 买空全部（卖家 7 → 0）", f.holding(0, 11)[0], 0)
    case("★ 大下标组合取址仍准（buyer=1 / stock 11 ⇒ 买家得 7）",
         f.holding(1, 11)[0], 7)

    print("\n[C] 均价：卖家清零才归零；买家按「先取整再相加」重算")
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=0, buyer_avg=0.0,
                seller_amount=20, seller_avg=20.0, amount=20, price=100)
    case("★ 卖家卖光 ⇒ 均价归 0（`0x4256bc`）", f.holding(1, 5), (0, 0.0))
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=0, buyer_avg=0.0,
                seller_amount=50, seller_avg=20.0, amount=20, price=100)
    case("★ 卖家没卖光 ⇒ 均价**原样保留**（50−20=30）", f.holding(1, 5), (30, 20.0))
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=100, buyer_avg=10.0,
                seller_amount=50, seller_avg=20.0, amount=20, price=100)
    case("买家新均价 = (100×10+100)/120 = 1100/120（f32）",
         f.holding(0, 5)[1], struct.unpack("<f", struct.pack("<f", 1100 / 120))[0])

    print("\n[D] ★ `oldTotal` 先向零取整：逐例比对复刻 `recalcAvgCost` 口径")
    for ba, bavg, amount, price in ((100, 10.0, 20, 100), (0, 0.0, 1, 7),
                                    (7, 3.3, 3, 11), (1000, 12.345, 7, 99),
                                    (123, 17.77, 5, 1000), (1, 0.9, 1, 0)):
        f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=ba, buyer_avg=bavg,
                    seller_amount=1000, seller_avg=1.0, amount=amount, price=price)
        old_total = math.trunc(ba * bavg)
        want = struct.unpack("<f", struct.pack("<f", (old_total + price) / (ba + amount)))[0]
        case(f"({ba}, {bavg}) +{amount}股 @{price} ⇒ ({ba+amount}, {want})",
             f.holding(0, 5), (ba + amount, want))

    print("\n[E] 闸门：现金 < 挂牌价 ⇒ 一笔都不动（走「钱不够」提示）")
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=100, buyer_avg=10.0,
                seller_amount=50, seller_avg=20.0, amount=20, price=1000, cash=999)
    case("现金 999 < 价 1000 ⇒ 双方持仓都不动",
         (f.holding(0, 5), f.holding(1, 5)), ((100, 10.0), (50, 20.0)))
    f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=100, buyer_avg=10.0,
                seller_amount=50, seller_avg=20.0, amount=20, price=1000, cash=1000)
    case("★ 现金恰好 == 价 ⇒ **成交**（`jge` 而非 `jg`）", f.holding(0, 5)[0], 120)

    print("\n[F] kind 越界（5 / 6 / 0xFF）⇒ 走公共尾段、持仓不动")
    for kind in (5, 6, 0xFF):
        f = F().run(buyer=0, seller=1, stock_id=5, buyer_amount=100, buyer_avg=10.0,
                    seller_amount=50, seller_avg=20.0, amount=20, price=100, kind=kind)
        case(f"kind={kind} ⇒ 持仓不动", (f.holding(0, 5), f.holding(1, 5)),
             ((100, 10.0), (50, 20.0)))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
