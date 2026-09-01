# -*- coding: utf-8 -*-
"""
P6 dialogs & widgets: solve settings, run solution, patch temperatures,
QPainter 2D plot window + residual monitor.
"""
import math

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTabWidget, QVBoxLayout, QWidget)

from ice_forms import FormPage
from ice_solve import (ADVANCED_FIELDS, BASIC_FIELDS, PARALLEL_FIELDS,
                       read_setters, write_setter)


def _page_for(fields, problem):
    page = FormPage()
    form = page.section("Settings")
    for key, label, kind, options, *rest in fields:
        value = read_setters(problem, key, rest[0] if rest else None)
        if kind == "check":
            page.add_row(form, key, label, "check",
                         bool(value) if value not in (None, "") else False)
        else:
            page.add_row(form, key, label, kind, value, options=options)
    return page


class SolveSettingsDialog(QDialog):
    """Solve -> Settings (Basic / Advanced / Parallel) — edits problem vars."""

    KINDS = {"Basic settings": BASIC_FIELDS,
             "Advanced settings": ADVANCED_FIELDS,
             "Parallel settings": PARALLEL_FIELDS}

    def __init__(self, parent=None, kind="Basic settings", problem=None,
                 title=None):
        super().__init__(parent)
        self._kind = kind
        self._problem = problem
        self.setWindowTitle(title or kind)
        self.setMinimumSize(480, 420)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget(self)
        self.page = _page_for(self.KINDS.get(kind, BASIC_FIELDS), problem)
        self.tabs.addTab(self.page, kind)
        v.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_apply = QPushButton("Apply", self)
        self.btn_apply.clicked.connect(self._apply)
        ok_btn = QPushButton("OK", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._apply_and_close)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        row.addWidget(self.btn_apply)
        row.addWidget(ok_btn)
        row.addWidget(cancel)
        v.addLayout(row)

    def _apply(self):
        for row in self.page._rows:
            write_setter(self._problem, row.key, row.get())
        parent = self._parent
        mark = getattr(parent, "_mark_dirty", None)
        if mark:
            mark("%s edited" % self._kind)
        log = getattr(parent, "log", None)
        if log:
            log("%s applied to problem" % self._kind)

    def _apply_and_close(self):
        self._apply()
        self.accept()

    @property
    def _parent(self):
        return self.parent() or self.window()


class RunSolutionDialog(QDialog):
    """Solve -> Run solution panel: iterations, convergence, solution id."""

    def __init__(self, parent=None, problem=None):
        super().__init__(parent)
        self.setWindowTitle("Run solution")
        self.setMinimumSize(460, 300)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        page = FormPage(self)
        f = page.section("Run")
        page.add_row(f, "solve_id", "Solution ID", "text",
                     read_setters(problem, "solve_id", "transient00"))
        page.add_row(f, "iters", "Iterations", "int", 100, minimum=1,
                     maximum=100000)
        page.add_row(f, "cont", "Continuity criteria", "text", 1e-4)
        page.add_row(f, "energy", "Energy criteria", "text", 1e-6)
        page.add_row(f, "solve_startmon", "Start monitor", "check",
                     bool(read_setters(problem, "solve_startmon", 1)))
        page.add_row(f, "solve_where", "Where", "combo", "here",
                     options=["here", "remote", "queue"])
        self.page = page
        v.addWidget(page, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok_btn = QPushButton("OK", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._ok)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel)
        v.addLayout(row)

    def _ok(self):
        self.values = self.page.values()
        self.accept()

    def params(self):
        return getattr(self, "values", self.page.values())


class PatchTemperaturesDialog(QDialog):
    """Solve -> Patch temperatures: name -> temperature (model attach)."""

    def __init__(self, parent=None, model=None, patches=None):
        super().__init__(parent)
        self.setWindowTitle("Patch temperatures")
        self.setMinimumSize(420, 320)
        self._model = model
        self._patches = dict(patches or {})
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        page = FormPage(self)
        f = page.section("Initial temperature patch")
        page.add_row(f, "object", "Object name", "text", "")
        page.add_row(f, "temp", "Temperature (C)", "spin", 80.0)
        f = page.section("Existing patches")
        for name, t in self._patches.items():
            page.add_row(f, "pt_%s" % name, name, "label", "%g C" % t)
        self.page = page
        v.addWidget(page, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok_btn = QPushButton("Patch", self)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._ok)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel)
        v.addLayout(row)

    def _ok(self):
        name = str(self.page.row("object").get()).strip()
        temp = float(self.page.row("temp").get())
        if name:
            self._patches[name] = temp
        self.accept()

    def patches(self):
        return dict(self._patches)


class PlotWindow(QWidget):
    """Minimal 2D polyline plot (convergence/variation/history/trials)."""

    COLORS = [QColor("#1f4e79"), QColor("#d32f2f"), QColor("#2e7d32"),
              QColor("#7b1fa2")]

    def __init__(self, parent=None, title="Plot"):
        super().__init__(parent)
        self._title = title
        self._series = []
        self._xlabel = "Iteration"
        self._ylabel = "Residual"
        self.setMinimumSize(420, 260)

    def set_data(self, series, title=None, xlabel=None, ylabel=None,
                 log_y=False):
        """series: list of [(x, y), ...] or list of x,list-of-y? -> list of pts."""
        self._series = [list(s) for s in series]
        if title:
            self._title = title
        if xlabel:
            self._xlabel = xlabel
        if ylabel:
            self._ylabel = ylabel
        self._log_y = log_y
        self.update()

    def set_histogram(self, values, bins=12, title=None, xlabel=None):
        """Temperature distribution histogram (bar plot)."""
        if not values:
            self._series = []
            self.update()
            return
        import numpy as np
        lo, hi = float(min(values)), float(max(values))
        span = (hi - lo) or 1e-12
        hist = [0] * bins
        for v in values:
            i = min(bins - 1, int((v - lo) / span * bins))
            hist[i] += 1
        edges = [lo + i * span / bins for i in range(bins + 1)]
        m = max(hist) or 1
        series = [[(edges[i], hist[i]), (edges[i + 1], hist[i]),
                   (edges[i + 1], 0.0)] for i in range(bins)]
        self._series = series
        if title:
            self._title = title
        self._xlabel = xlabel or "Temperature (K)"
        self._ylabel = "Cell count"
        self._log_y = False
        self.update()

    def _bounds(self):
        xs, ys = [], []
        for s in self._series:
            for x, y in s:
                xs.append(x)
                ys.append(math.log10(max(y, 1e-300)) if
                          getattr(self, "_log_y", False) else y)
        if not xs:
            return 0.0, 1.0, 0.0, 1.0
        return min(xs), max(xs), min(ys), max(ys)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        rect = self.rect().adjusted(48, 16, -16, -28)
        p.setPen(QPen(QColor("#90a4ae"), 1))
        p.drawRect(rect)
        x0, x1, y0, y1 = self._bounds()
        if not self._series:
            p.setPen(QPen(QColor("#607d8b")))
            p.drawText(rect, Qt.AlignCenter, "no data")
            return
        spanx = (x1 - x0) or 1.0
        spany = (y1 - y0) or 1.0
        p.setPen(QPen(QColor("#455a64")))
        p.drawText(QRectF(0, self.height() - 22, self.width(), 20),
                   Qt.AlignCenter, self._title)
        for idx, s in enumerate(self._series):
            p.setPen(QPen(self.COLORS[idx % len(self.COLORS)], 2))
            pts = []
            for x, y in s:
                yy = math.log10(max(y, 1e-300)) if getattr(self,
                                                           "_log_y",
                                                           False) else y
                px = rect.x() + (x - x0) / spanx * rect.width()
                py = rect.y() + rect.height() - \
                    (yy - y0) / spany * rect.height()
                pts.append((int(px), int(py)))
            if len(pts) > 1:
                from PyQt5.QtCore import QPoint
                p.drawPolyline([QPoint(a, b) for a, b in pts])
        p.end()


class ResidualMonitorWindow(QWidget):
    """Solve -> Solution monitor: residual plot + last values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Solution monitor")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.plot = PlotWindow(self, title="Residuals")
        self.plot._log_y = True
        v.addWidget(self.plot, 1)
        self.lbl = QLabel("No residuals loaded", self)
        v.addWidget(self.lbl)

    def set_residuals(self, rows):
        series = []
        labs = ["continuity", "x-velocity", "y-velocity", "temperature"]
        for k in range(4):
            series.append([(it, vals[k]) for it, vals in rows])
        self.plot.set_data(series, title="Residuals (%d iters)" % len(rows),
                           log_y=True)
        last = rows[-1] if rows else None
        if last:
            self.lbl.setText(", ".join("%s = %.3g" % (labs[k], last[1][k])
                                       for k in range(4)))
