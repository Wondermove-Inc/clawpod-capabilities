# Real enterprise design systems

Four complete design-system files, published by the organisations that run them and unchanged here. They are the level to aim for when a brief says "design system", "enterprise", "admin console" or "government service". Study how they are built; do not copy their brands into someone else's product.

| File | System | What is inside | Licence |
|---|---|---|---|
| `uswds-design-kit.fig` | U.S. Web Design System (federal government) | 59 pages: typography, colour and spacing tokens, 42 component pages, templates. About 34,000 layers, 766 components (483 of them variants in 84 sets), 1,195 variables with theme modes | Public domain / CC0 1.0: `LICENSE-USWDS.md` |
| `cfpb-design-system.fig` | Consumer Financial Protection Bureau | Colour tokens, text and grid styles, components, patterns, page templates. About 15,000 layers, 733 components, 345 variables | CC0 1.0: `LICENSE-CFPB.txt` |
| `carbon-v11-white.sketch` | IBM Carbon v11, White theme (Sketch library) | 42 pages: 34 component pages built from instances (Data table, UI Shell, Form, Notification, Modal and others) and a `symbols` page that holds the 3,000 mains. About 71,000 layers. Symbols open as components; a Sketch file has no component sets or variant properties | Apache-2.0: `LICENSE-CARBON.txt`. The six IBM Plex font files embedded in it are OFL-1.1: `LICENSE-IBM-PLEX-OFL.txt` |
| `pajamas-design-tokens.fig` | GitLab Pajamas | The token architecture on its own: 1,022 variables, 167 styles, default and dark modes. Only three sample components: study it for tokens | MIT, Copyright GitLab Inc.: `LICENSE-PAJAMAS.txt` |

Sources and exact commits are in `../../THIRD_PARTY_NOTICES.md`. The names and logos in these files belong to their owners; using a file to learn from it does not grant the right to use them.

## How to study one

```bash
figcraft-cli info uswds-design-kit.fig | grep '^page'                              # the page list is the system's table of contents
figcraft-cli render uswds-design-kit.fig --page "Button" -o out/uswds-button.png   # one component page
figcraft-cli render carbon-v11-white.sketch --page "Data table" -o out/carbon-table.png
```

Then read structure instead of pixels. `info` prints `page <id> "<name>"` for every page, and `node.find` searches only the first page unless it is given a `root`, so pass the id of the page you want. Run a small script with `--in` (the Button page of the USWDS kit is page 8455 in that list; read the id from your own `info` output):

```jsonl
{"command": "node.find", "as": "sets", "params": {"root": 8455, "type": "COMPONENT_SET", "limit": 20}}
{"command": "component.properties", "params": {"id": {"$ref": "sets", "field": "ids/0"}}}
{"command": "node.get", "params": {"id": {"$ref": "sets", "field": "ids/0"}, "outline": true}}
{"command": "variable.list", "params": {}}
```

```bash
figcraft-cli run study.jsonl --in uswds-design-kit.fig --out /tmp/study.figcraft
```

The second step answers with the set's properties (for this button: `type` with seven values, `state` with six, two icon booleans and a text property), the third with its 42 variants by name. Component sets are in the USWDS and CFPB files. In the Carbon Sketch file the mains sit on the `symbols` page: give `node.find` that page's id as `root`, `"type": "COMPONENT"` and a `name` such as `"button"`.

What `info` says it left out matters when you read a file. The USWDS kit binds 627 properties to variables of a team library that is not in the file: those layers keep their last colour but show no binding, so read its token structure from the collections that are in the file (`variable.list`), not from every layer.

What to take from them:

- **Page structure.** A start page, foundations (tokens), one page per component, patterns, templates, and internal or deprecated pages kept apart.
- **Token tiers.** Raw palette, then roles (surface, text, border, state), then component-level tokens; themes and density as modes. Compare `pajamas-design-tokens.fig` with `../10-token-sets/48-...` (Carbon) and `49-...` (Primer).
- **Component completeness.** Count the variants of one component and the properties it exposes. Every state exists, including focus, disabled, error and read-only.
- **Documentation in the file.** Usage notes, do and do-not pairs, anatomy, accessibility notes sit beside the component.
- **Naming.** Slash paths, `Property=Value` variants, no unnamed layers.

## Fonts

The files name fonts that are not installed on ClawPod, so text is drawn in a fallback and some labels look tighter or looser than intended (`figcraft-cli info` prints `missing font` lines). The open ones can be installed for the current user; FigCraft reads `~/.local/share/fonts`:

```bash
mkdir -p ~/.local/share/fonts && cd ~/.local/share/fonts
for w in Light Regular SemiBold; do curl -fsSLO "https://raw.githubusercontent.com/IBM/plex/master/packages/plex-sans/fonts/complete/ttf/IBMPlexSans-$w.ttf"; done   # IBM Plex Sans, OFL-1.1
```

USWDS uses Public Sans, Source Sans Pro and Roboto Mono (open; zips in `uswds/uswds-for-designers/fonts/`). CFPB uses Avenir Next and GitLab uses GitLab Sans: check their licences before installing. The examples in `../11-enterprise/` name IBM Plex Sans and are meant to be rendered with it installed.

## More, downloaded when needed

These are too large to ship or their licence asks for more care. All open in FigCraft (`.fig`, `.sketch`, `.penpot`).

| File | Size | Licence | Download |
|---|---|---|---|
| GitLab Pajamas component library `.fig` (1,979 components, 773 variables) | 12 MB | MIT | `https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com/-/raw/main/ui-kit/%F0%9F%93%99%20Component%20library.fig` |
| GitLab Pajamas patterns and page templates `.fig` | 11 MB | MIT | same folder, `Patterns%20and%20Page%20Templates.fig` |
| IBM Carbon v11 Gray 10 / 90 / 100 themes `.sketch` | 5 MB each | Apache-2.0 | `https://raw.githubusercontent.com/carbon-design-system/carbon-design-kit/master/Carbon%20Design%20Kit%20-%20v11.0.0/Carbon%20Design%20System%20(Gray%20100%20theme).sketch` |
| USWDS Sketch library and project file | 2 and 4 MB | Public domain / CC0 | `https://raw.githubusercontent.com/uswds/uswds-for-designers/main/sketch/libraries/uswds.sketch` |
| Ant Design library `.penpot` (tokens with Light / Dark and density modes) | 12 MB | CC BY 4.0 (credit required) | `https://raw.githubusercontent.com/penpot/penpot-files/main/antd-library.penpot` |
| Material Design 3 `.penpot` | 17 MB | CC BY 4.0 (credit required) | `https://raw.githubusercontent.com/penpot/penpot-files/main/Material%20Design%203.penpot` |

Kits that live only on Figma Community (Primer, Atlassian, Fluent, Spectrum, the Google Material 3 kit) need a Figma login to duplicate: ask the user to export the `.fig` and send it. Their token values are published openly and are already here as `../10-token-sets/48` to `50`.

## The same level, built from scripts

`../11-enterprise/` builds an enterprise library and product screens on the real Carbon token values: a Kind x State x Size button set of 125 variants, input states, table header and rows in five densities with typed cell properties, application chrome as components, a console with a side panel in two themes and two densities plus its empty, loading and no-permission states, a provisioning wizard, an audit log, a component specification with keyboard notes and contrast figures per theme, a changelog, a published library release, and a product file that consumes it. Read those scripts for *how*; open the files above for *how far*.
