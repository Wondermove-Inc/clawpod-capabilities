# GitHub capability contract

The canonical pair shares machine name `github` and title **GitHub**. The Skill routes intent; the Harness deterministically wraps bounded `gh` argv.

The pair is one transactional installation unit. A Skill declares `linkedHarness: github`; registry install, update, and validation require explicit Skill and Harness roots, type-disambiguated selection, digest verification of both packages, and rollback on partial failure.

Version 0.1 requires a pre-authenticated system `gh` CLI. It does not claim agent-complete login. `auth.status` performs only a bounded user GET for an exact validated host and emits allowlisted identity fields. Authorization and every external mutation remain separately approval-gated.

Runtime manifest numeric schemas use `number` for Gateway compatibility. Package-local contracts retain `integer`. No arbitrary mutation API passthrough is exposed. Output, input sizes, timeouts, retries, IDs, states, endpoints, and uploads are bounded. Mutation backend failures are non-retryable and marked potentially ambiguous.
