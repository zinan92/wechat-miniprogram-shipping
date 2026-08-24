# Ask Park module receipt contract

Module receipts are causal evidence records. They bind a module observation to
the exact source, issue, artifact/package, target alias, and invalidation rules
that made the observation meaningful. A receipt is not a progress message and
does not contain routing instructions.

QA candidate/target manifests, JCS digests, QA results, and screenshot matrix
rows are intentionally out of scope here and belong exclusively to S10. S01
only defines the generic causal primitive used by those later contracts.

## Versioning and status

Every receipt has `schema_version: 1` and
`contract_version: ask-park.receipt/v1`. `status` is one of:

- `valid`: the bound evidence is current and usable for its module;
- `stale`: evidence was once valid but an invalidation trigger changed;
- `invalid`: the observation failed or its causal identity no longer holds;
- `not-applicable`: the approved target explicitly excludes this module.

`not-applicable` must be used together with
`applicability: not-applicable` and `not_applicable_reason`. It still records
the source and issue that made the decision; it is not an omitted gate.

## Receipt shape

```json
{
  "receipt_id": "build-r1",
  "receipt_type": "module",
  "schema_version": 1,
  "contract_version": "ask-park.receipt/v1",
  "module": "build",
  "status": "valid",
  "applicability": "required",
  "source": {
    "repository_alias": "wechat-project",
    "commit_sha": "sha256:..."
  },
  "issue": {"id": "13"},
  "predecessor_receipt_ids": ["plan-r1"],
  "artifact": {
    "kind": "software",
    "alias": "mock-vertical-slice",
    "digest": "sha256:..."
  },
  "package": {
    "kind": "source-tree",
    "alias": "candidate-package",
    "digest": "sha256:..."
  },
  "target": {
    "alias": "local",
    "environment_contract_alias": "local-mock",
    "redacted_ref": "redacted:local-target"
  },
  "invalidation_rules": {
    "on": ["source.commit_sha", "contract_version", "artifact.digest", "package.digest"],
    "downstream_modules": ["cloudbase", "experience", "device", "release"],
    "causal_rewind": false,
    "declared_by": "ask-park"
  },
  "issued_at": "2026-08-24T10:00:00Z",
  "evidence_refs": ["redacted:software-gate-output"]
}
```

The validator requires the causal fields above. `artifact` and `package` are
objects with a stable alias and SHA-256 digest for applicable receipts. For a
not-applicable receipt each is instead an object with `state: not-applicable`
and a reason. Targets follow the same rule; an applicable target requires an
alias, an environment-contract alias, and a `redacted_ref`. The complete target
is resolved inside an approved adapter and is never persisted here.

## Causal identity and invalidation

The source commit, accepted issue, predecessor receipt IDs, artifact/package
digests, redacted target alias, and contract version form the causal identity.
The `invalidation_rules.on` list declares which identity changes make this
receipt stale. `downstream_modules` names only sequential modules. Every
invalidation declaration is owned by `ask-park`; a worker cannot route or
invalidate its successor.

`causal_rewind` is either `false` or an object containing:

```json
{
  "earliest_invalidated_module": "build",
  "reason_code": "source-changed",
  "invalidated_receipt_ids": ["build-r1", "cloudbase-r1"]
}
```

An invalid/stale receipt may carry this declaration. S01 validates that the
shape is safe; S01B performs lifecycle transitions and transitive invalidation.
Receipt reuse is legal only when every causal binding is unchanged and the
module's invalidation rules do not require a fresh observation.

## Persistence boundary

Persist only aliases, digests, timestamps, issue IDs, and `redacted:` evidence
references. Reject complete URLs, absolute paths, environment IDs, AppIDs,
OpenIDs, tokens, credentials, private certificates, QR contents, and customer
data. The validator's output contains only error codes and structural paths so
it is safe to put in CI logs.

`next_module` is forbidden in receipts. A receipt records what was proven; only
Ask Park's router may choose what comes next.
