# -*- coding: utf-8 -*-
"""P19-F2: File menu Workbench variant (golden note menus_icepak.tcl L170-211)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_actions import SLOT_MAP
import ice_menus_toolbars as MT

import ice_gui

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


def _file_actions(win):
    m = win._menus["File"]
    return m, [a.text() for a in m.actions() if a.text()]


def test_wb_slots():
    assert SLOT_MAP.get("Refresh Input Data") == "_refresh_input_data"
    assert SLOT_MAP.get("Close Icepak") == "_close_icepak"


def test_standalone_file_menu_default(win):
    m, texts = _file_actions(win)
    assert texts[:2] == ["New project", "Open project"]
    assert "Quit" in texts
    assert "Refresh Input Data" not in texts


def test_wb_file_variant(win):
    win._workbench = True
    MT.build_file_variant(win, wb=True)
    m, texts = _file_actions(win)
    assert texts[0] == "Refresh Input Data"
    for gone in ("New project", "Open project", "Save project as",
                 "Unpack project", "Quit"):
        assert gone not in texts, gone
    assert "Close Icepak" in texts
    # Import / Export cascades lose the JEDEC entries
    imp = [a.menu() for a in m.actions() if a.text() == "Import"][0]
    exp = [a.menu() for a in m.actions() if a.text() == "Export"][0]
    imp_texts = [a.text() for a in imp.actions()]
    exp_texts = [a.text() for a in exp.actions()]
    assert "Import JEDEC PTD/JEP30 file" not in imp_texts
    assert "Export JEDEC PTD/JEP30 file" not in exp_texts


def test_wb_env_flag_constructs_variant(qapp, monkeypatch):
    monkeypatch.setenv("ICE_WORKBENCH", "1")
    w = ice_gui.IceGui(enable_3d=False, show_welcome=False)
    try:
        assert w._workbench is True
        m, texts = _file_actions(w)
        assert texts[0] == "Refresh Input Data"
        assert "Close Icepak" in texts
    finally:
        w.close()
