{ stdenv, cmake, ninja, llvmPackages, mlir }:

stdenv.mkDerivation {
  pname = "llm2fpga-mlir-passes";
  version = "0.1.0";

  src = ../tools/mlir-passes;

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [ llvmPackages.llvm mlir ];

  cmakeFlags = [
    "-DMLIR_DIR=${mlir.dev}/lib/cmake/mlir"
    "-DLLVM_DIR=${llvmPackages.llvm.dev}/lib/cmake/llvm"
  ];

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib"
    cp LLM2FPGAMLIRPasses.so "$out/lib/"
    runHook postInstall
  '';
}
