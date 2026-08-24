# Diagnose incident contract

The incident record is a bounded, redacted observation. It is not a bug
tracker, a provider command, or a replacement for the S01 state record.

## Required shape

```yaml
schema_version: 1
module: diagnose
incident_id: stable local alias
diagnose_state: active | standby
outcome: recovered | unresolved | blocked-external
interrupted_module: plan | build | cloudbase | experience | device | release
post_recovery_current_module: sequential module alias
recovery_goal: original module exit outcome
symptom:
  statement: observable symptom
  observed_at: ISO-8601
  source_ref: redacted evidence alias
failure_class: source-drift | artifact-drift | deployment-drift | runtime-drift | identity | permission | network | device-only
observed_facts:
  - fact: bounded observation
    evidence_ref: redacted alias
    proves: what it proves
    cannot_prove: what remains unproven
hypotheses:
  - id: stable alias
    statement: falsifiable explanation
    test: smallest safe test
    falsifier: observation that rejects it
    status: open | supported | rejected
causal_invalidation_proposal:
  confirmed: true | false
  earliest_module: sequential module or null
  changed_fields: []
  invalidated_receipt_ids: []
  reason_code: safe alias or null
attempts:
  - attempt: positive integer
    action: bounded, reversible check
    result: observed result
bounded_next_action: one next step
human_gate_required: true | false
human_gate_ref: redacted alias or null
human_gate_summary: null | {state, action_type, action_scope, authorizing_role, evidence_ref}
unproven_claims: [explicit limitations]
load_contracts: [shared contracts, Diagnose, interrupted module]
```

## Causal proposal rules

- `confirmed: true` requires a named earliest module, at least one changed
  causal field, and every affected receipt alias. Ask Park passes this proposal
  to S01B; Diagnose does not directly rewrite state or receipts.
- A confirmed proposal may rewind only to an earlier or equal prerequisite of
  the interrupted module. The router, not an incident string, chooses the
  current module.
- A device-only observation or other no-predecessor defect uses
  `confirmed: false`, `earliest_module: null`, empty fields/IDs, and retains
  the interrupted module after recovery.
- Every attempt is bounded and numbered. Three attempts are the escalation
  ceiling for one incident; a fourth attempt requires a new Park decision or a
  superseding contract.

## Outcome rules

| Outcome | `diagnose_state` | Meaning |
| --- | --- | --- |
| `recovered` | `standby` | Original symptom rechecked and recovery evidence recorded |
| `unresolved` | `active` | Root cause remains uncertain; one bounded hypothesis remains |
| `blocked-external` | `active` | Human/platform/device authority is required |

`recovery_goal` is preserved in all outcomes. `unproven_claims` is never empty:
even a recovered incident states what the evidence does not prove.

## Loading and privacy

`load_contracts` records the shared status and evidence contracts, then the
human-gate and transition contracts, Diagnose, and exactly the interrupted
module. In S04, module paths for S05–S09 are planned/unavailable disclosure
targets until their stories land; a path in this record does not claim that an
unimplemented module was loaded. All source/target references are aliases or
`redacted:` values; no credentials, complete URLs, environment IDs, QR
contents, or private data are persisted.
