"""Audit actual emitted JSON connectivity, not recipe text or success markers."""
import json
import sys
from pathlib import Path

before, after = (json.loads(Path(p).read_text()) for p in sys.argv[1:])
def implemented_modules(design):
    return {name for name, module in design['modules'].items()
            if not any(int(module.get('attributes', {}).get(kind, '0'), 2)
                       for kind in ('blackbox', 'whitebox'))}

assert implemented_modules(before) == implemented_modules(after), 'implementation module set'
converted = unchanged = modules = 0
for name, original in before['modules'].items():
    if int(original.get('attributes', {}).get('blackbox', '0'), 2):
        continue  # Library declarations are reloaded, not implementation cells.
    current = after['modules'][name]
    modules += 1
    assert original['attributes'] == current['attributes'], ('module attributes', name)
    assert set(original['ports']) == set(current['ports']), ('ports', name)
    bit_map = {}
    reverse = {}

    def bind(a, b):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            if isinstance(x, str):
                assert x == y, ('constant', name, x, y)
            else:
                assert isinstance(y, int)
                assert bit_map.setdefault(x, y) == y, ('inconsistent bit', name, x)
                assert reverse.setdefault(y, x) == x, ('merged bits', name, y)

    for port, p in original['ports'].items():
        q = current['ports'][port]
        assert p['direction'] == q['direction']
        bind(p['bits'], q['bits'])
    for net, p in original['netnames'].items():
        bind(p['bits'], current['netnames'][net]['bits'])

    def mapped(bits):
        return [bit_map[b] if isinstance(b, int) else b for b in bits]

    assert set(original['cells']) == set(current['cells']), ('cell names', name)
    consumers = {}
    for cell_name, cell in current['cells'].items():
        for port, bits in cell['connections'].items():
            if cell.get('port_directions', {}).get(port) in ('input', 'inout'):
                for bit in bits:
                    if isinstance(bit, int):
                        consumers.setdefault(bit, []).append((cell_name, port))
    for cell_name, cell in original['cells'].items():
        new = current['cells'][cell_name]
        if cell['type'] != 'RAM64X1S':
            expected = dict(cell)
            expected['connections'] = {p: mapped(v) for p, v in cell['connections'].items()}
            assert expected == new, ('unintended cell change', name, cell_name)
            unchanged += 1
            continue
        assert new['type'] == 'RAM64X1D'
        effective = dict(before['modules']['RAM64X1S']['parameter_default_values'])
        effective.update(cell['parameters'])
        assert new['parameters'] == effective, ('effective RAM parameters', cell_name)
        for port in ('D', 'WCLK', 'WE', 'A0', 'A1', 'A2', 'A3', 'A4', 'A5'):
            assert mapped(cell['connections'][port]) == new['connections'][port]
            assert new['port_directions'][port] == 'input'
        assert mapped(cell['connections']['O']) == new['connections']['SPO']
        assert new['port_directions']['SPO'] == 'output'
        for index in range(6):
            assert new['connections'][f'DPRA{index}'] == mapped(cell['connections'][f'A{index}'])
        assert all(not consumers.get(b) for b in new['connections']['DPO'])
        assert not any(set(p['bits']) & set(new['connections']['DPO'])
                       for p in current['ports'].values())
        converted += 1
assert converted == 64, converted
print(f'PASS: {modules} implementation modules; {unchanged} other cells unchanged modulo bit IDs; '
      f'{converted} RAM conversions preserve every INIT/clock/write/address/data/output connection; DPO unused.')
print('Scope: actual netlist connectivity audit, not temporal primitive simulation, timing or board inference.')
