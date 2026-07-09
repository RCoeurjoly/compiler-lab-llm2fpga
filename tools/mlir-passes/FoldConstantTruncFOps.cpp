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
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"

#include "llvm/ADT/APFloat.h"

#include <optional>

using namespace mlir;

namespace {
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
    materializeDenseResourceMemRefGlobals(getOperation());
    DenseMap<StringAttr, MemRefType> flattenedGlobals;
    flattenStaticIdentityMemRefGlobals(getOperation(), flattenedGlobals);
    updateGetGlobalTypes(getOperation(), flattenedGlobals);
    getOperation().walk([&](func::FuncOp funcOp) { runOnFunction(funcOp); });
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<arith::ArithDialect, func::FuncDialect,
                    memref::MemRefDialect, scf::SCFDialect>();
  }

private:
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

  void runOnFunction(func::FuncOp funcOp) {
    if (funcOp.isExternal())
      return;

    DenseMap<Value, StaticMemRefView> argumentViews;
    flattenStaticIdentityMemRefArguments(funcOp, argumentViews);

    SmallVector<memref::LoadOp> loads;
    SmallVector<memref::StoreOp> stores;
    SmallVector<memref::CopyOp> copies;
    SmallVector<memref::ReinterpretCastOp> casts;
    SmallVector<memref::ExpandShapeOp> expands;
    SmallVector<memref::CollapseShapeOp> collapses;
    funcOp.walk([&](Operation *op) {
      if (auto load = dyn_cast<memref::LoadOp>(op))
        loads.push_back(load);
      else if (auto store = dyn_cast<memref::StoreOp>(op))
        stores.push_back(store);
      else if (auto copy = dyn_cast<memref::CopyOp>(op))
        copies.push_back(copy);
      else if (auto cast = dyn_cast<memref::ReinterpretCastOp>(op))
        casts.push_back(cast);
      else if (auto expand = dyn_cast<memref::ExpandShapeOp>(op))
        expands.push_back(expand);
      else if (auto collapse = dyn_cast<memref::CollapseShapeOp>(op))
        collapses.push_back(collapse);
    });

    IRRewriter rewriter(funcOp.getContext());
    for (memref::LoadOp load : loads)
      rewriteLoad(load, argumentViews, rewriter);
    for (memref::StoreOp store : stores)
      rewriteStore(store, argumentViews, rewriter);
    for (memref::CopyOp copy : copies)
      rewriteCopy(copy, argumentViews, rewriter);

    for (memref::ReinterpretCastOp cast : llvm::reverse(casts)) {
      if (cast->use_empty())
        rewriter.eraseOp(cast);
    }
    for (memref::ExpandShapeOp expand : llvm::reverse(expands)) {
      if (expand->use_empty())
        rewriter.eraseOp(expand);
    }
    for (memref::CollapseShapeOp collapse : llvm::reverse(collapses)) {
      if (collapse->use_empty())
        rewriter.eraseOp(collapse);
    }
  }

  void flattenStaticIdentityMemRefArguments(
      func::FuncOp funcOp, DenseMap<Value, StaticMemRefView> &argumentViews) {
    FunctionType functionType = funcOp.getFunctionType();
    SmallVector<Type> inputs(functionType.getInputs());
    bool changed = false;

    for (auto [index, input] : llvm::enumerate(inputs)) {
      auto memrefType = dyn_cast<MemRefType>(input);
      MemRefType flattenedType =
          getFlattenedStaticIdentityMemRef(memrefType);
      if (!flattenedType)
        continue;

      BlockArgument arg = funcOp.getArgument(index);
      argumentViews[arg] = StaticMemRefView{
          arg, 0, SmallVector<int64_t>(memrefType.getShape()),
          getIdentityStrides(memrefType)};
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

    if (auto cast = value.getDefiningOp<memref::ReinterpretCastOp>()) {
      auto sourceType = dyn_cast<MemRefType>(cast.getSource().getType());
      if (!sourceType)
        return std::nullopt;

      ArrayRef<int64_t> offsets = cast.getStaticOffsets();
      ArrayRef<int64_t> strides = cast.getStaticStrides();
      if (offsets.size() != 1 || !isStatic(offsets) || !isStatic(strides))
        return std::nullopt;

      auto resultType = cast.getResult().getType();
      if (!resultType.hasStaticShape())
        return std::nullopt;

      if (sourceType.getRank() <= 1)
        return StaticMemRefView{cast.getSource(), offsets.front(),
                                SmallVector<int64_t>(resultType.getShape()),
                                SmallVector<int64_t>(strides)};

      auto sourceView = getStaticView(cast.getSource(), argViews);
      if (!sourceView)
        return std::nullopt;

      return StaticMemRefView{sourceView->base, sourceView->offset + offsets.front(),
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
      if (!sourceView || !resultType.hasStaticShape() ||
          sourceView->strides != getIdentityStrides(sourceView->shape))
        return std::nullopt;
      return StaticMemRefView{sourceView->base, sourceView->offset,
                              SmallVector<int64_t>(resultType.getShape()),
                              getIdentityStrides(resultType)};
    }

    auto memrefType = dyn_cast<MemRefType>(value.getType());
    if (!memrefType || memrefType.getRank() > 1)
      return std::nullopt;

    return StaticMemRefView{value, 0, SmallVector<int64_t>(memrefType.getShape()),
                            SmallVector<int64_t>(memrefType.getRank(), 1)};
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

    rewriter.replaceOp(op, roundedF);
  }
};
} // namespace

MLIR_DECLARE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(FoldConstantTruncFOpsPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerStaticMemRefViewsForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerStaticMemRefViewsForCalyxPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(DropCalyxUnsupportedAssertOpsPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(DropCalyxUnsupportedAssertOpsPass)
MLIR_DECLARE_EXPLICIT_TYPE_ID(LowerRoundEvenForCalyxPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LowerRoundEvenForCalyxPass)

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGAMLIRPasses", LLVM_VERSION_STRING,
          []() {
            PassRegistration<FoldConstantTruncFOpsPass>();
            PassRegistration<LowerStaticMemRefViewsForCalyxPass>();
            PassRegistration<DropCalyxUnsupportedAssertOpsPass>();
            PassRegistration<LowerRoundEvenForCalyxPass>();
          }};
}
