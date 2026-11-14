# Driving FigCraft with scripts

Everything here was run on ClawPod. The installed app is still the authority: `figcraft-cli commands --filter <word>` prints the parameters a command takes today.

## The command line

| Command | Use |
|---|---|
| `figcraft-cli run script.jsonl [--in file] --out file.figcraft` | Run a script on a new document, or on `--in`. Saves by the extension of `--out`. |
| `figcraft-cli info file [--json]` | Pages, top-level frames with ids and sizes, counts, missing fonts, import notes. |
| `figcraft-cli export file -o out/ [--scale 2] [--page NAME]` | One file per top-level frame of the page. |
| `figcraft-cli export file -o hero.png --node "Hero"` | One layer, by name or id. The extension picks png, jpg, webp, svg, pdf, fig, penpot or xml. |
| `figcraft-cli export file -o deck.pdf` | Every top-level frame of the page as one PDF, in reading order. |
| `figcraft-cli render file -o page.png [--scale 2] [--page NAME]` | The whole page as one image: the overview shot. |
| `figcraft-cli convert in out` | By extension. `convert x.figcraft x.json` dumps every layer and property. |
| `figcraft-cli commands [--filter TEXT] [--json]` | The command list with parameter docs. |
| `figcraft x.figcraft` | Open the file in the desktop app. |

Inputs can be `.figcraft`, `.fig`, `.penpot`, `.sketch`, `.svg`, an image, or Figma REST file JSON. Print options for PDF: `--bleed 3mm --crop-marks --cmyk`.

## Scripts

A script is JSON lines: one step per line, `//` lines are comments. A JSON array of the same steps also works.

```jsonl
// A card with a title
{"command": "node.create", "as": "card", "params": {"type": "frame", "name": "Card", "width": 320, "props": {"layout": "vertical", "padding": 24, "gap": 12, "sizingV": "hug", "fill": "#FFFFFF", "cornerRadius": 16}}}
{"command": "node.create", "params": {"type": "text", "parent": {"$ref": "card"}, "text": "Cedar Hollow Loop", "props": {"fontSize": 20, "fontStyle": "Bold", "sizingH": "fill"}}}
```

- **All or nothing.** If one step fails, nothing is saved and the document is as it was. The failing step prints `"ok": false` with the reason.
- **References.** Name a step with `"as"`. `{"$ref": "card"}` anywhere in a later step is the `id` that step returned. For another part of the result add `"field"`: `{"$ref": "copy", "field": "ids/0"}`, `{"$ref": "map", "field": "children/1/id"}`. Names must be unique in a script.
- **Results.** One JSON line per step on stdout. To read values back (a layer tree, generated code, exported tokens), parse those lines.
- **Selection.** New layers become the selection, and most commands act on `ids` when given, else on the selection. Pass `ids` in scripts; do not rely on the selection.
- **Probing.** To try several things without losing the run, wrap them: `{"command": "command.batch", "params": {"onError": "continue", "commands": [...]}}` reports each inner step separately. Steps inside a batch can reference only names defined inside that batch.

Errors are precise: an unknown parameter lists the ones the command takes, a bad value lists the allowed values. Fix from the error text.

## Finding and reading layers

```jsonl
{"command": "node.find", "as": "hit", "params": {"name": "Home screen", "type": "FRAME"}}
{"command": "node.get", "params": {"id": {"$ref": "hit", "field": "ids/0"}, "outline": true}}
{"command": "node.get", "params": {"id": 12, "fields": ["name", "width", "height", "fills"]}}
```

`node.find` matches `name` and `text` as case-insensitive **substrings**, in document order, parents first. "Home" also matches "Home indicator", and a layer in an earlier frame wins. Give screens and components names nothing else contains, or search inside a `root`. `type` is exact: `FRAME`, `TEXT`, `INSTANCE`, `COMPONENT`, `COMPONENT_SET`, `RECTANGLE`, `VECTOR`.

## Layers and properties

`node.create {type, name, parent, x, y, width, height, text, path, props}` with `type` one of frame, rectangle, ellipse, polygon, star, line, arrow, vector, text, section, component, slice. `props` takes the same keys as `node.set {ids, props}`.

- `x`, `y` are relative to the parent frame, y down. Inside auto layout they are ignored unless `absolute: true`.
- Colours: `"#RRGGBB"` or `"#RRGGBBAA"`. `fill` and `stroke` take a colour, `"none"`, or `{"$var": "text/primary"}` to bind a variable. For several paints use `fills: [...]`.
- Gradient: `{"type": "linearGradient", "stops": ["#7048E8", "#1098AD"], "from": [0.5, 0], "to": [0.5, 1]}`; also `radialGradient`, `angularGradient`, `diamondGradient`.
- Strokes: `strokeWeight`, `strokeAlign` (inside, center, outside), `strokeSides: [top, right, bottom, left]` as a weight per side for a single-edge border (`[0, 0, 1, 0]` is a 1 px bottom line, `[0, 0, 0, 3]` a 3 px left accent; `true` only ever means 1, whatever `strokeWeight` says), `dashes: [6, 6]`, `strokeCap`, `strokeJoin`.
- `cornerRadius` is a number or `[tl, tr, br, bl]`. A frame crops its children by default; `clip: false` lets shadows and overflow show. `opacity` is 0 to 1.
- Effects: `effects: [{"type": "dropShadow", "color": "#0F172A1F", "offset": [0, 12], "radius": 24}]`; also `innerShadow`, `layerBlur`, `backgroundBlur`, `noise`, `glass`.
- Styles by name: `textStyle`, `fillStyle`, `effectStyle`.

## Auto layout

```json
{"layout": "vertical", "gap": 16, "padding": [24, 20, 24, 20], "mainAlign": "spaceBetween", "crossAlign": "center", "sizingH": "fill", "sizingV": "hug"}
```

- **A new frame is 100 x 100 and fixed.** Every auto layout frame needs `sizingH` and `sizingV` (`hug`, `fill`, or `fixed` with a width or height). Forgetting this is the most common cause of clipped text and squashed buttons.
- `fill` only works on a child of an auto layout frame, and a parent cannot hug an axis its child fills.
- Text wraps only when its width is set: `sizingH: "fill"` or a `width` with `textAutoResize: "height"`. For one line with an ellipsis: `textAutoResize: "height", maxLines: 1` (the `truncate` mode gives a box shorter than the line and cuts descenders). `wrapStyle: "pretty"` keeps lines full but never leaves one word alone on the last line: put it on every paragraph that wraps. `wrapStyle: "balance"` evens out the lines of a headline.
- `padding` is one number or `[top, right, bottom, left]`. `mainAlign`: min, center, max, spaceBetween. `crossAlign`: min, center, max, baseline.
- A spacer that pushes a footer down is an empty frame with `sizingH: "fill", sizingV: "fill", fill: "none"`.
- Wrap: `wrap: true` with `crossGap`. Grid: `layout: "grid"`, `gridColumns`, `columnTracks: [44, "2fr", "1fr", "auto"]`, `columnGap`, `rowGap`; children take `gridColumnSpan`, `gridAlignH`, `gridAlignV`. A cell centres vertically only when its row track has a size: for a one-row grid of fixed height add `gridRows: 1, rowTracks: ["1fr"]` and put `gridAlignV: "center"` on each child.
- Cards in one row share a height when the row has a fixed height and each card has `sizingV: "fill"`.
- A layer over others inside auto layout (a back button on a photo): `absolute: true` with `x`, `y` and `constraints`.
- Outside auto layout, `constraints: {"horizontal": "leftRight", "vertical": "top"}` decide what happens on resize: left, right, leftRight, center, scale.

## Text and fonts

Props: `fontFamily`, `fontStyle` ("Regular", "Medium", "Semi Bold", "Bold"), `fontSize`, `lineHeight` (px or `"150%"`), `letterSpacing` (px or `"-2%"`), `textAlign`, `textCase`, `textDecoration`, `features: {"tnum": true}`, `fontVariations: {"wght": 550}`.

`text.fonts` lists the installed families, and `text.fonts {"family": "Inter"}` lists the styles one family really has. **A style the family lacks is accepted and silently drawn in another weight**, so check before choosing weights:

| Family | Styles on ClawPod |
|---|---|
| Inter | Regular, Italic, SemiBold, Bold (no Medium, no Light) |
| Montserrat | Thin to Black with italics; variable `wght` axis |
| Roboto | Thin to Black, condensed widths; variable `wght` and `wdth` axes |
| Noto Sans, Noto Serif | Thin to Black with italics and condensed widths |
| Lato, Merriweather | Regular, Italic, Bold |
| Noto Sans CJK KR | Thin, Light, DemiLight, Regular, Medium, Bold, Black (no SemiBold) |
| Noto Serif CJK KR | ExtraLight, Light, Regular, Medium, SemiBold, Bold, Black |

A missing weight is drawn at the nearest one the family has, which for Inter Medium and Light is Regular. `"Semi Bold"` and `"SemiBold"` are the same style. `text.fonts {"family": "Montserrat", "axes": true}` shows variable axes. `text.missingFonts` (or `missing font` lines from `figcraft-cli info`) names families a file uses that are not installed. `text.fit {ids, maxLines}` shrinks a fixed-width headline until it fits.

## Variables and styles

```jsonl
{"command": "variable.createCollection", "params": {"name": "Theme", "modes": ["Light", "Dark"]}}
{"command": "variable.create", "params": {"collection": "Theme", "name": "bg/surface", "type": "color", "values": {"Light": "#FFFFFF", "Dark": "#0F172A"}}}
{"command": "variable.create", "params": {"collection": "Components", "name": "button/bg", "type": "color", "value": {"alias": "brand/primary"}}}
{"command": "variable.bind", "params": {"ids": [12], "field": "cornerRadius", "variable": "radius/md"}}
{"command": "variable.setMode", "params": {"ids": [40], "collection": "Theme", "mode": "Dark"}}
{"command": "style.create", "params": {"type": "text", "name": "Heading/1", "value": {"fontFamily": "Inter", "fontStyle": "Bold", "fontSize": 32, "lineHeight": 40, "letterSpacing": "-1.5%"}}}
```

Types: color, number, string, boolean. Bindable fields include fill, stroke, width, height, opacity, cornerRadius, gap, padding sides, `characters` and `visible`. A Dark version of a screen is a duplicate with `variable.setMode` on the copy. `variable.export {format: "css" | "json"}` returns the tokens. Style types: text, paint, effect, grid.

## Components

1. Build the layer tree as a frame, then `component.create {ids: [frame]}` (or `component.createMultiple` for many).
2. Variants: name each frame `Kind=Primary, State=Default`, make them components, then `component.combineVariants {ids}` and rename the set. Lay them out in a grid first; the set wraps them where they are.
3. Properties: `component.addProperty {id: <a layer in the first variant>, name, type}` with type text, boolean or instanceSwap binds that layer. In every other variant: `component.bindProperty {layer, property, field}` with field `characters`, `visible` or `mainComponent`.
4. Use: `instance.create {component, parent}` then `instance.setProperties {ids, properties: {"Kind": "Secondary", "Label": "Export"}}`. Set `sizingH: "fill"` on the instance where it should stretch.
5. To override inside an instance, find the layer in it (`node.find {root: instance, ...}`) and `node.set` it. Fills, text and visibility override cleanly; do not move or restructure layers inside an instance: change the main, or resize the instance.
6. Slots (`component.makeSlot`, `instance.slotInsert`) and exposed nested instances (`component.exposeInstance`): see `examples/02-components/09-...`. To set a nested instance from outside, find it inside the outer instance and call `instance.setProperties` on it (`examples/11-enterprise/52-...`). Switching the outer instance to another variant can reset the nested instance's variant properties (it does when the variants nest different mains; its text stays): look at the render and set them again.
7. A new instance of a set is the set's top-left variant. Name every variant property the design depends on, size included, instead of relying on that default.
8. A third axis is cheaper derived than drawn: `component.addVariant {id, property, value}` duplicates a variant with one property changed; bind what differs (`variable.bind {field: "height"}`) and place the copy. `examples/11-enterprise/51-...` turns 25 variants into 125 this way.
9. A state of a whole screen is `edit.duplicate` plus the properties that differ, never a redraw. New layers go to the end of their parent: `node.reparent {ids, parent}` into the same parent moves one to the end, `edit.delete {ids}` removes one (`examples/11-enterprise/52-...`, `53-...`).

## Libraries

The system file: `file.rename` (the library takes the file's name), `file.saveVersion`, `library.publish`, then save it. A product file: `library.add {path}`, then `library.import {library, component}` gives a local main for `instance.create`; its own layers take `library.applyStyle`, `library.bindVariable` and `library.setVariableMode`, so nothing is copied by hand. `examples/11-enterprise/54-...` and `55-...` are the two halves.

## Prototypes

```jsonl
{"command": "proto.interaction.add", "params": {"id": 21, "trigger": {"type": "onClick"}, "action": {"type": "navigate", "dest": 40}, "transition": {"type": "push", "direction": "left"}, "durationMs": 300, "easing": "easeOut"}}
{"command": "proto.flow.add", "params": {"start": 12, "name": "First run"}}
{"command": "proto.settings", "params": {"device": "iPhone 16"}}
```

Triggers: onClick, onHover, onPress, onDrag, mouseEnter, mouseLeave, mouseDown, mouseUp, `{"type": "afterDelay", "ms": 800}`, keyPress. Actions: navigate, back, openOverlay (with `position`, `background`), closeOverlay, swapOverlay, scrollTo, changeTo (between variants), openUrl, setVariable (with `expression: "count + 1"`), setVariableMode, conditional. A scrolling screen is a frame taller than the device with `overflow: "vertical"`; a header that stays put has `scrollPosition: "fixed"`.

## Vectors, booleans, masks, images

- `vector` layers take SVG path data in `path`. When joining several SVG `<path>` elements into one string, each element's leading relative `m` must become an absolute `M`.
- Arcs and rings are ellipses: `arcStart` and `arcSweep` in degrees, `arcInner` 0 to 1.
- `bool.union | subtract | intersect | exclude {ids}` returns the boolean group; `vector.flatten` makes it one path; `vector.outlineStroke` turns a stroke into a fill.
- `object.mask {ids}`: the **bottom** layer becomes the mask. Use `node.reorder {id, index: 0}` first if it was created last.
- An image is a paint. `image.place {path, target: <shape id>, mode: "fill"}` puts it in a shape (the shape is the crop); without `target` it makes a layer. Relative paths resolve from the folder you run in.
- Icons: draw the path in a 24 x 24 frame with `constraints` set to scale, then resize the frame; or `file.import {path: "icons/search.svg"}`.

## Boards

Whiteboard commands (`board.sticky`, `board.shape`, `board.connector`, `board.mindMap`, `board.table`, `board.stamp`) work only in a board file. Start the script with `{"command": "file.newBoard", "params": {"name": "Retro"}}`. In a design file, draw a flow arrow with a `line` or `arrow` layer.

## Checking the result

```bash
figcraft-cli export app.figcraft -o out/ --scale 2            # one PNG per top-level frame
figcraft-cli render app.figcraft -o out/page.png --scale 2    # the whole page: sections, loose layers, boards
python3 examples/check_layout.py app.figcraft                 # unsized frames, text too short or outside its frame, cut-off children, overlapping frames
```

- `export -o dir/` writes top-level **frames** only. Components kept in a section are not top-level frames, and on a board every shape and stamp is one, so a folder export gives no components and a file per sticky: use `render` (or `export --node NAME`) for those.
- Look at images at a size where 12 px text is readable. A 393 x 3000 page or a row of ten slides shrunk to one image hides clipped text: export frames separately, or crop tall ones into pieces before viewing.
- `check_layout.py` reads the file, so it sees what a small image hides: frames left at 100 x 100, text shorter than its line or outside its screen, a frame cut off by its auto-layout parent, top-level frames that overlap. It exits 1 and names each layer to look at; `NOT CHECKED` means the installed version's file layout changed and the check is yours to do by eye. Clean output is necessary, not sufficient.
- For numbers rather than pixels: `node.get {id, fields: ["width", "height", "x", "y"]}`, or `figcraft-cli convert app.figcraft app.json`.

## Mistakes that cost the most time

- Forgetting `sizingH` / `sizingV` on a frame, so it stays 100 x 100.
- A new frame clips its content. A row or column that only arranges cards cuts their shadows at its edge: set `clip: false` on layout-only frames, and keep clipping for screens, rounded cards and scrolling areas.
- `sizingV: "fill"` on cards inside a row that hugs: there is nothing to fill and they collapse. For cards of equal height give the row a height and let each card fill it.
- Text without a width, so it never wraps and runs off the frame.
- Searching for a name that is a substring of another layer's name.
- Leaving main components on the same page as screens, so they appear in the PDF. Put them in a section beside the screens or on their own page (`page.add`, then `page.select {index: 0}` to return).
- Reading a successful run as a correct design. A script can pass and still clip, overlap or misalign. Only the rendered image and `examples/check_layout.py` tell you.
- After `branch.create`, later steps run on the branch until `branch.merge`.
- A library must be saved to a file before another file can `library.add` it.
