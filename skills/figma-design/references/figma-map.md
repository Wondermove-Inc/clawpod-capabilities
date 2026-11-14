# Figma features and their FigCraft commands

Find the Figma feature, use the command group, read the example. `figcraft-cli commands --filter <group>.` lists a group's commands with parameters.

The second column holds what the example scripts really run (commands, or the layer properties in plain backticks). The last column holds commands that exist in the app but that no example here runs: read their parameter docs with `commands --filter` and try them on a copy first.

## Design

| In Figma | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Frames, device presets, sections | `node.create {type: section}` | `03-screens/10` | `frame.create`, `frame.presets` |
| Shapes, lines, arrows, polygons, stars | `node.create` | `05-graphics/23` | `shape.*` |
| Auto layout: direction, gap, padding, hug / fill, wrap, absolute | `node.set` layout keys, `layout.suggest` | `03-screens/*`, `09-.../44` | `layout.add` |
| Grid auto layout, spans | `layout: "grid"`, `columnTracks`, `rowTracks`, `gridAlignV` | `03-screens/16`, `11-enterprise/51` | `gridColumnSpan`, `gridRowSpan`, `layout.setTrack` |
| Constraints and resizing | `constraints`, `minWidth` / `maxWidth` | `03-screens/18` |  |
| Layout grids and guides | `grid.add` | `01-foundations/02` | `guide.add` |
| Text, rich text ranges, lists, links | `node.create {type: text}` | `05-graphics/27` | `text.style {start, end}`, `text.bulletList`, `text.link` |
| OpenType features, variable fonts | `features`, `fontVariations` | `05-graphics/27` | `text.setFeatures` |
| Text on a path | `text.onPath` | `05-graphics/27` |  |
| Fills, gradients, image fills, blend modes | `fills`, `fill.add`, `image.place` | `05-graphics/24`, `28` | `fill.set` |
| Strokes, dashes, caps, per-side borders, width profiles, brushes | `stroke.*`, `dashes`; `strokeSides` | `05-graphics/29`; `02-components/06` |  |
| Effects: shadows, blurs, noise, glass | `effects`, `effect.add` | `05-graphics/25` |  |
| Pattern fills | `fill.pattern` | `05-graphics/29` |  |
| Pen tool, vector networks, editing points | `node.create {type: vector, path}` | `05-graphics/24` | `vector.create`, `vector.edit.*` |
| Boolean groups, flatten, outline stroke, shape builder | `bool.*`, `vector.flatten`, `vector.outlineStroke` | `05-graphics/23` | `shapeBuilder.*` |
| Masks | `object.mask` | `05-graphics/24` | `isMask` on `node.set` |
| Image crop and adjustments | `image.adjust` | `05-graphics/28` | `image.crop`, `image.replace` |
| Align, distribute, tidy up, smart spacing | `align.*`, `distribute.*`, `arrange.tidy` | `09-.../44` | `arrange.spacing` |
| Group, frame selection, reorder, delete, lock, hide | `node.reorder`, `node.reparent`, `edit.delete` | `05-graphics/24`, `11-enterprise/52`, `53` | `object.group`, `object.frameSelection`, `object.toggleLock`, `object.toggleVisible` |
| Rename, batch rename, find and replace | `object.batchRename`, `edit.findReplace` | `09-.../43` | `object.rename` |
| Select similar (same fill, font, instance) | `selection.colors` | `09-.../43` | `select.same*`, `select.matching` |
| Scale tool (scales strokes, effects and text too) |  |  | `transform.scale {ids, factor}` |
| Pages | `page.add`, `page.select`, `page.rename` | `06-.../31` | `page.move` |

## Design systems

| In Figma | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Variables: collections, modes, aliases, scoping | `variable.*` | `01-foundations/01`, `10-token-sets/*` |  |
| Applying a mode to a frame or page | `variable.setMode` | `01-foundations/01` |  |
| Extended collections |  |  | `variable.extendCollection`, `variable.resetOverride` |
| Styles: colour, text, effect, grid | `style.create` | `01-foundations/02` | `style.apply`, `style.update` |
| Components and component sets (variants) | `component.create`, `component.createMultiple`, `component.combineVariants`, `component.addVariant` | `02-components/03` to `07`, `11-enterprise/51` |  |
| Component properties: text, boolean, instance swap, variant | `component.addProperty`, `component.bindProperty`, `component.properties` | `02-components/03` |  |
| Instances, overrides, swap, reset, detach | `instance.create`, `instance.setProperties` | `03-screens/10` | `instance.swap`, `component.resetInstance`, `component.detach` |
| Slots, exposed nested instances, preferred values | `component.makeSlot`, `instance.slotInsert`, `component.exposeInstance` | `02-components/09` |  |
| Component playground (try property values without changing the file) |  |  | `component.playground {id, properties, language, path}` |
| Libraries: publish, enable, place, update | `library.publish`, `library.add`, `library.place`, `library.import`, `library.applyStyle`, `library.bindVariable`, `library.setVariableMode`, `library.updates`, `file.rename` | `08-.../41`, `42`, `11-enterprise/51`, `54`, `55` | `library.acceptUpdates`, `library.swap` |
| Import and export variables (JSON, CSS) | `variable.export` | `08-.../38` | `variable.import` |

## Prototyping

| In Figma | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Interactions, triggers, actions, transitions, easing | `proto.interaction.add` | `04-prototyping/19` | `proto.interaction.set`, `proto.interaction.remove` |
| Overlays, swap and close | `openOverlay`, `closeOverlay` actions | `04-prototyping/19` | `swapOverlay` action |
| Smart animate, interactive components | `changeTo` on variants with `transition: {type: "smartAnimate"}` | `04-prototyping/22` |  |
| Variables in prototypes, expressions, conditionals, mode switching | `setVariable`, `conditional`, `setVariableMode`, `proto.action.add`, `proto.evaluate` | `04-prototyping/20` |  |
| Scrolling, fixed layers, scroll to | `overflow`, `scrollPosition: "fixed"`, `scrollTo` | `04-prototyping/21` | other `scrollPosition` values (sticky) |
| Flows and starting points | `proto.flow.add` | every prototype example |  |
| Device frame and background | `proto.settings` | `04-prototyping/19` |  |
| Present and preview |  |  | `proto.present`, `proto.preview` (they play in the desktop app) |

## Dev Mode

| In Figma | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Inspect values with token names | `inspect.properties` | `08-.../38` |  |
| Code: CSS, HTML, React, Vue, Tailwind, SwiftUI, Compose, Flutter | `inspect.code {language}`, `inspect.componentCode` | `08-.../38`, `39` |  |
| Annotations and categories | `annotation.add`, `annotation.addCategory` | `08-.../38` |  |
| Measurements | `devMode.addMeasurement` | `08-.../38` | `measure.distances`, `measure.padding` |
| Ready for dev, changed since, completed | `node.set {devStatus}`, `inspect.readyForDev` | `08-.../38` |  |
| Dev resources (links) | `devResource.add` | `08-.../38` |  |
| Code Connect | `codeConnect.set`, `codeConnect.export` | `08-.../39` | `figcraft-cli connect publish` (from a code repository) |
| Export settings and assets | `export.add`, `inspect.assets` | `02-components/08`, `08-.../38` | `file.exportLayers` |
| Compare changes |  |  | `dev.compare`, `dev.resolveChange` |

## Collaboration and file management

| In Figma | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Comments, replies, resolve, mentions | `comment.add`, `comment.reply`, `comment.resolve`, `comment.list` | `08-.../40` |  |
| Version history, named versions, restore | `file.saveVersion`, `version.list` | `08-.../40` | `version.restore` |
| Branches: create, review, update from main, merge | `branch.create`, `branch.review`, `branch.merge` | `08-.../40` | `branch.updateFromMain` |
| Live multiplayer, share links, follow, cursor chat |  |  | `collab.*` (needs a FigCraft server and the app or its MCP server; a one-shot `run` has no network) |
| Open, import, save as, duplicate | `--in` / `--out` | `09-.../43` | `file.open`, `file.import`, `file.saveAs` |
| Starter templates | | examples/README.md | `template.list`, `file.newFromTemplate` (run by hand while writing this skill; all eight templates open) |

## FigJam (boards)

| In FigJam | Used in the examples | Example | Also in the app, not run here |
|---|---|---|---|
| Sticky notes, authors, colours | `board.sticky` | `07-boards/34` | `board.setColor` |
| Shapes with text, connectors, labels | `board.shape`, `board.connector`, `board.addConnected` | `07-boards/35` | `board.label` |
| Mind maps | `board.mindMap`, `board.mindMapAdd` | `07-boards/36` |  |
| Tables | `board.table` | `07-boards/36` | `board.tableEdit` |
| Sections | `node.create {type: section}` | `07-boards/34`, `37` |  |
| Stamps | `board.stamp` | `07-boards/34` |  |
| Board templates | `board.templates` | `07-boards/34` | `board.template` |
| Timer and voting |  |  | `board.timer`, `board.vote` |
| Marker, highlighter, washi tape |  |  | `board.ink`, pointer tools (need the app) |

## Other Figma products

| In Figma | Here |
|---|---|
| Figma Slides | Slides are 1920 x 1080 frames exported as one PDF: `06-.../31`. For a browser deck use the `frontend-slides` skill. |
| Figma Buzz (assets in bulk from a template) | `data.fill` with rows and formats: `06-.../30`. |
| Figma Draw (illustration) | Vectors, brushes, patterns, text on a path: `05-graphics/*`. |
| Figma Sites (publishing a site) | Not available. `inspect.code {language: "html"}` or `"tailwind"` gives code for a frame; hosting is another skill's job. |
| Figma Make and AI generation | You are the generator: write the script. `data.fill` fills copies with content. |
| Plugins and widgets | `plugin.*`, `widget.*` run plugins in FigCraft's own format (*not exercised*); do not count on a Figma community plugin being available. Most plugin jobs (rename, tidy, charts, content fill, contrast) are a short script here. |

## File formats

| Format | Open | Save |
|---|---|---|
| `.figcraft` | yes | yes (the working format: keeps everything) |
| `.fig` (Figma) | yes; `info` lists what was not imported | yes, experimental: comments, Dev Mode data and prototype device settings are left out |
| `.jam` (FigJam) | yes, per the FigCraft documentation (not tried here) | no |
| `.penpot`, `.sketch` | yes | `.penpot` yes |
| Figma REST file JSON | yes | `.json` (FigCraft JSON) |
| SVG | yes, as editable layers | yes |
| PNG, JPG, WebP | yes, as an image layer | yes |
| PDF | no | yes, vector, with bleed, crop marks and CMYK options |
