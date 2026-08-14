# Google Workspace v0.3.0 regression evidence

Date: 2026-08-14 UTC  
Base: `fe0da535f00dfa836b97751e5b6a295bfac903b6`

This artifact contains no credentials, credential paths, provider responses, or external API traffic. Tests use `.invalid` identities, temporary protected state, installed Gateway code, and scripted HTTP fixtures.

## Binding path safety

Implemented and tested:

- Forge collaborative `workspace` ancestor mode 2777 is accepted only with a trusted owner and an owned private containment boundary below it.
- `auth.bindings.list`, `auth.bindings.status`, and `auth.bindings.resolve` succeed in that layout.
- Gmail, Calendar, and Drive resolve a pod-local alias in that layout with scripted HTTP only.
- symlink roots, hardlinked credentials, later non-sticky other-writable ancestors, missing containment boundaries, and parent inode/mode/owner races are rejected.
- file open/read still uses `O_NOFOLLOW`, ownership and 0600 checks, one-link enforcement, inode comparison, size limits, and before/after file metadata checks; ancestor snapshots are now rechecked after reads.

## Gateway and pagination

Root cause: installed Gateway 2026.4.11 reports JavaScript integer values as simple-schema type `number`, causing a lifecycle schema declaring `integer` to reject `pageSize: 10` before its integer argument mapping ran.

Generated lifecycle schemas now use Gateway-compatible `number` for rich-schema integers. Integer argument mappings remain authoritative at prepare time and rich command schemas remain authoritative in the harness. End-to-end installed-Gateway prepare→run tests prove:

- top-level `pageSize: 10` prepares and executes for Gmail, Calendar, and Drive;
- Gmail/Calendar `params.maxResults: 10` and Drive `params.pageSize: 10` prepare through the Gateway-compatible deterministic JSON-string representation and execute;
- fractional, string, and boolean top-level page sizes fail Gateway prepare;
- provider pagination values outside 1..500, booleans, and strings fail harness validation;
- conflicting top-level and provider pagination values fail instead of being silently selected;
- no external network is used.

## Commands and results

```text
python3 harnesses/google-workspace/scripts/generate_schemas.py
PASS (deterministic generated harness and rich contracts)

python3 -m pytest -q harnesses/google-workspace/tests
PASS: 125 passed, 164 subtests passed

python3 -m pytest -q tests/test_gateway_harness_manifests.py
PASS: 4 passed

python3 scripts/sync_registry.py --check
PASS: registry synchronized

python3 scripts/validate.py
PASS: validated 36 capability entries
```

The Google Workspace suite needed local loopback-socket permission for its existing desktop OAuth receiver tests. No external endpoint was contacted.

## Wider repository validation

A repository-wide `python3 -m pytest -q` collection is not a clean canonical command in this environment because Cloud Webhooks resolves an installed package instead of its in-tree package. With the package path corrected, unrelated baseline failures remain:

- Cloud Webhooks tests expect older 0.2.3 adapter/manifest behavior while the package reports 0.2.6; its local TLS suite also requires loopback sockets.
- the top-level version-integrity suite reports an unrelated Clawpod Video Studio credential-free self-report exit 12.

These failures do not touch Google Workspace source or generated artifacts. Relevant repository registry, manifest-parser, installed-Gateway, and Google Workspace validations pass.

## Security review

- The Forge exception is narrow: basename `workspace`, exact mode 2777, trusted ownership, and a private owned descendant are all required. Every other non-sticky other-writable ancestor remains rejected.
- A later shared ancestor cannot be hidden by an earlier acceptable Forge parent; each ancestor is independently checked.
- Existing symlink, hardlink, containment, atomic replacement, permission, and file-race checks remain active; ancestor race detection was strengthened.
- Provider parameter normalization removes both pagination spellings before emitting exactly the provider-correct key, preventing duplicates and ambiguity.
- Generated output was produced only by `scripts/generate_schemas.py`; the registry was produced only by `scripts/sync_registry.py`.
