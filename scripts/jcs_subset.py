"""Write vectors/jcs-subset.json: the RFC 8785 (JCS) cases of the test vectors, for any JSON value, with each
implementation's answer.

    python3 scripts/jcs_subset.py            # write the file
    python3 scripts/jcs_subset.py --check    # fail if the file is not what the three implementations give now

Each case takes the JSON text of one vector in vectors.json (its `tools`) as a plain JSON value and asks every
implementation for the RFC 8785 text of the whole value and that text's SHA-256 (`--canonical`), or for the reason
it refuses. Nothing here is specific to tool lists: the text is canonicalized as it stands. A case is written only
when the three implementations agree; their three answers stay in the file, so a fourth implementation that differs
shows up as one implementation against three. Asked for in x402-foundation/x402#4457 (signed-receipt digests).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vectors" / "jcs-subset.json"
IMPLEMENTATIONS = {
    "python": (["python3", "tool_set_digest.py", "--canonical"], ROOT / "implementations" / "python"),
    "javascript": (["node", "tool-set-digest.mjs", "--canonical"], ROOT / "implementations" / "javascript"),
    "go": (["go", "run", ".", "--canonical"], ROOT / "implementations" / "go"),
}
# Our refusal codes, named for readers who do not use this specification (SPEC.md section 10).
REFUSALS = {
    "TSD-NUMBER": "number-without-double: a number literal with no IEEE 754 double (RFC 8785 section 3.2.2.3, "
                  "I-JSON RFC 7493 section 2.2)",
    "TSD-TEXT": "lone-surrogate: a string holding an unpaired UTF-16 surrogate (RFC 8785 section 3.2.2.2, "
                "I-JSON RFC 7493 section 2.1)",
}
CASES = [
    # numbers
    "numbers-as-written", "numbers-canonical", "extras-numbers-as-written", "extras-numbers-canonical",
    "integer-beyond-2-53-odd", "integer-beyond-2-53-even", "number-overflow", "number-overflow-negative",
    # strings
    "string-escapes", "string-escaped-a", "string-raw-a", "string-nfc", "string-nfd",
    "lone-surrogate-high", "lone-surrogate-low", "lone-surrogate-reversed", "lone-surrogate-in-key",
    # member order and whitespace
    "member-order-keys", "order-utf16-escaped", "order-utf16-raw", "typical",
    "typical-whitespace",
]
# Where the vector's note speaks of the tool-set digest, what the case shows for RFC 8785 alone.
NOTES = {
    "order-utf16-escaped": "U+E000 and U+1F600 written as \\u escapes. RFC 8785 keeps array order; with "
                           "order-utf16-raw this shows that escaped and raw characters give the same bytes.",
    "order-utf16-raw": "The same two names written as the characters themselves.",
    "typical": "Two ordinary tools.",
    "typical-whitespace": "The same tools with other whitespace and member order, and the two tools in the other "
                          "order: RFC 8785 sorts members but keeps array order, so this differs from typical.",
}
EQUAL = [
    ["numbers-as-written", "numbers-canonical"], ["extras-numbers-as-written", "extras-numbers-canonical"],
    ["integer-beyond-2-53-odd", "integer-beyond-2-53-even"], ["string-escaped-a", "string-raw-a"],
    ["order-utf16-escaped", "order-utf16-raw"],
]
# typical-whitespace also lists the two tools in the other order. The tool-set digest sorts tools; RFC 8785 keeps
# array order, so here the two must differ. NFC and NFD are different strings: RFC 8785 does not normalize.
DIFFER = [["string-nfc", "string-nfd"], ["typical", "typical-whitespace"]]


def answer(command, cwd, text):
    run = subprocess.run(command, cwd=cwd, input=text.encode("utf-8", "surrogatepass"),
                         capture_output=True, timeout=120)
    try:
        return json.loads(run.stdout.decode("utf-8").strip().split("\n")[-1])
    except (ValueError, IndexError):
        sys.exit(f"{command[0]} gave no answer: {run.stderr.decode(errors='replace')[:300]}")


def build():
    vectors = {v["id"]: v for v in json.loads((ROOT / "vectors" / "vectors.json").read_text())["vectors"]}
    cases = []
    for case_id in CASES:
        vector = vectors[case_id]
        answers = {name: answer(cmd, cwd, vector["tools"]) for name, (cmd, cwd) in IMPLEMENTATIONS.items()}
        distinct = {json.dumps(a, sort_keys=True) for a in answers.values()}
        if len(distinct) != 1:
            sys.exit(f"{case_id}: the implementations disagree: {answers}")
        agreed = next(iter(answers.values()))
        expected = ({"refused": REFUSALS[agreed["error"]].split(":")[0], "code": agreed["error"]}
                    if "error" in agreed else {"canonical": agreed["canonical"], "sha256": agreed["sha256"]})
        cases.append({"id": case_id, "note": NOTES.get(case_id, vector["note"]), "input": vector["tools"], "expected": expected,
                      "implementations": answers})
    by_id = {c["id"]: c["expected"] for c in cases}
    for pair in EQUAL:
        assert by_id[pair[0]] == by_id[pair[1]], pair
    for pair in DIFFER:
        assert by_id[pair[0]] != by_id[pair[1]], pair
    return {
        "format": "RFC 8785 (JCS) cases from the mcp-tool-set-digest/1 test vectors",
        "licence": "Apache-2.0 OR MIT",
        "how": ("input is JSON text. Parse it as I-JSON and write the RFC 8785 canonical form of the whole value; "
                "expected is {canonical, sha256} (sha256 = hex SHA-256 of the UTF-8 bytes of canonical) or "
                "{refused, code} when RFC 8785 has no output for the input. implementations holds what each of the "
                "three reference implementations answered (python, javascript, go; `--canonical` mode), all equal. "
                "equal and differ name pairs whose expected results must match or must not."),
        "refusals": REFUSALS,
        "source": "vectors.json (each case's id is the vector its input comes from; scripts/jcs_subset.py)",
        "not_covered": ("repeated member names (RFC 8785 requires I-JSON, which forbids them; mcp-tool-set-digest "
                        "keeps the last one, so those vectors are left out) and nesting depth limits."),
        "equal": EQUAL,
        "differ": DIFFER,
        "cases": cases,
    }


def main():
    text = json.dumps(build(), ensure_ascii=True, indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            sys.exit("vectors/jcs-subset.json is not what the implementations give now: run scripts/jcs_subset.py")
        print(f"jcs-subset.json: {len(json.loads(text)['cases'])} cases, the three implementations agree")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(json.loads(text)['cases'])} cases")


if __name__ == "__main__":
    main()
