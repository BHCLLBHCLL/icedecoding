# -*- coding: utf-8 -*-
"""提取5-2rf_amp中的fan对象编码行"""
import re

with open(r"D:\training\icepak\5-2rf_amp\model", encoding="latin-1") as f:
    lines = f.read().splitlines()

# 找 fan 对象
in_fan = False
fan_lines = []
for l in lines:
    if l.startswith("object fan "):
        in_fan = True
    if in_fan:
        fan_lines.append(l)
    if in_fan and l == "end object":
        break

for i, l in enumerate(fan_lines):
    print(f"{i:3d} len={len(l):4d} |{l}|")
