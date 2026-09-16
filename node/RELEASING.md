# Publishing ClawPod Node installers

This directory distributes installers built from the private Agent repository.
It does not rebuild the Agent or change its source. Node releases use their own
`node-vX.Y.Z` tags. Keep them separate from Skill/Harness versions and the bundled
Agent runtime version.

## Prepare

1. Update `release.json` with reviewed build metadata: exact installer version,
   target, filename, byte size, SHA-256, runtime version, and immutable release URL.
   `sourceCommit` describes the bundled Agent source, not wrapper provenance.
   `installerSourceCommit` identifies the Agent-repository commit containing the
   installer wrapper and setup app. The public release tag targets the reviewed
   capabilities-repository commit instead; these are separate histories.
   Record actual signing and native verification status; do not infer it from the
   presence of an installer.
2. Run `python3 node/prepare_release.py sync` to copy that manifest into the
   standalone `clawpod-node-host` Harness. Bump the capability version and linked
   Skill version for changed package contents, then regenerate the Registry.
3. Check both manifest copies and the original binary files:

   ```sh
   python3 node/prepare_release.py check --source /path/to/built/installers
   python3 scripts/sync_registry.py --check
   python3 scripts/validate.py
   python3 -m unittest discover -s tests -v
   ```

4. After tests and review, stage the files:

   ```sh
   python3 node/prepare_release.py stage --source /path/to/built/installers
   ```

Staging writes `node/releases/<version>/` locally. The full set is verified before
copying, copied bytes are checked again, and only a complete directory is made
available. Repeating staging is a no-op if all existing files match. Differing or
extra files produce an error instead of being overwritten. Original installers
remain untouched. Do not commit the binary files; `node/.gitignore` excludes them.
Run whole-repository copy tests before staging large local artifacts.

The staged set contains exactly four installers, four individual checksum files,
and sanitized `release.json`. Raw build reports are not distributed because they
contain machine-local paths. Keep licenses and third-party notices inside the
installers intact.

## Publish and verify

Commit and push the reviewed branch. Submit the documentation and capability
changes through the repository's normal PR flow; never push a merge directly to
`main`. Publish the exact reviewed commit, not a moving default branch:

```sh
gh release create node-v0.2.2 node/releases/0.2.2/* \
  --repo Wondermove-Inc/clawpod-capabilities \
  --target REVIEWED_COMMIT_SHA \
  --title 'ClawPod Node 0.2.2 preview' \
  --notes-file node/RELEASE-NOTES-0.2.2.md --prerelease --latest=false
```

The 0.2.2 preview has an ad-hoc signed Mac app, without Developer ID signing or
notarization, and no Windows publisher signature. Consult `VALIDATION.md` for
the verified Apple Silicon/Linux coverage and remaining native-platform limits.
`--latest=false` prevents this installer release from taking over the capability
repository's generic latest-release selector. Download links always use the Node
tag directly. Checksum files use only the installer basename so they can be
checked from the download directory with standard SHA-256 tools.

After publication, download every asset without authentication into a temporary
directory and run `verify_stage` or compare each file to `release.json`. Confirm
the release is publicly readable and all four download links resolve. If a
version already exists, inspect it; do not replace published installer bytes
under the same version. Changes require a new version and updated metadata.

Source preparation does not imply that these URLs are already live. The Harness
reports static release metadata without probing availability. Repository `main`
navigation gains the new download page after the PR merges; release assets are
independently accessible as soon as the release is published.
