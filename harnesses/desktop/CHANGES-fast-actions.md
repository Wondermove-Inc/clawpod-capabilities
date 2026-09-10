# Desktop fast and accurate actions — work in progress

Not a release or a claim of verified whole-GUI performance. Live GUI validation,
linked package installation and independent review are still required.

## Root-cause separation

| Class | Observed cause | Change / limit |
|---|---|---|
| Calling mistake | Multiple chords supplied where backend consumes one | Reject key arrays rather than silently partially executing |
| API friction | Caller computes screenshot-region and target digests | `ui.observe` with `input.target` returns the bound target |
| API friction | Approval receipt requires intermediate file | Optional inline `approval` JSON; identical digest and expiry validation |
| Input implementation | Click before type destroys a prior selection | `keyboard.type` with `textMode: replace` clicks once, then selects all and types |
| Input implementation | Coordinate right/double clicks dispatched as left click | Dispatch the requested button/repetition |
| CPU overhead | Python reconstructs every screenshot pixel for region hashing | Optional native Pillow decoding; same legacy digest bytes, no cached target identities |
| Verification bug | Pixel change reported as literal requested text | Reject semantic assertions for visual targets before input; structural change is not text verification |
| Visual recognition | Ambiguity, occlusion, stale screens, absent accessibility | Not solved by these changes; fresh binding, focus checks and independent result inspection remain necessary |

## Current evidence

- Unmodified baseline: 44 pytest tests passed.
- Working implementation: 87 pytest tests passed (local run; not independent review).
- Digest microbenchmark: RGB 1920x1080 solid-color PNG, region 600x100,
  three samples per implementation, median 462.408 ms Python versus 5.808 ms native.
  Hashes matched. This is not browser/native-app end-to-end performance.
- Runtime prepare/run, idempotency and unknown-outcome no-replay remain required.
- Display/session mutations remain structurally forbidden.

## Interface notes

`ui.observe` input may include a typed `target`. It prepares only; it neither
clicks nor authorizes the later action. Supply observed coordinates and a small
visual region, or an unambiguous accessibility node. Returned `target` can be
passed unchanged to a precision action; that action re-observes and checks it.

`keyboard.type` accepts exactly one text string in `args`. Optional
`textMode: replace` currently supports explicitly bound image/coordinate input
fields only. It does not prove the literal appeared; verify the resulting field.
A key command accepts exactly one key/chord, never a silently truncated sequence.

Inline `approval` is a JSON string with `requestDigest` from preview and a future
timezone-aware ISO `expiresAt`. It is mutually exclusive with `approvalFile`.
The receipt is not a credential and never substitutes for user authority.

Visual postconditions accept only true-valued `activeWindowMatch`,
`windowBoundsUnchanged`, and `visualRegionChanged`. They establish only those
structural properties, not navigation, text contents, search success or purchase.
Unsupported assertions fail before input. Accessibility verification continues
through its existing backend contract.
