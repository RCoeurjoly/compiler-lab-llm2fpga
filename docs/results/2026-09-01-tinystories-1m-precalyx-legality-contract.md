# TinyStories-1M pre-Calyx legality census contract

## Result

The pre-Calyx checker now fails closed on the three operation classes exposed
by the reviewed exact TinyStories-1M normalized flat-SCF artifact. A fresh
census of the retained normalized output with SHA-256
`e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
reconstructed:

| Prohibited operation | Exact count | First location |
| --- | ---: | --- |
| `math.floor` | 1,376 | line 422, column 18 |
| `arith.negf` | 1,369 | line 460, column 18 |
| `math.absi` | 1,156 | line 848, column 16 |

The checker emitted no scanner diagnostics for that artifact and classified it
as `blocked`. This closes the former false-clean result. It does not alter the
separate authenticated zero count for the four registered memref blockers and
does not authorize Calyx.

The schema-v3 normalized report is byte-identical between measurement and
`--require-clean` modes. Its file SHA-256 is
`8c27b2419fd37434b360fd98b0fcdbc2b929767a9501f33ef05780c339c3e079`
and its embedded self-hash is
`ad16079fd1fccf83d837507b526048dce4c87e0fa5744b9293e48bdd9d4a732c`.

## Schema version 3

`scripts/pipeline/calyx_preflight_report.py` emits deterministic JSON with
exactly these fields:

```json
{
  "schema_version": 3,
  "status": "blocked",
  "prohibited_ops": {"math.floor": 1},
  "first_locations": {"math.floor": {"line": 1, "column": 6}},
  "scanner_diagnostics": [],
  "parser_validation": {
    "authorized_identity": {
      "canonical_path": "/nix/store/...-mlir-21.1.2/bin/mlir-opt",
      "sha256": "...",
      "version": "21.1.2"
    },
    "identity_status": "verified",
    "input_status": "accepted",
    "observed_identity": {
      "canonical_path": "/nix/store/...-mlir-21.1.2/bin/mlir-opt",
      "sha256": "...",
      "version_output": "LLVM ... LLVM version 21.1.2 ..."
    }
  },
  "sha256": "..."
}
```

Counts and first-location keys are sorted by decoded operation name. Locations
are one-based and identify the first source character of the operation token;
for generic syntax that character is the opening quote. Diagnostics retain
source order. `parser_validation` binds the Nix-authorized identity to the
canonical executable actually inspected and to the parse outcome. The
self-hash is SHA-256 over canonical compact JSON with sorted keys and the
`sha256` member omitted.

Schema v3 is required because parser identity is authorization evidence, not
ambient configuration. It necessarily changes the prior schema-v2 report
bytes and self-hashes; operation counts, first locations, and source artifact
hashes remain unchanged. The retained generic rendering is likewise
byte-identical between modes, with report file SHA-256
`1829037ebdbf41c15659233951adb41de544d8b074370dff1375659c68f9ba6a`
and self-hash
`5da0fc0e8844a8fa8db7c2d6292ba6cb0a10f722f76aa899a9364fe16016ad7c`.

`status` is `blocked` when either a prohibited operation or a scanner
diagnostic exists. `--require-clean` exits 1 for either condition; without that
flag the checker still records `blocked` but exits 0 so a measurement-only
stage can retain the receipt.

## Scanner boundary

The scanner tokenizes the complete input buffer rather than treating physical
lines as operation boundaries. It recognizes custom operation names with or
without SSA result assignments and quoted generic operation names, including
multiple and nested operations on one line and legal trivia in result groups
such as `%r: 1 =`. It decodes MLIR two-digit hex escapes before
classification, skips whitespace and `//` comment trivia, and tracks explicit
attribute dictionaries so attribute keys, attribute strings, and quoted
symbol names do not enter the census. After authoritative parsing, top-level
attribute and location alias declarations are also data: the scanner masks
exactly one complete balanced RHS atom, including strings, arrays,
`distinct`, dialect attributes, attached delimiter groups, and typed suffixes.
This boundary leaves compact operations immediately before or after a
declaration visible.

Authoritative parser acceptance also supplies the quoted-generic grammar
boundary. A parser-accepted operation-shaped string enters the census only
when its next non-trivia token is the required operand-list `(`. Thus strings
such as LLVM named-struct identifiers, EmitC opaque type payloads, and
`cf.assert` messages remain data even when their decoded spelling is
`math.floor` or an unknown dotted name. Quoted zero-result, result-bearing,
escaped, comment-separated, same-line, and region-nested generic operations
all retain the required `(` and remain visible. Unvalidated or parser-rejected
text does not receive this exclusion: standalone names, malformed post-name
trivia, unknown operations, and operation-shaped strings in unproven metadata
continue through the conservative fail-closed path.

Location handling has an explicit trust boundary. The CLI first sends the
exact input text to pinned `mlir-opt` 21.1.2. Only after that authoritative
parse succeeds does the scanner treat each balanced, complete `loc(...)` span
as data. Thus arbitrary builtin, distinct, and dialect-extensible fused
metadata remains data without a Python reimplementation of MLIR's full
attribute grammar. The census still runs on the original text and retains its
original source locations. Parser rejection or an unavailable parser adds a
deterministic blocking diagnostic, then uses the conservative scanner so
operation-shaped strings inside or after malformed locations remain visible.

The pure `build_report(text)` API performs no subprocess work and records
`identity_status: not_run`. It recognizes a
bounded builtin subset: name/file/range locations, `unknown`, resolved named
and numeric aliases, callsites, and fused locations without metadata. Complex
fused metadata and top-level alias containers are never trusted as data in
this unvalidated mode; operation-shaped tokens remain visible and the complex
location case emits `malformed_location`.

The production CLI artifact is materialized by Nix with the exact
`${mlir}/bin/mlir-opt` canonical path, `pkgs.lib.getVersion mlir`, and
`builtins.hashFile "sha256"` digest embedded in its source. The checker
resolves the candidate executable, requires its canonical path and file hash
to match that tuple, independently runs and checks `--version`, and only then
parses the input. `--mlir-opt` can select a candidate but cannot replace the
authorized identity; the checked-in unbound source blocks. `/bin/true` and
version-spoofing or delegating wrappers therefore produce
`mlir_parser_identity_mismatch` before input parsing. These contexts are
excluded without suppressing neighboring,
result-bearing, or region-nested generic operations. The checker retains exact
counts for `arith.uitofp`, `memref.collapse_shape`,
`memref.copy`, `memref.expand_shape`, and `memref.reinterpret_cast` while also
prohibiting `arith.negf`, `math.floor`, and `math.absi`.

Generic and bare custom operation names are checked against an explicit
reviewed vocabulary. An unknown operation, malformed hex escape, missing
closing quote, missing operand list, or malformed post-name trivia emits a
deterministic scanner diagnostic regardless of whether the operation has SSA
results. Adding a new operation class requires an explicit checker-contract
change.

## Regression evidence

The focused suite covers result-bearing custom spellings, generic spellings,
SSA result lists and result-group trivia, escaped names, comments between a
generic name and operands, multiple and nested same-line operations, multiline
attribute keys, malformed zero-result operations, unknown quoted and custom
operations, comment/attribute/symbol/location string false positives,
neighboring true generic operations, balanced-malformed and unclosed location
wrappers, nested malformed callsite locations, deterministic bytes, exact
first locations, the schema-v3 key set, and independent self-hash
reconstruction. A pinned-parser corpus exercises 23 accepted builtin-location
and metadata combinations—including distinct and an LLVM dialect attribute—
plus nine rejected malformed, unbalanced, overflow, alias, and arbitrary
metadata mutations. Compact parser-accepted and parser-rejected fixtures
confirm that result-bearing and region-nested generic operations outside or
after fused location syntax remain visible. Additional pinned-valid cases
cover the exact array-alias reproducer, a compact array containing `distinct`
and an LLVM dialect attribute, and true operations on both sides; a rejected
unclosed-array mutation and the pure API prove the mask is parser-gated. The
Calyx-stage caller continues to use the checker's exit status and now invokes
the Nix-materialized identity-bound checker directly.

The accepted-parser boundary is additionally pinned by LLVM named-struct,
EmitC opaque-type, and `cf.assert` message fixtures using both prohibited and
unknown operation-shaped strings. A compact accepted fixture places two real
generic `math.floor` operations around two such data strings and requires an
exact count of two at the original first location. Accepted generic controls
cover zero-result `memref.copy`, result-bearing and escaped `math.floor`,
comments before the operand list, and a compact region-nested operation.
Pure-API and parser-rejected controls retain conservative diagnostics for the
same lexical shapes.
