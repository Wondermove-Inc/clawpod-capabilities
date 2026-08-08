# Professional AI Photo Studio E2E Validation

Date: 2026-08-08 (Asia/Seoul)

## Result

**PASS with documented limitations.** The v0.3.0 professional studio vertical slice completed a representative offline commercial product campaign from approved brief through deterministic package delivery. No network or paid provider call was made.

## Commercial project

- Project: Aster No. 8 Launch
- Use: premium product web hero and email launch
- Provider plan recorded: OpenAI `gpt-image-1`
- Actual provider submissions: 0
- Initial candidate: `sha256:0c68153cda1e8b1c580f2a2f2c84ef6b35746884d84b7282ef5c79b501f45047`
- Final master: `sha256:2735b64b906bbc40a64c46da0b6c410b0ac836c2f38a7a38b3417825e8b820bf`
- Verified lineage: final master names the initial candidate as its parent
- Audit: valid, zero blocking findings
- Machine-readable evidence: `docs/professional-ai-photo-studio-e2e-validation.json`

## Rubric comparison

| Dimension | Weight | Initial | Final |
|---|---:|---:|---:|
| Technical | 25% | 4.0 | 5.0 |
| Brand fidelity | 30% | 3.4 | 4.8 |
| Composition | 25% | 4.0 | 4.6 |
| Commercial readiness | 20% | 3.2 | 4.2 |
| **Weighted total** | **100%** | **3.66** | **4.68** |

The final master improved by 1.02 points and cleared the 4.0 acceptance threshold. The critic payload remained advisory-only, and creative, rights, brand-critical, identity, product-truth, and regulated-claims decisions remained explicit human gates.

## Validation matrix

| Area | Evidence | Result |
|---|---|---|
| Success path | Full project, brief, shot, candidate, QA, critic, select, revision, finish, approval, contact sheet, delivery, audit | PASS |
| Invalid input | Unknown Shot Spec field rejected atomically as `UNKNOWN_FIELD` | PASS |
| Backend failure | Mock outage and OpenAI HTTP/transport classifications in automated suite | PASS |
| Permission/path boundary | Missing durable root rejected as `DURABLE_ROOT_UNAVAILABLE`; traversal/symlink tests retained | PASS |
| Retry safety | Ambiguous potentially billable submission classified `BILLING_AMBIGUOUS`, no automatic retry | PASS |
| Secret redaction | Plaintext credential rejection, authorization/body isolation, and redacted error tests | PASS |
| Project recovery | Fresh module process reloaded persisted project and verified audit | PASS |
| Version lineage | Hash-bound parent version, finish recipe, QA, and master approval verified | PASS |
| Output QA | Decode/MIME/dimensions/hash checks passed for candidate and master | PASS |
| Contact sheet | Deterministic SVG proxy and manifest digest produced | PASS |
| Delivery package | Hash-bound deterministic ZIP written beneath an existing durable root | PASS |
| Registry | `scripts/validate.py` validated 32 capability entries | PASS |
| Full harness suite | 31 tests passed | PASS |
| Diff hygiene | `git diff --check` | PASS |

## Limitations

1. Rubric scores are documented human-review judgments, not automated perceptual metrics.
2. The contact sheet is a deterministic SVG review proxy, not a color-managed raster proof.
3. No paid provider generation was performed because fresh exact approval was not supplied.
4. Offline SVG assets validate workflow mechanics, safety gates, persistence, and lineage, but not provider photorealism or model quality.
5. Publication remains unapproved and was not attempted. The package is an internal review delivery only.
