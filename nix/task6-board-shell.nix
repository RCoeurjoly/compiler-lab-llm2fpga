{ pkgs, bitstreamPkgs ? pkgs, openXC7Packages ? null }:
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
  commandSourceClosure = pkgs.runCommand "task6-board-shell-command-stage-closure" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    cp -r ${sourceClosure} "$out"
    chmod -R u+w "$out"
    mkdir -p scripts/pipeline rtl/diagnostics
    cp ${../scripts/pipeline/apply_task6_command_overlay.py} scripts/pipeline/apply_task6_command_overlay.py
    cp ${../scripts/pipeline/task6_command_overlay_pins.json} scripts/pipeline/task6_command_overlay_pins.json
    cp ${../rtl/diagnostics/task6_normal_command_stage.sv} rtl/diagnostics/task6_normal_command_stage.sv
    python3 scripts/pipeline/apply_task6_command_overlay.py --closure "$out"
    cp rtl/diagnostics/task6_normal_command_stage.sv "$out/"
  '';
  m2SourceClosure = pkgs.runCommand "task6-board-shell-m2-production-source-closure" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    cp -r ${commandSourceClosure} "$out"
    chmod -R u+w "$out"
    mkdir -p scripts/pipeline
    cp ${../scripts/pipeline/apply_task6_m2_banking_overlay.py} scripts/pipeline/apply_task6_m2_banking_overlay.py
    cp ${../scripts/pipeline/task6_m2_banking_overlay_pins.json} scripts/pipeline/task6_m2_banking_overlay_pins.json
    python3 scripts/pipeline/apply_task6_m2_banking_overlay.py --closure "$out"
  '';
  replayObserverSourceClosure = pkgs.runCommand "task6-board-shell-replay-pcie-cfg-observer-source-closure" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    cp -r ${m2SourceClosure} "$out"
    chmod -R u+w "$out"
    mkdir -p scripts/pipeline
    cp ${../scripts/pipeline/apply_task6_pcie_cfg_observer_overlay.py} scripts/pipeline/apply_task6_pcie_cfg_observer_overlay.py
    cp ${../scripts/pipeline/task6_pcie_cfg_observer_overlay_pins.json} scripts/pipeline/task6_pcie_cfg_observer_overlay_pins.json
    python3 scripts/pipeline/apply_task6_pcie_cfg_observer_overlay.py --closure "$out"
  '';
  sources = builtins.filter (row: pkgs.lib.hasSuffix ".sv" row.logical_path ||
    pkgs.lib.hasSuffix ".v" row.logical_path) pins.sources;
  sourceArgs = pkgs.lib.concatMapStringsSep " "
    (row: "${replayObserverSourceClosure}/${row.logical_path}") sources;
  # The production implementation screen must include the actual
  # compiler-generated accelerator and its transport-neutral DDR3 boundary.
  # Keeping these paths explicit makes it impossible for the derivation to
  # silently fall back to the trace-replay-only shell.
  compilerAnnotatedSource = pkgs.runCommand "compiler-generated-model-lutram-annotated" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    python3 ${../scripts/pipeline/annotate_compiler_lutram.py} \
      ${../.superpowers/sdd/2026-09-18-compiler-micron-integration/task-4-recovered-inputs/model.sv} \
      "$out/model.sv" "$out/annotation.json"
  '';
  compilerSourceArgs = pkgs.lib.concatStringsSep " " [
    "${compilerAnnotatedSource}/model.sv"
    "${../rtl/memory/llm_external_memory_arbiter.sv}"
    "${../rtl/memory/llm_wishbone_pipeline.sv}"
    "${../rtl/tinystories_1m_ddr3_backend.sv}"
    "${../rtl/tinystories_1m_ddr3_command_adapter.sv}"
  ];
  yosys = builtins.storePath "/nix/store/1g0dvnvw75fnlnk4ad586c65wfxbf5rs-yosys-with-plugins-0.66";
  # Fast feedback target for the same production source closure.  This keeps
  # hierarchy/elaboration failures separate from the much slower global
  # synthesis screen and emits a reusable parameterized RTLIL checkpoint.
  replayElaboration = pkgs.runCommand "compiler-ddr3-trace-replay-elaboration" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    cat > run.ys <<EOF
    read_verilog -lib +/xilinx/cells_sim.v
    read_verilog -lib +/xilinx/cells_xtra.v
    read_verilog -sv -DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS -DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS -DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS ${sourceArgs} ${compilerSourceArgs} ${m2SourceClosure}/task6_normal_command_stage.sv ${../rtl/diagnostics/compiler_ddr3_trace_replay.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_csr.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_top.sv}
    chparam -set ENABLE_COMPILER_ACCELERATOR 1 compiler_ddr3_trace_replay_top
    hierarchy -check -top compiler_ddr3_trace_replay_top
    proc
    opt_clean
    check
    write_rtlil $out/compiler-top.il
    EOF
    timeout 120 ${yosys}/bin/yosys -Q -s run.ys > "$out/yosys.log" 2>&1
    test -s "$out/compiler-top.il"
    grep -q 'Checking module compiler_ddr3_trace_replay_top' "$out/yosys.log"
    cp run.ys "$out/"
  '';
  replaySynthesis = pkgs.runCommand "compiler-ddr3-trace-replay-synthesis-screen" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    cat > run.ys <<EOF
    read_verilog -lib +/xilinx/cells_sim.v
    read_verilog -lib +/xilinx/cells_xtra.v
    read_verilog -sv -DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS -DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS -DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS ${sourceArgs} ${compilerSourceArgs} ${m2SourceClosure}/task6_normal_command_stage.sv ${../rtl/diagnostics/compiler_ddr3_trace_replay.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_csr.sv} ${../rtl/diagnostics/compiler_ddr3_trace_replay_top.sv}
    chparam -set ENABLE_COMPILER_ACCELERATOR 1 compiler_ddr3_trace_replay_top
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
  # Route the current compiler-generated top, not a historical synthesis JSON.
  # A pinned netlist can silently discard RTL integration fixes (and was the
  # reason the previous replay bitstream did not contain the current PCIe
  # bridge).  The synthesis screen remains bounded and is now the provenance
  # source for every replay bitstream.
  replayTimingBaseline = replaySynthesis;
  replayResetPatched = pkgs.runCommand "compiler-ddr3-trace-replay-reset-patched" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    python3 ${../scripts/pipeline/patch_replay_pcie_reset_netlist.py} \
      ${replayTimingBaseline}/replay.json "$out/replay.json" "$out/patch-receipt.json"
  '';
  # The current synthesis has already eliminated the absolute BAR high bits;
  # applying the historical bit-disconnect patch would be both unnecessary and
  # unauthenticated.  Preserve the reset-patch receipt as the route input.
  replayBarOffsetPatched = replayResetPatched;
  replayBarObserverResetPatched = pkgs.runCommand "compiler-ddr3-trace-replay-bar-observer-reset-patched" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    REPLAY_RESET_PATCH_TOOL=${../scripts/pipeline/patch_replay_pcie_reset_netlist.py} \
      python3 ${../scripts/pipeline/patch_replay_pcie_bar_probe_netlist.py} \
      ${replayTimingBaseline}/replay.json "$out/replay.json" "$out/patch-receipt.json"
  '';
  # Exact Task 3R executable/chipdb; route the production serialization once.
  nextpnr = builtins.storePath "/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2";
  chipdb = builtins.storePath "/nix/store/8s95bdz7d69facix9k7h99dfw2chah45-nextpnr-xilinx-chipdb-0.8.2";
  replayRoute = pkgs.runCommand "compiler-ddr3-trace-replay-route" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    ulimit -c 0
    ulimit -f 400000
    test -s ${replayBarOffsetPatched}/patch-receipt.json
    echo '25c434b7614ade7cbdd448b4f993d1feced26296b0164f6e648ddaced7ebac16  ${nextpnr}/bin/nextpnr-xilinx' | sha256sum -c -
    echo 'd8472bfcc19dc31686d80cc34f0d37b958c268656182537b06b3439711b105f1  ${chipdb}/xc7k480tffg1156.bin' | sha256sum -c -
    echo '890ebb9d0fc854c8595d3e9e67b4a4074fe42ac7682680b9c33dd1d2c8662f57  ${m2SourceClosure}/constraints/board.xdc' | sha256sum -c -
    echo '42acd411f3e34ac494e56f64b12c0de81394b567d5087c1213b820040fa9d698  ${m2SourceClosure}/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py' | sha256sum -c -
    timeout --signal=TERM --kill-after=10s 1200 ${nextpnr}/bin/nextpnr-xilinx \
      --chipdb ${chipdb}/xc7k480tffg1156.bin \
      --xdc ${m2SourceClosure}/constraints/board.xdc \
      --json ${replayBarOffsetPatched}/replay.json \
      --pre-pack ${m2SourceClosure}/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py \
      --pre-place ${../scripts/pipeline/replay_pcie_clock_topology.py} \
      --seed 15 --placer-budgets --timing-allow-fail --fasm "$out/replay.fasm" \
      2>&1 | tee "$out/route.log"
    python3 ${../scripts/analysis/check_compiler_replay_route.py} "$out/route.log" "$out/route.json"
    sha256sum "$out/replay.fasm" > "$out/replay.fasm.sha256"
  '';
  replayBarObserverRoute = pkgs.runCommand "compiler-ddr3-trace-replay-bar-observer-route" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    mkdir -p "$out"
    ulimit -c 0
    ulimit -f 400000
    test -s ${replayResetPatched}/patch-receipt.json
    echo '25c434b7614ade7cbdd448b4f993d1feced26296b0164f6e648ddaced7ebac16  ${nextpnr}/bin/nextpnr-xilinx' | sha256sum -c -
    echo 'd8472bfcc19dc31686d80cc34f0d37b958c268656182537b06b3439711b105f1  ${chipdb}/xc7k480tffg1156.bin' | sha256sum -c -
    echo '890ebb9d0fc854c8595d3e9e67b4a4074fe42ac7682680b9c33dd1d2c8662f57  ${m2SourceClosure}/constraints/board.xdc' | sha256sum -c -
    echo '42acd411f3e34ac494e56f64b12c0de81394b567d5087c1213b820040fa9d698  ${m2SourceClosure}/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py' | sha256sum -c -
    timeout --signal=TERM --kill-after=10s 1200 ${nextpnr}/bin/nextpnr-xilinx \
      --chipdb ${chipdb}/xc7k480tffg1156.bin \
      --xdc ${m2SourceClosure}/constraints/board.xdc \
      --json ${replayResetPatched}/replay.json \
      --pre-pack ${m2SourceClosure}/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py \
      --pre-place ${../scripts/pipeline/replay_pcie_clock_topology.py} \
      --pre-route ${../scripts/pipeline/replay_pcie_bar_probe_pre_route.py} \
      --seed 15 --placer-budgets --timing-allow-fail --fasm "$out/replay.fasm" \
      2>&1 | tee "$out/route.log"
    python3 ${../scripts/analysis/check_compiler_replay_route.py} "$out/route.log" "$out/route.json"
    grep -q 'TASK4_BAR_PROBE_PRE_ROUTE_PASS consumers=14' "$out/route.log"
    cp ${replayResetPatched}/patch-receipt.json "$out/reset-patch-receipt.json"
    sha256sum "$out/replay.fasm" > "$out/replay.fasm.sha256"
  '';
  prjxray = openXC7Packages.prjxray;
  fasm = openXC7Packages.fasm;
  pythonDeps = bitstreamPkgs.python312.withPackages (ps: [
    ps.pyyaml ps.simplejson ps.intervaltree ps.pyjson5 ps.progressbar2
  ]);
  patchedDb = pkgs.runCommand "compiler-replay-prjxray-db-lioi3-compat" {
    nativeBuildInputs = [ pkgs.patch ];
  } ''
    original=${nextpnr}/share/nextpnr/external/prjxray-db
    echo "d74bb512c56af57510ce89b351f1bf666e96196e20c8b1bc18e8521fe45bdd61  $original/kintex7/segbits_lioi3_tbytesrc.db" | sha256sum -c -
    echo '197e2f126a6f3917c1ceca62394acd957397679538df077f7119de97c28e05bc  ${../patches/prjxray-db/0001-kintex7-add-lioi3-tbytesrc-oclkm-imux31.patch}' | sha256sum -c -
    # Symlink unchanged data to conserve disk; replace only our generated link.
    cp -rs "$original" "$out"
    chmod u+w "$out/kintex7"
    cp --remove-destination "$original/kintex7/segbits_lioi3_tbytesrc.db" "$out/kintex7/segbits_lioi3_tbytesrc.db"
    chmod u+w "$out/kintex7/segbits_lioi3_tbytesrc.db"
    cd "$out"
    patch --no-backup-if-mismatch -p1 < ${../patches/prjxray-db/0001-kintex7-add-lioi3-tbytesrc-oclkm-imux31.patch}
    echo '7108c7c92097d591e404852ce5eb18a6ed1851352d399eb29c1bd7eed3ffd710  kintex7/segbits_lioi3_tbytesrc.db' | sha256sum -c -
  '';
  dbRoot = "${patchedDb}/kintex7";
  replayBitstream = pkgs.runCommand "compiler-ddr3-trace-replay-bitstream" {
    nativeBuildInputs = [ fasm prjxray pythonDeps ];
  } ''
    mkdir -p "$out"
    export PYTHONPATH="${fasm}/lib/python3.12/site-packages:${pythonDeps}/${bitstreamPkgs.python312.sitePackages}:${prjxray}/usr/share/python3"
    export PRJXRAY_PYTHON_DIR="${prjxray}/usr/share/python3"
    export PRJXRAY_DB_DIR="${dbRoot}"
    timeout --kill-after=10s 600 bash ${../scripts/pipeline/build_and_validate_xc7_bitstream.sh} \
      ${replayRoute}/replay.fasm "$out/replay.bit" "$out/replay.frames" \
      ${dbRoot} ${dbRoot}/xc7k480tffg1156-1/part.yaml
    sha256sum "$out/replay.bit" > "$out/replay.bit.sha256"
  '';
  replayBarObserverBitstream = pkgs.runCommand "compiler-ddr3-trace-replay-bar-observer-bitstream" {
    nativeBuildInputs = [ fasm prjxray pythonDeps ];
  } ''
    mkdir -p "$out"
    export PYTHONPATH="${fasm}/lib/python3.12/site-packages:${pythonDeps}/${bitstreamPkgs.python312.sitePackages}:${prjxray}/usr/share/python3"
    export PRJXRAY_PYTHON_DIR="${prjxray}/usr/share/python3"
    export PRJXRAY_DB_DIR="${dbRoot}"
    timeout --kill-after=10s 600 bash ${../scripts/pipeline/build_and_validate_xc7_bitstream.sh} \
      ${replayBarObserverRoute}/replay.fasm "$out/replay.bit" "$out/replay.frames" \
      ${dbRoot} ${dbRoot}/xc7k480tffg1156-1/part.yaml
    sha256sum "$out/replay.bit" > "$out/replay.bit.sha256"
  '';
in { inherit sourceClosure commandSourceClosure m2SourceClosure replayObserverSourceClosure replayElaboration replaySynthesis replayTimingBaseline replayResetPatched replayBarOffsetPatched replayRoute replayBitstream replayBarObserverResetPatched replayBarObserverRoute replayBarObserverBitstream patchedDb; }
