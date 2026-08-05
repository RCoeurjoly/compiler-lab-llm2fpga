# Controlled Phase-1 screening audit

This audit is generated from the frozen Phase-1 mapping and the controlled reviewer decisions. Automatic levels and scores remain source metadata and never substitute for `final_level`.

## Reconciliation

- Source manifestations: 461
- Bibliographic work IDs: 456
- Included A-D manifestations: 231
- Excluded X manifestations: 230
- Included project families: 231

## Final counts

| Disposition | Records |
|---|---:|
| A | 30 |
| B | 57 |
| C | 75 |
| D | 69 |
| X | 230 |

## Controlled exclusion counts

| Disposition | Records |
|---|---:|
| X_ASIC_GPU_ONLY | 4 |
| X_DUPLICATE | 5 |
| X_LLM_FOR_EDA | 29 |
| X_NON_LM_MODEL | 155 |
| X_NOT_FPGA | 7 |
| X_NO_EVIDENCE | 4 |
| X_PERFORMANCE_MODEL_ONLY | 2 |
| X_RETRACTED | 0 |
| X_SECONDARY | 19 |
| X_TRAINING_ONLY | 5 |
| X_VIT_NO_TRANSFER | 0 |

## Duplicate/version decisions

Every source manifestation remains in `screening_decisions.csv`. Non-preferred duplicate manifestations use `X_DUPLICATE`; the family map retains their record evidence beside the preferred manifestation.

| Work ID | Record ID | Preferred record | Dedup rule | Final | Evidence |
|---|---|---|---|---|---|
| WORK-10AC642EACF002E1 | REC-52B9F62BBB664FC3 | REC-FB33D5E71B559051 | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-52B9F62BBB664FC3:title+abstract |
| WORK-10AC642EACF002E1 | REC-FB33D5E71B559051 | REC-FB33D5E71B559051 | preferred_manifestation | D | survey/build/phase1_mapping.csv#record_id=REC-FB33D5E71B559051:title+abstract |
| WORK-200199F16387DE63 | REC-5C037721F00D95E3 | REC-21E9ADD61448834C | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-5C037721F00D95E3:title+abstract |
| WORK-200199F16387DE63 | REC-21E9ADD61448834C | REC-21E9ADD61448834C | preferred_manifestation | B | survey/build/phase1_mapping.csv#record_id=REC-21E9ADD61448834C:title+abstract |
| WORK-52B6DB71CE1A8E32 | REC-63FB82EAD3C7188A | REC-922C6E25EEDB6165 | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-63FB82EAD3C7188A:title+abstract |
| WORK-52B6DB71CE1A8E32 | REC-922C6E25EEDB6165 | REC-922C6E25EEDB6165 | preferred_manifestation | X | survey/build/phase1_mapping.csv#record_id=REC-922C6E25EEDB6165:title+abstract |
| WORK-6B67737B78AD16BF | REC-BBE0B7CFE2C766EB | REC-1CADB59192072EAC | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-BBE0B7CFE2C766EB:title+abstract |
| WORK-6B67737B78AD16BF | REC-1CADB59192072EAC | REC-1CADB59192072EAC | preferred_manifestation | D | survey/build/phase1_mapping.csv#record_id=REC-1CADB59192072EAC:title+abstract |
| WORK-DE1374C0AC8B542C | REC-374F2F1C49957DA6 | REC-B9BB1B48E25209CD | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-374F2F1C49957DA6:title+abstract; LLM-inference-on-FPGA-papers/papers/2508.10303v1.pdf pages 12-13 section VI search phrase FPGA Implementation |
| WORK-DE1374C0AC8B542C | REC-B9BB1B48E25209CD | REC-B9BB1B48E25209CD | preferred_manifestation | C | survey/build/phase1_mapping.csv#record_id=REC-B9BB1B48E25209CD:title+abstract |

## Project-family consolidation

Project-family IDs are distinct from bibliographic `work_id` values. For conservative single-work families, the stable identifier is `PF-` followed by the first 16 uppercase hexadecimal characters of SHA-256(`project-family:` + `work_id`). The default is a conservative single-work family, explicitly marked `single_work_family`; multiple works share a family only when paper text identifies a named extension or release relationship. Repository URL equality is never used as family evidence.

## Reviewer sample / re-review design

The controlled pass is recorded as `codex-title-abstract-screen`. All provisional A and C records, conflicts, and route-boundary cases were individually adjudicated; material ambiguity was checked against the locally cached PDF and marked `title_abstract+local_full_text`. Obvious exclusions may retain `title_abstract` as their accurate basis.

The frozen repeat-review set is every final A/C record plus the stable 20% sample of B/D/X for which the first byte of SHA-256(record_id) is below 51. A second independent or one-week-delayed blind pass has not been represented as completed; downstream reporting must preserve this single-reviewer limitation until that pass is performed.

## Unresolved but non-blocking uncertainty

- Route-family labels describe the closest frozen route vocabulary; Level D components may intentionally have no route family.
- Single-work project families are conservative: absence of explicit cross-work release evidence is not evidence that no broader project relationship exists.
- The delayed or independent repeat-review sample remains a reporting limitation, not an invented agreement statistic.

## Decision evidence paths

Every final disposition and reviewer basis is listed below; these paths are also machine-readable in `screening_decisions.csv`.

| Record ID | Final | Reviewer | Basis | Evidence location |
|---|---|---|---|---|
| REC-A90ED129C90C94AD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A90ED129C90C94AD:title+abstract |
| REC-AAB3600F00A60110 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AAB3600F00A60110:title+abstract |
| REC-61B0E818AB02E4D2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-61B0E818AB02E4D2:title+abstract |
| REC-E887FD9D5AB3827A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E887FD9D5AB3827A:title+abstract |
| REC-416B2DD45741AF37 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-416B2DD45741AF37:title+abstract |
| REC-03C5614289D5B5ED | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-03C5614289D5B5ED:title+abstract |
| REC-068D2E4C36E0A59F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-068D2E4C36E0A59F:title+abstract |
| REC-AAAC49C19C9048DC | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-AAAC49C19C9048DC:title+abstract;LLM-inference-on-FPGA-papers/papers/1008.1673v2.pdf#text-search="purely formal, to be simulated only" |
| REC-CE62EB126433974E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CE62EB126433974E:title+abstract |
| REC-B86DE6D6670ABBED | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B86DE6D6670ABBED:title+abstract |
| REC-082721F13E9FFC71 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-082721F13E9FFC71:title+abstract |
| REC-42EE9703F04DEB01 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-42EE9703F04DEB01:title+abstract |
| REC-ADAAD71114348F43 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-ADAAD71114348F43:title+abstract |
| REC-BA343A3251B11D61 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BA343A3251B11D61:title+abstract |
| REC-8B22D9D0AE96DE69 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8B22D9D0AE96DE69:title+abstract |
| REC-D0A5C080D9A7A8BB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D0A5C080D9A7A8BB:title+abstract |
| REC-74F02CC1F5FFC6ED | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-74F02CC1F5FFC6ED:title+abstract |
| REC-F7672CF25143AE27 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F7672CF25143AE27:title+abstract |
| REC-268040C167BF9193 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-268040C167BF9193:title+abstract |
| REC-3C23A5B385B56748 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3C23A5B385B56748:title+abstract |
| REC-789E8FCA8135E770 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-789E8FCA8135E770:title+abstract |
| REC-C494916B77FB32D3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C494916B77FB32D3:title+abstract |
| REC-B995D93FB5904453 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B995D93FB5904453:title+abstract |
| REC-0FD00811878FA3A4 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0FD00811878FA3A4:title+abstract |
| REC-EB5B8D6B828622FE | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EB5B8D6B828622FE:title+abstract |
| REC-CF808A2F7D6515B3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CF808A2F7D6515B3:title+abstract |
| REC-3DCB691A456F4283 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3DCB691A456F4283:title+abstract |
| REC-1CDB61F0CD5CAEB4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1CDB61F0CD5CAEB4:title+abstract |
| REC-D30DB4EA311A5217 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D30DB4EA311A5217:title+abstract |
| REC-F4379DB7478366EF | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F4379DB7478366EF:title+abstract;LLM-inference-on-FPGA-papers/papers/1504.05372v1.pdf#text-search="TyTra architecture" |
| REC-24BB9609714294BE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-24BB9609714294BE:title+abstract |
| REC-F73FEC8CDF1AD512 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F73FEC8CDF1AD512:title+abstract;LLM-inference-on-FPGA-papers/papers/1505.01120v1.pdf#text-search="binary execution flow needed to support FPGAs" |
| REC-7D9A3E658DD7EEE6 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-7D9A3E658DD7EEE6:title+abstract;LLM-inference-on-FPGA-papers/papers/1508.06811v1.pdf#text-search="VHDL code was synthesized" |
| REC-6D2573B50D47CD83 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6D2573B50D47CD83:title+abstract |
| REC-97877AF2A5AE0C14 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-97877AF2A5AE0C14:title+abstract |
| REC-88F29B4B825641C8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-88F29B4B825641C8:title+abstract |
| REC-9A045A7D0B1DE0CE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9A045A7D0B1DE0CE:title+abstract |
| REC-65A934FBB91EDDC4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-65A934FBB91EDDC4:title+abstract |
| REC-FA096E95A0E3F88E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FA096E95A0E3F88E:title+abstract |
| REC-CCE2E4EFAFB5F4F8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CCE2E4EFAFB5F4F8:title+abstract |
| REC-DCFC6B023D9EF9F8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DCFC6B023D9EF9F8:title+abstract |
| REC-24048AD2630EDCFD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-24048AD2630EDCFD:title+abstract |
| REC-366778764662CFF9 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-366778764662CFF9:title+abstract |
| REC-975D4F11BDBF4844 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-975D4F11BDBF4844:title+abstract |
| REC-1CE9180A227DA1D1 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1CE9180A227DA1D1:title+abstract |
| REC-91117B7563F9179D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-91117B7563F9179D:title+abstract |
| REC-3DC05E88182B3C4E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3DC05E88182B3C4E:title+abstract |
| REC-88300383F39A1E30 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-88300383F39A1E30:title+abstract |
| REC-B4570AD5B3B50DDC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B4570AD5B3B50DDC:title+abstract |
| REC-F88C6066A8140556 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F88C6066A8140556:title+abstract |
| REC-7E30A752F924F93D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7E30A752F924F93D:title+abstract |
| REC-22B8F133078A7448 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-22B8F133078A7448:title+abstract |
| REC-3D12045BD8FEDC90 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3D12045BD8FEDC90:title+abstract |
| REC-805602F7D1C60B60 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-805602F7D1C60B60:title+abstract |
| REC-49F3AB6C20566E0A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-49F3AB6C20566E0A:title+abstract |
| REC-C174DDF6D468F0A5 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C174DDF6D468F0A5:title+abstract |
| REC-6B8F0EBD4ABBF3A2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6B8F0EBD4ABBF3A2:title+abstract |
| REC-0328D92B8D7AB525 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0328D92B8D7AB525:title+abstract |
| REC-380484F40BC5E6D9 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-380484F40BC5E6D9:title+abstract |
| REC-71655A79D4851161 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-71655A79D4851161:title+abstract |
| REC-BB06084936167C6D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BB06084936167C6D:title+abstract |
| REC-3570BA8F2CBFC43F | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-3570BA8F2CBFC43F:title+abstract;LLM-inference-on-FPGA-papers/papers/1711.04471v1.pdf#text-search="complete OpenCL-enabled code base" |
| REC-794B4806F5632532 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-794B4806F5632532:title+abstract |
| REC-193C307FD04D33A3 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-193C307FD04D33A3:title+abstract |
| REC-ACAB157CC9F0D857 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-ACAB157CC9F0D857:title+abstract;LLM-inference-on-FPGA-papers/papers/1712.03411v1.pdf#text-search="complete, open-source FPGA design methodology" |
| REC-0E5CD4ABE22322D8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0E5CD4ABE22322D8:title+abstract |
| REC-14F5886A00FF13FD | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-14F5886A00FF13FD:title+abstract;LLM-inference-on-FPGA-papers/papers/1801.06541v1.pdf#text-search="automatically generating serialization and deserialization hardware" |
| REC-478BAE4ECE99CA8F | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-478BAE4ECE99CA8F:title+abstract |
| REC-2A1F549319EB2EEB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2A1F549319EB2EEB:title+abstract |
| REC-1C2BC4282AF1A5AD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C2BC4282AF1A5AD:title+abstract |
| REC-DF772EB64BB5C76B | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DF772EB64BB5C76B:title+abstract |
| REC-38831414C8CA227A | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-38831414C8CA227A:title+abstract |
| REC-95E67C186BC2B316 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-95E67C186BC2B316:title+abstract |
| REC-35A5F4E0194903D4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-35A5F4E0194903D4:title+abstract |
| REC-F6A6EB8FD7251DAD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F6A6EB8FD7251DAD:title+abstract |
| REC-49F671D93D450AD9 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-49F671D93D450AD9:title+abstract |
| REC-FEAE1D67589AD270 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FEAE1D67589AD270:title+abstract |
| REC-AAFC038BCBE50BB1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AAFC038BCBE50BB1:title+abstract |
| REC-D88E8214DB7BBA3E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D88E8214DB7BBA3E:title+abstract |
| REC-ED59B1D5F5C32113 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-ED59B1D5F5C32113:title+abstract |
| REC-D65706651462F659 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D65706651462F659:title+abstract |
| REC-34D6BAEDB792D06C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-34D6BAEDB792D06C:title+abstract |
| REC-BDF6D5B4373DE47A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BDF6D5B4373DE47A:title+abstract |
| REC-36F0A271EFF0199A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-36F0A271EFF0199A:title+abstract |
| REC-6FF78E8941C82A36 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6FF78E8941C82A36:title+abstract |
| REC-89287D342E6CE922 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-89287D342E6CE922:title+abstract |
| REC-A47AFFCD278380DB | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A47AFFCD278380DB:title+abstract |
| REC-D0099014D837A521 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D0099014D837A521:title+abstract |
| REC-D97053B95AB833E6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D97053B95AB833E6:title+abstract |
| REC-F8D486FD316535AD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F8D486FD316535AD:title+abstract |
| REC-3D1B48A36A1C29EF | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3D1B48A36A1C29EF:title+abstract |
| REC-77F2744384901A06 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-77F2744384901A06:title+abstract |
| REC-714959A473E278C1 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-714959A473E278C1:title+abstract |
| REC-AA3630B18BB5F5C6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AA3630B18BB5F5C6:title+abstract |
| REC-E1A7182426E47166 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E1A7182426E47166:title+abstract |
| REC-B899DAA9C0C71D45 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B899DAA9C0C71D45:title+abstract |
| REC-798CD52628A50AD6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-798CD52628A50AD6:title+abstract |
| REC-8CEEE39C1C03B3AE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8CEEE39C1C03B3AE:title+abstract |
| REC-FA1D60BEAE9A18AD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FA1D60BEAE9A18AD:title+abstract |
| REC-1BD39A11DBF6BC60 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1BD39A11DBF6BC60:title+abstract |
| REC-2591DFCD2FE56740 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2591DFCD2FE56740:title+abstract |
| REC-BAA08971107EB217 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BAA08971107EB217:title+abstract |
| REC-45D346345BCBEE33 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-45D346345BCBEE33:title+abstract |
| REC-E7364B5C13D3ACB6 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E7364B5C13D3ACB6:title+abstract |
| REC-B8C88E3CD57FA457 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B8C88E3CD57FA457:title+abstract |
| REC-B050DA93F1DA379D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B050DA93F1DA379D:title+abstract |
| REC-2342F9BF3B1AB602 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2342F9BF3B1AB602:title+abstract |
| REC-D0D2254368D3B08B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D0D2254368D3B08B:title+abstract |
| REC-3DBEC0B586ABB7C0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3DBEC0B586ABB7C0:title+abstract |
| REC-3BF9C4C1B606866E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3BF9C4C1B606866E:title+abstract |
| REC-969D3C59E6AFE5EC | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-969D3C59E6AFE5EC:title+abstract |
| REC-3BFEDC35FEE6688E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3BFEDC35FEE6688E:title+abstract |
| REC-20E17694FEA9B59B | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-20E17694FEA9B59B:title+abstract |
| REC-D5344767957D09B6 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D5344767957D09B6:title+abstract |
| REC-E43A2DC89D039B8D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E43A2DC89D039B8D:title+abstract |
| REC-348FA63EF433FC7D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-348FA63EF433FC7D:title+abstract |
| REC-147FD411962C71A6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-147FD411962C71A6:title+abstract |
| REC-7C4BA136157B6978 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-7C4BA136157B6978:title+abstract;LLM-inference-on-FPGA-papers/papers/2109.02484v1.pdf#text-search="compiler backend targeting an OS-level protection layer" |
| REC-5EBD295089780BF4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5EBD295089780BF4:title+abstract |
| REC-BE790A13874474BF | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BE790A13874474BF:title+abstract |
| REC-76DCF46E7848DAB7 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-76DCF46E7848DAB7:title+abstract |
| REC-F75ACEF70BC3579F | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F75ACEF70BC3579F:title+abstract |
| REC-B7FF364706B031F7 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B7FF364706B031F7:title+abstract |
| REC-641104861DB63DFC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-641104861DB63DFC:title+abstract |
| REC-4A6FA7206BAA75B4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4A6FA7206BAA75B4:title+abstract |
| REC-4677DAA8E1C4E7A9 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4677DAA8E1C4E7A9:title+abstract |
| REC-2D18C1AB2332BD28 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2D18C1AB2332BD28:title+abstract |
| REC-82C674E8D7722312 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-82C674E8D7722312:title+abstract |
| REC-C2D16149A62BB51E | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C2D16149A62BB51E:title+abstract |
| REC-EB4A8C6C964584F8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EB4A8C6C964584F8:title+abstract |
| REC-F3DEAE2A615F1BEE | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F3DEAE2A615F1BEE:title+abstract |
| REC-3197E8A9160CF79B | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3197E8A9160CF79B:title+abstract |
| REC-5BA6F31CB89D22EF | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5BA6F31CB89D22EF:title+abstract |
| REC-09A364F2082BC906 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-09A364F2082BC906:title+abstract |
| REC-1FB2D9363D418D3A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1FB2D9363D418D3A:title+abstract |
| REC-AED6C450CC7834B2 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-AED6C450CC7834B2:title+abstract; LLM-inference-on-FPGA-papers/papers/2205.03886v1.pdf#section=II.System_Setup&search=prototype_based_on_a_field-programmable_gate_array |
| REC-BF8086DAD8681402 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BF8086DAD8681402:title+abstract |
| REC-447285B4B840EE11 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-447285B4B840EE11:title+abstract |
| REC-61C90658EFFD39BF | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-61C90658EFFD39BF:title+abstract |
| REC-DA2EC52C4B78AD71 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DA2EC52C4B78AD71:title+abstract |
| REC-B2475D779EEF408D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B2475D779EEF408D:title+abstract |
| REC-27EC4FCAD057D2AF | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-27EC4FCAD057D2AF:title+abstract |
| REC-4894CC10C8AB67A3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4894CC10C8AB67A3:title+abstract |
| REC-09886EF1B7D2452B | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-09886EF1B7D2452B:title+abstract |
| REC-D9F3C753FC29AAD4 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D9F3C753FC29AAD4:title+abstract |
| REC-07348ADFD0A3279E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-07348ADFD0A3279E:title+abstract |
| REC-A1560326B01F3E64 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A1560326B01F3E64:title+abstract |
| REC-79C05654ACFFF3E5 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-79C05654ACFFF3E5:title+abstract |
| REC-EEEA57D7E193DA78 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EEEA57D7E193DA78:title+abstract |
| REC-F05D5A696ACC9648 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F05D5A696ACC9648:title+abstract |
| REC-DACDD99CB85CF6D1 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DACDD99CB85CF6D1:title+abstract |
| REC-5A6C902321EA037F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5A6C902321EA037F:title+abstract |
| REC-6FB8D6370DDA238B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6FB8D6370DDA238B:title+abstract |
| REC-A2503EFE5BB738CE | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A2503EFE5BB738CE:title+abstract;LLM-inference-on-FPGA-papers/papers/2210.12703v1.pdf#text-search="eDSL to FPGA input representation" |
| REC-4C2E95DDB8B7F21F | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-4C2E95DDB8B7F21F:title+abstract; LLM-inference-on-FPGA-papers/papers/2210.14793v1.pdf#section=3.2.Circuit-level_Implementation&search=layer-wise_implementation |
| REC-D2117C9C65232AA0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D2117C9C65232AA0:title+abstract |
| REC-B797976E8C3DD74B | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B797976E8C3DD74B:title+abstract |
| REC-461426DFCC1AA131 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-461426DFCC1AA131:title+abstract |
| REC-F5EC31B9648B775E | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F5EC31B9648B775E:title+abstract;LLM-inference-on-FPGA-papers/papers/2211.14547v1.pdf#text-search="integrated compile time and runtime environment" |
| REC-532363BE02AE8521 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-532363BE02AE8521:title+abstract |
| REC-FD5A471D9856BBC7 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FD5A471D9856BBC7:title+abstract |
| REC-786ADC1381CD7C7C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-786ADC1381CD7C7C:title+abstract |
| REC-5FD6C290B90048C6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5FD6C290B90048C6:title+abstract |
| REC-B1AB3CDD99DC6F68 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B1AB3CDD99DC6F68:title+abstract |
| REC-B1E7232B88648FB9 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B1E7232B88648FB9:title+abstract |
| REC-A3BF29C8BC422359 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A3BF29C8BC422359:title+abstract |
| REC-B1B744172924155F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B1B744172924155F:title+abstract |
| REC-030A349885C6007C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-030A349885C6007C:title+abstract |
| REC-5F8D8FEE55A44AE2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5F8D8FEE55A44AE2:title+abstract |
| REC-1E7441F9766064EE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1E7441F9766064EE:title+abstract |
| REC-03B61755E4BFDD6B | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-03B61755E4BFDD6B:title+abstract |
| REC-EB622A25C915E5D5 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EB622A25C915E5D5:title+abstract |
| REC-66B094C6BAA51FA7 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-66B094C6BAA51FA7:title+abstract |
| REC-1C939925CE9E62FF | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C939925CE9E62FF:title+abstract |
| REC-0F2A03A0DF86FD27 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0F2A03A0DF86FD27:title+abstract |
| REC-0ED11F871A636313 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0ED11F871A636313:title+abstract |
| REC-5B72DD0EC4232AAC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5B72DD0EC4232AAC:title+abstract |
| REC-1C3DF74FE00A7869 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C3DF74FE00A7869:title+abstract |
| REC-BCFB3C4AFAE3811E | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BCFB3C4AFAE3811E:title+abstract |
| REC-1D91E09883329FFA | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1D91E09883329FFA:title+abstract;LLM-inference-on-FPGA-papers/papers/2308.06849v1.pdf#text-search="Generation of HLS-based BayesNN Accelerator" |
| REC-5379D6B857EA5D12 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5379D6B857EA5D12:title+abstract |
| REC-A4176B89BC21CA65 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A4176B89BC21CA65:title+abstract; LLM-inference-on-FPGA-papers/papers/2309.12917v1.pdf#section=Olympus_flow&search=implemented_as_an_FPGA_bitstream |
| REC-03737A3859757540 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-03737A3859757540:title+abstract |
| REC-BCED24E48DF96CCD | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BCED24E48DF96CCD:title+abstract |
| REC-366753D8F671C3E6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-366753D8F671C3E6:title+abstract |
| REC-3F04DF5486FF18BF | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3F04DF5486FF18BF:title+abstract |
| REC-951785FA7828CC56 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-951785FA7828CC56:title+abstract |
| REC-432F7854F5018CF5 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-432F7854F5018CF5:title+abstract |
| REC-D9405439DEC665EE | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D9405439DEC665EE:title+abstract |
| REC-8079DF7689E5D2AD | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8079DF7689E5D2AD:title+abstract |
| REC-03DB065D26928ABC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-03DB065D26928ABC:title+abstract |
| REC-69006487AF098BB4 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-69006487AF098BB4:title+abstract |
| REC-AA2294917DBE09FA | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AA2294917DBE09FA:title+abstract |
| REC-0E92CE28414078EE | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0E92CE28414078EE:title+abstract |
| REC-9DD301C82F69C383 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-9DD301C82F69C383:title+abstract; LLM-inference-on-FPGA-papers/papers/2401.03868v2.pdf#section=5.3.Analytical_Model_for_RTL_Generation&search=RTL_generator |
| REC-18A9873A1ED2419D | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-18A9873A1ED2419D:title+abstract |
| REC-5D437477A3B3F0CC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5D437477A3B3F0CC:title+abstract |
| REC-AAF5141FDB3D1BC0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AAF5141FDB3D1BC0:title+abstract |
| REC-EB5DF096D8CCF2D9 | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-EB5DF096D8CCF2D9:title+abstract; LLM-inference-on-FPGA-papers/papers/2401.10417v2.pdf#section=Table_3&search=vision_transformer_models |
| REC-8C100552CB5EC8D8 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8C100552CB5EC8D8:title+abstract |
| REC-F95950AEA19221D0 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F95950AEA19221D0:title+abstract |
| REC-8D280CE74606BAF2 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8D280CE74606BAF2:title+abstract |
| REC-E7AE600E045763D8 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E7AE600E045763D8:title+abstract |
| REC-E1548173957F8389 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E1548173957F8389:title+abstract |
| REC-89DB69AA1112A17A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-89DB69AA1112A17A:title+abstract |
| REC-501B131BCCDB0BBF | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-501B131BCCDB0BBF:title+abstract |
| REC-8315B7014468B835 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8315B7014468B835:title+abstract |
| REC-C011C30026F65B8A | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C011C30026F65B8A:title+abstract |
| REC-2A1E7F2B5FE644D9 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2A1E7F2B5FE644D9:title+abstract |
| REC-EC01639CBEC45A37 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EC01639CBEC45A37:title+abstract |
| REC-50F6BA42D72FB565 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-50F6BA42D72FB565:title+abstract |
| REC-40DE72B605CF02EB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-40DE72B605CF02EB:title+abstract |
| REC-8CA067D69DCD7740 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8CA067D69DCD7740:title+abstract |
| REC-A8FC56A3513C926D | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A8FC56A3513C926D:title+abstract; LLM-inference-on-FPGA-papers/papers/2405.00738v1.pdf page 3 section 3.1 Implementation search phrase host reads the output and performs sampling |
| REC-EE5E845B0F2772CA | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EE5E845B0F2772CA:title+abstract |
| REC-F03EEDBB96B92664 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F03EEDBB96B92664:title+abstract |
| REC-CB909EA926A5AC72 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CB909EA926A5AC72:title+abstract |
| REC-DC3D7EFD2F28A99F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DC3D7EFD2F28A99F:title+abstract |
| REC-F65FD886EFF07883 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F65FD886EFF07883:title+abstract |
| REC-76DBC4C4BEB42ABB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-76DBC4C4BEB42ABB:title+abstract |
| REC-B98F65C951D2121A | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B98F65C951D2121A:title+abstract |
| REC-A53433EACA5A3E39 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A53433EACA5A3E39:title+abstract;LLM-inference-on-FPGA-papers/papers/2406.14593v2.pdf#text-search="extends our conference publication" |
| REC-29297747619229E3 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-29297747619229E3:title+abstract |
| REC-CB40F46E4458382D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CB40F46E4458382D:title+abstract |
| REC-0A53F8CDE071DFAB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0A53F8CDE071DFAB:title+abstract |
| REC-CE605F5FE8275050 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CE605F5FE8275050:title+abstract |
| REC-2E8C2D5C8564F14C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2E8C2D5C8564F14C:title+abstract |
| REC-52DB9C1A84C344D5 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-52DB9C1A84C344D5:title+abstract |
| REC-6C5ABE261E433D60 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6C5ABE261E433D60:title+abstract |
| REC-B7DAC6E64AEA32C6 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B7DAC6E64AEA32C6:title+abstract |
| REC-179585D01665ABA3 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-179585D01665ABA3:title+abstract |
| REC-4810175E48EBE449 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4810175E48EBE449:title+abstract |
| REC-09DEF0F386F31DC0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-09DEF0F386F31DC0:title+abstract |
| REC-B4C13EE048139933 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B4C13EE048139933:title+abstract |
| REC-949433116AB006C6 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-949433116AB006C6:title+abstract |
| REC-770179015FF9EE68 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-770179015FF9EE68:title+abstract |
| REC-CCE11013FD53FD03 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CCE11013FD53FD03:title+abstract |
| REC-1E3A0B27361246BF | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1E3A0B27361246BF:title+abstract; LLM-inference-on-FPGA-papers/papers/2409.00661v1.pdf pages 6-8 section 5.4.3 search phrase GPT-2 inference speed comparison |
| REC-78DA1BBA4525C9E1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-78DA1BBA4525C9E1:title+abstract |
| REC-6099EE66504F6EF2 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6099EE66504F6EF2:title+abstract |
| REC-2861404557D1782A | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2861404557D1782A:title+abstract |
| REC-D80BA185FF6CE5BD | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-D80BA185FF6CE5BD:title+abstract; LLM-inference-on-FPGA-papers/papers/2409.11424v1.pdf page 6 section IV-C Performance Analysis search phrase tokens generated per second |
| REC-00876C5760C7308E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-00876C5760C7308E:title+abstract |
| REC-4D7BFF9A0A171A01 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4D7BFF9A0A171A01:title+abstract |
| REC-3219982CADC13B0C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3219982CADC13B0C:title+abstract |
| REC-32CC94372EE77D83 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-32CC94372EE77D83:title+abstract |
| REC-9C66DFA2ACB829E8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9C66DFA2ACB829E8:title+abstract |
| REC-90F9BA0E8090E56C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-90F9BA0E8090E56C:title+abstract |
| REC-EF524C7130F26BAD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EF524C7130F26BAD:title+abstract |
| REC-62D71FDC9956799A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-62D71FDC9956799A:title+abstract |
| REC-DD28132BF04122F9 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DD28132BF04122F9:title+abstract |
| REC-053F8CE5FE90B1D2 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-053F8CE5FE90B1D2:title+abstract |
| REC-D17ED0BF4F48BE11 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D17ED0BF4F48BE11:title+abstract |
| REC-C048DE10B21EE1B8 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-C048DE10B21EE1B8:title+abstract; LLM-inference-on-FPGA-papers/papers/2410.23083v1.pdf pages 2-3 sections 2-4 search phrase finite state transducer |
| REC-36C4AAA4FD4ACA93 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-36C4AAA4FD4ACA93:title+abstract; LLM-inference-on-FPGA-papers/papers/2411.03697v1.pdf#section=Table_7&search=only_measure_the_pre-fill_stage_for_GPT-2 |
| REC-C89D508C9645DB7B | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C89D508C9645DB7B:title+abstract |
| REC-78E9518BF6FC6EBF | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-78E9518BF6FC6EBF:title+abstract |
| REC-AD576C077EF03A16 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AD576C077EF03A16:title+abstract |
| REC-57B890A5DC77C4AA | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-57B890A5DC77C4AA:title+abstract |
| REC-361ADBB8874502B6 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-361ADBB8874502B6:title+abstract |
| REC-D7B209C7FF8D65B2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D7B209C7FF8D65B2:title+abstract |
| REC-170585CD873D413E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-170585CD873D413E:title+abstract |
| REC-8D6ACCD4E099C008 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8D6ACCD4E099C008:title+abstract |
| REC-AC7A77515D490E82 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AC7A77515D490E82:title+abstract |
| REC-04D1F7D833DB856C | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-04D1F7D833DB856C:title+abstract |
| REC-01007E919BA67615 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-01007E919BA67615:title+abstract |
| REC-F9910295847671D0 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F9910295847671D0:title+abstract |
| REC-856C24626DD738E5 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-856C24626DD738E5:title+abstract |
| REC-1ABE8CB7844BC247 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1ABE8CB7844BC247:title+abstract |
| REC-F511D5DFCA074FB4 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F511D5DFCA074FB4:title+abstract |
| REC-5B2530528709F6B9 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5B2530528709F6B9:title+abstract |
| REC-7CB959417EB26834 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7CB959417EB26834:title+abstract |
| REC-41EB5F1536296C6C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-41EB5F1536296C6C:title+abstract |
| REC-2C0E34856A04F65F | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2C0E34856A04F65F:title+abstract |
| REC-12C9D1ED9EF711FB | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-12C9D1ED9EF711FB:title+abstract; LLM-inference-on-FPGA-papers/papers/2501.19135v1.pdf pages 5-6 section V Experimental Results search phrase whole network |
| REC-9C5B33458C163E1C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9C5B33458C163E1C:title+abstract |
| REC-E1978C76FDD941FD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E1978C76FDD941FD:title+abstract |
| REC-37D418A5B0CD24F0 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-37D418A5B0CD24F0:title+abstract |
| REC-397AA2E8B322E5B6 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-397AA2E8B322E5B6:title+abstract |
| REC-7DA72502BFE51076 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7DA72502BFE51076:title+abstract |
| REC-614E448623940710 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-614E448623940710:title+abstract |
| REC-BCA6BA5940337BB3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BCA6BA5940337BB3:title+abstract |
| REC-561FD75C12B8EF91 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-561FD75C12B8EF91:title+abstract |
| REC-13722C8F89C40F15 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-13722C8F89C40F15:title+abstract |
| REC-9EEECBE6F301F9A2 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9EEECBE6F301F9A2:title+abstract |
| REC-688C296AB31CFA2F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-688C296AB31CFA2F:title+abstract |
| REC-507EEB2F277BB4EB | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-507EEB2F277BB4EB:title+abstract;LLM-inference-on-FPGA-papers/papers/2503.01138v1.pdf#text-search="release the source code and datasets of DB-Hunter" |
| REC-D97610736AA58551 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D97610736AA58551:title+abstract |
| REC-4BEC5993271B5F05 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4BEC5993271B5F05:title+abstract |
| REC-29CEB82FFB7D60B1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-29CEB82FFB7D60B1:title+abstract |
| REC-8038055899F288DD | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8038055899F288DD:title+abstract |
| REC-E47480B3889FF9C0 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E47480B3889FF9C0:title+abstract |
| REC-EA4C0FAA7D7F488C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EA4C0FAA7D7F488C:title+abstract |
| REC-AB2731AA91BB679A | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AB2731AA91BB679A:title+abstract |
| REC-A9B512BD33750559 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A9B512BD33750559:title+abstract; LLM-inference-on-FPGA-papers/papers/2504.09561v1.pdf pages 2 and 5-6 sections III and V search phrase end-to-end inference through L transformer blocks |
| REC-971FEFE09F7F6727 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-971FEFE09F7F6727:title+abstract;LLM-inference-on-FPGA-papers/papers/2504.10411v1.pdf#text-search="image data" |
| REC-C3B39CB94F1B4C76 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C3B39CB94F1B4C76:title+abstract |
| REC-4A2A4509290BC306 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4A2A4509290BC306:title+abstract |
| REC-74DFFEF8FFD0B3C6 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-74DFFEF8FFD0B3C6:title+abstract; LLM-inference-on-FPGA-papers/papers/2504.16112v2.pdf pages 5-6 sections V-B and VI search phrase end-to-end execution time |
| REC-0A35BCF12DE7E299 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0A35BCF12DE7E299:title+abstract |
| REC-7EB569AC45BB6577 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7EB569AC45BB6577:title+abstract |
| REC-27F112DB592D26A2 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-27F112DB592D26A2:title+abstract |
| REC-58388E3A8C4C4CC3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-58388E3A8C4C4CC3:title+abstract |
| REC-0084AA0272388588 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0084AA0272388588:title+abstract |
| REC-1C8427A2FAEFACE4 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1C8427A2FAEFACE4:title+abstract; LLM-inference-on-FPGA-papers/papers/2505.03745v1.pdf pages 9-11 section VI search phrase input and output token sizes |
| REC-8C8DCF083E462893 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8C8DCF083E462893:title+abstract |
| REC-EEF9D996052FB8A2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EEF9D996052FB8A2:title+abstract |
| REC-CF124426CCD42DE6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CF124426CCD42DE6:title+abstract |
| REC-C4AB2AB8C1CF67B5 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C4AB2AB8C1CF67B5:title+abstract |
| REC-504E4904B99F7C5E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-504E4904B99F7C5E:title+abstract |
| REC-55C6CBE6658E4D6D | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-55C6CBE6658E4D6D:title+abstract |
| REC-6FA4AA8C0ADE1CF7 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6FA4AA8C0ADE1CF7:title+abstract |
| REC-6001BF8DB461EEBB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6001BF8DB461EEBB:title+abstract |
| REC-C9B23D5F0BA8A1A3 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C9B23D5F0BA8A1A3:title+abstract |
| REC-BA79F5E84B429763 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BA79F5E84B429763:title+abstract |
| REC-58EA590C04E33E29 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-58EA590C04E33E29:title+abstract |
| REC-6304EAE6041C2B77 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6304EAE6041C2B77:title+abstract |
| REC-BCC3E9EFF1B93E62 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-BCC3E9EFF1B93E62:title+abstract;LLM-inference-on-FPGA-papers/papers/2506.12971v1.pdf#text-search="partial reconfiguration" |
| REC-69F340FD9A5D9F2E | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-69F340FD9A5D9F2E:title+abstract;LLM-inference-on-FPGA-papers/papers/2506.15613v1.pdf#text-search="prototype a CXL-SSD" |
| REC-DCFB7010F089D86B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DCFB7010F089D86B:title+abstract |
| REC-A9265AD0192938C0 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A9265AD0192938C0:title+abstract |
| REC-09794B47FC51DBAE | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-09794B47FC51DBAE:title+abstract; LLM-inference-on-FPGA-papers/papers/2507.01035v1.pdf pages 2-5 section III Research Methodology search phrase Hybrid + FPGA + DeepSpeed |
| REC-804DE81A30D8BC62 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-804DE81A30D8BC62:title+abstract |
| REC-DE3DA0389AC93D33 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DE3DA0389AC93D33:title+abstract |
| REC-43EBA3F96335295D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-43EBA3F96335295D:title+abstract;LLM-inference-on-FPGA-papers/papers/2507.10912v1.pdf#text-search="source code of this work" |
| REC-D4D0D4D6341705BB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D4D0D4D6341705BB:title+abstract |
| REC-5300A102BA97CB5B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5300A102BA97CB5B:title+abstract |
| REC-3E83647529A0BF93 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-3E83647529A0BF93:title+abstract; LLM-inference-on-FPGA-papers/papers/2507.14139v1.pdf page 2 search phrase complete inference |
| REC-928C37379AB66C32 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-928C37379AB66C32:title+abstract |
| REC-C1B45DD5CFFDEF49 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C1B45DD5CFFDEF49:title+abstract |
| REC-70FF806962EDBD4E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-70FF806962EDBD4E:title+abstract |
| REC-D675CF108CBF8BAA | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D675CF108CBF8BAA:title+abstract |
| REC-A84588B0F7BE86BC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A84588B0F7BE86BC:title+abstract |
| REC-1229847FA1C1D549 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1229847FA1C1D549:title+abstract |
| REC-374F2F1C49957DA6 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-374F2F1C49957DA6:title+abstract; LLM-inference-on-FPGA-papers/papers/2508.10303v1.pdf pages 12-13 section VI search phrase FPGA Implementation |
| REC-B9BB1B48E25209CD | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B9BB1B48E25209CD:title+abstract |
| REC-867BF18E2ADEBF6C | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-867BF18E2ADEBF6C:title+abstract; LLM-inference-on-FPGA-papers/papers/2508.10370v1.pdf#section=3.eMamba_Design_Framework_Overview&search=focus_on_three_representative_vision_datasets |
| REC-55AF74F48541DBB8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-55AF74F48541DBB8:title+abstract |
| REC-0AB8E04D7DD6C72A | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0AB8E04D7DD6C72A:title+abstract |
| REC-1C63BBF0DA4696BC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C63BBF0DA4696BC:title+abstract |
| REC-2524EF73E57121D9 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-2524EF73E57121D9:title+abstract; LLM-inference-on-FPGA-papers/papers/2508.13905v2.pdf#section=Hardware-aware_deployment&search=modular_VHDL_code_generation |
| REC-805AE51C4211C504 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-805AE51C4211C504:title+abstract |
| REC-F6EE464E0EAC055F | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F6EE464E0EAC055F:title+abstract |
| REC-6CF049B6B7FF9E23 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6CF049B6B7FF9E23:title+abstract |
| REC-A9812738B0D3FDF8 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A9812738B0D3FDF8:title+abstract;LLM-inference-on-FPGA-papers/papers/2509.01149v1.pdf#text-search="metamorphic transformation rules" |
| REC-FD2B3322B61290F3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FD2B3322B61290F3:title+abstract |
| REC-908FFDB34685B693 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-908FFDB34685B693:title+abstract |
| REC-BEACC83B64B951BF | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-BEACC83B64B951BF:title+abstract; LLM-inference-on-FPGA-papers/papers/2509.13765v1.pdf#section=Evaluation&search=TENET-FPGA_achieves_an_end-to-end_speedup |
| REC-C9DCCD19015DC11E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C9DCCD19015DC11E:title+abstract |
| REC-E4632083C47944B3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E4632083C47944B3:title+abstract |
| REC-2D053154E4E78BA8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2D053154E4E78BA8:title+abstract |
| REC-BE520FAB2229160E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BE520FAB2229160E:title+abstract |
| REC-525F07C62996AA0D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-525F07C62996AA0D:title+abstract; LLM-inference-on-FPGA-papers/papers/2509.26335v2.pdf pages 3-5 sections 3-4 search phrase Vitis HLS is used |
| REC-939579D7FA707D17 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-939579D7FA707D17:title+abstract |
| REC-65FB5420A0B12A25 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-65FB5420A0B12A25:title+abstract |
| REC-FE659F378ED5871B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FE659F378ED5871B:title+abstract |
| REC-28937A3B820B31B6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-28937A3B820B31B6:title+abstract |
| REC-48B14D3F981A4130 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-48B14D3F981A4130:title+abstract |
| REC-DD588E778AEE07F4 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DD588E778AEE07F4:title+abstract |
| REC-965CCFFDE7F04B1C | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-965CCFFDE7F04B1C:title+abstract;LLM-inference-on-FPGA-papers/papers/2510.21745v1.pdf#text-search="RTLLM benchmark" |
| REC-462BCA4753C78ACE | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-462BCA4753C78ACE:title+abstract |
| REC-EABB5667866DC451 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EABB5667866DC451:title+abstract |
| REC-7A1FA14A8DCA183B | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7A1FA14A8DCA183B:title+abstract |
| REC-9979CC5AB4BD1317 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9979CC5AB4BD1317:title+abstract |
| REC-12ADC59BADCFF351 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-12ADC59BADCFF351:title+abstract |
| REC-5F3EF920419354F6 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5F3EF920419354F6:title+abstract |
| REC-3ED97335A1D4DAF1 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3ED97335A1D4DAF1:title+abstract |
| REC-5D415BE753409B13 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5D415BE753409B13:title+abstract |
| REC-5F3D8033CA8716D1 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5F3D8033CA8716D1:title+abstract |
| REC-A09E64F97FA61561 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A09E64F97FA61561:title+abstract |
| REC-ED5450FF15872377 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-ED5450FF15872377:title+abstract |
| REC-5C4ADC39D64D338C | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-5C4ADC39D64D338C:title+abstract;LLM-inference-on-FPGA-papers/papers/2511.15505v1.pdf#text-search="transforms DNN models into instruction programs" |
| REC-0FC0CC9FC50469EE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0FC0CC9FC50469EE:title+abstract |
| REC-92F308C0D23DBD70 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-92F308C0D23DBD70:title+abstract |
| REC-F678D73F154843E5 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F678D73F154843E5:title+abstract |
| REC-795EC13A60CA2881 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-795EC13A60CA2881:title+abstract |
| REC-A3A7195BE5E5F981 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A3A7195BE5E5F981:title+abstract |
| REC-83B76CC7809050A0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-83B76CC7809050A0:title+abstract |
| REC-3E67D6E6336EB3E9 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3E67D6E6336EB3E9:title+abstract |
| REC-BB32A1B6674133E8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BB32A1B6674133E8:title+abstract |
| REC-2514284B7C63EDA7 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2514284B7C63EDA7:title+abstract |
| REC-510075C37D685110 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-510075C37D685110:title+abstract |
| REC-A0B5993AEECCF0B8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A0B5993AEECCF0B8:title+abstract |
| REC-136E0A6CF2902F8E | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-136E0A6CF2902F8E:title+abstract; LLM-inference-on-FPGA-papers/papers/2601.02135v1.pdf pages 6-8 sections 4.1 and 5.3 search phrase sustained token-per-second rate |
| REC-9C84CD6F53E668CB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9C84CD6F53E668CB:title+abstract |
| REC-57D5901E46D93621 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-57D5901E46D93621:title+abstract |
| REC-FEAA09BB86B0EBDA | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FEAA09BB86B0EBDA:title+abstract |
| REC-B0590D78EA1EFC4E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B0590D78EA1EFC4E:title+abstract |
| REC-B43B25ED6C25AA2D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-B43B25ED6C25AA2D:title+abstract;LLM-inference-on-FPGA-papers/papers/2601.15151v1.pdf#text-search="architectural parameterization framework" |
| REC-F7C40BB06A37B794 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F7C40BB06A37B794:title+abstract |
| REC-4E361D4CBDFC8F53 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4E361D4CBDFC8F53:title+abstract |
| REC-AA20210441F740E6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AA20210441F740E6:title+abstract |
| REC-8545F20267A68E40 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8545F20267A68E40:title+abstract |
| REC-5DE990D2A7F4ED8B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5DE990D2A7F4ED8B:title+abstract |
| REC-23229B1B1C344FB1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-23229B1B1C344FB1:title+abstract |
| REC-D287787009EA9CFE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D287787009EA9CFE:title+abstract |
| REC-6959A58704BD803C | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6959A58704BD803C:title+abstract |
| REC-47E3674AA323D0A4 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-47E3674AA323D0A4:title+abstract |
| REC-D73CD39BFAF22510 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D73CD39BFAF22510:title+abstract |
| REC-81988529E906B625 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-81988529E906B625:title+abstract |
| REC-6861DF774D045B5D | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6861DF774D045B5D:title+abstract |
| REC-FAC8489480AB16AF | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FAC8489480AB16AF:title+abstract |
| REC-C5FFB21E3A3121F0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C5FFB21E3A3121F0:title+abstract |
| REC-5C037721F00D95E3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5C037721F00D95E3:title+abstract |
| REC-21E9ADD61448834C | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-21E9ADD61448834C:title+abstract |
| REC-324FEBE49170D903 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-324FEBE49170D903:title+abstract |
| REC-D2CCA02341920D52 | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-D2CCA02341920D52:title+abstract; LLM-inference-on-FPGA-papers/papers/2603.22867v1.pdf#section=4.1.Compiler_Infrastructure&search=Chisel-based_RTL_generator |
| REC-5DDEE20F5B196B1D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5DDEE20F5B196B1D:title+abstract |
| REC-BBE0B7CFE2C766EB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BBE0B7CFE2C766EB:title+abstract |
| REC-1CADB59192072EAC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1CADB59192072EAC:title+abstract |
| REC-377F6DCA995797F6 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-377F6DCA995797F6:title+abstract |
| REC-1B391A89C0485DFA | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1B391A89C0485DFA:title+abstract;LLM-inference-on-FPGA-papers/papers/2604.04694v1.pdf#text-search="live kernel migration" |
| REC-86EE7D1C5BCC6BE3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-86EE7D1C5BCC6BE3:title+abstract |
| REC-E735B0C0CC6BAEC2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E735B0C0CC6BAEC2:title+abstract |
| REC-B8F583785D75AE85 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-B8F583785D75AE85:title+abstract; LLM-inference-on-FPGA-papers/papers/2604.13933v2.pdf pages 2-4 sections II-D and IV-B search phrase U-Net |
| REC-24F11AD2640DE71D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-24F11AD2640DE71D:title+abstract |
| REC-39AD7E76048C13F1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-39AD7E76048C13F1:title+abstract |
| REC-906ABFB35680FA91 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-906ABFB35680FA91:title+abstract |
| REC-086BFC4543DB0A77 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-086BFC4543DB0A77:title+abstract |
| REC-8539603CEC57E49F | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8539603CEC57E49F:title+abstract |
| REC-B0C90C8C1FE0E7CF | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B0C90C8C1FE0E7CF:title+abstract |
| REC-C2EE0783B7B592BD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C2EE0783B7B592BD:title+abstract |
| REC-952DDF542BB99BA4 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-952DDF542BB99BA4:title+abstract |
| REC-48C8BD37C529BFD7 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-48C8BD37C529BFD7:title+abstract |
| REC-0030D8D9BECDB48D | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0030D8D9BECDB48D:title+abstract |
| REC-52B9F62BBB664FC3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-52B9F62BBB664FC3:title+abstract |
| REC-FB33D5E71B559051 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FB33D5E71B559051:title+abstract |
| REC-0D2FAB7474469C66 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-0D2FAB7474469C66:title+abstract;LLM-inference-on-FPGA-papers/papers/2605.18444v1.pdf#text-search="Cadence simulations" |
| REC-4B81C38EF3EA8055 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4B81C38EF3EA8055:title+abstract |
| REC-0C1041A492BBE78B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0C1041A492BBE78B:title+abstract |
| REC-10744E88807F3025 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-10744E88807F3025:title+abstract |
| REC-3997FA16D99A7164 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3997FA16D99A7164:title+abstract |
| REC-02EB72AEF9B113D9 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-02EB72AEF9B113D9:title+abstract |
| REC-A0B0390046E2E6F5 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A0B0390046E2E6F5:title+abstract |
| REC-4C1B20A6E3DE81C3 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4C1B20A6E3DE81C3:title+abstract |
| REC-72DC5BAC04D90C54 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-72DC5BAC04D90C54:title+abstract |
| REC-1C97721CCD37B094 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C97721CCD37B094:title+abstract |
| REC-0EFADB30331858A2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0EFADB30331858A2:title+abstract |
| REC-C63FAD4BB750FE4C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C63FAD4BB750FE4C:title+abstract |
| REC-25D1D3FB6640874F | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-25D1D3FB6640874F:title+abstract |
| REC-63FB82EAD3C7188A | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-63FB82EAD3C7188A:title+abstract |
| REC-922C6E25EEDB6165 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-922C6E25EEDB6165:title+abstract |
| REC-90FA67A1B637BEA1 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-90FA67A1B637BEA1:title+abstract |
| REC-CC1778CFFA15521D | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CC1778CFFA15521D:title+abstract |
| REC-108DD28A7C9AB62D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-108DD28A7C9AB62D:title+abstract |
| REC-01720AD4700AA4A1 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-01720AD4700AA4A1:title+abstract |
| REC-DCFB2D3622A71A68 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DCFB2D3622A71A68:title+abstract |
| REC-C963AD29DE58DB45 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-C963AD29DE58DB45:title+abstract; LLM-inference-on-FPGA-papers/papers/2607.03652v1.pdf#section=4.3.2.ELiTeFormer_1B_Latency_Profile&search=employs_Vitis_HLS_to_generate_RTL |
| REC-EA143A4A252C95C7 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EA143A4A252C95C7:title+abstract |
| REC-07755277A14E36BC | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-07755277A14E36BC:title+abstract |
| REC-6A586600EEDCB118 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6A586600EEDCB118:title+abstract |
| REC-3C1BB60FF7107D12 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3C1BB60FF7107D12:title+abstract |
| REC-26BE38724CE14F44 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-26BE38724CE14F44:title+abstract |
| REC-BD77A6758C470A7E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BD77A6758C470A7E:title+abstract |
| REC-3D8BAE87506248E2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-3D8BAE87506248E2:title+abstract |
| REC-9293F046B0D112DC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9293F046B0D112DC:title+abstract |
| REC-E66ED844D509AC26 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E66ED844D509AC26:title+abstract |
| REC-05CE8CF08628F250 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-05CE8CF08628F250:title+abstract |
| REC-EAAAF4FE370E17FC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EAAAF4FE370E17FC:title+abstract |
| REC-BA4F44A6E9632049 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BA4F44A6E9632049:title+abstract |
| REC-541008175C865D59 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-541008175C865D59:title+abstract |
