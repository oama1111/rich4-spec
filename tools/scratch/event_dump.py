#!/usr/bin/env python3
"""新闻/命运事件取证转储器 —— 从 rich4.exe 实际反汇编。

只做机械抽取，不做任何推断：
  - 每个事件处理函数的完整反汇编（按分派表的地址序确定边界）
  - 指令里出现的所有 DGROUP 立即数：若可 Big5 解码则打印为字符串
  - 全局内存引用 [0xXXXXXX] 与玩家字段偏移注释
  - call 目标与已知符号名
用法:
  python3 tools/event_dump.py selftest      # 打印表与边界
  python3 tools/event_dump.py news  <N|all>
  python3 tools/event_dump.py fortune <N|all>
  python3 tools/event_dump.py func 0x44b6df 0x44b896
  python3 tools/event_dump.py data 0x475ed8 36 4
"""
import struct
import sys

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
except ImportError:
    sys.exit("需要 capstone")

EXE = "/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe"

# (名称, VA, 文件偏移, 大小)  ← 顺序无关，按 VA 查
SECTIONS = [
    ("AUTO",   0x401000,   1024, 394240),
    (".idata", 0x462000, 395264,   3584),
    ("DGROUP", 0x463000, 398848, 158720),
]

TABLES = {
    "news":    (0x475e24, 36),
    "fortune": (0x475ef0, 37),
}

# 分派表之后的第一个函数地址（末项上界）
AFTER = {
    "news":    0x44b6df,
    "fortune": 0x44d959,
}

PLAYER_BASE = 0x496b68
PLAYER_FIELDS = {
    0x00: "name_ptr", 0x04: "f04", 0x08: "xpos", 0x0a: "ypos",
    0x0c: "node_id", 0x0e: "last_node_id", 0x10: "direction",
    0x11: "traffic_method", 0x12: "ndices", 0x13: "character",
    0x14: "sex", 0x15: "who_plays", 0x1c: "cash",
    0x20: "money_in_bank", 0x24: "loan", 0x28: "special_finance",
    0x2c: "f44", 0x30: "points", 0x32: "days_in_hotel",
    0x33: "days_disappearing", 0x34: "days_in_prison",
    0x35: "days_in_hospital", 0x36: "days_sleeping",
    0x37: "days_sleep_walking", 0x38: "days_stopping",
    0x39: "days_tortoise_walking", 0x3b: "days_rejected_by_bank",
    0x3c: "bank_freeze_days", 0x3d: "allied_days", 0x3f: "god_info",
    0x40: "f64", 0x41: "allied_player",
    0x42: "total_winter_sleep_days", 0x44: "f44b", 0x46: "f46",
    0x4c: "hostility[0]", 0x50: "hostility[1]", 0x54: "hostility[2]",
    0x58: "hostility[3]", 0x5c: "monthly_paid", 0x60: "monthly_received",
}

# 已知全局符号（来自既有审计与 rich4-re 文档；★ 未在此表者一律以地址呈现）
GLOBALS = {
    0x496b30: "player_in_hospital_or_sleep?[4]",
    0x496b38: "in_hospital_flag[4]",
    0x496b60: "player_in_prison?[4]",
    0x496b68: "player_info[4] base",
    0x497158: "rich4_config",
    0x4971a0: "?",
    0x497328: "price_history? ",
    0x498e7c: "on_map_commercial_ptr",
    0x498e80: "map_node_ptr",
    0x498e84: "land_info_ptr",
    0x498e88: "facility_info_ptr",
    0x498e8c: "num_facilities",
    0x498e90: "num_on_map_commercials",
    0x498e98: "num_lands",
    0x499090: "news_order[36]",
    0x4990b4: "fortune_cur_idx",
    0x4990b8: "fortune_order[36]",
    0x4990dc: "stock_rest_days",
    0x4990e0: "news_cur_idx",
    0x4990e4: "?",
    0x4990e8: "price_index",
    0x4990ec: "?",
    0x4990f0: "?",
    0x499100: "?",
    0x499104: "?",
    0x499108: "?",
    0x49910c: "current_player",
    0x499110: "?",
    0x499114: "num_players",
    0x499118: "?",
    0x49911c: "?",
    0x4991b6: "uint16 ?",
    0x4991b8: "uint16 ?",
    0x48c5ac: "g_event_panel_surface",
    0x48c5b8: "?",
    0x48c5e0: "g_fortune_surface",
    0x48c5e4: "?",
    0x48c5e8: "?",
    0x48c5ec: "?",
    0x48c5f0: "?",
    0x48c5f4: "?",
    0x48c5f8: "?",
    0x475eb4: "news_pic_group[36]",
    0x475ed8: "news_title_ptr[36]",
    0x475fb4: "fortune_pic_group[37]",
    0x476018: "fortune_title_ptr?[37]",
}

CALLS = {
    0x456f2d: "rand()",
    0x457110: "sprintf",
    0x458370: "strcmp",
    0x4582fc: "strcpy",
    0x41d2c6: "pay_money",
    0x41d3f4: "?money2",
    0x41d476: "update_player_info_window",
    0x44ef41: "player_say",
    0x450441: "read_mkf",
    0x44f9d8: "create_font",
    0x44fabc: "draw_text",
    0x456280: "draw_graph?",
    0x456e11: "free_graph?",
    0x4563f5: "refresh_screen?",
    0x456f60: "?",
    0x448be2: "check_news(可行性判定)",
    0x44b6df: "news_events",
    0x44db81: "fortune_events",
    0x44bb4b: "?(fortune helper)",
    0x44b896: "?(news helper)",
    0x44d959: "?(after fortune table)",
    0x40d375: "?",
    0x40fa61: "?",
    0x440ba8: "?",
    0x440cac: "player_say2?",
    0x41906a: "?",
    0x409b18: "?",
    0x40a4e1: "?",
    0x40ab4a: "?",
    0x40ac7b: "?",
    0x40af12: "?",
    0x40cd07: "?",
    0x40dffa: "?",
    0x40df69: "update_hostility",
    0x40cc1a: "break_alliance",
    0x43d304: "?",
    0x43e9a4: "?",
    0x4315cc: "?",
    0x436b0a: "?",
    0x433b7e: "sell_stock?",
    0x4192a0: "?",
    0x4192e0: "?",
    0x419319: "?",
    0x4192f1: "?",
    0x4194b0: "?",
    0x4194e9: "?",
    0x4192a9: "?",
    0x4192b8: "?",
    0x415215: "?",
    0x4154dc: "?",
    0x4155fc: "?",
    0x440cda: "?",
    0x44101d: "?",
    0x4420d8: "card1",
    0x419800: "?",
    0x419a60: "?",
    0x41a1a0: "?",
    0x41a050: "?",
    0x41a168: "?",
    0x41b2a3: "?",
    0x41b42d: "?",
    0x44baea: "?",
    0x44ba63: "?",
    0x44f354: "?",
    0x44f42d: "?",
    0x44f567: "?",
    0x451985: "auction?",
    0x451a5a: "allocate_graph_st",
    0x4542ce: "print_message?",
    0x4544f6: "sleep_ms",
    0x4563f5: "?",
    0x4569a0: "?",
    0x456c0a: "?",
    0x4562a5: "draw_graph_dyn?",
    0x456e11: "free_graph",
    0x456f2d: "rand",
    0x44f354: "?",
    0x4192a0: "?",
    0x4195a0: "?",
}

KNOWN_STRINGS = {}


def load():
    with open(EXE, "rb") as f:
        return f.read()


def va_to_off(va):
    for _, sva, off, size in SECTIONS:
        if sva <= va < sva + size:
            return off + (va - sva)
    return None


def section_of(va):
    for name, sva, _, size in SECTIONS:
        if sva <= va < sva + size:
            return name
    return None


def cstr(data, va, maxlen=200):
    off = va_to_off(va)
    if off is None:
        return None
    end = data.find(b"\0", off, off + maxlen)
    if end < 0:
        return None
    raw = data[off:end]
    if not raw:
        return ""
    # 只接受可 Big5 解码且含可见字符的串
    for enc in ("big5", "cp950"):
        try:
            s = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if all(ch.isprintable() or ch in "\r\n\t" for ch in s):
            return s
    return None


def describe_mem(op):
    import re
    out = []
    for m in re.finditer(r"\[([^\]]*)\]", op):
        inner = m.group(1)
        for a in re.finditer(r"0x([0-9a-f]{5,8})", inner):
            addr = int(a.group(1), 16)
            if PLAYER_BASE <= addr < PLAYER_BASE + 4 * 0x68:
                base = PLAYER_BASE + ((addr - PLAYER_BASE) // 0x68) * 0x68
                off = addr - base
                pid = (addr - PLAYER_BASE) // 0x68
                nm = PLAYER_FIELDS.get(off, f"+0x{off:02x}")
                out.append(f"player[{pid}].{nm}")
            elif addr in GLOBALS:
                out.append(GLOBALS[addr])
            elif 0x463000 <= addr < 0x48a000:
                out.append(f"g_0x{addr:x}")
    return out


def disasm_range(va, end=None, count=None):
    data = load()
    off = va_to_off(va)
    if off is None:
        sys.exit(f"VA 0x{va:x} 越界")
    n = (end - va) if end else (count or 80) * 8 + 64
    code = data[off: off + n]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    return list(md.disasm(code, va))


def fmt_insn(data, ins):
    extra = []
    op = ins.op_str
    # 立即数 → 字符串 / 全局
    import re
    for m in re.finditer(r"(?<![\w\]])(0x[0-9a-f]{5,8})(?![\w\]])", op):
        addr = int(m.group(1), 16)
        if 0x463000 <= addr < 0x48a000:
            s = cstr(data, addr)
            if s:
                extra.append(f"→ \"{s}\"")
            elif addr in GLOBALS:
                extra.append(f"→ {GLOBALS[addr]}")
    mem = describe_mem(op)
    for x in mem:
        extra.append(f"→ {x}")
    if ins.mnemonic == "call" and op.startswith("0x"):
        t = int(op, 16)
        if t in CALLS:
            extra.append(f"→ {CALLS[t]}")
    tail = ("   ; " + " | ".join(extra)) if extra else ""
    return f"  {ins.address:08x}  {ins.mnemonic:<8} {op}{tail}"


def dump_func(va, end):
    data = load()
    print(f"# VA 0x{va:08x} .. 0x{end:08x}  ({end - va} 字节)  节 {section_of(va)}")
    for ins in disasm_range(va, end=end):
        if ins.address >= end:
            break
        print(fmt_insn(data, ins))


def table_entries(name):
    data = load()
    tva, n = TABLES[name]
    off = va_to_off(tva)
    return [struct.unpack_from("<I", data, off + i * 4)[0] for i in range(n)]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    data = load()
    if cmd == "selftest":
        for name in ("news", "fortune"):
            ents = table_entries(name)
            print(f"# {name} 表 {TABLES[name][0]:#x} × {len(ents)}，末项上界 0x{AFTER[name]:x}")
            for i, e in enumerate(ents):
                end = ents[i + 1] if i + 1 < len(ents) else AFTER[name]
                print(f"  [{i:>2}] 0x{e:08x} .. 0x{end:08x}  {end - e:5d} 字节")
    elif cmd in ("news", "fortune"):
        which = sys.argv[2]
        ents = table_entries(cmd)
        idxs = range(len(ents)) if which == "all" else [int(which, 0)]
        for i in idxs:
            end = ents[i + 1] if i + 1 < len(ents) else AFTER[cmd]
            print(f"\n===== {cmd}[{i}]  0x{ents[i]:08x} =====")
            dump_func(ents[i], end)
    elif cmd == "func":
        a = int(sys.argv[2], 0)
        b = int(sys.argv[3], 0)
        dump_func(a, b)
    elif cmd == "data":
        va = int(sys.argv[2], 0)
        cnt = int(sys.argv[3])
        w = int(sys.argv[4], 0)
        off = va_to_off(va)
        for i in range(cnt):
            v = struct.unpack_from({1: "<B", 2: "<H", 4: "<I"}[w], data, off + i * w)[0]
            s = cstr(data, v) if (w == 4 and 0x463000 <= v < 0x48a000) else None
            print(f"  [{i:>2}] 0x{v:08x} {v:>10d}" + (f'  "{s}"' if s else ""))
    elif cmd == "str":
        va = int(sys.argv[2], 0)
        print(cstr(data, va))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
