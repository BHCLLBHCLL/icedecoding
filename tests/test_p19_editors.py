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
