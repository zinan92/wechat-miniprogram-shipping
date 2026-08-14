# Project lessons and anti-patterns

This reference distills one completed member-content Mini Program. Use it to recognize failure patterns; re-check provider limits and current tool behavior instead of copying every numeric value.

## Failure patterns to recognize

| Symptom | Likely cause | Durable response |
| --- | --- | --- |
| “The code is done but cannot upload” | Tourist AppID, missing formal AppID, wrong account association, or missing environment | Separate identity/platform gates from software gates |
| Frontend change “deployed to CloudBase” but users see no change | DevTools upload and CloudBase deployment were conflated | Compile locally and upload the frontend to WeChat; deploy CloudBase only for backend/resources |
| Member image loads after making storage public | FileID was mistaken for authorization | Keep storage server-only and issue temporary URLs after content authorization |
| Function appears deployed but health call fails | Runtime dependency installation or package layout is wrong | Build the exact production package and run a dependency/startup health check |
| iPhone upload fails or loops on “try again” | Format/size/payload/retry/permission failures collapsed into one path | Validate signature and byte budget, compress/chunk, bound retries, clean staging, map errors |
| Image appears only at the beginning/end of an article | Text and images stored separately without order | Use one ordered block stream and explicit insertion controls |
| Unknown account status grants admin/member access | Authorization checks only positive role/status or only one field | Require explicit active status plus effective expiry; deny unknown states |
| Duplicate orders or paid order overwritten by failure | Check-then-write and provider call are not atomic | Deterministic order ID, atomic claim, lease, CAS, durable pending timestamp |
| Rebuilt renewal page creates a new payment attempt | Idempotency key exists only in page memory | Restore the unresolved order/key from durable state |
| UI test is green but screenshot is wrong | Test checks class/string presence instead of a layout invariant | Add structural assertions and a mutation test that must turn red |
| Fix works on one page and breaks another | Page-local offset compensates for a shared component/platform rule | Fix shared wrapper/component or icon generator |
| Simulator screenshot looks current but code changed later | Evidence predates the code, or native/GPU capture is stale | Record SHA/time/device and downgrade stale evidence to historical |
| Release gate passes before formal configuration but cannot run after it | Mock and configured targets use conflicting validation assumptions | Maintain separate mock/cloud gates and restore local baseline after upload |
| Registry says 48 tests while output says 79/112 | Documentation is not tied to the final gate output | Update registry/receipt only after the final run and actual upload read-back |

## Do not generalize these project-specific facts

- A free CloudBase tier may reject custom storage rules; verify the current plan.
- A particular Developer Tools/base-library version may reject syntax or inject CSS that another version does not.
- Image byte limits, block counts, query limits, COS timeouts, and package-size budgets are contracts to measure, not universal constants.
- A mock provider proves a state machine, not real payment authorization, settlement, refund, or platform review.

## Minimum reusable evidence packet

- milestone issue and acceptance criteria;
- commit SHA and clean worktree;
- mock release-gate output;
- configured/cloud gate output when applicable;
- CloudBase function names, redacted environment suffix, and health response;
- experience version, upload timestamp, and QR/target;
- iOS and Android device matrix with route-level results;
- explicit list of blocked external gates.
