#!/usr/bin/env python3
"""扫某个玩家结构字段（绝对地址形式 `[reg + 0x496bXX]`）的所有读写点。

用途：判定一个「状态里没有对应字段」的字节到底是**真状态**还是**派生量**。
例：`0x496b6c`（player+0x04 代表色）的写者为空 ⇒ 它只可能是初始 memcpy 来的
角色表常量（见 `save-scalars.md` §2.17）。

⚠️ 只覆盖**绝对地址形式**。若某处用 `player_base + 0x64` 的寄存器相对形式访问，
本脚本看不见 —— 需要另扫 `[reg + 0xNN]`（`rich4-remake` 的
`gen/db.txt` 或本目录的 `fieldscan` 变体）。
"""
import sys
from pathlib import Path
ROOT=Path("/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-spec"); sys.path.insert(0,str(ROOT/"tools"))
import rich4dis as R
img=R.Image(); dis=R.Disassembler(img); dis.traverse()
# 找到所有「指令的 mem_addr 命中这些地址」的位置（含计算基址 +0x496bXX 的形式）
TARGETS = {0x496B83:"+0x1b f27", 0x496BB2:"+0x4a f74", 0x496BCC:"+0x64 f100"}
hits=[]
for f in dis.funcs.values():
    for x in f.insns:
        if x.mem_addr in TARGETS:
            hits.append((TARGETS[x.mem_addr], x.va, f.va, x.mnemonic, x.op_str))
for label, va, fva, mn, op in sorted(hits):
    print(f"{label:12s} 0x{va:08x} (函数 0x{fva:06x})  {mn} {op}")
