// Read signed-note verifier keys (c2sp.org/signed-note, "Verifier keys"), one per line, and print one JSON
// line for each: the parts of the key, or why it is refused. Node.js standard library only.
//
//     <key name>+hex(32-bit key ID)+base64(signature type || public key)
//
// The name has no '+' and the key ID is hex, so the first two '+' are the only separators: the base64 part
// is standard base64 and may contain '+' itself.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// The public key length the C2SP texts fix for a signature type (signed-note, tlog-checkpoint).
const KEY_BYTES = { 0x01: 32, 0x04: 32, 0x06: 1312 };
// Unicode White_Space: key names must not contain any of these.
const SPACES = new Set([0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]);
for (let c = 0x2000; c <= 0x200A; c += 1) SPACES.add(c);
const hasSpace = (text) => [...text].some((ch) => SPACES.has(ch.codePointAt(0)));

function parse(vkey) {
  const first = vkey.indexOf('+');
  const second = first < 0 ? -1 : vkey.indexOf('+', first + 1);
  if (second < 0) return { refused: 'not-three-parts' };
  const name = vkey.slice(0, first);
  const hexId = vkey.slice(first + 1, second);
  const b64 = vkey.slice(second + 1);
  if (name === '' || hasSpace(name)) return { refused: 'bad-name' };
  if (!/^[0-9a-fA-F]{8}$/.test(hexId)) return { refused: 'bad-key-id' };
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(b64)) return { refused: 'bad-base64' };
  const raw = Buffer.from(b64, 'base64');
  if (raw.length < 2 || raw.toString('base64') !== b64) return { refused: 'bad-base64' };
  const kind = raw[0];
  const key = raw.subarray(1);
  if (kind in KEY_BYTES && key.length !== KEY_BYTES[kind]) return { refused: 'bad-key-length' };
  const keyId = createHash('sha256').update(Buffer.from(name, 'utf8')).update(Buffer.from([0x0a, kind]))
    .update(key).digest().subarray(0, 4).toString('hex');
  if (keyId !== hexId.toLowerCase()) return { refused: 'key-id-mismatch' };
  return {
    keyBytes: key.length, keyId, keySha256: createHash('sha256').update(key).digest('hex'), name,
    type: '0x' + kind.toString(16).padStart(2, '0'),
  };
}

for (const line of readFileSync(0, 'utf8').split('\n')) {
  if (line !== '') console.log(JSON.stringify(parse(line)));
}
