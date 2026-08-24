# -*- coding: utf-8 -*-
"""解析PE并找到引用Il!!字符串的代码"""
import struct

path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    data = f.read()

# PE头
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
machine, nsec, _, _, _, optsz, _ = struct.unpack_from("<HHIIIHH", data, e_lfanew + 4)
opt = e_lfanew + 24
magic = struct.unpack_from("<H", data, opt)[0]
image_base = struct.unpack_from("<Q", data, opt + 24)[0]
print(f"machine={machine:#x} sections={nsec} magic={magic:#x} image_base={image_base:#x}")

secs = []
sec_off = opt + optsz
for i in range(nsec):
    name = data[sec_off:sec_off+8].rstrip(b"\0").decode()
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, sec_off + 8)
    secs.append((name, vaddr, vsize, raddr, rsize))
    print(f"  {name:8s} vaddr={vaddr:#x} vsize={vsize:#x} raw={raddr:#x} rsize={rsize:#x}")
    sec_off += 40

def off_to_va(off):
    for name, vaddr, vsize, raddr, rsize in secs:
        if raddr <= off < raddr + rsize:
            return image_base + vaddr + (off - raddr)
    return None

def va_to_off(va):
    rva = va - image_base
    for name, vaddr, vsize, raddr, rsize in secs:
        if vaddr <= rva < vaddr + vsize:
            return raddr + (rva - vaddr)
    return None

# 字符串位置
targets = {
    "Il!!": data.find(b"Il!!\0"),
    "q|sz}y~": data.find(b"q|sz}y~\0"),
    "cor5...": data.find(b"cor5(#b!S0efP3+E\0"),
}
print()
for name, off in targets.items():
    va = off_to_va(off)
    print(f"string {name!r} file_off={off} VA={va:#x}")
    targets[name] = (off, va)

# 搜索代码中对这些VA的RIP相对引用 (lea rXX, [rip+disp])
# lea 模式: 48 8d 0d/15/05... disp32
text_secs = [s for s in secs if s[0] in (".text", ".rdata", "UPX0", "CODE")]
print("\n搜索RIP相对引用...")
for name, (off, va) in targets.items():
    refs = []
    for sname, vaddr, vsize, raddr, rsize in secs:
        if sname not in (".text",):
            continue
        # 扫描 lea 指令: 48 8d XX disp32 (XX低3位=001表示reg, [rip+disp])
        for i in range(raddr, raddr + rsize - 7):
            if data[i] == 0x48 and data[i+1] == 0x8D:
                modrm = data[i+2]
                if (modrm & 0xC7) == 0x05:  # [rip+disp32]
                    disp = struct.unpack_from("<i", data, i+3)[0]
                    instr_end_va = off_to_va(i) + 7
                    if instr_end_va + disp == va:
                        refs.append((i, off_to_va(i)))
    print(f"{name!r}: {len(refs)} refs: {[(hex(o), hex(v)) for o, v in refs]}")
