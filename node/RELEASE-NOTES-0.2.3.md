# ClawPod Node 0.2.3

연결된 컴퓨터의 원격 데스크톱에서 모니터를 전환하는 동작과 관찰 좌표를 수정했습니다.

- 제어 중 `screenshot` 또는 `observe`에 `display_id`를 지정하고 `frame_id`를
  생략해 다른 모니터를 관찰하세요. 이전 모니터의 frame을 붙이면 기존처럼
  `STALE_FRAME`으로 거부됩니다. 이후 입력에는 새 응답의 `frameId`를
  `frame_id`로 전달하고 새 viewport의 좌표를 사용하세요.
- 같은 화면의 텍스트 전용 관찰과 이미지 관찰이 동일한 전체 화면 뷰포트 좌표를
  사용합니다. 확대 이미지의 픽셀 좌표를 입력 좌표로 사용하지 마세요.
- 모든 원격 데스크톱 호출에서 대상 Node ID를 명시하고, 사용자나 다른 세션에
  작업을 넘기기 전에 제어를 해제하세요.

## 업데이트

**Node 앱 0.2.3과 제어하는 Agent를 모두 업데이트하세요.**
`clawpod-node-host` Skill과 Harness도 **0.7.4**로 업데이트하세요.
능력 업데이트만으로 설치된 Node 앱이나 Agent가 바뀌지는 않습니다.
기존 설정과 장치 식별 정보는 앱 업데이트 시 유지됩니다.

| 컴퓨터 | 설치 파일 |
| --- | --- |
| Mac Apple Silicon | `ClawPod-Node-0.2.3-darwin-arm64.pkg` |
| Mac Intel | `ClawPod-Node-0.2.3-darwin-x64.pkg` |
| Windows x64 | `ClawPod-Node-0.2.3-win32-x64.exe` |
| Linux x64 · Debian/Ubuntu | `ClawPod-Node-0.2.3-linux-x64.deb` |

[다운로드 안내](README.md) · [릴리스 페이지](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/tag/node-v0.2.3)

## 검증 범위

두 Mac 설치 파일은 Developer ID 서명, Apple 공증, staple 검증 및 Gatekeeper
검사를 통과했습니다. Apple Silicon과 Apple Silicon의 Rosetta에서 실행한 Intel
빌드의 앱 실행·런타임·데스크톱·CLI 검증도 통과했습니다. 물리 Intel Mac 검증은
수행하지 않았습니다. Linux 설치 파일은 네트워크 없는 설치와 설치된 native GUI
2개·CLI 1개 테스트를 통과했습니다.

Mac에서는 새 screenshot으로 모니터를 전환한 뒤 같은 화면을 observe하는 흐름을
검증했습니다. observe만으로 전환하는 흐름, 입력의 오래된 frame 거부, 접근성
요소의 정확한 좌표 변환은 소스 테스트 범위입니다. Linux 다중 모니터 전환과
실제 앱 접근성 요소 좌표, Windows 실행, 로그인 자동 시작은 검증하지 않았습니다.
Windows 게시자 서명은 포함하지 않으며 전체 Agent 테스트 통과를 주장하지 않습니다.

최종 크기와 SHA-256은 [릴리스 메타데이터](release.json)에 있습니다.
[상세 검증 기록](VALIDATION.md)을 확인하세요. 공개 다운로드 검증은 아직 수행하지
않았습니다.
