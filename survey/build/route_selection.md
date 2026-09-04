# Route selection

- Status: `NO_PRIMARY_ROUTE_PASSED`
- Primary route: ``

Every R1-R8 candidate fails at least one hard gate. Weighted totals remain visible in `decision_matrix_scored.csv` for evidence prioritisation only; none overrides eligibility.

`first_failed_gate` in the scored CSV means the first false gate in the frozen protocol order; it is distinct from the receipt's observed `actual_stage`.

## Next evidence-gathering route (not selected primary)

- Next evidence-gathering route: `R1` (MLIR_CIRCT)
- Current eligibility: `INELIGIBLE`; final receipt `RTL_GENERATION/F_SOURCE_MISSING`.
- Bounded action: restore the committed native-SV helper, regenerate RTL, then rerun independent lint and synthesis before any M0-M3 claim.

## Different-family fallback hypothesis (also not selected)

- Fallback hypothesis: `R2` (PARAMETERIZED_RTL)
- Current eligibility: `INELIGIBLE` — ineligible because its final receipt is `SOURCE_CLOSURE/F_VENDOR_IP` and the RTL is proprietary.
- This is a different-family research hypothesis only; it is not a fallback route selection and cannot become one without redistributable RTL and new hard-gate evidence.
