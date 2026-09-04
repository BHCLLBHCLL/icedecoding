# -*- coding: utf-8 -*-
"""P19-4: Solve -> Transient settings command wiring."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_actions import SLOT_MAP
from ice_panes import SOLUTION_TRANSIENT_KEYS

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def test_transient_settings_slot():
    assert SLOT_MAP.get("Transient settings") == "_show_transient_settings"


def test_solution_transient_keys():
    assert "time_step" in SOLUTION_TRANSIENT_KEYS
    assert "n_time_steps" in SOLUTION_TRANSIENT_KEYS
    assert "end_time" in SOLUTION_TRANSIENT_KEYS
    assert "problem_time" in SOLUTION_TRANSIENT_KEYS


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


def test_gui_show_transient_settings(win, monkeypatch):
    calls = []
    def rec(title, keys):
        calls.append((title, keys))
    monkeypatch.setattr(win, "_show_problem_keys", rec)
    win._show_transient_settings()
    assert calls == [("Transient settings", SOLUTION_TRANSIENT_KEYS)]
