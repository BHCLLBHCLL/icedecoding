# -*- coding: utf-8 -*-
"""反汇编引用Il!!的函数"""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    data = f.read()

image_base = 0x140000000
secs = [(".text", 0x1000, 0x617e6c, 0x400, 0x618000)]

def va_to_off(va):
    rva = va - image_base
    for name, vaddr, vsize, raddr, rsize in secs:
        if vaddr <= rva < vaddr + vsize:
            return raddr + (rva - vaddr)

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False

# 反汇编两处引用附近的代码 (向前256字节开始)
for ref_va in (0x14002b913, 0x14002bbf6):
    print(f"\n{'='*70}\n=== ref @ {ref_va:#x} ===\n{'='*70}")
    start_va = ref_va - 0x180
    off = va_to_off(start_va)
    code = data[off:off+0x400]
    for insn in md.disasm(code, start_va):
        marker = " <<<<" if insn.address <= ref_va < insn.address + insn.size else ""
        print(f"  {insn.address:#x}: {insn.mnemonic} {insn.op_str}{marker}")
        if insn.address > ref_va + 0x200:
            break
