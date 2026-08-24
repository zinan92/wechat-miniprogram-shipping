# S14B independent forward-evaluation contract

S14B runs the merged Ask Park architecture and independent QA designs from raw
fixtures. The manifest contains 23 architecture cases and 22 QA cases with
explicit allowed inputs and exclusions. It contains no intended verdict,
`expected_result`, route command, or canned pass/fail field.
Its canonical digest binds every operation, input alias, fixture closure,
allowed-input list, and exclusion; a tampered descriptor is rejected before
execution.

## Fresh bounded execution

`scripts/forward-eval.py` drives only the staged router, lifecycle, QA schema,
independent evaluator, Browser QA, DevTools QA, and S14A QA-routing seams. Its
record/replay adapter permits fixture reads and fails closed on every network,
provider write, or deletion. Each result is an observed oracle derived from
the returned state/result fields, not from scenario prose.

The matrix covers the 23 architecture behaviors (single current module,
causal receipt rewind, Diagnose overlay, human gates, terminal release,
control outcomes, and compatible migration) and all merged QA behaviors
(identity drift, stale render/package, matrix coverage, prerequisite missing,
human blocking, evaluator independence, privacy, and Ask Park authority).

## Surface controls

Every surface has an explicit `pass → seeded defect → restore → pass` control:

- Browser candidate/target drift;
- DevTools duplicate-title/read-back/provenance defect;
- independent evaluator candidate repair;
- QA schema identity invalidation;
- lifecycle evidence rewind and restored fixture state;
- QA-routing Diagnose activation and recovery.

The QA-routing control actually activates Diagnose, recovers it, and reruns a
QA_PASS; the evaluator control actually attempts a fourth repair and records
that the bounded loop rejects it.

Attempt three retains `QA_FAIL + needs-park-decision`; no blind fourth repair is
run. Simulator, Browser, and upload evidence retain their limitations.

## Artifact and privacy assertions

Sensitive screenshot bytes, private paths, credentials, full URLs, and private
fixture names are created only ephemerally for the artifact-tree control and
are removed before the result is emitted. The final tree must contain only
sanitized/redacted aliases. The report derives and records
`external_network_events: []`, `mutation_events: []`, and
`artifact_tree_clean: true` from the adapter/event log and the actual
temporary run-output tree, rather than writing these values as a canned
verdict.

S14B is a read-only evaluation. It never edits code, changes a CloudBase or
WeChat environment, uploads a package, or promotes Ask Park state.
