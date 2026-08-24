# -*- coding: utf-8 -*-
from collections import Counter

model_path = r"D:\training\icepak\10-1transient\model"
mat_path = r"D:\training\icepak\10-1transient\materials_from_libraries"

def read_lines(path):
    with open(path, "r", encoding="latin-1") as f:
        return f.read().splitlines()

model_lines = read_lines(model_path)
mat_lines = read_lines(mat_path)

enc_model = [l[4:] for l in model_lines if l.startswith("Il!!")]
enc_mat = [l[4:] for l in mat_lines if l.startswith("Il!!")]

print(f"model: {len(enc_model)} encoded lines, materials: {len(enc_mat)} encoded lines")

all_chars = Counter()
for l in enc_model + enc_mat:
    all_chars.update(l)
print(f"\ncharset ({len(all_chars)} distinct):")
print("".join(sorted(all_chars.keys(), key=ord)))
print(f"\ntop20 freq: {all_chars.most_common(20)}")

lens = [len(l) for l in enc_model]
print(f"\nline len: min={min(lens)}, max={max(lens)}")

line_freq = Counter(enc_model + enc_mat)
print("\nmost common lines (top15):")
for line, cnt in line_freq.most_common(15):
    print(f"  {cnt:3d}x len={len(line):3d} |{line}|")

print("\n=== groups by first 8 chars ===")
groups = {}
for l in set(enc_model + enc_mat):
    key = l[:8]
    groups.setdefault(key, []).append(l)
for key, ls in sorted(groups.items(), key=lambda x: -len(x[1]))[:10]:
    print(f"  prefix {key!r}: {len(ls)} distinct lines")
    for l in sorted(ls, key=len)[:3]:
        print(f"      len={len(l)} |{l}|")
