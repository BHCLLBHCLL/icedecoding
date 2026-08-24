# -*- coding: utf-8 -*-
"""In-memory object factory / model serialize tests (no GUI)."""

from ice_create import (
    default_cabinet, default_object, next_object_name, project_files_for_pack,
    remove_object, serialize_model,
)
from icepak_parser.model_parser import ModelFile, parse_text
from icepak_parser.project import IcepakProject
from icepak_parser import tzr


def test_empty_project_and_cabinet():
    proj = IcepakProject.empty("untitled")
    assert proj.model is not None
    assert proj.model.count_all() == 0
    proj.model.objects.append(default_cabinet())
    cab = proj.model.object_by_name("cabinet")
    assert cab is not None
    assert cab.kind == "domain"
    assert cab.shape.type == "shape_hexa"
    p1 = [float(x) for x in cab.shape.setvals["point1"]]
    p2 = [float(x) for x in cab.shape.setvals["point2"]]
    assert p1 == [0.0, 0.0, 0.0]
    assert p2 == [0.5, 0.4, 0.3]


def test_default_shapes_and_names():
    model = ModelFile()
    model.objects.append(default_cabinet())
    blk = default_object("block", next_object_name(model, "block"), index=1)
    fan = default_object("fan", next_object_name(model, "fan"), index=1)
    plate = default_object("plate", next_object_name(model, "plate"), index=1)
    mat = default_object("material", next_object_name(model, "material"))
    model.objects.extend([blk, fan, plate, mat])
    assert blk.shape.type == "shape_hexa"
    assert fan.shape.type == "shape_cyl"
    assert plate.shape.type == "shape_quad"
    assert mat.shape is None
    assert next_object_name(model, "block") == "block.2"


def test_remove_nested_and_serialize_roundtrip():
    model = ModelFile()
    cab = default_cabinet()
    blk = default_object("block", "block.1")
    inner = default_object("plate", "plate.1")
    blk.children.append(inner)
    model.objects = [cab, blk]
    assert remove_object(model, "plate.1")
    assert model.object_by_name("plate.1") is None
    assert model.object_by_name("block.1") is not None
    text = serialize_model(model)
    back = parse_text(text)
    assert back.object_by_name("cabinet") is not None
    assert back.object_by_name("block.1") is not None
    assert back.object_by_name("block.1").shape.type == "shape_hexa"


def test_pack_in_memory_project():
    proj = IcepakProject.empty("job")
    proj.model.objects.append(default_cabinet())
    files = project_files_for_pack(proj)
    assert "model" in files
    blob = tzr.pack(files, prefix="job")
    loaded = IcepakProject.from_archive(blob)
    assert loaded.model is not None
    assert loaded.model.object_by_name("cabinet") is not None
    assert loaded.model.object_by_name("cabinet").kind == "domain"
