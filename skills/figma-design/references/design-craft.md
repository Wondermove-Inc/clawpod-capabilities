# Design craft

What separates a file a senior designer would sign from one that merely runs. The numbers are defaults; a brief or a brand overrides them, a whim does not.

## Before any layer

Write down, in a sentence each: who uses this and where, the one thing each screen is for, the content it must hold, the platform and frame size, the brand (colours, typeface, tone) or that there is none yet. If a brand exists, take its colours and fonts from the user's files (`examples/09-working-with-existing-files/`) instead of inventing.

## Layout and spacing

- **One scale**: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96. No 13, no 22.
- **Proximity carries meaning.** Things that belong together sit closer than things that do not: 4 to 8 inside a group, 12 to 16 between items, 24 to 32 between groups, 48 and up between sections.
- **Frames**: phone 393 x 852 (the iPhone 16 preset; `frame.presets` lists the others, and `proto.settings {device}` should name the same device), margins 16 to 24. Tablet 768 or 834 wide. Desktop 1440 wide with content held to 1200 to 1280 and 12 columns, gutter 24.
- **Padding is consistent per container type.** Every card in a product has the same padding; every screen the same side margin.
- **Everything aligns to something.** Shared left edges, a common baseline, columns. Centre a whole screen only when it has one message (empty state, confirmation).
- **Radius is a family**: for example 6 for inputs and chips, 10 to 12 for buttons, 16 to 20 for cards, full for pills. An inner radius is the outer radius minus the padding between them.

## Typography

- Two families at most; one is usually enough. Two or three weights.
- A scale with a ratio near 1.2 to 1.33: for example 12, 13, 15, 17, 20, 24, 32, 48.
- Body 15 to 17 on phones, 16 on desktop. Nothing meant to be read under 12.
- Line height: 140 to 160% for body, 110 to 130% for headings, tighter as size grows.
- Tracking: 0 for body, -1% to -3% for large headings, +6% to +10% for small capitals.
- Line length 45 to 75 characters. Left-align running text. Centre only short blocks of three lines or fewer.
- Numbers in tables use tabular figures (`features: {"tnum": true}`) and align right.
- **Korean, Japanese, Chinese**: line height 150 to 170%, tracking -1% to -2%, no italics, weights from the family's real list (Noto Sans CJK KR has Regular, Medium, Bold). Korean wraps between any two syllables and the app has no keep-all setting, so a line can break in the middle of a word: put line breaks at phrase boundaries yourself (`\n` in the text), or change the width or the copy until each line ends on a word.
- **No orphans.** Paragraphs get `wrapStyle: "pretty"`, which never leaves one word alone on the last line; a headline gets `wrapStyle: "balance"`; a fitted headline uses `text.fit` (it avoids one-word last lines by default).

## Colour

- A neutral ramp does most of the work; one brand hue marks what matters; status colours (success, warning, danger) appear only for status.
- Semantic tokens, not hues: `bg/canvas`, `bg/surface`, `text/primary`, `text/secondary`, `border/subtle`, `brand/primary`, `danger/fg`. Screens bind to these. See `examples/01-foundations/` and `examples/10-token-sets/`.
- **Contrast** (WCAG AA): 4.5 : 1 for text, 3 : 1 for text of 24 px and up (or 19 px bold) and for the outlines of controls and icons. That includes white text on a brand button (many brand 500 / 600 steps fail; go a step darker), the outline of an input or checkbox (a pale 200 / 300 border fails; keep a separate, darker control-border token), and tertiary text in Dark (it needs its own lighter value, not the Light one). Compute it when unsure: relative luminance L = 0.2126 R + 0.7152 G + 0.0722 B on linearised channels (c / 12.92 if c <= 0.04045, else ((c + 0.055) / 1.055) ^ 2.4, with c from 0 to 1), ratio = (L lighter + 0.05) / (L darker + 0.05). Grey placeholder text on white is the usual failure.
- Never signal with colour alone: an error also has an icon and words.
- Dark mode is not inverted light mode. Surfaces get lighter as they rise, not shadowed; pure black and pure white are avoided; brand colours shift a step lighter. Build it with a Dark mode on the same variables, then render it and look.

## Depth

- Borders are 1 px in a subtle neutral. Use a border or a shadow to separate a surface, rarely both.
- Shadows are soft, low and layered: a tight one for the edge plus a wide one for the lift, each around 6 to 16% opacity of a dark neutral, offset down. A shadow you notice is too strong.
- Three elevation levels are enough: cards, menus and popovers, dialogs.

## Components

- Every interactive component has: default, hover, pressed, focus (a visible 2 px ring), disabled, and loading or error where they apply.
- Touch targets are 44 x 44 or larger on iOS and 48 x 48 on Android, even when the glyph inside is 20.
- One primary button per view. Secondary and tertiary actions step down in weight.
- Icons come from one family at one stroke weight, at 16, 20 or 24, aligned to the text beside them. Do not use emoji as icons.
- Text in components is a property; anything optional is a boolean property; anything swappable is an instance-swap property. Nobody should need to detach.
- Names read as paths: `Button`, `Input / Search`, `icon/search`. Variants read `Kind=Primary, State=Hover`.

## Content

- Write the real words. Buttons say what happens ("Save changes", not "OK"). Errors say what went wrong and what to do.
- Use realistic data: names of different lengths, a price with cents, a date, a long title that truncates. Design for the longest, not the prettiest.
- Empty, loading and error states are part of the screen, not an afterthought. See `examples/03-screens/15-...`.

## File structure

- Pages: Cover (optional), Foundations, Components, then one page per flow or platform. Old explorations go to an Archive page, not the bin.
- Frames are named for the screen and state, numbered in flow order: `Checkout / 2 Delivery`, `Checkout / 2 Delivery · error`.
- No "Frame 482", "Rectangle 12", "Group 7". Layers are named for their role: Header, Avatar, Price.
- Frames, not groups, so layout and constraints work.
- Related screens sit in a row, states of one screen in a column under it, with a gap of 100 or more.

## Enterprise products and design systems

Large organisations do not buy screens; they buy a system that hundreds of people can build with for years. See `examples/enterprise/README.md` for real ones and `examples/11-enterprise/` for scripts.

- **Tokens in tiers.** Palette (every raw colour, never bound by products), roles (background, layer, field, border, text, icon, support, focus) whose values are aliases into the palette, then component tokens where a component needs its own. Themes, high-contrast variants and density are **modes** of the same variables, not copies of the file.
- **Every component is a matrix.** Kind x state at least, size as a property, and the states products forget: focus, disabled, read-only, invalid, loading, skeleton. Count variants against a real system before calling a component done.
- **Properties instead of overrides.** Text, visibility and swaps are properties; a nested part with its own variants (a status tag in a table row) is an exposed instance. A product team should never detach.
- **Density is designed.** Data-heavy screens need compact rows (24 to 32 px) as well as comfortable ones (48); bind heights to size tokens so density is one property.
- **Tables are the core screen.** Toolbar with search and filters, batch actions on selection, sortable headers, a status column that is not colour alone, row overflow menu, pagination, and a side panel or detail view. Design the empty, loading, error and no-permission versions.
- **Long flows show where you are.** Progress indicator, a summary that stays visible, validation that names the field and blocks the step, draft saving, a way back.
- **Documentation is part of the file.** For each component: anatomy with numbered parts and their tokens, sizes with measurements, do and do-not pairs, keyboard and screen-reader notes, and contrast ratios computed from the token values for every theme.
- **Releases.** A changelog that says added, changed, deprecated or fixed and whether products must act; a named version; a published library; proposals on a branch that is reviewed before merge.
- **Brand fonts.** An enterprise system names its own typeface. Install it before rendering (`~/.local/share/fonts`), or the review happens in a fallback face with different widths.

## Marketing, slides and print

- One idea per slide or post; the headline carries it. Supporting text is half the headline's size or less.
- On a 1920 x 1080 slide nothing is smaller than 28 px, body is 40 to 48, and the content fills the slide: a slide whose lower half is empty needs a larger point, a supporting row, or to be merged with its neighbour.
- **A chart is never a bare shape.** It has a title that states the point, values on an axis or on the marks, labelled categories, and a legend when there is more than one series.
- Re-set a design for each ratio; do not scale it. A leaderboard and a story are different compositions of the same message.
- Print: sizes in points (1 pt = 1/72 inch; A4 595 x 842, A3 842 x 1191), art that touches an edge extends 3 mm past it, text stays 5 mm or more inside, export with bleed and crop marks. See `examples/06-marketing-and-print/32-...`.

## Review every render against this list

Open every exported frame at a readable size and run `examples/check_layout.py`. Deliver only when every line is true.

1. No text is clipped, overflows its container or collides with another layer, and no descender is cut.
2. Every frame is the size it should be; nothing is left at 100 x 100, nothing is cut off by its parent, and no two frames on a page overlap.
3. Left edges, baselines and gaps line up; equal things have equal spacing; cards in a row are the same height.
4. Squinting, there is one clear focal point, then a second, then the rest.
5. Every text colour is at 4.5 : 1 or better on its background, in Light and in Dark, including text on brand-coloured buttons.
6. Tap targets are 44 or more, control outlines are visible (3 : 1), and there is one primary action.
7. The content is real and consistent with itself (filters match the rows, totals match the items), and the longest item fits or truncates cleanly.
8. Icons share one family and weight and sit centred on their text line.
9. The unhappy states exist: empty, loading, error, disabled.
10. Fonts in the render are the ones asked for (no silent fallback to another weight or family), and no line ends on a single word or breaks inside a Korean word (sticky notes and board shapes wrap by themselves: keep their text short instead).
11. No area is empty by accident: a frame half blank is a layout that has not been finished.
12. In the file: colours and text are bound to variables and styles, repeated parts are instances, layers are named.

## Signs of amateur or machine-made work

Fix these on sight: a purple-to-blue gradient chosen for no reason; everything centred; five font sizes within 2 px of each other; a different radius on every card; grey text too pale to read; heavy black shadows; cards nested in cards nested in cards; a border and a shadow and a tint on the same box; emoji standing in for icons; placeholder copy; hex colours typed straight onto layers; x / y positions inside a screen; buttons of slightly different heights; a Dark mode that is only a black background.
