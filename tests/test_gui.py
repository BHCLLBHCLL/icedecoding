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


def test_new_project_has_cabinet(win):
    win._new_project()
    assert win.project is not None
    cab = win.project.model.object_by_name("cabinet")
    assert cab is not None
    assert cab.kind == "domain"
    assert win.project_tree.find_object_item("cabinet") is not None
    it = win.project_tree.find_object_item("cabinet")
    assert it.checkState(0) != 0  # checked


def test_create_and_delete_object(win):
    win._new_project()
    obj = win._create_object("block")
    assert obj.name == "block.1"
    assert win.project.model.object_by_name("block.1") is not None
    assert win.project_tree.find_object_item("block.1") is not None
    win.selected = "block.1"
    win._delete_current()
    assert win.project.model.object_by_name("block.1") is None
    assert win.project_tree.find_object_item("block.1") is None
    assert win.project.model.object_by_name("cabinet") is not None


def test_tree_checkbox_hides_object(win):
    from PyQt5.QtCore import Qt
    win._new_project()
    win._create_object("block")
    seen = []
    win.project_tree.visibility_changed.connect(
        lambda n, v: seen.append((n, v)))
    it = win.project_tree.find_object_item("block.1")
    it.setCheckState(0, Qt.Unchecked)
    assert "block.1" in win._hidden
    assert seen and seen[-1] == ("block.1", False)
    it.setCheckState(0, Qt.Checked)
    assert "block.1" not in win._hidden


def test_find_selects_object(win):
    win._new_project()
    win._create_object("fan")
    found = win._find_object("fan.1")
    assert found is not None
    assert found.name == "fan.1"
    assert win.selected == "fan.1"


def test_pack_new_project_roundtrip(win):
    import os
    import tempfile
    from icepak_parser.project import IcepakProject
    win._new_project()
    win._create_object("opening")
    with tempfile.TemporaryDirectory() as d:
        dest = os.path.join(d, "untitled.tzr")
        assert win.pack_to(dest) == dest
        loaded = IcepakProject.from_archive(dest)
        names = {o.name for o in loaded.model._all_objects()}
        assert "cabinet" in names
        assert "opening.1" in names


def test_user_views_save_write_read(win):
    import os
    import json
    import tempfile
    win._clear_user_views()
    win._save_user_view()
    assert len(win._user_views) == 1
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "views.json")
        win._write_user_views(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["name"] == "view.1"
        win._clear_user_views()
        assert win._user_views == []
        win._read_user_views(path)
        assert win._user_views[0]["name"] == "view.1"


def test_undo_redo_create(win):
    win._new_project()
    win._create_object("block")
    assert win.project.model.object_by_name("block.1") is not None
    win._undo()
    assert win.project.model.object_by_name("block.1") is None
    win._redo()
    assert win.project.model.object_by_name("block.1") is not None


def test_move_copy_and_trash(win):
    win._new_project()
    blk = win._create_object("block")
    p1 = [float(x) for x in blk.shape.setvals["point1"]]
    win.selected = "block.1"
    win._move_current(0.1, 0, 0)
    p1b = [float(x) for x in
           win.project.model.object_by_name("block.1").shape.setvals["point1"]]
    assert abs(p1b[0] - p1[0] - 0.1) < 1e-6
    copy = win._copy_current(0, 0.05, 0)
    assert copy.name == "block.2"
    assert win.project.model.object_by_name("block.2") is not None
    win.selected = "block.1"
    win._delete_current()
    assert win.project.model.object_by_name("block.1") is None
    assert any(o.name == "block.1" for o in win._trash)
    win.restore_from_trash("block.1")
    assert win.project.model.object_by_name("block.1") is not None
    assert not any(o.name == "block.1" for o in win._trash)


def test_inactive_and_groups(win):
    win._new_project()
    win._create_object("fan")
    win.selected = "fan.1"
    win._toggle_selected_active()
    assert "fan.1" in win._inactive
    assert win.project_tree.find_object_item("fan.1") is not None
    root = win.project_tree.topLevelItem(0)
    labels = [root.child(i).text(0) for i in range(root.childCount())]
    assert any(t.startswith("Inactive") for t in labels)
    win.selected = "fan.1"
    win._toggle_selected_active()
    assert "fan.1" not in win._inactive
    win.create_group("hot", ["fan.1"])
    assert win._groups["hot"] == ["fan.1"]
    g = win.project_tree._items["Groups"]
    assert g.childCount() == 1


def test_four_viewing_windows(win):
    win._set_view_panes(4)
    assert win._view_panes == 4
    assert win._view_stack.currentIndex() == 1
    win._set_view_panes(1)
    assert win._view_panes == 1
    assert win._view_stack.currentIndex() == 0


def test_problem_solution_and_post_nodes(win):
    from icepak_parser.problem_parser import ProblemFile
    from icepak_parser.project import IcepakProject, format_post_objects, parse_post_objects
    win._new_project()
    prb = ProblemFile()
    prb.setters = {
        "title": "demo job",
        "niterations": "100",
        "radiation": "off",
        "nproc": "4",
    }
    win.project.problem = prb
    win.project.post = parse_post_objects(
        "post_load_object {plane_cut -name cut.1 -x 0}")
    win._refresh()
    post = win.project_tree._items["Post-processing"]
    assert post.childCount() == 1
    assert "cut.1" in post.child(0).text(0)
    sol = win.project_tree._items["Solution settings"]
    found = [sol.child(i).text(0) for i in range(sol.childCount())]
    assert any("Basic settings" in t for t in found)
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "post_objects")
        assert win._save_post_objects(path) == path
        win.project.post = []
        win._load_post_objects(path)
        assert win.project.post and win.project.post[0]["type"] == "plane_cut"
    text = format_post_objects(win.project.post)
    assert "post_load_object" in text


def test_library_scan(win, tmp_path=None):
    import os, tempfile
    from ice_panes import LibraryTree
    with tempfile.TemporaryDirectory() as d:
        os.mkdir(os.path.join(d, "browsers"))
        open(os.path.join(d, "browsers", "fan.tcl"), "w").close()
        open(os.path.join(d, "materials"), "w").close()
        assert win.library_tree.populate_from_path(d)
        root = win.library_tree.topLevelItem(0)
        kids = [root.child(i).text(0) for i in range(root.childCount())]
        assert "browsers" in kids
        assert "materials" in kids

