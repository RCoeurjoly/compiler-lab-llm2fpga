# Calyx Memref View And Port Blocker

The direct-Linalg no-handshake TinyStories path currently reaches Calyx with
static memref view operations and ranked top-level memory ports. CIRCT Calyx
lowering rejects or crashes on those shapes before producing Calyx.

`ranked-port.mlir` shows that top-level memrefs must be scalar or
one-dimensional:

```text
input memory dimension must be empty or one
```

`reinterpret-cast.mlir` shows that a static `memref.reinterpret_cast` view from
a one-dimensional memref is not accepted by Calyx lowering.

`flat-port-no-view.mlir` is the equivalent accepted shape: one-dimensional port
and direct one-dimensional load.

Do not fix this with textual MLIR rewriting. Acceptable fixes are official MLIR
or CIRCT pass choices, a dialect route that avoids these view operations, or a
checked-in MLIR pass that rewrites the view users into Calyx-compatible
one-dimensional loads/stores.
