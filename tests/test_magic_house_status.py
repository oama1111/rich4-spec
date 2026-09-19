#!/usr/bin/env python3
"""
通道 2 差分测试 #61 · **魔法屋「移动方式 / 有神」类筛选器**（跳表 0x431812 的 idx 6/7/8/9）

第三条魔法屋筛选器差分（前两条：`test_magic_house_targets.py` 的 10/11、
`test_magic_house_extremes.py` 的 0/3/4/5）。本文件覆盖剩下四支里**判据最简单**的四个：

```asm
; @source 0x00431b2c（idx 6）—— 与 7/8 同构，只有比对常量不同
00431b2c  ebx = 0（玩家下标）; esi = 0（结果计数）
00431b36  cmp ebx, [0x499114] / jge 汇合点 0x431c62
00431b3e  eax = ebx * 0x68
00431b41  cmp byte [eax + 0x496b7d], 0 / je 下一位  ; ★ +0x7d = 0 ⇒ 不在场
00431b48  test byte [eax + 0x496b79], 3 / jne 下一位  ; ★★ `+0x11` = traffic_method，只看**低两位**
00431b52  [esi + 0x48c380] = (bl + 1)                ; 1 基
; ── idx 7（0x431b61）与 idx 8（0x431b99）──
00431b61  mov al, byte [eax + 0x496b79] / and al, 3 / cmp al, 1 / jne 跳过
00431b99  …                                  / and al, 3 / cmp al, 2 / jne 跳过
; ── idx 9（0x431bcf）身上有神 ──
00431bcf  cmp byte [eax + 0x496ba7], 0 / je 跳过      ; ★ `+0x3f` = god_info，非 0 即可
```

★ 三条实测要点：

| # | 事实 | 意义 |
|---|---|---|
| 1 | ★★ idx 6/7/8 都先 `and al, 3`，**只看 `traffic_method` 的低两位** | 更高位不参与判定 |
| 2 | idx 6 = 低两位 **== 0**（步行）、idx 7 = **== 1**（機車）、idx 8 = **== 2**（汽車） | 三支**互斥**且**不覆盖 3**（traffic_method == 3 的玩家三支都不收） |
| 3 | idx 9 只看 `player + 0x3f`（`god_info`）**非 0** | 与 `god_info ∈ 1..6` 那套跳表不同：**7..12 也算「有神」** |

## 打桩

无（四支都是纯读：只扫玩家记录的两个字节）。

跑法：cd rich4-spec && .venv/bin/python tests/test_magic_house_status.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

DISPATCH = 0x431842
TABLE = 0x431812
RESULTS_ARR = 0x48C380
NUM_PLAYERS = 0x499114
PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_PRESENT = 0x15
P_TRAFFIC = 0x11         # ★ +0x11 = traffic_method（0 步行 / 1 機車 / 2 汽車 / 3 …）
P_GOD = 0x3F
ARR_FILL = 0xEE
KINDS = {
    6: "低两位 == 0（无状态）",
    7: "低两位 == 1",
    8: "低两位 == 2",
    9: "身上有神（+0x3f != 0）",
}
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<26} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    def run(self, kind, traffic, god=None, present=None, players=None, present_flags=None):
        """`traffic[p]` = 玩家 p 的 `+0x11`（traffic_method）；`god[p]` = `+0x3f`。"""
        emu = Emu()
        n = len(traffic) if players is None else players
        pres = (present_flags if present_flags is not None
                else ([1] * 4 if present is None else present))

        def setup(e):
            e.write32(NUM_PLAYERS, n)
            for p in range(4):
                base = PLAYER_BASE + p * STRIDE
                e.write8(base + P_PRESENT, pres[p])
                e.write8(base + P_TRAFFIC, traffic[p] & 0xFF)
                e.write8(base + P_GOD, (god[p] if god else 0) & 0xFF)
            for i in range(8):
                e.write8(RESULTS_ARR + i, ARR_FILL)
        r = emu.call(DISPATCH, [kind, 0], setup=setup, timeout_insns=200000)
        self.emu = emu
        return r["eax"], list(emu.read(RESULTS_ARR, 8))


def main():
    print("差分测试 #61：魔法屋状态位/有神筛选器（idx 6/7/8/9）\n")

    print("[A] 跳表 `0x431812` 的四项")
    e0 = Emu()
    got = [struct.unpack("<I", e0.read(TABLE + 4 * i, 4))[0] for i in range(12)]
    case("[6] 无状态 = 0x431b2c", got[6], 0x431B2C)
    case("[7] 状态==1 = 0x431b61", got[7], 0x431B61)
    case("[8] 状态==2 = 0x431b99", got[8], 0x431B99)
    case("[9] 身上有神 = 0x431bcf", got[9], 0x431BCF)

    fill = [ARR_FILL] * 8

    print("\n[B] idx 6「低两位 == 0」")
    ret, arr = F().run(6, [0, 1, 2, 0])
    case("traffic [0,1,2,0] ⇒ 收下标 0 与 3", arr, [1, 4, 0, 0] + fill[4:])
    ret, arr = F().run(6, [0, 0, 0, 0])
    case("四人全 0 ⇒ [1,2,3,4]", arr, [1, 2, 3, 4] + fill[4:])

    print("\n[C] ★★ 判据是 `and al,3` 后与常量比 —— 只看**低两位**")
    #   `+0x11` 是 traffic_method，实际取值 0..3；仍可喂高位字节验证掩码确实生效
    ret, arr = F().run(6, [0x00, 0x04, 0x08, 0x0C])
    case("低两位都是 0（0x00/0x04/0x08/0x0C）⇒ 四人全收", arr, [1, 2, 3, 4] + fill[4:])
    ret, arr = F().run(7, [0x05, 0x0D, 0x15, 0x1D])
    case("★ 低两位都是 1（0x05/0x0D/0x15/0x1D）⇒ 四人全收", arr, [1, 2, 3, 4] + fill[4:])
    ret, arr = F().run(7, [0x06, 0x0E, 0x16, 0x1E])
    case("★ 低两位都是 2 ⇒ idx 7 返回 0（证明掩码后比的是常量 1）", ret, 0)
    ret, arr = F().run(8, [0x80 | 0x02, 0x40 | 0x02, 0x02, 0x00])
    case("idx 8：低两位都是 2 的前三人 ⇒ [1,2,3]", arr, [1, 2, 3, 0] + fill[4:])

    print("\n[D] ★ idx 6/7/8 三支**互斥**，且 traffic_method == 3 的三支都不收")
    for kind, want in ((6, 1), (7, 2), (8, 3)):
        ret, arr = F().run(kind, [0, 1, 2, 3])
        case(f"traffic [0,1,2,3] + idx {kind} ⇒ 只收 [{want}]",
             arr, [want, 0, 0, 0] + fill[4:])
    ret, arr = F().run(6, [3, 3, 3, 3])
    case("四人 traffic 都是 3 ⇒ idx 6 返回 0", ret, 0)
    ret, arr = F().run(7, [3, 3, 3, 3])
    case("★ 四人 traffic 都是 3 ⇒ idx 7 也返回 0", ret, 0)

    print("\n[E] ★ 不在场（`+0x7d == 0`）不参评")
    ret, arr = F().run(6, [0, 0, 0, 0], present_flags=[1, 0, 0, 1])
    case("下标 1/2 不在场 ⇒ 只收 0 与 3", arr, [1, 4, 0, 0] + fill[4:])

    print("\n[F] 人数闸 `[0x499114]`")
    ret, arr = F().run(6, [0, 0, 0, 0], players=2)
    case("人数 2 ⇒ [1,2]", arr, [1, 2, 0, 0] + fill[4:])

    print("\n[G] ★ idx 9「身上有神」：`+0x3f != 0`（**7..12 也算**）")
    ret, arr = F().run(9, [0, 0, 0, 0], god=[0, 1, 0, 12])
    case("god [0,1,0,12] ⇒ 收下标 1 与 3", arr, [2, 4, 0, 0] + fill[4:])
    ret, arr = F().run(9, [0, 0, 0, 0], god=[0, 0, 0, 0])
    case("四人无神 ⇒ 返回 0", ret, 0)
    ret, arr = F().run(9, [0, 0, 0, 0], god=[1, 2, 3, 4])
    case("四人各 1..4 ⇒ 四人全收", arr, [1, 2, 3, 4] + fill[4:])
    ret, arr = F().run(9, [0, 0, 0, 0], god=[6, 7, 8, 9])
    case("★ god 6..9（含小窮神/大窮神/小衰神/大衰神）**都算「有神」**",
         arr, [1, 2, 3, 4] + fill[4:])

    print("\n[H] idx 9 与 traffic_method 无关")
    ret, arr = F().run(9, [0, 1, 2, 3], god=[5, 0, 5, 0])
    case("traffic 乱七八糟也不影响 ⇒ [1, 3]", arr, [1, 3, 0, 0] + fill[4:])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
