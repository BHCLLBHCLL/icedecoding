# -*- coding: utf-8 -*-
"""
P4: 18-type object editors (Info/Properties/Geometry tabs) + Copy from.

Property field specs are data-driven (kind -> key/label/widget), reading and
writing through the same setval/attributes the model parser understands.
"""
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QTabWidget, QVBoxLayout, QWidget,
)

from ice_forms import FormPage

# keys commonly present in decoded projects (setvals) — verified live objects
PROPERTY_SPECS = {
    "block": [
        ("block_type", "Type", "combo", ["solid", "fluid", "hollow"]),
        ("temp", "Temperature", "text"),
        ("heat", "Heat flow", "text"),
        ("material", "Material", "text"),
    ],
    "plate": [
        ("plate_type", "Type", "combo", ["solid", "hollow", "pcb"]),
        ("temp", "Temperature", "text"),
        ("heat", "Heat flow", "text"),
        ("material", "Material", "text"),
        ("thickness", "Thickness", "spin"),
    ],
    "source": [
        ("power", "Power", "text"),
        ("temp", "Temperature", "text"),
        ("heat", "Heat flow", "text"),
        ("source_type", "Type", "combo", ["chip", "heat", "power", "current"]),
    ],
    "fan": [
        ("fan_type", "Type", "combo", ["axial", "radial", "p_external"]),
        ("flow", "Flow rate", "text"),
        ("pressure", "Pressure rise", "text"),
        ("power", "Power", "text"),
        ("rpm", "RPM", "text"),
        ("kind", "Behavior", "combo", ["curve", "fixed", "none"]),
    ],
    "blower": [
        ("blower_type", "Type", "combo", ["centrifugal", "p_external"]),
        ("flow", "Flow rate", "text"),
        ("pressure", "Pressure rise", "text"),
        ("power", "Power", "text"),
    ],
    "opening": [
        ("opening_type", "Type", "combo", ["free", "press_release", "vel"]),
        ("temp", "Temperature", "text"),
        ("pressure", "Pressure", "text"),
        ("velocity", "Velocity", "text"),
    ],
    "ventres": [
        ("loss", "Loss coefficient", "text"),
        ("area", "Open area", "text"),
        ("resist", "Resistance", "text"),
    ],
    "grille": [
        ("loss", "Loss coefficient", "text"),
        ("area", "Open area", "text"),
    ],
    "wall": [
        ("wall_type", "Type", "combo", ["solid", "thin", "plate"]),
        ("temp", "Temperature", "text"),
        ("heat", "Heat flow", "text"),
        ("material", "Material", "text"),
    ],
    "resistance": [
        ("area", "Open area", "text"),
        ("loss", "Loss coefficient", "text"),
    ],
    "package": [
        ("package_type", "Type", "combo", ["bga", "qfp", "soic", "sot", "generic"]),
        ("rjc", "Rjc (C/W)", "text"),
        ("rjb", "Rjb (C/W)", "text"),
        ("power", "Power", "text"),
        ("material", "Material", "text"),
    ],
    "heatsink": [
        ("heat_sink_type", "Type", "combo", ["extruded", "folded", "custom", "angled_fin"]),
        ("material", "Material", "text"),
        ("fin_height", "Fin height", "spin"),
        ("fin_thickness", "Fin thickness", "spin"),
        ("fin_gap", "Fin gap", "spin"),
        ("fin_count", "Fin count", "int"),
    ],
    "pcb": [
        ("pcb_type", "Type", "combo", ["simple", "detailed"]),
        ("material", "Material", "text"),
        ("thickness", "Thickness", "spin"),
        ("power", "Power", "text"),
    ],
    "enclosure": [
        ("enclosure_type", "Type", "combo", ["box", "cyl"]),
        ("material", "Material", "text"),
    ],
    "network": [
        ("network_type", "Type", "combo", ["two_resistor", "delphi", "multi_resistor"]),
        ("power", "Power", "text"),
    ],
    "assembly": [
        ("assembly_type", "Type", "combo", ["generic", "pcb"]),
    ],
    "material": [
        ("material_kind", "Kind", "combo", ["solid", "fluid", "surface"]),
        ("thermal_conductivity", "Thermal conductivity", "text"),
        ("density", "Density", "text"),
        ("specific_heat", "Specific heat", "text"),
    ],
    "periodic": [
        ("periodic_type", "Type", "combo", ["x", "y", "z"]),
    ],
    "domain": [
        ("domain_type", "Type", "combo", ["box", "cyl"]),
    ],
}

COMMON_SETVAL_KEYS = {
    "temp", "heat", "power", "material", "flow", "pressure", "rpm", "rjc",
    "rjb", "thickness", "area", "loss", "velocity", "fan_type", "kind",
    "block_type", "plate_type", "source_type", "opening_type", "wall_type",
    "package_type", "heat_sink_type", "pcb_type", "enclosure_type",
    "network_type", "blower_type", "ventres_type", "grid_priority",
    "current_stype", "creation_order",
}


# ---- P19-3: golden per-class property keys (from decoded real projects) ----
# union of 'properties' keys per kind across _report/projects/*.json (26 jobs).
GOLDEN_KEYS = {
    "block": ["solid_material", "power", "temp_total", "res_rjc",
              "res_rjb", "res_jpow", "thermal_heat_tr_face_profile",
              "group", "groups"],
    "domain": ["minx_type", "maxx_type", "miny_type", "maxy_type",
               "minz_type", "maxz_type", "fixvals"],
    "enclosure": ["solid_material", "xd", "xe", "yd", "ye", "zd", "ze",
                  "current_section"],
    "fan": ["case_size", "case_thickness", "mass_flow", "flowtype",
            "curvetype", "dir_spec", "side", "radius", "xc", "yc", "zc",
            "xvec", "yvec", "zvec"],
    "heatsink": ["dim1", "dim2", "num1", "sdim1", "base_height",
                 "overall_height", "hi_rad", "low_rad"],
    "material": ["mat_type", "mat_subtype", "solid_conductivity_x",
                 "solid_conductivity_y", "solid_conductivity_z",
                 "solid_density", "solid_sp_heat_constant", "fluid_density",
                 "fluid_viscosity_constant", "fluid_conductivity_constant",
                 "fluid_sp_heat_constant", "fluid_mol_weight",
                 "normal_conductivity"],
    "opening": ["xvecf", "yvecf", "zvecf", "xcoeffq", "ycoeffq", "zcoeffq",
                "losstype", "mass_type", "heat_input", "heat_type",
                "shtype", "vdepend"],
    "package": ["die_dim1", "die_dim2", "pad_dim1", "pad_dim2", "ball_diam",
                "package_thickness", "sub_material", "mold_material",
                "pad_material", "sub_1trace_pct", "sub_2trace_pct",
                "sub_3trace_pct", "sub_4trace_pct", "sub_btrace_pct",
                "sub_ttrace_pct", "sub_inter_trace_pct", "via_num",
                "via_diam", "via_plate_thickness", "sub_trace_thickness"],
    "part": ["is_container", "grid_use_global", "grid_size_x", "grid_size_y",
             "grid_size_z", "grid_hdm_uniform", "grid_hdm_mlm_2d",
             "grid_type", "mesh_separate"],
    "pcb": ["kneff", "kpeff", "sbth", "tth", "bth", "mth", "tper", "bper",
            "mper"],
    "plate": ["plate_type", "eff_thick", "sol_material", "power",
              "cres_heat_tr_on"],
    "resistance": ["xcoeffq", "ycoeffq", "zcoeffq", "losstype"],
    "source": ["temp_total", "temp_transient", "temp_trans_type",
               "temp_power_type", "current_voltage_type", "curr_source",
               "usagetype_s", "all_emis_on", "temp_trans_exp_a",
               "temp_trans_exp_b"],
    "ventres": ["vent_type", "xcoeffq", "ycoeffq", "zcoeffq", "xratioq",
                "dir_spec", "xvec", "yvec", "zvec"],
    "wall": ["thermal_type", "thermal_rtype", "thermal_heat_tr",
             "thermal_heat_tr_on", "thermal_heat_tr_type", "thermal_heat_area",
             "thermal_itemp", "eff_thick", "sol_material", "vtype",
             "forced_flow_dir", "convection_type", "external_orientation",
             "int_emis_on", "active"],
}

# P19-3: golden per-class keys also persist through the model codec
for _kind_keys in GOLDEN_KEYS.values():
    COMMON_SETVAL_KEYS.update(_kind_keys)


def _label_of(key):
    return key.replace('_', ' ').title()


def spec_for(kind):
    """Full per-class field spec: curated PROPERTY_SPECS rows + the golden
    real-project keys (any golden key not already curated becomes an editable
    text row), so the editor covers the decoded Icepak field set per kind."""
    base = list(PROPERTY_SPECS.get(kind, []))
    seen = {item[0] for item in base}
    for key in GOLDEN_KEYS.get(kind, []):
        if key not in seen:
            kind_ = 'check' if key in ('cres_heat_tr_on', 'thermal_heat_tr_on',
                                       'int_emis_on', 'temp_transient',
                                       'is_container', 'mesh_separate',
                                       'grid_use_global', 'grid_hdm_uniform',
                                       'grid_hdm_mlm_2d') else 'text'
            base.append((key, _label_of(key), kind_))
            seen.add(key)
    return base


def spec_has(key, kind):
    return any(item[0] == key for item in spec_for(kind))


class ObjectEditDialog(QDialog):
    """Icepak object editor: Info / Properties / Geometry notebook."""

    def __init__(self, parent=None, obj=None, project=None):
        super().__init__(parent)
        self._parent = parent
        self._obj = obj
        self._project = project
        self.setWindowTitle("Edit: %s" % getattr(obj, "name", "object"))
        self.setMinimumSize(560, 420)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget(self)
        v.addWidget(self.tabs, 1)
        self._build_tabs()
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_apply = QPushButton("Apply", self)
        self.btn_apply.clicked.connect(self._apply)
        ok_btn = QPushButton("OK", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._apply_and_close)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_apply)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel)
        v.addLayout(btns)

    # -- tabs ---------------------------------------------------------------
    def _build_tabs(self):
        obj = self._obj
        sv = dict(getattr(obj, "setvals", None) or {})
        # Info
        info = FormPage(self, "Info")
        f = info.section("Identification")
        info.add_row(f, "name", "Name", "text", getattr(obj, "name", ""))
        info.add_row(f, "kind", "Type", "label", getattr(obj, "kind", ""))
        info.add_row(f, "active", "Active", "check", True)
        info.add_row(f, "priority", "Priority", "int",
                     sv.get("grid_priority", 10), minimum=0, maximum=999)
        info.add_row(f, "group", "Group", "text", "")
        self.tabs.addTab(info, "Info")
        # Properties
        prop = FormPage(self, "Properties")
        spec = spec_for(getattr(obj, "kind", ""))
        if spec:
            f = prop.section("Properties")
            for spec_item in spec:
                key, label, kind = spec_item[0], spec_item[1], spec_item[2]
                options = spec_item[3] if len(spec_item) > 3 else None
                value = sv.get(key)
                if isinstance(value, list) and value:
                    value = value[-1]
                prop.add_row(f, key, label, kind, value, options=options)
        else:
            f = prop.section("Properties")
            prop.add_row(f, "info", "Field-set", "label",
                         "No dedicated fields for this type yet (read-only).")
        self.tabs.addTab(prop, "Properties")
        # Geometry
        geo = FormPage(self, "Geometry")
        sh = getattr(obj, "shape", None)
        svs = dict(getattr(sh, "setvals", None) or {})
        f = geo.section("Shape")
        geo.add_row(f, "shape_type", "Shape", "label",
                    getattr(sh, "type", "") or "")
        p1 = svs.get("point1", [0, 0, 0])
        p2 = svs.get("point2", [1, 1, 1])
        if not isinstance(p1, (list, tuple)):
            p1 = [0, 0, 0]
        if not isinstance(p2, (list, tuple)):
            p2 = [1, 1, 1]
        f = geo.section("Bounds")
        for i, ax in enumerate("xyz"):
            geo.add_row(f, "p1.%s" % ax, "%sS" % ax.upper(), "spin", p1[i])
        for i, ax in enumerate("xyz"):
            geo.add_row(f, "p2.%s" % ax, "%sE" % ax.upper(), "spin", p2[i])
        self.tabs.addTab(geo, "Geometry")

    # -- apply --------------------------------------------------------------
    def _apply(self):
        obj = self._obj
        if obj is None:
            return
        name_row = Info = None
        info_page = self.tabs.widget(0)
        r = info_page.row("name")
        if r is not None and r.get():
            obj.name = str(r.get())

        sv = getattr(obj, "setvals", None)
        if sv is None:
            sv = obj.setvals = {}
        prop_page = self.tabs.widget(1)
        for row in prop_page._rows:
            if row.key in ("info",):
                continue
            val = row.get()
            sv[row.key] = [str(val)] if isinstance(val, (float, int)) \
                else val
        geo_page = self.tabs.widget(2)
        p1 = [geo_page.row("p1.x").get(), geo_page.row("p1.y").get(),
              geo_page.row("p1.z").get()]
        p2 = [geo_page.row("p2.x").get(), geo_page.row("p2.y").get(),
              geo_page.row("p2.z").get()]
        sh = getattr(obj, "shape", None)
        if sh is not None:
            sv2 = sh.setvals
            sv2["point1"] = [str(x) for x in p1]
            sv2["point2"] = [str(x) for x in p2]
        parent = self._parent
        applied = getattr(parent, "_object_edit_applied", None)
        if applied is not None:
            applied(obj)

    def _apply_and_close(self):
        self._apply()
        self.accept()


class CopyFromDialog(QDialog):
    """Icepak edit panel Copy from: take another object's properties."""

    def __init__(self, parent=None, obj=None, others=None):
        super().__init__(parent)
        self.setWindowTitle("Copy from")
        self._obj = obj
        self._others = list(others or [])
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.addWidget(QLabel("Copy geometry and properties from:", self))
        self._radio = None
        grid = QGridLayout()
        for i, o in enumerate(self._others):
            rb = QRadioButton(getattr(o, "name", str(o)), self)
            if i == 0:
                rb.setChecked(True)
            grid.addWidget(rb, i, 0)
            self._radio = self._radio or rb
        v.addLayout(grid)
        self.mode = QRadioButton("Deactivate other object", self)
        self.mode2 = QRadioButton("Delete other object", self)
        self.mode3 = QRadioButton("Keep other object", self)
        self.mode3.setChecked(True)
        self.mode.setChecked(False)
        v.addWidget(self.mode)
        v.addWidget(self.mode2)
        v.addWidget(self.mode3)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok_btn = QPushButton("Copy", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._ok)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel)
        v.addLayout(btns)

    def _ok(self):
        self.accept()

    def choice(self):
        """(index_of_source, mode) with mode in deactivate/delete/keep."""
        checked = [r for r in self.findChildren(QRadioButton)
                   if r.isChecked()]
        src = None
        mode = "keep"
        for r in checked:
            if r is self.mode:
                mode = "deactivate"
            elif r is self.mode2:
                mode = "delete"
            elif r is self.mode3:
                mode = "keep"
            else:
                for i, o in enumerate(self._others):
                    if o is not None and getattr(o, "name", None) == r.text():
                        src = i
        return src, mode
