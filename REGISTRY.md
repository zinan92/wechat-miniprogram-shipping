# Registry

## 现在在哪里

- Public repository: `zinan92/wechat-miniprogram-shipping`.
- Existing published capability remains `$wechat-miniprogram-shipping`; no runtime behavior or installed-skill identity has changed yet.
- Ask Park single-entry, seven-module architecture is approved and merged in PR #5.
- Independent Ask Park QA Gate design is approved by Park and merged in PR #7. Its three-round independent review findings were addressed; the final two schema corrections were mechanically validated after the review ceiling and remain visible in the PR record.
- Ask Park, the seven internal modules, QA Agent, manifest validator, migration, and forward evaluations are **not implemented**.

## 下一步

1. Write and review the implementation plan from the merged architecture contracts.
2. Split implementation into dependency-ordered GitHub issues with one story per PR.
3. Implement the Ask Park router and shared state/receipt foundation before module or QA behavior.
4. Trial the independent QA Gate on a non-production Mini Program UI issue before making it mandatory for Park handoff.

## Evidence

- [Ask Park design](docs/superpowers/specs/2026-08-20-ask-park-seven-module-architecture-design.md)
- [Independent QA Gate design](docs/superpowers/specs/2026-08-24-ask-park-independent-qa-gate-design.md)
- [PR #5](https://github.com/zinan92/wechat-miniprogram-shipping/pull/5)
- [PR #7](https://github.com/zinan92/wechat-miniprogram-shipping/pull/7)
