# Independent QA evaluator contract

The QA evaluator is a distinct, fresh-context, read-only role. It receives the
issue contract and raw candidate evidence, not the worker's implementation
conversation. It cannot edit code, repair a candidate, route a module,
invalidate receipts, promote state, or weaken acceptance criteria.

## Required evaluator packet

```yaml
worker_identity: stable evaluator-external worker alias
evaluator_identity: stable fresh evaluator alias
fresh_context: true
read_only: true
candidate_sha_before: sha256:...
candidate_sha_after: sha256:...
bounded_inputs: [issue, diff, tests, manifests, raw evidence]
exclusions: [live provider, credentials, private data]
verdict: QA_PASS | QA_FAIL | QA_BLOCKED
findings: [observable finding records]
advisory_earliest_layer: plan | build | cloudbase | experience | device | release | null
automation_passed: true | false
human_gate_required: true | false
```

`worker_identity` and `evaluator_identity` must differ. `candidate_sha_before`
and `candidate_sha_after` must match; a candidate edit is a protocol failure,
not a QA result. Findings are observations, not routing commands. A PASS or
BLOCKED result is never self-signed by the worker.

## Verdict policy

- `QA_PASS`: all applicable automatable checks pass and no findings remain;
- `QA_FAIL`: an observable defect exists; emit findings and an advisory layer;
- `QA_BLOCKED`: automation passes and only a human/platform/device action
  remains; name the human gate and limitation;
- unavailable evaluator/tool: S10 state `qa-prerequisite-missing`, never
  `QA_BLOCKED`.

Ask Park consumes the result and owns Diagnose activation, receipt
invalidation, current-module selection, and human handoff.
