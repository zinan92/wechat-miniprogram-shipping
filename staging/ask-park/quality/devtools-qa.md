# DevTools Mini Program QA contract

DevTools QA is the native Mini Program branch of the independent QA Agent. It
uses Computer Use with WeChat Developer Tools for the exact project, then
records raw events and sanitized evidence. S13 tests use an ephemeral
record/replay adapter only: no real upload, QR, iPhone, platform mutation, or
private profile storage is touched.

## QA-1: candidate render

Before asking Park to inspect a change, the worker must:

1. Run the ordinary mock/release gates and preserve the candidate source SHA.
2. Open the exact project directory in WeChat Developer Tools; do not infer the
   project from a similarly named tab.
3. Compile the candidate and record the tool alias, base-library alias,
   `compile_provenance`, and source SHA.
4. Capture the affected and shared routes in the complete matrix below. Each
   screenshot is tied to route, device/viewport, role, data state, state,
   source SHA, screenshot hash, timestamp, and compile provenance.
5. Record observable defects as raw enum values. A worker summary such as
   “looks fixed” is not evidence.

## QA-2: upload/read-back and final compile

When the change is eligible for an experience check, the same candidate must
continue in this order:

`project-open → compile → screenshot → upload-note → platform-readback → final-compile`

The upload note and platform read-back must bind the same candidate digest. The
final compile must bind the candidate source SHA and a final compile
provenance alias. A stale package, stale copy, or final-compile mismatch is a
`QA_FAIL`; it is never repaired by changing the prose report.

## Defects and stop rules

The raw event contract detects duplicate title, one-character wrapping, double
safe area, stale copy/package, alignment, removed controls, and missing final
compile evidence. A screenshot predating the candidate or final compile fails
evidence integrity. Simulator evidence never produces `verified-device` or
physical-device completion. Missing WeChat Developer Tools or Computer Use is
`qa-prerequisite-missing`, not `QA_BLOCKED` and not a pass.

## Required matrix

The matrix includes each affected/shared route plus these states:

`loading`, `empty`, `error`, `locked`, English long-title,
Chinese long-title, `narrow-screen`, `accessibility-name`, and `tap-target`.

Every row records route, viewport/device profile, role, data state, state,
tool, runtime/base library, source identity, screenshot hash, timestamp, and
final-compile provenance. Before/after hashes may be retained only as
sanitized digests; after evidence is always required. Sensitive screenshot
bytes, URLs, OpenIDs, QR/payment data, credentials, and local filenames stay
ephemeral or use an approved governed reference.

## Hermetic adapter and negative control

`run_hermetic_qa()` serves raw events from an ephemeral loopback fixture,
returns only redacted transport references, proves zero external network, and records explicit
`external_network_events: []` and `platform_mutation_events: []`. Decisions
come from raw events and matrix hashes, not an intended verdict field.

The fixture suite proves:

`pass → seed duplicate-title/stale-package/provenance defect → QA_FAIL with
sanitized evidence → restore → pass`,

while the candidate SHA remains unchanged. A weaker screenshot never retains a
stronger claim, and QA never edits the candidate.
