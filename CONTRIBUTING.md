# Contributing

## General Rules

- Reuse or improve an existing capability before creating a duplicate.
- Keep names lowercase and hyphenated.
- Keep package instructions concise and operational.
- Never commit plaintext secrets, credentials, private endpoints, or customer data.
- Submit changes through pull requests after the initial repository bootstrap.

External contributions are welcome. Pull requests from contributors without
repository access may remain open for review, but only repository administrators
may merge pull requests. Merge authority is enforced through repository branch
protection, not by automatically closing pull requests based on their author.

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
- `descriptionI18n.ko`: a Korean translation of the effective English description
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

### Localized descriptions

Keep `description` in English. For Skills with
`descriptionSource: "skill-frontmatter"`, the effective English description comes
from `SKILL.md`; otherwise it comes from `capability.json`. Write its Korean
translation in `capability.json` as `"descriptionI18n": {"ko": "한국어 설명..."}`.
Preserve scope, prerequisites, safety qualifications, and routing exclusions in
the translation. Review the Korean text whenever the English source changes.

Do not author `descriptionI18n.en` in package metadata: the generator copies the
effective English description into both Registry `description` and
`descriptionI18n.en`. Every generated entry includes `en` and `ko`. Translations
must be 10–500 characters with no surrounding whitespace. Other language keys
require an explicit schema and validator extension. CI rejects missing or invalid
translations and mismatched generated English descriptions; translation accuracy
still requires review.

The v1 schemas and generator accept historical entries without localization for
backward compatibility. The repository coverage test requires Korean metadata
and both generated languages for every current package, including newly added
packages.

Metadata-only translations do not change installed package files or their
digests. Bump package versions when distributable files change, and update exact
`linkedHarness` versions when releasing a changed Harness.

### Generator format changes

The `registry-sync` workflow deliberately uses the generator on `main`, not the
PR's generator. When extending package metadata, first merge backward-compatible
generator support, then add metadata using the new format in a follow-up PR.
The support change must preserve existing index output until the new metadata is
present. Do not switch the write-enabled workflow to executing a candidate
generator to bypass this ordering. Strict frontend schema consumers must also
accept new fields before an index containing them is published.
