# Web Browser Skill — 설계서 v1.0

## 개요

에이전트가 사람처럼 웹 브라우저를 사용할 수 있게 하는 스킬.
**접근성 트리 + 스크린샷 하이브리드 방식**으로 ~95% 정밀도 목표.

## 핵심 원리

### 왜 하이브리드인가?

| 방식 | 장점 | 단점 | 정확도 |
|------|------|------|--------|
| DOM 셀렉터 | 빠름, 정확 | 사이트 변경에 취약, 봇 감지 | ~70% |
| 스크린샷만 | 범용, 봇 우회 | AI 비전 의존, 좌표 오차 | ~80% |
| **접근성 트리 + 스크린샷** | 정확 + 범용 + 검증 | 약간 느림 | **~95%** |

### 동작 흐름

```
1. Navigate (URL 이동)
        │
        ▼
2. Snapshot (접근성 트리 캡처)
   ┌─────────────────────────┐
   │ role="button" name="로그인" ref="e15"  │
   │ role="textbox" name="이메일" ref="e8"  │
   │ role="link" name="회원가입" ref="e22"  │
   └─────────────────────────┘
        │
        ▼
3. Screenshot (시각적 상태 확인 — 선택적)
   - 페이지 로딩 완료 확인
   - 팝업/오버레이 확인
   - 예상과 다른 상태 감지
        │
        ▼
4. Action (ref 기반 정밀 조작)
   - click(ref="e15")  → 로그인 버튼 클릭
   - type(ref="e8", "user@email.com") → 이메일 입력
   - select(ref="e30", "옵션A") → 드롭다운 선택
        │
        ▼
5. Verify (결과 확인)
   - 새 스냅샷으로 상태 변경 확인
   - 에러 메시지 감지
   - 예상 페이지 도달 확인
```

## 아키텍처

```
┌──────────────────────────────────────────┐
│              Web Browser Skill            │
│                                          │
│  ┌─────────────┐   ┌──────────────────┐  │
│  │ Task Runner  │   │ Action Library   │  │
│  │ (워크플로우  │   │ (navigate, click,│  │
│  │  오케스트라) │   │  type, scroll,   │  │
│  │             │──▶│  screenshot,     │  │
│  │             │   │  snapshot, wait)  │  │
│  └─────────────┘   └────────┬─────────┘  │
│                             │            │
│  ┌─────────────┐   ┌───────▼──────────┐  │
│  │ State Mgr   │   │ Playwright MCP   │  │
│  │ (페이지 상태│   │ (브라우저 제어)   │  │
│  │  추적/복구) │   │                  │  │
│  └─────────────┘   └──────────────────┘  │
│                                          │
│  ┌─────────────────────────────────────┐  │
│  │ Error Handler                       │  │
│  │ - 타임아웃 재시도 (3회, 백오프)     │  │
│  │ - 요소 미발견 → 스크린샷 → 재시도  │  │
│  │ - 네비게이션 실패 → 상태 복구       │  │
│  └─────────────────────────────────────┘  │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────┐
│ Chromium (Xvfb :99)  │
│ - Headless or GUI    │
│ - 1280x720 viewport  │
└──────────────────────┘
```

## 핵심 모듈

### 1. browser.js — 브라우저 제어 코어

```javascript
// 기본 액션들
async function navigate(url)           // 페이지 이동 + 로딩 대기
async function snapshot()              // 접근성 트리 캡처 → 구조화된 요소 목록
async function screenshot(path)        // 현재 화면 PNG 캡처
async function click(ref)              // ref 기반 요소 클릭
async function type(ref, text)         // ref 기반 텍스트 입력
async function select(ref, value)      // 드롭다운 선택
async function scroll(direction)       // 페이지 스크롤
async function waitFor(condition)      // 조건 대기 (텍스트 출현/소멸)
async function pressKey(key)           // 키보드 키 입력
```

### 2. workflow.js — 워크플로우 엔진

```javascript
// 복합 작업 수행
async function login(url, username, password)     // 로그인 워크플로우
async function fillForm(fields)                   // 폼 자동 입력
async function extractTable()                     // 테이블 데이터 추출
async function searchAndClick(query, targetText)  // 검색 후 결과 클릭
```

### 3. verify.js — 검증 엔진

```javascript
// 액션 결과 검증
async function verifyNavigation(expectedUrl)      // URL 확인
async function verifyElement(ref, expectedState)  // 요소 상태 확인
async function verifyText(text)                   // 텍스트 존재 확인
async function detectError()                      // 에러 메시지 감지
```

## 에러 핸들링 (방어적 코딩)

### 재시도 정책
```
실패 → 1초 대기 → 재시도 1 → 2초 대기 → 재시도 2 → 4초 대기 → 재시도 3 → 실패 보고
```

### 엣지 케이스 처리
1. **요소 미발견**: 스냅샷 재캡처 → 스크롤 → 재탐색 → 스크린샷으로 시각 확인
2. **팝업/모달 차단**: 스냅샷에서 dialog/modal 감지 → 자동 닫기 → 원래 액션 재시도
3. **페이지 로딩 지연**: waitFor로 핵심 요소 출현 대기 (타임아웃 30초)
4. **네비게이션 실패**: 상태 저장 → 재시도 → 복구 불가 시 에러 보고
5. **Stale reference**: 액션 실패 시 스냅샷 재캡처하여 새 ref로 재시도

### 성능 고려
- 스크린샷은 필요할 때만 (매 액션마다 X)
- 스냅샷 캐싱 (같은 페이지 상태에서 중복 호출 방지)
- 불필요한 대기 최소화 (waitFor 조건 기반)

## CLI 인터페이스

### 대화형 브라우저 사용
```bash
# 단일 명령
node /workspace/skills/web-browser/scripts/browse.js navigate "https://example.com"
node /workspace/skills/web-browser/scripts/browse.js snapshot
node /workspace/skills/web-browser/scripts/browse.js click "e15"
node /workspace/skills/web-browser/scripts/browse.js type "e8" "hello@world.com"
node /workspace/skills/web-browser/scripts/browse.js screenshot "/tmp/page.png"

# 워크플로우
node /workspace/skills/web-browser/scripts/browse.js login "https://app.com" "user" "pass"
```

### 에이전트 통합
에이전트는 exec 도구로 직접 호출하거나, Playwright MCP를 사용:
```bash
# Snapshot → 요소 파악 → Click 패턴
exec("mcporter call playwright.browser_navigate url='https://example.com'")
exec("mcporter call playwright.browser_snapshot")    # ref 확인
exec("mcporter call playwright.browser_click ref='e15'")  # ref로 클릭
```

## 파일 구조

```
web-browser/
├── SKILL.md          ← 스킬 메타데이터
├── DESIGN.md         ← 이 설계서
├── package.json      ← 의존성
├── scripts/
│   ├── browse.js     ← CLI 진입점
│   ├── lib/
│   │   ├── browser.js    ← 브라우저 제어 코어
│   │   ├── workflow.js   ← 워크플로우 엔진
│   │   ├── verify.js     ← 검증 엔진
│   │   └── errors.js     ← 에러 핸들링
│   └── examples/
│       ├── login.js      ← 로그인 예제
│       └── search.js     ← 검색 예제
└── README.md         ← 사용 가이드
```

## 의존성

- **Playwright MCP** (이미 설치됨) — 브라우저 제어 백엔드
- **Chromium** (이미 설치됨) — /usr/lib/chromium/chromium
- **Xvfb** (이미 설치됨) — 가상 디스플레이 (:99)

추가 npm 패키지 불필요 — Playwright MCP의 mcporter 호출로 구현.

## 구현 우선순위

1. ✅ 설계서 작성
2. 🔄 browser.js 코어 (navigate, snapshot, screenshot, click, type)
3. verify.js 검증 엔진
4. browse.js CLI
5. workflow.js 복합 워크플로우
6. README.md 사용 가이드
7. 에이전트 AGENTS.md/TOOLS.md 통합
