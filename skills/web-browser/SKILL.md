---
name: "web-browser"
description: "Add safe CLI OAuth browser bridge guidance."
---

# Web Browser Skill — Human-like Browser Automation

에이전트가 사람처럼 웹 브라우저를 사용할 수 있게 하는 스킬.
접근성 트리 + 스크린샷 하이브리드 방식으로 높은 정밀도 제공.

## Description

웹 브라우저를 사람이 마우스와 키보드로 사용하는 것처럼 자동화합니다.
접근성 트리(Accessibility Tree)로 요소를 정확히 파악하고,
스크린샷으로 시각적 상태를 확인하여 정밀한 조작이 가능합니다.

## Usage

에이전트가 웹 브라우저 작업을 요청받았을 때 이 스킬을 사용합니다:
- 웹사이트 탐색, 정보 수집
- 웹 앱 조작 (로그인, 폼 작성, 버튼 클릭)
- 웹 기반 관리 도구 사용 (Huly, GitHub 등)
- 시각적 확인이 필요한 UI 테스트
- CLI가 브라우저 OAuth 로그인을 요구하고, UI 입력/상태 판독을 안정적으로 해야 하는 경우

## Architecture

Playwright MCP를 기반으로 접근성 트리 + 스크린샷 하이브리드 워크플로우를 제공합니다.

## CLI OAuth Browser Bridge Pattern

Use this pattern when a CLI command starts a local OAuth callback flow, for example Salesforce `sf org login web`, GitHub browser auth, or another tool that opens a browser and waits on `localhost`.

### When to use

Use `web-browser` for the browser/UI portion when:
- the page has fields, buttons, consent screens, verification prompts, or errors that must be read precisely;
- xdotool/coordinate input is flaky or focus is unreliable;
- screenshots and accessibility tree observations can reduce mistakes;
- secrets can be injected safely without printing values.

Keep the CLI callback flow in the CLI process. `web-browser` should drive the browser tab that belongs to that CLI OAuth URL, not open an unrelated login page that cannot complete the callback.

### Safe workflow

1. Start the CLI OAuth command in a bounded foreground/background session.
2. Capture or route the generated OAuth URL into a controllable browser without printing sensitive query values in chat/logs/reports.
3. Use `browser.start`/`browser.open`/`browser.snapshot`/`browser.act` to inspect and operate the page by accessible refs, not by screen coordinates when refs are available.
4. If entering credentials is explicitly approved, use secret injection only. Never print credentials, tokens, sessions, auth URLs, SFDX auth URLs, client secrets, or sensitive query parameters.
5. Stop immediately on human-verification/CAPTCHA, email/SMS verification code prompts unless explicitly approved and provided by the human, unexpected OAuth consent, credential rejected errors, callback refused/timeout, or any credential reveal request.
6. After success, verify only with the safe CLI commands allowed for the task. Filter output to approved safe fields.
7. Close stale login windows and stop waiting CLI/browser processes when blocked, timed out, or complete.

### Salesforce `sf org login web` notes

For Salesforce CLI OAuth login:
- prefer `web-browser` for UI recognition, form filling, and error/verification prompt detection;
- preserve the CLI callback by keeping the `sf org login web` process alive until the browser flow completes;
- do not use `--set-default` unless explicitly approved;
- do not run `sf org display --verbose` or credential reveal commands;
- allowed verification is typically `sf org list --json` and `sf org display --target-org <alias> --json`, filtered to safe fields such as alias, username, org id, instance domain/url, connected status, API version, and default-org status.

### Reporting

Report only:
- command shape with sensitive values redacted;
- success/failure/blocker;
- safe fields explicitly allowed by the task;
- whether default org was not set;
- cleanup status for login processes/windows.

Never report plaintext credentials, tokens, session ids, auth URLs, SFDX auth URLs, client secrets, or full OAuth query strings.
