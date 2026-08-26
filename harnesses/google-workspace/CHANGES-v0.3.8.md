# Google Workspace 0.3.8 detached OAuth login

- Adds short, typed `auth.login.start`, `status`, `finalize`, `cancel`, and `recover` commands.
- Moves browser consent and callback waiting to a detached worker with private pod-local state.
- Makes legacy non-preview `auth.login` fail fast with `LOGIN_DETACHED_REQUIRED`; preview remains available for replacement planning.
- Stages credentials privately and performs the sole binding mutation in locked, idempotent finalize.
- Bounds Gateway Harness execution to 10 seconds and documents disconnect/recovery behavior.
