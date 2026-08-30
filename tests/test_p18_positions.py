# -*- coding: utf-8 -*-
"""P18 tests: oracle node-position extraction + first-order HDM prototype."""
import os
import struct
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.grid_positions import extract_nodes
from ice_hdm import (parse_grid_params, problem_grid_settings, face_planes,
                     leaf_vertices, snap_vertices, position_match)

pytestmark = []


def _fake_grid_output(pts):
    """Synthesize the observed binary layout: header (count at 24),
    marker 0x6baf1c32 at 60, records [BE counter][x][y][z] 28B from 64."""
    parts = [struct.pack(">iiiii", 4, 1, 2, 0, 58)]
    desc = b"X" * 40              # fill header gap up to marker area
    parts.append(desc)
    parts.append(struct.pack(">i", 0x6BAF1C32))
    parts.append(struct.pack(">i", 0))
    for i, (x, y, z) in enumerate(pts):
        parts.append(struct.pack(">iddd", i, x, y, z))
    return b"".join(parts)


def test_extract_nodes_roundtrip():
    rng = np.random.default_rng(7)
    pts = rng.uniform(0, 1, (50, 3))
    data = _fake_grid_output(pts)
    with tempfile.NamedTemporaryFile(suffix=".grid", delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        # the synthetic header lacks the true count at offset 24 -> patch
        raw = bytearray(open(path, "rb").read())
        raw[24:28] = struct.pack(">i", len(pts))
        open(path, "wb").write(bytes(raw))
        got, sec = extract_nodes(path, len(pts))
        assert got is not None, sec
        assert np.allclose(np.sort(got, axis=0), np.sort(pts, axis=0))
    finally:
        os.unlink(path)


def test_parse_grid_params_synthetic():
    d = tempfile.mkdtemp(prefix="ice_gp_")
    p = os.path.join(d, "grid_params")
    open(p, "w").write(
        "domain 0 0.0 0.0 0.0 0.3 0.3 0.3 0.01 0.01 1e+37\n"
        "hexa 1 0.1 0.1 0.1 0.2 0.2 0.2 1 0.005 0.005\n")
    recs = parse_grid_params(p)
    assert recs[0]["type"] == "domain"
    assert recs[1]["size"][2] == pytest.approx(0.005)
    faces = face_planes(recs)
    assert (0, 0.1) in faces and (2, 0.2) in faces


def test_problem_settings_synthetic():
    d = tempfile.mkdtemp(prefix="ice_pr_")
    open(os.path.join(d, "problem"), "w").write(
        "set grid_type hdm\nset grid_size_x 0.02\nset grid_gcount_i 10\n")
    st = problem_grid_settings(d)
    assert st.get("grid_size_x") == 0.02
    assert st.get("grid_gcount_i") == 10


def test_leaf_vertices_and_snap():
    boxes = np.array([[0.0, 0.0, 0.0, 0.1, 0.1, 0.1],
                      [0.1, 0.0, 0.0, 0.2, 0.1, 0.1]])
    v = leaf_vertices(boxes)
    assert len(v) == 12          # 2 boxes share a face -> 12 unique corners
    v2 = snap_vertices(v, [(0, 0.0), (0, 0.2)], tol=1e-9)
    assert (v2[:, 0] == 0.0).sum() >= 4


def test_position_match_synthetic():
    a = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    b = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0001, 0.0]])
    m = position_match(a, b)
    assert m["oracle_to_our"][0] == 0.0
    assert m["oracle_to_our"][1] == pytest.approx(0.0)
    assert m["oracle_matched_1e-6"] == pytest.approx(2 / 3.0)


def test_hdm_build_synthetic_fast():
    d = tempfile.mkdtemp(prefix="ice_hdm_")
    open(os.path.join(d, "grid_params"), "w").write(
        "domain 0 0.0 0.0 0.0 0.3 0.3 0.3 0.01 0.01 1e+37\n"
        "hexa 1 0.1 0.1 0.1 0.2 0.2 0.2 1 0.005 0.005\n")
    open(os.path.join(d, "problem"), "w").write(
        "set grid_type hdm\nset grid_size_x 0.02\nset grid_size_y 0.02\n"
        "set grid_size_z 0.02\n")
    from ice_hdm import build
    boxes, verts, params, st = build(d, max_levels=2, max_cells=30000)
    assert len(boxes) > 0
    assert len(verts) > 8
    assert st.get("grid_size_x") == 0.02
