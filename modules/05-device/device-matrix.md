# Device Acceptance matrix contract

The Device receipt binds human/device observations to an exact Experience
version. It keeps server/projection/HTTP/pixels/expiry evidence separate and
never contains routing instructions.

Simulator evidence is a useful local observation but is never a
`verified-device` claim.

## Required shape

```yaml
schema_version: 1
module: device
status: verified-device | failed | blocked-external | not-applicable
experience_receipt_id: experience receipt alias
experience_version_alias: stable version alias
matrix:
  - device_class: ios | android
    device_profile: redacted device profile alias
    role: admin | member | guest
    task: bounded task alias
    experience_version_alias: exact bound version
    result: pass | fail | blocked | not-applicable
    observed_at: ISO-8601
evidence_ladder:
  projection:
    result: pass | fail | blocked | not-applicable
    proves: projection/read state
    cannot_prove: pixels/device behavior
  http-reachability:
    result: pass | fail | blocked | not-applicable
    proves: response reachability/status
    cannot_prove: authorization or pixels
  pixels-layout:
    result: pass | fail | blocked | not-applicable
    proves: observed device pixels/layout
    cannot_prove: other devices/accounts
  expiry-fallback:
    result: pass | fail | blocked | not-applicable
    proves: observed expiry/retry/fallback behavior
    cannot_prove: unrelated routes
weak_network:
  retry_policy: bounded policy
  expiry_policy: bounded policy
client_logs:
  - source: client
    request_id: redacted request alias
    evidence_ref: redacted:...
attributed_client_events: [client-only event aliases]
client_log_summary:
  excluded_sources: [cli, server]
human_gate:
  required: true | false
  ref: redacted alias or null
unproven_claims: [explicit limitations]
receipt:
  # Full S01 generic module receipt with source/issue/predecessors,
  # artifact/package/target, invalidation rules, timestamp, and evidence refs.
  receipt_id: device-rN
  module: device
  status: valid | invalid | not-applicable
```

## Rules

- Every required matrix cell binds the exact Experience version, device class,
  role, task, and observation time. Missing cells are not a pass.
- Projection, HTTP, pixels/layout, and expiry/fallback are independent rungs.
  Higher-level claims require their own observed rung.
- CLI calls and server logs are excluded from real-client attribution. A
  request ID is necessary but does not prove pixels.
- `blocked-external` is legal after applicable automation passes and only a
  human/device/account action remains. The human gate is the smallest required
  action and uses a redacted reference.
- The nested `receipt` is a complete S01 generic receipt and must pass the
  shared validator. It records causal identity and invalidation but never
  contains routing or `next_module`.
- `verified-device` never means all devices/accounts. It is scoped to the
  matrix cells recorded in the receipt; later scope changes stale the receipt.
