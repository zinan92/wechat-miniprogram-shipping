# DevTools Mini Program QA contract

DevTools QA uses Computer Use/WeChat Developer Tools for the exact project and
records raw events. S13 tests use a record/replay adapter only; no real upload,
QR, iPhone, platform mutation, or private profile storage is touched.

## Raw event sequence

`project-open → compile → screenshot → upload-note → platform-readback →
final-compile` binds source SHA, tool/base-library/device/route/state, upload
note/candidate digest, platform read-back, and final compile provenance.

The evaluator detects duplicate title, one-character wrapping, double safe
area, stale copy/package, alignment, removed controls, and missing final
compile. Simulator evidence never produces `verified-device`; missing DevTools
or Computer Use is `qa-prerequisite-missing`.

## Matrix and evidence

Affected/shared routes cover loading, empty, error, locked, English/Chinese
long-title, narrow-screen, accessibility-name, and tap-target states. Every
sanitized before/after capture is tied to the route, viewport/device, role,
state, tool/runtime, source/package identity, and final compile receipt.

## Hermetic negative control

The raw adapter asserts zero external network/platform mutation and derives
decisions from events, not a prose verdict. Pass → seed a known render/package/
provenance defect → `QA_FAIL` with sanitized evidence → restore → pass keeps
the candidate SHA unchanged. Weaker screenshots never retain a stronger claim.
