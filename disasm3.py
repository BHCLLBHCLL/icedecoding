# -*- coding: utf-8 -*-
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    data = f.read()

image_base = 0x140000000
def va_to_off(va):
    rva = va - image_base
    return 0x400 + (rva - 0x1000)

md = Cs(CS_ARCH_X86, CS_MODE_64)

def disasm_func(start_va, name, max_len=0x400):
    print(f"\n{'='*70}\n=== {name} @ {start_va:#x} ===\n{'='*70}")
    off = va_to_off(start_va)
    code = data[off:off+max_len]
    lines = []
    for insn in md.disasm(code, start_va):
        lines.append(f"  {insn.address:#x}: {insn.mnemonic} {insn.op_str}")
        if insn.mnemonic == "ret":
            break
    print("\n".join(lines))
    return lines

disasm_func(0x14002bf70, "transform2")
disasm_func(0x14002bbf6 - 0x60, "decoder_ref2_context")
