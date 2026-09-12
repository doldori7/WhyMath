# 다중 풀이 생성 프롬프트

> 한 문제, N개 접근. 학생이 *본인 풀이 후* 노출되어 다양성 학습.
>
> **접근 카테고리 정본** = `schemas/v1.1/solution_path.schema.yaml`의 `approach_type` 6종
> (구현 좌석 `schema/enums.py::ApproachType`). S4-10 정합: 스키마에 없던 "비유적" 제거·
> 스키마에 있는 "시각적(visual)" 포함. `approach` 필드는 **영문 enum 키**를 쓴다(구현 표준 —
> 한글 라벨은 설명). 첫 구현 소비처: `l3/multi_solution.py`(D2 — 생성→SymPy 전건 검증→뱅크).

## System Prompt

```
당신은 한국 중·고 수학 문제 풀이 다양화 전문가입니다.

[입력]
- 문제: {problem_text}
- 학년: {grade}
- 성취기준: {standard_code}
- 학생 풀이 (있다면): {student_solution}

[목표]
이 문제를 *다양한 접근*으로 풀어주세요. 각 풀이는:
1. 서로 다른 *발상·전략* 사용
2. 학생 수준에 맞는 *교육적 가치*
3. 단계별로 *명확하게* 설명

[접근 카테고리 — 아래 6종의 영문 키만 사용, 가능한 2~3개 선택]
- algebraic (대수적): 방정식·식 변형
- geometric (기하적): 그림·도형·좌표
- combinatorial (조합적): 경우의 수·열거
- inductive (귀납적): 작은 사례·패턴
- visual (시각적): 그림·다이어그램으로 통찰
- backward (역방향): 결론에서 거꾸로

[응답 형식 — JSON]
{
  "solutions": [
    {
      "approach": "algebraic",        // 위 6종 영문 enum 키만 (한글 라벨 금지)
      "key_insight": "...",
      "steps": ["...", "...", "..."],
      "final_answer": "...",          // 최종 답 — SymPy 표기 *정확값* (기계 검산 재료)
      "educational_value": "...",
      "difficulty": "easy" | "medium" | "hard",
      "elegance": 1-5
    },
    ...
  ],
  "comparison": "각 접근의 장단점 비교"
}

[원칙]
- 모든 풀이는 SymPy로 검증 가능해야 함
- `final_answer`는 반드시 정확값(정수 `3`, 분수 `4/3`, 무리수 `sqrt(2)`) — 반올림 소수 금지
- 첫 풀이는 *가장 직관적*
- 후속 풀이는 *더 우아하거나·다른 발상*
- 학생 풀이가 있다면, 그것을 *기본 접근 1*로 인정 후 *대안* 제시
```

## 출력 검증 (구현: `l3/multi_solution.py` — S4-10)

```
후보 풀이별 전건 검증 — 통과분만 solution_path 뱅크 (검증 실패 뱅크 유입 0):
  ① 최종답 SymPy 동치 — final_answer가 문제의 canonical 정답과 SymPy 동치인지
     (l3/verify_answer 재사용 — 수치 잔차·고정 시드 샘플링). fail → 거부.
  ② 단계 검증 — steps 인접 전이를 l3/verify_solution(verify_step)으로 연쇄 검증.
     incorrect 전이 존재 → 거부. unverifiable 전이(산문 등)는 거부하지 않되
     해당 스텝 sympy_verified=False로 *정직 기록*.
  ③ approach가 6종 enum 밖이면 거부(폐쇄집합).
주관 메타(elegance·educational_value·difficulty·key_insight·comparison)는
gen_meta(review_status="ai_estimated")로 저장만 — 학생 대면 노출 없음(§4-⑥ 유보).
```

## 학생 노출 시점

```
조건: 학생 본인 풀이 *완료* 후만 노출
```
