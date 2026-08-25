# -*- coding: utf-8 -*-
"""P1 shell parity tests: project title bar, geometry window, New panel,
Edit toolbars dialog."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_panes import NewProjectDialog, GeometryWindow, EditToolbarsDialog

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


def test_title_bar(win):
    win._new_project("demo")
    assert "demo" in win._title_bar.text()
    assert win._title_bar.text().startswith("Project:")


def test_geometry_window_present(win):
    assert isinstance(win.geometry_win, GeometryWindow)
    assert win.geometry_win.txt_name is not None


def test_geometry_window_updates_on_selection(win):
    win._new_project()
    obj = win._create_object("block")
    win._on_object_selected(obj)
    assert win.geometry_win.txt_name.text() == obj.name
    assert win.geometry_win.txt_shape.text() != ""


def test_new_project_dialog_rejects_chinese(qapp):
    dlg = NewProjectDialog()
    dlg.txt_name.setText(u"中文project")
    assert dlg.btn_create.isEnabled() is False
    dlg.txt_name.setText("valid_name")
    assert dlg.btn_create.isEnabled() is True
    dlg.close()


def test_edit_toolbars_dialog_toggles(qapp):
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    w._toolbars["File commands"].hide()
    dlg = EditToolbarsDialog(w)
    for chk, name, tb in dlg._checks:
        if name == "File commands":
            assert chk.isChecked() is False
            chk.setChecked(True)
            assert tb.isHidden() is False
    dlg.close()
    w.close()
