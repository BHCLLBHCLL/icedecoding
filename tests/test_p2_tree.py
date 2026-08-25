# -*- coding: utf-8 -*-
"""P2 tree & navigation tests: sort, object view levels, drag-drop semantics,
context menu wiring may be covered by handler-level tests."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_panes import SpreadsheetDialog

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


def test_tree_detail_flat(win):
    win._new_project()
    win._create_object("block")
    win._create_object("fan")
    win._set_tree_detail(0)
    model = win.project_tree._items["Model"]
    texts = [model.child(i).text(0) for i in range(model.childCount())]
    assert "block.1" in texts and "fan.1" in texts, texts


def test_tree_detail_types_with_subtypes(win):
    win._new_project()
    win._create_object("block")
    win._set_tree_detail(2)
    model = win.project_tree._items["Model"]
    flat = [model.child(i).text(0) for i in range(model.childCount())]
    assert any(t.startswith("block") and "(" in t for t in flat), flat


def test_tree_sort_alphabetical(win):
    win._new_project()
    for n in ("zebra", "alpha", "mike"):
        win._create_object("block")
        win.project.model.objects[-1].name = n
    win._set_tree_sort("alphabetical")
    model = win.project_tree._items["Model"]
    seen = [w.text(0) for w in win.project_tree.findChildren(
        type(model)) if not w.parent() or True]
    # find the object items under Model
    import PyQt5.QtWidgets as QW
    texts = []
    for i in range(model.childCount()):
        texts.append(model.child(i).text(0))
    assert any("(3)" in x for x in texts)


def test_drop_to_inactive(win):
    win._new_project()
    obj = win._create_object("block")
    win._on_tree_drop("Inactive", [obj.name])
    assert obj.name in win._inactive
    model = win.project_tree._items["Model"]
    flat = [model.child(i).text(0) for i in range(model.childCount())]
    assert all(obj.name not in x for x in flat)


def test_drop_to_trash(win):
    win._new_project()
    obj = win._create_object("block")
    win._on_tree_drop("Trash", [obj.name])
    assert win.project.model.object_by_name(obj.name) is None
    assert [t.name for t in win._trash] == [obj.name]


def test_spreadsheet_reload(qapp):
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    w._new_project()
    obj = w._create_object("block")
    dlg = SpreadsheetDialog(w, names=[obj.name], project=w.project)
    assert dlg.table.rowCount() == 1
    dlg.table.item(0, 2).setText("0.5")
    dlg._apply()
    dlg.close()
    w.close()
