#!/usr/bin/env python3
"""
通道 2 差分测试 #12 · `0x00436b0a(arg)` —— **银行结算 / 经营权易主**

`bank.md` §3.4 早有详细规格（逐句注解），但从未做过真值比对。它是全局唯一的
「银行经营者资金对账」点，两个分支由 `arg` 选：

```
; ① 找银行地块的经营者（在 **設施表** [0x498e7c] 里找 +0x1a == 7 的那条）
edi = -1
for (ebx = 1; ebx <= [0x498e90]; ebx++) {
    esi = [0x498e7c] + ebx*0x34
    if ([esi+0x1a] == 7 && [esi+0x18] != 0) edi = [esi+0x18]-1   ; ★ 后者覆盖前者
}
; ② arg != 0（ATM 取款确认 / AI 比例重分）：
if (edi == -1 || edi == [0x49910c]) return
liab = player[edi].+0x28 ; if (liab == 0) return
total = Σ player[i].+0x20（**在场**且 i != edi）
if (total >= liab) return
shortfall = liab - total
sprintf('銀行資金準備不足…由經營者%s墊付！') ; 弹 2500ms
0x433bd8(edi, shortfall)        ; ★ 经营者付：**先扣存款**、不够再扣现金、都不够就破产
player[edi].+0x28 -= shortfall ; 负数夹 0
; ③ arg == 0（回合 / 事件驱动）：经营者的特别融资必须**还清**（经营权易主）
for (ebx = 0; ebx < [0x499114]; ebx++) {
    if (player[ebx].+0x28 == 0) continue
    sprintf('銀行經營權易主！…強制償還%d元…')
    0x433bd8(ebx, player[ebx].+0x28)
    player[ebx].+0x28 = 0
}
```

⚠️ **四处表现层打桩**（都只为让规则段跑到底；被桩函数与「规则状态」无关）：
| VA | 是什么 | 依据 |
|---|---|---|
| `0x41906a` | 窗口重画 | `writes` 只有 `0x475110` |
| `0x452946` | 取玩家名（去掉空格拷进缓冲） | `writes` 空（只写传出缓冲） |
| `0x457110` | `sprintf_wrap`（消息正文） | 只写传出缓冲 |
| `0x440cac` | 弹窗 2500ms | `writes` 只有 `0x48c51c` |

其中 `0x452946` 内部调 `0x45825d`（**`strlen`**，用 `mov es,ds` + `repne scasb`）——
与 CRT `memcpy` 同一类**纯仿真跑不了**的段寄存器写法（见 `test_notice_board.py` 的桩）。

⚠️ **诚实边界**：缺口大到把经营者**打空**时，`0x433bd8` 会调破产处理 `0x40cd87`，
后者走 `mkf_read_resource` 而 `UC_ERR_READ_UNMAPPED @0x450471` ⇒
本用例只断言到「经营者被抽空 + `whoPlays` 清 0」，
**`+0x28 -= shortfall` 那一句在纯仿真里到不了**（原版会执行到）。

跑法：cd rich4-spec && .venv/bin/python tests/test_bank_settle.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

BANK_SETTLE = 0x436B0A
PAY_SPECIAL_FINANCE = 0x433BD8   # 0x433bd8(player, amount)：先存款后现金

WINDOW_REFRESH = 0x41906A
PLAYER_NAME = 0x452946
SPRINTF_WRAP = 0x457110
MESSAGE_BOX = 0x440CAC

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
WHO_PLAYS, CASH, BANK, LIABILITY = 0x15, 0x1C, 0x20, 0x28

FACILITY_PTR, FACILITY_COUNT = 0x498E7C, 0x498E90
FACILITY_STRIDE = 0x34
FAC_OWNER, FAC_TYPE = 0x18, 0x1A
BANK_TYPE = 7

NUM_PLAYERS = 0x499114
CURRENT_PLAYER = 0x49910C
START_POS_PTR = 0x498E80
START_POS_TABLE = 0x601000
SCRATCH_FAC = 0x600000

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

    def run(self, arg, records=((BANK_TYPE, 1),), liabilities=(0, 0, 0, 0),
            players=((1000, 5000), (2000, 3000), (0, 0), (0, 0)),
            n=2, cur=9, who=(1, 1)):
        """records = 设施表第 1..n 条的 (type, owner+1)；type=None 表示不设类型。"""

        def setup(emu):
            for va in (WINDOW_REFRESH, PLAYER_NAME, SPRINTF_WRAP, MESSAGE_BOX):
                emu.patch(va, b"\xc3")
            emu.write32(START_POS_PTR, START_POS_TABLE)
            emu.scratch_write(START_POS_TABLE, bytes(0x28 * 8))
            emu.write32(FACILITY_PTR, SCRATCH_FAC)
            emu.scratch_write(SCRATCH_FAC, bytes(FACILITY_STRIDE * 4))
            emu.write32(FACILITY_COUNT, max(len(records), 1))
            for i, (typ, owner) in enumerate(records):
                rec = SCRATCH_FAC + (i + 1) * FACILITY_STRIDE
                if typ is not None:
                    emu.write8(rec + FAC_TYPE, typ)
                emu.write8(rec + FAC_OWNER, owner)
            emu.write32(NUM_PLAYERS, n)
            emu.write32(CURRENT_PLAYER, cur)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + WHO_PLAYS, who[i] if i < len(who) else 0)
                emu.write32(base + CASH, players[i][0])
                emu.write32(base + BANK, players[i][1])
                emu.write32(base + 0x24, 0)
                emu.write32(base + LIABILITY, liabilities[i])

        self.emu.call(BANK_SETTLE, [arg], setup=setup)
        return {
            "cash": [self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + CASH) for i in range(4)],
            "bank": [self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + BANK) for i in range(4)],
            "liab": [self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + LIABILITY) for i in range(4)],
            "who": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS) for i in range(4)],
        }

    def run_until_bankruptcy(self, **kw):
        try:
            self.run(**kw)
        except RuntimeError:
            pass                                   # 已知：破产处理会走 MKF 资源
        return {
            "bank": [self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + BANK) for i in range(4)],
            "cash": [self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + CASH) for i in range(4)],
            "who": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS) for i in range(4)],
        }


def main():
    print("差分测试 #12：银行结算 0x00436b0a(arg)\n")
    f = F()

    print("[1] 先找银行经营者：`+0x1a == 7` 且 `+0x18 != 0`，**后一条覆盖前一条**")
    # 让「用哪条」产生**可区分**的结果：liab[0]=4000（他人存款 3000 ⇒ 会付）、
    # liab[1]=4000（他人存款 5000 ⇒ 不动）
    liabs = (4000, 4000, 0, 0)
    r = f.run(1, records=((BANK_TYPE, 1),), liabilities=liabs)
    case("只有 owner=1 那条 → 经营者是下标 0：缺口 1000 ⇒ 存款 5000→4000",
         (r["bank"][0], r["bank"][1]), (4000, 3000))
    r = f.run(1, records=((BANK_TYPE, 1), (BANK_TYPE, 2)), liabilities=liabs)
    case("★ 两条(owner 1,2) → **最后一条赢**（下标 1）：他人存款 5000>=4000 ⇒ 不动",
         (r["bank"][0], r["bank"][1]), (5000, 3000))
    r = f.run(1, records=((BANK_TYPE, 2), (BANK_TYPE, 0)), liabilities=liabs)
    case("★ 后一条 owner=0（无主）**不重置** edi ⇒ 仍是下标 1 ⇒ 不动",
         (r["bank"][0], r["bank"][1]), (5000, 3000))
    r = f.run(1, records=((1, 1),), liabilities=(4000, 0, 0, 0))
    case("没有 `+0x1a == 7` 的记录 → 什么都不做",
         (r["liab"][0], r["bank"][0]), (4000, 5000))

    print("\n[2] `arg != 0` 的三道闸门")
    r = f.run(1, liabilities=(0, 0, 0, 0))
    case("经营者负债 0 → 不动", (r["liab"][0], r["bank"][0]), (0, 5000))
    r = f.run(1, liabilities=(4000, 0, 0, 0), cur=0)
    case("经营者 == 当前玩家 → 不动", (r["liab"][0], r["bank"][0]), (4000, 5000))
    r = f.run(1, liabilities=(2000, 0, 0, 0))
    case("他人存款合计 3000 >= 负债 2000 → 不动",
         (r["liab"][0], r["bank"][0]), (2000, 5000))

    print("\n[3] `arg != 0` 缺口垫付：`shortfall = 负债 − 他人存款合计`")
    r = f.run(1, liabilities=(4000, 0, 0, 0))
    case("欠 4000 / 他人存款 3000 → 缺口 1000：存款 5000→4000",
         (r["bank"][0], r["cash"][0]), (4000, 1000))
    case("  负债同时减到 4000-1000 = 3000", r["liab"][0], 3000)
    case("  他人一分不动", (r["bank"][1], r["liab"][1]), (3000, 0))
    r = f.run(1, liabilities=(4000, 0, 0, 0), players=((1000, 500), (2000, 3000), (0, 0), (0, 0)))
    case("存款不够 → 先扣光存款再扣现金（缺口 1000）",
         (r["bank"][0], r["cash"][0], r["liab"][0]), (0, 500, 3000))
    r = f.run_until_bankruptcy(arg=1, liabilities=(9000, 0, 0, 0),
                              players=((1000, 500), (2000, 3000), (0, 0), (0, 0)))
    case("缺口 6000 > 存款+现金 1500 → 两边都抽干",
         (r["bank"][0], r["cash"][0]), (0, 0))
    case("  ★ 此时破产处理把经营者 whoPlays 清 0", r["who"][0], 0)

    print("\n[4] 他人的存款合计**只算在场者**（出局者不算）")
    r = f.run(1, liabilities=(4000, 4000, 0, 0),
              players=((1000, 5000), (1000, 99999), (0, 0), (0, 0)), who=(1, 0))
    case("★ 出局者存款 99999 不计 → 缺口 4000（否则会被当成 99999>=4000 而不动）",
         (r["bank"][0], r["liab"][0]), (1000, 0))
    case("  出局者自己一动不动", (r["bank"][1], r["liab"][1]), (99999, 4000))

    print("\n[5] ★★ `arg == 0`：**跳过银行经营者**，其余在场者强制还清（经营权易主）")
    # 本条把 bank.md §3.4 的伪码**订正**了：那里漏了两道 guard
    # （`cmp ebx,edi / je` 跳过经营者、`whoPlays == 0` 跳过出局者）。
    r = f.run(0, liabilities=(5000, 3000, 2000, 0), n=3,
              players=((1000, 5000), (2000, 3000), (3000, 2000), (0, 0)),
              who=(1, 1, 1))
    case("★ 经营者（下标 0）被**跳过**：负债 5000 与存款 5000 都不动",
         (r["liab"][0], r["bank"][0]), (5000, 5000))
    case("  其余在场者各还清：下标 1 → 存款 3000→0、负债→0",
         (r["bank"][1], r["liab"][1]), (0, 0))
    case("  下标 2 同理 → 存款 2000→0、负债→0",
         (r["bank"][2], r["liab"][2]), (0, 0))
    case("  存款够时现金不动", (r["cash"][1], r["cash"][2]), (2000, 3000))
    r = f.run(0, liabilities=(5000, 3000, 2000, 0), n=3,
              players=((1000, 5000), (2000, 3000), (3000, 2000), (0, 0)),
              who=(1, 1, 0))
    case("★ 出局者（下标 2）也被跳过：负债仍 2000、存款仍 2000",
         (r["liab"][2], r["bank"][2]), (2000, 2000))
    r = f.run(0, liabilities=(0, 0, 0, 0))
    case("没人欠 → 什么都不做",
         (r["bank"][0], r["bank"][1], r["liab"][0]), (5000, 3000, 0))
    # 负债 3000 > 存款 100 + 现金 2000 ⇒ 抽干并触发破产（同样走 MKF，用容错变体）
    r = f.run_until_bankruptcy(arg=0, liabilities=(0, 3000, 0, 0),
                               players=((1000, 5000), (2000, 100), (0, 0), (0, 0)))
    case("存款不足者：存款 100→0、现金 2000→0、whoPlays 清 0",
         (r["bank"][1], r["cash"][1], r["who"][1]), (0, 0, 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
