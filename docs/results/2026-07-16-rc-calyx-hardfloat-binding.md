# RC Calyx/HardFloat basic-float binding evidence

## Unit under test

- Model key: `tinystories-w8a8-rc-study-mask9-vocab6-width2`.
- Flat-SCF input SHA-256: `2a2d0f15794833cb8af0fcdf168aef863e337f034750f7764c24da828d1525b1`.
- Source-inventory policy: `informational source inventory only; float presence or count does not decide lowering acceptance`.
- Reproduce the binding report with `nix build .#tinystories-w8a8-rc-calyx-hardfloat-bindings -L --no-link --print-out-paths`.

The inventory found `arith.addf` (106), `arith.subf` (7), `arith.mulf` (100), `arith.divf` (77), `arith.cmpf ugt` (67), `arith.sitofp i32 to f32` (74), `arith.fptosi f32 to i8` (65), and `arith.uitofp i1 to f32` (1). It deliberately leaves `arith.cmpf`, `arith.truncf`, `math.exp`, `math.fpowi`, `math.roundeven`, `math.rsqrt`, and `math.tanh` outside this basic-form MRC set.

## Native library closure

The all-wrapper fixture compiles through pinned Calyx and emits native SystemVerilog that includes these wrapper/implementation pairs:

| Calyx wrapper | Native implementation observed |
| --- | --- |
| `std_addFN` | `addRecFN` |
| `std_mulFN` | `mulRecFN` |
| `std_divSqrtFN` | `divSqrtRecFNToRaw_small` |
| `std_compareFN` | `compareRecFN` |
| `std_intToFp` | `iNToRecFN` |
| `std_fpToInt` | `recFNToIN` |

This is a concrete closure result for upstream Calyx float wrappers and their bundled HardFloat implementations. The only parser accommodation is the scoped `yosys-slang` flag `--allow-merging-ansi-ports`, required for upstream HardFloat's ANSI-port redeclarations; the emitted SystemVerilog itself is otherwise unchanged.

## RC-derived MRC results

Each source-form MRC came from the observed RC inventory and was lowered by `circt-opt --lower-scf-to-calyx`, translated via Calyx using the no-handshake SV script, then accepted by `yosys-slang`. `accepted` means an interface/binding capability result, not a numerical claim.

| RC form | MRC | CIRCT result | Futil imports | native SV/Yosys result | Binding status |
| --- | --- | --- | --- | --- |
| `arith.addf f32` | `addf-f32` | accepted | `primitives/float/addFN.futil` | accepted / accepted | accepted with `std_addFN` / HardFloat |
| `arith.subf f32` | `subf-f32` | accepted | `primitives/float/addFN.futil` | accepted / accepted | accepted with `std_addFN` / HardFloat |
| `arith.mulf f32` | `mulf-f32` | accepted | `primitives/float/mulFN.futil` | accepted / accepted | accepted with `std_mulFN` / HardFloat |
| `arith.divf f32` | `divf-f32` | accepted | `primitives/float/divSqrtFN.futil` | accepted / accepted | accepted with `std_divSqrtFN` / HardFloat |
| `arith.cmpf ugt f32` | `cmpf-ugt-f32` | accepted | `primitives/float/compareFN.futil` | accepted / accepted | accepted with `std_compareFN` / HardFloat |
| `arith.sitofp i32 to f32` | `sitofp-i32-f32` | accepted | `primitives/float/intToFp.futil` | accepted / accepted | accepted with `std_intToFp` / HardFloat |
| `arith.fptosi f32 to i8` | `fptosi-f32-i8` | accepted | `primitives/float/fpToInt.futil` | accepted / accepted | accepted with `std_fpToInt` / HardFloat |
| `arith.uitofp i1 to f32` | `uitofp-i1-f32` | rejected: explicitly illegal `arith.uitofp` | not reached | not reached / not reached | rejected; no binding claim |

The MRC inputs and runner are kept in-tree under [`reproducers/calyx-rc-basic-float-mrcs`](../../reproducers/calyx-rc-basic-float-mrcs) and [`scripts/pipeline/run_rc_calyx_hardfloat_bindings.py`](../../scripts/pipeline/run_rc_calyx_hardfloat_bindings.py).

## Limits

This is not numerical-equivalence evidence. The full RC has not reached a valid Calyx artifact or SystemVerilog through this route.

MRC capability does not make every float operation legal, does not prove a complete-RC lowering, and does not run the RC hardware-oracle gate. In particular, the HardFloat closure covers the listed arithmetic and conversion wrappers; it is not an implementation of transcendental `math.exp`.
