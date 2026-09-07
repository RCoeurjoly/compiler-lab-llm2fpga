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

The model weights remain immutable BRAM initialization data. The JTAG bridge
has been linted with Verilator in `BSCAN_SIM` mode, and the production
generated SV still passes Calyx compilation and the focused lowering tests.

This is not yet a board-acceptance result. The generated kernel still uses the
authenticated frozen prompt memory internally; the CSR prompt shadow is not
yet wired into the compiler schedule. A follow-up change must connect the four
CSR prompt words to the generated prompt-loading path before producing a
bitstream or claiming board inference.
