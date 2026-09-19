#!/usr/bin/env python3
"""
通道 2 差分测试 #22 · 首次关押的「传送 + 跟班搬家」全段

- `0x0043d593(player_or_slot, days)` —— `send_to_prison`
- `0x0043ec3f(player_or_slot, days)` —— `send_to_hospital`（同构，晚 0xF30）

规格来源：`docs/systems/game-loop.md`、`docs/systems/save-scalars.md` §2.17(b)、
`rich4-remake/docs/gaps/README.md` §7.3 第 15 项。

## 为什么需要这个测试

原版把「传送到监狱／医院格」与「跟班物件跟着搬」**写在 `send_to_*` 函数体内**，
所以**每一个**调用点都自动获得这套行为。先前 remake 把这两件事留给调用点自己做，
6 个调用点里只有 2 个接了 —— 另外 4 条（命運、新聞、炸彈落地、陷害/復仇卡）的
受害者只是计数进了监狱，`nodeId/xpos/ypos` 还停在原地。本测试把整段钉住。

## 逐条对照的机器码（首次分支）

```asm
0043d5a0  edi = ~(0x100 << idx)                     ; 节点占用位的清除掩码
0043d5a8  cmp edx, 4 / jge 0x43d760                 ; ★ 槽 4..7 = 地图物件，另一支
0043d5cc  call 0x41d476(x, y, 0)                    ; 旧位置重绘（表现，打桩）
0043d5d4  dh = [player + 0x34]                      ; 已在狱中？
0043d5dc  jne 0x43d6bd                              ; → 加刑：只累加，**不传送**
0043d5e7  call 0x40d761(idx)                        ; 清 +0x32..+0x35 四项 + "另一张"占用表
0043d5f9  call 0x44f2c2(idx, days)                  ; 换立绘（表现，打桩）
0043d601  and  byte [player + 0x15], 0xf            ; 清 who_plays 高 4 位
0043d60a  esi = node[old].nodeId * 5 ; *8 → 步长 0x28
0043d61d  and  dword [node[old] + 0x24], edi        ; ★ 清旧格的 0x100<<idx 占用位
0043d621  ax = word [0x48bae0]                      ; 监狱格号（医院是 [0x48bae2]）
0043d627  word [player + 0x0c] = ax                 ; nodeId ← 监狱格
0043d630  word [player + 0x0e] = 0                  ; lastNodeId ← 0
0043d637  byte [player + 0x1b] = 0xf                ; 朝向后备哨兵
0043d63e  eax = [0x498e78]                          ; 景观记录表
0043d643  word [player + 0x08] = [eax + 0x38]       ; ★ x ← 记录 2 的 x（监狱）
0043d64e  word [player + 0x0a] = [eax + 0x3a]       ;   y ← 记录 2 的 y
0043d65d  byte [player + 0x34] = days               ; 计数值（新判，不是累加）
0043d668  call 0x40fc00(player)                     ; ★ 跟班物件 nodeId ← 玩家所在格
0043d674  byte [idx + 0x496b30] = 1                 ; 占用表置位
; 尾段（首次与加刑**都**走）：
0043d6f1  call 0x41d476(...)                        ; 重绘（表现，打桩）
0043d71c  call 0x44ef41(idx, 2, 立绘)               ; 换动作（表现，打桩）
0043d749  call 0x44ba63(idx, days × 2000 × 物价指数) ; ★ 保险理赔
0043d755  add  byte [player + 0x42], days           ; ★ 本月倒楣天數 += 天数
```

## 打桩清单（全是表现层，C-ARC-2）

| VA | 原用途 | 桩 |
|---|---|---|
| `0x41d476` | 标记旧屏幕区域重绘 | `ret` |
| `0x44f2c2` | 换立绘/表情 | `ret` |
| `0x44ef41` | 设置动作帧 | `ret` |
| `0x44ba63` | 保险理赔 | 记录 `(idx, amount)` 后 `ret` |
| `0x40bf93` | 把玩家从病床/监狱画回棋盘（`0x40d761` 里逐项调用）| `ret` |

跑法：cd rich4-spec && .venv/bin/python tests/test_confinement_teleport.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

SEND_PRISON = 0x43D593
SEND_HOSPITAL = 0x43EC3F

PLAYER_BASE, PLAYER_STRIDE = 0x496B68, 0x68
P_X, P_Y = 0x08, 0x0A
P_NODE, P_LAST = 0x0C, 0x0E
P_FACING, P_WHO, P_BACKUP = 0x10, 0x15, 0x1B
P_HOTEL, P_VANISH, P_PRISON, P_HOSPITAL = 0x32, 0x33, 0x34, 0x35
P_INSURANCE, P_GOD, P_F64, P_MISFORTUNE = 0x3E, 0x3F, 0x40, 0x42

PRISON_OCC, HOSPITAL_OCC = 0x496B30, 0x496B60
NODE_TABLE_PTR, LANDSCAPE_PTR = 0x498E80, 0x498E78
PRISON_NODE_GLOBAL, HOSPITAL_NODE_GLOBAL = 0x48BAE0, 0x48BAE2
SKIP_PRESENTATION = 0x497159
OBJ_BASE, OBJ_STRIDE, OBJ_COUNT, OBJ_NODE = 0x496D08, 24, 46, 0x02
OBJECT_RECORDS = 0x498E2C          # 物件记录表（步长 16，+0 节点号，+6 关押位）

PRICE_INDEX = 0x4990E8

# 暂存区布局
NODES = SCRATCH_BASE + 0x1000      # 节点表（步长 0x28）
LANDSCAPE = SCRATCH_BASE + 0x4000  # 景观记录（步长 0x1C）
STUB_OUT = SCRATCH_BASE + 0x100    # 理赔桩写出的 (idx, amount)

OLD_NODE = 60
NEW_PRISON_NODE = 61
NEW_HOSPITAL_NODE = 62
PRISON_X, PRISON_Y = 1935, 1039
HOSPITAL_X, HOSPITAL_Y = 777, 888

RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<62} 实际 {got!s:<14} 期望 {want!s}")
    return ok


class F:
    def __init__(self):
        self.emu = Emu()
        # 表现层打桩（persist ⇒ 跨 reset 保持）
        for va in (0x41D476, 0x44F2C2, 0x44EF41, 0x40BF93):
            self.emu.patch(va, b"\xC3")
        # 理赔桩：把 arg1/arg2 抄进暂存区再返回
        #   mov eax,[esp+8] / mov [0x600104],eax / mov eax,[esp+4] / mov [0x600100],eax / ret
        stub = (
            b"\x8B\x44\x24\x08"
            + b"\xA3" + struct.pack("<I", STUB_OUT + 4)
            + b"\x8B\x44\x24\x04"
            + b"\xA3" + struct.pack("<I", STUB_OUT)
            + b"\xC3"
        )
        self.emu.patch(0x44BA63, stub)

    # ---------- 场景注入 ----------
    def _setup_factory(self, idx, days, *, pre=None, gods=(0, 0), occ=None, ins=0):
        pre = pre or {}

        def setup(emu):
            # 关掉尾段的「画面切换」演示块（`0x497159 != 0` 才走那一块）
            emu.write8(SKIP_PRESENTATION, 0)
            emu.write(PRICE_INDEX, struct.pack("<I", pre.get("price", 1)))
            emu.write16(PRISON_NODE_GLOBAL, NEW_PRISON_NODE)
            emu.write16(HOSPITAL_NODE_GLOBAL, NEW_HOSPITAL_NODE)

            # 节点表：给出旧格与新格的记录，旧格的占用掩码填满 1
            # ★ 索引方式 = **nodeId 直接当索引**（`0x43d613 shl esi,2 / add esi,eax`
            #   → 步长 0x28，没有减 1）——原版运行时表带 0 号哨兵项。
            emu.write32(NODE_TABLE_PTR, NODES)
            for nid in (OLD_NODE, NEW_PRISON_NODE, NEW_HOSPITAL_NODE):
                base = NODES + nid * 0x28
                emu.write16(base + 0x00, 4000 + nid)
                emu.write16(base + 0x02, 5000 + nid)
                emu.write(base + 0x24, b"\xff\xff\xff\xff")

            # 景观记录表：监狱 = 记录 2（+0x38/+0x3a）、医院 = 记录 1（+0x1c/+0x1e）
            emu.write32(LANDSCAPE_PTR, LANDSCAPE)
            emu.write16(LANDSCAPE + 0x38, PRISON_X)
            emu.write16(LANDSCAPE + 0x3A, PRISON_Y)
            emu.write16(LANDSCAPE + 0x1C, HOSPITAL_X)
            emu.write16(LANDSCAPE + 0x1E, HOSPITAL_Y)

            # 玩家
            base = PLAYER_BASE + idx * PLAYER_STRIDE
            emu.write16(base + P_X, 111)
            emu.write16(base + P_Y, 222)
            emu.write16(base + P_NODE, OLD_NODE)
            emu.write16(base + P_LAST, 59)
            emu.write8(base + P_FACING, 3)
            emu.write8(base + P_WHO, pre.get("who", 0x41))
            emu.write8(base + P_BACKUP, 0)
            emu.write8(base + P_HOTEL, pre.get("hotel", 0))
            emu.write8(base + P_VANISH, pre.get("vanish", 0))
            emu.write8(base + P_PRISON, pre.get("prison", 0))
            emu.write8(base + P_HOSPITAL, pre.get("hospital", 0))
            emu.write8(base + P_INSURANCE, ins)
            emu.write8(base + P_GOD, gods[0])
            emu.write8(base + P_F64, gods[1])
            emu.write8(base + P_MISFORTUNE, pre.get("misfortune", 0))

            # 占用表 / 物件表
            for i in range(8):
                emu.write8(PRISON_OCC + i, (occ or {}).get(("prison", i), 0))
                emu.write8(HOSPITAL_OCC + i, (occ or {}).get(("hospital", i), 0))
            for i in range(OBJ_COUNT):
                emu.write16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE, 0)
            emu.write32(STUB_OUT, 0)
            emu.write32(STUB_OUT + 4, 0)

        return setup

    def run(self, va, idx, days, **kw):
        self.emu.call(va, [idx, days], setup=self._setup_factory(idx, days, **kw))
        return Snapshot(self.emu, idx)

    def run_object(self, idx, days, rec_node=OLD_NODE):
        def setup(emu):
            emu.write8(SKIP_PRESENTATION, 0)
            emu.write32(NODE_TABLE_PTR, NODES)
            base = NODES + OLD_NODE * 0x28
            emu.write16(base + 0x00, 4000 + OLD_NODE)
            emu.write16(base + 0x02, 5000 + OLD_NODE)
            emu.write(base + 0x24, b"\xff\xff\xff\xff")
            for i in range(8):
                emu.write8(PRISON_OCC + i, 0)
                emu.write8(HOSPITAL_OCC + i, 0)
            for i in range(4):
                emu.write16(OBJECT_RECORDS + i * 16, rec_node)
                emu.write8(OBJECT_RECORDS + i * 16 + 6, 0x5A)
                for k in range(7, 12):
                    emu.write8(OBJECT_RECORDS + i * 16 + k, 0x5A)

        self.emu.call(SEND_PRISON, [idx, days], setup=setup)
        e = self.emu
        return {
            "occ": [e.read8(PRISON_OCC + i) for i in range(8)],
            "rec6": e.read8(OBJECT_RECORDS + (idx - 4) * 16 + 6),
            "rec7_11": [e.read8(OBJECT_RECORDS + (idx - 4) * 16 + k) for k in range(7, 12)],
            "node_mask": e.readu32(NODES + rec_node * 0x28 + 0x24),
        }


class Snapshot:
    """回读 `0x43d593` 跑完之后关心的全部字段。"""

    def __init__(self, e, idx):
        self.e = e
        self.idx = idx
        base = PLAYER_BASE + idx * PLAYER_STRIDE
        self.x = e.read16(base + P_X)
        self.y = e.read16(base + P_Y)
        self.node = e.read16(base + P_NODE)
        self.last = e.read16(base + P_LAST)
        self.facing = e.read8(base + P_FACING)
        self.who = e.read8(base + P_WHO)
        self.backup = e.read8(base + P_BACKUP)
        self.hotel = e.read8(base + P_HOTEL)
        self.vanish = e.read8(base + P_VANISH)
        self.prison = e.read8(base + P_PRISON)
        self.hospital = e.read8(base + P_HOSPITAL)
        self.misfortune = e.read8(base + P_MISFORTUNE)
        self.prison_occ = [e.read8(PRISON_OCC + i) for i in range(8)]
        self.hospital_occ = [e.read8(HOSPITAL_OCC + i) for i in range(8)]
        self.objs = [e.read16(OBJ_BASE + i * OBJ_STRIDE + OBJ_NODE) for i in range(OBJ_COUNT)]
        self.old_mask = e.readu32(NODES + OLD_NODE * 0x28 + 0x24)
        self.new_mask = e.readu32(NODES + NEW_PRISON_NODE * 0x28 + 0x24)
        self.claim_idx = e.readu32(STUB_OUT)
        self.claim_amount = e.readu32(STUB_OUT + 4)


def main():
    print("差分测试 #22：首次关押的传送 + 跟班搬家 —— 0x43d593 / 0x43ec3f\n")
    f = F()

    print("[1] 首次入监：传送到监狱格 + 三项位置原子更新")
    s = f.run(SEND_PRISON, 1, 5)
    case("nodeId ← [0x48bae0]（监狱格号）", s.node, NEW_PRISON_NODE)
    case("lastNodeId ← 0", s.last, 0)
    case("x/y ← 景观记录 2 的 +0x38/+0x3a", (s.x, s.y), (PRISON_X, PRISON_Y))
    case("+0x34 inPrison ← 5（新判=赋值，不是累加）", s.prison, 5)
    case("占用表 [idx] ← 1", s.prison_occ[1], 1)
    case("★ 朝向后备 +0x1b ← 0xf（哨兵：释放时不恢复朝向）", s.backup, 0x0F)
    case("★ whoPlays 高 4 位被清（0x41 → 0x01）", s.who, 0x01)
    case("★ 本月倒楣天數 +0x42 += 天数", s.misfortune, 5)
    case("朝向 +0x10 不被本函数改", s.facing, 3)

    print("\n[2] 旧格的 0x100<<idx 占用位被清、其余位保留")
    # 占用位 = bit(8+idx)：槽 0..3 玩家、槽 4..7 物件，共 8 位
    case("idx=1 ⇒ 掩码 0xfffffdff（清 bit9）", s.old_mask, 0xFFFFFDFF)
    case("★ 新格**不**置位（置位是释放函数 0x40d6be 的事）", s.new_mask, 0xFFFFFFFF)
    s2 = f.run(SEND_PRISON, 3, 5)
    case("idx=3 ⇒ 清 bit11 → 0xfffff7ff", s2.old_mask, 0xFFFFF7FF)

    print("\n[3] 首次关押顺手清掉另外三项阻碍 + 「另一张」占用表")
    s = f.run(SEND_PRISON, 1, 5, pre={"hotel": 2, "vanish": 3, "hospital": 4},
              occ={("hospital", 1): 1, ("hospital", 2): 1})
    case("+0x32 inHotel 清 0", s.hotel, 0)
    case("+0x33 disappearing 清 0", s.vanish, 0)
    case("+0x35 inHospital 清 0（住院中被判刑）", s.hospital, 0)
    case("★ 医院占用表 [1] 被清（同一 idx）", s.hospital_occ[1], 0)
    case("医院占用表 [2] 不动（别人）", s.hospital_occ[2], 1)

    print("\n[4] 加刑分支：只累加，**不传送**、不动跟班、不清旧格")
    s = f.run(SEND_PRISON, 2, 5, pre={"prison": 2}, gods=(3, 5))
    case("计数 = 2 + 5 = 7", s.prison, 7)
    case("★ nodeId 保持不变（0x43d6bd 不传送）", s.node, OLD_NODE)
    case("★ x/y 保持不变", (s.x, s.y), (111, 222))
    case("★ lastNodeId 保持不变", s.last, 59)
    case("★ 旧格占用位保持原样", s.old_mask, 0xFFFFFFFF)
    case("★ whoPlays 不被清（0x41）", s.who, 0x41)
    case("★ 跟班物件不搬（两个都还是 0）", (s.objs[2], s.objs[4]), (0, 0))
    case("★ 但倒楣天數照样 += 天数", s.misfortune, 5)
    s = f.run(SEND_PRISON, 1, 5, pre={"prison": 0x7C})
    case("加刑进位被 &0x7f 截掉（0x7c+5=0x81 → 1）", s.prison, 0x01)

    print("\n[5] 跟班搬家：0x40fc00 把 +0x3f / +0x40 两个物件的所在格改成玩家所在格")
    s = f.run(SEND_PRISON, 1, 5, gods=(3, 5))
    case("godInfo=3 ⇒ objects[2].nodeId = 监狱格", s.objs[2], NEW_PRISON_NODE)
    case("f64=5     ⇒ objects[4].nodeId = 监狱格", s.objs[4], NEW_PRISON_NODE)
    case("别的物件槽不动", (s.objs[0], s.objs[1], s.objs[3]), (0, 0, 0))
    s = f.run(SEND_PRISON, 1, 5, gods=(3, 0))
    case("★ +0x40 == 0 只跳过第二支", (s.objs[2], s.objs[4]), (NEW_PRISON_NODE, 0))

    print("\n[6] 保险理赔：`0x44ba63(idx, 天数 × 2000 × 物价指数)`")
    s = f.run(SEND_PRISON, 1, 5, ins=30)
    case("idx 参数 = 玩家下标", s.claim_idx, 1)
    case("金额 = 5 × 2000 × 物价指数(1) = 10000", s.claim_amount, 5 * 2000)
    s = f.run(SEND_PRISON, 3, 2, ins=30, pre={"price": 3})  # 物价指数是 dword
    case("金额 = 2 × 2000 × 3 = 12000", s.claim_amount, 12000)
    s = f.run(SEND_PRISON, 1, 4, ins=30, pre={"prison": 1})
    case("★ 加刑分支也理赔（尾段共用）", s.claim_amount, 4 * 2000)

    print("\n[7] 入院：完全同构，只换格号/景观记录/字段")
    s = f.run(SEND_HOSPITAL, 2, 3)
    case("nodeId ← [0x48bae2]（医院格号）", s.node, NEW_HOSPITAL_NODE)
    case("x/y ← 景观记录 1 的 +0x1c/+0x1e", (s.x, s.y), (HOSPITAL_X, HOSPITAL_Y))
    case("+0x35 inHospital ← 3", s.hospital, 3)
    case("医院占用表 [2] ← 1", s.hospital_occ[2], 1)
    case("★ 监狱占用表不动", s.prison_occ[2], 0)
    case("★ lastNodeId ← 0 / 后备 0xf / whoPlays 清高位",
         (s.last, s.backup, s.who), (0, 0x0F, 0x01))
    case("★ 旧格占用位清（idx=2 ⇒ 0xfffffbff）", s.old_mask, 0xFFFFFBFF)
    s = f.run(SEND_HOSPITAL, 2, 3, gods=(1, 2))
    case("跟班也搬进医院格", (s.objs[0], s.objs[1]), (NEW_HOSPITAL_NODE, NEW_HOSPITAL_NODE))

    print("\n[8] 槽位 4..7（地图物件分支 0x43d760）—— 与玩家分支完全不同")
    o = f.run_object(5, 5)
    case("占用表槽 5（= 4 + (5−4)）置 1", o["occ"][5], 1)
    case("★ 其它槽不动", [v for i, v in enumerate(o["occ"]) if i != 5], [0] * 7)
    case("物件记录 +6 ← 1", o["rec6"], 1)
    case("物件记录 +7..+11 清 0", o["rec7_11"], [0] * 5)
    # 槽 5 ⇒ 掩码 = ~(0x100 << 5) = 0xffffdfff（占用位 bit8..15 对应槽 0..7）
    case("★ 清的是**物件自己所在格**的占用位（0xffffdfff）", o["node_mask"], 0xFFFFDFFF)
    o = f.run_object(8, 5)
    case("★ 槽 8 越界 ⇒ 直接返回（占用表全 0）", o["occ"], [0] * 8)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 66}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
