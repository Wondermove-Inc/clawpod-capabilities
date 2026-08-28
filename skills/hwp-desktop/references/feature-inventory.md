# HOP 기능 인벤토리

HOP 또는 bundled rhwp가 바뀌었을 때와 기능 누락을 점검할 때 읽는다. 기준은 HOP `golbin/hop` main의 `608d54bbc75af4142bc69c2c2b50c0c217b45731` checkout에 포함된 rhwp submodule `f137b4c9468eaff5bb43e25108e9c9d39a2ed15b`이며, 실제 배포 버전에서는 UI 관찰로 다시 확인한다.

## HOP 네이티브 셸

HOP `apps/desktop/src-tauri/src/menu.rs`, README, desktop commands에서 확인한 표면:

- File: New, New Window, Open, Open Recent, Save, Save As, Export PDF, Print
- Edit: Undo, Redo, Cut, Copy, Paste, Find
- Table: Select Cells, Merge Cells, Split Cells
- View: Zoom In/Out, Actual Size, Fit Page, Fit Width
- Window: minimize, close; multi-window, drag/drop, `.hwp`/`.hwpx` file association
- 앱 수명주기: bootstrap, status, update, rollback, repair, quit

## 편집기 명령 표면

rhwp studio `src/command/commands/*.ts`에서 확인한 명령을 기능군별로 모두 다룬다.

- **파일/세션:** new, open, recent, clear recent, save, save as, save as HWP, save as HWPX, page setup, print, about
- **선택/탐색/편집:** select all, delete, cut/copy/paste, undo/redo, find/find again/find-replace, go to, format copy/paste, compare documents, document history
- **문자/문단:** bold, italic, underline, strikethrough, superscript, subscript, emboss, engrave, outline; font size, character ratio/spacing; left/center/right/justify/distribute/split alignment; line spacing; paragraph/character shape; style dialog/apply style; bullets, numbering, outline levels
- **표:** create/delete; select cells; insert/delete rows and columns; merge/split; equal width/height; cell properties; border/background; caption; formula/block formula; decimal/thousand separators; transpose copy/paste
- **쪽/구역:** page and column breaks; page/section setup; one/two/three/left/right columns and column settings; page border; new page number; hide page properties
- **머리말/꼬리말 (Header/Footer):** create, previous/next, close/delete, template, hide, insert page number/total pages/file name
- **삽입:** image, shape, textbox, equation/create/edit, symbols, bookmark, field/create/edit/remove, footnote, endnote and endnote shape
- **개체:** properties, picture properties/delete, caption; rotate/flip; arrange front/back/forward/backward; group/ungroup
- **보기/도구:** zoom/fit; grid and grid settings; paragraph/control marks; clipping; border transparency; form mode; basic/format toolboxes; options

## 실행 계약

1. 기능 요청을 위 목록의 정확한 군과 명령에 매핑한다.
2. Desktop으로 현재 메뉴, 도구막대, 컨텍스트 메뉴, 단축키를 관찰한다. 배포 버전에서 노출되지 않은 명령을 추측 실행하지 않는다.
3. document operations의 공통 Desktop recipe를 적용한다.
4. 명령의 can-execute 조건이 문서/선택/표/개체 컨텍스트를 요구하면 먼저 그 컨텍스트를 만든다.
5. 명령 후 해당 기능군의 postcondition을 확인하고 결과 파일 또는 문서 상태를 검증한다.

HWPX 저장 차단, autosave/recovery 부재 등 버전별 사실은 HOP `docs/DEVELOPMENT.md`와 실제 UI에서 확인해 실행 판단에만 사용한다. 기능군 전체를 스킬 범위에서 제외하는 근거로 사용하지 않는다.
