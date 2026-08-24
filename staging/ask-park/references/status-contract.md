# Ask Park state contract

This contract is the persisted control-plane state used by Ask Park. It is
deliberately separate from module prose and from QA candidate/target manifests.
The state record describes where the project is; it does not authorize an
action and it does not claim that a later module is complete.

## Versioning

The current schema is JSON data model version `1` and contract version
`ask-park.state/v1`. A record must carry both values. The validator rejects an
unknown version rather than guessing how to migrate it. State migration and
transition operations belong to S01B.

## Independent axes

The following axes are independent and must not be compressed into one status:

| Axis | Allowed values | Meaning |
| --- | --- | --- |
| `current_module` | `plan`, `build`, `cloudbase`, `experience`, `device`, `release` | The one sequential module Ask Park currently owns. Diagnose overlays this value. |
| `modules.<name>.applicability` | `required`, `not-applicable` | Whether the approved target requires the module. Not-applicable is an explicit Plan decision, never an omission. |
| `modules.<name>.activity_state` | `waiting`, `current`, `completed`, `failed`, `blocked-external`, `locked`, `not-applicable` | Work/control state for one module. |
| `modules.<name>.evidence_state` | `absent`, `valid`, `stale`, `invalid`, `not-applicable` | Freshness and causal validity of that module's evidence. |
| `diagnose.state` | `standby`, `active` | Whether Diagnose & Recover is overlaid on an interrupted module. |
| `diagnose.outcome` | `none`, `unresolved`, `recovered`, `blocked-external` | Diagnose outcome; it never promotes a module. |
| `control_outcome` | `none`, `unknown`, `baseline-conflict`, `needs-human-state-reconciliation`, `blocked-external` | A control-plane condition that remains visible independently of module activity. |
| `project_state` (or compatibility spelling `project_terminal_state`) | `active`/`none`, `target-achieved`, `released`, `abandoned` | Terminal claim for the approved target. `active` maps to `none`; `released` is not implied by a completed Experience module. |
| `human_gate.state` | `not-needed`, `prepared`, `awaiting-human`, `authorized`, `executed`, `read-back`, `denied`, `expired` | Separate lifecycle for human-controlled actions. Technical access is not authorization. |

The sequential modules are fixed in this order:

```text
Plan → Build → CloudBase → Experience → Device Acceptance → Release
```

The persisted module keys are `plan`, `build`, `cloudbase`, `experience`,
`device`, and `release`. A state record always includes all six keys. A module
with `applicability: not-applicable` must also have
`activity_state: not-applicable`, `evidence_state: not-applicable`, and a
non-empty `not_applicable_reason`.

## State shape

```json
{
  "schema_version": 1,
  "contract_version": "ask-park.state/v1",
  "project_id": "safe-project-alias",
  "project_state": "active",
  "current_module": "experience",
  "control_outcome": "none",
  "modules": {
    "plan": {
      "applicability": "required",
      "activity_state": "completed",
      "evidence_state": "valid",
      "receipt_id": "plan-r1"
    },
    "build": {
      "applicability": "required",
      "activity_state": "completed",
      "evidence_state": "valid",
      "receipt_id": "build-r1"
    },
    "cloudbase": {
      "applicability": "required",
      "activity_state": "completed",
      "evidence_state": "valid",
      "receipt_id": "cloudbase-r1"
    },
    "experience": {
      "applicability": "required",
      "activity_state": "current",
      "evidence_state": "absent",
      "receipt_id": null
    },
    "device": {
      "applicability": "required",
      "activity_state": "locked",
      "evidence_state": "absent",
      "receipt_id": null
    },
    "release": {
      "applicability": "required",
      "activity_state": "locked",
      "evidence_state": "absent",
      "receipt_id": null
    }
  },
  "diagnose": {
    "state": "standby",
    "outcome": "none",
    "interrupted_module": null,
    "recovery_goal": null
  },
  "human_gate": {
    "state": "not-needed",
    "action_scope": null,
    "authorizing_role": null,
    "requested_at": null,
    "authorized_at": null,
    "evidence_ref": null
  },
  "rewind": {
    "active": false,
    "earliest_invalidated_module": null,
    "reason_code": null,
    "invalidated_receipt_ids": []
  }
}
```

## Invariants

- `current_module` names exactly one sequential module. After formal release it
  remains `release`, with Release completed and valid.
- A failed or externally blocked module remains current. Diagnose is never a
  replacement current module.
- Later modules may be `locked` when a required predecessor lacks valid
  evidence. A later module cannot be completed by setting its activity flag.
- A stale or invalid required predecessor requires a causal rewind. `rewind`
  must be active, identify the earliest invalidated module, provide a reason,
  and list affected receipt aliases. The current module must be that earliest
  module. S01 validates this declaration; S01B computes the transitive closure.
- An inactive rewind carries no invalidation details. An active rewind must
  name a sequential module and a non-empty reason.
- `control_outcome` never clears `current_module` and is cleared only by direct
  evidence or a superseding contract in S01B.
- `project_state: released` requires valid Release evidence and a
  read-back receipt; an upload, simulator result, or user assertion is not a
  release claim.
- The architecture's `project_state` spelling is canonical for new records.
  The validator accepts `project_terminal_state` for the issue terminology, or
  both fields when they agree (`active` ↔ `none`). Conflicting aliases fail.
- A state record contains aliases and redacted evidence references only. It
  never contains AppID/AppSecret, environment IDs, OpenID, credentials, QR
  contents, complete URLs, absolute filesystem targets, or private customer
  data.

## Stable validator errors

`staging/ask-park/scripts/validate-state.py` emits machine-readable errors with
stable `code` and structural `path` fields. It never echoes input values.
Notable codes include `STATE_REQUIRED_FIELD`, `STATE_ENUM`,
`STATE_CURRENT_MODULE`, `STATE_NOT_APPLICABLE`, `STATE_REWIND_REQUIRED`,
`DIAGNOSE_STATE`, `HUMAN_GATE_STATE`, `PRIVATE_TARGET`, and
`SENSITIVE_FIELD`.
