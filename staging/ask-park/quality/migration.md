# S16A staging migration contract

S16A prepares, but does not activate, the canonical `$ask-park` identity.
`scripts/migration.py` is staging-only: it never edits the root package, the
active local skill, the selector, or a configured scanned root.

## Inventory

`inventory_roots()` accepts configured root aliases, path inputs, and enabled
state. It enumerates symlink status, a redacted realpath reference, file count,
per-file digest, and manifest digest. Paths, credentials, URLs, private names,
and secret bytes never enter the returned record.

## Staging and receipt

`stage_canonical_install()` copies the complete staged package to an explicit
destination outside scanned roots, validates the single entrypoint/metadata
closure, and emits an ask-park package manifest. `pre_migration_receipt()`
binds repository identity/history, inventory digest, staged manifest digest,
legacy-enabled/canonical-disabled state, and a recoverable rollback envelope.

## Rollback checkpoints

The rehearsal covers `staging-failure`, `canonical-validation-failure`,
`selector-failure`, and `post-retirement-failure`. Each checkpoint removes
partial canonical state while preserving the legacy backup. S16A does not
disable or move the current identity; S16B/S16C own the later cutover.
