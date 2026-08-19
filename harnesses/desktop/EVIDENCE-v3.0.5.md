# Evidence — Desktop v3.0.5

## Static / unit

- `py_compile` clean for engine + all modified libs.
- `scripts/validate.py`: OK. `scripts/sync_registry.py`: regenerated (version + digests).
- Parity test now requires engine dispatch for the 7 former stubs
  (`synth=set()`), and the direct-dispatch test covers the observation commands.

## Live pod smoke (RND, sooyoung; ran from /tmp, workspace untouched)

Observation commands (real data):
- `window-list` → real X window ids + geometry, e.g. `{"windows":[{"id":"543",...}]}`.
- `screen-list` → `{"screens":[{"name":"screen","width":1920,"height":1080,...}]}`.
- `clipboard-inspect` → `{"hasText":true,"length":3,"targets":["UTF8_STRING",...]}`.
- `download-inspect` → `{"directory":"/root/Downloads","files":[]}`.
- `app-get NoSuchApp` → clean not-found error.

Interactive commands — full live GUI sweep, **10/10 PASS**:
- `file-dialog-open /tmp/fdt.txt` against `zenity --file-selection` → dialog closed,
  zenity returned exactly `/tmp/fdt.txt` (no autocomplete corruption).
- `file-dialog-save /tmp/newfile.txt` against `--save` → closed, exact return.
- `file-dialog-cancel` → dialog closed.
- `dialog-respond No` against `zenity --question` → dialog closed.
- `window-maximize` → width 1920 (work area, panel-excluded); `window-restore` →
  back to 300; `window-resize 400 300` → width 400; `window-minimize` /
  `window-activate` → no error. (throwaway xclock window)
- `pointer-move 500 400` → pointer at X=500 Y=400.

## Root causes fixed (all surfaced only by live GUI testing)

- Dialog detection required MODAL/ACTIVE; Zenity's chooser is SHOWING+VISIBLE only.
- The GTK location entry has no persistent AT-SPI node and autocompletes as you
  type, so char-by-char entry corrupted the tail; clipboard paste is atomic.
- A single AT-SPI "not found" was mistaken for a confirmed dialog; now polled.
