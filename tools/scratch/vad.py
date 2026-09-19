#!/usr/bin/env python3
"""按需裁决反汇编（自足版，避免依赖外部工具的启动开销）。

用法:
    python3 tools/vad.py va 0x42e931 90
    python3 tools/vad.py bytes 0x47fee2 64
    python3 tools/vad.py dw 0x41b3e5 18
    python3 tools/vad.py cstr 0x463ab1
"""
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

EXE = "/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe"
SECTIONS = [
    ("AUTO", 0x401000, 1024, 394240),
    ("DGROUP", 0x463000, 398848, 158720),
    ("bss", 0x48A000, None, 64512),
]


def load():
    with open(EXE, "rb") as f:
        return f.read()


def va_to_off(va):
    for _, sva, off, size in SECTIONS:
        if sva <= va < sva + size:
            return None if off is None else off + (va - sva)
    return None


def main():
    data = load()
    cmd = sys.argv[1]
    if cmd == "va":
        va = int(sys.argv[2], 0)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        off = va_to_off(va)
        for i in md.disasm(data[off:off + n * 8], va):
            print(f"  {i.address:08x}  {i.mnemonic:<7} {i.op_str}")
    elif cmd == "bytes":
        va = int(sys.argv[2], 0)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 32
        off = va_to_off(va)
        for r in range(0, n, 16):
            b = data[off + r:off + r + 16]
            print(f"  {va + r:#010x}  " + " ".join(f"{x:02x}" for x in b))
    elif cmd == "dw":
        va = int(sys.argv[2], 0)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 16
        off = va_to_off(va)
        for i in range(n):
            (v,) = struct.unpack_from("<I", data, off + i * 4)
            print(f"  [{i:3d}] {v:#010x}  ({v})")
    elif cmd == "cstr":
        va = int(sys.argv[2], 0)
        off = va_to_off(va)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        for i in range(n):
            o = off + i * 4
            (p,) = struct.unpack_from("<I", data, o)
            po = va_to_off(p)
            if po is None:
                print(f"  +{i*4:#04x} -> {p:#010x}  <bad>")
                continue
            e = data.index(b"\0", po)
            try:
                s = data[po:e].decode("big5")
            except Exception:
                s = repr(data[po:e])
            print(f"  +{i*4:#04x} -> {p:#010x}  {s!r}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
