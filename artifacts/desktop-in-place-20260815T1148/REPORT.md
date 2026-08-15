# Desktop existing-session in-place validation

- Target: existing `DISPLAY=:99` XFCE session and its existing D-Bus address.
- Forbidden lifecycle actions: none performed. No Xvfb, dbus session, portal, or XFCE session was started/stopped/restarted; no process was killed; no display/DPI/theme setting was changed.
- Preflight: `succeeded`, checks `{"atspi": true, "backend": true, "dbus": true, "display": true}`.
- Gateway invariant: PID and listener snapshots matched before/after observation, app launch attempts, and S2 previews.
- Real Skill to Harness S0/S1: app/window/UI/dialog observation, screenshots, image fallback attempt, disposable-file launch, and settings launch were exercised.
- Visual QA: screenshots showed no opened note/settings window. The file launch backend returned exit 0 while explicitly warning `Window not detected`; this was a false success.
- Corrective change: `app.launch` now fails with `POSTCONDITION_NOT_CONFIRMED` when backend output says no window was detected. Added regression coverage.
- Image fallback: deterministic self-template localization returned `TARGET_NOT_FOUND`; no coordinate click was attempted.
- S2 actions were exact-previewed but not dispatched because the Desktop skill requires fresh digest-bound approval. Request digests: `{"preview-drag-drop": "68ad7416f06595ca3f238f3a8ce15df44302c9610f3acf74ca1568eeae5f610d", "preview-file-dialog-open": "008e5cce9662fd7a96c1da43174d5df8fe072a94f393dba8ae8bcfd25ab9a281", "preview-image-click": "a3dd3595e2ad1b1d9bd3a0079789e91676697f797d6736029049a02f970ae4c5", "preview-keyboard-type": "f192ebca8043afe4108bfd7d60e44035d32322b178a5b6d4627c7f9f28988d61"}`.
- Routing: description now states WHEN/CAN/BOUNDARY/COMPOSITION in natural language; collision fixture covers Browser/Playwright DOM, node remote screen, typed API, OCR, and Image Studio boundaries.
- Verification: 33 Desktop/routing tests passed; all 38 capability entries validated.
- Publication: not performed.

## Approved S2 execution

- Summary: `{"allScreenshotsIdentical": true, "approvedActions": {"approved-drag": {"durationMs": 296, "error": "STALE_TARGET", "rc": 20, "status": "failed"}, "approved-file-dialog": {"durationMs": 8, "error": "TARGET_NOT_FOUND", "rc": 20, "status": "failed"}, "approved-image": {"durationMs": 326, "error": "STALE_TARGET", "rc": 20, "status": "failed"}, "approved-keyboard": {"durationMs": 15, "error": "TARGET_NOT_FOUND", "rc": 20, "status": "failed"}}, "descriptionExactEquality": true, "descriptionSha256": "1b9b7668bd39d840f452a6073c33b0c9f407de9f6deaf1a30ea4e403b3799973", "gatewayListenersInvariant": true, "gatewayPidInvariant": true, "postActionScreenshotSha256": {"screen-after-drag.png": "1222842e9469c83178917d5b7593367c997087273e5cb536edc4ce4dae50a9f6", "screen-after-file-dialog.png": "1222842e9469c83178917d5b7593367c997087273e5cb536edc4ce4dae50a9f6", "screen-after-image.png": "1222842e9469c83178917d5b7593367c997087273e5cb536edc4ce4dae50a9f6", "screen-after-keyboard.png": "1222842e9469c83178917d5b7593367c997087273e5cb536edc4ce4dae50a9f6"}}`.
- All four exact approved invocations were attempted. File-dialog and keyboard reached the backend and failed `TARGET_NOT_FOUND`; drag and image fallback failed closed as `STALE_TARGET` before input. Visual QA found no visible app/modal/change and identical screenshots. No unsafe, duplicate, or dropped input occurred because no input was dispatched after failed targeting.
- Genuine blocker: the approved digests bind non-current placeholder target identities and inputs; the disposable window is not visible. A new observation-derived target and new digest-bound approval are required before any successful S2 action.

## Placeholder-binding correction and fresh previews

- Corrected the Harness to emit observation-derived target identities, bind keyboard input to a fresh target, bind coordinate/image targets to a fresh screenshot, and capture screenshots to a fresh run-scoped path instead of silently reusing `/tmp/desktop_screenshot.png`.
- Visible source window: `{'display': ':99', 'windowId': '52428807', 'title': 'Settings', 'screen': {'width': 1920, 'height': 1080}, 'screenshot': 'artifacts/desktop-in-place-20260815T1148/fresh-targets/screen-settings-final.png', 'screenshotDigest': '9d392ab66fe894f7a4babb32c99d7966e8796b28c02028af1d31b5af3a4a0dac', 'visibleBounds': [538, 261, 844, 534]}`. Visual QA confirmed focused XFCE Settings at bounds 538,261,844,534 with no modal.
- `pointer-click` digest `a0f76c42612778ee6755f2e06d638602f5adf5a089145bfb294c4fa01842db6b`; intended effect: Focus only; no setting activation or value change; executed: false.
- `pointer-drag` digest `0963e3c7f9bb527a28a62aa803807494d4185d1168b46e880b75996169f743f2`; intended effect: Move disposable Settings window exactly 50 px right without resizing or changing settings; executed: false.
- `keyboard-type` digest `98e67f1a69b2a8d282df3000aaa6bea0e0cc27518781c4fe40676583e8565264`; intended effect: Type literal display into focused Settings search; do not press Enter; executed: false.
- `image-click` digest `4afadac727195b7f556990ba79853cb9e8bb7d0adc3b23d4e28ac423027043e3`; intended effect: Focus the visible Settings search field only; no text or setting change; executed: false.
- File-dialog preview intentionally omitted: no file dialog was visibly present, so creating another non-current target would repeat the placeholder defect.
- Gateway PID/listeners matched before/after S0/S1 observation, visible-window focus, capture, and preview generation. S2 actions were not executed.

## Approved fresh digest execution and region-bound refinement

- Executed the four Room-230-approved digests exactly. The first attempt exposed an unhandled screenshot-metadata shape (`screenshot` object vs path) before dispatch; after correction, all four failed closed as `STALE_TARGET`. No S2 input was dispatched and the visible Settings state remained unchanged.
- Root cause: full-screen digest included unrelated changing pixels outside the target window. Replaced it with a stdlib PNG-decoded visual-region digest bound to the visible Settings bounds or image template region. This preserves visual freshness while excluding the unrelated panel clock.
- Region stability proof: `{'expected': '42b6f71599fa79064f6b2ae3265c2a1de1a5cdc465a63f6c0609c27436fd8352', 'actual': '42b6f71599fa79064f6b2ae3265c2a1de1a5cdc465a63f6c0609c27436fd8352', 'stable': True}` across independent captures.
- New `pointer-click` digest `6da262b22a0611ea9f811f66ca7270fdaab4ae266738684c5fb27ec223c45717`; exact intended effect: Focus only; no setting activation or value change; executed: false.
- New `pointer-drag` digest `c4fe51e611ae4e67012a882ca1975264b53eb2dc205d8ba3ca2ddc4097d7d945`; exact intended effect: Move disposable Settings window exactly 50 px right without resizing or changing settings; executed: false.
- New `keyboard-type` digest `d90f91f65ed60fed36a32b3a2e8c043638da7399817c4d5e7fe59035531a5e0f`; exact intended effect: Type literal display into focused Settings search; do not press Enter; executed: false.
- New `image-click` digest `a8c953dc8b7366946777242ee4ab60f80db3fb2a8eb1c9b2064a78e934947519`; exact intended effect: Focus the visible Settings search field only; no text or setting change; executed: false.
- These four new digests received bundled standing approval in Room 230.

## Final approved region-bound execution

- `image.click`: succeeded in 1498 ms; exact search-region focus-only effect, empty search, unchanged settings/window bounds, no modal.
- `pointer.click`: succeeded in 1391 ms; focus/category-highlight only, unchanged settings/window bounds, no modal.
- `pointer.drag-drop`: succeeded in 1356 ms; requested `[+50,0]`, observed `[+50,0]`, 0 px endpoint error, unchanged size/settings, no modal. The window was restored to its original geometry afterward.
- `keyboard.type`: literal `display` was visibly entered in 1496 ms without Enter or setting activation. The backend text finder could not confirm the clipped text and returned fail-safe `OUTCOME_UNKNOWN`; screenshot QA resolved the real outcome. Search text was cleared afterward.
- Final Settings state: empty focused search, original position/size, no setting value change, no modal.
- Idempotency replay: image/click/drag returned cached success in 0 ms without duplicate input; the prior unknown keyboard outcome was blocked in 0 ms and was not replayed.
- Safety totals: false input 0, duplicate input 0, dropped/unsafe input 0, unresolved real outcomes 0, recovery 100%. Detailed metrics: `fresh-targets/final-in-place-metrics.json`.

## Exact installation, live Gateway use, rollback, and pre-PR gate

- Installed commit `676667b75603121bb7e6d7646dcd2fbd7821bc99` byte-for-byte into `/workspace/skills/desktop` and `/workspace/harnesses/desktop`; source/installed digest diff was empty.
- Moved the discovery-visible `.prev` copies into reversible artifact backups. This removed the pre-existing duplicate Harness-name quarantine without deletion.
- Gateway validation succeeded, trust state became `trusted`, and prompt/run eligibility were true. Live Gateway `harness.run.prepare → harness.run` for installed `ui.observe` succeeded on the existing `DISPLAY=:99` Settings target in 77 ms (`hrun_503a3a0bd5d7009b6c0dd888`).
- Exact rollback restored both prior live roots and their `.prev` discovery copies. Gateway validation reproduced the prior duplicate-name quarantine. Exact reinstall then restored the candidate, source/installed digest diff remained empty, validation/trust returned green, and post-reinstall live Gateway run succeeded in 83 ms (`hrun_2f3ce79e6ed64f0f89aa6f5c`).
- Installed non-provenance tests: 28 passed. Installed precision benchmark with explicit source provenance: all 17 gates passed, 36,000 events/3,600 equivalent seconds, 0 failures, digest `8b268ed967320ec3ffb709584b491425a1656b6726ecda61cbc9fd65acab05c2`. Source Desktop/routing tests: 38 passed. Registry: 38 entries validated.
- Latest-main gate after `git fetch origin main`: `origin/main=c3db3fe62a9f5115029b986c7bd47dbb9d820f81`, merge-base is exactly the same commit, branch is 10 commits ahead and 0 behind.
- Gateway PID/listeners matched the original snapshots through approved actions, restoration, installation, rollback, reinstall, Gateway live runs, and final checks. No Xvfb/D-Bus/portal/XFCE/Gateway process lifecycle action occurred.
- Push, PR, publication, deployment, and Gateway/session restart were not performed.

## Corrective OUTCOME_UNKNOWN closure and final gate

- Diagnosed the remaining keyboard uncertainty precisely: `xdotool mousemove --sync` can wait until the action deadline when the pointer is already at the requested coordinate. The v7 checkpoint expired before dispatching text; post-action screenshot confirmed an empty focused search, so it was reconciled without replay.
- Removed `--sync` only from coordinate keyboard pointer positioning and retained focus verification plus post-action readback. Added regressions for the already-at-target deadlock and bounded visual postcondition confirmation.
- A new fresh target, digest, idempotency key, and standing-approval receipt were used for v8. `keyboard.type` succeeded in 2819 ms with exact argv literal `display`, active-window match, unchanged 834x500 geometry, changed search region, and `postconditionConfirmed=true`. Visual QA showed the filtered Appearance result, no Enter-triggered modal or setting change; at the existing oversized dark-theme rendering the field visibly clips the left `dis` and shows suffix `play`. Search state was cleared afterward.
- The earlier successful v4 image focus, pointer focus, and exact +50 px drag remained checkpointed and were not replayed. Their readbacks prove 0 px drag error, unchanged size/settings, and no modal; window position was restored.
- Safe app/file-dialog/editor/file-manager/modal/fallback coverage remains evidenced by the prior in-place bundle and real-session matrix. No absent file dialog was synthesized in the existing session, avoiding a placeholder target; unsupported/absent targets continued to fail closed.
- Source final gate: 40 Desktop/routing/Gateway-prepare tests passed; all 38 capability entries validated after registry regeneration.
- Transactional candidate cycle at `/workspace/artifacts/desktop-inplace-install-20260815T1240`: source/installed digest diff empty, installed version 3.0.0, installed live preflight succeeded with backend/display/D-Bus/AT-SPI all true, then prior live roots were restored byte-for-byte (content hashes identical). Gateway PID 665 and its three listener snapshots were invariant throughout install, live use, and rollback.
- Latest-main gate refreshed: `origin/main=c3db3fe62a9f5115029b986c7bd47dbb9d820f81`, merge-base exactly equals origin/main, branch 0 behind. No rebase was needed.
- Final corrective commit is recorded after this report update. No push, PR, publish, release, deploy, merge, or process restart was performed.

## Same-position precision-action deterministic closure

- Extended the same-position deadlock correction to coordinate click, image click, and every drag trajectory move. All non-accessibility precision pointer dispatch now omits `mousemove --sync`; pre-dispatch focus verification and post-action active-window/geometry/readback remain mandatory.
- Fresh approved reruns, never checkpoint replay: v9 image focus succeeded in 1436 ms, v9 pointer focus succeeded in 1421 ms, v10 keyboard literal succeeded in 2739 ms, and v11 exact +50 px drag succeeded in 1283 ms with 0 px error and unchanged 834x500 size. Search text and window position were restored.
- The v10 first drag targeted client geometry rather than the decoration and produced no movement; its `OUTCOME_UNKNOWN` was visually/readback-resolved as no effect and not replayed. v11 used a fresh target/digest/key at the observed decoration coordinate and succeeded.
- Regression coverage asserts no `--sync` across keyboard, coordinate click, image click, and drag argv construction. Gateway PID/listeners remained invariant around every fresh observation, preview, execution, cleanup, and restore.
