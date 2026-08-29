---
status: accepted
supersedes: RC-first active milestones in ADR-0002 and ADR-2026-07-16-rc-vertical-slice-fixture
---

# Use the full TinyStories-1M contract as the active compiler reference path

The active compiler/reference comparison will target the full TinyStories-1M
contract used by the validated kev-gpt implementation. The existing
Representative Core remains historical research and may be used opportunistically
for isolated unit tests, but it is not a milestone, acceptance gate, or evidence
of TinyStories-1M reproduction. This removes an unproven intermediate model from
the critical path and keeps the compiler comparison faithful to the actual
golden reference.
