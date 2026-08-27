# -*- coding: utf-8 -*-
"""
P0: CommandRegistry — Icepak 19.5 golden-spec-driven action bus.

The registry mirrors the original guibase mechanism:
  command_define {longname shortname icon cmd bubble helpurl whenactive ?dragoff_cmd?}
  command_set_hotkeys / command_set_hotkeys_tdv
so that PyQt menus/toolbars/hotkeys are *generated* from
docs/icepak_gui_golden.json instead of being hardcoded.

Every command resolves to either a real IceGui slot (SLOT_MAP) or an explicit
NYI handler that writes a WARN (red) message — menus stay complete, clicks
always land on a real execution path.
"""
import json
import os
import re

REPO = os.path.dirname(os.path.abspath(__file__))
GOLDEN_CANDIDATES = [
    os.environ.get("ICE_GOLDEN_SPEC"),
    os.path.join(REPO, "docs", "icepak_gui_golden.json"),
    os.path.join(REPO, "icepak_gui_golden.json"),
]

# --------------------------------------------------------------------------- #
# Golden spec loading
# --------------------------------------------------------------------------- #

def load_golden(path=None):
    """Return the parsed golden spec dict (menus/toolbars/hotkeys/icons)."""
    last = None
    for p in ([path] if path else GOLDEN_CANDIDATES):
        if not p or not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fp:
            last = json.load(fp)
        break
    if last is None:
        raise RuntimeError("icepak_gui_golden.json not found (set ICE_GOLDEN_SPEC)")
    return last


class CommandRegistry(object):
    """Read-only facade over the golden spec."""

    def __init__(self, spec=None):
        self.spec = spec if spec is not None else load_golden()

    # -- menus ---------------------------------------------------------------
    def menus(self):
        return list(self.spec.get("menus", []))

    def menu(self, name):
        for m in self.menus():
            if m["name"] == name:
                return m
        return None

    def all_commands(self, include_dynamic=False):
        """All scalar command labels referenced by menus/toolbars."""
        out = []

        def walk(entries):
            for e in entries:
                if isinstance(e, dict):
                    if "scalar" in e and isinstance(e["scalar"], str):
                        out.append(e["scalar"])
                    elif "descriptor" in e:
                        for w in e.get("descriptor", []):
                            if isinstance(w, str) and len(w) > 2:
                                out.append(w)
                        walk(e.get("cascade", []))
                    elif "list" in e:
                        walk(e["list"])

        for m in self.menus():
            if m.get("dynamic"):
                continue
            walk(m["entries"])
        for tb in self.toolbar_groups():
            walk(tb["entries"])
        return list(dict.fromkeys(out))

    # -- toolbars ------------------------------------------------------------
    def toolbar_groups(self):
        return list(self.spec.get("toolbars", []))

    def toolbar(self, name):
        for tb in self.toolbar_groups():
            if tb["name"] == name:
                return tb
        return None

    # -- hotkeys -------------------------------------------------------------
    def hotkeys(self, kind=None):
        out = []
        for h in self.spec.get("hotkeys", []):
            if kind is None or h.get("kind") == kind:
                out.append(h)
        return out

    # -- icons ---------------------------------------------------------------
    def icon_key(self, cmd):
        return self.spec.get("icons", {}).get(cmd, "")

    def command_meta(self, cmd):
        """Best-effort {icon, } metadata for a command label."""
        return {"icon": self.icon_key(cmd)}


# --------------------------------------------------------------------------- #
# Golden icon key -> IceIcons vector name
# --------------------------------------------------------------------------- #

ICON_ALIASES = {
    "bw_newg": "new", "open_icon": "open", "save_icon": "save",
    "print_icon": "print", "icepak_paint": "image", "bw_undo": "undo",
    "bw_redo": "redo", "new_home_nuvo": "home", "zoom_nuvo": "zoom",
    "scale_to_fit": "fit", "view_rotate_normal": "rotate",
    "one_window_nuvo": "win1", "four_windows_nuvo": "win4",
    "icepak_names_nuvo": "names", "neg_X": "axis_x", "pos_Y": "axis_y",
    "neg_Z": "axis_z", "iso": "iso", "reverse": "reverse",
    "power_setup": "limits", "icepak_mesh": "mesh",
    "icepak_radiation": "radiation", "check_nuvo": "check",
    "icepak_solve": "solve", "icepak_optim": "optim",
    "icepak_object_face": "face", "icepak_plane_cut": "plane",
    "icepak_iso_surface": "iso_surf", "icepak_point_probe": "point",
    "icepak_post_probe": "probe", "icepak_variation_plot": "plot",
    "icepak_history_plot": "history", "icepak_trials_plot": "trials",
    "icepak_transient": "transient", "icepak_solution_id": "sol_id",
    "icepak_summ_report": "report", "max_temperatures": "limits",
    "icepak_edit_object": "edit", "icepak_delete_object": "delete",
    "icepak_move_object": "move", "icepak_copy_object": "copy",
    "question": "help", "refresh_icon": "reload",
    "icepak_plus_x": "axis_x", "icepak_plus_y": "axis_y",
    "icepak_minus_z": "axis_z", "icepak_reverse": "reverse",
    "icepak_iso": "iso",
}

# object-type icon keys (icepak_block ...) map straight onto the same names
OBJECT_ICON_TYPES = [
    "block", "blower", "enclosure", "fan", "heat_exchanger", "heatsink",
    "material", "network", "opening", "package", "assembly", "pcb",
    "periodic", "plate", "resistance", "source", "grille", "wall",
]


def icon_for_command(icon_key):
    """Map a golden icon key to an IceIcons name ('' = no icon / generic)."""
    if not icon_key:
        return ""
    if icon_key.startswith("icepak_"):
        k = icon_key[len("icepak_"):]
        if k in OBJECT_ICON_TYPES:
            return k
    if icon_key in ICON_ALIASES:
        return ICON_ALIASES[icon_key]
    for pref in ("auto_", "icepak_"):
        if icon_key.startswith(pref):
            tail = icon_key[len(pref):]
            for k in ("align", "edit", "delete", "move", "copy", "mesh"):
                if tail.startswith(k):
                    return k
    if icon_key in ("align", "edit", "delete", "move", "copy", "help"):
        return icon_key
    return ""  # generic fallback in the UI layer


# --------------------------------------------------------------------------- #
# Command -> IceGui slot resolution
# --------------------------------------------------------------------------- #

# label -> "method" or "method:arg" or "" (explicit NYI)
def _create_kind(label):
    table = {
        "Create blocks": "block", "Create blowers": "blower",
        "Create enclosures": "enclosure", "Create fans": "fan",
        "Create heat exchangers": "heat_exchanger", "Create heat sinks": "heatsink",
        "Create materials": "material", "Create networks": "network",
        "Create openings": "opening", "Create packages": "package",
        "Create assemblies": "assembly", "Create printed circuit boards": "pcb",
        "Create periodic boundaries": "periodic", "Create plates": "plate",
        "Create resistances": "resistance", "Create sources": "source",
        "Create grille": "grille", "Create walls": "wall",
    }
    return table.get(label, "")


SLOT_MAP = {
    # File
    "New project": "_new_project_dialog", "Open project": "_open_dir",
    "Reload main version": "_reload", "Save project": "_save",
    "Save project as": "_save_as", "Unpack project": "_open_tzr",
    "Pack project": "_pack_project", "Print screen": "_print_screen",
    "Create image file": "_create_image", "Command prompt": "_command_prompt",
    "Quit": "close", "Export CSV/Excel": "_export_csv",
    # Edit
    "Undo": "_undo", "Redo": "_redo", "Find": "_find_object",
    # View
    "Bounding box": "_show_bbox", "Coord axes": "_toggle_axes",
    "Display ANSYS logo": "_toggle_logo",
    # Orient
    "Home position": "_home", "Isometric view": "_orient:iso",
    "Orient positive X": "_orient:+x", "Orient negative X": "_orient:-x",
    "Orient positive Y": "_orient:+y", "Orient negative Y": "_orient:-y",
    "Orient positive Z": "_orient:+z", "Orient negative Z": "_orient:-z",
    "Zoom in": "_zoom_in", "Scale to fit": "_fit",
    "Reverse orientation": "_reverse_orient", "Nearest axis": "_nearest_axis",
    "Save user view": "_save_user_view", "Clear user views": "_clear_user_views",
    "Write user views to file": "_write_user_views",
    "Read user views from file": "_read_user_views",
    # Model
    "Generate mesh": "_generate_mesh",
    "Check model": "_check_model",
    # Solve
    "Run solution": "_run_solution",
    "Solution monitor": "_open_solution_monitor",
    "Patch temperatures": "_patch_temperatures",
    "Basic settings": "_show_basic_settings",
    "Advanced settings": "_show_advanced_settings",
    "Parallel settings": "_show_parallel_settings",
    # Post
    "Object face (node)": "_create_post:Object face (node)",
    "Object face (facet)": "_create_post:Object face (facet)",
    "Plane cut": "_create_post:Plane cut",
    "Isosurface": "_create_post:Isosurface",
    "Point": "_create_post:Point",
    "Surface probe": "_create_post:Surface probe",
    "Min/max locations": "_create_post:Min/max locations",
    "Convergence plot": "_open_plot:Convergence",
    "Variation plot": "_open_plot:Variation",
    "3D Variation plot": "_open_plot:3D Variation",
    "History plot": "_open_plot:History",
    "Trials plot": "_open_plot:Trials",
    "Network temperature plot": "_open_plot:Network temperature",
    "Load post objects from file": "_load_post_objects",
    "Save post objects to file": "_save_post_objects",
    # View (window hotkey targets)
    "Edit object or postprocessing object": "_edit_current",
    "Delete object": "_delete_current",
    "Toggle object active": "_toggle_selected_active",
    "Toggle object visible": "_toggle_selected_visible",
    "Open/close tree node": "_toggle_tree_node",
    "Open/close model subtree": "_toggle_model_subtree",
    "Move object": "_move_current",
    "Copy object": "_copy_current",
    "Toggle shading type": "_cycle_shading",
    # Report
    "HTML report": "_html_report",
    "Summary report": "_summary_report",
    "Point report": "_point_report",
    "Full report": "_full_report",
    "Show optimization/param results": "_trials_results",
    "Fan operating points": "_fan_operating_points",
    "Network block values": "_network_block_values",
    # Help
    "Help": "_help", "Icepak on the Web": "_web_icepak",
    "Customer Portal": "_web_portal", "List shortcuts": "_list_shortcuts",
    "About Icepak": "_about",
    # View
    "Lights": "_lights_dialog",
    "Location": "_measure_start:Location",
    "Distance": "_measure_start:Distance",
    "Angle": "_measure_start:Angle",
    "Unit vector": "_measure_start:Unit vector",
    "Unit normal": "_measure_start:Unit normal",
    "Bounding box": "_measure_start:Bounding box",
    "Clear markers": "_marker_clear",
    "Clear rubber bands": "_marker_clear",
    "Location": "_measure_start:Location",
    "Distance": "_measure_start:Distance",
    "Angle": "_measure_start:Angle",
    "Unit vector": "_measure_start:Unit vector",
    "Unit normal": "_measure_start:Unit normal",
    "Bounding box": "_measure_start:Bounding box",
    "Add marker": None,
    "Clear markers": "_marker_clear",
    "Add rubber band": None,
    "Clear rubber bands": "_marker_clear",
    # Toolbar view actions
    "One viewing window": "_set_view_panes:1",
    "Four viewing windows": "_set_view_panes:4",
    "Display object names": "_cycle_names",
    # Toolbar object actions
    "Edit object": "_edit_current", "Move object": "_move_current",
    "Copy object": "_copy_current",
}

# toolbar/checkable items that carry state but no action yet (P3 wires them)
STATE_ONLY = {
    "Visible grid", "Origin marker", "Display rulers", "Display project title",
    "Display current date", "Display construction lines",
    "Display construction points", "Display mesh", "Mouse position",
    "Depthcue", "Tcl console", "Snap to grid", "Lights",
}


class NyiHandler(object):
    """Placeholder action: logs a red WARN with the command name."""

    def __init__(self, cmd):
        self.cmd = cmd

    def __call__(self, *args):
        gui = getattr(self, "_gui", None)
        if gui is not None:
            gui._nyi(self.cmd)


def resolve_slot(gui, cmd):
    """Return a callable for command label (or None if state-only)."""
    if cmd in SLOT_MAP and SLOT_MAP[cmd]:
        spec = SLOT_MAP[cmd]
        if ":" in spec:
            method, arg = spec.split(":", 1)
        else:
            method, arg = spec, None
        fn = getattr(gui, method, None)
        if fn is not None and callable(fn):
            if arg is not None:
                return (lambda fn=fn, arg=arg: fn(arg))
            return fn
    if cmd in set(_create_kind(table_name) for table_name in (
            "Create blocks", "Create blowers", "Create enclosures",
            "Create fans", "Create heat exchangers", "Create heat sinks",
            "Create materials", "Create networks", "Create openings",
            "Create packages", "Create assemblies",
            "Create printed circuit boards", "Create periodic boundaries",
            "Create plates", "Create resistances", "Create sources",
            "Create grille", "Create walls")):
        kind = _create_kind(cmd)
        fn = getattr(gui, "_create_object", None)
        if fn is not None and kind:
            return (lambda fn=fn, kind=kind: fn(kind))
    if cmd in STATE_ONLY:
        return None
    return NyiHandler(cmd)
