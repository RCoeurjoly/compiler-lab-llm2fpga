#include "circt/Dialect/Calyx/CalyxDialect.h"
#include "circt/Dialect/Calyx/CalyxOps.h"

#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Location.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "llvm/Config/llvm-config.h"

using namespace mlir;
using namespace circt;

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

struct CalyxHwPreflightPass
    : public PassWrapper<CalyxHwPreflightPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(CalyxHwPreflightPass)

  StringRef getArgument() const final {
    return "llm2fpga-calyx-hw-preflight";
  }

  StringRef getDescription() const final {
    return "Reject Calyx shapes known to crash or block direct Calyx-HW lowering.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<calyx::CalyxDialect>();
  }

  void runOnOperation() final {
    ModuleOp module = getOperation();
    bool failed = false;
    bool reportedInvoke = false;
    bool reportedInstance = false;
    bool reportedSeqMemory = false;
    bool reportedMemory = false;

    module.walk([&](Operation *op) {
      if (isa<calyx::InvokeOp>(op) && !reportedInvoke) {
        failed = true;
        reportedInvoke = true;
      } else if (isa<calyx::InstanceOp>(op) && !reportedInstance) {
        failed = true;
        reportedInstance = true;
      } else if (isa<calyx::SeqMemoryOp>(op) && !reportedSeqMemory) {
        failed = true;
        reportedSeqMemory = true;
      } else if (isa<calyx::MemoryOp>(op) && !reportedMemory) {
        failed = true;
        reportedMemory = true;
      }
    });

    if (failed) {
      Location summaryLoc = UnknownLoc::get(module.getContext());
      if (reportedSeqMemory)
        emitError(summaryLoc)
            << "calyx.seq_mem blocks direct Calyx-HW lowering; "
               "add a memory lowering or external-memory ABI before --lower-calyx-to-hw";
      if (reportedMemory)
        emitError(summaryLoc)
            << "calyx.memory blocks direct Calyx-HW lowering; "
               "add a memory lowering or external-memory ABI before --lower-calyx-to-hw";
      if (reportedInstance)
        emitError(summaryLoc)
            << "calyx.instance blocks direct Calyx-HW lowering; "
               "lower or inline component instances before --lower-calyx-to-hw";
      if (reportedInvoke)
        emitError(summaryLoc)
            << "calyx.invoke blocks direct Calyx-HW lowering; "
               "structuralize invokes before --calyx-remove-groups";
      signalPassFailure();
    }
  }
};
} // namespace

static void registerLLM2FPGACIRCTPasses() {
  PassRegistration<CalyxPipelineSanityPass>();
  PassRegistration<CalyxHwPreflightPass>();
}

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGACIRCTPasses",
          LLVM_VERSION_STRING, []() { registerLLM2FPGACIRCTPasses(); }};
}
