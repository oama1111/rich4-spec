#!/usr/bin/env python3
"""
通道 2 差分测试 · **AI 出牌的个性闸门** `0x0041e69e`（84 B）

复刻侧对应 `packages/core/src/ai/personality.ts` 的 `personalityAllows(f7, personality, roll)`
（`@source 0x0041e69e`），调用点见 `ai/policy.ts:237`（卡）与 `:336`（道具）。
exe 里它是 `ai_use_card` 的**调度入口** —— 每个 AI 行为进来先过这一关。

## 语义（84 B 全文）

```
0x41e69e(cardId):                                  ; cdecl，1 个参数
    eax = [esp+4]                                  ; cardId
    dl  = byte [cardId*8 + 0x47fdf1]               ; ★ 卡表 +2 = 该卡的 f7
    eax = [0x49910c] * 0x68
    al  = byte [eax + 0x496b7f]                    ; ★ **当前玩家**的个性（+0x17）
    edx = edx - eax                                ; ★ diff = f7 − 个性（**可负**）
    eax = edx
    if (edx >= 2) { eax ^= edx; ret }              ; eax == edx ⇒ **返回 0**（从不）
    ; ── edx <= 1 ──
    if (edx != 1) {                                ; edx <= 0
        eax = cardId
        call [cardId*4 + 0x475324]                 ; ★ 卡效果跳表 ⇒ 返回它的返回值
        ret
    }
    ; ── edx == 1 ──
    call rand
    edx = eax % 3
    if (edx != 0) { eax = 0; ret }                 ; ★ 2/3 概率挡掉
    eax = cardId
    call [cardId*4 + 0x475324]
    ret
```

一句话：**`f7 − 个性 ≥ 2` ⇒ 从不；`== 1` ⇒ 三分之一概率；`≤ 0` ⇒ 照做。**
闸门放行时**返回卡效果处理器的返回值**，挡掉时**返回 0**。

★ 顺带确认一处此前只当"标量"用的全局：`0x41e6f2(n)` = `dword [0x48be58 + n*4]` ——
即 `0x48be58` 是**参数数组的基址**（`[0]` = 目标、`[1]` = 第二参数，如搶奪卡偷哪张）。
这与前面几轮在 `0x48be58`/`0x48be5c` 上的观察**一致**，此处只是把"数组"这件事写实。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x00475324 + cardId*4` | 30 张卡的**效果处理器跳表** | 全部指向 `STUB_BASE` 的一段小桩：记下 `eax`（= cardId）后返回哨兵 `0x1234`；`0x456f2d`（CRT `rand`）→ 数据槽 |

★ **为什么可以打桩跳表**：本测试要钉的是**闸门本身**（比较 + 1/3 摇号 + 是否转交），
不是任何一张卡的效果 —— 效果由各自的差分测试覆盖。桩把"有没有转交、转交给谁"
变成可断言的：`SLOT_LAST` 记到 cardId 就证明转交过。

跑法：cd rich4-spec && .venv/bin/python tests/test_personality_gate.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STUB_BASE, Emu  # noqa: E402

GATE = 0x41E69E
PRNG = 0x456F2D
PARAM_GETTER = 0x41E6F2

CUR = 0x49910C
CARD_TABLE = 0x47FDEF          # +0 价格 / +2 f7，步长 8
F7_OFF = 2
CARD_TABLE_BASE = 0x47FDF1     # ★ 闸门直接读这个绝对地址（= CARD_TABLE + 2）
CARD_FX_TABLE = 0x475324       # 卡效果跳表（dword × 卡号）
CARD_PARAM = 0x48BE58          # 参数数组基址：[0]=目标、[1]=第二参数

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_PERSONALITY = 0x17

RAND_SLOT = SCRATCH_BASE + 0x800
SLOT_LAST = SCRATCH_BASE + 0x820
RETVAL = 0x1234
UNSET = 0x5A5A5A5A
MAX_CARD = 31
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<64} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT) + b"\xC3")
        # 卡效果桩：EAX 进来时就是 cardId（调用点 0x41e6ea 前有 `mov eax,[esp+4]`）
        self.emu.patch(STUB_BASE,
                       b"\xA3" + struct.pack("<I", SLOT_LAST)        # mov [SLOT_LAST], eax
                       + b"\xB8" + struct.pack("<I", RETVAL)         # mov eax, RETVAL
                       + b"\xC3")                                    # ret
        self.clear()

    def clear(self):
        self.me = 0
        self.personality = 0
        self.f7 = {}                # cardId → f7
        self.rand = 0
        self.params = {}            # slot → value（给参数 getter 那几条用）

    def card(self, cid, f7):
        self.f7[cid] = f7
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(RAND_SLOT, self.rand & 0xFFFFFFFF)
        emu.write32(SLOT_LAST, UNSET)
        for i in range(4):
            emu.write8(PLAYER_BASE + i * PLAYER_STRIDE + P_PERSONALITY, 0)
        emu.write8(PLAYER_BASE + self.me * PLAYER_STRIDE + P_PERSONALITY, self.personality)
        # 卡表：f7 写在 +2；价格无关，留 0
        for cid in range(MAX_CARD + 1):
            emu.write8(CARD_TABLE + cid * 8, 0)
            emu.write8(CARD_TABLE_BASE + cid * 8, self.f7.get(cid, 0) & 0xFF)
        # 卡效果跳表 → 全部指向桩
        for cid in range(MAX_CARD + 1):
            emu.write32(CARD_FX_TABLE + cid * 4, STUB_BASE)
        # 参数数组
        for slot, v in self.params.items():
            emu.write32(CARD_PARAM + slot * 4, v & 0xFFFFFFFF)

    def run(self, cid):
        r = self.emu.call(GATE, [cid], setup=self._setup)
        self.ret = r["eax"]
        self.dispatched_to = self.emu.readu32(SLOT_LAST)
        return self

    @property
    def called(self):
        return self.dispatched_to != UNSET


def main():
    print("差分测试 · AI 出牌个性闸门 0x41e69e（84 B）\n")

    # ── A. 三条分支的边界 ──────────────────────────────────────────
    print("[A] `diff = f7 − 个性`：≥2 从不 / ==1 三分之一 / ≤0 照做")
    w = World()

    for f7, per, desc in [(5, 5, "diff = 0"), (5, 6, "diff = −1"), (5, 9, "diff = −4"),
                          (0, 0, "diff = 0（都是 0）"), (3, 255, "diff = −252")]:
        w.clear()
        w.personality = per
        w.card(7, f7)
        r = w.run(7)
        case(f"★ {desc}（f7={f7} 个性={per}）⇒ 照做", r.called, True)
        case("  返回卡处理器的返回值", r.ret, RETVAL)
        case("  转交时带的是同一个卡号", r.dispatched_to, 7)

    for f7, per, desc in [(7, 5, "diff = 2"), (9, 5, "diff = 4"), (255, 0, "diff = 255"),
                          (5, 3, "diff = 2")]:
        w.clear()
        w.personality = per
        w.card(7, f7)
        r = w.run(7)
        case(f"★ {desc}（f7={f7} 个性={per}）⇒ **从不**（返回 0）", r.ret, 0)
        case("  且**没有**转交给卡处理器", r.called, False)

    # ── B. diff == 1：三分之一 ─────────────────────────────────────
    print("\n[B] `diff == 1` ⇒ `rand() % 3 == 0` 才放行（三分之一）")
    for rand, want, why in [(0, True, "0%3=0"), (1, False, "1%3=1"), (2, False, "2%3=2"),
                            (3, True, "3%3=0"), (4, False, "4%3=1"), (5, False, "5%3=2"),
                            (6, True, "6%3=0"), (12345, True, "12345%3=0"),
                            (12344, False, "12344%3=2")]:
        w.clear()
        w.personality = 5
        w.card(7, 6)          # diff = 1
        w.rand = rand
        r = w.run(7)
        case(f"rand={rand}（{why}）⇒ {'放行' if want else '挡掉'}", r.called, want)
        case("  返回值", r.ret, RETVAL if want else 0)

    # ── C. 边界：diff 恰好 0 / 1 / 2 ───────────────────────────────
    print("\n[C] ★ 三条分支的**边界**（0 / 1 / 2）在同一个个性下逐一验")
    w.clear()
    w.personality = 5
    w.rand = 1                    # 1%3 != 0 ⇒ diff==1 必定被挡
    for f7, want_called, want_ret, why in [
        (4, True, RETVAL, "diff = −1 ⇒ 照做"),
        (5, True, RETVAL, "diff = 0 ⇒ 照做"),
        (6, False, 0, "diff = 1 且 rand%3≠0 ⇒ 挡"),
        (7, False, 0, "diff = 2 ⇒ 从不"),
    ]:
        w.clear()
        w.personality = 5
        w.rand = 1
        w.card(7, f7)
        r = w.run(7)
        case(f"f7={f7}（{why}）", (r.called, r.ret), (want_called, want_ret))

    w.clear()
    w.personality = 5
    w.rand = 3                    # 3%3 == 0 ⇒ diff==1 放行
    w.card(7, 6)
    r = w.run(7)
    case("f7=6（diff = 1）且 rand=3（3%3=0）⇒ 放行", (r.called, r.ret), (True, RETVAL))

    # ── D. 个性取自**当前玩家** ─────────────────────────────────────
    print("\n[D] 个性读的是 **当前玩家**（`[0x49910c]`）的 `+0x17`，不是 0 号玩家")
    for me, per, f7, want in [(0, 5, 6, False), (2, 5, 6, False), (3, 9, 6, True),
                              (1, 0, 5, False), (2, 255, 5, True)]:
        w.clear()
        w.me = me
        w.personality = per
        w.card(7, f7)
        w.rand = 1                # 让 diff==1 时必定被挡，结论只由 diff 决定
        r = w.run(7)
        gap = f7 - per
        want_called = gap <= 0
        case(f"当前玩家={me}、个性={per}、f7={f7}（diff={gap}）⇒ "
             f"{'照做' if want_called else '挡掉'}", r.called, want_called)

    # ── E. 挡掉时返回 0，放行时返回处理器的值 ──────────────────────
    print("\n[E] 返回值语义：挡掉 ⇒ 0；放行 ⇒ 卡处理器的返回值")
    w.clear()
    w.card(7, 1)
    w.personality = 0
    r = w.run(7)
    case("★ diff = 1、rand=0 ⇒ 放行，返回处理器值（不是 1）", r.ret, RETVAL)

    w.clear()
    w.card(7, 2)
    w.personality = 0
    r = w.run(7)
    case("★ diff = 2 ⇒ 挡，返回 0（即使处理器会返回 0x1234）", r.ret, 0)

    # ── F. 卡号不同 ⇒ 查的是那张卡的 f7 ────────────────────────────
    print("\n[F] f7 按**卡号**查（`0x47fdf1 + 卡号*8`），且转交的是同一个卡号")
    w.clear()
    w.personality = 5
    w.card(3, 5).card(9, 99)
    r = w.run(3)
    case("卡 3 的 f7=5（diff 0）⇒ 放行", r.called, True)
    case("  转交的卡号 = 3", r.dispatched_to, 3)

    w.clear()
    w.personality = 5
    w.card(3, 5).card(9, 99)
    r = w.run(9)
    case("★ 同一局里卡 9 的 f7=99（diff 94）⇒ 挡掉", r.called, False)

    w.clear()
    w.personality = 5
    w.card(1, 6).card(2, 6)
    w.rand = 1
    r = w.run(1)
    a = r.called
    w.rand = 3
    r = w.run(2)
    b = r.called
    case("★ 两个卡号、同一 f7、同一 rand ⇒ 结论相同（不串号）", (a, b), (False, True))

    # ── G. 顺带：参数数组 getter 0x41e6f2 ─────────────────────────
    print("\n[G] ★ 顺带确认 `0x41e6f2(n)` = `dword [0x48be58 + n*4]`（参数**数组**）")
    w.clear()
    w.params = {0: 0x8004, 1: 7, 2: 0xDEAD}
    for slot, want in [(0, 0x8004), (1, 7), (2, 0xDEAD)]:
        r = w.emu.call(PARAM_GETTER, [slot], setup=w._setup)
        case(f"参数槽 {slot} ⇒ {want}", r["eax"], want)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
