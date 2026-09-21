# Pinned Task 4 lifecycle runtime (installation plan only)

These two wrapper sources remove Nix/uv/package resolution from the existing
deferred-authorization lifecycle. They do not change its controller, power
script, target plug, off/on checks, or 10/45-second waits. Python uses `-I -B`
to ignore ambient Python paths and avoid changing the frozen runtime's pyc.
There is no new recovery, programming, MMIO, reset, remove or rescan command.

The parent already materialized `tapo==0.9.0` and relocated its complete 23 MiB
venv to `/home/roland/.local/share/ypcb-tapo-runtime/venv`, successfully checked
the import there, then removed `/tmp/ypcb-tapo-preflight`. Do not recreate that
temporary runtime, install dependencies during a hardware run, or run Nix GC.
The continuation authenticates all 123 retained files/symlinks (including
package metadata, native module and existing pyc), plus both interpreter paths,
the installed power script and both installed wrapper bytes. Its tree digest is
SHA-256 of compact JSON `[relative_path, size, file_sha256]` or
`[relative_path, "symlink", target]` rows, sorted by relative path.

| Identity | SHA-256 |
| --- | --- |
| Complete runtime tree | `48f91b0f5cd7d6fa2e60a319006bb172f00671f600cdce8ab3d18b41aacf4cca` |
| System/venv Python executable | `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` |
| Tapo native module | `9f5a5929b3ca2fde91dcd68a76c9ed1a8f3a87fad0d4e99363b7b4de6502c6e8` |
| Tapo 0.9.0 metadata | `9eb886a044c6bc1d3fb582af5d36de5895ba90585e32ff7d3d84506551bc0780` |
| Existing power script | `db25a6bd8efb0da1a7d2dd02ad1cf8252ea241d07f47a8faf38cdee7b9289548` |
| New root wrapper | `fd5204da90cb9df14efe64421062d2309dcaed08517397b8866ea410d1c0ed0f` |
| New unprivileged power wrapper | `a7d88192a14c9e27e5efd9e73c83375fe53e02b7b77f661bb5faeb678eb96c8f` |

## One-time installation (requires separate host-change approval)

These commands are supplied for review; the implementer has not run them.
They only install the two reviewed wrappers. The retained runtime and existing
controller/power script remain untouched; no registry, Nix, uv, network or
hardware command is required. Keep the existing narrow sudo policy unchanged.

```bash
cd /home/roland/compiler-lab-llm2fpga/.worktrees/compiler-micron-integration-exec
sha256sum scripts/host/ypcb/ypcb-thunderbolt-cold-cycle scripts/host/ypcb/ypcb-tapo-cycle
sudo /usr/bin/install -o root -g root -m 0755 scripts/host/ypcb/ypcb-thunderbolt-cold-cycle /usr/local/sbin/ypcb-thunderbolt-cold-cycle
sudo /usr/bin/install -o root -g root -m 0755 scripts/host/ypcb/ypcb-tapo-cycle /usr/local/libexec/ypcb-tapo-cycle
sha256sum /usr/local/sbin/ypcb-thunderbolt-cold-cycle /usr/local/libexec/ypcb-tapo-cycle
```

Do not invoke either wrapper as an installation test: it changes hardware.
Review/compare all printed hashes against the table before authorizing a run.
The old smoke manifest and failed-attempt logs remain historical evidence,
unchanged. The continuation validates their exact old contract separately,
then substitutes only the newly authenticated active root-wrapper identity.
The old smoke harness intentionally cannot authenticate the replaced wrapper.

## Disk and receipt gate

Require at least 72 MiB available before reserving eight physically allocated
1 MiB slots, leaving at least 64 MiB free on both receipt/runtime filesystems.
Recheck the 64 MiB runtime floor immediately before the only cold-cycle.
The allocated reserve is not counted as free space and must not be sparse.
Three slots fund bounded snapshots, four fund primary/emergency worker/parent
receipts, and one is metadata/cleanup margin. Receipts are bounded to 256 KiB;
each slot is released immediately before its corresponding publication. A
terminal ENOSPC turns the result into FAIL and retries publication once using
the separate emergency slot. Existing signal-aware no-overwrite publication
and supervisor process-tree cleanup remain unchanged. No guarantee is made
against storage I/O failure or a hostile writer consuming released capacity.

The fixed runtime is small, but this is not a general 64 MiB dependency-build
budget: dependency resolution is prohibited during the lifecycle. An OS Python,
runtime or wrapper update invalidates authentication and needs fresh review.
The host's shared libraries/stdlib remain the existing host trust boundary.

The continuation requires the externally reviewed literal own SHA through
`--expected-sha256`; both parent and worker verify it and record their actual
hashes. Do not compute a new expected hash from changed code to bypass review.
No hardware continuation is authorized by this installation plan.

## Permanent programming isolation

The replay programmer must leave the exact Helios chassis unauthorized while
the YPCB BPI flash is written.  The repository now provides a fail-closed,
idempotent helper for that transition.  It accepts no arguments, pins Helios
device `1-1` by name and UUID, requires Thunderbolt `user` security with
deauthorization support, accepts only the expected `10ee:0480` endpoint at
`0000:42:00.0`, writes only `authorized=0`, and waits until no matching PCIe
endpoint remains.  It performs no rescan, PCI reset, authorization, power
operation, programming, or MMIO.

Install it once:

```bash
cd /home/roland/compiler-lab-llm2fpga/.worktrees/compiler-micron-integration-exec
sudo scripts/host/ypcb/install-programming-isolation
```

Thereafter the authenticated replay runner performs the transition itself via:

```bash
sudo -n /usr/local/sbin/ypcb-thunderbolt-isolate-for-programming
```

The existing deferred-authorization cold-cycle remains responsible for
power-cycling and restoring authorization after fully verified BPI programming.
