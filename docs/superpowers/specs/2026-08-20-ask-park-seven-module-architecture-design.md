# Ask Park: Seven-Module WeChat Mini Program Shipping Architecture

Status: proposed design for Park review  
Issue: [#4](https://github.com/zinan92/wechat-miniprogram-shipping/issues/4)  
Scope: architecture only; no skill implementation

## 1. Outcome

Create one durable user-facing entry, **Ask Park**, that guides a Mini Program from unclear intent to release through six ordered shipping modules and one cross-cutting recovery module.

Users should remember the product as:

> One conductor, six shipping gates, one repair lane.

The seven modules are first-class mental anchors. They must remain visible in status reports, have independent contracts, and hand work to each other through evidence. They are not seven competing commands.

## 2. Why this architecture

The current `wechat-miniprogram-shipping` skill contains a sound end-to-end workflow, but one large instruction surface makes three jobs harder:

1. A new user cannot easily tell where they are in the journey.
2. An agent may load release, payment, device, and diagnosis detail when only one stage matters.
3. Evidence from one layer can be accidentally promoted into a claim about another layer.

Ask Park solves these problems by separating **navigation**, **work**, and **proof**:

- the router determines the current module;
- one module performs the current class of work;
- a receipt proves that module's exit contract;
- the router alone promotes the project to the next module.

## 3. Product principles

### 3.1 One entry, visible modules

Ask Park is the only supported starting point. Every response shows the complete module map so users develop a stable mental model.

The modules must not be hidden as incidental reference files. Each has a name, responsibility, entrance contract, exit contract, forbidden boundary, and receipt type.

### 3.2 One current module

Exactly one sequential module may be current. A project cannot be simultaneously "in CloudBase" and "in Release".

Diagnose & Recover is an overlay. It may interrupt any sequential module, but it records the interrupted module and must return there after recovery.

### 3.3 Evidence cannot travel upward by implication

Evidence belongs to the module that produced it:

- local tests prove software behavior;
- CloudBase read-back proves a target backend;
- DevTools upload proves an experience package exists;
- device observation proves a recorded device path;
- payment verification proves a server-verified payment path;
- platform read-back proves review or release state.

No receipt may promote a different module without that module's own acceptance evidence.

### 3.4 Human gates stay human

QR scans, platform identity, legal terms, payment credentials, review submission, and release decisions remain human actions. Ask Park may prepare and verify surrounding work, but cannot infer authority from technical access.

### 3.5 Progressive disclosure

For ordinary work, the router loads shared contracts plus only the current module. During recovery it loads shared contracts, Diagnose & Recover, and exactly the interrupted module contract. It does not load all seven modules for every request.

## 4. User-facing mental model

Every substantive Ask Park response starts with a compact map:

```text
ASK PARK · MINI PROGRAM SHIPPING

1. Plan              completed  [planned]
2. Build             completed  [verified-software]
3. CloudBase         completed  [verified-cloud]
4. Experience        current    [evidence absent]
5. Device Acceptance waiting    [evidence absent]
6. Release           locked     [evidence absent]

7. Diagnose & Recover standby   [no incident]
```

The map displays separate axes rather than mixing workflow activity with proof:

- **activity state:** `locked | waiting | current | blocked-external | failed | completed | not-applicable`;
- **evidence state:** `absent | valid | stale | invalid | not-applicable` plus the module's evidence status such as `verified-cloud`;
- **diagnose activity:** `standby | active`;
- **diagnose outcome:** `none | unresolved | recovered | blocked-external`.

`blocked-external` and `failed` do not clear `current_module`; they describe why that same module cannot advance. When Diagnose is active, the interrupted sequential module remains `current_module` while `diagnose_state=active` overlays it.

The map is followed by exactly four operator sections:

1. conclusion;
2. current module and evidence;
3. decision or action needed from Park;
4. next verifiable step.

## 5. System architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                         ASK PARK                             │
│ intent classification · state read · routing · promotion    │
└──────────────────────────────┬───────────────────────────────┘
                               │ loads exactly one module
                               ▼
┌────────┐  ┌────────┐  ┌───────────┐  ┌────────────┐
│  Plan  │→ │ Build  │→ │ CloudBase │→ │ Experience │
└────────┘  └────────┘  └───────────┘  └──────┬─────┘
                                              │
                                              ▼
                                  ┌─────────────────────┐
                                  │ Device Acceptance   │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                      ┌────────────┐
                                      │  Release   │
                                      └────────────┘

              ┌─────────────────────────────────────────┐
              │ Diagnose & Recover                      │
              │ interrupt any module → repair → return  │
              └─────────────────────────────────────────┘
```

Ask Park owns routing and promotion. Modules own work and receipts. A module cannot mark the next module complete.

## 6. Router contract

### State record

The router operates on an explicit state record:

```yaml
schema_version: 1
project_state: active
current_module: experience
control_outcome: none
modules:
  plan:
    applicability: required
    activity_state: completed
    evidence_state: valid
    receipt_id: plan-example
  experience:
    applicability: required
    activity_state: current
    evidence_state: absent
diagnose:
  state: standby
  outcome: none
  interrupted_module: null
  recovery_goal: null
human_gate:
  state: not-needed
  action_scope: null
```

State invariants:

1. `current_module` always names exactly one of the six sequential modules. After formal release it remains `release` with `activity_state=completed` and `project_state=released`. When an approved target stops earlier, it remains the last required completed module with `project_state=target-achieved`.
2. A `failed` or `blocked-external` module remains `current_module`.
3. Diagnose never becomes `current_module`; `diagnose.state=active` overlays the interrupted module while `diagnose.outcome` records `none`, `unresolved`, `recovered`, or `blocked-external`.
4. Later modules are `locked` when any required predecessor has absent, stale, or invalid evidence.
5. A module can be `not-applicable` only from a Plan impact decision with a reason and receipt.
6. Regression or a changed causal identity rewinds `current_module` to the earliest invalidated prerequisite and locks later modules.
7. Completion promotes only to the earliest required or waiting module; modules cannot self-promote their successor.
8. `control_outcome` is one of `none | unknown | baseline-conflict | needs-human-state-reconciliation`. It does not replace or clear `current_module`.

Legal transition examples:

```text
waiting → current → completed
current → blocked-external → current
current → failed → Diagnose active → current
completed + invalidating change → stale → current
Diagnose active/outcome none → active/outcome unresolved | standby/outcome recovered | active/outcome blocked-external
recovered → earliest invalidated prerequisite current
control outcome unknown → none after direct evidence resolves the unknown
control outcome baseline-conflict → none only after a superseding contract is accepted
control outcome needs-human-state-reconciliation → none only after state sources are reconciled and recorded
```

### Input

- user intent or failure report;
- repository and Git state when available;
- GitHub issue contracts;
- project registry or equivalent current-state record;
- existing receipts and their timestamps;
- known human/platform blockers.

### Output

- full seven-module map;
- one current or interrupted module;
- evidence-backed current status;
- selected module contract;
- smallest next verifiable action;
- named human decision when required.

### Routing algorithm

1. Read state; do not infer it from the latest chat message alone.
2. Validate receipt causal bindings, freshness, and named source SHA/environment/package version.
3. If the user reports a failure, activate Diagnose & Recover and record the interrupted module.
4. Invalidate downstream receipts when source, contract, artifact, target, package, or acceptance scope changes.
5. Otherwise choose the earliest required sequential module whose exit contract is not satisfied.
6. Load shared contracts plus the selected module; during recovery also load Diagnose and the interrupted module.
7. Execute only actions authorized by the user and module boundary.
8. Produce or update the selected module receipt.
9. Promote only when every exit criterion has direct evidence.
10. Publish the seven-module map and the next action.

### Router failures

- conflicting state sources → `needs-human-state-reconciliation`;
- stale or missing receipt → rewind to the earliest invalidated prerequisite and lock later modules;
- original issue acceptance changed → require a superseding contract;
- sensitive or irreversible action lacks authority → `blocked-external`;
- target repository cannot be reproduced from a named SHA → activate Diagnose with Build as the earliest possible recovery module.

### Applicability and receipt reuse

Plan records every sequential module as `required` or `not-applicable` for the approved release target. `not-applicable` is an explicit receipt, never an omitted gate.

- A frontend-only change may reuse a valid CloudBase receipt only when backend contract, target identity, permissions, and environment configuration are unchanged.
- A backend-only change may mark Experience and Device as `not-applicable` only when the Mini Program package and its backend contract are unchanged and the accepted outcome does not require client retesting.
- A project without a backend marks CloudBase `not-applicable` with architecture evidence.
- A non-CloudBase serverless provider uses the CloudBase module's backend-role contract with a provider adapter and the same privacy, deployment, health, and read-back requirements.
- Payment may be `not-applicable`, but platform review and release remain independently evaluated when formal release is the target.

Receipt reuse is allowed only when every causal binding remains identical and the module's invalidation rules do not require a fresh observation.

### Human-gate protocol

Human-controlled actions use a separate state machine:

```text
not-needed → prepared → awaiting-human → authorized → executed → read-back
                                 └──────→ denied
authorized → expired
```

The authorization record contains action type, scope, authorizing role, timestamp, and a non-sensitive evidence reference. It never contains credentials, QR contents, legal documents, payment keys, or private identity values. Technical access, an authenticated CLI, or the ability to click a control never constitutes authorization. A denied or expired gate keeps the same sequential module current.

## 7. Module contracts

Every module implements the same six-part contract: **Input, Output, Success predicate, Failure outcomes and routing, Evidence, Forbidden boundary**. Responsibilities explain how the module works but do not replace the contract.

### Module 1: Plan

**Mental anchor:** Decide what useful result is being built before writing code.

**Input:** a product idea, takeover request, or material scope change, plus any existing product/repository evidence.

**Responsibilities:**

- define the user outcome and first useful moment;
- classify S/M/L complexity;
- define V1 and explicit deferrals;
- map AppID,主体, CloudBase, identity, storage, payment, device, review, and migration risk;
- inspect reusable products, repositories, components, and skills;
- create one issue contract per independently verifiable story.

**Output:** an approved V1 boundary, module applicability map, risk map, and ordered issue/milestone queue.

**Success predicate:** every independently verifiable story has an immutable issue contract; all six downstream modules are marked `required` or `not-applicable`; no unresolved intent decision can materially change the first useful moment.

**Failure outcomes and routing:** unclear outcome or material choice → remain in Plan and request one decision; missing repository/platform facts → `unknown` with read-only investigation; conflicting accepted baseline → `baseline-conflict`; identity, legal, or payment authority needed → `blocked-external`.

**Evidence:**

- Outcome;
- three to seven verifiable acceptance criteria;
- In/Out scope and forbidden changes;
- risk map;
- ordered issue or milestone queue.

**Forbidden:** coding before the issue contract, secret collection in chat, or calling an idea "MVP" without a bounded useful moment.

**Exit state:** `planned`.

### Module 2: Build

**Mental anchor:** Prove the product behavior locally before depending on platform identity.

**Input:** accepted issue contract, module applicability map, reproducible source repository, and valid Plan receipt.

**Responsibilities:**

- create a mock-first vertical slice;
- keep mock and cloud adapters behind one page-facing service boundary;
- design authorization and state machines before provider adapters;
- use ordered content blocks where text and images interleave;
- derive content-contract versions from actual parsed capabilities, not file extensions;
- preserve stable domain error codes across service boundaries;
- snapshot external images into controlled first-party assets;
- run scoped software, audit, secret, and diff gates.

**Output:** a committed mock-first vertical slice and software verification receipt tied to the accepted issue.

**Success predicate:** named source SHA reproduces the agreed slice; scoped tests and security/diff gates pass; known platform assumptions remain explicit; no out-of-scope feature is required for the first useful moment.

**Failure outcomes and routing:** test/contract/security failure → Diagnose with Build interrupted; missing issue or changed acceptance → Plan/`baseline-conflict`; unreproducible source → Diagnose and remain in Build; required credential/platform action → `blocked-external` without collecting secrets.

**Evidence:** named commit SHA, issue ID, clean scoped diff, software gate output, audit/secret result, and known unverified platform assumptions.

**Forbidden:** deploying to production, uploading an experience version, enabling real payment, or claiming simulator evidence is device evidence.

**Exit state:** `verified-software`.

### Module 3: CloudBase

**Mental anchor:** Prove the backend is deployed, private, healthy, and running the intended artifact.

**Input:** valid Build receipt, approved backend provider/target, deployment scope, and any causally reusable backend receipt.

**Responsibilities:**

- verify collections, indexes, seed data, storage rules, permissions, runtime, and environment variables;
- assemble a clean production deployment package without nested development dependencies;
- deploy only named functions and assets in scope;
- read back function state, runtime configuration, and code result;
- run dependency-safe health and read-only projection checks;
- verify Hosting build mode, live index bundle, deep links, and SPA fallback when a Web admin exists;
- keep private storage closed and issue authorized short-lived URLs.

**Output:** a target backend running the intended artifact with verified privacy, health, and read-back behavior, or an explicit `not-applicable` receipt.

**Success predicate:** deployed artifact and target bindings match the receipt; required health/projection checks pass; permissions and protected storage fail closed; live Hosting references the intended build when applicable.

**Failure outcomes and routing:** packaging/runtime/health/Hosting drift → Diagnose with CloudBase interrupted; target identity mismatch or missing authorization → `blocked-external`; backend architecture absent by approved design → `not-applicable`; security rule would require public protected data → failed with no unsafe fallback.

**Evidence:** redacted provider/target receipt, deployed artifact digest, runtime/config read-back, health result, permissions/storage result, and live Hosting read-back when applicable.

**Forbidden:** making protected storage public, treating an upload command as health proof, or counting CLI health calls as Mini Program client evidence.

**Exit state:** `verified-cloud`.

### Module 4: Experience

**Mental anchor:** Prove a named source version became a traceable WeChat experience package.

**Input:** valid required predecessor receipts, formal AppID/env alignment, named source SHA, release scope, and a clean reproducible tree.

**Responsibilities:**

- run mock and configured release gates;
- open the exact local project in DevTools;
- compile before upload and resolve stale cache deliberately;
- upload with explicit version and note;
- restore ignored local configuration after upload;
- read back the package version and experience target;
- preserve unsaved operator content during Web/DevTools deployment checks.

**Output:** a traceable experience package tied to the accepted source and backend contract, or an explicit `not-applicable` receipt for an approved backend-only change.

**Success predicate:** DevTools compiled the named tree; platform read-back shows the intended version/target; the upload receipt binds source SHA, package identity, environment contract, and tool version; local configuration is restored.

**Failure outcomes and routing:** compile/upload/cache/package drift → Diagnose with Experience interrupted; AppID/env/account mismatch or QR identity action → `blocked-external`; uncommitted source → invalidate Build receipt and rewind to Build; approved backend-only change with unchanged client contract → `not-applicable`.

**Evidence:** version, timestamp, commit SHA, package digest or stable version identity, redacted environment, tool/base-library version, upload receipt, and experience target.

**Forbidden:** claiming upload equals review/release, exposing AppSecret, or using an uncommitted tree as the release source.

**Exit state:** `verified-experience`.

### Module 5: Device Acceptance

**Mental anchor:** Prove real people, roles, devices, and failure conditions can use the experience build.

**Input:** valid Experience receipt, agreed device/role/task matrix, experience version, and prepared human test actions.

**Responsibilities:**

- test administrator and ordinary-member roles;
- test public and protected text/images and the agreed V1 task matrix;
- record iOS and Android route-level outcomes;
- test weak network, retry, expiry, refresh, and recovery paths;
- use the asset evidence ladder: projection → HTTP reachability → device pixels/layout → expiry/fallback;
- attribute CloudBase client logs by request source and request ID while excluding CLI calls;
- state what logs, screenshots, and operator observations cannot prove.

**Output:** a route-level real-device acceptance result for the agreed scope, or an explicit `not-applicable` receipt when client behavior is causally unchanged.

**Success predicate:** every required role/device/task cell has a fresh result for the bound experience build; protected-content and failure-path expectations hold; server evidence and visual/operator evidence are not conflated.

**Failure outcomes and routing:** observable device failure → Diagnose with Device interrupted; missing device/account/operator action → `blocked-external`; mismatched experience build → invalidate Experience and Device evidence; approved unchanged client behavior → `not-applicable` only with impact analysis.

**Evidence:** device/version/account-role matrix, fresh screenshots or observations, relevant redacted client-log attribution, failure-path results, and open failure list.

**Forbidden:** inferring device model or pixels from server logs, counting one device as full coverage, or treating HTTP 200 as visual acceptance.

**Exit state:** `verified-device`.

### Module 6: Release

**Mental anchor:** Separate payment, platform review, and formal release into explicit final gates.

**Input:** valid required predecessor receipts, approved release scope, payment applicability decision, prepared platform materials, and explicit human authorizations.

**Responsibilities:**

- verify payment using provider and server truth when payment is in scope;
- verify order owner, amount, payer, transaction, and event identity;
- prepare review materials without fabricating compliance claims;
- record platform review state by read-back;
- confirm released version matches the accepted experience/source version;
- run release smoke checks and publish a final receipt.

**Output:** an evidence-backed formal release state with payment, review, and release claims kept distinct.

**Success predicate:** every applicable final gate has a read-back result; released version causally matches accepted source/experience/device evidence; post-release smoke checks pass; non-applicable payment is explicitly recorded.

**Failure outcomes and routing:** payment mismatch, review rejection, release mismatch, or smoke failure → Diagnose with Release interrupted; legal/payment/review/release human action → `awaiting-human`/`blocked-external`; source or package fix required → invalidate from the earliest changed prerequisite.

**Evidence:** distinct payment receipt or `not-applicable`, review read-back, released version read-back, predecessor receipt IDs, timestamp, authorization references, and release smoke result.

**Forbidden:** using a client callback to grant membership, submitting legal/payment materials without human approval, or equating review approval with release before release read-back.

**Exit state:** `released`.

### Module 7: Diagnose & Recover

**Mental anchor:** Locate the broken layer, repair the smallest cause, prove recovery, and return to the interrupted module.

**Input:** observable failure or inconsistent evidence, interrupted module, original module contract, current receipt chain, and user authorization boundary.

**Responsibilities:**

- record the interrupted module and original success contract;
- inspect Local → Git → DevTools/artifact → WeChat package → CloudBase in order relevant to the symptom;
- preserve stable errors and request IDs rather than diagnosing generic UI text;
- distinguish source drift, build drift, upload drift, runtime drift, identity, permissions, network, and device-only failures;
- form falsifiable hypotheses and test the smallest safe one;
- verify recovery at the layer where the symptom occurred;
- preserve the interrupted module as the recovery goal while rewinding execution to the earliest prerequisite invalidated by the fix.

**Output:** a recovered, unresolved, or externally blocked incident record plus the correct post-diagnosis current module.

**Success predicate:** the original symptom is rechecked at its actual layer; the causal fix and regression proof are recorded; invalidated receipts are marked stale; the router selects the earliest module requiring revalidation.

**Failure outcomes and routing:** root cause not established → keep `diagnose.state=active` and set `diagnose.outcome=unresolved`; human/platform action required → keep Diagnose active with `diagnose.outcome=blocked-external`; repair fails verification → remain active with a bounded next hypothesis; repair changes an earlier artifact/contract → rewind to that earliest module and lock later modules.

**Evidence:** symptom, interrupted module, observed facts, root cause or remaining hypotheses, scoped fix, regression proof, target-environment read-back, invalidated receipt IDs, and explicitly unproven claims.

**Forbidden:** broad speculative refactors, bypassing security gates, retrying external writes indefinitely, or treating repair as automatic release progress.

**Exit state:** `diagnose.state` returns to `standby` only for `outcome=recovered`; unresolved or externally blocked incidents remain active. `current_module` is independently set to the earliest invalidated prerequisite or remains the interrupted module when no predecessor changed.

## 8. Shared status contract

Canonical evidence claims remain:

- `planned`;
- `verified-software`;
- `verified-cloud`;
- `verified-experience`;
- `verified-device`;
- `verified-payment` when applicable;
- `verified-review`;
- `released`;
- `not-applicable`.

`blocked-external`, `failed`, `unknown`, and `baseline-conflict` are activity/control outcomes, not evidence claims.

Each receipt includes:

```yaml
schema_version: 1
receipt_id: experience-example
module: experience
module_contract_version: 1
status: verified-experience
observed_at: ISO-8601 timestamp
source_sha: named commit
issue_contract_id: issue-or-superseding-contract
predecessor_receipt_ids:
  - build-example
  - cloud-example
target_ref: stable redacted alias
artifact_ref: version or digest
environment_contract_ref: redacted contract identifier
applicability: required
evidence:
  - artifact or URL reference
cannot_prove:
  - device acceptance
  - payment
blockers: []
human_authorization_refs: []
invalidation_rules:
  - source SHA changes
  - AppID/environment contract changes
  - uploaded package is replaced
```

Receipts are causal attestations, not timeless checklists. A receipt is valid only when:

1. its schema and `module_contract_version` are supported; a contract-version change invalidates the receipt unless the new contract declares and verifies an explicit backward-compatible migration;
2. every required predecessor receipt remains valid;
3. source, issue contract, artifact, provider target, environment contract, and package/device identities still match;
4. its module-specific observation remains fresh enough for the claim;
5. no invalidation rule has fired.

Freshness is claim-specific rather than one global duration. A commit-bound local test stays valid until relevant source or dependencies change; an ephemeral signed URL check expires with the URL; a device result becomes stale when the experience build, affected UI/runtime contract, required OS/device scope, or acceptance criteria change; platform review/release state must be read back for the currently bound version.

Changing any causal identity marks that receipt and all dependent receipts `stale`. A contradictory read-back marks it `invalid`. The router rewinds to the earliest affected module. Receipts never contain `next_module`; routing remains solely Ask Park's authority.

Receipts must not contain secrets, complete private URLs, OpenIDs, credentials, payment keys, or private business content.

## 9. Context-loading design

The canonical package is one standalone public skill named `ask-park` in the existing `zinan92/wechat-miniprogram-shipping` repository. The repository name remains stable; its root skill changes canonical identity from `wechat-miniprogram-shipping` to `ask-park` and contains seven internal module packages:

```text
ask-park/
├── SKILL.md
├── agents/openai.yaml
├── modules/
│   ├── 01-plan/
│   │   ├── MODULE.md
│   │   └── acceptance-contract.md
│   ├── 02-build/
│   │   ├── MODULE.md
│   │   └── software-receipt.md
│   ├── 03-cloudbase/
│   │   ├── MODULE.md
│   │   └── cloud-receipt.md
│   ├── 04-experience/
│   │   ├── MODULE.md
│   │   └── upload-receipt.md
│   ├── 05-device/
│   │   ├── MODULE.md
│   │   └── device-matrix.md
│   ├── 06-release/
│   │   ├── MODULE.md
│   │   └── release-receipt.md
│   └── 07-diagnose/
│       ├── MODULE.md
│       └── incident-receipt.md
├── references/
│   ├── status-contract.md
│   ├── evidence-contract.md
│   └── project-lessons.md
└── scripts/
    └── optional deterministic state validator
```

`SKILL.md` contains only the product promise, shared safety boundaries, state-reading rules, routing algorithm, and module index. Module detail stays in its own package and is loaded only after routing. Recovery loads shared contracts + Diagnose + exactly the interrupted module contract.

The only canonical explicit skill invocation is `$ask-park`; it is also discoverable through the host's enabled-skill picker. No start/next/debug/release aliases are created. A literal slash spelling is not required for correctness and must not create a second workflow entry.

Migration contract:

1. update root `SKILL.md` frontmatter to `name: ask-park` and preserve the shipping capability in its description;
2. update `agents/openai.yaml` display/default prompt to Ask Park;
3. install under the canonical local path `~/.codex/skills/ask-park`;
4. verify `$ask-park` routing and the seven-module map;
5. remove or disable the old local `wechat-miniprogram-shipping` skill only after read-back confirms the new installation;
6. document the rename in the repository README without preserving the old name as an active alias.

The old `$wechat-miniprogram-shipping` entry must not remain enabled after migration. A recoverable backup may exist outside scanned skill locations during migration, but two discoverable entries are a release-blocking failure.

## 10. Error handling and recovery

Ask Park distinguishes five non-success outcomes across module activity, human-gate state, and `control_outcome`:

| Outcome | Meaning | Behavior |
| --- | --- | --- |
| `failed` | Observable module verification failed | Keep current module and activate Diagnose & Recover; represented in module activity rather than `control_outcome` |
| `blocked-external` | Human/platform action is required | Keep current module, stop mutation, and provide the smallest handoff; represented in module/human-gate state |
| `unknown` | Evidence is missing or contradictory | Set `control_outcome=unknown`; keep current module and gather read-only evidence |
| `baseline-conflict` | New work contradicts the accepted issue or receipt | Set `control_outcome=baseline-conflict`; stop and require a superseding contract |
| `needs-human-state-reconciliation` | Authoritative state sources conflict | Set the control outcome, show the conflicting references, and wait for a recorded reconciliation |

Retries must be bounded. External writes, uploads, payment operations, and review actions require a fresh authorization or an existing explicit envelope.

## 11. Behavioral validation

Validation must test routing decisions and forbidden promotions, not wording snapshots.

Minimum scenarios:

1. New idea without an issue routes to Plan.
2. A valid Build receipt plus absent required CloudBase evidence routes to CloudBase, not Experience.
3. Successful Hosting upload with stale live index remains in CloudBase.
4. Experience upload without device evidence routes to Device Acceptance.
5. Server logs showing client calls do not satisfy pixel/fallback acceptance.
6. Mock payment never satisfies Release.
7. A failure in Experience activates Diagnose, records Experience as interrupted, and returns to Experience when recovery changes no prerequisite.
8. A changed acceptance contract produces `baseline-conflict` rather than silent promotion.
9. A secret or identity request stops at `blocked-external` without asking the user to paste it into chat.
10. Every response has exactly one current sequential module and a complete seven-module map.
11. A source SHA mismatch makes Build and every dependent receipt stale and rewinds to Build.
12. An environment-contract mismatch invalidates CloudBase and required downstream receipts without invalidating an unchanged Plan receipt.
13. A package version mismatch prevents Device evidence from attaching to the wrong Experience receipt.
14. `failed` and `blocked-external` preserve the same single `current_module`.
15. A Release incident fixed by a source change keeps Release as the recovery goal but rewinds execution to Build and locks downstream modules.
16. An unresolved diagnosis keeps `diagnose.state=active` with `diagnose.outcome=unresolved`, does not promote state, and records a bounded next hypothesis.
17. Payment out of scope produces an explicit `not-applicable` receipt while review/release gates remain required.
18. Denied or expired human authorization prevents execution and remains in the same module.
19. A causally unchanged frontend-only or backend-only path reuses only receipts whose invalidation rules remain false.
20. Skill discovery exposes `$ask-park` and does not expose an enabled `$wechat-miniprogram-shipping` entry.
21. A released project retains `current_module=release`, marks Release completed, and sets `project_state=released`.
22. Unknown, baseline-conflict, and state-reconciliation outcomes persist in `control_outcome` until their defined clearing evidence appears.
23. A module contract version change invalidates receipts unless an explicit compatible migration is verified.

Fixtures consist of a versioned state record, issue contract, receipt chain, authorized-action record, and minimal raw repository/platform evidence. The observable oracle is the resulting state record: `current_module`, each module's applicability/activity/evidence axes, Diagnose state, invalidated receipt IDs, requested human gate, and emitted next action. Forward evaluation should use independent agents with realistic raw project states and no supplied expected routing answer. No evaluation may mutate a live Mini Program, CloudBase environment, payment system, or platform review state.

## 12. Packaging and rollout boundaries

Ask Park ships as a standalone skill update in the existing public repository, with seven internal modules and one canonical `$ask-park` entry. It is not a multi-skill plugin in V1. The implementation must preserve:

- one discoverable user-facing entry;
- seven visible internal mental anchors;
- no competing start/next/debug/release aliases;
- progressive disclosure;
- deterministic shared status validation where useful;
- repository continuity while migrating and disabling the old installed skill identity.

Recommended rollout order:

1. implement the router, state validator, and shared status/evidence contracts under the new canonical name;
2. migrate Plan and Diagnose first to prove routing, invalidation, and recovery;
3. migrate Build and CloudBase;
4. migrate Experience and Device Acceptance;
5. migrate Release and the human-gate protocol;
6. run end-to-end forward evaluations including single-entry discovery;
7. install and verify `$ask-park`, then disable the old installed skill identity;
8. update public documentation only after observed behavior matches the design.

## 13. Success criteria for the eventual product

Ask Park succeeds when:

- a novice needs to remember only one entry;
- every response reinforces the same seven mental anchors;
- the system identifies the correct current module from evidence;
- no module can promote another module's status by implication;
- failures enter a repair lane and return to the interrupted module;
- context stays bounded to the active module;
- humans retain control of identity, legal, payment, review, and release gates;
- an independent evaluator can verify routing and stop conditions from observable outputs.

## 14. Explicit non-goals

- replacing WeChat Developer Tools or CloudBase consoles;
- automatically obtaining platform identity or secrets;
- turning every Mini Program into the same product architecture;
- requiring payment, SaaS, HTML readers, or Obsidian in V1;
- creating seven user-facing commands;
- claiming formal launch from software, cloud, experience, or device evidence alone.
