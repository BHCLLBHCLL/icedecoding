# -*- coding: utf-8 -*-
"""
项目聚合入口 (ANSYS Icepak).

把单个项目目录(或 .tzr 归档)内相互关联的文件聚合成一个对象:

    IcepakProject
      .model      ModelFile        - 几何对象树
      .problem    ProblemFile      - 求解设置
      .xml        dict/list        - main.ice.xml 元数据
      .grid       list[list]       - grid_params 数值行(原始 token)
      .materials  list[str]        - 解码后的 materials_from_libraries 逐行
      .post       list[dict]       - post_objects 后处理对象
      .name                           项目名(目录名/归档顶层)

同时支持从目录或内存归档加载。
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from . import model_parser, problem_parser, tzr
from .decoder import decode_file


class IcepakProject:
    _COMPONENTS = ("model", "problem", "main.ice.xml", "grid_params",
                   "materials_from_libraries", "post_objects")

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(os.path.normpath(path)) or path
        self.files = {}
        self.model = None
        self.problem = None
        self.xml = None
        self.grid = []
        self.materials = None
        self.post = []
        self._load_dir()

    # ------------------------------------------------------ 目录加载
    def _load_dir(self):
        # model / problem 用专用解析器
        mp = os.path.join(self.path, "model")
        if os.path.isfile(mp):
            self.model = model_parser.parse_file(mp)
        pp = os.path.join(self.path, "problem")
        if os.path.isfile(pp):
            self.problem = problem_parser.parse_file(pp)
        # 其余通用文件
        self._load_generic()

    def _load_generic(self, files=None):
        """files: dict[basename->bytes] 或 None(从目录读)."""
        def read(name):
            if files is not None:
                return files.get(name)
            p = os.path.join(self.path, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    return f.read()
            return None

        xb = read("main.ice.xml")
        if xb is not None:
            try:
                self.xml = parse_xml(xb)
            except Exception:
                self.xml = xb.decode("utf-8", "replace")

        gb = read("grid_params")
        if gb is not None:
            self.grid = parse_grid_params(gb.decode("latin-1", "replace"))

        mb = read("materials_from_libraries")
        if mb is not None:
            # 材料文件多为 Il!! 编码: 解码后逐行
            self.materials = decode_file_bytes(mb)

        pb = read("post_objects")
        if pb is not None:
            self.post = parse_post_objects(pb.decode("latin-1", "replace"))

    # ------------------------------------------------------ 汇总接口
    def object_types(self):
        return dict(self.model.kind_counts()) if self.model else {}

    def summary(self) -> dict:
        s = {"name": self.name, "path": self.path}
        if self.model:
            s["objects"] = self.model.count_all()
            s["object_types"] = self.object_types()
        if self.problem:
            s["setters"] = len(self.problem.setters)
            s["arrays"] = len(self.problem.arrays)
            s["time"] = self.problem.value("problem_time")
        s["grid_params_lines"] = len(self.grid)
        s["materials_lines"] = len(self.materials) if self.materials else 0
        s["post_objects"] = len(self.post)
        return s

    @classmethod
    def from_archive(cls, path_or_bytes) -> "IcepakProject":
        """从 .tzr 归档加载(路径或字节)。"""
        if isinstance(path_or_bytes, (bytes, bytearray)):
            files = tzr.unpack(bytes(path_or_bytes))
            name = ""
        else:
            files = tzr.unpack_file(path_or_bytes)
            name = os.path.basename(os.path.normpath(path_or_bytes))
        obj = cls.__new__(cls)
        obj.path = path_or_bytes
        obj.name = name or "archive"
        obj.files = files
        obj.model = None
        obj.problem = None
        obj.xml = None
        obj.grid = []
        obj.materials = None
        obj.post = []
        mp = files.get("model")
        if mp is not None:
            obj.model = model_parser.parse_text(
                "\n".join(decode_file_bytes(mp)))
        pp = files.get("problem")
        if pp is not None:
            obj.problem = problem_parser.parse_text(pp.decode("latin-1", "replace"))
        obj._load_generic(files)
        return obj

    @classmethod
    def empty(cls, name="untitled"):
        """In-memory project with an empty model (GUI New project)."""
        from .model_parser import ModelFile
        obj = cls.__new__(cls)
        obj.path = None
        obj.name = name
        obj.files = {}
        obj.model = ModelFile()
        obj.problem = None
        obj.xml = None
        obj.grid = []
        obj.materials = None
        obj.post = []
        return obj


# ---------------------------------------------------------------- 子解析

def parse_xml(data: bytes):
    """解析 main.ice.xml -> 结构化 dict{metadata:{name:value}, setup, results}."""
    root = ET.fromstring(data)
    out = {"metadata": {}, "setup": [], "results": []}
    meta = root.find("metadata")
    if meta is not None:
        for d in meta.findall("data"):
            n = d.get("name")
            v = d.get("value")
            out["metadata"][n] = v
    return out


def parse_grid_params(text: str):
    """grid_params -> 每行解析为 token 列表(数值尽量转 float/int, 无法转的保留字符串)."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        toks = line.split()
        rows.append(toks)
    return rows


def _num(s):
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def decode_file_bytes(data: bytes):
    """latin-1 解码并逐行 Il!! 解码."""
    return decode_file_from_text(data.decode("latin-1", "replace"))


def decode_file_from_text(text: str):
    from .decoder import decode_line
    return [decode_line(l) for l in text.splitlines()]


def parse_post_objects(text: str):
    """post_objects -> [ {type, params:{k:v}} ] 每行一个 post_load_object."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("post_load_object"):
            continue
        body = line[len("post_load_object"):].strip()
        # body = '{type -name x -key val ...}' -> 先剥掉最外层花括号再切分
        if body.startswith("{") and body.endswith("}"):
            body = body[1:-1]
        tokens = _lex_tcl(body)
        if not tokens:
            continue
        ptype = tokens[0]
        params = {}
        i = 1
        while i < len(tokens) - 1:
            k = tokens[i]
            if k.startswith("-"):
                params[k] = tokens[i + 1]
                i += 2
            else:
                i += 1
        out.append({"type": ptype, "params": params})
    return out


def _lex_tcl(s: str):
    i, n, out = 0, len(s), []
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "{":
            depth, j, buf = 1, i + 1, []
            while j < n and depth:
                ch = s[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                if depth > 0:
                    buf.append(ch)
                j += 1
            out.append("".join(buf).strip())
            i = j
        elif c == "}":
            i += 1
        else:
            j = i
            while j < n and s[j] not in " \t\r\n{}":
                j += 1
            out.append(s[i:j])
            i = j
    return out


if __name__ == "__main__":
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else r"D:\training\icepak\10-1transient"
    proj = IcepakProject(p)
    import json
    print(json.dumps(proj.summary(), ensure_ascii=False, indent=2, default=str))