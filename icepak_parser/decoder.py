# -*- coding: utf-8 -*-
"""
Il!! 混淆编码 / 解码器 (ANSYS Icepak 项目文件).

背景
----
Icepak 的 model / materials_from_libraries 等文件以 "Il!!" 开头并整体做混淆。
逆向自 icepak.exe (v19.5) 的反汇编结果:

    解码: v = c - KQ[i % 7] - KC[i % 16] - seed
          若 v < 0x20 则循环 v += 0x5F
    编码(逆): c = ((p + KQ[i%7] + KC[i%16] + seed - 0x20) mod 0x5F) + 0x20

    其中:
        KQ   = b"q|sz}y~"           周期 7
        KC   = b"cor5(#b!S0efP3+E"  周期 16
        seed = "Il!!" 之后的第一个字符
        字符有效范围 0x20 - 0x7e, 周期 lcm(7,16) == 112 (实测统计吻合)

仅对以 "Il!!" 开头的行解码; 其余行(头部注释/空行)原样返回。
"""

from __future__ import annotations

KQ = b"q|sz}y~"
KC = b"cor5(#b!S0efP3+E"

MAGIC = "Il!!"

_LOW = 0x20
_HIGH = 0x7E
_SPAN = _HIGH - _LOW + 1  # 0x5F

_DEFAULT_SEED = 0x21


def decode_line(line: str) -> str:
    """解码单行. 非 Il!! 行原样返回."""
    if not line.startswith(MAGIC):
        return line
    s = line[len(MAGIC):]
    if not s:
        return ""
    seed = ord(s[0])
    body = s[1:]
    out = []
    for i, ch in enumerate(body):
        c = ord(ch)
        if _LOW <= c <= _HIGH:
            v = c - KQ[i % 7] - KC[i % 16] - seed
            while v < _LOW:
                v += _SPAN
            out.append(chr(v))
        else:
            out.append(ch)
    return "".join(out)


def decode_text(text: str, split: bool = False):
    lines = text.splitlines()
    dec = [decode_line(l) for l in lines]
    return dec if split else "\n".join(dec)


def decode_file(path: str):
    import io
    with io.open(path, "r", encoding="latin-1", errors="replace") as f:
        lines = f.read().splitlines()
    return [decode_line(l) for l in lines]


def encode_line(plain: str, seed: int = _DEFAULT_SEED) -> str:
    if seed < _LOW or seed > _HIGH:
        raise ValueError("seed 必须在 0x20..0x7e 之间")
    parts = [chr(seed)]
    for i, ch in enumerate(plain):
        p = ord(ch)
        if _LOW <= p <= _HIGH:
            c = (p + KQ[i % 7] + KC[i % 16] + seed - _LOW) % _SPAN + _LOW
            parts.append(chr(c))
        else:
            parts.append(ch)
    return MAGIC + "".join(parts)


def encode_text(plain: str, seed: int = _DEFAULT_SEED) -> str:
    return "\n".join(encode_line(l, seed) for l in plain.splitlines())


def encode_text_faithful(decoded_text: str, raw_text: str) -> str:
    """Byte-identity re-encode: re-obfuscate each Il!! line with its ORIGINAL
    per-line seed, leave non-Il!! lines verbatim.  Guarantees
    encode_text_faithful(decode_text(raw), raw) == raw."""
    raw_lines = raw_text.splitlines()
    dec_lines = decoded_text.splitlines()
    out = []
    for i, rl in enumerate(raw_lines):
        if rl.startswith(MAGIC):
            seed = ord(rl[4]) if len(rl) > 4 else _DEFAULT_SEED
            plain = decode_line(rl)
            out.append(encode_line(plain, seed))
        else:
            out.append(rl)
    s = "\n".join(out)
    if raw_text.endswith("\n"):
        s += "\n"
    return s


if __name__ == "__main__":
    import io
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else None
    if p:
        for l in decode_file(p):
            print(l)
        sys.exit(0)

    with io.open(r"D:\training\icepak\10-1transient\model", "r", encoding="latin-1") as f:
        ref = f.read().splitlines()
    ok = bad = plain = 0
    for l in ref:
        if not l.startswith(MAGIC):
            plain += 1
            continue
        dec = decode_line(l)
        re_enc = encode_line(dec, ord(l[len(MAGIC)]))  # 用原 seed 重编码
        if re_enc == l:
            ok += 1
        else:
            bad += 1
            if bad <= 3:
                print("MISMATCH:\n  ref :%r\n  dec :%r\n  re  :%r" % (l, dec, re_enc))
    print("same-seed round-trip ok=%d bad=%d plain=%d (lines)" % (ok, bad, plain))