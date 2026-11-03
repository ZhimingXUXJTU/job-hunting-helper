"""受限 YAML 读取器（零依赖）。

只支持本工作区两份配置文件用到的语法：
- 两空格缩进的嵌套映射
- ``key: value`` 标量（null / bool / int / float / 带引号或不带引号的字符串）
- ``- item`` 标量列表与 ``- key: value`` 起头的映射列表
- 行内数组 ``[a, b, c]``
- ``#`` 注释与空行

不支持锚点、多行字符串、流式映射等其他语法。文件格式超出范围时
抛 ``YamlLiteError``，而不是给出悄悄错误的结果。
"""

from __future__ import annotations

import re
from typing import Any


class YamlLiteError(ValueError):
    pass


_SCALAR_RE = re.compile(r"^(null|true|false|~)$", re.IGNORECASE)
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def _strip_comment(line: str) -> str:
    # 只剥同行注释：引号外第一个 " #"
    out, in_s, in_d = [], False, False
    for ch in line:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "":
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if _SCALAR_RE.match(s):
        low = s.lower()
        if low in ("null", "~"):
            return None
        return low == "true"
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _parse_inline_list(raw: str) -> list[Any]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [_parse_scalar(part) for part in inner.split(",")]


def parse(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for no, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw.rstrip("\n"))
        if not line.strip():
            continue
        if line.strip() == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise YamlLiteError(f"line {no}: 缩进必须是 2 的倍数: {raw!r}")
        lines.append((indent, line.strip()))

    def build(pos: int, indent: int) -> tuple[Any, int]:
        # 列表块
        def _is_list_item(i: int) -> bool:
            return (
                i < len(lines)
                and lines[i][0] == indent
                and (lines[i][1] == "-" or lines[i][1].startswith("- "))
            )

        if _is_list_item(pos):
            items: list[Any] = []
            while _is_list_item(pos):
                item = lines[pos][1][1:].strip()
                if not item:
                    pos += 1
                    continue
                if ":" in item and not item.startswith(("[", "'", '"')):
                    # 映射列表项：把 "- key: v" 归一成 "key: v" 后按映射解析
                    key, _, rest = item.partition(":")
                    items.append({key.strip(): _parse_scalar(rest)})
                    pos += 1
                    # 同一列表项的后续字段（更深缩进）
                    if pos < len(lines) and lines[pos][0] > indent:
                        sub, pos = build(pos, lines[pos][0])
                        if isinstance(sub, dict) and isinstance(items[-1], dict):
                            items[-1].update(sub)
                else:
                    items.append(_parse_scalar(item))
                    pos += 1
            return items, pos

        mapping: dict[str, Any] = {}
        while pos < len(lines) and lines[pos][0] == indent:
            _, content = lines[pos]
            if content.startswith("- "):
                break
            key, sep, rest = content.partition(":")
            if not sep:
                raise YamlLiteError(f"line: 期望 'key: value'，得到 {content!r}")
            k = key.strip()
            v = rest.strip()
            if v == "":
                # 值在更深缩进，或值为 null
                if pos + 1 < len(lines) and lines[pos + 1][0] > indent:
                    mapping[k], pos = build(pos + 1, lines[pos + 1][0])
                else:
                    mapping[k] = None
                    pos += 1
            elif v.startswith("["):
                mapping[k] = _parse_inline_list(v)
                pos += 1
            else:
                mapping[k] = _parse_scalar(v)
                pos += 1
        return mapping, pos

    if not lines:
        return {}
    result, _ = build(0, lines[0][0])
    return result


def load_file(path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return parse(fh.read())
