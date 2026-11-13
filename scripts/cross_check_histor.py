"""Checks every vector against HISTOR's own code, which was written before this specification and
separately from its reference implementations.

    PYTHONPATH=<monorepo>/histor:<monorepo>/awr/reference/python python3 scripts/cross_check_histor.py

* The contract digest against ``histor.subject.tool_set_digest``: every vector must agree. HISTOR's
  error codes are its own: MTL-SUBJ-001 (not a tool, or a string it cannot canonicalise) and
  MTL-NUM-001 (a number with no double).
* The extras digest against ``histor.extras.tool_extras``, the digest HISTOR publishes as
  ``toolExtrasDigest``, under each of HISTOR's two schemes. HISTOR's is the bounded, storage-oriented
  form (SPEC.md section 8.1). Under ``legacy`` (what HISTOR published until it moves) its serialiser is
  not RFC 8785 either, so it is expected to differ on the vectors named in KNOWN below; under
  ``rfc8785`` only on the bounded-form ones. A difference outside the list fails the check, and so
  does agreement on a listed vector.
"""

from __future__ import annotations

import json
from pathlib import Path

from histor import extras as histor_extras
from histor.extras import tool_extras
from histor.subject import MtlError, tool_set_digest

SAME_REASON = {"TSD-TOOL": {"MTL-SUBJ-001"}, "TSD-TEXT": {"MTL-SUBJ-001"}, "TSD-NUMBER": {"MTL-NUM-001"}}

#: vector id -> why HISTOR's deployed extras digest is another value there
KNOWN = {
    "extras-numbers-as-written": "HISTOR writes 1.0 and 0.50 as Python does and keeps 9007199254740993 exact; RFC 8785 writes 1, 0.5 and the nearest double",
    "extras-numbers-canonical": "the same: 1e-7 is written 1e-07, and the integer beyond 2^53 is not rounded",
    "extras-order-utf16": "HISTOR sorts member names by code point; RFC 8785 sorts by UTF-16 code unit",
    "number-overflow-in-extras": "HISTOR stores a number with no double as null and digests the rest",
    "lone-surrogate-in-extras": "HISTOR replaces an unpaired surrogate with U+FFFD and digests the result",
    "duplicate-names-both-with-extras": "HISTOR keeps the extras of the tool listed last",
    "duplicate-names-before-lone-surrogate": "HISTOR keeps the extras of the tool listed last",
    "duplicate-names-before-number-overflow": "HISTOR keeps the extras of the tool listed last",
    "lone-surrogate-before-bad-entry": "HISTOR passes over an entry that is not a tool",
    "one-bad-among-good": "HISTOR passes over an entry that is not a tool",
    "tool-is-string": "HISTOR passes over an entry that is not a tool",
    "tool-is-null": "HISTOR passes over an entry that is not a tool",
    "tool-is-array": "HISTOR passes over an entry that is not a tool",
    "name-missing": "HISTOR passes over an entry that is not a tool",
    "name-empty": "HISTOR passes over an entry that is not a tool",
    "name-not-string": "HISTOR passes over an entry that is not a tool",
}

#: the three KNOWN entries that are serialisation, not storage limits: gone under rfc8785
SERIALISER_ONLY = {"extras-numbers-as-written", "extras-numbers-canonical", "extras-order-utf16"}
SCHEMES = getattr(histor_extras, "SCHEMES", ("legacy",))


def known(scheme: str) -> dict[str, str]:
    return {k: v for k, v in KNOWN.items() if scheme == "legacy" or k not in SERIALISER_ONLY}


def main() -> int:
    document = json.loads(Path(__file__).resolve().parent.parent.joinpath("vectors/vectors.json").read_text("utf-8"))
    failed = 0
    agreed = dict.fromkeys(SCHEMES, 0)
    differed: dict[str, list[str]] = {scheme: [] for scheme in SCHEMES}
    for vector in document["vectors"]:
        tools = json.loads(vector["tools"])
        want = vector["contract"]
        try:
            got = tool_set_digest(tools)[0]
        except MtlError as error:
            if error.code not in SAME_REASON.get(want.get("error", ""), ()):
                failed += 1
                print(f"FAIL {vector['id']} contract: HISTOR refuses with {error.code}, the vector says {want}")
        else:
            if got != want.get("digest"):
                failed += 1
                print(f"FAIL {vector['id']} contract: HISTOR {got} != {want.get('digest') or want.get('error')}")

        expected = vector["extras"].get("digest") if "error" not in vector["extras"] else ("error", vector["extras"]["error"])
        for scheme in SCHEMES:
            listed = known(scheme)
            theirs = tool_extras(tools, scheme)[0] if len(SCHEMES) > 1 else tool_extras(tools)[0]
            if theirs == expected:
                agreed[scheme] += 1
                if vector["id"] in listed:
                    failed += 1
                    print(f"FAIL {vector['id']} extras ({scheme}): listed as a known difference, and HISTOR agrees")
            elif vector["id"] in listed:
                differed[scheme].append(vector["id"])
            else:
                failed += 1
                print(f"FAIL {vector['id']} extras ({scheme}): HISTOR {theirs} != {expected}")
    total = len(document["vectors"])
    print(f"histor: {total} vectors; contract digest {total - failed if not failed else '(see above)'} agree")
    for scheme in SCHEMES:
        print(f"  extras digest, {scheme}: {agreed[scheme]} agree, {len(differed[scheme])} differ as documented")
    for identifier in differed[SCHEMES[-1]]:
        print(f"  documented difference, {identifier}: {KNOWN[identifier]}")
    print(f"  {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
