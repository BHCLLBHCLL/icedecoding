# -*- coding: utf-8 -*-
"""
P8: ECAD — reuse the cabdecoding ECXML parser (JEDEC two-resistor/Delphi),
plus IDF/IDX, Networks, JEDEC PTD/JEP30, Powermaps (5 formats), EM Mapping,
and ICB reader (iceecad.exe grammar), mapping onto the Icepak model objects.
"""
import json
import re
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------- #
# ECXML — parse logic verbatim from cabdecoding/ecxml.py (schema identical)
# --------------------------------------------------------------------------- #

_KINDS = {"two_resistor", "delphi", "multi_resistor"}


def _attr_float(el, name, default=0.0):
    v = el.get(name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _tag_float(el, tag, default=0.0):
    c = el.find(tag)
    if c is None or c.text is None:
        return default
    try:
        return float(c.text.strip())
    except ValueError:
        return default


def parse_ecxml(text):
    """ECXML v1.0 components -> list of dicts (cabdecoding-compatible)."""
    root = ET.fromstring(text)
    out = []
    for c in root.findall("Component"):
        loc = c.find("Location")
        size = c.find("Size")
        therm = c.find("Thermal")
        comp = {
            "name": c.get("name", "Component"),
            "kind": c.get("kind", "two_resistor"),
            "manufacturer": c.get("manufacturer", ""),
            "part_number": c.get("part_number", ""),
            "base": (_attr_float(loc, "x") if loc is not None else 0.0,
                     _attr_float(loc, "y") if loc is not None else 0.0,
                     _attr_float(loc, "z") if loc is not None else 0.0),
            "size": (_attr_float(size, "x", 10.0) if size is not None else 10.0,
                     _attr_float(size, "y", 10.0) if size is not None else 10.0,
                     _attr_float(size, "z", 1.0) if size is not None else 1.0),
            "rjc": _tag_float(therm, "Rjc", 1.0) if therm is not None else 1.0,
            "rjb": _tag_float(therm, "Rjb", 5.0) if therm is not None else 5.0,
            "package_power": (_tag_float(therm, "Power", 1.0)
                              if therm is not None else 1.0),
        }
        comp["nodes"] = []
        if therm is not None:
            for nd in therm.findall("Node"):
                comp["nodes"].append((nd.get("name", "Node"),
                                      _attr_float(nd, "r", 1.0)))
        if comp["kind"] not in _KINDS:
            comp["kind"] = "two_resistor"
        out.append(comp)
    return out


def import_ecxml_path(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_ecxml(fh.read())


def _ensure_shape(o, lo, hi):
    """Give an object a hexa shape if default_object left it shapeless."""
    from icepak_parser.model_parser import Shape
    if getattr(o, "shape", None) is None:
        o.shape = Shape("s1", "shape_hexa",
                        {"point1": [str(v) for v in lo],
                         "point2": [str(v) for v in hi]})
    else:
        o.shape.setvals["point1"] = [str(v) for v in lo]
        o.shape.setvals["point2"] = [str(v) for v in hi]
    return o


def register_components(model, comps):
    """Map ECXML components onto model network/package objects (mm -> m)."""
    names = []
    for comp in comps:
        name = comp["name"]
        i = 2
        while model.object_by_name(name) is not None:
            name = "%s_%d" % (comp["name"], i)
            i += 1
        from ice_create import default_object
        idx = model.count_all()
        o = default_object("network", name, index=idx, creation_order=idx + 1)
        base = tuple(v / 1000.0 for v in comp["base"])
        size = tuple(max(v / 1000.0, 1e-6) for v in comp["size"])
        _ensure_shape(o, base, tuple(base[i] + size[i] for i in range(3)))
        sv = getattr(o, "setvals", None) or {}
        sv["network_type"] = [comp["kind"]]
        sv["rjc"] = ["%g" % comp["rjc"]]
        sv["rjb"] = ["%g" % comp["rjb"]]
        sv["power"] = ["%g" % comp["package_power"]]
        if comp["manufacturer"]:
            sv["manufacturer"] = [comp["manufacturer"]]
        if comp["part_number"]:
            sv["part_number"] = [comp["part_number"]]
        if comp.get("nodes"):
            sv["net_nodes"] = [json.dumps(comp["nodes"])]
        o.setvals = sv
        model.objects.append(o)
        names.append(name)
    return names


def parts_to_ecxml(model):
    """Serialize network objects back to ECXML v1.0 text."""
    root = ET.Element("ECXML", {"version": "1.0"})
    for o in model._all_objects():
        if o.kind != "network":
            continue
        sv = getattr(o, "setvals", None) or {}
        ntype = sv.get("network_type", ["two_resistor"])[0]
        if ntype not in _KINDS:
            ntype = "two_resistor"
        comp = ET.SubElement(root, "Component", {
            "name": o.name, "kind": ntype,
            "manufacturer": sv.get("manufacturer", [""])[0],
            "part_number": sv.get("part_number", [""])[0]})
        lo = [float(x) for x in o.shape.setvals.get("point1", [0, 0, 0])]
        hi = [float(x) for x in o.shape.setvals.get("point2", [1, 1, 1])]
        loc = ET.SubElement(comp, "Location", {"x": "0", "y": "0", "z": "0",
                                               "unit": "mm"})
        size = ET.SubElement(comp, "Size", unit="mm")
        size.set("x", "%.6g" % ((hi[0] - lo[0]) * 1000.0))
        size.set("y", "%.6g" % ((hi[1] - lo[1]) * 1000.0))
        size.set("z", "%.6g" % ((hi[2] - lo[2]) * 1000.0))
        th = ET.SubElement(comp, "Thermal")
        for tag, key in (("Rjc", "rjc"), ("Rjb", "rjb"), ("Power", "power")):
            ET.SubElement(th, tag, {"unit": "K/W" if tag != "Power" else "W"})
        # fill values after child creation (ET order ok but values needed)
        for el, key in zip(th, ("Rjc", "Rjb", "Power")):
            el.text = sv.get({"Rjc": "rjc", "Rjb": "rjb",
                              "Power": "power"}[key], ["1.0"])[0]
        nodes = sv.get("net_nodes")
        if nodes:
            for nm, r in json.loads(nodes[0]):
                ET.SubElement(th, "Node", {"name": nm, "r": "%g" % r})
    return ET.tostring(root, encoding="unicode")


def write_ecxml(path, model):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write(parts_to_ecxml(model))
    return path
# --------------------------------------------------------------------------- #
# IDF (v3 text) import/export: board outline + components
# --------------------------------------------------------------------------- #

def parse_idf(text):
    """Minimal IDF 3.0 subset: BOARD/OUTLINE + COMPONENTS sections."""
    board = None
    comps = []
    sect = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        up = line.upper()
        if up.startswith("BOARD"):
            sect = "board"
            continue
        if up.startswith("COMPONENTS"):
            sect = "component"
            continue
        if up.startswith("END"):
            sect = None
            continue
        if sect == "board":
            part = line.split()
            if len(part) >= 4 and len(part) <= 9:
                try:
                    x = float(part[-2])
                    y = float(part[-1])
                except ValueError:
                    continue
                if board is None:
                    board = {"min": [x, y], "max": [x, y]}
                else:
                    board["min"][0] = min(board["min"][0], x)
                    board["min"][1] = min(board["min"][1], y)
                    board["max"][0] = max(board["max"][0], x)
                    board["max"][1] = max(board["max"][1], y)
        elif sect == "component":
            m = re.match(r'^([^,]+)\s*,\s*([^,]+),\s*([^,]+),\s*'
                         r'([-\d.eE+]+),\s*([-\d.eE+]+),\s*(-?\d+)', line)
            if m:
                comps.append({"ref": m.group(1).strip(),
                              "part": m.group(2).strip(),
                              "side": m.group(3).strip(),
                              "x": float(m.group(4)),
                              "y": float(m.group(5)),
                              "rot": float(m.group(6))})
    return {"board": board, "components": comps}


def import_idf_path(path, model, offset=(0.0, 0.0, 0.0)):
    """Create pcb + package objects from an IDF file (mm -> m conversion)."""
    with open(path, encoding="latin-1", errors="replace") as fh:
        data = parse_idf(fh.read())
    created = []
    board = data.get("board")
    if board:
        from ice_create import default_object
        lo = (board["min"][0] / 1000.0 + offset[0],
              board["min"][1] / 1000.0 + offset[1], offset[2])
        hi = (board["max"][0] / 1000.0 + offset[0],
              board["max"][1] / 1000.0 + offset[1], offset[2] + 0.0016)
        idx = model.count_all()
        pcb = default_object("pcb", "pcb_ecad", index=idx,
                             creation_order=idx + 1)
        pcb.shape.setvals["point1"] = [str(v) for v in lo]
        pcb.shape.setvals["point2"] = [str(v) for v in hi]
        sv = getattr(pcb, "setvals", None) or {}
        sv["pcb_type"] = ["detailed"]
        sv["source"] = ["IDF"]
        pcb.setvals = sv
        model.objects.append(pcb)
        created.append(pcb)
    for comp in data.get("components", []):
        from ice_create import default_object
        name = "pkg_%s" % comp["ref"]
        i = 2
        while model.object_by_name(name) is not None:
            name = "pkg_%s_%d" % (comp["ref"], i)
            i += 1
        s = _part_size(comp["part"])
        cx = comp["x"] / 1000.0 + offset[0]
        cy = comp["y"] / 1000.0 + offset[1]
        cz = offset[2] + 0.0016
        idx = model.count_all()
        o = default_object("package", name, index=idx, creation_order=idx + 1)
        o.shape.setvals["point1"] = [str(cx - s[0] / 2), str(cy - s[1] / 2),
                                     str(cz)]
        o.shape.setvals["point2"] = [str(cx + s[0] / 2), str(cy + s[1] / 2),
                                     str(cz + s[2])]
        sv = getattr(o, "setvals", None) or {}
        sv["package_type"] = ["generic"]
        sv["part"] = [comp["part"]]
        sv["rotation"] = ["%g" % comp["rot"]]
        o.setvals = sv
        model.objects.append(o)
        created.append(o)
    return created, data


_PART_BOX = {
    "RESISTOR": (0.006, 0.003, 0.0015),
    "CAPACITOR": (0.004, 0.003, 0.0018),
    "IC": (0.010, 0.008, 0.0016),
    "SOT23": (0.003, 0.0028, 0.0013),
    "SOIC": (0.009, 0.004, 0.0018),
}


def _part_size(part):
    for k, v in _PART_BOX.items():
        if k in part.upper():
            return v
    return (0.005, 0.004, 0.0015)


def export_idf(path, model):
    """Write a minimal IDF subset from model pcb + package objects."""
    lines = ["IDF v3", "BOARD", "OUTLINE"]
    pcb = None
    parts = []
    for o in model._all_objects():
        if o.kind == "pcb" and pcb is None:
            pcb = o
        elif o.kind in ("package", "block"):
            parts.append(o)
    if pcb is not None:
        lo = [float(x) for x in pcb.shape.setvals["point1"]]
        hi = [float(x) for x in pcb.shape.setvals["point2"]]
        x0, y0 = lo[0] * 1000, lo[1] * 1000
        x1, y1 = hi[0] * 1000, hi[1] * 1000
        lines.append("0 %.6f %.6f" % (x0, y0))
        lines.append("0 %.6f %.6f" % (x1, y0))
        lines.append("0 %.6f %.6f" % (x1, y1))
        lines.append("0 %.6f %.6f" % (x0, y1))
        lines.append("END BOARD")
        lines.append("COMPONENTS")
        for o in parts:
            lo = [float(x) for x in o.shape.setvals.get("point1",
                                                        [0, 0, 0])]
            hi = [float(x) for x in o.shape.setvals.get("point2",
                                                        [1, 1, 1])]
            cx = (lo[0] + hi[0]) / 2 * 1000
            cy = (lo[1] + hi[1]) / 2 * 1000
            sv = getattr(o, "setvals", None) or {}
            rot = sv.get("rotation", ["0"])[0]
            lines.append("%s, %s, TOP, %.6f, %.6f, %s" %
                         (o.name, sv.get("part", ["UNKNOWN"])[0],
                          cx, cy, rot))
        lines.append("END COMPONENTS")
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
# --------------------------------------------------------------------------- #
# Networks, JEDEC PTD/JEP30, Powermaps (5 formats), EM Mapping, ICB
# --------------------------------------------------------------------------- #

def parse_networks(text):
    """Simple line format: 'node NAME X Y Z' / 'link N1 N2 R C' /
    '# name=N' metadata."""
    nodes = {}
    links = []
    meta = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            if line.startswith("#"):
                m = re.match(r'#\s*(\w+)\s*=\s*(\S+)', line)
                if m:
                    meta[m.group(1)] = m.group(2)
            continue
        parts = line.split()
        if parts[0] == "node" and len(parts) >= 5:
            nodes[parts[1]] = (float(parts[2]), float(parts[3]),
                               float(parts[4]))
        elif parts[0] == "link" and len(parts) >= 4:
            links.append((parts[1], parts[2],
                          float(parts[3]) if len(parts) > 3 else 0.0,
                          float(parts[4]) if len(parts) > 4 else 0.0))
    return {"nodes": nodes, "links": links, "meta": meta}


def register_networks(model, name, data):
    from ice_create import default_object
    idx = model.count_all()
    o = default_object("network", name, index=idx, creation_order=idx + 1)
    xs = [v[0] for v in data["nodes"].values()]
    ys = [v[1] for v in data["nodes"].values()]
    zs = [v[2] for v in data["nodes"].values()]
    lo = (min(xs + [0.0]), min(ys + [0.0]), min(zs + [0.0]))
    hi = (max(xs + [0.001]), max(ys + [0.001]), max(zs + [0.001]))
    _ensure_shape(o, lo, hi)
    sv = getattr(o, "setvals", None) or {}
    sv["network_type"] = ["net"]
    sv["net_nodes"] = [json.dumps(data["nodes"])]
    sv["net_links"] = [json.dumps(data["links"])]
    sv["network_name"] = [data.get("meta", {}).get("name", name)]
    o.setvals = sv
    model.objects.append(o)
    return o


def export_networks(path, model):
    lines = ["# name=%s" % (getattr(model, "name", "network"))]
    for o in model._all_objects():
        if o.kind != "network":
            continue
        sv = getattr(o, "setvals", None) or {}
        nodes = json.loads(sv.get("net_nodes", ["{}"])[0])
        links = json.loads(sv.get("net_links", ["[]"])[0])
        for n, p in nodes.items():
            lines.append("node %s %g %g %g" % (n, p[0], p[1], p[2]))
        for l in links:
            lines.append("link %s %s %g %g" % (l[0], l[1], l[2], l[3]))
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# --------------------------------------------------------------------------- #
# JEDEC PTD / JEP30 (text sections)
# --------------------------------------------------------------------------- #

def parse_jedec(text):
    sect = None
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        up = line.upper()
        if up.startswith("[") and up.endswith("]"):
            sect = up.strip("[]")
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            out.append((sect, k.strip(), v.strip()))
        elif sect and len(line.split()) >= 2:
            parts = line.split()
            out.append((sect, parts[0], " ".join(parts[1:])))
    return out


def register_jedec(model, entries):
    """Apply package/DIE keys onto a package object (PTD section table)."""
    from ice_create import default_object
    idx = model.count_all()
    o = default_object("package", "ptd_pkg", index=idx,
                       creation_order=idx + 1)
    sv = getattr(o, "setvals", None) or {}
    for sect, key, val in entries:
        if sect == "PACKAGE" and key.upper() in ("WIDTH", "LENGTH", "X", "Y"):
            sv.setdefault("ptd_%s" % key.lower(), []).append(val)
        elif sect == "DIE":
            sv.setdefault("ptd_die", []).append(val)
        elif sect == "ATTRIBUTES":
            sv.setdefault("ptd_attr", []).append("%s=%s" % (key, val))
    o.setvals = sv
    model.objects.append(o)
    return o


def export_jedec(path, model):
    lines = ["[PACKAGE]", "NAME=%s" % getattr(model, "name", "pkg")]
    for o in model._all_objects():
        if o.kind != "package":
            continue
        sv = getattr(o, "setvals", None) or {}
        for k, v in sv.items():
            if k.startswith("ptd_"):
                lines.append("%s=%s" % (k[4:].upper(), " ".join(
                    str(x) for x in v)))
    with open(path, "w", encoding="latin-1") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# --------------------------------------------------------------------------- #
# Powermaps (5 formats) — generic row parser returning [(x, y, value)]
# --------------------------------------------------------------------------- #

def parse_powermap(path, fmt):
    rows = []
    with open(path, encoding="latin-1", errors="replace") as fh:
        text = fh.read()
    lines = text.splitlines()
    i = 0
    if fmt == "tab":
        for line in lines:
            p = re.match(r'^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)',
                         line)
            if p:
                rows.append((float(p.group(1)), float(p.group(2)),
                             float(p.group(3))))
    elif fmt == "i2p":
        # Firebolt: POWERSET/POINT sections with x y watts
        for line in lines:
            p = re.match(r'^\s*POINT\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
                         r'([-\d.eE+]+)', line.upper())
            if p:
                rows.append((float(p.group(1)), float(p.group(2)),
                             float(p.group(3))))
    elif fmt == "ctm":
        # RedHawk CTM text: rows of x y power after the header
        for line in lines:
            p = re.match(r'^\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+'
                         r'([-\d.eE+]+)\s*$', line)
            if p:
                rows.append((float(p.group(1)), float(p.group(2)),
                             float(p.group(3))))
    elif fmt == "sentinel":
        # Apache Sentinel TI profile: "X,Y,TEMP" rows
        for line in lines:
            p = re.match(r'^\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*'
                         r'([-\d.eE+]+)', line)
            if p:
                rows.append((float(p.group(1)), float(p.group(2)),
                             float(p.group(3))))
    elif fmt == "apache":
        for line in lines:
            p = re.match(r'^\s*([-\d.eE+]+)\s*[,;]\s*([-\d.eE+]+)\s*[,;]\s*'
                         r'([-\d.eE+]+)', line)
            if p:
                rows.append((float(p.group(1)), float(p.group(2)),
                             float(p.group(3))))
    return rows


def powermap_extent(rows):
    if not rows:
        return None
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    return (min(xs), min(ys)), (max(xs), max(ys))


def apply_em_mapping(model, losses, kind="volumetric"):
    """EM Mapping: dict name->watt -> source objects / setvals."""
    from ice_create import default_object
    created = []
    for name, watt in losses.items():
        idx = model.count_all()
        o = default_object("source", "em_%s" % name, index=idx,
                           creation_order=idx + 1)
        sv = getattr(o, "setvals", None) or {}
        sv["power"] = ["%g" % float(watt)]
        sv["source_type"] = ["power"]
        sv["em_mapping"] = [kind]
        o.setvals = sv
        model.objects.append(o)
        created.append(o)
    return created


# --------------------------------------------------------------------------- #
# ICB reader (iceecad.exe INTERMEDIATE BOARD format grammar)
# --------------------------------------------------------------------------- #

def parse_icb(text):
    """ICB sections: board_outline / layers / shapes / vias / nets."""
    out = {"board_outline": [], "layers": [], "shapes": [], "vias": [],
           "nets": []}
    current = None
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("[start"):
            m = re.match(r'\[\s*start\s+(\w+)\]', low)
            current = m.group(1) if m else None
            if current not in out:
                current = None
            continue
        if low.startswith("[end"):
            current = None
            continue
        if current == "board_outline":
            parts = s.split()
            if len(parts) >= 2:
                try:
                    out["board_outline"].append((float(parts[0]),
                                                 float(parts[1])))
                except ValueError:
                    pass
        elif current == "layers" and s:
            out["layers"].append(s)
        elif current == "shapes" and s:
            out["shapes"].append(s)
        elif current == "vias" and s:
            out["vias"].append(s)
        elif current == "nets" and s:
            out["nets"].append(s)
        elif current == "layer" and s:
            out["layers"].append(s)
        elif current == "shape" and s:
            out["shapes"].append(s)
        elif current == "via" and s:
            out["vias"].append(s)
        elif current == "net" and s:
            out["nets"].append(s)
    return out


def icb_metal_fractions(icb, board_area=None):
    """Metal fraction per layer from shapes rows: 'layer x0 y0 x1 y1 ...'."""
    fracs = {}
    areas = {}
    if board_area is None:
        bl = icb["board_outline"]
        if bl:
            xs = [p[0] for p in bl]
            ys = [p[1] for p in bl]
            board_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    for row in icb["shapes"]:
        parts = row.split()
        if len(parts) < 5:
            continue
        layer, rest = parts[0], parts[1:]
        try:
            xs = [float(v) for v in rest[0::2]]
            ys = [float(v) for v in rest[1::2]]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        except ValueError:
            continue
        areas[layer] = areas.get(layer, 0.0) + area
    if board_area:
        for layer, a in areas.items():
            fracs[layer] = a / board_area
    return fracs

# ---- Phase D1: AEdt (Electronics Desktop) script export + metal display ----

def export_aedt(path, model):
    """Write an ANSYS Electronics Desktop python script that recreates the
    ECAD components (block/source/package -> placed blocks with material)."""
    aedt = ["# generated by icedecoding (ANSYS Electronics Desktop script)",
            "from pyaedt import Hfss", "hfss = Hfss()"]
    idx = 1
    for o in model._all_objects():
        sh = getattr(o, "shape", None)
        sv = getattr(sh, "setvals", None) or {}
        p1 = sv.get("point1")
        p2 = sv.get("point2")
        if not (isinstance(p1, (list, tuple)) and
                isinstance(p2, (list, tuple))):
            continue
        name = o.name.replace(" ", "_")
        aedt.append("mk = hfss.modeler.create_box([%.6g, %.6g, %.6g],"
                    " [%.6g, %.6g, %.6g], name=%r)" % (
                        float(p1[0]), float(p1[1]), float(p1[2]),
                        float(p2[0]) - float(p1[0]),
                        float(p2[1]) - float(p1[1]),
                        float(p2[2]) - float(p1[2]), o.name))
        aedt.append("mk.material_name = %r" % name)
        idx += 1
    aedt.append("hfss.save_project()")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aedt))
    return path


def metal_fraction_summary(icb, board_area=None):
    """Human-readable metal fraction / layer summary (Show metal fractions
    display).  board_area: optional gross board area (m^2)."""
    out = []
    fr = icb_metal_fractions(icb, board_area)
    for row in fr:
        out.append("%-12s %8.3f%%" % (row.get("layer", "?"),
                                      row.get("fraction", 0.0) * 100))
    return "\n".join(out)

# ---- Phase D1 (continued): ICB layer -> objects + metal display ----
def _icb_layer_scale(icb):
    return 0.05, 0.05
def icb_to_objects(model, icb, scale=0.001):
    created = []
    bl = icb.get('board_outline') or []
    for name in icb.get('layers', []):
        parts = [p.strip() for p in name.split(',')]
        if len(parts) < 3:
            continue
        lname, mat, ltype = parts[0], parts[1], parts[2]
        thick = float(parts[3]) if len(parts) > 3 and parts[3].replace('.','').isdigit() else 1.0
        sx, sy = _icb_layer_scale(icb)
        z = thick * scale
        base = (0.0, 0.0, 0.0)
        if bl:
            xs=[p[0] for p in bl]; ys=[p[1] for p in bl]
            sx=(max(xs)-min(xs))*scale; sy=(max(ys)-min(ys))*scale
            base=(min(xs)*scale, min(ys)*scale, 0.0)
        kind = 'pcb' if ltype.upper().startswith('COND') else 'block'
        from ice_create import default_object
        obj = default_object(kind, lname)
        _ensure_shape(obj, base, (base[0]+sx, base[1]+sy, base[2]+z))
        if getattr(obj, 'setvals', None) is None:
            obj.setvals = {}
        obj.setvals['material'] = [mat]
        obj.setvals['layer_type'] = [ltype]
        obj.setvals['thickness'] = [str(thick)]
        model.objects.append(obj)
        created.append(lname)
    return created
def metal_fraction_display(icb, board_area=None):
    rows = ['Layer                Material              Type          Thickness(mm)']
    for name in icb.get('layers', []):
        parts = [p.strip() for p in name.split(',')]
        if len(parts) < 3:
            continue
        rows.append('%-20s %-21s %-12s %s' % (parts[0][:20], parts[1][:21], parts[2][:12], parts[3] if len(parts)>3 else '-'))
    return chr(10).join(rows)