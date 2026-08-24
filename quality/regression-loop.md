# QA regression loop

The defect loop is bounded and issue-bound:

```text
candidate → independent evaluator → PASS
                              ↘ FAIL → Diagnose/repair → fresh attempt
                              ↘ BLOCKED → human gate
```

1. Start at attempt one with a named issue contract and candidate digest.
2. Same-contract repair increments the attempt and requires a new candidate
   digest/evidence packet.
3. Candidate, target, acceptance-scope, or evaluator identity changes reset a
   run to attempt one and invalidate the old result.
4. PASS or BLOCKED followed by a change starts a new run at one.
5. The attempt three result remains `QA_FAIL` with `control_outcome:
   needs-park-decision`; no blind fourth repair is legal.
6. Ask Park, not QA, selects the earliest layer after Diagnose confirms cause.

QA never edits a candidate or turns a verdict into a `next_module`. The packet
records before/after candidate identity, bounded inputs/exclusions, findings,
and limitations so an independent evaluator can be audited without the worker
conversation.
