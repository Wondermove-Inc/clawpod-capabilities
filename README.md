<div align="center">

# ClawPod Capabilities

**The canonical public registry for reusable AgentSkills and trusted CLI Harnesses.**

[![Registry validation](https://github.com/Wondermove-Inc/clawpod-capabilities/actions/workflows/validate.yml/badge.svg)](https://github.com/Wondermove-Inc/clawpod-capabilities/actions/workflows/validate.yml)
![Public registry](https://img.shields.io/badge/registry-public-2ea44f)
![Integrity](https://img.shields.io/badge/integrity-SHA--256-blue)

[Quick start](#quick-start-for-agents) · [Bootstrap pair](#bootstrap-pair) · [Harness commands](#harness-commands) · [Contributing](#contributing) · [Security](#security)

</div>

---

## Quick start for agents

> [!IMPORTANT]
> If a user gives you only this repository URL, bootstrap capability management from **this canonical repository** before doing anything else. Do not substitute a mirror.

### 1. Acquire and verify

```bash
git clone https://github.com/Wondermove-Inc/clawpod-capabilities.git
cd clawpod-capabilities
python3 scripts/validate.py
```

Continue only when validation succeeds.

### 2. Choose managed installation roots

Use the current agent's managed Skill and CLI Harness directories. Do not guess shared or system-wide paths.

```bash
python3 scripts/bootstrap.py \
  --skills-root <agent-workspace>/skills \
  --harnesses-root <agent-workspace>/harnesses \
  --dry-run
```

Review the dry-run output and confirm both destinations.

### 3. Install the bootstrap pair

```bash
python3 scripts/bootstrap.py \
  --skills-root <agent-workspace>/skills \
  --harnesses-root <agent-workspace>/harnesses
```

The dependency-free bootstrap verifies every declared SHA-256 digest, rejects path traversal, and does not require credentials.

> [!CAUTION]
> If a different installation already exists, stop and inspect it. Use `--force` only with approval. Replaced content is backed up under `.clawpod-bootstrap-backups/`.

### 4. Register, trust, and smoke-test

1. Register or reload the AgentSkill through the runtime's approved Skill lifecycle.
2. Validate and trust the CLI Harness through the runtime's approved Harness lifecycle.
3. Run the read-only `list` or `search` command.

Once active, use the shared machine name **`clawpod-capability-registry`** for both Skill routing and Harness execution. The identity is unambiguous because AgentSkills and CLI Harnesses use separate capability types and installation namespaces.

---

## Bootstrap pair

| Capability | Responsibility | Source |
|---|---|---|
| **AgentSkill** | Decides when and how to discover, install, validate, update, or roll back capabilities | [`skills/clawpod-capability-registry/SKILL.md`](skills/clawpod-capability-registry/SKILL.md) |
| **CLI Harness** | Performs deterministic registry operations with structured JSON output | [`harnesses/clawpod-capability-registry/harness.json`](harnesses/clawpod-capability-registry/harness.json) |
| **Registry index** | Declares typed packages, compatibility, safety metadata, files, and digests | [`registry/index.json`](registry/index.json) |

```text
User intent
    ↓
ClawPod Capability Registry Skill
    ↓
ClawPod Capability Registry CLI Harness
    ↓
Canonical registry + verified local installation
```

## Harness commands

| Command | Purpose |
|---|---|
| `list` | List registered capabilities |
| `search` | Search IDs and descriptions |
| `inspect` | Inspect compatibility and safety metadata |
| `install` | Install verified files into an explicit target root |
| `validate` | Compare installed files with registry digests |
| `update` | Back up and replace an installation |
| `rollback` | Restore a previous local backup |

All commands emit machine-readable JSON. Network reads are restricted to this canonical public repository.

## Repository layout

```text
skills/<name>/             AgentSkill packages
harnesses/<name>/          CLI Harness packages
registry/index.json        Machine-readable capability index
schemas/                   Registry contracts
scripts/bootstrap.py       Dependency-free first-install path
scripts/validate.py        Repository validation
tests/                     Repository policy and bootstrap tests
```

## Choosing a capability type

| Use | When |
|---|---|
| **AgentSkill** | The work needs judgment, routing, domain knowledge, or a reusable variable procedure |
| **CLI Harness** | Execution must be deterministic, typed, structured, and machine-verifiable |
| **Both** | A Skill should select the operation and a Harness should execute it |

Always discover and improve an existing capability before creating a duplicate.

## Safety boundary

Installing or trusting a capability does **not** authorize:

- credential or secret use,
- production-impacting changes,
- external publication,
- destructive or irreversible actions,
- privilege expansion.

Those actions remain subject to their normal runtime controls and approval boundaries.

## Contributing

This registry accepts pull requests only from authorized organization members and collaborators.

1. Add or update one package under `skills/` or `harnesses/`.
2. Update `registry/index.json`, including per-file SHA-256 digests.
3. Run repository and package tests.
4. Submit a pull request and wait for required CI and repository policy checks.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the complete contract.

## Security

Never publish credentials, internal endpoints, customer data, private configuration, or generated secret material. Report vulnerabilities according to [`SECURITY.md`](SECURITY.md).

## License

No license has been selected yet. Until one is added, copyright remains with the repository owner and reuse is not granted beyond applicable law.
