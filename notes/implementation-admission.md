# Binding a call to an admitted implementation: a three-case fixture

Note of 2026-11-24 · not part of `mcp-tool-set-digest/1` · status: proposal for discussion

The tool-set digests say which declaration a party saw. Section 11.1 of the [specification](../SPEC.md#111-profiles-and-approval)
ties an approval to that declaration, and the call record ties the approval to one request. Neither says which local
implementation receives the request.

The question was raised by Andrii Akhtanin (Radiolaria) on the agentproto list on 2026-11-24. The declaration and the
request payload can stay the same while a different implementation, admitted on its own terms, runs under the
original authorization. This note defines a small signed object that names the admitted implementation. It also
defines three cases a deployment has to get right. The execution-side check these cases test exists today in Radiolaria's N01 test (references below).
This repository adds the declaration side.

## The signed object

```json
{
  "binding": "implementation-admission/0",
  "tool_set": {
    "profile": "mcp-tool-set-digest/1",
    "contract": "sha256-...",
    "extras": "sha256-..."
  },
  "call": {"tool": "read_file", "arguments": "sha256-..."},
  "implementation_admission": "..."
}
```

| Member | Value |
|---|---|
| `binding` | the version of this object; `implementation-admission/0` while this note is a proposal |
| `tool_set` | both digests of the declaration the authorizer approved, under the profile named. The profile fixes the covered members: the contract members of section 7 and every other member under section 8, as section 11.1 asks a signed record to state. `extras` is `null` for a verified absence of extras (section 8.4). A set with no digest (section 10) cannot be bound |
| `call.tool` | the name of the tool called |
| `call.arguments` | `sha256-` and the base64 SHA-256 of the RFC 8785 text of the call's `arguments` object |
| `implementation_admission` | the execution authority's reference to the admission record of the implementation this call may run. Open question below |

The authorizer signs the UTF-8 bytes of the RFC 8785 text of the whole object. The signature scheme and key are the
deployment's. Where the object sits inside a record format (for example a TRAIL Action Record) is for that format to
define. This note defines only the object.

## The check

The execution authority is the component that dispatches the call to an implementation. Before dispatch, it:

1. verifies the signature;
2. resolves `implementation_admission` in its own catalogue;
3. confirms that the admission is for the implementation selected for this invocation;
4. recomputes `call.arguments` from the actual arguments;
5. refuses on any mismatch. A refused call starts no executor.

The tool-set digests are checked earlier, when the declaration is observed (section 11.1). This check is about who
runs the call.

## Three cases

Each case starts from its own fixture state. If one state is reused, A's completed effect can rightly prevent a
later attempt and hide the check under test. The declaration and the arguments are byte-identical in all three cases,
so `tool_set` and `call` are equal everywhere. Only the admission differs.

| Case | Signed object names | Invocation runs | Expected |
|---|---|---|---|
| 1 | A's admission | A | executes |
| 2 | A's admission | B, with its own valid admission and a structurally valid invocation | refused before dispatch, zero executor starts |
| 3 | B's admission | B | executes |

Case 3 shows that case 2 refused because of the binding, and not because it refuses B outright.

In Radiolaria's reference, case 2 is the `new_code` variant of N01. The structural validation of the invocation passes.
`execute_bound_effect_v01` then refuses with `capability_invocation_candidate_binding`, because the admission
snapshot is not the `execution_source` the authorized action retained. Commit `cf4840cfde1d64db1a208502c21aa3e8bfbfa716`:

- [the admission snapshot](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2140)
- [the check](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2787)
- [the N01 test](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/tests/test_action_packet_portability_v01.py#L300)

We have read that code but have not run it.

## Worked example

The declaration is the `read_file` tool from the README, and the arguments are `{"path": "/srv/report.txt"}`.
`admission:A` and `admission:B` stand for two admission references. Run
[`implementation_admission_example.py`](implementation_admission_example.py) (Python 3, standard library and the
reference implementation in this repository):

```
$ python3 notes/implementation_admission_example.py
A: {"binding":"implementation-admission/0","call":{"arguments":"sha256-nejYlDOnw0dbmVKNrRqzd95PJQldmWqMN9nGxG7sU7k=","tool":"read_file"},"implementation_admission":"admission:A","tool_set":{"contract":"sha256-pUO5TdOtj4yR/mh2VDcu4y6axwVix4xgwST6cFkdd3g=","extras":"sha256-Kmdz0r/Y+YnXALUVpJTXG8TUbKQhoFKQ7CeEpIw+1Oc=","profile":"mcp-tool-set-digest/1"}}
A sha256: sha256-2HylUAixNEALA0CFpYEiqPB68cPqPg87gAeetbaCB8U=
B: {"binding":"implementation-admission/0","call":{"arguments":"sha256-nejYlDOnw0dbmVKNrRqzd95PJQldmWqMN9nGxG7sU7k=","tool":"read_file"},"implementation_admission":"admission:B","tool_set":{"contract":"sha256-pUO5TdOtj4yR/mh2VDcu4y6axwVix4xgwST6cFkdd3g=","extras":"sha256-Kmdz0r/Y+YnXALUVpJTXG8TUbKQhoFKQ7CeEpIw+1Oc=","profile":"mcp-tool-set-digest/1"}}
B sha256: sha256-pLoWZgVatqt2EYbKtGyUYI05gYsdC1XSt65Hl+EznfA=
```

The two objects differ only in `implementation_admission`, so the bytes A's authorization signs are not the bytes B
needs. `scripts/check.sh` checks that this output is what the script prints.

## Open question: what the reference names

A local admission id such as N01's `admission_id` can be resolved only by the Host that issued it. A verifier
elsewhere can confirm that the signed reference equals the one the execution record names. It cannot tell what was
admitted. N01's admission snapshot already carries the definition, each code source with its `source_sha256`, the
input and output contracts, the implementation reference, the catalogue revision and the Host. A digest of that
snapshot would let anyone who holds the snapshot check the reference without the Host's catalogue. Whether
`implementation_admission` should be that digest, the local id, or both is not settled here.

Not covered: what the implementation does once it runs (a digest of definitions or of code cannot see that), and
revocation of an admission.
