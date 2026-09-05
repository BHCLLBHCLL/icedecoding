# -*- coding: utf-8 -*-
"""P19-H3: command-prompt full dispatch + Python console equivalence."""
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


def test_dispatch_golden_command(win, monkeypatch):
    calls = []
    monkeypatch.setattr(win, "_fit", lambda: calls.append("fit"))
    res = win._dispatch_command_text("Scale to fit")
    assert calls == ["fit"]
    assert res.startswith("ran: Scale to fit")


def test_dispatch_unknown_falls_to_python(win):
    res = win._dispatch_command_text("no_such_command_xyz")
    assert res.startswith("ERR:")


def test_python_console_eval(win):
    assert win._dispatch_command_text("1 + 1") == "2"
    assert win._dispatch_command_text("self.selected") == "None"


def test_python_console_exec(win):
    assert win._dispatch_command_text("x = 5") == "OK"
    assert win._dispatch_command_text("x + 1") == "6"
