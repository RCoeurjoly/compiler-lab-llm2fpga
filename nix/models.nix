{ registerModel, pythonWithTorch, pythonWithTinyStories
, pythonWithTinyStoriesTorchAO, torchMlir, python, tinyStories1m, fpPrimsSv
, compilePyTorch, matmulPy, matmulAdapterPy, matmulSrcDir, simDir }:
let
  torchMlirPythonPath =
    "${torchMlir}/${python.sitePackages}:${torchMlir}/${python.sitePackages}/torch_mlir";
  representativeCoreEnv = ''
    export TINYSTORIES_CORE_VOCAB_SIZE=32
    export TINYSTORIES_CORE_NUM_LAYERS=2
    export TINYSTORIES_CORE_MAX_POSITION_EMBEDDINGS=4
    export TINYSTORIES_CORE_WINDOW_SIZE=2
    export TINYSTORIES_CORE_HIDDEN_SIZE=2
    export TINYSTORIES_CORE_NUM_HEADS=1
  '';
in {
  matmul = registerModel {
    key = "matmul";
    name = "matmul";
    description =
      "Minimal local matmul PyTorch module used as a fast Task 3 pipeline smoke input.";
    source = {
      type = "local";
      path = "${matmulPy}";
    };
    torchInputBuildInputs = [ pythonWithTorch ];
    torchInputCommand = ''
      export MATMUL_PY="${matmulPy}"
      export PYTHONPATH="${matmulSrcDir}:${simDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      python ${compilePyTorch} \
        --adapter ${matmulAdapterPy} \
        --out "$out" >/dev/null
    '';
  };

  "tinystories-fp32" = registerModel {
    key = "tinystories-fp32";
    name = "tinystories-fp32";
    description =
      "TinyStories-1M FP32 export through the current Task 3-derived pipeline.";
    source = {
      type = "huggingface";
      model_id = tinyStories1m.modelId;
      inherit (tinyStories1m) revision;
      quantization = "none";
    };
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    torchInputBuildInputs = [ pythonWithTinyStories ];
    torchInputCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      python ${compilePyTorch} \
        --adapter ${tinyStories1m.adapterPy} \
        --model-path ${tinyStories1m.snapshot} \
        --out "$out" >/dev/null
    '';
  };

  "tinystories-representative-core-fp32" = registerModel {
    key = "tinystories-representative-core-fp32";
    name = "tinystories-representative-core-fp32";
    description =
      "Reduced TinyStories representative core through the current Task 3-derived FP32 pipeline.";
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
    torchInputBuildInputs = [ pythonWithTinyStories ];
    torchInputCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      ${representativeCoreEnv}
      python ${compilePyTorch} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core.py \
        --model-path ${tinyStories1m.snapshot} \
        --out "$out" >/dev/null
    '';
  };

  "tinystories-representative-core-w4a8" = registerModel {
    key = "tinystories-representative-core-w4a8";
    name = "tinystories-representative-core-w4a8";
    description =
      "Reduced TinyStories representative core using PT2E static W4A8 quantization through the current Task 3-derived pipeline.";
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
    torchInputBuildInputs = [ pythonWithTinyStoriesTorchAO ];
    torchInputCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      ${representativeCoreEnv}
      export TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4
      export TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8
      python ${compilePyTorch} \
        --adapter ${tinyStories1m.sourceDir}/model_adapter_representative_core_pt2e_static_quant.py \
        --model-path ${tinyStories1m.snapshot} \
        --out "$out" >/dev/null
    '';
  };
}
