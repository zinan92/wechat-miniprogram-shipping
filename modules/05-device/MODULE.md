# Device Acceptance module

Mental anchor: prove real people, roles, devices, and failure conditions can
use the accepted Experience build.

Device Acceptance is a bounded evidence handoff. Skill tests do not automate a
physical device; they validate the matrix and human gate contract that a real
operator must execute.

## Input

- valid Experience receipt and exact experience version alias;
- agreed device/role/task matrix;
- prepared human actions for QR, account, device, or physical observation;
- protected/public content expectations and weak-network/retry scope;
- client logs with request IDs and source attribution.

## Output

Produce a device record conforming to
[device-matrix.md](device-matrix.md):

- iOS/Android device, role, task, and version-bound matrix cells;
- separate evidence ladder for projection, HTTP reachability, pixels/layout,
  and expiry/fallback;
- protected text/image checks and weak-network/retry/expiry results;
- client-log attribution that excludes CLI/server-only events;
- smallest human gate when physical-device/account evidence is missing;
- `verified-device`, `failed`, `blocked-external`, or approved
  `not-applicable`.

## Success predicate

Device exits with `verified-device` only when every required matrix cell has a
fresh result bound to the Experience version, protected-content and failure
paths hold, and the evidence ladder states exactly what each rung proves. A
Simulator, HTTP 200, projection, log, or one device never proves all rungs.

## Failure outcomes and routing

- observable device/pixels/layout/protected-content failure → Diagnose with
  Device interrupted;
- missing QR/account/operator/physical action → `blocked-external` with the
  smallest named human gate, not “test everything”;
- experience version mismatch → invalidate Experience and Device evidence;
- HTTP/projection passes but pixels/layout or expiry fails → retain the lower
  rung result and route the actual defect;
- approved unchanged client behavior → explicit `not-applicable` only with
  impact analysis.

## Evidence

Record experience version, device profile/OS, account role, route/task, matrix
result, fresh timestamps, relevant redacted client-log attribution, protected
content result, network/retry/expiry result, screenshots/observations, and
limitations. State what projection, HTTP, pixels/layout, and expiry evidence do
not prove.

## Forbidden boundary

- Do not automate or mutate a physical device in skill tests.
- Do not infer pixels/layout from server logs, CLI calls, or HTTP reachability.
- Do not treat one device/account as full coverage.
- Do not persist QR contents, account identities, OpenID, credentials, or
  private customer data.
- Do not call a missing human observation `verified-device` or silently skip a
  matrix cell.

## Procedure

1. Bind the matrix to the exact Experience version and approved role/task
   scope.
2. Run applicable projection and HTTP checks while recording their limits.
3. Have the operator observe pixels/layout on the smallest required device and
   record protected text/image behavior.
4. Exercise weak network, retry, expiry, and fallback paths without duplicate
   destructive writes.
5. Attribute client logs by request ID and exclude CLI/server-only events.
6. If a physical gate remains after automation passes, prepare one named human
   gate and keep Device current/blocked.
7. Hand the matrix receipt to Ask Park. It alone promotes Release or rewinds
   Experience when the bound package changes.
