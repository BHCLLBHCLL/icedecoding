# -*- coding: utf-8 -*-
"""P9 prefs / i18n / annotations tests."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_i18n import tr, set_language, ZH
from ice_prefs import PrefsStore, PREFS_SPEC, DEFAULTS, config_path
from ice_prefs_gui import PreferencesDialog, AnnotationsDialog

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")

LEGACY = """set background_style solid
set background_color1 "#000000"
set snap_attributes 200
set unit_length mm
"""


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


def test_defaults_table():
    assert len(PREFS_SPEC) == 7
    assert DEFAULTS["snap_attributes"] == 100
    assert DEFAULTS["new_object_size_factor"] == 0.2
    assert DEFAULTS["background_style"] == "gradient"


def test_tr_zh():
    set_language("zh")
    assert tr("File") == "文件"
    assert tr("Run solution") == "运行求解"
    assert tr("UnknownKey") == "UnknownKey"
    set_language("en")
    assert tr("File") == "File"


def test_store_roundtrip(monkeypatch):
    d = tempfile.mkdtemp(prefix="ice_pref_")
    pth = os.path.join(d, "prefs.json")
    s = PrefsStore()
    s.set("background_style", "solid")
    s.save(pth)
    s2 = PrefsStore()
    assert s2.load(pth) is True
    assert s2.get("background_style") == "solid"


def test_store_legacy_compat(monkeypatch):
    d = tempfile.mkdtemp(prefix="ice_leg_")
    pth = os.path.join(d, ".icepak_config")
    with open(pth, "w", encoding="latin-1") as fh:
        fh.write(LEGACY)
    s = PrefsStore()
    # a key not in spec still parses; spec keys get coerced values
    assert s.load_legacy(pth) is True
    assert s.get("snap_attributes") == 200
    assert s.get("background_style") == "solid"
    out = os.path.join(d, "out.cfg")
    s.save_legacy(out)
    txt = open(out, encoding="latin-1").read()
    assert txt.startswith("set ")
    assert "set background_style" in txt


def test_preferences_dialog_apply(qapp, win):
    dlg = PreferencesDialog(win, store=win._prefs)
    dlg._pages["Interaction"].row("motion_y").set(False)
    dlg._apply()
    assert win._prefs.get("motion_y") is False
    assert win._motion_axes[1] is False
    dlg.close()


def test_apply_prefs_background(win):
    win._apply_prefs(win._prefs)
    assert win._bg_style in ("gradient", "solid")
    assert win._mouse_map is not None


def test_annotations_dialog(qapp, win):
    dlg = AnnotationsDialog(win)
    dlg.page.row("show_date").set(True)
    dlg._ok()
    assert win._display_state.get("Display current date") is True


def test_startup_banner(win):
    text = win.message_win.text.toPlainText()
    assert "64-bit" in text
    assert "Copyright" in text
    assert "ANSYS Icepak" in text
