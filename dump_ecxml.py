# -*- coding: utf-8 -*-
path = r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\bin.win64_amd\extension\ecxml.exe"
with open(path, "rb") as f:
    data = f.read()
print(f"size: {len(data)}")
for pat in [b"Il!!", b"DecodingLookupArray"]:
    idx = 0
    while True:
        idx = data.find(pat, idx)
        if idx < 0:
            break
        print(f"\n=== {pat!r} @ {idx} ===")
        start = max(0, idx - 96)
        chunk = data[start:idx+320]
        for i in range(0, len(chunk), 32):
            c = chunk[i:i+32]
            hexpart = " ".join(f"{b:02x}" for b in c)
            txtpart = "".join(chr(b) if 32 <= b < 127 else "." for b in c)
            print(f"{start+i:8d}  {hexpart}  {txtpart}")
        idx += 1
