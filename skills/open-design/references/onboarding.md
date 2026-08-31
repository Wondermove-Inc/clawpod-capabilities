# Onboarding script

Say, in the user's language: the capability is **installed but not connected**, and you need three things — the **agent-API Base URL** (may include a proxy prefix, e.g. `https://od.wondermove.local/agent-api`), the **web URL humans open** (e.g. `https://od.wondermove.local`; omit to derive it from the Base URL's origin), and the **API token** (`OD_API_TOKEN` value).

- The token goes into the Gateway secret lane bound to `OPEN_DESIGN_API_TOKEN`. If the user pastes it in chat, store it via the secret lane and do not repeat it back.
- Internal servers usually have private/self-signed certificates: pass `--ca-cert-path` when a CA file exists, otherwise `--insecure-tls-risk-accepted` — a supported everyday configuration for internal deployments.

Then, with an owner-only state root (0700):

```
open-design config.set --state-root <root> --base-url <api url> [--web-base-url <web url>] [--ca-cert-path <pem> | --insecure-tls-risk-accepted]
open-design health --state-root <root>
```

Read the `health` findings out loud:
- `AUTH_NOT_ENFORCED` — the daemon accepted a wrong token: anyone who can reach the server can use it. The fix is on the server (`OD_API_TOKEN` env on the daemon), not in this capability. Report it; continue onboarding.
- `TOKEN_ABSENT` — the secret is not injected; fix the secret binding before writes.
- `UNVERIFIED_SERVER_VERSION` — the server moved off the verified 0.20.x series; the contract may have drifted.

`verified` requires, in one session: `projects.list` succeeding, then a scratch write round-trip —

```
open-design projects.create --state-root <root> --name "onboarding-smoke-delete-me" --kind deck
open-design files.put --state-root <root> --project-id <id> --path <small local html>   # roundTripVerified must be true
open-design projects.delete --state-root <root> --project-id <id> --exact-name "onboarding-smoke-delete-me" --approve
```

Report exactly what was created and that it was deleted. Only then state the capability is ready. If the user defers, say "resume Open Design onboarding" resumes here, and do not claim readiness meanwhile.
