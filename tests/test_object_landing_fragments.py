#!/usr/bin/env python3
"""
通道 2 差分测试 #37 · **四个「踩上去」物件落点**（分派器片段）

四个处理函数是**大落点分派器** `0x41b42d`（帧 `sub esp,0xa8`）的跳表成员。
分派器把当前格的编码字 `[node+0x24]` 拆成四个**帧内局部量**，再按对象类型跳表：

```asm
; @source 0x41b491（esi = 当前格编号，[0x498e80] = 地图格数组，步长 0x28）
0041b491  mov  ecx, [eax + 0x24] / and ecx, 0xff       ; → [esp+0xa0] = 格子种类
0041b4a1  mov  ecx, [eax + 0x24] / and ecx, 0xf00 / shr 8
                                                       ; → [esp+0x98] = 第 2 字节（玩家位掩码）
0041b4b4  mov  eax, [eax + 0x24] / and eax, 0xff0000 / shr 0x10
0041b4bf  mov  [esp + 0xa4], eax                       ; ★ 对象槽号（1 基，0 = 无）
0041b4ca  lea  ebx, [eax - 1] / … / mov al, [eax*8 + 0x496d08]
0041b4e0  mov  [esp + 0x9c], eax                       ; ★ 对象类别 = objects_info[槽].+0
0041b7ef  mov  eax, [esp + 0x9c] / dec eax / cmp eax, 0x11 / ja 0x41c164
0041b800  jmp  dword ptr [eax*4 + 0x41b3e5]            ; ★ 类别分派表（18 项，类别 1..18）
```

| 类别 | 入口 | 规则核心 |
|---|---|---|
| 14 (`0x0e`) 寶箱 | `0x41bb0c` | `remove_object(**0xe**)` + **點券 +500**（16 位加）|
| 16 (`0x10`) 路障 | `0x41bceb` | `remove_object(槽号)` + `[0x48baf8]=0` + 一句台词 |
| 17 (`0x11`) 地雷 | `0x41be5f` | `remove_object(槽号)` + **毁座驾** + **住院 3 天** |
| 18 (`0x12`) 定時炸彈 | `0x41bfd2` | **挂到踩到者身上**（`player[+0x40] = 槽号`）+ 物件记录改写 + 一句台词 |

## ★★ 为什么寶箱写死 `0xe` 是对的（本轮新结论）

对象**槽号 → 类别**是**固定表** `0x47ed3c`（46 字节，装载时逐字节写进
`objects_info[i].+0`，`@source 0x407d4e..0x407d68` 的循环上限 `0x2e`）：

```
槽 1..14  → 类别 1..14       （每类恰好 1 槽 ⇒ 处理函数可以写死自己的槽号）
槽 15..16 → 类别 15          （`0x41c164` = 直接进收尾，不处理）(2 个)
槽 17..26 → 类别 16 路障      (10 个)
槽 27..36 → 类别 17 地雷      (10 个)
槽 37..46 → 类别 18 定時炸彈   (10 个)
```

所以「类别 14 的寶箱 ⇒ 一定在槽 14」是**表推出来的不变量**，`0x41bb31 push 0xe`
不是笔误；同族还有类别 11 的处理函数 `0x41b837 push 0xb`（类别 11 也在专属槽）。
路障/地雷/炸彈因为有多槽，必须用帧里的真实槽号 `[esp+0xa4]`。

## ★★ 驱动手法：`eval_block` + **手搓帧**（比第 36 条的「尾声打 ret」更稳）

片段由 `jmp [跳表]` 进入 ⇒ **栈上没有返回地址**，`[esp]` 是分派器的帧内局部量
（`0x41bc26 lea eax,[esp+0xc]` 算出来的 sprintf 目标正好等于 `[esp]`）。
所以用 `emu.call`（会在 `[esp]` 放假返回地址）驱动**替身分支**时，sprintf 会
把返回地址覆盖成台词文本，最后 `ret` 跳到垃圾地址。

本测试改用 `emu.eval_block(入口, 0x41c844, …)`：

* `0x41c844` = 分派器真正的尾声（`add esp,0xa8; pop×4; ret`），
  `emu_start` 在 **EIP 命中它时停住**，不执行 `ret` ⇒ 覆盖 `[esp]` 无害；
* `eval_block` 把 ESP 钉在 `STACK_TOP`，于是帧内量就是
  `[STACK_TOP+0x98/+0x9c/+0xa0/+0xa4]`，在 `setup` 里直接写这四个字；
* `esi` 是**当前格编号**（分派器 `0x41b461` 从 `player+0x74` / NPC 槽 `+4` 取），
  炸彈片段会拿它去写 `[0x498e80] + esi*0x28 + 0x26`，故 `eval_block` 里显式给 `esi`。

## 打桩清单

| VA | 原用途 | 桩 |
|---|---|---|
| `0x40e14d` | `remove_object(槽号)` | 记实参 + 计数 + `ret` |
| `0x40cd07` | 毁座驾（玩家）| 记实参 + `ret` |
| `0x43ec3f` | 送医院（玩家/替身, 天数）| 记两个实参 + `ret` |
| `0x41d476` | 落点事务 | 计数 + `ret` |
| `0x440cac` | 显示文字 | 记实参 + 计数 + `ret` |
| `0x44ef41` | `player_say` | 记三个实参 + `ret` |
| `0x445a4d` | `receive_tool(玩家, 道具号)` | 记两个实参 + `ret` |
| `0x41d546` | `refresh_map()` | 计数 + `ret`（内部走 DirectDraw 表面 vtable，无法仿真）|
| `0x450441`/`0x45144f`/`0x456e11` | MKF 装载/贴图/卸载 | `xor eax,eax`+计数 / 计数 / 计数 |
| `0x4542ce`/`0x4542e9` | 音效 | 计数 + `ret` |
| `0x452946` | 去空格拷贝（名字）| 计数 + `ret`（原版只拿它当摆设，结果未被使用）|
| `0x457110` | `sprintf(目标, 格式, 参数)` | 计数 + `ret`（→ CRT `0x458db5`，会走进未映射的 CRT 数据）|

**未决**：`objects_info.+4`（炸彈写 `0x26`）与 `.+5`（携带者 = 玩家号+1）在后文
`0x40e14d` 里被当作「携带者」；`+4` 的语义（`place_object` 写 7 / 类别 15 写 0xd）
尚未读通，本测试只钉**写入值**（另见 `tools.md` §6.3.3：它就是 38 格的引信）。

## [F] 再进一步：从**分派器入口** `0x41b42d` 驱动

`run()` 手搓帧内量、直接进处理器；`run_via_dispatch()` 只写**地图格编码字**
（`[node+0x24]`：低 8 位格子种类 / 8..11 玩家占位 / 16..23 槽号）与玩家/NPC 的当前格号，
让分派器自己 `0x41b461 → 0x41b47f → 0x41b491..0x41b4e0` 拆帧、按 `[esp+0x9c]` 查跳表。
这一组钉住**编码字 → 帧内量 → 处理器**这条链，并覆盖 `0x41b4e7`
（actor 8 在跳表**之前**被截住：照飞照拆，但寶箱的 +500 **不发生**）。
★ 分派器里还有一段「踩到乞丐」的处理（`0x41b5fd` 起，`施捨給乞丐%d元`）——
那一条已在 `rich4-remake` 的 `rules/beggar.ts` 实现并有测试，本文件不重复驱动。

跑法：cd rich4-spec && .venv/bin/python tests/test_object_landing_fragments.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, STACK_TOP, Emu  # noqa: E402

TREASURE, ROADBLOCK, MINE, BOMB = 0x41BB0C, 0x41BCEB, 0x41BE5F, 0x41BFD2
DISPATCH = 0x41B42D               # ★ 分派器**函数入口**（push×4 + sub esp,0xa8）
DISPATCH_EXIT = 0x41C844          # 分派器真尾声（eval_block 的停址）

PLAYER_BASE, STRIDE = 0x496B68, 0x68
P_NAME, P_POINTS, P_CARRIED = 0x00, 0x30, 0x40
ACTOR_BASE, ACTOR_STRIDE = 0x498E28, 0x10
A_OWNER, A_STATUS, A_SLEEP = 0x08, 0x0A, 0x0D
OBJ_BASE, OBJ_STRIDE = 0x496D08, 0x18   # objects_info：+0 类别 / +2 格 / +4 ? / +5 携带者+1
CUR, BUSY, NODE_ARRAY = 0x49910C, 0x48BAF8, 0x498E80

REMOVE, WRECK, HOSPITAL, TXN, SHOW, SAY = (0x40E14D, 0x40CD07, 0x43EC3F,
                                           0x41D476, 0x440CAC, 0x44EF41)
RECEIVE, REFRESH = 0x445A4D, 0x41D546
LOAD, BLIT, FREE, SND1, SND2, STRIP = (0x450441, 0x45144F, 0x456E11,
                                       0x4542CE, 0x4542E9, 0x452946)
FMT = 0x457110                       # sprintf(目标, 格式, 参数) → CRT 0x458db5

S = SCRATCH_BASE
M_REMOVE, C_REMOVE = S + 0x800, S + 0x804
M_WRECK, C_WRECK = S + 0x808, S + 0x80C
M_HOSP1, M_HOSP2, C_HOSP = S + 0x810, S + 0x814, S + 0x818
C_TXN = S + 0x81C
C_SHOW, M_SHOW = S + 0x820, S + 0x824
M_SAY1, M_SAY2, M_SAY3, C_SAY = S + 0x828, S + 0x82C, S + 0x830, S + 0x834
M_RECV1, M_RECV2, C_RECV = S + 0x838, S + 0x83C, S + 0x840
C_REFRESH = S + 0x844
C_LOAD, C_BLIT, C_FREE, C_SND, C_STRIP = (S + 0x848, S + 0x84C, S + 0x850,
                                          S + 0x854, S + 0x858)
C_FMT = S + 0x85C
NODE_PTR, NAMES = S + 0x3000, S + 0x400

ALL_SLOTS = (M_REMOVE, C_REMOVE, M_WRECK, C_WRECK, M_HOSP1, M_HOSP2, C_HOSP,
             C_TXN, C_SHOW, M_SHOW, M_SAY1, M_SAY2, M_SAY3, C_SAY,
             M_RECV1, M_RECV2, C_RECV, C_REFRESH, C_LOAD, C_BLIT, C_FREE,
             C_SND, C_STRIP, C_FMT)
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<58} 实际 {got!s:<16} 期望 {want!s}")
    return ok


def _inc(slot):
    return b"\xFF\x05" + struct.pack("<I", slot)


class F:
    def __init__(self):
        self.emu = Emu()
        self.emu.patch(LOAD, b"\x31\xC0" + _inc(C_LOAD) + b"\xC3")
        for va, cnt in ((BLIT, C_BLIT), (FREE, C_FREE), (SND1, C_SND),
                        (SND2, C_SND), (STRIP, C_STRIP), (FMT, C_FMT),
                        (REFRESH, C_REFRESH)):
            self.emu.patch(va, _inc(cnt) + b"\xC3")
        self.emu.patch(TXN, _inc(C_TXN) + b"\xC3")
        self.emu.patch(REMOVE, self._rec1(M_REMOVE, C_REMOVE))
        self.emu.patch(WRECK, self._rec1(M_WRECK, C_WRECK))
        self.emu.patch(HOSPITAL, self._rec2(M_HOSP1, M_HOSP2, C_HOSP))
        self.emu.patch(SHOW, self._rec1(M_SHOW, C_SHOW))
        self.emu.patch(RECEIVE, self._rec2(M_RECV1, M_RECV2, C_RECV))
        # player_say(player, 槽, 文本) —— 记三个实参
        code = b"".join(b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", s)
                        for off, s in ((4, M_SAY1), (8, M_SAY2), (0xC, M_SAY3)))
        self.emu.patch(SAY, code + _inc(C_SAY) + b"\xC3")

    @staticmethod
    def _rec1(s1, cnt):
        # mov eax,[esp+4] / mov [s1],eax / inc [cnt] / ret
        return (b"\x8B\x44\x24\x04" + b"\xA3" + struct.pack("<I", s1)
                + _inc(cnt) + b"\xC3")

    @staticmethod
    def _rec2(s1, s2, cnt):
        code = b""
        for off, slot in ((4, s1), (8, s2)):
            code += b"\x8B\x44\x24" + bytes([off]) + b"\xA3" + struct.pack("<I", slot)
        return code + _inc(cnt) + b"\xC3"

    def run(self, va, *, handle=3, cur=0, owner=1, sleep=0, points=0, busy=0,
            carried=0, node=3):
        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            for i in range(4):
                pb = PLAYER_BASE + i * STRIDE
                emu.write32(pb + P_NAME, NAMES + i * 16)      # 名字串指针（替身分支要用）
                emu.write16(pb + P_POINTS, points & 0xFFFF)
                emu.write8(pb + P_CARRIED, carried)
            emu.write32(CUR, cur)
            emu.write32(BUSY, busy)
            if cur >= 4:
                ab = ACTOR_BASE + (cur - 4) * ACTOR_STRIDE
                emu.write8(ab + A_OWNER, owner)               # 槽 +8 = 占用者
                emu.write8(ab + A_SLEEP, sleep)               # 槽 +0x0d = 梦游/冻结
            # objects_info[槽]：+0 类别、+2 格、+4 ?、+5 携带者+1
            rec = OBJ_BASE + (handle - 1) * OBJ_STRIDE
            emu.write(rec, b"\x00" * OBJ_STRIDE)
            # 手搓分派器帧：[esp+0xa4] 槽号、[esp+0x9c] 类别、[esp+0xa0] 格子种类、
            # [esp+0x98] 节点玩家位掩码
            for off, val in ((0xA4, handle), (0x9C, 0), (0xA0, 0), (0x98, 0)):
                emu.write32(STACK_TOP + off, val)
            emu.write32(NODE_ARRAY, NODE_PTR)                 # 地图格数组指针
            emu.write8(NODE_PTR + node * 40 + 0x26, 0x77)     # 预置非 0，看炸彈片段清掉

        self.emu.scratch_write(NAMES, b"P0\0".ljust(16, b"\0") * 4)
        self.emu.eval_block(va, DISPATCH_EXIT, {"esi": node}, setup=setup)
        e = self.emu
        rec = OBJ_BASE + (handle - 1) * OBJ_STRIDE
        return {
            "points": [e.read16(PLAYER_BASE + i * STRIDE + P_POINTS) for i in range(4)],
            "carried": [e.read8(PLAYER_BASE + i * STRIDE + P_CARRIED) for i in range(4)],
            "rec0": e.read8(rec), "rec4": e.read8(rec + 4), "rec5": e.read8(rec + 5),
            "remove": e.readu32(M_REMOVE), "n_remove": e.readu32(C_REMOVE),
            "wreck": e.readu32(M_WRECK), "n_wreck": e.readu32(C_WRECK),
            "hosp": (e.readu32(M_HOSP1), e.readu32(M_HOSP2)), "n_hosp": e.readu32(C_HOSP),
            "recv": (e.readu32(M_RECV1), e.readu32(M_RECV2)), "n_recv": e.readu32(C_RECV),
            "txn": e.readu32(C_TXN), "show": e.readu32(C_SHOW),
            "say": (e.readu32(M_SAY1), e.readu32(M_SAY2)), "n_say": e.readu32(C_SAY),
            "refresh": e.readu32(C_REFRESH), "fmt": e.readu32(C_FMT),
            "anim": (e.readu32(C_LOAD), e.readu32(C_BLIT), e.readu32(C_FREE)),
            "stripped": e.readu32(C_STRIP),
            "node_byte": e.read8(NODE_PTR + node * 40 + 0x26),
            "busy": e.readu32(BUSY),
        }

    def run_via_dispatch(self, *, actor=0, node=5, land_type=0, owner_mask=0,
                         slot=0, type_=0, steps=0, sleep=0, points=0):
        """★ 从**分派器入口** `0x41b42d` 驱动 —— 连同它自己那套「读格子编码字」一起。

        与 `run()` 的差别：`run()` 手搓 `[esp+0x98/+0x9c/+0xa0/+0xa4]` 四个帧内量、
        直接进某个处理器；本方法**只**写地图格与玩家/NPC 记录，让分派器自己：

        ```asm
        ; @source 0x41b461（当前格号）→ 0x41b47f（取节点记录）→ 0x41b491..0x41b4e0
        0041b4a1  and ecx, 0xf00 / shr 8  → [esp+0x98] = 玩家占位掩码
        0041b4b4  and eax, 0xff0000 / shr 0x10 → [esp+0xa4] = 物件槽号
        0041b4d4  mov al, [槽*24 + 0x496d08]    → [esp+0x9c] = 类别
        0041b4bf  and ecx, 0xff                 → [esp+0xa0] = 格子种类
        ```
        然后按 `[esp+0x9c]` 查跳表。⇒ 这一组用例钉的是**编码字 → 帧内量 → 处理器**
        这条链，顺带覆盖 `0x41b4e7` 的「娃娃在跳表外被截住」。
        """
        enc = ((slot & 0xFF) << 16) | ((owner_mask & 0xF) << 8) | (land_type & 0xFF)

        def setup(emu):
            for s in ALL_SLOTS:
                emu.write32(s, 0)
            for i in range(4):
                pb = PLAYER_BASE + i * STRIDE
                emu.write32(pb + P_NAME, NAMES + i * 16)
                emu.write16(pb + P_POINTS, points & 0xFFFF)
            # 当前格号：玩家在 `+0x0c`、替身在槽 `+4`（@source 0x41b461 / 0x41b472）
            if actor < 4:
                emu.write16(PLAYER_BASE + actor * STRIDE + 0x0C, node)
            else:
                ab = ACTOR_BASE + (actor - 4) * ACTOR_STRIDE
                emu.write16(ab + 4, node)
                emu.write16(ab + 6, node)          # lastNode：娃娃支要用来算打飞方向
                emu.write8(ab + A_OWNER, 2)
                emu.write8(ab + A_SLEEP, sleep)
            emu.write32(CUR, actor)
            emu.write32(BUSY, steps)
            # 地图格记录：+0/+2 屏幕 x/y、+0x24 编码字（低 8 位种类 / 8..11 玩家位 / 16..23 槽号）
            base = NODE_PTR + node * 40
            emu.write(base, b"\x00" * 40)
            emu.write16(base + 0x00, 100)
            emu.write16(base + 0x02, 200)
            emu.write32(base + 0x24, enc)
            emu.write32(NODE_ARRAY, NODE_PTR)
            # objects_info[槽-1].+0 = 类别（分派器就是读这个决定跳哪一支）
            if slot != 0:
                rec = OBJ_BASE + (slot - 1) * OBJ_STRIDE
                emu.write(rec, b"\x00" * OBJ_STRIDE)
                emu.write8(rec, type_)
                emu.write16(rec + 2, node)

        self.emu.scratch_write(NAMES, b"P0\0".ljust(16, b"\0") * 4)
        # 直接进分派器入口：它自己 `push×4 + sub esp,0xa8`，所有帧内量都自己算
        self.emu.eval_block(DISPATCH, DISPATCH_EXIT, None, setup=setup)
        e = self.emu
        return {
            "points": [e.read16(PLAYER_BASE + i * STRIDE + P_POINTS) for i in range(4)],
            "remove": e.readu32(M_REMOVE), "n_remove": e.readu32(C_REMOVE),
            "wreck": e.readu32(M_WRECK), "hosp": (e.readu32(M_HOSP1), e.readu32(M_HOSP2)),
            "n_hosp": e.readu32(C_HOSP), "txn": e.readu32(C_TXN),
            "recv": (e.readu32(M_RECV1), e.readu32(M_RECV2)),
            "say": (e.readu32(M_SAY1), e.readu32(M_SAY2)),
            "node_byte": e.read8(NODE_PTR + node * 40 + 0x26),
            # ★ `+0x08` 是 **float32**（`fstp dword`，见 test_object_float_move.py）
            "obj_x": (struct.unpack("<f", e.read(OBJ_BASE + (slot - 1) * OBJ_STRIDE + 8, 4))[0]
                      if slot else 0.0),
            "busy": e.readu32(BUSY),
        }


def main():
    print("差分测试 #37：四个「踩上去」物件落点（分派器片段）\n")
    f = F()

    print("[A] 类别 14 寶箱 `0x41bb0c`：`remove_object(0xe)` + 點券 +500")
    s = f.run(TREASURE, cur=0, handle=9, points=100)      # ★ 帧里槽号给 9（≠14）
    case("★ 移除的是**写死的槽 14**，不是帧里的 9", (s["remove"], s["n_remove"]), (14, 1))
    case("★ 玩家 0：100 + 500 = 600", s["points"][0], 600)
    case("   落点事务一次 + 文字框一次", (s["txn"], s["show"]), (1, 1))
    case("   台词：`player_say(0, 0, …)`", (s["say"], s["n_say"]), ((0, 0), 1))
    case("   无毁车/住院/道具回收/刷新", (s["n_wreck"], s["n_hosp"], s["n_recv"],
                                        s["refresh"]), (0, 0, 0, 0))
    s = f.run(TREASURE, cur=0, handle=14, points=65520)
    case("★ 65520 + 500 ⇒ 16 位回绕 66020−65536 = 484", s["points"][0], 484)

    print("\n[B] 寶箱 · 替身（`[0x49910c] == 4`）踩到 ⇒ 500 加到**主人**头上")
    s = f.run(TREASURE, cur=4, owner=2, handle=14, points=0)
    case("★ 2 号玩家（主人）+500，1 号玩家不动", (s["points"][2], s["points"][1]), (500, 0))
    case("★ 同样移除槽 14", (s["remove"], s["n_remove"]), (14, 1))
    case("★ 台词由**主人**说（`push edi`，edi = 槽 +8 占用者）⇒ (2, 0)", s["say"], (2, 0))
    case("★ 四个处理器里**只有它**收尾调 `refresh_map()`", s["refresh"], 1)
    s = f.run(TREASURE, cur=4, owner=2, sleep=1, handle=14, points=0)
    case("★ 冻结中（槽 +0x0d != 0）⇒ 整支跳过", (s["points"][2], s["n_remove"]), (0, 0))
    s = f.run(TREASURE, cur=5, owner=2, handle=14, points=0)
    case("★ 5 号替身 ⇒ 也跳过（只认 ==4）", (s["points"][2], s["n_remove"]), (0, 0))

    print("\n[C] 类别 16 路障 `0x41bceb`：`remove_object(槽号)` + 清忙标志 + 台词")
    s = f.run(ROADBLOCK, cur=1, handle=7, points=777, busy=1)
    case("★ 移除的是**帧里的槽号** 7", (s["remove"], s["n_remove"]), (7, 1))
    case("★ `[0x48baf8] = 0`", s["busy"], 0)
    case("   點券一分不动 / 事务一次", (s["points"][1], s["txn"]), (777, 1))
    case("   说一句（槽 1）`player_say(1, 1, …)`", s["say"], (1, 1))
    case("   无毁车/住院/回收/刷新", (s["n_wreck"], s["n_hosp"], s["n_recv"],
                                    s["refresh"]), (0, 0, 0, 0))
    s = f.run(ROADBLOCK, cur=4, owner=2, handle=7, points=0)
    case("★ 替身 4 号：照样移除，且 `receive_tool(2, 2)`（路障回主人）",
         (s["remove"], s["recv"], s["n_recv"]), (7, (2, 2), 1))
    case("   替身 4 号不说台词 / 不刷新（只有寶箱那支调 refresh）",
         (s["n_say"], s["refresh"]), (0, 0))
    case("   但**摆了文字框**（sprintf → `show(text,0x5dc)`）", (s["fmt"], s["show"]), (1, 1))
    s = f.run(ROADBLOCK, cur=8, owner=2, handle=7, points=0)
    case("★★ 实体 8（機器娃娃）⇒ 全跳过（`cmp ecx,4 / jne` 排除）",
         (s["n_remove"], s["n_recv"], s["refresh"]), (0, 0, 0))
    s = f.run(ROADBLOCK, cur=5, owner=2, handle=7, points=0)
    case("   ★ 5 号走**玩家分支**：移除 + 清忙，但不说台词、不回收",
         (s["remove"], s["busy"], s["n_say"], s["n_recv"]), (7, 0, 0, 0))
    s = f.run(ROADBLOCK, cur=4, owner=2, handle=7, sleep=1)
    case("   替身 4 号冻结中 ⇒ 跳过", s["n_remove"], 0)

    print("\n[D] 类别 17 地雷 `0x41be5f`：移除 + 毁座驾 + 住院 3 天")
    s = f.run(MINE, cur=2, handle=5)
    case("★ 移除物件（帧槽号 5）", (s["remove"], s["n_remove"]), (5, 1))
    case("★ 毁座驾 `0x40cd07(2)`", (s["wreck"], s["n_wreck"]), (2, 1))
    case("★★ 住院 `0x43ec3f(2, 3)`（3 天）", s["hosp"], (2, 3))
    case("★ `[0x48baf8] = 0`（★ 这一支**不**调落点事务、不摆文字框）",
         (s["busy"], s["txn"], s["show"]), (0, 0, 0))
    case("★ 爆炸动画：MKF 装载/贴图/卸载各一", s["anim"], (1, 1, 1))
    case("   说一句 `player_say(2, 1, …)`", s["say"], (2, 1))
    s = f.run(MINE, cur=5, owner=2, handle=5)
    case("★ 5 号替身：照样移除 + 照样**住院 3 天**，但不毁座驾",
         (s["remove"], s["wreck"], s["hosp"]), (5, 0, (5, 3)))
    s = f.run(MINE, cur=4, owner=2, handle=5)
    case("★★ 4 号（小偷）走**另一支**：移除 + `receive_tool(2, 3)`（地雷回主人）",
         (s["remove"], s["recv"]), (5, (2, 3)))
    case("   这一支**不毁座驾、不住院**", (s["n_wreck"], s["n_hosp"]), (0, 0))
    s = f.run(MINE, cur=2, handle=5, busy=1)
    case("★★ 「移动中」（`[0x48baf8] != 0`）⇒ 玩家分支整支跳过",
         (s["n_remove"], s["n_wreck"], s["n_hosp"]), (0, 0, 0))
    s = f.run(MINE, cur=4, owner=2, handle=5, sleep=1)
    case("   替身 4 号冻结中 ⇒ 跳过", s["n_remove"], 0)

    print("\n[E] 类别 18 定時炸彈 `0x41bfd2`：挂到踩到者身上")
    s = f.run(BOMB, cur=0, handle=6)
    case("★ `player[+0x40] = 槽号`（6）", s["carried"][0], 6)
    case("★ 物件记录 `+5 = 踩到者+1`（携带者）", s["rec5"], 1)
    case("★ 物件记录 `+4 = 0x26`（写入值，语义未决）", s["rec4"], 0x26)
    case("★ 当前格字节 `[node]+0x26` 被清 0", s["node_byte"], 0)
    case("   事务一次 + 台词 `player_say(0, 2, …)`", (s["txn"], s["say"]), (1, (0, 2)))
    case("   不动點券 / 无毁车住院", (s["points"][0], s["n_wreck"], s["n_hosp"]),
         (0, 0, 0))
    s = f.run(BOMB, cur=0, handle=6, carried=3)
    case("★★ 已带着一个物件（`+0x40 != 0`）⇒ 整支跳过",
         (s["carried"][0], s["rec5"]), (3, 0))
    s = f.run(BOMB, cur=0, handle=6, busy=1)
    case("   「移动中」⇒ 也跳过", (s["rec5"], s["n_remove"]), (0, 0))
    s = f.run(BOMB, cur=4, owner=2, handle=6)
    case("★★ 替身 4 号踩到：移除槽 6 + `receive_tool(2, 4)`（炸彈回主人）",
         (s["remove"], s["recv"]), (6, (2, 4)))
    case("   替身分支**不挂到自己身上**（主人 +0x40 仍为 0）", s["carried"][2], 0)

    print("\n[F] ★ 从**分派器入口** `0x41b42d` 驱动：编码字 → 帧内量 → 处理器")
    s = f.run_via_dispatch(actor=0, node=5, slot=0, steps=0)
    case("★★ 格里没物件（槽号 0）⇒ 一件调用都没有",
         (s["n_remove"], s["txn"], s["points"][0], s["busy"]), (0, 0, 0, 0))
    s = f.run_via_dispatch(actor=0, node=5, slot=14, type_=14, steps=0, points=100)
    case("★★ 编码字槽号在 16..23 位 → 读出类别 14 → 跳 `0x41bb0c`：+500 且移除槽 14",
         (s["points"][0], s["remove"]), (600, 14))
    s = f.run_via_dispatch(actor=0, node=5, slot=14, type_=14, steps=1, points=100)
    case("   ★ 同一格但 `[0x48baf8] = 1`（还没停）⇒ 寶箱不生效",
         (s["points"][0], s["n_remove"]), (100, 0))
    s = f.run_via_dispatch(actor=0, node=5, slot=17, type_=17, steps=0)
    case("   地雷整条链跑通：移除槽 17", s["remove"], 17)
    s = f.run_via_dispatch(actor=8, node=5, slot=14, type_=14, steps=0)
    case("★★★ 娃娃（actor 8）在跳表**之前**被截住：移除槽 14，但**不加 500**",
         (s["remove"], s["points"][0]), (14, 0))
    case("   娃娃支照样「打飞」物件（写 `+0x08` 的 x）", s["obj_x"] > 0, True)
    s = f.run_via_dispatch(actor=5, node=5, slot=17, type_=17, steps=0)
    case("   ★ 5 号（強盜）踩地雷：走**玩家分支** ⇒ 住院 `0x43ec3f(5,3)`",
         (s["remove"], s["hosp"]), (17, (5, 3)))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
