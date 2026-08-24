# -*- coding: utf-8 -*-
"""在所有Icepak二进制中搜索编码线索"""
import os, re, glob

base = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5"
patterns = [b"identity.", b"Il!!", b"encoding::", b"model file encoding"]

# 搜索exe和dll
for root, dirs, files in os.walk(base):
    for fn in files:
        if fn.lower().endswith((".exe", ".dll")):
            p = os.path.join(root, fn)
            try:
                with open(p, "rb") as f:
                    data = f.read()
            except Exception:
                continue
            for pat in patterns:
                idx = data.find(pat)
                if idx >= 0:
                    print(f"{fn}: {pat!r} @ {idx}")
                    # 打印上下文
                    ctx = data[max(0,idx-60):idx+100]
                    txt = ctx.decode("latin-1")
                    txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
                    print(f"   context: {txt}")
