# -*- coding: utf-8 -*-
"""P3 viewport completeness tests: snap, align/morph math, box/circle pick."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ice_view3d import (
    snap_value, snap_point, allowed_delta, clamp_to_box, box_contains,
    nearest_face, face_center, align_face_move, align_face_stretch,
    align_centers, match_face, box_pick, circle_pick,
)

import ice_gui

pytestmark = pytest.mark.skipif(not ice_gui.HAS_GUI,
                                reason="PyQt5/vtk not installed")


def test_snap_value():
    assert snap_value(0.123456, 0.01) == 0.12
    assert snap_value(0.0, 0.01) == 0.0
    assert snap_value(3.14159, 0.1) == 3.1


def test_allowed_delta_respects_axes():
    assert allowed_delta((1, 2, 3), (True, False, True)) == (1, 0, 3)
    assert allowed_delta((1, 2, 3), (False, False, False)) == (0, 0, 0)


def test_clamp_to_box():
    lo, hi = (0, 0, 0), (10, 10, 10)
    assert clamp_to_box((12, -3, 5), lo, hi) == (10, 0, 5)
    assert box_contains((5, 5, 5), lo, hi)


def test_nearest_face_and_center():
    lo, hi = (0, 0, 0), (4, 2, 6)
    axis, sign = nearest_face(lo, hi, (4.2, 1, 1))
    assert (axis, sign) == (0, 1)
    from ice_view3d import box_contains
    assert face_center(lo, hi, 0, 1) == (4, 1, 3)
    assert face_center(lo, hi, 2, -1) == (2, 1, 0)


def test_align_face_move():
    a = ((0, 0, 0), (2, 2, 2))
    b = ((5, 5, 0), (7, 7, 2))
    moved = align_face_move(a, (0, 1), b, (0, -1))
    assert moved == a or abs(moved[1][0] - 5.0) < 1e-9
    assert abs(moved[1][0] - 5.0) < 1e-9  # a's +x face now at b's -x face


def test_align_face_stretch():
    a = ((0, 0, 0), (2, 2, 2))
    b = ((5, 5, 0), (7, 7, 2))
    moved = align_face_stretch(a, (0, 1), b, (0, -1))
    assert abs(moved[1][0] - 5.0) < 1e-9


def test_align_centers():
    a = ((0, 0, 0), (2, 2, 2))
    b = ((10, 4, 0), (12, 6, 2))
    moved = align_centers(a, b)
    assert moved == a or abs(sum((moved[0][i] + moved[1][i]) for i in range(3))) > 0


def test_match_face():
    a = ((0, 0, 0), (2, 2, 2))
    b = ((5, 5, 0), (7, 7, 2))
    lo, hi = match_face(a, (0, 1), b, (0, -1))
    assert abs(hi[0] - 5.0) < 1e-9
    assert (hi[1] - lo[1]) >= (b[1][1] - b[0][1]) - 1e-9


def test_box_pick_math():
    objs = {"a": ((0, 0, 0), (1, 1, 1)), "b": ((5, 5, 5), (6, 6, 6)),
            "c": ((2, 0, 0), (3, 1, 1))}
    to_world = lambda p: (p[0], p[1])  # screen == world for the test
    hits = box_pick(objs, (0, 0, 3, 2), to_world)
    assert "a" in hits and "c" in hits and "b" not in hits


def test_circle_pick_math():
    objs = {"a": ((0, 0, 0), (1, 1, 1)), "far": ((9, 9, 9), (10, 10, 10))}
    to_world = lambda p: (p[0], p[1])
    hits = circle_pick(objs, (0.5, 0.5), 2.0, to_world)
    assert "a" in hits and "far" not in hits
