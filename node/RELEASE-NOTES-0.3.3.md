## ClawPod Node 0.3.3 (preview)

### 개선 사항
- **한국어 / English UI**: 브라우저 언어를 기본값으로 사용하며, 직접 선택한 언어는 앱 재시작 후에도 유지합니다. 상태·확인창·알려진 오류 메시지도 번역합니다. 외부 프로그램의 원문 진단 로그는 유지합니다.
- **연결 / 이 컴퓨터 탭 분리**: 연결 설정과 공통 로그인 시작·데스크톱 권한 설정을 구분했습니다. 컴퓨터 설정 저장이나 언어 변경은 실행 중인 연결을 재시작하지 않습니다. 탭 전환 시 작성 중인 연결 설정도 유지합니다.
- **macOS 패키지 정리**: ARM64 패키지의 미사용 Intel 전용 pi-tui helper와 Intel 패키지의 미사용 ARM64 helper를 제외했습니다. 현재 CPU에 필요한 helper는 유지하며 실제 로딩을 검증했습니다.

### 설치 파일
- Apple Silicon: `ClawPod-Node-0.3.3-darwin-arm64.pkg`
- Intel Mac: `ClawPod-Node-0.3.3-darwin-x64.pkg`
- Linux x64 (Debian/Ubuntu): `ClawPod-Node-0.3.3-linux-x64.deb`
- Windows x64: `ClawPod-Node-0.3.3-win32-x64.exe`

각 설치 파일의 SHA-256 파일과 공개용 `release.json`을 함께 제공합니다. 기존 연결·페어링·인증 저장소와 Agent 런타임은 유지합니다. 능력 카탈로그, Skills, Harnesses는 변경하지 않았습니다.

### 검증
- Node 테스트 61건 통과, opt-in 11건 별도 분류; 실제 설치 파일에서 추출한 브라우저 UI 테스트 7건 통과.
- Linux: 네트워크를 차단한 환경에서 0.3.2 → 0.3.3 업그레이드, 기존 설정·인증 유지, 활성 앱 재시작, 단일·다중 연결 프로토콜, 제거 후 사용자 설정 보존 확인.
- macOS ARM64 / Intel: Developer ID 서명, Apple 공증, stapling 및 Gatekeeper 검증. 서명된 런타임·앱 IPC·단일/다중 연결 프로토콜 및 패키지 추출 검증.
- 네 플랫폼의 패키지 내용과 소스·체크섬 대조.

### 검증 범위
Intel Mac 런타임은 Apple Silicon의 Rosetta에서 시험했습니다. 이번 버전의 실제 macOS 설치·로그인 시작·삭제 전체 흐름, 물리 Intel Mac, Windows 실제 실행 및 Windows 게시자 서명은 검증하지 않았습니다. macOS 28 호환성 경고가 사라지는지는 영향을 받은 Mac에 설치 후 확인이 필요합니다.

