---
status: accepted
supersedes: ADR-0002
---

# Complete the compiler-guided on-chip path before DDR3 integration

The project will first complete the existing Representative Core fast loop and
the full TinyStories-1M compiler-guided FPGA inference path using on-chip
memory. This supersedes the DDR3-first ordering in ADR 0002 because integrated
UberDDR3 remains unreliable and would obscure compiler and accelerator
validation. DDR3 integration, reliability improvements, and support for models
that exceed BRAM capacity remain later work.
