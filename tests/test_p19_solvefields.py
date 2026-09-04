# -*- coding: utf-8 -*-
"""P19-4: Solve panel full field sets - Patch / trials / ROM."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_solve import PATCH_FIELDS, TRIALS_FIELDS, ROM_FIELDS
from ice_actions import SLOT_MAP
import ice_solve_gui

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def test_field_tables_defined():
    keys = lambda fields: [f[0] for f in fields]
    assert "patch_object" in keys(PATCH_FIELDS)
    assert "patch_temp" in keys(PATCH_FIELDS)
    assert "solve_do_trials" in keys(TRIALS_FIELDS)
    assert "solve_trial_prefix" in keys(TRIALS_FIELDS)
    assert "ss_krylov" in keys(ROM_FIELDS)
    assert "krylov_cons_order" in keys(ROM_FIELDS)
    assert "krylov_trans_id" in keys(ROM_FIELDS)


def test_slots_resolve():
    assert SLOT_MAP.get("Define trials") == "_define_trials"
    assert SLOT_MAP.get("Create Krylov ROM") == "_create_krylov_rom"
    assert SLOT_MAP.get("Patch temperatures") == "_patch_temperatures"


def test_solve_dialog_kinds():
    assert "Define trials" in ice_solve_gui.SolveSettingsDialog.KINDS
    assert "Create Krylov ROM" in ice_solve_gui.SolveSettingsDialog.KINDS


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


class _Problem(object):
    setters = {}


def _with_problem(win):
    win._new_project()
    win.project.problem = _Problem()


def test_gui_define_trials_opens_dialog(win, monkeypatch):
    _with_problem(win)
    opened = []

    class FakeDlg(object):
        def __init__(self, parent=None, kind=None, problem=None, title=None):
            opened.append((kind, title))

        def exec_(self):
            return 1

    monkeypatch.setattr(ice_solve_gui, "SolveSettingsDialog", FakeDlg)
    win._define_trials()
    assert opened == [("Define trials", "Define trials")]


def test_gui_create_krylov_rom_opens_dialog(win, monkeypatch):
    _with_problem(win)
    opened = []

    class FakeDlg(object):
        def __init__(self, parent=None, kind=None, problem=None, title=None):
            opened.append(kind)

        def exec_(self):
            return 1

    monkeypatch.setattr(ice_solve_gui, "SolveSettingsDialog", FakeDlg)
    win._create_krylov_rom()
    assert opened == ["Create Krylov ROM"]


def test_gui_define_trials_no_problem_nyi(win, monkeypatch):
    win.project = None
    calls = []
    monkeypatch.setattr(win, "_nyi", lambda t: calls.append(t))
    win._define_trials()
    win._create_krylov_rom()
    assert calls == ["Define trials", "Create Krylov ROM"]
