# -*- coding: utf-8 -*-
"""Fluent .fdat (data file) parser — extract cell/node scalar fields.

Observed structure (Icepak 19.5 fluent20.1.0 data files):
  ASCII header (settings, machine-config, grid sizes) ...
  then repeated field sections:
    (N "SV_<name>, domain 1, cell zone 16, ... cells:")
    (3300 (1 16 1 0 1 <off?·> <count>)
    ( <count x float64 LE> )
"""
import re
import struct


def _be(data, off, fmt):
    return struct.unpack_from(fmt, data, off)


def parse_fdat(path):
    """Return {'header': {...}, 'fields': [(name, zone, values), ...]}."""
    with open(path, "rb") as fh:
        data = fh.read()
    n = len(data)
    out = {"header": {}, "fields": []}
    # --- header: grid sizes + variables (ASCII up to first binary) ---
    first_bin = None
    for i in range(min(n, 400000)):
        if data[i] < 9 or (13 < data[i] < 32) or data[i] > 126:
            first_bin = i
            break
    hdr = data[:first_bin].decode("latin-1", "replace")
    m = re.search(r"\(33 \(([0-9]+) ([0-9]+) ([0-9]+)\)\)", hdr)
    if m:
        out["header"]["cells"] = int(m.group(1))
        out["header"]["faces"] = int(m.group(2))
        out["header"]["nodes"] = int(m.group(3))
    m = re.search(r"\(37 \((.*?)\)\)\s*\n\s*\n", hdr, re.S)
    if m:
        out["header"]["variables_text"] = m.group(1)[:400]

    # --- field sections: scan for '(3300 (' then count + doubles ---
    pos = first_bin if first_bin is not None else 0
    idxs = [mm.start() for mm in re.finditer(rb"\n\(3300 \(", data)]
    # map each 3300 section to the nearest preceding SV_ name line
    names = [(mm.start(), mm.group(1).decode("latin-1", "replace"))
             for mm in re.finditer(rb'\(\s*\d+\s+"([^"]+)"', data)]
    for s0 in idxs:
        # parse args of this 3300 (text) then read doubles
        j = s0 + 1  # past '('
        close = data.find(b")", j)
        argtxt = data[j:close].decode("latin-1", "replace")
        args = [int(x) for x in re.findall(r"[0-9]+", argtxt)]
        count = args[-1] if args else 0
        # find the data '(' after the arg close
        dp = data.find(b"(", close)
        if dp < 0:
            continue
        # data ( may have trailing; values = count doubles
        base = dp + 1
        if base + count * 8 > n:
            break
        vals = struct.unpack_from("<%dd" % count, data, base)
        # name = last SV_ name before this section
        name = ""
        for off, nm in names:
            if off < s0:
                name = nm
            else:
                break
        out["fields"].append((name, args, list(vals)))
    return out


def fields_of(parsed, key):
    """Pick the field whose descriptor contains key (e.g. 'SV_T')."""
    for name, args, vals in parsed["fields"]:
        if key in name:
            return name, args, vals
    return None


def stats(vals):
    if not vals:
        return {}
    lo = min(vals)
    hi = max(vals)
    m = sum(vals) / len(vals)
    return {"min": round(lo, 4), "max": round(hi, 4),
            "mean": round(m, 4), "n": len(vals)}

# ---- P19-10: cas node+cell geometry -> cell centers (real-post source) ----

def parse_cas_cells(text):
    """Extract node coords (zone 10) and cell connectivity (zone 12) from
    an ASCII Fluent cas.  Returns (centers, node_coords, cell_nodes)."""
    import numpy as np
    nodes = {}
    cell_nodes = []
    lines = text.split("\n")
    i = 0
    n = len(lines)
    mode = None
    count = 0
    got = 0
    # node section: (10 (1 1 <N-hex> 1 3) (  then bare x y z triples
    mnode = re.search(r"\(10 \(1 1 ([0-9a-fA-F]+) 1 3\) \(\s*", text)
    if mnode:
        nnode = int(mnode.group(1), 16)
        cur = re.finditer(r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+"
                          r"([-+0-9.eE]+)", text[mnode.end():])
        k = 0
        for mm in cur:
            if k >= nnode:
                break
            nodes[k + 1] = (float(mm.group(1)), float(mm.group(2)),
                            float(mm.group(3)))
            k += 1
    # cell connectivity: per-block hex cells (8 node ids + 1 flag)
    for mm in re.finditer(r"\(\s*([0-9]+)\s+([0-9]+)\s+([0-9]+)"
                          r"\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)"
                          r"\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s*[01]\s*\)",
                          text):
        cell_nodes.append([int(mm.group(i)) for i in range(1, 9)])
    arr = []
    for nl in cell_nodes:
        pts = [nodes[k] for k in nl if k in nodes]
        if len(pts) >= 4:
            arr.append([sum(p[0] for p in pts) / len(pts),
                        sum(p[1] for p in pts) / len(pts),
                        sum(p[2] for p in pts) / len(pts)])
    return np.array(arr) if arr else np.zeros((0, 3))


def load_real_temperature(project_dir):
    """Return (vals, centers|None) — the real fdat temperature per cell and,
    when the cas cell connectivity parses, the cell centers.  vals are the
    authoritative real data source; centers are best-effort geometry."""
    import os
    fdat = os.path.join(project_dir, "transient00.fdat")
    if not os.path.exists(fdat):
        return None, None
    pf = parse_fdat(fdat)
    t = fields_of(pf, "SV_T")
    if t is None:
        return None, None
    _, _, vals = t
    centers = None
    cas = os.path.join(project_dir, "transient00.cas")
    if os.path.exists(cas):
        text = open(cas, encoding="latin-1", errors="replace").read()
        c = parse_cas_cells(text)
        if len(c):
            centers = c
    return list(vals), centers


def load_real_fields(project_dir):
    """Return {field_key: values} for every fdat field (real data for
    postprocessing).  field_key = e.g. 'SV_T' (last zone segment wins)."""
    import os
    fdat = os.path.join(project_dir, "transient00.fdat")
    if not os.path.exists(fdat):
        return {}
    pf = parse_fdat(fdat)
    out = {}
    for name, args, vals in pf["fields"]:
        base = name.split(",")[0].strip()
        out.setdefault(base, vals)   # first zone segment is the clean one
    return out


def scalar_minmax(rows):
    lo = min(min(r) for r in rows if r)
    hi = max(max(r) for r in rows if r)
    return lo, hi

# ---- P19-4: real temperature cloud via block bounds + per-zone cell counts ---

def cas_cell_zones(text):
    """Map cell-zone headers: ';;; cells for block <name>' + (12 (zhex nhex
    11 0) (  -> [(name, count, zone_id)] in file order."""
    out = []
    for m in re.finditer(
            r";;;\s+cells for\s+\S+\s+(\S+)\s+[^\n]*\n"
            r"(?:[^\n]*\n)*?"
            r"\(12 \(([0-9a-fA-F]+) [0-9]+ ([0-9a-fA-F]+) 11 0\) \(",
            text):
        name = m.group(1)
        zid = int(m.group(2), 16)
        count = int(m.group(3), 16)
        out.append((name, count, zid))
    return out


def _factor3(n):
    """Approx 3D factorization a*b*c == n, near-cubic."""
    import math
    ia = int(round(n ** (1.0 / 3.0)))
    for a in range(max(1, ia - 6), ia + 7):
        for b in range(max(1, ia - 6), ia + 7):
            if n % (a * b) == 0:
                c = n // (a * b)
                return (a, b, c)
    return (max(1, ia), max(1, ia), max(1, n // (ia * ia)))


def structured_cell_centers(lo, hi, n):
    """Approximate cell centers of a structured hex block with n cells."""
    import numpy as np
    la = _factor3(n)
    centers = []
    for i in range(la[0]):
        for j in range(la[1]):
            for k in range(la[2]):
                centers.append((
                    lo[0] + (i + 0.5) * (hi[0] - lo[0]) / la[0],
                    lo[1] + (j + 0.5) * (hi[1] - lo[1]) / la[1],
                    lo[2] + (k + 0.5) * (hi[2] - lo[2]) / la[2]))
    return np.array(centers)


def real_temp_cloud(project_dir):
    """Return (centers, temps) — real fdat temperatures on approximate cell
    centers (block bounds + per-zone counts).  None if unavailable."""
    import os
    import numpy as np
    cas = os.path.join(project_dir, "transient00.cas")
    fdat = os.path.join(project_dir, "transient00.fdat")
    if not os.path.exists(cas) or not os.path.exists(fdat):
        return None
    text = open(cas, encoding="latin-1", errors="replace").read()
    zones = cas_cell_zones(text)
    pf = parse_fdat(fdat)
    # temperature sections by zone id: match section (name 'SV_T... zone X')
    temps_by_zone = {}
    for name, args, vals in pf["fields"]:
        if "SV_T" not in name:
            continue
        # zone id = second arg of the (3300 (1 <zid> ...))
        zid = args[2] if len(args) > 2 else -1
        temps_by_zone.setdefault(zid, []).append(vals)
    # build geometry
    from icepak_parser.project import IcepakProject
    from ice_mesh import _bounds_of
    proj = IcepakProject(project_dir)
    model = proj.model
    centers = []
    temps = []
    for name, count, zid in zones:
        obj = next((o for o in model._all_objects()
                    if o.name == name), None)
        if obj is None:
            continue
        b = _bounds_of(obj)
        if b is None:
            continue
        vals = temps_by_zone.get(zid)
        if not vals:
            continue
        v = vals[-1]
        v = v[:count]
        if len(v) != count:
            continue
        c = structured_cell_centers(b[0], b[1], count)
        if len(c) != count:
            continue
        centers.append(c)
        temps.append(np.asarray(v))
    if not centers:
        return None
    centers = np.concatenate(centers, axis=0)
    temps = np.concatenate(temps)
    return centers, temps

# ---- P19-4: cell centers via FACE zones (reconstruct cell->node) ----

def parse_cas_faces(text):
    """Parse ALL face rows in (13)/(18) sub-zones:
    'num_nodes n1..nN c1 c2' with hex ids.  Returns [(nodes, c1, c2), ...]."""
    faces = []
    # each face row: N n1..nN c1 c2  (N = num nodes)
    for m in re.finditer(
            r"\b([0-9])\s+((?:[0-9a-fA-F]+\s+){3})(?:[0-9a-fA-F]+\s+)?"
            r"([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s*$",
            text, re.M):
        nn = int(m.group(1))
        ids = m.group(2).split()
        if nn >= 3:
            # last two tokens = c1 c2; the rest (up to nn) = nodes
            tail = m.group(3) + " " + m.group(4)
            c1, c2 = tail.split()[-2], tail.split()[-1]
            nodes = ids + tail.split()[:-2]
            nodes = [int(x, 16) for x in nodes[:nn]]
            faces.append((nodes, int(c1, 16), int(c2, 16)))
    return faces


def cell_centers_from_faces(text, node_coords):
    """Reconstruct cell->node (from face adjacency) then cell centers.
    node_coords: {id: (x,y,z)}.  Returns {cell_id: (cx,cy,cz)}."""
    faces = parse_cas_faces(text)
    cell_nodes = {}
    for nodes, c1, c2 in faces:
        for c in (c1, c2):
            if c > 0:
                cell_nodes.setdefault(c, set()).update(nodes)
    centers = {}
    for c, ns in cell_nodes.items():
        pts = [node_coords[n] for n in ns if n in node_coords]
        if len(pts) >= 4:
            centers[c] = (sum(p[0] for p in pts) / len(pts),
                          sum(p[1] for p in pts) / len(pts),
                          sum(p[2] for p in pts) / len(pts))
    return centers


def parse_cas_nodes(text):
    """node id -> (x,y,z) from the (10 (1 1 N 1 3) (  triple block."""
    import numpy as np
    m = re.search(r"\(10 \(1 1 ([0-9a-fA-F]+) 1 3\) \(\s*", text)
    if not m:
        return {}
    nnode = int(m.group(1), 16)
    nodes = {}
    cur = re.finditer(r"([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+"
                      r"([-+0-9.eE]+)", text[m.end():])
    k = 0
    for mm in cur:
        if k >= nnode:
            break
        nodes[k + 1] = (float(mm.group(1)), float(mm.group(2)),
                        float(mm.group(3)))
        k += 1
    return nodes

# ---- P19-4: real temperature cloud (face-based cell centers + fdat) ----

def _job_cas_fdat(project_dir):
    """Find (cas, fdat) sharing a base name (tutorial jobs vary)."""
    import os
    fdats = sorted(n for n in os.listdir(project_dir) if n.endswith(".fdat"))
    if not fdats:
        return None, None
    fdat = os.path.join(project_dir, fdats[0])
    base = fdats[0][:-5]
    cas = os.path.join(project_dir, base + ".cas")
    if not os.path.exists(cas):
        cas_list = [n for n in os.listdir(project_dir)
                    if n.endswith(".cas") and "nc.cas" not in n
                    and "cfd.cas" not in n]
        if cas_list:
            cas = os.path.join(project_dir, sorted(cas_list)[0])
        else:
            return None, None
    return cas, fdat


def real_temp_cloud_face(project_dir):
    """Return (centers[N,3], temps[N]) — real cell centers (face-zones)
    with real fdat temperatures ordered by cell id.  None if unavailable."""
    import os
    import numpy as np
    cas, fdat = _job_cas_fdat(project_dir)
    if not cas or not fdat:
        return None
    text = open(cas, encoding="latin-1", errors="replace").read()
    nodes = parse_cas_nodes(text)
    centers = cell_centers_from_faces(text, nodes)
    pf = parse_fdat(fdat)
    # pick the clean (finite-dominant) temperature section; map by its
    # cell-id start offset (args[6]) so temp[cell] = vals[cell - start].
    best = None
    for name, args, vals in pf["fields"]:
        if "SV_T" not in name or "SV_T_M1" in name:
            continue
        nf = sum(1 for v in vals if v == v and abs(v) < 1e6)
        if nf < len(vals) * 0.8:
            continue
        if best is None or nf > best[2]:
            best = (args, vals, nf)
    if best is None:
        return None
    args, vals, _ = best
    start = args[6] if len(args) > 6 else 1
    cell_ids = sorted(centers.keys())
    pts = []
    ts = []
    for cid in cell_ids:
        idx = cid - start
        if 0 <= idx < len(vals):
            v = vals[idx]
            if abs(v) < 1e6:
                pts.append(centers[cid])
                ts.append(v)
    if not pts:
        return None
    return np.array(pts), np.array(ts)


def temp_cloud_polys(centers, temps):
    """VTK point cloud with per-point temperature -> (vtkPoints, rgba array).
    Colours via a blue->red lookup normalised to [tmin, tmax]."""
    import vtk
    n = len(centers)
    pts = vtk.vtkPoints()
    pts.SetNumberOfPoints(n)
    colors = vtk.vtkUnsignedCharArray()
    colors.SetNumberOfComponents(4)
    colors.SetName("Temperature")
    tmin = float(temps.min())
    tmax = float(temps.max())
    span = max(tmax - tmin, 1e-12)
    for i in range(n):
        pts.SetPoint(i, float(centers[i][0]), float(centers[i][1]),
                     float(centers[i][2]))
        f = (float(temps[i]) - tmin) / span
        # blue (cold) -> red (hot)
        r = int(255 * f)
        b = int(255 * (1 - f))
        colors.InsertNextTuple4(r, 10, b, 255)
    cloud = vtk.vtkPolyData()
    cloud.SetPoints(pts)
    cloud.GetPointData().SetScalars(colors)
    return cloud, tmin, tmax

# ---- Phase A1: scalar-field viewport operators on the real temp cloud ----

def _mk_scalar_cloud(points):
    """vtkPolyData from (N,3) points with temp scalar -> (polydata, scalars)."""
    import vtk
    import numpy as np
    n = len(points)
    pts = vtk.vtkPoints()
    pts.SetNumberOfPoints(n)
    for i in range(n):
        pts.SetPoint(i, float(points[i][0]), float(points[i][1]),
                     float(points[i][2]))
    s = vtk.vtkDoubleArray()
    s.SetName("Temperature")
    s.SetNumberOfComponents(1)
    for i in range(n):
        s.InsertNextValue(float(points[i][3]))
    p = vtk.vtkPolyData()
    p.SetPoints(pts)
    p.GetPointData().SetScalars(s)
    return p, s


def iso_band_data(centers, temps, value, rel_tol=0.02):
    """Real iso 'surface' = points whose temp is within rel_tol*span of value.
    Returns (points[N,4], polydata)."""
    import numpy as np
    lo, hi = float(temps.min()), float(temps.max())
    span = (hi - lo) or 1e-12
    m = np.abs(temps - value) <= rel_tol * span
    sel = np.concatenate([centers[m, :3], temps[m][:, None]], axis=1)
    return sel, _mk_scalar_cloud(sel)[0]


def plane_band_data(centers, temps, axis, offset, tol=0.0008):
    """Real plane cut = points whose <axis> coord is within tol of offset."""
    import numpy as np
    m = np.abs(centers[:, axis] - offset) <= tol
    sel = np.concatenate([centers[m, :3], temps[m][:, None]], axis=1)
    return sel, _mk_scalar_cloud(sel)[0]


def extrema_data(centers, temps, k=12):
    """Hottest and coldest points (min/max location markers)."""
    import numpy as np
    hi_idx = np.argsort(-temps)[:k]
    lo_idx = np.argsort(temps)[:k]
    idx = np.concatenate([hi_idx, lo_idx])
    sel = np.concatenate([centers[idx, :3], temps[idx][:, None]], axis=1)
    return sel, _mk_scalar_cloud(sel)[0]

# ---- Phase A2: real velocity field -> vector glyph ----

def _clean_section(pf, prefix):
    import numpy as np
    best = None
    for name, args, vals in pf["fields"]:
        base = name.split(",")[0].strip()
        if base != prefix:
            continue
        a = np.asarray(vals, dtype=np.float64)
        nf = int((np.isfinite(a) & (np.abs(a) < 1e6)).sum())
        if nf < len(a) * 0.8:
            continue
        if best is None or nf > best[1]:
            best = (args, nf, list(a))
    return best


def real_velocity_cloud(project_dir):
    import os
    import numpy as np
    cas, fdat = _job_cas_fdat(project_dir)
    if not cas or not fdat:
        return None
    text = open(cas, encoding="latin-1", errors="replace").read()
    nodes = parse_cas_nodes(text)
    centers = cell_centers_from_faces(text, nodes)
    pf = parse_fdat(fdat)
    su = _clean_section(pf, "SV_U")
    sv = _clean_section(pf, "SV_V")
    sw = _clean_section(pf, "SV_W")
    if not (su and sv and sw):
        return None
    cids = sorted(centers.keys())
    pts = []
    vecs = []
    for cid in cids:
        idx = cid - su[0][6]
        if 0 <= idx < len(su[2]) and 0 <= idx < len(sv[2]) and \
                0 <= idx < len(sw[2]):
            u, v, w = su[2][idx], sv[2][idx], sw[2][idx]
            if abs(u) < 1e6 and abs(v) < 1e6 and abs(w) < 1e6:
                pts.append(centers[cid])
                vecs.append((u, v, w))
    if not pts:
        return None
    return np.array(pts, dtype=np.float64), np.array(vecs, dtype=np.float64)


def vector_glyph_cloud(centers, vectors, scale=1.0):
    import vtk
    n = len(centers)
    pts = vtk.vtkPoints()
    pts.SetNumberOfPoints(n)
    vecs = vtk.vtkDoubleArray()
    vecs.SetName("Velocity")
    vecs.SetNumberOfComponents(3)
    for i in range(n):
        pts.SetPoint(i, float(centers[i][0]), float(centers[i][1]),
                     float(centers[i][2]))
        vecs.InsertNextTuple3(float(vectors[i][0]), float(vectors[i][1]),
                              float(vectors[i][2]))
    p = vtk.vtkPolyData()
    p.SetPoints(pts)
    p.GetPointData().SetVectors(vecs)
    return p

# ---- Phase A3: real curves from fdat (line sample + point probe) ----

def real_line_sample(project_dir, p0, p1, n=41):
    """(centers, temps) sampled at n points along the line p0->p1 using the
    NEAREST real cell centre's temperature.  Returns (points[N,3], temps[N])."""
    import numpy as np
    from scipy.spatial import cKDTree
    r = real_temp_cloud_face(project_dir)
    if r is None:
        return None
    centers, temps = r
    tree = cKDTree(centers)
    ts = np.linspace(0.0, 1.0, n)
    p0 = np.asarray(p0, dtype=np.float64)
    p1 = np.asarray(p1, dtype=np.float64)
    pts = p0[None, :] + ts[:, None] * (p1 - p0)[None, :]
    _, idx = tree.query(pts)
    return pts, temps[idx]


def real_point_temp(project_dir, p):
    """Nearest real cell temperature at point p -> value or None."""
    import numpy as np
    r = real_temp_cloud_face(project_dir)
    if r is None:
        return None
    centers, temps = r
    from scipy.spatial import cKDTree
    d, i = cKDTree(centers).query(np.asarray(p, dtype=np.float64))
    return float(temps[i])
