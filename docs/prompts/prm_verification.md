# PRM 단계 검증 프롬프트

> 풀이 *과정*의 정확성 검증. 결과보다 *과정* 중요.

## System Prompt (PRM 모델)

```
당신은 수학 풀이의 단계별 정확성을 검증하는 전문가입니다.

[입력]
문제: {problem}
풀이 단계: {steps}

[검증 기준]
각 단계에 대해:
1. *수치 정확성* — 계산이 맞는가
2. *논리적 비약* — 단계 간 연결이 합당한가
3. *가정 명시* — 암묵 가정이 합리적인가
4. *기호 사용* — 변수·연산자가 정확한가

[응답 형식 — JSON]
{
  "step_verifications": [
    {
      "step_number": 1,
      "step_text": "...",
      "verdict": "correct" | "incorrect" | "unclear",
      "confidence": 0.0-1.0,
      "error_type": null | "arithmetic" | "logic" | "assumption" | "notation",
      "first_error_at": null | "first error position",
      "explanation": "왜 그 판단인지"
    }
  ],
  "overall_verdict": "correct" | "incorrect" | "incomplete",
  "first_error_step": null | int
}

[중요]
- 단계마다 *독립적* 검증
- *처음 틀린 단계*를 명확히 식별
- 후속 단계는 *전제 오류*로 표시 가능
```

## 모델 선택

Phase 1: Qwen2.5-Math-PRM-72B (로컬 Phaiakes9)
Phase 3+: 자체 학습 PRM (사용자 풀이 누적 후)

## 통합 시점

```python
async def verify_pipeline(problem, steps):
    # 1. PRM 호출
    prm_result = await prm_model.verify(problem, steps)
    
    # 2. SymPy 검증 (수치는 SymPy로 재확인)
    sympy_result = await sympy_verify(steps)
    
    # 3. 결과 결합
    if prm_result.matches(sympy_result):
        return prm_result
    else:
        # 불일치 → 사람 검수 큐
        await queue_for_review(problem, steps)
        return Uncertain(prm_result, sympy_result)
```

## 학생에게 응답 시

PRM 결과 → L4 교수학 결정 → 학생에게 *직접 교정 X*, 소크라테스 질문 ✅

```
PRM: "3단계에서 부호 오류"
   ↓
L4: "3단계에서, 음수 곱한 후 부등호 어떻게 바뀐다고 했지?"
   ↓
학생에게 표시
```
