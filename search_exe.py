# -*- coding: utf-8 -*-
path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\icepak.exe"
with open(path, "rb") as f:
    data = f.read()
print(f"size: {len(data)}")
for pat in [b"model file encoding", b"encoding::identity", b"#@ ANSYS Icepak", b"q|sz}y~", b"cor5(#b!S0efP3+E"]:
    idx = 0
    count = 0
    while True:
        idx = data.find(pat, idx)
        if idx < 0:
            break
        count += 1
        if count <= 3:
            start = max(0, idx - 100)
            chunk = data[start:idx+200]
            txt = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"\n=== {pat!r} @ {idx} ===")
            print(f"  {txt}")
        idx += 1
    if count == 0:
        print(f"\n=== {pat!r}: NOT FOUND ===")
    else:
        print(f"  (total {count} occurrences)")
