{ pkgs, mlir, circt, calyxTool, yosysPkg, yosysSlang, torchMlir, python
, pipelineScripts, compilePyTorch, svProvenanceReport, noHandshakeLinalgToScf
, noHandshakeScfToFlatScf, noHandshakeScfToCalyx, noHandshakeLinalgToLlvm
, calyxToSvNoHandshake, calyxToHwSvNoHandshake, flatScfBlockerReport, mlirPasses
, circtPasses, tosaToLinalgMlir ? mlir, torchMlirPasses ? null
, exactSerialGemvModelNames ? [ ] }:
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

  calyxPreflightReport = pkgs.substituteAll {
    src = "${pipelineScripts}/calyx_preflight_report.py";
    calyxPreflightMlirOptPath = "${mlir}/bin/mlir-opt";
    calyxPreflightMlirOptVersion = pkgs.lib.getVersion mlir;
    calyxPreflightMlirOptSha256 =
      builtins.hashFile "sha256" "${mlir}/bin/mlir-opt";
  };

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
    let
      exactSerialGemv = builtins.elem name exactSerialGemvModelNames;
      exactSerialGemvArgs = if !exactSerialGemv then "" else
        if torchMlirPasses == null then
          throw "exact serial-GEMV model ${name} requires torchMlirPasses"
        else "--torch-mlir-opt ${torchMlirOpt} "
          + "--pass-plugin ${torchMlirPasses}/lib/LLM2FPGATorchMLIRPasses.so "
          + "--custom-op-library ${../TinyStories/serial_gemv_boundary.py}";
    in pkgs.runCommand "${name}-torch.mlir" {
      buildInputs = pytorchToolchain
        ++ pkgs.lib.optionals exactSerialGemv [ torchMlirPasses ];
    } ''
      set -euo pipefail
      export PYTHONPATH="${torchMlir}/${python.sitePackages}:${torchMlir}/${python.sitePackages}/torch_mlir:''${PYTHONPATH:-}"
      python ${compilePyTorch} \
        --exported-program-dir ${pytorchExported} \
        --out "$out" ${exactSerialGemvArgs} >/dev/null
    '';

  # A deliberately bounded compiler-owned Calyx handoff for one legalized
  # serial-GEMV descriptor.  Full-model composition remains a later task: this
  # derivation proves the component/invoke, Calyx export, and SV parser path
  # without returning to the scalarized SCF route.
  mkExactSerialGemvCalyxDerivation = { name, descriptor }:
    pkgs.runCommand "${name}-exact-serial-gemv-calyx" {
      buildInputs = [ python circt calyxTool yosysPkg ];
    } ''
      set -euo pipefail
      mkdir -p "$out"
      timeout 1800 ${python}/bin/python3 \
        ${pipelineScripts}/lower_exact_serial_gemv_to_calyx.py \
        --input ${descriptor} \
        --output "$out/model.calyx.mlir" \
        --trace "$out/ordered-address-data-trace.json" \
        --provenance "$out/provenance.json"
      timeout 1800 ${circt}/bin/circt-opt "$out/model.calyx.mlir" \
        -o "$out/parsed.calyx.mlir"
      timeout 1800 ${circt}/bin/circt-translate --export-calyx \
        "$out/parsed.calyx.mlir" -o "$out/model.futil"
      timeout 1800 ${calyxTool}/bin/calyx "$out/model.futil" \
        -l ${calyxTool}/share/calyx -b verilog --synthesis --nested \
        -d papercut -o "$out/model.sv"
      timeout 1800 ${yosysPkg}/bin/yosys -p \
        "read_verilog -sv $out/model.sv; hierarchy -check; stat" \
        >"$out/yosys-stat.txt"
      test -s "$out/ordered-address-data-trace.json"
      test -s "$out/model.sv"
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

  mkScfToCalyxDerivation = { name, flatScf, calyxMathProfile ? "none" }:
    let
      mathPasses = if calyxMathProfile == "none" then ""
        else if calyxMathProfile == "scout" then
          ",llm2fpga-lower-scout-math-for-calyx,llm2fpga-lower-constant-fpowi-for-calyx"
        else if calyxMathProfile == "equivalence-candidate" then
          ",llm2fpga-lower-polynomial-exp-for-calyx,llm2fpga-lower-constant-fpowi-for-calyx,llm2fpga-lower-rational-tanh-for-calyx"
        else throw "unsupported Calyx math profile: ${calyxMathProfile}";
    in pkgs.runCommand "${name}-calyx" { buildInputs = [ mlir circt python ]; } ''
      tmp_pre_calyx="$(mktemp /tmp/no_handshake_pre_calyx_XXXXXX.mlir)"
      tmp_zero_seed_fixed="$(mktemp /tmp/no_handshake_zero_seed_XXXXXX.mlir)"
      mkdir -p "$out"
      ${python}/bin/python3 ${pipelineScripts}/materialize_zero_seed_copies.py \
        ${flatScf}/flat.scf.mlir "$tmp_zero_seed_fixed" \
        "$out/zero-seed-materialization-receipt.json"
      ${mlir}/bin/mlir-opt "$tmp_zero_seed_fixed" \
        --load-pass-plugin=${mlirPasses}/lib/LLM2FPGAMLIRPasses.so \
        --pass-pipeline='builtin.module(llm2fpga-lower-static-memref-views-for-calyx,llm2fpga-drop-calyx-unsupported-asserts,llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-negf-for-calyx${mathPasses},llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)' \
        -o "$tmp_pre_calyx"
      export CALYX_PREFLIGHT_REPORT=${calyxPreflightReport}
      ${pkgs.bash}/bin/bash ${noHandshakeScfToCalyx} \
        ${circt}/bin/circt-opt "$tmp_pre_calyx" "$out"
      ${python}/bin/python3 ${pipelineScripts}/calyx_float_frontier_report.py \
        "$out/flat.scf.mlir" "$out/float-frontier.json" \
        --manifest-json "$out/manifest.json"
      test -f "$out/manifest.json"
      test -f "$out/float-frontier.json"
      test -f "$out/pre-calyx-legality.json"
      test -f "$out/zero-seed-materialization-receipt.json"
      if ${pkgs.gnugrep}/bin/grep -q '"status":"ok"' "$out/manifest.json"; then
        test -f "$out/model.calyx.mlir"
      fi
    '';

  mkLinalgToLlvmDerivation = { name, linalg }:
    pkgs.runCommand "${name}-llvm.mlir" { buildInputs = [ mlir ]; } ''
      ${pkgs.bash}/bin/bash ${noHandshakeLinalgToLlvm} \
        ${mlir}/bin/mlir-opt ${linalg} "$out"
    '';

  mkCalyxNativeSvDerivation = { name, calyx, calyxCompilePasses ? [ ]
    , calyxEmitNested ? true, calyxSkipResourceReport ? false }:
    pkgs.runCommand "${name}-calyx-native-sv" {
      buildInputs = [ circt calyxTool python ];
    } ''
      export CALYX_NORMALIZE_FOR_EXPORT=${pipelineScripts}/normalize_calyx_for_export.py
      export CALYX_NORMALIZE_FUTIL_CONSTANTS=${pipelineScripts}/normalize_futil_float_constants.py
      export CALYX_FIX_FUTIL_FPTOSI_HANDSHAKE=${pipelineScripts}/fix_futil_fptosi_handshake.py
      export CALYX_FIX_SV_DIVSQRT_HANDSHAKE=${pipelineScripts}/fix_sv_divsqrt_handshake.py
      export CALYX_VERIFY_F32_CONSTANT_BITS=${pipelineScripts}/verify_calyx_f32_constant_bits.py
      export CALYX_COMPILE_PASSES=${pkgs.lib.escapeShellArg (pkgs.lib.concatStringsSep " " calyxCompilePasses)}
      export CALYX_EMIT_NESTED=${if calyxEmitNested then "1" else "0"}
      export CALYX_SKIP_RESOURCE_REPORT=${if calyxSkipResourceReport then "1" else "0"}
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
    , slangPerFileExternModules ? false, calyxMathProfile ? "none"
    , calyxCompilePasses ? [ ], calyxEmitNested ? true
    , calyxSkipResourceReport ? false }:
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
          inherit name calyxMathProfile;
          flatScf = self."flat-scf";
        };
        "calyx-native-sv" = mkCalyxNativeSvDerivation {
          inherit name calyxCompilePasses calyxEmitNested
            calyxSkipResourceReport;
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
    , slangPerFileExternModules ? false, calyxMathProfile ? "none"
    , calyxCompilePasses ? [ ], calyxEmitNested ? true
    , calyxSkipResourceReport ? false }:
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
        inherit allowHwExterns fpPrimsSv slangPerFileExternModules
          calyxMathProfile calyxCompilePasses calyxEmitNested
          calyxSkipResourceReport;
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

  withoutNoHandshakeCalyxOptions = pipelineArgs:
    builtins.removeAttrs pipelineArgs [
      "calyxMathProfile"
      "calyxCompilePasses"
      "calyxEmitNested"
      "calyxSkipResourceReport"
    ];

  registerModel = args:
    registerPipelineModel (args // {
      pipelineFactory = pipelineArgs:
        mkPipeline (withoutNoHandshakeCalyxOptions pipelineArgs);
    });

  registerTosaModel = args:
    registerPipelineModel (args // {
      pipelineFactory = pipelineArgs:
        mkTosaPipeline (withoutNoHandshakeCalyxOptions pipelineArgs);
    });

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
  inherit mkExactSerialGemvCalyxDerivation;
  inherit registerModel registerTosaModel registerTosaNoHandshakeModel
    registerNoHandshakeModel;
  inherit pipelineStagePackagesFromRegistry;
  inherit metadataPackagesFromRegistry;
  inherit registryIndexPackage;
}
