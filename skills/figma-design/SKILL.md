---
name: figma-design
description: "Use when the user wants a UI design, mockup, wireframe, prototype, design system, icons, vector artwork, a social or print layout or a whiteboard as an editable Figma-style file, or mentions Figma, FigJam, FigCraft or .fig. For HTML decks use frontend-slides; for generated images, clawpod-image-studio."
---

# Figma Design

ClawPod agents have **FigCraft**: a design app that does what Figma does (Applications → Graphics → FigCraft) and `figcraft-cli`, which runs the same app without a window. Every menu action is a command. You design by writing a script of commands, running it, rendering the result, **looking at it**, and fixing what you see.

```bash
figcraft-cli run screen.jsonl --out app.figcraft        # build
figcraft-cli export app.figcraft -o out/ --scale 2      # one PNG per top-level frame
python3 <this skill>/examples/check_layout.py app.figcraft   # what a small image hides: unsized frames, clipped text, overlaps
# then open every PNG and judge it before you change or deliver anything
```

Read before you start, in this order:

| File | Read it when |
|---|---|
| [references/scripting.md](references/scripting.md) | Always, once. How scripts, references, layout, components and export work, and the mistakes that cost the most time. |
| [references/design-craft.md](references/design-craft.md) | Always, once. The standards an expert holds and the checklist every frame must pass. |
| [examples/README.md](examples/README.md) | Every task. Pick the scripts closest to the job and read them in full. |
| [examples/enterprise/README.md](examples/enterprise/README.md) | A design system, an admin or back-office product, a government or regulated service, or any brief that says "enterprise". Real systems from USWDS, CFPB, IBM Carbon and GitLab, and how to study them. |
| [references/figma-map.md](references/figma-map.md) | When the task names a Figma feature and you need its commands. |

## How to work

1. **Pin the brief.** What is being made, for whom, at what size, in which language, with which brand colours and fonts. Ask only for what you cannot decide; a missing brand is yours to design.
2. **Study before drawing.** Read the nearest examples. Render a reference design from `examples/files/`, a page of a real system from `examples/enterprise/`, or a built-in template to see the level expected.
3. **Foundations first.** Colour variables (with Light and Dark when the product has both), a type scale as text styles, elevation as effect styles. Nothing later uses a raw hex or an unstyled font size.
4. **Components for anything that repeats**, with every state as a variant and content as properties.
5. **Screens from instances and auto layout.** No hand-placed x/y inside a screen except deliberate overlays.
6. **Run, render, check, look.** Export every frame, run `examples/check_layout.py` on the file, and open the images at a size where small text is readable (crop tall pages; `render` shows what `export` skips, such as sections and boards). Go through the checklist in design-craft.md line by line. Fix and re-run. Expect three or more rounds: first renders always have clipped text, a frame at the wrong size, or a gap that is off.
7. **Deliver** the `.figcraft` file, PNG or PDF exports, and a `.fig` copy when the user works in Figma. Say what is in the file, what you checked, and what you left out.

## What makes the result expert

- **Real content.** Real names, prices, dates and sentences at realistic lengths, including one that is too long. Never lorem ipsum or "Title".
- **One system.** Spacing from a 4 / 8 scale, one radius family, two typefaces at most, a neutral ramp plus one brand hue and status colours.
- **Hierarchy you can see with your eyes half closed.** One focal point per screen; size, weight and colour step down from it.
- **Every state.** Default, hover, focus, disabled, loading, empty, error. The happy path is a quarter of the work.
- **Text contrast of 4.5 : 1** or better (3 : 1 for large text and for the shapes of controls), targets of 44 px or more, and no meaning carried by colour alone.
- **A file someone else can use.** Layers named for what they are, components instead of copies, variables instead of values, pages for foundations, components and screens.
- **At enterprise scale, the system is the deliverable.** Tokens in three tiers (palette, roles, component) with a mode per theme; components with the full state and size matrix and typed properties; screens that hold up at high density; a specification with keyboard notes and contrast figures per theme, a changelog and a published library version that product files consume. `examples/11-enterprise/` builds all of this on IBM Carbon's real token values.

## The installed app is the reference

FigCraft updates often, and this skill does not assume a version. When a command or parameter here does not match:

```bash
figcraft-cli commands --filter variable      # every command whose id, label or parameters mention "variable"
figcraft-cli help export                     # a subcommand's options
bash examples/verify.sh                      # run and check every example on the installed version (in a temporary copy)
```

A failing step names the parameter it rejected and the values it accepts. Read the error, check `commands --filter`, and adapt. The examples are verified scripts, not a frozen specification.

## Working with the user's files

`figcraft-cli info design.fig` and every other subcommand read `.fig`, `.figcraft`, `.penpot`, `.sketch`, `.svg` and images directly. `info` lists pages and frames and reports anything it could not import. To change a file, run a script with `--in design.fig --out design.figcraft`; export a `.fig` again with `figcraft-cli export design.figcraft -o design.fig`. Read `examples/09-working-with-existing-files/` first: look at the structure and the colours in use before editing.

To let the user watch or take over, open the file in the app on the desktop: `figcraft app.figcraft`.

## Related skills

HTML slide decks: `frontend-slides`. The claude.ai/design canvas: `claude-design`. Decks and prototypes on the OpenDesign server: `open-design`. Generated or edited raster images: `clawpod-image-studio`. A page in the chat room: `artifact-design`.
