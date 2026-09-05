# -*- coding: utf-8 -*-
"""P19-I3: sharded CI runner - coverage/grouping invariants."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import glob

import tools.run_sharded as R


TESTS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tests")


def _all_files():
    return sorted(glob.glob(os.path.join(TESTS, "test_*.py")))


def test_every_file_assigned():
    for f, shard in R.discover():
        assert shard in R.SHARDS, (f, shard)


def test_grouping_covers_all_without_orphans():
    discovered = {b[0] for b in R.discover()}      # file paths
    grouped = set()
    for files in R.assign().values():
        grouped.update(files)
    assert discovered == grouped, (sorted(discovered - grouped),
                                   sorted(grouped - discovered))
    # every file path found by the union equals the real test directory
    assert discovered == set(_all_files()), (
        sorted(set(_all_files()) - discovered),
        sorted(discovered - set(_all_files())))


def test_shard_has_multiple_files():
    for name, files in R.assign().items():
        assert len(files) >= 1, name
    assert len(R.assign()) >= 5  # we expect at least data/mesh/post/ecad/gui


def test_list_cli():
    import subprocess, sys
    r = subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(os.path.dirname(
                            os.path.abspath(__file__))), "tools",
                            "run_sharded.py"), "--list"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "test files" in r.stdout
