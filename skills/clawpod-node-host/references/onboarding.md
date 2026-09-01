# Progressive onboarding

## Self-service enrollment (default)

The default track has five states and at most two user hand-offs:

| State | Automatic work | User-facing gate |
|---|---|---|
| `agent` | `agent status`; if not connected, `agent login` to obtain the sign-in link (the pod ships with Tailscale installed but signed out). Poll `agent status` until Running. | Once: send the login link and ask the user to sign in with the ClawPod Tailscale account. Skip entirely when already connected. |
| `platform` | None | Ask only whether the computer is Mac or Windows 11. |
| `handoff` | `enroll generate` with the agent's own Gateway endpoint; verify the returned script mentions no placeholder. | Send the complete script and say: run it, and sign in to Tailscale with the same account as ClawPod if asked. Nothing else. |
| `watch` | Poll `enroll status --node-id <id>` on a relaxed interval; `waiting_user` is normal, not an error. On the single match, `enroll approve` immediately without asking again. | None, unless the user reports an `ACTION:` line — then relay that one action and keep watching. |
| `verify` | `validate run --validation-level connection`, then report connected. | None. |

The script is idempotent: after any `ACTION:` stop (Tailscale install/login, Node.js install) the user simply re-runs it. Ambiguous or absent pairing matches fall back to `pairing status` / `pairing approve <exact-requestId>`.

## Agent-driven SSH provisioning (fallback)

Advance one state at a time. Persist only the state name and redacted facts so a later turn resumes at the first unmet gate. Ask one question or action per turn, never a checklist.

Supported paths are macOS Remote Login/OpenSSH, Windows OpenSSH Server, Tailscale SSH, and a local command. Password, key, SSH agent, and Tailscale SSH have no product-level preference.

| State | Automatic work | User-facing gate |
|---|---|---|
| `platform` | None | Ask only whether the computer is Mac or Windows 11. |
| `transport` | Run typed Tailscale install readiness, approved install, approved login initiation, login status, address, and same-tailnet verification **on the node only** (the agent already runs Tailscale on its tailnet — never reinstall, reconfigure, or log it out); join the node with MagicDNS/accept-dns disabled (`--accept-dns=false`), never enabling Tailscale DNS on the node. Then approved macOS Remote Login or Windows OpenSSH Server readiness with Tailscale-only scope. | Pause once at the browser login gate: give the user the Tailscale login link and ask them to sign in with the **same Tailscale account as ClawPod** (the agent). A different account fails `same-tailnet` — ask them to log out and re-login with the correct account. Then resume inspection. |
| `credentials` | Accept password, key, SSH agent, or Tailscale SSH without product-level preference. Ask the user to send the password/secret in chat; move it immediately into protected runtime injection and discard plaintext after capture. | Ask for any supported method and, for password, ask the user to send it in chat; the agent must not re-echo or persist secret material after capture. |
| `inspect` | Require a Tailscale IP, acquire the OpenSSH host key, compare its fingerprint to the locally displayed value, create an ephemeral mode-0600 known_hosts file, and run bounded noninteractive SSH. | Surface one classified blocker. Host-key mismatch always fails closed. |
| `plan` | Build a fresh target-bound plan with redacted effects and rollback. | Ask one simple approval describing the exact ClawPod-visible mutation. Bind it to the plan; changed target, transport, endpoint, version, or evidence requires replanning. |
| `apply` | Upload the deterministic script by content hash and execute it with noninteractive strict-host-key options, or generate the same credential-free script for the user to run locally. Persist completion of `preflight`, `upload`, `execute`, and `verify`; retry only the first incomplete idempotent stage. | Ask only for an unavoidable local OS consent prompt, such as a macOS privacy permission. For partial work, offer one retry action or guidance to remove installed user-scoped artifacts and revoke the bootstrap key/agent authorization. |
| `pair` | Re-list requests and internally match one exact request ID to the expected fingerprint. | Separately ask whether to approve the detected ClawPod node. Show identifiers only for ambiguity or safety. |
| `verify` | Validate service, Gateway connection, and requested system/browser capabilities. | If provisioning is correct but connection fails, hand redacted evidence to `node-connect`; otherwise ask one recovery action and resume at the first unmet state. |
| `complete` | Confirm no pending postcondition and retain rollback evidence. | Report the ClawPod node as connected and state the first useful next action, without implementation details. |

The local readiness script substantively enables the user-approved built-in Remote Login or OpenSSH Server path. This bootstrap does not change the node-to-Gateway transport. Remote execution is restricted to the Tailscale IP; it never falls back to public-internet, DNS, or generic LAN SSH, and resume always starts at the first unmet stage.

Store no password, private key, token, protected environment value, full account identity, or peer inventory. Persist only opaque reference kind, hashes, redacted facts, exact plan binding, and stage status. Never place secret plaintext in generated scripts, SSH argv, known-host arguments, command recordings, state, logs, plans, or JSON output.
