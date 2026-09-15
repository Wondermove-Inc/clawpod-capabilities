# ClawPod Node 0.1.1

Mac, Windows, Linux 컴퓨터를 ClawPod Agent에 연결하는 설치 프로그램입니다.
사용할 컴퓨터에 맞는 파일 하나를 내려받아 설치하면 됩니다.

## 달라진 점

- **사설 IP·Tailscale 연결 개선:** `ws://` 연결을 별도 옵션 없이 지원합니다. 기존 허용 체크박스는 제거했습니다.
- **운영체제별 아이콘 추가:** macOS 앱, Windows 설치 프로그램·바로가기, Linux 앱 실행기에 ClawPod 아이콘을 적용했습니다.
- **연결 안내 정리:** 실제 Gateway의 통신 방식에 맞춰 주소를 입력하도록 안내합니다. Tailscale에 로그인했다고 `wss://`를 사용할 수 있는 것은 아닙니다.

## 설치 파일 선택

| 컴퓨터 | 설치 파일 |
| --- | --- |
| macOS Apple Silicon | `ClawPod-Node-0.1.1-darwin-arm64.pkg` |
| macOS Intel | `ClawPod-Node-0.1.1-darwin-x64.pkg` |
| Windows x64 | `ClawPod-Node-0.1.1-win32-x64.exe` |
| Linux x64 — Debian/Ubuntu | `ClawPod-Node-0.1.1-linux-x64.deb` |

## 연결 방법

1. 에이전트와 컴퓨터 양쪽의 Tailscale 연결을 확인합니다.
2. 설치 후 **ClawPod Node**를 엽니다.
3. 일반 Gateway에는 `ws://<Tailscale IP>:<포트>`를 입력합니다. TLS가 구성된 접속 주소에는 `wss://`를 사용합니다.
4. 에이전트가 알려준 실제 Gateway 토큰 또는 비밀번호를 별도 인증 입력란에 넣습니다.
5. **Save settings → Start node**를 누르고, 에이전트가 해당 기기의 연결 요청을 승인·확인합니다.

기존 설치 위에 업데이트하면 설정과 기기 정보가 유지됩니다. 기존에 저장한
`wss://` 주소가 일반 Gateway를 가리킨다면 `ws://`로 바로잡아 주세요.
앱의 **Running** 표시는 프로세스 실행 상태이며, 연결 성공은 에이전트에서 확인합니다.

이 릴리스는 서명되지 않은 프리뷰입니다. 실제 macOS·Windows 환경의 전체
설치·업그레이드·제거 검증은 아직 완료되지 않았습니다.
