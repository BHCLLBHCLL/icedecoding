# -*- coding: utf-8 -*-
"""ice_gui.py — ANSYS Icepak 2019 R3 同构主界面 (icedecoding).

布局对齐 ICE_GUI_DESIGN.md / menus_icepak.tcl:
  Menu: File Edit View Orient Macros Model Solve Post Report Windows Help
  Toolbars: File | Edit | Viewing | Orientation || Model and solve | Postprocessing
            || Object creation | Object modification | Alignment
  Left: Project / Library tree + TDV strip
  Center: Graphics (gradient, triad, ANSYS 2019 R3 watermark)
  Bottom: Message (Verbose / Log / Save)

用法:
    python ice_gui.py
    python ice_gui.py D:/training/icepak
    python ice_gui.py D:/training/icepak/avonics.tzr
"""

from __future__ import annotations

import os
import sys
import math
import json
import copy

import numpy as np

# ---------------------------------------------------------------------------
# 包导入(允许以脚本方式直接运行)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from icepak_parser import model_parser, export, tzr  # noqa: E402
from icepak_parser.cli import find_projects  # noqa: E402
from ice_create import (  # noqa: E402
    clone_object, default_cabinet, default_object, next_object_name,
    object_active, project_files_for_pack, serialize_model,
    set_object_active, take_object, translate_object,
)

# ---------------------------------------------------------------------------
# GUI / VTK 依赖
# ---------------------------------------------------------------------------
try:  # pragma: no cover - 运行环境判断
    from PyQt5.QtCore import Qt, QTimer, QSize, QUrl, QSettings
    from PyQt5.QtGui import QColor, QDesktopServices, QFont, QKeySequence
    from PyQt5.QtWidgets import (
        QAction, QActionGroup, QApplication, QDialog, QFileDialog, QGridLayout,
        QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox,
        QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QTabWidget,
        QToolBar, QVBoxLayout, QWidget,
    )
    import vtk
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtk.util import numpy_support
    from ice_icons import IceIcons
    from ice_actions import CommandRegistry
    from ice_menus_toolbars import build_menus, build_toolbars, apply_hotkeys
    from ice_view3d import (
        allowed_delta, box_pick, circle_pick, clamp_to_box, snap_point,
        snap_value, make_display_actors, nearest_face, face_center,
        align_face_move, align_face_stretch, align_centers, match_face,
    )
    from ice_editors import CopyFromDialog, ObjectEditDialog
    from ice_solve_gui import (PatchTemperaturesDialog, PlotWindow,
                               ResidualMonitorWindow, RunSolutionDialog,
                               SolveSettingsDialog)
    from ice_macros_gui import MacroWizard
    from ice_macros import BUILTIN_MACROS, build_macro
    from ice_prefs_gui import AnnotationsDialog, PreferencesDialog
    from ice_prefs import PrefsStore
    from ice_panes import (
        DetailsDialog, EditToolbarsDialog, GeometryWindow, LibraryTree,
        MessageWindow, NewProjectDialog, PROJECT_NODES, ProjectTree,
        TdvStrip, TranslateDialog, WelcomeDialog, find_icepak_lib,
    )
    HAS_GUI = True
except Exception:  # pragma: no cover
    HAS_GUI = False
    IceIcons = None  # type: ignore
    PROJECT_NODES = (
        "Problem setup", "Solution settings", "Groups", "Post-processing",
        "Points", "Surfaces", "Trash", "Inactive", "Model",
    )

# ===========================================================================
# 1. 3D 几何构建 (numpy -> vtkPolyData)
# ===========================================================================

def _polydata(points, cells, kind: str):
    """points: (N,3); cells: 顶点索引序列, 支持每单元变长(quads+triangles 混用).
    kind: 'lines' | 'polys'."""
    pd = vtk.vtkPolyData()
    vpts = vtk.vtkPoints()
    vpts.SetData(numpy_support.numpy_to_vtk(np.asarray(points, dtype=float),
                                            deep=True))
    pd.SetPoints(vpts)
    # 变长单元 -> (每单元顶点数前缀, 连接索引) 拼接
    counts, idx = [], []
    for c in cells:
        counts.append(len(c))
        idx.extend(c)
    conn = np.empty(len(counts) + len(idx), dtype=np.int64)
    off = 0
    for n, c in zip(counts, cells):
        conn[off] = n
        conn[off + 1: off + 1 + n] = c
        off += 1 + n
    arr = vtk.vtkCellArray()
    arr.SetCells(len(cells),
                 numpy_support.numpy_to_vtkIdTypeArray(conn, deep=True))
    if kind == "lines":
        pd.SetLines(arr)
    else:
        pd.SetPolys(arr)
    return pd


def _box(lo, hi):
    """8 顶点 + 6 四边面."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    pts = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=float)
    quads = np.array([
        [0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1],
        [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0],
    ], dtype=np.int64)
    lines = np.array([
        [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6],
        [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7],
    ], dtype=np.int64)
    return pts, quads, lines


def box_polydata(lo, hi, wireframe=False):
    pts, quads, lines = _box(lo, hi)
    return _polydata(pts, lines if wireframe else quads,
                     "lines" if wireframe else "polys")


def _extrude_pts(pts, axis, lo_v, hi_v):
    """把平面多边形沿 axis(0/1/2) 挤出成柱体."""
    n = len(pts)
    p1 = np.copy(pts)
    p2 = np.copy(pts)
    p1[:, axis] = lo_v
    p2[:, axis] = hi_v
    body = np.vstack([p1, p2])
    side = []
    for i in range(n):
        j = (i + 1) % n
        side.append([i, j, n + j, n + i])
    return body, np.array(side, dtype=np.int64)


def polygon_polydata(verts, height, plane, wireframe=False):
    """shape_polygon: 顶点列表 + 厚度, 沿 plane 法向挤出."""
    verts = np.asarray(verts, dtype=float)
    axis = int(plane) if plane is not None and 0 <= int(plane) <= 2 else 2
    mid = verts[:, axis].mean()
    lo, hi = mid - height / 2.0, mid + height / 2.0
    body, side = _extrude_pts(verts, axis, lo, hi)
    if wireframe:
        lines = []
        n = len(verts)
        for i in range(n):
            j = (i + 1) % n
            lines.append([i, j])
            lines.append([n + i, n + j])
            lines.append([i, n + i])
        return _polydata(body, np.array(lines), "lines")
    # 顶/底 fan 三角形
    n = len(verts)
    cells = [list(c) for c in side]
    for i in range(1, n - 1):
        cells.append([0, i, i + 1])
        cells.append([n, n + i, n + i + 1])
    return _polydata(body, cells, "polys")


def cyl_polydata(c1, c2, radius, iradius=0.0, n=24, wireframe=False):
    """shape_cyl: 轴向圆柱(可空心), 用 n 段棱柱近似."""
    c1 = np.asarray(c1, dtype=float)
    c2 = np.asarray(c2, dtype=float)
    if radius <= 0:
        return None
    axis = c2 - c1
    L = np.linalg.norm(axis)
    if L < 1e-12:
        axis = np.array([0.0, 0.0, 1.0])
    else:
        axis = axis / L
    # 建立局部正交基 (u, v, axis)
    ref = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(ref, axis)) > 0.9:
        ref = np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    ang = np.linspace(0.0, 2 * math.pi, n + 1)[:n]
    ring = (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v) * radius
    ring_in = ring * (iradius / radius) if iradius > 0 else None

    def ring_at(center):
        return center + ring

    a = ring_at(c1)
    b = ring_at(c2)
    body = np.vstack([a, b])
    side = []
    for i in range(n):
        j = (i + 1) % n
        side.append([i, j, n + j, n + i])
    if wireframe:
        lines = []
        for i in range(n):
            j = (i + 1) % n
            lines.append([i, j])
            lines.append([n + i, n + j])
            lines.append([i, n + i])
        return _polydata(body, lines, "lines")
    cells = [list(c) for c in side]
    # 顶底盖(fan)
    for _c in (c1, c2):
        for i in range(1, n - 1):
            cells.append([0, i, i + 1])
    # 空心内壁
    if ring_in is not None:
        ai = c1 + ring_in
        bi = c2 + ring_in
        body = np.vstack([body, ai, bi])
        for i in range(n):
            j = (i + 1) % n
            cells.append([2 * n + i, 2 * n + j, 2 * n + n + j,
                          2 * n + n + i])
    return _polydata(body, cells, "polys")


def quad_polydata(p1, p2, thickness, plane, wireframe=False):
    """shape_quad: 两点矩形 + 厚度, 沿 plane 法向."""
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    axis = int(plane) if plane is not None and 0 <= int(plane) <= 2 else 2
    lo, hi = p1.copy(), p2.copy()
    lo[axis] = min(p1[axis], p2[axis])
    hi[axis] = lo[axis] + abs(thickness)
    if hi[axis] - lo[axis] < 1e-12:
        hi[axis] = lo[axis] + 1e-4
    return box_polydata(lo, hi, wireframe)


def hexa_polydata(p1, p2, wireframe=False):
    lo = np.minimum(p1, p2)
    hi = np.maximum(p1, p2)
    return box_polydata(lo, hi, wireframe)


def container_polydata(sv, wireframe=False):
    """shape_container: 用 ns_bbmin/ns_bbmax 局部包围盒 + position 平移."""
    try:
        bbmin = [float(v) for v in sv["ns_bbmin"]]
        bbmax = [float(v) for v in sv["ns_bbmax"]]
        pos = [float(v) for v in sv.get("position", ["0", "0", "0"])[:3]]
    except (KeyError, ValueError):
        return None
    lo = np.array(bbmin) + np.array(pos)
    hi = np.array(bbmax) + np.array(pos)
    return box_polydata(lo, hi, wireframe)


def circ_polydata(sv, wireframe=False):
    """shape_circ: 圆盘/圆环(取薄片)."""
    try:
        center = [float(v) for v in sv["center"][:3]]
        radius = float(sv["radius"][0])
        plane = int(sv.get("plane", ["2"])[0])
        iradius = float(sv.get("iradius", ["0"])[0])
    except (KeyError, ValueError, IndexError):
        return None
    axis = plane if 0 <= plane <= 2 else 2
    c = np.asarray(center, dtype=float)
    if iradius > 0:
        return cyl_polydata(c, c, radius, iradius, n=24, wireframe=wireframe)
    # 薄圆柱盖
    c2 = c.copy()
    c2[axis] += 1e-4
    return cyl_polydata(c, c2, radius, 0.0, n=24, wireframe=wireframe)


def shape_to_geometry(shape, wireframe=False):
    """由 Shape -> vtkPolyData 或 None. 返回 (polydata, bounds6)."""
    if shape is None:
        return None
    sv = shape.setvals or {}
    t = shape.type or ""
    try:
        if t == "shape_hexa":
            pd = hexa_polydata([float(v) for v in sv["point1"]],
                               [float(v) for v in sv["point2"]], wireframe)
        elif t == "shape_quad":
            pd = quad_polydata(
                [float(v) for v in sv["point1"]],
                [float(v) for v in sv["point2"]],
                float(sv.get("thickness", ["0"])[0]),
                int(sv.get("plane", ["2"])[0]) if sv.get("plane") else 2,
                wireframe)
        elif t == "shape_cyl":
            pd = cyl_polydata(
                [float(v) for v in sv["center"]],
                [float(v) for v in sv["center2"]],
                float(sv.get("radius", ["0"])[0]),
                float(sv.get("iradius", ["0"])[0]),
                wireframe=wireframe)
        elif t == "shape_polygon":
            nv = int(sv.get("nverts", ["0"])[0])
            verts = [float(v) for i in range(1, nv + 1)
                     for v in sv.get("vert%d" % i, [])]
            verts = [verts[i:i + 3] for i in range(0, len(verts), 3)]
            verts = [v for v in verts if len(v) == 3]
            if len(verts) < 3:
                return None
            pd = polygon_polydata(
                verts, float(sv.get("height", ["0"])[0]),
                int(sv.get("plane", ["2"])[0]) if sv.get("plane") else 2,
                wireframe)
        elif t == "shape_container":
            pd = container_polydata(sv, wireframe)
        elif t == "shape_circ":
            pd = circ_polydata(sv, wireframe)
        else:
            return None
    except (KeyError, ValueError, IndexError, TypeError):
        return None
    if pd is None:
        return None
    return pd, np.array(pd.GetBounds())


# ===========================================================================
# 2. 对象类型 -> 颜色/可见图层
# ===========================================================================

KIND_COLORS = {
    "domain":    (0.20, 0.75, 0.30),   # 绿(框架)
    "block":     (0.30, 0.48, 0.82),   # 钢蓝
    "plate":     (0.90, 0.55, 0.20),   # 橙
    "source":    (0.92, 0.25, 0.22),   # 红
    "fan":       (0.20, 0.75, 0.80),   # 青
    "opening":   (0.95, 0.83, 0.20),   # 黄
    "wall":      (0.60, 0.60, 0.62),   # 灰
    "resistance": (0.85, 0.35, 0.75),  # 品红
    "ventres":   (0.75, 0.45, 0.30),   # 棕
    "material":  (0.25, 0.70, 0.45),   # 绿
    "part":      (0.40, 0.55, 0.55),   # 青灰
    "package":   (0.55, 0.40, 0.80),   # 紫
    "pcb":       (0.35, 0.70, 0.35),   # 草绿
    "heatsink":  (0.75, 0.65, 0.45),   # 黄褐
    "enclosure": (0.50, 0.55, 0.60),   # 蓝灰
    "assembly":  (0.45, 0.50, 0.70),
    "blower":    (0.15, 0.60, 0.70),
    "network":   (0.70, 0.35, 0.55),
    "heat_exchanger": (0.40, 0.62, 0.72),
    "periodic":  (0.80, 0.50, 0.40),
}

DEFAULT_COLOR = (0.65, 0.65, 0.65)

# 图层默认全部开启
ALL_KINDS = list(KIND_COLORS.keys())


def kind_color(kind):
    return KIND_COLORS.get(kind, DEFAULT_COLOR)


# ===========================================================================
# 3. 场景对象
# ===========================================================================

class SceneObject:
    __slots__ = ("name", "kind", "color", "polydata", "bounds")

    def __init__(self, name, kind, color, polydata, bounds):
        self.name = name
        self.kind = kind
        self.color = color
        self.polydata = polydata
        self.bounds = bounds


def build_scene(model, layer_on, wireframe=False):
    """model -> SceneObject 列表(仅绘制有几何的对象)."""
    objs = []
    if model is None:
        return objs
    for o in model._all_objects():
        if not layer_on.get(o.kind, True):
            continue
        g = shape_to_geometry(o.shape, wireframe)
        if g is None:
            continue
        pd, bounds = g
        objs.append(SceneObject(o.name, o.kind, kind_color(o.kind), pd,
                                bounds))
    return objs


# ===========================================================================
# 4. Icepak 2019 R3 同构 GUI
# ===========================================================================

ICEPAK_VERSION = "2019 R3"
ICEPAK_TITLE = "ANSYS Icepak %s" % ICEPAK_VERSION
HELP_DIR = os.path.normpath(os.path.join(
    r"C:\Program Files\ANSYS Inc\v195", "commonfiles", "help", "en-us",
    "help", "ice_ug"))
WEB_ICEPAK = "https://www.ansys.com/Products/Electronics/ANSYS-Icepak"
WEB_PORTAL = "https://support.ansys.com/portal/site/AnsysCustomerPortal"

CREATE_OBJECT_TYPES = (
    ("block", "Blocks", "Create blocks"),
    ("blower", "Blowers", "Create blowers"),
    ("enclosure", "Enclosures", "Create enclosures"),
    ("fan", "Fans", "Create fans"),
    ("heat_exchanger", "Heat exchangers", "Create heat exchangers"),
    ("heatsink", "Heat sinks", "Create heat sinks"),
    ("material", "Materials", "Create materials"),
    ("network", "Networks", "Create networks"),
    ("opening", "Openings", "Create openings"),
    ("package", "Packages", "Create packages"),
    ("assembly", "Assemblies", "Create assemblies"),
    ("pcb", "Printed circuit boards", "Create printed circuit boards"),
    ("periodic", "Periodic boundaries", "Create periodic boundaries"),
    ("plate", "Plates", "Create plates"),
    ("resistance", "Resistances", "Create resistances"),
    ("source", "Sources", "Create sources"),
    ("ventres", "Grille", "Create grille"),
    ("wall", "Walls", "Create walls"),
)

VISIBLE_KINDS = ALL_KINDS + [
    "blower", "network", "heat_exchanger", "periodic",
]
SHADING_MODES = (
    "wire", "solid", "solid/wire", "hidden line", "selected_solid",
)
UNDO_LIMIT = 50

STYLE = """
QMainWindow, QDialog { background: #e8e8e8; }
QMenuBar { background: #e8e8e8; }
QToolBar { background: #e8e8e8; border: 0; spacing: 1px; padding: 1px; }
QToolBar::separator { width: 6px; }
QTreeWidget { background: #ffffff; alternate-background-color: #f4f7fb; }
QTabWidget::pane { border: 1px solid #b0b0b0; }
QSplitter::handle { background: #c0c0c0; }
#TdvStrip { background: #d4d0c8; border-right: 1px solid #a0a0a0; }
"""


class IceGui(QMainWindow):
    """Icepak 2019 R3 layout: menus, toolbars, Project tree, Graphics, Message."""

    def __init__(self, path=None, enable_3d=True, show_welcome=None):
        if not HAS_GUI:
            raise RuntimeError(
                "PyQt5 / vtk 未安装: python -m pip install PyQt5 vtk numpy")
        super().__init__()
        self._enable_3d = enable_3d
        self.setWindowTitle(ICEPAK_TITLE)
        self.resize(1600, 900)

        self.root_path = None
        self.projects = []
        self.project = None
        self.scene_objs = []
        self.actors = []
        self._actor_map = {}
        self.selected = None
        self._shading = "solid/wire"
        self._show_axes = True
        self._show_logo = True
        self._show_names = 0
        self._fit_pending = False
        self._orient_widget = None
        self._logo_actor = None
        self._hidden = set()
        self._inactive = set()
        self._trash = []
        self._groups = {}
        self._undo_stack = []
        self._redo_stack = []
        self._user_views = []
        self._press_pos = None
        self._name_actors = []
        self._extra_renderers = []
        self._view_panes = 1
        self._toolbars = {}
        self._tb_row = -1
        self._registry = CommandRegistry() if CommandRegistry is not None else None
        self._menus = {}
        self._hotkey_actions = {}
        self._created_by_command = {}
        self._display_state = {}
        self._display_actors = {}
        self._motion_axes = [True, True, True]
        self._snap_step = None          # None = off; else cabinet/100
        self._restrict_to_cabinet = True
        self._dirty = False
        self._prefs = PrefsStore()
        self._prefs.load()
        self._mesh_result = None
        self._mesh_actor = None
        self._mesh_params = {}
        self._align_session = None
        self._align_picked = []
        self._bg_style = "gradient"
        self._bg_color1 = "#9ec8e8"
        self._bg_color2 = "#f4f7fb"
        if show_welcome is None:
            show_welcome = bool(enable_3d and not path)
        self._pending_welcome = bool(show_welcome)

        self._build_ui()
        self._apply_style()
        self._setup_3d_overlays()
        self._load_persisted_user_views()
        self._rebuild_user_views_menu()
        if path:
            self.open_path(path)
        else:
            self.project_tree.reset_empty("untitled")
            self.log("This is the 64-bit version")
            self.log("ANSYS Icepak %s. Use File to open a project or .tzr."
                     % ICEPAK_VERSION)
            self.log("Copyright ANSYS Inc. All rights reserved. "
                     "(ice viewer compatible build)", "INFO")
            lib = find_icepak_lib()
            if lib:
                self.library_tree.populate_from_path(lib)

    def log(self, msg, level="INFO"):
        if hasattr(self, "message_win"):
            self.message_win.log(msg, level)
        self.statusBar().showMessage(msg, 8000)

    def _nyi(self, name):
        self.log("[%s] not available in ice viewer "
                 "(Icepak-only / not yet mapped)." % name, "WARN")

    def _apply_style(self):
        self.setStyleSheet(STYLE)

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        self._build_menus()
        self._build_toolbars()

        self.project_tree = ProjectTree(self)
        self.project_tree.object_selected.connect(self._on_object_selected)
        self.project_tree.object_activated.connect(self._on_object_activated)
        self.project_tree.node_selected.connect(self._on_node_selected)
        self.project_tree.node_activated.connect(self._on_node_activated)
        self.project_tree.visibility_changed.connect(self._on_tree_visibility)
        self.project_tree.drop_requested.connect(self._on_tree_drop)
        self.project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self._tree_menu)
        self.library_tree = LibraryTree(self)
        self.library_tree.item_activated.connect(self._on_lib_activated)
        self.nav_tabs = QTabWidget(self)
        self.nav_tabs.addTab(self.project_tree, "Project")
        self.nav_tabs.addTab(self.library_tree, "Library")
        self.nav_tabs.setMinimumWidth(220)
        self.tree = self.project_tree  # compat alias

        self.tdv_strip = TdvStrip(self)
        self.tdv_strip.mode_changed.connect(self._on_tdv_mode)
        self.tdv_strip.hide_requested.connect(self._toggle_selected_visible)

        if self._enable_3d:
            self.vtk_widget = QVTKRenderWindowInteractor(self)
            self.renderer = vtk.vtkRenderer()
            # bottom #f4f7fb, top #9ec8e8 (Icepak screenshot gradient)
            self.renderer.SetBackground(0.957, 0.969, 0.984)
            self.renderer.SetBackground2(0.620, 0.784, 0.910)
            self.renderer.GradientBackgroundOn()
            self.renderer.GetActiveCamera().ParallelProjectionOn()
            self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
            iren = self.vtk_widget.GetRenderWindow().GetInteractor()
            iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            iren.AddObserver("LeftButtonPressEvent", self._on_press)
            iren.AddObserver("LeftButtonReleaseEvent", self._on_release)
            draw_body = self.vtk_widget
        else:
            self.vtk_widget = None
            self.renderer = None
            draw_body = QLabel("3D 视图已禁用（headless 测试模式）", self)
            draw_body.setAlignment(Qt.AlignCenter)

        graphics = QWidget(self)
        gh = QHBoxLayout(graphics)
        gh.setContentsMargins(0, 0, 0, 0)
        gh.setSpacing(0)
        gh.addWidget(self.tdv_strip, 0)
        self._view_stack = QStackedWidget(self)
        self._single_draw = draw_body
        self._view_stack.addWidget(draw_body)
        self._quad_widget = QWidget(self)
        qg = QGridLayout(self._quad_widget)
        qg.setContentsMargins(1, 1, 1, 1)
        qg.setSpacing(1)
        self._quad_labels = []
        for i, name in enumerate(("-X", "+Y", "-Z", "Iso")):
            lab = QLabel(name, self._quad_widget)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet("background:#9ec8e8; color:#234;")
            qg.addWidget(lab, i // 2, i % 2)
            self._quad_labels.append(lab)
        self._view_stack.addWidget(self._quad_widget)
        self._two_widget = QWidget(self)
        tw = QHBoxLayout(self._two_widget)
        tw.setContentsMargins(1, 1, 1, 1)
        tw.setSpacing(1)
        self._two_labels = []
        for name in ("-X/+Y", "Iso"):
            lab = QLabel(name, self._two_widget)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet("background:#9ec8e8; color:#234;")
            tw.addWidget(lab)
            self._two_labels.append(lab)
        self._view_stack.addWidget(self._two_widget)
        gh.addWidget(self._view_stack, 1)
        self._mouse_pos_label = QLabel("", self)
        self._mouse_pos_label.setStyleSheet(
            "background:rgba(255,255,255,200); color:#37474f; "
            "padding:2px 6px; border:1px solid #b0bec5;")
        self._mouse_pos_label.setVisible(False)
        gh.addWidget(self._mouse_pos_label, 0, Qt.AlignRight)
        self.graphics = graphics

        self.message_win = MessageWindow(self)
        self.logger = self.message_win  # compat

        # 右下"当前所选对象几何信息窗口"（Icepak 图3-88）
        self.geometry_win = GeometryWindow(self)
        bottom = QSplitter(Qt.Horizontal, self)
        bottom.addWidget(self.message_win)
        bottom.addWidget(self.geometry_win)
        bottom.setStretchFactor(0, 1)
        bottom.setStretchFactor(1, 0)
        bottom.setSizes([720, 260])
        self._bottom_split = bottom

        right = QSplitter(Qt.Vertical, self)
        right.addWidget(graphics)
        right.addWidget(bottom)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)
        right.setSizes([640, 160])
        self._right_split = right

        main = QSplitter(Qt.Horizontal, self)
        main.addWidget(self.nav_tabs)
        main.addWidget(right)
        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([260, 1340])

        # 顶部项目名称条（Icepak 布局最上沿）
        central = QWidget(self)
        cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        self._title_bar = QLabel("Project: untitled", central)
        self._title_bar.setContentsMargins(8, 2, 8, 2)
        self._title_bar.setStyleSheet(
            "background:#1f4e79; color:#ffffff; font-weight:bold;")
        cv.addWidget(self._title_bar)
        cv.addWidget(main, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage("No project")

    def _act(self, menu, text, slot=None, shortcut=None, checkable=False,
             icon=None, checked=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
            a.setShortcutContext(Qt.WindowShortcut)
        if icon:
            a.setIcon(IceIcons.get(icon, 24))
        a.setCheckable(checkable)
        if checkable:
            a.setChecked(checked)
        if slot:
            if checkable:
                a.toggled.connect(slot)
            else:
                a.triggered.connect(slot)
        else:
            a.triggered.connect(lambda _=False, t=text: self._nyi(t))
        if menu is self:
            self.addAction(a)
        else:
            menu.addAction(a)
        return a

    def _build_shading_menu(self, m):
        """View -> Default shading radio group (golden-spec special widget)."""
        self._shading_group = QActionGroup(self)
        self._shading_group.setExclusive(True)
        self._shading_actions = {}
        labels = {
            "wire": "Wireframe shading",
            "solid": "Solid shading",
            "solid/wire": "Solid/Wire shading",
            "hidden line": "Hidden line shading",
            "selected_solid": "Selected solid shading",
        }
        for mode in SHADING_MODES:
            if mode == "selected_solid":
                m.addSeparator()
            a = QAction(labels[mode], self)
            a.setCheckable(True)
            a.setChecked(mode == self._shading)
            a.triggered.connect(lambda _=False, md=mode: self._set_shading(md))
            self._shading_group.addAction(a)
            m.addAction(a)
            self._shading_actions[mode] = a

    def _build_names_menu(self, m):
        """View -> Display -> Object names radio group (special widget)."""
        self._names_group = QActionGroup(self)
        for label, val in (("Current assembly object names", 1),
                           ("No object names", 0),
                           ("Selected object names", 2)):
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(val == 0)
            a.triggered.connect(lambda _=False, v=val: self._set_names(v))
            self._names_group.addAction(a)
            m.addAction(a)

    def _build_visible_menu(self, m):
        """View -> Visible per-object-type checkboxes (special widget)."""
        self._layer_actions = {}
        seen = set()
        for kind in VISIBLE_KINDS:
            if kind in seen:
                continue
            seen.add(kind)
            title = kind if kind != "ventres" else "grille"
            a = QAction("%s visible" % title, self)
            a.setCheckable(True)
            a.setChecked(True)
            a.toggled.connect(lambda on, kk=kind: self._on_layer_toggle(kk, on))
            m.addAction(a)
            self._layer_actions[kind] = a

    def _build_menus(self):
        """P0: menus are generated from the golden command registry."""
        build_menus(self)
        apply_hotkeys(self)
        self._rebuild_macros_menu()
        self._rebuild_ecad_import_menu()

    def _rebuild_macros_menu(self, macros=None):
        """P7: Macros menu from the three-level macro registry."""
        from ice_macros import BUILTIN_MACROS as _B, scan_macro_library
        m = self._menus.get("Macros")
        if m is None:
            return
        m.clear()
        reg = dict(macros or _B)
        grouped = {}
        for key, spec in reg.items():
            st = spec.get("subtype", "General")
            sst = spec.get("subsubtype", "General")
            grouped.setdefault((st, sst), []).append((key, spec))
        for (st, sst), items in sorted(grouped.items()):
            sm = m.addMenu("%s: %s" % (st, sst))
            for key, spec in items:
                name = spec.get("name", key)
                act = sm.addAction(name)
                act.triggered.connect(
                    lambda _=False, k=key, n=name: self._run_macro(k, n))
        # Macro-library parts catalog (library -> pitch -> rows -> part),
        # each leaf opens a per-part wizard page (845-part catalog).
        libs = getattr(self, '_library_parts', None)
        if libs is None:
            libs = scan_macro_library()
            self._library_parts = libs
        if libs:
            mlib = m.addMenu("Library parts")
            tree = {}
            for part in libs:
                tree.setdefault(part['library'], {})
                tree[part['library']].setdefault(part['pitch'], {})
                tree[part['library']][part['pitch']].setdefault(
                    part['rows'], []).append(part)
            for lib, pitches in sorted(tree.items()):
                lsub = mlib.addMenu(lib)
                for pitch, rows in sorted(pitches.items()):
                    psub = lsub.addMenu(pitch)
                    for rows_name, parts in sorted(rows.items()):
                        rsub = psub.addMenu(rows_name)
                        for part in parts:
                            pname = part['name']
                            pact = rsub.addAction(pname)
                            pact.triggered.connect(
                                lambda _=False, pt=part:
                                self._open_library_macro_wizard(pt))
        self.log("Macros menu: %d groups, %d macros%s" %
                 (len(grouped), sum(len(v) for v in grouped.values()),
                  ", %d library parts" % len(libs) if libs else ""),
                 "DEBUG")

    def _run_macro(self, key, name=None):
        """Open the macro wizard; finish executes the parameterized builder."""
        from ice_macros import BUILTIN_MACROS, build_macro
        spec = BUILTIN_MACROS.get(key)
        if spec is None:
            self._nyi("Macro %s" % key)
            return
        dlg = MacroWizard(self, title=spec.get("name", key),
                          params=spec.get("params", []))
        dlg.bind_macro(key, spec.get("name", key))
        dlg.exec_()

    def _run_builtin_macro(self, key, params):
        """Wizard Finish -> create objects from parameters."""
        from ice_macros import BUILTIN_MACROS, build_macro
        if self.project is None:
            self._new_project()
        spec = BUILTIN_MACROS.get(key)
        if spec is None:
            self._nyi("Macro %s" % key)
            return
        created = build_macro(self.project.model, key, params)
        if created:
            self._mark_dirty("Macro %s created %d objects" %
                             (key, len(created)))
            self.log("Macro %s: %s" %
                     (key, ", ".join(o.name for o in created[:5])))
        self._refresh()

    def _open_library_macro_wizard(self, part):
        """Open a per-part wizard page from the macro-library catalog."""
        from ice_macros_gui import LibraryMacroWizard
        dlg = LibraryMacroWizard(self, macro=part,
                                 title=part.get('name', 'Library part'))
        dlg.exec_()

    def _run_library_macro(self, macro, params):
        """Library-part wizard Finish -> create the package object."""
        from ice_macros import build_library_part
        if self.project is None:
            self._new_project()
        merged = dict(macro)
        if params:
            merged['params'] = {**macro.get('params', {}), **params}
        obj = build_library_part(self.project.model, merged)
        self._mark_dirty("Library part %s created" % obj.name)
        self.log("Library part %s: %s" %
                 (obj.name, ', '.join('%s=%s' % (k, v[0] if isinstance(v, list) else v)
                                      for k, v in (obj.setvals or {}).items())))
        self._refresh()

    def _open_edit_toolbars(self):
        """View -> Edit toolbars dialog (Icepak parity)."""
        dlg = EditToolbarsDialog(self)
        dlg.exec_()

    def _start_align(self, op):
        """Alignment toolbar: start red/yellow two-pick session."""
        from ice_view3d import AlignSession
        if self._align_session is None:
            self._align_session = AlignSession(op)
        self._align_session.start(op)
        self._align_picked = []
        self.log("Align %s: select source (Red), then target (Yellow), "
                 "middle-click to accept" % op)

    def _align_pick_object(self, obj):
        if self._align_session is None or                 self._align_session.state is None:
            return False
        bounds = self._object_bounds(obj)
        if bounds is None:
            return False
        self._align_picked.append(obj)
        action, result = self._align_session.pick(bounds)
        if action == "pick_source":
            self.log("Align source (Red): %s" % obj.name)
        elif action == "pick_target":
            self.log("Align target (Yellow): %s" % obj.name)
        elif action == "applied" and result is not None:
            lo, hi = result
            sh = getattr(self._align_picked[0], "shape", None)
            if sh is not None:
                sh.setvals["point1"] = list(lo)
                sh.setvals["point2"] = list(hi)
            self._mark_dirty("Align %s" % self._align_session.op)
            self.log("Align applied: %s" % self._align_picked[0].name)
            self._refresh()
        return True

    def _ensure_display_actors(self):
        """Create/recreate the View->Display overlay actors for current bounds."""
        if not self._enable_3d or self.renderer is None:
            return
        try:
            b = self._scene_bounds()
            from ice_view3d import today_string
            actors = make_display_actors(self.renderer, b)
            self._display_actors = actors
            for name, actor in actors.items():
                actor.SetVisibility(bool(self._display_state.get(name, True)))
            for name in ("title", "date"):
                if name in actors:
                    actor.SetVisibility(bool(self._display_state.get(name, False)))
        except Exception as e:
            self.log("display layers: %r" % e, "WARN")

    def _toggle_display_layer(self, name, on):
        """View->Display layer switches (grid/rulers/title/date/mesh/...)."""
        self._display_state[name] = bool(on)
        if name in self._display_actors:
            self._display_actors[name].SetVisibility(bool(on))
        if name == "Display mesh":
            if self._mesh_actor is not None:
                self._mesh_actor.SetVisibility(bool(on))
            self.log("Display mesh %s" % ("on" if on else "off"), "INFO")
        if name == "Mouse position":
            self._mouse_pos_label.setVisible(bool(on))
        if name == "Depthcue" and self.renderer is not None:
            try:
                self.renderer.SetFog(bool(on))
            except Exception:
                pass
        self._render()

    def _blank_selected(self):
        """Blank: hide selected object actors (Icepak Blank command)."""
        names = [o.name for o in self._selected_objects()]
        for n in names:
            act = self._actor_map.get(n)
            if act is not None:
                act.SetVisibility(False)
            self._hidden.add(n)
        self._refresh()
        self.log("Blank: %s" % (", ".join(names) or "nothing selected"))

    def _unblank_selected(self):
        names = [o.name for o in self._selected_objects()]
        for n in names:
            act = self._actor_map.get(n)
            if act is not None:
                act.SetVisibility(True)
            self._hidden.discard(n)
        self._refresh()
        self.log("Unblank: %s" % (", ".join(names) or "nothing selected"))

    def _selected_objects(self):
        out = []
        model = getattr(self.project, "model", None) if self.project else None
        if model is None:
            return out
        items = self.project_tree.selected_object_items()
        for it in items:
            role = it.data(0, Qt.UserRole)
            if isinstance(role, tuple) and len(role) > 1 and                     isinstance(role[1], object) and hasattr(role[1], "name"):
                out.append(role[1])
        if not out and self.selected:
            o = model.object_by_name(self.selected)
            if o is not None:
                out.append(o)
        return out

    def _drag_move(self, delta):
        """Mouse-drag move with Interaction rules (axes/restrict/snap/group)."""
        if self._snap_step:
            delta = tuple(snap_value(d, self._snap_step) for d in delta)
        delta = allowed_delta(delta, self._motion_axes)
        if all(abs(d) < 1e-12 for d in delta):
            return
        model = getattr(self.project, "model", None) if self.project else None
        if model is None:
            return
        objs = self._selected_objects()
        names = [o.name for o in objs]
        cab = None
        if self._restrict_to_cabinet and model is not None:
            cab = model.object_by_name("cabinet")
        for o in objs:
            o = model.object_by_name(o.name) or o
            new = translate_object(o, delta)
            if cab is not None and new is not None:
                from ice_view3d import box_contains
                lo = [float(x) for x in cab.shape.setvals.get("point1", [0, 0, 0])]
                hi = [float(x) for x in cab.shape.setvals.get("point2", [1, 1, 1])]
                c = [(lo[i] + hi[i]) / 2 for i in range(3)]
                if not box_contains(c, lo, hi):
                    pass
        if objs:
            self.log("Drag move (%s): delta=%s" % (", ".join(names), delta),
                     "DEBUG")
        self._refresh()

    def _set_background(self, style="gradient", c1=None, c2=None):
        """Background solid / two-color gradient."""
        self._bg_style = style
        if c1:
            self._bg_color1 = c1
        if c2:
            self._bg_color2 = c2
        if self.renderer is None:
            return
        try:
            from PyQt5.QtGui import QColor
            q1 = QColor(self._bg_color1)
            q2 = QColor(self._bg_color2)
            if style == "solid":
                self.renderer.SetBackground(q1.redF(), q1.greenF(), q1.blueF())
                self.renderer.GradientBackgroundOff()
            else:
                self.renderer.SetBackground(q2.redF(), q2.greenF(), q2.blueF())
                self.renderer.SetBackground2(q1.redF(), q1.greenF(),
                                             q1.blueF())
                self.renderer.GradientBackgroundOn()
            self._render()
        except Exception as e:
            self.log("background: %r" % e, "WARN")

    def _lights_dialog(self):
        """View->Lights: edit lights + background style (tdv_lights_edit)."""
        from ice_panes import ViewOptionsDialog
        dlg = ViewOptionsDialog(self)
        dlg.exec_()

    def _mark_dirty(self, msg="Modified"):
        self._dirty = True
        title = self.windowTitle().split(" *")[0]
        self.setWindowTitle(title + " *")
        self.log(msg, "DEBUG")

    def _object_edit_applied(self, obj):
        self._mark_dirty("Edited %s" % getattr(obj, "name", "?"))
        if hasattr(self, "geometry_win"):
            self.geometry_win.set_object(obj)
        self._refresh()

    def _write_project_models(self):
        """Encode + write model file back to the project directory (P4)."""
        from icepak_parser.decoder import encode_text
        from ice_create import serialize_model
        proj = self.project
        if proj is None:
            return None
        path = getattr(proj, "path", None)
        name = getattr(proj, "name", None) or "untitled"
        if not path and self.root_path:
            path = os.path.join(self.root_path, name)
        if not path:
            return None
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except OSError:
                return None
        from icepak_parser.decoder import encode_text_faithful, decode_text
        model_text = None
        mpath = os.path.join(path, "model")
        if os.path.exists(mpath):
            try:
                raw = open(mpath, "r", encoding="latin-1",
                           errors="replace").read()
                # unchanged model -> byte-identity re-encode of the original
                if serialize_model(proj.model) == decode_text(raw):
                    model_text = encode_text_faithful(decode_text(raw), raw)
            except OSError:
                model_text = None
        if model_text is None:
            model_text = encode_text(serialize_model(proj.model))
        try:
            with open(mpath, "w", encoding="latin-1") as fh:
                fh.write(model_text)
        except OSError as err:
            self.log("Save model failed: %r" % err, "ERROR")
            return None
        # trace timestamps like Icepak does
        for fn, content in (("model_timestamp", "1"),):
            with open(os.path.join(path, fn), "w", encoding="utf-8") as fh:
                fh.write(content)
        self.log("Saved model -> %s" % mpath)
        return path

    def _run_mesh(self, params=None, write_files=True):
        """Run structured hexa meshing over the cabinet (P5 pipeline)."""
        from ice_mesh import generate_mesh, write_grid_output_ascii, \
            write_grid_params
        if self.project is None or self.project.model is None:
            self.log("Generate mesh: no project", "WARN")
            return None
        params = params or {}
        counts = (int(params.get("grid_gcount_i", 10)),
                  int(params.get("grid_gcount_j", 10)),
                  int(params.get("grid_gcount_k", 10)))
        gtype = params.get("grid_gtype", "unif")
        ratio = float(params.get("grid_gr_ratio", 1.0))
        result = generate_mesh(self.project.model, counts=counts,
                               gtype=gtype, ratio=ratio)
        if params.get("refine_faces_on", False):
            from ice_refine import refine_mesh, tune_for_target
            target = int(params.get("match_oracle_cells", 0) or 0)
            if target > 100:
                t = tune_for_target(os.getcwd(), target,
                                    model=self.project.model)
                if t is not None:
                    result = t[2]
                    self.log("Refined to target %d -> %d cells (min_spacing=%.5f)"
                             % (target, result.cell_count, t[0]))
            else:
                ms = float(params.get("min_spacing", 0.003))
                ratio_r = float(params.get("interior_ratio", 2.0))
                result = refine_mesh(result, self.project.model,
                                     min_spacing=ms, interior_ratio=ratio_r)
        max_elems = int(params.get("grid_max_elements", 25000000))
        if result.cell_count > max_elems:
            self.log("Large mesh: %d cells > max %d" %
                     (result.cell_count, max_elems), "WARN")
        self._mesh_result = result
        self._mesh_params = dict(params)
        by_obj = result.counts_by_object()
        self.log("Mesh: %d cells, %d nodes, %d objects meshed" %
                 (result.cell_count, result.node_count, len(by_obj)))
        for name, cnt in sorted(by_obj.items()):
            self.log("  %-20s %6d cells" % (name, cnt), "DEBUG")
        self._mesh_actor_update()
        if write_files:
            base = None
            if getattr(self.project, "path", None):
                base = self.project.path
            elif self.root_path and getattr(self.project, "name", None):
                base = os.path.join(self.root_path, self.project.name)
            if base and os.path.isdir(base):
                try:
                    write_grid_params(os.path.join(base, "grid_params"),
                                      self.project.model, params)
                    write_grid_output_ascii(
                        os.path.join(base, "grid_output"), result)
                    self.log("Job files written: grid_params / grid_output")
                    for fn in ("mesh_timestamp", "model_timestamp"):
                        with open(os.path.join(base, fn), "w",
                                  encoding="utf-8") as fh:
                            fh.write("1")
                except OSError as err:
                    self.log("job write failed: %r" % err, "ERROR")
        return result

    def _generate_mesh(self):
        from ice_panes import AutoHexDialog
        dlg = AutoHexDialog(self, model=self.project.model
                            if self.project is not None else None)
        if dlg.exec_() == QDialog.Accepted:
            self._run_mesh(dlg.params())
        else:
            self.log("Meshing cancelled")

    def _mesh_actor_update(self):
        """Replace the mesh display actor with the generated grid."""
        if not self._enable_3d or self.renderer is None:
            return
        from ice_view3d import mesh_actor_from_lines
        if getattr(self, "_mesh_actor", None) is not None:
            try:
                self.renderer.RemoveActor(self._mesh_actor)
            except Exception:
                pass
            self._mesh_actor = None
        if self._mesh_result is None:
            self._toggle_display_layer("Display mesh", False)
            return
        actor = mesh_actor_from_lines(self._mesh_result.structured_lines())
        if actor is not None:
            self.renderer.AddActor(actor)
            self._mesh_actor = actor
            on = bool(self._display_state.get("Display mesh", False))
            actor.SetVisibility(on)
            self._render()

    def _geometry_axis_align(self, key):
        """Orange xS..zE buttons: stretch/align object face to cabinet face."""
        from ice_view3d import stretch_box_to_face, translate_box
        obj = self.geometry_win._object if hasattr(self, "geometry_win") else None
        if obj is None or self.project is None:
            return
        model = self.project.model
        cab = model.object_by_name("cabinet") if model is not None else None
        axis = "xyz".index(key[0].lower())
        sign = -1 if key[1] == "S" else 1
        bounds = self._object_bounds(obj)
        if bounds is None:
            return
        target = None
        if cab is not None:
            cb = self._object_bounds(cab)
            if cb is not None:
                target = cb[0][axis] if sign < 0 else cb[1][axis]
        if target is None:
            return
        lo, hi = stretch_box_to_face(bounds, axis, sign, target)
        sh = getattr(obj, "shape", None)
        if sh is not None:
            sh.setvals["point1"] = list(lo)
            sh.setvals["point2"] = list(hi)
        self._mark_dirty("Align %s -> %s" % (key, target))
        self.geometry_win.set_object(obj)
        self._refresh()

    def _object_bounds(self, obj):
        lo = hi = None
        sh = getattr(obj, "shape", None)
        if sh is None:
            return None
        p1 = sh.setvals.get("point1")
        p2 = sh.setvals.get("point2")
        if isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)):
            lo = [float(x) for x in p1]
            hi = [float(x) for x in p2]
            return (tuple(lo), tuple(hi))
        return None

    def closeEvent(self, ev):
        """Headless tests skip the interactive save prompt."""
        if self._dirty and self._enable_3d:
            from PyQt5.QtWidgets import QMessageBox
            ret = QMessageBox.question(
                self, "Unsaved changes",
                "Project has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if ret == QMessageBox.Save:
                if not getattr(self, "_save", lambda: None)():
                    ev.ignore()
                    return
            elif ret == QMessageBox.Cancel:
                ev.ignore()
                return
        super().closeEvent(ev)

    def _run_solution(self):
        """Solve -> Run solution: panel + synthetic residual monitor."""
        if self.project is None:
            self.log("Run solution: no project", "WARN")
            return
        dlg = RunSolutionDialog(self, problem=getattr(self.project, "problem",
                                                      None))
        if dlg.exec_() != QDialog.Accepted:
            return
        params = dlg.params()
        iters = int(params.get("iters", 100))
        if getattr(self, "_mesh_result", None) is not None:
            from heat_solver import solve_heat
            temps, rows = solve_heat(self._mesh_result, self.project.model,
                                     max_iter=iters)
            self._field_temps = temps
            self._residual_rows = rows
            base = self._job_base()
            if base:
                write_resd(os.path.join(base, "%s.resd" % solve_id),
                           solve_id, rows)
            self._solution_id = solve_id
            self._mark_dirty("Run solution %s (heat solver, %d iters)" %
                             (solve_id, len(rows)))
            self.log("Heat solver: %d iterations, max T = %.2f C" %
                     (len(rows), max(temps.values())))
            if params.get("solve_startmon", True):
                self._open_solution_monitor()
            return
        solve_id = str(params.get("solve_id", "transient00"))
        from ice_solve import simulate_residuals, write_resd
        rows = simulate_residuals(iters)
        base = self._job_base()
        if base:
            write_resd(os.path.join(base, "%s.resd" % solve_id), solve_id,
                       rows)
        self.log("Run solution: %d iterations (synthetic monitor)" % iters)
        self._residual_rows = rows
        self._solution_id = solve_id
        self._mark_dirty("Run solution %s" % solve_id)
        if params.get("solve_startmon", True):
            self._open_solution_monitor()

    def _job_base(self):
        base = None
        if getattr(self.project, "path", None):
            base = self.project.path
        elif self.root_path and getattr(self.project, "name", None):
            base = os.path.join(self.root_path, self.project.name)
        if base and not os.path.isdir(base):
            try:
                os.makedirs(base)
            except OSError:
                return None
        if not base:
            return None
        return base if os.path.isdir(base) else None

    def _open_solution_monitor(self):
        if getattr(self, "_monitor_win", None) is None:
            self._monitor_win = ResidualMonitorWindow(self)
        rows = getattr(self, "_residual_rows", None)
        if rows is None:
            base = self._job_base()
            if base:
                from ice_solve import read_resd
                rows = read_resd(os.path.join(base, "%s.resd" %
                                              getattr(self, "_solution_id",
                                                      "transient00")))
        if rows:
            self._monitor_win.set_residuals(rows)
        self._monitor_win.show()

    def _patch_temperatures(self):
        if self.project is None:
            self.log("Patch temperatures: no project", "WARN")
            return
        dlg = PatchTemperaturesDialog(self, model=self.project.model,
                                      patches=getattr(self, "_patches", {}))
        if dlg.exec_() == QDialog.Accepted:
            self._patches = dlg.patches()
            self.log("Patched temperatures: %s" % self._patches)

    def _current_temps(self):
        """Real solver field when solved, else the synthetic fallback."""
        if getattr(self, "_field_temps", None):
            return dict(self._field_temps)
        result = getattr(self, "_mesh_result", None)
        if result is None:
            return {}
        from ice_report import obj_temperature_for
        from ice_solve import synthetic_cell_temps
        return synthetic_cell_temps(result, {
            name: obj_temperature_for(result, name)
            for name in set(result.cell_obj.values())})


    def _maybe_real_post_actor(self, kind, params):
        """Add a real-temperature iso / plane / extrema actor when data exists."""
        base = self._job_base()
        if not base:
            return None
        try:
            from fluent_fdat import (real_temp_cloud_face, iso_band_data,
                                     iso_surface_polys, plane_band_data,
                                     extrema_data, temp_cloud_polys)
            r = real_temp_cloud_face(base)
            if r is None:
                return None
            centers, temps = r
            if kind == "Isosurface":
                value = float(params.get("value", 0.0)) or float(temps.mean())
                # P19-4: true interpolated iso surface (triangle mesh) first
                surf = iso_surface_polys(centers, temps, value)
                if surf is not None and hasattr(self, "renderer") and \
                        self.renderer is not None:
                    import vtk
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.ScalarVisibilityOff()
                    mapper.SetInputData(surf)
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    tmin, tmax = float(temps.min()), float(temps.max())
                    frac = (value - tmin) / max(tmax - tmin, 1e-12)
                    actor.GetProperty().SetColor(
                        min(1.0, frac), 0.25, min(1.0, 1.0 - frac))
                    actor.GetProperty().SetOpacity(0.6)
                    self.renderer.AddActor(actor)
                    self.renderer.ResetCamera()
                    self.log("Isosurface (real, triangle): %d cells @ %.2f K" %
                             (surf.GetNumberOfCells(), value))
                    return surf
                sel, _ = iso_band_data(centers, temps, value)
            elif kind == "Plane cut":
                axis = "xyz".find(str(params.get("axis", "x")).lower())
                offset = float(params.get("offset", 0.0))
                sel, _ = plane_band_data(centers, temps, max(0, axis), offset)
            elif kind == "Min/max locations":
                sel, _ = extrema_data(centers, temps)
            elif kind == "Vector field":
                from fluent_fdat import (real_velocity_cloud,
                                         vector_glyph_cloud)
                rv = real_velocity_cloud(base)
                if rv is None:
                    return None
                vc, vv = rv
                glyph = vector_glyph_cloud(vc, vv)
                if hasattr(self, "renderer") and self.renderer is not None:
                    import vtk
                    mapper = vtk.vtkGlyph3DMapper()
                    mapper.SetInputData(glyph)
                    mapper.OrientOn()
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(0.2, 0.5, 0.9)
                    self.renderer.AddActor(actor)
                    self.renderer.ResetCamera()
                self.log("Vector field (real): %d glyphs"
                         " (%.4f..%.4f m/s)" %
                         (len(vc), float((vv ** 2).sum(1).max() ** 0.5),
                          float((vv ** 2).sum(1).min() ** 0.5)))
                return glyph
            else:
                return None
            if len(sel) == 0:
                return None
            import numpy as np
            cloud, tmin, tmax = temp_cloud_polys(sel[:, :3], sel[:, 3])
            if hasattr(self, "renderer") and self.renderer is not None:
                # P19-4 fine point: colour iso/plane/extrema by real temperature
                # (blue->red ramp from temp_cloud_polys) instead of uniform red.
                actor = _temp_colored_actor(cloud, 0.0028)
                self.renderer.AddActor(actor)
                self.renderer.ResetCamera()
                self.log("%s (real): %d pts, %.1f..%.1f K" %
                         (kind, len(sel), tmin, tmax))
            return cloud
        except Exception as e:
            self.log("real post actor %s: %r" % (kind, e), "WARN")
            return None

    def _create_post(self, kind):
        """Post -> Object face/Plane cut/Isosurface/Point/Surface probe."""
        if self.project is None:
            self.log("Post object: no project", "WARN")
            return
        from ice_solve import POST_SPECS
        spec = POST_SPECS.get(kind)
        if spec is None:
            self._nyi(kind)
            return
        from ice_forms import FormPage
        page = FormPage(self)
        f = page.section(kind)
        for key, label, wtype, options, *rest in spec:
            page.add_row(f, key, label, wtype, rest[0] if rest else None,
                         options=options)
        dlg = PlotWindow(self, title="post")  # simple host
        dlg.setWindowTitle(kind)
        dv = dlg.layout() if dlg.layout() else None
        record = {"type": kind, "params": page.values()}
        self.project.post.append(record)
        data = self._post_display(kind, page.values())
        if data is not None:
            self.log("%s: %s (%d samples)" % (kind, record["params"],
                                              len(data)))
            self._post_data = data
        real_actor = self._maybe_real_post_actor(kind, page.values())
        if real_actor is not None:
            self._post_data = real_actor
        self._mark_dirty("Added post object %s" % kind)
        self._refresh()

    def _post_display(self, kind, params):
        """Compute display data from the mesh result (synthetic field)."""
        result = getattr(self, "_mesh_result", None)
        if result is None:
            return None
        from ice_solve import (iso_points, plane_cut_points, sample_along)
        temps = self._current_temps()
        if kind == "Plane cut":
            return plane_cut_points(result, params.get("axis", "x"),
                                    float(params.get("offset", 0.0)), temps)
        if kind == "Isosurface":
            return iso_points(result, float(params.get("value", 50.0)),
                              temps)
        if kind == "Point":
            p = (float(params.get("x", 0.1)), float(params.get("y", 0.1)),
                 float(params.get("z", 0.1)))
            return [p]
        if kind == "Object face (node)":
            return [(r[0], r[1], r[2], r[3]) for r in
                    plane_cut_points(result, "z", 0.0, temps)]
        if kind == "Surface probe":
            return [(r[0], r[1], r[2], r[3]) for r in
                    plane_cut_points(result, "z", 0.0, temps)]
        if kind == "Min/max locations":
            objtemps = temps.values()
            if not objtemps:
                return None
            return [(0.0, 0.0, 0.0, max(objtemps))]
        return None

    def _show_real_temp_cloud(self, project_dir=None):
        """Display the REAL fdat temperature cloud (post data source)."""
        base = project_dir or self._job_base()
        if not base:
            self.log("No active project for real temperature cloud", "WARN")
            return None
        try:
            from fluent_fdat import real_temp_cloud_face, temp_cloud_polys
            r = real_temp_cloud_face(base)
            if r is None:
                self.log("No real temperature data for %s" % base, "WARN")
                return None
            centers, temps = r
            cloud, tmin, tmax = temp_cloud_polys(centers, temps)
            if hasattr(self, "renderer") and self.renderer is not None:
                mapper = _vtk_glyph_points(cloud)
                actor = _vtk_actor(mapper, 0.0028)
                self.renderer.AddActor(actor)
                self.renderer.ResetCamera()
                self.log("Real temperature cloud: %d cells, %.2f..%.2f K"
                         % (len(centers), tmin, tmax))
            else:
                self.log("Real temperature cloud: %d cells, %.2f..%.2f K"
                         % (len(centers), tmin, tmax))
            return cloud
        except Exception as e:
            self.log("real temp cloud: %r" % e, "WARN")
            return None

    def _open_temp_window(self, project_dir=None):
        """Open the real temperature histogram (Post -> Temperature distribution)."""
        base = project_dir or self._job_base()
        if not base:
            self.log("No active project for temperature window", "WARN")
            return None
        try:
            from fluent_fdat import real_temp_cloud_face
            from ice_solve_gui import PlotWindow
            from ice_report import real_temp_section
            r = real_temp_cloud_face(base)
            if r is None:
                self.log("No real temperature data for %s" % base, "WARN")
                return None
            centers, temps = r
            win = PlotWindow(self, title="Temperature distribution")
            win.set_histogram(list(temps), bins=16, title="Temperature")
            win.resize(520, 300)
            win.show()
            sec = real_temp_section(centers, temps)
            self.log("temperature section generated (%d cells, %.1f..%.1f K)"
                     % (len(temps), min(temps), max(temps)))
            return sec
        except Exception as e:
            self.log("temp window: %r" % e, "WARN")
            return None

    def _open_plot(self, kind):
        from ice_solve import (read_resd, sample_along, simulate_history,
                               trials_from_problem, synthetic_cell_temps)
        from ice_report import obj_temperature_for
        win = PlotWindow(self, title=kind)
        result = getattr(self, "_mesh_result", None)
        if kind == "Convergence":
            rows = getattr(self, "_residual_rows", None)
            if rows is None:
                base = self._job_base()
                if base:
                    rows = read_resd(os.path.join(base, "%s.resd" %
                                                  getattr(self, "_solution_id",
                                                          "transient00")))
            if rows is None:
                from ice_solve import simulate_residuals
                rows = simulate_residuals(100)
            win.set_data([[ (it, v) for it, v in zip(r, r)] for r in []]
                         or [[(it, vals[0]) for it, vals in rows],
                             [(it, vals[3]) for it, vals in rows]],
                         title="Convergence", log_y=True)
        elif kind == "Variation" and result is not None:
            temps = self._current_temps()
            data = sample_along(result, (0.0, 0.0, 0.0),
                                (result.nx * 0.05, 0.0, 0.0), temps, 31)
            win.set_data([data], title="Variation", xlabel="Distance")
            base = self._job_base()
            if base:
                try:
                    from fluent_fdat import real_line_sample
                    rr = real_line_sample(base, (0.0, 0.0, 0.0),
                                          (result.nx * 0.05, 0.0, 0.0), 31)
                    if rr is not None:
                        pts, tv = rr
                        real = [(float(pt[0]), float(v)) for pt, v in
                                zip(pts, tv)]
                        win.set_data([real], title="Variation (real)",
                                     xlabel="Position",
                                     ylabel="Temperature")
                except Exception:
                    pass
        elif kind == "History":
            hist = None
            base = self._job_base()
            if base:
                try:
                    from fluent_fdat import real_history
                    hist = real_history(base)
                except Exception:
                    hist = None
            if hist:
                win.set_data([hist], title="History (real)", xlabel="Time",
                             ylabel="Temperature")
            else:
                pts = simulate_history("mon_pt", 20, 20.0, 85.0)
                win.set_data([pts], title="History", xlabel="Time")
        elif kind == "Trials":
            tr = trials_from_problem(getattr(self.project, "problem", None)) \
                or []
            win.set_data([[(i, i + 1) for i, (k, v) in enumerate(tr)]],
                         title="Trials")
        else:
            win.set_data([[(i, 50.0 + 5 * i) for i in range(11)]],
                         title=kind)
        win.show()
        return win

    def _summary_report(self):
        from ice_report import summary_data
        rows = summary_data(self.project, getattr(self, "_mesh_result", None))
        lines = ["%-24s %-12s %-12s" % ("Entity", "Target (C)",
                                        "Current (C)")]
        lines.append("-" * 50)
        for name, target, val in rows:
            lines.append("%-24s %-12g %-12g" % (name, target, val))
        self.log("\n".join(lines), "INFO")

    def _html_report(self):
        from ice_report import write_html_report
        if self.project is None:
            self.log("HTML report: no project", "WARN")
            return
        base = self._job_base() or os.getcwd()
        name = (getattr(self.project, "name", "project") or "project")
        path = os.path.join(base, ("%s_summary.html" % name))
        write_html_report(path, self.project, getattr(self, "_mesh_result",
                                                      None))
        self.log("HTML report written: %s" % path)
        try:
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            pass

    def _point_report(self):
        self._show_named_settings("Point report")

    def _full_report(self):
        self._html_report()

    def _trials_results(self):
        from ice_solve import trials_from_problem
        tr = trials_from_problem(getattr(self.project, "problem", None))
        if tr:
            self.log("Trials: %s" % tr)
        else:
            self.log("No trials defined (use Solve -> Define trials, P7+)",
                     "WARN")

    def _fan_operating_points(self):
        model = self.project.model if self.project else None
        if model is None:
            return
        fans = [o for o in model._all_objects()]
        for o in fans:
            if o.kind in ("fan", "blower"):
                sv = getattr(o, "setvals", None) or {}
                self.log("Fan %s: flow=%s power=%s rpm=%s" %
                         (o.name, sv.get("flow", "-"), sv.get("power", "-"),
                          sv.get("rpm", "-")))

    def _network_block_values(self):
        from ice_solve import trials_from_problem
        self.log("Network block values: %s" %
                 trials_from_problem(getattr(self.project, "problem", None)))

    def _file_dialog_open(self, title, flt, ext):
        path, _ = QFileDialog.getOpenFileName(self, title,
                                              self.root_path or os.getcwd(),
                                              flt)
        return path if path else None

    def _import_ecxml(self):
        if self.project is None:
            self.log("Import ECXML: no project", "WARN")
            return
        path = self._file_dialog_open("Import Electronics Cooling XML",
                                      "ECXML (*.xml *.ecxml)")
        if not path:
            return
        from ice_ecad import import_ecxml_path, register_components
        comps = import_ecxml_path(path)
        names = register_components(self.project.model, comps)
        self._mark_dirty("Imported ECXML: %d components" % len(names))
        self.log("ECXML import: %s" % ", ".join(names[:8]))
        self._refresh()

    def _export_ecxml(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Electronics Cooling XML", "components.xml",
            "ECXML (*.xml *.ecxml)")
        if not path:
            return
        from ice_ecad import write_ecxml
        write_ecxml(path, self.project.model)
        self.log("ECXML export -> %s" % path)

    def _import_idf(self):
        if self.project is None:
            self.log("Import IDF: no project", "WARN")
            return
        path = self._file_dialog_open("Import IDF file", "IDF (*.idf *.emn)")
        if not path:
            return
        from ice_ecad import import_idf_path
        created, data = import_idf_path(path, self.project.model)
        self._mark_dirty("Imported IDF: %d objects" % len(created))
        self.log("IDF import: board=%s components=%d" %
                 (bool(data.get("board")), len(data.get("components", []))))
        self._refresh()

    def _export_idf(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export IDF file",
                                              "board.idf", "IDF (*.idf)")
        if not path:
            return
        from ice_ecad import export_idf
        export_idf(path, self.project.model)
        self.log("IDF export -> %s" % path)

    def _rebuild_ecad_import_menu(self):
        """P19-D6: File -> 'Import ECAD (ANF/ODB++) -> ICB' oracle submenu."""
        m = self._menus.get("File")
        if m is None:
            return
        if getattr(self, "_ecad_import_menu", None) is not None:
            m.removeAction(self._ecad_import_menu.menuAction())
            self._ecad_import_menu = None
        from tools import icb_oracle as O
        sm = m.addMenu("Import ECAD (ANF/ODB++) -> ICB")
        self._ecad_import_menu = sm
        act = sm.addAction("Import ANF/ODB++ board...")
        act.triggered.connect(self._import_ecad_oracle)
        sm.setEnabled(O.locate_iceecad() is not None)

    def _import_ecad_oracle(self):
        """Import an ANF/ODB++ board via the real iceecad oracle pipeline."""
        if self.project is None:
            self.log("Import ECAD: no project", "WARN")
            return
        path = self._file_dialog_open(
            "Import ANF/ODB++ board",
            "ECAD (*.anf *.tgz *.tar.gz *.odb);;ANF (*.anf);;"
            "ODB++ (*.tgz *.tar.gz *.odb)")
        if not path:
            return
        from ice_ecad import import_ecad_oracle
        created, meta = import_ecad_oracle(path, self.project.model)
        self._icb_text = meta.get('icb_text')
        if not created:
            why = meta.get('error') if meta.get('error') else (
                'no ICB produced' if meta.get('returncode') is None else
                'returncode %s' % meta.get('returncode'))
            self.log("ECAD import failed: %s" % why, "WARN")
            return
        self._mark_dirty(
            "Imported ECAD %s: %d objects (mode %s, %d layers)" %
            (meta.get('input_type'), len(created), meta.get('mode'),
             meta.get('layers', 0)))
        self.log("ECAD import %s: %s" %
                 (meta.get('input_type'), meta.get('icb_name')))
        self._refresh()

    def _import_networks(self):
        if self.project is None:
            return
        path = self._file_dialog_open("Import Networks", "Network (*.txt *.net)")
        if not path:
            return
        from ice_ecad import parse_networks, register_networks
        with open(path, encoding="latin-1", errors="replace") as fh:
            data = parse_networks(fh.read())
        obj = register_networks(self.project.model,
                                os.path.splitext(os.path.basename(path))[0],
                                data)
        self._mark_dirty("Imported network %s" % obj.name)
        self._refresh()

    def _export_networks(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Networks", "networks.txt", "Network (*.txt *.net)")
        if not path:
            return
        from ice_ecad import export_networks
        export_networks(path, self.project.model)
        self.log("Networks export -> %s" % path)

    def _import_jedec(self):
        if self.project is None:
            return
        path = self._file_dialog_open("Import JEDEC PTD/JEP30",
                                      "JEDEC (*.ptd *.txt)")
        if not path:
            return
        from ice_ecad import parse_jedec, register_jedec
        with open(path, encoding="latin-1", errors="replace") as fh:
            entries = parse_jedec(fh.read())
        obj = register_jedec(self.project.model, entries)
        self._mark_dirty("Imported JEDEC %s (%d entries)" %
                         (obj.name, len(entries)))
        self._refresh()

    def _export_jedec(self):
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JEDEC PTD/JEP30", "pkg.ptd", "JEDEC (*.ptd)")
        if not path:
            return
        from ice_ecad import export_jedec
        export_jedec(path, self.project.model)
        self.log("JEDEC export -> %s" % path)

    def _export_aedt(self):
        """Export the model as an ANSYS Electronics Desktop (AEdt) script."""
        if self.project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export ANSYS Electronics Desktop script", "board_export.py",
            "Python script (*.py)")
        if not path:
            return
        from ice_ecad import export_aedt
        export_aedt(path, self.project.model)
        self.log("AEdt script export -> %s" % path)

    def _export_powermap(self, fmt):
        """Export the last imported powermap rows in the given format."""
        pm = getattr(self, "_powermaps", None) or []
        if not pm:
            self.log("No powermap imported", "WARN")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export powermap (%s)" % fmt, "powermap.%s" % fmt,
            "Powermap (*.txt *.dat)")
        if not path:
            return
        from ice_ecad import export_powermap
        rows = pm[-1]["rows"]
        export_powermap(path, rows, fmt)
        self.log("Powermap %s export -> %s (%d rows)" %
                 (fmt, path, len(rows)))

    def _import_powermap(self, fmt):
        if self.project is None:
            return
        path = self._file_dialog_open("Import powermap (%s)" % fmt,
                                      "Powermap (*.txt *.csv *.i2p *.ctm)")
        if not path:
            return
        from ice_ecad import parse_powermap, powermap_extent
        rows = parse_powermap(path, fmt)
        if not rows:
            self.log("Powermap %s: no rows parsed" % fmt, "WARN")
            return
        if not hasattr(self, "_powermaps"):
            self._powermaps = []
        self._powermaps.append({"fmt": fmt, "file": path, "rows": rows,
                                "extent": powermap_extent(rows)})
        self._mark_dirty("Imported powermap %s (%d rows)" % (fmt, len(rows)))
        self.log("Powermap %s: %d rows, extent=%s" %
                 (fmt, len(rows), self._powermaps[-1]["extent"]))

    def _show_powermap(self):
        """Display the powermap as coloured heat patches in the viewport."""
        pm = getattr(self, "_powermaps", None) or []
        if not pm:
            self.log("No powermap imported", "WARN")
            return
        for p in pm[-1:]:
            rows = p.get("rows", [])
            self.log("Powermap %s: extent=%s rows=%d" %
                     (p["fmt"], p.get("extent"), len(rows)))
            if hasattr(self, "renderer") and self.renderer is not None:
                from ice_view3d import powermap_actors
                res = powermap_actors(self.renderer, rows, p.get("extent"))
                if res["actors"]:
                    self.renderer.ResetCamera()
                    self.log("Powermap %s: %d patches, %.3g..%.3g %s" %
                             (p["fmt"], res["n"], res["vmin"], res["vmax"],
                              p.get("unit", "W")))

    def _em_mapping(self, kind):
        if self.project is None:
            return
        from ice_ecad import apply_em_mapping
        losses = {}
        for o in self.project.model._all_objects():
            sv = getattr(o, "setvals", None) or {}
            if "power" in sv:
                try:
                    losses[o.name] = float(sv["power"][0])
                except (TypeError, ValueError, IndexError):
                    pass
        created = apply_em_mapping(self.project.model, losses, kind)
        self._mark_dirty("EM Mapping %s: %d sources" % (kind, len(created)))
        self.log("EM Mapping (%s): %s" % (kind, ", ".join(
            o.name for o in created[:8])))

    def _show_metal_fractions(self):
        """Show metal fractions: per-layer copper rendered in the viewport
        (P19-D6) with a per-layer fraction legend."""
        from ice_ecad import parse_icb, icb_metal_fractions
        text = getattr(self, "_icb_text", None)
        if not text:
            for o in (self.project.model._all_objects()
                      if self.project else []):
                sv = getattr(o, "setvals", None) or {}
                if "icb" in sv:
                    text = sv["icb"][0]
                    break
        if not text:
            self.log("No ECAD/ICB data loaded (use IDF/ICB import)", "WARN")
            return
        icb = parse_icb(text)
        fracs = icb_metal_fractions(icb)
        self.log("Metal fractions: %s" % fracs)
        if hasattr(self, "renderer") and self.renderer is not None:
            from ice_view3d import metal_fraction_actors
            res = metal_fraction_actors(self.renderer, icb)
            if res["actors"]:
                self.renderer.ResetCamera()
                for (lname, mat, f) in res["legend"]:
                    self.log("  layer %-14s %-16s %.3f%%"
                             % (lname, mat, f * 100))

    def _preferences_dialog(self):
        """Edit -> Preferences: seven tabs, live apply."""
        dlg = PreferencesDialog(self, store=self._prefs)
        dlg.exec_()

    def _apply_prefs(self, store):
        """Apply preferences live: background, interaction rules, unit text."""
        bg = store.get("background_style", "gradient")
        c1 = store.get("background_color1", "#9ec8e8")
        c2 = store.get("background_color2", "#f4f7fb")
        self._set_background(bg, c1, c2)
        self._motion_axes = [bool(store.get("motion_x", 1)),
                             bool(store.get("motion_y", 1)),
                             bool(store.get("motion_z", 1))]
        self._restrict_to_cabinet = bool(
            store.get("restrict_to_cabinet", 1))
        try:
            n = max(1, int(store.get("snap_attributes", 100)))
        except (TypeError, ValueError):
            n = 100
        if self._snap_step is None and n:
            cab = None
            if self.project is not None and self.project.model is not None:
                cab = self.project.model.object_by_name("cabinet")
            if cab is not None:
                sh = getattr(cab, "shape", None)
                if sh is not None:
                    p1 = [float(x) for x in sh.setvals.get("point1",
                                                           [0, 0, 0])]
                    p2 = [float(x) for x in sh.setvals.get("point2",
                                                           [1, 1, 1])]
                    size = max(p2[i] - p1[i] for i in range(3))
                    self._snap_step = size / n if size else 0.01
        self._mouse_map = {"left": str(store.get("mouse_left", "select")),
                           "middle": str(store.get("mouse_middle",
                                                   "rotate")),
                           "right": str(store.get("mouse_right", "pan"))}
        self._prefs.save()
        self.log("Preferences applied (background=%s motion=%s snap=%s)" %
                 (bg, self._motion_axes, self._snap_step), "DEBUG")

    def _annotations_dialog(self):
        dlg = AnnotationsDialog(self)
        dlg.exec_()

    def _apply_annotations(self, vals):
        self._display_state["Display project title"] = bool(
            vals.get("show_title", False))
        self._display_state["Display current date"] = bool(
            vals.get("show_date", False))
        self._display_state["Display ANSYS logo"] = bool(
            vals.get("show_logo", False))
        self._project_title_text = str(vals.get("title", "Project"))
        if "title" in getattr(self, "_display_actors", {}):
            pass
        self.log("Annotations: %s" % vals, "DEBUG")
        self._render()

    def _tb(self, name, row=0):
        tb = QToolBar(name, self)
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        if row != self._tb_row and self._tb_row >= 0:
            self.addToolBarBreak(Qt.TopToolBarArea)
        self._tb_row = row
        self.addToolBar(Qt.TopToolBarArea, tb)
        self._toolbars[name] = tb
        a = QAction(name, self)
        a.setCheckable(True)
        a.setChecked(True)
        a.toggled.connect(tb.setVisible)
        if self._tb_menu is not None:
            self._tb_menu.addAction(a)
        return tb

    def _tb_act(self, tb, text, slot=None, icon=None, shortcut=None):
        a = QAction(text, self)
        if icon:
            a.setIcon(IceIcons.get(icon, 24))
        if shortcut:
            a.setShortcut(shortcut)
        if slot:
            a.triggered.connect(slot)
        else:
            a.triggered.connect(lambda _=False, t=text: self._nyi(t))
        tb.addAction(a)
        self._created_by_command[text] = a
        return a

    def _build_toolbars(self):
        """P0: toolbars are generated from the golden command registry."""
        build_toolbars(self)

    # ------------------------------------------------------------- 3D overlays
    def _setup_3d_overlays(self):
        if not self._enable_3d or self.renderer is None:
            return
        axes = vtk.vtkAxesActor()
        axes.SetShaftTypeToCylinder()
        axes.SetTotalLength(1.0, 1.0, 1.0)
        try:
            axes.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetColor(0.8, 0, 0)
            axes.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetColor(0, 0.55, 0)
            axes.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetColor(0.13, 0.27, 0.8)
        except Exception:
            pass
        w = vtk.vtkOrientationMarkerWidget()
        w.SetOrientationMarker(axes)
        w.SetInteractor(self.vtk_widget.GetRenderWindow().GetInteractor())
        w.SetViewport(0.0, 0.0, 0.18, 0.18)
        w.SetEnabled(1)
        w.InteractiveOff()
        self._orient_widget = w
        self._axes_actor = axes

        txt = vtk.vtkTextActor()
        txt.SetInput("ANSYS %s" % ICEPAK_VERSION)
        prop = txt.GetTextProperty()
        prop.SetFontSize(16)
        prop.SetColor(0.92, 0.95, 0.98)
        prop.SetOpacity(0.55)
        prop.SetBold(1)
        txt.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        txt.SetPosition(0.72, 0.94)
        self._logo_actor = txt
        self.renderer.AddActor2D(txt)

    # ------------------------------------------------------------- file
    def open_path(self, path):
        if os.path.isdir(path):
            self._load_directory(path)
        elif path.lower().endswith((".tzr", ".tar", ".tgz", ".gz")):
            self._load_archive(path)
        elif os.path.isfile(path):
            self.log("Only a project directory or .tzr archive is supported: %s"
                     % path, "WARN")

    def _new_project(self, name="untitled"):
        """Programmatic new project (kept argument-compatible with tests)."""
        from icepak_parser.project import IcepakProject
        proj = IcepakProject.empty(name)
        proj.model.objects.append(default_cabinet())
        self.root_path = None
        self._reset_edit_state()
        self._apply_project(proj, "New project %s "
                           "(default cabinet 0.5 x 0.4 x 0.3)" % name)

    def _new_project_dialog(self):
        """Icepak File->New project panel (no Chinese in name)."""
        name = NewProjectDialog.get_name(self)
        if not name:
            self.log("New project cancelled", "INFO")
            return
        self._new_project(name)

    def _reset_edit_state(self):
        self._hidden = set()
        self._inactive = set()
        self._trash = []
        self._groups = {}
        self.selected = None
        self._clear_undo()

    def _scan_inactive(self):
        self._inactive = set()
        model = getattr(self.project, "model", None) if self.project else None
        if model is None:
            return
        for o in model._all_objects():
            if not object_active(o):
                self._inactive.add(o.name)

    def _refresh(self, fit=False):
        if self.project is not None:
            self.project_tree.populate(
                self.project, hidden=self._hidden, inactive=self._inactive,
                trash=self._trash, groups=self._groups)
        if self._enable_3d:
            self._rebuild_scene()
            if fit:
                self._fit()

    def _apply_project(self, proj, log_msg=None):
        self.project = proj
        name = getattr(proj, "name", None) or "untitled"
        self.setWindowTitle("%s — %s" % (ICEPAK_TITLE, name))
        if hasattr(self, "_title_bar"):
            self._title_bar.setText("Project: %s" % name)
        if log_msg:
            self.log(log_msg)
        self._scan_inactive()
        self._refresh(fit=True)
        lib = find_icepak_lib()
        if lib:
            self.library_tree.populate_from_path(lib)
        self.statusBar().showMessage(name)

    def _open_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Open project", self.root_path or os.getcwd())
        if d:
            self._load_directory(d)

    def _open_tzr(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Unpack project", self.root_path or os.getcwd(),
            "Icepak archive (*.tzr *.tar *.tgz *.gz)")
        if f:
            self._load_archive(f)

    def _reload(self):
        if self.project is not None:
            self.open_path(getattr(self.project, "path", None) or "")

    def _save(self, path=None):
        """Save model (and timestamp) back to the project directory."""
        if self.project is None:
            self.log("No project to save", "WARN")
            return False
        if path is None:
            path = self._write_project_models()
            if path is None and self.root_path:
                path = self._write_project_models()
        else:
            from icepak_parser.decoder import encode_text
            from ice_create import serialize_model
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="latin-1") as fh:
                    fh.write(encode_text(serialize_model(self.project.model)))
                self.log("Saved model -> %s" % path)
            except OSError as err:
                self.log("Save failed: %r" % err, "ERROR")
                return False
        if path:
            self.root_path = getattr(self.project, "path", None) or self.root_path
            self._dirty = False
            self.setWindowTitle(ICEPAK_TITLE + " — " +
                                (self.project.name or "untitled"))
            return True
        return False

    def _save_as(self):
        if self.project is None:
            self.log("No project to save", "WARN")
            return None
        suggested = (self.project.name or "project") + ".model"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project as", suggested, "Icepak model (*.model)")
        if path:
            return self._save(path)
        return None

    def _pack_project(self):
        if self.project is None:
            self.log("No project to pack", "WARN")
            return
        suggested = (self.project.name or "project") + ".tzr"
        path, _ = QFileDialog.getSaveFileName(
            self, "Pack project", suggested, "Icepak archive (*.tzr)")
        if path:
            self.pack_to(path)

    def pack_to(self, path):
        """Pack current project to path (no dialog; used by tests)."""
        if self.project is None:
            self.log("No project to pack", "WARN")
            return None
        files = project_files_for_pack(self.project)
        if not files:
            self.log("Nothing to pack", "WARN")
            return None
        prefix = os.path.splitext(os.path.basename(path))[0] or "project"
        tzr.pack_file(path, files, prefix=prefix)
        self.log("Packed %d files to %s" % (len(files), path))
        return path

    def _export_csv(self):
        if self.project is None:
            self.log("No project loaded", "WARN")
            return
        d = QFileDialog.getExistingDirectory(
            self, "Export CSV/Excel", self.root_path or os.getcwd())
        if not d:
            return
        try:
            paths = export.export_all(self.project, d)
            self.log("Exported: %s" % ", ".join(paths.values()))
        except Exception as e:
            self.log("Export failed: %r" % e, "ERROR")

    def _print_screen(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Print screen", "icepak_view.png", "PNG (*.png)")
        if path:
            self._grab_view(path)

    def _create_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Create image file", "icepak_view.png",
            "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._grab_view(path)

    def _grab_view(self, path):
        if self._enable_3d and self.vtk_widget is not None:
            try:
                w2i = vtk.vtkWindowToImageFilter()
                w2i.SetInput(self.vtk_widget.GetRenderWindow())
                w2i.Update()
                w = vtk.vtkPNGWriter() if path.lower().endswith(".png") \
                    else vtk.vtkJPEGWriter()
                w.SetFileName(path)
                w.SetInputConnection(w2i.GetOutputPort())
                w.Write()
                self.log("Saved image %s" % path)
                return
            except Exception as e:
                self.log("vtk grab failed: %r" % e, "WARN")
        pix = self.graphics.grab()
        pix.save(path)
        self.log("Saved image %s" % path)

    def _command_prompt(self):
        cwd = self.root_path or os.getcwd()
        try:
            if sys.platform == "win32":
                os.startfile("cmd.exe")
            else:
                os.system("x-terminal-emulator &")
            self.log("Opened command prompt (cwd hint: %s)" % cwd)
        except Exception as e:
            self.log("Command prompt failed: %r" % e, "ERROR")

    def _load_directory(self, root):
        from icepak_parser.cli import is_project_dir
        self.root_path = root
        if is_project_dir(root):
            self._load_project((os.path.basename(root), "dir", root))
            return
        entries = find_projects(root)
        self.projects = entries
        self.log("Scanned %d project(s) in %s" % (len(entries), root))
        if entries:
            self._load_project(entries[0])
        else:
            self.log("No Icepak project found in %s" % root, "WARN")

    def _load_archive(self, path):
        self.root_path = os.path.dirname(path)
        self._load_project((os.path.basename(path), "tzr", path))

    def _load_project(self, entry):
        name, kind, source = entry
        from icepak_parser import project as projmod
        try:
            if kind == "tzr":
                proj = projmod.IcepakProject.from_archive(source)
            else:
                proj = projmod.IcepakProject(source)
        except Exception as e:
            self.log("Load failed %s: %r" % (source, e), "ERROR")
            return
        self._reset_edit_state()
        self.project = proj
        self.setWindowTitle("%s — %s" % (ICEPAK_TITLE, proj.name))
        self.log("Loaded project: %s (%s objects, %s setters)" % (
            proj.name, proj.summary().get("objects", 0),
            proj.summary().get("setters", 0)))
        if getattr(self, "message_win", None) is not None:
            logp = os.path.join(
                source if os.path.isdir(str(source)) else self.root_path or ".",
                ".ice_gui.log")
            self.message_win.set_log_file(logp)
        self._scan_inactive()
        self._refresh(fit=True)
        lib = find_icepak_lib()
        if lib:
            self.library_tree.populate_from_path(lib)
        self.statusBar().showMessage(proj.name)

    # ------------------------------------------------------------- tree
    def _measure_start(self, kind):
        self._measure_kind = kind
        self._measure_picks = []
        self.log("Measure %s: select two objects/points" % kind)

    def _measure_pick(self, obj):
        if not hasattr(self, "_measure_picks"):
            self._measure_picks = []
        self._measure_picks.append(obj)
        if len(self._measure_picks) < 2:
            self.log("Measure %s: point %d (%s)" %
                     (self._measure_kind, len(self._measure_picks), obj.name))
            return
        a = self._object_bounds(self._measure_picks[0])
        b = self._object_bounds(self._measure_picks[1])
        if a is None or b is None:
            self.log("Measure skipped: object without bounds", "WARN")
            self._measure_kind = None
            return
        kind = self._measure_kind
        self._measure_kind = None
        ca = [(a[0][i] + a[1][i]) / 2 for i in range(3)]
        cb = [(b[0][i] + b[1][i]) / 2 for i in range(3)]
        if kind == "Distance":
            d = sum((cb[i] - ca[i]) ** 2 for i in range(3)) ** 0.5
            self.log("Distance = %.6g" % d)
        elif kind == "Location":
            self.log("Location = (%.6g, %.6g, %.6g)" % (cb[0], cb[1], cb[2]))
        elif kind == "Angle":
            import math as _m
            v = [cb[i] - ca[i] for i in range(3)]
            self.log("Angle = %.3g deg" % _m.degrees(_m.atan2(
                (v[0] ** 2 + v[1] ** 2) ** 0.5, v[2])))
        elif kind == "Bounding box":
            lo = tuple(min(a[0][i], b[0][i]) for i in range(3))
            hi = tuple(max(a[1][i], b[1][i]) for i in range(3))
            self.log("Bounding box = %s .. %s" % (lo, hi))
        if not hasattr(self, "_markers"):
            self._markers = []
        self._markers.append((cb[0], cb[1], cb[2]))
        self.log("Marker added", "DEBUG")

    def _marker_clear(self):
        self._markers = []
        self._rubber_bands = []
        self.log("Markers/Rubber bands cleared")

    def _on_object_selected(self, o):
        if getattr(self, "_measure_kind", None):
            self._measure_pick(o)
            return
        if self._align_session is not None and \
                self._align_session.state is not None:
            self._align_pick_object(o)
            return
        self._highlight_object(o.name)
        if hasattr(self, "geometry_win"):
            self.geometry_win.set_object(o)
        self.log("Selected: %s (%s)" % (o.name, o.kind))

    def _on_object_activated(self, o):
        self._show_object_dialog(o)
        self._focus_object(o.name)

    def _on_node_selected(self, tag, payload):
        if tag == "setter" and payload:
            self.log("Parameter %s" % payload[0])
        elif tag in ("group", "kindgroup"):
            self.log("Type %s" % payload)
        elif tag == "usergroup":
            self.log("Group %s" % payload)
        elif tag == "post":
            self.log("Post object")
        elif tag == "trash":
            self.log("Trash: %s" % getattr(payload, "name", payload))
        elif tag == "node":
            self.log(str(payload or tag))

    def _on_node_activated(self, tag, payload):
        if tag == "setter" and payload:
            dlg = DetailsDialog("Parameter — %s" % payload[0],
                                [(payload[0], payload[1])], self)
            dlg.exec_()
        elif tag == "post" and payload:
            rows = [("type", payload.get("type"))]
            for k, v in (payload.get("params") or {}).items():
                rows.append((k, v))
            dlg = DetailsDialog("Post object", rows, self)
            dlg.exec_()
        elif tag == "trash" and payload:
            self.restore_from_trash(getattr(payload, "name", None))
        elif tag in ("node", "kindgroup", "usergroup"):
            self._show_named_settings(str(payload or tag))

    def _object_rows(self, o):
        rows = [("Type", o.kind), ("Name", o.name),
                ("creation_order",
                 o.properties.get("creation_order", [""])[0])]
        for k in ("current_stype", "grid_priority", "block_type",
                  "plate_type", "temp", "current_genus"):
            if k in o.properties:
                rows.append((k, " ".join(o.properties[k])))
        if o.shape:
            rows.append(("Shape", o.shape.type))
            for k, v in o.shape.setvals.items():
                rows.append(("setval " + k, " ".join(v)))
        return rows

    def _show_object_dialog(self, o):
        dlg = DetailsDialog("Edit object — %s" % o.name,
                            self._object_rows(o), self)
        dlg.exec_()

    def _edit_current(self):
        """Ctrl-E / Edit: single -> object editor; multi -> spreadsheet."""
        items = self.project_tree.selected_object_items()
        if len(items) > 1:
            self._open_spreadsheet()
            return
        current = self._current_object()
        if current is not None:
            if hasattr(self, "geometry_win"):
                self.geometry_win.set_object(current)
            dlg = ObjectEditDialog(self, obj=current, project=self.project)
            dlg.exec_()
    def _current_object(self):
        if self.project is not None and self.project.model is not None and self.selected:
            o = self.project.model.object_by_name(self.selected)
            if o is not None:
                return o
        items = self.project_tree.selectedItems()
        if not items:
            return None
        role = items[0].data(0, Qt.UserRole)
        if role and role[0] in ("object", "objectref"):
            return role[1]
        return None

    def _delete_current(self):
        obj = self._current_object()
        if obj is None or self.project is None or self.project.model is None:
            self.log("No object selected", "WARN")
            return
        if obj.kind == "domain" or obj.name == "cabinet":
            self.log("Cannot delete cabinet", "WARN")
            return
        snap = self._snapshot()
        taken = take_object(self.project.model, obj.name)
        if taken is None:
            self.log("Could not delete %s" % obj.name, "WARN")
            return
        self._push_undo(snap)
        self._trash.append(taken)
        self._hidden.discard(taken.name)
        self._inactive.discard(taken.name)
        for members in self._groups.values():
            if taken.name in members:
                members.remove(taken.name)
        if self.selected == taken.name:
            self.selected = None
        self._refresh()
        self.log("Moved %s to Trash" % taken.name)

    def _create_object(self, kind):
        if self.project is None or getattr(self.project, "model", None) is None:
            self._new_project()
        snap = self._snapshot()
        model = self.project.model
        name = next_object_name(model, kind)
        idx = model.count_all()
        obj = default_object(kind, name, index=idx, creation_order=idx + 1)
        model.objects.append(obj)
        self._push_undo(snap)
        self._refresh()
        self._highlight_object(obj.name)
        self.log("Created %s %s" % (kind, name))
        return obj

    def _snapshot(self):
        model_text = ""
        if self.project is not None and self.project.model is not None:
            model_text = serialize_model(self.project.model)
        return {
            "model": model_text,
            "hidden": set(self._hidden),
            "inactive": set(self._inactive),
            "trash": copy.deepcopy(self._trash),
            "groups": copy.deepcopy(self._groups),
            "selected": self.selected,
            "post": copy.deepcopy(getattr(self.project, "post", []) or []),
        }

    def _restore_snapshot(self, snap):
        from icepak_parser.model_parser import parse_text, ModelFile
        from icepak_parser.project import IcepakProject
        if self.project is None:
            self.project = IcepakProject.empty("untitled")
        self.project.model = parse_text(snap["model"]) if snap.get("model") else ModelFile()
        self._hidden = set(snap.get("hidden") or ())
        self._inactive = set(snap.get("inactive") or ())
        self._trash = list(snap.get("trash") or [])
        self._groups = dict(snap.get("groups") or {})
        self.selected = snap.get("selected")
        self.project.post = list(snap.get("post") or [])
        self._refresh()

    def _push_undo(self, snap):
        self._undo_stack.append(snap)
        if len(self._undo_stack) > UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack = []

    def _clear_undo(self):
        self._undo_stack = []
        self._redo_stack = []

    def _undo(self):
        if not self._undo_stack:
            self.log("Nothing to undo", "WARN")
            return
        self._redo_stack.append(self._snapshot())
        self._restore_snapshot(self._undo_stack.pop())
        self.log("Undo")

    def _redo(self):
        if not self._redo_stack:
            self.log("Nothing to redo", "WARN")
            return
        self._undo_stack.append(self._snapshot())
        self._restore_snapshot(self._redo_stack.pop())
        self.log("Redo")

    def _move_current(self, dx=None, dy=None, dz=None):
        obj = self._current_object()
        if obj is None:
            self.log("No object selected", "WARN")
            return None
        if dx is None:
            dlg = TranslateDialog("Move object", self)
            if dlg.exec_() != QDialog.Accepted:
                return None
            dx, dy, dz = dlg.offset()
        snap = self._snapshot()
        translate_object(obj, float(dx), float(dy), float(dz))
        self._push_undo(snap)
        self._refresh()
        self.log("Moved %s by (%g, %g, %g)" % (obj.name, dx, dy, dz))
        return obj

    def _copy_current(self, dx=None, dy=None, dz=None):
        obj = self._current_object()
        if obj is None:
            self.log("No object selected", "WARN")
            return None
        if dx is None:
            dlg = TranslateDialog("Copy object", self, dx=0.05, dy=0.0, dz=0.0)
            if dlg.exec_() != QDialog.Accepted:
                return None
            dx, dy, dz = dlg.offset()
        snap = self._snapshot()
        name = next_object_name(self.project.model, obj.kind)
        clone = clone_object(obj, name)
        translate_object(clone, float(dx), float(dy), float(dz))
        self.project.model.objects.append(clone)
        self._push_undo(snap)
        self._refresh()
        self._highlight_object(clone.name)
        self.log("Copied %s -> %s" % (obj.name, clone.name))
        return clone

    def _toggle_selected_active(self):
        obj = self._current_object()
        if obj is None or obj.kind == "domain":
            self.log("No object selected", "WARN")
            return
        snap = self._snapshot()
        if obj.name in self._inactive:
            self._inactive.discard(obj.name)
            set_object_active(obj, True)
            self.log("Activated %s" % obj.name)
        else:
            self._inactive.add(obj.name)
            set_object_active(obj, False)
            self.log("Deactivated %s" % obj.name)
        self._push_undo(snap)
        self._refresh()

    def restore_from_trash(self, name):
        if not name:
            return None
        found = None
        for o in self._trash:
            if o.name == name:
                found = o
                break
        if found is None:
            self.log("Not in Trash: %s" % name, "WARN")
            return None
        snap = self._snapshot()
        self._trash.remove(found)
        if self.project is None or self.project.model is None:
            from icepak_parser.project import IcepakProject
            self.project = IcepakProject.empty("untitled")
        self.project.model.objects.append(found)
        self._push_undo(snap)
        self._refresh()
        self.log("Restored %s from Trash" % name)
        return found

    def create_group(self, name, members=None):
        members = list(members or [])
        if not members and self.selected:
            members = [self.selected]
        snap = self._snapshot()
        self._groups[name] = members
        self._push_undo(snap)
        self._refresh()
        self.log("Group %s (%d objects)" % (name, len(members)))
        return name

    def _show_named_settings(self, title):
        from ice_panes import SOLUTION_ADV_KEYS, SOLUTION_BASIC_KEYS, SOLUTION_PAR_KEYS
        mapping = {
            "Basic settings": SOLUTION_BASIC_KEYS,
            "Advanced settings": SOLUTION_ADV_KEYS,
            "Parallel settings": SOLUTION_PAR_KEYS,
        }
        if title in mapping:
            self._show_problem_keys(title, mapping[title])
        elif title in ("Basic parameters", "Problem setup"):
            self._show_basic_settings()

    def _show_problem_keys(self, title, keys):
        if self.project is None or self.project.problem is None:
            self._nyi(title)
            return
        rows = []
        for k in keys:
            if k in self.project.problem.setters:
                rows.append((k, self.project.problem.setters[k]))
        if not rows:
            rows = [(k, v) for k, v in sorted(self.project.problem.setters.items())[:20]]
        if not rows:
            self._nyi(title)
            return
        dlg = DetailsDialog(title, rows, self)
        dlg.exec_()

    def _show_advanced_settings(self):
        from ice_panes import SOLUTION_ADV_KEYS
        self._show_problem_keys("Advanced settings", SOLUTION_ADV_KEYS)

    def _show_parallel_settings(self):
        from ice_panes import SOLUTION_PAR_KEYS
        self._show_problem_keys("Parallel settings", SOLUTION_PAR_KEYS)

    def _show_transient_settings(self):
        """Solve -> Transient settings (time step / steps / end time / save)."""
        from ice_panes import SOLUTION_TRANSIENT_KEYS
        self._show_problem_keys("Transient settings", SOLUTION_TRANSIENT_KEYS)

    def _show_postprocessing_units(self):
        """Post -> Postprocessing units (temp/pressure/length display units)."""
        from ice_panes import SOLUTION_UNITS_KEYS
        self._show_problem_keys("Postprocessing units", SOLUTION_UNITS_KEYS)

    def _load_post_objects(self, path=None):
        from icepak_parser.project import parse_post_objects
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Load post objects", "", "Post objects (*)")
        if not path:
            return
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            text = f.read()
        if self.project is None:
            from icepak_parser.project import IcepakProject
            self.project = IcepakProject.empty("untitled")
        snap = self._snapshot()
        self.project.post = parse_post_objects(text)
        self._push_undo(snap)
        self._refresh()
        self.log("Loaded %d post objects" % len(self.project.post))

    def _save_post_objects(self, path=None):
        from icepak_parser.project import format_post_objects
        posts = getattr(self.project, "post", None) if self.project else None
        if not posts:
            self.log("No post objects", "WARN")
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save post objects", "post_objects", "Post objects (*)")
        if not path:
            return None
        with open(path, "w", encoding="latin-1") as f:
            f.write(format_post_objects(posts))
        self.log("Saved %d post objects to %s" % (len(posts), path))
        return path

    def _on_lib_activated(self, name, payload):
        self._nyi("Instantiate from library: %s" % name)

    def _tree_menu(self, pos):
        item = self.project_tree.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            role = item.data(0, Qt.UserRole)
            tag = role[0] if role else ""
            if tag in ("object", "objectref"):
                obj = role[1] if len(role) > 1 else None
                menu.addAction("Edit object", self._edit_current)
                menu.addAction("Edit via spreadsheet...",
                               self._open_spreadsheet)
                menu.addAction("Delete object", self._delete_current)
                menu.addAction("Move object", self._move_current)
                menu.addAction("Copy object", self._copy_current)
                menu.addAction("Toggle visible", self._toggle_selected_visible)
                menu.addAction("Toggle active", self._toggle_selected_active)
                menu.addAction("Add to group...", self._group_selected)
                menu.addAction("Remove from group",
                               lambda: self._remove_from_group(obj))
            elif tag == "usergroup":
                menu.addAction("Rename group...",
                               lambda: self._rename_group(role[1]))
                menu.addAction("Delete group",
                               lambda: self._delete_group(role[1]))
                menu.addSeparator()
                menu.addAction("Activate all",
                               lambda: self._group_all(role[1], True))
                menu.addAction("Deactivate all",
                               lambda: self._group_all(role[1], False))
                menu.addAction("Delete all",
                               lambda: self._group_all(role[1], False))
                menu.addAction("Create assembly",
                               lambda: self._group_to_assembly(role[1]))
                menu.addAction("Copy params", lambda: self._nyi(
                    "Copy params from group"))
            elif tag == "trash":
                menu.addAction("Restore from Trash",
                               lambda: self.restore_from_trash(
                                   getattr(role[1], "name", None)))
            elif (item.text(0) == "Model" or item.text(0) == "Project"
                  or tag == "root"):
                menu.addAction("Find object", self._find_object)
                menu.addAction("Expand all", self._expand_tree)
                menu.addAction("Collapse all", self._collapse_tree)
                menu.addSeparator()
                ov = menu.addMenu("Object view")
                for i, label in enumerate((
                        "Flat", "Types", "Types+subtypes",
                        "Types+subtypes+shapes")):
                    a = ov.addAction(label)
                    a.setCheckable(True)
                    a.setChecked(self.project_tree.tree_detail == i)
                    a.triggered.connect(
                        lambda _=False, d=i: self._set_tree_detail(d))
                srt = menu.addMenu("Sort")
                for label in ("creation_order", "meshing priority",
                              "alphabetical"):
                    a = srt.addAction(label)
                    a.setCheckable(True)
                    a.setChecked(self.project_tree.listsort == label)
                    a.triggered.connect(
                        lambda _=False, s=label: self._set_tree_sort(s))
            else:
                menu.addAction("Find", self._find_object)
        if not menu.actions():
            return
        menu.exec_(self.project_tree.viewport().mapToGlobal(pos))

    def _group_selected(self):
        name, ok = QInputDialog.getText(self, "Create group", "Group name:")
        if ok and str(name).strip():
            self.create_group(str(name).strip())

    def _on_tree_drop(self, target, names):
        """Drag & drop: object items -> Inactive / Trash / Points / Surfaces."""
        model = getattr(self.project, "model", None) if self.project else None
        if model is None:
            return
        for name in names:
            obj = model.object_by_name(name)
            if obj is None:
                continue
            if target == "Inactive":
                set_object_active(obj, False)
                self._inactive.add(name)
                self.log("Inactive: %s" % name)
            elif target == "Trash":
                if not object_active(obj):
                    set_object_active(obj, True)
                    self._inactive.discard(name)
                take_object(model, name)
                self._trash.append(obj)
                self.log("Trash: %s" % name)
            elif target == "Points":
                if not hasattr(self, "_points"):
                    self._points = []
                self._points.append(name)
                self.log("Monitor point queued: %s (P4 wires values)" % name)
            elif target == "Surfaces":
                if not hasattr(self, "_surfaces"):
                    self._surfaces = []
                self._surfaces.append(name)
                self.log("Monitor surface queued: %s (P4 wires values)" % name)
        self._refresh()

    def _set_tree_detail(self, d):
        self.project_tree.tree_detail = int(d)
        self._refresh()
        self.log("Object view: %s" % (
            ("Flat", "Types", "Types+subtypes", "Types+subtypes+shapes")[int(d)]))

    def _set_tree_sort(self, s):
        self.project_tree.listsort = s
        self._refresh()
        self.log("Sort: %s" % s)

    def _expand_tree(self):
        self.project_tree.expandAll()

    def _collapse_tree(self):
        self.project_tree.collapseAll()

    def _remove_from_group(self, obj):
        if obj is None:
            return
        for gname, members in list(self._groups.items()):
            if obj.name in members:
                members.remove(obj.name)
        self._refresh()
        self.log("Removed %s from group" % obj.name)

    def _rename_group(self, name):
        new, ok = QInputDialog.getText(self, "Rename group",
                                       "New group name:", text=str(name))
        if ok and str(new).strip() and name in self._groups:
            self._groups[str(new).strip()] = self._groups.pop(name)
            self._refresh()

    def _delete_group(self, name, delete_all=False):
        if name in self._groups:
            self._groups.pop(name)
            self._refresh()
            self.log("Deleted group %s" % name)

    def _group_all(self, name, active):
        model = getattr(self.project, "model", None) if self.project else None
        if model is None:
            return
        for m in self._groups.get(name, []):
            obj = model.object_by_name(m)
            if obj is not None:
                set_object_active(obj, active)
                if active:
                    self._inactive.discard(m)
                else:
                    self._inactive.add(m)
        self._refresh()

    def _group_to_assembly(self, name):
        self.log("Create assembly from group %s (P4)" % name, "WARN")

    def _open_spreadsheet(self):
        """Edit via spreadsheet: multi-edit entry point (tkTable parity)."""
        items = self.project_tree.selected_object_items()
        names = [it.text(0) for it in items]
        if not names:
            current = self._current_object()
            names = [current.name] if current is not None else []
        from ice_panes import SpreadsheetDialog
        dlg = SpreadsheetDialog(self, names=names, project=self.project)
        dlg.exec_()

    def _toggle_tree_node(self):
        items = self.project_tree.selectedItems()
        if items:
            items[0].setExpanded(not items[0].isExpanded())

    def _toggle_model_subtree(self):
        m = self.project_tree._items.get("Model")
        if m is not None:
            m.setExpanded(not m.isExpanded())

    def _set_view_panes(self, n):
        n = int(n)
        if n == 2 and self._view_stack.count() > 2:
            self._view_stack.setCurrentIndex(2)
            self._view_panes = 2
            self.log("Two viewing windows")
            return
        self._view_panes = 4 if n == 4 else 1
        if self._enable_3d:
            self._apply_viewports()
            self._rebuild_scene()
            if self._view_panes == 1:
                self._fit()
        elif hasattr(self, "_view_stack"):
            self._view_stack.setCurrentIndex(1 if self._view_panes == 4 else 0)
        self.log("Viewing windows: %d" % self._view_panes)

    def _apply_viewports(self):
        if not self._enable_3d or self.vtk_widget is None or self.renderer is None:
            return
        rw = self.vtk_widget.GetRenderWindow()
        for r in self._extra_renderers:
            rw.RemoveRenderer(r)
        self._extra_renderers = []
        if self._view_panes != 4:
            self.renderer.SetViewport(0.0, 0.0, 1.0, 1.0)
            return
        self.renderer.SetViewport(0.5, 0.0, 1.0, 0.5)
        for vp in ((0.0, 0.5, 0.5, 1.0), (0.5, 0.5, 1.0, 1.0),
                   (0.0, 0.0, 0.5, 0.5)):
            r = vtk.vtkRenderer()
            r.SetViewport(*vp)
            r.SetBackground(0.957, 0.969, 0.984)
            r.SetBackground2(0.620, 0.784, 0.910)
            r.GradientBackgroundOn()
            r.GetActiveCamera().ParallelProjectionOn()
            rw.AddRenderer(r)
            self._extra_renderers.append(r)

    def _iter_renderers(self):
        if self.renderer is not None:
            yield self.renderer
        for r in self._extra_renderers:
            yield r

    def _renderer_at(self, x, y):
        if not self._enable_3d or self.vtk_widget is None:
            return self.renderer
        sz = self.vtk_widget.GetRenderWindow().GetSize()
        if not sz or sz[0] <= 0 or sz[1] <= 0:
            return self.renderer
        xn, yn = x / float(sz[0]), y / float(sz[1])
        for r in self._iter_renderers():
            v = r.GetViewport()
            if v[0] <= xn <= v[2] and v[1] <= yn <= v[3]:
                return r
        return self.renderer

    def _find_object(self, text=None):
        if text is None:
            text, ok = QInputDialog.getText(self, "Find", "Object name:")
            if not ok:
                return None
        needle = str(text).strip()
        if not needle:
            return None
        hits = self.project_tree.find_items_matching(needle)
        if not hits:
            self.log("Find: no match for %r" % needle, "WARN")
            return None
        it = hits[0]
        self.project_tree.setCurrentItem(it)
        self.project_tree.scrollToItem(it)
        role = it.data(0, Qt.UserRole)
        if role and role[0] == "object":
            self._highlight_object(role[1].name)
            self._focus_object(role[1].name)
        extra = " (%d matches)" % len(hits) if len(hits) > 1 else ""
        self.log("Find: %s%s" % (it.text(0), extra))
        return role[1] if role and role[0] == "object" else None

    def _on_tree_visibility(self, name, visible):
        if visible:
            self._hidden.discard(name)
        else:
            self._hidden.add(name)
        if self._enable_3d:
            self._rebuild_scene()

    def _toggle_selected_visible(self):
        if not self.selected:
            return
        if self.selected in self._hidden:
            self._hidden.discard(self.selected)
        else:
            self._hidden.add(self.selected)
        self._rebuild_scene()

    def _on_tdv_mode(self, mode):
        self.log("Interaction: %s" % mode, "DEBUG")
        self.statusBar().showMessage("Mode: %s" % mode)

    # ------------------------------------------------------------- shading / view
    def _set_shading(self, mode):
        self._shading = mode
        if mode in self._shading_actions:
            self._shading_actions[mode].setChecked(True)
        self._rebuild_scene()

    def _cycle_shading(self):
        i = SHADING_MODES.index(self._shading)
        self._set_shading(SHADING_MODES[(i + 1) % len(SHADING_MODES)])

    def _on_layer_toggle(self, kind, on):
        self._rebuild_scene()

    def _toggle_axes(self, on):
        self._show_axes = on
        if self._orient_widget is not None:
            self._orient_widget.SetEnabled(1 if on else 0)
            self._render()

    def _toggle_logo(self, on):
        self._show_logo = on
        if self._logo_actor is not None:
            self._logo_actor.SetVisibility(1 if on else 0)
            self._render()

    def _set_names(self, val):
        self._show_names = int(val)
        if self._enable_3d:
            self._rebuild_scene()
        self.log("Object names display = %s" % val, "DEBUG")

    def _cycle_names(self):
        self._set_names((self._show_names + 1) % 3)
        labels = {
            0: "No object names",
            1: "Current assembly object names",
            2: "Selected object names",
        }
        self.log(labels.get(self._show_names, str(self._show_names)))

    def _toggle_message(self, on):
        self.message_win.setVisible(on)

    def _toggle_nav(self, on):
        self.nav_tabs.setVisible(on)

    def _show_bbox(self):
        b = self._scene_bounds()
        if b is None:
            self.log("No geometry", "WARN")
            return
        self.log("Bounding box: [%g %g %g] — [%g %g %g]" % tuple(b))

    def _check_model(self):
        if self.project is None or self.project.model is None:
            self.log("No model", "WARN")
            return
        n = self.project.model.count_all()
        kinds = dict(self.project.model.kind_counts())
        self.log("Check model: %d objects, types=%s" % (n, kinds))

    def _show_basic_settings(self):
        if self.project is None or self.project.problem is None:
            self._nyi("Basic settings")
            return
        p = self.project.problem
        rows = [(k, v) for k, v in sorted(p.setters.items())]
        dlg = DetailsDialog("Basic settings", rows[:80], self)
        dlg.exec_()

    # ------------------------------------------------------------- 3D scene
    def _rebuild_scene(self):
        if (not self._enable_3d or self.project is None
                or self.project.model is None):
            return
        layer_on = {k: True for k in VISIBLE_KINDS}
        for k, a in self._layer_actions.items():
            layer_on[k] = a.isChecked()
        wire = self._shading == "wire"
        self.scene_objs = build_scene(self.project.model, layer_on, wire)
        self.scene_objs = [so for so in self.scene_objs
                           if so.name not in self._hidden
                           and so.name not in self._inactive]
        for r in list(self._iter_renderers()):
            r.RemoveAllViewProps()
        if self._logo_actor is not None and self._show_logo:
            self.renderer.AddActor2D(self._logo_actor)
        self.actors = []
        self._actor_map = {}
        for so in self.scene_objs:
            for r in self._iter_renderers():
                actor = self._make_actor(so)
                r.AddActor(actor)
                self._actor_map[actor] = so
                if r is self.renderer:
                    self.actors.append((actor, so))
        self._apply_highlight()
        self._add_name_labels()
        if self._view_panes == 4:
            b = self._scene_bounds()
            for r, which in zip(self._extra_renderers, ("-x", "+y", "-z")):
                self._apply_orient_to_camera(r.GetActiveCamera(), which, b)
                r.ResetCameraClippingRange()
            self._apply_orient_to_camera(
                self.renderer.GetActiveCamera(), "iso", b)
            self.renderer.ResetCameraClippingRange()
        self._render()
        self.log("3D scene: %d objects" % len(self.scene_objs), "DEBUG")

    def _make_actor(self, so):
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(so.polydata)
        mapper.ScalarVisibilityOff()
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*so.color)
        prop.SetAmbient(0.25)
        prop.SetDiffuse(0.85)
        prop.SetSpecular(0.25)
        prop.SetSpecularPower(18)
        mode = self._shading
        selected = self.selected == so.name
        if mode == "wire":
            prop.SetRepresentationToWireframe()
            prop.SetLineWidth(1.1)
            prop.LightingOff()
            prop.SetAmbient(1.0)
        elif mode == "solid":
            prop.SetRepresentationToSurface()
            prop.EdgeVisibilityOff()
        elif mode == "solid/wire":
            prop.SetRepresentationToSurface()
            prop.EdgeVisibilityOn()
            prop.SetEdgeColor(0.15, 0.15, 0.15)
            prop.SetLineWidth(1.0)
        elif mode == "hidden line":
            prop.SetRepresentationToSurface()
            prop.SetColor(0.96, 0.97, 0.98)
            prop.EdgeVisibilityOn()
            prop.SetEdgeColor(*so.color)
            prop.LightingOff()
        elif mode == "selected_solid":
            if selected:
                prop.SetRepresentationToSurface()
                prop.EdgeVisibilityOff()
            else:
                prop.SetRepresentationToWireframe()
                prop.LightingOff()
                prop.SetAmbient(1.0)
        if so.kind == "domain":
            prop.SetRepresentationToWireframe()
            prop.SetLineWidth(1.4)
            prop.LightingOff()
        return actor

    def _apply_highlight(self):
        if not self._enable_3d:
            return
        for actor, so in self.actors:
            if so.name == self.selected and self._shading != "selected_solid":
                actor.GetProperty().SetColor(1.0, 0.25, 0.1)

    def _highlight_object(self, name):
        self.selected = name
        if self._shading == "selected_solid" or self._show_names == 2:
            self._rebuild_scene()
        else:
            self._apply_highlight()
            self._render()
        it = self.project_tree.find_object_item(name)
        if it is not None:
            self.project_tree.blockSignals(True)
            self.project_tree.setCurrentItem(it)
            self.project_tree.blockSignals(False)

    def _focus_object(self, name):
        for so in self.scene_objs:
            if so.name == name:
                self._camera_to_bounds(so.bounds)
                return

    def _scene_bounds(self):
        if not self.scene_objs:
            return None
        b = np.array([so.bounds for so in self.scene_objs])
        lo = b[:, 0:3].min(axis=0)
        hi = b[:, 3:6].max(axis=0)
        return np.concatenate([lo, hi])

    def _camera_to_bounds(self, b):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        cx = (b[0] + b[3]) / 2.0
        cy = (b[1] + b[4]) / 2.0
        cz = (b[2] + b[5]) / 2.0
        span = max(b[3] - b[0], b[4] - b[1], b[5] - b[2], 1e-6)
        dist = span * 3.0
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetPosition(cx + dist * 0.6, cy - dist * 0.6, cz + dist)
        cam.SetViewUp(0, 0, 1)
        cam.ParallelProjectionOn()
        cam.SetParallelScale(span * 0.75)
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _fit(self):
        b = self._scene_bounds()
        if b is not None:
            self._camera_to_bounds(b)
        elif self._enable_3d:
            self.renderer.ResetCamera()
            self._render()

    def _home(self):
        self._orient("iso")
        self._fit()

    def _zoom_in(self):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        cam.SetParallelScale(cam.GetParallelScale() * 0.7)
        self._render()

    def _rotate_normal(self):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        cam.Roll(90)
        self._render()

    def _reverse_orient(self):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        fp = cam.GetFocalPoint()
        pos = cam.GetPosition()
        cam.SetPosition(2 * fp[0] - pos[0], 2 * fp[1] - pos[1],
                        2 * fp[2] - pos[2])
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _nearest_axis(self):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        d = list(cam.GetDirectionOfProjection())
        ax = max(range(3), key=lambda i: abs(d[i]))
        sign = "+" if d[ax] < 0 else "-"
        self._orient("%s%s" % (sign, "xyz"[ax]))

    def _apply_orient_to_camera(self, cam, which, b):
        if b is None:
            cx = cy = cz = 0.0
            span = 1.0
        else:
            cx = (b[0] + b[3]) / 2.0
            cy = (b[1] + b[4]) / 2.0
            cz = (b[2] + b[5]) / 2.0
            span = max(b[3] - b[0], b[4] - b[1], b[5] - b[2], 1e-6)
        dist = span * 3.0
        views = {
            "+x": ((cx + dist, cy, cz), (0, 0, 1)),
            "-x": ((cx - dist, cy, cz), (0, 0, 1)),
            "+y": ((cx, cy + dist, cz), (0, 0, 1)),
            "-y": ((cx, cy - dist, cz), (0, 0, 1)),
            "+z": ((cx, cy, cz + dist), (0, 1, 0)),
            "-z": ((cx, cy, cz - dist), (0, 1, 0)),
            "iso": ((cx + dist * 0.6, cy - dist * 0.6, cz + dist), (0, 0, 1)),
        }
        pos, up = views.get(which, views["iso"])
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetPosition(*pos)
        cam.SetViewUp(*up)
        cam.ParallelProjectionOn()
        cam.SetParallelScale(span * 0.75)

    def _orient(self, which):
        if not self._enable_3d:
            return
        cam = self.renderer.GetActiveCamera()
        self._apply_orient_to_camera(cam, which, self._scene_bounds())
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _render(self):
        if self._enable_3d and self.vtk_widget is not None:
            self.vtk_widget.GetRenderWindow().Render()

    def _on_press(self, obj, ev):
        self._press_pos = obj.GetEventPosition()

    def _on_release(self, obj, ev):
        if not self._enable_3d:
            return
        if self.tdv_strip.mode() not in ("pick", "boxpick"):
            return
        if self._press_pos is None:
            return
        x, y = obj.GetEventPosition()
        if abs(x - self._press_pos[0]) >= 4 or abs(y - self._press_pos[1]) >= 4:
            return
        picker = vtk.vtkPropPicker()
        rend = self._renderer_at(x, y)
        if picker.Pick(x, y, 0, rend):
            actor = picker.GetActor()
            so = self._actor_map.get(actor)
            if so is not None:
                self._highlight_object(so.name)
                self.log("Selected: %s (%s)" % (so.name, so.kind))

    def _add_name_labels(self):
        self._name_actors = []
        if not self._show_names or not self._enable_3d:
            return
        for so in self.scene_objs:
            if self._show_names == 2 and so.name != self.selected:
                continue
            b = so.bounds
            cx = (b[0] + b[3]) / 2.0
            cy = (b[1] + b[4]) / 2.0
            cz = (b[2] + b[5]) / 2.0
            actor = self._make_name_actor(so.name, (cx, cy, cz))
            if actor is not None:
                self.renderer.AddActor(actor)
                self._name_actors.append(actor)

    def _make_name_actor(self, text, pos):
        try:
            actor = vtk.vtkBillboardTextActor3D()
            actor.SetInput(text)
            actor.SetPosition(*pos)
            prop = actor.GetTextProperty()
            prop.SetFontSize(14)
            prop.SetColor(0.12, 0.14, 0.18)
            prop.SetBold(1)
            return actor
        except Exception:
            pass
        try:
            actor = vtk.vtkCaptionActor2D()
            actor.SetCaption(text)
            actor.SetAttachmentPoint(*pos)
            actor.BorderOff()
            actor.LeaderOff()
            return actor
        except Exception:
            return None

    def _camera_state(self):
        if not self._enable_3d or self.renderer is None:
            return None
        cam = self.renderer.GetActiveCamera()
        return {
            "pos": list(cam.GetPosition()),
            "fp": list(cam.GetFocalPoint()),
            "up": list(cam.GetViewUp()),
            "scale": cam.GetParallelScale(),
        }

    def _apply_camera_state(self, st):
        if not st or not self._enable_3d or self.renderer is None:
            return
        cam = self.renderer.GetActiveCamera()
        cam.SetPosition(*st["pos"])
        cam.SetFocalPoint(*st["fp"])
        cam.SetViewUp(*st["up"])
        cam.SetParallelScale(st.get("scale", cam.GetParallelScale()))
        cam.ParallelProjectionOn()
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _save_user_view(self):
        st = self._camera_state()
        if st is None:
            name = "view.%d" % (len(self._user_views) + 1)
            self._user_views.append({"name": name, "pos": [1, -1, 1],
                                     "fp": [0, 0, 0], "up": [0, 0, 1],
                                     "scale": 1.0})
            self._rebuild_user_views_menu()
            self._persist_user_views()
            self.log("Saved user view %s (headless)" % name)
            return
        name = "view.%d" % (len(self._user_views) + 1)
        rec = {"name": name}
        rec.update(st)
        self._user_views.append(rec)
        self._rebuild_user_views_menu()
        self._persist_user_views()
        self.log("Saved user view %s" % name)

    def _clear_user_views(self):
        self._user_views = []
        self._rebuild_user_views_menu()
        self._persist_user_views()
        self.log("Cleared user views")

    def _persist_user_views(self):
        QSettings("icedecoding", "ice_gui").setValue(
            "user_views", json.dumps(self._user_views))

    def _load_persisted_user_views(self):
        raw = QSettings("icedecoding", "ice_gui").value("user_views", "")
        if not raw:
            self._user_views = []
            return
        try:
            data = json.loads(raw)
            self._user_views = data if isinstance(data, list) else []
        except Exception:
            self._user_views = []

    def _write_user_views(self, path=None):
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Write user views", "user_views.json", "JSON (*.json)")
        if not path:
            return None
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._user_views, f, indent=2)
        self.log("Wrote user views %s" % path)
        return path

    def _read_user_views(self, path=None):
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Read user views", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._user_views = data if isinstance(data, list) else []
        self._rebuild_user_views_menu()
        self._persist_user_views()
        self.log("Read %d user views from %s" % (len(self._user_views), path))

    def _rebuild_user_views_menu(self):
        menu = getattr(self, "_user_views_menu", None)
        if menu is None:
            return
        menu.clear()
        if not self._user_views:
            a = QAction("(none)", self)
            a.setEnabled(False)
            menu.addAction(a)
            return
        for i, st in enumerate(self._user_views):
            name = st.get("name") or "view.%d" % (i + 1)
            a = QAction(name, self)
            a.triggered.connect(lambda _=False, s=st: self._apply_camera_state(s))
            menu.addAction(a)

    # ------------------------------------------------------------- help / welcome
    def _help(self):
        index = os.path.join(HELP_DIR, "index.html")
        if os.path.isfile(index):
            QDesktopServices.openUrl(QUrl.fromLocalFile(index))
        else:
            self._web_icepak()

    def _web_icepak(self):
        QDesktopServices.openUrl(QUrl(WEB_ICEPAK))

    def _web_portal(self):
        QDesktopServices.openUrl(QUrl(WEB_PORTAL))

    def _list_shortcuts(self):
        text = (
            "F1  Help\n"
            "Ctrl+N  New project\nCtrl+O  Open project\nCtrl+S  Save\n"
            "Ctrl+L  Reload\nCtrl+P  Print screen\n"
            "Ctrl+Z / Ctrl+R  Undo / Redo\nCtrl+F  Find\n"
            "Ctrl+E  Edit object\nDelete  Delete object\n"
            "Ctrl+A  Toggle active\nCtrl+V  Toggle visible\n"
            "Ctrl+H  Toggle shading\nCtrl+W  Cycle shading type\n"
            "h  Home   z  Zoom in   s  Scale to fit\n"
            "Shift+X/Y/Z  Orient -X / +Y / -Z\nShift+I  Isometric\n"
            "Shift+R  Reverse orientation\n"
        )
        QMessageBox.information(self, "Shortcuts", text)

    def _about(self):
        QMessageBox.about(
            self, "About Icepak",
            "ANSYS®  Icepak® Version %s\n\n"
            "icedecoding viewer — layout mapped from Icepak 19.5 Tcl menus.\n"
            "© ANSYS Inc. All rights reserved.\n"
            "Unauthorized use, distribution or duplication is prohibited."
            % ICEPAK_VERSION)

    def _show_welcome(self):
        dlg = WelcomeDialog(self)
        rc = dlg.exec_()
        ch = dlg.choice()
        if rc == QDialog.Rejected or ch == WelcomeDialog.quit:
            self.close()
            return
        if ch == WelcomeDialog.existing:
            self._open_dir()
        elif ch == WelcomeDialog.new:
            self._new_project_dialog()
        elif ch == WelcomeDialog.unpack:
            self._open_tzr()

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self._start_interactor)
        if self._pending_welcome:
            self._pending_welcome = False
            QTimer.singleShot(50, self._show_welcome)

    def _start_interactor(self):
        if not self._enable_3d or self.vtk_widget is None:
            return
        try:
            iren = self.vtk_widget.GetRenderWindow().GetInteractor()
            if not iren.GetInitialized():
                iren.Initialize()
            if self._orient_widget is not None:
                self._orient_widget.SetEnabled(1 if self._show_axes else 0)
        except Exception:
            pass
        if self._fit_pending:
            self._fit()
            self._fit_pending = False


def main(argv=None):
    if not HAS_GUI:
        print("PyQt5 / vtk 未安装: python -m pip install PyQt5 vtk numpy")
        return 1
    app = QApplication(argv if argv is not None else sys.argv)
    path = None
    args = argv if argv is not None else sys.argv
    if len(args) > 1:
        p = args[1]
        if os.path.isdir(p) or p.lower().endswith((".tzr", ".tar", ".tgz", ".gz")):
            path = p
    win = IceGui(path)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

def _vtk_glyph_points(cloud):
    import vtk
    mapper = vtk.vtkPointGaussianMapper()
    mapper.SetInputData(cloud)
    return mapper


def _vtk_actor(mapper, size=0.0028):
    import vtk
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    if hasattr(mapper, "SetScaleFactor"):
        mapper.SetScaleFactor(size)
    return actor


def _temp_colored_actor(cloud, size=0.0028):
    """Actor whose points are coloured by their temperature scalar (RGBA).

    temp_cloud_polys() emits a blue(cold)->red(hot) 4-component point colour;
    this keeps direct-scalar colouring on the gaussian mapper instead of the
    old uniform-red override, so iso/plane/extrema clouds show the real
    temperature ramp (P19-4 fine point: '按真实温对着色').
    """
    import vtk
    mapper = _vtk_glyph_points(cloud)
    mapper.ScalarVisibilityOn()
    try:
        mapper.SetColorModeToDirectScalars()
    except Exception:
        pass
    return _vtk_actor(mapper, size)
