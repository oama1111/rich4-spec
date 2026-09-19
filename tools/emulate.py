#!/usr/bin/env python3
"""
rich4-spec · 验收层：单函数差分测试台（通道 2）

思路
----
对一个**纯函数**（只读全局数据、无 I/O），直接在本地用 Unicorn **执行原版
exe 里的那份机器码**，把它的返回值当作**预言机**，与复刻版实现逐用例比对。

这比"读汇编再手写 TS"可靠得多：
  · 读汇编可能看错分支/看漏取整 —— 实测上游已有 8 处此类错误
  · 差分测试的成本是**固定**的（每个函数一个 harness），且随用例增加
    而不断加固，而读汇编的可靠性不会随投入线性提高

为什么不整体跑原版
------------------
原版是 2001 年的 Win32 程序，内部状态没有导出接口，无法与 TS/Web 版对内存
做 diff。但**单个函数的语义**完全可以这样精确对齐 —— 这是性价比最高的路径。

用法
----
    # 建立/刷新基础镜像缓存
    python3 tools/emulate.py selftest
    # 调用任意函数（参数按 cdecl 从右到左传入）
    python3 tools/emulate.py call 0x419744 0 0      # (player=0, land_name=NULL)
    python3 tools/emulate.py toll 0 0x4630f4        # 语义化封装：过路费
    python3 tools/emulate.py prng 7 5               # PRNG 前 5 个输出
"""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rich4dis import Image, EXE_DEFAULT  # noqa: E402

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (
        UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EAX, UC_X86_REG_EBX,
        UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
        UC_X86_REG_EIP, UC_X86_REG_FPCW, UC_X86_REG_FPSW, UC_X86_REG_FPTAG,
        UC_X86_REG_FP0, UC_X86_REG_FP1, UC_X86_REG_FP2, UC_X86_REG_FP3,
        UC_X86_REG_FP4, UC_X86_REG_FP5, UC_X86_REG_FP6, UC_X86_REG_FP7,
    )
except ImportError:
    sys.exit("需要 unicorn：python3 -m venv .venv && .venv/bin/pip install unicorn")

# ── 内存布局（与 PE 一致，实测自节表） ──
# ★ 2026-09-19 加：**桩区**。给「要替换 User32 导入桩」的窗口过程测试用
#   （`WndProc` 里 `call dword cs:[0x462310]` 之类走的是 `.idata` 的 thunk，
#   而 thunk 内容是 `jmp far 0x62xx:…` ⇒ 目标未映射、一进去就 FETCH_UNMAPPED）。
#   把 thunk 里的**地址**改成这里，那些调用就变成空操作。
#   为什么不用 .bss：那一段与游戏数据（节点表/地块表…）重叠，写桩会破坏数据。
STUB_BASE = 0x4C0000
STUB_SIZE = 0x1000

SEGMENTS = [
    # (VA, 文件偏移, 大小, 是否可写)
    (0x401000, 1024,    394240, False),   # AUTO  代码
    (0x462000, 395264,  3584,   True),    # .idata
    (0x463000, 398848,  158720, True),    # DGROUP 全局数据（可写：函数会改它）
    (0x48A000, None,    64512,  True),    # .bss 未初始化
    (STUB_BASE, None,   STUB_SIZE, True),  # ★ 桩区（见 STUB_BASE 注释）
]
STACK_BASE = 0x500000        # 栈放在 .rsrc 之后的空白区
STACK_SIZE = 0x40000
STACK_TOP = STACK_BASE + STACK_SIZE - 0x100

# ★ 暂存区：**故意不纳入 reset 快照**。
#   用途：需要跨多次 `call()` 保持的状态（例如 PRNG 的状态块）。
#   若把它放进 DGROUP/.bss，`reset()` 会在每次调用前把注入的数据抹回快照值 ——
#   实测因此出现「种子设了却被清零、PRNG 从 0 开始跑」的假象，浪费了一轮排查。
SCRATCH_BASE = 0x600000
SCRATCH_SIZE = 0x10000

# 这些函数用 cdecl（调用方清理栈）还是 callee-cleanup（ret N）？
# 由 harness 运行时探测：执行到 ret 后看 ESP 相对初值的变化即可判定。
MAX_INSN = 400000

# eval_block() 用的哨兵返回地址：落在已映射的栈区内，区块内若发生 call，
# 被调函数 ret 到这里时正好等于 emu_start 的停止地址，仿真自然结束。
RET_SENTINEL = 0x53FFF0

# ★ x87 控制字默认值：真实 Windows/MSVC 进程启动时的 0x027F
#   （RC=00 就近舍入，PC=10 双精度 53 位尾数，异常全屏蔽）。
#   Unicorn 的初始 CW 与真实进程**不一致**（读回 0x0000 → PC=00 单精度 24 位），
#   会让浮点结果被静默舍入：实测 `trunc(2147483644 × 0.05)` 在同一实例的
#   **第二次**求值上得到 107374184（而正确答案是 107374182），换新实例又正确；
#   根因是 Unicorn 缓存的精度/舍入状态不随内存快照还原（FPCW 读回恒为 0）。
#   因此每次求值前必须显式写回 FPCW_DEFAULT —— 见 Emu.reset_fpu()。
FPCW_DEFAULT = 0x027F

# x87 数据寄存器常量（按 ST(0)..ST(7) 顺序）。
FP_REGISTERS = [
    UC_X86_REG_FP0, UC_X86_REG_FP1, UC_X86_REG_FP2, UC_X86_REG_FP3,
    UC_X86_REG_FP4, UC_X86_REG_FP5, UC_X86_REG_FP6, UC_X86_REG_FP7,
]

# eval_block() 可设置的通用寄存器名 → Unicorn 常量。
GP_REGISTERS = {
    "eax": UC_X86_REG_EAX, "ebx": UC_X86_REG_EBX, "ecx": UC_X86_REG_ECX,
    "edx": UC_X86_REG_EDX, "esi": UC_X86_REG_ESI, "edi": UC_X86_REG_EDI,
    "ebp": UC_X86_REG_EBP,
}


class Emu:
    """一个可反复调用的 exe 镜像。

    ⚠️ 每次调用前必须**备份并恢复**写过的数据段，否则前一次调用对全局状态的
       副作用会污染后续用例（例如 `calculate_land_toll` 虽然只读，但被它调用
       的 `strcmp` 可能写全局；实测过一次调用后 DGROUP 有变化）。
    """

    def __init__(self, exe_path: str = EXE_DEFAULT):
        self.img = Image(exe_path)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        # ⚠️ Unicorn 要求映射地址与大小都按 4KB 页对齐，否则 UC_ERR_ARG。
        #    节表里的地址本身就是页对齐的，但为了稳妥仍做对齐计算。
        PAGE = 0x1000
        for va, off, size, writable in SEGMENTS:
            base = va & ~(PAGE - 1)
            end = (va + size + PAGE - 1) & ~(PAGE - 1)
            self.mu.mem_map(base, end - base)
            if off is not None:
                self.mu.mem_write(va, self.img.data[off:off + size])
        self.mu.mem_map(STACK_BASE, STACK_SIZE)
        self.mu.mem_map(SCRATCH_BASE, SCRATCH_SIZE)
        self._snapshot = {
            va: self.mu.mem_read(va, size)
            for va, off, size, writable in SEGMENTS if writable
        }
        self.insn_count = 0

    def scratch_write(self, va: int, data: bytes):
        """写暂存区（不被 reset 覆盖）。va 必须落在 SCRATCH_BASE 起 64KB 内。"""
        off = va - SCRATCH_BASE
        if not (0 <= off < SCRATCH_SIZE - len(data)):
            raise ValueError(f"0x{va:x} 超出暂存区 0x{SCRATCH_BASE:x}+{SCRATCH_SIZE:#x}")
        self.mu.mem_write(va, bytes(data))

    def scratch_read(self, va: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(va, n))

    def patch(self, va: int, code: bytes, persist: bool = True):
        """在代码段打桩，并把补丁**并入快照**，使后续 reset() 仍保持补丁。

        初版忘了重拍快照，导致补丁在第二次 call 时被还原 —— 排查成本很高，
        故在此显式提供 `patch()`。

        ★★ 2026-09-18（第 88 条末尾）**再修一个更隐蔽的同族缺陷**：原先只对
        **可写段**（`writable=True`，即 .idata/DGROUP/.bss）重拍快照，而代码段
        AUTO **不在其中** ⇒ 对同一个 VA **第二次** `patch()` 会被 `reset()`
        悄悄还原成**第一次**补丁的内容。表现是"改了桩的立即数，行为却没变"
        （实测：`patch(0x456f2d, mov eax,5)` 之后 `patch(…, mov eax,7)`，
        再调用仍返回 5）。排查花了很久，故这里改成：**任何段**都重拍
        （AUTO 若本来不在快照里，就地补一条，`reset()` 于是按"打过补丁的当前
        内容"还原 —— 正是"补丁持续生效"的语义）。
        ⚠️ 若某个用例需要**每个 case 不同的桩**，仍建议把变化放进**数据**
        （见 `tests/test_turn_around.py` 的 `rand_stub`）：那样连补丁都不用重打。
        """
        self.mu.mem_write(va, bytes(code))
        # ★★ 还必须**清掉 Unicorn 的翻译块缓存**：实测（第 88 条末尾）同一个 VA
        #   打第二次补丁时，`mem_write`/快照都更新了、内存读出来也是新字节，
        #   但再次 `call()` **仍执行旧补丁** —— 就是 TB 缓存。`ctl_remove_cache`
        #   一试即好（`mov eax,5` → `mov eax,7` 立刻生效）。
        if persist:
            for sva, off, size, writable in SEGMENTS:
                if sva <= va < sva + size:
                    # ★ 清 TB 缓存必须按**命中段**的范围来：宽范围（0x400000..0x500000）
                    #   在本 Unicorn 版本上不生效（实测），按段范围才生效。
                    try:
                        self.mu.ctl_remove_cache(sva, sva + size)
                    except Exception:            # noqa: BLE001
                        pass                         # 某些 Unicorn 版本没有这个 API
                    self._snapshot[sva] = self.mu.mem_read(sva, size)
                    break

    def reset(self):
        """恢复全部可写段到初始状态，并复位 x87（每用例之间必须调用）。

        ⚠️ 只还原内存是不够的：x87 的控制字/状态不在内存快照里，
        必须靠 reset_fpu() 显式写回，否则同一实例内连续求值会出现
        「第二次结果偏离第一次」的假象（详见 FPCW_DEFAULT 注释）。
        """
        for va, data in self._snapshot.items():
            self.mu.mem_write(va, bytes(data))
        self.reset_fpu()
        self.insn_count = 0

    def reset_fpu(self):
        """把 x87 恢复到真实进程默认状态：CW=0x027F、状态字/标记字清零、栈空。"""
        mu = self.mu
        mu.reg_write(UC_X86_REG_FPCW, FPCW_DEFAULT)
        mu.reg_write(UC_X86_REG_FPSW, 0)
        mu.reg_write(UC_X86_REG_FPTAG, 0xFFFF)   # 全空
        for reg in FP_REGISTERS:
            try:
                mu.reg_write(reg, (0, 0))
            except Exception:                    # noqa: BLE001
                pass                             # 某些版本不支持写 FP 数据寄存器

    def _hook(self, mu, address, size, user):
        self.insn_count += 1
        if self.insn_count > MAX_INSN:
            mu.emu_stop()

    def call(self, func_va: int, args: list[int], ret_addr: int = 0x53FFF0,
             setup=None, timeout_insns: int = MAX_INSN):
        """按 **cdecl** 调用：参数从右到左压栈。

        返回 (eax, esp_delta)。esp_delta 用于判定被调函数是否自己清了栈。

        ⚠️ 与 `eval_block` 同一个坑：本方法**开头就 `reset()`**，所以
        **凡是要注入的 DGROUP 全局量都必须走 `setup(emu)`**（在 reset 之后、
        压栈之前调用），直接写在调用外会被抹掉 —— 表现同样是「明明注入了却读到 0」，
        或者在 `idiv` 上直接 `UC_ERR_EXCEPTION`（除零）。这个坑已经踩过两次，
        两次都是花在「数据明明写进去了」的自我怀疑上。
        """
        self.reset()
        self.insn_count = 0        # 每次调用单独计数（reset 里也清，但这里更明确）
        if setup is not None:
            setup(self)
        self.max = timeout_insns
        mu = self.mu
        sp = STACK_TOP
        # 压参数（右→左）
        for a in reversed(args):
            sp -= 4
            mu.mem_write(sp, struct.pack("<I", a & 0xFFFFFFFF))
        # 返回地址
        sp -= 4
        mu.mem_write(sp, struct.pack("<I", ret_addr))
        # ret_addr 落在已映射的栈区内；emu_start 以它作为停止地址，
        # 不需要写入哨兵字节（写 hlt 反而可能覆盖合法代码/数据）。

        # ★★ 2026-09-19 修（§7.141）：**每次求值后必须 `hook_del`**。
        #   先前每次 `call()`/`eval_block()` 都 `hook_add` 却从不删除 ⇒ 第 k 次调用时
        #   `self._hook` 被挂 k 份、`insn_count` 每指令涨 k 倍，长循环会在
        #   `MAX_INSN` 处**静默假停**（表现为"函数行为不对"，根因在测试台）。
        #   实测：同一实例第 100 次调用一支洗牌函数 → 只摇 20/37 次 rand；
        #   另一个用例里 dx=5000 的 313 帧只跑了 177 帧。
        #   两个并行子代理各自独立撞上它 —— 故在测试台统一收口。
        hook = mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_EBP, sp)
        before = sp
        try:
            mu.emu_start(func_va, ret_addr, count=timeout_insns)
        except Exception as e:                    # noqa: BLE001
            raise RuntimeError(f"仿真异常 @EIP=0x{mu.reg_read(UC_X86_REG_EIP):08x}: {e}") from e
        finally:
            try:
                mu.hook_del(hook)
            except Exception:                     # noqa: BLE001
                pass
        eax = mu.reg_read(UC_X86_REG_EAX)
        esp_after = mu.reg_read(UC_X86_REG_ESP)
        # 有符号解释（原版多数金额是 32 位有符号）
        signed = eax - (1 << 32) if eax >= (1 << 31) else eax
        return {"eax": eax, "signed": signed, "esp_delta": esp_after - before,
                "insns": self.insn_count}

    # ── 内存读写：给「注入表数据 / 回读结果」用 ─────────────────────────
    # 注意：注入的地址必须落在 **可写段**（DGROUP/.bss/SCRATCH）。
    # DGROUP 会被 reset() 还原，所以「每用例注入」是正确姿势；
    # 跨多次求值要保持的数据请放 SCRATCH_BASE（见 scratch_write）。
    def read(self, va: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(va, n))

    def read32(self, va: int) -> int:
        return struct.unpack("<i", self.read(va, 4))[0]

    def readu32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]

    def read16(self, va: int) -> int:
        return struct.unpack("<H", self.read(va, 2))[0]

    def read8(self, va: int) -> int:
        return self.read(va, 1)[0]

    def write(self, va: int, data: bytes):
        self.mu.mem_write(va, bytes(data))

    def write32(self, va: int, v: int):
        self.write(va, struct.pack("<i", v))

    def write16(self, va: int, v: int):
        self.write(va, struct.pack("<H", v & 0xFFFF))

    def write8(self, va: int, v: int):
        self.write(va, struct.pack("<B", v & 0xFF))

    def f64(self, va: int) -> float:
        """读一个 f64 常量（原版把浮点常量放在 DGROUP 只读区）。"""
        return struct.unpack("<d", self.read(va, 8))[0]

    def eval_block(self, start_va: int, stop_va: int, regs: dict | None = None,
                   setup=None, timeout_insns: int = MAX_INSN):
        """求值一段 **内联代码块** —— 它不是函数入口，所以不能 call()。

        背景：原版里大量公式是内联展开的（地产估价、税率、利息…），
        没有 `call` 入口，`call()` 无法驱动。本方法用「寄存器初值 + 停址」求值：
        从 start_va 执行到 EIP==stop_va，期间**必须不 ret**，
        也不得读函数序言（push ebp/sub esp）建立的局部变量。

        调用姿势：
            def setup(e):                      # ★ 必须用 setup 注入全局量！
                e.write32(0x498e84, 0x600000)  #   reset() 会先抹掉直接写的 DGROUP
            emu.eval_block(0x4265a6, 0x426602, {"ebx": 2000}, setup=setup)
            → 结果在 regs["esi"]，或回读内存 read32(...)

        `setup(emu)` 在 reset() **之后**、开跑 **之前** 调用：直接写 DGROUP
        全局量的注入一律放这里（否则被 reset 还原，表现为「明明注入了却读到 0」）。

        ⚠️⚠️ **2026-09-19 补（gaps §7.99 踩过）**：`setup()` 是在**写 `regs` 之前**
        被调用的，所以「块内会读的**栈局部**」（形如 `mov edx,[esp+0xe0]`）必须
        在 `setup()` 里写，且**不要依赖 `regs` 的值**——需要段址时用常量写内存。
        另外 `reset()` **不清栈**，所以写到 `[STACK_TOP+…]` 的局部量是有效的；
        但**原版读的是它自己的全局段址**（如 `0x498E88` 的设施表基址），
        与我们要用的 `SCRATCH_BASE` **是两回事**，两个都要设。
        ⚠️ 返回的内存状态是**区块执行后**的；DGROUP 只读常量可直接用 f64() 读。
        """
        self.reset()
        self.insn_count = 0
        mu = self.mu
        sp = STACK_TOP
        mu.mem_write(sp, struct.pack("<I", RET_SENTINEL))
        if setup is not None:
            setup(self)
        given = dict(regs or {})
        for name, val in given.items():
            if name == "esp":
                continue
            if name not in GP_REGISTERS:
                raise ValueError(f"eval_block 不支持寄存器 {name!r}")
            mu.reg_write(GP_REGISTERS[name], val & 0xFFFFFFFF)
        # ★ 2026-09-19 加：`regs` 里可以给 `esp`（默认 `STACK_TOP`）。
        #   有些片段的帧比 `STACK_TOP` 到页边界的那点余量还大
        #   （实测 `0x4198b9` 那一支要读 `[esp+0x10c]`，而 `0x53ff00+0x10c`
        #   跨过了栈映射的上界）⇒ 允许调用方把 ESP 调低一点。
        sp = int(given.pop("esp", sp)) & 0xFFFFFFFF
        mu.reg_write(UC_X86_REG_ESP, sp)
        if "ebp" not in given:
            mu.reg_write(UC_X86_REG_EBP, sp)
        hook = mu.hook_add(UC_HOOK_CODE, self._hook)
        try:
            mu.emu_start(start_va, stop_va, count=timeout_insns)
        except Exception as e:                    # noqa: BLE001
            raise RuntimeError(
                f"仿真异常 @EIP=0x{mu.reg_read(UC_X86_REG_EIP):08x}: {e}") from e
        finally:
            # ★ 同 `call()`：用完即摘，否则 insn_count 会被放大 k 倍（§7.141）。
            try:
                mu.hook_del(hook)
            except Exception:                     # noqa: BLE001
                pass
        out = {name: mu.reg_read(reg) for name, reg in GP_REGISTERS.items()}
        out["esp"] = mu.reg_read(UC_X86_REG_ESP)
        eip = mu.reg_read(UC_X86_REG_EIP)
        if eip != stop_va:
            raise RuntimeError(
                f"区块未停在预期停址：EIP=0x{eip:08x}，期望 0x{stop_va:08x}"
                f"（{self.insn_count} 条指令）")
        return {"regs": out, "insns": self.insn_count}


def cmd_selftest(emu: Emu):
    print("=== 自检：能否执行原版机器码 ===")
    # 0x458370 是 strcmp：用两个 DGROUP 里的已知字符串试
    img = emu.img
    # 「二人」在 0x4630f4，「三人」在 0x4630f9（前一步已从字符串表确认）
    a, b = 0x4630f4, 0x4630f4
    r = emu.call(0x458370, [a, b])
    print(f"strcmp(相同串) → eax={r['eax']}  指令数={r['insns']}")
    assert r["eax"] == 0, "相同字符串应返回 0"
    r2 = emu.call(0x458370, [0x4630f4, 0x4630f9])
    print(f"strcmp(二人,三人) → eax={r2['eax']}（非 0 即正确）")
    assert r2["eax"] != 0, "不同字符串不应返回 0"
    print("✅ 自检通过：Unicorn 能正确执行原版代码")


def cmd_toll(emu: Emu, player: int, land_name):
    r = emu.call(0x419744, [player, land_name])
    print(f"calculate_land_toll(player={player}, land_name=0x{land_name:x}) "
          f"→ {r['signed']} (eax=0x{r['eax']:08x}, {r['insns']} 条指令)")
    return r


def cmd_prng(emu: Emu, seed: int, n: int):
    """PRNG 在 0x456f2d，内部经 0x456f23 取状态指针。

    ⚠️ 状态指针存放在全局里；本 harness 先调用一次让它初始化，
       再连续调用取序列。真正的 TS 对齐应比对**整段序列**而非单值。
    """
    print(f"PRNG seed={seed} 前 {n} 个输出：")
    out = []
    for i in range(n):
        r = emu.call(0x456f2d, [])
        out.append(r["eax"])
        print(f"  [{i}] 0x{r['eax']:08x}  ({r['signed']})")
    return out


def main(argv):
    emu = Emu()
    cmd = argv[1] if len(argv) > 1 else "selftest"
    if cmd == "selftest":
        cmd_selftest(emu)
    elif cmd == "call":
        va = int(argv[2], 16)
        args = [int(a, 0) for a in argv[3:]]
        r = emu.call(va, args)
        print(f"0x{va:08x}(" + ", ".join(hex(a) for a in args) + f") → {r['signed']} "
              f"(eax=0x{r['eax']:08x}, esp_delta={r['esp_delta']}, {r['insns']} 条)")
    elif cmd == "toll":
        cmd_toll(emu, int(argv[2], 0), int(argv[3], 0))
    elif cmd == "prng":
        cmd_prng(emu, int(argv[2], 0), int(argv[3], 0) if len(argv) > 3 else 5)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
