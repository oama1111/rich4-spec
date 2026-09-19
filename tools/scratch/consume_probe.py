#!/usr/bin/env python3
"""每张卡片效果函数：remove_card 与守卫分支的相对位置。

判定 remake `fail(..., consumes)` 的依据：
  · 守卫在 remove_card **之前** → 不扣卡（false）
  · 守卫在 remove_card **之后** → 扣卡（true）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import rich4dis as R  # noqa: E402

CARDS = {
    1: 0x4420D8, 2: 0x4421B4, 3: 0x442325, 4: 0x442622, 5: 0x442B02,
    6: 0x442F4D, 7: 0x44309B, 8: 0x443225, 9: 0x4434C0, 10: 0x4436E0,
    11: 0x443917, 12: 0x443B0F, 13: 0x443E3D, 14: 0x443F80, 15: 0x4440EA,
    16: 0x4441DC, 17: 0x4444BF, 18: 0x444691, 22: 0x444C45, 23: 0x444E1A,
    24: 0x444F25, 25: 0x44503F, 26: 0x4451F0, 27: 0x44542D, 28: 0x445593,
    29: 0x445710, 30: 0x4458DF,
}

PICKERS = {0x41E6F2, 0x446AE8, 0x40D293, 0x44192A, 0x4018E7, 0x4413EC, 0x440BA8}


def main() -> None:
    img = R.Image()
    dis = R.Disassembler(img)
    dis.traverse()
    which = [int(x) for x in sys.argv[1:]] or sorted(CARDS)
    for cid in which:
        va = CARDS[cid]
        fn = dis.funcs.get(va)
        if fn is None:
            print(f"卡 {cid}: 0x{va:06x} 不在函数集")
            continue
        rm_idx = [i for i, x in enumerate(fn.insns) if x.is_call and x.target == 0x441343]
        print(f"\n{'='*76}\n卡 {cid}  0x{va:06x}  {len(fn.insns)} 条 / {fn.size} 字节  结尾 {fn.ends}")
        if not rm_idx:
            print("  ⚠️ 本函数体内无 remove_card（可能在子函数/弹窗流程里）")
        for i, x in enumerate(fn.insns):
            tags = []
            if x.is_call and x.target == 0x441343:
                tags.append("<<< remove_card")
            if x.is_call and x.target in PICKERS:
                tags.append(f"<<< picker 0x{x.target:x}")
            if x.is_jcc:
                tags.append("BR")
            if tags:
                phase = "POST" if rm_idx and i > rm_idx[0] else "PRE"
                print(f"  [{i:4d}] 0x{x.va:08x}  {x.mnemonic:<8} {x.op_str:<40} "
                      f"{phase if rm_idx else '----':<5} {' '.join(tags)}")


if __name__ == "__main__":
    main()
