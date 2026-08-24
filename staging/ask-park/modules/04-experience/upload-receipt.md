# Experience upload receipt contract

The Experience receipt binds a named source version to a compiled/uploaded
package and target read-back. It is not a review or Release receipt.

The source SHA is the identity of the tree compiled by DevTools; an upload
cannot replace or broaden that source identity.

## Required shape

```yaml
schema_version: 1
module: experience
status: verified-experience | failed | blocked-external | not-applicable
issue_contract_id: stable alias
build_receipt_id: build receipt alias
cloudbase_receipt_id: cloudbase receipt or not-applicable alias
source_sha: sha256:...
project_identity:
  project_alias: stable alias
  appid_ref: redacted:...
  environment_ref: redacted:...
environment_contract_alias: stable alias
compile:
  result: pass | fail | blocked | not-applicable
  source_sha: sha256:...
simulator:
  result: pass | fail | blocked | not-applicable
  limitation: Simulator is not Device Acceptance
upload:
  result: pass | fail | blocked | not-applicable
  attempted: true | false
  package_digest: sha256:... | null
target_readback:
  result: pass | fail | blocked | not-applicable
  target_alias: stable alias
  package_digest: sha256:... | null
version:
  version_alias: stable version alias
  note_alias: stable note alias
  observed_at: ISO-8601
tool:
  name: wechat-devtools
  version: recorded version
  base_library: recorded version
clean_tree: true | false
ignored_config:
  restored: true | false
operator_state:
  preserved_before_check: true | false
  restored_after_check: true | false
  unsaved_content_loss: false | true
  evidence_ref: redacted:...
review:
  result: pass | fail | blocked | not-applicable
release:
  result: pass | fail | blocked | not-applicable
backend_only: true | false
client_contract_unchanged: true | false
not_applicable_reason: null | explicit reason
impact_analysis: null | explicit evidence
evidence_limitations: [what this receipt cannot prove]
receipt:
  # Full S01 module receipt: receipt_type, schema/contract version, source,
  # issue, applicability, artifact/package/target, invalidation_rules,
  # issued_at, evidence_refs, and predecessor_receipt_ids are required.
  receipt_id: experience-rN
  module: experience
  status: valid | invalid | not-applicable
  predecessor_receipt_ids: [Build, CloudBase aliases]
```

## Rules

- `verified-experience` requires matching source/package identity between
  Compile, Upload, and target read-back, a clean tree, and restored ignored
  configuration. Operator state is preserved before the DevTools check and
  restored afterward; unsaved-content loss blocks upload.
- Compile and Simulator are local observations. Upload proves a named package
  exists at a target only after target read-back; neither proves review,
  Release, payment, or physical-device behavior.
- `review` and `release` remain `not-applicable` in an Experience receipt when
  those gates have not run. Their absence is not approval.
- Backend-only `not-applicable` requires `backend_only: true`,
  `client_contract_unchanged: true`, a reason, impact analysis, and a matching
  not-applicable generic receipt. It does not skip later target-independent
  gates that remain in scope.
- A changed source/package/environment/tool identity makes the receipt stale
  and returns to Ask Park for causal invalidation. No upload retry is inferred.
- The nested `receipt` is a complete S01 generic module receipt and must pass
  the shared validator; this module adds the Experience observations around it.
- All identity/target values are aliases or `redacted:` references. A real QR,
  AppID, environment ID, or account identity never enters this record.
