# Reproducible Calyx Float-Library Package Design

## Objective

Replace the current crates.io-only Calyx package with an in-tree, fully pinned
Nix package that can satisfy the floating-point Futil imports emitted by the
current CIRCT Calyx exporter. The package must include the native Calyx
compiler, the complete upstream primitive library, and the compatible
HardFloat RTL source tree.

The immediate success condition is a small, reproducible native-Calyx float
test that reaches `yosys-slang` through an explicit source file list. The
full TinyStories PT2E W8A8 -> TOSA -> no-Handshake -> Calyx route is retried
only after that package-level boundary works.

## Evidence and root cause

The current package in `nix/calyx.nix` builds the crates.io `calyx` 0.7.1
crate and copies its bundled `primitives/` tree into the package output. That
tree lacks `primitives/float/`, so the native-SV exporter correctly stops when
CIRCT-generated Futil imports `primitives/float.futil` and float wrapper
files such as `primitives/float/addFN.futil`.

Upstream Calyx `v0.7.1` also lacks that directory. The first later upstream
source revision that contains every Futil file requested by the current CIRCT
exporter is `5a4303847392609cad83dda6f4bdffc8cc0e5c89`. It contains the
precise float Futil files and SystemVerilog wrappers requested by the
exporter. Those wrappers instantiate Berkeley HardFloat modules. Upstream's
helper script obtains `HardFloat-1.zip` dynamically over HTTP; that dynamic
script is not acceptable as a project dependency.

The selected Calyx backend embeds Morty as a Rust dependency. When it detects
float externs, Morty resolves the Calyx wrappers, HardFloat source directory,
and RISC-V include directory, then pickles that closure into the emitted SV.
The native-SV package self-test must prove that the resulting source list is
complete for `yosys-slang`; it must not rely on an unverified hand-maintained
HardFloat file list.

## Options considered

1. Build a pinned upstream Calyx source revision and a separately
   fixed-hash HardFloat archive in Nix. Install both as one library bundle and
   generate a complete deterministic source list. This is the selected
   approach.
2. Overlay only the newer `primitives/float` directory onto the existing
   crates.io compiler package. This is smaller, but it leaves an unproven
   compiler/library version mismatch and provides no principled HardFloat
   provenance.
3. Copy the needed Futil and SystemVerilog files into this repository. This
   would make the files visible, but creates an unmaintained fork of Calyx and
   HardFloat. It is rejected.

## Selected design

### Pinned source and library closure

Add a non-flake `calyx-src` input locked to upstream revision
`5a4303847392609cad83dda6f4bdffc8cc0e5c89`. Use it as the source of the
local `calyx` package rather than fetching a crates.io archive. The Nix lock
records the exact upstream tree; no source clone, compiler build, or library
assembly is performed manually outside the repository's Nix expressions.

This Calyx revision declares Rust 1.85. The root Nixpkgs input supplies Rust
1.77.2, so build the package from the already-pinned LLVM21 Nixpkgs scope,
which supplies Rust 1.91.1. The package remains a normal local flake output;
only its Rust build platform changes.

Add a small `nix/hardfloat.nix` fixed-output derivation. It fetches the exact
archive expected by Calyx with a content hash, unpacks it during the Nix build,
and exposes only the `HardFloat-1` tree. The Calyx package copies that tree to
the path expected by upstream wrappers:

```text
$out/share/calyx/primitives/float/HardFloat-1
```

The Calyx package installs the entire upstream `primitives/` hierarchy,
including `float.futil`, all `float/*.futil` files, wrapper SystemVerilog, and
the HardFloat source tree. It retains an explicit package version/provenance
record so a result can identify the Calyx revision and HardFloat fixed-output
input.

No build may run upstream `get_hardfloat.sh`, `curl`, or an unpinned source
fetch. The only durable inputs are the locked flake source, Nix expression,
and fixed content hash; build products live in the Nix store. New pipeline
work must not make `/tmp` a source of truth. Any scratch files are scoped to
their derivation and removed after their declared output has been produced.

### Native-SV source-list closure

Keep the existing Futil import audit immediately after CIRCT export. Do not
hand-enumerate the HardFloat closure in the pipeline: the selected native
Calyx backend uses its embedded Morty library to resolve and pickle float
externs into the emitted `main.sv`. The package installs HardFloat at exactly
the path Morty checks.

The self-test establishes the smallest deterministic `sources.f` accepted by
`yosys-slang` for a real float operator. The native-SV script then uses that
tested closure for float exports while retaining the established integer-only
list for integer pipelines. It must fail with a clear diagnostic on an import
that has no known synthesizable SV closure. The full generated file list,
rather than an undocumented shell environment, is the contract consumed by
the Task 3 `yosys-slang` route.

### Verification ladder

Tests precede package changes. They must establish that:

1. the flake declares and locks the upstream Calyx source;
2. `nix/calyx.nix` installs the float Futil directory and the separately
   pinned HardFloat tree;
3. the package exposes every Futil path currently imported by the CIRCT
   exporter;
4. a minimal float Futil fixture compiles through native Calyx and produces a
   deterministic source list; and
5. `yosys-slang` can read that exact source list without missing modules or
   include files.

Only after the small self-test passes will the existing full-model derivation
be rerun. A full-model failure remains a recorded compiler frontier; it is not
papered over by changing quantization, lowering, memory externalization, or
the model interface in this package task.

## Verified package outcome (Task 4)

The package boundary was verified on 2026-07-14 with the named Nix
derivation:

```text
nix build .#calyx-float-library-selftest -L
```

The command exited 0 and produced
`/nix/store/7cafwhjb6srwb05pvh46c6amd2xlyds6-calyx-float-library-selftest`.
Its derivation-produced `main.sv`, `sources.f`, `calyx.log`, and
`yosys-slang.log` confirm that the fixture reached `yosys-slang`; the latter
reports `Build succeeded: 0 errors, 0 warnings` for top `main`.

This result uses Calyx revision
`5a4303847392609cad83dda6f4bdffc8cc0e5c89` from the locked `calyx-src`
input, built in the `pkgsLlvm21` package scope. HardFloat remains the
fixed-output archive with hash
`sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs=` and is installed at
`$out/share/calyx/primitives/float/HardFloat-1` in the Calyx package (observed
package output:
`/nix/store/hafr57h6q1q46494z95a83fc9ad6bjlf-calyx-0.7.1`).

The fixture establishes only the Calyx/HardFloat library and native-SV source
closure. It is not evidence that the full TinyStories W8A8 route emits SV,
that Yosys accepts that full design, or that it fits an FPGA.

## Full W8A8 native-SV retry (Task 4)

The required full-model command was run outside the workspace sandbox:

```text
nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv -L
```

It exited 1 at the native-SV generation frontier. The failed derivation was
`/nix/store/2zmb3z0602x6s109j8mmcw9l7fg1j0vc-tinystories-w8a8-calyx-native-sv.drv`;
its inspectable failed output is
`/nix/store/2mrlpwn1ibvxsfxhqp6j1jfv66vmrvjk-tinystories-w8a8-calyx-native-sv`.

The named output contains `model.futil` (18,613,223 bytes) and a Calyx
manifest with `stage: "calyx"` and `status: "ok"`. It has no `sv/main.sv`.
The named derivation log's first failure is:

```text
... Killed "$calyx_bin" ... -b verilog ... -o "$output_dir/sv/main.sv" ...
Native Calyx-to-SV failed.
```

No full-model SV, Yosys, mapping, or utilization result exists.

## Scope and non-goals

This change restores a reproducible Calyx float-library dependency boundary.
It does not claim that the W8A8 model is integer-only, that its floating-point
operations are desirable hardware, that native Calyx handles every exported
operation, or that TinyStories is functionally equivalent to SystemVerilog.
Those questions remain separate milestones.

The existing user modification to `docs/glossary.md` is outside this work and
must remain untouched.
