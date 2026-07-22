# Contributing

## General Rules

- Reuse or improve an existing capability before creating a duplicate.
- Keep names lowercase and hyphenated.
- Keep package instructions concise and operational.
- Never commit plaintext secrets, credentials, private endpoints, or customer data.
- Submit changes through pull requests after the initial repository bootstrap.

## AgentSkill Package

Place each Skill under `skills/<name>/`.

Required:

- `SKILL.md` with valid frontmatter containing `name` and a concrete routing `description`.
- Instructions that state prerequisites, procedure, approval boundaries, verification, and failure handling.
- Every referenced support file must exist.

Use `references/`, `scripts/`, `assets/`, or `examples/` only when they materially improve reuse.

## CLI Harness Package

Place each Harness under `harnesses/<name>/`.

Required:

- `harness.json` with command, argument, output, and safety contracts.
- An executable entrypoint.
- Stable machine-readable JSON output.
- Tests for success, invalid input, backend failure, timeout, and approval behavior where applicable.
- No embedded credentials.

## Package Metadata and Registry Generation

Every package must include `capability.json` beside `SKILL.md` or `harness.json` with:

- `schemaVersion`
- semantic `version`
- concise Registry `description`
- `compatibility`
- `safety`

Do not edit `registry/index.json` by hand. The package folders and their metadata are the source of truth. Generate the Registry locally with:

```bash
python3 scripts/sync_registry.py
```

Check that the committed Registry is current with:

```bash
python3 scripts/sync_registry.py --check
python3 scripts/validate.py
```

For authorized same-repository pull requests, GitHub automatically regenerates and commits `registry/index.json` when package files change. Required CI blocks merge until the generated Registry, package metadata, files, and SHA-256 digests agree.
