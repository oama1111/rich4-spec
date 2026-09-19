#!/usr/bin/env python3
"""
通道 2 差分测试 #10 · `fcn_0041d89e`（VA 0x0041d89e）—— **全局唯一的胜负判定**

它的返回值直接决定「日推进要不要当场收摊」：
```asm
0041cfab  inc  dword [0x4990e4]      ; 總天數 +1
0041cfb1  call 0x41d89e
0041cfb6  cmp  eax, 1
0041cfb9  je   0x41d1a5              ; ★ 达成 → 日推进当场 return（行情/開獎/月結/地契都不走）
```
此前只有"读汇编 + 单元测试"。本用例直接 `call 0x41d89e`（**无参数、全读全局**）。

判定的全部逻辑（451 字节 / 140 条）：

```
ebp = 0
if ([0x49911c] == 0 && [0x499108] == 0) return 0        ; 两条胜利条件都没开
best = 0 ; bestIdx = 0
for p in 0..[0x499114]-1:                              ; 玩家数
    if whoPlays[p] == 0: continue                       ; 出局者不计
    w = wealth(p)                                        ; ★ 内部把总资产压成 float32
    if (best < w) { best = w ; bestIdx = p }             ; ★ 严格大于 ⇒ **平局取下标小的**
if (best == 0)            → 只看金额条件                 ; ★ 首富资产为 0 时**天数条件不生效**
if ([0x49911c] != 0 && [0x49911c] <= [0x4990e4]) → 结束   ; 天数达标
if ([0x499108] == 0)      → 不结束
if (best >= [0x499108])   → 结束                          ; 金额达标
结束:
    [0x49910c] = bestIdx                                  ; 当前玩家 = 赢家
    0x41906a(1)                                           ; 窗口（已打桩）
    player_say(bestIdx, 3, 台词表[角色])                    ; 台词（已打桩）
    for p != bestIdx: whoPlays[p] = 0                      ; ★ 只清这一个字节
    if ([0x499104] == 1):                                  ; 模式 1
        if (whoPlays[bestIdx] & 1):                        ; 赢家是「人类」
            for p != bestIdx: [0x4990f4 + 角色[p]] = 2      ; ★ 按**角色号**索引的表
            [0x46caf8] = 2
        else:                                              ; 赢家是电脑 → 一大段状态重置
            ... (走 mkf_read_resource，纯仿真跑不动，见下)
    else:
        [0x46caf8] = (whoPlays[bestIdx] & 1) ? 3 : 1        ; 终局码
    ebp = 1
return ebp                                                 ; 1 = 游戏结束
```

⚠️ **两处打桩**（与 `test_notice_board.py` 的 `memcpy` 桩同一性质）：
`0x41906a`（窗口重画，`writes` 只有 `0x475110`）与 `0x44ef41`（`player_say` 台词，
`writes` 只有 `0x46caf4`/`0x4762c8`）—— 两者的写入面都**不含**玩家/金钱/地图/股市，
故打桩只去掉表现层。它们之间的顺序要注意：**清 `whoPlays` 在它们之后**。

⚠️ **诚实边界**：`[0x499104] == 1` 且**赢家是电脑**的那一支（`0x41d9b9` 起：重置位置、
`fillBytes32` 清玩家 `+0x32..+0x68`、`0x40b93b`、`0x407842`）会走到
`mkf_read_resource`（读 MKF 资源）而 `UC_ERR_READ_UNMAPPED @0x450471` ——
与破产处理是**同一个**纯仿真限制。本用例只把故障地址钉住。

跑法：cd rich4-spec && .venv/bin/python tests/test_victory.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

VICTORY = 0x41D89E
WINDOW_REFRESH = 0x41906A      # 打桩：窗口
PLAYER_SAY = 0x44EF41          # 打桩：台词

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
WHO_PLAYS, CHAR = 0x15, 0x13
CASH, BANK, LOAN = 0x1C, 0x20, 0x24

NUM_PLAYERS = 0x499114
TIME_LIMIT = 0x49911C
WEALTH_TARGET = 0x499108
MODE = 0x499104
TOTAL_DAYS = 0x4990E4
CURRENT_PLAYER = 0x49910C
END_CODE = 0x46CAF8
CHAR_FLAGS = 0x4990F4          # [角色号] → 2
START_POS_PTR = 0x498E80       # 走位表（mode=1 电脑赢那一支要用）
START_POS_TABLE = 0x601000

BANKRUPTCY = 0x40CD87          # 破产处理（会走到 MKF 资源，见 [9]）
MKF_FAULT_EIP = 0x450471

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<52} 实际 {got_s!s:<18} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    def run(self, cashs, time_limit=0, target=0, mode=0, days=0,
            alive=None, who=(1, 2, 1, 2), chars=(0, 1, 2, 3)):
        alive = alive if alive is not None else [True] * len(cashs)
        n = len(cashs)

        def setup(emu):
            emu.patch(WINDOW_REFRESH, b"\xc3")       # 表现层桩
            emu.patch(PLAYER_SAY, b"\xc3")
            emu.write32(START_POS_PTR, START_POS_TABLE)
            emu.scratch_write(START_POS_TABLE, bytes(0x28 * 8))
            emu.write32(NUM_PLAYERS, n)
            emu.write32(TIME_LIMIT, time_limit)
            emu.write32(WEALTH_TARGET, target)
            emu.write32(MODE, mode)
            emu.write32(TOTAL_DAYS, days)
            emu.write32(CURRENT_PLAYER, 0)
            emu.write8(END_CODE, 0)
            # CHAR_FLAGS(0x4990f4) 在 .bss 里，reset() 已清零，无需注入
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write32(base + CASH, cashs[i] if i < n else 0)
                emu.write32(base + BANK, 0)
                emu.write32(base + LOAN, 0)
                emu.write8(base + WHO_PLAYS, who[i] if i < n and alive[i] else 0)
                emu.write8(base + CHAR, chars[i])

        r = self.emu.call(VICTORY, [], setup=setup)
        return {
            "ret": r["eax"],
            "who": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS)
                    for i in range(4)],
            "code": self.emu.read8(END_CODE),
            "cur": self.emu.read32(CURRENT_PLAYER),
            "charFlags": [self.emu.read8(CHAR_FLAGS + i) for i in range(4)],
        }

    def run_expect_mkf_fault(self, **kw):
        try:
            self.run(**kw)
        except RuntimeError as exc:
            if f"0x{MKF_FAULT_EIP:08x}" in str(exc):
                return MKF_FAULT_EIP
            raise
        return None


def main():
    print("差分测试 #10：fcn_0041d89e 胜负判定(VA 0x0041d89e)\n")
    f = F()

    print("[1] 两条胜利条件都没开 → 直接返回 0（不数资产）")
    r = f.run([1000, 2000])
    case("两条都关 → ret 0，没人出局（只有 2 名玩家，2/3 号是 0）",
         (r["ret"], r["who"]), (0, [1, 2, 0, 0]))

    print("\n[2] 金额条件（首富总资产 >= 目标）")
    r = f.run([1000, 2000], target=1500)
    case("目标 1500 / 首富 2000 → ret 1", r["ret"], 1)
    case("赢家 = 下标 1（当前玩家也设成它）", (r["cur"], r["who"]), (1, [0, 2, 0, 0]))
    case("★ 终局码：赢家 who=2（电脑）→ 1", r["code"], 1)
    r = f.run([2000, 1000], target=1500)     # 赢家下标 0，who=1（人类）
    case("★ 赢家 who=1（人类）→ 终局码 3", (r["code"], r["cur"]), (3, 0))
    r = f.run([1000, 2000], target=2500)
    case("目标 2500 未达 → ret 0，没人出局", (r["ret"], r["who"]), (0, [1, 2, 0, 0]))
    r = f.run([1000, 2000], target=2000)
    case("★ 恰好达标（>= 而非 >）→ ret 1", r["ret"], 1)

    print("\n[3] 时间条件（[0x49911c] <= 已过天数）")
    r = f.run([1000, 2000], time_limit=1, days=5)
    case("上限 1 / 已过 5 → ret 1", r["ret"], 1)
    r = f.run([1000, 2000], time_limit=9, days=5)
    case("上限 9 / 已过 5 → ret 0", r["ret"], 0)
    r = f.run([1000, 2000], time_limit=5, days=5)
    case("★ 恰好到期（5 <= 5）→ ret 1", r["ret"], 1)

    print("\n[4] ★ 首富资产为 0 时**天数条件不生效**（`test edi,edi / je` 那一下）")
    r = f.run([0, 0], time_limit=1, days=5)
    case("全员 0 资产 + 天数早过 → ret 0；且没人出局",
         (r["ret"], r["who"]), (0, [1, 2, 0, 0]))
    r = f.run([0, 0], target=0)
    case("全员 0 资产 + 金额目标 0 → 视为「没开条件」→ ret 0", r["ret"], 0)
    r = f.run([0, 500], time_limit=1, days=5)
    case("只要有人资产 > 0，天数条件就生效 → ret 1", r["ret"], 1)

    print("\n[5] 平局与出局者")
    r = f.run([2000, 2000], target=1500)
    case("★ 平局 [2000,2000] → 赢家是**下标小的**（严格大于才换）",
         (r["cur"], r["who"]), (0, [1, 0, 0, 0]))
    r = f.run([2000, 2000], target=1500, alive=[False, True, False, False])
    case("平局但 0 号已出局 → 赢家 1", (r["cur"], r["who"]), (1, [0, 2, 0, 0]))
    r = f.run([500, 2000], target=1000, alive=[True, False, False, False])
    case("★ 出局者资产更高也不算 → 活人 500 不达标 → ret 0",
         (r["ret"], r["who"]), (0, [1, 0, 0, 0]))

    print("\n[6] 收尾：只清其它人的 whoPlays（钱与地产留着）")
    r = f.run([1000, 2000], target=1500)
    case("赢家的 whoPlays 保持原值（人类 1）", r["who"][1], 2)
    case("其它活着的人被清成 0", (r["who"][0], r["who"][2]), (0, 0))
    case("totalDays / 其它全局不受影响", f.emu.read32(WEALTH_TARGET), 1500)

    print("\n[7] 模式 1：赢家是「人类」→ 终局码 2 + 按**角色号**写 [0x4990f4]")
    r = f.run([1000, 2000], target=1500, mode=1, who=(2, 1, 0, 0))
    case("终局码 2", r["code"], 2)
    case("★ 输家（角色 0）的 [0x4990f4 + 0] = 2", r["charFlags"][0], 2)
    case("赢家自己那一格不动", r["charFlags"][1], 0)
    print("\n[8] 终局码的判据是**全局** `[0x499104]`（不是现数在场的人）")
    # [0x499104] == 1 ⟺ 单人局 → 2；否则人类赢 → 3。它由 mode 参数写入。
    r = f.run([2000, 1000], target=1500, mode=2)     # 2 个人类
    case("人类赢 + [0x499104]=2（多人局）→ 终局码 3", r["code"], 3)
    r = f.run([2000, 1000], target=1500, mode=1)     # 1 个人类
    case("人类赢 + [0x499104]=1（单人局）→ 终局码 2", r["code"], 2)
    r = f.run([2000, 1000], target=1500, mode=7)
    case("★ 只要 != 1 就走多人支 → 3（不是「按实际人数算」）", r["code"], 3)

    print("\n[9] ★★ 破产处理**不改** `[0x499104]` —— 复刻若按 whoPlays 现数就会算错")
    # 实测：2 人局把 0 号破产后，[0x499104] 仍是 2，而 whoPlays==1 已只剩 1 人。
    def bankrupt_then_read():
        def setup(emu):
            emu.patch(0x41906A, b"\xc3")
            emu.write32(0x498E80, START_POS_TABLE)
            emu.scratch_write(START_POS_TABLE, bytes(0x28 * 8))
            emu.write32(0x46CAD8, 2)
            emu.write32(NUM_PLAYERS, 2)
            emu.write32(0x499104, 2)                      # 两个人类
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write32(base + CASH, 1000)
                emu.write32(base + BANK, 0)
                emu.write32(base + LOAN, 0)
                emu.write8(base + WHO_PLAYS, 1 if i < 2 else 2)
        try:
            f.emu.call(BANKRUPTCY, [0], setup=setup)      # 破产处理（会在 MKF 上炸）
        except RuntimeError:
            pass
        return (f.emu.read32(0x499104),
                [f.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + WHO_PLAYS)
                 for i in range(4)])

    humans, who = bankrupt_then_read()
    case("破产 0 号后 [0x499104] 仍是 2（**不变**）", humans, 2)
    case("而 whoPlays 已经掉到只剩 1 个人类", who, [0, 1, 2, 2])
    case("⇒ 现数会得 1（错），原版用 2 ⇒ 终局码 3",
         sum(1 for w in who if w == 1), 1)

    print("\n[10] 边界：模式 1 + **电脑**赢家会走 `0x41d9b9` 那一大段（读 MKF 资源）")
    case("★ 故障点固定在 0x450471（与破产处理同一限制）",
         f.run_expect_mkf_fault(cashs=[2000, 1000], target=1500, mode=1,
                                who=(2, 2, 0, 0)), MKF_FAULT_EIP)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
