# Synology SMB Storage Harness

Run `./synology_smb_storage.py --help`. Requires Linux, `smbclient` with `SMB3_11`, `mount.cifs` with `vers=3.1.1`, and mount privilege or `CAP_SYS_ADMIN`.

The Harness accepts an approved protected password through `SYNOLOGY_SMB_PASSWORD` or Harness stdin. Backend tools receive it only through `PASSWD`, with stdin disabled and backend diagnostics suppressed. It never stores credentials.

`mount.restore --server SERVER --account ACCOUNT --share SHARE` is the manual, idempotent recovery command. It no-ops on the exact existing mount without requiring a password; otherwise it checks bounded local prerequisites, requires `SYNOLOGY_SMB_PASSWORD`, uses the fixed target and safe SMB 3.1.1 options, and verifies the result.

File get/put defaults to 16 MiB and is capped at 64 MiB. Put requires an explicit absolute `--transfer-root` plus a relative `--source`; traversal and symlinks are rejected.
