# -*- coding: utf-8 -*-
"""从digest提取字符串，搜索编码相关线索"""
import re

path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\lib\icepak\digest"
with open(path, "rb") as f:
    data = f.read()

print(f"digest size: {len(data)}")

# 提取可打印字符串 (>=6 chars)
strings = re.findall(rb"[\x20-\x7e]{6,}", data)
print(f"total strings: {len(strings)}")

# 搜索关键词
keywords = [b"identity", b"encode", b"Il!!", b"model file", b"cipher", b"scrambl", b"obfusc"]
for kw in keywords:
    hits = [s for s in strings if kw.lower() in s.lower()]
    print(f"\n=== {kw!r}: {len(hits)} hits ===")
    for s in hits[:20]:
        print(f"  {s[:120]}")
