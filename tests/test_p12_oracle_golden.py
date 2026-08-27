# -*- coding: utf-8 -*-
"""P12: real-oracle golden counts (cross-validated cas/nodemap) + hex zones."""
import os
import pytest

from fluent_grid import parse_ascii_grid, _num

ICEPAK_ROOT = r"D:\training\icepak"
CAS = os.path.join(ICEPAK_ROOT, "10-1transient", "transient00.cas")
NODEMAP = os.path.join(ICEPAK_ROOT, "10-1transient", "transient00.nodemap")


def test_hex_zone_counts():
    text = '(10 (0 1 f4a2 1))\n(12 (0 1 e61c 0))\n'
    out = parse_ascii_grid(text)
    assert out["nodes"] == 62626
    assert out["cells"] == 58908


def test_hex_num():
    assert _num("f4a2") == 62626
    assert _num("1331") == 1331


@pytest.mark.skipif(not os.path.exists(CAS), reason="oracle cas missing")
def test_oracle_golden_cas():
    text = open(CAS, encoding="latin-1", errors="ignore").read()
    out = parse_ascii_grid(text)
    assert out["nodes"] == 62626, out
    assert out["cells"] == 58908, out


@pytest.mark.skipif(not os.path.exists(NODEMAP), reason="oracle nodemap missing")
def test_oracle_golden_nodemap():
    raw = open(NODEMAP, "rb").read()
    lines = raw.count(b"\r\n") + (0 if raw.endswith(b"\r\n") else 1)
    assert lines == 62626
