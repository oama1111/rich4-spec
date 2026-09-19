#!/usr/bin/env python3
"""
通道 2 差分测试 #52 · **神明對過路費的加成/減免** `0x41d709`（6 路跳表 `0x41d6f1`）

`0x41d709(player, baseToll, &buf)` 按**付款者身上的神明**调整过路费，
返回调整后的金额（`eax`），并把一句提示交给 `sprintf`。
住宅/設施/企業三条过路费路径**共用**这一支。

```asm
; @source 0x0041d709
0041d709  push ebx / push esi / sub esp,0x80
0041d711  edx  = [esp+0x90]              ; arg1 = 玩家索引
0041d718  esi  = [esp+0x94]              ; arg2 = baseToll（★ 也是「原值」基准）
0041d71f  ebx  = esi                     ; 结果初值 = 原值
0041d721  eax  = arg1 * 0x68
0041d729  al   = byte [eax + 0x496ba7]   ; ★ player + 0x3f = god_info
0041d72f  dec al / cmp al,5 / ja 0x41d79e ; 只有 god 1..6 落跳表
0041d73a  jmp  dword [eax*4 + 0x41d6f1]
;   跳表（实测 dump）= [0x41d741, 0x41d758, 0x41d79e, 0x41d79e, 0x41d76f, 0x41d788]
;     1 小財神 → 0x41d741：sprintf(0x48c6a0, "小財神顯靈\n\n%s減免一半！", &local) + `sar ebx,1`
;     2 大財神 → 0x41d758：sprintf(0x48c6a0, "大財神顯靈\n\n免付%s！",   &local) + `xor ebx,esi`（= 0）
;     3 小福神 → 0x41d79e ┐ ★ **与「不改变」同一个目标**
;     4 大福神 → 0x41d79e ┘   ⇒ 福神对过路费**没有影响**、也不 sprintf
;     5 小窮神 → 0x41d76f：sprintf(0x48c6a0, "小窮神顯靈\n\n%s加付50％！", &local) + `sar ebx,1` + `add ebx,esi`
;     6 大窮神 → 0x41d788：sprintf(0x48c6a0, "大窮神顯靈\n\n加倍付%s！",   &local) + `lea ebx,[esi+esi]`
0041d79e  cmp  ebx, esi / je 0x41d7c9
0041d7a0  fmt="%d" / sprintf(&local,…) / `0x44f230`（金额→显示串，内部走导入 thunk）
0041d7c9  返回 eax = ebx                 ; ★ 唯一的金额出口
```

★ 三条**机器次序**要点（都用返回值 `eax` 直接验，不靠读汇编）：
  1. 小財神 `sar ebx,1` ⇒ **算术**右移（`>>`），奇数**向下取整**。
  2. 小窮神先 `sar ebx,1` **再** `add ebx,esi` ⇒ 是 `toll/2 + toll`，
     **不是** `toll*1.5` 的浮点近似。
  3. 大財神 `xor ebx,esi`（而不是 `mov ebx,0`）⇒ 既得到 0，又让后面
     `cmp ebx,esi / je` **仍然成立**（⇒「免付」时不弹第二句）。

## 打桩

| VA | 桩 | 为什么 |
|---|---|---|
| `0x457110` | `sprintf(dst, fmt, …)` | 记下 `(dst, fmt)` 与调用次数；把格式串真拷进 `dst` |
| `0x46228c` | 导入 thunk → 桩区 `ret` | `0x44f230` 内部的 `call dword cs:[0x46228c]` 目标是未映射的 `0x624ce`（User32） |

跑法：cd rich4-spec && .venv/bin/python tests/test_god_toll_modifier.py
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

FN = 0x41D709
PLAYER_BASE = 0x496B68
STRIDE = 0x68
P_GOD = 0x3F
FMT_SMALL_FORTUNE = 0x463C67     # 小財神顯靈\n\n%s減免一半！
FMT_BIG_FORTUNE = 0x463C80       # 大財神顯靈\n\n免付%s！
FMT_SMALL_POVERTY = 0x463C95     # 小窮神顯靈\n\n%s加付50％！
FMT_BIG_POVERTY = 0x463CAE       # 大窮神顯靈\n\n加倍付%s！
TABLE = 0x41D6F1
MSG_BUF = 0x48C6A0               # sprintf 真正的 dst（DGROUP 全局消息缓冲）
LOCAL_BUF = SCRATCH_BASE + 0x2000  # arg2 指的**文本**（%s 的实参）
FRAME_BASE = 0x53F000            # 手搭栈帧基址（落在大栈里，远离返回哨兵）
M_BUFCNT, M_BUFTXT = SCRATCH_BASE + 0x100, SCRATCH_BASE + 0x104
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'OK ' if ok else 'NG '} {desc:<56} 实际 {got!s:<20} 期望 {want!s}")
    return ok


class F:
    """★ 打桩必须放在 `run()` 的 `setup()` 里，不能放 `__init__`。

    踩过的坑（很贵，记在这里）：`call()` 开头就 `reset()`，而 `reset()` 只还原
    `self._snapshot`。`patch(va, …)` 会把**命中段**的当前内容重拍进快照
    （见 `emulate.py` 里 2026-09-18 那段注释）—— 但在 `__init__` 里第一次
    `patch()` 时任务段尚未被改过，于是重拍的仍是**原始内容**；
    紧接着的第一次 `call()` 的 `reset()` 就把补丁**还原掉了**。
    表现极具误导性：`read()` 明明读到补丁字节，执行却是原版代码。
    ⇒ 把补丁写进 `setup()`（`reset()` 之后、压栈之前执行），补丁必然生效。

    ★★ 还有第二个同族坑：**同一实例里 `patch()` 之后，先前已翻译过的基本块
    仍会跑旧码**（`ctl_remove_cache` 在本 Unicorn 版本上不足以失效它）。
    实测：`patch(0x41D7B4, jmp)` 之后 `read()` 读到新字节，执行却仍走旧分支，
    连 hook 都只在**块首**触发、根本不报 0x41D7B4。⇒ 本类**每个用例新建一个
    `Emu()`**（实测一次构造 ~23ms，用例数十个，总开销可忽略）。
    """

    def __init__(self):
        self.emu = None

    def _install(self, e):
        # 只替换 `sprintf`（`0x457110`）为「原样拷贝」桩，用于记录**压进来的格式串**。
        # 取参：dst = [esp+4]、fmt = [esp+8]（cdecl）。
        e.patch(0x457110,
                b"\x8B\x4C\x24\x04" + b"\x8B\x54\x24\x08"
                + b"\x89\x15" + struct.pack("<I", M_BUFTXT)
                + b"\x31\xC0"
                # copy: al=[edx] ; [ecx]=al ; inc ecx/edx ; test al,al ; jne 回循环头
                + b"\x8A\x02" + b"\x88\x01" + b"\x41\x42" + b"\x84\xC0"
                + b"\x75\xF6"
                + b"\xFF\x05" + struct.pack("<I", M_BUFCNT)
                + b"\xC3")

    def run(self, god, toll, player=0, text=None):
        """在 **0x41d79e（跳表汇合点）之前**停下。

        `eval_block` 的停址语义是「EIP 到达该地址即停」，而各分支都以
        `jmp 0x41d79e` 汇合 ⇒ 停在 0x41d79e 时 `ebx` 就是最终金额。
        这样完全绕开了后面那段无法建模的 Win32 文本渲染
        （`0x41d7ac`→`0x440cac`→`0x44f9d8`→`0x44fa8f` 的 `call dword cs:[0x46228c]`）。
        """
        emu = Emu()
        text = SCRATCH_BASE + 0x2000 if text is None else text
        def setup(e):
            self._install(e)
            e.write8(0x496B68 + player * STRIDE + P_GOD, god)
            e.write32(M_BUFCNT, 0)
            e.write32(M_BUFTXT, 0)
            for i in range(0x30):
                e.write8(FRAME_BASE + i, 0)
            # 栈帧（实测：序言 4+4+0x80 = 0x88 ⇒ arg1=[esp+0x8c]、arg2=0x90、arg3=0x94）
            e.write32(FRAME_BASE + 4, player)                    # arg1 付款方
            e.write32(FRAME_BASE + 8, text)                      # arg2 填 %s 的文本
            e.write32(FRAME_BASE + 0xc, toll)                    # arg3 原始租金
            e.write32(FRAME_BASE + 0x10, 0x53FFF0)               # 返回地址哨兵
        out = emu.eval_block(FN, 0x41D79E, regs={"esp": FRAME_BASE},
                             setup=setup, timeout_insns=200000)
        self.emu = emu
        return {
            "toll": out["regs"]["ebx"],      # ★ 调整后的金额
            "esi": out["regs"]["esi"],       # 原值（恒等于入参 toll）
            "edx": out["regs"]["edx"],       # 填 %s 的文本指针
            "sprintf_n": emu.readu32(M_BUFCNT),
            "fmt": emu.readu32(M_BUFTXT),
        }


def main():
    print("差分测试 #52：神明對過路費的加成/減免 0x41d709\n")
    f = F()

    # ── [A] 跳表本身 ────────────────────────────────────────────────────
    print("[A] 跳表 `0x41d6f1`（6 项，实测 dump）")
    expect = [0x41D741, 0x41D758, 0x41D79E, 0x41D79E, 0x41D76F, 0x41D788]
    emu0 = Emu()
    got = [struct.unpack("<I", emu0.read(TABLE + 4 * i, 4))[0] for i in range(6)]
    case("6 项入口地址逐项相同", got, expect)
    case("★ 索引 3/4（福神）指向 **与「不改变」同一个地址** `0x41d79e`",
         (got[2], got[3]), (0x41D79E, 0x41D79E))

    # ── [B] 四个「有神」分支各弹哪一句 ──────────────────────────────────
    print("\n[B] `sprintf` 的格式串与调用次数（逐条对表）")
    for god, fmt, name in ((1, FMT_SMALL_FORTUNE, "小財神"), (2, FMT_BIG_FORTUNE, "大財神"),
                           (5, FMT_SMALL_POVERTY, "小窮神"), (6, FMT_BIG_POVERTY, "大窮神")):
        s = f.run(god, 1000)
        case(f"god {god}（{name}）⇒ 弹对应那句", (s["sprintf_n"], s["fmt"]), (1, fmt))

    # ── [C] 金额：用**返回值**验机器次序 ────────────────────────────────
    print("\n[C] 金额（`ebx`，即函数返回的 `eax`）—— 三种运算都作用在**原值**上")
    case("god 0（无神）toll=1000 ⇒ 原样", f.run(0, 1000)["toll"], 1000)
    case("god 1（小財神）toll=1000 ⇒ 1000 >> 1 = 500", f.run(1, 1000)["toll"], 500)
    case("★ god 1（小財神）toll=999 ⇒ 算术右移向下取整 = 499", f.run(1, 999)["toll"], 499)
    case("god 2（大財神）toll=1000 ⇒ 0（`xor ebx,esi`）", f.run(2, 1000)["toll"], 0)
    case("★ god 2（大財神）toll=0 ⇒ 0", f.run(2, 0)["toll"], 0)
    case("god 3（小福神）toll=1000 ⇒ 原样（与「不改变」同一目标）", f.run(3, 1000)["toll"], 1000)
    case("god 4（大福神）toll=1000 ⇒ 原样", f.run(4, 1000)["toll"], 1000)
    case("★ god 5（小窮神）toll=1000 ⇒ 1000>>1 + 1000 = 1500", f.run(5, 1000)["toll"], 1500)
    case("★ god 5（小窮神）toll=999 ⇒ 499 + 999 = 1498（证「先移位再加」，非 `×1.5`）",
         f.run(5, 999)["toll"], 1498)
    case("god 6（大窮神）toll=1000 ⇒ 2000（`lea ebx,[esi+esi]`）", f.run(6, 1000)["toll"], 2000)
    case("★ god 6（大窮神）toll=999 ⇒ 1998（整数加倍，无浮点）", f.run(6, 999)["toll"], 1998)
    case("★ 大額不溢出（toll=1_000_000_000，god 6）⇒ 2_000_000_000",
         f.run(6, 1000000000)["toll"], 2000000000)

    # ── [D] 无神/越界一律原样、且一次都不 sprintf ──────────────────────
    print("\n[D] 判据只认 `god_info ∈ 1..6`（`dec al / cmp al,5 / ja`）")
    for god in (0, 3, 4, 7, 8, 0x0C, 0x20, 0xFF):
        s = f.run(god, 777)
        case(f"god {god} ⇒ 不 sprintf 且返回 777", (s["sprintf_n"], s["toll"]), (0, 777))

    # ── [E] 判据取自**玩家索引**对应的记录 ─────────────────────────────
    print("\n[E] `god_info` 的取址 = `player*0x68 + 0x496ba7`")
    for god, want in ((1, 500), (2, 0), (5, 1500), (6, 2000)):
        s = f.run(god, 1000, player=2)
        case(f"player=2 god={god} ⇒ {want}", s["toll"], want)
    f.run(6, 1000, player=2)                       # 先污染 player2
    s = f.run(1, 1000, player=0)                   # 再验 player0
    case("★ 上一步把 player2 设成 god 6 **不影响** player0 的判定",
         (s["sprintf_n"], s["toll"]), (1, 500))

    # ── [F] arg2 是「要填进 %s 的文本」本身，本函数不读它 ──────────────
    print("\n[F] arg2 只是 `%s` 的实参（本函数**不解引用**它）")
    #   （`edx` **不能**用来看 arg2：本函数的桩 `sprintf` 内部会 `mov edx,[esp+8]`
    #    把 `edx` 覆盖成格式串地址 —— 第一版就是这么写错、被这条用例抓出来的。）
    for text in (0x4630F4, SCRATCH_BASE + 0x2000, 0x499000):
        s = f.run(1, 1000, text=text)
        case(f"★ arg2={text:#x} ⇒ 金额/提示句与默认完全相同",
             (s["toll"], s["sprintf_n"], s["fmt"]), (500, 1, FMT_SMALL_FORTUNE))
    case("★ 同上，god 6 ⇒ 金额仍是 2000（本函数不读 arg2 指向的内容）",
         f.run(6, 1000, text=0x4630F4)["toll"], 2000)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
