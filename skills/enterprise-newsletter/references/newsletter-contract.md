# Newsletter JSON contract

Use UTF-8 JSON with these required top-level fields: `schemaVersion` (number `1`), `profile`, `brand`, `edition`, `headline`, `preheader`, `executiveLead`, `atAGlance`, `keyNumbers`, `sections`, `synthesis`, `methodology`, `footer`, and `sources`.

- `brand`: required `name` and `primaryColor`, plus optional `tagline`; no customer-specific defaults. `primaryColor` is exactly `#RRGGBB` and becomes the deterministic HTML accent token; `tagline` is visibly rendered when supplied.
- `edition`: `label` and ISO `date` (`YYYY-MM-DD`).
- `atAGlance`: 2–6 items with `title`, `summary`, and optional `signal`.
- `keyNumbers`: exactly four `{value,label,sourceIds}` items. Each item must cite at least one declared source.
- `sections`: profile-bounded section/card collections. Brief: 1–4 sections and 2–8 total cards. Newsletter: 2–6 sections and 3–12 cards. Capability catalog: 1–6 sections and 4–24 cards.
- Every card contains `title`, `facts`, `whyItMatters`, and `cta`. Each fact is `{text,evidenceRequired,sourceIds}`. `cta` is `{label,url}` with an HTTPS URL.
- `synthesis`: 1–6 insight strings. `methodology`: concise scope/limitations text. `footer`: required distinct `tagline` and `text`, plus optional HTTPS `unsubscribeUrl`.
- `sources`: 1–40 unique `{id,title,url,publisher,publishedAt}` records. URLs must be HTTPS and dates ISO. Evidence-required facts must reference at least one declared source.

All nested objects reject undeclared properties, and all strings and arrays have profile-neutral bounds in the complete Harness JSON Schema. Profile-specific total-card and section rules remain validation rules and schema annotations. Text is escaped during HTML rendering. Rendering fails closed unless the headline, every card title, every CTA URL, every declared source URL, and both footer fields occur in both HTML and plain text.
