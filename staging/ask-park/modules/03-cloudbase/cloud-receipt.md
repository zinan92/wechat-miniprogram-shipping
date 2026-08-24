# CloudBase/backend receipt contract

This receipt separates backend observations that are often incorrectly merged
into “deployed”. It is compatible with the generic S01 receipt but keeps
provider identity, target, health, projection, Hosting, and client evidence
distinct.

## Required shape

```yaml
schema_version: 1
module: cloudbase
status: verified-cloud | failed | blocked-external | not-applicable
issue_contract_id: stable alias
build_receipt_id: build receipt alias
source_sha: named source identity
backend_contract_version: backend/vN
permission_runtime_identity:
  permissions_alias: redacted:...
  runtime_alias: stable runtime alias
observed_at: ISO-8601
provider_role: cloudbase | serverless-backend
target_alias: stable target alias
redacted_target_ref: redacted:...
artifact:
  alias: deployed artifact alias
  digest: sha256:...
production_package:
  alias: production package alias
  digest: sha256:...
  clean: true | false
  nested_dev_dependencies: false | true
readiness_checks:
  collections: pass | fail | not-applicable
  indexes: pass | fail | not-applicable
  rules: pass | fail | not-applicable
  runtime: pass | fail | not-applicable
  config: pass | fail | not-applicable
evidence_layers:
  function_upload: pass | fail | not-applicable
  health_readback: pass | fail | not-applicable
  projection_readback: pass | fail | not-applicable
  hosting_readback: pass | fail | not-applicable
  client_evidence: pass | fail | not-applicable
protected_storage:
  access: closed
  short_lived_assets: aliases-only | not-applicable
fallback_public_storage: false
not_applicable_reason: null | explicit reason
impact_analysis: null | explicit client/target impact
invalidation_rules: [source_sha, backend_contract_version, permission_runtime_identity, artifact.digest, production_package.digest, target_alias]
reuse:
  allowed: true | false
  changed_bindings: []
receipt:
  receipt_id: cloudbase-rN
  module: cloudbase
  status: valid | invalid | not-applicable
  predecessor_receipt_ids: [Build receipt alias]
unproven_claims: [explicit limitations]
routing: continue | diagnose | blocked-external
```

## Rules

- `verified-cloud` requires clean packaging, readiness, function upload,
  health, projection, closed storage, and any applicable Hosting/client checks.
- A function upload is not health. CLI health is not client evidence. Hosting
  read-back is not a physical-device result.
- An approved backend-free design uses `status: not-applicable`, a
  `not_applicable_reason`, impact analysis, and a not-applicable receipt. It
  does not skip later Experience/Device/Release decisions when those remain in
  scope.
- Reuse requires unchanged source/package/target/provider/permission/runtime
  identity and unchanged backend contract. `source_sha`,
  `backend_contract_version`, `permission_runtime_identity`, target/package
  digests, and `invalidation_rules` make those bindings explicit. Any drift is
  stale and returns to Ask Park for causal invalidation; `reuse.allowed` is
  false when `changed_bindings` is non-empty.
- Protected storage stays closed. Short-lived authorized assets are represented
  by aliases and `redacted:` references; public storage is never a fallback.
- Provider adapters may differ in commands, but this role contract and receipt
  fields remain stable. No provider credential belongs in the record.
