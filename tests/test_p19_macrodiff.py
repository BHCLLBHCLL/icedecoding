# -*- coding: utf-8 -*-
"""P19-5: macro oracle-diff harness (builtin rules + 845 official library parts)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from tools.macro_diff import (GOLDEN_PATH, diff_builtin, diff_library_part,
                              run_macro_diff, write_golden)
from ice_macros import BUILTIN_MACROS, scan_macro_library, build_macro
from icepak_parser.project import IcepakProject


def test_builtin_diff_zero():
    for key in sorted(BUILTIN_MACROS):
        deltas = diff_builtin(key)
        assert deltas == [], (key, deltas)


def test_library_diff_zero_sample():
    parts = scan_macro_library()
    assert len(parts) >= 800
    for macro in parts[:60]:
        deltas = diff_library_part(macro)
        assert deltas == [], (macro["name"], deltas)


def test_blower_builder_works():
    # the diff harness caught a latent bug: build_blower lacked default_object
    # import + setvals guard; it must build cleanly now
    proj = IcepakProject.empty("blw")
    created = build_macro(proj.model, "blower", {})
    assert created and created[0].kind == "blower"


def test_golden_anchors_match():
    import json
    golden = json.load(open(GOLDEN_PATH, encoding="utf-8"))
    assert golden["library_total"] == len(scan_macro_library())
    for key in sorted(BUILTIN_MACROS):
        assert golden["builtin"][key]["default_deltas"] == [], key


def test_run_macro_diff_full_zero():
    summary = run_macro_diff(lib_limit=None)
    assert summary["builtin_checked"] == 5
    assert summary["library_checked"] == summary["library_total"] >= 800
    assert summary["delta_total"] == 0, summary["library_deltas"][:5]
