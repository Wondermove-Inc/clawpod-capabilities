# Examples

Every script here runs as written on a new document unless its row names an input. They are the reference for how to write commands: read the one closest to your task before you start, and copy its structure, not its content.

```bash
cd <this folder>
figcraft-cli run 03-screens/12-web-dashboard-with-charts-and-table.jsonl --out out/dashboard.figcraft
figcraft-cli export out/dashboard.figcraft -o out/ --scale 2     # one PNG per top-level frame
```

A row whose Input names another script works on that script's output: run the named script first, then pass its file with `--in`, for example `figcraft-cli run 11-enterprise/52-enterprise-admin-console-access-management.jsonl --in out/51-enterprise-component-library-on-carbon-tokens.figcraft --out out/52.figcraft` (script 51 in turn takes the output of 48). An Input that names a file in this folder is passed the same way.

Run the commands from this folder: scripts read `assets/` and `out/` by relative path and write to `out/`. If the skill folder is read-only, copy `examples/` to your working directory first (`verify.sh` makes its own copy).

`bash verify.sh` copies this folder to a temporary one, runs every script there against the installed FigCraft, renders each result (token sets have no layers, so their render is empty), runs `check_layout.py` on it and prints where the results are. Run it after FigCraft is updated: a script that fails names the step and the reason, and `figcraft-cli commands --filter <command>` shows what that command takes now.

`python3 check_layout.py out/dashboard.figcraft` lists what a small render hides: frames left at 100 x 100, text shorter than its line or outside its screen, content cut off by its parent, top-level frames that overlap.

## Foundations: tokens and styles

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `01-foundations/01-color-tokens-light-dark.jsonl` | Colour tokens with Light and Dark modes | variable collections, modes, aliases (component token -> semantic token), number tokens bound to padding and radius, a mode set on a frame, tokens exported as CSS | new document |
| `01-foundations/02-type-scale-effect-and-grid-styles.jsonl` | Type scale, elevation and layout grid styles | text styles on a modular scale, effect styles for elevation, a paint style with a gradient, a column layout grid, a specimen sheet that documents them | new document |

## Components

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `02-components/03-button-variants-and-properties.jsonl` | Button: variants, states and component properties | a component set built from Kind x State variants, focus ring, text / boolean / instance-swap properties, an icon component, instances that set properties | new document |
| `02-components/04-form-controls-and-states.jsonl` | Form controls: input, checkbox, radio, toggle, select | an input with default, focus, error and disabled variants and its label, value and helper as text properties; checkbox, radio and toggle as on / off variants; a select at rest; labels as text properties on every control that has one; every control 44 px high to touch, the toggle inside a 44 px target; control outlines at 3 : 1 against the surface | new document |
| `02-components/05-cards-lists-avatars-badges.jsonl` | Cards, list items, avatars, badges and chips | content components with realistic data, a tone variant property, an avatar group with overlap (negative gap), truncating text, a card with media, body and actions | new document |
| `02-components/06-navigation-bars-tabs-sidebar.jsonl` | Navigation: app bar, tab bar, sidebar, tabs, breadcrumb, pagination | navigation components with the active item as a variant, icons that change colour per state, spaceBetween alignment, a segmented control | new document |
| `02-components/07-feedback-dialog-toast-empty-skeleton.jsonl` | Feedback: dialog, toast, banner, tooltip, empty state, progress, skeleton | overlays with a scrim, tone variants, an empty state with one clear action, a loading skeleton that matches the loaded layout, a progress bar sized by percentage | new document |
| `02-components/08-icon-set-on-a-24px-grid.jsonl` | Icon set: components on a 24 px grid with SVG export settings | vector paths inside 24 px frames, scale constraints so instances resize cleanly, one component per icon named icon/<name>, export settings added in bulk, a size preview from 16 to 48 px | new document |
| `02-components/09-slots-and-exposed-nested-instances.jsonl` | Slots and exposed nested instances | a card whose content area is a slot that instances fill with anything, a settings row that exposes its nested toggle, inserting components into a slot, reading the resulting properties | new document |

## Screens and pages

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `03-screens/10-mobile-app-flow-with-components.jsonl` | Mobile app: four screens built from components, wired as a prototype | a Components section with a button set, a list row and a tab bar set; screens assembled from instances with auto layout only; absolute layers over artwork; a spacer that pins the footer; navigate / back interactions and a flow start | new document |
| `03-screens/11-mobile-commerce-korean.jsonl` | Korean mobile commerce: 홈, 상품 상세, 장바구니 | CJK typography (Noto Sans CJK KR, looser line height, slight negative tracking), a two-column product grid with wrap, price / discount hierarchy, a purchase bar pinned to the bottom of the screen, a quantity stepper, an order summary | new document |
| `03-screens/12-web-dashboard-with-charts-and-table.jsonl` | Web dashboard: sidebar, figures, charts drawn from vectors, a table | a 1440 px app shell with a fixed sidebar and a fluid content column, KPI cards with trend badges, cards of equal height in a row, a line chart with a y scale and a comparison series, a bar chart, a donut from ellipse arcs, a table with status badges and right-aligned numbers | new document |
| `03-screens/13-landing-page-desktop-and-phone.jsonl` | Marketing landing page at 1440 and 390 | a page as stacked full-width sections, a centred max-width container, a hero with a balanced headline (wrapStyle) and a product shot built from frames, a three-up feature grid, pricing with a highlighted plan, the same content re-flowed for a phone | new document |
| `03-screens/14-settings-form-web.jsonl` | Settings page: a long form in sections | label-left form rows on a two-column grid, section headings with supporting text, helper and error messages, a save bar that closes the form, the destructive action kept apart | new document |
| `03-screens/15-screen-states-loading-empty-error-success.jsonl` | One screen, four states: loading, empty, error, loaded | designing the unhappy paths next to the happy one, a skeleton that mirrors the loaded layout, an empty state with a single action, an error that says what happened and how to recover | new document |
| `03-screens/16-data-table-with-toolbar-and-selection.jsonl` | Data table: toolbar, filters, selection, pagination | a table whose rows are one-row grids with fixed and fr column tracks (a 1fr row track is what lets cells centre vertically), a selected row and a bulk-action bar, sortable headers, numbers right-aligned in tabular figures, a footer with pagination | new document |
| `03-screens/17-low-fidelity-wireframe-flow.jsonl` | Low-fidelity wireframes: a checkout flow in grey boxes | greyscale only, two text weights, image placeholders marked with a cross, text as grey bars, notes beside the frames, arrows between screens; the structure is decided before any colour | new document |
| `03-screens/18-responsive-layout-constraints-and-grid.jsonl` | Responsive behaviour: constraints, min / max sizes, wrap and grid tracks | one card grid built once, then duplicated and resized to 768 and 390 (the layout does the work), fill children with min and max widths, a header row that wraps, a grid with fr tracks, constraints on a frame without auto layout | new document |

## Prototyping

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `04-prototyping/19-prototype-navigation-overlays-and-transitions.jsonl` | Prototype: navigation, a modal overlay, a bottom sheet, transitions | navigate with push and back, an overlay centred on a dimmed background, a bottom sheet that moves in from the bottom, close actions, two named flows, the device frame | new document |
| `04-prototyping/20-prototype-variables-conditions-and-modes.jsonl` | Prototype logic: variables, expressions, conditions, switching Light / Dark | a number variable that drives the logic and a string variable bound to the text that shows it, set-variable actions with expressions, a conditional that stops at a limit, a boolean that shows and hides a layer, a mode switch that re-themes the screen while the prototype runs | new document |
| `04-prototyping/21-prototype-scrolling-fixed-header-and-anchor-links.jsonl` | Prototype: vertical scroll, a fixed header, scroll-to links | a frame taller than the device that scrolls, a header that stays fixed while content moves, a horizontally scrolling row, scrollTo actions that stop below the fixed header | new document |
| `04-prototyping/22-interactive-components-hover-press-toggle.jsonl` | Interactive components: hover, press and toggle inside the component | interactions placed on variants so every instance behaves without wiring each screen: hover and press with changeTo, a toggle that flips on click, smart animate between variants | new document |

## Graphics, illustration, charts, type and images

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `05-graphics/23-logo-marks-with-boolean-operations.jsonl` | Logo marks from boolean operations, with lockups and export settings | union / subtract / intersect / exclude on simple shapes, flattening the result to one vector, outlining a stroke, a clear-space lockup on light and dark, export settings for SVG and PNG at 1x and 2x | new document |
| `05-graphics/24-vector-illustration-gradients-blur-mask.jsonl` | Vector illustration: layered gradients, glow, mask and grain | depth from overlapping gradient shapes, a blurred glow behind the sun, clouds from unioned ellipses, an alpha mask that crops the scene to a shape, a noise effect for grain | new document |
| `05-graphics/25-glassmorphism-card-with-background-blur.jsonl` | Glass: background blur, the glass effect and soft colour fields | blurred colour blobs for the backdrop, panels with a translucent fill plus backgroundBlur, the glass effect for refraction, hairline light strokes, inner shadow highlights | new document |
| `05-graphics/26-charts-from-vectors-and-arcs.jsonl` | Charts drawn with vectors, rectangles and ellipse arcs | a line chart with area and comparison series, bars that fill their column, a donut with its legend and a progress ring from arcStart / arcSweep / arcInner, a stacked bar, sparklines inside stat cards; the brand series, text and surfaces on tokens so Dark works; the other series keep literal colours, as categorical data does | new document |
| `05-graphics/27-expressive-typography-gradient-outline-path.jsonl` | Expressive type: gradient fill, outline, text on a path, OpenType features, fitted headlines | gradient paint on text, stroke-only display type, text following a circle, tabular figures, a variable-font weight axis (Montserrat has one; check with text.fonts {family, axes: true}), text.fit to hold a headline to two lines | new document |
| `05-graphics/28-image-fills-crop-adjust-and-masks.jsonl` | Images: fill modes, adjustments, masks and text over photos | placing an image file, fill and fit modes, adjustment presets, a gradient scrim that keeps text readable over a photo, circular and rounded crops by placing the image into a shape (target) | new document |
| `05-graphics/29-patterns-brushes-dashes-and-stroke-profiles.jsonl` | Patterns, brushes, dashes and stroke width profiles | a pattern fill tiled from a source layer, brush presets on paths, tapered and pinched width profiles, dashed and dotted strokes, arrow caps; decorative backgrounds without images | new document |

## Marketing and print

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `06-marketing-and-print/30-social-carousel-from-one-template-with-data-fill.jsonl` | Social carousel: one template, many slides, three sizes | a post template whose layer names are the data keys, data.fill making one copy per row, text fitted to its box per slide, a layer hidden per row, every slide also produced as story and square by resizing the auto layout, and the story copies given the margins the story interface needs | new document |
| `06-marketing-and-print/31-presentation-slides-16x9.jsonl` | Presentation slides at 1920 x 1080 | a deck as frames in reading order, one idea per slide, type no smaller than 28 px on a 1920 px slide, content that fills the slide, a footer component with a page number property on its own page, a chart with axis values, exporting the frames to one PDF | new document |
| `06-marketing-and-print/32-print-poster-and-business-card-with-bleed.jsonl` | Print: an A3 poster and a business card, exported with bleed and crop marks | page sizes in points (A3 = 842 x 1191, card = 90 x 55 mm), background art that runs past the trim edge, a safe margin for text, export settings that write a CMYK PDF with 3 mm bleed and crop marks | new document |
| `06-marketing-and-print/33-open-graph-image-and-ad-banners.jsonl` | Link preview image and display ad sizes from one design | the standard sizes (1200 x 630, 300 x 250, 728 x 90, 160 x 600, 320 x 50), one message re-set for each ratio rather than scaled (stacked for tall sizes, a single row for strips), export settings per frame | new document |

## Boards (whiteboarding)

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `07-boards/34-board-retrospective-with-sections-and-stamps.jsonl` | Board: a retrospective with sections, stickies and stamps | three sections as columns, stickies placed inside their section (parent) so they move with it, colour per column, authors, stamps as votes, the built-in board templates | new document |
| `07-boards/35-board-flowchart-with-decisions.jsonl` | Board: a flowchart with decisions and labelled connectors | process, decision and terminal shapes, elbow connectors that follow their shapes, yes / no labels, adding a connected shape in one call | new document |
| `07-boards/36-board-mind-map-and-decision-table.jsonl` | Board: a mind map and a decision table | a mind map that lays itself out, adding children to a branch, a table from a cells array, text labels as headings | new document |
| `07-boards/37-board-user-journey-map.jsonl` | Board: a user journey map | stages as sections in a row, lanes of stickies (doing, thinking, pain points, opportunities) coloured by lane and parented to their stage, an emotion lane with a labelled scale and a point per stage | new document |

## Developer handoff and collaboration

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `08-handoff-and-collaboration/38-developer-handoff-annotations-code-and-tokens.jsonl` | Developer handoff: annotations, status, measurements, code and tokens | annotation categories, notes that pin property values, ready-for-dev status, a kept measurement, a dev resource link, export settings, generated CSS / React / Tailwind / SwiftUI, the inspect table, tokens exported as CSS and JSON | `03-screens/10-mobile-app-flow-with-components` |
| `08-handoff-and-collaboration/39-code-connect-components-to-real-code.jsonl` | Code Connect: link components to the code that implements them | connecting a component set to its React and SwiftUI counterparts, a template that maps properties to props, what inspect shows afterwards, exporting the mappings file a repository can publish from | `02-components/03-button-variants-and-properties` |
| `08-handoff-and-collaboration/40-review-comments-versions-and-branches.jsonl` | Review workflow: comments, named versions and a branch merged back | pinned comments with replies and resolution, a named version before a risky change, a branch for an exploration, reviewing what changed, merging it into main | `03-screens/10-mobile-app-flow-with-components` |
| `08-handoff-and-collaboration/41-publish-a-library.jsonl` | Library, part 1: publish components, styles and variables | publishing a design-system file as a library version; run it with --out so the consumer in part 2 can add it | `02-components/03-button-variants-and-properties` |
| `08-handoff-and-collaboration/42-use-a-library-in-another-file.jsonl` | Library, part 2: use the published library from a product file | adding a library by path, placing a library component, applying a library text style, binding a library variable, checking for updates | new document; adds `out/41-publish-a-library.figcraft` as a library, so run that script first |

## Working with existing files

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `09-working-with-existing-files/43-restyle-an-existing-file.jsonl` | Edit a file you did not make: audit, retheme, rewrite copy | reading a file's structure before touching it, listing every colour in use, replacing one colour everywhere, find and replace across text, batch renaming layers, adding variables and binding existing layers to them | `files/ridgeline-onboarding.figcraft` |
| `09-working-with-existing-files/44-clean-up-a-messy-frame.jsonl` | Clean up: align, distribute, tidy, suggest auto layout, name layers | absolutely positioned leftovers turned into structure: align and distribute, tidy up a grid, layout.suggest to wrap rows and columns in auto layout frames, rounding to whole pixels, batch names with numbering | new document |

## Token sets from open and enterprise design systems

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `10-token-sets/45-radix-colors-light-and-dark.jsonl` | Token set: Radix Colors, 15 scales x 12 steps, Light and Dark | a primitive palette with a mode per theme, then a small semantic layer that aliases it. Steps: 1-2 app backgrounds, 3-5 component backgrounds, 6-8 borders, 9-10 solid fills, 11-12 text. Values from radix-ui/colors (MIT) | new document |
| `10-token-sets/46-tailwind-palette.jsonl` | Token set: the Tailwind CSS palette, 22 hues x 11 steps | a wide primitive palette as one collection; pick a neutral and a brand hue from it and alias them in your own semantic collection. Values from tailwindcss v3.4 (MIT) | new document |
| `10-token-sets/47-material-3-baseline-colour-roles.jsonl` | Token set: Material Design 3 baseline colour roles, Light and Dark | colour roles rather than hues (primary / on-primary / primary-container ...), each with a Light and a Dark value; pair every surface role with its on- role for text. Values from material-components/material-web tokens (Apache-2.0) | new document |
| `10-token-sets/48-ibm-carbon-four-themes-with-component-tokens.jsonl` | Enterprise token set: IBM Carbon, four themes in three tiers | the structure a large design system uses: a primitive palette, a semantic theme collection with one mode per theme (White, Gray 10, Gray 90, Gray 100) whose values are aliases into the palette (or a palette colour with its own opacity), a component tier (button, tag, notification) with the same modes, layout tokens as numbers, the productive and expressive type sets as text styles. Generated from carbon-design-system/carbon v11 token files (Apache-2.0) | new document |
| `10-token-sets/49-github-primer-five-themes-with-high-contrast.jsonl` | Enterprise token set: GitHub Primer functional colours in five themes | functional (role-based) colour tokens with a mode for each theme including the high-contrast and dimmed ones: accessibility themes are modes of the same tokens, not separate files. Generated from @primer/primitives 11.10.0 (MIT) | new document |
| `10-token-sets/50-atlassian-light-dark-with-spacing-and-shape.jsonl` | Enterprise token set: Atlassian colour, spacing and radius tokens | role-named colour tokens with state suffixes (hovered, pressed) in Light and Dark, a spacing scale and a radius scale as number variables. Generated from @atlaskit/tokens 20.12.0 (Apache-2.0) | new document |

## Enterprise: a full library, console screens, flows and governance on real Carbon tokens

| Script | What it builds | What it shows | Input |
|---|---|---|---|
| `11-enterprise/51-enterprise-component-library-on-carbon-tokens.jsonl` | Enterprise component library: full matrices on a three-tier token set | components bound only to role and component tokens, so all four themes work with no edits; a button set of Kind x State x Size (125 variants) where one size is built and the rest are derived with addVariant and bound to size tokens; a focus ring made of the focus and focus-inset tokens; text-input states including invalid and read-only; tags in two sizes on tag tokens; notifications on notification tokens; table header and row sets in five densities, rows with a text property per cell and an exposed nested status tag; application chrome (header, side navigation, toolbar, batch actions, pagination) as components; the kit previewed in White and Gray 100. Icons are Lucide stand-ins, not Carbon icons | `10-token-sets/48-ibm-carbon-four-themes-with-component-tokens` |
| `11-enterprise/52-enterprise-admin-console-access-management.jsonl` | Enterprise admin console: access management with a dense data table and a side panel | a 1584 px application frame made of library instances: header, side navigation, table toolbar, batch-action bar, table header, rows filled through cell properties and the nested status tag, pagination, and an edit panel with form states and a notification (the breadcrumb, page title and tabs are local layers on the same tokens); the same screen in Gray 100 by setting four modes; a compact copy by switching the Size property of the header and the rows; the table when it is empty, loading and not permitted | `11-enterprise/51-enterprise-component-library-on-carbon-tokens` |
| `11-enterprise/53-enterprise-flows-provisioning-wizard-and-audit-log.jsonl` | Enterprise flows: a multi-step provisioning wizard and an audit log | a three-step wizard with a progress indicator: a step blocked by a validation error, the same step valid (a duplicate with three properties changed), and a review step with edit links, all with a cost summary that stays in view; an audit log whose rows are 25 instances of one local component, bound with the header to the xs size token, with filters and an event-detail panel; prototype links that follow the real paths (fix the field, next, back, edit; open and close an event) | `11-enterprise/51-enterprise-component-library-on-carbon-tokens` |
| `11-enterprise/54-component-specification-accessibility-and-release.jsonl` | Design system governance: a component specification, accessibility notes, a changelog and a published release | what a team needs before it can adopt a component: anatomy with numbered callouts and the token behind each part, every size measured (instances of the one Button set, switched by its Size property), usage as do and do-not pairs, keyboard and screen-reader behaviour, contrast ratios computed from the real token values for every theme, a changelog that lists what this file really contains, an annotation, ready-for-dev status, a named version and a library release | `11-enterprise/51-enterprise-component-library-on-carbon-tokens` |
| `11-enterprise/55-product-file-on-the-published-library.jsonl` | A product file built on the published library | the other side of a release: a new file that adds the library, imports its components, fills a dense page with instances (table header and rows at the xs size, header labels set by property), styles its few own layers with library text styles and library variables instead of local copies, switches a copy to Gray 100 with the library collections, and asks for updates | new document; adds `out/54-component-specification-accessibility-and-release.figcraft` as a library, so run that script first |

## Real enterprise design systems (`enterprise/`)

Four complete design-system files published by their owners (USWDS, CFPB, IBM Carbon, GitLab Pajamas), with how to study them and where to download larger ones: see [enterprise/README.md](enterprise/README.md).

## Reference designs (`files/`)

Five finished documents from the FigCraft project (MIT or Apache-2.0). Open them to see how an expert file is organised: render one, read its layer tree, then inspect a layer you want to imitate.

| File | What is in it |
|---|---|
| `files/ridgeline-app.figcraft` | A mobile app: a Components section, Home in Light and Dark, a detail screen, 17 variables |
| `files/ridgeline-design-system.figcraft` | A foundations page: colour, type, spacing, components, 29 styles |
| `files/ridgeline-onboarding.figcraft` | A four-step onboarding flow |
| `files/ridgeline-studio-dashboard.figcraft` | A 1440 px analytics dashboard with charts and a table |
| `files/glass-and-vectors.figcraft` | Glass effects, background blur, boolean and gradient vector art |

```bash
figcraft-cli render files/ridgeline-app.figcraft -o out/ridgeline-app.png
figcraft-cli convert files/glass-and-vectors.figcraft out/glass.json     # every layer and property as JSON
```

## Icons (`icons/`)

98 Lucide icons as SVG (ISC licence): 24 px box, 2 px stroke, round caps. Import one with `file.import {"path": "icons/search.svg"}`, or draw it as an editable vector the way `02-components/08-icon-set-on-a-24px-grid.jsonl` does. More at lucide.dev.

## Starter templates built into FigCraft

`template.list` names them (mobile-app, landing-page, dashboard, design-system, wireframe-kit, social-posts, slides, icon-set). `file.newFromTemplate {"template": "dashboard"}` opens one as the document the rest of the script edits. They are a quality bar and a fast start, not a finished answer: replace the content and the brand.
