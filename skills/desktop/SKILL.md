---
name: "desktop"
description: "WHEN — 브라우저·일반 앱 GUI. CAN — 관찰·입력·검증. BOUNDARY — 구조화 웹 Browser; 원격 nodes; 서비스 API."
---

# Desktop

브라우저·일반 앱의 실제 GUI를 관찰·조작합니다. 구조화 웹 추출은 Browser/DOM, 원격 화면은 nodes, 서비스 데이터는 해당 API가 우선입니다. Desktop 시험을 DOM 결과로 대체하지 않습니다.

## 준비와 승인 경계
- 기존 세션만 사용합니다. 해상도·geometry·DPI·scale·X settings 변경과 세션 시작·교체·종료는 금지합니다. drift는 중단하며 환경을 바꿔 복구하지 않습니다.
- 최초 Harness detail과 environment.preflight로 실제 설치 버전·digest·schema·backend/AT-SPI/D-Bus를 확인합니다. 임의 설치는 하지 않습니다. 같은 계약·안정된 창 식별은 재사용하고 매 입력마다 전체 discovery를 반복하지 않습니다. 버전·환경·창 변화, 모호함, focus 변경·target 만료 때 필요한 조회만 갱신합니다.
- 이미 관찰한 정확한 창 ID가 있으면 `window.get`의 내부 `args:[WINDOW_ID]`로 조회합니다. ID를 모를 때만 compact window.list로 찾습니다. window.get은 focus/target receipt를 대신하지 않습니다. `activeWindowKnown:false`는 활성 창을 모른다는 뜻입니다.
- 보이는 창이 활성 창이라고 가정하지 않습니다. 비활성인 정확한 작업 창은 별도 허용된 window.activate prepare/run 후 다시 관찰합니다. 자동 focus 복구나 임의 ID·좌표 재사용은 하지 않습니다.
- 매 실행은 정식 prepare → 동일 입력·secretRefs(해당 시)·card binding·intent hash의 run입니다. 분류·allowlist·승인·freshness를 약화하거나 임의 batch로 줄이지 않습니다. 계정·금전·파괴·운영 위험은 상위 승인 경계에 따릅니다. CAPTCHA/MFA/타인의 로그인은 사람에게 넘깁니다.

## 입력 계약
1. 상위 Harness `input`은 JSON 문자열입니다. 내부 ui.observe가 반환한 완전한 `result.target`을 변경하지 않고 사용합니다. 좌표는 최신 화면의 x/y/visualRegion/monitor/scale/windowId에 결합합니다. monitor 문자열 screen이나 생략한 scale을 가정하지 않습니다. image target은 visionFallbackSupported:true를 유지합니다.
2. 접근성 precision mutation은 정확한 node dispatch adapter 부재로 ACCESSIBILITY_DISPATCH_UNSUPPORTED를 반환합니다. name selector/current focus로 대신 실행하지 않습니다. 좌표 fallback도 screenshot/window/revision/digest·freshness·focus·display 결합을 유지합니다.
3. keyboard.type 내부는 `args:[TEXT]`; 전체 교체는 `textMode:"replace"`로 클릭 한 번→Ctrl+A→입력입니다. 별도 재클릭으로 선택을 지우지 않습니다. 접근성 replace는 지원하지 않습니다.
4. keyboard.key/keyboard.shortcut은 단일 key/chord 배열입니다. visualRegion은 `[x,y,width,height]` 정수 배열이며 실제 대상 식별 영역을 씁니다. caret·동영상 등 무관한 변화 영역을 피하되 빈 영역으로 freshness를 우회하지 않습니다.
5. 정밀 동작은 지원 postcondition과 고유 idempotency key가 필요합니다. S2–S4 preview/actual은 같은 scope·key·payload, 각각 prepare/run을 지킵니다. 실제 preview requestDigest와 timezone 포함 ISO 만료에 결합한 top-level `approval:JSON.stringify({requestDigest,expiresAt})`를 기존 권한 내에서 사용합니다. approvalFile과 병용하지 않습니다. preview 통과는 실제 freshness 통과가 아닙니다.

```javascript
const outer = {input:JSON.stringify({
  args:[TEXT],textMode:"replace",target:FRESH_RETURNED_TARGET,
  postcondition:{activeWindowMatch:true,windowBoundsUnchanged:true}
}),idempotencyKey:UNIQUE_KEY};
```

## Guarded Return — 설치된 동일 계약 확인 후에만
- 아래 기능은 ui.observe.prepareFocusGuard와 keyboard.key.focusGuard를 실제 설치본에서 확인한 뒤 사용합니다. 미설치·부분 업데이트 상태에서는 실행하지 않습니다. 구버전 args/postCapture-only 예시는 사용하지 않습니다.
- 모든 prepareFocusGuard/focusGuard 경로는 기존 환경과 snapshot의 **정확한 DISPLAY=:99**만 지원합니다. missing/empty/alias/다른 display는 거부합니다. DISPLAY를 덮어쓰거나 세션을 생성해 통과시키지 않습니다.
- type/click/focus 변화 뒤 Return 직전에 새 ui.observe를 실행합니다. 내부 입력은 `{target:CURRENT_VISUAL_TARGET,prepareFocusGuard:true}`입니다. 반환된 `result.target`과 `result.focusGuard`를 둘 다 변경 없이 복사합니다. target만으로는 guard가 되지 않습니다.
- guard는 postCapture:true에 필수, plain Return에는 선택 지원입니다. 다른 key/shortcut은 지원하지 않습니다. 차단을 피해 unguarded Return을 재전송하지 않습니다.

```javascript
const inner = {
  args:["Return"],postCapture:true,
  target:observe.result.target,focusGuard:observe.result.focusGuard,
  postcondition:{activeWindowMatch:true,windowBoundsUnchanged:true}
};
const outer = {input:JSON.stringify(inner),idempotencyKey:UNIQUE_KEY};
// 이 outer를 동일하게 prepare/run에 전달합니다. 예제 receipt를 만들어 쓰지 않습니다.
```

- guarded Return postcondition은 위 두 true 값만 지원합니다. 구조 검증이지 문자열·검색·제출 성공 검증이 아닙니다. legacy precision 시각 postcondition은 true activeWindowMatch/windowBoundsUnchanged/visualRegionChanged만 지원하며 unsupported assertion을 추가하지 않습니다.
- 성공 캐시는 저장 결과만 반환하며 새 입력을 보내지 않습니다. afterScreenshot의 path/hash/bytes를 확인하고 별도 read로 판독합니다. 중간 화면이면 독립 capture/read로 확인하며 Return은 재전송하지 않습니다. 현재 플랫폼은 이미지가 같은 응답에 인라인 전달되어 read가 생략된다고 보장하지 않습니다.
- **F2 한계:** Return 이후 예외에서도 blocked와 빈 result가 반환될 수 있습니다. blocked는 미실행의 증거가 아닙니다. requestId/phase/dispatch 정보가 유실될 수 있으므로 코드만 보고 재시도하지 않습니다.
- guard는 원자적인 X focus/key 전달을 보장하지 않습니다. 최종 관찰 뒤 TOCTOU, PID/ID ABA, 같은 창의 child-focus 변화가 남습니다. 단일 subprocess budget은 lock/fsync/decode/OS 스케줄링까지 포함한 hard deadline이 아니며 readiness·속도·전체 PNG 규격·peak memory 상한을 보장하지 않습니다.

## 결과·Journal·측정
- 다음 동작은 최신 대상·의도·지원 postcondition으로 결정합니다. 필요한 full output은 읽고 잘린 target으로 진행하지 않습니다. retry.detailsRequired:true는 추가 상세 조회가 필요한 예외입니다. outputMode:full은 진단용이며 presentation은 mutation digest를 바꾸지 않습니다.
- dispatch·픽셀 변화는 정확한 최종 문자열이 아닙니다. 화면/지원 접근성으로 literal과 결과를 따로 판독합니다. 변경 전 거부가 실제로 확인된 경우에만 새 관찰·승인으로 복구하며 unknown을 우회하지 않습니다.
- journal은 DESKTOP_RUNS_ROOT/.journal에 run artifact와 분리됩니다. runRoot 생략은 default scope, 명시는 canonical path scope입니다. preview/actual/retry는 같은 scope·key·payload입니다. unknown을 새 key/runRoot/journal 삭제로 우회하지 않습니다. checkpoint 이후 입력 전 거부에도 unknown이 남을 수 있으며 삭제하거나 재전송하지 않고 독립 관찰로 확인합니다.
- 업데이트 전 journal과 이전 UUID-root의 미해결 unknown을 보존합니다. scope digest가 달라진 receipt는 재사용하지 않습니다. 임시저장소 삭제/재부팅 뒤 보존은 보장하지 않습니다.
- 전체 시간에는 준비·관찰·승인·입력·read·왕복·복구·모델 대기를 포함합니다. 같은 browser/native 과제의 정확도와 전후 초를 분리 보고합니다. 실패 비용을 숨기거나 유리한 시간을 얻으려 반복하지 않습니다. 출력 축소·시험 수·내부 계산 개선은 실제 GUI 속도 증거가 아니며 단일 A/B는 인과적·통계적 성능 보장이 아닙니다.
- 비밀값은 입력·preview·로그·증거에 넣지 않습니다. 관찰 결과도 공개 전에 검토합니다. private-file 검사 이후 경로 불변은 보장되지 않으므로 소비 시 bytes/hash를 재확인합니다.

명령군은 [operations](references/operations.md), 위험 단계 전에는 [safety](references/safety.md)를 확인합니다. 상위 승인·보안 규칙이 우선하며 교정 계약과 충돌하는 구버전 예시는 사용하지 않습니다.
