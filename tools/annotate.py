#!/usr/bin/env python3
"""
rich4-spec · 机械层：函数注解库与全库反汇编

产出什么
--------
    gen/db.txt        全库反汇编，**调用点已解析成名字**（含 Win32 导入与函数指针表）
    gen/annotations.json  每个函数的一行摘要（名称、类别、被调次数、引用字符串）

为什么它比"每次现查"强
----------------------
非显然但决定性：`call dword ptr cs:[0x46230c]` 光看是**读不出语义**的。
本工具把 IAT 槽解析回 `PeekMessageA`，把函数指针表解析回 `card_functions[1]`，
于是同一段反汇编从"一串数字"变成"能读懂的控制流"。

一次生成后，读任何函数都**不用再手工查 IAT** —— 这是本项目"查索引代替翻汇编"
最直接的体现。

用法
----
    python3 tools/annotate.py build          # 生成 gen/db.txt + gen/annotations.json
    python3 tools/annotate.py show 0x419744  # 看单个函数的带注解反汇编
"""
from __future__ import annotations

import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rich4dis import (Image, Disassembler, EXE_DEFAULT, KNOWN_TABLES,  # noqa: E402
                      is_code_ptr, CODE_VA, CODE_END)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "gen")

# 已知语义的本地函数（来自本会话的实测，全部有 VA 级证据）
KNOWN_LOCAL = {
    0x40DF69: "update_hostility",
    0x44EF41: "player_say",
    0x458370: "strcmp",
    0x419744: "calculate_land_toll",
    0x4413AD: "player_has_card",
    0x456F2D: "rand15",
    0x456F50: "srand_r4",
    0x456E11: "my_free",
    0x456E1F: "my_free_inner",
    0x456F60: "fillBytes32",
    0x458AE0: "memset",
    0x457110: "sprintf_wrap",
    0x458DB5: "vsprintf_wrap",
    0x4563F5: "blitRect",
    0x455B3A: "blitRect_inner",
    0x44FABC: "drawText_colorcode",
    0x450441: "mkf_read_resource",
    0x456F80: "mkf_decompress_entry",
    0x4521CB: "date_today",
    0x40D293: "ctz",
    0x41D559: "toll_related_check",
    0x4018E7: "modal_msg_pump",
    0x4019DD: "WndProc",
    0x458CED: "crt_startup",
    0x456F23: "rand_state_ptr",
    0x458B17: "memset_qwords",
    0x4542CE: "sub_4542ce",
}

CATEGORY = {
    "winapi": "Win32 导入（IAT thunk）",
    "libc": "C 运行时（Watcom/msvcrt 转发）",
    "noreturn": "不返回",
}


def load_imports():
    """载入导入表。⚠️ **键必须转成 int**。

    JSON 的键只能是字符串，若直接用 `int_slot in thunks` 去查，
    永远为 False（实测因此让全部 `call [IAT槽]` 解析失败，
    而这些调用恰恰是判断"这段代码在调哪个 Win32 API"的唯一线索）。
    """
    p = os.path.join(GEN, "import-thunks.json")
    if not os.path.exists(p):
        return {}, {}
    thunks = {int(k, 16): v for k, v in json.load(open(p)).items()}
    imports = {int(k, 16): v for k, v in
               json.load(open(os.path.join(GEN, "imports.json"))).items()}
    return thunks, imports


def build_table_index(img: Image):
    """函数指针表项 → 名字，例如 `card_functions[1]`。"""
    idx = {}
    for name, (tva, n, stride, _) in KNOWN_TABLES.items():
        for k in range(n):
            v = img.u32(tva + k * stride)
            if v and is_code_ptr(v):
                idx.setdefault(v, []).append(f"{name}[{k}]")
    return idx


def name_of(va, img, thunks, table_idx, dis):
    """给一个地址起名。优先级：导入 > 表项 > 已知本地 > 函数入口 > 子块。"""
    if va in thunks:
        dll, fn = thunks[va]
        return f"{dll.split('.')[0]}!{fn}", "winapi"
    # 导入桩是 `jmp dword ptr [iat]`，调用点常直接打在 IAT 槽上
    if va in table_idx:
        return table_idx[va][0], "table"
    if va in KNOWN_LOCAL:
        return KNOWN_LOCAL[va], "local"
    if va in dis.funcs:
        return f"sub_{va:08x}", "func"
    return f"loc_{va:08x}", "inner"


def annotate_insn(i, owner, img, thunks, imports, table_idx, dis):
    """把一条指令渲染成带注解的文本。"""
    extra = ""
    # 调用/跳转目标
    if i.target is not None and (i.is_call or i.mnemonic.startswith("j")):
        nm, _cat = name_of(i.target, img, thunks, table_idx, dis)
        extra = f"   → {nm}"
    # 目标写在 IAT 槽里的间接调用：`call dword ptr cs:[0x46230c]`
    if extra == "" and "[0x" in i.op_str:
        m = i.op_str.split("[")[-1].rstrip("]")
        try:
            slot = int(m, 16)
        except ValueError:
            slot = None
        if slot is not None:
            if slot in thunks:
                dll, fn = thunks[slot]
                extra = f"   → {dll.split('.')[0]}!{fn}"
            elif slot in imports:
                dll, fn = imports[slot]
                extra = f"   → {dll.split('.')[0]}!{fn}"
            elif slot in table_idx:
                extra = f"   → {table_idx[slot][0]}"
    # 全局变量读写标记
    if extra == "" and i.mem_addr is not None:
        extra = "   ← 全局"
    # 字符串
    if i.imm_data is not None or i.mem_addr is not None:
        cand = i.imm_data if i.imm_data is not None else i.mem_addr
        s = img.cstr(cand, 48) if cand else ""
        if s and _looks_like_text(s):
            extra += f'   "{s}"'
    return f"  {i.va:08x}  {i.mnemonic:<7} {i.op_str}{extra}"


def _looks_like_text(s: str) -> bool:
    if not s or len(s) < 2:
        return False
    printable = sum(1 for c in s if c.isprintable())
    return printable == len(s)


def build(verbose=True):
    img = Image(EXE_DEFAULT)
    thunks, imports = load_imports()
    dis = Disassembler(img)
    dis.traverse(verbose=False, include_orphans=True)
    table_idx = build_table_index(img)

    annotations = {}
    lines = []
    lines.append("# rich4.exe 全库反汇编（注解版）")
    lines.append("# 由 tools/annotate.py 生成 —— 调用点已解析为名字（Win32 导入 / 函数指针表 / 已知语义）")
    lines.append(f"# 函数数 {len(dis.funcs)}；导入 {len(thunks)}；表项 {sum(len(v) for v in table_idx.values())}")
    lines.append("")

    for va in sorted(dis.funcs):
        fn = dis.funcs[va]
        nm, cat = name_of(va, img, thunks, table_idx, dis)
        lines.append("#" * 78)
        lines.append(f"# 0x{va:08x}  {nm}   [{cat}]   {len(fn.insns)} 条 / {fn.size} 字节  结尾 {fn.ends}")
        if fn.callers:
            lines.append(f"#   被调用 {len(fn.callers)} 处: " +
                         ", ".join(f"0x{c:08x}" for c in sorted(fn.callers)[:10]))
        if fn.callees:
            names = []
            for c in sorted(fn.callees):
                cn, _ = name_of(c, img, thunks, table_idx, dis)
                names.append(cn)
            lines.append(f"#   调用: " + ", ".join(names[:14]))
        lines.append(f"0x{va:08x}:")
        for i in fn.insns:
            lines.append(annotate_insn(i, va, img, thunks, imports, table_idx, dis))
        lines.append("")

        annotations[f"0x{va:08x}"] = {
            "name": nm, "category": cat, "insns": len(fn.insns), "size": fn.size,
            "ends": fn.ends, "callers": len(fn.callers), "callees": len(fn.callees),
        }

    os.makedirs(GEN, exist_ok=True)
    with open(os.path.join(GEN, "db.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(GEN, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=1)

    if verbose:
        from collections import Counter
        c = Counter(d["category"] for d in annotations.values())
        print(f"已写入 gen/db.txt（{len(lines)} 行）")
        print(f"已写入 gen/annotations.json（{len(annotations)} 个函数）")
        print("  类别分布:", dict(c.most_common()))
    return dis, thunks, imports, table_idx


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "show":
        dis, thunks, imports, table_idx = build(verbose=False)
        img = dis.img
        va = int(argv[2], 16)
        if va not in dis.funcs:
            print(f"0x{va:08x} 不在函数集中")
            return 2
        fn = dis.funcs[va]
        nm, cat = name_of(va, img, thunks, table_idx, dis)
        print(f"# 0x{va:08x}  {nm}  [{cat}]  {len(fn.insns)} 条  结尾 {fn.ends}")
        for i in fn.insns:
            print(annotate_insn(i, va, img, thunks, imports, table_idx, dis))
        return 0
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
