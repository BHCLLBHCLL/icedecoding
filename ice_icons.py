# -*- coding: utf-8 -*-
"""Icepak-style vector icons for ice_gui (ported from cab_icons.AppIcons)."""

from __future__ import annotations

import math

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QPolygon,
)


class IceIcons:
    """24px icon-only toolbar / tree glyphs matching Icepak command names."""

    _cache = {}

    @classmethod
    def get(cls, name, size=24):
        key = (name, size)
        if key not in cls._cache:
            cls._cache[key] = QIcon(cls._paint(name, size))
        return cls._cache[key]

    @classmethod
    def _paint(cls, name, size):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        m = max(1, size // 10)
        r = QRectF(m, m, size - 2 * m, size - 2 * m)
        drawer = getattr(cls, "_draw_" + name, None)
        if drawer:
            drawer(p, r, size)
        else:
            cls._draw_letter(p, r, name[:1].upper())
        p.end()
        return pm

    @staticmethod
    def _pen(color, w=1.6):
        pen = QPen(QColor(color))
        pen.setWidthF(w)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    @classmethod
    def _draw_letter(cls, p, r, ch, fill="#dde3ea", fg="#37474f"):
        p.setPen(cls._pen("#555", 1.2))
        p.setBrush(QBrush(QColor(fill)))
        p.drawRoundedRect(r, 3, 3)
        p.setPen(cls._pen(fg, 1.0))
        p.setFont(QFont("Arial", max(7, int(r.height() * 0.48)), QFont.Bold))
        p.drawText(r.toRect(), Qt.AlignCenter, ch)

    @classmethod
    def _draw_new(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.3))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRoundedRect(r.adjusted(r.width() * 0.12, 0, 0, 0), 2, 2)
        p.setBrush(QBrush(QColor("#cfd8dc")))
        fold = QPolygon([
            QPoint(int(r.right() - r.width() * 0.02), int(r.top())),
            QPoint(int(r.right() - r.width() * 0.32), int(r.top())),
            QPoint(int(r.right() - r.width() * 0.02), int(r.top() + r.height() * 0.28)),
        ])
        p.drawPolygon(fold)

    @classmethod
    def _draw_open(cls, p, r, _s):
        p.setPen(cls._pen("#2e75b6", 1.4))
        p.setBrush(QBrush(QColor("#f4c542")))
        tab = QRectF(r.left(), r.top(), r.width() * 0.45, r.height() * 0.28)
        p.drawRoundedRect(tab, 2, 2)
        body = QRectF(r.left(), r.top() + r.height() * 0.22,
                      r.width(), r.height() * 0.72)
        p.setBrush(QBrush(QColor("#ffd966")))
        p.drawRoundedRect(body, 2, 2)

    @classmethod
    def _draw_save(cls, p, r, _s):
        p.setPen(cls._pen("#1f4e79", 1.3))
        p.setBrush(QBrush(QColor("#5b9bd5")))
        p.drawRoundedRect(r, 2, 2)
        p.setBrush(QBrush(QColor("#fff")))
        slot = QRectF(r.left() + r.width() * 0.22, r.top(),
                      r.width() * 0.56, r.height() * 0.38)
        p.drawRect(slot)

    @classmethod
    def _draw_print(cls, p, r, _s):
        p.setPen(cls._pen("#546e7a", 1.2))
        p.setBrush(QBrush(QColor("#90a4ae")))
        p.drawRoundedRect(r.adjusted(0, r.height() * 0.22, 0, -r.height() * 0.18), 2, 2)
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRect(r.adjusted(r.width() * 0.18, 0, -r.width() * 0.18, -r.height() * 0.55))
        p.drawRect(r.adjusted(r.width() * 0.18, r.height() * 0.62,
                              -r.width() * 0.18, 0))

    @classmethod
    def _draw_image(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(QBrush(QColor("#bbdefb")))
        p.drawRect(r)
        p.setBrush(QBrush(QColor("#ffd54f")))
        p.drawEllipse(QRectF(r.left() + 2, r.top() + 2,
                             r.width() * 0.28, r.height() * 0.28))
        poly = QPolygon([
            QPoint(int(r.left()), int(r.bottom())),
            QPoint(int(r.left() + r.width() * 0.4), int(r.center().y())),
            QPoint(int(r.right()), int(r.bottom())),
        ])
        p.setBrush(QBrush(QColor("#66bb6a")))
        p.drawPolygon(poly)

    @classmethod
    def _draw_undo(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 40 * 16, 220 * 16)
        cx, cy = r.center().x(), r.center().y()
        tip = QPolygon([
            QPoint(int(r.left() + 1), int(cy)),
            QPoint(int(r.left() + r.width() * 0.38), int(cy - r.height() * 0.28)),
            QPoint(int(r.left() + r.width() * 0.38), int(cy + r.height() * 0.08)),
        ])
        p.setBrush(QBrush(QColor("#1565c0")))
        p.setPen(Qt.NoPen)
        p.drawPolygon(tip)

    @classmethod
    def _draw_redo(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), -80 * 16, 220 * 16)
        cx, cy = r.center().x(), r.center().y()
        tip = QPolygon([
            QPoint(int(r.right() - 1), int(cy)),
            QPoint(int(r.right() - r.width() * 0.38), int(cy - r.height() * 0.28)),
            QPoint(int(r.right() - r.width() * 0.38), int(cy + r.height() * 0.08)),
        ])
        p.setBrush(QBrush(QColor("#1565c0")))
        p.setPen(Qt.NoPen)
        p.drawPolygon(tip)

    @classmethod
    def _draw_home(cls, p, r, _s):
        p.setPen(cls._pen("#6d4c41", 1.3))
        p.setBrush(QBrush(QColor("#a1887f")))
        roof = QPolygon([
            QPoint(int(r.center().x()), int(r.top())),
            QPoint(int(r.left()), int(r.center().y())),
            QPoint(int(r.right()), int(r.center().y())),
        ])
        p.drawPolygon(roof)
        p.setBrush(QBrush(QColor("#d7ccc8")))
        p.drawRect(r.adjusted(r.width() * 0.22, r.height() * 0.48,
                              -r.width() * 0.22, 0))

    @classmethod
    def _draw_zoom(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.4))
        p.setBrush(Qt.NoBrush)
        circ = r.adjusted(0, 0, -r.width() * 0.25, -r.height() * 0.25)
        p.drawEllipse(circ)
        p.drawLine(QPoint(int(circ.right() - 1), int(circ.bottom() - 1)),
                   QPoint(int(r.right() - 1), int(r.bottom() - 1)))

    @classmethod
    def _draw_fit(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.6))
        p.setBrush(Qt.NoBrush)
        s = r.width() * 0.28
        corners = [
            (r.left(), r.top(), 1, 1),
            (r.right(), r.top(), -1, 1),
            (r.left(), r.bottom(), 1, -1),
            (r.right(), r.bottom(), -1, -1),
        ]
        for x, y, sx, sy in corners:
            p.drawLine(QPoint(int(x), int(y)), QPoint(int(x + sx * s), int(y)))
            p.drawLine(QPoint(int(x), int(y)), QPoint(int(x), int(y + sy * s)))

    @classmethod
    def _draw_rotate(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 30 * 16, 300 * 16)

    @classmethod
    def _draw_win1(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.3))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRect(r)

    @classmethod
    def _draw_win4(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.2))
        p.setBrush(QBrush(QColor("#eceff1")))
        cx, cy = r.center().x(), r.center().y()
        p.drawRect(QRectF(r.left(), r.top(), cx - r.left() - 1, cy - r.top() - 1))
        p.drawRect(QRectF(cx + 1, r.top(), r.right() - cx - 1, cy - r.top() - 1))
        p.drawRect(QRectF(r.left(), cy + 1, cx - r.left() - 1, r.bottom() - cy - 1))
        p.drawRect(QRectF(cx + 1, cy + 1, r.right() - cx - 1, r.bottom() - cy - 1))

    @classmethod
    def _draw_names(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.1))
        p.setBrush(QBrush(QColor("#fff9c4")))
        p.drawRoundedRect(r, 2, 2)
        p.setFont(QFont("Arial", max(6, int(r.height() * 0.35))))
        p.drawText(r.toRect(), Qt.AlignCenter, "Aa")

    @classmethod
    def _draw_axis(cls, p, r, label, color):
        p.setPen(cls._pen(color, 1.3))
        p.setBrush(QBrush(QColor(color)))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(cls._pen("#fff", 1.0))
        p.setFont(QFont("Arial", max(7, int(r.height() * 0.42)), QFont.Bold))
        p.drawText(r.toRect(), Qt.AlignCenter, label)

    @classmethod
    def _draw_axis_x(cls, p, r, _s):
        cls._draw_axis(p, r, "−X", "#c62828")

    @classmethod
    def _draw_axis_y(cls, p, r, _s):
        cls._draw_axis(p, r, "+Y", "#2e7d32")

    @classmethod
    def _draw_axis_z(cls, p, r, _s):
        cls._draw_axis(p, r, "−Z", "#1565c0")

    @classmethod
    def _draw_iso(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawRect(r.adjusted(r.width() * 0.15, r.height() * 0.28,
                              -r.width() * 0.05, -r.height() * 0.05))
        p.setBrush(QBrush(QColor("#64b5f6")))
        top = QPolygon([
            QPoint(int(r.left() + r.width() * 0.15), int(r.top() + r.height() * 0.28)),
            QPoint(int(r.left() + r.width() * 0.38), int(r.top() + 1)),
            QPoint(int(r.right() - 1), int(r.top() + 1)),
            QPoint(int(r.right() - r.width() * 0.05), int(r.top() + r.height() * 0.28)),
        ])
        p.drawPolygon(top)

    @classmethod
    def _draw_reverse(cls, p, r, _s):
        p.setPen(cls._pen("#6a1b9a", 1.8))
        p.setBrush(Qt.NoBrush)
        cx, cy = r.center().x(), r.center().y()
        p.drawLine(QPoint(int(r.left() + 2), int(cy)), QPoint(int(r.right() - 2), int(cy)))
        p.drawLine(QPoint(int(r.left() + 2), int(cy)),
                   QPoint(int(r.left() + r.width() * 0.35), int(cy - r.height() * 0.25)))
        p.drawLine(QPoint(int(r.right() - 2), int(cy)),
                   QPoint(int(r.right() - r.width() * 0.35), int(cy + r.height() * 0.25)))

    @classmethod
    def _draw_limits(cls, p, r, _s):
        cls._draw_letter(p, r, "T", "#ffcdd2", "#b71c1c")

    @classmethod
    def _draw_mesh(cls, p, r, _s):
        p.setPen(cls._pen("#00838f", 1.2))
        p.setBrush(QBrush(QColor("#80deea")))
        p.drawEllipse(r)
        p.setPen(cls._pen("#006064", 1.0))
        cx, cy = r.center().x(), r.center().y()
        for ang in (0, 60, 120):
            a = math.radians(ang)
            x = cx + math.cos(a) * r.width() * 0.42
            y = cy + math.sin(a) * r.height() * 0.42
            p.drawLine(QPointF(cx, cy), QPointF(x, y))

    @classmethod
    def _draw_radiation(cls, p, r, _s):
        p.setPen(cls._pen("#ef6c00", 1.3))
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.drawEllipse(r.adjusted(r.width() * 0.28, r.height() * 0.28,
                                 -r.width() * 0.28, -r.height() * 0.28))
        cx, cy = r.center().x(), r.center().y()
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(cx + math.cos(a) * r.width() * 0.22,
                               cy + math.sin(a) * r.height() * 0.22),
                       QPointF(cx + math.cos(a) * r.width() * 0.48,
                               cy + math.sin(a) * r.height() * 0.48))

    @classmethod
    def _draw_check(cls, p, r, _s):
        p.setPen(cls._pen("#2e7d32", 2.2))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(r.left() + r.width() * 0.15, r.center().y())
        path.lineTo(r.left() + r.width() * 0.4, r.bottom() - 2)
        path.lineTo(r.right() - 2, r.top() + 2)
        p.drawPath(path)

    @classmethod
    def _draw_solve(cls, p, r, _s):
        p.setPen(cls._pen("#1b5e20", 1.2))
        p.setBrush(QBrush(QColor("#66bb6a")))
        tri = QPolygon([
            QPoint(int(r.left() + 2), int(r.top() + 1)),
            QPoint(int(r.left() + 2), int(r.bottom() - 1)),
            QPoint(int(r.right() - 1), int(r.center().y())),
        ])
        p.drawPolygon(tri)

    @classmethod
    def _draw_optim(cls, p, r, _s):
        cls._draw_letter(p, r, "O", "#c8e6c9", "#1b5e20")

    @classmethod
    def _cube(cls, p, r, fill, edge):
        p.setPen(cls._pen(edge, 1.2))
        p.setBrush(QBrush(QColor(fill)))
        p.drawRect(r.adjusted(r.width() * 0.12, r.height() * 0.22,
                              -r.width() * 0.08, -r.height() * 0.04))
        p.setBrush(QBrush(QColor(fill)))
        top = QPolygon([
            QPoint(int(r.left() + r.width() * 0.12), int(r.top() + r.height() * 0.22)),
            QPoint(int(r.left() + r.width() * 0.32), int(r.top() + 1)),
            QPoint(int(r.right() - r.width() * 0.08), int(r.top() + 1)),
            QPoint(int(r.right() - r.width() * 0.08), int(r.top() + r.height() * 0.22)),
        ])
        p.drawPolygon(top)

    @classmethod
    def _draw_block(cls, p, r, _s):
        cls._cube(p, r, "#90caf9", "#1565c0")

    @classmethod
    def _draw_plate(cls, p, r, _s):
        p.setPen(cls._pen("#ef6c00", 1.2))
        p.setBrush(QBrush(QColor("#ffcc80")))
        p.drawRoundedRect(r.adjusted(1, r.height() * 0.32, -1, -r.height() * 0.32), 2, 2)

    @classmethod
    def _draw_fan(cls, p, r, _s):
        p.setPen(cls._pen("#00838f", 1.3))
        p.setBrush(QBrush(QColor("#80deea")))
        p.drawEllipse(r)
        p.setBrush(QBrush(QColor("#006064")))
        p.drawEllipse(r.adjusted(r.width() * 0.35, r.height() * 0.35,
                                 -r.width() * 0.35, -r.height() * 0.35))

    @classmethod
    def _draw_opening(cls, p, r, _s):
        p.setPen(cls._pen("#f9a825", 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(2, 2, -2, -2))
        p.drawLine(QPoint(int(r.left() + 2), int(r.top() + 2)),
                   QPoint(int(r.right() - 2), int(r.bottom() - 2)))

    @classmethod
    def _draw_wall(cls, p, r, _s):
        p.setPen(cls._pen("#616161", 1.2))
        p.setBrush(QBrush(QColor("#bdbdbd")))
        p.drawRect(r.adjusted(r.width() * 0.28, 1, -r.width() * 0.28, -1))

    @classmethod
    def _draw_source(cls, p, r, _s):
        p.setPen(cls._pen("#c62828", 1.2))
        p.setBrush(QBrush(QColor("#ef9a9a")))
        p.drawEllipse(r)
        p.setPen(cls._pen("#b71c1c", 1.4))
        p.setFont(QFont("Arial", max(7, int(r.height() * 0.45)), QFont.Bold))
        p.drawText(r.toRect(), Qt.AlignCenter, "Q")

    @classmethod
    def _draw_grille(cls, p, r, _s):
        p.setPen(cls._pen("#6d4c41", 1.1))
        p.setBrush(QBrush(QColor("#bcaaa4")))
        p.drawRect(r)
        p.setPen(cls._pen("#4e342e", 1.0))
        for i in range(1, 4):
            y = r.top() + r.height() * i / 4.0
            p.drawLine(QPoint(int(r.left()), int(y)), QPoint(int(r.right()), int(y)))

    @classmethod
    def _draw_heatsink(cls, p, r, _s):
        p.setPen(cls._pen("#8d6e63", 1.1))
        p.setBrush(QBrush(QColor("#bcaaa4")))
        p.drawRect(r.adjusted(0, r.height() * 0.7, 0, 0))
        for i in range(5):
            x = r.left() + r.width() * (0.08 + i * 0.18)
            p.drawRect(QRectF(x, r.top(), r.width() * 0.1, r.height() * 0.72))

    @classmethod
    def _draw_pcb(cls, p, r, _s):
        p.setPen(cls._pen("#2e7d32", 1.2))
        p.setBrush(QBrush(QColor("#81c784")))
        p.drawRoundedRect(r, 2, 2)

    @classmethod
    def _draw_package(cls, p, r, _s):
        p.setPen(cls._pen("#6a1b9a", 1.2))
        p.setBrush(QBrush(QColor("#ce93d8")))
        p.drawRoundedRect(r, 2, 2)

    @classmethod
    def _draw_enclosure(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(1, 1, -1, -1))
        p.drawRect(r.adjusted(r.width() * 0.18, r.height() * 0.18,
                              -r.width() * 0.18, -r.height() * 0.18))

    @classmethod
    def _draw_assembly(cls, p, r, _s):
        cls._draw_letter(p, r, "A", "#b0bec5", "#263238")

    @classmethod
    def _draw_network(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.4))
        p.setBrush(QBrush(QColor("#90caf9")))
        pts = [
            QPointF(r.left() + 2, r.center().y()),
            QPointF(r.center().x(), r.top() + 2),
            QPointF(r.right() - 2, r.center().y()),
            QPointF(r.center().x(), r.bottom() - 2),
        ]
        p.drawLine(pts[0], pts[1])
        p.drawLine(pts[1], pts[2])
        p.drawLine(pts[2], pts[3])
        p.drawLine(pts[3], pts[0])
        for pt in pts:
            p.drawEllipse(pt, 2.2, 2.2)

    @classmethod
    def _draw_blower(cls, p, r, _s):
        p.setPen(cls._pen("#00838f", 1.2))
        p.setBrush(QBrush(QColor("#4dd0e1")))
        p.drawRoundedRect(r.adjusted(0, r.height() * 0.2, -r.width() * 0.15,
                                     -r.height() * 0.2), 3, 3)
        p.drawEllipse(QRectF(r.right() - r.width() * 0.4, r.top(),
                             r.width() * 0.4, r.height()))

    @classmethod
    def _draw_periodic(cls, p, r, _s):
        cls._draw_letter(p, r, "P", "#b3e5fc", "#01579b")

    @classmethod
    def _draw_resistance(cls, p, r, _s):
        p.setPen(cls._pen("#ad1457", 1.6))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(r.left(), r.center().y())
        n = 6
        for i in range(n):
            x = r.left() + r.width() * (i + 1) / (n + 1)
            y = r.top() + (2 if i % 2 == 0 else r.height() - 2)
            path.lineTo(x, y)
        path.lineTo(r.right(), r.center().y())
        p.drawPath(path)

    @classmethod
    def _draw_material(cls, p, r, _s):
        cls._draw_letter(p, r, "M", "#c8e6c9", "#1b5e20")

    @classmethod
    def _draw_edit(cls, p, r, _s):
        p.setPen(cls._pen("#5d4037", 1.3))
        p.setBrush(QBrush(QColor("#ffe0b2")))
        poly = QPolygon([
            QPoint(int(r.left() + 2), int(r.bottom() - 2)),
            QPoint(int(r.left() + r.width() * 0.28), int(r.bottom() - 2)),
            QPoint(int(r.right() - 2), int(r.top() + r.height() * 0.28)),
            QPoint(int(r.right() - r.width() * 0.28), int(r.top() + 2)),
        ])
        p.drawPolygon(poly)

    @classmethod
    def _draw_delete(cls, p, r, _s):
        p.setPen(cls._pen("#c62828", 2.0))
        p.drawLine(QPoint(int(r.left() + 2), int(r.top() + 2)),
                   QPoint(int(r.right() - 2), int(r.bottom() - 2)))
        p.drawLine(QPoint(int(r.right() - 2), int(r.top() + 2)),
                   QPoint(int(r.left() + 2), int(r.bottom() - 2)))

    @classmethod
    def _draw_move(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.6))
        cx, cy = r.center().x(), r.center().y()
        p.drawLine(QPoint(int(r.left() + 2), int(cy)), QPoint(int(r.right() - 2), int(cy)))
        p.drawLine(QPoint(int(cx), int(r.top() + 2)), QPoint(int(cx), int(r.bottom() - 2)))

    @classmethod
    def _draw_copy(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.2))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRect(r.adjusted(r.width() * 0.18, 0, 0, -r.height() * 0.18))
        p.drawRect(r.adjusted(0, r.height() * 0.18, -r.width() * 0.18, 0))

    @classmethod
    def _draw_align(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.5))
        p.drawLine(QPoint(int(r.center().x()), int(r.top())),
                   QPoint(int(r.center().x()), int(r.bottom())))
        p.setBrush(QBrush(QColor("#90caf9")))
        p.drawRect(QRectF(r.left(), r.top() + r.height() * 0.15,
                          r.width() * 0.38, r.height() * 0.7))
        p.drawRect(QRectF(r.right() - r.width() * 0.38, r.top() + r.height() * 0.15,
                          r.width() * 0.38, r.height() * 0.7))

    @classmethod
    def _draw_face(cls, p, r, _s):
        p.setPen(cls._pen("#0277bd", 1.2))
        p.setBrush(QBrush(QColor("#81d4fa")))
        p.drawRoundedRect(r, 2, 2)

    @classmethod
    def _draw_plane(cls, p, r, _s):
        p.setPen(cls._pen("#0277bd", 1.2))
        p.setBrush(QBrush(QColor("#81d4fa")))
        poly = QPolygon([
            QPoint(int(r.left() + r.width() * 0.08), int(r.bottom() - 1)),
            QPoint(int(r.left() + r.width() * 0.35), int(r.top() + 1)),
            QPoint(int(r.right() - 1), int(r.top() + 1)),
            QPoint(int(r.right() - r.width() * 0.27), int(r.bottom() - 1)),
        ])
        p.drawPolygon(poly)

    @classmethod
    def _draw_iso_surf(cls, p, r, _s):
        p.setPen(cls._pen("#6a1b9a", 1.3))
        p.setBrush(QBrush(QColor("#ce93d8")))
        p.drawEllipse(r.adjusted(2, r.height() * 0.2, -2, -r.height() * 0.2))

    @classmethod
    def _draw_point(cls, p, r, _s):
        p.setPen(cls._pen("#c62828", 1.2))
        p.setBrush(QBrush(QColor("#ef9a9a")))
        p.drawEllipse(r.adjusted(r.width() * 0.28, r.height() * 0.28,
                                 -r.width() * 0.28, -r.height() * 0.28))

    @classmethod
    def _draw_probe(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.4))
        p.drawLine(QPoint(int(r.left() + 2), int(r.bottom() - 2)),
                   QPoint(int(r.right() - 4), int(r.top() + 4)))
        p.setBrush(QBrush(QColor("#ef5350")))
        p.drawEllipse(QPoint(int(r.right() - 4), int(r.top() + 4)), 3, 3)

    @classmethod
    def _draw_plot(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.4))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(r.left(), r.bottom() - 2)
        path.lineTo(r.left() + r.width() * 0.3, r.center().y())
        path.lineTo(r.left() + r.width() * 0.6, r.top() + r.height() * 0.2)
        path.lineTo(r.right(), r.top() + r.height() * 0.45)
        p.drawPath(path)

    @classmethod
    def _draw_history(cls, p, r, _s):
        cls._draw_plot(p, r, _s)

    @classmethod
    def _draw_trials(cls, p, r, _s):
        cls._draw_letter(p, r, "Tr", "#d1c4e9", "#4527a0")

    @classmethod
    def _draw_transient(cls, p, r, _s):
        cls._draw_letter(p, r, "t", "#fff9c4", "#f57f17")

    @classmethod
    def _draw_sol_id(cls, p, r, _s):
        cls._draw_letter(p, r, "ID", "#cfd8dc", "#37474f")

    @classmethod
    def _draw_report(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.2))
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawRoundedRect(r, 2, 2)
        p.setPen(cls._pen("#263238", 1.0))
        for i in range(3):
            y = r.top() + r.height() * (0.3 + i * 0.22)
            p.drawLine(QPoint(int(r.left() + 3), int(y)),
                       QPoint(int(r.right() - 3), int(y)))

    @classmethod
    def _draw_pick(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.4))
        path = QPainterPath()
        path.moveTo(r.left() + 2, r.top() + 2)
        path.lineTo(r.left() + 2, r.bottom() - 2)
        path.lineTo(r.left() + r.width() * 0.35, r.top() + r.height() * 0.55)
        path.lineTo(r.left() + r.width() * 0.55, r.bottom() - 2)
        path.lineTo(r.right() - 2, r.top() + r.height() * 0.35)
        path.closeSubpath()
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawPath(path)

    @classmethod
    def _draw_boxpick(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.3))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(1, 1, -1, -1))

    @classmethod
    def _draw_pan(cls, p, r, _s):
        cls._draw_move(p, r, _s)

    @classmethod
    def _draw_hide(cls, p, r, _s):
        p.setPen(cls._pen("#ef6c00", 1.3))
        p.setBrush(QBrush(QColor("#ffe0b2")))
        p.drawEllipse(r.adjusted(r.width() * 0.1, r.height() * 0.22,
                                 -r.width() * 0.1, -r.height() * 0.18))
        p.setPen(cls._pen("#c62828", 1.8))
        p.drawLine(QPoint(int(r.left() + 2), int(r.bottom() - 2)),
                   QPoint(int(r.right() - 2), int(r.top() + 2)))

    @classmethod
    def _draw_existing(cls, p, r, _s):
        cls._draw_open(p, r, _s)

    @classmethod
    def _draw_unpack(cls, p, r, _s):
        p.setPen(cls._pen("#5d4037", 1.2))
        p.setBrush(QBrush(QColor("#bcaaa4")))
        p.drawRoundedRect(r.adjusted(0, r.height() * 0.15, 0, 0), 2, 2)
        p.setBrush(QBrush(QColor("#8d6e63")))
        p.drawRect(r.adjusted(r.width() * 0.15, 0, -r.width() * 0.15, -r.height() * 0.7))

    @classmethod
    def _draw_quit(cls, p, r, _s):
        p.setPen(cls._pen("#c62828", 1.3))
        p.setBrush(QBrush(QColor("#ef9a9a")))
        p.drawEllipse(r)
        p.setPen(cls._pen("#b71c1c", 2.0))
        p.drawLine(QPoint(int(r.center().x()), int(r.top() + 2)),
                   QPoint(int(r.center().x()), int(r.center().y() + 2)))

    @classmethod
    def _draw_folder(cls, p, r, _s):
        cls._draw_open(p, r, _s)

    @classmethod
    def _draw_group(cls, p, r, _s):
        cls._draw_letter(p, r, "G", "#bbdefb", "#0d47a1")

    @classmethod
    def _draw_domain(cls, p, r, _s):
        p.setPen(cls._pen("#2e7d32", 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(1, 1, -1, -1))

    @classmethod
    def _draw_trash(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.3))
        p.setBrush(QBrush(QColor("#90a4ae")))
        p.drawRoundedRect(r.adjusted(r.width() * 0.18, r.height() * 0.22,
                                     -r.width() * 0.18, 0), 2, 2)
        p.drawRect(r.adjusted(r.width() * 0.08, r.height() * 0.12,
                              -r.width() * 0.08, -r.height() * 0.72))

    @classmethod
    def _draw_inactive(cls, p, r, _s):
        cls._draw_letter(p, r, "∅", "#eeeeee", "#9e9e9e")

    @classmethod
    def _draw_library(cls, p, r, _s):
        p.setPen(cls._pen("#5d4037", 1.2))
        p.setBrush(QBrush(QColor("#d7ccc8")))
        p.drawRoundedRect(r, 2, 2)
        p.setBrush(QBrush(QColor("#8d6e63")))
        for i in range(3):
            y = r.top() + r.height() * (0.2 + i * 0.25)
            p.drawRect(QRectF(r.left() + 3, y, r.width() - 6, r.height() * 0.12))
