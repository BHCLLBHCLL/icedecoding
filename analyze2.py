# -*- coding: utf-8 -*-
"""深度密码分析：测试位置相关性"""
import os, glob
from collections import Counter, defaultdict

# 收集所有项目的model文件encoded lines
lines = []
for proj in glob.glob(r"D:\training\icepak\*"):
    mp = os.path.join(proj, "model")
    if os.path.isfile(mp):
        with open(mp, encoding="latin-1") as f:
            for l in f.read().splitlines():
                if l.startswith("Il!!"):
                    lines.append(l[4:])

print(f"total encoded lines: {len(lines)}")
total_chars = sum(len(l) for l in lines)
print(f"total chars: {total_chars}")

# 频率分析
freq = Counter()
for l in lines:
    freq.update(l)
print("\ncipher char freq (top 30):")
for c, n in freq.most_common(30):
    print(f"  {c!r}: {n} ({100*n/total_chars:.1f}%)")

# 搜索重复子串(>=6 chars)及其出现位置
substr_positions = defaultdict(list)
for li, l in enumerate(lines):
    for length in (6,):
        for i in range(len(l) - length + 1):
            substr_positions[l[i:i+length]].append((li, i))

# 找出在多个不同偏移出现的子串
multi_offset = {}
for s, positions in substr_positions.items():
    offsets = set(p[1] for p in positions)
    if len(positions) >= 3 and len(offsets) >= 2:
        multi_offset[s] = positions

print(f"\n重复>=3次且出现在不同偏移的6-char子串数: {len(multi_offset)}")
# 展示最强的例子
by_count = sorted(multi_offset.items(), key=lambda x: -len(x[1]))[:15]
for s, positions in by_count:
    offsets = Counter(p[1] for p in positions)
    print(f"  {s!r}: {len(positions)}x at offsets {dict(offsets)}")
