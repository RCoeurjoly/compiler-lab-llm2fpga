# D14 route-family comparison

This table is derived from `survey/build/project_families.csv` primary family rows and the 36 rows in `survey/build/deep_review.csv`. It keeps the six route-family values frozen in `survey/config/scope.yaml`; blank source-family assignments are counted separately rather than becoming a seventh taxonomy value.

| Route family | Corpus primary families | Reviewed families/control rows |
| --- | ---: | ---: |
| MLIR_CIRCT | 3 | 2 |
| PARAMETERIZED_RTL | 23 | 2 |
| HLS | 45 | 5 |
| DATAFLOW | 74 | 15 |
| OVERLAY | 22 | 6 |
| CPU_FPGA_FALLBACK | 21 | 6 |

Unassigned primary-family rows: **38**; they are not recast as a route family.

Evidence: `survey/build/project_families.csv`; `survey/build/deep_review.csv`; `survey/config/scope.yaml`.
