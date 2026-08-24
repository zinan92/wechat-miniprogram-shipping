# Ask Park router contract

Ask Park is a single conductor for six sequential modules and one overlay:

```text
Plan → Build → CloudBase → Experience → Device Acceptance → Release
                         ↘ Diagnose & Recover overlays any current module
```

The seven anchors are always visible. Diagnose is not a seventh sequential
current module and QA is a horizontal gate added by later stories.

## Input boundary

The router accepts:

- an explicit S01 `state` record;
- one route class: `new`, `takeover`, `failure`, `continuation`, or `release`;
- optional read-only conflict flags;
- optional receipt records plus changed causal fields for an Ask Park-owned
  invalidation/rewind.

It validates state with S01 before making a decision. It never infers the
current module, evidence, target, or authorization from chat prose. The input
is deep-copied; the caller's state and receipt objects are never mutated.

`classify_intent()` accepts an explicit `{intent: ...}` object or a short
natural-language request. If more than one route class matches, it returns
`ROUTER_INTENT_AMBIGUOUS`; an unclassified request returns
`ROUTER_INTENT_UNCLASSIFIED`.

## Routing algorithm

1. Validate the state and retain its one `current_module`.
2. If changed causal fields are supplied, require receipts. Ask Park calls the
   S01B invalidation operation; it rewinds to the earliest invalidated module
   and locks later modules. Missing or malformed causal receipts produce
   `needs-human-state-reconciliation`; no inference is made.
3. Give explicit conflicts precedence: competing sources produce
   `needs-human-state-reconciliation`; an accepted-baseline conflict produces
   `baseline-conflict`; missing authority for a human/platform action produces
   `blocked-external`.
4. Preserve a non-`none` state `control_outcome`; it is never silently cleared
   by routing.
5. A formal `released` state routes to Release and retains
   `current_module: release`. `target-achieved` and `abandoned` retain the
   recorded current module without promoting anything.
6. A failed or `blocked-external` current module remains current. A failure
   request asks for a Diagnose overlay on that same module.
7. Otherwise choose the first required module, in sequence, whose activity is
   not `completed` or whose evidence is not `valid`. Not-applicable modules
   are explicit Plan decisions and are skipped.
8. A `release` request may select Release only when every required predecessor
   already satisfies its exit contract; otherwise it reports the earliest gap.
9. Return the selected module, reason, control outcome, contracts to load,
   invalidated receipt IDs, a new state value, and the complete progress map.

The router never persists `next_module`. Promotion occurs only through the
S01B lifecycle operations after direct evidence satisfies the selected
module's exit contract.

## Control outcomes

`control_outcome` in a `RouteDecision` is a routing result; it does not silently
rewrite the persisted S01 state axis.

| Outcome | Meaning | Park decision |
| --- | --- | --- |
| `missing-evidence` | Selected module lacks a completed valid exit observation | Proceed only with that module's evidence contract |
| `needs-human-state-reconciliation` | Sources or causal receipts disagree/missing | Choose the authoritative source or record reconciliation evidence |
| `baseline-conflict` | Accepted issue/scope changed | Accept a superseding contract or keep the baseline |
| `blocked-external` | Human/platform authority is required | Complete or explicitly authorize the human gate |

An existing S01 `control_outcome` is preserved and takes precedence over
ordinary module selection. Clearing it belongs to S01B's defined evidence or
superseding-contract operations.

## Progress-map contract

Every decision renders this ordered map before its operator sections:

```text
ASK PARK · MINI PROGRAM SHIPPING

1. Plan              completed        [evidence valid]
2. Build             completed        [evidence valid]
3. CloudBase         completed        [evidence valid]
4. Experience        current          [evidence absent]
5. Device Acceptance locked           [evidence absent]
6. Release           locked           [evidence absent]
7. Diagnose & Recover standby          [outcome none]
```

The map carries independent `applicability`, `activity_state`, and
`evidence_state` values for each sequential module. Diagnose carries its
`state`, `outcome`, and `active` flag. It never replaces `current_module`.

The rendered response then has exactly four headings, in order:

1. `Conclusion` — the selected route or the blocking control outcome;
2. `Current module and evidence` — authoritative current and selected module;
3. `Decision or action needed from Park` — explicit human choice, if any;
4. `Next verifiable step` — the smallest bounded action.

## Progressive disclosure

The router loads the shared state, evidence, human-gate, and transition
contracts plus the selected module path. During failure recovery it also loads
Diagnose and the interrupted module. Module implementations, CloudBase
adapters, screenshots, browser/DevTools workflows, and QA manifests are later
stories; this router does not pretend to prove them.

## Executable seam

`scripts/router.py` exposes:

- `classify_intent(request)`;
- `route(state, intent, ...)`;
- `RouteDecision.as_dict()` and `RouteDecision.rendered`;
- a minimal JSON CLI for hermetic tests.

The seam calls only the local S01/S01B validators and lifecycle engine. It has
no provider, network, filesystem write, credential, or live-state authority.
