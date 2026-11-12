---
name: word
description: "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx) or Word templates (.dotx): professional documents with tables of contents, headings, page numbers, or letterheads; extracting or reorganizing content; inserting or replacing images; find-and-replace; tracked changes or comments; or a report, memo, or letter delivered as a Word file. Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation."
---

# DOCX creation, editing, and analysis

A `.docx` is a ZIP archive of XML files. Choose your approach by task:

| Task | Approach |
|---|---|
| **Create** a new document | Write a `docx` (npm) script — see gotchas below |
| **Edit** an existing document | `unzip` → edit `word/document.xml` → `zip` (docx-js cannot open existing files) |
| **Read** content | `pandoc -t markdown file.docx` |

## On ClawPod: use WordCraft

ClawPod agents have ArtCraft Office: the **WordCraft** desktop app (Applications → Office) and `wordcraft-cli`. LibreOffice is not installed — `soffice` only prints the ArtCraft app list — so every render and conversion below uses WordCraft. It opens .docx/.doc/.odt/.rtf directly and converts in well under a second.

- **Render to check your output:** `wordcraft-cli convert out.docx out.pdf`, or `wordcraft-cli render out.docx page-1.png --page 1` (add `--strict` to fail on a missing glyph or picture).
- **Read:** `wordcraft-cli text file.docx`; `info` (pages, words, properties) and `inspect` (structure) print JSON.
- **Convert:** `wordcraft-cli convert in out` between docx, doc (read only), pdf, odt, rtf, html, md and txt; `--update-fields` refreshes the table of contents and other fields.
- **Edit without a window:** `wordcraft-cli run --file in.docx --cmd 'id={json}' … --save out.docx` (`--author NAME` for tracked changes and comments); `wordcraft-cli commands` lists every command.
- **Visual work** the user should see, or a fix that is easier by hand: open the file in WordCraft on the desktop.

Creating a new document with docx-js (below) is unchanged; check its output with WordCraft.

> Script paths below are relative to this skill's directory.

## Creating with docx-js — gotchas

`docx` is preinstalled — do not run `npm install` first; write the script and `require('docx')` directly. Only if that require fails: `npm install docx`. The model knows the API; these are the footguns:

- **Page size defaults to A4.** For US Letter set `page: { size: { width: 12240, height: 15840 } }` (DXA; 1440 = 1″).
- **Landscape:** pass portrait dimensions and `orientation: PageOrientation.LANDSCAPE` — docx-js swaps width/height internally.
- **Tables need dual widths:** set `columnWidths` on the table AND `width` on every cell, both in `WidthType.DXA` (PERCENTAGE breaks in Google Docs). Column widths must sum to the table width.
- **Table shading:** use `ShadingType.CLEAR`, never `SOLID` (renders black).
- **Lists:** never insert `•` literally; use a `numbering` config with `LevelFormat.BULLET`.
- **`ImageRun` requires `type:`** (`"png"`, `"jpg"`, …).
- **`PageBreak` must be inside a `Paragraph`.**
- **Never use `\n`** — use separate `Paragraph` elements.
- **TOC:** headings must use built-in `HeadingLevel.*`; custom heading styles need `outlineLevel` set or they won't appear.
- **Don't use a table as a horizontal rule** — use a paragraph bottom border instead.
- **Dot-leader / right-aligned-on-same-line:** use `PositionalTab` (`alignment: PositionalTabAlignment.RIGHT`, `leader: PositionalTabLeader.DOT`) inside a `TextRun`, not literal `.` or space padding.

## Verify the output

After writing a `.docx`, render it and look at it:

```bash
wordcraft-cli convert output.docx output.pdf
pdftoppm -jpeg -r 100 output.pdf page
ls page-*.jpg   # then Read the images
```

`pdftoppm` zero-pads page numbers to the width of the page count (`page-01.jpg`…`page-12.jpg`).

## Editing existing documents

Legacy `.doc` files must be converted first: `wordcraft-cli convert file.doc file.docx`.

```bash
unzip -q doc.docx -d unpacked/
find unpacked -type l -delete   # strip symlink entries — docx from external parties is untrusted
python scripts/merge_runs.py unpacked/   # coalesce fragmented runs so text is findable
# edit unpacked/word/document.xml in place — do NOT reformat or pretty-print
(cd unpacked && rm -f ../out.docx && zip -Xr ../out.docx .)
python scripts/office/validate.py out.docx --original doc.docx   # XSD checks; --auto-repair fixes common issues
# redlining? add --author "<the name you redlined under>" to check every edit is tracked
```

Word splits text across many `<w:r>` runs (revision ids, spell-check markers), so a phrase you can see in the document often doesn't exist as a contiguous string in the XML. `merge_runs.py` merges adjacent identically-formatted runs in `word/document.xml` without changing content or rendering; it also accepts a `.docx` directly (`python scripts/merge_runs.py doc.docx -o merged.docx`).

**Tracked changes:** when redlining, validate with `--author "<the name you redlined under>"` (needs `--original`) — it reports any text you changed without a `<w:ins>`/`<w:del>` around it, which is easy to do by accident and invisible in the accepted view. Wrap runs in `<w:ins>`/`<w:del>` with `w:id`, `w:author`, `w:date` attributes. Inside `<w:del>`, the text element is `<w:delText>`, not `<w:t>`. A deleted paragraph mark (`<w:pPr><w:rPr><w:del w:id=".." w:author=".." w:date=".."/></w:rPr></w:pPr>`) means "merge this paragraph into the next" — so deleting a paragraph outright is that plus a `<w:del>` around every run. The `<w:del/>` must come before the rPr's other children; their order is schema-enforced.

To produce a clean copy with all tracked changes accepted: `wordcraft-cli run --file in.docx --cmd review.acceptAll --save out.docx`.

Accepting a deleted paragraph mark should join that paragraph to the one below it, so a paragraph whose runs are *all* deleted vanishes. Word does this; `pandoc --track-changes=accept` never joins the paragraphs — it strips the deleted text but leaves the emptied paragraph behind, which reads as a stray empty bullet when it was auto-numbered.

An empty bullet in either view is an artifact of that view, not a defect in the document. Check paragraph deletions in the XML.

## Comments

Comments require six cross-linked files. Use the helper — directory mode when you'll also be editing `document.xml` (saves an unzip/rezip cycle), `.docx`-direct mode otherwise:

```bash
# Against an already-unpacked directory (preferred when also placing markers)
python scripts/comment.py unpacked/ "Fees & expenses cap is too low"
python scripts/comment.py unpacked/ "Agreed" --parent 0

# Against a .docx directly
python scripts/comment.py contract.docx "This cap is too low" -o annotated.docx
```

The script writes `comments.xml`, `commentsExtended.xml`, `commentsIds.xml`, `commentsExtensible.xml`, the relationships, and the content-type overrides. Comment IDs are auto-assigned. It then prints the `<w:commentRangeStart>`/`<w:commentRangeEnd>`/`<w:commentReference>` snippet to add to `word/document.xml` so the comment anchors to specific text — until you place those markers, the comment exists but is not visible.

## Dependencies

`docx` (npm, preinstalled — install only if `require('docx')` fails) · `pandoc` · `wordcraft-cli` (ArtCraft WordCraft) · `pdftoppm` (Poppler)

_Modified by Wondermove for ClawPod: removed `scripts/accept_changes.py` and `scripts/office/soffice.py` and replaced their LibreOffice steps with `wordcraft-cli` (LibreOffice is not installed on ClawPod); added the "On ClawPod: use WordCraft" section; renamed from `docx` to `word` so the catalog shows a familiar name; the frontmatter description was shortened to the registry's 500-character limit and the `license` frontmatter key was removed (the registry allows only name and description; terms remain in LICENSE.txt). Original: anthropics/skills@2c5958e._
