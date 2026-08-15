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
