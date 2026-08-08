# Tests

Run `python3 -m pytest -q harnesses/synology-smb-storage/tests`. Tests use isolated temporary paths and mocked SMB/mount backends; no NAS credentials or live mounts are used.

## Mounted-filesystem-only refinement (0.1.3)

Version 0.1.3 removes the Harness file commands. Ordinary copy, move, read, write, and listing are OS filesystem operations permitted only after exact `/workspace/shared` mount target, CIFS type, and approved source verification.

Release verification covers absence from the manifest, command contracts, parser, command discovery, and Skill guidance, plus registry installation and validation. A real Gateway installation/trust and `harness.run.prepare → harness.run` lifecycle remains a release-environment check and is not performed by these offline tests.
