{ registerModel, pythonWithTorch, pythonWithTinyStories, torchMlir, python
, tinyStories1m, matmulPy, matmulAdapterPy, matmulSrcDir, fpPrimsSv, simDir
, compilePyTorch }:
let
  torchMlirPythonPath =
    "${torchMlir}/${python.sitePackages}:${torchMlir}/${python.sitePackages}/torch_mlir";
in {
  matmul = registerModel {
    name = "matmul";
    torchInputBuildInputs = [ pythonWithTorch ];
    torchInputCommand = ''
      export MATMUL_PY="${matmulPy}"
      export PYTHONPATH="${matmulSrcDir}:${simDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      python ${compilePyTorch} \
        --adapter ${matmulAdapterPy} \
        --out "$out" >/dev/null
    '';
  };

  "tiny-stories-1m-baseline-float" = registerModel {
    name = "tiny-stories-1m-baseline-float";
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

  "tinystories-representative-core-task3-baseline-float" = registerModel {
    name = "tinystories-representative-core-task3-baseline-float";
    allowHwExterns = true;
    slangPerFileExternModules = true;
    inherit fpPrimsSv;
    torchInputBuildInputs = [ pythonWithTinyStories ];
    torchInputCommand = ''
      export PYTHONPATH="${tinyStories1m.sourceDir}:${torchMlirPythonPath}:''${PYTHONPATH:-}"
      export TINYSTORIES_CORE_VOCAB_SIZE=32
      export TINYSTORIES_CORE_NUM_LAYERS=2
      export TINYSTORIES_CORE_MAX_POSITION_EMBEDDINGS=4
      export TINYSTORIES_CORE_WINDOW_SIZE=2
      export TINYSTORIES_CORE_HIDDEN_SIZE=2
      export TINYSTORIES_CORE_NUM_HEADS=1
      python ${compilePyTorch} \
        --adapter ${tinyStories1m.representativeCoreAdapterPy} \
        --model-path ${tinyStories1m.snapshot} \
        --out "$out" >/dev/null
    '';
  };
}
