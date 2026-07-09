#include "circt/Dialect/Calyx/CalyxDialect.h"

#include "mlir/IR/BuiltinOps.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "llvm/Config/llvm-config.h"

using namespace mlir;

namespace {
struct CalyxPipelineSanityPass
    : public PassWrapper<CalyxPipelineSanityPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(CalyxPipelineSanityPass)

  StringRef getArgument() const final {
    return "llm2fpga-calyx-pipeline-sanity";
  }

  StringRef getDescription() const final {
    return "No-op pass used to verify LLM2FPGA CIRCT pass plugin loading.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<circt::calyx::CalyxDialect>();
  }

  void runOnOperation() final {}
};
} // namespace

static void registerLLM2FPGACIRCTPasses() {
  PassRegistration<CalyxPipelineSanityPass>();
}

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGACIRCTPasses",
          LLVM_VERSION_STRING, []() { registerLLM2FPGACIRCTPasses(); }};
}
