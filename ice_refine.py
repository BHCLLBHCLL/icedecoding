# -*- coding: utf-8 -*-
"""Mesh replication: conformal refinement (AutoHex Edit/Deletion semantics) —
insert grid lines at object faces and subdivide object interiors so the
structured grid reaches Icepak-like magnitudes (target-cell matching)."""
import math

import numpy as np

from ice_mesh import MeshResult, classify_cells, generate_mesh


def merged_axis(base, cuts, min_spacing):
    """Conformal axis: base positions + object-face cuts (not too close)."""
    out = list(base)
    for c in cuts:
        if c < base[0] or c > base[-1]:
            continue
        if any(abs(c - v) < min_spacing for v in out):
            continue
        out.append(c)
    out.sort()
    return out


def object_cuts(objects, axis):
    """Cut positions from object bounds along one axis."""
    cuts = []
    for name, (lo, hi) in objects:
        cuts.append(lo[axis])
        cuts.append(hi[axis])
    return cuts


def refine_axes(axes, objects, min_spacing=0.0045, interior_ratio=2):
    """Return refined axes (base + object faces + interior splits)."""
    out = []
    for ax in range(3):
        base = list(axes[ax])
        cuts = object_cuts(objects, ax)
        merged = merged_axis(base, cuts, min_spacing)
        # interior subdivision: insert midpoints inside object spans until
        # the local spacing reaches min_spacing / interior_ratio
        extra = []
        for name, (lo, hi) in objects:
            span = hi[ax] - lo[ax]
            if span <= min_spacing:
                continue
            m = max(1, int(round(span / min_spacing * interior_ratio / 2)))
            for k in range(1, m):
                v = lo[ax] + span * k / m
                if base[0] <= v <= base[-1] and \
                        all(abs(v - u) > 1e-9 for u in merged):
                    extra.append(v)
        merged = sorted(set(merged + extra))
        # enforce min spacing once more (cheap: drop too-close neighbours)
        filt = []
        for v in merged:
            if not filt or v - filt[-1] >= min_spacing * 0.5:
                filt.append(v)
        out.append(filt)
    return out


def refine_mesh(result, model, min_spacing=0.0045, interior_ratio=2,
                max_cells=400000):
    """Build a refined conformal MeshResult over the existing base grid."""
    objects = []
    for o in model._all_objects():
        if o.kind == "domain":
            continue
        b = _bounds_of(o)
        if b is not None:
            objects.append((o.name, b))
    axes = refine_axes(result.axes, objects, min_spacing, interior_ratio)
    cells = (len(axes[0]) - 1) * (len(axes[1]) - 1) * (len(axes[2]) - 1)
    if cells > max_cells:
        # coarsen min_spacing iteratively to stay within budget
        scale = (cells / float(max_cells)) ** (1.0 / 3.0)
        axes = refine_axes(result.axes, objects,
                           min_spacing * scale * 1.15, interior_ratio)
        cells = (len(axes[0]) - 1) * (len(axes[1]) - 1) * (len(axes[2]) - 1)
    cell_obj = classify_cells(axes, objects)
    return MeshResult(axes, cell_obj)


def tune_for_target(project_dir, target, model=None, lo=0.002, hi=0.02,
                    iters=14):
    """Binary-search min_spacing so refined cell count ~= target."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh
    if model is None:
        proj = IcepakProject(project_dir)
        model = proj.model
    base = generate_mesh(model, counts=(10, 10, 10))
    best = None
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        r = refine_mesh(base, model, min_spacing=mid, interior_ratio=2,
                        max_cells=4 * target)
        n = r.cell_count
        if best is None or abs(n - target) < abs(best[1] - target):
            best = (mid, n, r)
        if n > target:
            lo = mid
        else:
            hi = mid
    return best


def _bounds_of(obj):
    sh = getattr(obj, "shape", None)
    if sh is None:
        return None
    p1 = sh.setvals.get("point1")
    p2 = sh.setvals.get("point2")
    if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple))):
        return None
    try:
        return (tuple(float(x) for x in p1), tuple(float(x) for x in p2))
    except (TypeError, ValueError):
        return None
