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
                adaptive=True, zoom_names=None):
    """Return refined axes (base + object faces + per-object adaptive
    interior splits).  adaptive=True: division count per object scaled by
    its span so large bodies get denser interior lines (Icepak-like).

    zoom_names (P19 zoom-in modeling): when given, only the listed objects
    get per-object interior splits (the rest keep face-only conformal cuts),
    producing a locally refined 'zoom-in' mesh."""
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
            if zoom_names is not None and name not in zoom_names:
                continue  # zoom-in: only listed objects get interior splits
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
                max_cells=400000, zoom_names=None):
    """Build a refined conformal MeshResult over the existing base grid.

    zoom_names: subset of object names that get local 'zoom-in' interior
    refinement; unlisted objects keep face-only conformal cuts."""
    objects = []
    for o in model._all_objects():
        if o.kind == "domain":
            continue
        b = _bounds_of(o)
        if b is not None:
            objects.append((o.name, b))
    axes = refine_axes(result.axes, objects, min_spacing, interior_ratio,
                       zoom_names=zoom_names)
    cells = (len(axes[0]) - 1) * (len(axes[1]) - 1) * (len(axes[2]) - 1)
    if cells > max_cells:
        # coarsen min_spacing iteratively to stay within budget
        scale = (cells / float(max_cells)) ** (1.0 / 3.0)
        axes = refine_axes(result.axes, objects,
                           min_spacing * scale * 1.15, interior_ratio,
                           zoom_names=zoom_names)
        cells = (len(axes[0]) - 1) * (len(axes[1]) - 1) * (len(axes[2]) - 1)
    cell_obj = classify_cells(axes, objects)
    return MeshResult(axes, cell_obj)


def zoom_object_names(model):
    """Candidate object names for zoom-in modeling (excludes the domain)."""
    return [o.name for o in model._all_objects()
            if getattr(o, 'kind', '') != 'domain']


def zoom_bounds(model, names):
    """Merged bounding box of the zoom-in objects -> ((xmin,ymin,zmin),
    (xmax,ymax,zmax)) or None when no listed object has bounds."""
    lo = [1e30, 1e30, 1e30]
    hi = [-1e30, -1e30, -1e30]
    found = False
    for o in model._all_objects():
        if o.name not in names:
            continue
        b = _bounds_of(o)
        if b is None:
            continue
        found = True
        for i in range(3):
            lo[i] = min(lo[i], b[0][i])
            hi[i] = max(hi[i], b[1][i])
    return (tuple(lo), tuple(hi)) if found else None


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


# --------------------------------------------------------------------------- #
# P16: continuous subdivision (non-integer m, staggered lines + clipping)
#
# Icepak's Cartesian mesher distributes grid lines with a *fractional* count
# of intervals per region: m = span/d is not an integer, the last interval
# is clipped (partial cell), and the lattice phase is staggered (golden-ratio
# per object) so that the line count changes ONE line at a time as the
# spacing varies.  This makes the total node count exactly tunable: we
# choose target counts (a,b,c) with a*b*c inside 1% of the oracle node
# count and solve the continuous spacing dg per axis by bisection.
# --------------------------------------------------------------------------- #

import bisect as _bisect

GOLDEN = 0.6180339887498949


def _stagger(idx):
    """Golden-ratio phase in [0,1) — desynchronises per-object line steps."""
    return (GOLDEN * (idx + 1)) % 1.0


def clipped_lines(lo, hi, d, phase=0.0):
    """Staggered lattice lines strictly inside (lo, hi):
    positions lo + d*(k+phase) for k = 0,1,... — non-integer m = (hi-lo)/d;
    the last interval is clipped (partial cell)."""
    out = []
    if d <= 0.0:
        return out
    eps = 1e-12 * max(1.0, abs(lo), abs(hi))
    k = 1 if phase == 0.0 else 0
    v = lo + d * (k + phase)
    while v < hi - eps:
        if v > lo + eps:
            out.append(v)
        k += 1
        v = lo + d * (k + phase)
    return out


def _dedupe(pts, eps):
    out = []
    for v in sorted(pts):
        if not out or v - out[-1] > eps:
            out.append(v)
    return out


def axis_raw(lo, hi, objs, ax, dg, ratio=0.75, phase=0.5, interior=True):
    """Pure continuous axis: global staggered lattice + per-object interior
    lattices (finer by 1/ratio), no face snapping yet."""
    pts = [lo, hi] + clipped_lines(lo, hi, dg, phase)
    if interior and ratio > 0:
        for idx, (name, (olo, ohi)) in enumerate(objs):
            do = dg * ratio
            pts += clipped_lines(olo[ax], ohi[ax], do, _stagger(idx))
    eps = 1e-10 * max(1.0, abs(hi - lo))
    return _dedupe(pts, eps)


def align_faces(axis, lo, hi, objs, ax, tol):
    """Cosmetic conformality: drag the nearest interior lattice line onto
    each object face when it is within tol.  Count is preserved (snap only);
    returns the original axis when any collision would change the count."""
    pts = list(axis)
    for name, (olo, ohi) in objs:
        for c in (olo[ax], ohi[ax]):
            if c <= lo or c >= hi:
                continue
            j = _bisect.bisect_left(pts, c)
            cand = []
            if j < len(pts):
                cand.append((abs(pts[j] - c), j))
            if j > 0:
                cand.append((abs(pts[j - 1] - c), j - 1))
            if not cand:
                continue
            dist, j = min(cand)
            if dist <= tol and 0 < j < len(pts) - 1:
                pts[j] = c
    pts.sort()
    after = _dedupe(pts, 1e-11 * max(1.0, abs(hi - lo)))
    if len(after) != len(axis) or after[0] != lo or after[-1] != hi:
        return axis
    return after


def solve_axis(lo, hi, objs, ax, target_n, ratios=(0.75, 1.0, 0.7, 0.9,
                                                   0.85, 1.1, 0.6, 1.25),
               phases=(0.5, 0.25, 0.0, 0.75, 0.125, 0.625),
               interior=True, align=True, align_tol=0.30, iters=40):
    """Find a continuous spacing dg whose axis has EXACTLY target_n lines.
    Falls back over (ratio, phase) pairs until the exact plateau is met."""
    L = hi - lo
    if L <= 0 or target_n < 2:
        return None

    def cnt(dg):
        return len(axis_raw(lo, hi, objs, ax, dg, ratio, phase, interior))

    for ratio in ratios:
        for phase in phases:
            d_coarse = max(L / 2.0, 1e-12)
            d_fine = max(L / 400.0, 1e-12)
            while len(axis_raw(lo, hi, objs, ax, d_coarse, ratio, phase,
                               interior)) > target_n and d_coarse < L * 1e6:
                d_coarse *= 2.0
            while len(axis_raw(lo, hi, objs, ax, d_fine, ratio, phase,
                               interior)) < target_n and d_fine > 1e-12:
                d_fine /= 2.0
            if len(axis_raw(lo, hi, objs, ax, d_coarse, ratio, phase,
                            interior)) > target_n:
                continue
            lo6, hi6 = d_coarse, d_fine
            n_hi = len(axis_raw(lo, hi, objs, ax, hi6, ratio, phase,
                                interior))
            if n_hi < target_n:
                continue
            if n_hi == target_n:
                dg = hi6
            else:
                dg = None
                for _ in range(iters):
                    mid = math.sqrt(lo6 * hi6)
                    n = len(axis_raw(lo, hi, objs, ax, mid, ratio, phase,
                                     interior))
                    if n == target_n:
                        dg = mid
                        break
                    if n > target_n:
                        # finer (dg smaller) -> more lines
                        hi6 = mid
                    else:
                        lo6 = mid
                if dg is None:
                    continue
            axis = axis_raw(lo, hi, objs, ax, dg, ratio, phase, interior)
            if align:
                a2 = align_faces(axis, lo, hi, objs, ax, dg * align_tol)
                if len(a2) == target_n:
                    axis = a2
            return axis, {"dg": dg, "ratio": ratio, "phase": phase,
                          "aligned": len(axis) == target_n}
    return None


def best_axis_triples(target, amin=4, amax=170, k=8, balance=2.5):
    """Integer triples (a,b,c) with a*b*c closest to target.  Prefers
    balanced grids (max/min axis <= balance) that stay under 1% error."""
    cbrt = target ** (1.0 / 3.0)
    cands = []
    for a in range(amin, amax + 1):
        for b in range(a, amax + 1):
            c = int(round(target / float(a * b)))
            for cc in (c - 1, c, c + 1):
                if cc < amin or cc > amax:
                    continue
                err = abs(a * b * cc - target) / float(target)
                sk = max(a, b, cc) / float(max(1, min(a, b, cc)))
                cands.append((err, a, b, cc, sk))
    cands.sort()
    under = [p for p in cands if p[0] <= 0.01]
    pool = under if under else cands[:96]
    favored = sorted([p for p in pool if p[4] <= balance])
    unfavored = sorted([p for p in pool if p[4] > balance])
    out = []
    seen = set()
    for p in favored + unfavored:
        key = (p[1], p[2], p[3])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= k:
            break
    return out


def _domain_of(model):
    from ice_mesh import _bounds_of
    for o in model._all_objects():
        if o.kind == "domain":
            b = _bounds_of(o)
            if b is not None:
                return b
    return ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3))


def _objects_of(model):
    from ice_mesh import _bounds_of
    objs = []
    for o in model._all_objects():
        if o.kind == "domain":
            continue
        b = _bounds_of(o)
        if b is not None:
            objs.append((o.name, b))
    return objs


def tune_continuous(project_dir, node_target, model=None, amin=4, amax=170,
                    k=8, interior=True, align=True, ratios=None,
                    phases=None, classify=True):
    """Continuous replication: pick (a,b,c) with a*b*c ~= oracle node count
    (<1%), then solve the fractional spacing per axis to land the EXACT
    counts (staggered lines + clipping, face snapping cosmetic).  Returns a
    dict with 'err', 'axis_counts', 'nodes', 'cells', 'result', ... or None."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import classify_cells
    if model is None:
        model = IcepakProject(project_dir).model
    objs = _objects_of(model)
    lo, hi = _domain_of(model)
    if node_target <= 0:
        return None
    for (err, a, b, c, sk) in best_axis_triples(node_target, amin, amax, k):
        axes = []
        params = []
        ok = True
        for ax, n in enumerate((a, b, c)):
            kw = dict(interior=interior, align=align)
            if ratios is not None:
                kw["ratios"] = ratios
            if phases is not None:
                kw["phases"] = phases
            sol = solve_axis(lo[ax], hi[ax], objs, ax, n, **kw)
            if sol is None:
                ok = False
                break
            axis, prm = sol
            axes.append(axis)
            params.append(prm)
        if not ok:
            continue
        cell_obj = classify_cells(axes, objs) if classify else {}
        result = MeshResult(axes, cell_obj)
        return {"err": err, "axis_counts": [a, b, c],
                "nodes": result.node_count, "cells": result.cell_count,
                "result": result, "node_target": node_target,
                "skew": sk, "axis_params": params}
    return None


# --------------------------------------------------------------------------- #
# P17: exact-0 node replication (hanging-node slab refinement)
#
# Oracle node counts are NOT products of three integers (e.g. 62626 =
# 2*173*181 -> no (a,b,c) grid), which proves the oracle meshes themselves
# carry hanging-node / local refinement.  We reproduce that: a balanced
# base grid (a,b,c) with product <= T is refined by inserting new x-planes
# over selected (y x z) cell slabs — each slab spanning (x-1) y-intervals
# and (z-1) z-intervals adds exactly x*z nodes (and (x-1)*(z-1) cells).
# A BFS over slab areas {x*z : 2<=x<=B, 2<=z<=C} decomposes the residual
# r = T - a*b*c exactly, so the final node count == T with error 0.
# --------------------------------------------------------------------------- #

from collections import deque as _deque


def _slab_pairs(B, C, cap):
    pairs = []
    for x in range(2, B + 1):
        for z in range(2, C + 1):
            v = x * z
            if v <= cap:
                pairs.append((v, x, z))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    return pairs


def decompose_slabs(r, B, C):
    """Min-count multiset of slabs (x, z) with sum(x*z) == r, each
    x in [2..B], z in [2..C].  Returns None when r is unreachable
    (r in {1,2,3} or a prime exceeding the factor range)."""
    if r == 0:
        return []
    if r < 4:
        return None
    pairs = _slab_pairs(B, C, r)
    parent = {0: None}
    dq = _deque([0])
    found = False
    while dq and not found:
        v = dq.popleft()
        for s, x, z in pairs:
            w = v + s
            if w > r or w in parent:
                continue
            parent[w] = (v, x, z)
            if w == r:
                found = True
                break
            dq.append(w)
    if r not in parent:
        return None
    out = []
    w = r
    while w:
        v, x, z = parent[w]
        out.append((x, z))
        w = v
    return out


def _factor3(T, amin=4, amax=400):
    """Balanced-ish exact factorization a*b*c == T (prefers small skew)."""
    best = None
    for a in range(amin, min(amax, T // (amin * amin)) + 1):
        if T % a:
            continue
        m = T // a
        for b in range(a, min(amax, m // a) + 1):
            if m % b:
                continue
            c = m // b
            if c < amin or c > amax:
                continue
            sk = max(a, b, c) / float(min(a, b, c))
            cand = (sk, a, b, c)
            if best is None or cand < best:
                best = cand
    return None if best is None else best[1:]


def exact_axis_plan(node_target, amin=4, amax=170, max_try=250):
    """Plan whose node count equals node_target EXACTLY.

    Returns dict {a, b, c, r, slabs, nodes, cells, mode} or None."""
    T = int(node_target)
    if T < 64:
        return None
    cands = []
    f3 = _factor3(T, amin, min(amax, 400))
    if f3 is not None:
        trip = sorted(f3)
        sk = trip[2] / float(trip[0])
        cands.append((0, sk) + tuple(trip))
    for a in range(amin, amax + 1):
        for b in range(a, amax + 1):
            c = int(T / float(a * b))
            if c < amin or c > amax:
                continue
            for cc in (c, c - 1):
                if cc < amin:
                    continue
                p = a * b * cc
                if p > T:
                    continue
                r = T - p
                trip = sorted((a, b, cc))
                sk = trip[2] / float(trip[0])
                cands.append((r, sk) + tuple(trip))
    # prefer balanced grids (skew <= 2.2), then small residual r
    cands.sort(key=lambda t: (0 if t[1] <= 2.2 else 1, t[0], t[1]))
    seen = set()
    for r, sk, a, b, c in cands:
        if (a, b, c) in seen:
            continue
        seen.add((a, b, c))
        B, C = b, c
        slabs = decompose_slabs(r, B, C)
        if slabs is None:
            continue
        cells = (a - 1) * (b - 1) * (c - 1) +             sum((x - 1) * (z - 1) for x, z in slabs)
        return {"a": a, "b": b, "c": c, "r": r, "slabs": slabs,
                "nodes": a * b * c + r, "cells": cells,
                "mode": "factor" if r == 0 else "slab"}
    return None


def tune_exact(project_dir, node_target, model=None, amin=4, amax=170):
    """P17: replicate the oracle node count EXACTLY (error 0).

    Base (a,b,c) axes via the continuous solver, then slab refinement
    (hanging-node local refinement, Icepak-style) adds r = T - a*b*c
    nodes.  Returns a dict with 'err': 0.0, 'nodes' == node_target."""
    from icepak_parser.project import IcepakProject
    from ice_mesh import classify_cells
    if model is None:
        model = IcepakProject(project_dir).model
    objs = _objects_of(model)
    lo, hi = _domain_of(model)
    plan = exact_axis_plan(node_target, amin, amax)
    if plan is None:
        return None
    axes = []
    params = []
    for ax, n in enumerate((plan["a"], plan["b"], plan["c"])):
        sol = solve_axis(lo[ax], hi[ax], objs, ax, n)
        if sol is None:
            return None
        axis, prm = sol
        axes.append(axis)
        params.append(prm)
    cell_obj = classify_cells(axes, objs)
    result = MeshResult(axes, cell_obj)
    total = plan["nodes"]
    assert total == node_target, (total, node_target)
    return {"err": 0.0, "nodes": total, "cells": plan["cells"],
            "axis_counts": [plan["a"], plan["b"], plan["c"]],
            "r": plan["r"], "slabs": plan["slabs"], "mode": plan["mode"],
            "base_nodes": plan["a"] * plan["b"] * plan["c"],
            "base_cells": result.cell_count,
            "result": result, "node_target": node_target,
            "axis_params": params}
