# S15 isolated end-to-end trial

S15 runs Ask Park and the QA Gate against `synthetic-reader-trial-v1`. The
fixture is deliberately local and contains no AppID, environment ID, customer
project, production CloudBase, or `wechat-xingqiu` data.

## Trial contract

1. Browser QA reads a matching synthetic candidate/target and passes.
2. A stale live bundle/deep-link/mock-marker seed produces `QA_FAIL`; restoring
   the target passes without changing the candidate source SHA.
3. DevTools QA reads a complete nine-state candidate and passes. The duplicate title,
   double safe area, stale package/read-back mismatch, and missing final
   compile seeds produce `QA_FAIL`; restoring raw events passes with the same
   candidate SHA.
4. A repair changes the candidate SHA and produces fresh evidence bound to the
   new identity; prior screenshots cannot prove the new candidate.
5. Only after automation passes does the physical-device/account requirement
   become `QA_BLOCKED` with an `awaiting-human` gate. Missing tools remain
   prerequisite-missing.
6. Three failed repair attempts retain `QA_FAIL + needs-park-decision`; `no blind fourth`
   repair is allowed.

The trial is read-only, emits sanitized observations and a reproducible fixture digest. It
does not edit code, upload a package, call a provider, or mutate a real target.
