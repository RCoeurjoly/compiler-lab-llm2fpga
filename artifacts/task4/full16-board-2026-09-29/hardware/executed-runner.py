"""Three SRAM configurations of the qualified compiler candidate; always restore baseline."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--bitstream-dir', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--preflight-only', action='store_true')
args = parser.parse_args()
here = Path(__file__).resolve().parent
root = next(p for p in here.parents if (p / 'TinyStories').is_dir())
candidate_dir = args.bitstream_dir.resolve()
assert (candidate_dir / 'receipt.json').is_file(), 'Candidate lacks a qualified full16 conversion receipt'
proof = json.loads((candidate_dir / 'receipt.json').read_text())
assert proof['status'] == 'converted-native-modes-verified-not-hardware-accepted'
assert proof['qualified_route'] == '/nix/store/vl799qzyilfyjyiysvz06klrz487h13n-compiler-full16-two-rom-placement-route-90m'
assert proof['bram_modes']['decoded_physical_bits_verified']
assert proof['bram_modes']['bram36_instances'] == 813
assert proof['bram_modes']['projection_mode_features'] == 29
candidate = candidate_dir / 'model.bit'
assert hashlib.sha256(candidate.read_bytes()).hexdigest() == proof['bitstream_sha256']
oracle = json.loads((root / 'artifacts/reference/tinystories-1m-fixed-point-continuation-oracle.json').read_text())
authority = json.loads(Path('/nix/store/fjwywimzsgziwx7vs30hq875ps67bvkp-compiler-full16-preserved-run0-semantic-receipt/receipt.json').read_text())
assert authority['status'] == 'passed' and oracle['artifact_sha256'] == authority['oracle_sha256']
assert hashlib.sha256(json.dumps({k: v for k, v in oracle.items() if k != 'artifact_sha256'},
    sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() == oracle['artifact_sha256']
prompt = oracle['token_contract']['initial_context']
expected = [step['selected_token']['value'] for step in oracle['steps']]
assert prompt == [7454, 2402, 257, 640] and len(expected) == 16 and expected == authority['tokens'][0]
routing = json.loads((candidate_dir / 'routing-receipt.json').read_text())
assert routing['synthesis_receipt']['semantic_gate']['tokens'][0] == expected
baseline = Path('/home/roland/compiler-lab-llm2fpga/result-compiler-first-token-signext-20260909/tinystories-signext-fixed.bit')
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == '2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a'
if args.preflight_only:
    print('Qualified full16 image, decoded modes, oracle and baseline preflight passed', flush=True)
    raise SystemExit(0)
sys.path.insert(0, str(root))
sys.path.insert(0, '/home/roland/LLM2FPGA/scripts/task6')
from scripts.pipeline.infer_tinystories_generation_jtag import infer_generation
from scripts.pipeline.infer_tinystories_first_token_jtag import infer
ftdi = importlib.import_module('read_jtag_debug_ftdi_bitbang')
jtag = importlib.import_module('read_jtag_debug_xvc')
loader = '/nix/store/39xij3c8kp29nkldm436g8im3rqb8jaj-openfpgaloader-3ae5e5e-bpi-full-verify/bin/openFPGALoader'
out = args.output.resolve()
out.mkdir(exist_ok=False)
shutil.copyfile(__file__, out / 'executed-runner.py')
receipt = dict(status='pending', candidate=str(candidate), candidate_sha256=proof['bitstream_sha256'],
    oracle_sha256=oracle['artifact_sha256'], programming=[], runs=[],
    claims=dict(bpi_changed=False, full_timing_qualification=False),
    checker_sha256=hashlib.sha256((root / 'scripts/pipeline/infer_tinystories_generation_jtag.py').read_bytes()).hexdigest(),
    transport_sha256={Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (ftdi, jtag)})

def save():
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

def program(image, label):
    assert Path('/sys/bus/thunderbolt/devices/1-1/authorized').read_text().strip() == '0'
    assert not Path('/sys/bus/pci/devices/0000:42:00.0').exists()
    command = [loader, '-c', 'digilent_hs3', '--ftdi-serial', '210299BF3824', '--freq', '1000000', '-m', str(image)]
    event = dict(label=label, command=command, image_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    receipt['programming'].append(event)
    save()
    start = time.monotonic()
    with (out / f'{label}-program.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=360)
    event.update(returncode=result.returncode, elapsed_seconds=time.monotonic() - start)
    save()
    result.check_returncode()
    print(label + ': independent SRAM programming completed', flush=True)

def connect():
    return ftdi.FtdiMpsseJtag(serial='210299BF3824', vid=0x0403, pid=0x6014, freq_hz=1000000, tdo_bit=7)

try:
    for index in range(3):
        program(candidate, f'run{index}')
        client = connect()
        try:
            result = infer_generation(client, clock_tms=jtag.clock_tms, reset_tap=jtag.reset_tap,
                shift_ir=jtag.shift_ir, prompt=prompt, expected_tokens=expected, timeout=300)
        finally:
            client.close()
        receipt['runs'].append(result)
        receipt['two_token_checkpoint_passed'] = receipt.get('two_token_checkpoint_passed', False) or result['tokens'][:2] == [11, 612]
        save()
        print(f'run{index}: ' + json.dumps({k: v for k, v in result.items() if k != 'transactions'}), flush=True)
        commands = [int(t['command'], 16) for t in result['transactions']]
        assert [c for c in commands if c >> 60 == 1] == [0x1000000000000000 | (i << 16) | word for i, word in enumerate(prompt)]
        assert commands.count(0x2000000000000000) == 1
        permitted = {0x2000000000000000, 0x3000000000000000, 0x5000000000000000}
        permitted.update(0x1000000000000000 | (i << 16) | word for i, word in enumerate(prompt))
        permitted.update(0x6000000000000000 | (i << 16) for i in range(4))
        permitted.update(0x4000000000000000 | i for i in range(16))
        assert all(command in permitted for command in commands), 'Unexpected host command'
        assert result['status'] == 'passed' and result['tokens'] == expected and result['elapsed_seconds'] <= 300
except Exception as error:
    receipt['candidate_error'] = repr(error)
    save()
finally:
    try:
        program(baseline, 'restored-first-token')
        client = connect()
        try:
            receipt['baseline_restoration'] = infer(client, clock_tms=jtag.clock_tms,
                reset_tap=jtag.reset_tap, shift_ir=jtag.shift_ir, prompt=prompt, expected_token=11, timeout=300)
        finally:
            client.close()
        print('baseline restoration: ' + json.dumps({k: v for k, v in receipt['baseline_restoration'].items() if k != 'transactions'}), flush=True)
    except Exception as error:
        receipt['restoration_error'] = repr(error)
    receipt['status'] = 'passed' if (len(receipt['runs']) == 3 and not receipt.get('candidate_error')
        and all(r['status'] == 'passed' for r in receipt['runs'])
        and receipt.get('baseline_restoration', {}).get('status') == 'passed') else 'failed'
    save()
raise SystemExit(0 if receipt['status'] == 'passed' else 1)
