# Direct source closure is independent of Morty

The active equivalence route supplies Verilator with an explicit raw-SV source closure and does not invoke, compare against, or depend on Morty. Existing bundled artifacts remain historical records only; confidence in the new route comes from the frozen PyTorch equivalence gates rather than from bundle byte or behavioral parity.

If simulator compatibility requires normalization, it is a named deterministic transformation with recorded input and output hashes, a narrow documented purpose, and an independent focused test. A substantive RTL transformation is instead an optimization branch and must pass the full canonical equivalence gate.
