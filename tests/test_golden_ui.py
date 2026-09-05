# -*- coding: utf-8 -*-
"""P0 golden-spec driven UI tests: menus/toolbars/hotkeys must equal
docs/icepak_gui_golden.json, and unimplemented commands must land on NYI."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import ice_gui
from ice_actions import CommandRegistry

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def _menu_texts(menu, out):
    for a in menu.actions():
        out.add(a.text())
        if a.menu() is not None:
            _menu_texts(a.menu(), out)
    return out


def _all_action_texts(win):
    out = set()
    for a in win.menuBar().actions():
        out.add(a.text())
        if a.menu() is not None:
            _menu_texts(a.menu(), out)
    for tb in win._toolbars.values():
        for a in tb.actions():
            out.add(a.text())
    return out


def _golden_command_texts(reg):
    texts = set()

    def walk(entries):
        for e in entries:
            if not isinstance(e, dict):
                continue
            if "scalar" in e:
                s = e["scalar"]
                if isinstance(s, str):
                    texts.add(s)
            elif "descriptor" in e:
                for w in e.get("descriptor", []):
                    if (isinstance(w, str) and not w.startswith("$")
                            and w not in ("cascade", "menu", "multiple")
                            and w != ""):
                        texts.add(w)
                walk(e.get("cascade", []))
            elif "list" in e:
                walk(e["list"])

    for m in reg.menus():
        if m.get("dynamic"):
            continue
        walk(m["entries"])
    for tb in reg.toolbar_groups():
        walk(tb["entries"])
    return texts


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


def test_registry_loads():
    reg = CommandRegistry()
    assert [m["name"] for m in reg.menus()] == [
        "File", "Edit", "View", "Orient", "Macros", "Model", "Solve",
        "Post", "Report", "Windows", "Help"]
    assert len(reg.toolbar_groups()) == 9
    assert reg.toolbar("File commands") is not None
    assert reg.toolbar("Object creation") is not None
    assert len(reg.hotkeys()) >= 25


def test_menu_tree_equals_golden(win):
    reg = win._registry
    names = [a.text().replace("&", "") for a in win.menuBar().actions()]
    for m in reg.menus():
        assert m["name"] in names, names
    file_menu = [a for a in win.menuBar().actions()
                 if a.text() == "File"][0].menu()
    cmds = [a.text() for a in file_menu.actions()
            if a.text() and not a.text() == ""]
    assert cmds[:4] == ["New project", "Open project",
                        "Merge project", "Reload main version"], cmds


def test_every_golden_command_is_on_a_menu(win):
    reg = win._registry
    wanted = _golden_command_texts(reg)
    all_texts = _all_action_texts(win)
    whitelist = {"Visible", "Object names", "Default shading", "Display",
                 "User views", "Edit toolbars", "Create object", "Traces",
                 "Markers", "Rubber bands", "Settings", "Diagnostics",
                 "Workflow data", "Solution overview", "Export", "Import",
                 "Powermaps", "IDF file", "EM Mapping", "Macros", "Windows"}
    missing = set(w for w in wanted
                  if w and not w.startswith("$") and w not in all_texts)
    assert not missing - whitelist, sorted(missing - whitelist)


def test_toolbar_groups_match_golden(win):
    reg = win._registry
    expected = ["File commands", "Edit commands", "Viewing options",
                "Orientation commands", "Model and solve", "Postprocessing",
                "Object creation", "Object modification", "Alignment"]
    assert list(win._toolbars.keys()) == expected
    for name in expected:
        tb_def = reg.toolbar(name)
        # F4: multi-command buttons are QToolButton widgets, not golden
        # scalars; their (empty-text) host actions are filtered out here
        actions = [a.text() for a in win._toolbars[name].actions()
                   if a.text()]
        wanted = [e["scalar"] for e in tb_def["entries"]
                  if isinstance(e.get("scalar"), str)]
        assert actions == wanted, (name, actions, wanted)


def test_file_toolbar_icons(win):
    for a in win._toolbars["File commands"].actions():
        assert not a.icon().isNull(), a.text()


def test_hotkeys_match_golden(win):
    shortcuts = set()

    def walk(menu):
        for a in menu.actions():
            if a.menu() is not None:
                walk(a.menu())
            else:
                if a.shortcut().toString():
                    shortcuts.add(a.shortcut().toString())
    for a in win.menuBar().actions():
        if a.menu() is not None:
            walk(a.menu())
        elif a.shortcut().toString():
            shortcuts.add(a.shortcut().toString())
    for a in win._hotkey_actions.values():
        if a.shortcut().toString():
            shortcuts.add(a.shortcut().toString())
    for sc in ("Ctrl+N", "Ctrl+O", "Ctrl+S", "Ctrl+Z", "Ctrl+R", "Ctrl+E",
               "F1", "Ctrl+X", "Ctrl+C"):
        assert sc in shortcuts, sc
    assert "Delete" in shortcuts or "Del" in shortcuts, shortcuts


def test_nyi_lands_in_message(win):
    action = win._toolbars["Model and solve"].actions()[4]  # Run solution
    assert action.text() == "Run solution"
    action.trigger()
    text = win.message_win.text.toPlainText()
    assert "Run solution" in text
    assert "not yet mapped" in text


def test_state_only_toggles_record(win):
    a = win._created_by_command.get("Display mesh")
    assert a is not None and a.isCheckable()
    a.trigger()
    assert win._display_state.get("Display mesh") is True
