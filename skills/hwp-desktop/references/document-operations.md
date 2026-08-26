# 전체 문서 작업과 Desktop recipes

실제 HWP/HWPX 작업을 시작하기 전에 읽는다. 지원 표면은 feature inventory를 기준으로 한다.

## 모든 명령의 공통 recipe

1. Observe: Desktop으로 창 목록과 UI를 다시 관찰하고 최신 revision을 얻는다.
2. Focus: HOP 창 제목, 활성 문서, 포커스 요소를 확인하고 필요한 선택 컨텍스트를 만든다.
3. Act: 접근성 target, 메뉴, 도구막대, 컨텍스트 메뉴, 관찰된 공식 단축키 순으로 사용한다.
4. Dialog: 제목, 현재 값, 대상 범위를 읽고 필요한 필드만 바꾼다.
5. Postcondition: 텍스트, 선택, 서식, 표, 페이지, 개체, 파일 또는 창 상태를 새 관찰로 확인한다.
6. Recover: 의미를 보존하는 취소/undo를 한 번 사용하고 불명확한 입력은 반복하지 않는다.

## 파일과 세션

New/New Window, Open/Recent/File association, Drag/drop, Multi-window, Save/Save As/HWP/HWPX, Export PDF, Print, Close/Quit와 session recovery를 모두 다룬다. 파일 경로·형식·덮어쓰기·dirty 상태를 확인하고 저장 파일은 해시/크기/수정 시각과 재열기로, PDF는 페이지와 대표 화면으로, 인쇄는 승인과 큐 상태로 검증한다.

## 탐색, 선택, 입력, 클립보드

caret/navigation, Go To, Find/Find Again/Replace, click-drag/Shift/double/triple click/Select All, IME 입력, Cut/Copy/Paste/Delete, Undo/Redo, Format Copy/Paste, Compare Documents, Document History를 다룬다. 각 동작은 범위와 postcondition을 확인한다.

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

텍스트, 페이지, 표, 그림/도형/수식, 글꼴, 머리말/꼬리말, 각주/미주, 쪽 설정을 작업 전후와 재열기/PDF에서 비교한다. 파일 대화상자 실패, 포커스/IME 오류, 부분 저장, 앱 충돌, 글꼴 대체, PDF 차이, 인쇄 불명을 분류한다. autosave/recovery와 HWPX 저장 같은 버전별 동작은 실제 UI에서 확인하며 비노출 기능은 범위를 줄이지 않고 provider 상태와 재개 조건을 보고한다.
