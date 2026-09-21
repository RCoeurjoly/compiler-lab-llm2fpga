"""One pre-place diagnostic constraint; no clock/reset/netlist changes.

Consumed only after the authenticated candidate preflight. The packed BUFG
retains its exact hierarchical name but nextpnr changes its type to BUFGCTRL.
"""
CELL = 'pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.txoutclk0_i'
BEL = 'BUFGCTRL_X0Y27/BUFGCTRL'


def apply(ctx):
    if CELL not in ctx.cells:
        raise RuntimeError('exact TXOUTCLK reference BUFG missing')
    cell = ctx.cells[CELL]
    if str(cell.type) != 'BUFGCTRL':
        raise RuntimeError('unexpected packed TXOUTCLK reference cell type')
    if 'BEL' in cell.attrs and str(cell.attrs['BEL']) != BEL:
        raise RuntimeError('refusing to override an existing reference-clock constraint')
    entries = ctx.cells.items() if hasattr(ctx.cells, 'items') else ctx.cells
    for name, other in entries:
        if name != CELL and 'BEL' in other.attrs and str(other.attrs['BEL']) == BEL:
            raise RuntimeError('BUFGCTRL_X0Y27 already constrained to another cell')
    cell.setAttr('BEL', BEL)
    print('Task4 one-cell overlay: ' + CELL + ' -> ' + BEL)


if 'ctx' in globals():
    apply(ctx)
