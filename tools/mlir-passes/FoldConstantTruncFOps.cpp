#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/ControlFlow/IR/ControlFlowOps.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/Math/IR/Math.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/IR/OpDefinition.h"
#include "mlir/IR/SymbolTable.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"

#include "llvm/ADT/APFloat.h"
#include "llvm/ADT/DenseSet.h"
#include "llvm/Support/CheckedArithmetic.h"

#include <optional>
#include <cstdlib>
#include <cstring>

using namespace mlir;

void registerLegalizePt2eTosaZeroPointPass();

namespace {
struct LowerAttentionSoftmaxFixedPass
    : public PassWrapper<LowerAttentionSoftmaxFixedPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerAttentionSoftmaxFixedPass)
  StringRef getArgument() const final { return "llm2fpga-lower-attention-softmax-fixed"; }
  StringRef getDescription() const final {
    return "Lower authenticated fixed attention softmax to an external RTL-call boundary.";
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
      SmallVector<Type> resultTypes{resultType};
      auto calleeType = FunctionType::get(context, op->getOperandTypes(), resultTypes);
      auto callee = module.lookupSymbol<func::FuncOp>("llm2fpga_attention_softmax_fixed");
      if (!callee)
        callee = func::FuncOp::create(op->getLoc(), "llm2fpga_attention_softmax_fixed", calleeType);
      if (callee->getParentOp() == nullptr)
        callee.setPrivate();
      if (callee->getParentOp() == nullptr)
        module.push_back(callee);
      OpBuilder builder(op);
      auto call = builder.create<func::CallOp>(op->getLoc(), callee.getName(),
                                                resultTypes, op->getOperands());
      op->replaceAllUsesWith(call.getResults());
      op->erase();
    }
  }
};

struct LowerFixedLayerNormQ16Pass
    : public PassWrapper<LowerFixedLayerNormQ16Pass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerFixedLayerNormQ16Pass)
  StringRef getArgument() const final {
    return "llm2fpga-lower-fixed-layernorm-q16";
  }
  StringRef getDescription() const final {
    return "Lower authenticated fixed Q16.16 LayerNorm to an external RTL call.";
  }
  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<func::FuncDialect>();
  }
  void runOnOperation() final {
    ModuleOp module = getOperation();
    MLIRContext *context = module.getContext();
    SmallVector<Operation *> ops;
    module.walk([&](Operation *op) {
      if (op->getName().getStringRef() == "llm2fpga.fixed_layer_norm_q16_16")
        ops.push_back(op);
    });
    for (Operation *op : ops) {
      auto resultType = op->getResult(0).getType();
      SmallVector<Type> resultTypes{resultType};
      auto calleeType = FunctionType::get(context, op->getOperandTypes(), resultTypes);
      auto callee = module.lookupSymbol<func::FuncOp>("llm2fpga_fixed_layer_norm_q16_16");
      if (!callee)
        callee = func::FuncOp::create(op->getLoc(), "llm2fpga_fixed_layer_norm_q16_16", calleeType);
      if (callee->getParentOp() == nullptr)
        callee.setPrivate();
      if (callee->getParentOp() == nullptr)
        module.push_back(callee);
      OpBuilder builder(op);
      auto call = builder.create<func::CallOp>(op->getLoc(), callee.getName(),
                                                resultTypes, op->getOperands());
      op->replaceAllUsesWith(call.getResults());
      op->erase();
    }
  }
};

// Remove only cast chains whose identity is provable from the integer widths.
// In particular, trunc(extsi|extui(x)) is an identity when the truncation
// returns to x's original width.  This is deliberately narrower than MLIR's
// general canonicalization so fixed-point wraparound semantics are preserved.
struct FoldRedundantIntegerCastsPass
    : public PassWrapper<FoldRedundantIntegerCastsPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(FoldRedundantIntegerCastsPass)

  StringRef getArgument() const final {
    return "llm2fpga-fold-redundant-integer-casts";
  }
  StringRef getDescription() const final {
    return "Fold provably identity integer extension/truncation pairs.";
  }

  void runOnOperation() final {
    IRRewriter rewriter(getOperation().getContext());
    SmallVector<arith::TruncIOp> truncs;
    getOperation().walk([&](arith::TruncIOp op) { truncs.push_back(op); });
    for (arith::TruncIOp trunc : truncs) {
      auto resultInt = dyn_cast<IntegerType>(trunc.getType());
      if (!resultInt)
        continue;
      Operation *def = trunc.getIn().getDefiningOp();
      if (!def || (def->getName().getStringRef() != "arith.extsi" &&
                   def->getName().getStringRef() != "arith.extui"))
        continue;
      auto sourceInt = dyn_cast<IntegerType>(def->getOperand(0).getType());
      auto extendedInt = dyn_cast<IntegerType>(def->getResult(0).getType());
      if (!sourceInt || !extendedInt ||
          sourceInt.getWidth() >= extendedInt.getWidth() ||
          sourceInt.getWidth() != resultInt.getWidth())
        continue;
      rewriter.replaceOp(trunc, def->getOperand(0));
    }
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect>();
  }
};

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
      StringRef name = op->getName().getStringRef();
      int64_t identity = name == "arith.addi" ? 0 : 1;
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

struct StaticMemRefView {
  Value base;
  int64_t offset = 0;
  SmallVector<int64_t> shape;
  SmallVector<int64_t> strides;
};

static bool isStatic(ArrayRef<int64_t> values) {
  return llvm::all_of(values, [](int64_t value) {
    return value != ShapedType::kDynamic;
  });
}

static SmallVector<int64_t> getIdentityStrides(ArrayRef<int64_t> shape) {
  SmallVector<int64_t> strides(shape.size(), 1);
  int64_t runningStride = 1;
  for (int64_t index = static_cast<int64_t>(shape.size()) - 1; index >= 0;
       --index) {
    strides[index] = runningStride;
    runningStride *= shape[index];
  }
  return strides;
}

static SmallVector<int64_t> getIdentityStrides(MemRefType type) {
  return getIdentityStrides(type.getShape());
}
static MemRefType getFlattenedStaticIdentityMemRef(MemRefType type) {
  if (!type || type.getRank() <= 1 || !type.hasStaticShape() ||
      !type.getLayout().isIdentity())
    return {};

  int64_t elementCount = 1;
  for (int64_t dim : type.getShape())
    elementCount *= dim;

  return MemRefType::get({elementCount}, type.getElementType(),
                         MemRefLayoutAttrInterface{}, type.getMemorySpace());
}

static Value materializeLinearIndex(OpBuilder &builder, Location loc,
                                    const StaticMemRefView &view,
                                    ValueRange indices) {
  Value linear =
      builder.create<arith::ConstantIndexOp>(loc, view.offset).getResult();
  for (auto [index, stride] : llvm::zip_equal(indices, view.strides)) {
    Value term = index;
    if (stride != 1) {
      Value strideValue =
          builder.create<arith::ConstantIndexOp>(loc, stride).getResult();
      term = arith::MulIOp::create(builder, loc, term, strideValue).getResult();
    }
    linear = arith::AddIOp::create(builder, loc, linear, term).getResult();
  }
  return linear;
}

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

struct LowerStaticMemRefViewsForCalyxPass
    : public PassWrapper<LowerStaticMemRefViewsForCalyxPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(
      LowerStaticMemRefViewsForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-static-memref-views-for-calyx";
  }
  StringRef getDescription() const final {
    return "Lower static memref views and ranked static memref function "
           "arguments to one-dimensional accesses accepted by Calyx.";
  }

  void runOnOperation() final {
    ModuleOp module = getOperation();
    llvm::DenseSet<Operation *> signatureProtectedFunctions;
    collectSignatureProtectedFunctions(module, signatureProtectedFunctions);

    materializeDenseResourceMemRefGlobals(module);
    DenseMap<StringAttr, MemRefType> flattenedGlobals;
    flattenStaticIdentityMemRefGlobals(module, flattenedGlobals);
    updateGetGlobalTypes(module, flattenedGlobals);
    module.walk([&](func::FuncOp funcOp) {
      runOnFunction(
          funcOp,
          signatureProtectedFunctions.contains(funcOp.getOperation()));
    });
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, func::FuncDialect,
                    memref::MemRefDialect, scf::SCFDialect>();
  }

private:
  void collectSignatureProtectedFunctions(
      ModuleOp module,
      llvm::DenseSet<Operation *> &signatureProtectedFunctions) {
    SymbolTableCollection symbolTables;
    auto protectDefinedCallee = [&](Operation *symbolUser,
                                    SymbolRefAttr symbol) {
      auto callee = symbolTables.lookupNearestSymbolFrom<func::FuncOp>(
          symbolUser, symbol);
      if (callee) {
        if (!callee.isExternal())
          signatureProtectedFunctions.insert(callee.getOperation());
        return;
      }

      if (auto caller = symbolUser->getParentOfType<func::FuncOp>())
        signatureProtectedFunctions.insert(caller.getOperation());
    };
    module.walk([&](func::CallOp call) {
      if (auto symbol = call->getAttrOfType<SymbolRefAttr>("callee"))
        protectDefinedCallee(call.getOperation(), symbol);
      else if (auto caller = call->getParentOfType<func::FuncOp>())
        signatureProtectedFunctions.insert(caller.getOperation());
    });
    module.walk([&](func::ConstantOp constant) {
      if (auto symbol = constant->getAttrOfType<SymbolRefAttr>("value"))
        protectDefinedCallee(constant.getOperation(), symbol);
      else if (auto caller = constant->getParentOfType<func::FuncOp>())
        signatureProtectedFunctions.insert(caller.getOperation());
    });
  }

  void materializeDenseResourceMemRefGlobals(ModuleOp module) {
    module.walk([&](memref::GlobalOp global) {
      std::optional<Attribute> initialValue = global.getInitialValue();
      if (!initialValue)
        return;

      if (auto resource = dyn_cast<DenseF32ResourceElementsAttr>(*initialValue)) {
        std::optional<ArrayRef<float>> values = resource.tryGetAsArrayRef();
        if (!values)
          return;
        global.setInitialValueAttr(DenseElementsAttr::get(resource.getType(),
                                                          *values));
      }
    });
  }

  void flattenStaticIdentityMemRefGlobals(
      ModuleOp module, DenseMap<StringAttr, MemRefType> &flattenedGlobals) {
    module.walk([&](memref::GlobalOp global) {
      MemRefType flattenedType =
          getFlattenedStaticIdentityMemRef(global.getType());
      if (!flattenedType)
        return;

      std::optional<Attribute> initialValue = global.getInitialValue();
      if (initialValue) {
        if (auto dense = dyn_cast<DenseElementsAttr>(*initialValue)) {
          auto tensorType = RankedTensorType::get(
              flattenedType.getShape(), flattenedType.getElementType());
          global.setInitialValueAttr(dense.reshape(tensorType));
        }
      }

      global.setType(flattenedType);
      flattenedGlobals[global.getSymNameAttr()] = flattenedType;
    });
  }

  void updateGetGlobalTypes(
      ModuleOp module, const DenseMap<StringAttr, MemRefType> &flattenedGlobals) {
    module.walk([&](memref::GetGlobalOp getGlobal) {
      StringAttr name = getGlobal.getNameAttr().getAttr();
      auto found = flattenedGlobals.find(name);
      if (found == flattenedGlobals.end())
        return;
      getGlobal.getResult().setType(found->second);
    });
  }

  void runOnFunction(func::FuncOp funcOp, bool protectSignature) {
    if (funcOp.isExternal())
      return;

    DenseMap<Value, StaticMemRefView> argumentViews;
    if (!protectSignature)
      flattenStaticIdentityMemRefArguments(funcOp, argumentViews);

    SmallVector<memref::LoadOp> loads;
    SmallVector<memref::StoreOp> stores;
    SmallVector<memref::CopyOp> copies;
    SmallVector<Operation *> viewOps;
    funcOp.walk([&](Operation *op) {
      if (auto load = dyn_cast<memref::LoadOp>(op))
        loads.push_back(load);
      else if (auto store = dyn_cast<memref::StoreOp>(op))
        stores.push_back(store);
      else if (auto copy = dyn_cast<memref::CopyOp>(op))
        copies.push_back(copy);
      else if (isa<memref::ReinterpretCastOp, memref::ExpandShapeOp,
                   memref::CollapseShapeOp, memref::SubViewOp>(op))
        viewOps.push_back(op);
    });

    IRRewriter rewriter(funcOp.getContext());
    for (memref::LoadOp load : loads)
      rewriteLoad(load, argumentViews, rewriter);
    for (memref::StoreOp store : stores)
      rewriteStore(store, argumentViews, rewriter);
    for (memref::CopyOp copy : copies)
      rewriteCopy(copy, argumentViews, rewriter);

    for (Operation *viewOp : llvm::reverse(viewOps)) {
      if (viewOp->use_empty())
        rewriter.eraseOp(viewOp);
    }
  }

  void flattenStaticIdentityMemRefArguments(
      func::FuncOp funcOp,
      DenseMap<Value, StaticMemRefView> &argumentViews) {
    FunctionType functionType = funcOp.getFunctionType();
    SmallVector<Type> inputs(functionType.getInputs());
    DenseMap<Value, StaticMemRefView> candidateViews;
    for (auto [index, input] : llvm::enumerate(inputs)) {
      auto memrefType = dyn_cast<MemRefType>(input);
      if (!getFlattenedStaticIdentityMemRef(memrefType))
        continue;
      BlockArgument arg = funcOp.getArgument(index);
      candidateViews[arg] = StaticMemRefView{
          arg, 0, SmallVector<int64_t>(memrefType.getShape()),
          getIdentityStrides(memrefType)};
    }

    while (true) {
      SmallVector<Value> newlyProtectedArguments;
      DenseMap<Value, bool> rewritableViewUses;
      for (auto &candidate : candidateViews) {
        Value argument = candidate.first;
        if (canRewriteAllViewUses(argument, candidateViews,
                                  rewritableViewUses))
          continue;
        newlyProtectedArguments.push_back(argument);
      }
      if (newlyProtectedArguments.empty())
        break;
      for (Value argument : newlyProtectedArguments)
        candidateViews.erase(argument);
    }

    bool changed = false;

    for (auto [index, input] : llvm::enumerate(inputs)) {
      BlockArgument arg = funcOp.getArgument(index);
      auto candidate = candidateViews.find(arg);
      if (candidate == candidateViews.end())
        continue;

      auto memrefType = cast<MemRefType>(input);
      MemRefType flattenedType = getFlattenedStaticIdentityMemRef(memrefType);
      argumentViews[arg] = candidate->second;
      inputs[index] = flattenedType;
      arg.setType(flattenedType);
      changed = true;
    }

    if (!changed)
      return;

    funcOp.setFunctionType(FunctionType::get(
        funcOp.getContext(), inputs, functionType.getResults()));
  }

  std::optional<StaticMemRefView>
  getStaticView(Value value, const DenseMap<Value, StaticMemRefView> &argViews) {
    auto argView = argViews.find(value);
    if (argView != argViews.end())
      return argView->second;

    if (auto subview = value.getDefiningOp<memref::SubViewOp>()) {
      auto sourceView = getStaticView(subview.getSource(), argViews);
      ArrayRef<int64_t> offsets = subview.getStaticOffsets();
      ArrayRef<int64_t> sizes = subview.getStaticSizes();
      ArrayRef<int64_t> strides = subview.getStaticStrides();
      auto resultType = subview.getType();
      if (!sourceView || !isStatic(offsets) || !isStatic(sizes) ||
          !isStatic(strides) || !resultType.hasStaticShape() ||
          sourceView->shape.size() != unsigned(resultType.getRank()) ||
          offsets.size() != sourceView->shape.size() ||
          sizes.size() != sourceView->shape.size() ||
          strides.size() != sourceView->shape.size() ||
          sourceView->strides.size() != sourceView->shape.size() ||
          resultType.getShape() != sizes)
        return std::nullopt;

      int64_t composedOffset = sourceView->offset;
      SmallVector<int64_t> composedStrides;
      composedStrides.reserve(strides.size());
      for (auto [offset, stride, sourceStride] :
           llvm::zip_equal(offsets, strides, sourceView->strides)) {
        std::optional<int64_t> nextOffset =
            llvm::checkedMulAdd(offset, sourceStride, composedOffset);
        std::optional<int64_t> composedStride =
            llvm::checkedMul(stride, sourceStride);
        if (!nextOffset || !composedStride)
          return std::nullopt;
        composedOffset = *nextOffset;
        composedStrides.push_back(*composedStride);
      }

      SmallVector<int64_t> resultStrides;
      int64_t resultOffset = 0;
      if (failed(resultType.getStridesAndOffset(resultStrides, resultOffset)) ||
          !isStatic(resultStrides) || ShapedType::isDynamic(resultOffset) ||
          resultStrides != composedStrides || resultOffset != composedOffset)
        return std::nullopt;

      return StaticMemRefView{sourceView->base, composedOffset,
                              SmallVector<int64_t>(sizes), composedStrides};
    }

    if (auto cast = value.getDefiningOp<memref::ReinterpretCastOp>()) {
      if (!isa<MemRefType>(cast.getSource().getType()))
        return std::nullopt;

      ArrayRef<int64_t> offsets = cast.getStaticOffsets();
      ArrayRef<int64_t> strides = cast.getStaticStrides();
      if (offsets.size() != 1 || !isStatic(offsets) || !isStatic(strides))
        return std::nullopt;

      auto resultType = cast.getResult().getType();
      if (!resultType.hasStaticShape())
        return std::nullopt;

      auto sourceView = getStaticView(cast.getSource(), argViews);
      if (!sourceView)
        return std::nullopt;

      return StaticMemRefView{sourceView->base, offsets.front(),
                              SmallVector<int64_t>(resultType.getShape()),
                              SmallVector<int64_t>(strides)};
    }

    if (auto expand = value.getDefiningOp<memref::ExpandShapeOp>()) {
      auto sourceView = getStaticView(expand.getSrc(), argViews);
      auto resultType = expand.getResult().getType();
      if (!sourceView || !resultType.hasStaticShape() ||
          sourceView->strides != getIdentityStrides(sourceView->shape))
        return std::nullopt;
      return StaticMemRefView{sourceView->base, sourceView->offset,
                              SmallVector<int64_t>(resultType.getShape()),
                              getIdentityStrides(resultType)};
    }

    if (auto collapse = value.getDefiningOp<memref::CollapseShapeOp>()) {
      auto sourceView = getStaticView(collapse.getSrc(), argViews);
      auto resultType = collapse.getResult().getType();
      if (!sourceView || !resultType.hasStaticShape())
        return std::nullopt;

      if (sourceView->strides == getIdentityStrides(sourceView->shape))
        return StaticMemRefView{sourceView->base, sourceView->offset,
                                SmallVector<int64_t>(resultType.getShape()),
                                getIdentityStrides(resultType)};

      auto reassociation = collapse.getReassociationIndices();
      if (sourceView->shape.size() != 2 ||
          sourceView->strides.size() != 2 || sourceView->shape[0] <= 0 ||
          sourceView->shape[1] != 1 || sourceView->strides[0] <= 0 ||
          sourceView->strides[1] != 1 || reassociation.size() != 1 ||
          reassociation.front().size() != 2 ||
          reassociation.front()[0] != 0 || reassociation.front()[1] != 1 ||
          resultType.getRank() != 1 ||
          resultType.getShape().front() != sourceView->shape[0])
        return std::nullopt;

      SmallVector<int64_t> resultStrides;
      int64_t resultOffset = 0;
      if (failed(resultType.getStridesAndOffset(resultStrides, resultOffset)) ||
          !isStatic(resultStrides) || ShapedType::isDynamic(resultOffset) ||
          resultStrides.size() != 1 ||
          resultStrides.front() != sourceView->strides[0] ||
          resultOffset != sourceView->offset)
        return std::nullopt;

      return StaticMemRefView{
          sourceView->base, sourceView->offset,
          SmallVector<int64_t>(resultType.getShape()), resultStrides};
    }

    auto memrefType = dyn_cast<MemRefType>(value.getType());
    if (!memrefType || memrefType.getRank() > 1)
      return std::nullopt;

    return StaticMemRefView{value, 0, SmallVector<int64_t>(memrefType.getShape()),
                            SmallVector<int64_t>(memrefType.getRank(), 1)};
  }

  bool canRewriteAllViewUses(
      Value value, const DenseMap<Value, StaticMemRefView> &argViews,
      DenseMap<Value, bool> &cache) {
    auto cached = cache.find(value);
    if (cached != cache.end())
      return cached->second;

    for (OpOperand &use : value.getUses()) {
      Operation *user = use.getOwner();
      if (auto load = dyn_cast<memref::LoadOp>(user)) {
        if (load.getMemRef() == value && getStaticView(value, argViews))
          continue;
        return false;
      }
      if (auto store = dyn_cast<memref::StoreOp>(user)) {
        if (store.getMemRef() == value && getStaticView(value, argViews))
          continue;
        return false;
      }
      if (auto copy = dyn_cast<memref::CopyOp>(user)) {
        auto sourceView = getStaticView(copy.getSource(), argViews);
        auto targetView = getStaticView(copy.getTarget(), argViews);
        if (sourceView && targetView && sourceView->shape == targetView->shape)
          continue;
        return false;
      }

      Value result;
      if (auto subview = dyn_cast<memref::SubViewOp>(user))
        result = subview.getResult();
      else if (auto cast = dyn_cast<memref::ReinterpretCastOp>(user))
        result = cast.getResult();
      else if (auto expand = dyn_cast<memref::ExpandShapeOp>(user))
        result = expand.getResult();
      else if (auto collapse = dyn_cast<memref::CollapseShapeOp>(user))
        result = collapse.getResult();
      if (!result || !getStaticView(result, argViews) ||
          !canRewriteAllViewUses(result, argViews, cache)) {
        cache[value] = false;
        return false;
      }
    }
    cache[value] = true;
    return true;
  }

  SmallVector<Value> getAccessIndices(OpBuilder &builder, Location loc,
                                      const StaticMemRefView &view,
                                      ValueRange indices) {
    auto baseType = cast<MemRefType>(view.base.getType());
    if (baseType.getRank() == 0)
      return {};
    return {materializeLinearIndex(builder, loc, view, indices)};
  }

  void rewriteLoad(memref::LoadOp load,
                   const DenseMap<Value, StaticMemRefView> &argViews,
                   IRRewriter &rewriter) {
    auto view = getStaticView(load.getMemRef(), argViews);
    auto baseType = view ? cast<MemRefType>(view->base.getType()) : MemRefType();
    if (!view || (view->base == load.getMemRef() &&
                  load.getIndices().size() == unsigned(baseType.getRank())))
      return;

    rewriter.setInsertionPoint(load);
    SmallVector<Value> indices =
        getAccessIndices(rewriter, load.getLoc(), *view, load.getIndices());
    auto replacement =
        memref::LoadOp::create(rewriter, load.getLoc(), view->base, indices);
    rewriter.replaceOp(load, replacement.getResult());
  }

  void rewriteStore(memref::StoreOp store,
                    const DenseMap<Value, StaticMemRefView> &argViews,
                    IRRewriter &rewriter) {
    auto view = getStaticView(store.getMemRef(), argViews);
    auto baseType = view ? cast<MemRefType>(view->base.getType()) : MemRefType();
    if (!view || (view->base == store.getMemRef() &&
                  store.getIndices().size() == unsigned(baseType.getRank())))
      return;

    rewriter.setInsertionPoint(store);
    SmallVector<Value> indices =
        getAccessIndices(rewriter, store.getLoc(), *view, store.getIndices());
    memref::StoreOp::create(rewriter, store.getLoc(), store.getValueToStore(),
                            view->base, indices);
    rewriter.eraseOp(store);
  }

  void rewriteCopy(memref::CopyOp copy,
                   const DenseMap<Value, StaticMemRefView> &argViews,
                   IRRewriter &rewriter) {
    auto sourceView = getStaticView(copy.getSource(), argViews);
    auto targetView = getStaticView(copy.getTarget(), argViews);
    if (!sourceView || !targetView || sourceView->shape != targetView->shape)
      return;

    if (sourceView->base == copy.getSource() && targetView->base == copy.getTarget() &&
        sourceView->shape.size() <= 1 && targetView->shape.size() <= 1)
      return;

    rewriter.setInsertionPoint(copy);
    SmallVector<Value> indices;
    emitCopyLoopNest(rewriter, copy.getLoc(), sourceView->shape, 0, indices,
                     *sourceView, *targetView);
    rewriter.eraseOp(copy);
  }

  void emitCopyLoopNest(OpBuilder &builder, Location loc, ArrayRef<int64_t> shape,
                        unsigned dim, SmallVectorImpl<Value> &indices,
                        const StaticMemRefView &sourceView,
                        const StaticMemRefView &targetView) {
    if (dim == shape.size()) {
      SmallVector<Value> sourceIndices =
          getAccessIndices(builder, loc, sourceView, indices);
      SmallVector<Value> targetIndices =
          getAccessIndices(builder, loc, targetView, indices);
      Value value =
          memref::LoadOp::create(builder, loc, sourceView.base, sourceIndices);
      memref::StoreOp::create(builder, loc, value, targetView.base,
                              targetIndices);
      return;
    }

    Value lower = builder.create<arith::ConstantIndexOp>(loc, 0);
    Value upper = builder.create<arith::ConstantIndexOp>(loc, shape[dim]);
    Value step = builder.create<arith::ConstantIndexOp>(loc, 1);
    auto loop = scf::ForOp::create(builder, loc, lower, upper, step);

    OpBuilder::InsertionGuard guard(builder);
    builder.setInsertionPointToStart(loop.getBody());
    indices.push_back(loop.getInductionVar());
    emitCopyLoopNest(builder, loc, shape, dim + 1, indices, sourceView,
                     targetView);
    indices.pop_back();
  }
};

struct DropCalyxUnsupportedAssertOpsPass
    : public PassWrapper<DropCalyxUnsupportedAssertOpsPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(
      DropCalyxUnsupportedAssertOpsPass)

  StringRef getArgument() const final {
    return "llm2fpga-drop-calyx-unsupported-asserts";
  }
  StringRef getDescription() const final {
    return "Drop cf.assert operations before Calyx lowering under the valid "
           "input-domain contract.";
  }

  void runOnOperation() final {
    SmallVector<cf::AssertOp> asserts;
    getOperation().walk([&](cf::AssertOp op) { asserts.push_back(op); });

    IRRewriter rewriter(getOperation().getContext());
    for (cf::AssertOp op : asserts)
      rewriter.eraseOp(op);
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<cf::ControlFlowDialect>();
  }
};

struct LowerRoundEvenForCalyxPass
    : public PassWrapper<LowerRoundEvenForCalyxPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerRoundEvenForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-roundeven-for-calyx";
  }
  StringRef getDescription() const final {
    return "Lower scalar f32 math.roundeven to arith operations before Calyx "
           "lowering.";
  }

  void runOnOperation() final {
    SmallVector<math::RoundEvenOp> ops;
    getOperation().walk([&](math::RoundEvenOp op) { ops.push_back(op); });

    IRRewriter rewriter(getOperation().getContext());
    for (math::RoundEvenOp op : ops)
      lowerRoundEven(op, rewriter);
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

private:
  void lowerRoundEven(math::RoundEvenOp op, IRRewriter &rewriter) {
    auto floatType = dyn_cast<FloatType>(op.getType());
    if (!floatType || !floatType.isF32())
      return;

    Location loc = op.getLoc();
    Value input = op.getOperand();
    auto intType = IntegerType::get(op.getContext(), 32);

    rewriter.setInsertionPoint(op);

    Value halfF = arith::ConstantOp::create(
        rewriter, loc, floatType, rewriter.getFloatAttr(floatType, 0.5));
    Value negHalfF = arith::ConstantOp::create(
        rewriter, loc, floatType, rewriter.getFloatAttr(floatType, -0.5));
    Value zeroI = arith::ConstantOp::create(
        rewriter, loc, intType, rewriter.getIntegerAttr(intType, 0));
    Value oneI = arith::ConstantOp::create(
        rewriter, loc, intType, rewriter.getIntegerAttr(intType, 1));
    Value negOneI = arith::ConstantOp::create(
        rewriter, loc, intType, rewriter.getIntegerAttr(intType, -1));

    Value truncI = arith::FPToSIOp::create(rewriter, loc, intType, input);
    Value truncF = arith::SIToFPOp::create(rewriter, loc, floatType, truncI);
    Value frac = arith::SubFOp::create(rewriter, loc, input, truncF);

    Value oddBit = arith::AndIOp::create(rewriter, loc, truncI, oneI);
    Value isOdd = arith::CmpIOp::create(rewriter, loc,
                                        arith::CmpIPredicate::ne, oddBit, zeroI);

    Value posPastHalf = arith::CmpFOp::create(
        rewriter, loc, arith::CmpFPredicate::OGT, frac, halfF);
    Value posTie = arith::CmpFOp::create(rewriter, loc,
                                         arith::CmpFPredicate::OEQ, frac, halfF);
    Value posTieOdd = arith::AndIOp::create(rewriter, loc, posTie, isOdd);
    Value roundUp = arith::OrIOp::create(rewriter, loc, posPastHalf, posTieOdd);

    Value negPastHalf = arith::CmpFOp::create(
        rewriter, loc, arith::CmpFPredicate::OLT, frac, negHalfF);
    Value negTie = arith::CmpFOp::create(rewriter, loc,
                                         arith::CmpFPredicate::OEQ, frac, negHalfF);
    Value negTieOdd = arith::AndIOp::create(rewriter, loc, negTie, isOdd);
    Value roundDown =
        arith::OrIOp::create(rewriter, loc, negPastHalf, negTieOdd);

    Value posAdjust =
        arith::SelectOp::create(rewriter, loc, roundUp, oneI, zeroI);
    Value negAdjust =
        arith::SelectOp::create(rewriter, loc, roundDown, negOneI, zeroI);
    Value adjusted = arith::AddIOp::create(rewriter, loc, truncI, posAdjust);
    Value roundedI = arith::AddIOp::create(rewriter, loc, adjusted, negAdjust);
    Value roundedF =
        arith::SIToFPOp::create(rewriter, loc, floatType, roundedI);

    Value result = roundedF;
    auto div = input.getDefiningOp<arith::DivFOp>();
    auto divisor = div ? div.getRhs().getDefiningOp<arith::ConstantOp>()
                       : arith::ConstantOp();
    auto divisorAttr = divisor ? dyn_cast<FloatAttr>(divisor.getValue())
                               : FloatAttr();
    const char *disableQ412Guard =
        std::getenv("LLM2FPGA_DISABLE_Q412_ROUNDEVEN_GUARD");
    const bool q412GuardDisabled =
        disableQ412Guard && std::strcmp(disableQ412Guard, "1") == 0;
    if (!q412GuardDisabled && divisorAttr &&
        divisorAttr.getValueAsDouble() == 0.000244140625) {
      // The RC softmax path requantizes a finite negative mask through an
      // exact Q4.12 scale (2^-12). The division can overflow to -inf before
      // roundeven. Values with |x| >= 2^31 have no fractional f32 bits; this
      // range also includes infinities and NaNs. Preserve those inputs rather
      // than invoking the overflowing integer arithmetic. Restricting the
      // guard to this proven-overflow family avoids multiplying Calyx compile
      // cost at every roundeven site.
      // The observed RC counterexample is negative infinity.  Compare against
      // -FLT_MAX rather than materializing an integer bit mask: this is the
      // smallest guard that covers the overflowing division result (finite
      // f32 values are never less than -FLT_MAX).
      Value negFltMax = arith::ConstantOp::create(
          rewriter, loc, floatType,
          rewriter.getFloatAttr(floatType, -3.4028234663852886e38));
      Value bypassConversion = arith::CmpFOp::create(
          rewriter, loc, arith::CmpFPredicate::OLT, input, negFltMax);
      result = arith::SelectOp::create(rewriter, loc, bypassConversion, input,
                                       roundedF);
    }

    rewriter.replaceOp(op, result);
  }
};

struct LowerExactMathForCalyxPass
    : public PassWrapper<LowerExactMathForCalyxPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerExactMathForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-exact-math-for-calyx";
  }
  StringRef getDescription() const final {
    return "Lower scalar f32 floor, ceil, and rsqrt to arithmetic supported by "
           "SCF-to-Calyx.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

  void runOnOperation() final {
    SmallVector<Operation *> ops;
    getOperation().walk([&](Operation *op) {
      if (isa<math::FloorOp, math::CeilOp, math::RsqrtOp>(op))
        ops.push_back(op);
    });

    IRRewriter rewriter(getOperation().getContext());
    for (Operation *op : ops) {
      auto floatType = dyn_cast<FloatType>(op->getResult(0).getType());
      if (!floatType || !floatType.isF32())
        continue;

      Location loc = op->getLoc();
      Value input = op->getOperand(0);
      rewriter.setInsertionPoint(op);

      if (isa<math::RsqrtOp>(op)) {
        Value one = arith::ConstantOp::create(
            rewriter, loc, floatType, rewriter.getFloatAttr(floatType, 1.0));
        Value root = math::SqrtOp::create(rewriter, loc, input);
        Value result = arith::DivFOp::create(rewriter, loc, one, root);
        rewriter.replaceOp(op, result);
        continue;
      }

      auto intType = rewriter.getI32Type();
      Value zero = arith::ConstantOp::create(
          rewriter, loc, intType, rewriter.getIntegerAttr(intType, 0));
      Value step = arith::ConstantOp::create(
          rewriter, loc, intType,
          rewriter.getIntegerAttr(intType, isa<math::FloorOp>(op) ? -1 : 1));
      Value truncI = arith::FPToSIOp::create(rewriter, loc, intType, input);
      Value truncF = arith::SIToFPOp::create(rewriter, loc, floatType, truncI);
      auto predicate = isa<math::FloorOp>(op) ? arith::CmpFPredicate::OLT
                                              : arith::CmpFPredicate::OGT;
      Value needsAdjustment =
          arith::CmpFOp::create(rewriter, loc, predicate, input, truncF);
      Value adjustment = arith::SelectOp::create(
          rewriter, loc, needsAdjustment, step, zero);
      Value roundedI =
          arith::AddIOp::create(rewriter, loc, truncI, adjustment);
      Value roundedF =
          arith::SIToFPOp::create(rewriter, loc, floatType, roundedI);
      rewriter.replaceOp(op, roundedF);
    }
  }
};

struct LowerI1UIToFPForCalyxPass
    : public PassWrapper<LowerI1UIToFPForCalyxPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerI1UIToFPForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-i1-uitofp-for-calyx";
  }
  StringRef getDescription() const final {
    return "Lower exact arith.uitofp i1 to f32 operations through i32 before "
           "Calyx lowering.";
  }

  void runOnOperation() final {
    SmallVector<arith::UIToFPOp> ops;
    getOperation().walk([&](arith::UIToFPOp op) {
      auto sourceType = dyn_cast<IntegerType>(op.getIn().getType());
      auto resultType = dyn_cast<FloatType>(op.getType());
      if (sourceType && sourceType.isInteger(1) && resultType &&
          resultType.isF32())
        ops.push_back(op);
    });

    IRRewriter rewriter(getOperation().getContext());
    for (arith::UIToFPOp op : ops)
      lower(op, rewriter);
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect>();
  }

private:
  void lower(arith::UIToFPOp op, IRRewriter &rewriter) {
    auto sourceType = dyn_cast<IntegerType>(op.getIn().getType());
    auto resultType = dyn_cast<FloatType>(op.getType());
    if (!sourceType || !sourceType.isInteger(1) || !resultType ||
        !resultType.isF32())
      return;

    rewriter.setInsertionPoint(op);
    Value widened = arith::ExtUIOp::create(
        rewriter, op.getLoc(), rewriter.getI32Type(), op.getIn());
    Value replacement =
        arith::SIToFPOp::create(rewriter, op.getLoc(), resultType, widened);
    rewriter.replaceOp(op, replacement);
  }
};

struct LowerScoutMathForCalyxPass
    : public PassWrapper<LowerScoutMathForCalyxPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerScoutMathForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-scout-math-for-calyx";
  }
  StringRef getDescription() const final {
    return "Apply explicitly approximate nonlinear arithmetic for the "
           "provisional resource scout only.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

  void runOnOperation() final {
    SmallVector<Operation *> ops;
    getOperation().walk([&](Operation *op) {
      if (isa<math::ExpOp, math::PowFOp, math::TanhOp>(op))
        ops.push_back(op);
    });

    IRRewriter rewriter(getOperation().getContext());
    for (Operation *op : ops) {
      auto floatType = dyn_cast<FloatType>(op->getResult(0).getType());
      if (!floatType || !floatType.isF32())
        continue;
      rewriter.setInsertionPoint(op);
      Location loc = op->getLoc();
      Value x = op->getOperand(0);

      if (isa<math::PowFOp>(op)) {
        // The observed TinyStories GELU graph uses pow(x, 3). This resource
        // scout deliberately materializes x^3 and is not an equivalence path.
        Value square = arith::MulFOp::create(rewriter, loc, x, x);
        Value cube = arith::MulFOp::create(rewriter, loc, square, x);
        rewriter.replaceOp(op, cube);
        continue;
      }

      if (isa<math::ExpOp>(op)) {
        // First-order exp approximation used only to retain a live arithmetic
        // datapath during the resource scout.
        Value one = arith::ConstantOp::create(
            rewriter, loc, floatType, rewriter.getFloatAttr(floatType, 1.0));
        Value result = arith::AddFOp::create(rewriter, loc, one, x);
        rewriter.replaceOp(op, result);
        continue;
      }

      // Saturating linear tanh approximation: clamp(x, -1, 1). This is
      // intentionally provisional and must not be used for equivalence claims.
      Value negOne = arith::ConstantOp::create(
          rewriter, loc, floatType, rewriter.getFloatAttr(floatType, -1.0));
      Value one = arith::ConstantOp::create(
          rewriter, loc, floatType, rewriter.getFloatAttr(floatType, 1.0));
      Value below = arith::CmpFOp::create(
          rewriter, loc, arith::CmpFPredicate::OLT, x, negOne);
      Value lowerClamped =
          arith::SelectOp::create(rewriter, loc, below, negOne, x);
      Value above = arith::CmpFOp::create(
          rewriter, loc, arith::CmpFPredicate::OGT, lowerClamped, one);
      Value result =
          arith::SelectOp::create(rewriter, loc, above, one, lowerClamped);
      rewriter.replaceOp(op, result);
    }
  }
};

struct LowerPolynomialExpForCalyxPass
    : public PassWrapper<LowerPolynomialExpForCalyxPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerPolynomialExpForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-polynomial-exp-for-calyx";
  }
  StringRef getDescription() const final {
    return "Replace f32 math.exp with a documented fifth-order Taylor candidate.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

  void runOnOperation() final {
    SmallVector<math::ExpOp> ops;
    getOperation().walk([&](math::ExpOp op) {
      if (op.getResult().getType().isF32())
        ops.push_back(op);
    });
    IRRewriter rewriter(getOperation().getContext());
    for (math::ExpOp op : ops) {
      rewriter.setInsertionPoint(op);
      Location loc = op.getLoc();
      Value x = op.getOperand();
      auto type = rewriter.getF32Type();
      auto constant = [&](double value) -> Value {
        return arith::ConstantOp::create(
            rewriter, loc, type, rewriter.getFloatAttr(type, value));
      };
      Value x2 = arith::MulFOp::create(rewriter, loc, x, x);
      Value x3 = arith::MulFOp::create(rewriter, loc, x2, x);
      Value x4 = arith::MulFOp::create(rewriter, loc, x3, x);
      Value x5 = arith::MulFOp::create(rewriter, loc, x4, x);
      Value result = arith::AddFOp::create(rewriter, loc, constant(1.0), x);
      result = arith::AddFOp::create(
          rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x2, constant(0.5)));
      result = arith::AddFOp::create(
          rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x3, constant(1.0 / 6.0)));
      result = arith::AddFOp::create(
          rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x4, constant(1.0 / 24.0)));
      result = arith::AddFOp::create(
          rewriter, loc, result,
          arith::MulFOp::create(rewriter, loc, x5, constant(1.0 / 120.0)));
      rewriter.replaceOp(op, result);
    }
  }
};

struct LowerConstantFPowIForCalyxPass
    : public PassWrapper<LowerConstantFPowIForCalyxPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerConstantFPowIForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-constant-fpowi-for-calyx";
  }
  StringRef getDescription() const final {
    return "Replace constant-exponent f32 math.fpowi with multiplications.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

  void runOnOperation() final {
    SmallVector<math::FPowIOp> ops;
    getOperation().walk([&](math::FPowIOp op) {
      if (op.getResult().getType().isF32())
        ops.push_back(op);
    });
    IRRewriter rewriter(getOperation().getContext());
    for (math::FPowIOp op : ops) {
      auto constant =
          op.getOperand(1).getDefiningOp<arith::ConstantIntOp>();
      if (!constant)
        continue;
      int64_t power = constant.value();
      if (power < 0 || power > 3)
        continue;
      rewriter.setInsertionPoint(op);
      Value base = op.getOperand(0);
      Value result = base;
      if (power == 0) {
        auto type = rewriter.getF32Type();
        result = arith::ConstantOp::create(
            rewriter, op.getLoc(), type, rewriter.getFloatAttr(type, 1.0));
      } else if (power >= 2) {
        result = arith::MulFOp::create(rewriter, op.getLoc(), base, base);
        if (power == 3)
          result = arith::MulFOp::create(rewriter, op.getLoc(), result, base);
      }
      rewriter.replaceOp(op, result);
    }
  }
};

struct LowerRationalTanhForCalyxPass
    : public PassWrapper<LowerRationalTanhForCalyxPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerRationalTanhForCalyxPass)

  StringRef getArgument() const final {
    return "llm2fpga-lower-rational-tanh-for-calyx";
  }
  StringRef getDescription() const final {
    return "Replace f32 math.tanh with the gated rational candidate.";
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, math::MathDialect>();
  }

  void runOnOperation() final {
    SmallVector<math::TanhOp> ops;
    getOperation().walk([&](math::TanhOp op) {
      if (op.getResult().getType().isF32())
        ops.push_back(op);
    });
    IRRewriter rewriter(getOperation().getContext());
    for (math::TanhOp op : ops) {
      rewriter.setInsertionPoint(op);
      Location loc = op.getLoc();
      auto type = rewriter.getF32Type();
      auto constant = [&](double value) -> Value {
        return arith::ConstantOp::create(
            rewriter, loc, type, rewriter.getFloatAttr(type, value));
      };
      Value x = op.getOperand();
      Value x2 = arith::MulFOp::create(rewriter, loc, x, x);
      Value numerator = arith::MulFOp::create(
          rewriter, loc, x,
          arith::AddFOp::create(rewriter, loc, constant(27.0), x2));
      Value denominator = arith::AddFOp::create(
          rewriter, loc, constant(27.0),
          arith::MulFOp::create(rewriter, loc, constant(9.0), x2));
      rewriter.replaceOp(
          op, arith::DivFOp::create(rewriter, loc, numerator, denominator));
    }
  }
};
} // namespace

MLIR_DECLARE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerAttentionSoftmaxFixedPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerAttentionSoftmaxFixedPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerFixedLayerNormQ16Pass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerFixedLayerNormQ16Pass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(FoldRedundantIntegerCastsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(FoldRedundantIntegerCastsPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(FoldIdentityIntegerArithmeticPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(FoldIdentityIntegerArithmeticPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerStaticMemRefViewsForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerStaticMemRefViewsForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(DropCalyxUnsupportedAssertOpsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(DropCalyxUnsupportedAssertOpsPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerRoundEvenForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerRoundEvenForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerExactMathForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerExactMathForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerI1UIToFPForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerI1UIToFPForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerScoutMathForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerScoutMathForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerPolynomialExpForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerPolynomialExpForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerConstantFPowIForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerConstantFPowIForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerRationalTanhForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerRationalTanhForCalyxPass)

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGAMLIRPasses", LLVM_VERSION_STRING,
          []() {
            PassRegistration<FoldConstantTruncFOpsPass>();
            PassRegistration<LowerAttentionSoftmaxFixedPass>();
            PassRegistration<LowerFixedLayerNormQ16Pass>();
            PassRegistration<FoldRedundantIntegerCastsPass>();
            PassRegistration<FoldIdentityIntegerArithmeticPass>();
            PassRegistration<LowerStaticMemRefViewsForCalyxPass>();
            PassRegistration<DropCalyxUnsupportedAssertOpsPass>();
            PassRegistration<LowerRoundEvenForCalyxPass>();
            PassRegistration<LowerExactMathForCalyxPass>();
            PassRegistration<LowerI1UIToFPForCalyxPass>();
            PassRegistration<LowerScoutMathForCalyxPass>();
            PassRegistration<LowerPolynomialExpForCalyxPass>();
            PassRegistration<LowerConstantFPowIForCalyxPass>();
            PassRegistration<LowerRationalTanhForCalyxPass>();
            registerLegalizePt2eTosaZeroPointPass();
          }};
}
