# Rollback and Incident Reference

Use for rollback planning, bounded cleanup, compensating changes, or unintended mutation handling.

## Rollback boundary

Do not claim rollback capability without a specific verified procedure. When automatic rollback is unavailable, define the smallest separately approved compensating change or bounded cleanup and its verification.

Rollback or cleanup must include:

- exact target;
- before state;
- intended after state;
- command or operation;
- authorization boundary;
- expected IDs;
- verification surface;
- residual risk.

## Unintended mutation

If any unintended mutation occurs:

1. Stop ordinary mutation work immediately.
2. Document incident, exact target, command, identifiers, before state, observed after state, and potential impact.
3. Request independent reviewer direction.
4. Perform only rollback or bounded cleanup allowed by reviewer direction and authorization boundary.
5. Verify and record cleanup result before any fresh attempt.

Do not conceal a partial result, reuse unrelated approval, or continue because remaining steps appear safe.
