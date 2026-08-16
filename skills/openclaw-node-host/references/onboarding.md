# Progressive onboarding

Advance one state at a time. Persist only the state name and redacted facts so a later turn resumes at the first unmet gate. Ask one question or action per turn, never a checklist.

| State | Automatic work | User-facing gate |
|---|---|---|
| `platform` | None | Ask only whether the computer is Mac or Windows 11. |
| `transport` | Check whether the target is already a connected node and inspect available protected bootstrap methods. | If remote bootstrap is needed, ask which existing method to use: macOS Remote Login/OpenSSH, Windows OpenSSH Server, Tailscale SSH, or a local command the user runs. Explain only the selected method's next action. |
| `credentials` | Prefer key-based SSH or Tailscale SSH and search protected credential storage. | If a credential is missing, ask the user to store it through the protected secret channel. Never request or accept a password or private key in chat, argv, logs, or plans. |
| `inspect` | Through the selected bootstrap transport, inspect OS, Node.js, exact package version, Tailscale readiness, service, and prior state without mutation. | Surface exactly one blocker action only when inspection cannot proceed. Tailscale remains user-managed and verification-only. |
| `plan` | Build a fresh target-bound plan with redacted effects and rollback. | Ask one simple approval describing the exact ClawPod-visible mutation. Bind it to the plan; changed target, transport, endpoint, version, or evidence requires replanning. |
| `apply` | Execute only through the approved bootstrap transport, verify each postcondition, and record the first unmet one for resume. | Ask only for an unavoidable local OS consent prompt, such as a macOS privacy permission. Never mutate another external node as an execution shortcut. |
| `pair` | Re-list requests and internally match one exact request ID to the expected fingerprint. | Separately ask whether to approve the detected ClawPod node. Show identifiers only for ambiguity or safety. |
| `verify` | Validate service, Gateway connection, and requested system/browser capabilities. | If provisioning is correct but connection fails, hand redacted evidence to `node-connect`; otherwise ask one recovery action and resume at the first unmet state. |
| `complete` | Confirm no pending postcondition and retain rollback evidence. | Report the ClawPod node as connected and state the first useful next action, without implementation details. |

The bootstrap transport is only the pre-node installation path. It does not change the node-to-Gateway transport. Never enable Remote Login, OpenSSH Server, or Tailscale SSH automatically; if none is already available, offer the single local bootstrap command path.
