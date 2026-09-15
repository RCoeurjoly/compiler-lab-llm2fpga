"""Generate a Wishbone trace for the authenticated 4 KiB Q table."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path

def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--image", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    image = bytes(int(x.strip(), 16) for x in a.image.read_text().splitlines() if x.strip())[:4096]
    chunks = [image[i:i+16].ljust(16, b"\0") for i in range(0, len(image), 16)]
    lines = [f"W {i:08x} {int.from_bytes(chunk, 'little'):032x} ffff 0 0 0" for i, chunk in enumerate(chunks)]
    addresses = list(range(len(chunks))) + list(range(len(chunks))) + [0, len(chunks)-1]
    lines.extend(f"R {i:08x} 0 ffff 0 {int.from_bytes(chunks[i], 'little'):032x} 0" for i in addresses)
    a.output.write_text("\n".join(lines) + "\n")
    print(f"transactions={len(lines)} sha256={hashlib.sha256(a.output.read_bytes()).hexdigest()}")

if __name__ == "__main__":
    main()
