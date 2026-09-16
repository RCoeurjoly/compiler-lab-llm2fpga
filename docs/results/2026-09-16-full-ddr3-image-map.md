# TinyStories-1M full DDR3 image map

The canonical compiler image directory
`result-compiler-top-30mhz-20260908` contains 240 immutable tensor files. The
new `scripts/analysis/build_ddr3_model_image_manifest.py` assigns each file a
16-byte-aligned byte range in lexical filename order, preserving each hex
element little-endian. It records source and payload hashes, element widths,
padding, and line counts; it does not alter tensor values or the validated
UberDDR3 profile.

The generated map is
`artifacts/diagnostics/tinystories-1m-ddr3-model-image-manifest.json`:

- 240 tensors
- 4,136,720 payload/padded image bytes
- 258,545 16-byte DDR3 lines
- packed image SHA-256
  `e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593`
- manifest content hash
  `1891a310e31817550cb85005b3e08de4159c3a392ba5ed4776b342d03fd12f98`
- serialized manifest SHA-256
  `c511cd6010e9d87133bf1a134d7ffe3f13bb8459b62d8e4be2c5225cd3852375`

The packed binary is emitted by `--image-output` (the working copy is kept in
`/tmp/tinystories-1m-ddr3-model-image.bin` for transfer experiments). Running
the generator twice produced identical serialized manifests before the image
hash field was added, and the generator's canonical map is deterministic. This is
the address-map contract used by the loader. Physical validation is recorded
in `artifacts/diagnostics/2026-09-16-ddr3-pcie-full-image-3-cold-starts.json`:
all 258,545 lines were streamed through PCIe and the complete readback matched
the packed-image hash on all three cold starts.
