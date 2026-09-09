# TinyStories signed DSP policy

Before running `synth_xilinx` through its `map_dsp` stage, load:

```yosys
script fpga/synthesis/tinystories_signed_dsp_policy.ys
```

The scratchpad is process-local: apply it in every fresh synthesis invocation
that runs DSP packing. Loading this file after packing cannot repair a netlist.
It preserves DSP multiplier inference and disables register/adder packing; it
does **not** disable DSPs or change the model arithmetic, memory, or clock.

## Evidence and limits

With the installed Yosys 0.66 (`7f8fdfd8d7bc08c749a2a969388d3425d4f369d5`),
the original full-model final netlist zero-extended the 40-bit token product
and 24-bit position product. Replaying those extensions exactly reproduced
all 64 values in an early hardware embedding capture, including its 50 errors.
The unchanged model before native DSP mapping produced correct embeddings.

A source-versus-mapped simulation independently reproduced the position-product
failure: `-1 * 18141` became `0x0000000000ffb923`, rather than the signed
`0xffffffffffffb923`. DSP packing moved the lower product bits into the DSP;
the remaining sign-extension registers were subsequently optimized to zero.
The policy avoids that transformation. It is a workaround, not an upstream
Yosys repair. Removing it requires fresh synthesis equivalence evidence.

The regression uses the compiler-generated `std_fp_mult_pipe` primitive with
the same register, enable, reset and signed-product behavior. It checks real
synthesized simulation against independent signed arithmetic for every 8-bit
code across eight scales, in both 15-bit unsigned and 32-bit signed scale
configurations, including idle retention and reset. With an empty policy, the
15-bit case fails; the standalone 32-bit case already passes. Neither test is
full-model equivalence, board acceptance, or timing qualification.

Run Python inside the project Nix environment, with `iverilog` and `vvp`
available on PATH (or supplied through `IVERILOG` and `VVP`):

```sh
nix develop . -c python -m unittest discover -s tests \
  -p test_xilinx_signed_embedding_product.py -v
```

Missing tools cause explicit skips; skips are not acceptance evidence.

The first full-model candidate with this policy preserves all 18,821 named
memory, MMCM and JTAG primitive parameter sets. Final DSP count remains 163;
FDRE rises from 13,275 to 16,280 and CARRY4 from 3,979 to 4,648. Placement and
timing must be rechecked. The 30 MHz design still has incomplete BRAM/DSP timing
coverage. At the time this policy was added, no corrected board inference had
passed; three independent FPGA configurations remain required.

Detailed local evidence is archived under the ignored
`result-compiler-first-token-failed-20260909/` directory. This policy, fixture,
and diagnosis were developed with LLM assistance; no kev-gpt RTL was copied.
