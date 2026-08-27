# -*- coding: utf-8 -*-
"""P7 macros tests: registry, scanner, builders, wizard, menu rebuild."""
import json
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_macros import (
    BUILTIN_MACROS, scan_macro_dir, scan_macros, build_macro,
    default_user_macro_dir, default_project_macro_dir,
)
from ice_macros_gui import MacroWizard

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


def test_builtin_registry_has_packages():
    keys = set(BUILTIN_MACROS.keys())
    assert {"angled_fin", "bga", "tec", "sot", "blower"} <= keys
    assert BUILTIN_MACROS["angled_fin"]["subtype"] == "Heat sinks"
    assert BUILTIN_MACROS["bga"]["builder"] == "build_bga"


def test_scan_macro_dir():
    d = tempfile.mkdtemp(prefix="ice_mac_")
    desc = {"name": "my_hs", "subtype": "Heat sinks",
            "subsubtype": "Custom",
            "params": [("width", "W", "spin", 0.1)],
            "builder": "build_heat_sink"}
    with open(os.path.join(d, "my_hs.macro.json"), "w",
              encoding="utf-8") as fh:
        json.dump(desc, fh)
    found = scan_macro_dir(d)
    assert len(found) == 1
    assert found[0]["name"] == "my_hs"
    assert found[0]["builder"] == "build_heat_sink"


def test_scan_layers_override():
    d1 = tempfile.mkdtemp(prefix="ice_mu_")
    d2 = tempfile.mkdtemp(prefix="ice_ms_")
    for d, val in ((d1, "user"), (d2, "sys")):
        with open(os.path.join(d, "same.macro.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"name": "same", "subtype": val}, fh)
    merged = scan_macros(system_dir=d2, user_dir=d1)
    assert merged["same"]["subtype"] == "user"  # user overrides system


def test_build_heat_sink_creates_fins(win):
    win._new_project()
    created = build_macro(win.project.model, "angled_fin",
                          {"width": 0.1, "depth": 0.1, "height": 0.05,
                           "base_thickness": 0.005, "fin_gap": 0.004,
                           "fin_thickness": 0.001, "fin_count": 6})
    assert len(created) == 7  # base + 6 fins
    names = [o.name for o in created]
    assert any(".base" in n for n in names)
    assert sum(1 for n in names if ".fin" in n) == 6


def test_build_bga_balls(win):
    win._new_project()
    created = build_macro(win.project.model, "bga",
                          {"body_size": 0.027, "body_thickness": 0.0012,
                           "die_size": 0.006, "ball_count": 3,
                           "ball_pitch": 0.0012})
    assert sum(1 for o in created if "ball" in o.name) == 9


def test_build_tec_pellets(win):
    win._new_project()
    created = build_macro(win.project.model, "tec", {"pellets": 5,
                                                     "power": 12.0})
    assert sum(1 for o in created if "pel" in o.name) == 5


def test_wizard_pages(qapp):
    params = BUILTIN_MACROS["angled_fin"]["params"]
    dlg = MacroWizard(title="test", params=params)
    assert dlg.stack.count() == 2
    assert dlg.nav.topLevelItemCount() >= 1
    dlg.close()


def test_menu_rebuild_groups(win):
    win._rebuild_macros_menu()
    m = win._menus["Macros"]
    texts = []
    for a in m.actions():
        texts.append(a.text())
        if a.menu() is not None:
            texts.extend([x.text() for x in a.menu().actions()])
    assert any("Heat sinks" in t for t in texts)
    assert any("BGA package" in t for t in texts)


def test_run_builtin_macro(win):
    win._new_project()
    win._run_builtin_macro("angled_fin",
                           {"width": 0.05, "depth": 0.05, "height": 0.02,
                            "base_thickness": 0.003, "fin_gap": 0.003,
                            "fin_thickness": 0.001, "fin_count": 4})
    names = [o.name for o in win.project.model._all_objects()]
    assert any(".base" in n for n in names)
    assert win._dirty is True


def test_default_dirs():
    import os as _os
    assert default_user_macro_dir().replace(_os.sep, "/").endswith(
        "icepak_lib/macros")
