# QA evidence matrix contract

Each applicable row binds the visual/functional observation to a surface,
route, state, identity, and runtime.

```yaml
surface: web-browser | live-browser | devtools-simulator | physical-device | projection
route: stable route alias
viewport: viewport/device profile alias
role: admin | member | guest
data_state: stable state alias
equivalence: exact | approved-reference | historical-exception
tool:
  name: tool alias
  version: recorded version
  runtime_or_base_library: recorded version
before_evidence: null | {ref, sha256, captured_at, identity}
after_evidence:
  ref: sanitized/redacted reference
  sha256: sha256:...
  captured_at: ISO-8601
  source_or_package_identity: alias/digest
  final_compile_receipt_id: stable alias
limitations: [explicit non-claims]
```

The after evidence row requires a hash, timestamp, identity, and final-compile provenance;
after evidence, hash, timestamp, identity, and final-compile provenance are
required. Historical/approved before exceptions never excuse missing after
evidence. Evidence is sanitized before persistence; sensitive screenshots,
URLs, OpenIDs, payment/QR/credential data, filenames, and raw bytes remain
ephemeral or use governed approved-store references.
