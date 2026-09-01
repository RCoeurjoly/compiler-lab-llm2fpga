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

## Schema version 2

`scripts/pipeline/calyx_preflight_report.py` emits deterministic JSON with
exactly these fields:

```json
{
  "schema_version": 2,
  "status": "blocked",
  "prohibited_ops": {"math.floor": 1},
  "first_locations": {"math.floor": {"line": 1, "column": 6}},
  "scanner_diagnostics": [],
  "sha256": "..."
}
```

Counts and first-location keys are sorted by decoded operation name. Locations
are one-based and identify the first source character of the operation token;
for generic syntax that character is the opening quote. Diagnostics retain
source order. The self-hash is SHA-256 over canonical compact JSON with sorted
keys and the `sha256` member omitted.

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
attribute dictionaries and structurally valid location expressions so
attribute keys, attribute strings, quoted symbol names, and valid `loc(...)`
strings do not enter the census. Location recognition follows the pinned MLIR
21.1.2 builtin grammar recursively: name and file locations (including line,
column, range, decimal, and hexadecimal forms), unknown locations, resolved
named and numeric aliases, callsites, and fused locations with optional
structured metadata. Fused elements, name children, callsites, and metadata
locations may nest without turning their strings into operations. A malformed
or unclosed location, unresolved/non-location alias, overflowing source
coordinate, malformed fused list, or malformed metadata value emits a
deterministic `malformed_location` diagnostic and does not suppress its tokens
from the operation scan. These data contexts are excluded without suppressing
neighboring, result-bearing, or region-nested generic operations. It retains
exact counts for `arith.uitofp`, `memref.collapse_shape`,
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
first locations, the schema-v2 key set, and independent self-hash
reconstruction. A pinned-parser corpus exercises 21 accepted builtin-location
and metadata combinations plus eight rejected malformed, unbalanced,
overflow, and alias mutations; a compact parser-accepted fixture confirms that
result-bearing and region-nested generic operations adjacent to a fused
location remain visible.
Existing callers use the checker's exit status rather than parsing schema-v1
fields, so no coupled caller change is required for this task.
