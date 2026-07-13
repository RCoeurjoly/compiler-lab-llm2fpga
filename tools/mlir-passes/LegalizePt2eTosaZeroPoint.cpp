#include "mlir/Dialect/Tosa/IR/TosaOps.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Pass/Pass.h"

#include "llvm/ADT/APInt.h"

using namespace mlir;

namespace {
static bool hasIntegerElementWidth(Value value, unsigned width) {
  auto type = dyn_cast<RankedTensorType>(value.getType());
  auto elementType = type ? dyn_cast<IntegerType>(type.getElementType())
                          : IntegerType{};
  return elementType && elementType.isSignless() &&
         elementType.getWidth() == width;
}

static bool hasFloatElementType(Value value) {
  auto type = dyn_cast<RankedTensorType>(value.getType());
  return type && isa<FloatType>(type.getElementType());
}

struct Pt2eZeroPointMatch {
  tosa::CastOp roundedCast;
  tosa::ConstOp zeroPoint;
  int64_t zeroPointValue;
};

static std::optional<Pt2eZeroPointMatch> matchPt2eZeroPointAdd(tosa::AddOp add) {
  if (!hasIntegerElementWidth(add.getInput1(), 8) ||
      !hasIntegerElementWidth(add.getInput2(), 8) ||
      !hasIntegerElementWidth(add.getOutput(), 8) || !add->hasOneUse())
    return std::nullopt;

  auto wideningCast = dyn_cast<tosa::CastOp>(*add->user_begin());
  if (!wideningCast || !hasIntegerElementWidth(wideningCast.getOutput(), 32))
    return std::nullopt;

  auto matchOperands = [](Value rounded, Value zeroPoint)
      -> std::optional<Pt2eZeroPointMatch> {
    auto roundedCast = rounded.getDefiningOp<tosa::CastOp>();
    auto zeroPointConst = zeroPoint.getDefiningOp<tosa::ConstOp>();
    if (!roundedCast || !hasFloatElementType(roundedCast.getInput()) ||
        !zeroPointConst)
      return std::nullopt;

    auto values = dyn_cast<DenseElementsAttr>(zeroPointConst.getValues());
    if (!values || !values.isSplat())
      return std::nullopt;
    auto integerValue = dyn_cast<IntegerAttr>(values.getSplatValue<Attribute>());
    auto integerType =
        integerValue ? dyn_cast<IntegerType>(integerValue.getType())
                     : IntegerType{};
    if (!integerType || integerType.getWidth() != 8)
      return std::nullopt;

    return Pt2eZeroPointMatch{roundedCast, zeroPointConst,
                              integerValue.getValue().getSExtValue()};
  };

  if (auto match = matchOperands(add.getInput1(), add.getInput2()))
    return match;
  return matchOperands(add.getInput2(), add.getInput1());
}

struct LegalizePt2eTosaZeroPointPass
    : public PassWrapper<LegalizePt2eTosaZeroPointPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(
      LegalizePt2eTosaZeroPointPass)

  StringRef getArgument() const final {
    return "llm2fpga-legalize-pt2e-tosa-zero-point";
  }

  StringRef getDescription() const final {
    return "Widen recognized PT2E TOSA quantization zero-point additions to "
           "i32 and saturate to i8 with identity rescale.";
  }

  void runOnOperation() final {
    SmallVector<tosa::AddOp> additions;
    getOperation().walk(
        [&](tosa::AddOp add) { additions.push_back(add); });

    IRRewriter rewriter(getOperation().getContext());
    for (tosa::AddOp add : additions) {
      auto match = matchPt2eZeroPointAdd(add);
      if (!match)
        continue;

      auto narrowResultType = cast<RankedTensorType>(add.getOutput().getType());
      auto wideResultType =
          narrowResultType.clone(rewriter.getI32Type());
      auto narrowZeroPointType =
          cast<RankedTensorType>(match->zeroPoint.getOutput().getType());
      auto wideZeroPointType =
          narrowZeroPointType.clone(rewriter.getI32Type());

      rewriter.setInsertionPoint(add);
      auto roundedI32 = tosa::CastOp::create(
          rewriter, add.getLoc(), wideResultType,
          match->roundedCast.getInput());
      auto zeroPointValues = DenseElementsAttr::get(
          wideZeroPointType,
          rewriter.getI32IntegerAttr(match->zeroPointValue));
      auto zeroPointI32 = tosa::ConstOp::create(
          rewriter, add.getLoc(), wideZeroPointType, zeroPointValues);
      auto addedI32 = tosa::AddOp::create(
          rewriter, add.getLoc(), wideResultType, roundedI32, zeroPointI32);
      auto multiplierType = RankedTensorType::get({1}, rewriter.getI32Type());
      auto shiftType = RankedTensorType::get({1}, rewriter.getI8Type());
      auto inputZeroPointType =
          RankedTensorType::get({1}, rewriter.getI32Type());
      auto outputZeroPointType =
          RankedTensorType::get({1}, rewriter.getI8Type());
      auto multiplier = tosa::ConstOp::create(
          rewriter, add.getLoc(), multiplierType,
          DenseElementsAttr::get(multiplierType,
                                 rewriter.getI32IntegerAttr(1 << 30)));
      auto shift = tosa::ConstOp::create(
          rewriter, add.getLoc(), shiftType,
          DenseElementsAttr::get(shiftType, rewriter.getI8IntegerAttr(30)));
      auto inputZeroPoint = tosa::ConstOp::create(
          rewriter, add.getLoc(), inputZeroPointType,
          DenseElementsAttr::get(inputZeroPointType,
                                 rewriter.getI32IntegerAttr(0)));
      auto outputZeroPoint = tosa::ConstOp::create(
          rewriter, add.getLoc(), outputZeroPointType,
          DenseElementsAttr::get(outputZeroPointType,
                                 rewriter.getI8IntegerAttr(0)));
      auto narrowedI8 = tosa::RescaleOp::create(
          rewriter, add.getLoc(), narrowResultType, addedI32, multiplier,
          shift, inputZeroPoint, outputZeroPoint,
          /*scale32=*/true, /*rounding_mode=*/"SINGLE_ROUND",
          /*per_channel=*/false, /*input_unsigned=*/false,
          /*output_unsigned=*/false);

      rewriter.replaceOp(add, narrowedI8.getOutput());
    }
  }

  void getDependentDialects(DialectRegistry &registry) const final {
    registry.insert<tosa::TosaDialect>();
  }
};
} // namespace

MLIR_DECLARE_EXPLICIT_TYPE_ID(LegalizePt2eTosaZeroPointPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LegalizePt2eTosaZeroPointPass)

void registerLegalizePt2eTosaZeroPointPass() {
  PassRegistration<LegalizePt2eTosaZeroPointPass>();
}
