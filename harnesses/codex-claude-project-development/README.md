# Codex & Claude Project Development Harness

Version 0.2.4 is a standard-library, fail-closed continuity orchestrator using bundled ACPX named persistent sessions across OS processes. It binds project ids to canonical git root/cwd/branch/full HEAD and maintains separate Codex and Claude lineages, CAS revisions, leases, rotation, and close.

`session-run` validates and leases, preflights ACPX/version/session discovery, calls strict-JSON `sessions ensure --name`, calls a separate bounded named prompt with stdin, returns the assembled agent response, records only identifiers/completion metadata, and releases. It stores neither prompts, responses, nor raw protocol output. Claude credentials come only from the caller's approved `exec.useSecrets` lane. There is no Gateway callback or OpenClaw runtime change.
