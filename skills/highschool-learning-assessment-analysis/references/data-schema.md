# data.json schema (schema_version 1)

One JSON file per 성적표. `build_deck.py` reads only this file; every number and every Korean sentence on the slides comes from here. Two complete examples are in `examples/`:
- `sample-g1-oct.json`: 고1 10월, 6 subjects, 교내 석차, 영역별 data, admission slide (14 slides). It reproduces the approved reference deck byte for byte.
- `sample-g2-jun.json`: 고2 6월, 미적분, 물리학Ⅰ/화학Ⅰ, no 교내 석차, no admission slide (12 slides).

Copy the closer example and edit it. Do not start from scratch.

## Conventions
- **성적표 values that have decimals are strings** (`"pct": "79.80"`) so trailing zeros survive. Integers stay numbers.
- Text fields may contain light HTML (`<b>`, `<br>`, `<em>`) and these markers:
  - `{추정}` renders the amber 추정 pill. Use it for anything not printed on the 성적표.
  - `{제안}` / `{제안 목표}` render the blue pill.
- The minus sign in copy is `−` (U+2212), not `-`.
- Never put the student name or school anywhere. List them in `privacy.forbidden_strings` so qa.py can enforce this.

## Top level
| key | req | meaning |
|---|---|---|
| `schema_version` | yes | `1` |
| `deck.title` | yes | `<title>` of the HTML (headline-style sentence) |
| `deck.meta` | yes | cover meta line, e.g. `2026학년도 10월 고1 전국연합학력평가 · 2026.10.20` |
| `deck.cover_title` | yes | e.g. `고1 10월 학평 분석` |
| `deck.cover_sub` | yes | 2-line takeaway, `<b>…</b>,<br>…` |
| `deck.cover_stats` | yes | 4 × `[value, label]` along the cover bottom |
| `exam.grade/month/kind/date` | yes | `고1`/`10월`/`학평`/`2026.10.20` |
| `exam.school_total` | no | 교내 응시 인원 (e.g. 225). `null` means no 교내 석차; the rank column and the 전국 vs 교내 slide are dropped |
| `exam.next_exam` | no | e.g. `고2 6월 학평` (used in your copy) |
| `privacy.forbidden_strings` | yes | the student name and school, as printed on the 성적표 |
| `qa.must_not_contain` | no | strings that must not appear, e.g. numbers from a previous student |
| `qa.allowed_percents` | no | bare `N%` values that legitimately equal a floor(x.5) rate |
| `headline_combo` | no | `{label, pct, top}`, the cover hero number plus the admission basis. `top` = 100 − pct, rounded half-up |
| `combined` | no | 조합 백분위 map (kept for reference/QA; not all are printed) |

## subjects[] (table order = this order)
| key | req | meaning |
|---|---|---|
| `name` | yes | 국어, 수학, 영어, 한국사, 통합사회, 물리학Ⅰ … (use the 성적표 spelling, e.g. Ⅰ U+2160) |
| `elective` | no | 선택과목 (언어와 매체, 미적분, 확률과 통계 …); put it in copy and table_note |
| `raw`, `full` | yes | 원점수 / 만점 |
| `std`, `pct` | no | 표준점수 (number) / 백분위 (string). Omit for 절대평가 subjects |
| `grade` | yes | 등급 |
| `rank` | no | 교내 석차 (needs `exam.school_total`) |
| `absolute` | no | `true` for 영어/한국사 (절대평가) |
| `cut` | no | `{grade, score}`: the grade-boundary raw score **printed on or officially fixed for** the 성적표 (영어 2등급 = 80). Shows 내 점수 / 기준 / 여유·부족 on the detail slide. Never invent cuts for relative-grade subjects |
| `status` | no | `best` (blue row + glow), `warn` (amber bar); omit = neutral |
| `tag`, `table_note` | no | the 비고 column, e.g. `주의` + `2등급 기준 80점 · 1점 차` |
| `areas[]` | no | 영역별 `{name, short?, got, full, avg}`; `avg` = 전국 평균 점수 (optional). A subject with areas gets its own detail slide |
| `wrong[]` | no | 보충학습 필요 문항 numbers as strings |
| `weak_note` | no | the 참고 cell on the 보완할 점 slide |

Derived automatically (do not type these in): `lost` = full − raw, area rate and 전국 rate (half-up %), %p gap, `weakest` area (lowest rate; ties go to more points lost), 교내 상위 % = rank/total (1 decimal, half-up), and the 보완할 점 order (points lost desc).

## slides.* (copy; a missing optional block drops its slide)
| block | slide | required keys |
|---|---|---|
| `diagnosis` | 종합 진단 (always) | `headline`, `lines[3]` = `{key, tone: glow/glow2/warn, title, desc, value, value_small}` |
| `table` | 과목별 성적 (always) | `headline` (auto if missing), optional `foot` |
| `national_vs_school` | 전국 vs 교내 | `headline`, `insight_title`, `insight_body`. Shown only if any subject has rank + pct (max 4) |
| `subject_strengths` | 잘한 점 ① | `headline`, `cards[≤3]` = `{n, n_small, title, desc, x_em, x_label}` |
| `area_strengths` | 잘한 점 ② | `headline`, `items[≤4]` = `{subject, area, title, desc}` (the area must exist in `subjects[].areas`); `foot` |
| `weak` | 보완할 점 한눈에 (always) | optional `headline`/`foot` (auto-generated otherwise) |
| `details.<subject>` | one per subject with areas | `headline`, `diagnosis?`, `actions[]`, `chips_note?` (wrong-item note), `item_types?` = `[[no, 유형]]` + `item_types_note` (always 추정) |
| `others[]` | one slide per entry | `{headline, label, aria?, subjects[1-2], comments{subject: html}}` for subjects without areas (사회/한국사/탐구) |
| `priorities` | 우선순위 & 루틴 (always) | `headline`, `items[4]` = `{title, desc}`, `routine[≤4]` = `{freq, title, desc}` (제안) |
| `admission` | 정시 지원 범위 | `headline`, `track`, `banner`, `bands[4]` = `{k, desc, items[]}`, `foot`. **Include only when the user asked for it or the reference flow calls for it**; everything on it is 추정 |
| `next` | 다음 단계 & 목표 (always) | `headline`, `cautions[4]` = `{title, desc}`, `targets_title`, `targets[≤4]` = `{title, desc, from, to, unit}` (제안 목표) |

## Length limits (keep layout_check green)
- Slide headline (`headline`): **at most ~34 Korean characters** with spaces. It must fit on one line at 64px across 1620px. render.py flags any wrap.
- Diagnosis `title` ≤ 22 chars; `desc` ≤ 45 chars.
- Card/tile `title` ≤ 16 chars; `desc` two short lines (`<br>`).
- Priority `title` ≤ 20 chars; routine `title` ≤ 16 chars.
- Detail `diagnosis` ≤ 70 chars; each `actions[]` item ≤ 26 chars.
- `weak_note` ≤ 10 chars.
