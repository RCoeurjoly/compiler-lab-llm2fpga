# Reproducible Calyx Float Nix Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the native Calyx float-library and HardFloat dependency closure reproducible in Nix, prove it with a small `yosys-slang` self-test, and retry the full W8A8 Calyx route.

**Architecture:** A locked non-flake Calyx source supplies the compiler and full primitive hierarchy. A fixed-output HardFloat derivation is installed at the exact path used by Calyx's embedded Morty linker. The native-SV script retains its import audit and switches to a minimal, tested `main.sv` source closure only for Futil imports under `primitives/float/`; the integer path remains unchanged.

**Tech Stack:** Nix flakes, `buildRustPackage`, fixed-output `fetchurl`, upstream Calyx 0.7.1 development source, Berkeley HardFloat 1, Calyx/Morty, CIRCT, `yosys-slang`, Python `unittest`.

## Global Constraints

- Work on the user-approved current `main` tree; preserve the pre-existing `docs/glossary.md` modification.
- Pin `calyx-src` to `5a4303847392609cad83dda6f4bdffc8cc0e5c89`; do not use a branch, tag, or crates.io source for the float-capable package.
- Build Calyx with `pkgsLlvm21` because that scope supplies Rust 1.91.1 and the selected source requires Rust 1.85; do not downgrade or bypass the source's Rust requirement.
- Pin `HardFloat-1.zip` at `sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs=`. Do not invoke upstream `get_hardfloat.sh`, `curl`, or any unpinned fetch during a build.
- Install HardFloat at `$out/share/calyx/primitives/float/HardFloat-1`, including its `source/` and `source/RISCV/` directories.
- Do not treat `/tmp` as durable state. All durable sources, fixtures, logs, reports, and tool identities must be tracked in-tree or emitted by named Nix derivations.
- Do not alter model semantics, quantization, memory externalization, or the full TinyStories interface while repairing this packaging boundary.
- Do not claim a mapped FPGA result unless the existing Task 3 utilization derivation actually reaches its mapped report.

---

### Task 1: Specify the float-package contract and reproducer

**Files:**
- Create: `tests/test_calyx_float_nix_package.py`
- Create: `reproducers/calyx-float-library-selftest/input.futil`
- Create: `reproducers/calyx-float-library-selftest/README.md`

**Interfaces:**
- Consumes: the root `flake.nix`, `nix/calyx.nix`, future `nix/hardfloat.nix`, and the native-SV script.
- Produces: an executable specification for the exact Calyx revision, HardFloat hash/install path, float Futil fixture, package export, and float-source-list policy.

- [ ] **Step 1: Write the failing package-contract test**

Create `tests/test_calyx_float_nix_package.py` with assertions that intentionally fail before implementation:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CALYX_REV = "5a4303847392609cad83dda6f4bdffc8cc0e5c89"
HARDFLOAT_HASH = "sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs="


class CalyxFloatNixPackageTest(unittest.TestCase):
    def test_pinned_upstream_calyx_and_hardfloat_are_declared(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        calyx = (ROOT / "nix" / "calyx.nix").read_text(encoding="utf-8")
        hardfloat = (ROOT / "nix" / "hardfloat.nix").read_text(encoding="utf-8")

        self.assertIn('calyx-src = {', flake)
        self.assertIn(f'github:calyxir/calyx/{CALYX_REV}', flake)
        self.assertIn('flake = false;', flake)
        self.assertIn('pkgsLlvm21.callPackage ./nix/hardfloat.nix', flake)
        self.assertIn('pkgsLlvm21.callPackage ./nix/calyx.nix', flake)
        self.assertIn('calyxSrc = inputs.calyx-src;', flake)
        self.assertIn('src = calyxSrc;', calyx)
        self.assertIn('HardFloat-1', calyx)
        self.assertIn('primitives/float/HardFloat-1', calyx)
        self.assertIn(HARDFLOAT_HASH, hardfloat)
        self.assertNotIn('get_hardfloat.sh', calyx)
        self.assertNotIn('curl', hardfloat)

    def test_float_reproducer_and_native_selftest_are_declared(self) -> None:
        fixture = (ROOT / "reproducers/calyx-float-library-selftest/input.futil")
        readme = (ROOT / "reproducers/calyx-float-library-selftest/README.md")
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertTrue(fixture.exists())
        self.assertTrue(readme.exists())
        source = fixture.read_text(encoding="utf-8")
        self.assertIn('import "primitives/float/addFN.futil";', source)
        self.assertIn('std_addFN(8, 24, 32)', source)
        self.assertIn('calyx-float-library-selftest', flake)
        self.assertIn('module std_addFN', flake)
        self.assertIn('module fNToRecFN', flake)
        self.assertIn('yosysSlang', flake)

    def test_float_exports_use_the_tested_main_sv_closure(self) -> None:
        script = (ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('primitives/float/*', script)
        self.assertIn('"$output_dir/sv/main.sv" >"$output_dir/sources.f"', script)
        self.assertNotIn('mktemp /tmp/calyx_', script)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test to prove it is red**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package -v
```

Expected: `FileNotFoundError` for `nix/hardfloat.nix` or assertions that the
new flake input, package wiring, fixture, and self-test do not exist.

- [ ] **Step 3: Add the valid upstream float-add fixture and its contract**

Create `reproducers/calyx-float-library-selftest/input.futil` using the
upstream float-add correctness shape:

```futil
import "primitives/core.futil";
import "primitives/memories/comb.futil";
import "primitives/float/addFN.futil";

component main(@go go: 1) -> (@done done: 1) {
    cells {
        @external mem_read_a = comb_mem_d1(32, 1, 1);
        @external mem_read_b = comb_mem_d1(32, 1, 1);
        @external mem_write = comb_mem_d1(32, 1, 1);
        addFN0 = std_addFN(8, 24, 32);
    }

    wires {
        group add_std_format {
            mem_read_a.addr0 = 1'b0;
            addFN0.left = mem_read_a.read_data;
            mem_read_b.addr0 = 1'b0;
            addFN0.right = mem_read_b.read_data;
            addFN0.go = 1'b1;
            addFN0.subOp = 1'b0;
            addFN0.control = 1'b0;
            addFN0.roundingMode = 3'b0;
            mem_write.addr0 = 1'b0;
            mem_write.write_data = addFN0.out;
            mem_write.write_en = 1'b1;
            add_std_format[done] = (mem_write.done & addFN0.done) ? 1'd1;
        }
    }

    control { seq { add_std_format; } }
}
```

Create a concise README stating that this fixture is a native Calyx/Morty and
`yosys-slang` library-closure test, not numerical-equivalence evidence.

- [ ] **Step 4: Re-run the contract test; retain expected failures only for implementation gaps**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package -v
```

Expected: the fixture assertions pass, while Nix package and pipeline assertions
still fail until Tasks 2 and 3.

- [ ] **Step 5: Commit the specification fixture and failing test**

```bash
git add tests/test_calyx_float_nix_package.py reproducers/calyx-float-library-selftest
git commit -m "test: specify Calyx float Nix package"
```

### Task 2: Package pinned Calyx source and HardFloat in Nix

**Files:**
- Modify: `flake.nix:4-18`
- Modify: `flake.nix:175`
- Modify: `flake.nix:1718-1764`
- Modify: `flake.lock`
- Modify: `nix/calyx.nix:1-22`
- Create: `nix/hardfloat.nix`

**Interfaces:**
- Consumes: `inputs.calyx-src`, the HardFloat fixed hash, and `pkgsLlvm21`.
- Produces: `packages.<system>.calyx` whose `share/calyx` contains the full
  upstream primitive library and `primitives/float/HardFloat-1/source`.

- [ ] **Step 1: Add the upstream source input and package wiring**

In `flake.nix`, add this input alongside the other source inputs:

```nix
    calyx-src = {
      url = "github:calyxir/calyx/5a4303847392609cad83dda6f4bdffc8cc0e5c89";
      flake = false;
    };
```

Replace the existing package binding with a shared LLVM21-scope HardFloat and
Calyx package:

```nix
        hardfloat = pkgsLlvm21.callPackage ./nix/hardfloat.nix { };
        calyx = pkgsLlvm21.callPackage ./nix/calyx.nix {
          calyxSrc = inputs.calyx-src;
          inherit hardfloat;
        };
```

Keep `calyx` exported from `packages`; do not create a manually assembled
runtime path outside the derivation.

- [ ] **Step 2: Implement the fixed-output HardFloat derivation**

Create `nix/hardfloat.nix`:

```nix
{ fetchurl, stdenvNoCC, unzip }:

stdenvNoCC.mkDerivation rec {
  pname = "hardfloat";
  version = "1";

  src = fetchurl {
    url = "http://www.jhauser.us/arithmetic/HardFloat-1.zip";
    hash = "sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs=";
  };

  nativeBuildInputs = [ unzip ];
  dontConfigure = true;

  unpackPhase = ''
    unzip -q "$src"
  '';

  installPhase = ''
    mkdir -p "$out"
    cp -r HardFloat-1/. "$out/"
    test -f "$out/source/HardFloat_consts.vi"
    test -f "$out/source/RISCV/HardFloat_specialize.vi"
  '';
}
```

- [ ] **Step 3: Replace the crates.io Calyx package with the locked source package**

Replace `nix/calyx.nix` with the following initial derivation, using
`lib.fakeHash` only for the first intentional cargo-vendor discovery build:

```nix
{ lib, rustPlatform, calyxSrc, hardfloat }:

rustPlatform.buildRustPackage rec {
  pname = "calyx";
  version = "0.7.1";
  src = calyxSrc;
  cargoHash = lib.fakeHash;

  CALYX_PRIMITIVES_DIR = "${placeholder "out"}/share/calyx";
  doCheck = false;

  postInstall = ''
    mkdir -p "$out/share/calyx"
    cp -r primitives "$out/share/calyx/"
    mkdir -p "$out/share/calyx/primitives/float/HardFloat-1"
    cp -r ${hardfloat}/. \
      "$out/share/calyx/primitives/float/HardFloat-1/"
    test -x "$out/bin/calyx"
    test -f "$out/share/calyx/primitives/float/addFN.futil"
    test -f "$out/share/calyx/primitives/float/fpToInt.futil"
    test -f "$out/share/calyx/primitives/float/HardFloat-1/source/HardFloat_consts.vi"
  '';
}
```

- [ ] **Step 4: Lock the source and discover the cargo-vendor hash through Nix**

Run:

```bash
nix flake lock --update-input calyx-src
nix build .#calyx -L
```

Expected first build: a fixed-output hash mismatch naming the actual SRI hash
for the selected Calyx Cargo dependency closure. Replace only
`cargoHash = lib.fakeHash;` with that exact reported hash, then rerun the same
build until it succeeds.

- [ ] **Step 5: Verify the installed library closure and green contract test**

Run:

```bash
nix build .#calyx -L
nix path-info .#calyx
python3 -m unittest tests.test_calyx_float_nix_package.CalyxFloatNixPackageTest.test_pinned_upstream_calyx_and_hardfloat_are_declared -v
```

Expected: the package has an executable `calyx` binary and all float Futil and
HardFloat install-path assertions pass. The native self-test and source-list
assertions remain intentionally unrun until Task 3.

- [ ] **Step 6: Commit the reproducible package closure**

```bash
git add flake.nix flake.lock nix/calyx.nix nix/hardfloat.nix tests/test_calyx_float_nix_package.py
git commit -m "feat: package Calyx float library in Nix"
```

### Task 3: Prove native Calyx float SV and apply the tested source closure

**Files:**
- Modify: `flake.nix:1718-1764`
- Modify: `scripts/pipeline/calyx_to_sv_no_handshake.sh:60-185`
- Modify: `tests/test_calyx_float_nix_package.py`

**Interfaces:**
- Consumes: `calyx`, `yosysPkg`, `yosysSlang`, and
  `reproducers/calyx-float-library-selftest/input.futil`.
- Produces: `packages.<system>.calyx-float-library-selftest`, a Nix check that
  proves float-linked `main.sv` is Yosys-readable, and a tested `sources.f`
  policy for float imports.

- [ ] **Step 1: Extend the failing test for the self-test output and float branch**

Add assertions that the flake defines a derivation named
`calyx-float-library-selftest`, invokes `${calyx}/bin/calyx` with the
checked-in fixture and `-l ${calyx}/share/calyx`, checks `module std_addFN`
and `module fNToRecFN`, and invokes `yosys` with the `yosys-slang` plugin.
Keep the source-list assertion from Task 1: wrapper imports under
`primitives/float/*` must produce a `sources.f` containing only generated
`main.sv`.

- [ ] **Step 2: Run the test to prove the self-test declaration is absent**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package -v
```

Expected: failure on the absent self-test derivation and absent float-source
branch, while the source-package assertions remain green.

- [ ] **Step 3: Add the Nix-native Calyx/Morty/Yosys self-test**

Before the final `in { packages = ...; }` block in `flake.nix`, add:

```nix
        calyxFloatLibrarySelftest = pkgs.runCommand
          "calyx-float-library-selftest" {
            nativeBuildInputs = [ calyx yosysPkg ];
          } ''
            mkdir -p "$out"
            ${calyx}/bin/calyx \
              ${./reproducers/calyx-float-library-selftest/input.futil} \
              -l ${calyx}/share/calyx \
              -b verilog --synthesis --nested -d papercut \
              -o "$out/main.sv" >"$out/calyx.log" 2>&1
            test -s "$out/main.sv"
            grep -q 'module std_addFN' "$out/main.sv"
            grep -q 'module fNToRecFN' "$out/main.sv"
            printf '%s\n' "$out/main.sv" >"$out/sources.f"
            ${yosysPkg}/bin/yosys \
              -m ${yosysSlang}/share/yosys/plugins/slang.so \
              -p "read_slang --threads 1 --no-proc --max-parse-depth 20000 --top main $out/main.sv; hierarchy -top main -check; stat" \
              >"$out/yosys-slang.log" 2>&1
          '';
```

Export it as both a package and an explicit check:

```nix
          "calyx-float-library-selftest" = calyxFloatLibrarySelftest;
```

and replace the singleton check assignment with:

```nix
        checks = {
          default = modelRegistryJson;
          "calyx-float-library" = calyxFloatLibrarySelftest;
        };
```

- [ ] **Step 4: Replace the native script's explicit `/tmp` scratch files and select the tested float source closure**

In `scripts/pipeline/calyx_to_sv_no_handshake.sh`, replace the four
`mktemp /tmp/calyx_...` calls with a private scratch directory under
`$output_dir`:

```bash
scratch_dir="$(mktemp -d "$output_dir/.calyx-native-sv.XXXXXX")"
tmp_export_log="$scratch_dir/export.log"
tmp_calyx_log="$scratch_dir/native-calyx.log"
tmp_normalized="$scratch_dir/normalized.mlir"
tmp_exported_futil="$scratch_dir/model.futil"
cleanup() {
  rm -f "$tmp_export_log" "$tmp_calyx_log" "$tmp_normalized" "$tmp_exported_futil"
  rmdir "$scratch_dir"
}
trap cleanup EXIT
```

During the existing Futil import loop, set `uses_float_extern=1` only for
`primitives/float/*` imports. Initialize `uses_float_extern=0` immediately
before that loop. Replace the unconditional `compile.sv` creation and
five-entry `sources.f` here-document with:

```bash
if [[ "$uses_float_extern" -eq 1 ]]; then
  printf '%s\n' "$output_dir/sv/main.sv" >"$output_dir/sources.f"
else
  python3 "$compile_primitives_to_sv" \
    --compile-futil "$calyx_lib/primitives/compile.futil" \
    --output "$output_dir/sv/compile.sv"
  cat >"$output_dir/sources.f" <<EOF
$output_dir/sv/compile.sv
$calyx_lib/primitives/core.sv
$calyx_lib/primitives/binary_operators.sv
$calyx_lib/primitives/memories/seq.sv
$output_dir/sv/main.sv
EOF
fi
```

The existing resource-backend invocation remains outside that branch. Do not
remove the import audit or change the normal integer source list.

- [ ] **Step 5: Build the self-test and run focused verification**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package -v
nix build .#calyx-float-library-selftest -L
nix flake check -L
```

Expected: the Nix self-test produces `main.sv`, `sources.f`, `calyx.log`, and
`yosys-slang.log`; Yosys resolves HardFloat modules without an external or
hand-written source list. If this build does not reach Yosys, stop and record
the exact native-Calyx/Morty failure rather than guessing an alternative
library closure.

- [ ] **Step 6: Commit the self-test and pipeline boundary**

```bash
git add flake.nix scripts/pipeline/calyx_to_sv_no_handshake.sh tests/test_calyx_float_nix_package.py reproducers/calyx-float-library-selftest
git commit -m "feat: validate native Calyx float SV"
```

### Task 4: Retry the real W8A8 route and record only observed evidence

**Files:**
- Modify if reached: `docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md`
- Modify if reached: `artifacts/tinystories-w8a8-calyx-task3-utilization/result.json`
- Modify: `docs/superpowers/specs/2026-07-14-calyx-float-nix-package-design.md`

**Interfaces:**
- Consumes: the named self-test and existing
  `tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization` route.
- Produces: a successful mapped utilization result or a precise new terminal
  compiler/synthesis frontier, without implying FPGA fit when no mapped report
  exists.

- [ ] **Step 1: Update the design record with the verified package outcome**

After Task 3 passes, add the exact locked Calyx revision, Nix package outcome,
HardFloat install path, and self-test command/result to the design document.
Do not state that full TinyStories has reached SV or Yosys until the following
commands prove it.

- [ ] **Step 2: Run the full native-SV prerequisite**

Run:

```bash
nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv -L
```

Expected: either a real native-SV derivation with `model.futil`, `sv/main.sv`,
and `sources.f`, or a new logged compiler frontier. Preserve the Nix command,
exit status, and the first failing boundary.

- [ ] **Step 3: Run the existing exact Task 3 utilization route only if native SV succeeds**

Run:

```bash
nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization -L
```

Expected: a mapped XC7K480T report only if every existing Task 3 stage
finishes. If an earlier stage fails or is OOM-killed, record that actual
frontier and leave all LUT/FF/BRAM/DSP claims null.

- [ ] **Step 4: Update evidence from actual Nix outputs**

Copy or regenerate only compact derivation-produced manifests, logs, and
result JSON into the existing result/artifact locations. State the exact
Calyx source pin, HardFloat fixed hash, package test command, completed stage,
and whether Task 3 technology mapping was reached. Do not use data from an
untracked shell session or `/tmp` directory.

- [ ] **Step 5: Run final verification and commit evidence**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package tests.test_representative_core_no_handshake_sv tests.test_task3_pinned_w8a8_utilization -v
nix flake check -L
git diff --check
```

Then commit only the files changed by this task:

```bash
git add docs/superpowers/specs/2026-07-14-calyx-float-nix-package-design.md docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md artifacts/tinystories-w8a8-calyx-task3-utilization/result.json
git commit -m "docs: record Calyx float package outcome"
```

If the full route remains at a frontier, the evidence commit must say so and
must not manufacture missing utilization fields.
