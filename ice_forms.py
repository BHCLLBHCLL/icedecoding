# -*- coding: utf-8 -*-
"""
P4: Form engine (Icepak form_init/form_frame parity) — a tiny declarative
layout builder over QFormLayout/QWidget, used by object editors and dialogs.
Field kinds: text, spin, combo, check, file, color, button, label, group.
"""
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QWidget,
)

FIELD_CLASSES = {
    "text": QLineEdit,
    "spin": QDoubleSpinBox,
    "int": QSpinBox,
    "check": QCheckBox,
    "label": QLabel,
}


class Row(object):
    """One form row: label + field widget (+ optional button)."""

    def __init__(self, form, key, label, kind="text", value=None, parent=None,
                 options=None, decimals=3, minimum=-1e9, maximum=1e9,
                 step=0.01, enabled=True):
        self.key = key
        self.kind = kind
        self.label = label
        if kind == "combo":
            cls = QComboBox
        else:
            cls = FIELD_CLASSES.get(kind, QLineEdit)
        self.widget = cls(parent)
        if kind in ("spin", "int"):
            if kind == "spin":
                self.widget.setDecimals(decimals)
                self.widget.setRange(minimum, maximum)
            else:
                self.widget.setRange(int(minimum), int(maximum))
            if kind == "spin":
                self.widget.setSingleStep(step)
            if value is not None:
                try:
                    if kind == "int":
                        self.widget.setValue(int(float(value)))
                    else:
                        self.widget.setValue(float(value))
                except (TypeError, ValueError):
                    self.widget.setValue(0)
        elif kind == "check":
            self.widget.setChecked(bool(value))
        elif kind == "combo":
            for opt in (options or []):
                self.widget.addItem(str(opt))
            if value is not None and value != "":
                idx = self.widget.findText(str(value))
                if idx >= 0:
                    self.widget.setCurrentIndex(idx)
        else:
            if value is not None:
                self.widget.setText(str(value))
        self.widget.setEnabled(enabled)
        form.addRow(QLabel(label, parent), self.widget)

    def get(self):
        if self.kind == "check":
            return self.widget.isChecked()
        if self.kind in ("spin", "int"):
            return self.widget.value()
        if self.kind == "combo":
            return self.widget.currentText()
        return self.widget.text()

    def set(self, value):
        if self.kind == "check":
            self.widget.setChecked(bool(value))
        elif self.kind in ("spin", "int"):
            try:
                if self.kind == "int":
                    self.widget.setValue(int(float(value)))
                else:
                    self.widget.setValue(float(value))
            except (TypeError, ValueError):
                pass
        elif self.kind == "combo":
            idx = self.widget.findText(str(value))
            if idx >= 0:
                self.widget.setCurrentIndex(idx)
        else:
            self.widget.setText(str(value))


class FormPage(QWidget):
    """A notebook tab: vertical stack of form sections."""

    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        from PyQt5.QtWidgets import QVBoxLayout
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(8, 8, 8, 8)
        self._rows = []
        self.title = title

    def section(self, name):
        from PyQt5.QtWidgets import QLabel
        lab = QLabel(name, self)
        lab.setStyleSheet("font-weight:bold; color:#1f4e79;")
        self._lay.addWidget(lab)
        form = QFormLayout()
        self._lay.addLayout(form)
        return form

    def add_row(self, form, key, label, kind="text", value=None, options=None,
                **kw):
        row = Row(form, key, label, kind, value, self, options, **kw)
        self._rows.append(row)
        return row

    def row(self, key):
        for r in self._rows:
            if r.key == key:
                return r
        return None

    def values(self):
        return {r.key: r.get() for r in self._rows}

    def load(self, values):
        for r in self._rows:
            if r.key in values:
                r.set(values[r.key])
        return self
