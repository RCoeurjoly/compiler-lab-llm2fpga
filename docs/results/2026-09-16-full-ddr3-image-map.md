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
- manifest content hash
  `1912a2c7e90ade960d002ca2b89f209da68ae11826c750860771d791c30bfd2c`
- serialized manifest SHA-256
  `6a2ae8f352bb97a55d7025fa338e4d23c536bacfb06890ac4bc665d728ac40c4`

Running the generator twice produced identical serialized manifests. This is
the address-map contract for the forthcoming loader; it is not yet evidence
that the image has been transferred to physical DDR3. The next gate is to
stream these 258,545 lines through the existing transport and compare a full
readback hash across three cold starts.
