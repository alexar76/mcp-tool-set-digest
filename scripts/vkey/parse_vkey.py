"""Read signed-note verifier keys (c2sp.org/signed-note, "Verifier keys"), one per line, and print one JSON
line for each: the parts of the key, or why it is refused. Standard library only.

    <key name>+hex(32-bit key ID)+base64(signature type || public key)

The name has no '+' and the key ID is hex, so the first two '+' are the only separators: the base64 part
is standard base64 and may contain '+' itself.
"""
import base64
import hashlib
import json
import re
import sys

# The public key length the C2SP texts fix for a signature type (signed-note, tlog-checkpoint).
KEY_BYTES = {0x01: 32, 0x04: 32, 0x06: 1312}
# Unicode White_Space: key names must not contain any of these.
SPACES = {chr(c) for c in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, *range(0x2000, 0x200B))}


def parse(vkey):
    parts = vkey.split("+", 2)
    if len(parts) != 3:
        return {"refused": "not-three-parts"}
    name, hex_id, b64 = parts
    if not name or any(ch in SPACES for ch in name):
        return {"refused": "bad-name"}
    if not re.fullmatch(r"[0-9a-fA-F]{8}", hex_id):
        return {"refused": "bad-key-id"}
    try:
        raw = base64.b64decode(b64, validate=True)
    except ValueError:
        return {"refused": "bad-base64"}
    if len(raw) < 2 or base64.b64encode(raw).decode() != b64:
        return {"refused": "bad-base64"}
    kind, key = raw[0], raw[1:]
    if kind in KEY_BYTES and len(key) != KEY_BYTES[kind]:
        return {"refused": "bad-key-length"}
    key_id = hashlib.sha256(name.encode() + b"\n" + bytes([kind]) + key).digest()[:4].hex()
    if key_id != hex_id.lower():
        return {"refused": "key-id-mismatch"}
    return {"name": name, "keyId": key_id, "type": f"0x{kind:02x}", "keyBytes": len(key),
            "keySha256": hashlib.sha256(key).hexdigest()}


if __name__ == "__main__":
    for line in sys.stdin.buffer.read().decode("utf-8").split("\n"):
        if line:
            print(json.dumps(parse(line), sort_keys=True))
