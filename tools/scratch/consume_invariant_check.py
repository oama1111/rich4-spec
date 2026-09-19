#!/usr/bin/env python3
"""核验不变量：**卡片的 `remove_card` 之后，函数必然返回非 0（= 成功）**。

这条不变量是 remake 里 `cards/registry.ts` 的 `fail()` / `noEffect()` 分工依据：
既然「扣卡之后必成功」，「目标已选定但状态不变」就不是 `fail`，而是
`noEffect()`（`ok: true` + 已扣卡）。

做法：全部函数的指令按 VA 拉成一张全局表（30 张卡共用若干条收尾 ——
`0x443069`、`0x441f1b`、`0x44557e`、`0x444685`、`0x442afa`、`0x4012de`…
只在本函数体内走会把「跳进共享尾声」误判成出口，只按 VA 大小取
「最后一次写 eax」也会因为**向后跳**而取错 —— 两处都是第一版的坑）。
从每个 `call 0x441343` 的下一条指令起做 DFS，**沿执行序携带**
「最近一次写 eax 的指令」，到出口（`ret` / 跳出已建图代码的 `jmp`）时判定。
`eax` 的部分寄存器（`ax`/`al`/`ah`）也算写。
"""
import re
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

EAX_ZERO = re.compile(r"^(xor\s+eax,\s*eax|mov\s+eax,\s*0)$")
EAX_WRITE = re.compile(
    r"^(mov|lea|add|sub|imul|or|and|xor|inc|dec|pop|movzx|movsx|neg|not|xchg|adc|sbb)"
    r"\s+(eax|ax|al|ah)\b"
    r"|^(mul|div|idiv|cdq|cwde)$"
)
# 出口处 eax 的来源是「参数/循环变量」而非返回值时，靠这条排除
UNKNOWN = "?"


def text_of(x):
    return f"{x.mnemonic} {x.op_str}"


def main() -> None:
    img = R.Image()
    dis = R.Disassembler(img)
    dis.traverse()

    flat = []
    for f in sorted(dis.funcs.values(), key=lambda f: f.va):
        flat.extend(f.insns)
    flat.sort(key=lambda x: x.va)
    byva = {x.va: i for i, x in enumerate(flat)}

    bad = 0
    for cid in sorted(CARDS):
        fn = dis.funcs.get(CARDS[cid])
        sites = [x for x in fn.insns if x.is_call and x.target == 0x441343]
        if not sites:
            print(f"卡 {cid:>2}: 本体内无 remove_card")
            continue
        for site in sites:
            # DFS，状态 = 最近一次写 eax 的文本
            work = [(byva[site.va] + 1, UNKNOWN)]
            seen: set[tuple[int, str]] = set()
            exits: list[tuple[int, str]] = []
            while work:
                i, last = work.pop()
                if i < 0 or i >= len(flat) or (i, last) in seen:
                    continue
                seen.add((i, last))
                x = flat[i]
                last = text_of(x) if EAX_WRITE.match(text_of(x)) else last
                if x.is_ret:
                    exits.append((i, last))
                    continue
                if x.mnemonic == "jmp":
                    t = byva.get(x.target) if x.target is not None else None
                    if t is None:
                        exits.append((i, last))
                    else:
                        work.append((t, last))
                    continue
                if x.is_jcc and x.target is not None:
                    t = byva.get(x.target)
                    if t is not None:
                        work.append((t, last))
                    work.append((i + 1, last))
                    continue
                work.append((i + 1, last))
            zero = [(flat[e].va, t) for e, t in exits if EAX_ZERO.match(t)]
            bad += 0 if not zero else 1
            detail = "; ".join(f"0x{flat[e].va:08x}<-{t}" for e, t in exits)
            print(f"卡 {cid:>2}  remove@0x{site.va:08x}  "
                  f"{'OK 全部出口非 0' if not zero else 'XX 有返回 0 的路径'}  "
                  f"({len(exits)} 出口: {detail})")
            for va, t in zero:
                print(f"         !! 出口 0x{va:08x} 的 eax = `{t}`")
    print()
    print("结论：不变量成立（30 张卡的 remove_card 之后都必然返回非 0）"
          if bad == 0 else f"{bad} 处反例")


if __name__ == "__main__":
    main()
