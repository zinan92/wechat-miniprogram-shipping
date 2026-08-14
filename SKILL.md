---
name: wechat-miniprogram-shipping
description: Plan, build, validate, deploy, and release native WeChat Mini Programs with an explicit frontend, WeChat platform, CloudBase backend, device, payment, and review boundary. Use when starting, taking over, debugging, or shipping a WeChat Mini Program that uses CloudBase or another serverless backend, especially when the request involves AppID, DevTools, experience versions, real-device acceptance, or launch readiness.
---

# WeChat Mini Program Shipping

## Overview

Treat a Mini Program as two connected release pipelines, not one deployment: the local `miniprogram/` frontend is compiled and uploaded through WeChat Developer Tools, while `cloudfunctions/`, databases, storage, and permissions are deployed to CloudBase. Keep software verification, target-environment proof, real-device acceptance, payment, and platform review as separate claims.

Read [references/project-lessons.md](references/project-lessons.md) when a project has already encountered platform, upload, permission, UI, or release failures.

## 1. Establish the contract before coding

1. Write the user outcome in one sentence and identify the first useful moment.
2. Define V1 and explicitly defer future capabilities such as live streaming, courses, desktop publishing, or complex rich text.
3. Make one issue/contract per independently verifiable milestone. Include Outcome, 3–7 acceptance criteria, In/Out scope, and forbidden changes.
4. Make a risk map before implementation: AppID/主体, CloudBase environment, account association, admin identity, storage rules, payment, device coverage, review, and data migration.
5. Inspect existing repositories, official platform capabilities, and reusable components before inventing infrastructure.

Do not call the project “launched” because the code compiles or tests pass. Use explicit status labels such as `verified-software`, `verified-cloud`, `verified-experience`, `verified-device`, `verified-payment`, `verified-review`, and `blocked-external`.

## 2. Keep the five layers separate

Explain this map to the project owner before operating tools:

| Layer | Source of truth | Release action |
| --- | --- | --- |
| Local project | WXML/WXSS/JS, tests, cloud functions, docs | edit, test, commit |
| Git remote | reproducible source and history | push a named commit |
| DevTools Simulator | compiled local frontend | Compile, inspect, clear cache if needed |
| WeChat platform | experience/review/released Mini Program package | DevTools Upload, then review/release |
| CloudBase | functions, database, storage, rules, environment | deploy functions/assets/rules and smoke-test |

For a frontend layout change, use `local → DevTools Compile → Simulator → DevTools Upload → WeChat experience`. Do not upload frontend source “to CloudBase”. For a backend change, use `cloudfunctions → CloudBase deploy → health check`; update the frontend package too if its contract changed.

## 3. Build a mock-first vertical slice

1. Create a service boundary so mock and cloud modes expose the same page-facing API.
2. Make the first slice useful without credentials: browse content, see locked content, and exercise the main author/member flow with deterministic seed data.
3. Keep production data inaccessible to direct client reads. Route member content, admin writes, images, and moderation through server-side authorization.
4. Model ordered content as ordered blocks when text and images can be interleaved. Do not store separate arrays and guess their order at render time.
5. Put bounds on text, blocks, image count, image bytes, query pages, and retry attempts. Reject with a specific user-facing reason; never silently truncate.

## 4. Design security and state machines before adapters

### Identity and authorization

- Keep AppID, CloudBase env ID, OpenID, admin role, payment credentials, and platform account association as separate fields and gates.
- Store secrets only in ignored local configuration or platform secret settings. Never commit `.env.local`, runtime overrides, AppSecret, payment keys, or private certificates.
- Fail closed: admin means `role === 'admin' && status === 'active'`; membership means active status plus a future expiry. Unknown, missing, suspended, or expired state denies access.
- Do not trust client-supplied author, owner, amount, role, payment success, or document ID.
- Keep database and storage client access closed. Serve protected images through server-authorized short-lived URLs.

### Orders and payments

- Write the order state machine and retry/timeout behavior before calling a payment provider.
- Use deterministic idempotency identity, atomic claim/CAS or transactions, an initialization lease, and a durable pending timestamp.
- A client payment callback never grants membership by itself. Verify order owner, amount, provider, payer, transaction, and event identity on the server.
- Reconcile missed client results from provider truth; close unpaid orders only after the provider confirms closure. Keep real payment disabled until a separate approved gate.

## 5. Deploy CloudBase deliberately

Before deploying, verify collections, indexes, seed data, cloud-function permissions, storage rules, runtime version, and environment variables. A function upload is not a healthy deployment until a dependency-safe smoke check returns the expected health response.

If dependencies include local `file:` packages or security patches, do not assume CloudBase online dependency installation is equivalent to local installation. Build a temporary production package, upload it, and retry with the same package using the provider's alternate upload path when appropriate.

Treat free-tier limits as design inputs. If a tier rejects custom storage rules, keep the stricter server-only setting; never make protected content public just to make an image load.

## 6. Use DevTools and evidence correctly

1. Run the mock release gate before opening DevTools: tests, page/WXML/WXSS validation, package size, dependency audits, secret scan, and diff check.
2. Open the exact local project directory. Compile before uploading. Clear cache/reopen the project when the simulator shows stale code.
3. Separate tool noise (`wx.operateWXData`, visitor-mode async security warnings, compiler warnings) from business failures.
4. When automating screenshots, enable the Developer Tools server port first. Re-read accessibility state after every UI action; do not reuse stale element indexes.
5. Record screenshot date, code SHA, tool/base-library version, device profile, route, and what the screenshot cannot prove. The Simulator cannot prove real payment, real keyboard behavior, platform capsule spacing, or review readiness.
6. Test shared components and layout invariants, not page-specific magic offsets. For visual tests, deliberately mutate a known-good invariant and require the test to fail.

For native component WXSS, inspect platform-injected styles and component selector restrictions before tuning numbers. Use shared class-based wrappers, keep correct flex/grid geometry, and generate icon assets from the generator rather than hand-editing PNGs.

## 7. Prepare and upload an experience version

Use two explicit gates:

- `release:check` for the credential-free mock baseline.
- `release:check:cloud` for the formal AppID, `cloud` mode, and non-empty CloudBase environment prepared for upload.

Apply formal values only in ignored local configuration, run the cloud gate, deploy/check CloudBase, compile the exact local tree, and upload through DevTools with an explicit version and note. After upload, run the restore command and verify a clean worktree. Never claim that a successful upload is a formal release.

Keep a receipt containing version, timestamp, commit SHA, cloud environment (redacted), health result, and experience QR/target. Update the registry only after reading back the actual result.

## 8. Acceptance and stop conditions

Before calling the MVP ready for users, run the matrix for:

- administrator and ordinary member accounts;
- public and protected text plus protected images;
- publish, unpublish, delete, moderation, search, history, favorites, questions, comments;
- iOS and Android real devices;
- weak network/retry and rebuilt-page payment attempts;
- experience version behavior.

Stop and name the blocker when any of these is true: formal AppID/env ID is missing or mismatched; identity/association is unclear; database/storage rules are not verified; health check fails; protected content is directly readable; admin upload is not server-checked; evidence is stale; real payment or review is being inferred from mock/simulator behavior; or the worktree cannot be reproduced from a committed SHA.

## 9. Claims and handoff format

Report only:

1. conclusion and current status;
2. decision needed from the owner;
3. link/path to the contract, receipt, screenshot, issue, or commit.

For an external handoff, provide commands and expected outputs, but never ask the recipient to paste secrets into chat. Human-only steps include QR scans, account/identity confirmation, legal terms, payment credentials, and platform review decisions.

See [references/project-lessons.md](references/project-lessons.md) for recurring failure modes and the distinction between transferable rules and environment-specific facts.
