#!/usr/bin/env python3
"""
通道 2 差分测试 #41 · **時光機還原** `0x448544`（`_rich4_restore_last_state`，1338 字节）

時光機（道具 10）按玩家各存一块 **10,008 字节（0x2718）的快照**（`0x48cb80 + p*0x2718`），
还原时把里面的各区**搬回全局**。本测试**不靠人工抄表**：两趟跑（快照内容换成另一套
逐字节不同的花样），把 DGROUP/.bss **做差**，差出来的就是「被还原的区」；
再按「目标字节 == 源花样」把每区的**源偏移**反解出来 ⇒ 得到一张**机械导出**的
「(源偏移 → 目标全局, 长度)」表，与 PRD / 复刻侧的表对账。

```asm
; @source 0x448544（片段）
00448547  edx = [0x49910c]                        ; 当前玩家
0044855e  ...（×0x2718 的乘加链）⇒ eax = p*0x2718
00448568  cmp dword [eax + 0x48cb80], 0 / jne 0x448577
00448571  eax = 0 / 返回                          ; ★ 没有快照 ⇒ 返回 0，一个字节都不动
00448577  edx = [eax + 0x48cb84] ; [0x497160] = edx   ; 日期（快照 +4）
00448583  push 0x1a0 / … push 0x496b68 / call 0x456de8 ; memcpy(玩家结构, 快照+8, 0x1a0)
0044859e  for (ebx < [0x499114]) {                ; ★ 玩家名/头像的**角色表常量回填**
            dl = byte [player+0x13]（角色号）
            dword [player + 0] = [0x47e80c + 角色号*0x68]
          }
          …16 次 memcpy（特殊实体/物件表/手牌/道具/库存/行情/AI 打分/持股/股票/公佈欄/
            樂透号码/监狱與医院占用/两副牌堆）+ 若干单字段……
00448a37  esi = [p*0x2718 + 0x48f294]            ; ★ 该玩家的**地图副本指针**
00448a3f  edi = [0x47493c]                        ; 地图缓冲
00448a46  call 0x456de8                           ; memcpy(地图缓冲, 地图副本, [0x498e94])
00448a4e  call 0x40c03b                           ; （表现层）
00448a53  for (ebx = 0; ebx < 9; ebx++)            ; 重绘：< [0x499114] 或 < 4 的那些
00448a6b    call 0x40b93b(ebx)
00448a75  eax = 1                                 ; 返回 1
```

## 打桩

| VA | 原用途 | 桩 |
|---|---|---|
| `0x456de8` | CRT `memcpy`（**本仿真器跑不了**：`mov es/movsd` 段寄存器技巧）| `rep movsb` 版 |
| `0x40b93b` | 玩家重绘 | 计数 + 记实参 + `ret` |
| `0x40c03b` | （0 参调用，表现层）| 计数 + `ret` |

## 诚实边界

- 快照区的**有效标记**（`+0`）与**地图副本指针**（`+0x2714`）不是从状态块搬来的，
  本测试按原版那样单独处理；
- 差分会把「角色表常量回填」也算成变化 —— 那一笔是**函数自己**写的（不是快照内容），
  本测试显式排除 `player[i]+0` 那 4 个 dword 再对账（并在场景 B 里单独钉它）；
- 快照块自身（`0x48CB80..0x4967E0`）在两次跑里内容不同，必须**排除**在差分区之外。

跑法：cd rich4-spec && .venv/bin/python tests/test_restore_last_state.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

RESTORE = 0x448544
MEMCPY, DRAW_PLAYER, OTHER0 = 0x456DE8, 0x40B93B, 0x40C03B

DGROUP_LO, DGROUP_HI = 0x463000, 0x463000 + 158720
BSS_LO, BSS_HI = 0x48A000, 0x48A000 + 64512
PLAYER_BASE, P_CHAR = 0x496B68, 0x13
CHAR_TABLE = 0x47E80C
SNAP0, SNAP_STRIDE = 0x48CB80, 0x2718
MAP_PTRS, MAP_BUF, MAP_SIZE = 0x48F294, 0x47493C, 0x498E94
CUR, NUMP = 0x49910C, 0x499114

S = SCRATCH_BASE
MAP_SRC, MAP_DST = S + 0x1000, S + 0x2000
C_DRAW, C_OTHER = S + 0x3000, S + 0x3004
RESULTS = []
REMAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                      "rich4-remake", "packages", "core", "src", "loaders", "save-writer.ts")


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<60} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def p1(off):
    # ★ 低 8 位与**高 8 位**都参与 ⇒ 相差 256 的偏移花样也不同（否则反解源偏移必多解）
    return ((off * 31 + 7) ^ ((off >> 8) * 0x5B)) & 0xFF


def p2(off):
    # ★ 与 p1 **逐字节都不同**（差集才恰好等于「被还原的区」，不会因巧合相等而漏）
    return p1(off) ^ 1


class F:
    def __init__(self):
        self.emu = Emu()
        # ★ 必须 pushad/popad 包住：`0x448544` 全程用 ebx 当循环计数，
        #   桩里不保存就会把调用方的寄存器打乱（表现为后面某次 memcpy 写到未映射地址）
        #   pushad 之后实参偏移 +32 ⇒ dst=[esp+0x24]、src=[esp+0x28]、size=[esp+0x2c]
        self.emu.patch(MEMCPY, b"\x60"
                               b"\x8B\x7C\x24\x24\x8B\x74\x24\x28\x8B\x4C\x24\x2C"
                               b"\xF3\xA4\x61\xC3")
        self.emu.patch(DRAW_PLAYER, b"\xFF\x05" + struct.pack("<I", C_DRAW) + b"\xC3")
        self.emu.patch(OTHER0, b"\xFF\x05" + struct.pack("<I", C_OTHER) + b"\xC3")

    def run(self, *, flag=1, pattern=p1, cur=0, nump=4, map_size=0x33, map_pat=0x40):
        def setup(emu):
            emu.write32(CUR, cur)
            emu.write32(NUMP, nump)
            emu.write32(C_DRAW, 0)
            emu.write32(C_OTHER, 0)
            # 快照块：整块铺花样，再把有效标记写成 1
            snap = SNAP0 + cur * SNAP_STRIDE
            emu.write(snap, bytes(pattern(o) for o in range(SNAP_STRIDE)))
            emu.write32(snap, flag)
            # 地图副本（每个玩家一个指针）+ 尺寸 + 目标缓冲
            emu.write(MAP_SRC, bytes((map_pat + i) & 0xFF for i in range(map_size)))
            emu.write32(MAP_BUF, MAP_DST)          # ★ 全局里的「地图缓冲指针」
            emu.write(MAP_DST, b"\x00" * map_size)
            for p in range(4):
                emu.write32(MAP_PTRS + p * SNAP_STRIDE, MAP_SRC)
            emu.write32(MAP_SIZE, map_size)

        r = self.emu.call(RESTORE, [], setup=setup)
        return r, self._dump()

    def _dump(self):
        e = self.emu
        img = {}
        for lo, hi in ((DGROUP_LO, DGROUP_HI), (BSS_LO, BSS_HI)):
            img[lo] = e.read(lo, hi - lo)
        return img


def flat(img):
    """把两段内存拼成 {地址: 字节}"""
    out = {}
    for lo, blob in img.items():
        for i, b in enumerate(blob):
            out[lo + i] = b
    return out


def diff_regions(a, b, exclude_lo, exclude_hi):
    """逐字节做差 ⇒ 变化的连续区间（排除快照块自身）"""
    fa, fb = flat(a), flat(b)
    addrs = sorted(fa)
    out = []
    i = 0
    while i < len(addrs):
        addr = addrs[i]
        if fa[addr] == fb[addr] or (exclude_lo <= addr < exclude_hi):
            i += 1
            continue
        j = i
        while (j < len(addrs) and fa[addrs[j]] != fb[addrs[j]]
               and not (exclude_lo <= addrs[j] < exclude_hi)):
            j += 1
        out.append((addr, j - i))
        i = j
    return out


def best_source(fa, addr, size, span=SNAP_STRIDE):
    """反解这一字节来自快照的哪个偏移：取**能连续对上最长**的那个 k（并列取最小）。

    ⚠️ 8 位花样必然多解（p1 有 256 条同余线），只看前几个字节会挑到错的 k ——
    表现是区内被切成一堆 4/8 字节的假碎片。
    """
    first = fa.get(addr)
    best = (0, 0)
    for k in range(span):
        if p1(k) != first:
            continue
        run = 1
        while run < size and fa.get(addr + run) == p1(k + run):
            run += 1
        if run > best[1]:
            best = (k, run)
    return best


def split_by_source(fa, dst, size):
    """把一段变化区间按快照花样反解成若干 (源偏移, 长度)。

    高 8 位也参与花样 ⇒ 相差 256 的偏移不会混淆；区内**每个字节**都必须接着
    `p1(K + j)`，否则就是另一个区（相邻区会在差集里连成一段）。
    """
    out = []
    i = 0
    while i < size:
        k, run = best_source(fa, dst + i, size - i)
        if run == 0:
            i += 1
            continue
        out.append((k, run))
        i += run
    return out


def _imm(op):
    try:
        return int(op, 0)
    except ValueError:
        return None


def scan_restores():
    """从 `0x448544` 的反汇编里扫出**所有**搬运：`(快照源偏移, 目标全局, 长度)`。

    两种形状（都不靠人工抄表）：

    1. **memcpy**：`push <长度>` …（乘加链 `… + 0x48cb80 + <K>`）… `push eax`（源）
       `push <目标全局>` `call 0x456de8`；
    2. **单字段**：`mov <reg>, dword ptr [<reg> + 0x48XXXX]`（XXXX 落在快照块
       `[0x48cb80, +0x2718)` 内 ⇒ `K = XXXX − 0x48cb80`）后紧跟
       `mov dword ptr [<目标全局>], <reg>` ⇒ 长度 4。
       ★ 这一支的基址是 `0x48f240`（= `0x48cb80 + 0x26c0`）而不是 `0x48cb80` ——
       同一个块的另一种寻址，不读代码会以为是「另一张表」。
    """
    import rich4dis as R
    im = R.Image(R.EXE_DEFAULT)
    dm = R.Disassembler(im)
    off = R.CODE_OFF + (RESTORE - R.CODE_VA)
    insns = list(dm.md.disasm(im.data[off:off + 1338], RESTORE))
    out = []
    for k, i in enumerate(insns):
        # ── 形状 2：单字段 ──
        if i.mnemonic == "mov" and ", dword ptr [" in i.op_str:
            reg, src = i.op_str.split(", ", 1)
            m = re.search(r"\[([a-z0-9]+) \+ (0x[0-9a-f]+)\]", src)
            if m is not None:
                disp = int(m.group(2), 16)
                nxt = insns[k + 1] if k + 1 < len(insns) else None
                if (nxt is not None and nxt.mnemonic == "mov"
                        and nxt.op_str.startswith("dword ptr [0x")
                        and nxt.op_str.endswith(f"], {reg}")):
                    dst = int(nxt.op_str.split("[")[1].split("]")[0], 16)
                    if SNAP0 <= disp < SNAP0 + SNAP_STRIDE and 0x463000 <= dst < 0x49A000:
                        out.append((disp - SNAP0, dst, 4))
        # ── 形状 1：memcpy ──
        if i.mnemonic != "call" or i.op_str != hex(MEMCPY):
            continue
        win = insns[max(0, k - 40):k]
        if not win or win[-1].mnemonic != "push":
            continue
        dst = _imm(win[-1].op_str)
        if dst is None or not 0x463000 <= dst < 0x49A000:
            continue
        size = None
        for j in reversed(win[:-1]):
            if j.mnemonic == "push":
                v = _imm(j.op_str)
                if v is not None and v != dst:
                    size = v
                    break
        adds = [_imm(j.op_str.split(", ", 1)[1]) for j in win
                if j.mnemonic == "add" and j.op_str.startswith("eax, ")]
        ks = [a for a in adds if a is not None and a != 0x48CB80]
        if ks:
            out.append((ks[-1], dst, size))
    return sorted(out)


def remake_offsets():
    txt = open(REMAKE, encoding="utf-8").read()
    blk = txt[txt.index("export const SNAPSHOT_REGIONS"):]
    blk = blk[:blk.index("];")]
    return sorted({int(m, 16) for m in re.findall(r"snapshotOffset: (0x[0-9a-f]+)", blk)})


def main():
    print("差分测试 #41：時光機還原 `0x448544`（1338 字节）\n")
    f = F()

    print("[A] 有效标记为 0 ⇒ 一个字节都不动、返回 0")
    r0, img_a = f.run(flag=0, pattern=p1)
    r0b, img_b = f.run(flag=0, pattern=p2)
    case("★ 返回 0", r0["eax"], 0)
    case("★★ 快照内容再怎么变也不动一个字节（排除快照块自身后差集为空）",
         diff_regions(img_a, img_b, SNAP0, SNAP0 + 4 * SNAP_STRIDE), [])

    print("\n[B] 两趟花样做差 + 反汇编扫描 ⇒ 逐区对账")
    ra, ia = f.run(pattern=p1, nump=0)
    rb, ib = f.run(pattern=p2, nump=0)
    case("★ 返回 1（有快照 ⇒ 成功）", (ra["eax"], rb["eax"]), (1, 1))
    runs = diff_regions(ia, ib, SNAP0, SNAP0 + 4 * SNAP_STRIDE)
    fa = flat(ia)
    changed = set()
    for lo, n in runs:
        changed.update(range(lo, lo + n))
    table = scan_restores()
    union = set()
    for src, dst, size in table:
        if size is None or src is None:
            continue
        union.update(range(dst, dst + size))
    case("★★ 反汇编扫出的区数 == 28（复刻侧表长）", len(table), 28)
    offs = sorted({src for src, _d, _l in table if src is not None})
    case("★★ 快照偏移集合 == 复刻侧 `SNAPSHOT_REGIONS`（机械对账）", offs, remake_offsets())
    # ★ 12 支股票每笔的**首 dword**不在快照里：还原之后被另一处写入覆盖
    #   （两趟花样在该处相同 ⇒ 那次写入与快照内容无关）。本测试只钉这一形状。
    stock_head = sorted(0x496980 + 0x24 * k + i for k in range(12) for i in range(4))
    bad = []
    for src, dst, size in table:
        if size is None or src is None:
            continue
        for j in range(size):
            if dst + j in stock_head:
                continue
            if fa.get(dst + j) != p1(src + j):
                bad.append((src, dst, j))
                break
    case("★★ 每一区的目标字节都 == 快照花样 `p1(源偏移 + j)`（逐区逐字节）", bad, [])
    missing = sorted(union - changed)
    if missing:
        print(f"      （并集里两趟仍相同的字节：{[hex(a) for a in missing[:16]]} …共 {len(missing)}）")
    extra = sorted(changed - union)
    case("★★ 差集没有落在各区之并之外的字节（扫描没漏区）", extra, [])
    case("★★ 并集里两趟仍相同的字节 == **12 支股票的首 dword**（还原后被另写）",
         sorted(union - changed), stock_head)
    if extra:
        print(f"      （多出来的字节位置：{extra[:12]} …共 {len(extra)}）")
    by_dst = {d: (k, l) for k, d, l in table if l is not None}
    case("★ 日期：快照 +4 → `0x497160`（4 字节）", by_dst.get(0x497160), (4, 4))
    case("★ 玩家结构：快照 +8 → `0x496b68`，0x1a0 字节（4×0x68）",
         by_dst.get(PLAYER_BASE), (8, 0x1A0))
    case("★ 特殊实体：快照 +0x1a8 → `0x498e28`，0x50 字节（5×0x10）",
         by_dst.get(0x498E28), (0x1A8, 0x50))
    case("★ 物件表：快照 +0x1f8 → `0x496d08`，0x450 字节（46×0x18）",
         by_dst.get(0x496D08), (0x1F8, 0x450))
    case("★ 手牌：快照 +0x648 → `0x499120`，0x3c 字节（4×15）",
         by_dst.get(0x499120), (0x648, 0x3C))
    case("★ 道具持有：快照 +0x684 → `0x49915c`，0x3c 字节（4×15）",
         by_dst.get(0x49915C), (0x684, 0x3C))
    case("★ 卡片库存：快照 +0x6c0 → `0x499198`，0x1e 字节",
         by_dst.get(0x499198), (0x6C0, 0x1E))
    case("★ 道具库存：快照 +0x6de → `0x497320`，8 字节",
         by_dst.get(0x497320), (0x6DE, 8))
    case("★ 行情历史：快照 +0x6ec → `0x497328`，0x1b00 字节",
         by_dst.get(0x497328), (0x6EC, 0x1B00))
    case("★ 各玩家持仓：快照 +0x21ec → `0x4971a0`，0x180 字节",
         by_dst.get(0x4971A0), (0x21EC, 0x180))
    case("★ 股票 12 支：快照 +0x236c → `0x496980`，0x1b0 字节",
         by_dst.get(0x496980), (0x236C, 0x1B0))
    case("★ 公佈欄：快照 +0x251c → `0x4967e0`，0x150 字节（4×7×12）",
         by_dst.get(0x4967E0), (0x251C, 0x150))
    case("★ 樂透号码表：快照 +0x268c → `0x4990b8`，0x24 字节",
         by_dst.get(0x4990B8), (0x268C, 0x24))
    case("★ 监狱占用：快照 +0x26b0 → `0x496b30`，8 字节", by_dst.get(0x496B30), (0x26B0, 8))
    case("★ 医院占用：快照 +0x26b8 → `0x496b60`，8 字节", by_dst.get(0x496B60), (0x26B8, 8))
    case("★ 新聞牌堆：快照 +0x26c8 → `0x499090`，0x24 字节",
         by_dst.get(0x499090), (0x26C8, 0x24))
    case("★ 命運牌堆：快照 +0x26ec → `0x496b38`，0x25 字节",
         by_dst.get(0x496B38), (0x26EC, 0x25))
    case("★ 单字段：命運游标 `0x4990b4` ← 快照 +0x26c4", by_dst.get(0x4990B4), (0x26C4, 4))
    case("★ 单字段：新聞游标 `0x4990e0` ← 快照 +0x26c0", by_dst.get(0x4990E0), (0x26C0, 4))
    case("★ 快照块 4 份正好铺到 `0x4967e0`（= 公佈欄，互不重叠）",
         SNAP0 + 4 * SNAP_STRIDE, 0x4967E0)
    case("★★ 差集里没有一个字节落在快照块自身",
         sorted(a for a in changed if SNAP0 <= a < SNAP0 + 4 * SNAP_STRIDE), [])

    print("\n[C] 地图副本与收尾（不在 DGROUP/.bss 的那一部分）")
    case("★ 地图缓冲被按 `[0x498e94]` 字节整块搬自该玩家的副本",
         f.emu.read(MAP_DST, 0x33), bytes((0x40 + i) & 0xFF for i in range(0x33)))
    # @source 0x448a5d：`if (ebx < [0x499114]) 画; else if (ebx < 4) 跳过; else 画`
    #   ⇒ 重绘的是「在局玩家」+ **实体槽 4..8**（0..nump 与 4..8 的并集）
    case("★ 收尾重绘：nump=0 ⇒ 只有实体槽 4..8 共 5 个", f.emu.readu32(C_DRAW), 5)
    case("   0 参的那个表现层调用发生一次", f.emu.readu32(C_OTHER), 1)

    print("\n[D] 角色表常量回填（函数自己写的，不是快照内容）")
    ra, ia = f.run(pattern=p1, nump=4)
    blobs = {lo: ia[lo] for lo in ia}

    def u32(addr):
        return struct.unpack_from("<I", blobs[addr & ~0x1FFF if False else
                                               (DGROUP_LO if addr < BSS_LO else BSS_LO)],
                                  addr - (DGROUP_LO if addr < BSS_LO else BSS_LO))[0]

    chars = [u32(PLAYER_BASE + i * 0x68 + P_CHAR) & 0xFF for i in range(4)]
    want = [u32(CHAR_TABLE + c * 0x68) for c in chars]
    got = [u32(PLAYER_BASE + i * 0x68) for i in range(4)]
    case("★ 玩家结构 `+0` 被按 `character` 查 `0x47e80c` 回填（4 人）", got, want)
    case("   与快照里那 4 个字节无关（角色号取自快照 +0x13）", chars, [p1(8 + i * 0x68 + 0x13) for i in range(4)])

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 72}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
