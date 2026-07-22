# ClawPod Capabilities

Public registry of reusable AgentSkills and trusted CLI Harnesses for ClawPod-Agent.

## Repository Layout

```text
skills/<name>/          AgentSkill packages
harnesses/<name>/       CLI Harness packages
registry/index.json     Machine-readable capability index
schemas/                Registry and package contracts
scripts/validate.py     Repository validation
```

## Capability Types

- **AgentSkill:** reusable judgment, routing, domain knowledge, or a multi-step procedure.
- **CLI Harness:** deterministic, machine-verifiable execution with explicit arguments, output, safety, and failure behavior.

Use both when a Skill should select an operation and a Harness should execute it.

## Consumer Workflow

1. Read `registry/index.json`.
2. Select a compatible capability by `id`, `type`, and `version`.
3. Download the package from its declared `path`.
4. Verify the package digest when one is declared.
5. Follow the package's installation and validation instructions.
6. Treat installation and risky invocation as separate approval decisions.

## Contributor Workflow

1. Add or update one package under `skills/` or `harnesses/`.
2. Update `registry/index.json`.
3. Run `python3 scripts/validate.py`.
4. Submit a pull request and wait for CI validation.

See [CONTRIBUTING.md](CONTRIBUTING.md) for package requirements.

## Security

Never publish credentials, internal endpoints, customer data, private configuration, or generated secret material. See [SECURITY.md](SECURITY.md).

## License

No license has been selected yet. Until one is added, copyright remains with the repository owner and reuse is not granted beyond applicable law.
