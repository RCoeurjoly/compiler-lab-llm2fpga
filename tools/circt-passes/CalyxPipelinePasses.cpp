#include "circt/Dialect/Calyx/CalyxDialect.h"
#include "circt/Dialect/Calyx/CalyxOps.h"

#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Math/IR/Math.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"

#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Location.h"
#include "mlir/Pass/Pass.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Tools/Plugins/PassPlugin.h"
#include "llvm/Config/llvm-config.h"

using namespace mlir;
using namespace circt;


namespace {
struct FoldIdentityIntegerArithmeticPass
    : public PassWrapper<FoldIdentityIntegerArithmeticPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(FoldIdentityIntegerArithmeticPass)

  StringRef getArgument() const final {
    return "llm2fpga-fold-identity-integer-arithmetic";
  }
  StringRef getDescription() const final {
    return "Fold integer add-zero and multiply-one operations.";
  }

  static bool isIntegerConstant(Value value, int64_t expected) {
    Attribute attr;
    if (!matchPattern(value, m_Constant(&attr)))
      return false;
    auto integer = dyn_cast<IntegerAttr>(attr);
    return integer && integer.getValue() == expected;
  }

  void runOnOperation() final {
    IRRewriter rewriter(getOperation().getContext());
    SmallVector<Operation *> candidates;
    getOperation().walk([&](Operation *op) {
      StringRef name = op->getName().getStringRef();
      if (name == "arith.addi" || name == "arith.muli")
        candidates.push_back(op);
    });
    for (Operation *op : candidates) {
      if (op->getNumOperands() != 2 || op->getNumResults() != 1)
        continue;
      int64_t identity = op->getName().getStringRef() == "arith.addi" ? 0 : 1;
      Value replacement;
      if (isIntegerConstant(op->getOperand(0), identity))
        replacement = op->getOperand(1);
      else if (isIntegerConstant(op->getOperand(1), identity))
        replacement = op->getOperand(0);
      if (replacement && replacement.getType() == op->getResult(0).getType())
        rewriter.replaceOp(op, replacement);
    }
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect>();
  }
};

struct LowerAuthenticatedSoftmaxCallPass
    : public PassWrapper<LowerAuthenticatedSoftmaxCallPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerAuthenticatedSoftmaxCallPass)
  StringRef getArgument() const final {
    return "llm2fpga-lower-attention-softmax-fixed";
  }
  StringRef getDescription() const final {
    return "Lower the authenticated tensor softmax operation to an RTL call boundary.";
  }
  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<func::FuncDialect>();
  }
  void runOnOperation() final {
    ModuleOp module = getOperation();
    MLIRContext *context = module.getContext();
    SmallVector<Operation *> ops;
    module.walk([&](Operation *op) {
      if (op->getName().getStringRef() == "llm2fpga.attention_softmax_fixed")
        ops.push_back(op);
    });
    for (Operation *op : ops) {
      auto resultType = op->getResult(0).getType();
      auto calleeType = FunctionType::get(context, op->getOperandTypes(), resultType);
      auto callee = module.lookupSymbol<func::FuncOp>("llm2fpga_attention_softmax_fixed");
      if (!callee) {
        callee = func::FuncOp::create(op->getLoc(),
                                      "llm2fpga_attention_softmax_fixed", calleeType);
        callee.setPrivate();
        module.push_back(callee);
      }
      OpBuilder builder(op);
      auto call = builder.create<func::CallOp>(op->getLoc(), callee.getName(),
                                                TypeRange{resultType}, op->getOperands());
      op->replaceAllUsesWith(call.getResults());
      op->erase();
    }
  }
};

// Resource-scout-only legalization.  This is intentionally not a behavioral
// replacement for the authenticated softmax exp contract.
struct LowerPolynomialExpScoutPass
    : public PassWrapper<LowerPolynomialExpScoutPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerPolynomialExpScoutPass)
  StringRef getArgument() const final {
    return "llm2fpga-lower-polynomial-exp-scout";
  }
  StringRef getDescription() const final {
    return "Replace f32 exp with a fifth-order resource-scout polynomial.";
  }
  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }
  void runOnOperation() final {
    SmallVector<math::ExpOp> ops;
    getOperation().walk([&](math::ExpOp op) {
      if (op.getResult().getType().isF32()) ops.push_back(op);
    });
    IRRewriter rewriter(getOperation().getContext());
    for (math::ExpOp op : ops) {
      rewriter.setInsertionPoint(op);
      Location loc = op.getLoc();
      auto type = rewriter.getF32Type();
      auto c = [&](double value) -> Value {
        return arith::ConstantOp::create(rewriter, loc, type,
                                          rewriter.getFloatAttr(type, value));
      };
      Value x = op.getOperand(), x2 = arith::MulFOp::create(rewriter, loc, x, x);
      Value x3 = arith::MulFOp::create(rewriter, loc, x2, x);
      Value x4 = arith::MulFOp::create(rewriter, loc, x3, x);
      Value x5 = arith::MulFOp::create(rewriter, loc, x4, x);
      Value result = arith::AddFOp::create(rewriter, loc, c(1.0), x);
      result = arith::AddFOp::create(rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x2, c(0.5)));
      result = arith::AddFOp::create(rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x3, c(1.0 / 6.0)));
      result = arith::AddFOp::create(rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x4, c(1.0 / 24.0)));
      result = arith::AddFOp::create(rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x5, c(1.0 / 120.0)));
      rewriter.replaceOp(op, result);
    }
  }
};

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
  PassRegistration<FoldIdentityIntegerArithmeticPass>();
  PassRegistration<LowerAuthenticatedSoftmaxCallPass>();
  PassRegistration<LowerPolynomialExpScoutPass>();
  PassRegistration<CalyxPipelineSanityPass>();
  PassRegistration<CalyxHwPreflightPass>();
}

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGACIRCTPasses",
          LLVM_VERSION_STRING, []() { registerLLM2FPGACIRCTPasses(); }};
}
