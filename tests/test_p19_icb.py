# -*- coding: utf-8 -*-
"""Phase D1: ODB++/ANF -> ICB oracle sandbox pipeline (graceful boundary)."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_ecad import parse_icb
import tools.icb_oracle as O


def test_parse_icb_sections():
    icb = "[start board_outline]\n0.0 0.0\n50.0 0.0\n50.0 40.0\n0.0 40.0\n[end]\n[start layers]\nTOP\nBOTTOM\n[end]\n[start shapes]\nTOP 0 0 10 10\n[end]"
    out = parse_icb(icb)
    assert len(out["board_outline"]) == 4
    assert "TOP" in out["layers"]
    metal = out["shapes"]
    assert len(metal) == 1


def test_icb_oracle_sandbox_graceful():
    # always returns a dict; never raises, never touches user data
    r = O.run_iceecad(O.MINIMAL_ANF, tempfile.mkdtemp(prefix="ice_icb_"))
    assert isinstance(r, dict)
    assert "available" in r


def test_icb_oracle_locate():
    # locate returns a path or None; no crash
    p = O.locate_iceecad()
    assert p is None or isinstance(p, str)


def test_trace_iceecad_watcher_returns_list():
    import tools.trace_iceecad as T
    procs = T.iceecad_processes()
    assert isinstance(procs, list)
    for p in procs:
        assert "cmdline" in p or "error" in p
