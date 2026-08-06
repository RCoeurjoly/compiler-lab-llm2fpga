#!/usr/bin/env bash
set -u

git rev-parse HEAD && nix --version && nix develop -c bash -c 'python --version; circt-opt --version; mlir-opt --version; verilator --version; yosys -V'
nix build .#tinystories-representative-core-w4a8-pytorch-exported --no-link --print-out-paths -L
nix build .#tinystories-representative-core-w4a8-linalg --no-link --print-out-paths -L
nix develop -c python -m unittest tests.test_torch_mlir_fingerprint tests.test_pipeline_clarity -v
nix build github:NixOS/nixpkgs/b134951a4c9f3c995fd7be05f3243f8ecd65d798#python311Packages.pytest --no-link
PYTHONPATH=/nix/store/wiivwk558q3nj8xnzyc901dsc5c8fqf4-python3.11-pytest-8.1.1/lib/python3.11/site-packages:/nix/store/g48903rpbx6czj8fdmjckxsn7ns4xi3b-python3.11-pluggy-1.4.0/lib/python3.11/site-packages:/nix/store/x86vbwafzpwk6nhcpgvfbyyma9ajp1b8-python3.11-iniconfig-2.0.0/lib/python3.11/site-packages:/nix/store/dkphwn70lhdmazrl4zdnj63gy0yw4qfj-python3.11-packaging-24.0/lib/python3.11/site-packages nix develop -c python -m pytest -q
nix develop -c python -m py_compile tests/test_rc_observable_driver.py
nix build .#tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-calyx-native-sv --no-link --print-out-paths -L
sha256sum /nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv/sv/main.sv && wc -c /nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv/sv/main.sv
nix develop -c verilator --lint-only --timing --Wno-fatal --top-module main /nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv/sv/main.sv
nix develop -c yosys -p 'read_verilog -sv /nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv/sv/main.sv; hierarchy -check -top main; synth -top main; stat'
