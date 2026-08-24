# QA result contract

QA results are advisory evidence for the independent gate. They do not edit
code or choose Ask Park's current module.

```yaml
kind: qa-result
result: QA_PASS | QA_FAIL | QA_BLOCKED | none
qa_run_id: stable run alias
gate: contract | qa-1 | target | qa-2 | evidence | final
candidate_manifest_digest: sha256:...
target_manifest_digest: sha256:... | null
target_receipt_id: stable alias | null
predecessor_receipt_ids: [aliases]
observed_at: ISO-8601
evidence_mode: sanitized-persisted | ephemeral-only | approved-store-reference
evidence_hashes: [sha256:...]
evidence_refs: []
passed_checks: [bounded checks]
limitations: [what remains unproven]
```

`QA_FAIL` emits observable findings and an advisory earliest layer. It blocks
handoff until repair and a fresh run. `QA_BLOCKED` requires automation passed
and only a human/platform/device gate remains. A missing evaluator/tool is
`qa-prerequisite-missing`, not BLOCKED.

Same-contract repairs increment attempts up to three. A candidate/target or
scope identity change, PASS/BLOCKED result, or superseding contract starts a
new run at one. The validator never accepts a fourth blind repair.
