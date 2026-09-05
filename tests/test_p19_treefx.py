# -*- coding: utf-8 -*-
"""P19-F3: tree right-click full set + group ops + clipboard + library search."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_create import default_object

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


def _with_block(win):
    win._new_project()
    blk = default_object("block", "blk.1")
    blk.setvals = {"material": ["Cu"], "power": ["2.0"]}
    win.project.model.objects.append(blk)
    return blk


def test_group_delete_all_removes_members(win):
    blk = _with_block(win)
    win.create_group("g1", ["blk.1"])
    win._delete_group("g1", delete_all=True)
    assert "g1" not in win._groups
    assert "blk.1" in win._trash
    assert win.project.model.object_by_name("blk.1") is None


def test_group_delete_group_only(win):
    _with_block(win)
    win.create_group("g1", ["blk.1"])
    win._delete_group("g1")
    assert "g1" not in win._groups
    assert win.project.model.object_by_name("blk.1") is not None


def test_copy_group_params_to_clipboard(win):
    from PyQt5.QtWidgets import QApplication
    _with_block(win)
    win.create_group("g1", ["blk.1"])
    win._copy_group_params("g1")
    text = QApplication.clipboard().text()
    assert "blk.1" in text and "material" in text


def test_show_clear_clipboard(win):
    from PyQt5.QtWidgets import QApplication
    QApplication.clipboard().setText("hello")
    win._show_clipboard()   # must not raise
    win._clear_clipboard()
    assert QApplication.clipboard().text() == ""


def test_search_library(win, monkeypatch):
    from PyQt5.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("BGA", True)))
    win._search_library()   # must not raise (may be 0 hits)


def test_tree_hotkeys_bound(win):
    for cmd in ("Toggle object active", "Toggle object visible",
                "Open/close tree node", "Open/close model subtree",
                "Toggle shading type"):
        assert cmd in win._hotkey_actions, cmd
