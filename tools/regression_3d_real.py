# -*- coding: utf-8 -*-
"""Real-project 3D interactive regression (desktop GL environment).

Opens each ANSYS Icepak project in the real GUI (enable_3d=True), rebuilds the
scene, drives camera/shading/panes/names/blank interactions, captures a PNG
screenshot per project into _report/screenshots and writes
_report/3d_regression_summary.json.

Usage: python tools/regression_3d_real.py [--root D:/training/icepak]
       [--limit N] [--out _report/screenshots]
"""
import argparse
import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication  # noqa: E402

import ice_gui  # noqa: E402


def maybe(op):
    try:
        op()
        return True, ""
    except Exception as e:
        return False, "%r" % e


def screenshot(win, out_path):
    try:
        from vtk.vtkRenderingCore import vtkWindowToImageFilter
        w = win.renderer.GetRenderWindow()
        wif = vtkWindowToImageFilter()
        wif.SetInput(w)
        wif.Update()
        from vtk.vtkIOImage import vtkPNGWriter
        writer = vtkPNGWriter()
        writer.SetFileName(out_path)
        writer.SetInputConnection(wif.GetOutputPort())
        writer.Write()
        return True
    except Exception:
        return False


def run_one(project_dir, out_dir, app):
    name = os.path.basename(project_dir)
    rec = {"project": name, "path": project_dir, "steps": {}}
    try:
        win = ice_gui.IceGui(project_dir, enable_3d=True, show_welcome=False)
        win.show()
        app.processEvents()
        rec["steps"]["open+rebuild"] = maybe(win._rebuild_scene)
        actors = len(getattr(win, "actors", []) or [])
        rec["actors"] = actors
        rec["steps"]["home"] = maybe(win._home)
        rec["steps"]["iso"] = maybe(lambda: win._orient("iso"))
        rec["steps"]["zoom_in"] = maybe(win._zoom_in)
        rec["steps"]["fit"] = maybe(win._fit)
        rec["steps"]["shading"] = maybe(win._cycle_shading)
        rec["steps"]["names"] = maybe(lambda: win._set_names(1))
        rec["steps"]["panes2"] = maybe(lambda: win._set_view_panes(2))
        rec["steps"]["panes1"] = maybe(lambda: win._set_view_panes(1))
        rec["steps"]["panes4"] = maybe(lambda: win._set_view_panes(4))
        rec["steps"]["panes1b"] = maybe(lambda: win._set_view_panes(1))
        o = None
        for so in getattr(win, "_scene_objs", None) or []:
            if so.name != "cabinet":
                o = so
                break
        if o is not None:
            def _blank_it():
                win.selected = o.name
                win.project_tree.recreate = None
                win._blank_selected()
            rec["steps"]["blank"] = maybe(_blank_it)
        app.processEvents()
        rec["steps"]["render"] = maybe(
            lambda: win.renderer.GetRenderWindow().Render())
        shot = os.path.join(out_dir, "%s.png" % name)
        ok = screenshot(win, shot)
        rec["steps"]["screenshot"] = (ok, shot)
        rec["passed"] = all(s[0] for k, s in rec["steps"].items())
        win.close()
        app.processEvents()
    except Exception as e:
        rec["passed"] = False
        rec["error"] = "%r" % e
        rec["traceback"] = traceback.format_exc()
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"D:/training/icepak")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "_report",
                                                  "screenshots"))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    entries = [os.path.join(args.root, n) for n in sorted(os.listdir(args.root))
               if os.path.isdir(os.path.join(args.root, n))]
    if args.limit:
        entries = entries[:args.limit]
    app = QApplication(sys.argv[:1])
    results = []
    for e in entries:
        print("== %s" % os.path.basename(e), flush=True)
        rec = run_one(e, args.out, app)
        results.append(rec)
        print("   actors=%s passed=%s" % (rec.get("actors"), rec["passed"]),
              flush=True)
    summary_path = os.path.join(os.path.dirname(args.out),
                                "3d_regression_summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump({"results": results,
                   "passed": sum(1 for r in results if r["passed"]),
                   "total": len(results)}, fh, ensure_ascii=False, indent=1)
    ok = sum(1 for r in results if r["passed"])
    print("SUMMARY: %d/%d projects passed -> %s" %
          (ok, len(results), summary_path), flush=True)
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
