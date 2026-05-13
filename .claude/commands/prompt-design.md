---
description: 교수학적으로 검증된 프롬프트 템플릿 설계·테스트
argument-hint: "[목적] 예: socratic-coaching, polya-4step"
---

# /prompt-design — 교수학 프롬프트 설계

## 임무
*답을 미루고 학생이 스스로 도착하게 만드는* 프롬프트를 체계적으로 설계·테스트한다.

## 실행 절차

### 1. 목적 분류
`$ARGUMENTS`를 다음 카테고리로 분류:

| 카테고리 | 예시 | 핵심 패턴 |
|---|---|---|
| **소크라테스 코칭** | socratic-coaching | 답이 아닌 *질문* |
| **Polya 4단계** | polya-4step | 이해→계획→실행→검토 |
| **오개념 진단** | misconception-dx | 풀이 패턴 → 오개념 |
| **다중 풀이** | multi-solution | 같은 문제 N개 접근 |
| **시각화 생성** | manim-gen | 학생 수준 맞춤 |
| **메타인지 유도** | metacognition | *왜* 그렇게 풀었어 |
| **부모 보고서** | parent-report | 따뜻하지만 정확 |
| **PRM 검증** | prm-verify | 단계별 엄밀성 |

### 2. 표준 템플릿 골격

```python
"""
[프롬프트명]
목적: [한 줄]
대상: [학생 학년·수준]
출력 형식: [JSON·자연어·둘 다]
검증 방법: [평가 기준]
"""

SYSTEM = """
당신은 [역할: 한국 중·고 수학 메타인지 코치].

[학생 컨텍스트]
- 학년: {grade}
- 성취기준: {standard_code}
- BKT 숙달도: {mastery_level}
- 최근 오개념: {misconceptions}

[행동 원칙]
1. *답을 절대 바로 주지 않는다*. Polya 4단계로 진행.
2. 학생이 막혔다고 *직접 코드를 보여주지 않는다*.
3. 항상 *질문*으로 답한다. 다음 4단계 중 가능한 가장 빠른 단계에서:
   - 1단계: 방향만 제시
   - 2단계: 의사코드/접근 힌트
   - 3단계: 부분 풀이
   - 4단계: 전체 풀이 (마지막 수단)
4. 학생 발화에서 *오개념 신호* 발견 시 *직접 교정하지 말고* 반례·예시로 자각 유도.
5. 부정적 표현 금지 ("틀렸어", "이거 모르네"). 대신 "흥미로운 시도다, 다른 각도로 봐볼까?"

[출력 형식]
{output_format}
"""

USER = """
[학생 입력]
{student_input}

[학생 풀이 (있다면)]
{student_solution}
"""
```

### 3. 테스트 케이스 설계
모든 프롬프트는 다음 시나리오로 테스트:

```python
TEST_CASES = [
    {
        "name": "정상 — 학생이 막혔을 때",
        "input": "...",
        "expected_behavior": "1단계 힌트만 제공",
        "anti_patterns": ["전체 답 제공", "부정적 표현"]
    },
    {
        "name": "오개념 — 학생이 잘못된 가정",
        "input": "...",
        "expected_behavior": "반례로 자각 유도",
        "anti_patterns": ["직접 교정", "그건 틀렸어"]
    },
    {
        "name": "답 강요 — 학생이 답만 요구",
        "input": "그냥 답 알려주세요",
        "expected_behavior": "공감 + 답 미루기 + 다음 힌트",
        "anti_patterns": ["바로 답 제공", "냉정한 거부"]
    },
    {
        "name": "정서 — 학생이 좌절",
        "input": "이거 너무 어려워요 못 하겠어요",
        "expected_behavior": "공감 + 작게 쪼개기",
        "anti_patterns": ["격려 없이 진도", "과도한 위로"]
    }
]
```

### 4. 평가 메트릭
프롬프트 응답을 다음으로 평가:

- **답 미루기 단계**: 1~4 중 어디서 멈췄나 (낮을수록 좋음)
- **질문 비율**: 응답 중 *질문*이 차지하는 비율 (높을수록 좋음)
- **오개념 명시화**: 학생 오개념을 *언어화*했나
- **메타인지 유도**: "왜 그렇게 생각해?" 류 질문 포함
- **정서 안전**: 부정적 표현 0건

### 5. Langfuse 등록
프롬프트를 Langfuse에 등록:

```python
from langfuse import Langfuse
langfuse = Langfuse()

langfuse.create_prompt(
    name="socratic-coaching-v1",
    prompt=SYSTEM,
    config={
        "model": "claude-sonnet-4-6",
        "temperature": 0.7,
        "max_tokens": 800
    },
    labels=["pedagogy", "socratic", "v1"]
)
```

### 6. A/B 테스트 설계
2개 이상 변형(variation) 만들어 비교:
- v1: 기준 (현재 표준)
- v2: 변형 (예: 더 빠른 답 제공)
- v3: 변형 (예: 더 많은 시각화)

KPI 추적:
- 학생 *재방문율*
- 답 미루기 단계 깊이
- 학생 *스스로 도착 비율*

### 7. 출력 산출물

```
✅ 프롬프트 설계 완료: [name]

생성된 파일:
- docs/prompts/[name].md (명세)
- src/backend/prompts/[name].py (구현)
- tests/prompts/test_[name].py (테스트)
- Langfuse 등록: [URL]

테스트: ✅ 8/8 통과 (앵커 시나리오)

다음 단계:
> /implement llm:[name] # 라우터에 통합
> A/B 테스트 시작 (Phase 1 사용자 50명)
```

## 원칙

### 답 미루기가 기본값
- 모든 프롬프트는 *답 미루기*가 기본
- 답 제공은 *예외*적이며 4단계 중 최후 단계

### 학생 발화 우선
- 학생의 *언어*를 그대로 반영
- LLM이 *교사 톤*으로 위에서 내려다보지 않음

### 컨텍스트 주입 명시적으로
- 학습자 모델 결과(BKT·오개념)를 *항상* 컨텍스트로
- 학생 학년·교과서·진도를 *항상* 컨텍스트로

### 버전 관리
- 모든 프롬프트는 버전 번호 (v1, v2, ...)
- 변경 시 *기존 버전 보존* + 신규 추가

## 호출 예시

```
> /prompt-design socratic-coaching
> /prompt-design polya-4step-quadratic
> /prompt-design misconception-dx-discriminant
> /prompt-design parent-weekly-report
```
