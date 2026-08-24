# -*- coding: utf-8 -*-
"""Icepak-style panes: Welcome, Message, Project/Library trees, TDV strip."""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QToolBar, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
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


class ProjectTree(QTreeWidget):
    """Icepak Project tab: nine fixed nodes + Model objects."""

    object_selected = pyqtSignal(object)
    object_activated = pyqtSignal(object)
    node_selected = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Project"])
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformRowHeights(True)
        self.itemSelectionChanged.connect(self._on_sel)
        self.itemDoubleClicked.connect(self._on_dbl)
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

    def populate(self, project):
        """Fill from IcepakProject. Keeps the nine fixed nodes."""
        name = getattr(project, "name", None) or "untitled"
        self.reset_empty(name)
        self.setHeaderLabels([name])

        model_item = self._items["Model"]
        model = getattr(project, "model", None)
        if model is not None:
            counts = model.kind_counts()
            cabinet = None
            for o in model._all_objects():
                if o.kind == "domain":
                    cabinet = o
                    break
            cab_it = QTreeWidgetItem(model_item, ["Cabinet"])
            cab_it.setIcon(0, IceIcons.get("domain", 16))
            if cabinet is not None:
                cab_it.setData(0, Qt.UserRole, ("object", cabinet))
                cab_it.setText(0, cabinet.name or "Cabinet")
            else:
                cab_it.setData(0, Qt.UserRole, ("node", "Cabinet"))

            by_kind = {}
            for o in model._all_objects():
                if o.kind == "domain":
                    continue
                by_kind.setdefault(o.kind, []).append(o)
            for kind in sorted(by_kind, key=lambda k: -len(by_kind[k])):
                objs = by_kind[kind]
                grp = QTreeWidgetItem(model_item, ["%s (%d)" % (kind, len(objs))])
                grp.setData(0, Qt.UserRole, ("group", kind))
                grp.setIcon(0, IceIcons.get(kind, 16))
                for o in objs:
                    it = QTreeWidgetItem(grp, [o.name])
                    it.setData(0, Qt.UserRole, ("object", o))
                    it.setIcon(0, IceIcons.get(o.kind, 16))
                    tip = "shape=%s" % (o.shape.type if o.shape else "-")
                    it.setToolTip(0, tip)
                grp.setExpanded(True)
            model_item.setText(0, "Model (%d)" % model.count_all())
        model_item.setExpanded(True)

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
            label = po.get("type") or po.get("name") or "post"
            if isinstance(po, dict):
                label = po.get("name") or po.get("type") or str(po)[:40]
            it = QTreeWidgetItem(post_item, [str(label)])
            it.setData(0, Qt.UserRole, ("post", po))
        if posts:
            post_item.setText(0, "Post-processing (%d)" % len(posts))

        self._items["Problem setup"].setExpanded(False)
        self._items["Solution settings"].setExpanded(False)

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
        else:
            self.node_selected.emit(tag, role[1] if len(role) > 1 else None)

    def _on_dbl(self, item, _col):
        role = item.data(0, Qt.UserRole)
        if role and role[0] == "object":
            self.object_activated.emit(role[1])


class LibraryTree(QTreeWidget):
    """Icepak Library tab (read-only browse of icepak_lib categories)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Library"])
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
