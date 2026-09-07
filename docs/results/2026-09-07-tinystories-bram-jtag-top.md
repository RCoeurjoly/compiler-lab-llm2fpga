# TinyStories-1M BRAM/JTAG top integration checkpoint

This checkpoint replaces the autonomous timing shell with a board-facing
control boundary. The generated production `main` component now exposes:

| Signal | Direction | Meaning |
| --- | --- | --- |
| `clk`, `reset`, `start`, `valid` | input | compiler-kernel control |
| `token_index` | input | selects token slot 0 or 1 |
| `token_id` | output | selected committed token |
| `done` | output | completion of the two-token run |

`rtl/tinystories_1m_jtag_csr.sv` defines the YPCB JTAG CSR transaction:

- command `1`: write one prompt word (`command[5:4]`, `command[15:0]`);
- command `2`: reset the run state and start the kernel;
- command `3`: read status;
- command `4`: select/read token slot (`command[0]`);
- command `5`: pulse kernel reset.

The four prompt words are now driven from the CSR shadow registers into the
generated prompt-loading schedule. The board therefore loads the prompt before
the start command; no host-side token or intermediate-state feedback is used.

The model weights remain immutable BRAM initialization data. The JTAG bridge
has been linted with Verilator in `BSCAN_SIM` mode, and the production
generated SV still passes Calyx compilation and the focused lowering tests.

This is not yet a board-acceptance result. A real YPCB bitstream, timing report,
and three cold-start JTAG runs are still required before claiming board
inference. The bounded generated-SV execution was timeboxed at 90 seconds
without reaching completion, and the first full-top Yosys attempt did not
produce a report within the available synthesis budget. These are integration
blockers, not evidence of board inference or timing closure.
