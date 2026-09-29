{ pkgs, yosys, synthesis, fsmCheck }:
let
  map = ../rtl/memory/xc7_ram64_compat.v;
  fixture = ../tests/rtl/ram64_compat_formal.sv;
  script = ''
    read_verilog -formal +/xilinx/cells_sim.v
    read_verilog -formal ${fixture}
    @PARAMETERS@
    copy gold gate
    techmap -map ${map} gate
    select -assert-count 1 gate/t:RAM64X1D
    select -assert-count 1 gold/t:RAM64X1S
    @FAULT@
    hierarchy -check
    flatten -wb gold gate
    proc gold gate
    memory_map gold gate
    opt gold gate
    design -save prepared
    equiv_make -make_assert gold gate base
    hierarchy -top base
    sat -seq 2 -prove-asserts -verify
    design -load prepared
    equiv_make gold gate equiv
    hierarchy -top equiv
    equiv_simple
    equiv_induct -seq 2
    equiv_status -assert
  '';
  makeScript = parameters: fault: pkgs.writeText "ram64-proof.ys"
    (builtins.replaceStrings [ "@PARAMETERS@" "@FAULT@" ] [ parameters fault ] script);
  cases = {
    zero-normal = "chparam -set INIT 64'h0 -set IS_WCLK_INVERTED 0 gold";
    zero-inverted = "chparam -set INIT 64'h0 -set IS_WCLK_INVERTED 1 gold";
    pattern-normal = "chparam -set INIT 64'hd39a7ce5126b804f -set IS_WCLK_INVERTED 0 gold";
    pattern-inverted = "chparam -set INIT 64'hd39a7ce5126b804f -set IS_WCLK_INVERTED 1 gold";
  };
  negative = makeScript "" "cd gate; connect -port ram WE 1'0; cd ..";
  proof = pkgs.runCommand "compiler-full16-ram64-initialized-induction-proof" { } ''
    set -euo pipefail
    ulimit -v 8388608
    ulimit -c 0
    mkdir -p "$out"
    ${pkgs.lib.concatStringsSep "\n" (pkgs.lib.mapAttrsToList (name: parameters:
      let file = makeScript parameters ""; in ''
        timeout --kill-after=5s 90 ${yosys}/bin/yosys -Q -s ${file} > "$out/${name}.log" 2>&1
        cp ${file} "$out/${name}.ys"
      '') cases)}
    set +e
    timeout --kill-after=5s 90 ${yosys}/bin/yosys -Q -s ${negative} > "$out/negative.log" 2>&1
    status=$?
    set -e
    test "$status" -eq 1
    # This marker distinguishes a native counterexample from a parser error.
    grep -q 'ERROR: Called with -verify and proof did fail!' "$out/negative.log"
    cp ${negative} "$out/negative.ys"
    printf '%s\n' 'Initialized SAT base and complete-state induction passed in four cases; disabled-write counterexample rejected. Logical primitive proof, not timing or board qualification.' > "$out/scope.txt"
  '';
  compatible = pkgs.runCommand "compiler-full16-ddr3-board-compatible-synthesis" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    set -euo pipefail
    ulimit -v 8388608
    ulimit -c 0
    ulimit -f 400000
    mkdir -p "$out"
    # A successful primitive proof is mandatory, not optional diagnostic data.
    cp -r ${proof} "$out/primitive-proof"
    cp -r ${fsmCheck} "$out/fsm-encoding-check"
    timeout --kill-after=5s 120 ${yosys}/bin/yosys -Q -p '
      read_json ${synthesis}/replay.json;
      read_verilog -lib +/xilinx/cells_sim.v;
      techmap -map ${map};
      select -assert-none */t:RAM64X1S */t:RAM128X1S;
      select =*;
      proc;
      select -clear;
      hierarchy -top compiler_ddr3_trace_replay_top -purge_lib;
      write_json '"$out"'/replay.json;
    ' 2>&1 | tee "$out/yosys.log"
    python3 ${../scripts/analysis/verify_full16_dram_compat.py} \
      ${synthesis}/replay.json "$out/replay.json" > "$out/graph-audit.log"
    FULL16_RAW_JSON=${synthesis}/replay.json FULL16_MAPPED_JSON="$out/replay.json" \
      FULL16_AUDIT=${../scripts/analysis/verify_full16_dram_compat.py} \
      python3 ${../tests/test_full16_dram_compat_audit.py} > "$out/audit-controls.log" 2>&1
    cp ${map} "$out/dram-compat-map.v"
    ln -s ${synthesis} "$out/raw-synthesis"
  '';
in { inherit proof compatible; }
