{
  description = "LLM2FPGA MLIR pipeline bring-up lab";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs-llvm21.url =
      "github:NixOS/nixpkgs/346dd96ad74dc4457a9db9de4f4f57dab2e5731d";
    nixpkgs-nix-eda.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
    circt-nix.url = "git+https://github.com/dtzSiFive/circt-nix?ref=main";
    nix-eda = {
      url = "github:fossi-foundation/nix-eda";
      inputs.nixpkgs.follows = "nixpkgs-nix-eda";
    };
    task3-main-pipeline.url = "path:./task3-main";
  };

  outputs = inputs@{ nixpkgs, nixpkgs-llvm21, nixpkgs-nix-eda, flake-utils
    , circt-nix, nix-eda, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        task3MainPackages =
          inputs.task3-main-pipeline.packages.${system};
        pkgsLlvm21 = import nixpkgs-llvm21 {
          inherit system;
          config.allowUnfreePredicate = pkg:
            builtins.elem (nixpkgs.lib.getName pkg) [ "torch" ];
        };

        circtPkgs = circt-nix.packages.${system};
        circt =
          (circtPkgs.circt.override { enableSlang = false; }).overrideAttrs
          (old: {
            # Historical Task 3 recovery stack required for representative-core
            # baseline-float lowering through handshake/HW/SV.
            patches = (old.patches or [ ]) ++ [
              ./archive/patches/unused/circt-upstream-task3-recovery/0001-flatten-memref-shape-ops-after-memref-flattening.patch
              ./archive/patches/unused/circt-upstream-task3-recovery/0002-handle-cfg-threaded-memrefs-in-handshake-lowering.patch
              ./archive/patches/unused/circt-upstream-task3-recovery/0005-handle-dense-resource-globals-in-flattenmemrefs.patch
              ./archive/patches/unused/circt-upstream-task3-recovery/0011-rebased-handshaketohw-stack.patch
              ./archive/patches/unused/circt-upstream-task3-recovery/0012-update-buffer-lowering-test-for-constant-order.patch
            ];
          });
        circtMlir = circtPkgs.mlir;
        circtLlvm = circtPkgs.libllvm;

        nixEdaPkgs = nix-eda.packages.${system};
        yosysPkgBase = nixEdaPkgs.yosys;
        yosysPkgPlugins = with nixEdaPkgs;
          [ yosys-sby yosys-eqy yosys-slang ] ++ pkgs.lib.optionals
          (pkgs.lib.lists.any (el: el == system) yosys-ghdl.meta.platforms)
          [ yosys-ghdl ];
        yosysPkgPluginPaths = pkgs.lib.closePropagation yosysPkgPlugins;
        yosysPkgPluginDylibs = pkgs.lib.lists.flatten
          (map (plugin: plugin.dylibs or [ ]) yosysPkgPlugins);
        yosysPkg = pkgs.symlinkJoin {
          name = "${yosysPkgBase.pname}-with-plugins-${yosysPkgBase.version}";
          paths = yosysPkgPluginPaths ++ [ yosysPkgBase ];
          nativeBuildInputs = [ pkgs.makeWrapper ];
          postBuild = ''
            cat <<SCRIPT > $out/bin/with_yosys_plugin_env
            #!${pkgs.bash}/bin/bash
            export YOSYS_PLUGIN_PATH='$out/share/yosys/plugins'
            exec "\$@"
            SCRIPT
            chmod +x $out/bin/with_yosys_plugin_env
            cp $out/bin/yosys $out/bin/yosys_with_plugins
            wrapProgram $out/bin/yosys \
              --suffix YOSYS_PLUGIN_PATH : $out/share/yosys/plugins
            wrapProgram $out/bin/yosys_with_plugins \
              --suffix YOSYS_PLUGIN_PATH : $out/share/yosys/plugins \
              ${
                builtins.concatStringsSep " "
                (map (so: "--add-flags -m --add-flags ${so}")
                  yosysPkgPluginDylibs)
              }
          '';
          passthru = yosysPkgBase.passthru;
          meta.mainProgram = "yosys_with_plugins";
        };
        yosysSlang = nixEdaPkgs.yosys-slang;

        llvmPackages = pkgsLlvm21.llvmPackages_21;
        torchMlirLlvmPackages = (pkgsLlvm21.llvmPackages_git.override {
          llvmVersions = {
            "22.0.0-git" = {
              gitRelease = {
                rev = "3ca2a5fc0b84762f0e7d8a0e613fd69f7e344219";
                rev-version = "23.0.0-unstable-2026-01-20";
                sha256 = "sha256-jjdb2PtKnjYo9RIGJ82YtKmZinqEOlmm7R64SeJqTac=";
              };
            };
          };
        }).overrideScope (final: prev: {
          libllvm =
            (prev.libllvm.override { buildLlvmPackages = final; }).overrideAttrs
            (old: {
              postConfigure = "";
              doCheck = false;
              cmakeFlags = (old.cmakeFlags or [ ]) ++ [
                (pkgsLlvm21.lib.cmakeBool "LLVM_BUILD_TESTS" false)
                (pkgsLlvm21.lib.cmakeBool "LLVM_INCLUDE_TESTS" false)
              ];
            });
        });
        inherit (llvmPackages) mlir;
        python = pkgsLlvm21.python311;

        torchao = python.pkgs.buildPythonPackage rec {
          pname = "torchao";
          version = "0.15.0";
          format = "wheel";
          src = pkgs.fetchurl {
            url =
              "https://files.pythonhosted.org/packages/f6/3b/6b9d5618720f63dbc2e2509cd6b57aae9c0d61b738d1d2172f4d5d9efaab/torchao-0.15.0-py3-none-any.whl";
            hash = "sha256-PzgSZ2BI74oqDp1JLRLYlxunp+uxb1SqVvaQQU4TDSw=";
          };
          propagatedBuildInputs = [ python.pkgs.torch ];
          dontBuild = true;
          doCheck = false;
          pythonImportsCheck = [ "torchao" ];
        };
        pythonWithTinyStories =
          python.withPackages (ps: [ ps.torch ps.packaging ps.transformers ]);
        pythonWithTinyStoriesTorchAO = python.withPackages
          (ps: [ ps.torch ps.packaging ps.transformers torchao ]);

        nanobindBootstrap =
          pkgsLlvm21.callPackage ./nix/nanobind-bootstrap.nix {
            inherit python;
          };
        mlirForTorchMlir = (torchMlirLlvmPackages.mlir.override {
          devExtraCmakeFlags =
            [ (pkgsLlvm21.lib.cmakeBool "MLIR_ENABLE_BINDINGS_PYTHON" true) ];
        }).overrideAttrs (old: {
          doCheck = false;
          nativeBuildInputs = old.nativeBuildInputs ++ [ python ];
          preConfigure = (old.preConfigure or "") + ''
            export PYTHONPATH="${python.pkgs.pybind11}/${python.sitePackages}:${nanobindBootstrap}/${python.sitePackages}:''${PYTHONPATH:-}"
          '';
          cmakeFlags = (old.cmakeFlags or [ ]) ++ [
            (pkgsLlvm21.lib.cmakeBool "LLVM_BUILD_TESTS" false)
            (pkgsLlvm21.lib.cmakeFeature "Python3_EXECUTABLE"
              "${python}/bin/python3")
            (pkgsLlvm21.lib.cmakeFeature "Python_EXECUTABLE"
              "${python}/bin/python3")
            (pkgsLlvm21.lib.cmakeFeature "pybind11_DIR"
              "${python.pkgs.pybind11}/${python.sitePackages}/pybind11/share/cmake/pybind11")
            (pkgsLlvm21.lib.cmakeFeature "nanobind_DIR"
              "${nanobindBootstrap}/${python.sitePackages}/nanobind/cmake")
          ];
        });
        torchMlir = pkgsLlvm21.callPackage ./torch-mlir.nix {
          inherit python;
          nanobind = nanobindBootstrap;
          inherit (torchMlirLlvmPackages) tblgen;
          mlir = mlirForTorchMlir;
          inherit (torchMlirLlvmPackages) llvm;
        };
        llm2fpgaMlirPasses = pkgsLlvm21.callPackage ./nix/mlir-passes.nix {
          inherit mlir llvmPackages;
        };
        llm2fpgaTorchMlirPasses =
          pkgsLlvm21.callPackage ./nix/mlir-passes.nix {
            mlir = mlirForTorchMlir;
            llvmPackages = torchMlirLlvmPackages;
          };
        llm2fpgaCirctPasses = pkgs.callPackage ./nix/circt-passes.nix {
          inherit circt;
          mlir = circtMlir;
          llvm = circtLlvm;
        };
        calyx = pkgs.callPackage ./nix/calyx.nix { };

        pipelineScripts = ./scripts/pipeline;
        svProvenanceReport = ./scripts/diagnostics/sv_provenance_report.py;
        noHandshakeLinalgToScf =
          ./scripts/pipeline/linalg_to_scf_no_handshake.sh;
        noHandshakeScfToFlatScf =
          ./scripts/pipeline/scf_to_flat_scf_no_handshake.sh;
        noHandshakeScfToCalyx = ./scripts/pipeline/scf_to_calyx_no_handshake.sh;
        calyxToSvNoHandshake = ./scripts/pipeline/calyx_to_sv_no_handshake.sh;
        calyxToHwSvNoHandshake =
          ./scripts/pipeline/calyx_to_hw_sv_no_handshake.sh;
        noHandshakeLinalgToLlvm =
          ./scripts/pipeline/linalg_to_llvm_no_handshake.sh;
        flatScfBlockerReport = ./scripts/diagnostics/flat_scf_blocker_report.py;
        fpPrimsSv = ./rtl/fp/circt_fp_primitives.sv;
        task3FpPrimitiveBlackboxes =
          pkgs.runCommand "task3-circt-fp-primitive-blackboxes.sv" { } ''
            ${python}/bin/python3 ${pipelineScripts}/write_fp_primitive_blackboxes.py \
              --input ${fpPrimsSv} \
              --output "$out"
          '';
        tinyStories1m = let
          modelId = "roneneldan/TinyStories-1M";
          revision = "77f1b168e219585646439073245fe87e56b3023e";
          fetch = file: hash:
            pkgs.fetchurl {
              url =
                "https://huggingface.co/${modelId}/resolve/${revision}/${file}";
              inherit hash;
            };
          snapshot = pkgs.linkFarm "tinystories-1m-hf-snapshot" [
            {
              name = "config.json";
              path = fetch "config.json"
                "sha256-/3TDDV67WrHaDy6kea33GXxQS0K1UiqFjDNKuR7UlYw=";
            }
            {
              name = "pytorch_model.bin";
              path = fetch "pytorch_model.bin"
                "sha256-B/lgnqiCuBY/87I9QOK4LLcV1AljG+sVyEsWTzh32uc=";
            }
          ];
        in {
          inherit modelId revision snapshot;
          sourceDir = ./TinyStories;
          adapterPy = ./TinyStories/model_adapter.py;
        };

        pipelineLib = import ./nix/pipeline.nix {
          inherit pkgs mlir circt yosysPkg yosysSlang torchMlir python;
          calyxTool = calyx;
          inherit pipelineScripts svProvenanceReport noHandshakeLinalgToScf
            noHandshakeScfToFlatScf noHandshakeScfToCalyx calyxToSvNoHandshake
            calyxToHwSvNoHandshake noHandshakeLinalgToLlvm;
          mlirPasses = llm2fpgaMlirPasses;
          circtPasses = llm2fpgaCirctPasses;
          inherit flatScfBlockerReport;
          compilePyTorch = ./scripts/compile-pytorch.py;
        };
        modelRegistry = import ./nix/models.nix {
          inherit (pipelineLib) registerModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO torchMlir
            tinyStories1m fpPrimsSv;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackages =
          pipelineLib.pipelineStagePackagesFromRegistry modelRegistry;
        pipelineMetadataPackages =
          pipelineLib.metadataPackagesFromRegistry modelRegistry;
        modelRegistryJson = pipelineLib.registryIndexPackage modelRegistry;
        modelRegistryNoHandshake = import ./nix/models.nix {
          registerModel = pipelineLib.registerNoHandshakeModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO torchMlir
            tinyStories1m fpPrimsSv;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesNoHandshake =
          pipelineLib.pipelineStagePackagesFromRegistry
          modelRegistryNoHandshake;
        pipelineLibTosa = import ./nix/pipeline.nix {
          inherit pkgs mlir circt yosysPkg yosysSlang python;
          calyxTool = calyx;
          tosaToLinalgMlir = mlirForTorchMlir;
          inherit torchMlir;
          inherit pipelineScripts svProvenanceReport noHandshakeLinalgToScf
            noHandshakeScfToFlatScf noHandshakeScfToCalyx calyxToSvNoHandshake
            calyxToHwSvNoHandshake noHandshakeLinalgToLlvm;
          mlirPasses = llm2fpgaTorchMlirPasses;
          circtPasses = llm2fpgaCirctPasses;
          inherit flatScfBlockerReport;
          compilePyTorch = ./scripts/compile-pytorch.py;
        };
        modelRegistryTosa = import ./nix/models.nix {
          registerModel = pipelineLibTosa.registerTosaModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO
            tinyStories1m fpPrimsSv;
          inherit torchMlir;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesTosa =
          pipelineLibTosa.pipelineStagePackagesFromRegistry modelRegistryTosa;
        modelRegistryTosaNoHandshake = import ./nix/models.nix {
          registerModel = pipelineLibTosa.registerTosaNoHandshakeModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO
            tinyStories1m fpPrimsSv;
          inherit torchMlir;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesTosaNoHandshake =
          pipelineLibTosa.pipelineStagePackagesFromRegistry
          modelRegistryTosaNoHandshake;
        handshakeSvStages = [
          "torch"
          "tosa"
          "linalg"
          "cf"
          "handshake"
          "hs-ext"
          "hw0"
          "hw"
          "hw-clean"
          "sv-mlir"
          "sv"
          "sv-provenance-report"
          "yosys-stat"
        ];
        handshakeHwStages = [
          "torch"
          "tosa"
          "linalg"
          "cf"
          "handshake"
          "hs-ext"
          "hw0"
          "hw"
          "hw-clean"
        ];
        noHandshakeStages = [
          "torch"
          "tosa"
          "linalg"
          "scf"
          "flat-scf"
          "calyx"
          "calyx-native-sv"
          "calyx-hw-sv"
          "calyx-sv"
          "sv-provenance-report"
          "il"
          "yosys-stat"
          "llvm"
        ];
        noHandshakeLinalgStages = [
          "torch"
          "linalg"
          "scf"
          "flat-scf"
          "calyx"
          "calyx-native-sv"
          "calyx-hw-sv"
          "calyx-sv"
          "sv-provenance-report"
          "il"
          "yosys-stat"
          "llvm"
        ];
        mkPipelineAlias = spec: stage: {
          name = "${spec.alias}-${stage}";
          value = builtins.getAttr "${spec.model}-${stage}" spec.packages;
        };
        mkPipelineAliases = specs:
          builtins.listToAttrs (pkgs.lib.concatMap
            (spec: map (stage: mkPipelineAlias spec stage) spec.stages) specs);
        pipelineAliasMetadata = spec: {
          inherit (spec) alias model frontend backend stages;
          generatedAliases = map (stage: {
            inherit stage;
            name = "${spec.alias}-${stage}";
            sourcePackage = "${spec.model}-${stage}";
          }) spec.stages;
        };
        pipelineAliasSpecs = [
          {
            alias = "pattern-linear-w4a8-via-tosa";
            model = "pattern-linear-w4a8";
            frontend = "tosa";
            backend = "handshake-sv";
            packages = pipelineStagePackagesTosa;
            stages = handshakeSvStages;
          }
          {
            alias = "pattern-linear-w4a8-core-via-tosa";
            model = "pattern-linear-w4a8-core";
            frontend = "tosa";
            backend = "handshake-sv";
            packages = pipelineStagePackagesTosa;
            stages = handshakeSvStages;
          }
          {
            alias = "tinystories-representative-core-w4a8-via-tosa";
            model = "tinystories-representative-core-w4a8";
            frontend = "tosa";
            backend = "handshake-hw";
            packages = pipelineStagePackagesTosa;
            stages = handshakeHwStages;
          }
          {
            alias = "pattern-linear-w4a8-core-via-tosa-no-handshake";
            model = "pattern-linear-w4a8-core";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias = "pattern-embedding-w4a8-core-via-tosa-no-handshake";
            model = "pattern-embedding-w4a8-core";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias = "pattern-layernorm-w4a8-core-via-tosa-no-handshake";
            model = "pattern-layernorm-w4a8-core";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias = "tinystories-w8a8-via-tosa-no-handshake";
            model = "tinystories-w8a8";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8";
            frontend = "linalg";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesNoHandshake;
            stages = noHandshakeLinalgStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-fixed-layernorm-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8-fixed-layernorm";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-fixed-layernorm-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8-fixed-layernorm";
            frontend = "linalg";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesNoHandshake;
            stages = noHandshakeLinalgStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-integer-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8-integer";
            frontend = "tosa";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-integer-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8-integer";
            frontend = "linalg";
            backend = "calyx-native-sv";
            packages = pipelineStagePackagesNoHandshake;
            stages = noHandshakeLinalgStages;
          }
        ];
        pipelineAliasPackages = mkPipelineAliases pipelineAliasSpecs;
        activePipelineVariantsJson =
          pkgs.writeText "active-pipeline-variants.json" (builtins.toJSON {
            schemaVersion = 1;
            variants = map pipelineAliasMetadata pipelineAliasSpecs;
          });
        quantizedLinalgDiagnosticPackages = {
          "pattern-linear-w4a8-tosa" =
            pkgs.runCommand "pattern-linear-w4a8-tosa.mlir" {
              buildInputs = [ torchMlir ];
            } ''
              ${torchMlir}/bin/torch-mlir-opt \
                ${pipelineStagePackages."pattern-linear-w4a8-torch"} \
                --torch-backend-to-tosa-backend-pipeline \
                -o "$out"
            '';

          "pattern-linear-w4a8-linalg-diagnostics" =
            pkgs.runCommand "pattern-linear-w4a8-linalg-diagnostics.json" { } ''
              ${python}/bin/python3 ${
                ./scripts/pipeline/diagnose_quantized_linalg.py
              } \
                --stage pattern-linear-w4a8-linalg \
                --input ${pipelineStagePackages."pattern-linear-w4a8-linalg"} \
                --out "$out" \
                --fail-on-float-after-quantized-matmul
            '';
        };
        tinystoriesW8A8Pt2eGraphShapeAudit =
          pkgs.runCommand "tinystories-w8a8-pt2e-graph-shape-audit" { } ''
            mkdir -p "$out"
            ${python}/bin/python3 ${
              ./scripts/pipeline/pt2e_graph_shape_audit.py
            } \
              --graph ${
                pipelineStagePackages."tinystories-w8a8-pytorch-exported"
              }/graph.txt \
              --json-out "$out/report.json" \
              --markdown-out "$out/report.md" \
              --model-label tinystories-w8a8
          '';
        resourceBaselineYosysStatMatrix =
          pkgs.runCommand "resource-baseline-yosys-stat-matrix" { } ''
            mkdir -p "$out"
            ${python}/bin/python3 ${
              ./scripts/pipeline/summarize_yosys_stat_baselines.py
            } \
              --entry alias=pattern-linear-w4a8-core-via-tosa-no-handshake,model=pattern-linear-w4a8-core,frontend=tosa,backend=calyx-native-sv,stat=${
                pipelineAliasPackages."pattern-linear-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=pattern-embedding-w4a8-core-via-tosa-no-handshake,model=pattern-embedding-w4a8-core,frontend=tosa,backend=calyx-native-sv,stat=${
                pipelineAliasPackages."pattern-embedding-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=pattern-layernorm-w4a8-core-via-tosa-no-handshake,model=pattern-layernorm-w4a8-core,frontend=tosa,backend=calyx-native-sv,stat=${
                pipelineAliasPackages."pattern-layernorm-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=tinystories-representative-core-w4a8-integer-via-linalg-no-handshake,model=tinystories-representative-core-w4a8-integer,frontend=linalg,backend=calyx-native-sv,stat=${
                pipelineAliasPackages."tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat"
              } \
              --entry alias=tinystories-representative-core-w4a8-integer-via-tosa-no-handshake,model=tinystories-representative-core-w4a8-integer,frontend=tosa,backend=calyx-native-sv,stat=${
                pipelineAliasPackages."tinystories-representative-core-w4a8-integer-via-tosa-no-handshake-yosys-stat"
              } \
              --summary-json "$out/summary.json" \
              --summary-md "$out/summary.md"
          '';
        tinystoriesIntegerSvEquivalenceReport = pkgs.runCommand
          "tinystories-representative-core-w4a8-integer-sv-equivalence" {
            buildInputs = [ pythonWithTinyStories ];
          } ''
            mkdir -p "$out"
            ${pythonWithTinyStories}/bin/python ${
              ./scripts/pipeline/tinystories_integer_reference.py
            } \
              --adapter ${
                ./TinyStories/model_adapter_representative_core_w4a8_integer.py
              } \
              --out "$out/reference.json"
            ${pythonWithTinyStories}/bin/python ${
              ./scripts/pipeline/tinystories_integer_sv_equivalence_report.py
            } \
              --sv-dir ${
                pipelineAliasPackages."tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-calyx-native-sv"
              }/sv \
              --expected-json "$out/reference.json" \
              --out "$out/report.json"
          '';
        task3TinyStoriesCapacities = {
          slices = 74650;
          clb_luts = 298600;
          clb_ffs = 597200;
          dsp = 1920;
          bram36 = 955;
          bram_kb = 34380;
        };
        task3BaselineFloatReference =
          ./references/task3/tiny-stories-1m-baseline-float-selftest-all-memory-utilization;
        task3RepresentativeCoreShapeMetadata =
          ./references/task3/representative-core-parity-shapes.json;
        mkTask3YosysRtlil = { name, script, quiet ? false }:
          pkgs.runCommand "${name}.il" { } ''
            cat > run.ys <<EOF
            ${script}
            EOF
            ${yosysPkg}/bin/yosys ${pkgs.lib.optionalString quiet "-q"} \
              -m ${yosysSlang}/share/yosys/plugins/slang.so \
              -s run.ys

            if [ ! -e "$out" ]; then
              echo "mkTask3YosysRtlil expected output path was not created: $out" >&2
              echo "--- run.ys ---" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
        mkTask3YosysJson = { name, modelIl, topName, topSv }:
          pkgs.runCommand "${name}.json" { } ''
            ${yosysPkg}/bin/yosys -m ${yosysSlang}/share/yosys/plugins/slang.so -p "
              read_rtlil ${modelIl}
              read_slang ${topSv}
              hierarchy -top ${topName} -check
              write_json $out
            "
          '';
        mkTask3SynthStageIl = { name, stageId, stageLabel, inputIl, topName
          , topSv ? null, commands, preCommands ? [ ], quiet ? false
          , memoryLimitKb ? null }:
          pkgs.runCommand "${name}-${stageId}.il" { } ''
            cat > run.ys <<EOF
            ${builtins.concatStringsSep "\n" ([ "read_rtlil ${inputIl}" ]
              ++ pkgs.lib.optional (topSv != null) "read_slang ${topSv}"
              ++ [ "hierarchy -top ${topName} -check" ] ++ preCommands
              ++ commands ++ [ "write_rtlil $out" ])}
            EOF

            ${pkgs.lib.optionalString (memoryLimitKb != null) ''
              ulimit -v ${toString memoryLimitKb}
            ''}

            echo "[mkSynthJson:${name}] ${stageLabel}" >&2
            ${yosysPkg}/bin/yosys ${pkgs.lib.optionalString quiet "-q"} ${
              pkgs.lib.optionalString (topSv != null)
              "-m ${yosysSlang}/share/yosys/plugins/slang.so"
            } -s run.ys

            if [ ! -e "$out" ]; then
              echo "mkTask3SynthStageIl ${stageId} expected output path was not created: $out" >&2
              echo "--- run.ys ---" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
        mkTask3SynthStageMemoryMapIl =
          { name, stageId, stageLabel, inputIl, topName, quiet ? false
          , memoryLimitKb ? null }:
          pkgs.runCommand "${name}-${stageId}.il" { } ''
            ${pkgs.gawk}/bin/awk '
              /^module / { mod = $2 }
              /^[[:space:]]*cell \$mem/ { mods[mod] = 1 }
              END {
                for (mod in mods)
                  print mod
              }
            ' ${inputIl} | ${pkgs.coreutils}/bin/sort > stage-modules.txt

            cat > run.ys <<EOF
            read_rtlil ${inputIl}
            hierarchy -top ${topName} -check
            EOF

            while IFS= read -r moduleName; do
              printf '%s\n' \
                "cd $moduleName" \
                'memory_map' \
                'cd ..' \
                >> run.ys
            done < stage-modules.txt

            printf '%s\n' "write_rtlil $out" >> run.ys

            ${pkgs.lib.optionalString (memoryLimitKb != null) ''
              ulimit -v ${toString memoryLimitKb}
            ''}

            echo "[mkSynthJson:${name}] ${stageLabel}" >&2
            ${yosysPkg}/bin/yosys ${
              pkgs.lib.optionalString quiet "-q"
            } -s run.ys

            if [ ! -e "$out" ]; then
              echo "mkTask3SynthStageMemoryMapIl ${stageId} expected output path was not created: $out" >&2
              echo "--- run.ys ---" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
        mkTask3SynthStageTargetedTechmapIl =
          { name, stageId, stageLabel, inputIl, topName, quiet ? false
          , memoryLimitKb ? null, cellRegex, techmapArgs, batchSize ? null
          , restartPerBatch ? false }:
          pkgs.runCommand "${name}-${stageId}.il" { } ''
            ${pkgs.gawk}/bin/awk '
              /^module / { mod = $2 }
              /^[[:space:]]*cell / {
                cell_name = $2
                if (cell_name ~ ${builtins.toJSON cellRegex})
                  mods[mod] = 1
              }
              END {
                for (mod in mods)
                  print mod
              }
            ' ${inputIl} | ${pkgs.coreutils}/bin/sort > stage-modules.txt

            moduleCount=$(${pkgs.coreutils}/bin/wc -l < stage-modules.txt)
            ${pkgs.lib.optionalString (batchSize != null) ''
              batchSize=${toString batchSize}
              if [ "$moduleCount" -eq 0 ]; then
                batchCount=0
              else
                batchCount=$(( (moduleCount + batchSize - 1) / batchSize ))
              fi
            ''}

            ${pkgs.lib.optionalString (memoryLimitKb != null) ''
              ulimit -v ${toString memoryLimitKb}
            ''}

            echo "[mkSynthJson:${name}] ${stageLabel} (selected modules: $moduleCount${
              pkgs.lib.optionalString (batchSize != null)
              ", batch size: ${toString batchSize}, batches: \$batchCount${
                pkgs.lib.optionalString restartPerBatch ", mode: restart"
              }"
            })" >&2

            ${pkgs.lib.optionalString (batchSize == null) ''
              cat > run.ys <<EOF
              read_rtlil ${inputIl}
              hierarchy -top ${topName} -check
              select -none
              EOF

              while IFS= read -r moduleName; do
                printf '%s\n' \
                  "select -add $moduleName" \
                  >> run.ys
              done < stage-modules.txt

              cat >> run.ys <<EOF
              techmap ${techmapArgs}
              select -clear
              write_rtlil $out
              EOF

              ${yosysPkg}/bin/yosys ${
                pkgs.lib.optionalString quiet "-q"
              } -s run.ys
            ''}

            ${pkgs.lib.optionalString (batchSize != null && !restartPerBatch) ''
              cat > run.ys <<EOF
              read_rtlil ${inputIl}
              hierarchy -top ${topName} -check
              select -none
              EOF

              batchModules=0
              while IFS= read -r moduleName; do
                if [ "$batchModules" -gt 0 ] && [ $((batchModules % batchSize)) -eq 0 ]; then
                  cat >> run.ys <<EOF
            techmap ${techmapArgs}
            select -clear
            select -none
            EOF
                fi
                printf '%s\n' \
                  "select -add $moduleName" \
                  >> run.ys
                batchModules=$((batchModules + 1))
              done < stage-modules.txt

              if [ "$moduleCount" -gt 0 ]; then
                cat >> run.ys <<EOF
            techmap ${techmapArgs}
            select -clear
            EOF
              fi

              cat >> run.ys <<EOF
            write_rtlil $out
            EOF

              ${yosysPkg}/bin/yosys ${
                pkgs.lib.optionalString quiet "-q"
              } -s run.ys
            ''}

            ${pkgs.lib.optionalString (batchSize != null && restartPerBatch) ''
              cp ${inputIl} work.il

              if [ "$moduleCount" -gt 0 ]; then
                batchIndex=0
                while [ "$batchIndex" -lt "$batchCount" ]; do
                  startLine=$((batchIndex * batchSize + 1))
                  endLine=$((startLine + batchSize - 1))
                  ${pkgs.gnused}/bin/sed -n "''${startLine},''${endLine}p" stage-modules.txt > batch-modules.txt

                  echo "[mkSynthJson:${name}] ${stageLabel} batch $((batchIndex + 1))/$batchCount" >&2

                  printf '%s\n' \
                    'read_rtlil work.il' \
                    'hierarchy -top ${topName} -check' \
                    'select -none' \
                    > run.ys

                  while IFS= read -r moduleName; do
                    printf '%s\n' \
                      "select -add $moduleName" \
                      >> run.ys
                  done < batch-modules.txt

                  printf '%s\n' \
                    'techmap ${techmapArgs}' \
                    'select -clear' \
                    'write_rtlil next.il' \
                    >> run.ys

                  ${yosysPkg}/bin/yosys ${
                    pkgs.lib.optionalString quiet "-q"
                  } -s run.ys

                  mv next.il work.il
                  batchIndex=$((batchIndex + 1))
                done
              fi

              cp work.il $out
            ''}

            if [ ! -e "$out" ]; then
              echo "mkSynthJson ${stageId} expected output path was not created: $out" >&2
              echo "--- run.ys ---" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
        mkTask3SynthStageJson =
          { name, stageId, stageLabel, inputIl, quiet ? false
          , memoryLimitKb ? null }:
          pkgs.runCommand "${name}.json" { } ''
            ${python}/bin/python3 ${pipelineScripts}/filter_rtlil_modules.py \
              --input ${inputIl} \
              --output stage8-stripped.il \
              --drop-escaped-uppercase-modules

            cat > run.ys <<EOF
            read_rtlil stage8-stripped.il
            proc
            write_json $out
            EOF

            ${pkgs.lib.optionalString (memoryLimitKb != null) ''
              ulimit -v ${toString memoryLimitKb}
            ''}

            echo "[mkSynthJson:${name}] ${stageLabel}" >&2
            ${yosysPkg}/bin/yosys ${
              pkgs.lib.optionalString quiet "-q"
            } -s run.ys

            if [ ! -e "$out" ]; then
              echo "mkTask3SynthStageJson ${stageId} expected output path was not created: $out" >&2
              echo "--- run.ys ---" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
        mkTask3SynthStage9Debug =
          { name, inputIl, failingLine ? 66916687, contextLines ? 40 }:
          pkgs.runCommand "${name}-stage9-debug" { } ''
            mkdir -p "$out"

            ${python}/bin/python3 ${pipelineScripts}/filter_rtlil_modules.py \
              --input ${inputIl} \
              --output stage8-stripped.il \
              --drop-escaped-uppercase-modules

            line=${toString failingLine}
            context=${toString contextLines}
            line_count=$(${pkgs.coreutils}/bin/wc -l < stage8-stripped.il)
            focus_line=$line
            if [ "$focus_line" -gt "$line_count" ]; then
              focus_line=$line_count
            fi
            start=$((line - context))
            end=$((line + context))
            if [ "$line" -gt "$line_count" ]; then
              start=$((line_count - context))
              end=$line_count
            fi
            if [ "$start" -lt 1 ]; then
              start=1
            fi

            {
              echo "name: ${name}"
              echo "input_il: ${inputIl}"
              echo "filtered_line_count: $line_count"
              echo "failing_line: $line"
              echo "context_focus_line: $focus_line"
              echo "context_start: $start"
              echo "context_end: $end"
            } > "$out/summary.txt"

            ${pkgs.gnused}/bin/sed -n "''${start},''${end}p" stage8-stripped.il \
              > "$out/failing-line-context.il"
            ${pkgs.gnused}/bin/sed -n "''${start},''${end}p" stage8-stripped.il \
              | ${pkgs.coreutils}/bin/nl -ba -v "$start" \
              > "$out/failing-line-context-numbered.il"
            ${pkgs.coreutils}/bin/tail -n "$context" stage8-stripped.il > "$out/eof-context.il"

            cat > "$out/run.ys" <<EOF
            read_rtlil stage8-stripped.il
            proc
            write_json stage9-debug.json
            EOF

            set +e
            ${yosysPkg}/bin/yosys -s "$out/run.ys" \
              > "$out/stage9-debug.log" 2>&1
            status=$?
            set -e

            echo "yosys_exit_status: $status" >> "$out/summary.txt"
            if [ -e stage9-debug.json ]; then
              cp stage9-debug.json "$out/stage9-debug.json"
            fi
          '';
        mkTask3SynthJsonStages =
          { name, modelIl, topName, topSv ? null, quiet ? false
          , memoryLimitKb ? null, splitFineStage ? false, useAbc9 ? false
          , stage1PreCommands ? [ "proc" ] }:
          rec {
            stage1 = mkTask3SynthStageIl {
              inherit name topName topSv quiet memoryLimitKb;
              stageId = "stage1";
              stageLabel = "stage1 synth_xilinx begin:prepare";
              inputIl = modelIl;
              preCommands = stage1PreCommands;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run begin:prepare"
              ];
            };
            stage2 = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage2";
              stageLabel = "stage2 synth_xilinx coarse:map_memory";
              inputIl = stage1;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run coarse:map_memory"
              ];
            };
            stage3 = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage3";
              stageLabel = "stage3 opt -fast -full";
              inputIl = stage2;
              commands = [ "opt -fast -full" ];
            };
            stage4 = mkTask3SynthStageMemoryMapIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage4";
              stageLabel = "stage4 targeted memory_map";
              inputIl = stage3;
            };
            stage5a = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage5a";
              stageLabel = "stage5a fine opt -full";
              inputIl = stage4;
              commands = [ "opt -full" ];
            };
            stage5b = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage5b";
              stageLabel = "stage5b xilinx_srl -variable -minlen 3";
              inputIl = stage5a;
              commands = [ "xilinx_srl -variable -minlen 3" ];
            };
            stage5c = mkTask3SynthStageTargetedTechmapIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage5c";
              stageLabel = "stage5c targeted techmap arith_map";
              inputIl = stage5b;
              cellRegex = "^\\$(alu|lcu)$";
              techmapArgs =
                "-map +/techmap.v -D LUT_SIZE=6 -map +/xilinx/arith_map.v";
            };
            stage5d = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage5d";
              stageLabel = "stage5d opt -fast";
              inputIl = stage5c;
              commands = [ "opt -fast" ];
            };
            stage5Monolithic = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage5";
              stageLabel = "stage5 synth_xilinx fine:fine";
              inputIl = stage4;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run fine:fine"
              ];
            };
            stage5 = stage5Monolithic;
            stage6a = mkTask3SynthStageTargetedTechmapIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage6a";
              stageLabel = "stage6a targeted techmap cells_map";
              inputIl = if splitFineStage then stage5d else stage5Monolithic;
              cellRegex = "^\\$";
              techmapArgs = "-map +/techmap.v -map +/xilinx/cells_map.v";
              batchSize = 2;
              restartPerBatch = true;
            };
            stage6b = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage6b";
              stageLabel = "stage6b clean";
              inputIl = stage6a;
              commands = [ "clean" ];
            };
            stage6Monolithic = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage6";
              stageLabel = "stage6 synth_xilinx map_cells:map_cells";
              inputIl = if splitFineStage then stage5d else stage5Monolithic;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run map_cells:map_cells"
              ];
            };
            stage6 = stage6Monolithic;
            stage7 = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage7";
              stageLabel = if useAbc9 then
                "stage7 synth_xilinx -abc9 map_ffs:map_ffs"
              else
                "stage7 synth_xilinx map_ffs:map_ffs";
              inputIl = if splitFineStage then stage6b else stage6Monolithic;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad ${
                  pkgs.lib.optionalString useAbc9 "-abc9 "
                }-run map_ffs:map_ffs"
              ];
            };
            stage8a = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8a";
              stageLabel = "stage8a opt_expr -mux_undef -noclkinv";
              inputIl = stage7;
              commands = [ "opt_expr -mux_undef -noclkinv" ];
            };
            stage8b = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8b";
              stageLabel = "stage8b abc -luts 2:2,3,6:5,10,20";
              inputIl = stage8a;
              commands = [ "abc -luts 2:2,3,6:5,10,20" ];
            };
            stage8c = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8c";
              stageLabel = "stage8c clean";
              inputIl = stage8b;
              commands = [ "clean" ];
            };
            stage8d = mkTask3SynthStageTargetedTechmapIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8d";
              stageLabel = "stage8d targeted techmap ff_map";
              inputIl = stage8c;
              cellRegex = "^\\$_(DFF|DFFE|DFFSRE|SDFF|SDFFE|DLATCH)_";
              techmapArgs = "-map +/xilinx/ff_map.v";
            };
            stage8e = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8e";
              stageLabel = "stage8e xilinx_srl -fixed -minlen 3";
              inputIl = stage8d;
              commands = [ "xilinx_srl -fixed -minlen 3" ];
            };
            stage8f = mkTask3SynthStageTargetedTechmapIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8f";
              stageLabel = "stage8f targeted techmap lut_map";
              inputIl = stage8e;
              cellRegex = "^\\$(lut|__XILINX_SHIFTX)$";
              techmapArgs =
                "-map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6";
            };
            stage8g = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8g";
              stageLabel = "stage8g xilinx_dffopt";
              inputIl = stage8f;
              commands = [ "xilinx_dffopt" ];
            };
            stage8h = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8h";
              stageLabel = "stage8h opt_lut_ins -tech xilinx";
              inputIl = stage8g;
              commands = [ "opt_lut_ins -tech xilinx" ];
            };
            stage8Monolithic = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8";
              stageLabel = if useAbc9 then
                "stage8 final synth/write -abc9"
              else
                "stage8 final synth/write";
              inputIl = stage7;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad ${
                  pkgs.lib.optionalString useAbc9 "-abc9 "
                }-run map_luts:check"
              ];
            };
            stage8Abc9 = mkTask3SynthStageIl {
              inherit name topName quiet memoryLimitKb;
              stageId = "stage8";
              stageLabel = "stage8 synth_xilinx -abc9 map_luts:check";
              inputIl = stage7;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -abc9 -run map_luts:check"
              ];
            };
            stage8 = if splitFineStage then
              (if useAbc9 then stage8Abc9 else stage8h)
            else
              stage8Monolithic;
            stage9 = mkTask3SynthStageJson {
              inherit name quiet memoryLimitKb;
              stageId = "stage9";
              stageLabel = "stage9 write_json";
              inputIl = stage8;
            };
            json = stage9;
          };
        mkTask3RtlilStageStatReport = { name, stageId, inputIl, topName }:
          pkgs.runCommand "${name}-${stageId}-stats" { } ''
            cat > run.ys <<EOF
            read_rtlil ${inputIl}
            hierarchy -top ${topName} -check
            tee -o raw-stat.json stat -json
            EOF

            ${yosysPkg}/bin/yosys -q -s run.ys >/dev/null

            mkdir -p "$out"
            ${python}/bin/python3 ${pipelineScripts}/write_rtlil_stage_stat_report.py \
              --input-il ${inputIl} \
              --raw-yosys-json raw-stat.json \
              --summary-json "$out/summary.json" \
              --summary-txt "$out/summary.txt" \
              --stat-json "$out/stat.json" \
              --top ${topName} \
              --stage-id ${stageId}
          '';
        mkTask3RtlilStageStats =
          { name, stages, topName, splitFineStage ? false, useAbc9 ? false }:
          let
            stageOrder = if splitFineStage then
              if useAbc9 then [
                "stage1"
                "stage2"
                "stage3"
                "stage4"
                "stage5a"
                "stage5b"
                "stage5c"
                "stage5d"
                "stage6a"
                "stage6b"
                "stage7"
                "stage8"
              ] else [
                "stage1"
                "stage2"
                "stage3"
                "stage4"
                "stage5a"
                "stage5b"
                "stage5c"
                "stage5d"
                "stage6a"
                "stage6b"
                "stage7"
                "stage8a"
                "stage8b"
                "stage8c"
                "stage8d"
                "stage8e"
                "stage8f"
                "stage8g"
                "stage8h"
              ]
            else [
              "stage1"
              "stage2"
              "stage3"
              "stage4"
              "stage5"
              "stage6"
              "stage7"
              "stage8"
            ];
            reports = builtins.listToAttrs (map (stageId: {
              name = stageId;
              value = mkTask3RtlilStageStatReport {
                inherit name stageId topName;
                inputIl = builtins.getAttr stageId stages;
              };
            }) stageOrder);
            index = pkgs.writeText "${name}-stage-stats-index.json"
              (builtins.toJSON {
                inherit name stageOrder;
                top = topName;
              });
            bundle = pkgs.runCommand "${name}-stage-stats" { } ''
              mkdir -p "$out"
              cp ${index} "$out/index.json"
              ${builtins.concatStringsSep "\n" (map (stageId: ''
                mkdir -p "$out/${stageId}"
                cp ${builtins.getAttr stageId reports}/summary.json "$out/${stageId}/summary.json"
                cp ${builtins.getAttr stageId reports}/summary.txt "$out/${stageId}/summary.txt"
                cp ${builtins.getAttr stageId reports}/stat.json "$out/${stageId}/stat.json"
              '') stageOrder)}
            '';
          in {
            inherit stageOrder reports bundle;
          };
        mkTask3ExternalizedMemoryPlan =
          { name, modelIl, minModuleBits ? 1, maxModules ? null }:
          pkgs.runCommand "${name}-external-memory-plan" { } ''
            ${python}/bin/python3 ${pipelineScripts}/externalize_large_memories.py \
              --input ${modelIl} \
              --output-script externalize.ys \
              --output-report report.json \
              --min-module-bits ${toString minModuleBits} ${
                pkgs.lib.optionalString (maxModules != null)
                "--max-modules ${toString maxModules}"
              }
            mkdir -p "$out"
            cp externalize.ys "$out/externalize.ys"
            cp report.json "$out/report.json"
          '';
        mkTask3TrimRtlil = { name, inputIl }:
          pkgs.runCommand "${name}.il" { } ''
            ${python}/bin/python3 ${pipelineScripts}/filter_rtlil_modules.py \
              --input ${inputIl} \
              --output "$out" \
              --drop-attributes
          '';
        mkTask3MappedJsonUtilizationReport =
          { name, capacities, topName, designJson }:
          pkgs.runCommand "${name}-utilization" { } ''
            mkdir -p "$out"
            ${python}/bin/python3 ${pipelineScripts}/write_utilization_report.py \
              --design-json ${designJson} \
              --top ${topName} \
              --summary-json "$out/summary.json" \
              --summary-txt "$out/summary.txt" \
              --stat-json "$out/stat.json" \
              --capacity-slices ${toString capacities.slices} \
              --capacity-clb-luts ${toString capacities.clb_luts} \
              --capacity-clb-ffs ${toString capacities.clb_ffs} \
              --capacity-dsp ${toString capacities.dsp} \
              --capacity-bram36 ${toString capacities.bram36} \
              --capacity-bram-kb ${toString capacities.bram_kb}
          '';
        mkTask3SelftestBundle = { name, modelLabel, topName, mainSv, modelIl
          , capacities, externalMemoryMinModuleBits ? (128 * 1024)
          , externalMemoryMaxModules ? null, useAbc9 ? false
          , modelPreBlackboxedMemory ? false, fpPrimitivesDescription ? null
          , memoryPrimitivesDescription ? null
          , externalizeBeforeModelOpt ? false }:
          let
            top = pkgs.runCommand "${name}-top.sv" { } ''
              ${python}/bin/python3 ${pipelineScripts}/gen_tiny_stories_selftest_top.py \
                --main-sv ${mainSv} \
                --out "$out"
            '';
            modelTrimIl = mkTask3TrimRtlil {
              name = "${name}-model-trim";
              inputIl = modelIl;
            };
            modelOptIl = if modelPreBlackboxedMemory then
              modelTrimIl
            else if externalizeBeforeModelOpt then
              modelTrimIl
            else
              mkTask3YosysRtlil {
                name = "${name}-model-opt";
                script = ''
                  read_rtlil ${modelTrimIl}
                  hierarchy -top main -check
                  proc
                  opt_expr
                  opt_clean
                  clean
                  write_rtlil $out
                '';
                quiet = true;
              };
            externalMemoryPlan = mkTask3ExternalizedMemoryPlan {
              inherit name;
              modelIl = if externalizeBeforeModelOpt then modelTrimIl else modelOptIl;
              minModuleBits = externalMemoryMinModuleBits;
            };
            modelShellIl = mkTask3YosysRtlil {
              name = "${name}-model-shell";
              script = if externalizeBeforeModelOpt then ''
                read_rtlil ${modelTrimIl}
                script ${externalMemoryPlan}/externalize.ys
                hierarchy -top main -check
                proc
                opt_expr
                opt_clean
                clean
                write_rtlil $out
              '' else ''
                read_rtlil ${modelOptIl}
                script ${externalMemoryPlan}/externalize.ys
                hierarchy -top main -check
                write_rtlil $out
              '';
              quiet = true;
            };
            stages = mkTask3SynthJsonStages {
              inherit name topName;
              topSv = top;
              modelIl = modelShellIl;
              quiet = true;
              splitFineStage = externalMemoryMaxModules != null;
              inherit useAbc9;
            };
            inherit (stages) json;
            yosysJson = mkTask3YosysJson {
              name = "${name}-yosys";
              inherit topName;
              modelIl = modelShellIl;
              topSv = top;
            };
            utilization = mkTask3MappedJsonUtilizationReport {
              inherit name capacities topName;
              designJson = json;
            };
            rtlilStageStats = mkTask3RtlilStageStats {
              inherit name stages topName;
              splitFineStage = externalMemoryMaxModules != null;
              inherit useAbc9;
            };
            stage9Debug = mkTask3SynthStage9Debug {
              inherit name;
              inputIl = stages.stage8;
            };
            utilizationBundle =
              pkgs.runCommand "${name}-utilization-bundle" { } ''
                mkdir -p "$out"
                cp ${utilization}/summary.json "$out/summary.json"
                cp ${utilization}/summary.txt "$out/summary.txt"
                cp ${utilization}/stat.json "$out/stat.json"
                cp ${externalMemoryPlan}/report.json "$out/external-memory-plan.json"
                cp ${top} "$out/tiny_stories_selftest_top.sv"
                cat > "$out/manifest.json" <<'JSON'
                ${builtins.toJSON {
                  package = name;
                  route = "task3-baseline-float-selftest-all-memory";
                  model = modelLabel;
                  source_pipeline =
                    "PyTorch ExportedProgram -> torch-mlir -> linalg -> cf -> handshake -> hw -> sv";
                  fp_primitives = fpPrimitivesDescription;
                  memory_primitives = memoryPrimitivesDescription;
                  selftest_top = topName;
                  external_memory_min_module_bits =
                    externalMemoryMinModuleBits;
                  final_reports = [ "summary.json" "summary.txt" "stat.json" ];
                }}
                JSON
              '';
          in {
            inherit top modelTrimIl modelOptIl modelShellIl externalMemoryPlan
              stages json yosysJson utilization rtlilStageStats stage9Debug
              utilizationBundle;
          };
        mkTask3BaselineFloatSv = { name, svMlir }:
          pkgs.runCommand "${name}-sv" { } ''
            export ALLOW_HW_EXTERNS=1
            export FP_PRIMS_SV=${task3FpPrimitiveBlackboxes}
            ${pkgs.bash}/bin/bash ${pipelineScripts}/sv_mlir_to_sv.sh \
              ${circt}/bin/circt-opt \
              ${svMlir} \
              "$out"
          '';
        mkTask3BaselineFloatIl = { name, sv }:
          pkgs.runCommand "${name}.il" { } ''
            ${pkgs.gawk}/bin/awk '
              /^module handshake_memory_/ {
                name = $2
                sub(/\(.*/, "", name)
                print "--blackboxed-module " name
              }
            ' ${sv}/sv/main.sv > memory-blackboxes.args

            blackboxArgs="$(${pkgs.coreutils}/bin/tr '\n' ' ' < memory-blackboxes.args)"
            cat > run.ys <<EOF
            plugin -i ${yosysSlang}/share/yosys/plugins/slang.so
            read_slang --threads 1 --no-proc --max-parse-depth 20000 --top main $blackboxArgs ${sv}/sv/main.sv ${sv}/sv/zz_circt_fp_primitives.sv
            hierarchy -check -top main
            stat
            write_rtlil $out
            EOF

            ${yosysPkg}/bin/yosys -s run.ys
          '';
        task3TinyStories1mBaselineFloatSelftestAllMemory =
          mkTask3SelftestBundle {
            name = "tiny-stories-1m-baseline-float-selftest-all-memory";
            modelLabel = "tiny-stories-1m-baseline-float";
            topName = "tiny_stories_selftest_top";
            mainSv =
              "${pipelineStagePackages."tiny-stories-1m-baseline-float-sv"}/sv/main.sv";
            modelIl =
              pipelineStagePackages."tiny-stories-1m-baseline-float-il";
            capacities = task3TinyStoriesCapacities;
            externalMemoryMinModuleBits = 1;
          };
        task3TinyStories1mBaselineFloatLiveUtilization =
          task3TinyStories1mBaselineFloatSelftestAllMemory.utilizationBundle;
        task3TinyStories1mBaselineFloatSavedUtilization = pkgs.runCommand
          "tiny-stories-1m-baseline-float-selftest-all-memory-saved-utilization"
          { } ''
            mkdir -p "$out"
            cp ${task3BaselineFloatReference}/summary.json "$out/summary.json"
            cp ${task3BaselineFloatReference}/summary.txt "$out/summary.txt"
            cp ${task3BaselineFloatReference}/stat.json "$out/stat.json"
            cat > "$out/manifest.json" <<'JSON'
            ${builtins.toJSON {
              package =
                "tiny-stories-1m-baseline-float-selftest-all-memory-saved-utilization";
              route = "task3-baseline-float-selftest-all-memory";
              model = "tiny-stories-1m-baseline-float";
              source = "copied final report artifact from ~/LLM2FPGA";
              final_reports = [ "summary.json" "summary.txt" "stat.json" ];
            }}
            JSON
          '';
        task3TinyStories1mBaselineFloatLiveStatus = pkgs.runCommand
          "tiny-stories-1m-baseline-float-selftest-all-memory-live-status"
          { } ''
            mkdir -p "$out"
            cat > "$out/summary.json" <<'JSON'
            ${builtins.toJSON {
              status = "pipeline-failed";
              route = "task3-baseline-float-selftest-all-memory";
              model = "tiny-stories-1m-baseline-float";
              failure = {
                stage = "sv-to-rtlil";
                reason =
                  "live full TinyStories rebuild reaches SystemVerilog, then Yosys/Slang is killed while importing main before RTLIL exists";
                observed_exit_code = 137;
              };
              attempted_flow =
                "PyTorch ExportedProgram -> torch-mlir -> linalg -> cf -> handshake -> hw -> sv -> rtlil -> Task 3 selftest/all-memory utilization";
              live_derivation =
                "tiny-stories-1m-baseline-float-selftest-all-memory-live-utilization";
              resources = { };
              usage = { };
              utilization = { };
            }}
            JSON
            cat > "$out/summary.txt" <<'TXT'
            status: pipeline-failed
            route: task3-baseline-float-selftest-all-memory
            model: tiny-stories-1m-baseline-float
            failure_stage: sv-to-rtlil
            failure: live full TinyStories reaches SV, then Yosys/Slang is killed while importing main before RTLIL exists
            observed_exit_code: 137
            TXT
            cat > "$out/stat.json" <<'JSON'
            ${builtins.toJSON {
              status = "pipeline-failed";
              top = "tiny_stories_selftest_top";
              resources = { };
            }}
            JSON
            cat > "$out/manifest.json" <<'JSON'
            ${builtins.toJSON {
              package =
                "tiny-stories-1m-baseline-float-selftest-all-memory-live-status";
              route = "task3-baseline-float-selftest-all-memory";
              model = "tiny-stories-1m-baseline-float";
              final_reports = [ "summary.json" "summary.txt" "stat.json" ];
              live_derivation =
                "tiny-stories-1m-baseline-float-selftest-all-memory-live-utilization";
            }}
            JSON
          '';
        task3TinyStories1mBaselineFloatSavedVsLive = pkgs.runCommand
          "tiny-stories-1m-baseline-float-selftest-all-memory-saved-vs-live"
          { } ''
            mkdir -p "$out"
            cp ${task3TinyStories1mBaselineFloatSavedUtilization}/summary.json "$out/saved-summary.json"
            cp ${task3TinyStories1mBaselineFloatLiveStatus}/summary.json "$out/live-summary.json"
            OUT="$out" ${python}/bin/python3 - <<'PY'
            import json
            import os
            from pathlib import Path

            out = Path(os.environ["OUT"])
            saved = json.loads((out / "saved-summary.json").read_text())
            live = json.loads((out / "live-summary.json").read_text())
            usage = saved.get("usage", {})
            payload = {
                "status": "not-reproduced",
                "saved_status": saved.get("status", "final-report"),
                "live_status": live.get("status"),
                "saved_usage": usage,
                "live_failure": live.get("failure", {}),
                "conclusion": (
                    "The saved FTS final report has utilization numbers, but "
                    "the live FTS derivation does not reproduce them on this "
                    "host/toolchain because it fails before RTLIL."
                ),
            }
            (out / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            lines = [
                "# Saved vs Live FTS Task 3",
                "",
                f"- status: `{payload['status']}`",
                "- saved artifact: final utilization report is present",
                f"- live derivation status: `{payload['live_status']}`",
                f"- live failure stage: `{payload['live_failure'].get('stage', 'unknown')}`",
                f"- live failure exit code: `{payload['live_failure'].get('observed_exit_code', 'unknown')}`",
                "",
                "| metric | saved FTS | live FTS |",
                "| --- | ---: | ---: |",
                f"| lut_total | {usage.get('lut_total', 'unknown')} | unknown |",
                f"| ff_total | {usage.get('ff_total', 'unknown')} | unknown |",
                "",
                payload["conclusion"],
                "",
            ]
            (out / "summary.md").write_text("\n".join(lines))
            (out / "summary.txt").write_text("\n".join(lines))
            PY
          '';
        task3RepresentativeCoreSelftestAllMemory = mkTask3SelftestBundle {
          name =
            "tinystories-representative-core-task3-baseline-float-selftest-all-memory";
          modelLabel = "tinystories-representative-core-fp32";
          topName = "tiny_stories_selftest_top";
          mainSv =
            "${pipelineStagePackages."tinystories-representative-core-fp32-sv"}/sv/main.sv";
          modelIl = pipelineStagePackages."tinystories-representative-core-fp32-il";
          capacities = task3TinyStoriesCapacities;
          externalMemoryMinModuleBits = 1;
          fpPrimitivesDescription =
            "full pipeline FP primitive SystemVerilog support";
          memoryPrimitivesDescription =
            "Task 3 external-memory shelling from RTLIL, min module bits 1";
          externalizeBeforeModelOpt = true;
        };
        task3RepresentativeCoreLiveUtilization =
          task3RepresentativeCoreSelftestAllMemory.utilizationBundle;
        task3RepresentativeCoreUtilization = pkgs.runCommand
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-utilization-bundle"
          { } ''
            mkdir -p "$out"
            cat > "$out/summary.json" <<'JSON'
            ${builtins.toJSON {
              status = "pipeline-failed";
              route = "task3-baseline-float-selftest-all-memory";
              model = "tinystories-representative-core-fp32";
              failure = {
                stage = "yosys model-shell";
                reason =
                  "representative-core normal RTLIL import succeeds, but Task 3 selftest/all-memory model-shell creation is killed while reading trimmed RTLIL, applying external-memory shelling, and running proc/opt/clean";
                observed_exit_code = 137;
              };
              capacities = task3TinyStoriesCapacities;
              resources = { };
              usage = { };
              utilization = { };
              attempted_flow = {
                baseline = "copied final FTS report artifact";
                candidate =
                  "normal representative-core pipeline RTLIL -> attribute-trimmed RTLIL -> externalize handshake memories before proc/opt -> old Task 3 staged synthesis";
                live_derivation =
                  "tinystories-representative-core-task3-baseline-float-selftest-all-memory-live-utilization";
              };
            }}
            JSON
            cat > "$out/summary.txt" <<'TXT'
            status: pipeline-failed
            route: task3-baseline-float-selftest-all-memory
            model: tinystories-representative-core-fp32
            failure_stage: yosys model-shell
            failure: normal representative-core RTLIL builds, but model-shell creation is killed during external-memory shelling plus proc/opt/clean
            observed_exit_code: 137
            TXT
            cat > "$out/stat.json" <<'JSON'
            ${builtins.toJSON {
              status = "pipeline-failed";
              top = "tiny_stories_selftest_top";
              resources = { };
            }}
            JSON
            cat > "$out/manifest.json" <<'JSON'
            ${builtins.toJSON {
              package =
                "tinystories-representative-core-task3-baseline-float-selftest-all-memory";
              route = "task3-baseline-float-selftest-all-memory";
              model = "tinystories-representative-core-fp32";
              source_pipeline =
                "PyTorch ExportedProgram -> torch-mlir -> linalg -> cf -> handshake -> hw -> sv -> rtlil";
              final_reports = [ "summary.json" "summary.txt" "stat.json" ];
              result = "pipeline failed before final utilization";
              live_derivation =
                "tinystories-representative-core-task3-baseline-float-selftest-all-memory-live-utilization";
            }}
            JSON
          '';
        task3RepresentativeCoreParity = pkgs.runCommand
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-parity"
          { } ''
            mkdir -p "$out"
            ${python}/bin/python3 ${pipelineScripts}/compare_task3_representative_core_parity.py \
              --baseline-dir ${task3BaselineFloatReference} \
              --candidate-dir ${task3RepresentativeCoreUtilization} \
              --shape-json ${task3RepresentativeCoreShapeMetadata} \
              --baseline-label tiny-stories-1m-baseline-float-selftest-all-memory-utilization \
              --candidate-label tinystories-representative-core-task3-baseline-float-selftest-all-memory-utilization \
              --summary-json "$out/parity-summary.json" \
              --summary-md "$out/parity-summary.md"
            cp ${task3BaselineFloatReference}/summary.json "$out/baseline-summary.json"
            cp ${task3RepresentativeCoreUtilization}/summary.json "$out/representative-core-summary.json"
          '';
      in {
        packages = {
          inherit circt mlir torchMlir yosysPkg modelRegistryJson
            llm2fpgaMlirPasses llm2fpgaTorchMlirPasses llm2fpgaCirctPasses
            calyx;
          "active-pipeline-variants" = activePipelineVariantsJson;
          "tinystories-w8a8-pt2e-graph-shape-audit" =
            tinystoriesW8A8Pt2eGraphShapeAudit;
          "resource-baseline-yosys-stat-matrix" =
            resourceBaselineYosysStatMatrix;
          "tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-sv-equivalence" =
            tinystoriesIntegerSvEquivalenceReport;
          "tiny-stories-1m-baseline-float-selftest-all-memory-utilization" =
            task3MainPackages."tiny-stories-1m-baseline-float-selftest-all-memory-utilization";
          "tiny-stories-1m-baseline-float-selftest-all-memory-live-utilization" =
            task3TinyStories1mBaselineFloatLiveUtilization;
          "tiny-stories-1m-baseline-float-selftest-all-memory-live-status" =
            task3TinyStories1mBaselineFloatLiveStatus;
          "tiny-stories-1m-baseline-float-selftest-all-memory-saved-utilization" =
            task3TinyStories1mBaselineFloatSavedUtilization;
          "tiny-stories-1m-baseline-float-selftest-all-memory-saved-vs-live" =
            task3TinyStories1mBaselineFloatSavedVsLive;
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-utilization" =
            task3MainPackages."tinystories-representative-core-task3-baseline-float-selftest-all-memory-utilization";
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-live-utilization" =
            task3RepresentativeCoreLiveUtilization;
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-parity" =
            task3MainPackages."tinystories-representative-core-task3-baseline-float-selftest-all-memory-parity";
          model-registry = modelRegistryJson;
          default = modelRegistryJson;
        } // pipelineStagePackages // pipelineMetadataPackages
          // quantizedLinalgDiagnosticPackages // pipelineAliasPackages;

        checks.default = modelRegistryJson;

        devShells.default = pkgs.mkShell {
          packages = [
            circt
            mlir
            torchMlir
            yosysPkg
            yosysSlang
            pythonWithTinyStories
            pkgs.verilator
          ];
        };

        formatter = pkgs.nixfmt-classic;
      });
}
