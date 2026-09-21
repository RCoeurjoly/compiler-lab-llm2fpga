#!/usr/bin/env python3
"""Leave the exact Helios/YPCB topology safely isolated for BPI programming."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, Sequence


class IsolationError(RuntimeError):
    """The fail-closed isolation sequence could not be completed."""


def _read(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="ascii").strip().lower()
    except OSError as exc:
        raise IsolationError(f"cannot read {label}: {exc}") from exc


class Controller:
    DOMAIN = "domain1"
    DEVICE = "1-1"
    DEVICE_NAME = "Helios 5S"
    DEVICE_UUID = "c4148780-0010-1ed9-ffff-ffffffffffff"
    ENDPOINT_BDF = "0000:42:00.0"
    ENDPOINT_VENDOR = "0x10ee"
    ENDPOINT_DEVICE = "0x0480"

    def __init__(
        self,
        *,
        thunderbolt_root: Path = Path("/sys/bus/thunderbolt/devices"),
        pci_root: Path = Path("/sys/bus/pci/devices"),
        geteuid: Callable[[], int] = os.geteuid,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        timeout_s: float = 20.0,
    ) -> None:
        self.thunderbolt_root = thunderbolt_root
        self.pci_root = pci_root
        self.geteuid = geteuid
        self.sleep = sleep
        self.monotonic = monotonic
        self.timeout_s = timeout_s

    def _device_path(self) -> Path:
        path = self.thunderbolt_root / self.DEVICE
        if not path.is_dir():
            raise IsolationError(f"exact Helios sysfs device {self.DEVICE} is absent")
        if _read(path / "device_name", "Thunderbolt device name") != self.DEVICE_NAME.lower():
            raise IsolationError("Thunderbolt device name does not match Helios 5S")
        if _read(path / "unique_id", "Thunderbolt device UUID") != self.DEVICE_UUID:
            raise IsolationError("Thunderbolt device UUID does not match the pinned chassis")
        return path

    def _validate_domain(self) -> None:
        domain = self.thunderbolt_root / self.DOMAIN
        if _read(domain / "security", "Thunderbolt security mode") != "user":
            raise IsolationError("refusing non-user Thunderbolt security mode")
        if _read(domain / "deauthorization", "Thunderbolt deauthorization capability") != "1":
            raise IsolationError("Thunderbolt deauthorization is unavailable")

    def _matching_endpoints(self) -> list[str]:
        matches: list[str] = []
        try:
            candidates = list(self.pci_root.iterdir())
        except OSError as exc:
            raise IsolationError(f"cannot enumerate PCI devices: {exc}") from exc
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            vendor = candidate / "vendor"
            device = candidate / "device"
            if not vendor.exists() or not device.exists():
                continue
            if _read(vendor, f"PCI vendor for {candidate.name}") == self.ENDPOINT_VENDOR and _read(
                device, f"PCI device for {candidate.name}"
            ) == self.ENDPOINT_DEVICE:
                matches.append(candidate.name)
        return sorted(matches)

    def _validate_endpoint_topology(self) -> None:
        expected = self.pci_root / self.ENDPOINT_BDF
        if expected.is_dir():
            identity = (
                _read(expected / "vendor", "pinned endpoint vendor"),
                _read(expected / "device", "pinned endpoint device"),
            )
            if identity != (self.ENDPOINT_VENDOR, self.ENDPOINT_DEVICE):
                raise IsolationError(
                    f"unexpected PCI device at {self.ENDPOINT_BDF}: {identity[0]}:{identity[1]}"
                )
        matches = self._matching_endpoints()
        if any(bdf != self.ENDPOINT_BDF for bdf in matches):
            raise IsolationError(f"refusing multiple or relocated 10ee:0480 endpoints: {matches}")

    def _deauthorize(self, path: Path) -> str:
        authorization = path / "authorized"
        if _read(authorization, "Helios authorization") == "0":
            return "already_deauthorized"
        try:
            authorization.write_text("0\n", encoding="ascii")
        except OSError as exc:
            # Some kernels return EINVAL when a racing transition already won.
            if _read(authorization, "Helios authorization") == "0":
                return "already_deauthorized"
            raise IsolationError(f"cannot write Helios authorized=0: {exc}") from exc
        return "deauthorized"

    def _wait_isolated(self, path: Path) -> None:
        deadline = self.monotonic() + self.timeout_s
        last = "transition not observed"
        while self.monotonic() <= deadline:
            authorization = _read(path / "authorized", "Helios authorization")
            endpoints = self._matching_endpoints()
            if authorization == "0" and not endpoints:
                return
            last = f"authorized={authorization}, matching_endpoints={endpoints}"
            self.sleep(0.25)
        raise IsolationError(f"timed out waiting for programming isolation: {last}")

    def isolate(self) -> dict[str, object]:
        if self.geteuid() != 0:
            raise IsolationError("isolation controller must run as root")
        self._validate_domain()
        path = self._device_path()
        self._validate_endpoint_topology()
        action = self._deauthorize(path)
        self._wait_isolated(path)
        return {
            "status": "isolated_for_programming",
            "timestamp": datetime.now().astimezone().isoformat(),
            "device": self.DEVICE,
            "device_name": self.DEVICE_NAME,
            "uuid": self.DEVICE_UUID,
            "authorization": action,
            "endpoint_bdf": self.ENDPOINT_BDF,
            "endpoint": "absent",
        }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print("usage: ypcb-thunderbolt-isolate-for-programming", file=sys.stderr)
        raise SystemExit(2)
    try:
        print(json.dumps(Controller().isolate(), indent=2, sort_keys=True))
    except IsolationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
