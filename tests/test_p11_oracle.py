# -*- coding: utf-8 -*-
"""P11 oracle infrastructure tests: ASCII grid parser roundtrip, binary
analyzer smoke (synthetic BE record), overview parser."""
import os
import struct
import tempfile

import pytest

from fluent_grid import parse_ascii_grid, analyze_binary, grid_counts
from ice_mesh import generate_mesh, write_grid_output_ascii
pytestmark = []  # pure logic, no GUI needed


def _synthetic_binary():
    """BE header + one marker record (grid 3 nodes of evidence)."""
    parts = [struct.pack(">iiii", 4, 1, 2, 0)]
    desc = b"X" * 56  # keep the marker 4-byte aligned
    parts.append(struct.pack(">i", len(desc)))
    parts.append(desc)
    node = struct.pack(">iiddd", 0x6BAF1C32, 0, 0.1, 0.2, 0.3)
    parts.append(node)
    return b"".join(parts)


def test_ascii_parser_headers():
    text = "(10 (2 3 0 0))\n(10 (0 1 1331 0))\n(12 (0 1 1000 0))\n"
    out = parse_ascii_grid(text)
    # Icepak cas zone counts are HEX (1331 -> 0x1331 = 4913)
    assert out["nodes"] == 0x1331
    assert out["cells"] == 0x1000


def test_our_writer_roundtrip_counts():
    from icepak_parser.project import IcepakProject
    from ice_create import default_cabinet
    proj = IcepakProject.empty("t")
    proj.model.objects.append(default_cabinet())
    result = generate_mesh(proj.model, counts=(6, 5, 4))
    d = tempfile.mkdtemp(prefix="ice_g_")
    path = os.path.join(d, "grid_output")
    write_grid_output_ascii(path, result)
    out = parse_ascii_grid(open(path, encoding="latin-1").read())
    assert out["nodes"] == result.node_count
    assert out["cells"] == result.cell_count
    assert out["cells"] == 120


def test_analyzer_synthetic():
    diag = analyze_binary(_synthetic_binary())
    assert diag["size"] > 0
    assert diag["record_hypothesis"]["offset"] >= 0


def test_grid_counts_ascii_file():
    d = tempfile.mkdtemp(prefix="ice_gc_")
    path = os.path.join(d, "grid_output")
    open(path, "w", encoding="latin-1").write(
        "(10 (0 1 55 0))\n(12 (0 1 48 0))\n")
    counts, diag = grid_counts(path)
    assert counts["nodes"] == 0x55 and counts["cells"] == 0x48
