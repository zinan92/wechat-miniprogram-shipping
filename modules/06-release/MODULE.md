# Release module

Mental anchor: separate payment, platform review, and formal release into
explicit final gates.

Release is the terminal module. It only produces `project_state: released`
after every applicable predecessor, human authorization, review/read-back,
release read-back, and smoke result pass. It never performs real payment,
legal, review, or release actions in skill tests.

## Input

- valid Build, CloudBase, Experience, and Device receipts;
- approved release scope and payment applicability decision;
- provider/server payment truth when payment is in scope;
- prepared platform review materials and explicit human authorizations;
- exact version/package identity and release smoke scope.

## Output

Produce a Release record conforming to
[release-receipt.md](release-receipt.md):

- payment applicability and provider/server truth kept distinct;
- human authorization for payment, legal, review, and formal release actions;
- review submission/read-back and released-version read-back;
- source/Experience/Device version causality;
- post-release smoke result and final generic receipt;
- `released`, `failed`, or `blocked-external` terminal outcome.

## Success predicate

Release exits with `project_state: released` only when every applicable final
gate has a read-back result, released version matches accepted predecessor
receipts, all required human actions are authorized, smoke checks pass, and the
final receipt is valid. Payment `not-applicable` is explicit and does not skip
Review or Release.

## Failure outcomes and routing

- payment mismatch or missing provider truth → Diagnose/blocked external;
- legal/payment/review/release human action → `awaiting-human` or
  `blocked-external`, never authority inferred from login/access;
- review rejection, version mismatch, or smoke failure → Diagnose with Release
  interrupted; keep project active;
- source/package/device identity change → Ask Park invalidates from the earliest
  changed prerequisite;
- client callback or review approval alone → never terminal Release.

## Evidence

Record distinct payment truth or N/A reason, review read-back, released-version
read-back, human authorization references, predecessor receipt IDs, smoke
result, final receipt, timestamps, and unproven claims. Keep payment keys,
legal documents, account identities, and private targets outside the record.

## Forbidden boundary

- Do not grant membership from a client payment callback.
- Do not submit legal/payment/review/release actions without human approval.
- Do not equate review approval, upload, or a smoke result with formal release
  until release read-back passes.
- Do not perform real provider/payment/review/release actions in skill tests.
- Do not change accepted predecessor identity or silently retry ambiguous writes.

## Procedure

1. Verify the complete predecessor receipt chain and exact version binding.
2. Decide payment applicability; when required, read provider/server truth for
   owner, amount, payer, transaction, and event identity.
3. Prepare review materials and use a named human gate for submission; read back
   review state separately.
4. Use a separate human gate for formal release and read back released version.
5. Run bounded post-release smoke checks against the released version.
6. Publish the final Release receipt only after all gates pass; Ask Park alone
   sets the terminal project state.
