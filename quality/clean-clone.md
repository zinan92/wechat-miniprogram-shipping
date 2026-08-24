# S16B atomic cutover and clean-clone contract

S16B promotes the reviewed staged package to the repository root and proves
that the README installer is complete in an isolated temporary `CODEX_HOME`.
It does not touch the user's active local skill; S16C owns that cutover.

## Atomic repository shape

The final repository has exactly one root `SKILL.md` with `name: ask-park` and
one root `agents/openai.yaml`. The complete closure lives under root
`modules/`, `quality/`, `references/`, `scripts/`, `tests/`, and `fixtures/`.
The old `staging/ask-park` duplicate is removed before merge.

## Clean-clone proof

`scripts/clean-clone.py` follows the README closure into an isolated
`CODEX_HOME`, records every installed file digest, compares it with the branch
package manifest, loads the router, all seven module contracts, and all QA
seams, then runs a real Ask Park continuation canary. Removing one referenced
contract must fail loudly; missing-file failure is not silently repaired.

The receipt is sanitized and uses only a redacted isolated-home reference.
`quick_validate`, final package layout, full isolated tests, gitleaks, and diff
checks are required before the root cutover is merged.
