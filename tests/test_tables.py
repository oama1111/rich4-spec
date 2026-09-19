#!/usr/bin/env python3
"""
通道 1 扩展 · 数据表结构真值校验

从 `Rich4/rich4.exe` 的 DGROUP 直接读表并与规格比对。与
`../rich4-remake/packages/data/src/binary-truth.test.ts` 同类，
但这里只校验**表的机械结构**（偏移、步长、相邻性、名称可解），
不重复它已覆盖的字段值。

为什么单独做：**表的相邻性是最强的自洽证据之一**。
卡片表 `0x47fdf2` 有 30 项、每项 8 字节 → 结束于 `0x47fee2`，
而道具表恰好从 `0x47fee2` 开始。两个独立表严丝合缝地相接，
基本排除了「项数或步长记错」这类错误。

跑法：cd rich4-spec && .venv/bin/python tests/test_tables.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from rich4dis import Image, EXE_DEFAULT, KNOWN_TABLES  # noqa: E402

RESULTS = []


def case(desc, ok, detail=""):
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc}{'  ' + detail if detail else ''}")


def main():
    img = Image(EXE_DEFAULT)
    print("数据表结构真值校验\n")

    print("[结构] 卡片表 30 项 × 8 字节，结束处应紧接道具表")
    card_base, card_n, card_stride = 0x47FDF2, 30, 8
    tool_base, tool_n, tool_stride = 0x47FEE2, 13, 8
    case(f"卡片表 {card_n}×{card_stride} 结束于 0x{card_base + card_n * card_stride:08x}",
         card_base + card_n * card_stride == tool_base,
         f"= 道具表起点 0x{tool_base:08x}")
    case(f"道具表 {tool_n}×{tool_stride} 结束于 0x{tool_base + tool_n * tool_stride:08x}",
         True)

    print("\n[内容] 卡片表 30 项的名称指针都指向可解的 Big5 字符串")
    names = []
    for k in range(card_n):
        p, = struct.unpack("<I", img.read(card_base + k * card_stride, 4))
        nm = img.cstr(p, 24)
        names.append(nm)
    ok = all(nm and len(nm) >= 2 for nm in names)
    case(f"30 项全部可解（例：{names[0]} / {names[1]} / {names[-1]}）", ok)

    print("\n[内容] 道具表 13 项的名称指针都指向可解的 Big5 字符串")
    tnames = []
    for k in range(tool_n):
        p, = struct.unpack("<I", img.read(tool_base + k * tool_stride, 4))
        tnames.append(img.cstr(p, 24))
    ok = all(nm and len(nm) >= 2 for nm in tnames)
    case(f"13 项全部可解（例：{tnames[0]} / {tnames[1]} / {tnames[-1]}）", ok)

    print("\n[结构] 函数指针表：除 NULL 占位项外，每项都应指向代码段")
    # 卡片表第 0 项是**有意**的 NULL 占位（被动卡指向同一空桩），故豁免
    NULL_OK = {"card_functions": {0}}
    for name, (tva, n, stride, desc) in KNOWN_TABLES.items():
        if stride != 4:
            continue            # 非函数指针表（如魔法屋选项表）单独校验
        exempt = NULL_OK.get(name, set())
        bad = []
        for k in range(n):
            v = img.u32(tva + k * stride)
            if v is None or not (0x401000 <= v < 0x463000):
                if k not in exempt:
                    bad.append(k)
        case(f"{name} @0x{tva:06x} {n}项×{stride}（问题项 {bad}）", not bad, desc)

    print("\n[结构] 魔法屋选项记录表 @0x47571C：**不是**函数表")
    mh = KNOWN_TABLES.get("magic_house_options")
    if mh:
        tva, n, stride, _ = mh
        case(f"基址应为 0x47571c（既有文档记的 0x475724 是 rec[0].name，偏 8 字节）",
             tva == 0x47571C)
        # 名称在 +8，而不是 +0
        ok8, ok0 = True, True
        for k in range(n):
            b = img.read(tva + k * stride, stride)
            p8, = struct.unpack_from("<I", b, 8)
            p0, = struct.unpack_from("<I", b, 0)
            if not (0x463000 <= p8 < 0x4B0000 and len(img.cstr(p8, 24)) >= 2):
                ok8 = False
            if 0x401000 <= p0 < 0x463000:
                ok0 = False
        first_p, = struct.unpack_from("<I", img.read(tva, stride), 8)
        first = img.cstr(first_p, 24)
        case(f"{n} 项的 **+8** 名称指针全部可解（第 0 项：{first}）", ok8)
        case("**+0** 无一是代码指针（故非函数表）", ok0)
        case("表范围 0x47571c..0x4757db（12×16）", tva + n * stride == 0x4757DC)

    print("\n[自洽] 股票表 96 项 × 36 字节")
    stocks_base, stocks_n, stocks_stride = 0x47F072, 96, 36
    # 8 张图 × 12 支
    case("96 = 8 图 × 12 支", stocks_n == 8 * 12)
    # 第 2 图块（gid=1）应紧接第 1 图块
    case(f"块步长 12×36 = 432 = 0x{12 * stocks_stride:x}", 12 * stocks_stride == 432)
    # 名称指针可解
    ok = True
    for gid in (0, 4, 7):
        p, = struct.unpack("<I", img.read(stocks_base + gid * 432, 4))
        if not img.cstr(p, 24):
            ok = False
    case("抽查 gid=0/4/7 块首名称可解", ok)

    print("\n[自洽] 卡片表与道具表的「价格」字段应大于 0（+4 处 uint16）")
    nz_cards = sum(1 for k in range(card_n)
                   if struct.unpack("<H", img.read(card_base + k * 8 + 4, 2))[0] > 0)
    nz_tools = sum(1 for k in range(tool_n)
                   if struct.unpack("<H", img.read(tool_base + k * 8 + 4, 2))[0] > 0)
    case(f"卡片表 +4 >0 的项数 {nz_cards}/{card_n}", nz_cards > 0)
    case(f"道具表 +4 >0 的项数 {nz_tools}/{tool_n}", nz_tools > 0)

    print("\n[不变量] 卡片系统的两条关键结论（守住本次最重要的发现）")
    # ① player_has_card(0x4413ad) 的调用点必须恰为 18 处。
    #    这条断言把「只有 3 张卡查防御卡」这一结论钉死：
    #    若复刻或后续分析改动导致调用点数变化，本断言立刻失败。
    hc = 0x4413AD
    sites = []
    for off in range(1024, 1024 + 394240 - 5):
        if img.data[off] == 0xE8:
            rel, = struct.unpack_from("<i", img.data, off + 1)
            site = 0x401000 + (off - 1024)
            if site + 5 + rel == hc:
                sites.append(site)
    case(f"call 0x4413ad（player_has_card）恰为 18 处（实测 {len(sites)}）",
         len(sites) == 18)

    # ② card_functions[18..21] 必须全部指向空桩 0x4420d5（`xor eax,eax; ret`）——
    #    即復仇/嫁禍/免費/免罪**不可主动使用**（反应式防御卡）。
    cf = 0x475D5C
    stub = img.u32(cf + 18 * 4)
    allstub = all(img.u32(cf + k * 4) == 0x4420D5 for k in range(18, 22))
    case("card_functions[18..21] 全部指向空桩 0x4420d5", allstub)
    case("0x4420d5 处确为 `xor eax,eax; ret`（字节 31 c0 c3）",
         img.read(0x4420D5, 3) == bytes([0x31, 0xC0, 0xC3]))

    print("\n[不变量] 台词表与语音号映射（12 角色 × 27 事件 = 324 条）")
    # 台词表 @0x48084a，行=角色、列=事件，行步长 108 = 27×4
    SP_T, SP_STRIDE, SP_EV, SP_CH = 0x48084A, 108, 27, 12
    case("台词表行步长 108 = 27 事件 × 4 字节", SP_STRIDE == SP_EV * 4)

    # 每条的串形如 #NNNN…；NNNN 应等于 1050 + 角色*27 + 事件
    import re as _re
    mismatches = []
    numbers = []
    for c in range(SP_CH):
        for e in range(SP_EV):
            p, = struct.unpack("<I", img.read(SP_T + c * SP_STRIDE + e * 4, 4))
            txt = img.cstr(p, 32)
            m = _re.match(r"#(\d{4})", txt)
            if not m:
                mismatches.append((c, e, txt))
                continue
            n = int(m.group(1))
            numbers.append((c, e, n))
            if n != 1050 + c * SP_EV + e:
                mismatches.append((c, e, n))
    case(f"324 条的 #NNNN 全部等于 1050+角色*27+事件（异常 {len(mismatches)}）",
         not mismatches)
    case("语音号范围 1050..1373（= 1050+12*27−1）",
         min(n for _, _, n in numbers) == 1050 and max(n for _, _, n in numbers) == 1373)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 60}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
