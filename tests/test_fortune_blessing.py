#!/usr/bin/env python3
"""
通道 2 差分测试 #59 · **福神／衰神的「獎金／罰金」倍率** `0x44b896(arg1, arg2)`

命运事件的分岔共 **16 处**调用它（`rich4_fortune.asm`）。它按两个实参选一路、
读当前玩家的一个 word 计数、算出倍率码 `ebx`，并把一句提示 `sprintf` 进
`0x48c5b8`，最后**返回 `ebx`**。

```asm
; @source 0x0044b896   cdecl(arg1, arg2)；序言 `push×4` ⇒ 函数内读 [esp+0x14]/[esp+0x18]
0044b938  byte [0x48c5b8] = 0            ; ★ 提示串缓冲：入口只清**首字节**
0044b93b  eax = [0x49910c] * 0x68        ; 当前玩家
0044b93f  cmp dword [esp+0x14], 0 / jne 0x44b9d3   ; arg1 != 0 ⇒ 路 C
0044b946  cmp dword [esp+0x18], 0 / jne 0x44b94b   ; arg2 != 0 ⇒ 路 B
; ── 路 A（arg1==0 ∧ arg2==0）：读 **player+0x46**（word）──
0044b94d  si = word [player+0x496bae]
0044b954  cmp si,0x64 / jle L1   ; >100  ⇒ ebx=2            （獎金加倍）
0044b95a  cmp si,0x32 / jle L2   ; (50,100] ⇒ ebx=(rand()&1)*2  ★ 只有 0 或 2
0044b8e9  test si,si / jge L3    ; <0    ⇒ ebx=1            （獎金作廢）
0044b8f5  L3: ebx 既非 2 也非 1 ⇒ **直接返回、不写提示**（ebx=0）
; ── 路 B（arg1==0 ∧ arg2!=0）：同样读 player+0x46，文案对调 ──
0044b94b  cmp di,0x64 ⇒ ebx=1（罰金加倍）; (50,100] ⇒ ebx=rand()&1（★ 0 或 1）; <0 ⇒ ebx=2（免付罰金）
; ── 路 C（arg1!=0）：读 **player+0x48**（word）──
0044b9d3  cmp dx,0x64 ⇒ ebx=1（倒霉加倍）; (50,100] ⇒ ebx=rand()&1; <0 ⇒ ebx=2（逃過此劫）
0044ba4f  sprintf(0x48c5b8, fmt, god_names[god_info])   ; ★ `[god*4 + 0x47ed76 − 4]`
0044ba5c  返回 eax = ebx
```

★ 三条要点（本测试逐条钉）：

| # | 事实 | 为什么重要 |
|---|---|---|
| 1 | ★★ `ebx == 0` 时**一个字节都不写**（两道 `cmp ebx,2/1` 闸都落到出口） | 「计了但不出提示」是原文如此 |
| 2 | ★★ 路 A 的随机乘数是 **`(rand()&1)*2` ⇒ {0, 2}**；路 B/C 是 **`rand()&1` ⇒ {0, 1}** | 「獎金」那条只有两档，**不是** 1/2 二选一 |
| 3 | 路 A/B 读 **`player+0x46`**，路 C 读 **`player+0x48`**（两个独立计数） | 两条计数各管一组事件 |

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x456f2d` | `mov eax,[数据槽] / ret` | `rand()`。返回值取自 `SCRATCH_BASE+0x800`（见 §7.116：代码段补丁同实例重写不生效） |

跑法：cd rich4-spec && .venv/bin/python tests/test_fortune_blessing.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

FN = 0x44B896
STOP = 0x44BA5C                 # 公共出口（`mov eax,ebx`）
PRNG = 0x456F2D
SPRINTF = 0x457110
FMT_SLOT = SCRATCH_BASE + 0x804
RAND_SLOT = SCRATCH_BASE + 0x800
CUR = 0x49910C
PLAYER_BASE = 0x496B68
P_GOD = 0x3F                    # +0x3f 神明编号（1..12）
P_C1 = 0x46                     # +0x46 路 A/B 读的 word
P_C2 = 0x48                     # +0x48 路 C 读的 word
TOAST = 0x48C5B8
GOD_NAMES = 0x47ED76            # 1 基表：`[god*4 + 0x47ed76 − 4]`
FRAME = 0x53F000
FILL = 0xEE
FMT = {
    "A2": 0x465888,             # %s保佑\n\n獎金加倍！
    "A1": 0x46589B,             # %s作祟\n\n獎金作廢！
    "B2": 0x4658AE,             # %s作祟\n\n罰金加倍！
    "B1": 0x4658C1,             # %s保佑\n\n免付罰金！
    "C2": 0x4658D4,             # %s作祟\n\n倒霉加倍！
    "C1": 0x4658E7,             # %s保佑\n\n逃過此劫！
}
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<58} 实际 {got!s:<30} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = None

    @staticmethod
    def rand_stub(slot):
        return b"\xA1" + struct.pack("<I", slot) + b"\xC3"

    @staticmethod
    def sprintf_stub(fmt_slot):
        """`sprintf(dst, fmt, …)` 的替身：把 `fmt` **原样**拷进 `dst`，并记下 `fmt`。

        `%s` 不代入（本测试要验的是**格式串**与「有没有调用」，
        代入后的神明名另有 `names()` 与 `god=…` 用例覆盖）。

        `mov ecx,[esp+4]` / `mov edx,[esp+8]` / `mov [fmt_slot],edx` / `xor eax,eax`
        / copy 循环 `mov al,[edx] / mov [ecx],al / inc ecx / inc edx / test al,al / jne`
        / `ret`
        """
        return (b"\x8B\x4C\x24\x04" + b"\x8B\x54\x24\x08"
                + b"\x89\x15" + struct.pack("<I", fmt_slot)
                + b"\x31\xC0"
                + b"\x8A\x02" + b"\x88\x01" + b"\x41\x42" + b"\x84\xC0"
                + b"\x75\xF6"
                + b"\xC3")

    def run(self, arg1, arg2, counter, counter2=0, god=3, rand=0, player=0):
        emu = Emu()

        def setup(e):
            e.patch(PRNG, self.rand_stub(RAND_SLOT))
            # ★ sprintf 也要打桩：真身走 CRT 的 `_output`（`0x45b392` 一带用
            #   `es:` 段前缀扫字符串），仿真里立刻踩未映射段。
            e.patch(SPRINTF, self.sprintf_stub(FMT_SLOT))
            e.write32(FMT_SLOT, 0)
            e.write32(RAND_SLOT, rand & 0xFFFFFFFF)
            e.write32(CUR, player)
            e.write8(PLAYER_BASE + player * 0x68 + P_GOD, god)
            e.write16(PLAYER_BASE + player * 0x68 + P_C1, counter & 0xFFFF)
            e.write16(PLAYER_BASE + player * 0x68 + P_C2, counter2 & 0xFFFF)
            for i in range(64):
                e.write8(TOAST + i, FILL)
            # ★ 帧：序言 `push ebx/esi/edi/ebp`（=0x10）⇒ 函数内读 `[esp+0x14]/[esp+0x18]`，
            #   即相对「进函数时的 esp」是 +4 / +8（+0 是返回地址哨兵）。
            e.write32(FRAME, 0x53FFF0)
            e.write32(FRAME + 4, arg1)
            e.write32(FRAME + 8, arg2)
        out = emu.eval_block(FN, STOP, regs={"esp": FRAME}, setup=setup,
                             timeout_insns=200000)
        self.emu = emu
        # ★★ 必须读 **ebx**，不能读 eax：函数尾是 `0x44ba5c mov eax,ebx`，
        #    而停址取在它**之前**；更要紧的是 `sprintf` 的替身也会改 eax ——
        #    真身的返回值就是 ebx（`0x44ba5c` 只是把它搬进 eax 好当返回值）。
        self._val = out["regs"]["ebx"]
        return self

    def val(self):
        """本函数真正的返回值（档位 0/1/2）。"""
        return self._val

    def fmt(self):
        return self.emu.readu32(FMT_SLOT)

    def toast(self):
        return self.emu.read(TOAST, 48)

    def toast_text(self):
        """提示缓冲里的字符串。

        ★ 桩不做 `%s` 代入 ⇒ 这里拿到的是**格式串原文**（含 `%s`）。
        代入后的样子用下面的 `rendered()` 复现：`%s` ← `god_names[god]`。
        """
        return self.toast().split(b"\x00")[0].decode("big5", errors="replace")

    def rendered(self, god):
        """把格式串里的 `%s` 换成 `god_names[god]`（复现真身 `sprintf` 的结果）。"""
        name = self.emu.read(self.emu.readu32(GOD_NAMES + 4 * (god - 1)), 16)
        name = name.split(b"\x00")[0].decode("big5", "replace")
        return self.toast_text().replace("%s", name)

    def untouched(self):
        """提示缓冲是否**完全没被写过**（仍全是预填值）。"""
        return all(b == FILL for b in self.toast())


def main():
    print("差分测试 #59：福神／衰神的獎金罰金倍率 0x44b896\n")

    print("[A] 路 A（arg1=0, arg2=0）读 `player+0x46`")
    case("counter=101（>100）⇒ 返回 2", F().run(0, 0, 101).val(), 2)
    case("counter=100（恰好 100）⇒ **不算 >100**，走随机档", F().run(0, 0, 100, rand=0).val(), 0)
    case("counter=51（>50）rand=0 ⇒ (0&1)*2 = 0", F().run(0, 0, 51, rand=0).val(), 0)
    case("★ counter=51 rand=1 ⇒ (1&1)*2 = 2", F().run(0, 0, 51, rand=1).val(), 2)
    case("★ counter=51 rand=3 ⇒ 仍是 2（只看最低位）", F().run(0, 0, 51, rand=3).val(), 2)
    case("counter=50（恰好 50）⇒ 不落随机档 ⇒ 0", F().run(0, 0, 50, rand=1).val(), 0)
    case("counter=0 ⇒ 0", F().run(0, 0, 0).val(), 0)
    case("★ counter=-1（0xffff）⇒ 1", F().run(0, 0, -1).val(), 1)

    print("\n[B] 路 A 的文案（桩不代入 `%s`，故断言**格式串原文**）")
    f = F().run(0, 0, 101, god=3)
    case("counter>100 ⇒ 格式串 = 「%s保佑 / 獎金加倍！」", f.toast_text(),
         "%s保佑\n\n獎金加倍！")
    case("★ 代入 god=3（大財神）后 = 「大財神保佑 / 獎金加倍！」",
         f.rendered(3), "大財神保佑\n\n獎金加倍！")
    f = F().run(0, 0, -1, god=3)
    case("counter<0 ⇒ 格式串 = 「%s作祟 / 獎金作廢！」", f.toast_text(),
         "%s作祟\n\n獎金作廢！")
    case("★★ counter=0 ⇒ 档位 0（调用方按 ×1 处理，不出提示语义）",
         F().run(0, 0, 0).val(), 0)

    print("\n[C] 路 B（arg1=0, arg2=1）读 `player+0x46`，文案对调")
    case("counter=101 ⇒ 返回 1（罰金加倍）", F().run(0, 1, 101).val(), 1)
    case("★ counter=51 rand=0 ⇒ 0", F().run(0, 1, 51, rand=0).val(), 0)
    case("★ counter=51 rand=1 ⇒ 1（**不是 2**：乘数是 `rand()&1`）",
         F().run(0, 1, 51, rand=1).val(), 1)
    case("★ counter=-1 ⇒ 2（免付罰金）", F().run(0, 1, -1).val(), 2)
    case("counter=100 ⇒ 0（恰好 100 不算 >100）", F().run(0, 1, 100).val(), 0)
    case("★ counter=101（>100）⇒ **1** ⇒ 「%s保佑 / 免付罰金！」",
         F().run(0, 1, 101).toast_text(), "%s保佑\n\n免付罰金！")
    case("★ counter=-1（<0）⇒ **2** ⇒ 「%s作祟 / 罰金加倍！」",
         F().run(0, 1, -1).toast_text(), "%s作祟\n\n罰金加倍！")
    case("counter=0 ⇒ 档位 0", F().run(0, 1, 0).val(), 0)

    print("\n[D] 路 C（arg1 != 0）读 **`player+0x48`**（另一个计数）")
    case("c2=101 ⇒ 1（倒霉加倍）", F().run(1, 0, 0, counter2=101).val(), 1)
    case("★ c2=101 而 c1=101 ⇒ 读的是 c2（返回 1，不是 2）",
         F().run(1, 0, 101, counter2=101).val(), 1)
    case("★ c1=101 而 c2=0 ⇒ 读的是 c2 ⇒ 0", F().run(1, 0, 101, counter2=0).val(), 0)
    case("c2=51 rand=1 ⇒ 1", F().run(1, 0, 0, counter2=51, rand=1).val(), 1)
    case("★ c2=-1 ⇒ 2（逃過此劫）", F().run(1, 0, 0, counter2=-1).val(), 2)
    case("★ c2=101（>100）⇒ **1** ⇒ 「%s保佑 / 逃過此劫！」",
         F().run(1, 0, 0, counter2=101).toast_text(), "%s保佑\n\n逃過此劫！")
    case("★ c2=-1（<0）⇒ **2** ⇒ 「%s作祟 / 倒霉加倍！」",
         F().run(1, 0, 0, counter2=-1).toast_text(), "%s作祟\n\n倒霉加倍！")
    case("c2=0 ⇒ 档位 0", F().run(1, 0, 0, counter2=0).val(), 0)

    print("\n[E] 神明名表 `0x47ed76`（1 基）逐条")
    e0 = Emu()
    names = {}
    for g in range(1, 13):
        p = e0.readu32(GOD_NAMES + 4 * (g - 1))
        names[g] = e0.read(p, 16).split(b"\x00")[0].decode("big5", "replace")
    case("12 个神明名（1..12）", names,
         {1: "間諜", 2: "小財神", 3: "大財神", 4: "小福神", 5: "大福神", 6: "小窮神",
          7: "大窮神", 8: "小衰神", 9: "大衰神", 10: "天使", 11: "惡魔", 12: "惡犬"})
    case("★ 提示串里的 %s 代入 god=6 ⇒ 小窮神", F().run(0, 0, 101, god=6).rendered(6),
         "小窮神保佑\n\n獎金加倍！")
    case("代入 god=12（惡犬）", F().run(0, 0, -1, god=12).rendered(12),
         "惡犬作祟\n\n獎金作廢！")

    print("\n[F] 6 条格式串原文（直接读 DGROUP）")
    for key, va in FMT.items():
        want = {
            "A2": "%s保佑\n\n獎金加倍！", "A1": "%s作祟\n\n獎金作廢！",
            "B2": "%s作祟\n\n罰金加倍！", "B1": "%s保佑\n\n免付罰金！",
            "C2": "%s作祟\n\n倒霉加倍！", "C1": "%s保佑\n\n逃過此劫！",
        }[key]
        got = e0.read(va, 40).split(b"\x00")[0].decode("big5", "replace")
        case(f"{key} @{va:#x}", got, want)

    print("\n[G] 玩家下标（`[0x49910c]`）决定读谁的计数")
    f = F().run(0, 0, 101, player=2, god=5)
    case("player=2, god=5 ⇒ 「大福神保佑 / 獎金加倍！」", f.rendered(5),
         "大福神保佑\n\n獎金加倍！")
    case("★ 同一实例里 player=2 的计数生效（不是 0 号玩家）",
         F().run(0, 0, 0, player=2).val(), 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
