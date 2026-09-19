#!/usr/bin/env python3
"""
通道 2 差分测试 · calculate_player_wealth (VA 0x004239b9)

用 Unicorn 执行**原版机器码**，验证总资产公式。

规格来源：`docs/systems/economy.md`（对照该文件逐条比对）+ `gen/db.txt`。

算法（实测自 `0x004239b9` - `0x00423ace`）

```
wealth(player) =                      ; player 为 **0 基下标**
      cash[player] + bank[player] - loan[player]
    + Σ_{s=0..11} round( stocks[player][s].amount * price_on_map[s] )   ; ★ 浮点累加
    + Σ_{每块 land, owner == player+1}
          + land_price                            ; 总是加
          + (type != 0) ? house_price             ; type 非 0
                        : (level != 0 ? level * house_price : 0)
    + Σ_{每块 commercial, owner == player+1}
          level * w[+0x24] + w[+0x22]
```

关键事实：
  · 玩家结构步长 **0x68**；`cash@+0x1c`、`bank@+0x20`、`loan@+0x24`
  · **`owner` 是 1 基**（与 `land-rent.md` 一致）
  · 股票用 **x87 浮点**（`fild` 整数装入 × `fmul` 单精度股价），每步 `call 0x457dbc`
    （疑似 `__round_toward_zero`）后 `fistp` 取整
  · 12 支股票固定遍历，与"本局开哪几只"无关
  · 地产步长 **0x34**，商業用地步长 **0x38**

跑法：cd rich4-spec && .venv/bin/python tests/test_wealth.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SEGMENTS  # noqa: E402

WEALTH = 0x4239B9

PLAYER_BASE = 0x496B68
PLAYER_STRIDE = 0x68
CASH, BANK, LOAN = 0x1C, 0x20, 0x24

STOCK_PLAYER_BASE = 0x4971A0      # + player*0x60 + stock*8
STOCK_STRIDE_PLAYER = 0x60
STOCK_PRICE_BASE = 0x496994       # + index*0x24（单精度）
# ⚠️ 股价表步长是 **0x24**，不是 4。
#    原版寻址：`shl eax,3` → `add eax,edx` → `[eax*4 + 0x496994]`
#    即 (8*idx + idx)*4 = 9*idx*4 = idx*0x24。初版按 4 写，导致股票市值恒为 0。
STOCK_PRICE_STRIDE = 0x24

LAND_PTR = 0x498E84
NUM_LANDS = 0x498E98
COM_PTR = 0x498E88
NUM_COMS = 0x498E8C

LAND_STRIDE = 0x34
COM_STRIDE = 0x38

# 把合成数据放在 DGROUP 之后的空闲区（可写、且在快照内，便于 reset 一致）
LAND_BUF = 0x480000
COM_BUF = 0x480800
STOCK_BUF = 0x481000               # 12 支 × 8 字节

RESULTS = []


class F:
    def __init__(self):
        self.emu = Emu()

    def put(self, va, data):
        self.emu.mu.mem_write(va, bytes(data))

    def u32(self, va):
        return struct.unpack("<I", self.emu.mu.mem_read(va, 4))[0]

    def i32(self, va):
        return struct.unpack("<i", self.emu.mu.mem_read(va, 4))[0]

    def f32(self, va):
        return struct.unpack("<f", self.emu.mu.mem_read(va, 4))[0]

    def set_player(self, idx, cash=0, bank=0, loan=0):
        b = PLAYER_BASE + idx * PLAYER_STRIDE
        self.put(b + CASH, struct.pack("<i", cash))
        self.put(b + BANK, struct.pack("<i", bank))
        self.put(b + LOAN, struct.pack("<i", loan))

    def set_stock(self, player, stock, amount, price):
        """按原版的寻址方式写：玩家股票区 + 价格表。"""
        # 原版：ecx=player*0x60；eax=stock；地址= ecx + eax*8 + 0x4971a0
        base = STOCK_PLAYER_BASE + player * STOCK_STRIDE_PLAYER + stock * 8
        self.put(base, struct.pack("<i", amount))
        self.put(STOCK_PRICE_BASE + stock * STOCK_PRICE_STRIDE, struct.pack("<f", price))

    def set_land(self, idx, owner, typ, level, land_price, house_price):
        b = LAND_BUF + idx * LAND_STRIDE
        self.put(b + 0x18, [typ])
        self.put(b + 0x19, [owner])
        self.put(b + 0x1A, [level])
        self.put(b + 0x1C, struct.pack("<H", land_price))
        self.put(b + 0x1E, struct.pack("<H", house_price))

    def set_com(self, idx, owner, level, w22, w24):
        """⚠️ 与住宅一样，**数组从下标 1 开始用**（原版循环前先 `add eax,0x38`）。
        因此 idx 是 1 基，idx=1 写在 COM_BUF + 0x38。"""
        b = COM_BUF + idx * COM_STRIDE
        self.put(b + 0x19, [owner])
        self.put(b + 0x1A, [level])
        self.put(b + 0x22, struct.pack("<H", w22))
        self.put(b + 0x24, struct.pack("<H", w24))

    def clear_stocks(self):
        """清零股票数量区与股价表。

        ⚠️ 必须在**写玩家/股票数据之前**调用。第一版把它放在 commit() 里，
        于是"写完股票 → commit 清零 → 市值消失"，表现为股票恒为 0。
        顺序应当是：clear_stocks() → set_*() → commit()。
        """
        for pl in range(4):
            base = STOCK_PLAYER_BASE + pl * STOCK_STRIDE_PLAYER
            self.put(base, b"\x00" * (12 * 8))
        for s in range(12):
            self.put(STOCK_PRICE_BASE + s * STOCK_PRICE_STRIDE, struct.pack("<f", 0.0))

    def reset_world(self):
        """把全部**可变游戏状态**恢复成零，避免用例之间互相污染。

        踩过的坑：股票用例留下的 1017 市值泄漏进后续地产/商業用例，
        表现为"期望 0 却得到 1017"。每个用例组开始前都应调用本方法。
        """
        self.put(PLAYER_BASE, b"\x00" * (4 * PLAYER_STRIDE))
        for pl in range(4):
            for st in range(12):
                self.put(STOCK_PLAYER_BASE + pl * STOCK_STRIDE_PLAYER + st * 8,
                         struct.pack("<i", 0))
        for st in range(12):
            self.put(STOCK_PRICE_BASE + st * STOCK_PRICE_STRIDE, struct.pack("<f", 0.0))
        self.put(LAND_BUF, b"\x00" * 0x400)
        self.put(COM_BUF, b"\x00" * 0x400)
        self.put(LAND_PTR, struct.pack("<I", LAND_BUF))
        self.put(COM_PTR, struct.pack("<I", COM_BUF))
        self.put(NUM_LANDS, struct.pack("<I", 0))
        self.put(NUM_COMS, struct.pack("<I", 0))

    def commit(self, num_lands=0, num_coms=0, clear_stocks=False):
        """把注入数据并入快照并设定全局。

        ⚠️ 陷阱（本测试第一版踩过）：**股票区与玩家区内存相邻**。
        原版寻址 `player*0x60 + stock*8 + 0x4971A0` 在 player=1 时就落在
        0x497200，而 `0x4971A0 + 0x200` 的清零范围会**顺手抹掉玩家 1 的
        cash/bank/loan** —— 表现是"player=1 的资产恒为 0"。
        因此这里只在需要时**按玩家精确**清零，绝不整片擦除。
        """
        self.put(LAND_PTR, struct.pack("<I", LAND_BUF))
        self.put(NUM_LANDS, struct.pack("<I", num_lands))
        self.put(COM_PTR, struct.pack("<I", COM_BUF))
        self.put(NUM_COMS, struct.pack("<I", num_coms))
        if clear_stocks:
            self.clear_stocks()
        self.emu._snapshot = {va: self.emu.mu.mem_read(va, sz)
                              for va, off, sz, w in SEGMENTS if w}

    def wealth(self, idx):
        return self.emu.call(WEALTH, [idx])["signed"]


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<46} 实际 {got:<10} 期望 {want}")
    return ok


def main():
    print("差分测试：calculate_player_wealth(VA 0x004239b9)\n")
    f = F()

    print("[规格] wealth = cash + bank - loan")
    f.reset_world()
    f.set_player(0, cash=1000, bank=500, loan=200)
    f.commit()
    case("cash1000 bank500 loan200", f.wealth(0), 1300)

    print("\n[规格] 支持负的贷款（负债）")
    f.reset_world()
    f.set_player(0, cash=100, bank=0, loan=5000)
    f.commit()
    case("cash100 bank0 loan5000", f.wealth(0), -4900)

    print("\n[规格] 下标是 0 基：改 player=1 不应影响 player=0 的结果")
    # 故意不 reset：本组要验证的就是"改 player=1 不影响 player=0"
    f.set_player(1, cash=7777, bank=0, loan=0)
    f.commit()                       # 重拍快照，保留上面刚写的玩家 1 数据
    case("player=0 仍为 -4900", f.wealth(0), -4900)
    case("player=1 = 7777", f.wealth(1), 7777)

    print("\n[规格] 股票：Σ round(数量 × 股价)，12 支固定遍历")
    f.reset_world()
    f.set_player(0, cash=0)
    f.set_stock(0, 0, amount=100, price=10.0)     # 1000
    f.set_stock(0, 3, amount=7, price=2.5)        # 17.5 → 取整
    f.commit()
    got = f.wealth(0)
    # 用同一取整规则（向零截断）计算期望
    import math
    exp = int(100 * 10.0) + int(7 * 2.5)
    case(f"100×10.0 + 7×2.5（期望按向零截断 {exp}）", got, exp)

    print("\n[规格] 地产：总是加 land_price；type!=0 加 house_price，否则 level≠0 加 level×house_price")
    f.reset_world()
    f.set_player(0, cash=0)
    f.set_land(0, 0, 0, 0, 0, 0)
    f.set_land(1, owner=1, typ=0, level=0, land_price=100, house_price=50)   # +100
    f.commit(num_lands=1)
    case("主人=1, type0 level0: +地价100", f.wealth(0), 100)

    f.set_land(1, owner=1, typ=0, level=3, land_price=100, house_price=50)   # 100+150
    f.commit(num_lands=1)
    case("type0 level3: 100 + 3×50", f.wealth(0), 250)

    f.set_land(1, owner=1, typ=1, level=1, land_price=100, house_price=50)   # 100+50
    f.commit(num_lands=1)
    case("type1 level1: 100 + 50", f.wealth(0), 150)

    print("\n[规格] owner 是 1 基：owner=2 属于 player=1，不计入 player=0")
    f.reset_world()
    f.set_player(1, cash=7777, bank=0, loan=0)
    f.set_land(1, owner=2, typ=0, level=0, land_price=999, house_price=0)
    f.commit(num_lands=1)
    case("owner=2 不计入 player=0", f.wealth(0), 0)
    # player=1 此时仍有上面写过的 cash=7777
    case("owner=2 计入 player=1（7777+999）", f.wealth(1), 7777 + 999)

    print("\n[规格] 商業用地：+ level × w[+0x24] + w[+0x22]")
    f.reset_world()
    f.set_com(1, owner=1, level=2, w22=30, w24=10)     # 2*10+30 = 50
    f.commit(num_coms=0)
    case("num_coms=0 → 不计入", f.wealth(0), 0)
    f.commit(num_coms=1)
    case("level2 w22=30 w24=10 → 50", f.wealth(0), 50)

    print("\n[规格] 股票每步的取整是 **向零截断**（0x457dbc 把 FPU 控制字设为 0x1f）")
    # .5 边界用例足以区分"向零截断"与"就近舍入"；含负数以排除"向下取整"
    for q, price, want in ((3, 0.5, 1), (7, 2.5, 17), (1, 1.5, 1),
                           (-1, 1.5, -1), (-1, 2.5, -2), (1, 0.5, 0)):
        f.reset_world()
        f.set_player(0, cash=0)
        f.set_stock(0, 0, amount=q, price=price)
        f.commit()
        case(f"{q} × {price} → 截断 {want}", f.wealth(0), want)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
