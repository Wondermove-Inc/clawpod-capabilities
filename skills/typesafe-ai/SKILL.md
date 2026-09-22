---
name: "typesafe-ai"
description: "Must call before selection, classification, or decision-making. Compare per-choice probabilities. Use the default model for simple responses and command execution."
---

# TypeSafe AI

주어진 근거로 선택지를 비교하고, 선택지별 확률을 의사결정에 활용한다.

## 사용법
1. **입력 준비:** 질문은 `instructions`, 근거는 `state`, 선택지와 설명은 `criteria`에 넣는다.
2. **호출:** TypeSafe 키 포인터를 `exec.useSecrets`로 `env:TYPESAFE_API_KEY`에 주입하고, 아래 예시의 입력을 바꿔 실행한다.
3. **판단:** `answers.department.choice`와 `answers.department.probabilities`를 읽고 선택 결과와 확률을 활용한다. 애매하면 근거를 보충하거나 보류한다. `confidence`는 정답률이 아니다.

```bash
curl --fail-with-body --silent --show-error --max-time 60 \
  -X POST https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "state": "고객이 같은 금액이 두 번 청구되었다고 문의했다.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "이 문의를 담당할 팀을 선택하라.",
      "criteria": {
        "billing": "결제, 청구, 환불",
        "technical": "제품 오류, 연동 장애",
        "hold": "근거 부족으로 판단 보류"
      }
    }
  }
}
JSON
```

키가 없거나 호출이 실패하면 원인을 알리고 결과 없음으로 처리한다.

공식 규격: https://docs.typesafe.ai/api.md · https://docs.typesafe.ai/introduction/quickstart.md · https://docs.typesafe.ai/confidence.md
