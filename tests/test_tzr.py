# -*- coding: utf-8 -*-
"""Round-trip tests for .tzr gzip+tar pack/unpack."""

import os

from icepak_parser import tzr


def test_pack_unpack_roundtrip():
    files = {
        "model": b"#@ model\nobject block block.1\nend object\n",
        "problem": b"set problem_time steady\n",
        "main.ice.xml": b"<icepak/>",
    }
    blob = tzr.pack(files, prefix="demo")
    assert tzr.is_tzr(blob)
    names = tzr.list_members(blob)
    assert any(n.endswith("model") for n in names)
    out = tzr.unpack(blob)
    assert out["model"] == files["model"]
    assert out["problem"] == files["problem"]
    assert out["main.ice.xml"] == files["main.ice.xml"]


def test_pack_file_and_directory():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "job1")
        os.mkdir(d)
        with open(os.path.join(d, "model"), "wb") as f:
            f.write(b"Il!!xabc")
        with open(os.path.join(d, "problem"), "wb") as f:
            f.write(b"set x 1\n")
        dest = os.path.join(tmp, "job1.tzr")
        tzr.pack_directory(d, dest=dest)
        assert os.path.isfile(dest)
        out = tzr.unpack_file(dest)
        assert out["model"] == b"Il!!xabc"
        assert out["problem"] == b"set x 1\n"
