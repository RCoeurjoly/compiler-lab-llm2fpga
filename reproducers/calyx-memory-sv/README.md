# Calyx Memory SV Reproducer

This isolates the direct Calyx-to-HW memory blocker independently of
`calyx.seq_mem`. The input uses the documented `calyx.memory` result order from
the CIRCT Calyx op definition:

```text
addr0, write_data, write_en, clk, read_data, done
```

Current observed failure:

```text
'calyx.memory' op couldn't convert to core primitive
```

Removing `{external = true}` does not change the failure. This means the
current direct Calyx-to-HW path does not lower Calyx memories at all, not only
external memories or sequential-read memories.
