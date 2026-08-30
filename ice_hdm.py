# -*- coding: utf-8 -*-
"""P18: first-order HDM (hierarchical density mesh) replication.

Icepak's mesher is grid_type hdm for all tutorial jobs: a padded octree
refined toward a per-object size field (grid_params dx/dy/dz, global
grid_size), with leaves snapped to object faces.  This prototype:
  - padded bounding box (cabinet bounds, pad to 0),
  - base grid at grid_size (0.02 default / problem file settings),
  - recursive cell refinement while cell size > size field at its center,
  - 2:1 balance pass, level cap (grid_hdm_mlm_auto_levels),
  - exports leaf vertices as mesh nodes for position comparison.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def parse_grid_params(path):
    """Lines: type id xS yS zS xE yE zE dx dy dz ..."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="latin-1", errors="replace") as fh:
        for line in fh:
            s = line.split()
            if len(s) < 11 or s[0].startswith("#"):
                continue
            try:
                vals = [float(v) for v in s[2:11]]
                rec = {"type": s[0], "id": s[1],
                       "lo": (vals[0], vals[1], vals[2]),
                       "hi": (vals[3], vals[4], vals[5]),
                       "size": (vals[6], vals[7], vals[8])}
            except ValueError:
                continue
            out.append(rec)
    return out


def problem_grid_settings(jdir):
    """Extract grid_* settings from the problem file."""
    p = os.path.join(jdir, "problem")
    if not os.path.exists(p):
        return {}
    out = {}
    try:
        with open(p, encoding="latin-1", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if s.startswith("set grid_") and " " in s:
                    parts = s.split()
                    if len(parts) >= 3:
                        try:
                            v = parts[2].strip('"')
                            out[parts[1]] = float(v) if \
                                v.replace(".", "").isdigit() else v
                        except ValueError:
                            out[parts[1]] = parts[2].strip('"')
    except OSError:
        pass
    return out


def face_planes(params):
    """Planar faces of axis-aligned objects: (axis, position) list."""
    faces = []
    for r in params:
        if r["type"] == "domain":
            continue
        lo, hi = r["lo"], r["hi"]
        for ax in range(3):
            faces.append((ax, lo[ax]))
            faces.append((ax, hi[ax]))
    return faces


def hdm_boxes(params, bounds, grid_size, max_levels=3, balance=False,
              max_cells=2_000_000, surface_extra=1,
              use_object_sizes=True, cyls=None, cyl_cap=4,
              shell_factor=1.05, curv_c=None):
    """Return leaf boxes [lo0,lo1,lo2,hi0,hi1,hi2] (n,6) and per-box size."""
    lo = np.array(bounds[0], dtype=np.float64)
    hi = np.array(bounds[1], dtype=np.float64)
    gs = np.array(grid_size, dtype=np.float64)
    n0 = np.maximum(1, np.ceil((hi - lo) / gs).astype(int))
    gs = (hi - lo) / n0  # snap base grid to exact tiles

    # size field: per-object requested sizes; global elsewhere
    objs = [(np.array(r["lo"]), np.array(r["hi"]), np.array(r["size"]))
            for r in params if r["type"] not in ("domain",)]

    def size_at(c):
        best = gs.copy()
        if use_object_sizes:
            for olo, ohi, osz in objs:
                if np.all(c >= olo) and np.all(c <= ohi):
                    s = np.where(osz > 1e30, gs, np.maximum(osz, 1e-5))
                    best = np.minimum(best, s)
        return best

    faces = face_planes(params)

    def in_shell(c, s):
        for cyl in cyls:
            p1, p2 = cyl["p1"], cyl["p2"]
            axis = p2 - p1
            h2 = float(axis @ axis)
            if h2 <= 0:
                continue
            u = axis / np.sqrt(h2)
            h = float(np.sqrt(h2))
            t = float((c - p1) @ u)
            if t < -s or t > h + s:
                continue
            w = c - p1 - t * u
            rho = float(np.linalg.norm(w))
            rt = cyl["r1"] + (cyl["r2"] - cyl["r1"]) * min(max(t / h, 0.0), 1.0)
            if abs(rho - rt) < s * shell_factor:
                return float(rt)
        return None

    boxes = []
    for i in range(n0[0]):
        for j in range(n0[1]):
            for k in range(n0[2]):
                b = np.array([lo[0] + gs[0] * i, lo[1] + gs[1] * j,
                              lo[2] + gs[2] * k,
                              lo[0] + gs[0] * (i + 1), lo[1] + gs[1] * (j + 1),
                              lo[2] + gs[2] * (k + 1)])
                _refine(b, size_at, faces, boxes, 0, max_levels, max_cells,
                        surface_extra, in_shell, cyl_cap, curv_c)
    boxes = np.array(boxes)
    if balance and len(boxes) > 1:
        boxes = _balance(boxes, max_cells)
    return boxes


def _refine(b, size_at, faces, out, level, max_levels, max_cells,
            surface_extra, in_shell=None, cyl_cap=4, curv_c=None):
    s = b[3:6] - b[0:3]
    c = (b[0:3] + b[3:6]) / 2.0
    tgt = size_at(c)
    cut = any(b[ax] < pos < b[ax + 3] for (ax, pos) in faces)
    shell_r = None
    if in_shell is not None:
        shell_r = in_shell(c, s.max() * 1.05)
    need = (s > tgt).any()
    if shell_r is not None and curv_c is not None:
        shell = s.max() > curv_c * shell_r and level < cyl_cap
    else:
        shell = shell_r is not None and level < cyl_cap
    refine = (need and level < max_levels) or \
        (cut and level < min(max_levels + surface_extra, 3)) or shell
    if refine and len(out) < max_cells:
        for ii in range(2):
            for jj in range(2):
                for kk in range(2):
                    child = b.copy()
                    child[0] = b[0] + s[0] / 2 * ii
                    child[1] = b[1] + s[1] / 2 * jj
                    child[2] = b[2] + s[2] / 2 * kk
                    child[3] = child[0] + s[0] / 2
                    child[4] = child[1] + s[1] / 2
                    child[5] = child[2] + s[2] / 2
                    _refine(child, size_at, faces, out, level + 1, max_levels,
                            max_cells, surface_extra, in_shell, cyl_cap,
                            curv_c)
    else:
        out.append(b)


def _balance(boxes, max_cells):
    """2:1 balance: subdivide leaves with a neighbour more than 2x smaller
    (KD-tree neighbour search, iterative)."""
    from scipy.spatial import cKDTree
    for _ in range(6):
        sizes = boxes[:, 3:6] - boxes[:, 0:3]
        s_max = sizes.max(axis=1)
        centers = (boxes[:, 0:3] + boxes[:, 3:6]) / 2.0
        tree = cKDTree(centers)
        split = np.zeros(len(boxes), dtype=bool)
        for i in range(len(boxes)):
            r = s_max[i] * 1.5
            js = tree.query_ball_point(centers[i], r)
            for j in js:
                if j == i:
                    continue
                # adjacent in space and much smaller -> split me
                if s_max[j] < 0.5 * s_max[i]:
                    split[i] = True
                    break
            if len(boxes) + 7 * int(split.sum()) > max_cells:
                break
        if not split.any():
            break
        nb = []
        for i in range(len(boxes)):
            if not split[i]:
                nb.append(boxes[i])
                continue
            b = boxes[i]
            s = sizes[i]
            for ii in range(2):
                for jj in range(2):
                    for kk in range(2):
                        nb.append([b[0] + s[0] / 2 * ii, b[1] + s[1] / 2 * jj,
                                   b[2] + s[2] / 2 * kk,
                                   b[0] + s[0] / 2 * (ii + 1),
                                   b[1] + s[1] / 2 * (jj + 1),
                                   b[2] + s[2] / 2 * (kk + 1)])
        boxes = np.array(nb)
    return boxes


def snap_vertices(verts, faces, tol):
    """Project vertices near a planar face onto it (Icepak snap-to-geometry)."""
    out = verts.copy()
    for ax, pos in faces:
        d = np.abs(out[:, ax] - pos)
        m = d < tol
        out[m, ax] = pos
    return out


def model_cylinders(model):
    """Conical/cylindrical surfaces from the decoded model:
    shape center/center2/radius[/radius2] (radius2 defaults to radius)."""
    cyls = []
    for o in model._all_objects():
        sh = getattr(o, "shape", None)
        if sh is None:
            continue
        sv = getattr(sh, "setvals", None) or {}
        if "center" not in sv or "center2" not in sv or "radius" not in sv:
            continue
        try:
            p1 = np.array([float(x) for x in sv["center"]])
            p2 = np.array([float(x) for x in sv["center2"]])
            r1 = float(sv["radius"][0])
            r2 = float((sv.get("radius2") or sv["radius"])[0])
            ir1 = float((sv.get("iradius") or ["0"])[0])
            ir2 = float((sv.get("iradius2") or sv.get("iradius")
                         or ["0"])[0])
        except (TypeError, ValueError, IndexError):
            continue
        cyls.append({"p1": p1, "p2": p2, "r1": max(r1, ir1),
                     "r2": max(r2, ir2)})
    return cyls


def project_to_cylinders(verts, cyls, tol):
    """Project vertices within tol of a conical surface onto it (the source
    of the oracle's 1e-7-scale continuous position spectrum)."""
    out = verts.copy()
    for c in cyls:
        p1, p2 = c["p1"], c["p2"]
        axis = p2 - p1
        h2 = float(axis @ axis)
        if h2 <= 0:
            continue
        u = axis / np.sqrt(h2)
        h = float(np.sqrt(h2))
        d = (out - p1) @ u
        m = (d >= -tol) & (d <= h + tol)
        if not m.any():
            continue
        w = out[m] - p1 - d[m, None] * u
        rho = np.linalg.norm(w, axis=1)
        rt = c["r1"] + (c["r2"] - c["r1"]) * np.clip(d[m] / h, 0.0, 1.0)
        hit = (np.abs(rho - rt) < tol) & (rho > 0)
        if not hit.any():
            continue
        idx = np.where(m)[0][hit]
        ww = w[hit]
        rr = rt[hit] / rho[hit]
        out[idx] = p1 + d[idx][:, None] * u + rr[:, None] * ww
    return out


def leaf_vertices(boxes):
    """Unique corner vertices of all leaves (the mesh nodes)."""
    pts = set()
    for b in boxes:
        for i in range(2):
            for j in range(2):
                for k in range(2):
                    pts.add((round(b[i * 3 + 0], 12), round(b[j * 3 + 1], 12),
                             round(b[k * 3 + 2], 12)))
    out = np.array(sorted(pts), dtype=np.float64)
    return out


def position_match(our, oracle):
    """Nearest-distance stats between two node clouds."""
    from scipy.spatial import cKDTree
    t_oracle = cKDTree(oracle)
    t_our = cKDTree(our)
    d1, _ = t_oracle.query(our)      # our node -> nearest oracle node
    d2, _ = t_our.query(oracle)      # oracle node -> nearest our node
    return {"our_to_oracle": [float(d1.min()), float(np.median(d1)),
                              float(d1.mean()), float(d1.max())],
            "oracle_to_our": [float(d2.min()), float(np.median(d2)),
                              float(d2.mean()), float(d2.max())],
            "oracle_matched_1e-6": float((d2 < 1e-6).mean()),
            "oracle_matched_1e-4": float((d2 < 1e-4).mean()),
            "oracle_matched_1e-3": float((d2 < 1e-3).mean())}


def build(jdir, max_levels=3, grid_size=None, max_cells=150000,
          surface_extra=0, use_object_sizes=True, model=None, cyl_cap=4,
          shell_factor=1.05, curv_c=None):
    params = parse_grid_params(os.path.join(jdir, "grid_params"))
    dom = [r for r in params if r["type"] == "domain"]
    if dom:
        lo = np.array(dom[0]["lo"]); hi = np.array(dom[0]["hi"])
    else:
        lo = np.array([0.0, 0.0, 0.0]); hi = np.array([0.3, 0.3, 0.3])
    st = problem_grid_settings(jdir)
    # base-size rule: s = min(sane grid_size, L / gcount) per axis
    # (grid_size is the max element size; gcount the legacy count fallback)
    def _sane(v, L):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        if v <= 0 or v >= L or v != v:
            return None
        return v

    span = hi - lo
    # cylinders from the model (curvature-driven refinement + projection)
    if model is None:
        try:
            from icepak_parser.project import IcepakProject
            model = IcepakProject(jdir).model
        except Exception:
            model = None
    cyls = model_cylinders(model) if model is not None else []
    gcount = (st.get("grid_gcount_i", 10), st.get("grid_gcount_j", 10),
              st.get("grid_gcount_k", 10))
    if grid_size is None:
        gx = _sane(st.get("grid_size_x", 0.02), span[0])
        gy = _sane(st.get("grid_size_y", 0.02), span[1])
        gz = _sane(st.get("grid_size_z", 0.02), span[2])
        if gx is None:
            gx = span[0] / float(gcount[0])
        if gy is None:
            gy = span[1] / float(gcount[1])
        if gz is None:
            gz = span[2] / float(gcount[2])
        grid_size = (gx, gy, gz)
    grid_size = tuple(min(grid_size[i], span[i] / 3.0) for i in range(3))
    # oracle meshes pad the box toward 0
    lo = np.minimum(lo, 0.0)
    boxes = hdm_boxes(params, (lo, hi), grid_size, max_levels=max_levels,
                      max_cells=max_cells, surface_extra=surface_extra,
                      use_object_sizes=use_object_sizes, cyls=cyls,
                      cyl_cap=cyl_cap, shell_factor=shell_factor,
                      curv_c=curv_c)
    verts = leaf_vertices(boxes)
    faces = face_planes(params)
    tol = max(grid_size) * 0.45
    verts = snap_vertices(verts, faces, tol=tol)
    if cyls:
        verts = project_to_cylinders(verts, cyls, tol=tol)
    return boxes, verts, params, st
