#!/usr/bin/env python3
"""
真值表测试 #32 · ★★ **點券（`player_info + 0x30`）是 16 位字段** —— 全 exe 所有访问的宽度普查

这一条不驱动某个函数，而是钉住**机器码层面的字段契约**：
原版把 `+0x30` 当 **word** 用，所以每一次加减都按 **16 位回绕**。
只要有一处按 32 位算，长局里「點券够不够」的判据就会与原版分叉
（原版绕回成小数字 ⇒ 付不起/保釋不起，复刻却付得起）。

做法：全文搜 `0x496b98` 这个 32 位位移（`98 6b 49 00`），对每处命中在
**函数级反汇编得到的指令边界表**里回溯定位真指令，再按操作数宽度分类。

```asm
0041b1d7  add word [player + 0x496b98], 0x32     ; 得點券５０點
0041b271  add word [player + 0x496b98], 0x1e     ; 得點券３０點
0041b2f5  add word [player + 0x496b98], 0xa      ; 得點券１０點
0041bb62  add word [player + 0x496b98], 0x1f4    ; 寶箱（当前玩家）
0041bcb6  add word [player + 0x496b98], 0x1f4    ; 寶箱/禮物（替身主人）
0041c25d  sub word [player + 0x496b98], di       ; 偷點券：受害者
0041c27a  add word [player + 0x496b98], di       ; 偷點券：主人
0043d55f  sub word [visitor + 0x496b98], si      ; 保釋（監獄）
0043ec0b  sub word [visitor + 0x496b98], si      ; 保釋（醫院）—— **与監獄完全一样**
```

★★ **本测试逮到并订正了一个自造的假发现（值得记）**：第 93 条曾据
`im.read(0x43ec0c, 6) = 29 b2 98 6b 49 00` 断言「醫院那条是 `sub dword`」，
并把它登记成原版瑕疵 Q-BAIL-1。真相是**反汇编起点错了一格**：
`0x43ec04` 的 `imul edx, [0x49910c], 0x68` 正好 7 字节（末字节 `68` 落在 `0x43ec0a`），
于是 `0x43ec0b` 的 `66` 才是下一条指令的前缀 —— 从 `0x43ec0c` 起解自然只剩
`29 b2 98 6b 49 00`（少了 `66`），看起来像 dword。
⇒ **判「某地址上是什么指令」必须用函数级/线性反汇编定边界，不能从半截字节起解。**

跑法：cd rich4-spec && .venv/bin/python tests/test_points_field.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import rich4dis as R  # noqa: E402

FIELD = 0x496B98
CODE_LO, CODE_HI = 0x401000, 0x462000

# 立即可数的奖点/扣点（不含寄存器操作数与纯读）
EXPECTED_IMMEDIATE = {
    0x41B1D7: ("add", 0x32),    # 得點券５０點
    0x41B271: ("add", 0x1E),    # 得點券３０點
    0x41B2F5: ("add", 0x0A),    # 得點券１０點
    0x41BB62: ("add", 0x1F4),   # 寶箱（当前玩家）
    0x41BCB6: ("add", 0x1F4),   # 寶箱/禮物（替身主人）
}
# 寄存器操作数的写点（数量固定，逐个钉住指令形状）
EXPECTED_REG_WRITES = {
    0x41B152: ("add", "ax"),
    0x41C25D: ("sub", "di"),
    0x41C27A: ("add", "di"),
    0x43CF87: ("sub", "dx"),
    0x43D55F: ("sub", "si"),
    0x43EC0B: ("sub", "si"),
    0x43DEC5: ("sub", "dx"),
    0x44D720: ("add", "ax"),
    0x44D739: ("add", "ax"),
}
RESULTS = []


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<66} 实际 {got!s:<22} 期望 {want!s}")
    return ok


def main():
    print("真值表测试 #32：點券（+0x30）的字段宽度普查\n")
    im = R.Image(R.EXE_DEFAULT)
    dis = R.Disassembler(im)
    print("[0] 先做函数级反汇编，拿到**合法指令边界表**（约 2 秒）")
    dis.traverse(verbose=False)
    boundaries = {}
    for _entry, fn in dis.funcs.items():
        for insn in fn.insns:
            boundaries[insn.va] = insn
    print(f"      函数 {len(dis.funcs)} 个 / 指令 {len(boundaries)} 条")

    pat = struct.pack("<I", FIELD)
    hits = []
    for va in range(CODE_LO, CODE_HI - 4):
        off = im.va_to_off(va)
        if off is None or off + 4 > len(im.data):
            continue
        if im.data[off:off + 4] == pat:
            hits.append(va)

    sites = {}
    unresolved = []
    for h in hits:
        found = False
        for back in (3, 2, 1):
            start = h - back
            insn = boundaries.get(start)
            if insn is not None:
                if "0x496b98" in insn.op_str:
                    sites[start] = (insn.mnemonic, insn.op_str, insn.size)
                    found = True
                    break
                continue
        if not found:
            # ★ 兜底：该处落在**函数级反汇编没覆盖到的碎片**里（本工程有两处：
            #   0x41bcb9、0x43dec8）。判边界的正道是**从已知入口线性扫过来**，
            #   而不是从半截字节起解 —— 线性扫描会自己落在真起点上。
            entry = max((e for e in dis.funcs if e <= h), default=None)
            if entry is not None:
                va = entry
                guard = 0
                while va <= h and guard < 100000:
                    cand = list(dis.md.disasm(im.read(va, 16), va))
                    if not cand:
                        break
                    i0 = cand[0]
                    if i0.address <= h < i0.address + i0.size and "0x496b98" in i0.op_str:
                        sites[i0.address] = (i0.mnemonic, i0.op_str, i0.size)
                        found = True
                        break
                    va = i0.address + i0.size
                    guard += 1
        if not found:
            unresolved.append(h)

    print(f"\n[A] 命中 {len(hits)} 处，定位到指令 {len(sites)} 处")
    case("★ 每一处命中都能在指令边界表里定位（没有半截字节的假象）", unresolved, [])
    for va in sorted(sites):
        mn, ops, size = sites[va]
        width = "dword" if "dword" in ops else ("word" if "word" in ops else "?")
        print(f"      {va:08x}  {size}  {mn:<5} {ops}   [{width}]")

    print("\n[B] ★★ 宽度：**每一处都是 16 位**（`word ptr`），全 exe 没有例外")
    case("命中处数（含读/写/比较）", len(hits), 38)
    non_word = {va: ops for va, (_m, ops, _s) in sites.items() if "word ptr" not in ops}
    case("★★ 非 16 位的访问", non_word, {})
    case("   其中有 32 位访问吗（第 93 条曾误报医院那条）",
         [va for va, (_m, ops, _s) in sites.items() if "dword" in ops], [])

    print("\n[C] 奖点/扣点的**操作数与立即数**（PRD 表格逐条钉）")
    for va, (mn, imm) in sorted(EXPECTED_IMMEDIATE.items()):
        got = sites.get(va)
        case(f"{va:08x} = {mn} → {imm:#x}",
             (got[0], int(got[1].split(",")[-1].strip(), 0)) if got else None,
             (mn, imm))
    for va, (mn, reg) in sorted(EXPECTED_REG_WRITES.items()):
        got = sites.get(va)
        case(f"{va:08x} = {mn} …, {reg}",
             (got[0], got[1].split(",")[-1].strip()) if got else None,
             (mn, reg))

    print("\n[D] 判据与纯读也是 16 位")
    for va, mn in [(0x42EEAB, "cmp"), (0x42F02C, "mov"), (0x43D4F4, "cmp"),
                   (0x43EBA0, "cmp"), (0x4165EA, "mov")]:
        got = sites.get(va)
        case(f"{va:08x} = {mn}（16 位读/比较）",
             (got[0], "word" in got[1]) if got else None, (mn, True))

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 70}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
