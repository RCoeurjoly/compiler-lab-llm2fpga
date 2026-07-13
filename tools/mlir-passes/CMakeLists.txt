cmake_minimum_required(VERSION 3.20)
project(LLM2FPGAMLIRPasses LANGUAGES CXX)

find_package(MLIR REQUIRED CONFIG)

list(APPEND CMAKE_MODULE_PATH "${MLIR_CMAKE_DIR}")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)
include(AddMLIR)

include_directories(${MLIR_INCLUDE_DIRS})
add_definitions(${MLIR_DEFINITIONS})

add_mlir_library(LLM2FPGAMLIRPasses
  FoldConstantTruncFOps.cpp
  LegalizePt2eTosaZeroPoint.cpp
  MODULE

  LINK_LIBS PUBLIC
  MLIRArithDialect
  MLIRControlFlowDialect
  MLIRFuncDialect
  MLIRIR
  MLIRMathDialect
  MLIRMemRefDialect
  MLIRPass
  MLIRSCFDialect
  MLIRTosaDialect
)
