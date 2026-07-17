# Full V=6 RC SV equivalence-interface blocker

The completed candidate SV is not yet a usable PyTorch-versus-SV testbench
target.

Observed from the generated artifact:

- `main` exposes only `clk`, `reset`, `go`, and `done`.
- `main_1` exposes the generated memory-service ports, but no named logits or
  token-ID output.
- The packed RC image is keyed by exported-program tensor names, while the
  generated Calyx/SV interface is keyed by compiler-generated `mem_N` names.
  No checked-in mapping connects the two namespaces.
- The generated artifact therefore does not yet define how a testbench should
  load the packed image or identify the six final logits.

Artifact provenance:

- SV SHA-256: `88474a01400fc1c7f4e098bdc72f7e92e16df96ac0d72fb6bd5a2df859c7127e`
- Futil SHA-256: `55a706fab9349bb91f99df2bd31744db17cc94b5834fcb89bc646ce213f26ceb`
- SV size: 9,955,404 bytes

This is an interface/observability blocker, not an equivalence failure. A
`done`-only smoke test would not satisfy the equivalence contract. The next
implementation must either add an explicit test wrapper with a stable input,
six-logit, and token-ID contract, or produce a deterministic manifest mapping
packed-image segments to the generated memory ports and designate the output
memory. Only then can the SV simulator compare all six logits and argmax token
ID against the PyTorch oracle.
