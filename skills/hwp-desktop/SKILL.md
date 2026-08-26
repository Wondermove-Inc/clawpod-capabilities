---
name: "hwp-desktop"
description: "Use for opening, editing, saving, and exporting HWP/HWPX files on Linux with HOP through Desktop; use clawpod-ocr only for OCR."
---

# HWP Desktop

Linux Pod에서 HOP을 지속 가능한 앱 경로에 보관하고 기존 `desktop` 능력으로 조작한다. HOP을 한컴 공식 제품으로 표현하지 않는다.

## 경계

- HWP/HWPX 네이티브 데스크톱 열기·편집, HWP 저장, PDF 내보내기에는 이 스킬을 사용한다.
- 한컴 계정 기반 웹 편집은 한컴독스를 사용한다.
- 단순 텍스트 추출이나 OCR에는 `clawpod-ocr`을 사용한다.
- 일반 OS 창 조작은 `desktop`이 수행하며, 이 스킬은 HWP 작업 절차와 HOP 수명주기를 선택한다.

## 앱 저장 계약

- 영구 루트: `/workspace/application/hop`
- 버전별 파일: `/workspace/application/hop/versions/<version>/HOP-linux-<arch>.AppImage`
- 활성 버전: `/workspace/application/hop/current` 심볼릭 링크
- 다운로드·해시·출처 기록: 버전 디렉터리의 `provenance.json`
- 임시 다운로드는 같은 파일시스템의 staging 디렉터리에 받고 검증 후 원자적으로 이동한다.
- `/usr`, `/opt` 등 Pod overlay 경로에 영구 설치하지 않는다.
- 이전 활성 버전 하나를 보존해 롤백한다.

## 최초 연결 및 업데이트

1. `uname -m`, `/workspace` 마운트, 여유 공간을 확인한다.
2. `desktop environment.preflight`를 `prepare → run`으로 실행해 display, D-Bus, AT-SPI, backend가 모두 사용 가능한지 확인한다.
3. 사용자가 다운로드와 외부 바이너리 실행을 명시적으로 승인했는지 확인한다. 스킬 설치 자체를 실행 승인으로 간주하지 않는다.
4. 공식 HOP 사이트와 GitHub Releases의 최신 릴리스, 자산 이름, 크기, 게시 시각을 확인한다.
5. 요청 아키텍처에 맞는 공식 AppImage만 staging으로 다운로드한다. 리디렉션의 최종 호스트가 GitHub release asset인지 확인한다.
6. SHA-256을 계산하고 URL, 버전, 자산명, 크기, 해시, 확인 시각을 `provenance.json`에 기록한다. 업스트림 서명이나 공식 체크섬이 없다면 그 한계를 명시한다.
7. 실행 권한을 부여한 뒤 `--appimage-extract-and-run` 또는 직접 실행 중 환경에서 작동하는 최소 방식을 선택한다. FUSE 부재 시 추출 실행을 우선한다.
8. 빈 창 실행과 Desktop 관찰을 검증한 뒤에만 `current`를 새 버전으로 원자 교체한다. 실패하면 기존 버전을 유지한다. AppImage 프로세스 종료는 창 관리자 단축키로 추정하지 말고 Desktop 관찰로 확인한다. 검증에서 `Alt+F`는 종료가 아니라 창 메뉴를 열었으므로 종료 동작으로 사용하지 않는다.
9. 설치 완료 후에도 실제 문서 편집은 별도 사용자 요청 범위에서 수행한다. 설치 검증이 HWP/HWPX 열기, 저장, 재열기 또는 PDF 내보내기를 증명했다고 보고하지 않는다.

## 문서 작업

1. 안전한 대표 문서가 없으면 문서 동작 검증을 건너뛰고 그 제한을 보고한다. 샘플을 임의로 생성하거나 사용자 파일을 탐색 범위 밖에서 찾지 않는다. 원본을 직접 덮어쓰지 말고 작업 복사본을 만든다.
2. `desktop`으로 HOP을 실행하고 창을 새로 관찰한다.
3. 접근성 대상과 최신 revision을 사용해 파일을 연다. 좌표 클릭은 마지막 수단이다.
4. 편집 전후 파일 해시와 수정 시각을 기록한다.
5. HWP 저장은 다른 이름으로 저장해 새 파일로 검증한다.
6. HWPX는 현재 저장 지원을 가정하지 않는다. 앱이 HWPX 저장을 명시적으로 제공하지 않으면 원본 HWPX를 보존하고 HWP 또는 PDF로 별도 출력한다.
7. 저장 후 파일 존재, 크기 변화, 재열기, 핵심 텍스트와 페이지 수를 확인한다. 중요 문서는 PDF 육안 대조와 한컴오피스 최종 검수를 권고한다.
8. 결과물은 사용자가 지정한 경로에 두고 원본, 작업본, PDF의 관계를 보고한다.

## 안전과 실패 처리

- 다운로드, 업데이트, 외부 바이너리 최초 실행은 명시적 승인 후 수행한다.
- HOP은 MIT 오픈소스이며 한컴 공식 호환성 보증이 없음을 밝힌다.
- 복잡한 표, 누름틀, 수식, 글꼴, 개체, 배치의 왕복 충실도를 보장하지 않는다.
- 실행 실패 시 AppImage/FUSE, WebKitGTK, 한글 IME, X11/Wayland 문제를 분리 진단한다.
- 부분 저장이나 결과 불명 상태에서는 원본을 보존하고 자동 재시도하지 않는다. 창 닫기나 프로세스 종료도 결과가 관찰되지 않으면 반복 입력하지 않는다.
- 업데이트 실패 시 `current`를 건드리지 않고 staging을 정리한다.

## 완료 증거

- 활성 버전과 provenance SHA-256
- Desktop preflight 및 창 관찰 성공
- 대표 HWP 열기, 복사본 저장, 재열기
- 대표 HWPX 열기와 저장 제한 확인
- PDF 내보내기 및 파일 검증
- 알려진 문서 충실도 차이와 미수행 항목
