# Ask Park lifecycle transition contract

S01 defines the persisted JSON shapes. S01B defines how those shapes may
change. The lifecycle engine in `scripts/state-lifecycle.py` is a pure,
deterministic operation layer: it deep-copies its input, validates the S01
boundary, performs one legal operation, and returns a new record. It never
calls a provider, writes a file, mutates live state, or chooses a route for a
later module.

## Stable rejection boundary

Every rejected operation raises `LifecycleError` with a machine-readable
`code` and structural `path`. The input value, private target, and secret are
never copied into an error. Representative codes are:

| Code | Meaning |
| --- | --- |
| `STATE_INVALID` | Input state does not satisfy the S01 state contract |
| `ILLEGAL_ACTIVITY_TRANSITION` | Module activity edge is not in the legal graph |
| `ILLEGAL_EVIDENCE_TRANSITION` | Evidence edge is not in the legal graph |
| `CURRENT_MODULE_REQUIRED` | A module cannot become current before its required predecessors |
| `COMPLETION_EVIDENCE_REQUIRED` | Completion lacks valid evidence |
| `ILLEGAL_DIAGNOSE_TRANSITION` | Diagnose state/outcome edge is not legal |
| `DIAGNOSE_MODULE_MISMATCH` | An active Diagnose overlay does not match `current_module` |
| `ILLEGAL_PROJECT_TRANSITION` | Project terminal edge is not legal |
| `PROJECT_TARGET_EVIDENCE_REQUIRED` / `PROJECT_TARGET_SCOPE_REQUIRED` | A target-achieved stop is missing a completed, valid, receipted current target or later modules are not explicitly out of scope |
| `PROJECT_RELEASE_EVIDENCE_REQUIRED` | Release completion lacks valid Release evidence, a receipt, or a read-back human gate |
| `RECEIPT_NOT_ISSUABLE` | Receipt is stale/invalid rather than an issuable observation |
| `PREDECESSOR_RECEIPT_MISSING` / `PREDECESSOR_RECEIPT_INVALID` | Causal predecessor chain is incomplete or unusable |
| `PREDECESSOR_ORDER_INVALID` / `RECEIPT_ID_MISMATCH` | A predecessor is not an earlier sequential module or an external receipt alias does not match its payload |
| `RECEIPT_REUSE_INVALIDATED` | A declared causal invalidation trigger changed |
| `INVALIDATION_REASON_REQUIRED` | A causal invalidation reason is missing or not a safe alias |
| `HUMAN_GATE_INVALID` | A prepared gate does not satisfy the S01 gate shape or persistence boundary |
| `HUMAN_AUTHORIZATION_REQUIRED` | An explicit owner decision is missing or technical access was supplied instead |
| `CONTROL_CLEARING_EVIDENCE_REQUIRED` | The supplied evidence does not directly resolve the control outcome |
| `SUPERSEDING_CONTRACT_REQUIRED` | A baseline conflict lacks an accepted superseding contract |
| `CONTRACT_MIGRATION_REQUIRED` | A contract-version change has no explicit migration |
| `INCOMPATIBLE_CONTRACT` | Migration does not explicitly prove compatibility and verification |
| `MIGRATION_CAUSAL_IDENTITY_CHANGED` | A claimed compatible migration changed a causal binding |
| `MIGRATION_TRANSFORM_FAILED` | A migration transform raised an internal exception and was rejected without exposing its details |

## Module activity and evidence

The sequential modules are fixed: `plan → build → cloudbase → experience →
device → release`. The activity graph is:

```text
waiting → current → completed
                  ├→ failed → current
                  └→ blocked-external → current
locked → current
```

`completed` is not directly rewound or made current. A causal invalidation
uses `rewind_state`, which sets the earliest prerequisite to `current` and
locks later modules. A module may complete only with `evidence_state: valid`;
the Release module additionally requires a `read-back` human gate. Completion
promotes the next required module and never persists `next_module`.
An active Diagnose overlay must be recovered before completion can be
recorded.

The evidence graph is intentionally narrower than the activity graph:

```text
absent → valid | invalid
valid → stale | invalid
stale → valid | invalid
invalid → valid | stale
```

Evidence cannot be silently removed from a completed module. `not-applicable`
is an explicit Plan decision and cannot be changed by a later module.

Failed or externally blocked work remains the one `current_module`.
Diagnose overlays that module; it is never a seventh sequential current
module.

When the approved target stops before Release, the final required module is
completed with valid evidence and a receipt, every later module is explicitly
`not-applicable`, and the project terminal axis becomes `target-achieved`.
The transition validates the complete output and removes the legacy
`project_terminal_state` alias. Release completion similarly synchronizes the
legacy alias and requires a `read-back` gate. All terminal project states
(`target-achieved`, `released`, and `abandoned`) freeze subsequent module and
Diagnose mutations. Release completion additionally requires a non-technical,
explicit `authority_basis` on that read-back gate; a gate state alone is not
authorization.

## Diagnose overlay

`activate_diagnose(state, interrupted_module, recovery_goal)` requires the
interrupted module to be the current module and records it without promoting
anything. An active Diagnose may be `none`, `unresolved`, or
`blocked-external`. `recover_diagnose` returns the overlay to
`standby/none`, restores a failed or blocked module to `current`, and leaves
the same sequential module current. It cannot issue a receipt or route to a
successor.

## Receipt issuance and reuse

`issue_receipt` accepts only a valid or explicit not-applicable S01 receipt.
Every listed predecessor must be supplied, validate under S01, have the same
alias, be valid/not-applicable, and belong to an earlier sequential module.
No predecessor is inferred from the state or from a chat message.

`reuse_receipt` is allowed only when:

1. the receipt is currently `valid`;
2. every supplied predecessor remains valid or explicitly not-applicable;
3. no `invalidation_rules.on` entry matches a changed causal field; and
4. an optional expected causal identity exactly equals the receipt identity.

The causal identity includes schema version, module/applicability, source,
issue, predecessor IDs, artifact, package, and redacted target. Contract
version is checked separately. Reuse never refreshes timestamps or produces a
new receipt ID.

## Transitive invalidation and rewind

`invalidate_receipts` starts at receipts whose declared `invalidation_rules.on`
match the changed fields, then reaches a fixed point over:

- predecessor receipt edges; and
- each selected receipt's Ask Park-owned `downstream_modules` declaration.

It marks valid selected receipts `stale`, returns deterministic module/ID
ordering, and selects the earliest invalidated module. It does not set a next
module and has no routing authority.

`rewind_state` applies that result to state: the earliest required module is
current, later required modules are locked, receipts at or after that module
are stale when present, and `rewind` records the earliest module, reason, and
invalidated receipt aliases. `invalidate_state` is the convenience composition
of both operations.

## Human-gate lifecycle

```text
not-needed → prepared → awaiting-human → authorized → executed → read-back
                                  └────→ denied
authorized → expired
```

Preparation requires explicit action type, scope, authorizing role, request
time, and redacted evidence reference. Authorization requires an explicit
`authority_basis` and authorization timestamp. Words such as authenticated,
CLI, access, permission, login, and capability are rejected as the authority
basis: an agent's ability to click or use an authenticated tool is not an
owner decision. Denied and expired gates are terminal and do not advance the
sequential module. A read-back gate records the result of the human/platform
action; it does not itself prove the module's other evidence.

## Control-outcome clearing

`control_outcome: unknown` or `blocked-external` clears only with direct,
matching evidence containing a redacted evidence reference. A
`baseline-conflict` clears only with an accepted superseding contract. A
`needs-human-state-reconciliation` clears only with a recorded reconciliation
and redacted evidence. Clearing an outcome never clears `current_module`,
Diagnose, a rewind, or a human gate.

## Contract migration

A contract-version change is rejected unless the caller supplies an explicit
migration that declares `compatible: true`,
`preserves_causal_identity: true`, and `verified: true`. An optional pure
transform is applied to a copy and then compared against the source causal
identity. Any source, issue, predecessor, artifact, package, target,
schema/module, or applicability change rejects with
`MIGRATION_CAUSAL_IDENTITY_CHANGED`. This prevents a migration from being a
disguised receipt re-issuance. An incompatible migration never gets a chance
to rewrite a persisted record.

## Public operations

The router may import these deterministic operations:

- `transition_activity`, `transition_evidence`, `transition_project`;
- `activate_diagnose`, `set_diagnose_outcome`, `recover_diagnose`;
- `issue_receipt`, `reuse_receipt`, `invalidate_receipts`, `rewind_state`,
  `invalidate_state`;
- `prepare_human_gate`, `transition_human_gate`, `authorize_human_gate`;
- `clear_control_outcome`, `migrate_receipt`.

This layer intentionally does not contain router language, Release-specific
authorization policy, target adapters, network calls, screenshots, QA
manifests, or persistence code.
