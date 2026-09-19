#!/usr/bin/env python3
"""
通道 2 差分测试 #18 · 物件**投放** `0x0040e033` ＋ 「回到棋盘」`0x0040d6be`

两支都是「把东西放到地图上」这条线上的原语；都是**纯规则**（不碰 MKF、不碰画面），
所以可以在 Unicorn 里整支调用。

## 一、`place_object 0x0040e033(type, nodeId, state, attached)`

```asm
0040e036  edi = arg1 = type
0040e03a  esi = arg2 = nodeId
0040e03e  eax = type - 0xf ; if (eax <= 3) jmp [eax*4 + 0x40e023]   ; ★ 四路跳表
             type 15 → ebx=0x0e ecx=0x10      ; 槽 14..15
             type 16 → ebx=0x10 ecx=0x1a      ; 槽 16..25
             type 17 → ebx=0x1a ecx=0x24      ; 槽 26..35
             type 18 → ebx=0x24 ecx=0x2e      ; 槽 36..45
          否则（1..14）→ ebx = type-1, ecx = type   ; ★ **只有自己那一格**
0040e082  for (i = ebx; i < ecx; i++)
             if (objects[i].nodeId != 0) 换下一格
             objects[i].nodeId  = nodeId
             objects[i].state   = arg3
             objects[i].attached= arg4
             if (arg4 != 0 && type == 0xf) call 0x40ead7(arg4-1, 0, i+1)   ; ★ 神明附身
             if (nodeId == 0) 收场
             找 node[nodeId].adjacent[0..3] 第一个非 0 → call 0x407a8c(邻格, 本格)
             objects[i].+0x01 = 朝向
             or dword [node + 0x24], (i+1) << 16        ; ★ 登记「这格有物件」
0040e13f  return i + 1                                          ; ★ 返回值 = handle
```

★ 要点：**种类 == 槽号 + 1**（下标↔种类的不变量），函数**不写 `+0x00` 的种类字节**；
`type 1..14` 每种只有一个专属槽，所以那一格被占时它会**空手返回 `type+1`**
（没有任何错误信号）。

## 二、`return_to_board 0x0040d6be(idx)`（住宿/坐牢/住院释放的**共用尾段**）

```asm
0040d6c7  esi = 0x100 << idx                     ; ★ 节点占用位（bits 8..11）
0040d6ce  ebx = idx * 0x68
0040d6d1  or byte [player + 0x15], 0x10          ; ★ 「走回棋盘」标记
0040d6ee  ecx = node.x - player.x ; edi = node.y - player.y
0040d70f  call 0x454fb4(dx, dy) → al             ; 朝向（atan2 + 表 0x482414）
0040d717  [player + 0x10] = al
0040d737  or dword [node + 0x24], esi            ; 登记占用
```

★★ **它不清 `+0x32..+0x35`**！真正的清账在**走路例程 `0x40c05c`** 里
（`0x40c3ab`..`0x40c3cf`）：看到 `+0x15 & 0x30` 且 `[0x48baf4] > 0` 时
`mov dword [player+0x32], 0` —— **一次清四个**。
本测试把「释放函数只立标记、不清计数」这条钉住（复刻把它折叠进 tick，见 PRD）。

跑法：cd rich4-spec && .venv/bin/python tests/test_object_place.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu  # noqa: E402

PLACE_OBJECT = 0x40E033
RETURN_TO_BOARD = 0x40D6BE

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y, P_NODE, P_LAST, P_FACING, P_WHO = 0x08, 0x0A, 0x0C, 0x0E, 0x10, 0x15
P_BLOCK_LO = 0x32                     # +0x32..+0x35 四个阻碍计数（dword 一次读写）

OBJ_BASE, OBJ_STRIDE, OBJ_COUNT = 0x496D08, 24, 46
OBJ_TYPE, OBJ_FACING, OBJ_NODE, OBJ_STATE, OBJ_ATTACHED = 0x00, 0x01, 0x02, 0x04, 0x05

NODE_TABLE_PTR, NODE_COUNT = 0x498E80, 0x498E9C
NODE_SCRATCH, NODE_STRIDE = 0x600000, 0x28
NODE_X, NODE_Y, NODE_ADJ, NODE_OCC = 0x00, 0x02, 0x18, 0x24

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    got_s = got if isinstance(got, (int, float)) else str(got)
    want_s = want if isinstance(want, (int, float)) else str(want)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got_s!s:<14} 期望 {want_s!s}")
    return ok


def node_addr(n):
    return NODE_SCRATCH + n * NODE_STRIDE


class F:
    def __init__(self):
        self.emu = Emu()

    # ---------- 共用环境 ----------
    def _env(self, emu, nodes):
        """nodes: {id: (x, y, [adj...])}"""
        emu.write32(NODE_TABLE_PTR, NODE_SCRATCH)
        emu.write32(NODE_COUNT, len(nodes) + 1)
        for nid, (x, y, adj) in nodes.items():
            a = node_addr(nid)
            emu.write16(a + NODE_X, x)
            emu.write16(a + NODE_Y, y)
            for k, v in enumerate(adj[:4]):
                emu.write16(a + NODE_ADJ + 2 * k, v)

    # ---------- place_object ----------
    def place(self, type_, node_id, state=0, attached=0, nodes=None, objs=None):
        nodes = nodes or {1: (100, 100, [2]), 2: (200, 100, [1]), 5: (300, 300, [1])}
        objs = objs or {}

        def setup(emu):
            self._env(emu, nodes)
            for i in range(OBJ_COUNT):
                base = OBJ_BASE + i * OBJ_STRIDE
                t, nd, st, at = objs.get(i, (0, 0, 0, 0))
                emu.write8(base + OBJ_TYPE, t)
                emu.write8(base + OBJ_FACING, 0)
                emu.write16(base + OBJ_NODE, nd)
                emu.write8(base + OBJ_STATE, st)
                emu.write8(base + OBJ_ATTACHED, at)
            for nid in nodes:
                emu.write32(node_addr(nid) + NODE_OCC, 0)

        out = self.emu.call(PLACE_OBJECT, [type_, node_id, state, attached], setup=setup)
        e = self.emu
        return {
            "ret": out["eax"],
            "obj": lambda i: (e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_TYPE),
                              e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_FACING),
                              e.read16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE),
                              e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_STATE),
                              e.read8(OBJ_BASE + i * OBJ_STRIDE + OBJ_ATTACHED)),
            "occ": lambda n: e.read32(node_addr(n) + NODE_OCC),
        }

    # ---------- return_to_board ----------
    def return_(self, idx, x=100, y=100, node_id=5, who=1, nodes=None, facing=0,
                block=0):
        nodes = nodes or {5: (300, 400, [1])}

        def setup(emu):
            self._env(emu, nodes)
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write16(base + P_X, x)
            emu.write16(base + P_Y, y)
            emu.write16(base + P_NODE, node_id)
            emu.write16(base + P_LAST, 0)
            emu.write8(base + P_FACING, facing)
            emu.write8(base + P_WHO, who)
            emu.write32(base + P_BLOCK_LO, block & 0xFFFFFFFF)
            emu.write32(node_addr(node_id) + NODE_OCC, 0)

        self.emu.call(RETURN_TO_BOARD, [idx], setup=setup)
        e = self.emu
        base = PLAYER_BASE + idx * PLAYER_STRIDE
        return {
            "who": e.read8(base + P_WHO),
            "facing": e.read8(base + P_FACING),
            "block": e.read32(base + P_BLOCK_LO),
            "occ": e.read32(node_addr(node_id) + NODE_OCC),
        }


def main():
    print("差分测试 #18：物件投放 0x0040e033 ＋ 回到棋盘 0x0040d6be\n")
    f = F()

    print("[1] place_object：种类 ↔ 槽号 的分区")
    # 每个槽先按不变量写好种类（函数自己不写 +0x00）
    def typed(slots):
        return {i: (t, 0, 0, 0) for i, t in slots.items()}

    r = f.place(16, 5, state=1, objs=typed({16: 16, 17: 16, 18: 16}))
    case("type 16（路障）落在槽 16 ⇒ 返回 handle 17", r["ret"], 17)
    case("   槽 16 写入 (type, facing, nodeId=5, state=1, attached=0)",
         (r["obj"](16)[0], r["obj"](16)[2], r["obj"](16)[3], r["obj"](16)[4]),
         (16, 5, 1, 0))
    case("   ★ 节点占用 |= (16+1)<<16 = 0x110000", r["occ"](5), 0x110000)
    case("   facing 被算出来（非 0 字节写在 +0x01）", r["obj"](16)[1] != 0xFF, True)

    r = f.place(17, 5, objs=typed({26: 17}))
    case("type 17（地雷）落在槽 26 ⇒ handle 27", (r["ret"], r["obj"](26)[2]), (27, 5))
    r = f.place(18, 5, objs=typed({36: 18}))
    case("type 18（炸彈）落在槽 36 ⇒ handle 37", (r["ret"], r["obj"](36)[2]), (37, 5))
    r = f.place(1, 5, objs=typed({0: 1}))
    case("type 1（神明）只有专属槽 0 ⇒ handle 1", (r["ret"], r["obj"](0)[2]), (1, 5))

    print("\n[2] place_object：槽被占则顺延（同一分区内）")
    r = f.place(16, 5, objs={16: (16, 5, 0, 0), 17: (16, 0, 0, 0)})
    case("槽 16 已占 ⇒ 用槽 17 ⇒ handle 18", (r["ret"], r["obj"](17)[2]), (18, 5))
    case("   槽 16 不动（仍是旧 nodeId 5）", r["obj"](16)[2], 5)

    print("\n[3] place_object：nodeId == 0 ⇒ 不置占用、不算朝向")
    r = f.place(16, 0, objs=typed({16: 16}))
    case("返回 handle 17、槽 16 的 nodeId 仍是 0",
         (r["ret"], r["obj"](16)[2]), (17, 0))

    print("\n[4] ★ place_object：types 1..14 只有一个专属槽，被占就空手返回")
    r = f.place(1, 7, objs={0: (1, 5, 0, 0)})
    case("槽 0 已占（nodeId=5）⇒ 不写任何东西（仍是 5）", r["obj"](0)[2], 5)
    case("★ 返回值是 `type+1` = 2（**没有错误信号**）", r["ret"], 2)

    print("\n[5] ★ return_to_board：只立「走回棋盘」标记，**不动四个阻碍计数**")
    r = f.return_(2, x=100, y=100, node_id=5)
    case("player.+0x15 |= 0x10", r["who"], 1 | 0x10)
    case("★ +0x32..+0x35 仍是 0（清账在走路例程里）", r["block"], 0)
    case("★ 节点占用 |= 0x100<<2 = 0x400", r["occ"], 0x400)
    case("朝向被写过（+0x10）", r["facing"] != 0xFF, True)

    r = f.return_(0, node_id=1, nodes={1: (300, 400, [2])})
    case("下标 0 ⇒ 占用位 0x100", r["occ"], 0x100)

    print("\n[6] ★★ return_to_board：计数**非 0** 时也照样不清 —— 清账不在这里")
    # 构造 inHotel=0x80（刑满待释放）+ inPrison=3 → dword = 0x00038080
    r = f.return_(1, node_id=5, block=0x00038080)
    case("★ +0x32..+0x35 原样不动（0x00038080）", r["block"], 0x00038080)
    case("   但标记与占用照常写入",
         (r["who"] & 0x10, r["occ"]), (0x10, 0x200))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
