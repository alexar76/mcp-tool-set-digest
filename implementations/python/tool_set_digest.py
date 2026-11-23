"""Reference implementation of mcp-tool-set-digest/1 (SPEC.md). Python 3.9+, standard library only.

    from tool_set_digest import digests
    contract, extras = digests(json_text_of_the_tools_array)      # extras is None when no tool has any

``python3 tool_set_digest.py < tools.json`` prints both digests of a ``tools`` array (or of a whole
``tools/list`` result). ``python3 tool_set_digest.py --vectors ../../vectors/vectors.json`` checks
every published vector and exits non-zero on the first that differs.

Licence: Apache-2.0 OR MIT.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import sys
from typing import Any

CONTRACT_MEMBERS = ("name", "description", "inputSchema", "outputSchema")
MAX_SAFE_INTEGER = 2**53 - 1
MAX_LEVEL = 512                 # section 12: the tools array is level 1, a tool level 2
WRAPPER_LEVELS = 2              # a JSON-RPC response and its result can wrap the tools array


class DigestError(Exception):
    """A tool set the specification gives no digest (SPEC.md section 9)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


# --- parsing (section 3) ------------------------------------------------------------------------

# A string token (so brackets inside strings are skipped) or a bracket.
_TOKEN = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[\[\]{}]', re.S)
_CLOSER = {"[": "]", "{": "}"}


def cut_deep(text: str, limit: int = MAX_LEVEL + WRAPPER_LEVELS) -> str:
    """The text with every array or object nested deeper than ``limit`` (counting the outermost
    value as 1) replaced by an empty one of the same kind.

    Nothing deeper than level 512 can reach a digest (section 12: a digest that would cover it
    gives TSD-DEPTH), and a replaced container keeps its kind and its level, so every answer stays
    what it would have been. The replacement keeps the parser out of deep recursion; JSON text with
    mismatched brackets is refused here, as the parser would refuse it.
    """
    depth = 0
    pieces: list[str] = []
    last = 0
    tokens = _TOKEN.finditer(text)
    for token in tokens:
        mark = token.group()
        if mark[0] == '"':
            continue
        if mark in _CLOSER:
            depth += 1
            if depth <= limit:
                continue
            start, closers = token.start(), [_CLOSER[mark]]
            for inner in tokens:
                found = inner.group()
                if found[0] == '"':
                    continue
                if found in _CLOSER:
                    closers.append(_CLOSER[found])
                elif closers.pop() != found:
                    raise json.JSONDecodeError("brackets do not match", text, inner.start())
                if not closers:
                    break
            else:
                raise json.JSONDecodeError("a nested value is not closed", text, start)
            pieces += [text[last:start], "[]" if mark == "[" else "{}"]
            last = inner.end()
            depth -= 1
        else:
            depth -= 1
    return text if not pieces else "".join(pieces) + text[last:]


def parse(text: str) -> Any:
    """JSON text to values, every number an IEEE 754 double or an exact integer inside 2^53.

    A literal too large for a double (``1e400``) parses to infinity and is refused when a digest
    that covers it is computed, not here: the contract digest of a set does not depend on what a
    member outside the contract holds. Arrays and objects deeper than any digest can cover are
    read as empty (``cut_deep``).
    """
    def number(literal: str) -> Any:
        if "." not in literal and "e" not in literal and "E" not in literal:
            value = int(literal)
            if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
                return value
        return float(literal)               # correctly rounded: nearest double, ties to even

    return json.loads(cut_deep(text), parse_float=number, parse_int=number)


# --- canonical form (section 6): RFC 8785 ---------------------------------------------------------

def utf16_key(text: str) -> bytes:
    """Sort key for RFC 8785 section 3.2.3: UTF-16 code units compared as unsigned integers."""
    return text.encode("utf-16-be", "surrogatepass")


def es_number(value: float) -> str:
    """ECMAScript Number::toString, the form RFC 8785 section 3.2.2.3 prescribes."""
    if value == 0:
        return "0"                          # -0 too
    sign = "-" if value < 0 else ""
    mantissa, _, exp = repr(abs(value)).partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = whole + frac
    lead = len(digits) - len(digits.lstrip("0"))
    s = digits.strip("0")
    k = len(s)
    n = len(whole) + (int(exp) if exp else 0) - lead     # value = 0.s x 10^n
    if k <= n <= 21:
        return sign + s + "0" * (n - k)
    if 0 < n <= 21:
        return sign + s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * -n + s
    e = n - 1
    return sign + (s if k == 1 else s[0] + "." + s[1:]) + "e" + ("+" if e >= 0 else "-") + str(abs(e))


def _string(text: str) -> str:
    for index, ch in enumerate(text):
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            # str holds code points, so any surrogate here is a lone one.
            raise DigestError("TSD-TEXT", f"lone surrogate U+{code:04X} at index {index}")
    return json.dumps(text, ensure_ascii=False)


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value) if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER else es_number(float(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DigestError("TSD-NUMBER", "a number with no IEEE 754 double")
        return es_number(value)
    if isinstance(value, str):
        return _string(value)
    raise TypeError(f"{type(value).__name__} is not a JSON value")


def canonical(value: Any) -> str:
    """RFC 8785 text of a value, written with an explicit stack so that depth costs no recursion."""
    out: list[str] = []
    stack: list[tuple[bool, Any]] = [(False, value)]     # (is literal text, item)
    while stack:
        literal, item = stack.pop()
        if literal:
            out.append(item)
        elif isinstance(item, list):
            out.append("[")
            stack.append((True, "]"))
            for index in range(len(item) - 1, -1, -1):
                stack.append((False, item[index]))
                if index:
                    stack.append((True, ","))
        elif isinstance(item, dict):
            out.append("{")
            stack.append((True, "}"))
            keys = sorted(item, key=utf16_key)
            for index in range(len(keys) - 1, -1, -1):
                stack.append((False, item[keys[index]]))
                stack.append((True, _string(keys[index]) + ":"))
                if index:
                    stack.append((True, ","))
        else:
            out.append(_scalar(item))
    return "".join(out)


def deeper_than(value: Any, level: int, limit: int = MAX_LEVEL) -> bool:
    """Whether an array or object inside ``value`` (itself at ``level``) sits deeper than ``limit``."""
    stack = [(value, level)]
    while stack:
        item, at = stack.pop()
        if at > limit:
            return True
        for child in (item.values() if isinstance(item, dict) else item):
            if isinstance(child, (dict, list)):
                stack.append((child, at + 1))
    return False


def _check_depth(projections: list[tuple[str, dict[str, Any]]]) -> None:
    """Section 12: each projection is a tool's contract entry or its extras, read at level 2 (the
    tool's own level), so the values of its members are at level 3."""
    for name, projection in projections:
        if deeper_than(projection, 2):
            raise DigestError("TSD-DEPTH", f"a value of tool {name!r} is nested deeper than level {MAX_LEVEL}")


# --- the two digests (sections 4 to 8) ------------------------------------------------------------

def _tool(tool: Any) -> dict[str, Any]:
    if not isinstance(tool, dict):
        raise DigestError("TSD-TOOL", "a tool entry is not a JSON object")
    if not isinstance(tool.get("name"), str) or not tool["name"]:
        raise DigestError("TSD-TOOL", "a tool entry has no non-empty string name")
    return tool


def contract_entry(tool: Any) -> dict[str, Any]:
    tool = _tool(tool)
    entry: dict[str, Any] = {
        "name": tool["name"],
        "description": tool["description"] if isinstance(tool.get("description"), str) else "",
        "inputSchema": tool["inputSchema"] if isinstance(tool.get("inputSchema"), dict) else {},
    }
    if isinstance(tool.get("outputSchema"), dict):
        entry["outputSchema"] = tool["outputSchema"]
    return entry


def ordered(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """By name in UTF-16 code units; entries sharing a name by their canonical UTF-8 bytes."""
    return sorted(entries, key=lambda e: (utf16_key(e["name"]), canonical(e).encode("utf-8")))


def digest_of(entries: list[dict[str, Any]]) -> tuple[str, str]:
    text = canonical(ordered(entries))
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii"), text


def tools_of(value: Any) -> list[Any]:
    """Extract a complete tools array or the tools from an unpaginated ``tools/list`` result."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for result in (value, value.get("result")):
            if isinstance(result, dict) and "tools" in result and "result" in result:
                raise DigestError("TSD-TOOL", "an object holds both tools and result (section 3)")
            if isinstance(result, dict) and isinstance(result.get("tools"), list):
                if "nextCursor" in result:
                    raise DigestError("TSD-PAGE", "collect all pages and pass the joined tools array")
                return result["tools"]
    raise DigestError("TSD-TOOL", "the input holds no tools array")


def contract(tools: list[Any]) -> tuple[str, str]:
    """``(digest, canonical text)`` of the contract digest."""
    entries = [contract_entry(tool) for tool in tools]
    _check_depth([(entry["name"], entry) for entry in entries])
    return digest_of(entries)


def extras_object(tools: list[Any]) -> dict[str, Any] | None:
    """``{"tools": {name: extras}}`` for the tools that carry a member outside the contract, or
    None when none does (section 8)."""
    by_name: dict[str, Any] = {}
    for tool in tools:
        tool = _tool(tool)
        extra = {key: value for key, value in tool.items() if key not in CONTRACT_MEMBERS}
        if not extra:
            continue
        if tool["name"] in by_name:
            raise DigestError("TSD-NAME", f"two tools named {tool['name']!r} both carry extras")
        by_name[tool["name"]] = extra
    return {"tools": by_name} if by_name else None


def extras(tools: list[Any]) -> tuple[str | None, str | None]:
    """``(digest, canonical text)`` of the extras digest; ``(None, None)`` when no tool has extras."""
    body = extras_object(tools)
    if body is None:
        return None, None
    _check_depth(list(body["tools"].items()))
    text = canonical(body)
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii"), text


def both(text: str) -> dict[str, dict[str, Any]]:
    """``{"contract": …, "extras": …}``: each ``{"digest", "canonical"}`` or ``{"error"}``; the
    extras digest is ``{"digest": None}`` when no tool carries extras. The two are computed apart,
    so a member only the extras digest covers cannot take the contract digest away."""
    tools = tools_of(parse(text))
    out: dict[str, dict[str, Any]] = {}
    for kind, compute in (("contract", contract), ("extras", extras)):
        try:
            digest, canonical_text = compute(tools)
            out[kind] = {"digest": digest} if digest is None else {"digest": digest, "canonical": canonical_text}
        except DigestError as error:
            out[kind] = {"error": error.code}
    return out


def digests(text: str) -> tuple[str, str | None]:
    """``(contract digest, extras digest or None)``; raises DigestError when either cannot be computed."""
    tools = tools_of(parse(text))
    return contract(tools)[0], extras(tools)[0]


def hex_form(digest: str) -> str:
    """The same hash as ``sha256:<lowercase hex>``, for systems that write digests that way."""
    return "sha256:" + base64.b64decode(digest.split("-", 1)[1]).hex()


# --- command line ---------------------------------------------------------------------------------

def check_vectors(path: str) -> int:
    document = json.load(open(path, encoding="utf-8"))
    failed = 0
    by_id: dict[str, dict[str, dict[str, str]]] = {}
    for vector in document["vectors"]:
        try:
            got = both(vector["tools"])
        except DigestError as error:        # the input holds no tools array
            got = {"contract": {"error": error.code}, "extras": {"error": error.code}}
        by_id[vector["id"]] = got
        for kind in ("contract", "extras"):
            want = {k: v for k, v in vector[kind].items() if k != "hex"}
            if got[kind] != want:
                failed += 1
                print(f"FAIL {vector['id']} {kind}: {got[kind].get('digest') or got[kind].get('error')} "
                      f"!= {want.get('digest') or want.get('error')}")
            elif want.get("digest") and hex_form(want["digest"]) != vector[kind]["hex"]:
                failed += 1
                print(f"FAIL {vector['id']} {kind}: hex form")
    for relation, same in (("equal", True), ("differ", False)):
        for row in document.get(relation, []):
            first, second = (by_id[i][row["digest"]].get("digest") for i in row["ids"])
            if first is None or second is None or (first == second) != same:
                failed += 1
                print(f"FAIL {relation} {row['ids']} {row['digest']}")
    print(f"python: {len(document['vectors'])} vectors, {failed} failed")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--vectors":
        return check_vectors(argv[1])
    try:
        result = both(sys.stdin.read())
    except DigestError as error:
        print(json.dumps({"error": error.code, "detail": str(error)}))
        return 2
    print(json.dumps({kind: value["digest"] if "digest" in value else {"error": value["error"]} for kind, value in result.items()}))
    return 0 if all("digest" in value for value in result.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
