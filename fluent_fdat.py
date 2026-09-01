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
