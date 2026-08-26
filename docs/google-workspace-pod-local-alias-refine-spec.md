# Google Workspace pod-local alias contract

Google Workspace keeps alias metadata in a pod-local binding registry and OAuth authentication material in referenced JSON files. Runtime readiness is based on whether the selected authentication file exists and parses successfully. Filesystem mode, UID, GID, ownership, symlink, and link-count metadata are not authentication gates.

## Layout and transactions

The binding root contains `bindings.v1.json`, `bindings.v1.lock`, `credentials/`, and `backups/`. New files may use private creation defaults, but existing artifacts are accepted regardless of filesystem permission metadata. Registry JSON validation, alias normalization, bounded file-size checks, advisory locking, revisions, atomic replacement, bounded backups, rollback, secret redaction, and package-tree/staging root exclusions remain enforced.

## Commands

`auth.bindings.list`, `status`, and `resolve` return sanitized metadata. `import`, `rename`, `remove`, and `migrate` retain preview/confirmation controls. The former binding permission check and repair commands are retired because permission metadata is no longer part of authentication readiness.

## OAuth file gate

`auth.login` requires the supplied OAuth client file to exist, remain beneath the selected transfer root, and parse as an installed/Desktop Google OAuth client. Existing credential bundles likewise need only exist and parse. Authentication behavior, endpoint allowlisting, PKCE/state validation, scope checks, bounded reads, atomic writes, provider error sanitization, and secret redaction are unchanged.

## Regression expectations

Tests cover absent files, malformed JSON, valid files with non-private modes, linked files, alias lifecycle, transaction failures, parsing, authentication, and redaction. Permission/mode/UID/GID/link status and repair contracts must not reappear.
