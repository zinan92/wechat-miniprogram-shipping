# QA state contract

QA is an independent horizontal gate, not an eighth Ask Park module. It never
selects `current_module`, invalidates receipts, edits a candidate, or signs its
own work.

```yaml
qa:
  execution_state: unavailable | ready | running | complete
  result: none | QA_PASS | QA_FAIL | QA_BLOCKED
  control_outcome: none | qa-prerequisite-missing | needs-park-decision
  gate: contract | qa-1 | target | qa-2 | evidence | final
  candidate_manifest_digest: sha256:... | null
  target_manifest_digest: sha256:... | null
  attempt: positive integer
  max_attempts: 3
  origin_module: plan | build | cloudbase | experience | device | release
  result_receipt_id: stable alias | null
```

Tool/evaluator unavailability is the explicit prerequisite missing condition:
`execution_state: unavailable` plus
`control_outcome: qa-prerequisite-missing`; it is never `QA_BLOCKED`. A
`QA_BLOCKED` result is legal only after all automatable checks pass and a
human/platform/device action remains. `QA_FAIL` blocks deployment, upload,
promotion, and Park handoff. Attempt three escalates to
`needs-park-decision`; there is no blind fourth repair.

Any candidate/target/acceptance identity change resets a prior non-none result
to `ready/none` through the QA validator. Ask Park still owns module routing and
causal invalidation.
