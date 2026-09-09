# First-token completion/status race

The JTAG inference checker now permits one zero response during inference
status polling, then requires another valid status within the original
deadline. Zero is not treated as completion. A second zero or any other
unexpected status fails. Prompt loading/readback, initialization checks,
exact done status, and exact reference-token comparison remain mandatory.
No reset or START is repeated, and every transaction remains in the receipt.
`transient_zero_status_reads` records whether the re-read was used.

## Evidence

The unchanged CSR RTL clears `response_word` when `core_done` is asserted.
That event can occur between a status command's UPDATE and the next CAPTURE.
The second original full-model board attempt failed at 3.138 seconds with
`unexpected inference status 0000000000000000`. Subsequent reads without a TAP
reset or another START observed done status `2c00000000001d1e` and token 27959.
This was still an incorrect inference, not a success: the expected token is 11.

Local receipts are preserved in the ignored
`result-compiler-first-token-failed-20260909/` directory as
`compiler-top-packed-inference-run2.json` and
`compiler-top-packed-completed-state-run2.json`.

The regression injects that completion-time response at the external JTAG
boundary while exercising the real checker. Before the fix, the successful
token case stopped at the zero status. After the fix, all 12 inference/USER1
tests pass, including rejection of repeated zero, other invalid status,
incorrect prompt, wrong token after the transient, and busy timeout.

```sh
nix develop . -c python -m unittest \
  tests.test_tinystories_first_token_jtag tests.test_tinystories_user1_check -v
```

This is a host-checker repair only. It does not modify RTL, JTAG transaction
encoding, the clock, or the running physical build, and proves neither corrected board
inference nor timing qualification. Developed with LLM assistance.
