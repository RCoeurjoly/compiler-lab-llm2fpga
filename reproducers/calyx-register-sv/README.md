# Calyx Register SV Smoke Test

This is the smallest positive Calyx-to-SV shape currently used by the
no-handshake baseline. It contains only core Calyx control and register
primitives, with no memories.

The point is to distinguish a general Calyx-to-SV failure from the narrower
`calyx.seq_mem` lowering blocker isolated in `reproducers/calyx-seq-mem-sv/`.
