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
