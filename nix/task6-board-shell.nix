{ pkgs }:
let
  pins = builtins.fromJSON (builtins.readFile ../scripts/pipeline/task6_board_shell_pins.json);
  storeInputs = map (row: builtins.storePath
    ("/nix/store/" + builtins.elemAt (pkgs.lib.splitString "/" row.source) 3))
    (builtins.filter (row: pkgs.lib.hasPrefix "/nix/store/" row.source) pins.sources);
  sourceClosure = pkgs.runCommand "task6-board-shell-source-closure" {
    nativeBuildInputs = [ pkgs.python3 ];
    pinnedInputs = storeInputs;
  } ''
    mkdir -p scripts/pipeline third_party
    cp ${../scripts/pipeline/materialize_task6_board_shell.py} scripts/pipeline/materialize_task6_board_shell.py
    cp ${../scripts/pipeline/task6_board_shell_pins.json} scripts/pipeline/task6_board_shell_pins.json
    cp -r ${../third_party/task6-e368449} third_party/task6-e368449
    python3 scripts/pipeline/materialize_task6_board_shell.py --out "$out"
  '';
  sources = builtins.filter (row: pkgs.lib.hasSuffix ".sv" row.logical_path ||
    pkgs.lib.hasSuffix ".v" row.logical_path) pins.sources;
  sourceArgs = pkgs.lib.concatMapStringsSep " "
    (row: "${sourceClosure}/${row.logical_path}") sources;
  yosys = builtins.storePath "/nix/store/1g0dvnvw75fnlnk4ad586c65wfxbf5rs-yosys-with-plugins-0.66";
  replaySynthesis = pkgs.runCommand "compiler-ddr3-trace-replay-synthesis-screen" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    cat > run.ys <<EOF
    read_verilog -lib +/xilinx/cells_sim.v
    read_verilog -lib +/xilinx/cells_xtra.v
    read_verilog -sv -DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS -DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS -DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS ${sourceArgs} ${../rtl/diagnostics/compiler_ddr3_trace_replay.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_csr.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_top.sv}
    hierarchy -check -top compiler_ddr3_trace_replay_top
    synth_xilinx -flatten -arch xc7 -nosrl -noiopad -top compiler_ddr3_trace_replay_top
    check
    stat -top compiler_ddr3_trace_replay_top
    write_json $out/replay.json
    EOF
    # Screen only. Bound wall time and per-file output; no bitstream is built.
    ulimit -f 180000
    timeout 600 ${yosys}/bin/yosys -Q -s run.ys > "$out/yosys.log" 2>&1
    python3 ${../scripts/analysis/check_compiler_shell_status.py} \
      "$out/yosys.log" --top compiler_ddr3_trace_replay_top
    cp run.ys "$out/"
  '';
in { inherit sourceClosure replaySynthesis; }
