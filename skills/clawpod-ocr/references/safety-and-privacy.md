# Safety and privacy

Local OCR is network-free. Remote Ollama review is external data transfer and may use a protected credential.

Before remote review, identify document sensitivity, listed pages, image byte counts/digests, endpoint, model, masking needs, and retention expectations. Send only the exact approved bounded page images. Never send full documents implicitly.

Reject traversal, symlinks, unsupported or corrupt files, over-limit sizes/pages/pixels, non-loopback HTTP, endpoint credentials in URLs, plaintext tokens in inputs, permissive secret files, oversized responses, and approval-digest mismatch.

Keep originals and raw OCR immutable. Treat model text as a proposal and require explicit correction selection. Do not expose document text, endpoints, tokens, or private paths in logs or reports.