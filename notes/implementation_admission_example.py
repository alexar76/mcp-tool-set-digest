#!/usr/bin/env python3
"""Prints the worked example of notes/implementation-admission.md: the two signed objects (A's and B's
authorization) for one declaration and one call, each as RFC 8785 text and its SHA-256.

    python3 notes/implementation_admission_example.py

Standard library only; the digests come from the Python reference implementation in this repository.
"""
import base64
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "implementations", "python"))
import tool_set_digest as tsd  # noqa: E402

DECLARATION = ('[{"name": "read_file", "title": "Read file", "description": "Read a file from disk.", '
               '"inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, '
               '"annotations": {"readOnlyHint": true}}]')
ARGUMENTS = '{"path": "/srv/report.txt"}'


def sha256(text: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def binding(admission: str) -> dict:
    contract, extras = tsd.digests(DECLARATION)
    return {
        "binding": "implementation-admission/0",
        "tool_set": {"profile": "mcp-tool-set-digest/1", "contract": contract, "extras": extras},
        "call": {"tool": "read_file", "arguments": sha256(tsd.canonical(tsd.parse(ARGUMENTS)))},
        "implementation_admission": admission,
    }


for name, admission in (("A", "admission:A"), ("B", "admission:B")):
    text = tsd.canonical(binding(admission))
    print(f"{name}: {text}")
    print(f"{name} sha256: {sha256(text)}")
