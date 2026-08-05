# RC exp table Verilator result

The generated table support module was compiled and executed with Verilator
5.022 using an explicit table hex image. The test drives reset, performs two
lookups (first and last address), checks the returned IEEE-754 float32 bit
patterns, and verifies the one-cycle response contract.

Result: `RC_EXP_TABLE_EQUIVALENCE_PASS`.

This is an actual RTL↔oracle equivalence test for the table component. It is
not yet a full RC-model equivalence result: the existing generated polynomial
RC top-level does not instantiate this lookup, and its strict harness still
has a preflight packaging failure (`/nix/store/build_rc_observable_oracle.py`
missing). The next integration step is therefore to make the support source
part of the generated top-level closure and pass it through the strict harness
without changing the RC memory ABI.
