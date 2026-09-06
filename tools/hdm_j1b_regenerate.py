# -*- coding: utf-8 -*-
"""J1b: regenerate the 10-1 coarse skeleton (38 x 45 graded grid) from
the recovered 1D law.

Per-axis anchors = domain ends + object faces + the interior-facing
cylinder base-extent faces (cx+/-r, cy+/-r — only the faces looking
into the 3x3 array appear in the oracle skeleton).  Segments use the
symmetric law (g0 = grid_size_h) except the four quad-adjacent segments,
which use fitted internal-anchor decompositions (chain_asym, per-side
g0) — recorded verbatim; their full meta-rule is a J1c open item.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm_layers import chain_asym, graded_chain

H = 0.005
GB = 0.02
JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
OUT = os.path.join(ROOT, "tools", "probe_work", "j1b_regenerate.json")

# fitted internal-anchor decompositions (tools/hdm_j1b_solver3.py)
X_OVERRIDES = {
    (0.12, 0.18): [((0.12, 0.17), (H / 2, GB / 2)),
                   ((0.17, 0.18), (H, H))],
    (0.22, 0.28): [((0.22, 0.23), (H, H)),
                   ((0.23, 0.28), (GB / 2, H / 2))],
}
Y_OVERRIDES = {
    (0.22, 0.28): [((0.22, 0.27), (H / 2, GB / 2)),
                   ((0.27, 0.28), (H, H))],
    (0.32, 0.38): [((0.32, 0.325), (H / 2, H)),
                   ((0.325, 0.3516666666666667), (H, GB)),
                   ((0.3516666666666667, 0.38), (GB, H))],
}
X_ANCHORS = [0.05, 0.1, 0.12, 0.18, 0.22, 0.28, 0.3, 0.35]
Y_ANCHORS = [0.1, 0.2, 0.22, 0.28, 0.32, 0.38, 0.4, 0.55]


def skeleton(anchors, overrides):
    lines = list(anchors)
    for i in range(len(anchors) - 1):
        a, b = anchors[i], anchors[i + 1]
        if (a, b) in overrides:
            for (sa, sb), (g0L, g0R) in overrides[(a, b)]:
                lines.extend([sa, sb])
                lines.extend(chain_asym(sa, sb, g0L, g0R, cap=GB).tolist())
        else:
            lines.extend(graded_chain(a, b, H, 2.0, GB).tolist())
    return np.unique(np.round(np.array(lines), 12))


def main():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    sub = nodes[np.abs(z - 0.25) < 1e-9]
    ox = np.unique(np.round(sub[:, 0], 12))
    oy = np.unique(np.round(sub[:, 1], 12))

    gx = skeleton(X_ANCHORS, X_OVERRIDES)
    gy = skeleton(Y_ANCHORS, Y_OVERRIDES)
    rec = {
        "x": {"generated": len(gx), "oracle": len(ox),
              "exact": bool(len(gx) == len(ox) and
                            np.array_equal(gx, ox)),
              "missing": [float(v) for v in np.setdiff1d(ox, gx)],
              "extra": [float(v) for v in np.setdiff1d(gx, ox)]},
        "y": {"generated": len(gy), "oracle": len(oy),
              "exact": bool(len(gy) == len(oy) and
                            np.array_equal(gy, oy)),
              "missing": [float(v) for v in np.setdiff1d(oy, gy)],
              "extra": [float(v) for v in np.setdiff1d(gy, oy)]},
    }
    # coarse layer = full cartesian product?
    prod = np.array([(x, y) for x in gx for y in gy])
    os_ = set(map(tuple, np.round(sub[:, :2], 12)))
    ps = set(map(tuple, np.round(prod, 12)))
    rec["coarse_grid_product"] = {
        "generated_nodes": len(ps), "oracle_nodes": len(os_),
        "exact": bool(ps == os_)}
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
