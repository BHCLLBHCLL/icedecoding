# -*- coding: utf-8 -*-
"""I3: sharded test runner.

The full suite (313+ tests, 9-20 min, ~20 IceGui constructions + oracle
iceecad runs) is unreliable in one process - the environment kills it under
memory/time pressure.  This runner splits the suite into per-subsystem shards,
each executed in a FRESH interpreter subprocess (memory freed, iceecad timeout
isolated), and aggregates pass/fail per shard.

Usage:
    python tools/run_sharded.py --list
    python tools/run_sharded.py --shard data
    python tools/run_sharded.py --all            # every shard, exit != 0 on any
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

# prefi x -> shard (data-driven; every discovered file must land in a shard)
SHARDS = {
    "data": ["test_p11", "test_p12", "test_p13", "test_p14", "test_p15",
             "test_p16", "test_p18", "test_p19_grid32", "test_p19_fdat",
             "test_p19_fdatvars", "test_p19_config", "test_p19_problem"],
    "mesh": ["test_p5_mesh", "test_p19_quality", "test_p19_gridctl",
             "test_p19_gates"],
    "post": ["test_p19_post", "test_p19_cloud", "test_p19_isosurface",
             "test_p19_tempcloud", "test_p19_history", "test_p19_report",
             "test_p19_curves", "test_p19_solve", "test_p19_solvefields",
             "test_p6_solve"],
    "ecad": ["test_p19_ecad", "test_p19_icb", "test_p19_ecad_oracle",
             "test_p19_metal", "test_p19_export", "test_p19_powermap",
             "test_p8_ecad"],
    "macros": ["test_p7_macros", "test_p19_macrolang", "test_p19_libwizard",
               "test_p19_macrodiff"],
    "solver": ["test_p10_solver", "test_p19_heatsolver", "test_p19_batch",
               "test_p19_writeback", "test_p19_g4"],
    "gui": ["test_golden_ui", "test_gui", "test_p1_shell", "test_p2_tree",
            "test_p3_view3d", "test_p3b_align", "test_p4_forms",
            "test_p9_prefs", "test_p19_editors", "test_p19_viewcontract",
            "test_p19_wbfile", "test_p19_windows", "test_p19_multibtn",
            "test_p19_treefx", "test_p19_transient", "test_p19_units",
            "test_p19_zoom", "test_p19_annotimg", "test_p19_cli"],
    "misc": ["test_tzr", "test_create"],
}


def discover():
    """All test_*.py files -> (file, shard)."""
    out = []
    for f in sorted(glob.glob(os.path.join(TESTS, "test_*.py"))):
        base = os.path.basename(f)[:-3]
        shard = None
        for name, prefixes in SHARDS.items():
            if any(base == p or base.startswith(p + "_") or
                   base.startswith(p) for p in prefixes):
                shard = name
                break
        out.append((f, shard or "misc"))
    return out


def assign():
    """{shard: [files]} for every discovered test file."""
    groups = {}
    for f, shard in discover():
        groups.setdefault(shard, []).append(f)
    return groups


def run_shard(name):
    """Run one shard in a fresh subprocess -> (returncode, output)."""
    files = assign().get(name, [])
    if not files:
        return 0, "no tests"
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + files
    print("== shard %s (%d tests) ==" % (name, len(files)), flush=True)
    p = subprocess.run(cmd, cwd=ROOT)
    return p.returncode, None


def main(argv):
    args = argv[1:]
    if "--list" in args:
        for name, files in sorted(assign().items()):
            print("%-8s %2d test files" % (name, len(files)))
        print("total", sum(len(v) for v in assign().values()), "files")
        return 0
    if "--shard" in args:
        name = args[args.index("--shard") + 1]
        return run_shard(name)[0]
    # --all (default): run every shard, aggregate
    failed = []
    for name in sorted(assign()):
        rc, _ = run_shard(name)
        if rc != 0:
            failed.append(name)
    print("== sharded run done: %s ==" % (
        "FAILED: " + ", ".join(failed) if failed else "ALL PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
