# -*- coding: utf-8 -*-
"""P16: continuous-subdivision cross-scan runner (non-integer m, staggered
lines + clipping) — every tutorial job is replicated with an exact
(a,b,c) axis triple whose product lands inside 1% of the oracle node count.

Results accumulate into tools/probe_work/fine_batch.json per project."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "tools", "probe_work", "fine_batch.json")
ROOT = r"D:\training\icepak"

# nested job dirs (root dir has no runnable model)
SUB = {
    "11-1compact-package": "compack-package",
}


def job_dir(name):
    sub = SUB.get(name)
    if sub:
        return os.path.join(ROOT, name, sub)
    return os.path.join(ROOT, name)


def run_scan(name):
    try:
        return _run_scan(name)
    except Exception as e:
        return {"project": name, "skipped": "%s" % e}


def _run_scan(name):
    from icepak_parser.project import IcepakProject
    from ice_refine import tune_continuous
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
    rec = tune_continuous(d, node_t, model=model)
    if rec is None:
        return {"project": name, "skipped": "no axis triple solved",
                "node_target": node_t, "objects": n_objs}
    cell_t = (proj.get("cas") or {}).get("cells")
    out = {
        "project": name, "engine": "continuous",
        "node_target": node_t, "cell_target": cell_t,
        "best_err": rec["err"],
        "axis_counts": rec["axis_counts"],
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
            if results.get("_version") != "p16":
                results = {}
        except (OSError, ValueError):
            results = {}
    if not results:
        results = {"_version": "p16"}
    for name in names:
        if name in results:
            continue
        print("scanning", name, flush=True)
        r = run_scan(name)
        results[name] = r
        json.dump(results, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if r.get("best_err") is not None:
            print("  %s err=%.4f%% nodes=%d/%d cells=%d axes=%s (%.1fs)" %
                  (name, r["best_err"] * 100, r["nodes"], r["node_target"],
                   r["cells"], r["axis_counts"], r["elapsed_s"]), flush=True)
        else:
            print("  %s %s" % (name, r.get("skipped")), flush=True)
    print("DONE", len(results), "entries")


if __name__ == "__main__":
    main(sys.argv)
