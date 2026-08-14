{ pkgs
, python
, yosys
, yosysSlang
, nextpnr
, chipdb
, normalizer
, evidenceWriter
, phaseName
, sourceSvGz
, sourceSha256
}:

let
  targetPart = "xc7k480tffg1156-1";
  targetChipdb = "xc7k480tffg1156.bin";
  dramCompatMap = pkgs.writeText "w4a8-xc7-dram-compat-map.v" ''
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
  probeXdc = pkgs.writeText "${phaseName}-xc7k480t-probe.xdc" ''
    # P&R-only probe constraints; this is not a board-function interface.
    set_property PACKAGE_PIN AA28 [get_ports {clk}]
    set_property PACKAGE_PIN R28 [get_ports {reset}]
    set_property PACKAGE_PIN P30 [get_ports {go}]
    set_property PACKAGE_PIN M30 [get_ports {done}]
    set_property IOSTANDARD LVCMOS18 [get_ports {clk}]
    set_property IOSTANDARD LVCMOS18 [get_ports {reset}]
    set_property IOSTANDARD LVCMOS18 [get_ports {go}]
    set_property IOSTANDARD LVCMOS18 [get_ports {done}]
  '';
in
pkgs.runCommand "${phaseName}-xc7k480t-evidence" {
  nativeBuildInputs = [ python yosys yosysSlang nextpnr pkgs.coreutils pkgs.gzip pkgs.time ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  gzip -dc ${sourceSvGz} > "$out/source.sv"
  test "$(sha256sum "$out/source.sv" | cut -d ' ' -f 1)" = '${sourceSha256}'
  : > "$out/normalized.sv"
  cp ${probeXdc} "$out/probe.xdc"
  cp ${dramCompatMap} "$out/dram-compat-map.v"
  printf '%s\n' '${targetPart}' > "$out/target-part.txt"
  printf '%s\n' '${targetChipdb}' > "$out/target-chipdb.txt"

  set +e
  ${python}/bin/python3 ${normalizer} "$out/source.sv" "$out/normalized.sv" \
    "$out/normalization-receipt.json" >"$out/normalizer.log" 2>&1
  normalizer_status=$?
  set -e
  printf '%s\n' "$normalizer_status" > "$out/normalizer-status.txt"
  if [ ! -s "$out/normalization-receipt.json" ]; then
    printf '{"status":"failed","exit_status":%s}\n' "$normalizer_status" \
      > "$out/normalization-receipt.json"
  fi

  if [ "$normalizer_status" -eq 0 ] && [ -s "$out/normalized.sv" ]; then
    cat > "$out/yosys.ys" <<YOSYS
    read_slang --ignore-initial --ignore-assertions --allow-use-before-declare --max-parse-depth 200000 --top main $out/normalized.sv
    hierarchy -check -top main
    synth_xilinx -family xc7 -top main -flatten -run begin:prepare
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
    techmap -map +/cmp2lut.v -map +/cmp2lcu.v -D LUT_WIDTH=6
    alumacc
    opt
    memory -nomap
    opt_clean
    synth_xilinx -family xc7 -top main -flatten -run map_memory:
    tee -o "$out/mapped-stat.json" stat -json
    write_json "$out/mapped.json"
    YOSYS
    set +e
    ${pkgs.time}/bin/time -v -o "$out/yosys.time" \
      ${yosys}/bin/yosys -m ${yosysSlang}/share/yosys/plugins/slang.so \
      -l "$out/yosys.log" -s "$out/yosys.ys" >"$out/yosys.console" 2>&1
    yosys_status=$?
    set -e
  else
    yosys_status="not-run: normalizer exited $normalizer_status"
    : > "$out/yosys.log"
    : > "$out/yosys.console"
    printf '%s\n' "Yosys not run because normalized SystemVerilog is unavailable." > "$out/yosys.time"
  fi
  printf '%s\n' "$yosys_status" > "$out/yosys-status.txt"

  if [ -s "$out/mapped.json" ]; then
    cat > "$out/nextpnr-prep.ys" <<YOSYS
    read_json "$out/mapped.json"
    techmap -map ${dramCompatMap}
    write_json "$out/nextpnr.json"
    YOSYS
    set +e
    ${pkgs.time}/bin/time -v -o "$out/nextpnr-prep.time" \
      ${yosys}/bin/yosys -l "$out/nextpnr-prep.log" -s "$out/nextpnr-prep.ys" \
      >"$out/nextpnr-prep.console" 2>&1
    prep_status=$?
    set -e
    printf '%s\n' "$prep_status" > "$out/nextpnr-prep-status.txt"
    if [ "$prep_status" -eq 0 ] && [ -s "$out/nextpnr.json" ]; then
      set +e
      ${pkgs.time}/bin/time -v -o "$out/nextpnr.time" \
        ${nextpnr}/bin/nextpnr-xilinx --chipdb ${chipdb} --xdc "$out/probe.xdc" \
        --json "$out/nextpnr.json" --fasm "$out/design.fasm" \
        --log "$out/nextpnr.log" --freq 12 >"$out/nextpnr.console" 2>&1
      nextpnr_status=$?
      set -e
    else
      nextpnr_status="not-run: compatibility transform exited $prep_status"
      : > "$out/nextpnr.log"
      : > "$out/nextpnr.console"
      printf '%s\n' "nextpnr not run because RAM64X1S/RAM128X1S compatibility transform failed." > "$out/nextpnr.time"
    fi
  else
    nextpnr_status="not-run: Yosys mapped JSON was unavailable"
    : > "$out/nextpnr.log"
    : > "$out/nextpnr.console"
    printf '%s\n' "nextpnr not run because Yosys did not emit mapped JSON." > "$out/nextpnr.time"
  fi
  printf '%s\n' "$nextpnr_status" > "$out/nextpnr-status.txt"

  ${python}/bin/python3 ${evidenceWriter} --phase '${phaseName}' \
    --source "$out/source.sv" --normalized "$out/normalized.sv" \
    --normalization-receipt "$out/normalization-receipt.json" \
    --yosys-stat "$out/mapped-stat.json" --yosys-status "$out/yosys-status.txt" \
    --yosys-log "$out/yosys.log" --yosys-time "$out/yosys.time" \
    --nextpnr-status "$out/nextpnr-status.txt" --nextpnr-log "$out/nextpnr.log" \
    --nextpnr-time "$out/nextpnr.time" --fasm "$out/design.fasm" --out "$out/result.json"
  sha256sum "$out/source.sv" "$out/normalized.sv" "$out/result.json" > "$out/sha256sums.txt"
''
