# Plan acceptance contract

This is the human-readable shape contract for a Plan record. It is a planning
artifact, not a GitHub issue API payload and not a receipt validator.

## Required top-level fields

```yaml
schema_version: 1
module: plan
mode: new | takeover | scope-change
control_outcome: none | unknown | baseline-conflict | blocked-external
issue_ready: true | false
decision_needed: null | concise decision text
outcome:
  statement: one sentence
  first_useful_moment: observable first user value
acceptance_criteria: 3–7 verifiable statements
scope:
  in: [concrete included work]
  out: [explicit deferrals]
forbidden_changes: [bounded prohibited actions]
complexity:
  label: S | M | L
  rationale: why this size
  test_depth: targeted | upstream-downstream | full-review
applicability:
  plan: required | not-applicable
  build: required | not-applicable
  cloudbase: required | not-applicable
  experience: required | not-applicable
  device: required | not-applicable
  release: required | not-applicable
applicability_reasons:
  module: reason required when applicability is not-applicable
risk_map:
  - category: intent | identity | backend | experience | device | release | migration
    status: known | unknown | mitigated | blocked
    impact: concrete consequence
    mitigation: bounded next check or decision
solution_search:
  - kind: product | repository | component | skill
    query: what was searched
    finding: reusable option or no suitable result
    decision: reuse | adapt | reject | investigate
    evidence_ref: redacted reference or public link alias
ordered_work:
  - story_id: stable local alias
    outcome: one useful result
    acceptance_criteria: 3–7 statements
    in_scope: [included work]
    out_of_scope: [deferred work]
    forbidden_changes: [guardrails]
    complexity: S | M | L
    issue_contract_ready: true | false
issue_contract:
  immutable: true | false
  version: positive integer
  contract_id: stable local alias
issue_actions: [] | [prepare]
source_evidence: [aliases and limitations]
```

## Rules

- The `solution_search` field is the solution search record: it names the
  search boundary, reusable finding, and reuse decision.
- `acceptance_criteria` and every story's criteria contain 3–7 concrete,
  independently verifiable statements. Count is not a substitute for quality.
- `applicability` has all six module keys. Every `not-applicable` value has a
  matching `applicability_reasons` entry; it is never an omission.
- The risk map covers every material risk category surfaced by the request.
  `unknown` is an honest state with a bounded mitigation, not a hidden guess.
- `solution_search` records the search boundary and reuse decision. It does not
  claim a product/repository is suitable without evidence.
- The S/M/L complexity choice binds the test depth and delivery boundary.
- An issue contract is an immutable boundary for one independently verifiable story.
- S means targeted tests, M means targeted plus immediate upstream/downstream
  tests, and L means review/evaluation/rollback depth defined by the queue.
- `issue_contract.immutable` is true only after the human accepts the boundary.
  A material change creates a new version/superseding contract; the old
  criteria are not rewritten.
- `issue_actions` may prepare a contract. Automatic issue creation is outside
  Plan and remains an empty list in a stopped/blocked record.
- No field may contain secrets, AppID/AppSecret, environment IDs, OpenID,
  credentials, QR contents, complete private URLs, or private customer data.

## Exit and stop conditions

`issue_ready: true` and `control_outcome: none` describe an approved Plan
boundary. `unknown`, `baseline-conflict`, or `blocked-external` keeps
`issue_ready: false` and requires `decision_needed`; `ordered_work` is empty
when no safe story can yet be written.
