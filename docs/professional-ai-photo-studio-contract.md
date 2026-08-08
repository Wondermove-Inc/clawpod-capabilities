# ClawPod Image Studio Professional Production Contract

Date: 2026-08-08
Status: implementation contract
Target: refine the existing `clawpod-image-studio` Skill/Harness, preserving its provider, secret, paid-intent, safety, artifact, and retry controls.

## 1. Boundary and invariants

The professional layer owns persistent studio planning, lineage, review, finishing, proofing, and delivery. Existing provider commands remain the only execution boundary for billable generation/editing.

Non-negotiable invariants:

1. Every mutable record has `schemaVersion`, stable ID, `revision`, `createdAt`, and `updatedAt`. Mutations require the expected revision.
2. Asset bytes are immutable and content-addressed by lowercase SHA-256. A changed byte creates a new asset/version.
3. Project and shot identity is independent of provider request identity.
4. An approval binds an exact asset hash, record revisions, proof condition where applicable, and approval purpose. A relevant change invalidates it, never silently migrates it.
5. Source, editable master, review proxy, proof, and delivery rendition are separate asset roles.
6. Provider, model/version, reference hashes, prompt digest, controls, and result provenance remain explicit. Unsupported controls are rejected, not emulated or invented.
7. No studio command may carry plaintext credentials. Provider execution still uses identical owner-scoped `secretRefs` at prepare/run and never persists pointers or plaintext.
8. Paid work still requires `request.validate` → `request.estimate` → `request.prepare` → exact approval → unchanged run digest. Studio approval is not paid approval, and paid approval is not publication approval.
9. Ambiguous or possibly accepted paid requests are never automatically retried. Reconcile the original request; a new submission requires a fresh estimate and approval.
10. Real-person identity, product truth, regulated claims, brand-critical details, rights/legal clearance, and publication require human decisions.
11. Files remain under the configured root with symlink/traversal protection. Durable delivery requires an approved durable artifact root.
12. Provider acceptance, safety acceptance, critic scores, or automated QA can never create a human approval.

## 2. Canonical lifecycle

```text
Project
  intake → brief_pending → brief_approved → shot_plan_approved
  → look_development → production → selects → retouch
  → continuity_review → proofing → approval → delivery_ready
  → delivered → archived
```

A project may move backward only through `project.reopen`, which records reason and actor, increments revision, and invalidates affected downstream approvals and exports. `blocked` and `cancelled` are terminal operational states but retain all records. Archive is reversible metadata; asset deletion is outside this contract.

Per-shot lifecycle:

```text
planned → ready → attempting → variants_ready → selected
→ retouching → master_candidate → master_approved
→ rendition_ready → output_approved → delivered
```

A command must reject a transition when prerequisites are absent. It must return the full list of unmet gates without partially mutating state.

## 3. Core records

All records are canonical JSON, UTF-8, sorted-key hashed when a digest is required. IDs use prefixed UUIDs, for example `prj_…`, `shot_…`, `ast_…`, `ver_…`, `rev_…`, `apr_…`.

### 3.1 Creative Brief

Required fields:

```yaml
schemaVersion: 1
projectId: prj_uuid
revision: 3
title: Campaign name
businessGoal: measurable outcome
audience: [segment]
message: single creative proposition
intendedUses: [web, social, print]
deliverables:
  - channelPresetId: instagram-feed-v1
    quantity: 4
    dueAt: RFC3339
creativeDirection:
  mood: [precise terms]
  palette: ["#RRGGBB"]
  composition: [rules]
  lighting: [rules]
  forbiddenElements: [rules]
references: [ref_uuid]
brandConstraints: [constraint_uuid]
rightsPolicy:
  territories: [KR]
  media: [digital]
  term: ISO8601 duration or date interval
  realPersonPolicy: prohibited|consented_only|not_applicable
  trademarkPolicy: text
privacyPolicy:
  promptRetention: allowed|redacted|digest_only
  publicMetadata: allowlist
budget:
  currency: USD
  projectHardCeiling: decimal string
  perShotHardCeiling: decimal string
successCriteria:
  - id: crit_uuid
    metric: structured name
    operator: eq|gte|lte|human_pass
    target: value
approval:
  status: draft|approved|invalidated
  approvalId: apr_uuid|null
```

Brief approval requires complete rights/privacy/budget fields, at least one measurable success criterion, reference rights status, and a human approver. Any change to intended use, rights, budget, references, brand constraints, or success criteria invalidates brief and downstream shot-plan approvals.

### 3.2 Shot Spec DSL

The DSL is declarative YAML or equivalent JSON. Unknown keys are errors. Units and enums are explicit.

```yaml
shotSpecVersion: 1
shotId: shot_uuid
projectId: prj_uuid
name: hero-front-01
priority: required|optional
purpose: text
subject:
  kind: product|person|place|composite|illustration
  ids: [sku_or_subject_id]
  referenceIds: [ref_uuid]
  releases: [rights_uuid]
frame:
  aspectRatio: "4:5"
  orientation: portrait
  composition: centered|rule_of_thirds|symmetrical|custom
  cropSafetyPct: {top: 8, right: 8, bottom: 12, left: 8}
  camera:
    shotSize: ECU|CU|MCU|MS|FS|WS
    angle: eye|high|low|top|custom
    focalLengthEquivalentMm: 85
    perspective: compressed|natural|wide|custom
  subjectOccupancyPct: {min: 55, max: 68}
look:
  continuitySpecId: cont_uuid
  lighting: {keyDirectionDeg: 315, hardness: soft, contrast: medium}
  palette: ["#RRGGBB"]
  background: text
  materialRules: [text]
constraints:
  - id: con_uuid
    scope: subject|logo|text|color|lighting|geometry|background|prop
    rule: text
    severity: blocking|major|minor
    evaluation: exact|tolerance|human
    tolerance: {metric: deltaE2000, max: 2.0}
    referenceIds: [ref_uuid]
variants:
  requested: 4
  maximumPaidAttempts: 8
  explorationMode: bounded
providerPlan:
  preferredProvider: openai
  preferredModel: gpt-image-1
  requiredCapabilities: [reference_image]
  optionalControls: [seed]
  fallback: none|fresh_approval
outputs: [out_uuid]
acceptanceRubricId: rub_uuid
```

Rules:

- Exact claims such as logo geometry or required text must use `evaluation: exact` and human/technical verification. They may not rely solely on generative output.
- A numeric tolerance names its metric and units. No generic “consistent” boolean is valid.
- `maximumPaidAttempts` is a hard bound, not a retry target.
- Missing provider capabilities produce `UNSUPPORTED_CONTROL`; fallback never occurs silently.
- Provider/model/version changes invalidate look approval and require regression/continuity review.

### 3.3 References, continuity, rights, and color

`ReferenceAsset` contains `referenceId`, asset hash, source URI or acquisition note, role (`subject`, `product`, `style`, `palette`, `set`, `logo`, `mask`, `golden_frame`), owner, rights status, consent/release IDs, allowed uses, expiry, privacy classification, and provenance. Expired, missing, or incompatible rights block prepare.

`ContinuitySpec` contains immutable reference hashes, approved palette, lighting intent, perspective/lens rules, set/background rules, wardrobe/prop rules, recurring scale relationships, exact invariants, tolerances, forbidden deviations, golden frames, and exceptions. Each exception has scope, reason, approver, expiry, and affected shots.

`RightsRecord` states subject/asset, owner or releasing party, status (`unknown`, `pending`, `cleared`, `restricted`, `expired`, `revoked`), allowed media/territory/term, evidence asset hash, and human verifier. `unknown`, `pending`, `expired`, or `revoked` blocks incompatible production and delivery.

`ColorPolicy` contains working space, bit depth, embedded-profile requirement, display profile/calibration date, viewing assumptions, destination profile, rendering intent, black-point compensation, paper simulation, proof requirement, and human confidence limitation. Unknown display calibration must be reported and cannot produce high-confidence color approval.

### 3.4 Project, shot, asset, and version model

```text
Project 1─* Shot 1─* Attempt 1─* Variant
Variant 0─* Select
Asset 1─* AssetVersion
AssetVersion 1─* EditOperation → AssetVersion
AssetVersion 1─* ReviewDecision
AssetVersion 1─* Rendition 1─* Proof
Delivery *─* Rendition
```

`AssetVersion` fields include:

- `versionId`, `assetId`, `projectId`, optional `shotId`.
- `role`: `source`, `reference`, `attempt`, `variant`, `select`, `editable_master`, `review_proxy`, `proof`, `rendition`, `delivery_manifest`.
- path relative to root, SHA-256, byte count, MIME, dimensions, alpha, bit depth, ICC profile fingerprint/name.
- parent version IDs and producing operation ID.
- provider/model/request provenance, reference hashes, prompt digest, supported control values, seed only if returned/supported.
- metadata/provenance/C2PA inspection state.
- immutable creation timestamp and actor.

Overwrite is forbidden. Filenames are presentation metadata, never identity. Lineage must be a directed acyclic graph; cycles and missing parents are validation errors.

### 3.5 Attempts, cost ledger, and billing state

Every provider submission creates one `Attempt` before transport with prepared digest, binding digest (not secret pointer), approval ID, estimate, hard ceiling, expiry, shot/project IDs, and status. Statuses:

`prepared`, `submitted`, `accepted`, `succeeded`, `definite_pre_acceptance_failure`, `ambiguous_billing`, `failed_after_acceptance`, `reconciled`, `cancelled_before_submit`.

`CostLedgerEntry` records estimate low/high, approved maximum, provider-reported cost when available, currency, billing state (`not_billable`, `estimated`, `possibly_billed`, `billed`, `reconciled`), provider request ID, and attempt ID. Project and shot totals include successful, abandoned, and ambiguous attempts. Preparing another paid request is blocked if its maximum plus billed/possibly-billed exposure exceeds either hard ceiling.

## 4. Review, critic, revision, and finishing contracts

### 4.1 Critic rubric

A rubric is versioned and weighted but cannot override blocking checks.

```yaml
rubricId: rub_uuid
revision: 1
dimensions:
  - id: technical
    weight: 0.15
    evaluator: machine_then_human
    minimum: 4
  - id: brief_alignment
    weight: 0.20
    evaluator: human
    minimum: 4
  - id: subject_product_fidelity
    weight: 0.25
    evaluator: human_required
    minimum: 5
  - id: composition
    weight: 0.10
    evaluator: human
    minimum: 3
  - id: lighting_material_realism
    weight: 0.10
    evaluator: human
    minimum: 3
  - id: continuity
    weight: 0.10
    evaluator: set_human_required
    minimum: 4
  - id: retouch_integrity
    weight: 0.05
    evaluator: machine_then_human
    minimum: 4
  - id: output_color_metadata
    weight: 0.05
    evaluator: machine_then_human
    minimum: 5
scoreScale: {min: 1, max: 5}
pass:
  weightedMinimum: 4.0
  blockingSeveritiesAllowed: 0
```

Each score includes evaluator identity/type, evidence, confidence, annotations, and asset hash. Automated scores are advisory for identity, product truth, regulated claims, brand-critical details, creative approval, and rights.

Default blocking defects: corrupt/decode failure, wrong subject/SKU, identity mismatch, malformed logo/type, prohibited content, absent release, output profile mismatch, metadata leakage, broken lineage, stale approval, and unresolved ambiguous billing before delivery closure.

### 4.2 Review decisions

A `ReviewDecision` binds exact asset SHA-256, shot/project revision, rubric revision, proof condition, reviewer, role, timestamp, revision round, annotations, and one decision:

- `selected`
- `changes_requested`
- `approved_creative`
- `approved_rights`
- `approved_master`
- `approved_output`
- `rejected`

Annotations use normalized coordinates `[0,1]` with rectangle/polygon/point, category, severity, text, and optional reference/constraint ID. Review proxies display asset ID/hash prefix, revision, color limitation, and “not delivery master”.

### 4.3 Revision Plan

A revision plan is created only from a selected or master-candidate hash:

```yaml
revisionPlanId: rev_uuid
baseVersionId: ver_uuid
baseSha256: 64hex
round: 2
objective: text
preserve:
  - constraint/reference/region identifier
issues:
  - issueId: issue_uuid
    sourceAnnotationIds: [ann_uuid]
    category: cleanup|fidelity|composition|color|composite|metadata|output
    severity: blocking|major|minor
    acceptance: measurable statement
    operation: local_edit|composite|color_adjust|metadata|export|regenerate
    maskVersionId: ver_uuid|null
    owner: human|provider
order: [issue_uuid]
maximumPaidOperations: 2
approvalImpact: [creative, master, output]
```

Rules: directed local edits are preferred after selection. `regenerate` must state why controlled edit/composite is inadequate and creates a new attempt/variant branch. Completion requires every issue to be `resolved`, `accepted_exception`, or `deferred` with approver and rationale.

### 4.4 Retouch/finishing recipe

Recipes are ordered, declarative, and non-destructive. Allowed operation kinds:

- `cleanup` (mask required)
- `composite` (source and mask required)
- `geometry` (parameters and affected region required)
- `tone_color` (working-space parameters required)
- `texture_detail` (mask required)
- `generative_edit` (mask, prompt digest, provider/model, paid intent when billable)
- `metadata_apply` (policy and field allowlist required)
- `profile_convert` (source/destination ICC fingerprints and intent required)
- `resize_crop` (algorithm, dimensions, crop anchor/safe-area check)
- `sharpen` (output dimensions/medium target required)
- `encode` (format/options required)

Every `EditOperation` records ordered index, input hashes, mask hash, recipe revision, tool/provider/model version, parameters or redacted/digested prompt, operator, timestamp, output hash, and QA result. A failure leaves input untouched and creates no successful version record. Recipe execution is idempotent by `(recipeDigest, inputHashes, destinationSpec)`; conflicting output bytes are `NONDETERMINISTIC_OUTPUT`, preserved for inspection, and never overwrite the expected asset.

## 5. Contact sheets, proofing, exports, and delivery

### 5.1 Contact sheet

`contact_sheet.create` is deterministic for identical inputs/options and generates:

- bounded review proxies, never originals by default;
- stable ordering by shot then variant or explicit order;
- thumbnail, shot ID, variant ID, hash prefix, provider/model, dimensions, rubric score/status, and rights-safe labels;
- page size, grid, background, caption policy, and color limitation;
- a JSON manifest listing exact source hashes and renderer version.

Private prompt text, personal information, unreleased subject data, secret metadata, and provider credentials are excluded. Contact sheets cannot confer selection or approval.

### 5.2 Output and proof

`OutputSpec` requires pixel dimensions or physical size+DPI, aspect/crop, file format, quality/compression, color destination/profile, bit depth, alpha, metadata policy, naming template, size ceiling, sharpening target, and channel preset revision.

A `Proof` binds rendition hash, source master hash, output spec digest, destination ICC fingerprint, rendering intent, display profile/calibration context, soft/hard proof kind, proof asset/evidence hash, reviewer, decision, and confidence. Any crop, pixels, metadata, encoding, or ICC change creates a new rendition and invalidates output approval.

### 5.3 Versioned channel presets

Minimum built-ins are policy examples, not claims about mutable platform limits:

| Preset ID | Contract |
|---|---|
| `web-srgb-v1` | JPEG/PNG, embedded sRGB, metadata allowlist, explicit dimensions and byte ceiling supplied by output spec |
| `instagram-feed-v1` | 4:5 or 1:1, sRGB JPEG, safe-area check, user-supplied current byte/dimension limit |
| `linkedin-feed-v1` | sRGB JPEG/PNG, explicit aspect/dimensions, user-supplied current platform limit |
| `print-tiff-v1` | TIFF, destination ICC required, 16-bit when pipeline supports it, no flattening of the only editable master |
| `marketplace-v1` | per-marketplace child preset required, exact dimensions/background/metadata rules, no generic silent defaults |
| `archive-master-v1` | lossless high-bit-depth master plus sidecars, original ICC retained, not a publication rendition |

Presets are immutable/versioned. Platform limits must be reviewed at use time when marked volatile. A changed preset revision requires re-export and reapproval.

`delivery.prepare` creates an exact manifest with project/shot/version IDs, paths, hashes, bytes, MIME/dimensions, ICC, metadata/provenance/C2PA state, rights and approval IDs, output spec/preset revision, and destination. `delivery.commit` requires exact manifest digest, durable-root verification, and separate publication/share approval when externally visible.

## 6. Harness command surface

All commands accept one JSON object and return the standard redacted envelope. Local planning/QA commands are non-networked and non-billable unless explicitly stated.

| Command | Purpose | Side effect / gate |
|---|---|---|
| `project.create|get|list` | Create/read project | Local mutation for create |
| `project.transition|reopen` | Enforce lifecycle | Revision checked; reopen invalidates downstream records |
| `brief.validate|save|approve` | Brief contract | Human approval required for approve |
| `shot.validate|save|list` | Shot DSL | Requires approved brief before plan approval |
| `shot.plan.approve` | Freeze shot list | Human approval; exact revisions/digest |
| `reference.add|inspect` | Register immutable refs | Rights/consent validation |
| `continuity.validate|evaluate` | Per-shot and set QA | No provider call; human gate where declared |
| `look.approve` | Freeze golden look | Human, hash-bound |
| `attempt.prepare` | Build provider request | Delegates existing validate/estimate/prepare; paid approval unchanged |
| `attempt.record` | Link provider result | Requires artifact inspection and prepared digest |
| `select.record` | Select immutable variant | Human decision |
| `critic.evaluate` | Structured rubric | Advisory except deterministic blockers |
| `revision.plan|close` | Directed change contract | Hash/revision checked |
| `retouch.plan|execute` | Non-destructive recipe | Billable operations separately prepared/approved |
| `contact_sheet.create` | Review proxy/manifest | Local deterministic render |
| `proof.prepare|record` | Output-condition proof | Human decision for approval |
| `rendition.export` | Deterministic export | Requires approved master and output spec |
| `approval.record|status` | Hash-bound decisions | Typed human role and purpose |
| `delivery.prepare|commit` | Manifest and durable delivery | Exact digest; publication/share is separate approval |
| `ledger.summary|reconcile` | Cost/billing state | Reconcile cannot invent provider cost |
| `audit.verify` | Full project invariant check | Read-only, fail-closed report |

Existing `provider.*`, `onboarding.*`, `connection.*`, `request.*`, `image.*`, `job.*`, and `artifact.inspect` contracts remain authoritative. Professional commands call or compose them; they do not bypass them.

## 7. Error and failure semantics

Every response envelope includes `ok`, `command`, `schemaVersion`, `data`, `warnings`, and `error`. Errors include stable `code`, safe `message`, `retryClass`, and structured `details`; no secrets, full private prompts, or raw provider bodies.

Retry classes:

- `safe_after_fix`: local validation, stale revision, missing prerequisite, path/profile/metadata issue.
- `safe_same_operation`: deterministic local render before commit, with idempotency key.
- `reconcile_only`: submitted provider timeout/loss/5xx/malformed success/download failure.
- `fresh_paid_approval`: any new billable submission.
- `human_decision_required`: rights, identity/product truth, exceptions, publication, destructive action.
- `not_retryable`: safety prohibition, revoked rights, corrupt immutable source until replaced.

Required codes include:

`SCHEMA_INVALID`, `UNKNOWN_FIELD`, `STALE_REVISION`, `INVALID_TRANSITION`, `MISSING_GATE`, `RIGHTS_NOT_CLEARED`, `CONSENT_REQUIRED`, `UNSUPPORTED_CONTROL`, `PROVIDER_MODEL_DRIFT`, `STALE_APPROVAL`, `HASH_MISMATCH`, `LINEAGE_INVALID`, `BUDGET_EXCEEDED`, `AMBIGUOUS_BILLING`, `PROFILE_MISSING`, `PROFILE_MISMATCH`, `PROOF_CONDITION_CHANGED`, `CONTINUITY_FAILED`, `METADATA_LEAK`, `PATH_ESCAPE`, `CORRUPT_ASSET`, `NONDETERMINISTIC_OUTPUT`, `DURABLE_ROOT_UNAVAILABLE`, `PUBLICATION_APPROVAL_REQUIRED`, `SAFETY_BLOCKED`.

Batch commands are atomic for metadata mutations unless explicitly documented as a resumable job. Partial file outputs are quarantined and listed, never registered as successful assets. Audit logs are append-only and redact secret/prompt/private metadata according to policy.

## 8. Approval invalidation matrix

| Change | Invalidates |
|---|---|
| Brief intended use, references, rights, budget, success criteria | brief, shot plan, look, downstream creative/output approvals |
| Shot composition/subject/constraint/output | shot plan, selects onward for affected shot |
| Reference bytes/hash or rights status | look, continuity, affected selects/masters/outputs |
| Provider/model/version/control set | look regression, affected generation approval, continuity review |
| Asset bytes, crop, profile, metadata, encoding | approvals bound to old hash; output proof/approval for rendition |
| Continuity spec | set continuity and affected creative/master approvals |
| Rubric revision | critic pass only; human approvals remain but are marked based on older rubric |
| Output spec/preset/profile | rendition, proof, output approval, delivery manifest |
| Delivery destination or publication scope | delivery/publication approval, not master approval |

Invalidation is explicit, timestamped, reasoned, and queryable. Historical approvals remain audit records with status `invalidated`.

## 9. Measurable acceptance gates

Implementation is acceptable only when automated tests and fixture audits demonstrate all gates below.

1. **Schema coverage:** valid fixtures for every record and command; unknown fields, invalid enums/units, and missing requirements fail. 100% of required commands expose input/output schemas.
2. **Lifecycle:** every illegal project/shot transition fails atomically; reopen records cause and invalidates exactly the matrix-defined descendants.
3. **Lineage:** altered bytes yield a new hash/version; overwrite, missing parent, cycle, hash mismatch, and path escape are rejected.
4. **Approvals:** tests prove stale approvals fail after pixel, crop, ICC, metadata, preset, relevant brief/shot/reference, and provider/model changes.
5. **Rights/safety:** missing/expired/revoked reference rights or required release blocks prepare and delivery; automated scores cannot approve human-gated categories.
6. **Paid controls:** secret pointers/plaintext never appear in persisted fixtures or envelopes; prepare/run binding and digest must match; budget exposure includes `possibly_billed`; ambiguous requests cannot be retried.
7. **Continuity:** fixture set evaluates every blocking invariant and tolerance, identifies affected shots, and blocks master/output progression on failure unless a scoped human exception exists.
8. **Critic:** weights sum to 1.0, minima and blocking defects are enforced, evidence/asset hash is required, and human-only dimensions reject machine approval.
9. **Retouch:** each successful operation preserves input, records mask/parameters/tool/output lineage, and rerunning an identical deterministic recipe is idempotent. Failed execution registers no successful output.
10. **Color/proof:** embedded ICC is inspected; missing/mismatched profiles fail declared policy; proof binds destination condition and display confidence; profile/crop/metadata changes invalidate output approval.
11. **Contact sheet:** same inputs/options produce byte-identical output or a documented renderer-normalized digest, stable order, exact manifest hashes, visible proxy/color labels, and no disallowed metadata.
12. **Exports:** each built-in preset has golden fixtures for dimensions, MIME, ICC, bit depth where detectable, metadata allowlist, byte ceiling, naming, and safe-area checks. Editable master is never overwritten.
13. **Delivery:** manifest accounts for 100% of delivered files with recomputed hashes and approval/right/provenance references; commit fails without durable-root and publication approval when external.
14. **Failure semantics:** each required error code has a test; no test performs a provider call; ambiguous billing, corrupt output, provider drift, metadata leakage, and partial-output quarantine are covered.
15. **Compatibility:** existing v0.2.0 onboarding, OpenAI one-shot transport, exact paid approval, protected secret injection, artifact inspection, and no-auto-retry tests continue to pass unchanged.
16. **Audit:** `audit.verify` on the complete golden project reports zero blocking findings and machine-readable counts for shots, assets, unresolved issues, approvals, rights, costs, proofs, renditions, and deliveries.

## 10. Skill workflow contract

The Skill must guide users through:

1. Intake and approved Creative Brief.
2. Rights-cleared references, continuity bible, color policy, and Shot Spec list.
3. Human approval of shot plan and bounded look development.
4. Existing exact paid preparation/approval per attempt, with project/shot ledger limits.
5. Contact sheet, selects, critic evidence, and directed revision plan.
6. Non-destructive retouch recipes and set-level continuity QA.
7. Hash-bound creative, rights, master, proof, and output approvals.
8. Versioned channel exports, deterministic manifest, durable delivery, and separate publication/share approval.

Completion reporting must include project/shot IDs, exact selected/master/rendition hashes, unresolved exceptions, rights and approval states, continuity and color/proof status, provider/model provenance, billed/possibly-billed/unreconciled costs, durable destination, delivery manifest digest, publication state, and limitations.

The Skill must state plainly that stochastic generation cannot guarantee identity, product, logo, typography, palette, or style consistency; those are specified through references, constraints, controlled edits, set-level evaluation, and human approval.
