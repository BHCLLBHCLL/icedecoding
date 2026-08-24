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
start_va = 0x14002b8c0
off = va_to_off(start_va)
code = data[off:off+0x500]
out = []
for insn in md.disasm(code, start_va):
    out.append(f"  {insn.address:#x}: {insn.mnemonic} {insn.op_str}")
    if insn.mnemonic == "ret":
        break
"\n".join(out)
open(r"D:\training\icepak_parser\func_disasm.txt", "w").write("\n".join(out))
print(f"{len(out)} instructions written")
