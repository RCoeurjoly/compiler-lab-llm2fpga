# Quantized RC Flat-SCF I/O Reproducer

This is a reduced ABI transcription of the exact fixed working model:

```text
tinystories-w8a8-rc-study-mask9-vocab6-width2
```

The source flat-SCF artifact was built through the registered direct
Linalg/no-Handshake path.  Its `flat.scf.mlir` SHA-256 is:

```text
2a2d0f15794833cb8af0fcdf168aef863e337f034750f7764c24da828d1525b1
```

The actual `@main` signature has 27 memref arguments.  The last two are
already the desired functional boundary:

```mlir
%arg25: memref<1x8xi64>
%arg26: memref<1x8x6xi8>
```

The full artifact ends with:

```mlir
memref.copy %reinterpret_cast_231, %arg26
    : memref<1x8x6xi8> to memref<1x8x6xi8>
return
```

It therefore has no scalar or tensor function result to materialize.  The
reproducer replaces the enormous compute body with an allocated source buffer
and the same caller-owned-output `memref.copy`; it is an ABI test, not a
replacement model or a functional equivalence fixture.

This settles only the flat-SCF boundary.  It does not claim that Calyx or
generated SystemVerilog preserves those buffers as observable top-level ports.
That question remains a separate audit after a real SV bundle exists.
