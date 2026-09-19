#!/usr/bin/env python3
"""
通道 2 差分测试 · **月度奖项评分 /「本月悲情人物」评选** `0x00437D1A`（228 B）

复刻侧对应两处**逐行相同**的实现：
  · `rich4-remake/packages/core/src/rules/monthly.ts:130` `monthlyScore()`
    （核心，**无生产调用点**，只有 `monthly.test.ts` 在喂它）
  · `rich4-remake/packages/client/src/monthly-screen.ts:850` `awardScore()`
    （客户端**复制**了一份，被 `monthlyAward()` @ `:944` 生产调用）

## 调用者（★ 本测试纠正了规格里的「死码」结论）

任务书与 `docs/systems/gods.md` §八.5 / `docs/gaps/README.md` §7.19 都写
「`0x437d1a` **全档无任何呼叫点**，疑似死码」。**实测推翻**：

```
$ python3 tools/disasm.py callers 0x437d1a
# call 0x00437d1a 的调用点，共 1 处
  ── 0x00438240
$ python3 -c '...' rich4-spec/gen/rel32-calls.json
"0x00437d1a": ["0x00438240"]
```

字节级核对（`Rich4/rich4.exe`，AUTO 段 `off = VA - 0x400000 - 0xC00`）：

```
0x00438239  2e ff 15 f8 22 46 00   call dword cs:[0x4622f8]   ; 长 7 字节，正好到 0x43823f
0x00438240  e8 d5 fa ff ff         call 0x437d1a              ; rel32 = 0xfffffad5 → 0x438245-0x52b
0x00438245  a2 2f c4 48 00         mov  byte [0x48c42f], al   ; ★ 返回值立刻落全局
0x0043824a  call 0x437dfe                                     ; 首富评选
0x0043824f  mov  byte [0x48c430], al
```

返回值 `[0x48c42f]` 是真被消费的（**玩家可见**）：

```
0x00438536  mov al, byte [0x48c42f]
0x0043853b  mov al, byte [eax + 0x48c418]   ; ★ 返回值是**候选表下标**，再映射回玩家 id
0x00438546  imul eax, eax, 0x68
0x00438549  mov al, byte [eax + 0x496b7b]   ; 获奖者角色号 → 立绘/FLIC
```

同一处链路上 `0x48c42a`（状态机）被置 `6`，而 `0x439196` 用
`jmp dword [eax*4 + 0x437e35]`（表项 0..5 = `0x4391ee/0x43930f/0x4394cd/0x4396a8/
0x4395c2/0x4396d7`）按 `[0x48c42d]` 分派 —— 是月结屏状态机的**常规一支**。
更上游：`0x439bfa`（月度结算主流程）在 `0x00439ea8` 用
`push 0; push 0x437e61; call 0x4018e7` 进入装得下本函数的那个大函数
（`0x437e61`，3957 B；`gen/functions.json` 因 root=`speculative` 而 callers 为空，
是**工具口径**问题，不是没有调用者）。

⇒ **结论：不是死码**；`+0x44`（衰運）因此**影响玩法**（决定颁奖屏上「本月悲情人物」是谁），
`docs/gaps/README.md` §7.19「`+0x44` 唯一读者是那个死函数 ⇒ 神明三项修正对玩法仍无影响」
这句的后半**不成立**。

## 语义（228 B 全程读完）

函数**无参数**，只读全局与玩家记录（`gen/functions.json` 的 `reads` 恰为本表 8 项，
`writes` 为空 ⇒ **打桩清单为空，全部真跑**）：

```
0x437d1a():
    n = byte [0x48c420]                       ; 候选人数（0x439caa 按 whoPlays 铺的）
    best = 0 ; bestAt = 0 ; best = -1
    for i in 0 .. n-1:
        pid = byte [0x48c418 + i]             ; 候选表（生产时 = 在场玩家，升序）
        p   = 0x496b68 + pid*0x68             ; 玩家记录
        score[i] = (dword [p+0x5c] - dword [p+0x60])          ; 意外損失 − 意外之財
                 +  byte [p+0x42] * dword [0x4990e8] * 0x9c4  ; 倒楣天數 × 物價 × 2500
                 +  (int16) word [p+0x44] * 10                ; 衰運 × 10   ★ movsx！
        if best < 0: best = 0                 ; 0x437d80 test/jge：负的「当前最大」先夹到 0
        if best < score[i]: best = score[i] ; bestAt = i
    if best == 0: return -1                    ; 0x437dc9 test ecx,ecx / je
    second = 0
    for i in 0 .. n-1:
        if score[i] == best: score[i] = 0     ; ★ 等于最高分的**全部**清零
        if second < score[i]: second = score[i]
    if second == 0: return -1                 ; 0x437dcd test ebx,ebx / je
    if (best - second) / best <= 0.4: return -1   ; x87 fdivp + fcomp [0x464d58] + jbe
    return bestAt                             ; = 候选表下标（不是玩家 id）
```

★ 三处**不是常识**的地方，本测试逐条钉死：

1. `+0x44` 是 **`movsx` 有符号 16 位**（`0x437d6a`），不是零扩展；而
   `monthly.ts:104` 的接口注释写的是 `(uint16)` —— 见报告里的差异项。
2. 返回值是 **候选表下标**，不是玩家 id（`0x437d94 mov edi,eax` 里 `eax` 是循环变量）。
3. `[0x464d58]` 实测 = **0.4**（`9a9999999999d93f`），且判据是 **`jbe` 不颁奖**
   ⇒ 必须**严格大于** 0.4。

## 与 remake 的对应

本测试把原版当预言机，与两个 Python 模型逐项比对：

| 模型 | 依据 |
|---|---|
| `remake_score` | `monthly.ts:130-136`（JS number，**无 32 位回绕**）|
| `orig_score`  | 本函数汇编的 32 位**模运算**语义（`imul`/`add`/`lea` 全部只留低 32 位）|
| `remake_pick` | `monthly.ts:177-208` `pickAwardWinner`（整数比较 `3·max > 5·second`）|
| `x87_pick`    | 原版真实判据 `(max-second)/max > double(0.4)`（FPCW=0x027F ⇒ 双精度，与 Python float 同）|

打桩清单：**无**（函数不 `call` 任何东西；`esp_delta` 恒为 4 = 一条 `ret`，非 `ret N`）。

## 与 remake 的逐项比对（`file:line` + 玩家可见后果）

| 项 | 原版 `@source` | remake | 判定 |
|---|---|---|---|
| 第一项 `[+0x5c] − [+0x60]` | `0x437d43`–`0x437d51` | `monthly.ts:132-133` | **算式 MATCH**；★ **标签 DISCREPANCY**：`monthly.ts:98/100` 把 `+0x5C` 叫 `windfall`、`+0x60` 叫 `unexpectedLoss`，与 exe 自己的 UI 串**正好相反**（`0x464def`「本月意外損失：」画在 y=0x184 即 `+0x5c` 那行；`0x464dfe`「本月意外之財：」画在 y=0x196 即 `+0x60` 那行）⇒ 谁若照名字去接字段，损失/之財会**对调** |
| 第二项 `byte[+0x42] × p × 2500` | `0x437d55`–`0x437d68` | `monthly.ts:134` | **MATCH**（u8 零扩展 + 2500 常量一致；负物价指数也一致）|
| 第三项 `movsx word[+0x44] × 10` | `0x437d6a`–`0x437d7a` | `monthly.ts:135` | **算式 MATCH（有符号）**；注释 DISCREPANCY：`monthly.ts:104` 写 `(uint16)`，同文件 `monthly.ts:127` 却写 `(int16)`，`types.ts:249` 也写「有符号 16 位」|
| 32 位回绕 | `imul`/`add`/`lea` 全留低 32 位 | JS number **不回绕** | **DISCREPANCY**（[E] 组钉死：`p=3369, 天=255` 时原版 `-2147229796` vs remake `2147737500`）|
| 门槛 `(max−second)/max > double(0.4)` | `0x437dc9`–`0x437df2` | `monthly.ts:157-190` 的 `3max>5second` | **MATCH**（[L] 组 136 对穷举，原版 == 整数模型 == x87 模型）|
| 返回值 = **候选表下标** | `0x437d94 mov edi,eax` | `monthly.ts:155` 注释 + `monthly-screen.ts:947 present[at]` | **MATCH** |
| 候选表来源 | `0x439caa`：`whoPlays != 0` 的玩家、升序 | `monthly-screen.ts:939`：`isAlive` 过滤、升序 | **MATCH**（在调用点，不在本函数内）|

★ 后果说明：因为调用点存在（见上），上表三项的后果都是**玩家可见**——
「本月悲情人物」颁奖屏会显示 `[0x48c418][返回值]` 那位玩家的立绘与四项明细。
`monthly.ts` 的 `monthlyScore()` 本身无生产调用点，但 `monthly-screen.ts:855 awardScore()`
把同一条公式**又抄了一份**并在 `monthlyAward()`（`:938`）里生产调用
⇒「没有调用点所以忠实」不成立，实际是**核心空转、客户端自己实现**；
`monthly.ts` 与 `awardScore` 两份实现若漂移，只有 typecheck/测试拦得住。

跑法：cd rich4-spec && .venv/bin/python tests/test_monthly_score.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_ESP  # noqa: E402

TARGET = 0x437D1A
SCORES_READY = 0x437D99      # 第一轮结束、第二轮开始前：栈上分数数组仍是原值

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_F42 = 0x42                 # 本月倒楣天數（u8 累加器）
P_F44 = 0x44                 # 衰運（i16，唯一 movsx 读点）
P_F5C = 0x5C                 # 本月意外損失
P_F60 = 0x60                 # 本月意外之財

PRICE_INDEX = 0x4990E8       # 物價指數
AWARD_COUNT = 0x48C420       # 候选人数（byte）
AWARD_LIST = 0x48C418        # 候选表：byte[0..n-1] = 玩家 id（生产时升序）
MARGIN_CONST = 0x464D58      # double 0.4

UNLUCKY_DAY_WEIGHT = 0x9C4   # 2500
F68_WEIGHT = 10

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def bulk(ok):
    """批量用例：只计数、不逐条打印（用于穷举扫描）。"""
    RESULTS.append(bool(ok))


def i32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >= (1 << 31) else x


def orig_score(f5c, f60, f42, price, f68):
    """原版 32 位模运算模型（@source 0x437d43..0x437d7d）。"""
    s = i32(f5c - f60)                                 # sub ebx,esi
    s = i32(s + i32(i32(f42 * price) * UNLUCKY_DAY_WEIGHT))   # imul / imul / add
    s = i32(s + i32(f68 * F68_WEIGHT))                 # movsx*10 / lea / add
    return s


def remake_score(f5c, f60, f42, price, f68):
    """remake 模型 @source monthly.ts:130-136（JS number，不回绕）。

    对应关系：`acc.windfall` → +0x5C、`acc.unexpectedLoss` → +0x60、
    `acc.f42` → +0x42、`acc.f68` → +0x44。★ 前两个**标签与 exe 的 UI 串相反**，
    见模块末尾的「已知差异」。算式本身与汇编同序。
    """
    return f5c - f60 + f42 * price * UNLUCKY_DAY_WEIGHT + f68 * F68_WEIGHT


def remake_pick(scores):
    """remake 模型 @source monthly.ts:177-208 pickAwardWinner。"""
    if not scores:
        return -1
    mx, at = 0, 0
    for i, v in enumerate(scores):
        if mx < v:
            mx, at = v, i
    second = 0
    for v in scores:
        v2 = 0 if v == mx else v
        if second < v2:
            second = v2
    if mx == 0 or second == 0:
        return -1
    return at if 3 * mx > 5 * second else -1


def x87_pick(scores):
    """原版真实判据：x87 双精度 (max-second)/max > double(0.4)（@source 0x437dd1..0x437df0）。"""
    if not scores:
        return -1
    mx, at = 0, 0
    for i, v in enumerate(scores):
        if mx < v:
            mx, at = v, i
    second = 0
    for v in scores:
        v2 = 0 if v == mx else v
        if second < v2:
            second = v2
    if mx == 0 or second == 0:
        return -1
    return at if (mx - second) / mx > 0.4 else -1


class World:
    """无桩：只铺 4 张玩家记录 + 候选表 + 物價指數。"""

    def __init__(self):
        self.emu = Emu()
        self.emu.mu.hook_add(UC_HOOK_CODE, self._capture,
                             begin=SCORES_READY, end=SCORES_READY)
        self.clear()

    def clear(self):
        self.n = 0
        self.order = []
        self.price = 1
        self.players = {}
        self.captured = None
        self.ret = None
        self.esp_delta = None

    def player(self, pid, f5c=0, f60=0, f42=0, f44=0):
        self.players[pid] = (f5c, f60, f42, f44)
        return self

    def _capture(self, mu, address, size, user):
        """在 0x437D99 抓下栈上分数数组（0x14 字节局部区 = esp+0..esp+0x10）。"""
        esp = mu.reg_read(UC_X86_REG_ESP)
        self.captured = [i32(int.from_bytes(bytes(mu.mem_read(esp + 4 * i, 4)), "little"))
                         for i in range(self.n)]

    def _setup(self, emu):
        emu.write(PRICE_INDEX, struct.pack("<I", self.price & 0xFFFFFFFF))
        emu.write8(AWARD_COUNT, self.n)
        emu.write(AWARD_LIST, b"\x00" * 8)          # 候选表残留先清
        for i, pid in enumerate(self.order):
            emu.write8(AWARD_LIST + i, pid)
        for pid in range(4):                        # 4 张记录全清（.bss 本会被 reset，显式更稳）
            b = PLAYER_BASE + pid * PLAYER_STRIDE
            emu.write8(b + P_F42, 0)
            emu.write16(b + P_F44, 0)
            emu.write(b + P_F5C, b"\x00" * 4)
            emu.write(b + P_F60, b"\x00" * 4)
        for pid, (f5c, f60, f42, f44) in self.players.items():
            b = PLAYER_BASE + pid * PLAYER_STRIDE
            emu.write8(b + P_F42, f42 & 0xFF)
            emu.write16(b + P_F44, f44 & 0xFFFF)
            emu.write(b + P_F5C, struct.pack("<I", f5c & 0xFFFFFFFF))
            emu.write(b + P_F60, struct.pack("<I", f60 & 0xFFFFFFFF))

    def run(self):
        r = self.emu.call(TARGET, [], setup=self._setup)
        self.ret = r["signed"]
        self.esp_delta = r["esp_delta"]
        return self

    def snapshot_players(self):
        out = []
        for pid in range(4):
            b = PLAYER_BASE + pid * PLAYER_STRIDE
            out.append(bytes(self.emu.read(b, PLAYER_STRIDE)))
        return out


# ── 评分公式场景：单候选人，只读捕获的分数[0] ────────────────────────
def score_case(w, desc, f5c, f60, f42, price, f68):
    w.clear()
    w.n, w.order, w.price = 1, [0], price
    w.player(0, f5c=f5c, f60=f60, f42=f42, f44=f68)
    w.run()
    got = w.captured[0]
    case(f"{desc}  ⇒ 与 remake 模型一致", got, remake_score(f5c, f60, f42, price, f68))
    case("  ↳ 与 32 位（imul/add 回绕）模型一致", got, orig_score(f5c, f60, f42, price, f68))


def overflow_case(w, desc, f5c, f60, f42, price, f68, want_plain):
    """已知差异：原版回绕，remake 不回绕 —— 两边都钉死，差异本身也断言。"""
    w.clear()
    w.n, w.order, w.price = 1, [0], price
    w.player(0, f5c=f5c, f60=f60, f42=f42, f44=f68)
    w.run()
    got = w.captured[0]
    wrapped = orig_score(f5c, f60, f42, price, f68)
    plain = remake_score(f5c, f60, f42, price, f68)
    case(f"{desc}  ⇒ 原版 = 32 位回绕值", got, wrapped)
    case("  ↳ remake 模型 = JS 未回绕值", plain, want_plain)
    case("  ↳ ★ 两侧确实不等（否则该差异不成立）", plain != wrapped, True)


def pick_case(w, desc, order_scores, want=None):
    """order_scores: [(pid, score), ...] 按候选表顺序。"""
    w.clear()
    w.n = len(order_scores)
    w.order = [pid for pid, _ in order_scores]
    for pid, s in order_scores:
        w.player(pid, f5c=s)
    w.run()
    scores = [s for _, s in order_scores]
    want_r = remake_pick(scores)
    want_x = x87_pick(scores)
    case(f"{desc}  ⇒ remake", w.ret, want_r)
    case("  ↳ 与 x87 判据一致", w.ret, want_x)
    case("  ↳ 两版模型互相一致", want_r, want_x)
    if want is not None:
        case("  ↳ 与手推期望一致", w.ret, want)
    return w


def main():
    print("差分测试 · 月度奖项评分 / 本月悲情人物 0x00437d1a（228 B）\n")
    w = World()

    # ── A. 公式三项：意外損失(+0x5c) − 意外之財(+0x60) ────────────────
    print("[A] 第一项：+0x5c（本月意外損失）− +0x60（本月意外之財），dword 有符号")
    score_case(w, "+0x5c=50000（只有损失）", 50000, 0, 0, 1, 0)
    score_case(w, "+0x60=20000（只有之財）", 0, 20000, 0, 1, 0)
    score_case(w, "50000 − 20000", 50000, 20000, 0, 1, 0)
    score_case(w, "两者相等 ⇒ 0", 12345, 12345, 0, 1, 0)
    score_case(w, "之財 > 損失 ⇒ 负", 100, 400, 0, 1, 0)
    score_case(w, "Save0 实测样本 26000 − 394432", 26000, 394432, 0, 1, 0)
    score_case(w, "+0x5c 负（负数 dword）", -5000, 1000, 0, 1, 0)

    # ── B. 第二项：+0x42（本月倒楣天數，u8）× 物價指數 × 2500 ────────
    print("\n[B] 第二项：byte[+0x42] × dword[0x4990e8] × 0x9c4（= 2500）")
    score_case(w, "3 天 × p=1 × 2500", 0, 0, 3, 1, 0)
    score_case(w, "3 天 × p=4 × 2500", 0, 0, 3, 4, 0)
    score_case(w, "0 天 ⇒ 该整项为 0", 0, 0, 0, 7, 0)
    score_case(w, "255 天（u8 满值）× p=1", 0, 0, 255, 1, 0)
    score_case(w, "p=0 ⇒ 该整项为 0（即使有倒楣天數）", 0, 0, 200, 0, 0)
    score_case(w, "★ 物價指數为负 p=-2", 0, 0, 1, -2, 0)
    score_case(w, "p=2500（项 = 1×2500×2500）", 0, 0, 1, 2500, 0)

    # ── C. 第三项：+0x44（衰運，**i16**）× 10 ───────────────────────
    print("\n[C] 第三项：movsx word[+0x44] × 10 —— ★ 有符号，不是零扩展")
    score_case(w, "+0x44 = 7", 0, 0, 0, 1, 7)
    score_case(w, "★ +0x44 = −100（0xFF9C）⇒ −1000（若零扩展会是 654360）", 0, 0, 0, 1, -100)
    score_case(w, "★ +0x44 = −32768（0x8000，符号位）⇒ −327680", 0, 0, 0, 1, -32768)
    score_case(w, "+0x44 = 32767（0x7FFF）⇒ 327670", 0, 0, 0, 1, 32767)
    score_case(w, "+0x44 = −1 ⇒ −10", 0, 0, 0, 1, -1)
    score_case(w, "+0x44 = −500（土地公）⇒ −5000", 0, 0, 0, 1, -500)
    score_case(w, "+0x44 = 1000（死神）⇒ 10000", 0, 0, 0, 1, 1000)

    # ── D. 三项组合 ──────────────────────────────────────────────────
    print("\n[D] 三项组合")
    score_case(w, "1000−400 + 2×3×2500 + 5×10", 1000, 400, 2, 3, 5)
    score_case(w, "负债玩家：−20000−0 + 0 + (−200)×10", -20000, 0, 0, 1, -200)
    score_case(w, "全项非零 p=5 天=1 衰運=−100", 300, 100, 1, 5, -100)

    # ── E. 32 位回绕（原版 vs remake 的**已知差异**）──────────────────
    print("\n[E] ★ 32 位回绕：原版 `imul`/`add` 只留低 32 位，remake（JS）不回绕")
    overflow_case(w, "p=3369, 天=255（越界一步：255×3369×2500）",
                  0, 0, 255, 3369, 0, 255 * 3369 * 2500)
    score_case(w, "p=3368, 天=255（越界前一步，仍不溢）", 0, 0, 255, 3368, 0)
    overflow_case(w, "中间量溢出：天=255 × p=9000000",
                  0, 0, 255, 9000000, 0, 255 * 9000000 * 2500)
    overflow_case(w, "+0x5c=0x7fffffff, +0x60=−1 ⇒ 和回绕",
                  0x7FFFFFFF, -1, 0, 1, 0, 0x7FFFFFFF - (-1))
    overflow_case(w, "+0x5c 溢出后再加天數项",
                  0x7FFFFFFF, 0, 1, 1, 0, 0x7FFFFFFF + 2500)

    # ── F. 评选：max / second / 严格 > 0.4 ───────────────────────────
    print("\n[F] 评选门槛：(max−second)/max **严格 > 0.4** 才颁奖（0x437df0 jbe）")
    pick_case(w, "100 vs 50（0.5）", [(0, 100), (1, 50)], 0)
    pick_case(w, "★ 100 vs 60（恰好 0.4）⇒ 不颁奖", [(0, 100), (1, 60)], -1)
    pick_case(w, "★ 100 vs 59（0.41）⇒ 颁奖", [(0, 100), (1, 59)], 0)
    pick_case(w, "100 vs 61（0.39）⇒ 不颁奖", [(0, 100), (1, 61)], -1)
    pick_case(w, "10 vs 6（0.4）⇒ 不颁奖", [(0, 10), (1, 6)], -1)
    pick_case(w, "10 vs 5（0.5）⇒ 颁奖", [(0, 10), (1, 5)], 0)
    pick_case(w, "5 vs 3（0.4）⇒ 不颁奖", [(0, 5), (1, 3)], -1)
    pick_case(w, "5 vs 2（0.6）⇒ 颁奖", [(0, 5), (1, 2)], 0)
    pick_case(w, "★ 12 vs 7（3m=36 仅 > 5s=35）⇒ 颁奖", [(0, 12), (1, 7)], 0)
    pick_case(w, "★ 12 vs 8（36 < 40）⇒ 不颁奖", [(0, 12), (1, 8)], -1)
    pick_case(w, "★ 17 vs 10（51 > 50）⇒ 颁奖", [(0, 17), (1, 10)], 0)
    pick_case(w, "★ 7 vs 4（21 > 20）⇒ 颁奖", [(0, 7), (1, 4)], 0)
    pick_case(w, "★ 7 vs 5（21 < 25）⇒ 不颁奖", [(0, 7), (1, 5)], -1)

    # ── G. second 的算法：等于最高分的**全部**清零 ───────────────────
    print("\n[G] 次高分的定义：把等于最高分的项**全部**清零后再取最大")
    pick_case(w, "两人同分 100/100 ⇒ 全清 ⇒ 无次高 ⇒ 不颁奖", [(0, 100), (1, 100)], -1)
    pick_case(w, "★ 100/100/10 ⇒ 清两个 100 ⇒ 次高 10 ⇒ 颁奖", [(0, 100), (1, 100), (2, 10)], 0)
    pick_case(w, "★ 10/100/100 ⇒ 最高在**下标 1** ⇒ 返回 1", [(0, 10), (1, 100), (2, 100)], 1)
    pick_case(w, "三人同分 50/50/50 ⇒ 不颁奖", [(0, 50), (1, 50), (2, 50)], -1)
    pick_case(w, "100/50/50 ⇒ 次高 50（两个 50 只清最高）", [(0, 100), (1, 50), (2, 50)], 0)
    pick_case(w, "★ 100/0/0 ⇒ 次高 0 ⇒ 不颁奖", [(0, 100), (1, 0), (2, 0)], -1)

    # ── H. 最高分 == 0 / 全负 / 单人 / 空表 ──────────────────────────
    print("\n[H] 前置：最高分为 0 ⇒ 不颁奖；全负 ⇒ 最高被夹到 0")
    pick_case(w, "全 0", [(0, 0), (1, 0), (2, 0)], -1)
    pick_case(w, "★ 全负 −5/−10 ⇒ max 保持 0 ⇒ 不颁奖", [(0, -5), (1, -10)], -1)
    pick_case(w, "★ 只有一人 100 ⇒ 次高 0 ⇒ 不颁奖", [(0, 100)], -1)
    pick_case(w, "★ 空表（n=0）⇒ −1", [], -1)
    pick_case(w, "★ 100 / −50 ⇒ 次高 0（负数不顶替）⇒ 不颁奖", [(0, 100), (1, -50)], -1)
    pick_case(w, "100 / 50 / −60 ⇒ 次高 50 ⇒ 颁奖", [(0, 100), (1, 50), (2, -60)], 0)
    pick_case(w, "★ 负分玩家不夺冠：−1/−5 ⇒ 不颁奖", [(0, -1), (1, -5)], -1)
    pick_case(w, "★ 正分压过负分：20/−30 ⇒ 次高 0 ⇒ 不颁奖", [(0, 20), (1, -30)], -1)

    # ── I. 返回值 = 候选表下标，不是玩家 id ──────────────────────────
    print("\n[I] ★ 返回值是**候选表下标**（0x437d94 mov edi,eax），再经 [0x48c418] 映射成 id")
    w.clear()
    w.n, w.order = 4, [2, 0, 3, 1]
    for pid, s in [(2, 100), (0, 50), (3, 30), (1, 10)]:
        w.player(pid, f5c=s)
    w.run()
    case("候选表 [2,0,3,1]，player2 分最高 ⇒ 返回**下标 0**（不是 id 2）", w.ret, 0)
    case("  捕获的分数数组按**候选表顺序**排列", w.captured, [100, 50, 30, 10])
    case("  夺冠者 id 经 [0x48c418] 映射 = player 2", w.order[w.ret], 2)

    w.clear()
    w.n, w.order = 4, [1, 3, 0, 2]
    for pid, s in [(3, 100), (1, 50), (0, 30), (2, 10)]:
        w.player(pid, f5c=s)
    w.run()
    case("候选表 [1,3,0,2]，player3 分最高 ⇒ 返回下标 1（不是 id 3）", w.ret, 1)
    case("  夺冠者 id = player 3", w.order[w.ret], 3)

    w.clear()
    w.n, w.order = 2, [3, 1]
    w.player(3, f5c=100)
    w.player(1, f5c=50)
    w.player(0, f5c=999999)          # 不在候选表里的玩家，**必须完全不被看见**
    w.run()
    case("★ 表外玩家 0 的 999999 分不参与 ⇒ 仍返回 0", w.ret, 0)
    case("  分数数组只有 2 项", w.captured, [100, 50])

    # ── J. 只读 8 项：+0x44 是唯一的神明字段，+0x46/+0x48 完全不被读 ──
    print("\n[J] 本函数**只**读 8 个地址（gen/functions.json 的 reads 清单）；+0x46/+0x48 不参与")
    w.clear()
    w.n, w.order, w.price = 1, [0], 1
    w.player(0, f5c=100, f42=1, f44=5)
    w.run()
    base = w.captured[0]

    # ★ +0x46/+0x48 的注入必须在 `_setup` 里做：`reset()` 会抹掉调用外写的 DGROUP。
    #   做法是把 `_setup` 包一层，在原注入之后再补写这两个 i16，然后同一次调用读回分数。
    for extra_off, extra_val, name in [(0x46, 30000, "+0x46 fortune"), (0x48, 30000, "+0x48 luck")]:
        w.clear()
        w.n, w.order, w.price = 1, [0], 1
        w.player(0, f5c=100, f42=1, f44=5)
        orig_setup = w._setup

        def setup2(emu, _off=extra_off, _v=extra_val, _s=orig_setup):
            _s(emu)
            emu.write16(PLAYER_BASE + _off, _v & 0xFFFF)
        w._setup = setup2
        w.run()
        w._setup = orig_setup
        case(f"{name} = 30000 完全不影响分数（本函数不读它）", w.captured[0], base)

    # 相邻**独立字节** +0x41 / +0x43（★ 不能动 +0x45/+0x47：它们是 +0x44/+0x46 的高字节）
    w.clear()
    w.n, w.order, w.price = 1, [0], 1
    w.player(0, f5c=100, f42=1, f44=5)
    orig_setup = w._setup

    def setup3(emu, _s=orig_setup):
        _s(emu)
        emu.write8(PLAYER_BASE + 0x41, 0xFF)
        emu.write8(PLAYER_BASE + 0x43, 0xFF)     # f67：全 exe 无读无写
    w._setup = setup3
    w.run()
    w._setup = orig_setup
    case("★ 相邻独立字节 +0x41/+0x43 = 0xFF 不影响分数", w.captured[0], base)
    case("  基线分本身 = 100 + 1×2500 + 50 = 2650", base, 2650)

    # ── K. 纯函数性：不改任何全局/记录；无 call（esp_delta = 4）────────
    print("\n[K] 副作用与调用协议")
    w.clear()
    w.n, w.order, w.price = 4, [0, 1, 2, 3], 7
    for pid in range(4):
        w.player(pid, f5c=100 * (pid + 1), f60=10, f42=pid, f44=-pid)
    model = [remake_score(100 * (pid + 1), 10, pid, 7, -pid) for pid in range(4)]
    # ★ 「不变」必须与 **setup 之后、执行之前** 的快照比 —— 直接在执行前读会因为
    #   `call()` 内部先 `reset()`（.bss 归零）而拿到空记录，是本测试首跑踩的坑。
    snap = {}
    orig_setup = w._setup

    def setup_k(emu, _s=orig_setup, _c=snap):
        _s(emu)
        _c["players"] = [bytes(emu.read(PLAYER_BASE + pid * PLAYER_STRIDE, PLAYER_STRIDE))
                         for pid in range(4)]
        _c["globals"] = (emu.read(PRICE_INDEX, 4), emu.read8(AWARD_COUNT),
                         emu.read(AWARD_LIST, 8))
    w._setup = setup_k
    w.run()
    w._setup = orig_setup
    after = w.snapshot_players()
    case("★ 4 张玩家记录逐字节不变（函数只读）", after == snap["players"], True)
    case("★ 0x4990e8 / 0x48c420 / 0x48c418 逐字节不变",
         (w.emu.read(PRICE_INDEX, 4), w.emu.read8(AWARD_COUNT),
          w.emu.read(AWARD_LIST, 8)) == snap["globals"], True)
    case("  分数数组 == 模型（90/17680/35270/52860）", w.captured, model)
    case("  领先幅度 0.33 < 0.4 ⇒ 返回 −1", w.ret, remake_pick(model))
    case("★ cdecl 0 参数：esp_delta = 4（一条 ret，不是 ret N）", w.esp_delta, 4)
    case("★ reads 清单核验：实测 [0x464d58] 常量 = double 0.4",
         w.emu.f64(MARGIN_CONST), 0.4)
    case("  ↳ 0.4 的位模式确为 9a9999999999d93f",
         w.emu.read(MARGIN_CONST, 8).hex(), "9a9999999999d93f")

    # ── L. 门槛穷举：max = 1..16，second = 0..max-1 ──────────────────
    print("\n[L] 门槛穷举 max = 1..16 × second = 0..max−1（原版逐对驱动，136 对）")
    mism = []
    for mx in range(1, 17):
        for sec in range(0, mx):
            w.clear()
            w.n, w.order = 2, [0, 1]
            w.player(0, f5c=mx)
            w.player(1, f5c=sec)
            w.run()
            want_i = remake_pick([mx, sec])
            want_x = x87_pick([mx, sec])
            ok = (w.ret == want_i == want_x)
            bulk(ok)
            if not ok:
                mism.append((mx, sec, w.ret, want_i, want_x))
    for m in mism[:10]:
        print(f"     ✗ max={m[0]} second={m[1]} 原版={m[2]} remake={m[3]} x87={m[4]}")
    case("★ 136 对全部满足「原版 == remake 整数模型 == x87 模型」", len(mism), 0)

    # ── M. 候选表下标语义穷举（0/1/2 人时下标 == 位置）────────────────
    print("\n[M] 候选表乱序时，返回值跟随**位置**而非 id（vals 按候选表**位置**给）")
    for order, vals, want in [
        ([3, 0, 2, 1], [10, 200, 30, 50], 1),
        ([2, 1, 0, 3], [10, 20, 300, 40], 2),
        ([0, 2, 1], [10, 300, 20], 1),
    ]:
        w.clear()
        w.n, w.order = len(order), order
        for pos, pid in enumerate(order):
            w.player(pid, f5c=vals[pos])
        w.run()
        want_i = remake_pick(vals)
        want_x = x87_pick(vals)
        case(f"order={order} scores={vals} ⇒ 下标 {want}", w.ret, want)
        bulk(w.ret == want_i == want_x)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 74}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
