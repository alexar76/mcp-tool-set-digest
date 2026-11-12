# MCP tool-set digest, version 1

Identifier: `mcp-tool-set-digest/1` · Editor's draft, 2026-11-12 · Text: CC BY 4.0 · Code and vectors: Apache-2.0 OR MIT

**Status.** A draft for discussion. It writes down a digest that several independently maintained
tools already compute and agree on (Appendix A), so that the next implementation can agree with
them by reading one page and running one file of vectors. It is not a product of the MCP project or
of a standards body, and nobody named in it has endorsed it.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be read as in RFC 2119 and RFC 8174.

## 1. What it is for

An MCP server tells a client which tools it has in the result of `tools/list`. A model reads the
names, descriptions and schemas in that list and acts on them, and a server can serve a different
list tomorrow. To notice that, a client, a gateway, a registry or an outside observer keeps a
digest of the list and compares.

Two parties can only compare digests they compute the same way. Today each tool hashes the list in
its own way: different members, different order, different number formatting. This document fixes
one way, as two digests:

* the **contract digest**, over the parts of every tool that a model reads and a call must
  satisfy: its name, description and schemas;
* the **extras digest**, over everything else a tool carries: its title, annotations, icons,
  `_meta` and vendor members.

Together they cover every member of every tool, and they say which kind of change happened: the
contract digest moved, so what a model reads or a call accepts changed; only the extras digest
moved, so an annotation flipped, a title was edited or a price in `_meta` changed.

With them:

* a client that approved a tool set can tell that the set it is offered now is the same one;
* two clients, or a client and a public record, can tell whether a server serves them the same set,
  by exchanging 32 bytes and no tool text;
* a lock file written by one tool can be checked by another.

What they do not show is in section 12. In short: the digests cover what a server says about its
tools, not what the tools do.

## 2. Terms

*Tool set*: the `tools` array of one complete `tools/list` result.

*Contract members* of a tool: `name`, `description`, `inputSchema`, `outputSchema`. Every other
member a tool carries (`title`, `annotations`, `icons`, `execution`, `_meta`, vendor members) is an
*extra*.

*Producer*: whoever computes a digest.

## 3. Input

1. The input is the `tools` array of a successful `tools/list` result. When the result is paged,
   every page MUST be read (`nextCursor` followed to the end) and the arrays joined in the order
   they were read. A producer MUST NOT digest part of a list.
2. A list is what one server answered to one request under one authorisation. A server may list
   other tools to another user, scope or protocol version; those are other tool sets. A digest
   says nothing about a list the producer did not read.
3. The JSON text is parsed into values. Every number is the IEEE 754 double nearest to its
   literal, ties to even: what ECMAScript's `JSON.parse` yields and what a correctly rounding
   parser yields in any language. A parser that keeps large integers exact MUST convert an integer
   outside ±(2^53 − 1) to its nearest double before use (section 6).
4. When an object repeats a member name, the last one counts, which is what `JSON.parse`, Python's
   `json` and Go's `encoding/json` do. A producer whose parser reports repeated names SHOULD say so
   beside the digest. The vectors hold no repeated member names.
5. Nothing is normalised beyond what sections 4 to 8 state: no Unicode normalisation, no trimming,
   no case folding, no reading of the schemas.

## 4. Contract entry

Each element of the array MUST be a JSON object whose `name` is a non-empty string. Otherwise the
set has neither digest (`TSD-TOOL`, section 10).

Each tool is replaced by an object with exactly these members:

| Member | Value |
|---|---|
| `name` | the tool's `name` |
| `description` | the tool's `description` when it is a string, otherwise `""` |
| `inputSchema` | the tool's `inputSchema` when it is a JSON object, otherwise `{}` |
| `outputSchema` | the tool's `outputSchema`, present if and only if the tool carried a JSON object under that name |

Extras are left out of the contract digest; section 8 covers them.

`outputSchema` is conditional on purpose: a tool with no output schema and a tool with the empty
schema `{}` promise different things, and one rule for both would let a server change the promise
without moving the digest. `description` and `inputSchema` get a default because a tool without
them means the same to a model as a tool with an empty one.

## 5. Order

1. The entries are sorted by `name`, compared as sequences of **UTF-16 code units** read as
   unsigned integers. This is the order RFC 8785 section 3.2.3 gives to member names, so an
   implementation sorts both with one comparison.
2. Entries with the same `name` are ordered among themselves by their canonical text (section 6)
   as UTF-8, compared as unsigned bytes. All of them are kept.
3. The empty set is a set: its array is `[]`.

A producer MUST NOT sort with a locale collation, and MUST NOT sort by Unicode code point.
Collation disagrees with code-unit order on ordinary names (`Z_tool` before `a_tool`; `resume`,
`rezume`, `résumé`). Code-point order agrees with it inside the Basic Multilingual Plane and
disagrees outside (U+1F600 sorts before U+E000 by code unit and after it by code point), which is a
defect that passes tests until a name with such a character arrives. The vectors hold both cases.

## 6. Canonical form

The sorted array is written as RFC 8785 (JSON Canonicalization Scheme) text:

* no whitespace; members of every object in the order of section 5.1; arrays in their own order;
* strings as ECMAScript's `JSON.stringify` writes them: `\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`,
  `\u00XX` (lowercase hex) for the other characters below U+0020, and every other character as
  itself in UTF-8, including U+007F, U+2028 and U+2029;
* numbers as ECMAScript's `Number.prototype.toString` writes the double: `1` for `1.0`, `0` for
  `-0`, `100` for `1E2`, `0.5`, `1e+21`, `1e-7`, `0.000001`.

Two consequences, stated plainly:

* Two integers that round to the same double (`9007199254740993` and `9007199254740992`) give the
  same digest. A change between them does not move it.
* A literal with no double (`1e400`) cannot be written. A set that holds one in a contract member
  has no digest (`TSD-NUMBER`).

A string that holds a surrogate code unit without its pair cannot be written as UTF-8 and RFC 8785
makes it an error. A set that holds one in a contract member has no digest (`TSD-TEXT`).

## 7. The contract digest

The **contract digest** is SHA-256 over the UTF-8 bytes of the canonical text of the sorted array.

Its text form is the Subresource Integrity form, `sha256-` followed by the standard base64 of the
32 bytes with padding:

    sha256-T1PNoYwrqgwDVLtfmj7L5e0Sq02OEbqHPC8RFhICuUU=

(the digest of the empty set). A system that writes digests as `sha256:` and lowercase hex MAY
write the same 32 bytes that way; the two forms name the same digest:

    sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

A producer SHOULD publish, with a digest, the identifier `mcp-tool-set-digest/1`, so that a later
version is not mistaken for this one.

## 8. The extras digest

1. For each tool, its *extras* are the members it carries whose names are not `name`,
   `description`, `inputSchema` or `outputSchema`. A member with one of those four names is a
   contract member whatever value it holds: a `description` that is a number is read as absent by
   section 4 and is not an extra.
2. The **extras object** is `{"tools": {<name>: <extras>, …}}`, with one member for every tool
   that has at least one extra and no member for a tool that has none.
3. The **extras digest** is SHA-256 over the UTF-8 bytes of the RFC 8785 text of the extras object
   (section 6), in the text form of section 7.
4. When no tool has an extra, the set has **no extras digest**. That is a state like any other: it
   is written as JSON `null` (or left out), and it equals itself and differs from every digest.
5. When two tools share a name and both have extras, an object keyed by name cannot hold both, and
   the extras digest cannot be computed (`TSD-NAME`). When only one of them has extras, the object
   holds that one.
6. `TSD-NUMBER` and `TSD-TEXT` (section 10) apply to the extras as they apply to contract members,
   and separately: a set can have a contract digest and no computable extras digest, and the
   reverse.

For the one-tool list

    [{"name": "read_file", "title": "Read file", "description": "Read a file from disk.",
      "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
      "annotations": {"readOnlyHint": true}}]

the extras object is `{"tools":{"read_file":{"annotations":{"readOnlyHint":true},"title":"Read file"}}}`,
the extras digest `sha256-Kmdz0r/Y+YnXALUVpJTXG8TUbKQhoFKQ7CeEpIw+1Oc=` and the contract digest
`sha256-pUO5TdOtj4yR/mh2VDcu4y6axwVix4xgwST6cFkdd3g=`.

### 8.1 The bounded form in use

The two public records that publish an extras digest today (Appendix A) compute it with limits
that suit storing the extras, not only hashing them:

* a tool whose extras exceed 16,384 bytes is left out of `tools` and named, with its size, in a
  member `oversized`; once the members of `tools` add up to 262,144 bytes the remaining names are
  listed in a member `omitted`;
* NUL and unpaired surrogates in strings become U+FFFD, and a value nested deeper than 12 levels
  is replaced by the string `"…"`;
* an entry that is not a tool is passed over, and of two tools with one name the one listed last
  is kept.

A digest in that form equals the digest of this section whenever none of these applies, which is
the ordinary case. Where one applies the two differ, and the bounded form gives a digest where
this section gives none. A producer that applies the limits SHOULD say so beside the digest.
Whether the limits belong in the definition is an open question (Appendix B).

## 9. Per-tool digests (optional)

The contract digest of one tool is SHA-256 over the canonical text of its contract entry alone,
and its extras digest SHA-256 over the canonical text of its extras, each written as lowercase hex.
They say which tool changed when a set's digest moved. They are derived from the same values and
add no rule. For the tool of section 8 they are `73a730ee6b28fe0524038cd5082e673a108617d258153d44daafb2aa8eeef1f6`
and `b08036e71687b7855244656f049eec719c13c214eb9575731f118331e565cb3c`.

## 10. When there is no digest

| Code | When | Which digest |
|---|---|---|
| `TSD-TOOL` | an element of the array is not a JSON object, or has no non-empty string `name` | both |
| `TSD-NUMBER` | a member holds a number with no IEEE 754 double | the digest that covers that member |
| `TSD-TEXT` | a member holds a string, or a member name, with an unpaired surrogate | the digest that covers that member |
| `TSD-NAME` | two tools share a name and both have extras | the extras digest |

A producer that meets one of these MUST NOT publish that digest for the set and SHOULD publish the
code, with the tool's name when it has one. It MUST NOT skip the tool, repair the value or digest
the rest. A comparison with a set whose digest could not be computed has no result; it is not a
change.

An extra never takes the contract digest away: whatever a tool's `title` or `_meta` holds, the
contract digest is computed from the contract members only.

## 11. Comparing

* Equal contract digests: the two lists had the same tools with the same names, descriptions and
  schemas.
* Different contract digests: at least one contract member of one tool differs, or a tool is in
  one list and not in the other.
* Equal contract digests and different extras digests (or one absent): only extras differ.

A digest is comparable only with a digest of a list read under like conditions. A producer SHOULD
record with it: when the list was read; the endpoint or the package and version; the protocol
version it asked for, and whether it sent the `MCP-Protocol-Version` header; whether the list was
paged and how many pages; and whether the request was authorised. When two public records
of the same servers were compared on one day, two of the causes of different digests were of this
kind: a reader that stopped at the first page, and a reader whose missing protocol header made
servers answer in an older protocol version, without `outputSchema`.

## 12. Security considerations

* **Definitions, not behaviour.** A server can keep every definition and change what a tool does.
  The digests cannot see that.
* **First sight.** A digest shows change. A list that was hostile when first read has nothing
  earlier to differ from.
* **Extras decide things too.** `annotations` such as `readOnlyHint` and `destructiveHint` decide
  in some clients whether a user is asked before a call. They are not contract members, so a flip
  moves the extras digest and not the contract digest. A client that acts on extras compares both.
* **Wrongly typed contract members.** A `description` that is not a string and an `inputSchema`
  that is not an object are read as absent (section 4) and are not extras (section 8). A change
  from one such value to another moves neither digest.
* **Per-caller lists.** A server can serve one list to an observer and another to a victim. A
  digest held by a public record says what the record was served. Comparing a client's own digest
  with it is the check; trusting the record's digest in place of one's own is not.
* **A digest is not a signature.** It says two lists are the same, not who published either.
* **Size.** A producer SHOULD bound the size of a list and the depth of nesting it accepts before
  parsing.

## 13. Conformance

An implementation conforms when, for every vector in [`vectors/vectors.json`](vectors/vectors.json),
it produces the vector's contract digest, extras digest and canonical texts, reports no extras
digest where the vector has `null`, and reports that a digest cannot be computed where the vector
says so. The file holds 68 vectors, among them the orderings, number forms and strings of
sections 5 and 6, and pairs marked as equal or different.

Three reference implementations with no dependencies are in
[`implementations/`](implementations/): Python, JavaScript and Go. [`scripts/check.sh`](scripts/check.sh)
runs them over the vectors.

## Appendix A. Digests in use

Named for comparison. None of these projects has reviewed this text.

**The same contract digest.** The contract digest of this document is what these compute:

| Where | Name there | Since |
|---|---|---|
| HISTOR, a public log of MCP tool definitions | tool-set digest of MTL/1.1, section 5 | 2026-10-31 (1.1) |
| WARDEN, an MCP firewall | `mtlToolSetDigest` (`contractDigest`) | follows MTL/1.1 |
| CrawlCheck, [mcp-lockfile](https://crawlcheck.io/spec/mcp-lockfile) | `jcs_v1.tools_sha256` | 2026-11-07 |

Checked for this draft on 2026-11-12: HISTOR's and WARDEN's code, each run over the 68 vectors,
gives the contract digest and the refusals of every one (`scripts/cross_check_histor.py`,
`scripts/cross_check_warden.mjs`); and the reference implementation reproduces the five values
printed in CrawlCheck's specification as read that day: the empty list, and for the one-tool list
of section 8 its `tools_sha256`, its `extras_sha256` and the per-tool `contract` and `extras`. In
the MCP Registry's issue 82, CrawlCheck's author reported on 2026-11-07 that this digest, computed
from his own reads of 30 registry servers, equalled HISTOR's published one on all 30. A daily
comparison of HISTOR's and CrawlCheck's digests of the same servers is published at
<https://histor.modelmarket.dev/datasets/peers/crawlcheck/>.

**The extras digest.** HISTOR (`toolExtrasDigest`) and CrawlCheck (`jcs_v1.extras_sha256`, since
2026-11-07) publish the extras digest in the bounded form of section 8.1; CrawlCheck's author
reported equal values on the same 30 servers. CrawlCheck writes the extras object as RFC 8785.
HISTOR writes it with a serialiser that differs from RFC 8785 in three narrow cases, which that
report also names: fractions and integral floats such as `1.0`, integers beyond 2^53, and member
names outside the Basic Multilingual Plane (sorted by code point). `scripts/cross_check_histor.py`
runs HISTOR's code over the vectors: of 68, the extras digest agrees on 55 and differs on 13, each of
them one of those three cases or one of the limits of section 8.1. HISTOR's code since 2026-11-12 can
also write the RFC 8785 form (its `rfc8785` extras scheme) and move every stored value to it in one
step; under that scheme it agrees on 58 and differs on the 10 limits of section 8.1. Its public log
still publishes the first form until CrawlCheck, which reads those values daily, has agreed a date.

**Other constructions.** These cover other members or serialise differently, and give other
values for the same list:

* AgentAvow `agentavow.mcp-tool-definition.v1`: per tool, `name`, `title`, `description`,
  `inputSchema`, `outputSchema`, `annotations`, absent and null members omitted.
* heldfast lock file: per tool, `name`, `title`, `description`, `input_schema`, `annotations`,
  `output_schema`, `icons`; RFC 8785, hex.
* Vercel AI SDK `fingerprintTools`: per tool, the description, the input schema as the MCP client
  adapts it, and the title.
* draft-sharif-mcps-secure-mcp: a signature over a JCS object of name, description and input schema.
* In the MCP specification repository: SEP-1766 (digest-pinned tool versioning) and the discussion
  under issue 3452, where a digest over whole tool objects with RFC 8785 and published vectors was
  asked for.
* In the MCP Registry repository: issue 82, the tracker for fingerprints of a server's tool
  surface, where the maintainers listed "canonicalization rules, treatment of annotations and
  dynamic/auth-dependent tools, and client verification semantics" as what a design still needs.

## Appendix B. Open questions

1. The limits of section 8.1: should the definition keep the extras digest total and unbounded, as
   section 8 has it, or take the limits in?
2. Two tools with one name that both have extras: no digest (section 8), or a rule that orders
   them?
3. Should a producer be required to refuse repeated member names when its parser can see them?
4. Should the server's `instructions` and `serverInfo` have a digest of their own? A model reads
   them too, and they are outside the tool set.
5. A `_meta` key or a registry field under which a publisher or a registry states the digests it
   expects, and how a client should treat a difference.

## Change log

* 2026-11-12: first draft.
