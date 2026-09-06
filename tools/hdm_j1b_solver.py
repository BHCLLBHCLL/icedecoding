# -*- coding: utf-8 -*-
"""J1b solver v2: segment fitting with the verified symmetric law
(graded_chain) plus an asymmetric/internal-anchor search for the
failing segments; cluster-layer circle-projection family test."""
import json
import os
import sys
from collections import Counter
from itertools import product

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ice_hdm_layers import graded_chain

JOB = "10-1transient"
JDIR = os.path.join("D:", os.sep, "training", "icepak", JOB)
H = 0.005
GB = 0.02


def load_oracle():
    from tools.grid_positions import extract_nodes
    nm = [f for f in os.listdir(JDIR) if f.endswith(".nodemap")]
    raw = open(os.path.join(JDIR, nm[0]), "rb").read()
    n = raw.count(bytes([10]))
    if not raw.endswith(bytes([10])):
        n += 1
    r = extract_nodes(os.path.join(JDIR, "grid_output"), n)
    return r[0]


def chain_asym(lo, hi, g0L, g0R, ratio=2.0, cap=GB):
    """Asymmetric two-sided chain: repeatedly the side with the smaller
    next cell takes it while rem >= (its cell + other side's next cell);
    remainder split into ceil(rem/cap) equal middle cells."""
    L = hi - lo
    rem = L
    cl, cr = g0L, g0R
    left, right = [], []
    while True:
        if cl <= cr:
            if rem < cl + cr - 1e-15:
                break
            lo_c = lo + sum(left) + cl
            left.append(cl)
            rem -= cl
            cl = min(cl * ratio, cap)
        else:
            if rem < cl + cr - 1e-15:
                break
            hi_c = hi - sum(right) - cr
            right.append(cr)
            rem -= cr
            cr = min(cr * ratio, cap)
    base = lo + sum(left)
    stop = hi - sum(right)
    mids = []
    if rem > 1e-15:
        k = max(1, int(np.ceil(rem / cap - 1e-12)))
        c = base
        for w in ([rem / k] * k)[:-1]:
            c += w
            mids.append(c)
    lines = left + mids + [hi - sum(right)] + \
        [hi - sum(right[:i + 1]) for i in range(1, len(right))]
    return np.unique(np.round(np.array(sorted(set(lines))), 12))


def main():
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    layer = lambda zz: nodes[np.abs(z - zz) < 1e-9]
    out = {}

    sub = layer(0.25)
    xs = np.unique(np.round(sub[:, 0], 12))
    ys = np.unique(np.round(sub[:, 1], 12))
    out["nx"], out["ny"] = len(xs), len(ys)

    def fit_segment(name, a, b, obs, extra_anchors):
        rec = {"seg": [a, b], "obs": [round(v, 6) for v in obs]}
        # 1. symmetric law
        for g0 in (H / 2, H, GB / 2, GB / 4):
            got = graded_chain(a, b, g0, 2.0, GB)
            if len(got) == len(obs) and np.allclose(got, obs, atol=1e-12):
                rec["fit_sym"] = g0
                return rec
        # 2. internal anchors x per-side g0 asymmetric
        best = []
        anchors = [a] + sorted(set(x for x in extra_anchors
                                   if a + 1e-9 < x < b - 1e-9)) + [b]
        g0s = (H / 2, H, GB / 2, GB / 4)
        for split in range(1, 2 ** (len(anchors) - 2)):
            subs = [anchors[0]]
            for bit in range(len(anchors) - 2):
                if split >> bit & 1:
                    subs.append(anchors[bit + 1])
            subs.append(anchors[-1])
            g0s_all = []
            ok = True
            for i in range(len(subs) - 1):
                sa, sb = subs[i], subs[i + 1]
                o = [v for v in obs if sa + 1e-12 < v < sb - 1e-12]
                found = None
                for g0L, g0R in product(g0s, g0s):
                    got = chain_asym(sa, sb, g0L, g0R)
                    if len(got) == len(o) and np.allclose(got, o,
                                                          atol=1e-12):
                        found = (sa, sb, g0L, g0R)
                        break
                if found is None:
                    ok = False
                    break
                g0s_all.append(found)
            if ok:
                best.append((tuple(round(s, 4) for s in subs), g0s_all))
        rec["fit_asym"] = best[:4]
        return rec

    AX = [0.05, 0.1, 0.12, 0.18, 0.22, 0.28, 0.3, 0.35]
    AY = [0.1, 0.2, 0.22, 0.28, 0.32, 0.38, 0.4, 0.55]
    EXTRA = [0.13, 0.17, 0.175, 0.225, 0.23, 0.27, 0.33, 0.37, 0.375,
             0.15, 0.25, 0.16, 0.24, 0.14, 0.26]
    for name, vals, anchors in (("x", xs, AX), ("y", ys, AY)):
        segs = []
        for i in range(len(anchors) - 1):
            a, b = anchors[i], anchors[i + 1]
            obs = [v for v in vals if a + 1e-12 < v < b - 1e-12]
            segs.append(fit_segment(name, a, b, obs, EXTRA))
        out[name] = segs

    # ---- cluster layer families ----
    cnt = Counter(z.tolist())
    cluster = sorted(zz for zz, c in cnt.items()
                     if 20 < c < 600 and (0.1204 < zz < 0.1299 or
                                          0.1921 < zz < 0.201))
    cl = np.array(cluster)
    fits = []
    for n in range(16, 96):
        th = 2 * np.pi * np.arange(0, n) / n
        for r in np.arange(0.008, 0.0205, 0.0005):
            d1 = r * (1 - np.cos(th))
            d2 = r * np.sin(th)
            for d, z0, sgn in ((d1, 0.13, -1), (d1, 0.19, +1),
                               (d2, 0.13, -1), (d2, 0.19, +1)):
                cand = np.unique(np.round(z0 + sgn * d, 12))
                lo, hi = (0.1204, 0.1299) if z0 == 0.13 else (0.1921, 0.201)
                cand = cand[(cand > lo) & (cand < hi)]
                if len(cand) < 3:
                    continue
                hit = np.isin(np.round(cand, 12), np.round(cl, 12)).sum()
                fits.append((int(hit), int(len(cand)), n, round(r, 4),
                             "1-cos" if d is d1 else "sin",
                             z0, sgn))
    fits.sort(key=lambda t: (-t[0] / max(t[1], 1), -t[0]))
    out["cluster_family_top"] = fits[:10]
    out["cluster_n"] = len(cluster)

    print(json.dumps(out, indent=1, default=float))
    json.dump(out, open(os.path.join(ROOT, "tools", "probe_work",
                                     "j1b_solver2.json"), "w",
                        encoding="utf-8"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
