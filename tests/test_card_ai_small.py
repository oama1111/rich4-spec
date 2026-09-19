#!/usr/bin/env python3
"""
通道 2 差分测试 · 五支小函数（各自独立、都无 `call` 调用者或只被单点调用）

| # | VA | 语义 | 复刻侧 |
|---|---|---|---|
| A | `0x0041fe4e` (33 B) | 冬眠卡（卡 15）AI：`rand() % 4 == 0` → 用 | `ai/card-policy.ts` `dongmian` |
| B | `0x0041970f` (53 B) | `chainStoreCount(owner)`：数该 owner 的**非住宅**地块（連鎖店） | `ai/card-policy.ts` `chainStoreCount` |
| C | `0x0041ff77` (129 B) | 送神符（卡 22）AI：身上的神是坏神（物件类型 5/6/7/8/10/15），**或**跟班 `+0x40` 的**另一个字段**不是死神态 | `ai/card-policy.ts` `songshen` |
| D | `0x00447285` (16 B) | 遙控骰子点数的**读出即清**（`[0x475dd8]`）| `state/types.ts` `forcedDice` + `state/reduce.ts` `rollDice` |
| E | `0x0040ea62` (56 B) | `canAttachObjectType(idx)`：`(type <= 12 && type != 11) || type == 15` | `cards/summon.ts` `canAttach` |

★ C 的易错点是**两个字段不是同一个**：神用物件记录 `+0x00`（类型），
  跟班用 `+0x04`（状态）—— 本文件用「同一物件在这两个字段放不同值」把这件事钉死。

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x00456f2d` | CRT `rand()` | 数据槽 + **自增计数槽**（本文件 A 组要断言「恰好摇 1 次」）| 只钉取模规则与消费时机（D-004 已登记复刻用确定性替身）|

`0x498e84`（地块表指针）/`0x498e98`（地塊记录数）/`0x49910c`（当前玩家）/
`0x496b68`（玩家表）/`0x496d08`（**物件表绝对基址**，不是指针）全由 `setup()` 直接铺。
三支函数都**不调用**其他子程序（B 只读表、A 只摇一次、C 只读玩家与物件）。

跑法：cd rich4-spec && .venv/bin/python tests/test_card_ai_small.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

HIBERNATE = 0x41FE4E      # A 冬眠卡 AI
CHAIN_COUNT = 0x41970F    # B 連鎖店计数
DISPEL = 0x41FF77         # C 送神符 AI
FORCED_DICE = 0x447285    # D 遙控骰子点数「读出即清」
CAN_ATTACH = 0x40EA62     # E 可附身判据
PRNG = 0x456F2D

CUR = 0x49910C
LAND_TABLE_PTR = 0x498E84
NUM_LANDS = 0x498E98
OBJ_TABLE = 0x496D08      # ★ 绝对基址（不是指针）
FORCED_FLAG = 0x475DD8    # D 的全局（byte）
PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_GOD, P_F64 = 0x3F, 0x40

LAND_STRIDE, L_TYPE, L_OWNER = 0x34, 0x18, 0x19
OBJ_STRIDE, O_TYPE, O_STATE = 0x18, 0x00, 0x04

LANDS = SCRATCH_BASE + 0x3000
RAND_SLOT = SCRATCH_BASE + 0x900
RAND_CALLS = SCRATCH_BASE + 0x904
SENTINEL = 0x5A5A5A5A
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<68} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class World:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        self.clear()

    def clear(self):
        self.me = 0
        self.god = 0
        self.f64 = 0
        self.lands = {}        # idx → (type, owner)
        self.num_lands = 0
        self.objs = {}         # idx(1 基) → (type, state)
        self.rand = 0
        self.flag = 0          # D 的全局初值
        return self

    def put_land(self, idx, ltype, owner):
        self.lands[idx] = (ltype, owner)
        self.num_lands = max(self.num_lands, idx)
        return self

    def put_obj(self, idx, otype, state=0):
        self.objs[idx] = (otype, state)
        return self

    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(NUM_LANDS, self.num_lands)
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        emu.write(LANDS, b"\x00" * (LAND_STRIDE * 32))
        emu.write(OBJ_TABLE, b"\x00" * (OBJ_STRIDE * 16))
        pb = PLAYER_BASE + self.me * PLAYER_STRIDE
        emu.write8(pb + P_GOD, self.god)
        emu.write8(pb + P_F64, self.f64)
        for idx, (lt, ow) in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write8(b + L_TYPE, lt)
            emu.write8(b + L_OWNER, ow)
        for idx, (ot, st) in self.objs.items():
            b = OBJ_TABLE + (idx - 1) * OBJ_STRIDE
            emu.write8(b + O_TYPE, ot)
            emu.write8(b + O_STATE, st)
        emu.write8(FORCED_FLAG, self.flag)

    def run(self, func, args=()):
        r = self.emu.call(func, list(args), setup=self._setup)
        self.ret = r["eax"]
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        return self

    def read_flag(self):
        return self.emu.read8(FORCED_FLAG)


def main():
    print("差分测试 · 冬眠卡 AI / 連鎖店计数 / 送神符 AI / 骰子点数清标志 / 可附身\n")
    w = World()

    # ═══════════ [A] 0x41fe4e 冬眠卡 AI ═══════════
    print("[A] 冬眠卡 `0x41fe4e`：rand() % 4 == 0 → 1（每次恰好摇 1 次）")
    for rand, want in [(0, 1), (1, 0), (2, 0), (3, 0), (4, 1), (5, 0), (8, 1), (7, 0)]:
        w.clear(); w.rand = rand
        r = w.run(HIBERNATE)
        case(f"rand={rand} ⇒ 返回 {want}", r.ret, want)
    w.clear(); r = w.run(HIBERNATE)
    case("★ rand 消费恰好 1 次（无前置闸）", r.rand_calls, 1)
    seen = set()
    for v in range(8):
        w.clear(); w.rand = v
        seen.add(w.run(HIBERNATE).ret)
    case("  8 个 rand 值下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    # ═══════════ [B] 0x41970f chainStoreCount ═══════════
    print("\n[B] 連鎖店计数 `0x41970f(owner)`：数**非住宅**（type != 0）且 owner 相符的地块")
    w.clear()
    w.put_land(1, 0, 2)   # 住宅，不计
    w.put_land(2, 1, 2)   # 連鎖店，owner 2 → 计
    w.put_land(3, 2, 3)   # 連鎖店，owner 3 → 不计
    w.put_land(4, 4, 2)   # 連鎖店（type != 0），owner 2 → 计
    r = w.run(CHAIN_COUNT, [2])
    case("★ owner=2 ⇒ 只数到记录 2/4 两条", r.ret, 2)
    r = w.run(CHAIN_COUNT, [3])
    case("★ owner=3 ⇒ 只数到记录 3 一条", r.ret, 1)
    r = w.run(CHAIN_COUNT, [1])
    case("★ owner=1（没有地）⇒ 0", r.ret, 0)

    # type == 0 一律不算（含 owner 相符）
    w.clear(); w.put_land(1, 0, 2).put_land(2, 0, 2)
    r = w.run(CHAIN_COUNT, [2])
    case("★ 全是住宅 ⇒ 0（type 0 是住宅，不是連鎖店）", r.ret, 0)

    # 上界 = num_lands（含），记录 0 永远看不到
    w.clear()
    w.put_land(0, 1, 2)   # 记录 0：owner 相符、非住宅 —— 但循环从 1 起 ⇒ 不该被数
    w.put_land(1, 1, 2)
    w.num_lands = 1
    r = w.run(CHAIN_COUNT, [2])
    case("★★ 记录 0 不计（循环 `edx=1..num_lands`）", r.ret, 1)

    w.clear()
    w.put_land(1, 1, 2).put_land(2, 1, 2)
    w.num_lands = 1        # 记录 2 在上界之外
    r = w.run(CHAIN_COUNT, [2])
    case("★ 超过 num_lands 的记录不计（上界含 num_lands 本身）", r.ret, 1)

    w.clear()
    w.put_land(1, 1, 2)
    w.num_lands = 0
    r = w.run(CHAIN_COUNT, [2])
    case("  num_lands = 0 ⇒ 0（空循环）", r.ret, 0)

    # 高位 type 也照数（只要 != 0）
    w.clear(); w.put_land(1, 255, 2)
    r = w.run(CHAIN_COUNT, [2])
    case("  type = 255（只要 != 0）⇒ 计", r.ret, 1)

    w.clear(); r = w.run(CHAIN_COUNT, [2])
    case("  rand 不被消费（本函数无随机）", r.rand_calls, 0)

    # ═══════════ [C] 0x41ff77 送神符 AI ═══════════
    print("\n[C] 送神符 `0x41ff77`：神用物件 `+0x00`（类型）、跟班用 `+0x04`（状态）")
    # godInfo 分支：类型 5/6/7/8/10/15 命中
    for ot, want in [(5, 1), (6, 1), (7, 1), (8, 1), (10, 1), (15, 1),
                     (1, 0), (2, 0), (3, 0), (4, 0), (9, 0), (11, 0), (12, 0), (13, 0), (16, 0)]:
        w.clear(); w.god = 3; w.put_obj(3, ot, 0)
        r = w.run(DISPEL)
        case(f"godInfo=3、物件类型 {ot} ⇒ {want}", r.ret, want)

    w.clear(); w.god = 0; w.f64 = 0
    r = w.run(DISPEL)
    case("★ 神与跟班都为 0 ⇒ 不用", r.ret, 0)

    # godInfo 用的是 object[godInfo-1] —— 换一格类型，结论必须跟着换
    w.clear(); w.god = 1; w.put_obj(1, 1, 0).put_obj(2, 15, 0)
    r = w.run(DISPEL)
    case("★ godInfo=1 读物件 1（类型 1）⇒ 不用（证明下标是 godInfo-1，不是别处）", r.ret, 0)
    w.clear(); w.god = 2; w.put_obj(1, 1, 0).put_obj(2, 15, 0)
    r = w.run(DISPEL)
    case("★ godInfo=2 读物件 2（类型 15）⇒ 用", r.ret, 1)

    # 跟班分支：读物件 +0x04（state），门槛 < 0xd
    w.clear(); w.god = 0; w.f64 = 1; w.put_obj(1, 99, 0)     # type=99（坏值）但 state=0
    r = w.run(DISPEL)
    case("★★ 跟班读的是 `+0x04`（state=0 < 13）⇒ 用，**即使 +0x00 是 99**", r.ret, 1)

    w.clear(); w.god = 0; w.f64 = 1; w.put_obj(1, 15, 13)    # type=15（神值）但 state=13
    r = w.run(DISPEL)
    case("★★ 跟班 state=13（不 < 13）⇒ 不用，**即使 +0x00 是坏神值 15**", r.ret, 0)

    for st, want in [(0, 1), (12, 1), (13, 0), (14, 0), (255, 0)]:
        w.clear(); w.god = 0; w.f64 = 2; w.put_obj(2, 0, st)
        r = w.run(DISPEL)
        case(f"跟班 state={st} ⇒ {want}（门槛严格 < 13）", r.ret, want)

    w.clear(); w.god = 0; w.f64 = 3; w.put_obj(2, 5, 13)     # 跟班下标 3 指向空槽
    r = w.run(DISPEL)
    case("★★ 跟班下标指向**空槽**（读到全 0 ⇒ state=0 < 13）⇒ 原版照样算「用」", r.ret, 1)

    # 神分支优先于跟班分支
    w.clear(); w.god = 5; w.f64 = 1
    w.put_obj(5, 1, 0)      # 神的物件类型 1 → 不用
    w.put_obj(1, 0, 0)      # 跟班 state 0 → 若走跟班分支会用
    r = w.run(DISPEL)
    case("★★ godInfo != 0 时**不再看跟班**（神分支优先）", r.ret, 0)

    w.clear(); w.god = 1; w.f64 = 1
    w.put_obj(1, 15, 0)     # 神来判：类型 15 → 用
    r = w.run(DISPEL)
    case("★★ 神是坏神 ⇒ 用（跟班那格无关）", r.ret, 1)

    seen = set()
    w.clear(); w.god = 0; w.f64 = 0; seen.add(w.run(DISPEL).ret)
    w.clear(); w.god = 5; w.put_obj(5, 5, 0); seen.add(w.run(DISPEL).ret)
    w.clear(); w.god = 0; w.f64 = 1; w.put_obj(1, 0, 5); seen.add(w.run(DISPEL).ret)
    case("  三种情形下返回值集合恰为 {0,1}", sorted(seen), [0, 1])

    w.clear(); w.god = 5; w.put_obj(5, 5, 0)
    r = w.run(DISPEL)
    case("  rand 不被消费（本函数无随机）", r.rand_calls, 0)

    # ═══════════ [D] 0x447285 遙控骰子点数「读出即清」 ═══════════
    print("\n[D] 点数标志 `0x447285`：返回旧值并**当场清零**（`[0x475dd8]`）")
    for v in (0, 1, 3, 6, 255):
        w.clear(); w.flag = v
        r = w.run(FORCED_DICE)
        case(f"标志 = {v} ⇒ 返回 {v}", r.ret, v)
        case("  ★ 读完即清（全局变 0）", w.read_flag(), 0)
    # ⚠️ 诚实边界：**跨调用**的"一次性"不可观测 —— `Emu.call` 每次先 `reset()`，
    #   会把 DGROUP（含 `0x475dd8`）恢复成快照，所以"第二次调用读到 0"既可能来自
    #   函数的清零、也可能来自 reset，**区分不了**。可证伪的那一半（同一次调用内
    #   返回旧值 + 清零）已由上面 10 条断言钉住。

    # ═══════════ [E] 0x40ea62 可附身判据 ═══════════
    print("\n[E] 可附身 `0x40ea62(idx)`：(type <= 12 且 type != 11) 或 type == 15")
    hit = set()
    for t in list(range(0, 17)) + [255]:
        w.clear(); w.put_obj(1, t, 0)
        r = w.run(CAN_ATTACH, [1])
        want = 1 if ((t <= 12 and t != 11) or t == 15) else 0
        if r.ret == 1:
            hit.add(t)
        case(f"idx=1、type={t} ⇒ {want}", r.ret, want)
    case("★★ 命中集合恰为 {0..10, 12, 15}（惡犬 11 / 禮物 13 / 寶箱 14 等全落选）",
         sorted(hit), list(range(0, 11)) + [12, 15])

    w.clear(); w.put_obj(2, 0, 0)
    r = w.run(CAN_ATTACH, [0])
    case("★ idx = 0（原版以 0 表示「无」）⇒ 0", r.ret, 0)
    w.clear(); w.put_obj(2, 0, 0)
    r = w.run(CAN_ATTACH, [3])
    case("★ idx 指向空槽（type 读到 0）⇒ 1（0 <= 12 且 != 11）", r.ret, 1)
    w.clear(); r = w.run(CAN_ATTACH, [1])
    case("  rand 不被消费（本函数无随机）", r.rand_calls, 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 76}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
