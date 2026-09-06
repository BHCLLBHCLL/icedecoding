# -*- coding: utf-8 -*-
"""Phase J1a: layered-HDM architecture forensics + 1D graded-chain law."""
import os
import sys
from collections import Counter

import numpy as np

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ice_hdm_layers import graded_chain, chain_asym

JDIR = os.path.join("D:", os.sep, "training", "icepak", "10-1transient")
HAS_ORACLE = os.path.isdir(JDIR) and os.path.exists(
    os.path.join(JDIR, "grid_output"))


def test_graded_chain_three_confirmed_segments():
    """The exact two-sided law on the three oracle-confirmed segments."""
    a = graded_chain(0.05, 0.12, 5e-3, 2.0, 2e-2)
    assert np.allclose(a, [0.055, 0.065, 0.085, 0.105, 0.115], atol=1e-12)
    b = graded_chain(0.13, 0.19, 5e-3, 2.0, 2e-2)
    assert np.allclose(b, [0.135, 0.145, 0.16, 0.175, 0.185], atol=1e-12)
    c = graded_chain(0.05, 0.1, 5e-3, 2.0, 2e-2)
    assert np.allclose(c, [0.055, 0.065, 0.085, 0.095], atol=1e-12)


def test_chain_asym_pair_growth():
    """Equal per-side g0 grows in synchronised pairs (J1b pair fix)."""
    got = chain_asym(0.18, 0.22, 5e-3, 5e-3, cap=2e-2)
    assert np.allclose(got, [0.185, 0.195, 0.205, 0.215], atol=1e-12)


def test_chain_asym_fitted_decompositions():
    """The four quad-adjacent skeleton segments (fitted internal anchors,
    per-side g0) reproduce the oracle lines exactly."""
    cases = [
        (0.12, 0.18, [(0.12, 0.17, 2.5e-3, 1e-2), (0.17, 0.18, 5e-3, 5e-3)],
         [0.1225, 0.1275, 0.1375, 0.14875, 0.16, 0.17, 0.175]),
        (0.22, 0.28, [(0.22, 0.23, 5e-3, 5e-3), (0.23, 0.28, 1e-2, 2.5e-3)],
         [0.225, 0.23, 0.24, 0.25125, 0.2625, 0.2725, 0.2775]),
        (0.22, 0.28, [(0.22, 0.27, 2.5e-3, 1e-2), (0.27, 0.28, 5e-3, 5e-3)],
         [0.2225, 0.2275, 0.2375, 0.24875, 0.26, 0.27, 0.275]),
        (0.32, 0.38, [(0.32, 0.325, 2.5e-3, 5e-3),
                      (0.325, 0.3516666666666667, 5e-3, 2e-2),
                      (0.3516666666666667, 0.38, 2e-2, 5e-3)],
         [0.325, 0.33, 0.3408333333333333, 0.3516666666666667,
          0.36333333333333334, 0.375]),
    ]
    for lo, hi, subs, expect in cases:
        got = [lo, hi]
        for sa, sb, g0l, g0r in subs:
            got.extend([sa, sb])
            got.extend(chain_asym(sa, sb, g0l, g0r, cap=2e-2).tolist())
        got = np.unique(np.round(np.array(got), 12))
        assert np.allclose(got, [lo] + expect + [hi], atol=1e-12), (lo, got)


def test_graded_chain_properties():
    """Palindrome spacing, cap respect, remainder equal split."""
    lines = graded_chain(0.0, 0.09, 1e-2, 2.0, 3e-2)
    # left chain 1e-2, 2e-2 (cap 3e-2), rem 0.09-0.06=0.03 -> 1 mid cell
    assert np.allclose(lines, [0.01, 0.03, 0.06, 0.08], atol=1e-12)
    # degenerate: g0 larger than span -> no interior lines
    assert len(graded_chain(0.0, 0.004, 5e-3, 2.0, 2e-2)) == 0


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_oracle_layer_taxonomy():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    cnt = Counter(z.tolist())
    assert len(nodes) == 62626
    assert sum(cnt.values()) == len(nodes)
    hist = Counter(cnt.values())
    assert hist[1710] == 13 and hist[3212] == 7 and hist[1470] == 2
    assert hist[1932] == 1 and hist[1] == 1
    # coarse layers share one identical 2D grid
    coarse_z = [zz for zz, c in cnt.items() if c == 1710]
    subs = [nodes[np.abs(z - zz) < 1e-9][:, :2] for zz in coarse_z]
    s0 = set(map(tuple, np.round(subs[0], 12)))
    for s in subs[1:]:
        assert set(map(tuple, np.round(s, 12))) == s0
    assert len(s0) == 1710


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_oracle_graded_law_on_z_segments():
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = set(np.round(nodes[:, 2], 12).tolist())
    for lo, hi in ((0.05, 0.12), (0.13, 0.19)):
        for v in graded_chain(lo, hi, 5e-3, 2.0, 2e-2):
            assert round(float(v), 12) in z


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_oracle_skeleton_regeneration():
    """J1b milestone: the 38x45 coarse grid regenerates exactly from the
    law (both axes and the cartesian product)."""
    from tools.hdm_j1b_regenerate import (X_ANCHORS, X_OVERRIDES,
                                          Y_ANCHORS, Y_OVERRIDES, skeleton)
    from tools.hdm_graded_lattice import load_oracle
    nodes = load_oracle()
    z = np.round(nodes[:, 2], 12)
    sub = nodes[np.abs(z - 0.25) < 1e-9]
    gx = skeleton(X_ANCHORS, X_OVERRIDES)
    gy = skeleton(Y_ANCHORS, Y_OVERRIDES)
    assert np.array_equal(gx, np.unique(np.round(sub[:, 0], 12)))
    assert np.array_equal(gy, np.unique(np.round(sub[:, 1], 12)))
    prod = set(map(tuple, np.round(
        np.array([(x, y) for x in gx for y in gy]), 12)))
    assert prod == set(map(tuple, np.round(sub[:, :2], 12)))
    assert len(prod) == 1710


@pytest.mark.skipif(not HAS_ORACLE, reason="oracle project not available")
def test_oracle_cone_surface_radius_scaled_rings():
    """Cone-exact nodes ~ 7 z-levels x radius-scaled angular counts."""
    from tools.hdm_graded_lattice import load_oracle
    from ice_hdm import model_cylinders
    from icepak_parser.project import IcepakProject
    nodes = load_oracle()
    cyls = model_cylinders(IcepakProject(JDIR).model)
    m = np.zeros(len(nodes), dtype=bool)
    for c in cyls:
        p1, p2 = c["p1"], c["p2"]
        u = p2 - p1
        h = float(np.linalg.norm(u))
        u = u / h
        d = (nodes - p1) @ u
        w = nodes - p1 - d[:, None] * u
        rho = np.linalg.norm(w, axis=1)
        rt = c["r1"] + (c["r2"] - c["r1"]) * np.clip(d / h, 0.0, 1.0)
        m |= (np.abs(rho - rt) < 1e-7) & (d >= -1e-9) & (d <= h + 1e-9)
    assert 1400 <= int(m.sum()) <= 1700
