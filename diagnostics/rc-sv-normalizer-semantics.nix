{ pkgs }:

pkgs.runCommand "tinystories-w8a8-rc-sv-normalizer-semantics" {
  nativeBuildInputs = [ pkgs.python3 pkgs.iverilog ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  ${pkgs.python3}/bin/python3 - ${../scripts/pipeline/run_rc_sv_equivalence.py} "$out" <<'PY'
import importlib.util
import json
import pathlib
import sys

runner_path = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("rc_runner", runner_path)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

terms = 2000
ternary = " : ".join(
    f"cond[{index}] ? 13'd{index % 8192}" for index in range(terms)
) + " : 13'd0"
or_expression = " | ".join(f"cond[{index}]" for index in range(terms))
raw = f'''module candidate_raw(
  input logic [{terms - 1}:0] cond,
  output logic [12:0] ternary_out,
  output logic or_out
);
  logic [12:0] state;
  logic enable;
  assign state = {ternary};
  assign enable = {or_expression};
  assign ternary_out = state;
  assign or_out = enable;
endmodule
'''
normalized = runner._normalize_large_or_assignments(raw)
if "always_comb" in normalized:
    raise SystemExit("normalizer emitted procedural logic")
if normalized == raw:
    raise SystemExit("normalizer did not page the generated source")
normalized = normalized.replace("module candidate_raw", "module candidate_normalized", 1)
(out / "candidate_raw.sv").write_text(raw, encoding="utf-8")
(out / "candidate_normalized.sv").write_text(normalized, encoding="utf-8")
(out / "normalization.json").write_text(json.dumps({
    "raw_bytes": len(raw),
    "normalized_bytes": len(normalized),
    "normalizer_page_terms": runner.NORMALIZER_PAGE_TERMS,
    "generated_page_wires": normalized.count("__llm2fpga_sim_"),
}, sort_keys=True) + "\n", encoding="utf-8")
(out / "tb.sv").write_text(f'''module tb;
  logic [{terms - 1}:0] cond;
  wire [12:0] raw_ternary_out, normalized_ternary_out;
  wire raw_or_out, normalized_or_out;
  candidate_raw raw(
    .cond(cond), .ternary_out(raw_ternary_out), .or_out(raw_or_out));
  candidate_normalized normalized(
    .cond(cond), .ternary_out(normalized_ternary_out), .or_out(normalized_or_out));

  task check_equal;
    begin
      #1;
      if (raw_ternary_out !== normalized_ternary_out || raw_or_out !== normalized_or_out) begin
        $display("MISMATCH raw_state=%b normalized_state=%b raw_or=%b normalized_or=%b",
                 raw_ternary_out, normalized_ternary_out, raw_or_out, normalized_or_out);
        $fatal(1, "normalization changed four-state behavior");
      end
    end
  endtask

  initial begin
    cond = '0;
    check_equal();
    cond = '0;
    cond[0] = 1'bx;
    cond[127] = 1'bz;
    cond[128] = 1'b1;
    cond[511] = 1'bx;
    check_equal();
    cond = '0;
    cond[0] = 1'bz;
    cond[127] = 1'bx;
    cond[128] = 1'bz;
    cond[129] = 1'b1;
    cond[1023] = 1'bx;
    check_equal();
    cond = '1;
    cond[0] = 1'bx;
    cond[127] = 1'bz;
    cond[128] = 1'bx;
    check_equal();
    $display("NORMALIZER_SEMANTICS_PASS");
    $finish;
  end
endmodule
''', encoding="utf-8")
PY
  ${pkgs.iverilog}/bin/iverilog -g2012 -s tb -o "$out/tb.vvp" \
    "$out/candidate_raw.sv" "$out/candidate_normalized.sv" "$out/tb.sv"
  ${pkgs.iverilog}/bin/vvp "$out/tb.vvp" > "$out/simulator.log"
  ${pkgs.python3}/bin/python3 - "$out" <<'PY'
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
log = (out / "simulator.log").read_text(encoding="utf-8")
if "NORMALIZER_SEMANTICS_PASS" not in log:
    raise SystemExit("normalizer selftest did not report success")
result = json.loads((out / "normalization.json").read_text(encoding="utf-8"))
result["status"] = "pass"
result["simulator"] = "iverilog-four-state"
(out / "summary.json").write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
PY
''
