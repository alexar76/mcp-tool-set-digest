# Binding a call to an admitted implementation: a three-case fixture

Proposal for discussion · 2026-11-24, updated 2026-11-25 · companion to `mcp-tool-set-digest/1`

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
| `implementation_admission` | the reference to the admission record of the implementation authorized for this call. The N01 fixture uses the native `CapabilityAdmissionSnapshotV01.admission_id` |

The authorizer signs the UTF-8 bytes of the RFC 8785 text of the whole object. The signature scheme and key are the
deployment's. Where the object sits inside a record format (for example a TRAIL Action Record) is for that format to
define. This note defines only the object.

## The check

The execution authority is the component that dispatches the call to an implementation. Before dispatch, it:

1. verifies the signature on the binding;
2. resolves the selected admission in its own catalogue and refreshes the observed code;
3. checks that the signed reference matches the selected snapshot's ID and that the snapshot matches the
   `execution_source` retained by the authorized action;
4. matches `call.tool` to the tool being invoked and recomputes `call.arguments` from the actual arguments.

Any mismatch stops the call before dispatch. The tool-set digests are checked when the declaration is observed
(section 11.1). The signature and MCP fields above belong to the companion proposal. N01 exercises the native
admission and action binding at the execution boundary.

## Three cases

Each case starts from its own fixture state. If one state is reused, A's completed effect can rightly prevent a
later attempt and hide the check under test. Keep the external MCP declaration and application payload byte-identical
in all three cases, so `tool_set` and `call` are equal throughout. A's and B's authorizations differ in
`implementation_admission`.

| Case | Signed object names | Invocation runs | Expected |
|---|---|---|---|
| 1 | A's admission | A | executes |
| 2 | A's admission | B, with its own valid admission and a structurally valid invocation | refused before dispatch, zero executor starts |
| 3 | B's admission | B | executes |

Case 3 confirms that B is executable when the action authorizes B.

Case 2 maps to the `new_code` variant of Radiolaria's N01. The variant changes native `CapabilityDefinitionV01`
fields including `executor_ref` and `code_sha256s`, which changes its definition, implementation and admission
identities. The invocation passes structural validation under B's snapshot. The execution boundary refuses it with
`capability_invocation_candidate_binding` because A's action retained a different `execution_source`. Commit
`cf4840cfde1d64db1a208502c21aa3e8bfbfa716`:

- [the admission snapshot](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2140)
- [the check](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2787)
- [the N01 test](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/tests/test_action_packet_portability_v01.py#L300)

## Verifying the native admission reference

For the N01 fixture, carry the pinned native derivation profile and the complete
`CapabilityAdmissionSnapshotV01` for each implementation. That includes the full `definition`, ordered
`code_sources` (each with `public_symbol`, `source_utf8` and `source_sha256`), `input_contract_ref`,
`output_contract_ref`, `implementation_ref`, `catalogue_revision` and `host_instance_ref`, along with
the expected `admission_id`.

The N01 profile serializes every snapshot field except `admission_id` as ordered field/value pairs in
dataclass declaration order. Nested native records use the same rule, tuples become JSON arrays, and absent
values use `{"$hedgehog_absent":"ABSENT_V01"}`. The native encoder emits compact UTF-8 JSON with string
escaping as in `canonical_material_bytes_v01`. SHA-256 covers the following byte sequence:

```text
b"HEDGEHOG_KERNEL_V01\x00" || u32be(len(domain)) || domain || u64be(len(payload)) || payload
```

`domain` is the ASCII string `hedgehog.common_action.capability_admission.v01`. `payload` is the native
encoding above. Prepend `capability_admission:` to the lowercase hexadecimal digest. Use RFC 8785 for the
outer signed binding. The native digest uses its own profile.
[Native material and validation](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2239) · [native encoder](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/action_commit_packet_v02.py#L2700) · [hash envelope](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/integrity_replay_v01.py#L249)

A verifier holding the snapshot can recompute the ID and check the source hashes and internal references
without contacting the issuing Host. `validate_capability_admission_snapshot_v01` performs those checks.
The same code admitted under a different Host reference or catalogue revision has a different admission
ID. `implementation_ref` separately commits the code-source records.

Current authority stays with the executing Host, which checks the admission and the action before dispatch.
S08 exercises this distinction. It rejects a copy of an admitted object with `capability_not_trusted_admission`.
Genuine re-observation yields an equal snapshot and allows the authorized mock effect to complete.
[Snapshot validator](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/kernel/effect_firewall_v01.py#L2418) · [S08](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/tests/test_action_packet_portability_v01.py#L1049) · [Host refresh](https://gitlab.com/radiolaria/radiolaria-os/-/blob/cf4840cfde1d64db1a208502c21aa3e8bfbfa716/hedgehog/work_execution_host_v01.py#L312)

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

The fixture covers implementation identity and its binding to one authorized action. Runtime behavior and
admission revocation are outside its scope.
