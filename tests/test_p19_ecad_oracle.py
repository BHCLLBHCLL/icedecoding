# -*- coding: utf-8 -*-
"""P19-D6: generalized ODB++/ANF -> ICB oracle sandbox pipeline."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import tools.icb_oracle as O
from ice_ecad import import_ecad_oracle
from icepak_parser.project import IcepakProject

ANF = os.path.join("D:", os.sep, "training", "icepak", "6-2traces", "A1.anf")
NEEDS_ANF = os.path.exists(ANF)
NEEDS_EXE = O.locate_iceecad() is not None
oracle_ok = NEEDS_ANF and NEEDS_EXE


def test_input_modes_table():
    assert O.INPUT_MODES == {'anf': 1, 'edb': 2, 'odbpp': 3}


def test_sniff_ecad_type():
    assert O.sniff_ecad_type("b.anf") == "anf"
    assert O.sniff_ecad_type("b.tgz") == "odbpp"
    assert O.sniff_ecad_type("b.tar.gz") == "odbpp"
    assert O.sniff_ecad_type("b.odb") == "odbpp"
    assert O.sniff_ecad_type("b.edb") == "edb"
    assert O.sniff_ecad_type(None) is None
    assert O.sniff_ecad_type("b.txt") is None


def test_convert_unknown_type_graceful():
    d = tempfile.mkdtemp(prefix="icb_")
    r = O.convert_ecad_to_icb("board.zzz", d)
    assert r["available"] is True
    assert r["error"] == "unknown ECAD input type"
    assert r["icb_file"] is None


@pytest.mark.skipif(not oracle_ok, reason="iceecad/A1.anf oracle missing")
def test_convert_ecad_to_icb_anf():
    import shutil
    d = tempfile.mkdtemp(prefix="icb_")
    out = os.path.join(d, "out")
    anf = os.path.join(d, "A1.anf")
    shutil.copy(ANF, anf)
    res = O.convert_ecad_to_icb(anf, out, input_type="anf")
    assert res["available"] is True
    assert res["input_type"] == "anf"
    assert res["mode"] == 1
    assert res["returncode"] == 0, res
    assert res["icb_file"]
    icb = O.parse_icb_file(res["icb_file"])
    assert len(icb["layers"]) >= 2
    assert len(icb["shapes"]) > 0


@pytest.mark.skipif(not oracle_ok, reason="iceecad/A1.anf oracle missing")
def test_import_ecad_oracle_creates_objects():
    import shutil
    proj = IcepakProject.empty("ecor")
    d = tempfile.mkdtemp(prefix="icb_")
    out = os.path.join(d, "out")
    anf = os.path.join(d, "A1.anf")
    shutil.copy(ANF, anf)
    created, meta = import_ecad_oracle(anf, proj.model, out_dir=out)
    assert len(created) >= 2
    assert meta["mode"] == 1
    assert meta["layers"] >= 2
    assert meta["shapes"] > 0
    assert len(list(proj.model._all_objects())) >= 2
