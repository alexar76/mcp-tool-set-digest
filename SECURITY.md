# Security

This repository defines how to compute a digest of the tools an MCP server lists. A defect here is
one of these:

- two tool lists that mean different things get the same digest under the rules of `SPEC.md`;
- an input on which the reference implementations disagree with each other or with `vectors/`;
- an implementation that crashes, hangs or uses unbounded memory on some input.

Report it by email to **qwezzy721@gmail.com**, with the input that shows it. Please do not open a
public issue first for the first kind: clients may be pinning digests computed by these rules.
We answer within 48 hours. A confirmed defect gets a test vector, a fix in all three
implementations and a note in `SPEC.md`.

A digest says that a tool list is unchanged; it does not say that the tools are safe. Reports that
a server's tools are malicious belong with that server.
