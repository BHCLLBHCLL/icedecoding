# -*- coding: utf-8 -*-
"""
P6 reports: HTML report (model summary), summary data (templim table),
point report helpers. Runs headless (pure text generation).
"""
import html

REPORT_STYLE = """
body { font-family: Arial, sans-serif; margin: 24px; color: #212121; }
h1 { color: #1f4e79; }
h2 { color: #37474f; border-bottom: 1px solid #cfd8dc; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th, td { border: 1px solid #b0bec5; padding: 4px 8px; font-size: 13px; }
th { background: #eceff1; }
"""


def object_table(project):
    rows = []
    model = getattr(project, "model", None)
    if model is None:
        return rows
    for o in model._all_objects():
        sh = getattr(o, "shape", None)
        stype = getattr(sh, "type", "") if sh is not None else ""
        p1 = getattr(sh, "setvals", {}).get("point1", ["-", "-", "-"]) \
            if sh is not None else ["-", "-", "-"]
        p2 = getattr(sh, "setvals", {}).get("point2", ["-", "-", "-"]) \
            if sh is not None else ["-", "-", "-"]
        rows.append((o.name, o.kind, stype, " ".join(str(x) for x in p1),
                     " ".join(str(x) for x in p2)))
    return rows


def html_report(project, mesh=None, title="ANSYS Icepak model report"):
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
             "<title>%s</title>" % html.escape(title),
             "<style>%s</style></head><body>" % REPORT_STYLE,
             "<h1>%s</h1>" % html.escape(title),
             "<h2>Project</h2><table><tr><th>Name</th><td>%s</td></tr>"
             "<tr><th>Objects</th><td>%d</td></tr></table>" % (
                 html.escape(getattr(project, "name", "untitled")),
                 len(object_table(project)))]
    if mesh is not None:
        parts.append("<h2>Mesh</h2><table><tr><th>Cells</th><td>%d</td>"
                     "<th>Nodes</th><td>%d</td></tr></table>" %
                     (mesh.cell_count, mesh.node_count))
    parts.append("<h2>Objects</h2><table><tr><th>Name</th><th>Kind</th>"
                 "<th>Shape</th><th>Start</th><th>End</th></tr>")
    for name, kind, stype, p1, p2 in object_table(project):
        parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td></tr>" % tuple(
                         html.escape(str(v)) for v in (name, kind, stype,
                                                       p1, p2)))
    parts.append("</table><h2>Generated</h2><p>ice viewer report</p>"
                 "</body></html>")
    return "".join(parts)


def summary_data(project, mesh=None):
    """Summary report rows: (entity, target, current) — templim style."""
    rows = []
    current = {}
    if mesh is not None:
        from ice_solve import obj_temperature
        for (i, j, k), name in mesh.cell_obj.items():
            val = obj_temperature_for(mesh, name)
            current[name] = max(current.get(name, -1e300), val)
    for name, val in sorted(current.items()):
        target = 100.0 if "source" in name or "block" in name else 85.0
        rows.append((name, target, val))
    return rows


def obj_temperature_for(mesh, name):
    """Synthetic per-object temperature (report/post displays)."""
    from ice_solve import DEFAULT_OBJ_TEMPS
    for key, t in DEFAULT_OBJ_TEMPS.items():
        if name.startswith(key) or key in name:
            return t
    return 50.0


def write_html_report(path, project, mesh=None):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_report(project, mesh))
    return path


def real_stats(project_dir):
    """Real temperature summary dict (or None)."""
    try:
        from fluent_fdat import real_temp_cloud_face
        r = real_temp_cloud_face(project_dir)
        if r is None:
            return None
        centers, temps = r
        return {"cells": int(len(temps)), "tmin": float(temps.min()),
                "tmax": float(temps.max()), "tmean": float(temps.mean())}
    except Exception:
        return None


def real_summary_table_html(project_dir, title="Temperature summary"):
    """Summary report rows: real temperature stats."""
    st = real_stats(project_dir)
    if st is None:
        return "<h2>%s</h2><p>No real temperature data.</p>" % title
    return ("<h2>%s</h2><table><tr><th>Cells</th><td>%d</td></tr>"
            "<tr><th>Min</th><td>%.2f K</td></tr>"
            "<tr><th>Max</th><td>%.2f K</td></tr>"
            "<tr><th>Mean</th><td>%.2f K</td></tr>"
            "<tr><th>Range</th><td>%.2f K</td></tr></table>" %
            (title, st["cells"], st["tmin"], st["tmax"], st["tmean"],
             st["tmax"] - st["tmin"]))


def point_report_html(project_dir, points):
    """Point report: real temperature at a list of points."""
    import html
    from fluent_fdat import real_point_temp
    rows = ["<h2>Point report</h2>"
            "<table><tr><th>Point</th><th>Temperature</th></tr>"]
    for p in points:
        t = real_point_temp(project_dir, p)
        rows.append("<tr><td>(%.3f, %.3f, %.3f)</td><td>%s</td></tr>" %
                    (p[0], p[1], p[2],
                     "%.2f K" % t if t is not None else "n/a"))
    rows.append("</table>")
    return "".join(rows)


def full_report_html(project_dir, title="ANSYS Icepak report",
                     points=None):
    """Full report: header + real temperature summary + histogram section."""
    try:
        from fluent_fdat import real_temp_cloud_face
        r = real_temp_cloud_face(project_dir)
    except Exception:
        r = None
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
             "<title>%s</title>" % html.escape(title),
             "<style>%s</style></head><body><h1>%s</h1>"
             % (REPORT_STYLE, html.escape(title))]
    if r is not None:
        centers, temps = r
        parts.append(real_temp_section(centers, temps))
    else:
        parts.append("<p>No real temperature data.</p>")
    parts.append(real_summary_table_html(project_dir))
    if points:
        parts.append(point_report_html(project_dir, points))
    parts.append("</body></html>")
    return "".join(parts)


def write_real_report(path, project_dir, points=None):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(full_report_html(project_dir, points=points))
    return path


def histogram_svg(values, bins=12, width=440, height=160, color="#1f4e79"):
    """Inline SVG bar histogram of a value array -> (svg, hist, edges)."""
    import math
    if not values:
        return "<svg width='%d' height='%d'></svg>" % (width, height), [], []
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1e-12
    hist = [0] * bins
    for v in values:
        i = min(bins - 1, int((v - lo) / span * bins))
        hist[i] += 1
    n = len(values)
    maxc = max(hist) or 1
    pad = 8
    bh = (height - 2 * pad) / maxc
    bw = (width - 2 * pad) / bins
    parts = ["<svg width='%d' height='%d' xmlns='http://www.w3.org/2000/svg'>"
             % (width, height)]
    for i, c in enumerate(hist):
        x = pad + i * bw
        h = max(1.0, c * bh)
        parts.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' "
                     "fill='%s' stroke='#ffffff' stroke-width='0.5'/>" %
                     (x, height - pad - h, bw - 1, h, color))
    parts.append("</svg>")
    return "".join(parts), hist, [lo + i * span / bins for i in range(bins + 1)]


def real_temp_section(centers, temps, title="Temperature field"):
    """HTML section: real temperature stats + SVG histogram."""
    import html
    import numpy as np
    hist_svg, hist, edges = histogram_svg(list(temps))
    lo, hi = float(min(temps)), float(max(temps))
    mean = float(np.mean(temps))
    p = ["<h2>%s</h2>" % html.escape(title),
         "<table><tr><th>Cells</th><td>%d</td></tr>"
         "<tr><th>Min</th><td>%.2f K</td></tr>"
         "<tr><th>Max</th><td>%.2f K</td></tr>"
         "<tr><th>Mean</th><td>%.2f K</td></tr>"
         "<tr><th>Range</th><td>%.2f K</td></tr></table>"
         % (len(temps), lo, hi, mean, hi - lo)]
    if centers is not None and len(centers):
        xr = centers[:, 0].min(), centers[:, 0].max()
        yr = centers[:, 1].min(), centers[:, 1].max()
        zr = centers[:, 2].min(), centers[:, 2].max()
        p.append("<table><tr><th>Extent X</th><td>%.3f..%.3f</td></tr>"
                 "<tr><th>Extent Y</th><td>%.3f..%.3f</td></tr>"
                 "<tr><th>Extent Z</th><td>%.3f..%.3f</td></tr></table>"
                 % (xr[0], xr[1], yr[0], yr[1], zr[0], zr[1]))
    p.append(hist_svg)
    return "".join(p)
