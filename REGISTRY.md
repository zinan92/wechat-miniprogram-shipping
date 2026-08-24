# Registry

## 现在在哪里

- Public repository: `zinan92/wechat-miniprogram-shipping`.
- Existing published capability remains `$wechat-miniprogram-shipping`; no runtime behavior or installed-skill identity has changed yet.
- Ask Park single-entry, seven-module architecture is approved and merged in PR #5.
- Independent Ask Park QA Gate design is approved by Park and merged in PR #7. Its three-round independent review findings were addressed; the final two schema corrections were mechanically validated after the review ceiling and remain visible in the PR record.
- The L-level implementation plan is approved by architecture, QA/test, and packaging reviewers and merged in PR #11.
- Dependency-ordered implementation issues #12–#33 are published. V1 WIP is hard-capped at one.
- S00/#12 is complete in PR #36 (`0e2e9b6`): staged package layout, validator, and hermetic harness; 9/9 targeted tests passed, staged validation passed, gitleaks passed.
- S01/#13 is complete in PR #39 (`366edb0`): core state/receipt/applicability/human-gate contracts; 21/21 S01 tests plus 9/9 S00 tests passed, staged validation and gitleaks passed.
- S01B/#14 is complete in PR #42 (`defa799`): mutation-free lifecycle transitions, causal receipt issuance/reuse/invalidation/rewind, Diagnose overlay, human-gate lifecycle, control-outcome clearing, and explicit receipt migration; 30/30 lifecycle tests, 22/22 S01 tests, and 9/9 S00 tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S02/#15 is complete in PR #44 (`c644ada`): one staged `$ask-park` entry, deterministic route classification, six-module plus Diagnose progress map, explicit control outcomes, causal rewind handoff, and four operator sections; 9/9 router tests plus 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S03/#16 is complete in PR #46 (`57d7ddd`): Plan's six-part contract, applicability reasons, S/M/L sizing/test depth, risk map, bounded solution search, issue-ready story shape, and safe new/takeover/scope-change stop fixtures; 6/6 Plan tests plus 9/9 router, 30/30 lifecycle, 22/22 state, and 9/9 package tests passed. Staged validation, `py_compile`, diff-check, gitleaks, and both independent spec/standards reviews passed.
- S04/#17 is the next story to implement. Build through Release modules, QA workflows, migration, and forward evaluations remain unimplemented.

## 下一步

1. Implement [#17 / S04](https://github.com/zinan92/wechat-miniprogram-shipping/issues/17): Diagnose & Recover.
2. Merge S04 after its gates pass, update this Registry, then make the next dependency-ready story ready from the new `main`.
3. Preserve hard WIP=1 and the published dependency order through #33/S16D.

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
- [Implementation Dev Queue](https://github.com/zinan92/wechat-miniprogram-shipping/issues?q=is%3Aissue%20state%3Aopen%20label%3Aenhancement)
