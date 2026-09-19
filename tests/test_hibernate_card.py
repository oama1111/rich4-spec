#!/usr/bin/env python3
"""
通道 2 差分测试 #42 · **冬眠卡（卡 15）** `0x4440ea`（242 字节）

PRD 里已有「✅ 完整规格」（`cards.md` §卡 15），本轮第一次**整支驱动**验证。
函数体只有 76 条指令、四个直接调用（`remove_card` / `player_say` /
`update_hostility` / `0x41d476`），非常适合通道 2。

```asm
; @source 0x4440ea
004440ed  push 0xf / push [0x49910c] / call 0x441343     ; ① 先扣卡（卡 15）
00444104  imul eax, ecx, 0x68
00444109  dl = byte [eax + 0x496b7b]                     ; 角色号
00444120  ebx = [eax + 0x481272]                         ; 台词指针
0044412a  call 0x44ef41                                  ; say(cur, 3, 台词)
00444132  ebx = 0                                        ; ② 循环 8 个槽
loop:
00444142  if (ebx >= 4) goto npc_branch
00444147  if (ebx == [0x49910c]) goto next                ; 跳过自己
00444154  if (byte [player+0x15] == 0) goto next          ; 空槽
0044415d  if (word [player+0x08] == 0) goto next          ; 没落位
00444167  if (dword [player+0x32] != 0) goto next         ; 消失/住宿/坐牢/住院
00444186  update_hostility(目标, 当前, **150 × [0x4990e8]**)
00444193  byte [player+0x37] = 0                         ; 清梦游
0044419b  byte [player+0x36] = 5                         ; 睡眠 5 天
004441a1  byte [player+0x42] += 5
next:
00444136  dh = 5                                         ; ★ 每轮都置 5（含「跳过」）
00444138  ebx++ / cmp 8 / jl loop
npc_branch:                                              ; 下标 ≥ 4（替身槽）
004441ae  ch = byte [ebx*16 + 0x498df2]  （= 槽 +0x0a 状态）
004441b6  if (ch != 0) goto next                          ; 在监/在院 → 跳过
004441b8  byte [ebx*16 + 0x498df5] = 0   （槽 +0x0d）
004441be  byte [ebx*16 + 0x498df4] = 5   （槽 +0x0c = dh）
004441c9  0x41d476(0, 0, 1)                              ; 落点事务
004441d7  return 1                                       ; 恒成功
```

## 打桩

| VA | 原用途 | 桩 |
|---|---|---|
| `0x441343` | `remove_card(player, cardId)` | 记两个实参 + 调用序列 + `ret` |
| `0x44ef41` | `player_say(player, 槽, 文本)` | 记**每一次** + `ret` |
| `0x40df69` | `update_hostility(a, b, delta)` | 记**每一次** + `ret` |
| `0x41d476` | 落点事务（只写重绘标志）| 记三个实参 + `ret` |

**诚实边界**：`0x40df69` 内部「delta > 0 且两者已是盟友 → 额外拆盟」那一段（`0x40dfb5`
起）**被本测试打桩跳过** —— 那一层由 `tests/test_hostility_update.py`（22/22）单独覆盖；
本测试只钉「本卡传了什么」。

跑法：cd rich4-spec && .venv/bin/python tests/test_hibernate_card.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

HIBERNATE = 0x4440EA
REMOVE_CARD, SAY, HOSTILITY, TXN = 0x441343, 0x44EF41, 0x40DF69, 0x41D476

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_X, P_CHAR, P_WHO = 0x08, 0x13, 0x15
P_BLOCK, P_SLEEP, P_SLEEPWALK, P_MISFORTUNE = 0x32, 0x36, 0x37, 0x42
SAY_LINE = 0x481272
CUR, NUMP, PRICE = 0x49910C, 0x499114, 0x4990E8
NPC_STATUS, NPC_F0C, NPC_F0D = 0x498DF2, 0x498DF4, 0x498DF5

S = SCRATCH_BASE
SEQ, SEQ_N = S + 0xE00, S + 0xE80
M_RMC1, M_RMC2 = S + 0x900, S + 0x904
SAY_N, M_SAY = S + 0x920, S + 0x940
HOS_N, M_HOS = S + 0xA00, S + 0xA40
# ⚠️ 计数器**不能**挨着被记录的实参放（`M_TXN+4` 与 `TXN_N` 撞过一次 ——
#    实参写 0 之后被 `inc` 成 1，读出来是 (0,1,1) 而不是 (0,0,1)）
M_TXN, TXN_N = S + 0xB00, S + 0xE90
ZERO = S + 0xC30
A1, A2, A3 = 0x24, 0x28, 0x2C
ALL_SLOTS = [SEQ, SEQ_N, M_RMC1, M_RMC2, SAY_N, HOS_N, M_TXN, TXN_N, ZERO]
ALL_SLOTS += list(range(M_SAY, M_SAY + 24, 4)) + list(range(M_HOS, M_HOS + 24, 4))
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<60} 实际 {got!s:<24} 期望 {want!s}")
    return ok


def _log(code):
    return (b"\xB8" + struct.pack("<I", code)
            + b"\x8B\x1D" + struct.pack("<I", SEQ_N)
            + b"\x89\x04\x9D" + struct.pack("<I", SEQ)
            + b"\xFF\x05" + struct.pack("<I", SEQ_N))


def _rec(off, slot):
    return b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)


def _list(n_slot, count, base):
    code = (b"\x8B\x1D" + struct.pack("<I", n_slot)
            + b"\x6B\xDB" + bytes([4 * count])
            + b"\x81\xC3" + struct.pack("<I", base))
    for k in range(count):
        code += _rec(A1 + 4 * k, ZERO) + b"\x89\x43" + bytes([k * 4])
    return code + b"\xFF\x05" + struct.pack("<I", n_slot)


def _stub(body):
    return b"\x60" + body + b"\x61\xC3"


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(REMOVE_CARD, _stub(_log(1) + _rec(A1, M_RMC1) + _rec(A2, M_RMC2)))
        self.emu.patch(SAY, _stub(_log(2) + _list(SAY_N, 3, M_SAY)))
        self.emu.patch(HOSTILITY, _stub(_log(3) + _list(HOS_N, 3, M_HOS)))
        self.emu.patch(TXN, _stub(_log(4) + _rec(A1, M_TXN) + _rec(A2, M_TXN + 4)
                                  + _rec(A3, M_TXN + 8)
                                  + b"\xFF\x05" + struct.pack("<I", TXN_N)))

    def run(self, *, cur=0, nump=4, price=1, players=None, npcs=None):
        players = players if players is not None else [{} for _ in range(4)]
        npcs = npcs or {}

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            emu.write32(CUR, cur)
            emu.write32(NUMP, nump)
            emu.write32(PRICE, price)
            emu.write(PLAYER_BASE, b"\x00" * (4 * STRIDE))
            for i, spec in enumerate(players):
                pb = PLAYER_BASE + i * STRIDE
                emu.write32(pb + P_X, spec.get("x", 100))
                emu.write8(pb + P_CHAR, spec.get("char", 0))
                emu.write8(pb + P_WHO, spec.get("who", 1))
                emu.write32(pb + P_BLOCK, spec.get("block", 0))
                emu.write8(pb + P_SLEEP, spec.get("sleep", 0))
                emu.write8(pb + P_SLEEPWALK, spec.get("sleepwalk", 0))
                emu.write8(pb + P_MISFORTUNE, spec.get("misfortune", 0))
            for i in range(8):
                st = npcs.get(i, 1)          # 默认：替身槽「在监/在院」⇒ 不施法
                emu.write8(NPC_STATUS + i * 16, 0 if i < 4 else st)
                emu.write8(NPC_F0C + i * 16, 9)
                emu.write8(NPC_F0D + i * 16, 9)

        r = self.emu.call(HIBERNATE, [], setup=setup)
        e = self.emu
        return {
            "ret": r["eax"],
            "seq": [e.readu32(SEQ + 4 * i) for i in range(min(e.readu32(SEQ_N), 16))],
            "rmc": (e.readu32(M_RMC1), e.readu32(M_RMC2)),
            "says": [(e.readu32(M_SAY + 12 * i), e.readu32(M_SAY + 12 * i + 4),
                      e.readu32(M_SAY + 12 * i + 8)) for i in range(e.readu32(SAY_N))],
            "hos": [(e.read32(M_HOS + 12 * i), e.read32(M_HOS + 12 * i + 4),
                     e.read32(M_HOS + 12 * i + 8)) for i in range(e.readu32(HOS_N))],
            "txn": (e.read32(M_TXN), e.read32(M_TXN + 4), e.read32(M_TXN + 8),
                    e.readu32(TXN_N)),
            "sleep": [e.read8(PLAYER_BASE + i * STRIDE + P_SLEEP) for i in range(4)],
            "sleepwalk": [e.read8(PLAYER_BASE + i * STRIDE + P_SLEEPWALK) for i in range(4)],
            "misfortune": [e.read8(PLAYER_BASE + i * STRIDE + P_MISFORTUNE) for i in range(4)],
            "npc": [(e.read8(NPC_F0C + i * 16), e.read8(NPC_F0D + i * 16)) for i in range(4, 8)],
        }


def main():
    print("差分测试 #42：冬眠卡 `0x4440ea`（卡 15）\n")
    f = F()

    print("[A] 扣卡 + 台词 + 恒返回 1")
    s = f.run(cur=0, price=1, players=[{}, {}, {}, {}])
    case("★ 先扣卡：`remove_card(cur, 15)`", s["rmc"], (0, 15))
    case("★ 调用顺序：扣卡 → 台词 → 敌意 → 落点事务",
         s["seq"], [1, 2, 3, 3, 3, 4])
    case("★ 台词 `player_say(cur, 3, 非空)` —— 只在最前说一句",
         (len(s["says"]), s["says"][0][0], s["says"][0][1], s["says"][0][2] != 0),
         (1, 0, 3, True))
    case("★ 恒返回 1（没有任何失败路径）", s["ret"], 1)

    print("\n[B] 对其它三名玩家施加：睡眠 5 天 + 清梦游 + 倒霉天数 +5 + 敌意 150×物價")
    case("★★ 三人全被冬眠（自己除外）", s["sleep"], [0, 5, 5, 5])
    case("★ `+0x37`（梦游）被清 0", s["sleepwalk"], [0, 0, 0, 0])
    case("★ `+0x42`（倒霉天數）各 +5", s["misfortune"], [0, 5, 5, 5])
    case("★★ 敌意 `update_hostility(目标, 当前, 150 × 物價指數)`（物價 = 1 ⇒ 150）",
         s["hos"], [(1, 0, 150), (2, 0, 150), (3, 0, 150)])
    case("★ 收尾 `0x41d476(0, 0, 1)` 一次", s["txn"], (0, 0, 1, 1))

    print("\n[C] 物價指數与「已休眠/梦游」的状态覆盖")
    s = f.run(cur=0, price=3, players=[{}, {}, {}, {}])
    case("★★ 物價 = 3 ⇒ 敌意 150×3 = 450", [h[2] for h in s["hos"]], [450, 450, 450])
    s = f.run(cur=0, players=[{}, {"sleep": 9, "sleepwalk": 7}, {}, {}])
    case("★★ 已经睡着（9）也被**覆盖**成 5、梦游（7）被清 0（不排除这些状态）",
         (s["sleep"][1], s["sleepwalk"][1]), (5, 0))

    print("\n[D] 四道跳过闸（自己 / 空槽 / 没落位 / 被阻碍）")
    s = f.run(cur=1, players=[{}, {}, {}, {}])
    case("★ 当前行动者（1 号）自己不会被冬眠", s["sleep"], [5, 0, 5, 5])
    case("   敌意也只对另外两人", s["hos"], [(0, 1, 150), (2, 1, 150), (3, 1, 150)])
    s = f.run(cur=0, players=[{}, {"who": 0}, {}, {}])
    case("★ 空玩家槽（`who_plays == 0`）跳过", s["sleep"], [0, 0, 5, 5])
    s = f.run(cur=0, players=[{}, {"x": 0}, {}, {}])
    case("★ 没落位（`player+0x08 == 0`）跳过", s["sleep"], [0, 0, 5, 5])
    s = f.run(cur=0, players=[{}, {"block": 1}, {}, {}])
    case("★ 被阻碍（`dword[player+0x32] != 0`）跳过", s["sleep"], [0, 0, 5, 5])
    case("   被阻碍者连带**不记敌意**", [h[0] for h in s["hos"]], [2, 3])

    print("\n[E] 替身槽（下标 4..7）：另一张表、不记敌意")
    s = f.run(cur=0, players=[{}, {}, {}, {}], npcs={4: 0, 5: 1, 6: 0, 7: 0})
    case("★★ 槽 +0x0a == 0 ⇒ `+0x0c = 5`、`+0x0d = 0`（不检查 who/坐标/阻碍）",
         s["npc"], [(5, 0), (9, 9), (5, 0), (5, 0)])
    case("★★ 替身槽**不记敌意**（敌意仍只有 3 个玩家）",
         [h[0] for h in s["hos"]], [1, 2, 3])
    case("   玩家侧的睡眠不受替身分支影响", s["sleep"], [0, 5, 5, 5])

    print("\n[F] 边界：没有符合条件的玩家")
    s = f.run(cur=0, players=[{"who": 0}, {"who": 0}, {"who": 0}, {"who": 0}],
              npcs={i: 1 for i in range(4, 8)})
    case("★ 只扣卡 + 说一句 + 落点事务，仍返回 1（卡照样消耗）",
         (s["rmc"], len(s["says"]), s["hos"], s["txn"][3], s["ret"]),
         ((0, 15), 1, [], 1, 1))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
