# -*- coding: utf-8 -*-
"""
P0: build QMenuBar / QToolBar / shortcuts from the golden spec.

Structure is 100% data-driven (docs/icepak_gui_golden.json).  Only the few
widgets that carry *state* in Icepak (Default shading radio group, Object
names group, Visible per-type checkboxes, Display checkboxes, Edit toolbars
checkbox menu, dynamic User views / Windows / Macros menus) keep dedicated
builders that live on IceGui (guarded by "special" entries).
"""
import re

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QMenu, QAction, QActionGroup

from ice_actions import (
    CommandRegistry, icon_for_command, resolve_slot, SLOT_MAP, STATE_ONLY,
)

# menu labels that are not command entries but dynamic/decorative menus
WHITELIST = {"User views", "Edit toolbars", "Message", "Project", "Macros"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _norm_key(key):
    """Normalize golden hotkey ('Control-f') to Qt text ('Ctrl+F')."""
    k = key.replace("Control", "Ctrl").replace("Question", "?").strip()
    k = k.replace("-", "+")
    return re.sub(r"\++", "+", k)


def _has_icon(gui):
    from ice_icons import IceIcons
    return IceIcons


def make_action(gui, text, parent, icon_key=None, shortcut=None,
                checkable=False, checked=False, slot=None):
    if slot is None and text in STATE_ONLY:
        checkable = True
    """Create a QAction resolved through the command registry."""
    a = QAction(text, gui)
    if icon_key:
        try:
            from ice_icons import IceIcons
            name = icon_for_command(icon_key)
            if name:
                a.setIcon(IceIcons.get(name, 24))
        except Exception:
            pass
    if shortcut:
        a.setShortcut(shortcut)
    if checkable:
        a.setCheckable(True)
        a.setChecked(checked)
    if slot is None:
        slot = resolve_slot(gui, text)
    if slot is None:
        # state-only toggle: remember display state, wire a no-op handler
        def _state(_=False, t=text):
            gui._display_state[t] = not gui._display_state.get(t, False)
        a.triggered.connect(_state)
    elif callable(slot):
        a.triggered.connect(slot)
    else:
        a.triggered.connect(lambda _=False, t=text: gui._nyi(t))
    parent.addAction(a)
    if hasattr(gui, "_created_by_command"):
        gui._created_by_command[text] = a
    return a


def _entries(entries):
    """Iterate spec entries yielding ('sep'|('cmd',label)|('cascade',label,sub))."""
    for e in entries:
        if not isinstance(e, dict):
            continue
        if "sep" in e:
            yield ("sep", None, None)
        elif "scalar" in e:
            s = e["scalar"]
            if isinstance(s, list):
                words = [w for w in s if isinstance(w, str)]
                yield ("cascade", words[0] if words else "", [])
            else:
                yield ("cmd", s, None)
        elif "descriptor" in e:
            words = [w for w in e.get("descriptor", []) if isinstance(w, str)]
            yield ("cascade", words[0] if words else "", e.get("cascade", []))
        elif "list" in e:
            # parser artifact: braced entries come back wrapped in {'list': [...]}
            for sub in _entries(e["list"]):
                yield sub


# --------------------------------------------------------------------------- #
# menu generation
# --------------------------------------------------------------------------- #

def build_menus(gui):
    reg = gui._registry
    mb = gui.menuBar()

    def build(parent, entries):
        for kind, label, sub in _entries(entries):
            if kind == "sep":
                parent.addSeparator()
                continue
            if kind == "cascade":
                if label == "Default shading":
                    m = parent.addMenu("Default shading")
                    gui._build_shading_menu(m)
                elif label == "Object names":
                    m = parent.addMenu("Object names")
                    gui._build_names_menu(m)
                elif label == "Visible":
                    m = parent.addMenu("Visible")
                    gui._build_visible_menu(m)
                elif label == "Edit toolbars":
                    m = parent.addMenu("Edit toolbars")
                    gui._tb_menu = m
                elif label == "User views" or "$visible_object_commands" in str(sub):
                    # dynamic submenu placeholders
                    if label == "User views":
                        gui._user_views_menu = parent.addMenu("User views")
                    else:
                        gui._build_visible_menu(parent)
                else:
                    m = parent.addMenu(label)
                    build(m, sub)
                continue
            # plain command
            if label in ("Edit toolbars",):
                m = parent.addMenu("Edit toolbars")
                gui._tb_menu = m
                continue
            if label == "Lights":
                make_action(gui, label, parent, icon_key=reg.icon_key(label))
                continue
            if isinstance(label, list):
                label = label[0] if label else ""
            if label.startswith("$"):
                continue
            make_action(gui, label, parent, icon_key=reg.icon_key(label))

    for menu_def in reg.menus():
        name = menu_def.get("name")
        if menu_def.get("dynamic"):
            continue
        m = mb.addMenu(name)
        gui._menus[name] = m
        build(m, menu_def.get("entries", []))

    # dynamic menus (golden placeholders, semantics from the plan)
    _build_dynamic_menus(gui)


def _build_dynamic_menus(gui):
    mb = gui.menuBar()
    # Macros: dynamic in Icepak -> documented skeleton (P7 wires live scan)
    if "Macros" not in gui._menus:
        m = mb.addMenu("Macros")
        gui._menus["Macros"] = m
        for t in ("ATX / Micro-ATX chassis", "Angled Fin Heat Sink", "PCB",
                  "Polygonal ducts", "Heat sink creation",
                  "Detailed heat sink creation", "Heat Pipe"):
            make_action(gui, t, m, icon_key=gui._registry.icon_key(t))
    # Windows: dynamic toplevel registry
    if "Windows" not in gui._menus:
        m = mb.addMenu("Windows")
        gui._menus["Windows"] = m
        gui._act_show_msg = make_action(
            gui, "Message", m, slot=gui._toggle_message,
            checkable=True, checked=True)
        gui._act_show_nav = make_action(
            gui, "Project", m, slot=gui._toggle_nav,
            checkable=True, checked=True)
    # Orient trailing dynamic "User views" submenu (Icepak adds it at runtime)
    orient = gui._menus.get("Orient")
    if orient is not None and not hasattr(gui, "_user_views_menu"):
        gui._user_views_menu = orient.addMenu("User views")


def apply_hotkeys(gui):
    """Window-level hotkeys from the golden spec (app-level only; tdv-level is
    handled by the 3D viewport in P3)."""
    reg = gui._registry
    for h in reg.hotkeys(kind="command_set_hotkeys"):
        if h.get("cmd") not in SLOT_MAP:
            continue
        created = gui._hotkey_actions.get(h["cmd"])
        if created is None:
            created = getattr(gui, "_created_by_command", {}).get(h["cmd"])
        if created is None:
            slot = resolve_slot(gui, h["cmd"])
            if slot is None:
                continue
            a = QAction(h["cmd"], gui)
            a.triggered.connect(slot)
            gui.addAction(a)
            gui._hotkey_actions[h["cmd"]] = a
            created = a
        created.setShortcut(_norm_key(h["key"]))
    # orient/viewport companions currently registered as plain shortcuts
    for text, sc, slot in (
        ("Edit object or postprocessing object", "Ctrl+E", None),
        ("Delete object", "Delete", None),
        ("Toggle object active", "Ctrl+A", None),
        ("Toggle object visible", "Ctrl+V", None),
        ("Open/close tree node", "Ctrl+T", None),
        ("Open/close model subtree", "Ctrl+M", None),
        ("Move object", "Ctrl+X", None),
        ("Copy object", "Ctrl+C", None),
        ("Toggle shading type", "Ctrl+W", None),
    ):
        a = gui._hotkey_actions.get(text)
        if a is not None and not a.shortcut():
            pass  # already set from golden
        elif a is None:
            a = make_action(gui, text, gui, shortcut=sc)
            gui._hotkey_actions[text] = a


# --------------------------------------------------------------------------- #
# toolbar generation
# --------------------------------------------------------------------------- #

def build_toolbars(gui):
    reg = gui._registry
    ROW_BY_NAME = {
        "File commands": 0, "Edit commands": 0, "Viewing options": 0,
        "Orientation commands": 0, "Model and solve": 1, "Postprocessing": 1,
    }
    groups = list(reg.toolbar_groups())
    groups.sort(key=lambda t: (ROW_BY_NAME.get(t["name"], 2),) if False else 0)
    # stable order: index in golden keeps canonical sequence within each row
    ordered = []
    for row in (0, 1, 2):
        for g in groups:
            if ROW_BY_NAME.get(g["name"], 2) == row:
                ordered.append(g)
    groups = ordered
    seq = 0
    for tb_def in groups:
        row = 0 if tb_def["row"] == "1" else 2
        name = tb_def["name"]
        tb = gui._tb(name, row)
        for kind, label, sub in _entries(tb_def["entries"]):
            if kind != "cmd":
                continue
            if not label or label.startswith("$"):
                continue
            icon_key = reg.icon_key(label)
            slot = None
            if label in ("Align and morph faces", "Align and morph edges",
                         "Align and morph vertices", "Align object centers",
                         "Align face centers", "Morph faces", "Morph edges"):
                slot = None
            gui._tb_act(tb, label, slot, icon=icon_for_command(icon_key))
        seq += 1
