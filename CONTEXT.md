# LLM2FPGA project language

This glossary defines the project terms used when discussing the compiler,
reference accelerator, and validation scope.

## Terms

**Working notes**: The evolving record of project reasoning, evidence,
decisions, open questions, and next actions. It supplements the formal project
plan and does not change its scope by itself.

**Reference implementation**: A working implementation used to define
observable behavior and validation requirements; it is not automatically the
project’s submitted implementation.

**TinyStories backend**: The compiler backend that lowers configurations in the
ordinary TinyStories family. Arbitrary PyTorch models are outside the current
backend scope.

**Behavioral golden reference**: The frozen model, inputs, outputs, and
observable checkpoints used to judge functional equivalence.

**Exact executable model**: The model structure, package, tokenizer,
quantization, arithmetic semantics, and token-selection behavior whose
execution is compared across reference, compiler, RTL, and hardware.
_Avoid_: Same checkpoint, same model name

**Authenticated compiler input**: An exported program whose complete identity
and observable behavior are proven to match the exact executable model before
compiler lowering begins.
_Avoid_: Reconstructed FP32 model

**Compiler frontier**: The earliest pipeline boundary that cannot produce a
valid artifact or preserve the authenticated compiler input's behavior.
_Avoid_: Final error, downstream failure

**Resource baseline**: Measured implementation data used to compare area,
timing, memory, and throughput; it is not itself a functional specification.

**Contract slice**: A minimal compiler graph cut derived from the exact
executable model, retaining its real tensor shapes, quantization constants,
and observable checkpoints. It is the functional acceptance target for a
vertical-slice milestone.

**Micro-fixture**: A deliberately smaller instance of a contract slice used
for fast compiler and RTL iteration. It cannot by itself establish exact-model
support; it must be paired with a passing contract slice.

**Contract pass**: A project-owned, narrowly scoped compiler pass that
preserves or lowers an exact executable-model semantic contract. Established
upstream passes may be used as utilities, but they do not substitute for a
contract pass at a contract-critical transformation.

**Fixed-point SSA IR**: The project-owned `llm2fpga.fixed` intermediate
representation that carries exact fixed-point values and their dataflow between
contract operations. It is lowered to Calyx only after arithmetic, lookup,
requantization, and storage/control semantics have been made explicit.

**Fixed-point contract operation**: A semantic `llm2fpga.fixed` operation
whose attributes fully specify exact arithmetic behavior. For example,
`fixed.requantize` records scale, rounding, signedness, saturation, and result
width; its lowerer must implement those recorded primitive semantics exactly.

**Fixed-point schema**: The initial representation of `llm2fpga.fixed` using
existing MLIR operations and project-owned attributes, verified and transformed
by an out-of-tree plugin. It avoids a CIRCT rebuild while the contract evolves;
the schema may later become a compiled dialect without changing semantics.

**Logical fixed-point value**: An SSA value in the fixed-point schema that
denotes exact arithmetic dataflow without committing to a physical memory,
port, or lifetime. Storage assignment is a separate lowering decision.

**Vertical-slice acceptance gate**: The mandatory pair of proofs before a
contract slice may expand: bit-exact output tensors and per-stage hashes match
the frozen checkpoint, and the generated-Calyx ordered-value trace matches the
same checkpoint.

**Captured contract fixture**: A frozen tensor checkpoint captured at a named
boundary of the exact executable model during the frozen prompt run. It is the
primary input/output fixture for a contract slice; synthetic tensors are only
supplementary edge cases.
