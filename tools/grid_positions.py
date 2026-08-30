# -*- coding: utf-8 -*-
"""P18: extract EXACT oracle node positions from binary grid_output.

Record hypothesis (P12): big-endian 32B strides
[BE int32 marker 0x6baf1c32][BE int32 counter][double x][double y][double z]
with counters 0..N-1 contiguous.  Locates the section by scanning, then
exports per-job node coordinates + per-axis line structure analysis."""
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MARKER = 0x6BAF1C32


def _be(data, off, fmt):
    return struct.unpack_from(fmt, data, off)


def find_node_section(data):
    """Node section: [BE marker 0x6baf1c32][BE counter 0] then 28-byte
    records [double x][double y][double z][BE int32 counter], counters
    consecutive.  The header also carries the node count as BE int32 at
    offset 24 (cross-check).  Returns (record_offset, 28, n_nodes_hdr)."""
    off = None
    # primary: records follow the header; locate the counter run 0,1,2...
    for o in range(56, 200, 4):
        if _be(data, o, ">i")[0] != 0:
            continue
        if o + 56 > len(data):
            continue
        if _be(data, o + 28, ">i")[0] == 1 and \
                _be(data, o + 56, ">i")[0] == 2:
            off = o
            break
    if off is None:
        return None
    n_hdr = _be(data, 24, ">i")[0]
    # records: [BE counter][double x][double y][double z], counters 0..N-1
    k = 0
    p = off
    while p <= len(data) - 28 and _be(data, p, ">i")[0] == k:
        k += 1
        p += 28
    return (off, k, n_hdr)


def extract_nodes(path, n_nodes):
    with open(path, "rb") as fh:
        data = fh.read()
    sec = find_node_section(data)
    if sec is None:
        return None, None
    off, k, n_hdr = sec
    if k < n_nodes:
        return None, sec
    pts = np.empty((n_nodes, 3), dtype=np.float64)
    for i in range(n_nodes):
        o = off + i * 28
        cnt = _be(data, o, ">i")[0]
        if cnt != i:
            return None, sec
        x, y, z = _be(data, o + 4, ">ddd")
        pts[i] = (x, y, z)
    return pts, sec


def axis_analysis(pts):
    out = {}
    for ax, name in enumerate(("x", "y", "z")):
        col = np.sort(np.unique(np.round(pts[:, ax], 12)))
        d = np.diff(col)
        out[name] = {
            "lines": int(len(col)),
            "min": float(col[0]), "max": float(col[-1]),
            "spacing_min": float(d.min()),
            "spacing_max": float(d.max()),
            "spacing_mean": float(d.mean()),
            "spacing_median": float(np.median(d)),
            "unique_spacings": int(len(np.unique(np.round(d, 12)))),
            "first": [float(v) for v in col[:12]],
        }
    return out


def main(argv):
    job = argv[1] if len(argv) > 1 else "10-1transient"
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    go = os.path.join(jdir, "grid_output")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n_nodes = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n_nodes += 1
    print("job", job, "nodes", n_nodes)
    pts, sec = extract_nodes(go, n_nodes)
    if pts is None:
        print("SECTION FAIL", sec)
        return 1
    print("section offset", sec[0], "first counter", sec[1], "contig", sec[2])
    an = axis_analysis(pts)
    for name, a in an.items():
        print(name, "lines", a["lines"], "spacing min/med/max %.8g/%.8g/%.8g"
              % (a["spacing_min"], a["spacing_median"], a["spacing_max"]),
              "uniq", a["unique_spacings"])
        print("   first:", [round(v, 6) for v in a["first"]])
    out = {"job": job, "nodes": n_nodes, "section": list(sec),
           "axes": an, "bounds": {"min": pts.min(0).tolist(),
                                  "max": pts.max(0).tolist()}}
    pout = os.path.join(ROOT, "tools", "probe_work",
                        "pos_" + job.replace(" ", "_") + ".json")
    json.dump(out, open(pout, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print("saved", pout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
