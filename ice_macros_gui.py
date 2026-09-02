# -*- coding: utf-8 -*-
"""
P7 GUI: macro wizard shell (nav tree + pages, cabdecoding WizardBase parity)
and dynamic Macros menu rebuild (type/subtype/macro three-level cascades).
"""
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QSplitter, QStackedWidget, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from ice_forms import FormPage


class MacroWizard(QDialog):
    """Icepak-style macro wizard: left navigation tree + stacked pages."""

    def __init__(self, parent=None, title="Macro", params=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 420)
        self._params = list(params or [])
        self._pages = {}
        self._nav = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        split = QSplitter(Qt.Horizontal, self)
        self.nav = QTreeWidget(self)
        self.nav.setHeaderLabels(["Steps"])
        self.nav.setFixedWidth(170)
        split.addWidget(self.nav)
        self.stack = QStackedWidget(self)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        v.addWidget(split, 1)
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet("font-weight:bold; color:#1f4e79;")
        v.addWidget(self.lbl_title)
        row = QHBoxLayout()
        row.addWidget(self.lbl_title, 1)
        self.btn_back = QPushButton("Back", self)
        self.btn_back.clicked.connect(self._back)
        self.btn_next = QPushButton("Next", self)
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(self._next)
        self.btn_finish = QPushButton("Finish", self)
        self.btn_finish.clicked.connect(self._finish)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)
        row.addWidget(self.btn_back)
        row.addWidget(self.btn_next)
        row.addWidget(self.btn_finish)
        row.addWidget(self.btn_cancel)
        v.addLayout(row)
        self._cur = 0
        self._build_pages()
        self._sync()

    # -- page registry (WizardBase._add_page parity) ------------------------
    def _add_page(self, key, title, widget, parent_key=None):
        idx = self.stack.count()
        self.stack.addWidget(widget)
        parent = self.nav.invisibleRootItem()
        if parent_key is not None and parent_key in self._nav:
            parent = self._nav[parent_key]
        item = QTreeWidgetItem([title])
        parent.addChild(item)
        self._pages[key] = idx
        self._nav[key] = item
        return item

    def _build_pages(self):
        params = self._params
        if not params:
            page = QWidget(self)
            lay = QVBoxLayout(page)
            lay.addWidget(QLabel("No parameters required.", page))
            self._add_page("run", "Run", page)
        else:
            page = FormPage(self)
            f = page.section("Parameters")
            for key, label, kind, default, *rest in params:
                page.add_row(f, key, label, kind, default,
                             options=rest[0] if rest else None)
            self.form = page
            self._add_page("params", "Parameters", page)
            confirm = QWidget(self)
            lay = QVBoxLayout(confirm)
            self.lbl_confirm = QLabel("", confirm)
            lay.addWidget(self.lbl_confirm)
            self._add_page("confirm", "Confirm", confirm)
        self.nav.expandAll()

    def _sync(self):
        keys = list(self._pages.keys())
        if not keys:
            return
        self._cur = min(self._cur, len(keys) - 1)
        self.stack.setCurrentIndex(self._pages[keys[self._cur]])
        it = self._nav.get(keys[self._cur])
        if it is not None:
            self.nav.setCurrentItem(it)
        self.btn_back.setEnabled(self._cur > 0)
        self.btn_next.setVisible(self._cur < len(keys) - 1)
        self.btn_finish.setVisible(self._cur == len(keys) - 1)

    def _back(self):
        self._cur -= 1
        self._sync()

    def _next(self):
        self._cur += 1
        self._sync()

    def _finish(self):
        params = {}
        if hasattr(self, "form"):
            params = self.form.values()
        parent = self._parent or self.window()
        run = getattr(parent, "_run_builtin_macro", None)
        if run is not None:
            run(self._macro_key, params)
        self.accept()

    # -- helpers ------------------------------------------------------------
    def bind_macro(self, key, name):
        self._macro_key = key
        self.setWindowTitle(name)

    def params(self):
        return self.form.values() if hasattr(self, "form") else {}

    @property
    def _parent(self):
        return self.parent()


# ---- Phase D2: per-part wizard pages for the macro-library catalog (845) ---
_CNT_RE = re.compile(r"(^|_)(num|rows|count|via_num|row_sup|ball_mid)(?=_|$|\d)", re.I)


def _is_count_key(key):
    """Parameters that encode a count rather than a physical dimension."""
    return bool(_CNT_RE.search(key))


def _param_label(key):
    """Human-friendly label: split digit groups, underscores to spaces."""
    s = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', key)
    return s.replace('_', ' ').title()


def macro_param_rows(macro, max_rows=None):
    """Turn a library macro's param dict into add_row 5-tuples (key,label,kind,default,options).

    Kinds are inferred from the value type: bool->check, whole count keys->int,
    floats->spin, everything else->text. max_rows limits the number of rows
    (used by tests) while keeping the full catalog editable in the GUI.
    """
    params = macro.get('params') or {}
    rows = []
    for key, val in list(params.items())[:max_rows]:
        label = _param_label(key)
        if isinstance(val, bool):
            rows.append((key, label, 'check', val, None))
        elif isinstance(val, int):
            rows.append((key, label, 'int', val, None))
        elif isinstance(val, float):
            if val == int(val) and _is_count_key(key):
                rows.append((key, label, 'int', int(val), None))
            else:
                rows.append((key, label, 'spin', val, None))
        else:
            rows.append((key, label, 'text', val, None))
    return rows


class LibraryMacroWizard(MacroWizard):
    """Wizard page for one macro-library part (library / pitch / rows / name).

    Emits the edited param dict to the parent ``_run_library_macro``, which
    builds the package object via :func:`ice_macros.build_library_part`.
    """

    def __init__(self, parent=None, macro=None, title=None):
        macro = macro or {}
        self._library_macro = macro
        title = title or macro.get('name') or 'Library part'
        super().__init__(parent, title=title, params=macro_param_rows(macro))

    def _build_pages(self):
        super()._build_pages()
        lbl = getattr(self, 'lbl_confirm', None)
        if lbl is not None:
            m = self._library_macro
            lbl.setText(
                "Create part %s\nLibrary: %s\nPitch: %s  Rows: %s"
                "  (%d parameters)" %
                (m.get('name', 'part'), m.get('library', ''),
                 m.get('pitch', ''), m.get('rows', ''),
                 len(m.get('params') or {})))

    def _finish(self):
        params = self.form.values() if hasattr(self, 'form') else {}
        parent = self.parent() or self.window()
        run = getattr(parent, '_run_library_macro', None)
        if run is not None:
            run(self._library_macro, params)
        self.accept()
