# ClawPod Node 0.2.3

ClawPod Agent와 연결된 컴퓨터에서 원격 작업을 더 안정적으로 수행할 수 있도록 개선했습니다.

## 개선사항

- 여러 모니터를 사용할 때 다른 모니터로 처음 전환하면 발생하던 오류를 수정했습니다.
- 화면 이미지와 접근성 정보의 좌표를 맞춰, 클릭 위치가 어긋나거나 화면 범위를 벗어나는 문제를 수정했습니다.

## 다운로드

사용할 컴퓨터에 맞는 설치 파일을 선택하세요.

| 컴퓨터 | 설치 파일 |
| --- | --- |
| Mac · Apple Silicon (M 시리즈) | [PKG 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.3/ClawPod-Node-0.2.3-darwin-arm64.pkg) |
| Mac · Intel | [PKG 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.3/ClawPod-Node-0.2.3-darwin-x64.pkg) |
| Windows · x64 | [EXE 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.3/ClawPod-Node-0.2.3-win32-x64.exe) |
| Linux · x64 (Debian/Ubuntu) | [DEB 다운로드](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.3/ClawPod-Node-0.2.3-linux-x64.deb) |

두 Mac 설치 파일은 Developer ID 서명과 Apple 공증을 완료했습니다.
Windows 설치 파일에는 코드 서명이 적용되지 않았습니다.

## 업데이트 방법

1. 위 설치 파일로 기존 **ClawPod Node 앱을 0.2.3으로 업데이트**하세요. 저장된 설정과 연결된 장치 정보는 유지됩니다.
2. 컴퓨터를 제어하는 **ClawPod Agent도 최신 버전으로 업데이트**하세요.
3. Agent의 **`clawpod-node-host` Skill과 Harness를 0.7.4로 업데이트**하세요.

[상세 변경 및 검증](https://github.com/Wondermove-Inc/clawpod-capabilities/pull/190)
