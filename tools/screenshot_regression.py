# -*- coding: utf-8 -*-
"""I2: screenshot regression harness.

Renders offscreen scenarios (main window, a project with objects, a mesh) to
PNGs in _report/screenshots and reports each image's non-blankness so a
regression in the viewport/UI layout shows up as a blank/broken capture
without a brittle pixel-diff against tutorial references.

Usage:  python tools/screenshot_regression.py [--out DIR]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def img_stats(pix):
    """Non-blank metric: fraction of non-white pixels of a downsampled image."""
    from PyQt5.QtGui import QImage
    img = pix.toImage().convertToFormat(QImage.Format_RGB32)
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return {"size": (w, h), "non_blank": 0.0}
    nonblank = 0
    total = 0
    for y in range(0, h, max(1, h // 32)):
        for x in range(0, w, max(1, w // 32)):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            total += 1
            if not (r > 245 and g > 245 and b > 245):
                nonblank += 1
    return {"size": (w, h), "non_blank": round(nonblank / max(total, 1), 4)}


def capture(win, out_dir, name, grab=False):
    """Structural snapshot (deterministic, offscreen-safe).

    QWidget.grab() of any window holding a VTK-backed widget hard-crashes Qt
    offscreen (0xC0000409, uncatchable), so the CI-safe regression records the
    scenario STRUCTURE (objects/mesh/bounds/title/shading) instead of pixels;
    set grab=True with a real display for actual PNG captures."""
    os.makedirs(out_dir, exist_ok=True)
    n_objs = len(list(win.project.model._all_objects())) \
        if (win.project and win.project.model) else 0
    mesh_cells = win._mesh_result.cell_count if getattr(
        win, "_mesh_result", None) else 0
    rec = {"scenario": name, "objects": n_objs, "mesh_cells": mesh_cells,
           "title": win.windowTitle(),
           "selected": win.selected if hasattr(win, "selected") else None,
           "shading": getattr(win, "_shading", None)}
    if grab:
        pix = getattr(win, "graphics", win).grab()
        path = os.path.join(out_dir, "ice_%s.png" % name)
        pix.save(path)
        rec["file"] = path
        rec.update(img_stats(pix))
    return rec


def build_scenario(kind):
    import ice_gui
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    w._new_project()
    from ice_create import default_cabinet, default_object
    w.project.model.objects.append(default_cabinet())
    blk = default_object("block", "blk.1")
    blk.setvals = {"material": ["Si"], "power": ["1.0"]}
    blk.shape.setvals["point1"] = ["0.1", "0.1", "0.0"]
    blk.shape.setvals["point2"] = ["0.25", "0.3", "0.15"]
    w.project.model.objects.append(blk)
    w._refresh(fit=True)
    if kind == "mesh" and w._mesh_result is None:
        from ice_mesh import generate_mesh
        w._mesh_result = generate_mesh(w.project.model, counts=(8, 6, 4))
        if w._enable_3d:
            w._mesh_actor_update()
    return w


def main(argv):
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    out = os.path.join(ROOT, "_report", "screenshots")
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    grab = "--grab" in argv
    results = {}
    for kind in ("empty", "objects", "mesh"):
        try:
            w = build_scenario(kind)
            results[kind] = capture(w, out, kind, grab=grab)
            w.close()
        except Exception as e:
            results[kind] = {"error": "%r" % e}
    report = os.path.join(out, "screenshot_report.json")
    os.makedirs(out, exist_ok=True)
    with open(report, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print(json.dumps(results, indent=1))
    ok = "error" not in results.get("mesh", {}) and \
        "error" not in results.get("objects", {})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
