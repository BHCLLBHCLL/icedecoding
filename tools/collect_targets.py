# -*- coding: utf-8 -*-
"""P16 helper: collect authoritative per-job oracle node/cell targets.

Ground truth for NODES = line count of *.nodemap (one line per node);
cross-check vs ASCII Fluent cas zone header (10 ... count 1) where the
zone count is HEX (Icepak writes hex, e.g. f4a2 = 62626).  Also parse all
zone headers of the current model's cas and the binary grid_output size.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = r"D:\training\icepak"

ZONE = re.compile(
    r"\(\s*(10|12|13|18)\s+\(\s*0\s+1\s+([0-9a-fA-F]+)\s+[01]\s*\)\)")


def _count_lines(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return data.count(b"\n") - (1 if data.endswith(b"\n") else 0)


def nodemap_counts(jdir):
    out = []
    for n in sorted(os.listdir(jdir)):
        if n.endswith(".nodemap"):
            p = os.path.join(jdir, n)
            out.append((n, _count_lines(p), os.path.getsize(p)))
    return out


def cas_zones(jdir):
    out = []
    for n in sorted(os.listdir(jdir)):
        if not n.endswith(".cas"):
            continue
        p = os.path.join(jdir, n)
        try:
            text = io.open(p, "r", encoding="utf-8", errors="replace"
                           ).read(2 * 1024 * 1024)
        except OSError:
            continue
        zones = []
        for m in ZONE.finditer(text):
            kind = int(m.group(1))
            cnt = int(m.group(2), 16)
            zones.append((kind, cnt))
        out.append({"cas": n, "size": os.path.getsize(p), "zones": zones})
    return out


def grid_output_size(jdir):
    p = os.path.join(jdir, "grid_output")
    if os.path.exists(p):
        return os.path.getsize(p)
    return None


def grouped(jdir):
    """kept small: return dict with the main cas zone table."""
    cz = cas_zones(jdir)
    main = None
    for c in cz:
        if c["cas"].endswith("00.cas") and not c["cas"].endswith("nc.cas"):
            main = c
            break
    if main is None and cz:
        main = cz[0]
    return {"nodemaps": nodemap_counts(jdir), "cas": cz,
            "main_cas": main, "grid_output": grid_output_size(jdir)}


def main(job_names):
    for name in job_names:
        jdir = os.path.join(ROOT, name)
        if not os.path.isdir(jdir):
            print(name, "(missing)")
            continue
        info = grouped(jdir)
        print("==", name, "grid_output", info["grid_output"])
        for n, lines, sz in info["nodemaps"]:
            print("   nodemap", n, "lines", lines, "bytes", sz)
        for czz in info["cas"]:
            parts = " ".join("%s:%d" % (k, c) for k, c in czz["zones"])
            print("   cas", czz["cas"], czz["size"], parts)


if __name__ == "__main__":
    args = sys.argv[1:] or [n for n in sorted(os.listdir(ROOT))
                            if os.path.isdir(os.path.join(ROOT, n))]
    main(args)
