# -*- coding: utf-8 -*-
"""验证完整model文件解码"""
KQ = b"q|sz}y~"
KC = b"cor5(#b!S0efP3+E"

def decode_line(line):
    if not line.startswith("Il!!"):
        return line
    s = line[4:]
    if not s:
        return ""
    seed = ord(s[0])
    body = s[1:]
    out = []
    for i, ch in enumerate(body):
        c = ord(ch)
        if 0x20 <= c <= 0x7e:
            v = c - KQ[i % 7] - KC[i % 16] - seed
            while v < 0x20:
                v += 0x5f
            out.append(chr(v))
        else:
            out.append(ch)
    return "".join(out)

with open(r"D:\training\icepak\10-1transient\model", encoding="latin-1") as f:
    lines = f.read().splitlines()

decoded = [decode_line(l) for l in lines]
print("\n".join(decoded[:75]))
print(f"\n... 共{len(decoded)}行 ...")
