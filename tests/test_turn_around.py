#!/usr/bin/env python3
"""
通道 2 差分测试 #26 · **掉头**（轉向卡 / 特殊棋子）`0x0040c78c`（390 字节）

全 exe 的调用点里，玩家那一条来自轉向卡（`0x00443025 call 0x40c78c`）。
它做**两**件事，第二件此前只在复刻的注释里挂着"未实现"：

1. **朝向 +4（半圈）**；
2. ★★ **把「来路」`last_node` 改成一个随机邻居** —— 从当前格的 4 个邻接槽里筛出
   候选（非 0、该槽**未被封路**、且 **≠ 旧的 `last_node`**），再 `rand() % k` 摇一个写回去；
   一个候选都没有就写 0。

第 2 件是**规则可见**的：`0x40c101`（行走选路）会避开 `last_node`，所以改它
就是"换一个方向走回去"。

## 反汇编（A 级）

```asm
0040c793  push 0 / push 0x4823f2 / call 0x4542ce     ; 掉头音效
0040c7a2  edx = 目标（玩家号或 4..7 的替身号）
0040c7a6  cmp edx, 4 / jge 0x40c85e                  ; ★ ≥4 走替身表分支
; ── 玩家分支 ──
0040c7b2  dl = [player + 0x10] ; add 4 ; and 7 ; 写回 ; ★ 掉头
0040c7c6  dx = [player + 0x0c]                       ; nodeId
0040c7dd  ecx = node表 + nodeId*0x28
0040c7e3  esi = 0x40000000                           ; 封路掩码 bit30 起，每槽 sar 1
0040c7ea/0x40c7f2  for (slot = 0..3):
0040c7f4      ax = word [ecx + slot*2 + 0x18]        ; adjacent[slot]
0040c7f9      test ax,ax / je 下一槽                 ; 空槽跳过
0040c7fe      test dword [ecx + 0x24], esi / jne 下一槽 ; ★ 被封路跳过
0040c80f      edi = 旧 last_node（[player + 0x0e]）
0040c81e      cmp edi, ax / je 下一槽                ; ★ 等于旧来路跳过
0040c824      word [esp + ebx*2] = ax ; ebx++        ; 收进候选
0040c830  if (ebx != 0) { call 0x456f2d ; idiv ebx ; last_node = 候选[余数] }
0040c850  else          { last_node = 0 }
; ── 替身分支（0x40c85e，与玩家同构）──
0040c86a  dl = [slot + 0x498e31] ; add 4 ; and 7 ; 写回 ; ★ 掉头（+9 = direction）
0040c87e  dx = word [slot + 0x498e2c]                ; 替身的 nodeId（+4）
0040c8c2  di = word [slot + 0x498e2e]                ; 旧 last_node（+6）
0040c8e8  call 0x456f2d / idiv ebx / word [slot + 0x498e2e] = 候选[余数]
```

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x4542ce` | 掉头音效 | `ret` |
| `0x456f2d` | PRNG | **返回固定值**（本测试用它控制"摇到第几个候选"）|

跑法：cd rich4-spec && .venv/bin/python tests/test_turn_around.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

TURN_AROUND = 0x40C78C

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_NODE, P_LAST, P_FACING = 0x0C, 0x0E, 0x10
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10
A_NODE, A_LAST, A_DIR = 0x04, 0x06, 0x09
NODE_TABLE_PTR = 0x498E80
NODE_STRIDE = 0x28
ADJACENT_OFF, FLAGS_OFF = 0x18, 0x24

SOUND = 0x4542CE
PRNG = 0x456F2D
RAND_SLOT = SCRATCH_BASE + 0x800  # 桩从它读"这次 rand() 返回几"

NODES = SCRATCH_BASE + 0x1000
CENTER = 50
NEIGHBOURS = (51, 52, 53, 54)  # 4 个邻接槽的目标
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<18} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(SOUND, b"\xC3")
        self.emu.patch(PRNG, self.rand_stub(RAND_SLOT))

    def rand_stub(self, slot):
        """
        PRNG 桩：`mov eax, [slot] / ret` —— 返回值来自**数据**，不是指令立即数。

        ★★ 为什么不能每个用例重写一段 `mov eax, imm32` 的桩：**代码段的补丁只在
        "首次"生效**。`patch()` 只对**可写段**刷新快照，而 AUTO（0x401000 起）不在
        可写段表里 ⇒ 第一次 patch 之后 `reset()` 会把那一次的内容当作初始状态，
        之后任何重写都会被 `reset()` 抹掉（本测试踩了：`rand=5` 之后改 `rand=7`，
        实测仍按 5 走）。把变化的部分放进**数据**就绕开了：指令一次装好，
        每个用例只改那个 slot。
        """
        return b"\xA1" + struct.pack("<I", slot) + b"\xC3"

    def run(self, target, *, facing=2, last_node=0, node=CENTER, adj=None,
            blocked=(), rand=0, actor_facing=2, actor_last=0):
        """`adj` 缺省 = 四个邻接槽全给 NEIGHBOURS；`blocked` = 要封的槽号集合"""
        adj = adj if adj is not None else list(NEIGHBOURS)

        def setup(emu):
            emu.write32(RAND_SLOT, rand & 0xFFFFFFFF)  # ★ 桩从数据读返回值，见 rand_stub
            emu.write32(NODE_TABLE_PTR, NODES)
            base = NODES + node * NODE_STRIDE  # 表按 nodeId 直接索引
            for slot in range(4):
                emu.write16(base + ADJACENT_OFF + slot * 2, adj[slot])
            flags = 0
            for slot in blocked:
                flags |= 0x40000000 >> slot
            emu.write32(base + FLAGS_OFF, flags)
            if target < 4:
                pb = PLAYER_BASE + target * PLAYER_STRIDE
                emu.write16(pb + P_NODE, node)
                emu.write16(pb + P_LAST, last_node)
                emu.write8(pb + P_FACING, facing)
            else:
                ab = ACTOR_BASE + (target - 4) * ACTOR_STRIDE
                emu.write16(ab + A_NODE, node)
                emu.write16(ab + A_LAST, actor_last)
                emu.write8(ab + A_DIR, actor_facing)

        self.emu.call(TURN_AROUND, [target], setup=setup)
        e = self.emu
        if target < 4:
            pb = PLAYER_BASE + target * PLAYER_STRIDE
            return {"kind": "player", "facing": e.read8(pb + P_FACING),
                    "last": e.read16(pb + P_LAST), "rand": rand}
        ab = ACTOR_BASE + (target - 4) * ACTOR_STRIDE
        return {"kind": "actor", "facing": e.read8(ab + A_DIR),
                "last": e.read16(ab + A_LAST), "rand": rand}


def main():
    print("差分测试 #26：掉头（轉向卡）—— 0x40c78c\n")
    f = F()

    print("[1] 朝向 +4（半圈）")
    for d in range(8):
        s = f.run(0, facing=d)
        case(f"facing {d} → {(d + 4) & 7}", s["facing"], (d + 4) & 7)
    s = f.run(2, facing=7)
    case("玩家号是参数指定的那一位（2 号）", s["facing"], 3)

    print("\n[2] ★★ 来路 `last_node` = 候选里 `rand() % k` 摇一个")
    s = f.run(0, last_node=0, rand=0)
    case("四个邻接槽都可用、rand=0 ⇒ 取第 0 个", s["last"], NEIGHBOURS[0])
    s = f.run(0, last_node=0, rand=5)
    case("rand=5、k=4 ⇒ 5 % 4 = 1 ⇒ 第 1 个", s["last"], NEIGHBOURS[1])
    s = f.run(0, last_node=0, rand=7)
    case("rand=7 ⇒ 3 ⇒ 第 3 个", s["last"], NEIGHBOURS[3])

    print("\n[3] 候选的三个筛子：空槽 / 封路 / 等于旧来路")
    s = f.run(0, adj=[0, NEIGHBOURS[1], 0, NEIGHBOURS[3]], rand=0)
    case("空槽（0）不入选 ⇒ k=2，rand=0 ⇒ 第 0 个（= 51）", s["last"], NEIGHBOURS[1])
    s = f.run(0, blocked=(0,), rand=0)
    case("★ 槽 0 被封路（bit30）⇒ 从槽 1 开始 ⇒ 52", s["last"], NEIGHBOURS[1])
    s = f.run(0, blocked=(0, 1, 3), rand=0)
    case("★ 只剩槽 2 ⇒ k=1 ⇒ 53", s["last"], NEIGHBOURS[2])
    s = f.run(0, last_node=NEIGHBOURS[0], rand=0)
    case("★ 邻接里等于旧来路的那个不入选 ⇒ 取第 1 个（52）", s["last"], NEIGHBOURS[1])
    s = f.run(0, last_node=NEIGHBOURS[0], adj=[NEIGHBOURS[0], 0, 0, 0], rand=0)
    case("★ 一个候选都没有 ⇒ last_node 写 **0**", s["last"], 0)
    s = f.run(0, adj=[0, 0, 0, 0], rand=3)
    case("   四个槽全空 ⇒ 也是 0", s["last"], 0)

    print("\n[4] 替身分支（目标 4..7）：同构，只是换了一张表")
    s = f.run(4, actor_facing=1, actor_last=0, rand=2)
    case("替身 4：朝向 1 → 5", s["facing"], 5)
    case("★ 来路同样摇一个（rand=2 ⇒ 第 2 个 = 53）", s["last"], NEIGHBOURS[2])
    s = f.run(7, actor_facing=6, actor_last=NEIGHBOURS[3], rand=0)
    case("替身 7：朝向 6 → 2", s["facing"], 2)
    case("   邻居里排除旧来路 ⇒ 取第 0 个", s["last"], NEIGHBOURS[0])
    s = f.run(5, actor_last=NEIGHBOURS[0], adj=[NEIGHBOURS[0], 0, 0, 0], rand=0)
    case("   候选为空 ⇒ 替身的来路写 0", s["last"], 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
