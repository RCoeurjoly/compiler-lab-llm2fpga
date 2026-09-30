{ pkgs, python, placement, nextpnr, chipdb, constraints }:
pkgs.runCommand "task6-full16-two-rom-route" {
  nativeBuildInputs = [ python nextpnr ];
} ''
  set -euo pipefail
  export OMP_NUM_THREADS=1
  ulimit -v 16777216
  python3 ${../scripts/pipeline/rebuild_task6_bram_route.py} \
    ${placement} ${nextpnr} ${chipdb} ${constraints} "$out"
''
