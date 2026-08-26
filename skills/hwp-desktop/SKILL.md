---
name: "hwp-desktop"
description: "Use for opening, editing, saving, and exporting HWP/HWPX files on Linux with HOP through Desktop; use clawpod-ocr only for OCR."
---

# HWP Desktop

Linux에서 HOP의 전체 실용 기능을 기존 `desktop` 능력으로 조작한다. HOP을 한컴 공식 제품으로 표현하지 않는다.

## 라우팅과 구성

- HWP/HWPX 파일·세션, 편집, 서식, 표, 쪽/구역, 머리말/꼬리말, 삽입/개체, 보기/도구, 저장/내보내기/인쇄에는 이 스킬을 사용한다.
- 단순 텍스트 추출이나 OCR에는 `clawpod-ocr`을 사용한다.
- 웹 오피스, 다른 네이티브 앱, 일반 OS 조작에는 이 스킬을 선택하지 않는다.
- 모든 GUI 동작은 `desktop`의 `prepare → run`으로 실행한다. 이 스킬은 HOP 기능 선택, Desktop recipe, 문서 검증, 앱 수명주기를 제공한다.

## 필요한 참조

- 실제 문서 작업 전 [references/document-operations.md](references/document-operations.md)를 읽는다.
- 기능 범위 점검 또는 HOP 버전 변경 시 [references/feature-inventory.md](references/feature-inventory.md)를 읽는다.
- 설치, 상태, 업데이트, 롤백, repair 시 [references/app-lifecycle.md](references/app-lifecycle.md)를 읽는다.

## 시작 전

1. 요청을 feature inventory의 기능군과 명령에 매핑한다. 지원되는 실용 표면을 제한 중심으로 축소하지 않는다.
2. 입력, 출력, 대상 문서/범위/표/개체, 원본 보존, 외부 부수효과를 확인한다.
3. 원본을 보존하고 명시적 작업 복사본과 출력 경로를 사용한다. 사용자가 정확히 승인한 경우에만 기존 파일을 덮어쓴다.
4. `desktop environment.preflight`로 display, D-Bus, AT-SPI, backend를 확인한다.
5. `/workspace/application/hop/current`의 AppImage와 provenance를 검증한다. 없거나 손상되었으면 app lifecycle로 bootstrap 또는 repair한다.
6. HOP을 실행하고 창을 관찰한다. 각 동작 직전에 최신 revision, 활성 창, 문서 제목, 포커스, selection/context를 확인한다.

## 전체 작업 순서

1. **세션:** New/Open/Open Recent/file association/drag-drop/multi-window 중 요청에 맞는 경로로 문서를 준비한다.
2. **탐색과 편집:** navigation, selection, text/IME, clipboard, undo/redo, find/replace, go-to, history/compare를 수행한다.
3. **서식:** 문자/문단 모양, 스타일, 정렬, 간격, 글머리표/번호/개요 수준을 적용한다.
4. **구조:** 표 생성·편집·수식·속성, 쪽/구역/다단/경계, 머리말/꼬리말과 필드를 조작한다.
5. **삽입/개체:** 그림, 도형, 글상자, 수식, 기호, bookmark/field, 각주/미주를 삽입하고 object properties, caption, rotate/flip, arrange, group을 조작한다.
6. **보기/도구:** zoom/fit, grid/marks, clip, form mode, toolboxes, options를 설정한다.
7. **출력:** Save, Save As, 지원 형식 저장, PDF export, Print를 요청대로 수행한다.
8. **검증:** 저장 파일을 재열고 텍스트, 페이지, 표, 개체, 수식, 글꼴, 머리말/꼬리말, 각주/미주, 쪽 설정과 PDF/인쇄 결과를 대조한다.
9. **종료:** dirty 상태와 복구 대화상자를 처리하고 문서 창과 HOP 프로세스 종료를 관찰한다.

## Desktop 실행 계약

모든 명령은 `observe → focus/context → action → dialog review → postcondition → recovery` 순서를 따른다.

- 접근성 target과 식별 가능한 메뉴/도구막대/컨텍스트 메뉴를 우선한다.
- 파일 대화상자는 전체 경로와 확장자를 확인한다. 필요하면 검증된 drag/drop으로 전환한다.
- 좌표 클릭은 같은 revision에서만 쓰는 마지막 수단이다.
- 명령 후 예상 상태를 새 관찰로 확인하기 전 다음 입력을 보내지 않는다.
- 불명확한 저장, 인쇄, 창 닫기, 프로세스 종료를 반복 입력하지 않는다.

## 버전별 provider 사실

HWP/HWPX 저장, autosave/recovery, 패키징, 서명, IME, WebKitGTK 등은 설치된 HOP 버전과 UI에서 확인한다. 미지원 또는 비노출 상태는 정확한 실행 메모와 재개 조건으로 보고하되 스킬의 전체 기능 범위를 인위적으로 줄이지 않는다.

## 완료 증거

- 활성 HOP 버전, AppImage SHA-256, provenance와 `current` 대상
- Desktop preflight, 창/revision/focus/context 관찰
- 실행한 기능과 대화상자 입력, postcondition
- 입력·작업본·출력의 경로, 해시, 크기, 수정 시각
- 재열기 및 텍스트·페이지·표·개체·수식·글꼴·쪽 요소 충실도
- PDF/인쇄 결과, 복구 조치, provider 제한, 미수행 항목과 재개 조건
