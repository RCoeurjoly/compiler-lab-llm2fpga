# Supplemental Task 3n report — authenticated LayerNorm semantics

## Result

The LayerNorm evidence is now content-bound, but it does **not** select a
compiler profile.  The receipt authenticates the pinned `df1fc45` fixed Python
runtime, LayerNorm RTL, and iterative-divider RTL by revision, clean selected
path status, and SHA-256.  It records Q16.16 inputs/gamma/beta, epsilon 42950
in Q32.32, mean/variance order and widths, floor square-root plus
truncation-toward-zero division, affine right shift, no saturation, and the
runtime checkpoint shapes/dtypes/hashes for `block.ln_1.output` and
`block.ln_2.output`.

The profile remains fail-closed.  The executable reduction witness
`[-2^31, 2^31-1] * 32` makes the authenticated Python runtime raise
`ValueError: isqrt() argument must be nonnegative`, while an independent model
of the declared RTL widths yields unsigned Q32.32 variance
`4611686016279947206` and first normalized values `[-65536, 65536]`.  The
runtime squares/reduces in NumPy signed INT64; RTL retains 66-bit squares and a
72-bit serial sum before a different 64-bit variance assignment.

There is a separate affine-output conflict: with normalized values
`[-370727, 370727]`, gamma `INT32_MAX`, and beta zero, the runtime's int64
results are `[-12147982331, 12147982330]`, while signed 32-bit `out_y` wraps
to `[736919557, -736919558]`.  The existing checkpoints are authenticated
fixed-runtime data, not board checkpoints.  No full-domain bit-exact compiler
lowering may claim either authority until both conflicts are resolved and a
board-bound trace selects it.

## Files

- `scripts/comparison/authenticate_tinystories_1m_layernorm_semantics.py`
- `artifacts/reference/tinystories-1m-layernorm-semantics.json`
- `tests/test_tinystories_1m_layernorm_semantics.py`

## Verification

```text
XDG_CACHE_HOME=/tmp/task3n-nix-cache nix develop -c python -m unittest \
  discover -s tests -p 'test_tinystories_1m_layernorm_semantics.py' -v

Ran 5 tests ... OK
```

The suite re-derives the checked-in receipt, rejects a tampered Q/DQ profile,
checks receipt integrity, executes both concrete overflow witnesses, checks
the adverse width conflicts stay non-selectable, and executes a deterministic
content-bound runtime probe.  It does not copy reference code or RTL into
compiler output and changes no board transport.
