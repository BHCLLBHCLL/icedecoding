# -*- coding: utf-8 -*-
"""P19-F1: Windows dynamic menu from the live toplevel registry."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

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


def _win_texts(win):
    m = win._menus["Windows"]
    return [a.text() for a in m.actions() if a.text()]


def test_windows_menu_from_registry(win):
    texts = _win_texts(win)
    for name in ("Message", "Project", "Graphics", "Geometry"):
        assert name in texts, texts
    m = win._menus["Windows"]
    assert all(a.isCheckable() for a in m.actions())


def test_register_toplevel_adds_entry(win):
    from PyQt5.QtWidgets import QWidget
    w = QWidget()
    w.setWindowTitle("Test window")
    win.register_toplevel("Test window", w)
    texts = _win_texts(win)
    assert "Test window" in texts
    # re-register with the same name must not duplicate
    win.register_toplevel("Test window", w)
    assert texts.count("Test window") == 1
    w.close()


def test_toggle_toplevel_visibility(win):
    from PyQt5.QtWidgets import QWidget
    w = QWidget()
    w.show()
    win.register_toplevel("Toggle me", w)
    m = win._menus["Windows"]
    act = [a for a in m.actions() if a.text() == "Toggle me"][0]
    assert act.isChecked() is True
    act.trigger()
    assert w.isVisible() is False
    assert act.isChecked() is False
    act.trigger()
    assert w.isVisible() is True
    w.close()


def test_plot_window_registered(win, monkeypatch):
    import tempfile
    win._new_project()
    d = tempfile.mkdtemp(prefix="win_")
    monkeypatch.setattr(win, "_job_base", lambda: d)
    pw = win._open_plot("History")
    texts = _win_texts(win)
    assert "Plot: History" in texts
    pw.close()
