# ClawPod Node 0.2.0

연결한 Mac·Windows·Linux 컴퓨터의 화면을 에이전트가 보고, 마우스와 키보드로 조작할 수 있도록 **ClawPod Node에 데스크탑 기능을 통합했습니다.** 별도의 데스크탑 앱이나 헬퍼를 설치할 필요가 없습니다.

## 달라진 점

- **원격 GUI 조작:** 화면 확인, 창과 접근성 정보 조회, 클릭·스크롤·드래그·키 입력·다국어 붙여넣기를 지원합니다.
- **앱에서 준비 상태 확인:** 실행 후 **Desktop setup**에서 해당 OS의 화면·입력 사용 가능 여부를 확인합니다.
- **macOS 권한 통합:** 화면 및 입력 권한을 **ClawPod Node** 이름으로 요청합니다. 별도의 ‘ClawPod Remote Computer’ 앱은 필요하지 않습니다.
- **기존 연결 유지:** 사설 IP·Tailscale의 `ws://` 연결과 기존 설정·기기 정보를 유지합니다. CLI와 브라우저 작업도 기존 노드 연결을 사용합니다.

에이전트는 대상 노드를 지정한 `remote_computer`로 원격 화면을 조작합니다. 기존 `computer`는 계속 에이전트 파드의 화면을 담당합니다. Gateway의 Agent도 `remote_computer`가 포함된 버전이어야 합니다. 소리 수집 기능은 포함되지 않습니다.

## 설치 파일 선택

| 컴퓨터 | 설치 파일 |
| --- | --- |
| macOS Apple Silicon | `ClawPod-Node-0.2.0-darwin-arm64.pkg` |
| macOS Intel | `ClawPod-Node-0.2.0-darwin-x64.pkg` |
| Windows x64 | `ClawPod-Node-0.2.0-win32-x64.exe` |
| Linux x64 — glibc 2.36 이상, Debian 12·Ubuntu 24.04 등 | `ClawPod-Node-0.2.0-linux-x64.deb` |

## 설치 후 연결

1. 에이전트와 컴퓨터 양쪽의 Tailscale 연결을 확인합니다.
2. 해당 설치 파일을 실행하고 **ClawPod Node**를 엽니다.
3. **Desktop setup**을 확인합니다. Mac에서는 **ClawPod Node**에 ‘화면 및 시스템 오디오 녹음’과 ‘손쉬운 사용’ 권한을 허용합니다. macOS 27에서는 입력 권한이 ‘기기 제어 및 데이터 접근’으로 표시됩니다.
4. 에이전트가 알려준 실제 Gateway 주소와 토큰 또는 비밀번호를 각각 입력합니다. 일반 리스너에는 `ws://<Tailscale IP>:<포트>`, TLS가 구성된 주소에는 `wss://`를 사용합니다.
5. **Save settings → Start node**를 누르고, 에이전트가 해당 기기의 연결 요청을 승인·확인합니다.

Windows에서는 로그인된 데스크탑을 사용합니다. Linux X11은 X 디스플레이·XTest가 필요하며, Wayland는 화면·입력 공유 요청을 사용자가 승인해야 합니다. GUI 권한이 없어도 Gateway 연결 설정은 진행할 수 있습니다.

Mac 업데이트 후 권한 스위치가 켜져 있는데도 접근이 거부되면, 기존 권한 항목을 제거하고 응용프로그램의 현재 **ClawPod Node**를 다시 추가한 뒤 **Check again**을 누르세요.

## 검증 범위

Mac Apple Silicon 실기기의 화면·입력과 Linux X11 설치 패키지를 검증했습니다. Windows·Intel Mac의 실제 GUI, 실제 Wayland 환경 및 모든 OS의 로그인 시작 동작은 아직 검증이 완료되지 않았습니다.

이 버전은 프리뷰입니다. Mac 앱은 임시 서명이며 Apple 공증과 Developer ID 서명은 적용되지 않았고, Windows 게시자 서명도 적용되지 않았습니다.
