# Google Workspace pod-local alias refine specification

Status: implementation specification, no capability code, installation, credentials, or publication in this change  
Canonical baseline: `origin/main` commit `a9e92867264b2527965d51ff285b161d307eb223`  
Baseline package: Google Workspace AgentSkill and Harness `0.2.6`, Harness manifest v1, 152 commands  
Release type: backward-compatible refine release, target version `0.3.0`

## 1. Goal and invariants

Make a short account alias sufficient for normal invocations in one ClawPod pod while keeping OAuth material outside replaceable capability packages. A pod isolates one independent agent, so this design MUST NOT add a runtime `agentId`, agent namespace, or cross-pod lookup. An alias is local to the pod and is not a Google identity.

The implementation MUST preserve these invariants:

1. OAuth tokens and client secrets never enter the binding registry, package tree, manifest, logs, diagnostics, test fixtures, or stdout.
2. The protected binding root survives package replacement and capability update.
3. Explicit typed `credentialPath` remains supported and has highest precedence.
4. Existing credential bundles remain readable without an eager rewrite.
5. No fallback may silently select among multiple aliases or identities.
6. Existing mutation preview, confirmation, idempotency, ETag, and safety behavior is unchanged.
7. Package install/update/rollback MUST NOT recursively copy, delete, chmod, chown, or migrate the protected root.

## 2. Storage boundary and discovery

### 2.1 Protected root

Use one pod-local root selected in this order:

1. `GOOGLE_WORKSPACE_BINDING_ROOT`, accepted only when set by a trusted local runtime and absolute;
2. platform state root plus `openclaw/google-workspace`, for example `${XDG_STATE_HOME:-$HOME/.local/state}/openclaw/google-workspace` on Unix;
3. a runtime-provided OpenClaw pod state directory, if a standard typed value becomes available.

The root MUST be outside `skills/google-workspace`, `harnesses/google-workspace`, registry caches, staging directories, and package replacement targets. Do not infer it from the executable directory or current working directory. Windows and macOS adapters MUST use their standard per-user state locations and equivalent ACL checks.

Layout:

```text
<root>/                         0700, non-symlink directory
  bindings.v1.json             0600, non-symlink regular file
  bindings.v1.lock             0600, non-symlink regular file
  credentials/                 0700
    <opaque-id>.json            0600, credential bundle, never alias-named
  backups/                     0700
    bindings.v1.<timestamp>.json 0600, bounded metadata-only rollback copies
```

The registry stores references to credential files, never credentials. Credential references SHOULD be root-relative opaque paths under `credentials/`. Import may retain an external absolute path only when the user explicitly chooses reference mode; diagnostics must label it non-portable.

### 2.2 Registry schema

`bindings.v1.json` is canonical UTF-8 JSON with no duplicate keys:

```json
{
  "schemaVersion": 1,
  "revision": 7,
  "updatedAt": "2026-08-14T00:00:00Z",
  "bindings": {
    "work": {
      "credentialRef": "credentials/8d3c...json",
      "subjectHash": "sha256:...",
      "emailHint": "u***@example.com",
      "createdAt": "...",
      "updatedAt": "...",
      "source": "login",
      "bundleFormat": 1
    }
  },
  "migration": {"legacyScanCompletedAt": null}
}
```

Aliases MUST match `^[a-z][a-z0-9._-]{0,62}$`, be NFC-normalized, lower-case, and reject path separators, whitespace, control characters, `.` and `..`. `credentialRef` must resolve beneath the root unless explicitly marked `externalReference: true`. `subjectHash` is a non-reversible correlation value. `emailHint` is optional and masked. Unknown top-level or binding keys are rejected until a schema revision defines them.

### 2.3 Locking and atomicity

All reads that participate in mutation and all writes take an OS advisory exclusive lock on `bindings.v1.lock`. Lock acquisition has a bounded timeout and returns `BINDING_LOCK_TIMEOUT`, never an unlocked fallback. Writers:

1. securely open and validate root, lock, registry, and referenced path with no symlink traversal;
2. read and validate current schema and revision;
3. apply one transaction in memory;
4. write canonical JSON to a random same-directory temporary file with create-exclusive semantics and mode 0600;
5. flush file data, atomically replace `bindings.v1.json`, then fsync the parent directory where supported;
6. increment `revision` exactly once and release the lock.

Credential creation/import first stages a mode-0600 file in `credentials/`, fsyncs it, then commits its registry reference. Failure before registry commit removes the staged file. Replacement keeps the prior credential until the registry commit succeeds. Cleanup of unreferenced files is a separate guarded command, never part of a failed transaction. Cross-device rename is forbidden. Crash recovery may remove only validated stale temporary files and unreferenced opaque credential files after a grace period.

## 3. Commands and safety classes

Add these dotted commands to `command_contracts.json`, generated `harness.json`, CLI parsing, and catalog:

| Command | Purpose | Required safety classes |
|---|---|---|
| `auth.bindings.list` | List aliases and sanitized metadata | `secretUse`, `authReuse`, `readOnly` |
| `auth.bindings.status` | Validate registry, path, permissions, bundle shape, and identity consistency | `secretUse`, `authReuse`, `readOnly` |
| `auth.bindings.resolve` | Return sanitized resolution metadata, never a path or token | `secretUse`, `authReuse`, `readOnly` |
| `auth.bindings.import` | Copy or explicitly reference a legacy bundle and bind an alias | `secretUse`, `authReuse`, `writeSafe`, `humanAccountAction` |
| `auth.bindings.rename` | Atomically rename an alias | `secretUse`, `authReuse`, `writeSafe` |
| `auth.bindings.remove` | Remove binding; credential deletion is separate and explicit | `secretUse`, `authReuse`, `writeSafe` |
| `auth.bindings.migrate` | Preview/apply deterministic legacy discovery | `secretUse`, `authReuse`, `writeSafe`, `humanAccountAction` |
| `auth.bindings.permissions.check` | Report permission defects | `secretUse`, `authReuse`, `readOnly` |
| `auth.bindings.permissions.repair` | Repair only owned pod-local root artifacts | `secretUse`, `authReuse`, `writeSafe` |
| `gmail.read` | High-level bounded message/thread search and normalized summaries | `secretUse`, `authReuse`, `readOnly` |
| `calendar.read` | High-level bounded upcoming/range event summaries | `secretUse`, `authReuse`, `readOnly` |
| `drive.read` | High-level bounded file search/list/get metadata | `secretUse`, `authReuse`, `readOnly` |

Every write command supports `preview`; apply requires the fresh effect digest under the existing confirmation machinery. `remove` defaults to binding-only. Deleting a credential requires `deleteCredential: true`, proof that no binding references it, and destructive classification/confirmation. Remote revocation remains `auth.logout` behavior.

## 4. Resolution precedence

For any credentialed command, resolve exactly once before API work:

1. explicit typed `credentialPath` plus explicit `account`: use the named alias inside that bundle, preserving 0.2.6 behavior;
2. explicit typed `credentialPath` without `account`: allow only when that bundle has exactly one account, otherwise `ACCOUNT_REQUIRED`;
3. explicit `account` without `credentialPath`: resolve it in the pod-local registry;
4. deprecated `GOOGLE_WORKSPACE_ACCOUNT`: use only as an alias selector, then resolve in the registry; emit a structured deprecation warning;
5. no selector: use the sole healthy pod-local binding only; zero returns `AUTH_REQUIRED`, multiple returns `ACCOUNT_REQUIRED` with sanitized alias candidates.

An explicit invalid value MUST fail and MUST NOT fall through. Registry aliases never override an explicit bundle path. Identity disagreement between registry metadata and the resolved bundle returns `BINDING_IDENTITY_MISMATCH`. The resolved filesystem path is passed internally to `CredentialProvider`; it is never returned.

## 5. Login, import, and migration

### 5.1 `auth.login`

Retain current consent, managed-browser, loopback-only, PKCE, scope, and smoke-test requirements. Add `bind: true` by default and make `outputPath` optional. With default binding, login stages an opaque credential file under the protected root and atomically binds the requested alias only after OAuth exchange and requested smoke tests succeed. Existing alias replacement requires `overwrite: true`, preview, and confirmation. A failed/cancelled login leaves no binding and removes staged secrets. Explicit legacy `transferRoot` plus `outputPath` remains supported; `bind: false` exactly preserves file-only behavior and emits a migration warning.

Never merge aliases into one new shared bundle for the default path. One opaque credential file per binding reduces write collision and rollback scope. Existing multi-account bundles remain supported through explicit `credentialPath` and import.

### 5.2 Import

`auth.bindings.import` accepts a typed input path, alias, and mode `copy` (default) or `reference`. It validates regular non-symlink mode-0600 input, parses without echoing content, proves the alias exists (or requires `sourceAlias`), obtains sanitized identity metadata, detects duplicate subject bindings, and previews destination/change. Copy mode writes a new opaque file under the root. Reference mode never changes source permissions automatically and is rejected if the source is inside a replaceable package tree.

### 5.3 Migration

Migration is explicit and idempotent. Preview scans only documented legacy paths supplied by typed input or a tightly bounded historical default list. It does not recursively search a home directory, package tree, or workspace. It reports candidate count, masked identity, aliases, permission health, and conflicts, never paths. Apply requires a per-candidate mapping and defaults to copy. Existing bindings win; collisions require an explicit rename or overwrite decision. Record completion metadata but allow later explicit imports. Do not delete legacy files automatically. A post-migration status and one authorized read smoke test are required before recommending manual legacy cleanup.

## 6. Structured diagnostics and permission repair

All new errors use the existing stable envelope and sanitized `error.details`. Add stable codes:

`BINDING_NOT_FOUND`, `BINDING_AMBIGUOUS`, `BINDING_SCHEMA_UNSUPPORTED`, `BINDING_REGISTRY_CORRUPT`, `BINDING_LOCK_TIMEOUT`, `BINDING_PATH_UNSAFE`, `BINDING_PERMISSION_DENIED`, `BINDING_PERMISSION_INSECURE`, `BINDING_IDENTITY_MISMATCH`, `BINDING_CONFLICT`, `MIGRATION_REQUIRED`, and `MIGRATION_CONFLICT`.

Diagnostics include only: alias, schema version, registry revision, check IDs, pass/fail, masked identity, portability, remediation code, and whether repair is available. Never include credential/root paths, OAuth/provider bodies, authorization URL/code, token fields, raw exception text containing a path, or file contents.

Permission checks cover root ownership, root/credentials/backups directory mode, file mode, regular-file type, symlink/reparse-point rejection, parent trust, and referenced-file containment. Repair is conservative:

- preview exact artifact categories and intended mode/ACL, not paths;
- operate only inside the resolved protected root and only on files owned by the current pod user;
- set directories to 0700 and files to 0600 on Unix, equivalent user-only ACLs elsewhere;
- never `chown`, follow links, repair external references, broaden access, or touch package files;
- fail closed on unknown ownership, unsupported ACL semantics, or a changed inode between check and apply.

## 7. High-level read commands

These are convenience adapters, not new provider capabilities:

- `gmail.read`: modes `messages|threads`, bounded query/labels/time filters, default metadata format, normalized sender/recipient/date/subject/snippet/IDs; body or attachment content requires explicit `includeBody`/existing get command and remains size-bounded.
- `calendar.read`: bounded `calendarId` (default `primary`), time range/upcoming window, normalized event ID, summary, start/end/time zone, organizer/attendee counts, status, recurrence marker; no invitation mutation.
- `drive.read`: modes `search|recent|get`, bounded query/spaces/corpora/drive ID, normalized file ID, name, MIME type, modified time, owners masked/count, parents, web link, size; no download/content by default.

Each delegates to existing Gmail/Calendar/Drive transport and pagination code, honors `fields`, `maxItems`, `maxPages`, timeout, scopes, and bound continuation tokens, and emits the existing envelope. Defaults MUST be narrow and bounded. No command infers a remote resource for a later mutation.

## 8. Compatibility, updates, and rollback

- All 152 baseline command names and input/output contracts remain valid.
- `--credential-path` and legacy multi-account bundle semantics remain valid.
- Existing environment alias selection remains for one minor cycle with warnings; token-bearing environment variables remain unsupported.
- New optional resolution does not change mutation safety classes or approval requirements.
- Registry schema v1 readers reject future major schemas without rewriting them.
- Capability update replaces package files only. A pre/post-install test must prove binding-root inode/content digests are unchanged.
- Package rollback to 0.2.6 cannot consume registry aliases, but explicit legacy credential paths remain usable. Document the safe rollback command as selecting the referenced credential path manually, without moving it into the package.
- Registry rollback restores a metadata backup only after validating every referenced credential and revision. Never roll back token content automatically. Keep a bounded number of metadata backups and prune only under lock.

## 9. Manifest, Gateway, version, and digest constraints

Target both linked packages at `0.3.0`: AgentSkill `capability.json`, Harness `capability.json`, AgentSkill `linkedHarness.version`, and Harness `harness.json`. Regenerate `harness.json` from canonical command contracts; do not hand-edit divergent schemas.

For every added command:

- use `kind: openclaw.harness.v1`, `schemaVersion: 1`;
- closed `inputSchema` with `additionalProperties: false`;
- only Gateway-supported schema keywords and arg-map types;
- typed path fields with correct `pathRole`; never pass a root/path in free-form body when a typed path exists;
- stable existing output envelope;
- safety classes from the table above, with no invented class names;
- `baseArgv` equal to the canonical dotted command.

The installed OpenClaw Gateway parser is a release gate. Parse the complete generated manifest, not a reduced fixture. Record in release evidence:

- canonical source commit;
- package versions;
- command count (expected baseline 152 plus exactly the implemented additions);
- SHA-256 for both package metadata files, generated `harness.json`, `command_contracts.json`, entrypoint, and release archive;
- clean-tree commit containing generated artifacts.

A version or digest mismatch blocks publication.

## 10. Redaction requirements

Extend recursive redaction to keys and values representing `credentialRef`, resolved path, root, tokens, secrets, authorization, codes, verifier, raw/body/content, client configuration, provider response, and exception context. Alias is safe after validation; email is masked unless an existing authorized API result intentionally returns it. Audit records contain command, request ID, alias, input hash, safety classes, result code, and effect digest only. Debug mode may add check IDs and stack classification, never secret values or paths. Tests must seed canary secrets and assert their absence from stdout, stderr, audit, exceptions, previews, diagnostics, and temporary filenames.

## 11. Required implementation structure

Recommended modules, keeping transport behavior isolated:

- `google_workspace_core/bindings.py`: schema, secure path handling, lock, transactions, resolution;
- `google_workspace_core/migration.py`: bounded legacy discovery/import planning;
- `google_workspace_core/permissions.py`: checks and guarded repair;
- `google_workspace_core/high_level_reads.py`: convenience adapters;
- minimal integration changes in `core.py`, `auth.py`, `oauth_desktop.py`, CLI parser, contracts, and generated manifest.

Do not make registry code depend on provider network calls except explicit identity/smoke verification. Inject clock, filesystem boundary, lock, and transport in tests.

## 12. Acceptance test matrix

### Unit

1. Alias normalization and every invalid character/boundary case.
2. Schema parse, duplicate keys, unknown keys, revision increments, future schema rejection.
3. Root precedence and rejection of relative/package-contained roots.
4. Resolution precedence for every branch, explicit-invalid no-fallback, zero/one/many aliases.
5. Lock contention/timeout, concurrent rename/import/remove, lost-update prevention.
6. Atomic replace failures at create/write/fsync/replace/dir-fsync and crash orphan handling.
7. Symlink, hard-link where detectable, reparse point, traversal, TOCTOU/inode-swap, cross-device rejection.
8. Login staging/commit/cancel/overwrite/smoke-failure cleanup.
9. Import copy/reference, multi-account source alias, duplicate subject, collision behavior.
10. Migration preview/apply/idempotence/conflicts/no automatic deletion.
11. Permission checks and repairs, owner mismatch, external reference refusal, platform ACL adapters.
12. Every diagnostic code, retryability, remediation, and stable envelope.
13. Gmail/Calendar/Drive high-level request mapping, narrow defaults, pagination and truncation.
14. Recursive redaction with canary secrets in keys, values, nested lists, provider errors, and paths.
15. Existing `CredentialProvider`, explicit path, account environment selector, previews, and mutations unchanged.

### Integration

1. Fresh pod root, login mocked at OAuth boundary, bind, status, and each high-level read.
2. Two independent pod roots with the same alias resolve different fixtures, proving no `agentId` and no cross-pod leakage.
3. Two concurrent processes mutate one root without corruption.
4. Import a representative 0.2.6 single- and multi-account bundle, then perform mocked Gmail, Calendar, and Drive reads.
5. Upgrade simulation replaces package directory and proves root registry/credential hashes unchanged.
6. Roll back executable to 0.2.6 and prove explicit credential-path access remains possible.
7. Registry metadata backup/restore with valid and missing references.
8. Full 152-command baseline regression plus all new commands.
9. Generated manifest parses through the installed live Gateway parser and repository schema tests.
10. Unix tests plus Windows/macOS ACL/path adapter tests in CI where runners exist.

### Security/adversarial

1. World/group-readable root, registry, and credential files fail closed before token read.
2. Malicious aliases, JSON duplicate keys, oversized registry, deep nesting, Unicode confusables, control bytes.
3. Symlink races at every path component and replacement between check/open/commit.
4. Lock-file substitution, stale lock, denial-of-service timeout, and concurrent crash recovery.
5. Crafted external references into package/system/other-user paths.
6. Canary access/refresh/client secrets and filesystem paths absent from every output channel and artifact.
7. Corrupt/hostile credential JSON never appears in diagnostics.
8. Unauthorized permission repair cannot chown, escape root, follow links, or broaden ACLs.
9. Update/uninstall simulation cannot erase or traverse the protected root.
10. Fuzz registry parser, alias parser, resolution, redactor, and migration candidate parser.

Release passes only with all baseline and new tests green, zero real credential use, live Gateway parse success, clean generated diff, and an independent publication validator confirming versions and digests.

## 13. Source evidence

Evidence was inspected read-only from canonical commit `a9e92867264b2527965d51ff285b161d307eb223` and installed/local 0.2.6 artifacts:

- `harnesses/google-workspace/capability.json`: version `0.2.6`, OpenClaw `>=2026.4.0`, credential-related approval boundary.
- `skills/google-workspace/capability.json`: version `0.2.6`, linked Harness `0.2.6`.
- `harnesses/google-workspace/harness.json`: Harness v1, OAuth human-account model, typed `credentialPath`, 152 declared commands, current Gateway-compatible safety classes.
- `harnesses/google-workspace/google_workspace.py`: explicit `--account` and `--credential-path` parsing.
- `google_workspace_core/core.py`: current account precedence is explicit account then `GOOGLE_WORKSPACE_ACCOUNT`; `CredentialProvider` receives the typed path; stable envelope and confirmation controls already exist.
- `google_workspace_core/auth.py`: bundles map aliases under `accounts`; credential files must be regular, non-symlink, and mode 0600; provider refresh errors are sanitized.
- `google_workspace_core/state.py`: existing lock-backed state, same-directory temporary write, chmod 0600, and atomic replace establish a reusable pattern, but binding durability additionally requires fsync, revisioning, protected-root checks, and crash tests.
- `google_workspace_core/security.py`: existing path containment and secret-key redaction provide a base that must be extended for binding metadata/path diagnostics.
- `docs/google-workspace-contract.md`: stable JSON, account ambiguity, typed credential injection, desktop-local login, read commands, safety and redaction contract.
- Installed/local package metadata observed at `0.2.6`; protected credential material was not opened, copied, invoked, or modified for this specification.
