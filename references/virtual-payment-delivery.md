# Virtual payment delivery know-how

Read this reference when a Mini Program sells virtual goods — membership,
subscription, unlocked content, coins or paid features — or when a task
involves `wx.requestVirtualPayment`, virtual-payment items (道具) or coins
(代币), the sandbox/production switch, Apple IAP on iOS, order
reconciliation, or a review rejection about payment or empty member pages.
These are branching rules learned from a real delivery. Re-check platform
behavior when WeChat, Apple or the SDK changes.

## Outcome

A reader on each required terminal can buy the accepted plan through the
platform's virtual-payment channel, the server grants the entitlement from its
own order query, and the exact submitted version shows a working purchase to
the reviewer. Keep configuration, signing, client launch, server fulfilment,
device purchase and review as separate receipts.

## Channel: virtual goods must use virtual payment

Membership and other knowledge/content goods are virtual goods. They must be
sold through Mini Program virtual payment, not ordinary WeChat Pay
(`wx.requestPayment` / cloud pay). An existing ordinary-payment integration is
not reusable for membership; plan a separate provider.

A coin (代币) layer does not change the category of what is sold. Reviewers
judge the goods the reader receives, and coins may only be spent inside the
same Mini Program. Relabeling goods to fit a different service category is a
misrepresentation risk for the whole Mini Program, not a workaround.

## Terminal routing decides the rehearsal plan

`wx.requestVirtualPayment` is one client call; the platform routes it by
device:

| Terminal | Payment system | Sandbox |
| --- | --- | --- |
| Android, HarmonyOS, Windows | WeChat Pay | Available |
| iPhone, iPad | Apple IAP | **Not available — production only** |

Consequences:

- An iOS-only team cannot rehearse. On iOS the sandbox environment fails
  (observed as `-15001`), so the first iOS purchase is real money. Name device
  roles before choosing the environment: rehearse on Android in sandbox, then
  do one approved real purchase on iOS.
- iOS buyers need iOS 15+, a WeChat client at or above the platform's stated
  minimum, a mainland-China App Store account and a price of at least 1 CNY.
  An overseas App Store account on the tester's phone is an environment
  blocker, not a code failure.
- The iOS buyer pays Apple through the Apple ID's payment method. Apple takes
  its commission and settles monthly (documented as 45–60 days after month
  end); WeChat Pay orders settle T+3. Acceptance never waits for funds to
  arrive; it reads the order state.

## Enablement is a ladder of separate human gates

Each gate is a platform/merchant action with its own evidence. Several fail
with the same generic client code, so check them in order:

1. Virtual payment opened for an eligible (verified enterprise/individual
   business) subject; record the offer ID (not a secret).
2. Items published with the exact product IDs and prices the server signs.
   Publication propagates for about 10 minutes (`-15014`).
3. Mini Program short name (简称) configured — required for Apple's display
   name. It is set in the Mini Program's basic settings, not in the virtual
   payment console; it may need review.
4. **Apple IAP enabled** in virtual payment basic configuration — a separate
   toggle. Without it iOS fails with `-15001` and errMsg
   “当前商户尚未开启 iOS 支付”.
5. AppSecret and the AppKey for the chosen environment entered into the
   function environment by the owner. The sandbox and production AppKeys
   differ and must match `env`.

Do not enable the “platform path” (平台路径) toggle unless the product has the
recommendation/subscription pages it describes; it is unrelated to purchase.

## Signing and secrets

- `signData` is the exact JSON string passed to the client; `paySig` is
  `HMAC-SHA256(appKey, "requestVirtualPayment&" + signData)`; `signature` is
  `HMAC-SHA256(session_key, signData)` with a fresh `session_key` from a new
  login code per request.
- Server API calls sign `uri + "&" + postBody` with the same environment's
  AppKey. Verify the algorithm once against the platform's published fixed
  vector before debugging live failures.
- Secrets live only in the function environment. Store no signature, session
  key or AppKey in order documents, logs, receipts or screenshots. When
  verifying configuration, read back names, lengths and non-secret values
  only; a verification script must whitelist printable keys rather than
  blacklist secret-looking ones.
- A successful `jscode2session` proves the AppSecret; it does not prove the
  AppKey or merchant enablement.

## Diagnose from errMsg, not only errCode

`-15001` means “parameter error” and carries the actual reason only in the
fail callback's `errMsg`. Treat these as client rules:

- Never collapse a provider failure into a generic network or
  “service unavailable” message. A broad matcher such as “message contains
  `request`” also matches `requestVirtualPayment:fail…` and hides the code.
- Show errCode and the full errMsg for every non-cancel failure (`-2` is user
  cancel). Diagnosis took two extra device round-trips before this was true.
- Map known codes to plain messages (`-15014` item not yet effective, `-15007`
  session expired, `-15002`/`-15012` order unusable → create a new order), and
  keep an explicit fallback that prints the code.

## Orders, environments and fulfilment

- Grant the entitlement only from a server-side order query (`query_order`
  status paid/delivering/delivered, amount matched), never from the client
  success callback, which can be lost.
- Implement at least one of delivery push (`xpay_goods_deliver_notify`) and
  polling on page entry; both together are more reliable. A push is only a
  trigger for a server query.
- **An environment switch invalidates in-flight orders.** An order signed for
  sandbox can never settle in production. If the client restores pending
  orders by idempotency key, it will re-select the dead order on every tap.
  Bind each order to the environment it was created under, and cancel it on
  mismatch so the next attempt creates a fresh order.
- A pending order whose client payment was cancelled or failed is reconciled
  quietly; a closed/unpaid query result cancels it.

## Review state is a configuration state

- Plans visible while payment is disabled reads to a reviewer as both
  “button does nothing” and “virtual payment not integrated”.
- Hiding the purchase entry instead triggers the “member page has no real
  operating content/goods” rejection.
- Neither is fixed in code alone: the submitted version must have payment
  live, real member content published, and a review note/recording showing
  home → free article → locked member article → purchase → member article
  readable.

## Deploy and upload sentinels

- A packaging step inside a command substitution such as
  `$(prepare | tail -n 1)` swallows its own failure. `npm ci --prefix` under a
  symlinked temporary directory rejected `file:` dependencies, and the
  function shipped without `node_modules`; every invoke then failed with
  “0 code exit unexpected”. Resolve staging paths physically and assert the
  artifact contains its dependencies before upload; a health check after
  deploy is required, not optional.
- A dependency audit gate can start failing between deploys from new
  advisories; fix it as its own tracked change rather than bypassing the gate.
- Function configuration edits made in a console survive code-only updates;
  still read them back after every deploy.
- DevTools CLI upload can report “AppID does not exist” when its login state
  has expired even though the account is the owner; check login state before
  investigating membership.

## Acceptance ladder

| Layer | Minimum evidence | Still unproven |
| --- | --- | --- |
| Software | Signing matches the platform vector; provider, reconcile, env-mismatch and error-message tests | Platform acceptance of the signature |
| Cloud | Deployed package contains dependencies; health check; environment names/lengths read back | Client launch |
| Experience | Exact uploaded version creates an order and launches the cashier (Android sandbox) | Apple IAP, real money |
| Device | Exact version on each required terminal: paid order, entitlement and expiry visible, reconciliation after app kill | Review outcome |
| Review | Submitted version with live payment and real member content | Settlement |

## Persistable evidence

Use redacted aliases and digests for environment class, product/plan class,
order state transitions, errCode/errMsg, device profile and version. Keep
AppIDs, offer IDs, environment IDs, order numbers, openids, AppKeys,
AppSecrets, session keys and signatures outside the public skill record.

## Failure patterns to recognize

- Testing iOS in sandbox and reading the failure as a signing bug.
- Treating a generic client toast as the diagnosis.
- Switching environments without closing orders signed for the old one.
- Hiding the purchase entry to pass review.
- Trusting installer exit status instead of inspecting the uploaded artifact.
