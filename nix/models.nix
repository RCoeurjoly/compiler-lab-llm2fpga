{ registerModel, pythonWithTinyStories, pythonWithTinyStoriesTorchAO, torchMlir
, tinyStories1m, fpPrimsSv, materializePyTorchExported, exactPackageExportProvenance
, exactTinyStoriesPackage }:
let
  representativeCoreEnv = ''
    export TINYSTORIES_CORE_VOCAB_SIZE=32
    export TINYSTORIES_CORE_NUM_LAYERS=2
    export TINYSTORIES_CORE_MAX_POSITION_EMBEDDINGS=4
    export TINYSTORIES_CORE_WINDOW_SIZE=2
    export TINYSTORIES_CORE_HIDDEN_SIZE=2
    export TINYSTORIES_CORE_NUM_HEADS=1
  '';

  rcStudyEnv = { vocabSize, numLayers, maxPositionEmbeddings, windowSize
    , hiddenSize, numHeads }:
    ''
      export TINYSTORIES_RC_STUDY_CONTEXT_LENGTH=8
      export TINYSTORIES_RC_STUDY_VOCAB_SIZE=${toString vocabSize}
      export TINYSTORIES_RC_STUDY_NUM_LAYERS=${toString numLayers}
      export TINYSTORIES_RC_STUDY_MAX_POSITION_EMBEDDINGS=${toString maxPositionEmbeddings}
      export TINYSTORIES_RC_STUDY_WINDOW_SIZE=${toString windowSize}
      export TINYSTORIES_RC_STUDY_HIDDEN_SIZE=${toString hiddenSize}
      export TINYSTORIES_RC_STUDY_NUM_HEADS=${toString numHeads}
    '';

  registerRcStudyCore = { key, vocabSize, numLayers, maxPositionEmbeddings
    , windowSize, hiddenSize, numHeads }:
    registerModel {
      inherit key;
      name = key;
      description =
        "Structure-preserving TinyStories PT2E W8A8 representative-core study profile.";
      source = {
        type = "derived";
        base_model_id = tinyStories1m.modelId;
        inherit (tinyStories1m) revision;
        profile = "quantized-representative-core-structural-study";
        quantization = "pt2e-static-w8a8";
        calibration = "frozen-structural-eight-token-v1";
        context_length = 8;
        vocab_size = vocabSize;
        num_layers = numLayers;
        max_position_embeddings = maxPositionEmbeddings;
        window_size = windowSize;
        hidden_size = hiddenSize;
        num_heads = numHeads;
      };
      allowHwExterns = true;
      slangPerFileExternModules = true;
      inherit fpPrimsSv;
      hfSnapshot = tinyStories1m.snapshot;
      # Export materialization uses torch.export and PT2E only.  Torch-MLIR
      # remains a dependency of the later torch.mlir lowering stage, but must
      # not be pulled into the frozen-export/image derivation through the
      # shared pytorchExportedBuildInputs default.
      pytorchToolchain = [ pythonWithTinyStoriesTorchAO ];
      pytorchExportedCommand = ''
        export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
        ${rcStudyEnv {
          inherit vocabSize numLayers maxPositionEmbeddings windowSize hiddenSize
            numHeads;
        }}
        python ${materializePyTorchExported} \
          --adapter ${tinyStories1m.sourceDir}/model_adapter_quantized_representative_core_pt2e_w8a8.py \
          --model-path ${tinyStories1m.snapshot} \
          --out-dir "$out"
      '';
    };
in {
  "pattern-linear-fp32" = registerModel {
    key = "pattern-linear-fp32";
    name = "pattern-linear-fp32";
    description =
      "Local FP32 linear PyTorch pattern through the baseline lowering pipeline.";
    source = {
      type = "pattern";
      pattern = "linear";
      quantization = "none";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/linear}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${../patterns/linear/adapter.py} \
        --out-dir "$out"
    '';
  };

  "pattern-linear-w4a8" = registerModel {
    key = "pattern-linear-w4a8";
    name = "pattern-linear-w4a8";
    description =
      "Local linear PyTorch pattern with PT2E static W4A8 quantization through the baseline lowering pipeline.";
    source = {
      type = "pattern";
      pattern = "linear";
      quantization = "pt2e-static-w4a8";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/linear}:''${PYTHONPATH:-}"
      export TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4
      export TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8
      python ${materializePyTorchExported} \
        --adapter ${../patterns/linear/adapter_w4a8.py} \
        --out-dir "$out"
    '';
  };

  "pattern-linear-w4a8-core" = registerModel {
    key = "pattern-linear-w4a8-core";
    name = "pattern-linear-w4a8-core";
    description =
      "Local linear W4A8 hardware core with int8 activation input and explicit integer requantization.";
    source = {
      type = "pattern";
      pattern = "linear";
      quantization = "w4a8-core-int8-input";
      boundary = "hardware";
    };
    allowHwExterns = false;
    slangPerFileExternModules = false;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/linear}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${../patterns/linear/adapter_w4a8_core.py} \
        --out-dir "$out"
    '';
  };

  "pattern-embedding-w4a8-core" = registerModel {
    key = "pattern-embedding-w4a8-core";
    name = "pattern-embedding-w4a8-core";
    description =
      "Local embedding W4A8 hardware core with int64 token input and int8 activation output.";
    source = {
      type = "pattern";
      pattern = "embedding";
      quantization = "w4a8-core-int8-lookup";
      boundary = "hardware";
    };
    allowHwExterns = false;
    slangPerFileExternModules = false;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/embedding}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${../patterns/embedding/adapter_w4a8_core.py} \
        --out-dir "$out"
    '';
  };

  "pattern-layernorm-w4a8-core" = registerModel {
    key = "pattern-layernorm-w4a8-core";
    name = "pattern-layernorm-w4a8-core";
    description =
      "Local layernorm W4A8 hardware core with int8 activation input, integer reductions, fixed-point inverse standard deviation, and int8 output.";
    source = {
      type = "pattern";
      pattern = "layernorm";
      quantization = "w4a8-core-int8-fixed-point";
      boundary = "hardware";
    };
    allowHwExterns = false;
    slangPerFileExternModules = false;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/layernorm}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${../patterns/layernorm/adapter_w4a8_core.py} \
        --out-dir "$out"
    '';
  };

  "tinystories-fp32" = registerModel {
    key = "tinystories-fp32";
    name = "tinystories-fp32";
    description =
      "Full TinyStories-1M FP32 ExportedProgram through the baseline lowering pipeline.";
    source = {
      type = "huggingface";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      quantization = "none";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.adapterPy} \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tiny-stories-1m-baseline-float" = registerModel {
    key = "tiny-stories-1m-baseline-float";
    name = "tiny-stories-1m-baseline-float";
    description =
      "Task 3/old Task 6 baseline TinyStories-1M FP32 ExportedProgram through the baseline lowering pipeline.";
    source = {
      type = "huggingface";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      quantization = "none";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.adapterPy} \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor" = registerModel {
    key = "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor";
    name = "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor";
    description =
      "Successor exact TinyStories-1M export authorized by the frozen Task 1--3 artifact and serial-GEMV successor receipt.";
    source = {
      type = "authenticated-exact-package-successor";
      predecessor = "tiny-stories-1m-kev-gpt-exact";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      adapter = "TinyStories/model_adapter_exact_serial_gemv_successor.py";
      successor_adapter_sha256 = "e403b516600d3247e5cc66ef3541f541239c1db0858cafe29b23529463c19a7a";
      exact_adapter_sha256 = "5f2dfa10c54134e44a31f89608b562aea33ef39deacfcd62eadac1f0fda94892";
      serial_gemv_boundary_sha256 = "a3e0c9f5ccd56fcd530174e2e15747008344b8e32384e508611c793008037b14";
      task_1_successor_receipt_file_sha256 = "d6c71ad94ccb0e00c2edb0dfbc3a2004d9e21bf1a30984b9df57570c04415dee";
      task_1_successor_receipt_sha256 = "ec9985628911a28374d9b304e7896e61d1dc9635612e74311d6667eef470f7db";
      task_3_generation_file_sha256 = "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3";
      task_3_generation_artifact_sha256 = "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3";
      package_path = exactTinyStoriesPackage;
      package_source = "kev-gpt-src@df1fc45b2ffcb26fddc19cfd57621e7eedf6153f";
      backend_overrides = [ ];
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedBuildInputs = [ pythonWithTinyStories ];
    pytorchExportedCommand = ''
      package="${exactTinyStoriesPackage}"
      contract_source="${../artifacts/reference/tinystories-1m-exact-input-contract.json}"
      audit="${../artifacts/reference/tinystories-1m-exact-input-audit.json}"
      contract_dir="$TMPDIR/exact-successor-inputs"
      mkdir -p "$contract_dir"
      cp "$contract_source" "$contract_dir/tinystories-1m-exact-input-contract.json"
      cp "$audit" "$contract_dir/tinystories-1m-exact-input-audit.json"
      contract="$contract_dir/tinystories-1m-exact-input-contract.json"

      adapter_root="$TMPDIR/exact-successor-adapter-root"
      mkdir -p "$adapter_root/TinyStories" "$adapter_root/artifacts/comparison" \
        "$adapter_root/scripts/comparison" "$adapter_root/scripts/pipeline" \
        "$adapter_root/docs/superpowers/specs" "$adapter_root/tests"
      cp ${tinyStories1m.sourceDir}/*.py "$adapter_root/TinyStories/"
      cp -r ${../artifacts/reference} "$adapter_root/artifacts/reference"
      cp ${../artifacts/comparison/tinystories-1m-exact-serial-gemv-successor.json} \
        "$adapter_root/artifacts/comparison/tinystories-1m-exact-serial-gemv-successor.json"
      cp ${../scripts/comparison}/*.py "$adapter_root/scripts/comparison/"
      cp ${../scripts/pipeline/verify_exact_serial_gemv_successor_torch.py} \
        "$adapter_root/scripts/pipeline/verify_exact_serial_gemv_successor_torch.py"
      cp ${../tests/test_tinystories_1m_exact_generation.py} \
        "$adapter_root/tests/test_tinystories_1m_exact_generation.py"
      cp ${../docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md} \
        "$adapter_root/docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md"
      export PYTHONPATH="$adapter_root:${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      adapter="$adapter_root/TinyStories/model_adapter_exact_serial_gemv_successor.py"
      ${pythonWithTinyStories}/bin/python ${materializePyTorchExported} \
        --adapter "$adapter" --contract "$contract" --package "$package" \
        --model-path ${tinyStories1m.snapshot} --out-dir "$out"
      ${pythonWithTinyStories}/bin/python \
        "$adapter_root/scripts/pipeline/verify_exact_serial_gemv_successor_torch.py" \
        write-export --root "$adapter_root" --exported-dir "$out" \
        --output "$out/exact-serial-gemv-successor-provenance.json" >/dev/null
    '';
  };

  "tiny-stories-1m-kev-gpt-exact" = registerModel {
    key = "tiny-stories-1m-kev-gpt-exact";
    name = "tiny-stories-1m-kev-gpt-exact";
    description =
      "Authenticated exact integer/fixed-point TinyStories-1M package export through the existing baseline pipeline.";
    source = {
      type = "authenticated-exact-package";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      adapter = "TinyStories/model_adapter_exact_package.py";
      adapter_sha256 = "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e";
      contract_sha256 = "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c";
      package_path = exactTinyStoriesPackage;
      package_source = "kev-gpt-src@df1fc45b2ffcb26fddc19cfd57621e7eedf6153f";
      package_manifest_sha256 = "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35";
      task_1_audit_file_sha256 = "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd";
      task_1_audit_payload_sha256 = "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766";
      task_2_artifact_file_sha256 = "173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a";
      task_2_artifact_sha256 = "af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838";
      task_2_model_receipt_sha256 = "5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834";
      task_3_generation_file_sha256 = "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3";
      task_3_generation_artifact_sha256 = "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3";
      task_3_generation_result_sha256 = "c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644";
      backend_overrides = [ ];
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedBuildInputs = [ pythonWithTinyStories ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      package="${exactTinyStoriesPackage}"
      contract_source="${../artifacts/reference/tinystories-1m-exact-input-contract.json}"
      audit="${../artifacts/reference/tinystories-1m-exact-input-audit.json}"
      contract_dir="$TMPDIR/exact-inputs"
      mkdir -p "$contract_dir"
      cp "$contract_source" "$contract_dir/tinystories-1m-exact-input-contract.json"
      cp "$audit" "$contract_dir/tinystories-1m-exact-input-audit.json"
      contract="$contract_dir/tinystories-1m-exact-input-contract.json"
      task_2_artifact="${../artifacts/reference/tinystories-1m-exact-package-model.json}"
      generation_receipt="${../artifacts/reference/tinystories-1m-exact-generation.json}"
      adapter="${tinyStories1m.sourceDir}/model_adapter_exact_package.py"
      ${pythonWithTinyStories}/bin/python ${exactPackageExportProvenance} verify \
        --adapter "$adapter" --contract "$contract" --audit "$audit" --package "$package" \
        --model-path ${tinyStories1m.snapshot} --task-2-artifact "$task_2_artifact" \
        --generation-receipt "$generation_receipt"
      adapter_root="$TMPDIR/exact-adapter-root"
      mkdir -p "$adapter_root/TinyStories" "$adapter_root/artifacts" "$adapter_root/scripts/comparison" \
        "$adapter_root/docs/superpowers/specs"
      cp ${tinyStories1m.sourceDir}/*.py "$adapter_root/TinyStories/"
      cp -r ${../artifacts/reference} "$adapter_root/artifacts/reference"
      cp ${../scripts/comparison}/*.py "$adapter_root/scripts/comparison/"
      cp ${../docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md} \
        "$adapter_root/docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md"
      adapter="$adapter_root/TinyStories/model_adapter_exact_package.py"
      ${pythonWithTinyStories}/bin/python ${materializePyTorchExported} \
        --adapter "$adapter" --contract "$contract" --package "$package" \
        --model-path ${tinyStories1m.snapshot} --out-dir "$out"
      ${pythonWithTinyStories}/bin/python ${exactPackageExportProvenance} write \
        --adapter "$adapter" --contract "$contract" --audit "$audit" --package "$package" \
        --model-path ${tinyStories1m.snapshot} --task-2-artifact "$task_2_artifact" \
        --generation-receipt "$generation_receipt" --out-dir "$out"
    '';
  };

  "tinystories-w8a8" = registerModel {
    key = "tinystories-w8a8";
    name = "tinystories-w8a8";
    description =
      "Full TinyStories-1M XNNPACK PT2E static W8A8 ExportedProgram for the provisional TOSA no-handshake resource scout.";
    source = {
      type = "huggingface";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      quantization = "pt2e-static-w8a8";
      calibration = "frozen-single-token-zero-input";
      evidence = "provisional-resource-scout";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_pt2e_static_quant.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tinystories-w8a8-rc-study-full" = registerModel {
    key = "tinystories-w8a8-rc-study-full";
    name = "tinystories-w8a8-rc-study-full";
    description =
      "Full pretrained TinyStories PT2E W8A8 profile for the eight-token representative-core structural study.";
    source = {
      type = "huggingface";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      profile = "quantized-representative-core-structural-study";
      quantization = "pt2e-static-w8a8";
      calibration = "frozen-structural-eight-token-v1";
      context_length = 8;
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      export TINYSTORIES_RC_STUDY_CONTEXT_LENGTH=8
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_pt2e_w8a8_study.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tinystories-w8a8-rc-study-anchor" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-anchor";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-vocab128" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-vocab128";
    vocabSize = 128;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-vocab512" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-vocab512";
    vocabSize = 512;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-width8" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-width8";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 8;
    numHeads = 2;
  };

  "tinystories-w8a8-rc-study-width16" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-width16";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 16;
    numHeads = 4;
  };

  "tinystories-w8a8-rc-study-layers4" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-layers4";
    vocabSize = 32;
    numLayers = 4;
    maxPositionEmbeddings = 8;
    windowSize = 4;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-window8" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-window8";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 8;
    windowSize = 8;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask2048" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask2048";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 2048;
    windowSize = 256;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9";
    vocabSize = 32;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 256;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9-vocab6" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9-vocab6";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 256;
    hiddenSize = 4;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9-vocab6-width1" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9-vocab6-width1";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 256;
    hiddenSize = 1;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9-vocab6-width2" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9-vocab6-width2";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 256;
    hiddenSize = 2;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9-vocab6-width3" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9-vocab6-width3";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 256;
    hiddenSize = 3;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-mask9-vocab6-width2-window1" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-mask9-vocab6-width2-window1";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 1;
    hiddenSize = 2;
    numHeads = 1;
  };

  "tinystories-w8a8-rc-study-minimum" = registerRcStudyCore {
    key = "tinystories-w8a8-rc-study-minimum";
    vocabSize = 6;
    numLayers = 2;
    maxPositionEmbeddings = 9;
    windowSize = 1;
    hiddenSize = 1;
    numHeads = 1;
  };

  "tinystories-representative-core-fp32" = registerModel {
    key = "tinystories-representative-core-fp32";
    name = "tinystories-representative-core-fp32";
    description =
      "Reduced TinyStories representative-core FP32 ExportedProgram for pipeline bring-up.";
    source = {
      type = "derived";
      base_model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      profile = "representative-core-min";
      quantization = "none";
      vocab_size = 32;
      num_layers = 2;
      max_position_embeddings = 4;
      window_size = 2;
      hidden_size = 2;
      num_heads = 1;
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      ${representativeCoreEnv}
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tinystories-representative-core-w4a8" = registerModel {
    key = "tinystories-representative-core-w4a8";
    name = "tinystories-representative-core-w4a8";
    description =
      "Reduced TinyStories representative-core PT2E static W4A8 ExportedProgram for quantized bring-up.";
    source = {
      type = "derived";
      base_model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      profile = "representative-core-min";
      quantization = "pt2e-static-w4a8";
      lowering = "default-handshake-nolsq";
      vocab_size = 32;
      num_layers = 2;
      max_position_embeddings = 4;
      window_size = 2;
      hidden_size = 2;
      num_heads = 1;
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      ${representativeCoreEnv}
      export TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4
      export TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core_pt2e_static_quant.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tinystories-representative-core-w4a8-fixed-layernorm" = registerModel {
    key = "tinystories-representative-core-w4a8-fixed-layernorm";
    name = "tinystories-representative-core-w4a8-fixed-layernorm";
    description =
      "Reduced TinyStories representative-core PT2E static W4A8 ExportedProgram with explicit fixed-point LayerNorm bridge for Calyx bring-up.";
    source = {
      type = "derived";
      base_model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      profile = "representative-core-min";
      quantization = "pt2e-static-w4a8";
      normalization = "fixed-point-layernorm-bridge";
      activation = "quadratic-gelu-hardware-approximation";
      lowering = "default-handshake-nolsq";
      vocab_size = 32;
      num_layers = 2;
      max_position_embeddings = 4;
      window_size = 2;
      hidden_size = 2;
      num_heads = 1;
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      ${representativeCoreEnv}
      export TINYSTORIES_REPRESENTATIVE_CORE_FIXED_POINT_LAYERNORM=1
      export TINYSTORIES_REPRESENTATIVE_CORE_QUADRATIC_GELU=1
      export TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4
      export TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core_pt2e_static_quant.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };

  "tinystories-representative-core-w4a8-integer" = registerModel {
    key = "tinystories-representative-core-w4a8-integer";
    name = "tinystories-representative-core-w4a8-integer";
    description =
      "TinyStories representative-core W4A8 hardware slice with explicit integer embedding, normalization, linear, activation, and residual arithmetic.";
    source = {
      type = "derived";
      base_model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      profile = "representative-core-min-integer-slice";
      quantization = "w4a8-explicit-integer-core";
      normalization = "fixed-point-layernorm-core";
      activation = "integer-quadratic-core";
      boundary = "hardware";
      vocab_size = 8;
      num_layers = 2;
      max_position_embeddings = 1;
      hidden_size = 2;
    };
    allowHwExterns = false;
    slangPerFileExternModules = false;
    hfSnapshot = tinyStories1m.snapshot;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core_w4a8_integer.py \
        --model-path ${tinyStories1m.snapshot} \
        --out-dir "$out"
    '';
  };
}
