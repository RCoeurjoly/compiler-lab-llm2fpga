{ pkgs, sv, simulator }:

pkgs.runCommand "tinystories-w8a8-rc-sv-static-cost-profile" {
  nativeBuildInputs = [ pkgs.python3 pkgs.coreutils ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  SV=${sv}/sv/main.sv
  OBJ=${simulator}/verilator-work/obj_dir
  ${pkgs.python3}/bin/python3 - "$SV" "$OBJ" > "$out/report.json" <<'PY'
import json, pathlib, re, sys
sv = pathlib.Path(sys.argv[1]); obj = pathlib.Path(sys.argv[2])
source = sv.read_text(encoding="utf-8")
cpp = sorted(obj.glob("*.cpp"))
sizes = sorted(((p.stat().st_size, p.name) for p in cpp), reverse=True)
wide = [len(m.group(0)) for m in re.finditer(r"assign [^;]{500,}", source)]
report = {
  "sv": {"bytes": sv.stat().st_size, "lines": source.count("\n") + 1,
         "modules": len(re.findall(r"^module ", source, re.MULTILINE)),
         "hardfloat_related_matches": len(re.findall(r"HardFloat|std_(add|sub|mul|div|fpTo|intTo)|math\\.(exp|tanh|fpowi)", source)),
         "memory_port_references": len(re.findall(r"arg_mem_[0-9]+_", source)),
         "wide_assignment_count": len(wide), "largest_assignment_chars": max(wide, default=0)},
  "verilator_cpp": {"file_count": len(cpp), "bytes": sum(p.stat().st_size for p in cpp),
                    "largest_units": [{"name": n, "bytes": z} for z, n in sizes[:20]]},
  "provenance": {"sv": str(sv), "obj_dir": str(obj)}}
print(json.dumps(report, indent=2, sort_keys=True))
PY
  ${pkgs.python3}/bin/python3 - "$out/report.json" "$out/report.md" <<'PY'
import json, pathlib, sys
r = json.loads(pathlib.Path(sys.argv[1]).read_text()); s = r["sv"]; c = r["verilator_cpp"]
lines = ["# RC SV static cost profile", "",
 f"- SV: {s['bytes']} bytes, {s['lines']} lines, {s['modules']} modules.",
 f"- HardFloat/float-related matches: {s['hardfloat_related_matches']}.",
 f"- Memory-port references: {s['memory_port_references']}.",
 f"- Wide assignments: {s['wide_assignment_count']}; largest: {s['largest_assignment_chars']} characters.",
 f"- Verilator C++ units: {c['file_count']}; total source bytes: {c['bytes']}.", "", "Largest Verilator C++ units:", ""]
lines += [f"- `{x['name']}`: {x['bytes']} bytes" for x in c['largest_units']]
pathlib.Path(sys.argv[2]).write_text("\n".join(lines) + "\n")
PY
''
