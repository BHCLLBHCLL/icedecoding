# -*- coding: utf-8 -*-
"""P9: Preferences — seven tabs (Display/Libraries/Object types/Interaction/
Mouse buttons/Meshing/Units), JSON store, .icepak_config variable-name
compatibility (read/write 'set key value' text), live application."""
import json
import os
import re

# --------------------------------------------------------------------------- #
# Preference spec (tabs -> fields), key names follow .icepak_config variables
# --------------------------------------------------------------------------- #

PREFS_SPEC = {
    "Display": [
        ("background_style", "Background style", "combo",
         ["gradient", "solid"]),
        ("background_color1", "Background color 1", "text", "#9ec8e8"),
        ("background_color2", "Background color 2", "text", "#f4f7fb"),
    ],
    "Libraries": [
        ("main_library_path", "Main library path", "text", ""),
        ("user_library_dir", "User library dir", "text", ""),
    ],
    "Object types": [
        ("obj_width", "Wireframe width", "spin", 1.0),
        ("obj_shading", "Allow solid shading", "check", 1),
        ("obj_decoration", "Show decoration (grille etc.)", "check", 1),
        ("obj_font_size", "Name font size", "int", 9),
    ],
    "Interaction": [
        ("motion_x", "Motion allowed X", "check", 1),
        ("motion_y", "Motion allowed Y", "check", 1),
        ("motion_z", "Motion allowed Z", "check", 1),
        ("restrict_to_cabinet", "Restrict movement to cabinet", "check", 1),
        ("no_penetration", "Objects can't penetrate each other", "check", 0),
        ("move_group", "Move object also moves group", "check", 0),
        ("snap_attributes", "Snap attributes (divs)", "int", 100),
        ("new_object_size_factor", "New object size factor", "spin", 0.2),
        ("cabinet_autoscale_factor", "Cabinet autoscale factor", "spin", 1.0),
        ("move_points_with_object", "Move points with object", "check", 0),
    ],
    "Mouse buttons": [
        ("mouse_left", "Left button", "combo", ["select", "box_pick", "rotate", "pan"]),
        ("mouse_middle", "Middle button", "combo", ["rotate", "pan", "accept"]),
        ("mouse_right", "Right button", "combo", ["pan", "finish", "select"]),
    ],
    "Meshing": [
        ("mesher_settings_type", "Default mesher settings", "combo",
         ["normal", "coarse", "null"]),
        ("min_elements_gap", "Min elements in gap", "int", 3),
    ],
    "Units": [
        ("unit_length", "Length unit", "text", "mm"),
        ("unit_temperature", "Temperature unit", "combo", ["C", "K", "F"]),
        ("unit_pressure", "Pressure unit", "text", "Pa"),
    ],
}

DEFAULTS = {}
for _tabs, _fields in PREFS_SPEC.items():
    for _f in _fields:
        _v = _f[3] if len(_f) > 3 else _f[2]
        if isinstance(_v, list):
            _v = _v[0]
        DEFAULTS[_f[0]] = _v


# --------------------------------------------------------------------------- #
# Store: JSON persistence + .icepak_config text compatibility
# --------------------------------------------------------------------------- #

def config_path():
    return os.path.join(os.path.expanduser("~"), ".icepak_config.json")


def default_legacy_path():
    return os.path.join(os.path.expanduser("~"), ".icepak_config")


class PrefsStore(object):
    """Key-value preference store with legacy Tcl 'set key value' IO."""

    def __init__(self, values=None):
        self.values = dict(DEFAULTS)
        for k, v in (values or {}).items():
            self.values[k] = v

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def update(self, mapping):
        self.values.update(mapping)

    def load(self, path=None):
        path = path or config_path()
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.values.update(data)
                return True
            except (OSError, ValueError):
                return False
        return False

    def save(self, path=None):
        path = path or config_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, ensure_ascii=False, indent=1)
        return path

    # -- legacy .icepak_config compatibility --------------------------------
    def load_legacy(self, path):
        """Parse 'set key value' lines (Tcl-style, .icepak_config)."""
        if not path or not os.path.exists(path):
            return False
        pat = re.compile(r'^\s*set\s+(\S+)\s+(.+?)\s*$')
        with open(path, encoding="latin-1", errors="replace") as fh:
            for line in fh:
                m = pat.match(line)
                if not m:
                    continue
                key, val = m.group(1), m.group(2).strip()
                if val.startswith('{') and val.endswith('}'):
                    val = val[1:-1].strip()
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                val = _coerce(val)
                self.values[key] = val
        return True

    def save_legacy(self, path=None):
        """Write 'set key value' text (can be sourced by Tcl)."""
        path = path or default_legacy_path()
        with open(path, "w", encoding="latin-1") as fh:
            fh.write(self.legacy_text())
        return path

    def legacy_text(self):
        """H1: all stored variables as Tcl 'set key value' text (roundtrip)."""
        return "".join('set %s %s\n' % (k, _tcl(v))
                       for k, v in sorted(self.values.items()))


def _coerce(val):
    low = val.lower()
    if low in ("true", "on"):
        return 1
    if low in ("false", "off"):
        return 0
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def _tcl(val):
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    return '"%s"' % str(val).replace('"', "")
