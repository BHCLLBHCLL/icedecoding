# -*- coding: utf-8 -*-
"""P9 GUI: PreferencesDialog (seven tabs) + AnnotationsDialog."""
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                             QTabWidget, QVBoxLayout)

from ice_forms import FormPage
from ice_prefs import PREFS_SPEC


class PreferencesDialog(QDialog):
    """Edit -> Preferences: Display / Libraries / Object types / Interaction /
    Mouse buttons / Meshing / Units."""

    def __init__(self, parent=None, store=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(560, 460)
        self._store = store
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget(self)
        self._pages = {}
        for tab, fields in PREFS_SPEC.items():
            page = FormPage(self)
            form = page.section(tab)
            val = store.values if store is not None else {}
            for spec in fields:
                key, label, kind = spec[0], spec[1], spec[2]
                options = spec[3] if len(spec) > 3 and isinstance(spec[3],
                                                                   list) \
                    else None
                default = spec[4] if len(spec) > 4 else (
                    spec[3] if len(spec) > 3 else None)
                if isinstance(default, list):
                    default = default[0]
                value = val.get(key, default)
                if kind == "check":
                    page.add_row(form, key, label, "check",
                                 bool(value) if value not in (None, "") else
                                 False)
                else:
                    page.add_row(form, key, label, kind, value,
                                 options=options)
            self._pages[tab] = page
            self.tabs.addTab(page, tab)
        v.addWidget(self.tabs, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_apply = QPushButton("Apply", self)
        self.btn_apply.clicked.connect(self._apply)
        ok = QPushButton("OK", self)
        ok.setDefault(True)
        ok.clicked.connect(self._apply_and_close)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_apply)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        v.addLayout(btns)

    def values(self):
        out = {}
        for page in self._pages.values():
            out.update(page.values())
        return out

    def _apply(self):
        vals = self.values()
        if self._store is not None:
            self._store.update(vals)
        parent = self._parent
        fn = getattr(parent, "_apply_prefs", None)
        if fn is not None:
            fn(self._store or _ValueStore(vals))

    def _apply_and_close(self):
        self._apply()
        self.accept()

    @property
    def _parent(self):
        return self.parent() or self.window()


class _ValueStore(object):
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class AnnotationsDialog(QDialog):
    """Edit -> Annotations: project title / date / logo visuals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Annotations")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        page = FormPage(self)
        form = page.section("Viewport annotations")
        page.add_row(form, "title", "Project title", "text", "Project")
        page.add_row(form, "show_title", "Show title", "check", 0)
        page.add_row(form, "show_date", "Show current date", "check", 0)
        page.add_row(form, "show_logo", "Show ANSYS logo", "check", 0)
        self.page = page
        v.addWidget(page, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("OK", self)
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        v.addLayout(btns)

    def _ok(self):
        parent = self._parent
        vals = self.page.values()
        apply_ = getattr(parent, "_apply_annotations", None)
        if apply_ is not None:
            apply_(vals)
        self.accept()

    @property
    def _parent(self):
        return self.parent() or self.window()
