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

### PRD `Hint` 엔티티와의 정렬 (graded hint)

> MathScope PRD v1.1을 정본으로 흡수하며 들여온 정렬. 채택 근거는 `MEMORY.md` 2026-05-14 결정 로그 참조.

PRD는 힌트를 **graded 3단계**(1=가장 은근, 3=거의 정답)로 정의하고, 각 힌트가 *얼마나 노출하는지*를 `reveals` 필드로 정량화한다. WhyMath의 "답 미루기 4단계"는 이를 *상위 호환*하는 척도다 — PRD 3단계를 WhyMath 4단계 안에 다음과 같이 매핑한다:

| PRD `Hint.level` | WhyMath 답 미루기 단계 | `reveals` 의미 |
|---|---|---|
| 1 (가장 은근) | 1. 방향 | 다음에 *주목할 대상*만 가리킴 (개념·도구 이름) |
| 2 (중간) | 2. 의사코드 | 풀이의 *단계 흐름*을 노출, 계산은 미노출 |
| 3 (거의 정답) | 3. 부분 풀이 | 일부 단계를 *실제로 시연* |
| — (PRD에 없음) | 4. 전체 풀이 | 마지막 수단 — PRD 척도 밖, 학습 곡선 분석과 함께만 |

- WhyMath 4단계의 1~3단계가 PRD 3단계와 1:1 정렬되고, **4단계(전체 풀이)는 WhyMath 고유 안전망**으로 PRD 척도 위에 한 칸 더 둔다.
- 각 단계 산출 시 `reveals`를 함께 기록해 *세션당 평균 노출량*을 KPI(답 미루기 도달 깊이)로 추적한다.
- 척도 변환은 L4 내부 책임. L5는 "지금 1단계 힌트" 같은 *단계 라벨*만 표시한다(시각화는 L5 책임).

## 소크라테스 질문 카테고리

1. **명료화 (Clarification)** — "어디까지 이해됐어?"
2. **가정 탐색 (Assumption)** — "왜 그렇게 가정했어?"
3. **근거·증거 (Evidence)** — "어떻게 알아?"
4. **관점 (Perspective)** — "다른 방법은?"
5. **함의 (Implication)** — "그러면 다음은?"
6. **메타인지 (Meta)** — "어떻게 도달했어?"

### PRD Socratic 풀이 흐름과의 정렬

PRD의 Socratic 풀이 흐름은 한 문제를 다음 순서로 전개한다:

```
관점 선택 → 전략 선택 → 단계별 풀이 + graded hint → 개념 점화
```

이 흐름은 WhyMath의 Polya 4단계·소크라테스 6카테고리와 *충돌하지 않고 하위 호환*된다 — PRD 흐름의 각 마디는 기존 골격 안의 한 지점이다:

| PRD 흐름 마디 | WhyMath 매핑 |
|---|---|
| 관점 선택 | Polya 2단계(계획) 진입 + 소크라테스 **관점** 카테고리("다른 방법은?") |
| 전략 선택 | Polya 2단계 내 도구·공식 선정 + **가정 탐색** 카테고리 |
| 단계별 풀이 + graded hint | Polya 3단계(실행) + 위 답 미루기 4단계(graded `Hint`) |
| 개념 점화 | Polya 4단계(검토) 직후 — 아래 *개념 점화 지도* 참조 |

- PRD 흐름은 *콘텐츠의 전개 순서*를 규정하고, WhyMath 6카테고리는 *매 발화의 질문 종류*를 규정한다. 둘은 직교한다.
- L4는 학생이 PRD 흐름의 어느 마디에 있든 그 마디에 맞는 소크라테스 카테고리를 골라 `PedagogyDecision.socratic_category`로 반환한다.

## 개념 점화 지도 (Concept Ignition Map)

> MathScope PRD v1.1을 정본으로 흡수하며 들여온 정렬. 채택 근거는 `MEMORY.md` 2026-05-14 결정 로그 참조.

PRD는 풀이 완료 시 *그 풀이 과정에서 활성화된 개념 노드*를 학생에게 시각화한다 — "이 한 문제를 풀며 너는 이 개념들을 썼다"를 보여주는 지도다. WhyMath에서는 이 기능을 **L4 판정 + L5 시각화**로 책임 분리한다:

- **L4의 책임 — 어떤 개념이 점화됐는가 판정**: Polya 4단계(검토) 진입 시점에, 해당 세션의 풀이 흐름·`SolutionPath.concept_sequence`(L3 산출)·학생 발화를 근거로 *실제로 활성화된 개념 노드 집합*과 각 노드의 *점화 강도*(주개념/보조개념/스치듯 언급)를 판정한다. 개념 노드의 식별자·인접 관계 자체는 L1 개념 그래프에서 온다 — L4는 그래프를 *구현하지 않고*, "이번 풀이에서 이 노드들이 켜졌다"는 판정만 한다.
- **L5의 책임 — 켜진 노드를 시각화**: L4가 반환한 점화 노드 집합·강도를 받아 학생에게 지도 형태로 표시한다(시각화 명세는 L5 책임, `05_interaction.md` 참조).
- **경계**: L4는 *판정자*, L5는 *표시자*, L1은 *그래프 원천*. L4는 L1을 호출하고 L5는 L4 출력을 받는다 — 7계층 의존 방향과 일치.

`PedagogyDecision`에 검토 단계 산출용 필드를 둔다:

```python
class IgnitedConcept(BaseModel):
    concept_node_id: str          # L1 개념 그래프의 노드 식별자
    ignition_strength: Literal["primary", "supporting", "touched"]

class PedagogyDecision(BaseModel):
    # ... 기존 필드 ...
    ignited_concepts: list[IgnitedConcept] | None  # Polya 4단계에서만 채워짐
```

- 점화 판정은 Polya 4단계에서만 일어나며, 그 외 단계에서는 `None`이다.
- *세션당 점화 노드 수·강도 분포*는 L2 학습자 모델의 `MasteryState` 갱신 입력으로도 쓰일 수 있으나, 그 갱신은 L2 책임 — L4는 판정 결과만 넘긴다.

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
    # 명칭 충돌 해소(2026-05-20, docs/architecture/03a_l3_router_design.md §0.1): 구 LLMTier 단일 enum이
    # 두 축(비용·위치 / 로컬 크기)으로 분해됨. L4는 *교수학적 권장 비용 티어*(축1)만 힌트로 넘긴다 —
    # 로컬 모델 크기(축2 FAST/MID/QUALITY) 세분·동기성은 L3 라우터가 신호로 최종 결정(계층 경계 준수).
    recommended_cost_tier: CostTier  # 구 recommended_tier: LLMTier → CostTier(LOCAL/CLOUD_MID/CLOUD_HIGH)
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
