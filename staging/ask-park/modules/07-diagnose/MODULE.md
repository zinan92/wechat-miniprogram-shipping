# Diagnose & Recover module

Mental anchor: locate the broken layer, repair the smallest cause, prove
recovery, and return to the interrupted module.

Diagnose is a cross-cutting overlay. It never becomes a seventh sequential
current module and it never self-promotes a project. Ask Park keeps the
interrupted sequential module authoritative, then uses the lifecycle engine to
rewind to the earliest confirmed invalidated prerequisite.

## Input

- an observable failure, regression, or inconsistent evidence record;
- the authoritative `current_module` and its module contract;
- the current receipt chain and source/package identities;
- a recovery goal stated in terms of the original module outcome;
- the user's authorization boundary and any human/platform gate.

Read shared state/evidence/human-gate/transition contracts, Diagnose, and
exactly the interrupted module. Do not load every module to speculate.

## Output

Produce an incident record conforming to
[incident-contract.md](incident-contract.md):

- symptom, observed facts, failure class, and limitations;
- one or more falsifiable hypotheses, each with a test and falsifier;
- bounded recovery actions and attempt count (maximum three before escalation);
- a causal invalidation proposal with changed fields, earliest module, and
  receipt IDs when a predecessor identity actually changed;
- `recovered`, `unresolved`, or `blocked-external` outcome;
- preserved recovery goal, post-recovery current module, evidence, unproven
  claims, and the next bounded action;
- named human gate when identity, permission, device, payment, review, or
  platform action is required.

## Success predicate

Diagnose exits only when the original symptom is rechecked at its actual layer,
the smallest causal fix and regression proof are recorded, affected receipts
are marked stale through Ask Park, and the router selects the earliest module
requiring revalidation. `recovered` returns Diagnose to standby; the
interrupted module or earliest invalidated prerequisite remains the sequential
current module.

## Failure outcomes and routing

- root cause not established → keep `diagnose_state: active`, outcome
  `unresolved`, and write one bounded next hypothesis;
- human/platform action required → keep Diagnose active, outcome
  `blocked-external`, and prepare a human gate;
- a source, artifact, package, contract, or target identity changed → propose
  invalidation; Ask Park alone computes the transitive closure and rewinds;
- no predecessor changed (for example a device-only observation) → preserve the
  interrupted module and do not manufacture a rewind;
- three bounded attempts without recovery → stop and request a Park decision;
- a recovery attempt changes scope → return to Plan with a superseding contract.

`failed`, `blocked-external`, `unknown`, and `baseline-conflict` are control or
activity outcomes, not evidence claims.

## Evidence

Record the symptom, timestamp/source alias, observed facts, failure class,
hypotheses and tests, root cause or remaining uncertainty, scoped repair,
regression proof, invalidated receipt IDs, post-recovery module, target
read-back, human authorization references, and explicit unproven claims. Keep
all private targets, credentials, QR contents, and customer data outside the
record.

## Forbidden boundary

- Do not perform application, provider, payment, review, or device mutation as
  part of the module contract.
- Do not bypass security or human gates.
- Do not retry external writes indefinitely or broaden a repair into a refactor.
- Do not mark a hypothesis recovered without rechecking the original symptom.
- Do not let Diagnose choose a successor or clear a control outcome by prose.
- Do not treat logs, Simulator, HTTP reachability, or a screenshot as stronger
  evidence than the surface they actually observe.

## Procedure

1. Bind the incident to the current module and preserve the recovery goal.
2. Classify the failure as source drift, artifact drift, deployment drift,
   runtime drift, identity, permission, network, or device-only.
3. Inspect the smallest relevant layer in Local → Git → artifact/DevTools →
   WeChat package → CloudBase order, recording observed facts and limitations.
4. Write a falsifiable hypothesis and the smallest safe test; stop after three
   bounded attempts if the symptom remains unresolved.
5. If a causal identity changed, submit an Ask Park invalidation proposal with
   the changed fields and earliest confirmed prerequisite. Do not route by
   writing `next_module`.
6. Recheck the original symptom at its actual layer and record recovered,
   unresolved, or externally blocked outcome.
7. Return the incident to Ask Park. Ask Park performs lifecycle rewind,
   promotion, human-gate transitions, and the next module selection.
