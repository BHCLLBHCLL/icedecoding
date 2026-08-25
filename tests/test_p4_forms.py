# -*- coding: utf-8 -*-
"""P4 form engine / object editor / save tests."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_editors import ObjectEditDialog
from ice_forms import FormPage

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


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


def test_form_page_rows(qapp):
    page = FormPage()
    form = page.section("Test")
    r1 = page.add_row(form, "name", "Name", "text", "abc")
    r2 = page.add_row(form, "size", "Size", "spin", 3.5)
    r3 = page.add_row(form, "kind", "Kind", "combo", "b", options=["a", "b"])
    assert r1.get() == "abc"
    assert abs(r2.get() - 3.5) < 1e-9
    assert r3.get() == "b"
    page.load({"name": "xyz", "size": 9.0})
    assert page.row("name").get() == "xyz"
    assert abs(page.row("size").get() - 9.0) < 1e-9


def test_object_edit_dialog_applies(win):
    win._new_project()
    obj = win._create_object("block")
    dlg = ObjectEditDialog(win, obj=obj, project=win.project)
    dlg.tabs.widget(0).row("name").set("block_renamed")
    dlg.tabs.widget(1).row("block_type").set("fluid")
    dlg._apply()
    assert obj.name == "block_renamed"
    assert obj.setvals.get("block_type") == "fluid"
    assert win._dirty is True
    dlg.close()
    dlg.close()


def test_editor_geometry_writeback(win):
    win._new_project()
    obj = win._create_object("block")
    dlg = ObjectEditDialog(win, obj=obj, project=win.project)
    geo = dlg.tabs.widget(2)
    geo.row("p1.x").set(1.0)
    geo.row("p2.x").set(2.0)
    dlg._apply()
    assert obj.shape.setvals["point1"][0] == "1.0"
    assert obj.shape.setvals["point2"][0] == "2.0"
    dlg.close()


def test_geometry_window_dual_write(win):
    win._new_project()
    obj = win._create_object("block")
    win._on_object_selected(obj)
    win.geometry_win._rows["xS"].setText("0.11")
    win.geometry_win._apply_geo()
    assert float(obj.shape.setvals["point1"][0]) == pytest.approx(0.11, abs=1e-9)


def test_geometry_axis_align_orange(win):
    win._new_project()
    blk = win._create_object("block")
    win._on_object_selected(blk)
    win._geometry_axis_align("xS")
    cab = win.project.model.object_by_name("cabinet")
    cab_lo = float(cab.shape.setvals["point1"][0])
    assert float(blk.shape.setvals["point1"][0]) == pytest.approx(cab_lo, abs=1e-9)


def test_save_writes_model(win):
    import tempfile
    win._new_project()
    blk = win._create_object("block")
    blk.name = "saved.block"
    proj_dir = tempfile.mkdtemp(prefix="ice_save_")
    from icepak_parser import model_parser
    ok = win._save(os.path.join(proj_dir, "model"))
    assert ok is True
    raw = open(os.path.join(proj_dir, "model"), "r", encoding="latin-1").read()
    assert raw.startswith("Il!!") or "#@" in raw
    mf = model_parser.parse_file(os.path.join(proj_dir, "model"))
    names = [o.name for o in mf._all_objects()]
    assert "saved.block" in names
    assert win._dirty is False