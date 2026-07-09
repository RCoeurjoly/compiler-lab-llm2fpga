{ stdenv, cmake, ninja, circt, mlir, llvm }:

stdenv.mkDerivation {
  pname = "llm2fpga-circt-passes";
  version = "0.1.0";

  src = ../tools/circt-passes;

  nativeBuildInputs = [ cmake ninja ];
  buildInputs = [ circt mlir llvm ];

  cmakeFlags = [
    "-DCIRCT_DIR=${circt.dev}/lib/cmake/circt"
    "-DMLIR_DIR=${mlir.dev}/lib/cmake/mlir"
    "-DLLVM_DIR=${llvm.dev}/lib/cmake/llvm"
  ];

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib"
    cp LLM2FPGACIRCTPasses.so "$out/lib/"
    runHook postInstall
  '';
}
