{ pkgs
, python
, yosys
, yosysSlang
, nextpnr
, chipdb
, sourceSvGz
, normalizer
, evidenceWriter
}:

let
  routeName = "tinystories-w8a8-rc-xc7k480t";
  targetPart = "xc7k480tffg1156-1";
  targetChipdb = "xc7k480tffg1156.bin";
  normalizerName = "fix_sv_synthesis_frontend.py";
  sourceArchiveName = "rc-validated-main.sv.gz";

  normalized = pkgs.runCommand "${routeName}-normalized-sv" {
    nativeBuildInputs = [ python pkgs.coreutils pkgs.gzip ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    printf '%s\n' '${normalizerName}' > "$out/normalizer-name.txt"
    printf '%s\n' '${sourceArchiveName}' > "$out/source-archive-name.txt"
    gzip -dc ${sourceSvGz} > source-main.sv
    ${python}/bin/python3 ${normalizer} \
      source-main.sv \
      "$out/main.sv" \
      "$out/normalization-receipt.json" \
      > "$out/normalizer-stdout.json"
    sha256sum source-main.sv "$out/main.sv" \
      > "$out/sha256sums.txt"
    test "$(sha256sum source-main.sv | cut -d ' ' -f 1)" = \
      2262298433271af636683517bba9c7641d02097de314b3dac4f4e3c0843e83f7
    test "$(sha256sum "$out/main.sv" | cut -d ' ' -f 1)" = \
      f6ea6c64dd33dff5fd2ab50de14b1e32b369e32ea6d6b2e18b6da9e4d1e3bd82
  '';

  mapped = pkgs.runCommand "${routeName}-mapped" {
    nativeBuildInputs = [ yosys yosysSlang pkgs.time pkgs.gzip ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    cat > run.ys <<YOSYS
    read_slang --ignore-initial --ignore-assertions --allow-use-before-declare --max-parse-depth 200000 --top main ${normalized}/main.sv
    hierarchy -check -top main

    synth_xilinx -family xc7 -top main -flatten -run begin:prepare

    # Preserve the original sequential logic while avoiding pathological FSM
    # reconstruction of the generated monolithic controller.
    proc
    check
    flatten
    tribuf -logic
    deminout
    opt_expr
    opt_clean
    check
    opt -nodffe -nosdff
    opt
    wreduce
    peepopt
    opt_clean
    pmux2shiftx
    clean
    sort

    synth_xilinx -family xc7 -top main -flatten -run map_dsp:coarse

    # Avoid the standalone SAT SHARE pass; ordinary OPT_SHARE remains enabled.
    techmap -map +/cmp2lut.v -map +/cmp2lcu.v -D LUT_WIDTH=6
    alumacc
    opt
    memory -nomap
    opt_clean

    synth_xilinx -family xc7 -top main -flatten -run map_memory:
    tee -o "$out/mapped-stat.json" stat -json
    write_json "$out/mapped.json"
    YOSYS
    cp run.ys "$out/yosys.ys"
    ${pkgs.time}/bin/time -v -o "$out/yosys.time" \
      ${yosys}/bin/yosys \
        -m ${yosysSlang}/share/yosys/plugins/slang.so \
        -l yosys.log -s run.ys > yosys.console 2>&1
    test -s "$out/mapped.json"
    test -s "$out/mapped-stat.json"
    gzip -9 < yosys.log > "$out/yosys.log.gz"
    gzip -9 < yosys.console > "$out/yosys.console.gz"
    cp ${normalized}/normalization-receipt.json "$out/normalization-receipt.json"
    sha256sum "$out/mapped.json" "$out/mapped-stat.json" \
      > "$out/sha256sums.txt"
  '';

  dramCompatMap = pkgs.writeText "rc-nextpnr-dram-compat-map.v" ''
    module RAM64X1S(output O, input A0, A1, A2, A3, A4, A5, input D, WCLK, WE);
      parameter [63:0] INIT = 64'h0;
      parameter IS_WCLK_INVERTED = 1'b0;
      wire unused_dpo;
      RAM64X1D #(.INIT(INIT), .IS_WCLK_INVERTED(IS_WCLK_INVERTED))
        _TECHMAP_REPLACE_ (
          .SPO(O), .DPO(unused_dpo), .D(D), .WCLK(WCLK), .WE(WE),
          .A0(A0), .A1(A1), .A2(A2), .A3(A3), .A4(A4), .A5(A5),
          .DPRA0(A0), .DPRA1(A1), .DPRA2(A2), .DPRA3(A3),
          .DPRA4(A4), .DPRA5(A5)
        );
    endmodule

    module RAM128X1S(output O, input A0, A1, A2, A3, A4, A5, A6, input D, WCLK, WE);
      parameter [127:0] INIT = 128'h0;
      parameter IS_WCLK_INVERTED = 1'b0;
      wire unused_dpo;
      wire [6:0] addr = {A6, A5, A4, A3, A2, A1, A0};
      RAM128X1D #(.INIT(INIT), .IS_WCLK_INVERTED(IS_WCLK_INVERTED))
        _TECHMAP_REPLACE_ (
          .SPO(O), .DPO(unused_dpo), .D(D), .WCLK(WCLK), .WE(WE),
          .A(addr), .DPRA(addr)
        );
    endmodule
  '';

  dramCompatible = pkgs.runCommand "${routeName}-dram-compatible" {
    nativeBuildInputs = [ yosys pkgs.time pkgs.gzip pkgs.coreutils ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    cat > run.ys <<YOSYS
    read_json ${mapped}/mapped.json
    techmap -map ${dramCompatMap}
    tee -o $out/mapped-stat.json stat -json
    write_json $out/mapped.json
    YOSYS
    cp run.ys "$out/yosys.ys"
    cp ${dramCompatMap} "$out/dram-compat-map.v"
    ${pkgs.time}/bin/time -v -o "$out/yosys.time" \
      ${yosys}/bin/yosys -l yosys.log -s run.ys > yosys.console 2>&1
    test -s "$out/mapped.json"
    gzip -9 < yosys.log > "$out/yosys.log.gz"
    gzip -9 < yosys.console > "$out/yosys.console.gz"
    sha256sum "$out/mapped.json" "$out/mapped-stat.json" \
      "$out/dram-compat-map.v" > "$out/sha256sums.txt"
  '';

  probeXdc = pkgs.writeText "${routeName}-probe.xdc" ''
    # P&R-only probe constraints; not a board-function interface.
    set_property PACKAGE_PIN AA28 [get_ports {clk}]
    set_property PACKAGE_PIN R28 [get_ports {reset}]
    set_property PACKAGE_PIN P30 [get_ports {go}]
    set_property PACKAGE_PIN M30 [get_ports {done}]
    set_property IOSTANDARD LVCMOS18 [get_ports {clk}]
    set_property IOSTANDARD LVCMOS18 [get_ports {reset}]
    set_property IOSTANDARD LVCMOS18 [get_ports {go}]
    set_property IOSTANDARD LVCMOS18 [get_ports {done}]
  '';

  pnrEvidence = pkgs.runCommand "${routeName}-nextpnr-evidence" {
    nativeBuildInputs = [ nextpnr python pkgs.time pkgs.gzip pkgs.coreutils ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    cp ${probeXdc} "$out/probe.xdc"
    printf '%s\n' '${targetPart}' > "$out/target-part.txt"
    printf '%s\n' '${targetChipdb}' > "$out/target-chipdb.txt"
    set +e
    ${pkgs.time}/bin/time -v -o "$out/nextpnr.time" \
      ${nextpnr}/bin/nextpnr-xilinx \
        --chipdb ${chipdb} \
        --xdc ${probeXdc} \
        --json ${dramCompatible}/mapped.json \
        --fasm "$out/design.fasm" \
        --log nextpnr.log \
        --freq 12 > nextpnr.console 2>&1
    nextpnr_status=$?
    set -e
    printf '%s\n' "$nextpnr_status" > "$out/nextpnr-exit-status.txt"
    ${python}/bin/python3 ${evidenceWriter} \
      --log nextpnr.log \
      --exit-status "$nextpnr_status" \
      --out "$out/timing-status.json"
    gzip -9 < nextpnr.log > "$out/nextpnr.log.gz"
    gzip -9 < nextpnr.console > "$out/nextpnr.console.gz"
    test "$nextpnr_status" -ne 0
    grep -F "SLICE_LUTX: 776182/597200" nextpnr.log
    grep -F "Failed to expand region" nextpnr.log
    sha256sum "$out/timing-status.json" "$out/probe.xdc" \
      > "$out/sha256sums.txt"
  '';
in
{
  inherit normalized mapped dramCompatible pnrEvidence;
}
