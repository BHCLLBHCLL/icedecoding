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
                     leaf_vertices, snap_vertices, position_match,
                     model_cylinders, project_to_cylinders,
                     project_to_cylinders_local)

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


def test_project_to_cylinders():
    verts = np.array([
        [0.1, 0.0, 0.05],      # on surface (r=0.1)
        [0.101, 0.0, 0.05],    # slightly outside -> project inward
        [0.099, 0.0, 0.05],    # slightly inside -> project outward
        [0.5, 0.0, 0.05],      # far away -> untouched
        [0.1, 0.0, 0.25],      # beyond axis end -> untouched
    ])
    cyls = [{"p1": np.array([0.0, 0.0, 0.0]), "p2": np.array([0.0, 0.0, 0.2]),
             "r1": 0.1, "r2": 0.1}]
    out = project_to_cylinders(verts, cyls, tol=0.002)
    for v in out[:3]:
        assert abs(np.hypot(v[0], v[1]) - 0.1) < 1e-12
    assert out[3][0] == 0.5
    assert out[4][2] == 0.25


def test_model_cylinders_from_default_object():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet, default_object
    proj = IcepakProject.empty("t18c")
    proj.model.objects.append(default_cabinet())
    proj.model.objects.append(default_object("fan", "fan.1"))
    cyls = model_cylinders(proj.model)
    assert len(cyls) >= 1
    assert cyls[0]["r1"] > 0


def test_base_size_fallback_gcount():
    # grid_size 8 (nonsense) must fall back to L/gcount
    d = tempfile.mkdtemp(prefix="ice_bs_")
    open(os.path.join(d, "grid_params"), "w").write(
        "domain 0 0.0 0.0 0.0 0.3 0.3 0.3 0.01 0.01 1e+37\n")
    open(os.path.join(d, "problem"), "w").write(
        "set grid_type hdm\nset grid_size_x 8\nset grid_size_y 8\n"
        "set grid_size_z 8\nset grid_gcount_i 10\nset grid_gcount_j 10\n"
        "set grid_gcount_k 10\n")
    from ice_hdm import build
    boxes, verts, params, st = build(d, max_levels=1, max_cells=20000,
                                     use_object_sizes=False)
    vmax = verts.max(axis=0) - verts.min(axis=0)
    assert vmax.max() == pytest.approx(0.3)
    # base cells ~10 per axis -> at least 11^2-ish distinct nodes
    assert len(verts) >= 64


def test_curvature_criterion_shallower():
    """Higher curv_c -> shallower shell refinement -> fewer distinct x."""
    d = tempfile.mkdtemp(prefix="ice_curv_")
    open(os.path.join(d, "grid_params"), "w").write(
        "domain 0 0.0 0.0 0.0 0.3 0.3 0.3 0.01 0.01 1e+37\n"
        "hexa 1 0.1 0.1 0.1 0.2 0.2 0.2 1 0.005 0.005\n")
    open(os.path.join(d, "problem"), "w").write(
        "set grid_type hdm\nset grid_size_x 0.02\nset grid_size_y 0.02\n"
        "set grid_size_z 0.02\n")
    from ice_hdm import build
    b1, v1, _, _ = build(d, max_levels=2, max_cells=30000,
                         use_object_sizes=False, cyl_cap=6, curv_c=0.10)
    b2, v2, _, _ = build(d, max_levels=2, max_cells=30000,
                         use_object_sizes=False, cyl_cap=6, curv_c=0.25)
    assert len(b1) >= len(b2)
    assert len(v1) >= len(v2)


def test_in_shell_returns_radius():
    # cone surface radius check via project_to_cylinders + taper
    verts = np.array([[0.05, 0.0, 0.0], [0.1, 0.0, 0.1]])
    cyls = [{"p1": np.array([0.0, 0.0, 0.0]),
             "p2": np.array([0.0, 0.0, 0.1]),
             "r1": 0.05, "r2": 0.1}]
    out = project_to_cylinders(verts, cyls, tol=0.001)
    # first point: r(z=0) = 0.05 -> stays on r=0.05
    assert abs(np.hypot(out[0][0], out[0][1]) - 0.05) < 1e-12
    # second point: r(z=0.1) = 0.1 -> projected onto r=0.1
    assert abs(np.hypot(out[1][0], out[1][1]) - 0.1) < 1e-12


def test_vec_builder_children_halve():
    import numpy as np
    from ice_hdm import hdm_boxes_vec
    params = [{"type": "domain", "id": "0", "lo": (0.0, 0.0, 0.0),
               "hi": (0.3, 0.3, 0.3), "size": (0.01, 0.01, 1e37)},
              {"type": "hexa", "id": "1", "lo": (0.1, 0.1, 0.1),
               "hi": (0.2, 0.2, 0.2), "size": (1, 0.005, 0.005)}]
    cyls = [{"p1": np.array([0.25, 0.25, 0.13]),
             "p2": np.array([0.25, 0.25, 0.19]), "r1": 0.02, "r2": 0.012}]
    b = hdm_boxes_vec(params, ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3)),
                      (0.02, 0.02, 0.02), max_levels=2, max_cells=200000,
                      surface_extra=1, use_object_sizes=True, cyls=cyls,
                      cyl_cap=4, shell_factor=1.05)
    s = b[:, 3:6] - b[:, 0:3]
    base = 0.3 / np.ceil(0.3 / 0.02)
    ratios = s / base
    # every leaf size is a power of 1/2 times the snapped base size
    assert np.allclose(np.round(np.log2(ratios)), np.log2(ratios))
    assert s.max() <= base + 1e-12


def test_vec_matches_recursive_small():
    import numpy as np
    from ice_hdm import hdm_boxes, hdm_boxes_vec
    params = [{"type": "domain", "id": "0", "lo": (0.0, 0.0, 0.0),
               "hi": (0.3, 0.3, 0.3), "size": (0.01, 0.01, 1e37)},
              {"type": "hexa", "id": "1", "lo": (0.1, 0.1, 0.1),
               "hi": (0.2, 0.2, 0.2), "size": (1, 0.005, 0.005)}]
    cyls = [{"p1": np.array([0.25, 0.25, 0.13]),
             "p2": np.array([0.25, 0.25, 0.19]), "r1": 0.02, "r2": 0.012}]
    b1 = hdm_boxes(params, ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3)),
                   (0.02, 0.02, 0.02), max_levels=2, max_cells=2_000_000,
                   surface_extra=1, use_object_sizes=True, cyls=cyls,
                   cyl_cap=4, shell_factor=1.05)
    b2 = hdm_boxes_vec(params, ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3)),
                       (0.02, 0.02, 0.02), max_levels=2,
                       max_cells=2_000_000, surface_extra=1,
                       use_object_sizes=True, cyls=cyls, cyl_cap=4,
                       shell_factor=1.05)
    assert abs(len(b1) - len(b2)) < 0.05 * len(b1)


def test_quad_plane_token_parse():
    from ice_hdm import parse_grid_params
    d = tempfile.mkdtemp(prefix="ice_quad_")
    p = os.path.join(d, "grid_params")
    open(p, "w").write(
        "quad 11 xy 0.12 0.22 0.12 0.18 0.28 0.12 1 0.06 0.06 0.005 0.005 "
        "0.00375 2 1 1\n"
        "hexa 10 0.1 0.2 0.12 0.3 0.4 0.13 1 0.2 0.2 0.01 0.005 0.005 "
        "0.005 0.005 0.005 0.005 2 2 2 2 2 2 0.005 1\n")
    recs = parse_grid_params(p)
    assert len(recs) == 2
    quad = [r for r in recs if r["type"] == "quad"][0]
    assert quad["lo"] == (0.12, 0.22, 0.12)
    assert quad["hi"] == (0.18, 0.28, 0.12)
    hexa = [r for r in recs if r["type"] == "hexa"][0]
    assert 0.005 in hexa["face_sizes"]


def test_project_local_uses_own_cell_size():
    verts = np.array([[0.101, 0.0, 0.05], [0.104, 0.0, 0.05]])
    sizes = np.array([0.01, 0.001])
    cyls = [{"p1": np.array([0.0, 0.0, 0.0]), "p2": np.array([0.0, 0.0, 0.2]),
             "r1": 0.1, "r2": 0.1}]
    out = project_to_cylinders_local(verts, sizes, cyls, tol_frac=0.5)
    # vertex 0: 0.001 < 0.5*0.01 -> projected onto r=0.1
    assert abs(np.hypot(out[0][0], out[0][1]) - 0.1) < 1e-12
    # vertex 1: 0.004 > 0.5*0.001 -> untouched
    assert out[1][0] == 0.104


def test_bounded_faces_only_overlap_cells():
    from ice_hdm import bounded_faces
    params = [{"type": "hexa", "id": "1", "lo": (0.1, 0.1, 0.1),
               "hi": (0.2, 0.2, 0.2), "size": (0.005, 0.005, 0.005)}]
    bf = bounded_faces(params)
    # 6 bounded faces; each carries its own other-axis extent
    assert len(bf) == 6
    zf = [f for f in bf if f[0] == 2]
    assert len(zf) == 2
    # the z=0.1 face rectangle spans x/y [0.1, 0.2]
    assert np.allclose(zf[0][2], [0.1, 0.1])
    assert np.allclose(zf[0][3], [0.2, 0.2])


def test_base_phase_shifts_lattice():
    import numpy as np
    from ice_hdm import hdm_boxes_vec
    params = [{"type": "domain", "id": "0", "lo": (0.0, 0.0, 0.0),
               "hi": (0.3, 0.3, 0.3), "size": (0.01, 0.01, 1e37)}]
    b0 = hdm_boxes_vec(params, ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3)),
                       (0.1, 0.1, 0.1), max_levels=0, max_cells=100000,
                       use_object_sizes=False)
    b1 = hdm_boxes_vec(params, ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3)),
                       (0.1, 0.1, 0.1), max_levels=0, max_cells=100000,
                       use_object_sizes=False, base_phase=(0.02, 0.0, 0.0))
    x0 = np.unique(b0[:, 0])
    x1 = np.unique(b1[:, 0])
    # phase shifts the lattice anchor
    assert not np.allclose(x0, x1)
    assert np.min(x1) > np.min(x0)
    assert len(x0) == len(x1)


def test_ring_nodes_uniform():
    import numpy as np
    from ice_hdm import ring_nodes
    cyls = [{"p1": np.array([0.15, 0.25, 0.13]),
             "p2": np.array([0.15, 0.25, 0.19]), "r1": 0.02, "r2": 0.02}]
    r = ring_nodes(cyls, pitch_c=0.1, z_frac=0.5)
    assert len(r) > 100
    rho = np.hypot(r[:, 0] - 0.15, r[:, 1] - 0.25)
    assert np.allclose(rho, 0.02)          # all on the surface
    assert r[:, 2].min() >= 0.13 - 1e-12
    assert r[:, 2].max() <= 0.19 + 1e-12
    th = np.arctan2(r[:, 1] - 0.25, r[:, 0] - 0.15)
    hist, _ = np.histogram(th, bins=np.linspace(-np.pi, np.pi, 19))
    # near-uniform angular sampling: no empty bins, no huge spikes
    assert hist.min() > 0
    assert hist.max() < 3 * hist.mean()


def test_ring_stagger_binary_effect():
    import numpy as np
    from ice_hdm import ring_nodes
    cyls = [{"p1": np.array([0.15, 0.25, 0.13]),
             "p2": np.array([0.15, 0.25, 0.19]), "r1": 0.02, "r2": 0.02},
            {"p1": np.array([0.15, 0.30, 0.13]),
             "p2": np.array([0.15, 0.30, 0.19]), "r1": 0.02, "r2": 0.02}]
    r0 = ring_nodes(cyls, pitch_c=0.1, z_frac=0.5, stagger_strength=0.0)
    r1 = ring_nodes(cyls, pitch_c=0.1, z_frac=0.5, stagger_strength=1.0)
    x0 = len(np.unique(np.round(r0[:, 0], 12)))
    x1 = len(np.unique(np.round(r1[:, 0], 12)))
    # zero stagger: same-column cylinders share their x lattice (overlap);
    # full stagger: x-sets become disjoint
    assert x0 < x1
    assert x1 > x0 * 1.5
