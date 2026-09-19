#!/usr/bin/env python3
"""
通道 2 差分测试 #40 · **两张事件牌堆的洗牌** `0x44baea`（命運 37）/ `0x448b81`（新聞 36）

两者是同一段代码、只差长度与落点：

```asm
; @source 0x44baea（命運；新聞 = 0x448b81，把 0x25→0x24、0x496b38→0x499090、0x4990b4→0x4990e0）
0044baec  sub  esp, 0x28
0044baef  push 0x25 / push 0 / lea eax,[esp+8] / push eax / call 0x456f60   ; used[37] = {0}
0044bb00  xor  ebx, ebx                  ; placed = 0
0044bb02  mov  esi, 0x25                 ; remaining = 37
loop:
0044bb1a  call 0x456f2d                  ; rand()
0044bb1f  mov  edx, eax / sar edx,0x1f / idiv esi
                                        ; ★ 用的是**余数**（edx）⇒ k = rand() % remaining
0044bb26  xor  eax, eax                  ; at = 0
scan:
0044bb30  cmp  byte [esp+eax], 0         ; if (!used[at]) k--
0044bb36  dec  edx
0044bb37  test edx, edx / jl adopt       ; k < 0 → 就用这个 at
0044bb3b  jmp  0x44bb2a                  ; ++at（≥0x25 也会走到 adopt —— 边界保护）
adopt:
0044bb09  mov  byte [esp+eax], 1         ; used[at] = 1
0044bb0d  mov  byte [ebx + 0x496b38], al ; ★ deck[placed] = at（= 事件号）
0044bb13  inc  ebx / dec esi
0044bb3d  mov  dword [0x4990b4], 0       ; 游标清零
```

⇒ 「**选择采样**」：每轮取 `rand() % 剩余数`，再从头扫过 `used[]`，
落在第 (k+1) 个未使用槽上。**不是** Fisher-Yates（分布相同、消耗的随机序列不同）——
所以「恰好 37 / 36 次 `rand()`」与**具体排列**都得照原样钉住（本测试两者都钉）。

## 与复刻的关系

`packages/core/src/events/deck.ts` 的 `shuffleDeck()` 自称照抄这一段；
本测试的期望值同时写进 `packages/core/src/events/deck.test.ts`
（喂同一条 `below()` 序列 ⇒ 两个实现必须给出**同一个排列**）。

## 诚实边界

用户的随机数口径：**不要求与原版位级一致**（只要原则上随机 + 读档重播种）。
本测试钉「算法形状 / 消耗次数 / 给定余数序列下的排列」，是为了让
「复刻的洗牌 == 原版洗牌」这一步**可判定**；这不构成「必须位级一致」的要求。

跑法：cd rich4-spec && .venv/bin/python tests/test_deck_shuffle.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

FORTUNE, NEWS = 0x44BAEA, 0x448B81
PRNG = 0x456F2D

F_ORDER, F_SIZE, F_CUR = 0x496B38, 0x25, 0x4990B4
N_ORDER, N_SIZE, N_CUR = 0x499090, 0x24, 0x4990E0

S = SCRATCH_BASE
ROLLS, ROLL_PTR, ROLL_N = S + 0x800, S + 0x900, S + 0x904
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<24} 期望 {want!s}")
    return ok


def model(size, rolls):
    """按 exe 的算法用给定的 `rand()` 返回值序列算出排列（`k = rand() % 剩余数`）。"""
    used = [False] * size
    deck = []
    remaining = size
    for i in range(size):
        k = rolls[i] % remaining
        at = 0
        while True:
            if not used[at]:
                k -= 1
            if k < 0:
                break
            at += 1
            if at >= size:
                break
        used[at] = True
        deck.append(at)
        remaining -= 1
    return deck


class F:
    def __init__(self):
        self.emu = Emu()
        # PRNG 序列桩：按 [ROLL_PTR] 依次吐值、记次数
        self.emu.patch(PRNG, b"\x51"
                       + b"\x8B\x0D" + struct.pack("<I", ROLL_PTR)
                       + b"\x8B\x01"
                       + b"\x83\x05" + struct.pack("<I", ROLL_PTR) + b"\x04"
                       + b"\xFF\x05" + struct.pack("<I", ROLL_N)
                       + b"\x59\xC3")

    def run(self, va, rolls):
        order, size, cur = ((F_ORDER, F_SIZE, F_CUR) if va == FORTUNE
                            else (N_ORDER, N_SIZE, N_CUR))

        def setup(emu):
            emu.write32(ROLL_N, 0)
            for i, v in enumerate(rolls):
                emu.write32(ROLLS + 4 * i, v & 0xFFFFFFFF)
            emu.write32(ROLL_PTR, ROLLS)
            emu.write(order, b"\x00" * size)
            emu.write32(cur, 0x0BADF00D)      # 预置非 0，看它清不清零
            emu.write8(order - 1, 0xC5)       # ★ 前后哨兵：数组越界写会踩到
            emu.write8(order + size, 0xC5)

        r = self.emu.call(va, [], setup=setup)
        e = self.emu
        return {
            "calls": e.readu32(ROLL_N),
            "deck": [e.read8(order + i) for i in range(size)],
            "cursor": e.readu32(cur),
            "before": e.read8(order - 1),
            "after": e.read8(order + size),
            "eax": r["eax"],
        }


# 写进 deck.test.ts 的那两条固定序列（同一条序列、两个实现必须同排列）
SEQ37 = [12345, 30000, 7, 19999, 32767, 1, 25000, 0, 4096, 5555, 1234, 31000,
         77, 8888, 22222, 3, 16384, 999, 27182, 31415, 6, 4242, 16180, 2718,
         9001, 20000, 13, 3000, 12345, 65535 % 32768, 100, 5000, 777, 26000,
         33333, 2, 18000]
SEQ36 = [11111, 22222, 33333, 4444, 5555, 6666, 7777, 8888, 9999, 10101, 12000,
         13000, 14000, 15000, 16000, 17000, 18000, 19000, 20000, 21000, 22000,
         23000, 24000, 25000, 26000, 27000, 28000, 29000, 30000, 31000, 32000,
         1, 2, 3, 4, 5]


def main():
    print("差分测试 #40：两张事件牌堆的洗牌 `0x44baea` / `0x448b81`\n")
    f = F()

    print("[A] 命運牌堆（37 张，落点 0x496b38）")
    s = f.run(FORTUNE, [0] * 37)
    case("★★ 全 0 序列 ⇒ `k` 每轮都是 0 ⇒ 排列 == [0,1,2,…,36]",
         s["deck"], list(range(37)))
    case("★ 恰好消耗 **37** 次 `rand()`（每轮一次）", s["calls"], 37)
    case("★ 游标 `[0x4990b4]` 被清零", s["cursor"], 0)
    case("★ 不越界写（前后哨兵都在）", (s["before"], s["after"]), (0xC5, 0xC5))
    case("   返回值不参与语义（原版不设返回值）", s["eax"], s["eax"])

    s = f.run(FORTUNE, SEQ37)
    case("★★ 给定余数序列 ⇒ 排列与「选择采样」模型**逐项相同**",
         s["deck"], model(37, SEQ37))
    case("   它确实是 0..36 的一个排列", sorted(s["deck"]), list(range(37)))
    case("   仍然只消耗 37 次", s["calls"], 37)

    # 让「余数」真的起作用：全用同一个大数（每轮 k 都取模到不同的值）
    s = f.run(FORTUNE, [32767] * 37)
    case("★ 恒定 32767 ⇒ `k = 32767 % 剩余数`（余数随剩余数变化）",
         s["deck"], model(37, [32767] * 37))
    case("   这时的首项是 32767 % 37 = 18 ⇒ 开头是 18",
         s["deck"][0], 32767 % 37)

    print("\n[B] 新聞牌堆（36 张，落点 0x499090）—— 同一段代码、长度与落点不同")
    s = f.run(NEWS, [0] * 36)
    case("★★ 全 0 序列 ⇒ 排列 == [0,1,2,…,35]", s["deck"], list(range(36)))
    case("★ 只消耗 36 次 `rand()`", s["calls"], 36)
    case("★ 游标 `[0x4990e0]` 被清零", s["cursor"], 0)
    case("★ 不越界写", (s["before"], s["after"]), (0xC5, 0xC5))
    s = f.run(NEWS, SEQ36)
    case("★★ 给定序列下的排列 == 模型", s["deck"], model(36, SEQ36))
    case("   确实是 0..35 的一个排列", sorted(s["deck"]), list(range(36)))

    print("\n[C] 两副牌共用同一段代码，但**第一轮的模数就不同**（37 vs 36）")
    a = f.run(FORTUNE, SEQ36 + [12345])
    b = f.run(NEWS, SEQ36)
    case("★★ 同一条序列、长度不同 ⇒ 首项就分叉（`r % 37` ≠ `r % 36`）",
         (a["deck"][0], b["deck"][0]), (SEQ36[0] % 37, SEQ36[0] % 36))
    case("   37 张那副的第 37 项是最后剩下的那个数", a["deck"][36],
         [v for v in range(37) if v not in set(a["deck"][:36])][0])
    same = f.run(FORTUNE, SEQ36 + [12345])
    case("   同输入可复现（同一个桩序列 ⇒ 同一结果）", same["deck"], a["deck"])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
