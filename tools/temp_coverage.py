# -*- coding: utf-8 -*-
"""P19-10b: survey fluid-temperature coverage across all jobs (any .fdat)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fluent_fdat import parse_fdat

JDIR = r"D:\training\icepak"


def find_fdat(d):
    for n in sorted(os.listdir(d)):
        if n.endswith(".fdat"):
            return os.path.join(d, n)
    return None


def main():
    for name in sorted(os.listdir(JDIR)):
        d = os.path.join(JDIR, name)
        if not os.path.isdir(d):
            continue
        fdat = find_fdat(d)
        if fdat is None:
            sub = os.path.join(d, "compack-package")
            if os.path.isdir(sub):
                fdat = find_fdat(sub)
        if fdat is None:
            continue
        pf = parse_fdat(fdat)
        cells = pf["header"].get("cells", 0)
        best = None
        for nm, args, vals in pf["fields"]:
            if "SV_T" not in nm or "SV_T_M1" in nm or len(vals) > 3 * cells:
                continue
            a = np.asarray(vals, dtype=np.float64)
            fin = np.isfinite(a) & (np.abs(a) < 1e6)
            nf = int(fin.sum())
            warm = np.isfinite(a) & (np.abs(a - 300.0) < 100.0)
            nw = int(warm.sum())
            if best is None or nw > best[1]:
                rng = ((float(a[warm].min()), float(a[warm].max()))
                       if nw else None)
                best = (nm, nw, nf, rng)
        if best is None:
            print(name, "no clean temp")
            continue
        nm, nw, nf, rng = best
        cov = nw / float(cells) * 100 if cells else 0
        print("%-22s cells=%6d warm_cells=%6d cov=%.0f%%  temp=%s" %
              (name, cells, nw, cov, rng))


if __name__ == "__main__":
    main()
