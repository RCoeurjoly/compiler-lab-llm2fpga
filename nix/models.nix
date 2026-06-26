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
    slangPerFileExternModules = true;
    pytorchToolchain = [ pythonWithTinyStories torchMlir ];
    pytorchExportedCommand = ''
      export PYTHONPATH="${../patterns/linear}:''${PYTHONPATH:-}"
      python ${materializePyTorchExported} \
        --adapter ${../patterns/linear/adapter_w4a8_core.py} \
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
}
