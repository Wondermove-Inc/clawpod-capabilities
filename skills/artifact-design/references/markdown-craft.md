# Markdown artifacts

Choose `markdown` only when the content is prose-first and its whole structure is expressed by headings, lists, tables, and code blocks — a meeting summary, a decision record, a runbook, a reference sheet without charts. The renderer controls typography and color, so the design craft moves entirely into structure and words.

Choose `html` instead when any of these apply: layout beyond a single column, charts or diagrams, state encoded in color, interaction, a specific visual identity, or a table wider than a few short columns.

## Structure carries the design

- **One H1** that is the artifact's name; it should match `title`.
- A one-paragraph lede directly under it — this is also what the server keeps as the card preview (first 240 characters, tags stripped).
- Headings encode the reading path. Do not number sections unless the content is a real sequence.
- Lists for parallel items; tables for comparisons with the same attributes per row; paragraphs for reasoning. Never a list of one.
- Tables: header row, right-aligned numeric columns (`---:`), units in the header not the cells, at most six columns before you switch to HTML.
- Code blocks with a language tag. Commands the reader will run get their own block, one command per block.
- Emphasis is information: bold the decision, the deadline, the owner — never a whole sentence.
- No emoji as section markers; no horizontal rules as decoration (a rule marks a real change of part).

## Words

Write from the reader's side. Active voice. Name things as people recognize them. State facts separately from assumptions. The requested action, owner, and deadline are explicit and near the top when the artifact asks for a decision.

## Example shape

```markdown
# Node Onboarding Runbook

Connect a Mac or Windows 11 machine to ClawPod as a node in about ten minutes; the only human steps are sign-in and approval.

## Before you start
- Admin access on the machine
- The ClawPod organization's Tailscale login link

## Steps
1. Install Tailscale and sign in with the organization account.
2. Run the node installer …

## Verify
| Check | Command | Expected |
|---|---|---|
| Node visible | `clawpod node status` | `paired` |

## If it fails
…
```
