# -*- coding: utf-8 -*-
"""ice_gui.py — ANSYS Icepak 项目文件/目录查看器.

技术路线参照 D:/training/cgns/cabdecoding:
  * GUI:   PyQt5 (QMainWindow + QSplitter 左右布局 + 菜单/工具栏/状态栏)
  * 3D:    VTK QVTKRenderWindowInteractor, 每对象一个 vtkActor
  * 几何:  由 model 文件的 shape/setval 解析出包围盒/圆柱/多边形,
           numpy 生成顶点+单元, vtkPolyData 送入渲染器
  * 交互:  TrackballCamera 旋转缩放, 鼠标拾取对象高亮, Fit/重置相机
  * 渲染:  Shading / Line(线框) / Translucent(半透明) 三种模式, 按对象类型分层开关

用法:
    python ice_gui.py                    # 启动后 File->Open Directory / Open .tzr
    python ice_gui.py D:/training/icepak                 # 直接打开项目目录
    python ice_gui.py D:/training/icepak/avonics.tzr     # 直接打开归档
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
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import QColor, QFont
    from PyQt5.QtWidgets import (
        QAction, QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
        QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
        QTableWidget, QTableWidgetItem, QToolBar, QTreeWidget, QTreeWidgetItem,
        QComboBox, QCheckBox, QVBoxLayout, QWidget,
    )
    import vtk
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtk.util import numpy_support
    HAS_GUI = True
except Exception:  # pragma: no cover
    HAS_GUI = False

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
# 4. GUI
# ===========================================================================

class MessageLog(QPlainTextEdit):
    """底部消息日志."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2000)
        f = QFont("Consolas", 9)
        self.setFont(f)

    def log(self, msg, level="INFO"):
        self.appendPlainText("[%s] %s" % (level, msg))


class DetailsTable(QTableWidget):
    """属性键值表."""
    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["属性", "值"])
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)

    def fill(self, rows):
        self.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.setItem(r, 0, QTableWidgetItem(str(k)))
            self.setItem(r, 1, QTableWidgetItem(str(v)))
        self.resizeRowsToContents()
        self.resizeColumnToContents(0)


class IceGui(QMainWindow):
    """主窗口."""

    def __init__(self, path=None, enable_3d: bool = True):
        if not HAS_GUI:
            raise RuntimeError(
                "PyQt5 / vtk 未安装: python -m pip install PyQt5 vtk numpy")
        super().__init__()
        self._enable_3d = enable_3d
        self.setWindowTitle("ice_gui — ANSYS Icepak 项目查看器")
        self.resize(1500, 880)

        self.root_path = None
        self.projects = []           # [(name, kind, source)]
        self.project = None          # 当前 IcepakProject
        self.scene_objs = []         # SceneObject 列表
        self.actors = []             # [(vtkActor, SceneObject)]
        self._actor_map = {}         # id(actor) -> SceneObject
        self.selected = None         # 当前选中 SceneObject 名
        self._wireframe = False
        self._translucent = False
        self._show_axes = True
        self._fit_pending = False
        self._rendering = False

        self._build_ui()
        self._build_axes()
        if path:
            self.open_path(path)

    # ------------------------------------------------------------- UI 构建
    def _build_ui(self):
        self._build_menus()
        self._build_toolbar()

        # 左侧: 项目树
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Icepak 项目 / 对象"])
        self.tree.itemSelectionChanged.connect(self._on_tree_selected)
        self.tree.itemDoubleClicked.connect(self._on_tree_double)

        # 右侧: 3D + 属性 + 日志
        if self._enable_3d:
            self.vtk_widget = QVTKRenderWindowInteractor(self)
            self.renderer = vtk.vtkRenderer()
            self.renderer.SetBackground(0.93, 0.93, 0.94)
            self.renderer.SetBackground2(0.78, 0.82, 0.90)
            self.renderer.GradientBackgroundOn()
            self.renderer.GetActiveCamera().ParallelProjectionOn()
            self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
            self.vtk_widget.GetRenderWindow().GetInteractor().SetInteractorStyle(
                vtk.vtkInteractorStyleTrackballCamera())
            self.vtk_widget.GetRenderWindow().GetInteractor().AddObserver(
                "LeftButtonPressEvent", self._on_pick)
            self.vtk_widget.GetRenderWindow().GetInteractor().AddObserver(
                "RightButtonPressEvent", self._on_right_press)
        else:
            self.vtk_widget = None
            self.renderer = None
            self._label_3d = QLabel("3D 视图已禁用（headless 测试模式）", self)
            self._label_3d.setAlignment(Qt.AlignCenter)

        self.details = DetailsTable(self)
        self.logger = MessageLog(self)
        self.logger.log("ice_gui 就绪。File->Open Directory 打开项目目录。")

        right_top = QWidget(self)
        lt = QVBoxLayout(right_top)
        lt.setContentsMargins(0, 0, 0, 0)
        lt.addWidget(self.vtk_widget if self._enable_3d else self._label_3d, 1)
        lt.addWidget(QLabel("属性", self))
        lt.addWidget(self.details, 1)

        right = QSplitter(Qt.Vertical, self)
        right.addWidget(right_top)
        right.addWidget(self.logger)
        right.setStretchFactor(0, 4)
        right.setStretchFactor(1, 1)
        right.setSizes([620, 150])

        main = QSplitter(Qt.Horizontal, self)
        main.addWidget(self.tree)
        main.addWidget(right)
        main.setStretchFactor(0, 0)
        main.setStretchFactor(1, 1)
        main.setSizes([330, 1100])
        self.setCentralWidget(main)

        self.statusBar().showMessage("未打开项目")

    def _build_menus(self):
        mb = self.menuBar()

        def add(menu, text, slot=None, shortcut=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            if slot:
                a.triggered.connect(slot)
            menu.addAction(a)
            return a

        m = mb.addMenu("文件(&F)")
        add(m, "打开项目目录…", self._open_dir, "Ctrl+O")
        add(m, "打开 .tzr 归档…", self._open_tzr, "Ctrl+T")
        add(m, "重新载入", self._reload, "F5")
        m.addSeparator()
        add(m, "退出", self.close, "Ctrl+Q")

        m = mb.addMenu("视图(&V)")
        self._act_fit = add(m, "适应窗口", self._fit, "F")
        add(m, "重置相机", self._reset_camera)
        m.addSeparator()
        self._act_axes = QAction("显示坐标轴", self)
        self._act_axes.setCheckable(True)
        self._act_axes.setChecked(self._show_axes)
        self._act_axes.toggled.connect(self._toggle_axes)
        m.addAction(self._act_axes)
        m.addSeparator()

        # 图层开关
        m2 = m.addMenu("对象图层")
        self._layer_actions = {}
        for k in ALL_KINDS:
            a = QAction(k, self)
            a.setCheckable(True)
            a.setChecked(True)
            a.toggled.connect(
                lambda on, kk=k: self._on_layer_toggle(kk, on))
            m2.addAction(a)
            self._layer_actions[k] = a

        m.addSeparator()
        self._act_wire = QAction("线框模式", self)
        self._act_wire.setCheckable(True)
        self._act_wire.toggled.connect(self._on_wire_toggle)
        m.addAction(self._act_wire)
        self._act_trans = QAction("半透明模式", self)
        self._act_trans.setCheckable(True)
        self._act_trans.toggled.connect(self._on_trans_toggle)
        m.addAction(self._act_trans)

    def _build_toolbar(self):
        tb = QToolBar("主工具栏", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(QAction("打开目录", self, triggered=self._open_dir))
        tb.addAction(QAction("打开 .tzr", self, triggered=self._open_tzr))
        tb.addAction(QAction("适应", self, triggered=self._fit))
        tb.addSeparator()
        self._mode_combo = QComboBox(self)
        self._mode_combo.addItems(["Shading", "Line", "Translucent"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_change)
        tb.addWidget(QLabel(" 渲染:", self))
        tb.addWidget(self._mode_combo)

    # ------------------------------------------------------------- 打开
    def open_path(self, path):
        if os.path.isdir(path):
            self._load_directory(path)
        elif path.lower().endswith(".tzr") or path.lower().endswith(".tar"):
            self._load_archive(path)
        elif os.path.isfile(path):
            self.logger.log("仅支持目录或 .tzr 归档: %s" % path, "WARN")

    def _open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择 Icepak 项目目录",
                                             self.root_path or os.getcwd())
        if d:
            self._load_directory(d)

    def _open_tzr(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 .tzr 归档",
                                           self.root_path or os.getcwd(),
                                           "Icepak 归档 (*.tzr *.tar)")
        if f:
            self._load_archive(f)

    def _reload(self):
        if self.project is not None:
            self.open_path(getattr(self.project, "path", None) or "")

    def _load_directory(self, root):
        self.root_path = root
        entries = find_projects(root)
        self.projects = entries
        self.tree.clear()
        root_item = QTreeWidgetItem(["%s (%d 个项目)" % (os.path.basename(
            os.path.normpath(root)), len(entries))])
        self.tree.addTopLevelItem(root_item)
        for name, kind, source in entries:
            item = QTreeWidgetItem(root_item)
            item.setText(0, ("[tzr] " if kind == "tzr" else "") + name)
            item.setData(0, Qt.UserRole, ("project", source))
            item.setToolTip(0, source)
        root_item.setExpanded(True)
        self.logger.log("已扫描 %d 个项目: %s" % (len(entries), root))
        self.statusBar().showMessage("打开目录: %s" % root)
        if entries:
            # 自动载入第一个项目
            self._load_project(entries[0])

    def _load_archive(self, path):
        self.root_path = os.path.dirname(path)
        self.tree.clear()
        item = QTreeWidgetItem(["[tzr] " + os.path.basename(path)])
        item.setData(0, Qt.UserRole, ("project", path))
        self.tree.addTopLevelItem(item)
        self._load_project((os.path.basename(path), "tzr", path))

    # ------------------------------------------------------------- 项目载入
    def _load_project(self, entry):
        name, kind, source = entry
        from icepak_parser import project as projmod
        try:
            if kind == "tzr":
                proj = projmod.IcepakProject.from_archive(source)
            else:
                proj = projmod.IcepakProject(source)
        except Exception as e:
            self.logger.log("载入失败 %s: %r" % (source, e), "ERROR")
            return
        self.project = proj
        self.logger.log("载入项目: %s (%d 对象, %d setters)" % (
            proj.name, proj.summary().get("objects", 0),
            proj.summary().get("setters", 0)))
        self._populate_project_tree(proj)
        if self._enable_3d:
            self._rebuild_scene()
            self._fit()

    def _populate_project_tree(self, proj):
        """把已打开的项目挂到树根部(替换原扫描列表为项目详情)."""
        top = self.tree.topLevelItem(0)
        if top is None:
            top = QTreeWidgetItem([proj.name])
            self.tree.addTopLevelItem(top)
        else:
            top.setText(0, proj.name)
            while top.childCount():
                top.removeChild(top.child(0))
        self.tree.setHeaderLabels(["%s — 对象与设置" % proj.name])

        # 对象(按类型分组)
        if proj.model is not None:
            obj_node = QTreeWidgetItem(top, ["对象 (%d)" % (
                proj.model.count_all())])
            obj_node.setData(0, Qt.UserRole, ("node", "objects"))
            counts = proj.model.kind_counts()
            for kind in sorted(counts, key=lambda k: -counts[k]):
                grp = QTreeWidgetItem(obj_node, ["%s (%d)" % (
                    kind, counts[kind])])
                grp.setData(0, Qt.UserRole, ("group", kind))
                for o in proj.model._all_objects():
                    if o.kind != kind:
                        continue
                    it = QTreeWidgetItem(grp, [o.name])
                    it.setData(0, Qt.UserRole, ("object", o))
                    tip = "shape=%s" % (o.shape.type if o.shape else "-")
                    it.setToolTip(0, tip)
                grp.setExpanded(True)
            obj_node.setExpanded(True)

        # problem 变量
        if proj.problem is not None:
            prb = proj.problem
            p_node = QTreeWidgetItem(top, ["问题设置 (%d)" % len(prb.setters)])
            p_node.setData(0, Qt.UserRole, ("node", "problem"))
            for k, v in sorted(prb.setters.items()):
                it = QTreeWidgetItem(p_node, ["%s = %s" % (k, v)])
                it.setData(0, Qt.UserRole, ("setter", (k, v)))
                if len(it.text(0)) > 100:
                    it.setText(0, it.text(0)[:100] + "…")
            p_node.setExpanded(False)

        # 文件
        files = []
        if kind_from := getattr(self.project, "path", None):
            if os.path.isdir(kind_from):
                try:
                    files = sorted(os.listdir(kind_from))
                except OSError:
                    pass
            else:
                files = []
        f_node = QTreeWidgetItem(top, ["文件 (%d)" % len(files)])
        f_node.setData(0, Qt.UserRole, ("node", "files"))
        for fname in files:
            it = QTreeWidgetItem(f_node, [fname])
            it.setData(0, Qt.UserRole, ("file", fname))
        f_node.setExpanded(False)

    # ------------------------------------------------------------- 树交互
    def _on_tree_selected(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        role = item.data(0, Qt.UserRole)
        if not role:
            return
        tag = role[0]
        if tag == "object":
            self._show_object(role[1])
        elif tag == "setter":
            self._show_setter(role[1])
        elif tag == "project":
            self._load_project(("dir" if os.path.isdir(role[1])
                                else "tzr", role[1]))
        elif tag == "group":
            self._show_group(role[1])
        elif tag == "node":
            self._show_node(role[1])
        elif tag == "file":
            self._show_file(role[1])

    def _on_tree_double(self, item, _col):
        role = item.data(0, Qt.UserRole)
        if role and role[0] == "object":
            self._focus_object(role[1].name)
        elif role and role[0] == "project":
            self._load_project(("dir" if os.path.isdir(role[1])
                                else "tzr", role[1]))

    def _show_object(self, o):
        rows = [("类型", o.kind), ("名称", o.name), ("创建顺序",
                o.properties.get("creation_order", [""])[0])]
        for k in ("current_stype", "grid_priority", "block_type",
                  "plate_type", "temp", "current_genus"):
            if k in o.properties:
                rows.append((k, " ".join(o.properties[k])))
        if o.shape:
            rows.append(("形状", o.shape.type))
            for k, v in o.shape.setvals.items():
                rows.append(("setval " + k, " ".join(v)))
        self.details.fill(rows)
        self._highlight_object(o.name)

    def _show_setter(self, kv):
        self.details.fill([("变量", kv[0]), ("值", kv[1])])

    def _show_group(self, kind):
        self.details.fill([("对象类型", kind),
                           ("颜色", str(kind_color(kind)))])

    def _show_node(self, tag):
        if tag == "objects" and self.project is not None:
            rows = [("对象总数", self.project.summary().get("objects", 0))]
            for k, v in sorted(self.project.model.kind_counts().items()):
                rows.append(("  " + k, v))
            self.details.fill(rows)
        elif tag == "problem" and self.project is not None:
            p = self.project.problem
            rows = [("setters", len(p.setters)), ("arrays", len(p.arrays))]
            for k in ("problem_time", "problem_nsteps", "problem_temp",
                      "problem_opressure", "problem_turbmodel"):
                if p.value(k) is not None:
                    rows.append((k, p.value(k)))
            self.details.fill(rows)
        elif tag == "files":
            if getattr(self.project, "files", None):
                rows = [("文件数", len(self.project.files))]
                for f in sorted(self.project.files)[:40]:
                    rows.append(("  " + f, "%d B" % len(
                        self.project.files[f])))
                if len(self.project.files) > 40:
                    rows.append(("  …", "…"))
                self.details.fill(rows)
            elif self.project is not None and os.path.isdir(
                    getattr(self.project, "path", "") or ""):
                try:
                    fl = sorted(os.listdir(self.project.path))
                except OSError:
                    fl = []
                self.details.fill([("文件数", len(fl))] +
                                  [("  " + f, "") for f in fl[:60]])

    def _show_file(self, fname):
        files = getattr(self.project, "files", None)
        if files and fname in files:
            self.details.fill([("文件", fname),
                               ("大小", "%d 字节" % len(files[fname])),
                               ("来源", "归档 %s" % self.project.name)])
            return
        base = getattr(self.project, "path", None)
        if not base:
            return
        p = os.path.join(base, fname)
        try:
            sz = os.path.getsize(p)
        except OSError:
            sz = 0
        self.details.fill([("文件", fname), ("大小", "%d 字节" % sz)])

    # ------------------------------------------------------------- 3D 渲染
    def _on_wire_toggle(self, on):
        if on:
            self._act_trans.setChecked(False)
        self._rebuild_scene()

    def _on_trans_toggle(self, on):
        if on:
            self._act_wire.setChecked(False)
        self._rebuild_scene()

    def _on_mode_change(self, text):
        if text == "Line":
            self._act_wire.setChecked(True)
        elif text == "Translucent":
            self._act_trans.setChecked(True)
        else:
            self._act_wire.setChecked(False)
            self._act_trans.setChecked(False)
        self._rebuild_scene()

    def _on_layer_toggle(self, kind, on):
        self._rebuild_scene()

    def _toggle_axes(self, on):
        self._show_axes = on
        if self._enable_3d and hasattr(self, "_axes_actor"):
            self._axes_actor.SetVisibility(1 if on else 0)
            self._render()

    def _build_axes(self):
        self._axes_actor = None
        if not self._enable_3d:
            return
        pd = self._axes_polydata()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(pd)
        self._axes_actor = vtk.vtkActor()
        self._axes_actor.SetMapper(mapper)
        self._axes_actor.SetVisibility(0)
        self.renderer.AddActor(self._axes_actor)

    @staticmethod
    def _axes_polydata():
        pts = np.array([
            [0, 0, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0],
            [0, 0, 0], [0, 0, 1],
        ], dtype=float)
        cells = np.array([[0, 1], [2, 3], [4, 5]], dtype=np.int64)
        return _polydata(pts, cells, "lines")

    def _rebuild_scene(self):
        if (not self._enable_3d or self.project is None
                or self.project.model is None):
            return
        self._wireframe = self._act_wire.isChecked()
        self._translucent = self._act_trans.isChecked()
        layer_on = {k: self._layer_actions[k].isChecked()
                    for k in ALL_KINDS}
        self.scene_objs = build_scene(self.project.model, layer_on,
                                      self._wireframe)
        self.renderer.RemoveAllViewProps()
        if self._show_axes and self._axes_actor is not None:
            self.renderer.AddActor(self._axes_actor)
        self.actors = []
        self._actor_map = {}
        for so in self.scene_objs:
            actor = self._make_actor(so)
            self.renderer.AddActor(actor)
            self.actors.append((actor, so))
            self._actor_map[actor] = so
        self._apply_highlight()
        self._render()
        self.logger.log("3D 场景: %d 个对象" % len(self.scene_objs))

    def _make_actor(self, so):
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(so.polydata)
        mapper.ScalarVisibilityOff()
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*so.color)
        if self._translucent and not self._wireframe:
            prop.SetOpacity(0.45)
        prop.SetAmbient(0.25)
        prop.SetDiffuse(0.85)
        prop.SetSpecular(0.25)
        prop.SetSpecularPower(18)
        if self._wireframe:
            prop.SetRepresentationToWireframe()
            prop.SetLineWidth(1.1)
            prop.LightingOff()
            prop.SetAmbient(1.0)
        actor.SetVisibility(1)
        return actor

    def _apply_highlight(self):
        if not self._enable_3d or self.selected is None:
            return
        for actor, so in self.actors:
            if so.name == self.selected:
                actor.GetProperty().SetColor(1.0, 0.25, 0.1)
            elif self._translucent and not self._wireframe:
                actor.GetProperty().SetOpacity(0.45)

    def _highlight_object(self, name):
        self.selected = name
        self._apply_highlight()
        self._render()

    def _focus_object(self, name):
        for so in self.scene_objs:
            if so.name == name:
                self._camera_to_bounds(so.bounds)
                return

    # ------------------------------------------------------------- 相机
    def _scene_bounds(self):
        if not self.scene_objs:
            return None
        b = np.array([so.bounds for so in self.scene_objs])
        lo = b[:, 0:3].min(axis=0)
        hi = b[:, 3:6].max(axis=0)
        return np.concatenate([lo, hi])

    def _camera_to_bounds(self, b):
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
        if not self._enable_3d:
            return
        b = self._scene_bounds()
        if b is not None:
            self._camera_to_bounds(b)

    def _reset_camera(self):
        if not self._enable_3d:
            return
        self.renderer.GetActiveCamera().SetPosition(1, 1, 1)
        self.renderer.GetActiveCamera().SetViewUp(0, 0, 1)
        self.renderer.ResetCamera()
        self._render()

    # ------------------------------------------------------------- 交互
    def _render(self):
        if self._enable_3d:
            self.vtk_widget.GetRenderWindow().Render()

    def _on_right_press(self, obj, ev):
        if not self._enable_3d:
            return
        self.renderer.GetActiveCamera().SetViewUp(0, 0, 1)
        self._render()

    def _on_pick(self, obj, ev):
        if not self._enable_3d:
            return
        iren = obj
        x, y = iren.GetEventPosition()
        picker = vtk.vtkPropPicker()
        if picker.Pick(x, y, 0, self.renderer):
            actor = picker.GetActor()
            so = self._actor_map.get(actor)
            if so is not None:
                self.selected = so.name
                self._apply_highlight()
                self._render()
                # 同步树选中
                self._select_in_tree(so.name)
                self.logger.log("选中: %s (%s)" % (so.name, so.kind))

    def _select_in_tree(self, name):
        def walk(item):
            role = item.data(0, Qt.UserRole)
            if role and role[0] == "object" and role[1].name == name:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if walk(item.child(i)):
                    return True
            return False
        for i in range(self.tree.topLevelItemCount()):
            if walk(self.tree.topLevelItem(i)):
                break

    # ------------------------------------------------------------- 事件
    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self._start_interactor)

    def _start_interactor(self):
        try:
            iren = self.vtk_widget.GetRenderWindow().GetInteractor()
            if not iren.GetInitialized():
                iren.Initialize()
        except Exception:
            pass
        if self._fit_pending:
            self._fit()
            self._fit_pending = False


# ===========================================================================
# 5. 入口
# ===========================================================================

def main(argv=None):
    if not HAS_GUI:
        print("PyQt5 / vtk 未安装: python -m pip install PyQt5 vtk numpy")
        return 1
    app = QApplication(argv if argv is not None else sys.argv)
    path = None
    args = argv if argv is not None else sys.argv
    if len(args) > 1:
        p = args[1]
        if os.path.isdir(p) or p.lower().endswith((".tzr", ".tar")):
            path = p
    win = IceGui(path)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())