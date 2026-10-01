# Live view design and motion

Read this when designing a live dashboard or adding feedback for changing data. It complements [design fundamentals](design-fundamentals.md) and the [live SDK guide](live-artifact/guide.md). These instructions are self-contained; no additional design skill, animation library, or network dependency is required.

## Compose the resting state first

- Identify the next decision: current step, blocked item, changed metric, or result. Give that one thing the strongest hierarchy. Put details below it in rows or disclosures; do not turn every field into a card.
- Reuse the host's palette and type roles where available. A compact title, tabular numbers, quiet dividers, and consistent spacing usually serve a status view better than a hero or decorative gradients. Respect an explicitly requested visual identity.
- Render usable content at 320 px as well as the normal panel width. Avoid giant progress numerals, clipped status labels, and controls that compete with the data.
- Put language and system/light/dark choices together when both exist. An icon-only settings trigger needs a translated accessible name and tooltip, a visible focus ring, and an adequate touch target. Escape closes its disclosure and returns focus.
- Localize titles, labels, loading/empty/stale/error states, and accessible names. Keep locale and theme selections through data refreshes. System is a useful theme default; explicit choices override the OS. Do not rely on storage in the sandbox.
- Live titles, version selection, and disabled-version fallback belong to the Portal. Avoid duplicating the host's live badge or rainbow treatment inside the HTML.

## Animate information, not polling

Compare the previous and next **visible values by stable ID**. `revision`, `updatedAt`, and stale flags alone are not evidence of a content change. Repeated snapshots, first render, locale/theme switches, and recovery with identical data should not replay update effects.

| Change | Useful treatment | Starting values |
| --- | --- | --- |
| Progress changes | Retarget a persistent fill using `transform: scaleX(...)`, origin left | 240 ms, `cubic-bezier(0.23,1,0.32,1)` |
| Row status or content changes | A low-opacity highlight over only that row, fading away | 280 ms, `cubic-bezier(0.23,1,0.32,1)`; about 8% ink overlay |
| A stage becomes complete | A small check entrance, only on the transition into done | 200 ms, scale .9 → 1 plus opacity; no bounce |
| A new row appears | Short opacity fade if it helps locate the new item | 160–200 ms ease-out |
| No visible change | Keep the same nodes and render immediately | No effect |

These are starting points, not mandatory effects. Use one or two that help the reader. Frequent updates should be quieter. Avoid bouncing numbers, animated rainbow titles, looping pulses, staggered refreshes, or replaying the whole page entrance. Numbers and status text update immediately; motion must never delay the truth.

## Keep state and interruption predictable

- Keep stable DOM nodes for unchanged rows and the progress track. Patch changed content or replace only the changed row. Do not clear the entire list on every SDK callback.
- Preserve expanded sections, focused controls, text selection where feasible, and scroll position. If a focused control must be replaced, restore focus without scrolling. A removed row must actually disappear: snapshots replace data rather than accumulating old records.
- Prefer CSS transitions for persistent values; rapid updates retarget the in-flight transition. A bounded highlight may use CSS keyframes or WAAPI. Replace/cancel an earlier highlight for the same row instead of queuing animations.
- Derive change signatures from fields that the view actually renders. Exclude synchronization metadata. Clear retained data and comparison state when the SDK contract requires a terminal clear; the next valid snapshot is a fresh initial render.
- Suppress update effects while hidden and for stale delivery. The parent owns subscriptions and polling; do not add timers to fetch or animate a fake live state.
- Use transform/opacity where possible. Scope any color fade to a small region. Do not use `transition: all`, continuous layout measurement, or a new library for a progress bar. A highlight overlay must not intercept clicks.

## Accessibility and sandbox

Honor `prefers-reduced-motion` in CSS, including when the preference changes while the view is open. For this frequently updated surface, snapping progress to its final value and removing the highlight is a good default. Keep status text/icons so color and animation are never the only signals.

```css
.progress-fill { transform-origin: left; transition: transform 240ms cubic-bezier(0.23,1,0.32,1); }
@media (prefers-reduced-motion: reduce) {
  .progress-fill { transition: none; }
  .changed::before { animation: none; opacity: 0; }
}
```

Keep native progress semantics (or a correctly labeled progressbar with current/min/max values) alongside any decorative fill. Do not announce every polling response to screen readers. Keep keyboard operations immediate and respect visible focus.

Use inline CSS/scripts and embedded assets only. Native CSS and WAAPI need no external dependencies. Static HTML does not run scripts; do not promise snapshot transitions there. Motion adds no permission to write data, call services, bypass schema compatibility, or execute disabled HTML.

## Verify actual transitions

In a real sandbox preview, deliver an initial snapshot, an identical snapshot with a new revision, a changed snapshot, and a rapid follow-up. Verify that only the changed rows animate, the bar reaches the latest value, and unchanged rows retain identity. Then change language/theme and confirm there is no data-change effect.

Also check reduced motion, light/dark, narrow width, keyboard focus, expanded sections, removal, stale/error delivery, and recovery. When available, use a Storybook story with the real HTML and SDK bridge and changing API fixtures. Inspect an intermediate animation frame and its final state; static screenshots alone do not prove motion. Report what actually ran; do not describe source inspection as runtime verification.
