# QA → Diagnose → Ask Park routing contract

S14A is the integration owner for the horizontal QA gate. S10–S13 evaluators
remain fresh, read-only, and advisory. They emit findings and an advisory
earliest layer; they never select `current_module`, invalidate receipts, clear a
control outcome, or promote a module. Ask Park alone owns those transitions.

The integration depends explicitly on the merged S02 router, S04 Diagnose
contract, S09 Release/human-gate boundary, S10 QA schemas, S11 independent
evaluator, S12 Browser QA, and S13 DevTools QA. It does not replace any of
those contracts.

## One authority chain

```text
QA result → advisory packet → Diagnose confirms cause → Ask Park invalidates/routes
                         ↘ QA_BLOCKED → human gate (Diagnose stays standby)
```

`qa-routing.py` is the only seam that consumes a validated evaluator packet.
`advisory_from_packet()` returns findings, provenance, and limitations only.
Supplying `selected_module`, `current_module`, `next_module`, `route_to`, or
receipt invalidation inside a QA packet is rejected.

## Result behavior

- `QA_PASS` returns an advisory continuation decision and the unchanged S01
  state. It never marks a module complete or promotes to a successor.
- `QA_FAIL` is inert until Diagnose supplies a bounded diagnosis. A confirmed
  causal proposal includes the interrupted module, earliest module, changed
  fields, reason code, and raw receipt chain. Ask Park verifies the receipt
  closure, rewinds to its computed earliest module, and then activates Diagnose
  on that recovery module. The incident preserves both the original
  `interrupted_module` and the actual `recovery_module`.
- A device-only or target-only defect with no causal predecessor activates
  Diagnose on the interrupted module without invalidating receipts.
- `QA_BLOCKED` is legal only when automation passed and no findings remain.
  Missing physical-device/account evidence prepares an `awaiting-human` gate;
  Diagnose remains `standby`. Missing tools/evaluators remain
  `qa-prerequisite-missing`, never `QA_BLOCKED`.

## Bounded repair loop

Every repair is a new candidate and a fresh QA attempt. `same-contract` repair
increments the attempt; a result after `QA_PASS` or `QA_BLOCKED` starts attempt
one again. A superseding contract requires a new issue and evaluator identity
and starts at one. On attempt three, a `QA_FAIL` retains `QA_FAIL + needs-park-decision`;
the integration rejects a blind fourth repair: no blind fourth is allowed. No helper in this module edits
code or receipts directly.

## State and privacy boundaries

The S01 state remains the authoritative module/Diagnose/human-gate record; QA
state and evaluator packets remain separate S10/S11 records. Every operation
deep-copies input. References are aliases or `redacted:` values only; URLs,
credentials, private paths, and raw evidence bytes are rejected. The router
returns a complete progress map while preserving exactly one sequential
current module. `next_module` is never persisted.
