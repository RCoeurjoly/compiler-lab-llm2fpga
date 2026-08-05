# Build an evidence-gated closed-loop optimizer before agentic search

The first closed-loop implementation is deterministic infrastructure: a manifest-defined, one-change candidate; an isolated executor; immutable equivalence and performance receipts; a scorer; and a durable experiment ledger. Candidate selection is initially rule-based. Only after baseline evidence exists may an LLM propose candidates within the explicit whitelist.

The canonical oracle, liveness/equivalence gates, DDR3 map, board constraints, and search whitelist are not mutable by the loop. Candidates rank lexicographically: exact functional and liveness acceptance first, then the applicable implementation gate, then trusted-result wall time, then resource slack. Every candidate, including mismatch, timeout, and OOM results, is retained in the ledger. Expanding the search space or altering protected evidence requires explicit user approval.
