# -*- coding: utf-8 -*-
"""P19-3: per-class editor field sets (golden keys from decoded projects)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_editors as E
from ice_editors import GOLDEN_KEYS, spec_for, spec_has, ObjectEditDialog
from ice_create import default_object

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def test_spec_covers_golden_keys():
    for kind, keys in GOLDEN_KEYS.items():
        for k in keys:
            assert spec_has(k, kind), (kind, k)


def test_golden_keys_persist_in_common():
    for kind, keys in GOLDEN_KEYS.items():
        for k in keys:
            assert k in E.COMMON_SETVAL_KEYS, (kind, k)


def test_golden_keys_spot_checks():
    assert spec_has("res_rjc", "block")
    assert spec_has("thermal_heat_tr", "wall")
    assert spec_has("kneff", "pcb")
    assert spec_has("ball_diam", "package")
    assert spec_has("case_thickness", "fan")
    assert spec_has("solid_conductivity_x", "material")


def _kind_in(kind, key):
    for item in E.spec_for(kind):
        if item[0] == key:
            return item[2]
    return None


def test_numeric_keys_are_spin_not_text():
    assert _kind_in("block", "res_rjc") == "spin"
    assert _kind_in("block", "power") == "spin"
    assert _kind_in("block", "temp") == "spin"
    assert _kind_in("block", "solid_material") == "text"
    assert _kind_in("package", "via_num") == "int"
    assert _kind_in("package", "ball_diam") == "spin"
    assert _kind_in("wall", "thermal_heat_tr_on") == "check"
    assert _kind_in("pcb", "kneff") == "spin"
    assert _kind_in("fan", "case_thickness") == "spin"
    assert E.kind_of("cres_heat_tr_on") == "check"
    assert E.kind_of("dir_spec") == "text"


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_editor_dialog_shows_golden_rows(qapp):
    blk = default_object("block", "blk.1")
    dlg = ObjectEditDialog(parent=None, obj=blk, project=None)
    prop = dlg.tabs.widget(1)  # Properties tab
    keys = [r.key for r in prop._rows]
    assert "block_type" in keys
    assert "solid_material" in keys
    assert "res_rjc" in keys
    dlg.close()


def test_editor_dialog_unknown_kind_placeholder(qapp):
    o = default_object("block", "blk.1")
    o.kind = "mystery"
    dlg = ObjectEditDialog(parent=None, obj=o, project=None)
    prop = dlg.tabs.widget(1)
    keys = [r.key for r in prop._rows]
    assert "info" in keys  # read-only placeholder for unknown kinds
    dlg.close()


def test_spreadsheet_multi_body_edit(qapp):
    from ice_panes import SpreadsheetDialog
    from icepak_parser.project import IcepakProject
    proj = IcepakProject.empty("ss")
    blk = default_object("block", "blk.1")
    blk.setvals = {"power": ["2.0"], "material": ["Cu"]}
    blk2 = default_object("block", "blk.2")
    blk2.setvals = {"power": ["3.0"]}
    proj.model.objects.append(blk)
    proj.model.objects.append(blk2)
    dlg = SpreadsheetDialog(parent=None, names=["blk.1", "blk.2"],
                            project=proj)
    assert dlg.table.rowCount() == 2
    headers = [dlg.table.horizontalHeaderItem(c).text()
               for c in range(dlg.table.columnCount())]
    assert "Name" in headers and "Kind" in headers
    assert "power" in headers and "material" in headers
    pcol = headers.index("power")
    dlg.table.item(0, pcol).setText("9.5")
    dlg._apply()
    assert blk.setvals["power"] == "9.5"
    dlg.close()


def test_geometry_window_orange_axis_buttons(qapp):
    from PyQt5.QtWidgets import QPushButton
    from ice_panes import GeometryWindow
    w = GeometryWindow()
    btns = [b for b in w.findChildren(QPushButton)
            if b.text() in ("xS", "yS", "zS", "xE", "yE", "zE")]
    assert len(btns) == 6
    for b in btns:
        assert "#f3a53a" in b.styleSheet()  # orange button family
    blk = default_object("block", "blk.1")
    blk.shape.setvals["point1"] = ["0.1", "0.2", "0.3"]
    blk.shape.setvals["point2"] = ["0.4", "0.5", "0.6"]
    w.set_object(blk)
    assert w.txt_name.text() == "blk.1"
    assert w._rows["xS"].text() == "0.1"
    assert w._rows["zE"].text() == "0.6"
    w.close()
