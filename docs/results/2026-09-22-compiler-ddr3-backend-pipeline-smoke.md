# Compiler DDR3 backend pipeline smoke

The exact regenerated compiler `main` was elaborated with the repository
backend, 240-port external-memory arbiter, and registered Wishbone boundary.
Verilator built and ran the combined design for 10,000 clock cycles. A
registered zero-data Wishbone responder observed 1,468 requests and 1,468
acknowledgements, with no protocol errors.

The generated source hash is
`373ae31e6b3843ea0cb82614bcdbc7321aa4dbc5388831341dceef0a46dd9ab9`.
The detailed receipt is
`artifacts/diagnostics/2026-09-22-compiler-ddr3-backend-pipeline-smoke.json`.

This is only a bounded interface smoke gate. It does not prove the first token,
the complete authenticated image, PCIe ingress, physical DDR3 behavior, timing
closure, or board inference. The earlier provenance-clean transaction-level
simulation remains the semantic evidence for first token `11`; this run checks
that the proposed registered boundary can carry compiler traffic without
request/response loss.
