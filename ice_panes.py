# -*- coding: utf-8 -*-
"""Icepak-style panes: Welcome, Message, Project/Library trees, TDV strip."""

from __future__ import annotations

from datetime import datetime
import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
        QLineEdit,
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QToolBar,
    QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QPlainTextEdit, QButtonGroup, QSizePolicy, QGridLayout,
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

    LEVEL_COLORS = {
        "ERROR": "#b71c1c",
        "WARN": "#d32f2f",
        "WARNING": "#d32f2f",
        "INFO": "#212121",
        "DEBUG": "#607d8b",
    }

    def log(self, msg, level="INFO"):
        """Append colored log line (WARN/ERROR red like Icepak's mess command)."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s: %s" % (ts, level, msg)
        if level == "DEBUG" and not self.chk_verbose.isChecked():
            return
        color = self.LEVEL_COLORS.get(level, "#212121")
        cursor = self.text.textCursor()
        cursor.movePosition(cursor.End)
        fmt = self.text.currentCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(line + "\n", fmt)
        self.text.setTextCursor(cursor)
        self.text.ensureCursorVisible()
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
    drop_requested = pyqtSignal(str, list)
    context_action = pyqtSignal(str, object, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Project"])
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.tree_detail = 1          # 0 flat 1 types 2 types+subtypes 3 +shapes
        self.listsort = "creation_order"
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

        objs = []
        for o in model._all_objects():
            if o.kind == "domain":
                continue
            if o.name in inactive or o.name in trash_names:
                continue
            objs.append(o)

        def sort_key(o):
            if self.listsort == "alphabetical":
                return o.name.lower()
            if self.listsort == "meshing priority":
                sv = getattr(o, "setvals", None) or {}
                return (int(sv.get("grid_priority", 10)), getattr(o, "name", ""))
            return (getattr(o, "creation_order", 0), getattr(o, "name", ""))

        objs.sort(key=sort_key)

        def subtype_of(o):
            sv = getattr(o, "setvals", None) or {}
            return sv.get("current_stype") or getattr(o, "current_stype", None) \
                or sv.get("stype") or "default"

        def shape_of(o):
            return getattr(getattr(o, "shape", None), "type", None) or "-"

        def add_leaf(parent, o):
            it = QTreeWidgetItem(parent, [o.name])
            it.setIcon(0, IceIcons.get(o.kind, 16))
            self._mark_object_item(it, o, hidden)
            tip = "shape=%s" % shape_of(o)
            it.setToolTip(0, tip)
            return it

        if self.tree_detail == 0:
            for o in objs:
                add_leaf(model_item, o)
        else:
            by_kind = {}
            for o in objs:
                by_kind.setdefault(o.kind, []).append(o)
            for kind in sorted(by_kind, key=lambda k: -len(by_kind[k])):
                group = by_kind[kind]
                if self.tree_detail == 1:
                    grp = QTreeWidgetItem(model_item,
                                          ["%s (%d)" % (kind, len(group))])
                    grp.setData(0, Qt.UserRole, ("kindgroup", kind))
                    grp.setIcon(0, IceIcons.get(kind, 16))
                    for o in group:
                        add_leaf(grp, o)
                    grp.setExpanded(True)
                else:
                    grp = QTreeWidgetItem(model_item,
                                          ["%s (%d)" % (kind, len(group))])
                    grp.setData(0, Qt.UserRole, ("kindgroup", kind))
                    grp.setIcon(0, IceIcons.get(kind, 16))
                    by_sub = {}
                    for o in group:
                        by_sub.setdefault(subtype_of(o), []).append(o)
                    for sname, sobjs in sorted(by_sub.items()):
                        if self.tree_detail == 2:
                            sub_parent = grp
                            label = "%s (%d)" % (sname, len(sobjs))
                        else:
                            sub = QTreeWidgetItem(grp,
                                                  ["%s (%d)" % (sname,
                                                                 len(sobjs))])
                            sub.setData(0, Qt.UserRole, ("subtype", sname))
                            sub_parent = sub
                            label = None
                        for o in sobjs:
                            if label is not None:
                                add_leaf(sub_parent, o)
                            else:
                                add_leaf(sub_parent, o)
                        if sub_parent is not grp:
                            sub_parent.setExpanded(True)
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

    # ---- P2: drag & drop onto Inactive / Trash / Points -----------------
    def dropEvent(self, ev):
        """Dropping object items onto Inactive/Trash/Points nodes."""
        target = self.itemAt(ev.pos())
        if target is None:
            return
        tag = target.data(0, Qt.UserRole)
        tagname = tag[0] if isinstance(tag, tuple) else None
        if tagname not in ("Inactive", "Trash", "Monitor points",
                           "Monitor surfaces", "Points", "Surfaces"):
            return
        names = [it.text(0) for it in self.selectedItems()
                 if it.data(0, Qt.UserRole) and
                 it.data(0, Qt.UserRole)[0] == "object"]
        if names:
            target_name = "Trash" if tagname == "Trash" else (
                "Points" if tagname in ("Monitor points", "Points") else
                ("Surfaces" if tagname in ("Monitor surfaces", "Surfaces")
                 else "Inactive"))
            self.drop_requested.emit(target_name, names)
            ev.accept()
        super().dropEvent(ev)

    def selected_object_items(self):
        """All currently selected items that carry a model object."""
        out = []
        for it in self.selectedItems():
            d = it.data(0, Qt.UserRole)
            if isinstance(d, tuple) and d and d[0] == "object":
                out.append(it)
        return out

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


# ---------------------------------------------------------------------------
# P1 — New project panel (Icepak: name must not contain Chinese characters)
# ---------------------------------------------------------------------------

_CHINESE = [chr(c) for c in range(0x4E00, 0x9FFF + 1)]


class NewProjectDialog(QDialog):
    """File -> New project panel with Icepak name rules."""

    def __init__(self, parent=None, default_name="project"):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self._name = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        form = QHBoxLayout()
        form.addWidget(QLabel("Project name:", self))
        self.txt_name = QLineEdit(default_name, self)
        self.txt_name.setMinimumWidth(240)
        self.txt_name.textChanged.connect(self._check)
        form.addWidget(self.txt_name, 1)
        v.addLayout(form)
        self.lbl_err = QLabel("", self)
        self.lbl_err.setStyleSheet("color:#d32f2f;")
        v.addWidget(self.lbl_err)
        hint = QLabel("Project name and working directory must not contain "
                      "Chinese characters.", self)
        hint.setStyleSheet("color:#607d8b;")
        v.addWidget(hint)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_create = QPushButton("Create", self)
        self.btn_create.setDefault(True)
        self.btn_create.clicked.connect(self._accept)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_create)
        buttons.addWidget(self.btn_cancel)
        v.addLayout(buttons)
        self._check(self.txt_name.text())

    def _check(self, text):
        bad = [c for c in text if c in _CHINESE]
        if not text:
            self.lbl_err.setText("Project name is required.")
            self.btn_create.setEnabled(False)
            return False
        if bad:
            self.lbl_err.setText("Invalid project name: %s" %
                                 "".join(sorted(set(bad))))
            self.btn_create.setEnabled(False)
            return False
        self.lbl_err.setText("")
        self.btn_create.setEnabled(True)
        return True

    def _accept(self):
        name = self.txt_name.text().strip()
        if self._check(name):
            self._name = name
            self.accept()

    @staticmethod
    def get_name(parent=None):
        dlg = NewProjectDialog(parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg._name
        return None


# ---------------------------------------------------------------------------
# P1 — bottom-right "current object" geometry window (Icepak 图3-88)
# ---------------------------------------------------------------------------

class GeometryWindow(QWidget):
    """当前所选器件几何信息窗口: name/shape/geometry + orange xS..zE buttons."""

    AXIS_LABELS = ("xS", "yS", "zS", "xE", "yE", "zE")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(230)
        self.setMaximumWidth(330)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)
        self.lbl_title = QLabel("Geometry", self)
        self.lbl_title.setStyleSheet("font-weight:bold;")
        v.addWidget(self.lbl_title)
        self.txt_name = QLineEdit(self)
        self.txt_name.setReadOnly(True)
        v.addWidget(self.txt_name)
        self.txt_shape = QLineEdit(self)
        self.txt_shape.setReadOnly(True)
        v.addWidget(self.txt_shape)
        self.btn_copy_from = QPushButton("Copy from...", self)
        self.btn_copy_from.clicked.connect(self._copy_from)
        v.addWidget(self.btn_copy_from)
        self._rows = {}
        grid = QGridLayout()
        grid.setSpacing(3)
        for r, name in enumerate(("Start", "End")):
            for c, ax in enumerate(("X", "Y", "Z")):
                key = self.AXIS_LABELS[r * 3 + c]
                btn = QPushButton(key, self)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setToolTip("Align/stretch to %s (P4 wires the full "
                               "align engine)" % key)
                btn.setStyleSheet(
                    "QPushButton { background:#f3a53a; color:#3a2a10; "
                    "border:1px solid #c57f1e; border-radius:3px; "
                    "min-width:30px; min-height:20px; }")
                btn.clicked.connect(lambda _=False, k=key: self._axis(k))
                grid.addWidget(btn, r, c + 0)
                box = QLineEdit(self)
                box.setMinimumWidth(56)
                grid.addWidget(box, r, c + 3)
                self._rows[key] = box
        v.addLayout(grid)
        row_btns = QHBoxLayout()
        self.btn_apply = QPushButton("Apply", self)
        self.btn_apply.clicked.connect(self._apply_geo)
        self.btn_edit = QPushButton("Edit...", self)
        self.btn_edit.clicked.connect(self._edit)
        row_btns.addWidget(self.btn_apply)
        row_btns.addWidget(self.btn_edit)
        v.addLayout(row_btns)
        v.addStretch(1)
        self._object = None

    def set_object(self, obj):
        """obj: ModelObject or None; fills read-only values."""
        self._object = obj
        if obj is None:
            self.txt_name.setText("")
            self.txt_shape.setText("")
            for k in self._rows:
                self._rows[k].setText("")
            self.lbl_title.setText("Geometry")
            return
        name = getattr(obj, "name", "?")
        shape = getattr(obj, "shape", None)
        self.txt_name.setText(name)
        self.txt_shape.setText(getattr(shape, "type", None) or
                               getattr(shape, "stype", "") or "")
        sv = {}
        if shape is not None:
            sv = getattr(shape, "setvals", None) or {}
        axis_map = (("point1", "xS", "yS", "zS"), ("point2", "xE", "yE", "zE"))
        coord = {}
        for key, cx, cy, cz in axis_map:
            v = sv.get(key)
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                coord[cx], coord[cy], coord[cz] = v[0], v[1], v[2]
        for key in ("xS", "yS", "zS", "xE", "yE", "zE"):
            self._rows[key].setText(str(coord.get(key, "")))
        self.lbl_title.setText("Geometry — %s" % name)

    def _apply_geo(self):
        """Dual-write: GeometryWindow <-> object shape (orange engine)."""
        if self._object is None:
            return
        sh = getattr(self._object, "shape", None)
        if sh is None:
            return
        p1 = [self._rows["xS"].text() or "0",
              self._rows["yS"].text() or "0",
              self._rows["zS"].text() or "0"]
        p2 = [self._rows["xE"].text() or "0",
              self._rows["yE"].text() or "0",
              self._rows["zE"].text() or "0"]
        try:
            p1 = [float(x) for x in p1]
            p2 = [float(x) for x in p2]
        except ValueError:
            return
        sh.setvals["point1"] = p1
        sh.setvals["point2"] = p2
        parent = self.window()
        mark = getattr(parent, "_mark_dirty", None)
        if mark is not None:
            mark("Geometry applied")
        refresh = getattr(parent, "_refresh", None)
        if refresh is not None:
            refresh()

    def _copy_from(self):
        parent = self.window()
        fn = getattr(parent, "_copy_from_dialog", None)
        if fn is not None and self._object is not None:
            fn(self._object)

    def _edit(self):
        obj = self._object
        if obj is not None and hasattr(self, "edit_requested"):
            self.edit_requested.emit(obj.name)
        elif obj is not None:
            parent = self.window()
            fn = getattr(parent, "_edit_current", None)
            if fn is not None:
                fn()

    def _axis(self, key):
        if self._object is None:
            return
        msg = "Geometry window: %s selected — align/stretch engine lands in P4." % key
        parent = self.window()
        log = getattr(parent, "log", None)
        if log is not None:
            log(msg, "WARN")


# ---------------------------------------------------------------------------
# P1 — Edit toolbars dialog (Icepak View->Edit toolbars)
# ---------------------------------------------------------------------------

class EditToolbarsDialog(QDialog):
    """Check/uncheck toolbars; persisted through QSettings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit toolbars")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        self._checks = []
        owner = parent if parent is not None else None
        toolbars = getattr(owner, "_toolbars", {}) if owner is not None else {}
        for name, tb in toolbars.items():
            chk = QCheckBox(name, self)
            chk.setChecked(not tb.isHidden())
            chk.toggled.connect(
                lambda on, n=name, t=tb: self._apply(n, t, on))
            v.addWidget(chk)
            self._checks.append((chk, name, tb))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_btn = QPushButton("OK", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)
        v.addLayout(buttons)

    def _apply(self, name, tb, on):
        tb.setVisible(on)
        owner = self.window()
        if owner is not None and hasattr(owner, "_toolbar_visible"):
            owner._toolbar_visible[name] = bool(on)


# ---------------------------------------------------------------------------
# P2 — Edit via spreadsheet (Icepak tkTable parity, multi-edit entry)
# ---------------------------------------------------------------------------

class SpreadsheetDialog(QDialog):
    """Rows = objects, columns = property/setval keys; editable scalars."""

    def __init__(self, parent=None, names=None, project=None):
        super().__init__(parent)
        self.setWindowTitle("Edit via spreadsheet")
        self.setMinimumSize(760, 460)
        self._project = project
        objs = []
        if project is not None:
            for n in (names or []):
                o = project.model.object_by_name(n) if project.model else None
                if o is not None:
                    objs.append(o)
        self._objs = objs
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.table = QTableWidget(self)
        self.table.setAlternatingRowColors(True)
        v.addWidget(self.table, 1)
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
        self._reload()

    def _keys_of(self, obj):
        keys = []
        sv = getattr(obj, "setvals", None) or {}
        for k in sv:
            keys.append(k)
        sh = getattr(obj, "shape", None)
        ssv = getattr(sh, "setvals", None) or {}
        for k in ssv:
            keys.append("shape." + k)
        return list(dict.fromkeys(keys))

    def _reload(self):
        keys = []
        for obj in self._objs:
            for k in self._keys_of(obj):
                if k not in keys:
                    keys.append(k)
        cols = ["Name", "Kind"] + keys[:28]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(self._objs))
        for r, obj in enumerate(self._objs):
            name_item = QTableWidgetItem(getattr(obj, "name", ""))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, name_item)
            kind_item = QTableWidgetItem(getattr(obj, "kind", ""))
            kind_item.setFlags(kind_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 1, kind_item)
            sv = {}
            if getattr(obj, "setvals", None):
                sv.update(obj.setvals)
            sh = getattr(obj, "shape", None)
            ssv = getattr(sh, "setvals", None) or {}
            for k, val in ssv.items():
                sv["shape." + k] = val
            for c, key in enumerate(keys, start=2):
                val = sv.get(key, "")
                if isinstance(val, (list, tuple)):
                    val = " ".join(str(x) for x in val)
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

    def _apply(self):
        keys = []
        for c in range(2, self.table.columnCount()):
            keys.append(self.table.horizontalHeaderItem(c).text())
        for r, obj in enumerate(self._objs):
            for c, key in enumerate(keys):
                item = self.table.item(r, c + 2)
                if item is None:
                    continue
                val = item.text()
                if key.startswith("shape."):
                    sh = getattr(obj, "shape", None)
                    if sh is not None:
                        sh.setvals[key[6:]] = val
                else:
                    sv = getattr(obj, "setvals", None)
                    if sv is None:
                        sv = obj.setvals = {}
                    sv[key] = val
        parent = self.window()
        refresh = getattr(parent, "_refresh", None)
        if refresh is not None:
            refresh()

    def _apply_and_close(self):
        self._apply()
        self.accept()


# ---------------------------------------------------------------------------
# P3 — View->Lights dialog: tdv_lights_edit + background style
# ---------------------------------------------------------------------------

class ViewOptionsDialog(QDialog):
    """Edit viewer lights (ambient/light1-4) and background style."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lights")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)
        form = QFormLayout()
        self._hex = {}
        for name in ("ambient", "light1", "light2", "light3", "light4"):
            ed = QLineEdit("#ffffff", self)
            ed.setMaximumWidth(120)
            form.addRow(QLabel(name, self), ed)
            self._hex[name] = ed
        v.addLayout(form)
        from PyQt5.QtWidgets import QComboBox
        self.cmb_bg = QComboBox(self)
        self.cmb_bg.addItems(["Gradient", "Solid"])
        row_bg = QHBoxLayout()
        row_bg.addWidget(QLabel("Background style:", self))
        row_bg.addWidget(self.cmb_bg)
        self.btn_c1 = QPushButton("#9ec8e8", self)
        self.btn_c2 = QPushButton("#f4f7fb", self)
        self.btn_c1.setStyleSheet("background:%s;" % self.btn_c1.text())
        self.btn_c2.setStyleSheet("background:%s;" % self.btn_c2.text())
        self.btn_c1.clicked.connect(lambda: self._pick(self.btn_c1))
        self.btn_c2.clicked.connect(lambda: self._pick(self.btn_c2))
        row_bg.addWidget(self.btn_c1)
        row_bg.addWidget(self.btn_c2)
        row_bg.addStretch(1)
        v.addLayout(row_bg)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok_btn = QPushButton("Apply", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._apply)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel)
        v.addLayout(btns)

    def _pick(self, btn):
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        c = QColorDialog.getColor(QColor(btn.text()), self)
        if c.isValid():
            btn.setText(c.name())
            btn.setStyleSheet("background:%s;" % c.name())

    def _apply(self):
        parent = self.window()
        if not hasattr(parent, "_lights"):
            parent._lights = {}
        for name, ed in self._hex.items():
            parent._lights[name] = ed.text()
        style = "solid" if self.cmb_bg.currentIndex() == 1 else "gradient"
        set_bg = getattr(parent, "_set_background", None)
        if set_bg is not None:
            set_bg(style, self.btn_c1.text(), self.btn_c2.text())
        self.accept()

# ---------------------------------------------------------------------------
# P5 - AutoHex six-tab dialog (imports ice_mesh lazily inside __init__)
# ---------------------------------------------------------------------------

class AutoHexDialog(QDialog):
    """Icepak Complete Hex Mesher: Basic/Parameter/Detail/Edit/Deletion/Others."""

    TABS = ("Basic", "Parameter", "Detail", "Edit", "Deletion", "Others")

    def __init__(self, parent=None, model=None):
        super().__init__(parent)
        from ice_mesh import PARAMS_DEFAULTS
        self.setWindowTitle("Complete Hex Mesher")
        self.setMinimumSize(640, 480)
        self._model = model
        self._params = dict(PARAMS_DEFAULTS)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget(self)
        v.addWidget(self.tabs, 1)
        self._pages = {}
        self._build_tabs(PARAMS_DEFAULTS)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_large_mesh = QPushButton("Large mesh", self)
        self.btn_large_mesh.setToolTip(
            "Enforce grid_max_elements before meshing")
        self.btn_large_mesh.clicked.connect(self._large_mesh)
        self.btn_cancel = QPushButton("Cancel meshing", self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_gen = QPushButton("Generate mesh", self)
        self.btn_gen.setDefault(True)
        self.btn_gen.clicked.connect(self._collect_and_accept)
        row.addWidget(self.btn_large_mesh)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_gen)
        v.addLayout(row)

    def _build_tabs(self, D):
        from ice_forms import FormPage
        basic = FormPage(self, "Basic")
        f = basic.section("Size control")
        for ax in ("i", "j", "k"):
            basic.add_row(f, "grid_gcount_%s" % ax,
                          "%s divisions" % ax.upper(), "int", 10,
                          minimum=1, maximum=100000)
        basic.add_row(f, "grid_gtype", "Growth", "combo", "unif",
                      options=["unif", "geom"])
        basic.add_row(f, "grid_gr_ratio", "Ratio", "spin", 1.0,
                      minimum=1.0, maximum=100.0)
        for ax in ("x", "y", "z"):
            basic.add_row(f, "grid_size_%s" % ax,
                          "%s size (m)" % ax.upper(), "spin", 1.0)
        f = basic.section("Limits")
        basic.add_row(f, "grid_max_elements", "Max elements", "int",
                      25000000, minimum=100)
        for ax in ("x", "y", "z"):
            basic.add_row(f, "grid_sep_%s" % ax,
                          "Separation %s" % ax.upper(), "spin", 0.001,
                          minimum=0.0)
        self._pages["Basic"] = basic
        self.tabs.addTab(basic, "Basic")

        param = FormPage(self, "Parameter")
        f = param.section("Per-axis limits")
        for ax in ("i", "j", "k"):
            param.add_row(f, "grid_gmax_%s" % ax,
                          "Max %s" % ax.upper(), "int", 0, minimum=0)
        for ax in ("i", "j", "k"):
            param.add_row(f, "grid_gmin_%s" % ax,
                          "Min %s" % ax.upper(), "int", 0, minimum=0)
        param.add_row(f, "grid_ratios", "Auto ratios", "check", 0)
        self._pages["Parameter"] = param
        self.tabs.addTab(param, "Parameter")

        detail = FormPage(self, "Detail")
        f = detail.section("Hex mesher preset")
        detail.add_row(f, "grid_settings_type", "Settings", "combo",
                       "normal", options=["normal", "coarse", "null"])
        detail.add_row(f, "min_elements_gap", "Min elements in gap",
                       "int", 3, minimum=0)
        detail.add_row(f, "min_elements_block", "Min elements in block",
                       "int", 2, minimum=0)
        detail.add_row(f, "max_ratio", "Max ratio", "spin", 2.0,
                       minimum=1.0)
        f = detail.section("Tetra")
        detail.add_row(f, "grid_tetra_settings_type", "Tetra settings",
                       "combo", "normal", options=["normal", "coarse"])
        detail.add_row(f, "n_cells_in_gap", "Cells in gap", "int", 2,
                       minimum=0)
        detail.add_row(f, "natural_size_refinement",
                       "Natural size refinement", "int", 32, minimum=0)
        f = detail.section("Mesher-HD")
        detail.add_row(f, "grid_hdm_feature_angle", "Feature angle",
                       "int", 40, minimum=0, maximum=90)
        detail.add_row(f, "grid_hdm_mlm_auto_levels", "Auto levels",
                       "int", 2, minimum=0, maximum=6)
        detail.add_row(f, "grid_hdm_icechip", "Ice-chip mode", "combo",
                       "1", options=["0", "1"])
        f = detail.section("Smoother")
        detail.add_row(f, "grid_run_smoother", "Run smoother", "check", 0)
        detail.add_row(f, "limit_bad_angle", "Limiting bad angle", "spin",
                       35.0, minimum=0.0, maximum=90.0)
        detail.add_row(f, "mth_local_sm", "Method", "combo", "Optimize",
                       options=["Optimize", "Laplace"])
        f = detail.section("Quality")
        detail.add_row(f, "grid_qual", "Quality measure", "combo",
                       "facealign",
                       options=["facealign", "minangle", "orthogonal"])
        detail.add_row(f, "bad_face_align", "Bad face alignment", "spin",
                       0.05, minimum=0.0, maximum=1.0)
        f = detail.section("Pipe")
        detail.add_row(f, "pipe_mesh_on", "Pipe mesh", "check", 0)
        detail.add_row(f, "ogrid_height", "O-grid height", "spin", 0.5,
                       minimum=0.0, maximum=2.0)
        self._pages["Detail"] = detail
        self.tabs.addTab(detail, "Detail")

        edit = FormPage(self, "Edit")
        f = edit.section("Mesh line edit (grid edges)")
        edit.add_row(f, "edge_eps", "Edge epsilon", "spin", 0.00015,
                     minimum=0.0)
        edit.add_row(f, "element_threshold", "Element threshold", "spin",
                     0.9, minimum=0.0, maximum=1.0)
        edit.add_row(f, "panel_block_face", "Panel/block face", "check", 0)
        f = edit.section("Refinement (insert grid lines)")
        edit.add_row(f, "refine_faces_on", "Insert lines at object faces",
                     "check", 1)
        edit.add_row(f, "min_spacing", "Min spacing (m)", "spin", 0.003,
                     minimum=0.0001, maximum=0.05)
        edit.add_row(f, "interior_ratio", "Interior subdivision ratio",
                     "spin", 2.0, minimum=1.0, maximum=6.0)
        self._pages["Edit"] = edit
        self.tabs.addTab(edit, "Edit")

        deletion = FormPage(self, "Deletion")
        f = deletion.section("Deletion targets")
        deletion.add_row(f, "del_all_but_rough", "Delete all but rough",
                         "check", 0)
        deletion.add_row(f, "grid_include_all_gaps", "Include all gaps",
                         "check", 0)
        deletion.add_row(f, "grid_include_int_boundary",
                         "Include internal boundary", "check", 0)
        self._pages["Deletion"] = deletion
        self.tabs.addTab(deletion, "Deletion")

        others = FormPage(self, "Others")
        f = others.section("Mesher options")
        others.add_row(f, "check_scheme", "Check scheme", "check", 0)
        others.add_row(f, "part_mesh_option", "Part mesh option",
                       "combo", "0", options=["0", "1", "2"])
        others.add_row(f, "grid_display_mesh_separately",
                       "Display mesh separately", "check", 0)
        others.add_row(f, "grid_cutouts", "Cutouts", "check", 1)
        others.add_row(f, "match_oracle_cells", "Target cells (0=off)",
                       "int", 0, minimum=0, maximum=40000000)
        self._pages["Others"] = others
        self.tabs.addTab(others, "Others")

    def _large_mesh(self):
        row = self.tabs.widget(0).row("grid_max_elements")
        if row is not None:
            self._params["grid_max_elements"] = int(row.get())
        log = getattr(self.window(), "log", None)
        if log:
            log("Large mesh warning: max elements = %d" %
                self._params["grid_max_elements"], "WARN")

    def _collect_and_accept(self):
        for name, page in self._pages.items():
            self._params.update(page.values())
        self.accept()

    def params(self):
        return dict(self._params)
