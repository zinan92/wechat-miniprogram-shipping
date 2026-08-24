# Release receipt contract

The Release receipt is the final causal record. It keeps payment, review, and
formal release truth separate and never stores credentials or routing commands.

## Required shape

```yaml
schema_version: 1
module: release
status: released | failed | blocked-external
project_state: active | released
issue_contract_id: stable alias
predecessor_receipt_ids: [Build, CloudBase, Experience, Device aliases]
version_binding:
  source_sha: sha256:...
  experience_version_alias: stable alias
  device_version_alias: stable alias
  matches_predecessors: true | false
payment:
  applicability: required | not-applicable
  provider_truth: verified | unavailable | mismatch | not-applicable
  server_verification_ref: redacted:... | null
  not_applicable_reason: null | explicit reason
review:
  result: pass | fail | blocked | not-applicable
  readback_ref: redacted:... | null
release_readback:
  result: pass | fail | blocked | not-applicable
  released_version_alias: stable alias | null
  readback_ref: redacted:... | null
smoke:
  result: pass | fail | blocked | not-applicable
  evidence_ref: redacted:... | null
human_authorizations:
  - gate_id: stable gate alias
    schema_version: 1
    contract_version: ask-park.human-gate/v1
    state: authorized | executed | read-back | awaiting-human | denied | expired
    action_type: payment | legal | review | formal-release
    action_scope: stable scope alias
    authorizing_role: owner | reviewer | operator
    requested_at: ISO-8601
    authorized_at: ISO-8601 | null
    evidence_ref: redacted:...
    authority_basis: non-technical decision text
predecessor_bindings:
  experience: {receipt_id, source_sha, version_alias}
  device: {receipt_id, source_sha, version_alias}
unproven_claims: [explicit limitations]
receipt:
  # Full S01 generic module receipt: source/issue/applicability,
  # artifact/package/target, invalidation rules, issued_at, evidence refs.
  receipt_id: release-rN
  module: release
  status: valid | invalid
```

## Rules

- Applicable payment requires provider/server truth bound to owner, amount,
  payer, transaction, and event identity. A client callback never grants a
  membership or release claim.
- `payment.applicability: not-applicable` requires a reason and still requires
  Review and formal Release gates when the project target includes them.
- `review.result: pass` is a platform review claim only. `release_readback` is
  a separate formal release read-back claim and must match the Experience/Device version
  binding.
- `project_state: released` is legal only with review/read-back/smoke pass,
  required human authorizations, and a valid generic S01 receipt. Upload or
  review approval alone cannot set it.
- A version mismatch, stale predecessor, payment mismatch, or smoke failure
  keeps the project active and routes to Diagnose; no blind retry is inferred.
- Human authorization records contain only redacted references and explicit
  non-technical authority basis. Each record is a complete S01 human-gate
  record and must pass the shared validator; technical access is never
  authorization.
- `version_binding` is derived from the recorded Experience/Device
  `predecessor_bindings`, not from a free-standing `matches_predecessors` claim.
