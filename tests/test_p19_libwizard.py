# -*- coding: utf-8 -*-
"""Phase D2: per-part wizard pages for the macro-library (845-part) catalog."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_macros import scan_macro_library
from ice_macros_gui import macro_param_rows, LibraryMacroWizard

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


def test_macro_param_rows_infer_kinds():
    m = {'params': {'ball_num1': 12.0, 'ball_pitch': 1.0,
                    'wire_material': 'Au-Typical', 'xoff': 0.0}}
    rows = macro_param_rows(m)
    assert rows[0] == ('ball_num1', 'Ball Num 1', 'int', 12, None)
    assert rows[1] == ('ball_pitch', 'Ball Pitch', 'spin', 1.0, None)
    assert rows[2] == ('wire_material', 'Wire Material', 'text',
                       'Au-Typical', None)
    assert rows[3] == ('xoff', 'Xoff', 'spin', 0.0, None)


def test_library_wizard_pages_from_catalog(qapp):
    ms = scan_macro_library()
    assert len(ms) > 800
    part = ms[0]
    dlg = LibraryMacroWizard(macro=part, title=part['name'])
    # params + confirm pages, form populated from the real param file
    assert dlg.stack.count() == 2
    assert dlg.form.row('ball_num1') is not None
    assert dlg.form.row('package_thickness') is not None
    dlg.close()


def test_library_wizard_finish_creates_part(qapp, win):
    ms = scan_macro_library()
    part = ms[0]
    win._new_project()
    dlg = LibraryMacroWizard(win, macro=part, title=part['name'])
    dlg._finish()
    objs = list(win.project.model._all_objects())
    pkgs = [o for o in objs if o.kind == 'package']
    assert len(pkgs) == 1
    sv = pkgs[0].setvals or {}
    assert 'ball_pitch' in sv
    assert sv['ball_num1'][0] != ''
    assert win._dirty is True


def test_menu_includes_library_catalog(win):
    win._rebuild_macros_menu()
    m = win._menus['Macros']
    lib = None
    for a in m.actions():
        if a.text() == 'Library parts':
            lib = a.menu()
    assert lib is not None
    texts = [x.text() for x in lib.actions()]
    assert 'BGA_library' in texts
    assert 'FPBGA_library' in texts
    # recurse down to a leaf part action and confirm it routes to a wizard
    leaf = lib.actions()[0].menu().actions()[0].menu().actions()[0]
    assert leaf.text()
