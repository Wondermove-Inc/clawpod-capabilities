# ClawPod Node 0.3.0

**사용자 검증을 위한 설치 파일 Pre-release입니다. 이번 배포는 설치 파일만 제공하며, 기존 Skill/Harness와 능력 레지스트리는 변경하지 않습니다.**

하나의 컴퓨터를 여러 ClawPod Agent에 동시에 연결할 수 있습니다. 기존 단일 연결의 설정과 페어링 정보는 유지됩니다.

## 변경 사항

- 설정 화면의 **Add connection**으로 Agent 연결을 추가하고, 각 Agent에서 별도로 페어링합니다.
- 연결별 시작·재연결·중지·인증 변경·제거가 다른 연결에 영향을 주지 않습니다.
- 추가 연결은 상태·인증·작업 폴더·관리형 브라우저 프로필과 로컬 포트 범위를 각각 사용합니다. Agent Gateway 주소나 포트는 변경하지 않습니다.
- 앱 자동 시작 시 실행 상태였던 연결만 재개합니다. 중지했던 연결은 중지 상태를 유지합니다.
- 연결 제거 시 해당 연결의 실행을 중지하고 설정 인증정보를 제거합니다. 런타임 장치 식별정보와 브라우저 프로필은 보존합니다.
- 연결 선택·삭제 중 늦게 도착한 상태 응답이 다른 연결의 화면을 덮어쓰지 않도록 처리했습니다.

물리적인 키보드·마우스·화면과 사용자가 명시적으로 선택한 브라우저 세션은 공유합니다. **키보드·마우스 자동 순서 조율 기능은 포함하지 않습니다.** 여러 Agent의 데스크톱 작업은 조율해서 사용하세요.

## 다운로드

| 컴퓨터 | 설치 파일 |
| --- | --- |
| Mac · Apple Silicon (M 시리즈) | [PKG 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.3.0/ClawPod-Node-0.3.0-darwin-arm64.pkg) |
| Mac · Intel | [PKG 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.3.0/ClawPod-Node-0.3.0-darwin-x64.pkg) |
| Windows · x64 | [EXE 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.3.0/ClawPod-Node-0.3.0-win32-x64.exe) |
| Linux · x64 (Debian/Ubuntu) | [DEB 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.3.0/ClawPod-Node-0.3.0-linux-x64.deb) |

각 설치 파일의 SHA-256 파일과 `release.json`을 함께 제공합니다. 두 Mac 설치 파일은 Developer ID 서명, Apple 공증, 티켓 부착 및 Gatekeeper 검증을 완료했습니다. Windows 설치 파일은 서명되지 않았습니다.

## 업데이트

1. 컴퓨터에 맞는 설치 파일로 **ClawPod Node 앱을 0.3.0으로 업데이트**하세요. 기존 설정·장치 식별정보를 유지합니다.
2. 설정 화면에서 기존 연결을 확인하고, **Add connection**으로 다른 Agent를 추가하세요. 각 Agent에서 장치를 별도로 승인합니다.
3. 능력의 다운로드 안내는 기존 버전으로 유지됩니다. 0.3.0 시험에는 이 릴리즈의 설치 파일을 직접 사용하세요.

## 검증 범위

- 앱·패키징 테스트 54건 통과. 선택형·플랫폼 테스트 9건은 기본 실행에서 제외했으며, 별도 실행 결과를 아래에 구분했습니다.
- Linux: 실제 패키지 단일·다중 Gateway 연결, Chromium 설정 UI, 오프라인 설치·재설치·0.2.4 업그레이드·제거·설정 보존 검증 통과.
- Mac ARM 및 Intel: 서명된 앱 실행·네이티브 모듈·설정 IPC·권한 사전 조회·단일 및 다중 Gateway 연결 시험 통과. Intel 실행은 Apple Silicon Mac의 Rosetta에서 수행했습니다.
- Mac 패키지 내부 파일과 Windows 압축 해제 파일 대조 및 네 플랫폼 체크섬 검증 통과.
- 독립 적대 리뷰 GO.

실제 Intel Mac, Windows 실행, 이번 버전의 Mac 신규 설치·로그인 자동 시작·설치 앱 업그레이드/제거, 데스크톱 입력·캡처 및 운영 Gateway 페어링 전체를 시험했다는 뜻은 아닙니다. 이 릴리즈는 이전과 동일하게 **Pre-release**입니다.

빌드 출처: Agent 런타임과 Node 설치 앱 소스 모두 `5ba295f82b724de46f436178e6a30b1917e35786`. 포함된 Node.js는 24.15.0입니다. 공개 릴리즈 태그는 변경하지 않은 capabilities 저장소 메인의 별도 커밋을 가리킵니다. 정확한 설치 파일 출처는 첨부된 `release.json`에 기록했습니다.

