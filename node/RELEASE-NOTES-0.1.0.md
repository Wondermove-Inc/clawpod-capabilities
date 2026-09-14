# ClawPod Node 0.1.0 preview

원격 컴퓨터를 ClawPod Agent에 연결하는 독립 설치 프로그램입니다.
사용자는 운영체제와 CPU에 맞는 설치 파일 하나만 받으면 됩니다.
Node.js와 node-host 실행 환경이 포함되어 있어 별도 npm 설치나 비공개
Agent 저장소 접근이 필요하지 않습니다.

| 운영체제 | 설치 파일 |
| --- | --- |
| Linux x64 — Debian/Ubuntu | `ClawPod-Node-0.1.0-linux-x64.deb` |
| macOS Apple Silicon | `ClawPod-Node-0.1.0-darwin-arm64.pkg` |
| macOS Intel | `ClawPod-Node-0.1.0-darwin-x64.pkg` |
| Windows x64 | `ClawPod-Node-0.1.0-win32-x64.exe` |

설치 후 **ClawPod Node** 앱을 열고 Gateway WebSocket 주소와 인증 정보를
입력한 뒤 **Start node**를 누르세요. Agent Control UI에서 해당 컴퓨터의
기기 요청을 확인·승인하고 연결 상태를 확인하면 됩니다. 로컬 앱의 Running은
프로세스가 시작됐다는 뜻이며, 원격 연결 성공과는 다릅니다.

설정과 기기 정보는 사용자 홈의 별도 `.clawpod-node` 폴더에 보관합니다.
기존 `.openclaw` 설치를 교체하지 않습니다. 시작·중지는 새 앱에서 하고,
삭제는 OS의 앱 제거 절차를 따르세요. macOS는 앱 내부
`Contents/Resources/Uninstall ClawPod Node.command`를 먼저 실행합니다.

**초기 프리뷰 범위:** 설치 파일은 서명되지 않았습니다. Linux 오프라인
설치·업그레이드·제거는 Debian 컨테이너에서 검증했으며, macOS/Windows의
실제 OS 설치·로그인 자동 시작·제거는 아직 검증하지 않았습니다.
실제 Gateway에 연결하려면 네트워크 경로와 인증 정보가 필요합니다.
브라우저 자동화에는 대상 컴퓨터에 호환 브라우저가 설치되어 있어야 합니다.

각 설치 파일의 `.sha256`과 공개 `release.json`을 함께 제공합니다.
Node 설치 프로그램 버전은 **0.1.0**, 포함된 Agent 런타임 버전은
**2026.4.11**, Node.js는 **24.15.0**입니다.
