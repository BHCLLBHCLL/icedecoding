# -*- coding: utf-8 -*-
"""P19-E1: binary grid_output full-section decode (nodes/cells/faces 32B-ish)."""
import os
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fluent_grid import decode_grid_output

GO = os.path.join("D:", os.sep, "training", "icepak", "10-1transient",
                  "grid_output")
HAS_GRID = os.path.exists(GO)


@pytest.mark.skipif(not HAS_GRID, reason="real grid_output missing")
def test_decode_real_sections():
    r = decode_grid_output(GO, 62626)
    assert r is not None
    assert r["n_nodes"] == 62626
    # cell section: 58907 stored records (oracle cas counts 58908, delta 1 -
    # a degenerate cell counted but not stored), ids consecutive, node ids valid
    assert r["n_cells"] in (58907, 58908)
    assert r["cell_ids"][0] == 62628
    assert (r["cell_ids"] == 62628 +             __import__("numpy").arange(r["n_cells"])).all()
    assert bool(((r["cells"] >= 0) & (r["cells"] < 62626)).all())
    assert list(r["cells"][0]) == [4, 5, 6, 7, 8, 9, 10, 11]
    # face section: 24B records [4 node ids][face id][zone], ids consecutive
    assert r["n_faces"] >= 10000
    assert r["face_ids"][0] == 62626 + r["n_cells"] + 2
    assert bool((r["face_ids"][1:] - r["face_ids"][:-1] == 1).all())
    assert bool(((r["faces"] >= 0) & (r["faces"] < 62626)).all())
    assert r["lead_face"] == (4, 5, 6, 7, 62627, 10)


def test_decode_synthetic_roundtrip():
    import tempfile
    import numpy as np
    # 8 nodes (28B: counter + xyz), lead face 24B, 1 cell 40B, 3 faces 24B
    n = 8
    buf = bytearray()
    buf += b"\x00" * 64
    for i in range(n):
        buf += struct.pack(">i3d", i, float(i), float(i + 1), float(i + 2))
    buf += struct.pack(">6i", 0, 1, 2, 3, n + 1, 10)          # lead face
    buf += struct.pack(">8i2i", 0, 1, 2, 3, 4, 5, 6, 7,
                       n + 2, 1)                              # one cell
    faces = [(0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5)]
    for k, f in enumerate(faces):
        buf += struct.pack(">6i", f[0], f[1], f[2], f[3],
                           n + 2 + 1 + k, 0)                  # faces
    d = tempfile.mkdtemp(prefix="g32_")
    p = os.path.join(d, "grid_output")
    open(p, "wb").write(bytes(buf))
    r = decode_grid_output(p, n)
    assert r["n_nodes"] == 8
    assert r["n_cells"] == 1
    assert list(r["cell_ids"]) == [10]
    assert list(r["cells"][0]) == [0, 1, 2, 3, 4, 5, 6, 7]
    assert r["n_faces"] == 3
    assert list(r["face_ids"]) == [11, 12, 13]
    assert list(r["faces"][0]) == [0, 1, 2, 3]
    assert r["lead_face"][4] == 9
