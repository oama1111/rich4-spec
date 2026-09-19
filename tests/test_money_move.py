#!/usr/bin/env python3
"""
通道 2 差分测试 #9 · 金钱转移的两个原语

  · `pay_money`      VA `0x0041d2c6`（302 字节 / 91 条）—— **全局唯一的付款通道**
  · `give_money`     VA `0x0041d3f4`（63 字节 / 19 条）—— 纯收款，与付款**不对称**

规格来源：`docs/systems/bank.md`、`docs/systems/news.md` §`0x496bc8`、
`docs/systems/gods.md` 的玩家字段表、`gen/db.txt`。

`pay_money(payer, payee, amount, flags)`（Watcom 栈调用，3 参 + flags）：

```
if payer > 100:  企業 = [0x498e7c] + (payer-100)*0x34
                 [企業+0x28] -= amount ; [企業+0x2c] -= amount ; goto 收款方
eax = payer*0x68
if flags & 4:    ★ 存款优先
     bank -= amount ; bank>=0 ? →统计
     cash += bank(负) ; bank = 0 ; cash>=0 ? →统计
     amount += cash(负) ; cash = 0 ; amount<0 时 amount = 0
else:            ★ 现金优先（默认）
     cash -= amount ; cash>=0 ? →统计
     bank += cash(负) ; cash = 0 ; bank>=0 ? →统计
     amount += bank(负) ; bank = 0 ; amount<0 时 amount = 0
   ★ 只有在「两边都被抽干**且仍不够**」时才 `call 0x40cd87(payer)`（破产处理）
统计: [payer+0x5c] += amount      ; monthly_paid —— 累计的是**实付额**（可能被截）
收款方:
  payee == -1   → [0x499080] += amount          ; 公库
  payee >  100  → [企業+0x28] += amount ; [企業+0x2c] += amount
  else          → flags&1 ? [payee+0x1c] += amount（现金）: [payee+0x20] += amount（存款）
                  [payee+0x60] += amount        ; monthly_received
```

`give_money(player, amount, flags)`：只做加法，**没有付款方、不会破产**；
`flags&1 ? 现金 : 存款`，并且**总是** `[player+0x60] += amount`。
返回值（eax）是残留的 `player*0x68`，**调用方不读**。

⚠️ 两条注意：
1. 两者末尾都有「若收/付方是**当前玩家**就刷新面板」的调用（`0x41d433`）。
   那是**表现层**：实测放开它会进图形状态并 `UC_ERR_READ_UNMAPPED @0x415fa6`。
   本用例一律把 `[0x46cad8]` 设成 `2`（`0x41d433` 的早退条件）把它关掉，
   并单独断言 `[0x49910c]`（当前玩家）**用完被还原**。
2. **破产分支跑不到底**：真缺口时 `0x40cd87` 会走到 `mkf_read_resource`
   （读 MKF 资源文件）而 `UC_ERR_READ_UNMAPPED @0x450471`。
   但它**在此之前**已把 `whoPlays` 清 0，所以本用例断言的到「标记破产」为止；
   破产处理内部（位置还原、地块标记、资源加载后的月支出累计）**未验证**。

跑法：cd rich4-spec && .venv/bin/python tests/test_money_move.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

PAY_MONEY = 0x41D2C6
GIVE_MONEY = 0x41D3F4

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
CASH, BANK, MONTHLY_PAID, MONTHLY_RECEIVED = 0x1C, 0x20, 0x5C, 0x60
WHO_PLAYS = 0x15

CURRENT_PLAYER = 0x49910C      # 当前玩家
POOL = 0x499080                # 公库
GAME_MODE = 0x46CAD8           # > 1 ⇒ 0x41d433 早退（关掉面板刷新）
COMPANY_BASE_PTR = 0x498E7C    # 企業表指针
COMPANY_STRIDE = 0x34

SCRATCH_TABLE = 0x600000       # 注入用的假企業表
START_POS_PTR = 0x498E80       # 走位/起点表指针（破产处理还原位置用）
START_POS_TABLE = 0x601000     # 假表（0x28 步长 × 8）
MKF_FAULT_EIP = 0x450471       # 破产处理里读 MKF 资源的故障点（见文件头）

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<54} 实际 {got_s!s:<16} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    # ── 公共 ──
    def _setup_players(self, emu, players, who=1):
        for i, (cash, bank) in enumerate(players):
            base = PLAYER_BASE + i * PLAYER_STRIDE
            emu.write32(base + CASH, cash)
            emu.write32(base + BANK, bank)
            emu.write32(base + MONTHLY_PAID, 0)
            emu.write32(base + MONTHLY_RECEIVED, 0)
            emu.write8(base + WHO_PLAYS, who)

    def _player(self, i):
        base = PLAYER_BASE + i * PLAYER_STRIDE
        return (self.emu.read32(base + CASH), self.emu.read32(base + BANK),
                self.emu.read32(base + MONTHLY_PAID),
                self.emu.read32(base + MONTHLY_RECEIVED))

    def _who(self, n=4):
        return [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS)
                for i in range(n)]

    # ── give_money ──
    def give(self, player, amount, flags, cash=1000, bank=2000, cur=9, players=4):
        def setup(emu):
            emu.write32(GAME_MODE, 2)          # 关掉面板刷新
            emu.write32(CURRENT_PLAYER, cur)
            self._setup_players(emu, [(cash, bank)] * players)
        r = self.emu.call(GIVE_MONEY, [player, amount, flags], setup=setup)
        return r["eax"]

    # ── pay_money ──
    def pay(self, payer, payee, amount, flags, players=((1000, 2000),) * 4,
            cur=9, who=1, company=None):
        """company = (index, funds, mirror) → 写进假的企業表第 index 条。"""

        def setup(emu):
            emu.write32(GAME_MODE, 2)
            emu.write32(CURRENT_PLAYER, cur)
            emu.write32(POOL, 0)
            emu.write32(COMPANY_BASE_PTR, SCRATCH_TABLE)
            emu.scratch_write(SCRATCH_TABLE, bytes(COMPANY_STRIDE * 4))
            # 破产处理要用走位表还原位置；不给它就会在 [edx*8] 上先炸，
            # 那样测到的是**我方注入不全**，不是真实的文件 I/O 边界。
            emu.write32(START_POS_PTR, START_POS_TABLE)
            emu.scratch_write(START_POS_TABLE, bytes(0x28 * 8))
            self._setup_players(emu, players, who=who)
            if company is not None:
                i, funds, mirror = company
                emu.write32(SCRATCH_TABLE + i * COMPANY_STRIDE + 0x28, funds)
                emu.write32(SCRATCH_TABLE + i * COMPANY_STRIDE + 0x2C, mirror)

        self.emu.call(PAY_MONEY, [payer, payee, amount, flags], setup=setup)

    def company(self, index):
        base = SCRATCH_TABLE + index * COMPANY_STRIDE
        return (self.emu.read32(base + 0x28), self.emu.read32(base + 0x2C))

    # ── 破产分支：捕获那个**已知的** MKF 故障 ──
    def pay_expect_mkf_fault(self, payer, payee, amount, flags, players=((1000, 2000),) * 4,
                             who=1):
        try:
            self.pay(payer, payee, amount, flags, players=players, who=who)
        except RuntimeError as exc:
            msg = str(exc)
            if f"0x{MKF_FAULT_EIP:08x}" in msg:
                return MKF_FAULT_EIP
            raise
        return None


def main():
    print("差分测试 #9：pay_money(0x41d2c6) 与 give_money(0x41d3f4)\n")
    f = F()

    print("[A] give_money（纯收款）")
    f.give(0, 300, 1)
    case("flags=1 → 现金 +300，存款不变", f._player(0), (1300, 2000, 0, 300))
    f.give(0, 300, 0)
    case("flags=0 → 存款 +300，现金不变", f._player(0), (1000, 2300, 0, 300))
    f.give(0, 300, 2)
    case("flags=2（bit0=0）→ 进存款", f._player(0), (1000, 2300, 0, 300))
    f.give(0, 300, 3)
    case("flags=3（bit0=1）→ 进现金", f._player(0), (1300, 2000, 0, 300))
    case("★ 收款方也累计 monthly_paid? **不** —— 它是 +0x60 收入",
         (f._player(0)[2], f._player(0)[3]), (0, 300))
    f.give(0, -300, 1)
    case("负数 -300 → 现金 700、+0x60 变 -300（纯加法，无护栏）",
         f._player(0), (700, 2000, 0, -300))
    f.give(2, 777, 1)
    case("只动玩家 2；同一次调用里其它玩家不变",
         (f._player(2), f._player(1), f._player(3)),
         ((1777, 2000, 0, 777), (1000, 2000, 0, 0), (1000, 2000, 0, 0)))
    # 累计：连发三次。⚠️ `call()` 每次都 `reset()`，所以**测试自己必须扮演记忆** ——
    # 把上一次的字段回读出来再注入下一次，否则会被重置成初值。
    st = (1000, 2000, 0, 0)
    for amt in (100, 200, 300):
        def setup_n(emu, st=st):
            emu.write32(GAME_MODE, 2)
            emu.write32(CURRENT_PLAYER, 9)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                c, b, mp, mr = st if i == 0 else (1000, 2000, 0, 0)
                emu.write32(base + CASH, c)
                emu.write32(base + BANK, b)
                emu.write32(base + MONTHLY_PAID, mp)
                emu.write32(base + MONTHLY_RECEIVED, mr)
                emu.write8(base + WHO_PLAYS, 1)
        r = f.emu.call(GIVE_MONEY, [0, amt, 1], setup=setup_n)
        eax = r["eax"]
        st = f._player(0)
    case("★ 连续三次（100+200+300）→ 现金 1600、+0x60 = 600",
         (st[0], st[3]), (1600, 600))
    case("★ 返回值 eax = player*0x68（残留，调用方不读）", eax, 0)
    case("★ 当前玩家全局用完被还原", f.emu.read32(CURRENT_PLAYER), 9)

    print("\n[B] pay_money：基本转移（现金优先 / 存款优先 / 收方落点）")
    P = ((1000, 2000),) * 4
    f.pay(0, 1, 300, 0, players=P)
    case("flags=0 → 付款方现金 -300；收款方**存款** +300",
         (f._player(0), f._player(1)), ((700, 2000, 300, 0), (1000, 2300, 0, 300)))
    f.pay(0, 1, 300, 1, players=P)
    case("flags=1 → 收款方**现金** +300",
         (f._player(0), f._player(1)), ((700, 2000, 300, 0), (1300, 2000, 0, 300)))
    f.pay(0, 1, 300, 4, players=P)
    case("flags=4 → 付款方**存款** -300（现金不动）",
         (f._player(0), f._player(1)), ((1000, 1700, 300, 0), (1000, 2300, 0, 300)))
    f.pay(0, 1, 300, 5, players=P)
    case("flags=5 → 存款优先 + 收款方现金",
         (f._player(0), f._player(1)), ((1000, 1700, 300, 0), (1300, 2000, 0, 300)))
    case("★ 付款方累计的是 monthly_paid(+0x5c)、收款方是 +0x60 —— 两个字段别写反",
         (f._player(0)[2], f._player(1)[3]), (300, 300))

    print("\n[C] pay_money：级联（现金不够就用存款）")
    f.pay(0, 1, 800, 0, players=((500, 2000),) + P[1:])
    case("现金 500 付 800 → 现金归零、存款扣 300；收款方 +800",
         (f._player(0), f._player(1)), ((0, 1700, 800, 0), (1000, 2800, 0, 800)))
    f.pay(0, 1, 800, 4, players=((2000, 100),) + P[1:])
    case("flags=4 存款 100 付 800 → 存款归零、现金扣 700",
         (f._player(0), f._player(1)), ((1300, 0, 800, 0), (1000, 2800, 0, 800)))
    f.pay(0, 1, 799, 0, players=((500, 300),) + P[1:])
    case("总额 800 付 799 → 现金归零、存款剩 1，**不破产**",
         (f._player(0), f._who(4)), ((0, 1, 799, 0), [1, 1, 1, 1]))

    print("\n[D] pay_money：真缺口（截断到实有额；破产处理只标记到 whoPlays）")
    f.pay(0, 1, 1000, 0, players=((500, 300),) + P[1:], who=0)
    case("★ 总额 800 付 1000 → 实付 **800**（monthly_paid 记实付）",
         f._player(0), (0, 0, 800, 0))
    case("★ 收款方也只收到 800", f._player(1), (1000, 2800, 0, 800))
    f.pay(0, 1, 1000, 0, players=((0, 0),) + P[1:], who=0)
    case("总额 0 付 1000 → 全 0，双方都不动",
         (f._player(0), f._player(1)), ((0, 0, 0, 0), (1000, 2000, 0, 0)))
    f.pay_expect_mkf_fault(0, 1, 1000, 0, players=((500, 300),) + P[1:])
    case("★ 真缺口且 whoPlays=1 → 破产处理把 whoPlays 清 0", f._who(4)[0], 0)
    case("★ 破产处理之后才回到 `+0x5c += 实付`，所以此刻 monthly_paid 还是 0",
         f._player(0)[2], 0)
    case("★ 故障点固定在 mkf_read_resource 的 0x450471（越界即说明分支变了）",
         f.pay_expect_mkf_fault(0, 1, 1000, 0, players=((500, 300),) + P[1:]),
         MKF_FAULT_EIP)

    print("\n[E] pay_money：公库与企业")
    f.pay(0, -1, 300, 0, players=P)
    case("payee = -1 → 公库 [0x499080] += 300，没有玩家收到",
         (f.emu.read32(POOL), f._player(0), f._player(1)),
         (300, (700, 2000, 300, 0), (1000, 2000, 0, 0)))
    f.pay(101, 1, 300, 0, players=P, company=(1, 5000, 6000))
    case("企業付款(101)：企業 -0x28/-0x2c 各 300，**不累计 monthly_paid**",
         (f.company(1), f._player(0), f._player(1)),
         ((4700, 5700), (1000, 2000, 0, 0), (1000, 2300, 0, 300)))
    f.pay(0, 101, 300, 0, players=P, company=(1, 5000, 6000))
    case("企業收款(101)：企業 +0x28/+0x2c 各 300",
         (f.company(1), f._player(0)), ((5300, 6300), (700, 2000, 300, 0)))
    f.pay(101, 102, 300, 0, players=P, company=(1, 5000, 6000))
    case("企業→企業：付款企業 -300；付款方玩家完全不动",
         (f.company(1), f._player(0)), ((4700, 5700), (1000, 2000, 0, 0)))
    case("收款企業下标是 100 基（101 → 第 1 条）", f.company(2), (300, 300))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
