# ClawPod Capabilities

Canonical public registry of reusable AgentSkills and trusted CLI Harnesses for all ClawPod agents.

## Start Here, Agents

If a user gives you only this repository URL, bootstrap capability management before doing anything else:

```text
https://github.com/Wondermove-Inc/clawpod-capabilities
```

### 1. Acquire only this repository

```bash
git clone https://github.com/Wondermove-Inc/clawpod-capabilities.git
cd clawpod-capabilities
```

Do not substitute another repository or mirror.

### 2. Inspect the bootstrap pair

- AgentSkill: [`skills/clawpod-capability-registry/SKILL.md`](skills/clawpod-capability-registry/SKILL.md)
- CLI Harness: [`harnesses/clawpod-capability-registry/harness.json`](harnesses/clawpod-capability-registry/harness.json)
- Registry: [`registry/index.json`](registry/index.json)

The Skill decides when and how to manage capabilities. The Harness performs deterministic registry search, verified installation, validation, update, backup, and rollback.

### 3. Verify the repository

```bash
python3 scripts/validate.py
```

Continue only when validation succeeds.

### 4. Preview bootstrap installation

Choose the current agent's managed Skill and CLI Harness roots. Do not guess shared or system-wide paths.

```bash
python3 scripts/bootstrap.py \
  --skills-root <agent-workspace>/skills \
  --harnesses-root <agent-workspace>/harnesses \
  --dry-run
```

The bootstrap script is dependency-free, verifies every declared SHA-256 digest, rejects path traversal, and never uses credentials.

### 5. Install the bootstrap pair

After confirming the destinations:

```bash
python3 scripts/bootstrap.py \
  --skills-root <agent-workspace>/skills \
  --harnesses-root <agent-workspace>/harnesses
```

If a differing installation already exists, stop and inspect it. Use `--force` only with approval; the script backs up replaced content under `.clawpod-bootstrap-backups/`.

### 6. Register and validate through the agent runtime

- Reload or register the installed AgentSkill through the runtime's approved Skill lifecycle.
- Validate and trust the CLI Harness through the runtime's approved Harness lifecycle.
- Run a read-only `list` or `search` command as the smoke test.
- Do not treat installation as authorization for credential use, production impact, external publication, or destructive actions.

Once the pair is active, use `clawpod-capability-registry` for both Skill routing and Harness execution. The shared machine name is safe because Skills and CLI Harnesses are separate capability types and installation namespaces.

## CLI Harness Commands

```text
list       List registered capabilities
search     Search ids and descriptions
inspect    Inspect compatibility and safety metadata
install    Install verified files into an explicit target root
validate   Check installed files against registry digests
update     Replace an installation after creating a backup
rollback   Restore a previous local backup
```

All Harness commands emit machine-readable JSON. Network reads are restricted to the canonical public repository.

## Repository Layout

```text
skills/<name>/             AgentSkill packages
harnesses/<name>/          CLI Harness packages
registry/index.json        Machine-readable capability index
schemas/                   Registry contracts
scripts/bootstrap.py       Dependency-free first-install path
scripts/validate.py        Repository validation
```

## Capability Selection

- Use an **AgentSkill** for reusable judgment, routing, domain knowledge, or a variable procedure.
- Use a **CLI Harness** for deterministic execution with typed inputs, stable output, explicit safety classes, and machine-verifiable failure behavior.
- Use both when a Skill should select an operation and a Harness should execute it.

Always discover and improve an existing capability before creating a duplicate.

## Contributing

1. Add or update one package under `skills/` or `harnesses/`.
2. Update `registry/index.json`, including per-file SHA-256 digests.
3. Run repository and package tests.
4. Submit a pull request and wait for required CI and review.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Never publish credentials, internal endpoints, customer data, private configuration, or generated secret material. See [SECURITY.md](SECURITY.md).

## License

No license has been selected yet. Until one is added, copyright remains with the repository owner and reuse is not granted beyond applicable law.
