#!/usr/bin/env python3
"""
通道 2 差分测试 · 公佈欄挂牌表 `0x4967e0`（挂牌 `0x4246c5` / 撤件 `0x4247d5`）

用 Unicorn 跑**原版机器码**，逐字节比对该表的 12 字节槽 —— 即验证：

  · 槽布局（`+0` 類型 / `+1` 天龄 / `+2` u16 編號 / `+4` u32 標價 /
    `+8` u16 股數 / `+a`+`+b` 地產快照）；
  · 「**先找第一個空槽，途中遇到同類型同編號就覆蓋那一格**」的挂牌規則；
  · 七格占滿就掛不上；
  · 撤件 = **後面往前挪** + 最後一格清零。

对照规格：`docs/systems/places.md` §5c；remake 实现：`places/notice-board.ts`
的 `listItem`，以及 `loaders/save-writer.ts` 的块 `0x2526` 写出。

跑法：cd rich4-spec && .venv/bin/python tests/test_notice_board.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import Emu, SEGMENTS  # noqa: E402

LIST = 0x4246C5
WITHDRAW = 0x4247D5
BOARD = 0x4967E0
PLAYER_STRIDE = 0x54
SLOTS = 7
SLOT = 12
LAND_BASE = 0x480000
FAC_BASE = 0x481000

RESULTS = []


def model_list(board, kind, id_, price, amount, lands, facs):
    """按规格推演一次挂牌；返回新的 board（就地新列表）。"""
    out = [dict(s) for s in board]
    for i in range(SLOTS):
        cur = board[i]
        if cur["kind"] != 0 and not (cur["kind"] == kind and cur["id"] == id_):
            continue
        s = {"kind": kind, "age": 0, "id": id_, "price": price}
        if kind == 1:
            s["amount"] = amount
        if kind == 2:
            if 2000 < id_ < 4000:
                rec = lands[id_ - 2000]
            else:
                rec = facs[id_ - 4000]
            s["estateType"] = rec["type"]
            s["estateLevel"] = rec["level"]
        out[i] = s
        return out, True
    return out, False


def model_withdraw(board, slot):
    out = [dict(s) for s in board]
    for i in range(slot, SLOTS - 1):
        out[i] = dict(out[i + 1])
    out[SLOTS - 1] = {"kind": 0, "age": 0, "id": 0, "price": 0}
    return out


CRT_MEMCPY = 0x456DE8


class Fixture:
    """⚠️ 两个测试台技巧（都写进 `docs/verification.md` 了）：

    1. **CRT `memcpy` 在本仿真器里跑不了** —— 原版 `0x456de8` 用了
       `mov eax, ds / mov es, eax` 的段寄存器技巧，Unicorn 执行到
       `movsd es:[edi], [esi]` 就 `UC_ERR_WRITE_UNMAPPED`。
       故把它打桩成等价的 `rep movsb` 版本（**被测的是撤件的参数与顺序，
       不是 CRT 自己**）。
    2. **每次改完内存都要重拍快照**：`call()` 前会 `reset()`，
       不重拍的话板上刚写的东西会被还原成初始值（T-A 老坑的新面孔）。
    """

    def __init__(self):
        self.emu = Emu()
        # memcpy(dst, src, len) 的等价替身：19 字节，塞得进原来的 41 字节
        self.emu.patch(
            CRT_MEMCPY,
            bytes.fromhex("8b7c2404" "8b742408" "8b4c240c" "f3a4" "8b442404" "c3"),
        )

    def put(self, va, data):
        self.emu.mu.mem_write(va, bytes(data))

    def setup(self, lands, facs):
        self.put(0x498E84, struct.pack("<I", LAND_BASE))
        self.put(0x498E88, struct.pack("<I", FAC_BASE))
        # ★ 表是 **1 基**（下标 0 是哨兵）：地块 id 2000+i 落在 base + i*0x34
        for i, rec in enumerate(lands, start=1):
            o = LAND_BASE + i * 0x34
            self.put(o + 0x18, [rec["type"]])
            self.put(o + 0x1a, [rec["level"]])
        for i, rec in enumerate(facs, start=1):
            o = FAC_BASE + i * 0x38
            self.put(o + 0x18, [rec["type"]])
            self.put(o + 0x1a, [rec["level"]])
        self.emu.mu.mem_write(BOARD, b"\0" * (4 * PLAYER_STRIDE))
        self.emu._snapshot = {
            va: self.emu.mu.mem_read(va, sz)
            for va, off, sz, w in SEGMENTS if w
        }

    def board(self, player):
        raw = bytes(self.emu.mu.mem_read(BOARD + player * PLAYER_STRIDE, PLAYER_STRIDE))
        out = []
        for i in range(SLOTS):
            o = i * SLOT
            out.append({
                "kind": raw[o],
                "age": raw[o + 1],
                "id": struct.unpack_from("<H", raw, o + 2)[0],
                "price": struct.unpack_from("<I", raw, o + 4)[0],
                "amount": struct.unpack_from("<H", raw, o + 8)[0],
                "estateType": raw[o + 0xA],
                "estateLevel": raw[o + 0xB],
            })
        return out

    def resnap(self):
        """把当前内存重新拍进快照 —— 否则下一次 `call()` 的 reset 会抹掉刚写的板。"""
        self.emu._snapshot = {
            va: self.emu.mu.mem_read(va, sz)
            for va, off, sz, w in SEGMENTS if w
        }

    def list_(self, player, kind, id_, price, amount=0):
        self.emu.call(LIST, [player, kind, id_, price, amount])
        self.resnap()

    def withdraw(self, player, slot):
        self.emu.call(WITHDRAW, [player, slot])
        self.resnap()


def norm(s):
    """模型里没写的格按 0 补齐，便于整体比对。"""
    return {
        "kind": s.get("kind", 0), "age": s.get("age", 0), "id": s.get("id", 0),
        "price": s.get("price", 0), "amount": s.get("amount", 0),
        "estateType": s.get("estateType", 0), "estateLevel": s.get("estateLevel", 0),
    }


def case(desc, got, want):
    ok = [norm(g) for g in got] == [norm(w) for w in want]
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc}")
    if not ok:
        for i, (g, w) in enumerate(zip(got, want)):
            if norm(g) != norm(w):
                print(f"       槽[{i}] 原版={norm(g)}")
                print(f"             规格={norm(w)}")


def main():
    print("差分测试：公佈欄挂牌表（挂牌 0x4246c5 / 撤件 0x4247d5）")
    print("对照规格：docs/systems/places.md §5c\n")

    lands = [None] + [{"type": 0, "level": 3}, {"type": 1, "level": 4}]   # 1 基：2001/2002
    facs = [None] + [{"type": 2, "level": 1}, {"type": 0, "level": 5}]    # 1 基：4001/4002
    f = Fixture()
    f.setup(lands[1:], facs[1:])
    board = f.board(0)

    # ① 股票（類型 1，带股數）→ 落第 0 槽，`+8` 写股數
    f.list_(0, 1, 3, 98_765, 42)
    board, _ = model_list(board, 1, 3, 98_765, 42, lands, facs)
    case("挂牌 股票(類型1, +8 股數) 落第 0 槽", f.board(0), board)

    # ② 地產（類型 2）→ 落第 1 槽，`+a`/`+b` 取**地產表**的 +0x18/+0x1a
    f.list_(0, 2, 2001, 33_000)
    board, _ = model_list(board, 2, 2001, 33_000, 0, lands, facs)
    case("挂牌 地產 2001 → +a/+b = 地產的 類型/等級", f.board(0), board)

    # ③ 設施（類型 2）→ 落第 2 槽，快照取**設施表**
    f.list_(0, 2, 4001, 12_000)
    board, _ = model_list(board, 2, 4001, 12_000, 0, lands, facs)
    case("挂牌 設施 4001 → +a/+b = 設施的 類型/等級", f.board(0), board)

    # ④ 道具（類型 3）→ 落第 3 槽，不写 +8/+a/+b
    f.list_(0, 3, 11, 500)
    board, _ = model_list(board, 3, 11, 500, 0, lands, facs)
    case("挂牌 道具(類型3) 不写 +8/+a/+b", f.board(0), board)

    # ⑤ ★ 同類型同編號再挂 → **覆蓋同一格**（不新占）
    f.list_(0, 3, 11, 777)
    board, _ = model_list(board, 3, 11, 777, 0, lands, facs)
    case("★ 同類型同編號 → 覆蓋原格（不是新占一格）", f.board(0), board)

    # ⑥ 同類型、不同編號 → 下一格
    f.list_(0, 3, 12, 600)
    board, _ = model_list(board, 3, 12, 600, 0, lands, facs)
    case("同類型不同編號 → 下一格", f.board(0), board)

    # ⑦ ★ 同編號、不同類型 → **不能**覆蓋（類型也要相同）
    f.list_(0, 4, 12, 900)
    board, _ = model_list(board, 4, 12, 900, 0, lands, facs)
    case("★ 同編號不同類型 → 另占一格", f.board(0), board)

    # ⑧ 填满 7 格后第 8 件挂不上（板子原样）
    f.list_(0, 4, 20, 100)
    board, _ = model_list(board, 4, 20, 100, 0, lands, facs)
    f.list_(0, 4, 21, 100)
    board2, ok = model_list(board, 4, 21, 100, 0, lands, facs)
    case("第 8 件挂不上（七格已满）", f.board(0), board if not ok else board2)

    # ⑨ 撤件第 0 槽 → 后面的往前挪、末格清零
    f.withdraw(0, 0)
    board = model_withdraw(board, 0)
    case("撤件[0] → 前移 + 末格清零", f.board(0), board)

    # ⑩ 再撤中间一格
    f.withdraw(0, 2)
    board = model_withdraw(board, 2)
    case("撤件[2] → 前移 + 末格清零", f.board(0), board)

    # ⑪ 每个玩家的栏互不影响（玩家 1 仍是空的）
    case("玩家 1 的栏不受影响（全空）", f.board(1),
         [{"kind": 0}] * SLOTS)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
