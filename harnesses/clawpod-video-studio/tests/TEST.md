# Validation contract

Run from the repository root:

```bash
python3 harnesses/clawpod-video-studio/tests/test_clawpod_video_studio.py
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
```

The credential-free suite covers all 49 command declarations, all 13 pinned pipeline manifests, the 100+ tool OpenMontage registry, real local OpenMontage tool execution, detached worker success/cancellation, exact approval binding, protected pointer metadata, mode-0600 secret injection, path and symlink rejection, real ffmpeg/ffprobe media QA, and registry/package alignment.

Release verification also exercises:

- Backlot loopback start, health, ownership rejection, and stop.
- Transactional runtime plan, byte-copy staging and inode isolation, post-copy digest validation, activation, backup, rollback, and post-rollback validation.
- Gateway manifest validation, trust, eligibility, and a representative `prepare → run` invocation after installation.

Provider network verification and paid generation are not inferred from local tests. OpenAI, Google, ElevenLabs, Pexels, Unsplash, and xAI have reviewed non-billable read adapters, but live verification requires separate secret-use and network-read approval. Other providers remain `configured_unverified` until a reviewed adapter or approved real execution exists. Any paid/cloud execution requires exact provider, model, operation, digest, cost ceiling, expiry, credential-use, and external-side-effect approval.
