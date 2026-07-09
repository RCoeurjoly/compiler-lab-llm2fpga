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
  };

  outputs = inputs@{ nixpkgs, nixpkgs-llvm21, nixpkgs-nix-eda, flake-utils
    , circt-nix, nix-eda, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pkgsLlvm21 = import nixpkgs-llvm21 {
          inherit system;
          config.allowUnfreePredicate = pkg:
            builtins.elem (nixpkgs.lib.getName pkg) [ "torch" ];
        };

        circtPkgs = circt-nix.packages.${system};
        circt = circtPkgs.circt.override { enableSlang = false; };
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
          mlirPasses = llm2fpgaMlirPasses;
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
            cat > run.ys <<'EOF'
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
        mkTask3SynthStageIl = { name, stageId, stageLabel, inputIl, topName
          , topSv ? null, commands, preCommands ? [ ], quiet ? false }:
          pkgs.runCommand "${name}-${stageId}.il" { } ''
            cat > run.ys <<'EOF'
            ${builtins.concatStringsSep "\n" ([ "read_rtlil ${inputIl}" ]
              ++ pkgs.lib.optional (topSv != null) "read_slang ${topSv}"
              ++ [ "hierarchy -top ${topName} -check" ] ++ preCommands
              ++ commands ++ [ "write_rtlil $out" ])}
            EOF

            echo "[task3-synth:${name}] ${stageLabel}" >&2
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
          { name, stageId, stageLabel, inputIl, topName, quiet ? false }:
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

            echo "[task3-synth:${name}] ${stageLabel}" >&2
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
        mkTask3SynthStageJson =
          { name, stageId, stageLabel, inputIl, quiet ? false }:
          pkgs.runCommand "${name}.json" { } ''
            ${python}/bin/python3 ${pipelineScripts}/filter_rtlil_modules.py \
              --input ${inputIl} \
              --output stage8-stripped.il \
              --drop-escaped-uppercase-modules

            cat > run.ys <<'EOF'
            read_rtlil stage8-stripped.il
            proc
            write_json $out
            EOF

            echo "[task3-synth:${name}] ${stageLabel}" >&2
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
        mkTask3SynthJsonStages = { name, modelIl, topName, topSv }:
          let
            stage1 = mkTask3SynthStageIl {
              inherit name topName topSv;
              stageId = "stage1";
              stageLabel = "stage1 synth_xilinx begin:prepare";
              inputIl = modelIl;
              preCommands = [ "proc" ];
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run begin:prepare"
              ];
              quiet = true;
            };
            stage2 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage2";
              stageLabel = "stage2 synth_xilinx coarse:map_memory";
              inputIl = stage1;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run coarse:map_memory"
              ];
              quiet = true;
            };
            stage3 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage3";
              stageLabel = "stage3 opt -fast -full";
              inputIl = stage2;
              commands = [ "opt -fast -full" ];
              quiet = true;
            };
            stage4 = mkTask3SynthStageMemoryMapIl {
              inherit name topName;
              stageId = "stage4";
              stageLabel = "stage4 targeted memory_map";
              inputIl = stage3;
              quiet = true;
            };
            stage5 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage5";
              stageLabel = "stage5 synth_xilinx fine:fine";
              inputIl = stage4;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run fine:fine"
              ];
              quiet = true;
            };
            stage6 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage6";
              stageLabel = "stage6 synth_xilinx map_cells:map_cells";
              inputIl = stage5;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run map_cells:map_cells"
              ];
              quiet = true;
            };
            stage7 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage7";
              stageLabel = "stage7 synth_xilinx map_ffs:map_ffs";
              inputIl = stage6;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run map_ffs:map_ffs"
              ];
              quiet = true;
            };
            stage8 = mkTask3SynthStageIl {
              inherit name topName;
              stageId = "stage8";
              stageLabel = "stage8 final synth/write";
              inputIl = stage7;
              commands = [
                "synth_xilinx -family xc7 -top ${topName} -noiopad -run map_luts:check"
              ];
              quiet = true;
            };
            json = mkTask3SynthStageJson {
              inherit name;
              stageId = "stage9";
              stageLabel = "stage9 write_json";
              inputIl = stage8;
              quiet = true;
            };
          in {
            inherit stage1 stage2 stage3 stage4 stage5 stage6 stage7 stage8
              json;
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
        mkTask3SelftestAllMemoryUtilization =
          { name, mainSv, modelIl, capacities }:
          let
            topName = "tiny_stories_selftest_top";
            top = pkgs.runCommand "${name}-top.sv" { } ''
              ${python}/bin/python3 ${pipelineScripts}/gen_tiny_stories_selftest_top.py \
                --main-sv ${mainSv} \
                --out "$out"
            '';
            modelOptIl = mkTask3YosysRtlil {
              name = "${name}-model-opt";
              script = ''
                read_rtlil ${modelIl}
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
              modelIl = modelOptIl;
              minModuleBits = 1;
            };
            modelShellIl = mkTask3YosysRtlil {
              name = "${name}-model-shell";
              script = ''
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
            };
            utilization = mkTask3MappedJsonUtilizationReport {
              inherit name capacities topName;
              designJson = stages.json;
            };
          in pkgs.runCommand "${name}-utilization-bundle" { } ''
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
              model = "tinystories-representative-core-fp32";
              source_pipeline =
                "PyTorch ExportedProgram -> torch-mlir -> linalg -> cf -> handshake -> hw -> sv";
              selftest_top = "tiny_stories_selftest_top";
              external_memory_min_module_bits = 1;
              final_reports = [ "summary.json" "summary.txt" "stat.json" ];
            }}
            JSON
          '';
        task3RepresentativeCoreUtilization =
          mkTask3SelftestAllMemoryUtilization {
            name =
              "tinystories-representative-core-task3-baseline-float-selftest-all-memory";
            mainSv = "${
                pipelineStagePackages."tinystories-representative-core-fp32-sv"
              }/sv/main.sv";
            modelIl =
              pipelineStagePackages."tinystories-representative-core-fp32-il";
            capacities = task3TinyStoriesCapacities;
          };
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
            llm2fpgaMlirPasses llm2fpgaCirctPasses calyx;
          "active-pipeline-variants" = activePipelineVariantsJson;
          "resource-baseline-yosys-stat-matrix" =
            resourceBaselineYosysStatMatrix;
          "tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-sv-equivalence" =
            tinystoriesIntegerSvEquivalenceReport;
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-utilization" =
            task3RepresentativeCoreUtilization;
          "tinystories-representative-core-task3-baseline-float-selftest-all-memory-parity" =
            task3RepresentativeCoreParity;
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
