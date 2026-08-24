# Ask Park human-gate contract

Human gates protect actions that cannot be authorized from technical access or
an agent's ability to click a control. They are independent of module activity,
evidence freshness, Diagnose state, and project terminal state.

## Lifecycle

```text
not-needed → prepared → awaiting-human → authorized → executed → read-back
                                  └────→ denied
authorized → expired
```

S01 validates records; S01B owns legal transitions and expiry. A denied or
expired gate keeps the same sequential module current. A missing human gate is
not equivalent to authorization.

## Record shape

```json
{
  "gate_id": "gate-experience-upload-r1",
  "schema_version": 1,
  "contract_version": "ask-park.human-gate/v1",
  "state": "awaiting-human",
  "action_type": "upload-experience",
  "action_scope": "park-experience-v1",
  "authorizing_role": "owner",
  "requested_at": "2026-08-24T10:00:00Z",
  "authorized_at": null,
  "evidence_ref": "redacted:experience-upload-gate",
  "authority_basis": "owner decision recorded outside credentials"
}
```

An active gate requires a stable action type/scope, authorizing role, ISO-8601
request timestamp, and a redacted evidence reference. `authorized`, `executed`,
and `read-back` also require `authorized_at`. A `not-needed` gate carries null
authorization fields. A technical access statement such as an authenticated
CLI, login session, permission, or ability to click is not an authority basis.

The authorization record may describe the scope and authorizing role, but must
never contain credentials, QR contents, legal documents, payment keys, AppID or
environment identity values, OpenID, complete URLs, or private customer data.
Use a stable `redacted:` evidence reference instead.

## Human-only actions

Typical gates include identity/主体 confirmation, QR scans, real-device
acceptance, payment credentials and provider truth, legal terms, platform
review submission, and formal release. The gate only records that the human
decision exists; the module still needs read-back evidence after the action.

## Stable errors

The validator emits `HUMAN_GATE_REQUIRED_FIELD`, `HUMAN_GATE_STATE`,
`HUMAN_GATE_TIMESTAMP`, `HUMAN_GATE_EVIDENCE`, `HUMAN_GATE_AUTHORITY`, and
`HUMAN_GATE_NOT_NEEDED` without echoing sensitive values.
