# Experience module

Mental anchor: prove a named source version became a traceable WeChat
experience package.

Experience binds Build, CloudBase, DevTools, upload, and target read-back. It
does not equate upload with review or Release, and it does not perform actual
upload or QR interaction in skill tests.

## Input

- accepted issue and valid Build/CloudBase receipts;
- named source SHA and reproducible clean tree;
- formal project identity and redacted AppID/environment references;
- release scope, version/note aliases, tool/base-library versions, and backend
  environment contract;
- prepared human gates for account/QR/upload actions when required.

## Output

Produce an Experience record conforming to
[upload-receipt.md](upload-receipt.md):

- mock/configured release gates and exact DevTools project/compile/upload path;
- clean-tree and ignored-local-config restoration result;
- operator-state preservation before DevTools/upload checks and restoration
  result after the check;
- Compile, Simulator, Upload, target read-back, review, and Release as separate
  evidence layers;
- version/note/time/source SHA/tool/base-library/environment contract bindings;
- `verified-experience`, `failed`, `blocked-external`, or approved backend-only
  `not-applicable` with impact evidence.

## Success predicate

Experience exits with `verified-experience` only when DevTools compiled the
named tree, upload read-back shows the intended version/target, the receipt
binds source/package/environment/tool identity, ignored local config is
restored, and the release source is clean. Review and formal Release remain
separate claims.

## Failure outcomes and routing

- compile/upload/cache/package drift → Diagnose with Experience interrupted;
- AppID/environment/account/QR identity action → `blocked-external` and a named
  human gate;
- uncommitted source or changed Build/CloudBase identity → invalidate from the
  earliest changed prerequisite and return to Build/CloudBase;
- unsaved operator content cannot be preserved/restored → stop the check,
  record a bounded human decision, and do not upload;
- backend-only change with unchanged client contract → explicit
  `not-applicable` only with impact analysis;
- review or formal Release is not proven by Upload and remains a later gate.

## Evidence

Record source/package SHA or digest, project identity aliases, version/note/time,
DevTools/tool/base-library versions, environment contract alias, compile and
upload evidence, target read-back, clean-tree/config/operator-state restoration,
predecessor receipt IDs, limitations, and unproven review/release/device
claims. Use only redacted identity references.

## Forbidden boundary

- Do not persist AppID/AppSecret, environment IDs, QR contents, or account
  identity values.
- Do not upload from an uncommitted tree or leave ignored local configuration
  in the release source.
- Do not claim Upload proves review, Release, payment, or Device Acceptance.
- Do not perform actual upload, QR interaction, or platform mutation in skill
  tests.
- Do not silently reuse stale package/target evidence or broaden the accepted
  issue.

## Procedure

1. Verify Build/CloudBase predecessor receipts, source SHA, clean tree, and
   redacted project/environment identity.
2. Preserve unsaved operator state before opening/compiling/uploading and
   record the restoration evidence; stop if preservation is unavailable.
3. Run the credential-free mock gate, then the configured gate only when the
   human/platform boundary is explicitly prepared.
4. Open the exact project in DevTools, compile the named source, and record tool,
   base-library, route, and package identity.
5. Upload only through the approved human gate; record version/note/time and
   read back the target package.
6. Restore ignored local configuration and prove the release source is clean.
7. Keep Compile, Simulator, Upload, target, review, and Release evidence in
   separate fields; hand the Experience receipt to Ask Park for Device next.
