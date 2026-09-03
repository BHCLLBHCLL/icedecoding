# -*- coding: utf-8 -*-
"""P19-D6: remaining ECAD exports - AEdt script + 5 powermap formats."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_ecad import parse_powermap, export_powermap, export_aedt
from ice_actions import resolve_slot, SLOT_MAP
from icepak_parser.project import IcepakProject
from ice_create import default_cabinet

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

ROWS = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (-1.5, 9.25, 7.5)]
FMTS = ["tab", "i2p", "ctm", "sentinel", "apache"]


def test_export_powermap_roundtrip():
    for fmt in FMTS:
        d = tempfile.mkdtemp(prefix="pm_")
        p = os.path.join(d, "p.%s" % fmt)
        export_powermap(p, ROWS, fmt)
        got = parse_powermap(p, fmt)
        assert got == ROWS, (fmt, got)


def test_export_slots_resolve():
    assert SLOT_MAP.get("ANSYS Electronics Desktop script") == "_export_aedt"
    for label, fmt in (("Gradient Firebolt p2i file", "i2p"),
                       ("Cadence TPKG file", "ctm"),
                       ("SIwave temp data", "tab"),
                       ("Sentinel TI HTC file", "sentinel"),
                       ("RedHawk Back Annotation", "apache")):
        assert SLOT_MAP.get(label) == "_export_powermap:%s" % fmt


def test_export_aedt_script_contents():
    proj = IcepakProject.empty("aedt")
    proj.model.objects.append(default_cabinet())
    d = tempfile.mkdtemp(prefix="aedt_")
    p = os.path.join(d, "s.py")
    export_aedt(p, proj.model)
    s = open(p, encoding="utf-8").read()
    assert "pyaedt" in s and "create_box" in s


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp):
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    yield w
    w.close()


def test_gui_export_powermap_writes(win, monkeypatch):
    from PyQt5 import QtWidgets
    win._new_project()
    win._powermaps = [{"fmt": "i2p", "rows": list(ROWS)}]
    d = tempfile.mkdtemp(prefix="pm_")
    target = os.path.join(d, "p.i2p")
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (target, "")))
    win._export_powermap("i2p")
    assert os.path.exists(target)
    assert parse_powermap(target, "i2p") == ROWS


def test_gui_export_powermap_no_data_warns(win):
    win._new_project()
    win._powermaps = None
    win._export_powermap("i2p")  # must not raise
    assert True
