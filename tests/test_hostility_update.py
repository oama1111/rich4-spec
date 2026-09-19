#!/usr/bin/env python3
"""
通道 2 差分测试 #16 · `0x0040df69(a, b, delta)` —— **更新敌意（含解除同盟）**

规格来源：`gen/db.txt`（本函数全文 38 条）+ `docs/systems/ai.md`、
`docs/systems/cards.md`（`player+0x41` = `allied_player`，1 基、0 = 无）。

```asm
0040df69  push ebx / push edi
0040df6b  edx = [esp+0xc]                  ; arg1 = a
0040df6f  ebx = [esp+0x10]                 ; arg2 = b
0040df73  cmp edx, ebx / je end            ; ★ a == b 直接返回
0040df77  cmp dword [esp+0x14], 0 / jge 继续
0040df7e  eax = a*0x68
0040df83  cmp dword [eax + b*4 + 0x496bb4], 0 / je end   ; ★ 负增量且当前为 0 → 返回
0040df8d  edi = hostility[a][b]            ;   （+0x4c，4 个 dword）
0040df9b  edi += delta
0040dfa3  hostility[a][b] = edi
0040dfa9  test edi, edi / jge 跳过
0040dfad  hostility[a][b] = 0              ; ★ 只有下限 0，**没有上限**
0040dfb5  cmp dword [esp+0x14], 0 / jle end
0040dfbc  cl = byte [a + 0x41]             ; a 的同盟对象（1 基）
0040dfca  cmp ecx, ebx+1 / jne end
0040dfce  push edx / call 0x40cc1a         ; ★ 敌意**上升**且 b 是 a 的盟友 → 拆盟
```

★ 本用例验到的六条：
1. `a == b` 直接返回（连同盟都不看）；
2. 加减都对，**只有下限 0、没有上限**；
3. 负增量且当前已为 0 ⇒ 走提前返回（结果与"加到负数再夹"一致，但路径不同）；
4. 只动 `hostility[a][b]` 那一格，别的格不受影响；
5. ★ 同盟解除的**三个条件同时成立**才触发：`delta > 0` ∧ `allied[a] == b+1` ∧ `b != a`；
   `delta <= 0` 时**不拆**（这正是原版把 `cmp delta,0 / jle` 单独写一遍的原因）；
6. ★★ 原版对 `b` **没有上界检查**：`b = 4` 会写到 `+0x5c`（= `monthlyPaid`），
   而且和正常路径一样是**在旧值上累加**（`0x11111111 → 0x11111114`，不是覆盖）。
   复刻 `rules/hostility.ts` 加了 `b >= HOSTILITY_COUNT` 护栏，登记为**有意偏离**
   （实际调用点都只遍历 0..3，构造上不可达）。

★ 另一条**被本测试纠正**的直觉：「a 的盟友是自己」不可能触发拆盟 ——
  判据是 `allied[a] == b+1`，要 `allied[a] == a+1` 就得 `b == a`，而 `a == b` 已先返回。

跑法：cd rich4-spec && .venv/bin/python tests/test_hostility_update.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

UPDATE_HOSTILITY = 0x40DF69

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
HOSTILITY_OFF = 0x4C          # 4 个 dword
ALLIED_DAYS, ALLIED_PLAYER = 0x3D, 0x41
NEXT_AFTER_HOSTILITY = 0x5C   # 玩家 0 的 +0x5c = monthlyPaid（b=4 时被越界写的那一格）

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

    def upd(self, a, b, delta, host=None, allied=(0, 0, 0, 0), days=(1, 1, 1, 1),
            tail=0x11111111):
        host = host or {}
        tail0 = tail

        def setup(emu):
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                for j in range(4):
                    emu.write32(base + HOSTILITY_OFF + 4 * j, int(host.get((i, j), 0)))
                emu.write8(base + ALLIED_PLAYER, allied[i])
                emu.write8(base + ALLIED_DAYS, days[i])
            emu.write32(PLAYER_BASE + NEXT_AFTER_HOSTILITY, tail0)

        self.emu.call(UPDATE_HOSTILITY, [a, b, delta], setup=setup)
        return {
            "h": [[self.emu.read32(PLAYER_BASE + i * PLAYER_STRIDE + HOSTILITY_OFF + 4 * j)
                   for j in range(4)] for i in range(4)],
            "allied": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + ALLIED_PLAYER)
                       for i in range(4)],
            "days": [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + ALLIED_DAYS)
                     for i in range(4)],
            "tail": self.emu.read32(PLAYER_BASE + NEXT_AFTER_HOSTILITY),
        }


def main():
    print("差分测试 #16：更新敌意 0x0040df69(a, b, delta)\n")
    f = F()

    print("[1] 加减与下限")
    r = f.upd(0, 1, 7, host={(0, 1): 5})
    case("5 + 7 = 12", r["h"][0][1], 12)
    r = f.upd(0, 1, -3, host={(0, 1): 5})
    case("5 − 3 = 2", r["h"][0][1], 2)
    r = f.upd(0, 1, -9, host={(0, 1): 5})
    case("5 − 9 → 夹到 0（只有下限）", r["h"][0][1], 0)
    r = f.upd(0, 1, -1, host={(0, 1): 0})
    case("0 − 1 → 提前返回，仍是 0", r["h"][0][1], 0)

    print("\n[2] ★ 没有上限：正增量可以超过 100")
    r = f.upd(0, 1, 500, host={(0, 1): 0})
    case("0 + 500 = 500（原版不封顶）", r["h"][0][1], 500)
    r = f.upd(2, 3, 120, host={(2, 3): 95})
    case("95 + 120 = 215", r["h"][2][3], 215)

    print("\n[3] 只动 [a][b] 那一格")
    r = f.upd(1, 2, 9, host={(1, 0): 3, (1, 1): 4, (1, 2): 5, (1, 3): 6, (0, 2): 7})
    case("h[1][2] 5→14", r["h"][1][2], 14)
    case("h[1] 其余三格不变", (r["h"][1][0], r["h"][1][1], r["h"][1][3]), (3, 4, 6))
    case("h[0][2] 不受影响", r["h"][0][2], 7)

    print("\n[4] a == b：直接返回")
    r = f.upd(2, 2, 9, host={(2, 2): 4}, allied=(0, 0, 3, 0), days=(1, 1, 7, 1))
    case("h[2][2] 保持 4", r["h"][2][2], 4)
    case("   连同盟都不看（+0x41/+0x3d 不动）",
         (r["allied"][2], r["days"][2]), (3, 7))

    print("\n[5] ★ 同盟解除：三个条件同时成立才拆")
    r = f.upd(0, 1, 5, host={(0, 1): 0}, allied=(2, 0, 1, 0), days=(7, 5, 9, 5))
    case("a=0 的盟友是 1（b+1=2）且 Δ>0 ⇒ 拆", (r["allied"][0], r["days"][0]), (0, 0))
    case("   盟友那侧也被清（0x40cc1a 是双向的）",
         (r["allied"][1], r["days"][1]), (0, 0))
    case("   敌意照样加上", r["h"][0][1], 5)

    r = f.upd(0, 1, -1, host={(0, 1): 5}, allied=(2, 0, 1, 0), days=(7, 5, 9, 5))
    case("★ Δ<0 时**不**拆盟", (r["allied"][0], r["days"][0]), (2, 7))

    r = f.upd(0, 1, 0, host={(0, 1): 5}, allied=(2, 0, 1, 0), days=(7, 5, 9, 5))
    case("★ Δ=0 时也不拆", (r["allied"][0], r["days"][0]), (2, 7))

    r = f.upd(0, 1, 5, host={(0, 1): 0}, allied=(3, 0, 0, 1), days=(7, 5, 5, 8))
    case("★ 盟友不是 b（a 的盟友是 2）⇒ 不拆", (r["allied"][0], r["days"][0]), (3, 7))

    r = f.upd(0, 1, 5, host={(0, 1): 0}, allied=(1, 0, 0, 0), days=(7, 5, 5, 5))
    case("★ 盟友栏 = 1（自己）而 b=1 ⇒ 判据 1 == b+1 = 2 ⇒ **不拆**",
         (r["allied"][0], r["days"][0]), (1, 7))
    case("   （「自己和自己结盟」不可能触发：那需要 b = 0，而 a==b 已先返回）",
         r["h"][0][1], 5)

    print("\n[6] ★★ 原版对 b 没有上界检查：b=4 越界写到 +0x5c（monthlyPaid）")
    r = f.upd(0, 4, 3, tail=0)
    case("b=4 而 +0x5c 原本是 0 ⇒ 被写成 0 + 3 = 3", r["tail"], 3)
    r = f.upd(0, 4, 3, tail=0x11111111)
    case("   ★ 它是**在旧值上累加**（不是覆盖）：0x11111111 + 3", r["tail"], 0x11111114)
    r = f.upd(0, 3, 3, tail=0x11111111)
    case("对照：b=3（最后一格）不动 +0x5c", r["tail"], 0x11111111)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
