#!/usr/bin/env python3
"""
通道 2 差分测试 #13 · `0x0040cc1a(player)` —— **解除同盟（双向）**

规格来源：`docs/systems/cards.md`（`player+0x41` = `allied_player`，1 基、0 = 无）、
`docs/systems/hostility.md`/`ai.md`，以及 `gen/db.txt`。

```
0040cc1b  eax = player*0x68
0040cc22  [player+0x3d] = 0                  ; allied_days
0040cc2a  edx = [player+0x41]                ; allied_player（1 基）
0040cc30  dec edx                            ; ★ **没有 0 判断**
0040cc31  imul edx, edx, 0x68
0040cc36  [edx + 0x496ba9] = 0               ; 盟友 +0x41 = 0
0040cc48  [edx + 0x496ba5] = 0               ; 盟友 +0x3d = 0
0040cc4e  [player+0x41] = 0
```

★ 本用例验到的四条：
1. 双向清：自己与盟友的 `+0x3d`/`+0x41` 四格全清，其它玩家不动；
2. **不检查对方是否指回自己**（`p0→p1` 而 `p1→p2` 时，p1 照样被清）；
3. **不追链**：只清一层，盟友的"盟友"不动；
4. ★★ `allied_player == 0` 时**没有护栏**：`edx = 0-1 = -1` ⇒
   写到 `0x496ba9 - 0x68 = 0x496B41` 与 `0x496ba5 - 0x68 = 0x496B3D`
   —— **越界清掉两个字节**（实测把这两格从 `0xAA`/`0xBB` 清成 0）。
   这两格的语义 PRD 里**没有**（`0x496b30 + ...` 那一片只确认了「在狱」等少数几个）。
   ⚠️ 复刻 `rules/hostility.ts` 的 `breakAlliance` **加了 `alliedPlayer === 0` 提前返回**
   —— 登记为**有意偏离**（见该函数注释）。

跑法：cd rich4-spec && .venv/bin/python tests/test_alliance.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

BREAK_ALLIANCE = 0x40CC1A

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
ALLIED_DAYS, ALLIED_PLAYER = 0x3D, 0x41
# 越界写落点（allied_player == 0 时被误清的两格）
OOB_LO, OOB_HI = 0x496B3D, 0x496B41

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<52} 实际 {got_s!s:<20} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    def break_(self, target, allied=(0, 0, 0, 0), days=(1, 1, 1, 1),
               oob=(0xAA, 0xBB)):
        def setup(emu):
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + ALLIED_PLAYER, allied[i])
                emu.write8(base + ALLIED_DAYS, days[i])
            emu.write8(OOB_LO, oob[0])
            emu.write8(OOB_HI, oob[1])

        self.emu.call(BREAK_ALLIANCE, [target], setup=setup)
        return {
            "allied": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + ALLIED_PLAYER)
                       for i in range(4)],
            "days": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + ALLIED_DAYS)
                     for i in range(4)],
            "oob": (self.emu.read8(OOB_LO), self.emu.read8(OOB_HI)),
        }


def main():
    print("差分测试 #13：解除同盟 0x0040cc1a(player)\n")
    f = F()

    print("[1] 双向清空：自己与盟友各两格")
    r = f.break_(0, allied=(3, 0, 1, 0), days=(7, 5, 9, 5))
    case("p0↔p2：p0 的 +0x41/+0x3d 都清 0", (r["allied"][0], r["days"][0]), (0, 0))
    case("           p2 的 +0x41/+0x3d 都清 0", (r["allied"][2], r["days"][2]), (0, 0))
    case("           无关玩家（p1/p3）一动不动",
         (r["allied"][1], r["days"][1], r["allied"][3], r["days"][3]), (0, 5, 0, 5))

    print("\n[2] ★ 不检查对方是否「指回自己」")
    r = f.break_(0, allied=(2, 3, 0, 0), days=(7, 5, 4, 4))
    case("p0→p1（值 2），但 p1 自己→p2（值 3）：p1 照样被清",
         (r["allied"][1], r["days"][1]), (0, 0))
    case("   p2 不受影响（不追链）", (r["allied"][2], r["days"][2]), (0, 4))

    print("\n[3] ★ 只清一层：盟友的「盟友」不动")
    r = f.break_(0, allied=(3, 0, 4, 0), days=(7, 9, 8, 6))
    case("p0→p2、p2→p3：清 p0/p2，p3 保持",
         (r["days"][0], r["days"][2], r["days"][3]), (0, 0, 6))
    case("   p3 的 +0x41（值 0）也保持", r["allied"][3], 0)

    print("\n[4] 自指（allied_player = 自己+1）→ 无害地清自己两次")
    r = f.break_(0, allied=(1, 0, 0, 0), days=(7, 5, 5, 5))
    case("p0 自指：自己的两格清 0，别人不动",
         (r["allied"][0], r["days"][0], r["days"][1]), (0, 0, 5))

    print("\n[5] ★★ `allied_player == 0`：**没有护栏**，越界清掉两格")
    r = f.break_(0, allied=(0, 0, 0, 0), days=(7, 5, 5, 5))
    case("自己两格照清", (r["allied"][0], r["days"][0]), (0, 0))
    case("★ 越界落点 0x496B3D / 0x496B41 被清成 0（实测）", r["oob"], (0, 0))
    case("   对照：有盟友时这两格不动（见 [1] 的 oob 未被检查）",
         f.break_(0, allied=(3, 0, 1, 0), oob=(0xAA, 0xBB))["oob"], (0xAA, 0xBB))

    print("\n[6] 下标 3 也走同一条路（越界落点是算出来的，与调用者下标无关）")
    r = f.break_(3, allied=(0, 0, 0, 2), days=(5, 5, 5, 7))
    case("p3↔p1：p3 与 p1 都清", (r["days"][3], r["days"][1]), (0, 0))
    case("   有盟友 ⇒ 那两格不动", r["oob"], (0xAA, 0xBB))
    r = f.break_(3, allied=(0, 0, 0, 0), days=(5, 5, 5, 7))
    case("★ 下标 3 且无盟友 ⇒ 同样越界到 0x496B3D/0x496B41",
         r["oob"], (0, 0))
    case("   自己（下标 3）的两格照清", (r["allied"][3], r["days"][3]), (0, 0))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
