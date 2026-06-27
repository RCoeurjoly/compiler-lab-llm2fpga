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
        circt =
          (circtPkgs.circt.override { enableSlang = false; }).overrideAttrs
          (old: {
            patches = (old.patches or [ ]) ++ [
              ./patches/circt-upstream-task3-recovery/0001-flatten-memref-shape-ops-after-memref-flattening.patch
              ./patches/circt-upstream-task3-recovery/0002-handle-cfg-threaded-memrefs-in-handshake-lowering.patch
              ./patches/circt-upstream-task3-recovery/0005-handle-dense-resource-globals-in-flattenmemrefs.patch
              ./patches/circt-upstream-task3-recovery/0011-rebased-handshaketohw-stack.patch
              ./patches/circt-upstream-task3-recovery/0012-update-buffer-lowering-test-for-constant-order.patch
            ];
          });

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
        torchMlirPatched = pkgsLlvm21.callPackage ./torch-mlir.nix {
          inherit python;
          nanobind = nanobindBootstrap;
          inherit (torchMlirLlvmPackages) tblgen;
          mlir = mlirForTorchMlir;
          inherit (torchMlirLlvmPackages) llvm;
          applyTask3RfpPatches = true;
        };
        torchMlirUnpatched = pkgsLlvm21.callPackage ./torch-mlir.nix {
          inherit python;
          nanobind = nanobindBootstrap;
          inherit (torchMlirLlvmPackages) tblgen;
          mlir = mlirForTorchMlir;
          inherit (torchMlirLlvmPackages) llvm;
          applyTask3RfpPatches = false;
        };
        torchMlir = torchMlirUnpatched;

        pipelineScripts = ./scripts/pipeline;
        svProvenanceReport = ./scripts/diagnostics/sv_provenance_report.py;
        noHandshakeLinalgToScf =
          ./scripts/diagnostics/linalg_to_scf_no_handshake.sh;
        noHandshakeScfToFlatScf =
          ./scripts/diagnostics/scf_to_flat_scf_no_handshake.sh;
        noHandshakeScfToCalyx =
          ./scripts/diagnostics/scf_to_calyx_no_handshake.sh;
        calyxToSvNoHandshake =
          ./scripts/diagnostics/calyx_to_sv_no_handshake.sh;
        noHandshakeLinalgToLlvm =
          ./scripts/diagnostics/linalg_to_llvm_no_handshake.sh;
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
          inherit pipelineScripts svProvenanceReport noHandshakeLinalgToScf
            noHandshakeScfToFlatScf noHandshakeScfToCalyx
            noHandshakeLinalgToLlvm;
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
        pipelineLibPatched = import ./nix/pipeline.nix {
          inherit pkgs mlir circt yosysPkg yosysSlang python;
          torchMlir = torchMlirPatched;
          inherit pipelineScripts svProvenanceReport noHandshakeLinalgToScf
            noHandshakeScfToFlatScf noHandshakeScfToCalyx
            noHandshakeLinalgToLlvm;
          inherit flatScfBlockerReport;
          compilePyTorch = ./scripts/compile-pytorch.py;
        };
        modelRegistryPatched = import ./nix/models.nix {
          inherit (pipelineLibPatched) registerModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO
            tinyStories1m fpPrimsSv;
          torchMlir = torchMlirPatched;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesPatched =
          pipelineLibPatched.pipelineStagePackagesFromRegistry
          modelRegistryPatched;
        patchedLinearW4A8PipelinePackages = {
          "pattern-linear-w4a8-torch-patched" =
            pipelineStagePackagesPatched."pattern-linear-w4a8-torch";
          "pattern-linear-w4a8-linalg-patched" =
            pipelineStagePackagesPatched."pattern-linear-w4a8-linalg";
          "pattern-linear-w4a8-sv-patched" =
            pipelineStagePackagesPatched."pattern-linear-w4a8-sv";
          "pattern-linear-w4a8-yosys-stat-patched" =
            pipelineStagePackagesPatched."pattern-linear-w4a8-yosys-stat";
        };
        pipelineLibTosaPatched = import ./nix/pipeline.nix {
          inherit pkgs mlir circt yosysPkg yosysSlang python;
          tosaToLinalgMlir = mlirForTorchMlir;
          torchMlir = torchMlirPatched;
          inherit pipelineScripts svProvenanceReport noHandshakeLinalgToScf
            noHandshakeScfToFlatScf noHandshakeScfToCalyx
            noHandshakeLinalgToLlvm;
          inherit flatScfBlockerReport;
          compilePyTorch = ./scripts/compile-pytorch.py;
        };
        modelRegistryTosaPatched = import ./nix/models.nix {
          registerModel = pipelineLibTosaPatched.registerTosaModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO
            tinyStories1m fpPrimsSv;
          torchMlir = torchMlirPatched;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesTosaPatched =
          pipelineLibTosaPatched.pipelineStagePackagesFromRegistry
          modelRegistryTosaPatched;
        modelRegistryTosaNoHandshakePatched = import ./nix/models.nix {
          registerModel = pipelineLibTosaPatched.registerTosaNoHandshakeModel;
          inherit pythonWithTinyStories pythonWithTinyStoriesTorchAO
            tinyStories1m fpPrimsSv;
          torchMlir = torchMlirPatched;
          materializePyTorchExported =
            ./scripts/materialize-pytorch-exported.py;
        };
        pipelineStagePackagesTosaNoHandshakePatched =
          pipelineLibTosaPatched.pipelineStagePackagesFromRegistry
          modelRegistryTosaNoHandshakePatched;
        viaTosaLinearW4A8PipelinePackages = {
          "pattern-linear-w4a8-via-tosa-torch" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-torch";
          "pattern-linear-w4a8-via-tosa-tosa" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-tosa";
          "pattern-linear-w4a8-via-tosa-linalg" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-linalg";
          "pattern-linear-w4a8-via-tosa-cf" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-cf";
          "pattern-linear-w4a8-via-tosa-handshake" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-handshake";
          "pattern-linear-w4a8-via-tosa-hs-ext" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-hs-ext";
          "pattern-linear-w4a8-via-tosa-hw0" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-hw0";
          "pattern-linear-w4a8-via-tosa-hw" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-hw";
          "pattern-linear-w4a8-via-tosa-hw-clean" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-hw-clean";
          "pattern-linear-w4a8-via-tosa-sv-mlir" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-sv-mlir";
          "pattern-linear-w4a8-via-tosa-sv" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-sv";
          "pattern-linear-w4a8-via-tosa-sv-provenance-report" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-sv-provenance-report";
          "pattern-linear-w4a8-via-tosa-yosys-stat" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-yosys-stat";
          "pattern-linear-w4a8-core-via-tosa-torch" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-torch";
          "pattern-linear-w4a8-core-via-tosa-tosa" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-tosa";
          "pattern-linear-w4a8-core-via-tosa-linalg" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-linalg";
          "pattern-linear-w4a8-core-via-tosa-cf" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-cf";
          "pattern-linear-w4a8-core-via-tosa-handshake" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-handshake";
          "pattern-linear-w4a8-core-via-tosa-hs-ext" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-hs-ext";
          "pattern-linear-w4a8-core-via-tosa-hw0" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-hw0";
          "pattern-linear-w4a8-core-via-tosa-hw" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-hw";
          "pattern-linear-w4a8-core-via-tosa-hw-clean" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-hw-clean";
          "pattern-linear-w4a8-core-via-tosa-sv-mlir" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-sv-mlir";
          "pattern-linear-w4a8-core-via-tosa-sv" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-sv";
          "pattern-linear-w4a8-core-via-tosa-sv-provenance-report" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-sv-provenance-report";
          "pattern-linear-w4a8-core-via-tosa-yosys-stat" =
            pipelineStagePackagesTosaPatched."pattern-linear-w4a8-core-yosys-stat";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-torch" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-torch";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-tosa" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-tosa";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-linalg" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-linalg";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-scf";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-flat-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-flat-scf";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-calyx" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-calyx";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-llvm" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-llvm";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-sv" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-sv";
          "pattern-linear-w4a8-core-via-tosa-no-handshake-yosys-stat" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-linear-w4a8-core-yosys-stat";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-torch" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-torch";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-tosa" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-tosa";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-linalg" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-linalg";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-scf";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-flat-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-flat-scf";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-calyx" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-calyx";
          "pattern-embedding-w4a8-core-via-tosa-no-handshake-llvm" =
            pipelineStagePackagesTosaNoHandshakePatched."pattern-embedding-w4a8-core-llvm";
          "tinystories-representative-core-w4a8-via-tosa-torch" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-torch";
          "tinystories-representative-core-w4a8-via-tosa-tosa" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-tosa";
          "tinystories-representative-core-w4a8-via-tosa-linalg" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-linalg";
          "tinystories-representative-core-w4a8-via-tosa-cf" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-cf";
          "tinystories-representative-core-w4a8-via-tosa-handshake" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-handshake";
          "tinystories-representative-core-w4a8-via-tosa-hs-ext" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-hs-ext";
          "tinystories-representative-core-w4a8-via-tosa-hw0" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-hw0";
          "tinystories-representative-core-w4a8-via-tosa-hw" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-hw";
          "tinystories-representative-core-w4a8-via-tosa-hw-clean" =
            pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-hw-clean";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-torch" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-torch";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-tosa" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-tosa";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-linalg" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-linalg";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-scf";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-flat-scf" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-flat-scf";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-calyx";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-llvm" =
            pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-llvm";
          "tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv" =
            pkgs.runCommand "tinystories-representative-core-w4a8-calyx-sv" {
              buildInputs = [ circt ];
            } ''
              ${pkgs.bash}/bin/bash ${calyxToSvNoHandshake} \
                ${circt}/bin/circt-opt \
                ${
                  pipelineStagePackagesTosaNoHandshakePatched."tinystories-representative-core-w4a8-calyx"
                } \
                "$out"
            '';
        };
        torchMlirPatchedOpt = "${torchMlirPatched}/bin/torch-mlir-opt";
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

          "pattern-linear-w4a8-tosa-patched" =
            pkgs.runCommand "pattern-linear-w4a8-tosa-patched.mlir" {
              buildInputs = [ torchMlirPatched ];
            } ''
              ${torchMlirPatchedOpt} \
                ${pipelineStagePackages."pattern-linear-w4a8-torch"} \
                --torch-fuse-quantized-ops \
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
      in {
        packages = {
          inherit circt mlir torchMlir torchMlirPatched torchMlirUnpatched
            yosysPkg modelRegistryJson;
          model-registry = modelRegistryJson;
          default = modelRegistryJson;
        } // pipelineStagePackages // pipelineMetadataPackages
          // quantizedLinalgDiagnosticPackages
          // patchedLinearW4A8PipelinePackages
          // viaTosaLinearW4A8PipelinePackages;

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
