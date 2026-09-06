# -*- coding: utf-8 -*-
"""J1b solver v3: corrected asymmetric chain + exhaustive internal-anchor
search over the four failing skeleton segments."""
import json
import os
import sys
from itertools import combinations, product

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

H = 0.005
GB = 0.02
G0S = (H / 2, H, GB / 2, GB)


def chain_asym(lo, hi, g0L, g0R, ratio=2.0, cap=GB):
    """Two-sided chain, per-side g0; the side with the smaller next cell
    takes it while rem >= both next cells; remainder equal-split into
    ceil(rem/cap) cells (interior lines only)."""
    rem = hi - lo
    cl, cr = g0L, g0R
    left, right = [], []
    while True:
        if rem < cl + cr - 1e-15:
            break
        if cl <= cr:
            left.append(cl)
            rem -= cl
            cl = min(cl * ratio, cap)
        else:
            right.append(cr)
            rem -= cr
            cr = min(cr * ratio, cap)
    base = lo + sum(left)
    mids = []
    if rem > 1e-15:
        k = max(1, int(np.ceil(rem / cap - 1e-12)))
        c = base
        for w in ([rem / k] * k)[:-1]:
            c += w
            mids.append(c)
    rlines = [hi - sum(right[:i + 1]) for i in range(len(right) - 1, -1, -1)]
    lpos = []
    c = lo
    for w in left:
        c += w
        lpos.append(c)
    lines = lpos + mids + rlines
    return np.unique(np.round(np.array(lines), 12))


def fits(sa, sb, obs):
    o = [v for v in obs if sa + 1e-12 < v < sb - 1e-12]
    for g0L, g0R in product(G0S, G0S):
        got = chain_asym(sa, sb, g0L, g0R)
        if len(got) == len(o) and np.allclose(got, o, atol=1e-12):
            return (g0L, g0R)
    return None


def search(seg, obs, extra):
    cands = sorted(set(extra) | set(obs))
    cands = [v for v in cands if seg[0] + 1e-12 < v < seg[1] - 1e-12]
    out = []
    for k in range(0, 4):
        for combo in combinations(cands, k):
            subs = [seg[0]] + list(combo) + [seg[1]]
            sol = []
            ok = True
            for i in range(len(subs) - 1):
                f = fits(subs[i], subs[i + 1], obs)
                if f is None:
                    ok = False
                    break
                sol.append((round(subs[i], 5), round(subs[i + 1], 5), f))
            if ok:
                out.append(sol)
    return out


def main():
    segs = {
        "x[0.12,0.18]": ((0.12, 0.18),
                         [0.1225, 0.1275, 0.1375, 0.14875, 0.16, 0.17,
                          0.175],
                         [0.13, 0.14, 0.15, 0.16, 0.17, 0.175]),
        "x[0.22,0.28]": ((0.22, 0.28),
                         [0.225, 0.23, 0.24, 0.25125, 0.2625, 0.2725,
                          0.2775],
                         [0.23, 0.24, 0.25, 0.26, 0.27, 0.275]),
        "y[0.22,0.28]": ((0.22, 0.28),
                         [0.2225, 0.2275, 0.2375, 0.24875, 0.26, 0.27,
                          0.275],
                         [0.23, 0.25, 0.26, 0.27, 0.275, 0.24]),
        "y[0.32,0.38]": ((0.32, 0.38),
                         [0.325, 0.33, 0.3408333333333333, 0.3516666666666667,
                          0.36333333333333334, 0.375],
                         [0.33, 0.34, 0.35, 0.3516666666666667, 0.36,
                          0.37, 0.375]),
    }
    out = {}
    for name, (seg, obs, extra) in segs.items():
        r = search(seg, obs, extra)
        out[name] = r
        print(name, "->", len(r), "decompositions")
        for sol in r[:5]:
            print("   ", sol)
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j1b_solver3.json"), "w",
                        encoding="utf-8"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
