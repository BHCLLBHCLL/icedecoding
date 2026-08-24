# -*- coding: utf-8 -*-
"""提取icepak.exe中Il!!附近的原始字节"""
path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    f.seek(7156136 - 256)
    data = f.read(1024)

# hex dump
for i in range(0, len(data), 32):
    chunk = data[i:i+32]
    hexpart = " ".join(f"{b:02x}" for b in chunk)
    txtpart = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"{7156136-256+i:8d}  {hexpart}  {txtpart}")
