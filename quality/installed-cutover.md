# S16C installed-path canary and recoverable cutover

S16C is the only stage that may touch a real local skill root. It uses the
S16B clean-clone installer to prepare a canonical closure in a managed
temporary directory, runs the installed router/module/QA canary, and only then
moves the legacy entry to a recoverable backup outside scanned roots.

## Read-back contract

The selector inventory must show exactly one enabled `$ask-park` and zero
enabled `$wechat-miniprogram-shipping` entries. The installed manifest digest
must equal the repository closure digest, and the installed canary must load
the router, all seven module contracts, and all QA scripts.

## Rollback and final state

Every S16A checkpoint is rehearsed before retirement. A cutover rollback moves
the canonical directory aside, restores the legacy backup, and reads back
legacy-present/canonical-absent. After the last rehearsal, the canonical move
is re-applied and freshly canaried. The committed operational receipt records
only redacted refs, digests, selector counts, rollback results, and explicit
limitations; it never records a full local path or secret.
