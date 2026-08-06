#!/usr/bin/env bash
set -u

sha256sum survey/protocol.md survey/build/deep_review.csv survey/build/artifact_inventory.csv survey/build/repository_audit.csv
if test -d /tmp/llm2fpga-task6-r7-receipt-source/.git; then git -C /tmp/llm2fpga-task6-r7-receipt-source fetch --quiet origin 3b3e98fabbca7987809c681244076a646af519b9; else git clone --filter=blob:none --no-checkout https://github.com/Edwina1030/TinyTransformer4TS.git /tmp/llm2fpga-task6-r7-receipt-source; fi && git -C /tmp/llm2fpga-task6-r7-receipt-source checkout --detach 3b3e98fabbca7987809c681244076a646af519b9 && git -C /tmp/llm2fpga-task6-r7-receipt-source rev-parse HEAD && git -C /tmp/llm2fpga-task6-r7-receipt-source status --short
python3 -c "from pathlib import Path; r=Path('/tmp/llm2fpga-task6-r7-receipt-source'); req=(r/'requirements.txt').read_text(); dep=next(x for x in req.splitlines() if x.startswith('git+ssh://')); ref=dep.rsplit('@',1)[-1]; immutable=len(ref)==40 and all(c in '0123456789abcdef' for c in ref.lower()); marker=chr(36)+'{'; templates=list((r/'models/quant').glob('*.tpl.vhd')); print('r7_external_dependency='+dep); print('r7_external_dependency_immutable='+str(immutable).lower()); print('r7_templates_fully_rendered='+str(not any(marker in p.read_text() for p in templates)).lower())"
GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10' git ls-remote git@github.com:es-ude/elastic-ai.creator.git add-linear-quantization
python3 -m py_compile /tmp/llm2fpga-task6-r7-receipt-source/models/quant/design.py /tmp/llm2fpga-task6-r7-receipt-source/hw_converter/convert2hw.py
cd /tmp/llm2fpga-task6-r7-receipt-source && python3 -c 'import hw_converter.convert2hw'
nix develop -c bash -c 'command -v ghdl; ghdl -a /tmp/llm2fpga-task6-r7-receipt-source/models/quant/transformer.tpl.vhd'
python3 -c "from pathlib import Path; t=(Path('/tmp/llm2fpga-task6-r7-receipt-source')/'README.md').read_text(); print('r7_causal_lm_interface='+str('causal' in t.lower() and 'decode' in t.lower()).lower()); print('r7_declared_workload=time_series')"
