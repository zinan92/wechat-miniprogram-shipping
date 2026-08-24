# Build software receipt contract

The Build receipt is a causal software observation. It binds the candidate to
an accepted issue and source identity; it does not authorize deployment or
prove a target environment.

Every receipt names the source SHA that produced the candidate and states what
that source SHA cannot prove.

The issue contract is the immutable boundary that authorizes the Build slice;
the receipt does not create or rewrite that issue contract.

## Required shape

```yaml
schema_version: 1
module: build
status: verified-software | blocked-external | invalid
issue_ready: true | false
issue_contract_id: stable alias
source_sha: named SHA identity
service_boundary:
  page_facing_api: [method names]
  mock_api: [method names]
  cloud_api: [method names]
  mock_result_shapes: {method: stable result shape alias}
  cloud_result_shapes: {method: stable result shape alias}
  mock_error_codes: [stable domain codes]
  cloud_error_codes: [stable domain codes]
plan_boundary:
  plan_receipt_status: valid | missing | invalid
  issue_contract_status: accepted | missing | changed
  code_work_authorized: true | false
  cloudbase_claim: false
authorization:
  unknown_role: deny
  missing_role: deny
  suspended_state: deny
  expired_state: deny
state_machine:
  fail_closed: true
  stable_error_codes: [domain codes]
ordered_content:
  blocks:
    - position: 0
      kind: text | image
      alias: stable content alias
content_contract:
  version: content/vN
  capabilities: [parsed capabilities]
  version_source: parsed-capabilities
  extension_hint: ignored
first_party_assets:
  - alias: stable asset alias
    source: redacted reference
    digest: sha256:...
software_gates:
  tests: pass | fail | blocked
  audit: pass | fail | blocked
  secret_scan: pass | fail | blocked
  diff_check: pass | fail | blocked
unverified_assumptions: [platform facts not proven by Build]
evidence_claims: [verified-software]
evidence_limitations: [what this receipt cannot prove]
receipt:
  receipt_id: build-rN
  module: build
  predecessor_receipt_ids: [plan receipt alias]
human_gate_required: true | false
```

## Rules

- `issue_contract_id` and `source_sha` are required before Build work starts.
  `issue_ready: false` stops the module; it does not invite issue creation from
  inside Build.
- `mock_api` and `cloud_api` are equal page-facing method sets. Adapter
  internals may differ, but `mock_result_shapes`/`cloud_result_shapes` and
  `mock_error_codes`/`cloud_error_codes` are equal.
  These result shapes are part of the software receipt's parity evidence.
- `plan_boundary` must show an accepted issue and valid Plan receipt before
  `code_work_authorized` becomes true. Missing/changed Plan evidence stops
  Build before code work; `cloudbase_claim` is always false in this receipt.
- Unknown role, missing role, suspended state, and expired membership deny.
  Authorization is fail-closed and never derived from a client assertion.
- `ordered_content.blocks` is the sole order-bearing representation for
  interleaved content. Arrays of text and images plus a guessed merge order do
  not satisfy the contract.
- `content_contract.version_source` is `parsed-capabilities`. File extensions
  are a hint only and cannot select a contract version.
- Durable assets use first-party aliases and full SHA-256 digests. The receipt
  persists no complete remote URL or private target.
- `verified-software` proves local candidate behavior and gates only. It cannot
  prove CloudBase health, uploaded Experience, Simulator/Device acceptance,
  payment, review, or formal Release.
- `blocked-external` requires a named human gate in the surrounding incident or
  state record; it never stores the missing credential.
