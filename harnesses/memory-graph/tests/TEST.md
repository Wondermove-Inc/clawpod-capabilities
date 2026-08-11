# Memory Graph verification

Run the complete package suite from the repository root:

```bash
python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py' -v
```

The suite uses only temporary state, a fake direct Memory MCP executable, and sanitized package-local fixtures. It covers deterministic parsing and planning, the direct-memory-only source boundary, provenance, ambiguity, secret handling, and the chained private semantic JSON contract: exact bytes/digests/mode, paired arguments, bounds, traversal/extensions, symlinks, collisions, races, cleanup, deterministic repeats, invalid inputs, and unchanged full stdout when omitted. It also covers snapshot/diff validation, isolated ownership, crash-safe reconciliation, Gateway prepare/run simulation, standing authorization, and timezone-aware cron planning. It never creates a live namespace, cron job, network request, or MCP dispatch.
