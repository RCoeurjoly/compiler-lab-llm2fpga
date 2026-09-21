"""Authenticate a one-BUFG route candidate. This tool never launches a build.

No bitstream generation or hardware operations are exposed. A prospective
route must retain the exact original inputs plus the one reviewed overlay.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CELL = 'pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.txoutclk0_i'
BEL = 'BUFGCTRL_X0Y27/BUFGCTRL'
CLOSURE = '/nix/store/rlw4yzrqhavc7la9hrdng2l1khwklrfn-task6-board-shell-m2-production-source-closure'
PINS = {
    'netlist': ('/nix/store/iwy6sw36cskqqywj58jpg3f71c84qcm1-compiler-ddr3-trace-replay-synthesis-screen/replay.json', 'f24399228ba1009fbf1c890c01bfc670c140919479ca5df5d82c41c2c3c40e22'),
    'nextpnr': ('/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/bin/nextpnr-xilinx', '25c434b7614ade7cbdd448b4f993d1feced26296b0164f6e648ddaced7ebac16'),
    'chipdb': ('/nix/store/8s95bdz7d69facix9k7h99dfw2chah45-nextpnr-xilinx-chipdb-0.8.2/xc7k480tffg1156.bin', 'd8472bfcc19dc31686d80cc34f0d37b958c268656182537b06b3439711b105f1'),
    'xdc': (CLOSURE + '/constraints/board.xdc', '890ebb9d0fc854c8595d3e9e67b4a4074fe42ac7682680b9c33dd1d2c8662f57'),
    'pre_pack': (CLOSURE + '/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py', '42acd411f3e34ac494e56f64b12c0de81394b567d5087c1213b820040fa9d698'),
    'baseline_fasm': ('/nix/store/wzqmm002ziqkxyaiz3rgdy6h4kgchjzl-compiler-ddr3-trace-replay-route/replay.fasm', '6f98a14dc0c9f515632c793c4b1ecf1925456ee3a1e5730a69e131f119a6be61'),
    'overlay': (str(ROOT / 'scripts/pipeline/replay_txoutclk_bufg27.py'), 'a2fe21b9176011fed9be5d18afea6471ed5a85b421f7818a7669b8d1969700ea'),
}
MIN_FREE_BYTES = 144 << 20


def preflight():
    artifacts = {}
    for name, (filename, expected) in PINS.items():
        path = Path(filename)
        with path.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected: raise ValueError(name + ' source hash changed')
        artifacts[name] = {'path': filename, 'bytes': path.stat().st_size, 'sha256': actual}
    module = json.loads(Path(PINS['netlist'][0]).read_text())['modules']['compiler_ddr3_trace_replay_top']
    cell = module['cells'].get(EXPECTED_CELL)
    if not cell or cell['type'] != 'BUFG' or cell['connections'] != {'I': [38070], 'O': [38072]}:
        raise ValueError('exact reference BUFG connectivity changed')
    mmcm = module['cells']['pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.mmcm_i']
    if mmcm['connections']['CLKIN1'] != [38072] or mmcm['connections']['CLKIN2'] != [38072]:
        raise ValueError('reference buffer does not feed the exact MMCM')
    fasm = Path(PINS['baseline_fasm'][0]).read_text().splitlines()
    prefix = 'CLK_BUFG_TOP_R_X155Y209.BUFGCTRL.BUFGCTRL_X0Y'
    if prefix + '4.IN_USE' not in fasm or prefix + '11.IN_USE' in fasm:
        raise ValueError('baseline BUFG20 absent or requested BUFG27 occupied')
    return {'schema': 'task4-txoutclk-bufg27-candidate-v1', 'cell': EXPECTED_CELL,
            'bel': BEL, 'net_connections': cell['connections'], 'artifacts': artifacts,
            'profile': {'seed': 15, 'byte_lanes': 2, 'controller_period_ps': 12000,
                        'ddr_period_ps': 3000, 'pcie_clock_mhz': 62.5, 'bist_mode': 2},
            'baseline_routed_checkpoint_available': False,
            'scope': 'one input-constraint route diagnostic, not a frozen-placement ECO or hardware qualification'}


def admit_disk(directory):
    free = shutil.disk_usage(directory).free
    if free < MIN_FREE_BYTES:
        raise RuntimeError(f'build disk blocked: {free} bytes free; require {MIN_FREE_BYTES}')
    return {'minimum_bytes': MIN_FREE_BYTES, 'free_bytes': free,
            'measured_baseline_output_bytes': 21979861,
            'budget_bytes': {'fasm': 32 << 20, 'log': 32 << 20, 'metadata': 8 << 20,
                             'evidence_reserve': 8 << 20, 'free_floor': 64 << 20}}


def route_command(output):
    # The only new nextpnr input is --pre-place. Original seed/profile, netlist,
    # constraints, clock script, executable and chipdb remain byte-identical.
    return [PINS['nextpnr'][0], '--chipdb', PINS['chipdb'][0], '--xdc', PINS['xdc'][0],
            '--json', PINS['netlist'][0], '--pre-pack', PINS['pre_pack'][0],
            '--pre-place', PINS['overlay'][0], '--seed', '15', '--placer-budgets',
            '--timing-allow-fail', '--fasm', str(Path(output) / 'replay.fasm')]


def compare_fasm(baseline, candidate):
    """Compare every FASM block; tolerate only the target's two nets/site block.

    This is a conservative rejection gate, not proof of named-cell placement
    equivalence. FASM keeps cell/net blocks separated by blank lines. A changed
    unrelated block (including a constant tie net) is collateral and rejects.
    Even a passing result still needs independent clock-path/timing review.
    """
    site_prefix = 'CLK_BUFG_TOP_R_X155Y209.BUFGCTRL.BUFGCTRL_X0Y'
    def partition(text):
        rest, allowed = [], []
        for raw in text.split('\n\n'):
            lines = sorted(line.strip() for line in raw.splitlines() if line.strip())
            if not lines: continue
            target_site = all(line.startswith(site_prefix + '4.') or
                              line.startswith(site_prefix + '11.') for line in lines)
            target_net = any(marker in lines for marker in (
                'GTX_CHANNEL_3_X309Y306.GTXE2_CHANNEL_TXOUTCLK_3.GTXE2_CHANNEL_GTTXOUTCLK_3',
                'CMT_TOP_R_LOWER_B_X8Y217.CMT_LR_LOWER_B_MMCM_CLKIN1.CMT_R_LOWER_B_CLK_IN1_HCLK'))
            block = '\n'.join(lines)
            (allowed if target_site or target_net else rest).append(block)
        return Counter(rest), Counter(allowed)
    old, old_target = partition(baseline); new, new_target = partition(candidate)
    removed, added = old - new, new - old
    def inventory(counter):
        return [{'sha256': hashlib.sha256(block.encode()).hexdigest(), 'count': count,
                 'lines': len(block.splitlines()), 'first_line': block.splitlines()[0]}
                for block, count in sorted(counter.items())]
    lines = set(candidate.splitlines())
    target = site_prefix + '11.IN_USE' in lines and site_prefix + '4.IN_USE' not in lines
    def site_config(text, index):
        prefix = site_prefix + index + '.'
        return {line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)}
    same_cell_config = site_config(baseline, '4') == site_config(candidate, '11')
    collateral = sum(removed.values()) + sum(added.values())
    return {'target_site_realized': target, 'collateral_changed_blocks': collateral,
            'target_buffer_configuration_unchanged': same_cell_config,
            'candidate_accepted': target and same_cell_config and collateral == 0,
            'removed_collateral': inventory(removed), 'added_collateral': inventory(added),
            'removed_target': inventory(old_target - new_target),
            'added_target': inventory(new_target - old_target),
            'limitations': 'no routed checkpoint; block/configuration comparison is not complete named-cell placement or timing proof'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, required=True,
                        help='prospective persistent output; this tool does not create or build it')
    args = parser.parse_args()
    result = preflight()
    result['planned_argv'] = route_command(args.output_directory)
    try:
        result['disk'] = admit_disk(args.output_directory.parent)
        result['status'] = 'PREFLIGHT_PASS_NOT_BUILT'
    except RuntimeError as error:
        result.update(status='BLOCKED_BUILD_DISK', error=str(error))
    print(json.dumps(result, indent=2))
