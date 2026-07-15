{ pkgs, mlir, circt, calyxTool, yosysPkg, yosysSlang, torchMlir, python
, pipelineScripts, compilePyTorch, svProvenanceReport, noHandshakeLinalgToScf
, noHandshakeScfToFlatScf, noHandshakeScfToCalyx, noHandshakeLinalgToLlvm
, calyxToSvNoHandshake, calyxToHwSvNoHandshake, flatScfBlockerReport, mlirPasses
, circtPasses, tosaToLinalgMlir ? mlir }:
let
  stageNames = [
    "hf-snapshot"
    "pytorch-exported"
    "torch"
    "torch-stats"
    "tosa"
    "linalg"
    "scf"
    "flat-scf"
    "calyx"
    "calyx-sv"
    "calyx-native-sv"
    "calyx-hw-sv"
    "cf"
    "cf-stats"
    "llvm"
    "handshake"
    "hs-ext"
    "hw0"
    "hw"
    "hw-clean"
    "sv-mlir"
    "sv"
    "sv-provenance-report"
    "il"
    "yosys-stat"
  ];

  torchMlirOpt = let
    candidates = [
      "${torchMlir}/bin/torch-mlir-opt"
      "${torchMlir}/${python.sitePackages}/torch_mlir/_mlir_libs/torch-mlir-opt"
      "${torchMlir}/${python.sitePackages}/torch_mlir/torch_mlir/_mlir_libs/torch-mlir-opt"
    ];
    matches = builtins.filter builtins.pathExists candidates;
  in if matches == [ ] then
    throw "Unable to locate torch-mlir-opt in ${torchMlir}"
  else
    builtins.head matches;

  mkUnavailableStage = { name, stage, reason }:
    pkgs.runCommand "${name}-${stage}" { } ''
      mkdir -p "$out"
      cat >"$out/manifest.json" <<'JSON'
      ${builtins.toJSON {
        inherit stage reason;
        status = "unavailable";
      }}
      JSON
    '';

  mkHfSnapshotDerivation = { name, hfSnapshot ? null }:
    if hfSnapshot != null then
      hfSnapshot
    else
      mkUnavailableStage {
        inherit name;
        stage = "hf-snapshot";
        reason = "model was not registered from a HuggingFace snapshot";
      };

  mkPyTorchExportedDerivation = { name, command, buildInputs ? [ ], upstream }:
    pkgs.runCommand "${name}-pytorch-exported" { inherit buildInputs; } ''
      set -euo pipefail
      mkdir -p "$out"
      ln -s ${upstream} "$out/upstream"
      ${command}
    '';

  mkTorchStage = { name, pytorchExported, pytorchToolchain ? [ ] }:
    pkgs.runCommand "${name}-torch.mlir" { buildInputs = pytorchToolchain; } ''
      set -euo pipefail
      export PYTHONPATH="${torchMlir}/${python.sitePackages}:${torchMlir}/${python.sitePackages}/torch_mlir:''${PYTHONPATH:-}"
      python ${compilePyTorch} \
        --exported-program-dir ${pytorchExported} \
        --out "$out" >/dev/null
    '';

  mkMlirOpStatsDerivation = { name, stageName, tool, input }:
    pkgs.runCommand "${name}-${stageName}.stats" { } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/mlir_op_stats.sh \
        ${tool} ${input} "$out"
    '';

  mkLinalgDerivation = { name, torch }:
    pkgs.runCommand "${name}-linalg.mlir" { buildInputs = [ torchMlir ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/torch_to_linalg.sh \
        ${torchMlirOpt} ${torch} "$out"
    '';

  mkTosaDerivation = { name, torch }:
    pkgs.runCommand "${name}-tosa.mlir" { buildInputs = [ torchMlir ]; } ''
      ${torchMlirOpt} ${torch} \
        --torch-fuse-quantized-ops \
        --torch-backend-to-tosa-backend-pipeline \
        -o "$out"
    '';

  mkTosaToLinalgDerivation = { name, tosa }:
    pkgs.runCommand "${name}-linalg.mlir" {
      buildInputs = [ tosaToLinalgMlir mlirPasses ];
    } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/tosa_to_linalg.sh \
        ${tosaToLinalgMlir}/bin/mlir-opt \
        ${mlirPasses}/lib/LLM2FPGAMLIRPasses.so \
        ${tosa} "$out"
    '';

  mkCfDerivation = { name, linalg }:
    pkgs.runCommand "${name}-cf.mlir" { buildInputs = [ mlir ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/linalg_to_cf.sh \
        ${mlir}/bin/mlir-opt ${linalg} "$out"
    '';

  mkLinalgToScfDerivation = { name, linalg }:
    pkgs.runCommand "${name}-scf.mlir" { buildInputs = [ mlir ]; } ''
      ${pkgs.bash}/bin/bash ${noHandshakeLinalgToScf} \
        ${mlir}/bin/mlir-opt ${linalg} "$out"
    '';

  mkScfToFlatScfDerivation = { name, scf }:
    pkgs.runCommand "${name}-flat-scf" { buildInputs = [ mlir python ]; } ''
      export FLAT_SCF_BLOCKER_REPORT=${flatScfBlockerReport}
      ${pkgs.bash}/bin/bash ${noHandshakeScfToFlatScf} \
        ${mlir}/bin/mlir-opt ${scf} "$out"
      test -f "$out/flat.scf.mlir"
      test -f "$out/manifest.json"
      test -f "$out/blockers.json"
    '';

  mkScfToCalyxDerivation = { name, flatScf }:
    let
      scoutMathPass = pkgs.lib.optionalString (name == "tinystories-w8a8")
        ",llm2fpga-lower-scout-math-for-calyx";
    in pkgs.runCommand "${name}-calyx" { buildInputs = [ mlir circt python ]; } ''
      tmp_pre_calyx="$(mktemp /tmp/no_handshake_pre_calyx_XXXXXX.mlir)"
      ${mlir}/bin/mlir-opt ${flatScf}/flat.scf.mlir \
        --load-pass-plugin=${mlirPasses}/lib/LLM2FPGAMLIRPasses.so \
        --pass-pipeline='builtin.module(llm2fpga-lower-static-memref-views-for-calyx,llm2fpga-drop-calyx-unsupported-asserts,llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,llm2fpga-lower-exact-math-for-calyx${scoutMathPass},llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)' \
        -o "$tmp_pre_calyx"
      ${pkgs.bash}/bin/bash ${noHandshakeScfToCalyx} \
        ${circt}/bin/circt-opt "$tmp_pre_calyx" "$out"
      ${python}/bin/python3 ${pipelineScripts}/calyx_float_frontier_report.py \
        "$out/flat.scf.mlir" "$out/float-frontier.json" \
        --manifest-json "$out/manifest.json"
      test -f "$out/manifest.json"
      test -f "$out/float-frontier.json"
      if ${pkgs.gnugrep}/bin/grep -q '"status":"ok"' "$out/manifest.json"; then
        test -f "$out/model.calyx.mlir"
      fi
    '';

  mkLinalgToLlvmDerivation = { name, linalg }:
    pkgs.runCommand "${name}-llvm.mlir" { buildInputs = [ mlir ]; } ''
      ${pkgs.bash}/bin/bash ${noHandshakeLinalgToLlvm} \
        ${mlir}/bin/mlir-opt ${linalg} "$out"
    '';

  mkCalyxNativeSvDerivation = { name, calyx }:
    pkgs.runCommand "${name}-calyx-native-sv" {
      buildInputs = [ circt calyxTool python ];
    } ''
      export CALYX_NORMALIZE_FOR_EXPORT=${pipelineScripts}/normalize_calyx_for_export.py
      export CALYX_NORMALIZE_FUTIL_CONSTANTS=${pipelineScripts}/normalize_futil_float_constants.py
      ${pkgs.bash}/bin/bash ${calyxToSvNoHandshake} \
        ${circt}/bin/circt-translate \
        ${calyxTool}/bin/calyx \
        ${calyxTool}/share/calyx \
        ${calyx} "$out"
    '';

  mkCalyxHwSvDerivation = { name, calyx }:
    pkgs.runCommand "${name}-calyx-hw-sv" {
      buildInputs = [ circt python circtPasses ];
    } ''
      export CIRCT_PASS_PLUGIN=${circtPasses}/lib/LLM2FPGACIRCTPasses.so
      ${pkgs.bash}/bin/bash ${calyxToHwSvNoHandshake} \
        ${circt}/bin/circt-opt \
        ${calyx} "$out"
    '';

  mkHandshakeDerivation = { name, cf }:
    pkgs.runCommand "${name}-handshake.mlir" {
      buildInputs = [ mlir circt ];
    } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/cf_to_handshake.sh \
        ${circt}/bin/circt-opt ${mlir}/bin/mlir-opt ${cf} "$out"
    '';

  mkHsExtDerivation = { name, handshake }:
    pkgs.runCommand "${name}-hs-ext.mlir" { buildInputs = [ circt ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/handshake_to_hs_ext.sh \
        ${circt}/bin/circt-opt ${handshake} "$out"
    '';

  mkHw0Derivation = { name, hsExt }:
    pkgs.runCommand "${name}-hw0.mlir" { buildInputs = [ circt ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/hs_ext_to_hw0.sh \
        ${circt}/bin/circt-opt ${hsExt} "$out"
    '';

  mkHwDerivation = { name, hw0 }:
    pkgs.runCommand "${name}-hw.mlir" { buildInputs = [ circt ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/hw0_to_hw.sh \
        ${circt}/bin/circt-opt ${hw0} "$out"
    '';

  mkHwCleanDerivation = { name, hw }:
    pkgs.runCommand "${name}-hw-clean.mlir" { buildInputs = [ circt ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/hw_to_hw_clean.sh \
        ${circt}/bin/circt-opt ${hw} "$out"
    '';

  mkSvMlirDerivation = { name, hwClean }:
    pkgs.runCommand "${name}-sv-mlir" { buildInputs = [ circt ]; } ''
      ${pkgs.bash}/bin/bash ${pipelineScripts}/hw_clean_to_sv_mlir.sh \
        ${circt}/bin/circt-opt ${hwClean} "$out"
    '';

  mkSvDerivation = { name, svMlir, allowHwExterns ? false, fpPrimsSv ? null }:
    pkgs.runCommand "${name}-sv" { buildInputs = [ circt python ]; } ''
      ${pkgs.lib.optionalString allowHwExterns ''
        export ALLOW_HW_EXTERNS=1
      ''}
      ${pkgs.lib.optionalString (fpPrimsSv != null) ''
        export FP_PRIMS_SV=${fpPrimsSv}
      ''}
      ${pkgs.bash}/bin/bash ${pipelineScripts}/sv_mlir_to_sv.sh \
        ${circt}/bin/circt-opt ${svMlir} "$out"
    '';

  mkSvProvenanceReportDerivation = { name, sv }:
    pkgs.runCommand "${name}-sv-provenance-report.json" {
      buildInputs = [ python ];
    } ''
      ${python}/bin/python3 ${svProvenanceReport} \
        --input-filelist ${sv}/sources.f \
        --output "$out"
    '';

  mkIlDerivation = { name, sv, slangPerFileExternModules ? false }:
    pkgs.runCommand "${name}.il" { buildInputs = [ yosysPkg ]; } ''
      ${pkgs.lib.optionalString slangPerFileExternModules ''
        export YOSYS_SLANG_PER_FILE_EXTERNS=1
      ''}
      ${pkgs.bash}/bin/bash ${pipelineScripts}/sv_to_il.sh \
        ${yosysPkg}/bin/yosys \
        ${yosysSlang}/share/yosys/plugins/slang.so \
        ${sv}/sources.f "$out"
    '';

  mkYosysStatDerivation = { name, sv, slangPerFileExternModules ? false }:
    pkgs.runCommand "${name}-yosys.stat" {
      buildInputs = [ yosysPkg python ];
    } ''
      ${pkgs.lib.optionalString slangPerFileExternModules ''
        export YOSYS_SLANG_PER_FILE_EXTERNS=1
      ''}
      ${pkgs.bash}/bin/bash ${pipelineScripts}/sv_to_yosys_stat.sh \
        ${yosysPkg}/bin/yosys \
        ${yosysSlang}/share/yosys/plugins/slang.so \
        ${sv}/sources.f "$out"
    '';

  mkBasePipeline = { name, hfSnapshot, pytorchExported, torchStage
    , handshakeFromCf, tosaFromTorch ? null, linalgFromStages ?
      ({ name, torch, ... }: mkLinalgDerivation { inherit name torch; })
    , allowHwExterns ? false, fpPrimsSv ? null
    , slangPerFileExternModules ? false }:
    let
      self = {
        "hf-snapshot" = hfSnapshot;
        "pytorch-exported" = pytorchExported;
        torch = torchStage;
        "torch-stats" = mkMlirOpStatsDerivation {
          inherit name;
          stageName = "torch";
          tool = torchMlirOpt;
          input = self.torch;
        };
        tosa = if tosaFromTorch == null then
          mkUnavailableStage {
            inherit name;
            stage = "tosa";
            reason =
              "direct Torch-to-Linalg pipeline does not emit a TOSA handoff";
          }
        else
          tosaFromTorch {
            inherit name;
            inherit (self) torch;
          };
        linalg = linalgFromStages {
          inherit name;
          inherit (self) torch tosa;
        };
        scf = mkUnavailableStage {
          inherit name;
          stage = "scf";
          reason = "baseline hardware pipeline lowers through CF and Handshake";
        };
        "flat-scf" = mkUnavailableStage {
          inherit name;
          stage = "flat-scf";
          reason = "baseline hardware pipeline lowers through CF and Handshake";
        };
        calyx = mkUnavailableStage {
          inherit name;
          stage = "calyx";
          reason = "baseline hardware pipeline lowers through CF and Handshake";
        };
        "calyx-sv" = mkUnavailableStage {
          inherit name;
          stage = "calyx-sv";
          reason = "baseline hardware pipeline does not lower through Calyx";
        };
        "calyx-native-sv" = mkUnavailableStage {
          inherit name;
          stage = "calyx-native-sv";
          reason = "baseline hardware pipeline does not lower through Calyx";
        };
        "calyx-hw-sv" = mkUnavailableStage {
          inherit name;
          stage = "calyx-hw-sv";
          reason = "baseline hardware pipeline does not lower through Calyx";
        };
        cf = mkCfDerivation {
          inherit name;
          inherit (self) linalg;
        };
        "cf-stats" = mkMlirOpStatsDerivation {
          inherit name;
          stageName = "cf";
          tool = "${mlir}/bin/mlir-opt";
          input = self.cf;
        };
        llvm = mkUnavailableStage {
          inherit name;
          stage = "llvm";
          reason =
            "baseline hardware pipeline lowers through Handshake, not LLVM";
        };
        handshake = handshakeFromCf {
          inherit name;
          inherit (self) cf;
        };
        "hs-ext" = mkHsExtDerivation {
          inherit name;
          inherit (self) handshake;
        };
        hw0 = mkHw0Derivation {
          inherit name;
          hsExt = self."hs-ext";
        };
        hw = mkHwDerivation {
          inherit name;
          inherit (self) hw0;
        };
        "hw-clean" = mkHwCleanDerivation {
          inherit name;
          inherit (self) hw;
        };
        "sv-mlir" = mkSvMlirDerivation {
          inherit name;
          hwClean = self."hw-clean";
        };
        sv = mkSvDerivation {
          inherit name;
          svMlir = self."sv-mlir";
          inherit allowHwExterns fpPrimsSv;
        };
        "sv-provenance-report" = mkSvProvenanceReportDerivation {
          inherit name;
          inherit (self) sv;
        };
        il = mkIlDerivation {
          inherit name;
          inherit (self) sv;
          inherit slangPerFileExternModules;
        };
        "yosys-stat" = mkYosysStatDerivation {
          inherit name;
          inherit (self) sv;
          inherit slangPerFileExternModules;
        };
      };
    in self;

  mkPipeline = { name, hfSnapshot, pytorchExported, torchStage
    , allowHwExterns ? false, fpPrimsSv ? null
    , slangPerFileExternModules ? false }:
    mkBasePipeline {
      inherit name hfSnapshot pytorchExported torchStage allowHwExterns
        fpPrimsSv slangPerFileExternModules;
      handshakeFromCf = mkHandshakeDerivation;
    };

  mkTosaPipeline = { name, hfSnapshot, pytorchExported, torchStage
    , allowHwExterns ? false, fpPrimsSv ? null
    , slangPerFileExternModules ? false }:
    let
      self = mkBasePipeline {
        inherit name hfSnapshot pytorchExported torchStage allowHwExterns
          fpPrimsSv slangPerFileExternModules;
        handshakeFromCf = mkHandshakeDerivation;
        tosaFromTorch = mkTosaDerivation;
        linalgFromStages = { name, tosa, ... }:
          mkTosaToLinalgDerivation { inherit name tosa; };
      };
    in self;

  mkNoHandshakePipeline = { name, hfSnapshot, pytorchExported, torchStage
    , tosaFromTorch ? null, linalgFromStages ?
      ({ name, torch, ... }: mkLinalgDerivation { inherit name torch; })
    , allowHwExterns ? false, fpPrimsSv ? null
    , slangPerFileExternModules ? false }:
    let
      unavailable = stage: reason:
        mkUnavailableStage { inherit name stage reason; };
      self = {
        "hf-snapshot" = hfSnapshot;
        "pytorch-exported" = pytorchExported;
        torch = torchStage;
        "torch-stats" = mkMlirOpStatsDerivation {
          inherit name;
          stageName = "torch";
          tool = torchMlirOpt;
          input = self.torch;
        };
        tosa = if tosaFromTorch == null then
          unavailable "tosa"
          "direct Torch-to-Linalg no-handshake pipeline does not emit a TOSA handoff"
        else
          tosaFromTorch {
            inherit name;
            inherit (self) torch;
          };
        linalg = linalgFromStages {
          inherit name;
          inherit (self) torch tosa;
        };
        scf = mkLinalgToScfDerivation {
          inherit name;
          inherit (self) linalg;
        };
        "flat-scf" = mkScfToFlatScfDerivation {
          inherit name;
          inherit (self) scf;
        };
        calyx = mkScfToCalyxDerivation {
          inherit name;
          flatScf = self."flat-scf";
        };
        "calyx-native-sv" = mkCalyxNativeSvDerivation {
          inherit name;
          inherit (self) calyx;
        };
        "calyx-hw-sv" = mkCalyxHwSvDerivation {
          inherit name;
          inherit (self) calyx;
        };
        "calyx-sv" = self."calyx-native-sv";
        cf = unavailable "cf"
          "no-handshake experiment stops before control-flow hardware lowering";
        "cf-stats" = unavailable "cf-stats"
          "no-handshake experiment does not emit a CF hardware handoff";
        llvm = mkLinalgToLlvmDerivation {
          inherit name;
          inherit (self) linalg;
        };
        handshake = unavailable "handshake"
          "no-handshake experiment intentionally skips Handshake lowering";
        "hs-ext" = unavailable "hs-ext"
          "no-handshake experiment intentionally skips Handshake lowering";
        hw0 = unavailable "hw0"
          "no direct Linalg/SCF/MemRef-to-HW backend is wired yet";
        hw = unavailable "hw"
          "no direct Linalg/SCF/MemRef-to-HW backend is wired yet";
        "hw-clean" = unavailable "hw-clean"
          "no direct Linalg/SCF/MemRef-to-HW backend is wired yet";
        "sv-mlir" = unavailable "sv-mlir"
          "no direct no-handshake HW/SV lowering backend is wired yet";
        sv = unavailable "sv"
          "no direct no-handshake HW/SV lowering backend is wired yet";
        "sv-provenance-report" = mkSvProvenanceReportDerivation {
          inherit name;
          sv = self."calyx-native-sv";
        };
        il = mkIlDerivation {
          inherit name slangPerFileExternModules;
          sv = self."calyx-native-sv";
        };
        "yosys-stat" = mkYosysStatDerivation {
          inherit name slangPerFileExternModules;
          sv = self."calyx-native-sv";
        };
      };
    in self;

  stagePathsForPipeline = publicStageNames: pipeline:
    builtins.listToAttrs (map (stage: {
      name = stage;
      value = "${builtins.getAttr stage pipeline}";
    }) publicStageNames);

  mkPipelineStagePackages = publicStageNames: name: pipeline:
    builtins.listToAttrs (map (stage: {
      name = "${name}-${stage}";
      value = builtins.getAttr stage pipeline;
    }) publicStageNames);

  mkModelMetadata = modelKey: model:
    pkgs.writeText "${modelKey}-pipeline-metadata.json" (builtins.toJSON {
      model = {
        inherit modelKey;
        inherit (model) name description source;
      };
      artifacts = stagePathsForPipeline stageNames model.pipeline;
    });

  registerPipelineModel = { pipelineFactory, name, key ? name, description ? ""
    , source ? { type = "local"; }, hfSnapshot ? null, pytorchToolchain ? [ ]
    , pytorchExportedCommand, pytorchExportedBuildInputs ? pytorchToolchain
    , allowHwExterns ? false, fpPrimsSv ? null
    , slangPerFileExternModules ? false }:
    let
      resolvedHfSnapshot = mkHfSnapshotDerivation { inherit name hfSnapshot; };
      resolvedPyTorchExported = mkPyTorchExportedDerivation {
        inherit name;
        command = pytorchExportedCommand;
        buildInputs = pytorchExportedBuildInputs;
        upstream = resolvedHfSnapshot;
      };
      resolvedTorchStage = mkTorchStage {
        inherit name pytorchToolchain;
        pytorchExported = resolvedPyTorchExported;
      };
      normalizedSource =
        if source ? type then source else source // { type = "local"; };
      pipeline = pipelineFactory {
        inherit name;
        hfSnapshot = resolvedHfSnapshot;
        pytorchExported = resolvedPyTorchExported;
        torchStage = resolvedTorchStage;
        inherit allowHwExterns fpPrimsSv slangPerFileExternModules;
      };
      model = {
        inherit key name description;
        source = normalizedSource;
        hfSnapshot = resolvedHfSnapshot;
        pytorchExported = resolvedPyTorchExported;
        torchStage = resolvedTorchStage;
        inherit pipeline;
      };
      metadata = mkModelMetadata key model;
    in model // { inherit metadata; };

  registerModel = args:
    registerPipelineModel (args // { pipelineFactory = mkPipeline; });

  registerTosaModel = args:
    registerPipelineModel (args // { pipelineFactory = mkTosaPipeline; });

  registerTosaNoHandshakeModel = args:
    registerPipelineModel (args // {
      pipelineFactory = pipelineArgs:
        mkNoHandshakePipeline (pipelineArgs // {
          tosaFromTorch = mkTosaDerivation;
          linalgFromStages = { name, tosa, ... }:
            mkTosaToLinalgDerivation { inherit name tosa; };
        });
    });

  registerNoHandshakeModel = args:
    registerPipelineModel
    (args // { pipelineFactory = mkNoHandshakePipeline; });

  pipelineStagePackagesFromRegistry = registry:
    pkgs.lib.concatMapAttrs
    (name: model: mkPipelineStagePackages stageNames name model.pipeline)
    registry;

  metadataPackagesFromRegistry = registry:
    pkgs.lib.mapAttrs' (name: model:
      pkgs.lib.nameValuePair "${name}-pipeline-metadata" model.metadata)
    registry;

  registryIndexPackage = registry:
    pkgs.writeText "model-registry.json" (builtins.toJSON (pkgs.lib.mapAttrs
      (name: model: {
        inherit (model) name description source;
        packages = builtins.listToAttrs (map (stage: {
          name = stage;
          value = "${name}-${stage}";
        }) stageNames);
      }) registry));
in {
  inherit registerModel registerTosaModel registerTosaNoHandshakeModel
    registerNoHandshakeModel;
  inherit pipelineStagePackagesFromRegistry;
  inherit metadataPackagesFromRegistry;
  inherit registryIndexPackage;
}
