# ClawPod Node 0.2.2

앱을 눌렀는데 설정 화면이 열리지 않던 문제를 수정했습니다. macOS·Windows·Linux 모두 ClawPod Node를 열면 기본 브라우저에 설정 페이지가 표시됩니다.

- 설치 후 조용히 재시작한 앱에서도 설정 페이지를 다시 열 수 있습니다.
- macOS에서 실행 중인 앱을 다시 열어도 기존 백그라운드 프로세스를 종료하지 않습니다.
- 설치 후 자동 재시작과 로그인 시 자동 실행은 기존대로 유지합니다.
- 기존 연결 정보와 기기 등록을 유지하는 업데이트입니다.

## 다운로드

| 컴퓨터 | 설치 파일 |
|---|---|
| Mac Apple Silicon | `ClawPod-Node-0.2.2-darwin-arm64.pkg` |
| Mac Intel | `ClawPod-Node-0.2.2-darwin-x64.pkg` |
| Windows x64 | `ClawPod-Node-0.2.2-win32-x64.exe` |
| Linux x64 · Debian/Ubuntu | `ClawPod-Node-0.2.2-linux-x64.deb` |

기존 앱을 삭제하지 않고 같은 OS·CPU용 설치 파일로 업데이트하세요. 설치 후 **ClawPod Node**를 열면 설정 페이지가 표시됩니다.

Mac Apple Silicon·Intel 설치 파일을 Apple Developer ID 서명·공증 완료본으로 교체했습니다. 설치 파일에 공증 확인 정보도 포함했습니다. 기존 0.2.2 파일을 받아 두셨다면 다시 다운로드해 설치하세요. 이번 배포는 preview이며 Windows 게시자 서명은 아직 포함하지 않습니다. Mac 업데이트 후 화면 녹화·기기 제어 권한을 다시 허용해야 할 수 있습니다. 이번 수정은 앱 화면 열기에 관한 것으로, Gateway 토큰 인증 오류를 자동으로 수정하지 않습니다.

검증 범위와 남은 플랫폼 확인 항목은 저장소의 `node/VALIDATION.md`에 기록했습니다.

에이전트의 `clawpod-node-host` 능력도 **0.7.3**으로 업데이트하세요. 이전 능력에는 교체 전 Mac 파일의 다운로드 검증 정보가 들어 있습니다.
