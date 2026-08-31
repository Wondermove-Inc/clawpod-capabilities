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
registry/index.json        Generated machine-readable capability index
schemas/                   Registry and package metadata contracts
scripts/sync_registry.py    Deterministic Registry generator
scripts/bootstrap.py       Dependency-free first-install path
scripts/validate.py        Repository validation
tests/                     Registry, policy, and bootstrap tests
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
2. Add or update its package-local `capability.json` metadata.
3. Run `python3 scripts/sync_registry.py` locally if you want to preview the generated Registry.
4. Run repository and package tests.
5. Submit a pull request. GitHub automatically regenerates `registry/index.json`, and required CI blocks merge until it matches the package folders.

Do not edit `registry/index.json` by hand. Package folders and their `capability.json` files are the source of truth.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the complete contract.

## Security

Never publish credentials, internal endpoints, customer data, private configuration, or generated secret material. Report vulnerabilities according to [`SECURITY.md`](SECURITY.md).

## License

No license has been selected yet. Until one is added, copyright remains with the repository owner and reuse is not granted beyond applicable law.

### ClawPod OCR 0.3.4

ClawPod OCR produces local enterprise `.docx` comparison reports for one or multiple completed OCR jobs. Reports preserve and distinguish raw OCR from separately corrected text and include source imagery, QA metadata, document controls, and file-specific sections.

### ClawPod Image Studio 0.4.3

ClawPod Image Studio now includes an additive, offline professional production
slice: revisioned projects and briefs, strict shot compilation, content-addressed
candidate lineage, deterministic QA and critic inputs, human selections,
non-destructive master records, deterministic contact sheets, and reproducible
delivery manifests/packages. Its existing protected-secret and exact paid-intent
provider boundary remains unchanged; Studio registration commands never call a
provider.

### Memory Graph 0.11.4

Memory Graph is a paired Skill and Harness for autonomous, per-agent onboarding of a private, rebuildable Memory MCP graph from the exact recognized core workspace allowlist and canonical memory. Version 0.11.0 adds complete lifecycle-aware extractor paging, external-agent natural-language candidate authoring, explicit-evidence-only Person/Project/Decision/Cause/Effect/Event causal graphs, bounded review pages, hydrated decision recall, and full offline semantic HTML. The Harness itself never calls a model, network, MCP, or live graph mutation surface.

### Artifact Design 0.1.0

Artifact Design is a prose-only Skill that decides when a reply's output deserves to be a ClawPod room artifact, designs it for the actual rendering surface (a 320–670 px panel; HTML in a script-less sandboxed iframe with OS-level dark mode and the portal's CSP; markdown in the portal's themed renderer with mermaid), and publishes it through the verified save-then-`artifact_refs` contract (`POST /internal/chat-rooms/:roomId/artifacts` → `POST /internal/messages`, `markdown` or `html`, at most 5 per message, 200,000 characters each, `expectedVersion` CAS). It replaces the standalone `diagram-design` package; diagram pages are one of the artifact shapes it produces.

### Ops Troubleshooting 0.1.0

Ops Troubleshooting is a paired Skill and Harness for infrastructure and security-hygiene problem solving. The Skill supplies the method (intake, hypothesis tree, evidence rules, mitigate-vs-fix) and five playbooks (host, network, Kubernetes, security hygiene, change/config). The Harness supplies 24 bounded, read-only diagnostics over `/proc`, systemd, journald, iproute2, sockets/TLS, `kubectl`, and package managers — every response records the exact commands executed — plus `remediate.plan` → `remediate.apply` for three allowlisted actions (service restart, rollout restart, managed-pod delete) that run once, only against an approved, unexpired, precondition-bound plan. Compromise signals hand off to `soc-event-correlation`; reporting routes through `clawpod-org-operations`.

### Claude Design 0.4.1

Claude Design 0.4.0 makes the **verified project link** the deliverable: `projects.link.verify` checks the exact project/file route and slide count and renders a Korean/English handoff card so the user exports PPTX/PDF themselves in seconds, while agent-driven native export becomes an explicit opt-in (room artifacts cannot carry binaries). It also adds a deterministic layout quality gate, `projects.qa.layout`, that evaluates per-slide geometry captured from the canvas — text overflow, text escaping shapes, overlaps, off-canvas elements, near-miss alignment, uneven spacing, font floor, density, inconsistent diagram shapes, title drift — and returns a `revision_prompt` for a bounded revise loop through `projects.iterate`, alongside content and structure rubrics (one message per slide, layout family, diagram grammar, text budgets).

### Open Design 0.1.0

Open Design is a paired Skill and Harness that connects agents to a self-hosted OpenDesign server. Onboarding takes the server's Base URL and API token (token only through the Gateway-injected `OPEN_DESIGN_API_TOKEN` environment; never argv, state, or logs) and is `verified` only after a read plus a scratch write round-trip. The 16-command Harness covers health with a real auth-enforcement probe, project/file lifecycle with byte-identical upload verification, scoped preview links that open without the API token, HTML/ZIP export, and Claude Design `.zip` import — validated live against OpenDesign v0.20.3 (contract in `docs/open-design-contract.md`). The agent authors the HTML itself (artifact-design craft, claude-design layout gate) and delivers the preview link first.
