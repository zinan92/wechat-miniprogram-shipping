# Ask Park Independent QA Gate

Status: proposed design for Park review  
Issue: [#6](https://github.com/zinan92/wechat-miniprogram-shipping/issues/6)  
Depends on: Ask Park architecture [#4](https://github.com/zinan92/wechat-miniprogram-shipping/issues/4) / [PR #5](https://github.com/zinan92/wechat-miniprogram-shipping/pull/5)  
Scope: design only

## Outcome

Ask Park must prevent Park from becoming the first tester of automatable software, rendering, deployment, or evidence defects.

QA is an independent horizontal gate across the seven Ask Park modules. It is not an eighth mental anchor and does not add another command.

```text
module worker → committed candidate → independent QA
                                      ├─ QA_PASS → next authorized action
                                      ├─ QA_FAIL → Diagnose → repair → rerun
                                      └─ QA_BLOCKED → human-only gate
```

## Roles and authority

### Worker

- implements one accepted issue;
- commits a reproducible candidate;
- supplies raw tests, diff, manifests, and claimed limitations;
- never signs its own QA result.

### QA evaluator

- is a distinct agent/reviewer role with fresh bounded context;
- receives the issue contract and raw evidence, not the implementation conversation;
- cannot edit or silently repair the candidate;
- emits findings and an advisory earliest invalidated layer;
- cannot route work, invalidate receipts, promote modules, or weaken acceptance.

### Diagnose & Recover

- establishes root cause and actual repair scope after an observed defect;
- does not promote modules.

### Ask Park

- activates Diagnose;
- invalidates causally affected receipts;
- selects the earliest module requiring revalidation;
- controls human gates and handoff.

### Independence prerequisite

If no eligible independent evaluator exists, QA cannot issue `QA_PASS`. Ask Park records `qa.execution_state=unavailable` and `qa.control_outcome=qa-prerequisite-missing`. Disclosure does not turn self-certification into independent QA.

## QA state

```yaml
qa:
  execution_state: unavailable | ready | running | complete
  result: none | QA_PASS | QA_FAIL | QA_BLOCKED
  control_outcome: none | qa-prerequisite-missing | needs-park-decision
  gate: contract | qa-1 | target | qa-2 | evidence | final
  candidate_manifest_digest: null
  target_manifest_digest: null
  attempt: 1
  max_attempts: 3
  origin_module: build
  result_receipt_id: null
```

Legal transitions:

```text
unavailable/prerequisite-missing → ready/none
ready/none → running/none
running → complete/QA_PASS
running → complete/QA_FAIL → repair → ready/none
running → complete/QA_BLOCKED
QA_FAIL attempt 3 → QA_FAIL + needs-park-decision
any non-none result + candidate/target/scope identity change → ready/none
QA_BLOCKED + human evidence → ready/none
```

Rules:

- `QA_FAIL`, `qa-prerequisite-missing`, and `needs-park-decision` prevent deployment, upload, promotion, and Park handoff.
- `QA_BLOCKED` is legal only after every automatable gate passes and only a human/platform/device gate remains.
- Tool or evaluator unavailability is `qa-prerequisite-missing`, never `QA_BLOCKED`.
- A repair candidate under the same issue increments the attempt; changes after PASS/BLOCKED start a new run at one; a superseding contract always starts at one.

## Gate contracts

| Gate | Module | Inputs | Checks | Output |
| --- | --- | --- | --- | --- |
| `contract` | Plan | issue, scope, forbidden paths, applicability | criteria testable; routes/states/human gates explicit | contract result or missing-decision findings |
| `qa-1` | Build | committed candidate, diff, tests, render matrix | software, security, reproducibility, applicable local Browser/DevTools rendering | candidate manifest, QA-1 result, sanitized evidence |
| `target` | CloudBase/backend | QA-1 receipt, deployment receipt, target alias | privacy, health, config/runtime read-back, Hosting identity if applicable | target result and validated deployment identity |
| `qa-2` | Experience | candidate manifest, target/upload receipt | live bundle/package identity, target render, final-compile provenance | target manifest and QA-2 result |
| `evidence` | Device | version-bound device/account matrix | freshness, correct version, no Simulator/log substitution | evidence result or human gate/device defect |
| `final` | Release | valid receipt chain, authorizations, payment/review/release read-back | causal identity, claim separation, release smoke | Release-scoped final result |

For non-UI work, visual checks are explicitly `not-applicable` with impact analysis. Missing evidence is never silently treated as not applicable.

## QA-1: before deployment or upload

QA-1 runs after commit and before any target mutation.

For UI work it requires:

- issue/forbidden-path check;
- scoped and relevant upstream/downstream tests;
- secret scan and diff check;
- reproduction from candidate SHA;
- local Web build and Browser render when Web changes;
- DevTools Compile and Simulator screenshots when Mini Program UI changes;
- comparable before/after routes, viewports, roles, and data states;
- affected and shared-component regression routes;
- applicable loading, empty, error, locked, long-title, and narrow-screen states;
- accessibility names and tap targets for changed interactions.

Results:

- `QA_PASS`: candidate may enter the applicable deployment module;
- `QA_FAIL`: emit defect packet and advisory invalidated layer;
- `qa-prerequisite-missing`: required independent evaluator or automatable GUI/tool is unavailable.

QA-1 never proves Hosting, uploaded experience, or physical-device behavior.

## QA-2: after target deployment, before Park

### Web

- read live `index.html`;
- compare live JS/CSS digests with the candidate/target manifests;
- open live routes in Browser and capture the QA-1 matrix;
- verify authentication mode, deep links, SPA fallback, and absence of mock markers;
- compare local candidate render with live target render.

### Native Mini Program

- open the exact project in WeChat Developer Tools;
- verify source/config identity and compile;
- clear/reopen when stale evidence is suspected;
- capture required Simulator routes/device profiles after final compile;
- read back uploaded version, note, timestamp, candidate digest, and target receipt.

Results:

- `QA_PASS`: automatable target checks pass;
- `QA_FAIL`: drift or regression emits findings;
- `QA_BLOCKED`: automation passes, but QR, physical device, second identity, account authorization, payment, or review action remains.

Simulator never produces `verified-device`.

## Evidence strength

| Surface | Proves | Does not prove |
| --- | --- | --- |
| Local Browser | candidate Web render | live Hosting or Mini Program |
| Live Browser | current Hosting render | Mini Program or physical device |
| DevTools Simulator | compiled Simulator render | iPhone/Android behavior |
| Upload receipt | named experience package exists | physical-device UX |
| Mirrored phone window | visible mirrored session | other devices/accounts |
| User phone screenshot | recorded screen/context | hidden flow or other routes |
| Physical-device observation | stated device/account/version path | other devices/accounts |

Use built-in Browser for Web and Computer Use for desktop-only DevTools. An unavailable surface never authorizes a stronger claim from weaker evidence.

## Before/after contract

Before capture:

- capture before modification when possible;
- bind source/package identity or label it historical/unknown;
- record surface, route, viewport/device, role, data state, tool/runtime, timestamp, and limitations;
- sanitize identifiers and private content.

After capture:

- render the exact committed candidate after final compile/reload;
- use equivalent surface, route, viewport/device, role, and data state;
- include affected plus shared-component regression routes;
- persist only sanitized original-resolution evidence;
- state what the screenshot cannot prove.

If before cannot be reproduced, use `approved-reference` or `historical-exception`, record uncertainty, and do not claim strict before/after equivalence. Missing after evidence or final-compile provenance always fails.

## Visual checks

When applicable QA verifies:

- no overflow, clipping, or one-character-per-line title collapse;
- one product header and one article title unless explicitly designed otherwise;
- safe area reserved once;
- specified content-to-header spacing;
- consistent badge, membership, button, and metadata alignment;
- removed controls and obsolete copy absent from actual render;
- stable empty/loading/error/locked states;
- readable typography at required widths;
- state not conveyed by color or position alone;
- tap targets not hidden by native chrome/safe areas;
- shared components consistent across consumers.

When practical, deliberately mutate a known-good invariant and require the visual/structural test to fail.

## Functional checks

Visual pass does not replace behavior. According to issue scope QA may verify:

- server-backed read state and homepage refresh;
- locked articles not marked read;
- favorites persist without changing article visibility;
- removed UI absent while legacy data remains when required;
- canonical article/section identity across Web/mobile/reader;
- mock/cloud adapter parity;
- live target uses the intended candidate;
- stable actionable failures.

Avoid destructive or duplicate business writes. Real writes require an approved fixture/test account or human gate.

## Manifest model

### Canonical digest

Digest bytes use RFC 8785 JSON Canonicalization Scheme, not YAML serialization. Parse into the JSON data model, remove top-level `digest`, reject duplicate keys/non-JSON tags/NaN/infinities, serialize with JCS, and SHA-256 the exact UTF-8 bytes. YAML examples are human-readable only.

### Pre-upload candidate manifest

```yaml
schema_version: 1
kind: qa-candidate
digest: sha256:...
qa_run_id: issue-265-attempt-1
issue_contract_id: 265
issue_contract_version: 1
origin_module: build
candidate:
  source_sha: abc123
  lockfile_digest: sha256:...
  build_config_digest: sha256:...
  build_artifact_digest: sha256:...
  native_project_config_digest: sha256:...
  runtime_config_digest: sha256:...
  package_digest: sha256:... | unavailable
predecessor_receipt_ids: [build-receipt-123]
qa1_evidence_hashes: [sha256:...]
```

Upload notes bind the source and immutable candidate digest:

```text
sha=abc123; qa_candidate=sha256:0123abcd...
```

### Post-upload target manifest

```yaml
schema_version: 1
kind: qa-target
digest: sha256:...
qa_run_id: issue-265-attempt-1
candidate_manifest_digest: sha256:0123abcd...
target:
  target_alias: park-experience
  deployment_receipt_id: upload-receipt-123
  environment_contract_alias: park-cloud
  platform_version: 1.0.27
  upload_note: "sha=abc123; qa_candidate=sha256:0123abcd..."
  live_index_digest: null
  asset_digests: []
predecessor_receipt_ids: [build-receipt-123, cloud-receipt-456]
```

Pre-target `contract`/`qa-1` results bind the candidate manifest only. Applicable `target`/`qa-2`/`evidence`/`final` results bind both candidate and target manifests; every post-target/final result requires both.

## Evidence matrix row

```yaml
surface: devtools-simulator
route: /pages/article/index
viewport: iphone-15-profile
role: member
data_state: published-readable-long-title
equivalence: exact | approved-reference | historical-exception
tool:
  name: wechat-devtools
  version: recorded-version
  runtime_or_base_library: recorded-version
before_evidence:
  ref: sanitized/before/article.png
  sha256: sha256:...
  captured_at: ISO-8601
  source_or_package_identity: prior-sha-or-unknown
after_evidence:
  ref: sanitized/after/article.png
  sha256: sha256:...
  captured_at: ISO-8601
  source_or_package_identity: sha256:0123abcd...
  final_compile_receipt_id: compile-receipt-123
limitations:
  - physical-device safe area not proven
```

Strict equivalence with mismatched route/viewport/role/data state fails. Missing tool/runtime, after hash, timestamp, identity, or final-compile provenance fails. A historical exception can excuse only missing/uncertain before evidence.

## QA results

### QA_PASS

```yaml
result: QA_PASS
qa_run_id: issue-265-attempt-1
candidate_manifest_digest: sha256:0123abcd...
target_manifest_digest: sha256:4567efgh... | null-for-pre-target
target_receipt_id: upload-receipt-123 | null-for-pre-target
predecessor_receipt_ids: [build-receipt-123]
gate: qa-1 | qa-2
observed_at: ISO-8601
evidence_hashes: [sha256:...]
passed_checks: [tests, visual, functional, evidence-integrity]
limitations: [physical-device acceptance remains]
```

PASS authorizes only the next Ask Park action, never global release.

### QA_FAIL

Any automatable acceptance, rendering, behavior, version, artifact, security, or evidence-integrity failure. It blocks handoff and requires a defect packet.

### QA_BLOCKED

Allowed only when all automation passed and the remaining requirement is genuinely human/platform/device-only. No failed screenshot, stale artifact, failed test, missing QA tool, or missing evaluator may remain.

## Defect packet

```markdown
QA_FAIL

Candidate manifest: sha256:0123abcd...
Attempt: 1/3
Origin module: Build
Proposed earliest invalidated layer: Build (advisory)
Failed gate: DevTools visual regression
Route/device: /pages/article/index · iPhone 15 profile

Observed:
- Two equivalent titles.
- Safe area reserved twice.
- Removed control remains visible.

Expected:
- One title.
- One safe-area reservation.
- Only contracted actions visible.

Evidence:
- sanitized/before/article.png
- sanitized/after/article.png

Required repair:
1. Fix the projection-level duplicate.
2. Remove the second offset.
3. Remove the obsolete UI without deleting retained legacy data.
```

QA references observable evidence and the accepted contract; it does not prescribe unrelated refactors or select the authoritative return module.

## Repair and routing

```text
candidate A → QA_FAIL attempt 1
candidate B → QA_FAIL attempt 2
candidate C → QA_PASS attempt 3
```

Each repair is committed and independently rerendered. Prior screenshots cannot prove a new candidate.

After attempt three fails, retain `QA_FAIL`, set `needs-park-decision`, preserve all attempts, stop blind changes, and ask Park whether to change the contract, accept a limitation, or choose another design.

Deterministic routing:

1. QA emits findings and advisory invalidated layer.
2. Ask Park preserves `interrupted_module`.
3. Missing human evidence with no defect creates a human gate; Diagnose stays inactive.
4. An observed defect activates Diagnose with the defect packet.
5. Diagnose confirms cause and repair scope.
6. Ask Park invalidates causal receipts and selects the earliest required module.
7. Worker repairs and commits a new candidate.
8. A fresh eligible QA evaluator reruns the applicable gate.

QA never marks modules complete. Diagnose never promotes. Ask Park alone routes.

## Artifact privacy

Persisted QA artifacts must be sanitized, whether committed or ignored. `.gitignore` is not a privacy control.

Sensitive evidence is either:

1. inspected ephemerally without copying/persisting it; or
2. stored only in an explicitly approved access-controlled evidence store with audience, retention, deletion, and redacted-reference rules.

Otherwise QA stops.

Complete private targets are resolved inside an approved tool adapter. QA sees stable aliases such as `park-cloud`; the adapter supplies the complete URL/environment directly to the tool without printing or recording it.

Never persist secrets, QR contents, credentials, full OpenIDs, payment data, private URLs, or private business content. Do not inspect browser cookies/passwords/profile storage or bypass authentication policy.

## Artifact layout

```text
qa/<issue>-<timestamp>-attempt-<n>/
├── candidate-manifest.yaml
├── target-manifest.yaml
├── sanitized/before/*.png
├── sanitized/after/*.png
├── raw-sanitized/test-output.txt
├── visual-findings.md
├── defect-packet.md
└── qa-result.yaml
```

## Park handoff

Ask Park may contact Park for acceptance only with:

- `QA_PASS`: candidate/version, proven claims, sanitized before/after evidence, limitations; or
- `QA_BLOCKED`: every automatic check passed plus one smallest human-only action, expected observation, and claim boundary.

Park must never receive “please test everything” while an automatable defect remains.

## Behavioral evaluation

The eventual QA Agent must pass independent fixtures where the evaluator is not given the intended verdict:

1. Green tests plus duplicated title → `QA_FAIL`.
2. Correct local render plus stale live bundle → `QA_FAIL`.
3. Screenshot predating candidate/final compile → fail evidence integrity.
4. Simulator pass plus missing iPhone evidence → `QA_BLOCKED`, not device pass.
5. Failed automatable screenshot cannot hide behind BLOCKED.
6. Any identity change invalidates a non-none result.
7. Worker “looks fixed” summary without raw render fails.
8. Missing before uses documented exception, never fabrication.
9. Shared component change expands regression routes.
10. Old screenshot triggers version investigation before code changes.
11. Source repair during Experience rewinds Build receipts.
12. Three failures retain `QA_FAIL + needs-park-decision`.
13. No eligible evaluator → `qa-prerequisite-missing`.
14. Required Browser/DevTools unavailable → prerequisite missing, not BLOCKED.
15. Live assets not matching candidate/target manifests → fail.
16. Upload note/version/receipt mismatch → fail.
17. Missing row hash/tool/runtime/route/role/state/final compile → fail.
18. Baseline exception cannot excuse missing after evidence.
19. Sensitive screenshot is inspected ephemerally and absent from artifacts.
20. QA findings activate Diagnose; Ask Park alone routes.
21. QA never modifies code.
22. Seven mental anchors remain unchanged; no QA command appears.

## Proposed implementation

```text
ask-park/
├── SKILL.md
├── quality/
│   ├── QA-AGENT.md
│   ├── visual-evidence-contract.md
│   ├── qa-result-schema.md
│   └── regression-loop.md
├── modules/<seven existing modules>/
└── scripts/validate-qa-manifest.*
```

`SKILL.md` contains only the mandatory QA routing/stop hook. Detailed contracts load when a module produces a candidate. No `$qa`, `/qa`, start, next, debug, or release command is added.

## Rollout

1. Merge/implement Ask Park state and receipt foundation from #4.
2. Add QA schema and manifest validator.
3. Add independent evaluator and defect packet.
4. Add Web QA-1/QA-2.
5. Add DevTools QA-1/QA-2.
6. Add routing and three-attempt loop.
7. Run forward evaluations.
8. Trial on a non-production Mini Program UI issue.
9. Require QA before Park handoff only after trial passes.

## Success criteria

- Park is not the first to find an automatable visual regression.
- UI handoffs bind exact candidate and comparable sanitized rendering evidence.
- QA failure automatically returns through Diagnose for repair.
- QA_FAIL never reaches deployment or Park acceptance.
- QA_BLOCKED contains only genuine human work.
- Simulator, Hosting, logs, and device claims remain separate.
- Three failures stop blind iteration.
- QA is independent and never edits the candidate.
- Ask Park retains one entry and seven mental anchors.

## Non-goals

- approving by image-diff percentage alone;
- replacing Park's final product acceptance;
- claiming iPhone/Android behavior from Simulator;
- persisting private screenshots in public or ignored folders;
- destructive production QA writes;
- an eighth module or user-facing QA command;
- accepting changed requirements without a superseding issue.
