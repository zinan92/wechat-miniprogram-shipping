# CloudBase/backend module

Mental anchor: prove the backend is deployed, private, healthy, and running
the intended artifact.

This module is provider-neutral. CloudBase is the default role, but another
serverless backend may satisfy the same contract through an adapter. The
module records guidance and read-back evidence; it does not contain provider
credentials or perform a live deployment in skill tests.

## Input

- accepted issue contract and Plan/Build receipts;
- approved backend applicability and provider role;
- target alias and environment contract alias;
- deployment package identity and scope;
- any causally reusable backend receipt.

If the approved design has no backend, use the explicit not-applicable path with
architecture evidence and impact analysis. Never infer that path from a failed
deployment.

## Output

Produce a CloudBase/backend record conforming to
[cloud-receipt.md](cloud-receipt.md):

- collections, indexes, seed data, rules, runtime, and config readiness;
- clean production package without nested development dependencies;
- separate function upload, health, projection, Hosting, and client evidence;
- closed protected storage and authorized short-lived asset references;
- target/provider/artifact identity, redacted receipt, and reuse conditions;
- `verified-cloud`, `failed`, `blocked-external`, or explicit `not-applicable`.

## Success predicate

CloudBase exits with `verified-cloud` only when the deployed artifact and target
bindings match the receipt, readiness checks pass, permissions/protected
storage fail closed, required health and read-only projection checks pass, and
Hosting read-back matches the intended build when Hosting is applicable.

## Failure outcomes and routing

- packaging/runtime/config/health/projection drift → Diagnose with CloudBase
  interrupted;
- target identity mismatch or human authorization needed → `blocked-external`;
- protected storage would require public access → fail closed with no unsafe
  fallback;
- Hosting bundle or deep-link drift → Diagnose; do not treat function health as
  Hosting/client evidence;
- provider role absent by an approved architecture decision → explicit
  `not-applicable` with impact analysis;
- source, package, or backend contract identity changed → Ask Park invalidates
  causally affected receipts and rewinds to the earliest prerequisite.

## Evidence

Record provider/target aliases, artifact and production-package digests,
readiness checks, function upload, health, projection, Hosting, and client
evidence separately, plus storage/rules result, timestamps, limitations, and
predecessor receipt IDs. Use only redacted target references; short-lived URLs
are observations, not durable targets.

## Forbidden boundary

- Do not store provider credentials, AppID/AppSecret, environment IDs, or
  complete private URLs.
- Do not make protected storage public to make an asset load.
- Do not count a CLI health command as Mini Program client evidence.
- Do not conflate function upload, health, projection, Hosting, or client
  behavior into one “deployed” claim.
- Do not deploy a real provider or mutate production from module fixtures.

## Procedure

1. Verify the accepted issue, Build receipt, provider role, target alias, and
   package identity.
2. Check collections/indexes/seed/rules/runtime/config before deployment
   guidance; stop on missing or contradictory readiness.
3. Assemble a clean production package with no nested development dependency.
4. Record function upload separately from health and read-only projection
   read-back.
5. Verify protected storage remains closed and short-lived authorized assets are
   represented by aliases/redacted references.
6. Verify Hosting identity/build/deep-links separately when applicable; record
   client evidence only when the client surface was actually observed.
7. Hand the CloudBase receipt to Ask Park. It may be reused only while causal
   source, package, target, permissions, and environment bindings are unchanged.
