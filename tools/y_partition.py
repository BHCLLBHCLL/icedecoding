# -*- coding: utf-8 -*-
"""Partition a distinct-axis spectrum into geometry-shell vs background."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# cylinder centers for 10-1transient
CX = (0.15, 0.20, 0.25)
CY = (0.25, 0.30, 0.35)


def partition(vals, centers):
    shell = np.zeros(len(vals), dtype=bool)
    for c in centers:
        shell |= np.abs(vals - c) < 0.05
    return vals[shell], vals[~shell]


def load_oracle(job="10-1transient"):
    from tools.grid_positions import extract_nodes
    jdir = os.path.join(r"D:\training\icepak", job)
    if not os.path.isdir(jdir):
        jdir = os.path.join(r"D:\training\icepak", job, "compack-package")
    nm = [f for f in os.listdir(jdir) if f.endswith(".nodemap")]
    raw = open(os.path.join(jdir, nm[0]), "rb").read()
    n = raw.count(b"\n")
    if not raw.endswith(b"\n"):
        n += 1
    pts, sec = extract_nodes(os.path.join(jdir, "grid_output"), n)
    return pts


def main():
    pts = load_oracle()
    print("oracle distinct x/y =", len(np.unique(np.round(pts[:, 0], 12))),
          len(np.unique(np.round(pts[:, 1], 12))))
    for ax, name, centers in ((0, "x", CX), (1, "y", CY)):
        vals = np.unique(np.round(pts[:, ax], 12))
        sh, bg = partition(vals, centers)
        print("%s: total %d  shell(geometry band) %d  background %d"
              % (name, len(vals), len(sh), len(bg)))


if __name__ == "__main__":
    main()
