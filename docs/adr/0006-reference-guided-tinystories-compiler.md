---
status: accepted
---

# Use kev-gpt as a behavioral reference for a TinyStories-specific compiler backend

The project will finish Tasks 4–6 through the compiler-pipeline architecture,
but will scope the current backend to the ordinary TinyStories family (1M, 3M,
8M, 28M, and 33M), rather than arbitrary PyTorch models. The working
kev-gpt-derived accelerator is a behavioral and high-level architectural
reference—not source to copy into compiler output or submitted RTL. The
independently maintained implementation must reproduce the frozen reference
model’s exact 16-token FPGA output across three cold starts. DDR3 integration and
larger-model support are deferred while integrated UberDDR3 remains unreliable.
Existing LLM-assisted history is preserved and disclosed; new work is
provenance-tracked and NLnet guidance is requested before reference-derived
artifacts are treated as funded deliverables.
