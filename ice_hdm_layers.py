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
    L = float(hi) - float(lo)
    if L <= 0:
        return np.zeros(0)
    cap = L if cap is None else float(cap)
    chain = []
    cell = float(g0)
    rem = L
    while rem >= 2.0 * cell - 1e-15:
        chain.append(cell)
        rem -= 2.0 * cell
        cell = min(cell * ratio, cap)
    mid = []
    if rem > 1e-15:
        k = max(1, int(np.ceil(rem / cap - 1e-12)))
        mid = [rem / k] * k
    left = []
    c = float(lo)
    for w in chain:
        c += w
        left.append(c)
    right = []
    c = float(hi)
    for w in chain:
        c -= w
        right.append(c)
    base = float(lo) + sum(chain)
    stop = float(hi) - sum(chain)
    mids = []
    c = base
    for w in mid[:-1] if mid else []:
        c += w
        mids.append(c)
    pos = left + mids + right
    return np.unique(np.round(np.array(pos), 12))
