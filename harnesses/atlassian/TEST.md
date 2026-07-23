# OAuth onboarding test plan and results

No test uses a live credential or Atlassian account. Network fixtures bind only to loopback.

## Coverage

- private path, mode, redirect, and managed-CDP validation
- required `read:space:confluence` grant
- the complete live 11-scope consent rendering map, including intentionally hidden `offline_access`, exact-token `me`, abbreviated Jira categories, classic Confluence, granular Confluence, unmapped scopes, and missing tokens
- synthetic-DOM execution through the real Node helper: login wait, preselected plain-text site, native select, Atlaskit combobox/listbox, wrong/ambiguous site rejection, realistic captured consent text, rendered-scope verification, and autonomous Accept
- duplicate accessible-resource rows coalesced by cloud ID with scope union
- explicit cloud-ID and exact normalized-URL selection among multiple resources
- ambiguity, wrong resource, and callback-state failure
- short-return detached `auth.oauth.start` and subprocess `auth.oauth.job.status`
- full detached worker completion against loopback fake OAuth, accessible-resource, identity, Jira, and Confluence endpoints
- `pending-login`, `pending-consent`, `completed`, `failed`, and stale transitions
- concurrent output-path ownership, bounded stale-job failure, mode-0600 files, cleanup, and secret absence from argv, stdout, stderr, status, and job artifacts

## Verified results

- `python3 -m unittest -v`: 18 tests passed
- `node --check oauth_cdp.js`: passed
- `python3 -m py_compile atlassian.py oauth3lo.py`: passed
- `git diff --check`: passed

The synthetic-DOM mode is enabled only by an explicit test environment flag. It receives OAuth request material through stdin, never argv or environment. The worker test provider is required to be loopback HTTP.
