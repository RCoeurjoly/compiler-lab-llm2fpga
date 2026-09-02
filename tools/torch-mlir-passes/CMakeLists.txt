cmake_minimum_required(VERSION 3.20)
project(LLM2FPGATorchMLIRPasses LANGUAGES CXX)

find_package(MLIR REQUIRED CONFIG)

if(NOT TORCH_MLIR_INCLUDE_DIR)
  message(FATAL_ERROR "TORCH_MLIR_INCLUDE_DIR is required")
endif()

list(APPEND CMAKE_MODULE_PATH "${MLIR_CMAKE_DIR}")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)
include(AddMLIR)

include_directories(${MLIR_INCLUDE_DIRS})
include_directories(${TORCH_MLIR_INCLUDE_DIR})
add_definitions(${MLIR_DEFINITIONS})

add_library(LLM2FPGATorchMLIRPasses MODULE
  LegalizeExactSerialGemv.cpp)
set_target_properties(LLM2FPGATorchMLIRPasses PROPERTIES PREFIX "")

mlir_target_link_libraries(LLM2FPGATorchMLIRPasses PRIVATE
  MLIRIR
  MLIRPass
)
