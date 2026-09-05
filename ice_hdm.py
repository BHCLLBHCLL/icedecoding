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
            i = 2
            try:
                float(s[2])
            except ValueError:
                i = 3   # plane token (xy/xz/yz) for quad/plate lines
            if len(s) < i + 9:
                continue
            try:
                vals = [float(v) for v in s[i:i + 9]]
                rec = {"type": s[0], "id": s[1],
                       "lo": (vals[0], vals[1], vals[2]),
                       "hi": (vals[3], vals[4], vals[5]),
                       "size": (vals[6], vals[7], vals[8])}
            except ValueError:
                continue
            # per-face sizes for hexa-family objects (tail cols)
            rec["face_sizes"] = []
            if rec["type"] in ("hexa", "block", "source", "plate", "quad",
                               "pcb", "enclosure", "resistance", "package"):
                try:
                    fs = [float(v) for v in s[i + 9:i + 15]]
                    rec["face_sizes"] = [f for f in fs
                                         if 1e-5 < f < 0.5]
                except ValueError:
                    pass
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


def bounded_faces(params):
    """BOUNDED planar faces (axis, pos, other-lo, other-hi) — a cell is
    cut only where the face rectangle actually overlaps the cell."""
    out = []
    for r in params:
        if r["type"] == "domain":
            continue
        lo, hi = np.array(r["lo"]), np.array(r["hi"])
        for ax in range(3):
            others = [i for i in range(3) if i != ax]
            olo = lo[others]
            ohi = hi[others]
            out.append((ax, float(lo[ax]), olo.copy(), ohi.copy()))
            out.append((ax, float(hi[ax]), olo.copy(), ohi.copy()))
    return out


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
          shell_factor=1.05, curv_c=None, proj_tol=None, base_phase=None,
          ring_pitch=None, ring_zfrac=1.0, ring_stagger=0.0,
          ring_lattice=False, ring_base_step=0.02):
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
    boxes = hdm_boxes_vec(params, (lo, hi), grid_size,
                          max_levels=max_levels, max_cells=max_cells,
                          surface_extra=surface_extra,
                          use_object_sizes=use_object_sizes, cyls=cyls,
                          cyl_cap=cyl_cap, shell_factor=shell_factor,
                          curv_c=curv_c, base_phase=base_phase)
    faces = face_planes(params)
    if proj_tol is None:
        # local-tolerance snapping: only surface-adjacent cell vertices
        verts, sizes = leaf_vertices_sized(boxes)
        verts = snap_vertices_local(verts, sizes, faces)
        if cyls:
            if ring_pitch is not None:
                # replace cube-corner projection with uniform-angular
                # surface rings (the oracle's own shell structure)
                keep = np.ones(len(verts), dtype=bool)
                for c in cyls:
                    p1, p2 = c["p1"], c["p2"]
                    axis = p2 - p1
                    h2 = float(axis @ axis)
                    if h2 <= 0:
                        continue
                    u = axis / np.sqrt(h2)
                    h = float(np.sqrt(h2))
                    d = (verts - p1) @ u
                    m = (d >= -sizes) & (d <= h + sizes)
                    if not m.any():
                        continue
                    w = verts[m] - p1 - d[m, None] * u
                    rho = np.linalg.norm(w, axis=1)
                    rt = c["r1"] + (c["r2"] - c["r1"]) * \
                        np.clip(d[m] / h, 0.0, 1.0)
                    near = (np.abs(rho - rt) < 0.5 * sizes[m]) & (rho > 0)
                    idx = np.where(m)[0][near]
                    keep[idx] = False
                verts = verts[keep]
                rings = ring_nodes(cyls, pitch_c=ring_pitch,
                                   z_frac=ring_zfrac,
                                   stagger_strength=ring_stagger,
                                   lattice=ring_lattice,
                                   base_step=ring_base_step)
                verts = np.concatenate([verts, rings], axis=0)
            else:
                verts = project_to_cylinders_local(verts, sizes, cyls)
    else:
        verts = leaf_vertices_vec(boxes)
        tol = proj_tol
        verts = snap_vertices(verts, faces, tol=tol)
        if cyls:
            verts = project_to_cylinders(verts, cyls, tol=tol)
    return boxes, verts, params, st


def hdm_boxes_vec(params, bounds, grid_size, max_levels=3, balance=False,
                  max_cells=2_000_000, surface_extra=1,
                  use_object_sizes=True, cyls=None, cyl_cap=4,
                  shell_factor=1.05, curv_c=None, base_phase=None):
    """Vectorised level-by-level octree (same semantics as hdm_boxes).

    base_phase: per-axis phase shift of the base lattice (leaf placement
    offset relative to geometry — the lever for the x/y count asymmetry)."""
    lo0 = np.array(bounds[0], dtype=np.float64)
    hi = np.array(bounds[1], dtype=np.float64)
    gs = np.array(grid_size, dtype=np.float64)
    # tile lattice anchored at lo0 + base_phase (partial first cell at lo0)
    lo = lo0.copy()
    if base_phase is not None:
        lo = lo0 + np.array(base_phase, dtype=np.float64)
    n0 = np.maximum(1, np.ceil((hi - lo) / gs).astype(int))
    gs = (hi - lo) / n0

    faces = face_planes(params)
    face_ax = np.array([f[0] for f in faces], dtype=np.int64)
    face_pos = np.array([f[1] for f in faces], dtype=np.float64)
    bf = bounded_faces(params)
    bf_ax = np.array([f[0] for f in bf], dtype=np.int64)
    bf_pos = np.array([f[1] for f in bf], dtype=np.float64)
    bf_lo = np.array([f[2] for f in bf], dtype=np.float64)
    bf_hi = np.array([f[3] for f in bf], dtype=np.float64)

    objs = [(np.array(r["lo"]), np.array(r["hi"]), np.array(r["size"]))
            for r in params if r["type"] not in ("domain",)]
    obj_facesz = [r.get("face_sizes") or [] for r in params
                  if r["type"] not in ("domain",)]

    cyl_u = []
    cyl_p1 = []
    cyl_h = []
    cyl_r1 = []
    cyl_r2 = []
    for c in (cyls or []):
        axis = c["p2"] - c["p1"]
        h2 = float(axis @ axis)
        if h2 <= 0:
            continue
        cyl_p1.append(c["p1"])
        cyl_u.append(axis / np.sqrt(h2))
        cyl_h.append(float(np.sqrt(h2)))
        cyl_r1.append(c["r1"])
        cyl_r2.append(c["r2"])
    cyl_p1 = np.array(cyl_p1) if cyl_p1 else np.zeros((0, 3))
    cyl_u = np.array(cyl_u) if cyl_u else np.zeros((0, 3))
    cyl_h = np.array(cyl_h) if cyl_h else np.zeros(0)
    cyl_r1 = np.array(cyl_r1) if cyl_r1 else np.zeros(0)
    cyl_r2 = np.array(cyl_r2) if cyl_r2 else np.zeros(0)

    ix = np.arange(n0[0])
    jy = np.arange(n0[1])
    kz = np.arange(n0[2])
    ii, jj, kk = np.meshgrid(ix, jy, kz, indexing="ij")
    lo0 = np.stack([lo[0] + gs[0] * ii.ravel(), lo[1] + gs[1] * jj.ravel(),
                    lo[2] + gs[2] * kk.ravel()], axis=1)
    boxes = np.concatenate([lo0, lo0 + gs], axis=1)
    levels = np.zeros(len(boxes), dtype=np.int64)

    off = np.zeros((8, 6))
    for t in range(8):
        i = t & 1
        j = (t >> 1) & 1
        k = (t >> 2) & 1
        off[t, 0] = i * 0.5
        off[t, 1] = j * 0.5
        off[t, 2] = k * 0.5
        off[t, 3] = i * 0.5 + 0.5
        off[t, 4] = j * 0.5 + 0.5
        off[t, 5] = k * 0.5 + 0.5

    while True:
        s = boxes[:, 3:6] - boxes[:, 0:3]
        c = (boxes[:, 0:3] + boxes[:, 3:6]) / 2.0
        s_max = s.max(axis=1)
        n = len(boxes)

        tgt = np.tile(gs, (n, 1))
        if use_object_sizes:
            for k, (olo, ohi, osz) in enumerate(objs):
                m = np.all(c >= olo, axis=1) & np.all(c <= ohi, axis=1)
                if m.any():
                    os = np.where(osz > 1e30, gs, np.maximum(osz, 1e-5))
                    tgt[m] = np.minimum(tgt[m], os)
                    # per-face sizes are job-dependent and fragile to
                    # parse; the oracle's HDM depth is dominated by the
                    # curvature-shell, so we do NOT push object face sizes
                    # into the size field by default (they over-refine e.g.
                    # 8-2yyhh).  face_sizes remain available for inspection.
        need = (s > tgt).any(axis=1)
        refine = need & (levels < max_levels)

        cut = np.zeros(n, dtype=bool)
        if len(bf_pos):
            for f in range(len(bf_pos)):
                ax = int(bf_ax[f])
                pos = float(bf_pos[f])
                others = [i for i in range(3) if i != ax]
                ok = (boxes[:, ax] < pos) & (boxes[:, ax + 3] > pos)
                # face rectangle must overlap the cell in the other axes
                for oi, oc in enumerate(others):
                    ok &= (boxes[:, oc + 3] > bf_lo[f, oi]) & \
                        (boxes[:, oc] < bf_hi[f, oi])
                cut |= ok
        refine |= cut & (levels < min(max_levels + surface_extra, 3))

        if len(cyl_p1) and len(c):
            shell_ref = np.zeros(n, dtype=bool)
            for k in range(len(cyl_p1)):
                d = c - cyl_p1[k]
                t = d @ cyl_u[k]
                w = d - t[:, None] * cyl_u[k]
                rho = np.sqrt((w * w).sum(axis=1))
                h = cyl_h[k]
                rt = cyl_r1[k] + (cyl_r2[k] - cyl_r1[k]) * \
                    np.clip(t / h, 0.0, 1.0)
                band = (np.abs(rho - rt) < s_max * shell_factor) & \
                    (t >= -s_max * shell_factor) & \
                    (t <= h + s_max * shell_factor)
                if curv_c is not None:
                    band &= s_max > curv_c * rt
                shell_ref |= band
            refine |= shell_ref & (levels < cyl_cap)

        if not refine.any() or n >= max_cells:
            break
        sel = np.where(refine)[0]
        n_sel = len(sel)
        so = s[sel]
        plo = np.repeat(boxes[sel, 0:3], 8, axis=0)
        add_lo = np.tile(off[:, 0:3], (n_sel, 1)) * \
            np.repeat(so, 8, axis=0)
        add_hi = np.tile(off[:, 3:6], (n_sel, 1)) * \
            np.repeat(so, 8, axis=0)
        new = np.concatenate([plo + add_lo, plo + add_hi], axis=1)
        boxes = np.concatenate([boxes[~refine], new], axis=0)
        levels = np.concatenate([levels[~refine],
                                 np.repeat(levels[sel] + 1, 8)])
        if len(boxes) > max_cells:
            boxes = boxes[:max_cells]
            levels = levels[:max_cells]
            break
    if balance and len(boxes) > 1:
        boxes = _balance(boxes, max_cells)
    return boxes


def leaf_vertices_vec(boxes):
    """Unique corner vertices via numpy (fast for sweeps)."""
    b = boxes
    corners = np.empty((len(b) * 8, 3))
    for t in range(8):
        i = t & 1
        j = (t >> 1) & 1
        k = (t >> 2) & 1
        corners[t::8, 0] = b[:, i * 3]
        corners[t::8, 1] = b[:, 1 + j * 3]
        corners[t::8, 2] = b[:, 2 + k * 3]
    return np.unique(np.round(corners, 12), axis=0)


def ring_nodes(cyls, pitch_c=0.165, z_frac=1.0, theta_stagger=True,
               stagger_strength=1.0, lattice=False, base_step=0.02):
    """Uniform angular-pitch surface ring nodes around each conical
    cylinder (the oracle's shell structure: near-uniform theta sampling
    with ~1/4 the node count of cube-corner projection).

    pitch_c: angular pitch [rad] (cell_size / r, curv_c-like);
    axial step = pitch_c * r_local * z_frac.
    theta_stagger: per-cylinder theta phase offset (golden-ratio) — the
    oracle's octree leaves place each cylinder's angular grid at a
    different phase, so same-column x-sets only overlap ~30-40%."""
    out = []
    for j, c in enumerate(cyls):
        p1, p2 = c["p1"], c["p2"]
        axis = p2 - p1
        h2 = float(axis @ axis)
        if h2 <= 0:
            continue
        u = axis / np.sqrt(h2)
        h = float(np.sqrt(h2))
        z1, z2 = p1[2], p2[2]
        z = z1
        n = max(3, int(2 * np.pi / max(pitch_c, 1e-4)))
        phase = 0.0
        if theta_stagger:
            phase = ((0.6180339887498949 * (j + 1)) % 1.0) * \
                stagger_strength
        phase_rad = phase * 2 * np.pi / n
        while z <= z2 + 1e-12:
            f = (z - z1) / h if h > 0 else 0.0
            r = c["r1"] + (c["r2"] - c["r1"]) * min(max(f, 0.0), 1.0)
            step_z = max(pitch_c * r * z_frac, 1e-6)
            hc = max(pitch_c * r, 1e-6)
            for k in range(n):
                th = 2 * np.pi * k / n + phase_rad
                x = c["p1"][0] + r * np.cos(th)
                y = c["p1"][1] + r * np.sin(th)
                if lattice:
                    # quantize x/y back to the shared lattice at the local
                    # shell-cell size hc: same-column cylinders then share
                    # part of their x values (oracle 27-41% overlap)
                    x = round(x / hc) * hc
                    y = round(y / hc) * hc
                out.append((x, y, z))
            z += step_z
    return np.array(out, dtype=np.float64) if out else \
        np.zeros((0, 3), dtype=np.float64)


def lattice_surface_nodes(cyls, base=0.02, depth=3, phase=(0.0, 0.008),
                          pitch_c=0.165, z_frac=1.0, band=1.5,
                          snap_tol=1.0, stagger=0.0):
    """P19-1: oracle surface nodes as lattice-derived sampling.

    A GLOBAL shared fine lattice (step = base / 2**depth, per-axis phase)
    samples the conical surface neighbourhood (|rho - r(z)| <= band*g); the
    samples are projected radially onto the cone, then snapped back onto the
    lattice ONLY when within snap_tol*g of a lattice point (partial
    snapping); otherwise the continuous projected position is kept.  The
    snapped subset is shared across same-column cylinders, the continuous
    rest is per-cylinder - reproducing the oracle's PARTIAL (27-41%) x-set
    overlap rather than 0% or 100%.

    Returns unique (N, 3) surface nodes.
    """
    if not cyls:
        return np.zeros((0, 3), dtype=np.float64)
    g = float(base) / float(2 ** depth)
    px, py = float(phase[0]), float(phase[1])
    lo = np.full(3, 1e18)
    hi = np.full(3, -1e18)
    for c in cyls:
        rmax = max(c["r1"], c["r2"])
        lo = np.minimum(lo, c["p1"] - rmax - 2 * g)
        hi = np.maximum(hi, c["p2"] + rmax + 2 * g)
    xs = np.arange(lo[0] - g, hi[0] + g, g) + px
    ys = np.arange(lo[1] - g, hi[1] + g, g) + py
    out = []
    for j, c in enumerate(cyls):
        p1, p2 = c["p1"], c["p2"]
        axis = p2 - p1
        h = float(np.linalg.norm(axis))
        if h <= 0:
            continue
        rmax = max(c["r1"], c["r2"])
        # per-cylinder lattice phase stagger (oracle: each cylinder's octree
        # leaves sit at a different phase of the shared lattice)
        sj = ((0.6180339887498949 * j) % 1.0) * float(stagger)
        off_x = sj * g
        off_y = (sj * 0.5) * g
        z = float(p1[2])
        while z <= float(p2[2]) + 1e-12:
            f = (z - p1[2]) / h
            r = c["r1"] + (c["r2"] - c["r1"]) * min(max(f, 0.0), 1.0)
            wxs = (xs + off_x)[(xs >= p1[0] - rmax - g) &
                                  (xs <= p1[0] + rmax + g)]
            wys = (ys + off_y)[(ys >= p1[1] - rmax - g) &
                                  (ys <= p1[1] + rmax + g)]
            if len(wxs) == 0 or len(wys) == 0:
                z += max(pitch_c * r * z_frac, 1e-6)
                continue
            gx, gy = np.meshgrid(wxs, wys)
            dx = gx - p1[0]
            dy = gy - p1[1]
            rho = np.hypot(dx, dy)
            m = np.abs(rho - r) <= band * g
            if m.any():
                th = np.arctan2(dy[m], dx[m])
                xp = p1[0] + r * np.cos(th)
                yp = p1[1] + r * np.sin(th)
                # partial snap back to the shared lattice
                xf = (xp - px) / g
                yf = (yp - py) / g
                xr = np.round(xf)
                yr = np.round(yf)
                sx = np.abs(xf - xr) <= snap_tol
                sy = np.abs(yf - yr) <= snap_tol
                xq = np.where(sx, xr * g + px, xp)
                yq = np.where(sy, yr * g + py, yp)
                zz = np.full(xq.shape, z)
                out.append(np.stack([xq, yq, zz], axis=1))
            z += max(pitch_c * r * z_frac, 1e-6)
    if not out:
        return np.zeros((0, 3), dtype=np.float64)
    pts = np.concatenate(out, axis=0)
    return np.unique(np.round(pts, 12), axis=0)


def leaf_vertices_sized(boxes):
    """Corner vertices with their OWN leaf size (for local-tolerance
    snapping: only vertices of surface-adjacent cells project)."""
    b = boxes
    n = len(b)
    sz = (b[:, 3:6] - b[:, 0:3]).max(axis=1)
    corners = np.empty((n * 8, 3))
    sizes = np.empty(n * 8)
    for t in range(8):
        i = t & 1
        j = (t >> 1) & 1
        k = (t >> 2) & 1
        corners[t::8, 0] = b[:, i * 3]
        corners[t::8, 1] = b[:, 1 + j * 3]
        corners[t::8, 2] = b[:, 2 + k * 3]
        sizes[t::8] = sz
    u, idx = np.unique(np.round(corners, 12), axis=0, return_index=True)
    return u, sizes[idx]


def snap_vertices_local(verts, sizes, faces, tol_frac=0.5):
    """Project a vertex onto a planar face only when within
    tol_frac x (its own leaf size)."""
    out = verts.copy()
    for ax, pos in faces:
        d = np.abs(out[:, ax] - pos)
        m = d < tol_frac * sizes
        out[m, ax] = pos
    return out


def project_to_cylinders_local(verts, sizes, cyls, tol_frac=0.5):
    """Project only surface-adjacent vertices (within tol_frac x leaf
    size of the conical surface) — the oracle's own behaviour."""
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
        m = (d >= -sizes) & (d <= h + sizes)
        if not m.any():
            continue
        w = out[m] - p1 - d[m, None] * u
        rho = np.linalg.norm(w, axis=1)
        rt = c["r1"] + (c["r2"] - c["r1"]) * np.clip(d[m] / h, 0.0, 1.0)
        hit = (np.abs(rho - rt) < tol_frac * sizes[m]) & (rho > 0)
        if not hit.any():
            continue
        idx = np.where(m)[0][hit]
        ww = w[hit]
        rr = rt[hit] / rho[hit]
        out[idx] = p1 + d[idx][:, None] * u + rr[:, None] * ww
    return out
