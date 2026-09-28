"""Validate physical slice-clock evidence before normalizing legacy PIP names.

This does not recover historical PIP identity or prove full FASM equivalence.
Only explicit, independently matching FF parameters and original FASM permit
the later diagnostic importer to select CLK versus CLK_B.
"""
import argparse
import json
import re
from pathlib import Path


def boolean(value):
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and re.fullmatch(r"[01]+", value):
        number = int(value, 2)
        if number in (0, 1):
            return bool(number)
    raise ValueError(f"nonboolean IS_CLK_INVERTED: {value!r}")


def prepare(design, fasm, tilegrid):
    modules = design["modules"]
    if len(modules) != 1:
        raise ValueError("requires one flattened module")
    module = next(iter(modules.values()))
    sites = {}
    for tile, data in tilegrid.items():
        for site, kind in data.get("sites", {}).items():
            if site in sites:
                raise ValueError(f"duplicate tilegrid site: {site}")
            sites[site] = (tile, kind)
    features = set()
    for line in fasm.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name = line.split("=", 1)[0].strip()
        if not name.endswith((".CLKINV", ".NOCLKINV")):
            continue
        if "=" in line and line.split("=", 1)[1].strip() != "1":
            raise ValueError(f"unsupported clock feature assignment: {line}")
        features.add(name)
    polarity = {}
    ff_count = 0
    allowed = {kind + suffix for kind in ("FDRE", "FDSE", "FDCE", "FDPE")
               for suffix in ("", "_1")}
    for name, cell in module.get("cells", {}).items():
        if cell["type"] != "SLICE_FFX":
            continue
        attrs = cell["attributes"]
        kind = attrs["X_ORIG_TYPE"]
        if kind not in allowed:
            raise ValueError(f"unsupported FF type for {name}: {kind}")
        parameter = boolean(cell.get("parameters", {}).get("IS_CLK_INVERTED", 0))
        inverted = kind.endswith("_1") or parameter
        bel = attrs["NEXTPNR_BEL"]
        site, separator, _ = bel.partition("/")
        if not separator or not re.fullmatch(r"SLICE_X\d+Y\d+", site):
            raise ValueError(f"invalid placed FF BEL: {bel}")
        if site in polarity and polarity[site] != inverted:
            raise ValueError(f"conflicting FF clock polarity: {site}")
        polarity[site] = inverted
        ff_count += 1
    if not polarity:
        raise ValueError("no placed SLICE_FFX cells to validate")
    settings = dict(module.get("settings", {}))
    for site, inverted in polarity.items():
        tile, kind = sites[site]
        if kind not in ("SLICEL", "SLICEM") or not tile.startswith(("CLBLL_", "CLBLM_")):
            raise ValueError(f"unsupported tile/site: {tile}/{site}/{kind}")
        half = int(re.fullmatch(r"SLICE_X(\d+)Y\d+", site)[1]) % 2
        prefix = f"{tile}.{kind}_X{half}."
        present = {feature for feature in ("CLKINV", "NOCLKINV") if prefix + feature in features}
        expected = "CLKINV" if inverted else "NOCLKINV"
        if present != {expected}:
            raise ValueError(f"original FASM clock evidence mismatch: {site}: {sorted(present)}")
        key = f"checkpoint/selector/{site}/CLKINV"
        selector = "CLK_B" if inverted else "CLK"
        if key in settings and settings[key] != selector:
            raise ValueError(f"conflicting existing selector: {key}")
        settings[key] = selector
    module["settings"] = settings
    return {"validated_sites": len(polarity), "validated_ff_cells": ff_count,
            "historical_pip_identity_proven": False,
            "full_route_and_fasm_equivalence_proven": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("json", "fasm", "tilegrid", "output", "receipt"):
        parser.add_argument("--" + flag, required=True, type=Path)
    args = parser.parse_args()
    inputs = {path.resolve() for path in (args.json, args.fasm, args.tilegrid)}
    outputs = [args.output.resolve(), args.receipt.resolve()]
    if len(set(outputs)) != 2 or any(path in inputs or path.exists() for path in outputs):
        parser.error("outputs must be distinct new files, never overwrite inputs")
    try:
        design = json.loads(args.json.read_text())
        receipt = prepare(design, args.fasm.read_text(), json.loads(args.tilegrid.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(design) + "\n")
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
