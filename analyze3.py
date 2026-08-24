# -*- coding: utf-8 -*-
"""位置频率分析推导Vigenere密钥"""
import os, glob
from collections import Counter, defaultdict

lines = []
for proj in glob.glob(r"D:\training\icepak\*"):
    for fname in ("model", "materials_from_libraries"):
        mp = os.path.join(proj, fname)
        if os.path.isfile(mp):
            with open(mp, encoding="latin-1") as f:
                for l in f.read().splitlines():
                    if l.startswith("Il!!"):
                        lines.append(l[4:])

print(f"total encoded lines: {len(lines)}")

# 精确字符集
chars = set()
for l in lines:
    chars.update(l)
print(f"distinct chars: {len(chars)}")
print(f"char codes: {sorted(ord(c) for c in chars)}")

# 位置频率
pos_freq = defaultdict(Counter)
for l in lines:
    for i, c in enumerate(l):
        pos_freq[i][c] += 1

# 显示前40个位置的top字符
print("\npos | top3 chars (freq%)  | n_lines")
for p in range(40):
    if p in pos_freq:
        total = sum(pos_freq[p].values())
        top3 = pos_freq[p].most_common(3)
        tops = ", ".join(f"{c!r}:{100*n/total:.0f}%" for c, n in top3)
        print(f"{p:3d} | {tops:30s} | {total}")

# 位置0的详细分布
print("\nposition 0 full distribution:")
for c, n in pos_freq[0].most_common(20):
    print(f"  {c!r}: {n}")
