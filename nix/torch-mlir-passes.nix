{ stdenv, cmake, ninja, llvmPackages, mlir, torchMlir }:

stdenv.mkDerivation {
  pname = "llm2fpga-exact-serial-gemv-torch-mlir-passes";
  version = "0.1.0";

  src = ../tools/torch-mlir-passes;

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [ llvmPackages.llvm mlir torchMlir ];

  cmakeFlags = [
    "-DMLIR_DIR=${mlir.dev}/lib/cmake/mlir"
    "-DLLVM_DIR=${llvmPackages.llvm.dev}/lib/cmake/llvm"
    "-DTORCH_MLIR_INCLUDE_DIR=${torchMlir}/include"
    "-DMLIR_LINK_MLIR_DYLIB=ON"
  ];

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib"
    cp LLM2FPGATorchMLIRPasses.so "$out/lib/"
    runHook postInstall
  '';
}
