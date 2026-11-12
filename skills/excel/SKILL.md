---
name: excel
description: "Use this skill any time a spreadsheet file is the primary input or output: open, read, edit, or fix an .xlsx, .xlsm, .xltx, .csv, or .tsv file (formulas, formatting, charts, cleaning messy data); create a new spreadsheet; or convert between tabular formats. The deliverable must be a spreadsheet file. Do NOT use when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration."
---

# XLSX creation, editing, and analysis

| Task | Approach |
|---|---|
| **Create** or **edit** with formulas/formatting | `openpyxl` — see gotchas below |
| **Bulk data** in or out | `pandas` (`read_excel`, `to_excel`) |
| **Quick look** at a sheet | `markitdown file.xlsx` — `## SheetName` per sheet; reads `.xlsm` too. No cell coordinates, so don't plan edits from it |
| **Read** a model (formulas *and* values) | two `load_workbook` passes — see gotchas |

> `openpyxl`, `pandas`, and `markitdown` are preinstalled — do not run `pip install` first; write the script and import directly. Only if an import fails (or the `markitdown` command is missing): `pip install` the missing package.

## On ClawPod: use GridCraft

ClawPod agents have ArtCraft Office: the **GridCraft** desktop app (Applications → Office) and `gridcraft-cli`. LibreOffice is not installed — `soffice` only prints the ArtCraft app list — so recalculation and conversion use GridCraft:

- **Recalculate:** see the next section.
- **Read:** `gridcraft-cli cat file.xlsx [--sheet S] [--range A1:D20] [--formulas]`; `info --json` lists sheets, used ranges, tables, charts and names; `eval '=SUM(A1:A9)' --in file.xlsx` tests one formula.
- **Convert:** `gridcraft-cli convert in out` between xlsx, csv, tsv, json, html and pdf.
- **Edit without a window:** `gridcraft-cli run --in in.xlsx --cmd 'id={json}' … --out out.xlsx`; `gridcraft-cli commands --search X` finds commands.
- **Visual work** the user should see: open the workbook in GridCraft on the desktop.

> Script paths below are relative to this skill's directory.

## Requirements for every output

- **Professional font** (Arial, Times New Roman) throughout, unless the user says otherwise.
- **Zero formula errors.** Never ship while the error check after recalculating names any cell. If you think an error predates you, prove it: load the *original* with `data_only=True` and look at that cell. An error you introduced looks exactly like one you inherited.
- **Use formulas, never hardcoded results.** Write `sheet['B10'] = '=SUM(B2:B9)'`, not the Python-computed total. The sheet must recalculate when its inputs change.
- **Follow the user's spec literally.** Exact tab names, exact column headers, and the formula they spelled out. A redesign that computes something else fails, however elegant.
- **Document every assumption and hardcoded number** where the reader will see it — a cell comment, or an adjacent cell at a table's end. Cite a real source when one exists (`Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]`); when the number came from the user, say so plainly.
- **A workbook *you create* for someone to fill in** needs a short legend naming which cells to edit, and one example row of realistic values showing the expected format. Never add such a row to a file you were asked to edit.
- **Editing an existing file: match its conventions exactly.** They override every guideline here. Find its designated input cells first — a distinct font color, fill, or shading marks them — write only there, and leave every existing formula untouched.

## Recalculate (mandatory whenever the file contains formulas)

openpyxl writes formulas as strings with **no cached values**. Until you recalculate, every
formula cell reads back as `None` to anything reading cached values — `pandas`,
`load_workbook(data_only=True)`, and most previewers.

```bash
gridcraft-cli convert output.xlsx output.xlsx     # recalculates and rewrites in place, formulas kept
python3 -c "import sys,openpyxl; E={'#DIV/0!','#N/A','#NAME?','#REF!','#VALUE!','#NUM!','#NULL!'}; wb=openpyxl.load_workbook(sys.argv[1],data_only=True); e=[f'{ws.title}!{c.coordinate}={c.value}' for ws in wb for r in ws.iter_rows() for c in r if c.value in E]; print(len(e), e[:100])" output.xlsx
gridcraft-cli check output.xlsx                   # exits 1 if a cached value or the XLSX round trip differs
```

GridCraft computes every formula in milliseconds and writes each result as the cell's cached
value. The one-liner prints how many cells hold an error value and names up to 100 of them.
Fix what it names, recalculate, and run it again until it prints `0 []`.

**A green recalc proves your formulas *evaluate*, not that they are *right*.** An off-by-one
range or a reference to the wrong row yields a clean, error-free file with wrong numbers.
Write 2–3 formulas first and check they pull the values you expect, before building out a grid.

**A workbook that links to another file loses those links** if you re-save it with openpyxl and
then recalculate. Such a formula reads `='[1]Returns Analysis'!$B$2` — the `[1]` is an index
into the workbook's external-reference list, naming a *separate file on disk*, not a sheet.
That file is rarely present here, so the cell's cached value is the only thing holding its
data. openpyxl strips that value on save, and recalculating cannot bring it back — copy those
cells' values out of the original before you save over them.

## Choosing formulas that survive verification

The user's Excel may be older than yours, and a function it cannot evaluate shows as `#NAME?`
when they open the file.

- **Prefer Excel-2007-era functions** — `SUMIFS`, `INDEX`, `MATCH`, `IFERROR`, `SUMPRODUCT` — which need no prefix.
- **Six post-2007 functions work, but only with an `_xlfn.` prefix**, because openpyxl writes your formula into the XML verbatim and Excel stores post-2007 names prefixed (its UI hides the prefix): `_xlfn.TEXTJOIN`, `_xlfn.CONCAT`, `_xlfn.IFS`, `_xlfn.SWITCH`, `_xlfn.MAXIFS`, `_xlfn.MINIFS`. Written bare, each yields `#NAME?`.
- **Never use `XLOOKUP`, `XMATCH`, `SORT`, `FILTER`, `UNIQUE`, or `SEQUENCE`.** Excel before 2021 cannot evaluate them, and they are spilling array functions: an openpyxl-written file has no spill metadata, so only the top-left cell of the range gets a value — with no error to flag the truncated result. Use `INDEX`/`MATCH` for lookups, and sort, filter, and de-duplicate in Python before writing the cells.

## openpyxl gotchas

- **Reading a model takes two loads.** `data_only=True` yields cached values with the formulas gone; the default yields formula strings with no values. One pass cannot give you both.
- **`data_only=True` is destructive if you save.** That workbook has no formulas left, so saving replaces every one with a literal — permanently.
- **`data_only=True` on a file openpyxl just wrote returns `None` everywhere** — recalculate with GridCraft first. (A formula whose result is `""` also reads back as `None`.)
- **Merged cells: write the top-left anchor only.** Every other cell in the range is a `MergedCell` whose `.value` is read-only.
- **`.xlsm` loses its macros unless you pass `keep_vba=True`** to `load_workbook`.
- **A sheet name containing a space must be quoted** in a cross-sheet reference: `='Assumptions Inputs'!$B$5`. Unquoted, it evaluates to `#VALUE!`.

## Financial models

Unless the user says otherwise, or the existing file already does something else.

**Color:** blue text (`0,0,255`) for hardcoded inputs and scenario levers · black for formulas ·
green (`0,128,0`) for links to another sheet · red (`255,0,0`) for links to another file ·
yellow fill (`255,255,0`) for key assumptions and cells the user should fill in.

**Numbers:** currency `$#,##0`, with the unit named in the header (`Revenue ($mm)`) · zeros
render as `-`, including in percentages (`$#,##0;($#,##0);-`) · negatives in parentheses ·
percentages `0.0%`, **stored as fractions** (`0.15` renders `15.0%`; storing `15` renders
`1500.0%`) · valuation multiples `0.0x` · years as text (`"2024"`, never `2,024`).

**Structure:** every assumption in its own labeled cell, referenced by the formulas that use it
(`=B5*(1+$B$6)`, never `=B5*1.05`) · formulas consistent across every projection period, since a
lone edited cell mid-row is the commonest silent error · guard denominators that can be zero.

## Dependencies

`openpyxl`, `pandas`, `markitdown` (pip, preinstalled — install only if an import fails or the command is missing) · `gridcraft-cli` (ArtCraft GridCraft)

_Modified by Wondermove for ClawPod: removed `scripts/recalc.py` and `scripts/office/soffice.py` and replaced LibreOffice recalculation with `gridcraft-cli` plus an error-cell check (LibreOffice is not installed on ClawPod); added the "On ClawPod: use GridCraft" section; renamed from `xlsx` to `excel` so the catalog shows a familiar name; the frontmatter description was shortened to the registry's 500-character limit and the `license` frontmatter key was removed (the registry allows only name and description; terms remain in LICENSE.txt). Original: anthropics/skills@2c5958e._
