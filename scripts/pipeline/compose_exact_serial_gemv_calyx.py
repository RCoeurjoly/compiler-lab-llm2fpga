#!/usr/bin/env python3
"""Generate a 49-callsite compiler-owned Calyx serial-GEMV composition."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOWERER = ROOT / "scripts/pipeline/lower_exact_serial_gemv_to_calyx.py"

def lowerer():
    spec = importlib.util.spec_from_file_location("exact_serial_lowerer", LOWERER)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def callsites(torch_text: str):
    mod = lowerer(); found = []
    for ordinal, match in enumerate(mod._OPERATION.finditer(torch_text)):
        descriptor = mod.parse_descriptor_text(match.group(0))
        found.append({"ordinal": ordinal, "source_offset": match.start(), "descriptor": descriptor})
    if len(found) != 49:
        raise ValueError(f"exact_serial_gemv_composition: expected 49 boundaries, found {len(found)}")
    if any(item["descriptor"].rows != 4 for item in found):
        raise ValueError("exact_serial_gemv_composition: exact model requires rows=4")
    return found

def _mem(mod, prefix, desc):
    return "\n".join((
        mod._memory_ports(f"{prefix}_activation", desc.rows * desc.inputs, mod._ceil_log2(desc.rows * desc.inputs), False),
        mod._memory_ports(f"{prefix}_weights", desc.outputs * desc.inputs, mod._ceil_log2(desc.outputs * desc.inputs), False),
        mod._memory_ports(f"{prefix}_results", desc.rows * desc.outputs, mod._ceil_log2(desc.rows * desc.outputs), False),
    ))

def compose(torch_text: str):
    mod = lowerer(); sites = callsites(torch_text)
    shapes = []
    for site in sites:
        desc = site["descriptor"]
        if desc not in shapes: shapes.append(desc)
    kernels = "\n".join(mod._kernel_runtime(desc) for desc in shapes)
    memories = "\n".join(_mem(mod, f"call_{s['ordinal']}", s["descriptor"]) for s in sites)
    instances = "\n".join(
        f"    %call_{s['ordinal']}.clk, %call_{s['ordinal']}.reset, %call_{s['ordinal']}.go, %call_{s['ordinal']}.done = calyx.instance @call_{s['ordinal']} of @llm2fpga_serial_gemv_{s['descriptor'].outputs}_{s['descriptor'].inputs} : i1, i1, i1, i1"
        for s in sites)
    invokes = "\n".join(
        f"        calyx.invoke @call_{s['ordinal']}[activation = call_{s['ordinal']}_activation, weights = call_{s['ordinal']}_weights, results = call_{s['ordinal']}_results]() -> ()"
        for s in sites)
    mlir = f'''module attributes {{calyx.entrypoint = "tinystories_1m_exact_serial_gemv_program"}} {{
  // compiler-owned full exact boundary composition; no SCF or reference RTL.
  calyx.component @tinystories_1m_exact_serial_gemv_program(%clk: i1 {{clk}}, %reset: i1 {{reset}}, %go: i1 {{go}}) -> (%done: i1 {{done}}) {{
{memories}
{instances}
    calyx.wires {{}}
    calyx.control {{
      calyx.seq {{
{invokes}
      }}
    }}
  }} {{toplevel}}
{kernels}}}
'''
    mapping = {"schema": "llm2fpga-exact-serial-gemv-callsite-map-v1", "callsite_count": len(sites),
        "callsites": [{"ordinal": s["ordinal"], "source_offset": s["source_offset"],
                       "descriptor": {"rows": s["descriptor"].rows, "outputs": s["descriptor"].outputs, "inputs": s["descriptor"].inputs, "mac_order": s["descriptor"].mac_order}}
                      for s in sites],
        "component_shapes": [{"rows": d.rows, "outputs": d.outputs, "inputs": d.inputs, "mac_order": d.mac_order} for d in shapes]}
    mapping["map_sha256"] = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return mlir, mapping

def main():
    p=argparse.ArgumentParser(); p.add_argument("--torch",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--map",type=Path,required=True); a=p.parse_args()
    mlir, mapping = compose(a.torch.read_text())
    a.output.write_text(mlir); a.map.write_text(json.dumps(mapping,indent=2,sort_keys=True)+"\n")
if __name__ == "__main__": main()
