# 0.4.0 — Google Docs, Sheets, and Slides

27 new commands complete the three editor APIs' public REST surface (total 194):

- **Docs v1**: `docs.documents.get/create/batchUpdate`, high-level `docs.read` (bounded plain-text extraction with title/revision).
- **Sheets v4**: `sheets.spreadsheets.get/getByDataFilter/create/batchUpdate`, `sheets.values.get/batchGet/batchGetByDataFilter/update/append/clear/batchUpdate/batchClear/batchClearByDataFilter`, `sheets.sheets.copyTo`, `sheets.developerMetadata.get/search`, high-level `sheets.read`.
- **Slides v1**: `slides.presentations.get/create/batchUpdate`, `slides.pages.get/getThumbnail`, high-level `slides.read` (per-slide text outline).

Contracts: URL/method mapping for custom `:verb` endpoints; typed bodies (batch requests as closed single-verb envelopes, ValueRange with cell-typed matrices, closed DataFilter/GridRange/DeveloperMetadataLookup); query contracts (`valueInputOption` required on value writes, render options, thumbnail properties); least-privilege scopes with `.readonly` splits and implication closure; preflight reads for every mutation (resource GET with identifier-trimmed fields; creates are validated-body); `sheets.values.clear`/`batchClear*` classified destructive. New OAuth profiles `docs-*`/`sheets-*`/`slides-*`; `workspace-max` extended. Existing accounts must re-consent for the new scopes; the harness reports the exact missing scope until then.

Tests: `tests/test_docs_sheets_slides.py` (15 cases: exact URL mapping for all 24 provider commands, scope splits and enforcement, body requirements, safety classes, preflight validity, mock E2E for the three high-level reads and the values.update preview→confirm flow). Inventory/audit suites updated to 194 commands and pass unchanged otherwise.
