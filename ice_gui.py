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

import numpy as np

# ---------------------------------------------------------------------------
# 包导入(允许以脚本方式直接运行)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from icepak_parser import model_parser, export, tzr  # noqa: E402
from icepak_parser.cli import find_projects  # noqa: E402

# ---------------------------------------------------------------------------
# GUI / VTK 依赖
# ---------------------------------------------------------------------------
try:  # pragma: no cover - 运行环境判断
    from PyQt5.QtCore import Qt, QTimer, QSize, QUrl
    from PyQt5.QtGui import QColor, QDesktopServices, QFont, QKeySequence
    from PyQt5.QtWidgets import (
        QAction, QActionGroup, QApplication, QDialog, QFileDialog, QHBoxLayout,
        QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
        QTabWidget, QToolBar, QVBoxLayout, QWidget,
    )
    import vtk
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtk.util import numpy_support
    from ice_icons import IceIcons
    from ice_panes import (
        DetailsDialog, LibraryTree, MessageWindow, PROJECT_NODES, ProjectTree,
        TdvStrip, WelcomeDialog,
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
        self._toolbars = {}
        self._tb_row = -1
        if show_welcome is None:
            show_welcome = bool(enable_3d and not path)
        self._pending_welcome = bool(show_welcome)

        self._build_ui()
        self._apply_style()
        self._setup_3d_overlays()
        if path:
            self.open_path(path)
        else:
            self.project_tree.reset_empty("untitled")
            self.log("This is the 64-bit version")
            self.log("ANSYS Icepak %s. Use File to open a project or .tzr."
                     % ICEPAK_VERSION)

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
        self.library_tree = LibraryTree(self)
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
            iren.AddObserver("LeftButtonPressEvent", self._on_pick)
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
        gh.addWidget(draw_body, 1)
        self.graphics = graphics

        self.message_win = MessageWindow(self)
        self.logger = self.message_win  # compat

        right = QSplitter(Qt.Vertical, self)
        right.addWidget(graphics)
        right.addWidget(self.message_win)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)
        right.setSizes([640, 140])
        self._right_split = right

        main = QSplitter(Qt.Horizontal, self)
        main.addWidget(self.nav_tabs)
        main.addWidget(right)
        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([260, 1340])
        self.setCentralWidget(main)

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

    def _build_menus(self):
        mb = self.menuBar()
        add = self._act

        # File
        m = mb.addMenu("File")
        add(m, "New project", self._new_project, "Ctrl+N", icon="new")
        add(m, "Open project", self._open_dir, "Ctrl+O", icon="open")
        add(m, "Merge project")
        add(m, "Reload main version", self._reload, "Ctrl+L")
        m.addSeparator()
        add(m, "Save project", self._save, "Ctrl+S", icon="save")
        add(m, "Save project as", self._save_as)
        m.addSeparator()
        imp = m.addMenu("Import")
        add(imp, "Import CSV/Excel")
        idf = imp.addMenu("IDF file")
        add(idf, "New board")
        add(idf, "Update board")
        add(imp, "Import IDX file")
        add(imp, "Import Electronics Cooling XML")
        imp.addSeparator()
        pmap = imp.addMenu("Powermaps")
        for t in ("Apache Sentinel TI profile", "Cadence tab file",
                  "Cadence Stacked Die tab files",
                  "Gradient Firebolt i2p file", "RedHawk CTM profile"):
            add(pmap, t)
        add(imp, "Import Networks")
        add(imp, "Import JEDEC PTD/JEP30 file")
        exp = m.addMenu("Export")
        add(exp, "ANSYS Electronics Desktop script")
        exp.addSeparator()
        add(exp, "Export CSV/Excel", self._export_csv)
        add(exp, "Export IDF file")
        add(exp, "Export Electronics Cooling XML")
        exp.addSeparator()
        add(exp, "Export Networks")
        add(exp, "Export JEDEC PTD/JEP30 file")
        em = m.addMenu("EM Mapping")
        add(em, "Volumetric heat losses")
        add(em, "Surface heat losses")
        m.addSeparator()
        add(m, "Unpack project", self._open_tzr)
        add(m, "Pack project")
        m.addSeparator()
        add(m, "Cleanup")
        add(m, "Print screen", self._print_screen, "Ctrl+P", icon="print")
        add(m, "Create image file", self._create_image, icon="image")
        add(m, "Command prompt", self._command_prompt)
        add(m, "Quit", self.close)

        # Edit
        m = mb.addMenu("Edit")
        add(m, "Undo", shortcut="Ctrl+Z", icon="undo")
        add(m, "Redo", shortcut="Ctrl+R", icon="redo")
        m.addSeparator()
        add(m, "Find", shortcut="Ctrl+F")
        add(m, "Show clipboard")
        add(m, "Clear clipboard")
        m.addSeparator()
        add(m, "Snap to grid")
        add(m, "Preferences")
        add(m, "Annotations")

        # View
        m = mb.addMenu("View")
        add(m, "Summary (HTML)")
        m.addSeparator()
        add(m, "Location")
        add(m, "Distance")
        add(m, "Angle")
        add(m, "Unit vector")
        add(m, "Unit normal")
        add(m, "Bounding box", self._show_bbox)
        m.addSeparator()
        tr = m.addMenu("Traces")
        add(tr, "Net info")
        add(tr, "Trace info")
        m.addSeparator()
        mk = m.addMenu("Markers")
        add(mk, "Add marker")
        add(mk, "Clear markers")
        rb = m.addMenu("Rubber bands")
        add(rb, "Add rubber band")
        add(rb, "Clear rubber bands")
        m.addSeparator()
        tbmenu = m.addMenu("Edit toolbars")
        self._tb_menu = tbmenu
        sh = m.addMenu("Default shading")
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
        for i, mode in enumerate(SHADING_MODES):
            if mode == "selected_solid":
                sh.addSeparator()
            a = QAction(labels[mode], self)
            a.setCheckable(True)
            a.setChecked(mode == self._shading)
            a.triggered.connect(lambda _=False, md=mode: self._set_shading(md))
            self._shading_group.addAction(a)
            sh.addAction(a)
            self._shading_actions[mode] = a
        disp = m.addMenu("Display")
        names = disp.addMenu("Object names")
        self._names_group = QActionGroup(self)
        for label, val in (("Current assembly object names", 1),
                           ("No object names", 0),
                           ("Selected object names", 2)):
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(val == 0)
            a.triggered.connect(lambda _=False, v=val: self._set_names(v))
            self._names_group.addAction(a)
            names.addAction(a)
        disp.addSeparator()
        self._act_axes = add(disp, "Coord axes", self._toggle_axes,
                             checkable=True, checked=True)
        add(disp, "Visible grid", checkable=True)
        add(disp, "Origin marker", checkable=True)
        add(disp, "Display rulers", checkable=True)
        add(disp, "Display project title", checkable=True)
        self._act_logo = add(disp, "Display ANSYS logo", self._toggle_logo,
                             checkable=True, checked=True)
        add(disp, "Display current date", checkable=True)
        add(disp, "Display construction lines", checkable=True)
        add(disp, "Display construction points", checkable=True)
        add(disp, "Display mesh", checkable=True)
        add(disp, "Mouse position", checkable=True)
        add(disp, "Depthcue", checkable=True)
        add(disp, "Tcl console", checkable=True)
        vis = m.addMenu("Visible")
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
            vis.addAction(a)
            self._layer_actions[kind] = a
        m.addSeparator()
        add(m, "Lights")

        # Orient
        m = mb.addMenu("Orient")
        add(m, "Home position", self._home, "H", icon="home")
        add(m, "Isometric view", lambda: self._orient("iso"), icon="iso")
        add(m, "Orient positive X", lambda: self._orient("+x"))
        add(m, "Orient negative X", lambda: self._orient("-x"), icon="axis_x")
        add(m, "Orient positive Y", lambda: self._orient("+y"), icon="axis_y")
        add(m, "Orient negative Y", lambda: self._orient("-y"))
        add(m, "Orient positive Z", lambda: self._orient("+z"))
        add(m, "Orient negative Z", lambda: self._orient("-z"), icon="axis_z")
        add(m, "Zoom in", self._zoom_in, "Z", icon="zoom")
        add(m, "Scale to fit", self._fit, "S", icon="fit")
        add(m, "Reverse orientation", self._reverse_orient, icon="reverse")
        add(m, "Nearest axis", self._nearest_axis)
        add(m, "Save user view")
        add(m, "Clear user views")
        add(m, "Write user views to file")
        add(m, "Read user views from file")

        # Macros (dynamic in Icepak; skeleton + documented entries)
        m = mb.addMenu("Macros")
        for t in ("ATX / Micro-ATX chassis", "Angled Fin Heat Sink",
                  "PCB", "Polygonal ducts", "Heat sink creation",
                  "Detailed heat sink creation", "Heat Pipe"):
            add(m, t)

        # Model
        m = mb.addMenu("Model")
        cr = m.addMenu("Create object")
        for kind, title, cmd in CREATE_OBJECT_TYPES:
            add(cr, title, lambda _=False, k=kind, c=cmd: self._nyi(c),
                icon=kind)
        m.addSeparator()
        add(m, "Radiation form factors")
        m.addSeparator()
        add(m, "Generate mesh", icon="mesh")
        m.addSeparator()
        add(m, "Edit priorities")
        add(m, "Edit cutouts")
        add(m, "Create material library")
        add(m, "Power and temperature limits", icon="limits")
        m.addSeparator()
        add(m, "Check model", self._check_model, icon="check")
        add(m, "Show objects by material")
        add(m, "Show objects by property")
        add(m, "Show objects by type")
        add(m, "Show metal fractions")

        # Solve
        m = mb.addMenu("Solve")
        st = m.addMenu("Settings")
        add(st, "Basic settings", self._show_basic_settings)
        add(st, "Advanced settings")
        add(st, "Parallel settings")
        add(m, "Patch temperatures")
        m.addSeparator()
        add(m, "Run solution", icon="solve")
        add(m, "Run optimization", icon="optim")
        add(m, "Create Krylov ROM")
        m.addSeparator()
        add(m, "Solution monitor")
        m.addSeparator()
        add(m, "Define trials")
        add(m, "Define report")
        m.addSeparator()
        diag = m.addMenu("Diagnostics")
        add(diag, "Edit .cas file")
        add(diag, "Edit .diag file")
        add(diag, "Edit .uns_out file")
        add(diag, "Edit optimization log")

        # Post
        m = mb.addMenu("Post")
        add(m, "Object face (node)", icon="face")
        add(m, "Object face (facet)", icon="face")
        add(m, "Plane cut", icon="plane")
        add(m, "Isosurface", icon="iso_surf")
        add(m, "Point", icon="point")
        add(m, "Surface probe", icon="probe")
        add(m, "Min/max locations")
        m.addSeparator()
        add(m, "Convergence plot")
        add(m, "Variation plot", icon="plot")
        add(m, "3D Variation plot")
        add(m, "History plot", icon="history")
        add(m, "Trials plot", icon="trials")
        add(m, "Network temperature plot")
        m.addSeparator()
        add(m, "Transient settings", icon="transient")
        add(m, "Load solution ID", icon="sol_id")
        add(m, "Postprocessing units")
        add(m, "Load post objects from file")
        add(m, "Save post objects to file")
        add(m, "Rescale vectors")
        m.addSeparator()
        add(m, "Create zoom-in model")
        add(m, "Power and temperature values")
        wf = m.addMenu("Workflow data")
        add(wf, "CFD Post/Mechanical")
        add(m, "Display powermap property")

        # Report
        m = mb.addMenu("Report")
        add(m, "HTML report", icon="report")
        ov = m.addMenu("Solution overview")
        add(ov, "View solution overview")
        add(ov, "Create solution overview")
        add(m, "Show optimization/param results")
        m.addSeparator()
        add(m, "Summary report", icon="report")
        add(m, "Point report")
        add(m, "Full report")
        m.addSeparator()
        add(m, "Network block values")
        add(m, "Fan operating points")
        add(m, "EM heat losses")
        add(m, "Solar loads")
        m.addSeparator()
        add(m, "Write Autotherm file")
        m.addSeparator()
        rexp = m.addMenu("Export")
        for t in ("Gradient Firebolt p2i file", "Cadence TPKG file",
                  "SIwave temp data", "Sentinel TI HTC file",
                  "RedHawk Back Annotation"):
            add(rexp, t)

        # Windows
        m = mb.addMenu("Windows")
        self._act_show_msg = add(m, "Message", self._toggle_message,
                                 checkable=True, checked=True)
        self._act_show_nav = add(m, "Project", self._toggle_nav,
                                 checkable=True, checked=True)

        # Help
        m = mb.addMenu("Help")
        add(m, "Help", self._help, "F1")
        add(m, "Icepak on the Web", self._web_icepak)
        add(m, "Customer Portal", self._web_portal)
        add(m, "List shortcuts", self._list_shortcuts)
        m.addSeparator()
        add(m, "About Icepak", self._about)

        # Extra hotkeys (Icepak command_set_hotkeys) — window actions, not menus
        add(self, "Edit object or postprocessing object",
            self._edit_current, "Ctrl+E")
        for text, sc, slot in (
            ("Delete object", "Delete", self._delete_current),
            ("Toggle object active", "Ctrl+A", None),
            ("Toggle object visible", "Ctrl+V", self._toggle_selected_visible),
            ("Toggle object shading", "Ctrl+H", None),
            ("Open/close tree node", "Ctrl+T", None),
            ("Open/close model subtree", "Ctrl+M", None),
            ("Move object", "Ctrl+X", None),
            ("Copy object", "Ctrl+C", None),
            ("Toggle shading type", "Ctrl+W", self._cycle_shading),
        ):
            add(self, text, slot, sc)

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
        return a

    def _build_toolbars(self):
        # Row 1
        tb = self._tb("File commands", 0)
        self._tb_act(tb, "New project", self._new_project, "new")
        self._tb_act(tb, "Open project", self._open_dir, "open")
        self._tb_act(tb, "Save project", self._save, "save")
        self._tb_act(tb, "Print screen", self._print_screen, "print")
        self._tb_act(tb, "Create image file", self._create_image, "image")

        tb = self._tb("Edit commands", 0)
        self._tb_act(tb, "Undo", icon="undo")
        self._tb_act(tb, "Redo", icon="redo")

        tb = self._tb("Viewing options", 0)
        self._tb_act(tb, "Home position", self._home, "home")
        self._tb_act(tb, "Zoom in", self._zoom_in, "zoom")
        self._tb_act(tb, "Scale to fit", self._fit, "fit")
        self._tb_act(tb, "Rotate about screen normal", self._rotate_normal,
                     "rotate")
        self._tb_act(tb, "One viewing window", icon="win1")
        self._tb_act(tb, "Four viewing windows", icon="win4")
        self._tb_act(tb, "Display object names", icon="names")

        tb = self._tb("Orientation commands", 0)
        self._tb_act(tb, "Orient negative X", lambda: self._orient("-x"),
                     "axis_x")
        self._tb_act(tb, "Orient positive Y", lambda: self._orient("+y"),
                     "axis_y")
        self._tb_act(tb, "Orient negative Z", lambda: self._orient("-z"),
                     "axis_z")
        self._tb_act(tb, "Isometric view", lambda: self._orient("iso"), "iso")
        self._tb_act(tb, "Reverse orientation", self._reverse_orient, "reverse")

        # Row 2
        tb = self._tb("Model and solve", 1)
        self._tb_act(tb, "Power and temperature limits", icon="limits")
        self._tb_act(tb, "Generate mesh", icon="mesh")
        self._tb_act(tb, "Radiation", icon="radiation")
        self._tb_act(tb, "Check model", self._check_model, "check")
        self._tb_act(tb, "Run solution", icon="solve")
        self._tb_act(tb, "Run optimization", icon="optim")

        tb = self._tb("Postprocessing", 1)
        self._tb_act(tb, "Object face", icon="face")
        self._tb_act(tb, "Plane cut", icon="plane")
        self._tb_act(tb, "Isosurface", icon="iso_surf")
        self._tb_act(tb, "Point", icon="point")
        self._tb_act(tb, "Surface probe", icon="probe")
        self._tb_act(tb, "Variation plot", icon="plot")
        self._tb_act(tb, "History plot", icon="history")
        self._tb_act(tb, "Trials plot", icon="trials")
        self._tb_act(tb, "Transient settings", icon="transient")
        self._tb_act(tb, "Load solution ID", icon="sol_id")
        self._tb_act(tb, "Summary report", icon="report")
        self._tb_act(tb, "Power and temperature values", icon="limits")

        # Row 3 object_tools
        tb = self._tb("Object creation", 2)
        for kind, title, cmd in CREATE_OBJECT_TYPES:
            self._tb_act(tb, title, lambda _=False, c=cmd: self._nyi(c), kind)

        tb = self._tb("Object modification", 2)
        self._tb_act(tb, "Edit object", self._edit_current, "edit")
        self._tb_act(tb, "Delete object", self._delete_current, "delete")
        self._tb_act(tb, "Move object", icon="move")
        self._tb_act(tb, "Copy object", icon="copy")

        tb = self._tb("Alignment", 2)
        for t in ("Align and morph faces", "Align and morph edges",
                  "Align and morph vertices", "Align object centers",
                  "Align face centers", "Morph faces", "Morph edges"):
            self._tb_act(tb, t, icon="align")

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

    def _new_project(self):
        self.project = None
        self.root_path = None
        self.project_tree.reset_empty("untitled")
        self.setWindowTitle(ICEPAK_TITLE + " — untitled")
        self.scene_objs = []
        self.actors = []
        self._actor_map = {}
        if self._enable_3d and self.renderer is not None:
            self.renderer.RemoveAllViewProps()
            if self._logo_actor is not None and self._show_logo:
                self.renderer.AddActor2D(self._logo_actor)
            self._render()
        self.log("New project")
        self.statusBar().showMessage("untitled")

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

    def _save(self):
        self._nyi("Save project")

    def _save_as(self):
        self._nyi("Save project as")

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
        self.project_tree.populate(proj)
        if self._enable_3d:
            self._rebuild_scene()
            self._fit()
        self.statusBar().showMessage(proj.name)

    # ------------------------------------------------------------- tree
    def _on_object_selected(self, o):
        self._highlight_object(o.name)
        self.log("Selected: %s (%s)" % (o.name, o.kind))

    def _on_object_activated(self, o):
        self._show_object_dialog(o)
        self._focus_object(o.name)

    def _on_node_selected(self, tag, payload):
        if tag == "setter" and payload:
            self.log("Parameter %s" % payload[0])
        elif tag == "group":
            self.log("Type %s" % payload)
        elif tag == "node":
            self.log(str(payload or tag))

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
        items = self.project_tree.selectedItems()
        if not items:
            return
        role = items[0].data(0, Qt.UserRole)
        if role and role[0] == "object":
            self._show_object_dialog(role[1])

    def _delete_current(self):
        self._nyi("Delete object")

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
        self._show_names = val
        self.log("Object names display = %s" % val, "DEBUG")

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
                           if so.name not in self._hidden]
        self.renderer.RemoveAllViewProps()
        if self._logo_actor is not None and self._show_logo:
            self.renderer.AddActor2D(self._logo_actor)
        self.actors = []
        self._actor_map = {}
        for so in self.scene_objs:
            actor = self._make_actor(so)
            self.renderer.AddActor(actor)
            self.actors.append((actor, so))
            self._actor_map[actor] = so
        self._apply_highlight()
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
        if self._shading == "selected_solid":
            self._rebuild_scene()
            return
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

    def _orient(self, which):
        if not self._enable_3d:
            return
        b = self._scene_bounds()
        if b is None:
            cx = cy = cz = 0.0
            span = 1.0
        else:
            cx = (b[0] + b[3]) / 2.0
            cy = (b[1] + b[4]) / 2.0
            cz = (b[2] + b[5]) / 2.0
            span = max(b[3] - b[0], b[4] - b[1], b[5] - b[2], 1e-6)
        cam = self.renderer.GetActiveCamera()
        cam.SetFocalPoint(cx, cy, cz)
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
        cam.SetPosition(*pos)
        cam.SetViewUp(*up)
        cam.ParallelProjectionOn()
        cam.SetParallelScale(span * 0.75)
        self.renderer.ResetCameraClippingRange()
        self._render()

    def _render(self):
        if self._enable_3d and self.vtk_widget is not None:
            self.vtk_widget.GetRenderWindow().Render()

    def _on_pick(self, obj, ev):
        if not self._enable_3d:
            return
        if self.tdv_strip.mode() not in ("pick", "boxpick"):
            return
        x, y = obj.GetEventPosition()
        picker = vtk.vtkPropPicker()
        if picker.Pick(x, y, 0, self.renderer):
            actor = picker.GetActor()
            so = self._actor_map.get(actor)
            if so is not None:
                self._highlight_object(so.name)
                self.log("Selected: %s (%s)" % (so.name, so.kind))

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
            self._new_project()
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
