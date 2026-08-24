# Registry

## 现在在哪里

- Public repository: `zinan92/wechat-miniprogram-shipping`.
- Existing published capability remains `$wechat-miniprogram-shipping`; no runtime behavior or installed-skill identity has changed yet.
- Ask Park single-entry, seven-module architecture is approved and merged in PR #5.
- Independent Ask Park QA Gate design is approved by Park and merged in PR #7. Its three-round independent review findings were addressed; the final two schema corrections were mechanically validated after the review ceiling and remain visible in the PR record.
- The L-level implementation plan is approved by architecture, QA/test, and packaging reviewers and merged in PR #11.
- Dependency-ordered implementation issues #12–#33 are published. V1 WIP is hard-capped at one.
- S00/#12 is complete in PR #36 (`0e2e9b6`): staged package layout, validator, and hermetic harness; 9/9 targeted tests passed, staged validation passed, gitleaks passed.
- S01/#13 is now the only `ready-for-agent` story. Ask Park router/state/modules, QA evaluator/Browser/DevTools workflows, migration, and forward evaluations remain unimplemented.

## 下一步

1. Implement [#13 / S01](https://github.com/zinan92/wechat-miniprogram-shipping/issues/13): core state, receipt, applicability, and human-gate schemas.
2. Merge S01 after its gates pass, update this Registry, then make #14/S01B ready from the new `main`.
3. Preserve hard WIP=1 and the published dependency order through #33/S16D.

## Evidence

- [Ask Park design](docs/superpowers/specs/2026-08-20-ask-park-seven-module-architecture-design.md)
- [Independent QA Gate design](docs/superpowers/specs/2026-08-24-ask-park-independent-qa-gate-design.md)
- [Implementation plan](docs/superpowers/specs/2026-08-24-ask-park-implementation-plan.md)
- [PR #5](https://github.com/zinan92/wechat-miniprogram-shipping/pull/5)
- [PR #7](https://github.com/zinan92/wechat-miniprogram-shipping/pull/7)
- [PR #11](https://github.com/zinan92/wechat-miniprogram-shipping/pull/11)
- [PR #36](https://github.com/zinan92/wechat-miniprogram-shipping/pull/36)
- [Implementation Dev Queue](https://github.com/zinan92/wechat-miniprogram-shipping/issues?q=is%3Aissue%20state%3Aopen%20label%3Aenhancement)
