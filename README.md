# MCP tool-set digest

<!-- aicom-mirror-notice -->
> 🔄 Synced from the [AI-Factory monorepo](https://github.com/alexar76/aicom) (append-only history). **Pull requests are welcome** — merged PRs are imported back and re-synced here. [Issues](https://github.com/alexar76/mcp-tool-set-digest/issues) · [Pull requests](https://github.com/alexar76/mcp-tool-set-digest/pulls)

One way to hash what an MCP server says about its tools, so that two parties who never exchanged
the tool text can tell whether they were served the same thing.

* [`SPEC.md`](SPEC.md): the specification, `mcp-tool-set-digest/1` (draft of 2026-11-13, about four pages).
* [`vectors/vectors.json`](vectors/vectors.json): 92 test vectors, with the canonical text each digest is the hash of.
* [`vectors/jcs-subset.json`](vectors/jcs-subset.json): 22 of those inputs as plain RFC 8785 (JCS) cases, for any JSON value, with each implementation's answer. See [RFC 8785 alone](#rfc-8785-alone).
* [`vectors/vkey-cases.json`](vectors/vkey-cases.json): 16 signed-note verifier keys with what three readers make of each. Not part of the specification. See [Verifier keys](#verifier-keys).
* [`implementations/`](implementations/): reference implementations in Python, JavaScript and Go, each one file with no dependencies.
* [`notes/implementation-admission.md`](notes/implementation-admission.md): a proposal, not part of the specification: binding a signed call to the admitted implementation that may run it, with three test cases.

## The digests in one paragraph

Take the `tools` array of a complete `tools/list` result. Of every tool keep `name`,
`description` (`""` when absent), `inputSchema` (`{}` when absent) and `outputSchema` (when
it is a JSON object). Sort the tools by name in UTF-16 code-unit order. Write the array as RFC 8785
canonical JSON. SHA-256 it. Write the result as `sha256-<base64>`. That is the **contract
digest**. Everything else a tool carries (`title`, `annotations`, `_meta`, …) goes into an object
`{"tools": {name: extras}}`, hashed the same way: the **extras digest**.

```
$ cat read_file.json
[{"name": "read_file", "title": "Read file", "description": "Read a file from disk.",
  "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
  "annotations": {"readOnlyHint": true}}]
$ python3 implementations/python/tool_set_digest.py < read_file.json
{"contract": "sha256-pUO5TdOtj4yR/mh2VDcu4y6axwVix4xgwST6cFkdd3g=", "extras": "sha256-Kmdz0r/Y+YnXALUVpJTXG8TUbKQhoFKQ7CeEpIw+1Oc="}
$ node implementations/javascript/tool-set-digest.mjs < read_file.json
$ (cd implementations/go && go run .) < read_file.json
```

All three print the same two digests. If a response contains `nextCursor`, the commands return
`TSD-PAGE`. Fetch every page and pass the concatenated `tools` array. A bare array carries no
pagination information, so the caller has to supply the complete list.

## Why another document

Tools that watch MCP servers often hash different fields, which prevents direct comparison.
HISTOR (a public log), WARDEN (a client-side firewall) and CrawlCheck (a lock file and change feed)
had converged on the contract digest by November 2026. This document gives implementers one set of
rules and test vectors. Appendix A records the contract checks and the differences in how extras
are hashed.

For an approval that depends on annotations, compare an annotation-inclusive digest or the
contract and complete extras separately. [Profiles and approval](SPEC.md#111-profiles-and-approval)
defines which coverage a decision requires and how to describe it in signed records.

## Checking an implementation

Read `vectors/vectors.json`. For each vector, parse `tools` (it is JSON text, kept as text so that
number forms and escapes reach you as written), compute the two digests and compare them and the
canonical texts with `contract` and `extras`; where one is `{"error": …}`, your implementation must
give no digest of that kind, and where `extras` is `{"digest": null}` no tool has extras. `equal` and `differ` list pairs of vectors whose digests must match or must not.

The vectors cover what goes wrong in practice:

| Group | Examples |
|---|---|
| order | `Z_tool` before `a_tool`; `resume`, `rezume`, `résumé`; U+1F600 before U+E000; two tools with one name |
| numbers | `1.0`, `1E2`, `-0.0`, `1e21`, `1e-7`, an integer beyond 2^53, `1e400` |
| strings | every JSON escape, U+2028, NFC and NFD, lone surrogates |
| members | absent, `null` and wrongly typed `description`, `inputSchema`, `outputSchema` |
| extras | present and absent; `readOnlyHint` and `destructiveHint` flips; numbers and names outside the BMP; two tools with one name |
| not a tool | a string, `null`, no `name`, an empty `name` |
| repeated names | a member written twice in a tool, inside `inputSchema` and outside the contract; once plainly and once escaped; an empty `name` first or last |
| depth | 512 levels counted from the tools array on each side of the contract, and one past it |
| several codes | two tools with one name whose extras also hold a lone surrogate or a number with no double; a lone surrogate before an entry that is not a tool |

## RFC 8785 alone

[`vectors/jcs-subset.json`](vectors/jcs-subset.json) takes 22 inputs from the vectors and asks for the RFC 8785
canonical form of the whole JSON value, not of a tool set: number forms (`1E2`, `-0.0`, `1e21`, an integer beyond
2^53, `1e400` refused), escapes and U+2028, NFC against NFD, lone surrogates refused, member names sorted by UTF-16
code unit, and array order kept. Each case gives the canonical text and its SHA-256, or the reason RFC 8785 has no
output, and what the Python, JavaScript and Go implementations each answered (`--canonical`, which reads one JSON
value on standard input). It was cut for checking signed-receipt digests
([x402-foundation/x402#4457](https://github.com/x402-foundation/x402/issues/4457)); repeated member names are left
out, because RFC 8785 requires I-JSON and this specification keeps the last one. `scripts/jcs_subset.py` writes the
file and `--check` compares it with what the implementations give now.

## Verifier keys

[`vectors/vkey-cases.json`](vectors/vkey-cases.json) is not about tool lists. A transparency-log checkpoint is
checked with [signed-note](https://c2sp.org/signed-note) verifier keys, written
`<key name>+hex(key ID)+base64(signature type || public key)`. The base64 part is standard base64 and may itself
contain `+`, so only the first two `+` separate. A reader that splits on every `+` passes its tests with a key
whose base64 part happens to hold none, and fails on the next key: about every second Ed25519 key, and
practically every ML-DSA-44 key (1,752 base64 characters). The file has 16 cases:

* six keys to accept: the example of the signed-note text (no `+`), two Ed25519 keys of public witnesses (one
  and two `+`), the ML-DSA-44 key one of those witnesses publishes (27), and two ML-DSA-44 test keys (24 and 33);
* ten to refuse: two parts only, a name with `+` that a reader splitting from the right would accept, an empty
  name, a name with a space, a short key ID, a key ID that does not recompute, base64 cut short, in the URL-safe
  alphabet or not canonical, and an Ed25519 key of 31 bytes.

Each case gives the parts of the key or the refusal, and what readers in Python, JavaScript and Go answered
(`scripts/vkey/`, standard library only). The cases were asked for beside the RFC 8785 cases in
[x402-foundation/x402#4457](https://github.com/x402-foundation/x402/issues/4457). `scripts/vkey_cases.py` writes
the file and `--check` compares it with what the readers give now. Verifying signatures is not covered.

To run everything in this repository:

```
scripts/check.sh
```

Requires Python 3.9+, Node.js 20+ and Go 1.21+. It compares the generated vectors with the checked-in
file, runs the three implementations over them, and checks that all three command lines agree on a
complete list and reject a response that has `nextCursor`.

## Status

A draft by two editors, Aleksandr Artamokhov (HISTOR) and Emmanuel Orta (CrawlCheck), offered for discussion to the people who implement tool-definition pinning
and to the MCP Security Interest Group, whose agenda lists "Runtime drift: `list_changed` semantics
after approval" and "Supply-chain integrity" as open topics. Comments and other implementations'
results are welcome as issues. Open questions are in Appendix B of the specification.

## Licence

The specification text is CC BY 4.0. The implementations, the scripts and the vectors are Apache-2.0 OR
MIT, at your choice. See `LICENSE`.
