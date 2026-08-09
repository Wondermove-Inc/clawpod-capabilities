# projects

## Alpha — project

<!-- openclaw-memory-claim:cl_project_alpha -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_project_alpha","claim_key":"project.alpha","status":"current","created_at":"2026-08-09T00:00:00.000Z","updated_at":"2026-08-09T00:00:00.000Z","supersedes":[],"superseded_by":[],"contradicts":[],"evidence":[{"evidence_id":"ev_alpha","path":"memory/2026-08-09.md","anchor_id":"alpha","content_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","source_document_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","captured_at":"2026-08-09T00:00:00.000Z","source_type":"sanitized_fixture","source_actor":"test"}],"writer_version":"memory-writer-contract-v1","extraction_version":"claim-extraction-contract-v1","entity":{"name":"project.alpha","type":"Project"}} -->
- Status: current
- Claim: Alpha is active.
- Confidence: 1
- Evidence: memory/2026-08-09.md (ev_alpha)
- Updated: 2026-08-09T00:00:00.000Z

## Retired note — prior version

<!-- openclaw-memory-claim:cl_retired_old -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_retired_old","claim_key":"project.retired-note","status":"superseded","created_at":"2026-08-07T00:00:00.000Z","updated_at":"2026-08-08T00:00:00.000Z","supersedes":[],"superseded_by":["cl_retired_archived"],"contradicts":[],"evidence":[{"evidence_id":"ev_retired_old","path":"memory/2026-08-09.md","anchor_id":"retired-old","content_hash":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}],"writer_version":"memory-writer-contract-v1","extraction_version":"claim-extraction-contract-v1"} -->
- Status: superseded
- Claim: This historical note was replaced before archival.
- Confidence: 0.7
- Evidence: memory/2026-08-09.md (ev_retired_old)
- Updated: 2026-08-08T00:00:00.000Z

## Retired note — archived terminal

<!-- openclaw-memory-claim:cl_retired_archived -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_retired_archived","claim_key":"project.retired-note","status":"archived","created_at":"2026-08-08T00:00:00.000Z","updated_at":"2026-08-09T00:00:00.000Z","supersedes":["cl_retired_old"],"superseded_by":[],"contradicts":[],"evidence":[{"evidence_id":"ev_retired_archived","path":"memory/2026-08-09.md","anchor_id":"retired-archived","content_hash":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"}],"writer_version":"memory-writer-contract-v1","extraction_version":"claim-extraction-contract-v1"} -->
- Status: archived
- Claim: This note is archived and must not enter the current graph.
- Confidence: 1
- Evidence: memory/2026-08-09.md (ev_retired_archived)
- Updated: 2026-08-09T00:00:00.000Z

## Alpha — former owner

<!-- openclaw-memory-claim:cl_project_owner_old -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_project_owner_old","claim_key":"project.alpha.owner","status":"superseded","created_at":"2026-08-08T00:00:00.000Z","updated_at":"2026-08-09T00:00:00.000Z","supersedes":[],"superseded_by":["cl_project_owner_new"],"contradicts":[],"evidence":[{"evidence_id":"ev_old","path":"memory/2026-08-09.md","anchor_id":"old","content_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}],"writer_version":"memory-writer-contract-v1","extraction_version":"claim-extraction-contract-v1","entity":{"name":"project.alpha.owner","type":"ProjectFact"},"relations":[{"to":"project.alpha","type":"belongs_to"}]} -->
- Status: superseded
- Claim: The former owner is archived history.
- Confidence: 0.8
- Evidence: memory/2026-08-09.md (ev_old)
- Updated: 2026-08-09T00:00:00.000Z

## Alpha — owner

<!-- openclaw-memory-claim:cl_project_owner_new -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_project_owner_new","claim_key":"project.alpha.owner","status":"current","created_at":"2026-08-09T00:00:00.000Z","updated_at":"2026-08-09T00:00:00.000Z","supersedes":["cl_project_owner_old"],"superseded_by":[],"contradicts":[],"evidence":[{"evidence_id":"ev_new","path":"memory/2026-08-09.md","anchor_id":"new","content_hash":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}],"writer_version":"memory-writer-contract-v1","extraction_version":"claim-extraction-contract-v1","entity":{"name":"project.alpha.owner","type":"ProjectFact"},"relations":[{"to":"project.alpha","type":"belongs_to"}]} -->
- Status: current
- Claim: Mina owns Alpha.
- Confidence: 1
- Evidence: memory/2026-08-09.md (ev_new)
- Updated: 2026-08-09T00:00:00.000Z
