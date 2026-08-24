# Ask Park and Independent QA Gate Implementation Plan

Status: proposed implementation plan  
Planning issue: [#10](https://github.com/zinan92/wechat-miniprogram-shipping/issues/10)  
Architecture: [Ask Park](2026-08-20-ask-park-seven-module-architecture-design.md) and [Independent QA Gate](2026-08-24-ask-park-independent-qa-gate-design.md)

## Sprint goal

Deliver one installable `$ask-park` skill that routes Mini Program work through six sequential modules plus Diagnose & Recover, enforces causal evidence receipts, and requires independent QA before deployment or Park handoff.

## Planning assumptions

- This is an L implementation delivered as dependency-ordered PRs, not one sprint-sized code dump.
- Calendar duration and historical velocity are unknown; story sizes are relative planning units, not delivery promises.
- V1 WIP is hard-capped at one implementation PR at a time.
- Reserve at least 20% capacity for forward-evaluation findings and migration repairs.
- Each story starts from current `main`, merges immediately after its gates pass, and the next story starts from the new `main`.
- No implementation test may mutate a real Mini Program, CloudBase environment, payment system, WeChat review state, credentials, or private customer data.
- Until the final cutover wave, all new behavior lives in `staging/ask-park/`, which is not an active scanned skill location. The existing root `$wechat-miniprogram-shipping` entry, metadata, and documented installer remain valid.
- Internal modules use `MODULE.md`, never nested `SKILL.md` or nested `agents/openai.yaml`; the staged package has exactly one staged entrypoint and the final package has exactly one root entrypoint.

## Definition of Ready

Each story must have:

- merged predecessor stories;
- Why / What / 3–7 acceptance criteria;
- In/Out scope and forbidden changes;
- named files or module ownership;
- S/M/L size and test depth;
- safe fixtures and expected observable outputs;
- no unresolved product decision.

## Definition of Done

- scoped acceptance passes;
- required targeted/upstream/downstream tests pass;
- `quick_validate.py` passes for changed skill surfaces;
- `git diff --check` and gitleaks pass;
- changed behavior has a meaningful forward test, not wording-only assertions;
- PR body contains What / Why / Validation and `Closes #N`;
- `REGISTRY.md` is updated after merge;
- no implementation or evidence claim exceeds its module boundary.

## Dependency graph

```text
S00 staged package + hermetic harness
  → S01 core state/receipt schemas
  → S01B lifecycle/receipt engine
  → S02 Ask Park router/map
  → S03 Plan
  → S04 Diagnose & Recover
  → S05 Build
  → S06 CloudBase/backend
  → S07 Experience
  → S08 Device Acceptance
  → S09 Release
  → S10 QA schemas/validator
  → S11 independent evaluator/defect loop
  → S12 Browser QA
  → S13 DevTools QA
  → S14A QA→Diagnose→Ask Park routing integration
  → S14B full independent forward-evaluation matrix
  → S15 isolated end-to-end trial
  → S16A canonical identity + migration tooling in staging
  → S16B atomic repository cutover + clean-clone install proof
  → S16C installed-path canary + recoverable local cutover
  → S16D public README/Registry publication
```

Default Dev Queue and merge order is exactly the sequence above. WIP is one. Limited parallelism is not planned for V1; this is a dependency/merge order rather than a calendar critical-path estimate.

Explicit joins remain contractual even with WIP one: S05 requires both S03 and S04; S14A requires the completed router/modules through S09 plus S10–S13; S14B requires S14A; S15 requires S14B; cutover cannot begin before S15 passes.

## Test-depth policy

| Size | Required depth |
| --- | --- |
| S | targeted validation for the changed contract |
| M | targeted plus immediate upstream/downstream behavioral tests |
| L | plan review first, full isolated forward-evaluation matrix, migration/rollback exercise, and final package validation |

Ordinary module stories are M. S14B, S15, S16B, and S16C are L integration/release stories.

## Story-to-path ownership

| Story | Exclusive primary paths |
| --- | --- |
| S00 | `staging/ask-park/` skeleton, `tools/validate-package-layout.py`, `tests/package-layout/` |
| S01 | `staging/ask-park/references/{status,evidence,human-gates}-contract.md`, `scripts/validate-state.*`, `tests/state/`, `fixtures/state/` |
| S01B | `scripts/state-lifecycle.*`, `references/transition-contract.md`, `tests/lifecycle/`, `fixtures/lifecycle/` |
| S02 | staged `SKILL.md`, `references/router.md`, `tests/router/`, `fixtures/router/` |
| S03 | `modules/01-plan/` and matching `tests/modules/plan/`, `fixtures/modules/plan/` |
| S04 | `modules/07-diagnose/` and matching `tests/modules/diagnose/`, `fixtures/modules/diagnose/` |
| S05–S09 | `modules/02-build/` through `modules/06-release/` and matching module tests/fixtures |
| S10 | `quality/{qa-state,qa-manifests,qa-results,evidence-matrix}.md`, `scripts/validate-qa-manifest.*`, `tests/qa-schema/`, `fixtures/qa-schema/` |
| S11 | `quality/QA-AGENT.md`, `quality/regression-loop.md`, `tests/qa-evaluator/`, `fixtures/qa-evaluator/` |
| S12 | `quality/browser-qa.md`, `tests/browser-qa/`, `fixtures/browser-qa/` |
| S13 | `quality/devtools-qa.md`, `tests/devtools-qa/`, `fixtures/devtools-qa/` |
| S14A | `quality/qa-routing.md`, `tests/qa-routing/`, `fixtures/qa-routing/` |
| S14B | `tests/forward-evals/`, `fixtures/forward-evals/`, evaluation report |
| S15 | isolated synthetic trial fixture and trial receipt |
| S16A | staged identity/metadata, migration inventory/tooling, rollback procedure |
| S16B | root package cutover, root metadata, minimum correct README installer, clean-clone receipt |
| S16C | installed-canary/cutover/rollback receipt; no repository behavior beyond evidence |
| S16D | final README narrative, final Registry release summary, public release evidence |

All paths in the table are under `staging/ask-park/` unless stated otherwise. Only S16B may promote the staged package to repository root. Package validation rejects internal `SKILL.md` or `agents/openai.yaml` below the single package entrypoint. `REGISTRY.md` is an append-only shared post-merge completion path for every story; S16D owns only the final public release summary.

## Wave 1: Foundation

### S00 — Staged package layout and hermetic test harness

**Why:** Every later story needs fixed paths and safe fixtures without breaking the currently installed/public skill.

**What:** Create the non-discoverable `staging/ask-park/` package skeleton, package-layout validator, test runner, fixture conventions, and zero-network hermetic adapter interfaces.

**Acceptance Criteria:**

- Staging contains one `SKILL.md`, one `agents/openai.yaml`, and empty owned directories for `modules`, `quality`, `references`, `scripts`, `tests`, and `fixtures`.
- Internal module directories permit `MODULE.md` but reject nested `SKILL.md` and `agents/openai.yaml`.
- Layout validator has staged and final modes and verifies complete referenced-file closure.
- Test harness can assert zero external network/mutation and consume record/replay adapter outputs.
- Root `SKILL.md`, root metadata, README installer, and installed skill behavior are unchanged.

**Paths:** `staging/ask-park/**`, `tools/validate-package-layout.py`, `tests/package-layout/**`.  
**Out:** substantive router/module/QA behavior.  
**Forbidden:** make staging discoverable; duplicate active entry.  
**Size/Test:** S; targeted layout and missing-file mutation tests.

### S01 — Versioned state, receipt, and deterministic validators

**Why:** Routing and QA cannot be reliable while state and evidence exist only as prose.

**What:** Add core Ask Park schemas and validators for project state, module receipts, applicability, causal identity, invalidation declarations, and human-gate records. QA manifests/JCS belong exclusively to S10.

**Acceptance Criteria:**

- State axes represent current module, applicability, activity, evidence, Diagnose, control outcome, project terminal state, and human gates independently.
- Receipt validation binds schema/contract version, source, issue, predecessor receipts, artifact/package, redacted target, and invalidation rules.
- Fixtures cover valid, stale, invalid, not-applicable, and causal-rewind cases.
- Validator output is machine-readable and never stores secrets or complete private targets.
- No candidate/target QA manifest or QA result schema is introduced.

**Paths:** `staging/ask-park/references/status-contract.md`, `evidence-contract.md`, `human-gates-contract.md`; `scripts/validate-state.*`; `tests/state/**`; `fixtures/state/**`.  
**Out:** router/module instructions and migration.  
**Forbidden:** live platform calls; `next_module` in receipts.  
**Size/Test:** M; schema unit tests plus downstream invalidation fixtures.

### S01B — State-transition and receipt lifecycle engine

**Why:** Schemas alone cannot issue receipts, reject illegal transitions, close invalidation graphs, or clear control outcomes.

**What:** Implement deterministic lifecycle operations consumed by the router: legal transitions, receipt issuance/reuse, downstream invalidation/locking, human-gate lifecycle, control-outcome clearing, and schema/contract migration.

**Acceptance Criteria:**

- Illegal module/activity/evidence/Diagnose/project transitions fail with stable codes.
- Receipt issuance and reuse require valid predecessors and unchanged causal identities.
- Invalidation computes transitive downstream closure and selects the earliest stale prerequisite without routing authority.
- Human gates support prepared → awaiting-human → authorized → executed → read-back, plus denied/expired.
- Control outcomes clear only from defined evidence or superseding contracts.
- Version migration rejects incompatible receipts and verifies explicit compatible migrations.

**Paths:** `staging/ask-park/scripts/state-lifecycle.*`, `references/transition-contract.md`, `tests/lifecycle/**`, `fixtures/lifecycle/**`.  
**Out:** router language and Release-specific authorizations.  
**Forbidden:** infer authorization from access; mutate live state.  
**Size/Test:** M; S01 unit integration plus illegal-transition mutation tests.

### S02 — Ask Park router and seven-module progress map

**Why:** Users need one entry and a stable mental model rather than choosing commands.

**What:** Implement the staged Ask Park entrypoint and routing contract using merged S01 and S01B behavior, selecting one current module and rendering all seven anchors while the root skill remains unchanged.

**Acceptance Criteria:**

- One user-facing entry routes new, takeover, failure, continuation, and release requests.
- Every substantive result renders six sequential modules plus Diagnose without creating extra commands.
- Router chooses the earliest required module lacking valid evidence.
- Failed/blocked modules remain current; formal release retains `current_module=release`.
- Conflicting sources, baseline conflict, and missing evidence produce explicit control outcomes.
- Only Ask Park promotes modules or invalidates dependent receipts.

**In:** `staging/ask-park/SKILL.md`, staged router reference, routing fixtures/tests.  
**Out:** detailed module behavior and QA.  
**Forbidden:** edit root `SKILL.md`, root metadata, or README installer before S16B; expose `$start/$next/$debug/$release`; infer state from chat alone.  
**Size/Test:** M; route-classification and state-transition tests.

### S03 — Plan module

**Why:** Development must start from a testable user outcome and issue contract.

**What:** Implement the Plan module's six-part contract, applicability decisions, risk map, solution search, S/M/L sizing, and issue-ready output.

**Acceptance Criteria:**

- Produces Outcome, 3–7 criteria, scope, forbidden changes, risk map, and ordered work.
- Marks every downstream module `required` or explicitly `not-applicable`.
- Stops on material unresolved intent or baseline conflict.
- Never requests secrets or starts code before an issue contract.
- Forward fixtures distinguish a new idea, takeover, and material scope change.

**In:** Plan module and fixtures.  
**Out:** automatic issue creation and code changes.  
**Forbidden:** silently alter accepted criteria.  
**Size/Test:** M; targeted plus router upstream tests.

### S04 — Diagnose & Recover module

**Why:** Failures must return to the earliest broken layer instead of triggering broad speculative repair.

**What:** Implement Diagnose overlay, interrupted-module tracking, falsifiable hypotheses, causal invalidation proposal, recovery outcomes, and bounded escalation.

**Acceptance Criteria:**

- Diagnose overlays rather than replacing the sequential current module.
- Loads shared contracts plus Diagnose and the interrupted module only.
- Distinguishes source, artifact, deployment, identity, permission, network, and device-only failures.
- Preserves recovery goal while Ask Park rewinds to the earliest confirmed invalidated prerequisite.
- Supports recovered, unresolved, and externally blocked outcomes without self-promotion.
- Fixtures cover repair with and without predecessor invalidation.

**In:** Diagnose module, incident schema, fixtures.  
**Out:** actual application debugging or mutation.  
**Forbidden:** bypass gates; indefinite retries; broad refactors.  
**Size/Test:** M; targeted plus router state-transition tests.

## Wave 2: Sequential modules

### S05 — Build module

**Why:** Software behavior must be proven locally without platform identity.

**What:** Implement mock-first, service-boundary, content/security/state-machine, stable-error, first-party asset, and software receipt guidance.

**Acceptance Criteria:**

- Routes code work only from an accepted issue.
- Requires mock/cloud page-facing parity and fail-closed authorization.
- Preserves ordered content and derives contract version from actual capabilities.
- Requires named SHA, scoped tests, audit, secrets, diff, and unverified assumptions.
- Never treats Simulator or source inspection as target/device evidence.

**In:** Build module/references/fixtures.  
**Out:** framework templates or real application code.  
**Forbidden:** deployment, real payment, unsafe storage.  
**Size/Test:** M; module fixtures plus Plan/CloudBase boundary tests.

### S06 — CloudBase/backend module

**Why:** Upload success is not a healthy, private, correctly deployed backend.

**What:** Implement provider-role contract for CloudBase or another backend, including packaging, rules, health, Hosting identity, short-lived assets, and redacted receipts.

**Acceptance Criteria:**

- Verifies collections/indexes/rules/runtime/config before deployment guidance.
- Requires clean production packaging without nested development dependencies.
- Separates function upload, health, projection, Hosting, and client evidence.
- Keeps protected storage closed and private targets out of artifacts.
- Supports causally valid receipt reuse and explicit not-applicable backend paths.

**In:** CloudBase/backend module and provider-neutral fixtures.  
**Out:** real provider credentials or deployment.  
**Forbidden:** public protected storage; CLI health as client proof.  
**Size/Test:** M; Build/Experience boundary and drift fixtures.

### S07 — Experience module

**Why:** A traceable experience package must bind source, backend contract, tool, and upload receipt.

**What:** Implement mock/configured gates, exact DevTools project/compile/upload flow, restore/clean-tree rule, version receipt, and operator-state protection.

**Acceptance Criteria:**

- Requires valid predecessors, formal AppID/env alignment, and reproducible tree.
- Separates Compile, Simulator, Upload, experience target, review, and release.
- Binds version/note/time/SHA/tool/base library/environment contract.
- Restores ignored local configuration and verifies clean release source.
- Supports explicit backend-only not-applicable path only with impact evidence.

**In:** Experience module and receipt templates.  
**Out:** actual upload or QR interaction during skill tests.  
**Forbidden:** upload equals release; uncommitted release source.  
**Size/Test:** M; CloudBase/Device boundary fixtures.

### S08 — Device Acceptance module

**Why:** Simulator, logs, and HTTP reachability cannot prove physical-device UX.

**What:** Implement role/device/task matrices, protected-content checks, asset evidence ladder, client-log attribution, weak-network/retry guidance, and human handoff.

**Acceptance Criteria:**

- Keeps projection, HTTP, pixels/layout, and expiry/fallback as separate evidence rungs.
- Requires experience-version-bound device/account results.
- Excludes CLI calls from real-client log attribution.
- States what screenshots, logs, and operator observations cannot prove.
- Produces smallest human gate rather than “test everything.”

**In:** Device module, matrices, fixtures.  
**Out:** physical-device automation in tests.  
**Forbidden:** one device proves all; server logs prove pixels.  
**Size/Test:** M; Experience/Release boundary fixtures.

### S09 — Release module

**Why:** Payment, review, and formal release are distinct final gates.

**What:** Implement payment applicability, provider-truth verification, human authorization, review/read-back, version causality, smoke receipt, and terminal state.

**Acceptance Criteria:**

- Keeps payment, review, and release claims distinct.
- Requires provider/server truth for applicable payment.
- Requires human authorization for legal/payment/review/release actions.
- Confirms released version matches accepted predecessor receipts.
- Records explicit payment not-applicable without skipping review/release.
- Produces `project_state=released` only after release read-back and smoke result.

**In:** Release module and fixtures.  
**Out:** real payment, legal, review, or release actions.  
**Forbidden:** client callback grants membership; access implies authority.  
**Size/Test:** M; Device/terminal-state tests.

## Wave 3: Independent QA

### S10 — QA schemas and manifest validator

**Why:** QA results must bind exact candidates, targets, and sanitized evidence mechanically.

**What:** Exclusively own QA state/result/candidate/target/evidence-matrix schemas, JCS digests, privacy modes, result invalidation, and compatibility tests. S01 provides only generic causal-receipt primitives.

**Acceptance Criteria:**

- JCS candidate manifest exists before upload; the target manifest references it after upload; pre-target results bind candidate only and applicable post-target results bind both.
- Matrix rows require route, viewport/device, role, state, tool/runtime, hashes, time, identities, and final-compile provenance; historical exceptions cannot excuse missing after evidence.
- Tool/evaluator unavailable is prerequisite missing, not BLOCKED, and any identity change invalidates the applicable result.
- Evidence mode is exactly `sanitized-persisted | ephemeral-only | approved-store-reference`; ephemeral evidence cannot leave persistent refs.
- Sensitive/mislabeled URL, OpenID, payment, QR, credential, filename, or byte fixtures fail persistence; approved-store references require audience, retention, deletion, access-control, and redacted-reference governance.
- Negative controls prove valid → seed malformed/stale manifest → `QA_FAIL` → restore → valid without changing candidate SHA.

**In:** QA schemas, validator, fixtures.  
**Out:** Browser/DevTools operations.  
**Forbidden:** YAML serializer-dependent digest; private ignored evidence.  
**Size/Test:** M; unit plus S01 causal integration.

### S11 — Independent evaluator and three-attempt defect loop

**Why:** Worker self-certification cannot satisfy independent QA.

**What:** Implement eligible-evaluator contract, bounded context builder, PASS/FAIL/BLOCKED policy, defect packets, attempt counting, and escalation.

**Acceptance Criteria:**

- QA evaluator is distinct, fresh-context, read-only, and records worker/evaluator identities, bounded inputs/exclusions, and candidate/worktree hashes before/after each attempt.
- No eligible evaluator produces prerequisite missing and blocks handoff.
- FAIL emits observable findings/advisory layer only; BLOCKED requires all automation passed.
- Candidate identity changes invalidate results; same-contract repairs increment, PASS/BLOCKED or superseding-contract changes reset to one.
- Attempt three remains `QA_FAIL + needs-park-decision` with no blind fourth repair.
- Fixtures reject self-signing, verdict/conversation leakage, candidate edits, and improper evaluator reuse.

**In:** QA evaluator contract/fixtures.  
**Out:** surface-specific capture.  
**Forbidden:** QA edits code or selects authoritative module.  
**Size/Test:** M; S04/S10 upstream/downstream behavior.

### S12 — Browser Web QA workflows

**Why:** Web changes require actual local and live rendering, not source-only assurance.

**What:** Implement Browser QA-1/QA-2 instructions and a hermetic adapter using two localhost fixture servers: immutable candidate assets and a swappable target that can serve matching, stale, mock-marked, or broken-deep-link artifacts.

**Acceptance Criteria:**

- Uses built-in Browser first and captures equivalent sanitized before/after evidence for affected and shared routes.
- Validates live index/JS/CSS digests and detects mock, auth-mode, deep-link, and SPA drift against manifests.
- Missing Browser is prerequisite missing, not QA BLOCKED.
- Matrix covers applicable loading, empty, error, locked, long-title, narrow-screen, accessibility-name, and tap-target states.
- Hermetic QA-2 compares candidate/target rendering from raw localhost adapter outputs with zero external mutation/network access.
- Negative control proves pass → inject stale bundle/mock marker/deep-link drift → `QA_FAIL` with evidence → restore → pass, candidate SHA unchanged.

**In:** Web QA module, fixture site, screenshots.  
**Out:** production Hosting mutation.  
**Forbidden:** DOM/source inspection substitutes render; private browser storage access.  
**Size/Test:** M; Browser fixture integration.

### S13 — DevTools Mini Program QA workflows

**Why:** Native Mini Program UI must be compiled and inspected before Park sees it.

**What:** Implement Computer Use/DevTools QA-1/QA-2 instructions plus a hermetic record/replay adapter or fixture app that emits raw project-open, compile, screenshot, upload-note, platform read-back, and final-compile events without real upload.

**Acceptance Criteria:**

- Opens the exact project, compiles/captures after final compile, records tool/base-library/device/route/state evidence, and binds upload note/read-back to source and candidate digest.
- Detects duplicate title, one-character wrapping, double safe area, stale copy/package, alignment, removed controls, and missing final-compile evidence.
- Simulator never produces verified-device; missing DevTools/Computer Use is prerequisite missing.
- Matrix covers affected/shared routes plus loading, empty, error, locked, English/Chinese long-title, narrow-screen, accessibility-name, and tap-target states.
- Negative controls prove pass → seed defined render/package/provenance defect → `QA_FAIL` and evidence → restore → pass, candidate SHA unchanged.
- Fake adapter asserts zero external network/platform mutation and derives decisions from raw events, not prose verdicts.

**In:** DevTools QA module and isolated fixtures.  
**Out:** real app upload or iPhone mutation in tests.  
**Forbidden:** weaker screenshot retains stronger claim.  
**Size/Test:** M; fixture manifests plus Computer Use contract tests.

### S14A — QA → Diagnose → Ask Park repair routing

**Why:** QA findings, diagnosis, causal invalidation, human gates, and repair attempts need one deterministic integration owner.

**What:** Integrate the completed router/modules through S09 with S10–S13 QA behavior. Implement non-defect human routing, observed-defect Diagnose activation, advisory QA layers, authoritative Ask Park invalidation, and attempt-state transitions.

**Acceptance Criteria:**

- Depends explicitly on S02, S04, S09, S10, S11, S12, and S13.
- QA emits findings/advisory layer only; Ask Park alone invalidates and routes after Diagnose confirms cause.
- Missing human device/account evidence without defect creates a human gate and does not activate Diagnose.
- Observed device or target defects activate Diagnose and preserve the interrupted/recovery modules.
- Same-contract repair, PASS/BLOCKED reset, superseding-contract reset, third-failure escalation, and no-fourth-repair rules are executable.
- Negative controls prove incorrect direct routing or QA self-promotion is rejected.

**In:** QA routing integration and fixtures.  
**Out:** full scenario matrix and migration.  
**Forbidden:** QA selects current module; wording-only state assertions.  
**Size/Test:** M; cross-module transition/mutation tests.

### S14B — Full independent forward-evaluation matrix

**Why:** The combined product needs raw, independent evidence that every Ask Park and QA invariant holds.

**What:** Implement every architecture and QA behavioral scenario with versioned fixtures, observable state/result oracles, negative controls, privacy tree inspection, and package validation.

**Acceptance Criteria:**

- Depends on S14A and includes all 23 Ask Park scenarios plus all QA scenarios from the merged designs.
- Independent evaluators receive raw fixtures, explicit allowed inputs/exclusions, and no intended verdict.
- Every surface has pass → seeded defect → expected failure/defect packet → restore → pass controls.
- Artifact-tree assertions prove sensitive fixture bytes/names are absent after execution.
- Zero external network/mutation is asserted for every fixture adapter.
- Full staged-skill validation, gitleaks, diff, package closure, and adversarial review pass.

**In:** forward evals, fixtures, evaluation report.  
**Out:** installed migration.  
**Forbidden:** canned verdict fixtures; live system/customer project use.  
**Size/Test:** L; complete isolated matrix and adversarial review.

## Wave 4: Productization

### S15 — Isolated end-to-end trial

**Why:** The QA Gate should become mandatory only after it catches a realistic defect without harming a real project.

**What:** Run Ask Park on an isolated synthetic Mini Program/Web fixture containing known visual, artifact, routing, and human-gate defects; verify repair loops and receipts.

**Acceptance Criteria:**

- Depends on S14B and QA catches test-green visual defects on both Browser and DevTools fixture paths.
- Stale local/live artifact mismatch is rejected.
- DevTools duplicate-title/double-safe-area/stale-package or final-compile defect is rejected.
- Repair produces a new candidate and fresh evidence.
- Physical-device requirement becomes BLOCKED only after automation passes.
- Three-failure escalation is exercised without blind fourth repair.
- Trial artifacts are sanitized and reproducible.

**In:** synthetic fixture and evaluation report.  
**Out:** real customer project trial.  
**Forbidden:** use `wechat-xingqiu` or production CloudBase as fixture.  
**Size/Test:** L; full-story trial and code-reviewer approval.

### S16A — Canonical identity and migration tooling in staging

**Why:** Cutover requires deterministic inventory, staging, and rollback tools before public or installed identities change.

**What:** Finalize staged `name: ask-park`, metadata, complete referenced-file manifest, scanned-root/symlink inventory tool, pre-migration digest receipt, staged installer, cutover checkpoints, and rollback procedure without changing root behavior.

**Acceptance Criteria:**

- Staged package contains one entrypoint/metadata pair and complete module/quality/script closure.
- Inventory enumerates every configured/scanned skill root, symlink, realpath, enabled state, and digest without printing secrets.
- Migration stages canonical install outside scanned roots before cutover.
- Rollback checkpoints cover staging failure, canonical validation failure, selector failure, and post-retirement failure.
- Repository identity/history remains `zinan92/wechat-miniprogram-shipping`.
- Root skill, root metadata, current README installer, and active local skill remain unchanged.

**In:** staged identity, inventory/migration/rollback tools and fixtures.  
**Out:** root or local cutover.  
**Forbidden:** change active identity; delete/move old install.  
**Size/Test:** M; hermetic scanned-root/symlink and checkpoint rollback tests.

### S16B — Atomic repository cutover and clean-clone install proof

**Why:** The public repository must never contain a root entrypoint that references files its documented installer omits.

**What:** Atomically promote the staged package to root, replace root identity/metadata, update the minimum README installation closure, and prove a clean-clone isolated installation before merge.

**Acceptance Criteria:**

- Root contains exactly one `SKILL.md` and one `agents/openai.yaml`; internal modules/quality contain no discoverable skill metadata.
- README commands copy the complete referenced closure: modules, quality, references, scripts, and required assets.
- Anonymous clean clone → follow README exactly into isolated temporary `CODEX_HOME` → validate package closure → invoke Ask Park router, every module-load path, QA-load path, and missing-file failure.
- Installed manifest records every file digest and matches the branch package.
- Staged source is removed or archived outside active package paths with no duplicated source of truth.
- `quick_validate`, package-layout final mode, full isolated tests, gitleaks, and diff pass.

**In:** root package, root metadata, minimum accurate README installer, clean-clone receipt.  
**Out:** user's active local installed skill.  
**Forbidden:** merge partial package; preserve active old alias in root.  
**Size/Test:** L; clean-clone installation and missing-dependency mutation tests.

### S16C — Installed-path canary, recoverable cutover, and rollback receipt

**Why:** Repository correctness does not prove the user's actual scanned skill roots and selector are safe.

**What:** Use S16A tooling after S16B merge to inventory real scanned roots, stage canonical install, run installed-path canary, cut over one public entry, and exercise rollback after every defined checkpoint.

**Acceptance Criteria:**

- Pre-migration receipt records scanned roots, symlink realpaths, enabled identities, file digests, and recoverable legacy backup outside scanned roots.
- Canonical install is validated before the old entry is disabled or moved.
- `$ask-park` discovery and installed-path router/module/QA smoke tests pass from the actual scanned path.
- Selector read-back shows one enabled `$ask-park` and no enabled `$wechat-miniprogram-shipping` duplicate.
- Rollback tests remove partial canonical state and restore/read back the legacy entry at every checkpoint.
- After the last rollback rehearsal, reapply the canonical cutover and freshly verify one enabled `$ask-park`, no legacy entry, installed-manifest equality, and router/module/QA smoke tests; this final read-back is the issue-closing state.
- Operational receipt is sanitized and committed for review before issue closure.

**In:** installed canary/cutover/rollback and receipt.  
**Out:** public narrative docs.  
**Forbidden:** unrecoverable delete; two enabled entries; claim success from repo clone alone.  
**Size/Test:** L; real local canary with reversible mutations and rollback proof.

### S16D — Public README, release evidence, and Registry publication

**Why:** Public documentation should describe observed installed behavior, not an unverified intended package.

**What:** After S16C passes, publish the capability-first Ask Park README, installation/rollback guidance, QA evidence boundaries, migration note, and final Registry position.

**Acceptance Criteria:**

- README explains one entry, seven anchors, QA Gate, evidence limitations, install, upgrade, and rollback using commands proven in S16B/S16C.
- Old invocation is described only as migrated/deprecated, never as an active alias.
- Links and file closure validate from an anonymous clean clone.
- Registry records implemented/installed/verified status separately and names the next real-use trial.
- S16D changes only README, release/migration receipts, and Registry; root metadata/runtime/package digests remain identical to the verified S16B/S16C state.
- gitleaks, diff, link/placeholder checks, and anonymous read-back pass.

**In:** README, migration/release receipt, Registry.  
**Out:** real Mini Program release claim.  
**Forbidden:** document unobserved behavior; alter runtime package.  
**Size/Test:** M; documentation/install replay and public read-back.

## Risk register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Root skill becomes too large | context dilution | keep router thin; progressive module loading |
| State validator overfits examples | false confidence | independent raw fixtures and mutation tests |
| QA requires unavailable GUI | stalled workflow | explicit prerequisite-missing state; no fake pass |
| Browser/DevTools APIs drift | broken QA | isolate tool-specific references and fixtures |
| Private screenshots leak | privacy harm | sanitized persistence, ephemeral sensitive inspection |
| Old/new skill both enabled | lost mainline | S16 selector read-back and recoverable retirement |
| QA creates endless loop | wasted effort | three-failure hard stop |
| Module receipt reused incorrectly | invalid promotion | causal identity and downstream invalidation tests |

## Review plan

Before implementation tickets are published, independent reviewers assess:

1. architecture/dependency boundaries and module depth;
2. testing/QA observability and non-live fixture strategy;
3. packaging/migration/discovery and rollback safety.

P0/P1 findings must be resolved in this plan. P2 items may become explicit later stories only when they do not make implementation ambiguous.

## Publication gate

After Park approves the reviewed plan:

1. publish S00–S16D as dependency-linked GitHub issues;
2. mark only S00 ready for execution initially;
3. keep V1 WIP hard-capped at one with no parallel exception;
4. begin implementation from fresh `main`;
5. merge and update Registry after every story.
