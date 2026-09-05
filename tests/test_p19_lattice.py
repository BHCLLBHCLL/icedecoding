# -*- coding: utf-8 -*-
"""P19-1: lattice-derived surface sampling - partial same-column overlap.

The oracle fingerprint (P18j): same-column cylinders' surface x-sets overlap
PARTIALLY (27-41%), not 0% (independent rings) and not 100% (identical grids).
This test locks the replicated mechanism: global shared lattice sampling ->
radial projection -> partial snap (snap_tol) with per-cylinder phase stagger.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from ice_hdm import lattice_surface_nodes

ROWS = (0.25, 0.30, 0.35)
CX = 0.15
BEST = dict(base=0.02, depth=4, phase=(0.0, 0.008), band=1.0,
            snap_tol=0.4, stagger=0.7)


def _cyls():
    return [{"p1": np.array([CX, y, 0.13]), "p2": np.array([CX, y, 0.19]),
             "r1": 0.012, "r2": 0.02} for y in ROWS]


def _annulus(pts, cy):
    rho = np.hypot(pts[:, 0] - CX, pts[:, 1] - cy)
    m = (pts[:, 2] >= 0.13) & (pts[:, 2] <= 0.19) & \
        (rho > 0.005) & (rho < 0.035)
    return pts[m]


def _overlaps():
    pts = lattice_surface_nodes(_cyls(), **BEST)
    sets = {}
    for cy in ROWS:
        a = _annulus(pts, cy)
        sets[cy] = (set(np.round(a[:, 0], 12)),
                    set(np.round(a[:, 1], 12)))
    ov = []
    for i, c1 in enumerate(ROWS):
        for c2 in ROWS[i + 1:]:
            ox = len(sets[c1][0] & sets[c2][0]) / float(max(len(sets[c1][0]), 1))
            oy = len(sets[c1][1] & sets[c2][1]) / float(max(len(sets[c1][1]), 1))
            ov.append((ox, oy))
    return pts, sets, ov


def test_partial_overlap_not_zero_or_full():
    pts, sets, ov = _overlaps()
    xs = [len(sets[c][0]) for c in ROWS]
    # partial sharing: at least one pair overlaps strictly between 0 and 60%
    assert any(0.01 < o[0] < 0.6 for o in ov), ov
    # every column has a real population of distinct positions
    assert all(x > 100 for x in xs), xs


def test_per_column_magnitude_matches_oracle():
    pts, sets, ov = _overlaps()
    xs = sorted(len(sets[c][0]) for c in ROWS)
    # oracle annulus per-column distinct x ~ 650-1000 (P18j annulus_xy)
    assert 400 < xs[0] and xs[-1] < 2500, xs


def test_finer_lattice_gives_finer_spectrum():
    pts3 = lattice_surface_nodes(_cyls(), base=0.02, depth=3,
                                 phase=(0.0, 0.008), band=1.0,
                                 snap_tol=0.4, stagger=0.7)
    pts4 = lattice_surface_nodes(_cyls(), **BEST)
    x3 = len(set(np.round(pts3[:, 0], 12)))
    x4 = len(set(np.round(pts4[:, 0], 12)))
    assert x4 > x3


def test_deterministic():
    a = lattice_surface_nodes(_cyls(), **BEST)
    b = lattice_surface_nodes(_cyls(), **BEST)
    assert np.array_equal(a, b)


def test_empty_cylinders():
    out = lattice_surface_nodes([])
    assert out.shape == (0, 3)
