# Controlled Phase-1 screening audit

This audit is generated from the frozen Phase-1 mapping and the controlled reviewer decisions. Automatic levels and scores remain source metadata and never substitute for `final_level`.

## Reconciliation

- Source manifestations: 461
- Bibliographic work IDs: 456
- Included A-D manifestations: 230
- Excluded X manifestations: 231
- Included project families: 226

## Final counts

| Disposition | Records |
|---|---:|
| A | 30 |
| B | 57 |
| C | 75 |
| D | 68 |
| X | 231 |

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
| X_TRAINING_ONLY | 6 |
| X_VIT_NO_TRANSFER | 0 |

## Duplicate/version decisions

Every source manifestation remains in `screening_decisions.csv`. Non-preferred duplicate manifestations use `X_DUPLICATE`. When the preferred manifestation is included, the family map retains duplicate record evidence beside it; excluded groups remain traceable here and in the decision file.

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
| WORK-DE1374C0AC8B542C | REC-374F2F1C49957DA6 | REC-B9BB1B48E25209CD | exact_arxiv | X | survey/build/phase1_mapping.csv#record_id=REC-374F2F1C49957DA6:title+abstract;source_url=https://arxiv.org/pdf/2508.10303v1;cache_filename=2508.10303v1.pdf;cache_sha256=6666bba0612a0b2b9225dd2fa4ec8141a1092c3ad50dbd8b4b336c02b21acc02;locator=pages 12-13 section VI search phrase FPGA Implementation |
| WORK-DE1374C0AC8B542C | REC-B9BB1B48E25209CD | REC-B9BB1B48E25209CD | preferred_manifestation | C | survey/build/phase1_mapping.csv#record_id=REC-B9BB1B48E25209CD:title+abstract |

## Project-family consolidation

Project-family IDs are distinct from bibliographic `work_id` values. For conservative single-work families, the stable identifier is `PF-` followed by the first 16 uppercase hexadecimal characters of SHA-256(`project-family:` + `work_id`). Named multi-work families use the same derivation with a canonical `named-system:<slug>` key recorded in `project_family_key`; callers cannot choose IDs. The default is a conservative single-work family, explicitly marked `single_work_family`; multiple works share a family only when paper text identifies a named extension or release relationship. Repository URL equality is never used as family evidence.

Named multi-work families: 4. Every linked bibliographic work remains a separate row in `project_families.csv`.

| Project family | Family key | Primary work | Linked works | Grouping basis |
|---|---|---|---|---|
| PF-25C132E08D276681 | named-system:tellme | WORK-D98F092B3E212C22 | WORK-D98F092B3E212C22;WORK-EDCEC112A1B67954 | named_system_extension; TeLLMe v2 cites the original TeLLMe arXiv:2504.16266, retains all five authors, and extends the same ternary prefill/decode accelerator |
| PF-31AE21CFCF31BECE | named-system:metaml | WORK-76ACBFCD99E4F225 | WORK-76ACBFCD99E4F225;WORK-ABC385BEAF195807 | named_system_extension; MetaML-Pro section Relationship to Prior Publications states that it expands the prior MetaML framework |
| PF-443A595D662099E7 | named-system:m3vit_edge_moe | WORK-2D44FCCE8D9826E3 | WORK-2D44FCCE8D9826E3;WORK-5B6F84F0C6192010 | named_system_extension; Edge-MoE explicitly names M3ViT as its source model and solves its FPGA-deployment challenges with five shared authors |
| PF-4814F9379C7A45A0 | named-system:haddoc2 | WORK-674CDDB57508D5CE | WORK-674CDDB57508D5CE;WORK-769AF53322C4EFB1 | named_system_extension; both papers introduce the same HADDOC2 open-source CNN-to-VHDL tool with five core authors, and the later peer-reviewed work extends its direct-mapping tactics |

## Explicit conservative non-merges

Similar titles, authors, domains, or framework dependencies do not establish a shared implementation family without direct lineage evidence. These reviewed candidate pairs therefore remain separate.

| Candidate records | Assigned families | Non-merge rationale |
|---|---|---|
| REC-8079DF7689E5D2AD; REC-361ADBB8874502B6 | PF-EC7A371C4608D83D; PF-3123E25E353ECBC2 | The later particle-physics paper neither cites the earlier audio paper nor identifies it as a predecessor; shared naming and authors are insufficient with no direct release, version, or extension evidence. |
| REC-1D91E09883329FFA; REC-A53433EACA5A3E39 | PF-5F8C88F4E63C8F53; PF-91EE3D151F49EC76 | The later paper cites a conference predecessor, but the cited conference predecessor is a different 2021 work; neither paper identifies the other as a release or extension. |
| REC-F95950AEA19221D0; REC-6099EE66504F6EF2 | PF-A254A36430409187; PF-3DBBE522B68ECE13 | Both works use hls4ml in particle-physics transformer implementations, but shared use of hls4ml is insufficient without an explicit cross-citation or stated release/extension relationship. |

## Reviewer sample / re-review design

The controlled pass is recorded as `codex-title-abstract-screen`. All provisional A and C records, conflicts, and route-boundary cases were individually adjudicated; material ambiguity was checked against the locally cached PDF and marked `title_abstract+local_full_text`. Obvious exclusions may retain `title_abstract` as their accurate basis.

The frozen repeat-review set contains every final A/C record. Within each of B, D, and X independently, records are sorted by SHA-256(`record_id`) and the first `ceil(20%)` are selected. This gives an exact, deterministic stratified sample rather than a pooled Bernoulli approximation.
The exact selected IDs are committed in `repeat_review_sample.csv` and enumerated below.

| Level | Available | Frozen repeat-review sample |
|---|---:|---:|
| A | 30 | 30 |
| B | 57 | 12 |
| C | 75 | 75 |
| D | 68 | 14 |
| X | 231 | 47 |

A second independent or one-week-delayed blind pass has not been represented as completed; downstream reporting must preserve this single-reviewer limitation until that pass is performed.

| Record ID | Final | Selection rule | SHA-256(record_id) |
|---|---|---|---|
| REC-804DE81A30D8BC62 | A | all final A/C | 0154f48f925c2e65fed54d057dced5502e033432e9272ce7ffa825df55ece1c5 |
| REC-12C9D1ED9EF711FB | A | all final A/C | 1a49e51497adc66f99635f05a604da71fa8aa61662c3f24183b5b326b1b8198c |
| REC-BEACC83B64B951BF | A | all final A/C | 3743fa26add8ef2062a6dbdd60a6d5ab55348ce553c986c92ef72de453457d61 |
| REC-6FA4AA8C0ADE1CF7 | A | all final A/C | 543487817de55abfd80b52268ebaa4ceabc321f9f7fd7463de192a5a61b21aa6 |
| REC-8038055899F288DD | A | all final A/C | 569e8221840ca7182093493686ea356a43500cc8069991d3bbbc7bd77f15dbed |
| REC-A8FC56A3513C926D | A | all final A/C | 586f8be99353950807036b6142a5f4caf854d9a36d33ac1d1a9c03d8f248a0d5 |
| REC-9EEECBE6F301F9A2 | A | all final A/C | 5be94fe918019cc76a2d665f4bca9c44c0e254d7515ad5f9b08cf0900943fc90 |
| REC-B4C13EE048139933 | A | all final A/C | 5e396bfe815b3dbbad44832a8f70fddfab76ee84ab171c6049ffd9877a39c495 |
| REC-D80BA185FF6CE5BD | A | all final A/C | 617566a76a0e70981ac886971ff4072b09441996ec678a7bd40a0e4cf85affee |
| REC-F7C40BB06A37B794 | A | all final A/C | 7081d6f93a40d16996fa2a4fe732415704dd7fc4c506908bdd7136aa107bf8de |
| REC-1C8427A2FAEFACE4 | A | all final A/C | 7c8209b4880448dd8d3dcfcbaa53cd6651fe4921b2cc7d052be3b119c8c290c9 |
| REC-F678D73F154843E5 | A | all final A/C | 84d489636861f87c4abf6065e36ad89216bf0fd946eebb78a04c77eee4ba0dde |
| REC-74DFFEF8FFD0B3C6 | A | all final A/C | 91ae5cc8f766b61bad450acf4aae5015433a4d574e17af4fc0d2850a52cd7037 |
| REC-C963AD29DE58DB45 | A | all final A/C | 928ea6b97fb61c3a70cf1d12f7e9f8b5f09e8b505436c6fdef216878df698387 |
| REC-795EC13A60CA2881 | A | all final A/C | a0f72d4f2ff027a7f538f45c7727cd8e3ea060202b5bd09297cd11805a591864 |
| REC-561FD75C12B8EF91 | A | all final A/C | a1b348125b5b8ee0de94a4fe1ff498a45932481396451cac15d9bd36c4ea1f2d |
| REC-3E83647529A0BF93 | A | all final A/C | a34bba66476f4ad5f5c7549c004748eabc3388ea6c6b0dc8c82281ed714fbbd3 |
| REC-A9B512BD33750559 | A | all final A/C | aba659cf3411b26bbf1c91e0cc38bb4636b01fb7cfe281c81b62f6e1e43fa97f |
| REC-36C4AAA4FD4ACA93 | A | all final A/C | bb05d1fe7f29fd304b7cf98848e2b3836749820589f8a250711385d97acdf5fa |
| REC-27F112DB592D26A2 | A | all final A/C | c8b396d704ef5c5b84bae1d4cb216ff805b7a3d706cf640d043721716f8c139f |
| REC-3ED97335A1D4DAF1 | A | all final A/C | cbbda38c4bd4d8b3951dc8d8ed765a6c54457c6a35be633679ec44a33890824b |
| REC-48B14D3F981A4130 | A | all final A/C | d98f092b3e212c223533322f310ee35574a3643ef3e88b388f85da000e3151bc |
| REC-1E3A0B27361246BF | A | all final A/C | dce09d929c018ae26c6c8c9efe89dd3f9a5256d19ababfbea2ba13ddd8c3f85c |
| REC-69006487AF098BB4 | A | all final A/C | e16d1da19cb5e658cdf39b248ec1fc730595c464f0faa537b188350323ce1aa6 |
| REC-9DD301C82F69C383 | A | all final A/C | e236c8566735c650dc7cbae39189b4c9b49fffa4c4461d10544dac797e77b039 |
| REC-DACDD99CB85CF6D1 | A | all final A/C | e2de341fff77bc478e8014f6e09c57caacaa2ac0227dd3fbb6a328340f040edb |
| REC-377F6DCA995797F6 | A | all final A/C | ea9f4d3b9bbe30b01f3f114f9c72a51f58c04c8dbb015646856807e38a80c255 |
| REC-614E448623940710 | A | all final A/C | ecef69a1b2e67bcf6f30624dcfeb37a0b3dbcd6d4bdf90bbce9088b15654b12d |
| REC-0A35BCF12DE7E299 | A | all final A/C | edcec112a1b6795422840d2c66d6cb412a59bfeecf9d562900510db76cd17595 |
| REC-136E0A6CF2902F8E | A | all final A/C | f722142b1b386e2d51293b4295001521c2bc912c00cc58d39a2fc766bf07db82 |
| REC-CC1778CFFA15521D | B | lowest stable hashes; ceil(20%) | 003ef2caf21772ca3ce89f82fc2ebbe0d9b87cdaefea1a4de500a607894e8736 |
| REC-20E17694FEA9B59B | B | lowest stable hashes; ceil(20%) | 03d94e125dd80af1a816e19847713e86e62cea0ddb533c13f74fa46133e36276 |
| REC-5379D6B857EA5D12 | B | lowest stable hashes; ceil(20%) | 17a0a20aece62821c799415dddbfa4d5b9c010539874ae391aeef368d4a2cce8 |
| REC-E1A7182426E47166 | B | lowest stable hashes; ceil(20%) | 1ad08f6aba5aa02ae512147e73e29d21dd08ec2f3f6deb35d0f171421801a70c |
| REC-969D3C59E6AFE5EC | B | lowest stable hashes; ceil(20%) | 297ff14654635be29d81e4049cb97d93db3c7cba956750a79d12af0a70a78a05 |
| REC-00876C5760C7308E | B | lowest stable hashes; ceil(20%) | 2c89087ad30358ee35ab485bf7397ee3e8a2cbec9aaaa5871e87b7095265dec2 |
| REC-66B094C6BAA51FA7 | B | lowest stable hashes; ceil(20%) | 2d44fcce8d9826e3c047997beb93425c25a38beb5a828cb1ac7633f4d603bb44 |
| REC-8539603CEC57E49F | B | lowest stable hashes; ceil(20%) | 30e9fbe10b8e68774a2220c4bf312e0171f67aabfb3e3d2a651edf652b126377 |
| REC-2591DFCD2FE56740 | B | lowest stable hashes; ceil(20%) | 33fcaa9884545edc06b7f3cdb5f86501a407cfcd01d1f0c5b6537a1a307d6535 |
| REC-09886EF1B7D2452B | B | lowest stable hashes; ceil(20%) | 38bf32f01373e3f9bfc0f73db83626ce8eea6096411ef3f9daebc5bad53f19bc |
| REC-6C5ABE261E433D60 | B | lowest stable hashes; ceil(20%) | 3b8c5897c48327f634f44a294089a73c8a43d31e91cb8816f88ac5cfea859ccb |
| REC-7EB569AC45BB6577 | B | lowest stable hashes; ceil(20%) | 3e70f9d5f5091c07af9ead0f8013e98e63da6f9739dfe8cac1a9806e1ff5b5bd |
| REC-949433116AB006C6 | C | all final A/C | 04c9e3214fc7c3f0eba66cec7b57ad7fac128aa722c2e7628165a746c0cd7377 |
| REC-78E9518BF6FC6EBF | C | all final A/C | 0673cdf1421e115953867322a04d0f51fc22b987baa173cc354f0e4edf047ff3 |
| REC-8CA067D69DCD7740 | C | all final A/C | 07267f46fb72a6f467a8ce5895811a9af522cb248fb13e8c741ff7d27e4f729c |
| REC-77F2744384901A06 | C | all final A/C | 084846f91cfbbcb6f6d5702e360ed6f7df712e725ad0333f83870ae4820b4fee |
| REC-D9F3C753FC29AAD4 | C | all final A/C | 08fab232b669e96ae241a6a20eed349ebb3ef1dfb88eb401aee1fbed882bff9b |
| REC-6099EE66504F6EF2 | C | all final A/C | 1088af5881ecbed89d0fd12402ec27451cbdb3efa8243a1243aad8c6b232efe0 |
| REC-A47AFFCD278380DB | C | all final A/C | 1188f93214a494f8e017aa39d7b34737d9f06cf9361e519c900ab3220926ab57 |
| REC-B7DAC6E64AEA32C6 | C | all final A/C | 13dc055f6b2873846917509297a6817800d4e36c657048c5773c4ae89a8398ee |
| REC-D5344767957D09B6 | C | all final A/C | 16be8a034354171563be1f52a6970b359eed4b829bbe8296aff577ea6980f2a6 |
| REC-525F07C62996AA0D | C | all final A/C | 16dc17039a44a99355b3587184bf30827886994c3ed1da142042e5c7e13577e8 |
| REC-F4379DB7478366EF | C | all final A/C | 1cd43d6ebfe7e2f2123f1fd0622e262aa5e7a44c700f84c221c58b77c1c9367a |
| REC-ED5450FF15872377 | C | all final A/C | 1f4a9ae690a421dcd78737b1c68bd163966669069d3f01146ad8ffa6dab3059c |
| REC-03B61755E4BFDD6B | C | all final A/C | 2812841b4b991927d7efa6040ef8270567fbb280f832cbff366f00df61e323b6 |
| REC-7C4BA136157B6978 | C | all final A/C | 359ff56d3a0f097743cdc1ad84fd30767dfc3eca441da56ce3bca0f0c14a33e8 |
| REC-A0B5993AEECCF0B8 | C | all final A/C | 3a37bbc235ad6733d9533ed4b94fa05673c23e5e964a864041daedbba3ae9025 |
| REC-3C1BB60FF7107D12 | C | all final A/C | 3cab3d32cf889a6ed5ac5a06fe1e6fd6488787c79717d12d5b89f7baa1a9ff14 |
| REC-EB4A8C6C964584F8 | C | all final A/C | 3ccb7f61909fff3d7ee19fc16fb4825c28f023078a3e83ef2edeb2a89816b35c |
| REC-32CC94372EE77D83 | C | all final A/C | 49843e6b36f898d36adba655c5f1eb4aa221e3c8ed79b1ec15235bdb8462b0a8 |
| REC-B9BB1B48E25209CD | C | all final A/C | 50b1397a5a82974e6e6077da104f39f1c177899b9ad6413366ff6920c5110a74 |
| REC-2524EF73E57121D9 | C | all final A/C | 5333e781778558b3574d95046456387aeece9574a857f5beb930dfdba7e94b5b |
| REC-F73FEC8CDF1AD512 | C | all final A/C | 5364cb92405d533bb116f88e6f9a91ccc4ee0815b92a81117a679ab5f0b35055 |
| REC-A4176B89BC21CA65 | C | all final A/C | 55dd95aafb8a7368963dd22d3b5ea0f3a473aad9b6f0aab6ae82a9abd7c410f1 |
| REC-FD5A471D9856BBC7 | C | all final A/C | 5c4897c26c108340411d6dd33e2cb5878197e62a4a8bd33a86fdb53a20effa3d |
| REC-4677DAA8E1C4E7A9 | C | all final A/C | 6262379dce0876e725d83611cb4d5e08c9e3fbb583f933540f748e09c8874f0f |
| REC-0E5CD4ABE22322D8 | C | all final A/C | 674cddb57508d5cef4865417b18fd85dcbb93231a406a018f353012b3bbc3069 |
| REC-856C24626DD738E5 | C | all final A/C | 6cef5028f277834a46949ae99f189de01aa5f585c94d382550321685dd46c912 |
| REC-07755277A14E36BC | C | all final A/C | 705e62583203237a6873c3dc134810b9ff241f3a55cc6a4e55234b58cba5e01c |
| REC-22B8F133078A7448 | C | all final A/C | 769af53322c4efb1906d0de49b76cbb953aacf070e6712cfc4804fcab7c5b03e |
| REC-397AA2E8B322E5B6 | C | all final A/C | 76acbfcd99e4f225ae023d72eb8d4883c524dbaded3d6acbcc56fa3cc3ed8d32 |
| REC-27EC4FCAD057D2AF | C | all final A/C | 798576da3360cbe17b834de2c808eb98d306af11daa8ccc7f8ed663cb859cdfa |
| REC-18A9873A1ED2419D | C | all final A/C | 88e810112c6cfb1c4abc10fc4a763bcf25811bcada48db6e08cff53c907d1659 |
| REC-EB5B8D6B828622FE | C | all final A/C | 89693455549ab2564c345b073e89c20eaf2305764194a4a0238d81e17ef5c2f2 |
| REC-7A1FA14A8DCA183B | C | all final A/C | 8af4153ee2c14ac442f42a60f7f29e79b4f36bc0f62bef58e72cf5821cb5890e |
| REC-478BAE4ECE99CA8F | C | all final A/C | 8bb80f97035c469d415e9c2d711ba3920ef64891f4db15b35f8260ed34a52505 |
| REC-ACAB157CC9F0D857 | C | all final A/C | 8fbae8318b23cb6d8bd87cbd2c9bf278bfef91f7f00afef818f1c7d610a007a6 |
| REC-A2503EFE5BB738CE | C | all final A/C | 925641344ed78e9499af1791ff5b6f644a4dda6b20956b7862851c94b30cce0e |
| REC-A53433EACA5A3E39 | C | all final A/C | 93d0810bfbbf88fee695dd3119188e868b41a07dae25e0771117f8c9edfbe5e4 |
| REC-A9265AD0192938C0 | C | all final A/C | 95a79f278cce5a255fa15e45016c1bc50b8552e6581e68c808fd3410921ffee0 |
| REC-1C939925CE9E62FF | C | all final A/C | 973a8436d1edb6aec95bda60f0d9839c0e8e6a106894d832f22de3cb47061c15 |
| REC-6861DF774D045B5D | C | all final A/C | a0aa3299ffd4b55e8f30d8533e9234201add86e3606bb46a5b7ea3752071dedc |
| REC-0AB8E04D7DD6C72A | C | all final A/C | a23779f50004e7dd3fd5b6975c4dadb214388c8a8474178d2198608ad8bb8bb1 |
| REC-7D9A3E658DD7EEE6 | C | all final A/C | a2765c794787b27c802cbfe2d9c3cb22293991964f2034ba30d8479499beda6f |
| REC-1D91E09883329FFA | C | all final A/C | a39d9a95839eb26b324971086b36cbf7087c21ad8fefa9772cba9bd57f97a44c |
| REC-053F8CE5FE90B1D2 | C | all final A/C | a55c651f3ad0f7d8455f921ddef2c6903456d431385b29ec076231770d0371e7 |
| REC-FEAA09BB86B0EBDA | C | all final A/C | a89b5aedbb0e756d0ff3f470fc5a006865f4e746637a2c567bd79814ba6fa6c3 |
| REC-0ED11F871A636313 | C | all final A/C | abc385beaf1958071627d2fc0b253f9f2724c9d5b76ad054ac99328c83ce83ad |
| REC-F5EC31B9648B775E | C | all final A/C | af1beb366a84bd62bbd935a314293b888332582b4e115ddb1ab62ab602d9d8c2 |
| REC-4810175E48EBE449 | C | all final A/C | b71a12bc8dbbfd571981a1ce5eed85e06af84bf16e8d00c3e06b9559ccb7f001 |
| REC-5C4ADC39D64D338C | C | all final A/C | b98b10173c8823ffc61bbfaad27a4ef1d162d2f26f4c39f7189db9d1b9ba9611 |
| REC-714959A473E278C1 | C | all final A/C | bc85abc7c414b1ad05bfe1e14950ce65d147bce6219196e45217c44f5c8ef664 |
| REC-D65706651462F659 | C | all final A/C | c124167e5add090e7d7ef1443f70d1d7b7c3c879a1a3e6f7bc77f8cf9afc2d4f |
| REC-794B4806F5632532 | C | all final A/C | c4538805c17bb756b16de42f5a6c03602675c3124cad065b16c61f5a5e1f729f |
| REC-EABB5667866DC451 | C | all final A/C | cc16b9a0f03a626050a3d45b840f238d7b1a78ef6bf0bce1ac8836f1a818bedb |
| REC-0F2A03A0DF86FD27 | C | all final A/C | d2ac7dc7828cc30d88463137df8103521205beff17add2a14ffa4904866990a1 |
| REC-6FF78E8941C82A36 | C | all final A/C | d411f849602ddb4c2ff75e98c727abe72537c2bd571543ab7931bbf3935ee281 |
| REC-43EBA3F96335295D | C | all final A/C | d7d399b194f3b590bc2c52ae65b683854407206e6efe207fcc677d89d0ae5170 |
| REC-F9910295847671D0 | C | all final A/C | db47abdf312e1c33cac826a8f829c1cc175698501face26f13bf54d3eab8b510 |
| REC-48C8BD37C529BFD7 | C | all final A/C | db653fe81637438cee394d1440ba534874ea11545ac020294172f233f979db32 |
| REC-AC7A77515D490E82 | C | all final A/C | df0318d2edcfd441c12afd8a28a6e21af5d84bb22c468001f4555cc889c4e78f |
| REC-55C6CBE6658E4D6D | C | all final A/C | e10d2bd8734a5a8626ac1c0ac5b19fb71ed9b9c1aafd34c6212b02693820d1f3 |
| REC-88F29B4B825641C8 | C | all final A/C | e284c7e0d2f511975cdedd3f568e323415123bb04d7efb17c57092b745942517 |
| REC-1B391A89C0485DFA | C | all final A/C | e76ca777606dae51d022b806d763398a0b28420494f2d2d6043f3cb65969c281 |
| REC-B43B25ED6C25AA2D | C | all final A/C | e7d0e6cb21e15e0b172096fc1949ceaa39935e825d1a9fd1d5f3f9111c9161fc |
| REC-193C307FD04D33A3 | C | all final A/C | e7d5b9c603ab1c6ecf47f9e41096a4cc135551cea45ae6c64f02ebec2f779f8a |
| REC-462BCA4753C78ACE | C | all final A/C | e994fa217d820fe46ca6a7239bbfc11e18ce71b7645800fd02f0645ccb8473a1 |
| REC-501B131BCCDB0BBF | C | all final A/C | ead196538ead217a2315b9c730d6c54730a8ce5e2058a6debf6edea80efa536b |
| REC-3197E8A9160CF79B | C | all final A/C | ec1f3835d1737b4ec7e8cdb9fcbcd326dda894fa0752a6d4baad1f672acc3779 |
| REC-CCE2E4EFAFB5F4F8 | C | all final A/C | ec3a1dda4b8ad17b93743b6e7ab1bbe6ff7c2c9fff4c29cb5f55569fcfb3e5d3 |
| REC-38831414C8CA227A | C | all final A/C | ec7bee73d212e888a73781ef3366b156037c7bfa6ecc75a101dec14e7e2a5e5c |
| REC-BCFB3C4AFAE3811E | C | all final A/C | eea9c79fa86878ba0aa29b9c3ca9a289f41f423b977cfe45934d20b4196b8c77 |
| REC-2861404557D1782A | C | all final A/C | eebd41a0c917c4768e633a56f2db64bee9e6ac019eb53dfc660e7a094899a9cc |
| REC-03737A3859757540 | C | all final A/C | f2094fb5495ffe07f237b8b0adc63fab671bb07f646809463a3dea5978b6e649 |
| REC-908FFDB34685B693 | C | all final A/C | f23c2d3f2b09453053b84c3c8e5b4ee0fd01169b6af6ae6f086e2712663524dd |
| REC-89287D342E6CE922 | C | all final A/C | f7bb1c315c9513ca2a0e587e198153d383cff501e7389915a43828567f00ed92 |
| REC-F95950AEA19221D0 | C | all final A/C | ff56ff204d5876688d2ff58d364be069055f250f5422c08cf70371a7f00cb92e |
| REC-532363BE02AE8521 | D | lowest stable hashes; ceil(20%) | 016028d1606e48f4f00050b2129304f8b9caafe7ebb404724e593f401af88788 |
| REC-52DB9C1A84C344D5 | D | lowest stable hashes; ceil(20%) | 02e3cb04168bdd853c35ee4d577a8c63f3c719ca61ad1f94ed20988a49b6e6c5 |
| REC-4C1B20A6E3DE81C3 | D | lowest stable hashes; ceil(20%) | 043ba2068422d2d7667c2eb0bfd0f664bfbe6ea2a44b2a2186379f3e569b223f |
| REC-A3A7195BE5E5F981 | D | lowest stable hashes; ceil(20%) | 0730d94f1faffe1e5caff380cd73ce2165c787a74161114175b44aebebfbdcd7 |
| REC-5F3EF920419354F6 | D | lowest stable hashes; ceil(20%) | 16a3f379becf832adf7aa737b2b9da10a4a5d3a41d40a5b21b09dbe4f7728100 |
| REC-F03EEDBB96B92664 | D | lowest stable hashes; ceil(20%) | 20095dcfbb515dc4e0f54f659d939e5a7b92c845af9ee3332f5ca4f2381cfe51 |
| REC-C89D508C9645DB7B | D | lowest stable hashes; ceil(20%) | 216914a5d9b159e3c97eea254705c48c9cff46e74b780c2b62b9f27abf464da3 |
| REC-25D1D3FB6640874F | D | lowest stable hashes; ceil(20%) | 24598d19210758ba38a8eccc4ea3431899bdc342f80cd63f71e080fab822cb0d |
| REC-E7364B5C13D3ACB6 | D | lowest stable hashes; ceil(20%) | 32fac64a074ccb39e3f6a02409e8e050eb18431d66e22125012eb99219a59b59 |
| REC-952DDF542BB99BA4 | D | lowest stable hashes; ceil(20%) | 37eb9a4023c0a2ed39ad584a97bf27f0f5bdb75045bd6751b5724661affa275e |
| REC-939579D7FA707D17 | D | lowest stable hashes; ceil(20%) | 3c1cfb27ab6b59855df2a0fc947dd8eda2593b87dfa91643e1bbc75821ce5a08 |
| REC-BCC3E9EFF1B93E62 | D | lowest stable hashes; ceil(20%) | 3d07e20c120729be9e7c81e457da04b51cfdf6380987ce7d306584b51aaabaf5 |
| REC-50F6BA42D72FB565 | D | lowest stable hashes; ceil(20%) | 4627bbcbfe1ba7bb294f6324f85e1cb75ce73d8fa941496d3db29ae027d3eb4d |
| REC-EA4C0FAA7D7F488C | D | lowest stable hashes; ceil(20%) | 467d637f1a5f438cf6ea145a5db7f51fdd23d5858b8607326dac38e0ecc9dae1 |
| REC-72DC5BAC04D90C54 | X | lowest stable hashes; ceil(20%) | 0139482664cc6d3ddc57ca62c5d6d26d5e9fd6896b295dfc80ac6ab76e35588d |
| REC-F6A6EB8FD7251DAD | X | lowest stable hashes; ceil(20%) | 0201d83e77165afc2ef75df70a201764131fb4eff6f262dadd892504adb77c91 |
| REC-366778764662CFF9 | X | lowest stable hashes; ceil(20%) | 03251b78f491ccff406e8575890a3e31234d4edfea6dc1c5af7e6d10882980f8 |
| REC-55AF74F48541DBB8 | X | lowest stable hashes; ceil(20%) | 03a819e438c4121853b6b8feee67b1d34f90ca2c2875b883335d9d3bb38cef21 |
| REC-6959A58704BD803C | X | lowest stable hashes; ceil(20%) | 05e3f9ec4680c080d4e4865344221e0bce5983b7301e194aac25b01407084154 |
| REC-2342F9BF3B1AB602 | X | lowest stable hashes; ceil(20%) | 0652d93dc13b88618a32044af6e9cbe047defbf8cf7397af7dd914d64b549406 |
| REC-03DB065D26928ABC | X | lowest stable hashes; ceil(20%) | 07eed84e7b19b4d84dd7bf2fcc23a74ab1d822906470d5e437f8b227a8815def |
| REC-DE3DA0389AC93D33 | X | lowest stable hashes; ceil(20%) | 0865c46561b46f1f57b561d03dccdc85f2566f274774463cc97bd59e1ea7ee61 |
| REC-1C2BC4282AF1A5AD | X | lowest stable hashes; ceil(20%) | 08c70db9c38c8fd7e9ac6674ed2a12930494e519fb98889a163dced87670ff34 |
| REC-641104861DB63DFC | X | lowest stable hashes; ceil(20%) | 0a1fbbd9bcc0af75e0b02df90028cba4636550e21f1a4e292eac34cdcab6138d |
| REC-BE790A13874474BF | X | lowest stable hashes; ceil(20%) | 0c3eacd3cb42e3dff48ae6ee3d167aa694ac896c18ab46bb24927b3d776baf54 |
| REC-70FF806962EDBD4E | X | lowest stable hashes; ceil(20%) | 0c40ca296579f793cde33e8ee4c4891260be20ee0e488313b13abf061693a243 |
| REC-3997FA16D99A7164 | X | lowest stable hashes; ceil(20%) | 0c5876e71d35c1a4a8a9fd1d23759820b656a4b676e0222744fa0ee30ba626c1 |
| REC-09DEF0F386F31DC0 | X | lowest stable hashes; ceil(20%) | 0cc1892518243abdbc7608d3d24876d98938c0bf46be64a8df15b1bed7460d05 |
| REC-0C1041A492BBE78B | X | lowest stable hashes; ceil(20%) | 0d23c125fbbf7bbc55e2d7917b9ff00702bb29dd484ddb9f9bf66605aa1a28c7 |
| REC-3D8BAE87506248E2 | X | lowest stable hashes; ceil(20%) | 0d2a08eacb2f8b917de4a1707184e618e38a527393636c74230028a4963f2c0e |
| REC-DCFC6B023D9EF9F8 | X | lowest stable hashes; ceil(20%) | 0d9869a0e3ddbeeec088ac5157bf62a88191829193e7a21fdba5ab0c57fa6624 |
| REC-C5FFB21E3A3121F0 | X | lowest stable hashes; ceil(20%) | 0ea70d682c20a538a423fd40f3ac85a1146b6c9aa6385db5dfb19f9b5446977b |
| REC-EB622A25C915E5D5 | X | lowest stable hashes; ceil(20%) | 1077cc27b9dbb0e76f418f957a19a4dd3a9ae61234ebd4ab443e4336e857ff05 |
| REC-DCFB7010F089D86B | X | lowest stable hashes; ceil(20%) | 11b82327e2bbcbfb176e0dd0141bbf27bff16454b6c9cdbd568356afeab68cda |
| REC-58EA590C04E33E29 | X | lowest stable hashes; ceil(20%) | 1290984a89b382e5866f6d008ef49805fdd1a06bada208d70a7c9a214f47c580 |
| REC-F88C6066A8140556 | X | lowest stable hashes; ceil(20%) | 12f868132d84c877668e462f9356962752d2e6876c5c19b80d17327e80d0db4b |
| REC-23229B1B1C344FB1 | X | lowest stable hashes; ceil(20%) | 13666109d1e8df37d3b01f1c6f2210dd0d26a3bcfc72da9913bc586d0c3adf51 |
| REC-C048DE10B21EE1B8 | X | lowest stable hashes; ceil(20%) | 14283b78961a8bd0e75964533728758efe8ef46334f2fc35cec4148bfbab6926 |
| REC-6001BF8DB461EEBB | X | lowest stable hashes; ceil(20%) | 147a4db2f932b9d42c467735057ebaff0358a708a5b8ff500986b57475ae3f4d |
| REC-D7B209C7FF8D65B2 | X | lowest stable hashes; ceil(20%) | 150f543e36d36727ce8b864fd190bddb695f098efb3b9625725b9cd9a4a35d69 |
| REC-0A53F8CDE071DFAB | X | lowest stable hashes; ceil(20%) | 16239b4d93e0eee1d11f88c66aaf92cc84db7d90bf9ddb4031d51057f66d8a4c |
| REC-24F11AD2640DE71D | X | lowest stable hashes; ceil(20%) | 19f5686959a45a24e3147742f5419476e0182a7691f961f8d89310658483e7de |
| REC-030A349885C6007C | X | lowest stable hashes; ceil(20%) | 1ad5564f25acf064b894ba2d309333ff6d1190543ee6ddea34202dff6717be84 |
| REC-28937A3B820B31B6 | X | lowest stable hashes; ceil(20%) | 1b294a2d3bfb3bf1ce3fe0552fe574a8ec1c30d3a12b7be98f5443c75fc22d29 |
| REC-05CE8CF08628F250 | X | lowest stable hashes; ceil(20%) | 1bc18618fbc2578aa0b0139c5f1f864b460bba2aa508a8673481eb237d86cdcf |
| REC-B1B744172924155F | X | lowest stable hashes; ceil(20%) | 1caeed2e683e919fdb91b4f29dcfef359de55b62ec2b3f67513d132ce3834f46 |
| REC-688C296AB31CFA2F | X | lowest stable hashes; ceil(20%) | 1d29b54f5b29549476e189bda501327a9af5fbb1bfb5e9e236ee4b1129d47541 |
| REC-3BF9C4C1B606866E | X | lowest stable hashes; ceil(20%) | 1ed064754b5996ea2882a541640e5b068b23fe2dd064864d6be0cd33696c5d11 |
| REC-EA143A4A252C95C7 | X | lowest stable hashes; ceil(20%) | 21314b2f4925c4482591545dc5edfe80cecec1bc3156caf2473aa857cb4c09a2 |
| REC-5FD6C290B90048C6 | X | lowest stable hashes; ceil(20%) | 221d4f0b94090672f771afed5529977acec6434a2f9b6175e05f19f35f7756f1 |
| REC-0FC0CC9FC50469EE | X | lowest stable hashes; ceil(20%) | 222e3401cf4291257a2890a0ab9f30a2f848ab4faa0c2e180510a4fb26478077 |
| REC-D675CF108CBF8BAA | X | lowest stable hashes; ceil(20%) | 227b756559009085fa757bd85f8371caecc603cdce3eb6d9091563e51fcaa44b |
| REC-AAAC49C19C9048DC | X | lowest stable hashes; ceil(20%) | 22bf9f055eb3cbadf70ea1906a21a6db9d68530e3f7d9817fc681b2b818744db |
| REC-61B0E818AB02E4D2 | X | lowest stable hashes; ceil(20%) | 24bffa21a0643e15b109bfb66606ad13f32784406953204530cb2ccf41c818e5 |
| REC-416B2DD45741AF37 | X | lowest stable hashes; ceil(20%) | 253528675cbd2d66c10259d33144b85682ec555cdc7020eccd1e28b80b807e88 |
| REC-C1B45DD5CFFDEF49 | X | lowest stable hashes; ceil(20%) | 26328c11c60ef5a661eb94f53dc24885e3b53f1aa49beb2699418c19e5af236b |
| REC-086BFC4543DB0A77 | X | lowest stable hashes; ceil(20%) | 26427c11840bf2f5c971e62da6cf9f4faa5934f2e632c715006fb7aab7a7332a |
| REC-BA4F44A6E9632049 | X | lowest stable hashes; ceil(20%) | 264d264cabcbd74177a33e3a5fd41f22542b4f8da406f5c2b5229b3d79c62834 |
| REC-2E8C2D5C8564F14C | X | lowest stable hashes; ceil(20%) | 28a5f262f9d93710247c793d5f7ea8feea93e73f144f7982a8352d5626f1e756 |
| REC-EAAAF4FE370E17FC | X | lowest stable hashes; ceil(20%) | 29bb177bbffa63f4681234031eca43bf40e70a4d8d667d3194405d7d95a7b794 |
| REC-366753D8F671C3E6 | X | lowest stable hashes; ceil(20%) | 2a491aa8902918517dd869199711e1e4757aec4dbedcf5d414d1fbb32fed26ff |

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
| REC-AAAC49C19C9048DC | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-AAAC49C19C9048DC:title+abstract;source_url=https://arxiv.org/pdf/1008.1673v2;cache_filename=1008.1673v2.pdf;cache_sha256=872b71dff54bb867c3d60638422151fb60773e2fc6ce2f49b769e3661995732f;locator=text-search="purely formal, to be simulated only" |
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
| REC-F4379DB7478366EF | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F4379DB7478366EF:title+abstract;source_url=https://arxiv.org/pdf/1504.05372v1;cache_filename=1504.05372v1.pdf;cache_sha256=8bc31794ab37585fbadeabbd60fc10796ef4ddbf2eb14c61c6b27b18519ce930;locator=text-search="TyTra architecture" |
| REC-24BB9609714294BE | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-24BB9609714294BE:title+abstract |
| REC-F73FEC8CDF1AD512 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F73FEC8CDF1AD512:title+abstract;source_url=https://arxiv.org/pdf/1505.01120v1;cache_filename=1505.01120v1.pdf;cache_sha256=d56a1b4367b62b0f3fb3d4dab972818219cf98ff59e897199239f7a43d0c0da5;locator=text-search="binary execution flow needed to support FPGAs" |
| REC-7D9A3E658DD7EEE6 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-7D9A3E658DD7EEE6:title+abstract;source_url=https://arxiv.org/pdf/1508.06811v1;cache_filename=1508.06811v1.pdf;cache_sha256=88043b2da5cfb9173d1893bcc8a9c749e318d3605c42cd4579005fe38a3a7c47;locator=text-search="VHDL code was synthesized" |
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
| REC-3570BA8F2CBFC43F | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-3570BA8F2CBFC43F:title+abstract;source_url=https://arxiv.org/pdf/1711.04471v1;cache_filename=1711.04471v1.pdf;cache_sha256=9d910d0dd4d14a58219146e0a67a58e822b55d171730259a875e6c9b71aa5366;locator=text-search="complete OpenCL-enabled code base" |
| REC-794B4806F5632532 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-794B4806F5632532:title+abstract |
| REC-193C307FD04D33A3 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-193C307FD04D33A3:title+abstract |
| REC-ACAB157CC9F0D857 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-ACAB157CC9F0D857:title+abstract;source_url=https://arxiv.org/pdf/1712.03411v1;cache_filename=1712.03411v1.pdf;cache_sha256=e12b2be6e6c8b1bcac5f53a3f9724f1636ca8f01989938ec2f7cc8c33c20f1f2;locator=text-search="complete, open-source FPGA design methodology" |
| REC-0E5CD4ABE22322D8 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0E5CD4ABE22322D8:title+abstract |
| REC-14F5886A00FF13FD | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-14F5886A00FF13FD:title+abstract;source_url=https://arxiv.org/pdf/1801.06541v1;cache_filename=1801.06541v1.pdf;cache_sha256=d8f204cb8f662a5f33d15ea0c4650d6557ec8c1ec9f056b5d00917313002f5a2;locator=text-search="automatically generating serialization and deserialization hardware" |
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
| REC-7C4BA136157B6978 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-7C4BA136157B6978:title+abstract;source_url=https://arxiv.org/pdf/2109.02484v1;cache_filename=2109.02484v1.pdf;cache_sha256=b5f7bce13f2db0443d2390c546971fc0a35bc222ba578d1c0dd9ee0918520c55;locator=text-search="compiler backend targeting an OS-level protection layer" |
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
| REC-AED6C450CC7834B2 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-AED6C450CC7834B2:title+abstract;source_url=https://arxiv.org/pdf/2205.03886v1;cache_filename=2205.03886v1.pdf;cache_sha256=813924582f03b063b5cc6302e2493d0ce4adc0a52cd481113b5e276f1eb0c039;locator=section=II.System_Setup&search=prototype_based_on_a_field-programmable_gate_array |
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
| REC-A2503EFE5BB738CE | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A2503EFE5BB738CE:title+abstract;source_url=https://arxiv.org/pdf/2210.12703v1;cache_filename=2210.12703v1.pdf;cache_sha256=8e500a1ead343cefcffe946862e25b4b0c9f0f9e0ace4f8d1874036976bc4a96;locator=text-search="eDSL to FPGA input representation" |
| REC-4C2E95DDB8B7F21F | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-4C2E95DDB8B7F21F:title+abstract;source_url=https://arxiv.org/pdf/2210.14793v1;cache_filename=2210.14793v1.pdf;cache_sha256=b045d48019b1b1d14b0f9daa9a84b7978cb5d2b1fc3dbcde49c6d96b2f7b8717;locator=section=3.2.Circuit-level_Implementation&search=layer-wise_implementation |
| REC-D2117C9C65232AA0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D2117C9C65232AA0:title+abstract |
| REC-B797976E8C3DD74B | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B797976E8C3DD74B:title+abstract |
| REC-461426DFCC1AA131 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-461426DFCC1AA131:title+abstract |
| REC-F5EC31B9648B775E | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-F5EC31B9648B775E:title+abstract;source_url=https://arxiv.org/pdf/2211.14547v1;cache_filename=2211.14547v1.pdf;cache_sha256=48d1b732365eb2ac766d26063c0f5d7ea4e8e5ec4ffade965beca8f0a1eea5ed;locator=text-search="integrated compile time and runtime environment" |
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
| REC-1D91E09883329FFA | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1D91E09883329FFA:title+abstract;source_url=https://arxiv.org/pdf/2308.06849v1;cache_filename=2308.06849v1.pdf;cache_sha256=e7241851c366d551d075cef45ac45257484cafdd67df0debd30740bc63b414bb;locator=text-search="Generation of HLS-based BayesNN Accelerator" |
| REC-5379D6B857EA5D12 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5379D6B857EA5D12:title+abstract |
| REC-A4176B89BC21CA65 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A4176B89BC21CA65:title+abstract;source_url=https://arxiv.org/pdf/2309.12917v1;cache_filename=2309.12917v1.pdf;cache_sha256=4c630272c06cb0f9264badec40c0d4543d0b1bfd7981cd3b146ab30d1162b0c0;locator=section=Olympus_flow&search=implemented_as_an_FPGA_bitstream |
| REC-03737A3859757540 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-03737A3859757540:title+abstract |
| REC-BCED24E48DF96CCD | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-BCED24E48DF96CCD:title+abstract;source_url=https://arxiv.org/pdf/2310.02654v1;cache_filename=2310.02654v1.pdf;cache_sha256=dec7727f4408387abe36faf8c4db15d31d3e1df087f1f6701b9d5699dff07d8c;locator=page=10,section=6.3.Extension_to_Mixed-precision_Quantisation,search=deployment_possibilities_on_embedded_FPGAs |
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
| REC-9DD301C82F69C383 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-9DD301C82F69C383:title+abstract;source_url=https://arxiv.org/pdf/2401.03868v2;cache_filename=2401.03868v2.pdf;cache_sha256=e0d38c8754516973d62749c846ebe63ea3984b569a1613b98340ef13249fd4da;locator=section=5.3.Analytical_Model_for_RTL_Generation&search=RTL_generator |
| REC-18A9873A1ED2419D | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-18A9873A1ED2419D:title+abstract |
| REC-5D437477A3B3F0CC | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5D437477A3B3F0CC:title+abstract |
| REC-AAF5141FDB3D1BC0 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AAF5141FDB3D1BC0:title+abstract |
| REC-EB5DF096D8CCF2D9 | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-EB5DF096D8CCF2D9:title+abstract;source_url=https://arxiv.org/pdf/2401.10417v2;cache_filename=2401.10417v2.pdf;cache_sha256=1c8e12b03b5e5a4480afd4827949b8682dc12ee57fecd0aa4331da7adef24ec0;locator=section=Table_3&search=vision_transformer_models |
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
| REC-A8FC56A3513C926D | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A8FC56A3513C926D:title+abstract;source_url=https://arxiv.org/pdf/2405.00738v1;cache_filename=2405.00738v1.pdf;cache_sha256=d4d5f70aefc7116006fb7d87d3db35824d057ada6b4225ad6dcff7a1130096fc;locator=page 3 section 3.1 Implementation search phrase host reads the output and performs sampling |
| REC-EE5E845B0F2772CA | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EE5E845B0F2772CA:title+abstract |
| REC-F03EEDBB96B92664 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F03EEDBB96B92664:title+abstract |
| REC-CB909EA926A5AC72 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-CB909EA926A5AC72:title+abstract |
| REC-DC3D7EFD2F28A99F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DC3D7EFD2F28A99F:title+abstract |
| REC-F65FD886EFF07883 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F65FD886EFF07883:title+abstract |
| REC-76DBC4C4BEB42ABB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-76DBC4C4BEB42ABB:title+abstract |
| REC-B98F65C951D2121A | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B98F65C951D2121A:title+abstract |
| REC-A53433EACA5A3E39 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A53433EACA5A3E39:title+abstract;source_url=https://arxiv.org/pdf/2406.14593v2;cache_filename=2406.14593v2.pdf;cache_sha256=9aa6db50684b46ca348ff20e9dc808a26c77aaedff49455dbbc951cc8e4b95f2;locator=text-search="extends our conference publication" |
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
| REC-1E3A0B27361246BF | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1E3A0B27361246BF:title+abstract;source_url=https://arxiv.org/pdf/2409.00661v1;cache_filename=2409.00661v1.pdf;cache_sha256=5a86cbf7e409b775e6b559e98d7d9305d851c45f92ca1f0a0e4cb5e731f52097;locator=pages 6-8 section 5.4.3 search phrase GPT-2 inference speed comparison |
| REC-78DA1BBA4525C9E1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-78DA1BBA4525C9E1:title+abstract |
| REC-6099EE66504F6EF2 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6099EE66504F6EF2:title+abstract |
| REC-2861404557D1782A | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2861404557D1782A:title+abstract |
| REC-D80BA185FF6CE5BD | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-D80BA185FF6CE5BD:title+abstract;source_url=https://arxiv.org/pdf/2409.11424v1;cache_filename=2409.11424v1.pdf;cache_sha256=863004facf1b502140ad2d0c556897f42d8773d2218ed83ee84ca5a7ed574796;locator=page 6 section IV-C Performance Analysis search phrase tokens generated per second |
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
| REC-C048DE10B21EE1B8 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-C048DE10B21EE1B8:title+abstract;source_url=https://arxiv.org/pdf/2410.23083v1;cache_filename=2410.23083v1.pdf;cache_sha256=6a3324e8c69c21e15a2f37e28d4ac42b276637c3a69ca73ae2c9d1642b6ed674;locator=pages 2-3 sections 2-4 search phrase finite state transducer |
| REC-36C4AAA4FD4ACA93 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-36C4AAA4FD4ACA93:title+abstract;source_url=https://arxiv.org/pdf/2411.03697v1;cache_filename=2411.03697v1.pdf;cache_sha256=525c9c6acb16aaa5e833ced7eae3252d03863f3f0189782c654aa2f870547c47;locator=section=Table_7&search=only_measure_the_pre-fill_stage_for_GPT-2 |
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
| REC-12C9D1ED9EF711FB | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-12C9D1ED9EF711FB:title+abstract;source_url=https://arxiv.org/pdf/2501.19135v1;cache_filename=2501.19135v1.pdf;cache_sha256=f5537770a482adb8996867a7ef57a9358263195f3d58f81f019806bb048d5aeb;locator=pages 5-6 section V Experimental Results search phrase whole network |
| REC-9C5B33458C163E1C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9C5B33458C163E1C:title+abstract |
| REC-E1978C76FDD941FD | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E1978C76FDD941FD:title+abstract |
| REC-37D418A5B0CD24F0 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-37D418A5B0CD24F0:title+abstract |
| REC-397AA2E8B322E5B6 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-397AA2E8B322E5B6:title+abstract;source_url=https://arxiv.org/pdf/2502.05850v3;cache_filename=2502.05850v3.pdf;cache_sha256=9526c20c6b00cdf37ca5b8110912bf3e11e99f68490baa8387bb80d2745cb535;locator=section=Relationship_to_Prior_Publications&search=In_[36],_we_propose_MetaML |
| REC-7DA72502BFE51076 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7DA72502BFE51076:title+abstract |
| REC-614E448623940710 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-614E448623940710:title+abstract |
| REC-BCA6BA5940337BB3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BCA6BA5940337BB3:title+abstract |
| REC-561FD75C12B8EF91 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-561FD75C12B8EF91:title+abstract |
| REC-13722C8F89C40F15 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-13722C8F89C40F15:title+abstract |
| REC-9EEECBE6F301F9A2 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9EEECBE6F301F9A2:title+abstract |
| REC-688C296AB31CFA2F | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-688C296AB31CFA2F:title+abstract |
| REC-507EEB2F277BB4EB | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-507EEB2F277BB4EB:title+abstract;source_url=https://arxiv.org/pdf/2503.01138v1;cache_filename=2503.01138v1.pdf;cache_sha256=d6f4a35545e1f583442e9f4457d30dc392ed55e80fab03372c8c4d10000aeff4;locator=text-search="release the source code and datasets of DB-Hunter" |
| REC-D97610736AA58551 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D97610736AA58551:title+abstract |
| REC-4BEC5993271B5F05 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4BEC5993271B5F05:title+abstract |
| REC-29CEB82FFB7D60B1 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-29CEB82FFB7D60B1:title+abstract |
| REC-8038055899F288DD | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-8038055899F288DD:title+abstract |
| REC-E47480B3889FF9C0 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E47480B3889FF9C0:title+abstract |
| REC-EA4C0FAA7D7F488C | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-EA4C0FAA7D7F488C:title+abstract |
| REC-AB2731AA91BB679A | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-AB2731AA91BB679A:title+abstract |
| REC-A9B512BD33750559 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A9B512BD33750559:title+abstract;source_url=https://arxiv.org/pdf/2504.09561v1;cache_filename=2504.09561v1.pdf;cache_sha256=ec1414a11856842e6ae5bc705891fed12649b8ad422e464b6da5bd0b6fd2e937;locator=pages 2 and 5-6 sections III and V search phrase end-to-end inference through L transformer blocks |
| REC-971FEFE09F7F6727 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-971FEFE09F7F6727:title+abstract;source_url=https://arxiv.org/pdf/2504.10411v1;cache_filename=2504.10411v1.pdf;cache_sha256=88b89ebafc1a9a2a804ba2816a000ef0425101e59875eaa2edcf36f2016e346f;locator=text-search="image data" |
| REC-C3B39CB94F1B4C76 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C3B39CB94F1B4C76:title+abstract |
| REC-4A2A4509290BC306 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-4A2A4509290BC306:title+abstract |
| REC-74DFFEF8FFD0B3C6 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-74DFFEF8FFD0B3C6:title+abstract;source_url=https://arxiv.org/pdf/2504.16112v2;cache_filename=2504.16112v2.pdf;cache_sha256=213bc5f4839143796fc7f26ab61a4de490f60adccd62dea250305148fa88d733;locator=pages 5-6 sections V-B and VI search phrase end-to-end execution time |
| REC-0A35BCF12DE7E299 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0A35BCF12DE7E299:title+abstract |
| REC-7EB569AC45BB6577 | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-7EB569AC45BB6577:title+abstract |
| REC-27F112DB592D26A2 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-27F112DB592D26A2:title+abstract |
| REC-58388E3A8C4C4CC3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-58388E3A8C4C4CC3:title+abstract |
| REC-0084AA0272388588 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0084AA0272388588:title+abstract |
| REC-1C8427A2FAEFACE4 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1C8427A2FAEFACE4:title+abstract;source_url=https://arxiv.org/pdf/2505.03745v1;cache_filename=2505.03745v1.pdf;cache_sha256=9d183689febd28655e39b0b35fddc464d32306e4138f8817d2c269f96f1c4aca;locator=pages 9-11 section VI search phrase input and output token sizes |
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
| REC-BCC3E9EFF1B93E62 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-BCC3E9EFF1B93E62:title+abstract;source_url=https://arxiv.org/pdf/2506.12971v1;cache_filename=2506.12971v1.pdf;cache_sha256=823b6d38241eaf7b6a25e2c92fcd0c4fa68e8e52501ccb0ef670bd63f2a789ac;locator=text-search="partial reconfiguration" |
| REC-69F340FD9A5D9F2E | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-69F340FD9A5D9F2E:title+abstract;source_url=https://arxiv.org/pdf/2506.15613v1;cache_filename=2506.15613v1.pdf;cache_sha256=673f4408a1365c570b77b8e1c9194d4463fdba8a57d641ef0960c3da879ff4ea;locator=text-search="prototype a CXL-SSD" |
| REC-DCFB7010F089D86B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DCFB7010F089D86B:title+abstract |
| REC-A9265AD0192938C0 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A9265AD0192938C0:title+abstract |
| REC-09794B47FC51DBAE | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-09794B47FC51DBAE:title+abstract;source_url=https://arxiv.org/pdf/2507.01035v1;cache_filename=2507.01035v1.pdf;cache_sha256=87b6c8071413c6eab1235b197913c601ad5ee6b8bf9b7d46f9e8771f300316ae;locator=pages 2-5 section III Research Methodology search phrase Hybrid + FPGA + DeepSpeed |
| REC-804DE81A30D8BC62 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-804DE81A30D8BC62:title+abstract |
| REC-DE3DA0389AC93D33 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DE3DA0389AC93D33:title+abstract |
| REC-43EBA3F96335295D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-43EBA3F96335295D:title+abstract;source_url=https://arxiv.org/pdf/2507.10912v1;cache_filename=2507.10912v1.pdf;cache_sha256=54c7f1a4885634f007be5a890149fa9873335b94ea02e10fa779f0ab7079bbfa;locator=text-search="source code of this work" |
| REC-D4D0D4D6341705BB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D4D0D4D6341705BB:title+abstract |
| REC-5300A102BA97CB5B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5300A102BA97CB5B:title+abstract |
| REC-3E83647529A0BF93 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-3E83647529A0BF93:title+abstract;source_url=https://arxiv.org/pdf/2507.14139v1;cache_filename=2507.14139v1.pdf;cache_sha256=1e6f55eab43699e6f5ed9f76a8ad76e36e2ac2a87cee0bc2e74c9e601444dd37;locator=page 2 search phrase complete inference |
| REC-928C37379AB66C32 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-928C37379AB66C32:title+abstract |
| REC-C1B45DD5CFFDEF49 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C1B45DD5CFFDEF49:title+abstract |
| REC-70FF806962EDBD4E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-70FF806962EDBD4E:title+abstract |
| REC-D675CF108CBF8BAA | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-D675CF108CBF8BAA:title+abstract |
| REC-A84588B0F7BE86BC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-A84588B0F7BE86BC:title+abstract |
| REC-1229847FA1C1D549 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1229847FA1C1D549:title+abstract |
| REC-374F2F1C49957DA6 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-374F2F1C49957DA6:title+abstract;source_url=https://arxiv.org/pdf/2508.10303v1;cache_filename=2508.10303v1.pdf;cache_sha256=6666bba0612a0b2b9225dd2fa4ec8141a1092c3ad50dbd8b4b336c02b21acc02;locator=pages 12-13 section VI search phrase FPGA Implementation |
| REC-B9BB1B48E25209CD | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B9BB1B48E25209CD:title+abstract |
| REC-867BF18E2ADEBF6C | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-867BF18E2ADEBF6C:title+abstract;source_url=https://arxiv.org/pdf/2508.10370v1;cache_filename=2508.10370v1.pdf;cache_sha256=baabd5d322ffc02b98d59babd3dfa981111741a780f6d21923dc777858d53223;locator=section=3.eMamba_Design_Framework_Overview&search=focus_on_three_representative_vision_datasets |
| REC-55AF74F48541DBB8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-55AF74F48541DBB8:title+abstract |
| REC-0AB8E04D7DD6C72A | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-0AB8E04D7DD6C72A:title+abstract |
| REC-1C63BBF0DA4696BC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1C63BBF0DA4696BC:title+abstract |
| REC-2524EF73E57121D9 | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-2524EF73E57121D9:title+abstract;source_url=https://arxiv.org/pdf/2508.13905v2;cache_filename=2508.13905v2.pdf;cache_sha256=fc8531e3e197d60f4c38c90490300f416cdd7e0c952c35dce328d95dc940a3be;locator=section=Hardware-aware_deployment&search=modular_VHDL_code_generation |
| REC-805AE51C4211C504 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-805AE51C4211C504:title+abstract |
| REC-F6EE464E0EAC055F | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-F6EE464E0EAC055F:title+abstract |
| REC-6CF049B6B7FF9E23 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-6CF049B6B7FF9E23:title+abstract |
| REC-A9812738B0D3FDF8 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-A9812738B0D3FDF8:title+abstract;source_url=https://arxiv.org/pdf/2509.01149v1;cache_filename=2509.01149v1.pdf;cache_sha256=2700e0e8f1e642aba32d9f6a8c4405209de1cff43bd184c64799aad4c1b49f06;locator=text-search="metamorphic transformation rules" |
| REC-FD2B3322B61290F3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FD2B3322B61290F3:title+abstract |
| REC-908FFDB34685B693 | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-908FFDB34685B693:title+abstract |
| REC-BEACC83B64B951BF | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-BEACC83B64B951BF:title+abstract;source_url=https://arxiv.org/pdf/2509.13765v1;cache_filename=2509.13765v1.pdf;cache_sha256=6e30b46b859e0f59d219cb23fb26ab187a64e831f0e39bb91a3b4338cc26f2b5;locator=section=Evaluation&search=TENET-FPGA_achieves_an_end-to-end_speedup |
| REC-C9DCCD19015DC11E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-C9DCCD19015DC11E:title+abstract |
| REC-E4632083C47944B3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E4632083C47944B3:title+abstract |
| REC-2D053154E4E78BA8 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-2D053154E4E78BA8:title+abstract |
| REC-BE520FAB2229160E | B | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BE520FAB2229160E:title+abstract |
| REC-525F07C62996AA0D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-525F07C62996AA0D:title+abstract;source_url=https://arxiv.org/pdf/2509.26335v2;cache_filename=2509.26335v2.pdf;cache_sha256=0bb2fdd9db448347dbc5104aef9217f83017dcecc5dad37e37d0c3b431220668;locator=pages 3-5 sections 3-4 search phrase Vitis HLS is used |
| REC-939579D7FA707D17 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-939579D7FA707D17:title+abstract |
| REC-65FB5420A0B12A25 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-65FB5420A0B12A25:title+abstract |
| REC-FE659F378ED5871B | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FE659F378ED5871B:title+abstract |
| REC-28937A3B820B31B6 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-28937A3B820B31B6:title+abstract |
| REC-48B14D3F981A4130 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-48B14D3F981A4130:title+abstract;source_url=https://arxiv.org/pdf/2510.15926v2;cache_filename=2510.15926v2.pdf;cache_sha256=510e249e529748795cf6544efe41473ee18bf0ffd943e37974f76afc3064f14d;locator=References_[8],_arXiv:2504.16266 |
| REC-DD588E778AEE07F4 | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-DD588E778AEE07F4:title+abstract |
| REC-965CCFFDE7F04B1C | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-965CCFFDE7F04B1C:title+abstract;source_url=https://arxiv.org/pdf/2510.21745v1;cache_filename=2510.21745v1.pdf;cache_sha256=790a8952af5d0ed42341df069bd89512fa00428e95248cbe21b1ab0e1e518c44;locator=text-search="RTLLM benchmark" |
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
| REC-5C4ADC39D64D338C | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-5C4ADC39D64D338C:title+abstract;source_url=https://arxiv.org/pdf/2511.15505v1;cache_filename=2511.15505v1.pdf;cache_sha256=83c706a40821b588ee9fc19e86c9af692a5e3c77df0795e9224dbfdd0840e22f;locator=text-search="transforms DNN models into instruction programs" |
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
| REC-136E0A6CF2902F8E | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-136E0A6CF2902F8E:title+abstract;source_url=https://arxiv.org/pdf/2601.02135v1;cache_filename=2601.02135v1.pdf;cache_sha256=01d696a483f0a36e2b9790e445da5fa2261f495851eeed29fe095b9529daed69;locator=pages 6-8 sections 4.1 and 5.3 search phrase sustained token-per-second rate |
| REC-9C84CD6F53E668CB | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-9C84CD6F53E668CB:title+abstract |
| REC-57D5901E46D93621 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-57D5901E46D93621:title+abstract |
| REC-FEAA09BB86B0EBDA | C | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-FEAA09BB86B0EBDA:title+abstract |
| REC-B0590D78EA1EFC4E | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-B0590D78EA1EFC4E:title+abstract |
| REC-B43B25ED6C25AA2D | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-B43B25ED6C25AA2D:title+abstract;source_url=https://arxiv.org/pdf/2601.15151v1;cache_filename=2601.15151v1.pdf;cache_sha256=41a44bc9de79e1713e960bd4e69b24c44624d7c8dd1d59ab983779a9626e9e37;locator=text-search="architectural parameterization framework" |
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
| REC-D2CCA02341920D52 | B | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-D2CCA02341920D52:title+abstract;source_url=https://arxiv.org/pdf/2603.22867v1;cache_filename=2603.22867v1.pdf;cache_sha256=b6a91522a3f97d9164b49b6db8736e976ca09b3df3faa0e97723da4e86e43d0a;locator=section=4.1.Compiler_Infrastructure&search=Chisel-based_RTL_generator |
| REC-5DDEE20F5B196B1D | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-5DDEE20F5B196B1D:title+abstract |
| REC-BBE0B7CFE2C766EB | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-BBE0B7CFE2C766EB:title+abstract |
| REC-1CADB59192072EAC | D | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-1CADB59192072EAC:title+abstract |
| REC-377F6DCA995797F6 | A | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-377F6DCA995797F6:title+abstract |
| REC-1B391A89C0485DFA | C | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-1B391A89C0485DFA:title+abstract;source_url=https://arxiv.org/pdf/2604.04694v1;cache_filename=2604.04694v1.pdf;cache_sha256=18722aef678d243adbece2b6149acc8ee7a93fe0238506000ecd22a6c8dae800;locator=text-search="live kernel migration" |
| REC-86EE7D1C5BCC6BE3 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-86EE7D1C5BCC6BE3:title+abstract |
| REC-E735B0C0CC6BAEC2 | X | codex-title-abstract-screen | title_abstract | survey/build/phase1_mapping.csv#record_id=REC-E735B0C0CC6BAEC2:title+abstract |
| REC-B8F583785D75AE85 | X | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-B8F583785D75AE85:title+abstract;source_url=https://arxiv.org/pdf/2604.13933v2;cache_filename=2604.13933v2.pdf;cache_sha256=ce4ba0029193979efebfddfdcaee0869a2d30a833830657af0ff6c830639bcf9;locator=pages 2-4 sections II-D and IV-B search phrase U-Net |
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
| REC-0D2FAB7474469C66 | D | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-0D2FAB7474469C66:title+abstract;source_url=https://arxiv.org/pdf/2605.18444v1;cache_filename=2605.18444v1.pdf;cache_sha256=d99e23773f80c831e9f0d6a848aa3934b3e91685c449b3b6e1b8d1a18dd82a91;locator=text-search="Cadence simulations" |
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
| REC-C963AD29DE58DB45 | A | codex-title-abstract-screen | title_abstract+local_full_text | survey/build/phase1_mapping.csv#record_id=REC-C963AD29DE58DB45:title+abstract;source_url=https://arxiv.org/pdf/2607.03652v1;cache_filename=2607.03652v1.pdf;cache_sha256=9ba54bc8de4d7dbdc384b8bd8938b7bca32b3ba3c4e6b4f4699ed75dfb9b3860;locator=section=4.3.2.ELiTeFormer_1B_Latency_Profile&search=employs_Vitis_HLS_to_generate_RTL |
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
