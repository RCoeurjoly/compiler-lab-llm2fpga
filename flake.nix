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
        pythonWithTorch = python.withPackages (ps: [ ps.torch ps.packaging ]);
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
          inherit pipelineScripts;
          directLowerScript = ./scripts/direct_lower.py;
        };
        modelRegistry = import ./nix/models.nix {
          inherit (pipelineLib) registerModel;
          inherit pythonWithTorch pythonWithTinyStories
            pythonWithTinyStoriesTorchAO torchMlir python tinyStories1m
            fpPrimsSv;
          compilePyTorch = ./scripts/compile-pytorch.py;
          matmulPy = ./src/matmul.py;
          matmulAdapterPy = ./src/matmul_adapter.py;
          matmulSrcDir = ./src;
          simDir = ./sim;
        };
        pipelineStagePackages =
          pipelineLib.pipelineStagePackagesFromRegistry modelRegistry;
        pipelineMetadataPackages =
          pipelineLib.metadataPackagesFromRegistry modelRegistry;
        modelRegistryJson = pipelineLib.registryIndexPackage modelRegistry;
      in {
        packages = {
          inherit circt mlir torchMlir torchMlirPatched torchMlirUnpatched
            yosysPkg modelRegistryJson;
          model-registry = modelRegistryJson;
          default = modelRegistryJson;
        } // pipelineStagePackages // pipelineMetadataPackages;

        checks.default = modelRegistryJson;

        devShells.default = pkgs.mkShell {
          packages = [
            circt
            mlir
            torchMlir
            yosysPkg
            yosysSlang
            pythonWithTorch
            pythonWithTinyStories
            pkgs.verilator
          ];
        };

        formatter = pkgs.nixfmt-classic;
      });
}
