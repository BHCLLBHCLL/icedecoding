# -*- coding: utf-8 -*-
"""P18f: where are the oracle's x/y positions refined? Position histogram."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load():
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", "10-1transient")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    return pts


def main():
    pts = load()
    # x-axis: cylinders at cx in {0.15,0.2,0.25}, block x [0.1,0.3], quad [0.12,0.18]
    for ax, name in enumerate(("x", "y")):
        vals = np.unique(np.round(pts[:, ax], 12))
        # histogram into 0.05 bins
        bins = np.arange(0, 0.6 + 1e-9, 0.05)
        hist, edges = np.histogram(vals, bins=bins)
        print("==", name, "distinct", len(vals))
        for i, h in enumerate(hist):
            print("  [%.2f,%.2f]: %d" % (edges[i], edges[i + 1], h))
    # min spacing per region (level proxy) — x near cylinder centres vs far
    for ax, name in enumerate(("x", "y")):
        vals = np.unique(np.round(pts[:, ax], 12))
        d = np.diff(vals)
        dpos = d[d > 1e-9]
        # level of the SPACING: log2(0.02/d)
        lv = np.round(np.log2(0.02003 / np.clip(dpos, 1e-12, None))).astype(int)
        uniq, cnts = np.unique(np.clip(lv, 0, 12), return_counts=True)
        print(name, "spacing-level hist:", dict(zip(uniq.tolist(), cnts.tolist())))


if __name__ == "__main__":
    main()
