# -*- coding: utf-8 -*-
"""Icepak-style panes: Welcome, Message, Project/Library trees, TDV strip."""

from __future__ import annotations

from datetime import datetime
import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QToolBar,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QPlainTextEdit, QButtonGroup, QSizePolicy,
)

from ice_icons import IceIcons

# Project tree top-level nodes, order locked to Icepak (menus / Chinese resources).
PROJECT_NODES = (
    "Problem setup",
    "Solution settings",
    "Groups",
    "Post-processing",
    "Points",
    "Surfaces",
    "Trash",
    "Inactive",
    "Model",
)

PROBLEM_CHILDREN = (
    "Basic parameters",
    "Title/notes",
    "Parameters and trials",
    "Local coords",
)

SOLUTION_CHILDREN = (
    "Basic settings",
    "Advanced settings",
    "Parallel settings",
)

NODE_ICONS = {
    "Problem setup": "folder",
    "Solution settings": "folder",
    "Groups": "group",
    "Post-processing": "plot",
    "Points": "point",
    "Surfaces": "plane",
    "Trash": "trash",
    "Inactive": "inactive",
    "Model": "domain",
}

TITLE_KEYS = ("title", "notes", "job_title", "problem_title")
SOLUTION_BASIC_KEYS = (
    "niterations", "flow_iterations", "energy_iterations", "problem_time",
    "time_step", "n_time_steps", "flow_regime", "temp_precision",
)
SOLUTION_ADV_KEYS = (
    "radiation", "solar_load", "gravity", "ambient_temp", "ambient_pressure",
)
SOLUTION_PAR_KEYS = (
    "nproc", "parallel", "npartitions", "hosts", "parallel_type",
)

ICEPAK_LIB_CANDIDATES = (
    r"C:\Program Files\ANSYS Inc\v195\Icepak\icepak19.5\icepak_lib",
)


class WelcomeDialog(QDialog):
    """Icepak cold-start dialog: Existing / New / Unpack / Quit."""

    existing = 0
    new = 1
    unpack = 2
    quit = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Icepak")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._choice = self.quit
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)
        msg = QLabel(
            "Do you want to open an existing project, create a new one, "
            "or unpack a .tzr file?", self)
        msg.setWordWrap(True)
        msg.setMinimumWidth(380)
        lay.addWidget(msg)
        row = QHBoxLayout()
        row.setSpacing(12)
        for text, icon, val in (
            ("Existing", "existing", self.existing),
            ("New", "new", self.new),
            ("Unpack", "unpack", self.unpack),
            ("Quit", "quit", self.quit),
        ):
            b = QPushButton(text, self)
            b.setIcon(IceIcons.get(icon, 32))
            b.setIconSize(QSize(32, 32))
            b.setMinimumSize(88, 64)
            b.clicked.connect(lambda _=False, v=val: self._pick(v))
            row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, val):
        self._choice = val
        if val == self.quit:
            self.reject()
        else:
            self.accept()

    def choice(self):
        return self._choice


class MessageWindow(QWidget):
    """Bottom Message pane: log text + Verbose / Log / Save."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        self.text.setFont(QFont("Consolas", 9))
        v.addWidget(self.text, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 4, 2)
        self.chk_verbose = QCheckBox("Verbose", self)
        self.chk_log = QCheckBox("Log", self)
        self.btn_save = QPushButton("Save", self)
        self.btn_save.setFixedWidth(64)
        self.btn_save.clicked.connect(self._save)
        bar.addWidget(self.chk_verbose)
        bar.addWidget(self.chk_log)
        bar.addWidget(self.btn_save)
        bar.addStretch(1)
        v.addLayout(bar)
        self._file_log = None

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s: %s" % (ts, level, msg)
        if level == "DEBUG" and not self.chk_verbose.isChecked():
            return
        self.text.appendPlainText(line)
        if self.chk_log.isChecked() and self._file_log:
            try:
                with open(self._file_log, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass

    def set_log_file(self, path):
        self._file_log = path

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save message log", "", "Text (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.text.toPlainText())
            except OSError:
                pass


class DetailsTable(QTableWidget):
    """Read-only key/value property table (Edit dialog body)."""

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Property", "Value"])
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


class DetailsDialog(QDialog):
    """Icepak-style Edit object dialog wrapping DetailsTable."""

    def __init__(self, title, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 420)
        v = QVBoxLayout(self)
        self.table = DetailsTable(self)
        self.table.fill(rows)
        v.addWidget(self.table, 1)
        btn = QPushButton("Done", self)
        btn.clicked.connect(self.accept)
        v.addWidget(btn, 0, Qt.AlignRight)


class TranslateDialog(QDialog):
    """Numeric Move / Copy offset dialog (Icepak-style dx dy dz)."""

    def __init__(self, title="Move object", parent=None, dx=0.0, dy=0.0, dz=0.0):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        form = QFormLayout(self)
        self.spx = QDoubleSpinBox(self)
        self.spy = QDoubleSpinBox(self)
        self.spz = QDoubleSpinBox(self)
        for sp, val in ((self.spx, dx), (self.spy, dy), (self.spz, dz)):
            sp.setDecimals(6)
            sp.setRange(-1e6, 1e6)
            sp.setSingleStep(0.01)
            sp.setValue(val)
        form.addRow("X offset", self.spx)
        form.addRow("Y offset", self.spy)
        form.addRow("Z offset", self.spz)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def offset(self):
        return (self.spx.value(), self.spy.value(), self.spz.value())


class ProjectTree(QTreeWidget):
    """Icepak Project tab: nine fixed nodes + Model objects."""

    object_selected = pyqtSignal(object)
    object_activated = pyqtSignal(object)
    node_selected = pyqtSignal(str, object)
    node_activated = pyqtSignal(str, object)
    visibility_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Project"])
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformRowHeights(True)
        self.itemSelectionChanged.connect(self._on_sel)
        self.itemDoubleClicked.connect(self._on_dbl)
        self.itemChanged.connect(self._on_item_changed)
        self._items = {}
        self.reset_empty()

    def reset_empty(self, root_name="untitled"):
        self.clear()
        self._items = {}
        root = QTreeWidgetItem([root_name])
        root.setData(0, Qt.UserRole, ("root", root_name))
        root.setIcon(0, IceIcons.get("folder", 16))
        self.addTopLevelItem(root)
        for name in PROJECT_NODES:
            it = QTreeWidgetItem(root, [name])
            it.setData(0, Qt.UserRole, ("node", name))
            it.setIcon(0, IceIcons.get(NODE_ICONS.get(name, "folder"), 16))
            self._items[name] = it
            if name == "Problem setup":
                for ch in PROBLEM_CHILDREN:
                    c = QTreeWidgetItem(it, [ch])
                    c.setData(0, Qt.UserRole, ("node", ch))
            elif name == "Solution settings":
                for ch in SOLUTION_CHILDREN:
                    c = QTreeWidgetItem(it, [ch])
                    c.setData(0, Qt.UserRole, ("node", ch))
        root.setExpanded(True)
        self._items["Model"].setExpanded(True)

    def _mark_object_item(self, it, obj, hidden):
        it.setData(0, Qt.UserRole, ("object", obj))
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        it.setCheckState(0, Qt.Unchecked if obj.name in hidden else Qt.Checked)

    def populate(self, project, hidden=None, inactive=None, trash=None,
                 groups=None):
        """Fill from IcepakProject. Keeps the nine fixed nodes."""
        hidden = set(hidden or ())
        inactive = set(inactive or ())
        trash = list(trash or [])
        groups = dict(groups or {})
        name = getattr(project, "name", None) or "untitled"
        self.blockSignals(True)
        try:
            self.reset_empty(name)
            self.setHeaderLabels([name])
            self._fill_model(project, hidden, inactive, trash)
            self._fill_problem_and_post(project)
            self._fill_groups_inactive_trash(project, groups, inactive, trash)
        finally:
            self.blockSignals(False)

    def _fill_problem_and_post(self, project):
        prb = getattr(project, "problem", None)
        if prb is not None and getattr(prb, "setters", None):
            basic = None
            parent = self._items["Problem setup"]
            for i in range(parent.childCount()):
                if parent.child(i).text(0) == "Basic parameters":
                    basic = parent.child(i)
                    break
            if basic is not None:
                for k, v in sorted(prb.setters.items()):
                    it = QTreeWidgetItem(basic, ["%s = %s" % (k, v)])
                    it.setData(0, Qt.UserRole, ("setter", (k, v)))
                    if len(it.text(0)) > 80:
                        it.setText(0, it.text(0)[:80] + "…")

        posts = getattr(project, "post", None) or []
        post_item = self._items["Post-processing"]
        for po in posts:
            label = "post"
            if isinstance(po, dict):
                params = po.get("params") or {}
                label = (params.get("-name") or params.get("name")
                         or po.get("name") or po.get("type") or "post")
            it = QTreeWidgetItem(post_item, [str(label)])
            it.setData(0, Qt.UserRole, ("post", po))
        if posts:
            post_item.setText(0, "Post-processing (%d)" % len(posts))
            post_item.setExpanded(True)

        self._items["Problem setup"].setExpanded(False)
        self._items["Solution settings"].setExpanded(False)

        sol = self._items["Solution settings"]
        prb = getattr(project, "problem", None)
        if prb is not None and getattr(prb, "setters", None):
            buckets = {
                "Basic settings": SOLUTION_BASIC_KEYS,
                "Advanced settings": SOLUTION_ADV_KEYS,
                "Parallel settings": SOLUTION_PAR_KEYS,
            }
            for child_name, keys in buckets.items():
                node = None
                for i in range(sol.childCount()):
                    if sol.child(i).text(0) == child_name:
                        node = sol.child(i)
                        break
                if node is None:
                    continue
                n = 0
                for k in keys:
                    if k in prb.setters:
                        it = QTreeWidgetItem(node, ["%s = %s" % (k, prb.setters[k])])
                        it.setData(0, Qt.UserRole, ("setter", (k, prb.setters[k])))
                        n += 1
                if n:
                    node.setText(0, "%s (%d)" % (child_name, n))

        title_node = None
        parent = self._items["Problem setup"]
        for i in range(parent.childCount()):
            if parent.child(i).text(0) == "Title/notes":
                title_node = parent.child(i)
                break
        if title_node is not None and prb is not None:
            for k in TITLE_KEYS:
                if getattr(prb, "setters", None) and k in prb.setters:
                    it = QTreeWidgetItem(title_node, ["%s = %s" % (k, prb.setters[k])])
                    it.setData(0, Qt.UserRole, ("setter", (k, prb.setters[k])))

    def _fill_model(self, project, hidden, inactive=None, trash=None):
        inactive = set(inactive or ())
        trash_names = {getattr(o, "name", None) for o in (trash or [])}
        model_item = self._items["Model"]
        model = getattr(project, "model", None)
        if model is None:
            model_item.setExpanded(True)
            return
        cabinet = None
        for o in model._all_objects():
            if o.kind == "domain":
                cabinet = o
                break
        cab_it = QTreeWidgetItem(model_item, ["Cabinet"])
        cab_it.setIcon(0, IceIcons.get("domain", 16))
        if cabinet is not None:
            self._mark_object_item(cab_it, cabinet, hidden)
            cab_it.setText(0, cabinet.name or "Cabinet")
        else:
            cab_it.setData(0, Qt.UserRole, ("node", "Cabinet"))

        by_kind = {}
        for o in model._all_objects():
            if o.kind == "domain":
                continue
            if o.name in inactive or o.name in trash_names:
                continue
            by_kind.setdefault(o.kind, []).append(o)
        for kind in sorted(by_kind, key=lambda k: -len(by_kind[k])):
            objs = by_kind[kind]
            grp = QTreeWidgetItem(model_item, ["%s (%d)" % (kind, len(objs))])
            grp.setData(0, Qt.UserRole, ("kindgroup", kind))
            grp.setIcon(0, IceIcons.get(kind, 16))
            for o in objs:
                it = QTreeWidgetItem(grp, [o.name])
                it.setIcon(0, IceIcons.get(o.kind, 16))
                self._mark_object_item(it, o, hidden)
                tip = "shape=%s" % (o.shape.type if o.shape else "-")
                it.setToolTip(0, tip)
            grp.setExpanded(True)
        model_item.setText(0, "Model (%d)" % model.count_all())
        model_item.setExpanded(True)

    def _fill_groups_inactive_trash(self, project, groups, inactive, trash):
        g_item = self._items["Groups"]
        model = getattr(project, "model", None)
        for gname, members in sorted((groups or {}).items()):
            git = QTreeWidgetItem(g_item, ["%s (%d)" % (gname, len(members))])
            git.setIcon(0, IceIcons.get("group", 16))
            git.setData(0, Qt.UserRole, ("usergroup", gname))
            for m in members:
                obj = model.object_by_name(m) if model is not None else None
                c = QTreeWidgetItem(git, [m])
                if obj is not None:
                    c.setData(0, Qt.UserRole, ("objectref", obj))
                    c.setIcon(0, IceIcons.get(obj.kind, 16))
                else:
                    c.setData(0, Qt.UserRole, ("groupmember", (gname, m)))
            git.setExpanded(True)
        if groups:
            g_item.setText(0, "Groups (%d)" % len(groups))
            g_item.setExpanded(True)

        in_item = self._items["Inactive"]
        n_in = 0
        for name in sorted(inactive or ()):
            obj = model.object_by_name(name) if model is not None else None
            it = QTreeWidgetItem(in_item, [name])
            if obj is not None:
                self._mark_object_item(it, obj, set())
                it.setIcon(0, IceIcons.get(obj.kind, 16))
            else:
                it.setData(0, Qt.UserRole, ("inactive", name))
            n_in += 1
        if n_in:
            in_item.setText(0, "Inactive (%d)" % n_in)
            in_item.setExpanded(True)

        tr_item = self._items["Trash"]
        for o in trash or []:
            it = QTreeWidgetItem(tr_item, [getattr(o, "name", str(o))])
            it.setIcon(0, IceIcons.get(getattr(o, "kind", "trash"), 16))
            it.setData(0, Qt.UserRole, ("trash", o))
        if trash:
            tr_item.setText(0, "Trash (%d)" % len(trash))
            tr_item.setExpanded(True)

    def find_object_item(self, name):
        def walk(item):
            role = item.data(0, Qt.UserRole)
            if role and role[0] == "object" and getattr(role[1], "name", None) == name:
                return item
            for i in range(item.childCount()):
                hit = walk(item.child(i))
                if hit is not None:
                    return hit
            return None
        for i in range(self.topLevelItemCount()):
            hit = walk(self.topLevelItem(i))
            if hit is not None:
                return hit
        return None

    def find_items_matching(self, text):
        """Object items whose name contains text (case-insensitive)."""
        needle = (text or "").strip().lower()
        hits = []
        if not needle:
            return hits

        def walk(item):
            role = item.data(0, Qt.UserRole)
            if role and role[0] == "object":
                name = getattr(role[1], "name", "") or ""
                if needle in name.lower():
                    hits.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return hits

    def select_object_named(self, name):
        it = self.find_object_item(name)
        if it is None:
            return False
        self.setCurrentItem(it)
        self.scrollToItem(it)
        return True

    def _on_item_changed(self, item, _col):
        role = item.data(0, Qt.UserRole)
        if not role or role[0] != "object":
            return
        name = getattr(role[1], "name", None)
        if not name:
            return
        self.visibility_changed.emit(name, item.checkState(0) == Qt.Checked)

    def _on_sel(self):
        items = self.selectedItems()
        if not items:
            return
        role = items[0].data(0, Qt.UserRole)
        if not role:
            return
        tag = role[0]
        if tag == "object":
            self.object_selected.emit(role[1])
        elif tag == "objectref":
            self.object_selected.emit(role[1])
        else:
            self.node_selected.emit(tag, role[1] if len(role) > 1 else None)

    def _on_dbl(self, item, _col):
        role = item.data(0, Qt.UserRole)
        if not role:
            return
        if role[0] in ("object", "objectref"):
            self.object_activated.emit(role[1])
        else:
            self.node_activated.emit(role[0], role[1] if len(role) > 1 else None)


class LibraryTree(QTreeWidget):
    """Icepak Library tab (read-only browse of icepak_lib categories)."""

    item_activated = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Library"])
        self.itemDoubleClicked.connect(self._on_dbl)
        self.reset_default()

    def reset_default(self):
        self.clear()
        root = QTreeWidgetItem(["icepak_lib"])
        root.setIcon(0, IceIcons.get("library", 16))
        self.addTopLevelItem(root)
        for name in ("Materials", "Fans", "Packages", "Heat sinks", "Blowers"):
            it = QTreeWidgetItem(root, [name])
            it.setIcon(0, IceIcons.get("folder", 16))
            it.setData(0, Qt.UserRole, ("lib", name))
        root.setExpanded(True)

    def populate_from_path(self, root):
        """Read-only listing of icepak_lib (no tar unpack)."""
        if not root or not os.path.isdir(root):
            self.reset_default()
            return False
        self.clear()
        top = QTreeWidgetItem([os.path.basename(root) or "icepak_lib"])
        top.setIcon(0, IceIcons.get("library", 16))
        top.setData(0, Qt.UserRole, ("libroot", root))
        self.addTopLevelItem(top)
        names = sorted(os.listdir(root), key=lambda s: s.lower())
        for name in names:
            if name.startswith("."):
                continue
            fp = os.path.join(root, name)
            label = name
            if name.endswith(".tar"):
                label = os.path.splitext(name)[0]
            it = QTreeWidgetItem(top, [label])
            it.setIcon(0, IceIcons.get("folder" if os.path.isdir(fp) else "material", 16))
            it.setData(0, Qt.UserRole, ("lib", fp))
            if os.path.isdir(fp):
                children = sorted(os.listdir(fp), key=lambda s: s.lower())[:40]
                for ch in children:
                    if ch.startswith("."):
                        continue
                    cfp = os.path.join(fp, ch)
                    cit = QTreeWidgetItem(it, [ch])
                    cit.setData(0, Qt.UserRole, ("lib", cfp))
                    cit.setIcon(0, IceIcons.get("folder" if os.path.isdir(cfp) else "material", 16))
        top.setExpanded(True)
        return True

    def _on_dbl(self, item, _col):
        role = item.data(0, Qt.UserRole)
        self.item_activated.emit(item.text(0), role[1] if role and len(role) > 1 else None)


def find_icepak_lib():
    env = os.environ.get("ICEPAK_LIB") or ""
    if env and os.path.isdir(env):
        return env
    root = os.environ.get("ICEPAK_ROOT") or ""
    if root:
        for sub in ("icepak_lib", os.path.join("icepak19.5", "icepak_lib")):
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                return p
    for p in ICEPAK_LIB_CANDIDATES:
        if os.path.isdir(p):
            return p
    return None


class TdvStrip(QFrame):
    """Narrow vertical interaction strip between tree and Graphics."""

    mode_changed = pyqtSignal(str)  # pick / boxpick / rotate / pan / zoom
    hide_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(32)
        self.setObjectName("TdvStrip")
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 4, 2, 4)
        v.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for i, (name, tip) in enumerate((
            ("pick", "Pick"),
            ("boxpick", "Box pick"),
            ("rotate", "Rotate"),
            ("pan", "Pan"),
            ("zoom", "Zoom"),
        )):
            b = QToolButton(self)
            b.setIcon(IceIcons.get(name, 22))
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setFixedSize(28, 28)
            self._group.addButton(b, i)
            v.addWidget(b)
            self._buttons[name] = b
            b.clicked.connect(lambda _=False, n=name: self.mode_changed.emit(n))
        self._buttons["pick"].setChecked(True)
        hide = QToolButton(self)
        hide.setIcon(IceIcons.get("hide", 22))
        hide.setToolTip("Show/Hide selected")
        hide.setAutoRaise(True)
        hide.setFixedSize(28, 28)
        hide.clicked.connect(self.hide_requested.emit)
        v.addWidget(hide)
        v.addStretch(1)

    def mode(self):
        for name, b in self._buttons.items():
            if b.isChecked():
                return name
        return "pick"
