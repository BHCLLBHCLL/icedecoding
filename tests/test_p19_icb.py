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


@pytest.mark.skipif(not os.path.exists(
        os.path.join("D:", os.sep, "training", "icepak", "6-2traces", "A1.anf")),
        reason="ANF oracle input missing")
def test_full_anf_to_icb_parse():
    import shutil
    import tempfile
    from ice_ecad import parse_icb
    d = tempfile.mkdtemp(prefix="icb_")
    out = os.path.join(d, "out")
    anf = os.path.join(d, "A1.anf")
    shutil.copy(os.path.join("D:", os.sep, "training", "icepak", "6-2traces",
                            "A1.anf"), anf)
    res = O.convert_anf_to_icb(anf, out)
    assert res["returncode"] == 0, res
    assert res.get("icb_file")
    icb = parse_icb(O.icb_text_of(res["icb_file"]))
    assert len(icb["layers"]) >= 2
    assert len(icb["shapes"]) > 0



@pytest.mark.skipif(not os.path.exists(
        os.path.join("D:", os.sep, "training", "icepak", "6-2traces", "A1.anf")),
        reason="ANF oracle input missing")
def test_icb_to_objects_and_metal_display():
    from ice_ecad import icb_to_objects, metal_fraction_display
    from icepak_parser.project import IcepakProject
    # regenerate ICB in temp
    import tempfile, shutil
    d = tempfile.mkdtemp(prefix="icb_")
    out = os.path.join(d, "out")
    anf = os.path.join(d, "A1.anf")
    shutil.copy(os.path.join("D:", os.sep, "training", "icepak", "6-2traces",
                            "A1.anf"), anf)
    res = O.convert_anf_to_icb(anf, out)
    assert res["returncode"] == 0
    icb = parse_icb(O.icb_text_of(res["icb_file"]))
    proj = IcepakProject.empty("icb")
    n = icb_to_objects(proj.model, icb)
    assert len(n) >= 2
    assert len(list(proj.model._all_objects())) >= 2
    tbl = metal_fraction_display(icb)
    assert "Layer" in tbl and "TOP" in tbl
