# -*- coding: utf-8 -*-
"""Regression: resolve_slot Create-family branch (was dead: cmd matched
against kind-name set, never the label) + NyiHandler gui binding."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ice_actions import resolve_slot, _create_kind, NyiHandler

CREATE_LABELS = [
    "Create blocks", "Create blowers", "Create enclosures", "Create fans",
    "Create heat exchangers", "Create heat sinks", "Create materials",
    "Create networks", "Create openings", "Create packages",
    "Create assemblies", "Create printed circuit boards",
    "Create periodic boundaries", "Create plates", "Create resistances",
    "Create sources", "Create grille", "Create walls"]


class _StubGui(object):
    def __init__(self):
        self.created = []

    def _create_object(self, kind):
        self.created.append(kind)
        return kind


class _NyiSpyGui(object):
    def __init__(self):
        self.warncmd = None

    def _nyi(self, name):
        self.warncmd = name


def test_create_labels_resolve_to_create_object():
    gui = _StubGui()
    for label in CREATE_LABELS:
        fn = resolve_slot(gui, label)
        assert callable(fn), label
        fn()
    kinds = [_create_kind(l) for l in CREATE_LABELS]
    assert gui.created == kinds
    assert len(set(kinds)) == len(kinds)  # no collapsed duplicates


def test_unknown_label_falls_back_to_bound_nyi():
    gui = _NyiSpyGui()
    fn = resolve_slot(gui, "Definitely not a command")
    assert isinstance(fn, NyiHandler)
    fn()
    assert gui.warncmd == "Definitely not a command"
