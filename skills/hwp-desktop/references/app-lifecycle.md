# HOP 앱 수명주기

앱 bootstrap, status, update, rollback, repair가 필요할 때만 읽는다.

- 루트 `/workspace/application/hop`, 버전 `versions/<version>/HOP-linux-<arch>.AppImage`, 활성 `current`, 출처 `provenance.json`을 사용한다.
- status는 아키텍처, 링크, 실행 파일, provenance/SHA-256, Desktop preflight와 창 실행/정리를 검증한다.
- bootstrap/update는 승인 후 공식 release asset을 staging에 받고 크기/SHA-256/최종 호스트를 기록하며 검증 성공 후에만 current를 원자 교체한다.
- Rollback과 repair는 마지막 정상 버전을 검증해 current를 원자 복구하고 orphan staging/process를 안전하게 정리한 뒤 status를 반복한다.
- FUSE/AppImage, WebKitGTK, display/D-Bus/AT-SPI, IME, font, crash를 분리 진단한다.
- `Alt+F`는 종료로 사용하지 않고 창과 프로세스 종료를 Desktop 관찰로 확인한다.
