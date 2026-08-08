# Professional AI Photo Studio Workflow Research

Date: 2026-08-08
Status: evidence-backed design input

Scope: established commercial photography, art direction, shot planning, retouching, proofing, color/output, provenance, and AI consistency workflows.

## Executive conclusion

ClawPod Image Studio should be **refined**, not replaced or duplicated. The installed v0.2.0 Skill and Harness already provide strong provider routing, request validation, cost/approval gates, provenance, artifact inspection, and retry safety. However, their unit of work is still primarily a provider request. A professional studio needs a higher-level, persistent **production/job model** that starts with a brief and shot plan, controls references and continuity, preserves editable masters, supports review decisions and revision rounds, and produces output-specific proofs and renditions.

The recommended classification is **compose + refine**:

- **Refine** the existing `clawpod-image-studio` Skill/Harness because the capability boundary remains image production and the existing provider execution is useful.
- **Compose** its provider execution with the installed `verified-research` capability for evidence-heavy briefs/reference provenance and with approved durable storage for production assets.
- **Do not create** a parallel “professional photo studio” capability. No separate installed or canonical-registry capability covers the same boundary.

## Registry-first evidence

### Installed scan

The environment contains `clawpod-image-studio` v0.2.0 as a Skill/Harness pair. It supports create/edit/compare/onboard/QA across OpenAI, Vertex Imagen, BFL FLUX, and Recraft. Its current production workflow asks for target, audience, intended use, references, rights, dimensions, budget, then validates, estimates, prepares, runs, and inspects artifacts.

Nearby installed capabilities:

- `verified-research`, suitable for traceable source/reference evidence.
- `synology-smb-storage`, suitable for an approved durable-artifact root.
- `clawpod-ocr`, useful only when extracting text from visual references, not a studio workflow substitute.
- `clawpod-video-studio`, adjacent media production but not a still-photo workflow substitute.

### Canonical registry scan

Canonical registry inspected at `Wondermove-Inc/clawpod-capabilities`, commit `c0f9d2852412d2312c40cc3d65da002dc89233c4`. Searches for image, photo, studio, retouch, color, and proof found no canonical still-image studio capability. The canonical registry includes `verified-research` and adjacent capabilities, but not a competing professional still-production system.

### Decision

| Option | Decision | Evidence |
|---|---|---|
| Reuse unchanged | Reject | Existing capability safely executes provider requests but lacks persistent production/shot/review/output states. |
| Refine | Yes | Same image-production boundary; preserve provider adapters, approvals, estimates, artifact inspection, and retry controls. |
| Compose | Yes | Use verified research for sourced reference briefs and durable storage for masters/deliverables. |
| Create parallel capability | Reject | Would duplicate the installed studio boundary and fragment policy, providers, and provenance. |

## Evidence and implications

### 1. Color is an end-to-end managed system, not an export option

Adobe explains that devices operate in different color spaces, profiles reconcile those differences, monitors should be calibrated/profiled, editing may use a wide-gamut space, and output should select a destination profile. Adobe also states that soft-proof reliability depends on monitor quality, monitor/output profiles, and ambient light, and that a paper/printer-specific profile is often the most accurate proof.

**Requirements**

1. Record a job-level color policy: working space, bit depth, display profile/calibration date, viewing assumptions, destination profile, rendering intent, and black-point/paper simulation choices.
2. Separate editable master from output rendition. Never silently convert or flatten the only master.
3. Add an explicit `proof` stage keyed to output condition, not a generic “looks good” QA flag.
4. Validate embedded ICC profile and report profile mismatches or untagged output.
5. Support multiple renditions from one approved master, for example web sRGB JPEG, print-profile TIFF, and marketplace-specific crop.
6. Treat human visual approval on an uncalibrated/unknown display as limited-confidence approval.

**Anti-patterns**

- Assuming sRGB is universally correct.
- Comparing provider outputs without normalizing viewing/color conditions.
- Calling pixel decode/dimensions a professional color QA.
- Baking a destination conversion into the only editable asset.

### 2. Professional editing is selective, reversible, and versioned

Adobe describes Generative Fill as a non-destructive edit, with an explicit selection and selectable variations. The Library of Congress describes TIFF as commonly used as an initial- or middle-state format and as a preferred format for digital photographs, with strong support for high resolution and flexible color space/bit depth.

**Requirements**

1. Model retouch work as ordered operations against a source/master, with masks/selections, tool/model/version, parameters or prompt digest, operator, timestamp, and resulting derivative hash.
2. Preserve source, editable master, review proxy, and final rendition as distinct asset roles.
3. Make alternatives first-class `variants`, never overwrite-in-place.
4. Allow approved variants to branch into retouch versions while retaining lineage.
5. Add stage-specific QA: technical cleanup, product/identity fidelity, compositing realism, forbidden change checks, and output QA.
6. Export a high-bit-depth/lossless master where the workflow requires further finishing; do not equate final delivery format with archival/edit master.

**Anti-patterns**

- Destructive edits with no mask, source, or operation history.
- Prompt-only history that omits reference hashes, model version, seed/control inputs, or local edits.
- Repeated generation as a substitute for directed retouching.
- One file called `final.png` that simultaneously acts as source, master, proof, and delivery.

### 3. Proofing is a decision workflow

Adobe’s proofing guidance explicitly compares original and simulated output and distinguishes soft proofs from hard proofs. This implies that approval must be tied to a particular asset version and output condition.

**Requirements**

1. Review objects must bind asset hash/version, proof condition, reviewer, decision, annotations, timestamp, and revision-round number.
2. Use closed decision states such as `selected`, `changes_requested`, `approved_master`, `approved_output`, and `rejected`.
3. Support region-based annotations and structured change requests, not only free-text comments.
4. Freeze the exact approved hash. Any pixel, crop, metadata, or profile change invalidates downstream approval or creates a new reviewable version.
5. Distinguish creative approval, retouch approval, legal/rights approval, and output approval.
6. Make contact-sheet/review proxies reproducible from immutable variants and visibly label color limitations.

**Anti-patterns**

- “Latest file wins.”
- Approval detached from an artifact digest.
- Treating provider acceptance, safety acceptance, or generation completion as client approval.
- Sending full masters when bounded review proxies are sufficient.

### 4. Metadata and provenance are production data

IPTC describes its Photo Metadata Standard as widely used professionally and says it supports precise data for people, locations, products, creation dates/identifiers, and rights. IPTC 2025.1 adds AI prompt information, prompt-writer name, AI system, and AI system version. C2PA’s stated purpose is certifying the source and history/provenance of media.

**Requirements**

1. Maintain a structured metadata manifest across derivatives: creator/contributors, client/job/shot IDs, caption, products/subjects, locations, rights, releases/consent, usage/license, accessibility text, and delivery restrictions.
2. Record AI involvement with system/model/version, operation type, prompt digest or policy-governed prompt data, reference hashes, and human edits.
3. Preserve provider metadata and C2PA/Content Credentials when present; verify rather than merely copy provenance claims.
4. Apply explicit metadata policies per rendition because some destinations strip metadata or require privacy redaction.
5. Generate a machine-readable delivery manifest with hashes, dimensions, MIME, ICC profile, metadata/provenance state, rights state, and approval IDs.

**Anti-patterns**

- Storing provenance only in filenames or chat transcripts.
- Stripping all metadata by default.
- Embedding private prompts, personal information, or unreleased subject data into public files without policy review.
- Claiming C2PA authenticity when only a sidecar log exists.

### 5. AI consistency must be specified and tested, not promised

This is a design inference from professional variant/version/provenance practice and from the current provider capability’s support for references, masks, models, and artifact inspection. Model output remains stochastic and provider features differ, so “same character/product/style” cannot be a boolean provider option.

**Requirements**

1. Create a **continuity bible** per production: canonical subject/product views, immutable reference hashes, approved palette, lighting diagram/intent, lens/perspective language, background/set rules, wardrobe/prop rules, composition constraints, and forbidden deviations.
2. Define shot-level invariants and tolerances, for example logo geometry exact, SKU color within approved proof process, face/identity consent required, camera angle approximate, background flexible.
3. Pin provider, model/version, operation, reference set, control inputs, and supported seed when available. Never invent determinism where the provider does not guarantee it.
4. Evaluate continuity across the set, not only image-by-image. Include identity/product geometry, materials, typography/logos, palette, lighting direction, perspective, scale, and recurring props.
5. Escalate failed consistency from rerolling to controlled editing/compositing or human retouch. Preserve selected source regions and masks.
6. Keep a golden approved frame/reference set and run regression comparison when model/provider changes.
7. Require human approval for identity, product truth, regulated claims, and brand-critical details.

**Anti-patterns**

- One giant prompt as the only art-direction record.
- Using prompt text as proof of visual consistency.
- Mixing model/provider versions inside a set without a recorded exception and reproof.
- Endless paid rerolls with no acceptance metric.
- Pixel-similarity scoring as the sole creative or identity decision.

## Required professional production model

The minimum viable domain model should be:

`Production → Brief → Shot list → Shot → Attempt/Variant → Select → Retouch version → Proof → Approval → Rendition → Delivery`

Supporting immutable records:

- `ReferenceAsset` with source, rights/consent, role, hash, and usage limits.
- `ContinuitySpec` with set-level invariants and tolerances.
- `ColorPolicy` and `OutputSpec`.
- `EditOperation` with mask/input/output lineage.
- `ReviewDecision` bound to an exact hash and proof condition.
- `RightsRecord` and release/consent status.
- `ProvenanceManifest` and delivery manifest.
- `CostLedger` aggregating attempts, edits, comparisons, and abandoned variants by production/shot.

## Workflow gates and states

1. **Intake**: business goal, audience, channels, deliverables, deadline, budget, rights, privacy, real-person policy.
2. **Brief approved**: creative proposition, references with provenance/rights, brand constraints, success criteria.
3. **Shot plan approved**: shot IDs, framing/crops, subject/SKU, required variants, continuity constraints, priority, output specs.
4. **Look development**: low-cost bounded explorations, then approved look/reference freeze.
5. **Production**: prepared provider operations per shot, exact approval and cost ledger, immutable attempts.
6. **Selects**: contact sheet, ratings/annotations, explicit select decision.
7. **Retouch**: issue list and ordered non-destructive operations; no uncontrolled regeneration of approved content.
8. **Set continuity QA**: compare the complete campaign/set against the continuity bible.
9. **Proofing**: output-condition soft proof and, when required, hard-proof evidence.
10. **Approvals**: separate creative, rights/legal, master, and output approvals, each hash-bound.
11. **Renditions/delivery**: deterministic exports, metadata policy, manifest, checksums, durable destination.
12. **Archive/reopen**: retain sources, masters, operations, decisions, manifests, and provider/cost provenance according to policy.

## Acceptance requirements for the next contract-design card

The next implementation contract should be rejected unless it includes:

- Persistent production and shot IDs, not only request IDs.
- Immutable asset/version lineage and exact hashes.
- Brief, shot-list, continuity, color, rights, review, approval, rendition, and delivery schemas.
- Stage transitions with validation and explicit reopen/invalidation rules.
- Provider/model capability declarations, including unsupported consistency controls.
- Aggregated budgets and ambiguous-billing handling at production and shot scope.
- Output-specific proof records and ICC/profile inspection.
- Metadata/provenance manifests including AI fields.
- Human-gated approvals for rights, identity/product fidelity, brand-critical content, and publication.
- Tests for stale approvals, mutated assets, missing references/releases, profile mismatch, provider/model drift, failed set continuity, metadata leakage, and retry ambiguity.

## Sources

1. Adobe, “How to manage color in Lightroom Classic,” updated 2021-04-27. https://helpx.adobe.com/lightroom-classic/desktop/workspace/color-management.html
   - Evidence: profiles reconcile device color differences; monitor calibration/profile is required; wide-gamut editing and output-specific profiles/soft proofs are distinct.
2. Adobe, “Proofing colors in Photoshop.” https://helpx.adobe.com/photoshop/using/proofing-colors.html
   - Evidence: soft proofs simulate a specific output device; reliability depends on monitor/output profiles and ambient lighting; custom paper/printer profiles improve accuracy.
3. Adobe, “Use Generative Fill in Photoshop on desktop,” updated 2026-06-18. https://helpx.adobe.com/photoshop/desktop/create-open-import-images/create-images/edit-images-with-generative-fill.html
   - Evidence: Adobe explicitly describes the operation as non-destructive, selection-scoped, and variation-based.
4. IPTC, “IPTC Photo Metadata Standard.” https://iptc.org/standards/photo-metadata/iptc-standard/
   - Evidence: professional photo metadata covers people, locations, products, creation, rights; 2025.1 adds AI prompt/system fields.
5. Library of Congress, “TIFF, Revision 6.0,” last significant update 2024-05-06. https://www.loc.gov/preservation/digital/formats/fdd/fdd000022.shtml
   - Evidence: TIFF is commonly an initial/middle-state format, preferred for digital photographs, and supports high resolution, flexible color space, and bit depth.
6. C2PA, “C2PA Specifications 2.2.” https://spec.c2pa.org/specifications/specifications/2.2/index.html
   - Evidence: C2PA develops standards for certifying media source and history/provenance.

## Confidence and limitations

- **High confidence**: color management, output proofing, metadata/provenance, non-destructive/versioned editing, and master/rendition separation, based on first-party or standards-body sources.
- **Medium-high confidence**: the proposed production/shot/review domain model, synthesized from established professional workflow concepts and the cited technical requirements.
- **Medium confidence**: AI continuity test design. Provider guarantees and controls vary and must be verified in the provider contract; no claim of deterministic identity or style consistency is made.
- Capture One documentation was identified as a relevant first-party source for sessions/variants/live review but returned access-control responses during this run, so no unsupported quotes from it are used.
