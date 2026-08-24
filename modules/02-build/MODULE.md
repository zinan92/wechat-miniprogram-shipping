# Build module

Mental anchor: prove the product behavior locally before depending on platform
identity.

Build consumes an accepted Plan issue contract and produces a reproducible,
mock-first software candidate. It does not deploy, upload an experience
version, enable real payment, or claim device evidence.

## Input

- accepted immutable issue contract and Plan receipt;
- applicability map and the selected Build story;
- reproducible source repository and named source SHA;
- known capability, content, authorization, and service-boundary constraints.

Build stops when the issue contract is missing, acceptance changed, source is
not reproducible, or a required human/platform authority is unavailable.

## Output

Produce a software candidate and receipt conforming to
[software-receipt.md](software-receipt.md):

- mock-first vertical slice behind one page-facing service boundary;
- parity inventory for mock and cloud adapters;
- fail-closed authorization and stable domain error codes;
- ordered content blocks and a capability-derived contract version;
- controlled first-party assets rather than unreviewed remote images;
- scoped tests, audit, secret scan, and diff check;
- named source SHA, issue contract ID, limitations, and unverified platform
  assumptions.

The receipt claims `verified-software` only. It never claims CloudBase,
Experience, Device Acceptance, payment, review, or Release evidence.

## Success predicate

Build exits when the agreed slice is reproducible from the named SHA, mock and
cloud page-facing APIs have parity, unknown authorization denies, ordered
content and capability versioning pass, first-party asset rules pass, scoped
software/security/diff gates pass, and every unverified platform assumption is
listed. The source remains clean and committed.

## Failure outcomes and routing

- missing issue or changed acceptance → return to Plan and
  `baseline-conflict`;
- source cannot be reproduced → Diagnose with Build interrupted;
- tests, service contract, authorization, asset, audit, secret, or diff gate
  fails → Diagnose with a bounded Build hypothesis;
- credential or platform action is required → `blocked-external` and prepare a
  human gate without collecting the credential;
- CloudBase, Simulator, upload, or device behavior is needed → hand off to the
  later module; do not weaken the Build exit claim.

## Evidence

Record source SHA, issue contract ID/version, clean diff, scoped test output,
audit and secret-scan result, diff-check result, service-boundary parity,
authorization behavior, content capability/version, first-party asset aliases,
receipt ID, and explicit limitations. Use aliases, digests, and redacted
references only.

## Forbidden boundary

- Do not deploy functions or assets, upload an experience version, or call a
  real payment/review/release system.
- Do not collect AppID, environment IDs, credentials, or private targets.
- Do not make protected content directly client-readable.
- Do not treat Simulator, logs, source inspection, or HTTP reachability as
  Device Acceptance evidence.
- Do not broaden the accepted issue, silently add features, or use a remote
  image URL as a durable first-party asset.

## Procedure

1. Verify the accepted issue and named source SHA before editing.
2. Build the smallest useful mock-first vertical slice.
3. Define one page-facing service API and make mock/cloud adapters implement the
   same methods, result shapes, and stable error codes.
4. Design authorization/state transitions first; unknown and expired states
   deny by default.
5. Model interleaved text/images as ordered blocks and derive a content
   contract version from parsed capabilities, not file extensions.
6. Snapshot approved external assets into controlled first-party aliases and
   record their digests.
7. Run scoped tests, audit, secret, and diff gates; record assumptions and what
   the candidate cannot prove.
8. Commit the candidate and hand its software receipt to Ask Park. Ask Park,
   not Build, promotes CloudBase or invalidates dependent receipts.
