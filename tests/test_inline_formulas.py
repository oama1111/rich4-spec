#!/usr/bin/env python3
"""
通道 2 差分测试 #7 · **内联公式区块**（非函数入口）

原版里大量规则公式是**内联展开**的，没有 `call` 入口，`Emu.call()` 驱动不了。
本用例用新加的 `Emu.eval_block(start, stop, regs, setup)`（寄存器约定 + 停址）
直接求值这些区块，覆盖 5 条此前只能靠"读汇编 + 手算"的公式：

  1. 地產市价  `0x4265a6`→`0x426605`   (地价 + 等级×房价) × 物价指数
  2. 設施市价  `0x4265cb`→`0x426605`   (底价 + 等级×单价) × 物价指数
  3. 所得税    `0x449cee`→`0x449d18`   trunc(现金 × 0.05)  → 每玩家数组 0x48c59c
  4. 儲金紅利  `0x44af44`→`0x44af5c`   trunc(存款 × 0.1)
  · 第 6/7 条的標價表是**镜像里的真数据**（`0x47fdea` 起、8 字节一条、`+5` 是標價）：
    **卡与道具共用同一张表** —— 道具 `0x47fedf` = `0x47fdef` + 0xF0 = 第 **30** 条记录，
    即 0..29 是卡片、30..44 是道具（15 种）。故这两条**不注入**表数据，直接读真值；
    只有物价指数 `0x4990e8`（.bss）需要注入。
  · 第 8 条的股价表 `0x496994`（步长 `0x24`）也在 .bss，须注入 **float32**。
     ⚠️ 本条只差分**乘法与截断**；「loan ≠ 0 则跳过」的闸门在 `0x44af3c`
        （`mov ebp,[ebx+0x496b8c]; test ebp,ebp; jne 0x44b004`），位于被测区块
        **之前**，且其跳转目标在停址之外 —— 故该闸门目前是**静态 A 级**
        （无条件分支真值），不是差分结论。月息那条的闸门则在区块**之内**，已差分。
  5. 存款月息  `0x4381f8`→`0x438218`   trunc(存款 × 1.1)，且**贷款(+0x24)≠0 时不计息**
  6. 道具市价  `0x426af2`→`0x426b09`   標價 × 100 × 物价指数（结果在 **ebx**）
  7. 卡片市价  `0x426f0f`→`0x426f2b`   標價 × 100 × 物价指数（结果在 **ebx**）
  8. 股票市价  `0x425f1e`→`0x425f38`   trunc(股數 × 現價)，現價是 **float32**
  9. 挂牌价上限 `0x426627`→`0x426630`  市价 × 10（四类挂牌共用同一形状）
 10. 股票段累加 **两条**循环，都用 float32 存回合计数：
     · 證交稅基数 `0x44a0c6`→`0x44a110`  `fstp dword [esp+ebx*4+0x94]`（**跳过空仓**）
     · 总资产股票段 `0x4239e0`→`0x423a20`  `fstp dword [esp+4]`（**12 轮一轮不落**）

关键事实（静态读码 + 本用例验证）：
  · `0x457dbc` = **`frndint` 助手**：`fnstcw` → 把控制字高字节改成 `0x1f`
    → `fldcw` → `frndint` → 还原。`0x1f` 高字节 ⇒ RC=11 **向零截断**、PC=11 扩展精度。
    所以这些公式的取整语义是 **trunc（向零）**，不是四舍五入。
  · `frndint` 只改 ST(0)，**不动 eax**；结果由紧随其后的 `fistp` 落到内存
    （所得税/紅利落 `[esp+0x94]` 局部量，月息直接落回 `player+0x496b88`）。
    初版误以为结果在 eax，得到"恒为 0"的假象。
  · 地产/商業用地表基址在 **.bss**（`0x498e84`/`0x498e88` 加载时为 0），
    物价指数 `0x4990e8` 同理 —— 必须由用例注入，且注入要放在 `setup` 回调里
    （`eval_block` 内的 `reset()` 会把直接写入的 DGROUP 抹掉）。

⚠️ harness 保真度（本轮发现并修复）：
  Unicorn 的 x87 初始控制字与真实进程不同（PC=单精度 24 位尾数），且该状态
  **不随内存快照还原** —— 表现为"同一实例里第二次求值给出不同结果"：
  `trunc(2147483644×0.05)` 首次 107374182（正确）、第二次 107374184。
  修法见 `Emu.reset_fpu()`（每次求值前写回真实进程默认 `0x027F`）。
  本文件末尾专门锁死这个回归。

跑法：cd rich4-spec && .venv/bin/python tests/test_inline_formulas.py
"""
import math
import os
import struct
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, STACK_TOP  # noqa: E402

# ── 区块地址 ──
LAND_VAL, COM_VAL, VAL_STOP = 0x4265A6, 0x4265CB, 0x426605
TAX, TAX_STOP = 0x449CEE, 0x449D18
DIVIDEND, DIV_STOP = 0x44AF44, 0x44AF5C
INTEREST, INT_STOP = 0x4381F8, 0x438218

# ── 全局量 ──
LAND_PTR, COM_PTR, PRICE_INDEX = 0x498E84, 0x498E88, 0x4990E8
LAND_STRIDE, COM_STRIDE = 0x34, 0x38
TAX_ARRAY = 0x48C59C                # + player*4
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
CASH, BANK, LOAN = 0x1C, 0x20, 0x24
F_CONST_TAX, F_CONST_DIV, F_CONST_INT = 0x4655A4, 0x465734, 0x464E88

STOCK_SUM_LOOP, STOCK_SUM_STOP = 0x44A0C6, 0x44A110      # 證交稅基数（float32 累加）
WEALTH_STOCK_LOOP, WEALTH_STOCK_STOP = 0x4239E0, 0x423A20  # 总资产的股票段
HOLD_BASE, HOLD_PLAYER_STRIDE = 0x4971A0, 0x60
SUM_LOCAL, IDX_LOCAL = 0x94, 0xA4          # 證交稅基数槽 / 循环下标（相对 esp）

TOOL_PRICE, TOOL_STOP = 0x426AF2, 0x426B09      # 结果在 ebx
CARD_PRICE, CARD_STOP = 0x426F0F, 0x426F2B      # 结果在 ebx
STOCK_PRICE, STOCK_STOP = 0x425F1E, 0x425F38    # 结果在 [esp+0xd0]
ESTATE_X10, X10_STOP = 0x426627, 0x426630       # 结果在 eax = esi*10

RECORD = 0x47FDEA          # 标价表记录基址（8 字节/条：+0..3 name_ptr, +4 init, +5 price, +6 f6, +7 f7）
CARD_TABLE = RECORD + 5    # = 0x47fdef：卡片 0 的標價
TOOL_TABLE = RECORD + 5 + 30 * 8   # = 0x47fedf：道具 0 = 第 30 条记录
CARD_COUNT, TOOL_COUNT = 30, 15
STOCK_TABLE, STOCK_STRIDE = 0x496994, 0x24
STACK_LOCAL_SHARES, STACK_LOCAL_OUT = 0xD8, 0xD0

SCRATCH = 0x600000                  # 注入用的假表基址

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<52} 实际 {got_s!s:<12} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    # ── 1/2 地产 / 設施估价 ──
    def _setup_tables(self, emu, price_index=1):
        emu.scratch_write(SCRATCH, bytes(COM_STRIDE * 4))
        emu.write32(LAND_PTR, SCRATCH)
        emu.write32(COM_PTR, SCRATCH)
        emu.write32(PRICE_INDEX, price_index)

    def land_value(self, land_id, level, land_price, house_price, price_index=1):
        def setup(emu):
            self._setup_tables(emu, price_index)
            off = (land_id - 2000) * LAND_STRIDE
            emu.write8(SCRATCH + off + 0x1A, level)
            emu.write16(SCRATCH + off + 0x1C, land_price)
            emu.write16(SCRATCH + off + 0x1E, house_price)
        r = self.emu.eval_block(LAND_VAL, VAL_STOP, {"ebx": land_id}, setup=setup)
        return r["regs"]["esi"]

    def com_value(self, com_id, level, base_price, unit_price, price_index=1):
        def setup(emu):
            self._setup_tables(emu, price_index)
            off = (com_id - 4000) * COM_STRIDE
            emu.write8(SCRATCH + off + 0x1A, level)
            emu.write16(SCRATCH + off + 0x22, base_price)
            emu.write16(SCRATCH + off + 0x24, unit_price)
        r = self.emu.eval_block(COM_VAL, VAL_STOP, {"ebx": com_id}, setup=setup)
        return r["regs"]["esi"]

    # ── 3 所得税 ──
    def tax(self, player, cash):
        def setup(emu):
            emu.write32(PLAYER_BASE + player * PLAYER_STRIDE + CASH, cash)
            emu.write32(TAX_ARRAY + player * 4, -1)
        r = self.emu.eval_block(TAX, TAX_STOP,
                                {"edx": player * PLAYER_STRIDE, "ebx": player},
                                setup=setup)
        local = self.emu.read32(r["regs"]["esp"] + 0x94)
        arr = self.emu.read32(TAX_ARRAY + player * 4)
        return local, arr

    # ── 4 儲金紅利 ──
    def dividend(self, player, bank):
        def setup(emu):
            emu.write32(PLAYER_BASE + player * PLAYER_STRIDE + BANK, bank)
        r = self.emu.eval_block(DIVIDEND, DIV_STOP,
                                {"ebx": player * PLAYER_STRIDE}, setup=setup)
        return self.emu.read32(r["regs"]["esp"] + 0x94)

    # ── 6/7 道具 / 卡片市价（標價 × 100 × 物价指数，结果在 ebx） ──
    def _price_block(self, entry, stop, item_id, price_index):
        def setup(emu):
            emu.write32(PRICE_INDEX, price_index)
        # `mov al, dh` ⇒ 编号走 **dh**（edx 的高字节）
        r = self.emu.eval_block(entry, stop, {"edx": (item_id & 0xFF) << 8}, setup=setup)
        return r["regs"]["ebx"]

    def tool_price(self, tool_id, price_index=1):
        return self._price_block(TOOL_PRICE, TOOL_STOP, tool_id, price_index)

    def card_price(self, card_id, price_index=1):
        return self._price_block(CARD_PRICE, CARD_STOP, card_id, price_index)

    def listed_price(self, tool_id):
        """直接从镜像读標價：道具 = 共用表第 30+id 条记录。"""
        return self.emu.read8(TOOL_TABLE + tool_id * 8)

    def card_listed_price(self, card_id):
        return self.emu.read8(CARD_TABLE + card_id * 8)

    # ── 8 股票市价（trunc(股數 × 現價)，現價 float32） ──
    def stock_price(self, shares, stock_index, price):
        def setup(emu):
            emu.write32(STOCK_TABLE + stock_index * STOCK_STRIDE, 0)  # 先清 4 字节
            emu.write(STOCK_TABLE + stock_index * STOCK_STRIDE,
                      struct.pack("<f", price))
            emu.write32(STACK_TOP + STACK_LOCAL_SHARES, shares)
        r = self.emu.eval_block(STOCK_PRICE, STOCK_STOP,
                                {"eax": stock_index * 9, "edx": stock_index},
                                setup=setup)
        return self.emu.read32(r["regs"]["esp"] + STACK_LOCAL_OUT)

    # ── 9 挂牌价上限 = 市价 × 10 ──
    def times_ten(self, market_price):
        r = self.emu.eval_block(ESTATE_X10, X10_STOP, {"esi": market_price})
        return r["regs"]["eax"]

    # ── 10 股票段的两条累加循环（原版都用 float32 存回） ──
    def _setup_stocks(self, emu, player, holdings, prices):
        for i in range(12):
            emu.write32(HOLD_BASE + player * HOLD_PLAYER_STRIDE + i * 8, int(holdings[i]))
            emu.write(STOCK_TABLE + i * STOCK_STRIDE, struct.pack("<f", prices[i]))

    def stock_accum(self, holdings, prices, player=0):
        """證交稅基数：`0x44a0c6`..`0x44a110`，每步 `fstp dword` 把合计数存回 float32。"""

        def setup(emu):
            self._setup_stocks(emu, player, holdings, prices)
            emu.write32(STACK_TOP + IDX_LOCAL, 0)
            emu.write(STACK_TOP + player * 4 + SUM_LOCAL, struct.pack("<f", 0.0))

        self.emu.eval_block(STOCK_SUM_LOOP, STOCK_SUM_STOP, {"ebx": player}, setup=setup)
        raw = self.emu.read(STACK_TOP + player * 4 + SUM_LOCAL, 4)
        return struct.unpack("<f", raw)[0]

    def wealth_stock_total(self, total0, holdings, prices, player=0):
        """总资产的股票段：`0x4239e0`..`0x423a20`，12 轮**一轮不落**。"""

        def setup(emu):
            self._setup_stocks(emu, player, holdings, prices)
            emu.write32(STACK_TOP, total0)        # [esp] = 运行中的整数总资产
            emu.write32(STACK_TOP + 4, 0)

        self.emu.eval_block(WEALTH_STOCK_LOOP, WEALTH_STOCK_STOP,
                            {"ebx": player, "edx": 0}, setup=setup)
        return self.emu.read32(STACK_TOP)

    # ── 5 存款月息（含贷款闸门） ──
    def interest(self, player, bank, loan=0):
        def setup(emu):
            emu.write32(PLAYER_BASE + player * PLAYER_STRIDE + BANK, bank)
            emu.write32(PLAYER_BASE + player * PLAYER_STRIDE + LOAN, loan)
        self.emu.eval_block(INTEREST, INT_STOP,
                            {"eax": player * PLAYER_STRIDE}, setup=setup)
        return self.emu.read32(PLAYER_BASE + player * PLAYER_STRIDE + BANK)

    def f64(self, va):
        return self.emu.f64(va)


def f32(x):
    """舍入到 float32（= 原版的 `fstp dword`，`RC` 为就近舍入）。"""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def trunc_exact(x, num, den):
    """精确模型：trunc(x × num/den)，用有理数避免 Python 浮点二次误差。"""
    return math.trunc(Fraction(x) * Fraction(num, den))


def main():
    print("差分测试 #7：内联公式区块（估价 / 税率 / 利率）\n")
    f = F()

    print("[常量] 直接解码镜像里的 f64 常量（A 级：二进制真值）")
    case("所得税乘数 @0x4655a4 == 0.05", f.f64(F_CONST_TAX), 0.05)
    case("儲金紅利乘数 @0x465734 == 0.1", f.f64(F_CONST_DIV), 0.1)
    case("存款月息乘数 @0x464e88 == 1.1", f.f64(F_CONST_INT), 1.1)

    print("\n[1] 地產市价 = (地价 + 等级×房价) × 物价指数")
    case("地价1000 等级0 房价200 指数1", f.land_value(2000, 0, 1000, 200), 1000)
    case("地价1000 等级5 房价200 指数1", f.land_value(2000, 5, 1000, 200), 2000)
    case("指数3 同上", f.land_value(2000, 5, 1000, 200, 3), 6000)
    case("指数0 → 0（乘数为 0）", f.land_value(2000, 5, 1000, 200, 0), 0)
    case("空地 地价0 等级9 房价150", f.land_value(2001, 9, 0, 150), 1350)
    case("下标 3 走 (id-2000)×0x34",
         f.land_value(2003, 7, 800, 150, 3), 3 * (800 + 7 * 150))
    case("u16 地价上限 65535 等级1 房价1",
         f.land_value(2000, 1, 65535, 1), 65536)
    case("等级上限 255 房价 200", f.land_value(2000, 255, 0, 200), 51000)

    print("\n[2] 設施市价 = (底价 + 等级×单价) × 物价指数")
    case("底价5000 等级0 单价300", f.com_value(4000, 0, 5000, 300), 5000)
    case("底价5000 等级2 单价300", f.com_value(4000, 2, 5000, 300), 5600)
    case("指数3 同上", f.com_value(4000, 2, 5000, 300, 3), 16800)
    case("下标 2 走 (id-4000)×0x38",
         f.com_value(4002, 1, 700, 50, 2), 2 * (700 + 50))

    print("\n[3] 所得税 = trunc(现金 × 0.05)，写入每玩家数组 0x48c59c")
    for cash, want in ((1000, 50), (2000, 100), (99, 4), (101, 5), (19, 0),
                       (20, 1), (0, 0), (7, 0), (99999999, 4999999)):
        local, arr = f.tax(0, cash)
        case(f"现金 {cash} → {want}（且落数组）", (local, arr), (want, want))
    # 玩家下标：税额落 0x48c59c + player*4。
    # ⚠️ 不能跨两次 eval_block 累加观察：每次求值前的 reset() 会把 .bss 里的
    #    数组一并还原（0x48c59c 在快照内），所以断言必须在**同一次调用内**成立。
    f.tax(0, 3000)
    case("玩家 0：3000 → 150，落 0x48c59c+0", f.emu.read32(TAX_ARRAY), 150)
    case("玩家 0 的写入不碰 +8 槽", f.emu.read32(TAX_ARRAY + 8), 0)
    local, arr = f.tax(2, 777)
    case("玩家 2：777 → 38，落 0x48c59c+8", (local, arr), (38, 38))
    case("玩家 2 的写入不碰 +0 槽", f.emu.read32(TAX_ARRAY), 0)

    print("\n[4] 儲金紅利 = trunc(存款 × 0.1)")
    for bank, want in ((1000, 100), (2000, 200), (99, 9), (101, 10),
                       (5, 0), (0, 0), (99999999, 9999999)):
        case(f"存款 {bank} → {want}", f.dividend(0, bank), want)
    case("玩家 1：存款 4444 → 444", f.dividend(1, 4444), 444)

    print("\n[5] 存款月息 = trunc(存款 × 1.1)，贷款≠0 时**不计息**")
    for bank, want in ((1000, 1100), (0, 0), (100, 110), (105, 115),
                       (95, 104), (99999999, 109999998)):
        case(f"存款 {bank} 无贷款 → {want}", f.interest(0, bank), want)
    case("存款 1000 有贷款 1 → 原样 1000（不计息）",
         f.interest(0, 1000, loan=1), 1000)
    case("存款 1000 有贷款 50000 → 原样 1000",
         f.interest(0, 1000, loan=50000), 1000)
    case("玩家 3：存款 2000 → 2200", f.interest(3, 2000), 2200)

    print("\n[6] 道具市价 = 標價 × 100 × 物价指数（標價取自镜像真表）")
    print("    表结构：卡与道具**共用**一条 8 字节记录表，道具 = 第 30 条起")
    case("道具表基址 = 卡片表基址 + 30×8", TOOL_TABLE - CARD_TABLE, 30 * 8)
    for t in (0, 2, 8, 9, 14):
        want = f.listed_price(t) * 100
        case(f"道具{t} 標價{f.listed_price(t)} ×100 指数1 → {want}",
             f.tool_price(t, 1), want)
    case("道具0 標價 70 ×100 ×指数3", f.tool_price(0, 3), 70 * 100 * 3)
    case("道具2（路障，標價 30）×100 = 3000（对上截图 S13）",
         f.tool_price(2, 1), 3000)
    case("道具14 標價 3 ×100", f.tool_price(14, 1), 300)
    case("指数 0 → 0", f.tool_price(0, 0), 0)
    case("★ 表尾越界：道具15 读到记录 45（標價 0）", f.listed_price(15), 0)

    print("\n[7] 卡片市价 = 標價 × 100 × 物价指数")
    for c in (1, 9, 10, 15, 25, 29):
        want = f.card_listed_price(c) * 100
        case(f"卡片{c} 標價{f.card_listed_price(c)} ×100 指数1 → {want}",
             f.card_price(c, 1), want)
    case("卡片0 標價 0 → 0", f.card_price(0, 1), 0)
    case("卡片1 標價 200 ×100 ×指数2", f.card_price(1, 2), 200 * 100 * 2)
    case("卡片11 標價 60 ×100 = 6000（怪獸卡，與簇 C 同一条）",
         f.card_price(11, 1), 6000)
    # 两支公式只差表基址：同一编号在两张表上应给出不同结果，证明基址没写反
    case("同编号 0：道具=70×100 而卡片=0（基址未互换）",
         (f.tool_price(0, 1), f.card_price(0, 1)), (7000, 0))

    print("\n[8] 股票市价 = trunc(股數 × 現價)，現價是 float32")
    case("3 股 × 12.5 → 37", f.stock_price(3, 0, 12.5), 37)
    case("7 股 × 2.5 → 17（.5 截断）", f.stock_price(7, 0, 2.5), 17)
    case("1 股 × 1.5 → 1（排除四舍五入）", f.stock_price(1, 0, 1.5), 1)
    case("-1 股 × 1.5 → -1（排除向下取整）", f.stock_price(-1, 0, 1.5), -1)
    case("0 股 → 0", f.stock_price(0, 0, 999.5), 0)
    case("1000 股 × 0.1 → 100", f.stock_price(1000, 0, 0.1), 100)
    case("下标隔离：同一价格下 5 股在不同股票位各自成立",
         (f.stock_price(5, 1, 3.0), f.stock_price(5, 7, 3.0)), (15, 15))
    # float32 现价：0.1f 略大于 0.1 ⇒ 用大股数把差异放大到可观测
    case("float32(0.1) 与 double(0.1) 的差在万股级可观测",
         f.stock_price(100000, 0, 0.1), math.trunc(100000 * struct.unpack(
             "<f", struct.pack("<f", 0.1))[0]))
    case("1 亿股 × 0.1 仍取 float32 精确值", f.stock_price(100000000, 0, 0.1),
         math.trunc(100000000 * struct.unpack("<f", struct.pack("<f", 0.1))[0]))

    print("\n[9] 挂牌价上限 = 市价 × 10（四类挂牌同一形状：shl 2 / add / add）")
    for v in (0, 1, 7, 3000, 7000, 123456):
        case(f"{v} × 10 → {v * 10}", f.times_ten(v), v * 10)
    case("上限与市价的关系：道具2 市价 3000 → 上限 30000",
         f.times_ten(f.tool_price(2, 1)), 30000)
    # 3 亿 × 10 = 30 亿 > int32：`eax` 寄存器里是 0xB2D05E00。
    # harness 回读的是**无符号**寄存器值（3000000000），调用方按有符号解释就是 -1294967296。
    case("★ int32 溢出：3 亿 × 10 → 寄存器 0xB2D05E00", f.times_ten(300000000),
         0xB2D05E00)
    case("同上按有符号解释 = -1294967296", f.times_ten(300000000) - 2 ** 32,
         -1294967296)
    case("2 亿 × 10 = 20 亿仍在 int32 内", f.times_ten(200000000), 2000000000)

    print("\n[10] 股票段两条累加循环：原版都用 **float32 存回合计数**")
    print("     （x87 乘积本身是 53 位，与 JS 双精度一致；只有「存回」是 float32）")

    # ── 10a 證交稅基数：0x44a0c6 循环，每步 fstp dword ──
    H6 = [9572, 3546, 5541, 8967, 9430, 683, 0, 0, 0, 0, 0, 0]
    P6 = [141.9310760498047, 78.52230072021484, 284.5124816894531,
          57.75619888305664, 238.64231872558594, 113.8723373413086,
          0, 0, 0, 0, 0, 0]
    case("空仓 → 0", f.stock_accum([0] * 12, [0.0] * 12), 0.0)
    case("单支整数价 1000×12 = 12000", f.stock_accum([1000] + [0] * 11,
                                                 [12.0] + [0.0] * 11), 12000.0)
    got = f.stock_accum(H6, P6)
    case("★ 六支大额：原版 float32 累加 = 6059560", got, 6059560.0)
    naive = sum(h * p for h, p in zip(H6, P6))
    case("同一输入的**双精度**合计（应不同）", round(naive, 6), 6059559.706715)
    case("★ 差值落进證交稅：原版 302978 vs 双精度 302977",
         (math.trunc(got * 0.05), math.trunc(naive * 0.05)), (302978, 302977))
    # 模型对照：t = f32(t + h×p)（跳过空仓——证交税循环**有**跳过）
    model = 0.0
    for h, p in zip(H6, P6):
        model = f32(model + h * p)
    case("模型 t = f32(t + h×p) 与原版一致", got, model)

    # ── 10b 总资产的股票段：0x4239e0 循环，12 轮全跑 ──
    PRICE = struct.unpack("<f", struct.pack("<f", 10.35))[0]   # 股价表是 float32
    one = [1000] + [0] * 11
    pone = [PRICE] + [0.0] * 11
    case("起始 0 → 10350", f.wealth_stock_total(0, one, pone), 10350)
    case("起始 2^24（边界内）→ 16787566",
         f.wealth_stock_total(2 ** 24, one, pone), 16787566)
    case("★ 起始 2^24+1 → 16787566（纯双精度会给 16787567）",
         f.wealth_stock_total(2 ** 24 + 1, one, pone), 16787566)
    case("★ 起始 1e8 → 100010352（纯双精度 100010350）",
         f.wealth_stock_total(10 ** 8, one, pone), 100010352)
    case("★ 起始 123456789 → 123467144（纯双精度 123467139）",
         f.wealth_stock_total(123456789, one, pone), 123467144)
    case("★ 起始 999999999 → 1000010368（纯双精度 1000010349，差 19）",
         f.wealth_stock_total(999999999, one, pone), 1000010368)
    # 空仓也 12 轮全跑 ⇒ 总资产照样被量化
    case("★ 空仓 999999999 → 1000000000（照样量化）",
         f.wealth_stock_total(999999999, [0] * 12, [0.0] * 12), 1000000000)
    case("★ 空仓 2^24+1 → 16777216（**往下**舍）",
         f.wealth_stock_total(2 ** 24 + 1, [0] * 12, [0.0] * 12), 2 ** 24)
    case("空仓 123456789 → 123456792",
         f.wealth_stock_total(123456789, [0] * 12, [0.0] * 12), 123456792)
    case("空仓 1000 → 1000（小额不受影响）",
         f.wealth_stock_total(1000, [0] * 12, [0.0] * 12), 1000)

    print("\n[规格] 取整是 **向零截断**（0x457dbc 把 CW 高字节设为 0x1f ⇒ RC=11）")
    print("         .5/.9 边界 + 负值足以区分 截断 / 四舍五入 / 向下取整")
    case("trunc(99×0.05)=4（四舍五入会给 5）", f.tax(0, 99)[0], 4)
    case("trunc(-99×0.05)=-4（向下取整会给 -5）", f.tax(0, -99)[0], -4)
    case("trunc(19×0.05)=0（四舍五入会给 1）", f.tax(0, 19)[0], 0)
    case("trunc(99×0.1)=9（四舍五入会给 10）", f.dividend(0, 99), 9)
    case("trunc(-99×0.1)=-9（向下取整会给 -10）", f.dividend(0, -99), -9)
    case("trunc(105×1.1)=115（精确 115.5 → 不给 116）", f.interest(0, 105), 115)

    print("\n[回归] x87 控制字保真度：同一实例连续求值必须逐次一致")
    print("        （Unicorn 初始 CW 的 PC=单精度，会让大额结果被舍入到 24 位）")
    seq = [f.tax(0, v)[0] for v in (2147483640, 2147483644, 2147483647, 2147483647)]
    case("连续 4 次大额所得税", seq, [107374182, 107374182, 107374182, 107374182])
    case("trunc(2147483647×0.05) 精确模型对照", seq[-1], trunc_exact(2147483647, 1, 20))
    seq2 = [f.interest(0, v) for v in (1073741824, 1073741824)]
    case("连续 2 次大额月息（bank=2^30）", seq2, [1181116006, 1181116006])
    case("trunc(2^30×1.1) 精确模型对照", seq2[-1], trunc_exact(1073741824, 11, 10))
    seq3 = [f.dividend(0, v) for v in (99999999, 99999999)]
    case("连续 2 次大额紅利", seq3, [9999999, 9999999])

    print("\n[边界] `fistp dword` 溢出 int32 → x87「整数不定值」0x80000000（硬件行为）")
    case("bank=1952257861 → ×1.1=2147483647.1 → 恰好放得下",
         f.interest(0, 1952257861), 2147483647)
    case("bank=1952257862 → ×1.1=2147483648.2 → 溢出存 0x80000000",
         f.interest(0, 1952257862), -2147483648)
    case("bank=INT32_MAX → ×1.1=2362232011.7 → 溢出存 0x80000000",
         f.interest(0, 2147483647), -2147483648)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
