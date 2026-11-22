"""Section 12 (depth) through the three command lines: run from the repository root by check.sh.

    python3 scripts/check_depth.py

Levels count arrays and objects: the tools array is level 1, a tool level 2, an array or object held
by a member of a tool level 3. A reader accepts every level up to 512 and gives TSD-DEPTH, for the
digest that would cover a deeper value, past it; no reader may crash. The edges come from CrawlCheck
(alexar76/mcp-tool-set-digest#1).
"""

import json
import subprocess
import sys

READERS = {
    "python": [sys.executable, "implementations/python/tool_set_digest.py"],
    "javascript": ["node", "implementations/javascript/tool-set-digest.mjs"],
    "go": ["go", "run", "."],
}
CWD = {"go": "implementations/go"}
TOOL = "sha256-88Wu+RBqslXnbKusDxk1TtLT0D2iT/d07h7ia5bzX2U="  # [{"name": "t"}]


def nest(n: int) -> str:
    return "[" * n + "0" + "]" * n


def schema(n: int) -> str:
    return '{"name":"t","inputSchema":{"x":%s}}' % nest(n)


def extra(n: int) -> str:
    return '{"name":"t","x":%s}' % nest(n)


DIGEST, DEPTH, NONE = "digest", "TSD-DEPTH", None
CASES = [
    # (id, text, contract, extras)
    ("contract-509", "[%s]" % schema(509), DIGEST, NONE),
    ("contract-510", "[%s]" % schema(510), DEPTH, NONE),
    ("contract-100000", "[%s]" % schema(100000), DEPTH, NONE),
    ("extras-510", "[%s]" % extra(510), TOOL, DIGEST),
    ("extras-511", "[%s]" % extra(511), TOOL, DEPTH),
    ("extras-100000", "[%s]" % extra(100000), TOOL, DEPTH),
    ("result-contract-509", '{"tools":[%s]}' % schema(509), "=contract-509", NONE),
    ("jsonrpc-contract-509", '{"jsonrpc":"2.0","id":1,"result":{"tools":[%s]}}' % schema(509), "=contract-509", NONE),
    ("jsonrpc-contract-510", '{"jsonrpc":"2.0","id":1,"result":{"tools":[%s]}}' % schema(510), DEPTH, NONE),
    ("deep-outside-tools", '{"jsonrpc":"2.0","id":%s,"result":{"tools":[{"name":"t"}]}}' % nest(100000), TOOL, NONE),
    ("deep-description", '[{"name":"t","description":%s}]' % nest(100000), TOOL, NONE),
    ("deep-string-brackets", '[{"name":"t","description":"%s"}]' % ("[" * 100000), "digest", NONE),
]


def run(reader: str, text: str) -> tuple[int, str]:
    done = subprocess.run(READERS[reader], input=text.encode(), capture_output=True, cwd=CWD.get(reader), timeout=120)
    return done.returncode, done.stdout.decode().strip().splitlines()[-1] if done.stdout.strip() else done.stderr.decode()[-300:]


def main() -> int:
    failed = 0
    seen: dict[str, dict] = {}
    for case, text, want_contract, want_extras in CASES:
        answers = {}
        for reader in READERS:
            code, line = run(reader, text)
            try:
                answers[reader] = json.loads(line)
            except ValueError:
                print(f"FAIL {case} {reader}: no JSON answer (exit {code}): {line}")
                failed += 1
        if len(answers) < len(READERS):
            continue
        if len({json.dumps(a, sort_keys=True) for a in answers.values()}) != 1:
            print(f"FAIL {case}: the readers disagree: {answers}")
            failed += 1
            continue
        got = answers["python"]
        seen[case] = got
        for side, want in (("contract", want_contract), ("extras", want_extras)):
            value = got.get(side)
            if isinstance(want, str) and want.startswith("="):
                ok = value == seen[want[1:]][side]
            elif want == DIGEST:
                ok = isinstance(value, str) and value.startswith("sha256-")
            elif want == DEPTH:
                ok = value == {"error": DEPTH}
            else:
                ok = value == want
            if not ok:
                print(f"FAIL {case} {side}: {value} (wanted {want})")
                failed += 1
    print(f"depth: {len(CASES)} cases through {len(READERS)} readers, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
