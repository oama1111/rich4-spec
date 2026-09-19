#!/usr/bin/env python3
"""
通道 2 差分测试 #21 · 「神明/跟班」两支小函数

- `0x0040fbb8(player)` —— 找一个**身上带着神 14 / 15 的别的玩家**（找不到返回 −1）
- `0x0040fc00(player)` —— 把玩家身上两个跟班物件（`+0x3f` / `+0x40`）的**所在格**
  同步成玩家所在格

规格来源：`gen/db.txt` + `docs/systems/gods.md`（`0x40fc00` 的用途已登记；
`0x40fbb8` 此前只在清单里列名、用途未定）+ `docs/systems/save-scalars.md` §2.2
（`0x499114` = **玩家人数**）。

## 一、`0x40fbb8(player)` —— 找「带着 14/15 号神的别人」

```asm
0040fbba  ecx = arg = player ; ebx = −1
0040fbc5  esi = [0x499114]                      ; ★ 循环上界 = **玩家人数**
0040fbcf  for (edx = 0; edx < esi; edx++):
            if (edx == arg) continue            ; 不算自己
            if (player[edx].+0x15 == 0) continue ; 出局者不算
            if (player[edx].+0x3f == 14 || == 15) → return edx
0040fbfb  return −1
```

★ 全 exe 只有 `0x41af99`（企業落点收尾）用它：找到就把那位的名字拿出来拼一句话
（`0x4639cc`），——所以它是**「谁的神顯靈」那句话的选人器**。

## 二、`0x40fc00(player)` —— 跟班跟着走

```asm
0040fc01  edx = player*0x68
0040fc06  ah = byte [player+0x3f]                ; god_info
0040fc0e  if (ah != 0):
             ecx = ah − 1                        ; 物件下标
             eax = ecx*24
             dx = word [player+0x0c]             ; nodeId
             word [eax*8 + 0x496d0a] = dx        ; ★ objects[下标].nodeId = 玩家所在格
0040fc30  bl = byte [player+0x40]                ; f64（另一个跟班槽）
0040fc38  if (bl != 0): 同上
```

★ **两支互相独立**（`+0x3f == 0` 只跳过第一支，不影响 `+0x40`）；
调用点：入监 `0x43d593`（`0x43d668`）与入院 `0x43ec3f` —— 即**被关押时神明/跟班一起搬走**。

跑法：cd rich4-spec && .venv/bin/python tests/test_god_follow.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

FIND_CARRIER = 0x40FBB8
SYNC_ESCORT = 0x40FC00

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_WHO, P_GOD, P_F64 = 0x0C, 0x15, 0x3F, 0x40
PLAYER_COUNT = 0x499114
OBJ_BASE, OBJ_STRIDE, OBJ_COUNT = 0x496D08, 24, 46
OBJ_NODE = 0x02

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got_s!s:<14} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    # ---------- 0x40fbb8 ----------
    def find(self, arg, gods=(0, 0, 0, 0), who=(1, 1, 1, 1), count=4):
        def setup(emu):
            emu.write32(PLAYER_COUNT, count)
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + P_WHO, who[i])
                emu.write8(base + P_GOD, gods[i])

        out = self.emu.call(FIND_CARRIER, [arg], setup=setup)
        return out["signed"]

    # ---------- 0x40fc00 ----------
    def sync(self, idx, god=0, f64=0, node_id=42, pre=None):
        pre = pre or {}

        def setup(emu):
            for i in range(OBJ_COUNT):
                emu.write16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE, int(pre.get(i, 0)))
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write8(base + P_GOD, god)
            emu.write8(base + P_F64, f64)
            emu.write16(base + P_NODE, node_id)

        self.emu.call(SYNC_ESCORT, [idx], setup=setup)
        e = self.emu
        return [e.read16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE) for i in range(OBJ_COUNT)]


def main():
    print("差分测试 #21：神明/跟班 —— 0x40fbb8 找携带者 ＋ 0x40fc00 同步所在格\n")
    f = F()

    print("[1] 0x40fbb8：找 +0x3f ∈ {14,15} 的**别人**")
    case("gods=(0,14,0,0), arg=0 ⇒ 返回 1", f.find(0, gods=(0, 14, 0, 0)), 1)
    case("gods=(0,15,0,0), arg=0 ⇒ 返回 1（15 也算）", f.find(0, gods=(0, 15, 0, 0)), 1)
    case("gods=(0,13,0,0) ⇒ −1（别的神不算）", f.find(0, gods=(0, 13, 0, 0)), -1)
    case("gods=(0,0,0,0) ⇒ −1", f.find(0, gods=(0, 0, 0, 0)), -1)
    case("★ 携带者就是自己（arg=1, gods[1]=14）⇒ 跳过自己 ⇒ −1", f.find(1, gods=(0, 14, 0, 0)), -1)
    case("★ 携带者已出局（who[1]=0）⇒ 跳过 ⇒ −1", f.find(0, gods=(0, 14, 0, 0), who=(1, 0, 1, 1)), -1)
    case("★ 循环上界 = [0x499114]：count=1 时看不到玩家 1 ⇒ −1",
         f.find(0, gods=(0, 14, 0, 0), count=1), -1)
    case("   count=2 时看得到 ⇒ 1", f.find(0, gods=(0, 14, 0, 0), count=2), 1)
    case("两个都带（gods=(14,0,0,15)）⇒ 取**下标最小**的 0",
         f.find(3, gods=(14, 0, 0, 15)), 0)

    print("\n[2] 0x40fc00：把跟班物件的所在格同步成玩家所在格")
    r = f.sync(1, god=3, f64=0, node_id=42)
    case("god=3 ⇒ objects[2].nodeId = 42", r[2], 42)
    case("   别的槽不动", (r[0], r[1], r[3]), (0, 0, 0))
    r = f.sync(1, god=0, f64=5, node_id=7)
    case("f64=5 ⇒ objects[4].nodeId = 7", r[4], 7)
    case("   objects[2] 不动", r[2], 0)
    r = f.sync(0, god=1, f64=2, node_id=9)
    case("两支都非 0 ⇒ objects[0] 与 [1] 都同步", (r[0], r[1]), (9, 9))
    r = f.sync(2, god=0, f64=0, node_id=5, pre={0: 8, 1: 8, 2: 8, 3: 8})
    case("★ 两个都是 0 ⇒ 一个都不动", (r[0], r[1]), (8, 8))
    r = f.sync(2, god=0, f64=4, node_id=5, pre={0: 8, 1: 8, 2: 8, 3: 8})
    case("★ +0x3f==0 只跳过第一支，第二支照做", (r[0], r[3]), (8, 5))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
