# Polya 4단계 프롬프트 템플릿

## Stage 1: 이해 (Understand)

```
[목적] 학생이 문제를 *자기 언어로* 다시 말하게.

[프롬프트]
이 문제, 잠깐 같이 읽어볼까?

다음 3가지 질문에 답해줘:
1. *주어진 정보*가 뭐야? (조건들)
2. *구해야 하는 게* 뭐야? (목표)
3. *모르는 게* 뭐야? (미지수·미정 요소)

너의 말로 다시 표현해줘.
```

## Stage 2: 계획 (Plan)

```
[목적] 학생이 *전략·접근*을 떠올리게.

[프롬프트]
좋아, 이제 *어떻게 풀지* 계획을 세워보자.

다음 중 떠오르는 게 있어?
- 비슷한 문제 본 적 있어?
- 어떤 *공식·개념·도구*가 떠올라?
- 더 *작은 경우*부터 시작해볼까?
- *그림·표·도형*으로 정리하면?

먼저 떠오르는 거 하나만 말해줘.
```

## Stage 3: 실행 (Execute)

```
[목적] 학생이 계획대로 *실행*하게. AI는 *관찰자*.

[프롬프트]
좋은 계획이야. 한번 그 방법으로 풀어볼래?

천천히 단계별로 적어줘.
중간에 막히면 어디서 막혔는지 말해주면 같이 봐줄게.
```

[중간 점검 — 학생이 풀이 단계 제출 시]
```
[목적] 답 X, 단계 검증

[프롬프트]
{n}단계까지 좋아.
{n+1}단계에서 너의 가정이 뭐였어? *왜* 그렇게 한 거야?
```

## Stage 4: 검토 (Look back)

```
[목적] 메타인지 강화. 일반화·전이 가능성.

[프롬프트]
풀이 끝났네. 잠깐, 몇 가지 같이 생각해보자:

1. *답이 합리적이야*? (검산·단위·크기)
2. *다른 방법*으로도 풀릴 거 같아?
3. *어떻게* 이 풀이에 도달했어? (메타인지)
4. 이 *발상*을 다른 비슷한 문제에 쓸 수 있을까? (전이)

먼저 떠오르는 거 하나만.
```

## 단계 전환 트리거

```python
def should_advance(state: PolyaState, student_input: str) -> bool:
    """다음 단계로 갈지 판단"""
    if state == PolyaState.UNDERSTAND:
        # 학생이 *자기 언어로* 문제를 재진술했는가
        return has_restated_problem(student_input)
    
    if state == PolyaState.PLAN:
        # 학생이 *전략·접근*을 제시했는가
        return has_proposed_strategy(student_input)
    
    if state == PolyaState.EXECUTE:
        # 학생이 *답에 도달*했는가
        return has_reached_answer(student_input)
    
    if state == PolyaState.REVIEW:
        # 학생이 *메타·일반화* 응답 했는가
        return has_reflected(student_input)
    
    return False
```

## 후퇴 트리거

학생이 한 단계 어려우면 *이전 단계로* 자연스럽게:

```
"잠깐, 한 발 뒤로 가서, [이전 단계 질문]"
```
