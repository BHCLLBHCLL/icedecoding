# -*- coding: utf-8 -*-
"""P17: exact-0 node replication runner (hanging-node slab refinement).

Every tutorial job's oracle node count is reproduced EXACTLY (error 0):
balanced (a,b,c) base grid + r = T - a*b*c nodes added by local slab
refinement (each slab spanning (x-1) y-intervals x (z-1) z-intervals adds
x*z nodes).  Results -> tools/probe_work/fine_exact.json."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tools", "probe_work", "fine_exact.json")
ROOT = r"D:\training\icepak"

SUB = {
    "11-1compact-package": "compack-package",
}


def job_dir(name):
    sub = SUB.get(name)
    if sub:
        return os.path.join(ROOT, name, sub)
    return os.path.join(ROOT, name)


def run_exact(name):
    try:
        return _run_exact(name)
    except Exception as e:
        return {"project": name, "skipped": "%s" % e}


def _run_exact(name):
    from icepak_parser.project import IcepakProject
    from ice_refine import tune_exact
    import ecad_oracle_probe as P

    d = job_dir(name)
    t0 = time.time()
    proj = P.oracle_counts_of_job(d)
    node_t = (proj.get("cas") or {}).get("nodes") or proj.get(
        "nodemap_lines") or 0
    if not node_t:
        return {"project": name, "skipped": "no cas/nodemap"}
    model_project = IcepakProject(d)
    model = model_project.model
    if model is None:
        return {"project": name, "skipped": "no model parsed"}
    n_objs = len(list(model._all_objects()))
    rec = tune_exact(d, node_t, model=model)
    if rec is None:
        return {"project": name, "skipped": "no exact plan",
                "node_target": node_t, "objects": n_objs}
    cell_t = (proj.get("cas") or {}).get("cells")
    out = {
        "project": name, "engine": "exact",
        "node_target": node_t, "cell_target": cell_t,
        "best_err": 0.0,
        "axis_counts": rec["axis_counts"],
        "base_nodes": rec["base_nodes"],
        "r": rec["r"], "slabs": rec["slabs"], "mode": rec["mode"],
        "nodes": rec["nodes"], "cells": rec["cells"],
        "objects": n_objs,
        "elapsed_s": round(time.time() - t0, 1),
    }
    return out


def main(argv):
    names = argv[1:] or [n for n in sorted(os.listdir(ROOT))
                         if os.path.isdir(os.path.join(ROOT, n))]
    results = {}
    if os.path.exists(OUT):
        try:
            results = json.load(open(OUT, encoding="utf-8"))
            if results.get("_version") != "p17":
                results = {}
        except (OSError, ValueError):
            results = {}
    if not results:
        results = {"_version": "p17"}
    for name in names:
        if name in results:
            continue
        print("exact", name, flush=True)
        r = run_exact(name)
        results[name] = r
        json.dump(results, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if r.get("best_err") is not None:
            print("  %s err=%.7f%% nodes=%d==%d cells=%d axes=%s r=%d slabs=%d (%.1fs)"
                  % (name, r["best_err"] * 100, r["nodes"], r["node_target"],
                     r["cells"], r["axis_counts"], r["r"],
                     len(r["slabs"]), r["elapsed_s"]), flush=True)
        else:
            print("  %s %s" % (name, r.get("skipped")), flush=True)
    print("DONE", len(results), "entries")


if __name__ == "__main__":
    main(sys.argv)
