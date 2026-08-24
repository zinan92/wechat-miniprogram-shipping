---
name: ask-park
description: Route new, takeover, failure, continuation, and release work for a WeChat Mini Program through one Ask Park entry, six evidence-gated shipping modules, Diagnose & Recover, and an independent QA gate.
---

# Ask Park

Ask Park is the one user-facing entry for Mini Program shipping. Use `$ask-park`
(or `/ask-park` in clients that expose slash commands) for a new project,
takeover, failure, continuation, or release request. The staged package is not
discoverable until the final migration story; this entry is nevertheless the
complete contract that later migration will publish.

## Operating loop

1. Read an explicit state record and classify the request. State never comes
   from the latest chat message alone.
2. Validate the S01 state and receipt contracts before selecting work.
3. Render the complete map: Plan, Build, CloudBase, Experience, Device
   Acceptance, Release, and the Diagnose & Recover overlay.
4. Select the earliest required module whose activity/evidence exit contract
   is not complete. A failed or blocked module remains the one current module.
5. If a failure is reported, overlay Diagnose & Recover on the current module;
   do not create a seventh sequential current module.
6. Load shared contracts plus the selected module contract. During recovery,
   also load Diagnose and the interrupted module only.
7. Let Ask Park alone promote modules or invalidate dependent receipts. A
   worker reports evidence; it cannot choose the next module.
8. End every substantive response with the map and exactly four operator
   sections: conclusion; current module and evidence; decision/action needed
   from Park; next verifiable step.

## Route classes

Use one explicit route class:

- `new`: start from an idea or a new Mini Program;
- `takeover`: continue an existing repository or project handoff;
- `failure`: activate Diagnose & Recover around the authoritative current module;
- `continuation`: resume from the recorded state;
- `release`: assess the release path without skipping incomplete predecessors.

If the request matches multiple classes, ask Park to choose; do not guess.

## Contracts

Read [references/router.md](references/router.md) for the routing algorithm,
map/output contract, control outcomes, and the deterministic router API. The
router composes these shared contracts:

- [references/status-contract.md](references/status-contract.md)
- [references/evidence-contract.md](references/evidence-contract.md)
- [references/human-gates-contract.md](references/human-gates-contract.md)
- [references/transition-contract.md](references/transition-contract.md)

The executable seam is [scripts/router.py](scripts/router.py). It is pure and
provider-free: it validates state, optionally asks S01B to compute causal
invalidation/rewind, and returns a new decision. It does not write files,
call WeChat/CloudBase, infer authority, or mutate a live project.

## Boundaries

- A receipt proves only the module that produced it. It cannot prove a later
  target or a physical device.
- Missing, stale, or invalid evidence selects the earliest affected module;
  missing causal receipts become an explicit state-reconciliation outcome.
- Conflicting state sources produce `needs-human-state-reconciliation`;
  changed acceptance produces `baseline-conflict`; human/platform action without
  explicit authority is `blocked-external`.
- Diagnose, QA, and human gates never promote a sequential module by
  themselves. QA remains a later independent horizontal gate, not an eighth
  mental anchor.
- Root `SKILL.md`, root metadata, README installer, installed skill behavior,
  and live Mini Program systems are outside this staged implementation.
