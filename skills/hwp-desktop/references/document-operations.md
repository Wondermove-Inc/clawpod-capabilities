# 전체 문서 작업과 Desktop recipes

실제 HWP/HWPX 작업을 시작하기 전에 읽는다. 지원 표면은 feature inventory를 기준으로 한다.

## 모든 명령의 공통 recipe

1. Observe: Desktop으로 창 목록과 UI를 다시 관찰하고 최신 revision을 얻는다.
2. Focus: HOP 창 제목, 활성 문서, 포커스 요소를 확인하고 필요한 선택 컨텍스트를 만든다.
3. Act: 접근성 target, 메뉴, 도구막대, 컨텍스트 메뉴, 관찰된 공식 단축키 순으로 사용한다.
4. Dialog: 제목, 현재 값, 대상 범위를 읽고 필요한 필드만 바꾼다.
5. Postcondition: 텍스트, 선택, 서식, 표, 페이지, 개체, 파일 또는 창 상태를 새 관찰로 확인한다.
6. Recover: 의미를 보존하는 취소/undo를 한 번 사용하고 불명확한 입력은 반복하지 않는다.

## HOP 단일 GUI 소유권과 인계

- HOP launch, focus, input, close, process cleanup 전에 concrete Desktop session/display와 HOP instance를 합친 lease key로 exclusive logical lease를 획득한다. 같은 HOP process의 여러 window는 하나의 ownership domain이다.
- lease record에는 owner session 또는 Workboard card, acquired-at, heartbeat/expiry, intended document, observed PID/window identity를 기록한다. lease owner만 해당 instance를 조작한다.
- 경쟁 owner가 있으면 `HOP_GUI_BUSY`와 current owner/retry condition을 반환하고 fail closed한다. 두 번째 worker는 focus, type, close, relaunch, kill 등 GUI/process action을 하나도 수행하지 않는다.
- lease heartbeat를 유지하되 expiry만으로 takeover하지 않는다. stale worker는 orchestrator가 cancel/reclaim하고 attempt가 stopped임을 확인하며 Desktop input을 더 이상 소유하지 않음을 재관찰해야 한다.
- stale cancellation confirmation 뒤에만 Forge-owned로 positively identified된 residual HOP/AppImage PID/window를 재관찰하고 정리한다. 다른 owner나 출처가 불명확한 process는 건드리지 않는다.
- replacement는 clean process/window preflight 후 한 fresh instance를 시작하고 새 PID/window/revision을 lease에 bind한다. 이전 coordinate, screenshot digest, context는 폐기한다.
- dirty dialog를 처리하고 owned window/process가 닫혔음을 확인한 뒤 release한다. 계속 실행할 때는 owner, document, state가 명시된 documented safe handoff만 허용한다.

## 파일과 세션

New/New Window, Open/Recent/File association, Drag/drop, Multi-window, Save/Save As/HWP/HWPX, Export PDF, Print, Close/Quit와 session recovery를 모두 다룬다.

- 모든 file read/write/hash/package action 전에 expected CIFS mount path, source, filesystem, read/write 상태, freshness, target path를 확인한다. absent, wrong-source, read-only, stale이면 file action 전에 중지하고 자동 mount/remount나 credential 사용을 하지 않는다.
- source path, size, SHA-256을 mutation 전에 기록하고 distinct work copy/output을 쓴다. 정확한 승인 없이 source를 overwrite하지 않으며 완료 전에 source를 re-hash해 동일성을 증명한다.
- HOP/AppImage process/window를 전부 관찰하고 confirmed Forge-owned residual만 정리한 후 stale process/window가 없음을 증명한다. fresh HOP PID/window/revision/title/canvas를 lease에 bind한다.
- 파일 경로·형식·덮어쓰기·dirty 상태를 확인하고 저장 파일은 해시/크기/수정 시각과 재열기로, PDF는 page count/render/representative Korean text로, 인쇄는 승인과 큐 상태로 검증한다.
- 요청·승인된 raw HWP Room delivery가 confirmed HTTP 415로 실패하면 final HWP bytes를 바꾸지 않은 one-file ZIP fallback만 사용한다. HWP hash, ZIP hash/contents와 byte identity를 기록하고 PDF는 직접 보낼 수 있다. HWP를 몰래 변환하거나 대체하지 않는다.

## 탐색, 선택, 입력, 클립보드

caret/navigation, Go To, Find/Find Again/Replace, click-drag/Shift/double/triple click/Select All, IME 입력, Cut/Copy/Paste/Delete, Undo/Redo, Format Copy/Paste, Compare Documents, Document History를 다룬다. 각 동작은 범위와 postcondition을 확인한다.

모든 clipboard write는 다음 네 phase 중 하나를 execution record에 명시한다.

1. `CONTENT_PENDING_PASTE`: document content가 clipboard에 있고 paste postcondition 전이다.
2. `CONTENT_PASTED_VERIFIED`: fresh observation에서 expected Korean anchor가 target document에 보인다.
3. `PATH_PENDING_DIALOG`: 지정한 open/save/export dialog용 path가 clipboard에 있다.
4. `PATH_CONSUMED_VERIFIED`: dialog 또는 resulting file state로 path consumption을 증명했다.

`CONTENT_PENDING_PASTE`에서는 즉시 focus/context 확립과 paste만 허용한다. path write, copy/cut, unrelated clipboard action, save/export dialog, formatting, worker handoff가 개입해서는 안 된다. clipboard 변경 가능성이 있으면 content를 rewrite하고 fresh canvas/context를 다시 확인한 뒤 paste한다. keystroke dispatch, caret movement, page count, file creation만으로 verified 상태로 올리지 않는다.

Pending content 위에 path를 쓰려는 transition은 hard error `CLIPBOARD_PHASE_VIOLATION`이며 formatting/save/export/delivery 없이 중지한다. Path clipboard는 content visibility 검증 이후 지정 dialog에만 쓰고 document content로 재사용하지 않는다. Formatting, Save/Save As, export, delivery는 `CONTENT_PASTED_VERIFIED` 이후에만 허용한다.

## 문자, 문단, 스타일

굵게, 기울임, 밑줄, 취소선, 위/아래 첨자, 양각/음각/외곽선, 글꼴/크기/장평/자간, 정렬/들여쓰기/문단 간격/줄 간격, 글머리표/문단 번호/개요 수준, style 생성/수정/적용을 다룬다.

## 표

Create/Delete, 셀 선택, 행/열 삽입·삭제, 병합·분할, 너비/높이 같게, Cell Properties, Border/Background, Caption, Formula/Block Formula, decimal/thousand separator, Transpose Copy/Paste를 다룬다.

## 쪽, 구역, 머리말/꼬리말

Page/Column Break, Page Setup, Section Settings, Columns, Page Border, Page Number/hide, Header/Footer create/prev/next/close/delete/template과 page/total/file fields를 다룬다.

## 삽입과 개체

Image, Shape, Textbox, Equation create/edit, Symbols, Bookmark, Field create/edit/remove, Footnote/Endnote, Picture/Object Properties, caption, rotate/flip, arrange, group/ungroup을 다룬다.

## 보기와 도구

Zoom/Actual/Fit, Grid/Settings, paragraph/control marks, clip, border transparency, form mode, toolboxes, Options를 다룬다.

## 충실도와 복구

- formatting/save 전에 fresh screenshot/observation에서 representative Korean anchor text가 실제 canvas에 보이는지 확인한다. paste가 ambiguous하거나 anchor가 없으면 상태를 advance하지 않고 screenshot과 blocker를 남기며 path clipboard/save를 금지한다.
- `HOP_GUI_BUSY`는 current owner가 release하거나 orchestrator cancellation/reclaim과 stopped confirmation이 끝날 때까지 기다린다. stale actor의 close/relaunch는 거부한다.
- `CLIPBOARD_PHASE_VIOLATION`은 즉시 중지하고 blank/ambiguous document를 저장하지 않는다. content rewrite와 fresh context부터 별도 recovery한다.
- mount failure는 file action 전에 resumable blocker로 남기고 별도 승인 없는 remount를 하지 않는다. source-hash mismatch는 hard failure로 outputs를 quarantine/report하고 delivery하지 않는다.
- raw HWP 415 뒤 ZIP permission이나 packaging verification이 없으면 delivery blocker로 보고하며 HWP를 변환해 우회하지 않는다.
- 텍스트, 페이지, 표, 그림/도형/수식, 글꼴, 머리말/꼬리말, 각주/미주, 쪽 설정을 작업 전후와 close/reopen/PDF에서 비교한다. 파일 대화상자 실패, 포커스/IME 오류, 부분 저장, 앱 충돌, 글꼴 대체, PDF 차이, 인쇄 불명을 분류한다. autosave/recovery와 HWPX 저장 같은 버전별 동작은 실제 UI에서 확인하며 비노출 기능은 범위를 줄이지 않고 provider 상태와 재개 조건을 보고한다.
