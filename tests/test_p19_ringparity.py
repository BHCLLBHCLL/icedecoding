# -*- coding: utf-8 -*-
"""I1c: ring parity mechanism (n even/odd) + decoupled n_ang + per-axis
partial lattice snap."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ice_hdm import ring_nodes

CYL = {"p1": np.array([0.15, 0.25, 0.13]),
       "p2": np.array([0.15, 0.25, 0.19]),
       "r1": 0.012, "r2": 0.02}
KW = dict(pitch_c=0.10, z_frac=0.5, theta_stagger=False)


def _rings(**kw):
    a = dict(KW)
    a.update(kw)
    return ring_nodes([CYL], **a)


def test_ring_parity_y_spectrum():
    """Even n self-pairs sin(pi-x)=sin x -> y spectrum ~half of odd n."""
    even = _rings(n_ang=62)
    odd = _rings(n_ang=63)
    dy_even = len(np.unique(np.round(even[:, 1], 12)))
    dy_odd = len(np.unique(np.round(odd[:, 1], 12)))
    assert dy_odd > 1.6 * dy_even
    # x spectrum is nearly unaffected by parity (cos pairs k<->n-k always)
    dx_even = len(np.unique(np.round(even[:, 0], 12)))
    dx_odd = len(np.unique(np.round(odd[:, 0], 12)))
    assert abs(dx_odd - dx_even) < 0.35 * dx_even


def test_ring_n_decoupled_from_pitch():
    """n_ang overrides int(2*pi/pitch_c): exactly n samples per z level."""
    r = _rings(n_ang=50)
    nz = len(np.unique(np.round(r[:, 2], 9)))
    assert len(r) == 50 * nz
    # default (pitch derived) differs from the override
    r0 = _rings()
    n0 = int(2 * np.pi / 0.10)
    assert len(r0) == n0 * len(np.unique(np.round(r0[:, 2], 9)))


def test_ring_snap_partial_merge():
    """Per-axis partial lattice snap: y merges monotonically, x untouched
    when tol_x=0, tol=0 == snap off."""
    off = _rings(n_ang=66)
    s0 = _rings(n_ang=66, snap_g=2e-4, snap_tol_y=0.0)
    assert np.array_equal(off, s0)
    dx_off = len(np.unique(np.round(off[:, 0], 12)))
    prev = len(np.unique(np.round(off[:, 1], 12)))
    for ty in (0.02, 0.05, 0.1):
        r = _rings(n_ang=66, snap_g=2e-4, snap_tol_y=ty)
        dy = len(np.unique(np.round(r[:, 1], 12)))
        assert dy < prev
        prev = dy
        assert len(np.unique(np.round(r[:, 0], 12))) == dx_off


def test_ring_deterministic():
    a = _rings(n_ang=66, snap_g=2e-4, snap_tol_y=0.08)
    b = _rings(n_ang=66, snap_g=2e-4, snap_tol_y=0.08)
    assert np.array_equal(a, b)


def test_build_ring_passthrough_signature():
    """build() exposes the I1c ring knobs (n_ang/snap pass-through)."""
    import inspect
    import ice_hdm
    pars = inspect.signature(ice_hdm.build).parameters
    for name in ("ring_n", "ring_snap_g", "ring_snap_tol_x",
                 "ring_snap_tol_y"):
        assert name in pars
