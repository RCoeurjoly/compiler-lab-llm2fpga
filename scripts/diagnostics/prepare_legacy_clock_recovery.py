"""Validate placed-cell/FASM evidence for supported legacy PIP recovery.

This does not recover historical PIP identity or prove full FASM equivalence.
Only independently matching placed-cell parameters and original FASM permit
the later diagnostic importer to select supported input inversion pairs.
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


def unsigned_mask(value, width):
    if isinstance(value, str) and re.fullmatch(r"[01]+", value):
        value = int(value, 2)
    if not isinstance(value, int) or not 0 <= value < (1 << width):
        raise ValueError(f"invalid {width}-bit inversion mask: {value!r}")
    return value


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
        if not re.search(r"\.(CLKINV|NOCLKINV|IN_USE|IS_IGNORE[01]_INVERTED|ZINV_(CE|S)[01]|ZINV_(CLKARDCLK|CLKBWRCLK|ENARDEN|ENBWREN|RSTRAMARSTRAM|RSTRAMB|RSTREGARSTREG|RSTREGB|RST|PWRDWN|PSEN|PSINCDEC)|INV_CLKINSEL|ZIS_(CLK|CARRYIN)_INVERTED|ZIS_(INMODE|OPMODE|ALUMODE)_INVERTED\[\d+\])$", name):
            continue
        if "=" in line and line.split("=", 1)[1].strip() != "1":
            raise ValueError(f"unsupported clock feature assignment: {line}")
        features.add(name)
    polarity = {}
    ff_count = 0
    lutram_count = 0
    constant_lutram_sites = set()
    constant_bits = {bit for name, net in module.get("netnames", {}).items()
                     if name in ("$PACKER_GND_NET", "$PACKER_VCC_NET") for bit in net["bits"]}
    allowed = {kind + suffix for kind in ("FDRE", "FDSE", "FDCE", "FDPE")
               for suffix in ("", "_1")}
    for name, cell in module.get("cells", {}).items():
        clock = cell.get("connections", {}).get("CLK", [])
        lutram = cell["type"] == "SLICE_LUTX" and bool(clock)
        if lutram and all(bit in constant_bits or bit in ("0", "1") for bit in clock):
            # Immutable LUT ROMs have a tied-off write clock; their packing
            # inversion does not configure the active shared slice clock.
            attrs = cell["attributes"]
            if attrs["X_ORIG_TYPE"] != "RAMD64E":
                raise ValueError(f"unsupported constant-clock LUT type: {name}")
            boolean(cell["parameters"]["IS_WCLK_INVERTED"])
            match = re.fullmatch(r"(SLICE_X\d+Y\d+)/[ABCD][56]LUT", attrs["NEXTPNR_BEL"])
            if not match:
                raise ValueError(f"unsupported constant-clock LUT BEL: {name}")
            constant_lutram_sites.add(match[1])
            continue
        if cell["type"] != "SLICE_FFX" and not lutram:
            continue
        attrs = cell["attributes"]
        kind = attrs["X_ORIG_TYPE"]
        if lutram:
            if kind != "RAMD64E":
                raise ValueError(f"unsupported clocked LUT type for {name}: {kind}")
            inverted = boolean(cell["parameters"]["IS_WCLK_INVERTED"])
            lutram_count += 1
        elif kind not in allowed:
            raise ValueError(f"unsupported FF type for {name}: {kind}")
        else:
            parameter = boolean(cell.get("parameters", {}).get("IS_CLK_INVERTED", 0))
            inverted = kind.endswith("_1") or parameter
            ff_count += 1
        bel = attrs["NEXTPNR_BEL"]
        site, separator, _ = bel.partition("/")
        if not separator or not re.fullmatch(r"SLICE_X\d+Y\d+", site):
            raise ValueError(f"invalid placed clocked slice BEL: {bel}")
        if site in polarity and polarity[site] != inverted:
            raise ValueError(f"conflicting slice clock polarity: {site}")
        polarity[site] = inverted
    # The pinned write_ffs_config defaults to NOCLKINV when no FF exists.
    # Validate that physical FASM setting explicitly; do not treat a ROM's
    # constant-net packing inversion as an active edge-sensitive clock.
    for site in constant_lutram_sites:
        polarity.setdefault(site, False)
    if not polarity:
        raise ValueError("no placed SLICE_FFX cells to validate")
    settings = dict(module.get("settings", {}))
    validated_selectors = set()
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
        validated_selectors.add(key)
    bufg_sites = set()
    for name, cell in module.get("cells", {}).items():
        if cell["type"] != "BUFGCTRL":
            continue
        bel = cell["attributes"]["NEXTPNR_BEL"]
        match = re.fullmatch(r"(BUFGCTRL_X0Y(\d+))/BUFGCTRL", bel)
        if not match:
            raise ValueError(f"unsupported BUFG BEL: {bel}")
        site = match[1]
        if site in bufg_sites:
            raise ValueError(f"duplicate BUFG site: {site}")
        bufg_sites.add(site)
        tile, kind = sites[site]
        if kind != "BUFGCTRL" or not tile.startswith(("CLK_BUFG_BOT_R_", "CLK_BUFG_TOP_R_")):
            raise ValueError(f"unsupported BUFG tile/site: {tile}/{site}")
        # Audited against all 32 BUFG sites in the pinned Kintex chipdb.
        prefix = f"{tile}.BUFGCTRL.BUFGCTRL_X0Y{int(match[2]) % 16}."
        if prefix + "IN_USE" not in features:
            raise ValueError(f"missing original BUFG IN_USE evidence: {site}")
        for pin in ("IGNORE0", "IGNORE1", "CE0", "CE1", "S0", "S1"):
            parameter = "IS_" + pin + "_INVERTED"
            inverted = boolean(cell.get("parameters", {}).get(parameter, 0))
            feature = parameter if pin.startswith("IGNORE") else "ZINV_" + pin
            expected = inverted if pin.startswith("IGNORE") else not inverted
            if (prefix + feature in features) != expected:
                raise ValueError(f"original BUFG FASM mismatch: {site}/{feature}")
            key = f"checkpoint/selector/{site}/{pin}INV"
            selection = pin + ("_B" if inverted else "")
            if key in settings and settings[key] != selection:
                raise ValueError(f"conflicting existing selector: {key}")
            settings[key] = selection
            validated_selectors.add(key)
    bram_count = 0
    for name, cell in module.get("cells", {}).items():
        if cell["type"] not in ("RAMB18E1_RAMB18E1", "RAMB36E1_RAMB36E1"):
            continue
        size = 18 if cell["type"].startswith("RAMB18") else 36
        original = f"RAMB{size}E1"
        attrs = cell["attributes"]
        if attrs["X_ORIG_TYPE"] != original:
            raise ValueError(f"unsupported BRAM original type: {name}")
        match = re.fullmatch(rf"(RAMB{size}_X\d+Y(\d+))/{original}", attrs["NEXTPNR_BEL"])
        if not match:
            raise ValueError(f"unsupported BRAM BEL: {attrs['NEXTPNR_BEL']}")
        site = match[1]
        tile, kind = sites[site]
        # Tilegrid names the default physical site type, not the placed BEL
        # variant: lower RAMB18 sites are FIFO18E1; RAMB36 is RAMBFIFO36E1.
        allowed_kinds = ("RAMB18E1", "FIFO18E1") if size == 18 else ("RAMBFIFO36E1",)
        if kind not in allowed_kinds or not tile.startswith(("BRAM_L_", "BRAM_R_")):
            raise ValueError(f"unsupported BRAM tile/site: {tile}/{site}")
        # The writer emits both RAMB18 halves for a RAMB36 cell. For RAMB18,
        # absolute site Y parity equals relative half in the pinned chipdb.
        halves = (int(match[2]) % 2,) if size == 18 else (0, 1)
        for half in halves:
            prefix = f"{tile}.RAMB18_Y{half}."
            if prefix + "IN_USE" not in features:
                raise ValueError(f"missing original BRAM IN_USE evidence: {site}/{half}")
            for pin in ("CLKARDCLK", "CLKBWRCLK", "ENARDEN", "ENBWREN",
                        "RSTRAMARSTRAM", "RSTRAMB", "RSTREGARSTREG", "RSTREGB"):
                inverted = boolean(cell.get("parameters", {}).get(f"IS_{pin}_INVERTED", 0))
                if (prefix + "ZINV_" + pin in features) != (not inverted):
                    raise ValueError(f"original BRAM FASM mismatch: {site}/{half}/{pin}")
                physical_pin = pin + (("L" if half == 0 else "U") if size == 36 else "")
                key = f"checkpoint/selector/{site}/{physical_pin}INV"
                selection = physical_pin + ("_B" if inverted else "")
                if key in settings and settings[key] != selection:
                    raise ValueError(f"conflicting existing selector: {key}")
                settings[key] = selection
                validated_selectors.add(key)
        bram_count += 1
    dsp_sites = set()
    for name, cell in module.get("cells", {}).items():
        if cell["type"] != "DSP48E1_DSP48E1":
            continue
        attrs = cell["attributes"]
        match = re.fullmatch(r"(DSP48_X\d+Y(\d+))/DSP48E1", attrs["NEXTPNR_BEL"])
        if not match or attrs["X_ORIG_TYPE"] != "DSP48E1":
            raise ValueError(f"unsupported DSP BEL/type: {name}")
        site = match[1]
        if site in dsp_sites:
            raise ValueError(f"duplicate placed DSP site: {site}")
        dsp_sites.add(site)
        tile, kind = sites[site]
        if kind != "DSP48E1" or not tile.startswith(("DSP_L_", "DSP_R_")):
            raise ValueError(f"unsupported DSP tile/site: {tile}/{site}")
        # All 1,920 DSP sites in the pinned chipdb were checked independently.
        prefix = f"{tile}.DSP48.DSP_{int(match[2]) % 2}."
        params = cell.get("parameters", {})
        selections = []
        for bus, width in (("ALUMODE", 4), ("INMODE", 5), ("OPMODE", 7)):
            vector = unsigned_mask(params.get(f"IS_{bus}_INVERTED", 0), width)
            for bit in range(width):
                override = boolean(params.get(f"IS_{bus}[{bit}]_INVERTED", 0))
                inverted = bool((vector >> bit) & 1) or override
                selections.append((f"{bus}{bit}", f"ZIS_{bus}_INVERTED[{bit}]", inverted))
        for pin in ("CLK", "CARRYIN"):
            selections.append((pin, f"ZIS_{pin}_INVERTED", boolean(params.get(f"IS_{pin}_INVERTED", 0))))
        for pin, feature, inverted in selections:
            if (prefix + feature in features) != (not inverted):
                raise ValueError(f"original DSP FASM mismatch: {site}/{feature}")
            key = f"checkpoint/selector/{site}/{pin}INV"
            selection = pin + ("_B" if inverted else "")
            if key in settings and settings[key] != selection:
                raise ValueError(f"conflicting existing selector: {key}")
            settings[key] = selection
            validated_selectors.add(key)
    mmcm_sites = set()
    for name, cell in module.get("cells", {}).items():
        if cell["type"] != "MMCME2_ADV_MMCME2_ADV":
            continue
        attrs = cell["attributes"]
        match = re.fullmatch(r"(MMCME2_ADV_X\d+Y\d+)/MMCME2_ADV", attrs["NEXTPNR_BEL"])
        if not match or attrs["X_ORIG_TYPE"] != "MMCME2_ADV":
            raise ValueError(f"unsupported MMCM BEL/type: {name}")
        site = match[1]
        if site in mmcm_sites:
            raise ValueError(f"duplicate placed MMCM site: {site}")
        mmcm_sites.add(site)
        tile, kind = sites[site]
        if kind != "MMCME2_ADV" or not tile.startswith("CMT_TOP_R_LOWER_B_"):
            raise ValueError(f"unsupported MMCM tile/site: {tile}/{site}")
        prefix = f"{tile}.MMCME2_ADV."
        if prefix + "IN_USE" not in features:
            raise ValueError(f"missing original MMCM IN_USE evidence: {site}")
        for pin in ("CLKINSEL", "RST", "PWRDWN", "PSEN", "PSINCDEC"):
            inverted = boolean(cell.get("parameters", {}).get(f"IS_{pin}_INVERTED", 0))
            # The pinned writer's historical ZINV_* spelling means INV here;
            # preserve its exact emitted configuration, not the name's connotation.
            feature = "INV_CLKINSEL" if pin == "CLKINSEL" else "ZINV_" + pin
            if (prefix + feature in features) != inverted:
                raise ValueError(f"original MMCM FASM mismatch: {site}/{feature}")
            key = f"checkpoint/selector/{site}/{pin}INV"
            selection = pin + ("_B" if inverted else "")
            if key in settings and settings[key] != selection:
                raise ValueError(f"conflicting existing selector: {key}")
            settings[key] = selection
            validated_selectors.add(key)
    unvalidated = {key for key in settings if key.startswith("checkpoint/selector/")} - validated_selectors
    if unvalidated:
        raise ValueError(f"selectors without placed-cell and original FASM evidence: {sorted(unvalidated)}")
    module["settings"] = settings
    return {"validated_sites": len(polarity), "validated_ff_cells": ff_count,
            "validated_bufg_sites": len(bufg_sites),
            "validated_bram_cells": bram_count,
            "validated_lutram_clock_cells": lutram_count,
            "validated_constant_lutram_clock_sites": len(constant_lutram_sites),
            "validated_dsp_cells": len(dsp_sites),
            "validated_mmcm_cells": len(mmcm_sites),
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
