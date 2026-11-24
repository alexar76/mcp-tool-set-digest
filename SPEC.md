# MCP tool-set digest, version 1

Identifier: `mcp-tool-set-digest/1` · Editors' draft, 2026-11-24 · Text: CC BY 4.0 · Code and vectors: Apache-2.0 OR MIT

Editors: Aleksandr Artamokhov (HISTOR), Emmanuel Orta (CrawlCheck)

**Status.** A draft for discussion. It documents the contract digest used by HISTOR and WARDEN,
and the definition CrawlCheck implements from its own code (Appendix A). The vectors let another
implementation check the same rules. This is an editors' draft without endorsement by the MCP
project or any other project named in it.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be read as in RFC 2119 and RFC 8174.

## 1. What it is for

An MCP server tells a client which tools it has in the result of `tools/list`. A model reads the
names, descriptions and schemas in that list and acts on them, and a server can serve a different
list tomorrow. To notice that, a client, a gateway, a registry or an outside observer keeps a
digest of the list and compares.

Two parties can only compare digests they compute the same way. Today each tool hashes the list in
its own way: different members, different order, different number formatting. This document fixes
one way, as two digests:

* the **contract digest**, over the tool's name, description, input schema and output schema as
  defined in section 4;
* the **extras digest**, over everything else a tool carries: its title, annotations, icons,
  `_meta` and vendor members.

When both parts are available, they cover the normalized contract entries and the extras as
defined in sections 4 and 8. A change confined to annotations, titles or prices in `_meta` moves
the extras digest.

With them:

* a client can compare the fields it approved with the set it is offered now, subject to the
  coverage rules in section 11.1;
* two clients, or a client and a public record, can compare the sets they observed by exchanging
  digest values and their profiles;
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
   they were read. A producer MUST NOT digest part of a list (`TSD-PAGE`, section 10). A wrapper
   containing `nextCursor` is insufficient input, even if the cursor is an empty string. A bare
   array or a final page cannot show whether earlier pages were omitted. The caller is responsible
   for gathering them before hashing.
   A reader takes the array in one of three forms: the array itself; a `tools/list` result object,
   from its `tools` member; or a JSON-RPC response, from the `tools` member of its `result`. An
   object read as one of these that holds both a `tools` member and a `result` member is neither
   form: which list it means is not clear, so the set has no digest (`TSD-TOOL`), whatever else it
   holds. Two `tools` members in one object are a repeated name (item 4): the last one counts.
2. A list is what one server answered to one request under one authorisation. A server may list
   other tools to another user, scope or protocol version; those are other tool sets. A digest
   says nothing about a list the producer did not read.
3. The JSON text is parsed into values. Every number is the IEEE 754 double nearest to its
   literal, ties to even: what ECMAScript's `JSON.parse` yields and what a correctly rounding
   parser yields in any language. A parser that keeps large integers exact MUST convert an integer
   outside ±(2^53 − 1) to its nearest double before use (section 6).
4. When an object repeats a member name, the last one counts, which is what `JSON.parse`, Python's
   `json` and Go's `encoding/json` do. A producer whose parser reports repeated names SHOULD say so
   beside the digest. The `repeated-member-*` vectors pin the rule in a tool, inside `inputSchema`,
   in a member outside the contract and for a name written once with an escape; the last value also
   decides validity (an empty `name` last gives `TSD-TOOL`, an empty `name` first does not).
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
* A literal with no double (`1e400`) cannot be written. A set that holds one in a value the
  contract entry carries has no digest (`TSD-NUMBER`). A `description` that is not a string and an
  `inputSchema` that is not an object are replaced by their defaults (section 4), so `1e400` there
  reaches neither digest.

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
   the extras digest cannot be computed (`TSD-NAME`). A result that depended on listing order would
   not be a digest of the set. A producer SHOULD report the shared name: two tools a client cannot
   tell apart by name are a finding about the server on their own. When only one of them has extras,
   the object holds that one.
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

HISTOR's public extras digest (Appendix A) uses the following limits when preparing extras for
storage and hashing:

* a tool whose extras exceed 16,384 bytes is left out of `tools` and named, with its size, in a
  member `oversized`; once the members of `tools` add up to 262,144 bytes the remaining names are
  listed in a member `omitted`;
* NUL and unpaired surrogates in strings become U+FFFD, a number that overflows a double becomes
  `null`, and a value nested deeper than 12 levels is replaced by the string `"…"`;
* an entry that is not a tool is passed over, and of two tools with one name the one listed last
  is kept.

These limits are a way of storing extras, not part of the definition: the extras digest is
defined on what the server sent. A value computed under them is not the extras digest of section 8,
even where the two agree. A bounded digest written as RFC 8785 agrees with section 8 when the
limits leave the same extras object intact; the historical serializer also has encoding differences
(Appendix A). A producer that publishes a bounded value MUST label it with the profile it used and
MUST NOT present it as the extras digest, and SHOULD report any omissions or substitutions beside
it. CrawlCheck's `jcs_v1` is a bounded form of this kind.

## 9. Per-tool digests (optional)

The contract digest of one tool is SHA-256 over the canonical text of its contract entry alone,
and its extras digest SHA-256 over the canonical text of its extras, each written as lowercase hex.
They say which tool changed when a set's digest moved. They are derived from the same values and
add no rule. For the tool of section 8 they are `73a730ee6b28fe0524038cd5082e673a108617d258153d44daafb2aa8eeef1f6`
and `b08036e71687b7855244656f049eec719c13c214eb9575731f118331e565cb3c`.

## 10. When there is no digest

| Code | When | Which digest |
|---|---|---|
| `TSD-PAGE` | the complete tool list is unavailable, including a result that still carries `nextCursor` | both |
| `TSD-TOOL` | an element of the array is not a JSON object, or has no non-empty string `name`; or the input holds both `tools` and `result` (section 3) | both |
| `TSD-NUMBER` | a member holds a number with no IEEE 754 double | the digest that covers that member |
| `TSD-TEXT` | a member holds a string, or a member name, with an unpaired surrogate | the digest that covers that member |
| `TSD-NAME` | two tools share a name and both have extras | the extras digest |
| `TSD-DEPTH` | an array or object the digest covers is nested deeper than level 512 (section 12) | the digest that covers it |

A producer that meets one of these MUST NOT publish that digest for the set and SHOULD publish the
code, with the tool's name when it has one.

When more than one code applies to the same digest, a producer reports the first of `TSD-PAGE`,
`TSD-TOOL` and `TSD-NAME` that applies; these concern the set and can be found without writing any
value. `TSD-DEPTH` comes next: it too is found without writing a value. Between `TSD-NUMBER` and
`TSD-TEXT` either conforms, and the vectors hold no set where both
apply to one digest. A producer MAY report the other codes as well. Which code is reported does not
change a comparison (section 11). It MUST NOT skip the tool, repair the value or digest
the rest. A comparison with a set whose digest could not be computed has no result; it is not a
change.

Each digest is computed or refused on its own; a code for one digest does not take the other away.
An extra never takes the contract digest away: whatever a tool's `title` or `_meta` holds, the
contract digest is computed from the contract members only.

## 11. Comparing

* Equal contract digests: the two lists had the same normalized contract entries.
* Different contract digests: at least one contract member of one tool differs, or a tool is in
  one list and not in the other.
* Equal contract digests and different comparable extras digests, including verified absence of
  extras on one side: extras changed and the normalized contract stayed equal.

A digest is comparable only with a digest of a list read under like conditions. A producer SHOULD
record with it: when the list was read; the endpoint or the package and version; the protocol
version it asked for, and whether it sent the `MCP-Protocol-Version` header; whether the list was
paged and how many pages; and whether the request was authorised. When two public records
of the same servers were compared on one day, two of the causes of different digests were of this
kind: a reader that stopped at the first page, and a reader whose missing protocol header made
servers answer in an older protocol version, without `outputSchema`.

### 11.1 Profiles and approval

A digest profile identifies the input scope (one tool or a complete tool set), member selection,
rules for absent or malformed members, normalization and canonical encoding. A verifier SHOULD
compare the algorithm and profile for each digest component before comparing its value. For a
split digest, identify the contract and extras profiles separately. In particular, a label for
the RFC 8785 contract digest does not identify the extras encoding or its bounds.

Digest coverage depends on the decision. A claim about the normalized contract entries can use the
contract digest alone. Carrying forward an approval requires comparable evidence for every member
that influenced it, including whether a relevant member was absent. A control that uses
`annotations.readOnlyHint` or `annotations.destructiveHint` requires an annotation-inclusive
digest or a separate, complete extras comparison. A policy that approved the full declaration
requires coverage of the whole declaration at the precision it approved. Compute the current
digest from the declaration observed for that client and server context (section 3), then compare
it with the approved digest. Bind a call that relies on that approval to the observed declaration
used for the comparison.

For approval of an individual declaration, resolve the identity of that declaration. When several
entries share a name, section 8 groups their extras by name, leaving the association between an
extra and a specific contract entry ambiguous.

Treat the approval as unverifiable if a required profile is unknown or incompatible, a
declaration was unobserved or refused by its profile, or a bounded result leaves the required
members' coverage uncertain. Require a complete, comparable observation before carrying
approval forward. Record a verified absence of extras (section 8.4) separately from an
unobserved list or a list the profile could not digest. For a refusal, retain the profile and
its error code when available (section 10).

When a signed record uses these digests, include each component's kind, algorithm, value, profile
and covered member list in the signed scope, alongside the subject and observation context. For
an open-ended member set, state the selection rule, such as all tool members except the four
contract members, and include any coverage limits or omissions in the signed record. The
signature binds the digest to that scope. Keep the digest inputs defined by sections 7 and 8. A
construction that puts the profile identifier into the hashed bytes uses a different profile.

## 12. Security considerations

* **Definitions, not behaviour.** A server can keep every definition and change what a tool does.
  The digests cannot see that.
* **First sight.** A digest shows change. A list that was hostile when first read has nothing
  earlier to differ from.
* **Extras decide things too.** `annotations` such as `readOnlyHint` and `destructiveHint` decide
  in some clients whether a user is asked before a call. They are not contract members, so a flip
  moves the extras digest and leaves the contract digest equal. Section 11.1 states the coverage
  needed for approval.
* **Wrongly typed contract members.** A `description` that is not a string and an `inputSchema`
  that is not an object are read as absent (section 4) and are not extras (section 8). A change
  from one such value to another moves neither digest.
* **Per-caller lists.** A server can serve one list to an observer and another to a victim. A
  digest held by a public record says what the record was served. Comparing a client's own digest
  with it is the check; trusting the record's digest in place of one's own is not.
* **A digest is not a signature.** It says two lists are the same, not who published either.
* **Size.** A producer SHOULD bound the size of a list it accepts before parsing.
* **Depth.** Every array and object has a level: the tools array is level 1, a tool level 2, an array
  or object held by a member of a tool level 3, and each array or object inside it one more. Levels
  are counted from the tools array whatever wraps it (a `tools/list` result, a JSON-RPC response).
  A reader MUST accept every level up to 512. A digest that would cover an array or object at level
  513 or deeper cannot be computed (`TSD-DEPTH`); the other digest is computed as usual. A value the
  contract entry does not carry, such as a `description` that is not a string (section 4), is not
  counted. On deeper input a reader MUST NOT crash, stop on a resource limit or truncate; it need not
  build anything past level 512, and reading such an array or object as an empty one of the same
  kind changes no answer. The floor is fixed so that readers agree: a bound of each reader's own
  would give different answers on the same deep list.

## 13. Conformance

An implementation conforms when, for every vector in [`vectors/vectors.json`](vectors/vectors.json),
it produces the vector's contract digest, extras digest and canonical texts, reports no extras
digest where the vector has `null`, and reports that a digest cannot be computed where the vector
says so. The file holds 73 vectors, among them the orderings, number forms and strings of
sections 5 and 6, and pairs marked as equal or different.

Three reference implementations with no dependencies are in
[`implementations/`](implementations/): Python, JavaScript and Go. [`scripts/check.sh`](scripts/check.sh)
runs them over the vectors. CrawlCheck's SDKs implement it independently (Appendix A).

## Appendix A. Digests in use

Named for comparison. Apart from CrawlCheck, whose author co-edits this draft, none of these
projects has reviewed this text.

**The same contract digest.** The contract digest of this document is what these compute:

| Where | Name there | Since |
|---|---|---|
| HISTOR, a public log of MCP tool definitions | tool-set digest of MTL/1.1, section 5 | 2026-10-31 (1.1) |
| WARDEN, an MCP firewall | `mtlToolSetDigest` (`contractDigest`) | follows MTL/1.1 |
| CrawlCheck, [mcp-lockfile](https://crawlcheck.io/spec/mcp-lockfile) | `jcs_v1.tools_sha256` | 2026-11-07 |
| CrawlCheck SDKs and lockfile endpoint | `toolSetDigest` (JavaScript), `tool_set_digest` (Python), lockfile member `tool_set_digest` | 2026-11-13 |

Checked for this draft on 2026-11-13: HISTOR's and WARDEN's code, each run over the 73 vectors,
gives the contract digest and the refusals of every one (`scripts/cross_check_histor.py`,
`scripts/cross_check_warden.mjs`). The reference implementation reproduces the five values in
[CrawlCheck's lockfile examples](https://crawlcheck.io/spec/mcp-lockfile#jcs-v1), fetched directly on
2026-11-12: the empty-list contract digest and the set and per-tool contract and extras digests for
the `read_file` example in section 8. The five values cover these two inputs. They do not establish
agreement on the full vector suite.

**An independent implementation.** CrawlCheck's SDKs implement this definition, both digests and the
refusals, apart from its bounded `jcs_v1` (section 8.1): `sdk/src/tsd.js` and
`sdk-python/crawlcheck/tsd.py` in [emmanuelorta/crawlcheck-core](https://github.com/emmanuelorta/crawlcheck-core)
at commit 7568d46. Run over the vectors on 2026-11-13, both give the digests, canonical texts and
codes of all 70 vectors of the 2026-11-12 file. Of the three vectors added on 2026-11-13 for the
order of codes (section 10), they agree on the two with `TSD-NAME`; on
`lone-surrogate-before-bad-entry` they report `TSD-TEXT` for the contract digest where section 10
gives `TSD-TOOL`.
In [MCP Registry issue 82](https://github.com/modelcontextprotocol/registry/issues/82), CrawlCheck's
author reported on 2026-11-07 that the contract digest, computed from his own reads of 30 registry
servers, equalled HISTOR's published one on all 30. The daily comparison checks the contract digests
of the same servers and publishes the results at
<https://histor.modelmarket.dev/datasets/peers/crawlcheck/>.

**The extras digest.** In the 2026-11-07 follow-up on issue 82, CrawlCheck's author described using
the object from section 8 and reported equal values for HISTOR and CrawlCheck on the same 30
servers. The current lockfile page documents that object shape with size caps and orders tools by
Unicode code point when applying the caps. The shared example does not exercise differences in
encoding, ordering or bounds. The daily comparison's inputs carry only the contract digest.

HISTOR's deployed `toolExtrasDigest` uses the bounded form of section 8.1 and a serialiser that
differs from RFC 8785 for fractions and integral floats such as `1.0`, integers beyond 2^53, and member
names outside the Basic Multilingual Plane (sorted by code point). `scripts/cross_check_histor.py`
runs HISTOR's code over the vectors: of 92, the extras digest agrees on 72 and differs on 20, each of
them one of those three cases or one of the limits of section 8.1. HISTOR's code since 2026-11-12 can
also write the RFC 8785 form (its `rfc8785` extras scheme) and move every stored value to it in one
step; under that scheme it agrees on 75 and differs on the 17 vectors its limits of section 8.1
change. Its public log has published that form since 2026-11-13, when CrawlCheck's author agreed to
the change.

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

1. Should a producer be required to refuse repeated member names when its parser can see them?
2. Should the server's `instructions` and `serverInfo` have a digest of their own? A model reads
   them too, and they are outside the tool set.
3. A `_meta` key or a registry field under which a publisher or a registry states the digests it
   expects, and how a client should treat a difference.

## Change log

* 2026-11-24: section 10 says outright that each digest is computed or refused on its own, so a code
  for one digest does not take the other away. The table and the rule for extras already implied
  it. An implementer of the vectors whose runner returned one outcome for the pair, and so lost a
  computed contract digest wherever the extras side failed, suggested the sentence. No vector
  changed.
* 2026-11-23: section 3 names the three input forms, and an object that holds both `tools` and
  `result` gives `TSD-TOOL` (case 1 on issue #1, the wording agreed there with Emmanuel Orta and
  bcrypto0); two `tools` members fall under the repeated-name rule. Before, the three reference
  implementations took the top-level `tools` and ignored `result`; `scripts/check.sh` now checks the
  wrapper cases through all three. Section 6 says that `TSD-NUMBER` applies to a value the contract
  entry carries, which the references and the vectors already did.
* 2026-11-23: vectors (92). Seven from Emmanuel Orta's pull request #2: the
  depth edges of section 12 on each side, a 600-deep description that reaches neither digest, and
  `1e400` as a description (no code) and as an extra (`TSD-NUMBER` for the extras digest). Seven
  from bcrypto0 on issue #1 for repeated member names (section 3.4), with five vectors that write
  the same tools once so that six equal pairs tie them together. All agree with the three
  reference implementations, and the repeated-member ones with the values bcrypto0's reader gave.
* 2026-11-22: section 12 gains the depth rule and section 10 the code `TSD-DEPTH`, as proposed by
  Emmanuel Orta (CrawlCheck) on alexar76/mcp-tool-set-digest#1 after bcrypto0 reported that the text
  named no bound. The three reference implementations follow it (`scripts/check_depth.py`: the edges
  509/510 under `inputSchema.x`, 510/511 for an extra, 100,000 levels, wrapped inputs); before, the
  Python one crashed from about 330 levels, the JavaScript one at 100,000, and the Go one refused
  past 512 levels of the whole input, so a wrapper moved its edge. No vector changed.
* 2026-11-13: second editor (Emmanuel Orta, CrawlCheck). Two open questions settled with
  CrawlCheck: the limits of section 8.1 describe storage, and a bounded value is labelled and not
  presented as the extras digest; two tools with one name that both have extras give no extras
  digest, and the shared name SHOULD be reported. Section 10 orders the codes when several apply,
  a question CrawlCheck raised while implementing it; three vectors added for that (73).
  CrawlCheck's SDKs added to Appendix A.
* 2026-11-12: first draft.
