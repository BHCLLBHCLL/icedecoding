# -*- coding: utf-8 -*-
"""
problem 文件解析 (ANSYS Icepak).

problem 为明文 Tcl 风格:
    set name value
    array set name { key value  key value ... }

value 可为标量、花括号组(可跨行, 如 array set 的大块)。本模块解析出:
    ProblemFile.setters: dict[name -> str(原始值)]
    ProblemFile.arrays : dict[array_name -> {key: value}]
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProblemFile:
    raw: str = ""
    setters: dict = field(default_factory=dict)
    arrays: dict = field(default_factory=dict)

    # ---------------------------------------------------- 便捷访问
    def value(self, name: str, default=None):
        return self.setters.get(name, default)

    def int_value(self, name: str, default=None):
        v = self.setters.get(name)
        if v is None:
            return default
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return default

    def float_value(self, name: str, default=None):
        v = self.setters.get(name)
        if v is None:
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def array(self, name: str, default=None):
        return self.arrays.get(name, default if default is not None else {})

    # ---------------------------------------------------- E2: structured tables
    def table(self, name: str):
        """Array value entries with multi-token values split into token lists.
        {'key': ['tok', ...]}"""
        return {k: v.split() for k, v in self.array(name).items()}

    def trials(self):
        """Optimization trials: {trial_id: {'name', 'vars': {param: value}}}
        per-trial variables from expression_param_random (9-2Optimization)."""
        names = self.array("expression_trial_name", {})
        rnd_tbl = self.table("expression_param_random")
        out = {}
        for t in sorted(self.array("expression_param_trials", {})):
            toks = rnd_tbl.get(t, [])
            vars_ = {}
            for k in range(0, len(toks) - 1, 2):
                vars_[toks[k]] = toks[k + 1]
            out[t] = {"name": names.get(t, t), "vars": vars_}
        return out

    def design_params(self):
        """Design parameters: {param: {'value', 'range', 'choice'}} from the
        expression_params / expression_param_range / expression_param_choices
        arrays."""
        vals = self.array("expression_params", {})
        rng = self.array("expression_param_range", {})
        chc = self.array("expression_param_choices", {})
        out = {}
        for k in sorted(set(vals) | set(rng) | set(chc)):
            out[k] = {"value": vals.get(k),
                      "range": (rng.get(k) or "").split(),
                      "choice": chc.get(k)}
        return out

    def transient_tables(self):
        """Transient parameter tables: arrays whose name mentions trans/ambient."""
        return {k: v for k, v in self.arrays.items()
                if "trans" in k or "ambient" in k}


# ---------------------------------------------------------------- 词法

def _lex(s: str):
    """把 Tcl 语句拆成 value 序列。花括号组折叠为单个 token(取内侧文本)。"""
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


def _gather(lines: list, i: int):
    """从 i 行开始累积一个逻辑语句(花括号平衡)直至闭合。返回 (语句文本, 下一行索引)。"""
    depth = 0
    buf = []
    while i < len(lines):
        line = lines[i]
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        buf.append(line)
        i += 1
        if depth <= 0:
            break
    return "\n".join(buf), i


def _pairs(tokens: list) -> dict:
    """把 [k,v,k,v,...] 序列转为 dict。忽略尾巴不成对的 key。"""
    d = {}
    k = 0
    while k + 1 < len(tokens):
        key = tokens[k]
        d[key] = tokens[k + 1]
        k += 2
    return d


# ---------------------------------------------------------------- 主入口

def parse_text(text: str) -> ProblemFile:
    pf = ProblemFile(raw=text)
    lines = text.split("\n")
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        stmt, i = _gather(lines, i)
        stmt = stmt.strip()
        head, _, rest = stmt.partition("\n")
        head_flat = " ".join(head.split())

        if head_flat.startswith("array set "):
            toks = _lex(stmt)
            # toks: ['array','set', name, {k v ...}]
            if len(toks) >= 4:
                pf.arrays[toks[2]] = _pairs(_lex(toks[3]))
            else:
                name = head_flat.split()[2] if len(head_flat.split()) > 2 else ""
                rest_full = "\n".join(x.strip() for x in stmt.split("\n")[0:]) 
                # 兜底: 直接取整行, 尽量 match name
                inner = stmt[stmt.find("{"):]
                if inner:
                    pf.arrays[name] = _pairs(_lex(inner))
        elif head_flat.startswith("set "):
            toks = _lex(stmt)
            if len(toks) >= 2:
                pf.setters[toks[1]] = " ".join(toks[2:])
    return pf


def parse(text: str) -> ProblemFile:
    return parse_text(text)


def parse_file(path: str) -> ProblemFile:
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        return parse_text(f.read())


if __name__ == "__main__":
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else r"D:\training\icepak\10-1transient\problem"
    pf = parse_file(p)
    print("setters=%d arrays=%d" % (len(pf.setters), len(pf.arrays)))
    for k in list(pf.setters)[:10]:
        print("  set %s = %r" % (k, pf.setters[k]))
    for name, d in list(pf.arrays.items())[:3]:
        print("  array %s: %d entries" % (name, len(d)))
        for k, v in list(d.items())[:5]:
            print("      %s = %r" % (k, v))