#!/usr/bin/env python3
"""
通道 2 差分测试 #15 · `0x0040d761(player)` —— **解除关押：清占用表 + 清四个阻塞计数器**

```asm
0040d766  eax = player*0x68
0040d769  if ([eax + 0x496b9c] == 0) goto 0x40d785      ; +0x34 = inPrison
0040d774      [player + 0x496b30] = 0                   ; ★ 监狱占用表（下标 = **玩家号**，步长 1）
0040d77d      call 0x40bf93(player, 1)                  ; 换图标（MKF）
0040d785  if ([eax + 0x496b9d] == 0) goto 0x40d7a4      ; +0x35 = inHospital
0040d793      [player + 0x496b60] = 0                   ; ★ 医院占用表
0040d79c      call 0x40bf93(player, 0)
0040d7a4  imul ebx, ebx, 0x68
0040d7a9  dword [ebx + 0x496b9a] = 0                    ; ★ 四个计数器一起清（+0x32..+0x35）
```

⇒ 两条容易做错的：
1. 占用表**按玩家号**索引（`[ebx + 0x496b30]`，ebx = **玩家下标**，不是 `*0x68`）；
2. 最后那句是 **dword** 清零 —— 把**刚刚用来做判据的** `+0x34`/`+0x35` 也一并抹掉。

⚠️ **打桩**：两支都会 `call 0x40bf93(player, which)`，而它是 **MKF 资源装载**
（`0x40bff7 call mkf_read_resource`，把图标指针写进每玩家表 `0x498eb8`）
⇒ 纯仿真 `UC_ERR_READ_UNMAPPED @0x450471`。本用例把它打桩成 `ret`；
被打掉的只是"换图标"（`writes` 只有 `0x498ea0..a3` 与 `0x498eb8` 两张**表现**表），
被验的是它**之前**的占用表与计数器改动。

跑法：cd rich4-spec && .venv/bin/python tests/test_confinement_release.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

RELEASE_CONFINEMENT = 0x40D761
ICON_REFRESH = 0x40BF93          # 打桩：MKF 图标装载

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
IN_PRISON, IN_HOSPITAL = 0x34, 0x35
BLOCKING_DWORD = 0x32            # +0x32..+0x35 = inHotel/disappearing/inPrison/inHospital

PRISON_TABLE = 0x496B30          # 8 槽：0..3 玩家、4..7 物件
HOSPITAL_TABLE = 0x496B60

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<54} 实际 {got_s!s:<20} 期望 {want_s!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()

    def release(self, player=0, in_prison=0, in_hospital=0,
                prison_slots=(0x0A, 0x0B, 0x0C, 0x0D),
                hospital_slots=(0x1A, 0x1B, 0x1C, 0x1D)):
        def setup(emu):
            emu.patch(ICON_REFRESH, b"\xc3")
            for i in range(4):
                base = PLAYER_BASE + i * PLAYER_STRIDE
                emu.write8(base + BLOCKING_DWORD + 0, 0x11)
                emu.write8(base + BLOCKING_DWORD + 1, 0x22)
                emu.write8(base + BLOCKING_DWORD + 2, 0x33)
                emu.write8(base + BLOCKING_DWORD + 3, 0x44)
            base = PLAYER_BASE + player * PLAYER_STRIDE
            emu.write8(base + IN_PRISON, in_prison)
            emu.write8(base + IN_HOSPITAL, in_hospital)
            for k, v in enumerate(prison_slots):
                emu.write8(PRISON_TABLE + k, v)
            for k, v in enumerate(hospital_slots):
                emu.write8(HOSPITAL_TABLE + k, v)

        self.emu.call(RELEASE_CONFINEMENT, [player], setup=setup)
        base = PLAYER_BASE + player * PLAYER_STRIDE
        return {
            "dword": [self.emu.read8(base + BLOCKING_DWORD + k) for k in range(4)],
            "prison": [self.emu.read8(PRISON_TABLE + k) for k in range(4)],
            "hospital": [self.emu.read8(HOSPITAL_TABLE + k) for k in range(4)],
            # 四个玩家各自的 dword（用来验证"只动被调那个人"）
            "allDwords": [
                [self.emu.read8(PLAYER_BASE + i * PLAYER_STRIDE + BLOCKING_DWORD + k)
                 for k in range(4)]
                for i in range(4)
            ],
        }


def main():
    print("差分测试 #15：0x0040d761(player) 解除关押\n")
    f = F()

    print("[1] 两个标志都为 0 → 只清四个计数器，占用表不动")
    r = f.release(in_prison=0, in_hospital=0)
    case("dword(+0x32..+0x35) 全清 0", r["dword"], [0, 0, 0, 0])
    case("监狱占用表原样", r["prison"], [0x0A, 0x0B, 0x0C, 0x0D])
    case("医院占用表原样", r["hospital"], [0x1A, 0x1B, 0x1C, 0x1D])

    print("\n[2] 只在狱（+0x34 != 0）→ 清**监狱**那一格")
    r = f.release(player=0, in_prison=1)
    case("★ 监狱表 0 号格被清（按玩家号索引）", r["prison"], [0x00, 0x0B, 0x0C, 0x0D])
    case("医院表不动", r["hospital"], [0x1A, 0x1B, 0x1C, 0x1D])

    print("\n[3] 只住院（+0x35 != 0）→ 清**医院**那一格")
    r = f.release(player=0, in_hospital=1)
    case("医院表 0 号格被清", r["hospital"], [0x00, 0x1B, 0x1C, 0x1D])
    case("监狱表不动", r["prison"], [0x0A, 0x0B, 0x0C, 0x0D])

    print("\n[4] 两者都有 → 两张都清那一格")
    r = f.release(player=0, in_prison=1, in_hospital=1)
    case("监狱表 0 号清", r["prison"][0], 0)
    case("医院表 0 号清", r["hospital"][0], 0)

    print("\n[5] 下标跟着玩家走（玩家 2 → 第 2 格）")
    r = f.release(player=2, in_prison=1, in_hospital=1)
    case("监狱表只剩 0/1/3 格", r["prison"], [0x0A, 0x0B, 0x00, 0x0D])
    case("医院表只剩 0/1/3 格", r["hospital"], [0x1A, 0x1B, 0x00, 0x1D])

    print("\n[6] ★ 最后那句是 **dword** 清零：判据字节 +0x34/+0x35 也被抹掉")
    r = f.release(player=0, in_prison=1, in_hospital=1)
    case("四个字节全 0（含刚用来判断的 +0x34/+0x35）", r["dword"], [0, 0, 0, 0])
    r = f.release(player=1, in_prison=1)
    case("只动被调玩家（1 号）：其余三人 dword 保持 0x11/0x22/0x33/0x44",
         (r["dword"], r["allDwords"][0], r["allDwords"][2], r["allDwords"][3]),
         ([0, 0, 0, 0], [0x11, 0x22, 0x33, 0x44], [0x11, 0x22, 0x33, 0x44],
          [0x11, 0x22, 0x33, 0x44]))
    case("  监狱表清的是 1 号格", r["prison"], [0x0A, 0x00, 0x0C, 0x0D])

    print("\n[7] 幂等：清完再调一次仍全 0")
    f.release(player=0, in_prison=1, in_hospital=1)
    r2 = f.release(player=0, in_prison=0, in_hospital=0)
    case("第二次调用后仍是全 0", r2["dword"], [0, 0, 0, 0])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
