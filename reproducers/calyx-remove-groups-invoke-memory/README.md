# Calyx `remove-groups` Invoke/Memory Reproducer

This attempts to isolate the assertion seen when the generated integer-core
pattern is passed through:

```text
circt-opt --calyx-remove-groups
```

The full pattern has a top-level wrapper with external memories and an invoke
into an inner component using memory reference bindings. If this reduced case
fails the same way, it is the preferred target for a CIRCT issue or a real
CIRCT pass workaround.

Current observed failure:

```text
Assertion `BaseT::wrapped() != End && "Cannot dereference end iterator!"' failed.
```

Direct `--lower-calyx-to-hw` on the same input still reports the separate
`calyx.seq_mem` legalization failure.

The memory-free reproducer in `reproducers/calyx-remove-groups-invoke-ref/`
shows that the assertion is caused by `calyx.invoke` with reference-cell
bindings, not by memory ports specifically.
