# -*- coding: utf-8 -*-
"""P18g: decompose x/y spectra per cylinder column/row; identify base lattice."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CX = (0.15, 0.20, 0.25)
CY = (0.25, 0.30, 0.35)


def load_oracle():
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
    pts = load_oracle()
    print("== oracle decomposition ==")
    xs = np.unique(np.round(pts[:, 0], 12))
    ys = np.unique(np.round(pts[:, 1], 12))
    # per-column unique spans: cylinders at cx with r<=0.02; columns do not
    # overlap in x (gaps ~0.01): [cx-0.025, cx+0.025]
    total_x = 0
    for cx in CX:
        c = xs[(xs >= cx - 0.025) & (xs <= cx + 0.025)]
        print("column cx=%.2f: %d distinct x" % (cx, len(c)))
        total_x += len(c)
    print("sum of columns:", total_x, "(total 8190)")
    total_y = 0
    for cy in CY:
        c = ys[(ys >= cy - 0.025) & (ys <= cy + 0.025)]
        print("row cy=%.2f: %d distinct y" % (cy, len(c)))
        total_y += len(c)
    print("sum of rows:", total_y, "(total 6777)")
    # block/quad region contribution (outside cylinder spans)
    bx = xs[(xs >= 0.1) & (xs < 0.125) | (xs > 0.275) & (xs <= 0.3)]
    by = ys[(ys >= 0.2) & (ys < 0.225) | (ys > 0.375) & (ys <= 0.4)]
    print("block-edge x:", len(bx), "block-edge y:", len(by))
    # background lines
    print("background x values:", np.round(xs[(xs < 0.1) | (xs > 0.3)], 6))
    print("background y values:", np.round(ys[(ys < 0.2) | (ys > 0.4)], 6))
    # lattice identification on the x band: multiples of 0.02 and snapped
    inband = xs[(xs >= 0.1) & (xs <= 0.3)]
    for step, label in ((0.02, "0.02-exact"),
                        (0.35 / 18.0, "snapped 0.35/18"),
                        (0.01, "0.01")):
        frac = (inband / step) % 1.0
        hit = ((frac < 1e-9) | (frac > 1 - 1e-9)).mean()
        print("x band on %s lattice: %.1f%%" % (label, hit * 100))
    inband_y = ys[(ys >= 0.2) & (ys <= 0.4)]
    for step, label in ((0.02, "0.02-exact"),
                        (0.55 / 28.0, "snapped 0.55/28")):
        frac = (inband_y / step) % 1.0
        hit = ((frac < 1e-9) | (frac > 1 - 1e-9)).mean()
        print("y band on %s lattice: %.1f%%" % (label, hit * 100))


if __name__ == "__main__":
    main()
