"""Constrain the replay PCIe clock buffers to the proven smoke allocation."""

PIPE = "pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i."
TARGETS = {
    PIPE + "pclk_i1_bufgctrl.pclk_i1":
        ("BUFGCTRL", "BUFGCTRL_X0Y23/BUFGCTRL"),
    PIPE + "txoutclk0_i":
        ("BUFGCTRL", "BUFGCTRL_X0Y27/BUFGCTRL"),
}


def _entries(cells):
    if hasattr(cells, "items"):
        return list(cells.items())
    return list(cells)


def apply(ctx):
    entries = _entries(ctx.cells)
    targets_by_bel = {bel: name for name, (_, bel) in TARGETS.items()}

    # Validate the entire operation before changing the first attribute.
    for name, (kind, bel) in TARGETS.items():
        if name not in ctx.cells:
            raise RuntimeError("exact PCIe clock cell missing: " + name)
        cell = ctx.cells[name]
        if str(cell.type) != kind:
            raise RuntimeError("unexpected packed PCIe clock cell type: " + name)
        if "BEL" in cell.attrs and str(cell.attrs["BEL"]) != bel:
            raise RuntimeError("refusing to override PCIe clock constraint: " + name)
    for name, cell in entries:
        if str(name) not in TARGETS and "BEL" in cell.attrs:
            bel = str(cell.attrs["BEL"])
            if bel in targets_by_bel:
                raise RuntimeError("proven PCIe clock site already occupied: " + bel)

    for name, (_, bel) in TARGETS.items():
        ctx.cells[name].setAttr("BEL", bel)
        print("Task4 PCIe clock topology: " + name + " -> " + bel)


if "ctx" in globals():
    apply(ctx)
