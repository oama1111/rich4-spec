#!/usr/bin/env python3
"""
rich4-spec · 机械层：rich4.exe 递归遍历反汇编器

为什么不沿用线性反汇编
----------------------
`rich4.exe` 的 `AUTO` 代码段里**夹杂着字符串与对齐数据**（实证：
入口点 0x45709c 是 `jmp 0x458ced`，紧随其后的 0x4570a1 起就是 "Time..."
之类的字符串）。从段首一路 `md.disasm` 会在数据处**失步**，
之后解码出的指令全是假的。

本工具改为 **递归遍历（recursive traversal）**：
  1. 从已知根出发（PE 入口点、段首启动桩、已内建的函数指针表）
  2. 遇到 `call rel32` / `jmp rel32` / `jcc rel32` 就把目标入队
  3. 遇到 `jmp dword [reg*4 + table]` 就解析跳表，把每个表项入队
  4. 最后做一遍**未访问字节中的 call 目标补扫**，收口只被间接调用的函数

与 `rich4-remake/tools/disasm.py` 的关系
----------------------------------------
那个工具是**按需裁决**（`va` / `callers` / `xref` / `scan`），
每条查询独立对齐、不受失步影响 —— 方法正确，本工具保留其结论。
本工具是**全量建图**，产出函数清单 / 调用图 / xref 表，供后续语义层使用。
两者是互补关系，不是替代关系。

真值声明
--------
唯一真值是 `Rich4/rich4.exe` 本身。本工具的一切输出都必须能被
`VA → 文件字节` 复核。凡本工具的**推断**（函数边界、函数名）都标 inferred。

用法
----
    python3 tools/rich4dis.py info                  段信息 + 根清单
    python3 tools/rich4dis.py func 0x0045709c       反汇编一个函数
    python3 tools/rich4dis.py boundaries            校验函数边界与覆盖
    python3 tools/rich4dis.py build                 全量建图 → gen/*.json
"""
from __future__ import annotations

import json
import os
import struct
import sys
from dataclasses import dataclass, field, asdict

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
except ImportError:
    sys.exit("需要 capstone: python3 -m pip install capstone")

# ─────────────────────────── PE 常量（实测自 PE 头，勿凭记忆修改） ───────────────────────────

EXE_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Rich4", "rich4.exe",
)

IMAGE_BASE = 0x400000

SECTIONS = {
    # name: (VA, raw_off, raw_size, is_writable, is_executable)
    "AUTO":    (0x401000, 1024,    394240, False, True),
    ".idata":  (0x462000, 395264,  3584,  False, False),
    "DGROUP":  (0x463000, 398848, 158720, True,  False),
    ".bss":    (0x48a000, None,    64512, True,  False),   # 未初始化，文件中无对应字节
    ".reloc":  (0x49a000, 557568,  41984, False, False),
    ".rsrc":   (0x4a5000, 599552,   2560, False, False),
}

CODE_VA, CODE_OFF, CODE_SIZE = SECTIONS["AUTO"][0], SECTIONS["AUTO"][1], SECTIONS["AUTO"][2]
CODE_END = CODE_VA + CODE_SIZE

# 可写数据区（DGROUP + .bss）—— 全局变量与结构体所在
WRITABLE_RANGES = [
    (0x463000, 0x463000 + 158720),   # DGROUP
    (0x48a000, 0x48a000 + 64512),    # .bss
]
# 只读数据区（含跳表、常量表、字符串）
RODATA_RANGES = [
    (0x463000, 0x463000 + 158720),   # DGROUP 同时含初始化数据与跳表
]


def in_ranges(va: int, ranges) -> bool:
    return any(lo <= va < hi for lo, hi in ranges)


def is_code_ptr(v: int) -> bool:
    return CODE_VA <= v < CODE_END


def is_data_ptr(v: int) -> bool:
    return in_ranges(v, WRITABLE_RANGES)


class Image:
    """原始 PE 字节 + VA 换算。绝不改写二进制。"""

    def __init__(self, path: str = EXE_DEFAULT):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        self._verify_pe()

    # ⚠️ 该 PE 的节表 VirtualSize 全为 0（老 Watcom 链接器特征），
    #    必须用 SizeOfRawData 做换算，否则所有地址解析都会失败。
    def _verify_pe(self):
        d = self.data
        if d[:2] != b"MZ":
            raise SystemExit("不是 PE 文件")
        e = struct.unpack_from("<I", d, 0x3C)[0]
        if d[e:e + 4] != b"PE\0\0":
            raise SystemExit("PE 签名不匹配")
        nsec = struct.unpack_from("<H", d, e + 6)[0]
        opt = e + 24
        base = struct.unpack_from("<I", d, opt + 28)[0]
        if base != IMAGE_BASE:
            print(f"⚠️ ImageBase 实测 0x{base:x}，常量写的是 0x{IMAGE_BASE:x}，请更正", file=sys.stderr)
        self.entry = struct.unpack_from("<I", d, opt + 16)[0]
        self.sections = []
        so = opt + 224
        for i in range(nsec):
            o = so + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode("latin1")
            vs, va, rs, ro = struct.unpack_from("<IIII", d, o + 8)
            chars = struct.unpack_from("<I", d, o + 36)[0]
            self.sections.append({
                "name": name, "va": base + va, "vsize": vs,
                "raw_off": ro, "raw_size": rs, "chars": chars,
                "writable": bool(chars & 0x80000000),
                "executable": bool(chars & 0x20000000),
                "present": ro != 0,
            })
        self.image_base = base

    def va_to_off(self, va: int):
        """VA → 文件偏移。用 SizeOfRawData（见上）。"""
        for s in self.sections:
            if s["present"] and s["va"] <= va < s["va"] + s["raw_size"]:
                return s["raw_off"] + (va - s["va"])
        return None

    def off_to_va(self, off: int):
        for s in self.sections:
            if s["present"] and s["raw_off"] <= off < s["raw_off"] + s["raw_size"]:
                return s["va"] + (off - s["raw_off"])
        return None

    def read(self, va: int, n: int) -> bytes:
        """读 VA 处 n 字节；跨节或越界返回 b''。"""
        off = self.va_to_off(va)
        if off is None:
            return b""
        return self.data[off:off + n]

    def u32(self, va: int):
        b = self.read(va, 4)
        return struct.unpack("<I", b)[0] if len(b) == 4 else None

    def cstr(self, va: int, maxlen: int = 512) -> str:
        """读 C 字符串。原版是 Big5 繁体中文，按 big5 → cp950 尝试。"""
        off = self.va_to_off(va)
        if off is None:
            return ""
        end = self.data.find(b"\0", off, off + maxlen)
        raw = self.data[off:end if end >= 0 else off + maxlen]
        for enc in ("big5", "cp950", "latin1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.hex()

    def section_of(self, va: int):
        for s in self.sections:
            if s["va"] <= va < s["va"] + max(s["raw_size"], s["vsize"]):
                return s["name"]
        return None


# ─────────────────────────── 函数指针表（已知根，来自 rich4-remake 的既成结论） ───────────────────────────

KNOWN_TABLES = {
    "card_functions":        (0x475D5C, 31, 4, "卡片效果函数表（第 0 项 NULL 占位）"),
    "events_calls_table":    (0x475E24, 36, 4, "新闻事件分派表"),
    "fortune_call_table":    (0x475EF0, 37, 4, "命运事件分派表"),
    # ⚠️ 这张表**不是函数表**，而是魔法屋的选项记录表。已修正过两次，记法如下：
    #    记录基址 **0x47571C**、12 项 × 16 字节、布局：
    #      +0  int32 图标 x      +4  int32 图标 y
    #      +8  char* 选项名      +0xC int32 **全档无读取者（死数据）**
    #    既有文档把它记成「0x475724 处的 12 项函数表」：基址偏了 8 字节
    #    （0x475724 其实是 rec[0] 的 name 字段），且它不是函数表。
    #    用正确基址后 12 项的名称全部可解（變賣所有卡片 … 拍賣當格土地）。
    "magic_house_options": (0x47571C, 12, 16, "魔法屋选项记录表：图标x/y + 名称指针 + 死字段"),
}


# ── 内存操作数读/写分类表（缺陷 5 的修法依据）────────────────────────────────
# 为什么需要：Capstone 只给助记符与操作数，不说"这条指令写不写内存"。
# 只看"operands[0] 是不是内存"会把 `cmp`/`test`/`fild` 这类**只读**指令
# 误判成 writer，污染 gen/xrefs.json 与一切基于它的语义结论。
# 下面三个集合是**保守**的：不在集合里的助记符维持旧行为（判为写），
# 因此这个修复只会**减少误报**，不会引入新的"该写却没记"。
# 孤儿收容时，一个“函数”至少要有几条指令（单条 int3/ret 不算）
_MIN_ORPHAN_INSNS = 2

_MEM_READONLY = {
    # 比较/测试：不动目的操作数
    "cmp", "test", "bt",
    # 传址类
    "push", "call", "jmp", "lea",
    # x87 装载与算术（内存操作数是被**读**的）
    "fld", "fild", "fadd", "faddp", "fsub", "fsubr", "fsubp", "fsubrp",
    "fmul", "fmulp", "fdiv", "fdivr", "fdivp", "fdivrp",
    "fcom", "fcomp", "fcompp", "fucom", "fucomp", "fucompp",
    "ficom", "ficomp", "fiadd", "fisub", "fisubr", "fimul", "fidiv", "fidivr",
    "fldcw", "fldenv", "frstor",
    # 其它只读
    "nop", "prefetch", "prefetchnta", "prefetcht0", "prefetcht1", "prefetcht2",
}
# 单操作数形式才只读的（两操作数形式 operands[0] 是寄存器，不受影响）
_MEM_READONLY_UNARY = {"imul", "mul", "idiv", "div", "inc", "dec", "neg", "not"}
# 读-改-写：既是 reader 也是 writer
_MEM_RMW = {
    "add", "sub", "adc", "sbb", "and", "or", "xor",
    "inc", "dec", "neg", "not", "xchg",
    "shl", "shr", "sar", "rol", "ror", "rcl", "rcr",
    "bts", "btr", "btc",
}


@dataclass
class Insn:
    va: int
    size: int
    mnemonic: str
    op_str: str
    target: int | None = None        # 直接跳转/调用目标
    mem_addr: int | None = None      # 内存操作数的绝对地址（若有）
    # ★ 立即数形式的**数据地址**（`push 0x4630f4` 这类）。
    #   字符串与部分表是用立即数传址的，只记内存操作数会漏掉它们 ——
    #   实测漏掉后「被引用的字符串」只有 49 条（实际应上千）。
    imm_data: int | None = None
    indirect_table: int | None = None  # 跳表基址（若有）
    is_call: bool = False
    is_ret: bool = False
    is_jcc: bool = False


@dataclass
class Func:
    va: int
    insns: list = field(default_factory=list)
    ends: str = "unknown"            # ret / jmp / fallthrough / unknown
    callers: set = field(default_factory=set)
    callees: set = field(default_factory=set)
    # 读/写的绝对数据地址
    reads: set = field(default_factory=set)
    writes: set = field(default_factory=set)
    # 解码期间**局部**认领的指令边界；函数确认有效后才并入 owner
    _claimed: set = field(default_factory=set, repr=False)

    @property
    def size(self) -> int:
        return sum(i.size for i in self.insns)


class Disassembler:
    def __init__(self, img: Image):
        self.img = img
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        self.md = md
        self.funcs: dict[int, Func] = {}
        # 指令归属：VA → 所在函数入口
        self.owner: dict[int, int] = {}
        # ★ 字节级覆盖集：**每条指令覆盖的全部字节**（不只是起始地址）。
        #   为什么必需：`owner` 只记起始地址，于是"某地址不在 owner 里"
        #   并不等于"它不在任何指令内" —— 指令**中间**的地址会被误判为"自由"，
        #   孤儿收容就在那里造出**幻影函数**。
        #   实测：0x41abe6 落在 0x41abe5 那条 `jmp rel32` 的操作数内部，
        #   被当成一个 20 条指令的"函数"。
        # ★ 字节 → 覆盖它的那条指令的**末尾**（不是指令起始）。
        #   这样孤儿收容遇到「已被占用」时可以**精确前进到占用者之后**，
        #   而不是放弃整段未覆盖区间（缺陷 6）。
        self.covered: dict[int, int] = {}
        self._visited_starts: set[int] = set()
        self.roots: dict[int, str] = {}
        self.stats = {"unreachable_call_targets": [], "jump_tables": {},
                      "rejected_speculative": [], "bad_jumptables": [],
                      "skipped_tables": [], "skipped_mid_insn": []}

    # ── 解码一个函数体，直到终止指令 / 撞上**其它**函数 / 越界 ──
    def decode_at(self, va: int, max_insns: int = 4000) -> Func:
        """从 va 解码一个函数体。

        ★ 两个易错点（初版都踩了，故在此写明）：
        1. **不要**在解码过程中把地址写进 `self.owner`。否则函数解码到自己的
           第二个基本块时会看到「该地址已被占用」而误判为 fallthrough，
           于是函数被切成碎片、边界大面积重叠（实测 1057 处冲突）。
           改为先记入 `fn._claimed`，待函数确认有效后由 traverse 合并。
        2. **`jcc` 的目标不是函数入口。** 它是同一函数内的分支目标，正常
           线性解码就会走到。把 jcc 目标当函数根，会把每个函数按分支
           裂成大量假函数（实测从 ~1000 虚增到 4256，覆盖率仅 16.7%）。
        """
        fn = Func(va=va)
        fn.insns, fn.ends, fn._claimed, fn.callees = self.decode_block(va, max_insns)
        return fn

    def decode_block(self, va: int, max_insns: int = 4000):
        """从 va 解码**一个基本块**，直到终止指令 / 撞上已确认函数 / 越界。

        返回 (insns, ends, claimed, callees)。这是唯一的解码实现，
        `decode_at` 与 `extend_by_branches` 都走它，避免两套逻辑漂移。
        """
        fn = Func(va=va)
        cur = va
        while cur < CODE_END and len(fn.insns) < max_insns:
            if cur != va and cur in self.owner:
                fn.ends = "fallthrough"     # 撞进**其它**已确认函数：边界在此结束
                break
            src_off = CODE_OFF + (cur - CODE_VA)
            chunk = self.img.data[src_off:src_off + 16]
            if len(chunk) < 2:
                fn.ends = "out_of_section"
                break
            got = list(self.md.disasm(chunk, cur, count=1))
            if not got:
                fn.ends = "bad_decode"
                break
            ins = got[0]
            i = self._mk_insn(ins)
            fn.insns.append(i)
            fn._claimed.add(cur)              # ★ 局部登记，确认有效后再并入 owner
            cur += ins.size

            # ★ 跳表必须在**任何 break 之前**读取。初版把这段放在 jmp 的 break
            #   之后，导致「以 jmp 结尾的跳表分派函数」永远读不到自己的跳表——
            #   switch 表正是这种形状（jmp dword [eax*4 + table] 是函数的最后一条
            #   指令），于是全部分支被判为不可达。这是覆盖率缺口的主要来源。
            if i.indirect_table is not None:
                self._read_jump_table(i.indirect_table, fn)

            m = ins.mnemonic
            if m == "ret" or m.startswith("ret"):
                fn.ends = "ret"
                break
            if m == "int3":
                fn.ends = "int3"
                break
            if m == "jmp":
                fn.ends = "jmp" if i.target is not None else "jmp_indirect"
                break
            if m == "call" and i.target is not None:
                fn.callees.add(i.target)
        return fn.insns, fn.ends, fn._claimed, fn.callees

    def extend_by_branches(self, entry: int, budget: int = 20000) -> int:
        """把 entry 这个函数**顺着条件跳转**补全其全部基本块。

        为什么必需：Watcom 把函数的不同分支块排布在函数体外围，
        `call` 目标只指向函数的第一个块。只解码第一块会导致覆盖率停在
        54.5%，剩下的大片真代码永远进不来（实测最大的漏块有 1994 字节）。

        安全约束：只解码**尚未被任何函数认领**的地址；每条新指令都要
        登记进 owner；总预算封顶，避免在数据上跑飞。
        """
        fn = self.funcs[entry]
        added = 0
        # ★ 必须同时跟 jcc 与 jmp 的目标。只跟 jcc 会漏掉函数内部的
        #   `jmp` 汇合点与循环回边 —— 实测过路费函数 0x419744 因 `je 0x4197a5`
        #   的另一分支未被解码，整个函数只显示出 33 条指令（实际约 70 条）。
        pending = [i.target for i in fn.insns
                   if (i.is_jcc or i.mnemonic == "jmp") and i.target is not None]
        seen = set()
        while pending and added < budget:
            t = pending.pop()
            if t in seen or not is_code_ptr(t) or t in self.owner:
                continue
            seen.add(t)
            insns, ends, claimed, _ = self.decode_block(t)
            if not insns or ends == "bad_decode":
                continue
            for i in insns:
                if i.va in self.owner:
                    continue
                self.owner[i.va] = entry
                fn.insns.append(i)
                added += 1
                if (i.is_jcc or i.mnemonic == "jmp") and i.target is not None \
                        and i.target not in self.owner:
                    pending.append(i.target)
        if added:
            fn.insns.sort(key=lambda i: i.va)
        return added

    def _looks_like_pointer_table(self, va: int, min_run: int = 3) -> bool:
        """va 处是否是「指向代码段的 dword 连续串」（即跳表/函数指针表）。

        用于孤儿收容前的把关 —— 表不是代码，不该建函数。
        """
        n = 0
        for k in range(8):
            v = self.img.u32(va + k * 4)
            if v is None or not is_code_ptr(v):
                break
            n += 1
        return n >= min_run

    def _absorb_orphan_branch_blocks(self) -> int:
        """★ 终检：把「其实只是某个函数的基本块」的孤儿并入它的真宿主。

        为什么必需：`extend_by_branches` 依赖处理顺序，某些 jcc 目标在被跟到
        之前就被别的函数认领了（或被判成表/孤儿），于是真函数的**分支块**被
        孤儿收容建成了独立"函数"。实测 `0x4198b9`（地产结算）被切成 5 块：
        `0x419a67`(63条) / `0x41a013`(89条) / `0x41a86b`(77条) /
        `0x41abe6`(20条) / `0x41ac8c`(17条)，全是它的 jcc 目标。
        按碎片去读逻辑会得出完全错误的结论 —— 这是必须修的正确性问题。

        判据（保守，只并**无歧义**的）：
          · 入口**不是**任何 call 的目标（是 call 目标 ⇒ 真函数）；
          · 入口被**恰好一个**其它函数的 **jcc**（条件跳转）指向。
        条件跳转**从不跨函数**，所以这一条是无歧义的。
        纯 `jmp` 引用的（可能是尾调用，也可能是共享尾块）静态无法判定，
        **不自动合并**，只登记进 stats["jmp_merge_candidates"] 交人判断。

        放在遍历末尾统一执行，**与处理顺序无关**。
        """
        call_targets: set[int] = set()
        branch_srcs: dict[int, set[int]] = {}
        branch_kinds: dict[int, set[str]] = {}
        for va, fn in self.funcs.items():
            for i in fn.insns:
                if i.is_call and i.target is not None:
                    call_targets.add(i.target)
                elif (i.is_jcc or i.mnemonic == "jmp") and i.target is not None:
                    branch_srcs.setdefault(i.target, set()).add(va)
                    branch_kinds.setdefault(i.target, set()).add(
                        "jcc" if i.is_jcc else "jmp")

        # ★ 跳表项**绝对不能**被归并：它们是**合法的备用入口**，
        #   实测踩坑：落点分派表 `0x4197e9` 的 [1] = `0x41b3d0`（"普通格"共同尾码）
        #   曾被归并进 `0x41a3be`，于是所有 `jmp 0x41b3d0` 的桩（如 type 16 的
        #   `0x41b3cb`）在 `decode_block` 走到 `0x41b3d0` 时撞上"已被认领"而
        #   拿不到干净终点，**整类桩函数消失**。
        table_entries: set[int] = set()
        for _t, _es in self.stats.get("jump_tables", {}).items():
            table_entries.update(_es)

        absorbed, jmp_cands = [], []
        for va in sorted(self.funcs):
            if va in call_targets or va in table_entries:
                continue
            srcs = branch_srcs.get(va)
            if not srcs or len(srcs) != 1:
                continue
            host = next(iter(srcs))
            if host not in self.funcs or host == va:
                continue
            if "jcc" not in branch_kinds.get(va, set()):
                jmp_cands.append((va, host, len(self.funcs[va].insns)))
                continue
            if va in self.roots and not self.roots[va].startswith("speculative"):
                continue
            hfn, ofn = self.funcs[host], self.funcs[va]
            for i in ofn.insns:
                if i.va in self.owner and self.owner[i.va] != va:
                    continue
                self.owner[i.va] = host
                hfn.insns.append(i)
            hfn.insns.sort(key=lambda i: i.va)
            # 宿主原为 fallthrough 而新并入的块有明确终点时，采用该终点
            if hfn.ends in ("fallthrough", "unknown"):
                hfn.ends = ofn.ends
            del self.funcs[va]
            absorbed.append((va, host, len(ofn.insns)))
        self.stats["absorbed_orphan_blocks"] = absorbed
        self.stats["jmp_merge_candidates"] = jmp_cands
        return len(absorbed)

    def _force_jump_table_entries(self) -> int:
        """★ 终检：**跳表项按定义就是代码入口**，必须作为函数存在。

        为什么必需：跳表是在**解码到那条 `jmp dword [reg*4 + table]` 时**才被读出来的，
        而那条指令所在的函数可能很晚才被发现（实测落点分派器 `0x41982d` 是
        **投机根**，到投机轮次才建）。彼时跳表项地址可能已被别的函数"认领"，
        于是**整批入口消失** —— 实测落点跳表 `0x4197e9` 的 17 项里
        曾有 **14 项**不是函数（`0x41b302`/`0x41b396`/`0x41b3b9`/`0x41b3cb` …），
        而它们正是 PRD 「落点类型」维度的骨架。

        这与"投机候选/孤儿"不同：跳表项有**明确证据**（表里的 dword 就指向它），
        不是猜出来的，所以可以直接补建。
        只补**完全未覆盖**的地址；已被别的函数覆盖的不动（避免切碎真函数）。
        """
        # ★ 判据只有一条：**该地址尚未被任何指令覆盖**。
        #   已被覆盖 ⇒ 它要么是某函数内部的基本块（switch 的 case），
        #   要么已被正确归属 ⇒ 不动它。
        #   （补建放在**归并终检之后**执行，因此"认领顺序"不再影响结果，
        #     也不会像早先那样把真函数的分支块抢走。）
        forced = []
        for tva, entries in self.stats.get("jump_tables", {}).items():
            for t in entries:
                if t in self.funcs or t in self.covered:
                    continue
                fn = self.decode_at(t)
                if not fn.insns:
                    self.stats.setdefault("jtable_entry_failed", []).append(t)
                    continue
                self.funcs[t] = fn
                for a in fn._claimed:
                    self.owner.setdefault(a, t)
                for i in fn.insns:
                    for k in range(i.size):
                        self.covered[i.va + k] = i.va + i.size
                self.roots.setdefault(t, f"jumptable 0x{tva:08x}")
                forced.append((t, tva, len(fn.insns)))
        self.stats["forced_jtable_entries"] = forced
        return len(forced)

    def _drop_mid_instruction_entries(self) -> int:
        """★ 终检：剔除「入口落在**别的函数**的指令字节内部」的幻影函数。

        为什么必需：`owner` 只记指令**起始地址**，而投机候选/孤儿收容可能在
        一条多字节指令的**中间**建函数（实测 `0x41abe6` 落在 `0x41abe5` 的
        `jmp rel32` 操作数内部，却被当成一个 20 条指令的"函数"）。
        这类"函数"的解码结果纯属巧合。放在遍历末尾统一清理，**与处理顺序无关**。
        """
        byte_owner: dict[int, int] = {}
        for va, fn in self.funcs.items():
            for ins in fn.insns:
                for k in range(ins.size):
                    byte_owner.setdefault(ins.va + k, va)
        dropped = []
        for va in list(self.funcs):
            o = byte_owner.get(va)
            if o is not None and o != va:
                dropped.append(va)
                del self.funcs[va]
        self.stats["dropped_mid_insn"] = dropped
        return len(dropped)

    def _dedupe(self):
        """同一地址被两个函数都记进 insns 时，只保留真正拥有它的那个。"""
        for va, fn in self.funcs.items():
            fn.insns = [i for i in fn.insns
                        if self.owner.get(i.va, va) == va]
            self.funcs[va] = fn

    def _mk_insn(self, ins) -> Insn:
        i = Insn(va=ins.address, size=ins.size, mnemonic=ins.mnemonic, op_str=ins.op_str)
        i.is_call = ins.mnemonic.startswith("call")
        i.is_ret = ins.mnemonic.startswith("ret")
        # 条件跳转：以 j 开头但不是 jmp。它的目标是**同一函数内的另一个基本块**，
        # 不是函数入口 —— 这一条是覆盖率从 54.5% 提上去的关键。
        i.is_jcc = ins.mnemonic.startswith("j") and ins.mnemonic != "jmp"
        for op in ins.operands:
            if op.type == X86_OP_IMM:
                v = op.imm & 0xFFFFFFFF
                # 立即数既可能是跳转目标，也可能是常数：只有当它是代码地址时才当目标
                if is_code_ptr(v):
                    i.target = v
                elif is_data_ptr(v) or in_ranges(v, RODATA_RANGES):
                    i.imm_data = v
            elif op.type == X86_OP_MEM and op.mem.base != X86_REG_RIP:
                # 绝对寻址：disp 本身就是地址（Watcom 用绝对寻址访问全局）
                d = op.mem.disp & 0xFFFFFFFF
                if is_code_ptr(d) or is_data_ptr(d) or in_ranges(d, RODATA_RANGES):
                    i.mem_addr = d
                # 跳表形态 [reg*4 + table]
                if op.mem.index != 0 and op.mem.scale in (1, 2, 4, 8):
                    if is_data_ptr(d) or in_ranges(d, RODATA_RANGES) or is_code_ptr(d):
                        i.indirect_table = d
        # 目的操作数是否写内存
        #
        # ★★ 缺陷 5（本轮修）：**不能只看「第一个操作数是内存」就判为写**。
        #   实测两类误判，都会污染 `gen/xrefs.json`，进而污染所有下游语义结论：
        #     · `cmp dword ptr [g], 0` / `test byte ptr [g], 0x30` —— 只读，不写
        #     · `fild dword ptr [g]` / `fmul dword ptr [g]` —— x87 装载/运算，只读
        #   而 `fistp dword ptr [g]` / `fstp` / `fst` 才是写。
        #   实例：`0x49908c`（开局资金）曾被列成「会被改写」，实际只有 `0x406de7`
        #   写它 —— 因为 `0x41d7d4`/`0x41d839` 的 `fild dword ptr [0x49908c]`
        #   被当成了 writer。这类误判会让「某字段开局后不变」这种结论无法成立。
        if ins.operands:
            ops = ins.operands
            d0 = ops[0]
            if d0.type == X86_OP_MEM and d0.mem.base != X86_REG_RIP:
                d = d0.mem.disp & 0xFFFFFFFF
                if is_data_ptr(d) or in_ranges(d, RODATA_RANGES):
                    mn = ins.mnemonic
                    if mn in _MEM_READONLY or (
                            len(ops) == 1 and mn in _MEM_READONLY_UNARY):
                        pass                      # 只读：不记 writes
                    elif mn in _MEM_RMW:
                        i._writes = d
                        i._mem_reads = d          # 读-改-写：两边都记
                    else:
                        i._writes = d             # 默认（含 mov [g],r / fstp [g]）
        return i

    def _read_jump_table(self, table_va: int, fn: Func):
        """跳表：[reg*4 + table] 形式。表项是 4 字节绝对代码地址。

        ★ 必须限上界：表后面紧接着别的数据，无界扫描会把相邻表项吞进来
          （实测 `fortune_call_table` 声明 37 项却被读成 49 项）。
          已知表用其声明项数封顶；未知表最多取 64 项并登记待人工确认。
        """
        if table_va in self.stats["jump_tables"]:
            return
        limit = 64
        declared = None
        for name, (tva, n, stride, _) in KNOWN_TABLES.items():
            if stride == 4 and table_va == tva:
                limit = n
                declared = n
                break

        # ★ 表可能在**代码段内部**（Watcom 常把 switch 跳表排在函数之后）。
        #   初版只处理数据段地址，把这些表直接漏掉 —— 实测 0x4197e9 的 17 项表
        #   就在代码段里，漏掉它会让对应 switch 的全部分支变成「不可达」，
        #   这是覆盖率缺口的主要来源之一。
        entries = []
        for k in range(limit):
            v = self.img.u32(table_va + k * 4)
            if v is None or not is_code_ptr(v):
                break
            # 拒绝自指与落在表自身字节范围内的项（那是把表当成数据误读）
            if table_va <= v < table_va + (k + 1) * 4:
                break
            entries.append(v)
        if not entries:
            return

        # ★ 合理性约束，压掉误报。必须按**表所在位置**分两类，不能用统一距离阈值：
        #   初版统一要求「表项距表 < 0x8000」，结果把数据段里的合法跳表全误杀
        #   （0x47539c 的表在 0x475xxx、表项在 0x401xxx，距离 0x74000）。
        #
        #   实测数据：形如 `[reg*4 + 0x499120]`（结构体数组下标）的误报都落在
        #   `.bss`（未初始化，内容为 0），因此「项数 ≥ 4」天然把它们挡掉。
        if declared is None:
            in_code = CODE_VA <= table_va < CODE_END
            span = max(entries) - min(entries)
            near = all(abs(e - table_va) < 0x8000 for e in entries)
            mono = all(entries[i] <= entries[i + 1] for i in range(len(entries) - 1))
            ok = len(entries) >= 4 and (
                (in_code and near)        # 代码段内嵌表：表项必然紧邻
                or (mono and span < 0x20000)   # 数据段表：单调且跨度合理
                or span < 0x8000
            )
            if not ok:
                self.stats["bad_jumptables"].append((table_va, len(entries)))
                return

        self.stats["jump_tables"].setdefault(table_va, entries)

    # ── 递归遍历建图 ──
    def traverse(self, verbose: bool = True, include_orphans: bool = False):
        img = self.img
        queue: list[tuple[int, str]] = []
        # 投机根（从数据里凑巧出现的 0xE8/0xE9 反推出来的目标）单独放，
        # 必须等**高置信根**全部处理完再验证，否则它们会抢占真实函数边界。
        speculative: list[tuple[int, str]] = []

        def seed(va, why, spec=False):
            if is_code_ptr(va) and va not in self.funcs:
                self.roots.setdefault(va, why)
                (speculative if spec else queue).append((va, why))

        # 根 1：PE 入口点
        seed(img.entry, "PE entry")
        # 根 2：段首（Watcom 启动桩；0x401000 是 int3; jmp $ 占位）
        seed(CODE_VA, "section head")
        # 根 3：已知函数指针表 —— 这是最可靠的根，不依赖调用图
        for name, (tva, n, stride, _) in KNOWN_TABLES.items():
            for k in range(n):
                v = img.u32(tva + k * stride)
                if v and is_code_ptr(v):
                    seed(v, f"table:{name}[{k}]")

        # 其余全部 call rel32 目标作为**投机根**，用于收口只被间接调用的函数
        for t in self._scan_rel32_targets():
            seed(t, "speculative:call-target", spec=True)

        # ★ 再补一类：**只作为立即数被引用的函数**（回调注册）。
        #   实测坑：`0x40257a` 是某个模态界面的消息处理器，它**从不被 call/jmp**，
        #   只以 `push 0x40257a` 的形式注册进 `0x48a010[depth]`。
        #   只扫 E8/E9 会整类漏掉这种"回调注册"，并因此让假函数（表）挤占它的位置。
        for t in self._scan_code_immediates():
            seed(t, "speculative:code-immediate", spec=True)

        processed = 0

        def drain(q, tag):
            nonlocal processed
            while q:
                va, why = q.pop(0)
                if va in self.funcs:
                    continue
                if va in self.owner or va in self.covered:
                    continue        # 已是某指令的起点或落在某指令内部，不是函数入口
                fn = self.decode_at(va)
                if not fn.insns:
                    continue
                # ★ 高置信根无条件接受；投机根要求「解码到明确终点」才算真函数
                if tag == "speculative" and fn.ends not in ("ret", "jmp", "jmp_indirect", "int3"):
                    self.stats["rejected_speculative"].append(
                        (va, fn.ends, len(fn.insns)))
                    continue
                self.funcs[va] = fn
                for a in fn._claimed:
                    self.owner.setdefault(a, va)
                for ins in fn.insns:
                    for k in range(ins.size):
                        self.covered[ins.va + k] = ins.va + ins.size
                processed += 1

                # ★★ 必须**立刻**补全本函数的分支块，再入队其它目标。
                #   否则 `jcc` 的目标会被当成新函数入队 —— 实测过路费函数
                #   0x419744 的 `je 0x4197a5` 让 0x4197a5 变成一个独立的
                #   16 条指令的「函数」，真函数被砍成 33 条。
                #   先把分支块认领掉，jcc 目标就已归属本函数，自然不会再入队。
                #   （区分标准：`call` 目标是函数；`jcc`/`jmp` 目标是本函数的基本块。）
                self.extend_by_branches(va)

                for i in fn.insns:
                    if i.is_call and i.target is not None and is_code_ptr(i.target):
                        if i.target not in self.funcs and i.target not in self.owner:
                            queue.append((i.target, f"from 0x{va:08x}"))
                    if i.indirect_table is not None:
                        for t in self.stats["jump_tables"].get(i.indirect_table, []):
                            if t not in self.funcs and t not in self.owner:
                                queue.append((t, f"jumptable 0x{i.indirect_table:08x}"))
                if verbose and processed % 200 == 0:
                    print(f"  …[{tag}] 已处理 {processed} 个函数，队列 {len(queue)}", file=sys.stderr)

        # ★ 顺序至关重要，这里踩过一个严重的坑：
        #   投机候选（从数据里凑巧的 E8/E9 反推出来的目标）里包含**真函数内部
        #   的分支块地址**。如果先让投机候选建函数，这些分支块就被它们占走，
        #   真函数被砍成碎片（实测过路费函数 0x419744 只剩 33 条指令，
        #   而 0x4197a5 / 0x4197d8 被误建成两个独立函数）。
        #
        #   正确顺序：先把**可达根**全解出来，**立刻**顺着分支把每个函数补完整，
        #   之后才处理投机候选 —— 此时分支块已归属真函数，投机候选自然落空。
        total_added = 0

        def extend_all():
            nonlocal total_added
            added = 0
            for entry in list(self.funcs):
                if entry in self.funcs:
                    added += self.extend_by_branches(entry)
            total_added += added
            return added

        drain(queue, "confident")
        extend_all()
        drain(speculative, "speculative")
        extend_all()
        self._dedupe()

        # 可选的「孤儿」收容：代码段里**没有任何指令指向**的区域。
        # 实测这类区域是 Watcom 链进来的未调用库函数与死代码，
        # 不影响 1:1 复刻（不可达逻辑不产生行为），但收进清单更完整。
        n_orphans = 0
        if include_orphans:
            # ★★ 缺陷 6（本轮修）：**起点解码失败就整段放弃**是错的。
            #   实测：`0x41bd45` 是**真代码**（`imul eax,ebx,0x68` …
            #   `mov ebp,[eax+0x480d92]`），却完全不在 `gen/db.txt` 里 ——
            #   因为它所在的那段未覆盖区间起点不是代码（是数据/半条指令），
            #   起点 `decode_block` 失败后**整段被跳过**，`0x41bd45` 就再没机会。
            #   全代码段有 **167 段 ≥16 字节的未覆盖区间（合计 28,979 字节）**，
            #   里面混着真代码与被嵌在代码段里的数据，必须逐字节向前重试。
            #
            #   安全约束（避免把数据解成指令而“跑飞”）：
            #     · 必须以**干净终点**收尾（ret / jmp / jmp_indirect / int3），
            #       否则说明解码跨进了数据；
            #     · 至少 `_MIN_ORPHAN_INSNS` 条指令（单条 `int3`/`ret` 不算函数）；
            #     · 起点必须不是“指针表”（见 `_looks_like_pointer_table`）；
            #     · 一条被接受后，从它的**结尾**继续扫，不在其内部再造函数。
            # ⚠️ 试过「逐字节向前重试」的版本，**已回退**：它虽然把覆盖率刷到 98.0%，
            #   却让真函数被孤儿抢走块 —— 实测 `0x4198b9`（地产结算）从
            #   **765 条 / 2,924 字节**掉回 **255 条 / 1,020 字节**。
            #   根因：代码段里夹着数据，逐字节扫描会在数据上"碰巧"解出以 ret/jmp
            #   收尾的假块，这些假块先占住地址，真函数的分支块就再也进不来。
            #   **覆盖率不是正确性指标** —— 宁可有 7% 未覆盖，也不能把真函数切碎。
            #
            #   `0x41bd45` 那一类漏点（真代码但整段未覆盖）改用下方
            #   「按引用定向补扫」处理：只从**有指令指向**的地址起扫，不做无据猜测。
            for rlo, rhi in sorted(self.uncovered_ranges(), key=lambda g: g[0]):
                lo = rlo
                # ⚠️ 这里**不做**"往前挪一点再试"的扫描，理由见上：
                #   实测两种激进版本都会把真函数切碎（`0x4198b9` 765→255 条）。
                #   落点桩那一类漏点改由 `_force_jump_table_entries()` 用
                #   「跳表项必是代码入口」这条**硬证据**补回，不靠猜。
                if lo in self.covered:
                    continue
                if self._looks_like_pointer_table(lo):
                    self.stats.setdefault("skipped_tables", []).append(lo)
                    continue
                insns, ends, claimed, _ = self.decode_block(lo)
                if not insns or ends == "bad_decode":
                    continue
                if ends not in ("ret", "jmp", "jmp_indirect", "int3"):
                    continue
                self.funcs[lo] = Func(va=lo, insns=insns, ends=ends)
                for a in claimed:
                    self.owner.setdefault(a, lo)
                for i2 in insns:
                    for k in range(i2.size):
                        self.covered[i2.va + k] = i2.va + i2.size
                n_orphans += 1
            # 孤儿收容后可能又暴露出新的分支目标（原先目标落在孤儿区内被判为已占用），
            # 因此必须再跑一轮分支补全 —— 漏这一步会让可达代码被误标为孤儿。
            extend_all()
            self._dedupe()
            if verbose:
                print(f"  孤儿收容：{n_orphans} 个入口（不可达库代码/死代码）", file=sys.stderr)
        # ★ 终检 1（与处理顺序无关）：把「其实是别的函数分支块」的孤儿并入宿主，
        #   再顺一次分支 —— 并入的块自身可能还带 jcc，必须继续跟。
        n_absorb = self._absorb_orphan_branch_blocks()
        if n_absorb:
            extend_all()
            self._dedupe()
        # ★ 终检 2：跳表项按定义就是代码入口，必须存在（有硬证据，见方法注释）。
        #   放在归并**之后**：此时归属已稳定，补建不会抢走任何真函数的分支块。
        n_forced = self._force_jump_table_entries()
        # ★ 终检 3（与处理顺序无关）：剔除入口落在别的函数指令字节内部的幻影函数
        n_drop = self._drop_mid_instruction_entries()
        if verbose:
            print(f"  分支块补全：新增 {total_added} 条指令", file=sys.stderr)
            print(f"  补建跳表项函数：{n_forced} 个", file=sys.stderr)
            print(f"  归并「实为分支块」的孤儿函数：{n_absorb} 个", file=sys.stderr)
            print(f"  剔除「入口在别的指令内部」的幻影函数：{n_drop} 个", file=sys.stderr)
            print(f"  遍历完成：{len(self.funcs)} 个函数，跳表 {len(self.stats['jump_tables'])} 个，"
                  f"驳回投机候选 {len(self.stats['rejected_speculative'])} 个", file=sys.stderr)
        self._finalize()

    def _scan_rel32_targets(self) -> set[int]:
        """扫全代码段的 E8/E9 rel32，收集代码段内的目标。

        ⚠️ 数据里凑巧的 0xE8 会带来误报。这里**不**把它们当作确定的函数，
        只是当作**待验证的候选根**；`decode_at` 会在数据处解码失败或跑飞，
        真函数会干净地以 ret/jmp 收尾。误报的代价是多跑一次解码。
        """
        data = self.img.data
        out: set[int] = set()
        for off in range(CODE_OFF, CODE_OFF + CODE_SIZE - 5):
            b = data[off]
            if b != 0xE8 and b != 0xE9:
                continue
            rel = struct.unpack_from("<i", data, off + 1)[0]
            site = CODE_VA + (off - CODE_OFF)
            t = site + 5 + rel
            if is_code_ptr(t):
                out.add(t)
        return out

    def _scan_code_immediates(self) -> set[int]:
        """扫 `push imm32` / `mov reg, imm32` 里指向代码段的立即数。

        这类值多半是**回调注册**（把函数地址当数据传）。它们从不被 call/jmp，
        所以 `_scan_rel32_targets` 找不到 —— 而它们往往正是"界面消息处理器"。

        ⚠️ 数据里凑巧的 `68`/`B8..BF` 会带来误报；与 E8 扫描同理，
        这些只作为**投机根**，`decode_block` 会在数据处解码失败或跑飞。
        """
        data = self.img.data
        out: set[int] = set()
        for off in range(CODE_OFF, CODE_OFF + CODE_SIZE - 5):
            b = data[off]
            if b == 0x68:                      # push imm32
                (v,) = struct.unpack_from("<I", data, off + 1)
            elif 0xB8 <= b <= 0xBF:            # mov r32, imm32
                (v,) = struct.unpack_from("<I", data, off + 1)
            else:
                continue
            if is_code_ptr(v):
                out.add(v)
        return out

    def _finalize(self):
        """把每条指令的读写归属到函数，并补全 callers。"""
        for va, fn in self.funcs.items():
            for i in fn.insns:
                mr = getattr(i, "_mem_reads", None)
                if mr is not None:
                    fn.reads.add(mr)          # 读-改-写指令的"读"那一半
                w = getattr(i, "_writes", None)
                if w is not None:
                    fn.writes.add(w)
                if i.mem_addr is not None and i.mem_addr != w:
                    fn.reads.add(i.mem_addr)
                if i.imm_data is not None and i.imm_data != w:
                    fn.reads.add(i.imm_data)
        for va, fn in self.funcs.items():
            for callee in fn.callees:
                if callee in self.funcs:
                    self.funcs[callee].callers.add(va)

    # ── 校验：函数边界互相不重叠 ──
    def boundary_conflicts(self):
        conflicts = []
        owner_count: dict[int, set] = {}
        for va, fn in self.funcs.items():
            for i in fn.insns:
                owner_count.setdefault(i.va, set()).add(va)
        for va, owners in owner_count.items():
            if len(owners) > 1:
                conflicts.append((va, sorted(owners)))
        return conflicts

    def code_coverage(self):
        """已解码的**指令字节数** / 代码段字节数。

        ⚠️ 初版这里返回 `len(self.owner)`（指令起始地址个数）当作字节数，
        导致覆盖率被报成 16.7%（实际 54.5%）。指令数与字节数不可混用。
        """
        covered = 0
        for va, fn in self.funcs.items():
            for i in fn.insns:
                if self.owner.get(i.va) == va:
                    covered += i.size
        return covered, CODE_SIZE

    def uncovered_ranges(self):
        """真实未覆盖区间：以**指令字节**为单位合并已解码区间。"""
        spans = []
        for va, fn in self.funcs.items():
            for i in fn.insns:
                if self.owner.get(i.va) == va:
                    spans.append((i.va, i.va + i.size))
        spans.sort()
        merged = []
        for lo, hi in spans:
            if merged and lo <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        gaps = []
        prev = CODE_VA
        for lo, hi in merged:
            if lo > prev:
                gaps.append((prev, lo))
            prev = max(prev, hi)
        if prev < CODE_END:
            gaps.append((prev, CODE_END))
        return gaps


# ─────────────────────────── 输出辅助 ───────────────────────────

def fmt_bytes(va: int) -> str:
    return f"0x{va:08x}"


def render_func(dis: Disassembler, va: int) -> str:
    fn = dis.funcs.get(va)
    if not fn:
        return f"# 0x{va:08x} 不在已建图函数集中\n"
    out = [f"# 函数 0x{va:08x}  指令 {len(fn.insns)}  字节 {fn.size}  结尾 {fn.ends}"]
    if fn.callers:
        out.append(f"# 被调用 {len(fn.callers)} 处: " + ", ".join(fmt_bytes(c) for c in sorted(fn.callers)[:12]))
    if fn.callees:
        out.append(f"# 调用 {len(fn.callees)} 个: " + ", ".join(fmt_bytes(c) for c in sorted(fn.callees)[:12]))
    out.append("")
    prev_end = None
    for i in fn.insns:
        # 标出基本块断点：上一条不是顺序相邻，说明这里是分支汇合点
        if prev_end is not None and i.va != prev_end:
            out.append(f"  {'':8}  ── 基本块 0x{i.va:08x} ──")
        mark = ""
        if i.target is not None and is_code_ptr(i.target):
            mark = f"   → {fmt_bytes(i.target)}"
        elif i.mem_addr is not None:
            mark = "   ← 全局"
        out.append(f"  {i.va:08x}  {i.mnemonic:<8} {i.op_str}{mark}")
        prev_end = i.va + i.size
    return "\n".join(out) + "\n"


def cmd_info(img: Image):
    print(f"文件: {img.path}")
    print(f"大小: {len(img.data)}")
    print(f"ImageBase: 0x{img.image_base:x}   PE 入口点: 0x{img.entry:08x}")
    print("\n节表:")
    for s in img.sections:
        flags = ("W" if s["writable"] else "-") + ("X" if s["executable"] else "-")
        print(f"  {s['name']:<9} VA 0x{s['va']:06x}  RawOff {s['raw_off']:<7} "
              f"RawSize {s['raw_size']:<7} {flags}  {'（文件中无字节）' if not s['present'] else ''}")
    print("\n已知根（函数指针表）:")
    for name, (tva, n, stride, desc) in KNOWN_TABLES.items():
        print(f"  {name:<24} VA 0x{tva:06x} × {n}  每项 {stride} 字节  {desc}")
        for k in range(n):
            v = img.u32(tva + k * stride)
            tag = "NULL" if not v else (fmt_bytes(v) if is_code_ptr(v) else f"0x{v:08x} ← 非代码")
            print(f"      [{k:>2}] {tag}")


def cmd_boundaries(dis: Disassembler):
    conflicts = dis.boundary_conflicts()
    covered, total = dis.code_coverage()
    print(f"函数数: {len(dis.funcs)}")
    print(f"代码覆盖: {covered} / {total} 字节 = {covered / total * 100:.1f}%")
    print(f"已识别跳表: {len(dis.stats['jump_tables'])}")
    for t, entries in sorted(dis.stats["jump_tables"].items()):
        print(f"  0x{t:08x}  {len(entries)} 项")
    print(f"\n边界重叠冲突: {len(conflicts)}")
    for va, owners in conflicts[:30]:
        print(f"  0x{va:08x} 被 {[fmt_bytes(o) for o in owners]} 同时认领")
    # 结尾类型统计
    from collections import Counter
    c = Counter(f.ends for f in dis.funcs.values())
    print("\n函数结尾类型分布:")
    for k, v in c.most_common():
        print(f"  {k:<16} {v}")


def cmd_tail(dis: Disassembler, top: int = 15):
    """对**剩余未覆盖区**给出精确归因，而不是含糊地写「未覆盖」。

    归因口径（每一条都可复核）：
      · 全 0x00 / 0xCC        → 对齐填充
      · 能干净解码到 ret/jmp  → 不可达代码（收容为孤儿函数）
      · 其余                  → 代码段中内嵌的**数据**（字符串 / 常量表 / 跳表）

    这一步的意义：规格的可信度取决于「已知边界是否被精确画出」。
    把剩余部分明确划为数据，好过留一句「约 23% 未解释」。
    """
    from collections import Counter
    img = dis.img
    gaps = dis.uncovered_ranges()
    pad = unreachable = data = 0
    data_like = []
    for lo, hi in sorted(gaps, key=lambda g: g[0]):
        b = img.read(lo, hi - lo)
        if not b:
            data += hi - lo
            continue
        if all(c in (0x00, 0xCC) for c in b):
            pad += hi - lo
            continue
        insns, ends, claimed, _ = dis.decode_block(lo)
        if insns and ends in ("ret", "jmp", "jmp_indirect", "int3"):
            unreachable += hi - lo
            continue
        data += hi - lo
        data_like.append((lo, hi))
    total = pad + unreachable + data
    print(f"剩余未覆盖 {total} 字节的归因：")
    print(f"  对齐填充（全 00/CC）      {pad:7d}  {pad / total * 100:5.1f}%")
    print(f"  不可达代码（可干净解码）  {unreachable:7d}  {unreachable / total * 100:5.1f}%")
    print(f"  代码段内嵌数据            {data:7d}  {data / total * 100:5.1f}%")
    print(f"\n最大的 {top} 个「内嵌数据」区间（多为字符串与常量表）:")
    for lo, hi in sorted(data_like, key=lambda g: -(g[1] - g[0]))[:top]:
        b = img.read(lo, min(32, hi - lo))
        printable = sum(1 for c in b if 32 <= c < 127 or c >= 0x80)
        tag = "  ← 像字符串" if printable >= len(b) * 0.75 else ""
        print(f"  0x{lo:08x}-0x{hi:08x} {hi - lo:7d} 字节  {b.hex(' ')}{tag}")



    """判断每个未覆盖区间「有没有指令指向它」。

    这是停止猜测、直接定性的工具：
      · 有 call 指向  → 我们漏了函数（遍历有 bug）
      · 只有 jmp/jcc 指向 → 尾调用或分支块，仍属漏解
      · **完全没人指向** → 原版里的死代码 / Watcom 库残留 / 错误处理路径，
                            不属于「可达逻辑」，规格里不必逐条覆盖
    """
    claims: dict[int, list] = {}
    for va, fn in dis.funcs.items():
        for i in fn.insns:
            if i.target is not None and is_code_ptr(i.target):
                claims.setdefault(i.target, []).append((i.va, i.mnemonic, va))
    gaps = sorted(dis.uncovered_ranges(), key=lambda g: -(g[1] - g[0]))[:top]
    for lo, hi in gaps:
        callers = []
        for a in range(lo, hi):
            callers.extend(claims.get(a, []))
        kinds = {}
        for _, mn, _ in callers:
            kinds[mn] = kinds.get(mn, 0) + 1
        verdict = "★ 有 call 指向 → 漏了函数" if any(m == "call" for _, m, _ in callers) else (
            "仅 jmp/jcc 指向 → 尾调用或分支块" if callers else
            "✗ 无任何指令指向 → 死代码 / 库残留，非可达逻辑")
        print(f"0x{lo:08x}-0x{hi:08x} {hi - lo:6d} 字节  {verdict}")
        if callers:
            print(f"    引用指令 {len(callers)} 处，助记符分布 {kinds}，例如 "
                  f"{[(hex(a), m) for a, m, _ in callers[:5]]}")


def cmd_gaps(dis: Disassembler, top: int = 20):
    """诊断：列出最大的未覆盖区间，判断是「数据」还是「漏掉的函数」。

    这是判断遍历质量的**关键体检**。覆盖率高不代表对，覆盖率低一定要查清
    是代码段真的含大量数据，还是遍历漏了整片函数。
    """
    img = dis.img
    gaps = dis.uncovered_ranges()
    gaps.sort(key=lambda g: -(g[1] - g[0]))
    total_uncovered = sum(h - l for l, h in gaps)
    covered, total = dis.code_coverage()
    print(f"函数 {len(dis.funcs)} 个，覆盖 {covered}/{total} 字节 = {covered / total * 100:.1f}%")
    print(f"未覆盖 {total_uncovered} 字节，分布在 {len(gaps)} 个区间")
    print(f"\n最大的 {top} 个未覆盖区间（尾随的 00 / CC 通常是对齐或 Watcom 填充）:")
    for lo, hi in gaps[:top]:
        b = img.read(lo, 24)
        zeros = b.count(0)
        tag = ""
        if b and b[0] == 0xCC:
            tag = "  ← int3 对齐填充"
        elif zeros >= len(b) - 2:
            tag = "  ← 零填充"
        print(f"  0x{lo:08x}-0x{hi:08x} {hi - lo:7d} 字节  {b.hex(' ')}{tag}")


def build(img: Image, dis: Disassembler, outdir: str):
    os.makedirs(outdir, exist_ok=True)

    # 1. 函数清单
    funcs = []
    for va, fn in sorted(dis.funcs.items()):
        funcs.append({
            "va": f"0x{va:08x}",
            "insn_count": len(fn.insns),
            "size": fn.size,
            "ends": fn.ends,
            "root": dis.roots.get(va, ""),
            "callers": [f"0x{c:08x}" for c in sorted(fn.callers)],
            "callees": [f"0x{c:08x}" for c in sorted(fn.callees)],
            "reads": [f"0x{r:08x}" for r in sorted(fn.reads)],
            "writes": [f"0x{w:08x}" for w in sorted(fn.writes)],
        })
    with open(os.path.join(outdir, "functions.json"), "w") as f:
        json.dump(funcs, f, ensure_ascii=False, indent=1)

    # 2. 全局变量 xref 表
    xref: dict[int, dict] = {}
    for va, fn in sorted(dis.funcs.items()):
        for r in fn.reads:
            xref.setdefault(r, {"read": [], "write": []})["read"].append(va)
        for w in fn.writes:
            xref.setdefault(w, {"read": [], "write": []})["write"].append(va)
    xr = [{"addr": f"0x{a:08x}", "read_by": [f"0x{x:08x}" for x in sorted(v["read"])],
           "written_by": [f"0x{x:08x}" for x in sorted(v["write"])]}
          for a, v in sorted(xref.items())]
    with open(os.path.join(outdir, "xrefs.json"), "w") as f:
        json.dump(xr, f, ensure_ascii=False, indent=1)

    # 3. 跳表
    jt = [{"table": f"0x{t:08x}", "count": len(e),
           "entries": [f"0x{x:08x}" for x in e]}
          for t, e in sorted(dis.stats["jump_tables"].items())]
    with open(os.path.join(outdir, "jumptables.json"), "w") as f:
        json.dump(jt, f, ensure_ascii=False, indent=1)

    # 3b. ★ 函数边界「推断」审计：哪些入口被并入了宿主、哪些是待判候选。
    #     函数边界是**推断**而非事实（见 docs/00-methodology.md），
    #     所以把推断过程与未决候选一并落盘，方便复核与回退。
    bc = {
        "absorbed_into_host": [
            {"entry": f"0x{a:08x}", "host": f"0x{b:08x}", "insn_count": n}
            for a, b, n in dis.stats.get("absorbed_orphan_blocks", [])],
        "jmp_merge_candidates": [
            {"entry": f"0x{a:08x}", "host": f"0x{b:08x}", "insn_count": n,
             "why": "仅被单个函数的 jmp 引用（可能是尾调用，也可能是共享尾块），未自动合并"}
            for a, b, n in dis.stats.get("jmp_merge_candidates", [])],
        "dropped_mid_instruction": [
            f"0x{a:08x}" for a in dis.stats.get("dropped_mid_insn", [])],
    }
    with open(os.path.join(outdir, "function-boundary-candidates.json"), "w") as f:
        json.dump(bc, f, ensure_ascii=False, indent=1)
    print(f"已写入 {outdir}/function-boundary-candidates.json"
          f"（并入 {len(bc['absorbed_into_host'])}，待判候选 {len(bc['jmp_merge_candidates'])}）")

    # 4. ★ E8/E9 全量反查索引
    #    为什么单独做：`functions.json` 的 callers 只统计**已解码区域**内的调用，
    #    而遍历可能是不可达的函数（回调、仅经函数指针调用者）会因此**漏掉呼叫者**。
    #    本索引直接扫全代码段的 E8/E9 字节，与是否解码无关，故是**完整**的。
    #    （上游子代理报告过 `0x43380a`/`0x40f381` 在 callers 里为空，
    #      用这种扫描才找到 `0x41b3cb`/`0x418f59`。）
    img = dis.img
    calls: dict[int, list[int]] = {}
    for off in range(CODE_OFF, CODE_OFF + CODE_SIZE - 5):
        op = img.data[off]
        if op != 0xE8 and op != 0xE9:
            continue
        rel = struct.unpack_from("<i", img.data, off + 1)[0]
        site = CODE_VA + (off - CODE_OFF)
        tgt = site + 5 + rel
        if is_code_ptr(tgt):
            calls.setdefault(tgt, []).append(site)
    with open(os.path.join(outdir, "rel32-calls.json"), "w") as f:
        json.dump({f"0x{k:08x}": [f"0x{x:08x}" for x in v]
                   for k, v in sorted(calls.items())}, f, ensure_ascii=False, indent=1)
    print(f"已写入 {outdir}/rel32-calls.json（{len(calls)} 个被直接调用的目标，"
          f"共 {sum(len(v) for v in calls.values())} 处 E8/E9）")

    print(f"已写入 {outdir}/functions.json（{len(funcs)} 个函数）")
    print(f"已写入 {outdir}/xrefs.json（{len(xr)} 个全局地址）")
    print(f"已写入 {outdir}/jumptables.json（{len(jt)} 个跳表）")


def main(argv):
    img = Image(argv[1] if len(argv) > 1 and argv[1].endswith(".exe") else EXE_DEFAULT)
    args = [a for a in argv[1:] if not a.endswith(".exe")]
    cmd = args[0] if args else "info"

    if cmd == "info":
        cmd_info(img)
        return 0

    dis = Disassembler(img)
    if cmd in ("func", "boundaries", "build", "gaps", "gaprefs", "tail"):
        dis.traverse(include_orphans=("--orphans" in args))

    if cmd == "tail":
        cmd_tail(dis)
    elif cmd == "gaprefs":
        cmd_gaprefs(dis)
    elif cmd == "gaps":
        cmd_gaps(dis)
    elif cmd == "func":
        if len(args) < 2:
            return print("用法: func 0x0045709c") or 2
        print(render_func(dis, int(args[1], 16)))
    elif cmd == "boundaries":
        cmd_boundaries(dis)
    elif cmd == "build":
        outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gen")
        build(img, dis, outdir)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
