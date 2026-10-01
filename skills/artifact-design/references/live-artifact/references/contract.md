# Protocol and data contract

Source: `docs/decisions/live-artifact-design-spec.md` sections 6 and 10; implemented SDK: `src/admin-portal/lib/live-artifact/harness.ts`.

- `agent.data`: arbitrary JSON snapshot for this room and artifact identifier, at most 65,536 UTF-8 bytes when JSON encoded. Do not include credentials, private tokens, or data the room should not see.
- `org-package.checklist`: a display projection, not the raw checklist file. Actual response keys are `checklist`, `onboardingStatus`, `updatedAt`, `leaderRoomId`, and `rooms`. Render `checklist.stages`, an object keyed by stage id. A stage has `status`, optional string `title`, optional localized `displayTitle` (`ko`/`en`), and `items` with string `text` and optional localized `displayText`. Prefer `displayTitle[locale]` in the user's language, then `displayTitle.en`, then `title`, then the stage id. Apply the same locale choice to item displayText. The resolver enforces the existing checklist permission as well as room access. Do not request an installation id or another artifact through the SDK.
- `meta.revision`: ordered integer; `meta.kind`: `snapshot`; `meta.stale`: the last known value is being shown after a fetch failure. Preserve that value with a visible stale notice.
- Error codes: `not_found`, `forbidden`, `gone`, `too_large`, `rate_limited`, `unavailable`. Show a useful status when no payload is available; do not silently show invented current data.
- Parent prefetches before mounting the iframe and polls roughly every ten seconds while visible. HTML updates remount the iframe; data persists. No iframe polling or direct API authentication is needed.
- Static HTML has no scripts. Live HTML receives only `allow-scripts` with an opaque origin and restrictive CSP. Never add sandbox flags or rely on parent DOM/cookies/storage.

## Version compatibility

HTML `version`, data `revision`, protocol `v`/SDK `apiVersion`, and data `schemaVersion` are separate. Declare the supported version for every key in manifest `schemaVersions`. The parent compares it against the snapshot's schemaVersion before delivery. A mismatch clears cached data and stops that subscription. Room viewers open the latest stored version and follow new publications across Markdown, static HTML, and live HTML. A new publication is checked against fresh current data. If it cannot run, the viewer selects an available stored version or shows a disabled fallback and version selector. Versions incompatible with observed data are disabled in the selector; if no compatible version exists, the view stays disabled. This is runtime compatibility, not a permanent DB flag. SDK metadata includes schemaVersion for compatible snapshots. Reopen or publish compatible HTML to start a new session.

Legacy HTML, old envelopes, and writes without a version use v1. The checklist display projection is v1, independent of the source checklist's schema_version. Keep additive optional fields on the same version; removals/type/meaning changes require a new version. Arbitrary agent.data schemas are declared by the author, not validated against a platform schema registry. Validate fields before rendering. The platform retains the latest snapshot only, not per-HTML data history or automatic converters.

Roll out migration/API/Portal support before any writer sends schemaVersion above 1. To roll back to an older client/server, restore compatible v1 payloads and HTML first. Older clients cannot enforce this guard.
