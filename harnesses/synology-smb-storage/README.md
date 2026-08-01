# Synology SMB Storage Harness

Run `./synology_smb_storage.py --help`. Requires Linux, `smbclient` with `SMB3_11`, `mount.cifs` with `vers=3.1.1`, and mount privilege or `CAP_SYS_ADMIN`.

The Harness accepts an approved protected password through `SYNOLOGY_SMB_PASSWORD` or Harness stdin. Backend tools receive it only through `PASSWD`, with stdin disabled and backend diagnostics suppressed. It never stores credentials.

File get/put defaults to 16 MiB and is capped at 64 MiB. Put requires an explicit absolute `--transfer-root` plus a relative `--source`; traversal and symlinks are rejected.
