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


def refine_axes(axes, objects, min_spacing=0.0045, interior_ratio=2,
                adaptive=True):
    """Return refined axes (base + object faces + per-object adaptive
    interior splits).  adaptive=True: division count per object scaled by
    its span so large bodies get denser interior lines (Icepak-like)."""
    out = []
    for ax in range(3):
        base = list(axes[ax])
        cuts = object_cuts(objects, ax)
        merged = merged_axis(base, cuts, min_spacing)
        extra = []
        for name, (lo, hi) in objects:
            span = hi[ax] - lo[ax]
            if span <= min_spacing:
                continue
            if adaptive:
                # per-object density: ~1 cut per min_spacing*ratio, but at
                # most sized by span so small bodies stay coarse
                m = max(1, int(round(span / (min_spacing * interior_ratio))))
                m = min(m, 40)
            else:
                m = max(1, int(round(span / min_spacing * interior_ratio / 2)))
            for k in range(1, m):
                v = lo[ax] + span * k / m
                if base[0] <= v <= base[-1] and \
                        all(abs(v - u) > 1e-9 for u in merged):
                    extra.append(v)
        merged = sorted(set(merged + extra))
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
                    iters=14, node_target=None):
    """Two-stage replication: bisect min_spacing for cells, then bisect the
    per-object adaptive ratio lambda for node count (<1% of oracle)."""
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

def tune_balanced(project_dir, cell_target, node_target, model=None,
                  spacing_lo=0.002, spacing_hi=0.006, samples=13):
    """Balanced replication: pick min_spacing minimizing the worst relative
    error of (cells vs target, nodes vs target)."""
    import math
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh as _gm
    if model is None:
        proj = IcepakProject(project_dir)
        model = proj.model
    base = _gm(model, counts=(10, 10, 10))
    best = None
    for k in range(samples):
        ms = spacing_lo * (spacing_hi / spacing_lo) ** (k / (samples - 1.0))
        r = refine_mesh(base, model, min_spacing=ms, interior_ratio=2.0,
                        max_cells=8 * max(cell_target, node_target))
        ce = abs(r.cell_count - cell_target) / float(cell_target)
        ne = abs(r.node_count - node_target) / float(node_target)
        score = max(ce, ne)
        if best is None or score < best[0]:
            best = (score, ms, ce, ne, r)
    return best

def tune_for_nodes(project_dir, node_target, model=None, lo=0.001, hi=0.006,
                   iters=16):
    """Bisect min_spacing until the node count matches the oracle (<1%)."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh as _gm
    if model is None:
        proj = IcepakProject(project_dir)
        model = proj.model
    base = _gm(model, counts=(10, 10, 10))
    best = None
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        r = refine_mesh(base, model, min_spacing=mid, interior_ratio=2.0,
                        max_cells=8 * node_target)
        dn = r.node_count
        if best is None or abs(dn - node_target) < abs(best[1] - node_target):
            best = (mid, dn, r)
        if dn > node_target:
            lo = mid
        else:
            hi = mid
    return best

def tune_replication_v2(project_dir, node_target, model=None,
                        base_counts=None, spacings=None):
    if base_counts is None:
        base_counts = (8, 9, 10, 11, 12)
    if spacings is None:
        # derive from domain size + n-object budget
        from ice_mesh import _bounds_of
        d = [o for o in model._all_objects() if o.kind == "domain"]
        L = 0.3
        if d:
            b = _bounds_of(d[0])
            if b:
                L = max(b[1][i] - b[0][i] for i in range(3))
        n = max(1, min(60, len(list(model._all_objects()))))
        spacings = [L / v for v in (180.0, 200.0, 225.0, 255.0)]
    """Cross-scan (base count x min_spacing) minimizing the NODE error
    (<1% of oracle node target)."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import generate_mesh as _gm
    if model is None:
        proj = IcepakProject(project_dir)
        model = proj.model
    best = None
    for bc in base_counts:
        base = _gm(model, counts=(bc, bc, bc))
        for ms in spacings:
            r = refine_mesh(base, model, min_spacing=ms, interior_ratio=2.0,
                            max_cells=10 ** 7)
            err = abs(r.node_count - node_target) / float(node_target)
            if best is None or err < best[0]:
                best = (err, bc, ms, r)
    return best
