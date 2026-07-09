cmake_minimum_required(VERSION 3.20)
project(LLM2FPGACIRCTPasses LANGUAGES CXX)

find_package(CIRCT REQUIRED CONFIG)
find_package(MLIR REQUIRED CONFIG)

list(APPEND CMAKE_MODULE_PATH "${MLIR_CMAKE_DIR}")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
list(APPEND CMAKE_MODULE_PATH "${CIRCT_CMAKE_DIR}")
include(AddLLVM)
include(AddMLIR)
include(AddCIRCT)

include_directories(${MLIR_INCLUDE_DIRS})
include_directories(${CIRCT_INCLUDE_DIRS})
add_definitions(${MLIR_DEFINITIONS})
add_definitions(${LLVM_DEFINITIONS})

add_mlir_library(LLM2FPGACIRCTPasses
  CalyxPipelinePasses.cpp
  MODULE

  LINK_LIBS PUBLIC
  CIRCTCalyx
  MLIRIR
  MLIRPass
)
