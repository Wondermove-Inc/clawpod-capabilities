# Common Rules

Use for every Salesforce development, review, or org-change task.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-CMN-001` | MUST | Verify target Salesforce org identity at work start and immediately before any mutation; pin Salesforce CLI commands with an explicit target org. |
| `DR-CMN-002` | MUST | Pass check-only or dry-run validation before actual deployment when deployment is in scope. |
| `DR-CMN-003` | MUST | Do not treat deployment success as completion; verify permissions, UI/runtime surface, and data result when applicable. |
| `DR-CMN-004` | MUST | Do not mix unrelated change units; keep new work, corrections, deployment, activation, endpoint, and cleanup boundaries separate. |
| `DR-CMN-005` | MUST | Run relevant static analysis before deployment when the surface supports it; record tool version/provenance. |
| `DR-CMN-006` | SHOULD | Evaluate Configuration before Flow before Apex unless the approved request or defect evidence requires a lower layer. |
| `DR-CMN-007` | MUST | Preserve raw command output or equivalent machine-readable evidence; prose summaries are not enough. |
| `DR-CMN-008` | MUST | Mark facts as `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`. |
| `DR-CMN-009` | MUST NOT | Do not send secrets, private customer data, or sensitive Salesforce record content to external systems unless explicitly approved and minimized. |
| `DR-CMN-010` | MUST | Capture before-state evidence before mutation and comparable after-state evidence after mutation. |
| `DR-CMN-011` | MUST | Tie org-changing work to an approved request record and preserve correction/completion communication evidence. |
| `DR-CMN-012` | MUST | Before using unfamiliar CLI flags, API features, or platform behavior, check the official reference and record the citation. |
| `DR-CMN-013` | MUST | When building deploy input, include required source-format file pairs and verify the dry-run component list matches intended scope. |
| `DR-CMN-014` | MUST | Attribute each actual deployment result by explicit deploy ID substitution — `sf project deploy report --job-id <DEPLOY_ID>` plus a `DeployRequest` cross-query, stored as evidence; never use `--use-most-recent` (parallel-deploy misattribution risk). |
