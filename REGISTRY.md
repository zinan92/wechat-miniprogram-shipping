# Registry

## 现在在哪里

- Public repository: `zinan92/wechat-miniprogram-shipping`.
- Implemented: canonical root skill identity is `$ask-park`, with seven anchors, independent QA, migration, and cutover contracts.
- Installed: S16C/S16D read back one enabled `$ask-park` and zero enabled `$wechat-miniprogram-shipping`; the legacy directory remains only as recoverable backups outside scanned roots.
- Verified: root package, clean clone, installed router/module/QA canary, selector, rollback rehearsal, latest closure digest, and sanitized receipts all passed. This is skill/install verification, not a Mini Program production-release claim.
- Ask Park single-entry, seven-module architecture is approved and merged in PR #5.
- Independent Ask Park QA Gate design is approved by Park and merged in PR #7. Its three-round independent review findings were addressed; the final two schema corrections were mechanically validated after the review ceiling and remain visible in the PR record.
- The L-level implementation plan is approved by architecture, QA/test, and packaging reviewers and merged in PR #11.
- Dependency-ordered implementation issues #12–#33 are published. V1 WIP is hard-capped at one.
- S00/#12 is complete in PR #36 (`0e2e9b6`): staged package layout, validator, and hermetic harness; 9/9 targeted tests passed, staged validation passed, gitleaks passed.
- S01/#13 is complete in PR #39 (`366edb0`): core state/receipt/applicability/human-gate contracts; 21/21 S01 tests plus 9/9 S00 tests passed, staged validation and gitleaks passed.
- S01B/#14 is complete in PR #42 (`defa799`): mutation-free lifecycle transitions, causal receipt issuance/reuse/invalidation/rewind, Diagnose overlay, human-gate lifecycle, control-outcome clearing, and explicit receipt migration; 30/30 lifecycle tests, 22/22 S01 tests, and 9/9 S00 tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S02/#15 is complete in PR #44 (`c644ada`): one staged `$ask-park` entry, deterministic route classification, six-module plus Diagnose progress map, explicit control outcomes, causal rewind handoff, and four operator sections; 9/9 router tests plus 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S03/#16 is complete in PR #46 (`57d7ddd`): Plan's six-part contract, applicability reasons, S/M/L sizing/test depth, risk map, bounded solution search, issue-ready story shape, and safe new/takeover/scope-change stop fixtures; 6/6 Plan tests plus 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S04/#17 is complete in PR #48 (`24c541e`): Diagnose overlay and incident contract, failure taxonomy, falsifiable hypotheses, bounded attempts, named human-gate summaries, causal rewind proposals, and recovered/unresolved/blocked fixtures; 5/5 Diagnose tests plus 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S05/#18 is complete in PR #50 (`62d0e7b`): Build's mock-first/service-boundary contract, fail-closed authorization, ordered content, capability-derived versioning, first-party assets, Plan boundary, parity evidence, and software receipt limits; 5/5 Build tests plus 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S06/#19 is complete in PR #52 (`a3dfb47`): provider-neutral CloudBase/backend contract, readiness/package/privacy gates, function/health/projection/Hosting/client evidence layers, S01-valid causal receipt binding and reuse/invalidation fields, explicit backend N/A, security failure, and Hosting drift fixtures; 6/6 CloudBase tests plus 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S07/#20 is complete in PR #54 (`64fffa0`): Experience compile/simulator/upload/target/review/release separation, project/tool/environment identity, clean-tree and ignored-config restoration, operator-state preservation, backend-only N/A, and S01-valid upload receipts; 6/6 Experience tests plus 6/6 CloudBase, 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S08/#21 is complete in PR #56 (`665b120`): Device Acceptance role/device/task matrix, exact Experience-version binding, projection/HTTP/pixels/expiry evidence ladder, weak-network/retry checks, client-only log attribution, smallest physical human gate, protected-content failure, and S01-valid device receipts; 6/6 Device tests plus 6/6 Experience, 6/6 CloudBase, 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S09/#22 is complete in PR #58 (`b726460`): Release payment applicability/provider truth, distinct review/release read-back/smoke gates, complete S01 human-gate records, predecessor version causality, terminal `project_state=released`, payment N/A, human-blocked, and mismatch fixtures; 6/6 Release tests plus 6/6 Device, 6/6 Experience, 6/6 CloudBase, 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S10/#23 is complete in PR #60 (`ae5190c`): QA state/result/candidate/target/evidence matrix schemas, deterministic integer-profile JCS-compatible digests, candidate-before-target binding, privacy/evidence modes, approved-store governance, identity invalidation, and QA_FAIL restore controls; 11/11 QA tests plus 6/6 Release, 6/6 Device, 6/6 Experience, 6/6 CloudBase, 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S11/#24 is complete in PR #62 (`54d658c`): independent fresh-context/read-only evaluator packet, worker/evaluator and candidate/worktree provenance, PASS/FAIL/BLOCKED policy, prerequisite-missing, bounded same-contract repair, non-contract identity reset, stale-packet clearing, and attempt-three escalation; 10/10 evaluator tests plus 11/11 QA, 6/6 Release, 6/6 Device, 6/6 Experience, 6/6 CloudBase, 5/5 Build, 5/5 Diagnose, 6/6 Plan, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S12/#25 is complete in PR #64 (`8297169`): Browser QA-1/QA-2 contract, dual localhost raw adapter, sanitized Browser-first captures, candidate/compile/render matrix provenance, 8-state coverage, drift findings, prerequisite-missing, and pass→defect→restore controls; 8/8 Browser tests plus 10/10 evaluator, 11/11 QA, 6/6 Release, 6/6 Device, 6/6 Experience, 6/6 CloudBase, 5/5 Build, 6/6 Plan, 5/5 Diagnose, 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S13/#26 is complete in PR #66 (`24b07ea`): strict ordered raw DevTools event contract, QA-1 candidate-render and QA-2 upload/read-back/final-compile gates, nine-state per-screenshot matrix coverage, source/screenshot/before-after/final-compile provenance, sanitized evidence, prerequisite-missing semantics, Simulator `verified_device=false`, and hermetic loopback negative controls; 11/11 DevTools tests plus the S12/S11/S10/S01 regression set passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S14A/#27 is complete in PR #68 (`6fb9c6a`): QA advisory-only integration, Ask Park-owned QA_PASS/QA_BLOCKED/QA_FAIL routing, Diagnose confirmation, complete receipt-closure checks before causal rewind, interrupted/recovery module preservation, persisted human-gate blocking, privacy-safe packets, and bounded repair/reset/escalation controls; 9/9 S14A tests plus the 101-test S01/S10–S13 regression set passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S14B/#28 is complete in PR #70 (`6e95de1`): 23 architecture + 22 QA raw forward scenarios, canonical JCS-bound manifest, per-scenario fixture closures/allowed-input enforcement, observed state/result oracles, Browser/DevTools/evaluator/QA-schema/lifecycle/QA-routing pass→defect→restore controls, third-failure/no-fourth proof, artifact-tree privacy, and nested zero-side-effect receipts; 8/8 forward tests plus the full staged/module regression set passed. Staged validation, `py_compile`, diff-check, gitleaks, and both adversarial reviews passed.
- S15/#29 is complete in PR #72 (`b395598`): isolated synthetic-reader trial bound Browser and DevTools to one candidate/project identity, caught stale live drift, duplicate title, double safe area, stale package, and missing final compile, proved fresh repair evidence, post-automation human blocking, three-failure escalation/no-fourth, actual touched-target/side-effect receipts, and sanitized artifacts; 6/6 trial tests plus the full staged/module regression set passed. Staged validation, `py_compile`, diff-check, gitleaks, and both adversarial reviews passed.
- S16A/#30 is complete in PR #74 (`19a7bc6`): staging-only scanned-root/symlink/realpath inventory, redacted file refs, JCS-bound canonical package manifest, verified repository/history pre-migration receipt, outside-root staging scope, private/symlink escape rejection, transactional cleanup, managed four-checkpoint rollback rehearsals, and no root/active-skill cutover; 12/12 migration tests plus the full staged/module regression set passed. Staged validation, `py_compile`, diff-check, gitleaks, and both reviews passed.
- S16B/#31 is complete in PR #76 (`6fc11b4`): canonical Ask Park promoted to root with exactly one SKILL/metadata pair, full closure at root, staging duplicate removed, capability-first README with managed temporary clean-clone installer, closure manifest equality, full router/module/QA canary, seven-path missing-file failures, and no active local path mutation; root final layout and full regression suite passed. Final package, py_compile, diff-check, gitleaks, and both cutover reviews passed.
- S16C/#32 is complete in PR #78 (`1bfe3a1`): actual two-root inventory, one-canonical/zero-legacy selector read-back, installed manifest/canary equality, atomic legacy backup/canonical move, four rollback rehearsals, automatic post-apply rollback, final reapply, and sanitized operational receipt; 7/7 installed-cutover tests plus the full root regression suite passed. Final layout, `py_compile`, diff-check, gitleaks, and both reviews passed.
- S16D/#33 is complete and closed in PR #79 (`e1440a6`): capability-first README, proven clean-clone install/upgrade/rollback boundaries, latest installed canary/read-back, public evidence limits, and final Registry status. No real Mini Program release is implied.

## 下一步

1. [#33 / S16D](https://github.com/zinan92/wechat-miniprogram-shipping/issues/33) is merged and closed; the implementation queue is complete.
2. The next work is a separately scoped, human-approved, non-production Mini Program real-use trial; do not infer production readiness from this repository.
3. Preserve hard WIP=1; do not turn the trial into an implicit production-release claim.

## Evidence

- [Ask Park design](docs/superpowers/specs/2026-08-20-ask-park-seven-module-architecture-design.md)
- [Independent QA Gate design](docs/superpowers/specs/2026-08-24-ask-park-independent-qa-gate-design.md)
- [Implementation plan](docs/superpowers/specs/2026-08-24-ask-park-implementation-plan.md)
- [PR #5](https://github.com/zinan92/wechat-miniprogram-shipping/pull/5)
- [PR #7](https://github.com/zinan92/wechat-miniprogram-shipping/pull/7)
- [PR #11](https://github.com/zinan92/wechat-miniprogram-shipping/pull/11)
- [PR #36](https://github.com/zinan92/wechat-miniprogram-shipping/pull/36)
- [PR #39](https://github.com/zinan92/wechat-miniprogram-shipping/pull/39)
- [PR #42](https://github.com/zinan92/wechat-miniprogram-shipping/pull/42)
- [PR #44](https://github.com/zinan92/wechat-miniprogram-shipping/pull/44)
- [PR #46](https://github.com/zinan92/wechat-miniprogram-shipping/pull/46)
- [PR #48](https://github.com/zinan92/wechat-miniprogram-shipping/pull/48)
- [PR #50](https://github.com/zinan92/wechat-miniprogram-shipping/pull/50)
- [PR #52](https://github.com/zinan92/wechat-miniprogram-shipping/pull/52)
- [PR #54](https://github.com/zinan92/wechat-miniprogram-shipping/pull/54)
- [PR #56](https://github.com/zinan92/wechat-miniprogram-shipping/pull/56)
- [PR #58](https://github.com/zinan92/wechat-miniprogram-shipping/pull/58)
- [PR #60](https://github.com/zinan92/wechat-miniprogram-shipping/pull/60)
- [PR #62](https://github.com/zinan92/wechat-miniprogram-shipping/pull/62)
- [PR #64](https://github.com/zinan92/wechat-miniprogram-shipping/pull/64)
- [PR #66](https://github.com/zinan92/wechat-miniprogram-shipping/pull/66)
- [PR #68](https://github.com/zinan92/wechat-miniprogram-shipping/pull/68)
- [PR #70](https://github.com/zinan92/wechat-miniprogram-shipping/pull/70)
- [PR #72](https://github.com/zinan92/wechat-miniprogram-shipping/pull/72)
- [PR #74](https://github.com/zinan92/wechat-miniprogram-shipping/pull/74)
- [PR #76](https://github.com/zinan92/wechat-miniprogram-shipping/pull/76)
- [PR #78](https://github.com/zinan92/wechat-miniprogram-shipping/pull/78)
- [PR #79](https://github.com/zinan92/wechat-miniprogram-shipping/pull/79)
- [Installed cutover receipt](receipts/installed-cutover.json)
- [Public read-back receipt](receipts/public-readback.json)
- [Implementation Dev Queue](https://github.com/zinan92/wechat-miniprogram-shipping/issues?q=is%3Aissue%20state%3Aopen%20label%3Aenhancement)
