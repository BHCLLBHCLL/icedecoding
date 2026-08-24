# -*- coding: utf-8 -*-
"""读取密钥长度并测试解码算法"""
import struct

path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    data = f.read()

# .data: vaddr=0x7ca000, raw=0x7c8e00
def rva_to_off(rva):
    return 0x7c8e00 + (rva - 0x7ca000)

# 密钥字符串
key_q = data[0x400 + (0x6d3db0 - 0x1000):][:16]   # q|sz}y~ at RVA 0x6d3db0 (.rdata)
key_c = data[0x400 + (0x6d3db8 - 0x1000):][:24]   # cor5... at RVA 0x6d3db8
print(f"key_q bytes: {key_q}")
print(f"key_c bytes: {key_c}")

# 长度全局变量 (可能是运行时初始化, 静态值可能为0)
len_c = struct.unpack_from("<I", data, rva_to_off(0x807180))[0]
len_q = struct.unpack_from("<I", data, rva_to_off(0x807184))[0]
print(f"LEN_c (cor5, at 0x807180): {len_c}")
print(f"LEN_q (q|sz, at 0x807184): {len_q}")

# 附近的.data内容
print(f"\n.data around 0x807180: {data[rva_to_off(0x807170):rva_to_off(0x8071a0)].hex()}")

# ===== 解码函数 =====
KQ = b"q|sz}y~"
KC = b"cor5(#b!S0efP3+E"

def decode_line(line):
    """line: str (已去掉换行)"""
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

# 测试!
tests = [
    "Il!!t/XOxaaLH._EP4(W}4B\\qq",
    "Il!!1Nhq9y{g%s",
    "Il!!e\"B2v`L*J|",
    "Il!!1Kq^$-xcsB&e[B7/e",
    "Il!!0Npa&v~emQ([jUC>",
    "Il!!a,8+cN_'Ew`#;uVPj:A<SZ=\"@vi$",
    "Il!!}HQZ&fh`b?lNXZ1wQdy%.6\"os];ny?/n/JWe8$ql,_CVrQB=>qn!=  @h+rX\\]:<6op!G11c-V:ro^47Hm}kC'1SzGxPM:kd)IOK1v/]y6jH@*vp%<ka?#",
]
for t in tests:
    print(f"\n  enc: {t[:60]}...")
    print(f"  dec: |{decode_line(t)}|")
