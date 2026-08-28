# Web Browser Skill v1.0

에이전트가 사람처럼 웹 브라우저를 사용할 수 있게 하는 스킬.
**접근성 트리(Accessibility Tree) + 스크린샷 하이브리드** 방식으로 ~95% 정밀도 제공.

---

## 개요

### 왜 하이브리드인가?

| 방식 | 장점 | 단점 | 정확도 |
|------|------|------|--------|
| DOM 셀렉터 | 빠름 | 사이트 변경에 취약, 봇 감지 | ~70% |
| 스크린샷만 | 범용 | AI 비전 의존, 좌표 오차 | ~80% |
| **접근성 트리 + 스크린샷** | **정확 + 범용 + 검증** | 약간 느림 | **~95%** |

접근성 트리는 브라우저가 시각장애인용으로 제공하는 요소 구조로, 모든 버튼/입력창/링크에 고유 참조번호(ref)를 부여합니다. 이 ref로 클릭/입력하면 사람이 마우스로 정확히 해당 요소를 클릭하는 것과 동일한 이벤트가 발생합니다.

---

## 동작 원리

```
1. Navigate  → URL 이동 + 페이지 로딩 대기
        │
        ▼
2. Snapshot  → 접근성 트리 캡처
   ┌───────────────────────────────────────────┐
   │ heading "Example Domain" [ref=e3]         │
   │ textbox "이메일" [ref=e8]                  │
   │ button "로그인" [ref=e15] [cursor=pointer] │
   │ link "회원가입" [ref=e22]                  │
   └───────────────────────────────────────────┘
        │
        ▼
3. Action    → ref 기반 정밀 조작
   - click(ref="e15")  → 로그인 버튼 클릭
   - type(ref="e8", "user@email.com") → 이메일 입력
        │
        ▼
4. Verify    → 결과 확인
   - 텍스트 존재 확인 ("로그인 성공")
   - 에러 메시지 감지
   - 스크린샷으로 시각적 확인
```

---

## 설치

### Step 1: NAS에서 복사
```bash
# 빌드서버 경유 (NAS 직접 마운트 안 된 경우)
cp -r /mnt/nas/skills/web-browser /workspace/skills/web-browser
```

### Step 2: 사전조건 설정
```bash
# Chromium 심볼릭 링크 (Pod 재시작 시마다 필요)
mkdir -p /opt/google/chrome
ln -sf /usr/lib/chromium/chromium /opt/google/chrome/chrome
```

### Step 3: mcporter 설정
`/workspace/config/mcporter.json`의 playwright 설정에 `--no-sandbox` 추가:
```json
{
  "playwright": {
    "command": "npx",
    "args": ["-y", "@playwright/mcp", "--no-sandbox"]
  }
}
```

### Step 4: 동작 확인
```bash
node /workspace/skills/web-browser/scripts/browse.js navigate "https://example.com"
node /workspace/skills/web-browser/scripts/browse.js snapshot
```

**외부 npm 패키지 설치 불필요** — Playwright MCP (mcporter)만 사용.

---

## 사용법

### CLI 기본
```bash
# 페이지 이동
node /workspace/skills/web-browser/scripts/browse.js navigate "https://google.com"

# 접근성 트리 캡처 → ref 확인
node /workspace/skills/web-browser/scripts/browse.js snapshot
# 출력 예시:
# - textbox "Search" [ref=e10]
# - button "Google Search" [ref=e12]
# - link "Gmail" [ref=e5]

# ref로 요소 조작
node /workspace/skills/web-browser/scripts/browse.js click e12        # 버튼 클릭
node /workspace/skills/web-browser/scripts/browse.js type e10 "검색어"  # 텍스트 입력

# 스크린샷 저장
node /workspace/skills/web-browser/scripts/browse.js screenshot /tmp/page.png

# 검증
node /workspace/skills/web-browser/scripts/browse.js verify "검색 결과"
node /workspace/skills/web-browser/scripts/browse.js errors
```

### 에이전트 통합 패턴

에이전트가 대화 중 웹 브라우저를 사용할 때의 패턴:

```bash
# 패턴 1: exec 도구로 browse.js 호출
exec("node /workspace/skills/web-browser/scripts/browse.js navigate 'https://huly.wondermove.local'")
exec("node /workspace/skills/web-browser/scripts/browse.js snapshot")
exec("node /workspace/skills/web-browser/scripts/browse.js click e15")

# 패턴 2: mcporter로 Playwright MCP 직접 호출
exec("mcporter call playwright.browser_navigate url='https://example.com'")
exec("mcporter call playwright.browser_snapshot")
exec("mcporter call playwright.browser_click ref='e15'")
exec("mcporter call playwright.browser_type --args '{\"ref\":\"e8\",\"text\":\"hello\"}'")
```

### 실전 예시: Google 검색

```bash
# 1. Google 접속
node browse.js navigate "https://www.google.com"

# 2. 요소 파악
node browse.js snapshot
# → textbox "검색" [ref=e10]

# 3. 검색어 입력 + Enter
node browse.js type e10 "OpenClaw AI"
node browse.js key Enter

# 4. 결과 확인
node browse.js snapshot
node browse.js verify "OpenClaw"

# 5. 스크린샷 저장
node browse.js screenshot /tmp/google-result.png
```

### 실전 예시: 웹 앱 로그인

```bash
# 1. 로그인 페이지 이동
node browse.js navigate "https://app.example.com/login"

# 2. 요소 파악
node browse.js snapshot
# → textbox "Email" [ref=e5]
# → textbox "Password" [ref=e8]
# → button "Sign In" [ref=e12]

# 3. 인증 정보 입력
node browse.js type e5 "user@example.com"
node browse.js type e8 "mypassword"
node browse.js click e12

# 4. 로그인 성공 확인
node browse.js verify "Dashboard"
node browse.js errors
```

---

## 전체 명령어 레퍼런스

| 명령 | 인자 | 설명 | 예시 |
|------|------|------|------|
| `navigate` | `<url>` | 페이지 이동 + 로딩 대기 | `navigate "https://google.com"` |
| `snapshot` | — | 접근성 트리 캡처 (ref 부여) | `snapshot` |
| `screenshot` | `[path]` | 스크린샷 PNG 저장 | `screenshot /tmp/page.png` |
| `click` | `<ref>` | 요소 클릭 (`--double` 더블클릭) | `click e15` |
| `type` | `<ref> <text>` | 텍스트 입력 (`--submit` Enter) | `type e8 "hello"` |
| `select` | `<ref> <value>` | 드롭다운 선택 | `select e20 "옵션A"` |
| `key` | `<key>` | 키보드 키 입력 | `key Enter` |
| `scroll` | `<direction>` | 스크롤 (up/down/top/bottom) | `scroll down` |
| `hover` | `<ref>` | 마우스 호버 | `hover e10` |
| `wait` | `<seconds>` | 시간 대기 | `wait 3` |
| `waitfor` | `<text>` | 텍스트 출현 대기 | `waitfor "로딩 완료"` |
| `back` | — | 뒤로가기 | `back` |
| `tabs` | `[action]` | 탭 관리 (list/new/close/select) | `tabs list` |
| `verify` | `<text>` | 텍스트 존재 확인 | `verify "로그인"` |
| `errors` | — | 에러 메시지 감지 | `errors` |
| `eval` | `<js>` | JavaScript 실행 | `eval "() => document.title"` |
| `close` | — | 브라우저 닫기 | `close` |

### 키보드 키 이름 (key 명령)

| 키 | 이름 |
|----|------|
| Enter | `Enter` |
| Tab | `Tab` |
| Escape | `Escape` |
| 화살표 | `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight` |
| 백스페이스 | `Backspace` |
| 삭제 | `Delete` |
| Home/End | `Home`, `End` |
| Page Up/Down | `PageUp`, `PageDown` |

---

## 에러 핸들링

### 자동 재시도 (Exponential Backoff)
```
실패 → 1초 대기 → 재시도 1 → 2초 대기 → 재시도 2 → 4초 대기 → 재시도 3 → 실패 보고
```

모든 브라우저 액션(click, type, navigate)에 자동 적용됩니다.

### Stale Reference 복구
클릭/입력 시 ref가 유효하지 않으면(페이지 상태 변경됨):
1. 자동으로 snapshot 재캡처
2. 새로운 ref로 재시도
3. 3회까지 시도 후 실패 보고

### 스냅샷 캐싱
- 동일 페이지 상태에서 2초 이내 중복 snapshot 호출 방지
- `force: true` 옵션으로 캐시 우회 가능
- navigate, click, type 등 상태 변경 액션 후 자동으로 캐시 무효화

### 커스텀 에러 클래스
```javascript
BrowserError {
  message: "Ref e999 not found",
  type: "element",        // navigation | element | timeout | action | mcporter
  context: { ref: "e999" }
}
```

---

## 아키텍처

```
┌──────────────────────────────────────────┐
│           Web Browser Skill               │
│                                          │
│  browse.js (CLI)                         │
│      │                                   │
│      ├── lib/browser.js  (브라우저 코어)  │
│      │     └── mcporter → Playwright MCP │
│      ├── lib/verify.js   (검증 엔진)     │
│      ├── lib/workflow.js (워크플로우)     │
│      └── lib/errors.js   (에러 핸들링)   │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Chromium (Xvfb :99)  │
│ Headless + no-sandbox│
│ Viewport: 1280x720   │
└──────────────────────┘
```

### 모듈별 역할

| 모듈 | 역할 | 주요 함수 |
|------|------|-----------|
| `browser.js` | 브라우저 제어 코어 | navigate, snapshot, screenshot, click, type, select, scroll, pressKey, hover, waitFor, fillForm, tabs, close, evaluate, drag |
| `verify.js` | 액션 결과 검증 | verifyText, verifyTextGone, detectErrors, verify (복합), captureVerification |
| `workflow.js` | 복합 워크플로우 | login, search, extractPageText, navigateAndExtract |
| `errors.js` | 에러 처리 유틸 | BrowserError, withRetry (지수 백오프), sleep |

---

## 파일 구조

```
web-browser/
├── SKILL.md           ← 스킬 메타데이터
├── DESIGN.md          ← 설계서 (아키텍처, 구현 계획)
├── README.md          ← 이 파일 (사용 가이드)
├── package.json       ← 패키지 정보 (외부 의존성 없음)
└── scripts/
    ├── browse.js      ← CLI 진입점 (17개 명령)
    └── lib/
        ├── browser.js ← 브라우저 제어 코어 (15개 함수)
        ├── verify.js  ← 검증 엔진 (6개 함수)
        ├── workflow.js← 워크플로우 엔진 (4개 함수)
        └── errors.js  ← 에러 핸들링 (BrowserError, withRetry)
```

---

## 의존성

| 항목 | 설명 | 상태 |
|------|------|------|
| Playwright MCP | 브라우저 제어 백엔드 (mcporter 경유) | 에이전트 이미지에 포함 |
| Chromium | 웹 브라우저 엔진 | 에이전트 이미지에 포함 |
| Xvfb | 가상 디스플레이 서버 (:99) | 에이전트 이미지에 포함 |
| 외부 npm 패키지 | — | **없음** |

---

## 트러블슈팅

### Chromium sandbox 에러
```
Running as root without --no-sandbox is not supported
```
**해결:** mcporter config에 `--no-sandbox` 추가 (설치 Step 3 참고)

### /opt/google/chrome/chrome not found
```
Chromium distribution 'chrome' is not found
```
**해결:**
```bash
mkdir -p /opt/google/chrome
ln -sf /usr/lib/chromium/chromium /opt/google/chrome/chrome
```

### mcporter config 미적용 (cwd 문제)
browse.js가 `/workspace`가 아닌 다른 디렉토리에서 실행되면 mcporter가 config를 못 찾을 수 있음.
**해결:** browser.js에서 `cwd: '/workspace'`로 고정됨 (자동 처리)

### 스냅샷에 요소가 안 보임
- 페이지 로딩이 덜 됐을 수 있음 → `wait 3` 후 재시도
- 스크롤 아래에 있을 수 있음 → `scroll down` 후 재시도
- iframe 내부 요소는 접근성 트리에 안 나올 수 있음

### Pod 재시작 후 동작 안 함
```bash
# 심볼릭 링크 재생성
mkdir -p /opt/google/chrome
ln -sf /usr/lib/chromium/chromium /opt/google/chrome/chrome
```

---

## 라이선스

Internal tool — Wondermove.AI
