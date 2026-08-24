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

The S12 adapter starts two localhost HTTP fixture servers: an immutable
candidate server and a swappable target server. It compares raw responses,
emits sanitized before/after capture records and raw identity/drift findings,
and records zero network outside the two localhost servers plus zero
filesystem/provider mutation events. It never
substitutes DOM/source inspection for rendered evidence and never edits a
candidate.

The negative control is pass → inject stale/mock/deep-link drift → `QA_FAIL`
with evidence → restore target → pass; the candidate source SHA remains
unchanged throughout.

`capture_qa1()` produces Browser-first sanitized before/after records for the
affected/shared matrix. `run_hermetic_qa2()` keeps localhost transport refs
ephemeral and returns only redacted server aliases in its result; raw response
hashes and candidate/compile identity are checked against each matrix row.
