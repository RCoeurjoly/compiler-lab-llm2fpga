#include "torch-mlir/Dialect/Torch/IR/TorchTypes.h"

#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/OperationSupport.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Tools/Plugins/PassPlugin.h"

#include "llvm/ADT/SmallVector.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Config/llvm-config.h"

#include <optional>
#include <string>

using namespace mlir;

namespace {
constexpr llvm::StringLiteral kRawOperator = "torch.operator";
constexpr llvm::StringLiteral kExactOperator =
    "torch.llm2fpga.serial_gemv";
constexpr llvm::StringLiteral kCompilerOperator = "llm2fpga.serial_gemv";
constexpr llvm::StringLiteral kContractDiagnostic =
    "exact_serial_gemv_contract";

struct ParsedTensorType {
  SmallVector<int64_t, 2> shape;
};

static std::optional<ParsedTensorType> parseStaticSi64ValueTensor(Type type) {
  std::string storage;
  llvm::raw_string_ostream stream(storage);
  type.print(stream);
  stream.flush();

  llvm::StringRef text(storage);
  constexpr llvm::StringLiteral prefix = "!torch.vtensor<";
  if (!text.consume_front(prefix) || !text.consume_back(">") ||
      !text.consume_front("[") || text.starts_with("*"))
    return std::nullopt;

  auto [dimensions, dtype] = text.split("]");
  if (!dtype.consume_front(",") || dtype.trim() != "si64")
    return std::nullopt;

  ParsedTensorType parsed;
  SmallVector<llvm::StringRef, 4> pieces;
  dimensions.split(pieces, ',', -1, false);
  for (llvm::StringRef piece : pieces) {
    piece = piece.trim();
    int64_t dimension = 0;
    if (piece.empty() || piece == "?" || piece.getAsInteger(10, dimension) ||
        dimension <= 0)
      return std::nullopt;
    parsed.shape.push_back(dimension);
  }
  return parsed;
}

static void emitContractError(Operation *op, llvm::StringRef detail) {
  op->emitError() << kContractDiagnostic << ":" << detail;
}

struct LegalizeExactSerialGemvPass
    : public PassWrapper<LegalizeExactSerialGemvPass,
                         OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LegalizeExactSerialGemvPass)

  llvm::StringRef getArgument() const final {
    return "llm2fpga-legalize-exact-serial-gemv";
  }

  llvm::StringRef getDescription() const final {
    return "Convert the exact raw TinyStories signed-i64 serial-GEMV boundary "
           "to a compiler-owned descriptor.";
  }

  void runOnOperation() final {
    SmallVector<Operation *> rawOperators;
    getOperation().walk([&](Operation *op) {
      if (op->getName().getStringRef() == kRawOperator)
        rawOperators.push_back(op);
    });

    for (Operation *op : rawOperators) {
      auto name = op->getAttrOfType<StringAttr>("name");
      if (name && name.getValue().starts_with("torch.aten."))
        continue;
      if (!name || name.getValue() != kExactOperator) {
        emitContractError(op, "unknown_custom_operator");
        signalPassFailure();
        return;
      }
      if (op->getNumOperands() != 2 || op->getNumResults() != 1 ||
          op->getNumRegions() != 0) {
        emitContractError(op, "invalid_arity");
        signalPassFailure();
        return;
      }

      auto input = parseStaticSi64ValueTensor(op->getOperand(0).getType());
      auto weights = parseStaticSi64ValueTensor(op->getOperand(1).getType());
      auto result = parseStaticSi64ValueTensor(op->getResult(0).getType());
      if (!input || !weights || !result) {
        emitContractError(op, "requires_static_rank2_si64");
        signalPassFailure();
        return;
      }
      if (input->shape.size() != 2 || weights->shape.size() != 2 ||
          result->shape.size() != 2) {
        emitContractError(op, "requires_static_rank2_si64");
        signalPassFailure();
        return;
      }

      int64_t rows = input->shape[0];
      int64_t inputs = input->shape[1];
      int64_t outputs = weights->shape[0];
      if (weights->shape[1] != inputs || result->shape[0] != rows ||
          result->shape[1] != outputs) {
        emitContractError(op, "shape_mismatch");
        signalPassFailure();
        return;
      }

      OpBuilder builder(op);
      auto inputType =
          RankedTensorType::get(input->shape, builder.getI64Type());
      auto weightType =
          RankedTensorType::get(weights->shape, builder.getI64Type());
      auto resultType =
          RankedTensorType::get(result->shape, builder.getI64Type());

      OperationState inputBridgeState(op->getLoc(),
                                      "torch_c.to_builtin_tensor");
      inputBridgeState.addOperands(op->getOperand(0));
      inputBridgeState.addTypes(inputType);
      Operation *inputBridge = builder.create(inputBridgeState);

      OperationState weightBridgeState(op->getLoc(),
                                       "torch_c.to_builtin_tensor");
      weightBridgeState.addOperands(op->getOperand(1));
      weightBridgeState.addTypes(weightType);
      Operation *weightBridge = builder.create(weightBridgeState);

      OperationState gemvState(op->getLoc(), kCompilerOperator);
      gemvState.addOperands(
          {inputBridge->getResult(0), weightBridge->getResult(0)});
      gemvState.addTypes(resultType);
      gemvState.addAttribute("rows", builder.getI64IntegerAttr(rows));
      gemvState.addAttribute("outputs", builder.getI64IntegerAttr(outputs));
      gemvState.addAttribute("inputs", builder.getI64IntegerAttr(inputs));
      gemvState.addAttribute("mac_order",
                             builder.getStringAttr("ascending_i64_wrap"));
      Operation *gemv = builder.create(gemvState);

      OperationState resultBridgeState(op->getLoc(),
                                       "torch_c.from_builtin_tensor");
      resultBridgeState.addOperands(gemv->getResult(0));
      resultBridgeState.addTypes(op->getResult(0).getType());
      Operation *resultBridge = builder.create(resultBridgeState);

      op->getResult(0).replaceAllUsesWith(resultBridge->getResult(0));
      op->erase();
    }
  }
};
} // namespace

MLIR_DECLARE_EXPLICIT_TYPE_ID(LegalizeExactSerialGemvPass)
MLIR_DEFINE_EXPLICIT_TYPE_ID(LegalizeExactSerialGemvPass)

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo mlirGetPassPluginInfo() {
  return {MLIR_PLUGIN_API_VERSION, "LLM2FPGATorchMLIRPasses",
          LLVM_VERSION_STRING,
          []() { PassRegistration<LegalizeExactSerialGemvPass>(); }};
}
