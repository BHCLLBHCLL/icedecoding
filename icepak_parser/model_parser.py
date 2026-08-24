# -*- coding: utf-8 -*-
"""
model 文件解析 (ANSYS Icepak).

model 明文语法(解码后):
    #@ header comment...
    object <type> <name>
        <attr> <value...>          # key + 空白分隔的值(可含 {..} 花括号组)
        shape <shape_name> <shape_type>
            setval <key> {<val..>} <key> {<val..>} ...
        end shape
        ...
    end object

支持嵌套 object(assembly)与多个 shape, 单行注释 # 跳过.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .decoder import decode_file


@dataclass
class Shape:
    name: str
    type: str
    setvals: dict = field(default_factory=dict)  # key -> list[str]
    line: int = 0


@dataclass
class ModelObject:
    kind: str
    name: str
    properties: dict = field(default_factory=dict)  # key -> list[str]
    shape: "Shape | None" = None
    children: list = field(default_factory=list)  # 嵌套 object
    line: int = 0


@dataclass
class ModelFile:
    header: str = ""
    objects: list = field(default_factory=list)

    def object_by_name(self, name: str, _roots=None):
        _roots = self.objects if _roots is None else _roots
        for o in _roots:
            if o.name == name:
                return o
            if o.children:
                hit = self.object_by_name(name, o.children)
                if hit is not None:
                    return hit
        return None

    def _all_objects(self, _roots=None):
        _roots = self.objects if _roots is None else _roots
        for o in _roots:
            yield o
            if o.children:
                yield from self._all_objects(o.children)

    def kind_counts(self):
        from collections import Counter
        return Counter(o.kind for o in self._all_objects())

    def count_all(self) -> int:
        return sum(1 for _ in self._all_objects())


# ---------------------------------------------------------------- helpers

_TOKEN_RE = re.compile(r"\S+")


def _tokenize_groups(s: str):
    """返回 [(is_braced, tokens_list), ...] 依序. token 为字符串列表."""
    i, n, res = 0, len(s), []
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] == "{":
            j = s.find("}", i)
            if j < 0:
                j = n
            res.append((True, s[i + 1:j].split()))
            i = j + 1
        else:
            m = _TOKEN_RE.match(s, i)
            res.append((False, [m.group(0)]))
            i = m.end()
    return res


def _parse_setval_line(line: str) -> dict:
    """解析 'setval key {..} key {..}[ key scalar]' -> {key: [tokens]}."""
    groups = _tokenize_groups(line)
    d = {}
    k = 0
    while k + 1 < len(groups):
        _braced, key_tok = groups[k]
        if not key_tok:
            break
        key = key_tok[0]
        _br, val_tokens = groups[k + 1]
        d[key] = val_tokens
        k += 2
    return d


def _parse_attr_line(line: str):
    """解析对象级属性行 -> (key, values_list). 返回 None 若为纯 key."""
    groups = _tokenize_groups(line)
    if not groups:
        return None
    key = groups[0][1][0]
    vals = []
    for _br, toks in groups[1:]:
        vals.extend(toks)
    return key, vals


# ---------------------------------------------------------------- parser


def _read_lines(text: str):
    lines = text.split("\n")
    return [l.rstrip("\r") for l in lines]


def parse_text(text: str) -> ModelFile:
    """从解码后的明文解析 model 文件."""
    mf = ModelFile()
    lines = _read_lines(text)
    i = 0
    n = len(lines)

    # 头部注释/空行
    while i < n:
        l = lines[i].strip()
        if not l:
            i += 1
            continue
        if l.startswith("#"):
            if not mf.header:
                mf.header = l
            i += 1
            continue
        break

    while i < n:
        l = lines[i].strip()
        if not l:
            i += 1
            continue
        if l.startswith("object"):
            obj, i = _parse_object(lines, i)
            mf.objects.append(obj)
        else:  # 遇到未知顶层行, 跳过
            i += 1
    return mf


def _parse_object(lines: list, i: int):
    """从 'object ...' 行开始解析, 返回 (ModelObject, next_index)."""
    head = lines[i].strip()
    parts = head.split()
    otype = parts[1] if len(parts) > 1 else ""
    oname = " ".join(parts[2:]) if len(parts) > 2 else ""
    obj = ModelObject(kind=otype, name=oname, line=i + 1)
    i += 1
    n = len(lines)
    while i < n:
        raw = lines[i]
        l = raw.strip()
        i += 1
        if not l or l.startswith("#"):
            continue
        if l == "end object":
            break
        if l.startswith("end shape"):
            obj.shape = None  # 关闭当前 shape(嵌套时此处会出错, 见下)
            continue
        if l.startswith("shape "):
            sp = l.split(maxsplit=2)
            if len(sp) >= 3 and sp[1] != "setval":
                shape = Shape(name=sp[1], type=sp[2], line=0)
            else:
                # shape name 内可能带空格, 按 setval 风格取前缀
                shape = Shape(name=sp[1] if len(sp) > 1 else "", type=sp[2] if len(sp) > 2 else "", line=0)
            shape.line = i
            # 解析 shape 块内 setval
            while i < n:
                sl = lines[i].strip()
                if sl == "end shape":
                    i += 1
                    break
                if sl.startswith("setval"):
                    shape.setvals.update(_parse_setval_line(sl[6:].strip()))
                i += 1
            # 一个对象可能多次出现 shape(后出现者覆盖)
            if obj.shape is None or True:
                obj.shape = shape
            continue
        if l.startswith("object "):
            sub, i = _parse_object(lines, i - 1)
            obj.children.append(sub)
            continue
        if l.startswith("setval"):
            # 对象级 setval(少见), 并入 shape
            if obj.shape is None:
                obj.shape = Shape(name="", type="")
            obj.shape.setvals.update(_parse_setval_line(l[6:].strip()))
            continue
        # 普通属性行
        kv = _parse_attr_line(l)
        if kv is not None:
            obj.properties.setdefault(kv[0], []).extend(kv[1])
    return obj, i


def parse_file(path: str) -> ModelFile:
    """读取原始 model(可能含 Il!! 编码)并解析."""
    return parse_text("\n".join(decode_file(path)))


if __name__ == "__main__":
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else r"D:\training\icepak\10-1transient\model"
    mf = parse_file(p)
    print("header:", mf.header)
    print("object types:", dict(mf.kind_counts()))
    for o in mf.objects:
        shp = o.shape
        sv = shp.setvals if shp else {}
        print("\n[%s] %s  shape=%s setvals=%s" % (o.kind, o.name, shp.type if shp else None, list(sv.keys())))
        print("    props:", {k: v for k, v in list(o.properties.items())[:8]})