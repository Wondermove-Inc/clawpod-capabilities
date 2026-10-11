## 변경 사항

- **커넥션 이름 지정·변경:** Connection settings에서 선택적으로 이름을 입력하고 저장하면 목록과 선택한 연결의 제목에 표시됩니다. 이름을 비우면 Gateway 주소로 표시합니다.
- **컴퓨터 이름과 분리:** Connection name은 이 앱에서 연결을 구분하는 이름입니다. Agent에 전달되는 Computer display name은 그대로 유지됩니다. 기존 이름 없는 설정도 그대로 사용할 수 있습니다.
- **삭제 버튼 표시 개선:** Remove connection을 접힌 설정 밖의 Start / Reconnect / Stop 옆으로 옮겼습니다. 확인창에 저장된 이름과 Gateway 주소를 함께 표시합니다.
- **기존 연결 동작 유지:** 이름이 같아도 별도 연결로 유지합니다. 삭제는 선택한 연결만 중지하고 설정·인증정보를 제거하며, 장치 ID와 브라우저 프로필 등 런타임 데이터는 보존합니다. 기본 연결을 삭제하면 미설정 상태로 남습니다. 취소하면 변경하지 않습니다.

설정 저장은 기존과 같이 실행 중인 선택한 연결을 재시작합니다. 다른 연결에는 영향을 주지 않습니다. Gateway 프로토콜, 페어링, 포트 할당, Agent 런타임과 능력 카탈로그는 변경하지 않았습니다.

## 설치 파일

- macOS Apple Silicon: `ClawPod-Node-0.3.2-darwin-arm64.pkg`
- macOS Intel: `ClawPod-Node-0.3.2-darwin-x64.pkg`
- Windows x64: `ClawPod-Node-0.3.2-win32-x64.exe`
- Linux x64 Debian/Ubuntu: `ClawPod-Node-0.3.2-linux-x64.deb`

각 파일의 SHA-256 체크섬과 `release.json`을 제공합니다. 이전 릴리즈 파일은 변경하지 않습니다. 기존과 동일한 Pre-release입니다.

## 검증

- Node 전체 테스트 55건 통과, 실패 0건, 별도 환경이 필요한 10건 건너뜀.
- 실제 Linux 패키지에서 추출한 앱의 브라우저 테스트 5건 통과: 이름 저장·재표시, 삭제 취소, 선택한 연결 삭제, 다른 연결 유지, 데스크톱 설정 UI 포함.
- 오프라인 Linux 0.3.1 → 0.3.2 업그레이드, 설정·인증 보존, 이름 저장·삭제, 실제 CLI 단일·다중 Gateway 연결, 제거 검증.
- macOS 두 아키텍처 Developer ID 서명·Apple 공증·stapling·Gatekeeper 검증. 서명된 런타임, 앱 IPC/준비 상태, 단일·다중 Gateway 연결 시험.
- 네 플랫폼의 이전 패키지 내용과 비교해 이번 설정/UI 파일 및 버전 정보만 변경됨을 확인. 최종 패키지 추출·해시 검증.

**검증 범위:** Windows는 패키지 구조·내용 검증까지 수행했으며 실제 Windows 실행 및 게시자 서명은 수행하지 않았습니다. Mac Intel 실행은 Rosetta를 이용했습니다. Mac 신규 설치·로그인·설치된 앱 업그레이드·제거, 실제 데스크톱 조작 및 운영 Gateway 페어링은 이번 릴리즈에서 수행하지 않았습니다.

기존 0.3.1 설치 파일에는 이번 기능이 없습니다. 0.3.2 설치 파일로 업데이트해야 적용됩니다.

