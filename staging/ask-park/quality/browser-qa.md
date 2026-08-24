# Browser Web QA contract

Browser QA uses the built-in Browser first and separates QA-1 candidate render
from QA-2 target render. S12 tests use raw localhost fixture records only; they
do not access private browser storage, production Hosting, or live mutation.

## QA-1 and QA-2

- QA-1 binds the committed candidate SHA, issue/forbidden paths, tests,
  security/diff gates, and equivalent before/after route matrix.
- QA-2 reads the target index/JS/CSS identity, auth mode, deep links, SPA
  fallback, mock markers, and target render matrix. Candidate/target digests
  must match the candidate/target manifests.
- Missing Browser is `qa-prerequisite-missing`, never `QA_BLOCKED`.
- A stale bundle, mock marker, auth drift, broken deep link, or missing matrix
  state is `QA_FAIL` with observable findings. It is not repaired by wording.

## Matrix

Every affected and shared route records route, viewport, role, data state,
loading/empty/error/locked/long-title/narrow-screen/accessibility-name/tap-target
state, tool/runtime, before/after hashes, source identity, and final-compile
provenance. Historical before exceptions never excuse missing after evidence.

## Hermetic adapter

The S12 adapter compares immutable candidate raw assets with a swappable target
record. It emits raw identity/drift findings and zero network/filesystem/provider
events. It never substitutes DOM/source inspection for rendered evidence and
never edits a candidate.
