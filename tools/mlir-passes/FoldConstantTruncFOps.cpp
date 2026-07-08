#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"

#include "llvm/ADT/APFloat.h"

using namespace mlir;

namespace {
struct FoldConstantTruncFOpsPass
    : public PassWrapper<FoldConstantTruncFOpsPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(FoldConstantTruncFOpsPass)

  StringRef getArgument() const final { return "llm2fpga-fold-constant-truncf"; }
  StringRef getDescription() const final {
    return "Fold arith.truncf operations with constant float operands.";
  }

  void runOnOperation() final {
    ModuleOp module = getOperation();
    SmallVector<arith::TruncFOp> ops;

    module.walk([&](arith::TruncFOp op) { ops.push_back(op); });

    IRRewriter rewriter(module.getContext());
    for (arith::TruncFOp op : ops) {
      auto resultType = dyn_cast<FloatType>(op.getType());
      if (!resultType)
        continue;

      Attribute operandAttr;
      if (!matchPattern(op.getIn(), m_Constant(&operandAttr)))
        continue;

      auto operandFloat = dyn_cast<FloatAttr>(operandAttr);
      if (!operandFloat)
        continue;

      APFloat value = operandFloat.getValue();
      bool losesInfo = false;
      value.convert(resultType.getFloatSemantics(), APFloat::rmNearestTiesToEven,
                    &losesInfo);

      rewriter.setInsertionPoint(op);
      auto replacement = arith::ConstantOp::create(
          rewriter, op.getLoc(), resultType,
          rewriter.getFloatAttr(resultType, value));
      rewriter.replaceOp(op, replacement.getResult());
    }
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect>();
  }
};
} // namespace

MLIR_DECLARE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGAMLIRPasses", LLVM_VERSION_STRING,
          []() {
            PassRegistration<FoldConstantTruncFOpsPass>();
          }};
}
