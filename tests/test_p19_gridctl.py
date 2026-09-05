# -*- coding: utf-8 -*-
"""P19-G2: Edit priorities / Edit cutouts panels -> grid_params."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_actions import SLOT_MAP
from ice_create import default_object
from ice_mesh import write_grid_params
from icepak_parser.project import IcepakProject

import ice_gui
import ice_panes

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _objs():
    a = default_object("block", "blk.1")
    a.setvals = {"grid_priority": ["20"]}
    a.shape.setvals["point1"] = ["0", "0", "0"]
    a.shape.setvals["point2"] = ["0.1", "0.1", "0.1"]
    b = default_object("block", "blk.2")
    b.setvals = {"grid_cutout": ["1"]}
    b.shape.setvals["point1"] = ["0.2", "0", "0"]
    b.shape.setvals["point2"] = ["0.3", "0.1", "0.1"]
    return [a, b]


def test_slots():
    assert SLOT_MAP.get("Edit priorities") == "_edit_priorities"
    assert SLOT_MAP.get("Edit cutouts") == "_edit_cutouts"


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_priorities_dialog_values(qapp):
    dlg = ice_panes.EditPrioritiesDialog(parent=None, objects=_objs())
    dlg.table.item(0, 1).setText("77")
    vals = dlg.values()
    assert vals["blk.1"] == 77
    assert vals["blk.2"] == 10  # default when empty
    dlg.close()


def test_cutouts_dialog_values(qapp):
    from PyQt5.QtCore import Qt
    dlg = ice_panes.EditCutoutsDialog(parent=None, objects=_objs())
    # blk.2 preset to cutout=1; flip blk.1 on
    dlg._checks[0].setCheckState(Qt.Checked)
    vals = dlg.values()
    assert vals["blk.1"] == "1"
    assert vals["blk.2"] == "1"
    dlg.close()


def test_handlers_write_setvals(qapp, monkeypatch):
    win = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    try:
        win._new_project()
        win.project.model.objects.extend(_objs())

        class PrioDlg(object):
            def __init__(self, parent=None, objects=None):
                pass

            def exec_(self):
                return 1

            def values(self):
                return {"blk.1": 33, "blk.2": 44}

        class CutDlg(object):
            def __init__(self, parent=None, objects=None):
                pass

            def exec_(self):
                return 1

            def values(self):
                return {"blk.1": "1", "blk.2": "0"}

        monkeypatch.setattr(ice_panes, "EditPrioritiesDialog", PrioDlg)
        monkeypatch.setattr(ice_panes, "EditCutoutsDialog", CutDlg)
        win._edit_priorities()
        win._edit_cutouts()
        b1 = win.project.model.object_by_name("blk.1")
        b2 = win.project.model.object_by_name("blk.2")
        assert (b1.setvals["grid_priority"])[-1] == "33"
        assert (b1.setvals["grid_cutout"])[-1] == "1"
        assert (b2.setvals["grid_cutout"])[-1] == "0"
    finally:
        win.close()


def test_grid_params_include_priority_cutout():
    proj = IcepakProject.empty("gp")
    proj.model.objects.extend(_objs())
    d = tempfile.mkdtemp(prefix="gp_")
    path = os.path.join(d, "grid_params")
    write_grid_params(path, proj.model, {"grid_gcount_i": 10})
    lines = open(path, encoding="latin-1").read().splitlines()
    assert len(lines) == 2
    toks = lines[0].split()
    assert toks[-2] == "20"  # blk.1 priority
    assert toks[-1] == "0"   # blk.1 cutout
    assert lines[1].split()[-1] == "1"  # blk.2 cutout
