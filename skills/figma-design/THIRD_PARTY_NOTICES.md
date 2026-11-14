# Third-party material in this skill

The example scripts in `examples/01-*` to `examples/09-*` and `examples/11-enterprise/*`, `examples/check_layout.py`, `examples/verify.sh` and the documents in `references/` were written for this skill. `examples/assets/sample-scene.jpg` is a render of `examples/05-graphics/24-vector-illustration-gradients-blur-mask.jsonl`, also made for this skill. The material below comes from other projects and keeps its own licence.

| Material | Where | Source | Licence |
|---|---|---|---|
| Five reference designs | `examples/files/*.figcraft` | storytold/figcraft `examples/` at commit 24613d3fa6 | MIT or Apache-2.0, at your option. Copyright (c) 2026 ArtCraft Team and the FigCraft contributors. MIT text: `examples/files/LICENSE-MIT`. |
| 98 icons | `examples/icons/*.svg`; the same paths as vector data inside example scripts | lucide-icons/lucide at commit 55782beff3 | ISC, with the Feather-derived icons under MIT. Text: `examples/icons/LICENSE`. |
| Radix Colors values | `examples/10-token-sets/45-radix-colors-light-and-dark.jsonl` | radix-ui/colors `src/light.ts`, `src/dark.ts` | MIT. Copyright (c) 2021-2022 Modulz; Copyright (c) 2022-Present WorkOS. |
| Tailwind CSS palette values | `examples/10-token-sets/46-tailwind-palette.jsonl`; colours used across the example scripts | tailwindlabs/tailwindcss v3.4.17 `src/public/colors.js` | MIT. Copyright (c) Tailwind Labs, Inc. |
| Material Design 3 baseline colour roles | `examples/10-token-sets/47-material-3-baseline-colour-roles.jsonl` | material-components/material-web `tokens/versions/latest/sass` | Apache-2.0. Copyright 2026 Google LLC. Changed here: resolved to hex and rewritten as FigCraft variable commands. |
| IBM Carbon tokens (palette, four themes, button tokens, layout, type styles) | `examples/10-token-sets/48-ibm-carbon-four-themes-with-component-tokens.jsonl`; used by `examples/11-enterprise/*` | carbon-design-system/carbon tag v11.120.0, `packages/{colors,themes,layout,type}` | Apache-2.0. Copyright IBM Corp. 2018, 2026. Changed here: resolved and rewritten as FigCraft variable and style commands. |
| GitHub Primer functional colours, five themes | `examples/10-token-sets/49-github-primer-five-themes-with-high-contrast.jsonl` | @primer/primitives 11.10.0 (`dist/docs/functional/themes`) | MIT. Copyright (c) 2018 GitHub Inc. |
| Atlassian colour, spacing and shape tokens | `examples/10-token-sets/50-atlassian-light-dark-with-spacing-and-shape.jsonl` | @atlaskit/tokens 20.12.0 (`figma/*.json`) | Apache-2.0 (the package's `license` field; author Atlassian Pty Ltd). Changed here: rewritten as FigCraft variable commands. |
| U.S. Web Design System design kit | `examples/enterprise/uswds-design-kit.fig` (unchanged) | uswds/uswds-for-designers `figma/uswds-design-kit-beta.fig` at commit d607f4d1c1 | Public domain in the United States; CC0 1.0 elsewhere. Text: `examples/enterprise/LICENSE-USWDS.md`. No endorsement by the U.S. government is implied. |
| CFPB Design System 1.5.1 | `examples/enterprise/cfpb-design-system.fig` (unchanged) | cfpb/design-system `docs/assets/files/CFPB_Design_System_1.5.1.fig` at commit 992b6c938d | CC0 1.0. Text: `examples/enterprise/LICENSE-CFPB.txt`. The CFPB name and logo are not licensed for other uses. |
| IBM Carbon Design Kit v11, White theme | `examples/enterprise/carbon-v11-white.sketch` (unchanged) | carbon-design-system/carbon-design-kit `Carbon Design Kit - v11.0.0` at commit ac236dce37 | Apache-2.0. Text: `examples/enterprise/LICENSE-CARBON.txt`. IBM and Carbon are trademarks of IBM; the licence grants no trademark rights. |
| IBM Plex Sans, Serif and Mono (six font files embedded in the Carbon kit by its publisher) | inside `examples/enterprise/carbon-v11-white.sketch`, under `fonts/` | IBM/plex | SIL Open Font License 1.1. Copyright 2017 IBM Corp. with Reserved Font Name "Plex". Text: `examples/enterprise/LICENSE-IBM-PLEX-OFL.txt` |
| GitLab Pajamas design tokens | `examples/enterprise/pajamas-design-tokens.fig` (unchanged) | gitlab-org/gitlab-services/design.gitlab.com `ui-kit/Design tokens.fig` at commit f5a975eff0 | MIT, Copyright GitLab Inc. Text: `examples/enterprise/LICENSE-PAJAMAS.txt`. The GitLab name and logo are trademarks of GitLab. |

Command and behaviour descriptions in `references/` draw on the FigCraft documentation (`docs/cli.md`, `docs/mcp.md`; MIT or Apache-2.0) and on running the commands on ClawPod.

"Figma" is a trademark of Figma, Inc. This skill is not affiliated with or endorsed by Figma; the name describes file compatibility and the kind of work.

## MIT License (Radix Colors, Tailwind CSS, Primer primitives)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Apache License 2.0 (Material Design, IBM Carbon and Atlassian tokens)

Licensed under the Apache License, Version 2.0; you may not use these token values except in compliance with the License. The full text is in `examples/10-token-sets/LICENSE-APACHE-2.0.txt`. Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
