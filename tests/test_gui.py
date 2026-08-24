# -*- coding: utf-8 -*-
"""Headless GUI regression tests for the Icepak-aligned ice_gui."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_gui import IceGui
from ice_panes import PROJECT_NODES, WelcomeDialog
from icepak_parser.model_parser import ModelFile, ModelObject, Shape

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

MENUS = [
    "File", "Edit", "View", "Orient", "Macros", "Model",
    "Solve", "Post", "Report", "Windows", "Help",
]

TOOLBARS = [
    "File commands", "Edit commands", "Viewing options",
    "Orientation commands", "Model and solve", "Postprocessing",
    "Object creation", "Object modification", "Alignment",
]


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp):
    w = IceGui(enable_3d=False, show_welcome=False)
    yield w
    w.close()


def test_build_ui_headless(win):
    names = [a.text().replace("&", "") for a in win.menuBar().actions()]
    for m in MENUS:
        assert m in names, names
    assert len([n for n in names if n in MENUS]) == 11


def test_welcome_buttons(qapp):
    dlg = WelcomeDialog()
    labels = [b.text() for b in dlg.findChildren(
        __import__("PyQt5.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
    dlg.close()
    for name in ("Existing", "New", "Unpack", "Quit"):
        assert name in labels


def test_layout_panes(win):
    assert win.nav_tabs.tabText(0) == "Project"
    assert win.nav_tabs.tabText(1) == "Library"
    assert win.message_win.chk_verbose.text() == "Verbose"
    assert win.message_win.chk_log.text() == "Log"
    assert win.message_win.btn_save.text() == "Save"
    assert win.graphics is not None
    assert win.tdv_strip.mode() == "pick"


def test_project_tree_nodes(win):
    root = win.project_tree.topLevelItem(0)
    assert root is not None
    found = [root.child(i).text(0) for i in range(root.childCount())]
    assert found == list(PROJECT_NODES)


def test_toolbar_groups(win):
    for name in TOOLBARS:
        assert name in win._toolbars, name
        assert not win._toolbars[name].isHidden()


def test_nyi_logs(win):
    win._nyi("Run solution")
    text = win.message_win.text.toPlainText()
    assert "Run solution" in text
    assert "not yet mapped" in text
    assert "WARN" in text


def test_populate_model_tree(win):
    shape = Shape("s1", "shape_hexa", {
        "point1": ["0", "0", "0"], "point2": ["1", "1", "1"],
    })
    cab = ModelObject("domain", "cabinet", {}, shape)
    blk = ModelObject("block", "block.1", {}, shape)

    class Fake(object):
        name = "demo"
        model = ModelFile()
        problem = None
        post = []

    fake = Fake()
    fake.model.objects = [cab, blk]
    win.project_tree.populate(fake)
    assert win.project_tree.find_object_item("block.1") is not None
    assert win.project_tree.find_object_item("cabinet") is not None
    root = win.project_tree.topLevelItem(0)
    assert root.text(0) == "demo"


def test_shading_cycle(win):
    from ice_gui import SHADING_MODES
    start = win._shading
    win._cycle_shading()
    assert win._shading in SHADING_MODES
    assert win._shading != start
    for mode in SHADING_MODES:
        win._set_shading(mode)
        assert win._shading == mode
