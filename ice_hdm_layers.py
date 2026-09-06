# -*- coding: utf-8 -*-
"""Phase J engine seed: the HDM layered-mesh model.

J1a forensic discovery (10-1transient): the oracle mesh is a STACK OF
z-LAYERS, each carrying a 2D adaptive x-y grid — not a 3D octree:
  - coarse layers share one identical graded 2D grid (38x45 = 1710 nodes),
  - cylinder-span layers add per-layer circle refinement (3212 nodes each),
  - transition bands hold cylinder-local cluster layers (22-462 nodes),
  - 150 z positions total, sums exactly to the oracle node count.

The 1D line law recovered exactly on three segments: two-sided geometric
chains (g0 = grid_size_h, ratio 2, cap = grid_size) grown simultaneously
from both anchors; when the remaining span < 2 x next cell the remainder
is split into ceil(rem/cap) EQUAL middle cells.
"""
import numpy as np


def graded_chain(lo, hi, g0, ratio=2.0, cap=None):
    """Two-sided graded line placement between anchors lo < hi.

    Both chains grow geometrically (g0, g0*ratio, ... capped at cap) and
    take their next cell only while the remaining span >= 2*cell; the
    remainder is split into ceil(rem/cap) equal middle cells.  Returns
    the interior line positions (lo/hi excluded, deduplicated).
    """
    return chain_asym(lo, hi, g0, g0, ratio=ratio,
                      cap=(hi - lo) if cap is None else cap)


def chain_asym(lo, hi, g0L, g0R, ratio=2.0, cap=None):
    """Two-sided chain with per-side g0 (J1b meta-rule: cylinder
    base-extent faces act as internal anchors and the sub-segments use
    asymmetric start cells).

    The side with the smaller next cell takes it while the remaining
    span >= both next cells; the remainder is split into
    ceil(rem/cap) equal middle cells.  Returns interior line positions.
    """
    lo = float(lo)
    hi = float(hi)
    L = hi - lo
    if L <= 0:
        return np.zeros(0)
    cap = L if cap is None else float(cap)
    rem = L
    cl, cr = float(g0L), float(g0R)
    left, right = [], []
    while rem >= cl + cr - 1e-15:
        if cl == cr:
            left.append(cl)
            right.append(cr)
            rem -= cl + cr
            cl = cr = min(cl * ratio, cap)
        elif cl < cr:
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
    c = lo
    lpos = []
    for w in left:
        c += w
        lpos.append(c)
    rlines = [hi - sum(right[:i + 1]) for i in range(len(right) - 1, -1, -1)]
    lines = lpos + mids + rlines
    return np.unique(np.round(np.array(lines), 12))
