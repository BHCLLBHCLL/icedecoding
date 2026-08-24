# -*- coding: utf-8 -*-
"""列出所有项目的object类型和名称"""
import os, glob, re

for proj in sorted(glob.glob(r"D:\training\icepak\*")):
    mp = os.path.join(proj, "model")
    if not os.path.isfile(mp):
        continue
    types = {}
    with open(mp, encoding="latin-1") as f:
        for l in f:
            m = re.match(r"object (\S+) (.+)", l)
            if m:
                types.setdefault(m.group(1), []).append(m.group(2))
    name = os.path.basename(proj)
    summary = ", ".join(f"{t}x{len(v)}" for t, v in types.items())
    print(f"{name}: {summary}")
    # fan对象的名称详细列出
    if "fan" in types:
        for fn in types["fan"]:
            print(f"    fan: {fn}")
