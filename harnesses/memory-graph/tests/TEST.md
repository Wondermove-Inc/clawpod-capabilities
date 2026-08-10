# Memory Graph verification

Run the complete 46-test package suite from the repository root:

```bash
python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py' -v
```

The suite uses only temporary state, a fake direct Memory MCP executable, and sanitized package-local fixtures. It covers deterministic parsing and planning, the exact direct-memory-only source boundary, legacy core cleanup, provenance, ambiguity, secret rejection/redaction, bounded output, snapshot/diff validation, byte-capped MCP batches, isolated ownership, crash-safe reconciliation, Gateway prepare/run simulation, standing authorization, and registered-timezone daily cron planning. It never creates a live namespace or cron job.
