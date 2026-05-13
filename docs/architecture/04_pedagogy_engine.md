# L4. 교수학 엔진 (Pedagogy Engine)

> *진짜 차별화*. 한국에서 이 계층을 제대로 만든 곳 없음.

## 책임

학생 발화·상태에서 *교수학적 결정*을 내린다:
- 지금 Polya 어느 단계? 다음으로?
- 답을 어디까지 미룰까?
- 어떤 소크라테스 카테고리?
- 오개념 감지·개입?
- 정서적으로 안전한가?

L3 LLM은 *생성*, L4는 *결정*이다.

## 5가지 절대 원칙

1. **답 미루기 (Productive Struggle)**
2. **소크라테스 우선** (답 대신 질문)
3. **메타인지 명시화**
4. **다중 풀이 노출**
5. **정서 안전**

## Polya 4단계 엔진

```
1. 이해 (Understand): "문제가 뭐야?"
2. 계획 (Plan): "어떻게 풀까?"
3. 실행 (Execute): "해보자"
4. 검토 (Review): "맞나? 다른 방법?"
```

세션마다 `PolyaState` 추적. 자연스러운 진행·후퇴 가능.

## 답 미루기 4단계

| 단계 | 내용 | 사용 빈도 |
|---|---|---|
| 1. 방향 | 어디로 가야 할지만 | 가장 자주 |
| 2. 의사코드 | 단계의 흐름 | 좌절 시 |
| 3. 부분 풀이 | 일부 단계 시연 | 5회+ 막힘 |
| 4. 전체 풀이 | 마지막 수단 | 매우 드물게 |

규칙: *가능한 가장 빠른 단계에서 멈춤*.

## 소크라테스 질문 카테고리

1. **명료화 (Clarification)** — "어디까지 이해됐어?"
2. **가정 탐색 (Assumption)** — "왜 그렇게 가정했어?"
3. **근거·증거 (Evidence)** — "어떻게 알아?"
4. **관점 (Perspective)** — "다른 방법은?"
5. **함의 (Implication)** — "그러면 다음은?"
6. **메타인지 (Meta)** — "어떻게 도달했어?"

## LTHC — Low Threshold High Ceiling

NRICH 원칙. 동일 task를 학생 수준에 맞춰 진입점·확장 조정.

## 오개념 진단·개입

```
풀이 → 단계별 파싱 → PRM 검증 → 오개념 매핑 → 개입 전략
                                                ↓
                            직접 교정 ❌ / 반례 유도 ✅ / 구체 사례 ✅
```

## 정서 안전 — 톤 필터

### 금지 패턴
- "틀렸", "못 하", "잘못된", "실수", "바보", "포기"

### 권장 표현
- "흥미로운 시도네"
- "거의 다 왔어"
- "다른 각도로 봐볼까"

## 인터페이스

```python
class L4PedagogyService:
    async def decide(
        self,
        student_input: str,
        learner_state: LearnerState,
        session: Session,
    ) -> PedagogyDecision: ...
    
    async def filter_response(
        self, response: str
    ) -> str: ...  # 톤 필터
    
    async def diagnose_misconception(
        self,
        student_solution: ParsedSolution,
        correct_solution: ParsedSolution,
        standard_code: str
    ) -> MisconceptionDiagnosis: ...
```

```python
class PedagogyDecision(BaseModel):
    polya_stage_to_advance: Literal["stay", "next", "previous"]
    hint_level: int  # 1-4
    socratic_category: str
    prompt: str
    system: str
    recommended_tier: LLMTier
    suggested_actions: list[str]
```

## 성공 기준

### Phase 1
- ✅ Polya 4단계 엔진
- ✅ 소크라테스 카탈로그 50+
- ✅ 답 미루기 4단계
- ✅ 오개념 30개 + 개입
- ✅ 정서 필터 0건 위반
- ✅ 평균 답 미루기 도달 깊이 2.5+

### Phase 2
- ✅ LTHC 적응
- ✅ 메타 프롬프트
- ✅ 오개념 100개

### Phase 3+
- ✅ 학습자별 개인화 패턴
- ✅ 교수학 보고서
