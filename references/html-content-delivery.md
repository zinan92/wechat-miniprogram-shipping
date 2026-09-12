# HTML content delivery know-how

Read this reference when a Mini Program task involves imported HTML, native
`rich-text`, `web-view`, JavaScript/canvas charts, business-domain validation,
signed reader artifacts, or read state that depends on successful rendering.
These are branching rules learned from real delivery failures. Re-check
SDK-specific behavior when the SDK or platform changes.

## Outcome

Choose the smallest renderer that satisfies the accepted content contract,
then prove the complete path from a frozen source bundle to the exact
experience version and physical-device observation. Keep source conversion,
cloud access, simulator rendering, and device acceptance as separate receipts.

## Choose the renderer before building the transport

The `.html` extension does not decide the renderer. Freeze one representative
sample and inspect both its source and rendered behavior.

| Accepted behavior | Preferred path |
| --- | --- |
| Static text, images, inline emphasis, callouts and tables | Native `rich-text` |
| Mostly static article with canvas/SVG charts | Native text plus selective chart rasterization |
| Browser-only layout or required JavaScript interaction | `web-view`, with domain and navigation gates |
| Arbitrary website/app execution | New scope decision; never silently treat it as article import |

A page can create canvas nodes only after JavaScript runs, so source grep alone
cannot establish whether the article is static. Compare the rendered DOM and
the accepted user outcome. One successful sample establishes support for that
sample class, not a universal CSS/HTML preservation percentage.

Prefer native rendering when it meets the outcome. It preserves selectable
text and removes an unnecessary website-domain dependency. Use whole-document
rasterization only when the accepted outcome is genuinely a fixed image; it
does not preserve responsive layout, interaction, selection or accessibility.

## Prove the whole content path

Treat the delivery as one causal chain:

```text
frozen source bundle
  → resource normalization
  → preview/draft/version
  → publish read-back
  → entitlement/access decision
  → renderer load
  → read-state acknowledgement
  → physical-device observation
```

Each arrow needs evidence from the real preceding output. A manually created
ticket, a raw storage URL, a function health check, or a simulator screenshot
can test one layer but cannot replace the production call path for a real
published article.

## Import and staticization

- Freeze the representative HTML and allowed resources with content digests;
  a changing remote URL is not an acceptance fixture.
- Resolve relative resources by normalized source path, not basename. Surface
  missing files and same-name collisions instead of guessing.
- Bound remote acquisition by size, timeout, redirects, destination class and
  MIME. The import renderer receives no admin cookies, parent-page storage,
  arbitrary network access or business write authority.
- Run only the known dependencies needed by the accepted sample in an isolated
  renderer. Wait for fonts, data and chart initialization before capture.
- For canvas charts, account for every expected chart, non-zero dimensions,
  axes/legend and all canvas layers. An emitted PNG is not proof that the chart
  is complete. Capture at sufficient pixel density for the target viewport.
- Final article HTML does not retain importer scripts, event handlers, forms,
  unknown iframes or unsafe URLs. Conversion-time JavaScript and reader-time
  behavior are separate trust boundaries.
- Keep images within the body width and make wide tables scroll locally. Do
  not widen the whole page or shrink all text to fit one table.
- Retry and update paths are idempotent: preserve the article identity and
  current published version until the new draft is explicitly published.

## Native rich-text layout

Server-side validation/sanitization remains authoritative. A client-side HTML
splitter is a layout adapter, not a sanitizer.

When native layout separates a wide table into its own `scroll-view`:

- close and reopen enclosing tags around the table so adjacent body blocks
  retain their inherited styles;
- keep nested tables together;
- retain image-only blocks;
- preserve malformed or unsupported source for an explicit fallback instead
  of silently deleting content;
- size the table from observed columns with a bounded minimum/maximum, then
  verify real horizontal movement rather than only checking CSS declarations.

Native `rich-text` supports a subset of browser HTML/CSS. State the preserved
content class and limitations. Rasterize only unsupported visual blocks while
keeping ordinary body text native.

## WebView, domains and CloudBase

### Navigation evidence is not API evidence

CloudBase default domains can insert an access-reminder intermediate page for
browser navigation while an ordinary HTTP/API request appears healthy. A
`200` from `curl`, a function, or a signed resource therefore does not prove
that Mini Program `web-view` reached the article.

When WebView is required:

- verify the Mini Program subject and business-domain eligibility;
- inspect the actual navigation using `bindload`/`binderror`, resolved `src`,
  the visible page and the exact experience version;
- treat a required ICP/custom-domain/business-domain action as a named human
  gate rather than a software failure;
- keep a default-domain warning/interstitial as an Experience blocker until
  the accepted custom-domain path is observed.

CloudBase documents that Mini Program WebView requires an enterprise subject
and configured business domain, and that it covers the page's other native
components. Its default-domain documentation also distinguishes browser
navigation from ordinary requests and recommends a filed custom domain for
production navigation:

- <https://docs.cloudbase.net/lowcode/components/wedaUI/src/docs/compsdocs/super/WebView>
- <https://docs.cloudbase.net/service/alias>
- <https://docs.cloudbase.net/service/custom-domain>
- <https://cloud.tencent.com/document/product/1301/100434>

### Verification files must reach the exact public route

For a platform-provided domain verification file:

1. Keep the provided filename and bytes unchanged.
2. Resolve the exact hostname and root path validated by the platform. Static
   Hosting, storage and HTTP-gateway/app domains can be different routes.
3. Read back the exact URL. Require the expected content type and byte digest,
   not merely HTTP `200`; an SPA fallback can return `index.html` successfully.
4. Confirm whether gateway path transmission preserves the filename and allow
   for bounded propagation delay before retrying.
5. Keep the verified file available while the domain remains configured.

### Cloud data and storage sentinels

- For the CloudBase SDK behavior observed in this workflow,
  `collection(...).doc(id).set(data)` carries identity in `doc(id)`; including
  the reserved `_id` in `data` failed before the write. Keep a regression test
  and re-check this sentinel when upgrading the SDK.
- The hostname in a real signed storage URL can differ from the hostname used
  during manual tests. Build a narrow allowlist from the observed same-bucket
  hostname, preserve existing configuration fields, deploy, then read the
  effective configuration back.
- Reader tickets bind the smallest useful scope: instance/project alias,
  article identity, version, audience/entitlement and expiry. A one-time ticket
  proves replay resistance only when first use succeeds and reuse is rejected.
  Store ticket/token values only in approved secret-bearing systems, not in
  public receipts, screenshots or logs.

## Template, upload and read-state sentinels

- WXML `wx:if` / `wx:elif` / `wx:else` branches must remain adjacent. A helper
  node inserted between them can turn a small UI edit into a compile failure.
  Run a real DevTools compile after template changes.
- A tool-specific upload checkout can carry AppID/environment overlays that the
  canonical source checkout does not. Compare the scoped source/package files,
  preserve the overlay, and bind the final compile to both identities.
- An experience package uploaded before the final fix remains stale. Increment
  the version, upload the repaired package, and read back that new version;
  simulator success after the upload does not repair the old package.
- Mark content read only after the chosen renderer visibly succeeds and the
  server confirms the read fact. Locked previews, error pages, failed WebViews
  and failed read sync do not create a local authoritative read state. Offer a
  bounded retry when server acknowledgement fails.

## Acceptance ladder

| Layer | Minimum evidence | Still unproven |
| --- | --- | --- |
| Software | Frozen sample, parser/converter tests, resource and entitlement negatives | Cloud deployment and pixels |
| Cloud | Real published item through the authenticated production entry, artifact/config read-back | Mini Program navigation |
| Experience | Final DevTools compile, uploaded version read-back, simulator render/scroll/read acknowledgement | Physical-device behavior |
| Device | Exact version on required iPhone/Android roles, layout, scroll, access and read-state observations | Review and formal release |

If the server path passes but the user still sees a failure, keep the affected
Experience or Device module current. Inspect the navigation/rendering layer;
do not close the incident with “reopen the article” until the user's failing
path is re-observed.

## Persistable evidence

Use redacted aliases and digests for renderer mode, source bundle, resource and
chart counts, table scroll dimensions, source/package identity, experience
version, route/domain identity, content type/byte digest, load/error event,
read acknowledgement and device profile. Keep AppIDs, environment IDs, raw
URLs, local paths, account identities, tokens, secrets and cookies outside the
public skill record.

## Failure patterns to recognize

- Testing a manually generated ticket instead of the authenticated production
  entry hides repository, entitlement and storage-host failures.
- Treating `200` as rendered success hides interstitials, downloads and SPA
  fallbacks.
- Choosing WebView because the input is HTML adds domain and navigation gates
  before proving they are necessary.
- Silently stripping scripts/canvas can publish incomplete content; executing
  arbitrary imported scripts creates a larger security boundary. Staticize the
  accepted visual blocks in isolation.
- Uploading before the final compile creates a stale experience version even
  when the source tree is later fixed.
- Writing local “read” state before visible render and server acknowledgement
  creates false engagement evidence.
