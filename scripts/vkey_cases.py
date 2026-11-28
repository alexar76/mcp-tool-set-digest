"""Write vectors/vkey-cases.json: signed-note verifier keys (c2sp.org/signed-note) and what three readers make of
each one.

    python3 scripts/vkey_cases.py            # write the file
    python3 scripts/vkey_cases.py --check    # fail if the file is not what the three readers give now

A verifier key is `<key name>+hex(32-bit key ID)+base64(signature type || public key)`. The base64 part is
standard base64 and may contain '+', the separator, so only the first two '+' separate. A reader that splits on
every '+' works for a key whose base64 happens to hold none and fails for the next key. That is about every
second Ed25519 key (44 base64 characters) and practically every ML-DSA-44 key (1,752 characters). The cases are
keys with and without '+' in the base64 part, and keys that must be refused.

This is not part of mcp-tool-set-digest/1. The file sits here because the cases were asked for beside
jcs-subset.json in x402-foundation/x402#4457 (anchors for signed receipts: a checkpoint is checked with such keys).
A case is written only when the three readers (scripts/vkey/: Python, JavaScript, Go) agree.
"""
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vectors" / "vkey-cases.json"
READERS = {
    "python": (["python3", "parse_vkey.py"], ROOT / "scripts" / "vkey"),
    "javascript": (["node", "parse_vkey.mjs"], ROOT / "scripts" / "vkey"),
    "go": (["go", "run", "."], ROOT / "scripts" / "vkey" / "go"),
}
REFUSALS = {
    "not-three-parts": "fewer than two '+' in the text",
    "bad-name": "the key name is empty or contains a Unicode space (signed-note: key names MUST be non-empty and "
                "MUST NOT contain Unicode spaces or plus characters)",
    "bad-key-id": "the second part is not eight hex digits",
    "bad-base64": "the third part is not canonical standard base64 with padding (RFC 4648 section 4; signed-note: "
                  "decoders MUST reject non-canonical encodings), or holds fewer than two bytes",
    "bad-key-length": "the public key has another length than the C2SP texts fix for its signature type "
                      "(0x01 and 0x04: 32 bytes, 0x06: 1312 bytes)",
    "key-id-mismatch": "the key ID is not SHA-256(key name || 0x0A || signature type || public key)[:4]",
}
LONG = json.loads((ROOT / "scripts" / "vkey" / "long-keys.json").read_text())
C2SP_EXAMPLE = "example.com/foo+530d903a+AekyeRrm56hApGFkyQR4ZCbV54Id2LKaANYcrnKv3U2k"
WITNESS_ONE = "krabbel.ct.ipng.ch+4b10dbd8+BO4sLOtnhktlqMCejDx9C5LDd+/xZxbmBb6BP9ZD2Def"
WITNESS_TWO = "staging.witness.transparency.goog/ring-any-bells+2e1a8dc9+BG5JTpLc3FJtwzgh1Uv+Qelz9qeOH2bfWjS1s0s+y4rL"
GIST = "gist.github.com/johnInarti/0e06898fff2aa45c99bcd4b943a5a487 (test key from a published seed)"
WITNESS_PAGE = "transparency.dev/witnesses, read 2026-11-28"


def vkey(name, kind, key):
    key_id = hashlib.sha256(name.encode() + b"\n" + bytes([kind]) + key).digest()[:4].hex()
    return f"{name}+{key_id}+{base64.b64encode(bytes([kind]) + key).decode()}"


def example_key():
    return base64.b64decode(C2SP_EXAMPLE.split("+", 2)[2])[1:]


def not_canonical(text):
    """The same bytes with the two unused bits of the last base64 character set."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    assert text.endswith("=") and not text.endswith("==")
    return text[:-2] + alphabet[alphabet.index(text[-2]) | 1] + "="


CASES = [
    ("c2sp-example", "The example key of the signed-note text. No '+' in the base64 part.",
     "c2sp.org/signed-note, Verifier keys, Example", C2SP_EXAMPLE),
    ("ed25519-one-plus", "A public witness key (Ed25519 cosignature, 0x04) with one '+' in the base64 part.",
     "a witness that cosigns histor.modelmarket.dev/log; its key ID is on the cosigned checkpoint", WITNESS_ONE),
    ("ed25519-two-plus", "A public witness key (0x04) with two '+' in the base64 part.", WITNESS_PAGE, WITNESS_TWO),
    ("ml-dsa-44-witness", "The ML-DSA-44 key (0x06) the same witness publishes next to its Ed25519 key.",
     WITNESS_PAGE, LONG["ml-dsa-44-witness"]),
    ("ml-dsa-44-test-1", "ML-DSA-44 test key w1 of the checkpoint-signature cases posted in x402 #4457.", GIST,
     LONG["ml-dsa-44-test-1"]),
    ("ml-dsa-44-test-2", "ML-DSA-44 test key w2 of the same cases.", GIST, LONG["ml-dsa-44-test-2"]),
    ("two-parts", "The base64 part is missing.", "c2sp-example cut short", C2SP_EXAMPLE.rsplit("+", 1)[0]),
    ("name-with-plus", "The name is example.com/a+b and the key ID is the one that name would have. The base64 part "
     "holds no '+', so a reader that splits from the right takes it for a good key. Reading from the left, the "
     "second part is `b`, which is no key ID.", "the c2sp-example key under another name",
     vkey("example.com/a+b", 0x01, example_key())),
    ("empty-name", "No key name; the key ID is the one an empty name would have.",
     "the c2sp-example key under another name", vkey("", 0x01, example_key())),
    ("name-with-space", "The name holds U+0020; the key ID is the one that name would have.",
     "the c2sp-example key under another name", vkey("example.com/fo o", 0x01, example_key())),
    ("key-id-short", "Six hex digits where eight are needed.", "c2sp-example with a shorter key ID",
     C2SP_EXAMPLE.replace("+530d903a+", "+530d90+")),
    ("key-id-mismatch", "The last digit of the key ID is changed.", "c2sp-example with another key ID",
     C2SP_EXAMPLE.replace("+530d903a+", "+530d903b+")),
    ("base64-cut", "The last base64 character is missing.", "c2sp-example cut short", C2SP_EXAMPLE[:-1]),
    ("base64-url-alphabet", "The base64 part in the URL-safe alphabet ('-' and '_').",
     "ed25519-one-plus in another alphabet",
     "+".join(WITNESS_ONE.split("+", 2)[:2]) + "+" + WITNESS_ONE.split("+", 2)[2].replace("+", "-").replace("/", "_")),
    ("base64-not-canonical", "The unused bits of the last base64 character are set: the same bytes, another text.",
     "ml-dsa-44-test-1 with one character changed", not_canonical(LONG["ml-dsa-44-test-1"])),
    ("ed25519-short-key", "Signature type 0x01 with a 31-byte key; the key ID is the one those bytes would have.",
     "the c2sp-example key without its last byte", vkey("example.com/foo", 0x01, example_key()[:-1])),
]


def answers(command, cwd, lines):
    run = subprocess.run(command, cwd=cwd, input=("\n".join(lines) + "\n").encode(), capture_output=True, timeout=300)
    out = [json.loads(line) for line in run.stdout.decode().split("\n") if line]
    if run.returncode != 0 or len(out) != len(lines):
        sys.exit(f"{command[0]} gave no answer: {run.stderr.decode(errors='replace')[:300]}")
    return out


def build():
    inputs = [case[3] for case in CASES]
    by_reader = {name: answers(cmd, cwd, inputs) for name, (cmd, cwd) in READERS.items()}
    cases = []
    for index, (case_id, note, source, text) in enumerate(CASES):
        given = {name: by_reader[name][index] for name in READERS}
        if len({json.dumps(a, sort_keys=True) for a in given.values()}) != 1:
            sys.exit(f"{case_id}: the readers disagree: {given}")
        parts = text.split("+", 2)
        cases.append({
            "id": case_id, "note": note, "source": source, "input": text,
            "plus_in_base64_part": parts[2].count("+") if len(parts) == 3 else None,
            "parts_when_split_on_every_plus": len(text.split("+")),
            "expected": given["python"], "implementations": given,
        })
    accepted = [c for c in cases if "refused" not in c["expected"]]
    assert {c["expected"]["refused"] for c in cases if "refused" in c["expected"]} == set(REFUSALS), "a refusal has no case"
    assert [c["id"] for c in accepted] == [c[0] for c in CASES[:6]], [c["id"] for c in accepted]
    return {
        "format": "signed-note verifier keys (c2sp.org/signed-note): parsing cases",
        "licence": "Apache-2.0 OR MIT",
        "how": ("input is one verifier key, <key name>+hex(32-bit key ID)+base64(signature type || public key). "
                "Split it at the first two '+' only. expected is {name, keyId, type, keyBytes, keySha256} (type is "
                "the first decoded byte, keyBytes and keySha256 describe the bytes after it) or {refused}. The "
                "checks run in the order of refusals, and the first that fails names the refusal. implementations "
                "holds what each of three readers answered (scripts/vkey/: python, javascript, go), all equal. "
                "plus_in_base64_part and parts_when_split_on_every_plus are counted from the input: a reader that "
                "splits on every '+' gets three parts only where the first number is 0."),
        "refusals": REFUSALS,
        "not_covered": ("verifying a signature with the key; what a reader does with a signature type it does not "
                        "know (the three readers return it with no length check); upper-case hex in the key ID "
                        "(the three readers accept it); spaces other than U+0020 in a name (refused, no case)."),
        "why_here": ("not part of mcp-tool-set-digest/1. Asked for beside jcs-subset.json in "
                     "x402-foundation/x402#4457; scripts/vkey_cases.py writes and checks the file."),
        "cases": cases,
    }


def main():
    text = json.dumps(build(), ensure_ascii=True, indent=1) + "\n"
    count = len(json.loads(text)["cases"])
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            sys.exit("vectors/vkey-cases.json is not what the readers give now: run scripts/vkey_cases.py")
        print(f"vkey-cases.json: {count} cases, the three readers agree")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {count} cases")


if __name__ == "__main__":
    main()
