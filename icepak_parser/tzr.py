# -*- coding: utf-8 -*-
"""
.tzr 归档解包 (ANSYS Icepak 项目打包文件).

格式: gzip(魔数 1F 8B) + tar 双层封装.
归档内成员为项目文件(model/problem/main.ice.xml/materials_from_libraries...),
成员路径带一个顶层项目目录前缀(如 avonics/model).
"""

from __future__ import annotations

import gzip
import io
import os
import tarfile


def is_tzr(data: bytes) -> bool:
    """判断字节流是否为 .tzr(gzip 魔数 1F 8B)."""
    return data[:2] == b"\x1f\x8b"


def list_members(data: bytes):
    """返回归档内的成员名列表."""
    with tarfile.open(fileobj=io.BytesIO(_decompress(data)), mode="r:*") as t:
        return t.getnames()


def unpack(data: bytes) -> dict:
    """解包归档, 返回 {basename: bytes}. 仅返回文件(忽略目录).
    若归档内文件本就在顶层目录下, basename 取最后一段, 避免项目前缀噪声."""
    out = {}
    with tarfile.open(fileobj=io.BytesIO(_decompress(data)), mode="r:*") as t:
        for m in t:
            if not m.isfile():
                continue
            name = m.name.replace("\\", "/")
            base = name.rsplit("/", 1)[-1] if "/" in name else name
            out[base] = t.extractfile(m).read()
    return out


def unpack_file(path: str) -> dict:
    """从文件路径读取并解包."""
    with open(path, "rb") as f:
        return unpack(f.read())


def pack(files: dict, prefix="project") -> bytes:
    """打包 {basename: bytes} 为 .tzr (gzip + tar, 成员路径 prefix/name)."""
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for name, raw in files.items():
            if raw is None:
                continue
            if isinstance(raw, str):
                raw = raw.encode("latin-1", "replace")
            else:
                raw = bytes(raw)
            base = str(name).replace("\\", "/").rsplit("/", 1)[-1]
            if not base:
                continue
            info = tarfile.TarInfo("%s/%s" % (prefix, base))
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    return gzip.compress(tar_buf.getvalue())


def pack_file(path: str, files: dict, prefix=None):
    """写出 .tzr 文件. prefix 默认取目标文件名去扩展名."""
    if prefix is None:
        prefix = os.path.splitext(os.path.basename(path))[0] or "project"
    data = pack(files, prefix)
    with open(path, "wb") as f:
        f.write(data)
    return path


def pack_directory(dirpath: str, dest=None) -> bytes:
    """把工程目录内的普通文件打成 .tzr 字节; dest 若给出则同时写文件."""
    name = os.path.basename(os.path.normpath(dirpath)) or "project"
    files = {}
    for fn in os.listdir(dirpath):
        if fn.startswith("."):
            continue
        fp = os.path.join(dirpath, fn)
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                files[fn] = f.read()
    data = pack(files, name)
    if dest:
        with open(dest, "wb") as f:
            f.write(data)
    return data


def _decompress(data: bytes) -> bytes:
    try:
        return gzip.decompress(data)
    except OSError as e:
        raise ValueError("非有效 gzip 数据") from e


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        d = unpack_file(p)
        print("=== %s (%d files) ===" % (p, len(d)))
        for n, raw in d.items():
            print("  %-30s %8d bytes" % (n, len(raw)))