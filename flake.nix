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
            noHandshakeLinalgToLlvm;
          mlirPasses = llm2fpgaMlirPasses;
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
            noHandshakeLinalgToLlvm;
          mlirPasses = llm2fpgaMlirPasses;
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
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias = "pattern-embedding-w4a8-core-via-tosa-no-handshake";
            model = "pattern-embedding-w4a8-core";
            frontend = "tosa";
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias = "pattern-layernorm-w4a8-core-via-tosa-no-handshake";
            model = "pattern-layernorm-w4a8-core";
            frontend = "tosa";
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8";
            frontend = "tosa";
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8";
            frontend = "linalg";
            backend = "calyx-sv";
            packages = pipelineStagePackagesNoHandshake;
            stages = noHandshakeLinalgStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-fixed-layernorm-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8-fixed-layernorm";
            frontend = "tosa";
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-fixed-layernorm-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8-fixed-layernorm";
            frontend = "linalg";
            backend = "calyx-sv";
            packages = pipelineStagePackagesNoHandshake;
            stages = noHandshakeLinalgStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-integer-via-tosa-no-handshake";
            model = "tinystories-representative-core-w4a8-integer";
            frontend = "tosa";
            backend = "calyx-sv";
            packages = pipelineStagePackagesTosaNoHandshake;
            stages = noHandshakeStages;
          }
          {
            alias =
              "tinystories-representative-core-w4a8-integer-via-linalg-no-handshake";
            model = "tinystories-representative-core-w4a8-integer";
            frontend = "linalg";
            backend = "calyx-sv";
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
              --entry alias=pattern-linear-w4a8-core-via-tosa-no-handshake,model=pattern-linear-w4a8-core,frontend=tosa,backend=calyx-sv,stat=${
                pipelineAliasPackages."pattern-linear-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=pattern-embedding-w4a8-core-via-tosa-no-handshake,model=pattern-embedding-w4a8-core,frontend=tosa,backend=calyx-sv,stat=${
                pipelineAliasPackages."pattern-embedding-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=pattern-layernorm-w4a8-core-via-tosa-no-handshake,model=pattern-layernorm-w4a8-core,frontend=tosa,backend=calyx-sv,stat=${
                pipelineAliasPackages."pattern-layernorm-w4a8-core-via-tosa-no-handshake-yosys-stat"
              } \
              --entry alias=tinystories-representative-core-w4a8-integer-via-linalg-no-handshake,model=tinystories-representative-core-w4a8-integer,frontend=linalg,backend=calyx-sv,stat=${
                pipelineAliasPackages."tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat"
              } \
              --entry alias=tinystories-representative-core-w4a8-integer-via-tosa-no-handshake,model=tinystories-representative-core-w4a8-integer,frontend=tosa,backend=calyx-sv,stat=${
                pipelineAliasPackages."tinystories-representative-core-w4a8-integer-via-tosa-no-handshake-yosys-stat"
              } \
              --summary-json "$out/summary.json" \
              --summary-md "$out/summary.md"
          '';
      in {
        packages = {
          inherit circt mlir torchMlir yosysPkg modelRegistryJson
            llm2fpgaMlirPasses llm2fpgaCirctPasses calyx;
          "active-pipeline-variants" = activePipelineVariantsJson;
          "resource-baseline-yosys-stat-matrix" =
            resourceBaselineYosysStatMatrix;
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
