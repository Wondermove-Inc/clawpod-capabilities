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

## Registry Entry

Add one entry to `registry/index.json` with:

- `id`
- `type`: `skill` or `harness`
- semantic `version`
- concise `description`
- repository-relative package `path`
- `compatibility`
- `safety`

Run:

```bash
python3 scripts/validate.py
```

The pull request must pass repository validation before merge.
