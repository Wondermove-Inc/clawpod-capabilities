# Analysis rules: how to turn a 성적표 into consistent 학평 분석

The approved v2 deck (고1 10월, 2026-11-06) is the quality bar. Every new deck follows these rules.

## 1. Derived numbers (computed by build_deck.py; use the same math in your copy)
- **잃은 점수** per subject = 만점 − 원점수. Per area = 배점 − 득점.
- **득점률** = 득점/배점 × 100. **전국 득점률** = 전국평균/배점 × 100. **격차** = 내 득점률 − 전국 득점률, in **%p**.
- **Weakest area** per subject = lowest 득점률 (ties go to more points lost). It is highlighted amber on its detail slide.
- **전국 상위 %** = 100 − 백분위 (1 decimal). **교내 상위 %** = 석차 ÷ 응시자 × 100 (1 decimal).
- **보완 우선순위**: rank by points lost, then grade risk (a grade just above a cut, such as 영어 81 vs 80; or the lowest grade/백분위 among subjects). Usually the top 3–4 are: biggest area loss, the borderline 절대평가 subject, the lowest-grade subject, then the next biggest area loss.
- **목표 (제안 목표)**: next exam, realistic steps. Weakest area +4~6 points; borderline 절대평가 subject = cut + 5; lowest grade −1 등급.

## 2. Rounding: half-up, always
- Integer percent: `int(Decimal(x).quantize(1, ROUND_HALF_UP))`. 29/40 = 72.5 → **73%**. Never use Python `round()` (banker's rounding gives 72).
- One decimal: same with `Decimal('0.1')`.
- qa.py fails if any x.5 rate appears floored, or if a fraction is printed next to the wrong percent.

## 3. Labelling: 성적표 fact vs 추정 vs 제안
Anything not printed on the 성적표 gets a label on the slide:
- **추정** (amber pill `{추정}`): item types (문항 유형) inferred from the usual 수능/학평 layout; item difficulty position (e.g. "21·29·30번 고난도"); university ranges (the admission slide always has the 추정 banner); school-level interpretation ("이 학교 학생 수준이 전국보다 높다"); any "가능성이 큽니다" prediction.
- **제안** (blue pill): weekly routines (`priorities.routine`). **제안 목표**: targets.
- **General knowledge** is stated as such ("참고(일반 기준)"), not as a 성적표 fact:
  - 5등급제 내신 (1등급 = 상위 10%) applies from the 2025 고1 cohort; under the 9등급제, 1등급 = 상위 4%.
  - From the 2028 수능, every student takes 통합사회 and 통합과학 (no 탐구 선택).
  - 영어/한국사 are 절대평가: 영어 2등급 = 80점+, 1등급 = 90점+; 한국사 1등급 = 40점+.
  - 고1/고2 학평 is taken only by current students, so 수능 백분위 usually comes out lower.

## 4. Never invent
- Grade cuts for relative-grade subjects, national averages, item topics or 정답률 that are not on the 성적표.
- 교내 석차 or 영역별 data when the 성적표 does not have them. Leave the field out: the slide adapts or drops.
- If a number is unreadable, **ask the user**. Do not guess.

## 5. Privacy
- No student name, school, class or 수험번호 on any slide, in the `<title>` or in file names. Put them in `privacy.forbidden_strings`.

## 6. Copy style (Korean slide copy)
- **Headline = the takeaway** (5-second test). Use numbers: "가장 큰 감점은 수학 문제해결 −16점입니다", not "보완할 점".
- Concrete subject + verb + object. Use short 합니다/입니다 sentences, or noun phrases for labels.
- Banned vague words (qa.py fails on them): 고도화, 효율화, 최적화, 혁신, 체계적, 극대화, 다양한, 적극, 강화, 개선, 향상. Use 보완/늘리기/줄이기/다시 풀기 instead.
- One-line headlines (≤ ~34 chars). render.py's layout check fails on a wrap.
- No emoji.
- Actions must be doable this week: "미적분 4점 문항을 매일 2문제 풉니다", not "수학 실력을 키운다".

## 7. Slide set (adapts to the data)
| # | slide | condition |
|---|---|---|
| 1 | 표지 | always |
| 2 | 종합 진단 (위치/강점/약점 + 잃은 점수 strip) | always |
| 3 | 과목별 성적표 | always; 교내 석차 column only if any rank |
| 4 | 전국 vs 교내 위치 | needs rank + 백분위 (`school_total`) |
| 5 | 잘한 점 ① 과목 단위 | `subject_strengths` |
| 6 | 잘한 점 ② 영역 단위 (격차 %p) | `area_strengths` (needs areas) |
| 7 | 보완할 점 한눈에 | always (from lost points) |
| 8+ | 과목 상세 (one per subject with areas) | `areas` |
| … | 사회/한국사/탐구 (2 subjects per slide) | `others[]` |
| … | 보완 우선순위 & 학습 제안 | always |
| … | 정시 지원 범위 (추정) | `admission`: only when requested or clearly useful; never for 고3 without real 입결 |
| last | 다음 단계 & 목표 | always |

The typical size is 10–16 slides. If a subject has no 영역별 data, it gets no detail slide; it goes into `others[]` instead.
