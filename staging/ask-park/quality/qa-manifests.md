# QA candidate and target manifest contract

Candidate manifests exist before target mutation. Target manifests exist only
after a target receipt and reference the candidate digest. Both are JSON data
model records; YAML examples are explanatory only.

## Canonical digest

The validator removes top-level `digest`, rejects duplicate keys, rejects
non-JSON values/NaN/infinities and sensitive/private fields, canonicalizes the
remaining JSON object with deterministic JCS-compatible UTF-8 bytes, and
SHA-256 hashes those bytes. The manifest persists only `sha256:<64 hex>`.
This S10 profile uses integers, booleans, strings, arrays, and objects only;
floating-point JSON numbers are rejected so every implementation shares the
same RFC 8785-compatible number boundary.

## Candidate

`kind: qa-candidate` binds issue contract/version, origin module, source SHA,
lockfile/build/native/runtime/package digests, predecessor receipt aliases,
QA-1 evidence hashes, and an exact evidence mode.

## Target

`kind: qa-target` binds `candidate_manifest_digest`, deployment receipt,
environment-contract alias, platform version, upload note, live index/assets
when applicable, and predecessor receipt aliases. It cannot stand alone.

Pre-target results bind candidate only. Applicable post-target results bind both
candidate and target. An identity change invalidates the result; it never
silently reuses an older manifest.

Evidence mode is exactly `sanitized-persisted`, `ephemeral-only`, or
`approved-store-reference`. `ephemeral-only` records no persistent evidence
reference. Approved-store references require an audience, retention/deletion,
access-control, and a redacted reference.
