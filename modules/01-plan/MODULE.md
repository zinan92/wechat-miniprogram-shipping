# Plan module

Mental anchor: decide what useful result is being built before writing code.

Plan is the first sequential module. It turns a new idea, an existing-project
takeover, or a material scope change into an immutable issue contract. It
prepares work; it does not create GitHub issues, edit code, request secrets, or
promote the next module.

## Input

- the user's intended outcome and first useful moment;
- a route class: `new`, `takeover`, or `scope-change`;
- repository/Git and product evidence when available;
- prior accepted issue/contract and receipts for a takeover or scope change;
- known platform, identity, backend, device, release, and migration facts.

Read the recorded state before interpreting the request. When the outcome or
accepted baseline is materially uncertain, keep Plan current and record the
decision needed instead of filling the gap from chat memory.

## Output

Produce a Plan record conforming to
[acceptance-contract.md](acceptance-contract.md):

- one-sentence `outcome` and `first_useful_moment`;
- three to seven verifiable acceptance criteria;
- explicit In/Out scope and forbidden changes;
- an S/M/L complexity decision and matching test depth;
- a risk map across intent, identity, backend, experience, device, release,
  and migration;
- a bounded solution search with reusable products, repositories, components,
  or skills and the reason to reuse or reject each;
- `required` or `not-applicable` for every one of the six sequential modules;
- ordered independently verifiable work, each with an issue-ready contract;
- a control outcome and one decision needed when intent or baseline is not
  resolved.

`issue_ready: true` means a contract is prepared for a human or later issue
workflow. It does not mean an issue was created. The record never contains a
remote issue ID unless a separate human-approved workflow reads one back.

## Success predicate

Plan exits only when the outcome is testable, criteria are immutable and
observable, scope and forbidden boundaries are explicit, complexity/test depth
is chosen, all six module applicability decisions are recorded, risks have an
owner or a bounded investigation, and every ordered story has an issue-ready
contract. The resulting receipt is `planned`; it does not prove software,
CloudBase, Experience, Device Acceptance, or Release evidence.

## Failure outcomes and routing

- unclear first useful moment or a material product choice → `unknown`; ask one
  focused decision and remain in Plan;
- accepted criteria or scope conflict → `baseline-conflict`; require an
  accepted superseding contract before preparing work;
- repository/platform facts unavailable → keep the fact `unknown` and define a
  read-only investigation, never request credentials;
- identity, legal, payment, review, or other human authority required →
  `blocked-external` with a named human gate;
- a material source change after acceptance → scope-change Plan and invalidate
  only through Ask Park's lifecycle operation.

These outcomes are control-plane facts, not evidence claims. Plan cannot clear
them by changing prose.

## Evidence

Record the input references and their limitations, the approved outcome,
criteria, In/Out scope, forbidden changes, applicability map, risk decisions,
solution-search findings, complexity rationale, ordered issue contracts, and a
redacted Plan receipt. Keep repository aliases, commit identities, and
evidence references stable; do not persist private targets or secrets.

## Forbidden boundary

- Do not write application or infrastructure code.
- Do not create, edit, or silently rewrite a remote issue.
- Do not call WeChat, CloudBase, GitHub mutation APIs, payment, review, or
  release systems as part of Plan.
- Do not infer AppID, environment identity, ownership, credentials, or legal
  approval.
- Do not pad criteria to reach a count, hide a material deferral, or alter an
  accepted contract without a superseding decision.

## Procedure

1. Restate the outcome and first useful moment; stop for a material decision.
2. Classify `new`, `takeover`, or `scope-change` and read the available source
   evidence with `verified`, `unknown`, or `blocked` status.
3. Choose S/M/L and write the matching test depth and delivery boundary.
4. Search for reusable solutions before proposing new infrastructure. Record
   what was searched, what was found, and why the selected option fits.
5. Map every module to `required` or `not-applicable` with a reason for every
   not-applicable decision.
6. Build the ordered queue as independent story contracts with Outcome,
   3–7 acceptance criteria, In/Out scope, and forbidden changes.
7. Stop at `unknown`, `baseline-conflict`, or `blocked-external` when the
   missing decision can change the first useful moment or accepted boundary.

The next module receives the Plan receipt and the approved issue contract. It
does not receive hidden assumptions or an instruction to “just start coding.”
