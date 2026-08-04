# Tests

Run `python3 -m pytest -q harnesses/synology-smb-storage/tests`. Tests use isolated temporary paths and mocked SMB/mount backends; no NAS credentials or live mounts are used.

## Gateway schema compatibility recovery (0.1.2)

Version 0.1.1 reproduced a `harness.run.prepare` rejection for `file.get.maxBytes` and `file.put.maxBytes` because their input schemas used unsupported `minimum` and `maximum` keywords. Version 0.1.2 removes only those manifest constraints. Runtime validation remains authoritative and enforces 1 byte through 64 MiB for both commands.

Release verification covers the supported Gateway input-schema keyword subset, below-minimum and above-maximum runtime failures, registry installation, and a local installed-manifest prepare-to-subprocess-run exercise. A real Gateway installation/trust and `harness.run.prepare → harness.run` lifecycle remains a release-environment check and is not performed by these offline tests.
