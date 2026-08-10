# Interface-scoped behavioral seed RTL

EQY optimization will compare candidate RTL against a behavioral seed RTL only at an explicit architectural contract: clock/reset, input protocol, output protocol, and externally visible memory transactions. Internal hierarchy, state encoding, pipeline structure, and scratch layout remain outside the contract so RTL optimization does not become tied to the first compiler-produced implementation; PyTorch equivalence remains a separate gate for qualifying the seed and promoted candidates.

The seed qualification bar is the one-input smoke gate plus the frozen-four gate, with reset-isolation evidence and semantic-checkpoint agreement. Broader 24-context and 64-context campaigns remain required for stronger confidence, but do not delay establishing the EQY workflow.

The first EQY milestone uses deterministic abstract synchronous memories and verifies UberDDR3/vendor-memory transport separately against the same memory contract. This keeps compute optimization independent of the DDR3 controller's formal state space.

## Considered options

- Treat the complete seed RTL structure as the EQY contract. Rejected because it would unnecessarily lock optimization to compiler artifacts.
- Use only top-level input/output values and ignore memory behavior. Rejected because DDR3-backed designs expose meaningful transaction ordering and latency assumptions at the memory boundary.
