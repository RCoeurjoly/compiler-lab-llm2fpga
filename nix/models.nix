{ registerModel, pythonWithTinyStories, pythonWithTinyStoriesTorchAO, torchMlir
, tinyStories1m, fpPrimsSv, materializePyTorchExported }:
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
      pytorchToolchain = [ pythonWithTinyStoriesTorchAO torchMlir ];
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
