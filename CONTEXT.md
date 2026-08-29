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

**Resource baseline**: Measured implementation data used to compare area,
timing, memory, and throughput; it is not itself a functional specification.
